import argparse, os, random, math
from glob import glob
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips

def cover_resize(clip, target_w, target_h):
    """Resize image to fully cover the target canvas (like CSS object-fit: cover)."""
    iw, ih = clip.size
    target_ratio = target_w / target_h
    img_ratio = iw / ih
    if img_ratio >= target_ratio:
        # image is wider -> match height
        return clip.resize(height=target_h)
    else:
        # image is taller -> match width
        return clip.resize(width=target_w)

def ken_burns_clip(img_path, duration, size=(1920,1080), zoom_start=1.05, zoom_end=1.15, pan="auto"):
    """
    Create a Ken Burns effect (slow zoom + gentle pan) on a single image.
    pan: "in", "out", "left", "right", "up", "down", or "auto"
    """
    W, H = size
    base = ImageClip(img_path)
    base = cover_resize(base, W, H)  # start by covering the canvas at scale=1.0

    # choose a pan direction if auto
    if pan == "auto":
        pan = random.choice(["left", "right", "up", "down", "in", "out"])

    # we’ll apply a time-dependent scale and position
    # scale(t): linear from zoom_start -> zoom_end
    def scale_at(t):
        return zoom_start + (zoom_end - zoom_start) * (t / duration)

    # compute max overflow at end scale (approx) for safe panning range
    end_scaled_w, end_scaled_h = base.size[0] * zoom_end, base.size[1] * zoom_end
    overflow_x = max(0, end_scaled_w - W)
    overflow_y = max(0, end_scaled_h - H)

    # define panning paths (small, subtle)
    def pos_at(t):
        # start & end offsets (negative values move image left/up inside canvas)
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
            # zoom in, slight diagonal
            x = -overflow_x * (t / duration) * 0.6
            y = -overflow_y * (t / duration) * 0.6
        elif pan == "out":
            # zoom out effect simulated by reversing zoom direction below (we’ll swap start/end)
            x = -overflow_x * (1 - (t / duration)) * 0.6
            y = -overflow_y * (1 - (t / duration)) * 0.6
        else:
            x = y = 0
        return (x, y)

    # If "out", swap zoom start/end to feel like zooming out
    z0, z1 = (zoom_start, zoom_end)
    if pan == "out":
        z0, z1 = zoom_end, zoom_start

    def scale_at_outdir(t):
        return z0 + (z1 - z0) * (t / duration)

    # Apply dynamic resize + position via functions of t
    kb = (base
          .fx(lambda c: c.resize(lambda t: scale_at_outdir(t)))
          .set_position(lambda t: pos_at(t))
          .set_duration(duration))

    # Composite into fixed canvas to guarantee exact 1920x1080 with cropping if needed
    return CompositeVideoClip([kb], size=size).set_duration(duration)

def build_video(images, audio_path, out_path, per_image=10, size=(1920,1080),
                zoom_start=1.05, zoom_end=1.15, fps=30):
    # Load audio to determine target duration
    audio = AudioFileClip(audio_path)
    audio_duration = audio.duration
    clear_folder("edit_vid_output")
    # How many images are needed?
    needed = math.ceil(audio_duration / per_image)
    if len(images) == 0:
        raise RuntimeError("No images found in the specified folder.")

    # If fewer images than needed, loop through them; else take first N (or shuffle for randomness)
    imgs = images[:]
    random.shuffle(imgs)
    picks = (imgs * ((needed // len(imgs)) + 1))[:needed]

    # Create clips
    clips = []
    pan_cycle = ["left", "right", "up", "down", "in", "out"]
    for idx, img in enumerate(picks):
        pan = pan_cycle[idx % len(pan_cycle)]
        clip = ken_burns_clip(img, duration=per_image, size=size,
                              zoom_start=zoom_start, zoom_end=zoom_end, pan=pan)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")

    # Set audio and trim video to match audio duration exactly
    video = video.set_audio(audio).set_duration(audio_duration)

    # Render
    video.write_videofile(
        out_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        temp_audiofile="__temp_audio.m4a",
        remove_temp=True
    )

def clear_folder(folder_path, extensions=None):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    for file in os.listdir(folder_path):
        full_path = os.path.join(folder_path, file)
        if os.path.isfile(full_path):
            if not extensions or file.lower().endswith(extensions):
                os.remove(full_path)

# Example usage with parameters instead of argparse
# if __name__ == "__main__":
#     build_video(
#         input_folder="edit_vid_input",
#         audio_path="song.mp3",
#         output_path="edit_vid_output/final_video.mp4",
#         output_size=(1920,1080),
#         per_image=10
#     )

# def main():
#     parser = argparse.ArgumentParser(description="Create devotional slideshow with Ken Burns and attach audio.")
#     parser.add_argument("--images_dir", required=True, help="Folder containing landscape images (jpg/png).")
#     parser.add_argument("--audio", required=True, help="Path to audio file (mp3/wav/m4a).")
#     parser.add_argument("--output", default="final_video.mp4", help="Output video path.")
#     parser.add_argument("--per_image", type=int, default=10, help="Seconds per image (default: 10).")
#     parser.add_argument("--width", type=int, default=1920, help="Output width (default: 1920).")
#     parser.add_argument("--height", type=int, default=1080, help="Output height (default: 1080).")
#     parser.add_argument("--fps", type=int, default=30, help="Frames per second (default: 30).")
#     parser.add_argument("--zoom_start", type=float, default=1.05, help="Start zoom scale (default: 1.05).")
#     parser.add_argument("--zoom_end", type=float, default=1.15, help="End zoom scale (default: 1.15).")
#     args = parser.parse_args()

#     # Collect images
#     exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
#     files = []
#     for e in exts:
#         files.extend(glob(os.path.join(args.images_dir, e)))
#     files = sorted(files)
#     if not files:
#         raise RuntimeError(f"No images found in {args.images_dir}")

#     build_video(
#         files,
#         audio_path=args.audio,
#         out_path=args.output,
#         per_image=args.per_image,
#         size=(args.width, args.height),
#         zoom_start=args.zoom_start,
#         zoom_end=args.zoom_end,
#         fps=args.fps
#     )

# if __name__ == "__main__":
#     main()

def create_slideshow(input_folder, audio_folder, output_path,
                     output_size=(1920,1080), per_image=10,
                     zoom_start=1.05, zoom_end=1.15, fps=30):

    # collect images
    exts = ("*.jpg","*.jpeg","*.png","*.webp")
    images = []
    for e in exts:
        images.extend(glob(os.path.join(input_folder, e)))
    if not images:
        raise RuntimeError(f"No images found in {input_folder}")

    # find audio file inside the folder
    audio_exts = ("*.mp3","*.wav","*.m4a","*.aac")
    audio_files = []
    for e in audio_exts:
        audio_files.extend(glob(os.path.join(audio_folder, e)))
    if not audio_files:
        raise RuntimeError(f"No audio file found in {audio_folder}")
    audio_path = audio_files[0]   # pick first audio file

    # load audio
    audio = AudioFileClip(audio_path)
    audio_duration = audio.duration

    # determine how many images needed
    needed = math.ceil(audio_duration / per_image)
    random.shuffle(images)
    picks = (images * ((needed // len(images)) + 1))[:needed]

    # build clips
    clips = []
    pan_cycle = ["left","right","up","down","in","out"]
    for idx, img in enumerate(picks):
        pan = pan_cycle[idx % len(pan_cycle)]
        clips.append(
            ken_burns_clip(img, per_image, size=output_size,
                           zoom_start=zoom_start, zoom_end=zoom_end, pan=pan)
        )

    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio).set_duration(audio_duration)

    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4
    )

if __name__ == "__main__":
    create_slideshow(
        input_folder="edit_vid_input",        # folder with images
        audio_folder="edit_vid_audio",        # folder with your audio file
        output_path="edit_vid_output/final_video.mp4",
        output_size=(1920,1080),
        per_image=10
    )
