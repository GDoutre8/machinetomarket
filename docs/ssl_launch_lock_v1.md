# SSL Top 40 Launch Lock — v1

**Date:** 2026-04-09
**Registry locked:** `registry/active/mtm_skid_steer_registry_v1_16.json`
**Runtime pointer:** `mtm_registry_lookup.py` → `REGISTRY_FILENAMES[EQ_SKID_STEER]`

---

## Locked Launch Candidate

| Field | Value |
|-------|-------|
| Registry file | `mtm_skid_steer_registry_v1_16.json` |
| Internal version | 1.16 |
| Record count | 255 |
| Last updated | 2026-04-09 |
| Patch log | `registry/patch_logs/mtm_skid_steer_patch_log_v1_16.json` |

---

## Top 40 Skid Steer Acceptance — PASS

All 11 Top 40 skid steer models passed launch acceptance. 11/11 are 6/6 core-field complete.

| Slug | Resolved | Listing | Spec Snapshot | Spec Sheet | Dup Fields | Name Leakage | Null Leakage | Lift Path | Engine Make | Runtime | Status |
|------|----------|---------|---------------|------------|------------|--------------|--------------|-----------|-------------|---------|--------|
| case_sv280 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| kubota_ssv75 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| bobcat_s650 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| bobcat_s770 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| cat_262d3 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| jd_320g | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| jd_324g | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| bobcat_s510 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| bobcat_s550 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| nh_l228 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |
| nh_l230 | Y | Y | Y | Y | N | N | N | Y | N/A† | Y | PASS |

† `engine_make` is not in the SSL output tier (`SPEC_TIERS_BY_TYPE[skid_steer]` or `SPEC_LEVEL_FIELDS[skid_steer_loader]`). The field is correctly populated in the registry but not surfaced in user-facing output. This is consistent with CTL launch behavior (same `_SSL_CTL_FIELDS` definition). No wrong data is shown; no raw field name leaks. Accepted design.

---

## Blocker Found and Resolved

**BLOCKER: Runtime pointer was pointing to v1_15, not v1_16.**

- `mtm_registry_lookup.py` `REGISTRY_FILENAMES[EQ_SKID_STEER]` was set to `mtm_skid_steer_registry_v1_15.json`
- Without this fix, all v1_16 spec corrections (kubota_ssv75 OW/tipping, jd_324g tipping) would not be live
- Fixed in-place: pointer updated to `mtm_skid_steer_registry_v1_16.json`
- No registry file was created or modified — this was a runtime-only fix

---

## v1_16 Patch Summary (from audit pass)

| Slug | Field | Old | New | Type |
|------|-------|-----|-----|------|
| kubota_ssv75 | tipping_load_lbs | 3700 | 5380 | Spec correction |
| kubota_ssv75 | operating_weight_lbs | 6174 | 8157 | Spec correction (contradicted internal notes) |
| jd_324g | tipping_load_lbs | 4400 | 5380 | Spec correction (copy error from jd_320g) |
| bobcat_s770, jd_320g, case_sv280, jd_324g, bobcat_s550, nh_l228, nh_l230 | horsepower_hp / gross | various .0 floats | ints | Formatting normalization |

---

## Final Decision

**SSL v1_16 LOCKED FOR LAUNCH**
