# --- imports (top of file) ---
import os, json, re, subprocess, math
from flask import request, jsonify
import shlex

# ---------- helpers ----------
def _escape_ass_text(s: str) -> str:
    # Escape { }, and backslashes inside ASS text
    return s.replace('\\', r'\\').replace('{', r'\{').replace('}', r'\}')

def _segments_from_words(words, min_gap_sec=0.40, words_per_caption=5):
    """
    Split into caption segments by time gap (>= min_gap_sec),
    then (optionally) limit very long runs to chunks of N words.
    """
    if not words:
        return []

    # First cut: gaps in audio
    segs = []
    seg_start = 0
    for i in range(len(words) - 1):
        gap = words[i+1]['start'] - words[i]['end']
        if gap >= min_gap_sec:
            segs.append((seg_start, i))
            seg_start = i + 1
    segs.append((seg_start, len(words)-1))

    # Second cut: cap words per caption (if needed)
    final = []
    for a, b in segs:
        span = b - a + 1
        if span <= words_per_caption:
            final.append((a, b))
        else:
            i = a
            while i <= b:
                j = min(i + words_per_caption - 1, b)
                final.append((i, j))
                i = j + 1
    return final

def _build_ass_header(orientation='landscape'):
    is_portrait = (orientation == 'portrait')
    PlayResX = 1080 if is_portrait else 1920
    PlayResY = 1920 if is_portrait else 1080
    WrapStyle = 0  # smart auto-wrap
    # Modern, readable
    font = 'Noto Sans Devanagari'  # you can switch to Poppins for English
    fontsize = 58 if is_portrait else 72
    scaleX = 95 if is_portrait else 100
    outlinePx = 3
    shadowPx  = 4
    pri  = '&H00FFFFFF'
    sec  = '&H000000FF'
    outc = '&HAA000000'
    back = '&H64000000'
    alignVal = 2
    mL = 60 if is_portrait else 80
    mR = 60 if is_portrait else 80
    mV = 110 if is_portrait else 90
    header = f"""[Script Info]
Title: Word-level Captions ({'Portrait' if is_portrait else 'Landscape'})
ScriptType: v4.00+
PlayResX: {PlayResX}
PlayResY: {PlayResY}
WrapStyle: {WrapStyle}
ScaledBorderAndShadow: yes

[V4+ Styles]
; Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KStyle,{font},{fontsize},{pri},{sec},{outc},{back},1,0,0,0,{scaleX},100,0,0,1,{outlinePx},{shadowPx},{alignVal},{mL},{mR},{mV},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header, PlayResX, PlayResY, mV

def _to_ass_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - math.floor(sec)) * 100))
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def _anim_tag(style, PlayResX, PlayResY, mV, orientation):
    # Shared coords
    xCenter = PlayResX // 2
    yRest   = PlayResY - mV
    yStart  = yRest + (100 if orientation == 'portrait' else 120)
    zoomDur = 3000

    if style == 'cinematic':
        return f"{{\\an2\\move({xCenter},{yStart},{xCenter},{yRest})\\t(0,{zoomDur},\\fscx105\\fscy105)\\fad(200,150)}}"
    if style == 'pro_pop':
        return "{\\an2\\fscx85\\fscy85\\t(0,250,\\fscx100\\fscy100)\\fad(250,150)}"
    if style == 'drift_up':
        return f"{{\\an2\\move({xCenter},{yRest+10},{xCenter},{yRest},0,300)\\fad(250,150)}}"
    if style == 'typewriter':
        # We still add a small fade. Per-word \kf goes on the words.
        return "{\\an2\\fad(100,120)}"
    # Fallback: soft fade
    return "{\\an2\\fad(200,150)}"

def _build_karaoke_line(words, style, header_meta):
    """
    Build one Dialogue line (ASS) covering words[0]..words[-1] using \kf per-word highlighting.
    """
    start = words[0]['start']
    end   = words[-1]['end']
    dur_total_ms = max(1, int(round((end - start) * 1000)))

    # Karaoke in centiseconds per word
    chunks = []
    for w in words:
        w_ms = max(1, int(round((w['end'] - w['start']) * 1000)))
        w_cs = max(1, w_ms // 10)  # \kf uses centiseconds
        text = _escape_ass_text(w['word'])
        # Add a trailing space (outside highlight) so it feels natural
        chunks.append(f"{{\\kf{w_cs}}}{text} ")

    # Animation pre-tag
    anim = _anim_tag(style, header_meta['PlayResX'], header_meta['PlayResY'], header_meta['mV'], header_meta['orientation'])

    # Compose Dialogue
    return f"Dialogue: 0,{_to_ass_time(start)},{_to_ass_time(end)},KStyle,,0,0,0,,{anim}{''.join(chunks).rstrip()}\n"

def build_ass_from_word_json(
    word_json_path: str,
    orientation: str = 'landscape',
    style: str = 'cinematic',
    min_gap_sec: float = 0.40,
    words_per_caption: int = 5
) -> str:
    with open(word_json_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    words = [w for w in words if 'start' in w and 'end' in w and 'word' in w]
    header, PlayResX, PlayResY, mV = _build_ass_header(orientation)
    header_meta = dict(PlayResX=PlayResX, PlayResY=PlayResY, mV=mV, orientation=orientation)

    segs = _segments_from_words(words, min_gap_sec=min_gap_sec, words_per_caption=words_per_caption)

    lines = []
    for a, b in segs:
        part = words[a:b+1]
        lines.append(_build_karaoke_line(part, style, header_meta))

    return header + ''.join(lines)

def _ffmpeg_burn_subs(input_video: str, ass_path: str, output_path: str):
    """
    Burn ASS subtitles into the video using ffmpeg.
    Works on Windows and Unix-like systems.
    """

    # Convert backslashes to forward slashes for FFmpeg
    ass_path_fixed = ass_path.replace("\\", "/")

    # Quote the path safely for ffmpeg on Windows (important if path has spaces)
    quoted_ass_path = f"subtitles={shlex.quote(ass_path_fixed)}"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", quoted_ass_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy",
        output_path
    ]

    # Run FFmpeg and capture logs
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print("❌ FFmpeg failed:\n", result.stderr)
    else:
        print("✅ Subtitles burned successfully.")

    return result