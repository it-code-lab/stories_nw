const editor = document.getElementById("editor");
const timelineDiv = document.getElementById("timeline");
const mediaPick = document.getElementById("mediaPick");
const btnLoad = document.getElementById("btnLoad");
const btnAddMedia = document.getElementById("btnAddMedia");
const btnSave = document.getElementById("btnSave");
const btnRender = document.getElementById("btnRender");
const outRes = document.getElementById("outRes");
const heygenFile = document.getElementById("heygenFile");

let wordTimestamps = [];
let lastSelectedWordIndex = 0;

function setCaretAfterNode(node) {
  const range = document.createRange();
  const sel = window.getSelection();
  range.setStartAfter(node);
  range.collapse(true);
  sel.removeAllRanges();
  sel.addRange(range);
}

function clearWordSelection() {
  editor.querySelectorAll(".word.sel").forEach(el => el.classList.remove("sel"));
}

function renderWords() {
  editor.innerHTML = "";
  clearWordSelection();

  wordTimestamps.forEach((w, i) => {
    const span = document.createElement("span");
    span.className = "word";
    span.textContent = w.word;   // note: your JSON words may include leading spaces
    span.dataset.i = i;
    span.dataset.start = w.start;
    span.dataset.end = w.end;

    span.addEventListener("click", () => {
      clearWordSelection();
      span.classList.add("sel");
      lastSelectedWordIndex = i;
      setCaretAfterNode(span);
    });

    editor.appendChild(span);
  });

  // Put caret at the end initially
  if (editor.lastChild) setCaretAfterNode(editor.lastChild);
}

async function loadWordTimestamps() {
  const res = await fetch("/get_word_timestamps");
  wordTimestamps = await res.json();
  renderWords();
  refreshTimelinePreview();
}

// ---- Insert HTML at caret (based on your insertContentAtCaret pattern) ----
function insertHTMLAtCaret(html) {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;

  const range = sel.getRangeAt(0);

  // Ensure caret is inside editor
  let p = range.commonAncestorContainer;
  let inside = false;
  while (p) {
    if (p === editor) { inside = true; break; }
    p = p.parentNode;
  }
  if (!inside) {
    alert("Click inside the editor first.");
    return;
  }

  range.deleteContents();
  const el = document.createElement("div");
  el.innerHTML = html;

  const frag = document.createDocumentFragment();
  let lastNode = null;
  while (el.firstChild) lastNode = frag.appendChild(el.firstChild);

  range.insertNode(frag);
  if (lastNode) setCaretAfterNode(lastNode);
}

function getNearestWordTimeBeforeCaret() {
  // Best-effort: use last clicked word index
  const w = wordTimestamps[lastSelectedWordIndex] || wordTimestamps[0];
  return w ? Number(w.start) : 0.0;
}

async function uploadFileToServer(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/upload_media", { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return await res.json(); // {url, type}
}

async function insertMediaFiles(files) {
  for (const f of files) {
    const up = await uploadFileToServer(f);
    const t = getNearestWordTimeBeforeCaret();

    if (up.type === "image") {
      insertHTMLAtCaret(`
        <span class="media-block" contenteditable="false"
              data-type="image" data-src="${up.url}" data-start="${t}">
          <img src="${up.url}" class="movieImageCls" />
        </span>
      `);
    } else {
      insertHTMLAtCaret(`
        <span class="media-block" contenteditable="false"
              data-type="video" data-src="${up.url}" data-start="${t}">
          <video src="${up.url}" class="movieVideoCls" controls></video>
        </span>
      `);
    }
    insertHTMLAtCaret(`<span> </span>`);
  }
  refreshTimelinePreview();
}

btnAddMedia.addEventListener("click", () => mediaPick.click());
mediaPick.addEventListener("change", async () => {
  const files = Array.from(mediaPick.files || []);
  if (files.length) await insertMediaFiles(files);
  mediaPick.value = "";
});

// Paste handler (supports clipboard images)
editor.addEventListener("paste", async (e) => {
  const items = e.clipboardData?.items || [];
  const files = [];
  for (const it of items) {
    if (it.kind === "file") {
      const file = it.getAsFile();
      if (file && (file.type.startsWith("image/") || file.type.startsWith("video/"))) {
        files.push(file);
      }
    }
  }
  if (files.length) {
    e.preventDefault();
    await insertMediaFiles(files);
  }
});

function buildTimelineFromEditor() {
  const mediaNodes = Array.from(editor.querySelectorAll(".media-block"));
  const lastEnd = Number(wordTimestamps[wordTimestamps.length - 1]?.end || 0);

  const blocks = mediaNodes.map((n) => ({
    type: n.dataset.type,
    src: n.dataset.src,
    start: Number(n.dataset.start || 0),
    end: null,   // fill below
  })).sort((a,b) => a.start - b.start);

  for (let i = 0; i < blocks.length; i++) {
    const nextStart = blocks[i + 1]?.start;
    blocks[i].end = (nextStart != null) ? nextStart : lastEnd;
  }

  return { duration: lastEnd, blocks };
}

function refreshTimelinePreview() {
  const tl = buildTimelineFromEditor();
  timelineDiv.innerHTML = "";

  tl.blocks.forEach((b, idx) => {
    const div = document.createElement("div");
    div.className = "tline-item";
    div.innerHTML = `
      <div><b>${idx+1}. ${b.type.toUpperCase()}</b></div>
      <div class="small">${b.src}</div>
      <div style="margin-top:8px;">
        Start: <input value="${b.start.toFixed(2)}" data-idx="${idx}" data-field="start"/>
        End: <input value="${b.end.toFixed(2)}" data-idx="${idx}" data-field="end"/>
        <button data-del="${idx}" style="margin-left:8px;">Remove</button>
      </div>
    `;
    timelineDiv.appendChild(div);
  });

  // Simple editing of start/end
  timelineDiv.querySelectorAll("input").forEach(inp => {
    inp.addEventListener("change", () => {
      const tl2 = buildTimelineFromEditor();
      // For MVP we don’t rewrite DOM times from here (we keep editor as truth).
      // Next step: apply edited times back to data-start on media blocks.
      alert("MVP note: timeline inputs are preview only. Next step: apply changes back to editor nodes.");
    });
  });

  // Remove button (removes media node by index in DOM order)
  timelineDiv.querySelectorAll("button[data-del]").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.del);
      const nodes = Array.from(editor.querySelectorAll(".media-block"));
      if (nodes[idx]) nodes[idx].remove();
      refreshTimelinePreview();
    });
  });
}

btnLoad.addEventListener("click", loadWordTimestamps);
btnSave.addEventListener("click", async () => {
  const tl = buildTimelineFromEditor();
  const res = await fetch("/save_timeline", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ ...tl, outRes: outRes.value })
  });
  alert(await res.text());
});

btnRender.addEventListener("click", async () => {
  if (!heygenFile.files?.[0]) return alert("Choose HeyGen video first.");
  const fd = new FormData();
  fd.append("heygen", heygenFile.files[0]);
  fd.append("outRes", outRes.value);

  const res = await fetch("/render", { method: "POST", body: fd });
  const j = await res.json();
  if (!res.ok) return alert(j.error || "Render failed");
  alert("Done:\n" + j.output);
});

btnLoad.click();
