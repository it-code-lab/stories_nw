import shutil
from time import time
from flask import Flask, request, jsonify, render_template, send_from_directory, abort
import subprocess, json, math
from flask_cors import CORS
import os
import traceback  # to print detailed error info
from caption_generator import prepare_captions_file_for_notebooklm_audio
from get_audio import get_audio_file
from scraper import scrape_and_process  # Ensure this exists
from settings import background_music_options, font_settings, tts_engine, voices, sizes
from video_editor import batch_process
from youtube_uploader import upload_videos
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
from google import genai
from google.genai import types
import os
from flipthrough_video import generate_flipthrough_video, FlipThroughError
from bg_music_video import merge_video_with_bg_music, BgMusicError
import sys

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

# =========================
# Defaults (env-overridable)
# =========================
DEFAULT_TEXT_MODEL  = os.getenv("GEMINI_DEFAULT_TEXT_MODEL",  "gemini-2.0-flash")
DEFAULT_IMAGE_MODEL = os.getenv("GEMINI_DEFAULT_IMAGE_MODEL", "gemini-2.5-flash-image")


# Optional: central place to tweak RPM/paths
GEM_STATE = str(BASE_DIR / ".gemini_pool_state.json")

gemini_pool = None


@app.post("/merge_bg_music")
def merge_bg_music_route():
    """
    Mix background music (from edit_vid_audio/) into the first video in edit_vid_input/.
    Expects form fields:
      - bg_volume: float, 0.0–2.0 (default 0.3)
      - video_volume: float, 0.0–2.0 (default 1.0) – optional
      - out_name: optional output filename (default 'video_with_music.mp4')

    Output is written to edit_vid_output/<out_name>.
    Returns JSON with a web path you can use in the UI.
    """
    try:
        bg_volume = float(request.form.get("bg_volume", "0.3") or "0.3")
    except ValueError:
        bg_volume = 0.3

    try:
        video_volume = float(request.form.get("video_volume", "1.0") or "1.0")
    except ValueError:
        video_volume = 1.0

    out_name = (request.form.get("out_name") or "video_with_music.mp4").strip()

    try:
        out_path = merge_video_with_bg_music(
            base_dir=BASE_DIR,
            out_name=out_name,
            bg_volume=bg_volume,
            video_volume=video_volume,
        )
    except BgMusicError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

    # Assuming you have /video/<filename> serving from BASE_DIR
    web_path = f"/video/edit_vid_output/{out_path.name}"

    return jsonify({
        "ok": True,
        "output_file": str(out_path),
        "web_path": web_path,
        "bg_volume": bg_volume,
        "video_volume": video_volume,
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

@app.route('/background_videos/<path:filename>')
def serve_bg_video(filename):
    return send_from_directory(BASE_DIR / 'background_videos', filename)

@app.route('/quiz/downloads/<path:filename>')
def serve_quiz_downloads(filename):
    return send_from_directory(BASE_DIR / 'downloads', filename)

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
        from assemble_from_videos import assemble_videos
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
        from assemble_from_videos import assemble_videos
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

        from assemble_from_videos import assemble_videos
        assemble_videos(
            video_folder="edit_vid_input",                  # or "edit_vid_output" if you pre-made KB clips
            audio_folder="edit_vid_audio",
            output_path="edit_vid_output/final_video.mp4",
            fps=30,
            shuffle=True,                                   # different order each run
            prefer_ffmpeg_concat=True,                       # auto-uses concat if safe; else MoviePy
            keep_video_audio = keep_video_audio == 'yes',
            video_volume = video_volume,
            bg_volume = bg_volume
        )
        if copyforcaption == 'no':
            return "✅ Video song assembled successfully!", 200
        
        shutil.copy("edit_vid_output/final_video.mp4", "composed_video.mp4")

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
