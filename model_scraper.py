import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pydub import AudioSegment
from pydub.playback import play
from pydub.generators import Sine
from gtts import gTTS
import os
from moviepy.video.fx.all import crop, resize  # Import crop and resize effects as needed
from moviepy.editor import ImageClip, TextClip, concatenate_videoclips, concatenate_audioclips, CompositeAudioClip, AudioFileClip, VideoFileClip
from tempfile import NamedTemporaryFile
import numpy as np
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from effects import add_ken_burns_effect, create_camera_movement_clip, create_camera_movement_clip_Linear, create_camera_movement_video, create_camera_movement_video_Linear_motion
from moviepy.video.VideoClip import VideoClip



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

    for idx, element in enumerate(elements):  # Using enumerate to get the index

        #DND - For debugging
        if idx > 8:
            break  # Break the loop after processing 5 elements
        
        #if idx < 49:
        #    continue


        element_id = element.get("id", f"element_{idx}")  # Use "id" if available, fallback to generated ID
        
        #DND - For debugging
        print(f"Processing element {idx}: {element}")
        #print(f"Processing element: {idx}")

        if element["type"] == "text":
            try:
                # Generate TTS audio for text
                tts = gTTS(text=element["text"], lang="en")
                tts_audio_path = NamedTemporaryFile(delete=False, suffix=".mp3").name
                tts.save(tts_audio_path)
                tts_audio = AudioFileClip(tts_audio_path)
                audio_clips.append(tts_audio)

                #DND - For Debugging - Export intermediate TTS audio
                #tts_audio.write_audiofile(f"debug_audio_tts_{element_id}.mp3")

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

                # Normalize (optional)
                target_dBFS = -20.0
                sound_effect = sound_effect.apply_gain(target_dBFS - sound_effect.dBFS)

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

            #video_clip = create_camera_movement_clip_Linear(
            video_clip = create_camera_movement_clip(
                element['image'], 
                start_frame, 
                end_frame, 
                duration = duration,
                fps=24,
                movement_percentage=70
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

            # Render the video to a temporary file to ensure smooth concatenation - Needed for non linear camera movement
            temp_file = f"temp/temp_video_{element_id}.mp4"
            video_with_audio.write_videofile(temp_file, fps=24, codec="libx264", audio_codec="aac")

            # Load the rendered file as a VideoFileClip
            rendered_clip = VideoFileClip(temp_file)


            video_clips.append(rendered_clip)

            #DND - For debugging purposes    
            #video_with_audio.write_videofile(f"video_with_audio_{element_id}.mp4", fps=24)
            
            # Do not close the video_with_audio here
            # video_with_audio.close()


            # Reset audio clips for the next image
            audio_clips = []

    #DND - Working with linear camera movement
    final_video = concatenate_videoclips(video_clips, method="compose")

    # Not working with Linear motion - Concatenate video clips with 'chain' method to preserve motion
    #final_video = concatenate_videoclips(video_clips, method="chain")

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


