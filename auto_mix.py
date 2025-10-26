# auto_mix.py — ffmpeg/pydub backend (no librosa/soundfile)
import os, subprocess
from typing import Tuple
import numpy as np
from pydub import AudioSegment
import pyloudnorm as pyln

# ---------------------------
# Helpers
# ---------------------------
def _db_to_lin(db): return 10.0 ** (db / 20.0)
def _lin_to_db(x, eps=1e-12): return 20.0 * np.log10(np.maximum(np.abs(x), eps))

def _to_stereo(y):
    return np.stack([y, y], axis=1) if y.ndim == 1 else y

def _pad(a, L):
    if a.shape[0] >= L: return a[:L]
    pad = L - a.shape[0]
    if a.ndim == 1: return np.concatenate([a, np.zeros(pad, a.dtype)])
    return np.concatenate([a, np.zeros((pad, a.shape[1]), a.dtype)], axis=0)

def _normalize_peak(y, peak_db=-1.0):
    peak = np.max(np.abs(y)) if y.size else 1.0
    if peak == 0: return y
    return y * (_db_to_lin(peak_db) / peak)

def _lfilter(b, a, x):
    y = np.zeros_like(x)
    if x.ndim == 1:
        z1 = z2 = 0.0
        for n in range(len(x)):
            y[n] = b[0]*x[n] + z1
            z1_new = b[1]*x[n] - a[1]*y[n] + z2
            z2 = b[2]*x[n] - a[2]*y[n]
            z1 = z1_new
    else:
        z1 = np.zeros(x.shape[1]); z2 = np.zeros(x.shape[1])
        for n in range(x.shape[0]):
            y[n, :] = b[0]*x[n, :] + z1
            z1_new = b[1]*x[n, :] - a[1]*y[n, :] + z2
            z2 = b[2]*x[n, :] - a[2]*y[n, :]
            z1 = z1_new
    return y

def _highpass(v, sr, cutoff=80.0, q=0.707):
    w0 = 2*np.pi*cutoff/sr; alpha = np.sin(w0)/(2*q); c = np.cos(w0)
    b0=(1+c)/2; b1=-(1+c); b2=(1+c)/2; a0=1+alpha; a1=-2*c; a2=1-alpha
    b=np.array([b0,b1,b2])/a0; a=np.array([1.0,a1/a0,a2/a0])
    return _lfilter(b,a,v)

def _presence_eq(v, sr, freq=3500.0, gain_db=2.5, q=1.0):
    A=10**(gain_db/40); w0=2*np.pi*freq/sr; alpha=np.sin(w0)/(2*q); c=np.cos(w0)
    b0=1+alpha*A; b1=-2*c; b2=1-alpha*A; a0=1+alpha/A; a1=-2*c; a2=1-alpha/A
    b=np.array([b0,b1,b2])/a0; a=np.array([1.0,a1/a0,a2/a0])
    return _lfilter(b,a,v)

def _soft_knee_comp(x, sr, thr_db=-18.0, ratio=3.0, atk_ms=5.0, rel_ms=90.0, makeup_db=3.0, knee_db=6.0):
    win=max(1,int(sr*0.01))
    mono=x if x.ndim==1 else np.mean(x,axis=1)
    rms=np.sqrt(np.convolve(mono**2, np.ones(win)/win, mode='same') + 1e-12)
    lvl=_lin_to_db(rms)
    k0=thr_db - knee_db/2; k1=thr_db + knee_db/2
    def gr_db(L):
        if L<k0: over=0.0
        elif L>k1: over=L-thr_db
        else:
            t=(L-k0)/knee_db; over=t*t*(knee_db/2.0)
        return 0.0 if over<=0 else over - over/ratio
    gr=np.array([gr_db(L) for L in lvl])
    atk=np.exp(-1.0/(sr*(atk_ms/1000.0))); rel=np.exp(-1.0/(sr*(rel_ms/1000.0)))
    sm=np.zeros_like(gr); prev=0.0
    for i,g in enumerate(gr):
        c=atk if g>prev else rel
        prev=c*prev + (1-c)*g
        sm[i]=prev
    gain=_db_to_lin(-(sm))*_db_to_lin(makeup_db)
    return x*gain if x.ndim==1 else x*gain[:,None]

def _sidechain_duck(music, vocal, sr, duck_db=10.0, floor_db=-1.0, atk_ms=12.0, rel_ms=220.0, pre_ms=20.0, sens_db=-42.0):
    win = max(1, int(sr * 0.02))
    mono_v = vocal if vocal.ndim == 1 else np.mean(vocal, axis=1)
    env = np.sqrt(np.convolve(mono_v**2, np.ones(win)/win, mode='same') + 1e-12)
    env_db = _lin_to_db(env)
    trig = np.clip((env_db - sens_db) / max(1e-6, (0 - sens_db)), 0, 1)
    pre = int(sr * pre_ms / 1000.0)
    trig = np.concatenate([trig[:1].repeat(pre), trig])[:len(trig)]
    atk = np.exp(-1.0/(sr*(atk_ms/1000.0))); rel = np.exp(-1.0/(sr*(rel_ms/1000.0)))
    sm = np.zeros_like(trig); prev = 0.0
    for i, t in enumerate(trig):
        c = atk if t > prev else rel
        prev = c*prev + (1-c)*t
        sm[i] = prev
    duck_curve_db = -(sm * duck_db) + floor_db
    g = _db_to_lin(duck_curve_db)
    L = min(len(g), music.shape[0])
    return music[:L]*g[:,None] if music.ndim==2 else music[:L]*g

def _lufs_normalize(y, sr, target_lufs=-14.0):
    mono = y if y.ndim==1 else np.mean(y, axis=1)
    meter = pyln.Meter(sr)
    in_lufs = meter.integrated_loudness(mono.astype(np.float64))
    gain_db = target_lufs - in_lufs
    return y * _db_to_lin(gain_db), in_lufs, gain_db

# ---------------------------
# I/O via pydub/ffmpeg
# ---------------------------
def _seg_to_array(seg: AudioSegment) -> np.ndarray:
    """pydub AudioSegment -> float32 numpy in [-1,1], shape (n,) or (n,2)."""
    samples = np.array(seg.get_array_of_samples())
    ch = seg.channels
    if ch == 2:
        samples = samples.reshape((-1, 2))
    scale = float(1 << (8*seg.sample_width - 1))
    y = samples.astype(np.float32) / scale
    return y

def _array_to_seg(y: np.ndarray, sr: int) -> AudioSegment:
    """float32 numpy [-1,1] -> AudioSegment (16-bit PCM)."""
    y = np.clip(y, -1.0, 1.0)
    if y.ndim == 1:
        samples = (y * 32767.0).astype(np.int16)
        seg = AudioSegment(
            samples.tobytes(), frame_rate=sr, sample_width=2, channels=1
        )
    else:
        samples = (y * 32767.0).astype(np.int16)
        interleaved = samples.reshape((-1,)).tobytes()
        seg = AudioSegment(
            interleaved, frame_rate=sr, sample_width=2, channels=2
        )
    return seg

def _load_any(path: str, sr_target=44100, stereo=False) -> Tuple[np.ndarray, int]:
    seg = AudioSegment.from_file(path)
    if seg.frame_rate != sr_target:
        seg = seg.set_frame_rate(sr_target)
    seg = seg.set_channels(2 if stereo else 1)
    y = _seg_to_array(seg)
    return y, sr_target

def _export_audio(out_path: str, audio: np.ndarray, sr: int):
    seg = _array_to_seg(audio, sr)
    ext = os.path.splitext(out_path.lower())[1]
    if ext == ".mp3":
        seg.export(out_path, format="mp3", bitrate="256k")
    else:
        seg.export(out_path, format="wav")

# ---------------------------
# Core pipeline (no librosa)
# ---------------------------
def _trim_leading_silence(y: np.ndarray, sr: int, top_db: float = 40.0) -> np.ndarray:
    """Find first frame above threshold and trim before it. Works in mono or stereo."""
    mono = y if y.ndim == 1 else np.mean(y, axis=1)
    win = max(1, int(sr * 0.02))  # 20 ms
    # RMS
    kernel = np.ones(win) / win
    rms = np.sqrt(np.convolve(mono**2, kernel, mode="same") + 1e-12)
    rms_db = _lin_to_db(rms)
    # threshold relative to 0 dBFS -> consider below -top_db as silence
    idx = np.argmax(rms_db > -top_db)
    return y[idx:] if rms_db[idx] > -top_db else y

def mix_arrays(vocal, music, sr,
               music_gain_db=-10.0,
               duck_db=10.0,
               duck_floor_db=-1.0,
               target_lufs=-14.0,
               vocal_hp_cutoff=80.0,
               vocal_presence_db=2.5,
               comp_threshold_db=-18.0,
               comp_ratio=3.0):
    # Align vocal and match lengths
    vocal = _trim_leading_silence(vocal, sr, top_db=40)
    L = max(len(music), len(vocal))
    music = _to_stereo(_pad(music, L))
    vocal = _to_stereo(_pad(vocal, L))

    # Gain staging
    music = music * _db_to_lin(music_gain_db)
    vocal = vocal * _db_to_lin(+3.0)

    # Vocal cleanup
    vocal[:,0] = _highpass(vocal[:,0], sr, cutoff=vocal_hp_cutoff)
    vocal[:,1] = _highpass(vocal[:,1], sr, cutoff=vocal_hp_cutoff)
    if vocal_presence_db != 0:
        vocal[:,0] = _presence_eq(vocal[:,0], sr, freq=3500.0, gain_db=vocal_presence_db, q=1.0)
        vocal[:,1] = _presence_eq(vocal[:,1], sr, freq=3500.0, gain_db=vocal_presence_db, q=1.0)
    vocal = _soft_knee_comp(vocal, sr, thr_db=comp_threshold_db, ratio=comp_ratio, atk_ms=5.0, rel_ms=90.0, makeup_db=3.0, knee_db=6.0)

    # Duck music under vocal
    ducked_music = _sidechain_duck(music, vocal, sr, duck_db=duck_db, floor_db=duck_floor_db, atk_ms=12.0, rel_ms=220.0, pre_ms=20.0, sens_db=-42.0)

    # Sum → normalize → limit
    mixed = ducked_music + vocal
    mixed, in_lufs, gain_db = _lufs_normalize(mixed, sr, target_lufs=target_lufs)
    mixed = _normalize_peak(mixed, peak_db=-1.0)

    return mixed, in_lufs, gain_db

def mix_files(vocal_path: str, music_path: str, out_path: str,
              sr: int = 44100,
              music_gain_db: float = -10.0,
              duck_db: float = 10.0,
              duck_floor_db: float = -1.0,
              target_lufs: float = -14.0) -> Tuple[str, dict]:
    v, _ = _load_any(vocal_path, sr_target=sr, stereo=False)
    m, _ = _load_any(music_path, sr_target=sr, stereo=True)
    mixed, in_lufs, gain_db = mix_arrays(
        v, m, sr,
        music_gain_db=music_gain_db,
        duck_db=duck_db,
        duck_floor_db=duck_floor_db,
        target_lufs=target_lufs
    )
    _export_audio(out_path, mixed, sr)
    meta = {
        "pre_normalization_lufs": round(float(in_lufs), 2),
        "applied_gain_db": round(float(gain_db), 2),
        "target_lufs": float(target_lufs),
        "duck_db": float(duck_db),
        "music_gain_db": float(music_gain_db)
    }
    return out_path, meta
