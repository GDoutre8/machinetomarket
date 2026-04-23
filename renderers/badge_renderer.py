"""
MTM Listing Badge Renderer
==========================

Composites a dealer contact badge onto listing photos #2-6.
Photo #1 (hero card) has its own full overlay and does NOT receive this badge.

Design spec (Concept B — logo-adaptive):
- Logo background auto-detected -> WHITE badge or CHARCOAL badge (2-way only)
    Near-white opaque logo background  -> badge background #ffffff
    Everything else (transparent, colored, dark) -> badge background #1f2024
- Top accent bar: 4px yellow #f4b71a, full width, no top corner radius
- Two-column layout, gap 18px, vertically centered
    Left   : dealer logo mark, aspect-preserved, fitted in fixed box
    Center : 1px vertical separator (adaptive opacity)
    Right  : stacked contact block — name (17px/500) + phone (12px/mono)
- No outer stroke or border — drop shadow only for depth
- Positioned bottom-left with fixed margin

Font: Inter Medium (bundled at static/fonts/Inter-Medium.ttf)
Fallbacks: Montserrat → Calibri/Segoe → DejaVu
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ─── Design tokens ────────────────────────────────────────────────────────────

WHITE_BG           = (255, 255, 255)
CHARCOAL_BG        = (31,  32,  36)          # #1f2024
ACCENT_YELLOW      = (244, 183, 26)           # #f4b71a — top bar, always constant

NAME_ON_WHITE      = (31,  32,  36)           # #1f2024
NAME_ON_CHARCOAL   = (255, 255, 255)          # #ffffff
PHONE_ON_WHITE     = (107, 107, 107)          # #6b6b6b — muted, secondary to name
PHONE_ON_CHARCOAL  = (244, 183, 26)           # #f4b71a (yellow)

# Separator — pre-multiplied solid approximations of rgba alpha over badge bg
# rgba(0,0,0,0.15) over white   -> (217,217,217)
# rgba(255,255,255,0.15) over #1f2024 -> (69,70,74)
SEP_ON_WHITE      = (217, 217, 217)
SEP_ON_CHARCOAL   = (69,  70,  74)

# Theme accent palette — mirrors spec_sheet_renderer themes exactly.
# Badge accent bar and charcoal-variant phone text both use the resolved value.
ACCENTS = {
    "yellow": ACCENT_YELLOW,          # #f4b71a
    "red":    (200,  16,  46),        # #C8102E
    "blue":   ( 30,  77, 140),        # #1E4D8C
    "green":  ( 44,  95,  62),        # #2C5F3E
    "orange": (216,  90,  21),        # #D85A15
}

# Shadow margin baked into every badge canvas — must stay in sync with apply_badge_to_photo
_BADGE_SHADOW_MARGIN = 14


# ─── Font loading ─────────────────────────────────────────────────────────────
#
# Primary: Inter Medium bundled at static/fonts/Inter-Medium.ttf (name + phone).
# Both weights map to Inter Medium — phone is distinguished by size, not weight.
# Fallback chain: Montserrat → Calibri/Segoe → DejaVu.

_BUNDLED_INTER = str(Path(__file__).parent.parent / "static" / "fonts" / "Inter-Medium.ttf")

_FONT_CANDIDATES = {
    "medium": [
        # Bundled Inter (always first — works on Railway and local dev)
        _BUNDLED_INTER,
        # Linux (Railway/Debian) — Montserrat fallback
        "/usr/share/fonts/opentype/montserrat/Montserrat-Medium.otf",
        "/usr/share/fonts/opentype/montserrat/Montserrat-Regular.otf",
        "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Windows (local dev fallback)
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "mono": [
        # Inter Medium for phone (proportional, not monospace — matches design intent)
        _BUNDLED_INTER,
        "/usr/share/fonts/opentype/montserrat/Montserrat-Medium.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ],
    "black": [
        _BUNDLED_INTER,
        "/usr/share/fonts/opentype/montserrat/Montserrat-Black.otf",
        "/usr/share/fonts/opentype/montserrat/Montserrat-Bold.otf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
}


def _load_font(size: int, weight: str = "medium") -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES.get(weight, _FONT_CANDIDATES["medium"]):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ─── Logo background detection ────────────────────────────────────────────────

def detect_logo_background(logo_img: Image.Image) -> Literal["white", "other"]:
    """Sample four corner patches of the logo and classify background.

    Returns:
      "white"  — near-white opaque background  -> use white badge
      "other"  — transparent, colored, or dark -> use charcoal badge

    Pillow-only (no numpy). Corner patches are tiny so this is fast.
    """
    rgba = logo_img.convert("RGBA")
    w, h = rgba.size

    pw = max(2, min(w // 20, 20))
    ph = max(2, min(h // 20, 20))

    boxes = [
        (0,      0,      pw,  ph),
        (w - pw, 0,      w,   ph),
        (0,      h - ph, pw,  h),
        (w - pw, h - ph, w,   h),
    ]

    def _rgba_means(img: Image.Image) -> tuple[float, float, float, float]:
        n = img.width * img.height
        if n == 0:
            return (0.0, 0.0, 0.0, 0.0)
        r_sum = g_sum = b_sum = a_sum = 0
        for (r, g, b, a) in img.getdata():
            r_sum += r; g_sum += g; b_sum += b; a_sum += a
        return (r_sum / n, g_sum / n, b_sum / n, a_sum / n)

    corner_means = [_rgba_means(rgba.crop(b)) for b in boxes]

    # Any meaningfully transparent corner -> logo is not on a white background
    if min(m[3] for m in corner_means) < 200:
        return "other"

    # Count corners where all RGB channels >= 240 (near-white)
    white_corners = sum(
        1 for (r, g, b, _a) in corner_means
        if r >= 240 and g >= 240 and b >= 240
    )
    return "white" if white_corners >= 3 else "other"


# Legacy alias — internal callers used _detect_logo_bg
_detect_logo_bg = detect_logo_background


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _format_phone_us(phone: str) -> str:
    """Normalize to (xxx) xxx-xxxx. Returns original if not parseable to 10 digits."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return phone
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"


def _measure_tracked(font: ImageFont.FreeTypeFont, text: str, tracking: int = 0) -> tuple[int, int]:
    """Measure (width, height) of `text` with `tracking` extra px per glyph."""
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
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        bbox = font.getbbox(ch)
        x += (bbox[2] - bbox[0]) + tracking


def _strip_white_bg(logo: Image.Image, threshold: int = 230) -> Image.Image:
    """Convert near-white opaque pixels to transparent.

    Used when placing a logo onto a dark (charcoal) badge so a rectangular
    white bounding box doesn't create a "box within a box" effect.
    Only touches pixels whose RGB channels are all >= threshold AND alpha == 255.
    """
    rgba = logo.convert("RGBA")
    data = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = data[x, y]
            if a == 255 and r >= threshold and g >= threshold and b >= threshold:
                data[x, y] = (r, g, b, 0)
    return rgba


# ─── Badge builder ────────────────────────────────────────────────────────────

def build_badge(
    logo_path: str,
    name: str,
    phone: str,
    accent: str = "yellow",        # theme name — drives accent bar + phone color on charcoal
    *,
    force_variant: Optional[Literal["white", "charcoal"]] = None,  # QA override; None = auto-detect
    logo_box_w: int = 130,          # max logo bounding box width (horizontal baseline)
    logo_box_h: int = 48,           # max logo bounding box height
    padding_x: int = 35,
    padding_y: int = 28,
    gap: int = 18,                  # gap between logo box right edge and text left edge
    sep_width: int = 2,
    text_gap: int = 8,
    corner_radius: int = 13,
    accent_bar_h: int = 7,
    name_size: int = 31,
    phone_size: int = 21,
    phone_tracking: int = 0,
) -> Image.Image:
    """Build the badge as an RGBA image with drop shadow baked in.

    Badge background is auto-selected from logo analysis:
      white logo bg   -> white badge (dark name + dark phone)
      everything else -> charcoal badge (white name + accent-colored phone)

    `accent` is the dealer theme name (yellow/red/blue/green/orange).
    It controls the top accent bar and the phone color on the charcoal variant.
    Unknown values fall back to MTM yellow.

    Logo is fit inside logo_box_w × logo_box_h preserving aspect ratio —
    whichever constraint (width or height) is hit first governs the scale.

    Returns a PIL Image of size (badge_w + 2*shadow_margin) × (badge_h + 2*shadow_margin).
    """
    logo    = Image.open(logo_path).convert("RGBA")
    bg_kind = force_variant if force_variant in ("white", "charcoal") else detect_logo_background(logo)

    # Resolve accent color from theme name — fallback to MTM yellow
    accent_rgb = ACCENTS.get((accent or "yellow").lower().strip(), ACCENT_YELLOW)

    if bg_kind == "white":
        badge_bg    = WHITE_BG
        name_color  = NAME_ON_WHITE
        phone_color = PHONE_ON_WHITE   # dark on white — accent not used for phone
        sep_color   = SEP_ON_WHITE
    else:
        badge_bg    = CHARCOAL_BG
        name_color  = NAME_ON_CHARCOAL
        phone_color = accent_rgb       # accent-colored phone on charcoal
        sep_color   = SEP_ON_CHARCOAL

    # Logo: fit inside bounding box (logo_box_w × logo_box_h), aspect-preserved.
    # Horizontal logos hit the width constraint; tall logos hit the height constraint.
    # On charcoal badges, strip near-white bg pixels so no rectangular box shows.
    lw, lh  = logo.size
    scale   = min(logo_box_w / lw, logo_box_h / lh)
    logo_pw = int(lw * scale)      # actual pixel width of scaled logo
    logo_ph = int(lh * scale)      # actual pixel height of scaled logo
    logo_src = _strip_white_bg(logo) if bg_kind != "white" else logo
    logo_scaled = logo_src.resize((logo_pw, logo_ph), Image.LANCZOS)

    # Fonts
    name_font  = _load_font(name_size,  "medium")
    phone_font = _load_font(phone_size, "mono")
    phone_disp = _format_phone_us(phone)

    # Measure text
    scratch    = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    name_bbox  = scratch.textbbox((0, 0), name, font=name_font)
    name_w     = name_bbox[2] - name_bbox[0]
    name_h     = name_bbox[3] - name_bbox[1]
    phone_w, phone_h = _measure_tracked(phone_font, phone_disp, tracking=phone_tracking)

    text_block_w = max(name_w, phone_w)
    text_block_h = name_h + text_gap + phone_h

    # Badge dimensions
    content_h = max(logo_box_h, text_block_h)
    badge_h   = accent_bar_h + content_h + 2 * padding_y
    badge_w   = padding_x + logo_box_w + gap + text_block_w + padding_x

    sm       = _BADGE_SHADOW_MARGIN
    canvas_w = badge_w + 2 * sm
    canvas_h = badge_h + 2 * sm
    canvas   = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Drop shadow — slightly stronger on white badges (contrast against bright photos),
    # subtler on charcoal (self-sufficient dark bg needs less lift).
    shadow_opacity = 135 if bg_kind == "white" else 88
    shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    sdraw.rounded_rectangle(
        (sm, sm + 3, sm + badge_w, sm + badge_h + 3),
        radius=corner_radius,
        fill=(0, 0, 0, shadow_opacity),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    canvas.alpha_composite(shadow_layer)

    # Badge body — flat top corners, rounded bottom corners
    # Method: draw full rounded rect, then overdraw top corner_radius strip to flatten top.
    body  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(body)
    bdraw.rounded_rectangle(
        (sm, sm, sm + badge_w, sm + badge_h),
        radius=corner_radius,
        fill=badge_bg + (255,),
    )
    bdraw.rectangle(
        (sm, sm, sm + badge_w, sm + corner_radius),
        fill=badge_bg + (255,),
    )
    canvas.alpha_composite(body)

    draw = ImageDraw.Draw(canvas)

    # Top accent bar — theme accent color, flat top edge
    draw.rectangle(
        (sm, sm, sm + badge_w, sm + accent_bar_h),
        fill=accent_rgb + (255,),
    )

    # Content area origin
    content_top = sm + accent_bar_h + padding_y

    # Logo — centered within its fixed box, then vertically centered in content
    logo_x = sm + padding_x + (logo_box_w - logo_pw) // 2
    logo_y = content_top + (content_h - logo_ph) // 2
    canvas.alpha_composite(logo_scaled, (logo_x, logo_y))

    # Vertical separator — 1px, centered within gap, inset 1/5 content height top/bottom
    sep_x      = sm + padding_x + logo_box_w + (gap - sep_width) // 2
    sep_inset  = content_h // 5
    sep_top_y  = content_top + sep_inset
    sep_bot_y  = content_top + content_h - sep_inset
    draw.rectangle((sep_x, sep_top_y, sep_x + sep_width - 1, sep_bot_y), fill=sep_color)

    # Text block — vertically centered in content area
    text_col_x = sm + padding_x + logo_box_w + gap
    text_top_y = content_top + (content_h - text_block_h) // 2

    # Name (weight 500, letter-spacing -0.01em handled by font choice)
    name_x = text_col_x + (text_block_w - name_w) // 2
    draw.text(
        (name_x - name_bbox[0], text_top_y - name_bbox[1]),
        name,
        font=name_font,
        fill=name_color,
    )

    # Phone (mono, centered under name)
    phone_y_px = text_top_y + name_h + text_gap
    phone_x    = text_col_x + (text_block_w - phone_w) // 2
    _draw_tracked(draw, (phone_x, phone_y_px), phone_disp,
                  font=phone_font, fill=phone_color, tracking=phone_tracking)

    return canvas


# ─── Photo compositor (public API) ────────────────────────────────────────────

# Fixed placement constants — badge always anchored bottom-left.
_PLACEMENT_PADDING_X = 24
_PLACEMENT_PADDING_Y = 24


def apply_badge_to_photo(
    photo_path: str,
    logo_path: str,
    name: str,
    phone: str,
    accent: str = "yellow",
    force_variant: Optional[Literal["white", "charcoal"]] = None,
    output_path: Optional[str] = None,
) -> Image.Image:
    """
    Paste the dealer badge at the bottom-left of the photo.

    Badge background is auto-selected by logo analysis (white or charcoal).
    Depth comes from the badge's baked-in drop shadow — no dark buffer is drawn.
    """
    photo = Image.open(photo_path).convert("RGBA")
    badge = build_badge(logo_path, name, phone, accent=accent, force_variant=force_variant)

    pw, ph = photo.size
    bw, bh = badge.size
    sm = _BADGE_SHADOW_MARGIN

    # Align visible badge body to bottom-left with fixed padding.
    # Badge canvas extends sm px beyond visible body, so shift paste by -sm.
    x = _PLACEMENT_PADDING_X - sm
    y = ph - bh - _PLACEMENT_PADDING_Y + sm

    x = max(0, min(x, pw - bw))
    y = max(0, min(y, ph - bh))

    photo.alpha_composite(badge, (x, y))
    final = photo.convert("RGB")

    if output_path:
        final.save(output_path, quality=92)
    return final


__all__ = [
    "apply_badge_to_photo",
    "build_badge",
    "detect_logo_background",
    "ACCENTS",
]
