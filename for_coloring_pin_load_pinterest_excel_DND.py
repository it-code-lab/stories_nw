import os
import json
import time
import argparse
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from gemini_pool import GeminiPool  # same helper you already use


# ==============================
# CONFIG
# ==============================

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_EXCEL_DEFAULT = BASE_DIR / "master_shorts_uploader_data.xlsx"
PIN_MEDIA_ROOT = BASE_DIR / "pinterest_media"

PIN_WIDTH = 1000
PIN_HEIGHT = 1500

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


# ==============================
# HELPERS – FILE / IMAGE
# ==============================

def slugify(text: str) -> str:
    import re
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "book"


def find_book_row(book_excel_path: Path, source_folder: str) -> dict:
    """
    Read the book info Excel and return a dict for the row
    matching the given folder name.

    Expected columns:
      - folder       (e.g. "1.Cute Farm Animals")
      - book_title
      - product_url
      - board_name
      - base_tags   (optional, comma-separated)

    You can adjust this to your actual sheet structure.
    """
    df = pd.read_excel(book_excel_path)

    if "folder" not in df.columns:
        raise ValueError("Book info Excel must contain a 'folder' column.")

    # Try exact match first
    row = df.loc[df["folder"].astype(str).str.strip() == source_folder]
    if row.empty:
        # Fallback: substring match inside source_folder path
        row = df.loc[df["folder"].astype(str).apply(lambda v: v in source_folder)]
    if row.empty:
        raise ValueError(f"No matching 'folder' row found in {book_excel_path} for source_folder={source_folder!r}")

    r = row.iloc[0]

    return {
        "folder": str(r.get("folder", "")).strip(),
        "book_title": str(r.get("book_title", "")).strip(),
        "product_url": str(r.get("product_url", "")).strip(),
        "board_name": str(r.get("board_name", "")).strip(),
        "base_tags": str(r.get("base_tags", "")).strip(),
    }


def collect_image_files(source_folder: Path, max_pins: int) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg"}
    files = [
        p for p in sorted(source_folder.iterdir())
        if p.is_file() and p.suffix.lower() in exts
    ]
    if max_pins and max_pins > 0:
        return files[:max_pins]
    return files


def ensure_output_df(excel_path: Path) -> pd.DataFrame:
    cols = [
        "id",
        "media_type",
        "media_path",
        "book_title",
        "page_label",
        "pin_title",
        "pin_description",
        "link_url",
        "board_name",
        "tags",
        "status",
        "error_message",
        "scheduled_date",
        "created_at",
        "pin_notes",
    ]
    if excel_path.exists():
        df = pd.read_excel(excel_path)
        # ensure all columns exist
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        return df[cols]
    else:
        return pd.DataFrame(columns=cols)


def draw_pin_image(
    src_path: Path,
    dest_path: Path,
    book_title: str,
    page_label: str | None = None,
    watermark_text: str | None = None,
) -> Path:
    """
    Create a 1000x1500 Pinterest-ready image:
      - white background
      - source image centered
      - banner at bottom with book title + optional page label
      - optional small watermark
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Base canvas
    canvas = Image.new("RGB", (PIN_WIDTH, PIN_HEIGHT), "white")

    img = Image.open(src_path).convert("RGB")
    # Fit source image within a margin
    max_w = PIN_WIDTH - 80
    max_h = PIN_HEIGHT - 260  # leave room for banner/watermark
    img.thumbnail((max_w, max_h), Image.LANCZOS)

    # Center on canvas
    x = (PIN_WIDTH - img.width) // 2
    y = (PIN_HEIGHT - img.height) // 2 - 40
    canvas.paste(img, (x, y))

    draw = ImageDraw.Draw(canvas)

    # Try to load a font; fallback to default if missing
    try:
        # Adjust font path to your system if needed
        font_title = ImageFont.truetype("arial.ttf", 42)
        font_sub = ImageFont.truetype("arial.ttf", 28)
        font_watermark = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_watermark = ImageFont.load_default()

    # Banner at bottom
    banner_h = 160
    banner_y0 = PIN_HEIGHT - banner_h
    banner_y1 = PIN_HEIGHT
    banner_color = (248, 249, 252)

    draw.rectangle([0, banner_y0, PIN_WIDTH, banner_y1], fill=banner_color)

    # Title text
    title_text = book_title or "Coloring Book"
    if page_label:
        subtitle_text = page_label
    else:
        subtitle_text = "Printable coloring page"

    # Centered title
    tw, th = draw.textsize(title_text, font=font_title)
    tx = (PIN_WIDTH - tw) // 2
    ty = banner_y0 + 20
    draw.text((tx, ty), title_text, fill=(20, 20, 20), font=font_title)

    # Subtitle
    sw, sh = draw.textsize(subtitle_text, font=font_sub)
    sx = (PIN_WIDTH - sw) // 2
    sy = ty + th + 10
    draw.text((sx, sy), subtitle_text, fill=(70, 70, 70), font=font_sub)

    # Watermark at bottom
    if watermark_text:
        ww, wh = draw.textsize(watermark_text, font=font_watermark)
        wx = (PIN_WIDTH - ww) // 2
        wy = banner_y1 - wh - 12
        draw.text((wx, wy), watermark_text, fill=(130, 130, 130), font=font_watermark)

    canvas.save(dest_path, format="PNG", optimize=True)
    return dest_path


# ==============================
# HELPERS – GEMINI PIN META
# ==============================

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
        f"Perfect for creative screen-free time at home or in the classroom. Instant download from goodsandgift.com."
    )

    return {
        "pin_title": title,
        "pin_description": desc,
        "tags_str": tags_str,
    }


# ==============================
# MAIN LOGIC
# ==============================

def build_pins_excel(
    source_folder: str,
    book_info_excel: str,
    output_excel: str | Path = OUTPUT_EXCEL_DEFAULT,
    media_type: str = "image",
    max_pins: int = 20,
    watermark_text: str | None = "Creative Cubs",
    use_gemini: bool = True,
):
    source_folder = source_folder.strip().rstrip("/\\")
    excel_path = Path(output_excel)
    book_info_path = Path(book_info_excel)

    # Resolve source folder relative to BASE_DIR if not absolute
    sf_path = Path(source_folder)
    if not sf_path.is_absolute():
        sf_path = BASE_DIR / sf_path

    if not sf_path.exists():
        raise FileNotFoundError(f"Source folder not found: {sf_path}")

    if not book_info_path.is_absolute():
        book_info_path = BASE_DIR / book_info_path

    if not book_info_path.exists():
        raise FileNotFoundError(f"Book info Excel not found: {book_info_path}")

    book_row = find_book_row(book_info_path, source_folder)
    book_title = book_row["book_title"]
    product_url = book_row["product_url"]
    board_name = book_row["board_name"]
    base_tags = book_row["base_tags"]

    print(f"[INFO] Book: {book_title}")
    print(f"[INFO] URL:  {product_url}")
    print(f"[INFO] Board: {board_name}")
    print(f"[INFO] Base tags: {base_tags}")

    df = ensure_output_df(excel_path)
    next_id = (df["id"].max() if not df["id"].isna().all() else 0) + 1

    # Collect images for image pins
    if media_type in ("image", "both"):
        images = collect_image_files(sf_path, max_pins=max_pins)
        print(f"[INFO] Found {len(images)} images to process.")

        book_slug = slugify(book_title or sf_path.name)
        pin_media_dir = PIN_MEDIA_ROOT / book_slug
        pin_media_dir.mkdir(parents=True, exist_ok=True)

        for idx, img_path in enumerate(images, start=1):
            page_label = f"Page {idx}"
            pin_filename = f"{img_path.stem}_pin.png"
            out_path = pin_media_dir / pin_filename

            print(f"[PIN] {img_path.name} → {out_path.name}")

            draw_pin_image(
                src_path=img_path,
                dest_path=out_path,
                book_title=book_title,
                page_label=page_label,
                watermark_text=watermark_text,
            )

            # Generate meta (Gemini or fallback)
            error_message = ""
            try:
                if use_gemini:
                    meta = generate_pin_meta_with_gemini(
                        book_title=book_title,
                        product_url=product_url,
                        page_label=page_label,
                        base_tags=base_tags,
                        pin_role="sample_page",
                    )
                else:
                    meta = fallback_pin_meta(book_title, product_url, page_label, base_tags)
            except Exception as e:
                print(f"[WARN] Gemini meta failed for {img_path.name}: {e}")
                error_message = f"Gemini meta failed: {e}"
                meta = fallback_pin_meta(book_title, product_url, page_label, base_tags)

            row = {
                "id": int(next_id),
                "media_type": "image",
                "media_path": str(out_path.resolve()),
                "book_title": book_title,
                "page_label": page_label,
                "pin_title": meta["pin_title"],
                "pin_description": meta["pin_description"],
                "link_url": product_url,
                "board_name": board_name,
                "tags": meta["tags_str"],
                "status": "pending",
                "error_message": error_message,
                "scheduled_date": "",
                "created_at": time.strftime("%Y-%m-%d"),
                "pin_notes": "",
            }

            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            next_id += 1

    # TODO: later, add video pin generation here if needed.

    df.to_excel(excel_path, index=False)
    print(f"[DONE] Saved pins Excel: {excel_path}")


def parse_args():
    p = argparse.ArgumentParser(description="Generate Pinterest pins Excel from coloring book images.")
    p.add_argument("--source_folder", required=True, help="Folder with source images (relative to BASE_DIR or absolute).")
    p.add_argument("--book_info_excel", required=True, help="Excel file with book-level info (folder, book_title, product_url, board_name, base_tags).")
    p.add_argument("--output_excel", default=str(OUTPUT_EXCEL_DEFAULT), help="Output Excel file (default: master_shorts_uploader_data.xlsx in script folder).")
    p.add_argument("--media_type", choices=["image", "video", "both"], default="image", help="Type of pins to generate (image/video/both).")
    p.add_argument("--max_pins", type=int, default=20, help="Maximum number of pins to generate from this folder.")
    p.add_argument("--watermark_text", default="goodsandgift.com", help="Optional watermark text to draw on pins.")
    p.add_argument("--use_gemini", choices=["yes", "no"], default="yes", help="Use Gemini API to generate titles/descriptions/tags.")
    return p.parse_args()


if __name__ == "__main__":
    # Initialise GeminiPool similar to get_seo_meta_data.py
    GEM_STATE = str(BASE_DIR / ".gemini_pool_state.json")
    gemini_pool = GeminiPool(
        api_keys=None,          # load from env / config
        per_key_rpm=25,
        state_path=GEM_STATE,
        autosave_every=3,
    )

    args = parse_args()

    build_pins_excel(
        source_folder=args.source_folder,
        book_info_excel=args.book_info_excel,
        output_excel=args.output_excel,
        media_type=args.media_type,
        max_pins=args.max_pins,
        watermark_text=args.watermark_text or None,
        use_gemini=(args.use_gemini.lower() == "yes"),
    )
