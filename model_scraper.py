import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pydub import AudioSegment
from pydub.playback import play
from pydub.generators import Sine
from gtts import gTTS
import os
from moviepy.video.fx.all import crop, resize  # Import crop and resize effects as needed
from moviepy.editor import ImageClip, TextClip, concatenate_videoclips, concatenate_audioclips, AudioFileClip
from tempfile import NamedTemporaryFile


def scrape_page_chatgpt(url):
    """
    Scrapes text and images from a webpage, avoiding duplicates caused by nested 'paragraph2-desc' blocks.

    Args:
        url (str): The webpage URL.

    Returns:
        list of tuples: Extracted text and image URL pairs.
    """    
    print("Received scrape_page Arguments:", locals())
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch page, status code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    text_image_pairs = []
    current_text = ""
    last_image_url = None
    
    # Track processed blocks by their memory reference
    processed_blocks = set()

    # Extract only top-level content blocks
    content_blocks = soup.select("div.paragraph2-desc")
    print(f"Found {len(content_blocks)} content blocks")

    for block in content_blocks:
        if block in processed_blocks:
            print(f"Skipping already processed block with id {block.get('id', 'No ID')}")
            continue

        processed_blocks.add(block)
        print(f"Processing block with id {block.get('id', 'No ID')}")

        # Collect text and images
        for element in block.descendants:
            if element.name == "p" or isinstance(element, str):
                text_content = element.get_text(strip=True) if element.name == "p" else element.strip()
                if text_content:
                    current_text += " " + text_content
                    print(f"Collected text: {current_text.strip()}")

            elif element.name == "img" and "movieImageCls" in element.get("class", []):
                last_image_url = element["src"]
                print(f"Found image: {last_image_url}")

                # Save pair if text exists
                if current_text.strip():
                    text_image_pairs.append((current_text.strip(), last_image_url))
                    print(f"Pair added: Text: {current_text.strip()} | Image: {last_image_url}")
                    current_text = ""  # Reset text after pairing

    # Handle any remaining text without an image
    if current_text.strip():
        text_image_pairs.append((current_text.strip(), last_image_url))
        print(f"Final pair added: Text: {current_text.strip()} | Image: {last_image_url}")

    print("Completed processing")
    return text_image_pairs

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

def scrape_story_page_with_soundeffect(url):
    """
    Scrapes text, audio elements, and images from a given webpage URL.
    
    Args:
        url (str): The webpage URL.
        
    Returns:
        list of dict: Each dict contains details about text, audio, and images.
    """
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch the page, status code: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Target container
    song_lyrics_div = soup.select_one(".songLyrics")
    if not song_lyrics_div:
        raise ValueError("No element with class 'songLyrics' found on the page.")

    # Result structure
    elements = []
    current_text = ""
    current_image = None

    # Iterate over descendants
    for element in song_lyrics_div.descendants:
        if element.name == "script" or element.name == "style":
            continue

        # Text nodes
        if isinstance(element, str) and element.strip():
            current_text += " " + element.strip()

        # Image elements
        elif element.name == "img" and "movieImageCls" in element.get("class", []):
            current_image = urljoin(url, element["src"])

        # Audio elements
        elif element.name == "div" and "audio-desc" in element.get("class", []):
            audio_src = urljoin(url, element.find("audio")["src"])
            start_time = element.select_one("[id$='-start']").text.strip()
            duration = element.select_one("[id$='-duration']").text.strip()
            volume = element.select_one("[id$='-volume']").text.strip()
            overlap = element.select_one("[id$='-overlap']").text.strip()

            # Save collected data
            elements.append({
                "type": "audio",
                "text": current_text.strip(),
                "audio_src": audio_src,
                "start_time": float(start_time),
                "duration": float(duration),
                "volume": int(volume),
                "overlap": overlap.lower() == "yes",
                "image_src": current_image
            })
            current_text = ""  # Reset text
            current_image = None  # Reset image

    # Append remaining text and image if no audio
    if current_text.strip() or current_image:
        elements.append({
            "type": "text_image",
            "text": current_text.strip(),
            "audio_src": None,
            "start_time": None,
            "duration": None,
            "volume": None,
            "overlap": None,
            "image_src": current_image
        })

    return elements

#DND-Working
def scrape_page_sm(url):
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
    elements = []

    def is_skippable(element):
        """
        Check if the element should be skipped for text extraction.
        """
        if element.name == "span" or (
            element.name == "div" and "audio-details" in element.get("class", [])
        ):
            return True
        return False
    
    # Loop through all elements within "songLyrics" div
    for element in soup.select_one(".songLyrics").descendants:
        # Skip irrelevant elements (script, styles, etc.)
        if element.name in ("script", "style", "p"):
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
                    "audio_src": None,
                    "start_time": None,
                    "duration": None,
                    "volume": None,
                    "overlap": None,
                    "image_src": None,
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
                "audio_src": audio_src,
                "start_time": float(start_time),
                "duration": float(duration),
                "volume": int(volume),
                "overlap": overlap.lower() == "yes",
                "image_src": None,
            })

        # Text nodes
        elif isinstance(element, str) and element.strip():
            if not any(parent for parent in element.parents if is_skippable(parent)):
                current_text += " " + element.strip()

        # Collect images from <img class="movieImageCls">
        elif element.name == "img" and "movieImageCls" in element.get("class", []):
            last_image_url = element["src"]

            # Save text-image pair if text and image exist
            if current_text.strip() :
                # text_image_pairs.append((current_text.strip(), last_image_url))
                # current_text = ""  # Reset text after pairing
                elements.append({
                    "type": "text",
                    "text": current_text,
                    "audio_src": None,
                    "start_time": None,
                    "duration": None,
                    "volume": None,
                    "overlap": None,
                    "image_src": None,
                })
                current_text = ""  # Reset text after pairing

    # Handle remaining text if no image follows
    if current_text.strip():
        #text_image_pairs.append((current_text.strip(), last_image_url))
        elements.append({
            "type": "text",
            "text": current_text,
            "audio_src": None,
            "start_time": None,
            "duration": None,
            "volume": None,
            "overlap": None,
            "image_src": None,
        })
    #return text_image_pairs
    return elements

#DND-Working
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
    text_image_pairs = []
    current_text = ""
    last_image_url = None
    elements = []
    previous_image_data = None
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
                left = style_dict.get('left')
                top = style_dict.get('top')

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

            elements.append(image_data)
            previous_image_data = image_data

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

    return elements

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

#DND- Working
def generate_audio(elements, output_file="final_audio.mp3"):
    """
    Generates a single audio file from text and sound effects.

    Args:
        elements (list of dict): List of elements containing text, sound properties, etc.
        output_file (str): The path to save the final audio file.
    """
    final_audio = AudioSegment.silent(duration=0)  # Start with silence

    for element in elements:
        print(f"Processing element: {element}")
        if element["type"] == "text":
            try:
                # Generate TTS audio
                tts = gTTS(text=element["text"], lang="en")
                tts_file = "temp_tts.mp3"
                tts.save(tts_file)
                tts_audio = AudioSegment.from_file(tts_file)

                # Append TTS audio to final audio
                final_audio += tts_audio
                os.remove(tts_file)  # Clean up temporary file
            except Exception as e:
                print("Error processing text")
        elif element["type"] == "audio":
            # Download the audio file if it's a URL
            local_audio_path = download_file(element["audio_src"])
            sound_effect = AudioSegment.from_file(local_audio_path)

            # Trim or extend the sound effect to match duration
            duration_ms = int(element["duration"] * 1000)
            if len(sound_effect) > duration_ms:
                sound_effect = sound_effect[:duration_ms]
                #sound_effect.export("debug_sound_effect_1.mp3", format="mp3")
            else:
                # Repeat the sound effect if it is too short
                sound_effect = sound_effect * (duration_ms // len(sound_effect) + 1)
                #sound_effect.export("debug_sound_effect_2.mp3", format="mp3")
                sound_effect = sound_effect[:duration_ms]
                #sound_effect.export("debug_sound_effect_3.mp3", format="mp3")
            # Adjust volume
            print(f"Original dBFS: {sound_effect.dBFS}")
            # Calculate volume adjustment
            volume_adjustment = element["volume"] - 100

            # Clamp excessive decreases
            if volume_adjustment < -45:
                volume_adjustment = -45

            # Clamp excessive increases
            if volume_adjustment > 100:
                volume_adjustment = 100

            # Apply adjustment with threshold check
            if sound_effect.dBFS + volume_adjustment < -50:
                volume_adjustment = -50 - sound_effect.dBFS

            # Adjust volume
            sound_effect = sound_effect + volume_adjustment

            # Normalize (optional)
            target_dBFS = -20.0
            sound_effect = sound_effect.apply_gain(target_dBFS - sound_effect.dBFS)

            # Export for debugging
            #sound_effect.export("debug_sound_effect_4.mp3", format="mp3")
            print(f"Final adjusted dBFS: {sound_effect.dBFS}")

            # Handle overlap
            if element["overlap"]:
                # Mix sound effect with the current TTS audio
                final_audio = final_audio.overlay(sound_effect)
            else:
                # Append sound effect after the current audio
                final_audio += sound_effect

            # Clean up the downloaded file
            os.remove(local_audio_path)

    # Export final audio
    final_audio.export(output_file, format="mp3")
    print(f"Final audio saved to {output_file}")

def create_video_from_elements_Backup(elements, output_path):
    """
    Creates a video using the scrapped elements.

    Args:
        elements (list[dict]): Scrapped elements containing text, audio, and image data.
        output_path (str): Path to save the final video.
    """
    video_clips = []
    audio_clips = []
    last_image_clip = None

    for idx, element in enumerate(elements):# Using enumerate to get the index

        element_id = element.get("id", f"element_{idx}")  # Use "id" if available, fallback to generated ID

        print(f"Processing element: {element}")
        if element["type"] == "text":
            try:
                # Generate TTS audio for text
                tts = gTTS(text=element["text"], lang="en")
                tts_audio_path = NamedTemporaryFile(delete=False, suffix=".mp3").name
                tts.save(tts_audio_path)
                tts_audio = AudioFileClip(tts_audio_path)
                audio_clips.append(tts_audio)

                # Export intermediate TTS audio
                tts_audio.write_audiofile(f"debug_audio_tts_{element_id}.mp3")

            except Exception as e:
                print("Error processing text")

        elif element["type"] == "audio":
            # # Add sound effect
            # Download the audio file if it's a URL
            local_audio_path = download_file(element["audio"]["src"])
            sound_effect = AudioSegment.from_file(local_audio_path)

            # Trim or extend the sound effect to match duration
            duration_ms = int(float(element["audio"]["duration"]) * 1000)
            if len(sound_effect) > duration_ms:
                sound_effect = sound_effect[:duration_ms]
                #sound_effect.export(f"debug_sound_effect_1_{element_id}.mp3", format="mp3")
            else:
                # Repeat the sound effect if it is too short
                print(f"duration_ms: {duration_ms}")
                print(f"len(sound_effect): {len(sound_effect)}")
                sound_effect = sound_effect * (duration_ms // len(sound_effect) + 1)
                #sound_effect.export(f"debug_sound_effect_2_{element_id}.mp3", format="mp3")
                sound_effect = sound_effect[:duration_ms]
                #sound_effect.export(f"debug_sound_effect_3_{element_id}.mp3", format="mp3")
            # Adjust volume
            print(f"Original dBFS: {sound_effect.dBFS}")
            # Calculate volume adjustment
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

            # Adjust volume
            sound_effect = sound_effect + volume_adjustment

            # Normalize (optional)
            target_dBFS = -20.0
            sound_effect = sound_effect.apply_gain(target_dBFS - sound_effect.dBFS)

            # Export for debugging
            sound_effect.export(f"debug_sound_effect_4_{element_id}.mp3", format="mp3")
            print(f"Final adjusted dBFS: {sound_effect.dBFS}")

            # Save to temp file and load as AudioFileClip
            effect_audio_path = NamedTemporaryFile(delete=False, suffix=".mp3").name
            sound_effect.export(effect_audio_path, format="mp3")
            effect_audio_clip = AudioFileClip(effect_audio_path)
            audio_clips.append(effect_audio_clip)

            # Clean up the downloaded file
            os.remove(local_audio_path)

        elif element["type"] == "image":
            # Create an ImageClip with or without camera movement
            img_clip = ImageClip(element["image"])

            # Determine duration from preceding audio clips
            duration = sum([clip.duration for clip in audio_clips]) if audio_clips else 3

            if element["camera_movement"]:
                # Extract start and end frames
                start_frame = element["camera_movement"]["start_frame"]
                end_frame = element["camera_movement"]["end_frame"]

                # Get actual image dimensions
                actual_width, actual_height = img_clip.size

                # Styled dimensions (from the website)
                styled_width = 400  # Example styled width

                scale_x = actual_width / styled_width;

                # Parse and validate start frame values
                start_x1 = float((start_frame.get("left", "0px") or "0px").rstrip("px")) * scale_x
                start_y1 = float((start_frame.get("top", "0px") or "0px").rstrip("px")) * scale_x
                start_width = float((start_frame.get("width", "0px") or "0px").rstrip("px")) * scale_x
                start_height = float((start_frame.get("height", "0px") or "0px").rstrip("px")) * scale_x

                # Parse and validate end frame values
                end_x1 = float((end_frame.get("left", "0px") or "0px").rstrip("px")) * scale_x
                end_y1 = float((end_frame.get("top", "0px") or "0px").rstrip("px")) * scale_x
                end_width = float((end_frame.get("width", "0px") or "0px").rstrip("px")) * scale_x
                end_height = float((end_frame.get("height", "0px") or "0px").rstrip("px")) * scale_x

                # Crop image based on start and end frames
                # img_clip = img_clip.crop(
                #     x1=start_x1,
                #     y1=start_y1,
                #     x2=start_x1 + start_width,
                #     y2=start_y1 + start_height
                # ).set_position((end_x2, end_y2))


                # Define interpolation functions for crop values
                def interpolate(start, end):
                    return lambda t: start + (end - start) * t

                # Create animated crop parameters
                crop_x1 = interpolate(start_x1, end_x1)
                crop_y1 = interpolate(start_y1, end_y1)
                crop_x2 = interpolate(start_x1 + start_width, end_x1 + end_width)
                crop_y2 = interpolate(start_y1 + start_height, end_y1 + end_height)

                # Define crop animation
                def make_frame(get_frame, t):
                    x1 = crop_x1(t / duration)
                    y1 = crop_y1(t / duration)
                    x2 = crop_x2(t / duration)
                    y2 = crop_y2(t / duration)
                    return img_clip.crop(x1=x1, y1=y1, x2=x2, y2=y2).get_frame(t)

                # Apply the animation
                img_clip = img_clip.fl(make_frame, apply_to=['mask']).set_duration(duration)

            else:
                # Default zoom effect
                img_clip = img_clip.resize(height=720)


            img_clip = img_clip.set_duration(duration)
            video_clips.append(img_clip)

            # Export intermediate video for debugging
            img_clip.write_videofile(f"debug_video_{element_id}.mp4", fps=24)

            # Reset audio_clips for the next image's duration calculation
            audio_clips = []

            # Keep the last image clip for the final text block
            last_image_clip = img_clip

    # Handle final text or audio
    if last_image_clip:
        final_duration = sum([clip.duration for clip in audio_clips]) if audio_clips else 3
        last_image_clip = last_image_clip.set_duration(final_duration)
        video_clips.append(last_image_clip)

    # Concatenate video and audio clips
    final_video = concatenate_videoclips(video_clips)
    final_audio = concatenate_audioclips(audio_clips)
    final_video = final_video.set_audio(final_audio)

    # Write the final video
    final_video.write_videofile(output_path, fps=24)

    # Clean up temporary files
    # for temp_file in [tts_audio_path, effect_audio_path]:
    #     if os.path.exists(temp_file):
    #         os.remove(temp_file)

# Define crop animation

def create_video_from_elements(elements, output_path):
    """
    Creates a video using the scrapped elements.

    Args:
        elements (list[dict]): Scrapped elements containing text, audio, and image data.
        output_path (str): Path to save the final video.
    """
    video_clips = []
    audio_clips = []
    last_image_clip = None

    for idx, element in enumerate(elements):# Using enumerate to get the index

        element_id = element.get("id", f"element_{idx}")  # Use "id" if available, fallback to generated ID

        print(f"Processing element: {element}")
        if element["type"] == "text":
            try:
                # Generate TTS audio for text
                tts = gTTS(text=element["text"], lang="en")
                tts_audio_path = NamedTemporaryFile(delete=False, suffix=".mp3").name
                tts.save(tts_audio_path)
                tts_audio = AudioFileClip(tts_audio_path)
                audio_clips.append(tts_audio)

                # Export intermediate TTS audio
                tts_audio.write_audiofile(f"debug_audio_tts_{element_id}.mp3")

            except Exception as e:
                print("Error processing text")

        elif element["type"] == "audio":
            # # Add sound effect
            # Download the audio file if it's a URL
            local_audio_path = download_file(element["audio"]["src"])
            sound_effect = AudioSegment.from_file(local_audio_path)

            # Trim or extend the sound effect to match duration
            duration_ms = int(float(element["audio"]["duration"]) * 1000)
            if len(sound_effect) > duration_ms:
                sound_effect = sound_effect[:duration_ms]
                #sound_effect.export(f"debug_sound_effect_1_{element_id}.mp3", format="mp3")
            else:
                # Repeat the sound effect if it is too short
                print(f"duration_ms: {duration_ms}")
                print(f"len(sound_effect): {len(sound_effect)}")
                sound_effect = sound_effect * (duration_ms // len(sound_effect) + 1)
                #sound_effect.export(f"debug_sound_effect_2_{element_id}.mp3", format="mp3")
                sound_effect = sound_effect[:duration_ms]
                #sound_effect.export(f"debug_sound_effect_3_{element_id}.mp3", format="mp3")
            # Adjust volume
            print(f"Original dBFS: {sound_effect.dBFS}")
            # Calculate volume adjustment
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

            # Adjust volume
            sound_effect = sound_effect + volume_adjustment

            # Normalize (optional)
            target_dBFS = -20.0
            sound_effect = sound_effect.apply_gain(target_dBFS - sound_effect.dBFS)

            # Export for debugging
            sound_effect.export(f"debug_sound_effect_4_{element_id}.mp3", format="mp3")
            print(f"Final adjusted dBFS: {sound_effect.dBFS}")

            # Save to temp file and load as AudioFileClip
            effect_audio_path = NamedTemporaryFile(delete=False, suffix=".mp3").name
            sound_effect.export(effect_audio_path, format="mp3")
            effect_audio_clip = AudioFileClip(effect_audio_path)
            audio_clips.append(effect_audio_clip)

            # Clean up the downloaded file
            os.remove(local_audio_path)

        elif element["type"] == "image":
            # Create an ImageClip with or without camera movement
            img_clip = ImageClip(element["image"])

            # Determine duration from preceding audio clips
            duration = sum([clip.duration for clip in audio_clips]) if audio_clips else 3

            if element["camera_movement"]:
                # Extract start and end frames
                start_frame = element["camera_movement"]["start_frame"]
                end_frame = element["camera_movement"]["end_frame"]

                # Get actual image dimensions
                actual_width, actual_height = img_clip.size

                # Styled dimensions (from the website)
                styled_width = 400  # Example styled width

                scale_x = actual_width / styled_width;

                # Parse and validate start frame values
                start_x1 = float((start_frame.get("left", "0px") or "0px").rstrip("px")) * scale_x
                start_y1 = float((start_frame.get("top", "0px") or "0px").rstrip("px")) * scale_x
                start_width = float((start_frame.get("width", "0px") or "0px").rstrip("px")) * scale_x
                start_height = float((start_frame.get("height", "0px") or "0px").rstrip("px")) * scale_x

                # Parse and validate end frame values
                end_x1 = float((end_frame.get("left", "0px") or "0px").rstrip("px")) * scale_x
                end_y1 = float((end_frame.get("top", "0px") or "0px").rstrip("px")) * scale_x
                end_width = float((end_frame.get("width", "0px") or "0px").rstrip("px")) * scale_x
                end_height = float((end_frame.get("height", "0px") or "0px").rstrip("px")) * scale_x

                # Crop image based on start and end frames
                # img_clip = img_clip.crop(
                #     x1=start_x1,
                #     y1=start_y1,
                #     x2=start_x1 + start_width,
                #     y2=start_y1 + start_height
                # ).set_position((end_x2, end_y2))


                # Define interpolation functions for crop values
                def interpolate(start, end):
                    return lambda t: start + (end - start) * t

                # Create animated crop parameters
                crop_x1 = interpolate(start_x1, end_x1)
                crop_y1 = interpolate(start_y1, end_y1)
                crop_x2 = interpolate(start_x1 + start_width, end_x1 + end_width)
                crop_y2 = interpolate(start_y1 + start_height, end_y1 + end_height)

                # Define crop animation
                def make_frame(get_frame, t):
                    x1 = crop_x1(t / duration)
                    y1 = crop_y1(t / duration)
                    x2 = crop_x2(t / duration)
                    y2 = crop_y2(t / duration)
                    return img_clip.crop(x1=x1, y1=y1, x2=x2, y2=y2).get_frame(t)

                # Apply the animation
                img_clip = img_clip.fl(make_frame, apply_to=['mask']).set_duration(duration)

            else:
                # Default zoom effect
                img_clip = img_clip.resize(height=720)


            img_clip = img_clip.set_duration(duration)
            video_clips.append(img_clip)

            # Export intermediate video for debugging
            img_clip.write_videofile(f"debug_video_{element_id}.mp4", fps=24)

            # Reset audio_clips for the next image's duration calculation
            audio_clips = []

            # Keep the last image clip for the final text block
            last_image_clip = img_clip

    # Handle final text or audio
    if last_image_clip:
        final_duration = sum([clip.duration for clip in audio_clips]) if audio_clips else 3
        last_image_clip = last_image_clip.set_duration(final_duration)
        video_clips.append(last_image_clip)

    # Concatenate video and audio clips
    final_video = concatenate_videoclips(video_clips)
    final_audio = concatenate_audioclips(audio_clips)
    final_video = final_video.set_audio(final_audio)

    # Write the final video
    final_video.write_videofile(output_path, fps=24)

    # Clean up temporary files
    # for temp_file in [tts_audio_path, effect_audio_path]:
    #     if os.path.exists(temp_file):
    #         os.remove(temp_file)

# Define crop animation
