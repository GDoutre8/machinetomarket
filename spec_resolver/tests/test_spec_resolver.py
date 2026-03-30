"""
tests/test_spec_resolver.py
All 9 required test cases for the spec resolver.

Run with:
    python -m pytest spec_resolver/tests/ -v
or:
    python -m pytest spec_resolver/tests/test_spec_resolver.py -v

Test inventory
--------------
1.  test_exact_model_match
2.  test_family_match_returns_ranges
3.  test_high_flow_detected_hydraulic_override
4.  test_cab_vs_canopy_weight_difference
5.  test_seller_claim_conflicts_with_registry
6.  test_weak_fuzzy_match_no_injection
7.  test_package_dependent_unresolved
8.  test_ui_hint_fields_returned_correctly
9.  test_requires_confirm_populated_correctly
"""

from __future__ import annotations
import sys
import os

# Allow running from repo root with: python -m pytest spec_resolver/tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from spec_resolver.spec_resolver import resolve_from_dict
from spec_resolver.types import MatchType, OverallStatus, FieldSource, FieldBehavior
from spec_resolver.tests.fixtures import (
    CAT_259D3,
    DEERE_333_SERIES,
    KUBOTA_SVL75_2,
    DEERE_35G,
    CASE_580SN,
    WEAK_ENTRY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _input(
    raw:        str,
    mfr:        str,
    model:      str,
    category:   str,
    registry:   dict,
    confidence: float,
    match_type: str,
    claims:     dict | None = None,
    modifiers:  list | None = None,
) -> dict:
    return {
        "raw_listing_text":          raw,
        "parsed_manufacturer":       mfr,
        "parsed_model":              model,
        "parsed_category":           category,
        "detected_modifiers":        modifiers or [],
        "extracted_numeric_claims":  claims or {},
        "registry_match":            registry,
        "registry_match_confidence": confidence,
        "match_type":                match_type,
    }


# ---------------------------------------------------------------------------
# TEST 1 — Exact model match
# ---------------------------------------------------------------------------

class TestExactModelMatch:
    """
    Exact match (confidence ≥ 0.85) on Cat 259D3.
    All locked fields should be injected with no requires_confirm.
    """

    def setup_method(self):
        self.out = resolve_from_dict(_input(
            raw        = "2019 caterpillar 259D3 cab enclosed",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        ))

    def test_status_is_exact(self):
        assert self.out.overall_resolution_status == OverallStatus.EXACT

    def test_safe_for_injection(self):
        assert self.out.safe_for_listing_injection is True

    def test_net_hp_injected(self):
        assert self.out.resolved_specs.get("net_hp") == 73

    def test_operating_weight_injected(self):
        assert self.out.resolved_specs.get("operating_weight_lb") == 8990

    def test_roc_injected(self):
        assert self.out.resolved_specs.get("roc_lb") == 2200

    def test_tipping_load_injected(self):
        assert self.out.resolved_specs.get("tipping_load_lb") == 6300

    def test_travel_speed_injected(self):
        assert self.out.resolved_specs.get("travel_speed_mph") == 7.1

    def test_fuel_type_injected(self):
        assert self.out.resolved_specs.get("fuel_type") == "Diesel"

    def test_no_underscore_fields_in_resolved_specs(self):
        for key in self.out.resolved_specs:
            assert not key.startswith("_"), (
                f"UI hint '{key}' leaked into resolved_specs"
            )

    def test_source_is_registry_exact(self):
        meta = self.out.per_field_metadata.get("net_hp")
        assert meta is not None
        assert meta.source == FieldSource.REGISTRY_EXACT

    def test_no_warnings(self):
        # Exact high-confidence match should produce no warnings
        non_info = [w for w in self.out.warnings if w.severity.value != "info"]
        assert non_info == []


# ---------------------------------------------------------------------------
# TEST 2 — Family match → ranges
# ---------------------------------------------------------------------------

class TestFamilyMatchReturnsRanges:
    """
    Family match on Deere 333 Series.
    Fields with 'range' behavior must be returned as strings, not ints.
    All injected range-fields must appear in requires_confirm.
    """

    def setup_method(self):
        self.out = resolve_from_dict(_input(
            raw        = "2017 john deere 333 track loader",
            mfr        = "john deere",
            model      = "333",
            category   = "CTL",
            registry   = DEERE_333_SERIES,
            confidence = 0.80,
            match_type = "family",
        ))

    def test_status_is_family(self):
        assert self.out.overall_resolution_status == OverallStatus.FAMILY

    def test_roc_is_range_string(self):
        roc = self.out.resolved_specs.get("roc_lb")
        assert isinstance(roc, str), f"Expected range string, got {type(roc).__name__}"
        assert "–" in roc or "-" in roc, f"Expected dash in range: {roc}"

    def test_op_weight_is_range_string(self):
        wt = self.out.resolved_specs.get("operating_weight_lb")
        assert isinstance(wt, str), f"Expected range string, got {type(wt).__name__}"

    def test_range_fields_in_requires_confirm(self):
        confirm = self.out.requires_confirm
        # At least one range-behavior field must be in requires_confirm
        range_fields = {"roc_lb", "tipping_load_lb", "operating_weight_lb", "net_hp"}
        confirmed_range = range_fields & set(confirm)
        assert confirmed_range, (
            f"No range fields found in requires_confirm. Got: {confirm}"
        )

    def test_travel_speed_still_injected(self):
        # Non-range fields are still injected (but also require confirm)
        assert self.out.resolved_specs.get("travel_speed_mph") is not None

    def test_per_field_source_is_family(self):
        meta = self.out.per_field_metadata.get("roc_lb")
        assert meta is not None
        assert meta.source == FieldSource.REGISTRY_FAMILY


# ---------------------------------------------------------------------------
# TEST 3 — High-flow detected → hydraulic override
# ---------------------------------------------------------------------------

class TestHighFlowHydraulicOverride:
    """
    When 'high flow' is present in raw_listing_text:
    - hydraulic_flow_gpm should equal hi_flow_gpm from registry
    - _displayHiFlow hint should be True in ui_hints
    """

    def setup_method(self):
        self.out = resolve_from_dict(_input(
            raw        = "2018 caterpillar 259D3 HIGH FLOW cab 2 speed",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        ))

    def test_hydraulic_flow_equals_hi_flow_rate(self):
        hi_flow_rate = CAT_259D3["specs"]["hi_flow_gpm"]  # 34.0
        injected_flow = self.out.resolved_specs.get("hydraulic_flow_gpm")
        assert injected_flow == hi_flow_rate, (
            f"Expected hi-flow rate {hi_flow_rate}, got {injected_flow}"
        )

    def test_display_hi_flow_hint_set(self):
        assert self.out.ui_hints.get("_displayHiFlow") is True

    def test_hi_flow_gpm_also_present(self):
        # hi_flow_gpm should still be in resolved_specs as informational
        assert "hi_flow_gpm" in self.out.resolved_specs

    def test_std_flow_not_used_when_hiflow_detected(self):
        std_flow = CAT_259D3["specs"]["hydraulic_flow_gpm"]  # 20.5
        injected_flow = self.out.resolved_specs.get("hydraulic_flow_gpm")
        assert injected_flow != std_flow, (
            "Standard flow was used even though hi-flow was detected"
        )

    def test_no_errors(self):
        errors = [w for w in self.out.warnings if w.severity.value == "error"]
        assert errors == []


# ---------------------------------------------------------------------------
# TEST 4 — Cab vs canopy weight difference
# ---------------------------------------------------------------------------

class TestCabVsCanopyWeightDifference:
    """
    Kubota SVL75-2 has option_overrides for has_cab and has_canopy.
    The resolver must select the correct weight based on detected option.
    """

    def _resolve_with_option(self, raw_text: str) -> dict:
        return resolve_from_dict(_input(
            raw        = raw_text,
            mfr        = "kubota",
            model      = "SVL75-2",
            category   = "CTL",
            registry   = KUBOTA_SVL75_2,
            confidence = 0.95,
            match_type = "exact",
        ))

    def test_cab_weight_higher_than_canopy(self):
        out_cab    = self._resolve_with_option("2020 kubota SVL75-2 enclosed cab heat ac")
        out_canopy = self._resolve_with_option("2020 kubota SVL75-2 open canopy orops")

        wt_cab    = out_cab.resolved_specs.get("operating_weight_lb")
        wt_canopy = out_canopy.resolved_specs.get("operating_weight_lb")

        assert wt_cab is not None,    "Cab weight not resolved"
        assert wt_canopy is not None, "Canopy weight not resolved"
        assert wt_cab > wt_canopy, (
            f"Expected cab weight ({wt_cab}) > canopy weight ({wt_canopy})"
        )

    def test_cab_weight_matches_fixture_override(self):
        expected = KUBOTA_SVL75_2["option_overrides"]["has_cab"]["operating_weight_lb"]
        out = self._resolve_with_option("2021 kubota svl75-2 enclosed cab")
        wt  = out.resolved_specs.get("operating_weight_lb")
        assert wt == expected, f"Expected {expected}, got {wt}"

    def test_canopy_weight_matches_fixture_override(self):
        expected = KUBOTA_SVL75_2["option_overrides"]["has_canopy"]["operating_weight_lb"]
        out = self._resolve_with_option("2019 kubota svl75-2 canopy orops")
        wt  = out.resolved_specs.get("operating_weight_lb")
        assert wt == expected, f"Expected {expected}, got {wt}"

    def test_ui_hint_has_cab_set_correctly(self):
        out = self._resolve_with_option("2020 kubota SVL75-2 cab ac heat")
        assert out.ui_hints.get("_hasCab") is True

    def test_ui_hint_no_cab_when_orops(self):
        out = self._resolve_with_option("2020 kubota SVL75-2 orops open station")
        assert out.ui_hints.get("_hasCab") is False


# ---------------------------------------------------------------------------
# TEST 5 — Seller claim conflicts with registry
# ---------------------------------------------------------------------------

class TestSellerClaimConflict:
    """
    Seller claims an HP of 85 but registry says 73 for Cat 259D3.
    The resolver must:
      - Keep the registry value (not the seller claim)
      - Add a SELLER_CLAIM_CONFLICT warning
      - Add net_hp to requires_confirm
    """

    def setup_method(self):
        self.out = resolve_from_dict(_input(
            raw        = "2019 caterpillar 259D3 85hp cab nice machine",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
            claims     = {"seller_hp": 85.0},
        ))

    def test_registry_value_retained(self):
        assert self.out.resolved_specs.get("net_hp") == 73, (
            "Seller claim (85 hp) should NOT override registry value (73 hp)"
        )

    def test_conflict_warning_present(self):
        codes = [w.code for w in self.out.warnings]
        assert "SELLER_CLAIM_CONFLICT" in codes, (
            f"Expected SELLER_CLAIM_CONFLICT warning. Got: {codes}"
        )

    def test_net_hp_in_requires_confirm(self):
        assert "net_hp" in self.out.requires_confirm, (
            f"Conflicted field not in requires_confirm: {self.out.requires_confirm}"
        )

    def test_conflict_in_per_field_metadata(self):
        meta = self.out.per_field_metadata.get("net_hp")
        assert meta is not None
        # The trace should flag the conflict — check via warning list
        warn_fields = [w.field for w in self.out.warnings if w.code == "SELLER_CLAIM_CONFLICT"]
        assert "net_hp" in warn_fields


# ---------------------------------------------------------------------------
# TEST 6 — Weak fuzzy match → no injection
# ---------------------------------------------------------------------------

class TestWeakFuzzyMatchNoInjection:
    """
    Confidence 0.50 is below HARD_FLOOR_CONFIDENCE (0.55).
    Resolver must return empty resolved_specs and UNRESOLVED status.
    """

    def setup_method(self):
        self.out = resolve_from_dict(_input(
            raw        = "some loader machine unknown model",
            mfr        = "caterpillar",
            model      = "UNKNOWN",
            category   = "CTL",
            registry   = WEAK_ENTRY,
            confidence = 0.50,          # below HARD_FLOOR_CONFIDENCE = 0.55
            match_type = "family",
        ))

    def test_status_is_unresolved(self):
        assert self.out.overall_resolution_status == OverallStatus.UNRESOLVED

    def test_no_specs_injected(self):
        assert self.out.resolved_specs == {}, (
            f"Expected empty resolved_specs, got: {self.out.resolved_specs}"
        )

    def test_not_safe_for_injection(self):
        assert self.out.safe_for_listing_injection is False

    def test_unresolved_warning_present(self):
        assert len(self.out.warnings) > 0, "Expected at least one warning"

    def test_no_requires_confirm_when_nothing_resolved(self):
        # requires_confirm should only list fields that WERE injected but need checking
        # If nothing was injected, the list should be empty
        assert self.out.requires_confirm == []


# ---------------------------------------------------------------------------
# TEST 7 — Package-dependent field unresolved without option
# ---------------------------------------------------------------------------

class TestPackageDependentUnresolved:
    """
    hydraulic_flow_gpm on Cat 259D3 is package_dependent.
    When NO high_flow option is detected in the raw text, the resolver should:
      - Still inject the standard flow value (it IS present in registry)
      - NOT set _displayHiFlow
      - Add hydraulic_flow_gpm to requires_confirm (because it's pkg-dependent
        and we can't be certain which config the machine has)
    """

    def setup_method(self):
        # Raw text has NO mention of high flow
        self.out = resolve_from_dict(_input(
            raw        = "2019 caterpillar 259D3 cab 2 speed nice machine",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        ))

    def test_no_high_flow_hint(self):
        assert self.out.ui_hints.get("_displayHiFlow") is not True, (
            "_displayHiFlow should not be set when high flow was not detected"
        )

    def test_std_flow_used_not_hi_flow(self):
        expected_std = CAT_259D3["specs"]["hydraulic_flow_gpm"]  # 20.5
        injected = self.out.resolved_specs.get("hydraulic_flow_gpm")
        assert injected == expected_std, (
            f"Expected std flow {expected_std}, got {injected}"
        )

    def test_hydraulic_field_in_requires_confirm(self):
        # package_dependent field without confirmed option → requires confirm
        assert "hydraulic_flow_gpm" in self.out.requires_confirm, (
            f"Package-dependent field missing from requires_confirm: "
            f"{self.out.requires_confirm}"
        )


# ---------------------------------------------------------------------------
# TEST 8 — UI hint fields returned correctly
# ---------------------------------------------------------------------------

class TestUiHintFieldsReturnedCorrectly:
    """
    _ prefix fields must NEVER appear in resolved_specs.
    They must appear in ui_hints.
    Verified for _displayHiFlow (from high_flow option)
    and _isLGP (from lgp option).
    """

    def test_display_hi_flow_in_ui_hints_not_specs(self):
        out = resolve_from_dict(_input(
            raw        = "2020 caterpillar 259D3 high flow cab",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        ))
        # Must be in ui_hints
        assert "_displayHiFlow" in out.ui_hints, (
            f"_displayHiFlow not in ui_hints: {out.ui_hints}"
        )
        # Must NOT be in resolved_specs
        assert "_displayHiFlow" not in out.resolved_specs, (
            "_displayHiFlow leaked into resolved_specs"
        )

    def test_is_lgp_hint_from_option(self):
        out = resolve_from_dict(_input(
            raw        = "2018 caterpillar 259D3 lgp low ground pressure",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        ))
        assert "_isLGP" in out.ui_hints
        assert "_isLGP" not in out.resolved_specs

    def test_no_hint_keys_in_resolved_specs_general(self):
        out = resolve_from_dict(_input(
            raw        = "2019 john deere 333G high flow cab",
            mfr        = "john deere",
            model      = "333G",
            category   = "CTL",
            registry   = DEERE_333_SERIES,
            confidence = 0.80,
            match_type = "family",
        ))
        for key in out.resolved_specs:
            assert not key.startswith("_"), (
                f"UI hint key '{key}' found in resolved_specs"
            )

    def test_has_cab_hint_in_ui_hints(self):
        out = resolve_from_dict(_input(
            raw        = "2021 kubota SVL75-2 enclosed cab heat ac",
            mfr        = "kubota",
            model      = "SVL75-2",
            category   = "CTL",
            registry   = KUBOTA_SVL75_2,
            confidence = 0.95,
            match_type = "exact",
        ))
        assert "_hasCab" in out.ui_hints
        assert out.ui_hints["_hasCab"] is True


# ---------------------------------------------------------------------------
# TEST 9 — requires_confirm populated correctly
# ---------------------------------------------------------------------------

class TestRequiresConfirmPopulatedCorrectly:
    """
    Verifies all the cases that should populate requires_confirm:
      a) Family-level range fields
      b) Conflicting seller claim
      c) Package-dependent field without resolved option
    """

    def test_family_range_fields_in_requires_confirm(self):
        out = resolve_from_dict(_input(
            raw        = "deere 333 CTL",
            mfr        = "john deere",
            model      = "333",
            category   = "CTL",
            registry   = DEERE_333_SERIES,
            confidence = 0.78,
            match_type = "family",
        ))
        confirm = set(out.requires_confirm)
        # These are declared as 'range' in DEERE_333_SERIES field_behaviors
        assert "roc_lb" in confirm or "operating_weight_lb" in confirm, (
            f"Family range fields not in requires_confirm: {confirm}"
        )

    def test_conflict_adds_to_requires_confirm(self):
        out = resolve_from_dict(_input(
            raw        = "caterpillar 259D3 100hp cab",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
            claims     = {"seller_hp": 100.0},
        ))
        assert "net_hp" in out.requires_confirm

    def test_package_dependent_without_option_in_requires_confirm(self):
        # No high flow mentioned → hydraulic_flow_gpm should require confirm
        out = resolve_from_dict(_input(
            raw        = "caterpillar 259D3 enclosed cab",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        ))
        assert "hydraulic_flow_gpm" in out.requires_confirm

    def test_locked_exact_fields_not_in_requires_confirm(self):
        # For exact high-confidence matches with no conflict or package issue,
        # non-package-dependent locked fields must NOT be in requires_confirm
        out = resolve_from_dict(_input(
            raw        = "2019 john deere 35G mini excavator",
            mfr        = "john deere",
            model      = "35G",
            category   = "MINI",
            registry   = DEERE_35G,
            confidence = 0.95,
            match_type = "exact",
        ))
        confirm = set(out.requires_confirm)
        # These are all LOCKED fields with no option dependency on the 35G
        locked_clean = {"net_hp", "operating_weight_lb", "max_dig_depth",
                        "bucket_breakout_lb"}
        leaking = locked_clean & confirm
        assert not leaking, (
            f"Locked exact-match fields should not be in requires_confirm: {leaking}"
        )

    def test_requires_confirm_is_sorted_list(self):
        out = resolve_from_dict(_input(
            raw        = "deere 333 track loader",
            mfr        = "john deere",
            model      = "333",
            category   = "CTL",
            registry   = DEERE_333_SERIES,
            confidence = 0.78,
            match_type = "family",
        ))
        assert out.requires_confirm == sorted(out.requires_confirm), (
            "requires_confirm should be sorted alphabetically"
        )

    def test_requires_confirm_no_duplicates(self):
        out = resolve_from_dict(_input(
            raw        = "deere 333 high flow",
            mfr        = "john deere",
            model      = "333",
            category   = "CTL",
            registry   = DEERE_333_SERIES,
            confidence = 0.78,
            match_type = "family",
        ))
        assert len(out.requires_confirm) == len(set(out.requires_confirm)), (
            "requires_confirm contains duplicates"
        )


# ---------------------------------------------------------------------------
# Additional integration tests
# ---------------------------------------------------------------------------

class TestAdditionalIntegration:
    """Extra integration checks that round out coverage."""

    def test_year_outside_range_warning(self):
        """Year 2010 is before SVL75-2 production (2015). Expect year warning."""
        out = resolve_from_dict(_input(
            raw        = "2010 kubota SVL75-2 cab",
            mfr        = "kubota",
            model      = "SVL75-2",
            category   = "CTL",
            registry   = KUBOTA_SVL75_2,
            confidence = 0.90,
            match_type = "exact",
        ))
        codes = [w.code for w in out.warnings]
        assert "YEAR_OUTSIDE_RANGE" in codes

    def test_empty_registry_returns_unresolved(self):
        out = resolve_from_dict({
            "raw_listing_text":          "cat 259d3",
            "parsed_manufacturer":       "caterpillar",
            "parsed_model":              "259D3",
            "parsed_category":           "CTL",
            "detected_modifiers":        [],
            "extracted_numeric_claims":  {},
            "registry_match":            {},          # empty!
            "registry_match_confidence": 0.95,
            "match_type":                "exact",
        })
        assert out.overall_resolution_status == OverallStatus.UNRESOLVED
        assert out.resolved_specs == {}

    def test_manufacturer_only_returns_unresolved(self):
        out = resolve_from_dict(_input(
            raw        = "caterpillar machine",
            mfr        = "caterpillar",
            model      = "",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.60,
            match_type = "manufacturer_only",
        ))
        assert out.overall_resolution_status == OverallStatus.UNRESOLVED

    def test_backhoe_extendahoe_dig_depth_override(self):
        """Case 580SN with extendahoe: dig depth should use override value."""
        out = resolve_from_dict(_input(
            raw        = "2018 case 580SN 4wd extendahoe cab",
            mfr        = "case",
            model      = "580SN",
            category   = "BH",
            registry   = CASE_580SN,
            confidence = 0.95,
            match_type = "exact",
        ))
        expected = CASE_580SN["option_overrides"]["extendahoe"]["max_dig_depth"]
        actual   = out.resolved_specs.get("max_dig_depth")
        assert actual == expected, (
            f"Expected extendahoe dig depth '{expected}', got '{actual}'"
        )

    def test_mini_ex_travel_speed_high_and_low(self):
        """Deere 35G should resolve both high and low travel speeds."""
        out = resolve_from_dict(_input(
            raw        = "2020 john deere 35G mini excavator cab",
            mfr        = "john deere",
            model      = "35G",
            category   = "MINI",
            registry   = DEERE_35G,
            confidence = 0.95,
            match_type = "exact",
        ))
        assert out.resolved_specs.get("travel_speed_high_mph") == 3.0
        assert out.resolved_specs.get("travel_speed_low_mph") == 1.9

    def test_output_to_dict_is_json_serialisable(self):
        """ResolverOutput.to_dict() must produce a plain-dict with no custom types."""
        import json
        out = resolve_from_dict(_input(
            raw        = "2019 caterpillar 259D3 cab",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        ))
        d = out.to_dict()
        # Should not raise
        json.dumps(d)

    def test_audit_trail_attached(self):
        """Audit trail should be attached to the output object."""
        out = resolve_from_dict(_input(
            raw        = "2019 caterpillar 259D3 cab",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        ))
        assert hasattr(out, "_audit_trail")
        trail = out._audit_trail
        assert trail.parsed_mfr == "caterpillar"
        assert trail.n_injected > 0

    def test_resolve_from_dict_matches_resolve(self):
        """resolve() and resolve_from_dict() must produce identical output."""
        from spec_resolver.spec_resolver import resolve
        from spec_resolver.types import ResolverInput

        d = _input(
            raw        = "2019 caterpillar 259D3 cab",
            mfr        = "caterpillar",
            model      = "259D3",
            category   = "CTL",
            registry   = CAT_259D3,
            confidence = 0.95,
            match_type = "exact",
        )
        out_dict   = resolve_from_dict(d)
        inp        = ResolverInput(
            raw_listing_text          = d["raw_listing_text"],
            parsed_manufacturer       = d["parsed_manufacturer"],
            parsed_model              = d["parsed_model"],
            parsed_category           = d["parsed_category"],
            detected_modifiers        = d["detected_modifiers"],
            extracted_numeric_claims  = d["extracted_numeric_claims"],
            registry_match            = d["registry_match"],
            registry_match_confidence = d["registry_match_confidence"],
            match_type                = MatchType(d["match_type"]),
        )
        out_obj = resolve(inp)

        assert out_dict.resolved_specs == out_obj.resolved_specs
        assert out_dict.overall_resolution_status == out_obj.overall_resolution_status
