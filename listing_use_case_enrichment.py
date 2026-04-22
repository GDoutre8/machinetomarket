# =============================================================================
# MTM LOCKED — DO NOT MODIFY WITHOUT VERSION INCREMENT
# File:        listing_use_case_enrichment.py
# Version:     v1.1
# Status:      LOCKED (Production Baseline)
# Date Locked: 2026-04-20
# Controls:    Use case payload bridge for all equipment types — routing,
#              scorer calls, attachment detection, UC display label mapping,
#              attachment/limitation sentence generation, and inline logic
#              for telehandler, dozer, and wheel loader.
#              Supported types: skid_steer, compact_track_loader,
#              mini_excavator, backhoe_loader, telehandler, dozer, wheel_loader.
# Change rule: Increment version comment and update this header for any
#              logic change. Do NOT change scoring behavior silently.
# v1.1 changes (2026-04-20):
#   - Added _STUMP_NO_ATT_PENALTY: suppress Stump Grinding without stump_grinder
#     attachment (analogous to _FORESTRY_NO_ATT_PENALTY, _DEMO_NO_ATT_PENALTY)
#   - Replaced hardcoded 85-point 3rd-slot threshold with 7-point cluster rule:
#     use cases within 7 points of the top score form the cluster; at most 3
#     are shown (overlap pairs still gate the 3rd entry)
# =============================================================================

"""
listing_use_case_enrichment.py
==============================
MTM Use Case Scorer → Listing Text Payload

Isolated bridge between locked use-case scorers and listing generation.
Called by build_listing_pack_v1(); output passed as an optional payload
into build_listing_text().

Public API
----------
    build_use_case_payload(equipment_type, dealer_input, resolved_specs)
        -> dict | None

Payload schema (all keys always present when payload is not None):
    {
        "top_use_cases_for_listing": list[str],   # 0–3 use case names, score >= 70
        "attachment_sentence":       str | None,   # one sentence or None
        "limitation_sentence":       str | None,   # one sentence or None
    }

Guardrails
----------
- Score threshold: 70 minimum to include a use case claim
- At most 3 use cases in listing text
- Attachment claims suppressed if no meaningful tier passes (SSL/CTL)
  or if highest attachment score < 70 (mini ex)
- Limitation sentence only for material buyer-facing gaps
- Confidence "Low" → suppresses all claims (returns empty payload)
- If scorer raises, returns None silently so listing generation
  continues unaffected
- No scoring logic lives here — scorers are called as-is
"""

from __future__ import annotations

# Use-case score threshold for listing inclusion
_SCORE_THRESHOLD = 70


# ---------------------------------------------------------------------------
# Spec field normalizer
# ---------------------------------------------------------------------------
# The spec resolver returns internal canonical names; registry JSON and direct
# test inputs use registry schema names.  Both paths flow into resolved_specs.
# This function returns a dict that always has the registry schema names,
# regardless of which format was passed in.

def _normalize_specs(specs: dict) -> dict:
    """
    Map spec-resolver internal field names to registry schema field names.
    Operates non-destructively — returns a new dict with any missing
    registry names filled from their resolver-name equivalents.
    """
    out = dict(specs)  # copy; preserve whatever registry keys are already present

    def _fill(registry_key: str, *resolver_keys):
        if out.get(registry_key) is None:
            for rk in resolver_keys:
                v = specs.get(rk)
                if v is not None:
                    out[registry_key] = v
                    break

    # Core power / weight
    _fill("horsepower_hp",                "net_hp")
    _fill("operating_weight_lbs",         "operating_weight_lb")
    _fill("rated_operating_capacity_lbs", "roc_lb")
    _fill("tipping_load_lbs",             "tipping_load_lb")

    # Hydraulics (SSL / CTL)
    _fill("aux_flow_standard_gpm",        "hydraulic_flow_gpm")
    _fill("aux_flow_high_gpm",            "hi_flow_gpm")
    _fill("hydraulic_pressure_standard_psi", "hydraulic_pressure_standard_psi")  # same name, no-op

    # Hydraulics (mini ex)
    _fill("aux_flow_primary_gpm",         "hydraulic_flow_gpm")
    _fill("aux_pressure_primary_psi",     "hydraulic_pressure_standard_psi")

    # Dig / reach (mini ex) — resolver stores max_dig_depth as "X ft Y in" string.
    # Parse into decimal feet when the registry key is absent.
    if out.get("max_dig_depth_ft") is None:
        raw_depth = specs.get("max_dig_depth")
        if isinstance(raw_depth, (int, float)):
            out["max_dig_depth_ft"] = float(raw_depth)
        elif isinstance(raw_depth, str):
            # Parse "X ft Y in" or "X ft" formats
            import re as _re
            m = _re.match(r"(\d+)\s*ft(?:\s*(\d+)\s*in)?", raw_depth.strip())
            if m:
                ft = int(m.group(1))
                inch = int(m.group(2)) if m.group(2) else 0
                out["max_dig_depth_ft"] = round(ft + inch / 12, 2)

    _fill("max_dump_height_ft",           "max_dump_height_ft")  # same name, no-op
    _fill("max_reach_ft",                 "max_reach_ft")        # same name, no-op

    # Geometry
    _fill("bucket_hinge_pin_height_in",   "bucket_hinge_pin_height_in")  # same, no-op
    _fill("width_in",                     "width_in")                    # same, no-op

    return out

# Maximum use cases to mention in listing text
_MAX_USE_CASES = 3


# ---------------------------------------------------------------------------
# Equipment-type routing constants
# ---------------------------------------------------------------------------

_SSL  = "skid_steer"
_CTL  = "compact_track_loader"
_MEX  = "mini_excavator"
_BH   = "backhoe_loader"
_TH   = "telehandler"
_DZ   = "dozer"
_WL   = "wheel_loader"

_SUPPORTED_TYPES = {_SSL, _CTL, _MEX, _BH, _TH, _DZ, _WL}

# Labels that only appear when a matching attachment is explicitly listed.
# Prevents speculative seasonal/specialty claims on standard machines.
# Key: taxonomy label   Value: attachment key(s) that unlock it
_ATTACHMENT_TRIGGERED_LABELS: dict[str, str] = {
    "Snow Removal": "snow_blade",
    "Auger Work":   "auger",
}


# ---------------------------------------------------------------------------
# MachineRecord builders
# ---------------------------------------------------------------------------

_ENCLOSED_CAB_VALUES = frozenset({"enclosed", "erops", "closed", "cab"})
_OPEN_CAB_VALUES     = frozenset({"open", "rops", "canopy", "orops"})

def _enclosed_cab_from_cab_type(dealer_input) -> "bool | None":
    """
    Derive enclosed_cab_available (bool | None) from dealer_input.cab_type.
    cab_type is the canonical DealerInput field; enclosed_cab no longer exists.
    Returns True for enclosed variants, False for open variants, None if unknown.
    """
    raw = (getattr(dealer_input, "cab_type", None) or "").lower().strip()
    if raw in _ENCLOSED_CAB_VALUES:
        return True
    if raw in _OPEN_CAB_VALUES:
        return False
    return None


def _build_ssl_record(dealer_input, resolved_specs: dict):
    from scorers.skid_steer_use_case_scorer_v1_0 import MachineRecord
    return MachineRecord(
        horsepower_hp=resolved_specs.get("horsepower_hp"),
        rated_operating_capacity_lbs=resolved_specs.get("rated_operating_capacity_lbs"),
        operating_weight_lbs=resolved_specs.get("operating_weight_lbs"),
        aux_flow_standard_gpm=resolved_specs.get("aux_flow_standard_gpm"),
        aux_flow_high_gpm=resolved_specs.get("aux_flow_high_gpm"),
        hydraulic_pressure_standard_psi=resolved_specs.get("hydraulic_pressure_standard_psi"),
        hydraulic_pressure_high_psi=resolved_specs.get("hydraulic_pressure_high_psi"),
        bucket_hinge_pin_height_in=resolved_specs.get("bucket_hinge_pin_height_in"),
        lift_path=resolved_specs.get("lift_path"),
        high_flow_available=getattr(dealer_input, "high_flow", None),
        two_speed_available=(
            getattr(dealer_input, "two_speed_travel", None)
            or getattr(dealer_input, "two_speed", None)
        ),
        enclosed_cab_available=_enclosed_cab_from_cab_type(dealer_input),
        ride_control_available=getattr(dealer_input, "ride_control", None),
        joystick_controls_available=None,
        brand=getattr(dealer_input, "make", None),
        model=getattr(dealer_input, "model", None),
        hours=getattr(dealer_input, "hours", None),
        tire_condition_pct=None,
    )


def _build_ctl_record(dealer_input, resolved_specs: dict):
    from scorers.ctl_use_case_scorer_v1_0 import MachineRecord
    return MachineRecord(
        horsepower_hp=resolved_specs.get("horsepower_hp"),
        rated_operating_capacity_lbs=resolved_specs.get("rated_operating_capacity_lbs"),
        operating_weight_lbs=resolved_specs.get("operating_weight_lbs"),
        aux_flow_standard_gpm=resolved_specs.get("aux_flow_standard_gpm"),
        aux_flow_high_gpm=resolved_specs.get("aux_flow_high_gpm"),
        hydraulic_pressure_standard_psi=resolved_specs.get("hydraulic_pressure_standard_psi"),
        hydraulic_pressure_high_psi=resolved_specs.get("hydraulic_pressure_high_psi"),
        bucket_hinge_pin_height_in=resolved_specs.get("bucket_hinge_pin_height_in"),
        lift_path=resolved_specs.get("lift_path"),
        high_flow_available=getattr(dealer_input, "high_flow", None),
        two_speed_available=getattr(dealer_input, "two_speed", None),
        enclosed_cab_available=_enclosed_cab_from_cab_type(dealer_input),
        ride_control_available=getattr(dealer_input, "ride_control", None),
        brand=getattr(dealer_input, "make", None),
        hours=getattr(dealer_input, "hours", None),
        # track_condition is now free text in DealerInput (locked standard 2026-04-10).
        # Scorer expects a float 0-100. Passing None — scorer handles this safely.
        track_condition_pct=None,
    )


def _build_mex_record(dealer_input, resolved_specs: dict):
    from scorers.mini_ex_use_case_scorer_v1_0 import MachineRecord

    # tail_swing_type: check resolved_specs directly (mini ex registries store it there)
    tail_swing = resolved_specs.get("tail_swing_type")

    # blade_available: true if blade_width spec is present and > 0
    blade_w = resolved_specs.get("blade_width_in")
    blade_available = bool(blade_w and blade_w > 0)

    year_val = getattr(dealer_input, "year", None)

    return MachineRecord(
        make=getattr(dealer_input, "make", None),
        model=getattr(dealer_input, "model", None),
        year=int(year_val) if year_val else None,
        operating_weight_lbs=resolved_specs.get("operating_weight_lbs"),
        max_dig_depth_ft=resolved_specs.get("max_dig_depth_ft"),
        max_dump_height_ft=resolved_specs.get("max_dump_height_ft"),
        max_reach_ft=resolved_specs.get("max_reach_ft"),
        width_in=resolved_specs.get("width_in"),
        auxiliary_hydraulics_available=resolved_specs.get("auxiliary_hydraulics_available"),
        aux_flow_primary_gpm=resolved_specs.get("aux_flow_primary_gpm"),
        aux_pressure_primary_psi=resolved_specs.get("aux_pressure_primary_psi"),
        tail_swing_type=tail_swing,
        two_speed_travel=getattr(dealer_input, "two_speed", None),
        enclosed_cab_available=_enclosed_cab_from_cab_type(dealer_input),
        hydraulic_thumb_available=None,    # not in DealerInput V1
        retractable_undercarriage=resolved_specs.get("retractable_undercarriage"),
        angle_blade_available=None,
        blade_available=blade_available or None,
        brand=getattr(dealer_input, "make", None),
        hours=getattr(dealer_input, "hours", None),
        # track_condition is now free text in DealerInput (locked standard 2026-04-10).
        # Scorer expects a float 0-100. Passing None — scorer handles this safely.
        track_condition_pct=None,
    )


# ---------------------------------------------------------------------------
# Payload builders — per type
# ---------------------------------------------------------------------------


# Buyer-facing taxonomy labels for scorer use-case labels.
# Maps internal scorer labels → clean, listing-ready taxonomy names.
# Multiple scorer labels can share the same taxonomy label;
# _build_ranked_use_cases() deduplicates by keeping the highest-scored one.
_UC_DISPLAY: dict[str, str] = {
    # ── CTL scorer labels ──────────────────────────────────────────────────────
    "Grading / Site Prep":                        "Grading & Site Prep",
    "Material Handling / Loading":                "Material Handling",
    "Light Land Clearing":                        "Land Clearing",
    "Forestry Mulching":                          "Forestry Mulching",
    "Trenching (Standard -- Soft Ground)":        "Utility Trenching",
    "Trenching (Rock / Hard Ground)":             "Rock Trenching",
    "Demolition / Breaking":                      "Demolition & Breaking",
    "Snow Removal":                               "Snow Removal",
    "Cold Planing / Asphalt Milling":             "Cold Planing / Asphalt Milling",
    "Stump Grinding":                             "Stump Grinding",
    "Auger Work (Light Soil / Small Diameter)":   "Auger Work",
    "Auger Work (Rock / Hard Ground)":            "Auger Work",
    # ── SSL scorer labels ──────────────────────────────────────────────────────
    "Material Handling / Pallet Forks":           "Material Handling",
    "Truck Loading":                              "Truck Loading",
    "Concrete / Flatwork Prep":                   "Concrete & Flatwork Prep",
    "Demolition":                                 "Demolition & Breaking",
    "Auger Work":                                 "Auger Work",
    "Trenching (Standard / Soft Ground)":         "Utility Trenching",
    "Agriculture / Farm Use":                     "Farm & Agriculture Work",
    "Warehouse / Yard Use":                       "Yard & Staging Work",   # was Material Handling — now distinct
    "Landscaping / Irrigation":                   "Grading & Site Prep",
    # ── Mini ex scorer labels ─────────────────────────────────────────────────
    "Utility Trenching":                          "Utility Trenching",
    "Deep Trenching (Sewer / Storm Drain)":       "Utility Trenching",
    "Septic System Installation":                 "Utility Trenching",
    "Material Loading / Bucket Work":             "Excavation & Digging",
    "Footings / Foundation Digging":              "Excavation & Digging",
    "Tight Access / Backyard Work":               "Excavation & Digging",
    "Residential Construction":                   "Excavation & Digging",
    "Interior Demolition":                        "Demolition & Breaking",
    "Land Clearing / Site Grading":               "Land Clearing",
    # ── Backhoe scorer labels (display names) ────────────────────────────────
    "General Construction":                       "Grading & Site Prep",
    "Trenching":                                  "Utility Trenching",
    "Water Line Installation":                    "Utility Trenching",
    "Sewer Line Installation":                    "Utility Trenching",
    "Utility / Underground Work":                 "Utility Trenching",
    "Drainage Work":                              "Utility Trenching",
    "Road Work / Grading":                        "Grading & Site Prep",
    "Light Demolition":                           "Demolition & Breaking",
    "Foundation Excavation":                      "Excavation & Digging",
    "Loading Trucks":                             "Truck Loading",
    "Farm / Agricultural Use":                    "Farm & Agriculture Work",
    "Property / Estate Maintenance":              "Farm & Agriculture Work",
    "Landscaping":                                "Grading & Site Prep",
    "Material Handling":                          "Material Handling",
    "Pallet / Material Fork Handling":            "Material Handling",
    "Septic System Installation (backhoe)":       "Utility Trenching",
    # ── Backhoe scorer internal keys (snake_case — used by uc.use_case field) ─
    "general_construction":                       "Grading & Site Prep",
    "trenching":                                  "Utility Trenching",
    "water_line_install":                         "Utility Trenching",
    "sewer_line_install":                         "Utility Trenching",
    "utility_work":                               "Utility Trenching",
    "drainage_work":                              "Utility Trenching",
    "road_work":                                  "Grading & Site Prep",
    "demolition_light":                           "Demolition & Breaking",
    "foundation_digging":                         "Excavation & Digging",
    "loading_trucks":                             "Truck Loading",
    "farm_use":                                   "Farm & Agriculture Work",
    "property_maintenance":                       "Farm & Agriculture Work",
    "landscaping":                                "Grading & Site Prep",
    "material_handling":                          "Material Handling",
    "pallet_handling":                            "Material Handling",
    "septic_install":                             "Utility Trenching",
    "snow_removal":                               "Snow Removal",   # caught by _ATTACHMENT_TRIGGERED_LABELS
}


def _clean_uc_label(raw: str) -> str:
    """Return buyer-friendly display name for a scorer use-case label."""
    return _UC_DISPLAY.get(raw, raw)


# ---------------------------------------------------------------------------
# Attachment detection + scoring boost system
# ---------------------------------------------------------------------------

# Keyword patterns to detect each attachment type from free-text.
_ATTACHMENT_KEYWORD_MAP: dict[str, list[str]] = {
    "trencher":      ["trencher", "chain trencher", "rock trencher", "trenching head"],
    "auger":         ["auger", "boring head", "earth auger", "post hole digger", "post hole auger"],
    "mulcher":       ["mulcher", "mulching head", "forestry head", "brush cutter",
                      "rotary cutter", "masticator", "brush mulcher"],
    "forks":         ["forks", "pallet forks", "fork frame", "pallet fork"],
    "breaker":       ["breaker", "hydraulic breaker", "hammer", "hoe ram",
                      "concrete breaker", "rock breaker"],
    "cold_planer":   ["cold planer", "planer", "milling head",
                      "asphalt milling", "asphalt planer"],
    "stump_grinder": ["stump grinder", "stump grinding", "stump cutter"],
    "snow_blade":    ["snow blade", "snow pusher", "snow plow", "snow bucket",
                      "snow blower", "snowblower", "snow dozer"],
    "thumb":         ["thumb", "hydraulic thumb"],
    "blade":         ["blade", "dozer blade", "grading blade", "box blade", "angle blade"],
    "grapple":       ["grapple", "grapple bucket", "root grapple", "brush grapple"],
    "compactor":     ["compactor", "plate compactor", "vibratory plate", "drum roller"],
}

# Attachment type → {taxonomy_label: score_boost}.
# Primary match (+40): attachment directly enables this use case.
#   +40 is chosen so the category clears all generic 100-scoring items even
#   when the scorer gives the attachment use case a modest base score.
#   Scores are not capped at 100 — boosted items use scores up to 130 so
#   they sort reliably above un-boosted items that tie at 100.
# Secondary match (+10–15): attachment supports but doesn't define the job.
_ATTACHMENT_BOOSTS: dict[str, dict[str, int]] = {
    "trencher":      {"Utility Trenching": 40, "Rock Trenching": 12},
    "auger":         {"Auger Work": 40},
    "mulcher":       {"Forestry Mulching": 40, "Land Clearing": 12},
    "forks":         {"Material Handling": 25, "Truck Loading": 12},
    "breaker":       {"Demolition & Breaking": 60},
    "cold_planer":   {"Cold Planing / Asphalt Milling": 40},
    "stump_grinder": {"Stump Grinding": 40},
    "snow_blade":    {"Snow Removal": 30},
    "thumb":         {"Land Clearing": 15, "Demolition & Breaking": 12},
    "blade":         {"Grading & Site Prep": 18},
    "grapple":       {"Material Handling": 12, "Land Clearing": 12},
    "compactor":     {"Concrete & Flatwork Prep": 12, "Utility Trenching": 6},
}

# Penalty applied to Forestry Mulching when no mulcher attachment is listed.
# Prevents high-flow capability from surfacing as a primary output without
# direct evidence that the machine is actually set up for mulching work.
_FORESTRY_NO_ATT_PENALTY = 18.0

# Penalty applied to Demolition & Breaking when no breaker attachment is listed.
# Prevents hydraulic-output-based scoring from surfacing D&B as a top result
# without direct evidence the machine is configured for breaking work.
# Not applied to backhoe or mini ex — both do demolition work with primary tools.
_DEMO_NO_ATT_PENALTY = 15.0

# Penalty applied to Stump Grinding when no stump_grinder attachment is listed.
# High-flow capability alone is not enough — without a stump grinder confirmed
# on this unit, showing Stump Grinding as a top use case overclaims.
# Consistent with _FORESTRY_NO_ATT_PENALTY (-18) and _DEMO_NO_ATT_PENALTY (-15).
_STUMP_NO_ATT_PENALTY = 18.0

# Pairs of use case labels that overlap in meaning and should not both appear.
# If the candidate 3rd use case overlaps with either top-2 entry, it is skipped.
_OVERLAP_PAIRS: frozenset = frozenset({
    frozenset({"Material Handling", "Truck Loading"}),
    frozenset({"Land Clearing", "Forestry Mulching"}),
    frozenset({"Excavation & Digging", "Utility Trenching"}),
})

# Labels that represent attachment-specific work.
# When any of these are present, "Farm & Agriculture Work" is deprioritized
# so direct attachment signals take the top slots.
_ATTACHMENT_SPECIFIC_LABELS: frozenset = frozenset({
    "Utility Trenching", "Rock Trenching", "Auger Work",
    "Demolition & Breaking", "Forestry Mulching",
    "Cold Planing / Asphalt Milling", "Stump Grinding",
})

# Mini ex priority boosts: inherent advantage for the two defining mini ex
# use cases (Excavation & Digging, Utility Trenching) so they lead the
# output ahead of use cases that belong equally to other machine types
# (e.g. Truck Loading, Demolition).  Large enough to win normal tiebreaks,
# but an attachment-boosted competing use case (+20) can still beat Utility
# Trenching when genuinely justified (e.g. breaker → Demolition).
_MEX_PRIORITY_BOOST: dict[str, float] = {
    "Excavation & Digging": 5.0,
    "Utility Trenching":    15.0,
}


def _parse_attachment_keywords(
    text: "str | None",
    dealer_input=None,
) -> "set[str]":
    """
    Return set of attachment type keys detected from free-text and/or
    explicit DealerInput feature flags (thumb, blade).
    """
    detected: set[str] = set()

    if text:
        lowered = text.lower()
        for att_type, keywords in _ATTACHMENT_KEYWORD_MAP.items():
            if any(kw in lowered for kw in keywords):
                detected.add(att_type)

    # Explicit DealerInput flags (mini ex, but harmless for other types)
    if dealer_input is not None:
        if getattr(dealer_input, "thumb", False):
            detected.add("thumb")
        if getattr(dealer_input, "blade", False):
            detected.add("blade")

    return detected


def _build_ranked_use_cases(
    all_use_cases: list,
    dealer_input,
    equipment_type: str,
    cap_class: "str | None",
    score_threshold: float = _SCORE_THRESHOLD,
    apply_attachment_boosts: bool = True,
) -> "list[str]":
    """
    Build a ranked list of taxonomy use case labels for listing output.

    Pipeline:
    1. Map scorer labels → taxonomy labels via _UC_DISPLAY
    2. Apply attachment boosts (free-text + dealer flags) — skipped for backhoe,
       whose scorer already internalizes its own feature scoring
    3. Deduplicate: same taxonomy label → keep max effective score
    4. Suppress attachment-triggered labels unless matching attachment detected
    5. Filter at score_threshold (default _SCORE_THRESHOLD; override for types
       where spec coverage is incomplete and raw scores are structurally lower)
    6. Apply class suppression rules
    7. Return top 2 labels (or 3 if the third is strongly scored)
    """
    att_text = getattr(dealer_input, "attachments_included", None)
    detected_atts = _parse_attachment_keywords(att_text, dealer_input)

    # Build (taxonomy_label, effective_score) pairs
    label_scores: list[tuple[str, float]] = []
    for uc in all_use_cases:
        if uc.score is None:
            continue
        taxonomy_label = _UC_DISPLAY.get(uc.use_case, uc.use_case)
        effective = float(uc.score)
        if apply_attachment_boosts:
            for att_type in detected_atts:
                effective += _ATTACHMENT_BOOSTS.get(att_type, {}).get(taxonomy_label, 0)
        effective = min(130.0, effective)
        label_scores.append((taxonomy_label, effective))

    # Deduplicate: same taxonomy label → max effective score
    label_max: dict[str, float] = {}
    for label, score in label_scores:
        if label not in label_max or score > label_max[label]:
            label_max[label] = score

    # Attachment-triggered labels: suppress unless the required attachment is
    # explicitly detected.  Prevents speculative seasonal/specialty claims on
    # machines that simply have the capacity for the work but no direct evidence
    # they are configured for it.
    # Snow Removal: requires snow_blade / snow pusher listed in attachments.
    # Any other attachment-gated label follows the same pattern.
    for triggered_label, required_att in _ATTACHMENT_TRIGGERED_LABELS.items():
        if triggered_label in label_max and required_att not in detected_atts:
            del label_max[triggered_label]

    # Farm & Agriculture Work: deprioritize when attachment-specific signals are
    # present.  Without this, the scorer's generic agricultural classification
    # outranks direct attachment evidence even with active boosts applied.
    if "Farm & Agriculture Work" in label_max and detected_atts:
        att_labels = {lbl for lbl in label_max if lbl in _ATTACHMENT_SPECIFIC_LABELS}
        if att_labels:
            label_max["Farm & Agriculture Work"] = max(
                0.0, label_max["Farm & Agriculture Work"] - 12.0
            )

    # Forestry Mulching: require direct evidence (mulcher listed) to surface
    # as a primary output.  High-flow capability alone is not enough — without
    # a mulching head, calling it out as a top use case overclaims.
    if "Forestry Mulching" in label_max and "mulcher" not in detected_atts:
        label_max["Forestry Mulching"] = max(
            0.0, label_max["Forestry Mulching"] - _FORESTRY_NO_ATT_PENALTY
        )

    # Large CTL baseline boost: when no strong specialty attachments are listed,
    # both Grading & Site Prep and Material Handling should lead as the baseline
    # output for large machines.  The CTL scorer assigns 100 to nearly all
    # categories for Class C/D capable machines; these boosts lift the two true
    # baselines above the attachment-implied 100-tied pile so they consistently
    # occupy the top-2 listing slots.
    _STRONG_ATT_SIGNALS = {"mulcher", "trencher", "cold_planer", "stump_grinder", "breaker"}
    if equipment_type == _CTL and cap_class in ("C", "D"):
        if not detected_atts.intersection(_STRONG_ATT_SIGNALS):
            _CTL_LARGE_BASELINE_BOOSTS = {
                "Grading & Site Prep": 20.0,
                "Material Handling":   18.0,
            }
            for lbl, boost in _CTL_LARGE_BASELINE_BOOSTS.items():
                if lbl in label_max:
                    label_max[lbl] = min(130.0, label_max[lbl] + boost)

    # Utility Trenching: apply a small penalty when no trencher attachment is
    # detected.  Prevents moderate scorer base scores from surfacing this as a
    # top result without direct evidence the machine is set up for trenching.
    # Not applied to mini excavators or backhoes — both trench by default with
    # their primary digging tool (bucket / hoe), no add-on attachment required.
    if equipment_type not in (_MEX, _BH) and "Utility Trenching" in label_max and "trencher" not in detected_atts:
        label_max["Utility Trenching"] = max(
            0.0, label_max["Utility Trenching"] - 10.0
        )

    # Demolition & Breaking: apply penalty when no breaker attachment is detected.
    # Prevents high hydraulic output scores from surfacing D&B as a top result
    # without direct evidence the machine is equipped for breaking work.
    # Consistent with Forestry Mulching (-18) and Utility Trenching (-10) penalties.
    # Not applied to backhoe or mini ex — different demolition profiles.
    if equipment_type in (_SSL, _CTL) and "Demolition & Breaking" in label_max and "breaker" not in detected_atts:
        label_max["Demolition & Breaking"] = max(
            0.0, label_max["Demolition & Breaking"] - _DEMO_NO_ATT_PENALTY
        )

    # Stump Grinding: require a confirmed stump grinder to surface as a top use case.
    # High-flow compatibility alone (scored by the CTL/SSL scorers) is not enough —
    # without a stump grinder listed, showing it overclaims. Not applied to backhoe
    # or mini ex — neither is a stump grinder platform.
    if equipment_type in (_SSL, _CTL) and "Stump Grinding" in label_max and "stump_grinder" not in detected_atts:
        label_max["Stump Grinding"] = max(
            0.0, label_max["Stump Grinding"] - _STUMP_NO_ATT_PENALTY
        )

    # Mini ex: apply inherent priority boosts before sorting so that
    # Excavation & Digging and Utility Trenching lead ahead of use cases
    # that belong equally to other machine types (Truck Loading, Demolition).
    if equipment_type == _MEX:
        for lbl in list(label_max.keys()):
            bonus = _MEX_PRIORITY_BOOST.get(lbl, 0.0)
            if bonus:
                label_max[lbl] = min(130.0, label_max[lbl] + bonus)

    # Sort descending, then filter at threshold
    ranked = sorted(label_max.items(), key=lambda x: x[1], reverse=True)
    ranked = [(lbl, sc) for lbl, sc in ranked if sc >= score_threshold]

    # Class suppression: if Forestry Mulching outscores Land Clearing on a large
    # machine, suppress Land Clearing — they cover overlapping territory and
    # Forestry Mulching is the stronger, more specific claim.
    # Only fires when Forestry Mulching has the evidence to back it (i.e., its
    # score is actually higher than Land Clearing after any penalties applied).
    if equipment_type in (_CTL, _SSL) and cap_class in ("C", "D"):
        fm_sc = label_max.get("Forestry Mulching", 0.0)
        lc_sc = label_max.get("Land Clearing", 0.0)
        if fm_sc >= lc_sc and fm_sc >= _SCORE_THRESHOLD:
            ranked = [(lbl, sc) for lbl, sc in ranked if lbl != "Land Clearing"]

    # Mini ex: suppress categories that don't belong on an excavator.
    # Truck Loading is suppressed — mini exes are not loaders.
    # Grading & Site Prep is suppressed unless a blade is confirmed.
    if equipment_type == _MEX:
        blade_available = "blade" in detected_atts
        _MEX_SUPPRESS = {
            "Forestry Mulching", "Cold Planing / Asphalt Milling",
            "Stump Grinding", "Concrete & Flatwork Prep",
            "Farm & Agriculture Work", "Truck Loading",
        }
        if not blade_available:
            _MEX_SUPPRESS.add("Grading & Site Prep")
        ranked = [(lbl, sc) for lbl, sc in ranked if lbl not in _MEX_SUPPRESS]

    # Always show top 2. Apply the 7-point cluster rule only to the 3rd slot:
    # the 3rd use case is shown only when its score is within 7 points of the top
    # (i.e., genuinely tied) AND it has no semantic overlap with either top-2 entry.
    # This prevents specialty use cases with moderate scores (e.g. 85) from sneaking
    # in as a 3rd when the top-2 leaders are scoring 30+ points higher.
    if not ranked:
        return []

    result: list[str] = [lbl for lbl, _ in ranked[:2]]
    if len(ranked) >= 3:
        top_score = ranked[0][1]
        third_label, third_score = ranked[2]
        top2_set = set(result)
        overlaps = any(
            frozenset({third_label, existing}) in _OVERLAP_PAIRS
            for existing in top2_set
        )
        in_cluster = third_score >= top_score - 7.0
        if in_cluster and not overlaps:
            result.append(third_label)

    return result


# ---------------------------------------------------------------------------
# Supporting sentence helpers
# ---------------------------------------------------------------------------

def _supporting_sentence_ssl_ctl(result, top_labels: "list[str]", dealer_input=None) -> "str | None":
    """
    Render only when the dealer has confirmed high flow is installed on this
    unit AND tier-3 high-flow is scorer-compatible AND neither Forestry
    Mulching nor Cold Planing already appear in the top use cases.

    Requires dealer_input.high_flow == "yes" — prevents the claim from
    appearing on listings where high flow is an OEM option but the dealer
    has not confirmed it is installed on this specific machine.

    Skipped for Class A — high-flow is uncommon enough on small machines
    that calling it out reads as noise rather than signal.
    Default is no sentence; this fires only when it adds real buyer value.
    """
    # Require dealer-confirmed high flow on this unit.
    # "optional" means OEM offers it — not a confirmed feature of this listing.
    if getattr(dealer_input, "high_flow", None) != "yes":
        return None

    cap_class = getattr(result, "capability_class", None)
    if cap_class == "A":
        return None

    compat = getattr(result, "attachment_compatibility", {}) or {}
    tier3 = compat.get("tier_3_high_demand", {})

    high_demand_labels = {"Forestry Mulching", "Cold Planing / Asphalt Milling"}
    if tier3.get("compatible") and not high_demand_labels.intersection(set(top_labels)):
        return "High-flow hydraulics support mulchers, cold planers, and rotary cutters."

    return None


def _supporting_sentence_mex(result, top_labels: "list[str]", dealer_input) -> "str | None":
    """
    Render only when the dealer has explicitly listed an attachment that
    is not already represented in the top use case labels.

    Uses dealer_input, not scorer attachment scores, so the sentence
    reflects what the machine actually comes with rather than what it
    could theoretically support.
    Default is no sentence.
    """
    att_text = getattr(dealer_input, "attachments_included", None)
    detected_atts = _parse_attachment_keywords(att_text, dealer_input)

    if not detected_atts:
        return None  # nothing listed → nothing to call out

    # Map attachment type → (listing-ready display name, use case it covers).
    # Display names are title-cased to work with the "X included." format.
    _ATT_INFO: dict[str, tuple[str, str]] = {
        "breaker":  ("Hydraulic breaker",      "Demolition & Breaking"),
        "auger":    ("Auger attachment",        "Auger Work"),
        "grapple":  ("Grapple",                "Land Clearing"),
        "thumb":    ("Hydraulic thumb",         "Land Clearing"),
        "trencher": ("Trencher attachment",     "Utility Trenching"),
    }

    top_set = set(top_labels)
    unrepresented: list[str] = []

    for att_type in detected_atts:
        info = _ATT_INFO.get(att_type)
        if not info:
            continue
        display, covers_uc = info
        if covers_uc not in top_set:
            unrepresented.append(display)

    if not unrepresented:
        return None

    # One attachment call-out only — keep it tight
    return f"Includes {unrepresented[0].lower()}."


def _payload_from_ssl_ctl_result(result, dealer_input, equipment_type: str) -> dict:
    """Extract listing payload from a skid steer or CTL ScorerResult."""
    cap_class = getattr(result, "capability_class", None)

    # Use cases: machine-size-aware, attachment-influenced, deduplicated
    use_cases = _build_ranked_use_cases(
        all_use_cases=result.all_use_cases,
        dealer_input=dealer_input,
        equipment_type=equipment_type,
        cap_class=cap_class,
    )

    # Supporting sentence: only when dealer-confirmed high flow adds buyer
    # signal not already communicated by the use case descriptors
    attachment_sentence = _supporting_sentence_ssl_ctl(result, use_cases, dealer_input)

    return {
        "top_use_cases_for_listing": use_cases,
        "attachment_sentence":       attachment_sentence,
        "limitation_sentence":       _limitation_from_ssl_ctl(result, dealer_input),
    }


def _payload_from_mex_result(result, dealer_input) -> dict:
    """Extract listing payload from a mini excavator ScorerResult."""
    cap_class = getattr(result, "capability_class", None)

    # Use cases: attachment-influenced, mini-ex-appropriate
    use_cases = _build_ranked_use_cases(
        all_use_cases=result.all_use_cases,
        dealer_input=dealer_input,
        equipment_type=_MEX,
        cap_class=cap_class,
    )

    # Supporting sentence: only when a dealer-listed attachment isn't already
    # represented by the top use case labels
    attachment_sentence = _supporting_sentence_mex(result, use_cases, dealer_input)

    return {
        "top_use_cases_for_listing": use_cases,
        "attachment_sentence":       attachment_sentence,
        "limitation_sentence":       _limitation_from_mex(result),
    }


# ---------------------------------------------------------------------------
# Backhoe record builder + payload
# ---------------------------------------------------------------------------

def _build_bh_record(dealer_input, resolved_specs: dict):
    """Build a MachineRecord for the backhoe scorer from DealerInput + resolved specs."""
    from scorers.backhoe.backhoe_use_case_scorer_v1_0 import MachineRecord

    # Resolve dig depth — spec resolver stores as string "X ft Y in"
    dig_depth = resolved_specs.get("max_dig_depth_ft")
    if dig_depth is None:
        raw = resolved_specs.get("max_dig_depth")
        if isinstance(raw, (int, float)):
            dig_depth = float(raw)
        elif isinstance(raw, str):
            import re as _re
            m = _re.match(r"(\d+)\s*ft(?:\s*(\d+)\s*in)?", raw.strip())
            if m:
                dig_depth = int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)

    features: dict = {}
    # enclosed_cab from cab_type
    enclosed = _enclosed_cab_from_cab_type(dealer_input)
    if enclosed is not None:
        features["enclosed_cab"] = enclosed
    # rear_aux_hydraulics — backhoe-specific; use generic aux_hydraulics if present
    if getattr(dealer_input, "aux_hydraulics", None):
        features["rear_aux_hydraulics"] = True

    return MachineRecord(
        horsepower_hp        = resolved_specs.get("horsepower_hp") or resolved_specs.get("net_hp"),
        operating_weight_lbs = resolved_specs.get("operating_weight_lbs") or resolved_specs.get("operating_weight_lb"),
        max_dig_depth_ft     = dig_depth,
        hydraulic_flow_gpm   = resolved_specs.get("hydraulic_flow_gpm"),
        manufacturer         = getattr(dealer_input, "make", None),
        model                = getattr(dealer_input, "model", None),
        hours                = getattr(dealer_input, "hours", None),
        features             = features,
    )


# Backhoe scorer produces scores in the 20–60 range when key specs are missing
# (bucket force, loader breakout).  Use a lower threshold so top-scoring use
# cases still surface rather than returning an empty payload.
_BH_SCORE_THRESHOLD = 0.0   # take top 2 by raw score; > 0 implied by filter above


def _payload_from_bh_result(result, dealer_input) -> dict:
    """Extract listing payload from a backhoe ScorerResult."""
    use_cases = _build_ranked_use_cases(
        all_use_cases=result.all_use_cases,
        dealer_input=dealer_input,
        equipment_type=_BH,
        cap_class=getattr(result, "capability_class", None),
        score_threshold=_BH_SCORE_THRESHOLD,
        apply_attachment_boosts=False,   # backhoe scorer internalizes its own feature scoring
    )
    return {
        "top_use_cases_for_listing": use_cases,
        "attachment_sentence":       None,
        "limitation_sentence":       None,
    }


# ---------------------------------------------------------------------------
# Telehandler inline use case logic (no dedicated scorer)
# ---------------------------------------------------------------------------

def _score_telehandler_inline(dealer_input, resolved_specs: dict) -> dict:
    """
    Rule-based use case output for telehandlers.

    Telehandlers are spec-driven (capacity × reach), not job-driven like CTL/SSL.
    Use cases reflect real placement and reach work, tiered by max lift height.

    Height tiers:
      ≥ 50 ft  → Rooftop Material Placement + High-Reach Loading
                 (commercial roofing, steel erection, over-obstacle reach)
      42–49 ft → Jobsite Reach & Placement + Pallet Handling
                 (crossover class: general placement, staging, pallet distribution)
                 Note: these machines CAN reach residential roofs but are not
                 specialist roof-first machines — jobsite crossover is the real
                 primary market, rooftop is secondary/occasional.
      < 42 ft  → Pallet Handling + Jobsite Reach & Placement
                 (material distribution, on-site staging, short-reach work)

    Agriculture gating:
      max_lift_height ≤ 44 ft → Agricultural Use structurally allowed
      max_lift_height > 44 ft → Agricultural Use structurally suppressed
      In both cases, agriculture only appears when an explicit ag signal is
      present on the dealer input (ag_use flag). Without that signal it is
      omitted regardless of lift height.

    Not used: "General Jobsite", "Concrete Support", "Truck Loading" —
    these labels are either too generic or merge naturally into the reach tiers.
    """
    lift_height_raw = (
        resolved_specs.get("max_lift_height_ft")
        or resolved_specs.get("max_lift_height")
        or resolved_specs.get("max_load_height_ft")
    )
    lift_height = float(lift_height_raw) if lift_height_raw else 0.0

    if lift_height >= 50:
        use_cases = ["Rooftop Material Placement", "High-Reach Loading"]
    elif lift_height >= 42:
        # Crossover class: general placement and pallet handling are the
        # primary roles. Rooftop work is possible but not the defining use.
        use_cases = ["Jobsite Reach & Placement", "Pallet Handling"]
    else:
        use_cases = ["Pallet Handling", "Jobsite Reach & Placement"]

    # Agriculture: only when ≤44 ft AND an explicit ag signal is present.
    # getattr safely returns None if dealer_input lacks the ag_use field.
    if lift_height <= 44 and getattr(dealer_input, "ag_use", None):
        use_cases.append("Agricultural Use")

    return {
        "top_use_cases_for_listing": use_cases,
        "attachment_sentence":       None,
        "limitation_sentence":       None,
    }


# ---------------------------------------------------------------------------
# Dozer inline use case logic (no dedicated scorer)
# ---------------------------------------------------------------------------

def _score_dozer_inline(dealer_input, resolved_specs: dict) -> dict:
    """
    Rule-based use case output for dozers.

    Grading & Site Prep is universal — it is the primary work a dozer does.
    Second use case:
      HP ≥ 200 → Land Clearing (large blade, production-class push capacity)
      HP < 200 → Land Clearing (still correct; dozing is inherently clearing work)
    Grade control type drives an attachment sentence when confirmed.
    """
    hp = resolved_specs.get("horsepower_hp") or resolved_specs.get("net_hp")
    grade_control = getattr(dealer_input, "grade_control_type", None)

    use_cases = ["Grading & Site Prep", "Land Clearing"]

    att_sentence: "str | None" = None
    if grade_control and grade_control in ("2D", "3D"):
        att_sentence = f"{grade_control} grade control equipped."

    return {
        "top_use_cases_for_listing": use_cases,
        "attachment_sentence":       att_sentence,
        "limitation_sentence":       None,
    }


# ---------------------------------------------------------------------------
# Wheel loader inline use case logic (no dedicated scorer)
# ---------------------------------------------------------------------------

# Brands associated with ag / farm dealer channel.
# Matching is substring-based on make (lowercased), so "john deere" matches "deere".
_WL_AG_BRANDS = ("deere", "kubota", "new holland", "agco", "fendt", "massey")


def _score_wheel_loader_inline(dealer_input, resolved_specs: dict) -> dict:
    """
    Rule-based use case output for compact wheel loaders.

    Wheel loaders are identity-driven, not job-first like CTL/SSL.
    Core identity: material handling + pallet/fork work + high-speed yard ops.

    Default (all machines — always 2 use cases):
      1. Material Handling & Yard Work
      2. Pallet Handling & Loading

    Optional 3rd use case (first qualifying signal wins, in priority order):
      Snow Removal      — snow keyword in free text, OR municipal context
                          (NOT attachment-gated like SSL — snow is a primary WL use)
      Farm & Property   — ag brand (JD, Kubota, etc.) and no snow signal
      Municipal/Utility — explicit municipal keyword and no snow signal and not ag

    Attachment sentence:
      SSL coupler present → note skid steer attachment compatibility
      Forks confirmed in free text and no coupler info → note forks included

    No limitation sentence — wheel loaders have no material buyer-facing spec gaps
    that are universally applicable at this classification level.
    """
    make_raw  = (getattr(dealer_input, "make", None) or "").lower().strip()
    brand_is_ag = any(b in make_raw for b in _WL_AG_BRANDS)

    # Aggregate free-text fields for keyword scanning (lowercase)
    free_text = " ".join(filter(None, [
        getattr(dealer_input, "attachments_included", None),
        getattr(dealer_input, "additional_details", None),
        getattr(dealer_input, "condition_notes", None),
        getattr(dealer_input, "additional_features", None),
    ])).lower()

    snow_signal = "snow" in free_text
    municipal_signal = any(k in free_text for k in (
        "municipal", "city", "county", "utility fleet", "government",
        "airport", "public works", "municipality",
    ))

    # Default: always these two
    use_cases: list[str] = ["Material Handling & Yard Work", "Pallet Handling & Loading"]

    # Conditional 3rd — priority: snow > farm > municipal
    if snow_signal or (municipal_signal and not brand_is_ag):
        use_cases.append("Snow Removal")
    elif brand_is_ag:
        use_cases.append("Farm & Property Work")
    elif municipal_signal:
        use_cases.append("Municipal / Utility Work")

    # Attachment sentence: SSL coupler is the defining identity feature for compact WLs.
    # coupler_type field: hydraulic / manual / pin-on / None (not equipped / unknown).
    # Any confirmed coupler (non-pin-on) on a wheel loader = SSL quick-attach compatible.
    coupler_raw = (getattr(dealer_input, "coupler_type", None) or "").lower().strip()
    forks_signal = any(k in free_text for k in ("fork", "pallet fork"))

    att_sentence: "str | None" = None
    if coupler_raw and "pin" not in coupler_raw:
        att_sentence = "Skid steer coupler compatible — accepts standard SSL attachments."
    elif forks_signal:
        att_sentence = "Pallet forks included."

    return {
        "top_use_cases_for_listing": use_cases,
        "attachment_sentence":       att_sentence,
        "limitation_sentence":       None,
    }


# ---------------------------------------------------------------------------
# Limitation extraction helpers
# ---------------------------------------------------------------------------

def _limitation_from_ssl_ctl(result, dealer_input=None) -> str | None:
    """
    Derive at most one material limitation sentence from SSL/CTL scorer result.
    Only flags that materially affect buyer expectation.
    """
    compat = getattr(result, "attachment_compatibility", {}) or {}
    cap_class = getattr(result, "capability_class", None)

    # No standard flow → minimal attachment capability
    tier1 = compat.get("tier_1_low_demand", {})
    if not tier1.get("compatible", True):
        return "No auxiliary hydraulics — attachment work limited to mechanical couplers only."

    # Open cab — material for demolition / debris buyers
    flags = getattr(result, "scoring_flags", []) or []
    for f in flags:
        if "OPEN CAB" in f or "ROPS" in f.upper():
            return "Open cab — operator exposure limits suitability for demolition or heavy debris work."

    # No high flow — only material for Class C/D where HF is a normal upgrade path
    # and buyers actively compare HF vs non-HF. Class A/B machines were never
    # marketed as forestry or cold-planing candidates; flagging the absence
    # reads as a defect rather than a feature gap.
    # Suppressed when the dealer has confirmed high flow is installed ("yes") —
    # the scorer may mark tier_3 as unknown due to missing spec data, but the
    # dealer confirmation takes precedence.
    dealer_confirmed_hf = getattr(dealer_input, "high_flow", None) == "yes"
    tier3 = compat.get("tier_3_high_demand", {})
    if not tier3.get("compatible", True) and cap_class in ("C", "D") and not dealer_confirmed_hf:
        return (
            "No high-flow package — forestry mulching, cold planing, "
            "and rotary cutting not supported."
        )

    return None


def _limitation_from_mex(result) -> str | None:
    """
    Derive at most one material limitation sentence from mini ex scorer result.
    """
    # No auxiliary hydraulics
    flags = getattr(result, "scoring_flags", []) or []
    for f in flags:
        if "NO AUX" in f.upper() or "NO AUXILIARY" in f.upper():
            return "No auxiliary hydraulics — powered attachment work not supported."

    # Class A or shallow dig depth — material for septic / utility buyers
    cap_class = getattr(result, "capability_class", None)
    all_uc = getattr(result, "all_use_cases", []) or []
    deep_trench_score = next(
        (uc.score for uc in all_uc
         if "Deep Trench" in uc.use_case or "Sewer" in uc.use_case),
        None,
    )
    if deep_trench_score is not None and deep_trench_score == 0:
        return "Dig depth limits sewer and deep utility work — best suited for residential and light commercial trench depths."

    # Tight access scored poorly — relevant for residential buyers
    tight_score = next(
        (uc.score for uc in all_uc if "Tight Access" in uc.use_case),
        None,
    )
    if tight_score is not None and tight_score < 40 and cap_class in ("C", "D"):
        return (
            "Machine width and tail swing limit use in tight residential "
            "or gate-restricted sites."
        )

    # Open cab on mini ex
    for f in flags:
        if "OPEN CAB" in f.upper() or "canopy" in f.lower():
            return "Canopy cab only — enclosed cab not available on this configuration."

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_use_case_payload(
    equipment_type: "str | None",
    dealer_input,
    resolved_specs: dict,
) -> "dict | None":
    """
    Run the appropriate scorer/logic and return a normalized listing payload.

    Parameters
    ----------
    equipment_type : "skid_steer" | "compact_track_loader" | "mini_excavator"
                     | "backhoe_loader" | "telehandler" | "dozer" | "wheel_loader"
                     Any other value (or None) returns None.
    dealer_input   : DealerInput instance.
    resolved_specs : Flat dict of resolved OEM spec values.

    Returns
    -------
    dict with keys: top_use_cases_for_listing, attachment_sentence, limitation_sentence
    or None if equipment_type is unsupported or an error occurs.
    """
    if not equipment_type or equipment_type not in _SUPPORTED_TYPES:
        return None

    # Normalize field names: handles both registry schema and spec-resolver
    # internal names so the same function works from both code paths.
    resolved_specs = _normalize_specs(resolved_specs)

    try:
        if equipment_type == _SSL:
            from scorers.skid_steer_use_case_scorer_v1_0 import score_skid_steer
            record = _build_ssl_record(dealer_input, resolved_specs)
            result = score_skid_steer(record)

            # Suppress all claims on Low confidence
            if getattr(result, "confidence_level", None) == "Low":
                return _empty_payload()

            return _payload_from_ssl_ctl_result(result, dealer_input, _SSL)

        elif equipment_type == _CTL:
            from scorers.ctl_use_case_scorer_v1_0 import score_ctl
            record = _build_ctl_record(dealer_input, resolved_specs)
            result = score_ctl(record)
            return _payload_from_ssl_ctl_result(result, dealer_input, _CTL)

        elif equipment_type == _MEX:
            from scorers.mini_ex_use_case_scorer_v1_0 import score_mini_ex
            record = _build_mex_record(dealer_input, resolved_specs)
            result = score_mini_ex(record)

            if getattr(result, "confidence_level", None) == "Low":
                return _empty_payload()

            return _payload_from_mex_result(result, dealer_input)

        elif equipment_type == _BH:
            from scorers.backhoe.backhoe_use_case_scorer_v1_0 import score_machine
            record = _build_bh_record(dealer_input, resolved_specs)
            result = score_machine(record)
            return _payload_from_bh_result(result, dealer_input)

        elif equipment_type == _TH:
            return _score_telehandler_inline(dealer_input, resolved_specs)

        elif equipment_type == _DZ:
            return _score_dozer_inline(dealer_input, resolved_specs)

        elif equipment_type == _WL:
            return _score_wheel_loader_inline(dealer_input, resolved_specs)

    except Exception:
        # Scorer errors must never break listing generation
        return None

    return None


def _empty_payload() -> dict:
    return {
        "top_use_cases_for_listing": [],
        "attachment_sentence":       None,
        "limitation_sentence":       None,
    }
