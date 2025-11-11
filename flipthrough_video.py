import os
import shutil
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


def _resolve_transition_type(base_type: str, step_index: int, alternate_direction: bool) -> str:
    """
    Resolve xfade transition name.

    - If base_type is 'slide' and alternate_direction=True:
        alternate slideleft/slideright.
    - If base_type is 'wipe' and alternate_direction=True:
        alternate wipeleft/wiperight.
    - Otherwise, return base_type as-is.
    """
    base = base_type.lower().strip()

    if not alternate_direction:
        return base

    if base == "slide":
        # step_index: 1,2,3,... -> alternate directions
        return "slideleft" if (step_index % 2) else "slideright"

    if base == "wipe":
        return "wipeleft" if (step_index % 2) else "wiperight"

    return base


def _prepare_temp_sequence(images: List[Path], out_dir: Path) -> tuple[List[Path], Path]:
    """
    Copy images into a temp folder with short names to avoid
    Windows command-line length issues (WinError 206).
    """
    tmp_dir = out_dir / "_flip_tmp"

    # Clean existing temp dir if present
    if tmp_dir.exists():
        for f in tmp_dir.iterdir():
            try:
                f.unlink()
            except Exception:
                pass
    else:
        tmp_dir.mkdir(parents=True, exist_ok=True)

    short_paths: List[Path] = []
    for idx, img in enumerate(images):
        ext = img.suffix.lower() or ".png"
        name = f"i{idx:04d}{ext}"
        dest = tmp_dir / name
        shutil.copy2(img, dest)
        short_paths.append(dest)

    return short_paths, tmp_dir


def generate_flipthrough_video(
    base_dir: Path,
    folder: str,
    out_name: str = "flip_preview.mp4",
    seconds_per_image: float = 1.2,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    watermark_text: str = "PREVIEW ONLY - DO NOT PRINT",
    transition_duration: float = 0.3,        # overlap between pages
    transition_type: str = "slideleft",      # e.g. "slideleft", "slide", "wipe", "fade"
    alternate_direction: bool = False,       # True -> L/R/L/R "book" feel for generic 'slide'/'wipe'
) -> Path:
    """
    Create a flip-through video with professional transitions using ffmpeg xfade.

    - Loads images from <base_dir>/<folder>/processed_images or <base_dir>/<folder>.
    - Copies them into a temp folder with short names to avoid WinError 206.
    - Scales and centers on white WxH canvas.
    - Optional semi-transparent watermark.
    - Applies transitions between ALL pages:
        * slideleft / slideright / wipe* / fade / etc.
        * Optional alternating directions for "book" look (when using 'slide' or 'wipe').

    Uses -filter_complex_script to avoid Windows command-line length limits.

    Returns:
        Path to generated MP4.
    """
    images = collect_images_for_flip(base_dir, folder)
    base = base_dir.resolve()
    folder = folder.strip().strip("/\\")
    out_dir = (base / folder).resolve()
    if not str(out_dir).startswith(str(base)):
        raise FlipThroughError("Invalid output path")

    out_path = out_dir / out_name

    if transition_duration <= 0:
        raise FlipThroughError("transition_duration must be > 0")

    if seconds_per_image <= transition_duration:
        raise FlipThroughError(
            f"seconds_per_image ({seconds_per_image}) must be greater than "
            f"transition_duration ({transition_duration})."
        )

    # Prepare temp short-path images to keep paths small
    short_images, tmp_dir = _prepare_temp_sequence(images, out_dir)

    # ------------------------------------------------------------------
    # 1) Common video filter: scale + pad + format (+ watermark)
    # ------------------------------------------------------------------
    base_vf = (
        f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,"
        f"format=yuv420p"
    )

    final_vf = base_vf

    # Add watermark text if requested
    if watermark_text:
        safe_text = (
            watermark_text
                .replace("\\", "\\\\")
                .replace(":", r"\:")
                .replace("'", r"\'")
        )

        fontsize = int(height * 0.09)

        draw_args = [
            f"text='{safe_text}'",
            "fontcolor=black@0.3",
            "borderw=2",
            "bordercolor=white@0.6",
            f"fontsize={fontsize}",
            "x=(w-text_w)/2",
            "y=(h-text_h)/2",
        ]

        if os.name == "nt":
            win_font = _pick_windows_font()
            if win_font:
                win_font_escaped = win_font.replace("\\", "/").replace(":", r"\:")
                draw_args.append(f"fontfile='{win_font_escaped}'")

        draw = "drawtext=" + ":".join(draw_args)
        final_vf = base_vf + "," + draw

    processed_vf = f"{final_vf},fps={fps}"

    # ------------------------------------------------------------------
    # 2) Build filter graph text (to be written to a script file)
    # ------------------------------------------------------------------
    filter_parts: list[str] = []

    for i in range(len(short_images)):
        # [{i}:v] -> scale/pad/watermark/fps -> [s{i}]
        filter_parts.append(f"[{i}:v]{processed_vf}[s{i}]")

    if len(short_images) == 1:
        # No transitions, just single stream
        all_filters = ";".join(filter_parts)
        final_stream = "s0"
    else:
        xfade_parts: list[str] = []
        current_stream = "s0"
        current_duration = seconds_per_image  # after first still

        for step_index in range(1, len(short_images)):
            next_stream = f"s{step_index}"
            out_stream = f"v{step_index}"

            tr_name = _resolve_transition_type(
                transition_type,
                step_index,
                alternate_direction,
            )

            # offset is relative to the current_stream timeline:
            # start transition at (current_duration - transition_duration)
            offset = max(current_duration - transition_duration, 0.0)

            xfade_parts.append(
                f"[{current_stream}][{next_stream}]"
                f"xfade=transition={tr_name}:duration={transition_duration}:offset={offset:.6f}"
                f"[{out_stream}]"
            )

            # Each new image adds (seconds_per_image - transition_duration) effective duration
            current_duration += seconds_per_image - transition_duration
            current_stream = out_stream

        all_filters = ";".join(filter_parts + xfade_parts)
        final_stream = current_stream

    # Write filter graph to script file to avoid super long command line
    script_path = tmp_dir / "filters.ffscript"
    script_path.write_text(all_filters, encoding="utf-8")

    # ------------------------------------------------------------------
    # 3) Build ffmpeg command (small, safe for Windows)
    # ------------------------------------------------------------------
    cmd: list[str] = ["ffmpeg", "-y"]

    img_duration_str = f"{seconds_per_image:.6f}"
    for img_path in short_images:
        cmd.extend(["-loop", "1", "-t", img_duration_str, "-i", str(img_path)])

    cmd.extend([
        "-filter_complex_script", str(script_path),
        "-map", f"[{final_stream}]",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        str(out_path),
    ])

    # ------------------------------------------------------------------
    # 4) Run ffmpeg
    # ------------------------------------------------------------------
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if proc.returncode != 0:
            err_txt = (proc.stderr or b"").decode(errors="ignore")
            tail = err_txt[-800:] if err_txt else "Unknown error"

            if "drawtext" in err_txt.lower():
                raise FlipThroughError(
                    "ffmpeg drawtext/watermark failed. Details (tail): " + tail
                )
            if "xfade" in err_txt.lower():
                raise FlipThroughError(
                    "ffmpeg xfade (transition) failed. Details (tail): " + tail
                )
            raise FlipThroughError(
                "ffmpeg failed. Details (tail): " + tail
            )

    finally:
        # Best-effort cleanup of temp files and script
        try:
            if script_path.exists():
                script_path.unlink()
        except Exception:
            pass

        try:
            if tmp_dir.exists():
                for f in tmp_dir.iterdir():
                    try:
                        f.unlink()
                    except Exception:
                        pass
                tmp_dir.rmdir()
        except Exception:
            pass

    if not out_path.is_file():
        raise FlipThroughError("Flip-through video was not created.")

    return out_path
