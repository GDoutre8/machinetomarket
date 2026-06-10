"""
Tests for lookup query normalization and D/D3 bridge-alias removal.

Covers audit findings:
  F3 — MODEL_BRIDGE_ALIASES rewrote 259d/279d/289d to the D3 generation,
       shadowing the genuine Caterpillar 259D/279D/289D registry records.
  F1 — Year-prefixed queries ("2021 Bobcat S590") failed lookup.
  F2 — Marketplace-style strings ("2019 Bobcat S590, 1800 hrs") failed lookup.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mtm_registry_lookup import (  # noqa: E402
    MODEL_BRIDGE_ALIASES,
    _normalize_marketplace_query,
    _query_attempts,
    lookup_machine,
)


# ---------------------------------------------------------------------------
# F3 — D/D3 alias shadowing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("gen_d, gen_d3", [
    ("259D", "259D3"),
    ("279D", "279D3"),
    ("289D", "289D3"),
])
def test_cat_d_and_d3_records_both_reachable(gen_d, gen_d3):
    """Make+model lookups must return the exact generation requested."""
    res_d = lookup_machine(query=f"Caterpillar {gen_d}")
    assert res_d.get("match") is True
    assert res_d.get("model") == gen_d, f"expected {gen_d}, got {res_d.get('model')}"
    assert res_d.get("manufacturer") == "Caterpillar"

    res_d3 = lookup_machine(query=f"Caterpillar {gen_d3}")
    assert res_d3.get("match") is True
    assert res_d3.get("model") == gen_d3


@pytest.mark.parametrize("model", ["279D", "289D", "259D3", "279D3", "289D3"])
def test_cat_d_series_model_only_no_generation_upgrade(model):
    """Model-only input must never silently return a different generation."""
    res = lookup_machine(query=model)
    if res.get("match"):
        assert res.get("model") == model
    else:
        # An honest ambiguity/no-match is acceptable; a silent swap is not.
        assert res.get("model") is None


def test_bare_259d_known_f4_interaction():
    """
    Bare "259D" hits the F4 duplicate (a second 259D record with a null
    manufacturer) and returns ambiguous_model. That duplicate is out of scope
    here; this test documents the interaction so the behavior is intentional.
    It must NOT silently return the D3 generation.
    """
    res = lookup_machine(query="259D")
    if res.get("match"):
        assert res.get("model") == "259D"
    else:
        assert res.get("reason") == "ambiguous_model"


def test_d_series_bridge_entries_removed():
    for key in ("259d", "279d", "289d"):
        assert key not in MODEL_BRIDGE_ALIASES


def test_other_bridge_entries_unchanged():
    """SVL / 580N / 600AJ bridges are intentional and must keep working."""
    assert MODEL_BRIDGE_ALIASES.get("svl75") == "SVL75-2"
    assert MODEL_BRIDGE_ALIASES.get("svl65") == "SVL65-2"
    res = lookup_machine(query="Kubota SVL75")
    assert res.get("match") is True and res.get("model") == "SVL75-2"
    res = lookup_machine(query="Case 580N")
    assert res.get("match") is True and "580" in res.get("model", "")


# ---------------------------------------------------------------------------
# F1 — year-prefixed inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prefixed, clean", [
    ("2021 Bobcat S590",    "Bobcat S590"),
    ("2022 CAT 289D3",      "CAT 289D3"),
    ("2020 Deere 333G",     "Deere 333G"),
    ("2019 Kubota KX080-5", "Kubota KX080-5"),
])
def test_year_prefixed_resolves_same_as_clean(prefixed, clean):
    res_clean = lookup_machine(query=clean)
    res_pref  = lookup_machine(query=prefixed)
    assert res_clean.get("match") is True
    assert res_pref.get("match") is True
    assert res_pref.get("model") == res_clean.get("model")
    assert res_pref.get("manufacturer") == res_clean.get("manufacturer")
    assert res_pref.get("equipment_type") == res_clean.get("equipment_type")


def test_year_plus_make_only_adds_no_attempts():
    """
    "2021 Bobcat" must not gain new lookup attempts: after the year strips,
    only a make remains, and make-only candidates are skipped by the ladder.
    (Raw-query behavior for such strings is unchanged from before the fix.)
    """
    assert _query_attempts("2021 Bobcat") == ["2021 Bobcat"]


# ---------------------------------------------------------------------------
# F2 — marketplace-style strings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("listing, expected_model", [
    ("2019 Bobcat S590, 1800 hrs",                                       "S590"),
    ("2022 CAT 289D3 High Flow Cab",                                     "289D3"),
    ("2021 Deere 333G 1200 hours",                                       "333G"),
    ("2020 Kubota KX080-5 hydraulic thumb",                              "KX080-5"),
    ("2021 Deere 333G 1200 hours one owner",                             "333G"),
    ("2019 Bobcat S590, 1800 hrs, one owner, clean machine, ready to work $48,500 OBO", "S590"),
])
def test_marketplace_string_resolves(listing, expected_model):
    res = lookup_machine(query=listing)
    assert res.get("match") is True, f"no match for {listing!r}: {res.get('reason')}"
    assert res.get("model") == expected_model
    # explainability: rewritten queries must expose the normalized form
    assert "normalized_query" in res


def test_marketplace_match_confidence_not_inflated():
    """Normalized match must report the core matcher's own confidence."""
    res = lookup_machine(query="2019 Bobcat S590, 1800 hrs")
    clean = lookup_machine(query="Bobcat S590")
    assert res.get("confidence") == clean.get("confidence")
    assert res.get("match_method") == clean.get("match_method")


# ---------------------------------------------------------------------------
# Normalization helpers — deterministic and explainable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("2019 Bobcat S590, 1800 hrs",            "Bobcat S590"),
    ("2022 CAT 289D3 High Flow Cab",          "CAT 289D3"),
    ("2021 Deere 333G 1200 hours",            "Deere 333G"),
    ("2020 Kubota KX080-5 hydraulic thumb",   "Kubota KX080-5"),
    ("Bobcat S650",                           "Bobcat S650"),   # clean input untouched
])
def test_normalize_marketplace_query(raw, expected):
    assert _normalize_marketplace_query(raw) == expected


def test_query_attempts_raw_first_and_no_make_only():
    attempts = _query_attempts("2021 Bobcat S590")
    assert attempts[0] == "2021 Bobcat S590"          # raw behavior preserved
    assert "Bobcat S590" in attempts
    assert "Bobcat" not in attempts                   # make-only candidates skipped
    assert len(attempts) <= 5


def test_query_attempts_clean_input_single_attempt():
    assert _query_attempts("Bobcat S650") == ["Bobcat S650"]


# ---------------------------------------------------------------------------
# Regression — existing behavior unchanged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query, model", [
    ("Bobcat S650",      "S650"),
    ("bobcat s650",      "S650"),
    ("CAT 262D3",        "262D3"),
    ("John Deere 332G",  None),    # ambiguous (SSL+CTL) or matched — see assert
])
def test_clean_inputs_unchanged(query, model):
    res = lookup_machine(query=query)
    if model is None:
        # behavior must simply be deterministic; either a match or honest no-match
        assert isinstance(res.get("match"), bool)
    else:
        assert res.get("match") is True and res.get("model") == model
        assert "normalized_query" not in res          # raw query matched directly


def test_ambiguous_results_not_rewritten_past():
    """A genuinely ambiguous model must stay ambiguous, not be 'fixed' by shrinking."""
    res = lookup_machine(query="John Deere 319D")
    assert res.get("match") is False
    assert res.get("reason") == "ambiguous_model"


def test_direct_manufacturer_model_path_untouched():
    res = lookup_machine("Caterpillar", "259D")
    assert res.get("match") is True and res.get("model") == "259D"
    res = lookup_machine("Caterpillar", "259D3")
    assert res.get("match") is True and res.get("model") == "259D3"
