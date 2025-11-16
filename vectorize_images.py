import os
import subprocess
from pathlib import Path

# ====== CONFIGURE THESE TWO PATHS ======
INPUT_ROOT = Path("downloads")   # your source images root
OUTPUT_ROOT = Path("vector_images") # where SVGs will go
# =======================================

# Command for ImageMagick
# On most systems it's just "magick". If it doesn't work,
# you can put the full path to magick.exe here.
IMAGEMAGICK_CMD = "magick"

# File types to process
VALID_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def raster_to_svg(input_path: Path, output_path: Path, threshold: str = "60%"):
    """
    Convert a raster image to SVG using ImageMagick + Potrace.
    Preserves folder structure by using output_path provided.
    """
    # Make sure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Temporary PBM file (same folder as output to avoid cluttering input)
    pbm_path = output_path.with_suffix(".pbm")

    print(f"\n[INFO] Processing: {input_path}")
    print(f"[INFO]   -> Temp PBM: {pbm_path}")
    print(f"[INFO]   -> Output SVG: {output_path}")

    # 1) Convert raster -> 1-bit PBM using ImageMagick
    #    -threshold controls what becomes black vs white
    subprocess.run(
        [
            IMAGEMAGICK_CMD,
            str(input_path),
            "-threshold", threshold,  # adjust if needed (50–70% typical)
            "-monochrome",
            "-background", "white",
            "-flatten",
            str(pbm_path),
        ],
        check=True,
    )

    # 2) Convert PBM -> SVG via Potrace
    subprocess.run(
        [
            "potrace",
            str(pbm_path),
            "-s",                # output SVG
            "-o", str(output_path),
        ],
        check=True,
    )

    # 3) Remove temp PBM
    try:
        pbm_path.unlink()
    except FileNotFoundError:
        pass

    print(f"[OK]   Done: {output_path}")


def main():
    if not INPUT_ROOT.exists():
        print(f"ERROR: INPUT_ROOT does not exist: {INPUT_ROOT}")
        return

    print(f"Input root:  {INPUT_ROOT}")
    print(f"Output root: {OUTPUT_ROOT}")

    # Walk through all subfolders
    for dirpath, dirnames, filenames in os.walk(INPUT_ROOT):
        dirpath = Path(dirpath)
        for filename in filenames:
            if not filename.lower().endswith(VALID_EXTENSIONS):
                continue

            src_path = dirpath / filename

            # Relative path from INPUT_ROOT (e.g. "Animals/cat.png")
            rel_path = src_path.relative_to(INPUT_ROOT)

            # Build output SVG path under OUTPUT_ROOT, keeping same folders
            out_svg_path = OUTPUT_ROOT / rel_path
            out_svg_path = out_svg_path.with_suffix(".svg")

            try:
                raster_to_svg(src_path, out_svg_path, threshold="60%")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Failed on {src_path}: {e}")


if __name__ == "__main__":
    main()
