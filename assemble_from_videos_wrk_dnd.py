# assemble_from_videos.py
import os, math, random
from glob import glob
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips

def _find_audio(audio_folder):
    audio_exts = ("*.mp3","*.wav","*.m4a","*.aac","*.flac","*.ogg")
    files = []
    for e in audio_exts:
        files.extend(glob(os.path.join(audio_folder, e)))
    if not files:
        raise RuntimeError(f"No audio file found in {audio_folder}")
    return sorted(files)[0]

def _find_videos(video_folder):
    video_exts = ("*.mp4","*.mov","*.mkv","*.webm")
    files = []
    for e in video_exts:
        files.extend(glob(os.path.join(video_folder, e)))
    if not files:
        raise RuntimeError(f"No video files found in {video_folder}")
    return sorted(files)

def assemble_videos(video_folder, audio_folder, output_path,
                    fps=30, shuffle=False):
    """
    Assemble videos (any durations) back-to-back until they reach the audio duration.
    The final clip is trimmed to fit exactly; the result is set to the audio's length.
    """

    clear_folder("edit_vid_output")

    # 1) Load audio + duration
    audio_path = _find_audio(audio_folder)
    audio = AudioFileClip(audio_path)
    audio_duration = audio.duration

    # 2) Collect candidate videos
    video_paths = _find_videos(video_folder)
    if shuffle:
        random.shuffle(video_paths)

    # 3) Build a "plan" of (path, use_duration) to exactly cover audio length
    remaining = audio_duration
    plan = []
    tiny = 0.02  # small epsilon to avoid float edge cases

    # Pre-read durations in a rotating fashion, trim the last one if needed
    vp_idx = 0
    while remaining > tiny:
        p = video_paths[vp_idx % len(video_paths)]
        # Open clip just to read its duration, then close
        tmp_clip = VideoFileClip(p)
        d = max(0.0, float(tmp_clip.duration))
        tmp_clip.close()

        if d <= tiny:
            # skip zero-length or problematic file
            vp_idx += 1
            continue

        use_d = min(d, remaining)
        plan.append((p, use_d))
        remaining -= use_d
        vp_idx += 1

    # 4) Create actual clips (trim last one if needed), concat, add audio, export
    clips = []
    for (p, use_d) in plan:
        c = VideoFileClip(p).without_audio()
        if use_d < (c.duration - tiny):
            c = c.subclip(0, use_d)
        clips.append(c)

    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio).set_duration(audio_duration)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        temp_audiofile="__temp_audio.m4a",
        remove_temp=True
    )

    # Cleanup
    for c in clips:
        try: c.close()
        except: pass
    try: audio.close()
    except: pass

def clear_folder(folder_path, extensions=None):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    for file in os.listdir(folder_path):
        full_path = os.path.join(folder_path, file)
        if os.path.isfile(full_path):
            if not extensions or file.lower().endswith(extensions):
                os.remove(full_path)


if __name__ == "__main__":
    assemble_videos(
        video_folder="edit_vid_input",                 # can be your KB clips folder or any video folder
        audio_folder="edit_vid_audio",                 # folder with your audio file
        output_path="edit_vid_output/final_video.mp4", # output file
        fps=30,
        shuffle=True                                  # set True to randomize clip order
    )





