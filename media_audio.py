# media_audio.py
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ExtractResult:
    ok: bool
    input_name: str | None = None
    output_path: Path | None = None
    copy_path: Path | None = None
    fmt: str | None = None
    track: int | None = None
    duration_sec: float | None = None
    error: str | None = None
    detail: str | None = None

SUPPORTED_FORMATS = {"wav", "mp3", "m4a"}

def safe_join(base_dir: Path, urlish_path: str) -> Path:
    """
    Map a URL-like path (e.g. '/edit_vid_input/bg_video.mp4') to a filesystem path
    under base_dir, preventing path traversal.
    """
    p = (base_dir / urlish_path.lstrip("/")).resolve()
    if not str(p).startswith(str(base_dir.resolve())):
        raise ValueError("Invalid path (outside project).")
    return p

def ffprobe_duration(path: Path) -> float | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
        return round(float(out), 2)
    except Exception:
        return None

def _ffmpeg_cmd(in_path: Path, out_path: Path, fmt: str, track: int) -> list[str]:
    map_opt = f"a:{track}"
    if fmt == "wav":
        return ["ffmpeg", "-y", "-i", str(in_path), "-map", map_opt, "-vn", "-ac", "2", "-ar", "44100", str(out_path)]
    if fmt == "mp3":
        return ["ffmpeg", "-y", "-i", str(in_path), "-map", map_opt, "-vn", "-ac", "2", "-ar", "44100",
                "-c:a", "libmp3lame", "-b:a", "192k", str(out_path)]
    # m4a / AAC
    return ["ffmpeg", "-y", "-i", str(in_path), "-map", map_opt, "-vn", "-ac", "2", "-ar", "44100",
            "-c:a", "aac", "-b:a", "192k", str(out_path)]

def extract_audio_from_video(
    *,
    base_dir: Path,
    input_path: Path,
    fmt: str = "wav",
    track: int = 0,
    root_output_name: str = "edit_vid_output",
    also_copy_to: Path | None = None,
) -> ExtractResult:
    """
    Core worker that extracts audio from a given video path.

    - base_dir: project root
    - input_path: absolute path to video
    - fmt: wav|mp3|m4a (default wav)
    - track: audio stream index (default 0)
    - root_output_name: base file name without extension written under base_dir
    - also_copy_to: optional directory where a second copy is stored
    """

    print("extract_audio_from_video arguments:", locals())

    try:
        fmt = (fmt or "wav").lower()
        if fmt not in SUPPORTED_FORMATS:
            fmt = "wav"
        if track is None:
            track = 0
        try:
            track = int(track)
        except Exception:
            track = 0

        out_path = base_dir / f"{root_output_name}.{ 'mp3' if fmt=='mp3' else ('m4a' if fmt=='m4a' else 'wav') }"
        cmd = _ffmpeg_cmd(input_path, out_path, fmt, track)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0 or not out_path.exists():
            return ExtractResult(
                ok=False,
                input_name=input_path.name,
                fmt=fmt,
                track=track,
                error="ffmpeg failed",
                detail=proc.stdout[-2000:],
            )

        # copy_path = None
        # if also_copy_to:
        #     also_copy_to.mkdir(parents=True, exist_ok=True)
        #     copy_path = also_copy_to / out_path.name
        #     try:
        #         shutil.copy(str(out_path), str(copy_path))
        #     except Exception:
        #         copy_path = None  # non-fatal

        dur = ffprobe_duration(out_path)

        return ExtractResult(
            ok=True,
            input_name=input_path.name,
            output_path=out_path,
            copy_path=None,
            fmt=fmt,
            track=track,
            duration_sec=dur,
        )
    except Exception as e:
        return ExtractResult(ok=False, error=str(e))

def resolve_input_video(
    *,
    base_dir: Path,
    uploaded_temp_dir: Path | None,
    uploaded_file,  # Werkzeug FileStorage or None
    urlish_path: str | None,
    fallback_rel: str = "edit_vid_input/bg_video.mp4",
) -> Path:
    """
    Decide the input video path from either an uploaded file, a URL-like project path,
    or fallback (if present). Returns an absolute Path.
    """
    # 1) Uploaded file
    if uploaded_file and getattr(uploaded_file, "filename", None):
        uploaded_temp_dir = uploaded_temp_dir or (base_dir / "tmp_upload_video")
        uploaded_temp_dir.mkdir(parents=True, exist_ok=True)
        dest = uploaded_temp_dir / uploaded_file.filename
        uploaded_file.save(str(dest))
        return dest.resolve()

    # 2) URL-like path from the project
    if urlish_path:
        p = safe_join(base_dir, urlish_path.strip())
        if not p.exists():
            raise FileNotFoundError(f"File not found: {urlish_path}")
        return p

    # 3) Fallback if present
    fb = (base_dir / fallback_rel).resolve()
    if fb.exists():
        return fb
    raise FileNotFoundError(
        f"No input provided. Upload a file, pass a valid 'video' path, or place {fallback_rel}."
    )
