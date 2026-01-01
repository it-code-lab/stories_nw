"""
Convert landscape images in edit_vid_input -> portrait outputs in edit_vid_output

Modes:
- portrait      => 1080x1920 (9:16)
- landscape     => 1920x1080 (16:9)  <-- NEW
- 1000x1500     => 1000x1500 (2:3)

Fit:
- contain  => keep whole image, add padding (white or blurred background)
- cover    => fill frame, crop edges

Usage examples:
  python convert_images_portrait.py --mode portrait --fit contain --bg blur
  python convert_images_portrait.py --mode 1000x1500 --fit cover
"""

import argparse
import os
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def open_image_rgb(path: Path) -> Image.Image:
    # Handles EXIF orientation and ensures RGB for jpg output
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    return img


def make_background(
    src: Image.Image, target_w: int, target_h: int, bg_style: str
) -> Image.Image:
    if bg_style == "white":
        return Image.new("RGB", (target_w, target_h), (255, 255, 255))

    # blur background: resize to cover then blur
    # (convert to RGB so final paste is easy)
    bg = src.convert("RGB")
    scale = max(target_w / bg.width, target_h / bg.height)
    new_size = (max(1, int(bg.width * scale)), max(1, int(bg.height * scale)))
    bg = bg.resize(new_size, Image.LANCZOS)

    left = (bg.width - target_w) // 2
    top = (bg.height - target_h) // 2
    bg = bg.crop((left, top, left + target_w, top + target_h))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
    return bg


def fit_contain(
    src: Image.Image, target_w: int, target_h: int, bg_style: str
) -> Image.Image:
    bg = make_background(src, target_w, target_h, bg_style)

    # Resize source to fit inside target
    fg = src
    # If RGBA, keep alpha for pasting nicely
    has_alpha = (fg.mode == "RGBA")
    scale = min(target_w / fg.width, target_h / fg.height)
    new_size = (max(1, int(fg.width * scale)), max(1, int(fg.height * scale)))
    fg = fg.resize(new_size, Image.LANCZOS)

    x = (target_w - fg.width) // 2
    y = (target_h - fg.height) // 2

    if has_alpha:
        bg.paste(fg.convert("RGBA"), (x, y), fg.convert("RGBA"))
        return bg.convert("RGB")
    else:
        bg.paste(fg.convert("RGB"), (x, y))
        return bg


def fit_cover(src: Image.Image, target_w: int, target_h: int) -> Image.Image:
    # Resize to cover and crop
    img = src.convert("RGB")
    scale = max(target_w / img.width, target_h / img.height)
    new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    img = img.resize(new_size, Image.LANCZOS)

    left = (img.width - target_w) // 2
    top = (img.height - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))
    return img


def convert_one(
    in_path: Path,
    out_path: Path,
    target_w: int,
    target_h: int,
    fit: str,
    bg_style: str,
    quality: int,
) -> None:
    src = open_image_rgb(in_path)

    if fit == "cover":
        out_img = fit_cover(src, target_w, target_h)
    else:
        out_img = fit_contain(src, target_w, target_h, bg_style=bg_style)

    ensure_dir(out_path.parent)

    # Save as JPG for video pipelines (smaller + widely supported)
    # out_path = out_path.with_suffix(".jpg")
    # out_img.save(out_path, format="JPEG", quality=quality, optimize=True)
    # Save as PNG
    out_path = out_path.with_suffix(".png")
    out_img.save(
        out_path,
        format="PNG",
        optimize=True,
        compress_level=6  # 0 (fastest) → 9 (smallest)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="edit_vid_input", help="Input folder")
    parser.add_argument("--output", default="edit_vid_output", help="Output folder")

    # Mode flag requested
    parser.add_argument(
        "--mode",
        choices=["portrait", "1000x1500", "landscape"],
        default="portrait",
        help="Target format",
    )


    # Optional behavior flags
    parser.add_argument(
        "--fit",
        choices=["contain", "cover"],
        default="contain",
        help="contain = pad, cover = crop",
    )
    parser.add_argument(
        "--bg",
        choices=["blur", "white"],
        default="blur",
        help="Background used only when fit=contain",
    )
    parser.add_argument("--quality", type=int, default=92, help="JPEG quality 1-95")
    args = parser.parse_args()

    if args.mode == "portrait":
        target_w, target_h = 1080, 1920
    elif args.mode == "1000x1500":
        target_w, target_h = 1000, 1500
    else:  # landscape
        target_w, target_h = 1920, 1080


    in_dir = Path(args.input)
    out_dir = Path(args.output)
    if not in_dir.exists() or not in_dir.is_dir():
        raise SystemExit(f"❌ Input folder not found: {in_dir.resolve()}")

    count_in = 0
    count_out = 0

    for root, _, files in os.walk(in_dir):
        root_p = Path(root)
        rel = root_p.relative_to(in_dir)

        for fn in files:
            ext = Path(fn).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                continue

            count_in += 1
            in_path = root_p / fn
            # out_path = out_dir / rel / Path(fn).with_suffix(".jpg")
            out_path = out_dir / rel / Path(fn).with_suffix(".png")

            try:
                convert_one(
                    in_path=in_path,
                    out_path=out_path,
                    target_w=target_w,
                    target_h=target_h,
                    fit=args.fit,
                    bg_style=args.bg,
                    quality=max(1, min(int(args.quality), 95)),
                )
                count_out += 1
            except Exception as e:
                print(f"⚠️ Failed: {in_path} -> {e}")

    print(f"✅ Done. Read {count_in} images, wrote {count_out} images to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
