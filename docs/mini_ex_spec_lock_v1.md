# Mini Excavator Spec System Lock — v1

**Date:** 2026-04-10
**Status:** LOCKED FOR LAUNCH
**Registry:** `registry/active/mtm_mini_ex_registry_v2_1.json`
**Runtime pointer:** `mtm_registry_lookup.py` → `REGISTRY_FILENAMES[EQ_MINI_EX]` = `mtm_mini_ex_registry_v2_1.json`

---

## Scope

This lock covers the mini excavator spec pipeline: schema, field naming, injection logic, display tiers, and form configuration. Registry records and model-level launch readiness are covered separately in `mini_ex_launch_lock_v1.md`.

---

## Pipeline Components Locked

| Component | File | Status |
|-----------|------|--------|
| DealerInput schema | `dealer_input.py` | LOCKED |
| Form config | `app.py` → `_FEATURE_CONFIG["mini_excavator"]` | LOCKED |
| Feature map | `listing_builder.py` → `_FEATURE_MAP` | LOCKED |
| Injection block | `listing_pack_builder.py` | LOCKED |
| Spec display tiers | `mtm_service.py` → `_MINI_EX_FIELDS` | LOCKED |
| Display label map | `mtm_service.py` → `_SPEC_DISPLAY_META` | LOCKED |

---

## Core Field Inventory

### OEM Registry Fields (flow via spec resolver)

| Lock Name | Registry Key | Pipeline Canonical | In Technical Tier | Notes |
|-----------|-------------|-------------------|-------------------|-------|
| `engine_hp` | `horsepower_hp` | `net_hp` | YES | Both aliases map to `net_hp` via `_SPEC_KEY_MAP` |
| `operating_weight_lb` | `operating_weight_lbs` | `operating_weight_lb` | YES | Mapped in `_SPEC_KEY_MAP` |
| `max_dig_depth_ft` | `max_dig_depth_ft` | `max_dig_depth` | YES | Formatted as "X ft Y in" string by resolver |
| `retractable_undercarriage` | `retractable_undercarriage` | — | NO | Null across all records — ACCEPTED CONDITION |
| `engine_make` | `engine_make` | — | NO | Excluded from output tiers by design — ACCEPTED CONDITION |

### Feature Flag Fields (flow via feature system, not spec sheet)

| Lock Name | Registry Location | DealerInput Field | In `_FEATURE_MAP` | In Spec Tiers |
|-----------|------------------|-------------------|-------------------|--------------|
| `zero_tail_swing` | `feature_flags.zero_tail_swing` | `zero_tail_swing: bool` | YES | NO — feature only |
| `two_speed_travel` | `feature_flags.two_speed_travel_available` | `two_speed_travel: Optional[bool]` | YES | NO — feature only |

Both fields are accessible and wired through the listing text / feature list system. Neither surfaces on the spec sheet by design — consistent with the pattern established in `mini_ex_launch_lock_v1.md` line 60.

### DealerInput Core Output Fields (injected at output layer)

These fields do not exist in the OEM registry. They are confirmed by the dealer and injected into the output payload by `listing_pack_builder.py`.

| Field | Type | Confirm-Required | In Technical Tier | Label |
|-------|------|-----------------|-------------------|-------|
| `hours` | `int` | YES (required) | YES | "Hours" |
| `cab_type` | `Optional[str]` | NO (conditional) | YES | "Cab type" |
| `ac` | `Optional[bool]` | YES | YES | "A/C" |
| `heater` | `Optional[bool]` | YES | YES | "Heater" |
| `aux_hydraulics` | `Optional[bool]` | YES | YES | "Aux Hydraulics" |
| `coupler_type` | `Optional[str]` | NO (conditional) | YES | "Coupler" |
| `thumb_type` | `Optional[str]` | NO (conditional) | YES | "Thumb" |
| `blade_type` | `Optional[str]` | NO (conditional) | YES | "Blade" |
| `serial_number` | `Optional[str]` | NO (conditional) | YES | "Serial number" |

**Registry key translation:** `auxiliary_hydraulics` (registry) → `aux_hydraulics` (output layer). Translation performed at injection only. Registry key is not renamed.

---

## Dropdown Validators (DealerInput)

| Field | Allowed Values | Validator |
|-------|---------------|-----------|
| `coupler_type` | hydraulic / manual / pin-on | `coupler_type_valid` |
| `thumb_type` | hydraulic / manual / none | `thumb_type_valid` |
| `blade_type` | straight / angle / 6-way | `blade_type_valid` |
| `arm_length` | standard / long / extenda | `arm_length_valid` |
| `track_condition` | new / good / fair / worn | Form-layer only (backend free text for CTL compatibility) |

---

## Feature Fields (form-only, not injected to spec sheet)

| Field | DealerInput Type | In Form Config | In `_FEATURE_MAP` |
|-------|-----------------|----------------|-------------------|
| `arm_length` | `Optional[str]` | YES | NO |
| `two_speed_travel` | `Optional[bool]` | YES | YES |
| `pattern_changer` | `Optional[bool]` | YES | NO |
| `track_condition` | `Optional[str]` | YES | NO |
| `bucket_size_included` | `Optional[str]` | YES | NO |
| `zero_tail_swing` | `bool` | YES | YES |
| `rubber_tracks` | `bool` | YES | NO |

---

## Spec Display Tiers (`_MINI_EX_FIELDS`)

### Essential
`hours`, `net_hp`, `max_dig_depth`

### Standard
`hours`, `net_hp`, `cab_type`, `ac`, `heater`, `aux_hydraulics`, `coupler_type`, `thumb_type`, `blade_type`, `serial_number`, `max_dig_depth`, `hydraulic_flow_gpm`, `bucket_breakout_lb`, `tail_swing_type`

### Technical
All Standard fields plus: `max_dump_height_ft`, `max_reach_ft`, `hydraulic_pressure_standard_psi`, `travel_speed_high_mph`, `width_in`, `operating_weight_lb`, `fuel_type`

---

## Display Behavior

- Boolean fields (`ac`, `heater`, `aux_hydraulics`, `two_speed_travel`): render as "Yes" / "No"
- String fields (`cab_type`, `coupler_type`, `thumb_type`, `blade_type`): render as-is (lowercase — cosmetic, not a blocker)
- `cab_type`: title-cased via special handler in `_build_display_specs`
- Null fields: silently suppressed — no placeholders emitted
- `auxiliary_hydraulics` registry key: does not leak to output

---

## Accepted Conditions

These are not blockers and are not to be fixed:

1. `retractable_undercarriage` is null across all 63 records — field exists, never surfaces in output
2. `engine_make` is in registry but excluded from all output tiers by design
3. `cat_308_cr` is absent from registry — pre-existing gap, documented in `mini_ex_launch_lock_v1.md`
4. Coupler, thumb, and blade string values render lowercase — cosmetic only
5. Stale reference to `mtm_mini_ex_registry_v1.json` in module docstring of `mtm_registry_lookup.py` (line 11) — documentation artifact, no functional impact

---

## Runtime Verification

| Check | Result |
|-------|--------|
| `REGISTRY_FILENAMES[EQ_MINI_EX]` | `mtm_mini_ex_registry_v2_1.json` |
| File on disk | `registry/active/mtm_mini_ex_registry_v2_1.json` — EXISTS |
| Shadow versions in active/ | NONE — only one mini_ex file present |
| CTL spec sheet regression | PASS — all expected labels render |
| SSL spec sheet regression | PASS — all expected labels render |
| Null suppression | PASS — null fields produce no output rows |
| Raw key leakage | PASS — `auxiliary_hydraulics`, `engine_make` not in output |

---

## Statement of Lock

The Mini Excavator spec system is confirmed stable and locked for launch as of 2026-04-10.

This lock covers:
- DealerInput schema (field names, types, validators)
- Injection block (form → output payload)
- Spec display tiers (essential / standard / technical)
- Display label map
- Form configuration
- Feature map alignment
- CTL and SSL regression pass

The following are locked and must not be modified without a formal unlock pass:
- `_MINI_EX_FIELDS` in `mtm_service.py`
- Mini ex injection block in `listing_pack_builder.py`
- Mini ex entries in `dealer_input.py`, `app.py _FEATURE_CONFIG`, `listing_builder.py _FEATURE_MAP`

**MINI EX SPEC SYSTEM LOCKED FOR LAUNCH**
