"""
ctl_use_case_scorer.py
======================
MTM Listings -- CTL Use Case Scoring Engine
Derived from: CTL Use Case Scoring Engine Master Framework v1.0

Scores a CTL machine record against 11 real-world use cases using
weighted spec-driven rules. Returns capability class, ranked use cases,
attachment compatibility, listing value highlights, and scoring flags.

Usage:
    from ctl_use_case_scorer import score_ctl
    result = score_ctl(machine_record)
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class MachineRecord:
    """
    Normalized CTL machine input record.
    All fields are optional -- scorer handles None gracefully.
    Field names match MTM registry schema exactly.
    """
    # Core specs
    horsepower_hp: float | None = None
    rated_operating_capacity_lbs: float | None = None
    operating_weight_lbs: float | None = None
    aux_flow_standard_gpm: float | None = None
    aux_flow_high_gpm: float | None = None
    hydraulic_pressure_standard_psi: float | None = None
    hydraulic_pressure_high_psi: float | None = None
    bucket_hinge_pin_height_in: float | None = None

    # Feature flags
    high_flow_available: bool | None = None
    two_speed_available: bool | None = None
    enclosed_cab_available: bool | None = None
    ride_control_available: bool | None = None

    # Lift geometry: "radial" | "vertical"
    lift_path: str | None = None

    # Attachment flags
    hydraulic_breaker_available: bool | None = None

    # Condition / market fields
    brand: str | None = None
    hours: float | None = None
    track_condition_pct: float | None = None   # 0-100; None = unknown


@dataclass
class UseCaseScore:
    """Score result for a single use case."""
    use_case: str
    score: int                               # 0-100
    label: str                               # Excellent / Good / Fair / Poor / Not Recommended
    reasons: list[str] = field(default_factory=list)   # human-readable explanation strings
    flags: list[str] = field(default_factory=list)     # warning strings surfaced to output
    # Transparency / debug fields
    base_score_before_adjustments: int = 0             # raw weighted spec score before caps/penalties
    applied_caps: list[str] = field(default_factory=list)        # caps that fired
    applied_penalties: list[str] = field(default_factory=list)   # penalties that fired
    triggered_hard_gates: list[str] = field(default_factory=list)


@dataclass
class ScorerResult:
    """Full scoring result returned by score_ctl()."""
    capability_class: str                    # "A" | "B" | "C" | "D"
    capability_class_label: str
    frame_class: str                         # "small_frame" | "medium_frame" | "large_frame"
    frame_class_label: str
    hydraulic_tier: str                      # "standard" | "high_flow" | "enhanced_high_flow"
    hydraulic_tier_label: str
    profile: str                             # one of 7 CTL profile keys
    profile_label: str
    top_use_cases: list[UseCaseScore]        # top 3 scored use cases
    all_use_cases: list[UseCaseScore]        # all 11, sorted descending by score
    attachment_compatibility: dict[str, dict]
    listing_value_highlights: list[str]      # features worth calling out in listing copy
    scoring_flags: list[str]                 # warnings / notable conditions
    limitations: list[str]                   # things this machine cannot do well
    best_for_summary: str
    not_ideal_for_summary: str


# ---------------------------------------------------------------------------
# RULES DICTIONARY
# ---------------------------------------------------------------------------
# Edit this section to tune thresholds without touching scoring logic.

RULES: dict = {

    # --- Capability Class Boundaries ---
    # Classes are computed from actual specs, not manual labels.
    # ROC is primary driver. Weight is secondary. HP is tertiary.
    # Boundaries are INCLUSIVE of the max value shown.
    "class_boundaries": {
        # Class A: Small CTL  (ROC up to 2,199 lb)
        "A": {"roc_max": 2199, "weight_max": 8499, "hp_max": 67},
        # Class B: Mid CTL   (ROC 2,200 - 2,999 lb)
        "B": {"roc_max": 2999, "weight_max": 9699, "hp_max": 84},
        # Class C: Large CTL (ROC 3,000 - 3,999 lb)
        "C": {"roc_max": 3999, "weight_max": 12499, "hp_max": 105},
        # Class D: High-flow / Specialty -- requires BOTH thresholds
        "D": {"high_flow_min_gpm": 37, "hp_min": 96},
    },

    # Weight must exceed the band ceiling by this fraction to trigger a step-up.
    # Weight never steps a class DOWN -- ROC is the anchor.
    "weight_adjustment_pct": 0.15,

    # --- Hydraulic Flow Thresholds ---
    "hydraulic": {
        "tier3_hard_disqualifier_gpm": 25,   # below this + no HF flag: Tier 3 impossible
        "tier3_marginal_gpm": 29,            # 25-29 GPM: flag as limited, cap scores
        "tier3_capable_gpm": 30,             # >=30 GPM: Tier 3 capable
        "tier3_full_mulcher_gpm": 37,        # >=37 GPM: full mulcher/masticator capable
        "tier2_min_standard_gpm": 18,        # standard flow minimum for Tier 2 work
        "pressure_heavy_min_psi": 3000,      # minimum for rock trenching / planing
        "pressure_standard_min_psi": 2800,   # minimum for most Tier 2 work
    },

    # --- Use Case Spec Gates and Weights ---
    # Each use case defines:
    #   hard_gates:         list of (condition_name, reason) -- score = 0 if any fires
    #   base_score_factors: list of (field, full_credit_thresh, partial_credit_thresh, weight_pct)
    #   soft_caps:          list of (condition_name, cap_value, reason) -- applied before penalties
    #   soft_penalties:     list of (condition_name, deduction, reason) -- applied after caps

    "use_cases": {

        "grading_site_prep": {
            "label": "Grading / Site Prep",
            "hard_gates": [],
            "base_score_factors": [
                # ROC and weight anchor grading -- heavier machine is more stable on grades
                ("rated_operating_capacity_lbs", 2000, 1500, 35),
                ("operating_weight_lbs", 8500, 6000, 25),
                ("horsepower_hp", 70, 50, 25),
                ("aux_flow_standard_gpm", 20, 12, 15),
            ],
            "soft_penalties": [
                ("no_two_speed", 5, "2-speed helpful for travel between grading zones"),
                # Radial lift is well-suited for digging and grading; apply a small penalty
                # to vertical lift rather than a bonus for radial -- both remain viable
                ("vertical_lift", 3, "Vertical lift slightly less ideal for close-in digging vs radial"),
            ],
            "soft_caps": [],
        },

        "material_handling_loading": {
            "label": "Material Handling / Loading",
            "hard_gates": [],
            "base_score_factors": [
                ("rated_operating_capacity_lbs", 2800, 1800, 45),
                ("bucket_hinge_pin_height_in", 124, 108, 25),
                ("operating_weight_lbs", 9500, 7000, 15),
                ("horsepower_hp", 80, 60, 15),
            ],
            "soft_penalties": [
                ("radial_lift", 15, "Radial lift limits dump height; vertical lift preferred for truck-height loading"),
            ],
            "soft_caps": [],
        },

        "light_land_clearing": {
            "label": "Light Land Clearing",
            "hard_gates": [],
            # ROC and weight are the primary anchors for land clearing capability.
            # High flow is a bonus that enables brush cutters, not the base requirement.
            # A grapple/bucket clearing machine without high flow can still score well.
            "base_score_factors": [
                ("rated_operating_capacity_lbs", 2800, 1800, 35),
                ("operating_weight_lbs", 9500, 7000, 30),
                ("horsepower_hp", 80, 60, 25),
                ("aux_flow_standard_gpm", 22, 14, 10),
            ],
            "soft_penalties": [
                ("no_high_flow", 10, "High-flow package preferred for brush-cutting attachments"),
                ("no_enclosed_cab", 8, "Enclosed cab recommended for debris protection"),
            ],
            "soft_caps": [
                # Cap is moderate -- not devastating -- because bucket/grapple clearing remains valid
                ("no_high_flow", 72, "Without high-flow, clearing limited to bucket/grapple methods; brush cutters not supported"),
            ],
        },

        "forestry_mulching": {
            "label": "Forestry Mulching",
            "hard_gates": [
                ("no_high_flow_hard", "No high-flow package -- forestry mulchers require sustained >=28 GPM"),
                ("insufficient_flow_hard", "Confirmed aux flow below 25 GPM -- mulcher will cavitate and underperform"),
            ],
            "base_score_factors": [
                ("aux_flow_high_gpm", 40, 28, 40),
                ("horsepower_hp", 100, 80, 30),
                ("operating_weight_lbs", 10500, 9000, 15),
                ("rated_operating_capacity_lbs", 3200, 2500, 15),
            ],
            "soft_penalties": [
                # Open cab is a major safety concern for forestry -- heavy penalty
                ("no_enclosed_cab", 45, "SAFETY: Enclosed cab required for forestry mulching -- severe debris and rollover hazard"),
            ],
            "soft_caps": [
                # Tighten open-cab forestry cap significantly
                ("no_enclosed_cab", 25, "Safety cap: open-cab machine must not be used for forestry mulching"),
                ("marginal_flow", 50, "Marginal high-flow (25-29 GPM) limits production rate on large trees"),
                ("hf_gpm_unconfirmed", 55, "High-flow present but GPM unconfirmed -- score capped pending spec verification"),
            ],
        },

        "trenching_standard": {
            "label": "Trenching (Standard -- Soft Ground)",
            "hard_gates": [],
            "base_score_factors": [
                ("aux_flow_standard_gpm", 22, 15, 40),
                ("hydraulic_pressure_standard_psi", 3000, 2500, 30),
                ("horsepower_hp", 65, 50, 20),
                ("rated_operating_capacity_lbs", 2000, 1500, 10),
            ],
            "soft_penalties": [],
            "soft_caps": [],
        },

        "trenching_rock": {
            "label": "Trenching (Rock / Hard Ground)",
            "hard_gates": [
                ("insufficient_pressure_hard", "Confirmed hydraulic pressure below 2,800 PSI -- rock trencher will stall"),
            ],
            "base_score_factors": [
                ("aux_flow_high_gpm", 32, 22, 35),
                ("hydraulic_pressure_standard_psi", 3200, 2800, 30),
                ("horsepower_hp", 85, 65, 20),
                ("operating_weight_lbs", 9500, 7500, 15),
            ],
            "soft_penalties": [
                ("no_high_flow", 20, "High-flow strongly recommended for rock trenching chains"),
            ],
            "soft_caps": [
                ("no_high_flow", 55, "Without high-flow, rock trenching limited to softer rock or small chains"),
                ("hf_gpm_unconfirmed", 60, "High-flow present but GPM unconfirmed -- rock trench capability not fully scorable"),
            ],
        },

        "demolition_breaking": {
            "label": "Demolition / Breaking",
            "hard_gates": [],
            "base_score_factors": [
                ("hydraulic_pressure_standard_psi", 3200, 2600, 40),
                ("aux_flow_standard_gpm", 22, 15, 25),
                ("operating_weight_lbs", 10000, 7500, 20),
                ("horsepower_hp", 75, 60, 15),
            ],
            "soft_penalties": [],
            "soft_caps": [
                ("no_breaker", 65, "Demolition capped — no breaker/hammer confirmed; strong HF + large frame may override"),
            ],
        },

        "snow_removal": {
            "label": "Snow Removal",
            "hard_gates": [],
            "base_score_factors": [
                ("horsepower_hp", 70, 50, 30),
                ("operating_weight_lbs", 8500, 6500, 25),
                ("rated_operating_capacity_lbs", 2200, 1500, 20),
                ("aux_flow_standard_gpm", 18, 12, 25),
            ],
            "soft_penalties": [
                ("no_two_speed", 20, "2-speed critical for travel between zones; single-speed limits productivity"),
                ("no_enclosed_cab", 15, "Enclosed cab with heat essential for operator comfort in snow conditions"),
            ],
            "soft_caps": [
                ("no_two_speed", 60, "Without 2-speed, snow removal limited to small / tight areas"),
            ],
        },

        "cold_planing": {
            "label": "Cold Planing / Asphalt Milling",
            "hard_gates": [
                ("no_high_flow_hard", "No high-flow package -- cold planers require sustained high-flow hydraulics"),
                ("insufficient_flow_hard", "Confirmed aux flow below 25 GPM -- cold planer will underperform severely"),
            ],
            "base_score_factors": [
                ("aux_flow_high_gpm", 38, 28, 40),
                ("horsepower_hp", 90, 70, 30),
                ("operating_weight_lbs", 10000, 8000, 20),
                ("hydraulic_pressure_standard_psi", 3200, 2800, 10),
            ],
            "soft_penalties": [],
            "soft_caps": [
                ("marginal_flow", 55, "Marginal high-flow limits planer width and cutting depth"),
                ("hf_gpm_unconfirmed", 55, "High-flow present but GPM unconfirmed -- planing capability not fully scorable"),
            ],
        },

        "stump_grinding": {
            "label": "Stump Grinding",
            "hard_gates": [],
            "base_score_factors": [
                ("aux_flow_high_gpm", 34, 20, 40),
                ("horsepower_hp", 80, 60, 30),
                ("hydraulic_pressure_standard_psi", 3000, 2600, 20),
                ("rated_operating_capacity_lbs", 2400, 1800, 10),
            ],
            "soft_penalties": [
                ("no_high_flow", 20, "High-flow strongly preferred for production-rate stump grinding"),
            ],
            "soft_caps": [
                ("no_high_flow", 50, "Without high-flow, limited to smaller stumps at reduced feed rate"),
                ("hf_gpm_unconfirmed", 60, "High-flow present but GPM unconfirmed -- stump grinder compatibility not fully scorable"),
            ],
        },

        "auger_work": {
            "label": "Auger Work (Light Soil / Small Diameter)",
            "hard_gates": [],
            "base_score_factors": [
                ("aux_flow_standard_gpm", 18, 12, 40),
                ("hydraulic_pressure_standard_psi", 2800, 2200, 30),
                ("rated_operating_capacity_lbs", 2000, 1400, 20),
                ("horsepower_hp", 60, 45, 10),
            ],
            "soft_penalties": [],
            "soft_caps": [],
        },
    },

    # --- Score to Label Map ---
    "score_labels": [
        (85, "Excellent"),
        (70, "Good"),
        (50, "Fair"),
        (30, "Poor"),
        (0,  "Not Recommended"),
    ],

    # --- Brand Tiers (for listing value highlights) ---
    "brand_tiers": {
        "tier1": {
            "brands": ["caterpillar", "cat", "john deere", "deere", "bobcat"],
            "label": "Tier 1 Brand",
        },
        "tier2": {
            "brands": ["case", "new holland", "kubota"],
            "label": "Tier 2 Brand",
        },
        "tier3": {
            "brands": ["asv", "takeuchi", "gehl", "manitou", "toro"],
            "label": "Value Brand",
        },
    },

    # --- Hours Condition Labels ---
    # Tuples of (hours_threshold, label). None threshold = catch-all.
    "hours_labels": [
        (500,  "Like New"),
        (1500, "Low Hours"),
        (3000, "Mid Hours"),
        (5000, "High Hours"),
        (None, "Very High Hours"),
    ],
}


# ---------------------------------------------------------------------------
# FRAME CLASS / HYDRAULIC TIER / PROFILE SYSTEM
# ---------------------------------------------------------------------------
# Frame class: attachment-first identity model for CTL.
# Parallel to A/B/C/D cap system; used for identity framing and profile logic.
#
# small_frame:  ROC < 1,750 lb  — residential, tight access, property/farm
# medium_frame: ROC 1,750–2,500  — generalist contractor, rental, utility
# large_frame:  ROC > 2,500      — production work, heavy clearing, specialty
# ---------------------------------------------------------------------------

FRAME_CLASS_BOUNDARIES = {
    "small_frame": {
        "roc_max": 1749,
        "label": "Small Frame CTL (< 1,750 lb ROC) — residential, light property, tight access",
    },
    "medium_frame": {
        "roc_min": 1750,
        "roc_max": 2500,
        "label": "Medium Frame CTL (1,750–2,500 lb ROC) — generalist contractor, rental, utility",
    },
    "large_frame": {
        "roc_min": 2501,
        "label": "Large Frame CTL (> 2,500 lb ROC) — production work, heavy clearing, specialty",
    },
}

# Hydraulic tier — explicit layer above A/B/C/D for attachment identity
HYDRAULIC_TIERS_CTL = {
    "standard":           "Standard Hydraulics — general attachment work, no Tier 3 support",
    "high_flow":          "High-Flow Hydraulics — specialty attachment capable (mulcher, brush cutter, planer)",
    "enhanced_high_flow": "Enhanced High-Flow (≥37 GPM) — full production mulching, clearing, and specialty work",
}

# The 7 CTL identity profiles
CTL_PROFILES = {
    "small_generalist_ctl":          "Small Generalist CTL — residential utility, tight access, light grading, landscaping",
    "small_farm_property_ctl":       "Small Farm/Property CTL — fence posts, light clearing, drainage, rural utility",
    "medium_generalist_ctl":         "Mid-Size Generalist CTL — contractor all-rounder, rental-grade utility",
    "medium_radial_siteprep_ctl":    "Mid-Size Radial Site Prep CTL — grading, digging, site work, utility trenching",
    "large_production_vertical_ctl": "Large Vertical-Lift Production CTL — truck loading, stockpile, material handling",
    "large_production_radial_ctl":   "Large Radial Production CTL — site prep, grading, clearing, ground disturbance",
    "large_specialty_highflow_ctl":  "Large Specialty High-Flow CTL — forestry mulching, clearing, specialty production work",
}

# Brand channel — drives Best For ordering, not scores
BRAND_CHANNEL_CTL: dict[str, str] = {
    "cat":         "construction",
    "caterpillar": "construction",
    "bobcat":      "construction",
    "case":        "construction",
    "new holland": "construction",
    "asv":         "construction",
    "takeuchi":    "construction",
    "gehl":        "construction",
    "manitou":     "construction",
    "toro":        "construction",
    "john deere":  "rural",      # CTL rural: property/farm work secondary, not primary
    "deere":       "rural",
    "kubota":      "rural",
    "yanmar":      "rural",
}

# Profile score bonuses: applied to use case scores AFTER base scoring.
# Keys match use case labels in RULES["use_cases"][key]["label"].
# Rules: bonus only applied when base score > 0 and no hard gate triggered.
PROFILE_BONUSES: dict[str, dict[str, int]] = {
    "small_generalist_ctl": {
        "Grading / Site Prep":                      8,
        "Trenching (Standard -- Soft Ground)":       8,
        "Auger Work (Light Soil / Small Diameter)": 8,
        "Snow Removal":                             6,
    },
    "small_farm_property_ctl": {
        "Grading / Site Prep":                      12,
        "Light Land Clearing":                      14,
        "Auger Work (Light Soil / Small Diameter)": 12,
        "Trenching (Standard -- Soft Ground)":       8,
        "Snow Removal":                             6,
    },
    "medium_generalist_ctl": {},   # no adjustments — balanced baseline
    "medium_radial_siteprep_ctl": {
        "Grading / Site Prep":                  18,  # materially strong boost for radial grading
        "Trenching (Standard -- Soft Ground)":  12,
        "Light Land Clearing":                  10,
        # Demolition intentionally omitted — no_breaker cap must not be bypassed by profile bonus
    },
    "large_production_vertical_ctl": {
        "Material Handling / Loading":  20,   # materially strong boost for vertical loading
        "Light Land Clearing":           8,
        "Grading / Site Prep":           6,
    },
    "large_production_radial_ctl": {
        "Grading / Site Prep":                 18,
        "Light Land Clearing":                  8,
        "Trenching (Standard -- Soft Ground)": 10,
    },
    "large_specialty_highflow_ctl": {
        "Forestry Mulching":                   18,
        "Light Land Clearing":                 14,
        "Stump Grinding":                      12,
        "Cold Planing / Asphalt Milling":      12,
        "Trenching (Rock / Hard Ground)":       10,
        "Demolition / Breaking":                8,
    },
}

# Profile size identity caps: prevent small-frame machines from reading like
# production machines, and prevent large machines from reading like residential.
PROFILE_SIZE_CAPS: dict[str, dict[str, int]] = {
    "small_generalist_ctl": {
        "Material Handling / Loading":  62,   # small frame can't do production truck loading
        "Light Land Clearing":          60,
        "Forestry Mulching":             0,   # already hard-gated; belt-and-suspenders
        "Cold Planing / Asphalt Milling": 0,  # same
    },
    "small_farm_property_ctl": {
        "Material Handling / Loading":  58,
        "Forestry Mulching":             0,
        "Cold Planing / Asphalt Milling": 0,
    },
    "medium_generalist_ctl": {},
    "medium_radial_siteprep_ctl": {},
    "large_production_vertical_ctl": {},
    "large_production_radial_ctl": {},
    "large_specialty_highflow_ctl": {},
}

# Brand-specific use case bonuses — applied after profile bonuses.
# Purpose: differentiate machines that land in the same profile (e.g. Kubota vs JD in small_farm_property_ctl).
# Keyed by lowercase brand name; values are use case label → bonus int.
BRAND_SPECIFIC_BONUSES_CTL: dict[str, dict[str, int]] = {
    "kubota": {
        "Light Land Clearing": 35,
        "Grading / Site Prep":  3,
    },
    # JD intentionally omitted — generic profile behavior is correct for 317G
}

# Best For ordering for brand channels — used in summary generation.
# Construction: lead with construction work; Rural: allow clearing/property language earlier.
# Forestry / mulching listed early so large_specialty_highflow machines surface it
# (for non-HF machines forestry won't be in top 5, so this has no effect on them).
_CTL_CONSTRUCTION_ORDER = [
    "grading", "material handling", "forestry", "mulch", "land clearing",
    "trenching", "demolition", "cold plan", "stump", "snow removal", "auger",
]
_CTL_RURAL_ORDER = [
    "grading", "land clearing", "forestry", "mulch",
    "trenching", "auger", "snow removal", "stump", "material handling", "demolition",
]


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def _safe_get(record: MachineRecord, field_name: str, default=None):
    """Safely retrieve a field from the machine record."""
    return getattr(record, field_name, default)


def _effective_high_flow_gpm(record: MachineRecord) -> float | None:
    """
    Return the confirmed high-flow GPM value, or None.

    Rules:
      high_flow_available is False          -> None (no high flow)
      aux_flow_high_gpm has a value         -> return that value (confirmed GPM)
      high_flow_available is True but
        aux_flow_high_gpm is None           -> None (present but GPM unconfirmed)
      high_flow_available is None and
        aux_flow_high_gpm has a value       -> return that value
      both None                             -> None (fully unknown)

    IMPORTANT: Never invent a GPM value when only the flag is True.
    Callers that need to distinguish "no high flow" from "high flow with
    unknown GPM" should check _hf_present_unconfirmed() directly.
    """
    hf_available = _safe_get(record, "high_flow_available")
    hf_gpm = _safe_get(record, "aux_flow_high_gpm")

    if hf_available is False:
        return None
    if hf_gpm is not None:
        return hf_gpm
    # high_flow_available is True but GPM is missing -- do NOT invent a value
    return None


def _hf_present_unconfirmed(record: MachineRecord) -> bool:
    """
    Returns True when high flow is confirmed present but GPM is not recorded.
    Used to apply partial credit and flag the data gap without inventing a value.
    """
    hf_available = _safe_get(record, "high_flow_available")
    hf_gpm = _safe_get(record, "aux_flow_high_gpm")
    return hf_available is True and hf_gpm is None


def _score_label(score: int) -> str:
    """Map a numeric score to a human-readable label."""
    for threshold, label in RULES["score_labels"]:
        if score >= threshold:
            return label
    return "Not Recommended"


def _spec_score(value: float | None, full_credit_threshold: float,
                partial_credit_threshold: float) -> float:
    """
    Score a single spec field on a 0.0-1.0 scale.

      value >= full_credit_threshold    -> 1.0 (full credit)
      value between thresholds          -> linear interpolation
      value < partial_credit_threshold  -> 0.0
      value is None                     -> 0.3 (unknown: cautious partial credit)
    """
    if value is None:
        return 0.3   # unknown spec: partial credit; flagged separately
    if value >= full_credit_threshold:
        return 1.0
    if value <= partial_credit_threshold:
        return 0.0
    span = full_credit_threshold - partial_credit_threshold
    return (value - partial_credit_threshold) / span


def _compute_base_score(record: MachineRecord, factors: list) -> int:
    """
    Compute a weighted base score (0-100) from a list of spec factors.
    Each factor is a tuple: (field_name, full_threshold, partial_threshold, weight_pct).
    Weight percents should sum to 100.

    For aux_flow_high_gpm, uses _effective_high_flow_gpm() which returns None
    when GPM is unconfirmed -- this triggers 0.3 partial credit, which is
    appropriate for "high flow present but GPM not on record."
    """
    total_weight = 0
    weighted_sum = 0.0

    for spec_field, full_thresh, partial_thresh, weight in factors:
        if spec_field == "aux_flow_high_gpm":
            value = _effective_high_flow_gpm(record)
        else:
            value = _safe_get(record, spec_field)

        s = _spec_score(value, full_thresh, partial_thresh)
        weighted_sum += s * weight
        total_weight += weight

    if total_weight == 0:
        return 50   # fallback when no factors are defined

    raw = weighted_sum / total_weight * 100
    return max(0, min(100, round(raw)))


# ---------------------------------------------------------------------------
# CONDITION EVALUATORS
# Called by name from the RULES dictionary.
# Each returns True when the condition applies (penalty / gate / cap fires).
# ---------------------------------------------------------------------------

def _cond_no_two_speed(record: MachineRecord) -> bool:
    return _safe_get(record, "two_speed_available") is False


def _cond_radial_lift(record: MachineRecord) -> bool:
    return (_safe_get(record, "lift_path") or "").lower() == "radial"


def _cond_vertical_lift(record: MachineRecord) -> bool:
    return (_safe_get(record, "lift_path") or "").lower() == "vertical"


def _cond_no_enclosed_cab(record: MachineRecord) -> bool:
    return _safe_get(record, "enclosed_cab_available") is False


def _cond_no_high_flow(record: MachineRecord) -> bool:
    """Soft: high flow is explicitly not available."""
    return _safe_get(record, "high_flow_available") is False


def _cond_hf_gpm_unconfirmed(record: MachineRecord) -> bool:
    """Soft cap: high flow is present but GPM is not on record."""
    return _hf_present_unconfirmed(record)


def _cond_no_high_flow_hard(record: MachineRecord) -> bool:
    """
    Hard gate: high_flow_available is explicitly False AND standard flow is
    below the absolute Tier 3 minimum. Does not fire when high_flow_available
    is None (unknown) -- we only hard-disqualify on confirmed absence.
    """
    hf = _safe_get(record, "high_flow_available")
    std_flow = _safe_get(record, "aux_flow_standard_gpm") or 0
    return hf is False and std_flow < RULES["hydraulic"]["tier3_hard_disqualifier_gpm"]


def _cond_insufficient_flow_hard(record: MachineRecord) -> bool:
    """
    Hard gate: a confirmed aux_flow_high_gpm value is below the absolute
    Tier 3 minimum. Only fires on recorded values -- does not fire when GPM
    is simply missing.
    """
    hf_gpm = _safe_get(record, "aux_flow_high_gpm")
    std_flow = _safe_get(record, "aux_flow_standard_gpm") or 0

    if hf_gpm is not None and hf_gpm < 25:
        return True
    if _safe_get(record, "high_flow_available") is False and std_flow < 25:
        return True
    return False


def _cond_insufficient_pressure_hard(record: MachineRecord) -> bool:
    """
    Hard gate: confirmed hydraulic pressure is below the rock trenching minimum.
    Does not fire when pressure is None (unknown).
    """
    psi = _safe_get(record, "hydraulic_pressure_standard_psi")
    if psi is None:
        return False   # unknown: do not hard-gate
    return psi < 2800


def _cond_marginal_flow(record: MachineRecord) -> bool:
    """Soft cap: confirmed high-flow GPM is in the marginal 25-29 GPM band."""
    effective = _effective_high_flow_gpm(record)
    if effective is None:
        return False
    return (RULES["hydraulic"]["tier3_hard_disqualifier_gpm"]
            <= effective
            <= RULES["hydraulic"]["tier3_marginal_gpm"])


def _cond_no_breaker(record: MachineRecord) -> bool:
    """
    Fires (caps demolition) when a hydraulic breaker is NOT confirmed
    AND the machine doesn't have strong supporting signals (HF ≥ 25 GPM + ROC > 2,500 lb).
    """
    if _safe_get(record, "hydraulic_breaker_available"):
        return False  # breaker confirmed — no cap
    effective_gpm = _effective_high_flow_gpm(record)
    roc = _safe_get(record, "rated_operating_capacity_lbs")
    if effective_gpm is not None and effective_gpm >= 25 and roc is not None and roc > 2500:
        return False  # large frame + confirmed high flow — override allowed
    return True


# Map condition names to evaluator functions.
# Add new conditions here to make them available in RULES without touching logic.
CONDITION_EVALUATORS: dict[str, object] = {
    "no_two_speed":               _cond_no_two_speed,
    "radial_lift":                _cond_radial_lift,
    "vertical_lift":              _cond_vertical_lift,
    "no_enclosed_cab":            _cond_no_enclosed_cab,
    "no_high_flow":               _cond_no_high_flow,
    "hf_gpm_unconfirmed":         _cond_hf_gpm_unconfirmed,
    "no_high_flow_hard":          _cond_no_high_flow_hard,
    "insufficient_flow_hard":     _cond_insufficient_flow_hard,
    "insufficient_pressure_hard": _cond_insufficient_pressure_hard,
    "marginal_flow":              _cond_marginal_flow,
    "no_breaker":                 _cond_no_breaker,
}


def _eval_condition(name: str, record: MachineRecord) -> bool:
    """Look up and call a condition evaluator by name. Returns False for unknown names."""
    fn = CONDITION_EVALUATORS.get(name)
    if fn is None:
        return False
    return fn(record)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# CAPABILITY CLASS COMPUTATION
# ---------------------------------------------------------------------------

def _compute_capability_class(record: MachineRecord) -> tuple[str, str]:
    """
    Determine machine capability class (A/B/C/D) from actual specs.
    Returns (class_letter, class_label).

    Priority order:
      1. ROC is the primary class driver (loader capability anchor).
      2. Operating weight is a secondary modifier -- can step the class UP
         if weight is materially above the ROC-derived band ceiling.
         Weight never steps a class DOWN.
      3. HP is tertiary -- used as fallback when ROC is unknown.
      4. Class D requires BOTH confirmed high-flow GPM >= 37 AND HP >= 96.
         Class D does not apply when GPM is unconfirmed.
    """
    roc    = _safe_get(record, "rated_operating_capacity_lbs") or 0
    hp     = _safe_get(record, "horsepower_hp") or 0
    weight = _safe_get(record, "operating_weight_lbs") or 0
    hf_gpm = _effective_high_flow_gpm(record) or 0   # confirmed GPM only

    class_labels: dict[str, str] = {
        "A": "Small CTL -- Residential / Tight-Access",
        "B": "Mid CTL -- General Construction / Landscaping",
        "C": "Large CTL -- Heavy Construction / Land Clearing",
        "D": "High-Flow / Specialty CTL -- Forestry / Production Work",
    }
    class_order = ["A", "B", "C"]
    d_rules = RULES["class_boundaries"]["D"]

    # Class D: requires confirmed GPM and HP -- the flag alone is insufficient
    if hf_gpm >= d_rules["high_flow_min_gpm"] and hp >= d_rules["hp_min"]:
        return "D", class_labels["D"]

    def _roc_class(v: float) -> str:
        if v <= RULES["class_boundaries"]["A"]["roc_max"]:
            return "A"
        if v <= RULES["class_boundaries"]["B"]["roc_max"]:
            return "B"
        return "C"

    # Step 1: Derive base class from ROC
    if roc > 0:
        base_class = _roc_class(roc)
    elif weight > RULES["class_boundaries"]["B"]["weight_max"]:
        base_class = "C"
    elif weight > RULES["class_boundaries"]["A"]["weight_max"]:
        base_class = "B"
    elif hp > RULES["class_boundaries"]["B"]["hp_max"]:
        base_class = "C"
    elif hp > RULES["class_boundaries"]["A"]["hp_max"]:
        base_class = "B"
    else:
        base_class = "B"   # safe default when all primary specs are unknown

    # Step 2: Secondary weight adjustment -- step UP only, never down.
    # ROC is the anchor; a lighter-than-expected machine stays in its ROC class.
    if weight > 0 and base_class in class_order:
        adj_pct = RULES["weight_adjustment_pct"]
        idx = class_order.index(base_class)
        weight_max = RULES["class_boundaries"][base_class]["weight_max"]
        prev_weight_max = (
            RULES["class_boundaries"][class_order[idx - 1]]["weight_max"]
            if idx > 0 else 0
        )
        band_size = weight_max - prev_weight_max
        upper_threshold = weight_max + (band_size * adj_pct)

        if weight > upper_threshold and idx < len(class_order) - 1:
            base_class = class_order[idx + 1]   # step up one class only

    return base_class, class_labels[base_class]


# ---------------------------------------------------------------------------
# FRAME CLASS, HYDRAULIC TIER, PROFILE COMPUTATION
# ---------------------------------------------------------------------------

def _compute_frame_class(record: MachineRecord) -> tuple[str, str]:
    """
    Classify CTL into small_frame / medium_frame / large_frame by ROC.
    Primary driver: rated_operating_capacity_lbs.
    Fallback: operating_weight_lbs, then horsepower_hp.

    Boundaries:
      small_frame:  ROC < 1,750 lb   (sub-Class-A tier)
      medium_frame: ROC 1,750–2,500  (Class A upper + Class B lower)
      large_frame:  ROC > 2,500      (Class B upper, Class C, Class D)

    Expected validation:
      JD 317G     (ROC 1,750)     → medium_frame (inclusive)
      Kubota SVL65-2 (ROC 1,984)  → medium_frame
      Bobcat T650 (ROC 2,690)     → large_frame
      Case TR340B (ROC 3,400)     → large_frame
      Cat 299D3   (ROC 3,200)     → large_frame
    """
    roc    = _safe_get(record, "rated_operating_capacity_lbs") or 0
    weight = _safe_get(record, "operating_weight_lbs") or 0
    hp     = _safe_get(record, "horsepower_hp") or 0

    if roc > 0:
        if roc <= FRAME_CLASS_BOUNDARIES["small_frame"]["roc_max"]:
            return "small_frame", FRAME_CLASS_BOUNDARIES["small_frame"]["label"]
        elif roc <= FRAME_CLASS_BOUNDARIES["medium_frame"]["roc_max"]:
            return "medium_frame", FRAME_CLASS_BOUNDARIES["medium_frame"]["label"]
        else:
            return "large_frame", FRAME_CLASS_BOUNDARIES["large_frame"]["label"]

    # ROC unknown — fallback to weight / HP
    if weight > 10_000 or hp > 85:
        return "large_frame",  FRAME_CLASS_BOUNDARIES["large_frame"]["label"]
    elif weight > 7_000 or hp > 60:
        return "medium_frame", FRAME_CLASS_BOUNDARIES["medium_frame"]["label"]
    else:
        return "small_frame",  FRAME_CLASS_BOUNDARIES["small_frame"]["label"]


def _compute_hydraulic_tier_ctl(record: MachineRecord) -> tuple[str, str]:
    """
    Classify hydraulic capability into standard / high_flow / enhanced_high_flow.

    standard:          no high-flow package, or confirmed low flow
    high_flow:         high-flow available, GPM 25–36
    enhanced_high_flow: confirmed GPM >= 37 (full mulcher/masticator tier)
    """
    hf_available = _safe_get(record, "high_flow_available")
    hf_gpm       = _effective_high_flow_gpm(record)
    h            = RULES["hydraulic"]

    if hf_available is False:
        return "standard", HYDRAULIC_TIERS_CTL["standard"]

    if hf_gpm is None:
        if hf_available is True:
            # High flow present, GPM unknown — treat as high_flow with caveat
            return "high_flow", HYDRAULIC_TIERS_CTL["high_flow"] + " [GPM unconfirmed — verify before Tier 3 claims]"
        return "standard", HYDRAULIC_TIERS_CTL["standard"]

    if hf_gpm >= h["tier3_full_mulcher_gpm"]:   # >= 37 GPM
        return "enhanced_high_flow", HYDRAULIC_TIERS_CTL["enhanced_high_flow"]
    elif hf_gpm >= h["tier3_hard_disqualifier_gpm"]:  # >= 25 GPM
        return "high_flow", HYDRAULIC_TIERS_CTL["high_flow"]
    else:
        return "standard", HYDRAULIC_TIERS_CTL["standard"]


def _compute_ctl_profile(frame_class: str, hyd_tier: str,
                          record: MachineRecord) -> tuple[str, str]:
    """
    Assign one of 7 CTL identity profiles from frame class, hydraulic tier,
    lift path, and brand channel.

    Assignment logic:
      small_frame + rural brand   → small_farm_property_ctl
      small_frame + construction  → small_generalist_ctl
      medium_frame + radial       → medium_radial_siteprep_ctl
      medium_frame + vertical/unknown → medium_generalist_ctl
      large_frame + enhanced_hf   → large_specialty_highflow_ctl  (highest priority)
      large_frame + vertical      → large_production_vertical_ctl
      large_frame + radial/unknown → large_production_radial_ctl
    """
    lift    = (_safe_get(record, "lift_path") or "").lower()
    brand   = (_safe_get(record, "brand") or "").lower().strip()
    channel = BRAND_CHANNEL_CTL.get(brand, "construction")

    if frame_class == "small_frame":
        if channel == "rural":
            return "small_farm_property_ctl", CTL_PROFILES["small_farm_property_ctl"]
        return "small_generalist_ctl", CTL_PROFILES["small_generalist_ctl"]

    elif frame_class == "medium_frame":
        if lift == "radial":
            return "medium_radial_siteprep_ctl", CTL_PROFILES["medium_radial_siteprep_ctl"]
        return "medium_generalist_ctl", CTL_PROFILES["medium_generalist_ctl"]

    else:  # large_frame
        # Enhanced high-flow wins over lift path for large frame
        if hyd_tier == "enhanced_high_flow":
            return "large_specialty_highflow_ctl", CTL_PROFILES["large_specialty_highflow_ctl"]
        if lift == "vertical":
            return "large_production_vertical_ctl", CTL_PROFILES["large_production_vertical_ctl"]
        return "large_production_radial_ctl", CTL_PROFILES["large_production_radial_ctl"]


def _apply_profile_adjustments(profile: str,
                                all_scored: list[UseCaseScore],
                                record: "MachineRecord") -> list[UseCaseScore]:
    """
    Apply profile-specific score bonuses, brand-specific bonuses, and size identity caps.

    Order:
      1. Profile bonuses (lift path / frame class / HF tier)
      2. Brand-specific bonuses (differentiate same-profile siblings, e.g. Kubota vs JD)
      3. Profile size identity caps

    Bonuses only applied when base score > 0 and no hard gate triggered.
    Caps applied when current score exceeds cap value.
    """
    bonuses       = PROFILE_BONUSES.get(profile, {})
    caps          = PROFILE_SIZE_CAPS.get(profile, {})
    brand_key     = (_safe_get(record, "brand") or "").lower().strip()
    brand_bonuses = BRAND_SPECIFIC_BONUSES_CTL.get(brand_key, {})

    for uc in all_scored:
        # 1. Profile bonus
        if uc.use_case in bonuses:
            bonus = bonuses[uc.use_case]
            if uc.score > 0 and not uc.triggered_hard_gates:
                new_score = min(100, uc.score + bonus)
                if new_score > uc.score:
                    uc.reasons.append(
                        f"Profile bonus +{bonus} ({profile}): {uc.use_case} "
                        f"boosted by identity model"
                    )
                    uc.score = new_score
                    uc.label = _score_label(new_score)

        # 2. Brand-specific bonus
        if uc.use_case in brand_bonuses:
            bonus = brand_bonuses[uc.use_case]
            if uc.score > 0 and not uc.triggered_hard_gates:
                new_score = min(100, uc.score + bonus)
                if new_score > uc.score:
                    uc.reasons.append(
                        f"Brand bonus +{bonus} ({brand_key}): {uc.use_case} "
                        f"boosted by brand identity"
                    )
                    uc.score = new_score
                    uc.label = _score_label(new_score)

        # 3. Profile size identity cap
        if uc.use_case in caps:
            cap_val = caps[uc.use_case]
            if uc.score > cap_val:
                old = uc.score
                uc.score = cap_val
                uc.label = _score_label(cap_val)
                msg = (
                    f"PROFILE IDENTITY CAP ({profile}): {uc.use_case} "
                    f"capped {old} → {cap_val}; machine identity suppresses this use-case framing"
                )
                uc.applied_caps.append(msg)
                uc.flags.append(f"SIZE IDENTITY CAP: {msg}")

    return all_scored


def _apply_brand_channel_sort_ctl(brand: str | None,
                                   top_use_cases: list[UseCaseScore]) -> list[UseCaseScore]:
    """
    Reorder top use cases based on brand channel.

    construction brands (Cat, Bobcat, Case, etc.) → construction work first
    rural brands (Kubota, John Deere) → clearing, property, trenching surfaces higher

    CTL farm crossover is secondary, not primary — do not use ag/farm language.
    Only influences ordering, not scores.
    """
    if not brand:
        return top_use_cases

    brand_lower = brand.lower().strip()
    channel = BRAND_CHANNEL_CTL.get(brand_lower, "construction")
    priority = _CTL_RURAL_ORDER if channel == "rural" else _CTL_CONSTRUCTION_ORDER

    ordered: list[UseCaseScore] = []
    remainder = list(top_use_cases)

    for frag in priority:
        for uc in list(remainder):
            if frag.lower() in uc.use_case.lower():
                ordered.append(uc)
                remainder.remove(uc)
                break

    ordered.extend(remainder)
    return ordered


# ---------------------------------------------------------------------------
# USE CASE SCORER
# ---------------------------------------------------------------------------

def _score_use_case(use_case_key: str, record: MachineRecord) -> UseCaseScore:
    """Score a single use case and return a UseCaseScore with full transparency."""
    rules = RULES["use_cases"][use_case_key]
    reasons: list[str] = []
    flags: list[str] = []
    triggered_hard_gates: list[str] = []
    applied_caps: list[str] = []
    applied_penalties: list[str] = []

    # Step 1: Check hard gates -- any match returns score = 0
    for gate_name, gate_reason in rules.get("hard_gates", []):
        if _eval_condition(gate_name, record):
            return UseCaseScore(
                use_case=rules["label"],
                score=0,
                label="Not Recommended",
                reasons=[f"HARD DISQUALIFIER: {gate_reason}"],
                flags=[f"DISQUALIFIED: {gate_reason}"],
                base_score_before_adjustments=0,
                applied_caps=[],
                applied_penalties=[],
                triggered_hard_gates=[gate_reason],
            )

    # Step 2: Compute base score from weighted spec factors
    base = _compute_base_score(record, rules.get("base_score_factors", []))
    score = base

    # Step 3: Apply soft caps (before penalties)
    for cap_name, cap_value, cap_reason in rules.get("soft_caps", []):
        if _eval_condition(cap_name, record) and score > cap_value:
            score = cap_value
            cap_entry = f"Cap at {cap_value}: {cap_reason}"
            reasons.append(cap_entry)
            flags.append(f"CAP: {cap_reason}")
            applied_caps.append(cap_entry)

    # Step 4: Apply soft penalties (after caps)
    for penalty_name, deduction, penalty_reason in rules.get("soft_penalties", []):
        if _eval_condition(penalty_name, record):
            score = max(0, score - deduction)
            penalty_entry = f"-{deduction} pts: {penalty_reason}"
            reasons.append(penalty_entry)
            applied_penalties.append(penalty_entry)

    score = max(0, min(100, score))

    # Step 5: Flag high-flow-present-but-unconfirmed globally
    if _hf_present_unconfirmed(record):
        flags.append("INFO: High-flow present but GPM unconfirmed -- verify aux_flow_high_gpm")

    return UseCaseScore(
        use_case=rules["label"],
        score=score,
        label=_score_label(score),
        reasons=reasons,
        flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps,
        applied_penalties=applied_penalties,
        triggered_hard_gates=triggered_hard_gates,
    )


# ---------------------------------------------------------------------------
# ATTACHMENT COMPATIBILITY
# ---------------------------------------------------------------------------

def _compute_attachment_compatibility(record: MachineRecord) -> dict[str, dict]:
    """
    Classify Tier 1/2/3 attachment compatibility based on hydraulic specs.
    Handles the high-flow-present-but-GPM-unconfirmed case explicitly.
    """
    std_flow     = _safe_get(record, "aux_flow_standard_gpm") or 0
    hf_gpm       = _effective_high_flow_gpm(record) or 0
    pressure     = _safe_get(record, "hydraulic_pressure_standard_psi") or 0
    hf_available = _safe_get(record, "high_flow_available")
    hf_unconf    = _hf_present_unconfirmed(record)
    h = RULES["hydraulic"]

    # Tier 1: universal for all CTLs
    tier1_note = "Compatible -- standard bucket, forks, broom, light auger, grapple"

    # Tier 2: standard flow and pressure driven
    if std_flow >= h["tier2_min_standard_gpm"] and pressure >= h["pressure_standard_min_psi"]:
        tier2_ok   = True
        tier2_note = "Compatible -- auger (rock), breaker, chain trencher, tiller, compactor"
    elif std_flow >= 15:
        tier2_ok   = True
        tier2_note = "Marginal -- light Tier 2 work possible; reduced performance on demanding attachments"
    else:
        tier2_ok   = False
        tier2_note = "Not recommended -- standard flow too low for sustained Tier 2 attachments"

    # Tier 3: high flow required
    if hf_available is False and std_flow < h["tier3_hard_disqualifier_gpm"]:
        tier3_ok   = False
        tier3_note = ("Not compatible -- no high-flow package; "
                      "forestry mulcher, cold planer, and brush cutter not supported")
    elif hf_unconf:
        tier3_ok   = True
        tier3_note = ("High-flow available but GPM unconfirmed -- likely Tier 3 capable; "
                      "verify aux_flow_high_gpm before committing to large mulchers or cold planers")
    elif hf_gpm >= h["tier3_full_mulcher_gpm"]:
        tier3_ok   = True
        tier3_note = (f"Fully capable -- {hf_gpm:.0f} GPM high-flow; "
                      "mulchers, brush cutters, cold planer, stump grinder all supported")
    elif hf_gpm >= h["tier3_capable_gpm"]:
        tier3_ok   = True
        tier3_note = (f"Capable -- {hf_gpm:.0f} GPM high-flow; "
                      "brush cutter, stump grinder, rock trencher; large mulchers may cavitate")
    elif hf_gpm > 0:
        tier3_ok   = False
        tier3_note = (f"Marginal -- {hf_gpm:.0f} GPM only; "
                      "Tier 3 attachments will underperform; not recommended")
    else:
        tier3_ok   = False
        tier3_note = "Unknown high-flow capability -- verify before running Tier 3 attachments"

    return {
        "tier_1_low_demand": {
            "compatible": True,
            "summary": tier1_note,
            "attachments": [
                "Bucket", "Pallet forks", "Broom/sweeper", "Box blade",
                "Grapple", "Snow blade", "Light auger", "Landscape rake",
            ],
        },
        "tier_2_medium_demand": {
            "compatible": tier2_ok,
            "summary": tier2_note,
            "attachments": [
                "Auger (rock/large dia.)", "Hydraulic breaker", "Chain trencher",
                "Soil tiller", "Vibratory compactor", "Small cold planer",
            ],
        },
        "tier_3_high_demand": {
            "compatible": tier3_ok,
            "summary": tier3_note,
            "attachments": [
                "Forestry mulcher", "Brush/rotary cutter", "Large cold planer",
                "Rock trencher", "Stump grinder", "Wood chipper",
            ],
        },
    }


# ---------------------------------------------------------------------------
# LISTING VALUE HIGHLIGHTS
# ---------------------------------------------------------------------------

def _compute_listing_value_highlights(record: MachineRecord) -> list[str]:
    """
    Generate a prioritized list of listing-worthy features.
    Order matters -- higher items belong in the title or first sentence.
    """
    highlights: list[str] = []

    hours      = _safe_get(record, "hours")
    brand      = (_safe_get(record, "brand") or "").lower().strip()
    hf         = _safe_get(record, "high_flow_available")
    hf_gpm     = _effective_high_flow_gpm(record)
    hf_unconf  = _hf_present_unconfirmed(record)
    cab        = _safe_get(record, "enclosed_cab_available")
    lift       = (_safe_get(record, "lift_path") or "").lower()
    two_spd    = _safe_get(record, "two_speed_available")
    ride       = _safe_get(record, "ride_control_available")
    track_pct  = _safe_get(record, "track_condition_pct")
    roc        = _safe_get(record, "rated_operating_capacity_lbs")
    hp         = _safe_get(record, "horsepower_hp")

    # Hours
    if hours is not None:
        for threshold, label in RULES["hours_labels"]:
            if threshold is None or hours <= threshold:
                if hours <= 1500:
                    highlights.append(
                        f"[HIGH VALUE] {label} ({int(hours):,} hrs) -- lead with hours in title"
                    )
                elif hours <= 3000:
                    highlights.append(f"[NOTE] {int(hours):,} hrs -- solid working machine")
                else:
                    highlights.append(
                        f"[CAUTION] {int(hours):,} hrs -- price accordingly; emphasize service history"
                    )
                break

    # Brand tier
    for tier_key, tier_data in RULES["brand_tiers"].items():
        if brand in tier_data["brands"]:
            if tier_key == "tier1":
                highlights.append(
                    f"[HIGH VALUE] {tier_data['label']} ({brand.title()}) -- lead with brand name in title"
                )
            elif tier_key == "tier2":
                highlights.append(
                    f"[NOTE] {tier_data['label']} ({brand.title()}) -- mention dealer support network"
                )
            else:
                highlights.append(
                    f"[NOTE] {tier_data['label']} ({brand.title()}) -- emphasize specs over brand name"
                )
            break

    # High flow
    if hf is True and hf_gpm:
        highlights.append(
            f"[HIGH VALUE] High-Flow Hydraulics ({hf_gpm:.0f} GPM) -- "
            "call out explicitly; opens mulching and forestry attachment market"
        )
    elif hf_unconf:
        highlights.append(
            "[HIGH VALUE] High-Flow Hydraulics (GPM unconfirmed) -- "
            "call out in listing; verify GPM from spec sheet before advertising"
        )
    elif hf is False:
        highlights.append(
            "[NOTE] No High-Flow -- positions machine for standard attachment work only"
        )

    # Enclosed cab
    if cab is True:
        highlights.append(
            "[HIGH VALUE] Enclosed Cab -- all-weather use, debris protection; "
            "significant comfort premium over ROPS"
        )
    elif cab is False:
        highlights.append(
            "[NOTE] ROPS (Open Cab) -- limits buyer pool; "
            "note if heat or AC is not available"
        )

    # Lift path
    if lift == "vertical":
        highlights.append(
            "[VALUE] Vertical Lift -- higher dump height; "
            "preferred for truck-height loading and stockpiling"
        )
    elif lift == "radial":
        highlights.append(
            "[NOTE] Radial Lift -- suited for digging and grading; "
            "lower max dump height than vertical"
        )

    # 2-speed
    if two_spd is True:
        highlights.append(
            "[VALUE] 2-Speed -- road travel between sites; "
            "important for snow removal and large-area work"
        )
    elif two_spd is False:
        highlights.append(
            "[NOTE] Single Speed -- note for buyers who reposition frequently"
        )

    # Ride control
    if ride is True:
        highlights.append(
            "[VALUE] Ride Control -- reduced material spillage at travel speed; "
            "comfort upgrade worth noting"
        )

    # Track condition
    if track_pct is not None:
        if track_pct >= 80:
            highlights.append(
                f"[VALUE] Good Tracks ({int(track_pct)}%) -- "
                "call out proactively; reduces buyer concern about undercarriage cost"
            )
        elif track_pct >= 50:
            highlights.append(
                f"[NOTE] Moderate Tracks ({int(track_pct)}%) -- "
                "buyer will inspect; note condition accurately"
            )
        else:
            highlights.append(
                f"[CAUTION] Worn Tracks ({int(track_pct)}%) -- "
                "major upcoming expense; disclose upfront and price accordingly"
            )

    # Strong ROC
    if roc and roc >= 3000:
        highlights.append(
            f"[VALUE] High ROC ({int(roc):,} lb) -- "
            "strong lift capacity; worth featuring for production-use buyers"
        )

    # Strong HP
    if hp and hp >= 90:
        highlights.append(
            f"[VALUE] High HP ({int(hp)} HP) -- "
            "capable of sustained production-rate attachment work"
        )

    return highlights


# ---------------------------------------------------------------------------
# GLOBAL FLAGS AND LIMITATIONS
# ---------------------------------------------------------------------------

def _compute_global_flags(
    record: MachineRecord,
    all_scores: list[UseCaseScore],
) -> tuple[list[str], list[str]]:
    """
    Generate top-level scoring flags and a plain-language limitations list.
    Flags = notable warnings or call-outs for the scorer output.
    Limitations = things this machine objectively cannot do well.
    """
    flags: list[str] = []
    limitations: list[str] = []

    hf         = _safe_get(record, "high_flow_available")
    hf_gpm     = _effective_high_flow_gpm(record)
    hf_unconf  = _hf_present_unconfirmed(record)
    cab        = _safe_get(record, "enclosed_cab_available")
    two_spd    = _safe_get(record, "two_speed_available")
    lift       = (_safe_get(record, "lift_path") or "").lower()
    hp         = _safe_get(record, "horsepower_hp") or 0
    roc        = _safe_get(record, "rated_operating_capacity_lbs") or 0
    pressure   = _safe_get(record, "hydraulic_pressure_standard_psi")
    track_pct  = _safe_get(record, "track_condition_pct")

    # High flow flags
    if hf is False:
        flags.append(
            "NO HIGH-FLOW: Tier 3 attachments (mulcher, brush cutter, cold planer) not supported"
        )
        limitations.append("forestry mulching, large cold planing, and production-rate brush cutting")
    elif hf_unconf:
        flags.append(
            "HIGH-FLOW UNCONFIRMED GPM: High-flow package present but aux_flow_high_gpm not on record"
            " -- verify before advertising Tier 3 capability; scores capped on high-demand use cases"
        )
    elif hf_gpm and hf_gpm < 30:
        flags.append(
            f"MARGINAL HIGH-FLOW: {hf_gpm:.0f} GPM -- "
            "Tier 3 work possible but at reduced performance"
        )

    # Cab flags
    if cab is False:
        flags.append(
            "OPEN CAB (ROPS): Operator exposure limits use cases; "
            "forestry and heavy debris-generating work not recommended"
        )
        limitations.append("forestry mulching and debris-intensive work without enclosed cab")

    # 2-speed flags
    if two_spd is False:
        flags.append(
            "SINGLE-SPEED: Productivity limited on large sites and snow removal routes"
        )
        limitations.append("large-area snow removal and frequent multi-zone repositioning")

    # Lift path flags
    if lift == "radial":
        flags.append(
            "RADIAL LIFT: Lower max dump height than vertical lift; "
            "truck-height loading less efficient"
        )

    # HP flags
    if 0 < hp < 65:
        flags.append("LOWER HP: Sustained production-rate attachment work may stress engine")
        limitations.append("sustained high-demand hydraulic attachment work at lower HP")

    # ROC flags
    if 0 < roc < 2000:
        flags.append("LOWER ROC: Heavy material handling will require additional passes")
        limitations.append("production-rate material handling and truck loading at this ROC")

    # Pressure flags
    if pressure is not None and pressure < 2800:
        flags.append(
            f"LOW PRESSURE ({int(pressure)} PSI): "
            "Rock trenching and hydraulic breakers may underperform"
        )
        limitations.append("rock trenching and hydraulic breaker work at this pressure")

    # Track condition
    if track_pct is not None and track_pct < 40:
        flags.append(
            f"WORN TRACKS ({int(track_pct)}%): "
            "Major upcoming expense -- disclose and price accordingly"
        )

    # Hard-disqualified use cases
    hard_fails = [
        uc.use_case for uc in all_scores
        if uc.score == 0 and uc.triggered_hard_gates
    ]
    if hard_fails:
        flags.append(f"HARD DISQUALIFIED: {', '.join(hard_fails)}")

    return flags, limitations


# ---------------------------------------------------------------------------
# SUMMARY SENTENCES
# ---------------------------------------------------------------------------

# Map full use case label -> short human-readable phrase for summary sentences.
USE_CASE_SHORT_LABELS: dict[str, str] = {
    "Grading / Site Prep":                      "grading and site prep",
    "Material Handling / Loading":              "material handling and truck loading",
    "Light Land Clearing":                      "light land clearing",
    "Forestry Mulching":                        "production forestry mulching",
    "Trenching (Standard -- Soft Ground)":      "utility trenching",
    "Trenching (Rock / Hard Ground)":           "rock trenching",
    "Demolition / Breaking":                    "demolition and breaking",
    "Snow Removal":                             "snow removal",
    "Cold Planing / Asphalt Milling":           "cold planing and asphalt milling",
    "Stump Grinding":                           "stump grinding",
    "Auger Work (Light Soil / Small Diameter)": "auger work",
}

# Map limitation content keywords -> clean short phrase for not_ideal_for sentence.
LIMITATION_PHRASES: list[tuple[str, str]] = [
    ("forestry mulching",     "production forestry mulching"),
    ("cold plan",             "large cold-planing attachments"),
    ("brush cut",             "production-rate brush cutting"),
    ("truck load",            "heavy truck-height loading"),
    ("snow removal",          "large-area snow removal operations"),
    ("repositioning",         "frequent multi-zone site repositioning"),
    ("enclosed cab",          "debris-intensive work without a cab"),
    ("hydraulic breaker",     "sustained hydraulic breaker work"),
    ("rock trench",           "hard-ground and rock trenching"),
    ("lower hp",              "sustained production-rate hydraulic work"),
    ("material handling",     "production-rate material handling"),
]


def _shorten_limitation(raw: str) -> str:
    """Map a raw limitation string to a clean short phrase for summary sentences."""
    raw_lower = raw.lower()
    for keyword, phrase in LIMITATION_PHRASES:
        if keyword in raw_lower:
            return phrase
    return raw[:80].rstrip(",;.")


def _generate_summaries(
    capability_class: str,
    top_use_cases: list[UseCaseScore],
    limitations: list[str],
    record: MachineRecord,
) -> tuple[str, str]:
    """Generate natural-language best_for and not_ideal_for summary sentences."""
    hf      = _safe_get(record, "high_flow_available")
    hf_gpm  = _effective_high_flow_gpm(record)
    cab     = _safe_get(record, "enclosed_cab_available")
    two_spd = _safe_get(record, "two_speed_available")
    lift    = (_safe_get(record, "lift_path") or "").lower()
    roc     = _safe_get(record, "rated_operating_capacity_lbs") or 0

    # Build best-for phrase from top scored use cases (score >= 65)
    good_cases = [uc for uc in top_use_cases if uc.score >= 65]
    if good_cases:
        short_labels = []
        for uc in good_cases[:3]:
            phrase = USE_CASE_SHORT_LABELS.get(uc.use_case, uc.use_case.lower())
            short_labels.append(phrase)

        if len(short_labels) == 1:
            core = short_labels[0]
        elif len(short_labels) == 2:
            core = f"{short_labels[0]} and {short_labels[1]}"
        else:
            core = f"{short_labels[0]}, {short_labels[1]}, and {short_labels[2]}"

        best = f"Best suited for {core}."

        # Append one feature note if it adds meaningful context
        if (hf is True or hf_gpm) and capability_class in ("C", "D"):
            best += " High-flow hydraulics significantly expand attachment options."
        elif cab is True and capability_class in ("C", "D"):
            best += " Enclosed cab enables all-weather and debris-generating work."
        elif lift == "vertical" and roc >= 2800:
            best += " Vertical lift and strong ROC suit production-rate loading."
        elif two_spd is True and capability_class == "A":
            best += " 2-speed improves site-to-site productivity."
    else:
        best = "General-purpose CTL suited for standard construction and landscaping work."

    # Build not-ideal-for phrase from limitations -- deduplicate short phrases
    if limitations:
        seen: set[str] = set()
        short_lims: list[str] = []
        for lim in limitations:
            phrase = _shorten_limitation(lim)
            if phrase not in seen:
                seen.add(phrase)
                short_lims.append(phrase)
            if len(short_lims) == 2:
                break

        if len(short_lims) == 1:
            not_ideal = f"Not ideal for {short_lims[0]}."
        else:
            not_ideal = f"Not ideal for {short_lims[0]} or {short_lims[1]}."
    else:
        not_ideal = "No significant limitations identified based on available spec data."

    return best, not_ideal


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def score_ctl(record: MachineRecord) -> ScorerResult:
    """
    Score a CTL machine record against all use cases and return a ScorerResult.

    Args:
        record: MachineRecord with machine specs and feature flags.

    Returns:
        ScorerResult containing capability class, ranked use cases, attachment
        compatibility, listing highlights, flags, and limitations.
    """
    # 1. Compute capability class (existing A/B/C/D)
    cap_class, cap_label = _compute_capability_class(record)

    # 1b. Frame class (new identity layer: small_frame / medium_frame / large_frame)
    frame_class, frame_class_label = _compute_frame_class(record)

    # 1c. Hydraulic tier (standard / high_flow / enhanced_high_flow)
    hyd_tier, hyd_tier_label = _compute_hydraulic_tier_ctl(record)

    # 1d. CTL profile (7-profile identity model)
    profile, profile_label = _compute_ctl_profile(frame_class, hyd_tier, record)

    # 2. Score all use cases
    all_scored: list[UseCaseScore] = []
    for key in RULES["use_cases"]:
        all_scored.append(_score_use_case(key, record))

    # 2b. Apply profile bonuses and size identity caps
    all_scored = _apply_profile_adjustments(profile, all_scored, record)

    # 3. Sort by score descending
    all_scored_sorted = sorted(all_scored, key=lambda x: x.score, reverse=True)

    # 3b. Apply brand channel sort to top results (reorders for summary, not scores)
    brand_raw = _safe_get(record, "brand")
    top_3_sorted = _apply_brand_channel_sort_ctl(brand_raw, all_scored_sorted[:5])
    top_3 = top_3_sorted[:3]

    # 4. Attachment compatibility
    attachment_compat = _compute_attachment_compatibility(record)

    # 5. Listing value highlights
    highlights = _compute_listing_value_highlights(record)

    # 6. Global flags and limitations
    global_flags, limitations = _compute_global_flags(record, all_scored)

    # 7. Summary sentences
    best_for, not_ideal = _generate_summaries(cap_class, top_3, limitations, record)

    return ScorerResult(
        capability_class=cap_class,
        capability_class_label=cap_label,
        frame_class=frame_class,
        frame_class_label=frame_class_label,
        hydraulic_tier=hyd_tier,
        hydraulic_tier_label=hyd_tier_label,
        profile=profile,
        profile_label=profile_label,
        top_use_cases=top_3,
        all_use_cases=all_scored_sorted,
        attachment_compatibility=attachment_compat,
        listing_value_highlights=highlights,
        scoring_flags=global_flags,
        limitations=limitations,
        best_for_summary=best_for,
        not_ideal_for_summary=not_ideal,
    )


# ---------------------------------------------------------------------------
# OUTPUT FORMATTER
# ---------------------------------------------------------------------------

def format_result(result: ScorerResult, show_debug: bool = False) -> str:
    """
    Pretty-print a ScorerResult for CLI / logging use.
    Pass show_debug=True to include base scores and transparency fields.
    """
    lines: list[str] = []
    sep = "-" * 62

    lines.append(sep)
    lines.append("  CTL USE CASE SCORE REPORT")
    lines.append(sep)

    lines.append(f"\nCAPABILITY CLASS: {result.capability_class}")
    lines.append(f"  {result.capability_class_label}")

    lines.append("\nTOP USE CASES:")
    for uc in result.top_use_cases:
        filled = uc.score // 10
        bar = "#" * filled + "." * (10 - filled)
        lines.append(f"  {uc.score:3d}/100  [{bar}]  {uc.use_case}  ({uc.label})")
        for reason in uc.reasons:
            lines.append(f"              -> {reason}")
        if show_debug:
            lines.append(f"              [base={uc.base_score_before_adjustments}]")

    lines.append("\nALL USE CASES:")
    for uc in result.all_use_cases:
        filled = uc.score // 10
        bar = "#" * filled + "." * (10 - filled)
        lines.append(f"  {uc.score:3d}/100  [{bar}]  {uc.use_case}  ({uc.label})")
        if show_debug and (uc.applied_caps or uc.applied_penalties or uc.triggered_hard_gates):
            for g in uc.triggered_hard_gates:
                lines.append(f"      [GATE] {g}")
            for c in uc.applied_caps:
                lines.append(f"      [CAP]  {c}")
            for p in uc.applied_penalties:
                lines.append(f"      [PEN]  {p}")

    lines.append("\nATTACHMENT COMPATIBILITY:")
    for tier_key, tier_data in result.attachment_compatibility.items():
        status = "YES" if tier_data["compatible"] else "NO "
        label = tier_key.replace("_", " ").title()
        lines.append(f"  [{status}] {label}")
        lines.append(f"        {tier_data['summary']}")

    lines.append("\nLISTING VALUE HIGHLIGHTS:")
    for h in result.listing_value_highlights:
        lines.append(f"  {h}")

    lines.append("\nSCORING FLAGS:")
    if result.scoring_flags:
        for f in result.scoring_flags:
            lines.append(f"  {f}")
    else:
        lines.append("  None")

    lines.append("\nLIMITATIONS:")
    if result.limitations:
        for lim in result.limitations:
            lines.append(f"  - {lim}")
    else:
        lines.append("  None identified")

    lines.append(f"\nBEST FOR:      {result.best_for_summary}")
    lines.append(f"NOT IDEAL FOR: {result.not_ideal_for_summary}")
    lines.append(f"\n{sep}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TEST HARNESS
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # ------------------------------------------------------------------
    # Test 1: Small open-cab machine, no high flow, single speed
    # Profile: Bobcat T190 (legacy small CTL)
    # Expect: Class A | High: auger, trenching, grading
    #         Hard zero: forestry, cold planing | Low: snow removal
    # ------------------------------------------------------------------
    t1 = MachineRecord(
        horsepower_hp=56,
        rated_operating_capacity_lbs=1900,
        operating_weight_lbs=7920,
        aux_flow_standard_gpm=20.7,
        aux_flow_high_gpm=None,
        hydraulic_pressure_standard_psi=3335,
        hydraulic_pressure_high_psi=None,
        bucket_hinge_pin_height_in=None,
        high_flow_available=False,
        two_speed_available=False,
        enclosed_cab_available=False,
        ride_control_available=False,
        lift_path="radial",
        brand="Bobcat",
        hours=4200,
        track_condition_pct=45,
    )
    print("=== TEST 1: Bobcat T190 -- Small, Open Cab, No High-Flow ===")
    print("Expect: Class A | High: auger, trenching | Zero: forestry, cold planing")
    print(format_result(score_ctl(t1), show_debug=True))

    # ------------------------------------------------------------------
    # Test 2: Mid machine, enclosed cab, NO high flow
    # Profile: Case TR270 without high-flow option
    # Expect: Class B | High: grading, trenching | Hard zero: forestry, cold planing
    # ------------------------------------------------------------------
    t2 = MachineRecord(
        horsepower_hp=68,
        rated_operating_capacity_lbs=2700,
        operating_weight_lbs=8270,
        aux_flow_standard_gpm=24.2,
        aux_flow_high_gpm=None,
        hydraulic_pressure_standard_psi=3050,
        hydraulic_pressure_high_psi=None,
        bucket_hinge_pin_height_in=123.0,
        high_flow_available=False,
        two_speed_available=True,
        enclosed_cab_available=True,
        ride_control_available=False,
        lift_path="radial",
        brand="Case",
        hours=1800,
        track_condition_pct=75,
    )
    print("=== TEST 2: Case TR270 -- Mid, Enclosed Cab, No High-Flow ===")
    print("Expect: Class B | High: grading, trenching | Zero: forestry, cold planing")
    print(format_result(score_ctl(t2), show_debug=True))

    # ------------------------------------------------------------------
    # Test 3: Mid machine, enclosed cab, confirmed high flow (32.4 GPM)
    # Profile: Case TR270 with high-flow package
    # Expect: Class B | High: grading, trenching | Good: stump, light clearing
    #         Fair: forestry (marginal GPM) | Scored not zero: cold planing
    # ------------------------------------------------------------------
    t3 = MachineRecord(
        horsepower_hp=68,
        rated_operating_capacity_lbs=2700,
        operating_weight_lbs=8270,
        aux_flow_standard_gpm=24.2,
        aux_flow_high_gpm=32.4,
        hydraulic_pressure_standard_psi=3050,
        hydraulic_pressure_high_psi=3050,
        bucket_hinge_pin_height_in=123.0,
        high_flow_available=True,
        two_speed_available=True,
        enclosed_cab_available=True,
        ride_control_available=False,
        lift_path="radial",
        brand="Case",
        hours=2400,
        track_condition_pct=70,
    )
    print("=== TEST 3: Case TR270 -- Mid, Enclosed Cab, Confirmed High-Flow (32.4 GPM) ===")
    print("Expect: Class B | High: grading, trenching | Good: stump | Fair: forestry")
    print(format_result(score_ctl(t3), show_debug=True))

    # ------------------------------------------------------------------
    # Test 4: Large vertical-lift machine, strong ROC, high flow
    # Profile: JD 333G class (100 HP, 3600 lb ROC, 34 GPM)
    # Expect: Class C | Excellent: material handling, land clearing
    #         Good: forestry (34 GPM -- capable but not full mulcher)
    # ------------------------------------------------------------------
    t4 = MachineRecord(
        horsepower_hp=100,
        rated_operating_capacity_lbs=3600,
        operating_weight_lbs=11200,
        aux_flow_standard_gpm=27.0,
        aux_flow_high_gpm=34.0,
        hydraulic_pressure_standard_psi=3335,
        hydraulic_pressure_high_psi=3335,
        bucket_hinge_pin_height_in=133.0,
        high_flow_available=True,
        two_speed_available=True,
        enclosed_cab_available=True,
        ride_control_available=True,
        lift_path="vertical",
        brand="John Deere",
        hours=950,
        track_condition_pct=85,
    )
    print("=== TEST 4: JD 333G Class -- Large, Vertical Lift, High-Flow ===")
    print("Expect: Class C | Excellent: material handling, clearing | Good: forestry, cold planing")
    print(format_result(score_ctl(t4), show_debug=True))

    # ------------------------------------------------------------------
    # Test 5: Class D forestry machine -- very high GPM, enclosed cab
    # Profile: Cat 299D3 XHP (106 HP, 40 GPM, single-speed)
    # Expect: Class D | Excellent: forestry, cold planing, material handling
    #         Poor: snow removal (single-speed penalty)
    # ------------------------------------------------------------------
    t5 = MachineRecord(
        horsepower_hp=106,
        rated_operating_capacity_lbs=3550,
        operating_weight_lbs=11500,
        aux_flow_standard_gpm=27.0,
        aux_flow_high_gpm=40.0,
        hydraulic_pressure_standard_psi=3550,
        hydraulic_pressure_high_psi=4061,
        bucket_hinge_pin_height_in=131.0,
        high_flow_available=True,
        two_speed_available=False,       # XHP is single-speed
        enclosed_cab_available=True,
        ride_control_available=True,
        lift_path="vertical",
        brand="Caterpillar",
        hours=780,
        track_condition_pct=88,
    )
    print("=== TEST 5: Cat 299D3 XHP -- Class D, Forestry-Ready, Single-Speed ===")
    print("Expect: Class D | Excellent: forestry, cold planing | Poor: snow removal")
    print(format_result(score_ctl(t5), show_debug=True))

    # ------------------------------------------------------------------
    # Test 6: High-flow flag True but GPM not on record
    # Tests the unconfirmed-GPM logic (Part 2 fix)
    # Expect: NOT hard-disqualified | Capped on Tier 3 use cases
    #         | GPM unconfirmed flag throughout | Partial credit on HF scores
    # ------------------------------------------------------------------
    t6 = MachineRecord(
        horsepower_hp=90,
        rated_operating_capacity_lbs=3200,
        operating_weight_lbs=10000,
        aux_flow_standard_gpm=25.0,
        aux_flow_high_gpm=None,           # GPM not on record
        hydraulic_pressure_standard_psi=3050,
        hydraulic_pressure_high_psi=None,
        bucket_hinge_pin_height_in=128.0,
        high_flow_available=True,         # flag says yes, GPM unknown
        two_speed_available=True,
        enclosed_cab_available=True,
        ride_control_available=False,
        lift_path="vertical",
        brand="New Holland",
        hours=1200,
        track_condition_pct=80,
    )
    print("=== TEST 6: High-Flow Flag True, GPM Missing (Unconfirmed) ===")
    print("Expect: NOT hard-disqualified | Capped Tier 3 scores | GPM unconfirmed flag")
    print(format_result(score_ctl(t6), show_debug=True))


# ---------------------------------------------------------------------------
# MTM REGISTRY ADAPTER
# ---------------------------------------------------------------------------

def machine_record_from_registry(registry_record: dict) -> MachineRecord:
    """
    Build a MachineRecord from an MTM CTL registry record.
    """
    specs = registry_record.get("specs") or {}
    dealer_inputs = registry_record.get("dealer_inputs") or {}
    options = registry_record.get("options") or {}

    # Feature flag: high_flow_available
    hf_gpm = specs.get("aux_flow_high_gpm")
    if options.get("high_flow") is True or (hf_gpm is not None and hf_gpm > 0):
        high_flow_available = True
    elif options.get("high_flow") is False:
        high_flow_available = False
    else:
        high_flow_available = None

    # Feature flag: two_speed_available
    travel_high = specs.get("travel_speed_high_mph")
    if options.get("two_speed") is True or (travel_high is not None and travel_high > 7):
        two_speed_available = True
    elif options.get("two_speed") is False:
        two_speed_available = False
    else:
        two_speed_available = None

    # Feature flag: enclosed_cab_available
    cab_type = (dealer_inputs.get("cab_type") or "").lower().strip()
    if cab_type in ("enclosed", "erops", "closed", "cab"):
        enclosed_cab_available = True
    elif cab_type in ("open", "rops", "canopy", "orops"):
        enclosed_cab_available = False
    else:
        enclosed_cab_available = None

    # Feature flag: ride_control_available
    ride_raw = options.get("ride_control")
    ride_control_available = ride_raw if isinstance(ride_raw, bool) else None

    return MachineRecord(
        horsepower_hp=specs.get("horsepower_hp"),
        rated_operating_capacity_lbs=specs.get("rated_operating_capacity_lbs"),
        operating_weight_lbs=specs.get("operating_weight_lbs"),
        aux_flow_standard_gpm=specs.get("aux_flow_standard_gpm"),
        aux_flow_high_gpm=specs.get("aux_flow_high_gpm"),
        hydraulic_pressure_standard_psi=specs.get("hydraulic_pressure_standard_psi"),
        hydraulic_pressure_high_psi=specs.get("hydraulic_pressure_high_psi"),
        bucket_hinge_pin_height_in=specs.get("bucket_hinge_pin_height_in"),
        lift_path=specs.get("lift_path"),
        brand=registry_record.get("manufacturer") or registry_record.get("brand"),
        hours=dealer_inputs.get("hours"),
        track_condition_pct=dealer_inputs.get("track_condition_pct"),
        high_flow_available=high_flow_available,
        two_speed_available=two_speed_available,
        enclosed_cab_available=enclosed_cab_available,
        ride_control_available=ride_control_available,
    )


def score_registry_record(registry_record: dict) -> ScorerResult:
    """
    Convert MTM registry record -> MachineRecord -> score result.
    """
    return score_ctl(machine_record_from_registry(registry_record))


def batch_score_registry(records: list[dict]) -> list[dict]:
    """
    Score a batch of MTM CTL registry records and return compact summaries.
    """
    summaries = []
    for registry_record in records:
        result = score_registry_record(registry_record)
        top3 = result.top_use_cases[:3]
        summaries.append({
            "model_slug": registry_record.get("model_slug"),
            "manufacturer": registry_record.get("manufacturer"),
            "model": registry_record.get("model"),
            "capability_class": result.capability_class,
            "capability_class_label": result.capability_class_label,
            "frame_class": result.frame_class,
            "frame_class_label": result.frame_class_label,
            "hydraulic_tier": result.hydraulic_tier,
            "profile": result.profile,
            "profile_label": result.profile_label,
            "top_use_cases": [
                {"use_case": uc.use_case, "score": uc.score, "label": uc.label}
                for uc in top3
            ],
            "best_for_summary": result.best_for_summary,
            "not_ideal_for_summary": result.not_ideal_for_summary,
            "tier3_compatible": result.attachment_compatibility["tier_3_high_demand"]["compatible"],
            "tier3_summary": result.attachment_compatibility["tier_3_high_demand"]["summary"],
            "flags": result.scoring_flags,
        })
    return summaries


# ---------------------------------------------------------------------------
# REGISTRY ADAPTER TEST
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    sample_registry_record = {
        "model_slug": "case_tr270",
        "manufacturer": "Case",
        "model": "TR270",
        "specs": {
            "horsepower_hp": 68,
            "rated_operating_capacity_lbs": 2700,
            "operating_weight_lbs": 8270,
            "aux_flow_standard_gpm": 24.2,
            "aux_flow_high_gpm": 32.4,
            "hydraulic_pressure_standard_psi": 3050,
            "hydraulic_pressure_high_psi": 3050,
            "bucket_hinge_pin_height_in": 123.0,
            "lift_path": "radial",
            "travel_speed_high_mph": 8.4,
        },
        "dealer_inputs": {
            "hours": 2400,
            "track_condition_pct": 70,
            "cab_type": "enclosed",
        },
        "options": {
            "high_flow": True,
            "two_speed": True,
            "ride_control": False,
        },
    }

    print("=== REGISTRY ADAPTER TEST ===")
    registry_result = score_registry_record(sample_registry_record)
    print(format_result(registry_result, show_debug=True))


# ---------------------------------------------------------------------------
# CSV EXPORT
# ---------------------------------------------------------------------------

import csv
import json


# Maps the RULES use_case label strings to short CSV column keys.
_USE_CASE_LABEL_TO_KEY: dict[str, str] = {
    "Grading / Site Prep":                      "grading",
    "Material Handling / Loading":              "material_handling",
    "Light Land Clearing":                      "land_clearing",
    "Forestry Mulching":                        "forestry_mulching",
    "Trenching (Standard -- Soft Ground)":      "trenching",
    "Trenching (Rock / Hard Ground)":           "rock_trenching",
    "Demolition / Breaking":                    "demolition",
    "Snow Removal":                             "snow_removal",
    "Cold Planing / Asphalt Milling":           "cold_planing",
    "Stump Grinding":                           "stump_grinding",
    "Auger Work (Light Soil / Small Diameter)": "auger",
}


def _normalize_registry_record(record: dict) -> dict:
    """
    Map a native MTM CTL registry record to the format expected by
    machine_record_from_registry (options + dealer_inputs keys).

    Registry stores feature flags in feature_flags{}; the adapter
    expects them in options{} (short keys) and dealer_inputs{cab_type}.
    Specs and identity fields pass through unchanged.
    Does not modify the original dict.
    """
    ff = record.get("feature_flags") or {}

    options = {
        "high_flow":    ff.get("high_flow_available"),
        "two_speed":    ff.get("two_speed_available"),
        "ride_control": ff.get("ride_control_available"),
    }

    # Map enclosed_cab_available bool -> cab_type string for the adapter
    cab_bool = ff.get("enclosed_cab_available")
    if cab_bool is True:
        cab_type = "enclosed"
    elif cab_bool is False:
        cab_type = "open"
    else:
        cab_type = None

    dealer_inputs: dict = {}
    if cab_type is not None:
        dealer_inputs["cab_type"] = cab_type

    normalized = dict(record)
    normalized["options"] = options
    normalized["dealer_inputs"] = dealer_inputs
    return normalized


def export_ctl_use_case_table(registry_path: str, output_csv_path: str) -> None:
    """
    Load CTL registry JSON, score all production machines,
    and export a CSV table for review.
    """
    with open(registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records") or data

    # Only score production-quality records -- skip stubs and seed-only rows
    scoreable = [
        r for r in records
        if r.get("registry_tier") in ("production", "production_candidate")
        and r.get("status") not in ("seed_only",)
    ]

    rows = []

    for record in scoreable:
        try:
            normalized = _normalize_registry_record(record)
            result = score_registry_record(normalized)

            # Build label -> score lookup from all_use_cases
            score_map: dict[str, int] = {
                uc.use_case: uc.score for uc in result.all_use_cases
            }
            s = {key: score_map.get(label) for label, key in _USE_CASE_LABEL_TO_KEY.items()}

            top = result.top_use_cases
            specs = record.get("specs") or {}

            row = {
                "model_slug":             record.get("model_slug"),
                "manufacturer":           record.get("manufacturer"),
                "model":                  record.get("model"),
                "registry_tier":          record.get("registry_tier"),
                "status":                 record.get("status"),
                "machine_class":          result.capability_class_label,

                "grading_score":          s["grading"],
                "material_handling_score": s["material_handling"],
                "land_clearing_score":    s["land_clearing"],
                "forestry_mulching_score": s["forestry_mulching"],
                "trenching_score":        s["trenching"],
                "rock_trenching_score":   s["rock_trenching"],
                "demolition_score":       s["demolition"],
                "snow_removal_score":     s["snow_removal"],
                "cold_planing_score":     s["cold_planing"],
                "stump_grinding_score":   s["stump_grinding"],
                "auger_score":            s["auger"],

                "top_use_case_1":  top[0].use_case if len(top) > 0 else None,
                "top_use_case_2":  top[1].use_case if len(top) > 1 else None,
                "top_use_case_3":  top[2].use_case if len(top) > 2 else None,

                "tier3_compatible": result.attachment_compatibility["tier_3_high_demand"]["compatible"],

                "hp":              specs.get("horsepower_hp"),
                "roc":             specs.get("rated_operating_capacity_lbs"),
                "operating_weight": specs.get("operating_weight_lbs"),
                "std_flow":        specs.get("aux_flow_standard_gpm"),
                "high_flow_gpm":   specs.get("aux_flow_high_gpm"),
                "lift_path":       specs.get("lift_path"),
            }

            rows.append(row)

        except Exception as e:
            print(f"  [SKIP] {record.get('model_slug')}: {e}")

    if not rows:
        print("No rows to export.")
        return

    fieldnames = list(rows[0].keys())

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} records -> {output_csv_path}")


# ---------------------------------------------------------------------------
# EXPORT RUNNER
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    registry_file = "registry/mtm_ctl_registry_v1_17.json"
    output_file = "ctl_use_case_scores.csv"
    export_ctl_use_case_table(registry_file, output_file)
