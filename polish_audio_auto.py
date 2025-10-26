# polish_audio_auto.py
import subprocess, shlex, re, pathlib, statistics
from typing import Tuple, Optional, List
# -- add these at the top --
import json
import re

# -- remove _LOUDNORM_RE and _parse_loudnorm(...) --
# and add this instead:

def _parse_loudnorm_json(text: str) -> dict:
    """
    Extract the last JSON object printed by loudnorm (print_format=json),
    then map to the fields we need for pass 2.
    """
    # ffmpeg sometimes prints filter logs to stdout or stderr; text is combined upstream
    # Find the last {...} block in the text
    matches = list(re.finditer(r'\{.*?\}', text, flags=re.S))
    if not matches:
        raise RuntimeError("Could not find loudnorm JSON in ffmpeg output.")
    payload = json.loads(matches[-1].group(0))

    # loudnorm json keys use "input_*"
    # Map them to our expected names for pass2
    return {
        "I": str(payload["input_i"]),
        "LRA": str(payload["input_lra"]),
        "TP": str(payload["input_tp"]),
        "thresh": str(payload["input_thresh"]),
        "offset": str(payload["target_offset"]),
    }

def _run(cmd: str):
    p = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def _estimate_noise_dbfs(input_path: str, window_ms: int = 50) -> Tuple[float, float]:
    from pydub import AudioSegment  # pip install pydub
    seg = AudioSegment.from_file(input_path)
    mono = seg.set_channels(1)
    frames = []
    for i in range(0, len(mono), window_ms):
        ch = mono[i:i+window_ms]
        db = ch.dBFS if ch.dBFS != float("-inf") else -100.0
        frames.append(db)
    if not frames:
        return (-100.0, -100.0)
    quiet_10th = statistics.quantiles(frames, n=10)[0]
    overall = statistics.fmean(frames)
    return (quiet_10th, overall)

def _choose_denoise_strength(quiet_dbfs: float) -> Tuple[str, int]:
    if quiet_dbfs <= -55: return ("none", 0)
    if quiet_dbfs <= -45: return ("light", 6)
    if quiet_dbfs <= -35: return ("medium", 12)
    return ("strong", 15)

# _LOUDNORM_RE = {
#     'I': re.compile(r'measured_I:\s*(-?[\d.]+)'),
#     'LRA': re.compile(r'measured_LRA:\s*(-?[\d.]+)'),
#     'TP': re.compile(r'measured_TP:\s*(-?[\d.]+)'),
#     'thresh': re.compile(r'measured_thresh:\s*(-?[\d.]+)'),
#     'offset': re.compile(r'offset:\s*(-?[\d.]+)'),
# }

# def _parse_loudnorm(stderr: str) -> dict:
#     vals = {}
#     for k, rgx in _LOUDNORM_RE.items():
#         m = rgx.search(stderr)
#         if not m: raise RuntimeError(f"Could not parse loudnorm field: {k}")
#         vals[k] = m.group(1)
#     return vals

def _build_chain(denoise_nr: int, hp: int, lp: Optional[int], deess: int, use_speechnorm: bool) -> str:
    parts: List[str] = [f"highpass=f={hp}"]
    if lp: parts.append(f"lowpass=f={lp}")
    if denoise_nr > 0: parts.append(f"afftdn=nr={denoise_nr}:nt=w")
    parts.append("adeclip")
    if deess > 0:
        # Map 0..10 (UI) → 0..1 (FFmpeg), clamp
        deess_coef = max(0.0, min(1.0, deess / 10.0))
        parts.append(f"deesser=i={deess_coef}")  # ← removed ':f=5500'

    if use_speechnorm: parts.append("speechnorm=e=6:r=0.0005:l=1")
    return ",".join(parts)


def polish_audio(
    input_path: str,
    output_path: str,
    denoise_mode: str = "auto",     # auto|none|light|medium|strong
    target_lufs: float = -16.0,
    tp_limit: float = -1.5,
    lra_target: float = 11.0,
    highpass_hz: int = 80,
    lowpass_hz: Optional[int] = 12000,   # set None to disable
    deess_intensity: int = 5,
    force_mono: bool = False,
    samplerate: Optional[int] = None,
    use_speechnorm: bool = False,
    aac_bitrate: str = "192k"
) -> dict:

    in_p = str(pathlib.Path(input_path))
    out_p = str(pathlib.Path(output_path))

    if denoise_mode == "auto":
        quiet_dbfs, overall_dbfs = _estimate_noise_dbfs(in_p)
        label, nr = _choose_denoise_strength(quiet_dbfs)
    else:
        mapping = {"none":0,"light":6,"medium":12,"strong":15}
        label, nr = (denoise_mode, mapping.get(denoise_mode, 0))
        quiet_dbfs = overall_dbfs = None

    base = _build_chain(nr, highpass_hz, lowpass_hz, deess_intensity, use_speechnorm)
    fmt = []
    if force_mono: fmt += ["-ac", "1"]
    if samplerate: fmt += ["-ar", str(samplerate)]

    # probe = f"loudnorm=I={target_lufs}:TP={tp_limit}:LRA={lra_target}:print_format=summary"
    ln_probe = f"loudnorm=I={target_lufs}:TP={tp_limit}:LRA={lra_target}:print_format=json"
    # -nostats/-hide_banner reduce clutter; not required but cleaner
    code, out, err = _run(f'ffmpeg -hide_banner -nostats -y -i "{in_p}" -af "{base},{ln_probe}" -f null -')

    if code != 0: raise RuntimeError(f"ffmpeg pass 1 failed:\n{err}")
    if code != 0:
        # Even if ffmpeg returns non-zero, loudnorm might have printed JSON—try parse anyway
        combined = (out or "") + (err or "")
        try:
            m = _parse_loudnorm_json(combined)
        except Exception:
            raise RuntimeError(f"ffmpeg pass 1 failed:\n{err}")
    else:
        combined = (out or "") + (err or "")
        m = _parse_loudnorm_json(combined)

    ln = (f"loudnorm=I={target_lufs}:TP={tp_limit}:LRA={lra_target}"
          f":measured_I={m['I']}:measured_LRA={m['LRA']}:measured_TP={m['TP']}"
          f":measured_thresh={m['thresh']}:offset={m['offset']}:linear=true")

    

    # Convert dBTP to linear peak for alimiter (0.0625..1.0)
    lin_limit = 10 ** (tp_limit / 20.0)   # tp_limit is negative dB
    if lin_limit < 0.0625: 
        lin_limit = 0.0625
    elif lin_limit > 1.0:
        lin_limit = 1.0

    # chain = f"{base},{ln}"
    chain = f"{base},{ln},alimiter=limit={lin_limit:.6f}"

    print("AF chain:", chain)
    code, _o2, e2 = _run(
        f'ffmpeg -y -i "{in_p}" -af "{chain}" {" ".join(fmt)} -c:a aac -b:a {aac_bitrate} "{out_p}"'
    )


    if code != 0: raise RuntimeError(f"ffmpeg pass 2 failed:\n{e2}")

    return {
        "input": in_p,
        "output": out_p,
        "denoise_mode": label,
        "denoise_nr": nr,
        "quiet_dbfs": quiet_dbfs,
        "overall_dbfs": overall_dbfs,
        "target_lufs": target_lufs,
        "tp_limit_dbTP": tp_limit,
        "lra_target": lra_target,
        "highpass_hz": highpass_hz,
        "lowpass_hz": lowpass_hz,
        "deess_intensity": deess_intensity,
        "force_mono": force_mono,
        "samplerate": samplerate,
        "speechnorm": use_speechnorm
    }
