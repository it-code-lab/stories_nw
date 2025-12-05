# sketch_core.py
"""
Lightweight sketch core for coloring pages.

Dependencies:
  - opencv-python
  - numpy
  - pillow
  - rdp

NO rembg, NO scikit-image. This focuses on clean outline extraction,
which is ideal for coloring-page style inputs.
"""

import math
import cv2
import numpy as np
from PIL import Image
from rdp import rdp


# ---------- Core helpers ----------

def kmeans_quantize(img_bgr, k=8, iters=10):
    """
    Simple k-means color quantization. Helps make edges cleaner for cartoons.
    """
    Z = img_bgr.reshape((-1, 3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, iters, 1.0)
    _ret, labels, centers = cv2.kmeans(
        Z, k, None, criteria, iters, cv2.KMEANS_PP_CENTERS
    )
    centers = centers.astype(np.uint8)
    q = centers[labels.flatten()].reshape(img_bgr.shape)
    return q


def subject_mask_simple(img_rgb):
    """
    Fallback "subject" mask that is good enough for clean illustrations.
    For actual photos you'd want rembg, but here we keep it simple.

    Returns an 8-bit mask 0..255.
    """
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    # Otsu threshold to separate foreground-ish from background-ish
    _thr, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Make sure mask is not inverted (more foreground white)
    if np.mean(mask) < 128:
        mask = 255 - mask
    return mask


def edges_cartoon(img_bgr):
    """
    Edge map tuned for cartoons / coloring pages.
    """
    # Quantize to a reduced palette to reduce noise
    q = kmeans_quantize(img_bgr, k=7)
    gray = cv2.cvtColor(q, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold tends to keep inner lines
    binv = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        15,
        8,
    )

    # Clean up noise / fill small gaps
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binv = cv2.morphologyEx(binv, cv2.MORPH_CLOSE, k, iterations=1)
    binv = cv2.morphologyEx(binv, cv2.MORPH_OPEN, k, iterations=1)
    return binv


def edges_photo_light(img_bgr):
    """
    Simple edge detector for illustration/photo-like inputs.
    Uses a basic subject mask instead of heavy rembg/scikit-image.
    """
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    mask = subject_mask_simple(rgb)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    subj = cv2.bitwise_and(img_bgr, img_bgr, mask=mask)
    gray = cv2.cvtColor(subj, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 75, 75)

    med = float(np.median(gray))
    lo = int(max(0, 0.66 * med))
    hi = int(min(255, 1.33 * med))
    edges = cv2.Canny(gray, lo, hi)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k, iterations=1)
    edges = cv2.morphologyEx(edges, cv2.MORPH_OPEN, k, iterations=1)
    return edges


def remove_frame_like(cnt, img_w, img_h, area, pad=3):
    """
    Heuristic to drop outer page borders so we don't waste a big stroke
    on the rectangular frame around the page.
    """
    x, y, w, h = cv2.boundingRect(cnt)
    touches_edges = (
        x <= pad
        or y <= pad
        or x + w >= img_w - pad
        or y + h >= img_h - pad
    )
    too_big = (
        w >= 0.95 * img_w and h >= 0.95 * img_h
    ) or (area >= 0.60 * (img_w * img_h))
    return touches_edges and too_big


def contours_to_steps(
    binary_img,
    img_shape,
    rdp_eps=2.0,
    min_area_ratio=0.0005,
    max_paths=350,
    retrieval="tree",
):
    """
    Outline-style vectorization: returns (svg, steps) similar to your
    drawing app format.

    Each 'step' is a stroke with a single path 'd'.
    """
    h, w = img_shape[:2]
    min_area = max(4, int(min_area_ratio * (h * w)))
    mode = cv2.RETR_TREE if retrieval == "tree" else cv2.RETR_LIST

    cnts, _ = cv2.findContours(binary_img, mode, cv2.CHAIN_APPROX_NONE)

    paths = []
    for c in cnts:
        if len(c) < 8:
            continue
        area = abs(cv2.contourArea(c))
        if area < min_area:
            continue
        if remove_frame_like(c, w, h, area):
            continue

        pts = c[:, 0, :].astype(float).tolist()
        simp = rdp(pts, epsilon=rdp_eps)
        if len(simp) < 4:
            continue

        d = (
            f"M {simp[0][0]} {simp[0][1]} "
            + " ".join(f"L {x} {y}" for (x, y) in simp[1:])
            + " Z"
        )
        paths.append({"d": d, "area": area, "pts": len(simp)})

    paths.sort(key=lambda p: -p["area"])
    paths = paths[:max_paths]

    steps = [
        {
            "label": f"Stroke {i+1}",
            "paths": [{"d": p["d"]}],
            "est_ms": 500 + 7 * p["pts"],
        }
        for i, p in enumerate(paths)
    ]

    svg = {"viewBox": f"0 0 {w} {h}", "strokes": [p["d"] for p in paths]}
    return svg, steps


# ---------- High-level helper ----------

def build_sketch_from_pil(
    img_pil: Image.Image,
    mode: str = "auto",
    detail: int = 5,
    vector: str = "outline",  # "outline" | "centerline" (centerline treated as outline here)
):
    """
    Unified entrypoint for your Flask and other pipelines.

    - img_pil: PIL Image (RGB or anything convertible to RGB)
    - mode: "auto" | "cartoon" | "photo"
    - detail: 1..10 (higher = more detail, more paths)
    - vector: we keep the argument for API compatibility, but treat
              "centerline" same as "outline" in this lightweight version.

    Returns:
      (svg, steps)
    where:
      svg = { "viewBox": "0 0 W H", "strokes": [ "M ...", ... ] }
      steps = [ { "label": "...", "paths": [ {"d": "..."} ], "est_ms": ... }, ... ]
    """
    img_rgb = img_pil.convert("RGB")
    img_bgr = cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2BGR)
    h, w = img_bgr.shape[:2]

    # auto choose mode
    if mode == "auto":
        q = kmeans_quantize(img_bgr, k=7)
        # simple heuristic: more variation => treat as photo-ish
        is_photoish = (q.std() > 35)
        mode = "photo" if is_photoish else "cartoon"

    # edge/binary map
    if mode == "cartoon":
        binary = edges_cartoon(img_bgr)
    else:
        binary = edges_photo_light(img_bgr)

    # map detail 1..10 => rdp_eps, min area, max paths
    detail_clamped = max(1, min(10, int(detail)))
    rdp_eps = float(np.interp(detail_clamped, [1, 10], [4.0, 1.2]))
    min_area_ratio = float(np.interp(detail_clamped, [1, 10], [0.0020, 0.0002]))
    max_paths = int(np.interp(detail_clamped, [1, 10], [120, 700]))

    # This version does only outline-based vectorization.
    svg, steps = contours_to_steps(
        binary,
        img_bgr.shape,
        rdp_eps=rdp_eps,
        min_area_ratio=min_area_ratio,
        max_paths=max_paths,
        retrieval="tree",
    )

    return svg, steps
