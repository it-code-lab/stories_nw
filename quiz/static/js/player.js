// Player UI runtime (vanilla ES module)

const els = {
  bgVideo: document.getElementById('bgVideo'),
  bgImage: document.getElementById('bgImage'),
  bgTint:  document.getElementById('bgTint'),
  bgMusic: document.getElementById('bgMusic'),

  title:   document.getElementById('quizTitle'),
  counter: document.getElementById('qCounter'),
  diff:    document.getElementById('diffPill'),

  card:    document.getElementById('card'),
  qText:   document.getElementById('questionText'),
  imgs:    document.getElementById('images'),
  opts:    document.getElementById('options'),

  ringWrap: document.getElementById('timerRing'),
  ringBar:  document.getElementById('ringBar'),
  timeNum:  document.getElementById('timeNum'),

  barWrap:  document.getElementById('timerBarWrap'),
  barFill:  document.getElementById('timerBar'),
  timeNumB: document.getElementById('timeNumBar'),

  prevBtn: document.getElementById('prevBtn'),
  nextBtn: document.getElementById('nextBtn'),
  restartBtn: document.getElementById('restartBtn'),

  expl:    document.getElementById('explanation'),

  fsBtn:   document.getElementById('fsBtn'),
  landBtn: document.getElementById('landBtn'),
  portBtn: document.getElementById('portBtn'),
};

let quiz = null;
let idx = 0;
let cancelTimer = null;
let revealed = false; // state per question

// ---------- Boot ----------
init();

async function init(){
  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  if (!id) {
    setStatus('No quiz id provided. Append ?id=YOUR_ID');
    return;
  }
  try {
    const res = await fetch(`/quiz/api/quizzes/${id}`);
    if (!res.ok) throw new Error('Quiz not found');
    quiz = await res.json();
  } catch (e) {
    console.error(e);
    setStatus('Failed to load quiz.');
    return;
  }

  hydrateTheme();
  goTo(0);
  bindControls();
}

function setStatus(msg){
  if (els.qText) els.qText.textContent = msg || '';
}

// ---------- Theme / Background / Music ----------
function hydrateTheme(){
  const t = quiz.theme || {};
  setCSS('--primary', t.primary || '#00E5FF');
  setCSS('--accent',  t.accent  || '#FF3D7F');
  setCSS('--bg',      t.bg      || '#0B0B0B');
  document.body.style.fontFamily = t.fontFamily || 'Poppins, sans-serif';

  // Background
  const bg = t.background || {};
  const src = bg.src || '';
  if (src.endsWith('.mp4') || src.endsWith('.webm') || src.endsWith('.mov')) {
    els.bgVideo.src = src; els.bgVideo.classList.add('show'); els.bgImage.classList.remove('show');
  } else if (src) {
    els.bgImage.src = src; els.bgImage.classList.add('show'); els.bgVideo.classList.remove('show');
  }

  // Music
  if (t.music?.src) {
    els.bgMusic.src = t.music.src;
    els.bgMusic.volume = clamp01(t.music.volume ?? 0.35);
    // Autoplay may require interaction; try, but don't block
    els.bgMusic.play().catch(()=>{ /* ignore */ });
  }

  // Timer style toggle
  const style = (t.timerStyle || 'ring').toLowerCase();
  if (style === 'bar') {
    hide(els.ringWrap); show(els.barWrap);
  } else {
    hide(els.barWrap); show(els.ringWrap);
  }

  // Title
  els.title.textContent = quiz.title || '';
}

function setCSS(name, val){ document.documentElement.style.setProperty(name, val); }
function clamp01(x){ return Math.max(0, Math.min(1, x)); }

// ---------- Navigation ----------
function goTo(n){
  idx = Math.max(0, Math.min(n, quiz.questions.length - 1));
  const q = quiz.questions[idx];
  revealed = false;

  // HUD
  els.counter.textContent = `Q ${idx+1}/${quiz.questions.length}`;
  els.diff.textContent = (q.difficulty || '').toUpperCase();

  // Content
  els.qText.textContent = q.text || '';
  els.expl.classList.add('hidden');
  els.expl.textContent = q.explanation || '';

  // Images
  els.imgs.innerHTML = '';
  (q.images || []).forEach(src => {
    const im = document.createElement('img'); im.src = src; els.imgs.appendChild(im);
  });

  // Options
  els.opts.innerHTML = '';
  if (q.type === 'mcq') {
    (q.options || []).forEach((opt, i) => {
      const b = document.createElement('button');
      b.className = 'opt';
      b.textContent = opt || '';
      b.dataset.idx = String(i);
      els.opts.appendChild(b);
    });
  } else {
    const div = document.createElement('div');
    div.style.opacity = .8;
    div.textContent = 'Answer will be revealed when time ends…';
    els.opts.appendChild(div);
  }

  // Timer
  startTimer(q);
}

function next(){
  if (!quiz) return;
  if (idx < quiz.questions.length - 1) goTo(idx+1);
}
function prev(){
  if (!quiz) return;
  if (idx > 0) goTo(idx-1);
}
function restart(){
  if (!quiz) return;
  goTo(idx);
}

// ---------- Timer / Reveal ----------
function startTimer(q){
  cancelTimer?.();
  const total = Number(q.timerSec || quiz.defaults?.timerSec || 10);

  const useBar = (quiz.theme?.timerStyle || 'ring').toLowerCase() === 'bar';
  show(useBar ? els.barWrap : els.ringWrap);
  hide(useBar ? els.ringWrap : els.barWrap);

  if (useBar) {
    // Bar: scaleX from 1 → 0
    setBar(1); els.timeNumB.textContent = total;
  } else {
    // Ring: stroke-dasharray 100% → 0%
    setRing(100); els.timeNum.textContent = total;
  }

  let t = total;
  const iv = setInterval(()=>{
    t -= 1;
    if (t < 0) { clearInterval(iv); reveal(q); return; }
    if (useBar) { setBar(Math.max(0, t/total)); els.timeNumB.textContent = t; }
    else        { setRing(Math.max(0, (t/total)*100)); els.timeNum.textContent = t; }
  }, 1000);

  cancelTimer = ()=> clearInterval(iv);
}

function setRing(pct){ els.ringBar.setAttribute('stroke-dasharray', `${pct}, 100`); }
function setBar(scale){ els.barFill.style.transform = `scaleX(${scale})`; }

function reveal(q){
  if (revealed) return;
  revealed = true;

  // Music duck
  if (quiz.theme?.music?.duckOnReveal) {
    duckAudio(els.bgMusic, 0.2, 450, 750); // to 20%, fade 450ms, then recover over 750ms
  }

  if (q.type === 'mcq') {
    const buttons = [...els.opts.querySelectorAll('.opt')];
    buttons.forEach((b, i) => {
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

  if (q.explanation) els.expl.classList.remove('hidden');
}

// Simple ducking: fade to target, then back
function duckAudio(audio, targetVol=0.25, fadeMs=300, recoverMs=600){
  if (!audio) return;
  const start = audio.volume;
  const step = 16;

  // fade down
  const downSteps = Math.max(1, Math.floor(fadeMs/step));
  let i = 0;
  const down = setInterval(()=>{
    i++;
    audio.volume = start + (targetVol - start) * (i/downSteps);
    if (i >= downSteps) {
      clearInterval(down);
      // wait a beat, then recover
      setTimeout(()=>fadeTo(audio, start, recoverMs), 200);
    }
  }, step);
}
function fadeTo(audio, target, ms){
  const start = audio.volume;
  const step = 16;
  const steps = Math.max(1, Math.floor(ms/step));
  let i = 0;
  const iv = setInterval(()=>{
    i++;
    audio.volume = start + (target - start) * (i/steps);
    if (i>=steps){ audio.volume = target; clearInterval(iv); }
  }, step);
}

// ---------- Controls / Hotkeys ----------
function bindControls(){
  els.nextBtn.onclick = ()=> next();
  els.prevBtn.onclick = ()=> prev();
  els.restartBtn.onclick = ()=> restart();

  els.fsBtn.onclick = ()=> toggleFullscreen();
  els.landBtn.onclick = ()=> setLandscape();
  els.portBtn.onclick = ()=> setPortrait();

  window.addEventListener('keydown', (e)=>{
    const k = e.key.toLowerCase();
    if (k === ' ' || k === 'enter') { e.preventDefault(); next(); }
    else if (k === 'backspace')    { e.preventDefault(); prev(); }
    else if (k === 'r')            { restart(); }
    else if (k === 'f')            { toggleFullscreen(); }
    else if (k === 't')            { toggleOrientation(); }
  });
}

function toggleFullscreen(){
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
  else document.exitFullscreen?.();
}

function setLandscape(){ document.body.classList.remove('portrait'); }
function setPortrait(){  document.body.classList.add('portrait'); }
function toggleOrientation(){ document.body.classList.toggle('portrait'); }

// ---------- Utils ----------
function show(el){ el?.classList.remove('hidden'); }
function hide(el){ el?.classList.add('hidden'); }
