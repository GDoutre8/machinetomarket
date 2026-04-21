"""
Edge-case render tests:
  C — has-photo + tiles-3 (photo present, one hero spec null)
  D — no-photo  + tiles-4 (no photo, all 4 hero specs valid)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec_sheet_context import screenshot_spec_sheet

OUTPUTS  = "C:/mtm_mvp3/outputs"
DEMO_IMG = "C:/mtm_mvp3/inputs/demo_images/IMG_001.jpg"

DEALER = {
    "contact_name": "John Smith", "dealer_role": "Sales",
    "contact_phone": "555-111-2222", "location": "Ames, IA",
}

# ── Scenario C — has-photo + tiles-3 ─────────────────────────────────────────
# CTL: ground_pressure_psi is null → 4th tile dropped → tiles-3 with photo
print("--- Scenario C: has-photo + tiles-3 ---")
screenshot_spec_sheet(
    dealer_input_data={
        "year": 2021, "make": "CAT", "model": "299D3", "hours": 2100,
        "high_flow": "no", "two_speed_travel": "yes",
        "heater": True, "ac": True, "cab_type": "enclosed",
        "asking_price": 61000,
    },
    resolved_specs={
        "rated_operating_capacity_lbs": 3600,
        "horsepower_hp": 100,
        "aux_flow_standard_gpm": 22.5,
        # ground_pressure_psi intentionally absent → 4th tile missing → tiles-3
    },
    ui_hints={},
    equipment_type="compact_track_loader",
    dealer_contact=DEALER,
    session_id="test_photo_3tiles",
    outputs_dir=OUTPUTS,
    output_path="C:/mtm_mvp3/outputs/_test_photo_3tiles.png",
    field_confidence={
        "rated_operating_capacity_lbs": "HIGH",
        "horsepower_hp": "HIGH",
        "aux_flow_standard_gpm": "HIGH",
    },
    image_input_paths=[DEMO_IMG],
)
print("  -> saved: outputs/_test_photo_3tiles.png")

# ── Scenario D — no-photo + tiles-4 ──────────────────────────────────────────
# Telehandler: all 4 hero specs present, no photo
print("--- Scenario D: no-photo + tiles-4 ---")
screenshot_spec_sheet(
    dealer_input_data={
        "year": 2019, "make": "JLG", "model": "1055", "hours": 3800,
        "cab_type": "enclosed", "heater": True, "ac": True,
        "asking_price": 68000,
    },
    resolved_specs={
        "lift_capacity_lbs": 10000,
        "lift_height_ft": 42.0,
        "forward_reach_ft": 29.5,
        "horsepower_hp": 120,
        "operating_weight_lb": 28500,
        "width_in": 96.0,
        "hydraulic_pressure_standard_psi": 3200,
    },
    ui_hints={},
    equipment_type="telehandler",
    dealer_contact=DEALER,
    session_id="test_nophoto_4tiles",
    outputs_dir=OUTPUTS,
    output_path="C:/mtm_mvp3/outputs/_test_nophoto_4tiles.png",
    field_confidence={
        "lift_capacity_lbs": "HIGH",
        "lift_height_ft": "HIGH",
        "forward_reach_ft": "HIGH",
        "horsepower_hp": "HIGH",
    },
    image_input_paths=[],
)
print("  -> saved: outputs/_test_nophoto_4tiles.png")
print("Done.")
