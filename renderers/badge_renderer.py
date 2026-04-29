"""
MTM Listing Badge Renderer
==========================

Composites a dealer contact badge onto listing photos #2-6.
Photo #1 (hero card) has its own full overlay and does NOT receive this badge.

Design spec (adaptive — integrated logo zone, no boxed container):
- Logo background auto-detected -> LIGHT or DARK badge mode
    brightness > 220                         -> LIGHT  (#F5F3EE)
    transparency present OR brightness < 180 -> DARK   (#17191C)
- Top accent rail: 4px yellow #F4B71A, full width
- Logo zone: NO border, NO fill block — background matches badge body so
  the mark fades into the badge instead of looking pasted into a box.
- Hairline divider (1px), theme-tinted, vertically centered and inset.
- Right column: name (Inter SemiBold) + phone, theme-aware colors.
- No outer stroke — drop shadow only for depth.
- Positioned bottom-left with fixed margin.

Font: Inter Medium (bundled at static/fonts/Inter-Medium.ttf)
Fallbacks: Montserrat → Calibri/Segoe → DejaVu
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ─── Design tokens ────────────────────────────────────────────────────────────

LIGHT_BG           = (245, 243, 238)          # #F5F3EE — warm off-white
DARK_BG            = ( 23,  25,  28)          # #17191C — near-black charcoal
ACCENT_YELLOW      = (244, 183, 26)           # #F4B71A — top accent rail
WHITE_BG           = LIGHT_BG                 # legacy alias
CHARCOAL_BG        = DARK_BG                  # legacy alias

NAME_ON_LIGHT      = ( 17,  17,  17)          # #111111
NAME_ON_DARK       = (255, 255, 255)          # #FFFFFF
PHONE_ON_LIGHT     = ( 68,  68,  68)          # #444444
PHONE_ON_DARK      = (244, 183, 26)           # #F4B71A — accent yellow

# Separator — pre-multiplied approximations of rgba over badge bg
# rgba(0,0,0,0.08) over #F5F3EE   ≈ (225,224,219)
# rgba(255,255,255,0.10) over #17191C ≈ (46,48,51)
SEP_ON_LIGHT      = (225, 224, 219)
SEP_ON_DARK       = ( 46,  48,  51)

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
# Name: Inter SemiBold (600 weight) — bundled at static/fonts/Inter-SemiBold.ttf.
# Phone: Inter Medium (500 weight)  — bundled at static/fonts/Inter-Medium.ttf.
# Both weights share the same fallback chain so typography degrades gracefully.

_BUNDLED_INTER_MEDIUM   = str(Path(__file__).parent.parent / "static" / "fonts" / "Inter-Medium.ttf")
_BUNDLED_INTER_SEMIBOLD = str(Path(__file__).parent.parent / "static" / "fonts" / "Inter-SemiBold.ttf")

# Legacy alias — existing callers that reference _BUNDLED_INTER still work
_BUNDLED_INTER = _BUNDLED_INTER_MEDIUM

_FONT_CANDIDATES = {
    "semibold": [
        # Bundled Inter SemiBold (primary — works on Railway and local dev)
        _BUNDLED_INTER_SEMIBOLD,
        # Fallback to Medium if SemiBold unavailable
        _BUNDLED_INTER_MEDIUM,
        # Linux (Railway/Debian)
        "/usr/share/fonts/opentype/montserrat/Montserrat-SemiBold.otf",
        "/usr/share/fonts/opentype/montserrat/Montserrat-Medium.otf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Windows
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "medium": [
        # Bundled Inter Medium
        _BUNDLED_INTER_MEDIUM,
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
        _BUNDLED_INTER_MEDIUM,
        "/usr/share/fonts/opentype/montserrat/Montserrat-Medium.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ],
    "black": [
        _BUNDLED_INTER_MEDIUM,
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

def detect_logo_background(logo_img: Image.Image) -> Literal["light", "dark"]:
    """Classify logo background and pick the matching badge mode.

    Default is DARK. Only return LIGHT when the uploaded logo has a clearly
    solid, opaque, light/white rectangular background — i.e. a logo that
    would visibly clash if dropped onto a dark badge.

    LIGHT requires ALL of:
      1. edge pixels are >85% light (per-pixel brightness >= 220)
      2. image is mostly opaque (>=98% of pixels with alpha >= 250)
      3. corner regions are all opaque AND light (rectangular filled bg)

    Transparent logos — including transparent white wordmarks — fail (1) or
    (2) and stay on the dark badge. Pillow-only (no numpy).
    """
    rgba = logo_img.convert("RGBA")
    w, h = rgba.size
    if w == 0 or h == 0:
        return "dark"

    # ---- (2) Whole-image opacity ----------------------------------------
    alpha = rgba.split()[-1]
    total_px = w * h
    opaque_px = 0
    for a in alpha.getdata():
        if a >= 250:
            opaque_px += 1
    opaque_ratio = opaque_px / total_px
    if opaque_ratio < 0.98:
        return "dark"

    # ---- (3) Corner regions: opaque AND light ---------------------------
    pw = max(2, min(w // 20, 20))
    ph = max(2, min(h // 20, 20))
    corner_boxes = [
        (0,      0,      pw,  ph),
        (w - pw, 0,      w,   ph),
        (0,      h - ph, pw,  h),
        (w - pw, h - ph, w,   h),
    ]

    def _means(box) -> tuple[float, float, float, float]:
        patch = rgba.crop(box)
        n = patch.width * patch.height
        if n == 0:
            return (0.0, 0.0, 0.0, 0.0)
        r_sum = g_sum = b_sum = a_sum = 0
        for (r, g, b, a) in patch.getdata():
            r_sum += r; g_sum += g; b_sum += b; a_sum += a
        return (r_sum / n, g_sum / n, b_sum / n, a_sum / n)

    for box in corner_boxes:
        rm, gm, bm, am = _means(box)
        if am < 240:
            return "dark"
        if (rm + gm + bm) / 3.0 < 230:
            return "dark"

    # ---- (1) Edge pixels: >85% bright ----------------------------------
    edge_pixels = []
    rgba_data = rgba.load()
    for x in range(w):
        edge_pixels.append(rgba_data[x, 0])
        edge_pixels.append(rgba_data[x, h - 1])
    for y in range(1, h - 1):
        edge_pixels.append(rgba_data[0, y])
        edge_pixels.append(rgba_data[w - 1, y])

    light_edge = 0
    for (r, g, b, a) in edge_pixels:
        if a < 250:
            continue
        if (r + g + b) / 3.0 >= 220:
            light_edge += 1
    if light_edge / max(1, len(edge_pixels)) < 0.85:
        return "dark"

    return "light"


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


def _has_dark_opaque_background(logo: Image.Image, threshold: int = 40) -> bool:
    """Return True if 3+ corners are near-black and opaque (dark canvas background)."""
    rgba = logo.convert("RGBA")
    w, h = rgba.size
    pw = max(2, min(w // 20, 20))
    ph = max(2, min(h // 20, 20))
    boxes = [
        (0,      0,      pw,  ph),
        (w - pw, 0,      w,   ph),
        (0,      h - ph, pw,  h),
        (w - pw, h - ph, w,   h),
    ]
    dark_corners = 0
    for box in boxes:
        patch = rgba.crop(box)
        n = patch.width * patch.height
        if n == 0:
            continue
        r_sum = g_sum = b_sum = a_sum = 0
        for (r, g, b, a) in patch.getdata():
            r_sum += r; g_sum += g; b_sum += b; a_sum += a
        rm, gm, bm, am = r_sum / n, g_sum / n, b_sum / n, a_sum / n
        if am >= 200 and rm <= threshold and gm <= threshold and bm <= threshold:
            dark_corners += 1
    return dark_corners >= 3


def _trim_transparent_padding(logo: Image.Image, alpha_threshold: int = 8) -> Image.Image:
    """Crop fully/near-transparent rows and columns from the logo edges.

    Used so dark-mode logos don't carry invisible padding that pushes the
    visible mark away from the divider and inflates the badge body.
    """
    rgba = logo.convert("RGBA")
    alpha = rgba.split()[-1]
    bbox = alpha.point(lambda v: 255 if v > alpha_threshold else 0).getbbox()
    if not bbox:
        return rgba
    if bbox == (0, 0, rgba.width, rgba.height):
        return rgba
    return rgba.crop(bbox)


def _trim_light_padding(logo: Image.Image, threshold: int = 240) -> Image.Image:
    """Crop near-white opaque rows and columns from the logo edges.

    Light-mode logos keep their white background but lose excess whitespace
    so the artwork sits tight against the divider.
    """
    rgba = logo.convert("RGBA")
    w, h = rgba.size
    data = rgba.load()

    def _is_content(x: int, y: int) -> bool:
        r, g, b, a = data[x, y]
        if a < 200:
            return True
        return not (r >= threshold and g >= threshold and b >= threshold)

    left, right, top, bot = w, -1, h, -1
    for y in range(h):
        for x in range(w):
            if _is_content(x, y):
                if x < left:  left = x
                if x > right: right = x
                if y < top:   top = y
                if y > bot:   bot = y
    if right < 0 or bot < 0:
        return rgba
    return rgba.crop((left, top, right + 1, bot + 1))


def _strip_outer_dark_bg(logo: Image.Image, threshold: int = 40) -> Image.Image:
    """Convert connected near-black background pixels to transparent via corner flood-fill.

    Flood-fills from the four image corners treating near-black pixels (all RGB <= threshold)
    as background. Only the contiguous region reachable from the edges is cleared — interior
    black artwork (text, lines, icons) that is not edge-connected is preserved.

    NOTE: Only call this when the logo has a dark/black canvas background. Do NOT chain
    after _strip_white_bg — that zeroes white interior pixels whose alpha < 20 would then
    be treated as passable by this flood-fill, corrupting interior white artwork.
    """
    rgba = logo.convert("RGBA")
    data = rgba.load()
    w, h = rgba.size

    def _is_bg(x: int, y: int) -> bool:
        r, g, b, a = data[x, y]
        # Only treat opaque near-black pixels as background — do NOT propagate through
        # already-transparent pixels, which may be interior artwork stripped by an
        # earlier pass.
        return a >= 200 and r <= threshold and g <= threshold and b <= threshold

    visited: set[tuple[int, int]] = set()
    queue: list[tuple[int, int]] = []

    for sx, sy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if (sx, sy) not in visited and _is_bg(sx, sy):
            visited.add((sx, sy))
            queue.append((sx, sy))

    while queue:
        cx, cy = queue.pop()
        r, g, b, _a = data[cx, cy]
        data[cx, cy] = (r, g, b, 0)
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited and _is_bg(nx, ny):
                visited.add((nx, ny))
                queue.append((nx, ny))

    return rgba


# ─── Badge builder ────────────────────────────────────────────────────────────

def build_badge(
    logo_path: str,
    name: str,
    phone: str,
    accent: str = "yellow",        # theme name — drives accent bar + phone color on dark
    *,
    force_variant: Optional[Literal["light", "dark", "white", "charcoal"]] = None,  # QA override; None = auto-detect
    logo_box_w: int = 210,          # ~16% narrower than v1 — tighter footprint
    logo_box_h: int = 58,           # ~15% shorter than v1
    padding_x: int = 11,
    padding_y: int = 10,
    gap: int = 12,                  # gap between logo right edge and text column
    sep_width: int = 1,             # 1px hairline divider
    text_gap: int = 5,
    corner_radius: int = 6,
    accent_bar_h: int = 4,
    name_size: int = 18,
    phone_size: int = 14,
    phone_tracking: int = 0,
) -> Image.Image:
    """Build the badge as an RGBA image with drop shadow baked in.

    Badge background is auto-selected from logo analysis:
      white logo bg   -> white badge (dark name + dark phone)
      everything else -> charcoal badge (white name + accent-colored phone)

    `accent` is the dealer theme name (yellow/red/blue/green/orange).
    It controls the top accent bar and the phone color on the charcoal variant.
    Unknown values fall back to MTM yellow.

    Logo is fit inside logo_box_w × logo_box_h preserving aspect ratio.
    Badge width is based on actual rendered logo width (logo_pw), not the fixed
    box allocation, so wide logos fill their column and no dead space appears.

    Returns a PIL Image of size (badge_w + 2*shadow_margin) × (badge_h + 2*shadow_margin).
    """
    logo = Image.open(logo_path).convert("RGBA")

    # Normalize legacy variant names ("white"/"charcoal") to current ("light"/"dark")
    _variant_alias = {"white": "light", "charcoal": "dark", "light": "light", "dark": "dark"}
    if force_variant in _variant_alias:
        bg_kind = _variant_alias[force_variant]
    else:
        bg_kind = detect_logo_background(logo)

    # Resolve accent color from theme name — fallback to MTM yellow
    accent_rgb = ACCENTS.get((accent or "yellow").lower().strip(), ACCENT_YELLOW)

    if bg_kind == "light":
        badge_bg    = LIGHT_BG
        name_color  = NAME_ON_LIGHT
        phone_color = PHONE_ON_LIGHT
        sep_color   = SEP_ON_LIGHT
    else:
        badge_bg    = DARK_BG
        name_color  = NAME_ON_DARK
        phone_color = PHONE_ON_DARK
        sep_color   = SEP_ON_DARK

    # Logo cleanup before compositing.
    # Light mode  : trim excess whitespace, preserve white backing — blends into #F5F3EE.
    # Dark mode   : strip outer matte (white or dark canvas) and trim transparent padding,
    #               so the mark floats directly on #17191C with no visible logo box.
    if bg_kind == "light":
        logo_src = _trim_light_padding(logo)
    else:
        if _has_dark_opaque_background(logo):
            logo_src = _strip_outer_dark_bg(logo)
        else:
            logo_src = _strip_white_bg(logo)
        logo_src = _trim_transparent_padding(logo_src)

    # Fit inside (logo_box_w × logo_box_h), aspect-preserved.
    lw, lh  = logo_src.size
    scale   = min(logo_box_w / lw, logo_box_h / lh)
    logo_pw = max(1, int(lw * scale))
    logo_ph = max(1, int(lh * scale))
    logo_scaled = logo_src.resize((logo_pw, logo_ph), Image.LANCZOS)

    # Fonts — name: Inter SemiBold (600), phone: Inter Medium (500)
    name_font  = _load_font(name_size,  "semibold")
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

    # Badge dimensions — width uses actual logo_pw so no dead space is allocated
    # around the logo; wide logos naturally fill their column.
    content_h = max(logo_ph, text_block_h)
    badge_h   = accent_bar_h + content_h + 2 * padding_y
    badge_w   = padding_x + logo_pw + gap + text_block_w + padding_x

    sm       = _BADGE_SHADOW_MARGIN
    canvas_w = badge_w + 2 * sm
    canvas_h = badge_h + 2 * sm
    canvas   = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Drop shadow — slightly stronger on light badges (contrast against bright photos),
    # subtler on dark (self-sufficient dark bg needs less lift).
    shadow_opacity = 120 if bg_kind == "light" else 88
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

    # Logo — left-aligned in its column, vertically centered in content
    logo_x = sm + padding_x
    logo_y = content_top + (content_h - logo_ph) // 2
    canvas.alpha_composite(logo_scaled, (logo_x, logo_y))

    # Vertical separator — 1px hairline, theme-aware tint, vertically centered and inset.
    sep_x      = sm + padding_x + logo_pw + (gap - sep_width) // 2
    sep_inset  = max(4, content_h // 4)        # shorter than full height — true center hairline
    sep_top_y  = content_top + sep_inset
    sep_bot_y  = content_top + content_h - sep_inset
    draw.rectangle((sep_x, sep_top_y, sep_x + sep_width - 1, sep_bot_y), fill=sep_color + (255,))

    # Text block — centered within its column, vertically centered in content area.
    # Each line is independently centered on text_block_w so name and phone align
    # to the same optical midpoint regardless of their individual widths.
    # Same logic runs for both white and dark variants.
    text_col_x = sm + padding_x + logo_pw + gap
    text_top_y = content_top + (content_h - text_block_h) // 2

    # Name — centered in text block
    name_offset_x = (text_block_w - name_w) // 2
    draw.text(
        (text_col_x + name_offset_x - name_bbox[0], text_top_y - name_bbox[1]),
        name,
        font=name_font,
        fill=name_color,
    )

    # Phone — centered in text block, clearly secondary via size and weight
    phone_offset_x = (text_block_w - phone_w) // 2
    phone_y_px = text_top_y + name_h + text_gap
    _draw_tracked(draw, (text_col_x + phone_offset_x, phone_y_px), phone_disp,
                  font=phone_font, fill=phone_color, tracking=phone_tracking)

    return canvas


def _initials(text: str) -> str:
    parts = [p for p in (text or "").strip().split() if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def build_text_badge(
    name: str,
    phone: str,
    accent: str = "yellow",
    *,
    padding_x: int = 14,
    padding_y: int = 12,
    gap: int = 14,
    sep_width: int = 3,
    text_gap: int = 5,
    corner_radius: int = 6,
    accent_bar_h: int = 4,
    name_size: int = 18,
    phone_size: int = 14,
    phone_tracking: int = 0,
    mark_size: int = 56,
    mark_text_size: int = 22,
) -> Image.Image:
    """Logoless badge variant — initials mark + name/phone on charcoal.

    Used when the dealer provides identity (name and/or phone) but no logo.
    Visual contract matches build_badge: same accent bar, drop shadow, and
    text column geometry — only the left column swaps the logo for an
    accent-tinted initials mark."""
    accent_rgb  = ACCENTS.get((accent or "yellow").lower().strip(), ACCENT_YELLOW)
    badge_bg    = DARK_BG
    name_color  = NAME_ON_DARK
    phone_color = PHONE_ON_DARK
    sep_color   = SEP_ON_DARK

    initials = _initials(name) or "MTM"
    name_font  = _load_font(name_size,      "semibold")
    phone_font = _load_font(phone_size,     "mono")
    mark_font  = _load_font(mark_text_size, "semibold")
    phone_disp = _format_phone_us(phone or "")

    scratch    = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    name_bbox  = scratch.textbbox((0, 0), name or "", font=name_font)
    name_w     = name_bbox[2] - name_bbox[0]
    name_h     = name_bbox[3] - name_bbox[1]
    phone_w, phone_h = _measure_tracked(phone_font, phone_disp, tracking=phone_tracking)

    text_block_w = max(name_w, phone_w)
    text_block_h = (name_h if name else 0) + (text_gap if name and phone_disp else 0) + (phone_h if phone_disp else 0)

    content_h = max(mark_size, text_block_h)
    badge_h   = accent_bar_h + content_h + 2 * padding_y
    badge_w   = padding_x + mark_size + gap + text_block_w + padding_x

    sm       = _BADGE_SHADOW_MARGIN
    canvas_w = badge_w + 2 * sm
    canvas_h = badge_h + 2 * sm
    canvas   = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    sdraw.rounded_rectangle(
        (sm, sm + 3, sm + badge_w, sm + badge_h + 3),
        radius=corner_radius,
        fill=(0, 0, 0, 88),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    canvas.alpha_composite(shadow_layer)

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
    draw.rectangle(
        (sm, sm, sm + badge_w, sm + accent_bar_h),
        fill=accent_rgb + (255,),
    )

    content_top = sm + accent_bar_h + padding_y
    mark_x = sm + padding_x
    mark_y = content_top + (content_h - mark_size) // 2
    draw.rounded_rectangle(
        (mark_x, mark_y, mark_x + mark_size, mark_y + mark_size),
        radius=4,
        fill=accent_rgb + (255,),
    )
    init_bbox = draw.textbbox((0, 0), initials, font=mark_font)
    init_w = init_bbox[2] - init_bbox[0]
    init_h = init_bbox[3] - init_bbox[1]
    draw.text(
        (mark_x + (mark_size - init_w) // 2 - init_bbox[0],
         mark_y + (mark_size - init_h) // 2 - init_bbox[1]),
        initials, font=mark_font, fill=CHARCOAL_BG,
    )

    sep_x      = sm + padding_x + mark_size + (gap - sep_width) // 2
    sep_inset  = max(4, content_h // 4)
    sep_top_y  = content_top + sep_inset
    sep_bot_y  = content_top + content_h - sep_inset
    draw.rectangle((sep_x, sep_top_y, sep_x + sep_width - 1, sep_bot_y), fill=sep_color + (255,))

    text_col_x = sm + padding_x + mark_size + gap
    text_top_y = content_top + (content_h - text_block_h) // 2

    if name:
        name_offset_x = (text_block_w - name_w) // 2
        draw.text(
            (text_col_x + name_offset_x - name_bbox[0], text_top_y - name_bbox[1]),
            name, font=name_font, fill=name_color,
        )
    if phone_disp:
        phone_offset_x = (text_block_w - phone_w) // 2
        phone_y_px = text_top_y + (name_h + text_gap if name else 0)
        _draw_tracked(draw, (text_col_x + phone_offset_x, phone_y_px), phone_disp,
                      font=phone_font, fill=phone_color, tracking=phone_tracking)

    return canvas


# ─── Photo compositor (public API) ────────────────────────────────────────────

# Fixed placement constants — badge always anchored bottom-left.
_PLACEMENT_PADDING_X = 24
_PLACEMENT_PADDING_Y = 24


def apply_badge_to_photo(
    photo_path: str,
    logo_path: Optional[str],
    name: str,
    phone: str,
    accent: str = "yellow",
    force_variant: Optional[Literal["light", "dark", "white", "charcoal"]] = None,
    output_path: Optional[str] = None,
) -> Image.Image:
    """
    Paste the dealer badge at the bottom-left of the photo.

    Badge background is auto-selected by logo analysis (light or dark).
    Legacy values "white"/"charcoal" remain accepted as aliases.
    When `logo_path` is missing, falls back to the text/initials badge variant
    so dealers who skip the logo upload still get branded photos.
    """
    photo = Image.open(photo_path).convert("RGBA")
    if logo_path and Path(logo_path).is_file():
        badge = build_badge(logo_path, name or "", phone or "", accent=accent, force_variant=force_variant)
    else:
        if not (name or phone):
            return photo.convert("RGB")
        badge = build_text_badge(name or "", phone or "", accent=accent)

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
    "build_text_badge",
    "detect_logo_background",
    "ACCENTS",
]
