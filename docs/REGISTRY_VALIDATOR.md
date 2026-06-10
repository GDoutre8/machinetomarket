# MTM Registry Validator

Read-only automated validation harness for all active MTM registry files.

Detects registry integrity problems before they reach dealer-facing listing output.

---

## Quick Start

```bash
# Report only (safe, never modifies anything)
python scripts/registry_validator.py

# CI gate — exit nonzero on any ERROR
python scripts/registry_validator.py --strict

# Validate specific registry types only
python scripts/registry_validator.py --only skid_steer compact_track_loader

# Custom output directory
python scripts/registry_validator.py --output-dir /tmp/my-reports
```

Reports are written to `registry_validation_reports/latest.json` and
`registry_validation_reports/latest.md`.

---

## Design Guarantees

- **Read-only.** The validator never writes to any file under `registry/`.
- **Production-aligned.** Imports `REGISTRY_FILENAMES` directly from
  `mtm_registry_lookup.py` — always loads exactly the files production serves.
- **Deterministic.** Given the same registry files, the same report is produced
  on every run. Findings are sorted: ERROR first, then WARNING, then INFO;
  within each severity by registry type then slug.
- **Individually testable.** Every rule is a standalone function; unit tests
  in `tests/test_registry_validator.py` exercise each rule in isolation.

---

## Severity Levels

| Severity | Meaning | CI Behavior |
|----------|---------|-------------|
| **ERROR** | Likely dealer-facing wrong output — broken lookup, bad spec injection, genuine ratio anomaly | Fails `--strict` |
| **WARNING** | Possible integrity issue — sourcing gap, banned source, metadata mismatch | Reported only |
| **INFO** | Cleanup or future-verification item | Reported only |

---

## Validation Rules

### R01 — Duplicate Slugs
**Severity:** ERROR

Two or more records with the same `model_slug` within one registry file.
Duplicate slugs cause ambiguous lookup results (identical to the S850 failure
mode where a DEPRECATED record ties with the valid production record).

### R02 — Deprecated Record in Active Registry
**Severity:** ERROR

Records whose `status` or `registry_tier` contains "deprecat" (case-insensitive).
Deprecated records participate in scoring and cause ambiguous results.

**Real case:** `bobcat_s850_doosan` (registry_tier=DEPRECATED) was tied with
`bobcat_s850_kubota`, causing every "Bobcat S850" query to return `ambiguous_model`.

### R03 — Year Range Overlap
**Severity:** WARNING

Two non-era-split records for the same manufacturer+model share overlapping year
ranges. One era-split-retired parent per pair is exempt — these intentionally span
the full production run as the default catch-all.

### R04 — Successor/Predecessor Note
**Severity:** INFO

Records whose `notes` mention "successor", "predecessor", "replaced by", or
"replaces" alongside a year. The year boundary should be verified against both
the predecessor and successor records.

High false-positive rate — INFO only. Notes text is freeform.

### R05 — Missing Model Family
**Severity:** INFO

Production or production_candidate records with no `model_family` field.
`model_family` is returned in the lookup result identity block and used by
listing copy for family-level claims.

Coverage stubs are exempt.

### R06 — Missing Generation Metadata on Era-Split Records
**Severity:** WARNING (missing both) / INFO (missing generation label only)

Era-split records that lack year ranges and/or generation labels. Year-aware
routing (P-B03 proposal) cannot function without these.

### R07 — Missing Source/Confidence Metadata
**Severity:** WARNING

Production records with no `source_refs` or no `field_confidence` block.
Every production record must trace to an OEM source. Missing `field_confidence`
means all fields will be treated as UNKNOWN confidence by the tiered injection
system.

Coverage stubs are exempt.

### R08 — Banned Source Contamination
**Severity:** WARNING (in source_refs) / INFO (in notes)

Strings from the MTM banned source list in `source_refs` (active data source —
WARNING) or `notes` (may be cited for context — INFO).

**Banned list:** MachineryTrader, EquipmentTrader, RitchieSpecs, Lectura,
HeavyEquipmentGuide.

**Real finding:** CTL v1.32 merge notes cite RitchieSpecs, Lectura, and
ConstructionEquipmentGuide for Case Alpha Series width/hinge_pin patches.

### R09 — ROC/Tipping Ratio Anomaly
**Severity:** ERROR / WARNING / INFO

Applies to `skid_steer` and `compact_track_loader` registries only.

| Band | Range | Result |
|------|-------|--------|
| 50% convention (normal) | 1.80 – 2.20 | No finding |
| 35% convention, known OEM | 2.75 – 2.95 + Bobcat/JCB/Toro | INFO |
| 35% convention, other MFR | 2.75 – 2.95 + other | WARNING — normalization may have been skipped |
| Outside both bands | < 1.80, 2.20 – 2.75, > 2.95 | ERROR — genuine data anomaly |

**Real ERRORs in current data:** `bobcat_t190` ratio=3.606.

### R10 — Stub with Production-Level Integrity Signals
**Severity:** ERROR (HIGH/MEDIUM spec_confidence) / WARNING (locked field_behavior)

Coverage stubs that claim production-level integrity signals will pass the spec
injection guard and inject unverified specs into dealer listings.

### R11 — Meta Record Count Mismatch
**Severity:** WARNING

`_registry_meta.record_count` does not match `len(records)`.

**Real case:** wheel_loader meta says 25, actual count is 27.

---

## Output Files

### `registry_validation_reports/latest.json`

Machine-readable. Schema:

```json
{
  "generated_at": "2026-06-10T12:00:00Z",
  "strict_mode": false,
  "summary": {
    "total_findings": 42,
    "by_severity": {"ERROR": 3, "WARNING": 15, "INFO": 24},
    "by_rule": {"R09_ROC_RATIO_ANOMALY": 1, ...},
    "by_registry": {"skid_steer": 20, ...},
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
      "message": "...",
      "detail": {...}
    }
  ]
}
```

### `registry_validation_reports/latest.md`

Human-readable Markdown with:
- Summary counts table
- Findings by registry table
- Findings by rule table
- Registry metadata table
- Per-severity finding blocks with detail JSON

---

## CI Integration

Add to your CI pipeline:

```yaml
- name: Validate Registries
  run: python scripts/registry_validator.py --strict
```

Exits 0 if no ERROR findings. Exits 1 if ERRORs exist (strict mode only).

Default mode (no `--strict`) always exits 0 — safe for informational runs.

---

## Known False Positives

| Rule | False Positive Condition | Mitigation |
|------|--------------------------|------------|
| R03 | era_split parent/child pairs | Exempt via tier check |
| R04 | Notes citing past model lineage without year-boundary conflicts | INFO severity only |
| R08 (notes) | Notes mentioning banned sources to explain *why they weren't used* | INFO severity only |
| R09 | Bobcat/JCB/Toro 35% OEM convention | INFO severity only for known-35% manufacturers |
| R09 | NH/ASV/others that genuinely use 35% OEM convention | If NH/ASV should be added to the 35% list, update `_ROC_35PCT_OEM_MANUFACTURERS` in `registry_validator.py` |

---

## Tests

```bash
pytest tests/test_registry_validator.py -v
```

44 unit tests covering all 11 rules plus report builders and determinism.
Tests use synthetic fixtures — no live registry files required.

---

## Files

| File | Role |
|------|------|
| `scripts/registry_validator.py` | Validator implementation |
| `tests/test_registry_validator.py` | Unit tests |
| `docs/REGISTRY_VALIDATOR.md` | This document |
| `registry_validator_design.md` | Pre-implementation design artifact |
| `registry_validation_reports/latest.json` | Latest JSON report (generated at runtime) |
| `registry_validation_reports/latest.md` | Latest Markdown report (generated at runtime) |
