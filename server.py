from flask import Flask, request, jsonify, render_template
import json
from flask_cors import CORS
import os

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

        cmd = [
            "node", "puppeteer-launcher.js",
            "test.mp4", duration, orientation, "4", "style2",
            "story-classical-3-710.mp3", "0.05", "1", "yes"
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
# ------------------------ MAIN ------------------------ #

if __name__ == '__main__':
    app.run(debug=True, port=5000)
