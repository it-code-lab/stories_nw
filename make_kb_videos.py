# make_kb_videos.py
import os, random
from glob import glob
from moviepy.editor import ImageClip, CompositeVideoClip, VideoFileClip, vfx
import numpy as np
import subprocess

def cover_resize(clip, target_w, target_h):
    """Resize image to fully cover the target canvas (like CSS object-fit: cover)."""
    iw, ih = clip.size
    target_ratio = target_w / target_h
    img_ratio = iw / ih
    if img_ratio >= target_ratio:
        return clip.resize(height=target_h)
    else:
        return clip.resize(width=target_w)

def ease_in_out(t):
    """Smooth start and end movement using a cosine curve."""
    return 0.5 * (1 - np.cos(np.pi * t))

def ken_burns_clip(img_path, duration, size=(1920, 1080),
                      zoom_start=1.0, zoom_end=1.15, pan="auto", 
                      ease=True):
    """
    High-Quality Ken Burns effect.
    Operations are performed on the full-resolution image using a virtual camera (crop),
    preserving detail and avoiding jitter.
    """
    W, H = size
    target_ratio = W / H
    
    # Load image at FULL resolution
    img = ImageClip(img_path)
    iw, ih = img.size
    img_ratio = iw / ih

    # 1. Geometry: Calculate the "Playable Area" (Crop to Aspect Ratio)
    # We first determine the largest box within the image that matches the target aspect ratio.
    if img_ratio >= target_ratio:
        # Image is wider than target; crop width
        crop_h = ih
        crop_w = ih * target_ratio
    else:
        # Image is taller than target; crop height
        crop_w = iw
        crop_h = iw / target_ratio
        
    # Center the playable area on the source image
    x_offset = (iw - crop_w) / 2
    y_offset = (ih - crop_h) / 2

    # 2. Logic: Define Pan/Zoom dynamics
    if pan == "auto":
        pan = random.choice(["left", "right", "up", "down", "in", "out"])

    # Determine Zoom Levels relative to the "Playable Area"
    # Note: If pan is 'out', we swap start/end logic
    z0, z1 = (zoom_start, zoom_end)
    if pan == "out":
        z0, z1 = zoom_end, zoom_start

    # Helper to get progress 0.0 -> 1.0
    def get_progress(t):
        p = t / duration
        return ease_in_out(p) if ease else p

    # 3. The Virtual Camera (Crop Box) Calculation
    # We calculate the crop box (x, y, w, h) for every frame t.
    
    def get_crop_params(t):
        p = get_progress(t)
        
        # Interpolate Zoom
        current_zoom = z0 + (z1 - z0) * p
        
        # Calculate Viewport Size (The camera window size)
        # As zoom increases, the view window gets smaller
        view_w = crop_w / current_zoom
        view_h = crop_h / current_zoom
        
        # Max allowable movement ("Overflow") within the Playable Area
        max_x = crop_w - view_w
        max_y = crop_h - view_h
        
        # Interpolate Position
        # pan='left' means the IMAGE moves left, so the CAMERA moves Right (0 -> max_x)
        if pan == "left":
            px = max_x * p
            py = max_y / 2 # Center Y
        elif pan == "right":
            px = max_x * (1 - p)
            py = max_y / 2
        elif pan == "up":
            px = max_x / 2
            py = max_y * p # Camera moves down
        elif pan == "down":
            px = max_x / 2
            py = max_y * (1 - p)
        elif pan in ["in", "out"]:
            # Center Zoom
            px = max_x / 2
            py = max_y / 2
            
        # Add the offset from the original aspect-ratio crop
        final_x = x_offset + px
        final_y = y_offset + py
        
        return final_x, final_y, view_w, view_h

    # 4. Apply the dynamic crop and resize to final output
    return (img
            .fl(lambda gf, t: gf(t)[
                int(get_crop_params(t)[1]):int(get_crop_params(t)[1] + get_crop_params(t)[3]),
                int(get_crop_params(t)[0]):int(get_crop_params(t)[0] + get_crop_params(t)[2])
            ])
            .resize(newsize=size)
            .set_duration(duration))

# NOTE: The .fl() method above is a manual implementation of dynamic cropping 
# because moviepy's clip.crop() can sometimes be tricky with lambdas in older versions.
# If you prefer the cleaner moviepy syntax, replace step #4 with:
    
    # return (img
    #         .crop(x1=lambda t: get_crop_params(t)[0],
    #               y1=lambda t: get_crop_params(t)[1],
    #               width=lambda t: get_crop_params(t)[2],
    #               height=lambda t: get_crop_params(t)[3])
    #         .resize(newsize=size)
    #         .set_duration(duration))

def ken_burns_clip_jan10_2026(img_path, duration, size=(1920,1080),
                   zoom_start=1.05, zoom_end=1.15, pan="auto",
                   overscan=1.01):
    """
    Ken Burns with dynamic overflow so the frame is always fully covered.
    `overscan` adds a tiny extra scale to avoid 1px slivers from rounding.
    """
    import random
    from moviepy.editor import ImageClip, CompositeVideoClip

    W, H = size
    base = ImageClip(img_path)
    # Resize once to COVER the canvas; at scale=1 we already fill the frame
    def cover_resize(clip, target_w, target_h):
        iw, ih = clip.size
        target_ratio = target_w / target_h
        img_ratio = iw / ih
        if img_ratio >= target_ratio:
            return clip.resize(height=target_h)
        else:
            return clip.resize(width=target_w)
    base = cover_resize(base, W, H)

    if pan == "auto":
        pan = random.choice(["left", "right", "up", "down", "in", "out"])

    # Swap zoom if "out" so it feels like zooming out
    z0, z1 = (zoom_start, zoom_end)
    if pan == "out":
        z0, z1 = zoom_end, zoom_start

    # Scale is always >= 1 (because base is already COVERed) and we add overscan
    def scale_at(t):
        s = z0 + (z1 - z0) * (t / duration)
        return s * overscan

    # Position now uses the *current* overflow at time t so we never reveal borders
    def pos_at(t):
        s = scale_at(t)
        sw, sh = base.w * s, base.h * s
        overflow_x = max(0, sw - W)
        overflow_y = max(0, sh - H)

        if pan in ("left", "right"):
            start_x = 0 if pan == "left" else -overflow_x
            end_x   = -overflow_x if pan == "left" else 0
            x = start_x + (end_x - start_x) * (t / duration)
            y = 0
        elif pan in ("up", "down"):
            start_y = 0 if pan == "up" else -overflow_y
            end_y   = -overflow_y if pan == "up" else 0
            y = start_y + (end_y - start_y) * (t / duration)
            x = 0
        elif pan == "in":
            x = -overflow_x * (t / duration) * 0.6
            y = -overflow_y * (t / duration) * 0.6
        elif pan == "out":
            x = -overflow_x * (1 - (t / duration)) * 0.6
            y = -overflow_y * (1 - (t / duration)) * 0.6
        else:
            x = y = 0
        return (x, y)

    kb = (base
          .fx(lambda c: c.resize(lambda t: scale_at(t)))
          .set_position(lambda t: pos_at(t))
          .set_duration(duration))

    return CompositeVideoClip([kb], size=size).set_duration(duration)


# def ken_burns_clip(img_path, duration, size=(1920,1080),
#                    zoom_start=1.05, zoom_end=1.15, pan="auto"):
    
def ken_burns_clip_DND(img_path, duration, size=(1920,1080),
                   zoom_start=1.05, zoom_end=1.15, pan="auto"):
    """Create a Ken Burns effect (slow zoom + gentle pan) on a single image."""
    W, H = size
    base = ImageClip(img_path)
    base = cover_resize(base, W, H)

    if pan == "auto":
        pan = random.choice(["left", "right", "up", "down", "in", "out"])

    # zoom direction
    z0, z1 = (zoom_start, zoom_end)
    if pan == "out":
        z0, z1 = zoom_end, zoom_start

    def scale_at(t):
        return z0 + (z1 - z0) * (t / duration)

    # compute overflow
    end_scaled_w, end_scaled_h = base.size[0] * z1, base.size[1] * z1
    overflow_x = max(0, end_scaled_w - W)
    overflow_y = max(0, end_scaled_h - H)

    def pos_at(t):
        if pan in ("left", "right"):
            start_x = 0 if pan == "left" else -overflow_x
            end_x   = -overflow_x if pan == "left" else 0
            x = start_x + (end_x - start_x) * (t / duration)
            y = 0
        elif pan in ("up", "down"):
            start_y = 0 if pan == "up" else -overflow_y
            end_y   = -overflow_y if pan == "up" else 0
            y = start_y + (end_y - start_y) * (t / duration)
            x = 0
        elif pan == "in":
            x = -overflow_x * (t / duration) * 0.6
            y = -overflow_y * (t / duration) * 0.6
        elif pan == "out":
            x = -overflow_x * (1 - (t / duration)) * 0.6
            y = -overflow_y * (1 - (t / duration)) * 0.6
        else:
            x = y = 0
        return (x, y)

    kb = (base
          .fx(lambda c: c.resize(lambda t: scale_at(t)))
          .set_position(lambda t: pos_at(t))
          .set_duration(duration))

    return CompositeVideoClip([kb], size=size).set_duration(duration)

def _ffprobe_duration(path: str) -> float:
    """Return duration in seconds using ffprobe (format duration)."""
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ], universal_newlines=True).strip()
        return float(out)
    except Exception:
        # MoviePy fallback (slower but robust)
        try:
            return float(VideoFileClip(path).duration)
        except Exception:
            return 0.0

def export_kb_videos(input_folder, out_folder,
                     per_image=10, output_size=(1920,1080),
                     zoom_start=1.05, zoom_end=1.15, fps=30, only_select_images_without_video=False):
    os.makedirs(out_folder, exist_ok=True)
    print("Received export_kb_videos Arguments:", locals())
    # clear_folder(out_folder)

    exts = ("*.jpg","*.jpeg","*.png","*.webp")
    images = []
    for e in exts:
        images.extend(glob(os.path.join(input_folder, e)))
    if not images:
        raise RuntimeError(f"No images found in {input_folder}")

    #DND - Working
    #pan_cycle = ["left", "right", "up", "down", "in", "out"]

    pan_cycle = [ "left", "right", "up", "down" ]  # removed in/out for subtlety
    for idx, img in enumerate(sorted(images)):

        if only_select_images_without_video:
            base = os.path.splitext(os.path.basename(img))[0]
            corresponding_video_path = os.path.join("downloads", f"{base}.mp4")
            if os.path.exists(corresponding_video_path):
                try:
                    full_d = _ffprobe_duration(corresponding_video_path) or 0.0
                    if full_d > 0:
                        print(f"Skipping (video exists): {corresponding_video_path} with duration {full_d}")
                        continue
                    else:
                        print(f"Duration check failed for {corresponding_video_path}. Proceeding to create KB video.")
                except Exception as e:
                    print(f"Duration exception for {corresponding_video_path}: {e}. Proceeding to create KB video.")

        pan = pan_cycle[idx % len(pan_cycle)]
        base = os.path.splitext(os.path.basename(img))[0]
        #DND
        #out_path = os.path.join(out_folder, f"{base}_{pan}.mp4")
        out_path = os.path.join(out_folder, f"{base}.mp4")
        if os.path.exists(out_path):
            print(f"Skipping (exists): {out_path}")
            continue

        # Calculate a dynamic zoom based on duration to keep it interesting
        # e.g., if duration is 30s, zoom end is 1.25. If 10s, zoom end is 1.15
        dyn_zoom_end = 1.15 + (0.10 * (per_image / 30))

        clip = ken_burns_clip(img, duration=per_image, size=output_size,
                              zoom_start=zoom_start, zoom_end=dyn_zoom_end, pan=pan)
        clip.write_videofile(
            out_path,
            fps=fps,
            codec="libx264",
            audio=False,
            threads=4,
            preset="veryfast"
        )
        clip.close()

        if input_folder == "edit_vid_input":
            print(f"Deleting source image: {img}")
            os.remove(img)

def clear_folder(folder_path, extensions=None):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    for file in os.listdir(folder_path):
        full_path = os.path.join(folder_path, file)
        if os.path.isfile(full_path):
            if not extensions or file.lower().endswith(extensions):
                os.remove(full_path)

if __name__ == "__main__":
    export_kb_videos(
        input_folder="edit_vid_input",   # folder with images
        out_folder="edit_vid_output",    # where to save KB clips
        per_image=10,
        output_size=(1920,1080),
        zoom_start=1.0, zoom_end=1.05
    )
