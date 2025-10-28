// Enhanced Quiz Player for OBS + YouTube quiz videos

const els = {
  bgVideo: document.getElementById('bgVideo'),
  bgImage: document.getElementById('bgImage'),
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
  prevBtn: document.getElementById('prevBtn'),
  nextBtn: document.getElementById('nextBtn'),
  restartBtn: document.getElementById('restartBtn'),
  expl: document.getElementById('explanation'),
  fsBtn: document.getElementById('fsBtn'),
  landBtn: document.getElementById('landBtn'),
  portBtn: document.getElementById('portBtn')
};

let quiz=null, idx=0, cancelTimer=null, revealed=false;

// ---------- Initialization ----------
init();
async function init(){
  const id = new URLSearchParams(location.search).get('id');
  if(!id){ setStatus('Missing quiz id (?id=...)'); return; }

  try{
    const res = await fetch(`/quiz/api/quizzes/${id}`);
    quiz = await res.json();
  }catch(e){ console.error(e); setStatus('Load failed'); return; }

  hydrateTheme();
  goTo(0);
  bindControls();
}

function setStatus(msg){ if(els.qText) els.qText.textContent = msg; }

// ---------- Theme ----------
function hydrateTheme(){
  const t = quiz.theme||{};
  setCSS('--primary', t.primary||'#00E5FF');
  setCSS('--accent',  t.accent||'#FF3D7F');
  document.body.style.fontFamily = t.fontFamily||'Poppins, sans-serif';

  // background
  const bg = t.background||{};
  if(bg.src){
    if(/\.(mp4|webm|mov)$/i.test(bg.src)){
      els.bgVideo.src=bg.src; els.bgVideo.classList.add('show');
    }else{
      els.bgImage.src=bg.src; els.bgImage.classList.add('show');
    }
  }

  // music
  if(t.music?.src){
    els.bgMusic.src = t.music.src;
    els.bgMusic.volume = clamp01(t.music.volume??0.35);
    els.bgMusic.play().catch(()=>{});
  }

  // timer style
  const style = (t.timerStyle||'ring').toLowerCase();
  if(style==='bar'){ hide(els.ringWrap); show(els.barWrap); }
  else{ show(els.ringWrap); hide(els.barWrap); }

  els.title.textContent = quiz.title||'';
}
function setCSS(k,v){ document.documentElement.style.setProperty(k,v); }
function clamp01(x){ return Math.max(0,Math.min(1,x)); }

// ---------- Navigation ----------
function goTo(n){
  idx=Math.max(0,Math.min(n,quiz.questions.length-1));
  revealed=false;

  els.card.classList.remove('fade-in');
  els.card.classList.add('fade-out');

  setTimeout(()=>{
    renderQuestion(quiz.questions[idx]);
    els.card.classList.remove('fade-out');
    els.card.classList.add('fade-in');
  },250);
}
function next(){ if(idx<quiz.questions.length-1) goTo(idx+1); }
function prev(){ if(idx>0) goTo(idx-1); }
function restart(){ goTo(idx); }

// ---------- Render ----------
function renderQuestion(q){
  els.counter.textContent = `Q ${idx+1}/${quiz.questions.length}`;
  els.diff.textContent = (q.difficulty||'').toUpperCase();
  els.qText.textContent = q.text||'';
  els.expl.classList.add('hidden');
  els.expl.textContent = q.explanation||'';
  renderImages(q.images||[]);
  renderOptions(q);
  startTimer(q);
}

function renderImages(arr){
  els.imgs.innerHTML='';
  arr.forEach(src=>{
    const im=document.createElement('img');
    im.src=src; els.imgs.appendChild(im);
  });
}

function renderOptions(q){
  els.opts.innerHTML='';
  const opts=q.options||[];
  const count=Math.min(opts.length||1,4);
  els.opts.className=`options cols-${count}`;

  if(q.type==='mcq'){
    opts.forEach((opt,i)=>{
      const b=document.createElement('button');
      b.className='opt';
      // image + text
      if(opt.image){
        const div=document.createElement('div');
        div.className='opt-img';
        const im=document.createElement('img');
        im.src=opt.image; div.appendChild(im);
        b.appendChild(div);
      }
      if(opt.text||typeof opt==='string'){
        const txt=document.createElement('div');
        txt.className='opt-text';
        txt.textContent=opt.text||opt;
        b.appendChild(txt);
      }
      b.dataset.idx=i;
      els.opts.appendChild(b);
    });
  }else{
    const info=document.createElement('div');
    info.style.opacity=.8;
    info.textContent='Answer will be revealed at end of timer';
    els.opts.appendChild(info);
  }
}

// ---------- Timer ----------
function startTimer(q){
  cancelTimer?.();
  const total=Number(q.timerSec||quiz.defaults?.timerSec||10);
  const useBar=(quiz.theme?.timerStyle||'ring').toLowerCase()==='bar';
  show(useBar?els.barWrap:els.ringWrap);
  hide(useBar?els.ringWrap:els.barWrap);
  if(useBar){setBar(1);els.timeNumB.textContent=total;}
  else{setRing(100);els.timeNum.textContent=total;}

  let t=total;
  const iv=setInterval(()=>{
    t--;
    if(t<0){clearInterval(iv);reveal(q);return;}
    if(useBar){setBar(Math.max(0,t/total));els.timeNumB.textContent=t;}
    else{setRing((t/total)*100);els.timeNum.textContent=t;}
  },1000);
  cancelTimer=()=>clearInterval(iv);
}
function setRing(p){els.ringBar.setAttribute('stroke-dasharray',`${p},100`);}
function setBar(scale){els.barFill.style.transform=`scaleX(${scale})`;}

// ---------- Reveal ----------
function reveal(q){
  if(revealed) return; revealed=true;
  if(q.type==='mcq'){
    [...els.opts.querySelectorAll('.opt')].forEach((b,i)=>{
      if(i===(q.correctIndex??0)) b.classList.add('correct');
      else b.classList.add('dim');
    });
  }else{
    const ans=(q.answer||'').trim();
    if(ans){
      const r=document.createElement('div');
      r.className='opt correct';
      r.textContent=`Answer: ${ans}`;
      els.opts.appendChild(r);
    }
  }
  if(q.explanation) els.expl.classList.remove('hidden');
}

// ---------- Controls ----------
function bindControls(){
  els.nextBtn.onclick=()=>next();
  els.prevBtn.onclick=()=>prev();
  els.restartBtn.onclick=()=>restart();
  els.fsBtn.onclick=()=>toggleFullscreen();
  els.landBtn.onclick=()=>setLandscape();
  els.portBtn.onclick=()=>setPortrait();
  window.addEventListener('keydown',e=>{
    const k=e.key.toLowerCase();
    if(k===' '||k==='enter'){e.preventDefault();next();}
    else if(k==='backspace'){e.preventDefault();prev();}
    else if(k==='r'){restart();}
    else if(k==='f'){toggleFullscreen();}
    else if(k==='t'){toggleOrientation();}
  });
}

function toggleFullscreen(){
  if(!document.fullscreenElement) document.documentElement.requestFullscreen?.();
  else document.exitFullscreen?.();
}
function setLandscape(){document.body.classList.remove('portrait');}
function setPortrait(){document.body.classList.add('portrait');}
function toggleOrientation(){document.body.classList.toggle('portrait');}

// ---------- Utils ----------
function show(el){el?.classList.remove('hidden');}
function hide(el){el?.classList.add('hidden');}
