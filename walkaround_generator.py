"""
walkaround_generator.py
=======================
MTM Walkaround Video Generator (async-friendly, vertical 1080x1920).

Produces a 1080x1920 H.264 MP4 with a silent AAC stereo track, intro card,
static photo slides, and outro card. Designed to be invoked from
`asyncio.to_thread(...)` by an async job runner. Synchronous internals.

Public API:
    generate_walkaround_video(
        photos: list[str],
        output_path: str,
        year: int,
        make: str,
        model: str,
        dealer_name: Optional[str] = None,
        dealer_phone: Optional[str] = None,
        accent_color: Optional[str] = None,
        dealer_logo_path: Optional[str] = None,
    ) -> str

    score_dealer_logo(logo_path: str) -> int
        Scores a dealer logo 0–100. Threshold >= 60 = use logo.

    walkaround_filename(year, make, model) -> str
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_FFMPEG_CANDIDATES = [
    r"C:\ffmpeg\ffmpeg\bin\ffmpeg.exe",
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "ffmpeg",
]

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

TARGET_W = 1080
TARGET_H = 1920
FPS = 30
SLIDE_SECS = 3.0          # per-photo slide duration
INTRO_SECS = 2.0
OUTRO_SECS = 2.5
MAX_PHOTOS = 10
MIN_PHOTOS = 4
DEFAULT_TIMEOUT = 240
DEFAULT_ACCENT = "#FFCC00"
MAX_CROP_FRACTION = 0.10  # max overflow of a canvas edge before scale is reduced
BLUR_RADIUS = 40          # GaussianBlur radius on background fill

# Lower-rail overlay
RAIL_H = 130              # total rail height in pixels
RAIL_ALPHA = 184          # matte black opacity (~72% of 255)
RAIL_ACCENT_H = 3         # yellow accent line height at rail top
LOGO_MAX_H = 118          # max logo height inside rail
LOGO_LEFT_PAD = 18        # logo left margin
LOGO_TEXT_GAP = 10        # gap between logo and text
RAIL_NAME_SIZE = 46       # font pt for dealer name
RAIL_PHONE_SIZE = 32      # font pt for phone line
RAIL_MIN_BLUR_MARGIN = 10 # min px of blur zone required below fg before drawing rail

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _sanitize_part(part: str) -> str:
    s = _SANITIZE_RE.sub("_", str(part or "")).strip("_-")
    return s or "x"


def walkaround_filename(year, make: str, model: str) -> str:
    """Return a filesystem-safe filename for the walkaround MP4."""
    y = _sanitize_part(year)
    mk = _sanitize_part(make)
    md = _sanitize_part(model)
    return f"{y}_{mk}_{md}_Walkaround.mp4"


def _find_ffmpeg() -> str:
    for candidate in _FFMPEG_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("ffmpeg not found on PATH or known install locations.")


def check_ffmpeg_available() -> None:
    """Raise RuntimeError if ffmpeg cannot be located. Call before starting a job."""
    _find_ffmpeg()


def _load_font(size: int) -> ImageFont.ImageFont:
    """Best-effort font load; fall back to default."""
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            if os.path.isfile(c):
                return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _load_font_condensed(size: int) -> ImageFont.ImageFont:
    """Load a condensed/industrial-style font; fallback to bold, then default."""
    candidates = [
        r"C:\Windows\Fonts\impact.ttf",
        r"C:\Windows\Fonts\arialnarrow.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for c in candidates:
        try:
            if os.path.isfile(c):
                return ImageFont.truetype(c, size)
        except Exception:
            continue
    return _load_font(size)


def _load_font_mono(size: int) -> ImageFont.ImageFont:
    """Load a monospaced/condensed font for the phone line; fallback to default."""
    candidates = [
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
        r"C:\Windows\Fonts\lucon.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for c in candidates:
        try:
            if os.path.isfile(c):
                return ImageFont.truetype(c, size)
        except Exception:
            continue
    return _load_font(size)


def _parse_accent(accent: Optional[str]) -> tuple[int, int, int]:
    """Parse '#RRGGBB' or named token to RGB."""
    if not accent:
        accent = DEFAULT_ACCENT
    a = str(accent).strip()
    named = {
        "yellow": "#FFCC00",
        "orange": "#FF7A00",
        "red": "#E53935",
        "blue": "#1976D2",
        "green": "#2E7D32",
        "black": "#111111",
        "white": "#FFFFFF",
    }
    if a.lower() in named:
        a = named[a.lower()]
    if a.startswith("#") and len(a) == 7:
        try:
            return (int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16))
        except Exception:
            pass
    return (255, 204, 0)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill,
    canvas_w: int = TARGET_W,
) -> int:
    """Draw text horizontally centered. Returns text height."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((canvas_w - tw) // 2, y), text, font=font, fill=fill)
    return th


def score_dealer_logo(logo_path: str) -> int:
    """
    Score a dealer logo 0–100 for lower-rail suitability.
    Threshold: >= 60 use logo; < 60 fallback to text-only.

    Scoring dimensions (max 100):
      Resolution     0–30  (width >=500=30, >=300=20, >=200=10)
      Transparency   0–20  (PNG/WebP with meaningful alpha = 20)
      Aspect ratio   0–15  (1.5:1–5:1 = 15; 0.8:1–7:1 = 8)
      BBox occupancy 0–20  (>=60% = 20; >=40% = 10)
      Sharpness      0–15  (sharp = 15; medium = 8)
    """
    if not logo_path or not os.path.isfile(logo_path):
        return 0
    try:
        with Image.open(logo_path) as im:
            w, h = im.size
            score = 0

            # 1. Resolution (0–30)
            if w >= 500:   score += 30
            elif w >= 300: score += 20
            elif w >= 200: score += 10

            # 2. Transparency (0–20)
            has_alpha = False
            suffix = Path(logo_path).suffix.lower()
            if suffix in ('.png', '.webp') and im.mode in ('RGBA', 'LA', 'P'):
                rgba = im.convert('RGBA')
                sample = rgba.resize(
                    (max(1, min(w, 200)), max(1, min(h, 200))), Image.LANCZOS
                )
                n = sample.width * sample.height
                transparent_ct = sum(1 for px in sample.getdata() if px[3] < 200)
                if transparent_ct / max(n, 1) > 0.05:
                    has_alpha = True
                    score += 20

            # 3. Aspect ratio (0–15)
            ratio = w / max(h, 1)
            if 1.5 <= ratio <= 5.0:   score += 15
            elif 0.8 <= ratio <= 7.0: score += 8

            # 4. Bounding-box occupancy (0–20)
            sample_size = (max(1, min(w, 200)), max(1, min(h, 200)))
            if has_alpha:
                samp2 = im.convert('RGBA').resize(sample_size, Image.LANCZOS)
                px_list = list(samp2.getdata())
                sw2, sh2 = samp2.size
                active = [
                    (i % sw2, i // sw2) for i, px in enumerate(px_list) if px[3] > 50
                ]
            else:
                samp2 = im.convert('RGB').resize(sample_size, Image.LANCZOS)
                px_list = list(samp2.getdata())
                sw2, sh2 = samp2.size
                active = [
                    (i % sw2, i // sw2) for i, px in enumerate(px_list)
                    if not (px[0] > 240 and px[1] > 240 and px[2] > 240)
                ]
            if active:
                xs = [p[0] for p in active]
                ys = [p[1] for p in active]
                bbox_area = max((max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1), 1)
                occ = len(active) / bbox_area
                if occ >= 0.60:   score += 20
                elif occ >= 0.40: score += 10

            # 5. Sharpness (0–15): mean-square of edge-detected image
            gray = im.convert('L').resize(
                (max(1, min(w, 200)), max(1, min(h, 200))), Image.LANCZOS
            )
            edge_data = list(gray.filter(ImageFilter.FIND_EDGES).getdata())
            mean_sq = sum(p * p for p in edge_data) / max(len(edge_data), 1)
            if mean_sq > 400:   score += 15
            elif mean_sq > 80:  score += 8

            print(
                f"  [Walkaround] logo score={score} "
                f"(res={w}px ratio={ratio:.2f} alpha={has_alpha}) "
                f"path={os.path.basename(logo_path)}"
            )
            return min(score, 100)
    except Exception as exc:
        print(f"  [Walkaround] logo score error: {exc}")
        return 0


def _apply_lower_rail(
    canvas: "Image.Image",
    dealer_name: Optional[str],
    dealer_phone: Optional[str],
    accent_rgb: tuple[int, int, int],
    logo_path: Optional[str],
    fg_bottom_y: int,
) -> "Image.Image":
    """
    Composite an industrial lower-rail branding strip onto canvas.
    Returns a new RGB image; the original canvas is not mutated.

    Skips silently when:
      - no dealer name and no dealer phone
      - machine body (fg_bottom_y) extends into the rail zone
    """
    if not dealer_name and not dealer_phone:
        return canvas

    rail_top = TARGET_H - RAIL_H
    if fg_bottom_y > rail_top - RAIL_MIN_BLUR_MARGIN:
        return canvas  # no usable blur zone; skip rail

    # --- Rail strip + accent line (RGBA overlay) ---
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rectangle(
        [0, rail_top, TARGET_W - 1, TARGET_H - 1],
        fill=(18, 18, 18, RAIL_ALPHA),
    )
    odraw.rectangle(
        [0, rail_top, TARGET_W - 1, rail_top + RAIL_ACCENT_H - 1],
        fill=(*accent_rgb, 255),
    )

    base = Image.alpha_composite(canvas.convert("RGBA"), overlay)

    # --- Text strings ---
    name_str = (dealer_name or "").strip().upper()
    raw_phone = (dealer_phone or "").strip()
    if raw_phone and not raw_phone.upper().startswith(("CALL", "TEXT")):
        phone_str = f"CALL/TEXT {raw_phone}"
    else:
        phone_str = raw_phone.upper()

    # --- Measure text block ---
    name_font  = _load_font_condensed(RAIL_NAME_SIZE)
    phone_font = _load_font_mono(RAIL_PHONE_SIZE)
    tmp = ImageDraw.Draw(base)
    name_h = phone_h = 0
    if name_str:
        nb = tmp.textbbox((0, 0), name_str, font=name_font)
        name_h = nb[3] - nb[1]
    if phone_str:
        pb = tmp.textbbox((0, 0), phone_str, font=phone_font)
        phone_h = pb[3] - pb[1]
    line_gap = 7
    block_h   = name_h + (line_gap + phone_h if phone_str else 0)
    usable_h  = RAIL_H - RAIL_ACCENT_H
    text_top  = rail_top + RAIL_ACCENT_H + (usable_h - block_h) // 2 - 12
    x_text    = 30

    # --- Logo (quality-gated) ---
    logo_score = score_dealer_logo(logo_path) if logo_path else 0
    use_logo   = logo_score >= 60 and bool(logo_path and os.path.isfile(logo_path))

    if use_logo:
        try:
            with Image.open(logo_path) as lim:
                lim = lim.convert("RGBA")
                lw, lh    = lim.size
                fit_h     = min(LOGO_MAX_H, usable_h - 16)
                fit_w     = max(1, int(lw * fit_h / max(lh, 1)))
                lim       = lim.resize((fit_w, fit_h), Image.LANCZOS)
                logo_x    = LOGO_LEFT_PAD
                logo_y    = rail_top + RAIL_ACCENT_H + (usable_h - fit_h) // 2
                base.paste(lim, (logo_x, logo_y), lim)
                x_text    = LOGO_LEFT_PAD + fit_w + LOGO_TEXT_GAP
        except Exception as exc:
            print(f"  [Walkaround] logo render failed: {exc}")

    # --- Draw text ---
    tdraw = ImageDraw.Draw(base)
    if name_str:
        tdraw.text((x_text, text_top), name_str, font=name_font, fill=(255, 255, 255, 255))
    if phone_str:
        tdraw.text(
            (x_text, text_top + name_h + line_gap),
            phone_str,
            font=phone_font,
            fill=(*accent_rgb, 255),
        )

    return base.convert("RGB")


def _make_intro_card(
    out_path: str,
    year: int,
    make: str,
    model: str,
    accent_rgb: tuple[int, int, int],
) -> None:
    img = Image.new("RGB", (TARGET_W, TARGET_H), (15, 15, 15))
    draw = ImageDraw.Draw(img)

    # Accent bar
    bar_h = 14
    draw.rectangle([0, TARGET_H // 2 - 220, TARGET_W, TARGET_H // 2 - 220 + bar_h], fill=accent_rgb)

    title_font = _load_font(120)
    sub_font = _load_font(72)
    label_font = _load_font(48)

    label = "WALKAROUND"
    _draw_centered_text(draw, label, TARGET_H // 2 - 360, label_font, accent_rgb)

    year_str = str(year) if year else ""
    if year_str:
        _draw_centered_text(draw, year_str, TARGET_H // 2 - 160, sub_font, (230, 230, 230))

    mk = (make or "").upper()
    if mk:
        _draw_centered_text(draw, mk, TARGET_H // 2 - 60, title_font, (255, 255, 255))

    md = str(model or "")
    if md:
        _draw_centered_text(draw, md, TARGET_H // 2 + 90, title_font, (255, 255, 255))

    img.save(out_path, "PNG")


def _make_outro_card(
    out_path: str,
    dealer_name: Optional[str],
    dealer_phone: Optional[str],
    accent_rgb: tuple[int, int, int],
) -> None:
    img = Image.new("RGB", (TARGET_W, TARGET_H), (15, 15, 15))
    draw = ImageDraw.Draw(img)

    bar_h = 14
    draw.rectangle([0, TARGET_H // 2 - 220, TARGET_W, TARGET_H // 2 - 220 + bar_h], fill=accent_rgb)

    cta_font = _load_font(72)
    name_font = _load_font(96)
    phone_font = _load_font(84)

    _draw_centered_text(draw, "CALL FOR DETAILS", TARGET_H // 2 - 360, cta_font, accent_rgb)

    y = TARGET_H // 2 - 120
    if dealer_name:
        _draw_centered_text(draw, str(dealer_name), y, name_font, (255, 255, 255))
        y += 160
    if dealer_phone:
        _draw_centered_text(draw, str(dealer_phone), y, phone_font, (230, 230, 230))

    img.save(out_path, "PNG")


def _foreground_scale_for_ratio(src_w: int, src_h: int) -> float:
    """
    Return a target foreground scale multiplier based on photo aspect ratio.
    The caller applies crop protection to cap this before use.

    ratio < 0.75  → portrait / vertical  → 1.04 (machine tall, minimal boost)
    0.75–1.20     → near-square          → 1.12
    1.20–1.80     → standard horizontal  → 1.18
    > 1.80        → very wide            → 1.22
    """
    ratio = src_w / max(src_h, 1)
    if ratio < 0.75:
        return 1.04
    elif ratio < 1.20:
        return 1.12
    elif ratio < 1.80:
        return 1.18
    else:
        return 1.22


def _compose_photo_slide(
    src: str,
    dst: str,
    dealer_name: Optional[str] = None,
    dealer_phone: Optional[str] = None,
    accent_rgb: tuple[int, int, int] = (255, 204, 0),
    dealer_logo_path: Optional[str] = None,
) -> bool:
    """
    Compose a 1080x1920 photo slide with blurred cover-fill background
    and an optional industrial lower-rail branding overlay.

    Background: same photo scaled to cover the full canvas, then blurred + dimmed.
    Foreground: contain-fit × adaptive scale (ratio-dependent), with crop protection
    ensuring neither canvas edge is overflowed by more than MAX_CROP_FRACTION.
    """
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            sw, sh = im.size

            # --- Background: cover-fill → center-crop → blur → dim ---
            bg_scale = max(TARGET_W / sw, TARGET_H / sh)
            bg_w = max(1, int(sw * bg_scale))
            bg_h = max(1, int(sh * bg_scale))
            bg = im.resize((bg_w, bg_h), Image.LANCZOS)
            bx = (bg_w - TARGET_W) // 2
            by = (bg_h - TARGET_H) // 2
            bg = bg.crop((bx, by, bx + TARGET_W, by + TARGET_H))
            bg = bg.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))
            bg = bg.point(lambda p: int(p * 0.55))  # dim so foreground pops

            # --- Foreground: contain-fit × adaptive scale with crop protection ---
            contain_scale = min(TARGET_W / sw, TARGET_H / sh)
            contain_w_px = contain_scale * sw   # equals TARGET_W or TARGET_H at constraint
            contain_h_px = contain_scale * sh

            adaptive = _foreground_scale_for_ratio(sw, sh)

            # Crop protection: each canvas edge may overflow by at most MAX_CROP_FRACTION.
            # For the constrained dimension (which already fills the canvas edge), this
            # caps the scale at (1 + MAX_CROP_FRACTION). The unconstrained dimension has
            # room to grow and will not be the binding limit.
            max_scale_w = (TARGET_W * (1.0 + MAX_CROP_FRACTION)) / contain_w_px
            max_scale_h = (TARGET_H * (1.0 + MAX_CROP_FRACTION)) / contain_h_px
            effective = min(adaptive, max_scale_w, max_scale_h)

            print(
                f"  [Walkaround] {os.path.basename(src)}: "
                f"{sw}x{sh} ratio={sw/sh:.2f} "
                f"target={adaptive:.3f} effective={effective:.3f}"
            )

            fg_scale = contain_scale * effective
            fg_w = max(1, int(sw * fg_scale))
            fg_h = max(1, int(sh * fg_scale))
            fg = im.resize((fg_w, fg_h), Image.LANCZOS)

            # Center position; if foreground overflows, crop it symmetrically
            dst_x = (TARGET_W - fg_w) // 2
            dst_y = (TARGET_H - fg_h) // 2
            crop_l = max(0, -dst_x)
            crop_t = max(0, -dst_y)
            crop_r = fg_w - max(0, dst_x + fg_w - TARGET_W)
            crop_b = fg_h - max(0, dst_y + fg_h - TARGET_H)
            if crop_l or crop_t or crop_r < fg_w or crop_b < fg_h:
                fg = fg.crop((crop_l, crop_t, crop_r, crop_b))

            canvas = bg.copy()
            canvas.paste(fg, (max(0, dst_x), max(0, dst_y)))

            # Lower-rail: compute actual bottom edge of pasted foreground
            fg_actual_bottom = max(0, dst_y) + (crop_b - crop_t)
            canvas = _apply_lower_rail(
                canvas, dealer_name, dealer_phone, accent_rgb,
                dealer_logo_path, fg_actual_bottom,
            )
            canvas.save(dst, "PNG")
        return True
    except Exception as exc:
        print(f"  [Walkaround] photo compose failed for {src}: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Filter graph
# ─────────────────────────────────────────────────────────────────────────────

def _build_filter_complex(n_photos: int) -> str:
    """
    Build a filter_complex graph: intro + N static photo slides + outro,
    concatenated. Inputs order:
      [0] intro_card.png  (loop, t=INTRO_SECS)
      [1..n] photo_NN.png (loop, t=SLIDE_SECS each)
      [n+1] outro_card.png (loop, t=OUTRO_SECS)
    All inputs are already 1080x1920. Photos hold completely still for their
    full duration — no zoom, no pan, no drift.
    """
    parts: list[str] = []
    labels: list[str] = []

    # Intro
    parts.append(
        f"[0:v]setsar=1,fps={FPS},format=yuv420p,trim=duration={INTRO_SECS},setpts=PTS-STARTPTS[vintro]"
    )
    labels.append("[vintro]")

    # Photo slides — static hold, no motion
    for i in range(n_photos):
        in_idx = i + 1
        parts.append(
            f"[{in_idx}:v]setsar=1,fps={FPS},format=yuv420p,"
            f"trim=duration={SLIDE_SECS},setpts=PTS-STARTPTS[vp{i}]"
        )
        labels.append(f"[vp{i}]")

    # Outro
    out_idx = n_photos + 1
    parts.append(
        f"[{out_idx}:v]setsar=1,fps={FPS},format=yuv420p,trim=duration={OUTRO_SECS},setpts=PTS-STARTPTS[voutro]"
    )
    labels.append("[voutro]")

    # Concat
    concat_inputs = "".join(labels)
    parts.append(f"{concat_inputs}concat=n={len(labels)}:v=1:a=0[vout]")

    return ";".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_walkaround_video(
    photos: "list[str]",
    output_path: str,
    year: int,
    make: str,
    model: str,
    dealer_name: Optional[str] = None,
    dealer_phone: Optional[str] = None,
    accent_color: Optional[str] = None,
    dealer_logo_path: Optional[str] = None,
) -> str:
    """
    Render a 1080x1920 walkaround MP4.

    Raises ValueError if fewer than MIN_PHOTOS valid photos are provided.
    Silently truncates to MAX_PHOTOS.
    Returns the absolute output path.
    """
    valid = [
        p for p in (photos or [])
        if p and os.path.isfile(p) and Path(p).suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if len(valid) < MIN_PHOTOS:
        raise ValueError(
            f"Walkaround requires at least {MIN_PHOTOS} machine photos (got {len(valid)})."
        )
    if len(valid) > MAX_PHOTOS:
        valid = valid[:MAX_PHOTOS]

    ffmpeg = _find_ffmpeg()
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)

    tmp_dir = os.path.join(out_dir, "_walkaround_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    accent_rgb = _parse_accent(accent_color)

    try:
        # 1. Build cards
        intro_path = os.path.join(tmp_dir, "intro.png")
        outro_path = os.path.join(tmp_dir, "outro.png")
        _make_intro_card(intro_path, year, make, model, accent_rgb)
        _make_outro_card(outro_path, dealer_name, dealer_phone, accent_rgb)

        # 2. Compose photo slides (blurred bg + scaled fg + lower-rail overlay)
        photo_pngs: list[str] = []
        for i, src in enumerate(valid):
            dst = os.path.join(tmp_dir, f"photo_{i:02d}.png")
            if _compose_photo_slide(
                src, dst, dealer_name, dealer_phone, accent_rgb, dealer_logo_path
            ):
                photo_pngs.append(dst)

        if len(photo_pngs) < MIN_PHOTOS:
            raise RuntimeError(
                f"Only {len(photo_pngs)} photo(s) preprocessed successfully — need {MIN_PHOTOS}."
            )

        n = len(photo_pngs)

        # 3. Build ffmpeg command
        cmd: list[str] = [ffmpeg, "-y"]
        cmd += ["-loop", "1", "-t", str(INTRO_SECS), "-i", intro_path]
        for p in photo_pngs:
            cmd += ["-loop", "1", "-t", str(SLIDE_SECS), "-i", p]
        cmd += ["-loop", "1", "-t", str(OUTRO_SECS), "-i", outro_path]
        # Silent stereo audio source
        cmd += [
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        ]

        fc = _build_filter_complex(n)
        cmd += [
            "-filter_complex", fc,
            "-map", "[vout]",
            "-map", f"{n + 2}:a",
            "-c:v", "libx264",
            "-crf", "20",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]

        print(f"  [Walkaround] ffmpeg encoding {n} photos -> {os.path.basename(output_path)}")

        # 4. Run with single retry on non-zero exit
        attempts = 0
        last_err = ""
        while attempts < 2:
            attempts += 1
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=DEFAULT_TIMEOUT
                )
            except subprocess.TimeoutExpired:
                # Don't retry on timeout
                raise

            if result.returncode == 0 and os.path.isfile(output_path):
                break

            last_err = "\n".join(result.stderr.strip().splitlines()[-15:])
            print(f"  [Walkaround] ffmpeg attempt {attempts} failed (code {result.returncode}). "
                  f"Tail:\n{last_err}")

            if attempts < 2:
                time.sleep(2)

        if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(f"ffmpeg failed after retry. Stderr tail:\n{last_err}")

        size_kb = os.path.getsize(output_path) // 1024
        print(f"  [Walkaround] Done: {size_kb} KB, {n} slides")
        return os.path.abspath(output_path)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
