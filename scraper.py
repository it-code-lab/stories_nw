import os
import subprocess
import shutil
from tempfile import NamedTemporaryFile
import requests
from bs4 import BeautifulSoup
import urllib.request
from audio_video_processor import create_video, resize_and_crop_image
from caption_generator import add_captions
from effects import create_camera_movement_clip
from settings import sizes, background_music_options, font_settings
from tkinter import messagebox
import re
from pathlib import Path
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_audioclips, concatenate_videoclips
import time
import shutil
from get_audio import get_audio_file
from moviepy.editor import VideoFileClip
from call_to_action import add_gif_to_video
from pydub import AudioSegment
from urllib.parse import urljoin

def clear_folders():
    shutil.rmtree("audios", ignore_errors=True)
    shutil.rmtree("images", ignore_errors=True)
    shutil.rmtree("splits", ignore_errors=True)
    os.makedirs("audios", exist_ok=True)
    os.makedirs("images", exist_ok=True)
    os.makedirs("splits", exist_ok=True)

# scraper.py

def clean_text(text):
    # Remove dots, hyphens, and other special characters
    cleaned_text = re.sub(r"\.+", ",", text)
    return cleaned_text



def scrape_and_process(urls, selected_size, selected_music, max_words, fontsize, y_pos, style, 
                       selected_voice, language, gender, tts_engine):
    if not urls or selected_size not in sizes or selected_music not in background_music_options:
        raise ValueError("Invalid input parameters")

    clear_folders()

    target_size = sizes.get(selected_size)  # Ensure it gets a tuple like (1080, 1920)
    if not target_size:
        print(f"Error: Invalid video type {selected_size}. Cannot process the image.")
        return

    output_folder = "processed_videos"
    os.makedirs(output_folder, exist_ok=True)

    for url in urls.split(";"):
        url = url.strip()
        if not url:
            continue

        try:
            base_file_name = Path(url).name
            
            results = scrape_page_with_camera_frame(url)
            create_video_using_camera_frames(results, "composed_video.mp4", language, gender, tts_engine)


            add_captions(max_words, fontsize, y_pos, style, " ", font_settings, "composed_video.mp4")

            try:
                video_clip = VideoFileClip("output_video.mp4")

                final_video = add_gif_to_video(
                    video_clip, 5, icon_path="subscribe.gif"
                )

                final_video.write_videofile(
                    "output_video_with_gif.mp4", codec="libx264", audio_codec="aac", fps=24
                )

                output_file = "output_video_with_gif.mp4"
            except Exception as e:
                print("Error adding gif. Proceeding without gif")
                output_file = "output_video.mp4"

            if selected_size == "YouTube Shorts":
                video = VideoFileClip(output_file)
                duration_minutes = video.duration / 60

                if duration_minutes > 3:
                    print(f"Video duration {duration_minutes:.2f} minutes. Splitting required.")
                    split_files = split_video(output_file, video.duration, max_duration=130)  # 2m 10s
                    for idx, split_file in enumerate(split_files, start=1):
                        split_output_name = f"{output_folder}/{base_file_name}-{idx}.mp4"
                        safe_copy(split_file, split_output_name)
                else:
                    print(f"Video duration {duration_minutes:.2f} minutes. No splitting required.")
                    output_name = f"{output_folder}/{base_file_name}.mp4"
                    safe_copy(output_file, output_name)
            else:
                output_name = f"{output_folder}/{base_file_name}.mp4"
                safe_copy(output_file, output_name)

            print(f"Processing complete for {url}")

        except Exception as e:
            print(f"Error processing {url}: {e}. Proceeding to next")



def create_video_using_camera_frames(elements, output_path, language="english", gender="Female", tts_engine="google"):
    """
    Creates a video using the scrapped elements.

    Args:
        elements (list[dict]): Scrapped elements containing text, audio, and image data.
        output_path (str): Path to save the final video.
    """
    video_clips = []
    audio_clips = []
    #last_image_clip = None

    for idx, element in enumerate(elements):  # Using enumerate to get the index

        #DND - For debugging
        # if idx > 5:
        #     break  # Break the loop after processing 5 elements

        #element_id = element.get("id", f"element_{idx}")  # Use "id" if available, fallback to generated ID
        
        #DND - For debugging
        #print(f"Processing element: {element}")
        print(f"Processing element: {idx}")

        if element["type"] == "text":
            try:

                tts_audio_path = NamedTemporaryFile(delete=False, suffix=".mp3").name
                if tts_engine == "google":
                    generated_audio = get_audio_file(element["text"], tts_audio_path,"google",language,gender, "journey")
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

        elif element["type"] == "image":

            img_clip = ImageClip(element["image"])
            #DND - For Debugging purposes
            #print(f"Loaded image clip: {img_clip}")
            
            # Attempt to get the image size
            try:
                actual_width, actual_height = img_clip.size
                #DND - For Debugging purposes
                #print(f"Image dimensions: width={actual_width}, height={actual_height}")
                #print(f"Image source: {element['image']}")
                #print(f"ImageClip: {img_clip}")
            except Exception as e:
                print(f"Error getting image dimensions: {e}")
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

            video_clip = create_camera_movement_clip(
                element['image'], 
                start_frame, 
                end_frame, 
                duration = duration,
                fps=24
            )



            # Ensure all elements in audio_clips are AudioFileClip objects
            audio_clips_loaded = [
                clip if isinstance(clip, AudioFileClip) else AudioFileClip(clip)
                for clip in audio_clips
            ]

            combined_audio = concatenate_audioclips(audio_clips_loaded)

            if combined_audio.duration > video_clip.duration:
                combined_audio = combined_audio.subclip(0, video_clip.duration)

            # Set the combined audio to the video
            video_with_audio = video_clip.set_audio(combined_audio)
            video_clips.append(video_with_audio)

            #DND - For debugging purposes    
            #video_with_audio.write_videofile(f"video_with_audio_{element_id}.mp4", fps=24)
            
            # Do not close the video_with_audio here
            # video_with_audio.close()


            # Reset audio clips for the next image
            audio_clips = []

    final_video = concatenate_videoclips(video_clips, method="compose")

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

def scrape_page_with_camera_frame(url, base_url="https://readernook.com"):
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
        if element.name == "span" or element.name == "button" or (
            element.name == "div" and "audio-details" in element.get("class", [])
        ):
            return True
        return False
    
    # Loop through all elements within "songLyrics" div
    for element in soup.select_one(".songLyrics").descendants:
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
                current_text += " " + element.strip()

        # Collect images from <img class="movieImageCls">
        elif element.name == "div" and "image1-desc" in element.get("class", []):
            img_tag = element.find("img", class_="movieImageCls")
            img_src = urljoin(base_url, img_tag["src"]) if img_tag else None

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
                "camera_movement": camera_movement
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
                "camera_movement": None
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

#DND-OLD-For Reference-This had issues like image clip not being perfect.
def scrape_and_process_OLD_DND(urls, selected_size, selected_music, max_words, fontsize, y_pos, style, 
                       selected_voice, language, gender, tts_engine):
    if not urls or selected_size not in sizes or selected_music not in background_music_options:
        raise ValueError("Invalid input parameters")

    clear_folders()

    target_size = sizes.get(selected_size)  # Ensure it gets a tuple like (1080, 1920)
    if not target_size:
        print(f"Error: Invalid video type {selected_size}. Cannot process the image.")
        return

    output_folder = "processed_videos"
    os.makedirs(output_folder, exist_ok=True)

    for url in urls.split(";"):
        url = url.strip()
        if not url:
            continue

        try:
            base_file_name = Path(url).name
            text_image_pairs = scrape_page(url)

            audio_files, image_files = generate_audio_images(text_image_pairs, target_size, "audios", "images", language, gender, tts_engine)

            output_file = create_video(audio_files, image_files, target_size, background_music_options[selected_music])

            website_text = " ".join(text for text, _ in text_image_pairs)
            add_captions(max_words, fontsize, y_pos, style, website_text, font_settings)

            try:
                video_clip = VideoFileClip("output_video.mp4")

                final_video = add_gif_to_video(
                    video_clip, 5, icon_path="subscribe.gif"
                )

                final_video.write_videofile(
                    "output_video_with_gif.mp4", codec="libx264", audio_codec="aac", fps=24
                )

                output_file = "output_video_with_gif.mp4"
            except Exception as e:
                print("Error adding gif. Proceeding without gif")
                output_file = "output_video.mp4"

            if selected_size == "YouTube Shorts":
                video = VideoFileClip(output_file)
                duration_minutes = video.duration / 60

                if duration_minutes > 3:
                    print(f"Video duration {duration_minutes:.2f} minutes. Splitting required.")
                    split_files = split_video(output_file, video.duration, max_duration=130)  # 2m 10s
                    for idx, split_file in enumerate(split_files, start=1):
                        split_output_name = f"{output_folder}/{base_file_name}-{idx}.mp4"
                        safe_copy(split_file, split_output_name)
                else:
                    print(f"Video duration {duration_minutes:.2f} minutes. No splitting required.")
                    output_name = f"{output_folder}/{base_file_name}.mp4"
                    safe_copy(output_file, output_name)
            else:
                output_name = f"{output_folder}/{base_file_name}.mp4"
                safe_copy(output_file, output_name)

            print(f"Processing complete for {url}")

        except Exception as e:
            print(f"Error processing {url}: {e}. Proceeding to next")


def safe_copy(src, dst, retries=5, delay=2):
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

#DND-from ChatGPT - Failing for https://readernook.com/topics/amazing-short-stories/bruce-and-the-spider
def scrape_page_old(url):
    """
    Scrapes text and images from a given webpage URL, avoiding duplicates 
    caused by nested 'paragraph2-desc' blocks.

    Args:
        url (str): The webpage URL.

    Returns:
        list of tuples: Extracted text and image URL pairs.
    """    
    # Scrape the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Extract text-image pairs
    text_image_pairs = []
    current_text = ""
    last_image_url = None

    # Use a set to track processed divs to prevent duplicates
    processed_blocks = set()

    # Select all `paragraph2-desc` divs, including nested ones
    content_blocks = soup.select("div.paragraph2-desc")

    for block in content_blocks:
        # Skip already processed nested blocks
        if block in processed_blocks:
            continue
        
        # Mark this block as processed
        processed_blocks.add(block)

        # Traverse descendants
        for element in block.descendants:
            # Collect text directly from text nodes or text-like tags
            if isinstance(element, str) and element.strip():
                parent_classes = element.parent.get("class", [])
                if "paragraph2-desc" in parent_classes:
                    current_text += " " + element.strip()

            elif element.name == "p" and element.get_text(strip=True):
                current_text += " " + element.get_text(separator=" ").strip()

            # Collect images from <img class="movieImageCls">
            elif element.name == "img" and "movieImageCls" in element.get("class", []):
                last_image_url = element["src"]

                # Save text-image pair if text exists
                if current_text.strip():
                    text_image_pairs.append((current_text.strip(), last_image_url))
                    current_text = ""  # Reset after pairing
    
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
