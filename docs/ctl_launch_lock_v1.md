# CTL Launch Lock — v1

**Date:** 2026-04-09
**Status:** LOCKED FOR LAUNCH
**Registry:** `registry/active/mtm_ctl_registry_v1_20.json`
**Pipeline pointer updated:** `mtm_registry_lookup.py` line 149 → `mtm_ctl_registry_v1_20.json`

---

## Locked Launch Target Models (17)

| Slug | Make | Model | Tier | Final Status |
|------|------|-------|------|--------------|
| jd_333g | John Deere | 333G | A | PASS |
| bobcat_t770 | Bobcat | T770 | A | PASS |
| jd_325g | John Deere | 325G | A | PASS |
| cat_259d3 | Caterpillar | 259D3 | A | PASS |
| bobcat_t66 | Bobcat | T66 | A | PASS (HP suppressed by policy — see note) |
| jd_317g | John Deere | 317G | A | PASS |
| kubota_svl75_orig | Kubota | SVL75 | A | PASS (gen1 routing by design — see note) |
| cat_299d3 | Caterpillar | 299D3 | A | PASS |
| kubota_svl97 | Kubota | SVL97-2 | A | PASS |
| jd_331g | John Deere | 331G | B | PASS |
| cat_279d3 | Caterpillar | 279D3 | B | PASS |
| bobcat_t595 | Bobcat | T595 | B | PASS |
| bobcat_t650 | Bobcat | T650 | B | PASS |
| bobcat_t76 | Bobcat | T76 | B | PASS (HP suppressed by policy — see note) |
| takeuchi_tl8 | Takeuchi | TL8 | C | PASS |
| takeuchi_tl12v2 | Takeuchi | TL12V2 | C | PASS |
| kubota_svl97_3 | Kubota | SVL97-3 | C | PASS |

---

## v1_20 Patches Applied (from v1_19)

| Model | Field | Change | Reason |
|-------|-------|--------|--------|
| JD 325G | horsepower_hp | 74 → 66 | HP inversion — notes confirm 66 net SAE J1349 |
| Kubota SVL75 | hydraulic_flow_standard_gpm | REMOVED | Non-canonical dup of aux_flow_standard_gpm |
| Kubota SVL75 | hydraulic_flow_high_gpm | REMOVED | Non-canonical key, no high-flow available |
| Kubota SVL75 | width_over_tracks_in | REMOVED | Non-canonical dup of width_over_tires_in |
| Kubota SVL75 | height_to_hinge_pin_in | REMOVED | Non-canonical dup of bucket_hinge_pin_height_in |
| Kubota SVL75 | field_confidence / field_behavior stale entries | REMOVED | Matching metadata for removed non-canonical keys |
| Takeuchi TL8 | horsepower_hp | 74.3 → 74 | Float → integer format normalization |
| Takeuchi TL12V2 | horsepower_hp | 111.3 → 111 | Float → integer format normalization |

---

## Known Accepted Conditions (Not Blockers)

**T66 and T76 — HP suppressed:**
Both records carry `status=seed_only` with `horsepower_hp` field_behavior=`manual_review`.
The pipeline policy blocks manual_review fields from injection. Output renders 5–6 fields without HP.
This is a known product decision. HP will be surfaced once OEM confirmation is obtained and status is promoted.

**Kubota SVL75 gen1 routing:**
Bare "SVL75" query routes to `kubota_svl75` (SVL75-2, gen2) per MODEL_BRIDGE_ALIASES.
The gen1 record (`kubota_svl75_orig`) resolves via explicit `svl75original` or `SVL75 original` input.
This is intentional bridge behavior — no fix required.

**Kubota SVL97-3 — aux_flow_high_gpm absent:**
`high_flow_available=null` — field suppresses cleanly; no leak. Standard flow (23.8 gpm) renders correctly.

---

## Pipeline Fix Applied

**File:** `mtm_registry_lookup.py`
**Line 149** — REGISTRY_FILENAMES, EQ_CTL entry updated:
```
Before: "mtm_ctl_registry_v1_19.json"
After:  "mtm_ctl_registry_v1_20.json"
```
This was the only code change required for CTL launch.

---

## Acceptance Pass Summary

| Check | Result |
|-------|--------|
| Total models audited | 17 |
| PASS | 17 |
| FAIL | 0 |
| HOLD | 0 |
| Real blockers found | 1 (registry pointer — fixed) |
| Files changed | 2 (mtm_registry_lookup.py + this lock doc) |
| New registry version required | No — v1_20 is the locked launch candidate |

---

## Final Decision

**CTL v1_20 LOCKED FOR LAUNCH**

Registry: `registry/active/mtm_ctl_registry_v1_20.json`
Pipeline pointer: `mtm_registry_lookup.py` → `EQ_CTL: "mtm_ctl_registry_v1_20.json"`
Lock date: 2026-04-09
