"""
tests/test_capability_engine.py

Unit tests for capability_engine.py — V1 (CTL / SSL / Mini Ex / Full-Size Ex).
"""

import pytest
from capability_engine import (
    get_capability_tags,
    _CTL_LIBRARY,
    _SSL_LIBRARY,
    _MINI_EX_LIBRARY,
    _EX_LIBRARY,
    _RETIRED_TAGS,
    _CATEGORY_LIBRARIES,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — representative machine profiles
# ─────────────────────────────────────────────────────────────────────────────

# CTL — high-flow forestry machine (e.g. CAT 299D3 or Bobcat T870)
CTL_FORESTRY = {
    "specs": {
        "rated_operating_capacity_lbs": 4200,
        "aux_flow_standard_gpm": 26,
        "aux_flow_high_gpm": 40,
        "hydraulic_pressure_standard_psi": 3600,
        "lift_path": "vertical",
        "width_over_tires_in": 76.0,
        "operating_weight_lbs": 12800,
    },
    "flags": {"high_flow_available": True, "two_speed_available": True},
}

# CTL — tight-site vertical-lift, no high flow (e.g. Takeuchi TL6R)
CTL_TIGHT_RADIAL = {
    "specs": {
        "rated_operating_capacity_lbs": 2800,
        "aux_flow_standard_gpm": 18,
        "aux_flow_high_gpm": None,
        "hydraulic_pressure_standard_psi": 3200,
        "lift_path": "radial",
        "width_over_tires_in": 62.0,
        "operating_weight_lbs": 7200,
    },
    "flags": {"high_flow_available": False, "two_speed_available": False},
}

# CTL — mid-flow high-flow machine (HFH threshold but not FM)
CTL_HIGH_FLOW_MID = {
    "specs": {
        "rated_operating_capacity_lbs": 3100,
        "aux_flow_standard_gpm": 24,
        "aux_flow_high_gpm": 25,
        "hydraulic_pressure_standard_psi": 3400,
        "lift_path": "vertical",
        "width_over_tires_in": 72.0,
        "operating_weight_lbs": 10500,
    },
    "flags": {"high_flow_available": True, "two_speed_available": True},
}

# SSL — high-ROC vertical-lift, high-flow (e.g. JD 332G vertical)
SSL_TRUCK_LOADER = {
    "specs": {
        "rated_operating_capacity_lbs": 3200,
        "lift_path": "vertical",
        "aux_flow_standard_gpm": 22,
        "aux_flow_high_gpm": 35,
        "hydraulic_pressure_standard_psi": 3600,
        "width_over_tires_in": 66.0,
        "operating_weight_lbs": 9800,
    },
    "flags": {"high_flow_available": True, "two_speed_available": True},
}

# SSL — small radial-lift farm machine
SSL_FARM = {
    "specs": {
        "rated_operating_capacity_lbs": 1750,
        "lift_path": "radial",
        "aux_flow_standard_gpm": 14,
        "aux_flow_high_gpm": None,
        "hydraulic_pressure_standard_psi": 2700,
        "width_over_tires_in": 60.0,
        "operating_weight_lbs": 5200,
    },
    "flags": {"high_flow_available": False, "two_speed_available": False},
}

# SSL — vertical-lift, high-ROC but no high-flow
SSL_PALLET_ONLY = {
    "specs": {
        "rated_operating_capacity_lbs": 2600,
        "lift_path": "vertical",
        "aux_flow_standard_gpm": 21,
        "aux_flow_high_gpm": None,
        "hydraulic_pressure_standard_psi": 3500,
        "width_over_tires_in": 68.0,
        "operating_weight_lbs": 8200,
    },
    "flags": {"high_flow_available": False, "two_speed_available": True},
}

# Mini Ex — zero-tail, deep dig (e.g. Bobcat E32)
MINI_ZERO_DEEP = {
    "specs": {
        "operating_weight_lbs": 7000,
        "max_dig_depth_ft": 9.5,
        "aux_flow_primary_gpm": 15.9,
        "aux_pressure_primary_psi": 2844,
        "tail_swing_type": "zero",
        "blade_width_in": 59.1,
        "bucket_breakout_force_lbs": 6400,
        "auxiliary_hydraulics": True,
    },
    "flags": {},
}

# Mini Ex — compact landscaping machine (e.g. Bobcat E17 / Kubota U17)
MINI_LANDSCAPE = {
    "specs": {
        "operating_weight_lbs": 3774,
        "max_dig_depth_ft": 7.32,
        "hydraulic_flow_gpm": 8.2,
        "hydraulic_pressure_psi": 2700,
        "tail_swing_type": "zero",
        "blade_width_in": 39.4,
        "bucket_breakout_force_lbs": 3530,
        "auxiliary_hydraulics": True,
    },
    "flags": {},
}

# Mini Ex — mid-size no-zero-tail (e.g. Kubota KX057)
MINI_MID_STANDARD_TAIL = {
    "specs": {
        "operating_weight_lbs": 12600,
        "max_dig_depth_ft": 11.5,
        "aux_flow_primary_gpm": 20.1,
        "aux_pressure_primary_psi": 3200,
        "tail_swing_type": "standard",
        "blade_width_in": 79.0,
        "bucket_breakout_force_lbs": 11300,
        "auxiliary_hydraulics": True,
    },
    "flags": {},
}

# Full-Size Ex — 20-ton class (e.g. CAT 320GC)
EX_MASS = {
    "specs": {
        "operating_weight_lbs": 47500,
        "max_dig_depth_in": 243,
        "hydraulic_pressure_psi": 4990,
        "bucket_dig_force_lbf": 26200,
        "max_reach_ground_in": 388,
        "max_dump_height_in": 269,
        "boom_type": "mono_boom",
        "tail_swing_type": "standard_tail_swing",
    },
    "flags": {},
}

# Full-Size Ex — mid-class utility (e.g. Cat 320 / JD 210G range)
EX_UTILITY = {
    "specs": {
        "operating_weight_lbs": 30000,
        "max_dig_depth_in": 215,
        "hydraulic_pressure_psi": 4200,
        "bucket_dig_force_lbf": 22000,
        "max_reach_ground_in": 310,
        "max_dump_height_in": 220,
        "boom_type": "mono_boom",
    },
    "flags": {},
}

# Full-Size Ex — high-reach demo configuration
EX_HIGH_REACH = {
    "specs": {
        "operating_weight_lbs": 95000,
        "max_dig_depth_in": 350,
        "hydraulic_pressure_psi": 5000,
        "bucket_dig_force_lbf": 35000,
        "max_reach_ground_in": 420,
        "max_dump_height_in": 310,
        "boom_type": "high_reach_demolition",
    },
    "flags": {},
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def run(equipment_type: str, profile: dict) -> list:
    return get_capability_tags(
        equipment_type,
        profile["specs"],
        profile.get("flags"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# General contract tests (apply to all categories)
# ─────────────────────────────────────────────────────────────────────────────

class TestGeneralContracts:
    """Engine output must satisfy these invariants for every machine."""

    CASES = [
        ("compact_track_loader", CTL_FORESTRY),
        ("compact_track_loader", CTL_TIGHT_RADIAL),
        ("compact_track_loader", CTL_HIGH_FLOW_MID),
        ("skid_steer_loader",    SSL_TRUCK_LOADER),
        ("skid_steer_loader",    SSL_FARM),
        ("skid_steer_loader",    SSL_PALLET_ONLY),
        ("mini_excavator",       MINI_ZERO_DEEP),
        ("mini_excavator",       MINI_LANDSCAPE),
        ("mini_excavator",       MINI_MID_STANDARD_TAIL),
        ("excavator",            EX_MASS),
        ("excavator",            EX_UTILITY),
        ("excavator",            EX_HIGH_REACH),
    ]

    @pytest.mark.parametrize("eq_type,profile", CASES)
    def test_no_retired_tags(self, eq_type, profile):
        tags = run(eq_type, profile)
        for tag in tags:
            assert tag not in _RETIRED_TAGS, f"Retired tag emitted: {tag!r}"

    @pytest.mark.parametrize("eq_type,profile", CASES)
    def test_no_duplicate_tags(self, eq_type, profile):
        tags = run(eq_type, profile)
        assert len(tags) == len(set(tags)), f"Duplicate tags: {tags}"

    @pytest.mark.parametrize("eq_type,profile", CASES)
    def test_tags_in_approved_library(self, eq_type, profile):
        tags = run(eq_type, profile)
        library = _CATEGORY_LIBRARIES[
            {"compact_track_loader": "CTL",
             "skid_steer_loader": "SSL",
             "mini_excavator": "MINI",
             "excavator": "EX"}[eq_type]
        ]
        for tag in tags:
            assert tag in library, f"{tag!r} not in {eq_type} library"

    @pytest.mark.parametrize("eq_type,profile", CASES)
    def test_count_between_1_and_5(self, eq_type, profile):
        tags = run(eq_type, profile)
        assert 1 <= len(tags) <= 5, f"Tag count {len(tags)} out of range: {tags}"

    @pytest.mark.parametrize("eq_type,profile", CASES)
    def test_deterministic(self, eq_type, profile):
        first = run(eq_type, profile)
        second = run(eq_type, profile)
        assert first == second, "Non-deterministic output detected"


# ─────────────────────────────────────────────────────────────────────────────
# CTL — specific rule tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCTL:

    def test_forestry_mulching_fires_above_30gpm(self):
        tags = run("compact_track_loader", CTL_FORESTRY)
        assert "Forestry Mulching" in tags

    def test_forestry_mulching_suppresses_high_flow_hydraulics(self):
        tags = run("compact_track_loader", CTL_FORESTRY)
        assert "High-Flow Hydraulics" not in tags, (
            "Forestry Mulching and High-Flow Hydraulics are same concept group"
        )

    def test_high_flow_hydraulics_fires_20_to_29gpm(self):
        tags = run("compact_track_loader", CTL_HIGH_FLOW_MID)
        assert "High-Flow Hydraulics" in tags
        assert "Forestry Mulching" not in tags

    def test_high_flow_hydraulics_suppresses_land_clearing(self):
        tags = run("compact_track_loader", CTL_HIGH_FLOW_MID)
        assert "Land Clearing" not in tags, (
            "Land Clearing must not co-fire with High-Flow Hydraulics"
        )

    def test_land_clearing_fires_when_high_flow_below_20gpm(self):
        profile = {
            "specs": {
                "rated_operating_capacity_lbs": 2500,
                "aux_flow_standard_gpm": 16,
                "aux_flow_high_gpm": 15,
                "hydraulic_pressure_standard_psi": 3000,
                "lift_path": "radial",
                "width_over_tires_in": 72.0,
                "operating_weight_lbs": 8500,
            },
            "flags": {"high_flow_available": True, "two_speed_available": False},
        }
        tags = run("compact_track_loader", profile)
        assert "Land Clearing" in tags
        assert "High-Flow Hydraulics" not in tags
        assert "Forestry Mulching" not in tags

    def test_heavy_material_handling_fires_at_3000_roc(self):
        tags = run("compact_track_loader", CTL_FORESTRY)
        assert "Heavy Material Handling" in tags

    def test_finish_grading_fires_vertical_high_roc(self):
        tags = run("compact_track_loader", CTL_FORESTRY)
        assert "Finish Grading" in tags

    def test_grade_sensitive_work_fires_vertical_lower_roc(self):
        profile = {
            "specs": {
                "rated_operating_capacity_lbs": 2400,
                "aux_flow_standard_gpm": 18,
                "aux_flow_high_gpm": None,
                "hydraulic_pressure_standard_psi": 3000,
                "lift_path": "vertical",
                "width_over_tires_in": 70.0,
                "operating_weight_lbs": 8000,
            },
            "flags": {"high_flow_available": False, "two_speed_available": False},
        }
        tags = run("compact_track_loader", profile)
        assert "Grade-Sensitive Work" in tags
        assert "Finish Grading" not in tags

    def test_finish_grading_suppresses_grade_sensitive_work(self):
        tags = run("compact_track_loader", CTL_FORESTRY)
        assert "Grade-Sensitive Work" not in tags, (
            "Finish Grading and Grade-Sensitive Work are same concept group"
        )

    def test_tight_site_grading_fires_narrow_machine(self):
        tags = run("compact_track_loader", CTL_TIGHT_RADIAL)
        assert "Tight-Site Grading" in tags

    def test_tight_site_grading_does_not_fire_wide_machine(self):
        tags = run("compact_track_loader", CTL_FORESTRY)
        assert "Tight-Site Grading" not in tags  # CTL_FORESTRY width = 76 in

    def test_no_high_flow_tags_when_flag_false(self):
        tags = run("compact_track_loader", CTL_TIGHT_RADIAL)
        assert "Forestry Mulching" not in tags
        assert "High-Flow Hydraulics" not in tags
        assert "Land Clearing" not in tags

    def test_short_code_ctl_accepted(self):
        tags = get_capability_tags("CTL", CTL_FORESTRY["specs"], CTL_FORESTRY["flags"])
        assert len(tags) >= 1

    def test_low_ground_pressure_does_not_fire_without_field(self):
        tags = run("compact_track_loader", CTL_FORESTRY)
        assert "Low Ground Pressure" not in tags

    def test_low_ground_pressure_fires_with_field(self):
        # Use a minimal CTL profile so LGP can reach top-5.
        profile = {
            "specs": {
                "rated_operating_capacity_lbs": 2200,
                "aux_flow_standard_gpm": 16,
                "aux_flow_high_gpm": None,
                "hydraulic_pressure_standard_psi": 2800,
                "lift_path": "radial",
                "width_over_tires_in": 70.0,
                "operating_weight_lbs": 7500,
                "ground_pressure_psi": 3.8,
            },
            "flags": {"high_flow_available": False, "two_speed_available": False},
        }
        tags = run("compact_track_loader", profile)
        assert "Low Ground Pressure" in tags

    def test_snow_ice_removal_fires_above_2800_roc(self):
        # ROC >= 2800 is sufficient; two_speed is no longer required.
        tags = run("compact_track_loader", CTL_FORESTRY)
        assert "Snow & Ice Removal" in tags  # ROC 4200

        profile_no_two_spd = {
            "specs": CTL_FORESTRY["specs"],
            "flags": {"high_flow_available": True, "two_speed_available": False},
        }
        tags2 = run("compact_track_loader", profile_no_two_spd)
        assert "Snow & Ice Removal" in tags2  # still fires — two_speed not required

    def test_snow_ice_removal_does_not_fire_below_2800_roc(self):
        profile = {
            "specs": {
                "rated_operating_capacity_lbs": 2700,
                "aux_flow_standard_gpm": 16,
                "aux_flow_high_gpm": None,
                "hydraulic_pressure_standard_psi": 3000,
                "lift_path": "radial",
                "width_over_tires_in": 72.0,
                "operating_weight_lbs": 8000,
            },
            "flags": {"high_flow_available": False, "two_speed_available": True},
        }
        tags = run("compact_track_loader", profile)
        assert "Snow & Ice Removal" not in tags


# ─────────────────────────────────────────────────────────────────────────────
# SSL — specific rule tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSSL:

    def test_truck_loading_fires_high_roc_vertical(self):
        tags = run("skid_steer_loader", SSL_TRUCK_LOADER)
        assert "Truck Loading Operations" in tags

    def test_truck_loading_suppresses_heavy_material_handling(self):
        tags = run("skid_steer_loader", SSL_TRUCK_LOADER)
        assert "Heavy Material Handling" not in tags, (
            "Truck Loading Ops and Heavy Material Handling are same concept group"
        )

    def test_heavy_material_handling_fires_without_truck_loading(self):
        tags = run("skid_steer_loader", SSL_PALLET_ONLY)
        assert "Heavy Material Handling" in tags
        assert "Truck Loading Operations" not in tags  # ROC 2600, threshold 2800

    def test_high_flow_hydraulics_fires(self):
        tags = run("skid_steer_loader", SSL_TRUCK_LOADER)
        assert "High-Flow Hydraulics" in tags

    def test_pallet_fork_operations_fires_vertical_lift(self):
        tags = run("skid_steer_loader", SSL_TRUCK_LOADER)
        assert "Pallet Fork Operations" in tags  # vertical lift, ROC 3200

    def test_pallet_fork_does_not_fire_radial_lift(self):
        profile = {
            "specs": {
                "rated_operating_capacity_lbs": 2200,  # >= 1800 but radial lift
                "lift_path": "radial",
                "aux_flow_standard_gpm": 18,
                "aux_flow_high_gpm": None,
                "hydraulic_pressure_standard_psi": 3000,
                "width_over_tires_in": 68.0,
                "operating_weight_lbs": 7000,
            },
            "flags": {"high_flow_available": False},
        }
        tags = run("skid_steer_loader", profile)
        assert "Pallet Fork Operations" not in tags

    def test_brush_cutting_fires_with_sufficient_aux_flow(self):
        tags = run("skid_steer_loader", SSL_FARM)
        assert "Brush Cutting" in tags  # aux_std 14 = exact threshold

    def test_farm_agricultural_fires_for_small_light_machine(self):
        tags = run("skid_steer_loader", SSL_FARM)
        assert "Farm & Agricultural Use" in tags

    def test_farm_does_not_fire_for_heavy_machine(self):
        tags = run("skid_steer_loader", SSL_TRUCK_LOADER)
        assert "Farm & Agricultural Use" not in tags  # weight 9800, ROC 3200

    def test_tight_site_grading_fires_narrow_ssl(self):
        profile = {
            "specs": {
                **SSL_FARM["specs"],
                "width_over_tires_in": 60.0,
            },
            "flags": SSL_FARM["flags"],
        }
        tags = run("skid_steer_loader", profile)
        assert "Tight-Site Grading" in tags

    def test_material_handling_fallback_not_in_position_0_or_1(self):
        # SSL_FARM: ROC 1750 qualifies for Material Handling fallback.
        # Other tags should occupy positions 0 and 1 first.
        tags = run("skid_steer_loader", SSL_FARM)
        if "Material Handling" in tags:
            idx = tags.index("Material Handling")
            assert idx >= 2, f"Material Handling at position {idx} (must be >= 2)"

    def test_material_handling_fallback_is_ssl_only(self):
        # Material Handling must not appear for CTL (not in CTL library)
        for profile in [CTL_TIGHT_RADIAL]:
            tags = run("compact_track_loader", profile)
            assert "Material Handling" not in tags

    def test_concrete_demolition_fires_high_pressure_flow(self):
        profile = {
            "specs": {
                "rated_operating_capacity_lbs": 2200,
                "lift_path": "vertical",
                "aux_flow_standard_gpm": 23,
                "aux_flow_high_gpm": None,
                "hydraulic_pressure_standard_psi": 3500,
                "width_over_tires_in": 68.0,
                "operating_weight_lbs": 7500,
            },
            "flags": {"high_flow_available": False},
        }
        tags = run("skid_steer_loader", profile)
        assert "Concrete & Demolition" in tags

    def test_short_code_ssl_accepted(self):
        tags = get_capability_tags("ssl", SSL_TRUCK_LOADER["specs"], SSL_TRUCK_LOADER["flags"])
        assert len(tags) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Mini Excavator — specific rule tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMiniEx:

    def test_deep_utility_trenching_fires_above_9ft(self):
        tags = run("mini_excavator", MINI_ZERO_DEEP)
        assert "Deep Utility Trenching" in tags

    def test_deep_utility_trenching_suppresses_utility_trenching(self):
        tags = run("mini_excavator", MINI_ZERO_DEEP)
        assert "Utility Trenching" not in tags, (
            "Deep and standard trenching are same concept group"
        )

    def test_utility_trenching_fires_below_9ft_above_6_5ft(self):
        tags = run("mini_excavator", MINI_LANDSCAPE)
        assert "Utility Trenching" in tags
        assert "Deep Utility Trenching" not in tags  # dig_ft 7.32

    def test_zero_tail_swing_access_fires(self):
        tags = run("mini_excavator", MINI_ZERO_DEEP)
        assert "Zero-Tail Swing Access" in tags

    def test_zero_tail_swing_does_not_fire_standard_tail(self):
        tags = run("mini_excavator", MINI_MID_STANDARD_TAIL)
        assert "Zero-Tail Swing Access" not in tags

    def test_hydraulic_breaker_ready_fires_with_confirmed_aux_pressure(self):
        tags = run("mini_excavator", MINI_ZERO_DEEP)
        assert "Hydraulic Breaker Ready" in tags  # aux_pressure_primary_psi = 2844

    def test_hbr_does_not_fire_without_aux_pressure_field(self):
        # Main-circuit pressure only — no aux_pressure_primary_psi — must not fire HBR.
        profile = {
            "specs": {
                "operating_weight_lbs": 6000,
                "max_dig_depth_ft": 8.0,
                "hydraulic_flow_gpm": 18.0,
                "hydraulic_pressure_psi": 3000,
                "tail_swing_type": "zero",
                "blade_width_in": None,
                "bucket_breakout_force_lbs": 4000,
                "auxiliary_hydraulics": True,
            },
            "flags": {},
        }
        tags = run("mini_excavator", profile)
        assert "Hydraulic Breaker Ready" not in tags

    def test_drainage_grading_requires_blade(self):
        profile_no_blade = {
            "specs": {
                **MINI_ZERO_DEEP["specs"],
                "blade_width_in": None,
            },
            "flags": {},
        }
        tags_with = run("mini_excavator", MINI_ZERO_DEEP)
        tags_without = run("mini_excavator", profile_no_blade)
        assert "Drainage & Grading" in tags_with
        assert "Drainage & Grading" not in tags_without

    def test_tight_site_demo_work_fires_zero_tail_high_breakout(self):
        # Use a shallow-dig zero-tail machine so fewer high-priority tags
        # occupy the top-5 slots and Tight-Site Demo Work can appear.
        profile = {
            "specs": {
                "operating_weight_lbs": 5000,
                "max_dig_depth_ft": 5.0,   # below UT threshold — no trenching tag
                "aux_flow_primary_gpm": 10.0,
                "aux_pressure_primary_psi": 2000,  # below HBR threshold
                "tail_swing_type": "zero",
                "blade_width_in": None,    # no blade — no Drainage & Grading
                "bucket_breakout_force_lbs": 5000,
                "auxiliary_hydraulics": True,
            },
            "flags": {},
        }
        tags = run("mini_excavator", profile)
        assert "Tight-Site Demo Work" in tags

    def test_tight_site_demo_does_not_fire_low_breakout(self):
        profile = {
            "specs": {
                **MINI_LANDSCAPE["specs"],
                "bucket_breakout_force_lbs": 3000,  # below 4000
            },
            "flags": {},
        }
        tags = run("mini_excavator", profile)
        assert "Tight-Site Demo Work" not in tags

    def test_landscape_excavation_fires_small_machine(self):
        # Small machine, shallow dig, no blade, main-circuit data only (no aux_pressure_primary_psi).
        # HBR does not fire (no confirmed aux pressure). Landscape Excavation should appear.
        profile = {
            "specs": {
                "operating_weight_lbs": 3500,
                "max_dig_depth_ft": 5.5,   # qualifies for Landscape (>= 5) but not UT (< 6.5)
                "hydraulic_flow_gpm": 7.0,
                "hydraulic_pressure_psi": 2000,
                "tail_swing_type": "conventional",
                "blade_width_in": None,
                "bucket_breakout_force_lbs": 2500,
                "auxiliary_hydraulics": True,
            },
            "flags": {},
        }
        tags = run("mini_excavator", profile)
        assert "Landscape Excavation" in tags

    def test_landscape_excavation_does_not_fire_heavy_machine(self):
        tags = run("mini_excavator", MINI_MID_STANDARD_TAIL)
        assert "Landscape Excavation" not in tags  # weight 12600 > 5000

    def test_land_clearing_fires_with_high_aux_flow(self):
        # Zero-tail, shallow dig so Deep/UT don't crowd out Land Clearing.
        profile = {
            "specs": {
                "operating_weight_lbs": 7000,
                "max_dig_depth_ft": 5.0,   # below UT threshold
                "aux_flow_primary_gpm": 14.0,
                "aux_pressure_primary_psi": 2600,
                "tail_swing_type": "zero",
                "blade_width_in": None,
                "bucket_breakout_force_lbs": 5000,
                "auxiliary_hydraulics": True,
            },
            "flags": {},
        }
        tags = run("mini_excavator", profile)
        assert "Land Clearing" in tags

    def test_thumb_attachment_ready_fires_with_aux(self):
        tags = run("mini_excavator", MINI_LANDSCAPE)
        assert "Thumb & Attachment Ready" in tags

    def test_residential_foundation_fires_deep_and_heavy(self):
        tags = run("mini_excavator", MINI_MID_STANDARD_TAIL)
        assert "Residential Foundation Work" in tags  # dig 11.5ft, weight 12600

    def test_short_code_mini_accepted(self):
        tags = get_capability_tags("mini", MINI_LANDSCAPE["specs"])
        assert len(tags) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Full-Size Excavator — specific rule tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExcavator:

    def test_mass_excavation_fires_above_44000_lbs(self):
        tags = run("excavator", EX_MASS)
        assert "Mass Excavation" in tags

    def test_mass_excavation_does_not_fire_below_44000(self):
        tags = run("excavator", EX_UTILITY)
        assert "Mass Excavation" not in tags

    def test_deep_foundation_work_fires_above_300_in(self):
        profile = {
            "specs": {
                **EX_MASS["specs"],
                "max_dig_depth_in": 320,
            },
            "flags": {},
        }
        tags = run("excavator", profile)
        assert "Deep Foundation Work" in tags
        assert "Foundation Excavation" not in tags  # same concept group

    def test_foundation_excavation_fires_240_to_299_in(self):
        # EX_MASS: dig_in 243, weight 47500 → Foundation Excavation
        tags = run("excavator", EX_MASS)
        assert "Foundation Excavation" in tags

    def test_rock_excavation_fires_high_pressure_force(self):
        profile = {
            "specs": {
                **EX_MASS["specs"],
                "hydraulic_pressure_psi": 4800,
                "bucket_dig_force_lbf": 28000,
            },
            "flags": {},
        }
        tags = run("excavator", profile)
        assert "Rock Excavation" in tags

    def test_rock_excavation_does_not_fire_below_4500_psi(self):
        profile = {
            "specs": {
                **EX_MASS["specs"],
                "hydraulic_pressure_psi": 4200,
                "bucket_dig_force_lbf": 30000,
            },
            "flags": {},
        }
        tags = run("excavator", profile)
        assert "Rock Excavation" not in tags

    def test_demolition_work_fires_high_breakout_and_pressure(self):
        tags = run("excavator", EX_MASS)
        assert "Demolition Work" in tags  # force 26200 >= 25000, pressure 4990 >= 4000

    def test_pipe_utility_installation_fires_mid_class(self):
        tags = run("excavator", EX_UTILITY)
        assert "Pipe & Utility Installation" in tags  # weight 30000 < 45000, dig 215

    def test_utility_trenching_suppressed_by_pipe_utility(self):
        tags = run("excavator", EX_UTILITY)
        assert "Utility Trenching" not in tags  # same concept group as Pipe & Utility

    def test_slope_embankment_grading_fires_long_reach(self):
        tags = run("excavator", EX_MASS)
        assert "Slope & Embankment Grading" in tags  # reach 388 >= 350

    def test_lift_place_operations_fires(self):
        # Mid-class machine where fewer high-priority tags compete for top-5 slots.
        profile = {
            "specs": {
                "operating_weight_lbs": 35000,
                "max_dig_depth_in": 250,
                "hydraulic_pressure_psi": 4300,  # below rock (4500) and demo (4000) thresholds? No, 4300 > 4000 but bkt_force below
                "bucket_dig_force_lbf": 20000,   # below Demolition threshold (25000)
                "max_reach_ground_in": 300,       # below Slope threshold (350)
                "max_dump_height_in": 260,         # >= 250 → Lift & Place fires
                "boom_type": "mono_boom",
            },
            "flags": {},
        }
        tags = run("excavator", profile)
        assert "Lift & Place Operations" in tags

    def test_high_reach_demo_fires_confirmed_config(self):
        tags = run("excavator", EX_HIGH_REACH)
        assert "High-Reach Demo" in tags

    def test_high_reach_demo_does_not_fire_mono_boom(self):
        tags = run("excavator", EX_MASS)
        assert "High-Reach Demo" not in tags  # boom_type mono_boom

    def test_short_code_ex_accepted(self):
        tags = get_capability_tags("EX", EX_UTILITY["specs"])
        assert len(tags) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_unknown_equipment_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported equipment_type"):
            get_capability_tags("wheel_loader", {})

    def test_empty_specs_returns_list(self):
        # Should not raise — just return few or zero tags
        for eq_type in ("CTL", "SSL", "mini_excavator", "excavator"):
            result = get_capability_tags(eq_type, {})
            assert isinstance(result, list)
            assert len(result) <= 5

    def test_none_feature_flags_treated_as_empty(self):
        tags = get_capability_tags("CTL", CTL_FORESTRY["specs"], None)
        # No high-flow flags → no FM or HFH
        assert "Forestry Mulching" not in tags
        assert "High-Flow Hydraulics" not in tags

    def test_all_none_spec_values(self):
        null_specs = {k: None for k in CTL_FORESTRY["specs"]}
        result = get_capability_tags("CTL", null_specs, {})
        assert isinstance(result, list)

    def test_hyphenated_type_alias_accepted(self):
        tags = get_capability_tags("mini-excavator", MINI_LANDSCAPE["specs"])
        assert isinstance(tags, list)

    def test_output_never_contains_retired_tag(self):
        for tag in _RETIRED_TAGS:
            assert tag not in _CTL_LIBRARY
            assert tag not in _SSL_LIBRARY
            assert tag not in _MINI_EX_LIBRARY
            assert tag not in _EX_LIBRARY

    def test_ssl_material_handling_position_enforcement(self):
        # When only one other tag precedes Material Handling, it must be dropped
        # (cannot satisfy the >= position-2 constraint).
        profile_one_other = {
            "specs": {
                "rated_operating_capacity_lbs": 1450,  # Mat.Handling fires; Pallet Fork doesn't (< 1800)
                "lift_path": "radial",
                "aux_flow_standard_gpm": 10,
                "aux_flow_high_gpm": None,
                "hydraulic_pressure_standard_psi": 2600,
                "width_over_tires_in": 68.0,
                "operating_weight_lbs": 5500,   # Farm fires (< 6500, ROC < 2200)
            },
            "flags": {"high_flow_available": False},
        }
        tags_one = get_capability_tags("ssl", profile_one_other["specs"], profile_one_other["flags"])
        # Farm fires (pos 0), Material Handling can't reach pos 2 → must be dropped
        assert "Material Handling" not in tags_one

        # When >= 2 other tags precede it, Material Handling is allowed at position 2+.
        profile_many = {
            "specs": {
                "rated_operating_capacity_lbs": 2000,  # Pallet Fork (pos 0-ish) + Farm + Mat.Handling
                "lift_path": "radial",
                "aux_flow_standard_gpm": 14,  # Brush Cutting fires too
                "aux_flow_high_gpm": None,
                "hydraulic_pressure_standard_psi": 2600,
                "width_over_tires_in": 68.0,
                "operating_weight_lbs": 5500,
            },
            "flags": {"high_flow_available": False},
        }
        tags_many = get_capability_tags("ssl", profile_many["specs"], profile_many["flags"])
        if "Material Handling" in tags_many:
            assert tags_many.index("Material Handling") >= 2

    def test_no_cross_category_tags(self):
        # CTL should never emit SSL-only tags and vice versa
        ctl_tags = run("CTL", CTL_FORESTRY)
        ssl_only = _SSL_LIBRARY - _CTL_LIBRARY
        for tag in ctl_tags:
            assert tag not in ssl_only

        ssl_tags = run("SSL", SSL_TRUCK_LOADER)
        ctl_only = _CTL_LIBRARY - _SSL_LIBRARY
        for tag in ssl_tags:
            assert tag not in ctl_only
