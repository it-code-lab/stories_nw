import json
import subprocess
from pathlib import Path
from typing import Tuple

def _parse_hex_color(color: str) -> Tuple[int, int, int]:
    s = color.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        raise ValueError(f"Invalid color hex: {color}")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return r, g, b

def detect_chroma_by_green_ratio(
    video: Path,
    chroma_hex: str = "0x00FF00",
    *,
    ratio_threshold: float = 0.12,
    dist_threshold: int = 70,
    min_g: int = 180,
    max_r: int = 90,
    max_b: int = 90,
    sample_scale: tuple[int, int] = (160, 90),
    sample_window_s: float = 2.0,
    frames_per_window: int = 4,
) -> tuple[bool, float]:
    """
    Heuristic detection: sample a few short windows and estimate how much of the frame is near #00FF00.
    Returns (has_chroma, green_ratio).
    """
    try:
        dur = probe_duration(video)
    except Exception:
        dur = 0.0

    offsets = [0.0]
    if dur > 1.0:
        half = sample_window_s / 2.0
        offsets = [
            0.0,
            max(0.0, dur * 0.33 - half),
            max(0.0, dur * 0.66 - half),
        ]
        offsets = [min(o, max(0.0, dur - sample_window_s)) for o in offsets]

    target_r, target_g, target_b = _parse_hex_color(chroma_hex)
    w, h = sample_scale
    max_frames = max(1, int(frames_per_window))

    total_green = 0
    total_px = 0

    try:
        import numpy as np  # optional fast path
        have_np = True
    except Exception:
        have_np = False

    for ss in offsets:
        fps = max_frames / max(sample_window_s, 0.1)
        cmd = [
            "ffmpeg", "-v", "error",
            "-ss", f"{ss:.3f}",
            "-t", f"{sample_window_s:.3f}",
            "-i", str(video),
            "-vf", f"fps={fps:.6f},scale={w}:{h},format=rgb24",
            "-frames:v", str(max_frames),
            "-pix_fmt", "rgb24",
            "-f", "rawvideo",
            "pipe:1",
        ]
        try:
            raw = subprocess.check_output(cmd)
        except Exception:
            continue

        frame_size = w * h * 3
        n_frames = len(raw) // frame_size
        if n_frames <= 0:
            continue

        if have_np:
            import numpy as np
            arr = np.frombuffer(raw[: n_frames * frame_size], dtype=np.uint8)

            # arr = arr.reshape((n_frames, h, w, 3)).astype(np.int16)  # R,G,B
            # r = arr[..., 0]
            # g = arr[..., 1]
            # b = arr[..., 2]
            # dist_sq = (r - target_r) ** 2 + (g - target_g) ** 2 + (b - target_b) ** 2

            arr = arr.reshape((n_frames, h, w, 3)).astype(np.int16)  # R,G,B
            r = arr[..., 0].astype(np.int32)
            g = arr[..., 1].astype(np.int32)
            b = arr[..., 2].astype(np.int32)
            dr = r - target_r
            dg = g - target_g
            db = b - target_b
            dist_sq = dr*dr + dg*dg + db*db

            mask = (dist_sq <= (dist_threshold ** 2)) | ((g >= min_g) & (r <= max_r) & (b <= max_b))
            total_green += int(mask.sum())
            total_px += int(mask.size)
        else:
            green = 0
            px = n_frames * w * h
            data = raw[: n_frames * frame_size]
            for i in range(0, len(data), 3):
                rr = data[i]
                gg = data[i + 1]
                bb = data[i + 2]
                if (abs(rr - target_r) + abs(gg - target_g) + abs(bb - target_b) <= dist_threshold) or (gg >= min_g and rr <= max_r and bb <= max_b):
                    green += 1
            total_green += green
            total_px += px

    if total_px == 0:
        return False, 0.0

    ratio = total_green / total_px
    return (ratio >= ratio_threshold), ratio


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

def probe_has_audio(path: Path) -> bool:
    """
    Returns True if the file has at least one audio stream.
    (Avoids ffmpeg errors when applying -af but there is no audio.)
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        str(path),
    ]
    try:
        out = subprocess.check_output(cmd).decode("utf-8").strip()
        return bool(out)
    except Exception:
        return False
    
def merge_with_heygen(
    background: Path,
    heygen: Path,
    out_path: Path,
    chroma_key_hex: str | None = None,
    scaled_layout: bool = True,
    *,
    auto_detect_chroma: bool = False,
    chroma_detect_hex: str = "0x00FF00",
    chroma_ratio_threshold: float = 0.12,
):
    """
    Modes:
      - If chroma is used in HeyGen: key avatar/captions and composite over office_img.
      - If chroma is NOT used: keep HeyGen untouched and put `background` as PiP (scene-in-scene).
    """

    w, h = probe_resolution(heygen)
    is_portrait = h > w

    if is_portrait:
        res = "1080:1920"
        content_w_chroma = "iw"
        content_w_pip = "iw*0.96"
        overlay_pos = "0:200"
        overlay_pos_chroma = "0:200"
        overlay_pos_pip = "0:200"
        border_cfg = "white@0.0"
        office_img = "images/heygen_avtar_bg_port.png"
    else:
        res = "1920:1080"
        content_w_chroma = "iw*0.65"
        content_w_pip = "iw*0.55"
        # overlay_pos = "W-w-60:60"
        overlay_pos_chroma = "W-w-60:60" # keep as-is for chroma layout
        overlay_pos_pip    = "W-w-10:10" # move PiP more to the right
        border_cfg = "white@0.9"
        office_img = "images/heygen_avtar_bg_landscape.png"

    audio_filt = "loudnorm=I=-16:TP=-1.5:LRA=11,volume=1.2"
    heygen_has_audio = probe_has_audio(heygen)

    # Auto-detect chroma if requested (and if not explicitly provided)
    if auto_detect_chroma and not chroma_key_hex:
        has_key, ratio = detect_chroma_by_green_ratio(
            heygen,
            chroma_hex=chroma_detect_hex,
            ratio_threshold=chroma_ratio_threshold,
        )
        print(f"CHROMA_DETECT {heygen.name}: has_key={has_key} green_ratio={ratio:.3f}")
        if has_key:
            chroma_key_hex = chroma_detect_hex
            scaled_layout = False  # use chroma layout
        else:
            scaled_layout = True  # force PiP mode if no chroma detected

    # ---------------------------------------------------------
    # NON-CHROMA MODE  missing background => use HeyGen only
    # (still apply audio enhancement if audio exists)
    # ---------------------------------------------------------
    if not chroma_key_hex and (not background.exists()):
        print(f"NON_CHROMA: background missing, using HeyGen only: {background}")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(heygen),
            "-map", "0:v:0",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        ]
        if heygen_has_audio:
            cmd += [
                "-map", "0:a?",
                "-af", audio_filt,
                "-c:a", "aac", "-b:a", "192k",
            ]
        cmd += [
            "-shortest",
            str(out_path),
        ]
        run(cmd)
        return
    
    # --------------------------
    # CHROMA MODE → use office_img
    # --------------------------
    if chroma_key_hex:
        filt = (
            f"[0:v]scale={content_w_chroma}:-1,pad=iw+12:ih+12:6:6:{border_cfg}[vid_framed];"
            f"[2:v]scale={res.replace(':', 'x')}:force_original_aspect_ratio=increase,crop={res}[studio];"
            f"[1:v]colorkey={chroma_key_hex}:0.14:0.06,format=rgba,despill=green:0.8[avatar];"
            f"[studio][vid_framed]overlay={overlay_pos_chroma}[temp];"
            f"[temp][avatar]overlay=0:H-h:format=auto[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(background),
            "-i", str(heygen),
            "-i", office_img,
            "-filter_complex", filt,
            "-map", "[v]",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        ]
        if heygen_has_audio:
            cmd += ["-map", "1:a?", "-af", audio_filt, "-c:a", "aac", "-b:a", "192k"]

        cmd += ["-shortest", str(out_path)]

        run(cmd)
        return

    # -----------------------------------------
    # NON-CHROMA MODE → NO office_img, PiP only
    # -----------------------------------------
    if scaled_layout:
        filt = (
            f"[0:v]scale={content_w_pip}:-1,pad=iw+12:ih+12:6:6:{border_cfg}[pip];"
            f"[1:v]scale={res}:force_original_aspect_ratio=increase,crop={res}[base];"
            f"[base][pip]overlay={overlay_pos_pip}:format=auto[v]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(background),
            "-i", str(heygen),
            "-filter_complex", filt,
            "-map", "[v]",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        ]
        if heygen_has_audio:
           cmd += ["-map", "1:a?", "-af", audio_filt, "-c:a", "aac", "-b:a", "192k"]

        cmd += ["-shortest", str(out_path)]

        run(cmd)
        return

    # Fallback (old behavior)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(background),
        "-i", str(heygen),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
    ]
    if heygen_has_audio:
        cmd += ["-map", "1:a?", "-af", audio_filt, "-c:a", "aac", "-b:a", "192k"]

    cmd += ["-shortest", str(out_path)]

    run(cmd)


def merge_with_heygen_working(background: Path, heygen: Path, out_path: Path, chroma_key_hex: str | None = None, scaled_layout: bool = True):
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
    # chroma_key = "0x00FF00"  # change to None if you are NOT using chroma bg in HeyGen
    chroma_key = None  # auto-detect
    # merge_with_heygen(background=background, heygen=heygen_path, out_path=final_out, chroma_key_hex=chroma_key)
    merge_with_heygen(
        background=background,
        heygen=heygen_path,
        out_path=final_out,
        chroma_key_hex=chroma_key,
        auto_detect_chroma=True,
    )
    return final_out
