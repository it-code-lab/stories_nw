import shutil
from time import time
from flask import Flask, request, jsonify, render_template, send_from_directory, abort, url_for
import subprocess, json, math
from flask_cors import CORS
import os
import traceback
import contentplanner_worker as cpw

import openpyxl  # to print detailed error info
from build_coloring_app_manifest import build_coloring_manifest
from caption_generator import prepare_captions_file_for_notebooklm_audio
from facebook_uploader import upload_facebook_videos
from get_audio import get_audio_file
from instagram_uploader import upload_instagram_posts
from pinterest_uploader import upload_pins
from scene_builder import render_background_and_merge
from scraper import scrape_and_process  # Ensure this exists
from settings import background_music_options, font_settings, tts_engine, voices, sizes
from tiktok_uploader import upload_tiktok_videos
from video_editor import batch_process
from youtube_uploader import upload_shorts_from_master_file, upload_videos
import re
from pathlib import Path
import wave
from urllib.parse import unquote
from polish_audio_auto import polish_audio  # NEW
from auto_mix import mix_files
from quiz import quiz_bp
from flask import send_file
import tempfile
from coloring_upscale import process_coloring_folder
# from google import genai
# from google.genai import types
import os
from flipthrough_video import generate_flipthrough_video, FlipThroughError
from bg_music_video import merge_all_videos_with_bg_music, merge_video_with_bg_music, BgMusicError
import sys
from pdf2image import convert_from_path
import glob
import uuid
from coloring_animation import _create_coloring_animation, _create_coloring_animation_by_color
from sketch_core import build_sketch_from_pil
from PIL import Image
from scene_builder import probe_duration, make_scene, merge_with_heygen
from assemble_from_videos import assemble_videos, assemble_videos_by_titles_if_present

from media_audio import (
    extract_audio_from_video,
    resolve_input_video,
)
# ---- ADD near the top with imports (server.py) ----
import shutil

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

def _ensure_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg not found in PATH. Please install FFmpeg and add it to PATH.")
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found in PATH. Please install FFmpeg tools and add to PATH.")


app = Flask(__name__, template_folder='templates')
app.register_blueprint(quiz_bp)  # all quiz endpoints live under /api/quiz
CORS(app)

# Always resolve relative to this file (server.py)
BASE_DIR = Path(__file__).resolve().parent
AUDIO_PATH = BASE_DIR / "audio.wav"   # your file is beside server.py

COLORING_BASE = BASE_DIR / "downloads"
COLORING_BASE.mkdir(exist_ok=True)

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PAGES_FOLDER = os.path.join(BASE_DIR, "static", "pages")
STATIC_FOLDER = os.path.join(BASE_DIR, "static")

DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
OUT_DIR = BASE_DIR / "out"

UPLOADS_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PAGES_FOLDER, exist_ok=True)

POPPLER_PATH = r"C:\poppler-25.11.0\Library\bin"  # Adjust this path as needed

# =========================
# Defaults (env-overridable)
# =========================
DEFAULT_TEXT_MODEL  = os.getenv("GEMINI_DEFAULT_TEXT_MODEL",  "gemini-2.0-flash")
DEFAULT_IMAGE_MODEL = os.getenv("GEMINI_DEFAULT_IMAGE_MODEL", "gemini-2.5-flash-image")


# Optional: central place to tweak RPM/paths
GEM_STATE = str(BASE_DIR / ".gemini_pool_state.json")

gemini_pool = None

@app.post("/build_coloring_manifest")
def build_coloring_manifest_route():
    """
    Build coloring manifest + thumbnails under downloads/.

    Expects form-data or JSON:
      - source_folder: relative folder under downloads/
          e.g. "" (for BASE_DIR/downloads),
               "coloring/v2",
               "1.Cute Farm Animals"
      - force: "0" or "1" (optional, default 0)
    """
    try:
        data = request.get_json(silent=True) or request.form
        source_folder = (data.get("source_folder") or "").strip()
        force_raw = (data.get("force") or "0").strip().lower()
        force = force_raw in ("1", "true", "yes", "y", "on")

        result = build_coloring_manifest(
            source_subfolder=source_folder,
            thumb_edge=640,
            force=force,
        )
        result["ok"] = True
        result["source_folder"] = source_folder
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/upload_media")
def upload_media():
    f = request.files.get("file")
    if not f:
        return "missing file", 400

    name = f.filename or "upload.bin"
    ext = os.path.splitext(name)[1].lower()
    safe = f"{os.urandom(8).hex()}{ext}"
    dst = UPLOADS_DIR / safe
    f.save(dst)

    mime = (f.mimetype or "").lower()
    if mime.startswith("image/"):
        t = "image"
    elif mime.startswith("video/"):
        t = "video"
    else:
        return "unsupported type", 400

    return jsonify({"url": f"/uploads/{safe}", "type": t})

@app.post("/planner/populate_images_excel")
def planner_populate_images_excel():
    channel = (request.form.get("youtube_channel_name") or "").strip()
    if not channel:
        return jsonify({"ok": False, "message": "youtube_channel_name required"}), 400
    res = cpw.populate_image_jobs_excel_for_channel(channel)
    return jsonify(res)

@app.post("/planner/populate_heygen_excel")
def planner_populate_heygen_excel():
    channel = (request.form.get("youtube_channel_name") or "").strip()
    if not channel:
        return jsonify({"ok": False, "message": "youtube_channel_name required"}), 400
    res = cpw.populate_heygen_submit_excel_for_channel(channel)
    return jsonify(res)

@app.post("/planner/populate_upload_excel")
def planner_populate_upload_excel():
    channel = (request.form.get("youtube_channel_name") or "").strip()
    if not channel:
        return jsonify({"ok": False, "message": "youtube_channel_name required"}), 400
    res = cpw.populate_upload_excel_for_channel(channel)
    return jsonify(res)

@app.post("/planner/populate_upload_excel_long")
def planner_populate_upload_excel_long():
    channel = (request.form.get("youtube_channel_name") or "").strip()
    if not channel:
        return jsonify({"ok": False, "message": "youtube_channel_name required"}), 400
    res = cpw.populate_upload_excel_long_for_channel(channel)
    return jsonify(res)

@app.post("/planner/populate_order_excel")
def planner_populate_order_excel():
    channel = (request.form.get("youtube_channel_name") or "").strip()
    if not channel:
        return jsonify({"ok": False, "message": "youtube_channel_name required"}), 400
    return cpw.populate_section_order_excel_from_db(channel)


@app.post("/planner/populate_heygen_bulk_bg_excel")
def populate_heygen_bulk_bg_excel():
    channel = (request.form.get("youtube_channel_name") or "").strip()
    if not channel:
        return jsonify({"ok": False, "message": "youtube_channel_name required"}), 400
    return cpw.populate_heygen_bulk_bg_excel_from_db(channel)


@app.get("/uploads/<path:fn>")
def uploads(fn):
    return send_from_directory(str(UPLOADS_DIR), fn)

@app.post("/save_timeline")
def save_timeline():
    payload = request.get_json(force=True)
    (OUT_DIR / "timeline.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return "Saved to out/timeline.json"

def _safe_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^\w\-. ]+", "", s)
    s = s.replace(" ", "_")
    return s or "out"

def _resolve_path(p: str) -> Path:
    p = (p or "").strip().strip('"').strip("'")
    if not p:
        return Path("")
    pp = Path(p)
    return pp if pp.is_absolute() else (BASE_DIR / pp).resolve()

@app.post("/render_bulk_bg")
def render_bulk_bg(orientation="", scale_bg="yes", copy_as_is=True):
    """
    Reads BASE_DIR/heygen_bulk_bg.xlsx with columns:
      - heygen_video : path to HeyGen mp4
      - bg          : path to background image/video

    For each row:
      1) Create background video matching HeyGen duration
      2) Chroma-key merge (keeps HeyGen captions + avatar bubble untouched/unaltered)
      3) Output filename defaults to ORIGINAL HeyGen filename (same name) in OUT_DIR
    """
    try:
        excel_path = (BASE_DIR / "heygen_bulk_bg.xlsx").resolve()
        if not excel_path.exists():
            return jsonify({"ok": False, "error": f"Missing Excel: {excel_path}"}), 400

        if orientation.lower() not in ("landscape", "portrait"):
             out_res = request.form.get("outRes", "1080x1920")
        else:
            out_res = "1920x1080" if orientation.lower() == "landscape" else "1080x1920"

        chroma_key = "0x00FF00"  # HeyGen green export

        wb = openpyxl.load_workbook(excel_path)
        ws = wb.active

        # header -> index
        headers = {}
        for c in range(1, ws.max_column + 1):
            v = ws.cell(row=1, column=c).value
            if v:
                headers[str(v).strip().lower()] = c

        if "heygen_video" not in headers or "bg" not in headers:
            return jsonify({
                "ok": False,
                "error": "Excel must have header columns: heygen_video, bg"
            }), 400

        # Ensure 'status' column exists
        if "status" not in headers:
            status_col = ws.max_column + 1
            ws.cell(row=1, column=status_col).value = "status"
            headers["status"] = status_col
        else:
            status_col = headers["status"]


        results = []
        for r in range(2, ws.max_row + 1):
            heygen_raw = ws.cell(r, headers["heygen_video"]).value
            bg_raw = ws.cell(r, headers["bg"]).value

            status_val = ws.cell(r, status_col).value
            if status_val and str(status_val).strip().lower() == "success":
                results.append({
                    "row": r,
                    "ok": True,
                    "skipped": True,
                    "reason": "already processed"
                })
                continue

            if status_val and str(status_val).strip().lower() == "success (copied as is)":
                results.append({
                    "row": r,
                    "ok": True,
                    "skipped": True,
                    "reason": "already processed"
                })
                continue

            if not heygen_raw and not bg_raw:
                continue

            heygen_path = _resolve_path(str(heygen_raw))

            if not heygen_path.exists():
                results.append({"row": r, "ok": False, "error": f"HeyGen not found: {heygen_path}"})
                ws.cell(row=r, column=status_col).value = "HeyGen video not found"
                wb.save(excel_path)   # ✅ save immediately (important)
                continue

            if not bg_raw:
                if not copy_as_is:
                    results.append({"row": r, "ok": False, "error": f"BG not found: {bg_raw}"})
                    ws.cell(row=r, column=status_col).value = "BG asset not found"
                    wb.save(excel_path)   # ✅ save immediately (important)
                    continue
                else:
                    bg_asset = None
                    # copy HeyGen as is 
                    final_out = (OUT_DIR / f"{heygen_path.stem}{heygen_path.suffix}").resolve()
                    shutil.copy2(heygen_path, final_out)
                    ws.cell(row=r, column=status_col).value = "success (copied as is)"
                    wb.save(excel_path)   # ✅ save immediately (important)
                    continue

            bg_asset = _resolve_path(str(bg_raw))

            if bg_asset.suffix.lower() == ".mp4" and not bg_asset.exists():
                png_fallback = bg_asset.with_suffix(".png")
                if png_fallback.exists():
                    bg_asset = png_fallback  # use the png instead


            if not bg_asset.exists():
                results.append({"row": r, "ok": False, "error": f"BG not found: {bg_asset}"})
                ws.cell(row=r, column=status_col).value = "BG asset not found"
                wb.save(excel_path)   # ✅ save immediately (important)
                continue

            # 1) duration = HeyGen duration
            dur = probe_duration(heygen_path)

            # 2) build one full background clip (image loops / video holds last frame)
            work_dir = (OUT_DIR / "bulk_work").resolve()
            work_dir.mkdir(exist_ok=True)
            bg_video = work_dir / f"{_safe_name(heygen_path.stem)}__bg.mp4"

            make_scene(asset=bg_asset, duration=dur, out_path=bg_video, out_res=out_res)

            # 3) output file name = same as original HeyGen file name, but written under OUT_DIR
            final_out = (OUT_DIR / f"{heygen_path.stem}{heygen_path.suffix}").resolve()

            # merge: captions + avatar remain exactly as HeyGen because we don't scale HeyGen layer

            merge_with_heygen(
                background=bg_video,
                heygen=heygen_path,
                out_path=final_out,
                chroma_key_hex=None,  # <-- let the script decide
                scaled_layout=(scale_bg.lower() != "no"),
                auto_detect_chroma=True,
                chroma_detect_hex="0x00FF00",
                chroma_ratio_threshold=0.12,
            )

            ws.cell(row=r, column=status_col).value = "success"
            wb.save(excel_path)   # ✅ save immediately (important)

            results.append({
                "row": r,
                "ok": True,
                "heygen": str(heygen_path),
                "bg": str(bg_asset),
                "output": str(final_out)
            })

        wb.close()
        # return jsonify({"ok": True, "count": len(results), "results": results})
        return jsonify({
        "ok": True,
        "count": len(results),
        "results": results,
        "output": f"Processed/checked {len(results)} rows. See results[] for details."
        })


    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/render")
def render():
    # timeline must exist
    tl_path = OUT_DIR / "timeline.json"
    if not tl_path.exists():
        return jsonify({"error": "Please Save Timeline first."}), 400

    heygen = request.files.get("heygen")
    if not heygen:
        return jsonify({"error": "Missing HeyGen file."}), 400

    out_res = request.form.get("outRes", "1920x1080")

    heygen_path = OUT_DIR / "heygen.mp4"
    meta = json.loads((OUT_DIR / "job_meta.json").read_text())
    orig_name = meta["orig_name"]
    orig_ext  = meta["orig_ext"]

    # heygen_path = OUT_DIR / f"{orig_name}{orig_ext}"
    heygen.save(heygen_path)

    try:
        output_path = render_background_and_merge(
            timeline_json_path=tl_path,
            base_dir=BASE_DIR,
            heygen_path=heygen_path,
            out_dir=OUT_DIR,
            out_res=out_res,
            out_filename=f"{orig_name}{orig_ext}",   # ✅ NEW
        )
        return jsonify({"output": str(output_path)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.post("/api/coloring_sketch")
def api_coloring_sketch():
    """
    Generate sketch SVG + steps for a coloring page.

    Accepts form-data:
      - file: uploaded image
      - mode: auto|cartoon|photo (optional, default: auto)
      - detail: 1..10 (optional, default: 5)
      - vector: outline|centerline (optional, default: outline)
    """
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "Missing file"}), 400

    mode = (request.args.get("mode") or request.form.get("mode") or "auto").strip()
    detail_str = (request.args.get("detail") or request.form.get("detail") or "5").strip()
    vector = (request.args.get("vector") or request.form.get("vector") or "outline").strip()

    try:
        detail = int(detail_str)
    except ValueError:
        detail = 5

    try:
        img = Image.open(file.stream).convert("RGB")
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to read image: {e}"}), 400

    try:
        svg, steps = build_sketch_from_pil(
            img,
            mode=mode,
            detail=detail,
            vector=vector,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Sketch failed: {e}"}), 500

    return jsonify({
        "ok": True,
        "svg": svg,
        "steps": steps,
    })

@app.post("/api/coloring_animation")
def api_coloring_animation():
    """
    Upload a colored coloring-page image and generate a 'before/after' animation:
      - First: clean line-art (desaturated page)
      - Then: sweeping color fill using original colors

    Expects multipart/form-data:
      - image: file (PNG/JPG/WEBP)
      - fps: optional, default 30
      - duration: optional, default 4.0 seconds
      - canvas_preset: "none" | "shorts" | "pinterest" | "custom"
      - canvas_width, canvas_height: used when canvas_preset == "custom"

    Returns JSON:
      {
        ok: true,
        url: "/downloads/coloring_animation/<file>",
        filename: "<file>"
      }
    """
    try:
        _ensure_ffmpeg()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    if "image" not in request.files:
        return jsonify({"ok": False, "error": "Missing 'image' file"}), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    # Basic extension check
    fname = file.filename.lower()
    if not any(fname.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
        return jsonify({"ok": False, "error": "Only PNG/JPG/WEBP are supported"}), 400

    # Parse params
    form = request.form
    try:
        fps = int(form.get("fps") or 30)
        duration = float(form.get("duration") or 4.0)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid fps/duration"}), 400

    canvas_preset = (form.get("canvas_preset") or "none").lower()
    canvas_width = None
    canvas_height = None

    if canvas_preset == "shorts":
        # Portrait Shorts canvas
        canvas_width, canvas_height = 1080, 1920
    elif canvas_preset == "pinterest":
        canvas_width, canvas_height = 1000, 1500
    elif canvas_preset == "custom":
        try:
            canvas_width = int(form.get("canvas_width") or 0)
            canvas_height = int(form.get("canvas_height") or 0)
        except ValueError:
            return jsonify({"ok": False, "error": "Invalid custom canvas width/height"}), 400

    target_size = None
    if canvas_width and canvas_height and canvas_width > 0 and canvas_height > 0:
        target_size = (canvas_width, canvas_height)

    # Save uploaded original to uploads/
    uploads_dir = BASE_DIR / "uploads" / "coloring_animation"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}_{os.path.basename(fname)}"
    input_path = uploads_dir / unique_name
    file.save(str(input_path))

    # Prepare output under downloads/coloring_animation so it's served via /downloads/...
    out_dir = COLORING_BASE / "coloring_animation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = unique_name.rsplit(".", 1)[0] + "_anim.mp4"
    output_path = out_dir / out_name
    mode = (form.get("mode") or "sweep").lower()


    try:
        if mode == "by_color":
            _create_coloring_animation_by_color(
                input_path=input_path,
                output_path=output_path,
                fps=fps,
                num_colors=5,
                brush_steps_per_color=40,
                hold_line_sec=1.2,
                hold_end_sec=1.2,
                target_size=target_size,
                bg_color=(255, 255, 255),
            )
        else:
            _create_coloring_animation(
                input_path=input_path,
                output_path=output_path,
                fps=fps,
                duration_sec=duration,
                target_size=target_size,
                bg_color=(255, 255, 255),
            )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Failed to create animation: {e}"}), 500



    # URL under /downloads
    rel = output_path.resolve().relative_to(COLORING_BASE).as_posix()
    url = f"/downloads/{rel}"

    return jsonify({
        # Old style
        "ok": True,
        "url": url,
        "filename": out_name,
        "fps": fps,
        "duration": duration,
        "canvas": {
            "preset": canvas_preset,
            "width": canvas_width,
            "height": canvas_height,
        },
        # New style (so either JS version works)
        "success": True,
        "video_url": url,
        "video_path": rel,
    })



@app.post("/merge_bg_music")
def merge_bg_music_route():
    """
    Batch mix background music (from edit_vid_audio/) into ALL videos in edit_vid_input/.

    Expects form fields:
      - bg_volume: float, 0.0–2.0 (default 0.3)
      - video_volume: float, 0.0–2.0 (default 1.0)

    Output is written to edit_vid_output/<same filename as input>.
    Returns JSON with list of outputs (web paths) for the UI.
    """
    try:
        bg_volume = float(request.form.get("bg_volume", "0.3") or "0.3")
    except ValueError:
        bg_volume = 0.3

    try:
        video_volume = float(request.form.get("video_volume", "1.0") or "1.0")
    except ValueError:
        video_volume = 1.0

    try:
        result = merge_all_videos_with_bg_music(
            base_dir=BASE_DIR,
            bg_volume=bg_volume,
            video_volume=video_volume,
        )
    except BgMusicError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

    # Build UI-friendly items
    items = []
    for out_path, in_path in result["pairs"]:
        items.append({
            "input_name": in_path.name,
            "output_name": out_path.name,
            "web_path": f"/video/edit_vid_output/{out_path.name}",
        })

    return jsonify({
        "ok": True,
        "total": result["total"],
        "music_file": result["music_file"],
        "bg_volume": bg_volume,
        "video_volume": video_volume,
        "items": items,
    })


@app.post("/api/generate_flipthrough")
def api_generate_flipthrough():
    """
    Generate a flip-through preview video for a given folder under /downloads.
    Expects:
      - folder: subfolder name (e.g. "farm_animals")
      - seconds_per_image (optional, default 0.5)
      - width, height (optional, default 1920x1080)

    Returns:
      { ok: true, url: "/downloads/<folder>/flip_preview.mp4" }
    """
    data = request.get_json(silent=True) or request.form
    folder = (data.get("folder") or "").strip()
    if not folder:
        return jsonify({"ok": False, "error": "Missing 'folder'"}), 400

    try:
        seconds = float(data.get("seconds_per_image") or 1.5)
        width = int(data.get("width") or 1920)
        height = int(data.get("height") or 1080)
        watermark_text = data.get("watermark_text") or "PREVIEW ONLY"
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid numeric parameter"}), 400

    try:
        out_path = generate_flipthrough_video(
            COLORING_BASE,
            folder,
            out_name="flip_preview.mp4",
            seconds_per_image=seconds,
            width=width,
            height=height,
            watermark_text=watermark_text,
        )
    except FlipThroughError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Internal error: {e}"}), 500

    # Build public URL
    rel = out_path.resolve().relative_to(COLORING_BASE).as_posix()
    url = f"/downloads/{rel}"

    return jsonify({
        "ok": True,
        "folder": folder,
        "url": url,
    })


@app.post("/api/upscale_coloring")
def api_upscale_coloring():
    """
    Trigger upscaling for a given folder under /coloring.

    Expects JSON or form-data:
      - folder: subfolder under /coloring (e.g., "farm_animals")
      - page_size: "LETTER" or "EIGHTX10" (optional, default LETTER)
      - threshold: 0-255 (optional, default 200)

    Response:
      {
        ok: true,
        folder: "farm_animals",
        count: 24,
        processed: [
          { file: "page1_upscaled.png", rel_path: "farm_animals/processed_images/page1_upscaled.png", url: "/downloads/farm_animals/processed_images/page1_upscaled.png" },
          ...
        ]
      }
    """
    data = request.get_json(silent=True) or request.form
    folder = (data.get("folder") or "").strip()
    page_size = (data.get("page_size") or "LETTER").strip()
    threshold = int(data.get("threshold") or 200)

    if not folder:
        return jsonify({"ok": False, "error": "Missing 'folder'"}), 400

    try:
        output_files = process_coloring_folder(COLORING_BASE, folder, page_size, threshold)
    except FileNotFoundError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Internal error: {e}"}), 500

    processed = []
    for out_path in output_files:
        # path relative to COLORING_BASE for URL mapping
        rel = out_path.relative_to(COLORING_BASE).as_posix()
        processed.append({
            "file": out_path.name,
            "rel_path": rel,
            "url": f"/downloads/{rel}",
        })

    return jsonify({
        "ok": True,
        "folder": folder,
        "count": len(processed),
        "processed": processed,
    })

@app.get("/downloads/<path:subpath>")
def coloring_files(subpath: str):
    """
    Serve files from COLORING_BASE safely.
    Used by the Coloring Book Builder to load processed_images.
    """
    full = (COLORING_BASE / subpath).resolve()
    base = COLORING_BASE.resolve()
    if not str(full).startswith(str(base)) or not full.is_file():
        abort(404)
    return send_from_directory(full.parent, full.name)

@app.post("/generate_meta")
def seo_generate_meta():
    """
    Run get_seo_meta_data.py to generate SEO metadata into pages_with_meta.xlsx.
    Uses pages_input.xlsx as input in the same folder as server.py.
    """
    try:
        base_dir = BASE_DIR  # already defined above
        script_path = base_dir / "get_seo_meta_data.py"

        if not script_path.exists():
            return jsonify({
                "ok": False,
                "error": f"Script not found: {script_path}"
            }), 500

        # Run using the same Python interpreter/venv as the server
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            timeout=60 * 60,   # up to 1 hour for 400+ pages
        )

        ok = (proc.returncode == 0)

        # Keep logs short-ish for UI
        stdout_tail = (proc.stdout or "")[-4000:]
        stderr_tail = (proc.stderr or "")[-4000:]

        return jsonify({
            "ok": ok,
            "returncode": proc.returncode,
            "stdout": stdout_tail,
            "stderr": stderr_tail,
        }), (200 if ok else 500)

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@app.post("/create_images")
def create_images():
    """Run only the image creation job."""
    try:
        from multi_profile_media_agent import createImages
        result = createImages()
        return jsonify({"ok": True, "message": "Images created successfully", "result": str(result)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/remove_borders")
def remove_borders():
    try:
        from remove_borders import main as remove_borders_main

        data = request.form
        source_folder = (data.get("source_folder") or "").strip()
        border_px_str = (data.get("border_px") or "10").strip()

        try:
            border_px = int(border_px_str)
        except:
            border_px = 10

        result = remove_borders_main(
            source_subfolder=source_folder or None,
            border_px=border_px,
            fill="white"   # or "rgba(255,255,255,0)" for transparent
        )

        status = 200 if result.get("ok") else 500
        return jsonify(result), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/create_vector_images")
def create_vector_images():
    """
    Run the vector image creation job.

    Expects (optional) form field:
      - source_folder: relative folder under downloads/
        e.g. "1.Cute Farm Animals/pages"

    The vectorize_images.main() function should then create output under
    vector_images/<source_folder>/...
    """
    try:
        from vectorize_images import main
        data = request.get_json(silent=True) or request.form
        source_folder = (data.get("source_folder") or "").strip()

        # Call your script. Adjust if main() has a different signature.
        if source_folder:
            result = main(source_folder)
            msg = f"Vector images created successfully for '{source_folder}'"
        else:
            result = main()
            msg = "Vector images created successfully (default folder)"

        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

    
@app.post("/create_videos")
def create_videos():
    """Run only the video creation job."""
    try:
        from multi_profile_media_agent import createVideos
        result = createVideos()
        return jsonify({"ok": True, "message": "Videos created successfully", "result": str(result)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

# ---- ADD this route (server.py) ----
@app.post("/upscale")
def upscale_all_videos():
    """
    Batch-only: loop over all videos in 'edit_vid_input/' and upscale each one.

    Optional form fields:
      - width (default 1920)
      - deinterlace ('true'/'false', default 'true')
      - denoise   ('true'/'false', default 'true')
      - crf       (default 18)
      - preset    (default 'slow')
      - keep_audio ('yes'/'no', default 'yes')
    """
    try:
        _ensure_ffmpeg()

        base_dir = BASE_DIR
        in_dir = base_dir / "edit_vid_input"
        out_dir = base_dir / "edit_vid_output"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Options
        width = int(request.form.get("width", "1920") or 1920)
        deinterlace_val = (request.form.get("deinterlace", "true") or "true").lower() in ("1","true","yes","on")
        denoise_val    = (request.form.get("denoise", "true") or "true").lower() in ("1","true","yes","on")
        crf            = int(request.form.get("crf", "18") or 18)
        preset         = (request.form.get("preset", "slow") or "slow").strip()
        keep_audio_req = (request.form.get("keep_audio", "yes") or "yes").lower() in ("1","true","yes","on","y","yes")

        if not in_dir.exists():
            return jsonify({"ok": False, "error": f"Input folder not found: {in_dir}"}), 400

        exts = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
        inputs = [p for p in sorted(in_dir.iterdir()) if p.is_file() and p.suffix.lower() in exts]
        if not inputs:
            return jsonify({"ok": False, "error": "No videos found in edit_vid_input/"}), 400

        # Build filter chain
        vf = []
        if deinterlace_val:
            vf.append("bwdif=mode=1")
        if denoise_val:
            vf.append("atadenoise")
        vf.append(f"scale={width}:-2:flags=lanczos")
        vf.append("unsharp=lx=3:ly=3:la=0.4")
        vf.append("format=yuv420p")
        filter_str = ",".join(vf)

        def has_audio_stream(path: Path) -> bool:
            try:
                # returns 0 if at least one audio stream is present
                subprocess.check_call(
                    ["ffprobe", "-v", "error", "-select_streams", "a",
                     "-show_entries", "stream=index",
                     "-of", "csv=p=0", str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True
            except subprocess.CalledProcessError:
                return False

        results, errors = [], []

        for src in inputs:
            try:
                dst_name = f"{src.stem}_upscaled_{width}w.mp4"
                dst_path = out_dir / dst_name

                include_audio = keep_audio_req and has_audio_stream(src)

                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(src),
                    "-vf", filter_str,
                    "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                ]
                if include_audio:
                    cmd += ["-c:a", "aac", "-b:a", "192k"]
                else:
                    cmd += ["-an"]
                cmd += ["-movflags", "+faststart", str(dst_path)]

                print("Upscale cmd:", " ".join(cmd))
                subprocess.check_call(cmd)

                results.append({
                    "input":  str(src.relative_to(base_dir)),
                    "output": f"/video/edit_vid_output/{dst_name}",
                    "kept_audio": include_audio
                })
            except subprocess.CalledProcessError as e:
                errors.append({
                    "input": str(src.relative_to(base_dir)),
                    "error": "FFmpeg failed",
                    "detail": getattr(e, "output", None)
                })
            except Exception as e:
                errors.append({
                    "input": str(src.relative_to(base_dir)),
                    "error": str(e)
                })

        return jsonify({
            "ok": bool(results),
            "mode": "batch",
            "count_processed": len(results),
            "count_errors": len(errors),
            "settings": {
                "width": width,
                "deinterlace": deinterlace_val,
                "denoise": denoise_val,
                "crf": crf,
                "preset": preset,
                "keep_audio_requested": keep_audio_req
            },
            "outputs": results,
            "errors": errors
        }), (200 if results else 500)

    except subprocess.CalledProcessError as e:
        return jsonify({"ok": False, "error": "FFmpeg failed", "detail": getattr(e, "output", None)}), 500
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500



@app.post("/extract_audio")
def extract_audio_route():
    """
    Batch-extract audio for all videos in edit_vid_input/ when no file/path is provided.
    Otherwise (if you ever send "file" or "video"), it behaves like single-file mode.
    Form-data:
      - format: wav|mp3|m4a (default wav)
      - track: audio stream index, default 0
    """
    try:
        base_dir = Path(__file__).resolve().parent
        fmt = (request.form.get("format") or "wav").lower()
        track_raw = request.form.get("track", "0")
        try:
            track = int(track_raw)
        except Exception:
            track = 0

        uploaded = request.files.get("file")
        video_url = (request.form.get("video") or "").strip()

        # If either upload or explicit path is provided, fall back to single-file behavior
        if uploaded or video_url:
            try:
                in_path = resolve_input_video(
                    base_dir=base_dir,
                    uploaded_temp_dir=base_dir / "tmp_upload_video",
                    uploaded_file=uploaded,
                    urlish_path=video_url if video_url else None,
                    fallback_rel="edit_vid_input/bg_video.mp4",
                )
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 400

            result = extract_audio_from_video(
                base_dir=base_dir,
                input_path=in_path,
                fmt=fmt,
                track=track,
                root_output_name="edit_vid_output"
            )

            if not getattr(result, "ok", False):
                return jsonify({
                    "ok": False,
                    "error": result.error or "Failed",
                    "detail": result.detail,
                }), 500

            download_rel = f"/video/{result.output_path.name}" if result.output_path else None
            also_rel = f"/video/edit_vid_audio/{result.output_path.name}" if getattr(result, "copy_path", None) else None

            return jsonify({
                "ok": True,
                "mode": "single",
                "input": result.input_name,
                "format": result.fmt,
                "track": result.track,
                "duration_sec": result.duration_sec,
                "download": download_rel,
                "also_saved_in_edit_vid_audio": also_rel,
            })

        # === Batch mode: scan edit_vid_input/ ===
        in_dir = base_dir / "edit_vid_input"
        out_dir = base_dir / "edit_vid_output"
        out_dir.mkdir(parents=True, exist_ok=True)

        if not in_dir.exists():
            return jsonify({"ok": False, "error": f"Input folder not found: {in_dir}"}), 400

        candidates = sorted([p for p in in_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS])

        if not candidates:
            return jsonify({"ok": True, "mode": "batch", "items": []})

        items = []
        for vid in candidates:
            try:
                res = extract_audio_from_video(
                    base_dir=base_dir,
                    input_path=vid,
                    fmt=fmt,
                    track=track,
                    root_output_name="edit_vid_output"
                )
                if getattr(res, "ok", False) and getattr(res, "output_path", None):
                    items.append({
                        "ok": True,
                        "input": vid.name,
                        "fmt": res.fmt,
                        "track": res.track,
                        "duration_sec": res.duration_sec,
                        "output_name": res.output_path.name,
                        "download": f"/video/{res.output_path.name}"
                    })
                else:
                    items.append({
                        "ok": False,
                        "input": vid.name,
                        "error": getattr(res, "error", "Failed"),
                        "detail": getattr(res, "detail", None)
                    })
            except Exception as e:
                import traceback
                traceback.print_exc()
                items.append({
                    "ok": False,
                    "input": vid.name,
                    "error": str(e)
                })

        # Always return a compact summary for the UI to render
        return jsonify({
            "ok": True,
            "mode": "batch",
            "format": fmt,
            "track": track,
            "count": len(items),
            "items": items
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
    


# gemini_pool = GeminiPool(
#     api_keys=None,          # reads GEMINI_API_KEYS from env
#     per_key_rpm=25,         # tune to your safe RPM per key
#     state_path=GEM_STATE,   # persist key usage across restarts
#     autosave_every=3
# )

# =========================
# Minimal, defaulted routes
# =========================

@app.post("/ai/text")
def ai_text():
    """
    UI only needs: {"prompt": "..."}.
    Optional overrides: {"model": "...", "temperature": 0.7, "max_output_tokens": 512}
    """
    data = request.get_json(force=True) if request.is_json else {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "Missing 'prompt'"}), 400

    # Use server defaults unless client overrides
    model = data.get("model") or DEFAULT_TEXT_MODEL
    temperature = data.get("temperature")
    max_tokens  = data.get("max_output_tokens")

    try:
        text = gemini_pool.generate_text(
            prompt,
            model=model,
            temperature=temperature,
            max_output_tokens=max_tokens
        )
        return jsonify({"ok": True, "model": model, "text": text})
    except Exception as e:
        return jsonify({"ok": False, "model": model, "error": str(e)}), 500


@app.post("/ai/image")
def ai_image():
    """
    UI only needs: {"prompt": "..."}.
    Optional overrides: {"model": "..."} and any extras you pass through later.
    Saves the first image to /edit_vid_input/ and returns a web path for your pipeline.
    """
    data = request.get_json(force=True) if request.is_json else {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "Missing 'prompt'"}), 400

    model = data.get("model") or DEFAULT_IMAGE_MODEL

    try:
        out_dir = BASE_DIR / "edit_vid_input"
        out_dir.mkdir(exist_ok=True)
        out_name = f"gen_{int(__import__('time').time())}.png"
        out_path = out_dir / out_name

        gemini_pool.generate_image(
            prompt,
            model=model,
            out_path=str(out_path),
            # extra=data.get("extra")  # keep for future size/quality params
        )

        return jsonify({
            "ok": True,
            "model": model,
            "image_path": f"/edit_vid_input/{out_name}"  # relative path for your pipeline
        })
    except Exception as e:
        return jsonify({"ok": False, "model": model, "error": str(e)}), 500


@app.get("/ai/keys")
def ai_keys():
    """Quick peek at rotation state (helpful in logs/dashboards)."""
    return jsonify({"ok": True, "stats": gemini_pool.stats()})

@app.get("/ai/models")
def ai_models():
    try:
        models = gemini_pool.list_models(api_version="v1beta")
        return jsonify({"ok": True, "models": models})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500




@app.post("/mix_vocal_music")
def mix_vocal_music_endpoint():
    """
    Merge vocal + background music into a polished song.
    Accepts optional file uploads (vocal_file, music_file); otherwise
    tries to auto-pick from edit_vid_audio/ (vocal*, music*, etc.) or first two audio files.
    Returns JSON with download link and metadata.
    """
    try:
        base = BASE_DIR
        eva = base / "edit_vid_audio"
        eva.mkdir(exist_ok=True)

        uploaded_v = request.files.get("vocal_file")
        uploaded_m = request.files.get("music_file")

        def _save_upload(upfile, fallback_stem):
            if not upfile or not upfile.filename:
                return None
            ext = os.path.splitext(upfile.filename)[1]
            p = eva / f"{fallback_stem}{ext}"
            upfile.save(str(p))
            return p

        vocal_path = _save_upload(uploaded_v, "vocal_uploaded") if uploaded_v else None
        music_path = _save_upload(uploaded_m, "music_uploaded") if uploaded_m else None

        # Auto-pick from folder if any missing
        def _pick_candidates():
            if not eva.exists():
                return []
            return [
                p for p in sorted(eva.iterdir())
                if p.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
            ]

        files = _pick_candidates()
        if not vocal_path:
            # Prefer names
            for p in files:
                if "vocal" in p.name.lower() or "vox" in p.name.lower():
                    vocal_path = p; break
        if not music_path:
            for p in files:
                if p != vocal_path and any(tag in p.name.lower() for tag in ["music", "bg", "instrumental"]):
                    music_path = p; break
        # Fallback to first two
        if not (vocal_path and music_path) and len(files) >= 2:
            vocal_path = vocal_path or files[0]
            music_path = music_path or next(p for p in files if p != vocal_path)

        if not (vocal_path and music_path):
            return jsonify({"ok": False, "error": "Could not find both vocal and music. Upload them or place in edit_vid_audio/."}), 400

        # Read options
        sr = int(request.form.get("sr", 44100))
        music_gain_db = float(request.form.get("music_gain_db", -10.0))
        duck_db = float(request.form.get("duck_db", 10.0))
        duck_floor_db = float(request.form.get("duck_floor_db", -1.0))
        target_lufs = float(request.form.get("target_lufs", -14.0))
        out_fmt = (request.form.get("format", "wav") or "wav").lower()
        out_name = f"final_mix.{ 'mp3' if out_fmt=='mp3' else 'wav'}"
        out_path = base / out_name

        # Run mix
        final_path, meta = mix_files(
            str(vocal_path), str(music_path), str(out_path),
            sr=sr, music_gain_db=music_gain_db, duck_db=duck_db,
            duck_floor_db=duck_floor_db, target_lufs=target_lufs
        )

        # Optional: also copy to edit_vid_audio for downstream steps
        try:
            import shutil
            shutil.copy(str(final_path), str(eva / out_name))
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "download": f"/video/{out_name}",
            "saved_in_edit_vid_audio": f"/video/edit_vid_audio/{out_name}" if (eva / out_name).exists() else None,
            "inputs": {
                "vocal": str(vocal_path.relative_to(base)),
                "music": str(music_path.relative_to(base)),
            },
            "meta": meta
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/polish_audio")
def polish_audio_endpoint():
    """
    Polishes an audio file and writes result to root as 'audio_clean.m4a'.
    Source priority:
      1) uploaded file 'audio_file' (optional)
      2) first file under edit_vid_audio/
      3) ./audio.wav (root)
    Returns JSON with settings + downloadable link: /video/audio_clean.m4a
    """
    try:
        base_dir = Path(__file__).resolve().parent

        # 1) Decide input
        uploaded = request.files.get("audio_file")
        tmp_in = None
        if uploaded and uploaded.filename:
            tmp_in = base_dir / "tmp_upload_in"
            tmp_in.mkdir(exist_ok=True)
            in_path = tmp_in / uploaded.filename
            uploaded.save(str(in_path))
        else:
            # fallbacks: first file in edit_vid_audio, else root audio.wav
            eva = base_dir / "edit_vid_audio"
            candidates = []
            if eva.exists():
                for f in sorted(eva.iterdir()):
                    if f.suffix.lower() in {".wav",".m4a",".mp3",".aac",".flac",".ogg"}:
                        candidates.append(f)
            if not candidates and (base_dir / "audio.wav").exists():
                candidates.append(base_dir / "audio.wav")
            if not candidates:
                return jsonify({"error": "No input audio found. Upload a file or place one in edit_vid_audio/ or audio.wav."}), 400
            in_path = candidates[0]

        # 2) Read options from form (with safe defaults)
        mode = request.form.get("denoise", "auto")
        target = float(request.form.get("target_lufs", -16.0))
        tp = float(request.form.get("tp", -1.5))
        lra = float(request.form.get("lra", 11.0))
        hp = int(request.form.get("hp", 80))
        lp_raw = request.form.get("lp", "12000")
        lp = int(lp_raw) if lp_raw and lp_raw != "0" else None
        deess = int(request.form.get("deess", 5))
        if deess < 0: deess = 0
        if deess > 10: deess = 10
        mono = request.form.get("mono", "false").lower() == "true"
        ar_raw = request.form.get("ar", "").strip()
        ar = int(ar_raw) if ar_raw else None
        speechnorm = request.form.get("speechnorm", "false").lower() == "true"

        out_path = base_dir / "audio_clean.m4a"  # served by /video/<filename>
        meta = polish_audio(
            input_path=str(in_path),
            output_path=str(out_path),
            denoise_mode=mode,
            target_lufs=target,
            tp_limit=tp,
            lra_target=lra,
            highpass_hz=hp,
            lowpass_hz=lp,
            deess_intensity=deess,
            force_mono=mono,
            samplerate=ar,
            use_speechnorm=speechnorm,
        )

        # optional: also copy to edit_vid_audio for downstream steps
        try:
            (base_dir / "edit_vid_audio").mkdir(exist_ok=True)
            shutil.copy(str(out_path), str(base_dir / "edit_vid_audio" / "audio_clean.m4a"))
        except Exception:
            pass

        # Download via existing route /video/<filename> that serves from project root
        # (you already have: send_from_directory(directory='.', path=filename))
        return jsonify({
            "ok": True,
            "download": "/video/audio_clean.m4a",
            "meta": meta
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

def url_to_fs(url_path: str, base_subdir: str) -> Path:
    """
    Map a URL like '/thumbnail_images/a/b.png' to a safe filesystem path
    under BASE_DIR/base_subdir/a/b.png
    """
    if not url_path:
        abort(400, "Missing image path")
    url_path = unquote(url_path).lstrip("/")              # remove leading '/'
    # strip the first segment (should match base_subdir)
    first, _, tail = url_path.partition("/")
    if first != base_subdir:
        abort(400, f"Unexpected base folder: {first}")
    fs_path = (BASE_DIR / base_subdir / tail).resolve()
    allowed_base = (BASE_DIR / base_subdir).resolve()
    if not str(fs_path).startswith(str(allowed_base)):
        abort(400, "Invalid image path")
    return fs_path

def _duration_via_wave(p: Path):
    """Try Python wave for PCM WAV."""
    import wave
    with wave.open(str(p), 'rb') as w:
        frames = w.getnframes()
        rate = w.getframerate()
        if rate == 0:
            raise ValueError("Invalid WAV: sample rate is 0")
        return frames / float(rate)

def _duration_via_ffprobe(p: Path):
    """Fallback: use ffprobe for any codec/container."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(p)
    ]
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    # ffprobe prints a float in seconds (can be "N/A")
    if not out or out.upper() == "N/A":
        raise ValueError("ffprobe returned no duration")
    dur = float(out)
    if not math.isfinite(dur):
        raise ValueError("Non-finite duration from ffprobe")
    return dur

@app.route("/api/audio-duration")
def audio_duration():
    p = AUDIO_PATH
    if not p.exists():
        return jsonify({"error": f"File not found: {str(p)}", "cwd": str(BASE_DIR)}), 404
    try:
        # 1) Try wave first (fast, if PCM)
        try:
            seconds = _duration_via_wave(p)
        except Exception as e_wave:
            # 2) Fallback to ffprobe
            seconds = _duration_via_ffprobe(p)

        return jsonify({"seconds": round(seconds, 2), "path": str(p)})
    except subprocess.CalledProcessError as e:
        return jsonify({
            "error": "ffprobe failed",
            "detail": e.output
        }), 500
    except Exception as e:
        return jsonify({
            "error": type(e).__name__,
            "detail": str(e),
            "path": str(p)
        }), 500

@app.route('/edit_vid_thumbnail/<path:filename>')
def serve_generated_thumb(filename):
    return send_from_directory(BASE_DIR / 'edit_vid_thumbnail', filename)


@app.route('/generate_thumbnail', methods=['POST'])
def generate_thumbnail():
    try:
        from thumbnail_gen import create_thumbnail

        image_url = request.form.get('image')  # e.g. "/thumbnail_images/foo/bar.png"
        bg_color = request.form.get('bg_color', '#000000')
        text = request.form.get('text', '')
        colors = request.form.get('colors', 'auto')
        print("Generating thumbnail for image:", image_url)
        # Map the URL to a filesystem path safely
        fs_image_path = url_to_fs(image_url, base_subdir='thumbnail_images')
        print("Filesystem image path:", fs_image_path)

        # Ensure output folder exists; return a served URL
        out_dir = BASE_DIR / 'edit_vid_thumbnail'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / 'thumbnail.png'
        out_url = f"/edit_vid_thumbnail/{out_file.name}"

        create_thumbnail(
            image_path=str(fs_image_path),
            bg_color=bg_color,
            text=text,
            colors=colors,
            output_path=str(out_file)
        )

        return jsonify({"message": "✅ Thumbnail created successfully!", "thumbnail": out_url})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _safe_join(base: Path, sub: str) -> Path:
    """Prevent path traversal; always return a child of base."""
    p = (base / (sub or "")).resolve()
    base = base.resolve()
    if not str(p).startswith(str(base)):
        abort(400, "Invalid folder")
    return p

def _list_current(base_url: str, base_dir: Path, rel_folder: str, exts: set[str]):
    """
    Return files in the current folder and immediate subfolders.
    - base_url: '/thumbnail_images' or '/background_videos'
    - base_dir: BASE_DIR/'thumbnail_images' or 'background_videos'
    - rel_folder: '' or 'krishna/diwali'
    """
    cur = _safe_join(base_dir, rel_folder)
    if not cur.exists():
        return {"cwd": rel_folder, "folders": [], "files": []}

    # immediate subfolders
    folders = []
    for d in sorted([p for p in cur.iterdir() if p.is_dir()]):
        rel = (Path(rel_folder) / d.name).as_posix()
        folders.append(rel)

    # files in current folder only
    files = []
    for f in sorted([p for p in cur.iterdir() if p.is_file()]):
        if f.suffix.lower() in exts:
            rel_file = (Path(rel_folder) / f.name).as_posix()
            files.append(f"{base_url}/{rel_file}")

    # build breadcrumb segments for UI
    crumbs = []
    accum = []
    for part in Path(rel_folder).parts:
        accum.append(part)
        crumbs.append({"name": part, "path": "/".join(accum)})
    return {"cwd": rel_folder, "folders": folders, "files": files, "breadcrumbs": crumbs}

def _list_all_folders(base_dir: Path):
    """Return ALL subfolders (including root '') for the folder dropdown."""
    out = [""]
    for d, subdirs, _ in os.walk(base_dir):
        rel = os.path.relpath(d, base_dir)
        if rel == ".":
            continue
        out.append(rel.replace("\\", "/"))
    return sorted(out)

# --- STATIC file serving (so subpaths are accessible from <img>/<video> tags) ---
@app.route('/thumbnail_images/<path:filename>')
def serve_thumb_image(filename):
    return send_from_directory(BASE_DIR / 'thumbnail_images', filename)

@app.route('/images/<path:filename>')
def serve_reg_image(filename):
    return send_from_directory(BASE_DIR / 'images', filename)

@app.route('/background_videos/<path:filename>')
def serve_bg_video(filename):
    return send_from_directory(BASE_DIR / 'background_videos', filename)

@app.route('/quiz/downloads/<path:filename>')
def serve_quiz_downloads(filename):
    return send_from_directory(BASE_DIR / 'downloads', filename)

@app.get('/trigger_heygen_bulk_shorts')
def trigger_heygen_bulk_shorts():
    """Trigger background creation of HeyGen shorts."""
    from heygen_submit_videos import main as trigger_shorts
    try:
        count = trigger_shorts()
        return jsonify({"ok": True, "message": f"Triggered creation for {count} HeyGen shorts."})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post('/add_heygen_backgrounds')
def add_heygen_backgrounds():
    """Add HeyGen backgrounds to the system."""
    try:
        orientation = request.form.get('orientation', 'landscape')
        scaleBG = request.form.get('scale_bg', 'yes')
        copy_as_is = request.form.get('copy_asis', 'yes') == 'yes'
        render_bulk_bg(orientation, scaleBG, copy_as_is)
        return jsonify({"ok": True, "message": "HeyGen backgrounds added successfully."})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get('/trigger_heygen_downloads')
def trigger_heygen_downloads():
    """Trigger background download of HeyGen videos."""
    from heygen_download_and_trash import main as trigger_downloads
    try:
        count = trigger_downloads()
        return jsonify({"ok": True, "message": f"Triggered downloads for {count} HeyGen videos."})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

# --- BROWSING APIs ---
@app.get('/list_thumbnail_images')
def list_thumbnail_images():
    folder = request.args.get('folder', '').strip('/')
    base = BASE_DIR / 'thumbnail_images'
    data = _list_current('/thumbnail_images', base, folder, {'.png', '.jpg', '.jpeg', '.webp'})
    data["all_folders"] = _list_all_folders(base)
    return jsonify(data)

@app.get('/list_background_videos')
def list_background_videos():
    folder = request.args.get('folder', '').strip('/')
    base = BASE_DIR / 'background_videos'
    data = _list_current('/background_videos', base, folder, {'.mp4', '.mov', '.mkv', '.webm'})
    data["all_folders"] = _list_all_folders(base)
    return jsonify(data)

@app.post("/populate_media_jobs")
def populate_media_jobs():
    """
    Reads images from a source folder (server path or uploaded 'temp-del'),
    clears 'media_jobs.xlsx' (keeping headers), and populates:
      - prompt: filename
      - image_path: absolute file path
    """
    try:
        data = request.form
        source_type = data.get("source_type") # 'server' or 'upload'
        server_path_input = (data.get("server_path") or "").strip()
        uploaded_files = request.files.getlist("image_files")
        
        base_dir = BASE_DIR
        excel_path = base_dir / "media_jobs.xlsx"
        
        # 1. Determine Target Folder
        target_folder = None
        
        if source_type == "upload":
            # Use 'temp-del' for uploads to generate local paths
            target_folder = base_dir / "temp-del"
            target_folder.mkdir(exist_ok=True)
            
            # Clear existing files in temp-del to avoid mixing batches
            for f in target_folder.iterdir():
                if f.is_file():
                    f.unlink()
            
            # Save uploaded files
            if not uploaded_files or uploaded_files[0].filename == '':
                return jsonify({"ok": False, "error": "No files uploaded."}), 400
                
            for file in uploaded_files:
                # webkitdirectory sends relative paths (folder/file.jpg), we need just filename usually
                # or we keep structure. For this specific job, flat lists are usually better.
                fname = Path(file.filename).name 
                file.save(target_folder / fname)
                
        else:
            # Server path
            if not server_path_input:
                return jsonify({"ok": False, "error": "Server path is empty."}), 400
            
            # Handle absolute vs relative paths
            if os.path.isabs(server_path_input):
                target_folder = Path(server_path_input)
            else:
                target_folder = (base_dir / server_path_input).resolve()
                
            if not target_folder.exists():
                return jsonify({"ok": False, "error": f"Folder not found: {target_folder}"}), 404

        # 2. Get Image Files
        valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        images = [
            f for f in target_folder.iterdir() 
            if f.is_file() and f.suffix.lower() in valid_exts
        ]
        
        if not images:
            return jsonify({"ok": False, "error": "No images found in target folder."}), 400

        # 3. Update Excel
        if not excel_path.exists():
            return jsonify({"ok": False, "error": "media_jobs.xlsx not found."}), 404

        wb = openpyxl.load_workbook(excel_path)
        ws = wb.active
        
        # Clear old data (keep header at row 1)
        # delete_rows is efficient; delete from row 2 to end
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)
            
        # 4. Populate Data
        # Header assumed: prompt, account_id, image_path, video_cmd, video_path, status, ...
        # We map: prompt -> Col A (1), image_path -> Col C (3)
        
        count = 0
        for img in sorted(images, key=lambda x: x.name):
            ws.append([
                img.name,       # A: prompt
                "",             # B: account_id
                str(img.resolve()), # C: image_path (Absolute path)
                "",             # D: video_cmd
                "",             # E: video_path
                "pending"       # F: status (optional, setting default)
            ])
            count += 1
            
        wb.save(excel_path)
        wb.close()
        
        return jsonify({
            "ok": True, 
            "message": f"Updated media_jobs.xlsx with {count} images.",
            "folder": str(target_folder)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/render_pinterest_pins_from_pin_data")
def render_pinterest_pins_from_pin_data():
    """
    Reads PIN_DATA.xlsx from a folder, renders image/video pins using project_json overlays,
    writes outputs to pinterest_uploads/pinterest_pins, and appends records to master_shorts_uploader_data.xlsx
    """
    try:
        from pathlib import Path
        from time import time

        from pin_overlay_batch import batch_render_from_folder

        base_dir = BASE_DIR

        data = request.form
        uploaded_files = request.files.getlist("source_dir")  # directory upload (optional)
        source_folder = (data.get("source_folder") or "").strip()
        # print("Source folder:", source_folder)
        pin_type = (data.get("pin_type") or "image").strip().lower()  # image|video
        max_pins = int((data.get("max_pins") or "0").strip() or 0)
        skip_overlays = (data.get("skip_overlays") or "no").strip().lower() == "yes"

        if pin_type not in ("image", "video"):
            pin_type = "image"

        print(f"uploaded_files: {uploaded_files}, source_folder: {source_folder}, pin_type: {pin_type}, max_pins: {max_pins}")
        # Where the folder is
        if source_folder == "" and uploaded_files and len(uploaded_files) > 0:
            upload_root = base_dir / "pinterest_uploads" / "uploads"
            upload_root.mkdir(parents=True, exist_ok=True)

            # Clear previous contents
            for child in upload_root.iterdir():
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    import shutil
                    shutil.rmtree(child)

            for fs in uploaded_files:
                filename = Path(fs.filename).name
                dest_path = upload_root / filename
                fs.save(dest_path)

            folder = upload_root
        else:
            # Use server-side folder relative to BASE_DIR or downloads
            # If you prefer downloads/ only, swap BASE_DIR for COLORING_BASE
            folder = (base_dir / source_folder) if source_folder else None
            if not folder or not folder.exists():
                return jsonify({"ok": False, "error": f"Folder not found: {folder}"}), 400

        out_dir = base_dir / "pinterest_uploads" / "pinterest_pins"
        out_dir.mkdir(parents=True, exist_ok=True)

        master_excel = base_dir / "master_shorts_uploader_data.xlsx"

        result = batch_render_from_folder(
            folder=folder,
            pin_type=pin_type,
            max_pins=max_pins,
            out_dir=out_dir,
            master_excel=master_excel,
            skip_overlays=skip_overlays
        )
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/generate_pinterest_excel_for_coloring_pins")
def generate_pinterest_excel_route():
    """
    Run generate_excel.py to create a Pinterest Pin Excel file
    and Pinterest-ready images from either:
      - an uploaded folder (directory upload from browser), or
      - an existing folder under COLORING_BASE (downloads).
    """
    try:
        base_dir = BASE_DIR
        script_path = base_dir / "for_coloring_pin_load_pinterest_excel.py"

        if not script_path.exists():
            return jsonify({
                "ok": False,
                "error": f"Script not found: {script_path}"
            }), 500

        # --- Read form fields ---
        data = request.form
        uploaded_files = request.files.getlist("source_dir")  # directory upload

        # Optional: existing folder on server (relative to COLORING_BASE)
        source_folder = (data.get("source_folder") or "").strip()

        media_type = (data.get("media_type") or "image").strip()
        # pin_url = (data.get("pin_url") or "").strip()
        # pin_url = ""
        max_pins_str = (data.get("max_pins") or "0").strip()
        output_excel_name = (data.get("output_excel") or "master_shorts_uploader_data.xlsx").strip()

        # These can be blank – generate_excel.py will fall back to pinterest_config.json
        book_title = (data.get("book_title") or "").strip()
        book_url = (data.get("book_url") or "").strip()
        board_name = (data.get("board_name") or "").strip()
        banner_text = (data.get("banner_text") or "").strip()
        watermark_text = (data.get("watermark_text") or "").strip()

        fit_mode = (data.get("fit_mode") or "contain").strip()
        bg_style = (data.get("bg_style") or "white").strip()
        text_shadow = (data.get("text_shadow") or "yes").strip().lower()  # "yes"/"no"

        use_gemini_flag = (data.get("use_gemini") or "no").strip().lower()

        add_bg_music_flag = (data.get("add_bg_music") or "no").strip().lower()

        upload_pinterest_flg = (data.get("upload_pinterest") or "no").strip().lower()

        auto_crop_subject_flag = (data.get("auto_crop_subject") or "yes").strip().lower()
        if auto_crop_subject_flag not in ("yes", "no"):
            auto_crop_subject_flag = "yes"

        try:
            max_pins = int(max_pins_str)
        except ValueError:
            max_pins = 0

        video_duration_str = (data.get("video_duration") or "8").strip()
        video_fps_str = (data.get("video_fps") or "30").strip()

        try:
            video_duration = float(video_duration_str)
        except ValueError:
            video_duration = 8.0

        try:
            video_fps = int(video_fps_str)
        except ValueError:
            video_fps = 30

        video_style = (data.get("video_style") or "single").strip()
        if video_style not in ("single", "flipbook", "slideshow"):
            video_style = "single"

        pages_per_video_str = (data.get("pages_per_video") or "10").strip()
        try:
            pages_per_video = int(pages_per_video_str)
        except ValueError:
            pages_per_video = 10


        # Decide where images_root & source_subfolder will be
        images_root = None
        source_subfolder = None

        # --- CASE 1: user uploaded a directory from their computer ---
        if uploaded_files:
            # Store folder under pinterest_uploads/upload_<timestamp>/
            #upload_root = BASE_DIR / "pinterest_uploads" / f"upload_{int(time())}"

            upload_root = BASE_DIR / "pinterest_uploads/uploads" 
            upload_root.mkdir(parents=True, exist_ok=True)

            # Clear previous contents
            for child in upload_root.iterdir():
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    import shutil
                    shutil.rmtree(child)
            
            # With webkitdirectory, file.filename usually contains a relative path like "MyBook/page_01.png"
            for fs in uploaded_files:
                filename = Path(fs.filename).name  # ⬅ strip subfolders
                dest_path = upload_root / filename
                fs.save(dest_path)


            images_root = upload_root
            source_subfolder = None  # we already uploaded the exact folder tree
            print(f"[INFO] Using uploaded folder as images_root: {images_root}")

        # --- CASE 2: existing folder on server under COLORING_BASE (/downloads) ---
        else:
            # base images_root is COLORING_BASE, e.g. BASE_DIR/downloads
            images_root = COLORING_BASE
            source_subfolder = source_folder or None
            print(f"[INFO] Using server folder. images_root={images_root}, source_subfolder={source_subfolder}")

        output_excel = base_dir / output_excel_name

        # Build command for generate_excel.py
        cmd = [
            sys.executable,
            str(script_path),
            "--images-root", str(images_root),
            "--output-excel", str(output_excel),
            "--media-type", media_type,
            # "--pin-url", pin_url,
        ]

        if source_subfolder:
            cmd += ["--source-subfolder", source_subfolder]
        if max_pins > 0:
            cmd += ["--max-pins", str(max_pins)]

        # NEW: video parameters (safe to pass for both image & video)
        cmd += [
            "--video-style", video_style,
            "--pages-per-video", str(pages_per_video),
            "--video-duration", str(video_duration),
            "--video-fps", str(video_fps),
        ]


        # Optional overrides – safe to pass even if empty
        if book_title:
            cmd += ["--book-title", book_title]
        if book_url:
            cmd += ["--book-url", book_url]
        if board_name:
            cmd += ["--board-name", board_name]
        if banner_text:
            cmd += ["--banner-text", banner_text]
        if watermark_text:
            cmd += ["--watermark-text", watermark_text]

        # New options
        cmd += ["--fit-mode", fit_mode]
        cmd += ["--bg-style", bg_style]
        cmd += ["--text-shadow", text_shadow]
        cmd += ["--auto-crop-subject", auto_crop_subject_flag]  # <--- NEW

        cmd += ["--use-gemini", use_gemini_flag]

        cmd += ["--add-bg-music", add_bg_music_flag]

        proc = subprocess.run(
            cmd,
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            # timeout=60 * 60,
        )

        ok = (proc.returncode == 0)
        stdout_tail = (proc.stdout or "")[-4000:]
        stderr_tail = (proc.stderr or "")[-4000:]

        # if media_type == "video":


        if upload_pinterest_flg == "yes" and ok:
            upload_pins() #Pinterest upload
            # if media_type == "video" or media_type == "coloring":
            upload_shorts_from_master_file() #YouTube shorts upload
            upload_facebook_videos() #Facebook videos upload
            upload_tiktok_videos() #TikTok videos upload
            upload_instagram_posts() #Instagram posts upload
        
        return jsonify({
            "ok": ok,
            "returncode": proc.returncode,
            "stdout": stdout_tail,
            "stderr": stderr_tail,
        }), (200 if ok else 500)

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


@app.route('/convert_landscape_images', methods=['POST'])
def convert_images_route():
    """Convert images from edit_vid_input -> target size and write under edit_vid_output."""
    try:
        print("Processing request.convert_images")

        mode = (request.form.get('mode') or 'portrait').strip().lower()
        fit = (request.form.get('fit') or 'contain').strip().lower()
        bg = (request.form.get('bg') or 'blur').strip().lower()
        quality = request.form.get('quality') or 92

        # Optional custom size
        target_w_in = request.form.get('target_w')
        target_h_in = request.form.get('target_h')

        in_dir = (BASE_DIR / 'edit_vid_input').resolve()
        out_dir = (BASE_DIR / 'edit_vid_output').resolve()

        MODE_TO_SIZE = {
            "portrait": (1080, 1920),
            "1000x1500": (1000, 1500),
            "landscape": (1920, 1080),  # ✅ locked as requested
        }

        if fit not in ("contain", "cover"):
            return jsonify({"ok": False, "error": f"Invalid fit: {fit}"}), 400
        if bg not in ("blur", "white"):
            return jsonify({"ok": False, "error": f"Invalid bg: {bg}"}), 400

        try:
            quality = max(1, min(int(quality), 95))
        except Exception:
            quality = 92

        # Resolve target size
        if mode == "custom":
            try:
                target_w = int(target_w_in)
                target_h = int(target_h_in)
                if target_w <= 0 or target_h <= 0:
                    raise ValueError
            except Exception:
                return jsonify({
                    "ok": False,
                    "error": "Invalid custom size. Provide target_w and target_h."
                }), 400
        else:
            if mode not in MODE_TO_SIZE:
                return jsonify({
                    "ok": False,
                    "error": f"Invalid mode: {mode}. Supported: {list(MODE_TO_SIZE.keys()) + ['custom']}"
                }), 400
            target_w, target_h = MODE_TO_SIZE[mode]

        if not in_dir.exists():
            return jsonify({"ok": False, "error": f"Input folder not found: {in_dir}"}), 400

        from pathlib import Path
        import os
        from convert_landscape_img import convert_one, SUPPORTED_EXTS

        read_count = 0
        wrote_count = 0

        for root, _, files in os.walk(in_dir):
            root_p = Path(root)
            rel = root_p.relative_to(in_dir)

            for fn in files:
                if Path(fn).suffix.lower() not in SUPPORTED_EXTS:
                    continue

                read_count += 1
                in_path = root_p / fn
                out_path = out_dir / rel / Path(fn).with_suffix(".png")

                try:
                    convert_one(
                        in_path=in_path,
                        out_path=out_path,
                        target_w=target_w,
                        target_h=target_h,
                        fit=fit,
                        bg_style=bg,
                        quality=quality,
                    )
                    wrote_count += 1
                except Exception as e:
                    print(f"⚠️ Failed: {in_path} -> {e}")

        return jsonify({
            "ok": True,
            "read_count": read_count,
            "wrote_count": wrote_count,
            "output_dir": str(out_dir),
            "mode": mode,
            "target_w": target_w,
            "target_h": target_h,
            "fit": fit,
            "bg": bg,
            "quality": quality,
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500



@app.route('/batchmakevideoimagesfromdir', methods=['POST'])
def batch_make_video_images_from_dir_route():
    try:
        print("Processing request.batch_make_video_images_from_dir")

        # Read directory path from the form
        raw_source = (request.form.get('source_dir') or "").strip()
        target_size = (request.form.get('size_option') or "portrait").strip()
        if not raw_source:
            return "❌ Please provide a source directory.", 400

        # Normalize slashes
        raw_source = raw_source.replace("\\", "/")
        print(f"[DEBUG] raw source_dir from UI: {raw_source}")

        from pathlib import Path

        # If it's not absolute, treat it as relative to BASE_DIR
        p = Path(raw_source)
        if not p.is_absolute():
            full_source_dir = (BASE_DIR / raw_source).resolve()
        else:
            full_source_dir = p.resolve()

        print(f"[DEBUG] Resolved full source_dir: {full_source_dir}")

        # Import your batch helper
        from for_coloring_pin_load_pinterest_excel import batch_make_video_images_from_dir

        # Call the batch function; it returns processed image count
        result = batch_make_video_images_from_dir(str(full_source_dir), target_size)

        if isinstance(result, int):
            msg = f"✅ Batch video generation completed. Processed {result} image(s)."
        else:
            msg = "✅ Batch video generation completed."

        print(msg)
        return msg, 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}", 500



@app.route('/process_master_shorts_file_data', methods=['POST'])
def process_master_shorts_file_data():
    try:
        upload_pins() #Pinterest upload
        upload_shorts_from_master_file() #YouTube shorts upload
        upload_facebook_videos() #Facebook videos upload
        upload_tiktok_videos() #TikTok videos upload
        upload_instagram_posts() #Instagram posts upload
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/select_background_video', methods=['POST'])
def select_background_video():
    """Copy chosen video to edit_vid_input folder for use."""
    try:
        # Be tolerant to different content types
        payload = request.get_json(silent=True) or {}
        src = (payload or {}).get('video') or request.form.get('video') or request.values.get('video')

        if not src:
            return jsonify({"error": "Missing video path"}), 400

        clear_folder("edit_vid_input")  # your helper

        filename = "bg_video.mp4"  # fixed name on destination
        src_path = os.path.join(BASE_DIR, src.strip("/"))
        dest_path = os.path.join(BASE_DIR, "edit_vid_input", filename)

        if not os.path.exists(src_path):
            return jsonify({"error": f"File not found: {src_path}"}), 404

        import shutil
        shutil.copy(src_path, dest_path)
        # return jsonify({"message": "✅ Video selected and ready for editing!", "dest": dest_path})
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/sounds/<path:filename>')
def serve_sound(filename):
    sounds_dir = os.path.join(app.root_path, 'sounds')
    return send_from_directory(sounds_dir, filename)


# ------------------------ API ROUTES ------------------------ #

@app.route('/get_full_text', methods=['GET'])
def get_full_text():
    try:
        with open("temp/full_text.txt", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

@app.route('/get_word_timestamps', methods=['GET'])
def get_word_timestamps():
    try:
        with open("temp/word_timestamps.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

@app.route('/save_word_timestamps', methods=['POST'])
def save_word_timestamps():
    try:
        data = request.json
        with open("temp/word_timestamps.json", "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return jsonify({"message": "✅ Word timestamps updated successfully!"})
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

@app.route('/get_structured_output', methods=['GET'])
def get_structured_output():
    try:
        with open("temp/structured_output.json", "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

# ------------------------ HTML UI ROUTES ------------------------ #

@app.route('/')
def index():
    return render_template('index.html',
        music_options=background_music_options,
        style_options=font_settings,
        tts_options=tts_engine,
        voice_genders=voices,
        voice_map=voices,
        sizes=sizes
    )

@app.route('/thumbnail')
def thumbnail():
    return render_template('thu_index.html')

@app.route('/scene_builder')
def scene_builder():
    return render_template('scene_builder.html')

@app.route('/coloring_book_builder')
def coloringbook():
    return render_template('coloring-book-builder.html')

@app.route('/hindi_caption_builder')
def hindicaptions():
    return render_template('hindi_caption_builder.html')

@app.route('/aivideoprompt')
def aivideoprompt():
    return render_template('aivideoprompt.html')

@app.route('/prepare_captions')
def prep_caption():
    return render_template('index_captions.html')

@app.route('/flipping_book')
def flipping_book():
    return render_template('flipping_book.html')

@app.route('/portrait_website_loader')
def portrait_website_loader():
    return render_template('portrait_website_loader.html')

@app.route('/video/<filename>')
def serve_video(filename):
    return send_from_directory(directory='.', path=filename)

@app.route('/create_portrait_n_add_caption')
def create_portrait_n_add_caption():
    try:
        print("Processing request...create_portrait_n_add_caption")
        create_portrait()
        add_caption()
        return "✅ create_portrait_n_add_caption completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.route('/apply_caption')
def add_caption():
    try:
        print("Processing request...apply_caption")

        from apply_captions import add_captions_to_video

        # If edit_vid_output/out_landscape.mp4 and edit_vid_output/captions_landscape.ass exists
        

        if os.path.isfile("edit_vid_output/out_landscape.mp4") and os.path.isfile("edit_vid_output/captions_landscape.ass"):
            add_captions_to_video("edit_vid_output/out_landscape.mp4", "edit_vid_output/captions_landscape.ass", "edit_vid_output/landscape_with_captions.mp4")
        if os.path.isfile("edit_vid_output/out_portrait.mp4") and os.path.isfile("edit_vid_output/captions_portrait.ass"):
            add_captions_to_video("edit_vid_output/out_portrait.mp4", "edit_vid_output/captions_portrait.ass", "edit_vid_output/portrait_with_captions.mp4")

        return "✅ apply_caption completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500  


@app.route('/convert_landscape_to_portrait')
def create_portrait():
    try:
        print("Processing request...convert_landscape_to_portrait")

        from convert_to_portrait import convert_landscape_to_portrait
        if os.path.isfile("edit_vid_output/out_landscape.mp4"):
            convert_landscape_to_portrait("edit_vid_output/out_landscape.mp4", "edit_vid_output/out_portrait.mp4")

        return "✅ convert_landscape_to_portrait completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500  

@app.route('/process', methods=['POST'])
def process():
    try:
        print("Processing request...")
        urls = request.form.get('urls', '')
        excel = request.form.get('excel', 'no')
        notebooklm = request.form.get('notebooklm', 'no')
        language = request.form.get('language', 'english')
        tts = request.form.get('tts', 'google')
        gender = request.form.get('gender', 'Female')
        voice = request.form.get('voice', 'Joanna')
        size = request.form.get('size', 'YouTube Shorts')
        music = request.form.get('music')
        max_words = int(request.form.get('max_words', 4))
        fontsize = int(request.form.get('fontsize', 90))
        y_pos = request.form.get('y_pos', 'center')
        style = request.form.get('style', 'style2')
        skip_puppeteer = request.form.get('skip_puppeteer', 'no')
        skip_captions = request.form.get('skip_captions', 'no')
        pitch = request.form.get('pitch', 'adult')
        disable_subscribe = request.form.get('disable_subscribe', 'no')

        scrape_and_process(urls, excel, size, music, max_words, fontsize, y_pos,
                           style, voice, language, gender, tts,
                           skip_puppeteer, skip_captions, pitch, disable_subscribe, notebooklm)

        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.post("/prepare_captions_from_heygen")
def heygen_init_captions():
    """
    Upload HeyGen mp4, extract audio.wav, generate temp/word_timestamps.json,
    then UI can call /word_timestamps to load it.
    """
    try:
        CAPTION_LANG_OPTIONS = ["english", "hindi"]
        language = (request.form.get("language") or "english").strip().lower()
        if language not in CAPTION_LANG_OPTIONS:
            language = "english"

        music = (request.form.get("music") or "no").strip().lower()  # optional
        is_song = (music == "yes")

        f = request.files.get("heygen")
        if not f or not f.filename:
            return jsonify({"ok": False, "error": "Missing HeyGen video file (form field name: file)."}), 400

        orig_name = Path(f.filename).stem   # "my_heygen_video"
        orig_ext  = Path(f.filename).suffix # ".mp4"

        meta_path = OUT_DIR / "job_meta.json"
        meta_path.write_text(json.dumps({
            "orig_name": orig_name,
            "orig_ext": orig_ext
        }, indent=2))

        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in VIDEO_EXTS:
            return jsonify({"ok": False, "error": f"Unsupported video type: {ext}"}), 400

        # Save uploaded HeyGen video
        uploads_dir = Path(__file__).resolve().parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        heygen_path = uploads_dir / f"heygen{ext}"
        f.save(str(heygen_path))

        # Extract audio.wav beside server.py (AUDIO_PATH already points to BASE_DIR/audio.wav)
        base_dir = Path(__file__).resolve().parent
        res = extract_audio_from_video(
            base_dir=base_dir,
            input_path=heygen_path.resolve(),
            fmt="wav",
            track=0,
            root_output_name="audio"  # -> audio.wav
        )

        if not getattr(res, "ok", False):
            return jsonify({"ok": False, "error": res.error or "Audio extract failed", "detail": res.detail}), 500

        # Generate captions/word timestamps (writes temp/word_timestamps.json)
        prepare_captions_file_for_notebooklm_audio(
            audio_path=str(AUDIO_PATH),   # "audio.wav"
            language=language,
            is_song=is_song
        )

        return jsonify({
            "ok": True,
            "language": language,
            "audio": "audio.wav",
            "word_timestamps": "/word_timestamps"
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/caption', methods=['POST'])
def caption():
    try:
        print("Processing request...caption")
        music = request.form.get('music', 'no')
        language = request.form.get('language', 'english')
        prepare_captions_file_for_notebooklm_audio(
            audio_path="audio.wav",
            language=language,
            is_song=music == 'yes'
        )

        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.route('/generatettsaudio', methods=['POST'])
def generatettsaudio():
    try:
        print("Processing request...generatettsaudio")

        ttstext = request.form.get('ttstext', '')

        language = request.form.get('language', 'english')
        tts_engine = request.form.get('tts', 'google')
        gender = request.form.get('gender', 'Female')
        output_audio_file = "audio.wav"
        clear_folder("edit_vid_audio")

        generated_file = get_audio_file(ttstext, output_audio_file, tts_engine, language, gender)
        shutil.copy("audio.wav", "edit_vid_audio/audio.wav")
        
        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

@app.route("/get_audio", methods=["POST"])
def get_audio():
    """Generate and return TTS audio for question text."""
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    language = data.get("language", "en").lower()
    if not text:
        return jsonify({"error": "Missing text"}), 400

    try:
        # Temporary file for the output audio
        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()

        # Generate audio using the existing TTS pipeline
        get_audio_file(
            text=text,
            audio_file_name=tmp_path,
            tts_engine="google",   # or "amazon" if you prefer
            language="hindi" if language.startswith("hi") else "english",
            gender="Male",
            type="journey",        # "neural" / "journey" / "generative"
            age_group="adult"
        )

        return send_file(tmp_path, mimetype="audio/mpeg")

    except Exception as e:
        print(f"[TTS ERROR] {e}")
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500

@app.route('/bulkupload', methods=['POST'])
def bulkupload():
    try:
        print("Processing request...upload_videos")
        upload_videos()  # Assuming this function is defined in youtube_uploader.py

        # return "✅ Processing started!"
        return "✅ Processing completed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500
    
@app.route('/runobsrecorder', methods=['POST'])
def run_obs_recorder():
    try:
        print("Processing request...run OBS recorder")
        orientation = request.form.get('orientation', 'landscape')
        duration = request.form.get('duration', '10')  # Default to 10 seconds if not provided
        selectedStyle = request.form.get('captStyle', 'style1')
        captionLength = request.form.get('captLength', '5')
        bgMusicSelected = request.form.get('bgMusicSelect', 'none')
        minLineGapSec = request.form.get('minLineGapSec', '0.40')
        disableSubscribe = request.form.get('disableSubscribe', 'yes')
        outputfile = request.form.get('outputfile', 'test.mp4')
        language = request.form.get('language', 'english')

        if language == "english":
            if selectedStyle == "story-block":
                selectedStyle = "story-block-english"
            elif selectedStyle == "song-block":
                selectedStyle = "song-block-english"


        print("Form payload →", request.form.to_dict(flat=False))
        
        cmd = [
            "node", "puppeteer-launcher.js",
            outputfile, duration, orientation, captionLength, selectedStyle,
            bgMusicSelected, "0.05", "1", disableSubscribe, minLineGapSec
        ]
        print("▶️ Running Puppeteer with:", cmd)
        import subprocess
        subprocess.run(cmd)

        shutil.copy(outputfile, "processed_videos/output.mp4")
        # Here you would call the function to run OBS recorder
        # For example: run_obs_recorder_function()

        # return "✅ Processing started!"
        return "✅ OBS Recorder started successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500
    
@app.route('/editvideos', methods=['POST'])
def run_video_editor():
    try:
        print("Processing request...run edit videos")
        orientation = request.form.get('orientation', 'auto')
        add_music = True
        bg_music_folder = request.form.get('bgmusic')
        if bg_music_folder == 'none':
            add_music = False
        topcut = request.form.get('topcut',0)
        if topcut == '':
            topcut = 0

        bottomcut = request.form.get('bottomcut',0)
        if bottomcut == '':
            bottomcut = 0

        slowfactor = request.form.get('slowfactor',0)
        if slowfactor == '':
            slowfactor = 0

        slow_down = True
        if slowfactor == 0:
            slow_down = False

        add_watermark = True

        watermarkposition = request.form.get('watermarkposition','bottom-left')
        if watermarkposition == "none":
            add_watermark = False

        batch_process(
            input_folder="edit_vid_input",
            output_folder="edit_vid_output",
            bg_music_folder="god_bg",
            remove_top=float(topcut),
            remove_bottom=float(bottomcut),
            add_music=add_music,
            slow_down=slow_down,
            slow_down_factor=float(slowfactor),
            target_orientation=orientation, 
            add_watermark=add_watermark,
            watermark_path="logo.png",
            watermark_position=watermarkposition,
            watermark_scale=0.15
        )
        return "✅ Videos Processed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500    

@app.route('/sunotovideogenerator', methods=['POST'])
def run_sunotovideogenerator():
    try:
        print("*** Processing request sunotovideogenerator: Enlarging clip")
        orientation = 'auto'
        add_music = False
        topcut = 0
        bottomcut = 0
        slow_down = True
        slowfactor = request.form.get('slowfactor',1)
        if slowfactor == '' or slowfactor == '1':
            slowfactor = 1
            slow_down = False

        size = request.form.get('size', 'landscape')

        add_watermark = False
        watermarkposition = 'bottom-left'

        batch_process(
            input_folder="edit_vid_input",
            output_folder="edit_vid_output",
            bg_music_folder="god_bg",
            remove_top=float(topcut),
            remove_bottom=float(bottomcut),
            add_music=add_music,
            slow_down=slow_down,
            slow_down_factor=float(slowfactor),
            target_orientation=orientation, 
            add_watermark=add_watermark,
            watermark_path="logo.png",
            watermark_position=watermarkposition,
            watermark_scale=0.15
        )
        print("✅ Processing request sunotovideogenerator: Enlarging completed successfully")
        # copy files from edit_vid_output to edit_vid_input for next step
        import shutil
        for filename in os.listdir("edit_vid_output"):
            shutil.copy(os.path.join("edit_vid_output", filename), os.path.join("edit_vid_input", filename))

        print("*** Processing request sunotovideogenerator: Assembling clips to make video song")
        assemble_videos(
            video_folder="edit_vid_input",                  # or "edit_vid_output" if you pre-made KB clips
            audio_folder="edit_vid_audio",
            output_path="edit_vid_output/composed_video.mp4",
            fps=30,
            shuffle=True,                                   # different order each run
            prefer_ffmpeg_concat=True                       # auto-uses concat if safe; else MoviePy
        )

        print("✅ Processing request sunotovideogenerator: Assembling completed successfully")
        # place copy of audio file (mp3/wav) from edit_vid_audio to root folder as audio.wav

        audio_folder = "edit_vid_audio"
        import shutil
        from pydub import AudioSegment
        # get the first file found in that folder
        audio_file = os.listdir(audio_folder)[0]
        audio_path = os.path.join(audio_folder, audio_file)

        # output path in root folder
        output_path = "audio.wav"

        # convert mp3 → wav (if needed), else just copy
        if audio_file.lower().endswith(".mp3"):
            # convert using pydub (requires ffmpeg installed)
            sound = AudioSegment.from_mp3(audio_path)
            sound.export(output_path, format="wav")
        else:
            # already wav → overwrite if exists
            shutil.copy(audio_path, output_path)

        print(f"✅ Saved audio file as {output_path}")

        #place copy of composed_video.mp4 from edit_vid_output to root folder as composed_video.mp4. Replace if exists

        shutil.copy("edit_vid_output/composed_video.mp4", "composed_video.mp4")

        # Also place copy of composed_video.mp4 from edit_vid_output to edit_vid_output/out_{size}.mp4. Replace if exists
        shutil.copy("edit_vid_output/composed_video.mp4", f"edit_vid_output/out_{size}.mp4")

        print("✅ Copied composed video to root folder as composed_video.mp4")


        print("*** Processing request sunotovideogenerator...creating captions file ")
        music = request.form.get('music', 'no')
        language = request.form.get('language', 'english')
        if language != 'hindi':
            prepare_captions_file_for_notebooklm_audio(
                audio_path="audio.wav",
                language=language,
                is_song=music == 'yes'
            )
        # else:
        #     if size == 'landscape':
        #         create_portrait()
            # add_caption()
        return "✅ Videos Processed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500    


@app.route('/sunonimagetovideogenerator', methods=['POST'])
def run_sunonimagetovideogenerator():
    try:
        print("*** Processing request sunonimagetovideogenerator: creating clips")
        duration = request.form.get('duration',10)
        if duration == '':
            duration = 10

        video_size = (1920,1080)
        size = request.form.get('size', 'landscape')
        if size == 'portrait':
            video_size = (1080,1920)

        from make_kb_videos import export_kb_videos
        export_kb_videos(
            input_folder="edit_vid_input",   # folder with images
            out_folder="edit_vid_output",    # where to save KB clips
            per_image=int(duration),            # seconds per image
            output_size=video_size,
            zoom_start=1.0, zoom_end=1.05
        )
        print("✅ Processing request sunonimagetovideogenerator: Creating clips completed successfully")
        # copy files from edit_vid_output to edit_vid_input for next step
        import shutil
        for filename in os.listdir("edit_vid_output"):
            shutil.copy(os.path.join("edit_vid_output", filename), os.path.join("edit_vid_input", filename))

        print("*** Processing request sunonimagetovideogenerator: Assembling clips to make video song")

        assemble_videos(
            video_folder="edit_vid_input",                  # or "edit_vid_output" if you pre-made KB clips
            audio_folder="edit_vid_audio",
            output_path="edit_vid_output/composed_video.mp4",
            fps=30,
            shuffle=True,                                   # different order each run
            prefer_ffmpeg_concat=True                       # auto-uses concat if safe; else MoviePy
        )

        print("✅ Processing request sunonimagetovideogenerator: Assembling completed successfully")
        # place copy of audio file (mp3/wav) from edit_vid_audio to root folder as audio.wav

        audio_folder = "edit_vid_audio"
        import shutil
        from pydub import AudioSegment
        # get the first file found in that folder
        audio_file = os.listdir(audio_folder)[0]
        audio_path = os.path.join(audio_folder, audio_file)

        # output path in root folder
        output_path = "audio.wav"

        # convert mp3 → wav (if needed), else just copy
        if audio_file.lower().endswith(".mp3"):
            # convert using pydub (requires ffmpeg installed)
            sound = AudioSegment.from_mp3(audio_path)
            sound.export(output_path, format="wav")
        else:
            # already wav → overwrite if exists
            shutil.copy(audio_path, output_path)

        print(f"✅ Saved audio file as {output_path}")

        #place copy of composed_video.mp4 from edit_vid_output to root folder as composed_video.mp4. Replace if exists

        shutil.copy("edit_vid_output/composed_video.mp4", "composed_video.mp4")
        print("✅ Copied composed video to root folder as composed_video.mp4")

        # Also place copy of composed_video.mp4 from edit_vid_output to edit_vid_output/out_{size}.mp4. Replace if exists
        shutil.copy("edit_vid_output/composed_video.mp4", f"edit_vid_output/out_{size}.mp4")

        print("*** Processing request sunotovideogenerator...creating captions file ")
        language = request.form.get('language', 'english')
        music = request.form.get('music', 'no')

        if language != 'hindi':
            prepare_captions_file_for_notebooklm_audio(
                audio_path="audio.wav",
                language=language,
                is_song=music == 'yes'
            )
        # else:
        #     if size == 'landscape':
        #         create_portrait()
        #     # add_caption()
        return "✅ Videos Processed successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500    

# ------------------------ MAIN ------------------------ #
@app.route('/addoverlays', methods=['POST'])
def add_overlays():
    try:
        print("Processing request...add overlays")
        add_petal_overlay = request.form.get('add_petals', 'no') == 'yes'
        add_sparkle_overlay = request.form.get('add_sparkles', 'no') == 'yes'
        overlay_position = (0, 0)  # Default position, can be modified as needed

        from add_overlays import add_gif_overlays_to_videos
        add_gif_overlays_to_videos(
            input_folder="edit_vid_input",
            output_folder="edit_vid_output",
            add_petal_overlay=add_petal_overlay,
            add_sparkle_overlay=add_sparkle_overlay,
            overlay_position=overlay_position
        )
        return "✅ Overlays added successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500  

@app.route('/multiplyvideo', methods=['POST'])
def multiply_video():
    try:
        print("Processing request...multiplyvideo")
        repeat_factor = request.form.get('repeat_factor', 1)
        if repeat_factor == '':
            repeat_factor = 1

        from multiply_video import multiply_videos
        multiply_videos(
            input_folder="edit_vid_input",
            output_folder="edit_vid_output",
            repeat_factor=int(repeat_factor)
        )
        return "✅ Video multiplied successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500  

@app.route('/makekbvideofromimages', methods=['POST'])
def make_kb_video():
    try:
        print("Processing request...makekbvideo")

        duration = request.form.get('duration',10)
        if duration == '':
            duration = 10

        video_size = (1920,1080)
        size = request.form.get('size', 'landscape')
        if size == 'portrait':
            video_size = (1080,1920)

        from make_kb_videos import export_kb_videos
        export_kb_videos(
            input_folder="edit_vid_input",   # folder with images
            out_folder="edit_vid_output",    # where to save KB clips
            per_image=int(duration),            # seconds per image
            output_size=video_size,
            zoom_start=1.0, zoom_end=1.05
        )
        return "✅ Ken Burns videos created successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

def _files_with_ext(folder: str, exts: set[str]) -> list[str]:
    p = Path(folder)
    if not p.exists() or not p.is_dir():
        return []
    return [
        f.name for f in p.iterdir()
        if f.is_file() and f.suffix.lower() in exts
    ]

@app.route('/assembleclipstomakevideosong', methods=['POST'])
def assemble_clips_to_make_video_song():    
    try:
        print("Processing request...asseleclipstomakevideosong")
        #return with error message if edit_vid_input is empty

        video_input_folder = "edit_vid_input"
        copyforcaption = request.form.get('copyforcaption','no')
        # --- Validate inputs up front ---
        if not os.path.isdir(video_input_folder):
            print( "❌ Folder 'edit_vid_input' does not exist.")
            return jsonify({"error": "❌ Folder 'edit_vid_input' does not exist."}), 400

        video_files = _files_with_ext(video_input_folder, VIDEO_EXTS)
        if not video_files:
            print("❌ No video files found in 'edit_vid_input'.")
            return jsonify({                
                "error": "❌ No video files found in 'edit_vid_input'.",
                "hint":  "Add at least one of: .mp4, .mov, .mkv, .avi, .webm, .m4v"
            }), 400

        keep_video_audio = request.form.get('keep_video_audio','no')
        video_volume = float(request.form.get('video_volume',0.3))
        bg_volume = float(request.form.get('bg_volume',1.0))
        add_titles = request.form.get('add_titles', 'no') == 'yes'
        add_transitions = request.form.get('add_transitions', 'no') == 'yes'
        title_sec = float(request.form.get('title_sec', 2.0))
        transition_sec = float(request.form.get('transition_sec', 0.5))

        # --- NEW: If order.xlsx has a Title column (B), build one output per story group (no bg audio) ---
        group_outputs = assemble_videos_by_titles_if_present(
            video_folder="edit_vid_input",
            output_dir="edit_vid_output",
            fps=30,
            prefer_ffmpeg_concat=True,
            keep_video_audio=(keep_video_audio == 'yes'),
            video_volume=video_volume,
            bg_volume=bg_volume,
            add_titles=add_titles,
            title_sec=title_sec,
            add_transitions=add_transitions,
            transition_sec=transition_sec
        )

        if group_outputs:
            return jsonify({
                "ok": True,
                "mode": "story_groups",
                "outputs": group_outputs
            }), 200


        # ---- Derive output filename from first input video ----
        first_video = sorted(video_files)[0]  # deterministic
        base_name = os.path.basename(first_video)  # e.g. my_clip_01.mp4
        output_video_path = os.path.join("edit_vid_output", base_name)


        assemble_videos(
            video_folder="edit_vid_input",                  # or "edit_vid_output" if you pre-made KB clips
            audio_folder="edit_vid_audio",
            output_path=output_video_path,
            fps=30,
            shuffle=True,                                   # different order each run
            prefer_ffmpeg_concat=True,                       # auto-uses concat if safe; else MoviePy
            keep_video_audio = keep_video_audio == 'yes',
            video_volume = video_volume,
            bg_volume = bg_volume,
            add_titles=add_titles,
            title_sec=title_sec,
            add_transitions=add_transitions,
            transition_sec=transition_sec
        )
        if copyforcaption == 'no':
            return "✅ Video song assembled successfully!", 200
        
        shutil.copy(output_video_path, "composed_video.mp4")

        audio_folder = "edit_vid_audio"
        from pydub import AudioSegment
        # get the first file found in that folder
        audio_file = os.listdir(audio_folder)[0]
        audio_path = os.path.join(audio_folder, audio_file)

        # output path in root folder
        output_path = "audio.wav"

        # convert mp3 → wav (if needed), else just copy
        if audio_file.lower().endswith(".mp3"):
            # convert using pydub (requires ffmpeg installed)
            sound = AudioSegment.from_mp3(audio_path)
            sound.export(output_path, format="wav")
        else:
            # already wav → overwrite if exists
            shutil.copy(audio_path, output_path)

        print(f"✅ Saved audio file as {output_path}")

        return "✅ Video song assembled successfully!", 200
    except Exception as e:
        traceback.print_exc() 
        return f"❌ Error: {str(e)}", 500


# server.py
@app.route('/splitvideotoparts', methods=['POST'])
def splitvideotoparts():
    try:
        print("Processing request...splitvideotoparts")
        from assemble_from_videos import split_video, convert_landscape_to_portrait

        # existing field
        max_duration = str(request.form.get('duration', '178')).strip()

        # new fields
        convert_portrait = (request.form.get('convert_portrait', 'no') == 'yes')
        portrait_size    = (request.form.get('portrait_size', '1080x1920') or '1080x1920')
        focus            = (request.form.get('focus', 'center') or 'center')
        keep_audio       = (request.form.get('keep_audio', 'yes') == 'yes')

        # default source your UI mentions
        # (you already inform users the input lives here)
        in_path  = "edit_vid_output/output.mp4"
        work_src = in_path

        # Optional pre-pass: crop to 9:16 and scale
        if convert_portrait:
            out_portrait = "edit_vid_output/output_portrait.mp4"
            convert_landscape_to_portrait(
                input_path=in_path,
                output_path=out_portrait,
                portrait_size=portrait_size,
                focus=focus,
                keep_audio=keep_audio
            )
            work_src = out_portrait

        # Now split whichever source we decided on
        split_video(
            input_path=work_src,
            max_duration=max_duration
        )

        return "✅ splitvideotoparts completed successfully!", 200
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error: {str(e)}", 500


@app.route('/save_word_timestamps_file', methods=['POST'])
def save_word_timestamps_file():
  data = request.get_json(force=True)  # list of {word,start,end,position,matched}
  os.makedirs('temp', exist_ok=True)
  path = os.path.join('temp', 'word_timestamps.json')
  with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
  return jsonify({"ok": True, "path": "/temp/word_timestamps.json"})    

@app.route('/save_ass', methods=['POST'])
def save_ass():
    """
    Save a .ass subtitle file to the parent folder of this server.py.
    Body: {"filename": "captions_landscape.ass", "content": "...ass text..."}
    """
    try:
        data = request.get_json(force=True, silent=False)
        if not data:
            return jsonify({"ok": False, "error": "Empty payload"}), 400

        filename = str(data.get("filename", "")).strip()
        content  = str(data.get("content", ""))

        # sanitize filename (letters, numbers, ., _, -) and require .ass
        filename = re.sub(r'[^A-Za-z0-9._-]', '_', filename)
        if not filename or not filename.endswith(".ass"):
            return jsonify({"ok": False, "error": "Bad filename"}), 400

        # parent directory of this file's directory
        parent_dir    = os.path.dirname(os.path.abspath(__file__))

        # Go to sub-folder with name edit_vid_output

        # Path to the subfolder 'edit_vid_output'
        output_dir = os.path.join(parent_dir, "edit_vid_output")

        #parent_dir = os.path.abspath(os.path.join(app_dir, os.pardir))

        if not os.path.isdir(output_dir) or not os.access(output_dir, os.W_OK):
            return jsonify({"ok": False, "error": "Parent folder not writable"}), 500

        target_path = os.path.join(output_dir, filename)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        return jsonify({"ok": True, "path": target_path})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/render_captions', methods=['POST'])
def render_captions():

    from wordtimestamps_to_ass_captions import build_ass_from_word_json, _ffmpeg_burn_subs

    """
    Body JSON:
    {
      "input_video": "/absolute/or/relative/path.mp4",
      "orientation": "landscape"|"portrait",
      "style": "cinematic"|"pro_pop"|"drift_up"|"typewriter"|"fade"|"softzoom"|"wordpop"|"glowpulse",
      "min_gap_sec": 0.40,
      "words_per_caption": 5,
      "output": "/path/output_with_captions.mp4" (optional)
    }
    """
    try:
        data = request.get_json(force=True)
        #input_video = data.get('input_video')
        orientation = data.get('orientation', 'landscape')
        style = data.get('style', 'cinematic')
        min_gap = float(data.get('min_gap_sec', 0.40))
        wpc = int(data.get('words_per_caption', 5))
        #output = data.get('output')

        if orientation == 'landscape':
            create_portrait()

        # if not input_video or not os.path.isfile(input_video):
        #     return jsonify({"ok": False, "error": "input_video not found"}), 400

        # Where is your word_timestamps.json?  Adjust if needed.
        # (Uses the same JSON you already serve to the front end.)
        app_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(app_dir, 'temp')
        word_json_path = os.path.join(temp_dir, 'word_timestamps.json')
        if not os.path.isfile(word_json_path):
            # fallback: try parent folder
            word_json_path = os.path.abspath(os.path.join(app_dir, os.pardir, 'word_timestamps.json'))
        if not os.path.isfile(word_json_path):
            return jsonify({"ok": False, "error": "word_timestamps.json not found"}), 400

        # Build ASS (both orientations saved; use requested orientation for render)
        parent_dir = os.path.abspath(os.path.join(app_dir, os.pardir))
        out_dir = os.path.join(app_dir, 'edit_vid_output')
        os.makedirs(out_dir, exist_ok=True)

        ass_land = build_ass_from_word_json(word_json_path, 'landscape', style, min_gap, wpc)
        ass_port = build_ass_from_word_json(word_json_path, 'portrait',  style, min_gap, wpc)

        path_land = os.path.join(out_dir, 'captions_landscape.ass')
        path_port = os.path.join(out_dir, 'captions_portrait.ass')
        with open(path_land, 'w', encoding='utf-8') as f: f.write(ass_land)
        with open(path_port, 'w', encoding='utf-8') as f: f.write(ass_port)

        # Choose the ASS we render with
        #ass_path = path_port if orientation == 'portrait' else path_land

        # Output path
        # if not output:
        #     base = os.path.splitext(os.path.basename(input_video))[0]
        #     output = os.path.join(parent_dir, f"{base}_with_captions.mp4")

        # Burn it in
        proc = _ffmpeg_burn_subs("edit_vid_output/out_landscape.mp4", path_land, "edit_vid_output/landscape_with_captions.mp4")
        if proc.returncode != 0:
            return jsonify({"ok": False, "error": "ffmpeg failed", "stderr": proc.stderr}), 500

        proc = _ffmpeg_burn_subs("edit_vid_output/out_portrait.mp4", path_port, "edit_vid_output/portrait_with_captions.mp4")
        if proc.returncode != 0:
            return jsonify({"ok": False, "error": "ffmpeg failed", "stderr": proc.stderr}), 500


        return jsonify({
            "ok": True,
            "ass_landscape": path_land,
            "ass_portrait": path_port
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
def bool_from_form(val: str) -> bool:
    """
    Accepts 'true'/'false', 'on'/'off', '1'/'0', or truthy string.
    """
    if val is None:
        return False
    v = str(val).strip().lower()
    return v in ("true", "on", "1", "yes", "y")

@app.post("/upload")
def uploadVid():
    from pathlib import Path
    from datetime import datetime
    from flask import Flask, render_template, request, jsonify
    from playwright.sync_api import sync_playwright
    import youtube_uploader as yu
    try:
        # Collect inputs from form
        video_path            = (request.form.get("video_path") or "").strip()
        youtube_channel_name  = (request.form.get("youtube_channel_name") or "").strip()
        youtube_playlist_name = (request.form.get("youtube_playlist_name") or "").strip()
        youtube_title         = (request.form.get("youtube_title") or "").strip()
        youtube_description   = (request.form.get("youtube_description") or "").strip()
        youtube_tags          = (request.form.get("youtube_tags") or "").strip()
        made_for_kids         = bool_from_form(request.form.get("made_for_kids"))
        schedule_date_raw     = (request.form.get("schedule_date") or "").strip()
        size                  = (request.form.get("size") or "").strip()

        # Build the dict in the exact shape your upload_video expects
        video_info = {
            "video_path": video_path,                         # uploader will append .mp4 and prepend processed_videos
            "youtube_channel_name": youtube_channel_name,
            "youtube_playlist_name": youtube_playlist_name,
            "youtube_title": youtube_title,
            "youtube_description": youtube_description,
            "youtube_tags": youtube_tags,
            "made_for_kids": made_for_kids,
            "schedule_date": schedule_date_raw or None,       # keep raw; your code formats it for YouTube
            "thumbnail_path": "edit_vid_thumbnail/thumbnail.png",
            "size": size
        }

        # Basic validation
        missing = [k for k in ("video_path","youtube_channel_name","youtube_title") if not video_info[k]]
        if missing:
            return jsonify({"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400

        # Launch persistent Chrome with your existing settings
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                yu.PROFILE_DIR,
                headless=False,
                executable_path=yu.CHROME_EXECUTABLE,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            )
            page = browser.new_page()
            page.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined})""")

            # Do the upload (reuses your function)
            video_url = yu.upload_video(page, video_info)

            browser.close()

        return jsonify({"ok": True, "video_url": video_url})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    
def clear_folder(folder_path, extensions=None):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    for file in os.listdir(folder_path):
        full_path = os.path.join(folder_path, file)
        if os.path.isfile(full_path):
            if not extensions or file.lower().endswith(extensions):
                os.remove(full_path)


def clear_old_pages():
    """Delete any existing generated page images."""
    for pattern in ("*.png", "*.jpg", "*.jpeg"):
        for f in glob.glob(os.path.join(PAGES_FOLDER, pattern)):
            try:
                os.remove(f)
            except OSError:
                pass


def pdf_to_images(pdf_path):
    """
    Convert a PDF into PNG pages under static/pages/.
    Returns list of static URLs for those pages.
    """
    clear_old_pages()

    pages = convert_from_path(pdf_path, dpi=120, poppler_path=POPPLER_PATH)

    urls = []
    for i, page in enumerate(pages, start=1):
        filename = f"page_{i:03}.png"
        full_path = os.path.join(PAGES_FOLDER, filename)
        page.save(full_path, "PNG")

        # URL for browser
        urls.append(url_for("static", filename=f"pages/{filename}", _external=False))

    return urls

@app.route("/pdf_to_flipping_book")
def pdf_to_flipping_book():
    return render_template("pdf_to_flipping_book.html")

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    if "pdf" not in request.files:
        return jsonify({"success": False, "error": "No file part 'pdf' found."}), 400

    pdf_file = request.files["pdf"]
    if pdf_file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    pdf_path = os.path.join(UPLOAD_FOLDER, "current.pdf")
    pdf_file.save(pdf_path)

    try:
        page_urls = pdf_to_images(pdf_path)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    if not page_urls:
        return jsonify({"success": False, "error": "No pages generated."}), 500

    return jsonify({"success": True, "pages": page_urls})

if __name__ == '__main__':
    # app.run(debug=True, port=5000)

    # DND - Working but not in use
    # from gemini_pool import GeminiPool
    # GEM_STATE = str((Path(__file__).resolve().parent / ".gemini_pool_state.json"))
    # gemini_pool = GeminiPool(
    #     api_keys=None,
    #     per_key_rpm=25,
    #     state_path=GEM_STATE,
    #     autosave_every=3,
    # )   
    #  
    app.run(debug=True, host='0.0.0.0', port=5000)  # Use host='
