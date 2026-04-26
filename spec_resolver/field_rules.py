"""
field_rules.py
Per-field behavior definitions, precedence rules, and default behaviors.

This is the single source of truth for how each spec field behaves.
Field behaviors can be overridden per-registry-entry in the registry JSON.
"""

from __future__ import annotations
from typing import Dict, Optional
from types import MappingProxyType

from .types import FieldBehavior


# ---------------------------------------------------------------------------
# Default field behaviors by category
# These are the DEFAULTS. Registry entries may override per field.
# ---------------------------------------------------------------------------

_CTL_SSL_DEFAULTS: Dict[str, FieldBehavior] = {
    "net_hp":                      FieldBehavior.LOCKED,
    "operating_weight_lb":         FieldBehavior.LOCKED,
    "roc_lb":                      FieldBehavior.LOCKED,
    "tipping_load_lb":             FieldBehavior.LOCKED,
    "hydraulic_flow_gpm":          FieldBehavior.PACKAGE_DEPENDENT,  # std vs hi-flow
    "hi_flow_gpm":                 FieldBehavior.PACKAGE_DEPENDENT,
    "travel_speed_mph":            FieldBehavior.LOCKED,
    "travel_speed_high_mph":       FieldBehavior.LOCKED,
    "width_over_tires_in":         FieldBehavior.LOCKED,  # fixed OEM dimension
    "bucket_hinge_pin_height_in":  FieldBehavior.LOCKED,  # fixed OEM dimension
    "fuel_type":                   FieldBehavior.LOCKED,
    "lift_path":                   FieldBehavior.LOCKED,
    "track_width_in":              FieldBehavior.PACKAGE_DEPENDENT,  # varies by variant
}

_MINI_EX_DEFAULTS: Dict[str, FieldBehavior] = {
    "net_hp":               FieldBehavior.LOCKED,
    "operating_weight_lb":  FieldBehavior.LOCKED,
    "max_dig_depth":        FieldBehavior.LOCKED,
    "bucket_breakout_lb":   FieldBehavior.LOCKED,
    "tail_swing_type":      FieldBehavior.LOCKED,
    "travel_speed_high_mph":FieldBehavior.LOCKED,
    "travel_speed_low_mph": FieldBehavior.LOCKED,
    "fuel_type":            FieldBehavior.LOCKED,
}

_FULL_EX_DEFAULTS: Dict[str, FieldBehavior] = {
    "net_hp":               FieldBehavior.LOCKED,
    "operating_weight_lb":  FieldBehavior.RANGE,    # varies by configuration
    "max_dig_depth":        FieldBehavior.LOCKED,
    "bucket_breakout_lb":   FieldBehavior.LOCKED,
    "tail_swing_type":      FieldBehavior.LOCKED,
    "travel_speed_high_mph":FieldBehavior.LOCKED,
    "travel_speed_low_mph": FieldBehavior.LOCKED,
    "fuel_type":            FieldBehavior.LOCKED,
}

_WHEEL_LOADER_DEFAULTS: Dict[str, FieldBehavior] = {
    "net_hp":               FieldBehavior.LOCKED,
    "operating_weight_lb":  FieldBehavior.LOCKED,
    "bucket_capacity_yd3":  FieldBehavior.PACKAGE_DEPENDENT,
    "breakout_force_lb":    FieldBehavior.LOCKED,
    "hinge_pin_height_ft":  FieldBehavior.LOCKED,
    "travel_speed_mph":     FieldBehavior.LOCKED,
    "fuel_type":            FieldBehavior.LOCKED,
}

_TELEHANDLER_DEFAULTS: Dict[str, FieldBehavior] = {
    "max_lift_height_ft":   FieldBehavior.LOCKED,
    "max_lift_capacity_lb": FieldBehavior.LOCKED,
    "max_fwd_reach_ft":     FieldBehavior.LOCKED,
    "operating_weight_lb":  FieldBehavior.LOCKED,
    "travel_speed_mph":     FieldBehavior.LOCKED,
    "fuel_type":            FieldBehavior.LOCKED,
}

_BOOM_LIFT_DEFAULTS: Dict[str, FieldBehavior] = {
    "platform_height_ft":   FieldBehavior.LOCKED,
    "working_height_ft":    FieldBehavior.LOCKED,
    "horizontal_reach_ft":  FieldBehavior.LOCKED,
    "platform_capacity_lb": FieldBehavior.LOCKED,
    "power_type":           FieldBehavior.LOCKED,
    "four_wd":              FieldBehavior.LOCKED,
}

_SCISSOR_LIFT_DEFAULTS: Dict[str, FieldBehavior] = {
    "platform_height_ft":     FieldBehavior.LOCKED,
    "platform_capacity_lbs":  FieldBehavior.LOCKED,   # registry uses 'lbs'
    "platform_length_ft":     FieldBehavior.LOCKED,
    "platform_width_ft":      FieldBehavior.LOCKED,
    "operating_weight_lb":    FieldBehavior.LOCKED,   # canonical key after _SPEC_KEY_MAP
    "power_source":           FieldBehavior.LOCKED,   # registry uses 'power_source'
    "stowed_height_in":       FieldBehavior.LOCKED,
    "drive_speed_stowed_mph": FieldBehavior.LOCKED,   # registry marks manual_review; LOCKED
                                                       # causes suppression to drop that
                                                       # override so passthrough injects it
}

_DOZER_DEFAULTS: Dict[str, FieldBehavior] = {
    "net_hp":                   FieldBehavior.LOCKED,
    "operating_weight_lb":      FieldBehavior.RANGE,           # varies LGP vs std
    "blade_width_in":           FieldBehavior.PACKAGE_DEPENDENT,
    "blade_width_ft":           FieldBehavior.PACKAGE_DEPENDENT,
    "blade_capacity_yd3":       FieldBehavior.PACKAGE_DEPENDENT,
    "travel_speed_fwd_mph":     FieldBehavior.LOCKED,
    "travel_speed_high_mph":    FieldBehavior.LOCKED,
    "travel_speed_low_mph":     FieldBehavior.LOCKED,
    "fuel_capacity_gal":        FieldBehavior.LOCKED,
    "fuel_type":                FieldBehavior.LOCKED,
    "ground_pressure_psi":      FieldBehavior.PACKAGE_DEPENDENT,
    "hydraulic_flow_gpm":       FieldBehavior.PACKAGE_DEPENDENT,
}

_BACKHOE_DEFAULTS: Dict[str, FieldBehavior] = {
    "net_hp":               FieldBehavior.LOCKED,
    "operating_weight_lb":  FieldBehavior.RANGE,    # varies 2wd vs 4wd
    "max_dig_depth":        FieldBehavior.PACKAGE_DEPENDENT,  # std vs extendahoe
    "loader_bucket_capacity_yd3": FieldBehavior.LOCKED,
    "bucket_breakout_lb":         FieldBehavior.LOCKED,   # canonical key used by breakout_force.resolve
    "loader_breakout_force_lb":   FieldBehavior.LOCKED,   # front loader breakout force
    "travel_speed_mph":     FieldBehavior.LOCKED,
    "fuel_type":            FieldBehavior.LOCKED,
}


# ---------------------------------------------------------------------------
# Category → default behavior map
# ---------------------------------------------------------------------------

CATEGORY_DEFAULTS: Dict[str, Dict[str, FieldBehavior]] = MappingProxyType({
    "CTL":  _CTL_SSL_DEFAULTS,
    "SSL":  _CTL_SSL_DEFAULTS,
    "MINI": _MINI_EX_DEFAULTS,
    "EX":   _FULL_EX_DEFAULTS,
    "WL":   _WHEEL_LOADER_DEFAULTS,
    "TH":   _TELEHANDLER_DEFAULTS,
    "BOOM": _BOOM_LIFT_DEFAULTS,
    "SCIS": _SCISSOR_LIFT_DEFAULTS,
    "DOZ":  _DOZER_DEFAULTS,
    "BH":   _BACKHOE_DEFAULTS,
})


# ---------------------------------------------------------------------------
# Field precedence (applies to every field regardless of category)
# ---------------------------------------------------------------------------
# 1. Exact registry locked value
# 2. Option-dependent registry override (e.g. high_flow detected)
# 3. Family-level range
# 4. Seller numeric claim  ← only surfaced/flagged, NEVER silent override
# 5. Unresolved / omit


class FieldPrecedence:
    """
    Enum-style class documenting precedence levels.
    Used in audit trail resolution_reason strings.
    """
    EXACT_REGISTRY       = "Exact model locked spec"
    OPTION_OVERRIDE      = "Option-dependent registry override"
    FAMILY_RANGE         = "Family range used"
    SELLER_CLAIM         = "Seller claim (verify — not auto-applied)"
    UNRESOLVED           = "Unresolved — insufficient confidence"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_field_behavior(
    field_name: str,
    category: str,
    registry_overrides: Optional[Dict[str, FieldBehavior]] = None,
) -> FieldBehavior:
    """
    Return the effective FieldBehavior for field_name in category,
    applying any per-registry overrides.
    Falls back to MANUAL_REVIEW if field is not defined for the category.
    """
    # Registry-level override has highest priority
    if registry_overrides and field_name in registry_overrides:
        return registry_overrides[field_name]

    # Category default
    defaults = CATEGORY_DEFAULTS.get(category.upper(), {})
    return defaults.get(field_name, FieldBehavior.MANUAL_REVIEW)


def should_require_confirm(
    field_name: str,
    behavior: FieldBehavior,
    source: str,
    match_type: str,
) -> bool:
    """
    Return True if this field should be added to requires_confirm[].

    Typical cases:
      - family-level match (match_type == "family") for non-trivial specs
      - PACKAGE_DEPENDENT behavior without a resolved option
      - RANGE behavior
      - MANUAL_REVIEW
    """
    if behavior == FieldBehavior.MANUAL_REVIEW:
        return True
    if behavior == FieldBehavior.RANGE:
        return True
    if behavior == FieldBehavior.PACKAGE_DEPENDENT and source != "registry_exact":
        return True
    if match_type == "family" and behavior == FieldBehavior.LOCKED:
        # Even locked fields are require-confirm when we only have family match
        return True
    return False
