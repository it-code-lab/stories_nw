import shutil
from flask import Flask, request, jsonify, render_template, send_from_directory, abort
import subprocess, json, math
from flask_cors import CORS
import os
import traceback  # to print detailed error info
from caption_generator import prepare_captions_file_for_notebooklm_audio
from get_audio import get_audio_file
from scraper import scrape_and_process  # Ensure this exists
from settings import background_music_options, font_settings, tts_engine, voices, sizes
from video_editor import batch_process
from youtube_uploader import upload_videos
import re
from pathlib import Path
import wave
from urllib.parse import unquote

app = Flask(__name__, template_folder='templates')
CORS(app)

# Always resolve relative to this file (server.py)
BASE_DIR = Path(__file__).resolve().parent
AUDIO_PATH = BASE_DIR / "audio.wav"   # your file is beside server.py

def url_to_fs(url_path: str, base_subdir: str) -> Path:
    """
    Map a URL like '/thumbnail_images/a/b.png' to a safe filesystem path
    under BASE_DIR/base_subdir/a/b.png
    """
    if not url_path:
        abort(400, "Missing image path")
    url_path = unquote(url_path).lstrip("/")              # remove leading '/'
    # strip the first segment (should match base_subdir)
    first, _, tail = url_path.partition("/")
    if first != base_subdir:
        abort(400, f"Unexpected base folder: {first}")
    fs_path = (BASE_DIR / base_subdir / tail).resolve()
    allowed_base = (BASE_DIR / base_subdir).resolve()
    if not str(fs_path).startswith(str(allowed_base)):
        abort(400, "Invalid image path")
    return fs_path

def _duration_via_wave(p: Path):
    """Try Python wave for PCM WAV."""
    import wave
    with wave.open(str(p), 'rb') as w:
        frames = w.getnframes()
        rate = w.getframerate()
        if rate == 0:
            raise ValueError("Invalid WAV: sample rate is 0")
        return frames / float(rate)

def _duration_via_ffprobe(p: Path):
    """Fallback: use ffprobe for any codec/container."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(p)
    ]
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    # ffprobe prints a float in seconds (can be "N/A")
    if not out or out.upper() == "N/A":
        raise ValueError("ffprobe returned no duration")
    dur = float(out)
    if not math.isfinite(dur):
        raise ValueError("Non-finite duration from ffprobe")
    return dur

@app.route("/api/audio-duration")
def audio_duration():
    p = AUDIO_PATH
    if not p.exists():
        return jsonify({"error": f"File not found: {str(p)}", "cwd": str(BASE_DIR)}), 404
    try:
        # 1) Try wave first (fast, if PCM)
        try:
            seconds = _duration_via_wave(p)
        except Exception as e_wave:
            # 2) Fallback to ffprobe
            seconds = _duration_via_ffprobe(p)

        return jsonify({"seconds": round(seconds, 2), "path": str(p)})
    except subprocess.CalledProcessError as e:
        return jsonify({
            "error": "ffprobe failed",
            "detail": e.output
        }), 500
    except Exception as e:
        return jsonify({
            "error": type(e).__name__,
            "detail": str(e),
            "path": str(p)
        }), 500

@app.route('/edit_vid_thumbnail/<path:filename>')
def serve_generated_thumb(filename):
    return send_from_directory(BASE_DIR / 'edit_vid_thumbnail', filename)


@app.route('/generate_thumbnail', methods=['POST'])
def generate_thumbnail():
    try:
        from thumbnail_gen import create_thumbnail

        image_url = request.form.get('image')  # e.g. "/thumbnail_images/foo/bar.png"
        bg_color = request.form.get('bg_color', '#000000')
        text = request.form.get('text', '')
        colors = request.form.get('colors', 'auto')
        print("Generating thumbnail for image:", image_url)
        # Map the URL to a filesystem path safely
        fs_image_path = url_to_fs(image_url, base_subdir='thumbnail_images')
        print("Filesystem image path:", fs_image_path)

        # Ensure output folder exists; return a served URL
        out_dir = BASE_DIR / 'edit_vid_thumbnail'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / 'thumbnail.png'
        out_url = f"/edit_vid_thumbnail/{out_file.name}"

        create_thumbnail(
            image_path=str(fs_image_path),
            bg_color=bg_color,
            text=text,
            colors=colors,
            output_path=str(out_file)
        )

        return jsonify({"message": "✅ Thumbnail created successfully!", "thumbnail": out_url})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _safe_join(base: Path, sub: str) -> Path:
    """Prevent path traversal; always return a child of base."""
    p = (base / (sub or "")).resolve()
    base = base.resolve()
    if not str(p).startswith(str(base)):
        abort(400, "Invalid folder")
    return p

def _list_current(base_url: str, base_dir: Path, rel_folder: str, exts: set[str]):
    """
    Return files in the current folder and immediate subfolders.
    - base_url: '/thumbnail_images' or '/background_videos'
    - base_dir: BASE_DIR/'thumbnail_images' or 'background_videos'
    - rel_folder: '' or 'krishna/diwali'
    """
    cur = _safe_join(base_dir, rel_folder)
    if not cur.exists():
        return {"cwd": rel_folder, "folders": [], "files": []}

    # immediate subfolders
    folders = []
    for d in sorted([p for p in cur.iterdir() if p.is_dir()]):
        rel = (Path(rel_folder) / d.name).as_posix()
        folders.append(rel)

    # files in current folder only
    files = []
    for f in sorted([p for p in cur.iterdir() if p.is_file()]):
        if f.suffix.lower() in exts:
            rel_file = (Path(rel_folder) / f.name).as_posix()
            files.append(f"{base_url}/{rel_file}")

    # build breadcrumb segments for UI
    crumbs = []
    accum = []
    for part in Path(rel_folder).parts:
        accum.append(part)
        crumbs.append({"name": part, "path": "/".join(accum)})
    return {"cwd": rel_folder, "folders": folders, "files": files, "breadcrumbs": crumbs}

def _list_all_folders(base_dir: Path):
    """Return ALL subfolders (including root '') for the folder dropdown."""
    out = [""]
    for d, subdirs, _ in os.walk(base_dir):
        rel = os.path.relpath(d, base_dir)
        if rel == ".":
            continue
        out.append(rel.replace("\\", "/"))
    return sorted(out)

# --- STATIC file serving (so subpaths are accessible from <img>/<video> tags) ---
@app.route('/thumbnail_images/<path:filename>')
def serve_thumb_image(filename):
    return send_from_directory(BASE_DIR / 'thumbnail_images', filename)

@app.route('/background_videos/<path:filename>')
def serve_bg_video(filename):
    return send_from_directory(BASE_DIR / 'background_videos', filename)

# --- BROWSING APIs ---
@app.get('/list_thumbnail_images')
def list_thumbnail_images():
    folder = request.args.get('folder', '').strip('/')
    base = BASE_DIR / 'thumbnail_images'
    data = _list_current('/thumbnail_images', base, folder, {'.png', '.jpg', '.jpeg', '.webp'})
    data["all_folders"] = _list_all_folders(base)
    return jsonify(data)

@app.get('/list_background_videos')
def list_background_videos():
    folder = request.args.get('folder', '').strip('/')
    base = BASE_DIR / 'background_videos'
    data = _list_current('/background_videos', base, folder, {'.mp4', '.mov', '.mkv', '.webm'})
    data["all_folders"] = _list_all_folders(base)
    return jsonify(data)

@app.route('/select_background_video', methods=['POST'])
def select_background_video():
    """Copy chosen video to edit_vid_input folder for use."""
    data = request.json
    src = data.get('video')
    if not src:
        return jsonify({"error": "Missing video path"}), 400

    filename = os.path.basename(src)
    src_path = os.path.join(BASE_DIR, src.strip("/"))
    dest_path = os.path.join(BASE_DIR, "edit_vid_input", filename)
    if not os.path.exists(src_path):
        return jsonify({"error": f"File not found: {src_path}"}), 404

    import shutil
    shutil.copy(src_path, dest_path)
    return jsonify({"message": "✅ Video selected and ready for editing!", "dest": dest_path})

@app.route('/sounds/<path:filename>')
def serve_sound(filename):
    sounds_dir = os.path.join(app.root_path, 'sounds')
    return send_from_directory(sounds_dir, filename)


# ------------------------ API ROUTES ------------------------ #

@app.route('/get_full_text', methods=['GET'])
def get_full_text():
    try:
        with open("temp/full_text.txt", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

@app.route('/get_word_timestamps', methods=['GET'])
def get_word_timestamps():
    try:
        with open("temp/word_timestamps.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

@app.route('/save_word_timestamps', methods=['POST'])
def save_word_timestamps():
    try:
        data = request.json
        with open("temp/word_timestamps.json", "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return jsonify({"message": "✅ Word timestamps updated successfully!"})
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

@app.route('/get_structured_output', methods=['GET'])
def get_structured_output():
    try:
        with open("temp/structured_output.json", "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

# ------------------------ HTML UI ROUTES ------------------------ #

@app.route('/')
def index():
    return render_template('index.html',
        music_options=background_music_options,
        style_options=font_settings,
        tts_options=tts_engine,
        voice_genders=voices,
        voice_map=voices,
        sizes=sizes
    )

@app.route('/thumbnail')
def thumbnail():
    return render_template('thu_index.html')

@app.route('/hindi_caption_builder')
def hindicaptions():
    return render_template('hindi_caption_builder.html')

@app.route('/aivideoprompt')
def aivideoprompt():
    return render_template('aivideoprompt.html')

@app.route('/prepare_captions')
def prep_caption():
    return render_template('index_captions.html')

@app.route('/video/<filename>')
def serve_video(filename):
    return send_from_directory(directory='.', path=filename)

@app.route('/create_portrait_n_add_caption')
def create_portrait_n_add_caption():
    try:
        print("Processing request...create_portrait_n_add_caption")
        create_portrait()
        add_caption()
        return "✅ create_portrait_n_add_caption completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.route('/apply_caption')
def add_caption():
    try:
        print("Processing request...apply_caption")

        from apply_captions import add_captions_to_video

        # If edit_vid_output/out_landscape.mp4 and edit_vid_output/captions_landscape.ass exists
        

        if os.path.isfile("edit_vid_output/out_landscape.mp4") and os.path.isfile("edit_vid_output/captions_landscape.ass"):
            add_captions_to_video("edit_vid_output/out_landscape.mp4", "edit_vid_output/captions_landscape.ass", "edit_vid_output/landscape_with_captions.mp4")
        if os.path.isfile("edit_vid_output/out_portrait.mp4") and os.path.isfile("edit_vid_output/captions_portrait.ass"):
            add_captions_to_video("edit_vid_output/out_portrait.mp4", "edit_vid_output/captions_portrait.ass", "edit_vid_output/portrait_with_captions.mp4")

        return "✅ apply_caption completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500  


@app.route('/convert_landscape_to_portrait')
def create_portrait():
    try:
        print("Processing request...convert_landscape_to_portrait")

        from convert_to_portrait import convert_landscape_to_portrait
        if os.path.isfile("edit_vid_output/out_landscape.mp4"):
            convert_landscape_to_portrait("edit_vid_output/out_landscape.mp4", "edit_vid_output/out_portrait.mp4")

        return "✅ convert_landscape_to_portrait completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500  

@app.route('/process', methods=['POST'])
def process():
    try:
        print("Processing request...")
        urls = request.form.get('urls', '')
        excel = request.form.get('excel', 'no')
        notebooklm = request.form.get('notebooklm', 'no')
        language = request.form.get('language', 'english')
        tts = request.form.get('tts', 'google')
        gender = request.form.get('gender', 'Female')
        voice = request.form.get('voice', 'Joanna')
        size = request.form.get('size', 'YouTube Shorts')
        music = request.form.get('music')
        max_words = int(request.form.get('max_words', 4))
        fontsize = int(request.form.get('fontsize', 90))
        y_pos = request.form.get('y_pos', 'center')
        style = request.form.get('style', 'style2')
        skip_puppeteer = request.form.get('skip_puppeteer', 'no')
        skip_captions = request.form.get('skip_captions', 'no')
        pitch = request.form.get('pitch', 'adult')
        disable_subscribe = request.form.get('disable_subscribe', 'no')

        scrape_and_process(urls, excel, size, music, max_words, fontsize, y_pos,
                           style, voice, language, gender, tts,
                           skip_puppeteer, skip_captions, pitch, disable_subscribe, notebooklm)

        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.route('/caption', methods=['POST'])
def caption():
    try:
        print("Processing request...caption")
        music = request.form.get('music', 'no')
        language = request.form.get('language', 'english')
        prepare_captions_file_for_notebooklm_audio(
            audio_path="audio.wav",
            language=language,
            is_song=music == 'yes'
        )

        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.route('/generatettsaudio', methods=['POST'])
def generatettsaudio():
    try:
        print("Processing request...generatettsaudio")

        ttstext = request.form.get('ttstext', '')

        language = request.form.get('language', 'english')
        tts_engine = request.form.get('tts', 'google')
        gender = request.form.get('gender', 'Female')
        output_audio_file = "audio.wav"


        generated_file = get_audio_file(ttstext, output_audio_file, tts_engine, language, gender)
        shutil.copy("audio.wav", "edit_vid_audio/audio.wav")
        
        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500
        
@app.route('/bulkupload', methods=['POST'])
def bulkupload():
    try:
        print("Processing request...upload_videos")
        upload_videos()  # Assuming this function is defined in youtube_uploader.py

        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500
    
@app.route('/runobsrecorder', methods=['POST'])
def run_obs_recorder():
    try:
        print("Processing request...run OBS recorder")
        orientation = request.form.get('orientation', 'landscape')
        duration = request.form.get('duration', '10')  # Default to 10 seconds if not provided
        selectedStyle = request.form.get('captStyle', 'style1')
        captionLength = request.form.get('captLength', '5')
        bgMusicSelected = request.form.get('bgMusicSelect', 'none')
        minLineGapSec = request.form.get('minLineGapSec', '0.40')
        disableSubscribe = request.form.get('disableSubscribe', 'yes')
        outputfile = request.form.get('outputfile', 'test.mp4')

        print("Form payload →", request.form.to_dict(flat=False))
        
        cmd = [
            "node", "puppeteer-launcher.js",
            outputfile, duration, orientation, captionLength, selectedStyle,
            bgMusicSelected, "0.05", "1", disableSubscribe, minLineGapSec
        ]
        print("▶️ Running Puppeteer with:", cmd)
        import subprocess
        subprocess.run(cmd)

        # Here you would call the function to run OBS recorder
        # For example: run_obs_recorder_function()

        # return "✅ Processing started!"
        return "✅ OBS Recorder started successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500
    
@app.route('/editvideos', methods=['POST'])
def run_video_editor():
    try:
        print("Processing request...run edit videos")
        orientation = request.form.get('orientation', 'auto')
        add_music = True
        bg_music_folder = request.form.get('bgmusic')
        if bg_music_folder == 'none':
            add_music = False
        topcut = request.form.get('topcut',0)
        if topcut == '':
            topcut = 0

        bottomcut = request.form.get('bottomcut',0)
        if bottomcut == '':
            bottomcut = 0

        slowfactor = request.form.get('slowfactor',0)
        if slowfactor == '':
            slowfactor = 0

        slow_down = True
        if slowfactor == 0:
            slow_down = False

        add_watermark = True

        watermarkposition = request.form.get('watermarkposition','bottom-left')
        if watermarkposition == "none":
            add_watermark = False

        batch_process(
            input_folder="edit_vid_input",
            output_folder="edit_vid_output",
            bg_music_folder="god_bg",
            remove_top=float(topcut),
            remove_bottom=float(bottomcut),
            add_music=add_music,
            slow_down=slow_down,
            slow_down_factor=float(slowfactor),
            target_orientation=orientation, 
            add_watermark=add_watermark,
            watermark_path="logo.png",
            watermark_position=watermarkposition,
            watermark_scale=0.15
        )
        return "✅ Videos Processed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500    

@app.route('/sunotovideogenerator', methods=['POST'])
def run_sunotovideogenerator():
    try:
        print("*** Processing request sunotovideogenerator: Enlarging clip")
        orientation = 'auto'
        add_music = False
        topcut = 0
        bottomcut = 0
        slow_down = True
        slowfactor = request.form.get('slowfactor',1)
        if slowfactor == '' or slowfactor == '1':
            slowfactor = 1
            slow_down = False

        size = request.form.get('size', 'landscape')

        add_watermark = False
        watermarkposition = 'bottom-left'

        batch_process(
            input_folder="edit_vid_input",
            output_folder="edit_vid_output",
            bg_music_folder="god_bg",
            remove_top=float(topcut),
            remove_bottom=float(bottomcut),
            add_music=add_music,
            slow_down=slow_down,
            slow_down_factor=float(slowfactor),
            target_orientation=orientation, 
            add_watermark=add_watermark,
            watermark_path="logo.png",
            watermark_position=watermarkposition,
            watermark_scale=0.15
        )
        print("✅ Processing request sunotovideogenerator: Enlarging completed successfully")
        # copy files from edit_vid_output to edit_vid_input for next step
        import shutil
        for filename in os.listdir("edit_vid_output"):
            shutil.copy(os.path.join("edit_vid_output", filename), os.path.join("edit_vid_input", filename))

        print("*** Processing request sunotovideogenerator: Assembling clips to make video song")
        from assemble_from_videos import assemble_videos
        assemble_videos(
            video_folder="edit_vid_input",                  # or "edit_vid_output" if you pre-made KB clips
            audio_folder="edit_vid_audio",
            output_path="edit_vid_output/composed_video.mp4",
            fps=30,
            shuffle=True,                                   # different order each run
            prefer_ffmpeg_concat=True                       # auto-uses concat if safe; else MoviePy
        )

        print("✅ Processing request sunotovideogenerator: Assembling completed successfully")
        # place copy of audio file (mp3/wav) from edit_vid_audio to root folder as audio.wav

        audio_folder = "edit_vid_audio"
        import shutil
        from pydub import AudioSegment
        # get the first file found in that folder
        audio_file = os.listdir(audio_folder)[0]
        audio_path = os.path.join(audio_folder, audio_file)

        # output path in root folder
        output_path = "audio.wav"

        # convert mp3 → wav (if needed), else just copy
        if audio_file.lower().endswith(".mp3"):
            # convert using pydub (requires ffmpeg installed)
            sound = AudioSegment.from_mp3(audio_path)
            sound.export(output_path, format="wav")
        else:
            # already wav → overwrite if exists
            shutil.copy(audio_path, output_path)

        print(f"✅ Saved audio file as {output_path}")

        #place copy of composed_video.mp4 from edit_vid_output to root folder as composed_video.mp4. Replace if exists

        shutil.copy("edit_vid_output/composed_video.mp4", "composed_video.mp4")

        # Also place copy of composed_video.mp4 from edit_vid_output to edit_vid_output/out_{size}.mp4. Replace if exists
        shutil.copy("edit_vid_output/composed_video.mp4", f"edit_vid_output/out_{size}.mp4")

        print("✅ Copied composed video to root folder as composed_video.mp4")


        print("*** Processing request sunotovideogenerator...creating captions file ")
        music = request.form.get('music', 'no')
        language = request.form.get('language', 'english')
        if language != 'hindi':
            prepare_captions_file_for_notebooklm_audio(
                audio_path="audio.wav",
                language=language,
                is_song=music == 'yes'
            )
        # else:
        #     if size == 'landscape':
        #         create_portrait()
            # add_caption()
        return "✅ Videos Processed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500    


@app.route('/sunonimagetovideogenerator', methods=['POST'])
def run_sunonimagetovideogenerator():
    try:
        print("*** Processing request sunonimagetovideogenerator: creating clips")
        duration = request.form.get('duration',10)
        if duration == '':
            duration = 10

        video_size = (1920,1080)
        size = request.form.get('size', 'landscape')
        if size == 'portrait':
            video_size = (1080,1920)

        from make_kb_videos import export_kb_videos
        export_kb_videos(
            input_folder="edit_vid_input",   # folder with images
            out_folder="edit_vid_output",    # where to save KB clips
            per_image=int(duration),            # seconds per image
            output_size=video_size,
            zoom_start=1.0, zoom_end=1.05
        )
        print("✅ Processing request sunonimagetovideogenerator: Creating clips completed successfully")
        # copy files from edit_vid_output to edit_vid_input for next step
        import shutil
        for filename in os.listdir("edit_vid_output"):
            shutil.copy(os.path.join("edit_vid_output", filename), os.path.join("edit_vid_input", filename))

        print("*** Processing request sunonimagetovideogenerator: Assembling clips to make video song")
        from assemble_from_videos import assemble_videos
        assemble_videos(
            video_folder="edit_vid_input",                  # or "edit_vid_output" if you pre-made KB clips
            audio_folder="edit_vid_audio",
            output_path="edit_vid_output/composed_video.mp4",
            fps=30,
            shuffle=True,                                   # different order each run
            prefer_ffmpeg_concat=True                       # auto-uses concat if safe; else MoviePy
        )

        print("✅ Processing request sunonimagetovideogenerator: Assembling completed successfully")
        # place copy of audio file (mp3/wav) from edit_vid_audio to root folder as audio.wav

        audio_folder = "edit_vid_audio"
        import shutil
        from pydub import AudioSegment
        # get the first file found in that folder
        audio_file = os.listdir(audio_folder)[0]
        audio_path = os.path.join(audio_folder, audio_file)

        # output path in root folder
        output_path = "audio.wav"

        # convert mp3 → wav (if needed), else just copy
        if audio_file.lower().endswith(".mp3"):
            # convert using pydub (requires ffmpeg installed)
            sound = AudioSegment.from_mp3(audio_path)
            sound.export(output_path, format="wav")
        else:
            # already wav → overwrite if exists
            shutil.copy(audio_path, output_path)

        print(f"✅ Saved audio file as {output_path}")

        #place copy of composed_video.mp4 from edit_vid_output to root folder as composed_video.mp4. Replace if exists

        shutil.copy("edit_vid_output/composed_video.mp4", "composed_video.mp4")
        print("✅ Copied composed video to root folder as composed_video.mp4")

        # Also place copy of composed_video.mp4 from edit_vid_output to edit_vid_output/out_{size}.mp4. Replace if exists
        shutil.copy("edit_vid_output/composed_video.mp4", f"edit_vid_output/out_{size}.mp4")

        print("*** Processing request sunotovideogenerator...creating captions file ")
        language = request.form.get('language', 'english')
        music = request.form.get('music', 'no')

        if language != 'hindi':
            prepare_captions_file_for_notebooklm_audio(
                audio_path="audio.wav",
                language=language,
                is_song=music == 'yes'
            )
        # else:
        #     if size == 'landscape':
        #         create_portrait()
        #     # add_caption()
        return "✅ Videos Processed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500    

# ------------------------ MAIN ------------------------ #
@app.route('/addoverlays', methods=['POST'])
def add_overlays():
    try:
        print("Processing request...add overlays")
        add_petal_overlay = request.form.get('add_petals', 'no') == 'yes'
        add_sparkle_overlay = request.form.get('add_sparkles', 'no') == 'yes'
        overlay_position = (0, 0)  # Default position, can be modified as needed

        from add_overlays import add_gif_overlays_to_videos
        add_gif_overlays_to_videos(
            input_folder="edit_vid_input",
            output_folder="edit_vid_output",
            add_petal_overlay=add_petal_overlay,
            add_sparkle_overlay=add_sparkle_overlay,
            overlay_position=overlay_position
        )
        return "✅ Overlays added successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500  

@app.route('/multiplyvideo', methods=['POST'])
def multiply_video():
    try:
        print("Processing request...multiplyvideo")
        repeat_factor = request.form.get('repeat_factor', 1)
        if repeat_factor == '':
            repeat_factor = 1

        from multiply_video import multiply_videos
        multiply_videos(
            input_folder="edit_vid_input",
            output_folder="edit_vid_output",
            repeat_factor=int(repeat_factor)
        )
        return "✅ Video multiplied successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500  

@app.route('/makekbvideofromimages', methods=['POST'])
def make_kb_video():
    try:
        print("Processing request...makekbvideo")

        duration = request.form.get('duration',10)
        if duration == '':
            duration = 10

        video_size = (1920,1080)
        size = request.form.get('size', 'landscape')
        if size == 'portrait':
            video_size = (1080,1920)

        from make_kb_videos import export_kb_videos
        export_kb_videos(
            input_folder="edit_vid_input",   # folder with images
            out_folder="edit_vid_output",    # where to save KB clips
            per_image=int(duration),            # seconds per image
            output_size=video_size,
            zoom_start=1.0, zoom_end=1.05
        )
        return "✅ Ken Burns videos created successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.route('/assembleclipstomakevideosong', methods=['POST'])
def assemble_clips_to_make_video_song():    
    try:
        print("Processing request...asseleclipstomakevideosong")
        from assemble_from_videos import assemble_videos
        assemble_videos(
            video_folder="edit_vid_input",                  # or "edit_vid_output" if you pre-made KB clips
            audio_folder="edit_vid_audio",
            output_path="edit_vid_output/final_video.mp4",
            fps=30,
            shuffle=True,                                   # different order each run
            prefer_ffmpeg_concat=True                       # auto-uses concat if safe; else MoviePy
        )

        shutil.copy("edit_vid_output/final_video.mp4", "composed_video.mp4")
        return "✅ Video song assembled successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500


@app.route('/splitvideotoparts', methods=['POST'])
def splitvideotoparts():    
    try:
        print("Processing request...splitvideotoparts")
        from assemble_from_videos import split_video

        max_duration = request.form.get('duration', '178')  # Default to 178 seconds if not provided

        split_video(
            input_path="edit_vid_output/output.mp4",
            max_duration=max_duration 
        )

        return "✅ splitvideotoparts completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.route('/save_word_timestamps_file', methods=['POST'])
def save_word_timestamps_file():
  data = request.get_json(force=True)  # list of {word,start,end,position,matched}
  os.makedirs('temp', exist_ok=True)
  path = os.path.join('temp', 'word_timestamps.json')
  with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
  return jsonify({"ok": True, "path": "/temp/word_timestamps.json"})    

@app.route('/save_ass', methods=['POST'])
def save_ass():
    """
    Save a .ass subtitle file to the parent folder of this server.py.
    Body: {"filename": "captions_landscape.ass", "content": "...ass text..."}
    """
    try:
        data = request.get_json(force=True, silent=False)
        if not data:
            return jsonify({"ok": False, "error": "Empty payload"}), 400

        filename = str(data.get("filename", "")).strip()
        content  = str(data.get("content", ""))

        # sanitize filename (letters, numbers, ., _, -) and require .ass
        filename = re.sub(r'[^A-Za-z0-9._-]', '_', filename)
        if not filename or not filename.endswith(".ass"):
            return jsonify({"ok": False, "error": "Bad filename"}), 400

        # parent directory of this file's directory
        parent_dir    = os.path.dirname(os.path.abspath(__file__))

        # Go to sub-folder with name edit_vid_output

        # Path to the subfolder 'edit_vid_output'
        output_dir = os.path.join(parent_dir, "edit_vid_output")

        #parent_dir = os.path.abspath(os.path.join(app_dir, os.pardir))

        if not os.path.isdir(output_dir) or not os.access(output_dir, os.W_OK):
            return jsonify({"ok": False, "error": "Parent folder not writable"}), 500

        target_path = os.path.join(output_dir, filename)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        return jsonify({"ok": True, "path": target_path})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/render_captions', methods=['POST'])
def render_captions():

    from wordtimestamps_to_ass_captions import build_ass_from_word_json, _ffmpeg_burn_subs

    """
    Body JSON:
    {
      "input_video": "/absolute/or/relative/path.mp4",
      "orientation": "landscape"|"portrait",
      "style": "cinematic"|"pro_pop"|"drift_up"|"typewriter"|"fade"|"softzoom"|"wordpop"|"glowpulse",
      "min_gap_sec": 0.40,
      "words_per_caption": 5,
      "output": "/path/output_with_captions.mp4" (optional)
    }
    """
    try:
        data = request.get_json(force=True)
        #input_video = data.get('input_video')
        orientation = data.get('orientation', 'landscape')
        style = data.get('style', 'cinematic')
        min_gap = float(data.get('min_gap_sec', 0.40))
        wpc = int(data.get('words_per_caption', 5))
        #output = data.get('output')

        if orientation == 'landscape':
            create_portrait()

        # if not input_video or not os.path.isfile(input_video):
        #     return jsonify({"ok": False, "error": "input_video not found"}), 400

        # Where is your word_timestamps.json?  Adjust if needed.
        # (Uses the same JSON you already serve to the front end.)
        app_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(app_dir, 'temp')
        word_json_path = os.path.join(temp_dir, 'word_timestamps.json')
        if not os.path.isfile(word_json_path):
            # fallback: try parent folder
            word_json_path = os.path.abspath(os.path.join(app_dir, os.pardir, 'word_timestamps.json'))
        if not os.path.isfile(word_json_path):
            return jsonify({"ok": False, "error": "word_timestamps.json not found"}), 400

        # Build ASS (both orientations saved; use requested orientation for render)
        parent_dir = os.path.abspath(os.path.join(app_dir, os.pardir))
        out_dir = os.path.join(app_dir, 'edit_vid_output')
        os.makedirs(out_dir, exist_ok=True)

        ass_land = build_ass_from_word_json(word_json_path, 'landscape', style, min_gap, wpc)
        ass_port = build_ass_from_word_json(word_json_path, 'portrait',  style, min_gap, wpc)

        path_land = os.path.join(out_dir, 'captions_landscape.ass')
        path_port = os.path.join(out_dir, 'captions_portrait.ass')
        with open(path_land, 'w', encoding='utf-8') as f: f.write(ass_land)
        with open(path_port, 'w', encoding='utf-8') as f: f.write(ass_port)

        # Choose the ASS we render with
        #ass_path = path_port if orientation == 'portrait' else path_land

        # Output path
        # if not output:
        #     base = os.path.splitext(os.path.basename(input_video))[0]
        #     output = os.path.join(parent_dir, f"{base}_with_captions.mp4")

        # Burn it in
        proc = _ffmpeg_burn_subs("edit_vid_output/out_landscape.mp4", path_land, "edit_vid_output/landscape_with_captions.mp4")
        if proc.returncode != 0:
            return jsonify({"ok": False, "error": "ffmpeg failed", "stderr": proc.stderr}), 500

        proc = _ffmpeg_burn_subs("edit_vid_output/out_portrait.mp4", path_port, "edit_vid_output/portrait_with_captions.mp4")
        if proc.returncode != 0:
            return jsonify({"ok": False, "error": "ffmpeg failed", "stderr": proc.stderr}), 500


        return jsonify({
            "ok": True,
            "ass_landscape": path_land,
            "ass_portrait": path_port
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
def bool_from_form(val: str) -> bool:
    """
    Accepts 'true'/'false', 'on'/'off', '1'/'0', or truthy string.
    """
    if val is None:
        return False
    v = str(val).strip().lower()
    return v in ("true", "on", "1", "yes", "y")

@app.post("/upload")
def uploadVid():
    from pathlib import Path
    from datetime import datetime
    from flask import Flask, render_template, request, jsonify
    from playwright.sync_api import sync_playwright
    import youtube_uploader as yu
    try:
        # Collect inputs from form
        video_path            = (request.form.get("video_path") or "").strip()
        youtube_channel_name  = (request.form.get("youtube_channel_name") or "").strip()
        youtube_playlist_name = (request.form.get("youtube_playlist_name") or "").strip()
        youtube_title         = (request.form.get("youtube_title") or "").strip()
        youtube_description   = (request.form.get("youtube_description") or "").strip()
        youtube_tags          = (request.form.get("youtube_tags") or "").strip()
        made_for_kids         = bool_from_form(request.form.get("made_for_kids"))
        schedule_date_raw     = (request.form.get("schedule_date") or "").strip()

        # Build the dict in the exact shape your upload_video expects
        video_info = {
            "video_path": video_path,                         # uploader will append .mp4 and prepend processed_videos
            "youtube_channel_name": youtube_channel_name,
            "youtube_playlist_name": youtube_playlist_name,
            "youtube_title": youtube_title,
            "youtube_description": youtube_description,
            "youtube_tags": youtube_tags,
            "made_for_kids": made_for_kids,
            "schedule_date": schedule_date_raw or None,       # keep raw; your code formats it for YouTube
            # optional: "thumbnail_path": "path/to/thumbnail.png",
        }

        # Basic validation
        missing = [k for k in ("video_path","youtube_channel_name","youtube_title") if not video_info[k]]
        if missing:
            return jsonify({"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400

        # Launch persistent Chrome with your existing settings
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                yu.PROFILE_DIR,
                headless=False,
                executable_path=yu.CHROME_EXECUTABLE,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            )
            page = browser.new_page()
            page.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined})""")

            # Do the upload (reuses your function)
            video_url = yu.upload_video(page, video_info)

            browser.close()

        return jsonify({"ok": True, "video_url": video_url})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    
if __name__ == '__main__':
    # app.run(debug=True, port=5000)
    app.run(debug=True, host='0.0.0.0', port=5000)  # Use host='
