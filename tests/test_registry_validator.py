"""
Unit tests for scripts/registry_validator.py

Each rule is tested independently using synthetic fixtures.
Real registry files are NOT loaded — tests are isolated from live data.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.registry_validator import (
    ERROR,
    WARNING,
    INFO,
    Finding,
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
    run_all_rules,
    build_json_report,
    build_markdown_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_record(
    slug: str = "test_slug",
    mfr: str = "TestMfr",
    model: str = "TestModel",
    tier: str = "production",
    status: str = "active_used_market",
    year_start: int = 2015,
    year_end: int = 2022,
    roc: float = None,
    tipping: float = None,
    source_refs: list = None,
    model_family: str = "TestFamily",
    field_confidence: dict = None,
    notes: list = None,
    spec_confidence: str = None,
    field_behavior: dict = None,
    generation_name: str = None,
) -> dict:
    """Build a minimal synthetic registry record."""
    r: dict = {
        "model_slug":     slug,
        "manufacturer":   mfr,
        "model":          model,
        "registry_tier":  tier,
        "status":         status,
        "years_supported": {"start": year_start, "end": year_end},
        "specs":          {},
        "source_refs":    source_refs if source_refs is not None else ["oem.com spec page"],
        "field_confidence": field_confidence if field_confidence is not None else {"horsepower_hp": "HIGH"},
        "notes":          notes if notes is not None else [],
    }
    if model_family is not None:
        r["model_family"] = model_family
    if roc is not None:
        r["specs"]["rated_operating_capacity_lbs"] = roc
    if tipping is not None:
        r["specs"]["tipping_load_lbs"] = tipping
    if spec_confidence is not None:
        r["spec_confidence"] = spec_confidence
    if field_behavior is not None:
        r["field_behavior"] = field_behavior
    if generation_name is not None:
        r["generation_name"] = generation_name
    return r


META_275 = {"record_count": 275}
META_NONE = {}


# ---------------------------------------------------------------------------
# R01 — Duplicate Slugs
# ---------------------------------------------------------------------------

class TestDuplicateSlugs:
    def test_no_duplicates_clean(self):
        records = [make_record("a"), make_record("b"), make_record("c")]
        findings = rule_duplicate_slugs("skid_steer", META_NONE, records)
        assert findings == []

    def test_single_duplicate_is_error(self):
        records = [make_record("alpha"), make_record("alpha"), make_record("beta")]
        findings = rule_duplicate_slugs("skid_steer", META_NONE, records)
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "R01_DUPLICATE_SLUG"
        assert f.severity == ERROR
        assert f.slug == "alpha"
        assert f.detail["count"] == 2

    def test_triple_duplicate_reported_once(self):
        records = [make_record("x"), make_record("x"), make_record("x")]
        findings = rule_duplicate_slugs("skid_steer", META_NONE, records)
        assert len(findings) == 1
        assert findings[0].detail["count"] == 3

    def test_multiple_distinct_duplicates(self):
        records = [
            make_record("a"), make_record("a"),
            make_record("b"), make_record("b"),
        ]
        findings = rule_duplicate_slugs("skid_steer", META_NONE, records)
        slugs = {f.slug for f in findings}
        assert slugs == {"a", "b"}

    def test_empty_slug_ignored(self):
        records = [{"model_slug": ""}, {"model_slug": ""}]
        findings = rule_duplicate_slugs("skid_steer", META_NONE, records)
        assert findings == []

    def test_missing_slug_field_ignored(self):
        records = [{}, {}]
        findings = rule_duplicate_slugs("skid_steer", META_NONE, records)
        assert findings == []


# ---------------------------------------------------------------------------
# R02 — Deprecated in Active
# ---------------------------------------------------------------------------

class TestDeprecatedInActive:
    def test_active_record_clean(self):
        records = [make_record("a", tier="production", status="active_used_market")]
        findings = rule_deprecated_in_active("skid_steer", META_NONE, records)
        assert findings == []

    def test_deprecated_registry_tier_is_error(self):
        records = [make_record("bobcat_s850_doosan", tier="DEPRECATED")]
        findings = rule_deprecated_in_active("skid_steer", META_NONE, records)
        assert len(findings) == 1
        assert findings[0].rule_id == "R02_DEPRECATED_IN_ACTIVE"
        assert findings[0].severity == ERROR
        assert findings[0].slug == "bobcat_s850_doosan"

    def test_deprecated_status_is_error(self):
        records = [make_record("a", status="deprecated")]
        findings = rule_deprecated_in_active("skid_steer", META_NONE, records)
        assert any(f.severity == ERROR for f in findings)

    def test_deprecated_ambiguous_parent_is_error(self):
        # toro_dingo_tx700 real case: status = "deprecated_ambiguous_parent"
        records = [make_record("toro_dingo_tx700", status="deprecated_ambiguous_parent", tier="deprecated_ambiguous_parent")]
        findings = rule_deprecated_in_active("compact_track_loader", META_NONE, records)
        assert len(findings) >= 1
        assert all(f.severity == ERROR for f in findings)

    def test_case_insensitive_matching(self):
        records = [make_record("a", tier="DEPRECATED")]
        findings = rule_deprecated_in_active("skid_steer", META_NONE, records)
        assert any(f.severity == ERROR for f in findings)

    def test_coverage_stub_not_deprecated(self):
        records = [make_record("a", tier="coverage_stub")]
        findings = rule_deprecated_in_active("skid_steer", META_NONE, records)
        assert findings == []


# ---------------------------------------------------------------------------
# R03 — Year Range Overlap
# ---------------------------------------------------------------------------

class TestYearRangeOverlap:
    def test_no_overlap_clean(self):
        records = [
            make_record("a", model="S590", year_start=2010, year_end=2013, tier="production"),
            make_record("b", model="S590", year_start=2014, year_end=2022, tier="production"),
        ]
        findings = rule_year_range_overlap("skid_steer", META_NONE, records)
        assert findings == []

    def test_overlap_is_warning(self):
        records = [
            make_record("a", model="S590", year_start=2010, year_end=2016, tier="production"),
            make_record("b", model="S590", year_start=2014, year_end=2022, tier="production"),
        ]
        findings = rule_year_range_overlap("skid_steer", META_NONE, records)
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "R03_YEAR_OVERLAP"
        assert f.severity == WARNING
        assert f.detail["range_a"] == [2010, 2016]
        assert f.detail["range_b"] == [2014, 2022]

    def test_era_split_retired_exempt(self):
        records = [
            make_record("parent", model="S590", year_start=2010, year_end=2025, tier="era_split_retired"),
            make_record("child",  model="S590", year_start=2014, year_end=2022, tier="production"),
        ]
        findings = rule_year_range_overlap("skid_steer", META_NONE, records)
        assert findings == []

    def test_different_models_no_false_positive(self):
        records = [
            make_record("s590", model="S590", year_start=2014, year_end=2022, tier="production"),
            make_record("s650", model="S650", year_start=2014, year_end=2022, tier="production"),
        ]
        findings = rule_year_range_overlap("skid_steer", META_NONE, records)
        assert findings == []

    def test_no_years_skipped(self):
        r = make_record("a", model="S590", tier="production")
        del r["years_supported"]
        findings = rule_year_range_overlap("skid_steer", META_NONE, [r])
        assert findings == []

    def test_adjacent_years_not_overlap(self):
        records = [
            make_record("a", model="S590", year_start=2010, year_end=2013, tier="production"),
            make_record("b", model="S590", year_start=2014, year_end=2022, tier="production"),
        ]
        findings = rule_year_range_overlap("skid_steer", META_NONE, records)
        assert findings == []


# ---------------------------------------------------------------------------
# R04 — Successor Notes
# ---------------------------------------------------------------------------

class TestSuccessorNote:
    def test_no_notes_clean(self):
        records = [make_record("a")]
        findings = rule_successor_overlap("skid_steer", META_NONE, records)
        assert findings == []

    def test_successor_note_with_year_is_info(self):
        records = [make_record("a", notes=["Replaced by S595 in 2019"])]
        findings = rule_successor_overlap("skid_steer", META_NONE, records)
        assert len(findings) == 1
        assert findings[0].rule_id == "R04_SUCCESSOR_NOTE"
        assert findings[0].severity == INFO

    def test_predecessor_note_detected(self):
        records = [make_record("a", notes=["This model is the predecessor to T76 (2022+)"])]
        findings = rule_successor_overlap("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R04_SUCCESSOR_NOTE" for f in findings)

    def test_note_without_year_not_flagged(self):
        records = [make_record("a", notes=["Replaces the earlier model"])]
        findings = rule_successor_overlap("skid_steer", META_NONE, records)
        assert findings == []

    def test_only_one_finding_per_record(self):
        records = [make_record("a", notes=[
            "Replaced by S595 in 2019",
            "Successor model launched 2020",
        ])]
        findings = rule_successor_overlap("skid_steer", META_NONE, records)
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# R05 — Missing Model Family
# ---------------------------------------------------------------------------

class TestMissingModelFamily:
    def test_production_with_family_clean(self):
        records = [make_record("a", tier="production", model_family="S-Series")]
        findings = rule_missing_model_family("skid_steer", META_NONE, records)
        assert findings == []

    def test_stub_without_family_clean(self):
        records = [make_record("a", tier="coverage_stub", model_family=None)]
        findings = rule_missing_model_family("skid_steer", META_NONE, records)
        assert findings == []

    def test_production_without_family_is_info(self):
        records = [make_record("a", tier="production", model_family=None)]
        findings = rule_missing_model_family("skid_steer", META_NONE, records)
        assert len(findings) == 1
        assert findings[0].rule_id == "R05_MISSING_MODEL_FAMILY"
        assert findings[0].severity == INFO

    def test_production_candidate_without_family_is_info(self):
        records = [make_record("a", tier="production_candidate", model_family=None)]
        findings = rule_missing_model_family("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R05_MISSING_MODEL_FAMILY" for f in findings)

    def test_era_split_retired_without_family_not_flagged(self):
        records = [make_record("a", tier="era_split_retired", model_family=None)]
        findings = rule_missing_model_family("skid_steer", META_NONE, records)
        assert findings == []


# ---------------------------------------------------------------------------
# R06 — Missing Generation on Era-Split Records
# ---------------------------------------------------------------------------

class TestMissingGenerationOnEraSplit:
    def test_era_split_with_years_and_gen_clean(self):
        records = [make_record("a", tier="era_split_retired", generation_name="T4 Final era")]
        findings = rule_missing_generation_on_era_split("skid_steer", META_NONE, records)
        assert findings == []

    def test_era_split_with_years_no_gen_is_info(self):
        records = [make_record("a", tier="era_split_retired", year_start=2014, year_end=2022)]
        findings = rule_missing_generation_on_era_split("skid_steer", META_NONE, records)
        info_findings = [f for f in findings if f.rule_id == "R06_ERA_SPLIT_NO_GENERATION"]
        assert len(info_findings) == 1
        assert info_findings[0].severity == INFO

    def test_era_split_no_years_no_gen_is_warning(self):
        r = make_record("a", tier="era_split_retired")
        r["years_supported"] = {}
        findings = rule_missing_generation_on_era_split("skid_steer", META_NONE, [r])
        warn_findings = [f for f in findings if f.rule_id == "R06_ERA_SPLIT_NO_METADATA"]
        assert len(warn_findings) == 1
        assert warn_findings[0].severity == WARNING

    def test_non_era_split_tier_not_flagged(self):
        records = [make_record("a", tier="production")]
        findings = rule_missing_generation_on_era_split("skid_steer", META_NONE, records)
        assert findings == []


# ---------------------------------------------------------------------------
# R07 — Missing Source Metadata
# ---------------------------------------------------------------------------

class TestMissingSourceMetadata:
    def test_production_with_source_and_confidence_clean(self):
        records = [make_record(
            "a", tier="production",
            source_refs=["oem.com/specs"],
            field_confidence={"horsepower_hp": "HIGH"},
        )]
        findings = rule_missing_source_metadata("skid_steer", META_NONE, records)
        assert findings == []

    def test_production_no_source_refs_is_warning(self):
        records = [make_record("a", tier="production", source_refs=[])]
        findings = rule_missing_source_metadata("skid_steer", META_NONE, records)
        source_warnings = [f for f in findings if f.rule_id == "R07_MISSING_SOURCE_REFS"]
        assert len(source_warnings) == 1
        assert source_warnings[0].severity == WARNING

    def test_production_no_field_confidence_is_warning(self):
        records = [make_record("a", tier="production", field_confidence={})]
        findings = rule_missing_source_metadata("skid_steer", META_NONE, records)
        conf_warnings = [f for f in findings if f.rule_id == "R07_MISSING_FIELD_CONFIDENCE"]
        assert len(conf_warnings) == 1

    def test_stub_no_source_not_flagged(self):
        records = [make_record("a", tier="coverage_stub", source_refs=[], field_confidence={})]
        findings = rule_missing_source_metadata("skid_steer", META_NONE, records)
        assert findings == []


# ---------------------------------------------------------------------------
# R08 — Banned Source Contamination
# ---------------------------------------------------------------------------

class TestBannedSourceContamination:
    def test_clean_oem_source(self):
        records = [make_record("a", source_refs=["https://bobcat.com/specs/s590"])]
        findings = rule_banned_source_contamination("skid_steer", META_NONE, records)
        assert findings == []

    def test_ritchiespecs_in_source_refs_is_warning(self):
        records = [make_record("a", source_refs=["https://www.ritchiespecs.com/machine/bobcat-s590"])]
        findings = rule_banned_source_contamination("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R08_BANNED_SOURCE" and f.severity == WARNING for f in findings)

    def test_lectura_in_source_refs_is_warning(self):
        records = [make_record("a", source_refs=["lectura specs page"])]
        findings = rule_banned_source_contamination("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R08_BANNED_SOURCE" for f in findings)

    def test_machinerytrader_in_source_refs_is_warning(self):
        records = [make_record("a", source_refs=["machinerytrader.com listing"])]
        findings = rule_banned_source_contamination("skid_steer", META_NONE, records)
        assert any(f.severity == WARNING for f in findings)

    def test_banned_source_in_notes_is_info(self):
        records = [make_record("a", notes=["RitchieSpecs was checked but OEM PDF used instead"])]
        findings = rule_banned_source_contamination("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R08_BANNED_SOURCE_IN_NOTES" and f.severity == INFO for f in findings)

    def test_no_banned_in_notes_clean(self):
        records = [make_record("a", notes=["OEM spec sheet confirmed. All values locked."])]
        findings = rule_banned_source_contamination("skid_steer", META_NONE, records)
        assert findings == []


# ---------------------------------------------------------------------------
# R09 — ROC/Tipping Anomaly
# ---------------------------------------------------------------------------

class TestROCTippingAnomaly:
    def test_normal_2x_ratio_clean(self):
        records = [make_record("a", mfr="Case", roc=2000, tipping=4000)]
        findings = rule_roc_tipping_anomaly("skid_steer", META_NONE, records)
        assert findings == []

    def test_ratio_within_50pct_band_clean(self):
        records = [make_record("a", mfr="Case", roc=2000, tipping=3800)]
        findings = rule_roc_tipping_anomaly("skid_steer", META_NONE, records)
        assert findings == []

    def test_bobcat_35pct_is_info(self):
        # ROC=2100, tipping=6000 → ratio=2.857 — Bobcat 35% convention
        records = [make_record("a", mfr="Bobcat", roc=2100, tipping=6000)]
        findings = rule_roc_tipping_anomaly("skid_steer", META_NONE, records)
        assert len(findings) == 1
        assert findings[0].rule_id == "R09_ROC_35PCT_CONVENTION"
        assert findings[0].severity == INFO

    def test_jcb_35pct_is_info(self):
        records = [make_record("a", mfr="JCB", roc=3200, tipping=9143)]
        findings = rule_roc_tipping_anomaly("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R09_ROC_35PCT_CONVENTION" and f.severity == INFO for f in findings)

    def test_unknown_mfr_35pct_is_warning(self):
        # JD should have been normalized to 50% — if ratio is 2.857 it's a warning
        records = [make_record("a", mfr="John Deere", roc=2125, tipping=6070)]
        findings = rule_roc_tipping_anomaly("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R09_ROC_35PCT_UNEXPECTED" and f.severity == WARNING for f in findings)

    def test_genuine_anomaly_is_error(self):
        # ratio=4.0 — outside both bands
        records = [make_record("a", mfr="Case", roc=2000, tipping=8000)]
        findings = rule_roc_tipping_anomaly("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R09_ROC_RATIO_ANOMALY" and f.severity == ERROR for f in findings)

    def test_bobcat_t190_real_anomaly(self):
        # bobcat_t190: roc=1900, tl=6851, ratio=3.606 — anomaly even for Bobcat
        records = [make_record("bobcat_t190", mfr="Bobcat", roc=1900, tipping=6851)]
        findings = rule_roc_tipping_anomaly("compact_track_loader", META_NONE, records)
        assert any(f.severity == ERROR for f in findings)

    def test_non_roc_equipment_type_skipped(self):
        records = [make_record("a", mfr="JLG", roc=2000, tipping=8000)]
        findings = rule_roc_tipping_anomaly("boom_lift", META_NONE, records)
        assert findings == []

    def test_missing_roc_skipped(self):
        records = [make_record("a")]  # no roc/tipping
        findings = rule_roc_tipping_anomaly("skid_steer", META_NONE, records)
        assert findings == []

    def test_mini_excavator_type_skipped(self):
        records = [make_record("a", roc=2000, tipping=8000)]
        findings = rule_roc_tipping_anomaly("mini_excavator", META_NONE, records)
        assert findings == []


# ---------------------------------------------------------------------------
# R10 — Stub in Production Tier
# ---------------------------------------------------------------------------

class TestStubIntegrity:
    def test_stub_with_no_confidence_clean(self):
        records = [make_record("a", tier="coverage_stub", spec_confidence=None, field_behavior={})]
        findings = rule_stub_in_production_tier("skid_steer", META_NONE, records)
        assert findings == []

    def test_stub_high_confidence_is_error(self):
        records = [make_record("a", tier="coverage_stub", spec_confidence="HIGH")]
        findings = rule_stub_in_production_tier("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R10_STUB_HIGH_CONFIDENCE" and f.severity == ERROR for f in findings)

    def test_stub_medium_confidence_is_error(self):
        records = [make_record("a", tier="coverage_stub", spec_confidence="MEDIUM")]
        findings = rule_stub_in_production_tier("skid_steer", META_NONE, records)
        assert any(f.severity == ERROR for f in findings)

    def test_stub_locked_fields_is_warning(self):
        records = [make_record(
            "a", tier="coverage_stub",
            field_behavior={"horsepower_hp": "locked", "rated_operating_capacity_lbs": "locked"},
        )]
        findings = rule_stub_in_production_tier("skid_steer", META_NONE, records)
        assert any(f.rule_id == "R10_STUB_LOCKED_FIELDS" and f.severity == WARNING for f in findings)

    def test_production_record_not_flagged(self):
        records = [make_record(
            "a", tier="production",
            spec_confidence="HIGH",
            field_behavior={"horsepower_hp": "locked"},
        )]
        findings = rule_stub_in_production_tier("skid_steer", META_NONE, records)
        assert findings == []

    def test_stub_manual_review_field_behavior_clean(self):
        records = [make_record(
            "a", tier="coverage_stub",
            field_behavior={"horsepower_hp": "manual_review"},
        )]
        findings = rule_stub_in_production_tier("skid_steer", META_NONE, records)
        assert not any(f.rule_id == "R10_STUB_LOCKED_FIELDS" for f in findings)


# ---------------------------------------------------------------------------
# R11 — Meta Count Mismatch
# ---------------------------------------------------------------------------

class TestMetaCountMismatch:
    def test_matching_count_clean(self):
        records = [make_record(f"r{i}") for i in range(5)]
        meta = {"record_count": 5}
        findings = rule_meta_record_count("skid_steer", meta, records)
        assert findings == []

    def test_count_mismatch_is_warning(self):
        records = [make_record(f"r{i}") for i in range(7)]
        meta = {"record_count": 5}
        findings = rule_meta_record_count("skid_steer", meta, records)
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "R11_META_COUNT_MISMATCH"
        assert f.severity == WARNING
        assert f.detail["stated_count"] == 5
        assert f.detail["actual_count"] == 7
        assert f.detail["delta"] == 2

    def test_no_record_count_in_meta_clean(self):
        records = [make_record(f"r{i}") for i in range(5)]
        meta = {}
        findings = rule_meta_record_count("skid_steer", meta, records)
        assert findings == []

    def test_wheel_loader_real_case(self):
        # Governance audit found wheel_loader meta says 25 but actual is 27
        records = [make_record(f"r{i}") for i in range(27)]
        meta = {"record_count": 25}
        findings = rule_meta_record_count("wheel_loader", meta, records)
        assert len(findings) == 1
        assert findings[0].detail["delta"] == 2


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

class TestFindingDataclass:
    def test_as_dict_without_detail(self):
        f = Finding("R01", ERROR, "skid_steer", "slug_a", "message text")
        d = f.as_dict()
        assert d["rule_id"] == "R01"
        assert d["severity"] == ERROR
        assert "detail" not in d

    def test_as_dict_with_detail(self):
        f = Finding("R01", ERROR, "skid_steer", "slug_a", "msg", detail={"count": 2})
        d = f.as_dict()
        assert d["detail"]["count"] == 2


# ---------------------------------------------------------------------------
# run_all_rules integration
# ---------------------------------------------------------------------------

class TestRunAllRules:
    def test_clean_synthetic_registry_no_errors(self):
        """A perfectly-formed synthetic registry should produce no ERROR findings."""
        records = [
            make_record(
                slug=f"mfr_model_{i}",
                mfr="CleanMfr",
                model=f"Model{i}",
                tier="production",
                year_start=2010 + i * 3,
                year_end=2012 + i * 3,
                roc=2000.0,
                tipping=4000.0,
                source_refs=["https://oem.com/spec"],
                model_family="TestFamily",
                field_confidence={"horsepower_hp": "HIGH"},
            )
            for i in range(3)
        ]
        findings = run_all_rules("skid_steer", {"record_count": 3}, records)
        errors = [f for f in findings if f.severity == ERROR]
        assert errors == [], f"Unexpected errors: {[f.message for f in errors]}"

    def test_deprecated_record_produces_error(self):
        records = [make_record("deprecated_thing", tier="DEPRECATED")]
        findings = run_all_rules("skid_steer", {}, records)
        assert any(f.severity == ERROR for f in findings)

    def test_duplicate_slug_produces_error(self):
        records = [make_record("dup"), make_record("dup")]
        findings = run_all_rules("skid_steer", {}, records)
        assert any(f.rule_id == "R01_DUPLICATE_SLUG" for f in findings)

    def test_rule_exception_produces_error_finding(self):
        """If a rule crashes, it should produce an error finding rather than propagating."""
        def bad_rule(eq_type, meta, records):
            raise RuntimeError("intentional test failure")

        records = [make_record("a")]
        findings = run_all_rules("skid_steer", {}, records, rules=[bad_rule])
        assert len(findings) == 1
        assert findings[0].rule_id == "VALIDATOR_RULE_ERROR"
        assert findings[0].severity == ERROR


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

class TestReportBuilders:
    def _make_findings(self):
        return [
            Finding("R01_DUPLICATE_SLUG",    ERROR,   "skid_steer", "slug_a", "dup"),
            Finding("R11_META_COUNT_MISMATCH", WARNING, "wheel_loader", "(meta)", "mismatch",
                    detail={"stated_count": 25, "actual_count": 27, "delta": 2}),
            Finding("R04_SUCCESSOR_NOTE", INFO, "skid_steer", "slug_b", "successor"),
        ]

    def test_json_report_structure(self):
        findings = self._make_findings()
        meta = {"skid_steer": {"filename": "f.json", "stated_count": 275, "actual_count": 276}}
        report = build_json_report(findings, meta, strict_mode=True)
        assert "generated_at" in report
        assert report["strict_mode"] is True
        assert report["summary"]["total_findings"] == 3
        assert report["summary"]["by_severity"][ERROR] == 1
        assert report["summary"]["by_severity"][WARNING] == 1
        assert report["summary"]["by_severity"][INFO] == 1
        assert report["summary"]["strict_would_fail"] is True
        assert len(report["findings"]) == 3

    def test_json_report_strict_would_fail_false_on_no_errors(self):
        findings = [Finding("R04", INFO, "skid_steer", "s", "info only")]
        report = build_json_report(findings, {}, strict_mode=False)
        assert report["summary"]["strict_would_fail"] is False

    def test_markdown_report_contains_key_sections(self):
        findings = self._make_findings()
        meta = {"skid_steer": {"filename": "f.json", "stated_count": 275, "actual_count": 276}}
        report = build_json_report(findings, meta, strict_mode=False)
        md = build_markdown_report(findings, report)
        assert "# MTM Registry Validation Report" in md
        assert "## Summary" in md
        assert "## ERROR Findings" in md
        assert "## WARNING Findings" in md
        assert "## INFO Findings" in md
        assert "R01_DUPLICATE_SLUG" in md

    def test_report_findings_sorted_by_severity(self):
        findings = [
            Finding("R04", INFO,    "skid_steer", "a", "info"),
            Finding("R01", ERROR,   "skid_steer", "b", "error"),
            Finding("R11", WARNING, "skid_steer", "c", "warning"),
        ]
        report = build_json_report(findings, {}, strict_mode=False)
        # We pass already-sorted findings to markdown; test sort order in run_all_rules output
        # via the severities of report findings
        sevs = [f["severity"] for f in report["findings"]]
        assert sevs == [INFO, ERROR, WARNING]  # unsorted — sorting happens in main()


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self):
        """run_all_rules must be deterministic across two calls with the same input."""
        import json as _json
        records = [
            make_record(f"rec_{i}", mfr="TestMfr", model=f"M{i}", tier="production",
                        year_start=2010, year_end=2022, roc=2000.0, tipping=4000.0)
            for i in range(5)
        ] + [make_record("dup"), make_record("dup")]

        f1 = run_all_rules("skid_steer", {"record_count": 6}, records)
        f2 = run_all_rules("skid_steer", {"record_count": 6}, records)

        assert [f.as_dict() for f in f1] == [f.as_dict() for f in f2]
