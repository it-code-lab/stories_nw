from moviepy.editor import VideoFileClip
import subprocess
import os

def split_video(input_file, chunk_duration="02:20", output_dir="splits"):
    """
    Split the input video into multiple chunks if its duration exceeds 3 minutes.
    """
    os.makedirs(output_dir, exist_ok=True)

    split_command = [
        "ffmpeg",
        "-i", input_file,                # Input file
        "-c", "copy",                    # Copy codec without re-encoding
        "-map", "0",                     # Map all streams
        "-segment_time", chunk_duration, # Set split duration
        "-f", "segment",                 # Use segment format
        "-reset_timestamps", "1",        # Reset timestamps for each segment
        f"{output_dir}/part%03d.mp4"     # Output files pattern
    ]

    try:
        subprocess.run(split_command, check=True)
        print(f"Video split into chunks in '{output_dir}'")
    except subprocess.CalledProcessError as e:
        print(f"Error splitting video: {str(e)}")


def check_and_split_video(input_file, selected_size):
    """
    Check if the video duration exceeds 3 minutes and split if needed.
    Runs only if the user selected "YouTube Shorts".
    """
    print("Received check_and_split_video Arguments:", locals())
    if selected_size == "YouTube Shorts":
        video = VideoFileClip(input_file)
        duration_minutes = video.duration / 60

        # Split video if duration exceeds 3 minutes
        if duration_minutes > 3:
            print(f"Video duration {duration_minutes:.2f} minutes. Splitting required.")
            split_video(input_file)
        else:
            print("Video duration is under 3 minutes. No split needed.")

