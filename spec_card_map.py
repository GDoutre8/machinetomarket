"""Category-aware Verify Specs card definitions.

Single source of truth for which OEM spec cards render on the Verify page
per equipment_type, including the per-card override alias mirrors used to
push dealer edits back into resolved_specs across every consumer key.

Each card dict:
    key      — canonical override key (used as data-spec-key in the DOM)
    label    — desktop card title
    short    — mobile card title (uppercase, terse)
    index    — A1..A6 corner index
    type     — "int" | "float" | "string"  (override coercion + formatting)
    decimals — int, only when type == "float"
    unit     — display unit suffix (LB, HP, FT, GPM, IN, "")
    sub      — small grey caption under the value
    aliases  — list of resolved_specs keys to read from (first non-empty wins)
              and also the keys to mirror dealer overrides into
    required — True → REQUIRED footer badge / False → OPTIONAL
    warn     — True → render the .warn variant (verify-this-value treatment)
"""

from typing import Any

# --------------------------------------------------------------------------- #
# Per-type card configs                                                       #
# --------------------------------------------------------------------------- #

_ENGINE_CARD = {
    "key": "engine_model", "label": "Engine", "short": "ENGINE", "index": "A1",
    "type": "string", "unit": "",
    "sub_dynamic": "engine_sub",   # rendered from ctx.engine_sub
    "aliases": ["engine_model", "engine_manufacturer"],
    "required": True, "warn": False,
}

_HP_CARD = {
    "key": "net_hp", "label": "Horsepower", "short": "HORSEPOWER", "index": "A2",
    "type": "int", "unit": "HP", "sub": "Net rated",
    "aliases": ["net_hp", "horsepower_hp", "gross_hp", "horsepower_gross_hp"],
    "required": True, "warn": False,
}

_OP_WT_CARD = {
    "key": "operating_weight_lb", "label": "Operating Weight",
    "short": "OP. WEIGHT", "index": "A3",
    "type": "int", "unit": "LB", "sub": "Standard configuration",
    "aliases": ["operating_weight_lb", "operating_weight_lbs"],
    "required": True, "warn": False,
}

_SSL_CARDS = [
    _ENGINE_CARD,
    _HP_CARD,
    _OP_WT_CARD,
    {
        "key": "roc_lb", "label": "Lift Capacity", "short": "LIFT CAP.", "index": "A4",
        "type": "int", "unit": "LB", "sub": "SAE rated · 50% tip load",
        "aliases": ["roc_lb", "rated_operating_capacity_lbs"],
        "required": True, "warn": False,
    },
    {
        "key": "hydraulic_flow_gpm", "label": "Aux. Hyd. Flow", "short": "AUX FLOW",
        "index": "A5", "type": "float", "decimals": 1, "unit": "GPM",
        "sub": "Standard flow circuit",
        "aliases": ["hydraulic_flow_gpm", "aux_flow_standard_gpm"],
        "required": True, "warn": False,
    },
    {
        "key": "width_over_tires_in", "label": "Width Over Tires",
        "short": "WIDTH O.T.", "index": "A6",
        "type": "float", "decimals": 1, "unit": "IN",
        "sub": "Standard tire size",
        "aliases": ["width_over_tires_in", "track_width_in"],
        "required": False, "warn": False,
    },
]

_CTL_CARDS = [
    _ENGINE_CARD,
    _HP_CARD,
    _OP_WT_CARD,
    {
        "key": "roc_lb", "label": "Lift Capacity", "short": "LIFT CAP.", "index": "A4",
        "type": "int", "unit": "LB", "sub": "SAE rated · 35% tip load",
        "aliases": ["roc_lb", "rated_operating_capacity_lbs"],
        "required": True, "warn": False,
    },
    {
        "key": "hydraulic_flow_gpm", "label": "Aux. Hyd. Flow", "short": "AUX FLOW",
        "index": "A5", "type": "float", "decimals": 1, "unit": "GPM",
        "sub": "Standard flow circuit",
        "aliases": ["hydraulic_flow_gpm", "aux_flow_standard_gpm"],
        "required": True, "warn": False,
    },
    {
        "key": "track_width_in", "label": "Track Width", "short": "TRACK WIDTH",
        "index": "A6", "type": "float", "decimals": 1, "unit": "IN",
        "sub": "Multiple variants in registry",
        "aliases": ["track_width_in", "width_over_tracks_in", "width_over_tires_in"],
        "required": False, "warn": True,
    },
]

_TELEHANDLER_CARDS = [
    {
        "key": "lift_capacity_lb", "label": "Lift Capacity", "short": "LIFT CAP.",
        "index": "A1", "type": "int", "unit": "LB", "sub": "Maximum rated",
        "aliases": ["lift_capacity_lb", "lift_capacity_lbs"],
        "required": True, "warn": False,
    },
    {
        "key": "max_lift_height_ft", "label": "Max Lift Height",
        "short": "LIFT HEIGHT", "index": "A2",
        "type": "float", "decimals": 1, "unit": "FT", "sub": "Boom raised",
        "aliases": ["max_lift_height_ft"],
        "required": True, "warn": False,
    },
    {
        "key": "max_forward_reach_ft", "label": "Forward Reach",
        "short": "FWD REACH", "index": "A3",
        "type": "float", "decimals": 1, "unit": "FT", "sub": "Max horizontal reach",
        "aliases": ["max_forward_reach_ft"],
        "required": True, "warn": False,
    },
    dict(_HP_CARD, index="A4"),
    dict(_OP_WT_CARD, index="A5"),
    {
        "key": "drive_type", "label": "Drive Type", "short": "DRIVE", "index": "A6",
        "type": "string", "unit": "", "sub": "Drivetrain / transmission",
        "aliases": ["drive_type", "transmission_type"],
        "required": True, "warn": False,
    },
]

_MINI_EX_CARDS = [
    dict(_HP_CARD, index="A1"),
    dict(_OP_WT_CARD, index="A2"),
    {
        "key": "max_dig_depth_ft", "label": "Max Dig Depth", "short": "DIG DEPTH",
        "index": "A3", "type": "float", "decimals": 1, "unit": "FT",
        "sub": "Standard arm",
        "aliases": ["max_dig_depth_ft"],
        "required": True, "warn": False,
    },
    {
        "key": "max_reach_ft", "label": "Max Reach", "short": "REACH",
        "index": "A4", "type": "float", "decimals": 1, "unit": "FT",
        "sub": "Ground-level horizontal",
        "aliases": ["max_reach_ft"],
        "required": True, "warn": False,
    },
    {
        "key": "bucket_breakout_force_lbs", "label": "Bucket Breakout",
        "short": "BREAKOUT", "index": "A5",
        "type": "int", "unit": "LB", "sub": "Bucket curl force",
        "aliases": ["bucket_breakout_force_lbs", "bucket_breakout_lb"],
        "required": False, "warn": False,
    },
    {
        "key": "hydraulic_flow_gpm", "label": "Aux. Hyd. Flow", "short": "AUX FLOW",
        "index": "A6", "type": "float", "decimals": 1, "unit": "GPM",
        "sub": "Primary aux circuit",
        "aliases": ["hydraulic_flow_gpm", "aux_flow_primary_gpm", "aux_flow_standard_gpm"],
        "required": False, "warn": False,
    },
]

# Full-size excavators currently share native field names with mini ex
_EXCAVATOR_CARDS = _MINI_EX_CARDS

_WHEEL_LOADER_CARDS = [
    dict(_HP_CARD, index="A1"),
    dict(_OP_WT_CARD, index="A2"),
    {
        "key": "bucket_capacity_yd3", "label": "Bucket Capacity",
        "short": "BUCKET CAP.", "index": "A3",
        "type": "float", "decimals": 2, "unit": "YD³", "sub": "Standard bucket",
        "aliases": ["bucket_capacity_yd3", "bucket_capacity_cy"],
        "required": True, "warn": False,
    },
    {
        "key": "breakout_force_lbs", "label": "Breakout Force",
        "short": "BREAKOUT", "index": "A4",
        "type": "int", "unit": "LB", "sub": "Loader breakout",
        "aliases": ["breakout_force_lbs"],
        "required": False, "warn": False,
    },
    {
        "key": "hinge_pin_height_ft", "label": "Hinge Pin Height",
        "short": "HINGE PIN", "index": "A5",
        "type": "float", "decimals": 1, "unit": "FT", "sub": "Max raised",
        "aliases": ["hinge_pin_height_ft"],
        "required": False, "warn": False,
    },
    {
        "key": "hydraulic_flow_gpm", "label": "Aux. Hyd. Flow", "short": "AUX FLOW",
        "index": "A6", "type": "float", "decimals": 1, "unit": "GPM",
        "sub": "Implement circuit",
        "aliases": ["hydraulic_flow_gpm"],
        "required": False, "warn": False,
    },
]

_BACKHOE_CARDS = [
    dict(_HP_CARD, index="A1"),
    dict(_OP_WT_CARD, index="A2"),
    {
        "key": "max_dig_depth_ft", "label": "Max Dig Depth", "short": "DIG DEPTH",
        "index": "A3", "type": "float", "decimals": 1, "unit": "FT",
        "sub": "Backhoe standard arm",
        "aliases": ["max_dig_depth_ft"],
        "required": True, "warn": False,
    },
    {
        "key": "max_reach_ft", "label": "Max Reach", "short": "REACH",
        "index": "A4", "type": "float", "decimals": 1, "unit": "FT",
        "sub": "Backhoe horizontal",
        "aliases": ["max_reach_ft"],
        "required": False, "warn": False,
    },
    {
        "key": "loader_bucket_capacity_yd3", "label": "Loader Bucket",
        "short": "LDR BUCKET", "index": "A5",
        "type": "float", "decimals": 2, "unit": "YD³", "sub": "Standard loader",
        "aliases": ["loader_bucket_capacity_yd3"],
        "required": False, "warn": False,
    },
    {
        "key": "loader_breakout_force_lbf", "label": "Loader Breakout",
        "short": "BREAKOUT", "index": "A6",
        "type": "int", "unit": "LBF", "sub": "Loader curl",
        "aliases": ["loader_breakout_force_lbf", "loader_breakout_force_lbs"],
        "required": False, "warn": False,
    },
]

_DOZER_CARDS = [
    dict(_HP_CARD, index="A1"),
    dict(_OP_WT_CARD, index="A2"),
    {
        "key": "blade_capacity_yd3", "label": "Blade Capacity",
        "short": "BLADE CAP.", "index": "A3",
        "type": "float", "decimals": 2, "unit": "YD³",
        "sub": "Standard blade",
        "aliases": ["blade_capacity_yd3"],
        "required": True, "warn": False,
    },
    {
        "key": "blade_width_ft", "label": "Blade Width", "short": "BLADE W.",
        "index": "A4", "type": "float", "decimals": 1, "unit": "FT",
        "sub": "Standard blade",
        "aliases": ["blade_width_ft"],
        "required": False, "warn": False,
    },
    {
        "key": "ground_pressure_psi", "label": "Ground Pressure",
        "short": "GND PRESS.", "index": "A5",
        "type": "float", "decimals": 1, "unit": "PSI", "sub": "Standard track",
        "aliases": ["ground_pressure_psi"],
        "required": False, "warn": False,
    },
    {
        "key": "travel_speed_high_mph", "label": "Travel Speed",
        "short": "TRAVEL", "index": "A6",
        "type": "float", "decimals": 1, "unit": "MPH", "sub": "High range",
        "aliases": ["travel_speed_high_mph", "travel_speed_mph"],
        "required": False, "warn": False,
    },
]

_BOOM_LIFT_CARDS = [
    {
        "key": "platform_height_ft", "label": "Platform Height",
        "short": "PLATFORM HT.", "index": "A1",
        "type": "float", "decimals": 1, "unit": "FT", "sub": "Max working height",
        "aliases": ["platform_height_ft"],
        "required": True, "warn": False,
    },
    {
        "key": "horizontal_reach_ft", "label": "Horizontal Reach",
        "short": "REACH", "index": "A2",
        "type": "float", "decimals": 1, "unit": "FT", "sub": "Max horizontal",
        "aliases": ["horizontal_reach_ft"],
        "required": True, "warn": False,
    },
    {
        "key": "platform_capacity_lbs", "label": "Platform Capacity",
        "short": "CAPACITY", "index": "A3",
        "type": "int", "unit": "LB", "sub": "Unrestricted",
        "aliases": ["platform_capacity_lbs"],
        "required": True, "warn": False,
    },
    dict(_OP_WT_CARD, index="A4"),
    {
        "key": "power_source", "label": "Power Source", "short": "POWER",
        "index": "A5", "type": "string", "unit": "", "sub": "Drivetrain",
        "aliases": ["power_source"],
        "required": True, "warn": False,
    },
    {
        "key": "boom_type", "label": "Boom Type", "short": "BOOM",
        "index": "A6", "type": "string", "unit": "",
        "sub": "Telescopic / articulating",
        "aliases": ["boom_type"],
        "required": False, "warn": False,
    },
]

_SCISSOR_LIFT_CARDS = [
    {
        "key": "platform_height_ft", "label": "Platform Height",
        "short": "PLATFORM HT.", "index": "A1",
        "type": "float", "decimals": 1, "unit": "FT", "sub": "Max working height",
        "aliases": ["platform_height_ft"],
        "required": True, "warn": False,
    },
    {
        "key": "platform_capacity_lbs", "label": "Platform Capacity",
        "short": "CAPACITY", "index": "A2",
        "type": "int", "unit": "LB", "sub": "Unrestricted",
        "aliases": ["platform_capacity_lbs"],
        "required": True, "warn": False,
    },
    dict(_OP_WT_CARD, index="A3"),
    {
        "key": "platform_length_ft", "label": "Platform Length",
        "short": "DECK L.", "index": "A4",
        "type": "float", "decimals": 1, "unit": "FT", "sub": "Stowed deck",
        "aliases": ["platform_length_ft"],
        "required": False, "warn": False,
    },
    {
        "key": "platform_width_ft", "label": "Platform Width",
        "short": "DECK W.", "index": "A5",
        "type": "float", "decimals": 1, "unit": "FT", "sub": "Stowed deck",
        "aliases": ["platform_width_ft"],
        "required": False, "warn": False,
    },
    {
        "key": "power_source", "label": "Power Source", "short": "POWER",
        "index": "A6", "type": "string", "unit": "", "sub": "Drivetrain",
        "aliases": ["power_source"],
        "required": True, "warn": False,
    },
]

# --------------------------------------------------------------------------- #
# Public dispatch                                                             #
# --------------------------------------------------------------------------- #

SPEC_CARDS_BY_TYPE: dict[str, list[dict[str, Any]]] = {
    "skid_steer":           _SSL_CARDS,
    "compact_track_loader": _CTL_CARDS,
    "telehandler":          _TELEHANDLER_CARDS,
    "mini_excavator":       _MINI_EX_CARDS,
    "excavator":            _EXCAVATOR_CARDS,
    "wheel_loader":         _WHEEL_LOADER_CARDS,
    "backhoe_loader":       _BACKHOE_CARDS,
    "dozer":                _DOZER_CARDS,
    "boom_lift":            _BOOM_LIFT_CARDS,
    "scissor_lift":         _SCISSOR_LIFT_CARDS,
}

# Fallback when equipment_type is missing or unrecognized — use SSL shape
_DEFAULT_CARDS = _SSL_CARDS


def get_cards_for(equipment_type: str) -> list[dict[str, Any]]:
    et = (equipment_type or "").strip().lower()
    return SPEC_CARDS_BY_TYPE.get(et, _DEFAULT_CARDS)


def get_alias_map() -> dict[str, list[str]]:
    """Flat key→aliases map across every equipment type, used by the
    override-merge step in app.py to mirror dealer edits into every
    consumer key. When the same canonical key appears in multiple type
    configs (e.g. net_hp), aliases are unioned."""
    out: dict[str, list[str]] = {}
    for cards in SPEC_CARDS_BY_TYPE.values():
        for card in cards:
            key = card["key"]
            existing = out.setdefault(key, [])
            for alias in card.get("aliases", [key]):
                if alias not in existing:
                    existing.append(alias)
            if key not in existing:
                existing.insert(0, key)
    return out
