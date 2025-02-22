from moviepy.editor import *
from PIL import Image
import numpy as np
import cv2
import requests
from io import BytesIO
import os

def smoothstep(t):
    """Smoothstep easing function for smooth transitions (ease-in-out)."""
    return t * t * (3 - 2 * t)

def load_image(image_path):
    """
    Loads an image from a local path or URL.

    Args:
        image_path (str): Local file path or URL.

    Returns:
        The loaded image as a NumPy array (BGR format).
    """
    if image_path.startswith("http://") or image_path.startswith("https://"):
        try:
            response = requests.get(image_path, stream=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        except requests.exceptions.RequestException as e:
            print(f"Failed to load image from URL: {e}")
            return None
    else:
        return cv2.imread(image_path)

def add_zoom_effect(image_path, audio_duration, zoom_factor=1.05, output_size=(1920,1080)):
    """
    Applies a zoom effect on an image that is first upscaled to fill output_size.
    
    The image is upscaled (if needed) so that it fills the frame, and then a zoom
    effect is applied that linearly (with smoothstep easing) transitions the scale
    from 1.0 to zoom_factor.
    
    Args:
        image_path (str): Path to the image.
        audio_duration (float): Duration of the effect.
        zoom_factor (float): Final scale of the image at the end of the clip.
                              For a 5% zoom in, use 1.05.
        output_size (tuple): (width, height) of the output video.
        
    Returns:
        CompositeVideoClip with the zoom effect.
    """
    base_img = prepare_image(image_path, output_size)
    clip = ImageClip(base_img, duration=audio_duration)
    # Here we interpret zoom_factor as the final scaling value.
    zoom_clip = clip.resize(lambda t: 1 + (zoom_factor - 1) * smoothstep(t / audio_duration))
    zoom_clip = zoom_clip.fl_time(lambda t: t % audio_duration).set_duration(audio_duration)
    comp = CompositeVideoClip([zoom_clip.set_position("center")], size=output_size)
    return comp.set_duration(audio_duration)

def upscale_image_no_crop(image, scale):
    """
    Upscales an image by the given scale factor without cropping.
    
    Args:
        image (np.array): The input image.
        scale (float): Scale factor.
        
    Returns:
        The resized image.
    """
    orig_h, orig_w = image.shape[:2]
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)


def add_pan_effect(image_path, audio_duration, start_x, start_y, end_x, end_y,
                   output_size=(1920,1080), pan_scale=1.5):
    """
    Creates a pan effect by cropping a moving window from an upscaled image.
    
    For a pan effect, we want extra room. Instead of using our "cover" upscaling (which
    crops to exactly output_size), we upscale further (without cropping) so that the image
    is larger than the final frame.
    
    Args:
        image_path (str): Path to the image.
        audio_duration (float): Duration of the effect.
        start_x, start_y (int): Top-left crop coordinate at start.
        end_x, end_y (int): Top-left crop coordinate at end.
        output_size (tuple): (width, height) of the final video.
        pan_scale (float): Factor to upscale the image (without cropping) to provide room to pan.
        
    Returns:
        VideoClip with the pan effect.
    """
    # Load the original image (in BGR)
    img = load_image(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Ensure the image at least fills the output. If not, upscale using our "cover" strategy.
    orig_h, orig_w = img.shape[:2]
    target_w, target_h = output_size
    if orig_w < target_w or orig_h < target_h:
        # upscale_image() here upscales and then center crops to exactly output_size.
        img = upscale_image(img, output_size, min_scale=1.0)
    
    # Now upscale further without cropping so that the image is larger than output_size.
    large_img = upscale_image_no_crop(img, pan_scale)
    video_width, video_height = output_size

    def make_frame(t):
        progress = smoothstep(t / audio_duration)
        # Interpolate crop's top-left corner.
        cur_x = int(start_x + (end_x - start_x) * progress)
        cur_y = int(start_y + (end_y - start_y) * progress)
        
        h, w, _ = large_img.shape
        # Clamp coordinates so the window stays fully inside the large image.
        cur_x = max(0, min(cur_x, w - video_width))
        cur_y = max(0, min(cur_y, h - video_height))
        
        crop = large_img[cur_y:cur_y+video_height, cur_x:cur_x+video_width]
        if crop.size == 0:
            crop = np.zeros((video_height, video_width, 3), dtype=np.uint8)
        # (Optional) Ensure the crop is exactly output size.
        crop = cv2.resize(crop, (video_width, video_height))
        return cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

    return VideoClip(make_frame, duration=audio_duration).set_fps(24)




def create_camera_movement_clip_Linear(image_path, start_frame, end_frame, duration=5, fps=30):
    """
    Creates a video clip with linear camera movement or zoom effect on an image.
    
    Args:
        image_path (str): Path to the input image.
        start_frame (dict): {'width', 'height', 'left', 'top'} for the starting frame.
        end_frame (dict): {'width', 'height', 'left', 'top'} for the ending frame.
    
    Returns:
        VideoClip: The clip with the camera movement effect.
    """
    img = load_image(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at path: {image_path}")
    
    img_height, img_width, _ = img.shape
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920  # Output video base width
    video_height = int(video_width / start_aspect_ratio)

    # If the start and end frames are identical, apply zoom (Ken Burns) effect.
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )
    if is_zoom_out:
        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)
        zoom_clip = add_ken_burns_effect_DND(cropped_image_path, duration, 1.2, 1)
        zoom_clip = zoom_clip.resize(height=video_height, width=video_width)
        return zoom_clip

    def get_frame_at_time(t):
        progress = t / duration
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)

    def make_frame(t):
        width, height, left, top = get_frame_at_time(t)
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)
        frame = img[y1:y2, x1:x2]
        # Ensure aspect ratio matches the starting frame.
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]
        frame = cv2.resize(frame, (video_width, video_height))
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    video_clip = VideoClip(make_frame, duration=duration).set_fps(fps)
    return video_clip

def create_camera_movement_clip_nw(image_path, start_frame, end_frame, duration=5, fps=30, movement_easing='ease_in_out'):
    """
    Creates a video clip with non-linear camera movement or zoom effect on an image.
    
    Args:
        image_path (str): Path to the input image.
        start_frame (dict): Starting frame parameters.
        end_frame (dict): Ending frame parameters.
        movement_easing (str): Easing type ('linear' or 'ease_in_out').
    
    Returns:
        VideoClip: The clip with the camera movement effect.
    """
    img = load_image(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at path: {image_path}")
    
    img_height, img_width, _ = img.shape
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920
    video_height = int(video_width / start_aspect_ratio)
    
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )
    if is_zoom_out:
        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)
        zoom_clip = add_ken_burns_effect_DND(cropped_image_path, duration, 1.2, 1)
        zoom_clip = zoom_clip.resize(height=video_height, width=video_width)
        return zoom_clip

    def linear(t):
        return t

    def ease_in_out(t):
        return smoothstep(t)

    easing_function = {'linear': linear, 'ease_in_out': ease_in_out}.get(movement_easing, linear)

    def get_frame_at_time(t):
        progress = easing_function(t / duration)
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)

    def make_frame(t):
        width, height, left, top = get_frame_at_time(t)
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)
        frame = img[y1:y2, x1:x2]
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]
        frame = cv2.resize(frame, (video_width, video_height))
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    video_clip = VideoClip(make_frame, duration=duration).set_fps(fps)
    return video_clip

def create_camera_movement_clip(image_path, start_frame, end_frame, duration=5, fps=30, movement_percentage=70, img_animation='Zoom In'):
    """
    Creates a video clip with camera movement or zoom effect on an image.
    
    If the start and end frames are identical, a zoom effect is applied.
    
    Returns:
        VideoClip: The resulting clip.
    """
    img = load_image(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at path: {image_path}")
    img_height, img_width, _ = img.shape
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920
    video_height = int(video_width / start_aspect_ratio)
    
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )
    if is_zoom_out:
        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)
        if img_animation == '':
            still_clip = ImageSequenceClip([cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB)], durations=[duration])
            still_clip = still_clip.resize(height=video_height, width=video_width).set_position("center")
            return still_clip
        else:
            zoom_clip = add_zoom_effect(cropped_image_path, duration, zoom_factor=1.2, output_size=(1920,1080))
            return zoom_clip
            #SM-DND-Working but not smooth
            # start_zoom = 1.2
            # end_zoom = 1
            # def make_zoom_frame(t, last_progress=[0]):
            #     progress = smoothstep(t / duration)
            #     progress = max(progress, last_progress[0])
            #     last_progress[0] = progress
            #     zoom_factor = start_zoom + (end_zoom - start_zoom) * progress
            #     zoom_width = int(cropped_img.shape[1] / zoom_factor)
            #     zoom_height = int(cropped_img.shape[0] / zoom_factor)
            #     left_crop = (cropped_img.shape[1] - zoom_width) // 2
            #     top_crop = (cropped_img.shape[0] - zoom_height) // 2
            #     frame = cropped_img[top_crop:top_crop + zoom_height, left_crop:left_crop + zoom_width]
            #     frame = cv2.resize(frame, (cropped_img.shape[1], cropped_img.shape[0]), interpolation=cv2.INTER_LANCZOS4)
            #     return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # zoom_clip = VideoClip(make_zoom_frame, duration=duration).set_fps(24)
            # zoom_clip = zoom_clip.fl_time(lambda t: t % duration)
            # zoom_clip = zoom_clip.resize(height=video_height, width=video_width).set_position("center")
            # return zoom_clip

    def easing_progress(t, duration, movement_percentage):
        movement_factor = movement_percentage / 100
        linear_progress = t / duration
        if linear_progress < movement_factor:
            return (linear_progress / movement_factor) ** (1/3)
        else:
            remaining_factor = 1 - movement_factor
            return movement_factor + ((linear_progress - movement_factor) / remaining_factor) ** 3 * (1 - movement_factor)

    def get_frame_at_time(t, duration, start_frame, end_frame, aspect_ratio, movement_percentage=80, last_progress=[-1]):
        progress = easing_progress(t, duration, movement_percentage)
        if last_progress[0] != -1:
            progress = max(progress, last_progress[0])
        last_progress[0] = progress
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / aspect_ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return width, height, left, top

    def make_frame(t):
        width, height, left, top = get_frame_at_time(t, duration, start_frame, end_frame, start_aspect_ratio, movement_percentage)
        x1 = max(0, int(left))
        y1 = max(0, int(top))
        x2 = min(x1 + int(width), img_width)
        y2 = min(y1 + int(height), img_height)
        frame = img[y1:y2, x1:x2]
        frame = cv2.resize(frame, (video_width, video_height), interpolation=cv2.INTER_LANCZOS4)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    return VideoClip(make_frame, duration=duration).set_fps(fps)

def create_camera_movement_video_Linear_motion(image_path, start_frame, end_frame, output_path='output.mp4', duration=5, fps=30):
    """
    Creates a video with linear camera movement or zoom effect on an image and saves it.
    """
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )
    if is_zoom_out:
        img = load_image(image_path)
        if img is None:
            print("Failed to load image. Exiting.")
            return
        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)
        zoom_clip = add_ken_burns_effect_DND(cropped_image_path, duration, 1.2, 1)
        start_aspect_ratio = start_frame['width'] / start_frame['height']
        video_width = 1920
        video_height = int(video_width / start_aspect_ratio)
        zoom_clip = zoom_clip.resize(height=video_height, width=video_width)
        zoom_clip.write_videofile(output_path, fps=fps)
        return
    img = load_image(image_path)
    if img is None:
        print("Failed to load image. Exiting.")
        return
    img_height, img_width, _ = img.shape
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920
    video_height = int(video_width / start_aspect_ratio)
    def get_frame_at_time(t):
        progress = t / duration
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))
    for i in range(int(duration * fps)):
        t = i / fps
        width, height, left, top = get_frame_at_time(t)
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)
        frame = img[y1:y2, x1:x2]
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]
        frame = cv2.resize(frame, (video_width, video_height))
        out.write(frame)
    out.release()

def create_camera_movement_video(image_path, start_frame, end_frame, output_path='output.mp4', duration=5, fps=30, movement_percentage=80):
    """
    Creates a video with non-linear camera movement or zoom effect on an image and saves it.
    """
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )
    if is_zoom_out:
        img = load_image(image_path)
        if img is None:
            print("Failed to load image. Exiting.")
            return
        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)
        zoom_clip = add_ken_burns_effect_DND(cropped_image_path, duration, 1.2, 1)
        start_aspect_ratio = start_frame['width'] / start_frame['height']
        video_width = 1920
        video_height = int(video_width / start_aspect_ratio)
        zoom_clip = zoom_clip.resize(height=video_height, width=video_width)
        zoom_clip.write_videofile(output_path, fps=fps)
        return
    img = load_image(image_path)
    if img is None:
        print("Failed to load image. Exiting.")
        return
    img_height, img_width, _ = img.shape
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920
    video_height = int(video_width / start_aspect_ratio)
    def get_frame_at_time(t, movement_percentage=80):
        movement_percentage = max(0, min(movement_percentage, 100))
        movement_factor = movement_percentage / 100
        linear_progress = t / duration
        if linear_progress < movement_factor:
            progress = (linear_progress / movement_factor) ** (1/3)
        else:
            remaining_factor = 1 - movement_factor
            progress = movement_factor + ((linear_progress - movement_factor) / remaining_factor) ** 3 * (1 - movement_factor)
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))
    for i in range(int(duration * fps)):
        t = i / fps
        width, height, left, top = get_frame_at_time(t, movement_percentage)
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)
        frame = img[y1:y2, x1:x2]
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]
        frame = cv2.resize(frame, (video_width, video_height))
        out.write(frame)
    out.release()

def add_ken_burns_effect_DND(image_path, audio_duration, start_zoom=1, end_zoom=1.2):
    """
    Adds a Ken Burns effect with smooth pan and zoom.
    """
    clip = ImageClip(image_path, duration=audio_duration)
    def resize_frame(get_frame, t):
        frame = get_frame(t)
        img_pil = Image.fromarray(frame)
        ease = smoothstep(t / audio_duration)
        zoom_factor = start_zoom + (end_zoom - start_zoom) * ease
        new_width = round(img_pil.width * zoom_factor)
        new_height = round(img_pil.height * zoom_factor)
        resized_img = img_pil.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)
        left = (new_width - clip.w) // 2
        top = (new_height - clip.h) // 2
        cropped_img = resized_img.crop((left, top, left + clip.w, top + clip.h))
        return np.array(cropped_img)
    try:
        zoom_clip = clip.fl(resize_frame, apply_to=['image'])
    except Exception as e:
        print(f"Error during resize: {e}")
        raise
    zoom_clip = zoom_clip.fl_time(lambda t: t % audio_duration)
    return zoom_clip.set_position("center").set_duration(audio_duration)

def add_ken_burns_effect(image_path, audio_duration, start_zoom=1.2, end_zoom=1, output_size=(1920,1080)):
    """
    Applies a Ken Burns effect (pan & zoom) on the image using smooth easing.
    The effect scales the image from start_zoom to end_zoom over the duration.
    
    Args:
        image_path (str): Path to the image.
        audio_duration (float): Duration of the effect.
        start_zoom (float): Zoom factor at the beginning.
        end_zoom (float): Zoom factor at the end.
        output_size (tuple): The output (width, height). (Optional)
        
    Returns:
        VideoClip with the Ken Burns effect.
    """
    try:
        # Prepare the image so that it exactly fills the output size with the correct aspect ratio.
        base_img = prepare_image(image_path, output_size)  # prepare_image converts to RGB
        clip = ImageClip(base_img, duration=audio_duration)
        zoom_clip = clip.resize(lambda t: start_zoom + (end_zoom - start_zoom) * smoothstep(t / audio_duration))
        zoom_clip = zoom_clip.fl_time(lambda t: t % audio_duration).set_duration(audio_duration)
        comp = CompositeVideoClip([zoom_clip.set_position("center")], size=output_size)
        return comp.set_duration(audio_duration)
    except Exception as e:
        clip = ImageClip(image_path, duration=audio_duration)
        def resize_frame(get_frame, t):
            frame = get_frame(t)
            img_pil = Image.fromarray(frame)
            ease = smoothstep(t / audio_duration)
            zoom_factor = start_zoom + (end_zoom - start_zoom) * ease
            new_width = round(img_pil.width * zoom_factor)
            new_height = round(img_pil.height * zoom_factor)
            resized_img = img_pil.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)
            left = (new_width - clip.w) // 2
            top = (new_height - clip.h) // 2
            cropped_img = resized_img.crop((left, top, left + clip.w, top + clip.h))
            return np.array(cropped_img)
        try:
            zoom_clip = clip.fl(resize_frame, apply_to=['image'])
        except Exception as e:
            print(f"Error during resize: {e}")
            raise
        zoom_clip = zoom_clip.fl_time(lambda t: t % audio_duration)
        return zoom_clip.set_position("center").set_duration(audio_duration)


def create_stylized_video(image_files, audio_files, output_file="final_video.mp4"):
    """
    Creates a final video by applying a Ken Burns effect to each image paired with audio.
    """
    video_clips = []
    for idx, (image_file, audio_file) in enumerate(zip(image_files, audio_files)):
        audio_clip = AudioFileClip(audio_file)
        audio_duration = audio_clip.duration
        video_clip = add_ken_burns_effect(image_file, audio_duration)
        video_clip = video_clip.set_audio(audio_clip)
        video_clips.append(video_clip)
    final_video = concatenate_videoclips(video_clips, method="compose")
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac")

def upscale_image(image, output_size=(1920,1080), min_scale=1.0):
    """
    Upscales an image so that it covers the output_size.
    
    The image is resized by a scale factor = max(target_width/orig_width, target_height/orig_height, min_scale)
    and then center-cropped to exactly output_size.
    
    Args:
        image (np.array): Input image.
        output_size (tuple): (width, height) target.
        min_scale (float): Minimum scale factor to apply.
        
    Returns:
        Upscaled and cropped image.
    """
    target_w, target_h = output_size
    orig_h, orig_w = image.shape[:2]
    base_scale = max(target_w / orig_w, target_h / orig_h)
    scale_factor = max(base_scale, min_scale)
    new_w = int(orig_w * scale_factor)
    new_h = int(orig_h * scale_factor)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    # Center crop:
    x_start = (new_w - target_w) // 2
    y_start = (new_h - target_h) // 2
    cropped = resized[y_start:y_start+target_h, x_start:x_start+target_w]
    return cropped

def prepare_image(image_path, output_size=(1920,1080)):
    """
    Loads an image and upscales it so that it exactly fills the output_size.
    Then converts the image from BGR to RGB.
    """
    img = load_image(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {image_path}")
    upscaled = upscale_image(img, output_size, min_scale=1.0)
    # Convert from BGR to RGB before returning.
    return cv2.cvtColor(upscaled, cv2.COLOR_BGR2RGB)


def run_tests():
    """
    Test various video effects and movement functions.
    
    This function assumes the existence of:
      - "sample.jpg": a sample image file.
      - "sample.mp3": a sample audio file.
      
    It creates short video files for the zoom effect, pan effect, Ken Burns effect,
    camera movement, and a stylized video combining image and audio.
    """
    # Parameters for testing
    sample_image = "cropped_frame.png"

    sample_audio = "sounds/bird.wav"
    duration = 5        # seconds
    fps = 24

    #SM-DND-Working
    print("Testing add_zoom_effect...")

    #SM-DND-Working
    zoom_clip = add_zoom_effect(sample_image, duration, zoom_factor=1.1)
    zoom_clip.write_videofile("temp/test_zoom_effect.mp4", fps=fps)
    
    print("Testing add_pan_effect...")
    #SM-DND-Working but too much movement
    #pan_clip = add_pan_effect(sample_image, duration, start_x=0, end_x=1920, start_y=0, end_y=1080)
    
    pan_clip = add_pan_effect(sample_image, duration, 
                          start_x=0, end_x=192, 
                          start_y=0, end_y=108, 
                          output_size=(1920, 1080), 
                          pan_scale=1.5)
    pan_clip.write_videofile("temp/test_pan_effect.mp4", fps=fps)
    
    print("Testing add_ken_burns_effect...")
    ken_burns_clip = add_ken_burns_effect(sample_image, duration, start_zoom=1.2, end_zoom=1)
    ken_burns_clip.write_videofile("temp/test_ken_burns_effect.mp4", fps=fps)
    
    # Test camera movement clip using linear interpolation
    start_frame = {"width": 640, "height": 480, "left": 0, "top": 0}
    end_frame   = {"width": 640, "height": 480, "left": 50, "top": 50}
    print("Testing create_camera_movement_clip_Linear...")
    camera_clip_linear = create_camera_movement_clip_Linear(sample_image, start_frame, end_frame, duration, fps)
    camera_clip_linear.write_videofile("temp/test_camera_movement_linear.mp4", fps=fps)
    
    # Test non-linear camera movement clip
    print("Testing create_camera_movement_clip (non-linear)...")
    camera_clip_nonlinear = create_camera_movement_clip(
        sample_image, start_frame, end_frame, duration, fps, movement_percentage=80, img_animation="Zoom In"
    )
    camera_clip_nonlinear.write_videofile("temp/test_camera_movement_nonlinear.mp4", fps=fps)

    # Define start_frame and end_frame to be identical to trigger zoom-out.
    # These values should correspond to a region within your image.
    start_frame = {
        "width": 640,    # width of the cropped region
        "height": 480,   # height of the cropped region
        "left": 100,     # x-coordinate of the top-left corner
        "top": 50        # y-coordinate of the top-left corner
    }
    # End frame is identical to start_frame to indicate a zoom-out effect.
    end_frame = {
        "width": 640,
        "height": 480,
        "left": 100,
        "top": 50
    }
    
    # Here, we choose 'Zoom In' for img_animation so that the zoom-out branch is used.
    # (Your code uses img_animation to decide whether to just show a still image or apply zoom.)
    clip = create_camera_movement_clip(sample_image, start_frame, end_frame, duration=duration, fps=fps, img_animation="Zoom In")
    
    # Write the result to a file.
    clip.write_videofile("temp/test_camera_movement_clip.mp4", fps=fps)
        
    # Test the stylized video function (combining image and audio)
    # print("Testing create_stylized_video...")
    # image_files = [sample_image, sample_image]  # using the same image for testing
    # audio_files = [sample_audio, sample_audio]
    # create_stylized_video(image_files, audio_files, output_file="temp/test_stylized_video.mp4")
    
    print("All tests completed.")


if __name__ == "__main__":
    run_tests()
