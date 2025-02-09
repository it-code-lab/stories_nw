import subprocess
from moviepy.editor import VideoFileClip
# Paths for AI avatar generation
WAV2LIP_PATH = "Wav2Lip"
SADTALKER_PATH = "SadTalker"
TTS_AUDIO = "temp/audio.wav"
SADTALKER_OUT_DIR = "temp"
#INPUT_IMAGE = "Avatar_4_SadTalker/avatar_female.jpg"  # Chosen static image for avatar
AVATAR_VIDEO = "temp/sadtalker_out.mp4"
FINAL_VIDEO = "temp/clip_with_avatar.mp4"
UPDATED_BACKGROUND = "temp/output_video_updt.mp4"
AVATAR_WITHOUT_WHITEBG = "temp/avatar_transparent.mp4"

def create_avatar_video(BACKGROUND_VIDEO = "temp/video_b4_adding_avatar.mp4", gender = "Male"):

    INPUT_IMAGE = f"Avatar_4_SadTalker/avatar_{gender}.jpg"

    # Step : Use SadTalker to Add Facial Expressions
    sadtalker_command = [
        r"C:/0.data/4.SM-WSpace/6B.Python/1.Create_Video_From_Readernook_Story/application/venv/Scripts/python.exe", f"{SADTALKER_PATH}/inference.py",
        "--driven_audio", TTS_AUDIO,
        "--source_image", INPUT_IMAGE,
        "--checkpoint_dir", f"{SADTALKER_PATH}/checkpoints",
        "--result_dir", SADTALKER_OUT_DIR # code change done to store file name as sadtalker_out.mp4 
    ]
    print("SadTalker command:", sadtalker_command)
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

    #print("Removing  background from avatar video...")
    #subprocess.run(ffmpeg_command, check=True)

    # Step 3: Overlay the avatar video onto the background video
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
    # Return the final video clip with audio using MoviePy
    return VideoFileClip(FINAL_VIDEO)

# Example Usage
if __name__ == "__main__":
    create_avatar_video("temp/video_b4_adding_avatar.mp4", "Male")