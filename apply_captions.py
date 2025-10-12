import subprocess

def add_captions_to_video(input_path, captions_path, output_path):
    """
    Applies ASS subtitles to a video using FFmpeg.

    Args:
        input_path (str): Path to the input video file (e.g. "input.mp4")
        captions_path (str): Path to the .ass captions file (e.g. "captions.ass")
        output_path (str): Path to save the output video (e.g. "out.mp4")
    """
    try:
        command = [
            "ffmpeg",
            "-y",  
            "-i", input_path,
            "-vf", f"ass={captions_path}",
            "-c:a", "copy",
            output_path
        ]
        subprocess.run(command, check=True)
        print(f"✅ Captions added successfully! Output saved as: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg failed with error code {e.returncode}")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")

# Example usage:
# add_captions_to_video("input.mp4", "captions.ass", "out.mp4")
