import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import ImageFont


DEFAULT_MODEL = "large-v3"
DEFAULT_COMPUTE_TYPE = "int8"
DEFAULT_VAD_METHOD = "silero"

WORDS_PER_PHRASE_PORTRAIT = 3
WORDS_PER_PHRASE_LANDSCAPE = 5
MAX_GAP = 0.55

FONT_SIZE_PORTRAIT = 62
FONT_SIZE_LANDSCAPE = 52
BOTTOM_MARGIN_PORTRAIT = 150
BOTTOM_MARGIN_LANDSCAPE = 80
LINE_GAP = 14

BOX_PAD_X = 18
BOX_PAD_Y = 10
BOX_RADIUS = 12

MAX_CHARS_PER_LINE_PORTRAIT = 26
MAX_CHARS_PER_LINE_LANDSCAPE = 38

FONT_PATHS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Phrase:
    words: List[Word]
    start: float
    end: float
    lines: List[List[Word]]


def which_or_die(bin_name: str):
    if shutil.which(bin_name) is None:
        raise RuntimeError(f"'{bin_name}' not found in PATH. Install it and ensure it works in this terminal.")


def run(cmd: List[str], check=True):
    return subprocess.run(cmd, check=check)


def ffprobe_resolution(video_path: str) -> Tuple[int, int]:
    which_or_die("ffprobe")
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        video_path
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(p.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RuntimeError("Could not detect video resolution (no video stream found).")
    return int(streams[0]["width"]), int(streams[0]["height"])


def extract_audio_wav(video_path: str, wav_path: str):
    which_or_die("ffmpeg")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        wav_path
    ]
    run(cmd)


def ass_time(t: float) -> str:
    if t < 0:
        t = 0
    cs = int(round(t * 100))
    s = cs // 100
    cc = cs % 100
    hh = s // 3600
    mm = (s % 3600) // 60
    ss = s % 60
    return f"{hh}:{mm:02d}:{ss:02d}.{cc:02d}"


def clean_word(w: str) -> str:
    return re.sub(r"\s+", " ", w).strip()


def ass_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def pick_font(font_size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, font_size)
    raise FileNotFoundError("No font found. Set FONT_PATHS to a valid .ttf path on your system.")


def text_width(font: ImageFont.FreeTypeFont, s: str) -> int:
    bbox = font.getbbox(s)
    return bbox[2] - bbox[0]


def rect_path(w: int, h: int, r: int) -> str:
    r = max(0, min(r, min(w, h)//2))
    if r == 0:
        return f"m 0 0 l {w} 0 l {w} {h} l 0 {h} l 0 0"
    return (
        f"m {r} 0 "
        f"l {w-r} 0 "
        f"b {w-r//2} 0 {w} {r//2} {w} {r} "
        f"l {w} {h-r} "
        f"b {w} {h-r//2} {w-r//2} {h} {w-r} {h} "
        f"l {r} {h} "
        f"b {r//2} {h} 0 {h-r//2} 0 {h-r} "
        f"l 0 {r} "
        f"b 0 {r//2} {r//2} 0 {r} 0"
    )


def newest_json(out_dir: str) -> str:
    files = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.lower().endswith(".json")]
    if not files:
        raise RuntimeError("No JSON produced by WhisperX.")
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]


def run_whisperx(wav_path: str, out_dir: str, model: str, compute_type: str, vad_method: str,
                language: Optional[str] = None, device: Optional[str] = None) -> str:
    which_or_die("whisperx")
    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        "whisperx", wav_path,
        "--model", model,
        "--compute_type", compute_type,
        "--vad_method", vad_method,
        "--output_format", "json",
        "--output_dir", out_dir,
    ]
    if language:
        cmd += ["--language", language]
    if device:
        cmd += ["--device", device]

    run(cmd)
    return newest_json(out_dir)


def flatten_words_from_whisperx(aligned_json: dict) -> List[Word]:
    words: List[Word] = []
    for seg in aligned_json.get("segments", []):
        for wd in seg.get("words", []):
            txt = wd.get("word") or wd.get("text") or ""
            st = wd.get("start")
            en = wd.get("end")
            if txt and st is not None and en is not None and float(en) > float(st):
                words.append(Word(clean_word(txt), float(st), float(en)))

    if not words:
        raise ValueError("No word timestamps found in JSON (segments[].words[] missing).")
    return words


def choose_words_per_phrase(video_w: int, video_h: int) -> int:
    return WORDS_PER_PHRASE_PORTRAIT if video_h >= video_w else WORDS_PER_PHRASE_LANDSCAPE


def max_chars_per_line(video_w: int, video_h: int) -> int:
    return MAX_CHARS_PER_LINE_PORTRAIT if video_h >= video_w else MAX_CHARS_PER_LINE_LANDSCAPE


def wrap_phrase(words: List[Word], max_chars: int) -> List[List[Word]]:
    text = " ".join(w.text for w in words)
    if len(text) <= max_chars:
        return [words]
    mid = max(1, len(words) // 2)
    return [words[:mid], words[mid:]]


def break_into_phrases(words: List[Word], video_w: int, video_h: int) -> List[Phrase]:
    n = choose_words_per_phrase(video_w, video_h)
    max_chars = max_chars_per_line(video_w, video_h)

    phrases: List[Phrase] = []
    buf: List[Word] = []

    def flush():
        nonlocal buf
        if not buf:
            return
        phrases.append(Phrase(
            words=buf,
            start=buf[0].start,
            end=buf[-1].end,
            lines=wrap_phrase(buf, max_chars)
        ))
        buf = []

    for w in words:
        if buf and (w.start - buf[-1].end) > MAX_GAP:
            flush()
        buf.append(w)
        if len(buf) >= n:
            flush()
    flush()
    return phrases


def build_ass(phrases: List[Phrase], video_w: int, video_h: int) -> str:
    portrait = (video_h >= video_w)
    font_size = FONT_SIZE_PORTRAIT if portrait else FONT_SIZE_LANDSCAPE
    bottom_margin = BOTTOM_MARGIN_PORTRAIT if portrait else BOTTOM_MARGIN_LANDSCAPE
    font = pick_font(font_size)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,2,80,80,{bottom_margin},1
Style: Word,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,4,2,7,0,0,0,1
Style: Box,Arial,{font_size},&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def line_string(ws: List[Word]) -> str:
        return " ".join(w.text for w in ws)

    def compute_layout(phrase: Phrase):
        num_lines = len(phrase.lines)
        line_h = font_size + LINE_GAP
        total_h = num_lines * line_h - LINE_GAP
        y_bottom = video_h - bottom_margin
        y_start = y_bottom - total_h

        layouts = []
        for li, lw in enumerate(phrase.lines):
            s = line_string(lw)
            wpx = text_width(font, s)
            x0 = (video_w - wpx) // 2
            y_top = y_start + li * line_h
            layouts.append({"words": lw, "x0": x0, "y_top": y_top})
        return layouts

    events: List[str] = []

    for ph in phrases:
        layouts = compute_layout(ph)

        base_lines = [ass_escape(line_string(l["words"])) for l in layouts]
        base_text = "\\N".join(base_lines)
        events.append(f"Dialogue: 0,{ass_time(ph.start)},{ass_time(ph.end)},Base,,0,0,0,,{base_text}")

        for line in layouts:
            x_cursor = line["x0"]
            y_top = line["y_top"]

            for wi, wobj in enumerate(line["words"]):
                prefix = "" if wi == 0 else " "
                prefix_w = text_width(font, prefix)
                word_w = text_width(font, wobj.text)
                word_h = font_size

                x_word = x_cursor + prefix_w
                y_word = y_top
                x_cursor = x_word + word_w

                box_w = word_w + 2 * BOX_PAD_X
                box_h = word_h + 2 * BOX_PAD_Y
                box_x = x_word - BOX_PAD_X
                box_y = y_word - BOX_PAD_Y

                path = rect_path(box_w, box_h, BOX_RADIUS)

                box_text = f"{{\\an7\\pos({box_x},{box_y})\\p1\\1c&H0000FF&}}{path}{{\\p0}}"
                events.append(f"Dialogue: 1,{ass_time(wobj.start)},{ass_time(wobj.end)},Box,,0,0,0,,{box_text}")

                word_text = f"{{\\an7\\pos({x_word},{y_word})}}{ass_escape(wobj.text)}"
                events.append(f"Dialogue: 2,{ass_time(wobj.start)},{ass_time(wobj.end)},Word,,0,0,0,,{word_text}")

    return header + "\n".join(events) + "\n"


def ffmpeg_filter_escape_path(p: str) -> str:
    """
    Escapes a filesystem path for use inside FFmpeg -vf filter strings (Windows-safe).
    - use forward slashes
    - escape ':' as '\:'
    """
    p = os.path.abspath(p).replace("\\", "/")
    p = p.replace(":", r"\:")
    return p


def burn_ass_into_video(video_in: str, ass_path: str, video_out: str):
    which_or_die("ffmpeg")
    ass_esc = ffmpeg_filter_escape_path(ass_path)

    # Use subtitles filter (libass). This is more stable than ass=... on Windows parsing.
    vf = f"subtitles='{ass_esc}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_in,
        "-vf", vf,
        "-c:a", "copy",
        video_out
    ]
    run(cmd)


def main():
    ap = argparse.ArgumentParser(description="Video -> WhisperX JSON -> Word-highlight ASS -> Burned captions video")
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workdir", default="caption_work")
    ap.add_argument("--language", default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--compute_type", default=DEFAULT_COMPUTE_TYPE)
    ap.add_argument("--vad_method", default=DEFAULT_VAD_METHOD)
    ap.add_argument("--device", default=None)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        raise FileNotFoundError(f"Video not found: {args.video}")

    base, _ = os.path.splitext(args.video)
    out_video = args.out or (base + "_captioned.mp4")

    os.makedirs(args.workdir, exist_ok=True)

    vw, vh = ffprobe_resolution(args.video)

    wav_path = os.path.join(args.workdir, "audio_16k_mono.wav")
    extract_audio_wav(args.video, wav_path)

    whisper_out = os.path.join(args.workdir, "whisperx_out")
    json_path = run_whisperx(
        wav_path=wav_path,
        out_dir=whisper_out,
        model=args.model,
        compute_type=args.compute_type,
        vad_method=args.vad_method,
        language=args.language,
        device=args.device,
    )

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    words = flatten_words_from_whisperx(data)
    phrases = break_into_phrases(words, vw, vh)
    ass_text = build_ass(phrases, vw, vh)

    ass_path = os.path.join(args.workdir, "captions.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_text)

    burn_ass_into_video(args.video, ass_path, out_video)

    print("\n✅ Done!")
    print(f"Output video: {out_video}")
    print(f"ASS file:     {ass_path}")
    print(f"JSON file:    {json_path}")

    if not args.keep:
        try:
            os.remove(wav_path)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print("\n❌ Command failed:", e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("\n❌ Error:", e, file=sys.stderr)
        sys.exit(1)



# Running the script
# English
# python whisperx_captions_2.py --video input.mp4 --language en
# Hindi
# python whisperx_captions_2.py --video input.mp4 --language hi

# Auto Language Detect - Takes more time and processing
# python whisperx_captions_2.py --video input.mp4

