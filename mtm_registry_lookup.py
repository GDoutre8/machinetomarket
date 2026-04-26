"""
MTM Registry Lookup Module
Machine-to-Market — v1.2

Loads the three canonical MTM registries into a unified in-memory dataset
and exposes lookup_machine() for use by the listing parser and autofill engine.

Canonical sources:
  - mtm_skid_steer_registry_v1_16.json   (skid_steer           — 255 records)
  - mtm_ctl_registry_v1_6.json           (compact_track_loader — 195 records)
  - mtm_mini_ex_registry_v1.json         (mini_excavator        — 48 records)

v1.1 changes vs v1.0:
  - Canonical equipment_type values locked: skid_steer | compact_track_loader | mini_excavator
  - Equipment type alias map normalizes all legacy/shorthand values on load and on filter input
  - Output schema standardized: universal identity block + primary_power_spec / primary_capacity_spec
  - Ambiguous model guard: candidates within 0.03 of top score → match=False, reason=ambiguous_model
  - REGISTRY_FILENAMES keys updated to canonical type names

v1.2 changes vs v1.1:
  - Tiered field-level confidence system replacing single-threshold injection
  - Three tiers: Core (≥0.80), Supplemental (≥0.68), Provisional (≥0.55)
  - SPEC_TIERS_BY_TYPE maps equipment type → {core, supplemental, provisional} field lists
  - _build_tiered_specs() applies per-field confidence gating and emits labeled output
  - spec_sheet: ordered flat list ready for listing injection (~10–12 specs per machine)
  - tiered_specs: full structured breakdown with confidence + behavior metadata
  - Backward compat preserved: primary_power_spec, primary_capacity_spec, hydraulics still present
  - Extended equipment types in tier maps: excavator, telehandler, wheel_loader (future registries)
"""

import json
import re
import os
from difflib import SequenceMatcher
from typing import Optional

# ---------------------------------------------------------------------------
# CANONICAL EQUIPMENT TYPES
# These are the ONLY valid equipment_type values returned by the system.
# ---------------------------------------------------------------------------

EQ_SKID_STEER   = "skid_steer"
EQ_CTL          = "compact_track_loader"
EQ_MINI_EX      = "mini_excavator"
EQ_BACKHOE      = "backhoe_loader"
EQ_DOZER        = "dozer"
EQ_SCISSOR_LIFT = "scissor_lift"
EQ_BOOM_LIFT    = "boom_lift"

CANONICAL_EQ_TYPES = {EQ_SKID_STEER, EQ_CTL, EQ_MINI_EX}

# Maps any input or registry-stored value → canonical equipment_type string
EQUIPMENT_TYPE_ALIASES = {
    # skid_steer
    "skid_steer":           EQ_SKID_STEER,
    "skidsteer":            EQ_SKID_STEER,
    "skid_steer_loader":    EQ_SKID_STEER,
    "skidsteerloader":      EQ_SKID_STEER,
    "ssl":                  EQ_SKID_STEER,
    "skid steer":           EQ_SKID_STEER,
    "skid steer loader":    EQ_SKID_STEER,
    # compact_track_loader
    "compact_track_loader": EQ_CTL,
    "compacttrackloader":   EQ_CTL,
    "ctl":                  EQ_CTL,
    "compact track loader": EQ_CTL,
    "track loader":         EQ_CTL,
    # mini_excavator
    "mini_excavator":       EQ_MINI_EX,
    "miniexcavator":        EQ_MINI_EX,
    "mini excavator":       EQ_MINI_EX,
    "mini ex":              EQ_MINI_EX,
    "miniex":               EQ_MINI_EX,
    "mini_ex":              EQ_MINI_EX,
    # backhoe_loader
    "backhoe_loader":       EQ_BACKHOE,
    "backhoe":              EQ_BACKHOE,
    "backhoe loader":       EQ_BACKHOE,
    "bhl":                  EQ_BACKHOE,
    "tractor loader backhoe": EQ_BACKHOE,
    "tlb":                  EQ_BACKHOE,
    # dozer
    "dozer":                EQ_DOZER,
    "crawler_dozer":        EQ_DOZER,
    "crawler dozer":        EQ_DOZER,
    "bulldozer":            EQ_DOZER,
    "crawler tractor":      EQ_DOZER,
    # scissor_lift
    "scissor_lift":         EQ_SCISSOR_LIFT,
    "scissor lift":         EQ_SCISSOR_LIFT,
    "scissors":             EQ_SCISSOR_LIFT,
    "scissorlift":          EQ_SCISSOR_LIFT,
    "slab scissor":         EQ_SCISSOR_LIFT,
    # boom_lift
    "boom_lift":            EQ_BOOM_LIFT,
    "boom lift":            EQ_BOOM_LIFT,
    "boomlift":             EQ_BOOM_LIFT,
    "articulating boom":    EQ_BOOM_LIFT,
    "telescopic boom":      EQ_BOOM_LIFT,
    "manlift":              EQ_BOOM_LIFT,
    "man lift":             EQ_BOOM_LIFT,
}

def _resolve_eq_type(raw: str) -> Optional[str]:
    """
    Resolve any equipment type string to its canonical MTM value.
    Tries exact key first, then strips non-alpha chars as fallback.
    Returns None if unrecognized.
    """
    if not raw:
        return None
    key = raw.lower().strip()
    result = EQUIPMENT_TYPE_ALIASES.get(key)
    if result:
        return result
    # Fallback: strip everything except letters and underscores
    stripped = re.sub(r"[^a-z_]", "", key)
    return EQUIPMENT_TYPE_ALIASES.get(stripped)


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

_DEFAULT_REGISTRY_DIR = os.environ.get(
    "MTM_REGISTRY_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry")
)

def _registry_path(filename: str) -> str:
    """Resolve a registry filename. Checks MTM_REGISTRY_DIR, active/ subdir, then cwd."""
    explicit = os.path.join(_DEFAULT_REGISTRY_DIR, filename)
    if os.path.exists(explicit):
        return explicit
    active_path = os.path.join(_DEFAULT_REGISTRY_DIR, "active", filename)
    if os.path.exists(active_path):
        return active_path
    cwd_path = os.path.join(os.getcwd(), filename)
    if os.path.exists(cwd_path):
        return cwd_path
    raise FileNotFoundError(
        f"Registry file '{filename}' not found. "
        "Set MTM_REGISTRY_DIR or run from the directory containing the registry files."
    )

# Keys are canonical equipment_type values
REGISTRY_FILENAMES = {
    EQ_SKID_STEER:   "mtm_skid_steer_registry_v1_18.json",
    EQ_CTL:          "mtm_ctl_registry_v1_32.json",
    EQ_MINI_EX:      "mtm_mini_ex_registry_v2_2.json",
    EQ_BACKHOE:      "mtm_backhoe_loader_registry_v1.json",
    EQ_DOZER:        "mtm_dozer_registry_v1.json",
    EQ_SCISSOR_LIFT: "mtm_scissor_lift_registry_v1.json",
    EQ_BOOM_LIFT:    "mtm_boom_lift_registry_v1.json",
    "excavator":     "mtm_excavator_registry_v2.json",
    "wheel_loader":  "mtm_wheel_loader_registry_v1_2.json",
    "telehandler":   "mtm_telehandler_registry_v3.json",
}

# ---------------------------------------------------------------------------
# MANUFACTURER ALIAS MAP
# ---------------------------------------------------------------------------

MANUFACTURER_ALIASES = {
    # Caterpillar
    "cat":           "Caterpillar",
    "caterpillar":   "Caterpillar",
    "cat.":          "Caterpillar",
    # Genie
    "genie":         "Genie",
    # JLG
    "jlg":           "JLG",
    # Skyjack
    "skyjack":       "Skyjack",
    # Komatsu
    "komatsu":       "Komatsu",
    # John Deere
    "jd":            "John Deere",
    "john deere":    "John Deere",
    "deere":         "John Deere",
    "johndeere":     "John Deere",
    # Bobcat
    "bobcat":        "Bobcat",
    "bob cat":       "Bobcat",
    # Case
    "case":          "Case",
    "case ce":       "Case",
    # Kubota
    "kubota":        "Kubota",
    # New Holland
    "new holland":   "New Holland",
    "nh":            "New Holland",
    "newholland":    "New Holland",
    # Takeuchi
    "takeuchi":      "Takeuchi",
    # ASV
    "asv":           "ASV",
    # Gehl
    "gehl":          "Gehl",
    # JCB
    "jcb":           "JCB",
    # Wacker Neuson
    "wacker neuson": "Wacker Neuson",
    "wacker":        "Wacker Neuson",
    "wackerneuson":  "Wacker Neuson",
    # Yanmar
    "yanmar":        "Yanmar",
}

# Minimum fuzzy match ratio to accept a result
FUZZY_THRESHOLD = 0.72

# Candidates within this band of the top score are treated as ambiguous
AMBIGUITY_BAND = 0.03

# ---------------------------------------------------------------------------
# MODEL BRIDGE ALIASES
# Deterministic shorthand → canonical registry model map.
# Applied inside lookup_machine() before scoring, as a pre-normalization step.
# Only include entries where the target model EXISTS in the registry.
# This is NOT fuzzy matching — exact key lookup only.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# KUBOTA MEX SUFFIX-STRIPPING CONSTANTS  (Phase 1 — Approach B)
#
# Kubota mini excavators sometimes appear in listings with an emissions-tier
# suffix appended to the generation number (e.g. KX040-4R3T, U35-4R1).
# These suffixes are NOT stored as separate registry records; the base model
# (KX040-4, U35-4, etc.) covers all production years.
#
# _KUBOTA_MEX_BASE_MODELS is the authoritative set of Kubota MEX registry
# entries that participate in suffix stripping.  Only these stripped values
# are ever returned — the registry-existence check is an additional guard.
#
# Scope is intentionally narrow:
#   - Kubota make only (case-insensitive)
#   - /R[1-3]T?$/ suffix only — matches R1, R2, R3, R1T, R2T, R3T
#   - Base model must be in _KUBOTA_MEX_BASE_MODELS
# ---------------------------------------------------------------------------

_KUBOTA_MEX_BASE_MODELS: frozenset = frozenset({
    "KX033-4", "KX040-4", "KX057-6", "KX080-4",
    "U17", "U27-4", "U35-4", "U55-5",
})

_KUBOTA_MEX_SUFFIX_RE = re.compile(r"R[1-3]T?$", re.IGNORECASE)

MODEL_BRIDGE_ALIASES: dict[str, str] = {
    # Caterpillar CTL — shorthand without generation suffix
    # Note: 289d/259d/279d already resolve via slug_match (conf=0.95).
    # Bridge entries are included here as explicit overrides for clarity.
    "289d":  "289D3",
    "259d":  "259D3",
    "279d":  "279D3",
    # Kubota CTL — SVL75/SVL65 do NOT slug-match their -2 successors; bridge required.
    # Keys are pre-normalized (lowercase, spaces and hyphens stripped) because the
    # bridge lookup normalizes the input key before lookup — see step 1b in lookup_machine().
    "svl95":         "SVL95-2S",
    "svl75":         "SVL75-2",   # bare "svl75" / "svl 75" / "svl-75" → current gen
    "svl65":         "SVL65-2",   # bare "svl65" / "svl 65" / "svl-65" → current gen
    "svl75gen1":     "SVL75",     # explicit gen1 queries → first-generation record
    "svl75original": "SVL75",
    "svl65gen1":     "SVL65",
    "svl65original": "SVL65",
    # Kubota mini excavator — generation-suffix variants.
    # R3T (and similar Tier 4 Final / emissions-generation suffixes) appear in
    # auction listings but are not stored as separate registry records.
    # The base model KX040-4 covers all production years (2013–2024).
    # Key normalization: re.sub(r"[\s\-]", "", input.lower()) — hyphens and spaces
    # are both stripped, so "KX040-4R3T", "KX0404R3T", "KX040 4R3T" all resolve
    # to key "kx0404r3t" before this lookup.
    "kx0404r3t": "KX040-4",
    # Case backhoe — registry model "580N / 580 Super N" scores too low against
    # plain "580N" input (fuzzy 0.47).  Slug "case_580" already handles bare "580"
    # via containment (0.95).  Bridge covers the common "580N" and "580SN" inputs.
    "580n":  "580N / 580 Super N",
    "580sn": "580N / 580 Super N",
}

# ---------------------------------------------------------------------------
# REGISTRY LOADER
# ---------------------------------------------------------------------------

def _load_registry(path: str) -> list[dict]:
    """Load a single registry JSON. Handles both list and {records:[...]} formats."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("records") or data.get("new_records", [])


def load_all_registries(filenames: dict = None) -> list[dict]:
    """
    Load all canonical registries into a unified flat list.

    On load, each record's equipment_type is normalized to its canonical value
    so all downstream code can rely on canonical types being present.
    A '_registry' key is injected for traceability (source file tracking).
    """
    filenames = filenames or REGISTRY_FILENAMES
    unified = []
    for canonical_type, filename in filenames.items():
        path = _registry_path(filename)
        records = _load_registry(path)
        for r in records:
            # Normalize equipment_type to canonical — registry files may store
            # legacy values like "skid_steer_loader" or "ctl"
            raw_eq = r.get("equipment_type") or r.get("category") or ""
            r["equipment_type"] = _resolve_eq_type(raw_eq) or canonical_type
            r["_registry"] = canonical_type   # traceability tag
        unified.extend(records)
    return unified


# ---------------------------------------------------------------------------
# NORMALIZATION HELPERS
# ---------------------------------------------------------------------------

def _normalize_str(s: str) -> str:
    """Lowercase, collapse punctuation and whitespace for comparison."""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


def _resolve_manufacturer(raw: str) -> Optional[str]:
    """
    Resolve a raw manufacturer string to its canonical form.
    Returns None if no match found.
    """
    key = _normalize_str(raw)
    if key in MANUFACTURER_ALIASES:
        return MANUFACTURER_ALIASES[key]
    for alias, canonical in MANUFACTURER_ALIASES.items():
        norm_alias = _normalize_str(alias)
        if key.startswith(norm_alias) or norm_alias.startswith(key):
            return canonical
    return None


def _model_score(input_model: str, record_model: str, record_slug: str) -> float:
    """
    Score a (input_model, record) pair. Returns 0.0–1.0.
      Exact normalized match  → 1.0
      Slug containment match  → 0.95
      Fuzzy SequenceMatcher   → ratio
    """
    norm_input = _normalize_str(input_model)
    norm_model = _normalize_str(record_model)
    norm_slug  = _normalize_str(record_slug)

    if norm_input == norm_model:
        return 1.0
    if norm_input in norm_slug or norm_slug.endswith(norm_input):
        return 0.95
    return SequenceMatcher(None, norm_input, norm_model).ratio()


def _strip_variant_suffix(
    make: str,
    model: str,
    registry_models: set,
) -> "str | None":
    """
    Strip Kubota MEX emissions-tier suffixes (R1, R2, R3, R1T, R2T, R3T).

    Returns the stripped base model string only when ALL four conditions hold:
      1. make is Kubota (case-insensitive)
      2. The suffix regex matches and actually changes the model string
      3. The stripped model is in _KUBOTA_MEX_BASE_MODELS
      4. The stripped model exists in the live registry_models set

    Returns None in all other cases — caller falls through with original result.
    """
    if not re.match(r"kubota", make, re.IGNORECASE):
        return None
    stripped = _KUBOTA_MEX_SUFFIX_RE.sub("", model).rstrip("-").strip()
    if stripped == model:
        return None
    # Resolve canonical casing from _KUBOTA_MEX_BASE_MODELS (input may be lowercase)
    stripped_lower = stripped.lower()
    canonical = next(
        (m for m in _KUBOTA_MEX_BASE_MODELS if m.lower() == stripped_lower),
        None,
    )
    if canonical is None:
        return None
    if canonical not in registry_models:
        return None
    return canonical


# ---------------------------------------------------------------------------
# SPEC INJECTION GUARD
#
# Prevents low-confidence, family-level, or structurally incomplete records
# from injecting specs into listings as if they were production-quality data.
#
# A record is BLOCKED from full spec injection if ANY condition is true:
#   1. series_record == True   — explicitly a family/series placeholder
#   2. spec_confidence == "LOW" — overall record confidence below threshold
#   3. All required core fields for the equipment type are null
#      — record is structurally too empty to inject meaningfully
#
# Blocked records: identity block is returned normally; spec fields are
# withheld and replaced with a human-readable advisory message.
# ---------------------------------------------------------------------------

SPEC_INJECTION_CORE_FIELDS: dict[str, list[str]] = {
    EQ_SKID_STEER:   ["horsepower_hp", "rated_operating_capacity_lbs"],
    EQ_CTL:          ["horsepower_hp", "rated_operating_capacity_lbs"],
    EQ_MINI_EX:      ["horsepower_hp", "max_dig_depth_ft"],
    # Extended equipment types (wheel loader, excavator, telehandler registries)
    "wheel_loader":  ["horsepower_hp", "operating_weight_lbs"],
    "excavator":     ["horsepower_hp", "operating_weight_lbs"],
    "telehandler":   ["max_lift_capacity_lbs", "lift_height_ft"],
    # Mini registry types
    EQ_BACKHOE:      ["horsepower_hp", "operating_weight_lbs"],
    EQ_DOZER:        ["horsepower_hp", "operating_weight_lbs"],
    EQ_SCISSOR_LIFT: ["platform_height_ft", "platform_capacity_lbs"],
    EQ_BOOM_LIFT:    ["platform_height_ft", "platform_capacity_lbs"],
}

# Human-readable messages surfaced when injection is blocked
_INJECTION_BLOCKED_MESSAGES = {
    "series_record":        "Model family identified — specs require serial decode before injection.",
    "low_spec_confidence":  "Partial machine match — full OEM spec injection withheld (confidence too low).",
    "missing_core_fields":  "Model family identified — specs need verification before injection.",
}


# ---------------------------------------------------------------------------
# TIERED CONFIDENCE SYSTEM  (v1.2)
#
# Three tiers gate spec output based on per-field confidence level.
# Fields are emitted to spec_sheet only when their confidence score meets
# the threshold assigned to their tier.
#
#   Tier 1 — Core Identity Specs      threshold ≥ 0.80   HIGH required
#   Tier 2 — Supplemental Specs       threshold ≥ 0.68   HIGH or MEDIUM ok
#   Tier 3 — Provisional/Variant      threshold ≥ 0.55   any above LOW ok
#
# Target output: ~10–12 specs per machine total across all three tiers.
# spec_sheet is the flat injection-ready list; tiered_specs gives the full
# structured breakdown with per-field confidence + behavior metadata.
# ---------------------------------------------------------------------------

CORE_THRESHOLD         = 0.80
SUPPLEMENTAL_THRESHOLD = 0.68
PROVISIONAL_THRESHOLD  = 0.55

_CONFIDENCE_SCORES: dict[str, float] = {
    "HIGH":   0.90,
    "MEDIUM": 0.72,
    "LOW":    0.40,
}

# Per-equipment-type tier definitions.
# Fields listed in tier order — emitted in this order in spec_sheet output.
SPEC_TIERS_BY_TYPE: dict[str, dict[str, list[str]]] = {
    EQ_SKID_STEER: {
        "core": [
            "horsepower_hp",
            "horsepower_gross_hp",        # fallback when net HP unavailable
            "rated_operating_capacity_lbs",
            "tipping_load_lbs",
            "operating_weight_lbs",
            "aux_flow_standard_gpm",
            "hydraulic_pressure_standard_psi",
            "fuel_capacity_gal",
        ],
        "supplemental": [
            "aux_flow_high_gpm",
            "hydraulic_pressure_high_psi",
            "travel_speed_high_mph",
            "lift_path",
            "frame_size",
        ],
        "provisional": [
            # Ordered from most to least sales-useful (matched by PROVISIONAL_PRIORITY_BY_TYPE)
            "two_speed_available",
            "high_flow_available",
            "hinge_pin_height_in",
            "breakout_force_lbf",
            "emissions_tier",
            "engine_model",
        ],
    },
    EQ_CTL: {
        "core": [
            "horsepower_hp",
            "horsepower_gross_hp",        # fallback when net HP unavailable
            "rated_operating_capacity_lbs",
            "tipping_load_lbs",
            "operating_weight_lbs",
            "aux_flow_standard_gpm",
            "hydraulic_pressure_standard_psi",
            "fuel_capacity_gal",
        ],
        "supplemental": [
            "aux_flow_high_gpm",
            "hydraulic_pressure_high_psi",
            "travel_speed_high_mph",
            "lift_path",
            "frame_size",
        ],
        "provisional": [
            "two_speed_available",
            "high_flow_available",
            "hinge_pin_height_in",
            "breakout_force_lbf",
            "emissions_tier",
            "engine_model",
        ],
    },
    EQ_MINI_EX: {
        "core": [
            "horsepower_hp",
            "horsepower_gross_hp",          # fallback when net HP unavailable
            "operating_weight_lbs",
            "max_dig_depth_ft",             # v2: feet (not inches)
            "bucket_breakout_force_lbs",    # v2: canonical bucket breakout
            "hydraulic_flow_gpm",
            "hydraulic_pressure_psi",
        ],
        "supplemental": [
            "arm_digging_force_lbs",        # v2: canonical arm digging force
            "fuel_capacity_gal",
            "travel_speed_high_mph",
            "aux_flow_primary_gpm",
        ],
        "provisional": [
            # Ordered from most to least sales-useful (matched by PROVISIONAL_PRIORITY_BY_TYPE)
            "tail_swing_type",
            "max_reach_ft",                 # v2: feet (not inches)
            "max_dump_height_ft",           # v2: feet (not inches)
            "cab_available",                # v2: new field
            "auxiliary_hydraulics",         # v2: new field
            "width_in",                     # v2: was overall_width_in
            "aux_flow_secondary_gpm",
            "stick_length_in",
            "track_type",
            "engine_model",
            "engine_make",                  # v2: was engine_manufacturer
            "height_overall_in",            # v2: net-new (was transport_height_in)
        ],
    },
    # Extended types — excavator, telehandler, wheel_loader registries
    # Field names use canonical display-layer names (see SOURCE_FIELD_MAP below).
    # Source registry variants (net_power_hp, operating_weight_lb, etc.) are
    # normalized to these names before _build_tiered_specs() runs.
    "excavator": {
        "core": [
            "horsepower_hp",
            "horsepower_gross_hp",          # fallback when net HP unavailable
            "operating_weight_lbs",
            "max_dig_depth_ft",             # full excavator: feet (not inches)
            "bucket_breakout_force_lbs",    # canonical for full excavator
            "hydraulic_flow_gpm",
            "hydraulic_pressure_psi",
        ],
        "supplemental": [
            "arm_digging_force_lbs",        # canonical for full excavator
            "bucket_capacity_yd3",
            "fuel_capacity_gal",
            "travel_speed_mph",             # excavator doesn't distinguish high/low
            "tail_swing_type",
        ],
        "provisional": [
            "max_reach_ft",
            "track_width_in",
            "ground_pressure_psi",
            "track_type",
            "engine_model",
        ],
    },
    "telehandler": {
        "core": [
            "max_lift_capacity_lbs",        # canonical (source: lift_capacity_lb)
            "lift_height_ft",               # canonical (source: max_lift_height_ft)
            "forward_reach_ft",             # canonical (source: max_forward_reach_ft)
            "operating_weight_lbs",         # canonical (source: operating_weight_lb)
        ],
        "supplemental": [
            # horsepower_hp moved from core: telehandler OEM specs often report gross
            # only (MEDIUM confidence), which passes SUPPLEMENTAL_THRESHOLD (0.68)
            # but not CORE_THRESHOLD (0.80). Source: engine_hp → canonical horsepower_hp.
            "horsepower_hp",
            "hydraulic_flow_gpm",
            "hydraulic_pressure_psi",
            "fuel_capacity_gal",
            "travel_speed_mph",
        ],
        "provisional": [
            "engine_model",
            "drive_type",
        ],
    },
    "wheel_loader": {
        # Core: only fields locked to HIGH confidence in the registry.
        # bucket_capacity_yd3 and tipping_load_straight_lb are MEDIUM confidence
        # (config-dependent) — they live in supplemental where the 0.68 threshold
        # passes MEDIUM (0.72). Source: net_power_hp → horsepower_hp,
        # operating_weight_lb → operating_weight_lbs, breakout_force_lbf → breakout_force_lbs,
        # bucket_capacity_cy → bucket_capacity_yd3 (via SOURCE_FIELD_MAP).
        "core": [
            "horsepower_hp",
            "operating_weight_lbs",
            "breakout_force_lbs",
        ],
        "supplemental": [
            "bucket_capacity_yd3",
            "tipping_load_straight_lb",
            "hydraulic_flow_gpm",
            "hydraulic_pressure_psi",
            "fuel_capacity_gal",
            "travel_speed_mph",
            "hinge_pin_height_ft",
        ],
        "provisional": [
            "engine_model",
            "transmission_type",
        ],
    },
    EQ_BACKHOE: {
        # Core: only HIGH-confidence fields — power, weight, dig depth, fuel
        # loader_bucket_capacity_yd3 and backhoe_bucket_force_lbf are MEDIUM
        # (config/stick dependent) — they live in supplemental where 0.68 threshold
        # passes MEDIUM (0.72).
        "core": [
            "horsepower_hp",
            "operating_weight_lbs",
            "max_dig_depth_ft",
            "fuel_capacity_gal",
        ],
        "supplemental": [
            "loader_bucket_capacity_yd3",
            "backhoe_bucket_force_lbf",
            "loader_breakout_force_lbf",
            "travel_speed_mph",
            "max_reach_ft",
            "hydraulic_flow_gpm",
        ],
        "provisional": [
            "loader_lift_height_ft",
            "engine_model",
            "emissions_tier",
        ],
    },
    EQ_DOZER: {
        # Core: only HIGH-confidence fields — power, weight, fuel
        # blade_capacity_yd3 and blade_width_ft are MEDIUM (config-dependent) —
        # they live in supplemental where 0.68 threshold passes MEDIUM (0.72).
        "core": [
            "horsepower_hp",
            "operating_weight_lbs",
            "fuel_capacity_gal",
        ],
        "supplemental": [
            "blade_capacity_yd3",
            "blade_width_ft",
            "travel_speed_high_mph",
            "travel_speed_low_mph",
            "ground_pressure_psi",
            "hydraulic_flow_gpm",
        ],
        "provisional": [
            "engine_model",
            "emissions_tier",
            "track_type",
        ],
    },
    EQ_SCISSOR_LIFT: {
        "core": [
            "platform_height_ft",
            "platform_capacity_lbs",
            "platform_length_ft",
            "platform_width_ft",
            "operating_weight_lbs",
            "power_source",
        ],
        "supplemental": [
            "stowed_height_in",
            "stowed_length_ft",
            "drive_speed_stowed_mph",
            "max_ground_slope_pct",
        ],
        "provisional": [
            "fuel_capacity_gal",
            "turning_radius_ft",
        ],
    },
    EQ_BOOM_LIFT: {
        "core": [
            "platform_height_ft",
            "platform_capacity_lbs",
            "horizontal_reach_ft",
            "operating_weight_lbs",
            "power_source",
            "boom_type",
        ],
        "supplemental": [
            "fuel_capacity_gal",
            "drive_speed_stowed_mph",
            "max_ground_slope_pct",
        ],
        "provisional": [
            "engine_model",
            "stowed_length_ft",
        ],
    },
}

# ---------------------------------------------------------------------------
# ENUM DISPLAY MAP  (v1.2)
#
# Maps raw registry string values for known categorical fields to clean,
# human-readable display strings suitable for listing injection.
#
# Fields not listed here fall back to the generic snake_case → Title Case
# normalizer in _format_value().  Boolean fields (True/False) use the
# special "true"/"false" string keys after str().lower() normalization.
# ---------------------------------------------------------------------------

_ENUM_DISPLAY: dict[str, dict] = {
    "tail_swing_type": {
        "zero_tail_swing":          "Zero Tail Swing",
        "minimal_tail_swing":       "Minimal Tail Swing",
        "reduced_tail_swing":       "Reduced Tail Swing",
        "compact_radius":           "Compact Radius (Zero Tail)",
        "standard_tail_swing":      "Standard Tail Swing",
        "conventional_tail_swing":  "Conventional Tail Swing",
    },
    "track_type": {
        "rubber":       "Rubber",
        "steel":        "Steel",
        "rubber_steel": "Rubber / Steel",
    },
    "lift_path": {
        "radial":             "Radial",
        "vertical":           "Vertical",
        "radial_to_vertical": "Radial-to-Vertical",
    },
    "frame_size": {
        "small":       "Small",
        "compact":     "Compact",
        "mid":         "Mid",
        "medium":      "Medium",
        "large":       "Large",
        "extra_large": "Extra Large",
    },
    "high_flow_available": {
        "true":  "Available",
        "false": "Not Available",
    },
    "two_speed_available": {
        "true":  "Available",
        "false": "Not Available",
    },
    "power_source": {
        "electric_ac":   "Electric (AC)",
        "electric_dc":   "Electric (DC/Battery)",
        "electric":      "Electric",
        "diesel":        "Diesel",
        "dual_fuel":     "Dual Fuel (Diesel/LP)",
        "propane":       "Propane",
        "gasoline":      "Gasoline",
        "hybrid":        "Hybrid",
    },
    "boom_type": {
        "telescopic":    "Telescopic (Straight)",
        "articulating":  "Articulating (Knuckle)",
    },
}


# Display labels for Tier 3 fields — advisory text shown alongside the value
_PROVISIONAL_LABELS: dict[str, str] = {
    "engine_model":        "Engine (varies by configuration)",
    "emissions_tier":      "Emissions tier (varies by year/region)",
    "track_type":          "Track type (varies by configuration)",
    "tail_swing_type":     "Tail swing (varies by configuration)",
    "drive_type":          "Drive type (varies by configuration)",
    "transmission_type":   "Transmission (varies by configuration)",
    "two_speed_available": "Two-speed (optional — varies by configuration)",
    "high_flow_available": "High flow (optional — varies by configuration)",
}

# Display names and units for every spec field used in tier maps.
# Canonical names come first. Source-name entries (marked [legacy]) are kept
# as fallback display metadata only — they are never reached for records that
# have passed through _normalize_spec_keys() in _build_result().
_FIELD_META: dict[str, dict] = {
    # ── Canonical power fields ─────────────────────────────────────────────
    "horsepower_hp":                   {"display": "Net HP",                    "unit": "hp"},
    "horsepower_gross_hp":             {"display": "Gross HP",                  "unit": "hp"},
    # ── Legacy source names [kept as fallback; normalized before use] ──────
    "net_power_hp":                    {"display": "Net HP",                    "unit": "hp"},   # [legacy] → horsepower_hp
    "engine_hp":                       {"display": "Engine HP",                 "unit": "hp"},   # [legacy] → horsepower_hp
    # ── Canonical weight / capacity ────────────────────────────────────────
    "rated_operating_capacity_lbs":    {"display": "Rated Operating Capacity",  "unit": "lbs"},
    "tipping_load_lbs":                {"display": "Tipping Load",              "unit": "lbs"},
    "operating_weight_lbs":            {"display": "Operating Weight",          "unit": "lbs"},
    "operating_weight_lb":             {"display": "Operating Weight",          "unit": "lbs"},  # [legacy] → operating_weight_lbs
    "aux_flow_standard_gpm":           {"display": "Aux Hydraulic Flow (Std)",  "unit": "gpm"},
    "aux_flow_high_gpm":               {"display": "Aux Hydraulic Flow (Hi)",   "unit": "gpm"},
    "hydraulic_pressure_standard_psi": {"display": "Hydraulic Pressure (Std)", "unit": "psi"},
    "hydraulic_pressure_high_psi":     {"display": "Hydraulic Pressure (Hi)",  "unit": "psi"},
    "hydraulic_flow_gpm":              {"display": "Hydraulic Flow",            "unit": "gpm"},
    "hydraulic_pressure_psi":          {"display": "Hydraulic Pressure",        "unit": "psi"},
    "fuel_capacity_gal":               {"display": "Fuel Capacity",             "unit": "gal"},
    "travel_speed_high_mph":           {"display": "Travel Speed (High)",       "unit": "mph"},
    "travel_speed_low_mph":            {"display": "Travel Speed (Low)",        "unit": "mph"},
    "travel_speed_mph":                {"display": "Travel Speed",              "unit": "mph"},
    "travel_speed_forward_mph":        {"display": "Travel Speed (Fwd)",        "unit": "mph"},
    "lift_path":                       {"display": "Lift Path",                 "unit": None},
    "frame_size":                      {"display": "Frame Size",                "unit": None},
    "engine_model":                    {"display": "Engine",                    "unit": None},
    "emissions_tier":                  {"display": "Emissions Tier",            "unit": None},
    "max_dig_depth_in":                {"display": "Max Dig Depth",             "unit": "in"},
    "bucket_dig_force_lbf":            {"display": "Bucket Dig Force",          "unit": "lbf"},
    "arm_dig_force_lbf":               {"display": "Arm Dig Force",             "unit": "lbf"},
    "aux_flow_primary_gpm":            {"display": "Aux Flow (Primary)",        "unit": "gpm"},
    "aux_pressure_primary_psi":        {"display": "Aux Pressure (Primary)",    "unit": "psi"},
    "track_type":                      {"display": "Track Type",                "unit": None},
    "tail_swing_type":                 {"display": "Tail Swing",                "unit": None},
    # ── Legacy telehandler source names [kept as fallback; normalized before use]
    "lift_capacity_lb":                {"display": "Lift Capacity",             "unit": "lbs"},  # [legacy] → max_lift_capacity_lbs
    "max_lift_height_ft":              {"display": "Max Lift Height",           "unit": "ft"},   # [legacy] → lift_height_ft
    "max_forward_reach_ft":            {"display": "Max Forward Reach",         "unit": "ft"},   # [legacy] → forward_reach_ft
    "bucket_capacity_cu_yd":           {"display": "Bucket Capacity",           "unit": "cu yd"},
    "breakout_force_lbf":              {"display": "Breakout Force",            "unit": "lbf"},  # [legacy] → breakout_force_lbs (wheel_loader); SSL/CTL use this name natively
    "drive_type":                      {"display": "Drive Type",                "unit": None},
    "transmission_type":               {"display": "Transmission",              "unit": None},
    "two_speed_available":             {"display": "Two-Speed",                 "unit": None},
    "high_flow_available":             {"display": "High Flow",                 "unit": None},
    "bucket_capacity_cy":              {"display": "Bucket Capacity",           "unit": "cy"},   # [legacy] → bucket_capacity_yd3
    "tipping_load_straight_lb":        {"display": "Tipping Load (Straight)",   "unit": "lbs"},
    "hinge_pin_height_ft":             {"display": "Hinge Pin Height",          "unit": "ft"},
    "hinge_pin_height_in":             {"display": "Hinge Pin Height",          "unit": "in"},
    "tail_swing_type":                 {"display": "Tail Swing",                "unit": None},
    "max_reach_ft":                    {"display": "Max Reach",                 "unit": "ft"},
    "stick_length_in":                 {"display": "Stick Length",              "unit": "in"},
    "aux_flow_secondary_gpm":          {"display": "Aux Flow (Secondary)",      "unit": "gpm"},
    "transport_height_in":             {"display": "Transport Height",          "unit": "in"},
    "transport_width_in":              {"display": "Transport Width",           "unit": "in"},
    # Backhoe loader fields
    "max_dig_depth_ft":                {"display": "Max Dig Depth",             "unit": "ft"},
    "loader_bucket_capacity_yd3":      {"display": "Loader Bucket Capacity",    "unit": "yd³"},
    "backhoe_bucket_force_lbf":        {"display": "Backhoe Bucket Force",      "unit": "lbf"},
    "loader_breakout_force_lbf":       {"display": "Loader Breakout Force",     "unit": "lbf"},
    "max_reach_ft":                    {"display": "Max Reach",                 "unit": "ft"},
    "loader_lift_height_ft":           {"display": "Loader Lift Height",        "unit": "ft"},
    # Dozer fields
    "blade_capacity_yd3":              {"display": "Blade Capacity",            "unit": "yd³"},
    "blade_width_ft":                  {"display": "Blade Width",               "unit": "ft"},
    "ground_pressure_psi":             {"display": "Ground Pressure",           "unit": "psi"},
    # Scissor / boom lift fields
    "platform_height_ft":              {"display": "Platform Height",           "unit": "ft"},
    "platform_capacity_lbs":           {"display": "Platform Capacity",         "unit": "lbs"},
    "platform_length_ft":              {"display": "Platform Length",           "unit": "ft"},
    "platform_width_ft":               {"display": "Platform Width",            "unit": "ft"},
    "power_source":                    {"display": "Power Source",              "unit": None},
    "stowed_height_in":                {"display": "Stowed Height",             "unit": "in"},
    "stowed_length_ft":                {"display": "Stowed Length",             "unit": "ft"},
    "drive_speed_stowed_mph":          {"display": "Drive Speed (Stowed)",      "unit": "mph"},
    "max_ground_slope_pct":            {"display": "Max Ground Slope",          "unit": "%"},
    "turning_radius_ft":               {"display": "Turning Radius",            "unit": "ft"},
    # Boom lift fields
    "horizontal_reach_ft":             {"display": "Horizontal Reach",          "unit": "ft"},
    "boom_type":                       {"display": "Boom Type",                 "unit": None},
    # Canonical display-layer fields — wheel loader / excavator / telehandler
    "max_lift_capacity_lbs":           {"display": "Max Lift Capacity",         "unit": "lbs"},
    "lift_height_ft":                  {"display": "Max Lift Height",           "unit": "ft"},
    "forward_reach_ft":                {"display": "Max Forward Reach",         "unit": "ft"},
    "breakout_force_lbs":              {"display": "Breakout Force",            "unit": "lbs"},
    "bucket_capacity_yd3":             {"display": "Bucket Capacity",           "unit": "yd³"},
    "arm_digging_force_lbs":           {"display": "Arm Digging Force",         "unit": "lbs"},
    "bucket_breakout_force_lbs":       {"display": "Bucket Breakout Force",     "unit": "lbs"},
}


# ---------------------------------------------------------------------------
# CANONICAL FIELD NAMING RULES
#
# These are the authoritative display-layer field names for ALL equipment
# types. SPEC_TIERS_BY_TYPE, SPEC_INJECTION_CORE_FIELDS, DISPLAY_ORDER_BY_TYPE,
# spec_display_profiles.json, and specResolver.js must all use these names.
# Source/registry variants are normalized by SOURCE_FIELD_MAP below.
#
#   horsepower_hp        — net HP (primary power field; always prefer net)
#   horsepower_gross_hp  — gross HP (secondary/technical tier only; never essential)
#   operating_weight_lbs — standard weight field (plural 'lbs' throughout)
#   bucket_capacity_yd3  — standard bucket capacity (all loader types; not 'cy')
#   travel_speed_mph     — standard travel speed for all types EXCEPT:
#                          SSL / CTL    → travel_speed_high_mph (they track high + low)
#                          mini_ex      → travel_speed_high_mph (same convention)
#                          dozer        → travel_speed_high_mph + travel_speed_low_mph
#
# ---------------------------------------------------------------------------
# CANONICAL FIELD NAME MAP
#
# Maps source/registry field names → canonical display-layer field names.
# Applied to every registry record in _build_result() before any downstream
# processing (spec injection guard, tiered specs, display order).
#
# Safe for all equipment types: SSL/CTL/mini_ex fields are absent from this
# map and pass through unchanged. The map only covers source variants used
# in wheel_loader, telehandler, and excavator registries.
#
# Priority rule — power fields:
#   net_power_hp   → horsepower_hp        (wheel_loader net HP; preferred)
#   gross_power_hp → horsepower_gross_hp  (wheel_loader gross HP fallback)
#   engine_hp      → horsepower_hp        (telehandler; OEM often omits net/gross
#                                          label — mapped to net as conservative canonical)
#
# If a record already carries the canonical key, the source variant is ignored
# (_normalize_spec_keys: canonical keys from the first pass take priority).
# ---------------------------------------------------------------------------

SOURCE_FIELD_MAP: dict[str, str] = {
    # Power — wheel_loader / telehandler source variants
    "net_power_hp":        "horsepower_hp",       # wheel_loader net HP
    "gross_power_hp":      "horsepower_gross_hp", # wheel_loader gross HP fallback
    "engine_hp":           "horsepower_hp",        # telehandler (treat as net; see note above)
    # Weight — no-'s' variant in telehandler / wheel_loader registries
    "operating_weight_lb": "operating_weight_lbs",
    # Telehandler geometry
    "lift_capacity_lb":    "max_lift_capacity_lbs",
    "max_lift_height_ft":  "lift_height_ft",
    "max_forward_reach_ft": "forward_reach_ft",
    # Volume / capacity
    "bucket_capacity_cy":  "bucket_capacity_yd3",
    # Force — lbf unit suffix in name → lbs canonical
    "breakout_force_lbf":  "breakout_force_lbs",
    # Mini excavator v1 → v2 pure renames (no unit change — safe to remap)
    "bucket_dig_force_lbf":   "bucket_breakout_force_lbs",  # mini-ex v1 legacy
    "arm_dig_force_lbf":      "arm_digging_force_lbs",      # mini-ex v1 legacy
    "engine_manufacturer":    "engine_make",                 # mini-ex v1 legacy
    "overall_width_in":       "width_in",                   # mini-ex v1 legacy
    # NOTE: max_dig_depth_in / max_dump_height_in / max_reach_ground_in intentionally
    # omitted — unit conversion (in→ft) must happen at migration time, not here.
}


def _normalize_spec_keys(specs: dict) -> dict:
    """
    Translate source registry field names → canonical display-layer names
    using SOURCE_FIELD_MAP.

    Two-pass strategy ensures canonical keys already present in the record
    are never overwritten by remapped source variants:
      Pass 1 — copy keys NOT in SOURCE_FIELD_MAP (already canonical or unknown)
      Pass 2 — remap SOURCE_FIELD_MAP keys, skipping if target already set

    Unknown keys pass through unchanged (no entry in SOURCE_FIELD_MAP).
    Safe for SSL/CTL/mini_ex: their field names are absent from SOURCE_FIELD_MAP.
    """
    if not specs:
        return specs
    result: dict = {}
    # Pass 1: fields that don't need remapping
    for k, v in specs.items():
        if k not in SOURCE_FIELD_MAP:
            result[k] = v
    # Pass 2: remap source variants, only if canonical target not already set
    for k, v in specs.items():
        if k in SOURCE_FIELD_MAP:
            out_key = SOURCE_FIELD_MAP[k]
            if out_key not in result:
                result[out_key] = v
    return result


def _format_value(field: str, value):
    """
    Normalize a raw registry value to a human-readable listing display string.

    Pipeline
    --------
    1. Pass-through for None and numeric types — no transformation.
    2. Boolean: convert to lowercase string key ("true"/"false") then look up
       in _ENUM_DISPLAY[field].
    3. String: exact lookup in _ENUM_DISPLAY[field].
    4. drive_type: extract the leading drive-mode token (4WD / 2WD / AWD / 4x4)
       and append "(Full-Time)" qualifier when the source string says so.
    5. Generic fallback: snake_case strings with no spaces → Title Case.
    """
    if value is None:
        return value

    # Boolean normalization — JSON true/false arrives as Python bool
    if isinstance(value, bool):
        key = "true" if value else "false"
        mapped = _ENUM_DISPLAY.get(field, {}).get(key)
        return mapped if mapped is not None else ("Yes" if value else "No")

    # Exact enum lookup for known categorical string fields
    if isinstance(value, str):
        mapped = _ENUM_DISPLAY.get(field, {}).get(value)
        if mapped is not None:
            return mapped

        # drive_type: shorten verbose OEM descriptions to a compact token
        if field == "drive_type":
            s = value.upper()
            for token in ("4WD", "2WD", "AWD", "4X4", "2X2"):
                if s.startswith(token) or (" " + token) in s:
                    if "FULL" in s and "TIME" in s:
                        return "%s (Full-Time)" % token
                    return token
            # Unrecognized — return as-is (not worth truncating unknown strings)
            return value

        # Generic: snake_case identifiers → Title Case (e.g. tier4_final → Tier4 Final)
        if "_" in value and " " not in value:
            return value.replace("_", " ").title()

    return value


# ---------------------------------------------------------------------------
# DISPLAY CAP + PROVISIONAL GATE
# ---------------------------------------------------------------------------

DISPLAY_CAP   = 12   # hard ceiling on spec_sheet length
PROVISIONAL_CAP = 2  # max Tier 3 fields ever shown
_PROVISIONAL_BASE_THRESHOLD = 10  # include provisional only when base (T1+T2) < this

# ---------------------------------------------------------------------------
# SELLING-SHEET DISPLAY ORDER
#
# Defines the canonical left-to-right / top-to-bottom order that spec_sheet
# entries are sorted into for each equipment type.  Output should read like
# a dealer spec sheet, not a database dump.
# Fields not present in this list are appended at the end (shouldn't occur
# for well-defined registries).
# ---------------------------------------------------------------------------

DISPLAY_ORDER_BY_TYPE: dict[str, list[str]] = {
    EQ_SKID_STEER: [
        # Tier 1 core — identity block
        "horsepower_hp",
        "horsepower_gross_hp",
        "rated_operating_capacity_lbs",
        "operating_weight_lbs",
        "tipping_load_lbs",
        # Tier 2 supplemental — capability block
        "aux_flow_standard_gpm",
        "aux_flow_high_gpm",
        "hydraulic_pressure_standard_psi",
        "hydraulic_pressure_high_psi",
        "travel_speed_high_mph",
        "travel_speed_mph",
        "fuel_capacity_gal",
        "lift_path",
        "frame_size",
        # Tier 3 provisional — best fillers first
        "two_speed_available",
        "high_flow_available",
        "hinge_pin_height_in",
        "breakout_force_lbf",
        "emissions_tier",
        "engine_model",
    ],
    EQ_CTL: [
        "horsepower_hp",
        "horsepower_gross_hp",
        "rated_operating_capacity_lbs",
        "operating_weight_lbs",
        "tipping_load_lbs",
        "aux_flow_standard_gpm",
        "aux_flow_high_gpm",
        "hydraulic_pressure_standard_psi",
        "hydraulic_pressure_high_psi",
        "travel_speed_high_mph",
        "travel_speed_mph",
        "fuel_capacity_gal",
        "lift_path",
        "frame_size",
        "two_speed_available",
        "high_flow_available",
        "hinge_pin_height_in",
        "breakout_force_lbf",
        "emissions_tier",
        "engine_model",
    ],
    EQ_MINI_EX: [
        # Tier 1 core — identity block
        "horsepower_hp",
        "horsepower_gross_hp",
        "operating_weight_lbs",
        "max_dig_depth_in",
        "bucket_dig_force_lbf",
        # Tier 2 supplemental
        "arm_dig_force_lbf",
        "hydraulic_flow_gpm",
        "hydraulic_pressure_psi",
        "travel_speed_high_mph",
        "travel_speed_mph",
        "fuel_capacity_gal",
        "aux_flow_primary_gpm",
        # Tier 3 provisional — best fillers first per user spec:
        # tail swing > reach > stick > aux secondary > transport dims > track > engine
        "tail_swing_type",
        "max_reach_ft",
        "stick_length_in",
        "aux_flow_secondary_gpm",
        "transport_height_in",
        "transport_width_in",
        "track_type",
        "engine_model",
    ],
    "excavator": [
        # Selling-sheet: power → weight → dig → breakout → arm force → volume → hydraulics → travel → fuel → tail swing → reach → ground
        "horsepower_hp",
        "horsepower_gross_hp",
        "operating_weight_lbs",
        "max_dig_depth_ft",
        "bucket_breakout_force_lbs",
        "arm_digging_force_lbs",
        "bucket_capacity_yd3",
        "hydraulic_flow_gpm",
        "hydraulic_pressure_psi",
        "travel_speed_mph",
        "fuel_capacity_gal",
        "tail_swing_type",
        "max_reach_ft",
        "track_width_in",
        "ground_pressure_psi",
        "track_type",
        "engine_model",
    ],
    "telehandler": [
        # Selling-sheet: capacity → height → reach → weight → power → hydraulics → travel → fuel
        "max_lift_capacity_lbs",
        "lift_height_ft",
        "forward_reach_ft",
        "operating_weight_lbs",
        "horsepower_hp",
        "hydraulic_flow_gpm",
        "hydraulic_pressure_psi",
        "travel_speed_mph",
        "fuel_capacity_gal",
        "engine_model",
        "drive_type",
    ],
    "wheel_loader": [
        # Selling-sheet order: power → weight → capacity → force → hydraulics → motion → fuel
        "horsepower_hp",
        "operating_weight_lbs",
        "bucket_capacity_yd3",
        "breakout_force_lbs",
        "tipping_load_straight_lb",
        "hydraulic_flow_gpm",
        "hydraulic_pressure_psi",
        "travel_speed_mph",
        "fuel_capacity_gal",
        "hinge_pin_height_ft",
        "engine_model",
        "transmission_type",
    ],
    EQ_BACKHOE: [
        # Selling-sheet: power → weight → dig depth → reach → loader → dig force → hydraulics → motion → fuel
        "horsepower_hp",
        "operating_weight_lbs",
        "max_dig_depth_ft",
        "max_reach_ft",
        "loader_bucket_capacity_yd3",
        "backhoe_bucket_force_lbf",
        "loader_breakout_force_lbf",
        "hydraulic_flow_gpm",
        "travel_speed_mph",
        "fuel_capacity_gal",
        "loader_lift_height_ft",
        "engine_model",
        "emissions_tier",
    ],
    EQ_DOZER: [
        # Selling-sheet: power → weight → blade → travel → fuel → ground pressure
        "horsepower_hp",
        "operating_weight_lbs",
        "blade_width_ft",
        "blade_capacity_yd3",
        "travel_speed_high_mph",
        "travel_speed_low_mph",
        "fuel_capacity_gal",
        "ground_pressure_psi",
        "hydraulic_flow_gpm",
        "engine_model",
        "emissions_tier",
        "track_type",
    ],
    EQ_SCISSOR_LIFT: [
        # Selling-sheet: height → capacity → platform dims → weight → power → stowed dims → slope
        "platform_height_ft",
        "platform_capacity_lbs",
        "platform_length_ft",
        "platform_width_ft",
        "operating_weight_lbs",
        "power_source",
        "stowed_height_in",
        "stowed_length_ft",
        "drive_speed_stowed_mph",
        "max_ground_slope_pct",
        "fuel_capacity_gal",
        "turning_radius_ft",
    ],
    EQ_BOOM_LIFT: [
        # Selling-sheet: height → reach → capacity → weight → boom type → power → motion → fuel
        "platform_height_ft",
        "horizontal_reach_ft",
        "platform_capacity_lbs",
        "operating_weight_lbs",
        "boom_type",
        "power_source",
        "drive_speed_stowed_mph",
        "max_ground_slope_pct",
        "fuel_capacity_gal",
        "stowed_length_ft",
        "engine_model",
    ],
}

# ---------------------------------------------------------------------------
# REDUNDANCY RULES
#
# Prevents duplicate-value or semantically-overlapping fields from both
# appearing in spec_sheet.  Two rule types:
#
#   {"drop": field, "if_equals": other_field}
#       Drop `field` when its value is identical to `other_field` — the
#       second entry would add no information.
#       Example: hydraulic_pressure_high_psi == hydraulic_pressure_standard_psi
#                → high-flow PSI is unchanged; no point showing it twice.
#
#   {"drop": field, "if_present": other_field}
#       Drop `field` whenever `other_field` is in the active output set —
#       the more-specific field makes the generic one redundant.
#       Example: travel_speed_mph is the generic field; if travel_speed_high_mph
#                is present it carries more meaning for the buyer.
# ---------------------------------------------------------------------------

REDUNDANCY_RULES_BY_TYPE: dict[str, list[dict]] = {
    EQ_SKID_STEER: [
        # Net HP is preferred; drop gross HP when net HP is present
        {"drop": "horsepower_gross_hp",          "if_present": "horsepower_hp"},
        # High-pressure PSI equals standard PSI on most non-HF configs — silent drop
        {"drop": "hydraulic_pressure_high_psi",  "if_equals":  "hydraulic_pressure_standard_psi"},
        # Generic travel speed is superseded by the more precise high-range speed
        {"drop": "travel_speed_mph",             "if_present": "travel_speed_high_mph"},
    ],
    EQ_CTL: [
        {"drop": "horsepower_gross_hp",          "if_present": "horsepower_hp"},
        {"drop": "hydraulic_pressure_high_psi",  "if_equals":  "hydraulic_pressure_standard_psi"},
        {"drop": "travel_speed_mph",             "if_present": "travel_speed_high_mph"},
    ],
    EQ_MINI_EX: [
        {"drop": "horsepower_gross_hp",          "if_present": "horsepower_hp"},
        # Many mini-ex aux circuits run at the same flow as main circuit
        {"drop": "aux_flow_primary_gpm",         "if_equals":  "hydraulic_flow_gpm"},
        {"drop": "travel_speed_mph",             "if_present": "travel_speed_high_mph"},
    ],
    "excavator": [
        {"drop": "horsepower_gross_hp",          "if_present": "horsepower_hp"},
        {"drop": "aux_flow_primary_gpm",         "if_equals":  "hydraulic_flow_gpm"},
        {"drop": "travel_speed_mph",             "if_present": "travel_speed_high_mph"},
    ],
    "telehandler": [
        # Telehandlers have a single stated travel speed — prefer the generic field
        {"drop": "travel_speed_high_mph",        "if_present": "travel_speed_mph"},
    ],
    "wheel_loader": [
        {"drop": "horsepower_gross_hp",          "if_present": "horsepower_hp"},
        # Wheel loaders report a single travel speed — drop high-range if generic is present
        {"drop": "travel_speed_high_mph",        "if_present": "travel_speed_mph"},
    ],
    EQ_BACKHOE: [
        # Backhoes report a single travel speed
        {"drop": "travel_speed_high_mph",        "if_present": "travel_speed_mph"},
    ],
    EQ_DOZER: [
        # Generic travel speed is superseded by directional speeds for dozers
        {"drop": "travel_speed_mph",             "if_present": "travel_speed_high_mph"},
    ],
    EQ_SCISSOR_LIFT: [],  # No redundancy issues in scissor lift spec set
    EQ_BOOM_LIFT: [],     # No redundancy issues in boom lift spec set
}


# ---------------------------------------------------------------------------
# PROVISIONAL PRIORITY RANKING  (v1.2)
#
# When Tier 3 provisional fields are needed to fill out a thin spec_sheet,
# this ranking determines WHICH fields are selected first.  All candidates
# still must pass the PROVISIONAL_THRESHOLD confidence gate — this ranking
# only controls selection order among those that do pass.
#
# Rule: the most useful buyer-facing specs come first.  Weak internal-
# reference fields (engine_model, emissions_tier) come last so they only
# appear if nothing better is available.
#
# Equipment types not listed here fall back to the order in which
# provisional_fields are declared in SPEC_TIERS_BY_TYPE.
# ---------------------------------------------------------------------------

PROVISIONAL_PRIORITY_BY_TYPE: dict[str, list[str]] = {
    EQ_SKID_STEER: [
        "two_speed_available",   # premium capability — high buyer interest
        "high_flow_available",   # premium hydraulic package
        "hinge_pin_height_in",   # useful reach/capacity comparison
        "breakout_force_lbf",    # capability metric, strong selling point
        "emissions_tier",        # compliance / year filter
        "engine_model",          # weakest — mainly internal reference
    ],
    EQ_CTL: [
        "two_speed_available",
        "high_flow_available",
        "hinge_pin_height_in",
        "breakout_force_lbf",
        "emissions_tier",
        "engine_model",
    ],
    EQ_MINI_EX: [
        "tail_swing_type",       # zero vs conventional — strongest differentiator
        "max_reach_ft",          # horizontal reach — direct buyer comparison spec
        "stick_length_in",       # affects dig envelope, useful for job matching
        "aux_flow_secondary_gpm", # secondary aux circuit — attachment capability
        "transport_height_in",   # practical — trailer/building clearance
        "transport_width_in",    # practical — doorway / gate clearance
        "track_type",            # rubber vs steel — relevant but secondary
        "engine_model",          # weakest — mainly internal reference
    ],
    "excavator": [
        "tail_swing_type",
        "max_reach_ft",
        "stick_length_in",
        "aux_flow_secondary_gpm",
        "transport_height_in",
        "transport_width_in",
        "track_type",
        "engine_model",
    ],
    "telehandler": [
        "drive_type",            # 2WD / 4WD — key differentiator for job site fit
        "engine_model",
    ],
    "wheel_loader": [
        "transmission_type",     # powershift etc — operational differentiator
        "engine_model",
    ],
    EQ_BACKHOE: [
        "loader_lift_height_ft", # practical — loader reach/dump height
        "engine_model",
        "emissions_tier",
    ],
    EQ_DOZER: [
        "track_type",            # rubber vs steel pads — relevant for surface type
        "engine_model",
        "emissions_tier",
    ],
    EQ_SCISSOR_LIFT: [
        "fuel_capacity_gal",     # only relevant for diesel RT models
        "turning_radius_ft",
    ],
    EQ_BOOM_LIFT: [
        "engine_model",
        "stowed_length_ft",
    ],
}


def _confidence_to_score(confidence_label: str) -> float:
    """Map a confidence label string (HIGH / MEDIUM / LOW) to its numeric score."""
    return _CONFIDENCE_SCORES.get((confidence_label or "").upper(), 0.0)


def _build_tiered_specs(record: dict) -> dict:
    """
    Build the tiered, capped, and redundancy-filtered spec output for a
    production-eligible record.

    Pipeline
    --------
    1. Collect candidates from each tier using per-tier confidence thresholds.
    2. Apply redundancy filter (same-value dedup + semantic dedup) so only
       fields that add distinct buyer-facing information survive.
    3. Gate Tier 3 provisional inclusion: only add provisional fields when
       Tier 1 + Tier 2 base count is below _PROVISIONAL_BASE_THRESHOLD (10).
    4. Enforce priority ordering: Tier 1 fills first; Tier 2 fills remaining
       slots; Tier 3 fills only if capacity remains after T1+T2, up to
       PROVISIONAL_CAP (2) fields.
    5. Hard-cap final output at DISPLAY_CAP (12).
    6. Sort surviving fields into DISPLAY_ORDER_BY_TYPE selling-sheet order.

    Tier thresholds:
      Core           ≥ CORE_THRESHOLD         (0.80) — HIGH only in practice
      Supplemental   ≥ SUPPLEMENTAL_THRESHOLD (0.68) — HIGH or MEDIUM
      Provisional    ≥ PROVISIONAL_THRESHOLD  (0.55) — any above LOW

    Returns
    -------
    dict with keys:
      tier1_core          — post-filter core entries included in final output
      tier2_supplemental  — post-filter supplemental entries in final output
      tier3_provisional   — post-filter provisional entries in final output
      spec_count          — total fields in spec_sheet
      spec_sheet          — flat selling-sheet-ordered list, listing-ready
    """
    specs      = record.get("specs") or {}
    field_conf = record.get("field_confidence") or {}
    field_beh  = record.get("field_behavior") or {}
    eq_type    = record.get("equipment_type") or record.get("_registry", "")

    tier_defs           = SPEC_TIERS_BY_TYPE.get(eq_type, {})
    core_fields         = tier_defs.get("core", [])
    supplemental_fields = tier_defs.get("supplemental", [])
    provisional_fields  = tier_defs.get("provisional", [])

    _TIER_THRESHOLDS = {
        "core":         CORE_THRESHOLD,
        "supplemental": SUPPLEMENTAL_THRESHOLD,
        "provisional":  PROVISIONAL_THRESHOLD,
    }

    def _make_entry(field: str, tier_label: str) -> Optional[dict]:
        """Build one spec entry; return None if value absent or confidence fails."""
        value = specs.get(field)
        if value is None:
            value = record.get(field)
        if value is None:
            return None
        conf_label = (field_conf.get(field) or "").upper()
        if _confidence_to_score(conf_label) < _TIER_THRESHOLDS[tier_label]:
            return None
        meta = _FIELD_META.get(field, {})
        entry: dict = {
            "field":      field,
            "display":    meta.get("display", field),
            "value":      _format_value(field, value),
            "unit":       meta.get("unit"),
            "confidence": conf_label or "UNKNOWN",
            "behavior":   field_beh.get(field),
        }
        if tier_label == "provisional":
            entry["label"] = _PROVISIONAL_LABELS.get(field, "Varies by configuration")
        return entry

    # ── Step 1: Collect all threshold-passing candidates ──────────────────
    tier1_all = [e for f in core_fields         if (e := _make_entry(f, "core"))]
    tier2_all = [e for f in supplemental_fields if (e := _make_entry(f, "supplemental"))]
    tier3_all = [e for f in provisional_fields  if (e := _make_entry(f, "provisional"))]

    # ── Step 1b: Sort Tier 3 by provisional priority ───────────────────────
    # Apply PROVISIONAL_PRIORITY_BY_TYPE so the best buyer-facing provisional
    # fields are chosen first when capping to PROVISIONAL_CAP (2).
    # Fields absent from the priority list sort to the end (index 999).
    _prio      = PROVISIONAL_PRIORITY_BY_TYPE.get(eq_type, [])
    _prio_idx  = {f: i for i, f in enumerate(_prio)}
    tier3_all.sort(key=lambda e: _prio_idx.get(e["field"], 999))

    # ── Step 2: Redundancy filter ─────────────────────────────────────────
    # Build a flat value-lookup across all passing candidates for cross-field
    # comparison.  Redundancy rules run against this combined picture so a
    # rule can reference a field in a different tier.
    all_vals: dict[str, object] = {e["field"]: e["value"] for e in tier1_all + tier2_all + tier3_all}
    all_present: set[str] = set(all_vals)

    dropped: set[str] = set()
    for rule in REDUNDANCY_RULES_BY_TYPE.get(eq_type, []):
        drop_f = rule["drop"]
        if drop_f not in all_present:
            continue
        if "if_equals" in rule:
            keep_f = rule["if_equals"]
            if keep_f in all_present and all_vals[drop_f] == all_vals[keep_f]:
                dropped.add(drop_f)
        elif "if_present" in rule:
            if rule["if_present"] in all_present:
                dropped.add(drop_f)

    tier1_clean = [e for e in tier1_all if e["field"] not in dropped]
    tier2_clean = [e for e in tier2_all if e["field"] not in dropped]
    tier3_clean = [e for e in tier3_all if e["field"] not in dropped][:PROVISIONAL_CAP]

    # ── Step 3: Provisional gate ──────────────────────────────────────────
    # Tier 3 fields are only included when Tier 1+2 base count is below the
    # _PROVISIONAL_BASE_THRESHOLD (10), i.e. they are genuinely needed to
    # bring the listing into the 10–12 spec target range.
    base_count = len(tier1_clean) + len(tier2_clean)
    if base_count >= _PROVISIONAL_BASE_THRESHOLD:
        tier3_selected: list[dict] = []
    else:
        slots = DISPLAY_CAP - base_count
        tier3_selected = tier3_clean[:min(PROVISIONAL_CAP, slots)]

    # ── Step 4: Priority fill + hard display cap ──────────────────────────
    candidates: list[dict] = []
    candidates.extend(tier1_clean)
    candidates.extend(tier2_clean[: DISPLAY_CAP - len(candidates)])
    candidates.extend(tier3_selected[: DISPLAY_CAP - len(candidates)])

    # ── Step 5: Sort into selling-sheet display order ─────────────────────
    order     = DISPLAY_ORDER_BY_TYPE.get(eq_type, [])
    order_idx = {f: i for i, f in enumerate(order)}
    candidates.sort(key=lambda e: order_idx.get(e["field"], 999))

    # ── Step 6: Build structured tier outputs (post-filter, for metadata) ─
    in_final = {e["field"] for e in candidates}
    tier1_out = [e for e in tier1_clean    if e["field"] in in_final]
    tier2_out = [e for e in tier2_clean    if e["field"] in in_final]
    tier3_out = [e for e in tier3_selected if e["field"] in in_final]

    # ── Step 7: Build flat spec_sheet ─────────────────────────────────────
    spec_sheet: list[dict] = []
    for entry in candidates:
        row: dict = {"display": entry["display"], "value": entry["value"], "unit": entry["unit"]}
        if "label" in entry:
            row["label"] = entry["label"]
        spec_sheet.append(row)

    return {
        "tier1_core":         tier1_out,
        "tier2_supplemental": tier2_out,
        "tier3_provisional":  tier3_out,
        "spec_count":         len(spec_sheet),
        "spec_sheet":         spec_sheet,
    }


def _spec_injection_eligible(record: dict) -> tuple[bool, str]:
    """
    Returns (eligible: bool, reason: str).
    reason is "ok" when eligible, or a short code when blocked.
    """
    # 1. Explicit series/family flag
    if record.get("series_record") is True:
        return False, "series_record"

    # 2. Overall spec_confidence too low
    spec_conf = (record.get("spec_confidence") or "").upper()
    if spec_conf == "LOW":
        return False, "low_spec_confidence"

    # 3. All required core fields are null for this equipment type
    specs   = record.get("specs", {})
    eq_type = record.get("equipment_type") or record.get("_registry", "")
    required = SPEC_INJECTION_CORE_FIELDS.get(eq_type, [])
    if required and all(specs.get(f) is None for f in required):
        return False, "missing_core_fields"

    return True, "ok"


# ---------------------------------------------------------------------------
# PRIMARY SPEC MAPPING
# Equipment-type-aware extraction of the two headline spec values.
# These are the fields the autofill layer surfaces first in the listing form.
# ---------------------------------------------------------------------------

def _primary_specs(specs: dict, equipment_type: str) -> tuple:
    """
    Return (primary_power_spec, primary_capacity_spec) for the given equipment type.

    Skid Steer / Compact Track Loader:
      primary_power_spec    → horsepower_hp  (net HP)
      primary_capacity_spec → rated_operating_capacity_lbs

    Mini Excavator:
      primary_power_spec    → horsepower_hp  (net HP)
      primary_capacity_spec → max_dig_depth_ft (v2 schema; decimal feet)
                              returned as None if spec is absent
    """
    power = specs.get("horsepower_hp")

    if equipment_type == EQ_MINI_EX:
        depth_ft = specs.get("max_dig_depth_ft")
        capacity = round(depth_ft, 1) if depth_ft is not None else None
    else:
        # skid_steer and compact_track_loader
        capacity = specs.get("rated_operating_capacity_lbs")

    return power, capacity


# ---------------------------------------------------------------------------
# RESULT BUILDER
# ---------------------------------------------------------------------------

def _build_result(record: dict, confidence: float, match_method: str) -> dict:
    """
    Build the standardized MTM lookup result dict.

    Output schema
    ─────────────
    Identity block (always present, canonical values):
      match, confidence, match_method
      manufacturer, model, model_slug, model_family
      equipment_type      ← canonical: skid_steer | compact_track_loader | mini_excavator
      years_supported     ← {start, end}
      status

    Spec injection guard:
      spec_injection         ← True when specs are safe to inject; False when withheld
      spec_injection_blocked_reason  ← present only when spec_injection=False
      spec_injection_message         ← human-readable advisory when spec_injection=False

    Primary spec block (only present when spec_injection=True):
      primary_power_spec      ← horsepower_hp for all types
      primary_capacity_spec   ← rated_operating_capacity_lbs (SSL/CTL)
                                 or max_dig_depth_ft (Mini Ex)

    Extended specs (only present when spec_injection=True):
      operating_weight_lbs
      hydraulics              ← {aux_flow_standard_gpm, aux_flow_high_gpm,
                                   hydraulic_pressure_standard_psi,
                                   hydraulic_pressure_high_psi}

    Full record:
      full_record  ← complete registry record including all specs,
                     field_confidence, field_behavior, source_refs
    """
    # Normalize source field names → canonical display-layer names before any
    # downstream processing (injection guard, tiered specs, display order).
    # No-op for SSL/CTL/mini_ex: their fields are absent from SOURCE_FIELD_MAP.
    if record.get("specs"):
        record = {**record, "specs": _normalize_spec_keys(record["specs"])}

    specs   = record.get("specs", {})
    years   = record.get("years_supported", {})
    eq_type = record.get("equipment_type") or record.get("_registry")

    # ── Spec injection guard ───────────────────────────────────────────────
    eligible, block_reason = _spec_injection_eligible(record)

    # ── Identity block (always returned) ──────────────────────────────────
    result = {
        "match":          True,
        "confidence":     round(confidence, 3),
        "match_method":   match_method,
        "manufacturer":   record.get("manufacturer"),
        "model":          record.get("model"),
        "model_slug":     record.get("model_slug"),
        "model_family":   record.get("model_family"),
        "equipment_type": eq_type,
        "years_supported": {
            "start": years.get("start"),
            "end":   years.get("end"),
        },
        "status":         record.get("status"),
        "spec_injection": eligible,
    }

    if not eligible:
        result["spec_injection_blocked_reason"] = block_reason
        result["spec_injection_message"] = _INJECTION_BLOCKED_MESSAGES.get(
            block_reason,
            "Partial machine match — full OEM spec injection withheld.",
        )
        result["full_record"] = record
        return result

    # ── Spec injection (only when guard passes) ────────────────────────────
    power, capacity = _primary_specs(specs, eq_type)

    # ── Tiered specs (v1.2) ───────────────────────────────────────────────
    tiered = _build_tiered_specs(record)

    result.update({
        # ── Primary specs (backward compat) ────────────────────────────────
        "primary_power_spec":    power,
        "primary_capacity_spec": capacity,
        # ── Extended specs (backward compat) ───────────────────────────────
        "operating_weight_lbs":  specs.get("operating_weight_lbs"),
        "hydraulics": {
            "aux_flow_standard_gpm":           specs.get("aux_flow_standard_gpm"),
            "aux_flow_high_gpm":               specs.get("aux_flow_high_gpm"),
            "hydraulic_pressure_standard_psi": specs.get("hydraulic_pressure_standard_psi"),
            "hydraulic_pressure_high_psi":     specs.get("hydraulic_pressure_high_psi"),
        },
        # ── Tiered spec output (v1.2) ───────────────────────────────────────
        # spec_sheet: flat ordered list ready for listing injection (~10–12 items)
        # tiered_specs: structured breakdown with per-field confidence + behavior
        "spec_sheet": tiered["spec_sheet"],
        "tiered_specs": {
            "tier1_core":         tiered["tier1_core"],
            "tier2_supplemental": tiered["tier2_supplemental"],
            "tier3_provisional":  tiered["tier3_provisional"],
            "spec_count":         tiered["spec_count"],
        },
        # ── Full record ────────────────────────────────────────────────────
        "full_record": record,
    })
    return result


# ---------------------------------------------------------------------------
# CORE LOOKUP FUNCTION
# ---------------------------------------------------------------------------

_REGISTRY_CACHE: Optional[list[dict]] = None

def _get_registry() -> list[dict]:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is None:
        _REGISTRY_CACHE = load_all_registries()
    return _REGISTRY_CACHE


def lookup_machine(
    manufacturer: str = "",
    model: str = "",
    query: str = "",
    equipment_type: str = "",
) -> dict:
    """
    Look up a machine in the MTM canonical registry.

    Parameters
    ----------
    manufacturer : str
        Manufacturer name. Accepts aliases: "CAT", "JD", "cat", "john deere", etc.
    model : str
        Model designation. Case-insensitive. Hyphens and spaces are normalized.
    query : str
        Free-form string e.g. "CAT 262D3", "bobcat s650", "john deere 320g".
        Automatically parsed when manufacturer/model are not given separately.
    equipment_type : str
        Optional filter. Accepts aliases: "ctl", "ssl", "skid_steer_loader", etc.
        Normalized to canonical value before filtering.

    Returns
    -------
    dict
        On success: matched record with identity, primary specs, hydraulics, full_record.
        On failure: {"match": False, "reason": str, ...}

    Ambiguity guard
    ---------------
    If 2+ candidates score within AMBIGUITY_BAND (0.03) of the top result, the lookup
    returns match=False with reason="ambiguous_model" and a ranked suggestions list.
    Pass equipment_type to resolve ambiguous shared model numbers (e.g. "332G" exists
    in both skid_steer and compact_track_loader registries).

    Examples
    --------
    >>> lookup_machine("Caterpillar", "262D3")
    >>> lookup_machine("CAT", "262d3")
    >>> lookup_machine(query="cat 262d3")
    >>> lookup_machine(query="262D3")                                  # model-only
    >>> lookup_machine("JD", "332G", equipment_type="compact_track_loader")
    >>> lookup_machine("CAT", "299D3", equipment_type="ctl")           # alias accepted
    """
    registry = _get_registry()

    # ── 1. Parse free-form query ──────────────────────────────────────────
    if query and not manufacturer and not model:
        manufacturer, model = _parse_query(query, registry)

    if not manufacturer and not model:
        return {"match": False, "reason": "No manufacturer or model provided."}

    # ── 1b. Model bridge — shorthand → canonical registry model ──────────
    # Deterministic alias map. Applied before scoring so the rest of the
    # lookup runs against the canonical model string unchanged.
    # Key is normalized (lowercase, spaces and hyphens stripped) so that
    # "svl 75", "svl-75", and "svl75" all hit the same bridge entry.
    if model:
        _bridge_key = re.sub(r"[\s\-]", "", model.lower())
        model = MODEL_BRIDGE_ALIASES.get(_bridge_key, model)

    # ── 2. Resolve manufacturer alias ────────────────────────────────────
    canonical_mfr = None
    if manufacturer:
        canonical_mfr = _resolve_manufacturer(manufacturer)
        if canonical_mfr is None:
            canonical_mfr = manufacturer.strip()   # pass through for fuzzy

    # ── 3. Resolve and apply equipment_type filter ────────────────────────
    canonical_eq = _resolve_eq_type(equipment_type) if equipment_type else None
    candidates   = registry

    if canonical_eq:
        candidates = [r for r in candidates if r.get("equipment_type") == canonical_eq]
        if not candidates:
            return {
                "match":  False,
                "reason": f"No records found for equipment_type '{canonical_eq}'.",
            }

    if canonical_mfr:
        mfr_exact = [
            r for r in candidates
            if _normalize_str(r.get("manufacturer", "")) == _normalize_str(canonical_mfr)
        ]
        if mfr_exact:
            candidates = mfr_exact
        # If no exact manufacturer match, keep all candidates and let model scoring decide

    # ── 4. Score each candidate on model ─────────────────────────────────
    if not model:
        if candidates:
            return _build_result(candidates[0], confidence=0.5, match_method="manufacturer_only")
        return {"match": False, "reason": f"No records found for manufacturer '{canonical_mfr}'."}

    scored = []
    for r in candidates:
        s = _model_score(model, r.get("model", ""), r.get("model_slug", ""))
        scored.append((s, r))

    if not scored:
        return {"match": False, "reason": "No candidates found after filtering."}

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_record = scored[0]

    # ── 4b. Suffix strip — Kubota MEX R-suffix variants ──────────────────
    # If the first scoring pass produces a fuzzy result, try stripping a
    # Kubota MEX emissions-tier suffix (R1/R2/R3/R1T/R2T/R3T) and re-score.
    # Only fires when the stripped model exists in the live registry; otherwise
    # falls through and the original fuzzy result continues to step 5.
    _first_method = (
        "exact" if _normalize_str(model) == _normalize_str(best_record.get("model", ""))
        else "slug_match" if best_score >= 0.95
        else "fuzzy"
    )
    if _first_method == "fuzzy" and canonical_mfr:
        _registry_models: set = {r.get("model", "") for r in candidates}
        _stripped = _strip_variant_suffix(canonical_mfr, model, _registry_models)
        if _stripped is not None:
            _scored2 = []
            for r in candidates:
                s = _model_score(_stripped, r.get("model", ""), r.get("model_slug", ""))
                _scored2.append((s, r))
            _scored2.sort(key=lambda x: x[0], reverse=True)
            _best2_score, _best2_record = _scored2[0]
            _best2_method = (
                "exact" if _normalize_str(_stripped) == _normalize_str(_best2_record.get("model", ""))
                else "slug_match" if _best2_score >= 0.95
                else "fuzzy"
            )
            if _best2_method in ("exact", "slug_match"):
                scored      = _scored2
                best_score  = _best2_score
                best_record = _best2_record

    # ── 5. Below-threshold: no confident match ───────────────────────────
    if best_score < FUZZY_THRESHOLD:
        suggestions = [
            f"{r.get('manufacturer')} {r.get('model')}"
            for s, r in scored[:3] if s > 0.4
        ]
        return {
            "match":       False,
            "reason":      f"No confident match for '{manufacturer} {model}'. Best score: {round(best_score, 2)}.",
            "suggestions": suggestions,
        }

    # ── 6. Ambiguity guard ────────────────────────────────────────────────
    near_top = [
        (s, r) for s, r in scored
        if s >= best_score - AMBIGUITY_BAND and s >= FUZZY_THRESHOLD
    ]
    if len(near_top) > 1:
        # ── 6a. Tiebreaker: prefer the slug that directly encodes the model ──
        # When all tied candidates share the same manufacturer + equipment_type,
        # attempt deterministic resolution before returning ambiguous_model.
        #
        # Pass 1 — slug-model affinity: prefer the record whose model_slug ends
        #   with "_" + normalized_model (e.g. "310sl" → prefer slug "jd_310sl"
        #   over "jd_310").  This handles demoted legacy stubs that share the
        #   same model string but have a less specific slug.
        # Pass 2 — spec_confidence: prefer HIGH over MEDIUM over LOW.
        #
        # Only fires when all tied candidates are same mfr + eq_type (i.e. we
        # are NOT resolving cross-type or cross-manufacturer ambiguity, which
        # must still require the caller to supply equipment_type).
        _conf_rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0, "": 0}
        _tied_mfrs = {_normalize_str(r.get("manufacturer", "")) for _, r in near_top}
        _tied_eqs  = {r.get("equipment_type", "") for _, r in near_top}
        if len(_tied_mfrs) == 1 and len(_tied_eqs) == 1:
            _norm_model = _normalize_str(model)
            def _slug_affinity(r: dict) -> int:
                slug = _normalize_str(r.get("model_slug", ""))
                return 1 if slug.endswith(_norm_model) else 0
            _resolved = sorted(
                near_top,
                key=lambda x: (
                    _slug_affinity(x[1]),
                    _conf_rank.get((x[1].get("spec_confidence") or "").upper(), 0),
                ),
                reverse=True,
            )
            if _slug_affinity(_resolved[0][1]) > _slug_affinity(_resolved[1][1]) or (
                _conf_rank.get((_resolved[0][1].get("spec_confidence") or "").upper(), 0)
                > _conf_rank.get((_resolved[1][1].get("spec_confidence") or "").upper(), 0)
            ):
                best_score, best_record = _resolved[0]
                near_top = [_resolved[0]]

    if len(near_top) > 1:
        suggestions = [
            {
                "manufacturer":   r.get("manufacturer"),
                "model":          r.get("model"),
                "equipment_type": r.get("equipment_type"),
                "confidence":     round(s, 3),
            }
            for s, r in near_top[:5]
        ]
        return {
            "match":       False,
            "reason":      "ambiguous_model",
            "description": (
                f"Multiple models scored within {AMBIGUITY_BAND} of each other for "
                f"input '{manufacturer} {model}'. "
                "Provide equipment_type to disambiguate."
            ),
            "suggestions": suggestions,
        }

    # ── 7. Match method label ────────────────────────────────────────────
    norm_input = _normalize_str(model)
    norm_best  = _normalize_str(best_record.get("model", ""))
    if norm_input == norm_best:
        method = "exact"
    elif best_score >= 0.95:
        method = "slug_match"
    else:
        method = "fuzzy"

    return _build_result(best_record, best_score, method)


# ---------------------------------------------------------------------------
# FREE-FORM QUERY PARSER
# ---------------------------------------------------------------------------

def _parse_query(query: str, registry: list) -> tuple:
    """
    Parse a free-form string into (manufacturer, model).
    Tries longest alias first to prevent short aliases shadowing longer ones.
    Falls back to ("", query) if no manufacturer is detected.
    """
    q = query.strip()
    sorted_aliases = sorted(MANUFACTURER_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        pattern = re.compile(r"(?i)^" + re.escape(alias) + r"[\s\-_]*(.*)$")
        m = pattern.match(q)
        if m:
            mfr   = MANUFACTURER_ALIASES[alias]
            model = m.group(1).strip()
            return mfr, model
    return "", q


# ---------------------------------------------------------------------------
# CONVENIENCE: SEARCH BY MODEL ONLY
# ---------------------------------------------------------------------------

def search_by_model(model: str, equipment_type: str = "") -> list[dict]:
    """
    Search for all records matching a model string, across all manufacturers.
    equipment_type accepts aliases ("ctl", "ssl", "skid_steer_loader", etc.).
    Returns up to 5 matches sorted by descending confidence.
    """
    registry     = _get_registry()
    canonical_eq = _resolve_eq_type(equipment_type) if equipment_type else None
    if canonical_eq:
        registry = [r for r in registry if r.get("equipment_type") == canonical_eq]

    scored = []
    for r in registry:
        s = _model_score(model, r.get("model", ""), r.get("model_slug", ""))
        if s >= FUZZY_THRESHOLD:
            scored.append((s, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_build_result(r, s, "model_only_search") for s, r in scored[:5]]


# ---------------------------------------------------------------------------
# CONVENIENCE: LIST ALL MODELS
# ---------------------------------------------------------------------------

def list_models(manufacturer: str = "", equipment_type: str = "") -> list[dict]:
    """
    Return a summary list of all models, optionally filtered.
    Both arguments accept aliases.
    """
    registry      = _get_registry()
    canonical_eq  = _resolve_eq_type(equipment_type) if equipment_type else None
    canonical_mfr = (_resolve_manufacturer(manufacturer) or manufacturer) if manufacturer else None

    results = []
    for r in registry:
        if canonical_mfr:
            if _normalize_str(r.get("manufacturer", "")) != _normalize_str(canonical_mfr):
                continue
        if canonical_eq:
            if r.get("equipment_type") != canonical_eq:
                continue
        results.append({
            "manufacturer":   r.get("manufacturer"),
            "model":          r.get("model"),
            "model_slug":     r.get("model_slug"),
            "equipment_type": r.get("equipment_type"),
            "status":         r.get("status"),
        })
    return results


# ---------------------------------------------------------------------------
# REGISTRY STATS
# ---------------------------------------------------------------------------

def registry_stats() -> dict:
    """Return a summary of the loaded registry."""
    from collections import Counter
    registry = _get_registry()
    by_type  = Counter(r.get("equipment_type") for r in registry)
    by_mfr   = Counter(r.get("manufacturer")   for r in registry)
    return {
        "total_records":     len(registry),
        "by_equipment_type": dict(sorted(by_type.items())),
        "by_manufacturer":   dict(sorted(by_mfr.items())),
    }
