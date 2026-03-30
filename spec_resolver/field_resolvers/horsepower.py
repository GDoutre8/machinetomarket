"""
field_resolvers/horsepower.py
Resolves net_hp (net horsepower) for a registry entry.
"""

from __future__ import annotations
from typing import Optional

from ..types import FieldBehavior, FieldSource, MatchType
from ..confidence_policy import evaluate_injection
from ..field_rules import get_field_behavior
from ..unit_normalizer import kw_to_hp
from ._base import (
    ResolutionContext, FieldResolution, build_resolution,
    check_seller_conflict,
)

FIELD = "net_hp"


def resolve(ctx: ResolutionContext) -> Optional[FieldResolution]:
    """
    Resolve net_hp for the given context.
    Returns None if resolution should not be attempted.
    """
    if not ctx.can_attempt:
        return None

    entry = ctx.registry_entry
    behavior = get_field_behavior(FIELD, ctx.parsed_category, entry.field_behaviors)

    # ── Pull registry value ───────────────────────────────────────────────
    registry_hp = entry.specs.get(FIELD)

    # Handle kW → hp conversion if registry stores kW
    if registry_hp is None:
        registry_kw = entry.specs.get("net_kw")
        if registry_kw is not None:
            registry_hp = kw_to_hp(float(registry_kw))

    # Family range string
    family_range = entry.family_ranges.get(FIELD) if ctx.is_family else None

    # ── Seller claim ──────────────────────────────────────────────────────
    seller_hp = ctx.numeric_claims.get("seller_hp")
    conflict = check_seller_conflict(
        float(registry_hp) if registry_hp else None,
        float(seller_hp) if seller_hp else None,
    )

    # ── Choose value + source ─────────────────────────────────────────────
    if ctx.is_exact and registry_hp is not None:
        value  = registry_hp
        source = FieldSource.REGISTRY_EXACT
    elif ctx.is_family and family_range:
        value  = family_range
        source = FieldSource.REGISTRY_FAMILY
    elif ctx.is_family and registry_hp is not None:
        # No explicit family range — use point value but mark as family
        value  = registry_hp
        source = FieldSource.REGISTRY_FAMILY
    else:
        value  = None
        source = FieldSource.UNRESOLVED

    # ── Injection decision ────────────────────────────────────────────────
    decision = evaluate_injection(
        field_name=FIELD,
        behavior=behavior,
        match_type=ctx.match_type,
        registry_confidence=ctx.registry_confidence,
        has_conflict=conflict,
    )

    if value is None:
        decision_reason = f"Unresolved — no {FIELD} in registry for this entry."
        from ..confidence_policy import InjectionDecision
        decision = InjectionDecision(
            should_inject=False,
            require_confirm=True,
            reason=decision_reason,
        )

    return build_resolution(
        ctx=ctx,
        value=value,
        source=source,
        behavior=behavior,
        decision=decision,
        conflict=conflict,
        registry_value=registry_hp,
        seller_value=seller_hp,
        notes=(
            [f"Seller claimed {seller_hp} hp"] if seller_hp else []
        ),
    )
