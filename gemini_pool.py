# gemini_pool.py
from __future__ import annotations
import os, json, time, random, threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, Callable

import pytz
from google import genai
from google.genai import types as gt

PACIFIC_TZ = pytz.timezone("America/Los_Angeles")

def pacific_today_key() -> str:
    return datetime.now(PACIFIC_TZ).strftime("%Y-%m-%d")

def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None

def _iso_to_dt(s: Optional[str]) -> Optional[datetime]:
    if not s: return None
    return datetime.fromisoformat(s)

@dataclass
class KeyState:
    api_key: str
    max_rpm: int = 30
    window_secs: int = 60
    recent_timestamps: List[float] = field(default_factory=list)
    disabled_until: Optional[datetime] = None
    day_key: str = field(default_factory=pacific_today_key)
    requests_today: int = 0
    last_error: Optional[str] = None
    _client: Optional[genai.Client] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["disabled_until"] = _dt_to_iso(self.disabled_until)
        d["_client"] = None
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "KeyState":
        ks = KeyState(api_key=d["api_key"])
        ks.max_rpm = d.get("max_rpm", 30)
        ks.window_secs = d.get("window_secs", 60)
        ks.recent_timestamps = d.get("recent_timestamps", [])
        ks.disabled_until = _iso_to_dt(d.get("disabled_until"))
        ks.day_key = d.get("day_key", pacific_today_key())
        ks.requests_today = d.get("requests_today", 0)
        ks.last_error = d.get("last_error")
        return ks

    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def allow_now(self) -> bool:
        now = time.time()
        if self.day_key != pacific_today_key():
            self.reset_for_new_day()
        if self.disabled_until and datetime.now(PACIFIC_TZ) < self.disabled_until:
            return False
        cutoff = now - self.window_secs
        self.recent_timestamps = [t for t in self.recent_timestamps if t >= cutoff]
        return len(self.recent_timestamps) < self.max_rpm

    def mark_used_now(self):
        self.recent_timestamps.append(time.time())
        self.requests_today += 1

    def disable_until_midnight_pt(self, reason: str):
        self.last_error = reason
        today = datetime.now(PACIFIC_TZ)
        midnight = PACIFIC_TZ.localize(datetime.combine((today + timedelta(days=1)).date(), datetime.min.time()))
        self.disabled_until = midnight

    def reset_for_new_day(self):
        self.day_key = pacific_today_key()
        self.requests_today = 0
        self.disabled_until = None
        self.recent_timestamps.clear()
        self.last_error = None
        self._client = genai.Client(api_key=self.api_key)

class NoActiveKeysError(RuntimeError): ...

class GeminiPool:
    def __init__(
        self,
        api_keys: List[str] | None = None,
        *,
        per_key_rpm: int = 30,
        max_attempts: int = 5,
        base_backoff: float = 0.6,
        backoff_jitter: Tuple[float, float] = (0.2, 0.6),
        state_path: Optional[str] = ".gemini_pool_state.json",
        autosave_every: int = 5,
    ):
        if not api_keys:
            env = os.getenv("GEMINI_API_KEYS", "")
            api_keys = [k.strip() for k in env.split(",") if k.strip()]
        if not api_keys:
            raise ValueError("No API keys supplied. Set GEMINI_API_KEYS or pass a list.")

        self.state_path = state_path
        self.autosave_every = autosave_every
        self._save_counter = 0

        # load persisted state
        persisted: Dict[str, Dict[str, Any]] = {}
        if self.state_path and os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    persisted = json.load(f)
            except Exception:
                persisted = {}

        self.keys: List[KeyState] = []
        for k in api_keys:
            if k in persisted:
                ks = KeyState.from_dict(persisted[k])
                # If day changed while server was down, reset now:
                if ks.day_key != pacific_today_key():
                    ks.reset_for_new_day()
            else:
                ks = KeyState(api_key=k, max_rpm=per_key_rpm)
            ks.max_rpm = per_key_rpm  # ensure new RPM
            self.keys.append(ks)

        self._lock = threading.Lock()
        self._rr_index = 0
        self.max_attempts = max_attempts
        self.base_backoff = base_backoff
        self.backoff_jitter = backoff_jitter

        self.default_text_model = "gemini-2.0-flash"
        self.default_image_model = "gemini-2.5-flash-image"

        # initial save (so file exists)
        self._save_state()

    # ---------- Public ----------
    def generate_text(self, prompt: str, *, model: Optional[str] = None,
                      system_instruction: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_output_tokens: Optional[int] = None,
                      extra: Optional[Dict[str, Any]] = None) -> str:
        model = model or self.default_text_model
        def call(client: genai.Client):
            params = {}
            if system_instruction:
                params["system_instruction"] = system_instruction
            cfg = gt.GenerateContentConfig()
            if temperature is not None:
                cfg.temperature = temperature
            if max_output_tokens is not None:
                cfg.max_output_tokens = max_output_tokens
            if temperature is not None or max_output_tokens is not None:
                params["config"] = cfg
            if extra: params.update(extra)
            r = client.models.generate_content(model=model, contents=prompt, **params)
            if getattr(r, "text", None): return r.text
            if getattr(r, "candidates", None):
                parts = []
                for c in r.candidates:
                    if getattr(c, "content", None) and getattr(c.content, "parts", None):
                        for p in c.content.parts:
                            if getattr(p, "text", None): parts.append(p.text)
                if parts: return "\n".join(parts)
            return str(r)
        return self._with_key_rotation(call)

    def generate_image(self, prompt: str, *, model: Optional[str] = None,
                       extra: Optional[Dict[str, Any]] = None,
                       out_path: Optional[str] = None) -> bytes:
        model = model or self.default_image_model
        def call(client: genai.Client):
            kwargs = {}
            if extra: kwargs.update(extra)
            res = client.models.generate_images(model=model, prompt=prompt, **kwargs)
            img = res.images[0]
            data = getattr(img, "data", None) or getattr(img, "image_bytes", None)
            if not data:
                b64 = getattr(img, "base64_data", None)
                if b64:
                    import base64; data = base64.b64decode(b64)
            if not data:
                raise RuntimeError("No image bytes returned.")
            if out_path:
                with open(out_path, "wb") as f: f.write(data)
            return data
        return self._with_key_rotation(call)

    def stats(self) -> List[Dict[str, Any]]:
        out = []
        with self._lock:
            for i, k in enumerate(self.keys):
                out.append({
                    "slot": i,
                    "day": k.day_key,
                    "requests_today": k.requests_today,
                    "disabled_until": k.disabled_until.isoformat() if k.disabled_until else None,
                    "last_error": k.last_error,
                    "rpm_window_load": len(k.recent_timestamps),
                    "max_rpm": k.max_rpm,
                })
        return out

    # ---------- Internals ----------
    def _choose_key(self) -> KeyState:
        with self._lock:
            n = len(self.keys)
            for i in range(n):
                idx = (self._rr_index + i) % n
                ks = self.keys[idx]
                if ks.allow_now():
                    self._rr_index = (idx + 1) % n
                    return ks
        raise NoActiveKeysError("No active keys (throttled or disabled).")

    def _with_key_rotation(self, fn: Callable[[genai.Client], Any]) -> Any:
        attempt, last_err = 0, None
        while attempt < self.max_attempts:
            attempt += 1
            try:
                ks = self._choose_key()
            except NoActiveKeysError as e:
                last_err = e
                time.sleep(min(5 * attempt, 20))
                continue
            try:
                ks.mark_used_now()
                res = fn(ks.client())
                self._maybe_autosave()
                return res
            except Exception as e:
                reason = self._classify_error(e)
                if reason in ("quota", "rate"):
                    ks.disable_until_midnight_pt(f"{reason} limit reached")
                    self._save_state()
                    last_err = e
                    continue
                if reason in ("transient", "server", "network"):
                    last_err = e
                    time.sleep(self._compute_backoff(attempt))
                    continue
                raise
        if last_err: raise last_err
        raise RuntimeError("GeminiPool: exhausted attempts.")

    def _classify_error(self, e: Exception) -> str:
        m = str(e).lower()
        if any(t in m for t in ["quota exceeded","daily limit","exceeded your current quota","rpd quota","requests per day","too many requests","rate limit","429","resource has been exhausted"]):
            return "rate" if "rate" in m or "429" in m else "quota"
        if any(t in m for t in ["unavailable","timeout","timed out","503","502","500"]):
            return "transient"
        if any(t in m for t in ["connection","dns","ssl","socket","broken pipe","reset by peer"]):
            return "network"
        return "other"

    def _compute_backoff(self, attempt: int) -> float:
        return self.base_backoff * (2 ** (attempt - 1)) + random.uniform(*self.backoff_jitter)

    def _maybe_autosave(self):
        if not self.state_path: return
        self._save_counter += 1
        if self._save_counter >= self.autosave_every:
            self._save_counter = 0
            self._save_state()

    def _save_state(self):
        if not self.state_path: return
        state = {k.api_key: k.to_dict() for k in self.keys}
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.state_path)
