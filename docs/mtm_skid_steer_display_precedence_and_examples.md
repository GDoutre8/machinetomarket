# MTM Skid Steer Display Precedence And Examples

This guide uses:
- [mtm_skid_steer_registry_v1_15.json](C:/mtm_mvp3/registry/mtm_skid_steer_registry_v1_15.json)
- [mtm_skid_steer_soft_spec_cleanup_v2.json](C:/mtm_mvp3/registry/mtm_skid_steer_soft_spec_cleanup_v2.json)

## Display Precedence
1. First use the exact raw registry value if present.
2. If the exact raw registry value is missing, use the soft-spec cleanup artifact.
3. If the soft-spec status is `suppressed`, omit the field entirely.

Display wording convention:
- Exact: show exact value only
- Soft: show range or class plus `Exact value not provided by OEM`
- Suppressed: omit the field and do not show placeholder text

## 1. Exact-Heavy Examples

### 1. bobcat_s650
- Displayed horsepower line: `70 HP`
- Displayed ROC line: `2,690 lb ROC`
- Displayed operating weight line: `7,582 lb operating weight`
- Displayed hinge pin line: `122 in hinge pin height`
- Notes:
  Horsepower exact from raw registry.
  ROC exact from raw registry.
  Operating weight exact from raw registry.
  Hinge pin exact from raw registry.

### 2. nh_l230
- Displayed horsepower line: `90 HP`
- Displayed ROC line: `3,200 lb ROC`
- Displayed operating weight line: `9,430 lb operating weight`
- Displayed hinge pin line: `132 in hinge pin height`
- Notes:
  Horsepower exact from raw registry.
  ROC exact from raw registry.
  Operating weight exact from raw registry.
  Hinge pin exact from raw registry.

### 3. cat_260
- Displayed horsepower line: `74 HP`
- Displayed ROC line: `3,160 lb ROC`
- Displayed operating weight line: `8,523 lb operating weight`
- Displayed hinge pin line: `132.5 in hinge pin height`
- Notes:
  Horsepower exact because raw registry value exists and takes precedence over soft artifact.
  ROC exact because raw registry value exists and takes precedence over soft artifact.
  Operating weight exact from raw registry.
  Hinge pin exact because raw registry value exists and takes precedence over soft artifact.

### 4. jd_312gr
- Displayed horsepower line: `46 HP`
- Displayed ROC line: `1,550 lb ROC`
- Displayed operating weight line: `5,905 lb operating weight`
- Displayed hinge pin line: `115.1 in hinge pin height`
- Notes:
  Horsepower exact because raw registry value exists and takes precedence over soft artifact.
  ROC exact because raw registry value exists and takes precedence over soft artifact.
  Operating weight exact from raw registry.
  Hinge pin exact because raw registry value exists and takes precedence over soft artifact.

## 2. Mixed Exact + Soft Examples

### 5. jd_318d
- Displayed horsepower line: `60 HP`
- Displayed ROC line: `1,425 lb ROC`
- Displayed operating weight line: `6,590 lb operating weight`
- Displayed hinge pin line: `~105-110 in hinge pin class`
  `Exact value not provided by OEM`
- Notes:
  Horsepower exact from raw registry.
  ROC exact from raw registry.
  Operating weight exact from raw registry.
  Hinge pin soft because raw value is missing and family evidence is strong.

### 6. jd_319d
- Displayed horsepower line: `65 HP`
- Displayed ROC line: `1,750 lb ROC`
- Displayed operating weight line: `6,945 lb operating weight`
- Displayed hinge pin line: `~105-110 in hinge pin class`
  `Exact value not provided by OEM`
- Notes:
  Horsepower exact from raw registry.
  ROC exact from raw registry.
  Operating weight exact from raw registry.
  Hinge pin soft because raw value is missing and family evidence is strong.

### 7. jd_334_p_tier
- Displayed horsepower line: `114.7 HP`
- Displayed ROC line: `2,100+ lb ROC class`
  `Exact value not provided by OEM`
- Displayed operating weight line: `10,264 lb operating weight`
- Displayed hinge pin line: `132 in hinge pin height`
- Notes:
  Horsepower exact from raw registry.
  ROC soft because the raw exact value is missing.
  Operating weight exact from raw registry.
  Hinge pin exact from raw registry.

### 8. bobcat_a770
- Displayed horsepower line: `~100-115 HP class`
  `Exact value not provided by OEM`
- Displayed ROC line: `3,325 lb ROC`
- Displayed operating weight line: `~6,000-8,000 lb operating weight class`
  `Exact value not provided by OEM`
- Displayed hinge pin line: `131 in hinge pin height`
- Notes:
  Horsepower soft because the raw exact value is missing.
  ROC exact from raw registry.
  Operating weight soft because the raw exact value is missing.
  Hinge pin exact from raw registry.

## 3. Suppressed-Field Examples

### 9. jd_323g
- Displayed horsepower line: `74 HP`
- Displayed ROC line: `2,150 lb ROC`
- Displayed operating weight line: `8,170 lb operating weight`
- Displayed hinge pin line: omitted
- Notes:
  Horsepower exact from raw registry.
  ROC exact from raw registry.
  Operating weight exact from raw registry.
  Hinge pin suppressed because raw value is missing and soft confidence is insufficient.

### 10. jd_320
- Displayed horsepower line: `62 HP`
- Displayed ROC line: `1,950 lb ROC`
- Displayed operating weight line: `6,435 lb operating weight`
- Displayed hinge pin line: omitted
- Notes:
  Horsepower exact from raw registry.
  ROC exact from raw registry.
  Operating weight exact from raw registry.
  Hinge pin suppressed because raw value is missing and soft confidence is insufficient.

### 11. gehl_5635sx_ii
- Displayed horsepower line: omitted
- Displayed ROC line: `~1,600-2,100 lb ROC class`
  `Exact value not provided by OEM`
- Displayed operating weight line: `~6,000-8,000 lb operating weight class`
  `Exact value not provided by OEM`
- Displayed hinge pin line: omitted
- Notes:
  Horsepower suppressed because the soft range was too broad under v2 policy.
  ROC soft because the raw exact value is missing but class evidence exists.
  Operating weight soft because the raw exact value is missing but class evidence exists.
  Hinge pin suppressed because family confidence is insufficient.

### 12. case_75xt
- Displayed horsepower line: `~100-100 HP class`
  `Exact value not provided by OEM`
- Displayed ROC line: `1,200+ lb ROC class`
  `Exact value not provided by OEM`
- Displayed operating weight line: `~6,000-8,000 lb operating weight class`
  `Exact value not provided by OEM`
- Displayed hinge pin line: omitted
- Notes:
  Horsepower soft because the raw exact value is missing and class evidence exists.
  ROC soft because the raw exact value is missing and class evidence exists.
  Operating weight soft because the raw exact value is missing and class evidence exists.
  Hinge pin suppressed because family confidence is insufficient.
