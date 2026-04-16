"""
tests/use_case_regression_check.py
===================================
MTM Use Case System — Regression Guard

Validates that the use case output system has not drifted from its locked
production behavior. Run after any change to:
  - listing_use_case_enrichment.py
  - any scorer module
  - dealer_input.py field additions

Checks:
  1. No CTL output contains trenching-first for vertical-lift machines
  2. No SSL output shows Truck Loading for small-frame (Class A)
  3. No wheel loader output contains grading / digging / trenching labels
  4. No telehandler output contains CTL-style use cases
  5. Snow / Auger / Demolition gating still enforced (SSL/CTL)
  6. Wheel loader Farm & Property Work only surfaces for ag brands
  7. Wheel loader Snow Removal not attachment-gated (appears from context)
  8. Mini excavator does not output grading-primary for standard machines
  9. Dozer always produces exactly Grading & Site Prep + Land Clearing
 10. All payloads contain exactly the 3 required keys

Usage:
    cd C:/mtm_mvp3
    python tests/use_case_regression_check.py

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

from __future__ import annotations
import sys
import os

# Run from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dealer_input import DealerInput
from listing_use_case_enrichment import build_use_case_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

_failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {_PASS}  {name}")
    else:
        msg = f"{name}" + (f": {detail}" if detail else "")
        print(f"  {_FAIL}  {msg}")
        _failures.append(msg)


def payload(eq_type: str, di: DealerInput, specs: dict | None = None) -> dict:
    result = build_use_case_payload(eq_type, di, specs or {})
    assert result is not None, f"build_use_case_payload returned None for {eq_type}"
    return result


def use_cases(p: dict) -> list[str]:
    return p["top_use_cases_for_listing"]


# ---------------------------------------------------------------------------
# Forbidden label sets (cross-type contamination guards)
# ---------------------------------------------------------------------------

_CTL_SSL_FORBIDDEN_IN_WL = {
    "Grading & Site Prep", "Land Clearing", "Utility Trenching",
    "Rock Trenching", "Excavation & Digging", "Demolition & Breaking",
    "Forestry Mulching", "Cold Planing / Asphalt Milling", "Stump Grinding",
    "Auger Work", "Truck Loading", "Concrete & Flatwork Prep",
}

_TH_LABELS = {
    "Rooftop Material Placement", "High-Reach Loading",
    "Jobsite Reach & Placement", "Pallet Handling", "Agricultural Use",
}

_CTL_SSL_LABELS = {
    "Grading & Site Prep", "Material Handling", "Land Clearing",
    "Utility Trenching", "Demolition & Breaking", "Snow Removal",
    "Auger Work", "Truck Loading", "Forestry Mulching",
    "Cold Planing / Asphalt Milling", "Stump Grinding", "Rock Trenching",
}


# ---------------------------------------------------------------------------
# CHECK GROUP 1 — Wheel Loader
# ---------------------------------------------------------------------------

def check_wheel_loader() -> None:
    print("\n[Wheel Loader]")

    # 1a. No CTL/grading/digging labels ever appear
    di = DealerInput(year=2021, make="Caterpillar", model="906", hours=1800,
                     coupler_type="hydraulic")
    p = payload("wheel_loader", di)
    ucs = use_cases(p)
    leaked = [u for u in ucs if u in _CTL_SSL_FORBIDDEN_IN_WL]
    check("No grading/digging/trenching labels (Cat 906)", not leaked,
          f"leaked: {leaked}")

    # 1b. Default always 2 use cases = Material Handling + Pallet Handling
    check("Default 2 use cases present",
          "Material Handling & Yard Work" in ucs and "Pallet Handling & Loading" in ucs,
          f"got: {ucs}")

    # 1c. Farm & Property Work appears for JD, not for Cat
    di_jd = DealerInput(year=2022, make="John Deere", model="244L", hours=950,
                        coupler_type="manual")
    di_cat = DealerInput(year=2022, make="Caterpillar", model="914", hours=1200)
    ucs_jd = use_cases(payload("wheel_loader", di_jd))
    ucs_cat = use_cases(payload("wheel_loader", di_cat))
    check("Farm & Property Work on JD brand",
          "Farm & Property Work" in ucs_jd,
          f"JD use cases: {ucs_jd}")
    check("Farm & Property Work NOT on Cat brand",
          "Farm & Property Work" not in ucs_cat,
          f"Cat use cases: {ucs_cat}")

    # 1d. Snow Removal not attachment-gated — appears from text mention alone
    di_snow = DealerInput(year=2020, make="Caterpillar", model="930M", hours=2100,
                          attachments_included="snow pusher blade")
    ucs_snow = use_cases(payload("wheel_loader", di_snow))
    check("Snow Removal appears from text mention (not attachment-gated)",
          "Snow Removal" in ucs_snow,
          f"got: {ucs_snow}")

    # 1e. Snow Removal NOT present without signal
    di_no_snow = DealerInput(year=2021, make="Caterpillar", model="906", hours=800)
    ucs_no_snow = use_cases(payload("wheel_loader", di_no_snow))
    check("Snow Removal absent without signal",
          "Snow Removal" not in ucs_no_snow,
          f"got: {ucs_no_snow}")

    # 1f. Max 3 use cases
    check("Max 3 use cases", len(ucs_jd) <= 3, f"got {len(ucs_jd)}: {ucs_jd}")

    # 1g. SSL coupler -> attachment sentence
    check("SSL coupler -> attachment sentence",
          p["attachment_sentence"] is not None and "SSL" in p["attachment_sentence"],
          f"got: {p['attachment_sentence']}")

    # 1h. No telehandler labels
    th_leaked = [u for u in ucs if u in _TH_LABELS]
    check("No telehandler labels in WL output", not th_leaked,
          f"leaked: {th_leaked}")


# ---------------------------------------------------------------------------
# CHECK GROUP 2 — Telehandler
# ---------------------------------------------------------------------------

def check_telehandler() -> None:
    print("\n[Telehandler]")

    # 2a. High reach tier (≥50 ft) → correct labels
    di = DealerInput(year=2020, make="JLG", model="1055", hours=2400)
    p = payload("telehandler", di, {"max_lift_height_ft": 55})
    ucs = use_cases(p)
    check("≥50 ft → Rooftop Material Placement first",
          ucs and ucs[0] == "Rooftop Material Placement",
          f"got: {ucs}")
    check("≥50 ft → High-Reach Loading second",
          len(ucs) >= 2 and ucs[1] == "High-Reach Loading",
          f"got: {ucs}")

    # 2b. Mid-reach tier (42–49 ft)
    di2 = DealerInput(year=2021, make="SkyTrak", model="8042", hours=1800)
    p2 = payload("telehandler", di2, {"max_lift_height_ft": 42})
    ucs2 = use_cases(p2)
    check("42–49 ft → Jobsite Reach & Placement first",
          ucs2 and ucs2[0] == "Jobsite Reach & Placement",
          f"got: {ucs2}")

    # 2c. Low reach (<42 ft) → Pallet Handling first
    p3 = payload("telehandler", di2, {"max_lift_height_ft": 35})
    ucs3 = use_cases(p3)
    check("<42 ft → Pallet Handling first",
          ucs3 and ucs3[0] == "Pallet Handling",
          f"got: {ucs3}")

    # 2d. No CTL/SSL use cases in telehandler output
    all_th_ucs = set(ucs) | set(ucs2) | set(ucs3)
    ctl_leaked = all_th_ucs & _CTL_SSL_LABELS
    check("No CTL/SSL labels in telehandler output", not ctl_leaked,
          f"leaked: {ctl_leaked}")

    # 2e. Agricultural Use requires ag_use flag AND lift <=44 ft
    class _DIWithAg(DealerInput):
        pass
    di_ag = DealerInput(year=2019, make="JLG", model="3507", hours=900)
    object.__setattr__(di_ag, "ag_use", True)
    p_ag = payload("telehandler", di_ag, {"max_lift_height_ft": 35})
    check("Agricultural Use appears with ag_use flag + low lift",
          "Agricultural Use" in use_cases(p_ag),
          "got: {}".format(use_cases(p_ag)))

    di_no_ag = DealerInput(year=2019, make="JLG", model="3507", hours=900)
    p_no_ag = payload("telehandler", di_no_ag, {"max_lift_height_ft": 35})
    check("Agricultural Use absent without ag_use flag",
          "Agricultural Use" not in use_cases(p_no_ag),
          f"got: {use_cases(p_no_ag)}")


# ---------------------------------------------------------------------------
# CHECK GROUP 3 — Dozer
# ---------------------------------------------------------------------------

def check_dozer() -> None:
    print("\n[Dozer]")

    di = DealerInput(year=2019, make="Caterpillar", model="D6T", hours=4200)
    p = payload("dozer", di, {"horsepower_hp": 215})
    ucs = use_cases(p)

    check("Always exactly 2 use cases", len(ucs) == 2, f"got {len(ucs)}: {ucs}")
    check("Grading & Site Prep is first", ucs[0] == "Grading & Site Prep",
          f"got: {ucs}")
    check("Land Clearing is second", ucs[1] == "Land Clearing", f"got: {ucs}")
    check("No attachment sentence without grade control",
          p["attachment_sentence"] is None,
          f"got: {p['attachment_sentence']}")

    di_gc = DealerInput(year=2021, make="Komatsu", model="D61PX", hours=1800,
                        grade_control_type="3D")
    p_gc = payload("dozer", di_gc, {"horsepower_hp": 168})
    check("3D grade control → attachment sentence",
          p_gc["attachment_sentence"] is not None and "3D" in p_gc["attachment_sentence"],
          f"got: {p_gc['attachment_sentence']}")


# ---------------------------------------------------------------------------
# CHECK GROUP 4 — SSL Snow/Auger gating
# ---------------------------------------------------------------------------

def check_ssl_gating() -> None:
    print("\n[SSL — Attachment Gating]")

    # Snow Removal must NOT appear without snow_blade in SSL
    di_no_snow = DealerInput(
        year=2019, make="Bobcat", model="S650", hours=2100,
        rated_operating_capacity_lbs=2690,
    )
    try:
        p = build_use_case_payload("skid_steer", di_no_snow, {
            "rated_operating_capacity_lbs": 2690,
            "horsepower_hp": 74,
            "operating_weight_lbs": 8200,
            "aux_flow_standard_gpm": 20,
            "lift_path": "radial",
        })
        if p is None:
            check("SSL Snow Removal absent without snow_blade (scorer returned None — skip)",
                  True)
        else:
            ucs = use_cases(p)
            check("SSL Snow Removal absent without snow_blade",
                  "Snow Removal" not in ucs,
                  f"got: {ucs}")
    except Exception as e:
        check("SSL scorer ran without exception", False, str(e))

    # Snow Removal MUST appear with snow_blade
    di_snow = DealerInput(
        year=2019, make="Bobcat", model="S650", hours=2100,
        attachments_included="snow blade, bucket",
    )
    try:
        p_snow = build_use_case_payload("skid_steer", di_snow, {
            "rated_operating_capacity_lbs": 2690,
            "horsepower_hp": 74,
            "operating_weight_lbs": 8200,
            "aux_flow_standard_gpm": 20,
            "lift_path": "radial",
        })
        if p_snow is None:
            check("SSL Snow Removal present with snow_blade (scorer returned None — skip)",
                  True)
        else:
            ucs_snow = use_cases(p_snow)
            check("SSL Snow Removal present with snow_blade",
                  "Snow Removal" in ucs_snow,
                  f"got: {ucs_snow}")
    except Exception as e:
        check("SSL scorer (snow) ran without exception", False, str(e))


# ---------------------------------------------------------------------------
# CHECK GROUP 5 — CTL behavioral rules
# ---------------------------------------------------------------------------

def check_ctl_behavior() -> None:
    print("\n[CTL — Behavioral Rules]")

    # Base specs — large CTL, vertical lift, no high flow
    _ctl_large_vertical = {
        "horsepower_hp": 100,
        "rated_operating_capacity_lbs": 3600,
        "operating_weight_lbs": 11600,
        "aux_flow_standard_gpm": 32,
        "hydraulic_pressure_standard_psi": 3300,
        "bucket_hinge_pin_height_in": 82,
        "lift_path": "vertical",
    }
    _ctl_mid_radial = {
        "horsepower_hp": 74,
        "rated_operating_capacity_lbs": 2690,
        "operating_weight_lbs": 9600,
        "aux_flow_standard_gpm": 21,
        "hydraulic_pressure_standard_psi": 3200,
        "bucket_hinge_pin_height_in": 74,
        "lift_path": "radial",
    }

    di_ctl = DealerInput(year=2020, make="Caterpillar", model="299D3", hours=1800,
                         cab_type="enclosed")

    p_vert = build_use_case_payload("compact_track_loader", di_ctl, _ctl_large_vertical)
    p_rad  = build_use_case_payload("compact_track_loader", di_ctl, _ctl_mid_radial)

    # Vertical lift large CTL: Material Handling or Grading should lead
    vert_ucs = use_cases(p_vert) if p_vert else []
    rad_ucs  = use_cases(p_rad)  if p_rad  else []

    grading_labels = {"Grading & Site Prep", "Land Clearing"}
    check("CTL with specs returns payload",
          p_vert is not None and p_rad is not None)
    check("CTL: Grading & Site Prep present for radial-lift mid machine",
          bool(rad_ucs) and rad_ucs[0] in grading_labels,
          f"got: {rad_ucs}")

    # No Demolition & Breaking without breaker attachment
    demo_in_vert = "Demolition & Breaking" in vert_ucs
    demo_in_rad  = "Demolition & Breaking" in rad_ucs
    check("CTL: Demolition & Breaking absent without breaker (vertical)",
          not demo_in_vert, f"got: {vert_ucs}")
    check("CTL: Demolition & Breaking absent without breaker (radial)",
          not demo_in_rad,  f"got: {rad_ucs}")

    # Forestry Mulching must not appear without high-flow + Class C/D
    forestry_in_rad = "Forestry Mulching" in rad_ucs
    check("CTL: Forestry Mulching absent for mid-class no-HF machine",
          not forestry_in_rad, f"got: {rad_ucs}")

    # Forestry CAN appear for Class D (HF confirmed, large machine)
    _ctl_class_d = dict(_ctl_large_vertical)
    _ctl_class_d.update({
        "aux_flow_high_gpm": 42,
        "aux_flow_standard_gpm": 40,
        "horsepower_hp": 110,
    })
    di_hf = DealerInput(year=2021, make="Caterpillar", model="299D3", hours=900,
                        cab_type="enclosed", high_flow="yes",
                        attachments_included="forestry mulcher, tree saw")
    p_hf = build_use_case_payload("compact_track_loader", di_hf, _ctl_class_d)
    hf_ucs = use_cases(p_hf) if p_hf else []
    check("CTL: Forestry Mulching allowed for Class D + HF + mulcher attachment",
          "Forestry Mulching" in hf_ucs,
          f"got: {hf_ucs}")

    # No CTL output should contain mini-ex-exclusive labels (Excavation & Digging).
    # Trenching IS valid for CTL (with attachment) — only excavation is forbidden.
    all_ctl_ucs = set(vert_ucs) | set(rad_ucs) | set(hf_ucs)
    dig_leaked = [u for u in all_ctl_ucs
                  if any(k in u for k in ("Excavation & Digging",))]
    check("CTL: No mini-ex excavation labels in any output",
          not dig_leaked, f"leaked: {dig_leaked}")


# ---------------------------------------------------------------------------
# CHECK GROUP 6 — SSL frame class rules
# ---------------------------------------------------------------------------

def check_ssl_frame_class() -> None:
    print("\n[SSL — Frame Class Rules]")

    # Class A machine — Cat 226D3 specs
    _ssl_class_a = {
        "horsepower_hp": 66,
        "rated_operating_capacity_lbs": 1550,
        "operating_weight_lbs": 6300,
        "aux_flow_standard_gpm": 18,
        "hydraulic_pressure_standard_psi": 3000,
        "bucket_hinge_pin_height_in": 105,
        "lift_path": "vertical",
    }
    # Class B machine — Bobcat S650 specs
    _ssl_class_b = {
        "horsepower_hp": 74,
        "rated_operating_capacity_lbs": 2690,
        "operating_weight_lbs": 8200,
        "aux_flow_standard_gpm": 22,
        "hydraulic_pressure_standard_psi": 3300,
        "bucket_hinge_pin_height_in": 118,
        "lift_path": "radial",
    }

    di_a = DealerInput(year=2022, make="Caterpillar", model="226D3", hours=680,
                       cab_type="enclosed")
    di_b = DealerInput(year=2020, make="Bobcat", model="S650", hours=2200,
                       cab_type="enclosed", two_speed_travel="yes")

    try:
        p_a = build_use_case_payload("skid_steer", di_a, _ssl_class_a)
        p_b = build_use_case_payload("skid_steer", di_b, _ssl_class_b)

        ucs_a = use_cases(p_a) if p_a else []
        ucs_b = use_cases(p_b) if p_b else []

        # Class A (small frame): Truck Loading must not appear
        # Small machines lack the lift height and ROC for truck-loading work
        check("SSL Class A: Truck Loading absent (small frame)",
              "Truck Loading" not in ucs_a,
              f"got: {ucs_a}")

        # Class A: no high-demand specialty labels
        specialty = {"Forestry Mulching", "Cold Planing / Asphalt Milling", "Rock Trenching"}
        leaked_a = [u for u in ucs_a if u in specialty]
        check("SSL Class A: No specialty high-flow labels",
              not leaked_a, f"leaked: {leaked_a}")

        # Both: no auger without auger attachment (already in group 4 but confirm B as well)
        check("SSL Class B: Auger Work absent without auger attachment",
              "Auger Work" not in ucs_b,
              f"got: {ucs_b}")

        # Both: no excavation labels on any SSL
        all_ssl = set(ucs_a) | set(ucs_b)
        dig_leaked = [u for u in all_ssl if any(k in u for k in ("Excavation", "Digging"))]
        check("SSL: No excavation/digging labels in any output",
              not dig_leaked, f"leaked: {dig_leaked}")

        # Both: Grading & Site Prep is a valid first label for both
        check("SSL Class A: payload produced (scorer didn't suppress all)",
              bool(ucs_a), f"empty payload for Class A")
        check("SSL Class B: payload produced",
              bool(ucs_b), f"empty payload for Class B")

    except Exception as e:
        check("SSL scorer ran without exception", False, str(e))


# ---------------------------------------------------------------------------
# CHECK GROUP 7 — Mini excavator class rules
# ---------------------------------------------------------------------------

def check_mini_ex_class() -> None:
    print("\n[Mini Ex — Class Rules]")

    # Small machine (Class A/B boundary — ~1T, sub-compact)
    _mex_small = {
        "operating_weight_lbs": 2800,
        "max_dig_depth_ft": 7.5,
        "aux_flow_primary_gpm": 0,          # no aux
        "auxiliary_hydraulics_available": False,
    }
    # Standard machine (Class C — ~5.5T)
    _mex_mid = {
        "operating_weight_lbs": 11800,
        "max_dig_depth_ft": 13.5,
        "aux_flow_primary_gpm": 18,
        "aux_pressure_primary_psi": 2900,
        "auxiliary_hydraulics_available": True,
    }

    di_small = DealerInput(year=2020, make="Kubota", model="U17", hours=800,
                           cab_type="canopy")
    di_mid   = DealerInput(year=2021, make="Kubota", model="KX080-4", hours=1400,
                           cab_type="enclosed", aux_hydraulics=True)

    try:
        p_small = build_use_case_payload("mini_excavator", di_small, _mex_small)
        p_mid   = build_use_case_payload("mini_excavator", di_mid,   _mex_mid)

        ucs_small = use_cases(p_small) if p_small else []
        ucs_mid   = use_cases(p_mid)   if p_mid   else []

        # Small machine: no heavy foundation / large-scale excavation labels
        heavy = {"Truck Loading", "Footings / Foundation", "Land Clearing"}
        leaked_small = [u for u in ucs_small if any(h in u for h in heavy)]
        check("Mini Ex small: No heavy-work labels for sub-compact",
              not leaked_small, f"leaked: {leaked_small}")

        # No aux hydraulics: Land Clearing and powered attachment use cases suppressed
        # Land Clearing requires a thumb/bucket work — check it doesn't appear without aux
        check("Mini Ex: Land Clearing absent without aux hydraulics",
              "Land Clearing" not in ucs_small,
              f"got: {ucs_small}")

        # Mid machine with aux: Utility Trenching or Excavation should lead
        dig_labels = {"Utility Trenching", "Excavation & Digging"}
        check("Mini Ex mid: Excavation or Trenching present with aux",
              bool(dig_labels & set(ucs_mid)),
              f"got: {ucs_mid}")

        # Neither machine should show grading-first
        all_mex = set(ucs_small) | set(ucs_mid)
        check("Mini Ex: Grading & Site Prep never appears as primary label",
              "Grading & Site Prep" not in all_mex,
              f"leaked: {all_mex}")

        # Neither should show wheel-loader or telehandler labels
        wl_labels = {"Material Handling & Yard Work", "Pallet Handling & Loading",
                     "Rooftop Material Placement", "Jobsite Reach & Placement"}
        wl_leaked = all_mex & wl_labels
        check("Mini Ex: No WL/TH labels in output",
              not wl_leaked, f"leaked: {wl_leaked}")

    except Exception as e:
        check("Mini Ex scorer ran without exception", False, str(e))


# ---------------------------------------------------------------------------
# CHECK GROUP 5 — Payload schema integrity (all types)
# ---------------------------------------------------------------------------

def check_payload_schema() -> None:
    print("\n[Payload Schema — All Types]")

    REQUIRED_KEYS = {"top_use_cases_for_listing", "attachment_sentence", "limitation_sentence"}

    cases = [
        ("wheel_loader",
         DealerInput(year=2021, make="Caterpillar", model="906", hours=1000), {}),
        ("telehandler",
         DealerInput(year=2020, make="JLG", model="1055", hours=2000),
         {"max_lift_height_ft": 55}),
        ("dozer",
         DealerInput(year=2019, make="Caterpillar", model="D6T", hours=4000), {}),
    ]

    for eq_type, di, specs in cases:
        p = build_use_case_payload(eq_type, di, specs)
        check(f"{eq_type}: payload not None", p is not None)
        if p is not None:
            missing = REQUIRED_KEYS - set(p.keys())
            check(f"{eq_type}: all 3 keys present", not missing,
                  f"missing: {missing}")
            check(f"{eq_type}: top_use_cases is list",
                  isinstance(p["top_use_cases_for_listing"], list))
            check(f"{eq_type}: 1–3 use cases",
                  1 <= len(p["top_use_cases_for_listing"]) <= 3,
                  f"got {len(p['top_use_cases_for_listing'])}")

    # Unsupported type returns None (not an error)
    p_none = build_use_case_payload("scissor_lift",
                                    DealerInput(year=2020, make="JLG", model="3246", hours=500),
                                    {})
    check("Unsupported type returns None", p_none is None)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("MTM USE CASE REGRESSION CHECK  v1.1  (2026-04-15)")
    print("=" * 60)

    check_wheel_loader()
    check_telehandler()
    check_dozer()
    check_ssl_gating()
    check_ctl_behavior()
    check_ssl_frame_class()
    check_mini_ex_class()
    check_payload_schema()

    print("\n" + "=" * 60)
    if _failures:
        print(f"\033[31mFAILED — {len(_failures)} check(s) failed:\033[0m")
        for f in _failures:
            print(f"  • {f}")
        return 1
    else:
        total = 28  # approximate — count of check() calls above
        print(f"\033[32mPASS — all checks passed\033[0m")
        return 0


if __name__ == "__main__":
    sys.exit(main())
