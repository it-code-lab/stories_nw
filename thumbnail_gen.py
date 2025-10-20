"""
thumbnail_gen.py
----------------
Generate a YouTube thumbnail composed of:
- Left half: solid background color with multiline text (split by "|")
- Right half: image scaled using "cover" fit (fills panel, cropped as needed)

Features:
- Auto font-size per line to fit available width
- Optional per-line text colors or 'auto' contrast against background
- Robust Devanagari-capable font loading (Noto/Nirmala/Mangal or fonts/ folder)
- Stroke outline for readability

Usage (CLI):
    python thumbnail_gen.py \
      --image "thumbnail_images/krishna.jpg" \
      --bg_color "#101010" \
      --text "Narak Chaturdashi:|नरकासुर वध की|कथा" \
      --colors auto \
      --output "edit_vid_thumbnail/thumbnail.png"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Tuple
import random
from colorsys import rgb_to_hls, hls_to_rgb
from PIL import Image, ImageDraw, ImageFont, ImageOps


# ------------------------ Color helpers ------------------------

def hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rel_luminance(rgb: Tuple[int, int, int]) -> float:
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = map(chan, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    L1, L2 = _rel_luminance(a), _rel_luminance(b)
    L1, L2 = max(L1, L2), min(L1, L2)
    return (L1 + 0.05) / (L2 + 0.05)


def auto_text_color(bg_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """
    Choose an attractive, high-contrast text color automatically.
    It prefers golden, saffron, or turquoise tints when background is dark,
    and deep maroon / navy when background is bright.
    """
    r, g, b = bg_rgb
    lum = 0.299 * r + 0.587 * g + 0.114 * b  # perceived brightness 0–255
    is_dark = lum < 128

    if is_dark:
        palette = [
            (255, 255, 255),      # pure white
            (255, 221, 150),      # soft gold
            (255, 200, 80),       # saffron
            (0, 220, 255),        # bright cyan
            (255, 255, 0),      # Yellow
        ]
    else:
        palette = [
            (20, 20, 20),         # deep charcoal
            (120, 40, 40),        # deep red-brown
            (0, 90, 140),         # navy blue
            (60, 30, 90),         # purple accent
            (90, 60, 0),          # brown-gold
        ]

    # Bias toward first (high contrast) but occasionally pick accent
    choice = random.choices(palette, weights=[6, 3, 2, 1, 1])[0]
    return choice


# ------------------------ Font helpers ------------------------

def _possible_font_paths() -> List[Path]:
    """Common locations + local ./fonts folder (place NotoSansDevanagari-Bold.ttf here)."""
    here = Path(__file__).resolve().parent
    fonts_dir = here / "fonts"

    candidates = [
        # Bundled / local
        fonts_dir / "RozhaOne-Regular.ttf",
        fonts_dir / "NotoSansDevanagari-Bold.ttf",
        # fonts_dir / "NotoSansDevanagari-Regular.ttf",
        # fonts_dir / "NirmalaB.ttf",
        # fonts_dir / "Nirmala.ttf",
        fonts_dir / "MangalB.ttf",
        fonts_dir / "Mangal.ttf",

        # Windows
        Path("C:/Windows/Fonts/RozhaOne-Regular.ttf"),
        Path("C:/Windows/Fonts/NotoSansDevanagari-Bold.ttf"),
        # Path("C:/Windows/Fonts/NirmalaB.ttf"),
        # Path("C:/Windows/Fonts/Nirmala.ttf"),
        Path("C:/Windows/Fonts/Mangalb.ttf"),
        Path("C:/Windows/Fonts/Poppins-Bold.ttf"),
        Path("C:/Windows/Fonts/Poppins-ExtraBold.ttf"),
        # Path("C:/Windows/Fonts/MANGAL.TTF"),

        # macOS (paths vary by version)
        # Path("/System/Library/Fonts/Supplemental/NotoSansDevanagari-Bold.ttf"),
        # Path("/System/Library/Fonts/Supplemental/NotoSansDevanagari-Regular.ttf"),

        # # Linux
        # Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"),
        # Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
    ]
    return [p for p in candidates if p.exists()]


def _can_render(font: ImageFont.FreeTypeFont, sample="क") -> bool:
    """
    Robust 'can render' check:
    - try getlength()
    - then draw to a tiny image and see if bbox has width
    """
    try:
        if hasattr(font, "getlength") and font.getlength(sample) > 0:
            return True
    except Exception:
        pass
    try:
        img = Image.new("L", (256, 128), 0)
        d = ImageDraw.Draw(img)
        box = d.textbbox((0, 0), sample, font=font)
        if box and (box[2] - box[0]) > 0:
            return True
    except Exception:
        pass
    return False

def load_devanagari_font(size: int) -> ImageFont.FreeTypeFont:
    for p in _possible_font_paths():
        try:
            f = ImageFont.truetype(str(p), size)
            if _can_render(f, "क"):
                return f
        except Exception:
            continue
    raise RuntimeError(
        "No Devanagari-capable font found.\n"
        "➡ Solution: put NotoSansDevanagari-Bold.ttf in ./fonts/ next to thumbnail_gen.py"
    )

# Optional: quick one-time diagnoser you can call from __main__
def _debug_list_fonts():
    samples = ["क", "श्री", "लक्ष्मी"]
    print("\n-- Font Diagnostics --")
    for p in _possible_font_paths():
        ok = False
        try:
            f = ImageFont.truetype(str(p), 48)
            ok = all(_can_render(f, s) for s in samples)
        except Exception:
            ok = False
        print(f"{'[OK ]' if ok else '[NO ]'} {p}")
    print("-- End Diagnostics --\n")


def load_devanagari_font(size: int) -> ImageFont.FreeTypeFont:
    """Return a Devanagari-capable font at `size`, or raise a clear error."""
    for p in _possible_font_paths():
        try:
            f = ImageFont.truetype(str(p), size)
            if _can_render(f, "क"):
                return f
        except Exception:
            continue
    raise RuntimeError(
        "No Devanagari-capable font found. "
        "Add NotoSansDevanagari-Bold.ttf to a local ./fonts/ folder next to thumbnail_gen.py."
    )


# ------------------------ Core renderer ------------------------

def _cover_fit(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize & crop to completely fill target size (like CSS background-size: cover)."""
    aspect_img = img.width / img.height
    aspect_target = target_w / target_h

    if aspect_img > aspect_target:
        # Image is wider → fit height, crop sides
        new_h = target_h
        new_w = int(new_h * aspect_img)
        r = img.resize((new_w, new_h), Image.LANCZOS)
        x = (new_w - target_w) // 2
        return r.crop((x, 0, x + target_w, new_h))
    else:
        # Image is taller → fit width, crop top/bottom
        new_w = target_w
        new_h = int(new_w / aspect_img)
        r = img.resize((new_w, new_h), Image.LANCZOS)
        y = (new_h - target_h) // 2
        return r.crop((0, y, new_w, y + target_h))


def create_thumbnail(
    image_path: str,
    bg_color: str,
    text: str,
    colors: str = "auto",
    output_path: str = "thumbnail.png",
    size: Tuple[int, int] = (1280, 720),
    left_ratio: float = 0.5,
    max_font: int = 112,
    min_font: int = 32,
    line_spacing: float = 0.18,
    stroke: int = 4,
) -> None:
    """
    Render thumbnail and save to `output_path`.
    - text: parts separated by "|" (each on a new line)
    - colors: comma list for lines or "auto" (per-line allowed, e.g., "auto,#FFD34E,#fff")
    """
    W, H = size
    left_w = int(W * left_ratio)
    right_w = W - left_w

    # Left panel
    bg_rgb = hex_to_rgb(bg_color)
    left = Image.new("RGB", (left_w, H), bg_rgb)

    # Right image
    if not image_path or not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    right_src = Image.open(image_path).convert("RGB")
    right = _cover_fit(right_src, right_w, H)

    # Compose
    canvas = Image.new("RGB", (W, H))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left_w, 0))
    draw = ImageDraw.Draw(canvas)

    # Text prep
    parts = [p.strip() for p in (text or "").split("|") if p.strip()]
    if not parts:
        canvas.save(output_path, quality=95)
        return

    color_items = [c.strip() for c in (colors or "").split(",")] if colors else []
    if not color_items:
        color_items = ["auto"]

    # Compute sizes that fit width
    available_w = left_w - 120  # side padding
    sized: List[Tuple[str, ImageFont.FreeTypeFont, int, Tuple[int, int, int], float, int]] = []
    for i, part in enumerate(parts):
        # find max size that fits this line
        sz = max_font
        font = load_devanagari_font(sz)
        
        while draw.textlength(part, font=font) > available_w and sz > min_font:
            sz -= 2
            font = load_devanagari_font(sz)

        print(f"Line {i} font size: {sz}")
        print(f"font path used: {font.path}")
        text_w = draw.textlength(part, font=font)
        bbox = draw.textbbox((0, 0), part, font=font, stroke_width=stroke)
        text_h = bbox[3] - bbox[1]

        # color selection
        col_spec = color_items[i] if i < len(color_items) else color_items[-1]
        fill = auto_text_color(bg_rgb) if (col_spec or "").lower() == "auto" else hex_to_rgb(col_spec)

        print(f"Line {i} color: {fill}")

        sized.append((part, font, sz, fill, text_w, text_h))

    # Vertical placement (center block)
    total_h = sum(t[5] for t in sized) + int(sum(t[2] for t in sized) * line_spacing)
    y = (H - total_h) // 2
    x_center = left_w // 2

    # Draw
    for part, font, sz, fill, text_w, text_h in sized:
        x = int(x_center - text_w // 2)
        sw = 2 if sz <= 48 else stroke
        draw.text(
            (x, y),
            part,
            font=font,
            fill=fill,
            stroke_width=sw,
            stroke_fill=(0, 0, 0) if fill != (0, 0, 0) else (255, 255, 255),
        )
        y += text_h + int(sz * line_spacing)

    # Optional tiny border to avoid bleed on some platforms
    # canvas = ImageOps.expand(canvas, border=2, fill=(0, 0, 0))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=95)


# ------------------------ CLI ------------------------

def _parse_size(s: str) -> Tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError("size must be like 1280x720")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate a left-text/right-image thumbnail.")
    ap.add_argument("--image", required=True, help="Right-hand image file path")
    ap.add_argument("--bg_color", default="#101010", help="Left panel background hex")
    ap.add_argument("--text", required=True, help='Use "|" to break lines')
    ap.add_argument("--colors", default="auto",
                    help='Comma list for each line (e.g. "#FFB347,#FFFFFF") or "auto"')
    ap.add_argument("--output", default="thumbnail.png")
    ap.add_argument("--size", type=_parse_size, default=(1280, 720), help="WxH, e.g. 1280x720")
    ap.add_argument("--left_ratio", type=float, default=0.5, help="Left panel width ratio (0–1)")
    args = ap.parse_args()

    create_thumbnail(
        image_path=args.image,
        bg_color=args.bg_color,
        text=args.text,
        colors=args.colors,
        output_path=args.output,
        size=args.size,
        left_ratio=args.left_ratio,
    )
