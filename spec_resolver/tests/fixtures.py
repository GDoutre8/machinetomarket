"""
tests/fixtures.py
Registry entry fixtures used across all tests.
These are minimal but representative — they carry exactly the fields
the resolver needs; extra keys are fine (forward-compat).
"""

from __future__ import annotations
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Cat 259D3 — CTL, exact match target
# ---------------------------------------------------------------------------

CAT_259D3: Dict[str, Any] = {
    "family":   "Cat 259 Series",
    "mfr":      "caterpillar",
    "category": "CTL",
    "year_range": [2007, 2024],
    "variants": ["259B3", "259D", "259D3", "255"],
    "specs": {
        "net_hp":              73,
        "operating_weight_lb": 8990,
        "roc_lb":              2200,
        "tipping_load_lb":     6300,
        "hydraulic_flow_gpm":  20.5,
        "hi_flow_gpm":         34.0,
        "travel_speed_mph":    7.1,
        "fuel_type":           "Diesel",
        "lift_geometry":       "Vertical",
    },
    "family_ranges": {
        "roc_lb":              "2,200–2,400",
        "operating_weight_lb": "8,990–9,200",
    },
    "field_behaviors": {
        "hydraulic_flow_gpm": "package_dependent",
        "hi_flow_gpm":        "package_dependent",
    },
    "option_overrides": {
        # XE variant carries higher ROC
        "xe_variant": {
            "roc_lb":              4340,
            "tipping_load_lb":     12_400,
            "operating_weight_lb": 12_763,
        },
    },
    "year_overrides": {},
}


# ---------------------------------------------------------------------------
# Deere 333 Series — CTL, family match target
# ---------------------------------------------------------------------------

DEERE_333_SERIES: Dict[str, Any] = {
    "family":   "Deere 333 Series",
    "mfr":      "john deere",
    "category": "CTL",
    "year_range": [2013, 2030],
    "variants": ["333E", "333G", "333P"],
    "specs": {
        "net_hp":              97,          # 333G typical
        "operating_weight_lb": 12_100,
        "roc_lb":              3700,
        "tipping_load_lb":     10_580,
        "hydraulic_flow_gpm":  25,
        "hi_flow_gpm":         41,
        "travel_speed_mph":    8.0,
        "fuel_type":           "Diesel",
        "lift_geometry":       "Vertical",
    },
    "family_ranges": {
        "net_hp":              "97–108",        # 333G vs 333P
        "roc_lb":              "3,400–3,700",
        "tipping_load_lb":     "9,710–10,580",
        "operating_weight_lb": "12,000–12,500",
    },
    "field_behaviors": {
        "net_hp":              "range",
        "roc_lb":              "range",
        "tipping_load_lb":     "range",
        "operating_weight_lb": "range",
        "hydraulic_flow_gpm":  "package_dependent",
        "hi_flow_gpm":         "package_dependent",
    },
    "option_overrides": {},
    "year_overrides": {},
}


# ---------------------------------------------------------------------------
# Kubota SVL75-2 — CTL, cab vs canopy weight
# ---------------------------------------------------------------------------

KUBOTA_SVL75_2: Dict[str, Any] = {
    "family":   "Kubota SVL75 Series",
    "mfr":      "kubota",
    "category": "CTL",
    "year_range": [2015, 2030],
    "variants": ["SVL75-2", "SVL75-2W", "SVL75-3"],
    "specs": {
        "net_hp":              74,
        "operating_weight_lb": 9360,    # base / open ROPS
        "roc_lb":              2690,
        "tipping_load_lb":     7690,
        "hydraulic_flow_gpm":  17.4,
        "hi_flow_gpm":         24.6,
        "travel_speed_mph":    7.1,
        "fuel_type":           "Diesel",
        "lift_geometry":       "Vertical",
    },
    "family_ranges": {
        "roc_lb": "2,490–2,690",
    },
    "field_behaviors": {
        "hydraulic_flow_gpm":  "package_dependent",
        "hi_flow_gpm":         "package_dependent",
        "operating_weight_lb": "package_dependent",
    },
    "option_overrides": {
        # Cab adds ~258 lb
        "has_cab": {
            "operating_weight_lb": 9618,
        },
        # Canopy (OROPS) base
        "has_canopy": {
            "operating_weight_lb": 9190,
        },
    },
    "year_overrides": {},
}


# ---------------------------------------------------------------------------
# Deere 35G — Mini excavator
# ---------------------------------------------------------------------------

DEERE_35G: Dict[str, Any] = {
    "family":   "Deere 35 Series",
    "mfr":      "john deere",
    "category": "MINI",
    "year_range": [2013, 2030],
    "variants": ["35G", "35P"],
    "specs": {
        "net_hp":                 23,
        "operating_weight_lb":    8135,
        "max_dig_depth":          "10 ft 0 in",
        "bucket_breakout_lb":     5250,
        "tail_swing_type":        "Conventional",
        "travel_speed_high_mph":  3.0,
        "travel_speed_low_mph":   1.9,
        "fuel_type":              "Diesel",
    },
    "family_ranges": {},
    "field_behaviors": {},
    "option_overrides": {},
    "year_overrides": {},
}


# ---------------------------------------------------------------------------
# Case 580SN — Backhoe, extendahoe option
# ---------------------------------------------------------------------------

CASE_580SN: Dict[str, Any] = {
    "family":   "Case 580 Series",
    "mfr":      "case",
    "category": "BH",
    "year_range": [2000, 2030],
    "variants": ["580N", "580SN", "580SM"],
    "specs": {
        "net_hp":                 97,
        "operating_weight_lb":    17_838,
        "max_dig_depth":          "14 ft 3 in",
        "loader_bucket_cap_yd3":  1.1,
        "bh_breakout_force_lb":   10_947,
        "travel_speed_mph":       24,
        "fuel_type":              "Diesel",
    },
    "family_ranges": {
        "operating_weight_lb": "15,900–17,838",  # 2WD vs 4WD
    },
    "field_behaviors": {
        "max_dig_depth":       "package_dependent",
        "operating_weight_lb": "range",
    },
    "option_overrides": {
        "extendahoe": {
            "max_dig_depth": "16 ft 1 in",
        },
        "four_wheel_drive": {
            "operating_weight_lb": 17_838,
        },
    },
    "year_overrides": {},
}


# ---------------------------------------------------------------------------
# Generic "weak" registry entry — barely above hard floor
# ---------------------------------------------------------------------------

WEAK_ENTRY: Dict[str, Any] = {
    "family":   "Unknown Family",
    "mfr":      "unknown",
    "category": "CTL",
    "year_range": [2000, 2030],
    "variants": [],
    "specs": {
        "net_hp": 80,
    },
    "family_ranges": {},
    "field_behaviors": {},
    "option_overrides": {},
    "year_overrides": {},
}
