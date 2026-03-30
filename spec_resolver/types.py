"""
types.py
Strict schemas and interfaces for the spec resolver.
All data crossing module boundaries is typed here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MatchType(str, Enum):
    EXACT              = "exact"
    FAMILY             = "family"
    MANUFACTURER_ONLY  = "manufacturer_only"
    NONE               = "none"


class FieldSource(str, Enum):
    REGISTRY_EXACT   = "registry_exact"
    REGISTRY_FAMILY  = "registry_family"
    SELLER_CLAIM     = "seller_claim"
    UNRESOLVED       = "unresolved"


class FieldBehavior(str, Enum):
    LOCKED            = "locked"            # exact value, must not be overridden
    RANGE             = "range"             # family-level, show as editable range
    PACKAGE_DEPENDENT = "package_dependent" # depends on detected options
    MANUAL_REVIEW     = "manual_review"     # do not auto-inject ever


class OverallStatus(str, Enum):
    EXACT      = "exact"
    FAMILY     = "family"
    WEAK       = "weak"
    UNRESOLVED = "unresolved"


class WarningSeverity(str, Enum):
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"


# ---------------------------------------------------------------------------
# Warning
# ---------------------------------------------------------------------------

@dataclass
class ResolverWarning:
    code: str
    message: str
    field: Optional[str] = None
    severity: WarningSeverity = WarningSeverity.WARNING

    def to_dict(self) -> dict:
        return {
            "code":     self.code,
            "message":  self.message,
            "field":    self.field,
            "severity": self.severity.value,
        }


# ---------------------------------------------------------------------------
# Per-field metadata
# ---------------------------------------------------------------------------

@dataclass
class FieldMeta:
    value:             Optional[Union[str, int, float, bool]]
    source:            FieldSource
    confidence:        float                # 0.0 – 1.0
    behavior:          FieldBehavior
    resolution_reason: str
    injected:          bool

    def to_dict(self) -> dict:
        return {
            "value":              self.value,
            "source":             self.source.value,
            "confidence":         round(self.confidence, 3),
            "behavior":           self.behavior.value,
            "resolution_reason":  self.resolution_reason,
            "injected":           self.injected,
        }


# ---------------------------------------------------------------------------
# Resolver input
# ---------------------------------------------------------------------------

@dataclass
class ResolverInput:
    raw_listing_text:          str
    parsed_manufacturer:       str
    parsed_model:              str
    parsed_category:           str
    detected_modifiers:        List[str]
    extracted_numeric_claims:  Dict[str, Any]
    registry_match:            Dict[str, Any]          # the matched registry entry
    registry_match_confidence: float                   # 0.0 – 1.0
    match_type:                MatchType

    def validate(self) -> None:
        """Raise ValueError if required fields are missing or invalid."""
        if not self.parsed_manufacturer:
            raise ValueError("parsed_manufacturer is required")
        # parsed_model may be empty for manufacturer_only and none match types
        requires_model = self.match_type not in (
            MatchType.MANUFACTURER_ONLY, MatchType.NONE
        )
        if requires_model and not self.parsed_model:
            raise ValueError(
                "parsed_model is required when match_type is not "
                "'manufacturer_only' or 'none'"
            )
        if not self.parsed_category:
            raise ValueError("parsed_category is required")
        if not (0.0 <= self.registry_match_confidence <= 1.0):
            raise ValueError(
                f"registry_match_confidence must be 0.0–1.0, "
                f"got {self.registry_match_confidence}"
            )


# ---------------------------------------------------------------------------
# Resolver output
# ---------------------------------------------------------------------------

@dataclass
class ResolverOutput:
    resolved_specs:            Dict[str, Any]
    requires_confirm:          List[str]
    ui_hints:                  Dict[str, Any]
    per_field_metadata:        Dict[str, FieldMeta]
    warnings:                  List[ResolverWarning]
    overall_resolution_status: OverallStatus
    safe_for_listing_injection: bool

    def to_dict(self) -> dict:
        return {
            "resolved_specs":             self.resolved_specs,
            "requires_confirm":           self.requires_confirm,
            "ui_hints":                   self.ui_hints,
            "per_field_metadata":         {
                k: v.to_dict() for k, v in self.per_field_metadata.items()
            },
            "warnings":                   [w.to_dict() for w in self.warnings],
            "overall_resolution_status":  self.overall_resolution_status.value,
            "safe_for_listing_injection": self.safe_for_listing_injection,
        }


# ---------------------------------------------------------------------------
# Registry entry shape (what we expect from the registry JSON/dict)
# ---------------------------------------------------------------------------

@dataclass
class RegistryEntry:
    """
    Typed wrapper around a raw registry dict.
    Only decodes the fields the resolver actually needs.
    All other fields are preserved in .raw for forward-compatibility.
    """
    family:        str
    mfr:           str
    category:      str
    year_range:    List[int]           # [min_year, max_year]
    specs:         Dict[str, Any]      # canonical point-value specs
    family_ranges: Dict[str, str]      # field → "low–high" string
    variants:      List[str]           # exact model strings in this family
    # field-level behavior overrides: field → FieldBehavior
    field_behaviors: Dict[str, FieldBehavior] = field(default_factory=dict)
    # option-triggered spec overrides: option_key → {field: value}
    option_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # year-keyed spec overrides: {max_year: {field: value}}
    year_overrides: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "RegistryEntry":
        behaviors = {}
        for k, v in d.get("field_behaviors", {}).items():
            try:
                behaviors[k] = FieldBehavior(v)
            except ValueError:
                # Unknown values (e.g. "not_applicable") → treat as MANUAL_REVIEW
                behaviors[k] = FieldBehavior.MANUAL_REVIEW
        return cls(
            family           = d["family"],
            mfr              = d["mfr"],
            category         = d["category"],
            year_range       = d.get("year_range", [2000, 2030]),
            specs            = d.get("specs", {}),
            family_ranges    = d.get("family_ranges", {}),
            variants         = d.get("variants", []),
            field_behaviors  = behaviors,
            option_overrides = d.get("option_overrides", {}),
            year_overrides   = {
                int(k): v for k, v in d.get("year_overrides", {}).items()
            },
            raw = d,
        )
