export function startCountdown(seconds, onTick, onEnd) {
  let t = seconds, cancelled = false;
  const interval = setInterval(() => {
    if (cancelled) { clearInterval(interval); return; }
    t -= 1;
    onTick?.(t);
    if (t <= 0) { clearInterval(interval); onEnd?.(); }
  }, 1000);
  // first paint
  onTick?.(t);
  return () => { cancelled = true; clearInterval(interval); };
}
