"""
tools/test_listing_enrichment.py
=================================
Examples of scorer-enriched listing text for one SSL, one CTL, one mini ex.

Run from project root:
    python tools/test_listing_enrichment.py
"""

from __future__ import annotations
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dealer_input import DealerInput
from listing_builder import build_listing_text
from listing_use_case_enrichment import build_use_case_payload


DIVIDER = "=" * 70


def show_example(label: str, equipment_type: str, dealer_input: DealerInput, resolved_specs: dict):
    payload = build_use_case_payload(equipment_type, dealer_input, resolved_specs)
    text = build_listing_text(dealer_input, resolved_specs, payload)

    print(f"\n{DIVIDER}")
    print(f"  EXAMPLE: {label}")
    print(f"  Equipment Type: {equipment_type}")
    print(DIVIDER)
    print(text)

    print(f"\n  -- Payload Debug --")
    if payload:
        print(f"  use_cases : {payload['top_use_cases_for_listing']}")
        print(f"  attachment: {payload['attachment_sentence']}")
        print(f"  limitation: {payload['limitation_sentence']}")
    else:
        print("  payload   : None (scorer returned no payload)")
    print(DIVIDER)


# ---------------------------------------------------------------------------
# Example 1 — Skid Steer: Bobcat S650, enclosed cab, high flow, vertical lift
# ---------------------------------------------------------------------------

ssl_dealer = DealerInput(
    year=2018,
    make="Bobcat",
    model="S650",
    hours=2850,
    cab_type="enclosed",
    heat=True,
    ac=True,
    high_flow=True,
    two_speed=True,
    ride_control=False,
    backup_camera=False,
    one_owner=True,
    track_condition_pct=None,
    attachments_included="72\" bucket, pallet forks",
    condition_notes="Clean machine. No hydraulic issues.",
)

ssl_specs = {
    "horsepower_hp": 74.0,
    "rated_operating_capacity_lbs": 2690,
    "tipping_load_lbs": 5380,
    "operating_weight_lbs": 7595,
    "aux_flow_standard_gpm": 22.4,
    "aux_flow_high_gpm": 30.0,
    "hydraulic_pressure_standard_psi": 3600,
    "hydraulic_pressure_high_psi": 3600,
    "bucket_hinge_pin_height_in": 128.0,
    "lift_path": "vertical",
    "travel_speed_high_mph": 11.0,
    "width_over_tires_in": 66.0,
}


# ---------------------------------------------------------------------------
# Example 2 — CTL: Caterpillar 259D3, radial lift, high flow, enclosed cab
# ---------------------------------------------------------------------------

ctl_dealer = DealerInput(
    year=2021,
    make="Caterpillar",
    model="259D3",
    hours=1420,
    cab_type="enclosed",
    heat=True,
    ac=True,
    high_flow=True,
    two_speed=True,
    ride_control=True,
    backup_camera=True,
    one_owner=False,
    track_condition_pct=80,
    attachments_included=None,
    condition_notes="Low hours, well maintained. Clean undercarriage.",
)

ctl_specs = {
    "horsepower_hp": 74.3,
    "rated_operating_capacity_lbs": 2690,
    "tipping_load_lbs": 5380,
    "operating_weight_lbs": 10053,
    "aux_flow_standard_gpm": 20.5,
    "aux_flow_high_gpm": 32.0,
    "hydraulic_pressure_standard_psi": 3600,
    "hydraulic_pressure_high_psi": 3600,
    "bucket_hinge_pin_height_in": 122.0,
    "lift_path": "radial",
    "travel_speed_high_mph": 7.1,
    "width_over_tires_in": 72.0,
}


# ---------------------------------------------------------------------------
# Example 3 — Mini Ex: John Deere 35G, reduced tail swing, enclosed cab
# ---------------------------------------------------------------------------

mex_dealer = DealerInput(
    year=2020,
    make="John Deere",
    model="35G",
    hours=1950,
    cab_type="enclosed",
    heat=True,
    ac=False,
    high_flow=False,
    two_speed=True,
    ride_control=False,
    backup_camera=False,
    one_owner=True,
    track_condition_pct=75,
    attachments_included="24\" bucket, hydraulic thumb",
    condition_notes="Tight machine. Recent service. Thumb works great.",
)

mex_specs = {
    "operating_weight_lbs": 7716,
    "max_dig_depth_ft": 9.17,
    "max_dump_height_ft": 9.52,
    "max_reach_ft": 14.17,
    "width_in": 59.1,
    "aux_flow_primary_gpm": 16.1,
    "aux_pressure_primary_psi": 3046,
    "tail_swing_type": "reduced",
    "horsepower_hp": 24.4,
}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    show_example("2018 Bobcat S650 (Skid Steer)",   "skid_steer",            ssl_dealer, ssl_specs)
    show_example("2021 Caterpillar 259D3 (CTL)",     "compact_track_loader",  ctl_dealer, ctl_specs)
    show_example("2020 John Deere 35G (Mini Ex)",    "mini_excavator",        mex_dealer, mex_specs)
    print("\nAll examples completed.")
