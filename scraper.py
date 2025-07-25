import json
import os
import subprocess
import shutil
from tempfile import NamedTemporaryFile
import traceback
import psutil
import requests
from bs4 import BeautifulSoup
import urllib.request
from add_avatar import create_avatar_video
from audio_video_processor import create_video, resize_and_crop_image
from caption_generator import add_captions, extract_audio, prepare_file_for_adding_captions_n_headings_thru_html
from effects import create_camera_movement_clip
from settings import sizes, background_music_options, font_settings
from tkinter import messagebox
import re
from pathlib import Path
from moviepy.editor import VideoFileClip, CompositeAudioClip, AudioFileClip, ImageClip, concatenate_audioclips, concatenate_videoclips
import time
import shutil
from get_audio import get_audio_file
from moviepy.editor import VideoFileClip
from call_to_action import add_gif_to_video
from pydub import AudioSegment
from pydub import AudioSegment
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
from moviepy.video.fx.resize import resize
from tempfile import NamedTemporaryFile
import pandas as pd
from bs4 import Tag, NavigableString
word_timestamps = []

# Fetch word timestamps from the Flask server
import requests


def clear_folders(notebooklm="no"):
    shutil.rmtree("audios", ignore_errors=True)
    shutil.rmtree("images", ignore_errors=True)
    shutil.rmtree("splits", ignore_errors=True)
    if notebooklm == "no":
        shutil.rmtree("temp", ignore_errors=True)
        os.makedirs("temp", exist_ok=True)
        structured_output_path = "temp/structured_output.json"
        # Find start & end word timings
        structured_output = []
        # Save structured output
        with open(structured_output_path, "w", encoding="utf-8") as file:
            json.dump(structured_output, file, indent=4)

    os.makedirs("audios", exist_ok=True)
    os.makedirs("images", exist_ok=True)
    os.makedirs("splits", exist_ok=True)


# scraper.py

def clean_text(text):
    # Remove dots, hyphens, and other special characters
    cleaned_text = re.sub(r"\.+", ",", text)
    return cleaned_text

def is_excel_file_locked(file_path):
    try:
        with open(file_path, 'a'):
            pass
        return False
    except PermissionError:
        return True

def is_server_running(script_name="server.py"):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and script_name in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

def scrape_and_process(urls, excel_var, selected_size, selected_music, max_words, fontsize, y_pos, caption_style, 
                       selected_voice, language, gender, tts_engine, skip_puppeteer, skip_captions, pitch_age_group, disable_subscribe, notebooklm="no"):

    print("scrape_and_process - Received scrape_and_process Arguments:", locals())

    if skip_puppeteer == "no":
        if not is_server_running("server.py"):
            messagebox.showerror("Server Not Running", "To record the video, please start the server first by running server.py.")
            return
    EXCEL_FILE = "video_records.xlsx"
    if is_excel_file_locked(EXCEL_FILE):
        print(f"Error: Please close '{EXCEL_FILE}' before running the application.")
        return  # Exit cleanly without trying uploads  
       
    if excel_var == "no":
        if not urls or selected_size not in sizes or selected_music not in background_music_options:
            raise ValueError("Invalid input parameters")

    clear_folders(notebooklm)

    target_size = sizes.get(selected_size)  # Ensure it gets a tuple like (1080, 1920)
    if not target_size:
        print(f"Error: Invalid video type {selected_size}. Cannot process the image.")
        return

    output_folder = "processed_videos"
    os.makedirs(output_folder, exist_ok=True)

    if excel_var == "no":
        for url in urls.split(";"):
            url = url.strip()
            if not url:
                continue

            try:

                results = scrape_page_with_camera_frame(url, "https://readernook.com", notebooklm)
                if not results:
                    print(f"No valid content found in {url}. Skipping.")
                else:
                    for name_suffix, section_elements ,metadata in results:
                        base_file_name = Path(url).name
                        #base_file_name = re.sub(r'[^a-zA-Z0-9_-]', '_', base_file_name)  # Replace special chars with underscore
                        

                        title = metadata.get("title", "")

                        if title:
                            base_file_name = title

                        base_file_name = re.sub(r'[<>:"/\\\\|?*]', '', base_file_name)  # Remove file-unsafe chars

                        if language == 'hindi':
                            base_file_name = re.sub(r"[^\u0900-\u097Fa-zA-Z0-9.,!?\'\"\s-]", '', base_file_name)
                        else:
                            base_file_name = re.sub(r"[^a-zA-Z0-9.,!?\'\"\s-]", '', base_file_name)

                        base_file_name += f"_{name_suffix}"

                        description = metadata.get("description", "")
                        tags = metadata.get("tags", "")
                        channel = metadata.get("channel", "")
                        playlist = metadata.get("playlist", "")
                        ctatext = metadata.get("ctatext", "")
                        avatar = metadata.get("avatar", "")
                        shorts_html = metadata.get("shorts_html", "")

                        start = time.time()
                        create_video_using_camera_frames(section_elements, "composed_video.mp4", language, gender, tts_engine, target_size,base_file_name,avatar,pitch_age_group, notebooklm, title)
                        print(f"[{time.strftime('%H:%M:%S')}] Step create_video_using_camera_frames completed in {time.time() - start:.2f} seconds")
                        start = time.time()

                        output_file = "composed_video.mp4"
                        #SM- DND - Working. Commented out for now as captions are going to be added thru HTML. REF: https://readernook.com/topics/scary-stories/chatgpt-commands-for-youtube-video
                        #add_captions(max_words, fontsize, y_pos, style, " ", font_settings, "composed_video.mp4")
                        #prepare_file_for_adding_captions_n_headings_thru_html(url,output_file,base_file_name, language,story_text="")

                        prepare_file_for_adding_captions_n_headings_thru_html(url,output_file,base_file_name,language,story_text="", description=description, tags=tags, playlist=playlist, channel=channel, title=title, schedule_date="",shorts_html=shorts_html,skip_captions=skip_captions, notebooklm=notebooklm)
                        print(f"[{time.strftime('%H:%M:%S')}] Step prepare_file_for_adding_captions_n_headings_thru_html completed in {time.time() - start:.2f} seconds")
                        start = time.time()

                        #try:
                            #video_clip = VideoFileClip("output_video.mp4")

                            #DND - Temporarily disabled - as Gif is being added thru Mango as part of effects addition
                            # final_video = add_gif_to_video(
                            #     video_clip, 5, icon_path="gif_files/subscribe.gif"
                            # )

                            #SM - DND - Temporarily disabled - as Gif is being added thru HTML
                            # video_clip.write_videofile(
                            #     "output_video_with_gif.mp4", codec="libx264", audio_codec="aac", fps=24
                            # )

                            # output_file = "output_video_with_gif.mp4"
                        #except Exception as e:
                            #print("Error adding gif. Proceeding without gif")
                            #output_file = "output_video.mp4"

                        video = VideoFileClip(output_file)
                        duration_seconds = video.duration
                        duration_buffer = 3.5  # Buffer time for video processing
                        if selected_size == "YouTube Shorts":               
                            
                            duration_minutes = video.duration / 60

                            if duration_minutes > 3:
                                print(f"Video duration {duration_minutes:.2f} minutes. Splitting required.")
                                split_files = split_video(output_file, video.duration, max_duration=130)  # 2m 10s
                                for idx, split_file in enumerate(split_files, start=1):
                                    split_output_name = f"{output_folder}/{base_file_name}-{idx}.mp4"
                                    #safe_copy(split_file, split_output_name)
                                    shutil.copyfile(split_file, output_file)
                                    duration_seconds = split_file.duration
                                    duration_seconds = duration_seconds + duration_buffer
                                    # cmd = [
                                    #     "node", "puppeteer-recorder.js",
                                    #     split_output_name, f"{duration_seconds:.2f}", "portrait", str(max_words), caption_style,
                                    #     selected_music, "0.05", "1"
                                    # ]

                                    cmd = [
                                        "node", "puppeteer-launcher.js",
                                        split_output_name, f"{duration_seconds:.2f}", "portrait", str(max_words), caption_style,
                                        selected_music, "0.05", "1", disable_subscribe
                                    ]
                                    print("▶️ Running Puppeteer with:", cmd)
                                    if skip_puppeteer == "no":
                                        subprocess.run(cmd)

                            else:
                                print(f"Video duration {duration_minutes:.2f} minutes. No splitting required.")
                                output_name = f"{output_folder}/{base_file_name}.mp4"
                                duration_seconds = duration_seconds + duration_buffer
                                # cmd = [
                                #     "node", "puppeteer-recorder.js",
                                #     output_name, f"{duration_seconds:.2f}", "portrait", str(max_words), caption_style,
                                #     selected_music, "0.05", "1"
                                # ]

                                cmd = [
                                    "node", "puppeteer-launcher.js",
                                    output_name, f"{duration_seconds:.2f}", "portrait", str(max_words), caption_style,
                                    selected_music, "0.05", "1", disable_subscribe
                                ]
                                print("▶️ Running Puppeteer with:", cmd)
                                if skip_puppeteer == "no":
                                    subprocess.run(cmd)
                                else:
                                    if skip_captions == "yes":
                                        safe_copy(output_file, output_name)
                                #SM-DND
                                #safe_copy(output_file, output_name)
                        else:
                            output_name = f"{output_folder}/{base_file_name}.mp4"
                            duration_seconds = duration_seconds + duration_buffer
                            #SM-DND
                            #safe_copy(output_file, output_name)
                            # cmd = [
                            #     "node", "puppeteer-recorder.js",
                            #     output_name, f"{duration_seconds:.2f}", "landscape", str(max_words), caption_style,
                            #     selected_music, "0.05", "1"
                            # ]

                            cmd = [
                                "node", "puppeteer-launcher.js",
                                output_name, f"{duration_seconds:.2f}", "landscape", str(max_words), caption_style,
                                selected_music, "0.05", "1", disable_subscribe
                            ]
                            print("▶️ Running Puppeteer with:", cmd)
                            if skip_puppeteer == "no":
                                subprocess.run(cmd)
                            else:
                                if skip_captions == "yes":
                                    safe_copy(output_file, output_name)
                        print(f"Processing complete for {url}")

            except Exception as e:
                print(f"Error processing {url}: {e.with_traceback}. Proceeding to next")
                traceback.print_exc()

    if excel_var == "yes":
       input_excel_file = "video_story_input.xlsx"
       if is_excel_file_locked(input_excel_file):
           print(f"Error: Please close '{input_excel_file}' before running the application.")
           return  # Exit cleanly without trying uploads  
    
       df = pd.read_excel(input_excel_file)

       # Clean column names
       df.columns = df.columns.str.strip()
       print("Columns in Excel file:")
       print(df.columns.tolist())

       for short_idx, row in df.iterrows():
            if str(row.get("status")).strip().lower() == "success":
                print(f"Skipping row #{short_idx} - already marked as success")
                continue

            print(f"\nProcessing excel row #{short_idx}")
            title = row.get("title")
            background_video_src = row.get("background_video_src")
            story = row.get("story")
            description = row.get("description") 
            tags = row.get("tags")
            playlist = row.get("playlist")
            channel = row.get("channel")
            schedule_date = row.get("schedule_date")

            try:
                base_file_name = title
                base_file_name = re.sub(r'[<>:"/\\\\|?*]', '', base_file_name)  # Remove file-unsafe chars
                base_file_name = re.sub(r'[^a-zA-Z0-9_-]', '_', base_file_name)  # Replace special chars with underscore

                elements = []
                elements.append({
                    "type": "text",
                    "text": story,
                    "audio": None,
                    "image": None,
                    "camera_frame": None
                })

                video_data = {
                    "type": "video",
                    "text": None,
                    "audio": None,
                    "video": background_video_src,
                    "vid_duration": "",
                    "avatar_flag": "n", # Assuming no avatar for now
                    "local_video_flag": "y"
                }
                elements.append(video_data)

                results = elements
                
                start = time.time() 
                create_video_using_camera_frames(results, "composed_video.mp4", language, gender, tts_engine, target_size,base_file_name,avatar="", pitch_age_group=pitch_age_group, notebooklm=notebooklm, title=title)
                print(f"[{time.strftime('%H:%M:%S')}] Step create_video_using_camera_frames completed in {time.time() - start:.2f} seconds")
                start = time.time()                
                output_file = "composed_video.mp4"
                url = title
                #SM- DND - Working. Commented out for now as captions are going to be added thru HTML. REF: https://readernook.com/topics/scary-stories/chatgpt-commands-for-youtube-video
                #add_captions(max_words, fontsize, y_pos, style, " ", font_settings, "composed_video.mp4")

                prepare_file_for_adding_captions_n_headings_thru_html(url,output_file,base_file_name,language,story_text=story, description=description, tags=tags, playlist=playlist, channel=channel, title=title, schedule_date=schedule_date,skip_captions=skip_captions, notebooklm=notebooklm)

                #try:
                    #video_clip = VideoFileClip("output_video.mp4")

                    #DND - Temporarily disabled - as Gif is being added thru Mango as part of effects addition
                    # final_video = add_gif_to_video(
                    #     video_clip, 5, icon_path="gif_files/subscribe.gif"
                    # )

                    #SM - DND - Temporarily disabled - as Gif is being added thru HTML
                    # video_clip.write_videofile(
                    #     "output_video_with_gif.mp4", codec="libx264", audio_codec="aac", fps=24
                    # )

                    # output_file = "output_video_with_gif.mp4"
                #except Exception as e:
                    #print("Error adding gif. Proceeding without gif")
                    #output_file = "output_video.mp4"

                video = VideoFileClip(output_file)
                duration_seconds = video.duration
                duration_buffer = 3.5  # Buffer time for video processing
                if selected_size == "YouTube Shorts":               
                    
                    duration_minutes = video.duration / 60

                    if duration_minutes > 3:
                        print(f"Video duration {duration_minutes:.2f} minutes. Splitting required.")
                        split_files = split_video(output_file, video.duration, max_duration=130)  # 2m 10s
                        for idx, split_file in enumerate(split_files, start=1):
                            split_output_name = f"{output_folder}/{base_file_name}-{idx}.mp4"
                            #safe_copy(split_file, split_output_name)
                            shutil.copyfile(split_file, output_file)
                            duration_seconds = split_file.duration
                            duration_seconds = duration_seconds + duration_buffer
                            # cmd = [
                            #     "node", "puppeteer-recorder.js",
                            #     split_output_name, f"{duration_seconds:.2f}", "portrait", str(max_words), caption_style,
                            #     selected_music, "0.05", "1"
                            # ]

                            cmd = [
                                "node", "puppeteer-launcher.js",
                                split_output_name, f"{duration_seconds:.2f}", "portrait", str(max_words), caption_style,
                                selected_music, "0.05", "1", disable_subscribe
                            ]
                            print("▶️ Running Puppeteer with:", cmd)
                            if skip_puppeteer == "no":
                                subprocess.run(cmd)

                    else:
                        print(f"Video duration {duration_minutes:.2f} minutes. No splitting required.")
                        output_name = f"{output_folder}/{base_file_name}.mp4"
                        duration_seconds = duration_seconds + duration_buffer
                        #SM-DND - Working
                        # cmd = [
                        #     "node", "puppeteer-recorder.js",
                        #     output_name, f"{duration_seconds:.2f}", "portrait", str(max_words), caption_style,
                        #     selected_music, "0.05", "1"
                        # ]

                        cmd = [
                            "node", "puppeteer-launcher.js",
                            output_name, f"{duration_seconds:.2f}", "portrait", str(max_words), caption_style,
                            selected_music, "0.05", "1", disable_subscribe
                        ]
                        print("▶️ Running Puppeteer with:", cmd)
                        if skip_puppeteer == "no":
                            subprocess.run(cmd)
                        else:
                            if skip_captions == "yes":
                                safe_copy(output_file, output_name)
                        #SM-DND
                        #safe_copy(output_file, output_name)
                else:
                    output_name = f"{output_folder}/{base_file_name}.mp4"
                    duration_seconds = duration_seconds + duration_buffer
                    orientation = "landscape"
                    bg_music_volume = "0.05"
                    effect_volume = "1"
                    #SM-DND
                    #safe_copy(output_file, output_name)

                    #DND - Working
                    # cmd = [
                    #     "node", "puppeteer-recorder.js",
                    #     output_name, f"{duration_seconds:.2f}", orientation, str(max_words), caption_style,
                    #     selected_music, bg_music_volume, effect_volume
                    # ]
                    # 🟩 Step 1: Call Puppeteer to load the video page and prepare playback
                    puppeteer_cmd = [
                        "node", "puppeteer-launcher.js",
                        output_name, f"{duration_seconds:.2f}", orientation, str(max_words), caption_style,
                        selected_music, bg_music_volume, effect_volume, disable_subscribe
                    ]                    
                    print("▶️ Running Puppeteer with:", cmd)
                    if skip_puppeteer == "no":
                        #DND - Working
                        # subprocess.run(cmd)
                        print("▶️ Launching Puppeteer to set up the video with:", puppeteer_cmd)
                        subprocess.run(puppeteer_cmd)
                        # 🕒 Optional: Add small delay to ensure page is fully ready
                        subprocess.run(["timeout", "/t", "5"], shell=True)  # On Windows
                        # subprocess.run(["sleep", "5"])  # On macOS/Linux

                        # 🟩 Step 2: Call OBS to start recording
                        scene_name = "LandscapeScene" if orientation == "landscape" else "PortraitScene"

                        obs_cmd = ["node", "obs-recorder.js", scene_name, str(int(duration_seconds))]

                        print("🎬 Starting OBS recording with:", obs_cmd)
                        subprocess.run(obs_cmd)
                    else:
                        if skip_captions == "yes":
                            safe_copy(output_file, output_name)

                print(f"Processing complete for {url}")
                df.at[short_idx, "status"] = "success"
            except Exception as e:
                print(f"Error processing {url}: {e.with_traceback}. Proceeding to next")
                traceback.print_exc()

            df.to_excel(input_excel_file, index=False)


def create_video_using_camera_frames(elements, output_path, language="english", gender="Female", tts_engine="google", target_resolution = (1920, 1080),base_file_name="output_video", avatar="", pitch_age_group="adult", notebooklm="no", title="title_to_match_audio"):
    """
    Creates a video using the scrapped elements.

    Args:
        elements (list[dict]): Scrapped elements containing text, audio, and image data.
        output_path (str): Path to save the final video.
    """

    print("Received create_video_using_camera_frames Arguments:", locals())

    video_clips = []
    audio_clips = []
    READY_AUDIO_DIR = "ready_audio"
    #last_image_clip = None
    #target_resolution = (1920, 1080)  # Define the desired full frame resolution

    for idx, element in enumerate(elements):  # Using enumerate to get the index

        #DND - For debugging
        #if idx > 7:
             #break  # Break the loop after processing 5 elements

        element_id = element.get("id", f"element_{idx}")  # Use "id" if available, fallback to generated ID
        
        #DND - For debugging
        print(f"Processing element {idx}: {element}")
        #print(f"Processing element: {idx}")

        if element["type"] == "text":
            try:
                if notebooklm == "no":

                    base_audio_name = title
                    mp3_path = os.path.join(READY_AUDIO_DIR, f"{base_audio_name}.mp3")
                    wav_path = os.path.join(READY_AUDIO_DIR, f"{base_audio_name}.wav")

                    if os.path.exists(wav_path):
                        # Use wav directly
                        print(f"Using pre-existing WAV audio: {wav_path}")
                        tts_audio = AudioFileClip(wav_path)
                        audio_clips.append(tts_audio)

                    elif os.path.exists(mp3_path):
                        # Convert MP3 to WAV and use it
                        print(f"Converting MP3 to WAV: {mp3_path}")
                        sound = AudioSegment.from_mp3(mp3_path)
                        converted_wav = NamedTemporaryFile(delete=False, suffix=".wav").name
                        sound.export(converted_wav, format="wav")
                        tts_audio = AudioFileClip(converted_wav)
                        audio_clips.append(tts_audio)
                    else:

                        tts_audio_path = NamedTemporaryFile(delete=False, suffix=".mp3").name
                        

                        if tts_engine == "google":
                            if (language == "english-india"):
                                languageType = "neural"
                            else:
                                languageType = "journey"

                            generated_audio = get_audio_file(element["text"], tts_audio_path,"google",language,gender, languageType, pitch_age_group)
                        elif tts_engine == "amazon":
                            generated_audio = get_audio_file(element["text"], tts_audio_path,"amazon",language,gender, "generative")
                        
                        if generated_audio:
                            tts_audio = AudioFileClip(tts_audio_path)
                            audio_clips.append(tts_audio)

            except Exception as e:
                print(f"Error processing text: {e}")

        elif element["type"] == "audio":
            try:
                # Add sound effect
                local_audio_path = download_file(element["audio"]["src"])
                sound_effect = AudioSegment.from_file(local_audio_path)

                # Trim or extend the sound effect to match duration
                duration_ms = int(float(element["audio"]["duration"]) * 1000)
                if len(sound_effect) > duration_ms:
                    sound_effect = sound_effect[:duration_ms]
                else:
                    sound_effect = sound_effect * (duration_ms // len(sound_effect) + 1)
                    sound_effect = sound_effect[:duration_ms]

                # Adjust volume
                volume_adjustment = int(element["audio"]["volume"]) - 100

                # Clamp excessive decreases
                if volume_adjustment < -45:
                    volume_adjustment = -45

                # Clamp excessive increases
                if volume_adjustment > 100:
                    volume_adjustment = 100

                # Apply adjustment with threshold check
                if sound_effect.dBFS + volume_adjustment < -50:
                    volume_adjustment = -50 - sound_effect.dBFS

                sound_effect = sound_effect + volume_adjustment

                #DND- Normalize (optional)
                #target_dBFS = -20.0
                #sound_effect = sound_effect.apply_gain(target_dBFS - sound_effect.dBFS)

                # Save to temp file and load as AudioFileClip
                effect_audio_path = NamedTemporaryFile(delete=False, suffix=".mp3").name
                sound_effect.export(effect_audio_path, format="mp3")
                effect_audio_clip = AudioFileClip(effect_audio_path)
                audio_clips.append(effect_audio_clip)

                # Clean up the downloaded file
                os.remove(local_audio_path)
            except Exception as e:
                print(f"Error processing audio: {e}")

        # Video processing
        elif element["type"] == "video":
            try:
                # Define a small buffer in seconds (e.g., 0.1 seconds)
                BUFFER_DURATION = 0.0
                avatar_flag = element["avatar_flag"]
                local_video_flag = element.get("local_video_flag", "n")  # Default is 'n'

                if local_video_flag == 'y':
                    video_path = element["video"]  # Treat it as local file path
                else:
                    video_path = download_file(element["video"])

                video_clip = VideoFileClip(video_path).without_audio()

                # Resize the video clip to the target resolution
                video_clip = resize(video_clip, newsize=target_resolution)
                vid_duration = element["vid_duration"]
                loop_video = element.get("loop_video", "n")  # Default is 'n'
                
                # Calculate total audio duration
                combined_audio_duration = sum([clip.duration for clip in audio_clips]) if audio_clips else 0
                print(f"combined_audio_duration: {combined_audio_duration}")
                print(f"video_clip.duration: {video_clip.duration}")

                if vid_duration:  # Ensure it's not empty or None
                    try:
                        vid_duration = float(vid_duration)  # Convert to float
                        if vid_duration > combined_audio_duration:
                            combined_audio_duration = vid_duration
                            print(f"video duration switched from {combined_audio_duration} to {vid_duration} seconds")
                    except ValueError:
                        print(f"Warning: Unable to convert vid_duration ('{vid_duration}') to float. Skipping.")

                # Repeat video if it's shorter than the combined audio duration
                if local_video_flag == 'y' or loop_video == 'y':
                    if video_clip.duration < combined_audio_duration:
                        num_loops = int(combined_audio_duration // video_clip.duration) + 1
                        repeated_clips = [video_clip] * num_loops
                        video_clip = concatenate_videoclips(repeated_clips).subclip(0, combined_audio_duration + BUFFER_DURATION)
                
                # Clip video if it's longer than the combined audio duration
                if video_clip.duration > combined_audio_duration:
                    video_clip = video_clip.subclip(0, combined_audio_duration + BUFFER_DURATION)

                # Combine audio
                audio_clips_loaded = [clip if isinstance(clip, AudioFileClip) else AudioFileClip(clip) for clip in audio_clips]
                combined_audio = concatenate_audioclips(audio_clips_loaded)

                # if combined_audio.duration > video_clip.duration:
                #     combined_audio = combined_audio.subclip(0, video_clip.duration)

                # Handle remaining duration
                #0.5 buffer is added to avoid blank video file creation
                if combined_audio.duration > video_clip.duration :
                    remaining_audio = combined_audio.subclip(video_clip.duration)

                    if isinstance(remaining_audio, CompositeAudioClip):
                        audio_clips = [remaining_audio] # Keep CompositeAudioClip as it is
                    elif isinstance(remaining_audio, AudioFileClip): # If it is AudioFileClip
                        audio_clips = [remaining_audio] # Keep AudioFileClip as it is
                    else: # Handle the case where the remaining audio is None or something else
                        audio_clips = [] # Clear audio_clips or handle as appropriate                    
                    print(f"remaining_audio.duration: {remaining_audio.duration}")
                else:
                    audio_clips = []  # Clear audio_clips if no remaining audio

                # Add combined audio to video
                #video_with_audio = video_clip.set_audio(combined_audio)
                video_with_audio = video_clip.set_audio(combined_audio.subclip(0, video_clip.duration))

                if avatar_flag == 'y' or avatar != "":
                    temp_audio_path = "temp/audio.wav"
                    temp_output_path = "temp/video_b4_adding_avatar.mp4"
                    video_with_audio.write_videofile(temp_output_path, fps=24)
                    extract_audio(temp_output_path, temp_audio_path)
                    if avatar == "":
                        avatar = gender
                    video_with_audio  = create_avatar_video(temp_output_path, avatar)

                video_clips.append(video_with_audio)
                #DND-Working but can alter the clip so that the final video may not have the camera movement
                #video_with_audio.write_videofile(f"temp/video_with_audio_{element_id}.mp4", fps=24)

                # Reset audio clips
                #audio_clips = []
            except Exception as e:
                print(f"Error processing video: {e}")
                traceback.print_exc()

        elif element["type"] == "image":

            img_clip = ImageClip(element["image"])
            #DND - For Debugging purposes
            #print(f"Loaded image clip: {img_clip}")
            
            # Attempt to get the image size
            try:
                if notebooklm == "no":
                    if not audio_clips:
                        print("No audio clips available. Skipping image processing.")
                        continue  # Skip to the next element
                actual_width, actual_height = img_clip.size
                #DND - For Debugging purposes
                #print(f"Image dimensions: width={actual_width}, height={actual_height}")
                #print(f"Image source: {element['image']}")
                #print(f"ImageClip: {img_clip}")
            except Exception as e:
                print(f"Error getting image dimensions: {e}. Falling back to landscape.")
                actual_width, actual_height = 1920, 1080  # Fallback to default

            styled_width = 400  # Example styled width from the webpage
            scale_x = actual_width / styled_width

            duration = sum([clip.duration for clip in audio_clips]) if audio_clips else 3

            if element["camera_movement"]:

                start_frame = {
                    k: int(float(v[:-2]) * scale_x) if isinstance(v, str) and v.endswith("px") else int(float(v) * scale_x)
                    for k, v in element["camera_movement"]["start_frame"].items()
                }
                end_frame = {
                    k: int(float(v[:-2]) * scale_x) if isinstance(v, str) and v.endswith("px") else int(float(v) * scale_x)
                    for k, v in element["camera_movement"]["end_frame"].items()
                }
            else:
                start_frame = {
                    k: int(float(v[:-2]) * scale_x) if isinstance(v, str) and v.endswith("px") else int(float(v) * scale_x)
                    for k, v in element["camera_frame"].items()
                }
                end_frame = start_frame

            # DND - Working Code
            #output_file_name = f"output_{element_id}.mp4"

            # create_camera_movement_video(
            #     element['image'], 
            #     start_frame, 
            #     end_frame, 
            #     output_path=output_file_name,
            #     duration = duration,
            #     fps=24
            # )

            # # Load the video file
            # video_clip = VideoFileClip(output_file_name)
            img_duration = element["img_duration"]
            img_animation = element["img_animation"]
            avatar_flag = element["avatar_flag"]
            
            if img_duration:  # Ensure it's not empty or None
                try:
                    img_duration = float(img_duration)  # Convert to float
                    if img_duration > duration:
                        duration = img_duration
                        print(f"Image duration switched from {duration} to {img_duration} seconds")
                except ValueError:
                    print(f"Warning: Unable to convert img_duration ('{img_duration}') to float. Skipping.")

            if img_animation is None:  # Only set a default if img_animation is None
                img_animation = 'Zoom In'

            video_clip = create_camera_movement_clip(
                element['image'], 
                start_frame, 
                end_frame, 
                duration = duration,
                fps=24,
                movement_percentage=70,
                img_animation = img_animation,
                target_resolution = target_resolution
            )

            # Resize the image-based video clip to the target resolution
            video_clip = resize(video_clip, newsize=target_resolution)

            # Ensure all elements in audio_clips are AudioFileClip objects
            # audio_clips_loaded = [
            #     clip if isinstance(clip, AudioFileClip) else AudioFileClip(clip)
            #     for clip in audio_clips
            # ]
            if notebooklm == "no":
                audio_clips_loaded = [
                    clip if isinstance(clip, (AudioFileClip, CompositeAudioClip)) else None # Handle other types gracefully
                    for clip in audio_clips
                ]

                audio_clips_loaded = [clip for clip in audio_clips_loaded if clip is not None] #Remove None from the list


                combined_audio = concatenate_audioclips(audio_clips_loaded)

                if combined_audio.duration > video_clip.duration:
                    combined_audio = combined_audio.subclip(0, video_clip.duration)

                # Set the combined audio to the video
                video_with_audio = video_clip.set_audio(combined_audio)
            else:
                # If notebooklm is "yes", we assume audio_clips are already in the correct format
                video_with_audio = video_clip
            
            if avatar_flag == 'y' or avatar != "":
                temp_audio_path = "temp/audio.wav"
                temp_output_path = "temp/video_b4_adding_avatar.mp4"
                video_with_audio.write_videofile(temp_output_path, fps=24)
                extract_audio(temp_output_path, temp_audio_path)
                if avatar == "":
                    avatar = gender
                video_with_audio  = create_avatar_video(temp_output_path, avatar)
            
            video_clips.append(video_with_audio)

            #DND - For debugging purposes    
            #DND-Working but can alter the clip so that the final video may not have the camera movement
            #video_with_audio.write_videofile(f"temp/video_with_audio_{element_id}.mp4", fps=24)
            
            # Do not close the video_with_audio here
            # video_with_audio.close()


            # Reset audio clips for the next image
            audio_clips = []

    #final_video = concatenate_videoclips(video_clips, method="compose")
    final_video = concatenate_videoclips(video_clips, method="chain")

    if notebooklm == "yes":
        # set audi from audio.wav file
        audio_path = "audio.wav"
        if os.path.exists(audio_path):
            final_audio = AudioFileClip(audio_path)
            final_video = final_video.set_audio(final_audio)
        
    # # Check for audio in video_clips
    # audio_clips = [clip.audio for clip in video_clips if clip.audio is not None]

    # # Combine all valid audio tracks into a single audio track
    # if audio_clips:
    #     final_audio = CompositeAudioClip(audio_clips)
    #     # Set the final combined audio to the concatenated video
    #     final_video = final_video.set_audio(final_audio)
    # else:
    #     print("Warning: No audio found in video clips. Final video will be silent.")

    final_video.write_videofile(output_path, fps=24)

    # Cleanup resources
    for clip in video_clips:
        clip.close()

def download_file(url, temp_dir="temp_audio"):
    """
    Downloads a file from a URL and saves it locally.

    Args:
        url (str): The URL to download.
        temp_dir (str): The directory to save the file temporarily.

    Returns:
        str: The local file path of the downloaded file.
    """
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    local_filename = os.path.join(temp_dir, os.path.basename(url))
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    return local_filename



def scrape_page_with_camera_frame(url, base_url="https://readernook.com", notebooklm="no"):
    """
    Scrapes text, sound effects, and images along with camera movement properties.

    Args:
        url (str): The webpage URL.
        base_url (str): Base URL for resolving relative paths.

    Returns:
        list[dict]: A list of elements with text, audio, image, and camera frame details.
    """
   # Scrape the page


    resp = requests.get("http://localhost:5000/get_word_timestamps")

    if resp.status_code == 200:
        word_timestamps = resp.json()  # this is now a Python list of dicts
        print("Fetched word timestamps successfully.")
        # Now you can use it as needed
        # print(word_timestamps[0])  # print first word entry
    else:
        if notebooklm == "yes":
            print("Failed to fetch captions:", resp.status_code)
            exit(1)

    def is_skippable(element):
        """
        Check if the element should be skipped for text extraction.
        """
        # Skip <span> only if it has onclick="toggleParentDetails(this)"
        if element.name == "span" and element.get("onclick") == "toggleParentDetails(this)":
            return True
        
        # Skip <button> elements
        if element.name == "button":
            return True
        
        # Skip <div> with class "audio-details"
        if element.name == "div" and "audio-details" in element.get("class", []):
            return True

        # Skip <div> with class "audio-details"
        if element.name == "div" and "image-props" in element.get("class", []):
            return True

        if element.name == "div" and "video-props" in element.get("class", []):
            return True

        if element.name == "div" and "video-listitem-props" in element.get("class", []):
            return True

        if element.name == "div" and "video-hdr-props" in element.get("class", []):
            return True

        if element.name == "div" and "shorts-props" in element.get("class", []):
            return True
                                               
        return False
    
    def updateShortsHTMLImagesTimes(shortsObj, word_timestamps):       
        
        elements = []

        def is_inside_skippable_text(tag_or_string):
            """Skip only text or nested non-img tags inside skippable containers."""
            parent = tag_or_string.parent if isinstance(tag_or_string, NavigableString) else tag_or_string
            while parent and isinstance(parent, Tag):
                cls = parent.get("class", [])
                if any("shorts-props" in c or ("image" in c and "desc" in c) or "imgPropsInput" in c for c in cls):
                    return True
                parent = parent.parent
            return False
        word_position = 0
        text_start_position = 0

        for child in shortsObj.descendants:
            if isinstance(child, Tag):
                if child.name == "img":
                    # ✅ Always include image tags (even if inside .image1-desc)
                    elements.append({"type": "img", "tag": child, "text_start_position": text_start_position, "text_end_position": word_position -1})
                    text_start_position = word_position   # Update start position for next text segment
                    continue

                if is_inside_skippable_text(child):
                    continue  # ❌ skip container text

                if child.name in ["p", "span", "div"]:
                    text = child.get_text(strip=True, separator=" ")
                    words = text.split()
                    for word in words:
                        elements.append({"type": "word", "word": word, "position": word_position})
                        word_position += 1


            elif isinstance(child, NavigableString):
                if is_inside_skippable_text(child):
                    continue  # ❌ skip container text

                words = child.strip().split()
                for word in words:
                    elements.append({"type": "word", "word": word, "position": word_position})
                    word_position += 1

        # DND - For debugging purposes
        # print(elements)

        # Step 2: Compute durations between images and update imgduration inputs


        # Map position -> timestamp object for fast lookup
        position_map = {w['position']: w for w in word_timestamps}

        for i, el in enumerate(elements):
            if el["type"] == "img":
                start_pos = el.get("text_start_position")
                end_pos = el.get("text_end_position")

                start_ts = position_map.get(start_pos, {}).get("start")
                end_ts = position_map.get(end_pos, {}).get("end")

                if start_ts is not None and end_ts is not None and end_ts > start_ts:
                    duration = round(end_ts - start_ts, 2)
                else:
                    duration = 0.0

                # Set the data-imgduration on the imgPropsInput div (used for downstream processing)
                img_tag = el["tag"]
                parent_div = img_tag.find_parent("div", class_="image1-desc") or img_tag.find_parent("div", class_="image2-desc")

                if parent_div:
                    # Look for the imgPropsInput wrapper
                    image_props_div = parent_div.find("div", class_="image-props")
                    if image_props_div:
                        duration_updated = False
                        for div in image_props_div.find_all("div", class_="imgPropsInput"):
                            div_id = div.get("id", "")
                            if div_id.endswith("-imgduration"):
                                print(f"✅ Updating duration in: {div_id} from {div.string} → {duration:.2f}")
                                div.string = f"{duration:.2f}"
                                div["data-imgduration"] = f"{duration:.2f}"  # Optional, if needed in JS
                                duration_updated = True
                        if not duration_updated:
                            print("⚠️ No -imgduration field found inside image-props.")
                    else:
                        print("⚠️ No .image-props found in image1-desc container.")
                else:
                    print("⚠️ Image tag not inside .image1-desc or .image2-desc")


                # Also update on the image tag directly if needed
                # img_tag["data-imgduration"] = str(duration)

                # 🧾 Print debug info
                start_word = position_map.get(start_pos, {}).get("word", "?")
                end_word = position_map.get(end_pos, {}).get("word", "?")
                print(f"\n🖼️ Image at index {i}")
                print(f"   Start Word: '{start_word}' (Position: {start_pos}, Time: {start_ts})")
                print(f"   End Word:   '{end_word}' (Position: {end_pos}, Time: {end_ts})")
                print(f"   ⏳ Duration: {duration} seconds")

        return shortsObj
    
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    shorts_sections = soup.select("div.shorts")
    process_sections = []

    if shorts_sections:
        for idx, section in enumerate(shorts_sections, 1):
            name_suffix = f"shorts_{idx}"

            if notebooklm == "yes":
                shorts_html = updateShortsHTMLImagesTimes(section, word_timestamps)
                # print(shorts_html.prettify())
            else:
                shorts_html = str(section)

            # ✅ Extract metadata fields from input elements
            metadata = {
                "title": section.select_one("div.shorts-title").get_text(strip=True) if section.select_one("div.shorts-title") else "",
                "description": section.select_one("div.shorts-description").get_text(strip=True) if section.select_one("div.shorts-description") else "",
                "tags": section.select_one("div.shorts-tags").get_text(strip=True) if section.select_one("div.shorts-tags") else "",
                "channel": section.select_one("div.shorts-channel").get_text(strip=True) if section.select_one("div.shorts-channel") else "",
                "playlist": section.select_one("div.shorts-playlist").get_text(strip=True) if section.select_one("div.shorts-playlist") else "",
                "ctatext": section.select_one("div.shorts-ctatext").get_text(strip=True) if section.select_one("div.shorts-ctatext") else "",
                "avatar": section.select_one("div.shorts-avatar").get_text(strip=True) if section.select_one("div.shorts-avatar") else "",
                "shorts_html": shorts_html
            }

            process_sections.append((name_suffix, section, metadata))
    else:
        song_lyrics = soup.select_one(".songLyrics")
        if song_lyrics:
            process_sections.append(("main", song_lyrics, {}))
        else:
            return []  # No valid section found

    all_results = []


    

    

    for name_suffix, section, metadata  in process_sections:


        #DND - For debugginh
        #print(f"Processing element: {element}")

        current_text = ""
        elements = []
        previous_image_data = None
        last_image = None


        for element in section.descendants:
            # Skip irrelevant elements (script, styles, etc.)
            if element.name in ("script", "style", "p", "button"):
                continue

            # Skip skippable elements
            if is_skippable(element):
                continue         

            # Collect text from text nodes
            if element.name == "div" and "audio-desc" in element.get("class", []):

                if current_text.strip():
                    elements.append({
                        "type": "text",
                        "text": current_text,
                        "audio": None,
                        "image": None,
                        "camera_frame": None
                    })
                    current_text = ""  # Reset text after pairing
            
                audio_src = urljoin(url, element.find("audio")["src"])
                start_time = element.select_one("[id$='-start']").text.strip()
                duration = element.select_one("[id$='-duration']").text.strip()
                volume = element.select_one("[id$='-volume']").text.strip()
                overlap = element.select_one("[id$='-overlap']").text.strip()

                # Save collected data
                elements.append({
                    "type": "audio",
                    "text": None,
                    "audio": {
                        "src": audio_src,
                        "start_time": start_time,
                        "duration": duration,
                        "volume": volume,
                        "overlap": overlap
                    },
                    "image": None,
                    "camera_frame": None
                })

            # Text nodes
            elif isinstance(element, str) and element.strip():
                if not any(parent for parent in element.parents if is_skippable(parent)):
                    text = element.strip()
                    # if not text.endswith('.'):
                    #     text += '.'
                    
                    # try:
                    #     if isinstance(element, Tag) and "video-hdr-inline-cls" in element.get("class", []):
                    #         text += '.'
                    # except:
                    #     pass
                    current_text += " " + text


            elif element.name == "div" and "video1-desc" in element.get("class", []):
                video_tag = element.find("video", class_="movieVideoCls")
                video_src = urljoin(base_url, video_tag["src"]) if video_tag else None

                vid_duration = element.select_one("[id$='-vidduration']").text.strip()

                try:
                    add_avatar = element.select_one("[id$='-avatarflag']").text.strip()
                except:
                    add_avatar = 'n'

                try:
                    loop_video = element.select_one("[id$='-loopflag']").text.strip()
                except:
                    loop_video = 'n'

                video_data = {
                    "type": "video",
                    "text": None,
                    "audio": None,
                    "video": video_src,
                    "vid_duration": vid_duration,
                    "avatar_flag": add_avatar,
                    "loop_video": loop_video,
                }

                if current_text.strip() :
                    elements.append({
                        "type": "text",
                        "text": current_text,
                        "audio": None,
                        "image": None,
                        "camera_frame": None
                    })
                    current_text = ""  # Reset text after pairing

                elements.append(video_data)

            # Collect images from <img class="movieImageCls">
            elif element.name == "div" and "image1-desc" in element.get("class", []):
                img_tag = element.find("img", class_="movieImageCls")
                img_src = urljoin(base_url, img_tag["src"]) if img_tag else None

                img_duration = element.select_one("[id$='-imgduration']").text.strip()
                img_animation = element.select_one("[id$='-imganimation']").text.strip()
                try:
                    add_avatar = element.select_one("[id$='-avatarflag']").text.strip()
                except:
                    add_avatar = 'n'


                # Extract camera frame details
                camera_frame = element.find("div", class_="camera-frame")
                if camera_frame:
                    style = camera_frame.get("style", "")
                    # Use a more robust parsing mechanism to handle spaces and missing values
                    style_dict = {}
                    for item in style.split(";"):
                        if ": " in item:  # Ensure the item contains a key-value pair
                            key, value = item.split(": ", 1)
                            style_dict[key.strip()] = value.strip()

                    # Extract individual properties
                    width = style_dict.get('width')
                    height = style_dict.get('height')
                    left = style_dict.get('left', '0px')  # Default to '0px' if 'left' is not in style_dict
                    top = style_dict.get('top', '0px')    # Default to '0px' if 'top' is not in style_dict


                # Check for camera movement
                if previous_image_data and previous_image_data["image"] == img_src:
                    camera_movement = {
                        "start_frame": previous_image_data["camera_frame"],
                        "end_frame": {
                            "width": width,
                            "height": height,
                            "left": left,
                            "top": top
                        }
                    }
                else:
                    camera_movement = None

                image_data = {
                    "type": "image",
                    "text": None,
                    "audio": None,
                    "image": img_src,
                    "camera_frame": {
                        "width": width,
                        "height": height,
                        "left": left,
                        "top": top
                    },
                    "camera_movement": camera_movement,
                    "img_duration": img_duration,
                    "img_animation": img_animation,
                    "avatar_flag": add_avatar
                }
                last_image = {
                    "type": "image",
                    "text": None,
                    "audio": None,
                    "image": img_src,
                    "camera_frame": {
                        "width": width,
                        "height": height,
                        "left": left,
                        "top": top
                    },
                    "camera_movement": None,
                    "img_duration": img_duration,
                    "img_animation": img_animation,
                    "avatar_flag": add_avatar
                }


                # Save text-image pair if text and image exist
                if current_text.strip() :
                    elements.append({
                        "type": "text",
                        "text": current_text,
                        "audio": None,
                        "image": None,
                        "camera_frame": None
                    })
                    current_text = ""  # Reset text after pairing

                elements.append(image_data)
                previous_image_data = image_data

        # Handle remaining text if no image follows
        if current_text.strip():
            #text_image_pairs.append((current_text.strip(), last_image_url))
            elements.append({
                "type": "text",
                "text": current_text,
                "audio": None,
                "image": None,
                "camera_frame": None
            })
            elements.append(last_image)


        if elements:
            all_results.append((name_suffix, elements, metadata))

    return all_results  # List of (suffix, elements)

#DND - Working code before the change to support multiple shorts on a page
def scrape_page_with_camera_frame_DND(url, base_url="https://readernook.com"):
    """
    Scrapes text, sound effects, and images along with camera movement properties.

    Args:
        url (str): The webpage URL.
        base_url (str): Base URL for resolving relative paths.

    Returns:
        list[dict]: A list of elements with text, audio, image, and camera frame details.
    """
   # Scrape the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract text-image pairs
    #text_image_pairs = []
    current_text = ""
    #last_image_url = None
    elements = []
    previous_image_data = None
    last_image = None

    def is_skippable(element):
        """
        Check if the element should be skipped for text extraction.
        """
        # Skip <span> only if it has onclick="toggleParentDetails(this)"
        if element.name == "span" and element.get("onclick") == "toggleParentDetails(this)":
            return True
        
        # Skip <button> elements
        if element.name == "button":
            return True
        
        # Skip <div> with class "audio-details"
        if element.name == "div" and "audio-details" in element.get("class", []):
            return True

        # Skip <div> with class "audio-details"
        if element.name == "div" and "image-props" in element.get("class", []):
            return True

        if element.name == "div" and "video-props" in element.get("class", []):
            return True

        if element.name == "div" and "video-listitem-props" in element.get("class", []):
            return True

        if element.name == "div" and "video-hdr-props" in element.get("class", []):
            return True
                                        
        return False
    
    # Loop through all elements within "songLyrics" div
    for element in soup.select_one(".songLyrics").descendants:

        #DND - For debugginh
        #print(f"Processing element: {element}")

        # Skip irrelevant elements (script, styles, etc.)
        if element.name in ("script", "style", "p", "button"):
            continue

        # Skip skippable elements
        if is_skippable(element):
            continue

        # Collect text from text nodes
        if element.name == "div" and "audio-desc" in element.get("class", []):

            if current_text.strip():
                elements.append({
                    "type": "text",
                    "text": current_text,
                    "audio": None,
                    "image": None,
                    "camera_frame": None
                })
                current_text = ""  # Reset text after pairing
        
            audio_src = urljoin(url, element.find("audio")["src"])
            start_time = element.select_one("[id$='-start']").text.strip()
            duration = element.select_one("[id$='-duration']").text.strip()
            volume = element.select_one("[id$='-volume']").text.strip()
            overlap = element.select_one("[id$='-overlap']").text.strip()

            # Save collected data
            elements.append({
                "type": "audio",
                "text": None,
                "audio": {
                    "src": audio_src,
                    "start_time": start_time,
                    "duration": duration,
                    "volume": volume,
                    "overlap": overlap
                },
                "image": None,
                "camera_frame": None
            })

        # Text nodes
        elif isinstance(element, str) and element.strip():
            if not any(parent for parent in element.parents if is_skippable(parent)):
                text = element.strip()
                # if not text.endswith('.'):
                #     text += '.'
                
                # try:
                #     if isinstance(element, Tag) and "video-hdr-inline-cls" in element.get("class", []):
                #         text += '.'
                # except:
                #     pass
                current_text += " " + text


        elif element.name == "div" and "video1-desc" in element.get("class", []):
            video_tag = element.find("video", class_="movieVideoCls")
            video_src = urljoin(base_url, video_tag["src"]) if video_tag else None

            vid_duration = element.select_one("[id$='-vidduration']").text.strip()

            try:
                add_avatar = element.select_one("[id$='-avatarflag']").text.strip()
            except:
                add_avatar = 'n'

            try:
                loop_video = element.select_one("[id$='-loopflag']").text.strip()
            except:
                loop_video = 'n'

            video_data = {
                "type": "video",
                "text": None,
                "audio": None,
                "video": video_src,
                "vid_duration": vid_duration,
                "avatar_flag": add_avatar,
                "loop_video": loop_video,
            }

            if current_text.strip() :
                elements.append({
                    "type": "text",
                    "text": current_text,
                    "audio": None,
                    "image": None,
                    "camera_frame": None
                })
                current_text = ""  # Reset text after pairing

            elements.append(video_data)

        # Collect images from <img class="movieImageCls">
        elif element.name == "div" and "image1-desc" in element.get("class", []):
            img_tag = element.find("img", class_="movieImageCls")
            img_src = urljoin(base_url, img_tag["src"]) if img_tag else None

            img_duration = element.select_one("[id$='-imgduration']").text.strip()
            img_animation = element.select_one("[id$='-imganimation']").text.strip()
            try:
                add_avatar = element.select_one("[id$='-avatarflag']").text.strip()
            except:
                add_avatar = 'n'

            # Extract camera frame details
            camera_frame = element.find("div", class_="camera-frame")
            if camera_frame:
                style = camera_frame.get("style", "")
                # Use a more robust parsing mechanism to handle spaces and missing values
                style_dict = {}
                for item in style.split(";"):
                    if ": " in item:  # Ensure the item contains a key-value pair
                        key, value = item.split(": ", 1)
                        style_dict[key.strip()] = value.strip()

                # Extract individual properties
                width = style_dict.get('width')
                height = style_dict.get('height')
                left = style_dict.get('left', '0px')  # Default to '0px' if 'left' is not in style_dict
                top = style_dict.get('top', '0px')    # Default to '0px' if 'top' is not in style_dict


            # Check for camera movement
            if previous_image_data and previous_image_data["image"] == img_src:
                camera_movement = {
                    "start_frame": previous_image_data["camera_frame"],
                    "end_frame": {
                        "width": width,
                        "height": height,
                        "left": left,
                        "top": top
                    }
                }
            else:
                camera_movement = None

            image_data = {
                "type": "image",
                "text": None,
                "audio": None,
                "image": img_src,
                "camera_frame": {
                    "width": width,
                    "height": height,
                    "left": left,
                    "top": top
                },
                "camera_movement": camera_movement,
                "img_duration": img_duration,
                "img_animation": img_animation,
                "avatar_flag": add_avatar
            }
            last_image = {
                "type": "image",
                "text": None,
                "audio": None,
                "image": img_src,
                "camera_frame": {
                    "width": width,
                    "height": height,
                    "left": left,
                    "top": top
                },
                "camera_movement": None,
                "img_duration": img_duration,
                "img_animation": img_animation,
                "avatar_flag": add_avatar
            }


            # Save text-image pair if text and image exist
            if current_text.strip() :
                elements.append({
                    "type": "text",
                    "text": current_text,
                    "audio": None,
                    "image": None,
                    "camera_frame": None
                })
                current_text = ""  # Reset text after pairing

            elements.append(image_data)
            previous_image_data = image_data

    # Handle remaining text if no image follows
    if current_text.strip():
        #text_image_pairs.append((current_text.strip(), last_image_url))
        elements.append({
            "type": "text",
            "text": current_text,
            "audio": None,
            "image": None,
            "camera_frame": None
        })
        elements.append(last_image)

    return elements
def safe_copy(src, dst, retries=25, delay=2):
    """
    Safely copy a file from `src` to `dst`, retrying if the file is locked.
    If the file already exists, append a suffix (_1, _2, _3, etc.) to the destination filename.
    """
    base, ext = os.path.splitext(dst)  # Split destination into name and extension
    counter = 1

    # Check if the destination file exists, and modify the name with a suffix if necessary
    while os.path.exists(dst):
        dst = f"{base}_{counter}{ext}"
        counter += 1

    for attempt in range(retries):
        try:
            shutil.copy2(src, dst)
            print(f"Copied {src} to {dst}")
            return
        except PermissionError as e:
            print(f"PermissionError: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)

    raise PermissionError(f"Failed to copy {src} to {dst} after {retries} retries.")


def safe_copy_old(src, dst, retries=5, delay=2):
    """
    Safely copy a file from `src` to `dst`, retrying if the file is locked.
    """
    for attempt in range(retries):
        try:
            shutil.copy2(src, dst)
            print(f"Copied {src} to {dst}")
            return
        except PermissionError as e:
            print(f"PermissionError: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)

    raise PermissionError(f"Failed to copy {src} to {dst} after {retries} retries.")

#From Gemini - https://gemini.google.com/app/f86d38e806049040
def scrape_page(url):
    """
    Scrapes text and images from a given webpage URL.

    Args:
        url (str): The webpage URL.

    Returns:
        list of tuples: Each tuple contains extracted text and image URL pairs.
    """
    # Scrape the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract text-image pairs
    text_image_pairs = []
    current_text = ""
    last_image_url = None

    # Loop through all elements within "songLyrics" div
    for element in soup.select_one(".songLyrics").descendants:
        # Skip irrelevant elements (script, styles, etc.)
        if element.name in ("script", "style", "p"):
            continue

        # Collect text from text nodes
        if isinstance(element, str) and element.strip():
            current_text += " " + element.strip()

        # Collect images from <img class="movieImageCls">
        elif element.name == "img" and "movieImageCls" in element.get("class", []):
            last_image_url = element["src"]

            # Save text-image pair if text and image exist
            if current_text.strip() and last_image_url:
                text_image_pairs.append((current_text.strip(), last_image_url))
                current_text = ""  # Reset text after pairing

    # Handle remaining text if no image follows
    if current_text.strip():
        text_image_pairs.append((current_text.strip(), last_image_url))

    return text_image_pairs

def generate_audio_images(text_image_pairs, target_size, audio_dir="audios", image_dir="images", language="english", gender="Female", tts_engine="google"):
    """
    Generate audio files using TTS and download images.

    Args:
        pairs (list): List of (text, image_url) pairs.
        target_size (tuple): Target image size (width, height).
        audio_dir (str): Directory to save audio files.
        image_dir (str): Directory to save image files.

    Returns:
        tuple: List of generated audio file paths and image file paths.
    """
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(image_dir, exist_ok=True)
    audio_files = []
    image_files = []


    # Print pairs for verification
    for idx, (text, img_url) in enumerate(text_image_pairs):
        print(f"Pair {idx}: Text -> {text[:60]}... | Image -> {img_url}")
        # Your processing logic here

        # Generate audio using Amazon Polly
        audio_file = f"audios/audio{idx+1}.mp3"

        if tts_engine == "google":
            generated_audio = get_audio_file(text, audio_file,"google",language,gender, "journey")
        elif tts_engine == "amazon":
            generated_audio = get_audio_file(text, audio_file,"amazon",language,gender, "generative")
        
        if generated_audio:
            audio_files.append(generated_audio)

        # Download image if valid and not already processed
        if img_url:
            img_filename = f"images/image{idx+1}.jpg"
            full_img_url = f"https://readernook.com{img_url}"

            try:
                urllib.request.urlretrieve(full_img_url, img_filename)
                resize_and_crop_image(img_filename, target_size)
                image_files.append(img_filename)
            except Exception as e:
                print(f"Error downloading image {full_img_url}: {e}")

    # Ensure matching lengths before video creation
    if len(audio_files) != len(image_files):
        #messagebox.showerror("Error", "Mismatch between audio and image counts.")
        print("Mismatch between audio and image counts.")
        return
    return audio_files, image_files

def split_video(input_file, video_duration, max_duration=130):
    """
    Splits a video into multiple segments if its duration exceeds max_duration.

    Args:
        input_file (str): Path to the input video file.
        video_duration (int): Total video duration in seconds.
        max_duration (int): Maximum allowed duration in seconds.

    Returns:
        list: List of generated split video file paths.
    """
    try:
        # Prepare output directory for splits
        splits_dir = os.path.join(os.getcwd(), "splits")
        os.makedirs(splits_dir, exist_ok=True)

        # Prepare file naming
        file_basename = os.path.splitext(os.path.basename(input_file))[0]
        output_files = []

        # FFmpeg split command
        split_command = [
            "ffmpeg", "-i", input_file,
            "-c", "copy", "-map", "0",
            "-segment_time", str(max_duration),
            "-f", "segment", "-reset_timestamps", "1",
            os.path.join(splits_dir, f"{file_basename}-%02d.mp4")
        ]

        subprocess.run(split_command, check=True)

        # Collect generated files
        for idx in range(int(video_duration // max_duration) + 1):
            split_file = os.path.join(splits_dir, f"{file_basename}-{idx:02d}.mp4")
            if os.path.exists(split_file):
                output_files.append(split_file)

        print(f"Split videos generated: {output_files}")
        return output_files

    except subprocess.CalledProcessError as e:
        print(f"Error splitting video: {e}")
        return []
