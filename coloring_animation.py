import os
import cv2
import numpy as np
import subprocess
from typing import Tuple
from PIL import Image, ImageOps, ImageFilter, ImageDraw

from pathlib import Path


def _quantize_to_color_labels(img: Image.Image, num_colors: int = 7):
    """
    Use Pillow's adaptive palette to quantize the image into `num_colors`
    and return:
      - labels: (H,W) numpy array with palette indices 0..num_colors-1
      - palette_colors: list of (R,G,B) tuples for each index
    """
    quant = img.convert("P", palette=Image.ADAPTIVE, colors=num_colors)
    labels = np.array(quant, dtype=np.int32)

    pal = quant.getpalette()  # flat list [r0,g0,b0, r1,g1,b1, ...]
    palette_colors = []
    for i in range(num_colors):
        r = pal[3*i + 0]
        g = pal[3*i + 1]
        b = pal[3*i + 2]
        palette_colors.append((r, g, b))

    return labels, palette_colors

def _create_coloring_animation_by_color(
    input_path: Path,
    output_path: Path,
    fps: int = 30,
    num_colors: int = 7,
    brush_steps_per_color: int = 50,
    hold_line_sec: float = 1.2,
    hold_end_sec: float = 1.2,
    target_size: tuple[int, int] | None = None,
    bg_color=(255, 255, 255),
):
    """
    More 'artistic' coloring animation:
      - Start with clean line-art (no color)
      - Quantize image into `num_colors`
      - For each color cluster, brush-reveal that color region in several steps
      - Then move to next color

    Looks like an artist coloring the page one color at a time.
    """
    from tempfile import TemporaryDirectory
    import subprocess

    # Load original
    img = Image.open(input_path).convert("RGB")
    if target_size:
        img = _letterbox_to_canvas(img, target_size[0], target_size[1], bg_color=bg_color)
    w, h = img.size

    # --- Make line-art base ---
    # gray = ImageOps.grayscale(img)
    # edges = gray.filter(ImageFilter.FIND_EDGES)
    # edges = ImageOps.autocontrast(edges)
    # edges = ImageOps.invert(edges)
    # edges = edges.point(lambda p: 0 if p < 128 else 255)
    # line_art = edges.convert("RGB")

    # --- Make line-art base: keep original black ink (borders, eyes) ---
    img_np_full = np.array(img, dtype=np.uint8)

    # Detect “ink” as pixels that are very close to black in ALL channels
    r = img_np_full[:, :, 0]
    g = img_np_full[:, :, 1]
    b = img_np_full[:, :, 2]

    # Tune this threshold if needed (smaller = only pure black, larger = also very dark colors)
    ink_mask = (r < 60) & (g < 60) & (b < 60)

    # Start with a white page
    line_np_uint8 = np.full_like(img_np_full, 255, dtype=np.uint8)

    # Put solid black where the original had near-black ink
    line_np_uint8[ink_mask] = 0

    # This “line_art” now has exactly your original black borders/eyes on white
    line_art = Image.fromarray(line_np_uint8, mode="RGB")


    # --- Color quantization ---
    labels, palette_colors = _quantize_to_color_labels(img, num_colors=num_colors)

    # Decide which palette indices are *real colors* (skip nearly white)
    counts = np.bincount(labels.flatten())
    palette_indices = list(range(len(palette_colors)))

    def is_background_color(rgb):
        r, g, b = rgb
        return r > 240 and g > 240 and b > 240  # very close to white

    # Sort by area (biggest color first), skip background-ish
    color_order = []
    for idx in palette_indices:
        col = palette_colors[idx]
        if counts[idx] == 0:
            continue
        if is_background_color(col):
            continue
        color_order.append((counts[idx], idx))
    color_order.sort(reverse=True)  # large regions first
    ordered_indices = [idx for _, idx in color_order]

    # Precompute coordinate grids for stroke directions
    yy, xx = np.indices((h, w), dtype=np.float32)

    # Global noise map used to make brush fronts slightly irregular
    rng = np.random.default_rng(42)
    noise_map = rng.normal(loc=0.0, scale=0.35, size=(h, w)).astype(np.float32)

    # Numpy view of original + line-art
    img_np = np.array(img, dtype=np.float32)
    line_np = np.array(line_art, dtype=np.float32)


    total_colors = len(ordered_indices)
    if total_colors == 0:
        # fallback to simple sweep if weird image
        return _create_coloring_animation(
            input_path=input_path,
            output_path=output_path,
            fps=fps,
            duration_sec=4.0,
            target_size=target_size,
            bg_color=bg_color,
        )

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        frame_idx = 0

        # Start from pure line-art
        current_frame = line_np.copy()

        # Hold line-art for a moment
        hold_line_frames = int(round(hold_line_sec * fps))
        for _ in range(hold_line_frames):
            Image.fromarray(current_frame.astype(np.uint8)).save(
                tmpdir_path / f"frame_{frame_idx:04d}.png"
            )
            frame_idx += 1

        # Animate each color cluster
        for color_idx_pos, pal_idx in enumerate(ordered_indices):
            # Binary mask for this color
            mask_color = (labels == pal_idx).astype(np.float32)  # 0 or 1

            # Slightly erode/dilate via blur to avoid pixel-noise edges
            mask_img = Image.fromarray((mask_color * 255).astype(np.uint8))
            mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=0.8))
            mask_color = np.array(mask_img, dtype=np.float32) / 255.0

            # Skip super tiny regions
            if mask_color.sum() < 50:
                continue

            # For this color, gradually reveal with random brushiness
            # Skip super tiny regions
            if mask_color.sum() < 50:
                continue

            # ---- Directional brush front for this color ----
            ys, xs = np.where(mask_color > 0.2)
            if ys.size == 0:
                continue

            min_x, max_x = xs.min(), xs.max()
            min_y, max_y = ys.min(), ys.max()

            # Random stroke direction for this color (in radians)
            theta = float(rng.uniform(0.0, 2.0 * np.pi))
            dir_x, dir_y = float(np.cos(theta)), float(np.sin(theta))

            # Project each pixel to a 1D coordinate along the stroke direction
            proj = (xx - min_x) * dir_x + (yy - min_y) * dir_y
            proj_region = proj[mask_color > 0.2]
            p_min, p_max = proj_region.min(), proj_region.max()
            proj_norm = (proj - p_min) / (p_max - p_min + 1e-6)  # 0→1 over region

            # For this color, gradually reveal with a wavy brush front
            for step in range(brush_steps_per_color):
                t = (step + 1) / brush_steps_per_color  # 0→1

                # Threshold that moves across the region, with noise-based waviness
                threshold = proj_norm + noise_map * 0.25
                reveal_mask = (mask_color > 0.1) & (threshold <= t)
                reveal_mask = reveal_mask.astype(np.float32)

                # Soften edge a bit
                reveal_img = Image.fromarray((reveal_mask * 255).astype(np.uint8))
                reveal_img = reveal_img.filter(ImageFilter.GaussianBlur(radius=1.4))
                reveal_mask = np.array(reveal_img, dtype=np.float32) / 255.0

                # Restrict strictly to this color region
                reveal_mask *= (mask_color > 0.05).astype(np.float32)

                # Expand to 3 channels
                reveal_3 = np.dstack([reveal_mask] * 3)

                # Blend this color from original img into current_frame
                current_frame = current_frame * (1.0 - reveal_3) + img_np * reveal_3

                # 🔴 NEW: re-impose black ink lines so they never get washed out
                current_frame = np.minimum(current_frame, line_np)

                current_frame = np.clip(current_frame, 0, 255)

                # Save frame
                Image.fromarray(current_frame.astype(np.uint8)).save(
                    tmpdir_path / f"frame_{frame_idx:04d}.png"
                )
                frame_idx += 1


        # Hold final fully-colored frame
        hold_end_frames = int(round(hold_end_sec * fps))
        final_frame = np.array(img, dtype=np.uint8)
        for _ in range(hold_end_frames):
            Image.fromarray(final_frame).save(
                tmpdir_path / f"frame_{frame_idx:04d}.png"
            )
            frame_idx += 1

        # ffmpeg encode
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmpdir_path / "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed with code {proc.returncode}:\n"
                f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
            )


# =========================
#  Line Art Generation
# =========================

def make_line_art(colored_img: np.ndarray) -> np.ndarray:
    """
    Convert a fully colored page to 'coloring book' style line art:
    - White background
    - Clean black lines
    - 3-channel BGR image
    """
    # Convert to gray
    gray = cv2.cvtColor(colored_img, cv2.COLOR_BGR2GRAY)

    # Slight blur to reduce noise before edge detection
    gray_blur = cv2.medianBlur(gray, 3)

    # Adaptive threshold to emphasize dark outlines
    edges = cv2.adaptiveThreshold(
        gray_blur,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        blockSize=9,
        C=2
    )

    # edges: white lines on black; invert to black on white
    line_art = 255 - edges

    # Optional: strengthen lines / clean noise
    # dilate then erode to bold lines and close tiny gaps
    kernel = np.ones((2, 2), np.uint8)
    line_art = cv2.dilate(line_art, kernel, iterations=1)
    line_art = cv2.erode(line_art, kernel, iterations=1)

    # Convert to 3-channel BGR so we can blend later
    line_art_bgr = cv2.cvtColor(line_art, cv2.COLOR_GRAY2BGR)
    return line_art_bgr

def _create_coloring_animation(
    input_path: Path,
    output_path: Path,
    fps: int = 30,
    duration_sec: float = 4.0,
    target_size: tuple[int, int] | None = None,
    bg_color=(255, 255, 255),
) -> None:
    """
    Create a 'coloring' animation:
      1) Start with a clean line-art version (no color)
      2) Sweep color from left to right using the original colored image

    Writes an MP4 to `output_path` using ffmpeg.
    """

    from tempfile import TemporaryDirectory
    import subprocess

    # Load base image
    img = Image.open(input_path).convert("RGB")

    # Optional fixed canvas
    if target_size:
        tw, th = target_size
        img = _letterbox_to_canvas(img, tw, th, bg_color=bg_color)

    w, h = img.size

    # Create line-art look (desaturated + edge emphasis)
    gray = ImageOps.grayscale(img)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges = ImageOps.autocontrast(edges)
    # invert to get dark lines on light background
    edges = ImageOps.invert(edges)
    # push faint edges toward white for a clean page look
    edges = edges.point(lambda p: 0 if p < 128 else 255)
    line_art = edges.convert("RGB")

    total_frames = max(10, int(fps * duration_sec))
    hold_start_frames = int(fps * 0.7)   # how long to hold pure line art at the beginning
    hold_end_frames = int(fps * 0.7)     # hold full-color at the end

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        frame_idx = 0

        # 1) Hold line-art only
        for _ in range(hold_start_frames):
            frame_path = tmpdir_path / f"frame_{frame_idx:04d}.png"
            line_art.save(frame_path)
            frame_idx += 1

        # 2) Sweep color left→right
        sweep_frames = max(5, total_frames - hold_start_frames - hold_end_frames)
        for i in range(sweep_frames):
            t = (i + 1) / sweep_frames  # 0→1
            mask = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(mask)
            sweep_x = int(w * t)
            draw.rectangle([0, 0, sweep_x, h], fill=255)

            frame = Image.composite(img, line_art, mask).convert("RGB")
            frame_path = tmpdir_path / f"frame_{frame_idx:04d}.png"
            frame.save(frame_path)
            frame_idx += 1

        # 3) Hold full-color at the end
        for _ in range(hold_end_frames):
            frame_path = tmpdir_path / f"frame_{frame_idx:04d}.png"
            img.save(frame_path)
            frame_idx += 1

        # Build video using ffmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate", str(fps),
            "-i", str(tmpdir_path / "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed with code {proc.returncode}:\n"
                f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
            )
# =========================
#  Mask Utilities
# =========================

def _prepare_coord_grids(h: int, w: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Precompute coordinate grids and a radial distance map for mask generation.
    """
    yy, xx = np.indices((h, w), dtype=np.float32)
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    dist_norm = dist / (dist.max() + 1e-8)  # 0 at center, 1 at farthest corner

    return yy, xx, dist_norm


def _smooth_mask(mask: np.ndarray, sigma: float = 5.0) -> np.ndarray:
    """
    Apply Gaussian blur to soften mask edges and avoid harsh transitions.
    mask: float32 in [0,1]
    """
    if sigma <= 0:
        return np.clip(mask, 0.0, 1.0)
    mask = cv2.GaussianBlur(mask, ksize=(0, 0), sigmaX=sigma, sigmaY=sigma)
    return np.clip(mask, 0.0, 1.0)


def _easing(progress: float, kind: str = "ease_in_out") -> float:
    """
    Easing function for smoother, more cinematic motion.
    """
    p = np.clip(progress, 0.0, 1.0)
    if kind == "linear":
        return float(p)
    # Smoothstep ease-in-out
    return float(p * p * (3 - 2 * p))


def generate_mask(
    style: str,
    progress: float,
    h: int,
    w: int,
    yy: np.ndarray,
    xx: np.ndarray,
    dist_norm: np.ndarray,
    noise_map: np.ndarray = None
) -> np.ndarray:
    """
    Generate a 2D mask (float32 in [0,1]) for a given progress and style.

    style options:
        - "wipe_lr"   : left-to-right wipe
        - "radial_in" : from center outward
        - "noisy_brush": organic, slightly irregular brush-like reveal
    """
    p = _easing(progress, "ease_in_out")

    if style == "wipe_lr":
        # Linear gradient left (0) to right (1)
        base = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]  # shape (1, w)
        mask = (base <= p).astype(np.float32)
        mask = np.repeat(mask, h, axis=0)  # (h, w)
        mask = _smooth_mask(mask, sigma=4.0)
        return mask

    elif style == "radial_in":
        # dist_norm: 0 at center, 1 at far edge
        # Reveal where normalized distance <= p
        mask = (dist_norm <= p).astype(np.float32)
        mask = _smooth_mask(mask, sigma=6.0)
        return mask

    elif style == "noisy_brush":
        # Base gradient left->right plus fixed noise map
        if noise_map is None:
            raise ValueError("noise_map is required for 'noisy_brush' style.")
        base = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
        base = np.repeat(base, h, axis=0)
        # Combine linear gradient with noise
        threshold = base + noise_map * 0.25  # control roughness with factor
        mask = (threshold <= p).astype(np.float32)
        mask = _smooth_mask(mask, sigma=5.0)
        return mask

    else:
        # Fallback: simple linear wipe
        base = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
        mask = (base <= p).astype(np.float32)
        mask = np.repeat(mask, h, axis=0)
        mask = _smooth_mask(mask, sigma=3.0)
        return mask


# =========================
#  Main Animation Builder
# =========================

def create_coloring_animation_frames(
    input_path: str,
    frames_dir: str = "frames_coloring",
    style: str = "wipe_lr",
    fps: int = 30,
    color_reveal_duration_sec: float = 3.0,
    hold_start_sec: float = 0.7,
    hold_end_sec: float = 1.0,
) -> int:
    """
    Create high-quality coloring animation frames from a fully colored page.

    Steps:
        1) Load colored image
        2) Generate line-art "coloring page" version
        3) Hold line-art for a short time (before)
        4) Reveal original colors using chosen animation style
        5) Hold final colored frame (after)

    Returns:
        Total number of frames created.
    """

    img = cv2.imread(input_path)
    if img is None:
        raise ValueError(f"Could not read image from {input_path}")

    h, w = img.shape[:2]
    print(f"[INFO] Loaded image {input_path} with size {w}x{h}")

    # Generate line-art "no-color" version
    line_art = make_line_art(img)

    os.makedirs(frames_dir, exist_ok=True)

    # Convert timing to frame counts
    hold_start_frames = int(round(hold_start_sec * fps))
    hold_end_frames = int(round(hold_end_sec * fps))
    reveal_frames = max(1, int(round(color_reveal_duration_sec * fps)))
    total_frames = hold_start_frames + reveal_frames + hold_end_frames

    print(f"[INFO] FPS: {fps}")
    print(f"[INFO] Hold (start): {hold_start_frames} frames")
    print(f"[INFO] Reveal: {reveal_frames} frames")
    print(f"[INFO] Hold (end): {hold_end_frames} frames")
    print(f"[INFO] Total frames: {total_frames}")

    # Precompute coordinate grids and radial distance map
    yy, xx, dist_norm = _prepare_coord_grids(h, w)

    # Prepare a fixed noise map for 'noisy_brush' to avoid flicker
    rng = np.random.default_rng(seed=42)
    noise_map = rng.normal(loc=0.0, scale=0.8, size=(h, w)).astype(np.float32)

    # Prepare float versions for blending
    line_art_f = line_art.astype(np.float32)
    img_f = img.astype(np.float32)

    frame_idx = 0

    # 1) Hold pure line-art
    for _ in range(hold_start_frames):
        cv2.imwrite(os.path.join(frames_dir, f"frame_{frame_idx:04d}.png"), line_art)
        frame_idx += 1

    # 2) Reveal original colors progressively
    for step in range(reveal_frames):
        progress = step / max(1, reveal_frames - 1)  # 0 → 1

        mask_2d = generate_mask(
            style=style,
            progress=progress,
            h=h,
            w=w,
            yy=yy,
            xx=xx,
            dist_norm=dist_norm,
            noise_map=noise_map if style == "noisy_brush" else None
        )

        # Expand to 3 channels
        mask_3d = np.dstack([mask_2d] * 3).astype(np.float32)

        frame = line_art_f * (1.0 - mask_3d) + img_f * mask_3d
        frame = np.clip(frame, 0, 255).astype(np.uint8)

        cv2.imwrite(os.path.join(frames_dir, f"frame_{frame_idx:04d}.png"), frame)
        frame_idx += 1

    # 3) Hold final fully-colored frame
    for _ in range(hold_end_frames):
        cv2.imwrite(os.path.join(frames_dir, f"frame_{frame_idx:04d}.png"), img)
        frame_idx += 1

    print(f"[INFO] Saved {frame_idx} frames to: {frames_dir}")
    return frame_idx


# =========================
#  Optional: Frames → Video
# =========================

def frames_to_video(
    frames_dir: str,
    output_path: str,
    fps: int = 30,
    ffmpeg_path: str = "ffmpeg"
):
    """
    Convert PNG frames in frames_dir to an MP4 video using ffmpeg.
    Requires ffmpeg installed and available in PATH.

    Frames must be named frame_0000.png, frame_0001.png, ...
    """
    input_pattern = os.path.join(frames_dir, "frame_%04d.png")

    cmd = [
        ffmpeg_path,
        "-y",
        "-framerate", str(fps),
        "-i", input_pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # enforce even dimensions
        output_path,
    ]

    print(f"[INFO] Running ffmpeg to create video: {output_path}")
    print(" ".join(cmd))

    subprocess.run(cmd, check=True)
    print("[INFO] Video creation complete.")

def _letterbox_to_canvas(img: Image.Image,
                         target_w: int,
                         target_h: int,
                         bg_color=(255, 255, 255)) -> Image.Image:
    """
    Resize `img` to fit within (target_w, target_h) while preserving aspect ratio,
    adding padding (letterboxing) as needed.
    """
    if target_w <= 0 or target_h <= 0:
        return img

    w, h = img.size
    scale = min(target_w / w, target_h / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (target_w, target_h), bg_color)
    off_x = (target_w - new_w) // 2
    off_y = (target_h - new_h) // 2
    canvas.paste(img_resized, (off_x, off_y))

    return canvas
# =========================
#  Example CLI Usage
# =========================

if __name__ == "__main__":
    # Example usage - change input/output paths as needed
    INPUT_IMAGE = "input_colored_page.png"
    FRAMES_DIR = "frames_coloring_wipe"
    OUTPUT_VIDEO = "coloring_wipe_lr.mp4"

    # Basic: left → right professional wipe

    # total = create_coloring_animation_frames(
    #     input_path=INPUT_IMAGE,
    #     frames_dir=FRAMES_DIR,
    #     style="wipe_lr",          # "wipe_lr", "radial_in", or "noisy_brush"
    #     fps=30,
    #     color_reveal_duration_sec=3.0,
    #     hold_start_sec=0.7,
    #     hold_end_sec=1.0,
    # )

    # frames_to_video(
    #     frames_dir=FRAMES_DIR,
    #     output_path=OUTPUT_VIDEO,
    #     fps=30
    # )

    # 2️⃣ Cinematic center-out reveal (great for mandalas)
    # create_coloring_animation_frames(
    #     input_path="input_colored_page.png",
    #     frames_dir="frames_mandala_radial",
    #     style="radial_in",
    #     fps=30,
    #     color_reveal_duration_sec=4.0,  # slower, more meditative
    # )

    # frames_to_video(
    #     frames_dir="frames_mandala_radial",
    #     output_path="mandala_page_03_radial.mp4",
    #     fps=30
    # )

    # 3️⃣ Organic brushy feel (for fun kids’ pages)
    # create_coloring_animation_frames(
    #     input_path="input_colored_page.png",
    #     frames_dir="frames_fun_noisy",
    #     style="noisy_brush",
    #     fps=30,
    #     color_reveal_duration_sec=3.5,
    # )

    # frames_to_video(
    #     frames_dir="frames_fun_noisy",
    #     output_path="fun_activities_page_noisy_brush.mp4",
    #     fps=30
    # )


    _create_coloring_animation_by_color(
        input_path="input_colored_page.png",
        output_path= "coloring.mp4",
        fps = 30,
        num_colors= 7,
        brush_steps_per_color = 40,
        hold_line_sec = 1.2,
        hold_end_sec = 1.2,
        target_size = None,
        bg_color=(255, 255, 255),
    )

######USAGE EXAMPLES######
# 1️⃣
# Basic: left → right professional wipe
# python coloring_animation.py


# (or import in another script and call:)

# from coloring_animation import create_coloring_animation_frames, frames_to_video

# create_coloring_animation_frames(
#     input_path="baby_animals_page_01.png",
#     frames_dir="frames_baby_animals_wipe",
#     style="wipe_lr",
#     fps=30,
#     color_reveal_duration_sec=3.0,
#     hold_start_sec=0.7,
#     hold_end_sec=1.0,
# )

# frames_to_video(
#     frames_dir="frames_baby_animals_wipe",
#     output_path="baby_animals_page_01_wipe.mp4",
#     fps=30
# )

# 2️⃣ Cinematic center-out reveal (great for mandalas)
# create_coloring_animation_frames(
#     input_path="mandala_page_03.png",
#     frames_dir="frames_mandala_radial",
#     style="radial_in",
#     fps=30,
#     color_reveal_duration_sec=4.0,  # slower, more meditative
# )

# frames_to_video(
#     frames_dir="frames_mandala_radial",
#     output_path="mandala_page_03_radial.mp4",
#     fps=30
# )

# 3️⃣ Organic brushy feel (for fun kids’ pages)
# create_coloring_animation_frames(
#     input_path="fun_activities_page.png",
#     frames_dir="frames_fun_noisy",
#     style="noisy_brush",
#     fps=30,
#     color_reveal_duration_sec=3.5,
# )

# frames_to_video(
#     frames_dir="frames_fun_noisy",
#     output_path="fun_activities_page_noisy_brush.mp4",
#     fps=30
# )