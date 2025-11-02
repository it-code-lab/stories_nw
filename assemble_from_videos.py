# assemble_from_videos.py
import os, random, math, subprocess, tempfile, json
from glob import glob
from typing import List, Dict, Tuple
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips

# --------------------------
# FFmpeg / FFprobe utilities
# --------------------------
def _bin_exists(name: str) -> bool:
    try:
        subprocess.run([name, "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def _ffprobe_stream_info(path: str) -> Dict:
    """
    Return primary video stream info as a dict:
    {codec_name, width, height, avg_frame_rate (string), pix_fmt}
    """
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,avg_frame_rate,pix_fmt",
            "-of", "json",
            path
        ], universal_newlines=True)
        data = json.loads(out)
        streams = data.get("streams", [])
        if not streams:
            return {}
        s = streams[0]
        return {
            "codec_name": s.get("codec_name"),
            "width": s.get("width"),
            "height": s.get("height"),
            "avg_frame_rate": s.get("avg_frame_rate"),
            "pix_fmt": s.get("pix_fmt"),
        }
    except Exception:
        return {}

def split_video(input_path,  max_duration=180):
    print("✅ Received split_video Arguments:", locals())

    output_dir="edit_vid_output"
    os.makedirs(output_dir, exist_ok=True)
    output_pattern = os.path.join(output_dir, "part_%02d.mp4")

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c", "copy", "-map", "0",
        "-f", "segment",
        "-segment_time", str(max_duration),
        output_pattern
    ]
    subprocess.run(cmd, check=True)
    print(f"✅ Video split into parts saved under: {output_dir}")


# assemble_from_videos.py
def convert_landscape_to_portrait(
    input_path: str,
    output_path: str,
    portrait_size: str = "1080x1920",
    focus: str = "center",            # "left" | "center" | "right"
    keep_audio: bool = True
):
    """
    Crop a landscape video to 9:16 portrait by trimming left/right edges,
    then scale to the requested resolution. Optionally keep audio.
    """
    # Parse WxH like "1080x1920"
    try:
        tw, th = portrait_size.lower().split("x")
        tw, th = int(tw), int(th)
    except Exception:
        tw, th = 1080, 1920

    # Center/left/right anchor for crop X position
    # Crop width is ih*9/16 (portrait AR) when source is landscape
    # - center: x = (iw - ih*9/16)/2
    # - left:   x = 0
    # - right:  x = (iw - ih*9/16)
    if focus == "left":
        x_expr = "0"
    elif focus == "right":
        x_expr = "iw - ih*9/16"
    else:
        x_expr = "(iw - ih*9/16)/2"

    # If source is taller-than-wide (unlikely for landscape), this still behaves,
    # but we primarily target landscape→portrait cropping.
    crop_filter = f"crop=ih*9/16:ih:{x_expr}:0"

    # Build ffmpeg cmd
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"{crop_filter},scale={tw}:{th}",
    ]

    if keep_audio:
        cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast"]

    cmd += [output_path]

    subprocess.run(cmd, check=True)
    print(f"✅ Portrait video created at: {output_path}")


def _ffprobe_duration(path: str) -> float:
    """Return duration in seconds using ffprobe (format duration)."""
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ], universal_newlines=True).strip()
        return float(out)
    except Exception:
        # MoviePy fallback (slower but robust)
        try:
            return float(VideoFileClip(path).duration)
        except Exception:
            return 0.0

def _can_safe_concat(video_paths: List[str]) -> Tuple[bool, str]:
    """
    Check if all videos share the same codec/resolution/fps/pix_fmt,
    which is required for FFmpeg concat with -c:v copy.
    """
    if not _bin_exists("ffmpeg") or not _bin_exists("ffprobe"):
        return False, "FFmpeg/FFprobe not available"

    ref = None
    for p in video_paths:
        info = _ffprobe_stream_info(p)
        if not info or not all(info.get(k) for k in ["codec_name","width","height","avg_frame_rate","pix_fmt"]):
            return False, f"Missing stream info for: {os.path.basename(p)}"

        # Normalize avg_frame_rate textual forms (e.g., "30000/1001" vs "29.97")
        afr = info["avg_frame_rate"]
        if afr and "/" in afr:
            n, d = afr.split("/")
            try:
                afr_float = float(n) / float(d) if float(d) != 0 else 0.0
            except Exception:
                afr_float = 0.0
        else:
            try:
                afr_float = float(afr)
            except Exception:
                afr_float = 0.0
        info["_afr_float"] = afr_float

        if ref is None:
            ref = info
            continue

        same = (
            info["codec_name"] == ref["codec_name"] and
            info["width"] == ref["width"] and
            info["height"] == ref["height"] and
            info["pix_fmt"] == ref["pix_fmt"] and
            abs(info["_afr_float"] - ref["_afr_float"]) < 1e-3
        )
        if not same:
            reason = (
                f"Mismatch: {os.path.basename(p)} "
                f"(codec={info['codec_name']}, size={info['width']}x{info['height']}, "
                f"fps≈{info['_afr_float']:.3f}, pix_fmt={info['pix_fmt']}) "
                f"vs ref (codec={ref['codec_name']}, size={ref['width']}x{ref['height']}, "
                f"fps≈{ref['_afr_float']:.3f}, pix_fmt={ref['pix_fmt']})"
            )
            return False, reason

    return True, "All inputs match (codec/size/fps/pix_fmt)"

# --------------------------
# Discovery helpers
# --------------------------
def _find_audio(audio_folder: str) -> str:
    audio_exts = ("*.mp3","*.wav","*.m4a","*.aac","*.flac","*.ogg")
    files = []
    for e in audio_exts:
        files.extend(glob(os.path.join(audio_folder, e)))
    if not files:
        raise RuntimeError(f"No audio file found in {audio_folder}")
    return os.path.abspath(sorted(files)[0])

def _find_videos(video_folder: str) -> List[str]:
    video_exts = ("*.mp4","*.mov","*.mkv","*.webm")
    files = []
    for e in video_exts:
        files.extend(glob(os.path.join(video_folder, e)))
    if not files:
        raise RuntimeError(f"No video files found in {video_folder}")
    return [os.path.abspath(p) for p in sorted(files)]

# --------------------------
# Main assembly
# --------------------------
def assemble_videos(
    video_folder: str,
    audio_folder: str,
    output_path: str,
    fps: int = 30,
    shuffle: bool = True,
    prefer_ffmpeg_concat: bool = True,  # will auto-fallback if not safe
):
    """
    Auto-selects FFmpeg concat (stream-copy) if safe; otherwise falls back to MoviePy.

    - Reads the *real* duration of each clip.
    - Repeats clips (loop through list) until sum >= audio duration.
    - If using MoviePy: trims the last clip exactly to fit.
    - If using FFmpeg concat: concatenates whole clips, then muxes audio with -shortest.
    """
    
    print("Received assemble_videos Arguments:", locals())
    clear_folder("edit_vid_output")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 1) Load audio + duration
    audio_path = _find_audio(audio_folder)
    audio = AudioFileClip(audio_path)
    audio_duration = float(audio.duration)

    # 2) Collect videos
    video_paths = _find_videos(video_folder)
    if shuffle:
        random.shuffle(video_paths)

    # 3) Precompute durations (skip empties)
    durations = []
    valid_paths = []
    tiny = 0.02
    for p in video_paths:
        d = _ffprobe_duration(p)
        if d > tiny:
            valid_paths.append(p)
            durations.append(d)
    if not valid_paths:
        audio.close()
        raise RuntimeError("All candidate videos are zero-length or unreadable.")

    # 4) Build a plan (path, full_duration, use_duration) to cover >= audio length
    remaining = audio_duration
    plan: List[Tuple[str, float, float]] = []
    idx = 0
    while remaining > tiny:
        p = valid_paths[idx % len(valid_paths)]
        d = durations[idx % len(durations)]
        use_d = min(d, remaining)
        plan.append((p, d, use_d))
        remaining -= use_d
        idx += 1

    # 5) Decide path: FFmpeg concat if safe and preferred, else MoviePy
    if prefer_ffmpeg_concat:
        can_concat, reason = _can_safe_concat(valid_paths)
        if can_concat:
            # ---- FFmpeg concat (no re-encode) ----
            audio.close()  # we'll remux with ffmpeg
            with tempfile.TemporaryDirectory() as td:
                list_txt = os.path.join(td, "list.txt")
                # Write whole files (concat demuxer can't trim mid-file)
                with open(list_txt, "w", encoding="utf-8") as f:
                    for (p, full_d, use_d) in plan:
                        # Always list the *entire* file
                        safe_p = p.replace("'", r"'\''")
                        f.write(f"file '{safe_p}'\n")

                # 1) Concat (video only), stream copy
                temp_concat = os.path.join(td, "concat.mp4")
                cmd_concat = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", list_txt,
                    "-c:v", "copy",
                    "-an",
                    temp_concat
                ]
                subprocess.run(cmd_concat, check=True)

                # 2) Mux audio, end at audio length
                cmd_mux = [
                    "ffmpeg", "-y",
                    "-i", temp_concat,
                    "-i", audio_path,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest",
                    output_path
                ]
                subprocess.run(cmd_mux, check=True)

            return
        else:
            print(f"[Info] Falling back to MoviePy (concat not safe): {reason}")

    # ---- MoviePy re-encode path (robust, trims last clip) ----
    clips = []
    try:
        for (p, full_d, use_d) in plan:
            c = VideoFileClip(p).without_audio()
            if use_d < (c.duration - tiny):
                c = c.subclip(0, use_d)
            clips.append(c)

        video = concatenate_videoclips(clips, method="compose")
        video = video.set_audio(audio).set_duration(audio_duration)

        video.write_videofile(
            output_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            temp_audiofile="__temp_audio.m4a",
            remove_temp=True
        )
    finally:
        for c in clips:
            try: c.close()
            except: pass
        try: audio.close()
        except: pass



def clear_folder(folder_path, extensions=None):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    for file in os.listdir(folder_path):
        full_path = os.path.join(folder_path, file)
        if os.path.isfile(full_path):
            if not extensions or file.lower().endswith(extensions):
                os.remove(full_path)

# --------------------------
# Example usage (parameters)
# --------------------------
if __name__ == "__main__":
    assemble_videos(
        video_folder="edit_vid_input",                  # or "edit_vid_output" if you pre-made KB clips
        audio_folder="edit_vid_audio",
        output_path="edit_vid_output/final_video.mp4",
        fps=30,
        shuffle=True,                                   # different order each run
        prefer_ffmpeg_concat=True                       # auto-uses concat if safe; else MoviePy
    )



# clear_folder("edit_vid_output")

# def clear_folder(folder_path, extensions=None):
#     if not os.path.exists(folder_path):
#         os.makedirs(folder_path)
#     for file in os.listdir(folder_path):
#         full_path = os.path.join(folder_path, file)
#         if os.path.isfile(full_path):
#             if not extensions or file.lower().endswith(extensions):
#                 os.remove(full_path)
