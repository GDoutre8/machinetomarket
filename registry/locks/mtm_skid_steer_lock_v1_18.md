# MTM SKID STEER REGISTRY — LOCK v1.18

Date: 2026-04-13

## Source
- registry/active/mtm_skid_steer_registry_v1_18.json

## Scope
- 270 skid steer loader records
- 10 manufacturers: Bobcat, Case, Caterpillar, Gehl, JCB, John Deere, Kubota, New Holland, Takeuchi, Wacker Neuson
- OEM-verified production registry

## Core Spec Standard (Locked)
- horsepower_hp
- rated_operating_capacity_lbs
- tipping_load_lbs
- operating_weight_lbs
- aux_flow_standard_gpm
- aux_flow_high_gpm
- lift_path
- travel_speed_high_mph
- travel_speed_low_mph

## Patch Log at Lock
1. ssl_tl_2x_roc_fill_v1 (2026-03-31) — tipping_load_lbs = ROC * 2 applied to 64 records
2. ssl_nh_engine_mfr_fill_v1 (2026-03-31) — NH engine_manufacturer = FPT applied to 27 records
3. ssl_jd_engine_mfr_fill_v1 (2026-03-31) — JD engine_manufacturer = Yanmar applied to 41 records
4. ssl_case_b_series_lift_path_fill_v1 (2026-03-31) — lift_path = radial on 5 Case B-series records
5. bobcat_ssl_oem_verification_pass_v1 (2026-04-13) — Full OEM verification from bobcat.com NA spec pages, 26 Bobcat SSL models corrected/promoted

## Validation Summary
- Pre-promotion audit: PASS
- JSON valid: PASS
- Record count confirmed: 270
- All HIGH-vs-HIGH conflicts resolved via OEM verification pass
- Zero records dropped from v1_16 baseline
- Metadata registry_name corrected from v1.17 to v1.18 at promotion

## New Records Added vs v1_16 (16)
Bobcat M-Series era-splits (14):
- bobcat_s510_mseries_pret4 / bobcat_s510_mseries_t4
- bobcat_s550_mseries_pret4 / bobcat_s550_mseries_t4
- bobcat_s570_mseries_pret4 / bobcat_s570_mseries_t4
- bobcat_s590_mseries_pret4 / bobcat_s590_mseries_t4
- bobcat_s650_mseries_pret4 / bobcat_s650_mseries_t4
- bobcat_s750_mseries_pret4 / bobcat_s750_mseries_t4
- bobcat_s770_mseries_pret4 / bobcat_s770_mseries_t4

New Holland additions (2):
- nh_l316
- nh_l318

## Era-Split Parent Records (Retired in place)
The following slugs are retained in the registry but marked RETIRED via in-record notes.
They route to their era-split children for active scoring use:
- bobcat_s510 -> s510_mseries_pret4 / s510_mseries_t4
- bobcat_s550 -> s550_mseries_pret4 / s550_mseries_t4
- bobcat_s570 -> s570_mseries_pret4 / s570_mseries_t4
- bobcat_s590 -> s590_mseries_pret4 / s590_mseries_t4

## OEM Verification Pass — Key Corrections Applied
Model corrections from bobcat.com NA spec pages (HIGH/locked):
- bobcat_s130: OW 4498 -> 5235
- bobcat_s150: OW 5208 -> 5935
- bobcat_s160: HP 56 -> 61, OW 5573 -> 5965
- bobcat_s175: OW 5889 -> 6220, lift_path radial -> vertical
- bobcat_s185: HP 58 -> 61, OW 6127 -> 6220
- bobcat_s205: HP 66 -> 61 (two-engine variant flagged MANUAL_REVIEW)
- bobcat_s220: HP 72 -> 75, lift_path radial -> vertical
- bobcat_s250: HP 72 -> 75, tipping 5661 -> 5000, OW 7825 -> 7723
- bobcat_s300: HP 78 -> 81, aux_flow_std 24.0 -> 20.7
- bobcat_s330: aux_flow_std/high populated HIGH
- bobcat_s450: HP 46 -> 49
- bobcat_s530: HP 46 -> 49
- bobcat_s570: OW 6594 -> 6395
- bobcat_s630: HP 70 -> 74.3, tipping 4650 -> 4360, OW 7385 -> 7707
- bobcat_s650: HP 70 -> 74, OW 7582 -> 8061
- bobcat_s750: OW 9963 -> 8730
- bobcat_s770: HP 88 -> 92, OW 10505 -> 9314
- bobcat_s86: HP 105.5 -> 110

NH OEM cleanup corrections (2026-04-12):
- nh_l320: Complete rebuild — engine was misidentified as FPT (actual: ISM N4LDI-TA-50SL); HP 74 -> 64, ROC 3200 -> 2000, OW 9259 -> 6470
- nh_l334: HP 90 -> 84 (net), gross 90 populated; OW 10120 -> 8900
- new_holland_l328: HP 74 -> 68 (net), gross 74 populated; lift_path filled vertical

## Retired Active File
- Old active: registry/active/mtm_skid_steer_registry_v1_16.json
- Archived to: registry/archive/skid_steer/mtm_skid_steer_registry_v1_16.json
- v1_16 was a strict subset of v1_18 — no data loss on retirement

## Status
LOCKED — DO NOT MODIFY CORE FIELDS IN THIS SNAPSHOT
