"""
Two-scenario spec sheet render test.
Run from C:/mtm_mvp3: python _test_render_scenarios.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spec_sheet_context import screenshot_spec_sheet

OUTPUTS = "C:/mtm_mvp3/outputs"
DEMO_IMG = "C:/mtm_mvp3/inputs/demo_images/IMG_001.jpg"
LOGO = "C:/mtm_mvp3/static/assets/yellow_iron_yard_logo.png"

DEALER = {
    "contact_name":  "John Smith",
    "dealer_role":   "Sales Manager",
    "contact_phone": "555-867-5309",
    "location":      "Cedar Rapids, IA",
    "logo_filename":  LOGO,
}

# ── Scenario A — Data-rich: CTL with photo, full condition, 3 attachments ──────
print("--- Rendering Scenario A: data-rich CTL ---")
screenshot_spec_sheet(
    dealer_input_data={
        "year": 2022, "make": "Bobcat", "model": "T770", "hours": 3200,
        "high_flow": "yes", "two_speed_travel": "yes",
        "heater": True, "ac": True, "ride_control": True, "backup_camera": True,
        "cab_type": "enclosed", "control_type": "joystick",
        "one_owner": True,
        "asking_price": 52000,
        "track_condition": "Good",
        "condition_grade": "Good",
        "attachments_included": "72\" GP Bucket, Pallet Forks, Grapple",
        "additional_details": "Well maintained, all service records available. Stored inside.",
        "serial_number": "B3VT11001",
    },
    resolved_specs={
        "rated_operating_capacity_lbs": 3475,
        "horsepower_hp": 88,
        "aux_flow_standard_gpm": 23.0,
        "aux_flow_high_gpm": 37.0,
        "ground_pressure_psi": 5.1,
        "track_width_in": 15,
        "lift_path": "vertical",
        "tipping_load_lbs": 6950,
        "operating_weight_lb": 11450,
        "width_over_tires_in": 78.0,
        "bucket_hinge_pin_height_in": 132.0,
        "hydraulic_pressure_standard_psi": 3550,
        "high_flow": "yes",
    },
    ui_hints={},
    equipment_type="compact_track_loader",
    dealer_contact=DEALER,
    session_id="test_rich_ctl",
    outputs_dir=OUTPUTS,
    output_path="C:/mtm_mvp3/outputs/_test_rich_ctl.png",
    field_confidence={
        "rated_operating_capacity_lbs": "HIGH",
        "horsepower_hp": "HIGH",
        "aux_flow_standard_gpm": "HIGH",
        "aux_flow_high_gpm": "HIGH",
        "ground_pressure_psi": "MEDIUM",
    },
    image_input_paths=[DEMO_IMG],
)
print("  -> saved: outputs/_test_rich_ctl.png")

# ── Scenario B — Data-thin: mini-ex, no photo, no grade, no attachments ────────
print("--- Rendering Scenario B: data-thin mini-ex ---")
screenshot_spec_sheet(
    dealer_input_data={
        "year": 2020, "make": "Kubota", "model": "KX040-4", "hours": 1200,
        "heater": None, "ac": None, "cab_type": None, "one_owner": False,
        "asking_price": None,
        "condition_grade": None,
        "track_condition": None,
        "attachments_included": None,
        "additional_details": None,
    },
    resolved_specs={
        # only 3 hero-eligible fields
        "operating_weight_lbs": 8930,
        "max_dump_height_ft": 10.25,
        "hydraulic_flow_gpm": 19.0,
        # no max_dig_depth_ft, no other specs
    },
    ui_hints={},
    equipment_type="mini_excavator",
    dealer_contact={
        "contact_name": "Midwest Equipment",
        "dealer_role": "",
        "contact_phone": "",
        "location": "",
    },
    session_id="test_thin_mex",
    outputs_dir=OUTPUTS,
    output_path="C:/mtm_mvp3/outputs/_test_thin_mex.png",
    field_confidence={
        "operating_weight_lbs": "HIGH",
        "max_dump_height_ft": "MEDIUM",
        "hydraulic_flow_gpm": "MEDIUM",
    },
    image_input_paths=[],
)
print("  -> saved: outputs/_test_thin_mex.png")
print("Done.")
