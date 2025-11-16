# bg_music_video.py

import subprocess
import shutil
from pathlib import Path
from typing import Optional

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


class BgMusicError(Exception):
    pass


def _ensure_ffmpeg():
    """Raise if ffmpeg / ffprobe are not available."""
    if not shutil.which("ffmpeg"):
        raise BgMusicError("FFmpeg not found in PATH. Please install FFmpeg and add it to PATH.")
    if not shutil.which("ffprobe"):
        raise BgMusicError("ffprobe not found in PATH. Please install FFmpeg and add it to PATH.")


def _first_file(folder: Path, exts: set[str]) -> Optional[Path]:
    if not folder.exists():
        return None
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in exts:
            return p
    return None


def _has_audio_stream(path: Path) -> bool:
    """Return True if the video has at least one audio stream."""
    try:
        subprocess.check_call(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def merge_video_with_bg_music(
    base_dir: str | Path,
    out_name: str = "video_with_music.mp4",
    bg_volume: float = 0.3,
    video_volume: float = 1.0,
) -> Path:
    """
    Mix background music with the (optional) original audio of a video.

    - Picks the first video from edit_vid_input/
    - Picks the first audio file from edit_vid_audio/
    - Background audio is LOOPED and TRIMMED to the video length
      using -stream_loop and -shortest.
    - Volumes are linear multipliers (1.0 = unchanged, 0.5 ≈ -6 dB).

    Args:
        base_dir: Project root (where server.py lives). This folder
                  must contain edit_vid_input/ and edit_vid_audio/.
        out_name: Output filename under edit_vid_output/.
        bg_volume: Background music volume factor (0.0–2.0 typical).
        video_volume: Original video audio volume factor.

    Returns:
        Path to the output video file inside edit_vid_output/.

    Raises:
        BgMusicError on any error (missing files, ffmpeg failure, etc.).
    """
    _ensure_ffmpeg()

    base_dir = Path(base_dir).resolve()
    in_dir = base_dir / "edit_vid_input"
    aud_dir = base_dir / "edit_vid_audio"
    out_dir = base_dir / "edit_vid_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    video_path = _first_file(in_dir, VIDEO_EXTS)
    if not video_path:
        raise BgMusicError(f"No video files found in {in_dir}")

    music_path = _first_file(aud_dir, AUDIO_EXTS)
    if not music_path:
        raise BgMusicError(f"No audio files found in {aud_dir}")

    has_vid_audio = _has_audio_stream(video_path)
    out_path = out_dir / out_name

    # Build ffmpeg command
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-stream_loop",
        "-1",  # loop bg music
        "-i",
        str(music_path),
        "-map",
        "0:v:0",  # always take video from input 0
    ]

    filter_complex_parts = []

    if has_vid_audio:
        # Scale video audio and background music, then mix
        filter_complex_parts.append(f"[0:a]volume={video_volume}[v1]")
        filter_complex_parts.append(f"[1:a]volume={bg_volume}[m1]")
        filter_complex_parts.append("[v1][m1]amix=inputs=2:duration=first:dropout_transition=0[aout]")
        cmd += ["-map", "[aout]"]
    else:
        # Only background music, scaled; no original audio
        filter_complex_parts.append(f"[1:a]volume={bg_volume}[aout]")
        cmd += ["-map", "[aout]"]

    filter_complex = ";".join(filter_complex_parts)
    cmd += [
        "-filter_complex",
        filter_complex,
        "-c:v",
        "copy",       # keep original video stream
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",  # trim to video length
        "-movflags",
        "+faststart",
        str(out_path),
    ]

    try:
        print("Running ffmpeg:", " ".join(cmd))
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        raise BgMusicError(f"FFmpeg failed with code {e.returncode}") from e

    return out_path


if __name__ == "__main__":
    """
    Optional CLI usage, e.g.:

        python bg_music_video.py
        python bg_music_video.py /path/to/project
    """
    import sys

    base = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    try:
        out = merge_video_with_bg_music(base, out_name="video_with_music.mp4", bg_volume=0.3, video_volume=1.0)
        print("✅ Created:", out)
    except BgMusicError as e:
        print("❌ Error:", e)
        sys.exit(1)
