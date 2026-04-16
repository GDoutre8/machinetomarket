# Mini Excavator Top Models Launch Lock — v1

**Date:** 2026-04-09
**Registry locked:** `registry/active/mtm_mini_ex_registry_v2_1.json`
**Runtime pointer:** `mtm_registry_lookup.py` → `REGISTRY_FILENAMES[EQ_MINI_EX]` = `mtm_mini_ex_registry_v2_1.json` ✓

---

## Locked Launch Candidate

| Field | Value |
|-------|-------|
| Registry file | `mtm_mini_ex_registry_v2_1.json` |
| Internal version | v2_migration |
| Record count | 63 |
| Last updated | 2026-03-29 |

---

## Top Models Audit — Results

| Make | Model | Slug | Core Fields | Missing | Status |
|------|-------|------|-------------|---------|--------|
| John Deere | 35G | jd_35g | 6/7 | retractable_undercarriage (null, not in output) | OUTPUT-ELIGIBLE |
| Kubota | KX040-4 | kubota_kx040_4 | 6/7 | retractable_undercarriage (null, not in output) | OUTPUT-ELIGIBLE |
| Caterpillar | 308 CR | cat_308_cr | 0/7 | ABSENT — not in registry | NOT READY |
| John Deere | 50G | jd_50g | 6/7 | retractable_undercarriage (null, not in output) | OUTPUT-ELIGIBLE |
| Kubota | KX057-6 | kubota_kx057_6 | 6/7 | retractable_undercarriage (null, not in output) | OUTPUT-ELIGIBLE |
| Bobcat | E50 | bobcat_e50 | 6/7 | retractable_undercarriage (null, not in output) | OUTPUT-ELIGIBLE |
| Caterpillar | 306 CR | cat_306_cr | 6/7 | retractable_undercarriage (null, not in output) | OUTPUT-ELIGIBLE |
| Kubota | U35-4 | kubota_u35_4 | 6/7 | retractable_undercarriage (null, not in output) | OUTPUT-ELIGIBLE |
| Kubota | U55-5 | kubota_u55_5 | 6/7 | retractable_undercarriage (null, not in output) | OUTPUT-ELIGIBLE |

---

## Core Field Values (post-audit, no changes made)

| Slug | engine_hp | operating_weight_lb | max_dig_depth_ft | zero_tail_swing | two_speed | retractable | engine_make |
|------|-----------|---------------------|-----------------|-----------------|-----------|-------------|-------------|
| jd_35g | 24.4 | 7,716 | 9.17 | false | true | null | Yanmar |
| kubota_kx040_4 | 31.5 | 8,930 | 9.97 | true | true | null | Kubota |
| cat_308_cr | — | — | — | — | — | — | — |
| jd_50g | 37.6 | 10,914 | 10.72 | false | true | null | Yanmar |
| kubota_kx057_6 | 42.6 | 12,787 | 11.37 | false | true | null | Kubota |
| bobcat_e50 | 39.4 | 10,935 | 10.75 | false | true | null | Kubota |
| cat_306_cr | 42.6 | 13,669 | 11.52 | false | true | null | Caterpillar |
| kubota_u35_4 | 24.4 | 8,800 | 9.75 | true | true | null | Kubota |
| kubota_u55_5 | 47.6 | 12,247 | 11.94 | true | true | null | Kubota |

*Note: `engine_hp` is stored as `horsepower_hp` in v2 registry; `operating_weight_lb` stored as `operating_weight_lbs`; `zero_tail_swing` and `two_speed_travel` are in `feature_flags`, not `specs`. All canonical names for the v2 schema.*

---

## Output Pipeline — Clean

All 8 present records produce clean, credible output:

- **hp, weight, dig depth**: All HIGH confidence, locked, core-tier fields → always surface
- **engine_make**: HIGH confidence, locked, provisional-tier → surfaces when core+supplemental count < 10
- **zero_tail_swing / two_speed_travel**: In `feature_flags`; not in `SPEC_TIERS_BY_TYPE` or `SPEC_LEVEL_FIELDS`. Not surfaced in spec output — consistent with design (same pattern as `engine_make` in SSL)
- **retractable_undercarriage**: null, LOW confidence, manual_review; NOT in any output tier → null silently skipped, no leakage
- **tail_swing_type**: In provisional tier of both `SPEC_TIERS_BY_TYPE` and `SPEC_LEVEL_FIELDS`. Values ("zero", "reduced", "conventional") are readable as-is. Not a blocker.
- **Boolean correctness**: `zero_tail_swing` and `two_speed_travel_available` are proper Python `bool` types for all 8 records. ✓

---

## Known Gap — cat_308_cr

`cat_308_cr` (Cat 308 Series, Top Models slot 3) is absent from the mini excavator registry. This is a pre-existing known gap, documented in `mtm_top_models_index_v1.json` with `production_status: staged_needs_lock` and the note: *"CONFIRMED MISSING: cat_308_cr absent from all registries. 8-tonne class falls between mini_ex (<6t) and full excavator (>18t) registry scopes."*

This gap predates the launch pass and cannot be resolved without a dedicated OEM research pass. It does not block launch of the 8 present records.

---

## Patches Applied

**NONE.** No registry corrections were required or applied.

---

## Runtime Pointer

`REGISTRY_FILENAMES[EQ_MINI_EX]` = `"mtm_mini_ex_registry_v2_1.json"` ✓ Already correct. No change needed.

---

## Final Decision

**MINI EX READY FOR LAUNCH** (8/9 models)

cat_308_cr remains absent — pre-existing known gap, does not block the 8 launch-ready records.
