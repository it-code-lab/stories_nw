import re
import math
import whisperx
from pathlib import Path
from dataclasses import dataclass

# ----------------------------
# Settings you may tweak
# ----------------------------
MAX_LINE_CHARS = 42          # caption line length (characters)
MAX_LINE_DURATION = 2.8      # seconds per caption line
MIN_LINE_DURATION = 1.0      # seconds minimum
GAP_BREAK = 0.45             # break line if silence gap between words >= this
ASS_FONT = "Arial"
ASS_FONT_SIZE = 54

# Karaoke highlight is done via SecondaryColour in the style.
ASS_STYLE = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kara,{ASS_FONT},{ASS_FONT_SIZE},&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3.5,0.8,2,60,60,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

@dataclass
class Word:
    text: str
    start: float
    end: float

def ass_time(t: float) -> str:
    # H:MM:SS.cs
    if t < 0:
        t = 0
    cs = int(round((t - int(t)) * 100))
    s = int(t) % 60
    m = (int(t) // 60) % 60
    h = int(t) // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def tokenize_transcript(text: str) -> str:
    # WhisperX alignment is typically robust to punctuation; keep it, just normalize whitespace.
    return normalize_spaces(text)

def words_from_whisperx(aligned_result) -> list[Word]:
    out = []
    for seg in aligned_result.get("segments", []):
        for w in seg.get("words", []):
            if w.get("start") is None or w.get("end") is None:
                continue
            txt = w.get("word", "").strip()
            if not txt:
                continue
            out.append(Word(text=txt, start=float(w["start"]), end=float(w["end"])))
    return out

def chunk_words(words: list[Word]) -> list[list[Word]]:
    """
    Build caption lines from word timings using:
    - max chars
    - max duration
    - breaks on long gaps
    """
    chunks = []
    cur = []
    cur_chars = 0
    line_start = None

    def flush():
        nonlocal cur, cur_chars, line_start
        if cur:
            chunks.append(cur)
        cur = []
        cur_chars = 0
        line_start = None

    for i, w in enumerate(words):
        if line_start is None:
            line_start = w.start

        # break on silence gap
        if cur:
            gap = w.start - cur[-1].end
            if gap >= GAP_BREAK:
                flush()
                line_start = w.start

        # projected length if we add this word
        add = len(w.text) + (1 if cur else 0)
        projected = cur_chars + add

        # projected duration if we add this word
        projected_dur = (w.end - line_start) if line_start is not None else (w.end - w.start)

        # enforce limits
        if cur and (projected > MAX_LINE_CHARS or projected_dur > MAX_LINE_DURATION):
            flush()
            line_start = w.start

        cur.append(w)
        cur_chars = (cur_chars + add) if cur_chars else len(w.text)

    flush()

    # Ensure very short lines don't happen too often; (optional) can be refined later.
    return chunks

def karaoke_text_for_chunk(chunk: list[Word]) -> str:
    """
    ASS karaoke:
    - Use {\kN} per word, where N is duration in centiseconds.
    - SecondaryColour is the 'fill' highlight in karaoke.
    """
    parts = []
    for w in chunk:
        dur = max(0.01, w.end - w.start)
        k = max(1, int(round(dur * 100)))  # centiseconds, at least 1
        parts.append(f"{{\\k{k}}}{w.text}")
    # Join with spaces between words (spaces outside tags work fine)
    return " ".join(parts)

def write_ass(chunks: list[list[Word]], out_path: Path):
    lines = [ASS_STYLE]
    for chunk in chunks:
        start = chunk[0].start
        end = chunk[-1].end
        # Avoid ultra-short events
        if end - start < MIN_LINE_DURATION:
            end = start + MIN_LINE_DURATION

        text = karaoke_text_for_chunk(chunk)

        lines.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Kara,,0,0,0,,{text}\n"
        )

    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"✅ Wrote ASS karaoke subtitles: {out_path}")

def align_with_whisperx(audio_path: str, transcript_text: str, language: str = "en"):
    device = "cuda"  # use "cpu" if needed, but cuda is much faster
    compute_type = "float16"

    # 1) Load whisperx + transcribe to get segments (even though transcript is exact)
    model = whisperx.load_model("large-v3", device, compute_type=compute_type, language=language)
    result = model.transcribe(audio_path, language=language)

    # 2) Load align model
    align_model, metadata = whisperx.load_align_model(language_code=language, device=device)

    # 3) Forced alignment using your exact transcript
    transcript_text = tokenize_transcript(transcript_text)
    aligned = whisperx.align(
        transcript_text,
        align_model,
        metadata,
        audio_path,
        device,
        return_char_alignments=False
    )
    return aligned

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True, help="Path to audio file (wav/mp3/m4a)")
    p.add_argument("--text", required=True, help="Path to transcript text file (UTF-8)")
    p.add_argument("--lang", default="en", help="en for English, hi for Hindi")
    p.add_argument("--out", default="karaoke.ass", help="Output .ass path")
    args = p.parse_args()

    transcript = Path(args.text).read_text(encoding="utf-8")
    aligned = align_with_whisperx(args.audio, transcript, language=args.lang)
    words = words_from_whisperx(aligned)

    if not words:
        raise RuntimeError("No aligned words produced. Check audio/text/lang.")

    chunks = chunk_words(words)
    write_ass(chunks, Path(args.out))

if __name__ == "__main__":
    main()
