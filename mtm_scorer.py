"""
mtm_scorer.py
=============
MTM listing quality scorer.

Produces a structured score for any processed listing based on:
  - spec_completeness   : which critical OEM specs are registry-resolved
  - condition_coverage  : how well the listing documents machine condition
  - listing_quality     : how complete the listing identity and content are
  - commercial_readiness: how ready the listing is for a buyer to act on

Entry point:  score(listing_input) -> dict

Input types:
  FieldValue(name, value, confidence, source)
  ListingInput(equipment_type, undercarriage_family, fields, signals)

The scorer does NOT modify any upstream data; it only reads what the
pipeline has already produced.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Load schema
# ---------------------------------------------------------------------------

_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mtm_scoring_schema.json")

def _load_schema() -> dict:
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)

_SCHEMA = _load_schema()


# ---------------------------------------------------------------------------
# Input types
# ---------------------------------------------------------------------------

@dataclass
class FieldValue:
    """
    A single spec field with its resolved value and provenance.

    Attributes
    ----------
    name        : canonical field key (e.g. "net_hp", "roc_lb")
    value       : the resolved value (numeric, string, or None)
    confidence  : 0.0–1.0 trust level
                    1.0  — registry exact match, safe for injection
                    0.7  — registry match below injection confidence
                    0.5  — in requires_confirm list (needs human review)
                    0.9  — parsed from listing text (year, hours)
    source      : provenance tag
                    "registry_resolved"  — came from spec_resolver output
                    "requires_confirm"   — resolver flagged as needing review
                    "parsed"             — extracted from raw listing text
    """
    name:       str
    value:      Any
    confidence: float  = 1.0
    source:     str    = "registry_resolved"


@dataclass
class ListingInput:
    """
    Scorer input assembled from the MTM pipeline runtime data.

    Fields
    ------
    equipment_type      : e.g. "skid_steer", "mini_excavator"
    undercarriage_family: "tracked" | "wheeled" | None
    fields              : resolved spec fields (FieldValue list)
    photo_count         : number of photos attached (0 when not available)

    Signal booleans — presence flags derived from parsed listing:
    has_year, has_make, has_model, has_hours, has_price,
    has_location, has_contact, has_condition, has_features,
    has_attachments, has_notes

    Resolver quality flags:
    safe_for_injection  : from resolved_machine["safe_for_listing_injection"]
    requires_confirm    : list of field names flagged by the resolver
    """
    equipment_type:       str
    undercarriage_family: str | None         = None
    fields:               list[FieldValue]   = field(default_factory=list)
    photo_count:          int                = 0

    # Listing presence signals
    has_year:        bool = False
    has_make:        bool = False
    has_model:       bool = False
    has_hours:       bool = False
    has_price:       bool = False
    has_location:    bool = False
    has_contact:     bool = False
    has_condition:   bool = False
    has_features:    bool = False
    has_attachments: bool = False
    has_notes:       bool = False

    # Resolver quality flags
    safe_for_injection: bool      = True
    requires_confirm:   list[str] = field(default_factory=list)

    # Media / output asset signals (pack-generation path)
    has_walkaround_video: bool = False
    has_spec_sheet_pdf:   bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fields_dict(listing_input: ListingInput) -> dict[str, FieldValue]:
    """Index fields by name for O(1) lookup."""
    return {fv.name: fv for fv in listing_input.fields}


def _get_grade(score: float) -> tuple[str, str]:
    """Return (grade, grade_name) for a 0–100 score."""
    for band in _SCHEMA["grade_bands"]:
        if band["min"] <= score <= band["max"]:
            return band["grade"], band["name"]
    return "F", "Not Ready"


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------

def _score_spec_completeness(
    inp: ListingInput,
    fdict: dict[str, FieldValue],
) -> tuple[float, list[str], list[str], list[str]]:
    """
    Returns (score, present_critical, missing_critical, penalties).

    Score logic:
      base  = (present_critical / total_critical) × 100
      penalty for each critical field in requires_confirm   (up to max)
      penalty if safe_for_injection is False and specs exist
    """
    eq_type  = inp.equipment_type or "_default"
    schema   = _SCHEMA["critical_fields"]
    critical = schema.get(eq_type, schema.get("_default", []))

    if not critical:
        return 50.0, [], [], []

    # A field is "present" if it has a FieldValue with a non-None value
    # and confidence above a minimum threshold (0.3 — excludes placeholder entries)
    present = [
        f for f in critical
        if f in fdict and fdict[f].value is not None and fdict[f].confidence >= 0.3
    ]
    missing = [f for f in critical if f not in present]

    base_score = (len(present) / len(critical)) * 100.0

    penalties_applied: list[str] = []
    p_cfg = _SCHEMA.get("penalties", {})

    # Penalise critical fields that require confirmation
    confirm_critical = [f for f in present if f in (inp.requires_confirm or [])]
    if confirm_critical:
        per_field  = p_cfg.get("requires_confirm_per_field", 8)
        cap        = p_cfg.get("requires_confirm_max", 20)
        deduction  = min(len(confirm_critical) * per_field, cap)
        base_score = max(0.0, base_score - deduction)
        field_list = ", ".join(confirm_critical)
        penalties_applied.append(
            f"Unconfirmed critical specs ({field_list}): -{deduction} pts"
        )

    # Penalise if resolver marked the match as not safe for injection
    if not inp.safe_for_injection and present:
        deduction  = p_cfg.get("unsafe_injection", 10)
        base_score = max(0.0, base_score - deduction)
        penalties_applied.append(
            f"Registry match confidence below injection threshold: -{deduction} pts"
        )

    return round(min(base_score, 100.0), 1), present, missing, penalties_applied


def _score_condition_coverage(inp: ListingInput) -> float:
    """
    40 pts — machine hours documented
    35 pts — model year present
    25 pts — condition keyword detected
    """
    score = 0.0
    if inp.has_hours:     score += 40.0
    if inp.has_year:      score += 35.0
    if inp.has_condition: score += 25.0
    return round(score, 1)


def _score_listing_quality(inp: ListingInput) -> float:
    """
    Identity (max 40 pts):
      make  +15, model +15, year +10
      bonus +15 when all three present

    Content (max 45 pts):
      features    +20
      attachments +15
      notes       +10
    """
    score = 0.0

    # Identity
    if inp.has_make:  score += 15.0
    if inp.has_model: score += 15.0
    if inp.has_year:  score += 10.0
    if inp.has_make and inp.has_model and inp.has_year:
        score += 15.0   # full-identity bonus

    # Content
    if inp.has_features:    score += 20.0
    if inp.has_attachments: score += 15.0
    if inp.has_notes:       score += 10.0

    return round(min(score, 100.0), 1)


def _score_commercial_readiness(inp: ListingInput) -> float:
    """
    price    +45
    location +30
    contact  +25
    """
    score = 0.0
    if inp.has_price:    score += 45.0
    if inp.has_location: score += 30.0
    if inp.has_contact:  score += 25.0
    return round(min(score, 100.0), 1)


# ---------------------------------------------------------------------------
# Strengths / Weaknesses / Top Fixes
# ---------------------------------------------------------------------------

def _build_strengths(inp: ListingInput, present_critical: list[str]) -> list[str]:
    out: list[str] = []
    if present_critical:
        out.append(
            f"Registry OEM specs confirmed — {len(present_critical)} critical "
            f"field{'s' if len(present_critical) != 1 else ''} resolved"
        )
    if inp.has_price:      out.append("Price listed")
    if inp.has_hours:      out.append("Machine hours documented")
    if inp.has_year:       out.append("Model year present")
    if inp.has_location:   out.append("Location included")
    if inp.has_contact:    out.append("Contact information present")
    if inp.has_condition:  out.append("Condition described")
    if inp.has_features:   out.append("Machine features documented")
    if inp.has_attachments:out.append("Attachments listed")
    if inp.photo_count > 0:
        out.append(f"{inp.photo_count} photo{'s' if inp.photo_count != 1 else ''} attached")
    if inp.has_walkaround_video: out.append("Walkaround video included")
    if inp.has_spec_sheet_pdf:   out.append("Spec sheet generated")
    return out


def _build_weaknesses(inp: ListingInput, missing_critical: list[str]) -> list[str]:
    out: list[str] = []
    if not inp.fields:
        out.append("No registry match — OEM specs unavailable")
    elif missing_critical:
        labels = ", ".join(missing_critical)
        out.append(f"Missing critical specs: {labels}")
    if inp.requires_confirm:
        labels = ", ".join(inp.requires_confirm)
        out.append(f"Specs require confirmation before publishing: {labels}")
    if not inp.has_price:      out.append("No price listed")
    if not inp.has_hours:      out.append("No machine hours")
    if not inp.has_year:       out.append("Model year missing")
    if not inp.has_contact:    out.append("No contact information")
    if not inp.has_location:   out.append("No location")
    if not inp.has_condition:  out.append("No condition noted")
    if inp.photo_count == 0:   out.append("No photos attached")
    return out


# Top-fix priority: ordered by score impact (highest-impact fixes first)
# Weights: price=45, location=30, contact=25, hours=40, year=35+10, condition=25
_FIX_PRIORITY = [
    # (condition_fn, fix_text)
    (lambda i: not i.has_price,      "Add price — single highest-impact commercial signal (+45 pts)"),
    (lambda i: not i.has_hours,      "Add machine hours — critical for buyer trust (+40 pts on condition)"),
    (lambda i: not i.has_year,       "Add model year (+35 pts condition, +10 pts listing quality)"),
    (lambda i: not i.has_location,   "Add location — required by most listing platforms (+30 pts)"),
    (lambda i: not i.has_contact,    "Add contact information (+25 pts commercial)"),
    (lambda i: not i.has_condition,  "Add a condition note (e.g. 'runs great', 'good condition') (+25 pts)"),
    (lambda i: not i.has_features,   "Document key features (cab, controls, camera, etc.) (+20 pts)"),
    (lambda i: not i.has_attachments,"List any included attachments (+15 pts)"),
    (lambda i: i.photo_count == 0,   "Add photos — listings with photos sell significantly faster"),
]


def _build_top_fixes(inp: ListingInput, missing_critical: list[str]) -> list[str]:
    fixes: list[str] = []

    # Missing critical specs come first if there's a registry match
    if inp.fields and missing_critical:
        labels = ", ".join(missing_critical)
        fixes.append(f"Add missing critical specs to registry or listing: {labels}")

    for condition_fn, fix_text in _FIX_PRIORITY:
        if condition_fn(inp):
            fixes.append(fix_text)
        if len(fixes) >= 5:
            break

    return fixes[:5]


def _missing_commercial(inp: ListingInput) -> list[str]:
    out: list[str] = []
    if not inp.has_price:    out.append("price")
    if not inp.has_location: out.append("location")
    if not inp.has_contact:  out.append("contact")
    if not inp.has_hours:    out.append("hours")
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def score(listing_input: ListingInput) -> dict:
    """
    Score a listing and return a structured diagnostics dict.

    Return shape
    ------------
    {
        "spec_completeness":   float,   # 0–100
        "condition_coverage":  float,   # 0–100
        "listing_quality":     float,   # 0–100
        "commercial_readiness":float,   # 0–100
        "overall_score":       float,   # 0–100 (weighted)
        "grade":               str,     # "A+", "A", … "F"
        "grade_name":          str,     # "Ready to Post", …
        "strengths":           list,
        "weaknesses":          list,
        "top_fixes":           list,
        "missing_critical":    list,
        "missing_commercial":  list,
        "applied_penalties":   list,
    }
    """
    fdict = _fields_dict(listing_input)
    weights = _SCHEMA["weights"]

    spec_score, present_critical, missing_critical, penalties = (
        _score_spec_completeness(listing_input, fdict)
    )
    cond_score    = _score_condition_coverage(listing_input)
    quality_score = _score_listing_quality(listing_input)
    comm_score    = _score_commercial_readiness(listing_input)

    overall = round(
        spec_score    * weights["spec_completeness"]
        + cond_score  * weights["condition_coverage"]
        + quality_score * weights["listing_quality"]
        + comm_score  * weights["commercial_readiness"],
        1,
    )

    grade, grade_name = _get_grade(overall)

    return {
        "spec_completeness":    spec_score,
        "condition_coverage":   cond_score,
        "listing_quality":      quality_score,
        "commercial_readiness": comm_score,
        "overall_score":        overall,
        "grade":                grade,
        "grade_name":           grade_name,
        "strengths":            _build_strengths(listing_input, present_critical),
        "weaknesses":           _build_weaknesses(listing_input, missing_critical),
        "top_fixes":            _build_top_fixes(listing_input, missing_critical),
        "missing_critical":     missing_critical,
        "missing_commercial":   _missing_commercial(listing_input),
        "applied_penalties":    penalties,
    }


# ---------------------------------------------------------------------------
# Fix My Listing — dealer-facing response block
# ---------------------------------------------------------------------------

def _categorize_fix(msg: str) -> str:
    """Infer fix category from fix message text."""
    m = msg.lower()
    if "photo" in m or "video" in m or "walkaround" in m or "image" in m:
        return "media"
    if "price" in m or "financing" in m:
        return "commercial"
    if "location" in m:
        return "commercial"
    if "contact" in m:
        return "commercial"
    if "hours" in m:
        return "condition"
    if "condition" in m:
        return "condition"
    if "year" in m:
        return "identity"
    if "make" in m or "model" in m:
        return "identity"
    if "feature" in m or "attachment" in m:
        return "features"
    if "spec" in m or "registry" in m or "oem" in m:
        return "spec"
    return "spec"


def _prioritize_fix(msg: str) -> str:
    """Infer fix priority from point values mentioned in fix message."""
    m = msg.lower()
    if any(x in m for x in ["+45", "+40", "+35", "+30", "critical", "registry", "oem"]):
        return "high"
    if "photo" in m or "video" in m:
        return "high"
    if any(x in m for x in ["+15", "+10"]):
        return "low"
    return "medium"


def build_fix_my_listing(scoring: dict) -> dict:
    """
    Convert raw scorer output into a clean dealer-facing FML block.

    Derives next_tier and points_to_next_tier from the grade_bands schema.
    Structures top_fixes with category and priority labels.
    Does not modify any score values.

    Return shape
    ------------
    {
        "overall_score":       float,
        "grade":               str,
        "grade_name":          str,
        "current_tier":        str,
        "next_tier":           str | None,
        "points_to_next_tier": float,
        "top_strengths":       list[str],
        "top_weaknesses":      list[str],
        "top_fixes": [
            {"message": str, "category": str, "priority": str},
            ...
        ],
    }
    """
    overall    = scoring.get("overall_score", 0.0)
    grade      = scoring.get("grade",      "F")
    grade_name = scoring.get("grade_name", "Not Ready")

    # Grade bands sorted ascending by min score
    bands = sorted(_SCHEMA["grade_bands"], key=lambda b: b["min"])

    # Current band: highest band whose min is <= overall
    current_band = bands[0]
    for b in bands:
        if overall >= b["min"]:
            current_band = b

    # Next tier: the band immediately above current in sorted order
    current_idx = next(i for i, b in enumerate(bands) if b is current_band)
    if current_idx + 1 < len(bands):
        next_band         = bands[current_idx + 1]
        next_tier         = next_band["name"]
        points_to_next    = round(max(0.1, next_band["min"] - overall), 1)
    else:
        next_tier         = None
        points_to_next    = 0

    structured_fixes = [
        {
            "message":  fix,
            "category": _categorize_fix(fix),
            "priority": _prioritize_fix(fix),
        }
        for fix in (scoring.get("top_fixes") or [])
    ]

    return {
        "overall_score":       overall,
        "grade":               grade,
        "grade_name":          grade_name,
        "current_tier":        grade_name,
        "next_tier":           next_tier,
        "points_to_next_tier": points_to_next,
        "top_strengths":       (scoring.get("strengths")  or [])[:3],
        "top_weaknesses":      (scoring.get("weaknesses") or [])[:3],
        "top_fixes":           structured_fixes,
    }
