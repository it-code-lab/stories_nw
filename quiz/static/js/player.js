// Enhanced Quiz Player: honors Builder theme (animations, idle, stagger, timer style, overlay tint,
// image fit/pos, per-question font scales) + OBS-friendly controls.

const els = {
  bgVideo: document.getElementById('bgVideo'),
  bgImage: document.getElementById('bgImage'),
  bgTint: document.getElementById('bgTint'),
  bgMusic: document.getElementById('bgMusic'),
  title: document.getElementById('quizTitle'),
  counter: document.getElementById('qCounter'),
  diff: document.getElementById('diffPill'),
  card: document.getElementById('card'),
  qText: document.getElementById('questionText'),
  imgs: document.getElementById('images'),
  opts: document.getElementById('options'),
  ringWrap: document.getElementById('timerRing'),
  ringBar: document.getElementById('ringBar'),
  timeNum: document.getElementById('timeNum'),
  barWrap: document.getElementById('timerBarWrap'),
  barFill: document.getElementById('timerBar'),
  timeNumB: document.getElementById('timeNumBar'),

  //DND
  // prevBtn: document.getElementById('prevBtn'),
  // nextBtn: document.getElementById('nextBtn'),
  // restartBtn: document.getElementById('restartBtn'),

  expl: document.getElementById('explanation'),
  // fsBtn:   document.getElementById('fsBtn'),
  landBtn: document.getElementById('landBtn'),
  portBtn: document.getElementById('portBtn')
};

const soundGate = document.getElementById('soundGate');
const enableSoundBtn = document.getElementById('enableSoundBtn');

let audioUnlocked = false;
let audioCtx = null;


let quiz = null, idx = 0, cancelTimer = null, revealed = false, lastVol = null;

init();

function showSoundGate()  { soundGate?.classList.remove('hidden'); }
function hideSoundGate()  { soundGate?.classList.add('hidden'); }

function enableSound() {
  if (audioUnlocked) return;
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    // create a silent blip to satisfy gesture-required policy
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    gain.gain.value = 0;            // silence
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.01);
    audioCtx.resume?.();
  } catch (e) {
    console.warn('AudioContext init failed:', e);
  }
  audioUnlocked = true;
  hideSoundGate();
}

function waitForAudioUnlock() {
  if (audioUnlocked) return Promise.resolve();
  showSoundGate();
  return new Promise(res => {
    const once = () => { enableSound(); cleanup(); res(); };
    const cleanup = () => {
      window.removeEventListener('click', once, true);
      window.removeEventListener('keydown', once, true);
    };
    enableSoundBtn?.addEventListener('click', once, { once: true });
    // also unlock on any user interaction
    window.addEventListener('click', once, { once: true, capture: true });
    window.addEventListener('keydown', once, { once: true, capture: true });
  });
}

// Layout fitter: keeps options inside the card even with large question/images
function layoutOptionsFit() {
  const card = els.card;
  const qEl = els.qText;
  const imgsEl = els.imgs;
  const optsEl = els.opts;
  const footer = card.querySelector('.footer');

  if (!card || !optsEl) return;

  // How many rows will the options occupy?
  const count = optsEl.querySelectorAll('.opt').length;
  if (!count) return;

  // Columns mapping (your grid classes): 1->1 row, 2->1 row, 3->2 rows, 4->2 rows
  const rows = (count <= 2) ? 1 : 2;

  // Measurements
  const cardH = card.clientHeight;
  const qH = qEl?.offsetHeight || 0;
  const imgsH = imgsEl?.offsetHeight || 0;
  const footH = footer?.offsetHeight || 0;

  // Spacing (gap inside options grid)
  const styles = getComputedStyle(optsEl);
  const gap = parseFloat(styles.gap || '0');
  const verticalGaps = gap * Math.max(0, rows - 1);

  // Available vertical space for the options grid
  const available = Math.max(
    0,
    cardH - qH - imgsH - footH - verticalGaps - 24 // 24px buffer for borders/radii
  );

  // If images are too tall (leaving < ~160px per row), shrink image area first.
  const minPerRow = 160; // px target; feel free to tune
  const needPerRows = rows * minPerRow + verticalGaps + 24;
  if (available < needPerRows && imgsH > 0) {
    const deficit = needPerRows - available;
    const newMaxImgH = Math.max(80, imgsH - deficit);
    document.documentElement.style.setProperty('--img-max-h', `${newMaxImgH}px`);
  } else {
    // room is fine; let images use their default cap
    document.documentElement.style.setProperty('--img-max-h', '');
  }

  // Recompute with possibly reduced images height
  const imgsH2 = imgsEl?.offsetHeight || 0;
  const available2 = Math.max(
    0,
    cardH - qH - imgsH2 - footH - verticalGaps - 24
  );

  // Final per-row height for options
  const perRow = Math.max(88, Math.floor((available2 - 0) / rows)); // never below 88px
  document.documentElement.style.setProperty('--opt-h', `${perRow}px`);
}

// ---------- Init ----------
async function init() {
  const id = new URLSearchParams(location.search).get('id');
  if (!id) { setStatus('Missing quiz id (?id=...)'); return; }

  try {
    const res = await fetch(`/quiz/api/quizzes/${id}`);
    quiz = await res.json();
  } catch (e) { console.error(e); setStatus('Load failed'); return; }

  hydrateTheme();
  bindControls();
  goTo(0);
}

function setStatus(msg) { if (els.qText) els.qText.textContent = msg; }

// ---------- Theme / Layout ----------
function hydrateTheme() {
  const t = quiz.theme || {};
  setCSS('--primary', t.primary || '#00E5FF');
  setCSS('--accent', t.accent || '#FF3D7F');
  document.body.style.fontFamily = t.fontFamily || 'Poppins, sans-serif';

  // Background
  const bg = t.background || {};
  if (bg.src) {
    hide(els.bgVideo); hide(els.bgImage);
    if (/\.(mp4|webm|mov)$/i.test(bg.src)) {
      els.bgVideo.src = bg.src; show(els.bgVideo);
    } else {
      els.bgImage.src = bg.src; show(els.bgImage);
    }
  }

  // Overlay tint (color + opacity or fallback)
  const color = bg.overlay?.color || '#000000';
  const op = typeof bg.overlay?.opacity === 'number' ? bg.overlay.opacity : 0.45;
  const rgba = hexToRgba(color, op);
  setCSS('--bg-tint', `linear-gradient(180deg, ${rgba}, ${rgba})`);

  // Music
  if (t.music?.src) {
    els.bgMusic.src = t.music.src;
    els.bgMusic.volume = clamp01(t.music.volume ?? 0.35);
    els.bgMusic.play().catch(() => { });
  }

  // Timer style
  const style = (t.timerStyle || 'ring').toLowerCase();
  if (style === 'bar') { hide(els.ringWrap); show(els.barWrap); }
  else { show(els.ringWrap); hide(els.barWrap); }

  // HUD visibility (optional; default true)
  const hud = t.hud || {};
  showIf(els.counter, hud.showCounter !== false);
  showIf(els.diff, hud.showDifficulty !== false);

  els.title.textContent = quiz.title || '';
}

function setCSS(k, v) { document.documentElement.style.setProperty(k, v); }
function clamp01(x) { return Math.max(0, Math.min(1, x)); }
function show(el) { el?.classList.add('show'); el?.classList.remove('hidden'); }
function hide(el) { el?.classList.remove('show'); el?.classList.add('hidden'); }
function showIf(el, ok) { ok ? el.classList.remove('hidden') : el.classList.add('hidden'); }

// ---------- Navigation ----------
function goTo(n) {
  idx = Math.max(0, Math.min(n, quiz.questions.length - 1));
  revealed = false;

  els.card.classList.remove('fade-in');
  els.card.classList.add('fade-out');

  setTimeout(() => {
    renderQuestion(quiz.questions[idx]);
    els.card.classList.remove('fade-out');
    els.card.classList.add('fade-in');
  }, 220);
}

function next() { if (idx < quiz.questions.length - 1) goTo(idx + 1); }
function prev() { if (idx > 0) goTo(idx - 1); }
function restart() { goTo(idx); }

// ---------- Render ----------
async function renderQuestion(q) {
  // Always hide + clear explanation when a new question renders
  els.expl.classList.add('hidden');
  els.expl.classList.remove('show');
  els.expl.textContent = '';

  // HUD
  els.counter.textContent = `Q ${idx + 1}/${quiz.questions.length}`;
  els.diff.textContent = (q.difficulty || '').toUpperCase();

  // Question text + per-question font scaling
  els.qText.textContent = q.text || '';
  setCSS('--q-scale', (isFinite(q.qFontScale) ? q.qFontScale : 1));
  setCSS('--opt-scale', (isFinite(q.optFontScale) ? q.optFontScale : 1));

  // Images (fit/pos from q with fallback)
  setCSS('--qimg-fit', q.imgFit || 'cover');
  setCSS('--qimg-pos', q.imgPos || 'center');
  setCSS('--oimg-fit', q.optImgFit || q.imgFit || 'cover');
  setCSS('--oimg-pos', q.optImgPos || q.imgPos || 'center');

  await speakQuestion(q.text);

  renderImages(q.images || []);
  renderOptions(q);

  // Animations: entrance + idle
  applyAnimations();

  // fit layout now, and again when any question images finish loading
  layoutOptionsFit();
  els.imgs.querySelectorAll('img').forEach(im => {
    if (im.complete) return;
    im.addEventListener('load', layoutOptionsFit, { once: true });
  });

  // Timer
  startTimer(q);
}

function renderImages(arr) {
  els.imgs.innerHTML = '';
  arr.forEach(src => {
    const im = document.createElement('img');
    im.src = src;
    els.imgs.appendChild(im);
  });
}

function renderOptions(q) {
  els.opts.innerHTML = '';
  if (q.type === 'mcq') {
    const opts = q.options || [];
    const count = Math.min(opts.length || 1, 4);
    els.opts.className = `options cols-${count}`;

    const a = (quiz.theme?.animations) || {};
    const stagger = !!a.stagger;
    const step = isFinite(a.staggerStep) ? a.staggerStep : 0.10;

    opts.forEach((opt, i) => {
      const b = document.createElement('button');
      b.className = 'opt';

      // entrance class set later in applyAnimations()

      // image + text
      if (opt.image) {
        const div = document.createElement('div');
        div.className = 'opt-img';
        const im = document.createElement('img');
        im.src = opt.image; div.appendChild(im);
        b.appendChild(div);
      }
      if (opt.text || typeof opt === 'string') {
        const txt = document.createElement('div');
        txt.className = 'opt-text';
        txt.textContent = opt.text || opt;
        b.appendChild(txt);
      }

      // Stagger animation delay (applied before reveal)
      if (stagger) b.style.animationDelay = `${i * step}s`;

      b.dataset.idx = i;
      els.opts.appendChild(b);
    });
  } else {
    els.opts.className = 'options cols-1';
    const info = document.createElement('div');
    info.style.opacity = .85;
    info.textContent = 'Answer will be revealed at end of timer';
    els.opts.appendChild(info);
  }
}

function applyAnimations() {
  // remove previous
  ['anim-fade', 'anim-slide', 'anim-zoom', 'idle-breath', 'idle-shake', 'idle-float'].forEach(c => {
    els.qText.classList.remove(c);
    els.opts.classList.remove(c);
  });
  els.imgs.querySelectorAll('img').forEach(im => {
    ['anim-fade', 'anim-slide', 'anim-zoom', 'idle-breath', 'idle-shake', 'idle-float'].forEach(c => im.classList.remove(c));
  });

  const a = quiz.theme?.animations || {};
  const qEnt = a.question || 'fade';
  const oEnt = a.options || 'fade';
  const idle = a.idle || 'none';
  const intensity = a.idleIntensity || 3;

  // entrance
  els.qText.classList.add(`anim-${qEnt}`);
  // add to each .opt
  els.opts.querySelectorAll('.opt').forEach(o => {
    o.classList.add(`anim-${oEnt}`);
  });

  // idle motion (question, options container, images)
  if (idle !== 'none') {
    const speed = Math.max(0.5, 6 / (intensity / 3)); // higher intensity → faster loop
    els.qText.classList.add(`idle-${idle}`);
    els.opts.classList.add(`idle-${idle}`);
    els.qText.style.animationDuration = `${speed}s`;
    els.opts.style.animationDuration = `${speed}s`;
    els.imgs.querySelectorAll('img').forEach(im => {
      im.classList.add(`idle-${idle}`);
      im.style.animationDuration = `${speed}s`;
    });
  } else {
    els.qText.style.animationDuration = '';
    els.opts.style.animationDuration = '';
  }
}

// ---------- Timer / Reveal ----------
function startTimer(q) {
  cancelTimer?.();

  const total = Number(q.timerSec || quiz.defaults?.timerSec || 10);
  const useBar = (quiz.theme?.timerStyle || 'ring').toLowerCase() === 'bar';

  // show correct timer UI
  show(useBar ? els.barWrap : els.ringWrap);
  hide(useBar ? els.ringWrap : els.barWrap);

  if (useBar) {
    // ① Disable transition for the very first paint
    els.barFill.classList.add('notrans');
    setBar(1);
    els.timeNumB.textContent = total;

    // ② Force reflow, then re-enable transition for subsequent updates
    void els.barFill.offsetWidth;     // reflow
    requestAnimationFrame(() => {
      els.barFill.classList.remove('notrans');
    });
  } else {
    setRing(100);
    els.timeNum.textContent = total;
  }

  let t = total;
  const iv = setInterval(() => {
    t--;
    if (t < 0) { clearInterval(iv); reveal(q); return; }

    if (useBar) {
      setBar(Math.max(0, t / total));        // transitions now apply
      els.timeNumB.textContent = t;
    } else {
      setRing((t / total) * 100);
      els.timeNum.textContent = t;
    }
  }, 1000);

  cancelTimer = () => clearInterval(iv);
}


function setRing(p) { els.ringBar.setAttribute('stroke-dasharray', `${p},100`); }
function setBar(scale) { els.barFill.style.transform = `scaleX(${scale})`; }

function reveal(q) {
  if (revealed) return; revealed = true;

  // Music ducking
  const duck = !!(quiz.theme?.music?.duckOnReveal);
  if (duck) {
    lastVol = els.bgMusic.volume;
    els.bgMusic.volume = clamp01((lastVol ?? 0.35) * 0.45);
  }

  if (q.type === 'mcq') {
    [...els.opts.querySelectorAll('.opt')].forEach((b, i) => {
      if (i === (q.correctIndex ?? 0)) b.classList.add('correct');
      else b.classList.add('dim');
    });
  } else {
    const ans = (q.answer || '').trim();
    if (ans) {
      const r = document.createElement('div');
      r.className = 'opt correct';
      r.textContent = `Answer: ${ans}`;
      els.opts.appendChild(r);
    }
  }
  if (q.explanation) {
    els.expl.textContent = q.explanation;
    els.expl.classList.remove('hidden');

    // Start hidden (ensure no leftover state)
    els.expl.classList.remove('show');
    // els.expl.style.opacity = '0';

    // After a short delay (~1 second) fade it in
    setTimeout(() => {
      els.expl.classList.add('show');
    }, 1000);
  }

  // restore music on next question
}

// ---------- Controls / Hotkeys ----------
function bindControls() {
  //DND
  // els.nextBtn.onclick = () => next();
  // els.prevBtn.onclick = () => prev();
  // els.restartBtn.onclick = () => restart();


  //DND
  // els.fsBtn.onclick=()=>toggleFullscreen();
  els.landBtn.onclick = () => setLandscape();
  els.portBtn.onclick = () => setPortrait();

  window.addEventListener('keydown', (e) => {
    if (e.code === 'Space' || e.code === 'Enter') { e.preventDefault(); next(); }
    else if (e.code === 'Backspace') { e.preventDefault(); prev(); }
    else if (e.key === 'r' || e.key === 'R') { restart(); }
    else if (e.key === 'f' || e.key === 'F') { toggleFullscreen(); }
    else if (e.key === 't' || e.key === 'T') { toggleOrientation(); }
  });

  enableSoundBtn?.addEventListener('click', enableSound);

}

function toggleFullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => { });
  else document.exitFullscreen().catch(() => { });
}
function setLandscape() {
  document.body.classList.remove('portrait');
  els.landBtn.classList.remove('ghost');
  els.portBtn.classList.add('ghost');
}
function setPortrait() {
  document.body.classList.add('portrait');
  els.portBtn.classList.remove('ghost');
  els.landBtn.classList.add('ghost');
}
function toggleOrientation() { document.body.classList.contains('portrait') ? setLandscape() : setPortrait(); }

// ---------- Utils ----------
function hexToRgba(hex, alpha = 1) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '#000000');
  if (!m) return `rgba(0,0,0,${alpha})`;
  const r = parseInt(m[1], 16), g = parseInt(m[2], 16), b = parseInt(m[3], 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// after navigation, restore volume if ducked previously
const _goTo = goTo;
goTo = function (...args) {
  if (lastVol != null) {
    els.bgMusic.volume = lastVol;
    lastVol = null;
  }
  return _goTo.apply(this, args);
};

async function speakQuestion(text) {
  if (!text) return;

  // ensure user has interacted at least once
  await waitForAudioUnlock();

  const lang = quiz.language || 'en'; // fallback to English if missing

  try {
    const res = await fetch('/get_audio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, language: lang })
    });
    if (!res.ok) throw new Error('TTS request failed');

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);

    // try to play (should be allowed after unlock)
    try {
      await audio.play();
    } catch (e) {
      // If a race happens and we still get NotAllowedError, prompt again
      console.warn('TTS play blocked; waiting for user gesture...', e);
      await waitForAudioUnlock();
      await audio.play().catch(err => console.error('TTS play failed:', err));
    }

    return new Promise(resolve => {
      audio.onended = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      // safety: resolve after 30s if no end fires
      setTimeout(()=>{ try{audio.pause();}catch{} resolve(); }, 30000);
    });

  } catch (err) {
    console.error('TTS Error:', err);
  }
}


window.addEventListener('resize', layoutOptionsFit);
new ResizeObserver(layoutOptionsFit).observe(els.card);
