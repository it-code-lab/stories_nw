# make_kb_videos.py
import os, random
from glob import glob
from moviepy.editor import ImageClip, CompositeVideoClip

def cover_resize(clip, target_w, target_h):
    """Resize image to fully cover the target canvas (like CSS object-fit: cover)."""
    iw, ih = clip.size
    target_ratio = target_w / target_h
    img_ratio = iw / ih
    if img_ratio >= target_ratio:
        return clip.resize(height=target_h)
    else:
        return clip.resize(width=target_w)

# def ken_burns_clip(img_path, duration, size=(1920,1080),
#                    zoom_start=1.05, zoom_end=1.15, pan="auto"):
    
def ken_burns_clip(img_path, duration, size=(1920,1080),
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

def export_kb_videos(input_folder, out_folder,
                     per_image=10, output_size=(1920,1080),
                     zoom_start=1.05, zoom_end=1.15, fps=30):
    os.makedirs(out_folder, exist_ok=True)

    clear_folder(out_folder)

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
        pan = pan_cycle[idx % len(pan_cycle)]
        base = os.path.splitext(os.path.basename(img))[0]
        #DND
        #out_path = os.path.join(out_folder, f"{base}_{pan}.mp4")
        out_path = os.path.join(out_folder, f"{base}.mp4")
        if os.path.exists(out_path):
            print(f"Skipping (exists): {out_path}")
            continue

        clip = ken_burns_clip(img, duration=per_image, size=output_size,
                              zoom_start=zoom_start, zoom_end=zoom_end, pan=pan)
        clip.write_videofile(
            out_path,
            fps=fps,
            codec="libx264",
            audio=False,
            threads=4,
            preset="veryfast"
        )
        clip.close()
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
