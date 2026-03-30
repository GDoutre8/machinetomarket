"""
image_pack_generator.py
=======================
MTM Image Pack Generator

Given a folder of machine photos, produces platform-ready resized/cropped
images and packages everything into a ZIP file.

Pipeline (per image, in order):
  1. Auto-rotate from EXIF
  2. HEIC → JPG conversion
  3. Convert to sRGB
  4. Resize to cover target dimensions
  5. Center crop to exact aspect ratio
  6. Sharpen slightly
  7. Compress to web-friendly JPEG
  8. Export

Output structure:
  {output_folder}/
    images_original/
    images_4x5/
    images_1x1/
    images_9x16/
    thumbnails/
  {output_folder}.zip

Usage:
    from image_pack_generator import generate_image_pack
    result = generate_image_pack("path/to/photos", "path/to/output", "Bobcat_T770")
"""

import os
import io
import zipfile
import struct
import shutil
from pathlib import Path

from PIL import Image, ImageFilter, ImageCms

# Register HEIC/HEIF support if available
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False

try:
    import piexif
    PIEXIF_AVAILABLE = True
except ImportError:
    PIEXIF_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Platform targets
# ─────────────────────────────────────────────────────────────────────────────

TARGETS = {
    "4x5":   {"size": (1080, 1350), "suffix": "4x5",   "quality": 85},
    "1x1":   {"size": (1200, 1200), "suffix": "1x1",   "quality": 85},
    "9x16":  {"size": (1080, 1920), "suffix": "9x16",  "quality": 85},
    "thumb": {"size": (600,   600), "suffix": "thumb",  "quality": 75},
}

# Max file size goal (bytes) — soft target, we try subsampling
MAX_FILE_SIZE = 500 * 1024  # 500 KB

# sRGB ICC profile embedded in Pillow
_SRGB_PROFILE = ImageCms.createProfile("sRGB")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Auto-rotate from EXIF
# ─────────────────────────────────────────────────────────────────────────────

_EXIF_ORIENT_TAG = 274  # 0x0112

_ORIENT_TRANSFORMS = {
    2: (Image.Transpose.FLIP_LEFT_RIGHT,),
    3: (Image.Transpose.ROTATE_180,),
    4: (Image.Transpose.FLIP_TOP_BOTTOM,),
    5: (Image.Transpose.FLIP_LEFT_RIGHT, Image.Transpose.ROTATE_90),
    6: (Image.Transpose.ROTATE_270,),
    7: (Image.Transpose.FLIP_LEFT_RIGHT, Image.Transpose.ROTATE_270),
    8: (Image.Transpose.ROTATE_90,),
}


def _auto_rotate(img: Image.Image) -> Image.Image:
    """Rotate image according to EXIF orientation tag."""
    try:
        exif_data = img.getexif()
        orientation = exif_data.get(_EXIF_ORIENT_TAG)
        if orientation and orientation in _ORIENT_TRANSFORMS:
            for op in _ORIENT_TRANSFORMS[orientation]:
                img = img.transpose(op)
            # Strip orientation tag so downstream doesn't re-rotate
            exif_data[_EXIF_ORIENT_TAG] = 1
    except Exception:
        pass
    return img


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Normalize to sRGB JPEG-compatible mode
# ─────────────────────────────────────────────────────────────────────────────

def _to_srgb(img: Image.Image) -> Image.Image:
    """Convert image to sRGB color space and RGB mode."""
    # Handle transparency by compositing over white
    if img.mode in ("RGBA", "LA", "PA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        alpha = img.split()[-1]
        bg.paste(img.convert("RGB"), mask=alpha)
        img = bg
    elif img.mode == "P":
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGB"), mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Attempt ICC profile conversion to sRGB
    try:
        icc_bytes = img.info.get("icc_profile")
        if icc_bytes:
            src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
            img = ImageCms.profileToProfile(
                img, src_profile, _SRGB_PROFILE,
                renderingIntent=ImageCms.Intent.PERCEPTUAL,
                outputMode="RGB",
            )
    except Exception:
        pass  # No ICC profile or conversion failed — use as-is

    return img


# ─────────────────────────────────────────────────────────────────────────────
# Steps 3–4: Resize to cover, then center crop
# ─────────────────────────────────────────────────────────────────────────────

def _smart_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Resize image to cover target dimensions, then center crop.

    'Smart' here means we bias the vertical crop slightly upward
    (keep more of top) on portrait-orientation targets to preserve
    cab/boom visibility on typical machine photos shot at ground level.
    """
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # Source is wider — fit height, crop sides
        scale = target_h / src_h
    else:
        # Source is taller — fit width, crop top/bottom
        scale = target_w / src_w

    new_w = max(target_w, round(src_w * scale))
    new_h = max(target_h, round(src_h * scale))

    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Center crop with slight upward bias on vertical crops
    left = (new_w - target_w) // 2
    top_center = (new_h - target_h) // 2

    # Vertical bias: shift crop window up by up to 8% of overage
    # so we keep cab/top of machine more visible
    vertical_overage = new_h - target_h
    if vertical_overage > 0:
        bias = int(vertical_overage * 0.08)
        top = max(0, top_center - bias)
    else:
        top = top_center

    img = img.crop((left, top, left + target_w, top + target_h))
    return img


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Gentle sharpen
# ─────────────────────────────────────────────────────────────────────────────

def _sharpen(img: Image.Image) -> Image.Image:
    """Apply a mild sharpening pass appropriate for web display."""
    return img.filter(ImageFilter.UnsharpMask(radius=0.8, percent=60, threshold=3))


# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Compress to JPEG buffer, respecting MAX_FILE_SIZE
# ─────────────────────────────────────────────────────────────────────────────

def _save_jpeg(img: Image.Image, out_path: str, quality: int) -> int:
    """
    Save as JPEG. If file exceeds MAX_FILE_SIZE, reduce quality by 5
    until it fits (floor: quality 50). Returns final file size in bytes.
    """
    q = quality
    while q >= 50:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=q,
                 optimize=True, progressive=True,
                 subsampling=0)  # 4:4:4 chroma for quality
        size = buf.tell()
        if size <= MAX_FILE_SIZE or q <= 50:
            with open(out_path, "wb") as f:
                f.write(buf.getvalue())
            return size
        q -= 5
    # Fallback: save at minimum quality
    with open(out_path, "wb") as f:
        f.write(buf.getvalue())
    return size


# ─────────────────────────────────────────────────────────────────────────────
# Original normalization (auto-rotate + sRGB + reasonable max dimension)
# ─────────────────────────────────────────────────────────────────────────────

MAX_ORIGINAL_DIM = 2400  # Cap originals at 2400px on longest side


def _save_original(img: Image.Image, out_path: str) -> int:
    """Save normalized original, capped at MAX_ORIGINAL_DIM."""
    w, h = img.size
    if max(w, h) > MAX_ORIGINAL_DIM:
        scale = MAX_ORIGINAL_DIM / max(w, h)
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    return _save_jpeg(img, out_path, quality=90)


# ─────────────────────────────────────────────────────────────────────────────
# Per-image processing pipeline
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif"}


def _process_image(
    src_path: str,
    index: int,
    dirs: dict,
    machine_name: str,
) -> dict:
    """
    Run the full pipeline for one source image.
    Returns a dict of {variant: (out_path, file_size_bytes)}.
    """
    base = f"{machine_name}_{index:02d}"
    results = {}

    # ── Load ──────────────────────────────────────────────────────────────
    try:
        img = Image.open(src_path)
        img.load()  # Force decode (catches corrupt files early)
    except Exception as e:
        print(f"  [SKIP] Cannot open {os.path.basename(src_path)}: {e}")
        return {}

    # Step 1: Auto-rotate from EXIF
    img = _auto_rotate(img)

    # Step 2: Convert to sRGB
    img = _to_srgb(img)

    # Save normalized original
    orig_path = os.path.join(dirs["original"], f"{base}_original.jpg")
    orig_size = _save_original(img.copy(), orig_path)
    results["original"] = (orig_path, orig_size)

    # Steps 3–6: Each platform variant
    for variant, cfg in TARGETS.items():
        tw, th = cfg["size"]
        suffix = cfg["suffix"]
        quality = cfg["quality"]

        cropped = _smart_crop(img.copy(), tw, th)
        sharpened = _sharpen(cropped)

        folder_key = {
            "4x5":  "4x5",
            "1x1":  "1x1",
            "9x16": "9x16",
            "thumb": "thumb",
        }[variant]

        out_path = os.path.join(dirs[folder_key], f"{base}_{suffix}.jpg")
        size = _save_jpeg(sharpened, out_path, quality)
        results[variant] = (out_path, size)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Directory scaffolding
# ─────────────────────────────────────────────────────────────────────────────

def _make_dirs(output_folder: str) -> dict:
    dirs = {
        "root":     output_folder,
        "original": os.path.join(output_folder, "images_original"),
        "4x5":      os.path.join(output_folder, "images_4x5"),
        "1x1":      os.path.join(output_folder, "images_1x1"),
        "9x16":     os.path.join(output_folder, "images_9x16"),
        "thumb":    os.path.join(output_folder, "thumbnails"),
        "spec":     os.path.join(output_folder, "spec_sheet"),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    return dirs


# ─────────────────────────────────────────────────────────────────────────────
# ZIP packaging
# ─────────────────────────────────────────────────────────────────────────────

def _zip_folder(folder_path: str, zip_path: str) -> int:
    """Zip entire folder. Returns total ZIP size in bytes."""
    root = Path(folder_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in sorted(root.rglob("*")):
            if file_path.is_file():
                arcname = file_path.relative_to(root.parent)
                zf.write(file_path, arcname)
    return os.path.getsize(zip_path)


# ─────────────────────────────────────────────────────────────────────────────
# Report printer
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f} MB"
    return f"{n/1_000:.0f} KB"


def _print_report(all_results: list[dict], zip_path: str, zip_size: int, machine_name: str):
    print()
    sep = "-" * 62
    print(f"  MTM Image Pack - {machine_name}")
    print(f"  {sep}")
    print(f"  {'Image':<22} {'Variant':<10} {'Dimensions':<16} {'Size'}")
    print(f"  {sep}")

    for entry in all_results:
        label = entry["label"]
        for variant, (path, size) in entry["variants"].items():
            try:
                with Image.open(path) as im:
                    dims = f"{im.width}x{im.height}"
            except Exception:
                dims = "?"
            print(f"  {label:<22} {variant:<10} {dims:<16} {_fmt_size(size)}")

    print(f"  {sep}")
    print(f"  ZIP: {os.path.basename(zip_path)}  ({_fmt_size(zip_size)})")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_image_pack(
    input_folder: str,
    output_folder: str,
    machine_name: str = "machine",
) -> dict:
    """
    Generate a complete MTM image pack from a folder of machine photos.

    Parameters
    ----------
    input_folder  : Path to folder containing source images.
    output_folder : Path where output folders + ZIP will be written.
    machine_name  : Clean machine identifier used in filenames
                    (e.g. "Bobcat_T770"). Spaces replaced with underscores.

    Returns
    -------
    dict with keys:
        output_folder  : str — path to output directory
        zip_path       : str — path to generated ZIP
        zip_size       : int — ZIP file size in bytes
        image_count    : int — number of source images processed
        results        : list[dict] — per-image results
    """
    machine_name = machine_name.replace(" ", "_")
    input_folder = os.path.abspath(input_folder)
    output_folder = os.path.abspath(output_folder)

    if not HEIC_SUPPORTED:
        print("  [WARNING] pillow-heif not installed — HEIC files will be skipped.")

    # Collect source images, sorted
    src_files = sorted([
        f for f in Path(input_folder).iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ])

    if not src_files:
        raise ValueError(f"No supported image files found in: {input_folder}")

    print(f"\n  Processing {len(src_files)} image(s) -> {output_folder}")

    # Build directory structure
    dirs = _make_dirs(output_folder)

    all_results = []
    for idx, src_path in enumerate(src_files, start=1):
        label = src_path.name
        print(f"  [{idx}/{len(src_files)}] {label}")
        variants = _process_image(str(src_path), idx, dirs, machine_name)
        if variants:
            all_results.append({"label": label, "variants": variants})

    # ZIP everything
    zip_path = output_folder.rstrip("/\\") + ".zip"
    zip_size = _zip_folder(output_folder, zip_path)

    _print_report(all_results, zip_path, zip_size, machine_name)

    return {
        "output_folder": output_folder,
        "zip_path":      zip_path,
        "zip_size":      zip_size,
        "image_count":   len(all_results),
        "results":       all_results,
    }
