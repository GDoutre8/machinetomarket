"""
field_resolvers/dig_depth.py
Resolves max_dig_depth (string: "X ft Y in").

Special cases:
  - Backhoe: extendahoe option → use extendahoe_dig_depth from registry
  - No extendahoe: use std_dig_depth
"""

from __future__ import annotations
from typing import Optional

from ..types import FieldSource
from ..confidence_policy import evaluate_injection, InjectionDecision
from ..field_rules import get_field_behavior
from ..unit_normalizer import normalize_dig_depth, decimal_ft_to_ft_in
from ._base import ResolutionContext, FieldResolution, build_resolution

FIELD = "max_dig_depth"
# v2 mini-ex registry stores dig depth as decimal feet under this key.
# normalize_dig_depth() cannot handle decimal feet (heuristic treats ≤30 as metres).
_FIELD_V2_FT = "max_dig_depth_ft"


def resolve(ctx: ResolutionContext) -> Optional[FieldResolution]:
    if not ctx.can_attempt:
        return None

    entry    = ctx.registry_entry
    behavior = get_field_behavior(FIELD, ctx.parsed_category, entry.field_behaviors)
    applied: list[str] = []

    # Check option overrides first (extendahoe, long arm, etc.)
    overridden = None
    for opt_key, overrides in (entry.option_overrides or {}).items():
        if ctx.detected_options.has(opt_key) and FIELD in overrides:
            overridden = overrides[FIELD]
            applied.append(opt_key)
            break

    # Prefer v2 decimal-feet key; fall back to legacy string/numeric key.
    raw_ft_val = entry.specs.get(_FIELD_V2_FT) if not overridden else None
    if overridden is not None:
        raw_val = overridden
        registry_val = normalize_dig_depth(raw_val)
    elif raw_ft_val is not None:
        raw_val = raw_ft_val
        registry_val = decimal_ft_to_ft_in(float(raw_ft_val))
    else:
        raw_val = entry.specs.get(FIELD)
        registry_val = normalize_dig_depth(raw_val) if raw_val is not None else None
    family_range = entry.family_ranges.get(FIELD) if ctx.is_family else None

    if ctx.is_exact and registry_val is not None:
        value, source = registry_val, FieldSource.REGISTRY_EXACT
    elif ctx.is_family and family_range:
        value, source = family_range, FieldSource.REGISTRY_FAMILY
    elif ctx.is_family and registry_val is not None:
        value, source = registry_val, FieldSource.REGISTRY_FAMILY
    else:
        value, source = None, FieldSource.UNRESOLVED

    decision = evaluate_injection(
        field_name=FIELD,
        behavior=behavior,
        match_type=ctx.match_type,
        registry_confidence=ctx.registry_confidence,
        is_package_dependent=(
            behavior.value == "package_dependent" and not applied
        ),
    )
    if value is None:
        decision = InjectionDecision(
            should_inject=False, require_confirm=True,
            reason=f"Unresolved — no {FIELD} in registry.",
        )

    return build_resolution(
        ctx=ctx, value=value, source=source,
        behavior=behavior, decision=decision,
        registry_value=raw_val,
        options_applied=applied,
    )
