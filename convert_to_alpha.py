import os
import subprocess

def convert_to_alpha_overlay(input_folder="overlays", output_folder="edit_vid_output", format="mov"):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if filename.lower().endswith((".mp4", ".mov", ".webm")):
            input_path = os.path.join(input_folder, filename)
            base_name = os.path.splitext(filename)[0]

            if format == "mov":
                output_path = os.path.join(output_folder, f"{base_name}_alpha.mov")
                codec = ["-c:v", "qtrle"]
                pixel_format = "yuva420p"
            elif format == "webm":
                output_path = os.path.join(output_folder, f"{base_name}_alpha.webm")
                codec = ["-c:v", "libvpx-vp9", "-auto-alt-ref", "0"]
                pixel_format = "yuva420p"
            else:
                raise ValueError("Format must be 'mov' or 'webm'.")

            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-vf", f"chromakey=0x00FF00:0.3:0.1,format={pixel_format}"
            ] + codec + [output_path]

            subprocess.run(cmd, check=True)
            print(f"✅ Converted: {output_path}")

if __name__ == "__main__":
    convert_to_alpha_overlay(format="mov")  # or format="webm"
