"""
image_pack_generator.py
=======================
MTM Image Pack Generator

Given a folder of machine photos, produces clean dealer listing images
with an optional branding overlay and packages everything into a ZIP.

Pipeline (per image, in order):
  1. Auto-rotate from EXIF
  2. HEIC → JPG conversion
  3. Convert to sRGB
  4. Downscale to max 2400px on longest side (aspect ratio preserved — NO cropping)
  5. Sharpen slightly
  6. Apply lower-third branding overlay (logo + name + phone) if provided
  7. Compress to web-friendly JPEG
  8. Export

Output structure:
  {output_folder}/
    Listing_Photos/      ← overlay applied, original AR preserved
    Original_Photos/     ← normalized originals, no overlay
  {output_folder}.zip

Stamping note:
  Dealer badge (rounded-rect logo/contact at bottom-left) is stamped client-side
  in static/dealer_badge_renderer.js before photos are uploaded. This module treats
  uploaded photos as already-final for the badge and does not re-stamp it.
  The branding overlay here (lower-third gradient + text) is a separate, independent
  feature driven by the overlay_contact_name / overlay_logo form fields.

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

from PIL import Image, ImageFilter, ImageCms, ImageStat

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

# Maximum pixel dimension for listing photos (longest side).
# Original aspect ratio is always preserved — no cropping.
MAX_LISTING_DIM = 2400

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
# Step 3: Downscale to listing size, preserving original aspect ratio
# ─────────────────────────────────────────────────────────────────────────────

def _resize_for_listing(img: Image.Image, max_dim: int = MAX_LISTING_DIM) -> Image.Image:
    """
    Scale the image down so its longest side is at most max_dim.
    Original aspect ratio is preserved exactly — no cropping.
    Images already within the limit are returned unchanged.
    """
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    scale = max_dim / max(w, h)
    return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


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
# Branding overlay
# ─────────────────────────────────────────────────────────────────────────────

def _load_overlay_font(size: int, bold: bool = False):
    from PIL import ImageFont

    font_candidates = []
    if bold:
        font_candidates.extend([
            "arialbd.ttf", "Arial Bold.ttf", "Arialbd.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ])
    else:
        font_candidates.extend([
            "arial.ttf", "Arial.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ])

    for fp in font_candidates:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue

    try:
        return ImageFont.load_default(size=size)  # Pillow 10+
    except Exception:
        return ImageFont.load_default()


def _set_image_opacity(img: Image.Image, opacity: float) -> Image.Image:
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda px: int(px * max(0.0, min(1.0, opacity))))
    rgba.putalpha(alpha)
    return rgba


def _fit_logo(logo_img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    ratio = min(max_w / logo_img.width, max_h / logo_img.height)
    new_w = max(1, int(logo_img.width * ratio))
    new_h = max(1, int(logo_img.height * ratio))
    return logo_img.resize((new_w, new_h), Image.LANCZOS)


def _trim_transparent_padding(logo_img: Image.Image, alpha_threshold: int = 8) -> Image.Image:
    rgba = logo_img.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.point(lambda px: 255 if px >= alpha_threshold else 0).getbbox()
    if not bbox:
        return rgba
    return rgba.crop(bbox)


def _truncate_to_width(draw, text: str, font, max_width: int) -> str:
    """Truncate text with ellipsis so it fits within max_width pixels."""
    if not text:
        return text
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width:
        return text
    while text:
        text = text[:-1]
        bbox = draw.textbbox((0, 0), text + "\u2026", font=font)
        if bbox[2] - bbox[0] <= max_width:
            return text + "\u2026"
    return "\u2026"


def _build_monochrome_watermark(logo_img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Flatten a logo into a clean single-tone watermark to avoid muddy color mixing."""
    logo = _fit_logo(logo_img, max_w, max_h).convert("RGBA")
    alpha = logo.getchannel("A")
    watermark = Image.new("RGBA", logo.size, (255, 255, 255, 0))
    watermark.putalpha(alpha.point(lambda px: int(px * 0.22)))
    watermark = watermark.filter(ImageFilter.GaussianBlur(radius=max(0.8, max_w * 0.0035)))
    return watermark


def _build_bottom_gradient(width: int, height: int) -> Image.Image:
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = gradient.load()
    for y in range(height):
        t = y / max(1, height - 1)
        alpha = int((t ** 1.8) * 205)
        for x in range(width):
            px[x, y] = (8, 10, 14, alpha)
    return gradient


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def _channel(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _analyze_logo_image(logo_img: Image.Image) -> dict:
    trimmed = _trim_transparent_padding(logo_img)
    rgba = trimmed.convert("RGBA")
    width, height = rgba.size
    alpha = rgba.getchannel("A")
    alpha_bbox = alpha.point(lambda px: 255 if px >= 12 else 0).getbbox()
    if not alpha_bbox:
        raise ValueError("logo has no visible pixels")

    visible = rgba.crop(alpha_bbox)
    v_w, v_h = visible.size
    coverage = (v_w * v_h) / max(1, width * height)
    rgba_data = visible.getdata()
    visible_pixels = [px for px in rgba_data if px[3] >= 20]
    if not visible_pixels:
        raise ValueError("logo visible area is empty")

    luminances = [_relative_luminance(px[:3]) for px in visible_pixels]
    mean_luma = sum(luminances) / len(luminances)
    low_res = min(v_w, v_h) < 48 or (v_w * v_h) < 5000
    transparency_ratio = sum(1 for px in rgba_data if px[3] < 20) / max(1, len(rgba_data))

    edge_samples = []
    edge_coords = []
    for x in range(v_w):
        edge_coords.append((x, 0))
        edge_coords.append((x, v_h - 1))
    for y in range(1, v_h - 1):
        edge_coords.append((0, y))
        edge_coords.append((v_w - 1, y))
    px_access = visible.load()
    for coord in edge_coords:
        edge_samples.append(px_access[coord[0], coord[1]])
    opaque_edge = [px for px in edge_samples if px[3] >= 220]
    solid_badge = False
    if opaque_edge:
        edge_lumas = [_relative_luminance(px[:3]) for px in opaque_edge]
        edge_mean = sum(edge_lumas) / len(edge_lumas)
        edge_spread = max(edge_lumas) - min(edge_lumas)
        solid_badge = edge_spread < 0.12 and len(opaque_edge) / max(1, len(edge_samples)) > 0.72
    solid_badge = solid_badge or (coverage > 0.88 and transparency_ratio < 0.08)

    return {
        "image": rgba,
        "mean_luma": mean_luma,
        "visible_width": v_w,
        "visible_height": v_h,
        "coverage": coverage,
        "transparency_ratio": transparency_ratio,
        "solid_badge": solid_badge,
        "low_res": low_res,
    }


def _sample_overlay_patch(base_img: Image.Image, patch_w: int, patch_h: int, safe_pad: int) -> dict:
    w, h = base_img.size
    left = max(0, w - safe_pad - patch_w)
    top = max(0, h - safe_pad - patch_h)
    patch = base_img.crop((left, top, min(w, left + patch_w), min(h, top + patch_h))).convert("RGB")
    stat = ImageStat.Stat(patch)
    mean_rgb = tuple(int(v) for v in stat.mean[:3])
    luma = _relative_luminance(mean_rgb)
    channel_std = stat.stddev[:3] if getattr(stat, "stddev", None) else [0, 0, 0]
    variance = sum(channel_std) / max(1, len(channel_std))
    return {
        "mean_rgb": mean_rgb,
        "mean_luma": luma,
        "variance": variance,
    }


def _choose_overlay_plan(
    base_img: Image.Image,
    logo_path: "str | None",
    fallback_text: "str | None",
    safe_pad: int,
    max_logo_w: int,
    max_logo_h: int,
) -> dict:
    plan = {
        "mode": "none",
        "backing_mode": "none",
        "logo": None,
        "text": (fallback_text or "").strip() or None,
    }

    logo_analysis = None
    if logo_path and os.path.isfile(logo_path):
        try:
            with Image.open(logo_path) as logo_file:
                logo_analysis = _analyze_logo_image(logo_file)
        except Exception:
            logo_analysis = None

    if logo_analysis is None:
        plan["mode"] = "text" if plan["text"] else "none"
        plan["backing_mode"] = "shadow" if plan["mode"] == "text" else "none"
        return plan

    if logo_analysis["low_res"]:
        plan["mode"] = "text" if plan["text"] else "none"
        plan["backing_mode"] = "shadow" if plan["mode"] == "text" else "none"
        return plan

    try:
        fitted_logo = _fit_logo(logo_analysis["image"], max_logo_w, max_logo_h)
    except Exception:
        plan["mode"] = "text" if plan["text"] else "none"
        plan["backing_mode"] = "shadow" if plan["mode"] == "text" else "none"
        return plan

    if min(fitted_logo.size) < 26:
        plan["mode"] = "text" if plan["text"] else "none"
        plan["backing_mode"] = "shadow" if plan["mode"] == "text" else "none"
        return plan

    patch = _sample_overlay_patch(base_img, fitted_logo.width, fitted_logo.height, safe_pad)
    bg_luma = patch["mean_luma"]
    logo_luma = logo_analysis["mean_luma"]
    contrast_gap = abs(logo_luma - bg_luma)

    plan["mode"] = "logo"
    plan["logo"] = fitted_logo

    if logo_analysis["solid_badge"]:
        plan["backing_mode"] = "shadow" if contrast_gap < 0.14 else "none"
        return plan

    if contrast_gap < 0.18:
        if logo_luma >= 0.62:
            plan["backing_mode"] = "dark"
        elif logo_luma <= 0.34:
            plan["backing_mode"] = "light"
        else:
            plan["backing_mode"] = "shadow"
        return plan

    if logo_luma >= 0.75:
        plan["backing_mode"] = "dark"
    elif logo_luma <= 0.18:
        plan["backing_mode"] = "light"
    else:
        plan["backing_mode"] = "none"
    return plan


def _apply_soft_shadow(overlay_img: Image.Image, blur_radius: float, opacity: int = 100) -> Image.Image:
    shadow = Image.new("RGBA", overlay_img.size, (0, 0, 0, 0))
    alpha = overlay_img.getchannel("A").point(lambda px: int(px * opacity / 255))
    shadow.putalpha(alpha)
    return shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))


def _build_logo_plate(size: tuple[int, int], mode: str) -> Image.Image:
    from PIL import ImageDraw

    width, height = size
    plate = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    if mode == "dark":
        fill = (10, 12, 16, 162)
        outline = (255, 255, 255, 34)
    else:
        fill = (245, 247, 250, 172)
        outline = (255, 255, 255, 54)
    radius = max(10, int(min(width, height) * 0.22))
    draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=fill, outline=outline, width=1)
    return plate


def _compose_logo_overlay(base: Image.Image, logo_img: Image.Image, safe_pad: int, backing_mode: str) -> Image.Image:
    w, h = base.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    inner_pad_x = max(10, int(logo_img.width * 0.12))
    inner_pad_y = max(8, int(logo_img.height * 0.14))
    plate_w = logo_img.width + inner_pad_x * 2
    plate_h = logo_img.height + inner_pad_y * 2
    x = w - safe_pad - plate_w
    y = h - safe_pad - plate_h

    if backing_mode in {"dark", "light"}:
        plate = _build_logo_plate((plate_w, plate_h), backing_mode)
        plate_shadow = _apply_soft_shadow(plate, blur_radius=max(6, int(min(w, h) * 0.008)), opacity=86)
        overlay.alpha_composite(plate_shadow, (x, y))
        overlay.alpha_composite(plate, (x, y))
    elif backing_mode == "shadow":
        shadow = _apply_soft_shadow(logo_img, blur_radius=max(4, int(min(w, h) * 0.006)), opacity=120)
        overlay.alpha_composite(shadow, (x + inner_pad_x, y + inner_pad_y + 1))

    overlay.alpha_composite(logo_img, (x + inner_pad_x, y + inner_pad_y))
    out = base.copy()
    out.alpha_composite(overlay)
    return out


def _build_text_watermark(base_img: Image.Image, watermark_text: str, safe_pad: int) -> Image.Image:
    from PIL import ImageDraw

    if not watermark_text:
        return base_img

    w, h = base_img.size
    base = base_img.copy()
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_overlay_font(max(15, int(h * 0.0165)), bold=True)
    text = watermark_text.strip()
    max_text_w = int(w * 0.34)
    text = _truncate_to_width(draw, text, font, max_text_w)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x = max(11, int(text_h * 0.72))
    pad_y = max(8, int(text_h * 0.56))
    box_w = text_w + pad_x * 2
    box_h = text_h + pad_y * 2
    x = w - safe_pad - box_w
    y = h - safe_pad - box_h
    plate = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    plate_draw = ImageDraw.Draw(plate)
    plate_draw.rounded_rectangle(
        (0, 0, box_w, box_h),
        radius=max(10, int(box_h * 0.45)),
        fill=(8, 10, 14, 108),
        outline=(255, 255, 255, 26),
        width=1,
    )
    shadow = _apply_soft_shadow(plate, blur_radius=max(5, int(min(w, h) * 0.0065)), opacity=92)
    overlay.alpha_composite(shadow, (x, y))
    overlay.alpha_composite(plate, (x, y))
    draw = ImageDraw.Draw(overlay)
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=(255, 255, 255, 186))
    base.alpha_composite(overlay)
    return base

def _apply_branding_overlay(
    img: Image.Image,
    logo_path: "str | None",
    contact_text: "str | None",
    company_name: "str | None" = None,
) -> Image.Image:
    """
    Composite a premium branding treatment onto img.

    Uses a bottom safe-zone gradient, a left contact block, and a bottom-right
    branding mark that chooses logo or text fallback based on logo viability.
    Works on any aspect ratio; safe to call even if logo/text is None.
    """
    from PIL import ImageDraw

    fallback_brand_text = (company_name or "").strip() or None
    if not fallback_brand_text and contact_text:
        normalized_contact = (
            contact_text
            .replace("\u2022", "|")
            .replace("â€¢", "|")
            .replace("Ã¢â‚¬Â¢", "|")
            .replace("ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢", "|")
        )
        raw_parts = [part.strip() for part in normalized_contact.split("|") if part.strip()]
        fallback_brand_text = raw_parts[0] if raw_parts else normalized_contact.strip() or None

    if not logo_path and not contact_text and not fallback_brand_text:
        return img

    w, h = img.size
    safe_pad = max(18, int(min(w, h) * 0.024))
    overlay_h = max(142, int(h * 0.19))
    contact_block_max_w = int(w * 0.72)
    contact_logo_max_h = max(62, int(overlay_h * 0.48))
    contact_logo_max_w = int(w * 0.22)
    watermark_max_w = int(w * 0.18)
    watermark_max_h = int(h * 0.11)

    base = img.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    overlay.alpha_composite(_build_bottom_gradient(w, overlay_h), (0, h - overlay_h))
    draw = ImageDraw.Draw(overlay)

    dealer_logo = None
    overlay_plan = _choose_overlay_plan(
        base_img=base,
        logo_path=logo_path,
        fallback_text=fallback_brand_text,
        safe_pad=safe_pad,
        max_logo_w=watermark_max_w,
        max_logo_h=watermark_max_h,
    )

    if contact_text:
        normalized_contact = (
            contact_text
            .replace("\u2022", "|")
            .replace("•", "|")
            .replace("â€¢", "|")
            .replace("Ã¢â‚¬Â¢", "|")
        )
        raw_parts = [part.strip() for part in normalized_contact.split("|") if part.strip()]
        primary_text = raw_parts[0] if raw_parts else normalized_contact.strip()
        secondary_text = " | ".join(raw_parts[1:]) if len(raw_parts) > 1 else ""
        title_font = _load_overlay_font(max(22, int(h * 0.0210)), bold=True)
        body_font = _load_overlay_font(max(17, int(h * 0.0160)), bold=True)
        primary_bbox = draw.textbbox((0, 0), primary_text, font=title_font)
        primary_w = primary_bbox[2] - primary_bbox[0]
        primary_h = primary_bbox[3] - primary_bbox[1]
        secondary_w = 0
        secondary_h = 0
        if secondary_text:
            secondary_bbox = draw.textbbox((0, 0), secondary_text, font=body_font)
            secondary_w = secondary_bbox[2] - secondary_bbox[0]
            secondary_h = secondary_bbox[3] - secondary_bbox[1]

        text_gap = max(6, int(h * 0.0045))
        text_stack_h = primary_h + (secondary_h + text_gap if secondary_text else 0)
        text_stack_w = max(primary_w, secondary_w)
        logo_w = 0
        logo_h = 0
        contact_logo = None
        if logo_path and os.path.isfile(logo_path):
            try:
                with Image.open(logo_path) as dealer_logo_file:
                    dealer_logo = _trim_transparent_padding(dealer_logo_file)
                contact_logo = _fit_logo(dealer_logo, contact_logo_max_w, contact_logo_max_h)
                logo_w = contact_logo.width
                logo_h = contact_logo.height
            except Exception:
                contact_logo = None

        block_pad_x = max(18, int(safe_pad * 1.08))
        block_pad_y = max(14, int(safe_pad * 0.82))
        logo_gap = max(16, int(w * 0.012))

        # Truncate text that would overflow the maximum block width
        _text_budget = (
            contact_block_max_w
            - block_pad_x * 2
            - (logo_w + logo_gap if contact_logo is not None else 0)
        )
        if _text_budget > 20:
            primary_text = _truncate_to_width(draw, primary_text, title_font, _text_budget)
            if secondary_text:
                secondary_text = _truncate_to_width(draw, secondary_text, body_font, _text_budget)
            # Re-measure after truncation
            _pb = draw.textbbox((0, 0), primary_text, font=title_font)
            primary_w = _pb[2] - _pb[0]
            primary_h = _pb[3] - _pb[1]
            if secondary_text:
                _sb = draw.textbbox((0, 0), secondary_text, font=body_font)
                secondary_w = _sb[2] - _sb[0]
                secondary_h = _sb[3] - _sb[1]
            else:
                secondary_w = secondary_h = 0
            text_stack_h = primary_h + (secondary_h + text_gap if secondary_text else 0)
            text_stack_w = max(primary_w, secondary_w)

        content_w = text_stack_w + (logo_w + logo_gap if contact_logo is not None else 0)
        block_h = max(text_stack_h, logo_h) + (block_pad_y * 2)
        block_w = min(contact_block_max_w, max(int(w * 0.28), content_w + (block_pad_x * 2)))
        block_x = safe_pad
        block_y = h - safe_pad - block_h
        block = Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0))
        block_draw = ImageDraw.Draw(block)

        content_x = block_pad_x
        if contact_logo is not None:
            logo_y = (block_h - contact_logo.height) // 2
            block.alpha_composite(contact_logo, (content_x, logo_y))
            content_x += contact_logo.width + logo_gap

        text_x = content_x
        text_y = max(block_pad_y, (block_h - text_stack_h) // 2)
        # Subtle shadow pass for legibility on the gradient
        _sd = max(1, int(h * 0.0012))
        block_draw.text((text_x + _sd, text_y + _sd), primary_text, font=title_font, fill=(0, 0, 0, 110))
        block_draw.text(
            (text_x, text_y),
            primary_text,
            font=title_font,
            fill=(255, 255, 255, 238),
        )
        if secondary_text:
            text_y += primary_h + text_gap
            block_draw.text((text_x + _sd, text_y + _sd), secondary_text, font=body_font, fill=(0, 0, 0, 90))
            block_draw.text(
                (text_x, text_y),
                secondary_text,
                font=body_font,
                fill=(223, 226, 231, 210),
            )

        overlay.alpha_composite(block, (block_x, block_y))

    base.alpha_composite(overlay)
    # Bottom-right branding mark is suppressed when the lower-left contact block
    # is active — the dealer's name/phone already appear there, so rendering the
    # logo or text watermark again would duplicate the branding on the same image.
    # When no contact_text is provided, the bottom-right mark is the only branding
    # present and must be kept as a fallback.
    if contact_text is None:
        if overlay_plan["mode"] == "logo" and overlay_plan["logo"] is not None:
            base = _compose_logo_overlay(
                base,
                overlay_plan["logo"],
                safe_pad=safe_pad,
                backing_mode=overlay_plan["backing_mode"],
            )
        elif overlay_plan["mode"] == "text" and overlay_plan["text"]:
            base = _build_text_watermark(base, overlay_plan["text"], safe_pad=safe_pad)

    return base.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Per-image processing pipeline
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif"}


def _process_image(
    src_path: str,
    index: int,
    dirs: dict,
    machine_name: str,
    overlay_logo_path: "str | None" = None,
    overlay_contact_text: "str | None" = None,
    overlay_company_name: "str | None" = None,
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

    # Step 3: Scale to listing size — original aspect ratio preserved, no cropping
    listing_img = _resize_for_listing(img.copy())
    listing_img = _sharpen(listing_img)

    # Step 4: Apply branding overlay (lower-third only, non-destructive)
    if overlay_logo_path or overlay_contact_text:
        try:
            listing_img = _apply_branding_overlay(
                listing_img, overlay_logo_path, overlay_contact_text, overlay_company_name
            )
        except Exception as _ov_exc:
            print(f"  [WARN] Overlay failed for {os.path.basename(src_path)}: {_ov_exc}")

    out_path = os.path.join(dirs["listing"], f"{base}_listing.jpg")
    size = _save_jpeg(listing_img, out_path, quality=88)
    results["listing"] = (out_path, size)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Directory scaffolding
# ─────────────────────────────────────────────────────────────────────────────

def _make_dirs(output_folder: str) -> dict:
    dirs = {
        "root":     output_folder,
        "listing":  os.path.join(output_folder, "Listing_Photos"),
        "original": os.path.join(output_folder, "Original_Photos"),
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
    overlay_logo_path: "str | None" = None,
    overlay_company_name: "str | None" = None,
    overlay_contact_name: "str | None" = None,
    overlay_contact_phone: "str | None" = None,
    skip_zip: bool = False,
) -> dict:
    """
    Generate a complete MTM image pack from a folder of machine photos.

    Parameters
    ----------
    input_folder          : Path to folder containing source images.
    output_folder         : Path where output folders + ZIP will be written.
    machine_name          : Clean machine identifier used in filenames.
    overlay_logo_path     : Absolute path to logo image (PNG recommended).
    overlay_company_name  : Dealer/company name used for text fallback branding.
    overlay_contact_name  : Contact name for overlay text.
    overlay_contact_phone : Contact phone for overlay text.
    skip_zip              : Skip ZIP creation (use when caller handles ZIP assembly).

    Returns
    -------
    dict with keys:
        output_folder  : str — path to output directory
        zip_path       : str or None — path to generated ZIP (None if skip_zip=True)
        zip_size       : int — ZIP file size in bytes (0 if skip_zip=True)
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

    # Build overlay contact text (e.g. "John Smith  •  555-123-4567")
    _parts = [p for p in [overlay_contact_name, overlay_contact_phone] if p and p.strip()]
    overlay_contact_text: "str | None" = ("  \u2022  ".join(_parts)) if _parts else None

    # Build directory structure
    dirs = _make_dirs(output_folder)

    all_results = []
    for idx, src_path in enumerate(src_files, start=1):
        label = src_path.name
        print(f"  [{idx}/{len(src_files)}] {label}")
        variants = _process_image(
            str(src_path), idx, dirs, machine_name,
            overlay_logo_path=overlay_logo_path,
            overlay_contact_text=overlay_contact_text,
            overlay_company_name=overlay_company_name,
        )
        if variants:
            all_results.append({"label": label, "variants": variants})

    listing_dir  = dirs["listing"]
    original_dir = dirs["original"]
    total_variants = sum(len(r["variants"]) for r in all_results)
    print(f"  [ImagePack] Listing_Photos  : {listing_dir}")
    print(f"  [ImagePack] Original_Photos : {original_dir}")
    print(f"  [ImagePack] variants written: {total_variants} across {len(all_results)} image(s)")

    if skip_zip:
        return {
            "output_folder": output_folder,
            "zip_path":      None,
            "zip_size":      0,
            "image_count":   len(all_results),
            "results":       all_results,
        }

    # ZIP everything (standalone / CLI usage)
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
