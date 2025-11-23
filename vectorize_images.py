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

#IMAGEMAGICK_CMD = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"
POTRACE_CMD      = r"C:\potrace\potrace.exe"

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
            POTRACE_CMD,
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


def main(source_subfolder: str | None = None):
    """
    Convert images inside downloads/<source_subfolder>
    into vector_images/<source_subfolder>.

    If source_subfolder is None → process entire downloads folder (old behavior).
    """

    input_root = INPUT_ROOT
    output_root = OUTPUT_ROOT

    if source_subfolder:
        source_subfolder = source_subfolder.strip().replace("\\", "/")
        input_root = INPUT_ROOT / source_subfolder
        output_root = OUTPUT_ROOT / source_subfolder

    if not input_root.exists():
        print(f"ERROR: Input folder does not exist: {input_root}")
        return {"ok": False, "error": f"Input folder does not exist: {input_root}"}

    print(f"Input root:  {input_root}")
    print(f"Output root: {output_root}")

    for dirpath, dirnames, filenames in os.walk(input_root):
        dirpath = Path(dirpath)
        for filename in filenames:
            if not filename.lower().endswith(VALID_EXTENSIONS):
                continue

            src_path = dirpath / filename

            # Compute relative path from this input_root
            rel_path = src_path.relative_to(input_root)

            # Output: vector_images/<source_subfolder>/<same structure>
            out_svg_path = output_root / rel_path
            out_svg_path = out_svg_path.with_suffix(".svg")

            try:
                raster_to_svg(src_path, out_svg_path, threshold="60%")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Failed on {src_path}: {e}")

    return {"ok": True, "message": f"Vector images created under {output_root}"}



if __name__ == "__main__":
    main()
