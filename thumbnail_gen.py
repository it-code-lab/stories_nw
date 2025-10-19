import argparse
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pathlib import Path

# ---------- utilities ----------
def hex_to_rgb(h: str):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rel_luminance(rgb):
    # WCAG relative luminance
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = map(chan, rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast_ratio(rgb1, rgb2):
    L1, L2 = rel_luminance(rgb1), rel_luminance(rgb2)
    L1, L2 = max(L1, L2), min(L1, L2)
    return (L1 + 0.05) / (L2 + 0.05)

def auto_text_color(bg_rgb):
    # Compare against white and near-black, choose higher contrast
    white = (255, 255, 255)
    black = (17, 17, 17)
    return white if contrast_ratio(bg_rgb, white) >= contrast_ratio(bg_rgb, black) else black

def load_font_try(paths, size):
    for p in paths:
        p = Path(p)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    # Final fallback (Pillow default; might not render Devanagari correctly)
    return ImageFont.load_default()

# ---------- core ----------
def create_thumbnail(image_path, bg_color, text, colors, output_path,
                     size=(1280, 720), left_ratio=0.5,
                     max_font=112, min_font=32, line_spacing=0.18,
                     stroke=4):
    W, H = size
    left_w = int(W * left_ratio)
    right_w = W - left_w

    # Left panel
    bg_rgb = hex_to_rgb(bg_color)
    left = Image.new("RGB", (left_w, H), bg_rgb)

    # Right image (cover fit)
    right = Image.open(image_path).convert("RGB")
    right_aspect = right.width / right.height
    target_aspect = right_w / H
    if right_aspect > target_aspect:
        # wider than target: crop sides
        new_h = H
        new_w = int(new_h * right_aspect)
        r = right.resize((new_w, new_h), Image.LANCZOS)
        x = (new_w - right_w) // 2
        r = r.crop((x, 0, x + right_w, new_h))
    else:
        # taller than target: crop top/bottom
        new_w = right_w
        new_h = int(new_w / right_aspect)
        r = right.resize((new_w, new_h), Image.LANCZOS)
        y = (new_h - H) // 2
        r = r.crop((0, y, new_w, y + H))

    # Compose
    canvas = Image.new("RGB", (W, H))
    canvas.paste(left, (0, 0))
    canvas.paste(r, (left_w, 0))
    draw = ImageDraw.Draw(canvas)

    # Text prep
    parts = [p.strip() for p in text.split("|")]
    color_items = [c.strip() for c in colors.split(",")] if colors else []
    # Allow 'auto' per line or whole
    if not color_items:
        color_items = ["auto"]
    # Font search order (install at least one Hindi-capable bold font)
    font_candidates = [
        "NotoSansDevanagari-Bold.ttf",    # Linux/mac if installed
        "/System/Library/Fonts/Supplemental/NotoSansDevanagari-Bold.ttf",  # macOS (varies)
        "NotoSansDevanagari.ttf",
        "Lohit-Devanagari.ttf",
        "Arial Unicode.ttf",
        "arialbd.ttf",
    ]

    # 1) Decide font size for each line so it fits width
    available_w = left_w - 120  # side padding
    sized = []  # (text, font, size, fill_rgb, text_w, text_h)
    for i, part in enumerate(parts):
        # initial font
        sz = max_font
        font = load_font_try(font_candidates, sz)
        # shrink to fit width
        while draw.textlength(part, font=font) > available_w and sz > min_font:
            sz -= 2
            font = load_font_try(font_candidates, sz)
        text_w = draw.textlength(part, font=font)
        # height estimate via bbox
        bbox = draw.textbbox((0, 0), part, font=font, stroke_width=stroke)
        text_h = bbox[3] - bbox[1]

        # color selection
        col_spec = color_items[i] if i < len(color_items) else color_items[-1]
        if col_spec.lower() == "auto":
            fill = auto_text_color(bg_rgb)
        else:
            fill = hex_to_rgb(col_spec)

        sized.append((part, font, sz, fill, text_w, text_h))

    # 2) Compute vertical positions (center all lines block)
    total_h = sum(t[5] for t in sized) + int(sum(t[2] for t in sized) * line_spacing)
    y = (H - total_h) // 2

    # 3) Draw lines (centered horizontally in left panel)
    x_center = left_w // 2
    for part, font, sz, fill, text_w, text_h in sized:
        x = x_center - int(text_w // 2)
        # draw subtle stroke for readability (helps on colored backgrounds)
        draw.text((x, y), part, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=(0, 0, 0) if fill != (0, 0, 0) else (255, 255, 255))
        y += text_h + int(sz * line_spacing)

    # 4) optional brand padding/border (comment out if not needed)
    # canvas = ImageOps.expand(canvas, border=2, fill=(0,0,0))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=95)
    print(f"✅ Saved: {output_path}")

# ---------- cli ----------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="Right-hand image path")
    ap.add_argument("--bg_color", default="#000000", help="Left panel background hex")
    ap.add_argument("--text", required=True, help='Use "|" to break lines')
    ap.add_argument("--colors", default="auto",
                    help='Comma list for each line (e.g. "#FFB347,#FFFFFF") or "auto"')
    ap.add_argument("--output", default="thumbnail.png")
    ap.add_argument("--size", default="1280x720", help="WxH (default 1280x720)")
    ap.add_argument("--left_ratio", type=float, default=0.5, help="Left panel width ratio (0-1)")
    args = ap.parse_args()

    W, H = map(int, args.size.lower().split("x"))
    create_thumbnail(
        image_path=args.image,
        bg_color=args.bg_color,
        text=args.text,
        colors=args.colors,
        output_path=args.output,
        size=(W, H),
        left_ratio=args.left_ratio
    )
