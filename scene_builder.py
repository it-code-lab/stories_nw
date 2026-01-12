import json
import subprocess
from pathlib import Path

def run(cmd: list[str]):
    print("RUN:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def probe_duration(path: Path) -> float:
    # ffprobe duration
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    out = subprocess.check_output(cmd).decode("utf-8").strip()
    return float(out)

def make_scene(asset: Path, duration: float, out_path: Path, out_res: str, fps: int = 30):
    w, h = out_res.split("x")

    if asset.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
        # image -> loop for duration
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(asset),
            "-t", f"{duration:.3f}",
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
            "-r", str(fps),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out_path)
        ]
        run(cmd)
        return

    # video -> hold last frame if shorter
    dur_src = probe_duration(asset)
    stop_extra = max(0.0, duration - dur_src)

    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if stop_extra > 0.001:
        vf = vf + f",tpad=stop_mode=clone:stop_duration={stop_extra:.3f}"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(asset),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-r", str(fps),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path)
    ]
    run(cmd)

def concat_scenes(scene_paths: list[Path], out_path: Path):
    lst = out_path.parent / "scenes.txt"
    lst.write_text("\n".join([f"file '{p.as_posix()}'" for p in scene_paths]), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out_path)]
    run(cmd)

def probe_resolution(path: Path) -> tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        str(path)
    ]
    out = subprocess.check_output(cmd).decode("utf-8").strip()
    w, h = map(int, out.split("x"))
    return w, h

def merge_with_heygen(background: Path, heygen: Path, out_path: Path, chroma_key_hex: str | None = None, scaled_layout: bool = True):
    # Dynamic settings based on orientation

    # Detect resolution automatically
    w, h = probe_resolution(heygen)
    is_portrait = h > w

    if is_portrait:
        res = "1080:1920"
        # Background video scales to full width, placed at top
        vid_w = "iw"
        overlay_pos = "0:200" # Shifted down slightly from the very top
        border_cfg = "white@0.0" # Usually no border looks better in portrait stacks
        office_img = "images/heygen_avtar_bg_port.png" 
    else:
        res = "1920:1080"
        vid_w = "iw*0.65"
        overlay_pos = "W-w-60:60" # Top right
        border_cfg = "white@0.9"
        office_img = "images/heygen_avtar_bg_landscape.png" 

    # Audio Filter Chain: 
    # 1. loudnorm: Normalizes to -16 LUFS (industry standard)
    # 2. volume: Optional extra boost (1.2 = +20%) to ensure it's punchy
    audio_filt = "loudnorm=I=-16:TP=-1.5:LRA=11,volume=1.2"

    if chroma_key_hex:
        # Replace HeyGen background (if HeyGen exported with solid chroma key color)
        # Captions/Avatar remain unchanged because we DON'T scale HeyGen layer.

        # filt = (
        #     f"[1:v]colorkey={chroma_key_hex}:0.18:0.08,format=rgba[fg];"
        #     f"[0:v][fg]overlay=0:0:format=auto[v]"
        # )
        filt = (
            # 1. Prepare Content Video
            f"[0:v]scale={vid_w}:-1,pad=iw+12:ih+12:6:6:{border_cfg}[vid_framed];"
            
            # # 2. Prepare Studio Background (Office)
            # f"[2:v]scale={res}:force_original_aspect_ratio=increase,crop={res},boxblur=15[studio];"

            # Simplified: Scale to fill screen and crop excess, but no extra blur
            f"[2:v]scale={res.replace(':', 'x')}:force_original_aspect_ratio=increase,crop={res}[studio];"

            # 3. Key the Avatar
            f"[1:v]colorkey={chroma_key_hex}:0.14:0.06,format=rgba,despill=green:0.8[avatar];"
            
            # 4. Final Composition
            f"[studio][vid_framed]overlay={overlay_pos}[temp];"
            f"[temp][avatar]overlay=0:H-h:format=auto[v]" # Avatar anchored to bottom
        )

        

        cmd = [
            "ffmpeg", "-y",
            "-i", str(background),
            "-i", str(heygen),
            "-i", office_img, 
            "-filter_complex", filt if scaled_layout else "[1:v]colorkey=...[v]",
            "-map", "[v]",
            "-map", "1:a?",           # Select audio from HeyGen video
            "-af", audio_filt,        # Apply the normalization and boost
            "-c:v", "libx264", 
            "-crf", "18", 
            "-preset", "veryfast",
            "-c:a", "aac", 
            "-b:a", "192k",
            "-shortest",
            str(out_path)
        ]
        run(cmd)
        return

    # Simple overlay (keeps everything in HeyGen untouched; background fills behind if HeyGen has transparency via keying)
    # If HeyGen has its own background and you DON'T key it, it will cover the background.
    cmd = [
        "ffmpeg", "-y",
        "-i", str(background),
        "-i", str(heygen),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]",
        "-map", "1:a?",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path)
    ]
    run(cmd)

def render_background_and_merge(timeline_json_path: Path, base_dir: Path, heygen_path: Path, out_dir: Path, out_res: str, out_filename: str | None = None):
    tl = json.loads(timeline_json_path.read_text(encoding="utf-8"))
    blocks = tl.get("blocks", [])
    if not blocks:
        raise ValueError("No media blocks found. Insert at least one image/video and Save Timeline.")

    uploads_dir = base_dir / "uploads"
    work_dir = out_dir / "work"
    work_dir.mkdir(exist_ok=True)

    scenes = []
    for i, b in enumerate(blocks):
        start = float(b["start"])
        end = float(b["end"])
        dur = max(0.05, end - start)
        src = b["src"]  # "/uploads/xxxx.ext"
        asset = (base_dir / src.lstrip("/")).resolve()
        if not asset.exists():
            raise FileNotFoundError(f"Missing asset: {asset}")

        out_scene = work_dir / f"scene_{i:03d}.mp4"
        make_scene(asset=asset, duration=dur, out_path=out_scene, out_res=out_res)
        scenes.append(out_scene)

    background = out_dir / "background.mp4"
    concat_scenes(scenes, background)

    # final_out = out_dir / "final.mp4"

    if out_filename:
        final_out = out_dir / out_filename
    else:
        final_out = out_dir / "final.mp4"

    # If you export HeyGen with solid green background, set chroma key to "0x00FF00".
    # Otherwise leave None (but note: without keying, HeyGen’s background will cover yours).
    chroma_key = "0x00FF00"  # change to None if you are NOT using chroma bg in HeyGen
    merge_with_heygen(background=background, heygen=heygen_path, out_path=final_out, chroma_key_hex=chroma_key)

    return final_out
