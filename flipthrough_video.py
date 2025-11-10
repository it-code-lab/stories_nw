# flipthrough_video.py

import subprocess
from pathlib import Path
from typing import List

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class FlipThroughError(Exception):
    pass


def collect_images_for_flip(base_dir: Path, folder: str) -> List[Path]:
    """
    Prefer processed_images if present, otherwise use images directly under folder.
    Returns a sorted list of image paths.
    """
    folder = (folder or "").strip().strip("/\\")
    if not folder:
        raise FlipThroughError("Folder name is empty.")

    base = base_dir.resolve()
    raw_dir = (base / folder).resolve()

    if not str(raw_dir).startswith(str(base)) or not raw_dir.is_dir():
        raise FlipThroughError(f"Folder not found or invalid: {folder}")

    # Prefer processed_images
    processed_dir = raw_dir / "processed_images"
    src_dir = processed_dir if processed_dir.is_dir() else raw_dir

    images = [
        p for p in sorted(src_dir.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]

    if not images:
        raise FlipThroughError(f"No images found in: {src_dir}")

    return images


def generate_flipthrough_video(
    base_dir: Path,
    folder: str,
    out_name: str = "flip_preview.mp4",
    seconds_per_image: float = 0.5,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
) -> Path:
    """
    Create a simple flip-through video from images in downloads/<folder>/[processed_images].
    - Uses concat demuxer so each image shows for `seconds_per_image`.
    - Centers images with padding on a fixed canvas (e.g. 1920x1080).
    - Silent video (you can layer audio later if needed).

    Returns: Path to generated MP4.
    """
    images = collect_images_for_flip(base_dir, folder)
    base = base_dir.resolve()
    folder = folder.strip().strip("/\\")
    out_dir = (base / folder).resolve()
    if not str(out_dir).startswith(str(base)):
        raise FlipThroughError("Invalid output path")

    out_path = out_dir / out_name

    # Build concat list file in a safe temp-style location (inside folder)
    list_path = out_dir / "_flip_list.txt"
    with list_path.open("w", encoding="utf-8") as f:
        for img in images:
            # Use absolute paths; -safe 0 allows this.
            f.write(f"file '{img.as_posix()}'\n")
            f.write(f"duration {seconds_per_image}\n")
        # FFmpeg concat: last image needs file line without duration for proper ending
        f.write(f"file '{images[-1].as_posix()}'\n")

    # FFmpeg command:
    # - concat images
    # - scale to fit within WxH preserving aspect
    # - pad with white background to full WxH
    vf = (
        f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white"
    )

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
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise FlipThroughError(f"ffmpeg failed: {e.stderr.decode(errors='ignore')[:400]}") from e
    finally:
        # Clean up list file
        try:
            list_path.unlink(missing_ok=True)
        except Exception:
            pass

    if not out_path.is_file():
        raise FlipThroughError("Flip-through video was not created.")

    return out_path
