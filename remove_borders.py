import os
from pathlib import Path
from PIL import Image, ImageDraw

# Root folders
INPUT_ROOT = Path("downloads")
OUTPUT_ROOT = Path("borderless_images")

# File types
VALID_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def blank_out_border(input_path: Path,
                     output_path: Path,
                     border_px: int = 10,
                     fill="white") -> None:
    """
    Keep original image size, but blank out outer border_px pixels on all sides.
    fill = "white" or (R, G, B, A)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    im = Image.open(input_path).convert("RGBA")
    w, h = im.size

    draw = ImageDraw.Draw(im)

    # TOP
    draw.rectangle([(0, 0), (w, border_px)], fill=fill)

    # BOTTOM
    draw.rectangle([(0, h - border_px), (w, h)], fill=fill)

    # LEFT
    draw.rectangle([(0, 0), (border_px, h)], fill=fill)

    # RIGHT
    draw.rectangle([(w - border_px, 0), (w, h)], fill=fill)

    im.save(output_path)


def main(source_subfolder: str | None = None,
         border_px: int = 10,
         fill="white"):
    """
    Blank out border_px pixels from all sides, keeping image size unchanged.
    """
    input_root = INPUT_ROOT
    output_root = OUTPUT_ROOT

    if source_subfolder:
        source_subfolder = source_subfolder.strip().replace("\\", "/")
        input_root = INPUT_ROOT / source_subfolder
        output_root = OUTPUT_ROOT / source_subfolder

    if not input_root.exists():
        msg = f"Input folder does not exist: {input_root}"
        print(f"[ERROR] {msg}")
        return {"ok": False, "error": msg}

    print(f"Input root:  {input_root}")
    print(f"Output root: {output_root}")
    print(f"Blanking out {border_px}px border...")

    total = 0
    for dirpath, dirnames, filenames in os.walk(input_root):
        dirpath = Path(dirpath)
        for filename in filenames:
            if not filename.lower().endswith(VALID_EXTENSIONS):
                continue

            total += 1
            src = dirpath / filename
            rel = src.relative_to(input_root)
            out = output_root / rel

            try:
                blank_out_border(src, out, border_px=border_px, fill=fill)
                print(f"[OK] {src} -> {out}")
            except Exception as e:
                print(f"[ERROR] {src}: {e}")

    msg = f"Processed {total} images. Output in {output_root}"
    print("[DONE]", msg)
    return {"ok": True, "message": msg}


if __name__ == "__main__":
    # Example:
    # main("7b. Dinosaurs", border_px=10)
    main()
