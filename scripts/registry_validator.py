"""
MTM Registry Validator
======================
Read-only validation harness for all active MTM registry files.

Detects registry integrity problems before they reach dealer-facing output.
Mirrors the production registry load path — loads exactly the files that
mtm_registry_lookup.py serves to the listing engine.

Usage:
  python scripts/registry_validator.py
  python scripts/registry_validator.py --strict
  python scripts/registry_validator.py --only skid_steer compact_track_loader
  python scripts/registry_validator.py --output-dir /tmp/reports

Exit codes:
  0 — clean or warnings/info only
  1 — strict mode AND ERROR findings present
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Production registry map — import from lookup module so validator and
# production always load the same files.  Falls back to inline copy if the
# import fails (e.g. running validator from a different working directory).
# ---------------------------------------------------------------------------

_REGISTRY_DIR = Path(__file__).parent.parent / "registry" / "active"

try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from mtm_registry_lookup import REGISTRY_FILENAMES as _PROD_REGISTRY_FILENAMES
    REGISTRY_FILENAMES: dict[str, str] = dict(_PROD_REGISTRY_FILENAMES)
except ImportError:
    REGISTRY_FILENAMES = {
        "skid_steer":           "mtm_skid_steer_registry_v1_18.json",
        "compact_track_loader": "mtm_ctl_registry_v1_32.json",
        "mini_excavator":       "mtm_mini_ex_registry_v2_3.json",
        "backhoe_loader":       "mtm_backhoe_loader_registry_v1.json",
        "dozer":                "mtm_dozer_registry_v1.json",
        "scissor_lift":         "mtm_scissor_lift_registry_v1.json",
        "boom_lift":            "mtm_boom_lift_registry_v1.json",
        "wheel_loader":         "mtm_wheel_loader_registry_v1_2.json",
        "excavator":            "mtm_excavator_registry_v2.json",
        "telehandler":          "mtm_telehandler_registry_v3.json",
    }

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ERROR   = "ERROR"
WARNING = "WARNING"
INFO    = "INFO"

SEVERITY_RANK = {ERROR: 0, WARNING: 1, INFO: 2}

# Equipment types where the ROC/tipping ratio rule applies
_ROC_TIPPING_TYPES = {"skid_steer", "compact_track_loader"}

# 50% tipping convention: ROC = 50% tipping → ratio ~2.0
_ROC_50PCT_RATIO_MIN = 1.80
_ROC_50PCT_RATIO_MAX = 2.20

# 35% tipping convention: ROC = 35% tipping → ratio ~2.857
_ROC_35PCT_RATIO_MIN = 2.75
_ROC_35PCT_RATIO_MAX = 2.95

# Manufacturers whose OEM spec sheets use 35% ROC convention
# (policy: stored as-is rather than normalized to MTM 50% standard)
_ROC_35PCT_OEM_MANUFACTURERS = frozenset({"Bobcat", "JCB", "Toro"})

# Banned data sources per MTM CLAUDE.md
_BANNED_SOURCES = [
    "machinerytrader",
    "equipmenttrader",
    "ritchiespecs",
    "lectura",
    "heavyequipmentguide",
]

# Registry tier values that indicate a record is deprecated
_DEPRECATED_MARKERS = ("deprecat",)

# Registry tier values that indicate stubs / seeds
_STUB_MARKERS = ("coverage_stub", "seed_only", "seed")


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

class Finding:
    """A single validation finding."""

    __slots__ = ("rule_id", "severity", "registry", "slug", "message", "detail")

    def __init__(
        self,
        rule_id: str,
        severity: str,
        registry: str,
        slug: str,
        message: str,
        detail: Optional[dict] = None,
    ):
        self.rule_id  = rule_id
        self.severity = severity
        self.registry = registry
        self.slug     = slug
        self.message  = message
        self.detail   = detail

    def as_dict(self) -> dict:
        d: dict = {
            "rule_id":  self.rule_id,
            "severity": self.severity,
            "registry": self.registry,
            "slug":     self.slug,
            "message":  self.message,
        }
        if self.detail:
            d["detail"] = self.detail
        return d


# ---------------------------------------------------------------------------
# Registry loader
# ---------------------------------------------------------------------------

def _load_registry_file(path: Path, eq_type: str) -> tuple[dict, list[dict]]:
    """
    Load a single registry JSON file.
    Returns (meta_dict, records_list).
    Handles both {records:[...]} and {new_records:[...]} and bare-list formats.
    All opens use utf-8 — registry files contain non-ASCII characters in notes.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        meta    = {}
        records = data
    else:
        meta    = data.get("_registry_meta", {})
        records = (
            data.get("records")
            or data.get("new_records")
            or []
        )

    # Inject _registry tag so rules can reference the source type
    for r in records:
        r.setdefault("_registry", eq_type)

    return meta, records


def load_all_registries(
    registry_dir: Optional[Path] = None,
    target_types: Optional[set] = None,
) -> dict[str, tuple[dict, list[dict]]]:
    """
    Load all active registries.  Returns {eq_type: (meta, records)}.
    Skips types not in target_types when provided.
    """
    base = registry_dir or _REGISTRY_DIR
    result: dict[str, tuple[dict, list[dict]]] = {}

    for eq_type, filename in REGISTRY_FILENAMES.items():
        if target_types and eq_type not in target_types:
            continue

        # Try active/ subdir first, then parent dir (mirrors _registry_path logic)
        candidates = [base / filename, base.parent / filename]
        path = next((p for p in candidates if p.exists()), None)

        if path is None:
            result[eq_type] = ({}, [])
            continue

        meta, records = _load_registry_file(path, eq_type)
        result[eq_type] = (meta, records)

    return result


# ---------------------------------------------------------------------------
# Helper: normalize text for source-string matching
# ---------------------------------------------------------------------------

def _lower(s) -> str:
    return str(s).lower() if s is not None else ""


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def rule_duplicate_slugs(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R01: Duplicate model_slug within the same registry."""
    seen: dict[str, int] = defaultdict(int)
    for r in records:
        slug = r.get("model_slug") or ""
        if slug:
            seen[slug] += 1

    findings = []
    for slug, count in seen.items():
        if count > 1:
            findings.append(Finding(
                rule_id  = "R01_DUPLICATE_SLUG",
                severity = ERROR,
                registry = eq_type,
                slug     = slug,
                message  = (
                    f"Duplicate model_slug '{slug}' appears {count}x in {eq_type} registry — "
                    "causes ambiguous lookup identical to the S850 failure mode"
                ),
                detail   = {"count": count},
            ))
    return findings


def rule_deprecated_in_active(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R02: Deprecated records still present in an active registry file."""
    findings = []
    for r in records:
        slug   = r.get("model_slug") or "(unknown)"
        status = _lower(r.get("status"))
        tier   = _lower(r.get("registry_tier"))

        is_deprecated = any(m in status or m in tier for m in _DEPRECATED_MARKERS)
        if is_deprecated:
            findings.append(Finding(
                rule_id  = "R02_DEPRECATED_IN_ACTIVE",
                severity = ERROR,
                registry = eq_type,
                slug     = slug,
                message  = (
                    f"Deprecated record '{slug}' is present in active {eq_type} registry "
                    "and will be scored by lookup — causes ambiguous results"
                ),
                detail   = {
                    "status":        r.get("status"),
                    "registry_tier": r.get("registry_tier"),
                },
            ))
    return findings


def rule_year_range_overlap(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R03: Overlapping year ranges for same manufacturer+model pair.
    Exempts era_split_retired records — they are intentional year-range anchors.
    """
    # Group by canonical (manufacturer, model) key
    groups: dict[str, list[tuple]] = defaultdict(list)
    for r in records:
        mfr   = _lower(r.get("manufacturer") or "")
        model = _lower(r.get("model") or "")
        key   = f"{mfr}::{model}"
        ys    = r.get("years_supported") or {}
        start = ys.get("start")
        end_  = ys.get("end")
        tier  = _lower(r.get("registry_tier") or "")
        slug  = r.get("model_slug") or "?"

        if start and end_:
            groups[key].append((slug, int(start), int(end_), tier))

    findings = []
    for key, entries in groups.items():
        if len(entries) < 2:
            continue
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                s1, y1s, y1e, t1 = entries[i]
                s2, y2s, y2e, t2 = entries[j]

                # era_split_retired is an intentional anchor — skip any pair involving one
                if "era_split" in t1 or "era_split" in t2:
                    continue

                # Standard overlap check: two ranges overlap if start_a <= end_b AND start_b <= end_a
                if y1s <= y2e and y2s <= y1e:
                    overlap_s = max(y1s, y2s)
                    overlap_e = min(y1e, y2e)
                    mfr_label, model_label = key.split("::", 1)
                    findings.append(Finding(
                        rule_id  = "R03_YEAR_OVERLAP",
                        severity = WARNING,
                        registry = eq_type,
                        slug     = f"{s1}/{s2}",
                        message  = (
                            f"Year range overlap [{overlap_s}–{overlap_e}] between "
                            f"'{s1}' and '{s2}' ({mfr_label} {model_label})"
                        ),
                        detail   = {
                            "slug_a": s1, "range_a": [y1s, y1e],
                            "slug_b": s2, "range_b": [y2s, y2e],
                        },
                    ))
    return findings


def rule_successor_overlap(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R04: Records with successor/predecessor notes — flag for year-boundary verification."""
    findings = []
    trigger_words = ("successor", "predecessor", "replaced by", "replaces", "superseded")

    for r in records:
        slug  = r.get("model_slug") or "?"
        notes = r.get("notes") or []
        if isinstance(notes, str):
            notes = [notes]

        for note in notes:
            n_lower = _lower(note)
            has_trigger = any(w in n_lower for w in trigger_words)
            has_year    = any(c.isdigit() for c in note)
            if has_trigger and has_year:
                findings.append(Finding(
                    rule_id  = "R04_SUCCESSOR_NOTE",
                    severity = INFO,
                    registry = eq_type,
                    slug     = slug,
                    message  = (
                        f"'{slug}' has successor/predecessor note — year boundary "
                        "should be verified against both records"
                    ),
                    detail   = {"note_excerpt": note[:200]},
                ))
                break  # one finding per record
    return findings


def rule_missing_model_family(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R05: Production-tier records missing model_family."""
    findings = []
    for r in records:
        slug = r.get("model_slug") or "?"
        tier = _lower(r.get("registry_tier") or "")

        # Only check production and production_candidate — stubs are expected to be incomplete
        if tier not in ("production", "production_candidate"):
            continue

        if not r.get("model_family"):
            findings.append(Finding(
                rule_id  = "R05_MISSING_MODEL_FAMILY",
                severity = INFO,
                registry = eq_type,
                slug     = slug,
                message  = f"Production record '{slug}' is missing model_family",
                detail   = {"registry_tier": r.get("registry_tier")},
            ))
    return findings


def rule_missing_generation_on_era_split(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R06: Era-split records missing generation metadata or year range."""
    findings = []
    for r in records:
        slug = r.get("model_slug") or "?"
        tier = _lower(r.get("registry_tier") or "")

        if "era_split" not in tier:
            continue

        ys        = r.get("years_supported") or {}
        has_years = bool(ys.get("start") and ys.get("end"))
        has_gen   = bool(
            r.get("generation_name")
            or r.get("era")
            or r.get("generation")
        )

        if not has_years and not has_gen:
            findings.append(Finding(
                rule_id  = "R06_ERA_SPLIT_NO_METADATA",
                severity = WARNING,
                registry = eq_type,
                slug     = slug,
                message  = (
                    f"Era-split record '{slug}' has no year range AND no generation label — "
                    "year-aware routing cannot function for this record"
                ),
                detail   = {"registry_tier": r.get("registry_tier")},
            ))
        elif not has_gen:
            findings.append(Finding(
                rule_id  = "R06_ERA_SPLIT_NO_GENERATION",
                severity = INFO,
                registry = eq_type,
                slug     = slug,
                message  = (
                    f"Era-split record '{slug}' has years {ys} but no generation_name/era field"
                ),
                detail   = {"years_supported": ys},
            ))
    return findings


def rule_missing_source_metadata(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R07: Production records with empty source_refs or field_confidence."""
    findings = []
    for r in records:
        slug = r.get("model_slug") or "?"
        tier = _lower(r.get("registry_tier") or "")

        if tier not in ("production", "production_candidate"):
            continue

        source_refs  = r.get("source_refs") or []
        field_conf   = r.get("field_confidence") or {}

        if not source_refs:
            findings.append(Finding(
                rule_id  = "R07_MISSING_SOURCE_REFS",
                severity = WARNING,
                registry = eq_type,
                slug     = slug,
                message  = (
                    f"Production record '{slug}' has no source_refs — "
                    "OEM evidence chain is missing"
                ),
                detail   = {"registry_tier": r.get("registry_tier")},
            ))

        if not field_conf:
            findings.append(Finding(
                rule_id  = "R07_MISSING_FIELD_CONFIDENCE",
                severity = WARNING,
                registry = eq_type,
                slug     = slug,
                message  = (
                    f"Production record '{slug}' has no field_confidence block — "
                    "tiered spec injection will treat all fields as UNKNOWN confidence"
                ),
                detail   = {"registry_tier": r.get("registry_tier")},
            ))
    return findings


def rule_banned_source_contamination(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R08: Banned data sources appearing in source_refs (WARNING) or notes (INFO)."""
    findings = []

    for r in records:
        slug = r.get("model_slug") or "?"

        # Check source_refs — these are active data sources: WARNING
        for ref in (r.get("source_refs") or []):
            ref_lower = _lower(ref)
            for banned in _BANNED_SOURCES:
                if banned in ref_lower:
                    findings.append(Finding(
                        rule_id  = "R08_BANNED_SOURCE",
                        severity = WARNING,
                        registry = eq_type,
                        slug     = slug,
                        message  = (
                            f"'{slug}' source_refs contains banned source '{banned}' — "
                            "this source should not be used for spec values"
                        ),
                        detail   = {"source_ref": str(ref)[:300], "banned_source": banned},
                    ))
                    break  # one finding per ref entry

        # Check notes — may mention banned sources for context: INFO
        notes = r.get("notes") or []
        if isinstance(notes, str):
            notes = [notes]
        for note in notes:
            n_lower = _lower(note)
            for banned in _BANNED_SOURCES:
                if banned in n_lower:
                    findings.append(Finding(
                        rule_id  = "R08_BANNED_SOURCE_IN_NOTES",
                        severity = INFO,
                        registry = eq_type,
                        slug     = slug,
                        message  = (
                            f"'{slug}' notes mention banned source '{banned}' — "
                            "verify values were not derived from this source"
                        ),
                        detail   = {"note_excerpt": note[:300], "banned_source": banned},
                    ))
                    break  # one finding per note entry
    return findings


def rule_roc_tipping_anomaly(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R09: ROC/tipping load ratio anomaly detection for SSL and CTL registries.

    Three bands:
      [1.80 – 2.20]  50% tipping convention — normal (no finding)
      [2.75 – 2.95]  35% OEM convention:
                       known 35% manufacturer → INFO
                       other manufacturer     → WARNING (normalization may have been skipped)
      Outside both   → ERROR (genuine data anomaly)
    """
    if eq_type not in _ROC_TIPPING_TYPES:
        return []

    findings = []
    for r in records:
        slug  = r.get("model_slug") or "?"
        specs = r.get("specs") or {}
        roc   = specs.get("rated_operating_capacity_lbs")
        tl    = specs.get("tipping_load_lbs")
        mfr   = r.get("manufacturer") or ""

        if not roc or not tl or roc <= 0:
            continue

        ratio = tl / roc

        # Normal 50% convention — OK
        if _ROC_50PCT_RATIO_MIN <= ratio <= _ROC_50PCT_RATIO_MAX:
            continue

        # 35% OEM convention band
        if _ROC_35PCT_RATIO_MIN <= ratio <= _ROC_35PCT_RATIO_MAX:
            if mfr in _ROC_35PCT_OEM_MANUFACTURERS:
                findings.append(Finding(
                    rule_id  = "R09_ROC_35PCT_CONVENTION",
                    severity = INFO,
                    registry = eq_type,
                    slug     = slug,
                    message  = (
                        f"'{slug}' tipping/ROC ratio {ratio:.3f} — "
                        f"35% OEM convention (policy: store as-is for {mfr})"
                    ),
                    detail   = {
                        "roc": roc, "tipping_load": tl,
                        "ratio": round(ratio, 3), "manufacturer": mfr,
                    },
                ))
            else:
                findings.append(Finding(
                    rule_id  = "R09_ROC_35PCT_UNEXPECTED",
                    severity = WARNING,
                    registry = eq_type,
                    slug     = slug,
                    message  = (
                        f"'{slug}' tipping/ROC ratio {ratio:.3f} — 35% convention "
                        f"for {mfr} which is not a known 35%-OEM manufacturer; "
                        "MTM normalization to 50% may have been skipped"
                    ),
                    detail   = {
                        "roc": roc, "tipping_load": tl,
                        "ratio": round(ratio, 3), "manufacturer": mfr,
                    },
                ))
            continue

        # Outside both bands — genuine anomaly
        findings.append(Finding(
            rule_id  = "R09_ROC_RATIO_ANOMALY",
            severity = ERROR,
            registry = eq_type,
            slug     = slug,
            message  = (
                f"'{slug}' tipping/ROC ratio {ratio:.3f} is outside both the "
                f"50% [{_ROC_50PCT_RATIO_MIN}–{_ROC_50PCT_RATIO_MAX}] and "
                f"35% [{_ROC_35PCT_RATIO_MIN}–{_ROC_35PCT_RATIO_MAX}] bands — "
                "likely a data entry error"
            ),
            detail   = {
                "roc": roc, "tipping_load": tl,
                "ratio": round(ratio, 3), "manufacturer": mfr,
            },
        ))
    return findings


def rule_stub_in_production_tier(eq_type: str, _meta: dict, records: list[dict]) -> list[Finding]:
    """R10: Coverage stubs claiming production-level integrity signals.

    A stub claiming HIGH/MEDIUM spec_confidence will pass the spec injection guard
    and inject unverified specs into dealer listings.
    A stub with locked field_behavior signals contradict stub status.
    """
    findings = []
    for r in records:
        slug = r.get("model_slug") or "?"
        tier = _lower(r.get("registry_tier") or "")

        is_stub = any(m in tier for m in _STUB_MARKERS)
        if not is_stub:
            continue

        spec_conf = (r.get("spec_confidence") or "").upper()
        if spec_conf in ("HIGH", "MEDIUM"):
            findings.append(Finding(
                rule_id  = "R10_STUB_HIGH_CONFIDENCE",
                severity = ERROR,
                registry = eq_type,
                slug     = slug,
                message  = (
                    f"Coverage stub '{slug}' claims spec_confidence={spec_conf} — "
                    "stubs should be LOW or absent; HIGH/MEDIUM allows injection of unverified specs"
                ),
                detail   = {
                    "registry_tier": r.get("registry_tier"),
                    "spec_confidence": spec_conf,
                },
            ))

        field_beh     = r.get("field_behavior") or {}
        locked_fields = [k for k, v in field_beh.items() if v == "locked"]
        if locked_fields:
            findings.append(Finding(
                rule_id  = "R10_STUB_LOCKED_FIELDS",
                severity = WARNING,
                registry = eq_type,
                slug     = slug,
                message  = (
                    f"Coverage stub '{slug}' has {len(locked_fields)} locked field(s) — "
                    "locked behavior implies OEM-verified data; contradicts stub status"
                ),
                detail   = {
                    "locked_fields": sorted(locked_fields)[:10],
                    "registry_tier": r.get("registry_tier"),
                },
            ))
    return findings


def rule_meta_record_count(eq_type: str, meta: dict, records: list[dict]) -> list[Finding]:
    """R11: Registry _registry_meta.record_count does not match actual record count."""
    stated = meta.get("record_count")
    actual = len(records)

    if stated is None:
        return []

    try:
        stated_int = int(stated)
    except (TypeError, ValueError):
        return []

    if stated_int != actual:
        delta = actual - stated_int
        return [Finding(
            rule_id  = "R11_META_COUNT_MISMATCH",
            severity = WARNING,
            registry = eq_type,
            slug     = "(meta)",
            message  = (
                f"{eq_type} _registry_meta.record_count={stated_int} "
                f"but actual record count is {actual} (delta: {delta:+d}) — "
                "meta was not updated atomically with a record add/remove"
            ),
            detail   = {"stated_count": stated_int, "actual_count": actual, "delta": delta},
        )]
    return []


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

ALL_RULES = [
    rule_duplicate_slugs,
    rule_deprecated_in_active,
    rule_year_range_overlap,
    rule_successor_overlap,
    rule_missing_model_family,
    rule_missing_generation_on_era_split,
    rule_missing_source_metadata,
    rule_banned_source_contamination,
    rule_roc_tipping_anomaly,
    rule_stub_in_production_tier,
    rule_meta_record_count,
]


def run_all_rules(
    eq_type: str,
    meta: dict,
    records: list[dict],
    rules: list = None,
) -> list[Finding]:
    """Run all rules against a single registry.  Returns flat list of findings."""
    rules = rules or ALL_RULES
    findings: list[Finding] = []
    for rule_fn in rules:
        try:
            findings.extend(rule_fn(eq_type, meta, records))
        except Exception as exc:
            findings.append(Finding(
                rule_id  = "VALIDATOR_RULE_ERROR",
                severity = ERROR,
                registry = eq_type,
                slug     = "(validator_internal)",
                message  = f"Rule '{rule_fn.__name__}' raised an exception: {exc}",
                detail   = {"exception": str(exc)},
            ))
    return findings


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def build_json_report(
    all_findings: list[Finding],
    registry_metadata: dict,
    strict_mode: bool,
) -> dict:
    by_severity: dict[str, int] = defaultdict(int)
    by_rule:     dict[str, int] = defaultdict(int)
    by_registry: dict[str, int] = defaultdict(int)

    for f in all_findings:
        by_severity[f.severity] += 1
        by_rule[f.rule_id]      += 1
        by_registry[f.registry] += 1

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "strict_mode":  strict_mode,
        "summary": {
            "total_findings":    len(all_findings),
            "by_severity":       {k: by_severity[k] for k in [ERROR, WARNING, INFO] if by_severity[k]},
            "by_rule":           dict(sorted(by_rule.items())),
            "by_registry":       dict(sorted(by_registry.items())),
            "strict_would_fail": by_severity.get(ERROR, 0) > 0,
        },
        "registry_metadata": registry_metadata,
        "findings": [f.as_dict() for f in all_findings],
    }


def build_markdown_report(all_findings: list[Finding], report: dict) -> str:
    lines: list[str] = []
    ts = report["generated_at"]

    lines += [
        "# MTM Registry Validation Report",
        "",
        f"**Generated:** {ts}",
        f"**Strict mode:** {report['strict_mode']}",
        f"**Strict would fail:** {'**YES**' if report['summary']['strict_would_fail'] else 'NO'}",
        "",
    ]

    # Summary counts
    lines += ["## Summary", ""]
    lines += ["| Severity | Count |", "|----------|-------|"]
    for sev in [ERROR, WARNING, INFO]:
        count = report["summary"]["by_severity"].get(sev, 0)
        lines.append(f"| {sev} | {count} |")
    lines += [f"| **TOTAL** | {report['summary']['total_findings']} |", ""]

    # By registry
    lines += ["## Findings by Registry", ""]
    lines += ["| Registry | Findings |", "|----------|----------|"]
    for reg, count in sorted(report["summary"]["by_registry"].items()):
        lines.append(f"| {reg} | {count} |")
    lines.append("")

    # By rule
    lines += ["## Findings by Rule", ""]
    lines += ["| Rule | Count |", "|------|-------|"]
    for rule_id, count in sorted(report["summary"]["by_rule"].items()):
        lines.append(f"| {rule_id} | {count} |")
    lines.append("")

    # Registry metadata
    lines += ["## Registry Metadata", ""]
    lines += [
        "| Registry | File | Stated Count | Actual Count | Delta |",
        "|----------|------|-------------|-------------|-------|",
    ]
    for eq_type, info in sorted(report["registry_metadata"].items()):
        stated = info.get("stated_count", "—")
        actual = info.get("actual_count", "—")
        delta  = f"{actual - stated:+d}" if isinstance(stated, int) and isinstance(actual, int) else "—"
        lines.append(f"| {eq_type} | {info.get('filename','?')} | {stated} | {actual} | {delta} |")
    lines.append("")

    # Findings grouped by severity
    for sev in [ERROR, WARNING, INFO]:
        sev_findings = [f for f in all_findings if f.severity == sev]
        if not sev_findings:
            continue
        lines += [f"## {sev} Findings ({len(sev_findings)})", ""]
        for f in sev_findings:
            lines += [f"### [{f.rule_id}] `{f.registry}` / `{f.slug}`"]
            lines.append(f.message)
            if f.detail:
                lines += ["```json", json.dumps(f.detail, indent=2, ensure_ascii=False), "```"]
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] = None) -> int:
    parser = argparse.ArgumentParser(
        description="MTM Registry Validator — read-only validation harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any ERROR findings exist",
    )
    parser.add_argument(
        "--registry-dir",
        metavar="PATH",
        help="Override path to registry/active/ directory",
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        default="registry_validation_reports",
        help="Directory for JSON and Markdown reports (default: registry_validation_reports/)",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="TYPE",
        help="Validate only these equipment types (e.g. skid_steer compact_track_loader)",
    )

    args = parser.parse_args(argv)

    registry_dir = Path(args.registry_dir) if args.registry_dir else None
    output_dir   = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    target_types = set(args.only) if args.only else None

    print("MTM Registry Validator")
    print(f"  Registry dir : {registry_dir or _REGISTRY_DIR}")
    print(f"  Output dir   : {output_dir}")
    print(f"  Strict mode  : {args.strict}")
    print(f"  Types        : {sorted(target_types) if target_types else 'all'}")
    print()

    all_findings:   list[Finding] = []
    registry_meta_summary: dict   = {}

    registries = load_all_registries(registry_dir, target_types)

    for eq_type, (meta, records) in sorted(registries.items()):
        filename = REGISTRY_FILENAMES.get(eq_type, "?")

        if not records:
            print(f"  [SKIP] {eq_type:30s} — no records found (file may be missing)")
            continue

        findings = run_all_rules(eq_type, meta, records)
        all_findings.extend(findings)

        err_count  = sum(1 for f in findings if f.severity == ERROR)
        warn_count = sum(1 for f in findings if f.severity == WARNING)
        info_count = sum(1 for f in findings if f.severity == INFO)

        status_icon = "X" if err_count else ("~" if warn_count else ".")
        print(
            f"  [{status_icon}] {eq_type:30s}  "
            f"{len(records):4d} records  "
            f"ERR={err_count} WARN={warn_count} INFO={info_count}"
        )

        registry_meta_summary[eq_type] = {
            "filename":     filename,
            "stated_count": meta.get("record_count"),
            "actual_count": len(records),
        }

    # Sort deterministically: ERROR first, then WARNING, INFO; within each by registry + slug
    all_findings.sort(key=lambda f: (SEVERITY_RANK[f.severity], f.registry, f.slug or ""))

    # Write reports
    report     = build_json_report(all_findings, registry_meta_summary, args.strict)
    md_report  = build_markdown_report(all_findings, report)

    json_path = output_dir / "latest.json"
    md_path   = output_dir / "latest.md"

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md_report)

    # Print summary
    s = report["summary"]
    total = s["total_findings"]
    err   = s["by_severity"].get(ERROR, 0)
    warn  = s["by_severity"].get(WARNING, 0)
    info  = s["by_severity"].get(INFO, 0)

    print()
    print(f"Findings: {total} total  ({err} ERROR, {warn} WARNING, {info} INFO)")
    print(f"  {json_path}")
    print(f"  {md_path}")

    if args.strict and err > 0:
        print(
            f"\nSTRICT MODE FAIL: {err} ERROR finding(s) — see {json_path}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
