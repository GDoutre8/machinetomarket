"""
Test: CAT 320GC spec sheet render — Full-Size Excavator locked architecture v1.
Verifies hero, core, performance, condition, and features sections.

Run:
    python test_spec_sheet_cat320.py
"""

import json
import os
import sys
import copy
from pathlib import Path

from dealer_input import DealerInput
from spec_sheet_renderer_adapter import build_spec_sheet_data

DEALER_INFO = {
    "dealer_name":  "Iron Mountain Equipment",
    "phone":        "(605) 555-0199",
    "email":        "sales@ironmtn.com",
    "location":     "Rapid City, SD",
    "website":      "ironmtn.com",
    "accent_color": "yellow",
}

# Simulate registry-resolved specs for CAT 320GC (from mtm_excavator_registry_v2.json)
RESOLVED_SPECS = {
    "horsepower_gross_hp":   121,
    "operating_weight_lbs":  47500,
    "bucket_capacity_cy":    0.97,
    "bucket_dig_force_lbf":  26200,
    "arm_dig_force_lbf":     17200,
    "max_dig_depth_in":      243,
    "max_reach_ground_in":   388,
    "max_dump_height_in":    269,
    "hydraulic_flow_gpm":    83,
    "hydraulic_pressure_psi": 4990,
    "tail_swing_type":       "standard_tail_swing",
    "boom_type":             "mono_boom",
    "cab_type":              "enclosed_cab",
    "track_type":            "steel",
    "track_width_in":        23.6,
    "overall_width_in":      112,
}

dealer_input = DealerInput(
    year=2020,
    make="CAT",
    model="320GC",
    hours=4850,
    cab_type="enclosed",
    ac=True,
    heater=True,
    stick_arm_length_ft=9.5,       # 9' 6" arm — triggers hero slot 3
    boom_type="standard",          # Standard Boom — triggers hero slot 4
    track_shoe_width_in=32,        # 32" Pads — core row 5
    grade_control_type="2D",       # 2D Grade Control — feature
    coupler_type="hydraulic",      # Hydraulic Coupler — feature
    thumb_type="hydraulic",        # Hydraulic Thumb — feature
    aux_hydraulics_type="standard", # Auxiliary Hydraulics — feature
    undercarriage_percent_remaining=65,  # Undercarriage % Remaining — condition
    hours_qualifier="Since Service",     # condition section
    condition_grade="Good",
    condition_notes="Well maintained. Undercarriage recently inspected. No leaks.",
    asking_price=198000,
    serial_number="CAT0320GCABC1234",
    stock_number="STK-EX-0042",
)

print("\n" + "=" * 64)
print("  MTM Spec Sheet Test — CAT 320GC (Full-Size Excavator v1)")
print("=" * 64)

ss_data = build_spec_sheet_data(
    dealer_input_data       = dealer_input.model_dump(),
    enriched_resolved_specs = RESOLVED_SPECS,
    equipment_type          = "large_excavator",
    dealer_contact          = {
        "dealer_name": DEALER_INFO["dealer_name"],
        "phone":       DEALER_INFO["phone"],
        "location":    DEALER_INFO["location"],
    },
    dealer_info  = DEALER_INFO,
    full_record  = {},
    photo_path   = None,
)

print(f"\n  HERO TILES (expect: Operating Weight / Max Dig Depth / Arm Length / Boom Type):")
hero = ss_data["specs"]["hero"]
for t in hero:
    print(f"    {t.get('label'):<22} {t.get('value')} {t.get('unit','')}")

print(f"\n  CORE SPECS (expect: Hours / Wt / HP / DigDepth / PadWidth / Serial / Stock):")
for r in ss_data["specs"]["core"]:
    print(f"    {r.get('label'):<22} {r.get('value')} {r.get('unit','')}")

print(f"\n  PERFORMANCE DATA (expect: Max Reach / Bucket Breakout Force):")
for r in ss_data["specs"]["performance"]:
    print(f"    {r.get('label'):<22} {r.get('value')} {r.get('unit','')}")

print(f"\n  ADDITIONAL SPECS:")
for r in ss_data["specs"]["additional"]:
    print(f"    {r.get('label'):<22} {r.get('value')} {r.get('unit','')}")

print(f"\n  KEY FEATURES (expect: Cab/HVAC, Grade Control, Coupler, Thumb, Aux Hydraulics):")
for f in ss_data["features"]:
    print(f"    - {f}")

listing = ss_data["listing"]
print(f"\n  CONDITION & SERVICE:")
print(f"    condition      : {listing.get('condition')}")
print(f"    hours_qualifier: {listing.get('hours_qualifier')}")
print(f"    track_label    : {listing.get('track_label')}")
print(f"    track_pct      : {listing.get('track_pct')}")
print(f"    notes          : {listing.get('notes','')[:60]}")

# ── Assertions ────────────────────────────────────────────────────────────────
errors = []

hero_labels = [t["label"] for t in hero]
assert "Operating Weight" in hero_labels, "Hero must have Operating Weight"
assert "Max Dig Depth" in hero_labels, "Hero must have Max Dig Depth"
assert "Arm Length" in hero_labels, "Hero must have Arm Length"
assert "Boom Type" in hero_labels, "Hero must have Boom Type"
assert len(hero) == 4, f"Hero must have exactly 4 tiles, got {len(hero)}"

# Hero must NOT include Year, Hours, HP, Bucket Capacity
assert "Hours" not in hero_labels, "Hero must NOT have Hours"
assert "Engine HP" not in hero_labels and "Horsepower" not in hero_labels, "Hero must NOT have HP"
assert "Bucket Capacity" not in hero_labels, "Hero must NOT have Bucket Capacity"

core_labels = [r["label"] for r in ss_data["specs"]["core"]]
assert "Hours" in core_labels, "Core must have Hours"
assert "Operating Weight" in core_labels, "Core must have Operating Weight"
assert "Horsepower" in core_labels, "Core must have Horsepower"
assert "Max Dig Depth" in core_labels, "Core must have Max Dig Depth"
assert "Pad Width" in core_labels, "Core must have Pad Width"
assert "Serial #" in core_labels, "Core must have Serial #"
assert "Stock #" in core_labels, "Core must have Stock #"
assert "Rated Op Capacity" not in core_labels, "Core must NOT have ROC (CTL field)"
assert "Aux Hydraulic Flow (Standard)" not in core_labels, "Core must NOT have Aux Flow (CTL field)"

perf_labels = [r["label"] for r in ss_data["specs"]["performance"]]
assert "Max Reach" in perf_labels, "Performance must have Max Reach"
assert "Bucket Breakout Force" in perf_labels, "Performance must have Bucket Breakout Force"
assert "Tipping Load" not in perf_labels, "Performance must NOT have Tipping Load (CTL field)"
assert "High Flow Output" not in perf_labels, "Performance must NOT have High Flow Output (CTL field)"

assert listing["track_label"] == "Undercarriage % Remaining", "Condition label must be Undercarriage % Remaining"
assert listing["track_pct"] == "65%", f"Undercarriage pct should be 65%, got {listing['track_pct']}"
assert listing["hours_qualifier"] == "Since Service", "hours_qualifier must be wired"

feats = ss_data["features"]
assert any("Enclosed Cab" in f for f in feats), "Features must include Enclosed Cab"
assert "2D Grade Control" in feats, "Features must include Grade Control"
assert "Hydraulic Coupler" in feats, "Features must include Hydraulic Coupler"
assert "Hydraulic Thumb" in feats, "Features must include Hydraulic Thumb"
assert "Auxiliary Hydraulics" in feats, "Features must include Aux Hydraulics"
assert not any("attachments_included" in f.lower() for f in feats), "Features must NOT include raw attachments text"
assert not any("High Flow Equipped" in f for f in feats), "Features must NOT include CTL High Flow Equipped"

print("\n" + "=" * 64)
print("  ALL ASSERTIONS PASSED")
print("=" * 64)

# ── Optional: render PNG ──────────────────────────────────────────────────────
RENDER_PNG = os.environ.get("RENDER_PNG", "1") != "0"
if RENDER_PNG:
    try:
        from spec_sheet_renderer_adapter import export_spec_sheet
        from spec_sheet_renderer import render_spec_sheet
        out_path = Path("outputs/test_cat320_spec_sheet.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        html_str = render_spec_sheet(ss_data)
        debug_html = out_path.with_suffix(".debug.html")
        debug_html.write_text(html_str, encoding="utf-8")
        print(f"\n  Debug HTML  : {debug_html}")
        result = export_spec_sheet(ss_data, out_path, fail_silently=False)
        if result and result.exists():
            sz = result.stat().st_size / 1024
            print(f"  PNG artifact: {result}  ({sz:.0f} KB)")
        else:
            print("  PNG render: FAILED (export returned None)")
    except Exception as e:
        print(f"  PNG render skipped: {e}")
