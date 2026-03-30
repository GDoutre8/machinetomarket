"""
field_resolvers/roc.py
Resolves roc_lb (Rated Operating Capacity).
Family matches return range strings per spec: "3,400–3,700"
"""

from __future__ import annotations
from typing import Optional

from ..types import FieldBehavior, FieldSource
from ..confidence_policy import evaluate_injection, InjectionDecision
from ..field_rules import get_field_behavior
from ._base import ResolutionContext, FieldResolution, build_resolution

FIELD = "roc_lb"


def resolve(ctx: ResolutionContext) -> Optional[FieldResolution]:
    if not ctx.can_attempt:
        return None

    entry    = ctx.registry_entry
    behavior = get_field_behavior(FIELD, ctx.parsed_category, entry.field_behaviors)

    registry_roc = entry.specs.get(FIELD)
    family_range = entry.family_ranges.get(FIELD) if ctx.is_family else None

    # Option overrides (e.g. XE variant has higher ROC)
    applied: list[str] = []
    for opt_key, overrides in (entry.option_overrides or {}).items():
        if ctx.detected_options.has(opt_key) and FIELD in overrides:
            registry_roc = overrides[FIELD]
            applied.append(opt_key)

    seller_roc = ctx.numeric_claims.get("seller_roc_lb")

    if ctx.is_exact and registry_roc is not None:
        value, source = registry_roc, FieldSource.REGISTRY_EXACT
    elif ctx.is_family and family_range:
        value, source = family_range, FieldSource.REGISTRY_FAMILY
    elif ctx.is_family and registry_roc is not None:
        value, source = registry_roc, FieldSource.REGISTRY_FAMILY
    else:
        value, source = None, FieldSource.UNRESOLVED

    decision = evaluate_injection(
        field_name=FIELD,
        behavior=behavior,
        match_type=ctx.match_type,
        registry_confidence=ctx.registry_confidence,
    )
    if value is None:
        decision = InjectionDecision(
            should_inject=False, require_confirm=True,
            reason=f"Unresolved — no {FIELD} in registry.",
        )

    return build_resolution(
        ctx=ctx, value=value, source=source,
        behavior=behavior, decision=decision,
        registry_value=entry.specs.get(FIELD),
        seller_value=seller_roc,
        options_applied=applied,
    )
