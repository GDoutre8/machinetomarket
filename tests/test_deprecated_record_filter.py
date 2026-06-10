"""
Tests for deprecated-tier registry record filtering in the lookup layer.

Covers VF-01 and VF-02 from the MTM registry error backlog:
  VF-01 — toro_dingo_tx700 (deprecated_ambiguous_parent) must not be returned by lookup
  VF-02 — bobcat_s850_doosan (DEPRECATED) must not be returned by lookup

Regression tests confirm that sibling production-tier records still resolve correctly.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mtm_registry_lookup import (  # noqa: E402
    _DEPRECATED_REGISTRY_TIERS,
    lookup_machine,
    search_by_model,
)


# ---------------------------------------------------------------------------
# Constant sanity
# ---------------------------------------------------------------------------

def test_deprecated_tiers_constant_contains_expected_values():
    assert "DEPRECATED" in _DEPRECATED_REGISTRY_TIERS
    assert "deprecated_ambiguous_parent" in _DEPRECATED_REGISTRY_TIERS


# ---------------------------------------------------------------------------
# VF-02 — bobcat_s850_doosan (DEPRECATED tier) must not surface in lookup
# ---------------------------------------------------------------------------

def test_bobcat_s850_doosan_not_returned_by_lookup():
    result = lookup_machine(manufacturer="Bobcat", model="S850", equipment_type="skid_steer")
    slug = result.get("model_slug", "")
    assert slug != "bobcat_s850_doosan", (
        f"Deprecated record bobcat_s850_doosan was returned: {result}"
    )


def test_bobcat_s850_still_resolves_via_production_record():
    """The production sibling (bobcat_s850_kubota) must still resolve."""
    result = lookup_machine(manufacturer="Bobcat", model="S850", equipment_type="skid_steer")
    assert result.get("match") is True, f"Expected match=True, got: {result}"
    assert result.get("model_slug") == "bobcat_s850_kubota", (
        f"Expected bobcat_s850_kubota, got: {result.get('model_slug')}"
    )


def test_bobcat_s850_doosan_not_in_search_by_model():
    results = search_by_model("S850", equipment_type="skid_steer")
    slugs = [r.get("model_slug") for r in results]
    assert "bobcat_s850_doosan" not in slugs, (
        f"Deprecated record bobcat_s850_doosan appeared in search_by_model: {slugs}"
    )


# ---------------------------------------------------------------------------
# VF-01 — toro_dingo_tx700 (deprecated_ambiguous_parent) must not surface
# ---------------------------------------------------------------------------

def test_toro_dingo_tx700_not_returned_by_lookup():
    result = lookup_machine(manufacturer="Toro", model="TX700", equipment_type="ctl")
    slug = result.get("model_slug", "")
    assert slug != "toro_dingo_tx700", (
        f"Deprecated record toro_dingo_tx700 was returned: {result}"
    )


def test_toro_dingo_tx700_not_in_search_by_model():
    results = search_by_model("TX700", equipment_type="ctl")
    slugs = [r.get("model_slug") for r in results]
    assert "toro_dingo_tx700" not in slugs, (
        f"Deprecated record toro_dingo_tx700 appeared in search_by_model: {slugs}"
    )


# ---------------------------------------------------------------------------
# Non-deprecated Toro TX700 variants must still resolve
# ---------------------------------------------------------------------------

def test_toro_dingo_tx700n_resolves():
    result = lookup_machine(manufacturer="Toro", model="TX700N", equipment_type="ctl")
    assert result.get("match") is True, f"Expected match=True for TX700N, got: {result}"
    assert result.get("model_slug") == "toro_dingo_tx700n", (
        f"Expected toro_dingo_tx700n, got: {result.get('model_slug')}"
    )


def test_toro_dingo_tx700w_resolves():
    result = lookup_machine(manufacturer="Toro", model="TX700W", equipment_type="ctl")
    assert result.get("match") is True, f"Expected match=True for TX700W, got: {result}"
    assert result.get("model_slug") == "toro_dingo_tx700w", (
        f"Expected toro_dingo_tx700w, got: {result.get('model_slug')}"
    )


# ---------------------------------------------------------------------------
# Regression — unrelated production records unaffected
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("manufacturer,model,equipment_type,expected_slug", [
    ("Bobcat", "S590", "skid_steer", "bobcat_s590"),
    ("Bobcat", "T590", "ctl", "bobcat_t590"),
    ("Caterpillar", "299D3", "ctl", "cat_299d3"),
    ("John Deere", "317G", "ctl", "jd_317g"),
    ("Case", "SR240", "skid_steer", "case_sr240"),
])
def test_production_records_unaffected(manufacturer, model, equipment_type, expected_slug):
    result = lookup_machine(manufacturer=manufacturer, model=model, equipment_type=equipment_type)
    assert result.get("match") is True, (
        f"{manufacturer} {model}: expected match=True, got: {result}"
    )
    assert result.get("model_slug") == expected_slug, (
        f"{manufacturer} {model}: expected {expected_slug}, got: {result.get('model_slug')}"
    )
