# MTM Launch Rules

## Purpose
This file defines the hard rules for launch-critical registry work.
If any chat, Codex pass, Claude pass, or manual patch conflicts with this file, this file wins.

## Launch-Critical Scope
Tier A models are launch-critical and must be treated as locked infrastructure.

Current Tier A:
- jd_333g
- bobcat_t770
- jd_325g
- cat_259d3
- cat_308_cr
- kubota_kx040_4
- bobcat_e35
- jd_35g
- cat_262d3
- bobcat_t66
- jd_317g
- kubota_svl75
- cat_299d3
- kubota_svl97_2
- cat_303_cr

## Hard Rules
1. Do not silently modify any locked Tier A core field.
2. Do not rename Tier A models without explicit note in the fix log.
3. Do not use family placeholders for Tier A.
4. Do not allow LOW-confidence core specs for Tier A.
5. Do not allow missing core fields for Tier A.
6. Do not add non-canonical duplicate fields to Tier A records.
7. If lookup cannot confidently resolve a Tier A model, stop and report it.
8. If a spec is missing for a Tier A model, suppress output or block output. Never guess.

## Canonical Field Rules

### CTL / SSL canonical fields
- horsepower_hp
- horsepower_gross_hp
- operating_weight_lbs
- rated_operating_capacity_lbs
- tipping_load_lbs
- width_over_tires_in
- hinge_pin_height_in
- aux_flow_standard_gpm
- aux_flow_high_gpm
- travel_speed_high_mph

### Mini Excavator canonical fields
- horsepower_hp
- horsepower_gross_hp
- operating_weight_lbs
- max_dig_depth_ft
- machine_width_in
- zero_tail_swing
- tail_swing_type

## Launch Readiness Definitions
- READY: live record exists, lookup resolves correctly, core fields present, no blocking confidence/schema issues
- CONDITIONAL: live record exists but has a non-blocking issue
- BLOCKED: missing, mismatched, unresolved, or untrustworthy for launch use

## Lock Workflow Definitions
- PENDING: known issue state; nulls are allowed; not regression-enforced
- READY_FOR_LOCK: values verified and fields fully populated; passes audit; not regression-enforced yet
- LOCKED: values written to the lock file, fully populated, regression-enforced, immutable until explicitly reopened

## Required Workflow For Any Tier A Change
Audit -> Patch -> Verify active file -> Verify lookup path -> Update fix log -> Update lock file -> Run regression check

If any step is skipped, the fix is not complete.

## Regression Policy
If a locked Tier A field changes, becomes null, disappears, or is replaced by a non-canonical duplicate:
- fail the run
- do not proceed
- report exact model, field, and file

Null fields are never allowed in READY_FOR_LOCK or LOCKED.

## Priority Rule
For launch, a clean Tier A matters more than expanding breadth.
No new model work should take precedence over unresolved Tier A blockers.
