import os
import subprocess

# DND-Working 
def multiply_videos(
    input_folder="edit_vid_input",
    output_folder="edit_vid_output",
    repeat_factor=1
):
    print("✅ Received Arguments:", locals())

    clear_folder(output_folder)

    for filename in os.listdir(input_folder):
        if filename.lower().endswith(".mp4"):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-filter_complex', f"[0:v]null[base];[base]split={repeat_factor}[a][b];[a]setpts=N/FRAME_RATE/TB[a];[b]setpts=N/FRAME_RATE/TB[b];[a][b]concat=n=2:v=1:a=0[outv]",
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
    multiply_videos(
        input_folder="edit_vid_input",
        output_folder="edit_vid_output",
        repeat_factor=2
    )





