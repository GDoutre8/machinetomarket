"""
spec_sheet_generator.py
=======================
Generates a single-image spec sheet (PNG) from listing_data + resolved_specs.

Used for:
  - Facebook / Marketplace uploads
  - Buyer email attachments
  - Listing image supplements

Entry point:
    generate_spec_sheet_image(listing_data, resolved_specs, ui_hints, output_path)

Layout (top → bottom):
  ┌─────────────────────────────────────┐
  │  HEADER (navy)  — machine title     │
  ├─ accent stripe (orange) ────────────┤
  │  PRICE  │  HOURS  (info bar)        │
  ├─ SPECIFICATIONS (navy) ─────────────┤
  │  spec label : value  │ label : val  │  (2-column alternating rows)
  ├─ FEATURES (navy) ───────────────────┤
  │  • feature 1                        │
  │  • feature 2  …                     │
  ├─────────────────────────────────────┤
  │  FOOTER (navy)  — contact / brand   │
  └─────────────────────────────────────┘
"""

from __future__ import annotations

import os
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise ImportError("Pillow is required: pip install Pillow")


# ── Canvas ────────────────────────────────────────────────────────────────────
SHEET_W = 1200          # fixed width
MARGIN  = 64            # left / right margin
COL_GAP = 40            # gap between the two spec columns
DIVIDER_X = SHEET_W // 2  # vertical divider between columns

# ── Colors ────────────────────────────────────────────────────────────────────
C_BG            = "#FFFFFF"
C_NAVY          = "#1B2A3B"
C_ORANGE        = "#E07B20"
C_LIGHT_GRAY    = "#F4F5F6"
C_MID_GRAY      = "#E0E1E3"
C_LABEL         = "#555555"
C_VALUE         = "#111111"
C_WHITE         = "#FFFFFF"
C_SECTION_TEXT  = "#FFFFFF"

# ── Font paths (Windows — Segoe UI preferred; Arial fallback) ─────────────────
_FONT_DIR   = r"C:\Windows\Fonts"
_FONT_REG   = os.path.join(_FONT_DIR, "segoeui.ttf")
_FONT_BOLD  = os.path.join(_FONT_DIR, "segoeuib.ttf")
_FONT_REG_F = os.path.join(_FONT_DIR, "arial.ttf")
_FONT_BLD_F = os.path.join(_FONT_DIR, "arialbd.ttf")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a TrueType font at *size* pt; fall back to Pillow's built-in bitmap font."""
    candidates = (
        [_FONT_BOLD, _FONT_BLD_F] if bold
        else [_FONT_REG, _FONT_REG_F]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    """Return pixel width of *text* rendered in *font*."""
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


# ── Full-level spec field definitions ─────────────────────────────────────────
# Each entry: (resolver_key, display_label, unit_suffix)
# Unit suffix appended after the value; empty string → no suffix.
_FULL_FIELDS: list[tuple[str, str, str]] = [
    ("net_hp",                          "Engine",                    "hp"),
    ("roc_lb",                          "Rated Operating Capacity",  "lbs"),
    ("tipping_load_lb",                 "Tipping Load",              "lbs"),
    ("operating_weight_lb",             "Operating Weight",          "lbs"),
    ("hydraulic_flow_gpm",              "Aux Hydraulic Flow",        "gpm"),
    ("hi_flow_gpm",                     "Aux Flow (High)",           "gpm"),
    ("hydraulic_pressure_standard_psi", "Hydraulic Pressure",        "psi"),
    ("travel_speed_high_mph",           "Max Travel Speed",          "mph"),
    ("travel_speed_low_mph",            "Travel Speed (Low)",        "mph"),
    ("fuel_type",                       "Fuel Type",                 ""),
    ("frame_size",                      "Frame Size",                ""),
]


def _fmt_val(val: Any, unit: str) -> str:
    """Format a spec value with optional unit suffix and comma-separated numbers."""
    if val is None:
        return "—"
    # Numeric: drop .0 from whole floats, add commas
    if isinstance(val, float) and val.is_integer():
        formatted = f"{int(val):,}"
    elif isinstance(val, int):
        formatted = f"{val:,}"
    elif isinstance(val, float):
        formatted = str(round(val, 1))
    else:
        formatted = str(val)
    return f"{formatted} {unit}".strip() if unit else formatted


def _build_spec_rows(
    resolved_specs: dict,
    ui_hints: dict,
) -> list[tuple[str, str]]:
    """
    Return a list of (label, formatted_value) pairs for the full spec level.
    Skips fields absent from resolved_specs.
    Applies hi-flow display logic to hydraulic_flow_gpm.
    """
    hi_flow_active = ui_hints.get("_displayHiFlow", False)
    rows: list[tuple[str, str]] = []

    for key, label, unit in _FULL_FIELDS:
        val = resolved_specs.get(key)
        if val is None:
            continue

        if key == "hydraulic_flow_gpm":
            hi_val = resolved_specs.get("hi_flow_gpm")
            if hi_flow_active:
                rows.append((label, f"{_fmt_val(val, '')} gpm high"))
            elif hi_val is not None:
                rows.append((label, f"{_fmt_val(val, '')} gpm std / {_fmt_val(hi_val, '')} gpm high"))
            else:
                rows.append((label, _fmt_val(val, unit)))
        elif key == "hi_flow_gpm":
            # Already folded into hydraulic_flow_gpm when _displayHiFlow is False;
            # skip entirely when _displayHiFlow is True (value already shown).
            if not hi_flow_active and resolved_specs.get("hydraulic_flow_gpm") is None:
                rows.append((label, _fmt_val(val, unit)))
            # else: handled above
        else:
            rows.append((label, _fmt_val(val, unit)))

    return rows


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _draw_rect(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, fill: str) -> None:
    draw.rectangle([(x0, y0), (x1, y1)], fill=fill)


def _draw_section_header(
    draw: ImageDraw.ImageDraw,
    y: int,
    label: str,
    height: int = 50,
    font_size: int = 22,
) -> int:
    """Draw a full-width dark-navy section header bar. Returns the new y cursor."""
    _draw_rect(draw, 0, y, SHEET_W, y + height, C_NAVY)
    f = _font(font_size, bold=True)
    draw.text((MARGIN, y + height // 2 - font_size // 2 - 1), label.upper(), font=f, fill=C_WHITE)
    return y + height


def _draw_spec_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    row_height: int,
    left_pair: tuple[str, str] | None,
    right_pair: tuple[str, str] | None,
    alt: bool,
) -> int:
    """
    Draw one two-column spec row.  Either pair may be None (last row, odd count).
    Returns new y cursor.
    """
    bg = C_LIGHT_GRAY if alt else C_BG
    _draw_rect(draw, 0, y, SHEET_W, y + row_height, bg)

    # Vertical divider between columns
    draw.line([(DIVIDER_X, y + 10), (DIVIDER_X, y + row_height - 10)], fill=C_MID_GRAY, width=1)

    label_font = _font(22, bold=False)
    value_font = _font(22, bold=True)
    text_y     = y + (row_height - 24) // 2   # vertically centered

    col_w = DIVIDER_X - MARGIN - COL_GAP      # usable width per column
    value_right_l = DIVIDER_X - COL_GAP // 2  # right edge of left value
    value_right_r = SHEET_W - MARGIN          # right edge of right value

    for pair, label_x, val_right in (
        (left_pair,  MARGIN,           value_right_l),
        (right_pair, DIVIDER_X + COL_GAP // 2, value_right_r),
    ):
        if pair is None:
            continue
        lbl, val = pair
        draw.text((label_x, text_y), lbl, font=label_font, fill=C_LABEL)
        val_w = _text_w(draw, val, value_font)
        draw.text((val_right - val_w, text_y), val, font=value_font, fill=C_VALUE)

    return y + row_height


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_spec_sheet_image(
    listing_data: dict,
    resolved_specs: dict,
    ui_hints:       dict | None = None,
    output_path:    str  | None = None,
) -> str:
    """
    Generate a spec sheet PNG for a single machine listing.

    Parameters
    ----------
    listing_data   : dict from _stub_build_listing_data (or equivalent)
                     Keys used: year, make, model, hours, price_value,
                                price_is_obo, features, attachments, contact
    resolved_specs : resolved_specs dict from spec_resolver output
    ui_hints       : ui_hints dict from spec_resolver output (optional)
    output_path    : destination path; defaults to <module_dir>/outputs/spec_sheet.png

    Returns
    -------
    str — absolute path to the written PNG file
    """
    if ui_hints is None:
        ui_hints = {}
    if resolved_specs is None:
        resolved_specs = {}

    # ── Resolve output path ────────────────────────────────────────────────
    if output_path is None:
        here        = os.path.dirname(os.path.abspath(__file__))
        output_dir  = os.path.join(here, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "spec_sheet.png")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # ── Pull listing fields ────────────────────────────────────────────────
    year      = str(listing_data.get("year") or "")
    make      = str(listing_data.get("make") or "")
    model     = str(listing_data.get("model") or "")
    hours_raw = listing_data.get("hours")
    price_raw = listing_data.get("price_value")
    price_obo = listing_data.get("price_is_obo", False)
    features  = listing_data.get("features") or []
    contact   = listing_data.get("contact") or ""

    title = " ".join(p for p in [year, make, model] if p) or "Heavy Equipment"
    hours_str = f"{hours_raw:,} hrs" if hours_raw else "—"
    if price_raw:
        price_str = f"${price_raw:,}"
        if price_obo:
            price_str += " OBO"
    else:
        price_str = "—"

    # ── Build spec rows ────────────────────────────────────────────────────
    spec_rows = _build_spec_rows(resolved_specs, ui_hints)

    # ── Calculate total canvas height ─────────────────────────────────────
    HEADER_H      = 140
    ACCENT_H      = 8
    INFO_BAR_H    = 100
    SEC_HDR_H     = 50
    SPEC_ROW_H    = 50
    FEATURE_ROW_H = 42
    FOOTER_H      = 90
    PADDING       = 24   # bottom padding before footer

    n_spec_rows  = max(1, -(-len(spec_rows) // 2))   # ceil division → row pairs
    n_feat_rows  = len(features)
    feat_section = (SEC_HDR_H + n_feat_rows * FEATURE_ROW_H + PADDING) if features else 0

    total_h = (
        HEADER_H
        + ACCENT_H
        + INFO_BAR_H
        + SEC_HDR_H
        + n_spec_rows * SPEC_ROW_H
        + PADDING
        + feat_section
        + FOOTER_H
    )
    total_h = max(total_h, 1200)   # floor at 1200px

    # ── Create canvas ──────────────────────────────────────────────────────
    img  = Image.new("RGB", (SHEET_W, total_h), C_BG)
    draw = ImageDraw.Draw(img)

    y = 0

    # ── 1. Header ─────────────────────────────────────────────────────────
    _draw_rect(draw, 0, y, SHEET_W, y + HEADER_H, C_NAVY)

    # Machine title
    title_font = _font(52, bold=True)
    # Auto-shrink if title is too wide
    while _text_w(draw, title, title_font) > SHEET_W - MARGIN * 2 - 20:
        title_font = _font(title_font.size - 2, bold=True)
        if title_font.size < 28:
            break

    title_y = y + (HEADER_H - title_font.size) // 2 - 4
    draw.text((MARGIN, title_y), title, font=title_font, fill=C_WHITE)

    # "Machine-to-Market" brand stamp — bottom-right of header
    brand_font = _font(18, bold=False)
    brand_text = "Machine-to-Market Spec Sheet"
    bw = _text_w(draw, brand_text, brand_font)
    draw.text((SHEET_W - MARGIN - bw, y + HEADER_H - 28), brand_text, font=brand_font, fill="#7A9ABF")

    y += HEADER_H

    # ── 2. Accent stripe ──────────────────────────────────────────────────
    _draw_rect(draw, 0, y, SHEET_W, y + ACCENT_H, C_ORANGE)
    y += ACCENT_H

    # ── 3. Price / Hours info bar ─────────────────────────────────────────
    _draw_rect(draw, 0, y, SHEET_W, y + INFO_BAR_H, C_BG)
    draw.line([(0, y + INFO_BAR_H - 1), (SHEET_W, y + INFO_BAR_H - 1)], fill=C_MID_GRAY, width=1)

    # Center the two info blocks
    lbl_font  = _font(20, bold=False)
    val_font  = _font(38, bold=True)

    # Price block — left quarter
    px = SHEET_W // 4
    pl_w = _text_w(draw, "ASKING PRICE", lbl_font)
    draw.text((px - pl_w // 2, y + 12), "ASKING PRICE", font=lbl_font, fill=C_LABEL)
    pv_w = _text_w(draw, price_str, val_font)
    draw.text((px - pv_w // 2, y + 38), price_str, font=val_font, fill=C_NAVY)

    # Vertical divider
    draw.line([(SHEET_W // 2, y + 16), (SHEET_W // 2, y + INFO_BAR_H - 16)], fill=C_MID_GRAY, width=1)

    # Hours block — right quarter
    hx = SHEET_W * 3 // 4
    hl_w = _text_w(draw, "HOURS", lbl_font)
    draw.text((hx - hl_w // 2, y + 12), "HOURS", font=lbl_font, fill=C_LABEL)
    hv_w = _text_w(draw, hours_str, val_font)
    draw.text((hx - hv_w // 2, y + 38), hours_str, font=val_font, fill=C_NAVY)

    y += INFO_BAR_H

    # ── 4. Specifications section ─────────────────────────────────────────
    y = _draw_section_header(draw, y, "Specifications", height=SEC_HDR_H)

    if spec_rows:
        for i in range(0, len(spec_rows), 2):
            left  = spec_rows[i]
            right = spec_rows[i + 1] if i + 1 < len(spec_rows) else None
            y = _draw_spec_row(draw, y, SPEC_ROW_H, left, right, alt=(i // 2) % 2 == 1)
    else:
        # No specs resolved — show a placeholder row
        _draw_rect(draw, 0, y, SHEET_W, y + SPEC_ROW_H, C_LIGHT_GRAY)
        no_spec_font = _font(22)
        draw.text((MARGIN, y + 13), "Specifications not available for this model.", font=no_spec_font, fill=C_LABEL)
        y += SPEC_ROW_H

    y += PADDING

    # ── 5. Features section (omit if empty) ──────────────────────────────
    if features:
        y = _draw_section_header(draw, y, "Features & Options", height=SEC_HDR_H)
        feat_font = _font(23)
        for feat in features:
            _draw_rect(draw, 0, y, SHEET_W, y + FEATURE_ROW_H, C_BG)
            draw.text((MARGIN + 12, y + (FEATURE_ROW_H - 24) // 2), f"• {feat}", font=feat_font, fill=C_VALUE)
            y += FEATURE_ROW_H
        y += PADDING

    # ── 6. Footer ─────────────────────────────────────────────────────────
    footer_y = total_h - FOOTER_H
    _draw_rect(draw, 0, footer_y, SHEET_W, total_h, C_NAVY)

    # Orange accent top edge of footer
    _draw_rect(draw, 0, footer_y, SHEET_W, footer_y + 4, C_ORANGE)

    footer_font = _font(22)
    footer_bold = _font(22, bold=True)

    if contact:
        contact_text = f"Contact:  {contact}"
        draw.text((MARGIN, footer_y + 20), contact_text, font=footer_bold, fill=C_WHITE)

    # Brand tagline — right-aligned
    tag_text = "Spec sheet generated by Machine-to-Market"
    tag_w    = _text_w(draw, tag_text, footer_font)
    draw.text((SHEET_W - MARGIN - tag_w, footer_y + 20), tag_text, font=footer_font, fill="#7A9ABF")

    # ── Save ───────────────────────────────────────────────────────────────
    img.save(output_path, "PNG", optimize=True)
    return output_path


# ── Facebook placement variant generator ─────────────────────────────────────
#
# Target dimensions (w × h) and the crop/pad rule applied:
#
#   4x5       1200 × 1500   taller than source  → scale to width, center on navy canvas
#   square    1200 × 1200   same ratio as source → scale to fit, no padding needed
#   story     1080 × 1920   much taller          → scale to width, center on navy canvas
#   landscape 1200 ×  630   wider than source   → scale to fill width, top-crop
#
# No stretching is ever applied — aspect ratio of the source is always preserved.

_VARIANT_SIZES: dict[str, tuple[int, int]] = {
    "4x5":       (1200, 1500),
    "square":    (1200, 1200),
    "story":     (1080, 1920),
    "landscape": (1200,  630),
}


def _make_variant(src: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Produce one variant at exactly (target_w × target_h) without stretching.

    Strategy
    --------
    - Target wider-or-equal to source aspect ratio (landscape, square):
        Scale to fill target width → crop excess height from the bottom,
        keeping the top of the image (title / price bar) always visible.
    - Target taller than source aspect ratio (4x5, story):
        Scale to fit target width → center the result vertically on a
        navy-branded canvas so no content is clipped and the frame looks
        intentional rather than padded with blank white space.
    """
    src_w, src_h = src.size
    src_ratio    = src_w / src_h
    tgt_ratio    = target_w / target_h

    if tgt_ratio >= src_ratio:
        # ── Wider-or-equal: fill width, top-crop ──────────────────────────
        scale  = target_w / src_w
        new_h  = round(src_h * scale)
        scaled = src.resize((target_w, new_h), Image.LANCZOS)
        if new_h >= target_h:
            # Crop from top — title / header always remains visible
            return scaled.crop((0, 0, target_w, target_h))
        # Edge case: scaled image is shorter than target (shouldn't occur here)
        canvas = Image.new("RGB", (target_w, target_h), C_BG)
        canvas.paste(scaled, (0, 0))
        return canvas
    else:
        # ── Taller: fit to width, center on navy canvas ────────────────────
        scale  = target_w / src_w
        new_h  = round(src_h * scale)
        scaled = src.resize((target_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), C_NAVY)
        y_off  = (target_h - new_h) // 2
        canvas.paste(scaled, (0, y_off))
        return canvas


def generate_spec_sheet_variants(spec_sheet_path: str) -> dict[str, str]:
    """
    Generate resized / cropped variants of a spec sheet PNG for Facebook placements.

    Parameters
    ----------
    spec_sheet_path : absolute path to an existing spec_sheet.png

    Returns
    -------
    dict mapping variant key → absolute output path::

        {
            "4x5":       ".../outputs/spec_sheet_4x5.png",
            "square":    ".../outputs/spec_sheet_square.png",
            "story":     ".../outputs/spec_sheet_story.png",
            "landscape": ".../outputs/spec_sheet_landscape.png",
        }
    """
    src     = Image.open(spec_sheet_path)
    out_dir = os.path.dirname(os.path.abspath(spec_sheet_path))
    results: dict[str, str] = {}

    for key, (target_w, target_h) in _VARIANT_SIZES.items():
        variant  = _make_variant(src, target_w, target_h)
        out_path = os.path.join(out_dir, f"spec_sheet_{key}.png")
        variant.save(out_path, "PNG", optimize=True)
        results[key] = out_path

    return results


# ── Public API: generate_spec_sheet() ────────────────────────────────────────
#
# Cleaner entry point that accepts pre-formatted spec_sheet tuples directly.
# Produces a fixed 1200 × 1200 square PNG — ready for Facebook, email, text.
#
# Dynamic layout adapts row height to fill the canvas for any spec count:
#   8  specs → ~4 rows pairs at ~108 px each (airy, clean)
#   10 specs → ~5 row pairs at ~108 px each
#   12 specs → ~6 row pairs at  ~88 px each (denser but readable)


def generate_spec_sheet(
    make: str,
    model: str,
    year: "str | int | None" = None,
    equipment_type: "str | None" = None,
    spec_sheet: "list[tuple[str, str]] | None" = None,
    dealer_name: "str | None" = None,
    phone: "str | None" = None,
    email: "str | None" = None,
    location: "str | None" = None,
    output_path: "str | None" = None,
) -> str:
    """
    Generate a 1200 × 1200 spec sheet PNG from pre-formatted spec tuples.

    Parameters
    ----------
    make, model, year   : machine identification
    equipment_type      : displayed as subtitle in header, e.g. "Skid Steer Loader"
    spec_sheet          : list of (label, value) display pairs, e.g.
                          [("Net HP", "92 hp"), ("Operating Weight", "10,515 lbs"), ...]
    dealer_name, phone, email, location : optional dealer contact for footer
    output_path         : override save path; defaults to
                          outputs/spec_sheets/spec_sheet_{make}_{model}.png

    Returns
    -------
    str — absolute path of the written PNG file
    """
    # ── Canvas constants ───────────────────────────────────────────────────
    CW, CH = 1200, 1200
    M       = 64       # left / right margin
    COL_DIV = CW // 2  # vertical divider between spec columns
    COL_PAD = 24       # horizontal padding inside each column

    # ── Layout heights ─────────────────────────────────────────────────────
    HEADER_H  = 190    # title + subtitle
    ACCENT_H  = 10
    SECHDR_H  = 54
    FOOTER_H  = 152
    FIXED_H   = HEADER_H + ACCENT_H + SECHDR_H + FOOTER_H   # ≈ 406 px

    rows       = list(spec_sheet or [])
    n_pairs    = max(1, (len(rows) + 1) // 2)
    avail_h    = CH - FIXED_H                                 # ≈ 794 px

    # Row height: fill available space, clamped to readable range
    row_h      = max(65, min(108, avail_h // n_pairs))
    spec_blk_h = n_pairs * row_h

    # Distribute leftover space: 1/3 above spec block, 2/3 below
    extra      = avail_h - spec_blk_h
    pad_top    = extra // 3
    pad_bot    = extra - pad_top          # absorbs rounding remainder

    # ── Title string ───────────────────────────────────────────────────────
    parts = [str(p) for p in [year, make, model] if p]
    title = " ".join(parts) if parts else "Heavy Equipment"

    # ── Canvas ─────────────────────────────────────────────────────────────
    img  = Image.new("RGB", (CW, CH), C_BG)
    draw = ImageDraw.Draw(img)
    y    = 0

    # ──────────────────────────────────────────────────────────────────────
    # 1. HEADER
    # ──────────────────────────────────────────────────────────────────────
    _draw_rect(draw, 0, y, CW, y + HEADER_H, C_NAVY)

    sub_font  = _font(26)
    sub_h     = 26
    sub_gap   = 10

    title_font = _font(60, bold=True)
    while _text_w(draw, title, title_font) > CW - M * 2 - 20:
        title_font = _font(title_font.size - 2, bold=True)
        if title_font.size < 28:
            break

    # Vertically center title + subtitle together
    subtitle   = equipment_type or ""
    blk_h      = title_font.size + (sub_gap + sub_h if subtitle else 0)
    title_y    = y + (HEADER_H - blk_h) // 2
    sub_y      = title_y + title_font.size + sub_gap

    draw.text((M, title_y), title, font=title_font, fill=C_WHITE)
    if subtitle:
        draw.text((M, sub_y), subtitle.upper(), font=sub_font, fill="#90B0CC")

    # MTM brand stamp — bottom-right of header
    brand_font = _font(17)
    brand_text = "Machine-to-Market"
    bw = _text_w(draw, brand_text, brand_font)
    draw.text((CW - M - bw, y + HEADER_H - 26), brand_text, font=brand_font, fill="#4A6A8A")

    y += HEADER_H

    # ──────────────────────────────────────────────────────────────────────
    # 2. ACCENT STRIPE
    # ──────────────────────────────────────────────────────────────────────
    _draw_rect(draw, 0, y, CW, y + ACCENT_H, C_ORANGE)
    y += ACCENT_H

    # ──────────────────────────────────────────────────────────────────────
    # 3. PADDING ABOVE SPECS
    # ──────────────────────────────────────────────────────────────────────
    y += pad_top

    # ──────────────────────────────────────────────────────────────────────
    # 4. "SPECIFICATIONS" SECTION HEADER
    # ──────────────────────────────────────────────────────────────────────
    y = _draw_section_header(draw, y, "Specifications", height=SECHDR_H, font_size=24)

    # ──────────────────────────────────────────────────────────────────────
    # 5. SPEC ROWS
    # ──────────────────────────────────────────────────────────────────────
    # Font sizes scale proportionally to row height
    lbl_sz  = max(17, round(row_h * 0.215))
    val_sz  = max(22, round(row_h * 0.295))
    lbl_fnt = _font(lbl_sz, bold=False)
    val_fnt = _font(val_sz, bold=True)

    for i in range(0, len(rows), 2):
        left  = rows[i]
        right = rows[i + 1] if i + 1 < len(rows) else None
        alt   = (i // 2) % 2 == 1

        _draw_rect(draw, 0, y, CW, y + row_h, C_LIGHT_GRAY if alt else C_BG)

        # Vertical column divider (subtle)
        draw.line(
            [(COL_DIV, y + 14), (COL_DIV, y + row_h - 14)],
            fill=C_MID_GRAY, width=1,
        )

        lbl_y = y + (row_h - lbl_sz) // 2
        val_y = y + (row_h - val_sz) // 2

        for pair, lx, rx in (
            (left,  M,              COL_DIV - COL_PAD),
            (right, COL_DIV + COL_PAD, CW - M),
        ):
            if pair is None:
                continue
            label, value = pair

            # Truncate label if too wide for its column half
            col_w  = rx - lx - (val_sz * 4)   # rough guard space for value
            lbl_w  = _text_w(draw, label, lbl_fnt)
            if lbl_w > col_w:
                # Shorten until it fits
                while lbl_w > col_w and len(label) > 3:
                    label  = label[:-1]
                    lbl_w  = _text_w(draw, label + "…", lbl_fnt)
                label += "…"

            draw.text((lx, lbl_y), label, font=lbl_fnt, fill=C_LABEL)

            vw = _text_w(draw, value, val_fnt)
            draw.text((rx - vw, val_y), value, font=val_fnt, fill=C_VALUE)

        y += row_h

    # ──────────────────────────────────────────────────────────────────────
    # 6. FOOTER  (anchored to bottom of canvas)
    # ──────────────────────────────────────────────────────────────────────
    fy = CH - FOOTER_H
    _draw_rect(draw, 0, fy, CW, CH, C_NAVY)
    _draw_rect(draw, 0, fy, CW, fy + 4, C_ORANGE)   # orange accent top edge

    dbold = _font(21, bold=True)
    dreg  = _font(19, bold=False)

    dealer_lines = []
    if dealer_name:
        dealer_lines.append((dealer_name, True))
    if phone:
        dealer_lines.append((phone, False))
    if email:
        dealer_lines.append((email, False))
    if location:
        dealer_lines.append((location, False))

    dy = fy + 16
    for txt, bold in dealer_lines:
        draw.text((M, dy), txt, font=(dbold if bold else dreg), fill=C_WHITE)
        dy += 28

    # MTM tagline — right-aligned, vertically centered in footer
    tag_fnt  = _font(19)
    tag_text = "Generated by Machine-to-Market"
    tw       = _text_w(draw, tag_text, tag_fnt)
    tag_y    = fy + (FOOTER_H - 19) // 2
    draw.text((CW - M - tw, tag_y), tag_text, font=tag_fnt, fill="#7A9ABF")

    # ──────────────────────────────────────────────────────────────────────
    # SAVE
    # ──────────────────────────────────────────────────────────────────────
    if output_path is None:
        here    = os.path.dirname(os.path.abspath(__file__))
        slug    = (make + "_" + model).replace(" ", "_").lower()
        out_dir = os.path.join(here, "outputs", "spec_sheets")
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, "spec_sheet_" + slug + ".png")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    img.save(output_path, "PNG", optimize=True)
    return output_path


# ── Quick smoke-test (run this file directly) ─────────────────────────────────
if __name__ == "__main__":
    _listing = {
        "year":         2019,
        "make":         "Bobcat",
        "model":        "T770",
        "hours":        1800,
        "price_value":  48500,
        "price_is_obo": False,
        "features":     ["High Flow Hydraulics", "Enclosed Cab", "Heat", "2-Speed Drive"],
        "contact":      "555-867-5309",
    }
    _specs = {
        "net_hp":                          92,
        "roc_lb":                          3475,
        "tipping_load_lb":                 6950,
        "operating_weight_lb":             11245,
        "hydraulic_flow_gpm":              37.0,
        "hi_flow_gpm":                     37.0,
        "hydraulic_pressure_standard_psi": 3600,
        "travel_speed_high_mph":           7.3,
        "travel_speed_low_mph":            5.5,
        "fuel_type":                       "Diesel",
        "frame_size":                      "Large",
    }
    _hints = {"_displayHiFlow": True}

    out = generate_spec_sheet_image(_listing, _specs, _hints)
    print(f"Spec sheet written: {out}")
    variants = generate_spec_sheet_variants(out)
    for k, p in variants.items():
        print(f"  variant [{k}]: {p}")
