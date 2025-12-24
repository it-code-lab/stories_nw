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
  prevBtn: document.getElementById('prevBtn'),
  nextBtn: document.getElementById('nextBtn'),
  restartBtn: document.getElementById('restartBtn'),

  expl: document.getElementById('explanation'),
  // fsBtn:   document.getElementById('fsBtn'),
  landBtn: document.getElementById('landBtn'),
  portBtn: document.getElementById('portBtn'),
  sfxDing: document.getElementById('sfxDing')
};

const soundGate = document.getElementById('soundGate');
const enableSoundBtn = document.getElementById('enableSoundBtn');
const bgPlayPause = document.getElementById('bgPlayPause'), bgMute = document.getElementById('bgMute'), musicPlayPause = document.getElementById('musicPlayPause');

bgPlayPause.onclick = () => {
  if (bgVideo.paused) { bgVideo.play(); bgPlayPause.textContent = 'Pause BG'; }
  else { bgVideo.pause(); bgPlayPause.textContent = 'Play BG'; }
};
bgMute.onclick = () => {
  bgVideo.muted = !bgVideo.muted;
  bgMute.textContent = bgVideo.muted ? 'Unmute BG' : 'Mute BG';
};
musicPlayPause.onclick = () => {
  if (bgMusic.paused) { bgMusic.play(); musicPlayPause.textContent = 'Pause Music'; }
  else { bgMusic.pause(); musicPlayPause.textContent = 'Play Music'; }
};


let audioUnlocked = false;
let audioCtx = null;
let autoAdvanceTO = null;

let quiz = null, idx = 0, cancelTimer = null, revealed = false, lastVol = null;

init();

function showSoundGate() { soundGate?.classList.remove('hidden'); }
function hideSoundGate() { soundGate?.classList.add('hidden'); }

let musicStarted = false;

async function playBgMusic() {
  if (!quiz?.theme?.music?.src) return;
  const a = els.bgMusic;
  if (!a || musicStarted) return;
  await waitForAudioUnlock(); // ensure user gesture happened

  try {
    await a.play();
    musicStarted = true;
  } catch (e) {
    console.warn('bgMusic play blocked, will retry after next unlock', e);
    // Next user gesture will call enableSound() which we hook to retry
  }
}

function removeAnimClasses(el) {
  if (!el) return;
  ['anim-fade', 'anim-slide', 'anim-zoom', 'idle-breath', 'idle-shake', 'idle-float']
    .forEach(c => el.classList.remove(c));
}

function applyIdleTo(el, idle, intensity = 3) {
  if (!el || idle === 'none') return;
  removeAnimClasses(el);  // ensure no leftover entrance class
  el.classList.add(`idle-${idle}`);
  const speed = Math.max(0.5, 6 / (intensity / 3)); // higher intensity → faster
  el.style.animationDuration = `${speed}s`;
}

function clearIdle(el) {
  if (!el) return;
  ['idle-breath', 'idle-shake', 'idle-float'].forEach(c => el.classList.remove(c));
  el.style.animationDuration = '';
}

// Call this if you want to pause/resume around TTS instead of ducking
function pauseBgMusic() { try { els.bgMusic.pause(); } catch { } }
async function resumeBgMusic() {
  if (!quiz?.theme?.music?.src) return;
  await waitForAudioUnlock();
  try { await els.bgMusic.play(); musicStarted = true; } catch { }
}

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

  quiz.autoAdvance = quiz.autoAdvance || { enabled: false, delaySec: 3, afterExplanation: true };
  if (typeof quiz.autoAdvance.enabled !== 'boolean') quiz.autoAdvance.enabled = false;
  if (!Number.isFinite(quiz.autoAdvance.delaySec)) quiz.autoAdvance.delaySec = 3;
  if (typeof quiz.autoAdvance.afterExplanation !== 'boolean') quiz.autoAdvance.afterExplanation = true;

  hydrateTheme();
  bindControls();
  await waitForAudioUnlock();
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
    playBgMusic();
  }

  // Timer style
  const style = (t.timerStyle || 'ring').toLowerCase();
  if (style === 'bar') { hide(els.ringWrap); show(els.barWrap); }
  else { show(els.ringWrap); hide(els.barWrap); }

  // HUD visibility (optional; default true)
  const hud = t.hud || {};
  showIf(els.counter, hud.showCounter !== false);
  showIf(els.diff, hud.showDifficulty !== false);

  // SFX (ding)
  const sfx = (t.sfx || {});
  els.sfxDing.src = sfx.ding?.src || '/quiz/static/sfx/low-bell-ding.wav';   // put your file there
  // els.sfxDing.volume = clamp01(sfx.ding?.volume ?? 0.9);

  els.title.textContent = quiz.title || '';
}

function setCSS(k, v) { document.documentElement.style.setProperty(k, v); }
function clamp01(x) { return Math.max(0, Math.min(1, x)); }
function show(el) { el?.classList.add('show'); el?.classList.remove('hidden'); }
function hide(el) { el?.classList.remove('show'); el?.classList.add('hidden'); }
function showIf(el, ok) { ok ? el.classList.remove('hidden') : el.classList.add('hidden'); }

// ---------- Navigation ----------
function goTo(n) {
  // cancel any pending auto-advance
  if (autoAdvanceTO) { clearTimeout(autoAdvanceTO); autoAdvanceTO = null; }

  idx = Math.max(0, Math.min(n, quiz.questions.length - 1));
  revealed = false;

  // els.card.classList.add('hidden-vis');
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

async function playDing() {
  if (!els.sfxDing?.src) return;
  await waitForAudioUnlock();                 // respects autoplay policy
  try {
    els.sfxDing.currentTime = 0;              // rewind for rapid sequences
    await els.sfxDing.play();
  } catch (e) {
    console.warn('ding play blocked; will retry after unlock', e);
  }
}


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

  // 🔴 IMPORTANT: clear/hide previous UI BEFORE any TTS so nothing from the
  // previous question lingers while narration plays
  els.imgs.innerHTML = '';
  els.opts.innerHTML = '';

  // keep containers hidden until entrance sequence runs
  els.imgs.style.visibility = 'hidden';
  els.opts.style.visibility = 'hidden';

  // also remove any leftover animation classes
  removeAnimClasses(els.qText);
  
  els.imgs.querySelectorAll('img').forEach(removeAnimClasses);
  els.opts.querySelectorAll('.opt').forEach(removeAnimClasses);

  if (idx == 0) {
    //pause for 3 seconds on first question to let user get ready
    await new Promise(res => setTimeout(res, 3000));
  }
  await speakQuestion(q.text);

  renderImages(q.images || []);
  renderOptions(q);


  // fit layout now, and again when any question images finish loading
  layoutOptionsFit();
  els.imgs.querySelectorAll('img').forEach(im => {
    if (im.complete) return;
    im.addEventListener('load', layoutOptionsFit, { once: true });
  });

  // Timer
  //startTimer(q);
  runEntranceSequence(q);
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
      b.className = 'opt prehidden';
      // b.className = 'opt hidden-vis';
      //b.style.visibility = 'hidden';
      // entrance class set later in applyAnimations()

      // Option label (A, B, C, D)
      const label = document.createElement('span');
      label.className = 'opt-label';
      label.textContent = String.fromCharCode(65 + i); // 65 = 'A'
      b.appendChild(label);

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

//idle-only applicator
function applyAnimations() {
  const a = quiz.theme?.animations || {};
  const idle = a.idle || 'none';
  const intensity = a.idleIntensity || 3;

  // question
  clearIdle(els.qText);
  applyIdleTo(els.qText, idle, intensity);

  // each option
  els.opts.querySelectorAll('.opt').forEach(o => {
    clearIdle(o);
    applyIdleTo(o, idle, intensity);
  });

  // each question image
  els.imgs.querySelectorAll('img').forEach(im => {
    clearIdle(im);
    applyIdleTo(im, idle, intensity);
  });
}

function runEntranceSequence(q) {
  const a = quiz.theme?.animations || {};
  const qEnt   = a.question || 'fade';
  const imgEnt = a.images || a.question || 'fade';
  const oEnt   = a.options || 'fade';
  const idle   = a.idle || 'none';
  const intensity = a.idleIntensity || 3;
  const stagger = !!a.stagger;
  const step    = isFinite(a.staggerStep) ? a.staggerStep : 0.10;

  // Reset visibility + classes
  [els.qText, els.imgs, els.opts].forEach(el => {
    el.style.visibility = 'hidden';
    removeAnimClasses(el);
  });
  els.imgs.querySelectorAll('img').forEach(im => {
    removeAnimClasses(im);
    im.classList.add('prehidden');   // ⟵ start hidden
  });
  els.opts.querySelectorAll('.opt').forEach(o => {
    removeAnimClasses(o);
    o.classList.add('prehidden');    // ⟵ start hidden
  });

  // 1) Question
  els.qText.classList.add('prehidden');
  els.qText.style.visibility = 'visible';

  // apply entrance on next frame to ensure prehidden takes effect first
  requestAnimationFrame(() => {
    els.qText.classList.remove('prehidden');
    onQDone();

    // if (qEnt === 'none') {
    //   onQDone();
    //   return;
    // }
    // els.qText.classList.add(`anim-${qEnt}`);
    // els.qText.addEventListener('animationend', onQDone, { once: true });
  });

  function onQDone() {
    applyIdleTo(els.qText, idle, intensity);
    revealImages();
  }

  // 2) Images (with stagger)
  function revealImages() {
    const images = [...els.imgs.querySelectorAll('img')];
    if (!images.length) return revealOptions();

    els.imgs.style.visibility = 'visible';

    requestAnimationFrame(() => {
      images.forEach((im, i) => {
        im.classList.remove('prehidden');
        im.classList.add(`anim-${imgEnt}`);
        if (stagger) im.style.animationDelay = `${i * step}s`;
        im.addEventListener('animationend', () => applyIdleTo(im, idle, intensity), { once: true });
      });

      const last = images[images.length - 1];
      last.addEventListener('animationend', revealOptions, { once: true });
    });
  }

  // 3) Options (with stagger)
  function revealOptions() {
    const opts = [...els.opts.querySelectorAll('.opt')];
    els.opts.style.visibility = 'visible';

    if (!opts.length) { startTimer(q); return; }

    let ended = 0;
    requestAnimationFrame(() => {
      opts.forEach((o, i) => {
        o.classList.remove('prehidden');              // ⟵ prevents flash
        o.classList.add(`anim-${oEnt}`);
        if (stagger) o.style.animationDelay = `${i * step}s`;

        o.addEventListener('animationend', () => {
          applyIdleTo(o, idle, intensity);
          if (++ended === opts.length) startTimer(q);
        }, { once: true });
      });
    });
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

  // Play ding when revealing the answer
  playDing();

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


  // --- Auto-advance logic ---
  const qa = q.autoAdvance || {};
  const qaEnabled = (qa.enabled != null) ? qa.enabled : (quiz.autoAdvance?.enabled === true);
  if (!qaEnabled) return;                     // off globally or for this q

  const afterExp = (qa.afterExplanation != null) ? qa.afterExplanation : (quiz.autoAdvance?.afterExplanation === true);
  const baseDelay = Number.isFinite(qa.delaySec) ? qa.delaySec : (quiz.autoAdvance?.delaySec ?? 3);

  // If you fade explanation in after ~1s, optionally add a small buffer so the viewer can see it
  const extraBuffer = afterExp && q.explanation ? 0.8 : 0;  // seconds; tune if needed

  // Don’t queue beyond the last question
  if (idx >= quiz.questions.length - 1) return;

  // Clear any prior
  if (autoAdvanceTO) { clearTimeout(autoAdvanceTO); autoAdvanceTO = null; }

  autoAdvanceTO = setTimeout(() => {
    autoAdvanceTO = null;
    next(); // uses your existing navigation
  }, Math.max(0, (baseDelay + extraBuffer) * 1000));

  // restore music on next question
}

// ---------- Controls / Hotkeys ----------
function bindControls() {
  //DND
  els.nextBtn.onclick = () => next();
  els.prevBtn.onclick = () => prev();
  els.restartBtn.onclick = () => restart();


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

  enableSoundBtn?.addEventListener('click', () => {
    // when user enables sound, start (or retry) bg music
    playBgMusic();
  });

}

function toggleFullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => { });
  else document.exitFullscreen().catch(() => { });
}
function setLandscape() {
  document.body.classList.remove('portrait');
  document.body.classList.add('landscape');

  els.landBtn.classList.remove('ghost');
  els.portBtn.classList.add('ghost');
}
function setPortrait() {
  document.body.classList.remove('landscape');
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
  //await waitForAudioUnlock();
  if (!text) return;
  if (!quiz?.qsTTS || quiz.qsTTS.toLowerCase() !== 'y') return;

  // ensure user has interacted at least once
  await waitForAudioUnlock();

  const lang = quiz.language || 'en'; // fallback to English if missing

  let prevVol = null;
  if (els.bgMusic) {
    prevVol = els.bgMusic.volume;
    els.bgMusic.volume = clamp01((prevVol ?? 0.35) * 0.45);
  }

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
      setTimeout(() => { try { audio.pause(); } catch { } resolve(); }, 30000);
    });

  } catch (err) {
    console.error('TTS Error:', err);
  } finally {
    // restore music after TTS
    if (prevVol != null) els.bgMusic.volume = prevVol;
    // if paused instead of ducked: await resumeBgMusic();
  }
}


window.addEventListener('resize', layoutOptionsFit);
new ResizeObserver(layoutOptionsFit).observe(els.card);
