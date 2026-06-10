# MTM Registry Validator — Design Document

**Date:** 2026-06-10  
**Status:** APPROVED FOR IMPLEMENTATION  
**Phase:** Pre-implementation design artifact

---

## 1. Motivation

The Bobcat audit (2026-06-10) and Governance Audit (2026-06-10) revealed recurring registry
problems that reached dealer-facing output before being caught manually:

- A DEPRECATED record (`bobcat_s850_doosan`) participated in lookup scoring and caused every
  S850 query to return `ambiguous_model` — a demo blocker.
- 172 SSL coverage stubs and 58 CTL coverage stubs are actively served as production records.
- ROC/tipping ratio violations exist across multiple manufacturers (ratio anomalies identified
  in the overnight audit).
- Banned sources (RitchieSpecs, Lectura) appear in production record notes.
- `_registry_meta.record_count` for wheel_loader says 25, actual is 27.

This validator provides a read-only automated harness that detects these issues before they
reach production.

---

## 2. Architecture

### 2.1 Component Map

```
scripts/registry_validator.py
├── load_all_registries()         — mirrors production loader path
├── Finding (dataclass)           — single validation finding
├── RULES: list[Callable]         — individually invocable rule functions
│   ├── rule_duplicate_slugs()
│   ├── rule_deprecated_in_active()
│   ├── rule_year_range_overlap()
│   ├── rule_successor_overlap()
│   ├── rule_missing_model_family()
│   ├── rule_missing_generation_on_era_split()
│   ├── rule_missing_source_metadata()
│   ├── rule_banned_source_contamination()
│   ├── rule_roc_tipping_anomaly()
│   ├── rule_stub_in_production_tier()
│   └── rule_meta_record_count()
├── run_all_rules()               — orchestrates rule execution per registry
├── build_json_report()           — machine-readable output
├── build_markdown_report()       — human-readable output
└── main()                        — CLI entrypoint with --strict / --only flags
```

### 2.2 Registry Loading

The validator imports `REGISTRY_FILENAMES` and `_registry_path()` directly from
`mtm_registry_lookup` so the validator always loads exactly the files production loads.
No filename duplication. If the production lookup module is updated to point at a new
registry version, the validator picks it up automatically.

### 2.3 Read-Only Enforcement

- Validator opens files only with `open(..., "r")`.
- No writes to any path under `registry/`.
- Output goes exclusively to `registry_validation_reports/`.
- Guard: validator asserts no `write` calls occur on any registry path.

---

## 3. Rule Catalog

### R01 — Duplicate Slugs
**Severity:** ERROR  
**Detects:** Two or more records with identical `model_slug` within the same registry file.  
**Why it matters:** Lookup scoring uses slug containment as a near-exact match signal (0.95).
Duplicate slugs cause ambiguous results identical to the S850 failure mode.  
**False positive conditions:** None expected — slugs are designed to be unique per registry.

### R02 — Deprecated Record in Active Registry
**Severity:** ERROR  
**Detects:** Records whose `status` or `registry_tier` contains "deprecat" (case-insensitive).  
**Why it matters:** `bobcat_s850_doosan` (DEPRECATED tier) participated in scoring and caused
every S850 query to return `ambiguous_model`. Deprecated records must not be in active
registry files.  
**False positives:** None — deprecated records should never be served.

### R03 — Year Range Overlap
**Severity:** WARNING  
**Detects:** Two records for the same manufacturer+model that have overlapping year ranges.  
**Exemptions:** Records with `registry_tier == "era_split_retired"` are exempt — these parent
records are intentional year-range anchors that span the full production run.  
**False positive conditions:** Era-split parent/child pairs where the parent intentionally
spans all years. Exempted by tier check.

### R04 — Successor/Predecessor Note
**Severity:** INFO  
**Detects:** Records whose `notes` reference "successor", "predecessor", "replaced by", or
"replaces" alongside a year. These should have year-boundary alignment verified.  
**False positives:** High — notes text is freeform. This rule produces actionable INFO, not
blocking errors.

### R05 — Missing Model Family on Production Records
**Severity:** INFO  
**Detects:** `registry_tier in (production, production_candidate)` records with no
`model_family` field.  
**Why it matters:** `model_family` is returned in the lookup result identity block and used by
listing copy for family-level claims.  
**Exemptions:** `coverage_stub`, `seed`, `era_split_retired` tiers are not checked.

### R06 — Missing Generation Metadata on Era-Split Records
**Severity:** WARNING (missing years+generation) / INFO (missing generation label only)  
**Detects:** Records with `registry_tier` containing "era_split" that lack both a generation
label (`generation_name`, `era`, or `generation` field) and a year range.  
**Why it matters:** Era-split architecture requires child records to have distinct year ranges
so year-aware routing can resolve the correct generation.

### R07 — Missing Source/Confidence Metadata
**Severity:** WARNING  
**Detects:** Production-tier records with empty `source_refs` or empty `field_confidence`.  
**Why it matters:** The Governance Audit identified this as a CRITICAL gap — every production
record must trace to an OEM source per MTM methodology.  
**Exemptions:** `coverage_stub` and `seed` tiers are not checked (stubs by definition lack
OEM verification).

### R08 — Banned Source Contamination
**Severity:** WARNING (source_refs) / INFO (notes)  
**Detects:** Strings from the MTM banned source list appearing in `source_refs` or `notes`.  
**Banned list:** MachineryTrader, EquipmentTrader, RitchieSpecs, Lectura,
HeavyEquipmentGuide, forums, auction listings, resale listings.  
**Why it matters:** The CTL v1.32 merge notes explicitly cite RitchieSpecs, Lectura, and
ConstructionEquipmentGuide as sources for Case Alpha Series width/hinge_pin patches.  
**False positives:** Notes mentioning banned sources to explain *why they were not used*
(e.g., "RitchieSpecs was not used — OEM PDF confirmed instead"). INFO severity for notes
allows human review.

### R09 — ROC/Tipping Ratio Anomaly
**Severity:** ERROR (ratio outside both 50% and 35% ranges) / WARNING (35% on non-expected
manufacturer) / INFO (35% convention for known 35% manufacturers)  
**Applies to:** `skid_steer` and `compact_track_loader` registry types only.  
**Normal range:** 1.8 – 2.2 (50% tipping convention).  
**35% range:** 2.75 – 2.95 (OEM 35% convention).  
**Known 35% manufacturers:** Bobcat, JCB, Toro (per `project_roc_policy_by_manufacturer` memory).  
**Logic:**
- ratio in [1.8, 2.2] → OK (50% convention)
- ratio in [2.75, 2.95] AND manufacturer is known-35% → INFO
- ratio in [2.75, 2.95] AND manufacturer is NOT known-35% → WARNING (35% leaked through without MTM normalization)
- ratio outside both ranges → ERROR

**Real findings from current data:** `bobcat_t190` ratio=3.606 → ERROR. `bobcat_t595`
ratio=2.962 → borderline. 28 records have 35% ratios.

### R10 — Stub with Production-Level Integrity Signals
**Severity:** ERROR (stub claiming HIGH/MEDIUM spec_confidence) / WARNING (stub with locked fields)  
**Detects:** `coverage_stub` or `seed` tier records that also claim production-level integrity
signals (`spec_confidence: HIGH/MEDIUM` or `field_behavior: locked`).  
**Why it matters:** A stub claiming HIGH confidence will pass the spec injection guard and
inject unverified specs into dealer listings.

### R11 — Meta Record Count Mismatch
**Severity:** WARNING  
**Detects:** `_registry_meta.record_count` not equal to actual `len(records)`.  
**Real finding:** wheel_loader meta says 25, actual is 27.

---

## 4. Severity Mapping

| Severity | Definition | CI Behavior |
|----------|-----------|-------------|
| ERROR | Likely dealer-facing wrong output — lookup failure, bad spec injection, ratio violation | Fails `--strict` |
| WARNING | Possible integrity issue — sourcing gap, banned source, meta mismatch | Reported, no exit |
| INFO | Metadata or future cleanup item | Reported, no exit |

---

## 5. Report Schema

### JSON Report (`registry_validation_reports/latest.json`)

```json
{
  "generated_at": "2026-06-10T12:00:00Z",
  "strict_mode": false,
  "summary": {
    "total_findings": 42,
    "by_severity": { "ERROR": 3, "WARNING": 15, "INFO": 24 },
    "by_rule": { "R09_ROC_RATIO_ANOMALY": 1, ... },
    "by_registry": { "skid_steer": 20, "compact_track_loader": 12, ... },
    "strict_would_fail": true
  },
  "registry_metadata": {
    "skid_steer": {
      "filename": "mtm_skid_steer_registry_v1_18.json",
      "stated_count": 275,
      "actual_count": 276
    }
  },
  "findings": [
    {
      "rule_id": "R02_DEPRECATED_IN_ACTIVE",
      "severity": "ERROR",
      "registry": "skid_steer",
      "slug": "bobcat_s850_doosan",
      "message": "Deprecated record 'bobcat_s850_doosan' is present in active skid_steer registry",
      "detail": { "status": "active_used_market", "registry_tier": "DEPRECATED" }
    }
  ]
}
```

### Markdown Report (`registry_validation_reports/latest.md`)

Human-readable. Sections:
- Summary table (counts by severity)
- Findings by registry (table)
- Registry metadata table
- Per-severity finding blocks with detail JSON

---

## 6. Test Plan

### Unit Tests (`tests/test_registry_validator.py`)

Each rule gets at least one positive test (no finding) and one negative test (finding detected).

| Test Class | Rule | Cases |
|------------|------|-------|
| TestDuplicateSlugs | R01 | clean / duplicate detected |
| TestDeprecatedInActive | R02 | clean / deprecated status / deprecated tier / S850 real case |
| TestYearRangeOverlap | R03 | no overlap / overlap detected / era_split exempt |
| TestSuccessorNote | R04 | no note / successor note detected |
| TestMissingModelFamily | R05 | production with family / stub without family OK / production without family flagged |
| TestMissingGenerationOnEraSplit | R06 | era_split with years / era_split without years |
| TestMissingSourceMetadata | R07 | production with source / production without source / stub without source OK |
| TestBannedSource | R08 | clean source / ritchiespecs / lectura / note mention INFO |
| TestROCTippingAnomaly | R09 | normal 2x / bobcat 35% INFO / jd 35% WARNING / true anomaly ERROR / non-roc-type skipped |
| TestStubIntegrity | R10 | stub with no confidence OK / stub HIGH confidence ERROR / stub locked fields WARNING |
| TestMetaCount | R11 | match OK / mismatch WARNING |
| TestRunAllRules | integration | runs full rule set on synthetic registry without crash |

### Determinism Test
Run the validator twice on current active registries. Assert JSON report is byte-for-byte identical.

---

## 7. CLI Interface

```
python scripts/registry_validator.py [OPTIONS]

Options:
  --strict          Exit nonzero (code 1) if any ERROR findings exist
  --registry-dir    Override path to registry/active/ directory
  --output-dir      Override output directory (default: registry_validation_reports/)
  --only TYPE ...   Validate only specified equipment types
```

---

## 8. Risks

| Risk | Mitigation |
|------|-----------|
| Import of mtm_registry_lookup fails (circular or path issue) | Fallback: inline REGISTRY_FILENAMES copy with import error handling |
| Registry files have non-UTF-8 bytes | All opens use `encoding="utf-8"` |
| era_split_retired records trigger false positive year overlaps | Explicit tier exemption in R03 |
| ROC anomaly check overly sensitive for 35% convention records | Three-band check: 50% / 35%-known / 35%-unexpected / error |
| Notes-based rules (R04, R08-notes) produce high false positive counts | R04 and R08-notes are INFO only; actionable findings only at WARNING/ERROR |

---

## 9. Files to Create

| File | Purpose |
|------|---------|
| `scripts/registry_validator.py` | Validator implementation |
| `tests/test_registry_validator.py` | Unit + integration tests |
| `docs/REGISTRY_VALIDATOR.md` | User documentation |
| `registry_validation_reports/` | Output directory (created at runtime) |
| `registry_validator_design.md` | This file |

## 10. Files NOT Modified

All registry JSON files under `registry/active/` are read-only in this task.
No production Python source files are modified.
