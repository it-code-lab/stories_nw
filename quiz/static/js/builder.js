// Enhanced Builder: image+text options, per-question images, live preview, autosave

// --------- State ---------
//state.quiz.theme

const state = {
    quiz: {
        id: null,
        title: "",
        language: "en",
        qsTTS: "y",
        theme: {
            preset: "Neon Quiz",
            primary: "#00E5FF",
            accent: "#FF3D7F",
            bg: "#0B0B0B",
            fontFamily: "Poppins, sans-serif",
            timerStyle: "ring",
            background: { type: "video", src: "/quiz/static/backgrounds/A.mp4", intensity: 0.6 },
            music: { src: "/quiz/uploads/music/ambient_loop.mp3", volume: 0.35, duckOnReveal: true },
            animations: { question: 'fade', options: 'fade', stagger: true, staggerStep: 0.10, idle: 'none', idleIntensity: 3 },
        },
        defaults: { timerSec: 12 },
        questions: []
    },
    selIndex: -1,
    animatePreview: true
};

const LS_KEY = "quiz_builder_autosave_v1";

// --------- Helpers ---------
const $ = (id) => document.getElementById(id);
const el = (sel, root = document) => root.querySelector(sel);
function show(e) { e?.classList?.remove('hidden'); }
function hide(e) { e?.classList?.add('hidden'); }
function escapeHtml(s) { return (s || "").replace(/[&<>"']/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[m])); }
function debounce(fn, wait = 400) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); } }
function safeUrl(u) { if (!u) return u; return u.replace(/\\/g, '/').replace(/^\/?uploads\//, '/quiz/uploads/'); }

// --------- Elements ---------
// App bar
const loadJsonBtn = $('loadJsonBtn');
const loadJsonInput = $('loadJsonInput');
const saveBtn = $('saveBtn');
const playBtn = $('playBtn');


// Meta / Theme
const quizTitle = $('quizTitle');
const quizLang = $('quizLang');
const qsTTS = $('qsTTS');
const defaultTimer = $('defaultTimer');
const themePreset = $('themePreset');
const colorPrimary = $('colorPrimary');
const colorAccent = $('colorAccent');
const fontFamily = $('fontFamily');
const timerStyle = $('timerStyle');
const bgSrc = $('bgSrc');
const musicSrc = $('musicSrc');
const musicVol = $('musicVol');
const duckOnReveal = $('duckOnReveal');

const overlayColor = $('overlayColor');
const overlayOpacity = $('overlayOpacity');

const qAnim = $('qAnim');
const optAnim = $('optAnim');
const optStagger = $('optStagger');
const optStaggerStep = $('optStaggerStep');

const idleMotion = $('idleMotion');
const idleIntensity = $('idleIntensity');

const pvQuestionHd = $('pvQuestionHd');
const showQNum = $('showQNum');
const showDiff = $('showDiff');


// Question list
const qList = $('qList');
const qCount = $('qCount');
const addMcq = $('addMcq');
const addSingle = $('addSingle');

// Editor
const noSel = $('noSel');
const qEditor = $('qEditor');
const qType = $('qType');
const qDiff = $('qDiff');
const qTimer = $('qTimer');
const qText = $('qText');
const qExplain = $('qExplain');
const mcqBlock = $('mcqBlock');
const singleBlock = $('singleBlock');
const correctIdx = $('correctIdx');
const singleAnswer = $('singleAnswer');
const dupBtn = $('dupBtn');
const delBtn = $('delBtn');
const applyBtn = $('applyBtn');
// question images
const qImgBtn = $('qImgBtn');
const qImgInput = $('qImgInput');
const qImgGrid = $('qImgGrid');

// options
const optWrap = $('optWrap');
const addOptBtn = $('addOptBtn');
const remOptBtn = $('remOptBtn');

// Preview
const pv = {
    bgVideo: $('pvBgVideo'),
    bgImage: $('pvBgImage'),
    title: $('pvTitle'),
    count: $('pvCount'),
    diff: $('pvDiff'),
    card: $('pvCard'),
    q: $('pvQ'),
    imgs: $('pvImgs'),
    opts: $('pvOpts'),
    expl: $('pvExpl'),
    preview: $('preview'),
    landBtn: $('landBtn'),
    portBtn: $('portBtn'),
    animToggle: $('animToggle'),
    themeMode: $('themeMode')
};

const presetSelect = $('presetSelect');
const applyPresetBtn = $('applyPresetBtn');
const savePresetBtn  = $('savePresetBtn');

const THEME_PRESETS = {
  Neon: {
    primary:'#00E5FF', accent:'#FF3D7F', fontFamily:'Poppins, sans-serif',
    background:{ src:'/quiz/static/backgrounds/A.mp4', overlay:{color:'#000000',opacity:.45}},
    music:{ src:'/quiz/static/music/A.mp3', volume:.35, duckOnReveal:true },
    timerStyle: 'bar',
    animations:{ question:'fade', options:'fade', idle:'breath', idleIntensity:3, stagger:true, staggerStep:.10 }
  },
  Minimal: {
    primary:'#FFFFFF', accent:'#00B894', fontFamily:'Inter, ui-sans-serif, system-ui',
    background:{ src:'/quiz/static/backgrounds/B.mp4', overlay:{color:'#000000',opacity:0.35}},
    music:{ src:'/quiz/static/music/B.mp3', volume:0.25, duckOnReveal:true},
    timerStyle: 'bar',
    animations:{ question:'fade', options:'fade', idle:'breath', idleIntensity:3, stagger:true, staggerStep:.10 }
},
  Retro: {
    primary:'#FFD166', accent:'#EF476F', fontFamily:'Montserrat, Poppins, sans-serif',
    background:{ src:'/quiz/static/backgrounds/C.mp4', overlay:{color:'#1a0b2e',opacity:0.55}},
    music:{ src:'/quiz/static/music/C.mp3', volume:0.3, duckOnReveal:true},
    timerStyle: 'ring',
    animations:{ question:'fade', options:'fade', idle:'breath', idleIntensity:3, stagger:true, staggerStep:.10 }
},
  Paper: {
    primary:'#222222', accent:'#8C6239', fontFamily:'Merriweather, serif',
    background:{ src:'/quiz/static/backgrounds/D.mp4', overlay:{color:'#ffffff',opacity:0.25}},
    music:{ src:'/quiz/static/music/D.mp3', volume:0.25, duckOnReveal:true},
    timerStyle: 'ring',
    animations:{ question:'fade', options:'fade', idle:'breath', idleIntensity:3, stagger:true, staggerStep:.10 }

  }
};

const fontPreview = $('fontPreview');

const qImgFit=$('qImgFit'), qImgPos=$('qImgPos');

const pvMusic = $('pvMusic');
const bgPlayPause=$('bgPlayPause'), bgMute=$('bgMute'), musicPlayPause=$('musicPlayPause');

bgPlayPause.onclick = ()=>{
  if (pv.bgVideo.paused){ pv.bgVideo.play(); bgPlayPause.textContent='Pause BG'; }
  else { pv.bgVideo.pause(); bgPlayPause.textContent='Play BG'; }
};
bgMute.onclick = ()=>{
  pv.bgVideo.muted = !pv.bgVideo.muted;
  bgMute.textContent = pv.bgVideo.muted ? 'Unmute BG' : 'Mute BG';
};
musicPlayPause.onclick = ()=>{
  if (pvMusic.paused){ pvMusic.play(); musicPlayPause.textContent='Pause Music'; }
  else { pvMusic.pause(); musicPlayPause.textContent='Play Music'; }
};


const qFontScale=$('qFontScale'), optFontScale=$('optFontScale');

[qFontScale, optFontScale].forEach(el=> el && el.addEventListener('input', ()=>{
  const q = currentQ(); if(!q) return;
  q.qFontScale = parseFloat(qFontScale.value);
  q.optFontScale = parseFloat(optFontScale.value);
  preview.style.setProperty('--q-scale', q.qFontScale || 1);
  preview.style.setProperty('--opt-scale', q.optFontScale || 1);
  updatePreview(); autosave();
}));

const loopIdleOnly = $('loopIdleOnly');
const replayTransitions = $('replayTransitions');

loopIdleOnly.onchange = ()=> updatePreview();

replayTransitions.onclick = ()=>{
  // force reflow to replay entrance classes
  pv.card.classList.remove('fade-in'); void pv.card.offsetWidth; pv.card.classList.add('fade-in');
};

const pvTimer = $('pvTimer');

function startTimerPreview(sec){
  pvTimer.classList.remove('timer-anim'); void pvTimer.offsetWidth;
  pvTimer.style.setProperty('--timer-dur', `${Math.max(1, sec)}s`);
  pvTimer.style.setProperty('--timer-color', state.quiz.theme.primary || '#00E5FF');
  pvTimer.classList.add('timer-anim');
}

function applyImageFitVars(){
  // Question images
  preview.style.setProperty('--qimg-fit', state.current?.imgFit || 'cover');
  preview.style.setProperty('--qimg-pos', state.current?.imgPos || 'center');
  // Options use same for now (you can split if needed)
  preview.style.setProperty('--oimg-fit', state.current?.optImgFit || state.current?.imgFit || 'cover');
  preview.style.setProperty('--oimg-pos', state.current?.optImgPos || state.current?.imgPos || 'center');
}

[qImgFit, qImgPos].forEach(el=> el && el.addEventListener('change', ()=>{
  const q = currentQ(); if(!q) return;
  q.imgFit = qImgFit.value; q.imgPos = qImgPos.value;
  applyImageFitVars(); updatePreview(); autosave();
}));

function hydrateQuestionEditor(){
  const q = currentQ(); if(!q) return;
  qImgFit.value = q.imgFit || 'cover';
  qImgPos.value = q.imgPos || 'center';
  applyImageFitVars();
    qFontScale.value = q.qFontScale ?? 1;
  optFontScale.value = q.optFontScale ?? 1;
  preview.style.setProperty('--q-scale', q.qFontScale ?? 1);
  preview.style.setProperty('--opt-scale', q.optFontScale ?? 1);
}

function updateFontPreview(){
  const ff = state.quiz.theme.fontFamily || 'Poppins, sans-serif';
  fontPreview.style.fontFamily = ff;
  fontPreview.textContent = 'Aa Bb Cc';
}

fontFamily.onchange = ()=>{
  state.quiz.theme.fontFamily = fontFamily.value;
  updateFontPreview();
  applyThemeToPreview(); autosave();
};

function applyThemePreset(name){
  const p = THEME_PRESETS[name]; if(!p) return;
  const t = state.quiz.theme;
  t.primary=p.primary; t.accent=p.accent; t.fontFamily=p.fontFamily;
  t.background = {...(t.background||{}), ...p.background};
  t.music = {...(t.music||{}), ...p.music};
    t.timerStyle = p.timerStyle;
    t.animations = {...(t.animations||{}), ...p.animations};

  hydrateMeta(); // update controls
  applyThemeToPreview();
  hydrateMeta();
  autosave();
}

// applyPresetBtn.onclick = ()=> presetSelect.value && applyThemePreset(presetSelect.value);

applyPresetBtn.onclick = ()=>{
  const name = presetSelect.value;
  if (!name) return;
  applyThemePreset(name);
  alert(`"${name}" theme applied.`);
};


savePresetBtn.onclick = ()=>{
  const name = prompt('Preset name?'); if(!name) return;
  const t = state.quiz.theme;
  localStorage.setItem('quizPreset:'+name, JSON.stringify(t));
  alert('Saved! You can load it by choosing the same name from localStorage later (dev feature).');
};

// --------- Meta handlers ---------
function refreshMeta() {
    const qz = state.quiz;
    qz.title = (quizTitle?.value || '').trim();
    qz.language = (quizLang?.value || 'en');
    qz.qsTTS = (qsTTS?.value || 'y');
    qz.defaults.timerSec = parseInt(defaultTimer?.value || '12', 10);

    qz.theme.preset = themePreset?.value || qz.theme.preset;
    qz.theme.primary = colorPrimary?.value || qz.theme.primary;
    qz.theme.accent = colorAccent?.value || qz.theme.accent;
    qz.theme.fontFamily = fontFamily?.value || qz.theme.fontFamily;
    qz.theme.timerStyle = timerStyle?.value || qz.theme.timerStyle;
    qz.theme.background.overlay = qz.theme.background.overlay || {};
    qz.theme.background.overlay.color = overlayColor?.value || '#000000';
    qz.theme.background.overlay.opacity = parseFloat(overlayOpacity?.value ?? '0.45');

    qz.theme.animations = qz.theme.animations || {};
    qz.theme.animations.question = qAnim?.value || 'fade';
    qz.theme.animations.options = optAnim?.value || 'fade';

    if (bgSrc) qz.theme.background.src = (bgSrc.value || '').trim();
    if (musicSrc) qz.theme.music.src = (musicSrc.value || '').trim();
    if (musicVol) qz.theme.music.volume = parseFloat(musicVol.value || '0.35');
    if (duckOnReveal) qz.theme.music.duckOnReveal = !!duckOnReveal.checked;

    const anim = state.quiz.theme.animations || (state.quiz.theme.animations = {});
    anim.question = qAnim?.value || 'fade';
    anim.options = optAnim?.value || 'fade';
    anim.stagger = !!optStagger?.checked;
    anim.staggerStep = parseFloat(optStaggerStep?.value || '0.10');


    anim.idle = idleMotion?.value || 'none';
    anim.idleIntensity = parseInt(idleIntensity?.value || '3', 10);


    applyThemeToPreview();
    autosave();
}
[
    quizTitle, quizLang, qsTTS, defaultTimer, themePreset, colorPrimary, colorAccent,
    fontFamily, timerStyle, bgSrc, musicSrc, musicVol, duckOnReveal
].forEach(i => i && i.addEventListener('input', refreshMeta));

[overlayColor, overlayOpacity].forEach(i => i && i.addEventListener('input', refreshMeta));

[qAnim, optAnim, optStagger, optStaggerStep].forEach(el => el && el.addEventListener('input', refreshMeta));
[idleMotion, idleIntensity].forEach(el => el && el.addEventListener('input', refreshMeta));


// --------- Populate background & music dropdowns ---------
async function populateMediaLists() {
    try {
        const res = await fetch("/quiz/api/media");
        if (!res.ok) return;
        const data = await res.json();

        const bgSelect = document.getElementById("bgSelect");
        const musicSelect = document.getElementById("musicSelect");
        bgSelect.innerHTML = `<option value="">(Select Video)</option>`;
        musicSelect.innerHTML = `<option value="">(Select Music)</option>`;

        (data.videos || []).forEach(v => {
            const opt = document.createElement("option");
            opt.value = v;
            opt.textContent = v.split("/").pop();
            bgSelect.appendChild(opt);
        });

        (data.music || []).forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m.split("/").pop();
            musicSelect.appendChild(opt);
        });

        // set current selection
        bgSelect.value = state.quiz.theme.background?.src || "";
        musicSelect.value = state.quiz.theme.music?.src || "";

        // handle changes
        bgSelect.onchange = () => {
            state.quiz.theme.background.src = bgSelect.value;
            document.getElementById("bgSrc").value = bgSelect.value;
            applyThemeToPreview();
            autosave();
        };

        musicSelect.onchange = () => {
            state.quiz.theme.music.src = musicSelect.value;
            document.getElementById("musicSrc").value = musicSelect.value;
            // optional: live preview of background music (short fade)
            autosave();
        };
    } catch (err) {
        console.warn("Failed to fetch media list", err);
    }
}

populateMediaLists();

// function applyThemeToPreview(){
//   const t = state.quiz.theme;
//   document.documentElement.style.setProperty('--primary', t.primary);
//   document.documentElement.style.setProperty('--accent', t.accent);
//   document.body.style.fontFamily = t.fontFamily || 'Poppins, sans-serif';

//   pv.title.textContent = state.quiz.title || 'Title';

//   // background preview
//   const src = t.background?.src || '';
//   pv.bgVideo.classList.remove('show'); pv.bgImage.classList.remove('show');
//   if (/\.(mp4|webm|mov)$/i.test(src)) {
//     pv.bgVideo.src = src; pv.bgVideo.classList.add('show');
//   } else if (src) {
//     pv.bgImage.src = src; pv.bgImage.classList.add('show');
//   }
// }

function applyThemeToPreview() {
    const t = state.quiz.theme;

    document.documentElement.style.setProperty('--primary', t.primary);
    document.documentElement.style.setProperty('--accent', t.accent);
    document.body.style.fontFamily = t.fontFamily || 'Poppins, sans-serif';
    // pv.title.textContent = state.quiz.title || 'Title';

    // background
    const src = t.background?.src || '';
    pv.bgVideo.classList.remove('show'); pv.bgImage.classList.remove('show');
    if (/\.(mp4|webm|mov)$/i.test(src)) { pv.bgVideo.src = src; pv.bgVideo.classList.add('show'); }
    else if (src) { pv.bgImage.src = src; pv.bgImage.classList.add('show'); }

    // safe overlay defaults
    const overlay = (t.background && t.background.overlay) ? t.background.overlay : { color: '#000000', opacity: 0.45 };
    const tintRgba = hexToRgba(overlay.color || '#000000', typeof overlay.opacity === 'number' ? overlay.opacity : 0.45);
    document.documentElement.style.setProperty('--pv-bg-tint', tintRgba);
    if (t.music?.src){ pvMusic.src = t.music.src; pvMusic.volume = t.music.volume ?? 0.35; }
}

// --------- Question list & selection ---------
function addQuestion(type) {
    const base = {
        id: `q${Date.now()}`,
        type,
        difficulty: 'easy',
        text: '',
        images: [],
        timerSec: state.quiz.defaults.timerSec,
        explanation: ''
    };
    if (type === 'mcq') {
        base.options = [{ text: '' }, { text: '' }]; // start with 2
        base.correctIndex = 0;
    } else {
        base.answer = '';
    }
    state.quiz.questions.push(base);
    state.selIndex = state.quiz.questions.length - 1;
    renderQList();
    openEditor(state.selIndex);
    autosave();
}
addMcq.onclick = () => addQuestion('mcq');
addSingle.onclick = () => addQuestion('single');

function renderQList() {
    qList.innerHTML = '';
    state.quiz.questions.forEach((q, idx) => {
        const li = document.createElement('li');
        li.className = 'qitem' + (idx === state.selIndex ? ' active' : '');
        li.innerHTML = `
      <div class="idx">${idx + 1}</div>
      <div class="meta">
        <div class="title">${escapeHtml(q.text || (q.type === 'mcq' ? '(MCQ)' : '(Single)'))}</div>
        <div class="muted">${(q.difficulty || 'easy').toUpperCase()} • ${(q.timerSec || state.quiz.defaults.timerSec)}s</div>
      </div>
      <div class="row">
        <button class="btn tiny" data-act="up">↑</button>
        <button class="btn tiny" data-act="down">↓</button>
        <button class="btn tiny" data-act="edit">Edit</button>
      </div>
    `;
        li.querySelector('[data-act="edit"]').onclick = () => openEditor(idx);
        li.querySelector('[data-act="up"]').onclick = () => moveQ(idx, -1);
        li.querySelector('[data-act="down"]').onclick = () => moveQ(idx, 1);
        qList.appendChild(li);
    });
    qCount.textContent = `${state.quiz.questions.length} items`;
    updatePreview();
}

function moveQ(i, delta) {
    const j = i + delta; if (j < 0 || j >= state.quiz.questions.length) return;
    const arr = state.quiz.questions;[arr[i], arr[j]] = [arr[j], arr[i]];
    state.selIndex = j;
    renderQList();
    autosave();
}

function openEditor(i) {
    state.selIndex = i;
    const q = currentQ(); if (!q) { hide(qEditor); show(noSel); return; }
    hide(noSel); show(qEditor);

    qType.value = q.type;
    qDiff.value = q.difficulty || 'easy';
    qTimer.value = q.timerSec || '';
    qText.value = q.text || '';
    qExplain.value = q.explanation || '';

    // images
    qImgGrid.innerHTML = '';
    (q.images || []).forEach(src => addQImageThumb(src));

    if (q.type === 'mcq') {
        show(mcqBlock); hide(singleBlock);
        renderOptionsEditor(q);
        correctIdx.value = String(q.correctIndex ?? 0);
    } else {
        hide(mcqBlock); show(singleBlock);
        singleAnswer.value = q.answer || '';
    }

    renderQList();
    updatePreview();
}

function currentQ() { return state.quiz.questions[state.selIndex]; }

// --------- Question images upload ---------
qImgBtn.onclick = () => qImgInput.click();
qImgInput.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const url = await uploadImage(file);
    if (!url) return;
    const q = currentQ(); q.images = q.images || []; q.images.push(url);
    addQImageThumb(url);
    updatePreview(); autosave();
    qImgInput.value = '';
};
function addQImageThumb(url) {
    const wrap = document.createElement('div');
    wrap.style.position = 'relative';
    const im = document.createElement('img');
    im.src = url; im.style.width = '100%'; im.style.height = '90px';
    im.style.objectFit = 'cover'; im.style.borderRadius = '8px'; im.style.border = '1px solid #2a303b';
    const del = document.createElement('button');
    del.className = 'btn tiny ghost'; del.textContent = '✕';
    del.style.position = 'absolute'; del.style.top = '6px'; del.style.right = '6px';
    del.onclick = () => {
        const q = currentQ();
        q.images = (q.images || []).filter(s => s !== url);
        wrap.remove(); updatePreview(); autosave();
    };
    wrap.appendChild(im); wrap.appendChild(del);
    qImgGrid.appendChild(wrap);
}

// --------- Options editor (1-4, text+image) ---------
function renderOptionsEditor(q) {
    optWrap.innerHTML = '';
    const opts = q.options || [];
    opts.forEach((opt, i) => optWrap.appendChild(makeOptRow(q, i)));
}

function makeOptRow(q, i) {
    const opt = q.options[i] || { text: '' };

    const row = document.createElement('div');
    row.className = 'optrow';

    const top = document.createElement('div');
    top.className = 'row2';
    top.innerHTML = `
    <label>Text
      <input class="optText" placeholder="Option ${i + 1}" value="${escapeHtml(opt.text || '')}" />
    </label>
    <div class="opt-tools">
      <img class="thumb" src="${opt.image ? escapeHtml(opt.image) : ''}" alt="" />
      <input class="optFile" type="file" accept="image/*" hidden />
      <button class="btn tiny" data-act="upload">Upload</button>
      <button class="btn tiny ghost" data-act="clear">Clear</button>
    </div>
  `;
    row.appendChild(top);

    const optText = top.querySelector('.optText');
    const thumb = top.querySelector('.thumb');
    const optFile = top.querySelector('.optFile');
    const uploadBtn = top.querySelector('[data-act="upload"]');
    const clearBtn = top.querySelector('[data-act="clear"]');

    uploadBtn.onclick = () => optFile.click();
    optFile.onchange = async (e) => {
        const file = e.target.files[0]; if (!file) return;
        const url = await uploadImage(file); if (!url) return;
        q.options[i] = { ...q.options[i], image: url };
        thumb.src = url;
        updatePreview(); autosave();
    };
    clearBtn.onclick = () => {
        if (q.options[i]) q.options[i].image = ""; // clear image from data
        thumb.src = "";
        optFile.value = "";
        updatePreview();
        autosave();
    };


    optText.addEventListener('input', () => {
        q.options[i] = { ...(q.options[i] || {}), text: optText.value };
        updatePreview(); autosaveDebounced();
    });

    return row;
}

addOptBtn.onclick = () => {
    const q = currentQ(); if (!q || q.type !== 'mcq') return;
    q.options = q.options || [];
    if (q.options.length >= 4) return;
    q.options.push({ text: '' });
    renderOptionsEditor(q); updatePreview(); autosave();
};
remOptBtn.onclick = () => {
    const q = currentQ(); if (!q || q.type !== 'mcq') return;
    if ((q.options?.length || 0) <= 1) return;
    q.options.pop();
    if (q.correctIndex >= q.options.length) q.correctIndex = q.options.length - 1;
    renderOptionsEditor(q); updatePreview(); autosave();
};

correctIdx.addEventListener('change', () => {
    const q = currentQ(); if (!q) return;
    q.correctIndex = parseInt(correctIdx.value, 10) || 0;
    updatePreview(); autosave();
});

// Single answer bindings
singleAnswer.addEventListener('input', () => {
    const q = currentQ(); if (!q) return;
    q.answer = singleAnswer.value;
    updatePreview(); autosaveDebounced();
});

// Editor Apply / Duplicate / Delete
applyBtn.onclick = () => {
    const q = currentQ(); if (!q) return;
    q.type = qType.value;
    q.difficulty = qDiff.value;
    q.timerSec = parseInt(qTimer.value || state.quiz.defaults.timerSec, 10);
    q.text = (qText.value || '').trim();
    q.explanation = (qExplain.value || '').trim();

    if (q.type === 'mcq') {
        q.options = Array.from(optWrap.querySelectorAll('.optrow')).map((row, k) => {
            const text = el('.optText', row).value || '';
            const imgEl = el('.thumb', row);
            let image = imgEl?.src?.trim();
            if (!image || image.startsWith("data:") || image === window.location.href) image = "";
            return image ? { text, image } : { text };

        });
    } else {
        delete q.options; delete q.correctIndex;
    }
    renderQList(); updatePreview(); autosave();
};

dupBtn.onclick = () => {
    const q = currentQ(); if (!q) return;
    const copy = JSON.parse(JSON.stringify(q));
    copy.id = `q${Date.now()}`;
    state.quiz.questions.splice(state.selIndex + 1, 0, copy);
    state.selIndex++;
    renderQList(); openEditor(state.selIndex); autosave();
};

delBtn.onclick = () => {
    if (state.selIndex < 0) return;
    state.quiz.questions.splice(state.selIndex, 1);
    state.selIndex = Math.min(state.selIndex, state.quiz.questions.length - 1);
    renderQList(); if (state.selIndex >= 0) openEditor(state.selIndex); else { hide(qEditor); show(noSel); }
    updatePreview(); autosave();
};

// --------- Upload helper ---------
async function uploadImage(file) {
    try {
        const form = new FormData();
        form.append('file', file);
        form.append('type', 'images');
        const res = await fetch('/quiz/api/upload', { method: 'POST', body: form });
        const data = await res.json();
        if (data?.url) return safeUrl(data.url);
    } catch (e) { console.warn('Upload failed', e); }
    return null;
}

// --------- Preview ---------
function updatePreview() {
    const q = currentQ();
    // theme
    applyThemeToPreview();

    // orientation and theme mode
    pv.preview.classList.toggle('portrait', document.body.classList.contains('portrait'));
    pv.preview.classList.remove('fade-in', 'fade-out');
    if (state.animatePreview) { pv.card.classList.remove('fade-in'); pv.card.classList.add('fade-out'); }

    const qAnimType = state.quiz.theme.animations?.question || 'fade';
    pv.q.className = `question anim-${qAnimType}`;

    // pv.q.className = `question anim-${state.quiz.theme.animations?.question || 'fade'}`;
    pv.opts.classList.add(`anim-${state.quiz.theme.animations?.options || 'fade'}`);

    // Apply idle motion (breathing / shake / float)
    const idleType = state.quiz.theme.animations?.idle || 'none';
    const intensity = state.quiz.theme.animations?.idleIntensity || 3;

    const doEntrance = !loopIdleOnly.checked && state.animatePreview;
    if (doEntrance){ pv.card.classList.remove('fade-out'); pv.card.classList.add('fade-in'); }

    const seconds = Number((q && q.timerSec) || state.quiz.defaults?.timerSec || 12);
    startTimerPreview(seconds);

    // Remove previous idle classes
    pv.q.classList.remove('idle-breath', 'idle-shake', 'idle-float');
    pv.opts.classList.remove('idle-breath', 'idle-shake', 'idle-float');
    // pv.imgs.classList.remove('idle-breath', 'idle-shake', 'idle-float');
    // pv.imgs.classList.remove('anim-fade', 'anim-slide', 'anim-zoom');

        //     pv.imgs.querySelectorAll('img').forEach(im => {
        // im.classList.remove('idle-breath', 'idle-shake', 'idle-float');
        // im.classList.remove('anim-fade', 'anim-slide', 'anim-zoom');
        // });

    if (idleType !== 'none') {
        pv.q.classList.add(`idle-${idleType}`);
        pv.q.style.animationDuration = `${6 / (intensity / 3)}s`;
        pv.opts.classList.add(`idle-${idleType}`);
        pv.opts.style.animationDuration = `${6 / (intensity / 3)}s`;

        pv.imgs.querySelectorAll('img').forEach(im => {
        im.classList.add('anim-fade', `idle-${idleType}`);
        im.style.animationDuration = `${6 / (intensity / 3)}s`;
        });
        // pv.imgs.style.animationDuration = `${6 / (intensity / 3)}s`;

    } else {
        pv.q.style.animationDuration = '';
        pv.opts.style.animationDuration = '';
        // pv.imgs.style.animationDuration = '';
                pv.imgs.querySelectorAll('img').forEach(im => {

        im.style.animationDuration = '';
        });
    }


    setTimeout(() => {
        // content
        if (!q) {
            pv.count.textContent = 'Q 0/0';
            pvQuestionHd.textContent = 'Add a question to preview…';
            pv.q.textContent = '';               // we don’t show question in card

            pv.imgs.innerHTML = '';
            pv.opts.innerHTML = '';
            pv.expl.classList.add('hidden'); pv.expl.textContent = '';
        } else {
            pv.count.textContent = `Q ${state.selIndex + 1}/${state.quiz.questions.length}`;
            pvQuestionHd.textContent = q.text || '(question)';
            pv.q.textContent = '';
            pv.imgs.innerHTML = '';
            (q.images || []).forEach(src => {
                const im = document.createElement('img');
                im.className = 'qImg'; 
                // entrance + idle motion per image
                im.classList.add('anim-fade');
                if (idleType !== 'none') {
                    im.classList.add(`idle-${idleType}`);
                    im.style.animationDuration = `${6 / (intensity / 3)}s`;
                } else {
                    im.style.animationDuration = '';
                }                
                im.src = src; 
                pv.imgs.appendChild(im);
            });
            pv.diff.textContent = (q.difficulty || 'easy').toUpperCase();

            pv.count.style.display = showQNum && !showQNum.checked ? 'none' : '';
            pv.diff.style.display = showDiff && !showDiff.checked ? 'none' : '';

            // options grid
            pv.opts.innerHTML = '';
            if (q.type === 'mcq') {
                // keep animation/idle classes by not wiping className completely
                const count = Math.min((q.options || []).length || 1, 4);
                pv.opts.classList.remove('cols-1', 'cols-2', 'cols-3', 'cols-4');
                pv.opts.classList.add(`cols-${count}`);

                const animType = state.quiz.theme.animations?.options || 'fade';
                const doStagger = !!state.quiz.theme.animations?.stagger;
                const step = Number(state.quiz.theme.animations?.staggerStep || 0.10);

                // idle settings
                const idleType = state.quiz.theme.animations?.idle || 'none';
                const intensity = state.quiz.theme.animations?.idleIntensity || 3;
                const idleClass = (idleType !== 'none') ? `idle-${idleType}` : '';

                (q.options || []).forEach((opt, i) => {
                    const b = document.createElement('div');
                    // add both entrance animation and idle class on EACH option
                    b.className = `opt anim-${animType}` + (idleClass ? ` ${idleClass}` : '');
                    if (doStagger) b.style.animationDelay = `${i * step}s`;
                    if (idleClass) b.style.animationDuration = `${6 / (intensity / 3)}s`;

                    if (opt.image) {
                        const d = document.createElement('div'); d.className = 'opt-img';
                        const im = document.createElement('img'); im.src = (opt.image || '').trim();
                        d.appendChild(im); b.appendChild(d);
                    }
                    const t = document.createElement('div'); t.className = 'opt-text';
                    t.textContent = (opt.text || '').trim() || '(option)';
                    b.appendChild(t);
                    pv.opts.appendChild(b);
                });

                // also keep container-level animation class (for a subtle “group” pop)
                pv.opts.classList.remove('anim-fade', 'anim-slide', 'anim-zoom');
                pv.opts.classList.add(`anim-${animType}`);

                // and keep container-level idle (optional)
                pv.opts.classList.remove('idle-breath', 'idle-shake', 'idle-float');
                if (idleClass) {
                    pv.opts.classList.add(idleClass);
                    pv.opts.style.animationDuration = `${6 / (intensity / 3)}s`;
                } else {
                    pv.opts.style.animationDuration = '';
                }
            } else {
                const div = document.createElement('div'); div.style.opacity = .85;
                div.textContent = q.answer ? 'Answer will be revealed: ' + q.answer : 'Answer will be revealed at end of timer';
                pv.opts.appendChild(div);

                pv.opts.classList.remove('cols-1', 'cols-2', 'cols-3', 'cols-4');
                pv.opts.classList.add('cols-1');
                pv.opts.classList.remove('anim-fade', 'anim-slide', 'anim-zoom', 'idle-breath', 'idle-shake', 'idle-float');
                pv.opts.style.animationDuration = '';
            }

            // explanation
            if (q.explanation) { pv.expl.classList.remove('hidden'); pv.expl.textContent = q.explanation; }
            else { pv.expl.classList.add('hidden'); pv.expl.textContent = ''; }
        }

        if (state.animatePreview) { pv.card.classList.remove('fade-out'); pv.card.classList.add('fade-in'); }
    }, state.animatePreview ? 180 : 0);
}

// Preview toolbar
pv.landBtn.onclick = () => { document.body.classList.remove('portrait'); updatePreview(); };
pv.portBtn.onclick = () => { document.body.classList.add('portrait'); updatePreview(); };

showQNum && (showQNum.onchange = updatePreview);
showDiff && (showDiff.onchange = updatePreview);


pv.animToggle.onchange = () => { state.animatePreview = pv.animToggle.checked; };
pv.themeMode.onchange = () => {
    const m = pv.themeMode.value;
    document.body.classList.toggle('light', m === 'light');
    updatePreview();
};

// --------- IO (Load/Save/Play) ---------
loadJsonBtn.onclick = () => loadJsonInput.click();
loadJsonInput.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const txt = await file.text(); const qz = JSON.parse(txt);
    state.quiz = normalizeQuiz(qz);
    state.selIndex = state.quiz.questions.length ? 0 : -1;
    hydrateMeta(); renderQList(); if (state.selIndex >= 0) openEditor(state.selIndex); updatePreview(); autosave();
};

saveBtn.onclick = async () => {
    refreshMeta();
    try {
        const res = await fetch('/quiz/api/quizzes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state.quiz)
        });
        const data = await res.json();
        if (data?.id) { state.quiz.id = data.id; alert('Saved: ' + data.id); autosave(); }
        else alert('Save failed');
    } catch (e) { alert('Save failed'); }
};

playBtn.onclick = () => {
    if (!state.quiz.id) { alert('Please save first.'); return; }
    location.href = `/quiz/play?id=${state.quiz.id}`;
};

// --------- Meta hydrate / normalize ---------
function hydrateMeta() {
    const qz = state.quiz;
    quizTitle.value = qz.title || '';
    quizLang.value = qz.language || 'en';
    qsTTS.value = qz.qsTTS || 'y';
    defaultTimer.value = qz.defaults?.timerSec || 12;

    themePreset.value = qz.theme?.preset || 'Neon Quiz';
    colorPrimary.value = qz.theme?.primary || '#00E5FF';
    colorAccent.value = qz.theme?.accent || '#FF3D7F';
    fontFamily.value = qz.theme?.fontFamily || 'Poppins, sans-serif';
    timerStyle.value = qz.theme?.timerStyle || 'ring';
    bgSrc.value = qz.theme?.background?.src || '';
    musicSrc.value = qz.theme?.music?.src || '';
    musicVol.value = qz.theme?.music?.volume ?? 0.35;
    overlayColor.value = qz.theme?.background?.overlay?.color || '#000000';
    overlayOpacity.value = qz.theme?.background?.overlay?.opacity ?? 0.45;
    qAnim.value = state.quiz.theme?.animations?.question || 'fade';
    optAnim.value = state.quiz.theme?.animations?.options || 'fade';
    optStagger.checked = !!state.quiz.theme?.animations?.stagger;
    optStaggerStep.value = state.quiz.theme?.animations?.staggerStep ?? 0.10;
    idleMotion.value = qz.theme?.animations?.idle || 'none';
    idleIntensity.value = qz.theme?.animations?.idleIntensity ?? 3;


    duckOnReveal.checked = !!qz.theme?.music?.duckOnReveal;

    applyThemeToPreview();
    updateFontPreview();
    hydrateQuestionEditor();
}

function normalizeQuiz(q) {
    q.defaults = q.defaults || { timerSec: 12 };
    q.theme = q.theme || {};
    q.theme.background = q.theme.background || { type: 'video', src: '', intensity: 0.6, overlay: { color: '#000000', opacity: 0.45 } };
    q.theme.music = q.theme.music || { src: '', volume: 0.35, duckOnReveal: true };

    q.theme.animations = q.theme.animations || {};
    q.theme.animations.question = q.theme.animations.question || 'fade';
    q.theme.animations.options = q.theme.animations.options || 'fade';
    q.theme.animations.stagger = (typeof q.theme.animations.stagger === 'boolean') ? q.theme.animations.stagger : true;
    q.theme.animations.staggerStep = (typeof q.theme.animations.staggerStep === 'number') ? q.theme.animations.staggerStep : 0.10;

    q.theme.animations.idle = q.theme.animations.idle || 'none';
    q.theme.animations.idleIntensity = q.theme.animations.idleIntensity || 3;


    q.questions = q.questions || [];
    q.questions.forEach(qq => {
        qq.images = qq.images || [];
        if (qq.type === 'mcq') {
            qq.options = (qq.options || []).map(o => {
                if (typeof o === 'string') return { text: o };
                if (o && typeof o === 'object') return { text: o.text || '', image: o.image || undefined };
                return { text: '' };
            });
            if (qq.options.length === 0) qq.options = [{ text: '' }, { text: '' }];
            if (typeof qq.correctIndex !== 'number') qq.correctIndex = 0;
        } else {
            qq.answer = qq.answer || '';
            delete qq.options; delete qq.correctIndex;
        }
        qq.timerSec = qq.timerSec || q.defaults.timerSec;
        qq.difficulty = qq.difficulty || 'easy';
    });
    return q;
}

// --------- Autosave (localStorage) ---------
const autosaveDebounced = debounce(autosave, 500);
function autosave() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(state.quiz)); } catch (e) { }
}

// Restore from localStorage or ?id=...
(function restore() {
    const params = new URLSearchParams(location.search);
    const existingId = params.get('id');

    if (existingId) {
        fetch(`/quiz/api/quizzes/${existingId}`).then(r => r.ok ? r.json() : null).then(qz => {
            if (!qz) return;
            state.quiz = normalizeQuiz(qz);
            state.selIndex = state.quiz.questions.length ? 0 : -1;
            hydrateMeta(); renderQList(); if (state.selIndex >= 0) openEditor(state.selIndex); updatePreview();
        }).catch(() => { });
        return;
    }

    const raw = localStorage.getItem(LS_KEY);
    if (raw) {
        try {
            const qz = JSON.parse(raw);
            state.quiz = normalizeQuiz(qz);
            state.selIndex = state.quiz.questions.length ? 0 : -1;
            hydrateMeta(); renderQList(); if (state.selIndex >= 0) openEditor(state.selIndex); updatePreview();
        } catch (e) { }
    } else {
        hydrateMeta(); renderQList(); updatePreview();
    }
})();

// --------- New Quiz ---------
const newQuizBtn = document.getElementById("newQuizBtn");
newQuizBtn.onclick = () => {
    if (!confirm("Start a new blank quiz? Unsaved changes will be lost.")) return;

    // clear localStorage & reset everything
    localStorage.removeItem(LS_KEY);

    //state.quiz.theme

    state.quiz = {
        id: null,
        title: "",
        language: "en",
        qsTTS: "y",
        theme: {
            preset: "Neon Quiz",
            primary: "#00E5FF",
            accent: "#FF3D7F",
            bg: "#0B0B0B",
            fontFamily: "Poppins, sans-serif",
            timerStyle: "ring",
            background: { type: "video", src: "/quiz/static/backgrounds/A.mp4", intensity: 0.6, overlay: { color: "#000000", opacity: 0.45 } },
            music: { src: "/quiz/uploads/music/A.mp3", volume: 0.35, duckOnReveal: true },
            animations: { question: 'fade', options: 'fade', stagger: true, staggerStep: 0.10, idle: 'none', idleIntensity: 3 },
        },
        defaults: { timerSec: 12 },
        questions: []
    };

    state.selIndex = -1;
    hydrateMeta();
    renderQList();
    hide(qEditor);
    show(noSel);
    updatePreview();
};

function hexToRgba(hex, a) {
    // default color if missing
    let h = (hex || '#000000').trim();

    // expand #rgb to #rrggbb
    if (/^#?[a-f0-9]{3}$/i.test(h)) {
        h = '#' + h.replace(/^#?/, '').split('').map(c => c + c).join('');
    }

    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(h);
    let r = 0, g = 0, b = 0;
    if (m) {
        r = parseInt(m[1], 16);
        g = parseInt(m[2], 16);
        b = parseInt(m[3], 16);
    }
    const alpha = Number.isFinite(a) ? Math.max(0, Math.min(1, a)) : 0.45;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}




// --------- Init theme preview once ---------
applyThemeToPreview();
updatePreview();
