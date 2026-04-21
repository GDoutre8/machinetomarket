"""
renderers/badge_renderer.py
============================
Server-side light badge overlay for listing photos (Images 2+).

Badge layout — bottom-left corner:
    ┌──── accent stripe ──────────────────────────────────┐
    │  [Logo]  │  Contact Name                            │
    │          │  Phone                                   │
    └─────────────────────────────────────────────────────┘

Rules:
  - Applied ONLY to *_listing.jpg (never *_01_card.png)
  - Applied AFTER resize/crop, BEFORE zip
  - Photo is the primary visual — badge is secondary, bottom-left only
  - No title, no price, no spec strip

Public API
----------
apply_badge_to_photo(photo_path, logo_path, name, phone, accent, output_path) -> bool
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

# ── Accent palettes ────────────────────────────────────────────────────────────

_ACCENTS: dict[str, tuple[int, int, int]] = {
    "yellow": (245, 166,  35),
    "red":    (198,  40,  40),
}
_ACCENT_DEFAULT = _ACCENTS["yellow"]

# ── Badge background themes ────────────────────────────────────────────────────
# Auto-detected from logo artwork luminance — mirrors dealer_badge_renderer.js.

_DARK = {
    "bg":   (26,  26,  26),
    "text": (255, 255, 255),
    "muted":(160, 160, 160),
}
_WHITE = {
    "bg":   (255, 255, 255),
    "text": (26,  26,  26),
    "muted":(100, 100, 100),
}

_LUMA_THRESHOLD = 0.7
_NEAR_WHITE_CUT = 0.95
_MIN_USABLE_PX  = 50


# ── Internal helpers ───────────────────────────────────────────────────────────

def _linearize(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luma(r: int, g: int, b: int) -> float:
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _detect_theme(logo: Image.Image) -> dict:
    """Return DARK or WHITE badge palette based on logo artwork luminance."""
    rgba  = logo.convert("RGBA")
    data  = list(rgba.getdata())
    total, count = 0.0, 0
    for r, g, b, a in data:
        if a <= 10:
            continue
        lum = _luma(r, g, b)
        if lum > _NEAR_WHITE_CUT:
            continue
        total += lum
        count += 1
    if count < _MIN_USABLE_PX:
        return _DARK
    return _DARK if (total / count) > _LUMA_THRESHOLD else _WHITE


def _trim_bounds(logo: Image.Image) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) bounding box of non-transparent artwork pixels."""
    alpha = logo.convert("RGBA").split()[3]
    bbox  = alpha.point(lambda p: 255 if p > 10 else 0).getbbox()
    if bbox is None:
        return (0, 0, logo.width, logo.height)
    x0, y0, x1, y1 = bbox
    return (x0, y0, x1 - x0, y1 - y0)


def _font(size: int, bold: bool = False) -> "ImageFont.FreeTypeFont | ImageFont.ImageFont":
    """Load a sans-serif font; graceful fallback chain for all deployment targets."""
    candidates = (
        [   # Bold (contact name) — Montserrat Black preferred
            "/usr/share/fonts/truetype/montserrat/Montserrat-Black.ttf",
            "/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "/usr/share/fonts/truetype/carlito/Carlito-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [  # Regular (phone) — Montserrat Medium preferred
            "/usr/share/fonts/truetype/montserrat/Montserrat-Medium.ttf",
            "/usr/share/fonts/truetype/montserrat/Montserrat-Regular.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/carlito/Carlito-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)  # Pillow 10+
    except TypeError:
        return ImageFont.load_default()


# ── Public API ─────────────────────────────────────────────────────────────────

def apply_badge_to_photo(
    photo_path: str,
    logo_path: "str | None",
    name: "str | None",
    phone: "str | None",
    accent: str = "yellow",
    output_path: "str | None" = None,
) -> bool:
    """
    Stamp a light dealer badge onto a listing photo.

    Parameters
    ----------
    photo_path  : Source photo (JPEG/PNG).
    logo_path   : Dealer logo with transparency (PNG). Badge skipped if None/missing.
    name        : Contact name shown in the badge.
    phone       : Contact phone number.
    accent      : Accent color key — "yellow" (default) or "red".
    output_path : Write destination. Defaults to photo_path (in-place overwrite).

    Returns
    -------
    True on success, False on any failure — never raises, never blocks pipeline.
    """
    try:
        if not logo_path or not os.path.isfile(logo_path):
            return False
        if not name and not phone:
            return False

        out = output_path or photo_path
        accent_rgb = _ACCENTS.get(accent, _ACCENT_DEFAULT)

        photo    = Image.open(photo_path).convert("RGB")
        photo_w, photo_h = photo.size

        logo_src  = Image.open(logo_path).convert("RGBA")
        theme     = _detect_theme(logo_src)
        tx, ty, tw, th = _trim_bounds(logo_src)
        native_ar = tw / max(th, 1)

        # ── Badge sizing (fixed spec) ─────────────────────────────────────────
        badge_w  = min(700, max(400, round(photo_w * 0.45)))
        logo_h   = 80
        logo_w   = round(logo_h * native_ar)
        badge_h  = logo_h + 24

        ps       = logo_h / 90.0   # proportional scale factor
        pad_l    = 14
        pad_v    = 12
        gap      = 14
        div_w    = 5
        stripe_h = max(3, round(4  * ps))
        radius   = max(4, round(6  * ps))
        margin   = max(12, round(20 * ps))

        name_sz  = max(9,  round(18 * ps))
        phone_sz = max(8,  round(14 * ps))

        # ── Text lines ────────────────────────────────────────────────────────
        lines: list[tuple[str, int, tuple, bool]] = []
        if name:  lines.append((name,  name_sz,  theme["text"],  True))
        if phone: lines.append((phone, phone_sz, theme["muted"], False))
        if not lines:
            return False

        # ── Build badge canvas ────────────────────────────────────────────────
        badge = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
        bd    = ImageDraw.Draw(badge)

        # Background (rounded rect, semi-opaque)
        bd.rounded_rectangle(
            [0, 0, badge_w - 1, badge_h - 1],
            radius=radius,
            fill=(*theme["bg"], 230),
        )

        # Accent stripe — masked to rounded corners so top corners are clean
        stripe_mask = Image.new("L", (badge_w, badge_h), 0)
        smd = ImageDraw.Draw(stripe_mask)
        smd.rounded_rectangle([0, 0, badge_w - 1, badge_h - 1], radius=radius, fill=255)
        smd.rectangle([0, stripe_h, badge_w, badge_h], fill=0)
        badge.paste(
            Image.new("RGBA", (badge_w, badge_h), (*accent_rgb, 255)),
            (0, 0),
            stripe_mask,
        )

        # Logo — crop to artwork bounds, scale proportionally, no distortion
        logo_crop  = logo_src.crop((tx, ty, tx + tw, ty + th))
        logo_small = logo_crop.resize((logo_w, logo_h), Image.LANCZOS)
        badge.paste(logo_small, (pad_l, pad_v), logo_small)

        # Vertical accent divider
        bd2   = ImageDraw.Draw(badge)
        div_x = pad_l + logo_w + gap
        div_y0 = round(pad_v * 0.667)
        div_y1 = badge_h - round(pad_v * 1.333)
        bd2.rectangle([div_x, div_y0, div_x + div_w, div_y1], fill=(*accent_rgb, 255))

        # Text stack — vertically centered in badge
        text_x    = div_x + div_w + gap
        line_gap  = max(3, round(4 * ps))
        content_h = sum(sz for _, sz, _, _ in lines) + (len(lines) - 1) * line_gap
        text_y    = (badge_h - content_h) // 2

        for text, sz, col, bold in lines:
            bd2.text((text_x, text_y), text, fill=(*col, 255), font=_font(sz, bold=bold))
            text_y += sz + line_gap

        # ── Composite onto photo ───────────────────────────────────────────────
        bx = margin
        by = photo_h - margin - badge_h

        photo_rgba = photo.convert("RGBA")
        photo_rgba.paste(badge, (bx, by), badge)
        photo_rgba.convert("RGB").save(
            out,
            format="JPEG",
            quality=88,
            optimize=True,
            progressive=True,
            subsampling=0,
        )
        return True

    except Exception as exc:
        print(f"  [badge] FAIL {os.path.basename(photo_path)}: {exc}")
        return False
