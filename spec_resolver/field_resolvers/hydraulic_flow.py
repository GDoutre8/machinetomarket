"""
field_resolvers/hydraulic_flow.py
Resolves hydraulic_flow_gpm (standard flow) and hi_flow_gpm.

This is the most option-sensitive field:
  - If "high_flow" detected → return hi_flow value in hydraulic_flow_gpm
    and set ui_hint _displayHiFlow = True
  - If "high_flow" NOT detected → return std_flow value
  - If the machine has no hi-flow option at all → always return std_flow
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

from ..types import FieldBehavior, FieldSource, MatchType
from ..confidence_policy import evaluate_injection, InjectionDecision
from ..field_rules import get_field_behavior
from ..unit_normalizer import lpm_to_gpm
from ._base import ResolutionContext, FieldResolution, build_resolution


def resolve(ctx: ResolutionContext) -> Optional[Dict[str, FieldResolution]]:
    """
    Returns a dict with up to two FieldResolution objects:
      "hydraulic_flow_gpm" — the primary (active) flow rate
      "hi_flow_gpm"        — hi-flow capacity (if the machine has it)

    Also returns a ui_hint via trace.notes:
      "_displayHiFlow: true" when high flow is active.
    """
    if not ctx.can_attempt:
        return None

    entry   = ctx.registry_entry
    options = ctx.detected_options
    results: Dict[str, FieldResolution] = {}

    # ── Pull registry values ──────────────────────────────────────────────
    std_flow = _get_flow(entry.specs, "hydraulic_flow_gpm", "hydraulic_flow_lpm")
    hi_flow  = _get_flow(entry.specs, "hi_flow_gpm", "hi_flow_lpm")

    # Option overrides
    for opt_key, overrides in (entry.option_overrides or {}).items():
        if options.has(opt_key):
            if "hydraulic_flow_gpm" in overrides:
                std_flow = overrides["hydraulic_flow_gpm"]
            if "hi_flow_gpm" in overrides:
                hi_flow = overrides["hi_flow_gpm"]

    high_flow_detected = options.has("high_flow")

    # Family ranges
    std_range = entry.family_ranges.get("hydraulic_flow_gpm") if ctx.is_family else None
    hi_range  = entry.family_ranges.get("hi_flow_gpm") if ctx.is_family else None

    # ── Resolve primary flow field ────────────────────────────────────────
    behavior_std = get_field_behavior(
        "hydraulic_flow_gpm", ctx.parsed_category, entry.field_behaviors
    )

    if high_flow_detected and hi_flow is not None:
        # High flow option detected and available → use hi_flow value as primary
        if ctx.is_exact:
            value_std  = hi_flow
            source_std = FieldSource.REGISTRY_EXACT
        else:
            value_std  = hi_range or hi_flow
            source_std = FieldSource.REGISTRY_FAMILY
        applied = ["high_flow"]
        notes_std = ["High-flow option detected — hi-flow rate used as primary."]
        # Option is confirmed → no require_confirm needed for this field
        is_pkg_unresolved = False
    elif high_flow_detected and hi_flow is None:
        # Seller says high flow but registry has no hi-flow spec
        value_std  = std_flow if ctx.is_exact else (std_range or std_flow)
        source_std = FieldSource.REGISTRY_EXACT if ctx.is_exact else FieldSource.REGISTRY_FAMILY
        applied    = []
        notes_std  = [
            "WARNING: high_flow option detected but registry has no hi_flow_gpm. "
            "Std flow returned — verify."
        ]
        is_pkg_unresolved = True
    else:
        # No high-flow option detected — use std flow but mark require_confirm
        # because we cannot confirm which hydraulic config this machine has
        value_std  = std_flow if ctx.is_exact else (std_range or std_flow)
        source_std = FieldSource.REGISTRY_EXACT if ctx.is_exact else FieldSource.REGISTRY_FAMILY
        applied    = []
        notes_std  = []
        # Mark unresolved so caller knows the option was not confirmed
        is_pkg_unresolved = True

    decision_std = evaluate_injection(
        field_name="hydraulic_flow_gpm",
        behavior=behavior_std,
        match_type=ctx.match_type,
        registry_confidence=ctx.registry_confidence,
        # is_package_dependent=True blocks injection; we want injection but with
        # require_confirm when the option is unresolved.  Pass False here and
        # handle require_confirm via a custom decision below.
        is_package_dependent=False,
    )
    # If package option was not confirmed, override to require_confirm=True
    # while still injecting the std value (yellow cell, not blocked).
    if is_pkg_unresolved and decision_std.should_inject:
        from ..confidence_policy import InjectionDecision as _ID
        decision_std = _ID(
            should_inject=True,
            require_confirm=True,
            reason=(
                decision_std.reason
                + " Package-dependent: hydraulic config not confirmed — requires confirmation."
            ),
        )
    if value_std is None:
        from ..confidence_policy import InjectionDecision as _ID
        decision_std = _ID(
            should_inject=False, require_confirm=True,
            reason="Unresolved — no hydraulic_flow_gpm in registry.",
        )

    if high_flow_detected and hi_flow is not None:
        notes_std.append("_displayHiFlow: true")

    results["hydraulic_flow_gpm"] = build_resolution(
        ctx=ResolutionContext(
            field_name="hydraulic_flow_gpm",
            match_type=ctx.match_type,
            registry_entry=ctx.registry_entry,
            registry_confidence=ctx.registry_confidence,
            detected_options=ctx.detected_options,
            numeric_claims=ctx.numeric_claims,
            parsed_year=ctx.parsed_year,
            parsed_category=ctx.parsed_category,
        ),
        value=value_std,
        source=source_std,
        behavior=behavior_std,
        decision=decision_std,
        options_applied=applied,
        notes=notes_std,
    )

    # ── Resolve hi_flow_gpm (informational) ───────────────────────────────
    if hi_flow is not None:
        behavior_hi = get_field_behavior(
            "hi_flow_gpm", ctx.parsed_category, entry.field_behaviors
        )
        value_hi = hi_flow if ctx.is_exact else (hi_range or hi_flow)
        source_hi = FieldSource.REGISTRY_EXACT if ctx.is_exact else FieldSource.REGISTRY_FAMILY
        decision_hi = evaluate_injection(
            field_name="hi_flow_gpm",
            behavior=behavior_hi,
            match_type=ctx.match_type,
            registry_confidence=ctx.registry_confidence,
        )
        results["hi_flow_gpm"] = build_resolution(
            ctx=ResolutionContext(
                field_name="hi_flow_gpm",
                match_type=ctx.match_type,
                registry_entry=ctx.registry_entry,
                registry_confidence=ctx.registry_confidence,
                detected_options=ctx.detected_options,
                numeric_claims=ctx.numeric_claims,
                parsed_year=ctx.parsed_year,
                parsed_category=ctx.parsed_category,
            ),
            value=value_hi,
            source=source_hi,
            behavior=behavior_hi,
            decision=decision_hi,
            notes=["Hi-flow capacity spec (informational)."],
        )

    return results


def _get_flow(
    specs: dict,
    gpm_key: str,
    lpm_key: str,
) -> Optional[float]:
    """Pull gpm from registry, converting from lpm if needed."""
    val = specs.get(gpm_key)
    if val is not None:
        return float(val)
    lpm_val = specs.get(lpm_key)
    if lpm_val is not None:
        return lpm_to_gpm(float(lpm_val))
    return None
