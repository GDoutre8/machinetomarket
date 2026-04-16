# MTM Skid Steer Registry — State v1.13

## 1. Current Status
- Active registry file: `mtm_skid_steer_registry_v1_13.json`
- Total models: `255`
- Prior contradiction patch batch: `mtm_skid_steer_v1_12`
- Current fill batch: `mtm_skid_steer_v1_13`
- Validation: record count unchanged (`255`), JSON valid, `15` fields changed in `v1.13`, source registry untouched

## 2. What Was Patched in v1.12
### case_sr240
- `lift_path`: `vertical` → `radial`

### jd_318g
- `lift_path`: `radial` → `vertical`

### takeuchi_ts60v
- `lift_path`: `radial` → `vertical`

### case_85xt
- `bucket_hinge_pin_height_in`: `null` → `122.4`

## 3. What Was Filled in v1.13
- `bobcat_7753`: `bucket_hinge_pin_height_in`
- `bobcat_825`: `bucket_hinge_pin_height_in`
- `bobcat_843`: `bucket_hinge_pin_height_in`
- `bobcat_843b`: `bucket_hinge_pin_height_in`
- `bobcat_853`: `bucket_hinge_pin_height_in`
- `bobcat_873g`: `bucket_hinge_pin_height_in`
- `bobcat_980`: `bucket_hinge_pin_height_in`
- `bobcat_a770`: `bucket_hinge_pin_height_in`
- `bobcat_s220`: `bucket_hinge_pin_height_in`
- `bobcat_s250`: `bucket_hinge_pin_height_in`
- `bobcat_s330`: `bucket_hinge_pin_height_in`
- `bobcat_s530`: `engine_manufacturer`
- `bobcat_s62`: `operating_weight_lbs`
- `bobcat_s64`: `bucket_hinge_pin_height_in`
- `bobcat_s66`: `operating_weight_lbs`

## 4. Locked Rules
### Horsepower
- `horsepower_hp = NET horsepower only`
- `horsepower_gross_hp = GROSS horsepower only`
- Gross horsepower must never overwrite `horsepower_hp`

### Source Priority
1. OEM
2. Verified marketplace / authoritative dealer
3. Derived
4. Unknown

### Patch Philosophy
- Skip > guess
- Wrong patching is worse than incomplete data
- Only OEM-backed, single-value, non-config-dependent changes are SAFE

### Fill Philosophy
- Missing core specs may be filled only from OEM-backed, single-value, non-config-dependent sources
- No horsepower fill if net/gross standard is unclear
- No tipping/ROC fill from derived patterns

## 5. Known Deferred Work
- Broad derived-tipping cleanup is deferred
- Horsepower ambiguity cleanup is deferred except where direct net evidence exists
- Broad hinge-pin backfill beyond safe OEM batches is deferred
- Market-feature modeling is deferred
- Ratio-violation models without explicit replacement values are deferred

## 6. What Was NOT Done
- No horsepower normalization in `v1.13`
- No `tipping_load_lbs` changes in `v1.13`
- No `rated_operating_capacity_lbs` changes in `v1.13`
- No broad family-wide rewrites

## 7. Process Used
1. Audit registry
2. Identify safe contradictions
3. Patch to new version
4. Run OEM manufacturer fill pass
5. Create fill patch plan
6. Apply controlled fill batch
7. Validate output
8. Lock state in docs

## 8. Next Step
- Skid steer registry is stable at `v1.13`
- Do not reopen deferred items without new OEM-backed evidence
- Next work should be product-facing implementation or another tightly scoped manufacturer fill pass

This document is the source of truth for skid steer state.
Do not reopen decisions already captured here unless new source evidence contradicts them.

- Deferred items remain open only for future OEM-backed review, not speculative cleanup.
