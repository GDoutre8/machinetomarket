"""
dealer_input.py
Manual dealer-entered V1 listing inputs, separate from registry/autofilled OEM specs.

This model represents what a dealer provides when creating a listing through
the MTM workflow.  It is intentionally distinct from:
  - registry lookup results (OEM specs, autofilled values)
  - spec resolver output (resolved_specs, requires_confirm)
  - listing text or output assets

Intended consumers (wired up in a later task):
  - listing generation  (mtm_service._stub_generate_listing_text)
  - feature text builder
  - pack generation workflow (listing_pack_builder.build_listing_pack)
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

# Reasonable production year boundaries for used-market CTL / heavy equipment.
_YEAR_MIN = 1970
_YEAR_MAX = 2030


class DealerInput(BaseModel):
    """Manual dealer-entered V1 listing inputs."""

    # ── Required identity ─────────────────────────────────────────────────────
    year:  int
    make:  str
    model: str
    hours: int

    # ── Feature toggles (all default False) ───────────────────────────────────
    enclosed_cab:  bool = False
    heat:          bool = False
    ac:            bool = False
    high_flow:     bool = False
    two_speed:     bool = False
    ride_control:  bool = False
    backup_camera: bool = False
    one_owner:     bool = False

    # ── Numeric condition ─────────────────────────────────────────────────────
    track_condition_pct: Optional[int] = None

    # ── Free text ─────────────────────────────────────────────────────────────
    attachments_included: Optional[str] = None
    condition_notes:      Optional[str] = None

    # ── Validation ────────────────────────────────────────────────────────────

    @field_validator("year")
    @classmethod
    def year_in_range(cls, v: int) -> int:
        if not (_YEAR_MIN <= v <= _YEAR_MAX):
            raise ValueError(f"year must be between {_YEAR_MIN} and {_YEAR_MAX}")
        return v

    @field_validator("make")
    @classmethod
    def make_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("make cannot be blank")
        return v.strip()

    @field_validator("model")
    @classmethod
    def model_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model cannot be blank")
        return v.strip()

    @field_validator("hours")
    @classmethod
    def hours_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("hours cannot be negative")
        return v

    @field_validator("track_condition_pct")
    @classmethod
    def track_pct_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 100):
            raise ValueError("track_condition_pct must be between 0 and 100")
        return v
