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


def _resolve_transition_type(base_type: str, step_index: int, alternate_direction: bool) -> str:
    """
    Resolve the actual xfade transition name.

    - If base_type is 'slide' or 'wipe' and alternate_direction is True:
        alternate left/right per step for a book-like flip.
    - If base_type is already a valid specific xfade transition name:
        return as-is (no alternation unless you customize here).
    """
    base = base_type.lower().strip()

    if not alternate_direction:
        return base

    # Generic slide: alternate between slideleft / slideright
    if base == "slide":
        return "slideleft" if (step_index % 2) else "slideright"

    # Generic wipe: alternate between wipeleft / wiperight
    if base == "wipe":
        return "wipeleft" if (step_index % 2) else "wiperight"

    # If caller passed a specific name (slideleft, smoothleft, etc.), keep it.
    return base


def generate_flipthrough_video(
    base_dir: Path,
    folder: str,
    out_name: str = "flip_preview.mp4",
    seconds_per_image: float = 1.2,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    watermark_text: str = "PREVIEW ONLY - DO NOT PRINT",
    transition_duration: float = 0.3,       # overlap duration between pages
    transition_type: str = "smoothleft",        # "slide", "wipe", or any xfade type (e.g. "fade", "smoothleft")
    alternate_direction: bool = False,      # make it feel like pages turning L/R/L/R
) -> Path:
    """
    Create a flip-through video with professional page-style transitions using ffmpeg xfade.

    - Loads images from <base_dir>/<folder>/processed_images or <base_dir>/<folder>.
    - Centers each image on a white WxH canvas.
    - Optional semi-transparent watermark across center.
    - Applies crossfade/slide/wipe transitions between ALL pages.
    - Supports alternating left/right style for a "book flip" feel.
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

    # ------------------------------------------------------------------
    # 1) Common video filter: scale + pad + format
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
                # escape ':' for ffmpeg syntax
                win_font_escaped = win_font.replace("\\", "/").replace(":", r"\:")
                draw_args.append(f"fontfile='{win_font_escaped}'")

        draw = "drawtext=" + ":".join(draw_args)
        final_vf = base_vf + "," + draw

    # We'll also lock fps per stream to keep timing consistent
    processed_vf = f"{final_vf},fps={fps}"

    # ------------------------------------------------------------------
    # 2) Build ffmpeg input args
    # ------------------------------------------------------------------
    cmd: list[str] = ["ffmpeg", "-y"]

    # Each image is looped for full seconds_per_image
    img_duration_str = f"{seconds_per_image:.6f}"
    for img_path in images:
        cmd.extend(["-loop", "1", "-t", img_duration_str, "-i", str(img_path)])

    # ------------------------------------------------------------------
    # 3) Build filter_complex: process each input -> [s0], [s1], ...
    # ------------------------------------------------------------------
    filter_parts: list[str] = []

    for i in range(len(images)):
        # [{i}:v] -> scale/pad/watermark/fps -> [s{i}]
        filter_parts.append(f"[{i}:v]{processed_vf}[s{i}]")

    # If only one image: no transitions, just map s0.
    if len(images) == 1:
        all_filters = ";".join(filter_parts)
        final_stream = "s0"
    else:
        # ------------------------------------------------------------------
        # 4) Chain xfade transitions across all processed streams
        #     s0 + s1 -> v1
        #     v1 + s2 -> v2
        #     v2 + s3 -> v3
        #   each offset is relative to the first input of that xfade,
        #   so we use (current_duration - transition_duration)
        #   and track current_duration cumulatively.
        # ------------------------------------------------------------------
        xfade_parts: list[str] = []

        current_stream = "s0"
        # duration after first still
        current_duration = seconds_per_image

        for step_index in range(1, len(images)):
            next_stream = f"s{step_index}"
            out_stream = f"v{step_index}"

            # Resolve transition name (handles alternating slide/wipe)
            tr_name = _resolve_transition_type(
                transition_type,
                step_index,
                alternate_direction,
            )

            # offset = (duration of accumulated stream) - transition_duration
            offset = max(current_duration - transition_duration, 0.0)

            xfade_parts.append(
                f"[{current_stream}][{next_stream}]"
                f"xfade=transition={tr_name}:duration={transition_duration}:offset={offset:.6f}"
                f"[{out_stream}]"
            )

            # Update for next iteration: each new image extends by
            # (seconds_per_image - transition_duration) due to overlap.
            current_duration += seconds_per_image - transition_duration
            current_stream = out_stream

        all_filters = ";".join(filter_parts + xfade_parts)
        final_stream = current_stream

    # ------------------------------------------------------------------
    # 5) Finish command: map final stream, encode
    # ------------------------------------------------------------------
    cmd.extend([
        "-filter_complex", all_filters,
        "-map", f"[{final_stream}]",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        str(out_path),
    ])

    # ------------------------------------------------------------------
    # 6) Run ffmpeg and handle errors
    # ------------------------------------------------------------------
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
        raise FlipThroughError("ffmpeg failed. Details (tail): " + tail)

    if not out_path.is_file():
        raise FlipThroughError("Flip-through video was not created.")

    return out_path
