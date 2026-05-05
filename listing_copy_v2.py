"""
listing_copy_v2.py
==================
Deterministic listing copy variation for MTM generated listing text.

This module keeps copy decisions explicit:
- lead patterns rotate deterministically by equipment type and machine identity
- condition phrases are driven by hours only
- value points are equipment-specific and grounded in confirmed specs/features
- tone profiles alter length and CTA without changing factual claims
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToneProfile:
    name: str
    lead_limit: int
    cta_with_price: str
    cta_without_price: str


TONE_PROFILES: dict[str, ToneProfile] = {
    "dealer_clean": ToneProfile(
        name="Dealer Clean",
        lead_limit=2,
        cta_with_price="Call or text to schedule a look.",
        cta_without_price="Call or text for pricing and availability.",
    ),
    "marketplace_direct": ToneProfile(
        name="Marketplace Direct",
        lead_limit=1,
        cta_with_price="Message or call to come see it.",
        cta_without_price="Message or call for price and availability.",
    ),
    "premium_spec_sheet": ToneProfile(
        name="Premium Spec Sheet",
        lead_limit=3,
        cta_with_price="Contact us to confirm availability, request more photos, or schedule a walkaround.",
        cta_without_price="Contact us for pricing, availability, photos, and walkaround details.",
    ),
}


CONDITION_LOGIC: tuple[tuple[int, str], ...] = (
    (500, "low-hour"),
    (1500, "clean lower-hour"),
    (3500, "well-kept working machine"),
)


LEAD_PATTERNS: dict[str, tuple[str, ...]] = {
    "telehandler": (
        "{condition} {machine} built for material handling, pallet work, and jobsite placement.",
        "{machine} with {capacity} lift capacity and {reach} reach - a strong fit for material staging and lift support.",
        "Jobsite-ready {machine} set up for pallet work, material placement, and general lift support.",
        "{condition_cap}: {machine} with {height} lift height for crews moving material at elevation.",
        "{machine} configured for construction, yard, and ag material handling with {features}.",
        "Strong-fit {machine} for contractors who need reach, capacity, and jobsite mobility in one unit.",
    ),
    "compact_track_loader": (
        "{condition_cap}: {machine} with {roc} ROC and {features}.",
        "{machine} set up for grading, loading, attachment work, and daily site support.",
        "Clean CTL package: {machine} with {features}, plus track-loader stability.",
        "{machine} brings tracked traction, loader capacity, and jobsite versatility in a compact footprint.",
        "Contractor-ready {machine} for material handling, site prep, and attachment-driven work.",
        "{condition_cap}: {machine} with {hours} hours and CTL capability for mixed site work.",
    ),
    "skid_steer": (
        "{condition_cap}: {machine} with {roc} ROC and {features}.",
        "{machine} set up for loading, grading, pallet work, and attachment support.",
        "Practical skid steer package: {machine} with {features}.",
        "{machine} brings compact loader capacity and jobsite versatility for daily work.",
        "Contractor-ready {machine} for material handling, site prep, and bucket work.",
        "{condition_cap}: {machine} with {hours} hours and skid steer utility for tight jobsites.",
    ),
    "mini_excavator": (
        "{condition_cap}: {machine} with {dig_depth} dig depth and {features}.",
        "{machine} set up for trenching, utility work, and general excavation support.",
        "Clean mini ex package: {machine} with {features} for residential and light commercial work.",
        "{machine} brings compact digging capability with {dig_depth} dig depth.",
        "Jobsite-ready {machine} for digging, backfill, drainage, and prep work.",
        "{condition_cap}: {machine} with {hours} hours and mini excavator versatility.",
    ),
}


BEST_FOR_SENTENCE_MAP: dict[str, str] = {
    "Rooftop Material Placement": "Best suited for roof staging, truss placement, and elevated material placement.",
    "High-Reach Loading": "Best suited for reach work where loads need to clear barriers or work at elevation.",
    "Jobsite Reach & Placement": "Best suited for keeping active crews supplied across the site.",
    "Pallet Handling": "Best suited for pallets, flatbeds, and material staging.",
    "Grading & Site Prep": "Best suited for grading, backfill, and prep work.",
    "Material Handling": "Best suited for pallets, loading, and on-site material movement.",
    "Truck Loading": "Best suited for loading trucks and moving bulk material.",
    "Land Clearing": "Best suited for clearing, cleanup, and rough site work.",
    "Forestry Mulching": "Best suited for high-flow mulching and vegetation removal.",
    "Utility Trenching": "Best suited for utility cuts, drainage runs, and conduit work.",
    "Excavation & Digging": "Best suited for footings, drainage, and general digging.",
    "Demolition & Breaking": "Best suited for breaker work, slab removal, and demolition support.",
}


def condition_phrase(hours: int | None) -> str:
    """Return the hour-based condition phrase requested for v2 copy."""
    if hours is None:
        return "work-ready"
    for max_hours, phrase in CONDITION_LOGIC:
        if hours < max_hours:
            return phrase
    return "work-ready unit with honest hours"


def build_contact_cta(has_price: bool, tone_profile: str = "dealer_clean") -> str:
    profile = _tone(tone_profile)
    return profile.cta_with_price if has_price else profile.cta_without_price


def build_opening_paragraph(
    dealer_input: Any,
    resolved_specs: dict,
    equipment_type: str = "",
    tone_profile: str = "dealer_clean",
) -> str:
    """
    Build a deterministic 1-3 sentence opening paragraph.

    The same machine always receives the same lead pattern, but similar machines
    no longer collapse to one repeated sentence.
    """
    eq_type = _normalize_equipment_type(equipment_type)
    profile = _tone(tone_profile)
    machine = _machine_name(dealer_input)
    fields = {
        "condition": condition_phrase(getattr(dealer_input, "hours", None)),
        "condition_cap": condition_phrase(getattr(dealer_input, "hours", None)).capitalize(),
        "machine": machine,
        "hours": f"{getattr(dealer_input, 'hours', 0):,}",
        "capacity": _first_spec(resolved_specs, ("lift_capacity_lb", "max_lift_capacity_lbs", "lift_capacity_lbs", "max_load_capacity_lbs"), "rated lift"),
        "height": _first_spec(resolved_specs, ("max_lift_height_ft", "lift_height_ft", "max_load_height_ft"), "jobsite"),
        "reach": _first_spec(resolved_specs, ("max_forward_reach_ft", "forward_reach_ft"), "extended"),
        "roc": _first_spec(resolved_specs, ("roc_lb", "rated_operating_capacity_lbs"), "loader"),
        "dig_depth": _first_spec(resolved_specs, ("max_dig_depth", "max_dig_depth_ft"), "jobsite"),
        "features": _feature_phrase(dealer_input, resolved_specs, eq_type),
    }

    templates = LEAD_PATTERNS.get(eq_type) or (
        "{condition_cap} {machine} with {hours} hours and jobsite-ready configuration.",
        "{machine} set up for daily equipment work with {features}.",
    )
    lead = templates[_stable_index(dealer_input, eq_type, len(templates))].format(**fields)
    sentences = [_clean_sentence(lead)]

    value_sentence = _value_sentence(dealer_input, resolved_specs, eq_type)
    if value_sentence and profile.lead_limit >= 2:
        sentences.append(value_sentence)

    detail_sentence = _detail_sentence(dealer_input, eq_type)
    if detail_sentence and profile.lead_limit >= 3:
        sentences.append(detail_sentence)

    return " ".join(sentences)


def best_for_sentence(use_case: str) -> str:
    return BEST_FOR_SENTENCE_MAP.get(use_case, f"Best suited for {use_case.lower()}.")


def _tone(tone_profile: str) -> ToneProfile:
    return TONE_PROFILES.get(tone_profile, TONE_PROFILES["dealer_clean"])


def _normalize_equipment_type(equipment_type: str) -> str:
    value = (equipment_type or "").strip().lower()
    aliases = {
        "ctl": "compact_track_loader",
        "compact track loader": "compact_track_loader",
        "ssl": "skid_steer",
        "skid_steer_loader": "skid_steer",
        "mini ex": "mini_excavator",
        "mini excavator": "mini_excavator",
    }
    return aliases.get(value, value)


def _machine_name(dealer_input: Any) -> str:
    year = getattr(dealer_input, "year", None)
    make = getattr(dealer_input, "make", "")
    model = getattr(dealer_input, "model", "")
    return " ".join(str(p).strip() for p in (year, make, model) if str(p or "").strip())


def _stable_index(dealer_input: Any, equipment_type: str, modulo: int) -> int:
    key = "|".join(
        str(getattr(dealer_input, attr, "") or "")
        for attr in ("year", "make", "model", "hours")
    )
    digest = hashlib.sha1(f"{equipment_type}|{key}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _first_spec(specs: dict, keys: tuple[str, ...], fallback: str) -> str:
    for key in keys:
        value = specs.get(key)
        if value is None or value == "":
            continue
        label = _format_spec_value(key, value)
        if label:
            return label
    return fallback


def _format_spec_value(key: str, value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        if re.search(r"\b(ft|in|lb|lbs|gpm|hp)\b", stripped, re.I):
            return stripped
        value = stripped
    if isinstance(value, (int, float)):
        shown = f"{int(value):,}" if float(value).is_integer() else f"{value:,.1f}"
        if "lb" in key or key.endswith("_lbs"):
            return f"{shown} lb"
        if key.endswith("_ft") or "height" in key or "reach" in key:
            return f"{shown} ft"
        if key.endswith("_gpm") or "flow" in key:
            return f"{shown} GPM"
        if key.endswith("_hp"):
            return f"{shown} HP"
        return shown
    return str(value)


def _feature_phrase(dealer_input: Any, specs: dict, equipment_type: str) -> str:
    features = _equipment_features(dealer_input, specs, equipment_type)
    if not features:
        return "core work features"
    return _join_phrases(features[:3])


def _equipment_features(dealer_input: Any, specs: dict, equipment_type: str) -> list[str]:
    features: list[str] = []
    cab = str(getattr(dealer_input, "cab_type", "") or "").lower()
    if cab in {"enclosed", "erops", "closed", "cab"}:
        features.append("enclosed cab")
    if getattr(dealer_input, "ac", None):
        features.append("A/C")

    if equipment_type == "telehandler":
        if getattr(dealer_input, "has_stabilizers", None):
            features.append("stabilizers")
        if _has_attachment(dealer_input, ("fork", "pallet")):
            features.append("forks")
        if _has_attachment(dealer_input, ("bucket",)):
            features.append("bucket")
        if specs.get("hydraulic_flow_gpm"):
            features.append("aux hydraulics")
    elif equipment_type in {"compact_track_loader", "skid_steer"}:
        if getattr(dealer_input, "high_flow", None) == "yes":
            features.append("high flow")
        if getattr(dealer_input, "two_speed_travel", None) == "yes":
            features.append("2-speed")
        if getattr(dealer_input, "ride_control", None):
            features.append("ride control")
        if getattr(dealer_input, "track_condition", None):
            features.append("tracks noted")
    elif equipment_type == "mini_excavator":
        thumb = getattr(dealer_input, "thumb_type", None)
        if thumb and thumb != "none":
            features.append(f"{thumb} thumb")
        if getattr(dealer_input, "aux_hydraulics", None):
            features.append("aux hydraulics")
        if getattr(dealer_input, "blade_type", None):
            features.append("blade")
        if getattr(dealer_input, "zero_tail_swing", None) or str(specs.get("tail_swing_type") or "").lower() == "zero":
            features.append("zero tail swing")

    return _dedupe(features)


def _value_sentence(dealer_input: Any, specs: dict, equipment_type: str) -> str:
    if equipment_type == "telehandler":
        capacity = _first_spec(specs, ("lift_capacity_lb", "max_lift_capacity_lbs", "lift_capacity_lbs", "max_load_capacity_lbs"), "")
        height = _first_spec(specs, ("max_lift_height_ft", "lift_height_ft", "max_load_height_ft"), "")
        reach = _first_spec(specs, ("max_forward_reach_ft", "forward_reach_ft"), "")
        parts = [p for p in (capacity and f"{capacity} capacity", height and f"{height} lift height", reach and f"{reach} forward reach") if p]
        if parts:
            return f"Specs point toward {', '.join(parts)} for material placement and staging."
        return "Built around reach, lift capacity, and 4WD jobsite mobility."

    if equipment_type in {"compact_track_loader", "skid_steer"}:
        parts = []
        roc = _first_spec(specs, ("roc_lb", "rated_operating_capacity_lbs"), "")
        flow = _first_spec(specs, ("hydraulic_flow_gpm", "aux_flow_standard_gpm"), "")
        if roc:
            parts.append(f"{roc} ROC")
        if flow:
            parts.append(f"{flow} auxiliary flow")
        if getattr(dealer_input, "high_flow", None) == "yes":
            parts.append("confirmed high flow")
        return f"Key buyer points: {_join_phrases(parts)}." if parts else ""

    if equipment_type == "mini_excavator":
        parts = []
        depth = _first_spec(specs, ("max_dig_depth", "max_dig_depth_ft"), "")
        if depth:
            parts.append(f"{depth} dig depth")
        if getattr(dealer_input, "thumb_type", None) and getattr(dealer_input, "thumb_type") != "none":
            parts.append("thumb")
        if getattr(dealer_input, "aux_hydraulics", None):
            parts.append("aux hydraulics")
        if getattr(dealer_input, "blade_type", None):
            parts.append("blade")
        return f"Key buyer points: {_join_phrases(parts)}." if parts else ""

    return ""


def _detail_sentence(dealer_input: Any, equipment_type: str) -> str:
    details: list[str] = []
    if getattr(dealer_input, "one_owner", None):
        details.append("one owner")
    if getattr(dealer_input, "track_condition", None):
        details.append(f"tracks: {getattr(dealer_input, 'track_condition')}")
    if getattr(dealer_input, "tire_condition", None):
        details.append(f"tires: {getattr(dealer_input, 'tire_condition')}")
    if not details:
        return ""
    label = "Unit notes" if equipment_type else "Notes"
    return f"{label}: {_join_phrases(details)}."


def _has_attachment(dealer_input: Any, needles: tuple[str, ...]) -> bool:
    text = str(getattr(dealer_input, "attachments_included", "") or "").lower()
    return any(needle in text for needle in needles)


def _join_phrases(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _clean_sentence(sentence: str) -> str:
    sentence = re.sub(r"\s+", " ", sentence).strip()
    sentence = sentence.replace("with core work features", "with practical work features")
    return sentence if sentence.endswith(".") else f"{sentence}."


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
