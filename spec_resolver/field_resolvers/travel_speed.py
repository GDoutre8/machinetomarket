"""
field_resolvers/travel_speed.py
Resolves travel_speed_mph (and optionally travel_speed_high_mph / travel_speed_low_mph).

Some categories have only a single travel speed (CTL, WL, TH).
Excavators and backhoes have high + low.
The resolver checks what the registry provides and returns accordingly.
"""

from __future__ import annotations
from typing import Dict, Optional

from ..types import FieldSource
from ..confidence_policy import evaluate_injection, InjectionDecision
from ..field_rules import get_field_behavior
from ..unit_normalizer import kph_to_mph
from ._base import ResolutionContext, FieldResolution, build_resolution


def resolve(ctx: ResolutionContext) -> Optional[Dict[str, FieldResolution]]:
    """
    Returns a dict of field_name → FieldResolution.
    Keys present depend on what the registry provides:
      "travel_speed_mph"       — single speed (CTL, WL, etc.)
      "travel_speed_high_mph"  — high range (excavators, backhoes)
      "travel_speed_low_mph"   — low range  (excavators, backhoes)
    """
    if not ctx.can_attempt:
        return None

    entry   = ctx.registry_entry
    results: Dict[str, FieldResolution] = {}

    def _resolve_single(field: str) -> Optional[FieldResolution]:
        behavior = get_field_behavior(field, ctx.parsed_category, entry.field_behaviors)
        raw      = entry.specs.get(field)
        # Convert kph if needed
        if raw is None:
            kph_key = field.replace("_mph", "_kph")
            kph_val = entry.specs.get(kph_key)
            if kph_val is not None:
                raw = kph_to_mph(float(kph_val))

        family_range = entry.family_ranges.get(field) if ctx.is_family else None

        if ctx.is_exact and raw is not None:
            value, source = raw, FieldSource.REGISTRY_EXACT
        elif ctx.is_family and family_range:
            value, source = family_range, FieldSource.REGISTRY_FAMILY
        elif ctx.is_family and raw is not None:
            value, source = raw, FieldSource.REGISTRY_FAMILY
        else:
            value, source = None, FieldSource.UNRESOLVED

        decision = evaluate_injection(
            field_name=field,
            behavior=behavior,
            match_type=ctx.match_type,
            registry_confidence=ctx.registry_confidence,
        )
        if value is None:
            decision = InjectionDecision(
                should_inject=False, require_confirm=True,
                reason=f"Unresolved — no {field} in registry.",
            )
        return build_resolution(
            ctx=ResolutionContext(
                field_name=field,
                match_type=ctx.match_type,
                registry_entry=ctx.registry_entry,
                registry_confidence=ctx.registry_confidence,
                detected_options=ctx.detected_options,
                numeric_claims=ctx.numeric_claims,
                parsed_year=ctx.parsed_year,
                parsed_category=ctx.parsed_category,
            ),
            value=value, source=source,
            behavior=behavior, decision=decision,
            registry_value=entry.specs.get(field),
        )

    # Determine which speed fields this category uses
    has_single = "travel_speed_mph" in entry.specs
    has_high   = "travel_speed_high_mph" in entry.specs
    has_low    = "travel_speed_low_mph" in entry.specs

    if has_single:
        res = _resolve_single("travel_speed_mph")
        if res:
            results["travel_speed_mph"] = res

    if has_high:
        res = _resolve_single("travel_speed_high_mph")
        if res:
            results["travel_speed_high_mph"] = res

    if has_low:
        res = _resolve_single("travel_speed_low_mph")
        if res:
            results["travel_speed_low_mph"] = res

    # Fallback: try travel_speed_mph if nothing matched
    if not results:
        res = _resolve_single("travel_speed_mph")
        if res:
            results["travel_speed_mph"] = res

    return results or None
