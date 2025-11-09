# coloring_upscale.py

from pathlib import Path
from PIL import Image

# Allowed image types
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def get_page_size(page_size: str) -> tuple[int, int]:
    """
    Returns (width_px, height_px) for 300 DPI targets.
    """
    page_size = (page_size or "LETTER").upper()
    if page_size == "EIGHTX10":
        # 8 x 10 inches @ 300 DPI
        return 2400, 3000
    # Default: 8.5 x 11 inches @ 300 DPI
    return 2550, 3300


def upscale_coloring_page(
    input_path: Path,
    output_path: Path,
    target_width: int,
    target_height: int,
    threshold: int = 200,
) -> None:
    """
    Upscale + center + hard B/W threshold a coloring page onto a fixed canvas.
    - input_path: original image file
    - output_path: destination PNG
    - target_*: full page size in px (e.g. 2550x3300)
    - threshold: 0-255; lower = more black, higher = lighter
    """
    img = Image.open(input_path).convert("L")  # grayscale

    src_w, src_h = img.size

    # We'll use up to 80% of the page as drawing area to leave natural margins.
    max_w = target_width * 0.8
    max_h = target_height * 0.8

    # Scale to fit while preserving aspect ratio.
    scale = min(max_w / src_w, max_h / src_h)

    # If the original is small, still upscale so it doesn't look tiny on page.
    if scale < 1:
        scale = max(1.5, max_w / src_w, max_h / src_h)

    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    # High-quality resize
    upscaled = img.resize((new_w, new_h), Image.LANCZOS)

    # Hard B/W: great for crisp coloring lines
    bw = upscaled.point(lambda x: 0 if x < threshold else 255, mode="1")

    # White page canvas
    canvas = Image.new("1", (target_width, target_height), 1)  # 1 = white in mode "1"

    # Center on page
    offset_x = max(0, (target_width - new_w) // 2)
    offset_y = max(0, (target_height - new_h) // 2)

    canvas.paste(bw, (offset_x, offset_y))

    # Save as high-res PNG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)


def process_coloring_folder(
    coloring_base: Path,
    folder: str,
    page_size: str = "LETTER",
    threshold: int = 200,
) -> list[Path]:
    """
    Process all images in coloring_base/folder and write them into
    coloring_base/folder/processed_images as *_upscaled.png.

    Returns:
        List of Path objects for all processed files.

    Raises:
        ValueError, FileNotFoundError for invalid inputs.
    """
    folder = (folder or "").strip().strip("/\\")
    if not folder:
        raise ValueError("Folder name is empty.")

    base = coloring_base.resolve()
    src_dir = (base / folder).resolve()

    # Safety: prevent directory traversal
    if not str(src_dir).startswith(str(base)) or not src_dir.is_dir():
        raise FileNotFoundError(f"Folder not found or invalid: {folder}")

    out_dir = src_dir / "processed_images"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [
        p for p in sorted(src_dir.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]

    if not files:
        raise FileNotFoundError(f"No images found in folder: {folder}")

    target_w, target_h = get_page_size(page_size)
    outputs: list[Path] = []

    for img_path in files:
        out_path = out_dir / f"{img_path.stem}_upscaled.png"
        upscale_coloring_page(img_path, out_path, target_w, target_h, threshold)
        outputs.append(out_path)

    return outputs
