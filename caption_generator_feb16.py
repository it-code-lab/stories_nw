import os
import re
import difflib
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import whisper
import traceback

# Extract Audio from Video
def extract_audio(video_path, audio_path):
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path)

# Normalize Text with Enhanced Rules
def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s']", "", text)  # Keep only letters, numbers, and apostrophes
    text = re.sub(r"\s+", " ", text).strip()  # Remove extra spaces
    return text

# Improved Subtitle Generation Logic
def generate_aligned_subtitles(audio_path, website_text, max_words):

    print("Received generate_aligned_subtitles Arguments:", locals())

    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=True)
    grouped_subtitles = []
    current_caption = []
    current_start = None

    for segment in result['segments']:
        for word_info in segment['words']:
            word = word_info['word']
            start = word_info['start']
            end = word_info['end']
            if current_start is None:
                current_start = start
            current_caption.append(word)
            if len(current_caption) >= max_words or word_info == segment['words'][-1]:
                caption_text = " ".join(current_caption)
                grouped_subtitles.append((current_start, end, caption_text))
                current_caption = []
                current_start = None

    return grouped_subtitles

# Enhanced Stylish Subtitle Creator
def create_stylish_subtitles(video, subtitles, style, fontsize, y_pos, font_settings):
    subtitle_clips = []
    style_options = font_settings[style]

    for start, end, text in subtitles:
        txt_clip = (
            TextClip(
                text,
                font=style_options['font'],
                fontsize=fontsize,
                color=style_options['color'],
                stroke_color="black",
                stroke_width=2,
                method="label",
                bg_color="rgba(0, 0, 0, 0.5)"
            )
            .set_position(("center", y_pos))
            .set_start(start)
            .set_duration(end - start)
        )
        subtitle_clips.append(txt_clip)

    return CompositeVideoClip([video] + subtitle_clips)

# Correct and Add Captions
import traceback

def add_captions(max_words, fontsize, y_pos, style, website_text, font_settings, input_video_path="final_video.mp4"):
    
    print("Received add_captions Arguments:", locals())

    audio_path = "audio.wav"
    output_video_path = "output_video.mp4"

    try:
        extract_audio(input_video_path, audio_path)
        print("Audio extracted successfully!")
    except Exception as e:
        print(f"Error extracting audio: {e}")
        traceback.print_exc()
        return
    
    try:
        audio_transcription = normalize_text(website_text)
        print("Text normalized successfully!")
    except Exception as e:
        print(f"Error normalizing text: {e}")
        traceback.print_exc()
        return
    
    try:
        # Improved Alignment with Website Text
        subtitles = generate_aligned_subtitles(audio_path, audio_transcription, max_words)
        print("Subtitles generated successfully!")
    except Exception as e:
        print(f"Error generating subtitles: {e}")
        traceback.print_exc()
        return
    
    try:
        # Create the Video with Captions
        video = VideoFileClip(input_video_path)
        styled_video = create_stylish_subtitles(video, subtitles, style, fontsize, y_pos, font_settings)
    except Exception as e:
        print(f"Error loading video: {e}")
        traceback.print_exc()
        return
    
    try:
        # Write output and ensure file closure
        styled_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
    except Exception as e:
        print(f"Error writing video file: {e}")
        traceback.print_exc()
        return
    finally:
        # Ensure proper resource release
        styled_video.close()
        video.close()
    
    print("Captioning process completed successfully!")
