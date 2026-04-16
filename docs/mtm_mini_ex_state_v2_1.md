# MTM Mini Excavator Registry — State v2.1

## 1. Current Status
- Active registry file: mtm_mini_ex_registry_v2_1.json
- Total models: 63
- Patch batch: mtm_mini_ex_v2_1
- Fields updated: 6
- Validation: record count unchanged (63), JSON valid, 6 fields changed, 3 models touched
- Models modified:
  - bobcat_e17
  - bobcat_e20
  - kubota_u17

---

## 2. What Was Patched
### bobcat_e17
- horsepower_hp: 13.5 → 15.0 (OEM Bobcat brochure; approved direct correction)
- operating_weight_lb: 3803 → 3774 (OEM brochure)
- max_dig_depth_ft: 7.18 → 7.32 (OEM brochure)

### bobcat_e20
- operating_weight_lb: 4188 → 4167 (OEM webpage)
- max_dig_depth_ft: 7.52 → 8.35 (OEM webpage)

### kubota_u17
- operating_weight_lb: 3682 → 3703 (OEM webpage)

---

## 3. Locked Rules (DO NOT CHANGE WITHOUT EXPLICIT DECISION)

### Horsepower
- horsepower_hp = NET horsepower only
- horsepower_gross_hp = GROSS horsepower only
- Gross horsepower must NEVER overwrite horsepower_hp

### Source Priority
1. OEM
2. Verified marketplace
3. Derived
4. Unknown

### Patch Philosophy
- Skip > guess
- Wrong patching is worse than incomplete data
- Only patch with explicit OEM backing

### Config-Dependent Fields
- Do NOT patch without confirmed configuration:
  - operating_weight_lb (if multiple OEM configs)
  - travel speed
  - width
  - hydraulic flow

---

## 4. Known Deferred Work (INTENTIONAL)

### Kubota Horsepower
- OEM provides gross horsepower only
- Net horsepower not confirmed
- Action:
  - Do NOT patch horsepower_hp
  - Store/verify in horsepower_gross_hp
  - Flag:
    - HP_GROSS_ONLY_SOURCE
    - HP_NET_MISSING
    - HP_NET_GROSS_CONFLICT

Affected models:
- kubota_u17
- kubota_u27_4
- kubota_kx033_4
- kubota_kx040_4
- kubota_kx080_4
- kubota_u35_4

---

### Takeuchi Models
- OEM evidence not fully verified
- Routed to manual review
- No patching performed

---

## 5. What Was NOT Done (By Design)
- No broad horsepower normalization
- No inferred or estimated values
- No config-dependent overrides
- No non-OEM corrections
- No registry-wide rewrites

---

## 6. Process Used (LOCKED WORKFLOW)

1. Audit registry
2. Identify mismatches
3. Filter to OEM-backed candidates
4. Create patch plan
5. Apply controlled patch to new version
6. Validate output

---

## 7. Next Step (DO NOT EXPAND MINI EX SCOPE)

- Mini Excavator registry is now stable at v2.1
- Do NOT run additional mini ex audit passes immediately
- Do NOT expand horsepower corrections

Next focus should be:
- another registry (CTL, SSL, etc.)
OR
- audit system improvements

---

FINAL RULE:
This document is the source of truth for Mini Ex state.
Do not re-open decisions already captured here unless new OEM evidence contradicts them.
- Deferred items remain open only for future OEM-backed review, not for speculative cleanup.

---
