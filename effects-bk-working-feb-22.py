from moviepy.editor import *
from PIL import Image
import numpy as np  # Import numpy
import cv2
import numpy as np
from scipy.interpolate import CubicSpline
import requests
from io import BytesIO
import os

def add_zoom_effect(image_path, audio_duration, zoom_factor=0.9, start_pos="center", end_pos="center"):
    """
    Adds a zoom-in effect on an image over the audio duration.
    
    Args:
        image_path (str): Path to the image file.
        audio_duration (float): Duration for the zoom effect.
        zoom_factor (float): How much to zoom in or out (default 1.2).
        start_pos (str): Starting position ("center", "top", "bottom", "left", "right").
        end_pos (str): Ending position ("center", "top", "bottom", "left", "right").
        
    Returns:
        VideoClip: A clip with the zoom effect applied.
    """
    clip = ImageClip(image_path, duration=audio_duration)
    zoom_clip = clip.resize(lambda t: 1 + zoom_factor * t / audio_duration)
    return zoom_clip.set_position(("center", "center"))

def add_pan_effect(image_path, audio_duration, start_x=0, end_x=1920, start_y=0, end_y=1080):
    """
    Adds a smooth pan effect to the image.
    
    Args:
        image_path (str): Path to the image file.
        audio_duration (float): Duration for the pan effect.
        start_x (int): Start X position of the pan.
        end_x (int): End X position of the pan.
        start_y (int): Start Y position of the pan.
        end_y (int): End Y position of the pan.
        
    Returns:
        VideoClip: A clip with a pan effect applied.
    """
    clip = ImageClip(image_path, duration=audio_duration)
    pan_clip = clip.set_position(lambda t: (start_x + (end_x - start_x) * t / audio_duration, 
                                            start_y + (end_y - start_y) * t / audio_duration))
    return pan_clip

def load_image(image_path):
    """
    Loads an image from a local path or URL.

    Args:
        image_path: Path to the image file or a URL.

    Returns:
        The loaded image (as a NumPy array).
    """
    if image_path.startswith("http://") or image_path.startswith("https://"):
        # Handle URL
        try:
            response = requests.get(image_path, stream=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        except requests.exceptions.RequestException as e:
            print(f"Failed to load image from URL: {e}")
            return None
    else:
        # Handle local path
        return cv2.imread(image_path)


#DND-Working with Linear movement of duration
def create_camera_movement_clip_Linear(image_path, 
                                 start_frame, 
                                 end_frame, 
                                 duration=5, 
                                 fps=30):
    """
    Creates a video clip with camera movement or zoom effect on an image.

    Args:
        image_path: Path to the input image.
        start_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                     of the starting camera frame.
        end_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                   of the ending camera frame.
        duration: Duration of the video in seconds.
        fps: Frames per second for the video.

    Returns:
        A MoviePy video clip object with the camera movement effect.
    """
    from moviepy.editor import ImageClip, VideoClip
    import numpy as np
    import cv2

    def load_image(path):
        if path.startswith("http://") or path.startswith("https://"):
            try:
                response = requests.get(path, stream=True)
                if response.status_code == 200:
                    arr = np.asarray(bytearray(response.content), dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    return img
                else:
                    raise FileNotFoundError(f"Failed to download image from URL: {path}")
            except Exception as e:
                raise FileNotFoundError(f"Error downloading image: {e}")
        else:
            img = cv2.imread(path)
            if img is None:
                raise FileNotFoundError(f"Image not found at path: {path}")
            return img

    # Load the image
    img = load_image(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at path: {image_path}")

    # Determine if the effect is zoom-out
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )

    # Calculate image dimensions
    img_height, img_width, _ = img.shape

    # Calculate the aspect ratio from the start frame
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920  # Base width for output video
    video_height = int(video_width / start_aspect_ratio)

    if is_zoom_out:
        # video_clip = video_clip.set_fps(fps)
        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]

        # Save the cropped frame as a temporary file
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)
    
        zoom_clip = add_ken_burns_effect_DND(cropped_image_path, duration, 1.2, 1)

        start_aspect_ratio = start_frame['width'] / start_frame['height']

        zoom_clip = zoom_clip.resize(height=video_height, width=video_width)
        return zoom_clip

    # Define camera movement path (linear interpolation)
    def get_frame_at_time(t):
        progress = t / duration
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio  # Ensure consistent aspect ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)

    # Generate the video frames dynamically
    def make_frame(t):
        width, height, left, top = get_frame_at_time(t)

        # Adjust for out-of-bounds cropping
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)

        frame = img[y1:y2, x1:x2]

        # Ensure the cropped region matches the start frame's aspect ratio
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:  # Too wide
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:  # Too tall
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]

        # Resize the frame to the output video dimensions
        frame = cv2.resize(frame, (video_width, video_height))
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Create the video clip
    video_clip = VideoClip(make_frame, duration=duration)
    video_clip = video_clip.set_fps(fps)

    return video_clip

#Not working - Gemini
def create_camera_movement_clip_nw(image_path, 
                                 start_frame, 
                                 end_frame, 
                                 duration=5, 
                                 fps=30,
                                 movement_easing='ease_in_out'):
    """
    Creates a video clip with camera movement or zoom effect on an image.

    Args:
        image_path: Path to the input image.
        start_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                     of the starting camera frame.
        end_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                   of the ending camera frame.
        duration: Duration of the video in seconds.
        fps: Frames per second for the video.

    Returns:
        A MoviePy video clip object with the camera movement effect.
    """
    from moviepy.editor import ImageClip, VideoClip
    import numpy as np
    import cv2

    def load_image(path):
        if path.startswith("http://") or path.startswith("https://"):
            try:
                response = requests.get(path, stream=True)
                if response.status_code == 200:
                    arr = np.asarray(bytearray(response.content), dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    return img
                else:
                    raise FileNotFoundError(f"Failed to download image from URL: {path}")
            except Exception as e:
                raise FileNotFoundError(f"Error downloading image: {e}")
        else:
            img = cv2.imread(path)
            if img is None:
                raise FileNotFoundError(f"Image not found at path: {path}")
            return img

    # Load the image
    img = load_image(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at path: {image_path}")

    # Determine if the effect is zoom-out
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )

    # Calculate image dimensions
    img_height, img_width, _ = img.shape

    # Calculate the aspect ratio from the start frame
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920  # Base width for output video
    video_height = int(video_width / start_aspect_ratio)

    if is_zoom_out:
        # video_clip = video_clip.set_fps(fps)
        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]

        # Save the cropped frame as a temporary file
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)
    
        zoom_clip = add_ken_burns_effect_DND(cropped_image_path, duration, 1.2, 1)

        start_aspect_ratio = start_frame['width'] / start_frame['height']

        zoom_clip = zoom_clip.resize(height=video_height, width=video_width)
        return zoom_clip

    # Define easing functions
    def linear(t):
        return t

    def ease_in_out(t):
        if t < 0.5:
            return 4 * t * t
        else:
            return -1 + (4 - 4 * t) * t

    # Choose easing function based on input
    easing_function = {'linear': linear, 'ease_in_out': ease_in_out}.get(movement_easing, linear)


    # Define camera movement path
    def get_frame_at_time(t):
        progress = easing_function(t / duration)  # Apply easing
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio  # Ensure consistent aspect ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)

    # Generate the video frames dynamically
    def make_frame(t):
        width, height, left, top = get_frame_at_time(t)

        # Adjust for out-of-bounds cropping
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)

        frame = img[y1:y2, x1:x2]

        # Ensure the cropped region matches the start frame's aspect ratio
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:  # Too wide
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:  # Too tall
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]

        # Resize the frame to the output video dimensions
        frame = cv2.resize(frame, (video_width, video_height))
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Create the video clip
    video_clip = VideoClip(make_frame, duration=duration)
    video_clip = video_clip.set_fps(fps)

    return video_clip

#DND- Working - ChatGPT_Non Linear motion - Doing 80% movement during first 20% of movement durationdef create_camera_movement_clip(image_path, 
def create_camera_movement_clip(image_path, 
                                 start_frame, 
                                 end_frame, 
                                 duration=5, 
                                 fps=30, 
                                 movement_percentage=70,
                                 img_animation = 'Zoom In'):
    """
    Creates a video clip with camera movement or zoom effect on an image.

    Args:
        image_path: Path to the input image or a URL.
        start_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                     of the starting camera frame.
        end_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                   of the ending camera frame.
        duration: Duration of the video in seconds.
        fps: Frames per second for the video.
        movement_percentage: Percentage of total movement to occur in the initial portion 
                             of the duration (default is 80%).

    Returns:
        A MoviePy video clip object with the camera movement effect.
    """
    from moviepy.editor import VideoClip
    import numpy as np
    import cv2
    import requests

    def load_image(path):
        """Loads an image from a local file or URL."""
        if path.startswith("http://") or path.startswith("https://"):
            try:
                response = requests.get(path, stream=True)
                if response.status_code == 200:
                    arr = np.asarray(bytearray(response.content), dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is None:
                        raise ValueError("Failed to decode image from URL")
                    return img
                else:
                    raise FileNotFoundError(f"Failed to download image from URL: {path}")
            except Exception as e:
                raise FileNotFoundError(f"Error downloading image: {e}")
        else:
            img = cv2.imread(path)
            if img is None:
                raise FileNotFoundError(f"Image not found at path: {path}")
            return img

    def easing_progress(t, duration, movement_percentage):
        """Calculate easing progress based on time and movement percentage."""
        movement_factor = movement_percentage / 100
        linear_progress = t / duration

        if linear_progress < movement_factor:
            return (linear_progress / movement_factor) ** (1 / 3)  # Accelerated start
        else:
            remaining_factor = 1 - movement_factor
            return movement_factor + ((linear_progress - movement_factor) / remaining_factor) ** 3 * (1 - movement_factor)

    def get_frame_at_time(t, duration, start_frame, end_frame, aspect_ratio, movement_percentage=80, last_progress=[-1]):
        """Calculates the frame dimensions and position at time `t` with nonlinear camera movement."""
        progress = easing_progress(t, duration, movement_percentage)

        # Ensure progress is non-decreasing
        if last_progress[0] != -1:
            progress = max(progress, last_progress[0])

        # Update last progress
        last_progress[0] = progress

        # Interpolate frame dimensions and position
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / aspect_ratio  # Maintain consistent aspect ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])

        return width, height, left, top

    # Load the image
    img = load_image(image_path)
    img_height, img_width, _ = img.shape

    # Determine if the effect is zoom-out
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )

    # Aspect ratio and output dimensions
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920  # Base width for output video
    video_height = int(video_width / start_aspect_ratio)

    if is_zoom_out:
        # Load and crop the image to the starting frame
        img = load_image(image_path)
        if img is None:
            print("Failed to load image. Exiting.")
            return

        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]

        cropped_height, cropped_width, _ = cropped_img.shape

        # Save the cropped frame as a temporary file
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)

        # Set up the zoom clip

        start_zoom = 1.2
        end_zoom = 1

        def make_zoom_frame(t, last_progress=[0]):
            """
            Generate a frame for the zoom-out effect with smooth, non-linear motion.

            Args:
                t: Current time in the video.
                last_progress: Mutable container tracking the last progress value.

            Returns:
                A zoomed frame as a NumPy array.
            """
            # Calculate non-linear progress
            progress = easing_progress(t, duration, movement_percentage=80)

            # Ensure progress is non-decreasing
            progress = max(progress, last_progress[0])

            # Update last progress
            last_progress[0] = progress

            # Calculate zoom factor
            zoom_factor = start_zoom + (end_zoom - start_zoom) * progress

            # Calculate new dimensions based on zoom factor
            zoom_width = int(cropped_width / zoom_factor)
            zoom_height = int(cropped_height / zoom_factor)
            left = (cropped_width - zoom_width) // 2
            top = (cropped_height - zoom_height) // 2

            # Crop and resize the frame
            frame = cropped_img[top:top + zoom_height, left:left + zoom_width]
            frame = cv2.resize(frame, (cropped_width, cropped_height), interpolation=cv2.INTER_LANCZOS4)

            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if img_animation == '':
            # Convert image to a video clip with a fixed duration
            print("Creating still clip of duration " + str(duration))
            still_clip = ImageSequenceClip([cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB)], durations=[duration])

            start_aspect_ratio = start_frame['width'] / start_frame['height']        
            video_width = 1920  # Base width for output video
            video_height = int(video_width / start_aspect_ratio)

            still_clip = still_clip.resize(height=video_height, width=video_width)
            
            # Center the clip position
            still_clip = still_clip.set_position("center")

            return still_clip
        else:
            # Create the video clip
            zoom_clip = VideoClip(make_zoom_frame, duration=duration).set_fps(24)

            start_aspect_ratio = start_frame['width'] / start_frame['height']        
            video_width = 1920  # Base width for output video
            video_height = int(video_width / start_aspect_ratio)

            zoom_clip = zoom_clip.resize(height=video_height, width=video_width)  

            # Center the clip position
            zoom_clip = zoom_clip.set_position("center")

            return zoom_clip

    # General camera movement
    def make_frame(t):
        width, height, left, top = get_frame_at_time(
            t, duration, start_frame, end_frame, start_aspect_ratio, movement_percentage
        )

        x1 = max(0, int(left))
        y1 = max(0, int(top))
        x2 = min(x1 + int(width), img_width)
        y2 = min(y1 + int(height), img_height)

        frame = img[y1:y2, x1:x2]
        frame = cv2.resize(frame, (video_width, video_height), interpolation=cv2.INTER_LANCZOS4)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Create the video clip with camera movement
    return VideoClip(make_frame, duration=duration).set_fps(fps)




#DND - Working (Linear movement)
def create_camera_movement_video_Linear_motion(image_path, 
                                 start_frame, 
                                 end_frame, 
                                 output_path='output.mp4', 
                                 duration=5, 
                                 fps=30):
    """
    Creates a video with camera movement or zoom effect on an image.

    Args:
        image_path: Path to the input image.
        start_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                     of the starting camera frame.
        end_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                   of the ending camera frame.
        output_path: Path to save the output video.
        duration: Duration of the video in seconds.
        fps: Frames per second for the video.

    Returns:
        None
    """
    from moviepy.editor import ImageClip

    # Check if the start and end frames are the same (trigger zoom effect)
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )

    if is_zoom_out:
        # Crop the image to the selected frame
        img = load_image(image_path)
        if img is None:
            print("Failed to load image. Exiting.")
            return

        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]

        # Save the cropped frame as a temporary file
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)

        zoom_clip = add_ken_burns_effect_DND(cropped_image_path, duration, 1.2, 1)

        start_aspect_ratio = start_frame['width'] / start_frame['height']
        video_width = 1920  # Base width for output video
        video_height = int(video_width / start_aspect_ratio)

        zoom_clip = zoom_clip.resize(height=video_height, width=video_width)

        zoom_clip.write_videofile(output_path, fps=fps)        

        return

    # If not a zoom effect, proceed with the original camera movement logic
    img = load_image(image_path)
    if img is None:
        print("Failed to load image. Exiting.")
        return

    # Calculate image dimensions
    img_height, img_width, _ = img.shape

    # Calculate the aspect ratio from the start frame
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920  # Base width for output video
    video_height = int(video_width / start_aspect_ratio)

    # Define camera movement path (linear interpolation)
    def get_frame_at_time(t):
        progress = t / duration
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio  # Ensure consistent aspect ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)

    # Create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for MP4
    out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))

    # Generate frames for the video
    for i in range(int(duration * fps)):
        t = i / fps
        width, height, left, top = get_frame_at_time(t)

        # Adjust for out-of-bounds cropping
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)

        frame = img[y1:y2, x1:x2]

        # Ensure the cropped region matches the start frame's aspect ratio
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:  # Too wide
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:  # Too tall
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]

        # Resize the frame to the output video dimensions
        frame = cv2.resize(frame, (video_width, video_height))

        # Write the frame to the video
        out.write(frame)

    # Release the VideoWriter object
    out.release()

# With non linear movement progress, Doing 80% movement during first 20% movement duration
def create_camera_movement_video(image_path, 
                                 start_frame, 
                                 end_frame, 
                                 output_path='output.mp4', 
                                 duration=5, 
                                 fps=30,
                                 movement_percentage=80):
    """
    Creates a video with camera movement or zoom effect on an image.

    Args:
        image_path: Path to the input image.
        start_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                     of the starting camera frame.
        end_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                   of the ending camera frame.
        output_path: Path to save the output video.
        duration: Duration of the video in seconds.
        fps: Frames per second for the video.

    Returns:
        None
    """
    from moviepy.editor import ImageClip

    # Check if the start and end frames are the same (trigger zoom effect)
    is_zoom_out = (
        start_frame['width'] == end_frame['width'] and
        start_frame['height'] == end_frame['height'] and
        start_frame['left'] == end_frame['left'] and
        start_frame['top'] == end_frame['top']
    )

    if is_zoom_out:
        # Crop the image to the selected frame
        img = load_image(image_path)
        if img is None:
            print("Failed to load image. Exiting.")
            return

        x1, y1 = start_frame['left'], start_frame['top']
        x2, y2 = x1 + start_frame['width'], y1 + start_frame['height']
        cropped_img = img[y1:y2, x1:x2]

        # Save the cropped frame as a temporary file
        cropped_image_path = 'cropped_frame.png'
        cv2.imwrite(cropped_image_path, cropped_img)

        zoom_clip = add_ken_burns_effect_DND(cropped_image_path, duration, 1.2, 1)

        start_aspect_ratio = start_frame['width'] / start_frame['height']
        video_width = 1920  # Base width for output video
        video_height = int(video_width / start_aspect_ratio)

        zoom_clip = zoom_clip.resize(height=video_height, width=video_width)

        zoom_clip.write_videofile(output_path, fps=fps)        

        return

    # If not a zoom effect, proceed with the original camera movement logic
    img = load_image(image_path)
    if img is None:
        print("Failed to load image. Exiting.")
        return

    # Calculate image dimensions
    img_height, img_width, _ = img.shape

    # Calculate the aspect ratio from the start frame
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920  # Base width for output video
    video_height = int(video_width / start_aspect_ratio)

    def get_frame_at_time(t, movement_percentage=80):
        """
        Calculates the frame dimensions and position at time `t` with nonlinear camera movement.

        Args:
            t: Current time in the video.
            movement_percentage: Percentage of total movement to occur in the initial portion of the duration (default is 80%).

        Returns:
            Tuple containing width, height, left, and top of the frame at time `t`.
        """
        # Ensure movement_percentage is between 0 and 100
        movement_percentage = max(0, min(movement_percentage, 100))
        
        # Normalize to a factor of 0-1
        movement_factor = movement_percentage / 100
        
        # Map time to nonlinear progress based on movement factor
        linear_progress = t / duration
        if linear_progress < movement_factor:
            progress = (linear_progress / movement_factor) ** (1/3)  # Accelerate faster initially
        else:
            remaining_factor = 1 - movement_factor
            progress = movement_factor + ((linear_progress - movement_factor) / remaining_factor) ** 3 * (1 - movement_factor)

        # Interpolate width, height, left, and top
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio  # Ensure consistent aspect ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)


    # Create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for MP4
    out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))

    # Generate frames for the video
    for i in range(int(duration * fps)):
        t = i / fps
        width, height, left, top = get_frame_at_time(t, movement_percentage)

        # Adjust for out-of-bounds cropping
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)

        frame = img[y1:y2, x1:x2]

        # Ensure the cropped region matches the start frame's aspect ratio
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:  # Too wide
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:  # Too tall
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]

        # Resize the frame to the output video dimensions
        frame = cv2.resize(frame, (video_width, video_height))

        # Write the frame to the video
        out.write(frame)

    # Release the VideoWriter object
    out.release()





#working on Dell latitude and woring on precision  
def add_ken_burns_effect_DND(image_path, audio_duration, start_zoom=1, end_zoom=1.2):
    """Adds a Ken Burns effect with smooth pan and zoom."""
    clip = ImageClip(image_path, duration=audio_duration)

    def resize_frame(get_frame, t):
        frame = get_frame(t)
        img = Image.fromarray(frame)

        # Calculate smooth zoom factor
        zoom_factor = start_zoom + (end_zoom - start_zoom) * (t / audio_duration)
        
        # Ensure integer scaling
        new_width = round(img.width * zoom_factor)
        new_height = round(img.height * zoom_factor)

        # Resize with LANCZOS for better quality
        resized_img = img.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)

        # Calculate centered crop
        left = (new_width - clip.w) // 2
        top = (new_height - clip.h) // 2
        right = left + clip.w
        bottom = top + clip.h

        # Crop image to center
        cropped_img = resized_img.crop((left, top, right, bottom))
        return np.array(cropped_img)

    try:
        zoom_clip = clip.fl(resize_frame, apply_to=['image'])
    except Exception as e:
        print(f"Error during resize: {e}")
        raise

    return zoom_clip.set_position("center")

# Not working on Dell latitude but woring on precision  - smooth motion  
def add_ken_burns_effect(image_path, audio_duration, start_zoom=1.2, end_zoom=1):
    """
    Adds a Ken Burns effect with pan and zoom to the image.
    """
    try:
        clip = ImageClip(image_path, duration=audio_duration)
        zoom_clip = clip.resize(lambda t: start_zoom + (end_zoom - start_zoom) * t / audio_duration)
        return zoom_clip.set_position("center")
    except Exception as e:
        clip = ImageClip(image_path, duration=audio_duration)

        def resize_frame(get_frame, t):
            frame = get_frame(t)
            img = Image.fromarray(frame)

            # Calculate smooth zoom factor
            zoom_factor = start_zoom + (end_zoom - start_zoom) * (t / audio_duration)
            
            # Ensure integer scaling
            new_width = round(img.width * zoom_factor)
            new_height = round(img.height * zoom_factor)

            # Resize with LANCZOS for better quality
            resized_img = img.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)

            # Calculate centered crop
            left = (new_width - clip.w) // 2
            top = (new_height - clip.h) // 2
            right = left + clip.w
            bottom = top + clip.h

            # Crop image to center
            cropped_img = resized_img.crop((left, top, right, bottom))
            return np.array(cropped_img)

        try:
            zoom_clip = clip.fl(resize_frame, apply_to=['image'])
        except Exception as e:
            print(f"Error during resize: {e}")
            raise

        return zoom_clip.set_position("center")

def create_stylized_video(image_files, audio_files, output_file="final_video.mp4"):
    video_clips = []
    for idx, (image_file, audio_file) in enumerate(zip(image_files, audio_files)):
        audio_clip = AudioFileClip(audio_file)
        audio_duration = audio_clip.duration

        # Apply Effects
        video_clip = add_ken_burns_effect(image_file, audio_duration)
        video_clip = video_clip.set_audio(audio_clip)

        video_clips.append(video_clip)

    # Export Final Video
    final_video = concatenate_videoclips(video_clips, method="compose")
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac")
