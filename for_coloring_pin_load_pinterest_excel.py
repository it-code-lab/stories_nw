# generate_excel.py
import argparse
import sys
import json
from pathlib import Path
import json
from gemini_pool import GeminiPool  # same helper you use in get_seo_meta_data.py
import random
from openpyxl import Workbook
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageFilter

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi"}

CONFIG_FILENAME = "pinterest_config.json"


# Gemini settings
DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 256

# Global gemini_pool – initialised in main guard
gemini_pool = None


PINTEREST_SYSTEM_INSTRUCTION = """
You are a Pinterest marketing assistant for digital coloring books sold on goodsandgift.com.

Goal:
Given information about a specific coloring book page (sample, cover, or activity page), generate:
- A compelling Pinterest Pin title
- A persuasive but natural Pinterest Pin description
- A small set of relevant hashtags / tags

Audience:
- Parents looking for printable coloring pages for kids
- Teachers and homeschoolers
- Adults who enjoy relaxing coloring (for some books)

General rules:
- Use simple, friendly language.
- Emphasize benefits: printable, instant download, number of pages, fun themes, age range if provided.
- Highlight that it’s a DIGITAL DOWNLOAD (no physical item shipped).
- Include keywords like "coloring page", "coloring book", "printable", "digital download", "kids activities", where appropriate.
- Avoid clickbait or ALL CAPS.

Title rules:
- Max ~80 characters (Pinterest will truncate long titles anyway).
- Include the main theme (e.g., farm animals, dinosaurs, mandalas, etc.).
- Mention "coloring page" or "coloring book".

Description rules:
- 1–3 short sentences.
- 140–300 characters is ideal.
- Mention what’s included (e.g., number of pages in the book, theme, target age if known).
- Encourage saving the Pin or downloading/printing later.

Tags rules:
- 5–12 items.
- Each tag should be a hashtag string, e.g. "#coloringpages".
- Mix of broad and specific tags: e.g., "#coloringpages", "#printablecoloring", "#kidsactivities", "#mandalacoloring", "#farmanimals", etc.
- No duplicates.

Return STRICT JSON with this schema only:

{
  "pin_title": "string",
  "pin_description": "string",
  "tags": ["#tag1", "#tag2", "#tag3"]
}

Do not include any commentary or text outside this JSON.
"""

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
    fit_mode: str = "contain",          # "contain" (no crop) or "cover" (crop)
    bg_style: str = "white",            # "white" or "blur"
    text_shadow: bool = True,
) -> Path:
    """
    Create a Pinterest-friendly image:

    - target canvas size: 1000 x 1500
    - fit_mode:
        * "contain": whole image visible, letterboxed if needed (NO CROPPING)
        * "cover"  : image cropped to fill the canvas
    - bg_style:
        * "white": plain white background
        * "blur" : blurred version of the original image behind the main image
    - text_shadow: draws a subtle shadow behind banner & watermark text.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    base_img = Image.open(src).convert("RGB")
    orig_w, orig_h = base_img.size
    tgt_w, tgt_h = target_size

    # -------- Background --------
    if bg_style == "blur":
        # Use a blurred "cover" version of the image as background
        scale_bg = max(tgt_w / orig_w, tgt_h / orig_h)
        bg_w = int(orig_w * scale_bg)
        bg_h = int(orig_h * scale_bg)
        bg = base_img.resize((bg_w, bg_h), Image.LANCZOS)

        left = (bg_w - tgt_w) // 2
        top = (bg_h - tgt_h) // 2
        bg = bg.crop((left, top, left + tgt_w, top + tgt_h))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
        # Slight darken so foreground pops
        dark_overlay = Image.new("RGBA", (tgt_w, tgt_h), (0, 0, 0, 60))
        bg_rgba = bg.convert("RGBA")
        bg_rgba.alpha_composite(dark_overlay, (0, 0))
        canvas = bg_rgba.convert("RGB")
    else:
        # Plain white background
        canvas = Image.new("RGB", (tgt_w, tgt_h), "white")

    # -------- Foreground (main page) --------
    if fit_mode == "cover":
        # Crop to fill
        main = base_img.copy()
        main = ImageOps.fit(main, (tgt_w, tgt_h), method=Image.LANCZOS)
        # Slight inset so banner/watermark don't cover important edges
        inset = 40
        main = main.resize((tgt_w - inset * 2, tgt_h - inset * 2), Image.LANCZOS)
        mx = inset
        my = inset
    else:
        # contain – NO CROPPING
        scale = min(tgt_w / orig_w, tgt_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        main = base_img.resize((new_w, new_h), Image.LANCZOS)
        mx = (tgt_w - new_w) // 2
        my = (tgt_h - new_h) // 2

    canvas.paste(main, (mx, my))

    draw = ImageDraw.Draw(canvas)

    # Fonts
    try:
        font = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    W, H = canvas.size

    # Helpers ----------------------------------------------------
    def measure(text: str, font_obj):
        if not text:
            return (0, 0)
        bbox = draw.textbbox((0, 0), text, font=font_obj)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])

    def draw_text_with_shadow(x, y, text, font_obj, fill="white"):
        if not text:
            return
        if text_shadow:
            # Simple dark shadow offset
            shadow_offset = 2
            draw.text((x + shadow_offset, y + shadow_offset),
                      text, font=font_obj, fill="black")
        draw.text((x, y), text, font=font_obj, fill=fill)

    # -------- Banner at top --------
    if banner_text:
        banner_h = int(H * 0.12)
        banner_overlay = Image.new("RGBA", (W, banner_h), (0, 0, 0, 150))
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.alpha_composite(banner_overlay, (0, 0))
        canvas = canvas_rgba.convert("RGB")
        draw = ImageDraw.Draw(canvas)

        tw, th = measure(banner_text, font)
        tx = (W - tw) / 2
        ty = (banner_h - th) / 2
        draw_text_with_shadow(tx, ty, banner_text, font)

    # -------- Watermark at bottom --------
    if watermark_text:
        wm_h = int(H * 0.08)
        wm_overlay = Image.new("RGBA", (W, wm_h), (0, 0, 0, 130))
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.alpha_composite(wm_overlay, (0, H - wm_h))
        canvas = canvas_rgba.convert("RGB")
        draw = ImageDraw.Draw(canvas)

        tw, th = measure(watermark_text, font_small)
        tx = (W - tw) / 2
        ty = H - wm_h + (wm_h - th) / 2
        draw_text_with_shadow(tx, ty, watermark_text, font_small)

    # -------- Save --------
    out_path = out_dir / (src.stem + "_pin.webp")
    canvas.save(out_path, "WEBP", quality=90)
    return out_path

def make_pinterest_image_working_DND(
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
    fit_mode: str = "contain",
    bg_style: str = "white",
    text_shadow: bool = True,
    use_gemini: bool = False,          # <--- NEW
    base_tags: str | None = None,      # <--- optional - from config if you add it
) -> None:
    # 1) Load config (if present)
    cfg = load_book_config(images_root, source_subfolder)

    # 2) Resolve final values (UI/CLI overrides config)
    book_title = (book_title or cfg.get("book_title") or "Coloring Book").strip()
    book_url = (book_url or cfg.get("book_url") or "").strip()
    board_name = (board_name or cfg.get("board_name") or "").strip()
    banner_text = (banner_text or cfg.get("banner_text") or "").strip() or None
    watermark_text = (watermark_text or cfg.get("watermark_text") or "").strip() or None
    base_tags = base_tags or cfg.get("base_tags") or ""

    print(f"[INFO] Using values:")
    print(f"  book_title   = {book_title!r}")
    print(f"  book_url     = {book_url!r}")
    print(f"  board_name   = {board_name!r}")
    print(f"  banner_text  = {banner_text!r}")
    print(f"  watermark_text = {watermark_text!r}")
    print(f"  use_gemini = {use_gemini!r}")

    media_files = collect_media_files(images_root, source_subfolder)

    # Randomize the file order
    random.shuffle(media_files)

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
                    fit_mode=fit_mode,
                    bg_style=bg_style,
                    text_shadow=text_shadow,                    
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


        error_msg = ""
        try:
            if use_gemini:
                meta = generate_pin_meta_with_gemini(
                    book_title=book_title,
                    product_url=book_url,
                    page_label=page_label,
                    base_tags=base_tags,
                    pin_role="sample_page",
                )
            else:
                meta = fallback_pin_meta(book_title, book_url, page_label, base_tags)
        except Exception as e:
            print(f"[WARN] Gemini meta failed for {f.name}: {e}")
            error_msg = f"Gemini meta failed: {e}"
            meta = fallback_pin_meta(book_title, book_url, page_label, base_tags)

        pin_title = meta["pin_title"]
        pin_description = meta["pin_description"]
        tags_str = meta["tags_str"]

        # base_tags = [
        #     "coloring pages",
        #     "printable coloring",
        #     "kids coloring",
        #     "relaxing art",
        #     "coloring book",
        # ]
        # extra_tag = page_label.split()[0] if page_label else ""
        # tags_str = ", ".join(base_tags + ([extra_tag] if extra_tag else []))

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
            error_msg,  # or keep a separate error column if you like
        ]
        ws.append(row)

    output_excel.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_excel)
    print(f"[OK] Excel written to: {output_excel}")

def generate_pin_meta_with_gemini(
    book_title: str,
    product_url: str,
    page_label: str | None,
    base_tags: str | None,
    pin_role: str = "sample_page",
) -> dict:
    """
    Calls Gemini via GeminiPool to generate pin_title, pin_description, tags[].
    Returns dict; may raise or return fallback if something fails.
    """

    print(f"[INFO] Generating Pinterest meta with Gemini for page: {page_label!r}")

    global gemini_pool
    if gemini_pool is None:
        raise RuntimeError("gemini_pool is not initialised")

    base_tags = (base_tags or "").strip()

    context = {
        "book_title": book_title,
        "product_url": product_url,
        "page_label": page_label or "",
        "pin_role": pin_role,
        "base_tags": base_tags,
    }

    prompt = f"""{PINTEREST_SYSTEM_INSTRUCTION}

Now create metadata for one Pinterest Pin.

Context (JSON):
{json.dumps(context, ensure_ascii=False, indent=2)}
"""

    raw = gemini_pool.generate_text(
        prompt=prompt,
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_output_tokens=DEFAULT_MAX_TOKENS,
    )

    if not raw:
        raise RuntimeError("Empty response from Gemini for Pinterest meta")

    raw = raw.strip()

    if not raw.startswith("{"):
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1 and last > first:
            raw = raw[first:last + 1]

    data = json.loads(raw)

    pin_title = str(data.get("pin_title", "")).strip()
    pin_description = str(data.get("pin_description", "")).strip()
    tags = data.get("tags", [])

    if isinstance(tags, list):
        tags_str = ", ".join(str(t).strip() for t in tags if str(t).strip())
    else:
        tags_str = str(tags).strip()

    if not pin_title:
        raise RuntimeError("Gemini response missing pin_title")

    return {
        "pin_title": pin_title,
        "pin_description": pin_description,
        "tags_str": tags_str,
    }


def fallback_pin_meta(book_title: str, product_url: str, page_label: str | None, base_tags: str | None) -> dict:
    print("[INFO] Using fallback pin metadata generation.")
    base_tags = (base_tags or "").strip()
    if base_tags:
        tags_str = base_tags
    else:
        tags_str = "#coloringpages, #printablecoloring, #kidsactivities, #digitaldownload"

    if page_label:
        title = f"{book_title} – {page_label} Coloring Page"
    else:
        title = f"{book_title} – Printable Coloring Page"

    desc = (
        f"Download and print this coloring page from the '{book_title}' digital coloring book. "
        f"Perfect for creative, screen-free time at home or in the classroom. Instant digital download."
    )

    return {
        "pin_title": title,
        "pin_description": desc,
        "tags_str": tags_str,
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate Pinterest Pin Excel from images/videos.")
    parser.add_argument("--images-root", required=True, help="Root images folder (e.g. application/downloads)")
    parser.add_argument("--source-subfolder", default="", help="Subfolder under images-root, e.g. '1.Cute Farm Animals/pages'")
    parser.add_argument("--output-excel", default="pinterest_pins.xlsx", help="Output Excel filename")
    parser.add_argument("--media-type", choices=["image", "video"], default="image")
    parser.add_argument("--max-pins", type=int, default=0, help="Max pins to generate (0 = all)")

    parser.add_argument(
        "--fit-mode",
        choices=["contain", "cover"],
        default="contain",
        help="How to fit the image into the Pinterest canvas (contain=no crop, cover=crop)."
    )
    parser.add_argument(
        "--bg-style",
        choices=["white", "blur"],
        default="white",
        help="Background style behind the page (white or blurred image)."
    )
    parser.add_argument(
        "--text-shadow",
        choices=["yes", "no"],
        default="yes",
        help="Enable or disable text shadow for banner and watermark."
    )

    parser.add_argument(
        "--use-gemini",
        choices=["yes", "no"],
        default="no",
        help="Use Gemini API to generate Pinterest titles/descriptions/tags.",
    )
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

    text_shadow = (args.text_shadow.lower() == "yes")
    use_gemini = (args.use_gemini.lower() == "yes")
    global gemini_pool
    if use_gemini:
        GEM_STATE = Path(__file__).resolve().parent / ".gemini_pool_state_pinterest.json"
        gemini_pool = GeminiPool(
            api_keys=None,          # load from env/config, same as your SEO script
            per_key_rpm=25,
            state_path=str(GEM_STATE),
            autosave_every=3,
        )

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
        fit_mode=args.fit_mode,
        bg_style=args.bg_style,
        text_shadow=text_shadow,
        use_gemini=use_gemini,
        base_tags=None,  # or pre-read/CLI if you like
    )


    print("[DONE] Pinterest pin Excel generation finished.")


if __name__ == "__main__":
    main()
