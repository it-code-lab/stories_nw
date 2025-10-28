export function setupMusic(el, src, volume=0.35) {
  if (!src) return;
  el.src = src; el.volume = volume; el.play().catch(()=>{});
}
export function duck(el, factor=0.4, ms=300) {
  const start = el.volume, target = Math.max(0, start*factor);
  const step = (start-target)/(ms/16);
  const iv = setInterval(()=>{
    el.volume = Math.max(target, el.volume - step);
    if (el.volume <= target) clearInterval(iv);
  }, 16);
}
