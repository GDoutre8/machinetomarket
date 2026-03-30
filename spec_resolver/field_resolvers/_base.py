"""
field_resolvers/_base.py
Shared resolution context dataclass and helpers used by all field resolvers.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..types import (
    FieldBehavior, FieldMeta, FieldSource, MatchType,
    RegistryEntry, ResolverWarning, WarningSeverity,
)
from ..confidence_policy import evaluate_injection, InjectionDecision
from ..field_rules import get_field_behavior, should_require_confirm
from ..audit_trail import FieldTrace


# ---------------------------------------------------------------------------
# Resolution context — passed into every field resolver
# ---------------------------------------------------------------------------

@dataclass
class ResolutionContext:
    """Everything a field resolver needs to make its decision."""
    field_name:          str
    match_type:          MatchType
    registry_entry:      Optional[RegistryEntry]
    registry_confidence: float
    detected_options:    Any            # DetectedOptions
    numeric_claims:      Dict[str, Any]
    parsed_year:         Optional[int]  = None
    parsed_category:     str            = ""

    @property
    def is_exact(self) -> bool:
        return self.match_type == MatchType.EXACT

    @property
    def is_family(self) -> bool:
        return self.match_type == MatchType.FAMILY

    @property
    def can_attempt(self) -> bool:
        return (
            self.match_type not in (MatchType.NONE, MatchType.MANUFACTURER_ONLY)
            and self.registry_entry is not None
        )


# ---------------------------------------------------------------------------
# Resolution result
# ---------------------------------------------------------------------------

@dataclass
class FieldResolution:
    meta:     FieldMeta
    trace:    FieldTrace
    warnings: List[ResolverWarning]


# ---------------------------------------------------------------------------
# Base helper: build FieldMeta + FieldTrace from a decision
# ---------------------------------------------------------------------------

def build_resolution(
    ctx: ResolutionContext,
    value: Any,
    source: FieldSource,
    behavior: FieldBehavior,
    decision: InjectionDecision,
    conflict: bool = False,
    registry_value: Any = None,
    seller_value: Any = None,
    options_applied: Optional[List[str]] = None,
    notes: Optional[List[str]] = None,
) -> FieldResolution:
    """
    Create a FieldResolution from pre-computed parts.
    Centralizes FieldMeta + FieldTrace construction so field resolvers
    don't duplicate that boilerplate.
    """
    warnings: List[ResolverWarning] = []

    if conflict:
        warnings.append(ResolverWarning(
            code="SELLER_CLAIM_CONFLICT",
            message=(
                f"Seller claim ({seller_value}) conflicts with registry value "
                f"({registry_value}) for {ctx.field_name}. Registry value retained."
            ),
            field=ctx.field_name,
            severity=WarningSeverity.WARNING,
        ))

    meta = FieldMeta(
        value=value if decision.should_inject else None,
        source=source,
        confidence=ctx.registry_confidence if decision.should_inject else 0.0,
        behavior=behavior,
        resolution_reason=decision.reason,
        injected=decision.should_inject,
    )

    trace = FieldTrace(
        field_name=ctx.field_name,
        final_value=meta.value,
        source=source,
        behavior=behavior,
        confidence=meta.confidence,
        injected=meta.injected,
        require_confirm=decision.require_confirm,
        resolution_reason=decision.reason,
        registry_value=registry_value,
        seller_claim_value=seller_value,
        conflict_detected=conflict,
        options_applied=options_applied or [],
        notes=notes or [],
    )

    return FieldResolution(meta=meta, trace=trace, warnings=warnings)


# ---------------------------------------------------------------------------
# Shared: check for seller claim conflict
# ---------------------------------------------------------------------------

CONFLICT_TOLERANCE = 0.05   # 5% — values within this ratio are not flagged

def check_seller_conflict(
    registry_val: Optional[float],
    seller_val: Optional[float],
) -> bool:
    """
    Return True if seller_val is present and differs from registry_val
    by more than CONFLICT_TOLERANCE.
    """
    if registry_val is None or seller_val is None:
        return False
    if registry_val == 0:
        return seller_val != 0
    ratio = abs(registry_val - seller_val) / abs(registry_val)
    return ratio > CONFLICT_TOLERANCE
