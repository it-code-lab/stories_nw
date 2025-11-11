# flipthrough_video.py

import os
import subprocess
from pathlib import Path
from typing import List

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class FlipThroughError(Exception):
    pass


def collect_images_for_flip(base_dir: Path, folder: str) -> List[Path]:
    folder = (folder or "").strip().strip("/\\")
    if not folder:
        raise FlipThroughError("Folder name is empty.")

    base = base_dir.resolve()
    raw_dir = (base / folder).resolve()

    if not str(raw_dir).startswith(str(base)) or not raw_dir.is_dir():
        raise FlipThroughError(f"Folder not found or invalid: {folder}")

    processed_dir = raw_dir / "processed_images"
    src_dir = processed_dir if processed_dir.is_dir() else raw_dir

    images = [
        p for p in sorted(src_dir.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    if not images:
        raise FlipThroughError(f"No images found in: {src_dir}")

    return images


def _pick_windows_font() -> str | None:
    """Pick a common Windows font if available (for drawtext)."""
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\ARIAL.TTF",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\SEGOEUI.TTF",
    ]
    for c in candidates:
        if Path(c).is_file():
            # ffmpeg likes forward slashes inside fontfile path
            return c.replace("\\", "/")
    return None


def generate_flipthrough_video(
    base_dir: Path,
    folder: str,
    out_name: str = "flip_preview.mp4",
    seconds_per_image: float = 0.5,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    watermark_text: str = "PREVIEW ONLY - DO NOT PRINT",
) -> Path:
    """
    Create a flip-through video:
      - uses images from downloads/<folder>/processed_images (or folder),
      - centers them on WxH white canvas,
      - overlays semi-transparent watermark_text across the center.
    """
    images = collect_images_for_flip(base_dir, folder)
    base = base_dir.resolve()
    folder = folder.strip().strip("/\\")
    out_dir = (base / folder).resolve()
    if not str(out_dir).startswith(str(base)):
        raise FlipThroughError("Invalid output path")

    out_path = out_dir / out_name

    # Build concat list file
    list_path = out_dir / "_flip_list.txt"
    with list_path.open("w", encoding="utf-8") as f:
        for img in images:
            # Use absolute paths with -safe 0, properly quoted
            f.write(f"file '{img.as_posix()}'\n")
            f.write(f"duration {seconds_per_image}\n")
        # Repeat last image once (concat demuxer requirement)
        f.write(f"file '{images[-1].as_posix()}'\n")

    # 1) Base scale + pad (white background)
    base_vf = (
        f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white"
    )

    vf = base_vf

    # 2) Add watermark overlay if requested
    if watermark_text:
        # Escape text for drawtext: escape backslashes, colons, apostrophes
        safe_text = (
            watermark_text
            .replace("\\", "\\\\")
            .replace(":", r"\:")
            .replace("'", r"\'")
        )

        fontsize = int(height * 0.09)  # relative to video height

        # Base drawtext args
        draw_args = [
            f"text='{safe_text}'",
            "fontcolor=black@0.3",
            "borderw=2",
            "bordercolor=white@0.6",
            f"fontsize={fontsize}",
            "x=(w-text_w)/2",
            "y=(h-text_h)/2",
        ]

        # Explicit font on Windows to avoid "could not find font" failures

        if os.name == "nt":
            win_font = _pick_windows_font()
            if win_font:
                # Escape ':' for ffmpeg filter syntax, and ensure forward slashes
                win_font_escaped = win_font.replace("\\", "/").replace(":", r"\:")
                draw_args.append(f"fontfile='{win_font_escaped}'")

        # On non-Windows, ffmpeg+fontconfig will pick a default font.

        draw = "drawtext=" + ":".join(draw_args)
        vf = base_vf + "," + draw

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-vf", vf,
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            # Try to give the *end* of stderr where the real error is
            err_txt = (proc.stderr or b"").decode(errors="ignore")
            tail = err_txt[-400:] if err_txt else "Unknown error"

            # If the problem is clearly drawtext, hint it
            if "drawtext" in err_txt.lower():
                raise FlipThroughError(
                    "ffmpeg drawtext/watermark failed. Details (tail): " + tail
                )
            raise FlipThroughError("ffmpeg failed. Details (tail): " + tail)
    finally:
        try:
            list_path.unlink(missing_ok=True)
        except Exception:
            pass

    if not out_path.is_file():
        raise FlipThroughError("Flip-through video was not created.")

    return out_path
