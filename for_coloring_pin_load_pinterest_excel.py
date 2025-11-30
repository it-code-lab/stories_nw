# generate_excel.py
import argparse
import sys
import json
from pathlib import Path

from openpyxl import Workbook
from PIL import Image, ImageOps, ImageDraw, ImageFont

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi"}

CONFIG_FILENAME = "pinterest_config.json"


def collect_media_files(root: Path, subfolder: str | None) -> list[Path]:
    """
    Collect image / video files from images_root / subfolder (recursive).
    """
    base = root / subfolder if subfolder else root
    if not base.exists():
        raise FileNotFoundError(f"Source folder does not exist: {base}")

    files = []
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in IMAGE_EXTS.union(VIDEO_EXTS):
            files.append(p)

    files.sort()
    return files


def load_book_config(images_root: Path, source_subfolder: str | None) -> dict:
    """
    Look for pinterest_config.json inside source_subfolder and its parent.
    Returns dict with keys:
      book_title, book_url, board_name, banner_text, watermark_text
    Any missing file or key just means "no default" for that field.
    """
    
    if source_subfolder:
        base = images_root / source_subfolder
    else:
        base = images_root

    candidates = [
        base / CONFIG_FILENAME,
        base.parent / CONFIG_FILENAME
    ]

    # print candidates
    print(f"[INFO] Looking for Pinterest config in:")
    for c in candidates:
        print(f"  {c}")
    
    for cfg in candidates:
        if cfg.exists():
            try:
                with cfg.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[INFO] Loaded Pinterest config from: {cfg}")
                return {
                    "book_title": str(data.get("book_title", "")).strip(),
                    "book_url": str(data.get("book_url", "")).strip(),
                    "board_name": str(data.get("board_name", "")).strip(),
                    "banner_text": str(data.get("banner_text", "")).strip(),
                    "watermark_text": str(data.get("watermark_text", "")).strip(),
                }
            except Exception as e:
                print(f"[WARN] Failed to read config {cfg}: {e}")
                return {}
    print("[INFO] No pinterest_config.json found. Using only CLI/UI values.")
    return {}


def make_pinterest_image(
    src: Path,
    out_dir: Path,
    banner_text: str | None,
    watermark_text: str | None,
    target_size=(1000, 1500),
) -> Path:
    """
    Create a Pinterest-friendly image WITHOUT CROPPING:
    - white canvas 1000x1500
    - image fully visible (scaled to fit)
    - optional banner + watermark
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    base_img = Image.open(src).convert("RGB")
    orig_w, orig_h = base_img.size
    tgt_w, tgt_h = target_size

    # Scale to fit entire image inside canvas
    scale = min(tgt_w / orig_w, tgt_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    resized = base_img.resize((new_w, new_h), Image.LANCZOS)

    # Create white canvas
    canvas = Image.new("RGB", (tgt_w, tgt_h), "white")
    offset_x = (tgt_w - new_w) // 2
    offset_y = (tgt_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))

    draw = ImageDraw.Draw(canvas)

    # Fonts
    try:
        font = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 28)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    W, H = canvas.size

    # Helper for text size
    def measure(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])

    # ============= Banner =============
    if banner_text:
        banner_h = int(H * 0.12)

        overlay = Image.new("RGBA", (W, banner_h), (0, 0, 0, 160))
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.alpha_composite(overlay, (0, 0))
        canvas = canvas_rgba.convert("RGB")

        draw = ImageDraw.Draw(canvas)
        tw, th = measure(banner_text, font)
        draw.text(
            ((W - tw) / 2, (banner_h - th) / 2),
            banner_text,
            fill="white",
            font=font,
        )

    # ============= Watermark =============
    if watermark_text:
        wm_h = int(H * 0.08)

        overlay = Image.new("RGBA", (W, wm_h), (0, 0, 0, 140))
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.alpha_composite(overlay, (0, H - wm_h))
        canvas = canvas_rgba.convert("RGB")

        draw = ImageDraw.Draw(canvas)
        tw, th = measure(watermark_text, font_small)
        draw.text(
            ((W - tw) / 2, H - wm_h + (wm_h - th) / 2),
            watermark_text,
            fill="white",
            font=font_small,
        )

    # Save output
    out_path = out_dir / (src.stem + "_pin.webp")
    canvas.save(out_path, "WEBP", quality=90)
    return out_path



def make_pinterest_image_old(
    src: Path,
    out_dir: Path,
    banner_text: str | None,
    watermark_text: str | None,
    target_size=(1000, 1500),
) -> Path:
    """
    Create a Pinterest-friendly image (2:3-ish, tall) with optional banner + watermark.
    Returns output path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(src).convert("RGB")
    # Fit image to 1000x1500, cropping as needed
    img = ImageOps.fit(img, target_size, method=Image.LANCZOS)

    draw = ImageDraw.Draw(img)
    W, H = img.size
    font = ImageFont.load_default()

    # Banner at top
    if banner_text:
        banner_h = int(H * 0.12)
        overlay = Image.new("RGBA", (W, banner_h), (0, 0, 0, 160))
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(overlay, (0, 0))
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)
        tw, th = draw.textsize(banner_text, font=font)
        draw.text(
            ((W - tw) / 2, (banner_h - th) / 2),
            banner_text,
            fill="white",
            font=font,
        )

    # Watermark at bottom
    if watermark_text:
        wm_h = int(H * 0.08)
        overlay = Image.new("RGBA", (W, wm_h), (0, 0, 0, 140))
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(overlay, (0, H - wm_h))
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)
        tw, th = draw.textsize(watermark_text, font=font)
        draw.text(
            ((W - tw) / 2, H - wm_h + (wm_h - th) / 2),
            watermark_text,
            fill="white",
            font=font,
        )

    # Output filename
    out_name = src.stem + "_pin.webp"
    out_path = out_dir / out_name
    img.save(out_path, "WEBP", quality=90)
    return out_path


def build_excel(
    images_root: Path,
    source_subfolder: str | None,
    output_excel: Path,
    media_type: str,
    max_pins: int | None,
    book_title: str,
    book_url: str,
    board_name: str,
    banner_text: str | None,
    watermark_text: str | None,
) -> None:
    # 1) Load config (if present)
    cfg = load_book_config(images_root, source_subfolder)

    # 2) Resolve final values (UI/CLI overrides config)
    book_title = (book_title or cfg.get("book_title") or "Coloring Book").strip()
    book_url = (book_url or cfg.get("book_url") or "").strip()
    board_name = (board_name or cfg.get("board_name") or "").strip()
    banner_text = (banner_text or cfg.get("banner_text") or "").strip() or None
    watermark_text = (watermark_text or cfg.get("watermark_text") or "").strip() or None

    print(f"[INFO] Using values:")
    print(f"  book_title   = {book_title!r}")
    print(f"  book_url     = {book_url!r}")
    print(f"  board_name   = {board_name!r}")
    print(f"  banner_text  = {banner_text!r}")
    print(f"  watermark_text = {watermark_text!r}")

    media_files = collect_media_files(images_root, source_subfolder)
    if max_pins and max_pins > 0:
        media_files = media_files[:max_pins]

    print(f"[INFO] Found {len(media_files)} media files to process.")

    wb = Workbook()
    ws = wb.active
    ws.title = "Pins"

    # Column set (you can expand later if you want the earlier "full version")
    headers = [
        "pin_id",
        "media_file",       # final media file (image or video)
        "media_type",       # image / video
        "board_name",
        "book_title",
        "book_url",
        "pin_title",
        "pin_description",
        "pin_tags",
        "pin_url_to_link",
        "banner_text",
        "watermark_text",
        "notes",
    ]
    ws.append(headers)

    # Where to store generated Pinterest-ready images
    pins_output_root = images_root.parent / "pinterest_pins"
    pins_output_root.mkdir(parents=True, exist_ok=True)

    for idx, f in enumerate(media_files, start=1):
        ext = f.suffix.lower()
        is_image = ext in IMAGE_EXTS
        is_video = ext in VIDEO_EXTS

        if not (is_image or is_video):
            print(f"[SKIP] Unsupported file type: {f}")
            continue

        print(f"[PROCESS] {idx}: {f}")

        if is_image and media_type == "image":
            try:
                out_img = make_pinterest_image(
                    src=f,
                    out_dir=pins_output_root,
                    banner_text=banner_text,
                    watermark_text=watermark_text,
                )
                media_path_for_excel = str(out_img.relative_to(images_root.parent))
            except Exception as e:
                print(f"[WARN] Failed to create Pinterest image for {f}: {e}")
                media_path_for_excel = str(f.relative_to(images_root.parent))
        else:
            # For video mode, or if we decide to support original images without editing
            media_path_for_excel = str(f.relative_to(images_root.parent))

        # Very simple auto metadata (can be swapped with Gemini later)
        page_label = f.stem.replace("_", " ").replace("-", " ").title()
        pin_title = f"{book_title} – {page_label}"
        pin_description = (
            f"Coloring page from the '{book_title}' coloring book. "
            f"Perfect for relaxing creative time. Click to get the full printable book."
        )

        base_tags = [
            "coloring pages",
            "printable coloring",
            "kids coloring",
            "relaxing art",
            "coloring book",
        ]
        extra_tag = page_label.split()[0] if page_label else ""
        tags_str = ", ".join(base_tags + ([extra_tag] if extra_tag else []))

        pin_url_to_link = book_url or ""

        row = [
            idx,
            media_path_for_excel,
            media_type,
            board_name,
            book_title,
            book_url,
            pin_title,
            pin_description,
            tags_str,
            pin_url_to_link,
            banner_text or "",
            watermark_text or "",
            "",
        ]
        ws.append(row)

    output_excel.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_excel)
    print(f"[OK] Excel written to: {output_excel}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate Pinterest Pin Excel from images/videos.")
    parser.add_argument("--images-root", required=True, help="Root images folder (e.g. application/downloads)")
    parser.add_argument("--source-subfolder", default="", help="Subfolder under images-root, e.g. '1.Cute Farm Animals/pages'")
    parser.add_argument("--output-excel", default="pinterest_pins.xlsx", help="Output Excel filename")
    parser.add_argument("--media-type", choices=["image", "video"], default="image")
    parser.add_argument("--max-pins", type=int, default=0, help="Max pins to generate (0 = all)")

    # These are now OPTIONAL (can be provided by config file)
    parser.add_argument("--book-title", default="", help="Book title to use in Pin metadata (overrides config)")
    parser.add_argument("--book-url", default="", help="URL to link from the Pin (overrides config)")
    parser.add_argument("--board-name", default="", help="Pinterest board name (overrides config)")
    parser.add_argument("--banner-text", default="", help="Text banner at top of image (overrides config)")
    parser.add_argument("--watermark-text", default="", help="Watermark text at bottom of image (overrides config)")

    args = parser.parse_args(argv)

    images_root = Path(args.images_root).resolve()
    source_subfolder = args.source_subfolder or None
    output_excel = Path(args.output_excel).resolve()

    max_pins = args.max_pins if args.max_pins > 0 else None

    print("[INFO] Starting Pinterest Excel generation...")
    print(f"  images_root      = {images_root}")
    print(f"  source_subfolder = {source_subfolder}")
    print(f"  output_excel     = {output_excel}")
    print(f"  media_type       = {args.media_type}")
    print(f"  max_pins         = {max_pins}")

    build_excel(
        images_root=images_root,
        source_subfolder=source_subfolder,
        output_excel=output_excel,
        media_type=args.media_type,
        max_pins=max_pins,
        book_title=args.book_title,
        book_url=args.book_url,
        board_name=args.board_name,
        banner_text=args.banner_text,
        watermark_text=args.watermark_text,
    )

    print("[DONE] Pinterest pin Excel generation finished.")


if __name__ == "__main__":
    main()
