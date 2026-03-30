"""
audit_trail.py
Structured audit logging for every spec resolution decision.

Every resolved (or unresolved) field gets a full trail explaining:
  - What registry data was available
  - What options were detected
  - What precedence rule was applied
  - Why this specific value was chosen (or omitted)

This module is append-only during a single resolution run.
It does NOT write to disk — callers persist the trail if needed.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .types import FieldBehavior, FieldSource, MatchType


# ---------------------------------------------------------------------------
# Single field trace entry
# ---------------------------------------------------------------------------

@dataclass
class FieldTrace:
    field_name:         str
    final_value:        Any                         # None if unresolved
    source:             FieldSource
    behavior:           FieldBehavior
    confidence:         float
    injected:           bool
    require_confirm:    bool
    resolution_reason:  str
    registry_value:     Any = None                  # what the registry had
    seller_claim_value: Any = None                  # what seller asserted
    conflict_detected:  bool = False
    options_applied:    List[str] = field(default_factory=list)
    notes:              List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "field_name":         self.field_name,
            "final_value":        self.final_value,
            "source":             self.source.value,
            "behavior":           self.behavior.value,
            "confidence":         round(self.confidence, 3),
            "injected":           self.injected,
            "require_confirm":    self.require_confirm,
            "resolution_reason":  self.resolution_reason,
            "registry_value":     self.registry_value,
            "seller_claim_value": self.seller_claim_value,
            "conflict_detected":  self.conflict_detected,
            "options_applied":    self.options_applied,
            "notes":              self.notes,
        }


# ---------------------------------------------------------------------------
# Run-level summary
# ---------------------------------------------------------------------------

@dataclass
class AuditTrail:
    run_id:             str
    timestamp_utc:      str
    raw_input_preview:  str             # first 120 chars of raw listing text
    parsed_mfr:         str
    parsed_model:       str
    parsed_category:    str
    match_type:         MatchType
    registry_confidence: float
    detected_options:   List[str]
    numeric_claims:     Dict[str, Any]
    field_traces:       List[FieldTrace] = field(default_factory=list)
    global_warnings:    List[str] = field(default_factory=list)

    # ── builder helpers ──────────────────────────────────────────────────

    def add_trace(self, trace: FieldTrace) -> None:
        self.field_traces.append(trace)

    def add_warning(self, message: str) -> None:
        self.global_warnings.append(message)

    # ── serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "run_id":              self.run_id,
            "timestamp_utc":       self.timestamp_utc,
            "raw_input_preview":   self.raw_input_preview,
            "parsed_mfr":          self.parsed_mfr,
            "parsed_model":        self.parsed_model,
            "parsed_category":     self.parsed_category,
            "match_type":          self.match_type.value,
            "registry_confidence": round(self.registry_confidence, 3),
            "detected_options":    self.detected_options,
            "numeric_claims":      self.numeric_claims,
            "field_traces":        [t.to_dict() for t in self.field_traces],
            "global_warnings":     self.global_warnings,
        }

    # ── summary helpers ──────────────────────────────────────────────────

    @property
    def n_injected(self) -> int:
        return sum(1 for t in self.field_traces if t.injected)

    @property
    def n_unresolved(self) -> int:
        return sum(1 for t in self.field_traces if not t.injected)

    @property
    def n_conflicts(self) -> int:
        return sum(1 for t in self.field_traces if t.conflict_detected)

    @property
    def n_require_confirm(self) -> int:
        return sum(1 for t in self.field_traces if t.require_confirm)

    def summary_line(self) -> str:
        return (
            f"[{self.run_id}] {self.parsed_mfr} {self.parsed_model} | "
            f"match={self.match_type.value} conf={self.registry_confidence:.2f} | "
            f"injected={self.n_injected} unresolved={self.n_unresolved} "
            f"conflicts={self.n_conflicts} confirm={self.n_require_confirm}"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_audit_trail(
    run_id: str,
    raw_text: str,
    mfr: str,
    model: str,
    category: str,
    match_type: MatchType,
    confidence: float,
    detected_options: List[str],
    numeric_claims: Dict[str, Any],
) -> AuditTrail:
    return AuditTrail(
        run_id=run_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        raw_input_preview=raw_text[:120],
        parsed_mfr=mfr,
        parsed_model=model,
        parsed_category=category,
        match_type=match_type,
        registry_confidence=confidence,
        detected_options=detected_options,
        numeric_claims=numeric_claims,
    )


def make_unresolved_trace(
    field_name: str,
    reason: str,
    registry_value: Any = None,
    notes: Optional[List[str]] = None,
) -> FieldTrace:
    """Convenience builder for an unresolved field trace."""
    return FieldTrace(
        field_name=field_name,
        final_value=None,
        source=FieldSource.UNRESOLVED,
        behavior=FieldBehavior.MANUAL_REVIEW,
        confidence=0.0,
        injected=False,
        require_confirm=True,
        resolution_reason=reason,
        registry_value=registry_value,
        notes=notes or [],
    )
