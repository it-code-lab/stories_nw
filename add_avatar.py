import subprocess
# --- TorchVision shim for older basicsr expecting functional_tensor ---
import sys, types
try:
    # Old path used by basicsr
    from torchvision.transforms.functional_tensor import rgb_to_grayscale  # noqa: F401
except Exception:
    # Create a compatibility module that basicsr can import
    import torchvision.transforms.functional as F
    sys.modules.setdefault(
        'torchvision.transforms.functional_tensor',
        types.SimpleNamespace(rgb_to_grayscale=F.rgb_to_grayscale)
    )
# ----------------------------------------------------------------------

import gfpgan

import gfpgan
from moviepy.editor import VideoFileClip
from concurrent.futures import ThreadPoolExecutor

from caption_generator import extract_audio

# Paths for AI avatar generation
WAV2LIP_PATH = "Wav2Lip"
SADTALKER_PATH = "SadTalker"
TTS_AUDIO = "temp/audio.wav"
SADTALKER_OUT_DIR = "temp"
AVATAR_VIDEO = "temp/sadtalker_out.mp4"
FINAL_VIDEO = "temp/clip_with_avatar.mp4"
UPDATED_BACKGROUND = "temp/output_video_updt.mp4"
AVATAR_WITHOUT_WHITEBG = "temp/avatar_transparent.mp4"

def run_subprocess(command):
    print(f"Running command: {' '.join(command)}")
    subprocess.run(command, check=True)

def create_avatar_video(BACKGROUND_VIDEO = "temp/video_b4_adding_avatar.mp4", avatar = "Male"):

    INPUT_IMAGE = f"Avatar_4_SadTalker/avatar_{avatar}.jpg"

    # Step : Use SadTalker to Add Facial Expressions
    sadtalker_command = [
        r"C:/0.data/4.SM-WSpace/6B.Python/1.Create_Video_From_Readernook_Story/application/venv/Scripts/python.exe", f"{SADTALKER_PATH}/inference.py",
        "--driven_audio", TTS_AUDIO,
        "--source_image", INPUT_IMAGE,
        "--enhancer", "gfpgan",
        "--checkpoint_dir", f"{SADTALKER_PATH}/checkpoints",
        "--result_dir", SADTALKER_OUT_DIR, # code change done to store file name as sadtalker_out.mp4 
        "--still"  # Prevents aggressive movement
    ]

    print("SadTalker command:", sadtalker_command)
    subprocess.run(sadtalker_command)

    # Step 1: Fix video dimensions for the background video
    ffmpeg_command_1 = [
        "ffmpeg", "-i", BACKGROUND_VIDEO, "-vf", "scale=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v", "libx264", "-crf", "18", "-preset", "ultrafast", "-y", UPDATED_BACKGROUND
    ]

    # Step 2: Remove the green background from the avatar video
    ffmpeg_command_2 = [
        "ffmpeg", "-i", AVATAR_VIDEO,
        "-vf", "chromakey=0x008000:0.15:0.05",  # Adjust tolerance if needed
        "-c:v", "png",  # Use PNG for alpha support
        "-y", AVATAR_WITHOUT_WHITEBG
    ]

    # Run the FFmpeg commands in parallel
    with ThreadPoolExecutor() as executor:
        executor.submit(run_subprocess, ffmpeg_command_1)
        executor.submit(run_subprocess, ffmpeg_command_2)

    # Step 3: Overlay the transparent avatar onto the background video
    ffmpeg_command_3 = [
        "ffmpeg", "-i", UPDATED_BACKGROUND,
        "-i", AVATAR_WITHOUT_WHITEBG,
        "-filter_complex", "[1:v]scale=256:256[avatar];[0:v][avatar] overlay=W-w:0:format=auto", # position top right
        "-c:v", "libx264",  # Or your preferred output codec
        "-preset", "ultrafast",
        "-crf", "18",  # Adjust CRF for quality
        "-map", "0:a",  # Keep audio from background video
        "-y", FINAL_VIDEO
    ]

    #DND - For bottom right avatar position
    #"-filter_complex", "[1:v]scale=256:256[avatar];[0:v][avatar] overlay=W-w:H-h:format=auto",

    #DND - For top right avatar position
    #"-filter_complex", "[1:v]scale=256:256[avatar];[0:v][avatar] overlay=W-w:0:format=auto", # position top right

    print("Merging avatar video onto background...")
    subprocess.run(ffmpeg_command_3, check=True)

    print(f"✅ Final video saved as {FINAL_VIDEO}")
    # Return the final video clip with audio using MoviePy
    return VideoFileClip(FINAL_VIDEO)


def create_avatar_video_from_ref(REFERENCE_VIDEO = "Avatar_4_SadTalker/reference_video.mp4", avatar = "Male"):

    INPUT_IMAGE = f"Avatar_4_SadTalker/avatar_{avatar}.jpg"

    # Step : Use SadTalker to Add Facial Expressions
    sadtalker_command = [
        r"C:/0.data/4.SM-WSpace/6B.Python/1.Create_Video_From_Readernook_Story/application/venv/Scripts/python.exe", f"{SADTALKER_PATH}/inference.py",
        "--source_image", INPUT_IMAGE,
        "--driven_audio", "Avatar_4_SadTalker/audio.wav",
        "--ref_pose", REFERENCE_VIDEO,
        "--enhancer", "gfpgan",
        "--checkpoint_dir", f"{SADTALKER_PATH}/checkpoints",
        "--result_dir", SADTALKER_OUT_DIR
    ]

    print("SadTalker command:", sadtalker_command)
    subprocess.run(sadtalker_command)


# Example Usage
if __name__ == "__main__":
    avatar = "Krishna"
    temp_audio_path = "temp/audio.wav"
    temp_output_path = "temp/video_b4_adding_avatar.mp4"
    input_video_path="composed_video.mp4"

    # ✅ Convert string to VideoFileClip and save with desired FPS
    clip = VideoFileClip(input_video_path)
    clip.write_videofile(temp_output_path, fps=24)

    extract_audio(temp_output_path, temp_audio_path)
    video_with_audio  = create_avatar_video(temp_output_path, avatar)

    #create_avatar_video("temp/video_b4_adding_avatar.mp4", avatar)

    #create_avatar_video("temp/video_b4_adding_avatar.mp4", "feMale")
    #create_avatar_video_from_ref( "Avatar_4_SadTalker/reference_video.mp4",  "Male")