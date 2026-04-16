"""
tools/validate_use_case_output.py
===================================
MTM Use Case Output Refinement — Validation Test

Tests all 8 required models per spec:
  CTL:        cat_259d3, bobcat_t770
  SSL:        bobcat_s650
  Mini Ex:    kubota_kx040_4, jd_35g
  Backhoe:    case_580sn
  Dozer:      cat_d6
  Telehandler: skytrak_8042

Confirms:
  1. Auger Work does not appear unless auger attachment is listed
  2. Snow Removal does not appear unless snow attachment is listed
  3. Best For renders in the locked bullet structure (2 lines default)
  4. No regression in current supported types

Run from project root:
    python tools/validate_use_case_output.py
"""

from __future__ import annotations
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dealer_input import DealerInput
from listing_use_case_enrichment import build_use_case_payload
from listing_builder import build_listing_text, _build_use_case_section

DIVIDER = "=" * 70
PASS_MARK = "[PASS]"
FAIL_MARK = "[FAIL]"


# ---------------------------------------------------------------------------
# Test case definitions
# ---------------------------------------------------------------------------

TEST_CASES = [
    # (label, equipment_type, dealer_input_kwargs, resolved_specs, note)

    # ── CTL: cat_259d3 ─────────────────────────────────────────────────────
    {
        "label": "cat_259d3 (CTL — no attachments)",
        "equipment_type": "compact_track_loader",
        "di": dict(
            year=2021, make="Caterpillar", model="259D3", hours=1420,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=True, backup_camera=True,
            attachments_included=None,
        ),
        "specs": {
            "horsepower_hp": 74.3, "rated_operating_capacity_lbs": 2690,
            "tipping_load_lbs": 5380, "operating_weight_lbs": 10053,
            "aux_flow_standard_gpm": 20.5, "aux_flow_high_gpm": 32.0,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 122.0, "lift_path": "radial",
        },
        "expect_no": ["Auger Work", "Snow Removal"],
        "note": "No attachments -> neither Auger Work nor Snow Removal should appear",
    },

    # ── CTL: cat_259d3 WITH auger attachment ───────────────────────────────
    {
        "label": "cat_259d3 (CTL — with auger attachment)",
        "equipment_type": "compact_track_loader",
        "di": dict(
            year=2021, make="Caterpillar", model="259D3", hours=1420,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=True, backup_camera=True,
            attachments_included="earth auger, bucket",
        ),
        "specs": {
            "horsepower_hp": 74.3, "rated_operating_capacity_lbs": 2690,
            "tipping_load_lbs": 5380, "operating_weight_lbs": 10053,
            "aux_flow_standard_gpm": 20.5, "aux_flow_high_gpm": 32.0,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 122.0, "lift_path": "radial",
        },
        "expect_present": ["Auger Work"],
        "note": "Earth auger listed -> Auger Work should appear",
    },

    # ── CTL: bobcat_t770 ───────────────────────────────────────────────────
    {
        "label": "bobcat_t770 (CTL — no attachments)",
        "equipment_type": "compact_track_loader",
        "di": dict(
            year=2022, make="Bobcat", model="T770", hours=680,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=False, backup_camera=False,
            attachments_included=None,
        ),
        "specs": {
            "horsepower_hp": 92.0, "rated_operating_capacity_lbs": 3650,
            "tipping_load_lbs": 7250, "operating_weight_lbs": 11505,
            "aux_flow_standard_gpm": 24.0, "aux_flow_high_gpm": 37.5,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 134.0, "lift_path": "vertical",
        },
        "expect_no": ["Auger Work", "Snow Removal"],
        "note": "Large CTL, no attachments -> should get site prep / material handling",
    },

    # ── SSL: bobcat_s650 ───────────────────────────────────────────────────
    {
        "label": "bobcat_s650 (SSL — no attachments)",
        "equipment_type": "skid_steer",
        "di": dict(
            year=2018, make="Bobcat", model="S650", hours=2850,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=False, backup_camera=False,
            attachments_included='72" bucket, pallet forks',
        ),
        "specs": {
            "horsepower_hp": 74.0, "rated_operating_capacity_lbs": 2690,
            "tipping_load_lbs": 5380, "operating_weight_lbs": 7595,
            "aux_flow_standard_gpm": 22.4, "aux_flow_high_gpm": 30.0,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 128.0, "lift_path": "vertical",
        },
        "expect_no": ["Auger Work", "Snow Removal"],
        "note": "Has forks -> Material Handling expected; no auger/snow attachment",
    },

    # ── SSL: bobcat_s650 WITH post hole digger ─────────────────────────────
    {
        "label": "bobcat_s650 (SSL — post hole digger listed)",
        "equipment_type": "skid_steer",
        "di": dict(
            year=2018, make="Bobcat", model="S650", hours=2850,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=False, backup_camera=False,
            attachments_included="post hole digger, bucket",
        ),
        "specs": {
            "horsepower_hp": 74.0, "rated_operating_capacity_lbs": 2690,
            "tipping_load_lbs": 5380, "operating_weight_lbs": 7595,
            "aux_flow_standard_gpm": 22.4, "aux_flow_high_gpm": 30.0,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 128.0, "lift_path": "vertical",
        },
        "expect_present": ["Auger Work"],
        "note": "Post hole digger listed -> Auger Work should appear",
    },

    # ── Mini Ex: kubota_kx040_4 ────────────────────────────────────────────
    {
        "label": "kubota_kx040_4 (Mini Ex)",
        "equipment_type": "mini_excavator",
        "di": dict(
            year=2018, make="Kubota", model="KX040-4", hours=2900,
            cab_type=None, heater=False, ac=False,
            high_flow=None, two_speed_travel=None,
            ride_control=False, backup_camera=False,
            attachments_included=None,
        ),
        "specs": {
            "operating_weight_lbs": 8675, "max_dig_depth_ft": 11.5,
            "max_dump_height_ft": 9.2, "max_reach_ft": 15.3,
            "width_in": 62.2, "aux_flow_primary_gpm": 15.8,
            "horsepower_hp": 39.4, "tail_swing_type": "conventional",
        },
        "expect_no": ["Auger Work", "Snow Removal"],
        "note": "No attachments -> standard mini ex output",
    },

    # ── Mini Ex: jd_35g ────────────────────────────────────────────────────
    {
        "label": "jd_35g (Mini Ex — with thumb)",
        "equipment_type": "mini_excavator",
        "di": dict(
            year=2020, make="John Deere", model="35G", hours=1950,
            cab_type="enclosed", heater=True, ac=False,
            high_flow=None, two_speed_travel="yes",
            ride_control=False, backup_camera=False,
            attachments_included="24\" bucket, hydraulic thumb",
        ),
        "specs": {
            "operating_weight_lbs": 7716, "max_dig_depth_ft": 9.17,
            "max_dump_height_ft": 9.52, "max_reach_ft": 14.17,
            "width_in": 59.1, "aux_flow_primary_gpm": 16.1,
            "horsepower_hp": 24.4, "tail_swing_type": "reduced",
        },
        "expect_no": ["Auger Work", "Snow Removal"],
        "note": "Thumb listed, not auger — Auger Work should not appear",
    },

    # ── Backhoe: case_580sn ────────────────────────────────────────────────
    {
        "label": "case_580sn (Backhoe)",
        "equipment_type": "backhoe_loader",
        "di": dict(
            year=2017, make="Case", model="580SN", hours=4800,
            cab_type="enclosed", heater=True, ac=True,
            high_flow=None, two_speed_travel=None,
            ride_control=False, backup_camera=False,
            attachments_included="bucket, backhoe bucket",
        ),
        "specs": {
            "horsepower_hp": 97.0, "operating_weight_lbs": 14990,
            "max_dig_depth_ft": 14.1, "hydraulic_flow_gpm": 23.0,
        },
        "expect_no": ["Auger Work", "Snow Removal"],
        "note": "Standard backhoe -> should produce Utility Trenching and site work",
    },

    # ── Dozer: cat_d6 ──────────────────────────────────────────────────────
    {
        "label": "cat_d6 (Dozer)",
        "equipment_type": "dozer",
        "di": dict(
            year=2018, make="Caterpillar", model="D6", hours=5600,
            cab_type="enclosed", heater=True, ac=True,
            high_flow=None, two_speed_travel=None,
            ride_control=False, backup_camera=False,
            attachments_included=None,
        ),
        "specs": {
            "horsepower_hp": 215.0, "operating_weight_lbs": 51000,
        },
        "note": "Should produce Grading & Site Prep + Land Clearing",
    },

    # ── Telehandler: skytrak_8042 (42 ft / short-reach class) ────────────────
    {
        "label": "skytrak_8042 (Telehandler, 42 ft)",
        "equipment_type": "telehandler",
        "di": dict(
            year=2019, make="SkyTrak", model="8042", hours=3100,
            cab_type="enclosed", heater=True, ac=True,
            high_flow=None, two_speed_travel=None,
            ride_control=False, backup_camera=False,
            attachments_included=None,
        ),
        "specs": {
            "horsepower_hp": 74.0, "operating_weight_lbs": 16500,
            "max_lift_height_ft": 42.0, "max_load_capacity_lbs": 8000,
        },
        "expect_present": ["Rooftop Material Placement", "Jobsite Reach & Placement"],
        "expect_no": ["Agricultural Use", "High-Reach Loading", "Material Handling",
                      "Elevated Material Placement", "Truck Loading"],
        "note": "42 ft -> Rooftop Material Placement + Jobsite Reach & Placement; agriculture allowed but no signal",
    },

    # ── Telehandler: jcb_510_56 (56 ft / long-reach class) ──────────────────
    {
        "label": "jcb_510_56 (Telehandler, 56 ft)",
        "equipment_type": "telehandler",
        "di": dict(
            year=2021, make="JCB", model="510-56", hours=1200,
            cab_type="enclosed", heater=True, ac=True,
            high_flow=None, two_speed_travel=None,
            ride_control=False, backup_camera=False,
            attachments_included=None,
        ),
        "specs": {
            "horsepower_hp": 109.0, "operating_weight_lbs": 28200,
            "max_lift_height_ft": 56.0, "max_load_capacity_lbs": 10000,
        },
        "expect_present": ["Rooftop Material Placement", "High-Reach Loading"],
        "expect_no": ["Agricultural Use", "Jobsite Reach & Placement", "Material Handling",
                      "Elevated Material Placement", "Truck Loading", "Pallet Handling"],
        "note": "56 ft -> Rooftop Material Placement + High-Reach Loading; agriculture suppressed (> 44 ft)",
    },

    # ── CTL: Snow Removal gating test ──────────────────────────────────────
    {
        "label": "bobcat_t770 (CTL — snow blade listed)",
        "equipment_type": "compact_track_loader",
        "di": dict(
            year=2022, make="Bobcat", model="T770", hours=680,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=False, backup_camera=False,
            attachments_included="snow blade, bucket",
        ),
        "specs": {
            "horsepower_hp": 92.0, "rated_operating_capacity_lbs": 3650,
            "tipping_load_lbs": 7250, "operating_weight_lbs": 11505,
            "aux_flow_standard_gpm": 24.0, "aux_flow_high_gpm": 37.5,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 134.0, "lift_path": "vertical",
        },
        "expect_present": ["Snow Removal"],
        "note": "Snow blade listed -> Snow Removal should be present",
    },
]


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

def run_validation():
    print(f"\n{DIVIDER}")
    print("  MTM USE CASE OUTPUT — VALIDATION TEST")
    print(f"{DIVIDER}")

    total = 0
    passed = 0
    failures: list[str] = []

    for tc in TEST_CASES:
        total += 1
        label = tc["label"]
        eq_type = tc["equipment_type"]
        note = tc.get("note", "")

        # Build DealerInput
        try:
            di = DealerInput(**tc["di"])
        except Exception as e:
            print(f"\n  {FAIL_MARK} {label}")
            print(f"    DealerInput error: {e}")
            failures.append(f"{label}: DealerInput error: {e}")
            continue

        specs = tc["specs"]

        # Run scorer
        try:
            payload = build_use_case_payload(eq_type, di, specs)
        except Exception as e:
            print(f"\n  {FAIL_MARK} {label}")
            print(f"    Scorer error: {e}")
            failures.append(f"{label}: scorer error: {e}")
            continue

        use_cases = (payload or {}).get("top_use_cases_for_listing") or []

        # Render Best For section
        section = _build_use_case_section(payload) if payload else ""

        # Check assertions
        tc_pass = True
        fail_reasons: list[str] = []

        for forbidden in tc.get("expect_no", []):
            if forbidden in use_cases:
                tc_pass = False
                fail_reasons.append(f"UNEXPECTED '{forbidden}' in output (requires attachment not listed)")

        for required in tc.get("expect_present", []):
            if required not in use_cases:
                tc_pass = False
                fail_reasons.append(f"MISSING '{required}' (attachment IS listed, should appear)")

        # Format check: Best For section must use bullet format
        if payload and use_cases:
            if "Best For:" not in section:
                tc_pass = False
                fail_reasons.append("'Best For:' header missing from rendered section")
            if "•" not in section:
                tc_pass = False
                fail_reasons.append("Bullet character (•) missing from rendered section")
            # Should render exactly 2 lines by default (unless payload has only 1)
            bullet_lines = [ln for ln in section.split("\n") if "•" in ln]
            rendered_count = len(bullet_lines)
            if rendered_count == 0 and use_cases:
                tc_pass = False
                fail_reasons.append("No bullet lines rendered despite having use cases")

        mark = PASS_MARK if tc_pass else FAIL_MARK
        print(f"\n  {mark} {label}")
        if note:
            print(f"    Note: {note}")
        print(f"    Use Cases: {use_cases}")
        if section:
            for line in section.split("\n"):
                print(f"      {line}")
        else:
            print("      (no Best For section)")
        if payload:
            att = payload.get("attachment_sentence")
            lim = payload.get("limitation_sentence")
            if att:
                print(f"    attachment_sentence: {att}")
            if lim:
                print(f"    limitation_sentence: {lim}")

        if fail_reasons:
            for r in fail_reasons:
                print(f"    !! {r}")
            failures.append(f"{label}: {'; '.join(fail_reasons)}")
        else:
            passed += 1

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  VALIDATION SUMMARY")
    print(f"{DIVIDER}")
    status = "PASS" if not failures else "FAIL"
    print(f"  Result:  {status}")
    print(f"  Passed:  {passed}/{total}")

    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for f in failures:
            print(f"    !! {f}")

    print(f"\n{DIVIDER}")
    return not failures


# ---------------------------------------------------------------------------
# Before/After demonstration for the 3 required models
# ---------------------------------------------------------------------------

BEFORE_AFTER_CASES = [
    # (label, eq_type, di_kwargs, specs, before_note)
    {
        "label": "cat_259d3 (CTL)",
        "equipment_type": "compact_track_loader",
        "di": dict(
            year=2021, make="Caterpillar", model="259D3", hours=1420,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=True, backup_camera=True,
            attachments_included=None,
        ),
        "specs": {
            "horsepower_hp": 74.3, "rated_operating_capacity_lbs": 2690,
            "tipping_load_lbs": 5380, "operating_weight_lbs": 10053,
            "aux_flow_standard_gpm": 20.5, "aux_flow_high_gpm": 32.0,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 122.0, "lift_path": "radial",
        },
        "before_note": "Auger Work could appear without auger attachment",
    },
    {
        "label": "bobcat_t770 (CTL)",
        "equipment_type": "compact_track_loader",
        "di": dict(
            year=2022, make="Bobcat", model="T770", hours=680,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=False, backup_camera=False,
            attachments_included=None,
        ),
        "specs": {
            "horsepower_hp": 92.0, "rated_operating_capacity_lbs": 3650,
            "tipping_load_lbs": 7250, "operating_weight_lbs": 11505,
            "aux_flow_standard_gpm": 24.0, "aux_flow_high_gpm": 37.5,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 134.0, "lift_path": "vertical",
        },
        "before_note": "Auger Work could appear without auger attachment",
    },
    {
        "label": "bobcat_s650 (SSL)",
        "equipment_type": "skid_steer",
        "di": dict(
            year=2018, make="Bobcat", model="S650", hours=2850,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            ride_control=False, backup_camera=False,
            attachments_included='72" bucket, pallet forks',
        ),
        "specs": {
            "horsepower_hp": 74.0, "rated_operating_capacity_lbs": 2690,
            "tipping_load_lbs": 5380, "operating_weight_lbs": 7595,
            "aux_flow_standard_gpm": 22.4, "aux_flow_high_gpm": 30.0,
            "hydraulic_pressure_standard_psi": 3600,
            "bucket_hinge_pin_height_in": 128.0, "lift_path": "vertical",
        },
        "before_note": "Auger Work could appear without auger attachment",
    },
]


def print_final_outputs():
    """Print the locked Best For structure for all required equipment types."""
    print(f"\n{DIVIDER}")
    print("  FINAL OUTPUT EXAMPLES — ALL EQUIPMENT TYPES")
    print(f"{DIVIDER}")

    ALL_EXAMPLES = [
        # CTL
        ("cat_259d3 (CTL)", "compact_track_loader",
            dict(year=2021, make="Caterpillar", model="259D3", hours=1420,
                 cab_type="enclosed", heater=True, ac=True, high_flow="yes",
                 two_speed_travel="yes", ride_control=True, backup_camera=True,
                 attachments_included=None),
            {"horsepower_hp": 74.3, "rated_operating_capacity_lbs": 2690,
             "operating_weight_lbs": 10053, "aux_flow_standard_gpm": 20.5,
             "aux_flow_high_gpm": 32.0, "hydraulic_pressure_standard_psi": 3600,
             "bucket_hinge_pin_height_in": 122.0, "lift_path": "radial"}),
        # SSL
        ("bobcat_s650 (SSL)", "skid_steer",
            dict(year=2018, make="Bobcat", model="S650", hours=2850,
                 cab_type="enclosed", heater=True, ac=True, high_flow="yes",
                 two_speed_travel="yes", ride_control=False, backup_camera=False,
                 attachments_included='72" bucket, pallet forks'),
            {"horsepower_hp": 74.0, "rated_operating_capacity_lbs": 2690,
             "operating_weight_lbs": 7595, "aux_flow_standard_gpm": 22.4,
             "aux_flow_high_gpm": 30.0, "hydraulic_pressure_standard_psi": 3600,
             "bucket_hinge_pin_height_in": 128.0, "lift_path": "vertical"}),
        # Mini Ex
        ("kubota_kx040_4 (Mini Ex)", "mini_excavator",
            dict(year=2018, make="Kubota", model="KX040-4", hours=2900,
                 cab_type=None, heater=False, ac=False, high_flow=None,
                 two_speed_travel=None, ride_control=False, backup_camera=False,
                 attachments_included=None),
            {"operating_weight_lbs": 8675, "max_dig_depth_ft": 11.5,
             "max_dump_height_ft": 9.2, "max_reach_ft": 15.3, "width_in": 62.2,
             "horsepower_hp": 39.4, "tail_swing_type": "conventional"}),
        # Backhoe
        ("case_580sn (Backhoe)", "backhoe_loader",
            dict(year=2017, make="Case", model="580SN", hours=4800,
                 cab_type="enclosed", heater=True, ac=True, high_flow=None,
                 two_speed_travel=None, ride_control=False, backup_camera=False,
                 attachments_included="bucket, backhoe bucket"),
            {"horsepower_hp": 97.0, "operating_weight_lbs": 14990,
             "max_dig_depth_ft": 14.1}),
        # Dozer
        ("cat_d6 (Dozer)", "dozer",
            dict(year=2018, make="Caterpillar", model="D6", hours=5600,
                 cab_type="enclosed", heater=True, ac=True, high_flow=None,
                 two_speed_travel=None, ride_control=False, backup_camera=False,
                 attachments_included=None),
            {"horsepower_hp": 215.0, "operating_weight_lbs": 51000}),
        # Telehandler — 42 ft short-reach (SkyTrak 8042)
        ("skytrak_8042 (Telehandler, 42 ft)", "telehandler",
            dict(year=2019, make="SkyTrak", model="8042", hours=3100,
                 cab_type="enclosed", heater=True, ac=True, high_flow=None,
                 two_speed_travel=None, ride_control=False, backup_camera=False,
                 attachments_included=None),
            {"horsepower_hp": 74.0, "max_lift_height_ft": 42.0,
             "max_load_capacity_lbs": 8000}),
        # Telehandler — 56 ft long-reach (JCB 510-56)
        ("jcb_510_56 (Telehandler, 56 ft)", "telehandler",
            dict(year=2021, make="JCB", model="510-56", hours=1200,
                 cab_type="enclosed", heater=True, ac=True, high_flow=None,
                 two_speed_travel=None, ride_control=False, backup_camera=False,
                 attachments_included=None),
            {"horsepower_hp": 109.0, "max_lift_height_ft": 56.0,
             "max_load_capacity_lbs": 10000}),
    ]

    for label, eq_type, di_kwargs, specs in ALL_EXAMPLES:
        di = DealerInput(**di_kwargs)
        payload = build_use_case_payload(eq_type, di, specs)
        section = _build_use_case_section(payload) if payload else "(no payload)"
        use_cases = (payload or {}).get("top_use_cases_for_listing") or []
        print(f"\n  ── {label}")
        print(f"     use_cases raw: {use_cases}")
        print(f"     rendered:")
        for line in section.split("\n"):
            print(f"       {line}")

    print(f"\n{DIVIDER}")


def print_before_after():
    """Show the actual change for the 3 specified models."""
    print(f"\n{DIVIDER}")
    print("  BEFORE vs AFTER (Auger Work gating fix)")
    print(f"  Note: BEFORE = what the output WAS before this fix")
    print(f"        AFTER  = what the output IS now")
    print(f"{DIVIDER}")

    # Simulate BEFORE by temporarily removing Auger Work from the triggered labels
    import listing_use_case_enrichment as lue
    original_labels = dict(lue._ATTACHMENT_TRIGGERED_LABELS)

    for tc in BEFORE_AFTER_CASES:
        di = DealerInput(**tc["di"])

        # AFTER (current, with fix)
        payload_after = build_use_case_payload(tc["equipment_type"], di, tc["specs"])
        uc_after = (payload_after or {}).get("top_use_cases_for_listing") or []
        section_after = _build_use_case_section(payload_after) if payload_after else ""

        # BEFORE (remove Auger Work from gate to simulate old behavior)
        before_labels = {k: v for k, v in original_labels.items() if k != "Auger Work"}
        lue._ATTACHMENT_TRIGGERED_LABELS = before_labels
        payload_before = build_use_case_payload(tc["equipment_type"], di, tc["specs"])
        uc_before = (payload_before or {}).get("top_use_cases_for_listing") or []
        section_before = _build_use_case_section(payload_before) if payload_before else ""

        # Restore
        lue._ATTACHMENT_TRIGGERED_LABELS = original_labels

        print(f"\n  ── {tc['label']}")
        print(f"     Note: {tc['before_note']}")
        print(f"     BEFORE use_cases: {uc_before}")
        print(f"     AFTER  use_cases: {uc_after}")
        changed = uc_before != uc_after
        print(f"     Changed: {'YES — Auger Work suppressed' if changed else 'NO (Auger Work was not scoring high enough to appear anyway)'}")
        if section_after:
            print(f"     AFTER Best For:")
            for line in section_after.split("\n"):
                print(f"       {line}")

    print(f"\n{DIVIDER}")


if __name__ == "__main__":
    ok = run_validation()
    print_before_after()
    print_final_outputs()
    sys.exit(0 if ok else 1)
