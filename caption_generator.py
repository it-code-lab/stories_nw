import os
import re
import difflib
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import whisper


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
def add_captions(max_words, fontsize, y_pos, style, website_text, font_settings):
    video_path = "final_video.mp4"
    audio_path = "audio.wav"
    output_video_path = "output_video.mp4"

    extract_audio(video_path, audio_path)

    audio_transcription = normalize_text(website_text)

    # Improved Alignment with Website Text
    subtitles = generate_aligned_subtitles(audio_path, audio_transcription, max_words)

    # Create the Video with Captions
    video = VideoFileClip(video_path)
    styled_video = create_stylish_subtitles(video, subtitles, style, fontsize, y_pos, font_settings)
    styled_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
