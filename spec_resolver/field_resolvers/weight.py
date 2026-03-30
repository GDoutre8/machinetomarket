"""
field_resolvers/weight.py
Resolves operating_weight_lb.

Special cases:
  - Cab vs canopy adds ~200–400 lbs to base weight
  - LGP variant adds track/blade weight
  - Backhoe: 2WD vs 4WD changes weight
  - These adjustments are driven by option_overrides in the registry entry.
"""

from __future__ import annotations
from typing import Optional

from ..types import FieldBehavior, FieldSource, MatchType
from ..confidence_policy import evaluate_injection, InjectionDecision
from ..field_rules import get_field_behavior
from ..unit_normalizer import kg_to_lb
from ._base import (
    ResolutionContext, FieldResolution, build_resolution,
    check_seller_conflict,
)

FIELD = "operating_weight_lb"


def resolve(ctx: ResolutionContext) -> Optional[FieldResolution]:
    if not ctx.can_attempt:
        return None

    entry    = ctx.registry_entry
    behavior = get_field_behavior(FIELD, ctx.parsed_category, entry.field_behaviors)
    options  = ctx.detected_options
    applied_options: list[str] = []

    # ── Registry value ────────────────────────────────────────────────────
    registry_weight = entry.specs.get(FIELD)
    if registry_weight is None:
        registry_kg = entry.specs.get("operating_weight_kg")
        if registry_kg is not None:
            registry_weight = kg_to_lb(float(registry_kg))

    # ── Option overrides ──────────────────────────────────────────────────
    # Registry may define option_overrides like:
    #   { "lgp": { "operating_weight_lb": 51875 },
    #     "has_cab": { "operating_weight_lb": 9500 },
    #     "has_canopy": { "operating_weight_lb": 9200 } }

    overridden_weight = registry_weight
    for opt_key, overrides in (entry.option_overrides or {}).items():
        if options.has(opt_key) and FIELD in overrides:
            overridden_weight = overrides[FIELD]
            applied_options.append(opt_key)

    # Family range
    family_range = entry.family_ranges.get(FIELD) if ctx.is_family else None

    # ── Seller claim ──────────────────────────────────────────────────────
    seller_weight = ctx.numeric_claims.get("seller_op_weight_lb")
    reg_val_for_conflict = (
        float(overridden_weight) if overridden_weight is not None else None
    )
    conflict = check_seller_conflict(reg_val_for_conflict, seller_weight)

    # ── Choose value + source ─────────────────────────────────────────────
    if ctx.is_exact and overridden_weight is not None:
        value  = overridden_weight
        source = FieldSource.REGISTRY_EXACT if not applied_options else FieldSource.REGISTRY_EXACT
    elif ctx.is_family and family_range:
        value  = family_range
        source = FieldSource.REGISTRY_FAMILY
    elif ctx.is_family and registry_weight is not None:
        value  = registry_weight
        source = FieldSource.REGISTRY_FAMILY
    else:
        value  = None
        source = FieldSource.UNRESOLVED

    # ── Injection decision ────────────────────────────────────────────────
    is_pkg = (behavior == FieldBehavior.PACKAGE_DEPENDENT and not applied_options)
    decision = evaluate_injection(
        field_name=FIELD,
        behavior=behavior,
        match_type=ctx.match_type,
        registry_confidence=ctx.registry_confidence,
        has_conflict=conflict,
        is_package_dependent=is_pkg,
    )

    if value is None:
        decision = InjectionDecision(
            should_inject=False,
            require_confirm=True,
            reason=f"Unresolved — no {FIELD} in registry for this entry.",
        )

    notes = []
    if applied_options:
        notes.append(f"Weight adjusted for options: {', '.join(applied_options)}")
    if seller_weight:
        notes.append(f"Seller claimed {seller_weight:,.0f} lb")

    return build_resolution(
        ctx=ctx,
        value=value,
        source=source,
        behavior=behavior,
        decision=decision,
        conflict=conflict,
        registry_value=registry_weight,
        seller_value=seller_weight,
        options_applied=applied_options,
        notes=notes,
    )
