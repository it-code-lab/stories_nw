import os
import shutil
import requests
from bs4 import BeautifulSoup
import boto3
import urllib.request
from audio_video_processor import create_video, resize_and_crop_image
from caption_generator import add_captions
from settings import sizes, background_music_options, font_settings
from tkinter import messagebox
import re
from text_to_speech_google import synthesize_speech_google
from split_for_short import check_and_split_video

# Initialize Amazon Polly
polly_client = boto3.client('polly', region_name='us-east-1')

# Set Google Application Credentials using a relative path
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    os.path.dirname(__file__), "tts-secret", "notes-imgtotxt-7b07c59d85c6.json"
)

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


def scrape_and_process(url, selected_size, selected_music, max_words, fontsize, y_pos, style, 
selected_voice, language, gender):
    if not url or selected_size not in sizes or selected_music not in background_music_options:
        raise ValueError("Invalid input parameters")

    #print("Received scrape_and_process Arguments:", locals())

    # Clear folders
    clear_folders()

    # Scrape the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract text-image pairs
    text_image_pairs = []
    current_text = ""
    last_image_url = None
    language_code = ""
    gender_code = ""
    voice_code = ""
    tts_engine = "google"

    if (tts_engine == "google"):
        if (language == "english"):
            language_code = "en-US"
            if(gender == "Male"):
                voice_code = "en-US-Neural2-J"
                gender_code = "MALE"

            elif(gender == "Female"):
                voice_code = "en-US-Neural2-F"
                gender_code = "FEMALE"            
        elif(language == "hindi"):
            language_code = "hi-IN"
            if(gender == "Male"):
                voice_code = "hi-IN-Neural2-B"
                gender_code = "MALE"

            elif(gender == "Female"):
                voice_code = "hi-IN-Neural2-A"
                gender_code = "FEMALE"            
    elif (tts_engine == "amazon"):
        if (language == "english"):
            if(gender == "Male"):
                voice_code = "Matthew"
            elif(gender == "Female"):
                voice_code = "Joanna"
 
    # Correct function call
    target_size = sizes.get(selected_size)  # Ensure it gets a tuple like (1080, 1920)
    if not target_size:
        print(f"Error: Invalid video type {selected_size}. Cannot process the image.")

    # Select all `div.paragraph2-desc` blocks
    content_blocks = soup.select("div.paragraph2-desc")

    # Process each block
    for block in content_blocks:
        # Recursively process all descendants
        for element in block.descendants:
            # Collect text from text nodes or <p> tags
            if isinstance(element, str) and element.strip() and element.parent.name not in {"p", "img"}:  # Direct text node
                current_text += " " + element.strip()

            elif element.name == "p" and element.get_text(strip=True):
                current_text += " " + element.get_text(separator=" ").strip()

            # Collect images from <img class="movieImageCls">
            elif element.name == "img" and "movieImageCls" in element.get("class", []):
                last_image_url = element["src"]

                # Save text-image pair if text exists
                if current_text.strip():
                    text_image_pairs.append((current_text.strip(), last_image_url))
                    current_text = ""  # Reset text after pairing

    # Handle remaining text if no image follows
    if current_text.strip():
        text_image_pairs.append((current_text.strip(), last_image_url))

    audio_files = []
    image_files = []

    # Print pairs for verification
    for idx, (text, img_url) in enumerate(text_image_pairs):
        print(f"Pair {idx}: Text -> {text[:60]}... | Image -> {img_url}")
        # Your processing logic here

        # Generate audio using Amazon Polly
        audio_file = f"audios/audio{idx+1}.mp3"

        generated_audio = synthesize_speech_google(
            text=text, 
            output_file= audio_file, 
            language=language_code, 
            gender=gender_code, 
            voice_name=voice_code, 
            speaking_rate=1          #speaking_rate=0.9
        )
        if generated_audio:
            audio_files.append(generated_audio)

        # working sample for aws neural engine
        # response = polly_client.synthesize_speech(
        #     TextType="ssml",  # Use SSML for customization
        #     Text=f'<speak><prosody rate="80%">{clean_text(text)}</prosody></speak>',
        #     OutputFormat="mp3",
        #     VoiceId=selected_voice,
        #     Engine="neural"   
        # )

        # working sample for aws generative engine. ssml does not work for generative
        # response = polly_client.synthesize_speech(
        #     Text=text,
        #     OutputFormat="mp3",
        #     VoiceId=selected_voice,
        #     Engine="generative"  
        # )

        # with open(audio_file, "wb") as file:
        #     file.write(response['AudioStream'].read())
        # audio_files.append(audio_file)

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
        messagebox.showerror("Error", "Mismatch between audio and image counts.")
        return

    create_video(audio_files, image_files, target_size, background_music_options[selected_music])

    website_text = " ".join(text for text, _ in text_image_pairs)
    add_captions(max_words, fontsize, y_pos, style, website_text, font_settings)
    output_file = "output_video.mp4"
    check_and_split_video(output_file, selected_size)
