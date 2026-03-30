"""
confidence_policy.py
Defines confidence thresholds, injection gates, and overall status mapping.

This module answers two questions:
  1. Is confidence high enough to inject a spec at all?
  2. What overall_resolution_status should be reported?

The fail-closed rule: when uncertain, return null/omit rather than guess.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .types import FieldBehavior, MatchType, OverallStatus


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Minimum registry_match_confidence to attempt any spec injection
INJECTION_MINIMUM_CONFIDENCE = 0.70

# Minimum for a LOCKED field to be injected without require_confirm
LOCKED_FIELD_AUTO_INJECT_THRESHOLD = 0.85

# Minimum for a RANGE field to be surfaced (with require_confirm)
RANGE_FIELD_SURFACE_THRESHOLD = 0.70

# Below this, do not inject anything — return unresolved
HARD_FLOOR_CONFIDENCE = 0.55


# ---------------------------------------------------------------------------
# Policy dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InjectionDecision:
    should_inject:    bool
    require_confirm:  bool
    reason:           str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_injection(
    field_name: str,
    behavior: FieldBehavior,
    match_type: MatchType,
    registry_confidence: float,
    has_conflict: bool = False,
    is_package_dependent: bool = False,
) -> InjectionDecision:
    """
    Decide whether to inject a field value and whether to require user confirmation.

    Returns InjectionDecision with should_inject, require_confirm, reason.
    """

    # Hard floor: below minimum confidence → never inject anything
    if registry_confidence < HARD_FLOOR_CONFIDENCE:
        return InjectionDecision(
            should_inject=False,
            require_confirm=False,
            reason=(
                f"Confidence {registry_confidence:.2f} below hard floor "
                f"{HARD_FLOOR_CONFIDENCE}. No injection."
            ),
        )

    # Manufacturer-only or no match → never inject
    if match_type in (MatchType.MANUFACTURER_ONLY, MatchType.NONE):
        return InjectionDecision(
            should_inject=False,
            require_confirm=False,
            reason=f"match_type={match_type.value}: injection blocked.",
        )

    # Manual review fields: never inject
    if behavior == FieldBehavior.MANUAL_REVIEW:
        return InjectionDecision(
            should_inject=False,
            require_confirm=True,
            reason="Field behavior is MANUAL_REVIEW: auto-injection blocked.",
        )

    # Conflict: inject with warning and require_confirm
    if has_conflict:
        return InjectionDecision(
            should_inject=True,
            require_confirm=True,
            reason=(
                "Seller claim conflicts with registry value. "
                "Registry value injected — requires confirmation."
            ),
        )

    # Exact match, locked field, above threshold
    if (
        match_type == MatchType.EXACT
        and behavior == FieldBehavior.LOCKED
        and registry_confidence >= LOCKED_FIELD_AUTO_INJECT_THRESHOLD
        and not is_package_dependent
    ):
        return InjectionDecision(
            should_inject=True,
            require_confirm=False,
            reason="Exact model locked spec. Auto-injected.",
        )

    # Exact match, locked field, below auto-inject threshold
    if match_type == MatchType.EXACT and behavior == FieldBehavior.LOCKED:
        return InjectionDecision(
            should_inject=True,
            require_confirm=True,
            reason=(
                f"Exact match but confidence {registry_confidence:.2f} below "
                f"auto-inject threshold {LOCKED_FIELD_AUTO_INJECT_THRESHOLD}. "
                "Injected with confirmation required."
            ),
        )

    # Family match: inject ranges, always require confirm
    if match_type == MatchType.FAMILY:
        if registry_confidence < RANGE_FIELD_SURFACE_THRESHOLD:
            return InjectionDecision(
                should_inject=False,
                require_confirm=False,
                reason=(
                    f"Family confidence {registry_confidence:.2f} below "
                    f"surface threshold {RANGE_FIELD_SURFACE_THRESHOLD}."
                ),
            )
        return InjectionDecision(
            should_inject=True,
            require_confirm=True,
            reason="Family-level match. Range value injected — confirmation required.",
        )

    # Package-dependent with option detected (exact match)
    if behavior == FieldBehavior.PACKAGE_DEPENDENT and not is_package_dependent:
        return InjectionDecision(
            should_inject=True,
            require_confirm=False,
            reason="Package-dependent spec resolved via detected option.",
        )

    # Package-dependent WITHOUT option detected
    if behavior == FieldBehavior.PACKAGE_DEPENDENT and is_package_dependent:
        return InjectionDecision(
            should_inject=False,
            require_confirm=True,
            reason=(
                "Package-dependent field: required option not detected. "
                "Cannot resolve — requires confirmation."
            ),
        )

    # Range behavior (always require confirm)
    if behavior == FieldBehavior.RANGE:
        return InjectionDecision(
            should_inject=True,
            require_confirm=True,
            reason="Field is range type. Injected as range — confirmation required.",
        )

    # Default fallback: inject with confirm
    return InjectionDecision(
        should_inject=True,
        require_confirm=True,
        reason="Default policy: injected with confirmation required.",
    )


def determine_overall_status(
    match_type: MatchType,
    registry_confidence: float,
    n_resolved_fields: int,
    n_total_fields: int,
) -> OverallStatus:
    """Map match type + confidence to overall_resolution_status."""

    if match_type == MatchType.NONE or registry_confidence < HARD_FLOOR_CONFIDENCE:
        return OverallStatus.UNRESOLVED

    if match_type == MatchType.MANUFACTURER_ONLY:
        return OverallStatus.UNRESOLVED

    if match_type == MatchType.EXACT and registry_confidence >= LOCKED_FIELD_AUTO_INJECT_THRESHOLD:
        return OverallStatus.EXACT

    if match_type == MatchType.FAMILY and registry_confidence >= RANGE_FIELD_SURFACE_THRESHOLD:
        return OverallStatus.FAMILY

    if registry_confidence >= HARD_FLOOR_CONFIDENCE and n_resolved_fields > 0:
        return OverallStatus.WEAK

    return OverallStatus.UNRESOLVED


def is_safe_for_listing_injection(
    overall_status: OverallStatus,
    n_warnings: int,
    n_require_confirm: int,
) -> bool:
    """
    Return True only when it is safe to auto-inject specs into a listing draft.
    Conservative: exact status with no errors and few confirmations.
    """
    if overall_status in (OverallStatus.UNRESOLVED, OverallStatus.WEAK):
        return False
    # Allow family matches but flag them — UI still shows yellow cells
    return True
