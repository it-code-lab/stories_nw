#import os
import subprocess
#from my_existing_script import generate_video  # Your existing video creation script

# Paths for AI avatar generation
WAV2LIP_PATH = "Wav2Lip"
SADTALKER_PATH = "SadTalker"
TTS_AUDIO = "audio.wav"
#INPUT_TEXT = "input_text.txt"  # Extracted from your website
INPUT_IMAGE = "Avatar_4_SadTalker/avatar_female.jpg"  # Chosen static image for avatar
AVATAR_VIDEO = "temp/sadtaker_out.mp4"
#AVATAR_VIDEO = "temp/wav2lip_out.mp4"
FINAL_VIDEO = "final_output.mp4"
BACKGROUND_VIDEO = "output_video.mp4"
UPDATED_BACKGROUND = "temp/output_video_updt.mp4"
# Step 1: Generate the main video using your existing script
#generate_video(INPUT_TEXT)
AVATAR_WITHOUT_WHITEBG = "temp/avatar_transparent.mp4"



# Step : Use SadTalker to Add Facial Expressions
sadtalker_command = [
    "python", f"{SADTALKER_PATH}/inference.py",
    "--driven_audio", TTS_AUDIO,
    "--source_image", INPUT_IMAGE,
    "--checkpoint_dir", f"{SADTALKER_PATH}/checkpoints",
    "--output_video", AVATAR_VIDEO
]
subprocess.run(sadtalker_command)


# Step 1: Fix video dimensions for the background video
ffmpeg_command = [
    "ffmpeg", "-i", BACKGROUND_VIDEO, "-vf", "scale=ceil(iw/2)*2:ceil(ih/2)*2",
    "-c:v", "libx264", "-crf", "18", "-preset", "ultrafast", "-y", UPDATED_BACKGROUND
]

print("Fixing background video dimensions...")
subprocess.run(ffmpeg_command, check=True)

# Step 2: Remove the green background from the avatar video
# ffmpeg_command = [
#     "ffmpeg", "-i", AVATAR_VIDEO,
#     "-vf", "chromakey=0xFFFFFF:0.1:0.2",  # Remove green background (0xFFFFFF is the hex for green)
#     "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-preset", "ultrafast", "-y", AVATAR_WITHOUT_WHITEBG
# ]

print("Removing green background from avatar video...")
subprocess.run(ffmpeg_command, check=True)

# Step 3: Overlay the transparent avatar video onto the background video
ffmpeg_command = [
    "ffmpeg", "-i", UPDATED_BACKGROUND, "-i", AVATAR_VIDEO,
    "-filter_complex", "[1:v]scale=416:416[avatar];[0:v][avatar] overlay=W-w:H-h:format=auto",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
    "-map", "0:a",  # Keep only the main video’s audio
    "-y", FINAL_VIDEO
]

print("Merging avatar video onto background...")
subprocess.run(ffmpeg_command, check=True)

print(f"✅ Final video saved as {FINAL_VIDEO}")

