import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pydub import AudioSegment
from pydub.playback import play
from pydub.generators import Sine
from gtts import gTTS
import os
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

def generate_audio(elements, output_file="final_audio.mp3"):
    """
    Generates a single audio file from text and sound effects.

    Args:
        elements (list of dict): List of elements containing text, sound properties, etc.
        output_file (str): The path to save the final audio file.
    """
    final_audio = AudioSegment.silent(duration=0)  # Start with silence

    for element in elements:
        if element["type"] == "text":
            # Generate TTS audio
            tts = gTTS(text=element["text"], lang="en")
            tts_file = "temp_tts.mp3"
            tts.save(tts_file)
            tts_audio = AudioSegment.from_file(tts_file)

            # Append TTS audio to final audio
            final_audio += tts_audio
            os.remove(tts_file)  # Clean up temporary file

        elif element["type"] == "audio":
            # Download the audio file if it's a URL
            local_audio_path = download_file(element["audio_src"])
            sound_effect = AudioSegment.from_file(local_audio_path)

            # Trim or extend the sound effect to match duration
            duration_ms = int(element["duration"] * 1000)
            if len(sound_effect) > duration_ms:
                sound_effect = sound_effect[:duration_ms]
            else:
                # Repeat the sound effect if it is too short
                sound_effect = sound_effect * (duration_ms // len(sound_effect) + 1)
                sound_effect = sound_effect[:duration_ms]

            # Adjust volume
            sound_effect = sound_effect + element["volume"] - 100  # Normalize volume to dBFS

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