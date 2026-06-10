# MTM Registry Validation Report

**Generated:** 2026-06-10T17:43:18Z
**Strict mode:** False
**Strict would fail:** **YES**

## Summary

| Severity | Count |
|----------|-------|
| ERROR | 17 |
| WARNING | 439 |
| INFO | 263 |
| **TOTAL** | 719 |

## Findings by Registry

| Registry | Findings |
|----------|----------|
| backhoe_loader | 1 |
| compact_track_loader | 296 |
| excavator | 15 |
| mini_excavator | 60 |
| scissor_lift | 2 |
| skid_steer | 266 |
| telehandler | 41 |
| wheel_loader | 38 |

## Findings by Rule

| Rule | Count |
|------|-------|
| R02_DEPRECATED_IN_ACTIVE | 2 |
| R04_SUCCESSOR_NOTE | 59 |
| R05_MISSING_MODEL_FAMILY | 105 |
| R06_ERA_SPLIT_NO_GENERATION | 5 |
| R06_ERA_SPLIT_NO_METADATA | 2 |
| R07_MISSING_SOURCE_REFS | 7 |
| R08_BANNED_SOURCE | 258 |
| R08_BANNED_SOURCE_IN_NOTES | 75 |
| R09_ROC_35PCT_CONVENTION | 19 |
| R09_ROC_35PCT_UNEXPECTED | 7 |
| R09_ROC_RATIO_ANOMALY | 15 |
| R10_STUB_LOCKED_FIELDS | 163 |
| R11_META_COUNT_MISMATCH | 2 |

## Registry Metadata

| Registry | File | Stated Count | Actual Count | Delta |
|----------|------|-------------|-------------|-------|
| backhoe_loader | mtm_backhoe_loader_registry_v1.json | 47 | 47 | +0 |
| boom_lift | mtm_boom_lift_registry_v1.json | 8 | 8 | +0 |
| compact_track_loader | mtm_ctl_registry_v1_32.json | 211 | 211 | +0 |
| dozer | mtm_dozer_registry_v1.json | 6 | 6 | +0 |
| excavator | mtm_excavator_registry_v2.json | 14 | 14 | +0 |
| mini_excavator | mtm_mini_ex_registry_v2_3.json | 77 | 77 | +0 |
| scissor_lift | mtm_scissor_lift_registry_v1.json | 20 | 20 | +0 |
| skid_steer | mtm_skid_steer_registry_v1_18.json | 275 | 276 | +1 |
| telehandler | mtm_telehandler_registry_v3.json | 72 | 72 | +0 |
| wheel_loader | mtm_wheel_loader_registry_v1_2.json | 25 | 27 | +2 |

## ERROR Findings (17)

### [R09_ROC_RATIO_ANOMALY] `compact_track_loader` / `bobcat_t190`
'bobcat_t190' tipping/ROC ratio 3.606 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 1900,
  "tipping_load": 6851,
  "ratio": 3.606,
  "manufacturer": "Bobcat"
}
```

### [R09_ROC_RATIO_ANOMALY] `compact_track_loader` / `bobcat_t595`
'bobcat_t595' tipping/ROC ratio 2.962 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 2200,
  "tipping_load": 6517,
  "ratio": 2.962,
  "manufacturer": "Bobcat"
}
```

### [R09_ROC_RATIO_ANOMALY] `compact_track_loader` / `toro_dingo_tx420`
'toro_dingo_tx420' tipping/ROC ratio 3.060 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 500,
  "tipping_load": 1530,
  "ratio": 3.06,
  "manufacturer": "Toro"
}
```

### [R09_ROC_RATIO_ANOMALY] `compact_track_loader` / `toro_dingo_tx425`
'toro_dingo_tx425' tipping/ROC ratio 3.060 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 500,
  "tipping_load": 1530,
  "ratio": 3.06,
  "manufacturer": "Toro"
}
```

### [R02_DEPRECATED_IN_ACTIVE] `compact_track_loader` / `toro_dingo_tx700`
Deprecated record 'toro_dingo_tx700' is present in active compact_track_loader registry and will be scored by lookup — causes ambiguous results
```json
{
  "status": "deprecated_ambiguous_parent",
  "registry_tier": "deprecated_ambiguous_parent"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `bobcat_s100`
'bobcat_s100' tipping/ROC ratio 1.640 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 1000,
  "tipping_load": 1640,
  "ratio": 1.64,
  "manufacturer": "Bobcat"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `bobcat_s185`
'bobcat_s185' tipping/ROC ratio 2.203 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 1850,
  "tipping_load": 4076,
  "ratio": 2.203,
  "manufacturer": "Bobcat"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `bobcat_s550_mseries_pret4`
'bobcat_s550_mseries_pret4' tipping/ROC ratio 2.229 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 1750,
  "tipping_load": 3900,
  "ratio": 2.229,
  "manufacturer": "Bobcat"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `bobcat_s550_mseries_t4`
'bobcat_s550_mseries_t4' tipping/ROC ratio 2.229 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 1750,
  "tipping_load": 3900,
  "ratio": 2.229,
  "manufacturer": "Bobcat"
}
```

### [R02_DEPRECATED_IN_ACTIVE] `skid_steer` / `bobcat_s850_doosan`
Deprecated record 'bobcat_s850_doosan' is present in active skid_steer registry and will be scored by lookup — causes ambiguous results
```json
{
  "status": "active_used_market",
  "registry_tier": "DEPRECATED"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `cat_236b`
'cat_236b' tipping/ROC ratio 2.293 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 1750,
  "tipping_load": 4012,
  "ratio": 2.293,
  "manufacturer": "Caterpillar"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `cat_252b`
'cat_252b' tipping/ROC ratio 2.246 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 2500,
  "tipping_load": 5615,
  "ratio": 2.246,
  "manufacturer": "Caterpillar"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `jd_240`
'jd_240' tipping/ROC ratio 2.267 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 1500,
  "tipping_load": 3400,
  "ratio": 2.267,
  "manufacturer": "John Deere"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `jd_260`
'jd_260' tipping/ROC ratio 2.417 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 2400,
  "tipping_load": 5800,
  "ratio": 2.417,
  "manufacturer": "John Deere"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `jd_314g`
'jd_314g' tipping/ROC ratio 1.534 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 1760,
  "tipping_load": 2700,
  "ratio": 1.534,
  "manufacturer": "John Deere"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `jd_330g`
'jd_330g' tipping/ROC ratio 1.767 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 3000,
  "tipping_load": 5300,
  "ratio": 1.767,
  "manufacturer": "John Deere"
}
```

### [R09_ROC_RATIO_ANOMALY] `skid_steer` / `takeuchi_ts80v`
'takeuchi_ts80v' tipping/ROC ratio 1.773 is outside both the 50% [1.8–2.2] and 35% [2.75–2.95] bands — likely a data entry error
```json
{
  "roc": 2200,
  "tipping_load": 3900,
  "ratio": 1.773,
  "manufacturer": "Takeuchi"
}
```

## WARNING Findings (439)

### [R08_BANNED_SOURCE] `backhoe_loader` / `cat_420f`
'cat_420f' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "Cat 420F Specalog (secondary source: ritchiespecs.com — not OEM confirmed)",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `asv_vt70`
'asv_vt70' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ASV VT-70 operating weight ~6,350 lb; RitchieSpecs range', 'patch': 'pass2_b1b2 2026-03-27'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t110`
'bobcat_t110' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/bobcat_t110 (1200mm); ritchiespecs.com (47.2 in)', 'patch': 'v1.19b_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `bobcat_t110`
Coverage stub 'bobcat_t110' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `bobcat_t140`
Coverage stub 'bobcat_t140' has 4 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "bucket_hinge_pin_height_in",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `bobcat_t180`
Coverage stub 'bobcat_t180' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t190`
'bobcat_t190' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/bobcat-t190",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t190`
'bobcat_t190' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2002-2010)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t190`
'bobcat_t190' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'Bobcat T190 operating weight ~7,920 lb; RitchieSpecs / Bobcat historical spec', 'patch': 'pass2_b1b2 2026-03-27'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t190`
'bobcat_t190' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'bcrentals.com Bobcat T190 OEM spec sheet PDF; skidsteerloaderspecs.com; ritchiespecs.com', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `bobcat_t200`
Coverage stub 'bobcat_t200' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t250`
'bobcat_t250' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/bobcat_t250 (1980mm); ritchiespecs.com (78 in)', 'patch': 'v1.19b_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t250`
'bobcat_t250' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/bobcat_t250 (3110mm); ritchiespecs.com consistent', 'patch': 'v1.19b_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `bobcat_t250`
Coverage stub 'bobcat_t250' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t300`
'bobcat_t300' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/bobcat-t300",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t300`
'bobcat_t300' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2004-2011)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t320`
'bobcat_t320' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/bobcat-t320",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t320`
'bobcat_t320' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2006-2012)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t450`
'bobcat_t450' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/bobcat-t450",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t450`
'bobcat_t450' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2024)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t550`
'bobcat_t550' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/bobcat-t550",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t550`
'bobcat_t550' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2024)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t595`
'bobcat_t595' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/bobcat-t595",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t595`
'bobcat_t595' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2021-2024)",
  "banned_source": "machinerytrader"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `bobcat_t630`
Coverage stub 'bobcat_t630' has 4 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "bucket_hinge_pin_height_in",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `bobcat_t650`
'bobcat_t650' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'bobcat.com non-current product page; ritchiespecs.com/model/bobcat-t650-multi-terrain-loader', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr270`
'case_tr270' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs Case TR270 (ritchiespecs.com/model/case-tr270-multi-terrain-loader)",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr310`
'case_tr310' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs Case CTL index â€” TR310 68 hp, ROC 3100 lbs, OW 8880 lbs",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr310`
'case_tr310' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs + LECTURA Specs + skidsteerloaderspecs.com TR310 â€” width_over_tires_in 74.3 in (consistent 3 aggregators); bucket_hinge_pin_height_in 122.8 in (3,120 mm from skidsteerloaderspecs.com)', 'patch': 'case_alpha_width_hinge_pin 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr320`
'case_tr320' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/case-tr320",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr320`
'case_tr320' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2019)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr320`
'case_tr320' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'LECTURA Specs + VeriTread + skidsteerloaderspecs.com TR320 â€” width_over_tires_in 76.0 in (majority; some sources cite 78 in â€” flagged); bucket_hinge_pin_height_in conflicting (124 vs 126.5 in) â€” skipped', 'patch': 'case_alpha_width_hinge_pin 2026-04-08'}",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr340`
'case_tr340' source_refs contains banned source 'heavyequipmentguide' — this source should not be used for spec values
```json
{
  "source_ref": "Case CE press release via heavyequipmentguide.ca (Feb 2015)",
  "banned_source": "heavyequipmentguide"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr340`
'case_tr340' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs Case CTL index â€” TR340 84 hp confirmed",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tr340`
'case_tr340' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com TR340 â€” width_over_tires_in 76.0 in, bucket_hinge_pin_height_in 126.5 in (3,215 mm); cross-checked RitchieSpecs and LECTURA Specs â€” consistent at 76 in', 'patch': 'case_alpha_width_hinge_pin 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tv370b`
'case_tv370b' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "width: heavy-spec.com 1930mm + Ritchie Bros 6.34ft + LECTURA 1.94m (secondary sources â€” no OEM PDF retrieved); hinge pin 131.1in: consistent across 4+ Luby authorized dealer listings",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tv380`
'case_tv380' source_refs contains banned source 'heavyequipmentguide' — this source should not be used for spec values
```json
{
  "source_ref": "Case CE press release via heavyequipmentguide.ca (Feb 2015)",
  "banned_source": "heavyequipmentguide"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tv380`
'case_tv380' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs Case CTL index â€” TV380 84 hp confirmed",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tv380`
'case_tv380' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com TV380 + RitchieSpecs TV380 â€” width_over_tires_in 76.0 in, bucket_hinge_pin_height_in 131.6 in (3,340 mm); LECTURA Specs consistent at 76 in', 'patch': 'case_alpha_width_hinge_pin 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `case_tv450`
'case_tv450' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'brokentractor.com TV450 specs â€” bucket_hinge_pin_height_in 131.6 in; ConstructionEquipmentGuide + LECTURA Specs â€” width_over_tires_in 76.5 in; consistent with TV450B (HIGH/locked)', 'patch': 'case_alpha_width_hinge_pin 2026-04-08'}",
  "banned_source": "lectura"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_239d`
Coverage stub 'cat_239d' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_247b`
Coverage stub 'cat_247b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_247b3`
'cat_247b3' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/cat_247b3 (1675mm OEM-format verbatim); tractorgearbox.com; ritchiespecs.com consistent', 'patch': 'v1.19c_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_247b3`
'cat_247b3' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/cat_247b3 (2860mm OEM-format verbatim); tractorgearbox.com; ritchiespecs.com consistent', 'patch': 'v1.19c_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_247b3`
Coverage stub 'cat_247b3' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_249d`
Coverage stub 'cat_249d' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_259b`
Coverage stub 'cat_259b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_259b3`
'cat_259b3' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/caterpillar-259b3",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_259b3`
'cat_259b3' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs CAT 259B3",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_259b3`
'cat_259b3' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2016)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_259b3`
'cat_259b3' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'Cat 259B3 operating weight ~9,015 lb; RitchieSpecs / Cat spec', 'patch': 'pass2_b1b2 2026-03-27'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_259b3`
'cat_259b3' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'holtcat.com 259B3 spec PDF; skidsteerloaderspecs.com/cat_259b3; ritchiespecs.com', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_277`
Coverage stub 'cat_277' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_277b`
Coverage stub 'cat_277b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_277c`
'cat_277c' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/caterpillar-277c",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_277c`
'cat_277c' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs CAT 277C",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_277c`
'cat_277c' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2007-2012)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_277c`
'cat_277c' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'macallisterrentals.com 277C-Series-Spec-Sheet.pdf (OEM dealer PDF); ritchiespecs.com/model/caterpillar-277c', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_277c`
'cat_277c' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/caterpillar-277c; CodeReady; CEG aggregators (3122mm)', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_279c`
'cat_279c' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/cat_279c (OEM-format verbatim: 78 in / 1980mm); ritchiespecs.com; codeready.org consistent', 'patch': 'v1.19c_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_279c`
'cat_279c' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/cat_279c (3130mm); ritchiespecs.com consistent', 'patch': 'v1.19c_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_279c`
Coverage stub 'cat_279c' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_279c2`
'cat_279c2' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/caterpillar-279c-series-2; budgetequipment.com spec page (1981mm); heavyhaulers.com consistent', 'patch': 'v1.19c_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_279c2`
'cat_279c2' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/caterpillar-279c-series-2; budgetequipment.com (3129mm); consistent with 279C', 'patch': 'v1.19c_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `cat_279c2`
Coverage stub 'cat_279c2' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_279d`
'cat_279d' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/caterpillar-279d",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_279d`
'cat_279d' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs CAT 279D",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_279d`
'cat_279d' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2020)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_287c`
'cat_287c' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/caterpillar-287c",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_287c`
'cat_287c' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs CAT 287C",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_287c`
'cat_287c' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2007-2012)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_287c`
'cat_287c' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/caterpillar-287c; CodeReady; CEG; heavy-spec.com (1981mm)', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_287c`
'cat_287c' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/caterpillar-287c; multiple aggregators (3233mm)', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_299d`
'cat_299d' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/caterpillar-299d",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_299d`
'cat_299d' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs CAT 299D",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `cat_299d`
'cat_299d' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2020)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `caterpillar_259d`
'caterpillar_259d' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/caterpillar-259d",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `caterpillar_259d`
'caterpillar_259d' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs CAT 259D",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `caterpillar_259d`
'caterpillar_259d' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2020)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `caterpillar_259d`
'caterpillar_259d' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/cat_259d; ritchiespecs.com/model/caterpillar-259d; Peterson CAT product page', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `caterpillar_259d`
'caterpillar_259d' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'skidsteerloaderspecs.com/cat_259d; ritchiespecs.com; CEG (3075mm)', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `caterpillar_289d`
'caterpillar_289d' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/caterpillar-289d",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `caterpillar_289d`
'caterpillar_289d' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs CAT 289D",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `caterpillar_289d`
'caterpillar_289d' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2020)",
  "banned_source": "machinerytrader"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `gehl_v330`
Coverage stub 'gehl_v330' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `gehl_vt210`
'gehl_vt210' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'Gehl OEM audit pass: escalate stub to OEM-confirmed values for VT210.', 'source': 'OEM: gehl.com/en-US/our-machines/compact-loaders/vt210 (Technical features section); Manitou tech sheet ref: views.manitou-group.com/machines/50841629; Travel speeds: machinerytrader.com June 2023 article (Ge",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `gehl_vt275`
'gehl_vt275' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'Gehl OEM audit pass: escalate stub to OEM-confirmed values for VT275.', 'source': 'OEM: gehl.com/en-US/our-machines/compact-loaders/vt275 (Technical features); Manitou tech sheet ref: views.manitou-group.com/machines/50841783; Travel speeds: machinerytrader.com June 2023 article', 'patch': ",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_215t`
'jcb_215t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-215t-multi-terrain-loader; codeready.org/ctls/jcb-ctls/jcb-215t; LECTURA Specs jcb-215t (1680mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_215t`
'jcb_215t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-215t-multi-terrain-loader; codeready.org/ctls/jcb-ctls/jcb-215t; dealer spec refs (companywrench.com JCB_215_SPECS.pdf, ~3023mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `jcb_215t`
Coverage stub 'jcb_215t' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_270t`
'jcb_270t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/jcb-270t",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_270t`
'jcb_270t' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs JCB 270T",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_270t`
'jcb_270t' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2016-2024)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_270t`
'jcb_270t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-270t-multi-terrain-loader; heavy-spec.com/multi-terrain-loader/jcb-270t; LECTURA Specs (1900mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_270t`
'jcb_270t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-270t-multi-terrain-loader; heavy-spec.com/multi-terrain-loader/jcb-270t; JCB dealer spec pages (3175mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_2ts_7t`
'jcb_2ts_7t' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'lectura-specs.com/en/model/construction-machinery/skid-steer-loaders-jcb/2ts-7t (1800mm transport width)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "lectura"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `jcb_2ts_7t`
Coverage stub 'jcb_2ts_7t' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_300t`
'jcb_300t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-300t-multi-terrain-loader; heavy-spec.com/multi-terrain-loader/jcb-300t; LECTURA Specs (1900mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_300t`
'jcb_300t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-300t-multi-terrain-loader; heavy-spec.com; JCB dealer pages (3175mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `jcb_300t`
Coverage stub 'jcb_300t' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_320t`
'jcb_320t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-320t-multi-terrain-loader; heavy-spec.com/multi-terrain-loader/jcb-320t (1900mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_320t`
'jcb_320t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-320t-multi-terrain-loader; inferred from JCB 270T/300T same-platform cross-validation (3175mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_3ts_8t`
'jcb_3ts_8t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-3ts-8t-skid-steer-loader; lectura-specs.com/en/model/jcb/3ts-8t (~1956mm)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jcb_3ts_8t`
'jcb_3ts_8t' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'ritchiespecs.com/model/jcb-3ts-8t-skid-steer-loader; multiple dealer listings (7ft 10in = 2388mm, boom retracted position)', 'patch': 'v1.19d_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `jcb_3ts_8t`
Coverage stub 'jcb_3ts_8t' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "travel_speed_high_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R09_ROC_35PCT_UNEXPECTED] `compact_track_loader` / `jd_317g`
'jd_317g' tipping/ROC ratio 2.856 — 35% convention for John Deere which is not a known 35%-OEM manufacturer; MTM normalization to 50% may have been skipped
```json
{
  "roc": 2125,
  "tipping_load": 6070,
  "ratio": 2.856,
  "manufacturer": "John Deere"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jd_323e`
'jd_323e' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/john-deere-323e",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jd_323e`
'jd_323e' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2013-2017)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jd_329e`
'jd_329e' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/john-deere-329e",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jd_329e`
'jd_329e' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2013-2017)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jd_329e`
'jd_329e' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'deere.com E-Series CTL spec sheet PDF; ritchiespecs.com/model/john-deere-329e (2000mm)', 'patch': 'v1.19_fill_pass 2026-04-08'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jd_333e`
'jd_333e' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/john-deere-333e",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `jd_333e`
'jd_333e' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2013-2017)",
  "banned_source": "machinerytrader"
}
```

### [R09_ROC_35PCT_UNEXPECTED] `compact_track_loader` / `jd_335_p_tier`
'jd_335_p_tier' tipping/ROC ratio 2.857 — 35% convention for John Deere which is not a known 35%-OEM manufacturer; MTM normalization to 50% may have been skipped
```json
{
  "roc": 4025,
  "tipping_load": 11500,
  "ratio": 2.857,
  "manufacturer": "John Deere"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `jd_335_p_tier`
Coverage stub 'jd_335_p_tier' has 21 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "bucket_hinge_pin_height_in",
    "emissions_tier",
    "engine_aspiration",
    "engine_cylinders",
    "engine_displacement_cu_in",
    "engine_manufacturer",
    "engine_model",
    "frame_size",
    "fuel_capacity_gal"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `kubota_svl110_3`
Coverage stub 'kubota_svl110_3' has 16 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_high_gpm",
    "aux_flow_standard_gpm",
    "engine_aspiration",
    "engine_cylinders",
    "engine_displacement_cu_in",
    "engine_manufacturer",
    "frame_size",
    "fuel_type",
    "horsepower_gross_hp",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `kubota_svl90`
'kubota_svl90' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/kubota-svl90",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `kubota_svl90`
'kubota_svl90' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2012-2019)",
  "banned_source": "machinerytrader"
}
```

### [R07_MISSING_SOURCE_REFS] `compact_track_loader` / `new_holland_c332`
Production record 'new_holland_c332' has no source_refs — OEM evidence chain is missing
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_UNEXPECTED] `compact_track_loader` / `new_holland_c332`
'new_holland_c332' tipping/ROC ratio 2.857 — 35% convention for New Holland which is not a known 35%-OEM manufacturer; MTM normalization to 50% may have been skipped
```json
{
  "roc": 2240,
  "tipping_load": 6400,
  "ratio": 2.857,
  "manufacturer": "New Holland"
}
```

### [R07_MISSING_SOURCE_REFS] `compact_track_loader` / `new_holland_c337`
Production record 'new_holland_c337' has no source_refs — OEM evidence chain is missing
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_UNEXPECTED] `compact_track_loader` / `new_holland_c337`
'new_holland_c337' tipping/ROC ratio 2.857 — 35% convention for New Holland which is not a known 35%-OEM manufacturer; MTM normalization to 50% may have been skipped
```json
{
  "roc": 2590,
  "tipping_load": 7400,
  "ratio": 2.857,
  "manufacturer": "New Holland"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `nh_c227`
'nh_c227' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-c227",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `nh_c232`
'nh_c232' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-c232",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `nh_c238`
'nh_c238' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-c238",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `compact_track_loader` / `nh_c245`
'nh_c245' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-c245",
  "banned_source": "ritchiespecs"
}
```

### [R09_ROC_35PCT_UNEXPECTED] `compact_track_loader` / `nh_c327`
'nh_c327' tipping/ROC ratio 2.857 — 35% convention for New Holland which is not a known 35%-OEM manufacturer; MTM normalization to 50% may have been skipped
```json
{
  "roc": 1890,
  "tipping_load": 5400,
  "ratio": 2.857,
  "manufacturer": "New Holland"
}
```

### [R09_ROC_35PCT_UNEXPECTED] `compact_track_loader` / `nh_c330`
'nh_c330' tipping/ROC ratio 2.857 — 35% convention for New Holland which is not a known 35%-OEM manufacturer; MTM normalization to 50% may have been skipped
```json
{
  "roc": 2100,
  "tipping_load": 6000,
  "ratio": 2.857,
  "manufacturer": "New Holland"
}
```

### [R09_ROC_35PCT_UNEXPECTED] `compact_track_loader` / `nh_c362`
'nh_c362' tipping/ROC ratio 2.880 — 35% convention for New Holland which is not a known 35%-OEM manufacturer; MTM normalization to 50% may have been skipped
```json
{
  "roc": 4340,
  "tipping_load": 12500,
  "ratio": 2.88,
  "manufacturer": "New Holland"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `takeuchi_tl8r`
Coverage stub 'takeuchi_tl8r' has 3 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_model",
    "rated_operating_capacity_lbs",
    "travel_speed_low_mph"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `compact_track_loader` / `toro_dingo_tx427w`
Coverage stub 'toro_dingo_tx427w' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `excavator` / `case_cx350d`
'case_cx350d' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs case-cx350d",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `cat_320el`
'cat_320el' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs cat-320el",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `cat_320gc`
'cat_320gc' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs cat-320gc",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `deere_210_p_tier`
'deere_210_p_tier' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs john-deere-210-p-tier",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `deere_210g_lc`
'deere_210g_lc' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs john-deere-210g-lc",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `komatsu_pc210lc_11`
'komatsu_pc210lc_11' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs komatsu-pc210lc-11",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `sany_sy215`
'sany_sy215' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs sany-sy215",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `sany_sy265`
'sany_sy265' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs sany-sy265",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `sany_sy365`
'sany_sy365' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs sany-sy365",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `volvo_ec350`
'volvo_ec350' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs volvo-ec350",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `volvo_ec350el`
'volvo_ec350el' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs volvo-ec350el",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `volvo_ec380`
'volvo_ec380' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs volvo-ec380",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `excavator` / `volvo_ec380el`
'volvo_ec380el' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs volvo-ec380el",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e10`
'bobcat_e10' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e10",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e17`
'bobcat_e17' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e17",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e20`
'bobcat_e20' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e20",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e26`
'bobcat_e26' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e26",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e32`
'bobcat_e32' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e32",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e35`
'bobcat_e35' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e35",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e42`
'bobcat_e42' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e42",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e50`
'bobcat_e50' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e50",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e55`
'bobcat_e55' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e55",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e60`
'bobcat_e60' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e60",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `bobcat_e85`
'bobcat_e85' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs bobcat-e85",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_301_7`
'cat_301_7' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs cat-301-7",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_301_8`
'cat_301_8' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs caterpillar-301-8",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_301_8`
'cat_301_8' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs caterpillar-301-8",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_302_7d_cr`
'cat_302_7d_cr' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs caterpillar-302-7d-cr",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_302_cr`
'cat_302_cr' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs cat-302-cr",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_303_cr`
'cat_303_cr' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs cat-303-cr",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_304_cr`
'cat_304_cr' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs cat-304-cr",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_305_5_e2_cr`
'cat_305_5_e2_cr' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs caterpillar-305-5-e2-cr",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_305_cr`
'cat_305_cr' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs cat-305-cr",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `cat_306_cr`
'cat_306_cr' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs cat-306-cr",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `jd_17g`
'jd_17g' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs john-deere-17g",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `jd_26g`
'jd_26g' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs john-deere-26g",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `jd_35g`
'jd_35g' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs john-deere-35g",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `jd_50g`
'jd_50g' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs john-deere-50g",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `jd_60g`
'jd_60g' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs john-deere-60g",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `jd_85g`
'jd_85g' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs john-deere-85g",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `kubota_kx033_4`
'kubota_kx033_4' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs kubota-kx033-4",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `kubota_kx040_4`
'kubota_kx040_4' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs kubota-kx040-4",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `kubota_kx057_6`
'kubota_kx057_6' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs kubota-kx057-6",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `kubota_kx080_4`
'kubota_kx080_4' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs kubota-kx080-4",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `kubota_u17`
'kubota_u17' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs kubota-u17",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `kubota_u27_4`
'kubota_u27_4' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs kubota-u27-4",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `kubota_u35_4`
'kubota_u35_4' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs kubota-u35-4",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `kubota_u55_5`
'kubota_u55_5' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs kubota-u55-5",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `takeuchi_tb210`
'takeuchi_tb210' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs takeuchi-tb210",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `takeuchi_tb216`
'takeuchi_tb216' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs takeuchi-tb216",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `takeuchi_tb219`
'takeuchi_tb219' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs takeuchi-tb219",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `takeuchi_tb230`
'takeuchi_tb230' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs takeuchi-tb230",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `takeuchi_tb260`
'takeuchi_tb260' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs takeuchi-tb260",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `takeuchi_tb290`
'takeuchi_tb290' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs takeuchi-tb290",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `yanmar_sv17`
'yanmar_sv17' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs yanmar-sv17",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `yanmar_sv26`
'yanmar_sv26' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs yanmar-sv26",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `yanmar_sv40`
'yanmar_sv40' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs yanmar-sv40",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `yanmar_sv60`
'yanmar_sv60' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs yanmar-sv60",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `yanmar_sv80`
'yanmar_sv80' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs yanmar-sv80",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `mini_excavator` / `yanmar_vio55`
'yanmar_vio55' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs yanmar-vio55",
  "banned_source": "ritchiespecs"
}
```

### [R11_META_COUNT_MISMATCH] `skid_steer` / `(meta)`
skid_steer _registry_meta.record_count=275 but actual record count is 276 (delta: +1) — meta was not updated atomically with a record add/remove
```json
{
  "stated_count": 275,
  "actual_count": 276,
  "delta": 1
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `bobcat_7753`
Coverage stub 'bobcat_7753' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `bobcat_a770`
Coverage stub 'bobcat_a770' has 4 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `bobcat_s100`
Coverage stub 'bobcat_s100' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R06_ERA_SPLIT_NO_METADATA] `skid_steer` / `bobcat_s510`
Era-split record 'bobcat_s510' has no year range AND no generation label — year-aware routing cannot function for this record
```json
{
  "registry_tier": "era_split_retired"
}
```

### [R06_ERA_SPLIT_NO_METADATA] `skid_steer` / `bobcat_s570`
Era-split record 'bobcat_s570' has no year range AND no generation label — year-aware routing cannot function for this record
```json
{
  "registry_tier": "era_split_retired"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1737`
Coverage stub 'case_1737' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1816b`
Coverage stub 'case_1816b' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1816c`
Coverage stub 'case_1816c' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1825`
Coverage stub 'case_1825' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1835`
Coverage stub 'case_1835' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1835c`
Coverage stub 'case_1835c' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1838`
Coverage stub 'case_1838' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1840`
Coverage stub 'case_1840' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1845`
Coverage stub 'case_1845' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_1845c`
Coverage stub 'case_1845c' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_high_gpm",
    "aux_flow_standard_gpm",
    "horsepower_hp",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_450`
Coverage stub 'case_450' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `case_465`
Coverage stub 'case_465' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R07_MISSING_SOURCE_REFS] `skid_steer` / `case_sr210b`
Production record 'case_sr210b' has no source_refs — OEM evidence chain is missing
```json
{
  "registry_tier": "production"
}
```

### [R07_MISSING_SOURCE_REFS] `skid_steer` / `case_sr240b`
Production record 'case_sr240b' has no source_refs — OEM evidence chain is missing
```json
{
  "registry_tier": "production"
}
```

### [R07_MISSING_SOURCE_REFS] `skid_steer` / `case_sr270b`
Production record 'case_sr270b' has no source_refs — OEM evidence chain is missing
```json
{
  "registry_tier": "production"
}
```

### [R07_MISSING_SOURCE_REFS] `skid_steer` / `case_sv280b`
Production record 'case_sv280b' has no source_refs — OEM evidence chain is missing
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `case_sv300`
'case_sv300' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/case-sv300-skid-steer-loader",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `case_sv300`
'case_sv300' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs Case SV300",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `case_sv300`
'case_sv300' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2013-2024)",
  "banned_source": "machinerytrader"
}
```

### [R07_MISSING_SOURCE_REFS] `skid_steer` / `case_sv340b`
Production record 'case_sv340b' has no source_refs — OEM evidence chain is missing
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_216`
'cat_216' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_216`
Coverage stub 'cat_216' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_216b`
Coverage stub 'cat_216b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_216b3`
Coverage stub 'cat_216b3' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_226`
'cat_226' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_226`
Coverage stub 'cat_226' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_226b`
'cat_226b' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "skidsteerloaderspecs.com â€” Cat 226B spec page; cross-referenced ritchiespecs.com. Both sources agree on all six fields.",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_226b`
Coverage stub 'cat_226b' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_226b2`
Coverage stub 'cat_226b2' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_226b3`
Coverage stub 'cat_226b3' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_226d`
Coverage stub 'cat_226d' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_228`
Coverage stub 'cat_228' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_232`
'cat_232' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_232`
Coverage stub 'cat_232' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_232b`
'cat_232b' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "skidsteerloaderspecs.com â€” Cat 232B spec page; cross-referenced ritchiespecs.com. Sources agree except tipping_load_lbs (see notes).",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_232b`
Coverage stub 'cat_232b' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_232b2`
Coverage stub 'cat_232b2' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_232d`
Coverage stub 'cat_232d' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_236`
'cat_236' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_236`
Coverage stub 'cat_236' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_236b`
'cat_236b' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "skidsteerloaderspecs.com â€” Cat 236B spec page; cross-referenced ritchiespecs.com. Both sources agree on all six fields.",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_236b`
Coverage stub 'cat_236b' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_236b2`
Coverage stub 'cat_236b2' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_236b3`
Coverage stub 'cat_236b3' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_236d`
Coverage stub 'cat_236d' has 10 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_242`
'cat_242' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_242`
Coverage stub 'cat_242' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_242b`
'cat_242b' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "skidsteerloaderspecs.com â€” Cat 242B spec page; cross-referenced ritchiespecs.com. Both sources agree on all six fields.",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_242b`
Coverage stub 'cat_242b' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_242b2`
Coverage stub 'cat_242b2' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_242b3`
Coverage stub 'cat_242b3' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_242d`
Coverage stub 'cat_242d' has 10 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_246`
'cat_246' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_246`
Coverage stub 'cat_246' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_246b`
'cat_246b' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "skidsteerloaderspecs.com â€” Cat 246B spec page; cross-referenced ritchiespecs.com. Both sources agree on all six fields.",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_246b`
Coverage stub 'cat_246b' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_246c`
Coverage stub 'cat_246c' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_246d`
Coverage stub 'cat_246d' has 10 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_248b`
Coverage stub 'cat_248b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_250`
Coverage stub 'cat_250' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_252`
Coverage stub 'cat_252' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_252b`
'cat_252b' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "skidsteerloaderspecs.com â€” Cat 252B spec page; cross-referenced ritchiespecs.com. Sources conflict on tipping_load_lbs and HP measurement type (see notes).",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_252b`
Coverage stub 'cat_252b' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "horsepower_hp",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_252b2`
Coverage stub 'cat_252b2' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_252b3`
Coverage stub 'cat_252b3' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_256c`
Coverage stub 'cat_256c' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_260`
Coverage stub 'cat_260' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_262`
Coverage stub 'cat_262' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `cat_262b`
'cat_262b' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_262b`
Coverage stub 'cat_262b' has 10 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_high_gpm",
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_262c`
Coverage stub 'cat_262c' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_262c2`
Coverage stub 'cat_262c2' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_262d`
Coverage stub 'cat_262d' has 10 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_268b`
Coverage stub 'cat_268b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_270`
Coverage stub 'cat_270' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_272c`
Coverage stub 'cat_272c' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_272d`
Coverage stub 'cat_272d' has 10 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "horsepower_hp",
    "lift_path",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_272d2`
Coverage stub 'cat_272d2' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_272d2_xhp`
Coverage stub 'cat_272d2_xhp' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `cat_272d_xhp`
Coverage stub 'cat_272d_xhp' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "lift_path"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `caterpillar_256d3`
'caterpillar_256d3' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/caterpillar-256d3-skid-steer-loader",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `caterpillar_256d3`
'caterpillar_256d3' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs CAT 256D3",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `caterpillar_256d3`
'caterpillar_256d3' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2020-2024)",
  "banned_source": "machinerytrader"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `gehl_4840`
Coverage stub 'gehl_4840' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `gehl_4840e`
Coverage stub 'gehl_4840e' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `gehl_5240`
Coverage stub 'gehl_5240' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `gehl_5240e`
Coverage stub 'gehl_5240e' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `gehl_5240e_p2`
Coverage stub 'gehl_5240e_p2' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `gehl_5635`
Coverage stub 'gehl_5635' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `gehl_5640`
Coverage stub 'gehl_5640' has 6 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "horsepower_hp",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `gehl_r105`
'gehl_r105' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/gehl-r105",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `gehl_r135`
'gehl_r135' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/gehl-r135",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `gehl_r165`
'gehl_r165' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/gehl-r165",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `gehl_r190`
'gehl_r190' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/gehl-r190",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `jcb_215`
'jcb_215' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/jcb-215",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `jcb_225`
'jcb_225' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/jcb-225",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `jcb_260`
'jcb_260' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/jcb-260",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `jcb_270`
'jcb_270' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/jcb-270-skid-steer-loader",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `jcb_270`
'jcb_270' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs JCB 270",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `jcb_270`
'jcb_270' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2016-2024)",
  "banned_source": "machinerytrader"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_240`
Coverage stub 'jd_240' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_250`
Coverage stub 'jd_250' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_260`
Coverage stub 'jd_260' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_270`
Coverage stub 'jd_270' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_280`
Coverage stub 'jd_280' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_312gr`
Coverage stub 'jd_312gr' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_313`
Coverage stub 'jd_313' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_314g`
Coverage stub 'jd_314g' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_315`
Coverage stub 'jd_315' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_316gr`
Coverage stub 'jd_316gr' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_317`
Coverage stub 'jd_317' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_318_p_tier`
Coverage stub 'jd_318_p_tier' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_318d`
Coverage stub 'jd_318d' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_318e`
Coverage stub 'jd_318e' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_319d`
Coverage stub 'jd_319d' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_319e`
Coverage stub 'jd_319e' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_320`
Coverage stub 'jd_320' has 9 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_high_gpm",
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "horsepower_hp",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_320d`
Coverage stub 'jd_320d' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_320e`
Coverage stub 'jd_320e' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_323d`
Coverage stub 'jd_323d' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_323g`
Coverage stub 'jd_323g' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_324e`
Coverage stub 'jd_324e' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_325`
Coverage stub 'jd_325' has 9 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_high_gpm",
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "horsepower_hp",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_326d`
Coverage stub 'jd_326d' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_326e`
Coverage stub 'jd_326e' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_328`
Coverage stub 'jd_328' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "horsepower_hp",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_328d`
Coverage stub 'jd_328d' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_328e`
Coverage stub 'jd_328e' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "bucket_hinge_pin_height_in",
    "engine_manufacturer",
    "lift_path",
    "operating_weight_lbs",
    "tipping_load_lbs",
    "travel_speed_low_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_332`
Coverage stub 'jd_332' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "horsepower_hp",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_332d`
Coverage stub 'jd_332d' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_332e`
Coverage stub 'jd_332e' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_334_p_tier`
Coverage stub 'jd_334_p_tier' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_3375`
Coverage stub 'jd_3375' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_375`
Coverage stub 'jd_375' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_4475`
Coverage stub 'jd_4475' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_5575`
Coverage stub 'jd_5575' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_575`
Coverage stub 'jd_575' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_6675`
Coverage stub 'jd_6675' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_675b`
Coverage stub 'jd_675b' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_7775`
Coverage stub 'jd_7775' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `jd_8875`
Coverage stub 'jd_8875' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l150`
Coverage stub 'nh_l150' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l160`
Coverage stub 'nh_l160' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l170`
Coverage stub 'nh_l170' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l175`
Coverage stub 'nh_l175' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l180`
Coverage stub 'nh_l180' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l185`
Coverage stub 'nh_l185' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l190`
Coverage stub 'nh_l190' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l213`
'nh_l213' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-l213-skid-steer-loader",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l213`
'nh_l213' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs New Holland L213",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l213`
'nh_l213' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2013-2024)",
  "banned_source": "machinerytrader"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l215`
Coverage stub 'nh_l215' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l216`
'nh_l216' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-l216-skid-steer-loader",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l216`
'nh_l216' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs New Holland L216",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l216`
'nh_l216' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (2013-2024)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l218`
'nh_l218' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-l218",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l220`
'nh_l220' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-l220",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l221`
Coverage stub 'nh_l221' has 17 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "bucket_hinge_pin_height_in",
    "dump_reach_in",
    "engine_displacement_cu_in",
    "engine_manufacturer",
    "engine_model",
    "fuel_capacity_gal",
    "horsepower_gross_hp",
    "horsepower_hp",
    "hydraulic_pressure_standard_psi"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l223`
'nh_l223' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-l223",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l225`
Coverage stub 'nh_l225' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l228`
'nh_l228' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-l228",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l230`
'nh_l230' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-l230",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `nh_l234`
'nh_l234' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/new-holland-l234",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_l250`
Coverage stub 'nh_l250' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_ls160`
Coverage stub 'nh_ls160' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_ls170`
Coverage stub 'nh_ls170' has 8 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "horsepower_hp",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_ls180`
Coverage stub 'nh_ls180' has 9 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_high_gpm",
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "horsepower_hp",
    "operating_weight_lbs",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs",
    "travel_speed_high_mph",
    "width_over_tires_in"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_ls180b`
Coverage stub 'nh_ls180b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_ls185b`
Coverage stub 'nh_ls185b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_ls190`
Coverage stub 'nh_ls190' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_ls190b`
Coverage stub 'nh_ls190b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_lt185b`
Coverage stub 'nh_lt185b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_lt190b`
Coverage stub 'nh_lt190b' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_lx485`
Coverage stub 'nh_lx485' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_lx565`
Coverage stub 'nh_lx565' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_lx665`
Coverage stub 'nh_lx665' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_lx865`
Coverage stub 'nh_lx865' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_lx885`
Coverage stub 'nh_lx885' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `nh_lx985`
Coverage stub 'nh_lx985' has 2 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "engine_manufacturer",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `takeuchi_ts50r`
Coverage stub 'takeuchi_ts50r' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `takeuchi_ts60v`
'takeuchi_ts60v' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/takeuchi-ts60v",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `takeuchi_ts80r2`
Coverage stub 'takeuchi_ts80r2' has 7 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "aux_flow_standard_gpm",
    "engine_manufacturer",
    "engine_model",
    "horsepower_hp",
    "hydraulic_pressure_standard_psi",
    "rated_operating_capacity_lbs",
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `takeuchi_ts80v`
'takeuchi_ts80v' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/takeuchi-ts80v",
  "banned_source": "ritchiespecs"
}
```

### [R10_STUB_LOCKED_FIELDS] `skid_steer` / `takeuchi_ts80v2`
Coverage stub 'takeuchi_ts80v2' has 1 locked field(s) — locked behavior implies OEM-verified data; contradicts stub status
```json
{
  "locked_fields": [
    "tipping_load_lbs"
  ],
  "registry_tier": "coverage_stub"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `wn_sw20`
'wn_sw20' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/wacker-neuson-sw20",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `skid_steer` / `wn_sw28`
'wn_sw28' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "ritchiespecs.com/model/wacker-neuson-sw28",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `caterpillar_tl642`
'caterpillar_tl642' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `caterpillar_tl642`
'caterpillar_tl642' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (6,000 lb confirmed)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `caterpillar_tl642d`
'caterpillar_tl642d' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader D-series listings",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `caterpillar_tl642d`
'caterpillar_tl642d' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `caterpillar_tl943`
'caterpillar_tl943' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `caterpillar_tl943`
'caterpillar_tl943' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (9,000 lb confirmed)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `gehl_dl12_55`
'gehl_dl12_55' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `gehl_dl12_55`
'gehl_dl12_55' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (12,000 lb confirmed)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `gehl_rs10_55`
'gehl_rs10_55' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs (14.0t = 30,865 lb confirmed)",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `gehl_rs10_55`
'gehl_rs10_55' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `gehl_rs10_55`
'gehl_rs10_55' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs Gehl RS10-55 (pump flow 39.9 gal/min, relief 3000 psi)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `gehl_rs5_19`
'gehl_rs5_19' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs (5.08t = 11,200 lb confirmed)",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `gehl_rs5_19`
'gehl_rs5_19' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `gehl_rs5_19`
'gehl_rs5_19' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs Gehl RS5-19 (pump flow 22 gal/min, relief 3350 psi)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `genie_gth_636`
'genie_gth_636' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs (7.7t = 16,975 lb confirmed)",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jcb_509_42`
'jcb_509_42' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs (11.5t = 25,353 lb confirmed)",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jcb_509_42`
'jcb_509_42' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (9,000 lb capacity confirmed)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g10_55a`
'jlg_g10_55a' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs (12.97t = 28,600 lb confirmed)",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g10_55a`
'jlg_g10_55a' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g12_55a`
'jlg_g12_55a' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g12_55a`
'jlg_g12_55a' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g5_18a`
'jlg_g5_18a' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs (3.17t = 6,988 lb confirmed)",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g5_18a`
'jlg_g5_18a' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g5_18a`
'jlg_g5_18a' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs JLG G5-18A (pump flow 19.1 gal/min, relief 3495.5 psi)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g6_42a`
'jlg_g6_42a' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs (8.94t = 19,710 lb confirmed)",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g6_42a`
'jlg_g6_42a' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g9_43a`
'jlg_g9_43a' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `telehandler` / `jlg_g9_43a`
'jlg_g9_43a' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listings (9,000 lb confirmed)",
  "banned_source": "machinerytrader"
}
```

### [R11_META_COUNT_MISMATCH] `wheel_loader` / `(meta)`
wheel_loader _registry_meta.record_count=25 but actual record count is 27 (delta: +2) — meta was not updated atomically with a record add/remove
```json
{
  "stated_count": 25,
  "actual_count": 27,
  "delta": 2
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `case_621g`
'case_621g' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation (OW, HP cross-reference)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `case_621g`
'case_621g' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs Case 621G (max system 3625 psi / pump 45.2 gal/min)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `case_721g`
'case_721g' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "RitchieSpecs Case 721G (ritchiespecs.com/model/case-721g-wheel-loader) — OEM spec basis",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `caterpillar_950gc`
'caterpillar_950gc' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `caterpillar_950gc`
'caterpillar_950gc' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs CAT 950 GC (implement max 4047 psi / pump 68 gal/min @ 2390 rpm)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `caterpillar_950k`
'caterpillar_950k' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `caterpillar_950k`
'caterpillar_950k' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs CAT 950K (implement max 3800 psi / pump 90 gal/min @ 2340 rpm)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `caterpillar_950m`
'caterpillar_950m' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `caterpillar_950m`
'caterpillar_950m' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs CAT 950M (implement max 4250 psi / pump 76 gal/min @ 2150 rpm)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `doosan_dl250`
'doosan_dl250' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `hyundai_hl940`
'hyundai_hl940' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `hyundai_hl940`
'hyundai_hl940' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs Hyundai HL940 (relief 2987 psi / pump 39 gal/min)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `hyundai_hl960`
'hyundai_hl960' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `john_deere_524_p_tier`
'john_deere_524_p_tier' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `john_deere_544_p_tier`
'john_deere_544_p_tier' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `john_deere_544k`
'john_deere_544k' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `john_deere_544kii`
'john_deere_544kii' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `john_deere_544kii`
'john_deere_544kii' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs JD 544K-II (251.7 bar â†’ 3650 psi unit-corrected / 50 gal/min)', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `john_deere_544l`
'john_deere_544l' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `komatsu_wa320_8`
'komatsu_wa320_8' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `komatsu_wa380_8`
'komatsu_wa380_8' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation (cross-reference)",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `komatsu_wa380_8`
'komatsu_wa380_8' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'SMS Equipment WA380-8 spec (24.5 MPa = 3555 psi / 54.15 gpm); CONFLICT with RitchieSpecs (4550/36.2) â€” manual_review recommended', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `komatsu_wa500_8`
'komatsu_wa500_8' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `volvo_l60h`
'volvo_l60h' source_refs contains banned source 'machinerytrader' — this source should not be used for spec values
```json
{
  "source_ref": "MachineryTrader listing aggregation",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `volvo_l70h`
'volvo_l70h' source_refs contains banned source 'lectura' — this source should not be used for spec values
```json
{
  "source_ref": "LECTURA Specs: Volvo L70H (2014-2018, 2019-2025)",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `volvo_l70h`
'volvo_l70h' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'RitchieSpecs / search (CLSS implement working pressure 3046 psi / max flow 40.7 gpm); manual_review recommended', 'patch': 'backfill_pass1 2026-03-26'}",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE] `wheel_loader` / `volvo_l70h`
'volvo_l70h' source_refs contains banned source 'ritchiespecs' — this source should not be used for spec values
```json
{
  "source_ref": "{'ref': 'Volvo L70H (Stage V) max speed ~35.7 km/h = 22.2 mph (4-speed powershift); RitchieSpecs/Volvo range', 'patch': 'pass2_b1b2 2026-03-27'}",
  "banned_source": "ritchiespecs"
}
```

## INFO Findings (263)

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `asv_rt120`
Production record 'asv_rt120' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `asv_rt40`
Production record 'asv_rt40' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `asv_rt50`
Production record 'asv_rt50' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `asv_rt65`
Production record 'asv_rt65' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `asv_vt70`
'asv_vt70' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "VT-70 replaced by VT-75 (Yanmar) in 2023; status = active_used_market due to strong used inventory"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t190`
Production record 'bobcat_t190' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `bobcat_t190`
'bobcat_t190' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "horsepower_hp HIGH / locked: 55.5 hp confirmed from Bobcat legacy documentation and ritchiespecs.",
  "banned_source": "ritchiespecs"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `bobcat_t300`
'bobcat_t300' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: Legacy large-frame CTL, produced approx. 2004-2011. Strong used-market listing volume. Predecessor to T750/T770 vertical-lift class in registry."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t300`
Production record 'bobcat_t300' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `bobcat_t300`
'bobcat_t300' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "horsepower_hp HIGH / locked: 72 hp confirmed from Bobcat legacy spec documentation and ritchiespecs.",
  "banned_source": "ritchiespecs"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `bobcat_t300`
'bobcat_t300' tipping/ROC ratio 2.878 — 35% OEM convention (policy: store as-is for Bobcat)
```json
{
  "roc": 3000,
  "tipping_load": 8633,
  "ratio": 2.878,
  "manufacturer": "Bobcat"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t320`
Production record 'bobcat_t320' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `bobcat_t550`
'bobcat_t550' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Bobcat)
```json
{
  "roc": 1995,
  "tipping_load": 5700,
  "ratio": 2.857,
  "manufacturer": "Bobcat"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t590`
Production record 'bobcat_t590' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t64`
Production record 'bobcat_t64' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `bobcat_t64`
'bobcat_t64' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Bobcat)
```json
{
  "roc": 2300,
  "tipping_load": 6571,
  "ratio": 2.857,
  "manufacturer": "Bobcat"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t650`
Production record 'bobcat_t650' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `bobcat_t650`
'bobcat_t650' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Bobcat)
```json
{
  "roc": 2570,
  "tipping_load": 7343,
  "ratio": 2.857,
  "manufacturer": "Bobcat"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `bobcat_t66`
'bobcat_t66' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "G-Series CTL â€” introduced ~2019/2020 as successor to T590 in compact segment"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t66`
Production record 'bobcat_t66' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t740`
Production record 'bobcat_t740' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `bobcat_t740`
'bobcat_t740' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Bobcat)
```json
{
  "roc": 3200,
  "tipping_load": 9143,
  "ratio": 2.857,
  "manufacturer": "Bobcat"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t750`
Production record 'bobcat_t750' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `bobcat_t76`
'bobcat_t76' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "G-Series CTL â€” introduced ~2019/2020 as successor to T650 in mid-frame segment"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t76`
Production record 'bobcat_t76' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `bobcat_t76`
'bobcat_t76' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Bobcat)
```json
{
  "roc": 2900,
  "tipping_load": 8285,
  "ratio": 2.857,
  "manufacturer": "Bobcat"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t770`
Production record 'bobcat_t770' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `bobcat_t770`
'bobcat_t770' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Bobcat)
```json
{
  "roc": 3475,
  "tipping_load": 9929,
  "ratio": 2.857,
  "manufacturer": "Bobcat"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t86`
Production record 'bobcat_t86' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `bobcat_t86`
'bobcat_t86' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Bobcat)
```json
{
  "roc": 3800,
  "tipping_load": 10857,
  "ratio": 2.857,
  "manufacturer": "Bobcat"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `bobcat_t870`
Production record 'bobcat_t870' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr270`
'case_tr270' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "horsepower_hp = 68 SAE J1349 net (RitchieSpecs confirmed); horsepower_gross_hp = 74 SAE J1995 gross",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr270`
'case_tr270' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "FPT F5HFL463 A*F001 confirmed via RitchieSpecs full spec page",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr270`
'case_tr270' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "aux_flow_high_gpm = 32.4 confirmed via RitchieSpecs; package_dependent (optional upgrade)",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr270`
'case_tr270' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "width_over_tires_in 66.2 = 5.52 ft converted from RitchieSpecs â€” manual_review pending OEM confirmation",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr310`
'case_tr310' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "horsepower_hp = 68 from RitchieSpecs index only â€” OEM spec sheet not located; manual_review",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr310`
'case_tr310' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "width_over_tires_in = 74.3 in â€” consistent across RitchieSpecs, LECTURA Specs, skidsteerloaderspecs.com; MEDIUM/manual_review pending OEM spec sheet",
  "banned_source": "ritchiespecs"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `case_tr310b`
'case_tr310b' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "width_over_tires_in = 74.3in â€” direct from CASE OEM spec sheet PDF, dimension S (over the track width), standard 400mm/15.75in track. bucket_hinge_pin_height_in = 125.1in â€” same OEM PDF, dimension"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr320`
'case_tr320' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "width_over_tires_in = 76.0 in â€” majority of aggregators (LECTURA, VeriTread, skidsteerloaderspecs.com); some sources cite 78 in (possible wider-track variant); MEDIUM/manual_review",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr340`
'case_tr340' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "horsepower_hp = 84 SAE J1349 net â€” confirmed via Case IH dealer sheet (63 kW) and RitchieSpecs; horsepower_gross_hp = 90 SAE J1995 gross confirmed via OEM press",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tr340`
'case_tr340' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "width_over_tires_in = 76.0 in â€” consistent across RitchieSpecs, LECTURA Specs, skidsteerloaderspecs.com; MEDIUM/manual_review pending OEM spec sheet",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tv370b`
'case_tv370b' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "width_over_tires_in = 76.0in (1930mm) â€” standard 450mm/17.7in track. MEDIUM/manual_review: no OEM spec sheet PDF retrieved directly; secondary sources (heavy-spec, Ritchie, LECTURA) converge on 1930mm. Recommend OEM PDF confirmation before locking. bucket_hinge_pin_height_in = 131.1in â€” HIGH/loc",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tv380`
'case_tv380' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "horsepower_hp = 84 SAE J1349 net confirmed via RitchieSpecs; horsepower_gross_hp = 90 SAE J1995 gross confirmed via OEM press",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tv380`
'case_tv380' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "width_over_tires_in = 76.0 in â€” consistent across RitchieSpecs, LECTURA Specs, skidsteerloaderspecs.com; MEDIUM/manual_review pending OEM spec sheet",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tv380`
'case_tv380' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "bucket_hinge_pin_height_in = 131.6 in (3,340 mm) â€” from skidsteerloaderspecs.com and RitchieSpecs; MEDIUM/manual_review pending OEM spec sheet",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `case_tv450`
'case_tv450' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "width_over_tires_in = 76.5 in â€” from ConstructionEquipmentGuide and LECTURA Specs; consistent with TV450B (76.5 in HIGH/locked); MEDIUM/manual_review pending OEM spec sheet",
  "banned_source": "lectura"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_239d3`
Production record 'cat_239d3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_249d3`
Production record 'cat_249d3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_255`
Production record 'cat_255' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_257d3`
Production record 'cat_257d3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `cat_259b3`
'cat_259b3' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 259B3 is the B3-series predecessor to the 259D3 (in registry). Tier 4 Interim era. Significant used-market volume from fleet units."
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `cat_259d`
'cat_259d' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "259D is D-series predecessor to 259D3. Same C3.3B engine, same frame. Hydraulics: High Flow (not XPS) — both standard and high flow run at same 3335 psi, only flow differs (20 vs 30 gpm)."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_259d3`
Production record 'cat_259d3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_265`
Production record 'cat_265' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_275`
Production record 'cat_275' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_275_xe`
Production record 'cat_275_xe' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `cat_277c`
'cat_277c' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 277C is the C-series predecessor to the 279D3 (in registry). Pre-Tier 4 mid-frame vertical lift. Strong used-market presence from long-running fleet units."
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `cat_279c`
'cat_279c' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "[v1.19c fill pass] CAT 279C width 78.0 in (1980 mm). Multiple secondary aggregators report OEM-format spec: Width w/o Bucket Std Track 78 in (1980mm). MEDIUM/manual_review. Note: 279D (successor) in r"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `cat_279d`
'cat_279d' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 279D is the D-series predecessor to the 279D3 (in registry). Confirmed distinct listing population on MachineryTrader. Do not conflate with 279D3 (updated engine, revised hydraulics)."
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `cat_279d`
'cat_279d' notes mention banned source 'machinerytrader' — verify values were not derived from this source
```json
{
  "note_excerpt": "GENERATION: 279D is the D-series predecessor to the 279D3 (in registry). Confirmed distinct listing population on MachineryTrader. Do not conflate with 279D3 (updated engine, revised hydraulics).",
  "banned_source": "machinerytrader"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_279d3`
Production record 'cat_279d3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_285_xe`
Production record 'cat_285_xe' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `cat_287c`
'cat_287c' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 287C is the C-series predecessor to the 289D3 (in registry). Pre-Tier 4 large-frame vertical lift. Confirmed distinct listing population on MachineryTrader."
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `cat_287c`
'cat_287c' notes mention banned source 'machinerytrader' — verify values were not derived from this source
```json
{
  "note_excerpt": "GENERATION: 287C is the C-series predecessor to the 289D3 (in registry). Pre-Tier 4 large-frame vertical lift. Confirmed distinct listing population on MachineryTrader.",
  "banned_source": "machinerytrader"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_289d3`
Production record 'cat_289d3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_297d2_xhp`
Production record 'cat_297d2_xhp' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `cat_299d`
'cat_299d' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 299D is the D-series predecessor to the 299D3 (in registry). High-volume used-market listing population. Do not conflate with 299D3 (revised engine, updated hydraulics)."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_299d2`
Production record 'cat_299d2' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_299d2_xhp`
Production record 'cat_299d2_xhp' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_299d3`
Production record 'cat_299d3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_299d3_xe`
Production record 'cat_299d3_xe' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_299d3_xe_land_management`
Production record 'cat_299d3_xe_land_management' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `cat_299d_xhp`
Production record 'cat_299d_xhp' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `caterpillar_259d`
'caterpillar_259d' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 259D is the D-series predecessor to the 259D3 (in registry). D-series uses CAT C2.8T engine; D3-series updated to C2.8T with revised emissions calibration. Do not conflate with 259D3 or le"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `caterpillar_259d`
'caterpillar_259d' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lbs HIGH / locked: 8,560 lb consistent across multiple sources (ritchiespecs, LECTURA) for 259D base unit.",
  "banned_source": "ritchiespecs"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `caterpillar_289d`
'caterpillar_289d' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 289D is the D-series predecessor to the 289D3 (in registry). Uses CAT C3.3B engine; D3-series updated to C3.3B DIT. Do not conflate with 289D3 or legacy 289C."
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `caterpillar_289d`
'caterpillar_289d' notes mention banned source 'machinerytrader' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lbs HIGH / locked: 10,260 lb consistent across ritchiespecs, LECTURA, and MachineryTrader for 289D base unit.",
  "banned_source": "machinerytrader"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_rt105`
Production record 'gehl_rt105' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_rt135`
Production record 'gehl_rt135' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_rt165`
Production record 'gehl_rt165' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_rt195`
Production record 'gehl_rt195' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_rt210`
Production record 'gehl_rt210' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_rt215`
Production record 'gehl_rt215' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_rt250`
Production record 'gehl_rt250' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_rt255`
Production record 'gehl_rt255' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_vt210`
Production record 'gehl_vt210' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_vt230`
Production record 'gehl_vt230' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_vt275`
Production record 'gehl_vt275' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `gehl_vt320`
Production record 'gehl_vt320' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `jcb_215t`
'jcb_215t' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "[v1.19d fill pass] JCB 215T width 66.1 in (1680 mm). Multiple secondary aggregators consistent (RitchieSpecs, CodeReady, LECTURA). MEDIUM: confirm from jcb.com OEM spec PDF before lock. v1.19d fill pass 2026-04-08.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `jcb_270t`
'jcb_270t' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "[v1.19d fill pass] JCB 270T width 74.8 in (1900 mm). Large-platform machine confirmed across RitchieSpecs, heavy-spec.com, LECTURA. MEDIUM: confirm from jcb.com OEM spec PDF before lock. v1.19d fill pass 2026-04-08.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `jcb_2ts_7t`
'jcb_2ts_7t' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "[v1.19d fill pass] JCB 2TS-7T width 70.9 in (1800 mm). Single LECTURA source (transport width). MEDIUM: may reflect bucket/transport width rather than over-track width â€” confirm from jcb.com Teleskid OEM spec sheet before lock. v1.19d fill pass 2026-04-08.",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `compact_track_loader` / `jcb_300t`
'jcb_300t' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "[v1.19d fill pass] JCB 300T width 74.8 in (1900 mm). Same large platform as 270T; confirmed across RitchieSpecs, heavy-spec.com, LECTURA. MEDIUM: confirm from jcb.com OEM spec PDF before lock. v1.19d fill pass 2026-04-08.",
  "banned_source": "ritchiespecs"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jcb_320t`
Production record 'jcb_320t' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jd_317g`
Production record 'jd_317g' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jd_319g`
Production record 'jd_319g' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `jd_323e`
'jd_323e' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 323E is the E-series predecessor to the 323G (in registry). Tier 4 Interim era. Mid-frame, radial lift. Significant used-market listing volume."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jd_325g`
Production record 'jd_325g' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `jd_329e`
'jd_329e' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 329E is the E-series predecessor to the 329G (in registry). Tier 4 Interim era. Large-frame, vertical lift. Strong used-market listing volume."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jd_329g`
Production record 'jd_329g' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jd_331_ptier`
Production record 'jd_331_ptier' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jd_331g`
Production record 'jd_331g' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jd_333_ptier`
Production record 'jd_333_ptier' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `jd_333e`
'jd_333e' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: 333E is the E-series predecessor to the 333G (in registry). Tier 4 Interim era. Large-frame, vertical lift. Top of the E-series CTL lineup. Strong used-market listing volume."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `jd_333g`
Production record 'jd_333g' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `jd_335g`
'jd_335g' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "[jd_ctl_oem_patch 2026-04-26] TOMBSTONED: No production John Deere 335G CTL exists. Successor model is the 335 P-Tier (see jd_335_p_tier). JD G-Series lineup ends at 333G. Record retained as tombstone"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl50x`
Production record 'kubota_svl50x' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl65`
Production record 'kubota_svl65' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl65_2s`
Production record 'kubota_svl65_2s' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `kubota_svl65_orig`
'kubota_svl65_orig' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "First-generation SVL65 (Tier 3 / pre-Tier4). Replaced by SVL65-2 in April 2019. Radial lift. No DEF. OEM documentation no longer hosted by Kubota USA. All specs reconstructed from third-party aggregat"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl65_orig`
Production record 'kubota_svl65_orig' is missing model_family
```json
{
  "registry_tier": "production_candidate"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl75`
Production record 'kubota_svl75' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `kubota_svl75_3`
'kubota_svl75_3' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Engine: V3307-TE5A â€” Tier 5 / Stage V variant of the V3307 engine family. Replaces V3307-CR-TE4 used in SVL75-2."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl75_3`
Production record 'kubota_svl75_3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `kubota_svl75_orig`
'kubota_svl75_orig' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "First-generation SVL75 (Tier 3 engine V3307-TE3). Vertical lift. No DEF. No high-flow option. Replaced by SVL75-2 ~2016. Source: skidsteerloaderspecs.com cross-referenced with OEM-era dealer sheets."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl75_orig`
Production record 'kubota_svl75_orig' is missing model_family
```json
{
  "registry_tier": "production_candidate"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `kubota_svl90`
'kubota_svl90' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: SVL90 is the predecessor to the SVL95-2S (in registry). Discontinued approx. 2019. Mid-frame, vertical lift. Strong used-market listing volume in 2012-2019 inventory window."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl90_2`
Production record 'kubota_svl90_2' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl95`
Production record 'kubota_svl95' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl95_2`
Production record 'kubota_svl95_2' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl97`
Production record 'kubota_svl97' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `kubota_svl97_3`
Production record 'kubota_svl97_3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `nh_c227`
Production record 'nh_c227' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `nh_c232`
Production record 'nh_c232' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `nh_c238`
Production record 'nh_c238' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `nh_c245`
Production record 'nh_c245' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `nh_c327`
Production record 'nh_c327' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `nh_c330`
Production record 'nh_c330' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `nh_c345`
Production record 'nh_c345' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `nh_c362`
Production record 'nh_c362' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl10`
'takeuchi_tl10' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "CORRECTION: lift_path changed from 'vertical' to 'radial' — base TL10 uses radial lift; TL10V2 is the vertical-lift successor."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl10`
Production record 'takeuchi_tl10' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl10v2`
'takeuchi_tl10v2' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Vertical lift redesign replacing radial TL10. Switched from Interim T4 to Final T4. Downsized from 3.8L to 3.3L engine vs predecessor."
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl10v2`
Production record 'takeuchi_tl10v2' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl11r3`
Production record 'takeuchi_tl11r3' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl12`
Production record 'takeuchi_tl12' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl12r2`
'takeuchi_tl12r2' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "replaces_model: TL12"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl12r2`
Production record 'takeuchi_tl12r2' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl12v2`
'takeuchi_tl12v2' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "replaces_model: TL12"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl12v2`
Production record 'takeuchi_tl12v2' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl150`
Production record 'takeuchi_tl150' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl230`
'takeuchi_tl230' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: TL230 is a legacy small-frame CTL, produced approx. 2003-2012. Predecessor to TL240 and TL6/TL6R class. Strong legacy used-market presence."
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl240`
'takeuchi_tl240' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: TL240 is the successor to the TL230 and predecessor to the TL6/TL6R class. Tier 3 era (2009-2016 per registry)."
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl6r`
'takeuchi_tl6r' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "replaces_model: null (TL6R is the first model in TL6 radial CTL family)"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl6r`
Production record 'takeuchi_tl6r' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl8`
'takeuchi_tl8' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "replaces_model: TL230 Series 2"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl8`
Production record 'takeuchi_tl8' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl8r`
'takeuchi_tl8r' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Matching logic: route 'TL8R' queries to takeuchi_tl8 (base radial model) or takeuchi_tl8r2 (R2-gen successor) — both carry TL8R in their alias_hints."
}
```

### [R04_SUCCESSOR_NOTE] `compact_track_loader` / `takeuchi_tl8r2`
'takeuchi_tl8r2' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "replaces_model: TL8"
}
```

### [R05_MISSING_MODEL_FAMILY] `compact_track_loader` / `takeuchi_tl8r2`
Production record 'takeuchi_tl8r2' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx1000n`
'toro_dingo_tx1000n' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 1000,
  "tipping_load": 2857,
  "ratio": 2.857,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx1000w`
'toro_dingo_tx1000w' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 1075,
  "tipping_load": 3071,
  "ratio": 2.857,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx413`
'toro_dingo_tx413' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 420,
  "tipping_load": 1200,
  "ratio": 2.857,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx427n`
'toro_dingo_tx427n' tipping/ROC ratio 2.860 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 535,
  "tipping_load": 1530,
  "ratio": 2.86,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx427w`
'toro_dingo_tx427w' tipping/ROC ratio 2.860 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 535,
  "tipping_load": 1530,
  "ratio": 2.86,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx525n`
'toro_dingo_tx525n' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 553,
  "tipping_load": 1580,
  "ratio": 2.857,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx525w`
'toro_dingo_tx525w' tipping/ROC ratio 2.767 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 553,
  "tipping_load": 1530,
  "ratio": 2.767,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx700n`
'toro_dingo_tx700n' tipping/ROC ratio 2.856 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 764,
  "tipping_load": 2182,
  "ratio": 2.856,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_tx700w`
'toro_dingo_tx700w' tipping/ROC ratio 2.856 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 764,
  "tipping_load": 2182,
  "ratio": 2.856,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_txl2000`
'toro_dingo_txl2000' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 2000,
  "tipping_load": 5715,
  "ratio": 2.857,
  "manufacturer": "Toro"
}
```

### [R09_ROC_35PCT_CONVENTION] `compact_track_loader` / `toro_dingo_txl2000t`
'toro_dingo_txl2000t' tipping/ROC ratio 2.857 — 35% OEM convention (policy: store as-is for Toro)
```json
{
  "roc": 2000,
  "tipping_load": 5715,
  "ratio": 2.857,
  "manufacturer": "Toro"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `excavator` / `cat_308_cr`
'cat_308_cr' notes mention banned source 'machinerytrader' — verify values were not derived from this source
```json
{
  "note_excerpt": "SCOPE EXCEPTION: Cat 308 is the only sub-18t machine in this registry. Phase 1A scope was >=18 metric tons. Cat 308 operating weight ~8 metric tons (17,640 lb). Added because it is a Top50 slot and has high used-market volume per EDA / MachineryTrader.",
  "banned_source": "machinerytrader"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `excavator` / `sany_sy215`
'sany_sy215' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "NOTE: All MEDIUM-confidence values sourced from RitchieSpecs and IronPlanet listings; require OEM primary source confirmation before behavior can be upgraded to locked.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `mini_excavator` / `bobcat_e10`
'bobcat_e10' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "SOURCE: operating_weight_lbs 2,593 lbs confirmed per Bobcat OEM and RitchieSpecs.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `mini_excavator` / `cat_301_8`
'cat_301_8' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "SOURCE: horsepower_gross_hp 18.4 HP confirmed per RitchieSpecs and LECTURA. horsepower_hp 17.4 HP net is MEDIUM â€” derived from Cat C1.1 standard derating.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `mini_excavator` / `cat_301_8`
'cat_301_8' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "SOURCE: Cat C1.1 (Mitsubishi-sourced) 3-cyl NA 68 cu in Tier 4 Final confirmed per RitchieSpecs.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `mini_excavator` / `cat_302_7d_cr`
'cat_302_7d_cr' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "SOURCE: horsepower_gross_hp 24.3 HP confirmed per RitchieSpecs. horsepower_hp 23.5 HP net is MEDIUM â€” Yanmar 3TNV76 net derived from standard derating; OEM published gross only.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `mini_excavator` / `cat_302_7d_cr`
'cat_302_7d_cr' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "SOURCE: Yanmar 3TNV76 3-cyl NA 79 cu in Tier 4 Interim confirmed per RitchieSpecs engine cross-reference.",
  "banned_source": "ritchiespecs"
}
```

### [R04_SUCCESSOR_NOTE] `mini_excavator` / `takeuchi_tb135`
'takeuchi_tb135' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Lineage: predecessor to TB235 (same 3.5-ton platform; TB235 introduced iT4 engine)."
}
```

### [R04_SUCCESSOR_NOTE] `mini_excavator` / `takeuchi_tb153fr`
'takeuchi_tb153fr' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Lineage: successor to TB53FR; predecessor to TB257FR (turbocharged Kubota, 3-circuit aux)."
}
```

### [R04_SUCCESSOR_NOTE] `mini_excavator` / `takeuchi_tb216`
'takeuchi_tb216' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "OEM override applied 2026-03-29 â€” Takeuchi US OEM (takeuchi-us.com); replaces legacy specs."
}
```

### [R04_SUCCESSOR_NOTE] `mini_excavator` / `takeuchi_tb216h`
'takeuchi_tb216h' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Platform sibling to TB216 (non-hybrid); coexisted in lineup — not predecessor/successor relationship."
}
```

### [R04_SUCCESSOR_NOTE] `mini_excavator` / `takeuchi_tb230`
'takeuchi_tb230' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "OEM override applied 2026-03-29 â€” Takeuchi US OEM (takeuchi-us.com); replaces legacy specs."
}
```

### [R04_SUCCESSOR_NOTE] `mini_excavator` / `takeuchi_tb235`
'takeuchi_tb235' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Lineage: successor to TB135; succeeded by TB235-2 (Tier 4 Final Kubota engine)."
}
```

### [R04_SUCCESSOR_NOTE] `mini_excavator` / `takeuchi_tb257fr`
'takeuchi_tb257fr' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Lineage: current production FR line; direct successor to TB153FR."
}
```

### [R04_SUCCESSOR_NOTE] `mini_excavator` / `takeuchi_tb53fr`
'takeuchi_tb53fr' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Lineage: direct predecessor to TB153FR (same STS zero-swing platform)."
}
```

### [R04_SUCCESSOR_NOTE] `scissor_lift` / `genie_gs_1930`
'genie_gs_1930' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "platform_height_ft, operating_weight_lbs, stowed_height_in, power_source: prior locked values superseded by current Genie EN-US OEM PDF (2026). PDF values: 19 ft 3 in, 3,209 lb, 71 in rails-lowered, 2"
}
```

### [R04_SUCCESSOR_NOTE] `scissor_lift` / `genie_gs_2632`
'genie_gs_2632' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "platform_capacity_lbs, platform_height_ft, platform_length_ft, platform_width_ft, operating_weight_lbs, power_source: prior locked values superseded by current Genie EN-US OEM PDF (2026). Prior values"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s130`
Production record 'bobcat_s130' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s150`
Production record 'bobcat_s150' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s160`
Production record 'bobcat_s160' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s175`
Production record 'bobcat_s175' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s185`
Production record 'bobcat_s185' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s205`
Production record 'bobcat_s205' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s220`
Production record 'bobcat_s220' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s250`
Production record 'bobcat_s250' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `bobcat_s250`
'bobcat_s250' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "[2026-03-29 Research Batch] Net HP 72 (SAE Net) per OEM spec sheet. High-flow not available on standard S250. Two-speed high 12.0 mph. Sources: OEM Bobcat S250 spec sheet (scribd/ttcontractors.ca), ritchiespecs.com, skidsteerloaderspecs.com/bobcat_s250",
  "banned_source": "ritchiespecs"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s300`
Production record 'bobcat_s300' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `bobcat_s300`
'bobcat_s300' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "[2026-03-29 Research Batch] Kubota V3800-DI-TE3 81 hp net. ROC 3,000 lbs; tipping 6,000 lbs. Width 72.1 in over 12x16.5. Std flow 24.0 gpm. High-flow not available. Two-speed max 12.0 mph. Sources: ritchiespecs.com Bobcat S300, skidsteerloaderspecs.com/bobcat_s300",
  "banned_source": "ritchiespecs"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s330`
Production record 'bobcat_s330' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s510_mseries_pret4`
Production record 'bobcat_s510_mseries_pret4' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s510_mseries_t4`
Production record 'bobcat_s510_mseries_t4' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s530`
Production record 'bobcat_s530' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R06_ERA_SPLIT_NO_GENERATION] `skid_steer` / `bobcat_s550`
Era-split record 'bobcat_s550' has years {'start': 2012, 'end': 2025} but no generation_name/era field
```json
{
  "years_supported": {
    "start": 2012,
    "end": 2025
  }
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s570_mseries_pret4`
Production record 'bobcat_s570_mseries_pret4' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s570_mseries_t4`
Production record 'bobcat_s570_mseries_t4' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R06_ERA_SPLIT_NO_GENERATION] `skid_steer` / `bobcat_s590`
Era-split record 'bobcat_s590' has years {'start': 2014, 'end': 2025} but no generation_name/era field
```json
{
  "years_supported": {
    "start": 2014,
    "end": 2025
  }
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s62`
Production record 'bobcat_s62' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `bobcat_s630`
'bobcat_s630' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "Radial lift 600-frame. Kubota V3307 engine. Superseded by S650 (vertical lift) in same frame. Active used market 2012-2018. Net HP used for autofill (70.3), gross available separately."
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s64`
Production record 'bobcat_s64' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R06_ERA_SPLIT_NO_GENERATION] `skid_steer` / `bobcat_s650`
Era-split record 'bobcat_s650' has years {'start': 2009, 'end': 2020} but no generation_name/era field
```json
{
  "years_supported": {
    "start": 2009,
    "end": 2020
  }
}
```

### [R05_MISSING_MODEL_FAMILY] `skid_steer` / `bobcat_s66`
Production record 'bobcat_s66' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R06_ERA_SPLIT_NO_GENERATION] `skid_steer` / `bobcat_s750`
Era-split record 'bobcat_s750' has years {'start': 2011, 'end': 2022} but no generation_name/era field
```json
{
  "years_supported": {
    "start": 2011,
    "end": 2022
  }
}
```

### [R06_ERA_SPLIT_NO_GENERATION] `skid_steer` / `bobcat_s770`
Era-split record 'bobcat_s770' has years {'start': 2009, 'end': 2023} but no generation_name/era field
```json
{
  "years_supported": {
    "start": 2009,
    "end": 2023
  }
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_216`
'cat_216' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lbs (5740): RitchieSpecs shows conflicting weights â€” 5740 lb (Operational Weight section) vs 5490 lb (Weights section). Using 5740. Pending OEM verification.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_216`
'cat_216' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "6 spec fields populated (MEDIUM confidence) from RitchieSpecs â€” 2026-03-27.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_226`
'cat_226' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lbs (5830): RitchieSpecs shows conflicting weights â€” 5830 lb (Operational Weight) vs 5645 lb (Weights section). Using 5830. Pending OEM verification.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_226`
'cat_226' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "6 spec fields populated (MEDIUM confidence) from RitchieSpecs â€” 2026-03-27.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_226b`
'cat_226b' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "Pass 2 spec fill (2026-03-27): horsepower_hp=57, rated_operating_capacity_lbs=1500, tipping_load_lbs=3000, operating_weight_lbs=5835, travel_speed_high_mph=7.9, width_over_tires_in=60. Source: skidsteerloaderspecs.com (cross-ref ritchiespecs.com). Single-speed machine. MEDIUM confidence â€” secondar",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_232`
'cat_232' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lbs (6931): RitchieSpecs shows conflicting weights â€” 6931 lb (Operational Weight) vs 6739.5 lb (Weights section). Using 6931. Pending OEM verification.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_232`
'cat_232' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "6 spec fields populated (MEDIUM confidence) from RitchieSpecs â€” 2026-03-27.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_232b`
'cat_232b' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "Pass 2 spec fill (2026-03-27): horsepower_hp=49, rated_operating_capacity_lbs=1750, tipping_load_lbs=3500, operating_weight_lbs=6660, travel_speed_high_mph=6.9, width_over_tires_in=60. Source: skidsteerloaderspecs.com (cross-ref ritchiespecs.com). Single-speed machine. MEDIUM confidence â€” secondar",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_236`
'cat_236' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lbs (7030): RitchieSpecs shows conflicting weights â€” 7030 lb (Operational Weight) vs 6810 lb (Weights section). Using 7030. Pending OEM verification.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_236`
'cat_236' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "travel_speed_high_mph (6.9): RitchieSpecs shows conflict â€” Max Speed 6.9 mph vs Operating Speed 7.6 mph. Using 6.9 (Max Speed field, conservative/standard-config). Single-speed machine.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_236`
'cat_236' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "6 spec fields populated (MEDIUM confidence) from RitchieSpecs â€” 2026-03-27.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_236b`
'cat_236b' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "Pass 2 spec fill (2026-03-27): horsepower_hp=70, rated_operating_capacity_lbs=1750, tipping_load_lbs=4012, operating_weight_lbs=7005, travel_speed_high_mph=11.6, width_over_tires_in=66. Source: skidsteerloaderspecs.com (cross-ref ritchiespecs.com). MEDIUM confidence â€” secondary aggregators; OEM PD",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_242`
'cat_242' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lbs (6931): RitchieSpecs shows conflicting weights â€” 6931 lb (Operational Weight) vs 6858.5 lb (Weights section). Using 6931. Pending OEM verification.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_242`
'cat_242' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "width_over_tires_in (66.0): confirmed from RitchieSpecs Vehicle Width Over Tires field. Diagram header artifact (~60 in) is an incorrect display â€” use 66.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_242`
'cat_242' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "6 spec fields populated (MEDIUM confidence) from RitchieSpecs â€” 2026-03-27.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_242b`
'cat_242b' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "Pass 2 spec fill (2026-03-27): horsepower_hp=57, rated_operating_capacity_lbs=2000, tipping_load_lbs=4000, operating_weight_lbs=6800, travel_speed_high_mph=7.4, width_over_tires_in=66. Source: skidsteerloaderspecs.com (cross-ref ritchiespecs.com). Single-speed machine â€” no 2-speed option. operatin",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_246`
'cat_246' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lbs (7230): RitchieSpecs shows conflicting weights â€” 7230 lb (Operational Weight) vs 7087 lb (Weights section). Using 7230. Pending OEM verification.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_246`
'cat_246' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "travel_speed_high_mph (6.9): RitchieSpecs shows conflict â€” Max Speed 6.9 mph vs Operating Speed 7.6 mph. Using 6.9 (Max Speed field, standard-config). Single-speed machine.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_246`
'cat_246' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "6 spec fields populated (MEDIUM confidence) from RitchieSpecs â€” 2026-03-27.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_246b`
'cat_246b' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "Pass 2 spec fill (2026-03-27): horsepower_hp=78, rated_operating_capacity_lbs=2000, tipping_load_lbs=4188, operating_weight_lbs=7140, travel_speed_high_mph=11.8, width_over_tires_in=66. Source: skidsteerloaderspecs.com (cross-ref ritchiespecs.com). MEDIUM confidence â€” secondary aggregators; OEM PD",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_252b`
'cat_252b' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "Pass 2 spec fill (2026-03-27): tipping_load_lbs=5615, travel_speed_high_mph=11.1, width_over_tires_in=72. Source: skidsteerloaderspecs.com (cross-ref ritchiespecs.com). MEDIUM confidence â€” secondary aggregators; OEM PDF not directly accessed. NOTE: tipping_load_lbs=5615 per skidsteerloaderspecs (r",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_262b`
'cat_262b' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "Minor tipping_load_lbs source variance: RitchieSpecs 5613 vs skidsteerloaderspecs.com 5615 â€” using 5615.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `cat_262b`
'cat_262b' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "6 spec fields populated (MEDIUM confidence) from RitchieSpecs + skidsteerloaderspecs.com â€” 2026-03-27.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `gehl_5640`
'gehl_5640' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "[2026-03-29 Research Batch] Deutz BF4M2011 82 hp net (SpecsFront confirmed). Width 67 in. Flow 23 gpm. High-flow not standard. Travel 7.7 mph. Operating weight ~7,090 lbs estimated from platform; MEDIUM confidence â€” recommend OEM spec sheet confirmation. Sources: skidsteerloaderspecs.com/gehl_5640",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `gehl_6640`
'gehl_6640' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "[2026-03-29 Research Batch] 82 hp net (Deutz BF4M2011 â€” same engine as 5640). Width 67 in. Flow 23 gpm. High-flow null. Travel 7.7 mph. Operating weight MEDIUM â€” 6640E shows 7,920 lbs on RitchieSpecs; original 6640 consistent but OEM weight not explicitly confirmed. Sources: skidsteerloaderspecs",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `skid_steer` / `jd_332`
'jd_332' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "[2026-03-29 Research Batch] 85 net hp OEM brochure confirmed. Operating weight 9,160 lbs. Width 77.1 in over 14x17.5. Std flow 24 gpm. High-flow null for base 300-series. Travel 7.2 mph single-speed max. Sources: OEM JD 300-Series brochure, skidsteerloaderspecs.com/jd_332, ritchiespecs.com JD 332D",
  "banned_source": "ritchiespecs"
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l215`
'nh_l215' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 200 Series launch / early 2010-2014. Obsolete/replaced model; keep separate from later successor models."
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l223`
'nh_l223' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 200 Series launch / early 2010-2014. Obsolete/replaced model; keep separate from later successor models."
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l225`
'nh_l225' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 200 Series launch / early 2010-2014. Obsolete/replaced model; keep separate from later successor models."
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l230`
'nh_l230' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 200 Series launch / early 2010-2014. Obsolete/replaced model; keep separate from later successor models."
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l316`
'nh_l316' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 300 Series / OEM-confirmed in CNH New Holland 2019 brochure (L316/L318/L320/L321/L328/L334). Successor family to 200 Series. Do not use these specs to patch 200 Series records. L32"
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l318`
'nh_l318' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 300 Series / OEM-confirmed in CNH New Holland 2019 brochure (L316/L318/L320/L321/L328/L334). Successor family to 200 Series. Do not use these specs to patch 200 Series records. L32"
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l320`
'nh_l320' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 300 Series / OEM-confirmed in CNH New Holland 2019 brochure (L316/L318/L320/L321/L328/L334). Successor family to 200 Series. Do not use these specs to patch 200 Series records. L32"
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l321`
'nh_l321' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 300 Series / OEM-confirmed in CNH New Holland 2019 brochure (L316/L318/L320/L321/L328/L334). Successor family to 200 Series. Do not use these specs to patch 200 Series records. L32"
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l328`
'nh_l328' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 300 Series / OEM-confirmed in CNH New Holland 2019 brochure (L316/L318/L320/L321/L328/L334). Successor family to 200 Series. Do not use these specs to patch 200 Series records. L32"
}
```

### [R04_SUCCESSOR_NOTE] `skid_steer` / `nh_l334`
'nh_l334' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "ERA_CLASSIFICATION: 300 Series / OEM-confirmed in CNH New Holland 2019 brochure (L316/L318/L320/L321/L328/L334). Successor family to 200 Series. Do not use these specs to patch 200 Series records. L32"
}
```

### [R04_SUCCESSOR_NOTE] `telehandler` / `caterpillar_tl642`
'caterpillar_tl642' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "GENERATION: TL642 is the C-series predecessor to the TL642D. This record covers C-series (non-D) only."
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `telehandler` / `caterpillar_tl642`
'caterpillar_tl642' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight SOFT: LECTURA and VeriTread show range of 19,800–21,200 lb across C-series years. Registry uses 21,000 lb midpoint.",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `telehandler` / `gehl_rs10_55`
'gehl_rs10_55' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight 30,865 lb (14.0t) confirmed from LECTURA.",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `telehandler` / `genie_gth_636`
'genie_gth_636' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight 16,975 lb consistent across VeriTread, LECTURA (7.7t), and MAK Equipment.",
  "banned_source": "lectura"
}
```

### [R05_MISSING_MODEL_FAMILY] `telehandler` / `genie_gth_844`
Production record 'genie_gth_844' is missing model_family
```json
{
  "registry_tier": "production"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `telehandler` / `jcb_509_42`
'jcb_509_42' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight 25,350 lb confirmed from LECTURA (11.5t = 25,353 lb) and AllMachines.",
  "banned_source": "lectura"
}
```

### [R04_SUCCESSOR_NOTE] `telehandler` / `jlg_g10_55a`
'jlg_g10_55a' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "operating_weight SUPERSEDED: LECTURA value of 28,600 lb (12.97t) was recorded in pre-lock source_refs. This value is superseded by OEM spec sheet confirmation of 34,400 lb from JLG OEM brochure Part N"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `telehandler` / `jlg_g10_55a`
'jlg_g10_55a' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight SUPERSEDED: LECTURA value of 28,600 lb (12.97t) was recorded in pre-lock source_refs. This value is superseded by OEM spec sheet confirmation of 34,400 lb from JLG OEM brochure Part No. 3131573 (Form JLG-TEL-BRO-1108). Registry stores 34,400 lb as the authoritative value. LECTURA va",
  "banned_source": "lectura"
}
```

### [R04_SUCCESSOR_NOTE] `telehandler` / `jlg_g5_18a`
'jlg_g5_18a' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "OEM lock 2026-04-10 (_apply_jlg_oem_lock_v4_1): core perf+powertrain fields updated from OEM spec sheet. JLG OEM spec sheet Part No. 3132221 Form SS-G5-18A R021805. Rated Cap=5,500 lb. Max Lift=18 ft "
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `telehandler` / `jlg_g6_42a`
'jlg_g6_42a' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight 19,700 lb confirmed from LECTURA (8.94t = 19,710 lb).",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `telehandler` / `jlg_g9_43a`
'jlg_g9_43a' notes mention banned source 'machinerytrader' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight SOFT: LECTURA and MachineryTrader show range of 24,000–25,000 lb. Registry uses 24,500 lb midpoint; confirm from OEM PDF.",
  "banned_source": "machinerytrader"
}
```

### [R04_SUCCESSOR_NOTE] `telehandler` / `skytrak_10054`
'skytrak_10054' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "PLATFORM: 10054 shares core drivetrain (Cummins QSF3.8) with 10042 and 8042. Longer boom distinguishes 10054 from 10042 (42 ft vs 54 ft lift height). NOTE: pre-lock registry entries incorrectly refere"
}
```

### [R04_SUCCESSOR_NOTE] `telehandler` / `skytrak_6036`
'skytrak_6036' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "JLG/SkyTrak OEM spec sheet, Part No. 3132403LA, 0915. Generation: T4F_powershift. All 9 fields from this document. Model superseded by 6034 in 2023."
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `case_721g`
'case_721g' notes mention banned source 'ritchiespecs' — verify values were not derived from this source
```json
{
  "note_excerpt": "reach_at_dump_ft = 3.69 ft is MEDIUM confidence — RitchieSpecs shows this as 'Dump Reach @ Full Height, 45 deg'. May reflect reach at full height, not standard 45-deg/7 ft clearance. Manual review required before locking.",
  "banned_source": "ritchiespecs"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `doosan_dl250`
'doosan_dl250' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "tire_size_std patch (v1.1 tire pass): 20.5R25 â€” LECTURA (DL250-5): 20.5R25",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `hyundai_hl940`
'hyundai_hl940' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "tire_size_std patch (v1.1 tire pass): 20.5R25 â€” LECTURA (HL940): 20.5R25",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `hyundai_hl960`
'hyundai_hl960' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "tire_size_std patch (v1.1 tire pass): 23.5R25 â€” LECTURA (HL960): 23.5R25",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `komatsu_wa320_8`
'komatsu_wa320_8' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "tire_size_std patch (v1.1 tire pass): 20.5R25 â€” LECTURA (WA320-8E0): 20.5R25",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `komatsu_wa380_8`
'komatsu_wa380_8' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "tire_size_std patch (v1.1 tire pass): 23.5R25 â€” LECTURA (WA380-8E0): 23.5R25",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `komatsu_wa500_8`
'komatsu_wa500_8' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "tire_size_std patch (v1.1 tire pass): 29.5R25 â€” LECTURA (WA500-8): 29.5R25",
  "banned_source": "lectura"
}
```

### [R04_SUCCESSOR_NOTE] `wheel_loader` / `volvo_l70h`
'volvo_l70h' has successor/predecessor note — year boundary should be verified against both records
```json
{
  "note_excerpt": "fuel_capacity_gal = 58.6 (222 L per OEM). Replaces prior unconfirmed 50 gal."
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `volvo_l70h`
'volvo_l70h' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "operating_weight_lb = 30,880 lb (14.0 t per OEM header). Set to manual_review: LECTURA shows 13.7t (2016-2018) vs 13.96t (2019+); AllMachines cites 32,154 lb for fully equipped configs. Use 30,880 as base config floor.",
  "banned_source": "lectura"
}
```

### [R08_BANNED_SOURCE_IN_NOTES] `wheel_loader` / `volvo_l70h`
'volvo_l70h' notes mention banned source 'lectura' — verify values were not derived from this source
```json
{
  "note_excerpt": "bucket_capacity_cy = 2.75 yd3 (= 2.1 m3, base standard bucket per LECTURA consistent 2014-2025). Note: Volvo CE product page also references 2.3 m3 (3.0 yd3) STE P BOE config. Wide config range possible. manual_review required.",
  "banned_source": "lectura"
}
```
