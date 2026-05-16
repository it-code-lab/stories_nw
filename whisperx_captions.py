import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple


DEFAULT_MODEL = "large-v3"
DEFAULT_COMPUTE_TYPE = "int8"
DEFAULT_VAD_METHOD = "silero"

CAPTION_STYLES = {
    "premium-gold": {
        "label": "Premium Gold",
        "base_color": "&H00FAFAFA",
        "hi_color": "&H0000D5FF",
        "outline_color": "&H00000000",
        "shadow_color": "&H60000000",
        "font": "Montserrat Black",
        "outline": 2.5,
        "shadow": 2.0,
        "spacing": 1.0,
    },
    "clean-cyan": {
        "label": "Clean Cyan",
        "base_color": "&H00FFFFFF",
        "hi_color": "&H00FFD45A",
        "outline_color": "&H0020150A",
        "shadow_color": "&H70000000",
        "font": "Montserrat SemiBold",
        "outline": 2.0,
        "shadow": 1.5,
        "spacing": 0.5,
    },
    "neon-pop": {
        "label": "Neon Pop",
        "base_color": "&H00FFFFFF",
        "hi_color": "&H0000F5FF",
        "outline_color": "&H004B0054",
        "shadow_color": "&H90000000",
        "font": "Montserrat Black",
        "outline": 3.0,
        "shadow": 0.5,
        "spacing": 1.4,
    },
    "ruby-bold": {
        "label": "Ruby Bold",
        "base_color": "&H00FFFFFF",
        "hi_color": "&H005C4CFF",
        "outline_color": "&H00140416",
        "shadow_color": "&H78000000",
        "font": "Montserrat Black",
        "outline": 2.7,
        "shadow": 1.4,
        "spacing": 0.8,
    },
    "editorial-white": {
        "label": "Editorial White",
        "base_color": "&H00F7F4EF",
        "hi_color": "&H00B5FF6A",
        "outline_color": "&H00302A22",
        "shadow_color": "&H90000000",
        "font": "Arial",
        "outline": 1.5,
        "shadow": 1.8,
        "spacing": 0.2,
    },
}

WORDS_PER_PHRASE_PORTRAIT = 3
WORDS_PER_PHRASE_LANDSCAPE = 5

# If there's a long silence between words, start a new phrase
MAX_GAP = 0.55

# Layout / wrapping (character-based; avoids font-metric issues)
MAX_CHARS_PER_LINE_PORTRAIT = 26
MAX_CHARS_PER_LINE_LANDSCAPE = 38

# Positioning
BOTTOM_MARGIN_PORTRAIT = 150
BOTTOM_MARGIN_LANDSCAPE = 80

# Font sizing (dynamic based on video height)
def auto_font_size(video_w: int, video_h: int) -> int:
    portrait = video_h >= video_w
    if portrait:
        # tuned for readability without looking huge in fullscreen
        return int(max(40, min(56, round(video_h * 0.045))))
    else:
        return int(max(30, min(46, round(video_h * 0.070))))


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def resolve_font_size(video_w: int, video_h: int, font_size: Optional[int] = None,
                      font_scale: float = 100.0) -> int:
    if font_size:
        return clamp_int(int(font_size), 18, 140)
    scale = max(50.0, min(180.0, float(font_scale))) / 100.0
    return clamp_int(round(auto_font_size(video_w, video_h) * scale), 18, 140)


def resolve_alignment(position: str) -> int:
    return {
        "top": 8,
        "middle": 5,
        "bottom": 2,
    }.get(position, 2)


def resolve_margin_v(video_w: int, video_h: int, position: str, margin_v: Optional[int] = None) -> int:
    if margin_v is not None:
        return clamp_int(int(margin_v), 0, 500)
    portrait = video_h >= video_w
    if position == "top":
        return 120 if portrait else 70
    if position == "middle":
        return 0
    return BOTTOM_MARGIN_PORTRAIT if portrait else BOTTOM_MARGIN_LANDSCAPE


def transform_caption_text(text: str, text_case: str) -> str:
    if text_case == "uppercase":
        return text.upper()
    if text_case == "title":
        return text.title()
    return text


def resolve_caption_box(caption_box: str) -> dict:
    boxes = {
        "none": {
            "border_style": 1,
            "outline_extra": 0.0,
            "back_color": None,
        },
        "soft": {
            "border_style": 3,
            "outline_extra": 8.0,
            "back_color": "&H90000000",
        },
        "glass": {
            "border_style": 3,
            "outline_extra": 10.0,
            "back_color": "&H801A1610",
        },
        "solid": {
            "border_style": 3,
            "outline_extra": 9.0,
            "back_color": "&H30000000",
        },
    }
    return boxes.get(caption_box, boxes["none"])


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
    # lines are lists of Word, for optional wrapping
    lines: List[List[Word]]


def which_or_die(bin_name: str):
    if shutil.which(bin_name) is None:
        raise RuntimeError(f"'{bin_name}' not found in PATH. Install it and ensure it works in this terminal.")


def run(cmd: List[str], check=True):
    return subprocess.run(cmd, check=check)

def pick_font_for_language(lang: str) -> str:
    if lang and lang.lower().startswith("hi"):
        return "Noto Sans Devanagari"
    return "Arial"

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
    # escape ASS special chars
    return s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


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
    # simple char-based wrapping into up to 2 lines
    text = " ".join(w.text for w in words)
    if len(text) <= max_chars:
        return [words]
    mid = max(1, len(words) // 2)
    return [words[:mid], words[mid:]]


def break_into_phrases(words: List[Word], video_w: int, video_h: int,
                       words_per_phrase: Optional[int] = None) -> List[Phrase]:
    n = clamp_int(int(words_per_phrase), 1, 12) if words_per_phrase else choose_words_per_phrase(video_w, video_h)
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
def build_ass(phrases: List[Phrase], video_w: int, video_h: int, language="en") -> str:
    portrait = (video_h >= video_w)
    font_size = auto_font_size(video_w, video_h)
    
    # Modern sans-serif stack - bold weights look much more premium
    font_name = "Montserrat Black" if not language.startswith("hi") else "Noto Sans Devanagari"
    bottom_margin = BOTTOM_MARGIN_PORTRAIT if portrait else BOTTOM_MARGIN_LANDSCAPE

    # BGR Color Constants (ASS uses AABBGGRR format)
    BASE_COLOR = "&H00FAFAFA"     # Crisp Off-White (makes the highlight pop more)
    HI_COLOR = "&H0000D5FF"       # Premium Golden Yellow (#FFD500)
    OUTLINE_COLOR = "&H00000000"  # Pure Black
    SHADOW_COLOR = "&H60000000"   # Semi-transparent black for a softer, modern shadow
    
    # Thickness settings for a modern creator aesthetic
    BORDER_THICKNESS = 2.5 
    SHADOW_DEPTH = 2.0  

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,{font_name},{font_size},{BASE_COLOR},{BASE_COLOR},{OUTLINE_COLOR},{SHADOW_COLOR},1,0,0,0,100,100,1.0,0,1,{BORDER_THICKNESS},{SHADOW_DEPTH},2,80,80,{bottom_margin},1
Style: Hi,{font_name},{font_size},{HI_COLOR},{HI_COLOR},{OUTLINE_COLOR},{SHADOW_COLOR},1,0,0,0,100,100,1.0,0,1,{BORDER_THICKNESS},{SHADOW_DEPTH},2,80,80,{bottom_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def join_line(words: List[Word]) -> str:
        return " ".join(ass_escape(w.text) for w in words)

    def base_text_for_phrase(lines: List[List[Word]]) -> str:
        return "\\N".join(join_line(lw) for lw in lines)

    def overlay_text_for_phrase(lines: List[List[Word]], target: Word) -> str:
        out_lines = []
        for lw in lines:
            parts = []
            for i, w in enumerate(lw):
                spacer = " " if i > 0 else ""
                if w is target:
                    # Removed the \fscx and \fscy tags to prevent alignment shifting.
                    # The \alpha&H00& makes it opaque, \alpha&HFF& resets to transparent.
                    parts.append(
                        f"{spacer}{{\\alpha&H00&}}{ass_escape(w.text)}{{\\alpha&HFF&}}"
                    )
                else:
                    parts.append(f"{spacer}{{\\alpha&HFF&}}{ass_escape(w.text)}")
            out_lines.append("".join(parts))
        return "\\N".join(out_lines)

    events: List[str] = []

    for ph in phrases:
        # Layer 0: The full phrase (Off-White)
        base_txt = base_text_for_phrase(ph.lines)
        events.append(f"Dialogue: 0,{ass_time(ph.start)},{ass_time(ph.end)},Base,,0,0,0,,{base_txt}")

        # Layer 1: The active word highlight (Golden Yellow)
        for w in ph.words:
            txt = overlay_text_for_phrase(ph.lines, w)
            events.append(f"Dialogue: 1,{ass_time(w.start)},{ass_time(w.end)},Hi,,0,0,0,,{txt}")

    return header + "\n".join(events) + "\n"

def build_ass_apr12_2026(phrases: List[Phrase], video_w: int, video_h: int, language="en") -> str:
    portrait = (video_h >= video_w)
    font_size = auto_font_size(video_w, video_h)
    
    # Modern sans-serif stack
    font_name = "Montserrat" if not language.startswith("hi") else "Noto Sans Devanagari"
    bottom_margin = BOTTOM_MARGIN_PORTRAIT if portrait else BOTTOM_MARGIN_LANDSCAPE

    # BGR Color Constants
    BASE_COLOR = "&H00FFFFFF"     # Pure White
    HI_COLOR = "&H0000FFFF"       # Neon Yellow (High Contrast)
    OUTLINE_COLOR = "&H00000000"  # Pure Black
    
    # Thickness settings for max visibility
    BORDER_THICKNESS = 3.0 
    SHADOW_DEPTH = 0  # High-end modern style usually drops the shadow if the border is thick

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,{font_name},{font_size},{BASE_COLOR},{BASE_COLOR},{OUTLINE_COLOR},&H00000000,1,0,0,0,100,100,1.5,0,1,{BORDER_THICKNESS},{SHADOW_DEPTH},2,80,80,{bottom_margin},1
Style: Hi,{font_name},{font_size},{HI_COLOR},{HI_COLOR},{OUTLINE_COLOR},&H00000000,1,0,0,0,100,100,1.5,0,1,{BORDER_THICKNESS},{SHADOW_DEPTH},2,80,80,{bottom_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def join_line(words: List[Word]) -> str:
        return " ".join(ass_escape(w.text) for w in words)

    def base_text_for_phrase(lines: List[List[Word]]) -> str:
        return "\\N".join(join_line(lw) for lw in lines)

    def overlay_text_for_phrase(lines: List[List[Word]], target: Word) -> str:
        out_lines = []
        for lw in lines:
            parts = []
            for i, w in enumerate(lw):
                spacer = " " if i > 0 else ""
                if w is target:
                    # Highlight active word with color and a slight scale "pop"
                    parts.append(
                        f"{spacer}{{\\alpha&H00&\\c{HI_COLOR}\\fscx106\\fscy106}}{ass_escape(w.text)}{{\\fscx100\\fscy100\\alpha&HFF&}}"
                    )
                else:
                    parts.append(f"{spacer}{{\\alpha&HFF&}}{ass_escape(w.text)}")
            out_lines.append("".join(parts))
        return "\\N".join(out_lines)

    events: List[str] = []

    for ph in phrases:
        # Layer 0: The full phrase (Static White with Black Border)
        base_txt = base_text_for_phrase(ph.lines)
        events.append(f"Dialogue: 0,{ass_time(ph.start)},{ass_time(ph.end)},Base,,0,0,0,,{base_txt}")

        # Layer 1: The active word highlight (Neon Yellow with Black Border)
        for w in ph.words:
            txt = overlay_text_for_phrase(ph.lines, w)
            events.append(f"Dialogue: 1,{ass_time(w.start)},{ass_time(w.end)},Hi,,0,0,0,,{txt}")

    return header + "\n".join(events) + "\n"


def build_ass_wrk(phrases: List[Phrase], video_w: int, video_h: int, language="en") -> str:
    portrait = (video_h >= video_w)
    font_size = auto_font_size(video_w, video_h)
    font_name = pick_font_for_language(language)
    bottom_margin = BOTTOM_MARGIN_PORTRAIT if portrait else BOTTOM_MARGIN_LANDSCAPE

    # Netflix-ish: thin outline + soft shadow; highlight is yellow
    base_outline = 2
    base_shadow = 1

    # ASS colors are BGR (not RGB)
    # white = &H00FFFFFF
    # yellow = &H0000FFFF  (B=00, G=FF, R=FF)
    BASE_COLOR = "&H00FFFFFF"
    OUTLINE_COLOR = "&H00000000"
    HI_COLOR = "&H0000FFFF"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,{font_name},{font_size},{BASE_COLOR},{BASE_COLOR},{OUTLINE_COLOR},&H64000000,1,0,0,0,100,100,0,0,1,{base_outline},{base_shadow},2,80,80,{bottom_margin},1
Style: Hi,{font_name},{font_size},{HI_COLOR},{HI_COLOR},{OUTLINE_COLOR},&H00000000,1,0,0,0,100,100,0,0,1,{base_outline},{base_shadow},2,80,80,{bottom_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def join_line(words: List[Word]) -> str:
        return " ".join(ass_escape(w.text) for w in words)

    def base_text_for_phrase(lines: List[List[Word]]) -> str:
        return "\\N".join(join_line(lw) for lw in lines)

    def overlay_text_for_phrase(lines: List[List[Word]], target: Word) -> str:
        """
        Build a full phrase where all text is transparent except the target word,
        which is yellow. This avoids any shifting because libass renders the whole
        line layout consistently.
        """
        out_lines = []
        for lw in lines:
            parts = []
            for i, w in enumerate(lw):
                spacer = " " if i > 0 else ""
                if w is target:
                    # visible + yellow
                    parts.append(
                        f"{spacer}{{\\alpha&H00&\\c{HI_COLOR}}}{ass_escape(w.text)}{{\\alpha&HFF&}}"
                    )
                else:
                    # invisible
                    parts.append(f"{spacer}{{\\alpha&HFF&}}{ass_escape(w.text)}")
            out_lines.append("".join(parts))
        return "\\N".join(out_lines)

    events: List[str] = []

    for ph in phrases:
        # 1) Base line (white) for whole phrase duration
        base_txt = base_text_for_phrase(ph.lines)
        events.append(f"Dialogue: 0,{ass_time(ph.start)},{ass_time(ph.end)},Base,,0,0,0,,{base_txt}")

        # 2) Overlay: only the spoken word is visible and yellow during its time
        for w in ph.words:
            txt = overlay_text_for_phrase(ph.lines, w)
            events.append(f"Dialogue: 1,{ass_time(w.start)},{ass_time(w.end)},Hi,,0,0,0,,{txt}")

    return header + "\n".join(events) + "\n"


def build_ass_from_style(phrases: List[Phrase], video_w: int, video_h: int, language="en",
                         style: str = "premium-gold", font_size: Optional[int] = None,
                         font_scale: float = 100.0, position: str = "bottom",
                         margin_v: Optional[int] = None, word_transition: str = "none",
                         text_case: str = "original", caption_box: str = "none",
                         outline_scale: float = 100.0, shadow_scale: float = 100.0) -> str:
    preset = CAPTION_STYLES.get(style, CAPTION_STYLES["premium-gold"])
    resolved_font_size = resolve_font_size(video_w, video_h, font_size, font_scale)
    font_name = "Noto Sans Devanagari" if language and language.lower().startswith("hi") else preset["font"]
    alignment = resolve_alignment(position)
    resolved_margin_v = resolve_margin_v(video_w, video_h, position, margin_v)
    box = resolve_caption_box(caption_box)
    outline = round(float(preset["outline"]) * max(50.0, min(220.0, outline_scale)) / 100.0, 2)
    shadow = round(float(preset["shadow"]) * max(0.0, min(220.0, shadow_scale)) / 100.0, 2)
    base_border_style = box["border_style"]
    base_outline = round(outline + box["outline_extra"], 2)
    base_back_color = box["back_color"] or preset["shadow_color"]

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,{font_name},{resolved_font_size},{preset["base_color"]},{preset["base_color"]},{preset["outline_color"]},{base_back_color},1,0,0,0,100,100,{preset["spacing"]},0,{base_border_style},{base_outline},{shadow},{alignment},80,80,{resolved_margin_v},1
Style: Hi,{font_name},{resolved_font_size},{preset["hi_color"]},{preset["hi_color"]},{preset["outline_color"]},{preset["shadow_color"]},1,0,0,0,100,100,{preset["spacing"]},0,1,{outline},{shadow},{alignment},80,80,{resolved_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def join_line(words: List[Word]) -> str:
        return " ".join(ass_escape(transform_caption_text(w.text, text_case)) for w in words)

    def base_text_for_phrase(lines: List[List[Word]]) -> str:
        return "\\N".join(join_line(lw) for lw in lines)

    def overlay_text_for_phrase(lines: List[List[Word]], target: Word) -> str:
        out_lines = []
        for lw in lines:
            parts = []
            for i, w in enumerate(lw):
                spacer = " " if i > 0 else ""
                if w is target:
                    escaped = ass_escape(transform_caption_text(w.text, text_case))
                    if word_transition == "fade":
                        parts.append(f"{spacer}{{\\fad(80,80)\\alpha&H00&}}{escaped}{{\\alpha&HFF&}}")
                    elif word_transition == "pop":
                        parts.append(
                            f"{spacer}{{\\alpha&H00&\\fscx112\\fscy112\\t(0,140,\\fscx100\\fscy100)}}"
                            f"{escaped}{{\\fscx100\\fscy100\\alpha&HFF&}}"
                        )
                    elif word_transition == "glow":
                        parts.append(
                            f"{spacer}{{\\alpha&H00&\\blur1.2\\bord4\\t(0,140,\\bord{outline})}}"
                            f"{escaped}{{\\blur0\\bord{outline}\\alpha&HFF&}}"
                        )
                    else:
                        parts.append(f"{spacer}{{\\alpha&H00&}}{escaped}{{\\alpha&HFF&}}")
                else:
                    parts.append(f"{spacer}{{\\alpha&HFF&}}{ass_escape(transform_caption_text(w.text, text_case))}")
            out_lines.append("".join(parts))
        return "\\N".join(out_lines)

    events: List[str] = []
    for ph in phrases:
        base_txt = base_text_for_phrase(ph.lines)
        events.append(f"Dialogue: 0,{ass_time(ph.start)},{ass_time(ph.end)},Base,,0,0,0,,{base_txt}")
        for w in ph.words:
            txt = overlay_text_for_phrase(ph.lines, w)
            events.append(f"Dialogue: 1,{ass_time(w.start)},{ass_time(w.end)},Hi,,0,0,0,,{txt}")

    return header + "\n".join(events) + "\n"


def ffmpeg_filter_escape_path(p: str) -> str:
    r"""
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

    # Use subtitles filter (libass) - most stable on Windows
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
    ap = argparse.ArgumentParser(description="Video -> WhisperX JSON -> Netflix-style word highlight ASS -> Burn-in")
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workdir", default="caption_work")
    ap.add_argument("--language", default="en")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--compute_type", default=DEFAULT_COMPUTE_TYPE)
    ap.add_argument("--vad_method", default=DEFAULT_VAD_METHOD)
    ap.add_argument("--device", default=None)
    ap.add_argument("--style", default="premium-gold", choices=sorted(CAPTION_STYLES.keys()))
    ap.add_argument("--font_size", type=int, default=None, help="Exact ASS font size. Overrides --font_scale.")
    ap.add_argument("--font_scale", type=float, default=100.0, help="Percentage scale applied to orientation-aware auto font size.")
    ap.add_argument("--position", default="bottom", choices=["top", "middle", "bottom"])
    ap.add_argument("--margin_v", type=int, default=None, help="Vertical margin in pixels for top/bottom caption positions.")
    ap.add_argument("--words_per_phrase", type=int, default=None, help="Words shown at a time. Default is orientation-aware.")
    ap.add_argument("--word_transition", default="none", choices=["none", "fade", "pop", "glow"])
    ap.add_argument("--text_case", default="original", choices=["original", "uppercase", "title"])
    ap.add_argument("--caption_box", default="none", choices=["none", "soft", "glass", "solid"])
    ap.add_argument("--outline_scale", type=float, default=100.0)
    ap.add_argument("--shadow_scale", type=float, default=100.0)
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
    phrases = break_into_phrases(words, vw, vh, args.words_per_phrase)

    ass_text = build_ass_from_style(
        phrases,
        vw,
        vh,
        args.language,
        args.style,
        font_size=args.font_size,
        font_scale=args.font_scale,
        position=args.position,
        margin_v=args.margin_v,
        word_transition=args.word_transition,
        text_case=args.text_case,
        caption_box=args.caption_box,
        outline_scale=args.outline_scale,
        shadow_scale=args.shadow_scale,
    )

    ass_path = os.path.join(args.workdir, "captions.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_text)

    burn_ass_into_video(args.video, ass_path, out_video)

    print("\n✅ Done!")
    print(f"Output video: {out_video}")
    print(f"ASS file:     {ass_path}")
    print(f"JSON file:    {json_path}")
    print(f"Style:        {CAPTION_STYLES[args.style]['label']}")
    print(f"Position:     {args.position}")
    print(f"Transition:   {args.word_transition}")
    print(f"Text case:    {args.text_case}")
    print(f"Caption box:  {args.caption_box}")

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
# 
# venv_whisperx\Scripts\activate
# 
# English
# python whisperx_captions.py --video input.mp4 --language en

# Hindi - *****DOES NOT WORK WELL****
# python whisperx_captions.py --video input.mp4 --language hi

# Auto Language Detect - Takes more time and processing
# python whisperx_captions.py --video input.mp4

