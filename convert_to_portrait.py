import subprocess
import json
import os

def convert_landscape_to_portrait(input_path, output_path, portrait_width=1080, portrait_height=1920,
                  max_duration=180, trim_to=176):
    """
    Converts landscape videos to portrait by cropping sides and trims to 'trim_to' seconds
    if duration exceeds 'max_duration'.

    Args:
        input_path (str): Path to the input video.
        output_path (str): Path for processed video.
        portrait_width (int): Target width (default 1080).
        portrait_height (int): Target height (default 1920).
        max_duration (int): Duration threshold (default 180 seconds).
        trim_to (int): Trim target if over limit (default 176 seconds).
    """
    try:
        # Step 1️⃣: Get video info (width, height, duration)
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-show_entries", "format=duration",
                "-of", "json",
                input_path
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        info = json.loads(result.stdout)
        video_stream = info.get("streams", [{}])[0]
        duration = float(info["format"]["duration"])
        width = video_stream.get("width", 0)
        height = video_stream.get("height", 0)

        print(f"🎥 Video info: {width}x{height}, duration {duration:.2f}s")

        # Step 2️⃣: Decide if trimming is needed
        trim_flag = duration > max_duration

        # Step 3️⃣: Build FFmpeg filters
        vf_filters = []

        # Crop only if landscape
        if width > height:
            print("📐 Detected landscape — applying center crop to portrait.")
            crop_filter = f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale={portrait_width}:{portrait_height}"
            vf_filters.append(crop_filter)
        else:
            print("📱 Detected portrait — keeping original orientation.")

        # Combine filters
        vf_filter_str = ",".join(vf_filters) if vf_filters else "scale={}:{}".format(portrait_width, portrait_height)

        # Step 4️⃣: Build FFmpeg command
        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", vf_filter_str,
            "-c:a", "copy"
        ]

        # Add trimming if required
        if trim_flag:
            command.extend(["-t", str(trim_to)])
            print(f"⏱️ Trimming to {trim_to}s (was {duration:.2f}s)")

        # Add output
        command.append(output_path)

        # Step 5️⃣: Run FFmpeg
        subprocess.run(command, check=True)
        print(f"✅ Processed video saved as: {output_path}")

    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg failed with code {e.returncode}")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")

# Example usage:
# convert_landscape_to_portrait("input.mp4", "output_portrait.mp4")
