import os
import subprocess
import tempfile
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga"}

def is_video_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTS

def is_audio_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in AUDIO_EXTS

def make_concat_list_file(input_path: str, repeat_factor: int) -> str:
    """
    Create a temporary concat list file with the same input repeated 'repeat_factor' times.
    Uses absolute POSIX paths so FFmpeg can resolve them correctly on Windows.
    """
    # Absolute path, POSIX-style (forward slashes) for FFmpeg concat demuxer
    abs_posix = Path(input_path).resolve(strict=False).as_posix()

    # Create temp list file in %TEMP%
    fd, list_path = tempfile.mkstemp(prefix="concat_", suffix=".txt")
    os.close(fd)

    # Each line format: file '/absolute/path'
    # Single-quote any single quotes in the path (rare on Windows, but safe)
    safe_path = abs_posix.replace("'", r"'\''")

    with open(list_path, "w", encoding="utf-8") as f:
        for _ in range(max(1, repeat_factor)):
            f.write(f"file '{safe_path}'\n")

    return list_path


def audio_codec_flags_for(ext: str):
    """
    Choose an audio codec based on the output extension.
    Returns a list of ffmpeg args like ['-c:a','libmp3lame','-b:a','192k'].
    """
    ext = ext.lower()
    if ext == ".mp3":
        return ["-c:a", "libmp3lame", "-b:a", "192k"]
    if ext in {".m4a", ".aac"}:
        return ["-c:a", "aac", "-b:a", "192k"]
    if ext == ".wav":
        return ["-c:a", "pcm_s16le"]
    if ext == ".flac":
        return ["-c:a", "flac"]
    if ext in {".ogg", ".oga"}:
        return ["-c:a", "libvorbis", "-q:a", "5"]  # VBR ~160kbps
    # default fallback
    return ["-c:a", "aac", "-b:a", "192k"]

def repeat_single_source_fast(input_path: str, output_path: str, repeat_factor: int):
    """
    Repeat one clip N times using stream copy (no re-encode).
    Works perfectly for your 'one file at a time' scenario.
    """
    if repeat_factor < 1:
        raise ValueError("repeat_factor must be >= 1")

    if repeat_factor == 1:
        # Just copy
        subprocess.run([
            "ffmpeg", "-y",
            "-i", input_path,
            "-c", "copy",
            output_path
        ], check=True)
        return

    loop_count = repeat_factor - 1  # total = 1 + loop_count

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", str(loop_count),
        "-i", input_path,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    print("▶", " ".join(cmd))
    subprocess.run(cmd, check=True)

# DND-Working 
def multiply_videos(
    input_folder="edit_vid_input",
    output_folder="edit_vid_output",
    repeat_factor=1
):
    print("✅ Received Arguments:", locals())
    clear_folder(output_folder)

    for filename in os.listdir(input_folder):
        input_path = os.path.join(input_folder, filename)
        if not os.path.isfile(input_path):
            continue

        ext = Path(filename).suffix.lower()
        output_path = os.path.join(output_folder, filename)

        # VIDEO
        if is_video_file(filename):

            # Working - DDND
            # Build concat list
            # concat_list = make_concat_list_file(input_path, repeat_factor)
            try:
                # ffmpeg_cmd = [
                #     "ffmpeg", "-y",
                #     "-f", "concat",
                #     "-safe", "0",
                #     "-i", concat_list,
                #     "-c:v", "libx264",
                #     "-preset", "ultrafast",
                #     "-crf", "23",
                #     "-c:a", "aac",
                #     "-shortest",
                #     output_path,
                # ]
                # print(f"🎬 Processing video: {filename}")
                # subprocess.run(ffmpeg_cmd, check=True)
                repeat_single_source_fast(input_path, output_path, repeat_factor)
                print(f"✅ Done: {filename}")
            except OSError:
                pass
            # finally:
                #DND - Working
                # Clean temp concat list
                # try:
                #     os.remove(concat_list)
                # except OSError:
                #     pass

            # Remove original input (existing behavior)
            try:
                os.remove(input_path)
            except OSError:
                pass
            continue

        # AUDIO
        if is_audio_file(filename):
            # concat_list = make_concat_list_file(input_path, repeat_factor)
            try:
                # audio_flags = audio_codec_flags_for(ext)
                # ffmpeg_cmd = [
                #     "ffmpeg", "-y",
                #     "-f", "concat",
                #     "-safe", "0",
                #     "-i", concat_list,
                #     *audio_flags,
                #     output_path,
                # ]
                print(f"🎧 Processing audio: {filename}")
                # subprocess.run(ffmpeg_cmd, check=True)
                repeat_single_source_fast(input_path, output_path, repeat_factor)
                print(f"✅ Done: {filename}")
            except OSError:
                pass
            # finally:
            #     try:
            #         os.remove(concat_list)
            #     except OSError:
            #         pass

            # Remove original input (to match your current flow)
            try:
                os.remove(input_path)
            except OSError:
                pass
            continue

        # Non-media files ignored
        print(f"⏭️ Skipped (not audio/video): {filename}")

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
