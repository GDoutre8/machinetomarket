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

    # ── Skid steer / CTL / mini-ex unit-level status fields ─────────────────────
    # These are BUYER-FACING STATUS FIELDS, not installed-truth booleans.
    # Allowed values: "yes" | "no" | "optional"
    #   "yes"      = standard on this model/config (unit has it)
    #   "optional" = OEM offers it, but not standard on this unit
    #   "no"       = not offered by OEM for this model/config
    # None = unknown / not confirmed by dealer.
    # Installed-truth (unit-confirmed) must use separate _installed fields (future).
    high_flow:        Optional[str] = None
    two_speed_travel: Optional[str] = None  # renamed from two_speed; SSL/CTL + mini_ex

    # ── Feature toggles (all default False) ───────────────────────────────────
    heater:        Optional[bool] = None   # confirm-required; renamed from heat
    ac:            Optional[bool] = None   # confirm-required
    ride_control:  bool = False
    backup_camera: bool = False
    one_owner:     bool = False
    radio:         bool = False

    # ── Cab and controls — string fields (not booleans) ───────────────────────
    # cab_type: canonical cab classification (e.g. "enclosed", "canopy", "open")
    #   None = not specified / unknown
    cab_type:      Optional[str] = None
    # control_type: normalized controls descriptor (e.g. "joystick", "hand_foot", "pilot")
    #   None = not specified / unknown
    control_type:  Optional[str] = None

    # ── Skid steer dealer-input features (secondary output) ───────────────────
    # tire_condition: free-text dealer description (e.g. "80%", "new rubber", "fair")
    # (tire_condition_pct integer field is not used — free text only)
    tire_condition: Optional[str] = None

    # ── CTL core output — confirm-required or always-shown ────────────────────
    # serial_number: unit-level identifier; core output per locked CTL standard.
    #   None = not provided by dealer.
    serial_number:   Optional[str] = None
    # stock_number: dealer internal stock/inventory number.
    #   None = not provided by dealer.
    stock_number:    Optional[str] = None

    # ── CTL feature toggles (secondary output / listing features) ─────────────
    # These appear in listing text and are part of the locked CTL feature set.
    air_ride_seat:   bool = False
    self_leveling:   bool = False   # self-leveling loader arms
    reversing_fan:   bool = False
    bucket_included: bool = False
    # bucket_size: free-text bucket description (e.g. "72 inch GP bucket")
    bucket_size:     Optional[str] = None
    # warranty_status: free-text warranty description (e.g. "1 year remaining")
    warranty_status: Optional[str] = None

    # ── Mini-excavator specific ───────────────────────────────────────────────
    thumb_type:      Optional[str] = None   # hydraulic / manual / none
    aux_hydraulics:  Optional[bool] = None  # confirm-required: dedicated aux port for attachments
    blade_type:      Optional[str] = None   # straight / angle / 6-way
    arm_length:      Optional[str] = None   # standard / long / extenda
    pattern_changer: Optional[bool] = None  # confirm-required
    zero_tail_swing: bool = False
    rubber_tracks:   bool = False   # False = steel tracks

    # ── Telehandler specific ─────────────────────────────────────────────────
    # has_stabilizers: whether this unit is equipped with outrigger/stabilizers.
    #   True  = stabilizers present
    #   False = no stabilizers
    #   None  = unknown / not confirmed by dealer
    has_stabilizers: Optional[bool] = None

    # ── Large excavator specific (locked standard 2026-04-10) ─────────────────
    # aux_hydraulics_type: structured type field for 20–40 ton class excavators.
    #   None = not confirmed by dealer.
    aux_hydraulics_type:         Optional[str] = None   # standard / high_pressure / combined / hammer
    # undercarriage_condition_pct: free text — preserves raw dealer language.
    #   e.g. "75%", "60%+", "good", "new rails", "rebuilt"
    undercarriage_condition_pct: Optional[str] = None
    # undercarriage_percent_remaining: numeric estimate of undercarriage life remaining (0–100).
    #   Rendered on spec sheet as "Undercarriage % Remaining: 75%".
    #   Never converted from free-text grade — numeric only.
    undercarriage_percent_remaining: Optional[int] = None
    stick_arm_length_ft:         Optional[float] = None
    track_shoe_width_in:         Optional[float] = None
    boom_length_ft:              Optional[float] = None
    boom_type:                   Optional[str] = None   # reach / standard / mass_excavation
    rear_camera:                 Optional[bool] = None
    grade_control_type:          Optional[str] = None   # none / 2D / 3D
    hammer_plumbing:             Optional[bool] = None
    heated_seat:                 Optional[bool] = None
    track_type:                  Optional[str] = None   # rubber / steel / double_grouser
    # tail_swing_type: machine swing class (cross-type: large_excavator + mini_excavator)
    tail_swing_type:             Optional[str] = None   # standard / reduced / zero
    # hours_qualifier: free text for hours condition note (e.g. "Low Hours", "Since Rebuild")
    hours_qualifier:             Optional[str] = None

    # ── Cross-type ────────────────────────────────────────────────────────────
    # coupler_type: attachment coupler style; None = not equipped / unknown
    coupler_type:        Optional[str] = None   # hydraulic / manual / pin-on

    # bucket_size_included: free-text description if bucket included (e.g. '24" dig bucket')
    bucket_size_included: Optional[str] = None

    # ── Pricing ───────────────────────────────────────────────────────────────
    asking_price: Optional[int] = None  # dealer asking price in USD, e.g. 49500

    # ── Condition (cross-type) ────────────────────────────────────────────────
    # track_condition: free-text dealer description of track condition.
    #   e.g. "70%", "Good", "Just replaced", "Worn — needs replacement"
    #   None = not provided.
    track_condition: Optional[str] = None
    # track_percent_remaining: integer estimate of track life remaining (0–100).
    #   Rendered on spec sheet as "Track % Remaining: 85%".
    #   Separate from track_condition grade — never converted from grade text.
    #   None = not provided by dealer.
    track_percent_remaining: Optional[int] = None
    # condition_grade: structured overall condition rating for spec sheet display.
    #   Allowed values: "Excellent", "Good", "Fair" (case-sensitive).
    #   None = dealer did not select a grade.
    condition_grade: Optional[str] = None

    # ── Free text ─────────────────────────────────────────────────────────────
    attachments_included: Optional[str] = None
    condition_notes:      Optional[str] = None   # legacy — use additional_details for new sessions
    additional_features:  Optional[str] = None   # extra features, renders under Features section
    additional_details:   Optional[str] = None   # sales notes / remarks, renders at end of listing
    comparable_models:    Optional[str] = None   # manually entered comparable models for the listing

    # ── Validation ────────────────────────────────────────────────────────────

    @field_validator("high_flow", "two_speed_travel", mode="before")
    @classmethod
    def status_field_valid(cls, v: object) -> "Optional[str]":
        """
        Validate and normalize high_flow / two_speed_travel status fields.
        Accepted input values → normalized output:
          True / "true" / "1" / "on"   → "yes"
          False / "false" / "0" / "off" → "no"
          "yes"                          → "yes"
          "no"                           → "no"
          "optional"                     → "optional"
          None / ""                      → None
        Backward compatibility: Python bool True/False accepted (maps to yes/no).
        """
        if v is None:
            return None
        if isinstance(v, bool):
            return "yes" if v else "no"
        s = str(v).strip().lower()
        if not s:
            return None
        if s in ("true", "1", "on"):
            return "yes"
        if s in ("false", "0", "off"):
            return "no"
        if s in ("yes", "no", "optional"):
            return s
        raise ValueError(f"must be 'yes', 'no', or 'optional'; got '{v}'")

    @field_validator("track_percent_remaining")
    @classmethod
    def track_percent_in_range(cls, v: "Optional[int]") -> "Optional[int]":
        if v is not None and not (0 <= v <= 100):
            raise ValueError("track_percent_remaining must be between 0 and 100")
        return v

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

    @field_validator("asking_price")
    @classmethod
    def asking_price_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("asking_price must be a positive integer")
        return v

    @field_validator("condition_grade")
    @classmethod
    def condition_grade_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"Excellent", "Good", "Fair"}
        if v is not None and v not in _ALLOWED:
            raise ValueError(f"condition_grade must be 'Excellent', 'Good', or 'Fair'; got '{v}'")
        return v or None

    @field_validator("coupler_type")
    @classmethod
    def coupler_type_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"hydraulic", "manual", "pin-on"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(f"coupler_type must be 'hydraulic', 'manual', or 'pin-on'; got '{v}'")
        return v or None

    @field_validator("thumb_type")
    @classmethod
    def thumb_type_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"hydraulic", "manual", "none"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(f"thumb_type must be 'hydraulic', 'manual', or 'none'; got '{v}'")
        return v or None

    @field_validator("blade_type")
    @classmethod
    def blade_type_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"straight", "angle", "6-way"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(f"blade_type must be 'straight', 'angle', or '6-way'; got '{v}'")
        return v or None

    @field_validator("arm_length")
    @classmethod
    def arm_length_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"standard", "long", "extenda"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(f"arm_length must be 'standard', 'long', or 'extenda'; got '{v}'")
        return v or None

    @field_validator("aux_hydraulics_type")
    @classmethod
    def aux_hydraulics_type_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"standard", "high_pressure", "combined", "hammer"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(
                    f"aux_hydraulics_type must be 'standard', 'high_pressure', 'combined', or 'hammer'; got '{v}'"
                )
        return v or None

    @field_validator("undercarriage_percent_remaining")
    @classmethod
    def undercarriage_percent_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 100):
            raise ValueError("undercarriage_percent_remaining must be between 0 and 100")
        return v

    @field_validator("boom_type")
    @classmethod
    def boom_type_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"reach", "standard", "mass_excavation"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(
                    f"boom_type must be 'reach', 'standard', or 'mass_excavation'; got '{v}'"
                )
        return v or None

    @field_validator("tail_swing_type")
    @classmethod
    def tail_swing_type_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"standard", "reduced", "zero"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(
                    f"tail_swing_type must be 'standard', 'reduced', or 'zero'; got '{v}'"
                )
        return v or None

    @field_validator("grade_control_type")
    @classmethod
    def grade_control_type_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"none", "2d", "3d"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(f"grade_control_type must be 'none', '2D', or '3D'; got '{v}'")
            # Normalize canonical casing
            v = {"2d": "2D", "3d": "3D", "none": "none"}[v]
        return v or None

    @field_validator("track_type")
    @classmethod
    def track_type_valid(cls, v: Optional[str]) -> Optional[str]:
        _ALLOWED = {"rubber", "steel", "double_grouser"}
        if v is not None:
            v = v.strip().lower()
            if v not in _ALLOWED:
                raise ValueError(f"track_type must be 'rubber', 'steel', or 'double_grouser'; got '{v}'")
        return v or None
