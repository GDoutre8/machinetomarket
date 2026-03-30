"""
mtm_service.py
==============
Adapter layer between the FastAPI web app and the MTM parser modules.

Pipeline:
    raw_text
      → safe_parse_listing        (regex fields: year, hours, location, contact, condition)
      → match_known_model         (alias enrichment: make, model, equipment_type)
      → safe_lookup_machine       (Tier 1 spec injection gate)
      → _stub_build_listing_data  (merge parsed + specs)
      → _stub_generate_listing_text (format output)
      → format_output_response
      → dict

Public API (called from app.py):
    fix_listing_service(raw_text: str) -> dict

Integration checklist for real modules:
    Search for "── SWAP ──" to find each replacement point.
"""

from __future__ import annotations
import os
import re
import uuid
from datetime import datetime
from typing import Any

# ── Frozen parser modules ─────────────────────────────────────────────────────
from mtm_listing_parser_price       import extract_price
from mtm_listing_parser_attachments import extract_attachments
from mtm_listing_parser_model_alias import match_known_model, lookup_make_for_model, scan_bare_model_tokens
from mtm_registry_lookup            import lookup_machine

# ── Spec resolver ─────────────────────────────────────────────────────────────
from spec_resolver.spec_resolver import resolve as _spec_resolve
from spec_resolver.types         import MatchType, ResolverInput

# ── Spec sheet generator ───────────────────────────────────────────────────────
from spec_sheet_generator import (
    generate_spec_sheet_image,
    generate_spec_sheet_variants,
    generate_spec_sheet as _gen_spec_sheet,
)
from package_generator    import generate_listing_package

# ── Listing scorer ─────────────────────────────────────────────────────────────
from mtm_scorer import FieldValue, ListingInput, score as _score_listing, build_fix_my_listing

# ── Output directory ───────────────────────────────────────────────────────────
_OUTPUTS_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


def _make_session_dir(parsed: dict) -> tuple[str, str]:
    """
    Create a unique per-request output subdirectory.

    Name format:  YYYYMMDD_HHMMSS_<make>_<model>_<6hex>
    Example:      20260324_154412_bobcat_t770_ab12cd

    Returns
    -------
    abs_dir    : absolute filesystem path  (passed to generators as output_path)
    web_prefix : URL prefix served by the /outputs static mount
                 e.g. "/outputs/20260324_154412_bobcat_t770_ab12cd"
    """
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    make  = re.sub(r"[^a-z0-9]", "", (parsed.get("make")  or "").lower())[:10]
    model = re.sub(r"[^a-z0-9]", "", (parsed.get("model") or "").lower())[:10]
    slug  = "_".join(p for p in [make, model] if p) or "unknown"
    uid   = uuid.uuid4().hex[:6]
    name  = f"{ts}_{slug}_{uid}"
    abs_dir = os.path.join(_OUTPUTS_BASE, name)
    os.makedirs(abs_dir, exist_ok=True)
    return abs_dir, f"/outputs/{name}"


def _asset_url(abs_path: str | None, web_prefix: str) -> str | None:
    """Convert an absolute file path to a web-accessible URL using the session prefix."""
    if not abs_path:
        return None
    return f"{web_prefix}/{os.path.basename(abs_path)}"


# ── Config ────────────────────────────────────────────────────────────────────

SPEC_CONFIDENCE_THRESHOLD = 0.75

SUPPORTED_PLATFORMS = [
    "Facebook Marketplace",
    "Craigslist",
    "IronPlanet",
    "MachineryTrader",
    "Equipment Trader",
]


# ══════════════════════════════════════════════════════════════════════════════
# STUB FUNCTIONS  (swap bodies when real modules are ready)
# ══════════════════════════════════════════════════════════════════════════════

def _stub_lookup_machine(parsed: dict) -> tuple[dict | None, float]:
    """
    ── SWAP body ──
        specs, conf = lookup_machine(parsed)
        if specs is None:
            specs, conf = search_by_model(parsed.get("make"), parsed.get("model"))
        return specs, conf
    """
    return None, 0.0


def _stub_build_listing_data(parsed: dict, specs: dict | None) -> dict:
    """── SWAP body ──  return build_listing_data(parsed, specs)"""
    data = dict(parsed)
    if specs:
        data["specs"] = specs
    return data


def _stub_generate_listing_text(
    listing_data: dict,
    added_specs: dict | None,
    spec_level: str = "essential",
) -> str:
    """
    ── SWAP body ──  return generate_listing_text(listing_data)

    MTM output format:
        [Headline]
        Machine Snapshot • ...
        Features
        Attachments
        Condition • ...
        Price
        Location
        Contact
        #hashtags
    """
    spec_level = _normalize_tier(spec_level)   # accept legacy quick/dealer/full

    year      = listing_data.get("year") or ""
    make      = listing_data.get("make") or ""
    model     = listing_data.get("model") or ""
    hours     = listing_data.get("hours")
    price_int = listing_data.get("price_value")
    price_obo = listing_data.get("price_is_obo", False)
    location  = listing_data.get("location")
    contact   = listing_data.get("contact")
    condition = listing_data.get("condition")
    notes     = listing_data.get("notes")
    attachments = listing_data.get("attachments") or []
    features    = listing_data.get("features") or []

    # Headline — always emit year / make / model when available
    headline_parts = [str(p) for p in [year, make, model] if p]
    headline = " ".join(headline_parts) if headline_parts else "Heavy Equipment for Sale"

    lines = [headline]

    # Hours line immediately under headline
    if hours:
        lines.append(f"{hours:,} hours on machine")

    lines.append("")

    # Spec section — fields and title driven by spec_level
    _spec_payload = added_specs or listing_data.get("specs") or {}
    rs            = _spec_payload.get("resolved_specs") or {}
    ui_hints_data = _spec_payload.get("ui_hints") or {}

    _canonical_eq = (
        (added_specs or {}).get("equipment_type")
        or listing_data.get("equipment_type")
        or ""
    )
    bullets = _build_spec_bullets(
        rs, ui_hints_data, spec_level,
        equipment_type=_canonical_eq,
    ) if rs else []

    if notes:
        bullets.append(notes.strip().rstrip(".").capitalize())

    if bullets:
        section_title = _SPEC_SECTION_TITLES.get(spec_level, "Machine Snapshot")
        lines.append(section_title)
        for b in bullets:
            lines.append(f"• {b.rstrip('.')}")
        lines.append("")

    # Features first (cab, controls, hydraulic options, camera, etc.)
    if features:
        lines.append("Features")
        for f in features:
            lines.append(f"• {f}")
        lines.append("")

    # Attachments (physical work tools only)
    if attachments:
        lines.append("Attachments")
        for a in attachments:
            lines.append(f"• {a}")
        lines.append("")

    # Condition — omit section entirely if not detected
    if condition:
        lines.append("Condition")
        lines.append(f"• {condition}")
        lines.append("")

    # Price — omit section entirely if not detected
    if price_int:
        price_str = f"${price_int:,}"
        if price_obo:
            price_str += " OBO"
        lines.append("Price")
        lines.append(price_str)
        lines.append("")

    # Location — omit section entirely if not detected
    if location:
        lines.append("Location")
        lines.append(location)
        lines.append("")

    # Contact — omit section entirely if not detected
    if contact:
        lines.append("Contact")
        lines.append(contact)

    # Hashtags
    tags = []
    if make:
        tags.append(f"#{re.sub(r'[^a-z0-9]', '', make.lower())}")
    if model:
        tags.append(f"#{re.sub(r'[^a-z0-9]', '', model.lower())}")
    tags += ["#heavyequipment", "#equipmentdealer", "#usedequipment"]
    lines.append("")
    lines.append(" ".join(tags))

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SPEC RESOLVER BRIDGE  (translates registry lookup result → ResolverInput)
# ══════════════════════════════════════════════════════════════════════════════

# Maps registry equipment_type strings → spec_resolver category codes
_EQ_TYPE_TO_CATEGORY: dict[str, str] = {
    "skid_steer":           "SSL",
    "compact_track_loader": "CTL",
    "mini_excavator":       "MINI",
    "excavator":            "EX",
    "wheel_loader":         "WL",
    "telehandler":          "TH",
    "backhoe_loader":       "BH",
    "dozer":                "DOZ",
    "crawler_dozer":        "DOZ",  # alias — registry uses "dozer"
}

# Maps registry JSON spec key names → spec_resolver canonical field names.
# The registry uses legacy verbose keys; resolvers use short canonical names.
_SPEC_KEY_MAP: dict[str, str] = {
    "horsepower_hp":                "net_hp",
    "rated_operating_capacity_lbs": "roc_lb",
    "tipping_load_lbs":             "tipping_load_lb",
    "tipping_load_straight_lb":     "tipping_load_lb",      # wheel_loader variant
    "operating_weight_lbs":         "operating_weight_lb",
    "aux_flow_standard_gpm":        "hydraulic_flow_gpm",
    "aux_flow_high_gpm":            "hi_flow_gpm",
    # CTL records that use hydraulic_flow_* prefix instead of aux_flow_*
    "hydraulic_flow_standard_gpm":  "hydraulic_flow_gpm",
    "hydraulic_flow_high_gpm":      "hi_flow_gpm",
    # Excavator / mini-ex primary aux circuit
    "aux_flow_primary_gpm":         "hydraulic_flow_gpm",
    "aux_pressure_primary_psi":     "hydraulic_pressure_standard_psi",
    # Single-field hydraulic pressure (no std/high split)
    "hydraulic_pressure_psi":       "hydraulic_pressure_standard_psi",
    # Wheel loader: registry stores net and gross separately; prefer net
    "net_power_hp":                 "net_hp",
    # Telehandler: registry uses engine_hp as the HP field
    "engine_hp":                    "net_hp",
    # Telehandler: lookup_machine renames these before they reach full_record;
    # map them back to the spec_resolver / display canonical names.
    "max_lift_capacity_lbs":        "lift_capacity_lb",
    "lift_height_ft":               "max_lift_height_ft",
    "forward_reach_ft":             "max_forward_reach_ft",
    # Dig depth: registry key → resolver canonical name used by dig_depth.resolve
    "max_dig_depth_in":             "max_dig_depth",   # excavator, mini_ex (value in inches)
    "max_dig_depth_ft":             "max_dig_depth",   # backhoe_loader (value in feet → converted below)
    # Breakout force: registry key → resolver canonical name used by breakout_force.resolve
    "bucket_dig_force_lbf":         "bucket_breakout_lb",   # excavator, mini_ex
    "backhoe_bucket_force_lbf":     "bucket_breakout_lb",   # backhoe_loader
    # Bucket/blade capacity: source registries use 'cy' suffix; canonical is 'yd3'
    "bucket_capacity_cy":           "bucket_capacity_yd3",  # excavator, wheel_loader
}

# Fields whose registry values are stored in feet but the resolver expects inches.
# _normalize_registry_record multiplies these by 12 after the key rename.
_SPEC_FT_TO_IN_FIELDS: frozenset[str] = frozenset({"max_dig_depth_ft"})

# ── Spec display levels — keyed by equipment type ────────────────────────────
# Fields listed in render order.  Only fields present in resolved_specs appear.
# hi_flow_gpm is intentionally absent: it is merged into hydraulic_flow_gpm
# display by _build_display_specs and must not appear as a standalone row.
#
# Target spec counts:
#   Quick  →  3    (marketplace / FB)
#   Dealer →  6–7  (listing)
#   Full   →  9–12 (spec sheet / credibility)

# SSL and CTL share identical field sets for now.
# Defined once here; both keys reference the same dict so future divergence
# only requires updating one entry.
_SSL_CTL_FIELDS: dict[str, list[str]] = {
    "essential": [
        "net_hp",
        "roc_lb",
        "hydraulic_flow_gpm",
    ],
    "standard": [
        "net_hp",
        "roc_lb",
        "tipping_load_lb",
        "operating_weight_lb",
        "hydraulic_flow_gpm",
        "travel_speed_high_mph",
        "width_over_tires_in",
        "bucket_hinge_pin_height_in",
        "lift_path",
    ],
    "technical": [
        "net_hp",
        "roc_lb",
        "tipping_load_lb",
        "operating_weight_lb",
        "hydraulic_flow_gpm",
        "hydraulic_pressure_standard_psi",
        "travel_speed_high_mph",
        "travel_speed_low_mph",
        "width_over_tires_in",
        "bucket_hinge_pin_height_in",
        "lift_path",
        "fuel_type",
        "frame_size",
    ],
}

SPEC_LEVEL_FIELDS: dict[str, dict[str, list[str]]] = {
    "skid_steer_loader":    _SSL_CTL_FIELDS,
    "compact_track_loader": _SSL_CTL_FIELDS,
    "mini_excavator": {
        "essential": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
        ],
        "standard": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
            "max_reach_ground_in",
            "hydraulic_flow_gpm",
            "tail_swing_type",
        ],
        "technical": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
            "max_reach_ground_in",
            "hydraulic_flow_gpm",
            "hydraulic_pressure_standard_psi",
            "travel_speed_high_mph",
            "tail_swing_type",
            "fuel_type",
        ],
    },
    # ── New equipment types ───────────────────────────────────────────────────
    # Fields limited to what the spec resolver actually emits for each category.
    # Dig depth and breakout force are noted gaps (see _SPEC_KEY_MAP comments).
    "excavator": {
        "essential": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
        ],
        "standard": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
            "bucket_capacity_yd3",
            "bucket_breakout_lb",
            "travel_speed_high_mph",
            "travel_speed_low_mph",
            "hydraulic_flow_gpm",
            "tail_swing_type",
            "fuel_type",
        ],
        "technical": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
            "bucket_capacity_yd3",
            "bucket_breakout_lb",
            "travel_speed_high_mph",
            "travel_speed_low_mph",
            "hydraulic_flow_gpm",
            "tail_swing_type",
            "fuel_type",
        ],
    },
    "wheel_loader": {
        "essential": [
            "net_hp",
            "operating_weight_lb",
            "bucket_capacity_yd3",
            "travel_speed_mph",
        ],
        "standard": [
            "net_hp",
            "operating_weight_lb",
            "bucket_capacity_yd3",
            "travel_speed_mph",
            "hydraulic_flow_gpm",
            "fuel_type",
        ],
        "technical": [
            "net_hp",
            "operating_weight_lb",
            "bucket_capacity_yd3",
            "travel_speed_mph",
            "hydraulic_flow_gpm",
            "fuel_type",
        ],
    },
    "telehandler": {
        "essential": [
            "net_hp",
            "lift_capacity_lb",
            "max_lift_height_ft",
        ],
        "standard": [
            "net_hp",
            "operating_weight_lb",
            "lift_capacity_lb",
            "max_lift_height_ft",
            "max_forward_reach_ft",
            "travel_speed_mph",
            "drive_type",
            "hydraulic_flow_gpm",
        ],
        "technical": [
            "net_hp",
            "operating_weight_lb",
            "lift_capacity_lb",
            "max_lift_height_ft",
            "max_forward_reach_ft",
            "travel_speed_mph",
            "drive_type",
            "hydraulic_flow_gpm",
            "fuel_type",
        ],
    },
    "backhoe_loader": {
        "essential": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
        ],
        "standard": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
            "loader_bucket_capacity_yd3",
            "bucket_breakout_lb",
            "travel_speed_mph",
            "hydraulic_flow_gpm",
            "fuel_type",
        ],
        "technical": [
            "net_hp",
            "operating_weight_lb",
            "max_dig_depth",
            "loader_bucket_capacity_yd3",
            "bucket_breakout_lb",
            "travel_speed_mph",
            "hydraulic_flow_gpm",
            "fuel_type",
        ],
    },
    "crawler_dozer": {
        "essential": [
            "net_hp",
            "operating_weight_lb",
            "blade_capacity_yd3",
            "travel_speed_high_mph",
        ],
        "standard": [
            "net_hp",
            "operating_weight_lb",
            "blade_capacity_yd3",
            "travel_speed_high_mph",
            "travel_speed_low_mph",
            "ground_pressure_psi",
            "hydraulic_flow_gpm",
            "fuel_type",
        ],
        "technical": [
            "net_hp",
            "operating_weight_lb",
            "blade_capacity_yd3",
            "travel_speed_high_mph",
            "travel_speed_low_mph",
            "ground_pressure_psi",
            "hydraulic_flow_gpm",
            "fuel_type",
        ],
    },
}

# Maps parsed equipment_type strings → SPEC_LEVEL_FIELDS keys
_EQ_TYPE_TO_SPEC_KEY: dict[str, str] = {
    "skid_steer":           "skid_steer_loader",
    "compact_track_loader": "compact_track_loader",
    "mini_excavator":       "mini_excavator",
    "excavator":            "excavator",
    "wheel_loader":         "wheel_loader",
    "telehandler":          "telehandler",
    "backhoe_loader":       "backhoe_loader",
    "dozer":                "crawler_dozer",
    "crawler_dozer":        "crawler_dozer",
}
_DEFAULT_SPEC_TYPE = "skid_steer_loader"   # fallback for unknown types

# ── Runtime tier names ────────────────────────────────────────────────────────
# The active Python runtime uses three tiers: essential / standard / technical.
# These are the ONLY authoritative tier names for the API, display, and listing
# text pipeline.
#
# Relationship to other tier systems:
#   spec_display_profiles.json / specResolver.js  — frontend/JS display layer;
#       uses the same three names (essential/standard/technical).  NOT active in
#       the FastAPI runtime — the Python pipeline below is the runtime authority.
#   Registry-level tiers (core/supplemental/provisional) — internal data quality
#       labels on individual registry records; separate concern, not surfaced here.
#
# Backward-compatibility: callers that still send the old names are remapped by
# _normalize_tier() at each entry point.  The old names are NOT used internally.
_VALID_TIERS  = frozenset({"essential", "standard", "technical"})
_TIER_COMPAT  = {"quick": "essential", "dealer": "standard", "full": "technical"}
_DEFAULT_TIER = "essential"


def _normalize_tier(spec_level: str) -> str:
    """Map legacy quick/dealer/full names → essential/standard/technical.
    Unknown values are returned unchanged so callers can handle them."""
    return _TIER_COMPAT.get(spec_level, spec_level)


_SPEC_SECTION_TITLES: dict[str, str] = {
    "essential":  "Machine Snapshot",
    "standard":   "Dealer Specs",
    "technical":  "Full Specifications",
}


def _fmt_num(v: Any) -> str:
    """Format a numeric spec value with comma separators; drops .0 from whole floats."""
    if isinstance(v, float) and v.is_integer():
        return f"{int(v):,}"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return str(round(v, 1))
    return str(v)


# ── Spec display metadata — single source of truth for labels and units ────────
# Used by _build_display_specs, spec_sheet_generator, and the frontend.
# Fields NOT in this table get a generic title-cased label with no unit.

_SPEC_DISPLAY_META: dict[str, dict] = {
    "net_hp":                          {"label": "Engine",                    "unit": "hp"},
    "roc_lb":                          {"label": "Rated operating capacity",  "unit": "lbs"},
    "tipping_load_lb":                 {"label": "Tipping load",              "unit": "lbs"},
    "operating_weight_lb":             {"label": "Operating weight",          "unit": "lbs"},
    "hydraulic_flow_gpm":              {"label": "Aux hydraulic flow",        "unit": "gpm"},
    "hi_flow_gpm":                     {"label": "Aux hydraulic flow (high)", "unit": "gpm"},
    "hydraulic_pressure_standard_psi": {"label": "Hydraulic pressure",        "unit": "psi"},
    "travel_speed_mph":                {"label": "Travel speed",              "unit": "mph"},
    "travel_speed_high_mph":           {"label": "Max travel speed",          "unit": "mph"},
    "travel_speed_low_mph":            {"label": "Travel speed (low)",        "unit": "mph"},
    "lift_path":                       {"label": "Lift path",                 "unit": ""},
    "fuel_type":                       {"label": "Fuel type",                 "unit": ""},
    "frame_size":                      {"label": "Frame size",                "unit": ""},
    "max_dig_depth_in":                {"label": "Max dig depth",             "unit": "ft"},   # legacy key — no longer in SPEC_LEVEL_FIELDS
    "max_dig_depth":                   {"label": "Max dig depth",             "unit": ""},     # resolver output: pre-formatted "X ft Y in" string
    "max_reach_ground_in":             {"label": "Max reach",                 "unit": "ft"},
    "tail_swing_type":                 {"label": "Tail swing",                "unit": ""},
    # Excavator / backhoe breakout force
    "bucket_breakout_lb":              {"label": "Bucket breakout force",     "unit": "lbs"},
    # Telehandler lift specs
    "lift_capacity_lb":                {"label": "Max lift capacity",         "unit": "lbs"},
    "max_lift_height_ft":              {"label": "Max lift height",           "unit": "ft"},
    "max_forward_reach_ft":            {"label": "Max forward reach",         "unit": "ft"},
    # Capacity fields — excavator/wheel_loader bucket, backhoe loader bucket, dozer blade
    "bucket_capacity_yd3":             {"label": "Bucket capacity",           "unit": "yd3"},
    "loader_bucket_capacity_yd3":      {"label": "Loader bucket",             "unit": "yd3"},
    "blade_capacity_yd3":              {"label": "Blade capacity",            "unit": "yd3"},
    # CTL/SSL dimensional specs
    "width_over_tires_in":             {"label": "Width over tires",          "unit": "in"},
    "bucket_hinge_pin_height_in":      {"label": "Hinge pin height",          "unit": "in"},
    # Dozer site-suitability and telehandler drivetrain
    "ground_pressure_psi":             {"label": "Ground pressure",           "unit": "psi"},
    "drive_type":                      {"label": "Drive type",                "unit": ""},
}


def _build_display_specs(
    resolved_specs: dict,
    ui_hints: dict,
    spec_level: str,
    equipment_type: str = "",
) -> list[dict]:
    """
    Return an ordered list of display-ready spec items for the given level
    and equipment type.

    Each item: {"key": str, "label": str, "value": str}

    This is the single source of truth for spec formatting.  All consumers
    (listing text, API response display_specs, Facebook post) derive from here.

    Hydraulic flow special cases:
      - _displayHiFlow=True  → show std value labelled "gpm high"
      - essential/standard + both std and hi_flow present → combine on one line
      - technical + both present  → two separate items (std label, then high label)
    """
    eq_key  = _EQ_TYPE_TO_SPEC_KEY.get((equipment_type or "").lower(), _DEFAULT_SPEC_TYPE)
    eq_sets = SPEC_LEVEL_FIELDS.get(eq_key, SPEC_LEVEL_FIELDS[_DEFAULT_SPEC_TYPE])
    fields  = eq_sets.get(spec_level, eq_sets.get("essential", []))

    hi_flow_active = ui_hints.get("_displayHiFlow", False)
    items: list[dict] = []

    for field in fields:
        val = resolved_specs.get(field)
        if val is None:
            continue

        meta  = _SPEC_DISPLAY_META.get(field, {"label": field.replace("_", " ").title(), "unit": ""})
        label = meta["label"]
        unit  = meta["unit"]

        # ── Special case: hydraulic flow combination logic ─────────────────
        if field == "hydraulic_flow_gpm":
            hi_val = resolved_specs.get("hi_flow_gpm")
            if hi_flow_active:
                items.append({"key": field, "label": label,
                               "value": f"{_fmt_num(val)} gpm high"})
            elif hi_val is not None and spec_level == "technical":
                items.append({"key": field, "label": "Aux hydraulic flow (std)",
                               "value": f"{_fmt_num(val)} gpm"})
            elif hi_val is not None:
                items.append({"key": field, "label": label,
                               "value": f"{_fmt_num(val)} gpm std / {_fmt_num(hi_val)} gpm high"})
            else:
                items.append({"key": field, "label": label,
                               "value": f"{_fmt_num(val)} gpm"})
            continue

        # hi_flow_gpm is only emitted as a standalone line at full level
        # when _displayHiFlow is not already promoting it above
        if field == "hi_flow_gpm":
            if not hi_flow_active:
                items.append({"key": field, "label": label,
                               "value": f"{_fmt_num(val)} gpm"})
            continue

        # ── Mini excavator inch→foot conversions ──────────────────────────
        if field in ("max_dig_depth_in", "max_reach_ground_in"):
            try:
                items.append({"key": field, "label": label,
                               "value": f"{round(val / 12, 1)} ft"})
            except (TypeError, ValueError):
                items.append({"key": field, "label": label,
                               "value": f"{_fmt_num(val)} in"})
            continue

        # ── Generic numeric / string field ────────────────────────────────
        if isinstance(val, (int, float)):
            display_val = f"{_fmt_num(val)} {unit}".strip() if unit else _fmt_num(val)
        else:
            display_val = str(val)
            # Humanize registry string values that arrive as lowercase.
            # tail_swing_type uses descriptive underscore values across equipment types
            # (e.g. "zero_tail_swing", "conventional_tail_swing") so needs title-case
            # with underscore→space substitution rather than simple capitalize().
            if field == "tail_swing_type":
                display_val = display_val.replace("_", " ").title()
            elif field in ("fuel_type", "lift_path", "frame_size"):
                display_val = display_val.capitalize()

        items.append({"key": field, "label": label, "value": display_val})

    return items


def _build_spec_bullets(
    resolved_specs: dict,
    ui_hints: dict,
    spec_level: str,
    equipment_type: str = "",
) -> list[str]:
    """Thin wrapper — converts display_specs items to listing-text bullet strings."""
    return [
        f"{item['label']}: {item['value']}"
        for item in _build_display_specs(resolved_specs, ui_hints, spec_level, equipment_type)
    ]


def _eq_type_to_category(equipment_type: str) -> str:
    return _EQ_TYPE_TO_CATEGORY.get((equipment_type or "").lower(), "SSL")


# ══════════════════════════════════════════════════════════════════════════════
# SELLER SPEC EXTRACTION
# Pulls numeric spec values from raw listing text so the scorer can give credit
# for explicitly stated specs even when no registry match exists.
#
# Design constraints:
#   - Conservative: all patterns require the field label to appear near the
#     value. Bare numbers without context labels are never extracted.
#   - Non-destructive: does NOT touch parsed dict or registry output.
#   - Values returned in canonical units expected by the scorer schema:
#       hp → net_hp (numeric)
#       lb/lbs → *_lb (numeric, commas stripped)
#       gpm → hydraulic_flow_gpm (numeric)
#       ft+in / ft → max_dig_depth (inches, numeric)
#       mph → both travel_speed_high_mph AND travel_speed_mph (numeric)
#       ft → max_lift_height_ft / max_forward_reach_ft (numeric)
#       % → *_pct (numeric)
# ══════════════════════════════════════════════════════════════════════════════

# ── Compiled patterns ─────────────────────────────────────────────────────────

# net_hp: "74 HP", "74 hp", "74 horsepower", "74 h.p."
_SE_HP_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:net\s*)?(?:h\.?p\.?|horse\s*power)\b'
    r'|(?:net\s*)?horse\s*power[:\s]+(\d+(?:\.\d+)?)',
    re.I,
)

# roc_lb: "2,950 lb ROC", "ROC: 2950 lbs", "rated operating capacity 2950"
_SE_ROC_RE = re.compile(
    r'(?:ROC|rated\s+operating\s+cap(?:acity)?)[:\s]*(\d[\d,]*)\s*(?:lb|lbs)?'
    r'|(\d[\d,]*)\s*(?:lb|lbs)[,\s]+ROC\b'
    r'|(\d[\d,]*)\s*(?:lb|lbs)\s+rated\s+operating\s+cap(?:acity)?',
    re.I,
)

# operating_weight_lb: "8,615 lb operating weight", "operating weight: 8615 lbs"
_SE_OP_WEIGHT_RE = re.compile(
    r'(?:operating\s+weight|op(?:erating)?\.?\s*wt\.?|machine\s+weight)[:\s]*(\d[\d,]*)\s*(?:lb|lbs)?'
    r'|(\d[\d,]*)\s*(?:lb|lbs)[,\s]+(?:operating\s+weight|op(?:erating)?\.?\s*wt\.?)',
    re.I,
)

# tipping_load_lb: "5,800 lb tipping load", "tipping load: 5800 lbs"
_SE_TIP_LOAD_RE = re.compile(
    r'(?:tipping\s+load|tip\s+load|tipping\s+cap(?:acity)?)[:\s]*(\d[\d,]*)\s*(?:lb|lbs)?'
    r'|(\d[\d,]*)\s*(?:lb|lbs)[,\s]+(?:tipping\s+load|tip\s+load)',
    re.I,
)

# lift_capacity_lb (telehandler): "10,000 lb lift capacity", "max lift capacity: 10000"
_SE_LIFT_CAP_RE = re.compile(
    r'(?:(?:max|rated)\s+)?(?:lift\s+cap(?:acity)?|rated\s+lift)[:\s]*(\d[\d,]*)\s*(?:lb|lbs)?'
    r'|(\d[\d,]*)\s*(?:lb|lbs)[,\s]+(?:(?:max|rated)\s+)?(?:lift\s+cap(?:acity)?|rated\s+lift)',
    re.I,
)

# hydraulic_flow_gpm: "23.3 gpm", "23.3 GPM std", "flow: 23 gpm"
_SE_GPM_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:gpm|g\.p\.m\.|gal(?:lon)?s?\s*/?\s*min(?:ute)?)\b',
    re.I,
)

# travel_speed (stored under both travel_speed_high_mph and travel_speed_mph):
# "11.8 mph", "travel speed: 11.8 mph", "top speed 11.8mph"
_SE_MPH_RE = re.compile(
    r'(?:travel\s+speed|top\s+speed)[:\s]*(\d+(?:\.\d+)?)\s*(?:mph|MPH)?'
    r'|(\d+(?:\.\d+)?)\s*(?:mph|miles?\s+per\s+hour)\b',
    re.I,
)

# max_dig_depth — ft + in form: "11 ft 6 in dig depth", "dig depth: 14' 2\""
_SE_DIG_FT_IN_RE = re.compile(
    r'(\d+)\s*(?:ft|\'|feet?)\s*(\d+)\s*(?:in|"|inch(?:es)?)\s*(?:max\s*)?dig(?:ging)?\s*depth'
    r'|(?:max\s*)?dig(?:ging)?\s*depth[:\s]*(\d+)\s*(?:ft|\'|feet?)\s*(\d+)\s*(?:in|"|inch(?:es)?)',
    re.I,
)

# max_dig_depth — ft only: "14.5 ft dig depth", "dig depth: 14 ft"
_SE_DIG_FT_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:ft|\'|feet?)\s*(?:max\s*)?dig(?:ging)?\s*depth'
    r'|(?:max\s*)?dig(?:ging)?\s*depth[:\s]*(\d+(?:\.\d+)?)\s*(?:ft|\'|feet?)',
    re.I,
)

# bucket_breakout_lb: "12,000 lbs breakout force", "breakout force: 12,000 lb"
_SE_BREAKOUT_RE = re.compile(
    r'(?:bucket\s+)?breakout\s+(?:force|cap(?:acity)?)[:\s]*(\d[\d,]*)\s*(?:lb|lbs|lbf)?'
    r'|(\d[\d,]*)\s*(?:lb|lbs|lbf)[,\s]+(?:bucket\s+)?breakout\s+(?:force|cap(?:acity)?)',
    re.I,
)

# max_lift_height_ft (telehandler): "55 ft lift height", "max lift height: 55 ft"
_SE_LIFT_HT_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:ft|\'|feet?)\s*(?:(?:max|boom)\s*)?lift\s*height'
    r'|(?:(?:max|boom)\s*)?lift\s*height[:\s]*(\d+(?:\.\d+)?)\s*(?:ft|\'|feet?)',
    re.I,
)

# max_forward_reach_ft (telehandler): "34 ft forward reach", "max forward reach: 34 ft"
_SE_FWD_REACH_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:ft|\'|feet?)\s*(?:(?:forward|fwd|max)\s*reach)'
    r'|(?:(?:forward|fwd|max)\s*reach)[:\s]*(\d+(?:\.\d+)?)\s*(?:ft|\'|feet?)',
    re.I,
)

# track / undercarriage % condition: "tracks 80%", "undercarriage: 70%", "uc @ 85%"
_SE_TRACK_PCT_RE = re.compile(
    r'(?:tracks?|uc|undercarriage)[:\s@]*(\d{2,3})\s*%',
    re.I,
)

# tire % condition: "tires 80%", "tires: 70%"
_SE_TIRE_PCT_RE = re.compile(
    r'tires?[:\s@]*(\d{2,3})\s*%',
    re.I,
)

# financing available: "financing available", "we finance", "financing options"
_SE_FINANCING_RE = re.compile(
    r'\b(?:financing\s+(?:available|options?|offered|ok)|we\s+finance|oac|terms\s+available)\b',
    re.I,
)


def _parse_int(raw: str) -> int:
    """Strip commas and convert to int."""
    return int(raw.replace(",", ""))


def _extract_seller_specs(raw_text: str, eq_type: str = "") -> dict[str, Any]:
    """
    Extract seller-stated spec values from raw listing text using labelled patterns.

    Returns a dict of {canonical_field_name: value} using the same field names
    expected by the scorer schema (e.g. "net_hp", "roc_lb", "max_dig_depth").

    Conservative design: only extracts when a recognizable field label appears
    adjacent to the numeric value. Bare numbers without context are ignored.

    Values are returned in canonical units:
      - weights and forces: int (lbs)
      - flow: float (gpm)
      - depth / height / reach stored in the canonical unit for that field:
          max_dig_depth         → inches (int)
          max_lift_height_ft    → feet (float)
          max_forward_reach_ft  → feet (float)
      - travel speed: float (mph), stored under both travel speed keys
      - percentages: int
      - financing_available: bool
    """
    t    = raw_text
    out: dict[str, Any] = {}

    # ── net_hp ────────────────────────────────────────────────────────────────
    m = _SE_HP_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        out["net_hp"] = float(raw)

    # ── roc_lb ────────────────────────────────────────────────────────────────
    m = _SE_ROC_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        out["roc_lb"] = _parse_int(raw)

    # ── operating_weight_lb ───────────────────────────────────────────────────
    m = _SE_OP_WEIGHT_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        out["operating_weight_lb"] = _parse_int(raw)

    # ── tipping_load_lb ───────────────────────────────────────────────────────
    m = _SE_TIP_LOAD_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        out["tipping_load_lb"] = _parse_int(raw)

    # ── lift_capacity_lb (telehandler / wheel loader) ─────────────────────────
    m = _SE_LIFT_CAP_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        out["lift_capacity_lb"] = _parse_int(raw)

    # ── hydraulic_flow_gpm ────────────────────────────────────────────────────
    # Take the first match only — this is almost always the standard/primary value.
    m = _SE_GPM_RE.search(t)
    if m:
        out["hydraulic_flow_gpm"] = float(m.group(1))

    # ── travel_speed: stored under both speed keys ────────────────────────────
    m = _SE_MPH_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        mph = float(raw)
        out["travel_speed_high_mph"] = mph
        out["travel_speed_mph"]      = mph

    # ── max_dig_depth (in inches) ─────────────────────────────────────────────
    # Try ft+in first, then ft-only
    m = _SE_DIG_FT_IN_RE.search(t)
    if m:
        g = m.groups()
        # Groups: (ft_before, in_before, ft_after, in_after)
        if g[0] is not None and g[1] is not None:
            depth_in = int(g[0]) * 12 + int(g[1])
        else:
            depth_in = int(g[2]) * 12 + int(g[3])
        out["max_dig_depth"] = depth_in
    else:
        m = _SE_DIG_FT_RE.search(t)
        if m:
            raw = next(g for g in m.groups() if g is not None)
            out["max_dig_depth"] = round(float(raw) * 12)

    # ── bucket_breakout_lb ────────────────────────────────────────────────────
    m = _SE_BREAKOUT_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        out["bucket_breakout_lb"] = _parse_int(raw)

    # ── max_lift_height_ft (telehandler) ─────────────────────────────────────
    m = _SE_LIFT_HT_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        out["max_lift_height_ft"] = float(raw)

    # ── max_forward_reach_ft (telehandler) ───────────────────────────────────
    m = _SE_FWD_REACH_RE.search(t)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        out["max_forward_reach_ft"] = float(raw)

    # ── track_pct / tire_pct ─────────────────────────────────────────────────
    m = _SE_TRACK_PCT_RE.search(t)
    if m:
        out["track_pct"] = int(m.group(1))

    m = _SE_TIRE_PCT_RE.search(t)
    if m:
        out["tire_pct"] = int(m.group(1))

    # ── financing_available ───────────────────────────────────────────────────
    if _SE_FINANCING_RE.search(t):
        out["financing_available"] = True

    return out


# ── Feature / attachment → FieldValue boolean helpers ────────────────────────
# Maps feature/attachment label strings (from extract_attachments) to canonical
# scorer field names. These are informational extras and do not currently affect
# spec_completeness (not in critical_fields schema), but are included in the
# FieldValue list for completeness and future use.
_FEATURE_FIELD_MAP: dict[str, str] = {
    "High Flow":         "high_flow",
    "2-Speed":           "two_speed",
    "Ride Control":      "ride_control",
    "Backup Camera":     "backup_camera",
    "Enclosed Cab":      "cab_enclosed",
    "Cab":               "cab_present",
    "A/C":               "has_ac",
    "Auxiliary Hydraulics": "aux_hydraulics",
    "Pilot Controls":    "pilot_controls",
}

_ATTACHMENT_FIELD_MAP: dict[str, str] = {
    "Hydraulic Thumb":  "thumb",
    "Manual Thumb":     "thumb",
    "Thumb":            "thumb",
    "Quick Coupler":    "quick_attach",
    "Hydraulic Coupler":"quick_attach",
    "Pallet Forks":     "forks_included",
    "Tooth Bucket":     "bucket_included",
    "Smooth Bucket":    "bucket_included",
    "Grading Bucket":   "bucket_included",
    "Bucket":           "bucket_included",
}


# Maps equipment_type → undercarriage family for scorer input
_UNDERCARRIAGE_FAMILY: dict[str, str] = {
    "skid_steer":           "wheeled",
    "compact_track_loader": "tracked",
    "mini_excavator":       "tracked",
    "excavator":            "tracked",
    "wheel_loader":         "wheeled",
    "telehandler":          "wheeled",
    "backhoe_loader":       "wheeled",
    "dozer":                "tracked",
    "crawler_dozer":        "tracked",
}


def _build_scorer_input(
    parsed:              dict,
    resolved_machine:    dict | None,
    raw_text:            str  = "",
    photo_count:         int  = 0,
    eq_type_fallback:    str  = "",
    has_walkaround_video: bool = False,
    has_spec_sheet_pdf:   bool = False,
) -> ListingInput:
    """
    Translate MTM runtime data into a ListingInput for mtm_scorer.score().

    Merges three sources into a unified FieldValue list, with priority:
      1. Registry-resolved (safe)           — confidence 1.0
      2. Seller-stated corroborating a      — confidence 0.7 (upgrades requires_confirm)
         requires_confirm field
      3. Seller-stated only (no registry)   — confidence 0.7
      4. Registry requires_confirm only     — confidence 0.5

    For spec_completeness, any field with confidence >= 0.3 counts as present.
    This means seller-stated specs give listing credit even when no registry
    match exists.

    Field confidence mapping (registry path)
    -----------------------------------------
    - confidence=1.0  safe_for_injection=True, not in requires_confirm
    - confidence=0.7  safe_for_injection=False (low match confidence)
    - confidence=0.5  field is in requires_confirm list

    Known gap: individual registry field_confidence (HIGH/MEDIUM/LOW) is not
    yet propagated through the resolver output. All resolved fields share the
    same global confidence based on match quality.

    eq_type_fallback is used when parsed["equipment_type"] is absent (alias
    matcher did not fire) but the registry lookup succeeded and returned a type.
    """
    eq_type = (parsed.get("equipment_type") or "").lower() or eq_type_fallback.lower()

    # ── Step 1: Registry-resolved fields ──────────────────────────────────────
    # keyed by field name; resolved fields have higher confidence than seller-stated
    fv_map: dict[str, FieldValue] = {}
    requires_confirm_list: list[str] = []
    safe_for_injection = True

    if resolved_machine:
        resolved_specs   = resolved_machine.get("resolved_specs")   or {}
        requires_confirm_list = resolved_machine.get("requires_confirm") or []
        safe_for_injection    = resolved_machine.get("safe_for_listing_injection", True)
        base_conf             = 1.0 if safe_for_injection else 0.7

        for name, value in resolved_specs.items():
            if value is None:
                continue
            conf   = 0.5 if name in requires_confirm_list else base_conf
            source = "requires_confirm" if name in requires_confirm_list else "registry_resolved"
            fv_map[name] = FieldValue(name=name, value=value, confidence=conf, source=source)

    # ── Step 2: Seller-stated specs from raw listing text ─────────────────────
    seller_specs = _extract_seller_specs(raw_text, eq_type) if raw_text else {}

    for name, value in seller_specs.items():
        existing = fv_map.get(name)
        if existing is None:
            # Field not in registry at all — add as seller-stated
            fv_map[name] = FieldValue(
                name=name, value=value, confidence=0.7, source="seller_stated"
            )
        elif existing.confidence < 0.7:
            # Registry has it at requires_confirm (0.5) — seller explicit is more
            # direct evidence; upgrade confidence to 0.7
            fv_map[name] = FieldValue(
                name=name, value=value, confidence=0.7,
                source="seller_stated_corroborated"
            )
        # else: registry has it at >= 0.7 — keep registry value (OEM > seller claim)

    # ── Step 3: Feature / attachment boolean FieldValues ─────────────────────
    # These do not currently affect spec_completeness (not in critical_fields)
    # but are included for completeness and future scoring use.
    features    = parsed.get("features")    or []
    attachments = parsed.get("attachments") or []
    for label in features:
        fname = _FEATURE_FIELD_MAP.get(label)
        if fname and fname not in fv_map:
            fv_map[fname] = FieldValue(name=fname, value=True,
                                       confidence=0.9, source="parsed_feature")
    for label in attachments:
        fname = _ATTACHMENT_FIELD_MAP.get(label)
        if fname and fname not in fv_map:
            fv_map[fname] = FieldValue(name=fname, value=True,
                                       confidence=0.9, source="parsed_attachment")

    return ListingInput(
        equipment_type       = eq_type,
        undercarriage_family = _UNDERCARRIAGE_FAMILY.get(eq_type),
        fields               = list(fv_map.values()),
        photo_count          = photo_count,
        has_walkaround_video = has_walkaround_video,
        has_spec_sheet_pdf   = has_spec_sheet_pdf,
        # Identity signals
        has_year       = parsed.get("year")   is not None,
        has_make       = bool(parsed.get("make")),
        has_model      = bool(parsed.get("model")),
        # Condition / quality signals
        has_hours      = parsed.get("hours")  is not None,
        has_condition  = bool(parsed.get("condition")),
        has_features   = bool(features),
        has_attachments= bool(attachments),
        has_notes      = bool(parsed.get("notes")),
        # Commercial signals
        has_price      = bool(parsed.get("price_value")),
        has_location   = bool(parsed.get("location")),
        has_contact    = bool(parsed.get("contact")),
        # Resolver quality flags
        safe_for_injection = safe_for_injection,
        requires_confirm   = requires_confirm_list,
    )


def _match_method_to_type(method: str) -> MatchType:
    """Map lookup_machine match_method → spec_resolver MatchType."""
    if method in ("exact", "slug_match"):
        return MatchType.EXACT
    if method == "manufacturer_only":
        return MatchType.MANUFACTURER_ONLY
    return MatchType.FAMILY   # fuzzy and unknown → family-level


def _normalize_registry_record(record: dict, category: str) -> dict:
    """
    Translate a raw registry record into the shape RegistryEntry.from_dict expects.

    Fixes two classes of mismatch:
      1. Top-level key renames:
           manufacturer   → mfr
           equipment_type → category
           years_supported.start/end → year_range [lo, hi]
           model_family/model → family
           field_behavior (singular) → field_behaviors (plural)
      2. specs key renames (via _SPEC_KEY_MAP):
           horsepower_hp → net_hp, etc.
           field_behavior keys are remapped by the same table.
    """
    # Translate spec keys (and apply any required value transforms)
    translated_specs: dict = {}
    for k, v in (record.get("specs") or {}).items():
        canonical_key = _SPEC_KEY_MAP.get(k, k)
        # Fields whose source unit is feet must be converted to inches so that
        # normalize_dig_depth() treats the value correctly (>30 → inches path).
        if k in _SPEC_FT_TO_IN_FIELDS and isinstance(v, (int, float)):
            v = v * 12
        translated_specs[canonical_key] = v

    # Translate field_behavior → field_behaviors with the same key renames
    raw_behaviors = record.get("field_behaviors") or record.get("field_behavior") or {}
    translated_behaviors: dict = {}
    for k, v in raw_behaviors.items():
        translated_behaviors[_SPEC_KEY_MAP.get(k, k)] = v

    # year_range from years_supported — use `or` fallback so explicit null values
    # in the registry (e.g. "end": null for still-produced models) get defaults.
    ys = record.get("years_supported") or {}
    year_range = [ys.get("start") or 2000, ys.get("end") or 2030]

    return {
        "family":           record.get("model_family") or record.get("model", "unknown"),
        "mfr":              record.get("manufacturer", ""),
        "category":         category,
        "year_range":       year_range,
        "specs":            translated_specs,
        "family_ranges":    record.get("family_ranges", {}),
        "variants":         record.get("variants", []),
        "field_behaviors":  translated_behaviors,
        "option_overrides": record.get("option_overrides", {}),
        "year_overrides":   record.get("year_overrides", {}),
    }


def _run_spec_resolver(
    raw_text: str,
    parsed: dict,
    registry_result: dict,
    confidence: float,
) -> dict | None:
    """
    Call spec_resolver.resolve() immediately after safe_lookup_machine succeeds.

    Translates the lookup_machine result dict into a ResolverInput, runs the
    full per-field resolution framework, and returns the output as a plain dict:
        {
            "resolved_specs":             dict,
            "requires_confirm":           list[str],
            "ui_hints":                   dict,
            "warnings":                   list[dict],
            "overall_resolution_status":  str,
            "safe_for_listing_injection": bool,
        }
    Returns None on any error so the caller can fall back gracefully.
    """
    full_record = registry_result.get("full_record") or {}
    print(f"[MTM DEBUG SR] full_record keys   : {list(full_record.keys()) if full_record else 'EMPTY'}")
    if not full_record:
        print("[MTM DEBUG SR] EXIT 1: full_record empty")
        return None

    eq_type  = registry_result.get("equipment_type") or parsed.get("equipment_type") or ""
    category = _eq_type_to_category(eq_type)
    method   = registry_result.get("match_method", "exact")
    print(f"[MTM DEBUG SR] eq_type={eq_type!r}  category={category!r}  method={method!r}")

    # Normalize raw registry record into the shape RegistryEntry.from_dict expects
    normalized = _normalize_registry_record(full_record, category)
    print(f"[MTM DEBUG SR] normalized keys    : {list(normalized.keys())}")
    print(f"[MTM DEBUG SR] normalized specs   : {normalized.get('specs')}")
    print(f"[MTM DEBUG SR] match confidence   : {confidence}")

    try:
        inp = ResolverInput(
            raw_listing_text          = raw_text,
            parsed_manufacturer       = parsed.get("make") or "",
            parsed_model              = parsed.get("model") or "",
            parsed_category           = category,
            detected_modifiers        = [],
            extracted_numeric_claims  = {},
            registry_match            = normalized,
            registry_match_confidence = confidence,
            match_type                = _match_method_to_type(method),
        )
        out = _spec_resolve(inp)
    except Exception as exc:
        import traceback as _tb
        print(f"[MTM DEBUG SR] EXIT 2: exception — {exc}")
        _tb.print_exc()
        return None

    return {
        "equipment_type":             eq_type,
        "resolved_specs":             out.resolved_specs,
        "requires_confirm":           out.requires_confirm,
        "ui_hints":                   out.ui_hints,
        "warnings":                   [w.to_dict() for w in out.warnings],
        "overall_resolution_status":  out.overall_resolution_status.value,
        "safe_for_listing_injection": out.safe_for_listing_injection,
    }


# ── Make-token check for alias results ───────────────────────────────────────
# Aliases in MODEL_REGISTRY include both make+model forms ('bobcat t770',
# 'jd310') and bare model forms ('svl95-2s', 'tl12r2', 'kx040-4').
# Only the former count as "explicit" make presence for Tier 1 gating.

_MAKE_TOKENS_NORM: frozenset[str] = frozenset({
    # stripped to alphanumeric per normalize() rules
    "cat", "caterpillar",
    "bobcat",
    "kubota",
    "jd", "deere", "johndeere",
    "case",
    "takeuchi",
    "komatsu",
    "volvo",
    "doosan",
    "hitachi",
    "jcb",
    "kobelco",
    "newholland", "nh",
    "hyundai",
    "asv",
    "skytrak",
    "jlg",
    "genie",
    "manitou",
    "linkbelt",
    "yanmar",
    "liugong",
    "sany",
    "gradall",
})


def _alias_has_make_token(matched_alias: str, manufacturer: str) -> bool:
    """
    Return True if the matched alias string contains a recognizable make token,
    meaning the make name was actually present in the listing text.

    'bobcat t770' → True  (bobcat is a make token)
    'jd310'       → True  (jd is a make token)
    'svl95-2s'    → False (no make token — pure model string)
    'tl12r2'      → False (no make token)
    """
    norm = re.sub(r'[^a-z0-9]', '', matched_alias.lower())
    # Check canonical manufacturer name
    if re.sub(r'[^a-z0-9]', '', manufacturer.lower()) in norm:
        return True
    # Check known make abbreviations
    for token in _MAKE_TOKENS_NORM:
        if token and norm.startswith(token):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# PARSE LISTING  (regex fields + frozen module enrichment)
# ══════════════════════════════════════════════════════════════════════════════

def safe_parse_listing(raw_text: str) -> dict:
    """
    Extracts structured fields from raw listing text.

    Field sources:
      year, hours, location, contact, condition  — regex
      price_value, price_is_obo                 — extract_price()
      attachments, features                     — extract_attachments()
      make, model, equipment_type               — match_known_model() (gap-fill only)

    make_source values:
      "explicit" — make name appeared in the listing text (Tier 1 eligible)
      "inferred" — make was derived from a bare model token (Tier 1 ineligible)
      None       — make not detected
    """
    try:
        result: dict[str, Any] = dict.fromkeys(
            ["year", "make", "model", "equipment_type",
             "hours", "price_value", "price_is_obo",
             "location", "contact", "condition", "notes",
             "attachments", "features"]
        )
        # Tracks whether make came from explicit text (regex/alias) vs inference.
        # Tier 1 spec injection requires make_source == "explicit".
        result["make_source"] = None

        t = raw_text

        # Year ─────────────────────────────────────────────────────────────────
        m = re.search(r'\b(19[89]\d|20[0-3]\d)\b', t)
        if m:
            result["year"] = int(m.group())

        # Hours ────────────────────────────────────────────────────────────────
        m = re.search(r'(\d[\d,]*)\s*(?:hrs?\.?|hours?)', t, re.I)
        if m:
            result["hours"] = int(m.group(1).replace(",", ""))

        # Price — frozen module ────────────────────────────────────────────────
        price_val = extract_price(t)
        result["price_value"]  = price_val
        result["price_is_obo"] = bool(re.search(r'\bobo\b', t, re.I))

        # Location ─────────────────────────────────────────────────────────────
        # Pattern 1: explicit prefix — "located [in]" or "location:"
        # "in" is now optional so "Located Peoria IL" is captured as well as
        # the existing "Located in central Ohio" form.
        m = re.search(
            r'(?:located?\s+(?:in\s+)?|location[:\s]+)\s*([A-Za-z][A-Za-z\s,]{2,40}?)(?:[.\n]|$)',
            t, re.I
        )
        if m:
            result["location"] = m.group(1).strip().rstrip(",")

        # Pattern 2: bare "City ST" — Title-case city + 2-letter US state code.
        # Requires city to start uppercase then have lowercase chars so model
        # tokens like "320GC" or all-caps words never match.
        if not result["location"]:
            _US_ST = (
                r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME'
                r'|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA'
                r'|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)'
            )
            m = re.search(rf'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+({_US_ST})\b', t)
            if m:
                result["location"] = f"{m.group(1)} {m.group(2)}"

        # Pattern 3: directional qualifier + capitalized place name
        # Catches "central Ohio", "near Columbus", "northern Illinois".
        if not result["location"]:
            m = re.search(
                r'\b((?:central|northern|southern|eastern|western|near'
                r'|northeast|northwest|southeast|southwest)\s+[A-Z][a-z]+)\b',
                t, re.I
            )
            if m:
                result["location"] = m.group(1)

        # Contact ──────────────────────────────────────────────────────────────
        m = re.search(r'\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}', t)
        if m:
            result["contact"] = m.group().strip()

        # Condition ────────────────────────────────────────────────────────────
        # More-specific dealer assertions listed before generic single words so
        # "clean machine" wins over the bare "good" that follows.
        for kw in [
            "very clean machine", "clean machine", "very clean",
            "well maintained", "well-maintained", "serviced regularly",
            "runs strong", "no leaks", "no smoke",
            "like new", "very good", "runs great", "excellent",
            "good condition", "good", "fair", "needs work",
            "project machine", "poor",
        ]:
            if re.search(rf'\b{re.escape(kw)}\b', t, re.I):
                result["condition"] = kw.title()
                break

        # Make / Model — regex baseline ────────────────────────────────────────
        known_makes = [
            "Caterpillar", "CAT", "John Deere", "Komatsu", "Bobcat",
            "Case", "Volvo", "Doosan", "Hitachi", "JCB", "Kubota",
            "Takeuchi", "Liebherr", "Terex", "New Holland", "Hyundai",
            "Kobelco", "Genie", "JLG", "Skytrak", "Manitou", "Gradall",
            "Link-Belt", "Sany", "LiuGong", "Yanmar",
            "JD", "Deere",
            "ASV", "Gehl", "Toro",
        ]
        for make in known_makes:
            if re.search(rf'\b{re.escape(make)}\b', t, re.I):
                result["make"] = make
                result["make_source"] = "explicit"
                # Model-token blocklist: type/category words that follow a make
                # name but are not model numbers. Without this, "cat skid steer"
                # stores model=SKID, "jcb telehandler" stores model=TELEHANDLER, etc.
                _MODEL_BLOCKLIST = {
                    "MINI", "EXCAVATOR", "EXCAVTOR",
                    "SKID", "STEER",
                    "CTL", "TRACK", "LOADER",
                    "TELEHANDLER", "BACKHOE",
                    "DOZER", "CRAWLER",
                    "COMPACT",
                }
                m2 = re.search(
                    rf'\b{re.escape(make)}\s+([A-Z0-9][A-Za-z0-9\-]{{1,20}})',
                    t, re.I
                )
                if m2 and m2.group(1).upper() not in _MODEL_BLOCKLIST:
                    result["model"] = m2.group(1).upper()
                elif make in {"John Deere", "JD", "Deere"}:
                    # For Deere listings, category words (e.g. "skid steer",
                    # "compact track loader") may appear between make and model.
                    # Allow up to 4 pure-alpha words before the model token.
                    # Require both a digit and a letter so raw numbers (prices,
                    # hours) are never captured as a model.
                    m3 = re.search(
                        rf'\b{re.escape(make)}\b(?:\s+[A-Za-z]+){{1,4}}\s+([A-Z0-9][A-Za-z0-9\-]{{1,10}})',
                        t, re.I
                    )
                    if m3:
                        candidate = m3.group(1).upper()
                        if (candidate not in _MODEL_BLOCKLIST
                                and re.search(r'\d', candidate)
                                and re.search(r'[A-Za-z]', candidate)):
                            result["model"] = candidate
                break

        # Normalise abbreviated/alternate make names to canonical display form
        _MAKE_CANONICAL = {
            "CAT":         "Caterpillar",
            "CATERPILLAR": "Caterpillar",
            "JOHN DEERE":  "John Deere",
            "JD":          "John Deere",
            "DEERE":       "John Deere",
            "SKYTRAK":     "SkyTrak",
        }
        if result.get("make"):
            result["make"] = _MAKE_CANONICAL.get(
                result["make"].upper(), result["make"]
            )

        # Make / Model — alias enrichment (fills gaps, does not overwrite) ─────
        # INVARIANT: alias must NEVER overwrite a model already detected by regex.
        # Registry lookups are allowed only when the field is absent.
        alias = match_known_model(t)
        if alias:
            if not result.get("make"):
                result["make"] = alias["manufacturer"]
                # make_source is "explicit" only if the matched alias contains a
                # recognizable make token. Bare model aliases like 'svl95-2s' or
                # 'tl12r2' do NOT count as explicit — the make name was not in the text.
                result["make_source"] = (
                    "explicit"
                    if _alias_has_make_token(alias["matched_alias"], alias["manufacturer"])
                    else "inferred"
                )
            if not result.get("model"):
                result["model"] = alias["model"]
            # equipment_type not produced by regex — always store it
            result["equipment_type"] = alias["equipment_type"]

        # Bare model token scan — fires when neither regex nor alias found a model.
        # Gap-fill only: never overwrites a model or make already detected.
        # make_source stays "inferred" — bare model alone does NOT qualify for Tier 1.
        if not result.get("model"):
            bare_model, bare_mfr, bare_eq = scan_bare_model_tokens(t)
            if bare_model:
                result["model"] = bare_model
                if not result.get("make"):
                    result["make"] = bare_mfr
                    result["make_source"] = "inferred"
                if not result.get("equipment_type"):
                    result["equipment_type"] = bare_eq

        # Make inference from detected model — fires when model was detected by
        # regex or bare scan but make is still missing.
        # Exact registry match only — no fuzzy lookup.
        # make_source stays "inferred" — does NOT qualify for Tier 1.
        if result.get("model") and not result.get("make"):
            inferred_make, inferred_type = lookup_make_for_model(result["model"])
            if inferred_make:
                result["make"] = inferred_make
                result["make_source"] = "inferred"
                if not result.get("equipment_type"):
                    result["equipment_type"] = inferred_type

        # Attachments & Features — frozen module ──────────────────────────────
        att_result = extract_attachments(t)
        result["attachments"] = att_result.get("attachments", [])
        result["features"]    = att_result.get("features", [])

        return result

    except Exception as exc:
        print(f"[MTM] parse_listing error: {exc}")
        return dict.fromkeys(
            ["year", "make", "model", "equipment_type",
             "hours", "price_value", "price_is_obo",
             "location", "contact", "condition", "notes",
             "attachments", "features"]
        )


# ══════════════════════════════════════════════════════════════════════════════
# ADAPTER WRAPPERS
# ══════════════════════════════════════════════════════════════════════════════

def safe_lookup_machine(parsed: dict) -> tuple[dict | None, float]:
    """
    Tier 1 spec injection gate.

    Requirements for spec injection:
      - make present AND make_source == "explicit" (appeared in listing text)
      - model present
      - registry match method is 'exact' or 'slug_match', confidence >= 0.9

    Bare model inference (make_source == "inferred") does NOT qualify.
    "t770" alone → no specs. "bobcat t770" → specs allowed.
    """
    make        = parsed.get("make") or ""
    model       = parsed.get("model") or ""
    make_source = parsed.get("make_source") or ""

    # Gate: make must be explicit (from listing text) AND model must be present
    if not make or not model or make_source != "explicit":
        return None, 0.0

    try:
        result = lookup_machine(manufacturer=make, model=model)
    except Exception as exc:
        print(f"[MTM] lookup_machine error: {exc}")
        return None, 0.0

    if not result.get("match"):
        return None, 0.0

    method = result.get("match_method", "")
    conf   = result.get("confidence", 0.0)

    # Tier 1: only exact or high-confidence slug matches qualify
    if method not in ("exact", "slug_match") or conf < 0.9:
        return None, 0.0

    return result, conf


def format_output_response(
    cleaned_listing: str,
    parsed: dict,
    added_specs: dict | None,
    confidence_note: str | None,
    spec_level: str = "essential",
    output_assets: dict | None = None,
    display_specs: list | None = None,
    scoring: dict | None = None,
    fix_my_listing: dict | None = None,
    confirm_required: dict | None = None,
    rewritten_listing: dict | None = None,
) -> dict:
    """Shapes final dict → FixListingResponse in app.py."""
    # Build the parsed_machine display dict — convert price fields to display string
    display = {}
    for k, v in parsed.items():
        if v is None or v == [] or v is False:
            continue
        if k == "hours" and v:
            display["machine_hours"] = v   # structured hours field for API consumers
        elif k == "price_value" and v:
            price_str = f"${v:,}"
            if parsed.get("price_is_obo"):
                price_str += " OBO"
            display["price"] = price_str
        elif k == "price_is_obo":
            continue   # already folded into price above
        elif k == "attachments" and v:
            display["attachments"] = ", ".join(v)
        elif k == "features" and v:
            display["features"] = ", ".join(v)
        else:
            display[k] = v

    resolver_data = added_specs or {}
    return {
        "cleaned_listing":             cleaned_listing,
        "parsed_machine":              display,
        "spec_level":                  spec_level,
        "display_specs":               display_specs,
        "output_assets":               output_assets,
        "resolved_specs":              resolver_data.get("resolved_specs"),
        "requires_confirm":            resolver_data.get("requires_confirm"),
        "ui_hints":                    resolver_data.get("ui_hints"),
        "warnings":                    resolver_data.get("warnings"),
        "overall_resolution_status":   resolver_data.get("overall_resolution_status"),
        "safe_for_listing_injection":  resolver_data.get("safe_for_listing_injection"),
        "confidence_note":             confidence_note,
        "scoring":                     scoring,
        "fix_my_listing":              fix_my_listing,
        "confirm_required":            confirm_required,
        "rewritten_listing":           rewritten_listing,
        "error":                       None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def build_spec_sheet_entries(
    resolved_specs: dict,
    ui_hints: dict,
    equipment_type: str = "",
) -> list[tuple[str, str]]:
    """
    Public helper — returns spec sheet entries as (label, value) tuples at
    TECHNICAL tier, suitable for passing directly to generate_spec_sheet().
    """
    items = _build_display_specs(
        resolved_specs = resolved_specs,
        ui_hints       = ui_hints,
        spec_level     = "technical",
        equipment_type = equipment_type,
    )
    return [(item["label"], item["value"]) for item in items]


# ── Confirm-required field metadata ───────────────────────────────────────────
# Union of critical_fields across all equipment types in mtm_scoring_schema.json.
# Confirming any of these directly improves spec_completeness score.
_HIGH_IMPACT_CONFIRM_FIELDS: frozenset = frozenset({
    "net_hp", "roc_lb", "operating_weight_lb", "tipping_load_lb",
    "hydraulic_flow_gpm", "travel_speed_mph", "travel_speed_high_mph",
    "max_dig_depth", "bucket_breakout_lb", "lift_capacity_lb",
    "max_lift_height_ft", "max_forward_reach_ft",
})

# Fields whose value is option/package-dependent; reason text differs.
_PACKAGE_DEPENDENT_CONFIRM_FIELDS: frozenset = frozenset({
    "hydraulic_flow_gpm", "hi_flow_gpm",
})


def _confirm_field_label(field: str) -> str:
    """Human-readable label for a requires_confirm field, reusing _SPEC_DISPLAY_META."""
    meta = _SPEC_DISPLAY_META.get(field)
    if meta:
        unit = meta.get("unit", "")
        return f"{meta['label']} ({unit})" if unit else meta["label"]
    return field.replace("_", " ").title()


def _confirm_reason(field: str, resolution_status: str, safe_for_injection: bool) -> str:
    """Short dealer-facing explanation of why this field needs confirmation."""
    if field in _PACKAGE_DEPENDENT_CONFIRM_FIELDS:
        return "Spec varies by installed option — confirm which applies to your machine"
    if resolution_status == "family":
        return "Family-level match — verify this spec applies to your specific machine variant"
    if not safe_for_injection:
        return "Match confidence below auto-confirm threshold — verify before publishing"
    if resolution_status == "exact":
        return "Registry match found but below auto-confirm confidence — verify before publishing"
    return "Spec requires verification before use in listing"


def build_confirm_required(
    requires_confirm:           list,
    resolved_specs:             dict,
    overall_resolution_status:  str,
    safe_for_listing_injection: bool,
) -> dict:
    """
    Build the dealer-facing confirm_required block from spec resolver output.

    ``requires_confirm`` is the sorted list of field name strings produced by the
    spec resolver (_collect_requires_confirm).  For each field this adds:
      label           : human-readable name (from _SPEC_DISPLAY_META)
      reason          : why confirmation is needed (resolution_status-aware)
      suggested_value : the resolver-injected value, or null if not yet injected
      category        : "core_spec" | "features"
      priority        : "high" (scoring-critical) | "medium" (supplemental)

    Fields are sorted: high priority first, then alphabetical within each tier.

    Returns {"count": 0, "fields": []} when requires_confirm is empty or None.
    """
    confirm_list = requires_confirm or []
    if not confirm_list:
        return {"count": 0, "fields": []}

    _PRIO_ORDER = {"high": 0, "medium": 1}
    fields_out: list[dict] = []

    for field in confirm_list:
        category = "features" if field in _PACKAGE_DEPENDENT_CONFIRM_FIELDS else "core_spec"
        priority = "high"     if field in _HIGH_IMPACT_CONFIRM_FIELDS        else "medium"

        fields_out.append({
            "field":           field,
            "label":           _confirm_field_label(field),
            "reason":          _confirm_reason(
                                   field, overall_resolution_status, safe_for_listing_injection
                               ),
            "suggested_value": (resolved_specs or {}).get(field),
            "category":        category,
            "priority":        priority,
        })

    fields_out.sort(key=lambda f: (_PRIO_ORDER.get(f["priority"], 9), f["field"]))
    return {"count": len(fields_out), "fields": fields_out}


def build_rewritten_listing(
    listing_data: dict,
    added_specs: dict | None,
    spec_level: str = "essential",
    generated_listing_text: str = "",
) -> dict:
    """
    Produce a structured, dealer-facing listing rewrite from MTM runtime data.

    Uses only facts already present in the pipeline — never invents values.
    Fields in requires_confirm are treated as unverified: they are excluded
    from the facebook variant's top specs and footnoted in dealer_site copy.

    ``generated_listing_text`` is the pre-computed plain-text output of
    _stub_generate_listing_text(); it is reused as platform_variant.default
    to avoid duplicate generation.

    Return shape
    ------------
    {
        "title":             str,
        "description":       str,
        "spec_bullets":      list[str],
        "condition_summary": str | None,
        "financing_cta":     str,
        "platform_variant": {
            "default":     str,   # balanced plain-text, same as listing.txt
            "facebook":    str,   # punchy, short, social-optimised
            "dealer_site": str,   # formal paragraph + full spec section + CTA
        },
    }
    """
    year        = listing_data.get("year")           or ""
    make        = listing_data.get("make")           or ""
    model       = listing_data.get("model")          or ""
    eq_type     = listing_data.get("equipment_type") or ""
    hours       = listing_data.get("hours")
    price_int   = listing_data.get("price_value")
    price_obo   = listing_data.get("price_is_obo", False)
    location    = listing_data.get("location")
    contact     = listing_data.get("contact")
    condition   = listing_data.get("condition")
    notes       = listing_data.get("notes")
    attachments = listing_data.get("attachments") or []
    features    = listing_data.get("features")    or []

    # Fields the resolver flagged for confirmation — treat as unverified
    rc_set: set[str] = set((added_specs or {}).get("requires_confirm") or [])

    # ── Title ─────────────────────────────────────────────────────────────────
    # Rule: year + make + model + equipment type label.
    # Equipment type is always included when known — it improves searchability
    # and makes the listing immediately classifiable without reading the body.
    type_label = eq_type.replace("_", " ").title() if eq_type else ""
    title_parts = [str(p) for p in [year, make, model] if p]
    if type_label:
        title_parts.append(type_label)
    title = " ".join(title_parts) or "Heavy Equipment for Sale"

    # ── Spec bullets ──────────────────────────────────────────────────────────
    rs       = (added_specs or {}).get("resolved_specs") or {}
    ui_hints = (added_specs or {}).get("ui_hints")       or {}
    spec_lvl = _normalize_tier(spec_level)
    spec_bullets: list[str] = (
        _build_spec_bullets(rs, ui_hints, spec_lvl, eq_type) if rs else []
    )

    # Confirmed-only bullets: used by facebook to prefer verified specs.
    # Falls back to all spec_bullets when everything is unconfirmed.
    if rs and rc_set:
        all_display = _build_display_specs(rs, ui_hints, spec_lvl, eq_type)
        confirmed_bullets = [
            f"{item['label']}: {item['value']}"
            for item in all_display
            if item["key"] not in rc_set
        ]
        fb_spec_bullets = confirmed_bullets[:3] or spec_bullets[:3]
    else:
        fb_spec_bullets = spec_bullets[:3]

    # ── Price string ──────────────────────────────────────────────────────────
    if price_int:
        price_str = f"${price_int:,}"
        if price_obo:
            price_str += " OBO"
    else:
        price_str = None

    # ── Condition summary ─────────────────────────────────────────────────────
    cond_parts: list[str] = []
    if hours is not None:
        cond_parts.append(f"{hours:,} hours")
    if condition:
        cond_parts.append(condition)
    condition_summary = " — ".join(cond_parts) or None

    # ── Financing CTA ─────────────────────────────────────────────────────────
    if price_str:
        financing_cta = f"Asking {price_str}. Financing available — call for details."
    else:
        financing_cta = "Call or message for current pricing and financing options."

    # ── Description paragraph (shared base) ──────────────────────────────────
    # Kept lean: identity + hours, condition/notes, then commercial.
    # Features/attachments are omitted here — they get their own sections in
    # dealer_site and are summarised inline in facebook.
    desc_parts: list[str] = []

    id_tokens: list[str] = []
    if title != "Heavy Equipment for Sale":
        id_tokens.append(title)
    if hours is not None:
        id_tokens.append(f"{hours:,} hours")
    if id_tokens:
        desc_parts.append(", ".join(id_tokens) + ".")

    if condition or notes:
        cond_text = " ".join(filter(None, [condition, (notes or "").strip()]))
        desc_parts.append(cond_text.capitalize().rstrip(".") + ".")

    if price_str and location:
        desc_parts.append(f"Asking {price_str}, located in {location}.")
    elif price_str:
        desc_parts.append(f"Asking {price_str}.")
    elif location:
        desc_parts.append(f"Located in {location}.")

    description = " ".join(desc_parts) or title

    # ── Platform variants ─────────────────────────────────────────────────────

    # default — reuse pre-computed text verbatim (no duplicate generation)
    default_text = generated_listing_text or _stub_generate_listing_text(
        listing_data, added_specs, spec_level
    )

    # ── facebook ──────────────────────────────────────────────────────────────
    # Structure:
    #   [title]
    #   [condition summary]
    #   (blank)
    #   [top confirmed spec bullets]
    #   [features | attachments compact line]
    #   (blank)
    #   [Asking PRICE — LOCATION]   or just price or just location
    #   [Call or DM: CONTACT]
    #   (blank)
    #   [hashtags]
    fb: list[str] = []
    fb.append(title)
    if condition_summary:
        fb.append(condition_summary)

    if fb_spec_bullets or features or attachments:
        fb.append("")
        for b in fb_spec_bullets:
            fb.append(f"• {b}")

        # Features + attachments on one compact line, joined with " | "
        extras: list[str] = []
        if features:
            extras.append(", ".join(features))
        if attachments:
            extras.append(", ".join(attachments))
        if extras:
            fb.append(" | ".join(extras))

    fb.append("")
    if price_str and location:
        fb.append(f"Asking {price_str} — {location}")
    elif price_str:
        fb.append(f"Asking {price_str}")
    elif location:
        fb.append(location)

    if contact:
        fb.append(f"Call or DM: {contact}")

    fb.append("")
    fb_tags: list[str] = []
    if make:
        fb_tags.append(f"#{re.sub(r'[^a-z0-9]', '', make.lower())}")
    if model:
        fb_tags.append(f"#{re.sub(r'[^a-z0-9]', '', model.lower())}")
    fb_tags += ["#heavyequipment", "#usedequipment", "#forsale"]
    fb.append(" ".join(fb_tags))

    facebook_text = "\n".join(fb)

    # ── dealer_site ───────────────────────────────────────────────────────────
    # Structure:
    #   [title]
    #   (blank)
    #   [description paragraph — identity + hours + condition + price/location]
    #   (blank)
    #   Specifications
    #   [all spec bullets]
    #   (blank — if features present)
    #   Features / Included Attachments sections
    #   (blank)
    #   Condition
    #   [hours + condition bullets]
    #   (blank)
    #   Listing Details
    #   [price / location / contact lines]
    #   (blank)
    #   [financing_cta — if price present]
    #   (blank — if rc_set non-empty)
    #   [unverified spec note]
    ds: list[str] = []
    ds.append(title)
    ds.append("")
    ds.append(description)

    if spec_bullets:
        ds.append("")
        ds.append("Specifications")
        for b in spec_bullets:
            ds.append(f"• {b}")

    if features:
        ds.append("")
        ds.append("Features")
        for f in features:
            ds.append(f"• {f}")

    if attachments:
        ds.append("")
        ds.append("Included Attachments")
        for a in attachments:
            ds.append(f"• {a}")

    # Condition section — only when hours or condition is present
    if hours is not None or condition:
        ds.append("")
        ds.append("Condition")
        if hours is not None:
            ds.append(f"• {hours:,} hours")
        if condition:
            ds.append(f"• {condition.capitalize()}")

    # Listing details section
    has_commercial = any([price_str, location, contact])
    if has_commercial:
        ds.append("")
        ds.append("Listing Details")
        if price_str:
            ds.append(f"Asking Price: {price_str}")
        if location:
            ds.append(f"Location: {location}")
        if contact:
            ds.append(f"Contact: {contact}")

    if price_str:
        ds.append("")
        ds.append(financing_cta)

    # Flag unverified specs — only when requires_confirm fields exist in the
    # displayed spec bullets (i.e. rc_set overlaps with what was rendered)
    displayed_rc = [f for f in rc_set if any(f in b.lower().replace(" ", "_") for b in spec_bullets)]
    if displayed_rc and spec_bullets:
        ds.append("")
        ds.append("Note: one or more specifications are pending verification and should be confirmed before publishing.")

    dealer_site_text = "\n".join(ds)

    return {
        "title":             title,
        "description":       description,
        "spec_bullets":      spec_bullets,
        "condition_summary": condition_summary,
        "financing_cta":     financing_cta,
        "platform_variant": {
            "default":     default_text,
            "facebook":    facebook_text,
            "dealer_site": dealer_site_text,
        },
    }


def fix_listing_service(
    raw_text: str,
    spec_level:         str  = "essential",
    generate_spec_sheet: bool = True,
    generate_variants:   bool = True,
    generate_package:    bool = True,
) -> dict:
    """
    Full pipeline with Tier 1 spec injection gate.

    Core output (always produced):
        cleaned_listing — formatted listing text

    Optional outputs (controlled by toggles):
        generate_spec_sheet   — build spec_sheet.png from FULL spec data
        generate_variants     — build 4x5 / square / story / landscape PNGs
                                (skipped automatically if generate_spec_sheet=False)
        generate_package      — bundle listing.txt + images into listing_package.zip
                                (ZIP contains only listing.txt when no images exist)

    Tier 1 behavior:
        explicit make + model + registry hit    → inject OEM specs
        explicit make only (no model)           → cleanup only; prompt for model
        no explicit identity                    → cleanup only; prompt for identity
        explicit make+model but no registry hit → cleanup only; no message
    """
    # IMAGE PIPELINE HOOK — Future Enhancement (v2+)
    # When ready: image_notes = analyze_listing_image(image_data: bytes | None)
    # Do not implement in v1. See README > Future Enhancements.

    spec_level = _normalize_tier(spec_level)   # accept legacy quick/dealer/full

    parsed            = safe_parse_listing(raw_text)
    specs, confidence = safe_lookup_machine(parsed)

    # ── Per-request output directory (created once, used by all generators) ──
    session_dir, session_web = _make_session_dir(parsed)

    make        = parsed.get("make") or ""
    model       = parsed.get("model") or ""
    make_source = parsed.get("make_source") or ""

    added_specs:     dict | None = None
    confidence_note: str | None  = None

    if specs is not None:
        pct    = int(confidence * 100)
        method = specs.get("match_method", "")
        # ── spec_resolver replaces direct spec injection ──────────────────────
        added_specs = _run_spec_resolver(raw_text, parsed, specs, confidence)
        confidence_note = (
            f"OEM specs from MTM registry — "
            f"{specs.get('manufacturer')} {specs.get('model')} "
            f"({method} match, {pct}% confidence)"
        )
    elif make_source == "explicit" and not model:
        # Make in text, model missing
        confidence_note = (
            f"Make identified as {make}. "
            "Add model number to include OEM specs."
        )
    elif not make or make_source != "explicit":
        # No explicit identity in listing text
        confidence_note = (
            "Machine identity not detected. "
            "Add make and model number to include OEM specs."
        )
    # make+model explicit but no registry hit → no note; cleanup still works

    listing_data    = _stub_build_listing_data(parsed, added_specs)
    cleaned_listing = _stub_generate_listing_text(listing_data, added_specs, spec_level)

    # ── Canonical equipment type — single resolved value used everywhere below ──
    # Priority: resolver output > listing_data (alias matcher) > parsed (regex) > ""
    # added_specs["equipment_type"] is set from the registry match and is always
    # correct when a registry lookup succeeded.  The other fallbacks cover the case
    # where only listing_data or parsed could carry the type (no registry hit).
    _canonical_eq_type: str = (
        (added_specs.get("equipment_type") if added_specs else None)
        or listing_data.get("equipment_type")
        or parsed.get("equipment_type")
        or ""
    )

    # ── Launch guardrail: minimum technical-spec count before generating spec sheet ──
    # A spec sheet with fewer than N populated fields looks broken, not credible.
    # Count using TECHNICAL tier so the threshold is based on maximum available data,
    # not the user's selected listing level.
    # Thresholds (fields required to generate spec sheet):
    #   SSL / CTL : 6  — less than 6 technical specs = thin listing cleanup only
    #   mini ex   : 5
    #   default   : 6
    _SPEC_SHEET_MIN: dict[str, int] = {
        "skid_steer_loader":    6,
        "compact_track_loader": 6,
        "mini_excavator":       5,
    }
    _eq_spec_key     = _EQ_TYPE_TO_SPEC_KEY.get(
        _canonical_eq_type.lower(), _DEFAULT_SPEC_TYPE
    )
    _sheet_threshold = _SPEC_SHEET_MIN.get(_eq_spec_key, 6)
    _full_spec_count = 0
    _sheet_suppressed = False
    if added_specs and added_specs.get("resolved_specs"):
        _full_spec_count = len(_build_display_specs(
            resolved_specs = added_specs["resolved_specs"],
            ui_hints       = added_specs.get("ui_hints") or {},
            spec_level     = "technical",
            equipment_type = _canonical_eq_type,
        ))
        if _full_spec_count < _sheet_threshold:
            _sheet_suppressed = True
            print(
                f"[MTM] spec_sheet suppressed — only {_full_spec_count} technical specs "
                f"(threshold: {_sheet_threshold} for {_eq_spec_key})"
            )

    # ── Spec sheet — TECHNICAL tier; skipped when toggle is off, no resolved specs,
    #               or technical-spec count is below the launch threshold
    spec_sheet_path:     str  | None = None
    spec_sheet_variants: dict | None = None
    if (generate_spec_sheet
            and added_specs and added_specs.get("resolved_specs")
            and not _sheet_suppressed):
        try:
            _entries  = build_spec_sheet_entries(
                added_specs["resolved_specs"],
                added_specs.get("ui_hints") or {},
                _canonical_eq_type,
            )
            _eq_label = (
                _canonical_eq_type.replace("_", " ").title()
                if _canonical_eq_type else None
            )
            spec_sheet_path = _gen_spec_sheet(
                make           = listing_data.get("make") or "",
                model          = listing_data.get("model") or "",
                year           = listing_data.get("year"),
                equipment_type = _eq_label,
                spec_sheet     = _entries,
                output_path    = os.path.join(session_dir, "spec_sheet.png"),
            )
            if generate_variants:
                spec_sheet_variants = generate_spec_sheet_variants(spec_sheet_path)
        except Exception as exc:
            print(f"[MTM] spec_sheet generation failed: {exc}")

    # ── Listing package ZIP — uses whatever assets exist; skipped when toggle is off
    listing_package_path: str | None = None
    if generate_package:
        listing_package_path = generate_listing_package(
            cleaned_listing     = cleaned_listing,
            spec_sheet_path     = spec_sheet_path,
            spec_sheet_variants = spec_sheet_variants,
            output_path         = os.path.join(session_dir, "listing_package.zip"),
        )

    # ── Build output_assets — all keys always present, null when not generated ─
    _VARIANT_KEYS = ("4x5", "square", "story", "landscape")
    output_assets = {
        "session_id":         session_web.rsplit("/", 1)[-1],
        "base_url":           session_web,
        "spec_sheet":         _asset_url(spec_sheet_path, session_web),
        "variants": {
            k: _asset_url((spec_sheet_variants or {}).get(k), session_web)
            for k in _VARIANT_KEYS
        },
        "listing_package":    _asset_url(listing_package_path, session_web),
        # Coverage metadata — used by frontend to decide whether to show spec sheet CTA
        "spec_coverage": {
            "full_spec_count": _full_spec_count,
            "threshold":       _sheet_threshold,
            "suppressed":      _sheet_suppressed,
        },
    }

    # ── display_specs — pre-formatted, ordered for the selected spec_level ──
    # Single source of truth consumed by: API response, frontend panel, FB post.
    # resolved_specs is kept in the response too for raw access / debugging.
    display_specs: list | None = None
    if added_specs and added_specs.get("resolved_specs"):
        display_specs = _build_display_specs(
            resolved_specs = added_specs["resolved_specs"],
            ui_hints       = added_specs.get("ui_hints") or {},
            spec_level     = spec_level,
            equipment_type = _canonical_eq_type,
        )

    # ── Scoring ───────────────────────────────────────────────────────────────
    # eq_type_fallback: when the alias matcher didn't set parsed["equipment_type"],
    # use the registry result's equipment_type (present when lookup succeeded).
    _registry_eq_type = (specs.get("equipment_type") if specs else "") or ""
    scoring:           dict | None = None
    fix_my_listing:    dict | None = None
    rewritten_listing: dict | None = None
    try:
        scorer_input = _build_scorer_input(
            parsed, added_specs,
            raw_text=raw_text,
            eq_type_fallback=_registry_eq_type,
        )
        scoring        = _score_listing(scorer_input)
        fix_my_listing = build_fix_my_listing(scoring)
    except Exception as _exc:
        print(f"[MTM] scoring error (non-fatal): {_exc}")

    confirm_required: dict | None = None
    if added_specs:
        try:
            confirm_required = build_confirm_required(
                requires_confirm           = added_specs.get("requires_confirm") or [],
                resolved_specs             = added_specs.get("resolved_specs")   or {},
                overall_resolution_status  = added_specs.get("overall_resolution_status") or "",
                safe_for_listing_injection = added_specs.get("safe_for_listing_injection", True),
            )
        except Exception as _exc:
            print(f"[MTM] confirm_required error (non-fatal): {_exc}")

    try:
        rewritten_listing = build_rewritten_listing(
            listing_data           = listing_data,
            added_specs            = added_specs,
            spec_level             = spec_level,
            generated_listing_text = cleaned_listing,
        )
    except Exception as _exc:
        print(f"[MTM] rewrite error (non-fatal): {_exc}")

    return format_output_response(
        cleaned_listing=cleaned_listing,
        parsed=parsed,
        added_specs=added_specs,
        confidence_note=confidence_note,
        spec_level=spec_level,
        output_assets=output_assets,
        display_specs=display_specs,
        scoring=scoring,
        fix_my_listing=fix_my_listing,
        confirm_required=confirm_required,
        rewritten_listing=rewritten_listing,
    )