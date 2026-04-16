"""
mini_ex_use_case_scorer.py
===========================
MTM Listings -- Mini Excavator Use Case Scoring Engine V1
Derived from: MTM Mini Excavator Logic Design Document +
              MTM Mini Excavator Research Validation Memo (Safe-to-Code V1 Threshold Set)
Structural template: skid_steer_use_case_scorer.py

Scores a mini excavator registry record against 11 core use cases and 7 attachment
use cases using spec-driven rules. Returns capability class, hydraulic tier, ranked
use cases, attachment scores, listing highlights, best_for / not_ideal_for summaries,
confidence level, and scoring flags.

Key mini excavator scoring differences vs. skid steer:
  - Primary classifier: operating_weight_lbs (not ROC)
  - Dig depth and dump height are the dominant use-case spec drivers
  - Tail swing type (zero / reduced / conventional) is a major differentiator
  - Aux flow in GPM (not high-flow boolean) drives hydraulic tier
  - PSI is required for breaker claims — null PSI → score = None, not 0
  - Brush cutter has a hard gate at < 12 GPM (not a soft cap)
  - Class A hard-capped at 0 on septic_installation and truck_loading
  - Class D hard-capped at 35 on tight_access_backyard_work

CAPABILITY CLASSES
------------------
Class A: 0–4,000 lbs    Micro/mini; residential landscaping, tight access
Class B: 4,001–8,000    Mid; residential construction, drainage, plumbing
Class C: 8,001–13,000   Production; septic, utility, light commercial
Class D: 13,001–20,000  Full production; deep utility, truck loading, demo

HYDRAULIC TIERS (aux_flow_primary_gpm)
---------------------------------------
Tier 0: < 6 GPM     (non-functional for powered attachments)
Tier 1: 6–9.9 GPM   (thumb, light compactor, small auger only)
Tier 2M: 10–12.9    (auger OK; breaker marginal; no brush cutter)
Tier 2F: 13–19.9    (standard breaker, grapple, auger production)
Tier 3: 20+ GPM     (heavy breaker, brush cutter, large auger)

Usage:
    from mini_ex_use_case_scorer import score_mini_ex, MachineRecord
    result = score_mini_ex(machine_record)
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class MachineRecord:
    """
    Normalized mini excavator input record.
    All fields are optional — scorer handles None gracefully.
    Field names match MTM mini excavator registry schema.
    """
    # Identity
    make: str | None = None
    model: str | None = None
    year: int | None = None

    # Core dimension specs
    operating_weight_lbs: float | None = None
    max_dig_depth_ft: float | None = None
    max_dump_height_ft: float | None = None
    max_reach_ft: float | None = None
    width_in: float | None = None                  # transport/blade-up width

    # Hydraulics
    auxiliary_hydraulics_available: bool | None = None
    aux_flow_primary_gpm: float | None = None
    aux_pressure_primary_psi: float | None = None

    # Configuration flags
    tail_swing_type: str | None = None            # "zero" | "reduced" | "conventional"
    two_speed_travel: bool | None = None
    enclosed_cab_available: bool | None = None
    hydraulic_thumb_available: bool | None = None
    retractable_undercarriage: bool | None = None
    angle_blade_available: bool | None = None
    blade_available: bool | None = None

    # Attachment configuration (beyond aux hydraulics)
    thumb_ready: bool | None = None                 # thumb mount bracket present, no thumb installed
    quick_coupler: bool | None = None               # quick coupler present
    bucket_count: int | None = None                 # number of buckets in package (None = unknown)
    trenching_bucket: bool | None = None            # narrow trenching bucket present
    ditch_bucket: bool | None = None                # ditch / cleanup bucket present
    dual_aux: bool | None = None                    # dual aux / two-way hydraulic circuit available

    # Condition / market fields
    brand: str | None = None
    hours: float | None = None
    track_condition_pct: float | None = None       # 0–100; None = unknown


@dataclass
class UseCaseScore:
    """Score result for a single use case or attachment use case."""
    use_case: str
    score: int | None                              # 0–100, or None if unassessable
    label: str                                     # Excellent / Good / Fair / Poor / Not Recommended / Unassessable
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    base_score_before_adjustments: int = 0
    applied_caps: list[str] = field(default_factory=list)
    applied_penalties: list[str] = field(default_factory=list)
    triggered_hard_gates: list[str] = field(default_factory=list)


@dataclass
class ScorerResult:
    """Full scoring result returned by score_mini_ex()."""
    capability_class: str                          # "A" | "B" | "C" | "D"
    capability_class_label: str
    size_class: str                                # "micro_small" | "mid_size" | "large_mini"
    size_class_label: str
    hydraulic_tier: str                            # "Tier 0" through "Tier 3"
    hydraulic_tier_label: str

    # Core use cases
    top_use_cases: list[UseCaseScore]             # top 3 scored
    all_use_cases: list[UseCaseScore]             # all 11, sorted descending

    # Attachment use cases
    attachment_scores: dict[str, UseCaseScore]    # keyed by attachment name

    # Summary
    listing_highlights: list[str]
    scoring_flags: list[str]
    limitations: list[str]
    best_for: list[str]
    not_ideal_for: list[str]
    best_for_summary: str
    not_ideal_for_summary: str
    confidence_level: str                          # "High" | "Medium" | "Low"
    debug_data: dict


# ---------------------------------------------------------------------------
# SAFE-TO-CODE V1 THRESHOLD SET
# Source: MTM Mini Excavator Research Validation Memo
# Do NOT modify these constants without updating the Research Validation Memo.
# ---------------------------------------------------------------------------

CLASS_BOUNDARIES = {
    "A": {"weight_max": 4000},
    "B": {"weight_max": 8000},
    "C": {"weight_max": 13000},
    "D": {"weight_max": 20000},
}

# Edge case: 4,001–4,500 lb machines with small width/dig may behave like Class A
CLASS_A_SOFT_OVERLAP = {"weight_max": 4500, "width_max": 52, "dig_max": 8.5}

DIG_DEPTH_THRESHOLDS = {
    # trenching_utility
    "utility_trench_hard_gate":    5.0,
    "utility_trench_minimum":      6.0,
    "utility_trench_production":   7.5,

    # trenching_deep
    "deep_trench_hard_gate":       8.0,
    "deep_trench_sewer_service":   9.5,
    "deep_trench_main_line":      11.0,
    "deep_trench_full":           12.5,

    # septic_installation
    "septic_hard_gate":            7.0,
    "septic_field_lines_only":     7.0,
    "septic_tank_warm_climate":    9.5,
    "septic_tank_reliable":       10.5,
    "septic_tank_commercial":     12.0,

    # footings_foundation_digging
    "footings_hard_gate":          5.0,
    "footings_frost_footing":      6.0,
    "footings_basement_perimeter": 8.5,
    "footings_deep_basement":     10.5,

    # Class A hard caps
    "class_A_septic_cap":          0,
    "class_A_truck_loading_cap":   0,
    "class_A_deep_trench_cap":    30,
}

DUMP_HEIGHT_THRESHOLDS = {
    "truck_load_hard_gate":        8.5,
    "truck_load_marginal":         9.5,
    "truck_load_single_axle":     10.5,
    "truck_load_tandem":          12.0,
    "material_load_hard_gate":     8.0,
    "material_load_minimum":       9.0,
    "material_load_standard":     10.5,
}

AUX_FLOW_THRESHOLDS = {
    # Tier classification
    "tier_0_max":                  5.9,
    "tier_1_max":                  9.9,
    "tier_2_marginal_max":        12.9,
    "tier_2_full_max":            19.9,
    "tier_3_min":                 20.0,

    # Auger
    "auger_hard_gate":             6.0,
    "auger_marginal":             10.0,
    "auger_standard":             13.0,
    "auger_large_diameter":       18.0,

    # Breaker
    "breaker_minimum_flow":       10.0,
    "breaker_marginal_flow":      12.0,
    "breaker_standard_flow":      15.0,
    "breaker_heavy_flow":         20.0,

    # Brush cutter
    "brush_cutter_hard_gate":     12.0,
    "brush_cutter_marginal":      18.0,
    "brush_cutter_standard":      18.0,
    "brush_cutter_production":    25.0,

    # Grapple
    "grapple_marginal":            8.0,
    "grapple_standard":           12.0,

    # Compactor / tilt bucket
    "compactor_minimum":           5.0,
    "tilt_bucket_minimum":         8.0,
    "tiltrotator_minimum":        15.0,
}

AUX_PSI_THRESHOLDS = {
    # Breaker
    "breaker_psi_hard_gate":    1600,
    "breaker_psi_marginal":     2000,
    "breaker_psi_standard":     2200,
    "breaker_psi_strong":       2700,
    "breaker_psi_heavy":        3000,

    # Auger
    "auger_psi_minimum":        1800,
    "auger_psi_standard":       2000,
    "auger_psi_hard_soil":      2500,

    # General
    "compactor_psi_minimum":    1500,
    "tilt_bucket_psi_minimum":  1800,
    "grapple_psi_minimum":      1800,
    "brush_cutter_psi_minimum": 2500,
}

WIDTH_THRESHOLDS = {
    # tight_access
    "access_premium":           48,
    "access_good":              60,
    "access_limited":           72,
    "access_poor":              84,
    "access_hard_gate":         84,

    # interior_demo
    "interior_premium":         48,
    "interior_standard":        60,
    "interior_penalty":         66,
    "interior_hard_cap_72":     72,
    "interior_hard_cap_84":     84,
}

HARD_CAPS = {
    "class_A_septic_installation":  0,
    "class_A_truck_loading":        0,
    "class_A_deep_trench":         30,
    "class_A_material_loading":    50,

    "interior_demo_reduced_tail":  55,
    "interior_demo_conventional":  40,
    "interior_demo_width_72":      30,
    "interior_demo_width_84":       0,

    "brush_cutter_flow_12_17":     30,
    "brush_cutter_flow_18_24":     75,

    "breaker_psi_1600_2199":       35,
    "breaker_psi_2200_2699":       70,

    "class_D_tight_access":        35,
    "class_D_interior_demo":       20,
}

SCORE_LABELS = [
    (85, "Excellent"),
    (70, "Good"),
    (50, "Fair"),
    (30, "Poor"),
    (0,  "Not Recommended"),
]

HOURS_LABELS = [
    (500,  "Like New"),
    (1500, "Low Hours"),
    (3000, "Mid Hours"),
    (5000, "High Hours"),
    (None, "Very High Hours"),
]

BRAND_TIERS = {
    "tier1": {
        "brands": ["kubota", "bobcat", "caterpillar", "cat", "john deere", "deere"],
        "label": "Tier 1 Brand",
    },
    "tier2": {
        "brands": ["komatsu", "volvo", "case", "yanmar", "doosan", "hyundai"],
        "label": "Tier 2 Brand",
    },
    "tier3": {
        "brands": ["takeuchi", "wacker neuson", "wacker", "jcb", "kobelco", "hitachi"],
        "label": "Specialty Brand",
    },
}

# ---------------------------------------------------------------------------
# SIZE CLASS BOUNDARIES (attachment-first identity model)
# Parallel to A/B/C/D cap system but used for identity framing and suppression.
# micro_small: ≤4,000 lb — tight access, landscaping, backyard
# mid_size:    4,001–13,000 lb — utility, residential construction, site work
# large_mini:  13,001–20,000 lb — heavy utility, foundation, demo, land clearing
# ---------------------------------------------------------------------------

SIZE_CLASS_BOUNDARIES = {
    "micro_small": {
        "weight_max": 4000,
        "label": "Micro/Small Mini Ex (≤4,000 lb) — tight access, landscaping, backyard work",
        "suppress": ["Interior Demolition", "Land Clearing / Site Grading"],  # cap at 45 if spec-marginal
        "boost": ["Landscaping / Irrigation", "Tight Access / Backyard Work"],
    },
    "mid_size": {
        "weight_max": 13000,
        "label": "Mid-Size Mini Ex (4,001–13,000 lb) — utility trenching, residential construction, site prep",
        "suppress": [],
        "boost": [],
    },
    "large_mini": {
        "weight_max": 20000,
        "label": "Large Mini Ex (13,001–20,000 lb) — heavy utility, foundation excavation, demo, land clearing",
        "suppress": ["Landscaping / Irrigation", "Tight Access / Backyard Work"],  # cap at 50
        "boost": ["Land Clearing / Site Grading", "Footings / Foundation Digging"],
    },
}

# Brand channel — controls output framing bias, not scores
BRAND_CHANNEL = {
    "cat":          "construction",
    "caterpillar":  "construction",
    "bobcat":       "construction",
    "komatsu":      "construction",
    "case":         "construction",
    "kobelco":      "construction",
    "hitachi":      "construction",
    "doosan":       "construction",
    "hyundai":      "construction",
    "volvo":        "construction",
    "takeuchi":     "construction",
    "jcb":          "construction",
    "kubota":       "rural",     # allows rural/property/drainage crossover
    "john deere":   "rural",
    "deere":        "rural",
    "yanmar":       "rural",
    "wacker neuson": "construction",
    "wacker":       "construction",
}

# Construction-priority use case ordering for Best For
_CONSTRUCTION_ORDER = [
    "Utility Trenching", "Deep Trenching", "Septic",
    "Residential Construction", "Footings", "Truck Loading",
    "Land Clearing", "Interior Demolition",
]
# Rural-priority use case ordering for Best For
_RURAL_ORDER = [
    "Utility Trenching", "Land Clearing", "Landscaping",
    "Footings", "Residential Construction", "Septic",
    "Tight Access",
]


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def _safe_get(record: MachineRecord, field_name: str, default=None):
    return getattr(record, field_name, default)


def _score_label(score: int | None) -> str:
    if score is None:
        return "Unassessable"
    for threshold, label in SCORE_LABELS:
        if score >= threshold:
            return label
    return "Not Recommended"


def _spec_score(value: float | None, full_credit_threshold: float,
                partial_credit_threshold: float) -> float:
    """
    Score a single spec field on a 0.0–1.0 scale.
    None → 0.3 (unknown: cautious partial credit).
    """
    if value is None:
        return 0.3
    if value >= full_credit_threshold:
        return 1.0
    if value <= partial_credit_threshold:
        return 0.0
    span = full_credit_threshold - partial_credit_threshold
    return (value - partial_credit_threshold) / span


def _compute_weighted_score(factors: list[tuple]) -> int:
    """
    Compute a weighted base score from (field_value, full_thresh, partial_thresh, weight) tuples.
    field_value is already extracted — not a field name.
    Returns 0–100 int.
    """
    total_weight = 0
    weighted_sum = 0.0
    for value, full_thresh, partial_thresh, weight in factors:
        s = _spec_score(value, full_thresh, partial_thresh)
        weighted_sum += s * weight
        total_weight += weight
    if total_weight == 0:
        return 50
    raw = weighted_sum / total_weight * 100
    return max(0, min(100, round(raw)))


# ---------------------------------------------------------------------------
# SECTION 1: CAPABILITY CLASS COMPUTATION
# ---------------------------------------------------------------------------

def _compute_capability_class(record: MachineRecord) -> tuple[str, str, list[str]]:
    """
    Classify mini excavator into Class A/B/C/D by operating weight.
    Returns (class_key, class_label, scoring_flags).

    Primary driver: operating_weight_lbs
    Edge case: 4,001–4,500 lb machines with ≤52 in width and ≤8.5 ft dig
               are flagged as "upper-range Class A behavior" but NOT re-classed.
    """
    class_labels = {
        "A": "Class A — Micro/Mini (0–4,000 lb) — Landscaping / Tight Access / Residential",
        "B": "Class B — Mid Mini Ex (4,001–8,000 lb) — Residential Construction / Drainage / Plumbing",
        "C": "Class C — Production Mini Ex (8,001–13,000 lb) — Septic / Utility / Light Commercial",
        "D": "Class D — Full Production (13,001–20,000 lb) — Deep Utility / Truck Loading / Demo",
    }

    weight = _safe_get(record, "operating_weight_lbs")
    flags: list[str] = []

    if weight is None:
        return "B", class_labels["B"] + " [weight unknown — defaulted to Class B]", [
            "Operating weight not available — capability class defaulted to B; verify before listing"
        ]

    if weight <= CLASS_BOUNDARIES["A"]["weight_max"]:
        cap_class = "A"
    elif weight <= CLASS_BOUNDARIES["B"]["weight_max"]:
        cap_class = "B"

        # Flag upper-Class-B machines with Class A-like behavior
        width = _safe_get(record, "width_in")
        dig   = _safe_get(record, "max_dig_depth_ft")
        ol = CLASS_A_SOFT_OVERLAP
        if (weight <= ol["weight_max"]
                and (width is None or width <= ol["width_max"])
                and (dig is None or dig <= ol["dig_max"])):
            flags.append(
                f"Upper-range Class A overlap: {weight:,.0f} lb machine with compact width/dig depth "
                f"— may behave like a Class A in field use (e.g. Bobcat E20); scored as Class B"
            )

    elif weight <= CLASS_BOUNDARIES["C"]["weight_max"]:
        cap_class = "C"
    elif weight <= CLASS_BOUNDARIES["D"]["weight_max"]:
        cap_class = "D"
    else:
        cap_class = "D"
        flags.append(
            f"Operating weight {weight:,.0f} lb exceeds Class D ceiling (20,000 lb) — "
            "mini excavator framing may not apply; verify machine class"
        )

    return cap_class, class_labels[cap_class], flags


def _compute_size_class(record: MachineRecord) -> tuple[str, str]:
    """
    Classify mini excavator into micro_small / mid_size / large_mini.
    This is the user-facing identity layer — parallel to A/B/C/D cap system.

    micro_small:  ≤4,000 lb  — tight access, landscaping, backyard
    mid_size:  4,001–13,000 lb  — utility, residential construction, site work
    large_mini: 13,001–20,000 lb  — heavy utility, foundation, demo, land clearing

    Expected mapping:
      Cat 301.7 CR (~3,800 lb)  → micro_small
      Cat 305 CR (~11,200 lb)   → mid_size
      Kubota U55-5 (~12,100 lb) → mid_size
      Kubota KX080-4 (~17,900 lb) → large_mini
    """
    weight = _safe_get(record, "operating_weight_lbs")
    if weight is None:
        return "mid_size", SIZE_CLASS_BOUNDARIES["mid_size"]["label"] + " [weight unknown — defaulted to mid_size]"
    if weight <= SIZE_CLASS_BOUNDARIES["micro_small"]["weight_max"]:
        return "micro_small", SIZE_CLASS_BOUNDARIES["micro_small"]["label"]
    elif weight <= SIZE_CLASS_BOUNDARIES["mid_size"]["weight_max"]:
        return "mid_size", SIZE_CLASS_BOUNDARIES["mid_size"]["label"]
    else:
        return "large_mini", SIZE_CLASS_BOUNDARIES["large_mini"]["label"]


# ---------------------------------------------------------------------------
# SECTION 2: HYDRAULIC TIER CLASSIFICATION
# ---------------------------------------------------------------------------

def _compute_hydraulic_tier(record: MachineRecord) -> tuple[str, str, list[str]]:
    """
    Classify aux hydraulic capability into Tier 0–3 by GPM.
    Returns (tier_key, tier_label, flags).

    Null GPM with aux_available=True → Medium confidence, apply attachment caveats.
    """
    aux_available = _safe_get(record, "auxiliary_hydraulics_available")
    gpm           = _safe_get(record, "aux_flow_primary_gpm")
    flags: list[str] = []

    if aux_available is False:
        return "Tier 0", "Tier 0 — No Auxiliary Hydraulics", []

    if gpm is None:
        if aux_available is True:
            flags.append(
                "Aux hydraulics confirmed available but GPM not on record "
                "(common on Takeuchi older-gen models) — Medium Confidence; "
                "attachment scoring uses cautious estimates; verify GPM before listing attachment claims"
            )
            return "Tier 2M", "Tier 2 Marginal — GPM Unconfirmed (aux hydraulics present)", flags
        # aux_available unknown
        flags.append("Auxiliary hydraulics availability unknown — treating as no aux hydraulics")
        return "Tier 0", "Tier 0 — Aux Hydraulics Unknown", flags

    t = AUX_FLOW_THRESHOLDS
    if gpm < t["auger_hard_gate"]:           # < 6
        tier_key   = "Tier 0"
        tier_label = f"Tier 0 — Non-Functional for Powered Attachments ({gpm:.1f} GPM)"
    elif gpm <= t["tier_1_max"]:             # 6–9.9
        tier_key   = "Tier 1"
        tier_label = f"Tier 1 — Light Attachments Only ({gpm:.1f} GPM): thumb, small auger, compactor"
    elif gpm <= t["tier_2_marginal_max"]:    # 10–12.9
        tier_key   = "Tier 2M"
        tier_label = f"Tier 2 Marginal ({gpm:.1f} GPM): auger OK; breaker marginal; no brush cutter"
    elif gpm <= t["tier_2_full_max"]:        # 13–19.9
        tier_key   = "Tier 2F"
        tier_label = f"Tier 2 Full ({gpm:.1f} GPM): standard breaker, grapple, auger production"
    else:                                    # 20+
        tier_key   = "Tier 3"
        tier_label = f"Tier 3 — High Flow ({gpm:.1f} GPM): heavy breaker, brush cutter, large auger"

    return tier_key, tier_label, flags


# ---------------------------------------------------------------------------
# SECTION 3: CORE USE CASE SCORING FUNCTIONS
# ---------------------------------------------------------------------------

def _score_trenching_utility(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Utility trenching: service lines, irrigation, fence posts, shallow utility.
    Primary driver: max_dig_depth_ft
    Hard gate: dig_depth < 5.0 ft
    """
    label      = "Utility Trenching"
    dig        = _safe_get(record, "max_dig_depth_ft")
    two_speed  = _safe_get(record, "two_speed_travel")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []

    # Hard gate
    t = DIG_DEPTH_THRESHOLDS
    if dig is not None and dig < t["utility_trench_hard_gate"]:
        msg = f"Dig depth {dig:.1f} ft < 5.0 ft hard gate — cannot reliably trench to service depth"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    # Base score (dig depth drives ~75%; two-speed helps repositioning ~25%)
    two_spd_val = 1.0 if two_speed is True else (0.0 if two_speed is False else 0.5)
    base = _compute_weighted_score([
        (dig,         t["utility_trench_production"], t["utility_trench_minimum"], 75),
        (None,        1.0, 0.0, 0),   # placeholder — two-speed handled separately
    ])
    # Re-compute cleanly
    dig_s = _spec_score(dig, t["utility_trench_production"], t["utility_trench_minimum"])
    base  = round(dig_s * 75 + two_spd_val * 25)
    base  = max(0, min(100, base))
    score = base

    reasons: list[str] = []
    if dig is not None:
        if dig >= t["utility_trench_production"]:
            reasons.append(f"Dig depth {dig:.1f} ft — production-capable for deep service lines")
        elif dig >= t["utility_trench_minimum"]:
            reasons.append(f"Dig depth {dig:.1f} ft — minimum viable; adequate for 3–5 ft service trenches")
        else:
            reasons.append(f"Dig depth {dig:.1f} ft — marginal; limited to very shallow trenching")
            flags.append("Dig depth below minimum viable — flag in listing as 'shallow utility only'")
    else:
        reasons.append("Dig depth unknown — scored conservatively")
        flags.append("Dig depth not confirmed — verify before making utility trenching claims")

    if two_speed is True:
        reasons.append("Two-speed travel — good repositioning speed along trench lines")
    elif two_speed is False:
        reasons.append("Single-speed travel — slower repositioning; minor impact on linear trenching")

    # Class A deep-trench cap (not utility — utility is fine for Class A)
    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_trenching_deep(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Deep trenching: municipal sewer, storm drain, main-line utility.
    Hard gate: dig_depth < 8.0 ft
    Class A capped at 30.
    """
    label = "Deep Trenching (Sewer / Storm Drain)"
    dig   = _safe_get(record, "max_dig_depth_ft")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    t = DIG_DEPTH_THRESHOLDS

    if dig is not None and dig < t["deep_trench_hard_gate"]:
        msg = f"Dig depth {dig:.1f} ft < 8.0 ft hard gate — cannot reach finished sewer-service depth"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    dig_s = _spec_score(dig, t["deep_trench_full"], t["deep_trench_sewer_service"])
    base  = max(0, min(100, round(dig_s * 100)))
    score = base
    reasons: list[str] = []

    if dig is not None:
        if dig >= t["deep_trench_full"]:
            reasons.append(f"Dig depth {dig:.1f} ft — capable of storm drain and transmission main depth")
        elif dig >= t["deep_trench_main_line"]:
            reasons.append(f"Dig depth {dig:.1f} ft — production main-line sewer capable")
        elif dig >= t["deep_trench_sewer_service"]:
            reasons.append(f"Dig depth {dig:.1f} ft — residential sewer service connection capable")
        else:
            reasons.append(f"Dig depth {dig:.1f} ft — marginal for deep trench; limited to shallow sewer service")
    else:
        reasons.append("Dig depth unknown — scored conservatively")
        flags.append("Dig depth not confirmed — verify before making deep trench claims")

    # Class A cap
    if cap_class == "A":
        cap_val = HARD_CAPS["class_A_deep_trench"]
        if score > cap_val:
            score = cap_val
            msg = f"Class A machine — hard cap at {cap_val} on deep trenching (weight and stability limit production depth work)"
            applied_caps.append(msg)
            flags.append(f"CLASS A CAP: {msg}")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_septic_installation(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Septic installation: field lines + tank hole excavation.
    Hard gate: dig_depth < 7.0 ft
    Class A: hard cap at 0
    Upper Class B: scored from actual dig depth — no class cap if dig_depth >= 9.5 ft
    """
    label = "Septic System Installation"
    dig   = _safe_get(record, "max_dig_depth_ft")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    t = DIG_DEPTH_THRESHOLDS

    # Class A hard cap — period
    if cap_class == "A":
        msg = "Class A machine (≤ 4,000 lb) — cannot dig septic tank holes reliably; dig depth insufficient"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"CLASS A HARD CAP: {msg}"],
            flags=[f"DISQUALIFIED (Class A): {msg}"],
            triggered_hard_gates=[msg],
        )

    # Hard gate by dig depth
    if dig is not None and dig < t["septic_hard_gate"]:
        msg = f"Dig depth {dig:.1f} ft < 7.0 ft — cannot excavate septic tank holes or reliable field lines"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    # Scoring curve
    # 7.0–9.4 ft → field lines only (Fair: 35–54)
    # 9.5–10.4 ft → tank hole capable in warm climates (Good: 55–72)
    # 10.5–11.9 ft → reliable all residential (Good–Excellent: 73–84)
    # 12.0+ ft → commercial capable (Excellent: 85+)
    if dig is None:
        base = 40
        reasons = ["Dig depth unknown — scored conservatively; verify before septic listing claims"]
        flags.append("Dig depth not confirmed — septic claim may be inaccurate")
    elif dig >= t["septic_tank_commercial"]:
        base = 92
        reasons = [f"Dig depth {dig:.1f} ft — commercial and frost-depth residential septic capable"]
    elif dig >= t["septic_tank_reliable"]:
        base = 80
        reasons = [f"Dig depth {dig:.1f} ft — reliable for all residential septic including northern frost-depth markets"]
    elif dig >= t["septic_tank_warm_climate"]:
        base = 62
        reasons = [
            f"Dig depth {dig:.1f} ft — viable for most residential septic in warmer climates (tank top 6–8 ft)",
            "Northern frost-depth markets may require deeper dig — add listing caveat",
        ]
        flags.append("Add caveat: 'Verify local frost depth requirement — northern markets may need deeper dig'")
    else:
        # 7.0–9.4: field lines only
        base = 40
        reasons = [
            f"Dig depth {dig:.1f} ft — adequate for septic field lines (2.5–5 ft depth)",
            "Cannot reliably excavate tank holes — field lines only; do not claim full septic capability",
        ]
        flags.append("LISTING CAVEAT: Capable of septic field lines only — not tank hole excavation")

    score = base

    # Class B: if dig depth < 9.5 ft, apply soft cap at 60; if >= 9.5 ft, no class cap (spec-driven)
    if cap_class == "B" and dig is not None and dig < t["septic_tank_warm_climate"]:
        cap_val = 60
        if score > cap_val:
            score = cap_val
            msg = f"Class B machine with dig depth < 9.5 ft — septic score capped at {cap_val}"
            applied_caps.append(msg)
            flags.append(f"CAP: {msg}")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_truck_loading(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Truck loading: loading single-axle and tandem dump trucks.
    Primary driver: max_dump_height_ft
    If dump height is None → score = None, flag 'Dump height spec unavailable'
    Class A: hard cap at 0
    """
    label       = "Truck Loading"
    dump_height = _safe_get(record, "max_dump_height_ft")
    dig         = _safe_get(record, "max_dig_depth_ft")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    t = DUMP_HEIGHT_THRESHOLDS

    # Class A hard cap
    if cap_class == "A":
        msg = "Class A machine (≤ 4,000 lb) — dump height insufficient to clear any dump truck box"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"CLASS A HARD CAP: {msg}"],
            flags=[f"DISQUALIFIED (Class A): {msg}"],
            triggered_hard_gates=[msg],
        )

    # Null dump height → unassessable
    if dump_height is None:
        msg = "Dump height spec unavailable — truck loading capability cannot be assessed"
        return UseCaseScore(
            use_case=label, score=None, label="Unassessable",
            reasons=[f"UNASSESSABLE: {msg}"],
            flags=[f"UNASSESSABLE: {msg}"],
        )

    # Hard gate
    if dump_height < t["truck_load_hard_gate"]:
        msg = f"Dump height {dump_height:.1f} ft < 8.5 ft hard gate — cannot clear any dump truck box"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    # Scoring curve
    # 8.5–9.4 ft → marginal, cap at 45
    # 9.5–10.4 ft → marginal single-axle (35–55)
    # 10.5–11.9 ft → full single-axle (56–75)
    # 12.0+ ft → tandem/transfer (76+)
    reasons: list[str] = []
    if dump_height >= t["truck_load_tandem"]:
        base = 88
        reasons.append(f"Dump height {dump_height:.1f} ft — reaches tandem and transfer trailer clearance")
    elif dump_height >= t["truck_load_single_axle"]:
        dump_s = _spec_score(dump_height, t["truck_load_tandem"], t["truck_load_single_axle"])
        base   = round(56 + dump_s * 20)
        reasons.append(f"Dump height {dump_height:.1f} ft — full single-axle dump truck capable")
    elif dump_height >= t["truck_load_marginal"]:
        dump_s = _spec_score(dump_height, t["truck_load_single_axle"], t["truck_load_marginal"])
        base   = round(35 + dump_s * 20)
        reasons.append(
            f"Dump height {dump_height:.1f} ft — marginal; can load lower-sided single-axle trucks; "
            "productivity concern with higher-sided boxes"
        )
        flags.append("Add caveat: 'Verify dump truck box height before committing to truck loading work'")
    else:
        # 8.5–9.4: very marginal
        base = 35
        reasons.append(
            f"Dump height {dump_height:.1f} ft — very marginal for truck loading; "
            "only the lowest dump truck configurations possible"
        )
        flags.append("Truck loading claim should be avoided or heavily caveated — dump height borderline")

    score = base

    # Soft cap at 45 for very marginal zone (8.5–9.4)
    if dump_height < t["truck_load_marginal"] and score > 45:
        score = 45
        applied_caps.append("Marginal dump height zone — capped at 45")

    # Reach corroborates loading reach — note if available
    if dig is not None:
        reasons.append(f"Dig depth / reach profile: {dig:.1f} ft dig depth")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_material_loading_bucket(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Material loading with bucket: stockpile loading, fill work, aggregate loading.
    Primary driver: dump height; secondary: operating weight (stability).
    Class A capped at 50.
    """
    label       = "Material Loading / Bucket Work"
    dump_height = _safe_get(record, "max_dump_height_ft")
    weight      = _safe_get(record, "operating_weight_lbs")
    flags: list[str] = []
    applied_caps: list[str] = []
    t = DUMP_HEIGHT_THRESHOLDS

    if dump_height is None and weight is None:
        base = 40
        reasons = ["Both dump height and weight unknown — scored conservatively"]
        flags.append("Dump height and weight not confirmed — verify specs")
    else:
        dump_s   = _spec_score(dump_height, t["material_load_standard"], t["material_load_minimum"])
        weight_s = _spec_score(weight, 10000, 3000)
        base     = max(0, min(100, round(dump_s * 65 + weight_s * 35)))
        reasons: list[str] = []
        if dump_height is not None:
            if dump_height >= t["material_load_standard"]:
                reasons.append(f"Dump height {dump_height:.1f} ft — standard material loading capable")
            elif dump_height >= t["material_load_minimum"]:
                reasons.append(f"Dump height {dump_height:.1f} ft — adequate for most material loading")
            elif dump_height >= t["material_load_hard_gate"]:
                reasons.append(f"Dump height {dump_height:.1f} ft — limited; low-sided containers only")
            else:
                reasons.append(f"Dump height {dump_height:.1f} ft — very limited material loading reach")
        if weight is not None:
            reasons.append(f"Operating weight {weight:,.0f} lb — stability factor for bucket crowd")

    score = base

    # Class A cap
    if cap_class == "A":
        cap_val = HARD_CAPS["class_A_material_loading"]
        if score > cap_val:
            score = cap_val
            msg = f"Class A machine — material loading capped at {cap_val}"
            applied_caps.append(msg)
            flags.append(f"CLASS A CAP: {msg}")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps,
    )


def _score_footings_foundation(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Footing and foundation digging: deck footings through full basement perimeters.
    Primary driver: dig depth.
    Hard gate: dig_depth < 5.0 ft.
    """
    label = "Footings / Foundation Digging"
    dig   = _safe_get(record, "max_dig_depth_ft")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    t = DIG_DEPTH_THRESHOLDS

    if dig is not None and dig < t["footings_hard_gate"]:
        msg = f"Dig depth {dig:.1f} ft < 5.0 ft — cannot reach frost footing depth"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    reasons: list[str] = []
    dig_s = _spec_score(dig, t["footings_deep_basement"], t["footings_frost_footing"])
    base  = max(0, min(100, round(dig_s * 100)))

    if dig is not None:
        if dig >= t["footings_deep_basement"]:
            reasons.append(f"Dig depth {dig:.1f} ft — deep basement and commercial footing capable")
        elif dig >= t["footings_basement_perimeter"]:
            reasons.append(f"Dig depth {dig:.1f} ft — full residential basement perimeter capable")
        elif dig >= t["footings_frost_footing"]:
            reasons.append(f"Dig depth {dig:.1f} ft — frost footing and deck addition footing capable")
        else:
            reasons.append(f"Dig depth {dig:.1f} ft — limited footing capability; very shallow only")
    else:
        reasons.append("Dig depth unknown — scored conservatively")
        flags.append("Dig depth not confirmed — verify before making footing capability claims")

    return UseCaseScore(
        use_case=label, score=base, label=_score_label(base),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_tight_access_backyard_work(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Tight access and backyard work: residential gates, narrow passageways.
    Primary drivers: width_in, tail_swing_type.
    Hard gate: width > 84 in.
    Class D: hard cap at 35.
    """
    label      = "Tight Access / Backyard Work"
    width      = _safe_get(record, "width_in")
    tail_swing = (_safe_get(record, "tail_swing_type") or "").lower()
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    wt = WIDTH_THRESHOLDS

    # Class D cap
    if cap_class == "D":
        cap_val = HARD_CAPS["class_D_tight_access"]
        # still compute score but will cap
    else:
        cap_val = None

    # Hard gate
    if width is not None and width > wt["access_hard_gate"]:
        msg = f"Width {width:.0f} in > 84 in hard gate — does not fit standard residential double gate"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    reasons: list[str] = []

    # Width scoring (0–100 component, weight 55%)
    if width is None:
        width_score = 0.4
        reasons.append("Width unknown — conservative access estimate; verify before advertising as tight-access")
        flags.append("Width not confirmed — verify machine width before making tight-access claims")
    elif width <= wt["access_premium"]:
        width_score = 1.0
        reasons.append(f"Width {width:.0f} in — fits most single residential gates; excellent access")
    elif width <= wt["access_good"]:
        width_score = 0.75
        reasons.append(f"Width {width:.0f} in — fits standard double gates; good access for most residential properties")
    elif width <= wt["access_limited"]:
        width_score = 0.45
        reasons.append(f"Width {width:.0f} in — limited; wide double gate or large property only")
    elif width <= wt["access_poor"]:
        width_score = 0.2
        reasons.append(f"Width {width:.0f} in — significant access limitation; flag in listing")
        flags.append("Width restricts access to large-gate or open-site properties only")
    else:
        width_score = 0.0

    # Tail swing scoring (weight 45%)
    if tail_swing == "zero" or tail_swing == "zts":
        tail_score = 1.0
        reasons.append("Zero tail swing — full swing in tight spaces; genuine productivity and safety differentiator")
    elif tail_swing == "reduced":
        tail_score = 0.65
        reasons.append("Reduced tail swing — meaningfully better than conventional for tight access; not true ZTS")
    elif tail_swing == "conventional":
        tail_score = 0.2
        reasons.append("Conventional tail swing — limits swing in confined spaces; plan swing clearance carefully")
        flags.append("Conventional tail swing limits tight-access productivity — note in listing if selling into residential market")
    else:
        tail_score = 0.4
        reasons.append("Tail swing type unknown — scored conservatively")
        flags.append("Tail swing type not confirmed — verify; it significantly affects tight-access value")

    base  = max(0, min(100, round(width_score * 55 + tail_score * 45)))
    score = base

    # Class D cap
    if cap_class == "D" and score > HARD_CAPS["class_D_tight_access"]:
        score = HARD_CAPS["class_D_tight_access"]
        msg = f"Class D machine — tight access capped at {HARD_CAPS['class_D_tight_access']} (weight limits residential gate viability)"
        applied_caps.append(msg)
        flags.append(f"CLASS D CAP: {msg}")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_interior_demo(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Interior demolition: basement work, selective structural demo inside buildings.
    Primary drivers: width_in, tail_swing_type, operating_weight_lbs.
    Hard gates / caps: width > 84 → score 0; Class D → cap at 20.
    """
    label      = "Interior Demolition"
    width      = _safe_get(record, "width_in")
    tail_swing = (_safe_get(record, "tail_swing_type") or "").lower()
    weight     = _safe_get(record, "operating_weight_lbs")
    retract    = _safe_get(record, "retractable_undercarriage")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    wt = WIDTH_THRESHOLDS

    # Class D — almost never interior demo
    if cap_class == "D":
        if weight is not None and weight > 15000:
            msg = "Class D machine (15,000+ lb) — floor load and access prohibit interior demo in virtually all cases"
            return UseCaseScore(
                use_case=label, score=0, label="Not Recommended",
                reasons=[f"CLASS D HARD CAP: {msg}"],
                flags=[f"DISQUALIFIED (Class D): {msg}"],
                triggered_hard_gates=[msg],
            )
        # Lighter Class D still gets cap
        cap_at_20 = True
    else:
        cap_at_20 = False

    reasons: list[str] = []

    # Width caps
    if width is not None and width > wt["interior_hard_cap_84"]:
        msg = f"Width {width:.0f} in > 84 in — cannot access standard doorways or commercial entries"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    # Width scoring component (50%)
    if width is None:
        w_score = 0.4
        reasons.append("Width unknown — conservative interior access estimate")
        flags.append("Width not confirmed — interior demo access claim unverifiable")
    elif width <= wt["interior_premium"]:
        w_score = 1.0
        reasons.append(f"Width {width:.0f} in — fits most interior doorways; strong interior access")
    elif width <= wt["interior_standard"]:
        w_score = 0.7
        reasons.append(f"Width {width:.0f} in — standard interior access; fits most commercial double doors")
    elif width <= wt["interior_penalty"]:
        w_score = 0.45
        reasons.append(f"Width {width:.0f} in — limited interior access; select doorways only")
    elif width <= wt["interior_hard_cap_72"]:
        w_score = 0.2
        reasons.append(f"Width {width:.0f} in — very limited interior access; large commercial openings only")
        flags.append("Width restricts interior demo to large-opening commercial buildings only")
    else:
        # 72–84 — cap at 30 overall
        w_score = 0.0
        reasons.append(f"Width {width:.0f} in — interior access extremely limited")
        flags.append("Width > 72 in — interior demo cap applies")

    # Tail swing component (40%)
    # ZTS: bonus; Reduced: neutral (no bonus, no penalty); Conventional: cap at 40
    if tail_swing in ("zero", "zts"):
        t_score = 1.0
        reasons.append("Zero tail swing — essential for interior work; swing without hitting walls")
    elif tail_swing == "reduced":
        t_score = 0.55
        reasons.append("Reduced tail swing — usable inside; must monitor tail clearance; not ZTS")
    elif tail_swing == "conventional":
        t_score = 0.2
        reasons.append("Conventional tail swing — serious limitation for interior demo; tail clearance required at every swing")
        flags.append("Conventional tail swing is a major limitation for interior demolition work")
    else:
        t_score = 0.4
        reasons.append("Tail swing type unknown")
        flags.append("Tail swing type not confirmed — verify for interior demo claims")

    # Weight / floor load (10%)
    if weight is not None and weight <= 10000:
        wt_score = 0.8
    elif weight is not None and weight <= 13000:
        wt_score = 0.5
        reasons.append(f"Weight {weight:,.0f} lb — floor load assessment required before interior work")
        flags.append("Structural floor assessment required for interior work at this weight")
    else:
        wt_score = 0.2

    base  = max(0, min(100, round(w_score * 50 + t_score * 40 + wt_score * 10)))
    score = base

    # Retractable undercarriage bonus
    if retract is True:
        bonus = 10
        score = min(100, score + bonus)
        reasons.append("Retractable undercarriage — can narrow below 39 in for standard doorway entry; major interior demo advantage")

    # Apply tail swing caps
    if tail_swing in ("reduced",):
        cap_val = HARD_CAPS["interior_demo_reduced_tail"]
        if score > cap_val:
            score = cap_val
            msg = f"Reduced tail swing — interior demo capped at {cap_val}"
            applied_caps.append(msg)

    if tail_swing == "conventional":
        cap_val = HARD_CAPS["interior_demo_conventional"]
        if score > cap_val:
            score = cap_val
            msg = f"Conventional tail swing — interior demo capped at {cap_val}"
            applied_caps.append(msg)
            flags.append(f"CAP: {msg}")

    # Width caps
    if width is not None and width > wt["interior_hard_cap_72"] and score > HARD_CAPS["interior_demo_width_72"]:
        score = HARD_CAPS["interior_demo_width_72"]
        applied_caps.append(f"Width > 72 in — interior demo capped at {HARD_CAPS['interior_demo_width_72']}")

    # Class D cap
    if cap_at_20 and score > HARD_CAPS["class_D_interior_demo"]:
        score = HARD_CAPS["class_D_interior_demo"]
        msg = f"Class D machine — interior demo capped at {HARD_CAPS['class_D_interior_demo']}"
        applied_caps.append(msg)
        flags.append(f"CLASS D CAP: {msg}")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_land_clearing_grading(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Land clearing and rough grading: site prep, light clearing, grading passes.
    Drivers: weight, HP (via weight proxy), blade availability, two-speed.
    """
    label     = "Land Clearing / Site Grading"
    weight    = _safe_get(record, "operating_weight_lbs")
    two_speed = _safe_get(record, "two_speed_travel")
    blade     = _safe_get(record, "blade_available")
    ang_blade = _safe_get(record, "angle_blade_available")
    flags: list[str] = []
    reasons: list[str] = []

    weight_s  = _spec_score(weight, 12000, 3000)
    speed_s   = 1.0 if two_speed is True else (0.0 if two_speed is False else 0.5)
    has_blade = blade is True or ang_blade is True

    base = max(0, min(100, round(weight_s * 65 + speed_s * 20 + (15 if has_blade else 0))))

    if weight is not None:
        if weight >= 10000:
            reasons.append(f"Operating weight {weight:,.0f} lb — substantial machine for clearing and grading passes")
        else:
            reasons.append(f"Operating weight {weight:,.0f} lb — lighter machine; adequate for residential grading")

    if two_speed is True:
        reasons.append("Two-speed travel — efficient repositioning for grading passes")
    elif two_speed is False:
        reasons.append("Single-speed — slower repositioning; minor impact on small-area clearing")

    if ang_blade is True:
        reasons.append("Angle blade — strong grading versatility; push and angle material efficiently")
    elif blade is True:
        reasons.append("Blade available — useful for cleanup passes and grading")
    else:
        reasons.append("No blade confirmed — limits grading and clearing pass efficiency")
        flags.append("No blade — clearing and grading capability is limited without a dozer blade")

    return UseCaseScore(
        use_case=label, score=base, label=_score_label(base),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
    )


def _score_residential_construction(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    General residential construction: foundations, drainage, backfill, site work.
    Drivers: dig depth, dump height, weight, two-speed, enclosed cab.
    """
    label     = "Residential Construction"
    dig       = _safe_get(record, "max_dig_depth_ft")
    dump      = _safe_get(record, "max_dump_height_ft")
    weight    = _safe_get(record, "operating_weight_lbs")
    two_speed = _safe_get(record, "two_speed_travel")
    cab       = _safe_get(record, "enclosed_cab_available")
    flags: list[str] = []
    reasons: list[str] = []

    dig_s    = _spec_score(dig,    10.5, 6.0)
    dump_s   = _spec_score(dump,   10.5, 7.5)
    weight_s = _spec_score(weight, 11000, 3500)
    speed_s  = 1.0 if two_speed is True else (0.0 if two_speed is False else 0.5)

    base = max(0, min(100, round(
        dig_s * 30 + dump_s * 25 + weight_s * 25 + speed_s * 10 + (10 if cab is True else 0)
    )))

    if dig is not None:
        reasons.append(f"Dig depth {dig:.1f} ft")
    if dump is not None:
        reasons.append(f"Dump height {dump:.1f} ft")
    if weight is not None:
        reasons.append(f"Operating weight {weight:,.0f} lb")
    if two_speed is True:
        reasons.append("Two-speed travel — good site mobility")
    if cab is True:
        reasons.append("Enclosed cab — year-round production capability")
    elif cab is False:
        reasons.append("Canopy only — limits all-weather utilization")

    return UseCaseScore(
        use_case=label, score=base, label=_score_label(base),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
    )


def _score_landscape_irrigation(record: MachineRecord, cap_class: str) -> UseCaseScore:
    """
    Landscaping and irrigation: backyard work, planting beds, irrigation trenching.
    Drivers: tight access (width + tail swing) and dig depth for shallow work.
    Class A and lower Class B are the sweet spot.
    """
    label      = "Landscaping / Irrigation"
    width      = _safe_get(record, "width_in")
    tail_swing = (_safe_get(record, "tail_swing_type") or "").lower()
    dig        = _safe_get(record, "max_dig_depth_ft")
    weight     = _safe_get(record, "operating_weight_lbs")
    flags: list[str] = []
    reasons: list[str] = []
    wt = WIDTH_THRESHOLDS

    # Width
    if width is None:
        w_score = 0.4
    elif width <= wt["access_premium"]:
        w_score = 1.0
        reasons.append(f"Width {width:.0f} in — fits most residential gates; ideal for backyard landscaping")
    elif width <= wt["access_good"]:
        w_score = 0.75
        reasons.append(f"Width {width:.0f} in — good residential access")
    elif width <= wt["access_limited"]:
        w_score = 0.4
        reasons.append(f"Width {width:.0f} in — limited residential gate access")
    else:
        w_score = 0.1
        reasons.append(f"Width {width:.0f} in — poor residential access for landscaping use")
        flags.append("Width limits landscaping use to large or open properties")

    # Tail swing
    if tail_swing in ("zero", "zts"):
        t_score = 1.0
        reasons.append("Zero tail swing — ideal for landscaping in confined spaces")
    elif tail_swing == "reduced":
        t_score = 0.7
    elif tail_swing == "conventional":
        t_score = 0.35
        reasons.append("Conventional tail swing — limits maneuverability in typical landscaping environments")
    else:
        t_score = 0.5

    # Dig depth (shallow work is primary)
    dig_s = _spec_score(dig, 8.0, 4.0)

    # Weight penalty for very large machines
    weight_s = _spec_score(weight, 5000, 10000) if weight is not None else 0.5  # inverse — lighter is better
    # Lighter machines favor landscaping
    if weight is not None:
        if weight <= 4000:
            wt_adj = 1.0
        elif weight <= 7000:
            wt_adj = 0.8
        elif weight <= 10000:
            wt_adj = 0.55
        else:
            wt_adj = 0.3
            flags.append("Large machine — ground disturbance and access limit landscaping viability")
    else:
        wt_adj = 0.6

    base = max(0, min(100, round(w_score * 30 + t_score * 30 + dig_s * 20 + wt_adj * 20)))

    return UseCaseScore(
        use_case=label, score=base, label=_score_label(base),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
    )


# ---------------------------------------------------------------------------
# SECTION 4: ATTACHMENT USE CASE SCORING
# ---------------------------------------------------------------------------

def _score_auger(record: MachineRecord) -> UseCaseScore:
    """Auger attachment: fence posts, soil displacement, light to large diameter drilling."""
    label       = "Auger Attachment"
    aux_avail   = _safe_get(record, "auxiliary_hydraulics_available")
    gpm         = _safe_get(record, "aux_flow_primary_gpm")
    psi         = _safe_get(record, "aux_pressure_primary_psi")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    ft = AUX_FLOW_THRESHOLDS
    pt = AUX_PSI_THRESHOLDS

    if aux_avail is False:
        msg = "No auxiliary hydraulics — auger requires aux hydraulics"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    if gpm is None:
        # Aux available but GPM unknown — cautious estimate
        base = 40
        reasons = ["Aux hydraulics present but GPM not confirmed — auger likely viable; verify flow before purchase"]
        flags.append("GPM unconfirmed — auger flow adequacy cannot be confirmed; verify spec")
        return UseCaseScore(
            use_case=label, score=base, label=_score_label(base),
            reasons=reasons, flags=flags, base_score_before_adjustments=base,
        )

    if gpm < ft["auger_hard_gate"]:
        msg = f"Aux flow {gpm:.1f} GPM < 6.0 GPM hard gate — cannot run any practical auger motor"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    reasons: list[str] = []
    if gpm >= ft["auger_large_diameter"]:
        base = 88
        reasons.append(f"{gpm:.1f} GPM — large diameter auger capable (16\"+ in hard soil)")
    elif gpm >= ft["auger_standard"]:
        base = 72
        reasons.append(f"{gpm:.1f} GPM — standard production auger capable")
    elif gpm >= ft["auger_marginal"]:
        base = 50
        reasons.append(f"{gpm:.1f} GPM — standard auger capable; marginal for large diameter or hard soil")
        flags.append("Auger flow is adequate for standard work — verify attachment GPM spec for large-diameter augers")
    else:
        # 6–9.9: Tier 1 only — light fence post auger in soft soil
        base = 35
        reasons.append(f"{gpm:.1f} GPM — light fence post auger in soft soil only; not production-grade")
        flags.append("Low flow — limit auger claims to 'small diameter, soft soil only'; verify attachment minimum GPM")
        cap_val = 50
        if base > cap_val:
            base = cap_val
            applied_caps.append(f"Tier 1 flow — auger capped at {cap_val}")

    # PSI check for torque (hard soil)
    score = base
    if psi is not None and psi < pt["auger_psi_minimum"]:
        score = max(0, score - 15)
        reasons.append(f"Aux pressure {psi} PSI below 1,800 PSI — reduced torque for hard soil; soft soil only")
        flags.append("Low aux PSI — auger performance limited in hard or rocky soil conditions")
    elif psi is not None:
        reasons.append(f"Aux pressure {psi} PSI — adequate for auger torque demands")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_breaker_hammer(record: MachineRecord) -> UseCaseScore:
    """
    Hydraulic breaker / hammer: concrete breaking, rock work.
    CRITICAL: If aux_pressure_primary_psi is None → score = None (not 0).
    PSI is the primary driver; GPM required but secondary.
    """
    label     = "Hydraulic Breaker / Rock Hammer"
    aux_avail = _safe_get(record, "auxiliary_hydraulics_available")
    gpm       = _safe_get(record, "aux_flow_primary_gpm")
    psi       = _safe_get(record, "aux_pressure_primary_psi")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    ft = AUX_FLOW_THRESHOLDS
    pt = AUX_PSI_THRESHOLDS

    if aux_avail is False:
        msg = "No auxiliary hydraulics — breaker requires aux hydraulics"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    # CRITICAL: PSI null → score = None
    if psi is None:
        msg = (
            "Hydraulic pressure spec not available — breaker capability cannot be assessed. "
            "PSI is required to confirm breaker compatibility. Verify with seller before making any breaker claim."
        )
        return UseCaseScore(
            use_case=label, score=None, label="Unassessable",
            reasons=[f"UNASSESSABLE: {msg}"],
            flags=[f"PSI UNCONFIRMED: {msg}"],
        )

    # PSI hard gate
    if psi < pt["breaker_psi_hard_gate"]:
        msg = f"Aux pressure {psi} PSI < 1,600 PSI hard gate — cannot drive any practical hydraulic breaker"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    reasons: list[str] = []

    # GPM check (flow is secondary but required above minimum)
    if gpm is not None and gpm < ft["breaker_minimum_flow"]:
        msg = f"Aux flow {gpm:.1f} GPM < 10.0 GPM minimum — breaker cycle rate insufficient regardless of PSI"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    # Score from PSI (primary driver)
    if psi >= pt["breaker_psi_heavy"]:
        psi_base = 95
        reasons.append(f"Aux pressure {psi} PSI — production heavy breaker / rock hammer capable")
    elif psi >= pt["breaker_psi_strong"]:
        psi_base = 80
        reasons.append(f"Aux pressure {psi} PSI — strong breaker; handles rock and reinforced concrete")
    elif psi >= pt["breaker_psi_standard"]:
        psi_base = 65
        reasons.append(f"Aux pressure {psi} PSI — standard concrete and masonry breaking capable")
    elif psi >= pt["breaker_psi_marginal"]:
        psi_base = 35
        reasons.append(f"Aux pressure {psi} PSI — marginal; soft concrete and asphalt only")
        flags.append("PSI marginal for standard concrete breaking — limit claims to 'light demolition / asphalt'")
    else:
        psi_base = 20
        reasons.append(f"Aux pressure {psi} PSI — very marginal; limited practical breaker use")

    base  = psi_base
    score = base

    # GPM adjustment
    if gpm is not None:
        if gpm >= ft["breaker_heavy_flow"]:
            reasons.append(f"Aux flow {gpm:.1f} GPM — adequate for heavy breaker cycle rates")
        elif gpm >= ft["breaker_standard_flow"]:
            reasons.append(f"Aux flow {gpm:.1f} GPM — adequate for standard breaker work")
        elif gpm >= ft["breaker_marginal_flow"]:
            score = max(0, score - 10)
            reasons.append(f"Aux flow {gpm:.1f} GPM — marginal flow; slower cycle rates")
            flags.append("Marginal flow — breaker cycle rate will be reduced; light duty only")
        else:
            score = max(0, score - 15)
            reasons.append(f"Aux flow {gpm:.1f} GPM — low flow; significant cycle rate reduction")

    # PSI-based caps
    if psi < pt["breaker_psi_standard"]:  # < 2,200
        cap_val = HARD_CAPS["breaker_psi_1600_2199"]
        if score > cap_val:
            score = cap_val
            applied_caps.append(f"PSI {psi} < 2,200 — breaker capped at {cap_val}")
    elif psi < pt["breaker_psi_strong"]:  # < 2,700
        cap_val = HARD_CAPS["breaker_psi_2200_2699"]
        if score > cap_val:
            score = cap_val
            applied_caps.append(f"PSI {psi} 2,200–2,699 — breaker capped at {cap_val}")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_brush_cutter(record: MachineRecord) -> UseCaseScore:
    """
    Brush cutter / rotary head: vegetation clearing.
    HARD GATE: aux_flow < 12 GPM → score = 0 (no listing claim whatsoever).
    12–17.9 GPM: cap at 30 with caveat.
    18–24.9 GPM: standard capable, cap at 75.
    25+ GPM: full score.
    """
    label     = "Brush Cutter / Rotary Head"
    aux_avail = _safe_get(record, "auxiliary_hydraulics_available")
    gpm       = _safe_get(record, "aux_flow_primary_gpm")
    psi       = _safe_get(record, "aux_pressure_primary_psi")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    ft = AUX_FLOW_THRESHOLDS
    pt = AUX_PSI_THRESHOLDS

    if aux_avail is False:
        msg = "No auxiliary hydraulics"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    if gpm is None:
        msg = "GPM unknown — cannot confirm brush cutter compatibility; require confirmed GPM ≥ 18 for any positive claim"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"UNCONFIRMED: {msg}"],
            flags=[f"NO CLAIM: {msg}"],
        )

    # Hard gate: < 12 GPM → absolute zero; no claim at all
    if gpm < ft["brush_cutter_hard_gate"]:
        msg = (
            f"Aux flow {gpm:.1f} GPM < 12.0 GPM hard gate — "
            "cannot run even a light brush cutter without serious underperformance and heat buildup risk. "
            "Do NOT make any brush cutter claim in listing."
        )
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    reasons: list[str] = []
    if gpm >= ft["brush_cutter_production"]:
        base = 92
        reasons.append(f"{gpm:.1f} GPM — production brush cutter / heavy rotary head capable")
    elif gpm >= ft["brush_cutter_standard"]:
        base = 72
        reasons.append(f"{gpm:.1f} GPM — standard brush cutter capable (40–60 in cutting heads)")
        # Cap at 75 for 18–24.9 range
        cap_val = HARD_CAPS["brush_cutter_flow_18_24"]
        if base > cap_val:
            base = cap_val
            applied_caps.append(f"18–24.9 GPM zone — brush cutter capped at {cap_val}")
    else:
        # 12–17.9: marginal zone — cap at 30
        base = 28
        reasons.append(
            f"{gpm:.1f} GPM — marginal; light brush cutter use only. "
            "Not production-capable. Slow cutting speed and heat buildup risk at sustained use."
        )
        flags.append(
            "LISTING CAVEAT: Light brush cutter use only — not production capable. "
            "Verify attachment minimum GPM spec before purchase. Do not claim 'brush cutter ready' in headline."
        )
        cap_val = HARD_CAPS["brush_cutter_flow_12_17"]
        if base > cap_val:
            base = cap_val
            applied_caps.append(f"12–17.9 GPM — brush cutter capped at {cap_val}")

    score = base

    # PSI check
    if psi is not None and psi < pt["brush_cutter_psi_minimum"]:
        score = max(0, score - 12)
        reasons.append(f"Aux pressure {psi} PSI < 2,500 PSI — brush cutter claim not fully supported even with adequate flow")
        flags.append("PSI below brush cutter minimum — verify compatibility with specific attachment")
    elif psi is not None:
        reasons.append(f"Aux pressure {psi} PSI — adequate for brush cutter operation")

    return UseCaseScore(
        use_case=label, score=score, label=_score_label(score),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_grapple(record: MachineRecord) -> UseCaseScore:
    """Hydraulic grapple: debris sorting, log handling, land clearing assist."""
    label     = "Hydraulic Grapple"
    aux_avail = _safe_get(record, "auxiliary_hydraulics_available")
    gpm       = _safe_get(record, "aux_flow_primary_gpm")
    flags: list[str] = []
    applied_caps: list[str] = []
    triggered: list[str] = []
    ft = AUX_FLOW_THRESHOLDS

    if aux_avail is False:
        msg = "No auxiliary hydraulics"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    reasons: list[str] = []
    if gpm is None:
        base = 45
        reasons.append("GPM not confirmed — grapple likely viable with aux hydraulics; verify flow")
        flags.append("GPM unconfirmed — grapple cycle time unknown; verify spec")
        return UseCaseScore(
            use_case=label, score=base, label=_score_label(base),
            reasons=reasons, flags=flags, base_score_before_adjustments=base,
        )

    if gpm >= 18:
        base = 88
        reasons.append(f"{gpm:.1f} GPM — full grapple capable; good cycle times for log and debris handling")
    elif gpm >= ft["grapple_standard"]:
        base = 70
        reasons.append(f"{gpm:.1f} GPM — standard grapple capable; adequate cycle times")
    elif gpm >= ft["grapple_marginal"]:
        base = 45
        reasons.append(f"{gpm:.1f} GPM — marginal; light brush and small debris only; slow cycle times")
        flags.append("Marginal flow — grapple claim should be limited to 'light-duty' in listing")
        cap_val = 50
        if base > cap_val:
            base = cap_val
            applied_caps.append(f"Marginal GPM — grapple capped at {cap_val}")
    else:
        msg = f"Aux flow {gpm:.1f} GPM < 8.0 GPM — cannot run a productive hydraulic grapple"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    return UseCaseScore(
        use_case=label, score=base, label=_score_label(base),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
        applied_caps=applied_caps, triggered_hard_gates=triggered,
    )


def _score_compactor_plate(record: MachineRecord) -> UseCaseScore:
    """Hydraulic plate compactor: trench backfill, road base, structural fill."""
    label     = "Compactor Plate"
    aux_avail = _safe_get(record, "auxiliary_hydraulics_available")
    gpm       = _safe_get(record, "aux_flow_primary_gpm")
    psi       = _safe_get(record, "aux_pressure_primary_psi")
    flags: list[str] = []
    ft = AUX_FLOW_THRESHOLDS
    pt = AUX_PSI_THRESHOLDS

    if aux_avail is False:
        msg = "No auxiliary hydraulics — plate compactor requires aux hydraulics"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    reasons: list[str] = []
    if gpm is None:
        base = 60
        reasons.append("GPM not confirmed — compactor plate runs on modest flow demand; likely viable")
        flags.append("Verify aux flow is adequate for your specific compactor model (typically 5–18 GPM)")
    elif gpm >= 12:
        base = 88
        reasons.append(f"{gpm:.1f} GPM — capable of heavy compactor plate (sub-base and structural fill)")
    elif gpm >= 8:
        base = 72
        reasons.append(f"{gpm:.1f} GPM — standard compactor plate capable (road base, trench backfill)")
    elif gpm >= ft["compactor_minimum"]:
        base = 55
        reasons.append(f"{gpm:.1f} GPM — light compactor plate capable (trench backfill, pedestrian paths)")
        flags.append("Light compactor only — verify specific plate model GPM requirement")
    else:
        base = 20
        reasons.append(f"{gpm:.1f} GPM — very low flow; only the smallest compactor plates may function")
        flags.append("Very low flow — compactor plate claim should be avoided or heavily caveated")

    if psi is not None and psi < pt["compactor_psi_minimum"]:
        base = max(0, base - 10)
        flags.append("Aux PSI below 1,500 — verify compactor plate PSI requirement")

    return UseCaseScore(
        use_case=label, score=base, label=_score_label(base),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
    )


def _score_tilt_bucket(record: MachineRecord) -> UseCaseScore:
    """Tilt bucket / tiltrotator: precision grading, slope work."""
    label     = "Tilt Bucket / Tiltrotator"
    aux_avail = _safe_get(record, "auxiliary_hydraulics_available")
    gpm       = _safe_get(record, "aux_flow_primary_gpm")
    psi       = _safe_get(record, "aux_pressure_primary_psi")
    flags: list[str] = []
    ft = AUX_FLOW_THRESHOLDS
    pt = AUX_PSI_THRESHOLDS

    if aux_avail is False:
        msg = "No auxiliary hydraulics — tilt bucket requires aux hydraulics"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    reasons: list[str] = []
    if gpm is None:
        base = 50
        reasons.append("GPM not confirmed — standard tilt bucket likely viable; tiltrotator requires ≥ 15 GPM confirmation")
        flags.append("Verify GPM ≥ 8 for tilt bucket; ≥ 15 GPM for tiltrotator systems")
        return UseCaseScore(
            use_case=label, score=base, label=_score_label(base),
            reasons=reasons, flags=flags, base_score_before_adjustments=base,
        )

    if gpm >= ft["tiltrotator_minimum"]:
        base = 85
        reasons.append(f"{gpm:.1f} GPM — tiltrotator capable; full rotation + tilt")
    elif gpm >= ft["tilt_bucket_minimum"]:
        base = 68
        reasons.append(f"{gpm:.1f} GPM — standard tilt bucket capable (not tiltrotator)")
    else:
        base = 35
        reasons.append(f"{gpm:.1f} GPM — below 8 GPM; tilt bucket may be marginal; verify specific attachment spec")
        flags.append("Low flow — verify tilt bucket minimum GPM requirement before purchasing")

    if psi is not None and psi < pt["tilt_bucket_psi_minimum"]:
        base = max(0, base - 10)
        flags.append(f"Aux PSI {psi} below 1,800 — verify tilt cylinder PSI requirement")
    elif psi is not None:
        reasons.append(f"Aux pressure {psi} PSI — adequate for tilt bucket operation")

    return UseCaseScore(
        use_case=label, score=base, label=_score_label(base),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
    )


def _score_hydraulic_thumb(record: MachineRecord) -> UseCaseScore:
    """
    Hydraulic thumb: precision pick-and-place, rock sorting, debris handling.

    Three distinct states:
      thumb present  (hydraulic_thumb_available=True) — full score based on GPM
      thumb ready    (thumb_ready=True, thumb not True) — partial credit; machine prepped but no thumb
      no thumb       (hydraulic_thumb_available=False explicitly) — score 0
      unknown        (both None) — Unassessable
    """
    label       = "Hydraulic Thumb"
    thumb       = _safe_get(record, "hydraulic_thumb_available")
    thumb_ready = _safe_get(record, "thumb_ready")
    gpm         = _safe_get(record, "aux_flow_primary_gpm")
    flags: list[str] = []

    # --- STATE 1: No thumb ---
    if thumb is False:
        # Check thumb_ready — if bracket is present, note it
        if thumb_ready is True:
            return UseCaseScore(
                use_case=label, score=18, label="Not Recommended",
                reasons=[
                    "No hydraulic thumb installed — thumb mount bracket present (thumb-ready)",
                    "Buyer can add a thumb post-purchase; machine is prepped for it",
                ],
                flags=["THUMB READY: No thumb installed; bracket present — partial appeal to thumb buyers"],
            )
        msg = "Hydraulic thumb not confirmed as available on this machine"
        return UseCaseScore(
            use_case=label, score=0, label="Not Recommended",
            reasons=[f"HARD GATE: {msg}"], flags=[f"DISQUALIFIED: {msg}"],
            triggered_hard_gates=[msg],
        )

    # --- STATE 2: Thumb unknown but thumb_ready is True ---
    if thumb is None and thumb_ready is True:
        return UseCaseScore(
            use_case=label, score=35, label="Poor",
            reasons=[
                "Thumb availability unconfirmed — machine has thumb-ready bracket / quick attach prep",
                "Positive signal for buyers who plan to add a thumb; verify whether thumb is included",
            ],
            flags=["THUMB READY (unconfirmed install): verify whether hydraulic thumb is included with machine"],
        )

    # --- STATE 3: Thumb unknown, no ready signal ---
    if thumb is None:
        return UseCaseScore(
            use_case=label, score=None, label="Unassessable",
            reasons=["Hydraulic thumb availability not confirmed — verify with seller"],
            flags=["Thumb availability unknown — cannot score"],
        )

    # --- STATE 4: Thumb confirmed present ---
    reasons: list[str] = ["Hydraulic thumb confirmed — precision gripping capability"]
    if gpm is not None:
        if gpm >= 8:
            reasons.append(f"{gpm:.1f} GPM — adequate flow for responsive thumb actuation")
            base = 82
        elif gpm >= 5:
            base = 65
            reasons.append(f"{gpm:.1f} GPM — marginal flow; thumb will function but slower actuation")
        else:
            base = 40
            reasons.append(f"{gpm:.1f} GPM — very low flow; thumb actuation will be slow; only passive use recommended")
            flags.append("Very low flow — hydraulic thumb response will be slow; plan work accordingly")
    else:
        base = 72
        reasons.append("GPM not confirmed — thumb is likely functional at low flow demand; verify flow")

    return UseCaseScore(
        use_case=label, score=base, label=_score_label(base),
        reasons=reasons, flags=flags,
        base_score_before_adjustments=base,
    )


# ---------------------------------------------------------------------------
# SECTION 5: CONFIDENCE LEVEL
# ---------------------------------------------------------------------------

def _compute_confidence(record: MachineRecord) -> tuple[str, list[str]]:
    """
    Compute scoring confidence level based on field completeness.

    HIGH:   All primary fields present + aux hydraulics fully characterized
    MEDIUM: Core fields present; one or more secondary fields missing
    LOW:    Critical fields missing (operating weight, dig depth, or tail swing)
    """
    flags: list[str] = []

    weight      = _safe_get(record, "operating_weight_lbs")
    dig         = _safe_get(record, "max_dig_depth_ft")
    tail_swing  = _safe_get(record, "tail_swing_type")
    dump        = _safe_get(record, "max_dump_height_ft")
    reach       = _safe_get(record, "max_reach_ft")
    width       = _safe_get(record, "width_in")
    aux_avail   = _safe_get(record, "auxiliary_hydraulics_available")
    gpm         = _safe_get(record, "aux_flow_primary_gpm")
    psi         = _safe_get(record, "aux_pressure_primary_psi")

    # LOW triggers: critical fields missing
    low_triggers: list[str] = []
    if weight is None:
        low_triggers.append("operating_weight_lbs is None — cannot determine capability class")
    if dig is None:
        low_triggers.append("max_dig_depth_ft is None — cannot score dig-depth use cases")
    if tail_swing is None:
        low_triggers.append("tail_swing_type is None — cannot score tight access or interior demo accurately")

    if len(low_triggers) >= 2:
        for t in low_triggers:
            flags.append(f"LOW CONFIDENCE: {t}")
        return "Low", flags

    # MEDIUM triggers
    medium_missing: list[str] = []
    if dump is None:
        medium_missing.append("max_dump_height_ft (truck_loading and material_loading unassessable)")
    if reach is None:
        medium_missing.append("max_reach_ft")
    if width is None:
        medium_missing.append("width_in (tight_access and interior_demo scored conservatively)")
    if aux_avail is True and gpm is None:
        medium_missing.append("aux_flow_primary_gpm (attachment scores conservatively capped)")
    if aux_avail is True and psi is None:
        medium_missing.append("aux_pressure_primary_psi (breaker score = None; PSI-dependent claims blocked)")

    if len(low_triggers) == 1 or len(medium_missing) >= 2:
        if low_triggers:
            flags.append(f"LOW CONFIDENCE TRIGGER: {low_triggers[0]}")
        for m in medium_missing[:3]:
            flags.append(f"MEDIUM CONFIDENCE: Missing — {m}")
        return "Medium", flags

    if medium_missing:
        for m in medium_missing[:2]:
            flags.append(f"MISSING SPEC: {m}")
        return "Medium", flags

    return "High", flags


# ---------------------------------------------------------------------------
# SECTION 6: LISTING HIGHLIGHTS
# ---------------------------------------------------------------------------

def _compute_listing_highlights(record: MachineRecord, cap_class: str,
                                 hydraulic_tier: str) -> list[str]:
    """
    Generate prioritized listing highlight recommendations.

    Ranking (validated buyer behavior):
    1. Max dig depth — contractors search by this first
    2. Operating weight / class — transport and access planning
    3. Zero tail swing — residential buyers pay 5–15% premium
    4. Hours — strong proxy for remaining life
    5. Brand — Kubota and Bobcat command fastest liquidity
    6. Enclosed cab w/ HVAC — ~10–20% resale premium
    7. Hydraulic thumb — buyers ask this before flow or PSI
    8. Aux hydraulics (with GPM/PSI) — opens attachment market
    9. Two-speed travel — absence is a negative signal on Class B+
    10. Track condition — rubber track replacement is a known cost
    """
    highlights: list[str] = []

    dig        = _safe_get(record, "max_dig_depth_ft")
    dump       = _safe_get(record, "max_dump_height_ft")
    weight     = _safe_get(record, "operating_weight_lbs")
    tail_swing = (_safe_get(record, "tail_swing_type") or "").lower()
    hours      = _safe_get(record, "hours")
    brand      = (_safe_get(record, "brand") or "").lower().strip()
    cab        = _safe_get(record, "enclosed_cab_available")
    thumb      = _safe_get(record, "hydraulic_thumb_available")
    aux_avail  = _safe_get(record, "auxiliary_hydraulics_available")
    gpm        = _safe_get(record, "aux_flow_primary_gpm")
    psi        = _safe_get(record, "aux_pressure_primary_psi")
    two_speed  = _safe_get(record, "two_speed_travel")
    track_pct  = _safe_get(record, "track_condition_pct")
    retract    = _safe_get(record, "retractable_undercarriage")
    ang_blade  = _safe_get(record, "angle_blade_available")
    dual_aux   = _safe_get(record, "dual_aux")

    # Rank 1: Dig depth
    if dig is not None:
        t = DIG_DEPTH_THRESHOLDS
        if dig >= t["deep_trench_full"]:
            highlights.append(
                f"[HIGH VALUE] Dig Depth {dig:.1f} ft — deep utility and sewer main capable; "
                "lead with dig depth in listing title"
            )
        elif dig >= t["deep_trench_main_line"]:
            highlights.append(
                f"[HIGH VALUE] Dig Depth {dig:.1f} ft — production sewer and septic capable; "
                "lead with dig depth in title"
            )
        elif dig >= t["septic_tank_reliable"]:
            highlights.append(
                f"[VALUE] Dig Depth {dig:.1f} ft — full septic system capable; "
                "feature in listing for septic and utility contractors"
            )
        elif dig >= t["septic_tank_warm_climate"]:
            highlights.append(
                f"[NOTE] Dig Depth {dig:.1f} ft — warm-climate septic capable; residential utility work"
            )
        else:
            highlights.append(
                f"[NOTE] Dig Depth {dig:.1f} ft — residential utility and landscaping range"
            )
    else:
        highlights.append("[MISSING] Dig depth not in registry — verify and add before listing; it is the #1 spec buyers search")

    # Rank 2: Weight / class
    if weight is not None:
        highlights.append(
            f"[NOTE] Operating Weight {weight:,.0f} lb (Class {cap_class}) — "
            "determines trailer, transport, and gate access planning; state in listing"
        )

    # Rank 3: Zero tail swing
    if tail_swing in ("zero", "zts"):
        highlights.append(
            "[HIGH VALUE] Zero Tail Swing — residential and tight-access premium; "
            "buyers in landscaping and plumbing trades pay 5–15% premium; state 'ZTS' explicitly in title"
        )
    elif tail_swing == "reduced":
        highlights.append(
            "[VALUE] Reduced Tail Swing — better than conventional for tight access; "
            "note as 'reduced tail swing' in listing; do not claim zero / ZTS"
        )
    elif tail_swing == "conventional":
        highlights.append(
            "[NOTE] Conventional Tail Swing — no bonus; flag for buyers working in confined spaces; "
            "emphasize other strengths"
        )

    # Rank 4: Hours
    if hours is not None:
        for threshold, label in HOURS_LABELS:
            if threshold is None or hours <= threshold:
                if hours <= 1500:
                    highlights.append(
                        f"[HIGH VALUE] {label} ({int(hours):,} hrs) — "
                        "lead with hours in title; strong proxy for remaining capital life"
                    )
                elif hours <= 3000:
                    highlights.append(f"[NOTE] {int(hours):,} hrs — solid working machine; include in listing title")
                else:
                    highlights.append(
                        f"[CAUTION] {int(hours):,} hrs — price accordingly; "
                        "emphasize recent service history if available"
                    )
                break
    else:
        highlights.append("[MISSING] Hours not in record — add before listing; buyers ask immediately")

    # Rank 5: Brand
    for tier_key, tier_data in BRAND_TIERS.items():
        if brand in tier_data["brands"]:
            if tier_key == "tier1":
                highlights.append(
                    f"[HIGH VALUE] {tier_data['label']} ({brand.title()}) — "
                    "lead with brand; Kubota and Bobcat command fastest liquidity and resale premium"
                )
            elif tier_key == "tier2":
                highlights.append(
                    f"[VALUE] {tier_data['label']} ({brand.title()}) — "
                    "solid market acceptance; mention dealer support network"
                )
            else:
                highlights.append(
                    f"[NOTE] {tier_data['label']} ({brand.title()}) — "
                    "emphasize specs and condition over brand"
                )
            break

    # Rank 6: Enclosed cab
    if cab is True:
        highlights.append(
            "[HIGH VALUE] Enclosed Cab — year-round use; ~10–20% resale premium over comparable canopy unit; "
            "call out HVAC if equipped"
        )
    elif cab is False:
        highlights.append(
            "[NOTE] Canopy (Open Cab) — limits buyer pool for all-weather production operators; "
            "note any fan or canopy upgrades"
        )

    # Rank 7: Hydraulic thumb (three-state)
    thumb_ready = _safe_get(record, "thumb_ready")
    if thumb is True:
        highlights.append(
            "[VALUE] Hydraulic Thumb — buyers ask 'does it have a thumb?' before asking about flow; "
            "call out explicitly in listing"
        )
    elif thumb_ready is True:
        highlights.append(
            "[VALUE] Thumb-Ready — machine has mount bracket / quick-attach prep for hydraulic thumb; "
            "call out 'thumb-ready' in listing; appeals to buyers who plan to add one"
        )
    elif thumb is False:
        highlights.append(
            "[NOTE] No Hydraulic Thumb — buyers who need precision pick-and-place will note absence; "
            "consider adding to value proposition if thumb is available as add-on"
        )

    # Bucket package
    bucket_count  = _safe_get(record, "bucket_count")
    trench_bkt    = _safe_get(record, "trenching_bucket")
    ditch_bkt     = _safe_get(record, "ditch_bucket")
    quick_coup    = _safe_get(record, "quick_coupler")
    if bucket_count is not None and bucket_count >= 2:
        bkt_detail = []
        if trench_bkt is True:
            bkt_detail.append("trenching")
        if ditch_bkt is True:
            bkt_detail.append("ditch/cleanup")
        detail_str = f" ({', '.join(bkt_detail)} bucket included)" if bkt_detail else ""
        highlights.append(
            f"[VALUE] Bucket Package ({bucket_count} buckets){detail_str} — "
            "multi-bucket sets appeal to contractors who want to show up and work; "
            "list each bucket type explicitly"
        )
    elif trench_bkt is True:
        highlights.append(
            "[VALUE] Trenching Bucket — narrow bucket for clean utility trench; "
            "call out in listing for plumbers, electricians, and irrigation contractors"
        )
    elif ditch_bkt is True:
        highlights.append(
            "[VALUE] Ditch / Cleanup Bucket — grading and cleanup work; "
            "call out in listing for drainage and landscaping buyers"
        )
    if quick_coup is True:
        highlights.append(
            "[VALUE] Quick Coupler — fast bucket swap; "
            "buyers running multiple attachment types see this as a productivity multiplier"
        )

    # Rank 8: Aux hydraulics with GPM/PSI
    if aux_avail is True:
        if gpm is not None and psi is not None:
            highlights.append(
                f"[VALUE] Aux Hydraulics Confirmed — {gpm:.0f} GPM / {psi:,} PSI; "
                "state GPM and PSI in listing for attachment buyers; enables breaker, auger, grapple, compactor"
            )
        elif gpm is not None:
            highlights.append(
                f"[VALUE] Aux Hydraulics — {gpm:.0f} GPM confirmed; PSI not on record; "
                "verify PSI before making breaker claims"
            )
        elif psi is not None:
            highlights.append(
                f"[VALUE] Aux Hydraulics — {psi:,} PSI confirmed; GPM not on record; "
                "verify GPM before making attachment-specific claims"
            )
        else:
            highlights.append(
                "[VALUE] Aux Hydraulics Available — GPM and PSI not confirmed; "
                "verify before making specific attachment claims in listing"
            )
    elif aux_avail is False:
        highlights.append(
            "[NOTE] No Auxiliary Hydraulics — limits attachment compatibility; "
            "position as bucket-only work machine"
        )

    if dual_aux is True:
        highlights.append(
            "[VALUE] Dual Aux / Two-Way Hydraulics — enables powered reversible attachments (brush cutter, tiltrotator); "
            "call out for demo, clearing, and specialty attachment buyers"
        )

    # Rank 9: Two-speed
    if cap_class in ("B", "C", "D"):
        if two_speed is True:
            highlights.append("[VALUE] Two-Speed Travel — standard feature for Class B+; note if listing to utility or excavation contractors")
        elif two_speed is False:
            highlights.append(
                "[CAUTION] Single-Speed Travel — notable absence for Class B+ machines; "
                "flag for buyers in utility trenching and commercial excavation; price accordingly"
            )

    # Rank 10: Track condition
    if track_pct is not None:
        if track_pct >= 80:
            highlights.append(
                f"[VALUE] Good Tracks ({int(track_pct)}%) — "
                "call out proactively; buyers factor rubber track replacement cost immediately "
                "(typical: $800–3,500+ depending on class and width)"
            )
        elif track_pct >= 50:
            highlights.append(
                f"[NOTE] Moderate Tracks ({int(track_pct)}%) — "
                "describe accurately; buyer will inspect and price in replacement"
            )
        else:
            highlights.append(
                f"[CAUTION] Worn Tracks ({int(track_pct)}%) — "
                "disclose upfront or price accordingly; buyers will deduct replacement cost"
            )
    else:
        highlights.append("[MISSING] Track condition not in record — assess and add; buyers ask and factor this into offers")

    # Bonus: Dump height for truck loading
    if dump is not None and dump >= DUMP_HEIGHT_THRESHOLDS["truck_load_single_axle"]:
        highlights.append(
            f"[VALUE] Dump Height {dump:.1f} ft — truck loading capable; state in listing for excavation and utility contractors"
        )

    # Bonus: Retractable undercarriage
    if retract is True:
        highlights.append(
            "[SPECIALTY VALUE] Retractable Undercarriage — niche premium for interior demo and urban residential contractors; "
            "call out explicitly; significantly expands access options"
        )

    # Bonus: Angle blade
    if ang_blade is True:
        highlights.append(
            "[VALUE] Angle Blade — productive for grading and clearing; "
            "less common than straight blade; mention in listing"
        )

    return highlights


# ---------------------------------------------------------------------------
# SECTION 7: BEST FOR / NOT IDEAL FOR SUMMARIES
# ---------------------------------------------------------------------------

def _compute_best_for_not_ideal(record: MachineRecord, cap_class: str,
                                  all_use_cases: list[UseCaseScore],
                                  all_attachments: dict[str, UseCaseScore]) -> tuple[list[str], list[str]]:
    """Generate best_for and not_ideal_for lists from scored use cases."""

    # Best for: use cases scoring ≥ 70 (Good or Excellent)
    best: list[str] = []
    for uc in all_use_cases:
        if uc.score is not None and uc.score >= 70:
            best.append(uc.use_case)

    for att_name, uc in all_attachments.items():
        if uc.score is not None and uc.score >= 70:
            best.append(f"{uc.use_case} (attachment)")

    # Not ideal for: use cases scoring ≤ 30 (Poor or Not Recommended)
    not_ideal: list[str] = []
    for uc in all_use_cases:
        if uc.score is not None and uc.score <= 30:
            not_ideal.append(uc.use_case)
        elif uc.score is None:
            not_ideal.append(f"{uc.use_case} (spec unconfirmed)")

    for att_name, uc in all_attachments.items():
        if uc.score is not None and uc.score <= 30:
            not_ideal.append(f"{uc.use_case} (attachment)")
        elif uc.score is None:
            not_ideal.append(f"{uc.use_case} — unassessable (verify spec)")

    return best, not_ideal


# ---------------------------------------------------------------------------
# SECTION 8: ATTACHMENT-FIRST PROFILE ENGINE
# ---------------------------------------------------------------------------

# Map use case label → bonus key (used in _compute_attachment_profile and _apply_attachment_bonuses)
_UC_LABEL_TO_KEY: dict[str, str] = {
    "Utility Trenching":                    "trenching_utility",
    "Deep Trenching (Sewer / Storm Drain)": "trenching_deep",
    "Septic System Installation":           "septic_installation",
    "Truck Loading":                        "truck_loading",
    "Material Loading / Bucket Work":       "material_loading_bucket",
    "Footings / Foundation Digging":        "footings_foundation",
    "Tight Access / Backyard Work":         "tight_access_backyard",
    "Interior Demolition":                  "interior_demo",
    "Land Clearing / Site Grading":         "land_clearing_grading",
    "Residential Construction":             "residential_construction",
    "Landscaping / Irrigation":             "landscape_irrigation",
}


def _compute_attachment_profile(record: MachineRecord) -> dict[str, int]:
    """
    Scan attachment signals and return score bonuses for core use cases.

    Returns dict of {use_case_key: bonus_points}.
    Bonuses are additive, applied after base scoring, before Best For generation.
    Bonuses cannot override hard gates (applied only when base_score > 0 and no hard gate).

    Thumb states (distinct):
      thumb present  — material handling, cleanup, land-clearing framing
      thumb_ready    — weaker positive (bracket prepped, no thumb installed)
      no signal      — no adjustment

    Bucket signals:
      trenching_bucket  → trenching bias (+12 utility, +8 deep)
      ditch_bucket      → grading/drainage bias (+10 clearing, +8 landscape, +5 construction)
      bucket_count ≥ 2  → versatility boost (+8 construction, +4 more if ≥3)

    Dual aux / two-way:
      powered attachment readiness (+4 construction)

    Quick coupler:
      operational versatility (+4 construction)
    """
    bonuses: dict[str, int] = {}

    thumb        = _safe_get(record, "hydraulic_thumb_available")
    thumb_ready  = _safe_get(record, "thumb_ready")
    bucket_count = _safe_get(record, "bucket_count")
    trench_bkt   = _safe_get(record, "trenching_bucket")
    ditch_bkt    = _safe_get(record, "ditch_bucket")
    dual_aux     = _safe_get(record, "dual_aux")
    quick_coup   = _safe_get(record, "quick_coupler")
    angle_blade  = _safe_get(record, "angle_blade_available")

    # --- THUMB ---
    if thumb is True:
        # Full thumb: material handling, cleanup, land-clearing-style work
        bonuses["material_loading_bucket"] = bonuses.get("material_loading_bucket", 0) + 10
        bonuses["land_clearing_grading"]   = bonuses.get("land_clearing_grading", 0)   + 8
        bonuses["residential_construction"] = bonuses.get("residential_construction", 0) + 6
    elif thumb_ready is True:
        # Thumb-ready: real positive signal but weaker — machine is prepped, no thumb installed
        bonuses["material_loading_bucket"] = bonuses.get("material_loading_bucket", 0) + 4

    # --- BUCKET PACKAGE ---
    if trench_bkt is True:
        # Narrow trenching bucket: drives utility and deep trench bias
        bonuses["trenching_utility"] = bonuses.get("trenching_utility", 0) + 12
        bonuses["trenching_deep"]    = bonuses.get("trenching_deep", 0)    + 8

    if ditch_bkt is True:
        # Ditch / cleanup bucket: grading, drainage, shaping bias
        bonuses["land_clearing_grading"]    = bonuses.get("land_clearing_grading", 0)    + 10
        bonuses["landscape_irrigation"]     = bonuses.get("landscape_irrigation", 0)     + 8
        bonuses["residential_construction"] = bonuses.get("residential_construction", 0) + 5

    if bucket_count is not None and bucket_count >= 2:
        # Multiple buckets: general-construction versatility
        bonuses["residential_construction"] = bonuses.get("residential_construction", 0) + 8
        if bucket_count >= 3:
            bonuses["residential_construction"] = bonuses.get("residential_construction", 0) + 4

    # --- AUX / ATTACHMENT READINESS ---
    if dual_aux is True:
        # Dual aux / two-way: powered attachment readiness
        bonuses["residential_construction"] = bonuses.get("residential_construction", 0) + 4

    if quick_coup is True:
        # Quick coupler: operational versatility
        bonuses["residential_construction"] = bonuses.get("residential_construction", 0) + 4

    # --- ANGLE BLADE (cross-influence — already scored in land clearing, but adds identity weight) ---
    if angle_blade is True:
        bonuses["land_clearing_grading"] = bonuses.get("land_clearing_grading", 0) + 5

    return bonuses


def _apply_attachment_bonuses(use_cases: list[UseCaseScore],
                               bonuses: dict[str, int]) -> list[UseCaseScore]:
    """
    Apply attachment profile bonuses to use case scores.
    Rules:
      - Only applied when score > 0 and no hard gate triggered
      - Bonus cannot push score above 100
      - Bonus is noted in reasons for transparency
    """
    for uc in use_cases:
        key = _UC_LABEL_TO_KEY.get(uc.use_case)
        if key and key in bonuses:
            bonus = bonuses[key]
            if uc.score is not None and uc.score > 0 and not uc.triggered_hard_gates:
                new_score = min(100, uc.score + bonus)
                if new_score > uc.score:
                    uc.reasons.append(
                        f"Attachment profile bonus +{bonus}: {key.replace('_', ' ')} use case "
                        f"boosted by configured attachments/bucket package"
                    )
                    uc.score = new_score
                    uc.label = _score_label(new_score)
    return use_cases


def _apply_size_identity_adjustments(size_class: str,
                                      use_cases: list[UseCaseScore]) -> list[UseCaseScore]:
    """
    Apply size-based identity caps to use case scores.

    micro_small:
      - Suppress Interior Demolition and Land Clearing if they scored above 45
        (a 3,800 lb machine should not read like it's a production demo/clearing machine)

    large_mini:
      - Suppress Landscaping/Irrigation and Tight Access if above 50
        (a 17,000 lb machine should not read like a backyard machine)

    Adjustments are caps only — never inflate scores.
    """
    sc_data = SIZE_CLASS_BOUNDARIES.get(size_class, {})
    suppress_names = sc_data.get("suppress", [])
    if not suppress_names:
        return use_cases

    cap_value = 45 if size_class == "micro_small" else 50

    for uc in use_cases:
        if uc.use_case in suppress_names:
            if uc.score is not None and uc.score > cap_value:
                old_score = uc.score
                uc.score = cap_value
                uc.label = _score_label(cap_value)
                msg = (
                    f"SIZE CLASS CAP ({size_class}): score reduced from {old_score} → {cap_value}; "
                    f"machine identity suppresses '{uc.use_case}' framing"
                )
                uc.applied_caps.append(msg)
                uc.flags.append(f"SIZE IDENTITY CAP: {msg}")
    return use_cases


def _apply_brand_channel_refinement(brand: str | None,
                                     best_for: list[str],
                                     not_ideal_for: list[str]) -> tuple[list[str], list[str]]:
    """
    Reorder Best For list based on brand channel:
      construction brands (Cat, Bobcat, Komatsu, etc.) → prioritize construction-framed use cases first
      rural brands (Kubota, John Deere, Yanmar) → allow drainage, clearing, property work to surface higher

    Does not change scores — only influences ordering and therefore the 5-item summary.
    """
    if not brand:
        return best_for, not_ideal_for

    brand_lower = brand.lower().strip()
    channel = BRAND_CHANNEL.get(brand_lower, "construction")
    priority_order = _RURAL_ORDER if channel == "rural" else _CONSTRUCTION_ORDER

    # Stable sort: priority items first, rest maintain original order
    ordered: list[str] = []
    remainder: list[str] = list(best_for)

    for priority_fragment in priority_order:
        for item in list(remainder):
            if priority_fragment.lower() in item.lower():
                ordered.append(item)
                remainder.remove(item)
                break  # one match per priority slot

    ordered.extend(remainder)
    return ordered, not_ideal_for


# ---------------------------------------------------------------------------
# MAIN SCORING ENTRY POINT
# ---------------------------------------------------------------------------

def score_mini_ex(record: MachineRecord) -> ScorerResult:
    """
    Score a mini excavator record against all use cases and attachments.
    Returns a complete ScorerResult.
    """

    # Step 1: Classify machine
    cap_class, cap_class_label, class_flags = _compute_capability_class(record)

    # Step 1b: Size class (user-facing identity)
    size_class, size_class_label = _compute_size_class(record)

    # Step 2: Classify hydraulics
    hydraulic_tier, hydraulic_tier_label, hydraulic_flags = _compute_hydraulic_tier(record)

    # Step 3: Score all core use cases
    core_scorers = [
        ("trenching_utility",       _score_trenching_utility),
        ("trenching_deep",          _score_trenching_deep),
        ("septic_installation",     _score_septic_installation),
        ("truck_loading",           _score_truck_loading),
        ("material_loading_bucket", _score_material_loading_bucket),
        ("footings_foundation",     _score_footings_foundation),
        ("tight_access_backyard",   _score_tight_access_backyard_work),
        ("interior_demo",           _score_interior_demo),
        ("land_clearing_grading",   _score_land_clearing_grading),
        ("residential_construction",_score_residential_construction),
        ("landscape_irrigation",    _score_landscape_irrigation),
    ]

    all_use_cases: list[UseCaseScore] = []
    for key, fn in core_scorers:
        uc = fn(record, cap_class)
        all_use_cases.append(uc)

    # Step 3b: Apply attachment-first profile bonuses
    attachment_profile = _compute_attachment_profile(record)
    all_use_cases = _apply_attachment_bonuses(all_use_cases, attachment_profile)

    # Step 3c: Apply size-class identity adjustments (caps on out-of-character use cases)
    all_use_cases = _apply_size_identity_adjustments(size_class, all_use_cases)

    # Sort: Excellent → Good → Fair → Poor → Not Recommended → Unassessable
    def sort_key(uc: UseCaseScore):
        return -(uc.score if uc.score is not None else -1)

    all_use_cases.sort(key=sort_key)
    top_use_cases = [uc for uc in all_use_cases if uc.score is not None][:3]

    # Step 4: Score attachment use cases (7 total)
    attachment_scorers = {
        "auger":            _score_auger,
        "breaker_hammer":   _score_breaker_hammer,
        "brush_cutter":     _score_brush_cutter,
        "grapple":          _score_grapple,
        "compactor_plate":  _score_compactor_plate,
        "tilt_bucket":      _score_tilt_bucket,
        "hydraulic_thumb":  _score_hydraulic_thumb,
    }
    attachment_scores: dict[str, UseCaseScore] = {}
    for att_key, fn in attachment_scorers.items():
        attachment_scores[att_key] = fn(record)

    # Step 5: Confidence level
    confidence_level, confidence_flags = _compute_confidence(record)

    # Step 6: Listing highlights
    listing_highlights = _compute_listing_highlights(record, cap_class, hydraulic_tier)

    # Step 7: Best for / not ideal for
    best_for, not_ideal_for = _compute_best_for_not_ideal(
        record, cap_class, all_use_cases, attachment_scores
    )

    # Step 7b: Apply brand channel refinement (reorders Best For, does not change scores)
    brand_raw = _safe_get(record, "brand") or _safe_get(record, "make")
    best_for, not_ideal_for = _apply_brand_channel_refinement(brand_raw, best_for, not_ideal_for)

    best_for_summary    = "; ".join(best_for[:5]) if best_for    else "Insufficient spec data to generate summary"
    not_ideal_summary   = "; ".join(not_ideal_for[:5]) if not_ideal_for else "No significant limitations identified"

    # Step 8: Limitations (from flags across use cases)
    limitations: list[str] = []
    for uc in all_use_cases:
        for flag in uc.flags:
            if "DISQUALIFIED" in flag or "CAP" in flag or "CAUTION" in flag:
                limitations.append(f"{uc.use_case}: {flag}")
    limitations = limitations[:10]  # cap for readability

    # Step 9: Collect all flags
    all_flags: list[str] = (
        class_flags + hydraulic_flags + confidence_flags
    )
    for uc in all_use_cases:
        all_flags.extend(uc.flags)
    for att_uc in attachment_scores.values():
        all_flags.extend(att_uc.flags)
    # Deduplicate preserving order
    seen: set[str] = set()
    deduped_flags: list[str] = []
    for f in all_flags:
        if f not in seen:
            seen.add(f)
            deduped_flags.append(f)

    # Debug data
    debug_data = {
        "make": _safe_get(record, "make"),
        "model": _safe_get(record, "model"),
        "capability_class_raw": cap_class,
        "size_class_raw": size_class,
        "hydraulic_tier_raw": hydraulic_tier,
        "confidence_level": confidence_level,
        "attachment_profile_bonuses": attachment_profile,
        "input_weight_lbs": _safe_get(record, "operating_weight_lbs"),
        "input_dig_depth_ft": _safe_get(record, "max_dig_depth_ft"),
        "input_dump_height_ft": _safe_get(record, "max_dump_height_ft"),
        "input_width_in": _safe_get(record, "width_in"),
        "input_tail_swing": _safe_get(record, "tail_swing_type"),
        "input_aux_gpm": _safe_get(record, "aux_flow_primary_gpm"),
        "input_aux_psi": _safe_get(record, "aux_pressure_primary_psi"),
        "input_aux_available": _safe_get(record, "auxiliary_hydraulics_available"),
        "input_thumb": _safe_get(record, "hydraulic_thumb_available"),
        "input_thumb_ready": _safe_get(record, "thumb_ready"),
        "input_bucket_count": _safe_get(record, "bucket_count"),
        "input_trenching_bucket": _safe_get(record, "trenching_bucket"),
        "input_ditch_bucket": _safe_get(record, "ditch_bucket"),
        "use_case_scores_raw": {
            uc.use_case: uc.score for uc in all_use_cases
        },
        "attachment_scores_raw": {
            k: v.score for k, v in attachment_scores.items()
        },
    }

    return ScorerResult(
        capability_class=cap_class,
        capability_class_label=cap_class_label,
        size_class=size_class,
        size_class_label=size_class_label,
        hydraulic_tier=hydraulic_tier,
        hydraulic_tier_label=hydraulic_tier_label,
        top_use_cases=top_use_cases,
        all_use_cases=all_use_cases,
        attachment_scores=attachment_scores,
        listing_highlights=listing_highlights,
        scoring_flags=deduped_flags,
        limitations=limitations,
        best_for=best_for,
        not_ideal_for=not_ideal_for,
        best_for_summary=best_for_summary,
        not_ideal_for_summary=not_ideal_summary,
        confidence_level=confidence_level,
        debug_data=debug_data,
    )


# ---------------------------------------------------------------------------
# REGISTRY BATCH SCORING
# ---------------------------------------------------------------------------

def score_registry_record(record_dict: dict) -> dict:
    """
    Score a single registry record (dict format) and return a dict result.
    Maps registry field names to MachineRecord fields.
    """
    r = MachineRecord(
        make=record_dict.get("make"),
        model=record_dict.get("model"),
        year=record_dict.get("year"),
        operating_weight_lbs=record_dict.get("operating_weight_lbs"),
        max_dig_depth_ft=record_dict.get("max_dig_depth_ft"),
        max_dump_height_ft=record_dict.get("max_dump_height_ft"),
        max_reach_ft=record_dict.get("max_reach_ft"),
        width_in=record_dict.get("width_in"),
        auxiliary_hydraulics_available=record_dict.get("auxiliary_hydraulics_available"),
        aux_flow_primary_gpm=record_dict.get("aux_flow_primary_gpm"),
        aux_pressure_primary_psi=record_dict.get("aux_pressure_primary_psi"),
        tail_swing_type=record_dict.get("tail_swing_type"),
        two_speed_travel=record_dict.get("two_speed_travel"),
        enclosed_cab_available=record_dict.get("enclosed_cab_available"),
        hydraulic_thumb_available=record_dict.get("hydraulic_thumb_available"),
        thumb_ready=record_dict.get("thumb_ready"),
        quick_coupler=record_dict.get("quick_coupler"),
        bucket_count=record_dict.get("bucket_count"),
        trenching_bucket=record_dict.get("trenching_bucket"),
        ditch_bucket=record_dict.get("ditch_bucket"),
        dual_aux=record_dict.get("dual_aux"),
        retractable_undercarriage=record_dict.get("retractable_undercarriage"),
        angle_blade_available=record_dict.get("angle_blade_available"),
        blade_available=record_dict.get("blade_available"),
        brand=record_dict.get("brand") or record_dict.get("make"),
        hours=record_dict.get("hours"),
        track_condition_pct=record_dict.get("track_condition_pct"),
    )
    result = score_mini_ex(r)
    return {
        "make": r.make,
        "model": r.model,
        "year": r.year,
        "capability_class": result.capability_class,
        "capability_class_label": result.capability_class_label,
        "size_class": result.size_class,
        "size_class_label": result.size_class_label,
        "hydraulic_tier": result.hydraulic_tier,
        "confidence_level": result.confidence_level,
        "top_use_cases": [(uc.use_case, uc.score, uc.label) for uc in result.top_use_cases],
        "all_use_case_scores": {uc.use_case: uc.score for uc in result.all_use_cases},
        "attachment_scores": {k: (v.score, v.label) for k, v in result.attachment_scores.items()},
        "best_for_summary": result.best_for_summary,
        "not_ideal_for_summary": result.not_ideal_for_summary,
        "listing_highlights": result.listing_highlights,
        "scoring_flags": result.scoring_flags,
        "limitations": result.limitations,
        "debug_data": result.debug_data,
    }


def batch_score_registry(registry: list[dict]) -> list[dict]:
    """Score all records in a registry list. Returns list of result dicts."""
    results: list[dict] = []
    for record_dict in registry:
        try:
            result = score_registry_record(record_dict)
            results.append(result)
        except Exception as e:
            results.append({
                "make": record_dict.get("make"),
                "model": record_dict.get("model"),
                "year": record_dict.get("year"),
                "error": str(e),
            })
    return results


# ---------------------------------------------------------------------------
# FORMAT HELPER
# ---------------------------------------------------------------------------

def format_result(result: ScorerResult, show_debug: bool = False) -> str:
    """Pretty-print a ScorerResult for terminal review."""
    sep = "=" * 70
    lines = [sep]

    make  = result.debug_data.get("make") or "Unknown Make"
    model = result.debug_data.get("model") or "Unknown Model"
    lines.append(f"  MINI EX SCORER V1 — {make} {model}")
    lines.append(sep)

    lines.append(f"  CAPABILITY CLASS:  {result.capability_class_label}")
    lines.append(f"  HYDRAULIC TIER:    {result.hydraulic_tier_label}")
    lines.append(f"  CONFIDENCE:        {result.confidence_level}")
    lines.append("")

    lines.append("  TOP USE CASES:")
    for i, uc in enumerate(result.top_use_cases, 1):
        score_str = str(uc.score) if uc.score is not None else "N/A"
        lines.append(f"    {i}. {uc.use_case} — {score_str}/100 ({uc.label})")

    lines.append("")
    lines.append("  ALL USE CASES:")
    for uc in result.all_use_cases:
        score_str = str(uc.score) if uc.score is not None else "N/A"
        lines.append(f"    {uc.use_case:<42} {score_str:>5}  {uc.label}")

    lines.append("")
    lines.append("  ATTACHMENT SCORES:")
    for att_key, uc in result.attachment_scores.items():
        score_str = str(uc.score) if uc.score is not None else "N/A"
        lines.append(f"    {uc.use_case:<42} {score_str:>5}  {uc.label}")

    lines.append("")
    lines.append("  LISTING HIGHLIGHTS:")
    for h in result.listing_highlights:
        lines.append(f"    • {h}")

    lines.append("")
    lines.append(f"  BEST FOR:      {result.best_for_summary}")
    lines.append(f"  NOT IDEAL FOR: {result.not_ideal_for_summary}")

    if result.scoring_flags:
        lines.append("")
        lines.append("  SCORING FLAGS:")
        for f in result.scoring_flags[:10]:
            lines.append(f"    ⚑ {f}")

    if result.limitations:
        lines.append("")
        lines.append("  LIMITATIONS:")
        for lim in result.limitations[:6]:
            lines.append(f"    ✕ {lim}")

    if show_debug:
        lines.append("")
        lines.append("  DEBUG DATA:")
        for k, v in result.debug_data.items():
            if k not in ("use_case_scores_raw", "attachment_scores_raw"):
                lines.append(f"    {k}: {v}")
        lines.append("  USE CASE SCORES (raw):")
        for uc_name, score in result.debug_data.get("use_case_scores_raw", {}).items():
            lines.append(f"    {uc_name}: {score}")

    lines.append(f"\n{sep}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TEST HARNESS
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # ------------------------------------------------------------------
    # Test 1: Class A — Bobcat E17 (ZTS, tight access, landscaping)
    # Expect: Class A | High: landscaping, tight access, utility trenching
    #         Hard zero: septic, truck loading, deep trench (class caps)
    # ------------------------------------------------------------------
    t1 = MachineRecord(
        make="Bobcat", model="E17",
        operating_weight_lbs=3748,
        max_dig_depth_ft=7.5,
        max_dump_height_ft=7.8,
        max_reach_ft=12.4,
        width_in=39.4,
        auxiliary_hydraulics_available=True,
        aux_flow_primary_gpm=8.2,
        aux_pressure_primary_psi=2560,
        tail_swing_type="zero",
        two_speed_travel=False,
        enclosed_cab_available=False,
        hydraulic_thumb_available=True,
        retractable_undercarriage=False,
        blade_available=True,
        brand="Bobcat",
        hours=1240,
        track_condition_pct=75,
    )
    print("=== TEST 1: Bobcat E17 — Class A, ZTS, Landscaping Machine ===")
    print("Expect: Class A | High: landscaping, tight access | Zero: septic, truck loading")
    print(format_result(score_mini_ex(t1), show_debug=True))

    # ------------------------------------------------------------------
    # Test 2: Upper Class B — Takeuchi TB135 (conventional, high dump)
    # Weight 7,636 lb | Dig 11.2 ft | Dump 12.5 ft | Conventional tail
    # Expect: Class B | Truck loading GOOD (dump height 12.5 ft drives score)
    #         Septic GOOD (dig 11.2 ft >= 9.5 ft — no class cap)
    #         Tight access POOR (conventional + 62 in width)
    # ------------------------------------------------------------------
    t2 = MachineRecord(
        make="Takeuchi", model="TB135",
        operating_weight_lbs=7636,
        max_dig_depth_ft=11.2,
        max_dump_height_ft=12.5,
        max_reach_ft=18.2,
        width_in=62.0,
        auxiliary_hydraulics_available=True,
        aux_flow_primary_gpm=None,       # Takeuchi — GPM not on record
        aux_pressure_primary_psi=None,   # Takeuchi — PSI not on record
        tail_swing_type="conventional",
        two_speed_travel=True,
        enclosed_cab_available=True,
        hydraulic_thumb_available=False,
        blade_available=True,
        brand="Takeuchi",
        hours=2800,
        track_condition_pct=60,
    )
    print("=== TEST 2: Takeuchi TB135 — Upper Class B, Conventional, No GPM/PSI ===")
    print("Expect: Class B | Good: truck loading (12.5 ft dump), septic (11.2 ft dig)")
    print("        Breaker = None (PSI null); Tight access Poor (conventional + 62 in)")
    print(format_result(score_mini_ex(t2), show_debug=True))

    # ------------------------------------------------------------------
    # Test 3: Class C — Kubota KX057-6 (ZTS, production septic machine)
    # Weight 12,787 lb | Dig 13.5 ft | Dump 13.7 ft | ZTS | 27.4 GPM
    # Expect: Class C | Excellent: septic, deep trench, truck loading
    #         Excellent: auger, grapple, brush cutter (27.4 GPM)
    # ------------------------------------------------------------------
    t3 = MachineRecord(
        make="Kubota", model="KX057-6",
        operating_weight_lbs=12787,
        max_dig_depth_ft=13.5,
        max_dump_height_ft=13.7,
        max_reach_ft=20.2,
        width_in=78.0,
        auxiliary_hydraulics_available=True,
        aux_flow_primary_gpm=27.4,
        aux_pressure_primary_psi=3190,
        tail_swing_type="zero",
        two_speed_travel=True,
        enclosed_cab_available=True,
        hydraulic_thumb_available=True,
        angle_blade_available=True,
        brand="Kubota",
        hours=480,
        track_condition_pct=92,
    )
    print("=== TEST 3: Kubota KX057-6 — Class C, ZTS, Production Septic/Utility ===")
    print("Expect: Class C | Excellent: septic, deep trench, truck loading, brush cutter")
    print(format_result(score_mini_ex(t3), show_debug=True))

    # ------------------------------------------------------------------
    # Test 4: Class D — Bobcat E85 (conventional, production excavator)
    # Weight 18,078 lb | Dig 13.2 ft | Dump 13.6 ft | Conventional | 36 GPM
    # Expect: Class D | Good: septic, truck loading, deep trench
    #         Cap at 35 for tight access; cap at 20 for interior demo
    # ------------------------------------------------------------------
    t4 = MachineRecord(
        make="Bobcat", model="E85",
        operating_weight_lbs=18078,
        max_dig_depth_ft=13.2,
        max_dump_height_ft=13.6,
        max_reach_ft=21.5,
        width_in=86.6,
        auxiliary_hydraulics_available=True,
        aux_flow_primary_gpm=36.2,
        aux_pressure_primary_psi=3190,
        tail_swing_type="conventional",
        two_speed_travel=True,
        enclosed_cab_available=True,
        hydraulic_thumb_available=False,
        blade_available=True,
        brand="Bobcat",
        hours=1850,
        track_condition_pct=70,
    )
    print("=== TEST 4: Bobcat E85 — Class D, Conventional, Production Excavator ===")
    print("Expect: Class D | Good: septic, truck loading | Tight access cap=35 | Interior demo low/zero")
    print(format_result(score_mini_ex(t4), show_debug=True))

    # ------------------------------------------------------------------
    # Test 5: Class A — Takeuchi TB210 (ZTS, very small, minimal flow)
    # Weight 2,370 lb | Dig 5.76 ft | Dump 6.35 ft | ZTS | 5.8 GPM
    # Expect: Class A | Excellent: tight access | Hard zero: deep trench, septic, truck loading
    #         Auger: hard gate (< 6 GPM)
    # ------------------------------------------------------------------
    t5 = MachineRecord(
        make="Takeuchi", model="TB210",
        operating_weight_lbs=2370,
        max_dig_depth_ft=5.76,
        max_dump_height_ft=6.35,
        width_in=31.5,
        auxiliary_hydraulics_available=True,
        aux_flow_primary_gpm=5.8,
        aux_pressure_primary_psi=2560,
        tail_swing_type="zero",
        two_speed_travel=False,
        enclosed_cab_available=False,
        hydraulic_thumb_available=None,
        brand="Takeuchi",
        hours=650,
        track_condition_pct=80,
    )
    print("=== TEST 5: Takeuchi TB210 — Micro, ZTS, 31.5 in, Very Low Flow ===")
    print("Expect: Class A | Excellent: tight access, landscaping | Auger hard gate (5.8 GPM)")
    print(format_result(score_mini_ex(t5), show_debug=True))
