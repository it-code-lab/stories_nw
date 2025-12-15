import json
import subprocess
from pathlib import Path

def run(cmd):
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

def build_video_filter(project, overlay_png, out_w, out_h):
    """
    Returns FFmpeg filter_complex string.
    We do:
      - crop/scale video to out_w/out_h based on project.bgMode/bgCrop
      - optional dim using a black overlay with alpha = bgDim
      - overlay overlay_png on top
    """
    bg_mode = project.get("bgMode", "cover")
    bg_dim = float(project.get("bgDim", 0.0) or 0.0)
    bg_crop = project.get("bgCrop")  # {sx,sy,sw,sh} in source image coords (for image). We'll re-use for video if provided.

    # Base video chain label names
    # [0:v] -> (crop/scale/pad) -> [vbase]
    chains = []

    if bg_mode == "crop" and bg_crop:
        # Treat bgCrop as crop rectangle on the VIDEO.
        # (This is perfect if you're using the editor to decide what part of the landscape video to keep.)
        sx = int(bg_crop["sx"])
        sy = int(bg_crop["sy"])
        sw = int(bg_crop["sw"])
        sh = int(bg_crop["sh"])
        chains.append(
            f"[0:v]crop={sw}:{sh}:{sx}:{sy},scale={out_w}:{out_h}:flags=lanczos[vbase]"
        )
    elif bg_mode == "contain":
        chains.append(
            f"[0:v]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
            f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:black[vbase]"
        )
    elif bg_mode == "contain_blur":
        # Blur background fill + sharp foreground contain
        chains.append(
            f"[0:v]split=2[vbg][vfg];"
            f"[vbg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},gblur=sigma=25[vbg2];"
            f"[vfg]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease[fg2];"
            f"[vbg2][fg2]overlay=(W-w)/2:(H-h)/2[vbase]"
        )
    else:
        # default = cover (center crop)
        chains.append(
            f"[0:v]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h}[vbase]"
        )

    # Optional dim (bgDim is already in your app UI) :contentReference[oaicite:7]{index=7}
    if bg_dim > 0.001:
        # black solid with alpha then overlay
        # color source is [dim], then overlay on [vbase] -> [vdim]
        chains.append(
            f"color=c=black@{bg_dim}:s={out_w}x{out_h}:r=30[dim];"
            f"[vbase][dim]overlay=0:0[vdim]"
        )
        v_after_dim = "[vdim]"
    else:
        v_after_dim = "[vbase]"

    # Overlay PNG (with alpha)
    # [1:v] is overlay image
    chains.append(f"{v_after_dim}[1:v]overlay=0:0:format=auto[vout]")

    return ";".join(chains)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-video", required=True)
    ap.add_argument("--overlay-png", required=True)
    ap.add_argument("--project-json", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--keep-audio", action="store_true", help="keep original audio if present")
    args = ap.parse_args()

    project = json.loads(Path(args.project_json).read_text(encoding="utf-8"))
    out_w = int(project.get("format", {}).get("w", 1280))
    out_h = int(project.get("format", {}).get("h", 720))

    filt = build_video_filter(project, args.overlay_png, out_w, out_h)

    cmd = [
        "ffmpeg", "-y",
        "-i", args.input_video,
        "-i", args.overlay_png,
        "-filter_complex", filt,
        "-map", "[vout]",
    ]

    if args.keep_audio:
        cmd += ["-map", "0:a?"]  # optional audio

    # Encoding choices (good defaults)
    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
    ]

    if args.keep_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    cmd += [args.output]
    run(cmd)

if __name__ == "__main__":
    main()
