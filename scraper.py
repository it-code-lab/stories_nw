import os
import subprocess
import shutil
import requests
from bs4 import BeautifulSoup
import urllib.request
from audio_video_processor import create_video, resize_and_crop_image
from caption_generator import add_captions
from settings import sizes, background_music_options, font_settings
from tkinter import messagebox
import re
from pathlib import Path
from moviepy.editor import VideoFileClip
import time
import shutil
from get_audio import get_audio_file
from moviepy.editor import VideoFileClip
from call_to_action import add_gif_to_video

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


import os
from pathlib import Path
from moviepy.editor import VideoFileClip

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
            text_image_pairs = scrape_page(url)

            audio_files, image_files = generate_audio_images(text_image_pairs, target_size, "audios", "images", language, gender, tts_engine)

            output_file = create_video(audio_files, image_files, target_size, background_music_options[selected_music])

            website_text = " ".join(text for text, _ in text_image_pairs)
            add_captions(max_words, fontsize, y_pos, style, website_text, font_settings)

            try:
                video_clip = VideoFileClip("output_video.mp4")

                final_video = add_gif_to_video(
                    video_clip, 10, icon_path="subscribe.gif"
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
