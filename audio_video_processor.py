import os
import subprocess
from pydub import AudioSegment
from PIL import Image

# Resize and Crop Logic
def resize_and_crop_image(image_path, target_size):
    """
    Resize and crop an image to the target size without stretching or squeezing.
    - Resizes the image to double its size first to increase resolution.
    - Crops the image to fit the target size while maintaining the aspect ratio.
    """
    try:
        if not isinstance(target_size, (tuple, list)) or len(target_size) != 2:
            raise ValueError(f"Invalid target size: {target_size}. Expected a tuple (width, height).")

        target_width, target_height = target_size
        
        with Image.open(image_path) as img:
            # Double the image size
            new_size = (img.width * 2, img.height * 2)
            img_resized = img.resize(new_size, Image.LANCZOS)
            
            # Calculate the aspect ratios
            img_ratio = new_size[0] / new_size[1]
            target_ratio = target_width / target_height

            # Center-crop the image
            if img_ratio > target_ratio:
                # Image is wider than the target size
                new_width = int(target_height * img_ratio)
                crop_x = (new_width - target_width) // 2
                img_cropped = img_resized.crop((crop_x, 0, crop_x + target_width, target_height))
            else:
                # Image is taller than the target size
                new_height = int(target_width / img_ratio)
                crop_y = (new_height - target_height) // 2
                img_cropped = img_resized.crop((0, crop_y, target_width, crop_y + target_height))

            # Save the cropped image
            img_cropped.save(image_path)
            print(f"Processed {image_path} to {target_size}")
    except Exception as e:
        print(f"Error processing image {image_path}: {str(e)}")

# Video Creation Logic
def create_video(audio_files, image_files, target_size, background_music, output_file="final_video.mp4"):
    """
    Creates a video from audio files, images, and background music.

    Args:
        audio_files (list): List of audio file paths.
        image_files (list): List of image file paths.
        target_size (tuple): Target video size (width, height).
        background_music (str): Background music file path.
        output_file (str): Output video file path.
    """
    buffer_seconds = 3

    if len(audio_files) != len(image_files):
        raise ValueError("Mismatch between audio and image counts")

    # Calculate total audio duration with buffer
    total_audio_duration = sum(AudioSegment.from_file(audio).duration_seconds for audio in audio_files) + buffer_seconds
    formatted_duration = f"{int(total_audio_duration // 60):02}:{int(total_audio_duration % 60):02}"

    # Prepare FFmpeg input list
    input_list = "ffmpeg_input.txt"
    with open(input_list, "w") as f:
        for audio, image in zip(audio_files, image_files):
            duration = AudioSegment.from_file(audio).duration_seconds
            f.write(f"file '{image}'\n")
            f.write(f"duration {duration}\n")
        f.write(f"file '{image_files[-1]}'\n")
        f.write(f"duration {buffer_seconds}\n")

    # Delete old video file if exists
    if os.path.exists(output_file):
        os.remove(output_file)
        print(f"Deleted old file: {output_file}")

    # FFmpeg command to create video
    ffmpeg_command = [
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", input_list,  # Images
        "-i", "concat:" + "|".join(audio_files),                   # Voice-over
        "-i", background_music,                                    # Background music
        "-filter_complex", (
            "[1:a]volume=1.5[a1];"                                 # Boost voice-over volume
            "[2:a]volume=0.5[a2];"                                # Lower background music volume
            "[a1][a2]amix=inputs=2:duration=first[aout];"         # Mix audio
            "[aout]dynaudnorm=f=150[gain];"                      # Normalize audio output
            "[0:v]scale=ceil(iw/2)*2:ceil(ih/2)*2[vout]"  # Correct image scaling
        ),
        "-map", "[vout]", "-map", "[gain]",                      # Use processed audio & video
        "-c:v", "libx264", "-c:a", "aac",                       # Codec settings
        "-shortest", "-t", formatted_duration, output_file      # Final output
    ]

    # Execute FFmpeg command
    subprocess.run(ffmpeg_command, check=True)

    # Clean up input list
    os.remove(input_list)
    #print(f"Video created: {output_file}, Duration: {formatted_duration}")
    # Return the output file path
    return output_file