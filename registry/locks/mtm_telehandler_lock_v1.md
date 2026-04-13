# MTM TELEHANDLER REGISTRY — LOCK V1

Date: 2026-04-13

## Source
- registry/active/mtm_telehandler_registry_v3.json

## Scope
- 45 telehandler records
- OEM-validated production registry
- Safe for production spec injection

## Core Spec Standard (Locked)
- lift_capacity_lbs
- max_lift_height_ft
- max_forward_reach_ft
- lift_capacity_at_full_height_lbs
- horsepower_hp
- engine_manufacturer
- transmission_type
- operating_weight_lbs
- drive_type

## Validation Summary
- Post-cleanup validation: PASS
- Zero spec values changed during micro cleanup
- All audit blockers resolved
- JSON valid
- Encoding issues corrected
- Registry safe to lock

## OEM-backed confirmation set used in final validation
- SkyTrak 10054
- JLG G10-55A
- JCB 507-42
- Cat TL642
- Cat TL943
- Cat TL642D
- Gehl DL12-55
- SkyTrak 6034

## Notes
- Minor year/config drift normalized to canonical registry values where appropriate
- Compact telehandlers may use hydrostatic transmission
- Mid/full-size telehandlers may use powershift transmission
- This lock reflects production-ready registry state after metadata cleanup only

## Status
LOCKED — DO NOT MODIFY CORE FIELDS IN THIS SNAPSHOT
