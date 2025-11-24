from PIL import Image  # pip install pillow
from datetime import datetime
from pathlib import Path
import traceback  # to print detailed error info
import  json


BASE_DIR = Path(__file__).resolve().parent
COLORING_BASE = BASE_DIR

# COLORING_BASE = BASE_DIR / "downloads"
# COLORING_BASE.mkdir(exist_ok=True)

def _ensure_webp_thumb(src_png: Path, dest_webp: Path, edge: int, force: bool = False) -> bool:
    """
    Create/overwrite a WEBP thumbnail from a PNG source.
    Keeps alpha, resizes so the longest edge = edge.
    """
    try:
        if dest_webp.exists() and not force:
            return True

        dest_webp.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(src_png) as im:
            im = im.convert("RGBA")
            w, h = im.size
            ratio = edge / max(w, h)
            nw = max(1, int(round(w * ratio)))
            nh = max(1, int(round(h * ratio)))
            im = im.resize((nw, nh), Image.LANCZOS)
            im.save(dest_webp, "WEBP", quality=80)

        return True
    except Exception:
        traceback.print_exc()
        return False


def build_coloring_manifest(source_subfolder: str | None = None,
                            thumb_edge: int = 640,
                            force: bool = False) -> dict:
    """
    Build a coloring manifest + thumbnails under downloads/.

    - source_subfolder: relative folder under downloads/
        e.g. "", "coloring/v2", "1.Cute Farm Animals"
      The script will treat each immediate subfolder as a 'category'.
      Within each category:
        - If <cat>/pages/ exists, use that as pagesDir.
        - Else use <cat> itself as pagesDir.
    - Thumbs are written into <cat>/thumbs/ as <id>@2x.webp.
    - Manifest is written to <root>/v2.json.

    URL mapping:
      src/thumb = "/quiz/downloads/<path_relative_to_downloads>"
    """
    base_downloads = COLORING_BASE.resolve()
    source_subfolder = (source_subfolder or "").strip().strip("/")

    root = (base_downloads / source_subfolder).resolve()
    if not str(root).startswith(str(base_downloads)):
        raise ValueError(f"Invalid folder outside root/: {root}")

    if not root.is_dir():
        raise FileNotFoundError(f"Folder not found: {root}")

    categories: list[dict] = []
    total_pages = 0
    total_thumbs = 0

    # Immediate subfolders of root are categories
    cat_dirs = [p for p in sorted(root.iterdir(), key=lambda x: x.name.lower()) if p.is_dir()]

    def nice_label(raw: str) -> str:
        clean = raw.replace("_", " ").replace("-", " ")
        return " ".join(word.capitalize() for word in clean.split())

    for cat_dir in cat_dirs:
        slug = cat_dir.name

        pages_dir = cat_dir / "pages"
        if not pages_dir.is_dir():
            # Fallback: treat category folder itself as pages dir
            pages_dir = cat_dir

        thumbs_dir = cat_dir / "thumbs"
        thumbs_dir.mkdir(parents=True, exist_ok=True)

        # Collect PNG + SVG per stem
        files_by_id: dict[str, dict[str, Path]] = {}

        for path in pages_dir.glob("*.png"):
            files_by_id.setdefault(path.stem, {})["png"] = path

        for path in pages_dir.glob("*.svg"):
            files_by_id.setdefault(path.stem, {})["svg"] = path

        if not files_by_id:
            continue

        items: list[dict] = []

        for id_ in sorted(files_by_id.keys(), key=str.lower):
            entry = files_by_id[id_]
            png_path: Path | None = entry.get("png")
            svg_path: Path | None = entry.get("svg")

            if not png_path and not svg_path:
                continue

            # --- Choose src: prefer SVG if available ---
            src_path = svg_path or png_path
            src_ext = src_path.suffix.lstrip(".").lower()

            # --- Size: prefer PNG's size if available ---
            if png_path and png_path.exists():
                try:
                    with Image.open(png_path) as im:
                        w, h = im.size
                except Exception:
                    traceback.print_exc()
                    w, h = 1600, 1200
            else:
                # SVG only – fallback to defaults
                w, h = 1600, 1200

            # --- Thumbnail: prefer PNG; else fall back to SVG URL ---
            if png_path and png_path.exists():
                dest_webp = thumbs_dir / f"{id_}@2x.webp"
                ok = _ensure_webp_thumb(png_path, dest_webp, thumb_edge, force=force)
                if not ok:
                    thumb_url = None
                else:
                    rel_thumb = dest_webp.resolve().relative_to(root).as_posix()
                    thumb_url = f"https://coloring.readernook.com/static/v2/{rel_thumb}"
                    total_thumbs += 1
            elif svg_path and svg_path.exists():
                # No PNG – just use the SVG as thumb URL
                rel_svg = svg_path.resolve().relative_to(root).as_posix()
                thumb_url = f"https://coloring.readernook.com/static/v2/{rel_svg}"
            else:
                thumb_url = None

            # --- Src URL ---
            rel_src = src_path.resolve().relative_to(root).as_posix()
            src_url = f"https://coloring.readernook.com/static/v2/{rel_src}"

            label = nice_label(id_)

            items.append({
                "id": id_,
                "label": label,
                "src": src_url,     # <-- SVG when both exist
                "thumb": thumb_url, # <-- PNG-based WEBP when PNG exists
                "w": w,
                "h": h,
            })

            total_pages += 1

        if items:
            categories.append({
                "id": slug,
                "title": nice_label(slug),
                "items": items,
            })

    manifest = {
        "version": source_subfolder or "root",
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "categories": categories,
    }

    manifest_path = root / "v2.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "version": manifest["version"],
        "categories": len(categories),
        "total_pages": total_pages,
        "total_thumbs": total_thumbs,
    }
