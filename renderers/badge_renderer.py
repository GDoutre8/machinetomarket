"""
MTM Listing Badge Renderer
==========================

Composites a dealer contact badge onto listing photos #2-6.
Photo #1 (hero card) has its own full overlay and does NOT receive this badge.

Design spec (as reviewed and approved):
- Logo with near-white background       -> WHITE badge, black text
- Logo with transparent/colored/dark bg  -> DARK charcoal badge, white text
- Accent color (vertical divider) from dealer profile:
    "yellow" (MTM)  -> (244, 196, 0)
    "red"    (Rhino)-> (220, 38, 38)
- Typography: Montserrat Black (name), Montserrat Medium (phone)
- Phone auto-normalized to (xxx) xxx-xxxx
- Text block (name + phone) centered horizontally within its column
- Phone has 1px letter-spacing for more polished numerals
- Logo height 80px, badge height = 80 + 2*padding_y
- Badge width fits content (no hard minimum/maximum)
- Positioned bottom-left with margin + drop shadow

Required apt packages on Railway/Debian/Ubuntu:
    fonts-montserrat   (ships .otf files under /usr/share/fonts/opentype/)
    fonts-crosextra-carlito   (fallback)
    fonts-dejavu-core         (final fallback)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ─── Design tokens ────────────────────────────────────────────────────────────

WHITE_BG       = (255, 255, 255)
DARK_BG        = (24, 24, 26)
TEXT_ON_WHITE  = (17, 17, 17)
TEXT_ON_DARK   = (245, 245, 245)
SUB_ON_WHITE   = (85, 85, 85)
SUB_ON_DARK    = (190, 190, 195)

ACCENTS = {
    "yellow": (244, 196, 0),    # MTM
    "red":    (220, 38, 38),    # Rhino
}


# ─── Font loading ─────────────────────────────────────────────────────────────
#
# CRITICAL: Debian's `fonts-montserrat` package installs OTF files under
# /usr/share/fonts/opentype/montserrat/ — not TTF, not truetype/.
# Using the wrong path silently falls through the cascade to Carlito/DejaVu
# and rendered output looks nothing like Montserrat.

_FONT_CANDIDATES = {
    "black": [
        "/usr/share/fonts/opentype/montserrat/Montserrat-Black.otf",
        "/usr/share/fonts/opentype/montserrat/Montserrat-ExtraBold.otf",
        "/usr/share/fonts/opentype/montserrat/Montserrat-Bold.otf",
        "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "medium": [
        "/usr/share/fonts/opentype/montserrat/Montserrat-Medium.otf",
        "/usr/share/fonts/opentype/montserrat/Montserrat-Regular.otf",
        "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}


def _load_font(size: int, weight: str = "medium") -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES.get(weight, _FONT_CANDIDATES["medium"]):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _format_phone_us(phone: str) -> str:
    """Normalize to (xxx) xxx-xxxx. Returns original if not parseable to 10 digits."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return phone
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"


def _detect_logo_bg(logo_img: Image.Image) -> str:
    """Sample the four corners. Near-white + opaque -> 'white'. Else 'dark'.

    Pillow-only implementation (no numpy dependency). Each corner is cropped,
    pixels iterated with getdata(), and RGBA means computed in pure Python.
    Corner patches are tiny (typically 2-20 px on a side) so this is fast.
    """
    rgba = logo_img.convert("RGBA")
    w, h = rgba.size

    pw = max(2, min(w // 20, 20))
    ph = max(2, min(h // 20, 20))

    boxes = [
        (0,          0,          pw,       ph),        # top-left
        (w - pw,     0,          w,        ph),        # top-right
        (0,          h - ph,     pw,       h),         # bottom-left
        (w - pw,     h - ph,     w,        h),         # bottom-right
    ]

    def _rgba_means(img: Image.Image) -> tuple[float, float, float, float]:
        n = img.width * img.height
        if n == 0:
            return (0.0, 0.0, 0.0, 0.0)
        r_sum = g_sum = b_sum = a_sum = 0
        for (r, g, b, a) in img.getdata():
            r_sum += r
            g_sum += g
            b_sum += b
            a_sum += a
        return (r_sum / n, g_sum / n, b_sum / n, a_sum / n)

    corner_means = [_rgba_means(rgba.crop(b)) for b in boxes]

    # Any meaningfully transparent corner -> logo is NOT on a white background
    if min(m[3] for m in corner_means) < 200:
        return "dark"

    # Count corners where all three channels are >= 240 (near-white)
    white_corners = sum(
        1 for (r, g, b, _a) in corner_means
        if r >= 240 and g >= 240 and b >= 240
    )
    return "white" if white_corners >= 3 else "dark"


def _measure_tracked(font: ImageFont.FreeTypeFont, text: str, tracking: int = 0) -> tuple[int, int]:
    """Measure (width, height) of `text` drawn with `tracking` extra px per glyph."""
    if not text:
        return (0, 0)
    width = 0
    max_h = 0
    for ch in text:
        bbox = font.getbbox(ch)
        width += (bbox[2] - bbox[0]) + tracking
        max_h = max(max_h, bbox[3] - bbox[1])
    return (width - tracking, max_h)


def _draw_tracked(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill,
    tracking: int = 0,
) -> None:
    """Draw `text` at `xy` with `tracking` extra px between glyphs."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        bbox = font.getbbox(ch)
        x += (bbox[2] - bbox[0]) + tracking


# ─── Badge builder ────────────────────────────────────────────────────────────

def build_badge(
    logo_path: str,
    name: str,
    phone: str,
    accent: str = "yellow",
    *,
    target_logo_height: int = 80,
    padding_x: int = 14,
    padding_y: int = 14,
    divider_gap_logo: int = 10,
    divider_gap_text: int = 14,
    divider_width: int = 5,
    text_gap: int = 6,
    corner_radius: int = 10,
    phone_tracking: int = 1,
    name_size: int = 26,
    phone_size: int = 19,
) -> Image.Image:
    """
    Build the badge as an RGBA image with drop shadow baked in.

    Returns a PIL Image sized canvas_w × canvas_h; shadow extends
    `shadow_margin` pixels on each side of the visible badge.
    """
    # Logo
    logo = Image.open(logo_path).convert("RGBA")
    bg_kind = _detect_logo_bg(logo)

    if bg_kind == "white":
        badge_bg    = WHITE_BG
        name_color  = TEXT_ON_WHITE
        phone_color = SUB_ON_WHITE
    else:
        badge_bg    = DARK_BG
        name_color  = TEXT_ON_DARK
        phone_color = SUB_ON_DARK

    accent_rgb = ACCENTS.get(accent, ACCENTS["yellow"])

    # Scale logo to fixed target height; width flexes with aspect ratio
    lw, lh = logo.size
    scale   = target_logo_height / lh
    logo_w  = int(lw * scale)
    logo_h  = target_logo_height
    logo_scaled = logo.resize((logo_w, logo_h), Image.LANCZOS)

    # Fonts
    name_font   = _load_font(name_size,  "black")
    phone_font  = _load_font(phone_size, "medium")
    phone_disp  = _format_phone_us(phone)

    # Measure text block
    scratch = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    name_bbox = scratch.textbbox((0, 0), name, font=name_font)
    name_w    = name_bbox[2] - name_bbox[0]
    name_h    = name_bbox[3] - name_bbox[1]
    phone_w, phone_h = _measure_tracked(phone_font, phone_disp, tracking=phone_tracking)

    text_block_w = max(name_w, phone_w)
    text_block_h = name_h + text_gap + phone_h

    # Badge dimensions — fit content exactly, no minimum floor
    content_h = max(logo_h, text_block_h)
    badge_h   = content_h + 2 * padding_y
    badge_w   = (padding_x + logo_w + divider_gap_logo
                 + divider_width + divider_gap_text
                 + text_block_w + padding_x)

    # Canvas with shadow margin
    shadow_margin = 14
    canvas_w = badge_w + 2 * shadow_margin
    canvas_h = badge_h + 2 * shadow_margin
    canvas   = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Drop shadow: rounded rect, offset +3px Y, gaussian blur
    shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    sdraw.rounded_rectangle(
        (shadow_margin,              shadow_margin + 3,
         shadow_margin + badge_w,    shadow_margin + badge_h + 3),
        radius=corner_radius,
        fill=(0, 0, 0, 140),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=7))
    canvas.alpha_composite(shadow_layer)

    # Badge body (rounded rect)
    body = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(body)
    bdraw.rounded_rectangle(
        (shadow_margin,              shadow_margin,
         shadow_margin + badge_w,    shadow_margin + badge_h),
        radius=corner_radius,
        fill=badge_bg + (255,),
    )
    canvas.alpha_composite(body)

    draw = ImageDraw.Draw(canvas)

    # Logo (vertically centered in content area)
    x0     = shadow_margin + padding_x
    logo_y = shadow_margin + (badge_h - logo_h) // 2
    canvas.alpha_composite(logo_scaled, (x0, logo_y))

    # Divider (vertical accent bar)
    div_x   = x0 + logo_w + divider_gap_logo
    div_top = shadow_margin + padding_y + 3
    div_bot = shadow_margin + badge_h - padding_y - 3
    draw.rectangle(
        (div_x, div_top, div_x + divider_width, div_bot),
        fill=accent_rgb,
    )

    # Text block: each line centered within text_block_w
    text_col_x      = div_x + divider_width + divider_gap_text
    text_block_top  = shadow_margin + (badge_h - text_block_h) // 2

    # Name — centered horizontally within text column
    name_x = text_col_x + (text_block_w - name_w) // 2
    draw.text(
        (name_x - name_bbox[0], text_block_top - name_bbox[1]),
        name,
        font=name_font,
        fill=name_color,
    )

    # Phone — centered horizontally within text column, with letter-spacing
    phone_y = text_block_top + name_h + text_gap
    phone_x = text_col_x + (text_block_w - phone_w) // 2
    _draw_tracked(
        draw,
        (phone_x, phone_y),
        phone_disp,
        font=phone_font,
        fill=phone_color,
        tracking=phone_tracking,
    )

    return canvas


# ─── Photo compositor (public API) ────────────────────────────────────────────

def apply_badge_to_photo(
    photo_path: str,
    logo_path: str,
    name: str,
    phone: str,
    accent: str = "yellow",
    output_path: Optional[str] = None,
    margin_px: int = 28,
) -> Image.Image:
    """
    Paste the dealer badge at the bottom-left of the photo with `margin_px`
    from the photo edges, then either save to `output_path` (if given) or
    return the composited RGB image.

    `accent` must be one of ACCENTS keys ("yellow", "red"). Unknown values
    fall back to "yellow".
    """
    photo = Image.open(photo_path).convert("RGBA")
    badge = build_badge(logo_path, name, phone, accent=accent)

    pw, ph = photo.size
    bw, bh = badge.size

    # The badge's shadow_margin is 14; we want the visible badge's
    # bottom-left corner to sit margin_px from the photo's bottom-left.
    shadow_margin = 14
    x = margin_px - shadow_margin
    y = ph - bh + shadow_margin - margin_px

    photo.alpha_composite(badge, (x, y))
    final = photo.convert("RGB")

    if output_path:
        final.save(output_path, quality=92)
    return final


__all__ = [
    "apply_badge_to_photo",
    "build_badge",
    "ACCENTS",
]
