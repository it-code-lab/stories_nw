# GEMINI Code - Not working yet

import torch

# --- ⬇️ SECURE FIX FOR THE "WEIGHTS ONLY" ERROR ⬇️ ---
# PyTorch 2.6+ blocks certain library types by default. 
# We must allowlist them before importing whisperx.
from omegaconf.listconfig import ListConfig
from omegaconf.dictconfig import DictConfig
try:
    # Allow WhisperX and Pyannote to load their internal configs
    torch.serialization.add_safe_globals([ListConfig, DictConfig])
    
    # If you still get an error, this broad "trust" backup ensures it works:
    _original_torch_load = torch.load
    def patched_torch_load(*args, **kwargs):
        if 'weights_only' not in kwargs:
            kwargs['weights_only'] = False
        return _original_torch_load(*args, **kwargs)
    torch.load = patched_torch_load
except Exception as e:
    print(f"Warning: Setup patch failed: {e}")
# --- ⬆️ END FIX ⬆️ ---

import whisperx

import moviepy.editor as mp
from moviepy.editor import TextClip, CompositeVideoClip
import numpy as np
import gc

# --- CONFIGURATION ---
VIDEO_FILE = "input.mp4"       
OUTPUT_FILE = "output_captioned.mp4" 
# FONT_PATH = "Nirmala.ttf"            # Ensure this file exists!
FONT_PATH = "fonts/arial.ttf"            # Ensure this file exists!
FONT_SIZE = 70
HIGHLIGHT_COLOR = "yellow"
DEFAULT_COLOR = "white"
STROKE_COLOR = "black"
STROKE_WIDTH = 2
MAX_WORDS_PER_CHUNK = 4

def transcribe_audio(video_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading WhisperX on {device}...")
    
    # Use int8 on CPU to save memory, float16 on GPU for speed
    compute_type = "float16" if device == "cuda" else "int8"
    
    model = whisperx.load_model("large-v2", device, compute_type=compute_type)
    audio = whisperx.load_audio(video_path)
    result = model.transcribe(audio, batch_size=16)
    
    # Align model
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    
    # Cleanup
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    del model
    del model_a

    word_segments = []
    for segment in result["segments"]:
        if "words" in segment:
            for word in segment["words"]:
                if 'start' in word:
                    word_segments.append(word)
    return word_segments

def create_word_groups(word_segments, max_words=4):
    groups = []
    current_group = []
    for word in word_segments:
        current_group.append(word)
        if len(current_group) >= max_words:
            groups.append(current_group)
            current_group = []
    if current_group:
        groups.append(current_group)
    return groups

def generate_caption_clips(word_groups, video_size):
    w, h = video_size
    clips = []
    
    # Position settings
    y_pos = h * 0.75

    for group in word_groups:
        for i, active_word_data in enumerate(group):
            word_start = active_word_data['start']
            word_end = active_word_data['end']
            
            # Fill time until next word starts
            if i < len(group) - 1:
                clip_duration = group[i+1]['start'] - word_start
            else:
                clip_duration = word_end - word_start

            # Create the full line of text for this moment
            word_clips = []
            total_text_width = 0
            temp_clips = []
            
            for word_data in group:
                txt = word_data['word']
                is_active = (word_data['start'] == active_word_data['start'])
                color = HIGHLIGHT_COLOR if is_active else DEFAULT_COLOR
                
                txt_clip = TextClip(
                    txt, 
                    fontsize=FONT_SIZE, 
                    font=FONT_PATH, 
                    color=color, 
                    stroke_color=STROKE_COLOR, 
                    stroke_width=STROKE_WIDTH
                ).set_duration(clip_duration)
                
                temp_clips.append(txt_clip)
                total_text_width += txt_clip.w + 15 

            # Center the line
            x_pos = (w - total_text_width) / 2
            
            for txt_clip in temp_clips:
                txt_clip = txt_clip.set_position((x_pos, y_pos)).set_start(word_start)
                clips.append(txt_clip)
                x_pos += txt_clip.w + 15
                
    return clips

def main():
    try:
        video = mp.VideoFileClip(VIDEO_FILE)
    except Exception as e:
        print(f"Error loading video: {e}")
        return

    print("Transcribing and Aligning...")
    word_segments = transcribe_audio(VIDEO_FILE)
    
    print("Creating Captions...")
    groups = create_word_groups(word_segments, MAX_WORDS_PER_CHUNK)
    text_overlays = generate_caption_clips(groups, video.size)
    
    print("Rendering...")
    final_video = CompositeVideoClip([video] + text_overlays)
    final_video.write_videofile(OUTPUT_FILE, codec="libx264", audio_codec="aac", fps=video.fps, threads=4)

if __name__ == "__main__":
    main()