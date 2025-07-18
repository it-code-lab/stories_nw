import os
import subprocess

# DND-Working 
def add_gif_overlays_to_videos(
    input_folder="edit_vid_input",
    output_folder="edit_vid_output",
    add_petal_overlay=True,
    add_sparkle_overlay=True,
    overlay_position=(0, 0)
):
    print("✅ Received Arguments:", locals())

    petal_gif_path = "overlays/petals.gif"
    sparkle_gif_path = "overlays/sparkles.gif"

    clear_folder(output_folder)

    for filename in os.listdir(input_folder):
        if filename.lower().endswith(".mp4"):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            # Prepare input list: always start with base video
            inputs = ['-i', input_path]
            stream_args = []

            filter_complex = ""
            label = "[base]"
            overlay_idx = 1  # starts from 1 because main video is [0:v]

            filter_complex += "[0:v]null[base];"

            if add_petal_overlay and os.path.exists(petal_gif_path):
                stream_args += ['-stream_loop', '-1', '-i', petal_gif_path]
                filter_complex += f"{label}[{overlay_idx}:v]overlay={overlay_position[0]}:{overlay_position[1]}[tmp{overlay_idx}];"
                label = f"[tmp{overlay_idx}]"
                overlay_idx += 1

            if add_sparkle_overlay and os.path.exists(sparkle_gif_path):
                stream_args += ['-stream_loop', '-1', '-i', sparkle_gif_path]
                filter_complex += f"{label}[{overlay_idx}:v]overlay={overlay_position[0]}:{overlay_position[1]}[outv];"
            else:
                filter_complex += f"{label}copy[outv];"

            ffmpeg_cmd = ['ffmpeg', '-y'] + inputs + stream_args + [
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '0:a?',  # Audio from main video
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                '-preset', 'ultrafast',
                '-crf', '23',
                output_path
            ]

            print(f"🎬 Processing: {filename}")
            subprocess.run(ffmpeg_cmd, check=True)
            print(f"✅ Done: {filename}")
            os.remove(input_path)

def clear_folder(folder_path, extensions=None):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    for file in os.listdir(folder_path):
        full_path = os.path.join(folder_path, file)
        if os.path.isfile(full_path):
            if not extensions or file.lower().endswith(extensions):
                os.remove(full_path)


if __name__ == '__main__':
    add_gif_overlays_to_videos(
        input_folder="edit_vid_input",
        output_folder="edit_vid_output",
        add_petal_overlay=True,
        add_sparkle_overlay=True,
        overlay_position=(0, 0)
    )



