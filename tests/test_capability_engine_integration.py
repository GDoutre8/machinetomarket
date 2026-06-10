"""
tests/test_capability_engine_integration.py

Integration tests proving that capability_engine.get_capability_tags() is wired
into the listing pipeline and that its tags replace old/generic use-case labels
for V1 categories (CTL, SSL, Mini Ex, Excavator).

Tests are structured around build_use_case_payload() — the single production
call site — and verify that the correct tags flow into listing copy S4.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from dealer_input import DealerInput
from listing_use_case_enrichment import build_use_case_payload

# ─────────────────────────────────────────────────────────────────────────────
# Retired / generic labels that must never appear when CE fires
# ─────────────────────────────────────────────────────────────────────────────

_BANNED_LABELS = {
    "Earthmoving",
    "Site Prep",
    "Site Work",
    "General Purpose",
    "Versatile Machine",
    "Construction",
    "Grading & Site Prep",   # old scorer label — CE replaces with "Finish Grading"
    "Material Handling",     # generic old-scorer label — CE replaces with "Heavy Material Handling"
    "Utility Trenching",     # only banned on CTL where it's a spurious old-scorer artifact
}

# ─────────────────────────────────────────────────────────────────────────────
# CE approved tag libraries (mirrors capability_engine.py constants)
# ─────────────────────────────────────────────────────────────────────────────

_CTL_CE_TAGS = frozenset({
    "Forestry Mulching", "High-Flow Hydraulics", "Finish Grading",
    "Low Ground Pressure", "Breaker & Demolition Attachments",
    "Tight-Site Grading", "Heavy Material Handling",
    "Snow & Ice Removal", "Land Clearing", "Grade-Sensitive Work",
})
_SSL_CE_TAGS = frozenset({
    "High-Flow Hydraulics", "Heavy Material Handling", "Pallet Fork Operations",
    "Truck Loading Operations", "Brush Cutting", "Concrete & Demolition",
    "Tight-Site Grading", "Farm & Agricultural Use", "Material Handling",
})
_MINI_CE_TAGS = frozenset({
    "Utility Trenching", "Deep Utility Trenching", "Residential Foundation Work",
    "Zero-Tail Swing Access", "Hydraulic Breaker Ready", "Drainage & Grading",
    "Thumb & Attachment Ready", "Tight-Site Demo Work",
    "Landscape Excavation", "Land Clearing",
})
_EX_CE_TAGS = frozenset({
    "Foundation Excavation", "Deep Foundation Work", "Mass Excavation",
    "Utility Trenching", "Pipe & Utility Installation", "Demolition Work",
    "Slope & Embankment Grading", "Lift & Place Operations",
    "Rock Excavation", "High-Reach Demo",
})

# ─────────────────────────────────────────────────────────────────────────────
# DealerInput factories — minimal valid objects
# ─────────────────────────────────────────────────────────────────────────────

def _ctl_di(**kw) -> DealerInput:
    defaults = dict(year=2021, make="Caterpillar", model="299D3", hours=1000,
                    high_flow="yes", two_speed_travel="yes", cab_type="enclosed")
    defaults.update(kw)
    return DealerInput(**defaults)


def _ssl_di(**kw) -> DealerInput:
    defaults = dict(year=2022, make="John Deere", model="332G", hours=900,
                    high_flow="yes", two_speed_travel="yes", cab_type="enclosed")
    defaults.update(kw)
    return DealerInput(**defaults)


def _mex_di(**kw) -> DealerInput:
    defaults = dict(year=2022, make="Kubota", model="U55-5", hours=780,
                    cab_type="enclosed")
    defaults.update(kw)
    return DealerInput(**defaults)


def _ex_di(**kw) -> DealerInput:
    defaults = dict(year=2023, make="John Deere", model="210 P-Tier", hours=1420,
                    cab_type="enclosed")
    defaults.update(kw)
    return DealerInput(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# Representative resolved_specs dicts (registry schema field names)
# ─────────────────────────────────────────────────────────────────────────────

CTL_SPECS_HIGH_FLOW = {
    "rated_operating_capacity_lbs": 4972,
    "tipping_load_lbs": 9944,
    "aux_flow_standard_gpm": 30,
    "aux_flow_high_gpm": 45,
    "hydraulic_pressure_standard_psi": 4061,
    "lift_path": "vertical",
    "width_over_tires_in": 79.9,
    "bucket_hinge_pin_height_in": 131,
    "operating_weight_lbs": 11464,
    "horsepower_hp": 110,
}

CTL_SPECS_SPARSE = {
    # Minimal — only weight, no flow/pressure data → CE should return empty → fall back
    "operating_weight_lbs": 6000,
}

SSL_SPECS_TRUCK_LOADER = {
    "rated_operating_capacity_lbs": 3600,
    "tipping_load_lbs": 7200,
    "aux_flow_standard_gpm": 41.1,
    "aux_flow_high_gpm": 41.1,
    "hydraulic_pressure_standard_psi": 3450,
    "lift_path": "vertical",
    "width_over_tires_in": 72.4,
    "operating_weight_lbs": 9006,
    "horsepower_hp": 97,
}

MINI_SPECS_ZERO_TAIL = {
    "operating_weight_lbs": 6614,
    "max_dig_depth_ft": 9.08,
    "aux_flow_primary_gpm": 14.5,
    "aux_pressure_primary_psi": 2850,
    "tail_swing_type": "zero",
    "blade_width_in": 55.0,
    "auxiliary_hydraulics": True,
}

MINI_SPECS_DEEP = {
    "operating_weight_lbs": 12247,
    "max_dig_depth_ft": 11.94,
    "aux_flow_primary_gpm": 25.9,
    "aux_pressure_primary_psi": 2600,
    "tail_swing_type": "standard",
    "blade_width_in": 79.7,
    "auxiliary_hydraulics": True,
}

EX_SPECS_20TON = {
    "operating_weight_lbs": 47500,  # >= 44000 → Mass Excavation
}

EX_SPECS_SPARSE = {
    "operating_weight_lbs": 5000,   # too light for any EX rule → CE returns []
}

TELEHANDLER_SPECS = {
    "max_lift_height_ft": 42,
}


# ─────────────────────────────────────────────────────────────────────────────
# CTL tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCTLIntegration:

    def test_ce_tags_fire_for_ctl(self):
        payload = build_use_case_payload("compact_track_loader", _ctl_di(), CTL_SPECS_HIGH_FLOW)
        assert payload is not None
        tags = payload["top_use_cases_for_listing"]
        assert len(tags) >= 1
        for tag in tags:
            assert tag in _CTL_CE_TAGS, f"Unexpected CTL tag: {tag!r}"

    def test_forestry_mulching_fires_on_high_flow_ctl(self):
        """CAT 299D3 class: high flow + aux_flow_high >= 30 → Forestry Mulching."""
        payload = build_use_case_payload("compact_track_loader", _ctl_di(), CTL_SPECS_HIGH_FLOW)
        tags = payload["top_use_cases_for_listing"]
        assert "Forestry Mulching" in tags

    def test_heavy_material_handling_fires_on_large_ctl(self):
        """ROC >= 3000 lbs → Heavy Material Handling."""
        payload = build_use_case_payload("compact_track_loader", _ctl_di(), CTL_SPECS_HIGH_FLOW)
        tags = payload["top_use_cases_for_listing"]
        assert "Heavy Material Handling" in tags

    def test_no_banned_labels_in_ctl_tags(self):
        payload = build_use_case_payload("compact_track_loader", _ctl_di(), CTL_SPECS_HIGH_FLOW)
        tags = payload["top_use_cases_for_listing"]
        for tag in tags:
            assert tag not in _BANNED_LABELS, f"Banned label in CTL output: {tag!r}"

    def test_attachment_sentence_still_present_from_old_scorer(self):
        """Old scorer still runs for attachment/limitation sentences — CE only replaces use_cases."""
        payload = build_use_case_payload("compact_track_loader", _ctl_di(), CTL_SPECS_HIGH_FLOW)
        assert "attachment_sentence" in payload
        assert "limitation_sentence" in payload

    def test_fallback_to_old_scorer_when_ce_returns_empty(self):
        """With sparse specs, CE returns [] → fall back to old scorer use_cases."""
        payload = build_use_case_payload("compact_track_loader", _ctl_di(), CTL_SPECS_SPARSE)
        # Payload should still exist — old scorer can produce something
        assert payload is not None
        # All tags in result must come from a known source (CE or old scorer display names)
        # The key assertion: payload key exists and is a list (not crashed)
        assert isinstance(payload["top_use_cases_for_listing"], list)


# ─────────────────────────────────────────────────────────────────────────────
# SSL tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSSLIntegration:

    def test_ce_tags_fire_for_ssl(self):
        payload = build_use_case_payload("skid_steer", _ssl_di(), SSL_SPECS_TRUCK_LOADER)
        assert payload is not None
        tags = payload["top_use_cases_for_listing"]
        assert len(tags) >= 1
        for tag in tags:
            assert tag in _SSL_CE_TAGS, f"Unexpected SSL tag: {tag!r}"

    def test_truck_loading_operations_fires_on_vertical_lift_ssl(self):
        """Vertical lift + ROC >= 2800 → Truck Loading Operations."""
        payload = build_use_case_payload("skid_steer", _ssl_di(), SSL_SPECS_TRUCK_LOADER)
        tags = payload["top_use_cases_for_listing"]
        assert "Truck Loading Operations" in tags

    def test_high_flow_hydraulics_fires_on_confirmed_hf_ssl(self):
        """high_flow='yes' + aux_flow_high >= 22 → High-Flow Hydraulics."""
        payload = build_use_case_payload("skid_steer", _ssl_di(), SSL_SPECS_TRUCK_LOADER)
        tags = payload["top_use_cases_for_listing"]
        assert "High-Flow Hydraulics" in tags

    def test_no_banned_labels_in_ssl_tags(self):
        payload = build_use_case_payload("skid_steer", _ssl_di(), SSL_SPECS_TRUCK_LOADER)
        tags = payload["top_use_cases_for_listing"]
        # "Material Handling" is in _SSL_CE_TAGS as a fallback, only banned if it came from old scorer
        # specifically check the old generic ones never appear
        generic_banned = {"Earthmoving", "Site Prep", "Site Work", "General Purpose",
                          "Versatile Machine", "Construction", "Grading & Site Prep"}
        for tag in tags:
            assert tag not in generic_banned, f"Generic label in SSL output: {tag!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Mini Excavator tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMiniExIntegration:

    def test_ce_tags_fire_for_mini_ex(self):
        payload = build_use_case_payload("mini_excavator", _mex_di(), MINI_SPECS_ZERO_TAIL)
        assert payload is not None
        tags = payload["top_use_cases_for_listing"]
        assert len(tags) >= 1
        for tag in tags:
            assert tag in _MINI_CE_TAGS, f"Unexpected Mini Ex tag: {tag!r}"

    def test_zero_tail_swing_access_fires(self):
        """tail_swing_type='zero' → Zero-Tail Swing Access."""
        payload = build_use_case_payload("mini_excavator", _mex_di(), MINI_SPECS_ZERO_TAIL)
        tags = payload["top_use_cases_for_listing"]
        assert "Zero-Tail Swing Access" in tags

    def test_deep_utility_trenching_fires_on_deep_dig(self):
        """max_dig_depth_ft >= 9.0 → Deep Utility Trenching."""
        payload = build_use_case_payload("mini_excavator", _mex_di(), MINI_SPECS_DEEP)
        tags = payload["top_use_cases_for_listing"]
        assert "Deep Utility Trenching" in tags

    def test_no_banned_labels_in_mini_ex_tags(self):
        payload = build_use_case_payload("mini_excavator", _mex_di(), MINI_SPECS_DEEP)
        tags = payload["top_use_cases_for_listing"]
        generic_banned = {"Earthmoving", "Site Prep", "Site Work", "General Purpose",
                          "Versatile Machine", "Construction", "Excavation & Digging"}
        for tag in tags:
            assert tag not in generic_banned, f"Generic label in Mini Ex output: {tag!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Full-Size Excavator tests (new V1 support)
# ─────────────────────────────────────────────────────────────────────────────

class TestExcavatorIntegration:

    def test_ce_tags_fire_for_excavator_type(self):
        """Registry uses 'excavator' as equipment_type."""
        payload = build_use_case_payload("excavator", _ex_di(), EX_SPECS_20TON)
        assert payload is not None
        tags = payload["top_use_cases_for_listing"]
        assert len(tags) >= 1
        for tag in tags:
            assert tag in _EX_CE_TAGS, f"Unexpected Excavator tag: {tag!r}"

    def test_ce_tags_fire_for_large_excavator_type(self):
        """DealerInput / showcase uses 'large_excavator'."""
        payload = build_use_case_payload("large_excavator", _ex_di(), EX_SPECS_20TON)
        assert payload is not None
        tags = payload["top_use_cases_for_listing"]
        assert len(tags) >= 1

    def test_mass_excavation_fires_on_20ton_class(self):
        """operating_weight_lbs >= 44000 → Mass Excavation."""
        payload = build_use_case_payload("excavator", _ex_di(), EX_SPECS_20TON)
        tags = payload["top_use_cases_for_listing"]
        assert "Mass Excavation" in tags

    def test_excavator_returns_none_when_ce_returns_empty(self):
        """Sparse specs produce no CE tags → payload is None (no scorer fallback for EX)."""
        payload = build_use_case_payload("excavator", _ex_di(), EX_SPECS_SPARSE)
        assert payload is None

    def test_no_banned_labels_in_excavator_tags(self):
        payload = build_use_case_payload("excavator", _ex_di(), EX_SPECS_20TON)
        tags = payload["top_use_cases_for_listing"]
        generic_banned = {"Earthmoving", "Site Prep", "Foundation Work",
                          "Site Excavation", "General Purpose"}
        for tag in tags:
            assert tag not in generic_banned, f"Generic label in Excavator output: {tag!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Fallback: readiness pool still works when CE returns empty
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessPoolFallback:

    def test_ctl_fallback_returns_list_not_none(self):
        """Sparse CTL specs → CE returns [], old scorer runs, payload is a list."""
        payload = build_use_case_payload("compact_track_loader", _ctl_di(), CTL_SPECS_SPARSE)
        assert payload is not None
        assert isinstance(payload["top_use_cases_for_listing"], list)

    def test_ce_failure_does_not_crash_ctl(self):
        """If CE import raises, old scorer runs as fallback."""
        with patch("listing_use_case_enrichment._ce_tags_safe", return_value=[]):
            payload = build_use_case_payload("compact_track_loader", _ctl_di(), CTL_SPECS_HIGH_FLOW)
        assert payload is not None
        assert isinstance(payload["top_use_cases_for_listing"], list)

    def test_ce_failure_does_not_crash_ssl(self):
        with patch("listing_use_case_enrichment._ce_tags_safe", return_value=[]):
            payload = build_use_case_payload("skid_steer", _ssl_di(), SSL_SPECS_TRUCK_LOADER)
        assert payload is not None
        assert isinstance(payload["top_use_cases_for_listing"], list)

    def test_ce_failure_does_not_crash_mini_ex(self):
        with patch("listing_use_case_enrichment._ce_tags_safe", return_value=[]):
            payload = build_use_case_payload("mini_excavator", _mex_di(), MINI_SPECS_DEEP)
        assert payload is not None
        assert isinstance(payload["top_use_cases_for_listing"], list)


# ─────────────────────────────────────────────────────────────────────────────
# Unsupported categories unchanged
# ─────────────────────────────────────────────────────────────────────────────

class TestUnsupportedCategoriesUnchanged:

    def test_telehandler_not_affected_by_ce(self):
        """Telehandler uses inline logic — CE is never called, output unchanged."""
        di = DealerInput(year=2018, make="SkyTrak", model="8042", hours=2400,
                         cab_type="enclosed", has_stabilizers=True)
        payload = build_use_case_payload("telehandler", di, TELEHANDLER_SPECS)
        assert payload is not None
        tags = payload["top_use_cases_for_listing"]
        # Telehandler inline logic produces its own fixed labels
        assert any("Placement" in t or "Pallet" in t or "Loading" in t for t in tags), \
            f"Unexpected telehandler tags: {tags}"
        # None of the CE libraries' tags should appear
        all_ce_tags = _CTL_CE_TAGS | _SSL_CE_TAGS | _MINI_CE_TAGS | _EX_CE_TAGS
        for tag in tags:
            assert tag not in all_ce_tags, f"CE tag leaked into telehandler: {tag!r}"

    def test_unsupported_type_returns_none(self):
        """Unknown equipment type → None (unchanged behavior)."""
        di = DealerInput(year=2020, make="Generic", model="X100", hours=500)
        result = build_use_case_payload("unknown_type", di, {})
        assert result is None

    def test_none_equipment_type_returns_none(self):
        di = DealerInput(year=2020, make="Generic", model="X100", hours=500)
        result = build_use_case_payload(None, di, {})
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Listing copy integration — S4 sentence uses CE tags
# ─────────────────────────────────────────────────────────────────────────────

class TestListingCopyS4:
    """
    Verify that CE tags flow through to listing_copy_v3's S4 application sentence,
    replacing the readiness-pool fallback strings.
    """

    def test_ctl_listing_copy_uses_ce_tags_not_pool(self):
        from listing_builder import build_listing_text

        di = _ctl_di(asking_price=89500, track_condition="85%")
        specs = {**CTL_SPECS_HIGH_FLOW, "net_hp": 110, "roc_lb": 4972,
                 "operating_weight_lb": 11464, "hydraulic_flow_gpm": 30}
        payload = build_use_case_payload("compact_track_loader", di, CTL_SPECS_HIGH_FLOW)
        text = build_listing_text(di, specs,
                                  use_case_payload=payload,
                                  equipment_type="compact_track_loader")

        # CE tags should appear in lowercase in the S4 sentence
        text_lower = text.lower()
        assert ("forestry mulching" in text_lower
                or "heavy material handling" in text_lower
                or "finish grading" in text_lower
                or "high-flow hydraulics" in text_lower), \
            f"No CE tag found in CTL listing copy S4.\n---\n{text}"

        # Old generic pool phrases must not appear when CE fired
        assert "production site work, earthmoving" not in text_lower, \
            "Old readiness pool phrase leaked into CTL listing copy."

    def test_ssl_listing_copy_uses_ce_tags_not_pool(self):
        from listing_builder import build_listing_text

        di = _ssl_di(asking_price=78500, tire_condition="85%")
        specs = {**SSL_SPECS_TRUCK_LOADER, "net_hp": 97, "roc_lb": 3600,
                 "tipping_load_lb": 7200, "operating_weight_lb": 9006,
                 "hydraulic_flow_gpm": 41.1}
        payload = build_use_case_payload("skid_steer", di, SSL_SPECS_TRUCK_LOADER)
        text = build_listing_text(di, specs,
                                  use_case_payload=payload,
                                  equipment_type="skid_steer_loader")

        text_lower = text.lower()
        assert ("truck loading operations" in text_lower
                or "high-flow hydraulics" in text_lower
                or "pallet fork operations" in text_lower
                or "heavy material handling" in text_lower), \
            f"No CE tag found in SSL listing copy S4.\n---\n{text}"

    def test_excavator_listing_copy_uses_ce_tags(self):
        from listing_builder import build_listing_text

        di = _ex_di(asking_price=265000, undercarriage_percent_remaining=80)
        specs = {"net_hp": 156, "operating_weight_lb": 49500}
        payload = build_use_case_payload("excavator", di, EX_SPECS_20TON)
        # payload must exist (CE fires "Mass Excavation" from weight alone)
        assert payload is not None
        text = build_listing_text(di, specs,
                                  use_case_payload=payload,
                                  equipment_type="large_excavator")

        text_lower = text.lower()
        assert "mass excavation" in text_lower, \
            f"'Mass Excavation' not found in excavator listing copy.\n---\n{text}"

        # Must not fall back to readiness-pool phrase
        assert "foundation work, utility trenching, and earthmoving" not in text_lower, \
            "Old readiness pool phrase leaked into excavator listing copy."
