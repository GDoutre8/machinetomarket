# BACKHOE USE CASE SCORER — LOCKED FOR PRODUCTION
# Version: v1.0
# Do NOT modify scoring logic, thresholds, or class rules.
# Changes allowed only to:
# - listing language text
# - feature synonyms
# - new use cases added in future versions

"""
backhoe_use_case_scorer_v1_0.py
MTM Backhoe Loader Use Case Scoring Engine

Architecture:
  - Loads 4 JSON config files at startup (schema, rules, class adjustments, listing language)
  - MachineRecord: canonical input using registry-exact field names + from_registry_record() adapter
  - score_machine(): main entry point → ScorerResult
  - format_result(): human-readable formatted output
  - 4-test harness under __main__

Field name decisions (from registry audit 2026-04-04):
  The prompt spec named 'loader_lift_capacity_lbs' and 'bucket_breakout_force_lbs'.
  Neither exists in the registry. This scorer uses the actual registry field names:
    backhoe_bucket_force_lbf   (backhoe bucket dig force)
    loader_breakout_force_lbf  (loader arm breakout)
    loader_bucket_capacity_yd3 (cubic yards, not lbs)

  The prompt feature flag names ('four_wd', 'aux_hydraulics', 'climate_control') are
  not canonical. This scorer uses schema-exact names: '4wd', 'rear_aux_hydraulics', 'enclosed_cab'.

  String spec fields in the registry (drive, rops_type, transmission_type, operator_controls)
  are parsed by from_registry_record() into canonical boolean feature flags.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_SCORER_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_json(filename: str, required_keys: list[str]) -> dict:
    candidates = [
        os.path.join("/mnt/user-data/outputs", filename),
        os.path.join(_SCORER_DIR, filename),
        os.path.join(_SCORER_DIR, "registry", filename),
    ]
    path = next((c for c in candidates if os.path.isfile(c)), None)
    if path is None:
        raise FileNotFoundError(
            f"Required config '{filename}' not found. Searched: {candidates}"
        )
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ValueError(f"Config '{filename}' missing required keys: {missing}")
    return data


_SCHEMA    = _load_json("backhoe_feature_schema.json",           ["feature_categories"])
_RULES     = _load_json("backhoe_use_case_rules.json",           ["use_cases", "scoring_engine"])
_CLASS_ADJ = _load_json("backhoe_class_use_case_adjustments.json", ["class_multipliers", "class_assignment_rules"])
_LANG      = _load_json("backhoe_listing_language_map.json",     ["use_case_phrases", "feature_phrases"])

_ALL_SCHEMA_FLAGS: set[str] = {
    flag for cat in _SCHEMA["feature_categories"].values() for flag in cat
}
_ALL_USE_CASES: list[str] = list(_RULES["use_cases"].keys())
_VALID_CLASSES: set[str]  = set(_CLASS_ADJ["class_multipliers"].keys())
_THRESHOLDS: dict         = _RULES["scoring_engine"]["thresholds"]


# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------

@dataclass
class MachineRecord:
    """
    Canonical input.  All spec field names mirror the MTM registry exactly.
    Use from_registry_record() to convert a raw registry dict.
    """
    # --- Specs (registry-exact names) ---
    horsepower_hp:              float | None = None
    operating_weight_lbs:       float | None = None
    max_dig_depth_ft:           float | None = None
    loader_bucket_capacity_yd3: float | None = None
    backhoe_bucket_force_lbf:   float | None = None   # bucket dig force
    loader_breakout_force_lbf:  float | None = None   # loader arm breakout
    travel_speed_mph:           float | None = None
    hydraulic_flow_gpm:         float | None = None
    max_reach_ft:               float | None = None
    fuel_capacity_gal:          float | None = None
    loader_bucket_width_in:     float | None = None

    # --- Classification ---
    machine_class: str | None = None   # pre-assigned or inferred

    # --- Identity ---
    model_slug:   str        = "unknown"
    manufacturer: str | None = None
    model:        str | None = None
    hours:        float | None = None

    # --- Feature flags (canonical schema names → True/False/None) ---
    features: dict[str, bool | None] = field(default_factory=dict)

    # --- Raw strings (kept for transparency) ---
    drive_raw:             str | None = None
    rops_type_raw:         str | None = None
    transmission_type_raw: str | None = None
    operator_controls_raw: str | None = None

    @classmethod
    def from_registry_record(cls, record: dict) -> "MachineRecord":
        """
        Build a MachineRecord from a raw MTM registry dict.
        Parses drive / rops_type / transmission_type / operator_controls strings
        into canonical feature flags, then merges with feature_flags block.
        """
        specs:     dict = record.get("specs", {}) or {}
        reg_flags: dict = record.get("feature_flags", {}) or {}

        drive_raw = specs.get("drive")
        rops_raw  = specs.get("rops_type")
        trans_raw = specs.get("transmission_type") or ""
        ctrl_raw  = specs.get("operator_controls") or ""

        inferred: dict[str, bool | None] = {}

        # 4wd from drive string
        if drive_raw == "4WD":
            inferred["4wd"] = True;  inferred["2wd"] = False
        elif drive_raw == "2WD/4WD":
            inferred["4wd"] = True;  inferred["2wd"] = True    # option exists
        elif drive_raw == "2WD":
            inferred["4wd"] = False; inferred["2wd"] = True
        elif drive_raw == "Track":
            inferred["4wd"] = True;  inferred["2wd"] = False   # tracked = all-terrain
        else:
            inferred["4wd"] = None

        # enclosed_cab from rops_type string
        if rops_raw == "Enclosed":
            inferred["enclosed_cab"] = True
        elif rops_raw == "Open":
            inferred["enclosed_cab"] = False
        elif rops_raw == "Enclosed/Open":
            inferred["enclosed_cab"] = True   # cab is available
        elif rops_raw in (None, "DEPRECATED"):
            inferred["enclosed_cab"] = None
        else:
            inferred["enclosed_cab"] = None

        # powershift_transmission from transmission_type string
        trans_lo = trans_raw.lower()
        if any(kw in trans_lo for kw in ("powershift", "power shift", "power shuttle", "autoshift")):
            inferred["powershift_transmission"] = True
        elif any(kw in trans_lo for kw in ("synchromesh", "collar shift", "manual", "hst")):
            inferred["powershift_transmission"] = False
        else:
            inferred["powershift_transmission"] = None

        # pilot_controls from operator_controls string
        ctrl_lo = ctrl_raw.lower()
        if any(kw in ctrl_lo for kw in ("pilot", "joystick")):
            inferred["pilot_controls"] = True
        elif ctrl_lo == "mechanical":
            inferred["pilot_controls"] = False
        else:
            inferred["pilot_controls"] = None

        # Registry feature_flags key → schema canonical key.
        # Registry uses different names than the feature_schema.json canonical names.
        # Scoring logic reads schema canonical names; this map bridges them.
        # Any future registry schema change should be handled here.
        _REG_TO_CANONICAL: dict[str, str] = {
            "extend_a_hoe":        "extendahoe",
            "aux_hydraulics_rear": "rear_aux_hydraulics",
            "aux_hydraulics_front":"front_aux_hydraulics",
            "four_in_one_bucket":  "4in1_bucket",
            "thumb":               "hydraulic_thumb",
            "hammer_line":         "breaker_hammer",
            "erops":               "enclosed_cab",
            "differential_lock":   "limited_slip",
            "cold_weather_package":"heat",
            # Pass-through keys (already canonical):
            "pilot_controls":      "pilot_controls",
            "ride_control":        "ride_control",
            "quick_coupler_rear":  "quick_coupler_rear",
            "quick_coupler_front": "quick_coupler_front",
            "air_suspension_seat": "air_suspension_seat",
            "telematics":          "telematics",
            # Registry-only keys with no scoring use — still pass through
            "counterweight":       "counterweight",
            "outriggers":          "outriggers",
        }

        # Merge: translate registry keys to canonical, inferred values fill gaps
        merged: dict[str, bool | None] = dict(inferred)
        for k, v in reg_flags.items():
            canonical_key = _REG_TO_CANONICAL.get(k, k)  # translate or pass through
            if v is True or v is False:
                merged[canonical_key] = bool(v)
            elif v is None and canonical_key not in merged:
                merged[canonical_key] = None

        # Machine class from registry_class_map
        model_slug = record.get("model_slug", "unknown")
        machine_class = None
        class_map: dict = _CLASS_ADJ["class_assignment_rules"].get("registry_class_map", {})
        for cls_name, slugs in class_map.items():
            if model_slug in slugs:
                machine_class = cls_name
                break

        return cls(
            model_slug             = model_slug,
            manufacturer           = record.get("manufacturer"),
            model                  = record.get("model"),
            machine_class          = machine_class,
            hours                  = record.get("hours"),
            horsepower_hp          = specs.get("horsepower_hp"),
            operating_weight_lbs   = specs.get("operating_weight_lbs"),
            max_dig_depth_ft       = specs.get("max_dig_depth_ft"),
            loader_bucket_capacity_yd3 = specs.get("loader_bucket_capacity_yd3"),
            backhoe_bucket_force_lbf   = specs.get("backhoe_bucket_force_lbf"),
            loader_breakout_force_lbf  = specs.get("loader_breakout_force_lbf"),
            travel_speed_mph       = specs.get("travel_speed_mph"),
            hydraulic_flow_gpm     = specs.get("hydraulic_flow_gpm"),
            max_reach_ft           = specs.get("max_reach_ft"),
            fuel_capacity_gal      = specs.get("fuel_capacity_gal"),
            loader_bucket_width_in = specs.get("loader_bucket_width_in"),
            drive_raw              = drive_raw,
            rops_type_raw          = rops_raw,
            transmission_type_raw  = trans_raw or None,
            operator_controls_raw  = ctrl_raw or None,
            features               = merged,
        )

    def has_feature(self, flag: str) -> bool:
        return self.features.get(flag) is True

    def feature_unknown(self, flag: str) -> bool:
        return flag in self.features and self.features[flag] is None


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UseCaseScore:
    use_case:              str
    label:                 str
    score:                 float        # 0–100 clamped
    tier:                  str          # excellent/good/capable/marginal/not_recommended
    spec_score:            float
    feature_score:         float
    class_bonus:           float
    base_score:            float        # spec + feature before class bonus
    reasons:               list[str]
    soft_penalties:        list[str]
    hard_gates_triggered:  list[str]
    applied_caps:          list[str]


@dataclass
class ScorerResult:
    model_slug:              str
    manufacturer:            str | None
    model:                   str | None
    hours:                   float | None
    capability_class:        str
    capability_class_label:  str
    top_use_cases:           list[UseCaseScore]   # top 5
    all_use_cases:           list[UseCaseScore]   # all 17, sorted desc
    listing_value_highlights: list[str]
    scoring_flags:           list[str]
    limitations:             list[str]
    jobsite_fit_summary:     dict[str, list[str]]
    best_for_summary:        str
    not_ideal_for_summary:   str
    listing_description:     str


# ---------------------------------------------------------------------------
# Capability class
# ---------------------------------------------------------------------------

_CLASS_LABELS = {
    "full_size_backhoe":       "Full-Size Backhoe — Utility / Construction / Production Work",
    "compact_tlb":             "Compact TLB — Residential / Tight Access / General Property Work",
    "sub_compact_tlb":         "Sub-Compact TLB — Light Duty / Estate / Small Property Work",
    "compact_tracked_backhoe": "Compact Tracked Backhoe — Urban Access / Soft Ground / Tight Sites",
}


def _compute_capability_class(record: MachineRecord) -> tuple[str, str]:
    if record.machine_class and record.machine_class in _VALID_CLASSES:
        return record.machine_class, _CLASS_LABELS.get(record.machine_class, record.machine_class)

    if (record.drive_raw or "").lower() == "track":
        cls = "compact_tracked_backhoe"
        return cls, _CLASS_LABELS[cls]

    wt = record.operating_weight_lbs
    hp = record.horsepower_hp
    dig = record.max_dig_depth_ft

    if wt is not None:
        cls = "sub_compact_tlb" if wt < 4000 else "compact_tlb" if wt < 13000 else "full_size_backhoe"
        return cls, _CLASS_LABELS[cls]
    if hp is not None:
        cls = "sub_compact_tlb" if hp < 30 else "compact_tlb" if hp < 60 else "full_size_backhoe"
        return cls, _CLASS_LABELS[cls]
    if dig is not None:
        cls = "sub_compact_tlb" if dig < 7 else "compact_tlb" if dig < 12 else "full_size_backhoe"
        return cls, _CLASS_LABELS[cls]

    return "full_size_backhoe", _CLASS_LABELS["full_size_backhoe"]


# ---------------------------------------------------------------------------
# Spec scoring
# ---------------------------------------------------------------------------

# Maps JSON spec field name → MachineRecord attribute name.
# Entries set to None are intentionally unmapped (prompt used wrong names).
_SPEC_FIELD_MAP: dict[str, str | None] = {
    "horsepower_hp":             "horsepower_hp",
    "operating_weight_lbs":      "operating_weight_lbs",
    "max_dig_depth_ft":          "max_dig_depth_ft",
    "loader_bucket_capacity_yd3":"loader_bucket_capacity_yd3",
    "backhoe_bucket_force_lbf":  "backhoe_bucket_force_lbf",
    "loader_breakout_force_lbf": "loader_breakout_force_lbf",
    "travel_speed_mph":          "travel_speed_mph",
    "hydraulic_flow_gpm":        "hydraulic_flow_gpm",
    # Explicitly wrong prompt names — reject loudly, not silently
    "loader_lift_capacity_lbs":  None,
    "bucket_breakout_force_lbs": None,
}


def _tier_score(value: float, tiers: list[dict]) -> tuple[float, str]:
    """Linear interpolation between tier thresholds."""
    if not tiers:
        return 0.0, ""
    sorted_t = sorted(tiers, key=lambda t: t["min"], reverse=True)
    if value >= sorted_t[0]["min"]:
        return float(sorted_t[0]["score"]), sorted_t[0].get("label", "")
    if value < sorted_t[-1]["min"]:
        return float(sorted_t[-1]["score"]), sorted_t[-1].get("label", "")
    for i in range(len(sorted_t) - 1):
        hi, lo = sorted_t[i], sorted_t[i + 1]
        if lo["min"] <= value < hi["min"]:
            span = hi["min"] - lo["min"]
            frac = (value - lo["min"]) / span if span > 0 else 0.0
            interpolated = lo["score"] + frac * (hi["score"] - lo["score"])
            label = hi.get("label", "") if frac >= 0.5 else lo.get("label", "")
            return interpolated, label
    return float(sorted_t[-1]["score"]), sorted_t[-1].get("label", "")


def _score_specs(record: MachineRecord, uc_data: dict) -> tuple[float, list[str]]:
    spec_config: dict = uc_data.get("spec_scoring", {})
    total, reasons = 0.0, []
    for spec_field, spec_rules in spec_config.items():
        attr = _SPEC_FIELD_MAP.get(spec_field)
        if attr is None:
            reasons.append(f"[CONFIG] '{spec_field}' has no registry mapping — skipped")
            continue
        value = getattr(record, attr, None)
        weight = spec_rules.get("weight", 0)
        tiers  = spec_rules.get("tiers", [])
        if value is None:
            fallback = float(tiers[-1]["score"]) * 0.4 if (tiers and weight <= 8) else 0.0
            total += fallback
            if weight >= 10:
                reasons.append(f"⚠ {spec_field}: unknown (scoring 0 — verify before listing)")
        else:
            raw, label = _tier_score(value, tiers)
            total += raw
            if raw >= weight * 0.8 and label:
                reasons.append(f"✓ {spec_field}={value:.1f}: {label}")
            elif raw <= weight * 0.3:
                reasons.append(f"✗ {spec_field}={value:.1f}: below ideal for this use case")
    return min(total, 50.0), reasons


# ---------------------------------------------------------------------------
# Feature scoring
# ---------------------------------------------------------------------------

def _score_features(record: MachineRecord, uc_data: dict) -> tuple[float, list[str]]:
    feat_config = uc_data.get("feature_scoring", {})
    total, reasons = 0.0, []
    for tier_name in ("primary", "secondary", "bonus"):
        tier     = feat_config.get(tier_name, {})
        features = tier.get("features", [])
        pts_each = float(tier.get("points_each", 0))
        cap      = float(tier.get("max", 0))
        earned   = 0.0
        for flag in features:
            if record.has_feature(flag):
                earned += pts_each
                reasons.append(f"✓ {flag} (+{pts_each:.0f})")
            elif record.feature_unknown(flag) and tier_name == "primary":
                credit = pts_each * 0.3
                earned += credit
                reasons.append(f"? {flag} (unknown — partial credit +{credit:.1f})")
        total += min(earned, cap)
    return min(total, 35.0), reasons


# ---------------------------------------------------------------------------
# Class bonus
# ---------------------------------------------------------------------------

def _apply_class_bonus(capability_class: str, uc_name: str) -> tuple[float, float]:
    cls_data = _CLASS_ADJ["class_multipliers"].get(capability_class, {})
    uc_adj   = cls_data.get(uc_name, {})
    return float(uc_adj.get("class_bonus", 0)), float(uc_adj.get("multiplier", 1.0))


# ---------------------------------------------------------------------------
# Hard gates
# ---------------------------------------------------------------------------

_HARD_GATES: list[dict] = [
    {
        "use_cases": ["sewer_line_install", "water_line_install", "trenching", "utility_work"],
        "condition": lambda r: r.max_dig_depth_ft is not None and r.max_dig_depth_ft < 8.0,
        "message":   "Dig depth < 8 ft — insufficient for utility trenching",
    },
    {
        "use_cases": ["foundation_digging"],
        "condition": lambda r: (
            r.backhoe_bucket_force_lbf is not None and r.backhoe_bucket_force_lbf < 3000
        ),
        "message": "Bucket force < 3,000 lbf — insufficient for foundation excavation",
    },
    {
        "use_cases": ["loading_trucks"],
        "condition": lambda r: (
            r.loader_bucket_capacity_yd3 is not None and r.loader_bucket_capacity_yd3 < 0.25
        ),
        "message": "Loader bucket < 0.25 yd³ — too small for efficient truck loading",
    },
    {
        "use_cases": ["foundation_digging", "road_work"],
        "condition": lambda r: (
            r.operating_weight_lbs is not None and r.operating_weight_lbs < 3500
        ),
        "message": "Operating weight < 3,500 lbs — machine too light for this application",
    },
]


def _apply_hard_gates(
    record: MachineRecord, uc_name: str, score: float
) -> tuple[float, list[str]]:
    triggered: list[str] = []
    for gate in _HARD_GATES:
        if uc_name in gate["use_cases"]:
            try:
                if gate["condition"](record):
                    score = 0.0
                    triggered.append(gate["message"])
            except Exception:
                pass
    return score, triggered


# ---------------------------------------------------------------------------
# Soft penalties and caps
# ---------------------------------------------------------------------------

def _apply_soft_penalties(
    record: MachineRecord,
    uc_name: str,
    score: float,
    capability_class: str,
) -> tuple[float, list[str], list[str]]:
    penalties: list[str] = []
    caps:      list[str] = []

    # No enclosed cab for all-weather use cases
    if uc_name in {"snow_removal", "road_work", "utility_work", "general_construction"}:
        if record.features.get("enclosed_cab") is False:
            score -= 8
            penalties.append("Open station — limited all-weather usability (-8)")

    # No pilot controls for precision-critical use cases
    if uc_name in {"utility_work", "sewer_line_install", "trenching", "water_line_install"}:
        if record.features.get("pilot_controls") is False:
            score -= 5
            penalties.append("Mechanical controls — pilot preferred for precision utility work (-5)")

    # No extendahoe for deep dig use cases
    if uc_name in {"trenching", "utility_work", "water_line_install", "sewer_line_install"}:
        if record.features.get("extendahoe") is False:
            score -= 5
            penalties.append("No extendahoe — limits reach and deep trench capability (-5)")

    # No rear aux hydraulics for attachment-critical use cases
    if uc_name in {"demolition_light", "utility_work", "trenching"}:
        if record.features.get("rear_aux_hydraulics") is False:
            score -= 6
            penalties.append("No rear aux hydraulics — hammer/auger attachments not possible (-6)")

    # No 4WD for terrain-intensive use cases
    if uc_name in {"utility_work", "farm_use", "general_construction", "septic_install"}:
        if record.features.get("4wd") is False:
            score -= 6
            penalties.append("2WD only — traction limited on soft/uneven ground (-6)")

    # Sub-compact hard cap on commercial production use cases
    commercial = {
        "foundation_digging", "road_work", "loading_trucks",
        "sewer_line_install", "demolition_light", "utility_work",
    }
    if capability_class == "sub_compact_tlb" and uc_name in commercial:
        cap_val = 35.0
        if score > cap_val:
            caps.append(f"Sub-compact class cap at {cap_val:.0f} for '{uc_name}'")
            score = cap_val

    # Open-station cap for snow removal
    if uc_name == "snow_removal" and record.features.get("enclosed_cab") is False:
        if score > 50.0:
            caps.append("Open station cap at 50 for snow_removal")
            score = 50.0

    return max(score, 0.0), penalties, caps


# ---------------------------------------------------------------------------
# Score tier labelling
# ---------------------------------------------------------------------------

def _score_to_tier(score: float) -> str:
    if score >= _THRESHOLDS.get("excellent", 80): return "excellent"
    if score >= _THRESHOLDS.get("good",      60): return "good"
    if score >= _THRESHOLDS.get("capable",   40): return "capable"
    if score >= _THRESHOLDS.get("marginal",  25): return "marginal"
    return "not_recommended"


# ---------------------------------------------------------------------------
# Listing highlights
# ---------------------------------------------------------------------------

def _build_listing_highlights(record: MachineRecord, capability_class: str) -> list[str]:
    highlights: list[str] = []
    feat_phrases = _LANG.get("feature_phrases", {})

    low_thresh = {"full_size_backhoe": 3000, "compact_tlb": 1500, "sub_compact_tlb": 800,
                  "compact_tracked_backhoe": 1500}.get(capability_class, 2000)
    if record.hours is not None:
        if record.hours < low_thresh:
            highlights.append(f"Low hours — only {record.hours:,.0f} hrs")
        elif record.hours < low_thresh * 1.5:
            highlights.append(f"Moderate hours — {record.hours:,.0f} hrs")

    priority_flags = [
        ("tight_pins",             "Tight pins and bushings throughout"),
        ("enclosed_cab",           "Fully enclosed cab"),
        ("ac",                     "Air-conditioned cab"),
        ("4wd",                    "4-Wheel Drive"),
        ("pilot_controls",         "Pilot / joystick controls"),
        ("extendahoe",             "Extendahoe dipperstick"),
        ("hydraulic_thumb",        "Hydraulic thumb"),
        ("rear_aux_hydraulics",    "Rear auxiliary hydraulics for hammer/auger"),
        ("powershift_transmission","Powershift transmission"),
        ("ride_control",           "Ride control"),
        ("4in1_bucket",            "4-in-1 multipurpose loader bucket"),
        ("quick_coupler_rear",     "Quick coupler (backhoe)"),
        ("pallet_forks",           "Pallet forks included"),
        ("breaker_hammer",         "Hydraulic breaker / hammer included"),
        ("no_leaks",               "Clean machine — no hydraulic leaks"),
        ("new_tires",              "New tires"),
        ("fleet_maintained",       "Fleet / dealer maintained"),
        ("one_owner",              "Single owner"),
        ("ready_to_work",          "Serviced and ready to work"),
    ]
    for flag, default in priority_flags:
        if record.has_feature(flag):
            highlights.append(feat_phrases.get(flag, default))

    if record.max_dig_depth_ft is not None and record.max_dig_depth_ft >= 16.0:
        highlights.append(f"Deep dig capability — {record.max_dig_depth_ft:.1f} ft")
    elif record.max_dig_depth_ft is not None and record.max_dig_depth_ft >= 14.0:
        highlights.append(f"Strong dig depth — {record.max_dig_depth_ft:.1f} ft")
    if record.backhoe_bucket_force_lbf is not None and record.backhoe_bucket_force_lbf >= 13000:
        highlights.append(f"High breakout force — {record.backhoe_bucket_force_lbf:,.0f} lbf")
    if record.loader_breakout_force_lbf is not None and record.loader_breakout_force_lbf >= 12000:
        highlights.append(f"Strong loader breakout — {record.loader_breakout_force_lbf:,.0f} lbf")
    if record.loader_bucket_capacity_yd3 is not None and record.loader_bucket_capacity_yd3 >= 1.3:
        highlights.append(f"Large loader bucket — {record.loader_bucket_capacity_yd3:.2f} yd³")
    if record.horsepower_hp is not None and record.horsepower_hp >= 100:
        highlights.append(f"High horsepower — {record.horsepower_hp:.0f} HP")

    class_label = {
        "full_size_backhoe":       "Full-size construction-spec backhoe",
        "compact_tracked_backhoe": "Compact tracked backhoe — fits where wheeled machines can't",
        "sub_compact_tlb":         "Sub-compact TLB — easy to transport and maneuver",
    }.get(capability_class)
    if class_label:
        highlights.append(class_label)

    return highlights[:12]


# ---------------------------------------------------------------------------
# Global flags and limitations
# ---------------------------------------------------------------------------

def _build_global_flags(
    record: MachineRecord, capability_class: str
) -> tuple[list[str], list[str]]:
    flags:       list[str] = []
    limitations: list[str] = []

    for attr, label in [
        ("backhoe_bucket_force_lbf", "backhoe bucket dig force"),
        ("loader_breakout_force_lbf", "loader breakout force"),
        ("max_dig_depth_ft",          "dig depth"),
        ("operating_weight_lbs",      "operating weight"),
        ("horsepower_hp",             "horsepower"),
    ]:
        if getattr(record, attr) is None:
            flags.append(f"⚠ Missing spec: {label} — scores may be understated")

    for flag in ["4wd", "enclosed_cab", "extendahoe", "rear_aux_hydraulics"]:
        if record.feature_unknown(flag):
            flags.append(f"? Feature '{flag}' unknown — confirm before listing")

    if record.hours is None:
        flags.append("⚠ Hours unknown — verify before listing")

    if capability_class == "sub_compact_tlb":
        limitations.append("Sub-compact class — not suited for commercial excavation or production trenching")
        limitations.append("Loader and backhoe capacity limits material volume")
    if capability_class == "compact_tlb":
        if record.max_dig_depth_ft is not None and record.max_dig_depth_ft < 11:
            limitations.append(f"Dig depth ({record.max_dig_depth_ft:.1f} ft) limits deep utility work")
    if record.features.get("enclosed_cab") is False:
        limitations.append("Open station — limited all-weather and municipal applications")
    if record.features.get("4wd") is False:
        limitations.append("2WD only — traction limitations on soft or wet ground")
    if record.features.get("extendahoe") is False:
        limitations.append("No extendahoe — standard dig depth only")
    if record.features.get("rear_aux_hydraulics") is False:
        limitations.append("No rear auxiliary hydraulics — hammer/auger/compactor attachments not supported")
    if record.features.get("pilot_controls") is False:
        limitations.append("Mechanical controls — pilot controls preferred by many operators")
    if record.horsepower_hp is not None and record.horsepower_hp < 65:
        limitations.append(f"Lower horsepower ({record.horsepower_hp:.0f} HP) — limited in production excavation")
    if record.travel_speed_mph is not None and record.travel_speed_mph < 15:
        limitations.append(f"Lower road speed ({record.travel_speed_mph:.1f} mph) — limited site-to-site mobility")

    return flags, limitations


# ---------------------------------------------------------------------------
# Jobsite fit summary
# ---------------------------------------------------------------------------

_JOBSITE_DOMAINS: dict[str, list[str]] = {
    "Underground Utility":       ["trenching", "water_line_install", "sewer_line_install", "utility_work"],
    "Residential Construction":  ["septic_install", "foundation_digging", "general_construction", "drainage_work"],
    "Material Handling":         ["loading_trucks", "material_handling", "pallet_handling"],
    "Property & Agricultural":   ["farm_use", "property_maintenance", "landscaping"],
    "Specialty / Seasonal":      ["demolition_light", "road_work", "snow_removal"],
}


def _build_jobsite_fit_summary(all_uc: list[UseCaseScore]) -> dict[str, list[str]]:
    by_slug = {uc.use_case: uc for uc in all_uc}
    result: dict[str, list[str]] = {}
    for domain, uc_list in _JOBSITE_DOMAINS.items():
        rows = []
        for uc_name in uc_list:
            uc = by_slug.get(uc_name)
            if uc:
                rows.append(f"{uc.label}: {uc.score:.0f}/100 ({uc.tier})")
        result[domain] = rows
    return result


# ---------------------------------------------------------------------------
# Summary sentences
# ---------------------------------------------------------------------------

def _natural_list(items: list[str]) -> str:
    if not items:     return ""
    if len(items) == 1: return items[0]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _build_summaries(
    top_use_cases: list[UseCaseScore],
    all_use_cases: list[UseCaseScore],
    capability_class: str,
) -> tuple[str, str]:
    best = [uc.label for uc in top_use_cases if uc.score >= 60]
    if best:
        best_str = "Best suited for " + _natural_list(best[:3]) + "."
    else:
        capable = [uc.label for uc in top_use_cases if uc.score >= 40]
        best_str = (
            "Capable for " + _natural_list(capable[:3]) + ", though not optimized for heavy commercial work."
            if capable else
            "Light-duty machine best suited for property maintenance and small-scale tasks."
        )

    avoid  = sorted([uc for uc in all_use_cases if uc.score < 30 and not uc.hard_gates_triggered], key=lambda u: u.score)
    gated  = [uc for uc in all_use_cases if uc.hard_gates_triggered]
    avoid_labels = [uc.label for uc in avoid[:3]]
    gated_labels = [uc.label for uc in gated[:2]]
    not_items = gated_labels + avoid_labels
    not_str = (
        "Not ideal for " + _natural_list(not_items[:3]) + "."
        if not_items else
        "Few meaningful limitations for typical applications in this class."
    )
    return best_str, not_str


# ---------------------------------------------------------------------------
# Listing description composer
# ---------------------------------------------------------------------------

def _compose_listing_description(
    record: MachineRecord,
    capability_class: str,
    top_use_cases: list[UseCaseScore],
) -> str:
    class_openers  = _LANG.get("class_opener_phrases", {}).get(capability_class, {})
    combo_phrases  = _LANG.get("multi_use_case_combo_phrases", {})
    uc_phrases     = _LANG.get("use_case_phrases", {})
    feat_phrases   = _LANG.get("feature_phrases", {})

    low_thresh = {"full_size_backhoe": 3000, "compact_tlb": 1500, "sub_compact_tlb": 800,
                  "compact_tracked_backhoe": 1500}.get(capability_class, 2000)
    if record.hours is not None:
        opener = class_openers.get("low_hour" if record.hours < low_thresh else "high_hour",
                                   class_openers.get("generic", ""))
    else:
        opener = class_openers.get("generic", "")

    combo_groups: dict[str, set[str]] = {
        "trenching_utility":      {"trenching", "utility_work", "water_line_install", "sewer_line_install"},
        "septic_drainage":        {"septic_install", "drainage_work"},
        "general_loading":        {"general_construction", "loading_trucks", "material_handling"},
        "farm_property":          {"farm_use", "property_maintenance"},
        "landscaping_property":   {"landscaping", "property_maintenance"},
        "construction_foundation":{"general_construction", "foundation_digging"},
        "demolition_utility":     {"demolition_light", "utility_work"},
        "snow_year_round":        {"snow_removal", "general_construction"},
    }
    scored_65 = {uc.use_case for uc in top_use_cases if uc.score >= 65}
    use_case_line = ""
    for combo_key, combo_set in combo_groups.items():
        if len(scored_65 & combo_set) >= 2 and combo_key in combo_phrases:
            phrases = combo_phrases[combo_key]
            use_case_line = phrases[0] if phrases else ""
            break
    if not use_case_line and top_use_cases:
        top_uc    = top_use_cases[0]
        uc_tier_p = uc_phrases.get(top_uc.use_case, {}).get(top_uc.tier, [])
        use_case_line = uc_tier_p[0] if uc_tier_p else ""

    feature_line = ""
    for flag in ["extendahoe", "pilot_controls", "hydraulic_thumb",
                 "rear_aux_hydraulics", "4in1_bucket", "enclosed_cab"]:
        if record.has_feature(flag) and flag in feat_phrases:
            feature_line = feat_phrases[flag]
            break

    return " ".join(p for p in [opener, use_case_line, feature_line] if p)


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

def score_machine(record: MachineRecord) -> ScorerResult:
    capability_class, capability_class_label = _compute_capability_class(record)
    all_uc_scores: list[UseCaseScore] = []

    for uc_name in _ALL_USE_CASES:
        uc_data  = _RULES["use_cases"].get(uc_name, {})
        uc_label = uc_data.get("label", uc_name)

        spec_score,  spec_reasons  = _score_specs(record, uc_data)
        feat_score,  feat_reasons  = _score_features(record, uc_data)
        class_bonus, _             = _apply_class_bonus(capability_class, uc_name)

        base_score = spec_score + feat_score
        raw_score  = base_score + class_bonus

        gated_score, hard_gates   = _apply_hard_gates(record, uc_name, raw_score)
        final_score, soft_pen, caps = _apply_soft_penalties(
            record, uc_name, gated_score, capability_class
        )
        final_score = max(0.0, min(100.0, final_score))

        all_uc_scores.append(UseCaseScore(
            use_case             = uc_name,
            label                = uc_label,
            score                = round(final_score, 1),
            tier                 = _score_to_tier(final_score),
            spec_score           = round(spec_score, 1),
            feature_score        = round(feat_score, 1),
            class_bonus          = class_bonus,
            base_score           = round(base_score, 1),
            reasons              = spec_reasons + feat_reasons,
            soft_penalties       = soft_pen,
            hard_gates_triggered = hard_gates,
            applied_caps         = caps,
        ))

    all_uc_scores.sort(key=lambda u: u.score, reverse=True)
    top_use_cases = all_uc_scores[:5]

    listing_highlights = _build_listing_highlights(record, capability_class)
    scoring_flags, limitations = _build_global_flags(record, capability_class)
    jobsite_fit = _build_jobsite_fit_summary(all_uc_scores)
    best_for, not_ideal = _build_summaries(top_use_cases, all_uc_scores, capability_class)
    listing_desc = _compose_listing_description(record, capability_class, top_use_cases)

    return ScorerResult(
        model_slug              = record.model_slug,
        manufacturer            = record.manufacturer,
        model                   = record.model,
        hours                   = record.hours,
        capability_class        = capability_class,
        capability_class_label  = capability_class_label,
        top_use_cases           = top_use_cases,
        all_use_cases           = all_uc_scores,
        listing_value_highlights= listing_highlights,
        scoring_flags           = scoring_flags,
        limitations             = limitations,
        jobsite_fit_summary     = jobsite_fit,
        best_for_summary        = best_for,
        not_ideal_for_summary   = not_ideal,
        listing_description     = listing_desc,
    )


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

def format_result(result: ScorerResult, show_debug: bool = False) -> str:
    lines: list[str] = []

    def h(t: str) -> None:
        lines.extend([f"\n{'='*62}", f"  {t}", f"{'='*62}"])

    def sec(t: str) -> None:
        lines.append(f"\n--- {t} ---")

    def li(t: str) -> None:
        lines.append(f"  • {t}")

    name = (f"{result.manufacturer or ''} {result.model or ''}".strip()) or result.model_slug
    hrs  = f"{result.hours:,.0f} hrs" if result.hours else "hrs unknown"
    h(f"MTM Backhoe Scorer  |  {name}  ({hrs})")
    lines.append(f"\n  Class:  {result.capability_class_label}")
    lines.append(f"  Slug:   {result.model_slug}")

    if result.listing_description:
        sec("AUTO LISTING DESCRIPTION")
        lines.append(f'  "{result.listing_description}"')

    sec("TOP USE CASES")
    for uc in result.top_use_cases:
        bar = "█" * int(uc.score / 5) + "░" * (20 - int(uc.score / 5))
        lines.append(f"  {uc.score:5.1f}  [{bar}]  {uc.label}  [{uc.tier.upper()}]")

    sec("ALL USE CASES (ranked)")
    tier_sym = {"excellent":"★★★","good":"★★ ","capable":"★  ","marginal":"~  ","not_recommended":"✗  "}
    for uc in result.all_use_cases:
        sym = tier_sym.get(uc.tier, "   ")
        lines.append(
            f"  {sym}  {uc.score:5.1f}  {uc.label:<38}"
            f"  spec={uc.spec_score:.0f} feat={uc.feature_score:.0f} cls={uc.class_bonus:.0f}"
        )

    sec("JOBSITE FIT SUMMARY")
    for domain, items in result.jobsite_fit_summary.items():
        lines.append(f"  {domain}:")
        for item in items:
            lines.append(f"    - {item}")

    sec("LISTING VALUE HIGHLIGHTS")
    for h_item in result.listing_value_highlights:
        li(h_item)

    if result.scoring_flags:
        sec("SCORING FLAGS (data quality)")
        for f_item in result.scoring_flags:
            li(f_item)

    if result.limitations:
        sec("LIMITATIONS")
        for lim in result.limitations:
            li(lim)

    sec("SUMMARIES")
    lines.append(f"  Best for:      {result.best_for_summary}")
    lines.append(f"  Not ideal for: {result.not_ideal_for_summary}")

    if show_debug:
        sec("DEBUG — SCORE BREAKDOWN")
        for uc in result.all_use_cases:
            lines.append(f"\n  [{uc.use_case}]  score={uc.score}  tier={uc.tier}")
            for r in uc.reasons:
                lines.append(f"    {r}")
            for p in uc.soft_penalties:
                lines.append(f"    PENALTY: {p}")
            for c in uc.applied_caps:
                lines.append(f"    CAP: {c}")
            for g in uc.hard_gates_triggered:
                lines.append(f"    HARD_GATE: {g}")

    lines.append("\n" + "=" * 62)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json as _json

    def _load_registry() -> dict[str, dict]:
        path = "/mnt/user-data/outputs/mtm_backhoe_loader_registry_v9.json"
        if not os.path.isfile(path):
            return {}
        with open(path) as fh:
            data = _json.load(fh)
        return {r["model_slug"]: r
                for r in data.get("records", [])
                if r.get("registry_tier") == "production"}

    REG = _load_registry()
    print("\n" + "=" * 70)
    print("  MTM Backhoe Use Case Scorer v1.0 — Test Harness")
    print("=" * 70)

    # ------------------------------------------------------------------
    # TEST 1: JD 310SL — full-size, fully optioned utility/construction spec
    # ------------------------------------------------------------------
    print("\n\n[TEST 1] John Deere 310SL — full-size, well-optioned")
    rec1 = MachineRecord.from_registry_record(REG["jd_310sl"]) if "jd_310sl" in REG else MachineRecord(
        model_slug="jd_310sl", manufacturer="John Deere", model="310SL",
        machine_class="full_size_backhoe",
        horsepower_hp=99, operating_weight_lbs=15872, max_dig_depth_ft=14.3,
        loader_bucket_capacity_yd3=1.31, backhoe_bucket_force_lbf=12100,
        loader_breakout_force_lbf=11000, travel_speed_mph=25.0, hydraulic_flow_gpm=36,
    )
    rec1.hours = 2400
    rec1.features.update({
        "4wd": True, "extendahoe": True, "pilot_controls": True,
        "enclosed_cab": True, "ac": True, "rear_aux_hydraulics": True,
        "powershift_transmission": True, "quick_coupler_rear": True,
        "hydraulic_thumb": True, "ride_control": True,
        "tight_pins": True, "fleet_maintained": True,
    })
    print(format_result(score_machine(rec1)))

    # ------------------------------------------------------------------
    # TEST 2: Kubota M62 — compact TLB, farm/property sweet spot
    # ------------------------------------------------------------------
    print("\n\n[TEST 2] Kubota M62 — compact TLB, open station, farm use")
    rec2 = MachineRecord.from_registry_record(REG["kubota_m62"]) if "kubota_m62" in REG else MachineRecord(
        model_slug="kubota_m62", manufacturer="Kubota", model="M62",
        machine_class="compact_tlb",
        horsepower_hp=62, operating_weight_lbs=8925, max_dig_depth_ft=10.8,
        loader_bucket_capacity_yd3=0.67, backhoe_bucket_force_lbf=5500,
        loader_breakout_force_lbf=4800, travel_speed_mph=16.2,
    )
    rec2.hours = 1100
    rec2.features.update({
        "4wd": True, "extendahoe": False, "pilot_controls": False,
        "enclosed_cab": False, "rear_aux_hydraulics": True,
        "powershift_transmission": False, "quick_coupler_rear": True,
        "pallet_forks": True, "auger": True,
        "new_tires": True, "one_owner": True, "ready_to_work": True,
    })
    print(format_result(score_machine(rec2)))

    # ------------------------------------------------------------------
    # TEST 3: Kubota BX23S — sub-compact TLB, estate / light property
    # ------------------------------------------------------------------
    print("\n\n[TEST 3] Kubota BX23S — sub-compact TLB, low hours, property use")
    rec3 = MachineRecord.from_registry_record(REG["kubota_bx23s"]) if "kubota_bx23s" in REG else MachineRecord(
        model_slug="kubota_bx23s", manufacturer="Kubota", model="BX23S",
        machine_class="sub_compact_tlb",
        horsepower_hp=21, operating_weight_lbs=2800, max_dig_depth_ft=6.2,
        loader_bucket_capacity_yd3=0.13, backhoe_bucket_force_lbf=1936,
        loader_breakout_force_lbf=1286, travel_speed_mph=8.4,
    )
    rec3.hours = 450
    rec3.features.update({
        "4wd": True, "extendahoe": False, "pilot_controls": False,
        "enclosed_cab": False, "rear_aux_hydraulics": True,
        "powershift_transmission": False, "quick_coupler_front": True,
        "pallet_forks": True, "auger": True,
        "low_hours": True, "one_owner": True,
    })
    print(format_result(score_machine(rec3)))

    # ------------------------------------------------------------------
    # TEST 4: Cat 430F2 — large full-size, heavy production spec
    # ------------------------------------------------------------------
    print("\n\n[TEST 4] Caterpillar 430F2 — large full-size, production hours")
    rec4 = MachineRecord.from_registry_record(REG["cat_430f"]) if "cat_430f" in REG else MachineRecord(
        model_slug="cat_430f", manufacturer="Caterpillar", model="430F2",
        machine_class="full_size_backhoe",
        horsepower_hp=107, operating_weight_lbs=25040, max_dig_depth_ft=15.4,
        loader_bucket_capacity_yd3=1.31, backhoe_bucket_force_lbf=16162,
        loader_breakout_force_lbf=11197, travel_speed_mph=25.0, hydraulic_flow_gpm=43,
    )
    rec4.hours = 4800
    rec4.features.update({
        "4wd": True, "extendahoe": True, "pilot_controls": True,
        "enclosed_cab": True, "ac": True, "rear_aux_hydraulics": True,
        "powershift_transmission": True, "hydraulic_thumb": True,
        "ride_control": True, "breaker_hammer": True,
        "fleet_maintained": True, "tight_pins": False,
    })
    print(format_result(score_machine(rec4)))
