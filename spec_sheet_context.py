"""spec_sheet_context.py
======================
Shared spec sheet context builder and Playwright screenshot helper.

Used by both app.py (browser route) and listing_pack_builder.py (export PNG)
so the exported spec sheet is pixel-identical to the in-app view.
"""

from __future__ import annotations
import base64
import datetime
import os
import sys
from pathlib import Path

from spec_sheet_config import (
    CONDITION_CONTEXT,
    format_feet_inches,
    photo_data_uri,
    find_first_photo,
)

# ─── Display mappings ─────────────────────────────────────────────────────────

_EQ_TYPE_DISPLAY = {
    "compact_track_loader": "Compact Track Loader",
    "skid_steer":           "Skid Steer Loader",
    "mini_excavator":       "Mini Excavator",
    "backhoe_loader":       "Backhoe Loader",
    "large_excavator":      "Large Excavator",
    "telehandler":          "Telehandler",
}

_LIFT_PATH_DISPLAY = {
    "vertical": "Vertical",
    "radial":   "Radial",
    "high":     "Vertical",
    "locked":   "Vertical",
}

_CONTROL_DISPLAY = {
    "joystick":  "Joystick",
    "hand_foot": "Hand/Foot",
    "pilot":     "Pilot",
    "iso":       "ISO",
    "h":         "H-Pattern",
}

TAIL_SWING_CONTEXT: dict[str, str] = {
    "zero":         "Zero Tail",
    "reduced":      "Reduced Swing",
    "conventional": "Conv Swing",
}

# ─── Hero spec tables ─────────────────────────────────────────────────────────
# Each tile_def:
#   field    : primary registry output field name
#   aliases  : fallback field names tried in order after primary
#   label    : display label in tile
#   unit     : display unit string or None
#   fmt      : "int" | "dec1" | "feet_inches" | "lift_path"
#   req_conf : "HIGH" | "MEDIUM" | "NONE"  (confidence gate)
#   sublabel : optional registry field name — resolved dynamically as a sublabel string

HERO_SPECS: dict[str, list[dict]] = {
    "compact_track_loader": [
        {
            "field": "rated_operating_capacity_lbs", "aliases": ["tipping_load_lbs", "roc_lb"],
            "label": "ROC", "unit": "LB", "fmt": "int", "req_conf": "HIGH",
        },
        {
            "field": "horsepower_hp", "aliases": ["net_horsepower_hp", "net_hp"],
            "label": "Net Power", "unit": "HP", "fmt": "int", "req_conf": "HIGH",
        },
        {
            # aux_flow is selected dynamically in build_hero_tiles based on high_flow flag
            "field": "aux_flow_standard_gpm", "aliases": ["hydraulic_flow_gpm"],
            "label": "Aux Flow", "unit": "GPM", "fmt": "dec1", "req_conf": "MEDIUM",
        },
        {
            "field": "ground_pressure_psi", "aliases": [],
            "label": "Ground Pressure", "unit": "PSI", "fmt": "dec1", "req_conf": "MEDIUM",
            "sublabel": "track_width_in",
        },
    ],
    "skid_steer": [
        {
            "field": "rated_operating_capacity_lbs", "aliases": ["tipping_load_lbs"],
            "label": "ROC", "unit": "LB", "fmt": "int", "req_conf": "HIGH",
        },
        {
            "field": "lift_path", "aliases": [],
            "label": "Lift Path", "unit": None, "fmt": "lift_path", "req_conf": "MEDIUM",
        },
        {
            "field": "horsepower_hp", "aliases": ["net_horsepower_hp"],
            "label": "HP", "unit": "HP", "fmt": "int", "req_conf": "HIGH",
        },
        {
            # aux_flow is selected dynamically in build_hero_tiles based on high_flow flag
            "field": "aux_flow_standard_gpm", "aliases": [],
            "label": "Aux Flow", "unit": "GPM", "fmt": "dec1", "req_conf": "MEDIUM",
        },
    ],
    "mini_excavator": [
        {
            "field": "operating_weight_lbs", "aliases": ["operating_weight_lb"],
            "label": "Weight", "unit": "LB", "fmt": "int", "req_conf": "HIGH",
            "sublabel": "tail_swing_type",
        },
        {
            "field": "max_dig_depth_ft", "aliases": ["max_dig_depth"],
            "label": "Dig Depth", "unit": None, "fmt": "feet_inches", "req_conf": "HIGH",
        },
        {
            "field": "max_dump_height_ft", "aliases": [],
            "label": "Dump Ht", "unit": None, "fmt": "feet_inches", "req_conf": "MEDIUM",
        },
        {
            "field": "hydraulic_flow_gpm", "aliases": [],
            "label": "Aux Flow", "unit": "GPM", "fmt": "dec1", "req_conf": "MEDIUM",
        },
    ],
    "telehandler": [
        {
            "field": "lift_capacity_lbs", "aliases": ["lift_capacity_at_full_height_lbs", "lift_capacity_lb"],
            "label": "Lift Cap", "unit": "LB", "fmt": "int", "req_conf": "HIGH",
        },
        {
            "field": "lift_height_ft", "aliases": ["max_lift_height_ft"],
            "label": "Lift Ht", "unit": None, "fmt": "feet_inches", "req_conf": "NONE",
        },
        {
            "field": "forward_reach_ft", "aliases": ["max_forward_reach_ft"],
            "label": "Fwd Reach", "unit": None, "fmt": "feet_inches", "req_conf": "NONE",
        },
        {
            "field": "horsepower_hp", "aliases": ["net_hp"],
            "label": "HP", "unit": "HP", "fmt": "int", "req_conf": "HIGH",
        },
    ],
}

# ─── Feature groups ───────────────────────────────────────────────────────────

FEATURE_GROUPS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "compact_track_loader": {
        "Cab & Comfort": [
            ("enclosed_cab", "Enclosed Cab"),
            ("ac",           "A/C + Heat"),
            ("heat_only",    "Heat"),
        ],
        "Hydraulics & Drive": [
            ("high_flow", "High Flow"),
            ("two_speed", "2-Speed"),
        ],
        "Utility": [
            ("ride_control",     "Ride Control"),
            ("hyd_quick_attach", "Hyd Quick Attach"),
            ("backup_camera",    "Backup Camera"),
        ],
    },
    "skid_steer": {
        "Cab & Comfort": [
            ("enclosed_cab", "Enclosed Cab"),
            ("ac",           "A/C + Heat"),
            ("heat_only",    "Heat"),
        ],
        "Hydraulics & Drive": [
            ("high_flow", "High Flow"),
            ("two_speed", "2-Speed"),
        ],
        "Utility": [
            ("ride_control",     "Ride Control"),
            ("hyd_quick_attach", "Hyd Quick Attach"),
            ("backup_camera",    "Backup Camera"),
        ],
    },
    "mini_excavator": {
        "Cab & Comfort": [
            ("enclosed_cab", "Enclosed Cab"),
            ("ac",           "A/C + Heat"),
            ("heat_only",    "Heat"),
        ],
        "Attachments": [
            ("hyd_quick_attach", "Hyd Quick Attach"),
            ("hammer_plumbing",  "Hammer Plumbing"),
            ("thumb",            "Thumb"),
        ],
        "Utility": [
            ("backup_camera", "Backup Camera"),
            ("grade_control", "Grade Control"),
        ],
    },
    "telehandler": {
        "Cab & Comfort": [
            ("enclosed_cab", "Enclosed Cab"),
            ("ac",           "A/C + Heat"),
            ("heat_only",    "Heat"),
        ],
        "Utility": [
            ("backup_camera", "Backup Camera"),
        ],
    },
    "backhoe_loader": {
        "Cab & Comfort": [
            ("enclosed_cab", "Enclosed Cab"),
            ("ac",           "A/C + Heat"),
            ("heat_only",    "Heat"),
        ],
        "Utility": [
            ("hyd_quick_attach", "Hyd Quick Attach"),
            ("backup_camera",    "Backup Camera"),
        ],
    },
    "large_excavator": {
        "Cab & Comfort": [
            ("enclosed_cab", "Enclosed Cab"),
            ("ac",           "A/C + Heat"),
            ("heat_only",    "Heat"),
        ],
        "Attachments": [
            ("hyd_quick_attach", "Hyd Quick Attach"),
            ("hammer_plumbing",  "Hammer Plumbing"),
            ("thumb",            "Thumb"),
        ],
        "Utility": [
            ("backup_camera", "Backup Camera"),
            ("grade_control", "Grade Control"),
        ],
    },
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fmt_number(value: object) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and value.is_integer():
            return f"{int(value):,}"
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def hours_context(current_year: int, machine_year: int, hours: int | float) -> str:
    """Return a usage-intensity label based on hours per year of age."""
    age = max(1, current_year - int(machine_year))
    hpy = float(hours) / age
    if hpy < 350:
        return "Low for year"
    if hpy <= 700:
        return "Normal use"
    return "Heavy use"


def _passes_confidence(conf: str | None, req: str) -> bool:
    """Return True if field confidence meets the required threshold."""
    if req == "NONE":
        return True
    if conf is None:
        return True  # no field_confidence entry → pass through
    c = str(conf).upper()
    if c == "LOW":
        return False
    if req == "HIGH" and c == "MEDIUM":
        return False
    return True


def _render_tile_value(value: object, fmt: str) -> str:
    if fmt == "int":
        return _fmt_number(value)
    if fmt == "dec1":
        v = float(value)
        return str(int(v)) if v == int(v) else str(round(v, 1))
    if fmt == "feet_inches":
        try:
            result = format_feet_inches(float(value))
            return result if result is not None else str(value)
        except (TypeError, ValueError):
            # pre-v2 sessions stored dig/dump depth as "X ft Y in" strings
            import re
            m = re.match(r"(\d+)\s*ft\s*(\d+)\s*in", str(value).strip())
            if m:
                ft, inch = int(m.group(1)), int(m.group(2))
                return f"{ft}'" if inch == 0 else f"{ft}' {inch}\""
            print(f"[spec_sheet] feet_inches unhandled value: {value!r}", file=sys.stderr)
            return str(value)
    if fmt == "lift_path":
        return _LIFT_PATH_DISPLAY.get(str(value).lower(), str(value).title())
    return str(value)


def _normalize_features(di: dict) -> dict[str, bool]:
    """Map DealerInput model_dump fields to normalized boolean keys for FEATURE_GROUPS."""
    has_ac = bool(di.get("ac"))
    return {
        "high_flow":        di.get("high_flow") == "yes",
        "two_speed":        di.get("two_speed_travel") == "yes",
        "enclosed_cab":     di.get("cab_type") == "enclosed",
        "ac":               has_ac,
        "heat_only":        bool(di.get("heater")) and not has_ac,
        "ride_control":     bool(di.get("ride_control")),
        "hyd_quick_attach": di.get("coupler_type") == "hydraulic",
        "backup_camera":    bool(di.get("backup_camera") or di.get("rear_camera")),
        "hammer_plumbing":  bool(di.get("hammer_plumbing")),
        "thumb":            di.get("thumb_type") not in (None, "none", ""),
        "grade_control":    di.get("grade_control_type") not in (None, "none", ""),
    }


def _logo_is_light(logo_path: str) -> bool:
    """Corner-sample 8×8px from each corner; light if avg brightness > 200."""
    try:
        from PIL import Image as _PILImage
        img = _PILImage.open(logo_path).convert("RGBA")
        w, h = img.size
        size = 8
        corners = [
            (0, 0),
            (max(0, w - size), 0),
            (0, max(0, h - size)),
            (max(0, w - size), max(0, h - size)),
        ]
        total, count = 0, 0
        for cx, cy in corners:
            patch = img.crop((cx, cy, min(w, cx + size), min(h, cy + size)))
            for r, g, b, a in patch.getdata():
                if a > 10:
                    total += (r + g + b) / 3
                    count += 1
        return count > 0 and (total / count) > 200
    except Exception:
        return False


# ─── Hero tile builder ────────────────────────────────────────────────────────

def build_hero_tiles(
    equipment_type: str,
    specs: dict,
    field_confidence: dict,
) -> list[dict]:
    """
    Build up to 4 hero tiles for the spec sheet headline strip.

    Tiles are selected from HERO_SPECS[equipment_type] in order.  Each tile
    is dropped if its resolved value is None or its confidence gate fails.
    Dynamic sublabels (track_width_in, tail_swing_type) are resolved from specs.

    Aux flow special case: when the tile field is aux_flow_standard_gpm and
    specs["high_flow"] == "yes", selects aux_flow_high_gpm instead, with the
    sublabel adjusted to "high flow" vs "standard".
    """
    tiles = []
    for td in HERO_SPECS.get(equipment_type, []):
        sublabel_override: str | None = None

        # ── Aux flow dynamic selection ────────────────────────────────────────
        if td["field"] == "aux_flow_standard_gpm":
            high_flow_active = (specs.get("high_flow") == "yes")
            if high_flow_active and specs.get("aux_flow_high_gpm") is not None:
                val  = specs.get("aux_flow_high_gpm")
                conf = field_confidence.get("aux_flow_high_gpm")
                sublabel_override = "high flow"
            else:
                val  = specs.get("aux_flow_standard_gpm")
                if val is None:
                    # try alias
                    val = specs.get("hydraulic_flow_gpm")
                    conf = field_confidence.get("hydraulic_flow_gpm")
                else:
                    conf = field_confidence.get("aux_flow_standard_gpm")
                sublabel_override = "standard" if val is not None else None

        else:
            # ── Normal field resolution: primary field then aliases ───────────
            val = None
            conf = None
            for name in [td["field"]] + td.get("aliases", []):
                v = specs.get(name)
                if v is not None:
                    val = v
                    conf = field_confidence.get(name)
                    break

        if val is None:
            continue
        if not _passes_confidence(conf, td.get("req_conf", "MEDIUM")):
            continue

        display_val = _render_tile_value(val, td["fmt"])
        unit = td.get("unit") or ""

        # ── Sublabel resolution ───────────────────────────────────────────────
        sublabel: str | None = sublabel_override
        if sublabel is None:
            sl_field = td.get("sublabel")
            if sl_field:
                sl_raw = specs.get(sl_field)
                if sl_raw is not None:
                    if sl_field == "track_width_in":
                        v_in = float(sl_raw)
                        sub_num = str(int(v_in)) if v_in == int(v_in) else str(round(v_in, 1))
                        sublabel = f'{sub_num}" tracks'
                    elif sl_field == "tail_swing_type":
                        sublabel = TAIL_SWING_CONTEXT.get(str(sl_raw).lower())

        tiles.append({
            "label":    td["label"],
            "value":    display_val,
            "unit":     unit,
            "sublabel": sublabel,
        })

    return tiles[:4]


# ─── Feature group builder ────────────────────────────────────────────────────

def build_feature_groups(
    equipment_type: str,
    features: dict[str, bool],
) -> dict[str, list[str]]:
    """
    Return {group_name: [label, ...]} for features that are present (True).

    "No negatives" rule: groups with zero present features are omitted entirely.
    """
    groups: dict[str, list[str]] = {}
    for group_name, items in FEATURE_GROUPS.get(equipment_type, {}).items():
        present = [label for (field, label) in items if features.get(field) is True]
        if present:
            groups[group_name] = present
    return groups


# ─── Context builder ──────────────────────────────────────────────────────────

def build_spec_sheet_context(
    dealer_input_data: dict,
    resolved_specs: dict,
    ui_hints: dict,
    equipment_type: str,
    dealer_contact: dict,
    session_id: str,
    outputs_dir: str = "",
    logo_as_data_uri: bool = False,
    field_confidence: dict | None = None,
    image_input_paths: list[str] | None = None,
) -> dict:
    """
    Assemble the full Jinja2 context dict for spec_sheet.html.

    Parameters
    ----------
    logo_as_data_uri
        When True the dealer logo is embedded as a base64 data URI.
        Use this for offline Playwright export so no live server is required.
    outputs_dir
        Absolute path to the outputs/ directory (needed for logo path lookup
        and auto-discovery of session _uploads/ when image_input_paths is None).
    field_confidence
        Per-field confidence dict from the registry record.
    image_input_paths
        Ordered list of absolute photo paths.  The first valid image is embedded
        as a base64 data URI.  When None, no machine photo is shown.
    """
    di = dealer_input_data
    rs = resolved_specs
    fc = field_confidence or {}

    year  = di.get("year")
    make  = (di.get("make") or "").strip()
    model = (di.get("model") or "").strip()

    eq_display = _EQ_TYPE_DISPLAY.get(
        (equipment_type or "").lower(),
        (equipment_type or "").replace("_", " ").title(),
    )

    serial_number = di.get("serial_number") or rs.get("serial_number") or None
    location      = dealer_contact.get("location") or None

    # ── Price ─────────────────────────────────────────────────────────────────
    asking_price = di.get("asking_price")
    price_formatted: str | None = None
    if asking_price is not None:
        try:
            price_formatted = f"${int(asking_price):,}"
        except (TypeError, ValueError):
            pass

    # ── Hours display (Band 2 large metric) ──────────────────────────────────
    hours_val = di.get("hours")
    hours_formatted: str | None = _fmt_number(hours_val) if hours_val is not None else None

    # ── Machine photo ─────────────────────────────────────────────────────────
    machine_photo_url: str | None = None
    if image_input_paths:
        for p in image_input_paths:
            uri = photo_data_uri(p)
            if uri:
                machine_photo_url = uri
                break

    # ── Hero tiles ────────────────────────────────────────────────────────────
    hero_tiles = build_hero_tiles(
        equipment_type=(equipment_type or "").lower(),
        specs=rs,
        field_confidence=fc,
    )

    # ── Spec rows (secondary / full specs band) ───────────────────────────────
    spec_rows = []
    _eq = (equipment_type or "").lower()

    lift_raw = rs.get("lift_path")
    if lift_raw and _eq != "skid_steer":
        lift_display = _LIFT_PATH_DISPLAY.get(str(lift_raw).lower(), str(lift_raw).title())
        spec_rows.append({"key": "Lift Path", "value": lift_display, "unit": ""})
    elif lift_raw and _eq == "skid_steer":
        pass  # lift_path is already in hero strip for skid steer

    op_weight = rs.get("operating_weight_lb") or rs.get("operating_weight_lbs")
    if op_weight is not None and _eq not in ("mini_excavator",):
        spec_rows.append({"key": "Op Weight", "value": _fmt_number(op_weight), "unit": "LB"})

    hinge_pin = rs.get("bucket_hinge_pin_height_in")
    if hinge_pin is not None:
        spec_rows.append({
            "key": "Hinge Pin",
            "value": str(int(hinge_pin)) if isinstance(hinge_pin, float) and hinge_pin.is_integer() else str(round(hinge_pin, 1)),
            "unit": "IN",
        })

    if _eq == "mini_excavator":
        width = rs.get("width_in")
    else:
        width = rs.get("width_over_tires_in") or rs.get("width_in")
    if width is not None:
        spec_rows.append({
            "key": "Width",
            "value": str(int(width)) if isinstance(width, float) and width.is_integer() else str(round(width, 1)),
            "unit": "IN",
        })

    hi_flow_gpm = rs.get("hi_flow_gpm") or rs.get("aux_flow_high_gpm")
    if hi_flow_gpm is not None and _eq != "skid_steer":
        spec_rows.append({
            "key": "High Flow",
            "value": str(int(hi_flow_gpm)) if isinstance(hi_flow_gpm, float) and hi_flow_gpm.is_integer() else str(round(hi_flow_gpm, 1)),
            "unit": "GPM",
        })

    hyd_psi = rs.get("hydraulic_pressure_standard_psi") or rs.get("hydraulic_pressure_psi")
    if hyd_psi is not None:
        spec_rows.append({"key": "Hyd Pressure", "value": _fmt_number(hyd_psi), "unit": "PSI"})

    ctrl = di.get("control_type") or rs.get("controls_type") or rs.get("control_pattern")
    if ctrl:
        ctrl_display = _CONTROL_DISPLAY.get(str(ctrl).lower(), str(ctrl).title())
        spec_rows.append({"key": "Controls", "value": ctrl_display, "unit": ""})

    # ── Feature groups ────────────────────────────────────────────────────────
    normalized_features = _normalize_features(di)
    feature_groups = build_feature_groups(
        equipment_type=(equipment_type or "").lower(),
        features=normalized_features,
    )

    # ── Attachments (parsed list for pill display) ────────────────────────────
    attachments_raw = di.get("attachments_included") or ""
    attachments: list[str] = [
        a.strip() for a in attachments_raw.split(",") if a.strip()
    ] if attachments_raw else []

    # ── Condition stats ───────────────────────────────────────────────────────
    # Order: hours (primary) → condition grade (primary) → ownership (primary)
    #        → track condition (secondary) → undercarriage (secondary)
    condition_stats = []

    if hours_val is not None:
        cur_year = datetime.date.today().year
        machine_year = di.get("year")
        hour_sub: str | None = None
        if machine_year:
            try:
                hour_sub = hours_context(cur_year, int(machine_year), int(hours_val))
            except (TypeError, ValueError):
                pass
        condition_stats.append({
            "label":    "Hours",
            "value":    _fmt_number(hours_val),
            "sublabel": hour_sub,
        })

    condition_grade = di.get("condition_grade")
    if condition_grade:
        condition_stats.append({
            "label":    "Condition",
            "value":    condition_grade.upper(),
            "sublabel": CONDITION_CONTEXT.get(condition_grade),
        })

    if di.get("one_owner"):
        condition_stats.append({
            "label":    "Ownership",
            "value":    "1 OWNER",
            "sublabel": None,
        })

    track_cond = di.get("track_condition") or rs.get("track_condition")
    if track_cond:
        condition_stats.append({"label": "Tracks", "value": str(track_cond), "sublabel": None})

    undercarriage_pct = rs.get("undercarriage_percent") or di.get("undercarriage_condition_pct")
    if undercarriage_pct is not None:
        condition_stats.append({"label": "Undercarriage", "value": f"{undercarriage_pct}%", "sublabel": None})

    # 4-stat case uses two-up (2×2) intentionally; 5th+ slot is dropped by priority
    condition_stats = condition_stats[:4]
    n = len(condition_stats)
    condition_grid_class = {1: "one-up", 2: "two-up", 3: "three-up", 4: "two-up"}.get(n, "two-up")

    dealer_notes = (di.get("additional_details") or di.get("condition_notes") or "").strip() or None

    # ── OEM verified flag ─────────────────────────────────────────────────────
    oem_verified = bool(rs and any(v is not None for v in rs.values()))

    # ── Dealer footer ─────────────────────────────────────────────────────────
    contact_name  = dealer_contact.get("contact_name") or dealer_contact.get("dealer_name") or ""
    contact_phone = dealer_contact.get("contact_phone") or dealer_contact.get("phone") or ""
    dealer_role   = dealer_contact.get("dealer_role") or ""

    # Signature: "— Name, Role" or whichever parts are present
    if contact_name and dealer_role:
        dealer_signature: str | None = f"— {contact_name}, {dealer_role}"
    elif contact_name:
        dealer_signature = f"— {contact_name}"
    elif dealer_role:
        dealer_signature = f"— {dealer_role}"
    else:
        dealer_signature = None

    logo_filename = dealer_contact.get("logo_filename")
    logo_path = None
    if logo_filename:
        if os.path.isabs(logo_filename) and os.path.isfile(logo_filename):
            logo_path = logo_filename
        elif outputs_dir and session_id:
            candidate = os.path.join(outputs_dir, session_id, logo_filename)
            if os.path.isfile(candidate):
                logo_path = candidate

    dealer_logo_url = None
    badge_style   = "dark"
    logo_bg       = "dark"
    divider_color = "yellow"
    if logo_path:
        if logo_as_data_uri:
            ext  = Path(logo_path).suffix.lower().lstrip(".")
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
            with open(logo_path, "rb") as _f:
                b64 = base64.b64encode(_f.read()).decode()
            dealer_logo_url = f"data:image/{mime};base64,{b64}"
        else:
            dealer_logo_url = f"/outputs/{session_id}/{logo_filename}"
        if _logo_is_light(logo_path):
            badge_style   = "white"
            logo_bg       = "white"
            divider_color = "red"
        else:
            logo_bg = "yellow"

    words = [w for w in (contact_name or "").split() if w]
    dealer_initials = "".join(w[0].upper() for w in words[:2]) or "?"

    return {
        "year":                   year,
        "make":                   make,
        "model":                  model,
        "equipment_type_display": eq_display,
        "serial_number":          serial_number,
        "location":               location,
        # Price + hours (Band 2)
        "price_formatted":        price_formatted,
        "hours_formatted":        hours_formatted,
        # Machine photo (Band 3)
        "machine_photo_url":      machine_photo_url,
        # Hero tiles (Band 3)
        "hero_tiles":             hero_tiles,
        # Spec rows (Band 6)
        "spec_rows":              spec_rows,
        # Feature groups + attachments (Band 4)
        "feature_groups":         feature_groups,
        "attachments":            attachments,
        # Condition block (Band 5)
        "condition_stats":        condition_stats,
        "condition_grid_class":   condition_grid_class,
        "dealer_notes":           dealer_notes,
        "dealer_signature":       dealer_signature,
        # OEM verified
        "oem_verified":           oem_verified,
        # Dealer footer
        "dealer_name":            contact_name or "Your Dealer",
        "dealer_role":            dealer_role,
        "dealer_phone":           contact_phone,
        "dealer_logo_url":        dealer_logo_url,
        "dealer_initials":        dealer_initials,
        "badge_style":            badge_style,
        "logo_bg":                logo_bg,
        "divider_color":          divider_color,
    }


def screenshot_spec_sheet(
    dealer_input_data: dict,
    resolved_specs: dict,
    ui_hints: dict,
    equipment_type: str,
    dealer_contact: dict,
    session_id: str,
    outputs_dir: str,
    output_path: str,
    field_confidence: dict | None = None,
    image_input_paths: list[str] | None = None,
) -> None:
    """
    Render spec_sheet.html to a PNG via Playwright headless Chromium.

    Uses the identical context builder as the /build-listing/spec-sheet/{id}
    browser route — guaranteed single source of truth for spec sheet content.

    The dealer logo (if any) is embedded as a base64 data URI so no live
    server is required during pack assembly.

    When image_input_paths is None, the session's _uploads/ directory is
    scanned automatically so the PNG export includes the machine photo without
    requiring listing_pack_builder.py to be changed.

    Viewport 500×900 at device_scale_factor=2 captures the 440 px wide .sheet
    element at high resolution (~880 px effective width).
    """
    import concurrent.futures
    import jinja2
    from playwright.sync_api import sync_playwright

    print(">>> USING NEW SPEC SHEET PIPELINE")

    # Auto-discover photo from session uploads when caller doesn't pass paths
    if image_input_paths is None and outputs_dir and session_id:
        uploads_dir = os.path.join(outputs_dir, session_id, "_uploads")
        first = find_first_photo(uploads_dir)
        image_input_paths = [first] if first else []

    ctx = build_spec_sheet_context(
        dealer_input_data=dealer_input_data,
        resolved_specs=resolved_specs,
        ui_hints=ui_hints,
        equipment_type=equipment_type,
        dealer_contact=dealer_contact,
        session_id=session_id,
        outputs_dir=outputs_dir,
        logo_as_data_uri=True,
        field_confidence=field_confidence,
        image_input_paths=image_input_paths,
    )

    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir), autoescape=True)
    html_str = env.get_template("spec_sheet.html").render(**ctx)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    def _playwright_render() -> None:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": 500, "height": 900},
                    device_scale_factor=2.0,
                )
                page.set_content(html_str, wait_until="networkidle")
                sheet_el = page.query_selector(".sheet")
                if sheet_el is None:
                    raise RuntimeError("'.sheet' selector not found in rendered spec sheet HTML")
                sheet_el.screenshot(path=str(output_path))
            finally:
                browser.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_playwright_render).result()
