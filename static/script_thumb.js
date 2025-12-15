/* FINAL: Thumbnail & Pinterest Post Maker (BG Crop Mode)
 * - Background Crop box with drag + resize handles (aspect locked to canvas format)
 * - Text/Image layers drag+resize
 * - Export downloads canvas (bg + overlays) at target size
 */

const $ = (id) => document.getElementById(id);

const canvas = $("canvas");
const ctx = canvas.getContext("2d");

const formats = {
  youtube_16_9: { w: 1280, h: 720, safe: { x: 0.06, y: 0.08, w: 0.88, h: 0.84 } },
  pinterest_2_3: { w: 1000, h: 1500, safe: { x: 0.06, y: 0.06, w: 0.88, h: 0.88 } },
  story_9_16: { w: 1080, h: 1920, safe: { x: 0.06, y: 0.06, w: 0.88, h: 0.88 } },
};

const state = {
  formatKey: "youtube_16_9",
  bgMode: "crop", // crop | cover | contain | contain_blur
  bgDim: 0.15,
  bgImage: null,
  bgImageSrc: "",

  // Crop rectangle in SOURCE IMAGE pixel coordinates (sx,sy,sw,sh)
  bgCrop: null, // { sx, sy, sw, sh }
  showCropOverlay: false, // NEW: toggle crop UI visibility

  layers: [],
  selectedLayerId: null,

  dragging: null, // for layer move/resize
  bgDragging: null, // for background crop move/resize
  dpiScale: 1,
  bgType: "none",     // "none" | "image" | "video"
  bgVideoEl: null,
  bgVideoSrc: "",
  bgVideoReady: false,

};

let videoRAF = null;

function startVideoRenderLoop(){
  if (videoRAF) cancelAnimationFrame(videoRAF);

  const loop = () => {
    // Only animate when video background is active
    if (state.bgType === "video" && state.bgVideoReady) {
      render(); // edit mode
      videoRAF = requestAnimationFrame(loop);
    } else {
      videoRAF = null;
    }
  };
  loop();
}

function uid() { return Math.random().toString(16).slice(2) + Date.now().toString(16); }
function clamp(n, a, b) { return Math.max(a, Math.min(b, n)); }

function rgbaFromHex(hex, alpha = 1) {
  const h = hex.replace("#", "").trim();
  const full = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function setStatus(msg) { $("statusPill").textContent = msg; }

function pxBoxFromPct(boxPct) {
  const { w, h } = formats[state.formatKey];
  return { x: boxPct.x * w, y: boxPct.y * h, w: boxPct.w * w, h: boxPct.h * h };
}
function pctBoxFromPx(boxPx) {
  const { w, h } = formats[state.formatKey];
  return { x: boxPx.x / w, y: boxPx.y / h, w: boxPx.w / w, h: boxPx.h / h };
}

async function loadImageFromBlob(blob) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = URL.createObjectURL(blob);
  });
}

function getCanvasWH() {
  const f = formats[state.formatKey];
  return { W: f.w, H: f.h };
}


function getBgWH() {
  if (!state.bgImage) return { iw: 0, ih: 0 };
  const iw = state.bgImage.naturalWidth || state.bgImage.width;
  const ih = state.bgImage.naturalHeight || state.bgImage.height;
  return { iw, ih };
}

function getCanvasAspect() {
  const { W, H } = getCanvasWH();
  return W / H;
}

// -------------------- Layers --------------------
function makeTextLayer({ name = "Text", text = "YOUR HOOK", box = null } = {}) {
  return {
    id: uid(),
    type: "text",
    name,
    visible: true,
    box: box ?? { x: 0.10, y: 0.12, w: 0.80, h: 0.28 },
    style: {
      fontFamily: "Bebas Neue",
      fontWeight: 900,
      fontSize: 110,
      autoFit: true,
      fill: "#ffffff",
      align: "center",
      uppercase: true,
      lineHeight: 1.05,

      strokeOn: true,
      strokeColor: "#000000",
      strokeWidth: 14,

      shadowOn: true,
      shadowColor: "#000000",
      shadowBlur: 18,
      shadowDx: 6,
      shadowDy: 6,

      boxOn: false,
      boxColor: "#000000",
      boxOpacity: 0.35,
      boxPad: 18,
      boxRadius: 24,
    },
    text,
  };
}

function makeImageLayer({ name = "Logo", box = null } = {}) {
  return {
    id: uid(),
    type: "image",
    name,
    visible: true,
    box: box ?? { x: 0.78, y: 0.78, w: 0.18, h: 0.18 },
    img: null,
    imgSrc: "",
    fit: "contain",
    opacity: 1.0,
    shadow: false,
  };
}

// -------------------- Canvas sizing --------------------
function applyCanvasFormat() {
  const f = formats[state.formatKey];
  canvas.width = f.w * state.dpiScale;
  canvas.height = f.h * state.dpiScale;

  // Let CSS handle scaling (prevents "squeezing" on screen)
  canvas.style.width = "100%";
  canvas.style.height = "auto";

  ctx.setTransform(state.dpiScale, 0, 0, state.dpiScale, 0, 0);
}

// -------------------- Background crop init --------------------
// Create a centered crop box that matches canvas aspect ratio.
function initCenteredBgCrop() {
  if (!state.bgImage) { state.bgCrop = null; return; }
  const { iw, ih } = getBgWH();
  const ar = getCanvasAspect();

  // Start with the largest crop that fits inside the image with the same aspect ratio.
  let sw = iw;
  let sh = sw / ar;
  if (sh > ih) {
    sh = ih;
    sw = sh * ar;
  }

  const sx = (iw - sw) / 2;
  const sy = (ih - sh) / 2;

  state.bgCrop = { sx, sy, sw, sh };
}

// Reset crop to centered fit
function resetBgCrop() {
  initCenteredBgCrop();
  render();
  setStatus("Background crop reset");
}

// -------------------- Background rendering --------------------
function drawBackground() {
  const { W, H } = getCanvasWH();
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#0a1020";
  ctx.fillRect(0, 0, W, H);

  // if (!state.bgImage) return;

  if (state.bgType === "image" && state.bgImage) {
    ctx.fillStyle = "#0a1020";
    const img = state.bgImage;
    const { iw, ih } = getBgWH();

    if (state.bgMode === "crop" && state.bgCrop) {
      const { sx, sy, sw, sh } = state.bgCrop;
      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, W, H);
    } else if (state.bgMode === "cover") {
      const scale = Math.max(W / iw, H / ih);
      const dw = iw * scale, dh = ih * scale;
      ctx.drawImage(img, (W - dw) / 2, (H - dh) / 2, dw, dh);
    } else if (state.bgMode === "contain") {
      const scale = Math.min(W / iw, H / ih);
      const dw = iw * scale, dh = ih * scale;
      ctx.drawImage(img, (W - dw) / 2, (H - dh) / 2, dw, dh);
    } else { // contain_blur
      ctx.save();
      ctx.filter = "blur(22px) saturate(1.05)";
      const scaleC = Math.max(W / iw, H / ih);
      const dwC = iw * scaleC, dhC = ih * scaleC;
      ctx.drawImage(img, (W - dwC) / 2, (H - dhC) / 2, dwC, dhC);
      ctx.restore();

      const scale = Math.min(W / iw, H / ih);
      const dw = iw * scale, dh = ih * scale;
      ctx.drawImage(img, (W - dw) / 2, (H - dh) / 2, dw, dh);
    }

    if (state.bgDim > 0) {
      const g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, `rgba(0,0,0,${state.bgDim * 0.7})`);
      g.addColorStop(0.55, `rgba(0,0,0,${state.bgDim})`);
      g.addColorStop(1, `rgba(0,0,0,${state.bgDim * 0.85})`);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    }
  } else if (state.bgType === "video" && state.bgVideoReady) {
    const v = state.bgVideoEl;
    const iw = v.videoWidth;
    const ih = v.videoHeight;

    if (state.bgMode === "crop" && state.bgCrop) {
      const { sx, sy, sw, sh } = state.bgCrop;
      ctx.drawImage(v, sx, sy, sw, sh, 0, 0, W, H);
    } else if (state.bgMode === "cover") {
      const scale = Math.max(W / iw, H / ih);
      const dw = iw * scale, dh = ih * scale;
      ctx.drawImage(v, (W - dw) / 2, (H - dh) / 2, dw, dh);
    } else if (state.bgMode === "contain") {
      const scale = Math.min(W / iw, H / ih);
      const dw = iw * scale, dh = ih * scale;
      ctx.drawImage(v, (W - dw) / 2, (H - dh) / 2, dw, dh);
    } else {
      // contain_blur (optional): you can skip blur in live preview to keep it fast
      const scale = Math.min(W / iw, H / ih);
      const dw = iw * scale, dh = ih * scale;
      ctx.drawImage(v, (W - dw) / 2, (H - dh) / 2, dw, dh);
    }

    if (state.bgDim > 0) {
      const g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, `rgba(0,0,0,${state.bgDim * 0.7})`);
      g.addColorStop(0.55, `rgba(0,0,0,${state.bgDim})`);
      g.addColorStop(1, `rgba(0,0,0,${state.bgDim * 0.85})`);
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    }

  }
}

// -------------------- Text rendering --------------------
function buildFont(style, sizePx) {
  const weight = style.fontWeight ?? 800;
  const family = style.fontFamily ?? "Inter";
  return `${weight} ${sizePx}px "${family}"`;
}

function wrapTextToBox(text, style, boxPx, fontSize) {
  const maxWidth = Math.max(10, boxPx.w);
  const raw = (text ?? "").toString();
  const lines = [];

  const inputLines = raw.split("\n");
  for (const para of inputLines) {
    const words = para.split(/\s+/).filter(Boolean);
    if (words.length === 0) { lines.push(""); continue; }
    let line = words[0];
    for (let i = 1; i < words.length; i++) {
      const test = line + " " + words[i];
      const w = ctx.measureText(test).width;
      if (w <= maxWidth) line = test;
      else { lines.push(line); line = words[i]; }
    }
    lines.push(line);
  }

  const lh = (style.lineHeight ?? 1.05) * fontSize;
  return { lines, lineHeightPx: lh, heightPx: lines.length * lh };
}

function textFits(style, text, boxPx, sizePx) {
  ctx.font = buildFont(style, sizePx);
  return wrapTextToBox(text, style, boxPx, sizePx).heightPx <= boxPx.h;
}

function findBestFontSize(style, text, boxPx) {
  const start = clamp(parseInt(style.fontSize ?? 96, 10), 8, 260);
  if (textFits(style, text, boxPx, start)) return start;
  for (let s = start; s >= 10; s -= 2) {
    if (textFits(style, text, boxPx, s)) return s;
  }
  return 10;
}

function drawRoundedRect(x, y, w, h, r) {
  const rr = clamp(r, 0, Math.min(w, h) / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function drawTextLayer(layer) {
  if (!layer.visible) return;

  const box = pxBoxFromPct(layer.box);
  const s = layer.style;

  const pad = s.boxOn ? (s.boxPad ?? 0) : 0;
  const inner = {
    x: box.x + pad,
    y: box.y + pad,
    w: Math.max(10, box.w - pad * 2),
    h: Math.max(10, box.h - pad * 2),
  };

  let text = (layer.text ?? "").toString();
  if (s.uppercase) text = text.toUpperCase();

  if (s.boxOn) {
    ctx.save();
    ctx.fillStyle = rgbaFromHex(s.boxColor ?? "#000000", clamp(s.boxOpacity ?? 0.35, 0, 1));
    drawRoundedRect(box.x, box.y, box.w, box.h, s.boxRadius ?? 24);
    ctx.fill();
    ctx.restore();
  }

  let sizePx = clamp(parseInt(s.fontSize ?? 96, 10), 8, 260);
  if (s.autoFit) sizePx = findBestFontSize(s, text, inner);

  ctx.save();
  ctx.font = buildFont(s, sizePx);
  ctx.textBaseline = "top";

  const layout = wrapTextToBox(text, s, inner, sizePx);
  const startY = inner.y + (inner.h - layout.heightPx) / 2;

  const align = s.align ?? "center";
  ctx.textAlign = align;
  const anchorX = align === "left" ? inner.x
    : align === "right" ? (inner.x + inner.w)
      : (inner.x + inner.w / 2);

  if (s.shadowOn) {
    ctx.shadowColor = rgbaFromHex(s.shadowColor ?? "#000000", 0.55);
    ctx.shadowBlur = clamp(parseFloat(s.shadowBlur ?? 18), 0, 80);
    ctx.shadowOffsetX = clamp(parseFloat(s.shadowDx ?? 6), -80, 80);
    ctx.shadowOffsetY = clamp(parseFloat(s.shadowDy ?? 6), -80, 80);
  } else {
    ctx.shadowColor = "transparent";
    ctx.shadowBlur = 0;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 0;
  }

  if (s.strokeOn) {
    ctx.lineJoin = "round";
    ctx.miterLimit = 2;
    ctx.strokeStyle = s.strokeColor ?? "#000";
    ctx.lineWidth = clamp(parseFloat(s.strokeWidth ?? 10), 0, 60);
  }

  ctx.fillStyle = s.fill ?? "#fff";

  for (let i = 0; i < layout.lines.length; i++) {
    const line = layout.lines[i];
    const y = startY + i * layout.lineHeightPx;
    if (s.strokeOn && (s.strokeWidth ?? 0) > 0) ctx.strokeText(line, anchorX, y);
    ctx.fillText(line, anchorX, y);
  }

  ctx.restore();
}

// -------------------- Image layer rendering --------------------
function drawImageLayer(layer) {
  if (!layer.visible) return;
  const box = pxBoxFromPct(layer.box);

  ctx.save();
  ctx.globalAlpha = clamp(layer.opacity ?? 1, 0, 1);

  if (layer.shadow) {
    ctx.shadowColor = "rgba(0,0,0,0.45)";
    ctx.shadowBlur = 18;
    ctx.shadowOffsetX = 6;
    ctx.shadowOffsetY = 6;
  }

  if (!layer.img) {
    ctx.fillStyle = "rgba(255,255,255,0.10)";
    drawRoundedRect(box.x, box.y, box.w, box.h, 18);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.25)";
    ctx.lineWidth = 2;
    ctx.strokeRect(box.x, box.y, box.w, box.h);
    ctx.fillStyle = "rgba(232,238,252,0.8)";
    ctx.font = `800 16px "Inter"`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("Upload Image", box.x + box.w / 2, box.y + box.h / 2);
    ctx.restore();
    return;
  }

  const img = layer.img;
  const iw = img.naturalWidth || img.width;
  const ih = img.naturalHeight || img.height;

  if ((layer.fit ?? "contain") === "cover") {
    const scale = Math.max(box.w / iw, box.h / ih);
    const dw = iw * scale, dh = ih * scale;
    ctx.drawImage(img, box.x + (box.w - dw) / 2, box.y + (box.h - dh) / 2, dw, dh);
  } else {
    const scale = Math.min(box.w / iw, box.h / ih);
    const dw = iw * scale, dh = ih * scale;
    ctx.drawImage(img, box.x + (box.w - dw) / 2, box.y + (box.h - dh) / 2, dw, dh);
  }

  ctx.restore();
}

// -------------------- Handles (used for layers + crop) --------------------
function getHandles(box) {
  const s = 10;
  const hs = [
    { key: "nw", x: box.x - s / 2, y: box.y - s / 2 },
    { key: "n", x: box.x + box.w / 2 - s / 2, y: box.y - s / 2 },
    { key: "ne", x: box.x + box.w - s / 2, y: box.y - s / 2 },
    { key: "e", x: box.x + box.w - s / 2, y: box.y + box.h / 2 - s / 2 },
    { key: "se", x: box.x + box.w - s / 2, y: box.y + box.h - s / 2 },
    { key: "s", x: box.x + box.w / 2 - s / 2, y: box.y + box.h - s / 2 },
    { key: "sw", x: box.x - s / 2, y: box.y + box.h - s / 2 },
    { key: "w", x: box.x - s / 2, y: box.y + box.h / 2 - s / 2 },
  ];
  return hs.map(h => ({ ...h, w: s, h: s }));
}
function hitTestHandle(mx, my, box) {
  const handles = getHandles(box);
  for (const h of handles) {
    if (mx >= h.x && mx <= h.x + h.w && my >= h.y && my <= h.y + h.h) return h.key;
  }
  return null;
}
function hitTestBox(mx, my, box) {
  return (mx >= box.x && mx <= box.x + box.w && my >= box.y && my <= box.y + box.h);
}

// -------------------- Background Crop Overlay (on canvas) --------------------
// We draw crop rectangle in CANVAS space for user interaction
function getBgCropCanvasRect() {
  const { W, H } = getCanvasWH();
  if (!state.bgImage || !state.bgCrop) return null;

  // map source crop -> canvas (we show it as full canvas area, since it becomes the canvas)
  // For editing, we display a "crop frame" as if user is selecting which part of bg will be used.
  // We'll treat this as a virtual rectangle in canvas space that user manipulates,
  // then convert it back to source crop using the image "view" representation.

  // For simplicity and correctness, we edit crop in SOURCE coords but interact in CANVAS space:
  // We'll maintain an "editor view" where the full image is fitted to canvas (contain),
  // then the crop rect is drawn on top of that fitted image.
  const img = state.bgImage;
  const iw = img.naturalWidth || img.width;
  const ih = img.naturalHeight || img.height;

  // Fit full image into canvas (contain) for crop editor overlay
  const scale = Math.min(W / iw, H / ih);
  const dw = iw * scale, dh = ih * scale;
  const ox = (W - dw) / 2;
  const oy = (H - dh) / 2;

  // crop rect in source -> canvas
  const c = state.bgCrop;
  const x = ox + c.sx * scale;
  const y = oy + c.sy * scale;
  const w = c.sw * scale;
  const h = c.sh * scale;

  return { x, y, w, h, scale, ox, oy, dw, dh, iw, ih };
}

function drawBgCropOverlay() {
  if (!state.bgImage || !state.bgCrop || state.bgMode !== "crop") return;

  const { W, H } = getCanvasWH();
  const r = getBgCropCanvasRect();
  if (!r) return;

  ctx.save();

  // darken outside crop
  ctx.fillStyle = "rgba(0,0,0,0.45)";
  ctx.fillRect(0, 0, W, H);

  // clear inside crop area
  ctx.clearRect(r.x, r.y, r.w, r.h);

  // draw border
  ctx.strokeStyle = "rgba(255,255,255,0.95)";
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  ctx.strokeRect(r.x, r.y, r.w, r.h);
  ctx.setLineDash([]);

  // handles
  ctx.fillStyle = "rgba(255,255,255,0.95)";
  for (const h of getHandles({ x: r.x, y: r.y, w: r.w, h: r.h })) ctx.fillRect(h.x, h.y, h.w, h.h);

  // info
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.font = `700 14px "Inter"`;
  ctx.textAlign = "left";
  ctx.textBaseline = "bottom";
  ctx.fillText("Background Crop (drag/resize)", r.x + 8, r.y - 6);

  ctx.restore();
}

// Convert crop editor move/resize in CANVAS space back into SOURCE crop
function setBgCropFromCanvasRect(newRectCanvas) {
  const r = getBgCropCanvasRect();
  if (!r) return;

  // Clamp crop rect to the displayed image bounds (ox..ox+dw, oy..oy+dh)
  const minSizePx = 40;
  let x = clamp(newRectCanvas.x, r.ox, r.ox + r.dw - minSizePx);
  let y = clamp(newRectCanvas.y, r.oy, r.oy + r.dh - minSizePx);
  let w = clamp(newRectCanvas.w, minSizePx, (r.ox + r.dw) - x);
  let h = clamp(newRectCanvas.h, minSizePx, (r.oy + r.dh) - y);

  // Convert to source
  const sx = (x - r.ox) / r.scale;
  const sy = (y - r.oy) / r.scale;
  const sw = w / r.scale;
  const sh = h / r.scale;

  state.bgCrop = { sx, sy, sw, sh };
}

// Aspect-locked resize for crop box (matches output format)
function resizeBgCropAspectLocked(startRect, handle, dx, dy) {
  const ar = getCanvasAspect();
  let { x, y, w, h } = startRect;

  // We'll resize based on the handle, keeping aspect ratio w/h = ar.
  // Use dx/dy, choose primary direction by magnitude.
  const primary = Math.abs(dx) >= Math.abs(dy) ? "x" : "y";

  const applyWH = (newW, newH, anchorX, anchorY) => {
    // anchorX/anchorY indicates which corner stays fixed
    // anchorX: 0 left, 1 right ; anchorY: 0 top, 1 bottom
    const nx = anchorX === 0 ? x : (x + w - newW);
    const ny = anchorY === 0 ? y : (y + h - newH);
    return { x: nx, y: ny, w: newW, h: newH };
  };

  // Default anchors per handle
  let ax = 0, ay = 0;
  if (handle.includes("e")) ax = 0; else if (handle.includes("w")) ax = 1; else ax = 0;
  if (handle.includes("s")) ay = 0; else if (handle.includes("n")) ay = 1; else ay = 0;

  // For side handles, set anchors accordingly
  if (handle === "e") { ax = 0; ay = 0; }
  if (handle === "w") { ax = 1; ay = 0; }
  if (handle === "n") { ax = 0; ay = 1; }
  if (handle === "s") { ax = 0; ay = 0; }

  let newW = w;
  let newH = h;

  if (primary === "x") {
    if (handle.includes("e")) newW = w + dx;
    else if (handle.includes("w")) newW = w - dx;
    else newW = w + dx; // corner
    newW = Math.max(40, newW);
    newH = newW / ar;
  } else {
    if (handle.includes("s")) newH = h + dy;
    else if (handle.includes("n")) newH = h - dy;
    else newH = h + dy; // corner
    newH = Math.max(40, newH);
    newW = newH * ar;
  }

  return applyWH(newW, newH, ax, ay);
}

// -------------------- Layer selection UI --------------------
function selectedLayer() {
  return state.layers.find(l => l.id === state.selectedLayerId) || null;
}

function refreshLayersUI() {
  const list = $("layersList");
  list.innerHTML = "";

  for (const layer of state.layers) {
    const item = document.createElement("div");
    item.className = "layer-item" + (layer.id === state.selectedLayerId ? " active" : "");
    item.dataset.id = layer.id;

    const left = document.createElement("div");
    left.className = "layer-left";

    const nm = document.createElement("div");
    nm.className = "layer-name";
    nm.textContent = layer.name;

    const meta = document.createElement("div");
    meta.className = "layer-meta";
    meta.textContent = `${layer.visible ? "Visible" : "Hidden"} • ${layer.type === "image" ? "Image" : "Text"}`;

    left.appendChild(nm);
    left.appendChild(meta);

    const eye = document.createElement("button");
    eye.className = "layer-eye";
    eye.title = layer.visible ? "Hide layer" : "Show layer";
    eye.textContent = layer.visible ? "👁️" : "🚫";
    eye.addEventListener("click", (e) => {
      e.stopPropagation();
      layer.visible = !layer.visible;
      refreshLayersUI();
      render();
    });

    item.appendChild(left);
    item.appendChild(eye);

    item.addEventListener("click", () => {
      state.selectedLayerId = layer.id;
      refreshLayersUI();
      refreshPropsUI();
      render();
    });

    list.appendChild(item);
  }
}

// -------------------- Props UI --------------------
function showPropsNone() {
  $("noSelection").classList.remove("hidden");
  $("layerPropsText").classList.add("hidden");
  $("layerPropsImage").classList.add("hidden");
}
function showPropsText() {
  $("noSelection").classList.add("hidden");
  $("layerPropsText").classList.remove("hidden");
  $("layerPropsImage").classList.add("hidden");
}
function showPropsImage() {
  $("noSelection").classList.add("hidden");
  $("layerPropsText").classList.add("hidden");
  $("layerPropsImage").classList.remove("hidden");
}

function refreshPropsUI() {
  const layer = selectedLayer();
  if (!layer) { showPropsNone(); return; }

  if (layer.type === "text") {
    showPropsText();
    const s = layer.style;

    $("propName").value = layer.name ?? "";
    $("propText").value = layer.text ?? "";
    $("propFont").value = s.fontFamily ?? "Inter";
    $("propWeight").value = String(s.fontWeight ?? 800);
    $("propAutoFit").value = s.autoFit ? "yes" : "no";
    $("propFontSize").value = parseInt(s.fontSize ?? 96, 10);
    $("propFill").value = s.fill ?? "#ffffff";
    $("propAlign").value = s.align ?? "center";
    $("propUppercase").value = s.uppercase ? "yes" : "no";
    $("propLineHeight").value = parseFloat(s.lineHeight ?? 1.05);

    $("propStrokeOn").value = s.strokeOn ? "yes" : "no";
    $("propStrokeWidth").value = parseFloat(s.strokeWidth ?? 14);
    $("propStrokeColor").value = s.strokeColor ?? "#000000";

    $("propShadowOn").value = s.shadowOn ? "yes" : "no";
    $("propShadowBlur").value = parseFloat(s.shadowBlur ?? 18);
    $("propShadowDx").value = parseFloat(s.shadowDx ?? 6);
    $("propShadowDy").value = parseFloat(s.shadowDy ?? 6);
    $("propShadowColor").value = s.shadowColor ?? "#000000";

    $("propBoxOn").value = s.boxOn ? "yes" : "no";
    $("propBoxPad").value = parseFloat(s.boxPad ?? 18);
    $("propBoxRadius").value = parseFloat(s.boxRadius ?? 24);
    $("propBoxColor").value = s.boxColor ?? "#000000";
    $("propBoxOpacity").value = parseFloat(s.boxOpacity ?? 0.35);
    $("propBoxOpacityVal").textContent = Number($("propBoxOpacity").value).toFixed(2);
    return;
  }

  if (layer.type === "image") {
    showPropsImage();
    $("imgPropName").value = layer.name ?? "";
    $("imgPropOpacity").value = clamp(layer.opacity ?? 1, 0, 1);
    $("imgPropOpacityVal").textContent = Number($("imgPropOpacity").value).toFixed(2);
    $("imgPropFit").value = layer.fit ?? "contain";
    $("imgPropShadow").value = layer.shadow ? "yes" : "no";
  }
}

function bindTextProps() {
  const bind = (id, fn) => {
    $(id).addEventListener("input", () => {
      const layer = selectedLayer();
      if (!layer || layer.type !== "text") return;
      fn(layer);
      refreshLayersUI();
      render();
    });
    $(id).addEventListener("change", () => {
      const layer = selectedLayer();
      if (!layer || layer.type !== "text") return;
      fn(layer);
      refreshLayersUI();
      render();
    });
  };

  bind("propName", (l) => l.name = $("propName").value);
  bind("propText", (l) => l.text = $("propText").value);
  bind("propFont", (l) => l.style.fontFamily = $("propFont").value);
  bind("propWeight", (l) => l.style.fontWeight = parseInt($("propWeight").value, 10));
  bind("propAutoFit", (l) => l.style.autoFit = $("propAutoFit").value === "yes");
  bind("propFontSize", (l) => l.style.fontSize = clamp(parseInt($("propFontSize").value || "96", 10), 8, 260));
  bind("propFill", (l) => l.style.fill = $("propFill").value);
  bind("propAlign", (l) => l.style.align = $("propAlign").value);
  bind("propUppercase", (l) => l.style.uppercase = $("propUppercase").value === "yes");
  bind("propLineHeight", (l) => l.style.lineHeight = clamp(parseFloat($("propLineHeight").value || "1.05"), 0.8, 1.8));

  bind("propStrokeOn", (l) => l.style.strokeOn = $("propStrokeOn").value === "yes");
  bind("propStrokeWidth", (l) => l.style.strokeWidth = clamp(parseFloat($("propStrokeWidth").value || "0"), 0, 60));
  bind("propStrokeColor", (l) => l.style.strokeColor = $("propStrokeColor").value);

  bind("propShadowOn", (l) => l.style.shadowOn = $("propShadowOn").value === "yes");
  bind("propShadowBlur", (l) => l.style.shadowBlur = clamp(parseFloat($("propShadowBlur").value || "0"), 0, 80));
  bind("propShadowDx", (l) => l.style.shadowDx = clamp(parseFloat($("propShadowDx").value || "0"), -80, 80));
  bind("propShadowDy", (l) => l.style.shadowDy = clamp(parseFloat($("propShadowDy").value || "0"), -80, 80));
  bind("propShadowColor", (l) => l.style.shadowColor = $("propShadowColor").value);

  bind("propBoxOn", (l) => l.style.boxOn = $("propBoxOn").value === "yes");
  bind("propBoxPad", (l) => l.style.boxPad = clamp(parseFloat($("propBoxPad").value || "0"), 0, 80));
  bind("propBoxRadius", (l) => l.style.boxRadius = clamp(parseFloat($("propBoxRadius").value || "0"), 0, 120));
  bind("propBoxColor", (l) => l.style.boxColor = $("propBoxColor").value);
  bind("propBoxOpacity", (l) => {
    l.style.boxOpacity = clamp(parseFloat($("propBoxOpacity").value || "0.35"), 0, 1);
    $("propBoxOpacityVal").textContent = Number($("propBoxOpacity").value).toFixed(2);
  });
}

function bindImageProps() {
  $("imgPropName").addEventListener("input", () => {
    const layer = selectedLayer();
    if (!layer || layer.type !== "image") return;
    layer.name = $("imgPropName").value;
    refreshLayersUI();
    render();
  });

  $("imgPropOpacity").addEventListener("input", () => {
    const layer = selectedLayer();
    if (!layer || layer.type !== "image") return;
    layer.opacity = clamp(parseFloat($("imgPropOpacity").value || "1"), 0, 1);
    $("imgPropOpacityVal").textContent = Number(layer.opacity).toFixed(2);
    render();
  });

  $("imgPropFit").addEventListener("change", () => {
    const layer = selectedLayer();
    if (!layer || layer.type !== "image") return;
    layer.fit = $("imgPropFit").value;
    render();
  });

  $("imgPropShadow").addEventListener("change", () => {
    const layer = selectedLayer();
    if (!layer || layer.type !== "image") return;
    layer.shadow = $("imgPropShadow").value === "yes";
    render();
  });

  $("imgPropFile").addEventListener("change", async (e) => {
    const layer = selectedLayer();
    if (!layer || layer.type !== "image") return;
    const file = e.target.files?.[0];
    if (!file) return;
    const img = await loadImageFromBlob(file);
    layer.img = img;
    layer.imgSrc = img.src;
    render();
    setStatus("Logo/Image loaded");
  });
}

// -------------------- Render selection for layers --------------------
function drawLayerSelection() {
  const layer = selectedLayer();
  if (!layer || !layer.visible) return;

  const box = pxBoxFromPct(layer.box);
  const { w, h, safe } = formats[state.formatKey];

  ctx.save();

  // safe area
  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 6]);
  ctx.strokeRect(safe.x * w, safe.y * h, safe.w * w, safe.h * h);
  ctx.setLineDash([]);

  // selection box
  ctx.strokeStyle = "rgba(90,167,255,0.95)";
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  ctx.strokeRect(box.x, box.y, box.w, box.h);
  ctx.setLineDash([]);

  // handles
  ctx.fillStyle = "rgba(90,167,255,1)";
  for (const hnd of getHandles(box)) ctx.fillRect(hnd.x, hnd.y, hnd.w, hnd.h);

  ctx.restore();
}

// -------------------- Full render --------------------
function render({ forExport = false } = {}) {
  drawBackground();

  // Show crop overlay only while editing (never in export)
  if (
    !forExport &&
    state.bgMode === "crop" &&
    state.showCropOverlay
  ) {
    drawBgCropOverlay();
  }


  // draw layers
  for (const layer of state.layers) {
    if (!layer.visible) continue;
    if (layer.type === "image") drawImageLayer(layer);
    if (layer.type === "text") drawTextLayer(layer);
  }

  // Show selection box only while editing (never in export)
  if (!forExport && !(state.bgMode === "crop" && state.bgDragging)) {
    drawLayerSelection();
  }
}


// -------------------- Mouse mapping --------------------
function getMousePos(evt) {
  const rect = canvas.getBoundingClientRect();
  const { W, H } = getCanvasWH();
  const x = (evt.clientX - rect.left) * (W / rect.width);
  const y = (evt.clientY - rect.top) * (H / rect.height);
  return { x, y };
}

// -------------------- Background crop interaction --------------------
function bgCropHitTest(mx, my) {
  if (state.bgMode !== "crop") return null;
  const r = getBgCropCanvasRect();
  if (!r) return null;

  const box = { x: r.x, y: r.y, w: r.w, h: r.h };
  const hnd = hitTestHandle(mx, my, box);
  if (hnd) return { type: "handle", handle: hnd, box };
  if (hitTestBox(mx, my, box)) return { type: "box", box };
  return null;
}

// -------------------- Layer interaction --------------------
function layerHitTestSelect(mx, my) {
  // select topmost layer under cursor
  for (let i = state.layers.length - 1; i >= 0; i--) {
    const L = state.layers[i];
    if (!L.visible) continue;
    const b = pxBoxFromPct(L.box);
    if (hitTestBox(mx, my, b)) return L;
  }
  return null;
}

canvas.addEventListener("mousedown", (e) => {
  const { x: mx, y: my } = getMousePos(e);

  // 1) If in crop mode and user clicks crop box/handle -> start bg crop drag
  const bgHit = bgCropHitTest(mx, my);
  if (bgHit) {
    const r = getBgCropCanvasRect();
    state.bgDragging = {
      mode: bgHit.type === "handle" ? "resize" : "move",
      handle: bgHit.handle || null,
      startX: mx,
      startY: my,
      startRect: { x: r.x, y: r.y, w: r.w, h: r.h },
    };
    render();
    return;
  }

  // 2) Otherwise handle layers
  // Select if clicking a different layer
  const top = layerHitTestSelect(mx, my);
  if (top && top.id !== state.selectedLayerId) {
    state.selectedLayerId = top.id;
    refreshLayersUI();
    refreshPropsUI();
  }

  const layer = selectedLayer();
  if (!layer) return;

  const box = pxBoxFromPct(layer.box);
  const handle = hitTestHandle(mx, my, box);
  if (handle) {
    state.dragging = { id: layer.id, mode: "resize", handle, startX: mx, startY: my, startBox: { ...box } };
    return;
  }
  if (hitTestBox(mx, my, box)) {
    state.dragging = { id: layer.id, mode: "move", startX: mx, startY: my, startBox: { ...box } };
    return;
  }
});

window.addEventListener("mousemove", (e) => {
  const { x: mx, y: my } = getMousePos(e);

  // Background crop drag
  if (state.bgDragging) {
    const dx = mx - state.bgDragging.startX;
    const dy = my - state.bgDragging.startY;

    let rect = { ...state.bgDragging.startRect };

    if (state.bgDragging.mode === "move") {
      rect.x += dx;
      rect.y += dy;
    } else {
      rect = resizeBgCropAspectLocked(rect, state.bgDragging.handle, dx, dy);
    }

    // Apply back to source crop (clamps inside image bounds)
    setBgCropFromCanvasRect(rect);
    render();
    return;
  }

  // Layer drag
  if (!state.dragging) return;
  const layer = state.layers.find(l => l.id === state.dragging.id);
  if (!layer) return;

  const dx = mx - state.dragging.startX;
  const dy = my - state.dragging.startY;

  const { W, H } = getCanvasWH();
  const minSize = 30;

  let box = { ...state.dragging.startBox };

  if (state.dragging.mode === "move") {
    let ndx = dx, ndy = dy;
    if (e.shiftKey) {
      if (Math.abs(dx) > Math.abs(dy)) ndy = 0;
      else ndx = 0;
    }
    box.x += ndx; box.y += ndy;
    box.x = clamp(box.x, 0, W - box.w);
    box.y = clamp(box.y, 0, H - box.h);
  } else {
    const hnd = state.dragging.handle;
    const apply = (left, top, right, bottom) => {
      if (left) {
        const nx = clamp(box.x + dx, 0, box.x + box.w - minSize);
        box.w = box.x + box.w - nx; box.x = nx;
      }
      if (right) box.w = clamp(box.w + dx, minSize, W - box.x);
      if (top) {
        const ny = clamp(box.y + dy, 0, box.y + box.h - minSize);
        box.h = box.y + box.h - ny; box.y = ny;
      }
      if (bottom) box.h = clamp(box.h + dy, minSize, H - box.y);
    };
    if (hnd === "nw") apply(true, true, false, false);
    if (hnd === "n") apply(false, true, false, false);
    if (hnd === "ne") apply(false, true, true, false);
    if (hnd === "e") apply(false, false, true, false);
    if (hnd === "se") apply(false, false, true, true);
    if (hnd === "s") apply(false, false, false, true);
    if (hnd === "sw") apply(true, false, false, true);
    if (hnd === "w") apply(true, false, false, false);

    box.x = clamp(box.x, 0, W - minSize);
    box.y = clamp(box.y, 0, H - minSize);
    box.w = clamp(box.w, minSize, W - box.x);
    box.h = clamp(box.h, minSize, H - box.y);
  }

  layer.box = pctBoxFromPx(box);
  render();
});

window.addEventListener("mouseup", () => {
  if (state.bgDragging) {
    state.bgDragging = null;
    setStatus("Background crop updated");
    render();
  }
  state.dragging = null;
});

// -------------------- Background load (file + paste) --------------------
// $("imageInput").addEventListener("change", async (e) => {
//   const file = e.target.files?.[0];
//   if (!file) return;
//   const img = await loadImageFromBlob(file);
//   state.bgImage = img;
//   state.bgImageSrc = img.src;

//   initCenteredBgCrop();
//   render();
//   setStatus("Background loaded (crop ready)");
// });

$("bgFileInput").addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const url = URL.createObjectURL(file);

  if (file.type.startsWith("video/")) {
    // ---- VIDEO BACKGROUND ----
    const v = state.bgVideoEl;
    state.bgType = "video";
    state.bgVideoSrc = url;
    state.bgVideoReady = false;

    v.src = url;
    v.loop = true;
    v.muted = true;
    v.playsInline = true;

    v.onloadedmetadata = () => {
      state.bgVideoReady = true;

      // Initialize crop box based on video dimensions
      initCenteredBgCropForSource(v.videoWidth, v.videoHeight);

      v.play().catch(() => { });
      startVideoRenderLoop();
      setStatus("Video loaded (crop ready)");
    };

    return;
  }

  // ---- IMAGE BACKGROUND ----
  const img = await loadImageFromBlob(file);
  state.bgType = "image";
  state.bgImage = img;
  state.bgImageSrc = img.src;

  initCenteredBgCrop(); // existing image crop init
  render();
  setStatus("Image loaded (crop ready)");
});

function initCenteredBgCropForSource(iw, ih) {
  const ar = getCanvasAspect();

  let sw = iw;
  let sh = sw / ar;
  if (sh > ih) {
    sh = ih;
    sw = sh * ar;
  }

  const sx = (iw - sw) / 2;
  const sy = (ih - sh) / 2;

  state.bgCrop = { sx, sy, sw, sh };
}

window.addEventListener("paste", async (e) => {
  const items = e.clipboardData?.items || [];
  for (const it of items) {
    if (it.type && it.type.startsWith("image/")) {
      const blob = it.getAsFile();
      if (!blob) continue;
      const img = await loadImageFromBlob(blob);
      state.bgImage = img;
      state.bgImageSrc = img.src;

      initCenteredBgCrop();
      render();
      setStatus("Pasted background (crop ready)");
      return;
    }
  }
});

// -------------------- Project controls --------------------
$("formatSelect").addEventListener("change", () => {
  state.formatKey = $("formatSelect").value;
  applyCanvasFormat();

  // Keep crop aspect locked to new format: re-center crop (best UX)
  if (state.bgImage) {
    initCenteredBgCrop();
  }

  render();
  setStatus("Format changed");
});

$("bgModeSelect").addEventListener("change", () => {
  state.bgMode = $("bgModeSelect").value;

  // Ensure crop exists if user switches to crop
  if (state.bgMode === "crop" && state.bgImage && !state.bgCrop) {
    initCenteredBgCrop();
  }

  render();
  setStatus(`Background mode: ${state.bgMode}`);
});

$("bgDim").addEventListener("input", () => {
  state.bgDim = parseFloat($("bgDim").value);
  $("bgDimVal").textContent = state.bgDim.toFixed(2);
  render();
});

$("btnCenterCrop").addEventListener("click", () => {
  if (!state.bgImage) return;
  initCenteredBgCrop();
  render();
  setStatus("Centered background crop");
});
$("btnResetCrop").addEventListener("click", () => {
  if (!state.bgImage) return;
  resetBgCrop();
});

$("btnToggleCropOverlay").addEventListener("click", () => {
  state.showCropOverlay = !state.showCropOverlay;

  $("btnToggleCropOverlay").textContent =
    state.showCropOverlay ? "Hide Crop Overlay" : "Show Crop Overlay";

  render();
});

$("jpgQuality").addEventListener("input", () => {
  $("jpgQualityVal").textContent = Number($("jpgQuality").value).toFixed(2);
});

// -------------------- Layer buttons --------------------
$("btnAddTextLayer").addEventListener("click", () => {
  const l = makeTextLayer({
    name: `Text ${state.layers.length + 1}`,
    text: "TYPE HERE",
    box: { x: 0.12, y: 0.45, w: 0.76, h: 0.20 }
  });
  l.style.fontFamily = "Montserrat";
  l.style.fontWeight = 900;
  l.style.fontSize = 90;
  state.layers.push(l);
  state.selectedLayerId = l.id;
  refreshLayersUI();
  refreshPropsUI();
  render();
});

$("btnAddImageLayer").addEventListener("click", () => {
  const l = makeImageLayer({ name: `Logo ${state.layers.length + 1}` });
  state.layers.push(l);
  state.selectedLayerId = l.id;
  refreshLayersUI();
  refreshPropsUI();
  render();
  setStatus("Added Image/Logo layer (upload on right)");
});

$("btnDeleteLayer").addEventListener("click", () => {
  const id = state.selectedLayerId;
  if (!id) return;
  const idx = state.layers.findIndex(l => l.id === id);
  if (idx === -1) return;
  state.layers.splice(idx, 1);
  state.selectedLayerId = state.layers[idx - 1]?.id || state.layers[0]?.id || null;
  refreshLayersUI();
  refreshPropsUI();
  render();
});

$("btnDuplicateLayer").addEventListener("click", () => {
  const layer = selectedLayer();
  if (!layer) return;
  const copy = JSON.parse(JSON.stringify(layer));
  copy.id = uid();
  copy.name = (layer.name || "Layer") + " copy";
  copy.box = { ...layer.box, x: clamp(layer.box.x + 0.02, 0, 0.98), y: clamp(layer.box.y + 0.02, 0, 0.98) };

  if (layer.type === "image") {
    copy.img = layer.img || null;
    copy.imgSrc = layer.imgSrc || "";
  }
  state.layers.push(copy);
  state.selectedLayerId = copy.id;
  refreshLayersUI();
  refreshPropsUI();
  render();
});

$("btnBringForward").addEventListener("click", () => {
  const id = state.selectedLayerId;
  if (!id) return;
  const idx = state.layers.findIndex(l => l.id === id);
  if (idx === -1 || idx === state.layers.length - 1) return;
  [state.layers[idx], state.layers[idx + 1]] = [state.layers[idx + 1], state.layers[idx]];
  refreshLayersUI(); render();
});

$("btnSendBackward").addEventListener("click", () => {
  const id = state.selectedLayerId;
  if (!id) return;
  const idx = state.layers.findIndex(l => l.id === id);
  if (idx <= 0) return;
  [state.layers[idx], state.layers[idx - 1]] = [state.layers[idx - 1], state.layers[idx]];
  refreshLayersUI(); render();
});

function downloadDataUrl(dataUrl, filename) {
  const a = document.createElement("a");
  a.download = filename;
  a.href = dataUrl;
  a.click();
}

function downloadText(text, filename, mime = "application/json") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.download = filename;
  a.href = url;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

/**
 * Renders ONLY overlays (layers) to a transparent PNG at the target canvas size.
 * IMPORTANT: This needs render() to support an "overlayOnly" mode (see note below).
 */
$("btnExportOverlay").addEventListener("click", () => {
  const { w, h } = formats[state.formatKey];
  const ts = new Date().toISOString().replace(/[:.]/g, "-");

  // 1) draw transparent overlay only (no background image / dim / crop UI / selection UI)
  render({ forExport: true, overlayOnly: true });

  // 2) export transparent PNG
  const dataUrl = canvas.toDataURL("image/png");

  // 3) restore normal editor rendering
  render({ forExport: false, overlayOnly: false });

  downloadDataUrl(dataUrl, `overlay_${state.formatKey}_${w}x${h}_${ts}.png`);
  setStatus(`Exported Overlay PNG (${w}×${h})`);
});

$("btnExportProject").addEventListener("click", () => {
  const { w, h } = formats[state.formatKey];
  const ts = new Date().toISOString().replace(/[:.]/g, "-");

  // Keep it portable: store crop + layers + format + bgMode/bgDim.
  // Don't try to embed full image binary; just keep bgImageSrc if you want.
  const project = {
    version: 1,
    formatKey: state.formatKey,
    format: { w, h },
    bgMode: state.bgMode,
    bgDim: state.bgDim,
    // bgCrop is in SOURCE IMAGE pixel coords (sx,sy,sw,sh) already in your code :contentReference[oaicite:3]{index=3}
    bgCrop: state.bgCrop,
    // layers includes text + image layers (image layers store imgSrc) :contentReference[oaicite:4]{index=4}
    layers: state.layers
  };

  downloadText(JSON.stringify(project, null, 2), `project_${state.formatKey}_${w}x${h}_${ts}.json`);
  setStatus("Exported Project JSON");
});

// -------------------- Export --------------------
$("btnExport").addEventListener("click", () => {
  const type = $("exportType").value;

  // 1) render clean image (no crop overlay, no selection boxes)
  render({ forExport: true });

  // 2) export
  let dataUrl = "";
  if (type === "png") {
    dataUrl = canvas.toDataURL("image/png");
  } else {
    const q = clamp(parseFloat($("jpgQuality").value || "0.92"), 0.4, 1);
    dataUrl = canvas.toDataURL("image/jpeg", q);
  }

  // 3) restore edit overlays after export
  render({ forExport: false });

  const { w, h } = formats[state.formatKey];
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const a = document.createElement("a");
  a.download = `design_${state.formatKey}_${w}x${h}_${ts}.${type}`;
  a.href = dataUrl;
  a.click();
  setStatus(`Exported ${type.toUpperCase()} (${w}×${h})`);
});


// -------------------- New project --------------------
function resetProject() {
  state.bgImage = null;
  state.bgImageSrc = "";
  state.bgCrop = null;

  state.layers = [
    makeTextLayer({ name: "Hook", text: "CUTE FARM\nANIMALS", box: { x: 0.06, y: 0.10, w: 0.62, h: 0.30 } }),
    makeTextLayer({ name: "Sub", text: "Coloring Book", box: { x: 0.06, y: 0.42, w: 0.55, h: 0.14 } }),
  ];

  state.layers[0].style.fontFamily = "Anton";
  state.layers[0].style.fontSize = 150;
  state.layers[0].style.strokeWidth = 16;
  state.layers[0].style.align = "left";

  state.layers[1].style.fontFamily = "Bebas Neue";
  state.layers[1].style.fontSize = 90;
  state.layers[1].style.uppercase = false;
  state.layers[1].style.strokeWidth = 10;
  state.layers[1].style.align = "left";

  state.selectedLayerId = state.layers[0].id;
  applyCanvasFormat();
  render();
  refreshLayersUI();
  refreshPropsUI();
  setStatus("New project created");
}

$("btnNew").addEventListener("click", resetProject);

// -------------------- Init --------------------
function init() {
  state.dpiScale = 1;
  $("formatSelect").value = state.formatKey;
  $("bgModeSelect").value = state.bgMode;
  $("bgDim").value = state.bgDim;
  $("bgDimVal").textContent = state.bgDim.toFixed(2);
  $("jpgQualityVal").textContent = Number($("jpgQuality").value).toFixed(2);

  bindTextProps();
  bindImageProps();

  applyCanvasFormat();
  resetProject();
  state.bgVideoEl = document.getElementById("bgVideo");

}

init();
