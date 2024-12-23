# Enhanced Video Creation Script with Sound Effects
import os
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips
)
from moviepy.audio.AudioClip import CompositeAudioClip
from pydub import AudioSegment, silence
from PIL import Image
from effects import add_ken_burns_effect, add_zoom_effect
from call_to_action import add_gif_to_video
from get_audio import get_audio_file
from audio_video_processor import resize_and_crop_image
from settings import sizes, font_settings, background_music_options
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string
import nltk

nltk.download('punkt')
nltk.download('stopwords')
# Extract pauses from audio

custom_stopwords = set([
    "the", "and", "is", "in", "to", "of", "a", "with", "for", "on", "it", "that",
    "by", "this", "an", "be", "are", "or", "as", "at", "from", "but", "not", "was"
])

def simple_tokenize(text):
    import string
    text = text.lower()
    return [word.strip(string.punctuation) for word in text.split()]

def extract_keywords(text):
    words = text.lower().split()
    keywords = [word for word in words if word not in custom_stopwords]
    return keywords

def find_pauses(audio_file, min_silence_len=500, silence_thresh=-40):
    """Find pauses in the audio for inserting sound effects."""
    audio = AudioSegment.from_file(audio_file)
    pauses = silence.detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
    return [(start / 1000, end / 1000) for start, end in pauses]

# Add sound effects with controlled volume

def add_sfx_with_volume_control(video_clip, sfx_file, start_time, volume=0.3):
    """Add sound effects to the video at a specific timestamp with controlled volume."""
    sfx_clip = AudioFileClip(sfx_file).set_start(start_time).volumex(volume)
    return CompositeAudioClip([video_clip.audio, sfx_clip])

# Automatically assign sound effects to pauses or timestamps

def assign_sfx_to_scenes(text, sfx_mapping):
    """Map sound effects to story keywords extracted from the text."""
    keywords = extract_keywords(text)
    matched_sfx = [sfx_mapping[keyword] for keyword in keywords if keyword in sfx_mapping]
    return matched_sfx

# Extract keywords for identifying SFX

def extract_keywords(text):
    """Extract potential keywords for sound effects using simple rules."""


    stop_words = set(stopwords.words("english"))
    tokens = simple_tokenize(text)
    keywords = [word for word in tokens if word not in stop_words and word not in string.punctuation]
    return keywords

# Main video processing function

def apply_effects_and_create_video(image_files, audio_files, sfx_mapping, target_size, output_file="enhanced_video_with_sfx.mp4"):
    """Apply effects, captions, sound effects, and create an enhanced video."""
    video_clips = []
    total_audio_duration = 0

    for idx, (image_file, audio_file) in enumerate(zip(image_files, audio_files)):
        audio_clip = AudioFileClip(audio_file)
        img_duration = audio_clip.duration
        total_audio_duration += img_duration

        video_clip = add_zoom_effect(image_file, img_duration)
        video_clip = video_clip.set_audio(audio_clip)
        video_clips.append(video_clip)

    # Concatenate clips
    final_video = concatenate_videoclips(video_clips, method="compose")

    # DND- Temporarily commented out - 
    # Add background music
    # background_audio = AudioFileClip(background_music_options["Kids Stories"]).volumex(0.5)
    # if background_audio.duration > total_audio_duration:
    #     background_audio = background_audio.subclip(0, total_audio_duration)
    # else:
    #     background_audio = CompositeAudioClip(
    #         [background_audio] * int(total_audio_duration // background_audio.duration + 1)
    #     ).subclip(0, total_audio_duration)

    # mixed_audio = CompositeAudioClip([final_video.audio, background_audio])
    # final_video = final_video.set_audio(mixed_audio)

    # Add sound effects
    for idx, audio_file in enumerate(audio_files):
        pauses = find_pauses(audio_file)
        sfx_files = assign_sfx_to_scenes(text[idx], sfx_mapping)
        for sfx_file, (start, end) in zip(sfx_files, pauses):
            mixed_audio = add_sfx_with_volume_control(final_video, sfx_file, start)
    final_video = final_video.set_audio(mixed_audio)

    # DND-Temporarily commented out - Add call-to-action GIFs
    final_video = add_gif_to_video(final_video, show_gif_for_duration=3, icon_path="subscribe.gif")

    # Save the final video
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac")
    return output_file

# Process story with sound effects

def process_story_with_sfx(images, text, sfx_mapping, audio_output_dir="audio", video_output_dir="videos"):
    """Process story to create audio, captions, and final video with sound effects."""
    os.makedirs(audio_output_dir, exist_ok=True)
    os.makedirs(video_output_dir, exist_ok=True)

    audio_files = []
    for idx, scene_text in enumerate(text):
        audio_file = os.path.join(audio_output_dir, f"scene_{idx + 1}.mp3")
        get_audio_file(scene_text, audio_file, tts_engine="google", language="english", gender="Female")
        audio_files.append(audio_file)

    target_size = sizes["Regular YouTube Video"]
    for image in images:
        resize_and_crop_image(image, target_size)

    final_video_path = os.path.join(video_output_dir, "final_video_with_sfx.mp4")
    return apply_effects_and_create_video(images, audio_files, sfx_mapping, target_size, final_video_path)

# Example Usage
if __name__ == "__main__":
    images = ["images/image1.jpg", "images/image2.jpg", "images/image3.jpg"]  # Replace with actual paths
    text = [
        "Once upon a time, in a rain far away...",
        "A bird set out on an adventure.",
        "And they all laugh ever after.",
    ]

    sfx_mapping = {
        "rain": "sounds/rain.wav",
        "bird": "sounds/birds.wav",
        "thunder": "sounds/thunder.wav",
        "knock": "sounds/knock.wav",
        "laugh": "sounds/laugh.wav",
    }

    final_video = process_story_with_sfx(images, text, sfx_mapping)
    print(f"Final video with sound effects created: {final_video}")
