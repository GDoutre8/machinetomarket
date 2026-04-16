"""
spec_sheet_generator.py
=======================
Dealer-grade spec sheet image renderer for MTM listing assets.

Public APIs preserved:
    generate_spec_sheet_image(listing_data, resolved_specs, ui_hints, output_path)
    generate_spec_sheet_variants(spec_sheet_path)
    generate_spec_sheet(...)
"""

from __future__ import annotations

import math
import os
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise ImportError("Pillow is required: pip install Pillow") from exc


# ── Canvas & Layout ───────────────────────────────────────────────────────────
SHEET_W      = 1200
SHEET_H      = 1200
MARGIN       = 60          # outer left/right margin
COL_GAP      = 48          # gap between left and right grid columns
GRID_ROW_GAP = 40          # gap between top and bottom grid rows
ROW_H        = 68          # height per spec data row
HEAD_H       = 44          # section heading block height
CELL_PAD_X   = 20          # inner horizontal padding per cell
CELL_PAD_TOP = 26          # vertical padding above section heading
CELL_PAD_BOT = 22          # vertical padding below last row

# Legacy aliases kept for _draw_features_strip and _render_column
SECT_GAP     = GRID_ROW_GAP
BODY_PAD_TOP = CELL_PAD_TOP
BODY_PAD_BOT = CELL_PAD_BOT

# ── Color Palette ─────────────────────────────────────────────────────────────
C_BG      = "#F5F3EE"   # warm off-white body
C_HEADER  = "#1C2228"   # near-black charcoal header
C_ACCENT  = "#F4A100"   # yellow/gold accent
C_WHITE   = "#FFFFFF"
C_TEXT    = "#16212B"   # dark body text
C_MUTED   = "#647580"   # label gray — slightly darkened for legibility on light background
C_RULE    = "#DDD9D2"   # light row divider
C_FOOTER  = "#9EA8B0"   # footer text


# ── Font Resolution ───────────────────────────────────────────────────────────
_FONT_CANDIDATES_REG = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]
_FONT_CANDIDATES_BOLD = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REG
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_bbox(draw: ImageDraw.ImageDraw, text: str, font) -> tuple:
    return draw.textbbox((0, 0), text, font=font)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = _text_bbox(draw, text, font)
    return box[2] - box[0]


def _line_h(draw: ImageDraw.ImageDraw, font) -> int:
    box = _text_bbox(draw, "Ag", font)
    return box[3] - box[1]


def _tracked_text_width(draw, text, font, tracking):
    w = 0
    for i, ch in enumerate(text):
        w += _text_w(draw, ch, font)
        if i < len(text) - 1:
            w += tracking
    return w


def _draw_tracked_text(draw, x, y, text, font, fill, tracking=2):
    cx = x
    for i, ch in enumerate(text):
        draw.text((cx, y), ch, font=font, fill=fill)
        cx += _text_w(draw, ch, font)
        if i < len(text) - 1:
            cx += tracking


def _fit_font(draw, text, start_size, max_width, min_size=20, bold=False):
    size = start_size
    while size >= min_size:
        candidate = _font(size, bold=bold)
        if _text_w(draw, text, candidate) <= max_width:
            return candidate
        size -= 2
    return _font(min_size, bold=bold)


def _wrap_text(draw, text, font, max_width, max_lines=2):
    text = " ".join(str(text).split())
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        proposal = f"{current} {word}"
        if _text_w(draw, proposal, font) <= max_width:
            current = proposal
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    if len(lines) < max_lines:
        remaining = words[len(" ".join(lines).split()):]
        if remaining:
            current = " ".join(remaining)
        lines.append(current)
    lines = lines[:max_lines]
    while _text_w(draw, lines[-1], font) > max_width and len(lines[-1]) > 1:
        lines[-1] = lines[-1][:-1].rstrip()
    return lines


# ── Icon Drawing ──────────────────────────────────────────────────────────────

def _draw_section_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, section_name: str) -> None:
    """Thin-line section icon — unique per section type."""
    name = (section_name or "").upper()
    c = C_ACCENT

    if "PERF" in name:
        # Speedometer: half-circle arc + baseline + needle
        draw.arc((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=c, width=2)
        draw.line((cx - r, cy, cx + r, cy), fill=c, width=2)
        nx = cx + int(r * 0.62 * math.cos(math.radians(-48)))
        ny = cy + int(r * 0.62 * math.sin(math.radians(-48)))
        draw.line((cx, cy, nx, ny), fill=c, width=2)
        draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=c)

    elif "DIM" in name:
        # Ruler: rectangle + 3 interior tick marks
        rw, rh = r, r // 2 + 2
        draw.rectangle((cx - rw, cy - rh, cx + rw, cy + rh), outline=c, width=2)
        step = (rw * 2) // 4
        for i in range(1, 4):
            tx = cx - rw + i * step
            draw.line((tx, cy - rh, tx, cy - rh + rh // 2 + 1), fill=c, width=2)

    elif "CONFIG" in name:
        # Crossed tools: two diagonals with dot caps
        pad = max(r // 4, 2)
        draw.line((cx - r + pad, cy - r + pad, cx + r - pad, cy + r - pad), fill=c, width=3)
        draw.line((cx + r - pad, cy - r + pad, cx - r + pad, cy + r - pad), fill=c, width=3)
        e = max(r // 4, 3)
        for ddx, ddy in [(-1, -1), (1, 1), (1, -1), (-1, 1)]:
            ex = cx + ddx * (r - pad - 1)
            ey = cy + ddy * (r - pad - 1)
            draw.ellipse((ex - e, ey - e, ex + e, ey + e), fill=c)

    elif "CONDITION" in name or "MACHINE" in name:
        # Clock: circle outline + hour + minute hands
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=2)
        draw.line((cx, cy, cx - r // 2, cy - r // 2), fill=c, width=2)
        draw.line((cx, cy, cx, cy - int(r * 0.75)), fill=c, width=2)
        draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=c)

    else:
        s = r - 4
        draw.rectangle((cx - s, cy - s, cx + s, cy + s), fill=c)


# ── Section / Row Rendering ───────────────────────────────────────────────────

def _draw_section_heading(
    draw: ImageDraw.ImageDraw,
    x0: int,
    x1: int,
    y: int,
    section_name: str,
) -> int:
    """
    Draw: [icon circle] SECTION NAME
                        ─────────────────
    Returns y position after the heading block (including yellow rule).
    """
    icon_r = 14  # proper icon radius
    icon_cx = x0 + icon_r
    icon_cy = y + HEAD_H // 2
    _draw_section_icon(draw, icon_cx, icon_cy, icon_r, section_name)

    head_font = _font(17, bold=True)
    text_x = x0 + icon_r * 2 + 10
    text_y = y + (HEAD_H - _line_h(draw, head_font)) // 2
    _draw_tracked_text(draw, text_x, text_y, section_name.upper(), head_font, C_TEXT, tracking=2)

    rule_y = y + HEAD_H
    draw.line((x0, rule_y, x1, rule_y), fill=C_ACCENT, width=2)

    return rule_y + 8


def _draw_spec_row(
    draw: ImageDraw.ImageDraw,
    x0: int,
    x1: int,
    y: int,
    label: str,
    value: str,
    price_row: bool = False,
) -> None:
    """
    Document-style row:
      LABEL (uppercase, light gray, left)     VALUE (bold, dark, right-pinned to x1)
      ──────────────────────────────────────────────────────────────────────────────
    price_row=True adds subtle top-rule and bolder value for Asking Price emphasis.
    """
    label_font = _font(12, bold=False)

    # Value font: allow up to 60% of row width so values never crowd labels
    max_val_w = int((x1 - x0) * 0.60)
    value_font = _fit_font(draw, value, 23, max_val_w, min_size=16, bold=True)

    val_lh = _line_h(draw, value_font)
    lbl_lh = _line_h(draw, label_font)

    # Vertically center value; align label baseline to value baseline
    val_top = y + (ROW_H - val_lh) // 2
    lbl_top = val_top + (val_lh - lbl_lh)

    # Price row: faint top separator + slightly lighter rule to make it stand out
    if price_row:
        draw.line((x0, y + 1, x1, y + 1), fill="#C8C2B8", width=1)

    # Label — light muted gray, uppercase
    draw.text((x0, lbl_top), label.upper(), font=label_font, fill=C_MUTED)

    # Value — right-pinned to x1, bold dark
    val_fill = C_TEXT if not price_row else "#0D1820"   # near-black for price
    val_w = _text_w(draw, value, value_font)
    draw.text((x1 - val_w, val_top), value, font=value_font, fill=val_fill)

    # Thin bottom divider
    draw.line((x0, y + ROW_H, x1, y + ROW_H), fill=C_RULE, width=1)


def _render_column(
    draw: ImageDraw.ImageDraw,
    sections: list[tuple[str, list[tuple[str, str]]]],
    x0: int,
    x1: int,
    y_start: int,
) -> int:
    """Render a list of sections stacked vertically. Returns final y."""
    y = y_start
    for section_name, rows in sections:
        y = _draw_section_heading(draw, x0, x1, y, section_name)
        for label, value in rows:
            is_price = label.lower() == "asking price"
            _draw_spec_row(draw, x0, x1, y, label, value, price_row=is_price)
            y += ROW_H
        y += SECT_GAP
    return y


# ── Field Definitions & Data Building ────────────────────────────────────────

# Preserved for backward compat (used by generate_spec_sheet)
_FULL_FIELDS: list[tuple[str, str, str]] = [
    ("net_hp", "Engine", "hp"),
    ("roc_lb", "Rated Operating Capacity", "lbs"),
    ("tipping_load_lb", "Tipping Load", "lbs"),
    ("operating_weight_lb", "Operating Weight", "lbs"),
    ("hydraulic_flow_gpm", "Aux Hydraulic Flow", "gpm"),
    ("hi_flow_gpm", "Aux Flow (High)", "gpm"),
    ("hydraulic_pressure_standard_psi", "Hydraulic Pressure", "psi"),
    ("travel_speed_high_mph", "Max Travel Speed", "mph"),
    ("travel_speed_low_mph", "Travel Speed (Low)", "mph"),
    ("fuel_type", "Fuel Type", ""),
    ("frame_size", "Frame Size", ""),
]

# ── Equipment Type Normalization ──────────────────────────────────────────────

_EQ_TYPE_ALIASES: dict[str, str] = {
    "compact_track_loader": "compact_track_loader",
    "ctl":                  "compact_track_loader",
    "skid_steer":           "skid_steer",
    "skid_steer_loader":    "skid_steer",
    "ssl":                  "skid_steer",
    "mini_excavator":       "mini_excavator",
    "mini_ex":              "mini_excavator",
    "compact_excavator":    "mini_excavator",
    "excavator":            "mini_excavator",
    "telehandler":          "telehandler",
    "tele_handler":         "telehandler",
    "backhoe_loader":       "backhoe_loader",
    "backhoe":              "backhoe_loader",
    "boom_lift":            "boom_lift",
    "articulated_boom_lift":"boom_lift",
    "telescopic_boom_lift": "boom_lift",
    "scissor_lift":         "scissor_lift",
    "wheel_loader":         "wheel_loader",
    "dozer":                "dozer",
    "crawler_dozer":        "dozer",
}


def _normalize_eq_type(raw: str) -> str:
    key = str(raw).lower().strip().replace(" ", "_").replace("-", "_")
    return _EQ_TYPE_ALIASES.get(key, key)


# ── Core Spec Profiles ────────────────────────────────────────────────────────
# Field tuple: (spec_key, display_label, display_unit, source)
#   "specs"   → resolved_specs dict
#   "listing" → listing_data dict
#   "derived" → computed (key prefixed with _ is a virtual field)
#
# Fields are pulled in order; missing fields are skipped gracefully.
# Each section renders at most 4 rows; MACHINE CONDITION at most 3.

CORE_SPEC_PROFILES: dict[str, dict[str, list[tuple[str, str, str, str]]]] = {

    "compact_track_loader": {
        "PERFORMANCE": [
            ("net_hp",             "Engine Power",             "HP",  "specs"),
            ("roc_lb",             "Rated Operating Capacity", "LB",  "specs"),
            ("hydraulic_flow_gpm", "Aux Hydraulic Flow",       "GPM", "specs"),
            ("tipping_load_lb",    "Tipping Load",             "LB",  "specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb", "Operating Weight",    "LB", "specs"),
            ("width_in",            "Machine Width",       "IN", "specs"),
            ("hinge_pin_height_in", "Hinge Pin Height",    "IN", "specs"),
            ("length_in",           "Length (w/o Bucket)", "IN", "specs"),
        ],
        "CONFIGURATION": [
            ("lift_type",    "Lift Path",        "", "specs"),
            ("_high_flow",   "High Flow Option", "", "derived"),
            ("_two_speed",   "Travel Speed",     "", "derived"),
            ("track_type",   "Track Type",       "", "specs"),
            ("cab_type",     "Cab Type",         "", "specs"),
            ("ride_control", "Ride Control",     "", "derived"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",            "HRS", "listing"),
            ("track_condition",   "Track Condition",  "",    "listing"),
            ("overall_condition", "Overall Condition","",    "listing"),
            ("price_value",       "Asking Price",     "",    "listing"),
        ],
    },

    "skid_steer": {
        "PERFORMANCE": [
            ("net_hp",             "Engine Power",             "HP",  "specs"),
            ("roc_lb",             "Rated Operating Capacity", "LB",  "specs"),
            ("hydraulic_flow_gpm", "Aux Hydraulic Flow",       "GPM", "specs"),
            ("tipping_load_lb",    "Tipping Load",             "LB",  "specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb", "Operating Weight",    "LB", "specs"),
            ("width_in",            "Machine Width",       "IN", "specs"),
            ("hinge_pin_height_in", "Hinge Pin Height",    "IN", "specs"),
            ("length_in",           "Length (w/o Bucket)", "IN", "specs"),
        ],
        "CONFIGURATION": [
            ("lift_type",    "Lift Path",        "", "specs"),
            ("_high_flow",   "High Flow Option", "", "derived"),
            ("_two_speed",   "Travel Speed",     "", "derived"),
            ("tire_type",    "Tire Type",        "", "specs"),
            ("cab_type",     "Cab Type",         "", "specs"),
            ("ride_control", "Ride Control",     "", "derived"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",            "HRS", "listing"),
            ("tire_condition",    "Tire Condition",   "",    "listing"),
            ("overall_condition", "Overall Condition","",    "listing"),
            ("price_value",       "Asking Price",     "",    "listing"),
        ],
    },

    "mini_excavator": {
        "PERFORMANCE": [
            ("net_hp",           "Engine Power",   "HP", "specs"),
            ("max_dig_depth",    "Max Dig Depth",  "",   "specs"),   # resolved string: "X ft Y in"
            ("bucket_breakout_lb","Breakout Force","LB", "specs"),
            ("operating_weight_lb","Op. Weight",   "LB", "specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb","Operating Weight","LB", "specs"),
            ("width_in",           "Machine Width",   "IN", "specs"),
            ("max_dump_height_ft", "Dump Height",     "FT", "specs"),
            ("max_reach_ft",       "Max Reach",       "FT", "specs"),
        ],
        "CONFIGURATION": [
            ("tail_swing_type", "Tail Swing",     "", "specs"),   # passthrough string normalized
            ("_aux_hyd",        "Aux Hydraulics", "", "derived"),
            ("cab_type",        "Cab Type",       "", "specs"),
            ("blade_type",      "Blade",          "", "specs"),
            ("thumb_type",      "Thumb",          "", "specs"),
            ("track_type",      "Track Type",     "", "specs"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",           "HRS", "listing"),
            ("track_condition",   "Undercarriage",   "",    "listing"),
            ("overall_condition", "Overall Condition","",   "listing"),
            ("price_value",       "Asking Price",    "",    "listing"),
        ],
    },

    "telehandler": {
        "PERFORMANCE": [
            ("net_hp",               "Engine Power",      "HP", "specs"),
            ("max_lift_capacity_lb", "Max Lift Capacity", "LB", "specs"),
            ("max_lift_height_in",   "Max Lift Height",   "IN", "specs"),
            ("operating_weight_lb",  "Operating Weight",  "LB", "specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb",  "Operating Weight",  "LB", "specs"),
            ("max_lift_height_in",   "Max Lift Height",   "IN", "specs"),
            ("max_forward_reach_in", "Max Forward Reach", "IN", "specs"),
            ("length_in",            "Overall Length",    "IN", "specs"),
        ],
        "CONFIGURATION": [
            ("_stabilizers",  "Stabilizers",   "", "derived"),
            ("cab_type",      "Cab Type",      "", "specs"),
            ("_two_speed",    "Travel Speed",  "", "derived"),
            ("carriage_type", "Carriage Type", "", "specs"),
            ("tire_type",     "Tire Type",     "", "specs"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",            "HRS", "listing"),
            ("overall_condition", "Overall Condition","",    "listing"),
            ("price_value",       "Asking Price",     "",    "listing"),
        ],
    },

    "backhoe_loader": {
        "PERFORMANCE": [
            ("net_hp",            "Engine Power",     "HP", "specs"),
            ("loader_cap_lb",     "Loader Capacity",  "LB", "specs"),
            ("backhoe_cap_lb",    "Backhoe Capacity", "LB", "specs"),
            ("operating_weight_lb","Operating Weight","LB", "specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb",  "Operating Weight",   "LB", "specs"),
            ("max_dig_depth_in",     "Max Dig Depth",      "IN", "specs"),
            ("loader_dump_height_in","Loader Dump Height", "IN", "specs"),
            ("length_in",            "Overall Length",     "IN", "specs"),
        ],
        "CONFIGURATION": [
            ("cab_type",     "Cab Type",     "", "specs"),
            ("_two_speed",   "Travel Speed", "", "derived"),
            ("tire_type",    "Tire Type",    "", "specs"),
            ("quick_attach", "Quick Attach", "", "specs"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",            "HRS", "listing"),
            ("overall_condition", "Overall Condition","",    "listing"),
            ("price_value",       "Asking Price",     "",    "listing"),
        ],
    },

    "boom_lift": {
        "PERFORMANCE": [
            ("net_hp",              "Engine Power",      "HP", "specs"),
            ("platform_capacity_lb","Platform Capacity", "LB", "specs"),
            ("max_platform_height_in","Max Platform Ht","IN", "specs"),
            ("operating_weight_lb", "Operating Weight",  "LB", "specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb",   "Operating Weight",  "LB", "specs"),
            ("max_platform_height_in","Max Platform Ht",   "IN", "specs"),
            ("max_horizontal_reach_in","Horizontal Reach", "IN", "specs"),
            ("width_in",              "Machine Width",     "IN", "specs"),
        ],
        "CONFIGURATION": [
            ("fuel_type",  "Fuel Type",   "", "specs"),
            ("drive_type", "Drive",       "", "specs"),
            ("cab_type",   "Cab Type",    "", "specs"),
            ("jib_type",   "Jib",         "", "specs"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",            "HRS", "listing"),
            ("overall_condition", "Overall Condition","",    "listing"),
            ("price_value",       "Asking Price",     "",    "listing"),
        ],
    },

    "scissor_lift": {
        "PERFORMANCE": [
            ("platform_capacity_lb",  "Platform Capacity", "LB", "specs"),
            ("max_platform_height_in","Max Platform Ht",   "IN", "specs"),
            ("operating_weight_lb",   "Operating Weight",  "LB", "specs"),
            ("net_hp",                "Engine Power",      "HP", "specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb",   "Operating Weight",  "LB", "specs"),
            ("max_platform_height_in","Max Platform Ht",   "IN", "specs"),
            ("width_in",              "Machine Width",     "IN", "specs"),
            ("length_in",             "Platform Length",   "IN", "specs"),
        ],
        "CONFIGURATION": [
            ("fuel_type",  "Fuel Type",   "", "specs"),
            ("drive_type", "Drive",       "", "specs"),
            ("deck_ext",   "Deck Ext.",   "", "specs"),
            ("cab_type",   "Cab Type",    "", "specs"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",            "HRS", "listing"),
            ("overall_condition", "Overall Condition","",    "listing"),
            ("price_value",       "Asking Price",     "",    "listing"),
        ],
    },

    "wheel_loader": {
        "PERFORMANCE": [
            ("net_hp",              "Engine Power",       "HP", "specs"),
            ("bucket_capacity_cy",  "Bucket Capacity",    "CY", "specs"),
            ("operating_weight_lb", "Operating Weight",   "LB", "specs"),
            ("hydraulic_flow_gpm",  "Aux Hydraulic Flow", "GPM","specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb", "Operating Weight", "LB", "specs"),
            ("dump_height_in",      "Dump Height",      "IN", "specs"),
            ("length_in",           "Overall Length",   "IN", "specs"),
            ("width_in",            "Machine Width",    "IN", "specs"),
        ],
        "CONFIGURATION": [
            ("cab_type",     "Cab Type",    "", "specs"),
            ("_two_speed",   "Travel Speed","", "derived"),
            ("tire_type",    "Tire Type",   "", "specs"),
            ("quick_attach", "Quick Attach","", "specs"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",            "HRS", "listing"),
            ("overall_condition", "Overall Condition","",    "listing"),
            ("price_value",       "Asking Price",     "",    "listing"),
        ],
    },

    "dozer": {
        "PERFORMANCE": [
            ("net_hp",              "Engine Power",     "HP", "specs"),
            ("blade_capacity_cy",   "Blade Capacity",   "CY", "specs"),
            ("operating_weight_lb", "Operating Weight", "LB", "specs"),
            ("max_drawbar_pull_lb", "Max Drawbar Pull", "LB", "specs"),
        ],
        "DIMENSIONS": [
            ("operating_weight_lb","Operating Weight", "LB", "specs"),
            ("blade_width_in",     "Blade Width",      "IN", "specs"),
            ("ground_clearance_in","Ground Clearance", "IN", "specs"),
            ("length_in",          "Overall Length",   "IN", "specs"),
        ],
        "CONFIGURATION": [
            ("cab_type",    "Cab Type",    "", "specs"),
            ("blade_type",  "Blade Type",  "", "specs"),
            ("track_type",  "Track Type",  "", "specs"),
            ("ripper_type", "Ripper",      "", "specs"),
        ],
        "MACHINE CONDITION": [
            ("hours",             "Hours",            "HRS", "listing"),
            ("overall_condition", "Overall Condition","",    "listing"),
            ("price_value",       "Asking Price",     "",    "listing"),
        ],
    },
}


# ── Profile Field Resolver ────────────────────────────────────────────────────

def _resolve_profile_field(
    key: str,
    label: str,
    unit: str,
    source: str,
    resolved_specs: dict,
    listing_data: dict,
    ui_hints: dict,
    features_lower: list[str],
) -> "tuple[str, str] | None":
    """
    Resolve one profile field → (display_label, formatted_value) or None if unavailable.
    Handles all special cases: derived booleans, status strings, listing fields, price.
    """
    hi_flow_active = ui_hints.get("_displayHiFlow", False)

    # ── Virtual / derived fields ──────────────────────────────────────────────
    if key == "_high_flow":
        hi_val = resolved_specs.get("hi_flow_gpm")
        if hi_val or hi_flow_active or any("high flow" in f for f in features_lower):
            return (label, "YES")
        return None

    if key == "_two_speed":
        val = resolved_specs.get("two_speed")
        if val is None:
            if any("2-speed" in f or "two-speed" in f or "two speed" in f for f in features_lower):
                return (label, "2-SPEED")
            return None
        if isinstance(val, bool):
            return (label, "2-SPEED" if val else "SINGLE")
        s = str(val).lower()
        return (label, "2-SPEED" if s in ("yes", "true", "1", "on") else "SINGLE")

    if key == "ride_control":
        val = resolved_specs.get("ride_control")
        if val is None:
            if any("ride control" in f for f in features_lower):
                return (label, "YES")
            return None
        return (label, "YES" if val else "NO")

    if key == "_zero_tail":
        val = resolved_specs.get("zero_tail_swing")
        if val is None:
            return None
        return (label, "ZERO TAIL" if val else "CONVENTIONAL")

    if key == "_aux_hyd":
        val = resolved_specs.get("aux_hydraulics")
        if val is None:
            if any("aux hyd" in f or "auxiliary" in f for f in features_lower):
                return (label, "YES")
            return None
        return (label, "YES" if val else "NO")

    if key == "_stabilizers":
        val = resolved_specs.get("has_stabilizers")
        if val is None:
            return None
        return (label, "YES" if val else "NO")

    # ── Passthrough string normalization ──────────────────────────────────────
    if key == "tail_swing_type":
        val = resolved_specs.get("tail_swing_type")
        if not val:
            return None
        s = str(val).lower().replace("_", " ").strip()
        if "zero" in s:
            return (label, "ZERO TAIL")
        if "minimal" in s or "reduced" in s:
            return (label, "MINIMAL TAIL")
        return (label, "CONVENTIONAL")

    # ── max_dig_depth: already a formatted string "X ft Y in" ─────────────────
    if key == "max_dig_depth":
        val = resolved_specs.get("max_dig_depth")
        if val is None:
            return None
        return (label, str(val).upper())

    # ── Listing-data fields ───────────────────────────────────────────────────
    if source == "listing":
        val = listing_data.get(key)
        if val is None or val == "":
            return None
        if key == "hours":
            try:
                return (label, f"{int(val):,} HRS")
            except (ValueError, TypeError):
                return (label, str(val).upper())
        if key == "price_value":
            try:
                price_str = f"${int(val):,}"
                if listing_data.get("price_is_obo"):
                    price_str += " OBO"
                return (label, price_str)
            except (ValueError, TypeError):
                return None
        return (label, str(val).upper())

    # ── Resolved-spec fields ──────────────────────────────────────────────────
    if key == "hydraulic_flow_gpm":
        val = resolved_specs.get("hydraulic_flow_gpm")
        if val is None:
            return None
        hi_val = resolved_specs.get("hi_flow_gpm")
        if hi_val and not hi_flow_active:
            return (label, f"{_fmt_val(val, '')} / {_fmt_val(hi_val, '')} GPM")
        return (label, f"{_fmt_val(val, '')} GPM")

    val = resolved_specs.get(key)
    if val is None:
        return None
    if isinstance(val, bool):
        return (label, "YES" if val else "NO")
    formatted = _fmt_val(val, unit)
    return (label, formatted.upper()) if formatted else None


# ── Profile Section Builder ───────────────────────────────────────────────────

def _build_section_from_profile(
    section_name: str,
    field_defs: list[tuple[str, str, str, str]],
    resolved_specs: dict,
    listing_data: dict,
    ui_hints: dict,
    max_rows: int = 4,
) -> list[tuple[str, str]]:
    """Pull rows in profile order; skip missing fields; cap at max_rows."""
    features_lower = [str(f).lower() for f in (listing_data.get("features") or [])]
    rows: list[tuple[str, str]] = []
    for key, lbl, unit, source in field_defs:
        if len(rows) >= max_rows:
            break
        result = _resolve_profile_field(
            key, lbl, unit, source,
            resolved_specs, listing_data, ui_hints, features_lower,
        )
        if result is not None:
            rows.append(result)
    return rows


# Grouped field definitions for the dynamic fallback (unrecognized types)
_SECTION_GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("PERFORMANCE", [
        ("net_hp",                         "Engine Power",             "HP"),
        ("roc_lb",                         "Rated Operating Capacity", "LB"),
        ("hydraulic_flow_gpm",             "Aux Hydraulic Flow",       "GPM"),
        ("tipping_load_lb",                "Tipping Load",             "LB"),
        ("travel_speed_high_mph",          "Max Travel Speed",         "MPH"),
        ("hydraulic_pressure_standard_psi","Hydraulic Pressure",       "PSI"),
    ]),
    ("DIMENSIONS", [
        ("operating_weight_lb", "Operating Weight",    "LB"),
        ("width_in",            "Machine Width",       "IN"),
        ("hinge_pin_height_in", "Hinge Pin Height",    "IN"),
        ("length_in",           "Length (w/o Bucket)", "IN"),
        ("dump_height_in",      "Dump Height",         "IN"),
        ("reach_in",            "Reach",               "IN"),
        ("dig_depth_in",        "Dig Depth",           "IN"),
    ]),
    ("CONFIGURATION", [
        ("lift_type",  "Lift Path",   ""),
        ("track_type", "Track Type",  ""),
        ("tire_type",  "Tire Type",   ""),
        ("cab_type",   "Cab Type",    ""),
        ("fuel_type",  "Fuel Type",   ""),
    ]),
]


def _fmt_val(val: Any, unit: str) -> str:
    if val is None:
        return "—"
    if isinstance(val, float) and val.is_integer():
        formatted = f"{int(val):,}"
    elif isinstance(val, int):
        formatted = f"{val:,}"
    elif isinstance(val, float):
        formatted = str(round(val, 1))
    else:
        formatted = str(val)
    return f"{formatted} {unit}".strip() if unit else formatted


def _build_spec_rows(resolved_specs: dict, ui_hints: dict) -> list[tuple[str, str]]:
    """Legacy flat row builder (kept for generate_spec_sheet backward compat)."""
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
            if not hi_flow_active and resolved_specs.get("hydraulic_flow_gpm") is None:
                rows.append((label, _fmt_val(val, unit)))
        else:
            rows.append((label, _fmt_val(val, unit)))
    return rows


def _build_grouped_rows_from_profile(
    profile: dict[str, list[tuple[str, str, str, str]]],
    resolved_specs: dict,
    listing_data: dict,
    ui_hints: dict,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Dispatch to profile-based section building for a known equipment type."""
    section_order = ["PERFORMANCE", "DIMENSIONS", "CONFIGURATION", "MACHINE CONDITION"]
    result: list[tuple[str, list[tuple[str, str]]]] = []
    for section_name in section_order:
        field_defs = profile.get(section_name)
        if not field_defs:
            continue
        max_rows = 3 if section_name == "MACHINE CONDITION" else 4
        rows = _build_section_from_profile(
            section_name, field_defs,
            resolved_specs, listing_data, ui_hints, max_rows=max_rows,
        )
        if rows:
            result.append((section_name, rows))
    return result


def _build_grouped_rows(
    resolved_specs: dict,
    ui_hints: dict,
    listing_data: dict,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """
    Returns [(section_name, [(label, value), ...]), ...] for the 2×2 grid.
    Dispatches to CORE_SPEC_PROFILES for known equipment types;
    falls back to dynamic field scanning for unrecognized types.
    """
    eq_type_raw = (
        listing_data.get("equipment_type")
        or resolved_specs.get("equipment_type")
        or ""
    )
    eq_type = _normalize_eq_type(eq_type_raw)
    profile = CORE_SPEC_PROFILES.get(eq_type)
    if profile:
        return _build_grouped_rows_from_profile(profile, resolved_specs, listing_data, ui_hints)
    return _build_grouped_rows_dynamic(resolved_specs, ui_hints, listing_data)


def _build_grouped_rows_dynamic(
    resolved_specs: dict,
    ui_hints: dict,
    listing_data: dict,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """
    Fallback: dynamic field scanning for equipment types without a profile.
    PERFORMANCE (max 4) | DIMENSIONS (max 4)
    CONFIGURATION (max 4) | MACHINE CONDITION (max 3)
    """
    hi_flow_active = ui_hints.get("_displayHiFlow", False)
    features_lower = [str(f).lower() for f in (listing_data.get("features") or [])]

    # Per-section row limits (strict — keeps layout balanced in 2×2 grid)
    _ROW_LIMITS = {
        "PERFORMANCE":       4,
        "DIMENSIONS":        4,
        "CONFIGURATION":     4,
        "MACHINE CONDITION": 3,
    }

    result: list[tuple[str, list[tuple[str, str]]]] = []

    for section_name, fields in _SECTION_GROUPS:
        rows: list[tuple[str, str]] = []

        for key, label, unit in fields:
            val = resolved_specs.get(key)

            # --- Hydraulic flow: combined display ---
            if key == "hydraulic_flow_gpm":
                if val is None:
                    continue
                hi_val = resolved_specs.get("hi_flow_gpm")
                if hi_flow_active:
                    rows.append((label, f"{_fmt_val(val, '')} GPM"))
                elif hi_val is not None:
                    rows.append((label, f"{_fmt_val(val, '')} / {_fmt_val(hi_val, '')} GPM"))
                else:
                    rows.append((label, _fmt_val(val, unit).upper()))
                continue

            if key == "hi_flow_gpm":
                # Only shown standalone if hydraulic_flow_gpm is absent
                if not hi_flow_active and resolved_specs.get("hydraulic_flow_gpm") is None and val is not None:
                    rows.append((label, _fmt_val(val, unit).upper()))
                continue

            if val is None:
                continue

            if isinstance(val, bool):
                rows.append((label, "YES" if val else "NO"))
            else:
                rows.append((label, _fmt_val(val, unit).upper()))

        # --- CONFIGURATION extras from features/ui_hints ---
        if section_name == "CONFIGURATION":
            # High flow option
            has_hi_flow = (
                resolved_specs.get("hi_flow_gpm") is not None
                or hi_flow_active
                or any("high flow" in f for f in features_lower)
            )
            if has_hi_flow:
                rows.append(("High Flow Option", "YES"))

            # Ride control — show both YES and NO (decision-relevant; listed before travel speed)
            ride_val = resolved_specs.get("ride_control")
            if ride_val is not None:
                rows.append(("Ride Control", "YES" if ride_val else "NO"))
            elif any("ride control" in f for f in features_lower):
                rows.append(("Ride Control", "YES"))

            # Two-speed (lower priority than ride control in brochure view)
            two_speed_val = resolved_specs.get("two_speed")
            if two_speed_val is not None:
                rows.append(("Travel Speed", "2-SPEED" if two_speed_val else "SINGLE"))
            elif any("2-speed" in f or "two-speed" in f or "two speed" in f for f in features_lower):
                rows.append(("Travel Speed (2-Speed)", "YES"))

        # Enforce per-section row cap
        limit = _ROW_LIMITS.get(section_name)
        if limit is not None:
            rows = rows[:limit]

        if rows:
            result.append((section_name, rows))

    # --- MACHINE CONDITION (from listing_data) ---
    cond_rows: list[tuple[str, str]] = []

    hours_raw = listing_data.get("hours")
    if hours_raw:
        cond_rows.append(("Hours", f"{int(hours_raw):,} HRS"))

    for cond_key, cond_label in [
        ("overall_condition", "Overall Condition"),
        ("condition", "Overall Condition"),
        ("track_condition", "Track Condition"),
        ("tire_condition", "Tire Condition"),
    ]:
        cond_val = listing_data.get(cond_key)
        if cond_val:
            # Deduplicate "Overall Condition" if both keys present
            if cond_label not in [r[0] for r in cond_rows]:
                cond_rows.append((cond_label, str(cond_val).upper()))

    price_raw = listing_data.get("price_value")
    if price_raw:
        price_str = f"${int(price_raw):,}"
        if listing_data.get("price_is_obo"):
            price_str += " OBO"
        cond_rows.append(("Asking Price", price_str))

    # Enforce MACHINE CONDITION row cap
    cond_rows = cond_rows[:_ROW_LIMITS["MACHINE CONDITION"]]

    if cond_rows:
        result.append(("MACHINE CONDITION", cond_rows))

    return result


# ── Header Rendering ──────────────────────────────────────────────────────────

def _draw_header(
    draw: ImageDraw.ImageDraw,
    canvas_w: int,
    header_h: int,
    year: str,
    make: str,
    model: str,
    subtitle: str,
) -> None:
    """
    Dark charcoal header bar.
    Title: [YEAR bold yellow] [MAKE bold white] [MODEL bold yellow]
    Subtitle: muted gray, smaller
    Small yellow accent line at bottom-left.
    """
    # Background
    draw.rectangle((0, 0, canvas_w, header_h), fill=C_HEADER)

    # --- Title: mixed-color inline text ---
    max_title_w = canvas_w - MARGIN * 2 - 40
    # Pick a size that fits
    title_size = 52
    while title_size >= 28:
        fy = _font(title_size, bold=True)
        fw = _font(title_size, bold=True)
        total_w = (
            (_text_w(draw, year, fy) + 14 if year else 0)
            + (_text_w(draw, make.upper(), fw) + 14 if make else 0)
            + (_text_w(draw, model.upper(), fy) if model else 0)
        )
        if total_w <= max_title_w:
            break
        title_size -= 2

    title_font_bold = _font(title_size, bold=True)
    subtitle_font = _font(16, bold=False)

    lh = _line_h(draw, title_font_bold)
    sub_lh = _line_h(draw, subtitle_font)
    total_block_h = lh + 6 + sub_lh
    title_y = (header_h - total_block_h) // 2
    sub_y = title_y + lh + 6

    x = MARGIN
    if year:
        draw.text((x, title_y), year, font=title_font_bold, fill=C_ACCENT)
        x += _text_w(draw, year, title_font_bold) + 14
    if make:
        draw.text((x, title_y), make.upper(), font=title_font_bold, fill=C_WHITE)
        x += _text_w(draw, make.upper(), title_font_bold) + 14
    if model:
        draw.text((x, title_y), model.upper(), font=title_font_bold, fill=C_ACCENT)

    # Subtitle
    draw.text((MARGIN, sub_y), subtitle.upper(), font=subtitle_font, fill="#8A95A0")

    # Yellow accent bar at header bottom-left
    draw.rectangle((0, header_h - 4, canvas_w, header_h), fill=C_ACCENT)


# ── Features Row ──────────────────────────────────────────────────────────────

def _draw_features_strip(
    draw: ImageDraw.ImageDraw,
    x0: int,
    x1: int,
    y: int,
    features: list[str],
) -> int:
    """Full-width bullet list below the two-column spec area."""
    if not features:
        return y

    head_font = _font(13, bold=True)
    _draw_tracked_text(draw, x0, y, "FEATURES & OPTIONS", head_font, C_MUTED, tracking=2)
    rule_y = y + _line_h(draw, head_font) + 4
    draw.line((x0, rule_y, x1, rule_y), fill=C_RULE, width=1)
    y = rule_y + 12

    item_font = _font(16, bold=False)
    col_w = (x1 - x0 - COL_GAP) // 2
    item_h = _line_h(draw, item_font) + 10
    rows = math.ceil(len(features) / 2)

    for idx, feature in enumerate(features):
        col = idx % 2
        row = idx // 2
        fx = x0 + col * (col_w + COL_GAP)
        fy = y + row * item_h
        draw.text((fx, fy), "•", font=_font(18, bold=True), fill=C_ACCENT)
        feat_lines = _wrap_text(draw, feature, item_font, col_w - 20, max_lines=2)
        for li, line in enumerate(feat_lines):
            draw.text((fx + 16, fy + li * (_line_h(draw, item_font) + 2)), line, font=item_font, fill=C_TEXT)

    return y + rows * item_h + 10


# ── Main Render ───────────────────────────────────────────────────────────────

def _render_spec_sheet_to_image(
    *,
    title: str = "",
    subtitle: str,
    year: str,
    make: str,
    model: str,
    grouped_sections: list[tuple[str, list[tuple[str, str]]]],
    features: list[str],
    fixed_height: int | None = None,
) -> Image.Image:
    """
    2×2 dealer-brochure grid spec sheet — returns PIL Image (not saved).

      | PERFORMANCE (0)   | DIMENSIONS (1)       |
      |-------------------+----------------------|  ← thin gray rule
      | CONFIGURATION (2) | MACHINE CONDITION (3)|

    Row heights are synchronized: both cells in a row share the same
    start-y and end-y, determined by whichever cell has more rows.
    Thin rules separate the columns and rows. No heavy boxes.
    """
    HEADER_H = 110
    FOOTER_H  = 46

    # ── Column geometry ───────────────────────────────────────────────────────
    col_w = (SHEET_W - MARGIN * 2 - COL_GAP) // 2

    # Cell content x-extents (with inner padding)
    lx0 = MARGIN + CELL_PAD_X
    lx1 = MARGIN + col_w - CELL_PAD_X
    rx0 = MARGIN + col_w + COL_GAP + CELL_PAD_X
    rx1 = SHEET_W - MARGIN - CELL_PAD_X

    # Vertical divider x (center of gap)
    vdiv_x = MARGIN + col_w + COL_GAP // 2

    # ── Assign sections to the 2×2 grid ──────────────────────────────────────
    # Expected order: PERFORMANCE(0), DIMENSIONS(1), CONFIGURATION(2), MACHINE CONDITION(3)
    grid: list[tuple[str, list] | None] = [None, None, None, None]
    for i, sec in enumerate(grouped_sections[:4]):
        grid[i] = sec

    def _cell_h(pos: int) -> int:
        """Content height for one grid cell (heading + rows + padding)."""
        sec = grid[pos]
        if sec is None:
            return 0
        _, rows = sec
        return CELL_PAD_TOP + HEAD_H + 8 + len(rows) * ROW_H + CELL_PAD_BOT

    # Synchronized row heights
    row1_h = max(_cell_h(0), _cell_h(1), 1)
    row2_h = max(_cell_h(2), _cell_h(3), 1)

    # ── Optional features strip ───────────────────────────────────────────────
    feat_rows = math.ceil(len(features) / 2) if features else 0
    feat_strip_h = (32 + feat_rows * 28 + 16) if features else 0

    # ── Canvas ────────────────────────────────────────────────────────────────
    canvas_h = HEADER_H + row1_h + GRID_ROW_GAP + row2_h + feat_strip_h + FOOTER_H
    if fixed_height is not None:
        canvas_h = fixed_height

    img = Image.new("RGB", (SHEET_W, canvas_h), C_BG)
    draw = ImageDraw.Draw(img)

    # ── Header bar ────────────────────────────────────────────────────────────
    _draw_header(draw, SHEET_W, HEADER_H, year, make, model, subtitle)

    # ── Grid y-anchors ────────────────────────────────────────────────────────
    row1_y = HEADER_H          # top of grid row 1
    row2_y = row1_y + row1_h + GRID_ROW_GAP   # top of grid row 2

    # ── Grid separator lines ──────────────────────────────────────────────────
    # Vertical (column divider)
    draw.line(
        (vdiv_x, HEADER_H, vdiv_x, row2_y + row2_h),
        fill=C_RULE, width=1,
    )
    # Horizontal (row divider)
    hdiv_y = row1_y + row1_h + GRID_ROW_GAP // 2
    draw.line(
        (MARGIN, hdiv_y, SHEET_W - MARGIN, hdiv_y),
        fill=C_RULE, width=1,
    )

    # ── Draw each grid cell ───────────────────────────────────────────────────
    def _draw_cell(pos: int, x0: int, x1: int, cell_top: int) -> None:
        sec = grid[pos]
        if sec is None:
            return
        section_name, rows = sec
        y = cell_top + CELL_PAD_TOP
        y = _draw_section_heading(draw, x0, x1, y, section_name)
        for label, value in rows:
            is_price = label.lower() == "asking price"
            _draw_spec_row(draw, x0, x1, y, label, value, price_row=is_price)
            y += ROW_H

    _draw_cell(0, lx0, lx1, row1_y)   # PERFORMANCE     — top-left
    _draw_cell(1, rx0, rx1, row1_y)   # DIMENSIONS      — top-right
    _draw_cell(2, lx0, lx1, row2_y)   # CONFIGURATION   — bottom-left
    _draw_cell(3, rx0, rx1, row2_y)   # MACHINE COND.   — bottom-right

    # ── Features strip (optional, below grid) ────────────────────────────────
    feat_y = row2_y + row2_h + 8
    if features:
        _draw_features_strip(draw, MARGIN, SHEET_W - MARGIN, feat_y, features)

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_y = canvas_h - FOOTER_H
    draw.line((MARGIN, footer_y, SHEET_W - MARGIN, footer_y), fill=C_RULE, width=1)
    footer_font = _font(15, bold=False)
    footer_text = "Generated by Machine to Market"
    footer_w = _text_w(draw, footer_text, footer_font)
    draw.text(
        (SHEET_W - MARGIN - footer_w, footer_y + 14),
        footer_text,
        font=footer_font,
        fill=C_FOOTER,
    )

    return img


def _render_spec_sheet(
    *,
    title: str,
    subtitle: str,
    year: str,
    make: str,
    model: str,
    grouped_sections: list[tuple[str, list[tuple[str, str]]]],
    features: list[str],
    output_path: str,
    fixed_height: int | None = None,
) -> str:
    """Save the spec sheet image to output_path and return the path."""
    img = _render_spec_sheet_to_image(
        title=title, subtitle=subtitle, year=year, make=make, model=model,
        grouped_sections=grouped_sections, features=features, fixed_height=fixed_height,
    )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    return output_path


# ── Brochure Panel 1 ─────────────────────────────────────────────────────────

# Brochure layout constants
BROCHURE_W   = 1200
P1_H         = 660     # height of marketing panel
P1_BG        = "#18191D"
P1_DARK_BG   = "#0D0F12"   # inner image dark fill

# Image frame (left side)
IF_X0 = 22
IF_Y0 = 22
IF_W  = 786             # frame outer width
IF_H  = 616             # frame outer height  →  y1 = 22+616 = 638
IF_BORDER = 2
II_X0 = IF_X0 + IF_BORDER   # = 24
II_Y0 = IF_Y0 + IF_BORDER   # = 24
II_W  = IF_W - IF_BORDER * 2   # = 782
II_H  = IF_H - IF_BORDER * 2   # = 612

OVERLAY_H  = 90    # bottom overlay bar height

# Right info rail
RAIL_X0  = IF_X0 + IF_W + 22   # = 830
RAIL_X1  = BROCHURE_W - 20     # = 1180
RAIL_W   = RAIL_X1 - RAIL_X0   # = 350
RAIL_CX  = RAIL_X0 + 10        # content left edge = 840
RAIL_CX2 = RAIL_X1 - 4         # content right edge = 1176


def _load_fit_image(
    img_path: str,
    target_w: int,
    target_h: int,
    bg: str = P1_DARK_BG,
    pad_pct: float = 0.06,
) -> Image.Image:
    """
    Load image, contain-fit to target_w × target_h with inner padding.
    pad_pct=0.06 reserves 6% on each side so the full machine is always visible.
    """
    canvas = Image.new("RGB", (target_w, target_h), bg)
    try:
        src = Image.open(img_path).convert("RGB")
        sw, sh = src.size
        # Available area after padding
        avail_w = int(target_w * (1 - 2 * pad_pct))
        avail_h = int(target_h * (1 - 2 * pad_pct))
        scale = min(avail_w / sw, avail_h / sh)
        nw, nh = int(sw * scale), int(sh * scale)
        resized = src.resize((nw, nh), Image.LANCZOS)
        # Center within target
        paste_x = (target_w - nw) // 2
        paste_y = (target_h - nh) // 2
        canvas.paste(resized, (paste_x, paste_y))
    except Exception:
        pass
    return canvas


def _draw_callout_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, icon_type: str) -> None:
    """Thin-line callout icon for Panel 1 highlights."""
    c = C_ACCENT
    w = 2
    if icon_type == "gear":
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=w)
        ri = max(r // 2, 5)
        draw.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), outline=c, width=w)
        t = max(r // 4 + 1, 4)
        for ddx, ddy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            bx = cx + ddx * (r + t // 2)
            by = cy + ddy * (r + t // 2)
            draw.ellipse((bx - t, by - t, bx + t, by + t), fill=c)
    elif icon_type == "weight":
        # Dumbbell: center bar + end plates
        draw.line((cx - r, cy, cx + r, cy), fill=c, width=w)
        pw = max(r // 3, 4)
        ph = max(r // 2 + 2, 6)
        for sx in [-1, 1]:
            ex = cx + sx * r
            draw.rectangle((ex - pw // 2, cy - ph, ex + pw // 2, cy + ph), outline=c, width=w)
    else:  # "flow" / water drop
        # Teardrop: oval base + V-tip at top
        rc = max(r * 2 // 3, 6)
        draw.ellipse((cx - rc, cy - rc // 2, cx + rc, cy + rc + rc // 2), outline=c, width=w)
        draw.line((cx - rc, cy - rc // 4, cx, cy - r), fill=c, width=w)
        draw.line((cx + rc, cy - rc // 4, cx, cy - r), fill=c, width=w)


def _build_highlights(
    resolved_specs: dict,
    ui_hints: dict,
    equipment_type: str = "",
) -> list[tuple[str, str, str]]:
    """Return up to 3 (icon_type, bold_label, sub_text) for Panel 1 callouts."""
    hi_flow_active = ui_hints.get("_displayHiFlow", False)
    highlights: list[tuple[str, str, str]] = []

    hp = resolved_specs.get("net_hp")
    if hp:
        highlights.append(("gear", "POWERFUL", f"{_fmt_val(hp, '')} HP Engine"))

    roc  = resolved_specs.get("roc_lb")
    tip  = resolved_specs.get("tipping_load_lb")
    cap  = resolved_specs.get("max_lift_capacity_lb") or resolved_specs.get("rated_lift_capacity_lb")
    if roc:
        highlights.append(("weight", "STRONG LIFT", f"{_fmt_val(roc, '')} lb Rated Capacity"))
    elif tip:
        highlights.append(("weight", "STRONG LIFT", f"{_fmt_val(tip, '')} lb Tipping Load"))
    elif cap:
        highlights.append(("weight", "RATED LIFT", f"{_fmt_val(cap, '')} lb Lift Capacity"))

    flow    = resolved_specs.get("hydraulic_flow_gpm")
    hi_flow = resolved_specs.get("hi_flow_gpm")
    max_h   = resolved_specs.get("max_lift_height_in") or resolved_specs.get("max_fork_height_in")
    if flow:
        if hi_flow and hi_flow_active:
            highlights.append(("flow", "HIGH FLOW", f"{_fmt_val(hi_flow, '')} GPM High Flow"))
        else:
            highlights.append(("flow", "HIGH FLOW", f"{_fmt_val(flow, '')} GPM Aux Hydraulics"))
    elif max_h:
        highlights.append(("flow", "REACH HIGH", f"{_fmt_val(max_h, '')} in Max Height"))

    return highlights[:3]


def _render_panel1(
    *,
    year: str,
    make: str,
    model: str,
    subtitle: str,
    highlights: list[tuple[str, str, str]],
    machine_image_path: str | None,
    dealer_logo_path: str | None,
    dealer_info: dict,
    format_label: str = "FACEBOOK POST\nOPTIMIZED\n1200 x 1500",
) -> Image.Image:
    """Render the top marketing panel (machine photo + dark info rail)."""
    img = Image.new("RGB", (BROCHURE_W, P1_H), P1_BG)
    draw = ImageDraw.Draw(img)

    # ── Machine image area ────────────────────────────────────────────────────
    img.paste(Image.new("RGB", (II_W, II_H), P1_DARK_BG), (II_X0, II_Y0))

    if machine_image_path and os.path.isfile(machine_image_path):
        # Image fills full inner area (overlay covers bottom portion)
        fit = _load_fit_image(machine_image_path, II_W, II_H, bg=P1_DARK_BG)
        img.paste(fit, (II_X0, II_Y0))

    # Yellow frame border
    draw.rectangle(
        (IF_X0, IF_Y0, IF_X0 + IF_W - 1, IF_Y0 + IF_H - 1),
        outline=C_ACCENT, width=IF_BORDER,
    )

    # ── Bottom overlay bar ────────────────────────────────────────────────────
    ov_y0 = II_Y0 + II_H - OVERLAY_H
    ov_y1 = II_Y0 + II_H
    draw.rectangle((II_X0, ov_y0, II_X0 + II_W - 1, ov_y1 - 1), fill=P1_BG)

    # Left badge: format label
    badge_font_b = _font(10, bold=True)
    badge_font   = _font(10, bold=False)
    by = ov_y0 + 10
    for line in format_label.split("\n"):
        is_last = (line == format_label.split("\n")[-1])
        f = badge_font if is_last else badge_font_b
        draw.text((II_X0 + 12, by), line, font=f, fill=C_WHITE if not is_last else C_MUTED)
        by += _line_h(draw, f) + 3

    # Logo box: white rect ~185×64
    logo_box_x = II_X0 + 140
    logo_box_y = ov_y0 + 10
    logo_box_w = 188
    logo_box_h = OVERLAY_H - 18
    draw.rectangle(
        (logo_box_x, logo_box_y, logo_box_x + logo_box_w, logo_box_y + logo_box_h),
        fill=C_WHITE,
    )
    if dealer_logo_path and os.path.isfile(dealer_logo_path):
        try:
            logo_src = Image.open(dealer_logo_path).convert("RGBA")
            pad = 6
            lw, lh = logo_box_w - pad * 2, logo_box_h - pad * 2
            scale = min(lw / logo_src.width, lh / logo_src.height)
            ls = logo_src.resize(
                (int(logo_src.width * scale), int(logo_src.height * scale)), Image.LANCZOS
            )
            lx = logo_box_x + pad + (lw - ls.width) // 2
            ly = logo_box_y + pad + (lh - ls.height) // 2
            # Convert RGBA to RGB for paste onto RGB canvas using alpha
            bg_patch = img.crop((lx, ly, lx + ls.width, ly + ls.height))
            bg_patch.paste(ls, (0, 0), ls.split()[3] if ls.mode == "RGBA" else None)
            img.paste(bg_patch, (lx, ly))
        except Exception:
            pass
    else:
        # Fallback: "MACHINE TO MARKET" text
        mtm_font = _font(11, bold=True)
        mtm_lines = ["MACHINE", "TO MARKET"]
        ty = logo_box_y + (logo_box_h - len(mtm_lines) * (_line_h(draw, mtm_font) + 2)) // 2
        for ml in mtm_lines:
            mw = _text_w(draw, ml, mtm_font)
            draw.text((logo_box_x + (logo_box_w - mw) // 2, ty), ml, font=mtm_font, fill="#1C2228")
            ty += _line_h(draw, mtm_font) + 2

    # Contact info (right of logo box)
    contact_x = logo_box_x + logo_box_w + 14
    contact_y = ov_y0 + 16
    dealer_name = dealer_info.get("dealer_name") or dealer_info.get("contact_name") or ""
    dealer_phone = dealer_info.get("phone") or dealer_info.get("contact_phone") or ""
    if dealer_name:
        name_font = _font(13, bold=True)
        draw.text((contact_x, contact_y), dealer_name, font=name_font, fill=C_WHITE)
        contact_y += _line_h(draw, name_font) + 5
    if dealer_phone:
        ph_font = _font(12, bold=False)
        draw.text((contact_x, contact_y), dealer_phone, font=ph_font, fill=C_MUTED)

    # ── Right info rail ───────────────────────────────────────────────────────
    ry = 28  # current y position in rail

    # "BEST OPTION" label + "LISTING" pill
    bo_font = _font(11, bold=True)
    _draw_tracked_text(draw, RAIL_CX, ry, "BEST OPTION", bo_font, C_ACCENT, tracking=3)
    pill_label = "  LISTING  "
    pill_font  = _font(11, bold=True)
    pill_w     = _text_w(draw, pill_label, pill_font) + 4
    pill_h     = 22
    pill_x     = RAIL_CX2 - pill_w
    draw.rounded_rectangle(
        (pill_x, ry - 2, pill_x + pill_w, ry - 2 + pill_h),
        radius=10, outline=C_ACCENT, width=2,
    )
    pw = _text_w(draw, "LISTING", pill_font)
    draw.text((pill_x + (pill_w - pw) // 2, ry + 2), "LISTING", font=pill_font, fill=C_ACCENT)
    ry += 28

    # Yellow separator
    draw.line((RAIL_CX, ry, RAIL_CX2, ry), fill=C_ACCENT, width=1)
    ry += 18

    # Year / Make / Model (stacked, large)
    # Hierarchy: Model is hero (largest, gold), Make is strong (white bold), Year is small accent
    year_font  = _font(32, bold=False)
    make_font  = _fit_font(draw, make.upper() or "MAKE",  52, RAIL_W - 10, min_size=26, bold=True)
    model_font = _fit_font(draw, model.upper() or "MODEL", 64, RAIL_W - 10, min_size=30, bold=True)

    if year:
        draw.text((RAIL_CX, ry), year, font=year_font, fill=C_WHITE)
        ry += _line_h(draw, year_font) + 10
    if make:
        draw.text((RAIL_CX, ry), make.upper(), font=make_font, fill=C_WHITE)
        ry += _line_h(draw, make_font) + 8
    if model:
        draw.text((RAIL_CX, ry), model.upper(), font=model_font, fill=C_ACCENT)
        ry += _line_h(draw, model_font) + 16

    # Equipment type subtitle
    type_font = _font(13, bold=False)
    draw.text((RAIL_CX, ry), subtitle.upper(), font=type_font, fill="#8A95A0")
    ry += _line_h(draw, type_font) + 30

    # Second yellow separator
    draw.line((RAIL_CX, ry, RAIL_CX2, ry), fill=C_ACCENT, width=1)
    ry += 28

    # Highlight callouts — evenly distributed in remaining rail height
    remaining = P1_H - ry - 24
    callout_spacing = max(remaining // max(len(highlights), 1), 88)
    icon_r = 17
    lbl_font = _font(15, bold=True)
    sub_font = _font(13, bold=False)

    for icon_type, label, subtext in highlights:
        icon_cx = RAIL_CX + icon_r
        icon_cy = ry + icon_r
        _draw_callout_icon(draw, icon_cx, icon_cy, icon_r, icon_type)
        text_x = RAIL_CX + icon_r * 2 + 8
        draw.text((text_x, ry + 2), label, font=lbl_font, fill=C_WHITE)
        draw.text((text_x, ry + _line_h(draw, lbl_font) + 4), subtext, font=sub_font, fill=C_MUTED)
        ry += callout_spacing

    return img


# ── Public API ────────────────────────────────────────────────────────────────

def _resolve_machine_type(payload: dict) -> str:
    for key in ("equipment_type", "machine_type", "type_label", "category_label", "category", "type"):
        value = payload.get(key)
        if value:
            return str(value)
    return "Machine Specifications"


def _normalize_model(model: str) -> str:
    return str(model or "").strip().upper()


def generate_spec_sheet_image(
    listing_data: dict,
    resolved_specs: dict,
    ui_hints: dict | None = None,
    output_path: str | None = None,
) -> str:
    if ui_hints is None:
        ui_hints = {}
    if resolved_specs is None:
        resolved_specs = {}

    if output_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(here, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "spec_sheet.png")

    year  = str(listing_data.get("year") or "")
    make  = str(listing_data.get("make") or "")
    model = _normalize_model(str(listing_data.get("model") or ""))
    features = [str(item) for item in (listing_data.get("features") or []) if item]
    subtitle = _resolve_machine_type(listing_data)
    title = " ".join(p for p in [year, make.upper() if make else "", model] if p) or "Heavy Equipment"

    grouped_sections = _build_grouped_rows(resolved_specs, ui_hints, listing_data)

    return _render_spec_sheet(
        title=title,
        subtitle=subtitle,
        year=year,
        make=make,
        model=model,
        grouped_sections=grouped_sections,
        features=features,
        output_path=output_path,
        fixed_height=None,
    )


def generate_brochure_image(
    listing_data: dict,
    resolved_specs: dict,
    ui_hints: dict | None = None,
    machine_image_path: str | None = None,
    dealer_logo_path: str | None = None,
    dealer_info: dict | None = None,
    output_path: str | None = None,
) -> str:
    """
    Two-panel dealer brochure PNG (target 1200×1500):
      Panel 1  — dark marketing card: machine photo + info rail
      Panel 2  — spec grid: dark header + 2×2 brochure layout

    Parameters
    ----------
    listing_data       : year, make, model, hours, condition, price, features, etc.
    resolved_specs     : OEM spec fields (net_hp, roc_lb, hydraulic_flow_gpm, …)
    ui_hints           : rendering flags e.g. {"_displayHiFlow": true}
    machine_image_path : optional path to primary machine photo
    dealer_logo_path   : optional path to dealer logo (PNG/JPG)
    dealer_info        : dict with dealer_name, phone keys
    output_path        : PNG output path (auto-generated if None)
    """
    if ui_hints is None:
        ui_hints = {}
    if resolved_specs is None:
        resolved_specs = {}
    if dealer_info is None:
        dealer_info = {}

    if output_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(here, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "brochure.png")

    year     = str(listing_data.get("year") or "")
    make     = str(listing_data.get("make") or "")
    model    = _normalize_model(str(listing_data.get("model") or ""))
    subtitle = _resolve_machine_type(listing_data)
    title    = " ".join(p for p in [year, make.upper() if make else "", model] if p) or "Heavy Equipment"

    grouped_sections = _build_grouped_rows(resolved_specs, ui_hints, listing_data)
    highlights       = _build_highlights(resolved_specs, ui_hints, subtitle)

    # Panel 1: marketing card
    p1 = _render_panel1(
        year=year, make=make, model=model, subtitle=subtitle,
        highlights=highlights,
        machine_image_path=machine_image_path,
        dealer_logo_path=dealer_logo_path,
        dealer_info=dealer_info,
    )

    # Panel 2: spec grid — auto-height (no fixed constraint, let content breathe)
    p2 = _render_spec_sheet_to_image(
        title=title, subtitle=subtitle, year=year, make=make, model=model,
        grouped_sections=grouped_sections,
        features=[],   # no features strip in brochure mode — keeps it clean
        fixed_height=None,
    )

    # Thin accent bar between panels (visual connector, not a gap)
    SEP_H = 6
    total_h = p1.height + SEP_H + p2.height
    canvas = Image.new("RGB", (BROCHURE_W, total_h), C_BG)
    canvas.paste(p1, (0, 0))
    # Separator: solid charcoal bar
    from PIL import ImageDraw as _ID
    _sep_draw = _ID.Draw(canvas)
    _sep_draw.rectangle((0, p1.height, BROCHURE_W, p1.height + SEP_H), fill=C_HEADER)
    canvas.paste(p2, (0, p1.height + SEP_H))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    canvas.save(output_path, "PNG", optimize=True)
    return output_path


_VARIANT_SIZES: dict[str, tuple[int, int]] = {
    "4x5":       (1200, 1500),
    "square":    (1200, 1200),
    "story":     (1080, 1920),
    "landscape": (1200, 630),
}


def _make_variant(src: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = src.size
    src_ratio = src_w / src_h
    tgt_ratio = target_w / target_h

    if tgt_ratio >= src_ratio:
        scale = target_w / src_w
        new_h = round(src_h * scale)
        scaled = src.resize((target_w, new_h), Image.LANCZOS)
        if new_h >= target_h:
            return scaled.crop((0, 0, target_w, target_h))
        canvas = Image.new("RGB", (target_w, target_h), C_BG)
        canvas.paste(scaled, (0, 0))
        return canvas

    scale = target_w / src_w
    new_h = round(src_h * scale)
    scaled = src.resize((target_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), C_BG)
    y_off = (target_h - new_h) // 2
    canvas.paste(scaled, (0, y_off))
    return canvas


def generate_spec_sheet_variants(spec_sheet_path: str) -> dict[str, str]:
    src = Image.open(spec_sheet_path)
    out_dir = os.path.dirname(os.path.abspath(spec_sheet_path))
    results: dict[str, str] = {}
    for key, (target_w, target_h) in _VARIANT_SIZES.items():
        variant = _make_variant(src, target_w, target_h)
        out_path = os.path.join(out_dir, f"spec_sheet_{key}.png")
        variant.save(out_path, "PNG", optimize=True)
        results[key] = out_path
    return results


def generate_spec_sheet(
    make: str,
    model: str,
    year: str | int | None = None,
    equipment_type: str | None = None,
    spec_sheet: list[tuple[str, str]] | None = None,
    dealer_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    location: str | None = None,
    output_path: str | None = None,
    use_case_payload: dict | None = None,
) -> str:
    del dealer_name, phone, email, location, use_case_payload

    if output_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        slug = f"{make}_{model}".replace(" ", "_").lower()
        out_dir = os.path.join(here, "outputs", "spec_sheets")
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, f"spec_sheet_{slug}.png")

    normalized_model = _normalize_model(model)
    year_str = str(year) if year else ""
    subtitle = equipment_type or "Machine Specifications"

    # Convert legacy flat spec_sheet list → PERFORMANCE group
    grouped: list[tuple[str, list[tuple[str, str]]]] = []
    if spec_sheet:
        grouped.append(("PERFORMANCE", list(spec_sheet)))

    return _render_spec_sheet(
        title=" ".join(p for p in [year_str, make.upper() if make else "", normalized_model] if p) or "Heavy Equipment",
        subtitle=subtitle,
        year=year_str,
        make=make,
        model=normalized_model,
        grouped_sections=grouped,
        features=[],
        output_path=output_path,
        fixed_height=None,
    )


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _listing = {
        "year": 2021,
        "make": "Bobcat",
        "model": "T770",
        "equipment_type": "Compact Track Loader",
        "hours": 200,
        "price_value": 48500,
        "price_is_obo": False,
        "overall_condition": "Excellent",
        "features": ["High Flow Hydraulics", "Enclosed Cab", "Heat", "2-Speed Drive", "Ride Control"],
    }
    _specs = {
        "net_hp": 92,
        "roc_lb": 3475,
        "tipping_load_lb": 6950,
        "operating_weight_lb": 8900,
        "hydraulic_flow_gpm": 23.0,
        "hi_flow_gpm": 37.0,
        "hydraulic_pressure_standard_psi": 3600,
        "travel_speed_high_mph": 7.3,
        "travel_speed_low_mph": 5.5,
        "fuel_type": "Diesel",
        "frame_size": "Large",
        "width_in": 78,
        "hinge_pin_height_in": 132,
        "length_in": 132,
        "lift_type": "Vertical",
    }
    _hints = {"_displayHiFlow": False}

    out = generate_spec_sheet_image(_listing, _specs, _hints)
    print(f"Spec sheet written: {out}")
    variants = generate_spec_sheet_variants(out)
    for key, path in variants.items():
        print(f"  variant [{key}]: {path}")
