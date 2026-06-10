"""
capability_engine.py

Translates normalized machine specs into ordered capability tags.

V1 scope: CTL, SSL, Mini Excavator, Full-Size Excavator.

Input
-----
    equipment_type (str): Registry equipment_type string or short code.
    specs (dict): Normalized machine specs from registry / spec resolver.
    feature_flags (dict, optional): Boolean capability flags.

Output
------
    List[str]: Ordered capability tags, 3–5 items. Deterministic.

Rules
-----
    - Tags emitted only from the approved library for the category.
    - Retired / superseded tags never emitted.
    - One tag per concept group (highest-priority rule wins per group).
    - No duplicate tags.
    - Result ordered by rule priority (highest first).
    - Count clamped to [3, 5]; returns fewer only when < 3 rules fire.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Type aliases
# ─────────────────────────────────────────────────────────────────────────────

Specs = Dict[str, Any]
Flags = Dict[str, Any]
_Candidate = Tuple[str, str, int]  # (tag, concept_group, priority)

# ─────────────────────────────────────────────────────────────────────────────
# Approved tag libraries — final post-audit canonical sets
# ─────────────────────────────────────────────────────────────────────────────

_CTL_LIBRARY: frozenset = frozenset({
    "Forestry Mulching",
    "High-Flow Hydraulics",
    "Finish Grading",
    "Low Ground Pressure",
    "Breaker & Demolition Attachments",
    "Tight-Site Grading",
    "Heavy Material Handling",
    "Snow & Ice Removal",
    "Land Clearing",
    "Grade-Sensitive Work",
})

_SSL_LIBRARY: frozenset = frozenset({
    "High-Flow Hydraulics",
    "Heavy Material Handling",
    "Pallet Fork Operations",
    "Truck Loading Operations",
    "Brush Cutting",
    "Concrete & Demolition",
    "Tight-Site Grading",
    "Farm & Agricultural Use",
    "Material Handling",
})

_MINI_EX_LIBRARY: frozenset = frozenset({
    "Utility Trenching",
    "Deep Utility Trenching",
    "Residential Foundation Work",
    "Zero-Tail Swing Access",
    "Hydraulic Breaker Ready",
    "Drainage & Grading",
    "Thumb & Attachment Ready",
    "Tight-Site Demo Work",
    "Landscape Excavation",
    "Land Clearing",
})

_EX_LIBRARY: frozenset = frozenset({
    "Foundation Excavation",
    "Deep Foundation Work",
    "Mass Excavation",
    "Utility Trenching",
    "Pipe & Utility Installation",
    "Demolition Work",
    "Slope & Embankment Grading",
    "Lift & Place Operations",
    "Rock Excavation",
    "High-Reach Demo",
})

# Tags that must never appear in any output regardless of category.
_RETIRED_TAGS: frozenset = frozenset({
    "Rental-Ready Versatility",
    "General Purpose",
    "Versatile Machine",
    "Site Work",
    "Construction",
    "Earthmoving",
    "Agricultural Material Work",
    "High-Flow Attachment Work",
    "Demolition Attachment Work",
    "Material Handling Work",
    "Pallet & Load Operations",
    "Precision Grading",
    "Confined-Space Excavation",
    "Thumb & Grapple Work",
    "Demo in Tight Spaces",
    "Heavy Push Operations",
    "Front Loader Operations",
    "High-Reach Material Placement",
    "Agricultural Hay Handling",
    "Tree & Vegetation Work",
    "Tight-Clearance Access",
    "Slope & Embankment Work",
    "Heavy Lift Operations",
    "Demolition Material Handling",
    "Utility Corridor Cutting",
})

_CATEGORY_LIBRARIES: Dict[str, frozenset] = {
    "CTL":  _CTL_LIBRARY,
    "SSL":  _SSL_LIBRARY,
    "MINI": _MINI_EX_LIBRARY,
    "EX":   _EX_LIBRARY,
}

# Equipment-type string normalizer — handles registry values and short codes.
_TYPE_MAP: Dict[str, str] = {
    "compact_track_loader":  "CTL",
    "ctl":                   "CTL",
    "skid_steer_loader":     "SSL",
    "skid_steer":            "SSL",
    "ssl":                   "SSL",
    "mini_excavator":        "MINI",
    "mini_ex":               "MINI",
    "mini":                  "MINI",
    "excavator":             "EX",
    "full_size_excavator":   "EX",
    "large_excavator":       "EX",
    "ex":                    "EX",
}

# ─────────────────────────────────────────────────────────────────────────────
# Spec / flag accessors
# ─────────────────────────────────────────────────────────────────────────────

def _sp(specs: Specs, key: str, default: float = 0.0) -> float:
    """Return numeric spec; substitutes default for None / missing."""
    v = specs.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _ss(specs: Specs, key: str, default: str = "") -> str:
    """Return string spec; substitutes default for None / missing."""
    v = specs.get(key)
    return default if v is None else str(v)


def _sf(flags: Flags, key: str) -> bool:
    """Return boolean feature flag; defaults to False."""
    v = flags.get(key)
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "1", "yes")


# ─────────────────────────────────────────────────────────────────────────────
# Per-category candidate generators
#
# Each returns a list of (tag, concept_group, priority) triples.
#   priority — int, higher wins within a concept group and in overall ranking.
#   concept_group — str; only the highest-priority tag per group is emitted.
#                   Use a unique string to make a tag standalone (no grouping).
# ─────────────────────────────────────────────────────────────────────────────

def _ctl_candidates(specs: Specs, flags: Flags) -> List[_Candidate]:
    roc      = _sp(specs, "rated_operating_capacity_lbs")
    aux_high = _sp(specs, "aux_flow_high_gpm")
    aux_std  = _sp(specs, "aux_flow_standard_gpm")
    pressure = _sp(specs, "hydraulic_pressure_standard_psi")
    lift     = _ss(specs, "lift_path")
    width    = specs.get("width_over_tires_in")
    gp       = specs.get("ground_pressure_psi")   # rarely populated in CTL registry
    hf       = _sf(flags, "high_flow_available")

    out: List[_Candidate] = []

    # concept: high_flow  (Forestry Mulching > High-Flow Hydraulics > Land Clearing)
    # null aux_flow_high_gpm = confirmed flag but no GPM data → emit HFH (not FM).
    # stored zero = high-flow absent/unknown → fall through to Land Clearing.
    raw_aux_high = specs.get("aux_flow_high_gpm")
    if hf and raw_aux_high is not None and aux_high >= 30:
        out.append(("Forestry Mulching", "high_flow", 100))
    if hf and raw_aux_high is not None and aux_high >= 20:
        out.append(("High-Flow Hydraulics", "high_flow", 80))
    if hf and raw_aux_high is None:
        out.append(("High-Flow Hydraulics", "high_flow", 80))
    if hf:
        out.append(("Land Clearing", "high_flow", 30))

    # material capacity — secondary tipping-load gate handles Bobcat 35%-convention ROC
    tipping = _sp(specs, "tipping_load_lbs")
    if roc >= 3000 or (tipping > 0 and tipping / 2 >= 3000):
        out.append(("Heavy Material Handling", "material", 90))

    # concept: grading  (Finish Grading > Grade-Sensitive Work)
    if lift == "vertical" and roc >= 2800:
        out.append(("Finish Grading", "grading", 70))
    if lift == "vertical":
        out.append(("Grade-Sensitive Work", "grading", 40))

    # standalone — breaker / demolition
    if pressure >= 3200 and aux_std >= 18:
        out.append(("Breaker & Demolition Attachments", "breaker", 60))

    # standalone — snow & ice (ROC gate only; two-speed is common enough to not require)
    if roc >= 2800:
        out.append(("Snow & Ice Removal", "snow_ice", 50))

    # standalone — tight site
    if width is not None and float(width) <= 68:
        out.append(("Tight-Site Grading", "tight_site", 50))

    # standalone — low ground pressure (requires OEM-published PSI field)
    if gp is not None and float(gp) <= 4.5:
        out.append(("Low Ground Pressure", "lgp", 50))

    return out


def _ssl_candidates(specs: Specs, flags: Flags) -> List[_Candidate]:
    roc      = _sp(specs, "rated_operating_capacity_lbs")
    lift     = _ss(specs, "lift_path")
    aux_high = _sp(specs, "aux_flow_high_gpm")
    aux_std  = _sp(specs, "aux_flow_standard_gpm")
    pressure = _sp(specs, "hydraulic_pressure_standard_psi")
    width    = specs.get("width_over_tires_in")
    weight   = _sp(specs, "operating_weight_lbs")
    hf       = _sf(flags, "high_flow_available")

    out: List[_Candidate] = []

    # concept: heavy_lift  (Truck Loading Operations > Heavy Material Handling)
    if lift == "vertical" and roc >= 2800:
        out.append(("Truck Loading Operations", "heavy_lift", 100))
    if lift == "vertical" and roc >= 2500:
        out.append(("Heavy Material Handling", "heavy_lift", 80))

    # high flow — null aux_flow_high_gpm (confirmed flag, unknown GPM) still emits HFH
    raw_aux_high = specs.get("aux_flow_high_gpm")
    if hf and (raw_aux_high is None or aux_high >= 22):
        out.append(("High-Flow Hydraulics", "high_flow", 90))

    # pallet fork — vertical lift required (radial arc reduces fork precision)
    if lift == "vertical" and roc >= 1800:
        out.append(("Pallet Fork Operations", "pallet", 70))

    # concrete & demolition
    if pressure >= 3000 and aux_std >= 20:
        out.append(("Concrete & Demolition", "concrete_demo", 60))

    # brush cutting
    if aux_std >= 14 or (hf and aux_high >= 18):
        out.append(("Brush Cutting", "brush", 50))

    # tight site
    if width is not None and float(width) <= 64:
        out.append(("Tight-Site Grading", "tight_site", 50))

    # farm & agricultural
    if 0 < weight < 6500 and roc < 2200:
        out.append(("Farm & Agricultural Use", "farm", 30))

    # Material Handling fallback — priority 10 ensures it lands last.
    # A min-position constraint in the engine prevents it from occupying
    # positions 0 or 1 (i.e., it must be 3rd tag or later).
    if roc >= 1400:
        out.append(("Material Handling", "mat_fallback", 10))

    return out


def _mini_ex_candidates(specs: Specs, flags: Flags) -> List[_Candidate]:
    weight   = _sp(specs, "operating_weight_lbs")
    dig_ft   = _sp(specs, "max_dig_depth_ft")
    # Confirmed aux circuit fields — no main-circuit fallback (used for HBR and Land Clearing).
    aux_flow_confirmed  = _sp(specs, "aux_flow_primary_gpm")
    aux_pressure_confirmed = _sp(specs, "aux_pressure_primary_psi")
    # Fallback versions retain main-circuit data for has_aux detection (softer claims).
    aux_flow = aux_flow_confirmed or _sp(specs, "hydraulic_flow_gpm")
    pressure = aux_pressure_confirmed or _sp(specs, "hydraulic_pressure_psi")
    tail_sw  = _ss(specs, "tail_swing_type")
    blade_w  = specs.get("blade_width_in")
    breakout = _sp(specs, "bucket_breakout_force_lbs")
    aux_hyd  = specs.get("auxiliary_hydraulics")

    # auxiliary hydraulics: present if not explicitly False and flow/pressure populated
    has_aux: bool = (aux_hyd is not False) and (aux_flow > 0 or pressure > 0)

    is_zero: bool = tail_sw in (
        "zero", "zero_tail", "zero_swing", "ztail",
        "zero tail", "zero_tail_swing",
    )

    out: List[_Candidate] = []

    # concept: trenching  (Deep Utility Trenching > Utility Trenching)
    if dig_ft >= 9.0:
        out.append(("Deep Utility Trenching", "trenching", 100))
    if dig_ft >= 6.5:
        out.append(("Utility Trenching", "trenching", 70))

    # zero tail swing (independent — different buyer signal than trenching depth)
    if is_zero:
        out.append(("Zero-Tail Swing Access", "tail_swing", 90))

    # residential foundation (depth + weight gate — independent of trenching)
    if dig_ft >= 8.0 and weight >= 6000:
        out.append(("Residential Foundation Work", "foundation", 80))

    # hydraulic breaker ready — requires confirmed aux circuit pressure; no main-circuit fallback
    if aux_pressure_confirmed >= 2500:
        out.append(("Hydraulic Breaker Ready", "breaker", 70))

    # drainage & grading — requires dozer blade
    if blade_w is not None and float(blade_w) > 0 and dig_ft >= 5:
        out.append(("Drainage & Grading", "drainage", 60))

    # tight-site demo (zero tail + strong breakout)
    if is_zero and breakout >= 4000:
        out.append(("Tight-Site Demo Work", "tight_demo", 55))

    # land clearing — confirmed aux flow only; no main-circuit fallback
    if has_aux and aux_flow_confirmed >= 12:
        out.append(("Land Clearing", "land_clearing", 45))

    # thumb & attachment ready
    if has_aux:
        out.append(("Thumb & Attachment Ready", "thumb_attach", 40))

    # landscape excavation (lighter machines, accessible dig depth)
    if 0 < weight <= 5000 and dig_ft >= 5:
        out.append(("Landscape Excavation", "landscape", 30))

    return out


def _ex_candidates(specs: Specs, flags: Flags) -> List[_Candidate]:
    weight    = _sp(specs, "operating_weight_lbs")
    dig_in    = _sp(specs, "max_dig_depth_in")
    pressure  = _sp(specs, "hydraulic_pressure_psi")
    bkt_force = _sp(specs, "bucket_dig_force_lbf")
    reach     = _sp(specs, "max_reach_ground_in")
    dump_ht   = _sp(specs, "max_dump_height_in")
    boom_type = _ss(specs, "boom_type")

    out: List[_Candidate] = []

    # mass excavation — 20-ton class
    if weight >= 44000:
        out.append(("Mass Excavation", "production_class", 100))

    # high-reach demolition (confirmed configuration only)
    if boom_type in ("high_reach", "high_reach_demolition") and weight >= 40000:
        out.append(("High-Reach Demo", "high_reach", 95))

    # concept: foundation  (Deep Foundation Work > Foundation Excavation)
    if dig_in >= 300:
        out.append(("Deep Foundation Work", "foundation", 90))
    if dig_in >= 240 and weight >= 25000:
        out.append(("Foundation Excavation", "foundation", 70))

    # rock excavation — requires confirmed high pressure and breakout
    if pressure >= 4500 and bkt_force >= 25000:
        out.append(("Rock Excavation", "rock", 85))

    # demolition work
    if bkt_force >= 25000 and pressure >= 4000:
        out.append(("Demolition Work", "demo", 72))

    # concept: pipe/utility  (Pipe & Utility Installation > Utility Trenching)
    # scoped to mid-class machines (< 20-ton class)
    if weight < 45000 and dig_in >= 200:
        out.append(("Pipe & Utility Installation", "pipe_utility", 62))
    if weight < 45000 and dig_in >= 180:
        out.append(("Utility Trenching", "pipe_utility", 50))

    # slope & embankment grading — long-reach machines
    if reach >= 350:
        out.append(("Slope & Embankment Grading", "slope_reach", 50))

    # lift & place operations
    if dump_ht >= 250 and weight >= 30000:
        out.append(("Lift & Place Operations", "lift_place", 48))

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Core engine
# ─────────────────────────────────────────────────────────────────────────────

_CANDIDATE_FNS: Dict[str, Any] = {
    "CTL":  _ctl_candidates,
    "SSL":  _ssl_candidates,
    "MINI": _mini_ex_candidates,
    "EX":   _ex_candidates,
}

# SSL "Material Handling" must not occupy position 0 or 1 (0-indexed).
# If it cannot satisfy the constraint (fewer than 2 other tags precede it),
# it is dropped entirely — it adds no value without adequate context.
_SSL_MATERIAL_HANDLING_MIN_POS = 2


def get_capability_tags(
    equipment_type: str,
    specs: Dict[str, Any],
    feature_flags: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Translate normalized machine specs into ordered capability tags.

    Parameters
    ----------
    equipment_type : str
        Registry equipment_type string or short code.
        Supported values: ``compact_track_loader`` / ``ctl``,
        ``skid_steer_loader`` / ``skid_steer`` / ``ssl``,
        ``mini_excavator`` / ``mini_ex`` / ``mini``,
        ``excavator`` / ``full_size_excavator`` / ``large_excavator`` / ``ex``.
    specs : dict
        Normalized machine specs (registry or resolver output).
    feature_flags : dict, optional
        Boolean feature flags (e.g. ``high_flow_available``, ``two_speed_available``).
        Defaults to empty dict when not provided.

    Returns
    -------
    List[str]
        Ordered capability tags. Between 3 and 5 items when enough rules
        fire; fewer only when the machine specs are sparse.

    Raises
    ------
    ValueError
        ``equipment_type`` is not in the supported set.
    RuntimeError
        Engine-level rule violation (retired tag or tag outside library).
        Should never fire in production; indicates a rule authoring error.
    """
    flags: Flags = feature_flags or {}

    normalized = equipment_type.lower().replace("-", "_").replace(" ", "_")
    category = _TYPE_MAP.get(normalized, "")
    if not category:
        raise ValueError(
            f"Unsupported equipment_type {equipment_type!r}. "
            f"Supported aliases: {sorted(_TYPE_MAP)}"
        )

    library = _CATEGORY_LIBRARIES[category]
    candidates: List[_Candidate] = _CANDIDATE_FNS[category](specs, flags)

    # Sort by descending priority; stable sort preserves insertion order on tie.
    candidates.sort(key=lambda c: c[2], reverse=True)

    # Deduplicate: one tag per concept group, no duplicate tag strings.
    seen_groups: set = set()
    seen_tags: set = set()
    selected: List[str] = []

    for tag, group, _priority in candidates:
        if tag in seen_tags:
            continue
        if group in seen_groups:
            continue
        seen_groups.add(group)
        seen_tags.add(tag)
        selected.append(tag)

    # SSL: drop "Material Handling" if fewer than 2 other tags precede it.
    if category == "SSL" and "Material Handling" in selected:
        if selected.index("Material Handling") < _SSL_MATERIAL_HANDLING_MIN_POS:
            selected.remove("Material Handling")

    # Clamp to top 5.
    result = selected[:5]

    # Invariant checks — guard against rule authoring bugs.
    for tag in result:
        if tag not in library:
            raise RuntimeError(
                f"Engine emitted {tag!r} which is outside the {category} library"
            )
        if tag in _RETIRED_TAGS:
            raise RuntimeError(
                f"Engine emitted retired tag {tag!r}"
            )

    return result
