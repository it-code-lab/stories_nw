import os
import subprocess
import random

def get_random_music(bg_music_folder):
    music_files = [
        os.path.join(bg_music_folder, f)
        for f in os.listdir(bg_music_folder)
        if f.lower().endswith(('.mp3', '.wav', '.aac'))
    ]
    return random.choice(music_files) if music_files else None

def clear_folder(folder_path, extensions=None):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    for file in os.listdir(folder_path):
        full_path = os.path.join(folder_path, file)
        if os.path.isfile(full_path):
            if not extensions or file.lower().endswith(extensions):
                os.remove(full_path)

def process_video(
    input_path,
    output_path,
    remove_top=50,
    remove_bottom=0,
    add_music=True,
    slow_down=True,
    slow_down_factor=2.0,
    bg_music_path=None,
    target_orientation="auto",
    add_watermark=False,
    watermark_path="logo.png",
    watermark_position="bottom-right",
    watermark_scale=0.2
):
    # Get video size
    probe_cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=s=x:p=0', input_path
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    width, height = map(int, result.stdout.strip().split('x'))

    # Detect orientation
    orientation = (
        "portrait" if height > width else "landscape"
    ) if target_orientation == "auto" else target_orientation

    filter_parts = []

    if orientation == "portrait":
        cropped_height = height - remove_top - remove_bottom
        pad_top = (height - cropped_height) // 2
        filter_parts.append(f"crop={width}:{cropped_height}:0:{remove_top}")
        filter_parts.append(f"pad={width}:{height}:0:{pad_top}")
    elif orientation == "landscape":
        if remove_top > 0 or remove_bottom > 0:
            cropped_height = height - remove_top - remove_bottom
            filter_parts.append(f"crop={width}:{cropped_height}:0:{remove_top}")
        # Could scale or pad to vertical aspect if needed

    if slow_down:
        filter_parts.append(f"setpts={slow_down_factor}*PTS")

    base_filter = ",".join(filter_parts)

    # Watermark logic
    if add_watermark and watermark_path and os.path.exists(watermark_path):
        pos = {
            "top-left": "5:5",
            "top-right": f"W-w-5:5",
            "bottom-left": f"5:H-h-5",
            "bottom-right": f"W-w-5:H-h-5"
        }.get(watermark_position, "W-w-5:H-h-5")

        filter_str = (
            f"[0:v]{base_filter}[v1];"
            f"[1:v]scale=-1:'if(gt(ih*{watermark_scale},80),80,ih*{watermark_scale})'[wm];"
            f"[v1][wm]overlay={pos}[outv]"
        )


        ffmpeg_cmd = ['ffmpeg', '-y', '-i', input_path, '-i', watermark_path]
        if add_music and bg_music_path:
            ffmpeg_cmd += ['-i', bg_music_path]

        ffmpeg_cmd += ['-filter_complex', filter_str]
        ffmpeg_cmd += ['-map', '[outv]']

        if add_music and bg_music_path:
            ffmpeg_cmd += ['-map', f"{2 if add_music else 1}:a:0"]
        else:
            ffmpeg_cmd += ['-an']
    else:
        filter_str = base_filter
        ffmpeg_cmd = ['ffmpeg', '-y', '-i', input_path]
        if add_music and bg_music_path:
            ffmpeg_cmd += ['-i', bg_music_path]
        ffmpeg_cmd += ['-filter:v', filter_str]
        ffmpeg_cmd += ['-map', '0:v:0']
        if add_music and bg_music_path:
            ffmpeg_cmd += ['-map', '1:a:0']
        else:
            ffmpeg_cmd += ['-an']

    ffmpeg_cmd += [
        '-shortest',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:a', '192k',
        output_path
    ]

    #DND - Needed for additional logging
    # ffmpeg_cmd += ['-loglevel', 'debug']

    subprocess.run(ffmpeg_cmd)
    print(f"✅ {orientation.upper()} Processed: {os.path.basename(output_path)}")

def batch_process(
    input_folder='input',
    output_folder='output',
    bg_music_folder='god_bg',
    remove_top=50,
    remove_bottom=0,
    add_music=True,
    slow_down=True,
    slow_down_factor=2.0,
    target_orientation="auto",
    add_watermark=False,
    watermark_path="logo.png",
    watermark_position="bottom-right",
    watermark_scale=0.2
):
    print("Received batch_process Arguments:", locals())
    clear_folder(output_folder)
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(".mp4"):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, f"{filename}")
            bg_music = get_random_music(bg_music_folder) if add_music else None

            process_video(
                input_path=input_path,
                output_path=output_path,
                remove_top=remove_top,
                remove_bottom=remove_bottom,
                add_music=add_music,
                slow_down=slow_down,
                slow_down_factor=slow_down_factor,
                bg_music_path=bg_music,
                target_orientation=target_orientation,
                add_watermark=add_watermark,
                watermark_path=watermark_path,
                watermark_position=watermark_position,
                watermark_scale=watermark_scale
            )
            os.remove(input_path)

# ✅ Example usage
if __name__ == '__main__':
    batch_process(
        input_folder="input",
        output_folder="output",
        bg_music_folder="god_bg",
        remove_top=50,
        remove_bottom=0,
        add_music=False,
        slow_down=True,
        slow_down_factor=2.0,
        target_orientation="auto", 
        add_watermark=True,
        watermark_path="logo.png",
        watermark_position="bottom-left",
        watermark_scale=0.15
    )

# -----------------------------------------------
# ✅ Supported Parameters for batch_process()
# -----------------------------------------------

# input_folder            : Folder path with input .mp4 videos (default: "input")
# output_folder           : Folder path for processed videos (default: "output")
# bg_music_folder         : Folder containing background music files (default: "god_bg")

# remove_top              : Number of pixels to crop from top (default: 50)
# remove_bottom           : Number of pixels to crop from bottom (default: 0)

# add_music               : True/False – add random music from bg_music_folder (default: True)
# slow_down               : True/False – slow down video playback (default: True)
# slow_down_factor        : Float – how much to slow down video (e.g., 2.0 = 2x slower) (default: 2.0)

# target_orientation      : "portrait", "landscape", or "auto" (default: "auto")
#   - "auto" detects based on width vs height
#   - "portrait" applies top/bottom crop + pad logic
#   - "landscape" applies only top/bottom crop (optionally extend later)

# add_watermark           : True/False – whether to add a watermark image (default: False)
# watermark_path          : Path to the watermark image file (e.g., "logo.png")
# watermark_position      : "top-left", "top-right", "bottom-left", "bottom-right" (default: "bottom-right")
# watermark_scale         : Float – relative width of watermark (e.g., 0.2 = 20% of video width) (default: 0.2)

