from flask import Flask, request, jsonify, render_template, send_from_directory
import json
from flask_cors import CORS
import os
import traceback  # to print detailed error info
from caption_generator import prepare_captions_file_for_notebooklm_audio
from scraper import scrape_and_process  # Ensure this exists
from settings import background_music_options, font_settings, tts_engine, voices, sizes
from video_editor import batch_process
from youtube_uploader import upload_videos

app = Flask(__name__, template_folder='templates')
CORS(app)

# ------------------------ API ROUTES ------------------------ #

@app.route('/get_full_text', methods=['GET'])
def get_full_text():
    try:
        with open("temp/full_text.txt", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_word_timestamps', methods=['GET'])
def get_word_timestamps():
    try:
        with open("temp/word_timestamps.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save_word_timestamps', methods=['POST'])
def save_word_timestamps():
    try:
        data = request.json
        with open("temp/word_timestamps.json", "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return jsonify({"message": "✅ Word timestamps updated successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_structured_output', methods=['GET'])
def get_structured_output():
    try:
        with open("temp/structured_output.json", "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
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

@app.route('/aivideoprompt')
def aivideoprompt():
    return render_template('aivideoprompt.html')

@app.route('/prepare_captions')
def prep_caption():
    return render_template('index_captions.html')

@app.route('/video/<filename>')
def serve_video(filename):
    return send_from_directory(directory='.', path=filename)

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
        return f"❌ Error: {str(e)}", 500

@app.route('/caption', methods=['POST'])
def caption():
    try:
        print("Processing request...caption")
        language = request.form.get('language', 'english')
        prepare_captions_file_for_notebooklm_audio(
            audio_path="audio.wav",
            language=language
        )

        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        return f"❌ Error: {str(e)}", 500
    
@app.route('/upload', methods=['POST'])
def upload():
    try:
        print("Processing request...upload_videos")
        upload_videos()  # Assuming this function is defined in youtube_uploader.py

        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        return f"❌ Error: {str(e)}", 500
    
@app.route('/runobsrecorder', methods=['POST'])
def run_obs_recorder():
    try:
        print("Processing request...run OBS recorder")
        orientation = request.form.get('orientation', 'landscape')
        duration = request.form.get('duration', '10')  # Default to 10 seconds if not provided
        selectedStyle = request.form.get('captionStyle', 'style1')
        captionLength = request.form.get('captionLength', '5')
        bgMusicSelected = request.form.get('bgMusicSelect', 'None')
        minLineGapSec = request.form.get('minLineGapSec', '0.40')
        disableSubscribe = request.form.get('disableSubscribe', 'yes')
        outputfile = request.form.get('outputfile', 'test.mp4')

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
        print("✅ Copied composed video to root folder as composed_video.mp4")


        print("*** Processing request sunotovideogenerator...creating captions file ")
        language = request.form.get('language', 'english')
        prepare_captions_file_for_notebooklm_audio(
            audio_path="audio.wav",
            language=language
        )
        return "✅ Videos Processed successfully!", 200
    except Exception as e:
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


        print("*** Processing request sunotovideogenerator...creating captions file ")
        language = request.form.get('language', 'english')
        prepare_captions_file_for_notebooklm_audio(
            audio_path="audio.wav",
            language=language
        )
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
        return "✅ Video song assembled successfully!", 200
    except Exception as e:
        return f"❌ Error: {str(e)}", 500
            
if __name__ == '__main__':
    # app.run(debug=True, port=5000)
    app.run(debug=True, host='0.0.0.0', port=5000)  # Use host='
