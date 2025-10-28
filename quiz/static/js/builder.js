// Simple stateful builder for quiz JSON + live preview (ES module-safe)

// ---------- State ----------
const state = {
  quiz: {
    id: null,
    title: "",
    language: "en",
    theme: {
      preset: "Neon Quiz",
      primary: "#00E5FF",
      accent:  "#FF3D7F",
      bg:      "#0B0B0B",
      fontFamily: "Poppins, sans-serif",
      buttonStyle: "pill",
      timerStyle:   "ring",
      animationStyle: "slide-up",
      background: { type: "video", src: "/static/backgrounds/nebula.mp4", intensity: 0.6 },
      music: { src: "/static/music/ambient_loop.mp3", volume: 0.35, duckOnReveal: true }
    },
    defaults: { timerSec: 12 },
    questions: []
  },
  selIndex: -1
};

// ---------- Elements ----------
const el = (id) => document.getElementById(id);

// Meta / Theme
const quizTitle   = el('quizTitle');
const quizLang    = el('quizLang');
const defaultTimer= el('defaultTimer');
const themePreset = el('themePreset');
const colorPrimary= el('colorPrimary');
const colorAccent = el('colorAccent');
const fontFamily  = el('fontFamily');
const timerStyle  = el('timerStyle');
const bgSrc       = el('bgSrc');
const musicSrc    = el('musicSrc');
const musicVol    = el('musicVol');
const duckOnReveal= el('duckOnReveal');

// Question list + editor
const addMcq      = el('addMcq');
const addSingle   = el('addSingle');
const qList       = el('qList');
const qCount      = el('qCount');

const qEditor     = el('qEditor');
const qType       = el('qType');
const qDiff       = el('qDiff');
const qTimer      = el('qTimer');
const qText       = el('qText');
const qExplain    = el('qExplain');
const correctIdx  = el('correctIdx');
const singleAnswer= el('singleAnswer');
const mcqBlock    = el('mcqBlock');
const singleBlock = el('singleBlock');

const dupBtn      = el('dupBtn');
const delBtn      = el('delBtn');
const applyBtn    = el('applyBtn');

const addImgBtn   = el('addImgBtn');
const imgFile     = el('imgFile');
const imgGrid     = el('imgGrid');

// IO buttons
const loadJsonBtn   = el('loadJsonBtn');
const loadJsonInput = el('loadJsonInput');
const importCsvBtn  = el('importCsvBtn');
const importCsvInput= el('importCsvInput');
const saveBtn       = el('saveBtn');
const playBtn       = el('playBtn');

// Preview
const pv = {
  wrap: el('preview'),
  title: el('pvTitle'),
  count: el('pvCount'),
  diff:  el('pvDiff'),
  q:     el('pvQ'),
  imgs:  el('pvImgs'),
  opts:  el('pvOpts'),
  timer: el('pvTimer'),
  portraitBtn:  el('portraitBtn'),
  landscapeBtn: el('landscapeBtn')
};

// ---------- Meta handlers ----------
function refreshMeta() {
  const q = state.quiz;
  q.title = (quizTitle?.value || "").trim();
  q.language = (quizLang?.value || "en");
  q.defaults.timerSec = parseInt((defaultTimer?.value || '12'), 10);

  q.theme.preset     = themePreset?.value || q.theme.preset;
  q.theme.primary    = colorPrimary?.value || q.theme.primary;
  q.theme.accent     = colorAccent?.value  || q.theme.accent;
  q.theme.fontFamily = fontFamily?.value   || q.theme.fontFamily;
  q.theme.timerStyle = timerStyle?.value   || q.theme.timerStyle;

  if (bgSrc)    q.theme.background.src = bgSrc.value.trim();
  if (musicSrc) q.theme.music.src      = musicSrc.value.trim();
  if (musicVol) q.theme.music.volume   = parseFloat(musicVol.value || '0.35');
  if (duckOnReveal) q.theme.music.duckOnReveal = !!duckOnReveal.checked;

  applyThemeToPreview();
}

// Safely wire inputs
[
  quizTitle, quizLang, defaultTimer, themePreset,
  colorPrimary, colorAccent, fontFamily, timerStyle,
  bgSrc, musicSrc, musicVol, duckOnReveal
].forEach(i => { if (i) i.addEventListener('input', refreshMeta); });

function applyThemeToPreview(){
  const t = state.quiz.theme;
  document.body.style.setProperty('--primary', t.primary);
  document.body.style.setProperty('--accent',  t.accent);
  document.body.style.setProperty('--bg',      t.bg);
  document.body.style.setProperty('--font',    t.fontFamily);
  if (pv.title) pv.title.textContent = state.quiz.title || 'Title';
}

// ---------- Question actions ----------
function addQuestion(type){
  const base = {
    id: `q${Date.now()}`,
    type,
    difficulty: 'easy',
    text: '',
    images: [],
    timerSec: state.quiz.defaults.timerSec,
    explanation: ''
  };
  if (type === 'mcq') { base.options = ['', '', '', '']; base.correctIndex = 0; }
  else { base.answer = ''; }
  state.quiz.questions.push(base);
  state.selIndex = state.quiz.questions.length - 1;
  renderQList();
  openEditor(state.selIndex);
}

if (addMcq)    addMcq.onclick    = () => addQuestion('mcq');
if (addSingle) addSingle.onclick = () => addQuestion('single');

function renderQList(){
  if (!qList) return;
  qList.innerHTML = '';
  state.quiz.questions.forEach((q, idx) => {
    const li = document.createElement('li');
    li.className = 'qitem' + (idx===state.selIndex ? ' active' : '');
    li.innerHTML = `
      <div class="idx">${idx+1}</div>
      <div class="meta">
        <div class="title">${q.text ? escapeHtml(q.text.slice(0,60)) : (q.type==='mcq'?'(MCQ)':'(Single)')}</div>
        <div class="muted">${q.difficulty.toUpperCase()} • ${(q.timerSec||state.quiz.defaults.timerSec)}s</div>
      </div>
      <div class="row">
        <button class="btn" data-act="up">↑</button>
        <button class="btn" data-act="down">↓</button>
        <button class="btn" data-act="edit">Edit</button>
      </div>`;
    li.querySelector('[data-act="edit"]').onclick = ()=> openEditor(idx);
    li.querySelector('[data-act="up"]').onclick   = ()=> moveQ(idx,-1);
    li.querySelector('[data-act="down"]').onclick = ()=> moveQ(idx,1);
    qList.appendChild(li);
  });
  if (qCount) qCount.textContent = `${state.quiz.questions.length} items`;
  updatePreviewFromSelection();
}

function moveQ(i, delta){
  const j = i+delta; if (j<0 || j>=state.quiz.questions.length) return;
  const arr = state.quiz.questions; [arr[i], arr[j]] = [arr[j], arr[i]];
  state.selIndex = j; renderQList();
}

function openEditor(idx){
  state.selIndex = idx;
  const q = state.quiz.questions[idx];
  if (!qEditor) return;

  qEditor.classList.remove('hidden');
  if (qType) qType.value = q.type;
  if (qDiff) qDiff.value = q.difficulty;
  if (qTimer) qTimer.value = q.timerSec || '';
  if (qText) qText.value = q.text || '';
  if (qExplain) qExplain.value = q.explanation || '';

  if (imgGrid) imgGrid.innerHTML = '';
  (q.images||[]).forEach(src=> addImgThumb(src));

  if (q.type === 'mcq') {
    mcqBlock?.classList.remove('hidden'); singleBlock?.classList.add('hidden');
    // Only fill inputs inside the editor, not preview
    document.querySelectorAll('#qEditor .opt').forEach((inp,i)=>{ inp.value = q.options[i]||''; });
    if (correctIdx) correctIdx.value = String(q.correctIndex||0);
  } else {
    mcqBlock?.classList.add('hidden'); singleBlock?.classList.remove('hidden');
    if (singleAnswer) singleAnswer.value = q.answer || '';
  }
  renderQList();
}

if (qType) qType.onchange = ()=>{
  const q = currentQ(); if (!q) return;
  q.type = qType.value;
  if (q.type==='mcq' && !q.options) { q.options=['','','','']; q.correctIndex=0; }
  if (q.type==='single') { delete q.options; delete q.correctIndex; q.answer = q.answer || ''; }
  openEditor(state.selIndex);
};

if (applyBtn) applyBtn.onclick = ()=>{
  const q = currentQ(); if (!q) return;
  q.difficulty = qDiff?.value || 'easy';
  q.timerSec   = parseInt(qTimer?.value || state.quiz.defaults.timerSec, 10);
  q.text       = (qText?.value || '').trim();
  q.explanation= (qExplain?.value || '').trim();

  if (q.type==='mcq'){
    const opts = [...document.querySelectorAll('#qEditor .opt')].map(i=>i.value.trim());
    q.options = opts;
    q.correctIndex = parseInt(correctIdx?.value,10) || 0;
  } else {
    q.answer = (singleAnswer?.value || '').trim();
  }
  renderQList();
};

if (dupBtn) dupBtn.onclick = ()=>{
  const q = currentQ(); if (!q) return;
  const copy = JSON.parse(JSON.stringify(q));
  copy.id = `q${Date.now()}`;
  state.quiz.questions.splice(state.selIndex+1,0,copy);
  state.selIndex += 1; renderQList(); openEditor(state.selIndex);
};

if (delBtn) delBtn.onclick = ()=>{
  if (state.selIndex<0) return;
  state.quiz.questions.splice(state.selIndex,1);
  state.selIndex = Math.min(state.selIndex, state.quiz.questions.length-1);
  renderQList(); if (state.selIndex>=0) openEditor(state.selIndex); else qEditor?.classList.add('hidden');
};

function currentQ(){ return state.quiz.questions[state.selIndex]; }

// ---------- Images ----------
if (addImgBtn) addImgBtn.onclick = ()=> imgFile?.click();

if (imgFile) imgFile.onchange = async (e)=>{
  const file = e.target.files[0]; if (!file) return;
  const form = new FormData(); form.append('file', file); form.append('type','images');
  const res = await fetch('/quiz/api/upload', { method:'POST', body: form });
  const data = await res.json();
  if (data.url){ currentQ().images = currentQ().images || []; currentQ().images.push(data.url); addImgThumb(data.url); }
  imgFile.value = '';
};

function addImgThumb(url){
  if (!imgGrid) return;
  const im = document.createElement('img'); im.src = url; imgGrid.appendChild(im);
}

// ---------- IO (load/import/save/play) ----------
if (loadJsonBtn) loadJsonBtn.onclick = ()=> loadJsonInput?.click();

if (loadJsonInput) loadJsonInput.onchange = async (e)=>{
  const file = e.target.files[0]; if (!file) return;
  const txt = await file.text(); const qz = JSON.parse(txt);
  state.quiz = normalizeQuiz(qz); state.selIndex = -1;
  hydrateMeta(); renderQList();
};

if (importCsvBtn) importCsvBtn.onclick = ()=> importCsvInput?.click();

if (importCsvInput) importCsvInput.onchange = async (e)=>{
  const file = e.target.files[0]; if (!file) return;
  const form = new FormData(); form.append('file', file);
  const res = await fetch('/quiz/api/import/csv', { method:'POST', body: form });
  const data = await res.json();
  if (Array.isArray(data.questions)){
    state.quiz.questions = state.quiz.questions.concat(data.questions);
    renderQList();
  } else alert('CSV import failed.');
};

if (saveBtn) saveBtn.onclick = async ()=>{
  refreshMeta();
  const res = await fetch('/quiz/api/quizzes', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(state.quiz)
  });
  const data = await res.json();
  if (data?.id){ state.quiz.id = data.id; alert('Saved: '+data.id); }
};

if (playBtn) playBtn.onclick = ()=>{
  if (!state.quiz.id){ alert('Please save first.'); return; }
  location.href = `/quiz/play?id=${state.quiz.id}`;
};

// ---------- Preview ----------
function updatePreviewFromSelection(){
  applyThemeToPreview();
  const i = Math.max(0, state.selIndex);
  const q = state.quiz.questions[i];
  if (!q){
    if (pv.q)     pv.q.textContent = 'Add a question to preview';
    if (pv.count) pv.count.textContent = 'Q 0/0';
    return;
  }
  if (pv.q)     pv.q.textContent = q.text || '(question)';
  if (pv.count) pv.count.textContent = `Q ${i+1}/${state.quiz.questions.length}`;
  if (pv.diff)  pv.diff.textContent = (q.difficulty||'easy').toUpperCase();
  if (pv.timer) pv.timer.textContent = q.timerSec || state.quiz.defaults.timerSec;

  if (pv.imgs) {
    pv.imgs.innerHTML = '';
    (q.images||[]).slice(0,2).forEach(src=>{
      const im = document.createElement('img');
      im.src = src; im.style.maxHeight = '26vh'; im.style.borderRadius='10px';
      pv.imgs.appendChild(im);
    });
  }
  if (pv.opts){
    pv.opts.innerHTML='';
    if (q.type==='mcq') (q.options||['','','','']).forEach(o=>{
      const b=document.createElement('button'); b.className='opt'; b.textContent=o||'(option)'; pv.opts.appendChild(b);
    });
    else {
      const hint=document.createElement('div'); hint.style.opacity='.8'; hint.textContent='Answer shown on reveal'; pv.opts.appendChild(hint);
    }
  }
}

if (pv.portraitBtn)  pv.portraitBtn.onclick  = ()=>{ pv.wrap?.classList.add('portrait');  pv.wrap?.classList.remove('landscape'); };
if (pv.landscapeBtn) pv.landscapeBtn.onclick = ()=>{ pv.wrap?.classList.add('landscape'); pv.wrap?.classList.remove('portrait');  };

// ---------- Helpers ----------
function hydrateMeta(){
  const q = state.quiz;
  if (quizTitle) quizTitle.value = q.title||'';
  if (quizLang)  quizLang.value  = q.language||'en';
  if (defaultTimer) defaultTimer.value = q.defaults?.timerSec||12;

  if (themePreset)  themePreset.value  = q.theme?.preset||'Neon Quiz';
  if (colorPrimary) colorPrimary.value = q.theme?.primary||'#00E5FF';
  if (colorAccent)  colorAccent.value  = q.theme?.accent||'#FF3D7F';
  if (fontFamily)   fontFamily.value   = q.theme?.fontFamily||'Poppins, sans-serif';
  if (timerStyle)   timerStyle.value   = q.theme?.timerStyle||'ring';
  if (bgSrc)        bgSrc.value        = q.theme?.background?.src||'';
  if (musicSrc)     musicSrc.value     = q.theme?.music?.src||'';
  if (musicVol)     musicVol.value     = q.theme?.music?.volume ?? 0.35;
  if (duckOnReveal) duckOnReveal.checked = !!q.theme?.music?.duckOnReveal;
  applyThemeToPreview();
}

function normalizeQuiz(q){
  q.defaults = q.defaults||{}; q.defaults.timerSec = q.defaults.timerSec||12;
  q.theme = q.theme||{};
  q.theme.background = q.theme.background||{type:'video',src:''};
  q.theme.music = q.theme.music||{src:'',volume:0.35,duckOnReveal:true};
  q.questions = q.questions||[];
  return q;
}

function escapeHtml(s){ return (s||'').replace(/[&<>"']/g, m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m])); }

// ---------- Init ----------
hydrateMeta();
renderQList();

// Support deep link: /builder?id=quiz_...
const params = new URLSearchParams(location.search);
const existingId = params.get('id');
(async function initFromId(){
  if (!existingId) return;
  try {
    const res = await fetch(`/quiz/api/quizzes/${existingId}`);
    if (res.ok){
      const qz = await res.json();
      state.quiz = normalizeQuiz(qz);
      state.selIndex = -1;
      hydrateMeta(); renderQList();
    }
  } catch(e){ console.warn('Failed to load quiz by id', e); }
})();
