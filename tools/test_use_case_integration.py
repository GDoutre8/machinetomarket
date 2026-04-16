"""
tools/test_use_case_integration.py
====================================
MTM Use Case Scorer Integration Test

Loads live registry records and runs them through the locked use case scorers.
Verifies that registry → MachineRecord → scorer pipeline works end-to-end.

Machines tested:
  SSL:    Bobcat S650,          JD 324G  (note: JD 325G is a CTL, not SSL)
  CTL:    Caterpillar 259D3,    JD 325G
  Mini Ex: Kubota KX057-6,      JD 35G   (note: KX057-5 not in registry; using KX057-6)

Run from project root:
    python tools/test_use_case_integration.py
"""

from __future__ import annotations

import json
import os
import sys

# ---------------------------------------------------------------------------
# Path setup — allow running from project root or tools/ subfolder
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

REGISTRY_DIR = os.path.join(ROOT, "registry")

# ---------------------------------------------------------------------------
# Scorer imports
# ---------------------------------------------------------------------------
from scorers.skid_steer_use_case_scorer_v1_0 import (
    score_skid_steer,
    MachineRecord as SSLRecord,
)
from scorers.ctl_use_case_scorer_v1_0 import (
    score_registry_record as ctl_score_registry_record,
    machine_record_from_registry as ctl_adapter,
)
from scorers.mini_ex_use_case_scorer_v1_0 import (
    score_mini_ex,
    MachineRecord as MiniExRecord,
)


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def load_registry(filename: str) -> list[dict]:
    path = os.path.join(REGISTRY_DIR, filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if "records" in data:
        return data["records"]
    return list(data.values())


def find_record(records: list[dict], slug: str) -> dict:
    for r in records:
        if r.get("model_slug") == slug:
            return r
    raise ValueError(f"Record not found: {slug!r}")


# ---------------------------------------------------------------------------
# SSL adapter  (skid steer scorer has no built-in registry adapter)
# ---------------------------------------------------------------------------

def ssl_adapter(reg: dict) -> SSLRecord:
    """Build an SSLRecord from a nested registry record."""
    specs = reg.get("specs") or {}
    flags = reg.get("feature_flags") or {}
    dealer = reg.get("dealer_inputs") or {}
    options = reg.get("options") or {}

    # high_flow_available: prefer explicit flag, fall back to aux_flow_high_gpm presence
    hf_gpm = specs.get("aux_flow_high_gpm")
    if flags.get("high_flow_available") is not None:
        high_flow = flags["high_flow_available"]
    elif options.get("high_flow") is True or (hf_gpm is not None and hf_gpm > 0):
        high_flow = True
    elif options.get("high_flow") is False:
        high_flow = False
    else:
        high_flow = None

    # two_speed_available
    travel_high = specs.get("travel_speed_high_mph")
    if flags.get("two_speed_available") is not None:
        two_speed = flags["two_speed_available"]
    elif options.get("two_speed") is True or (travel_high is not None and travel_high > 7):
        two_speed = True
    elif options.get("two_speed") is False:
        two_speed = False
    else:
        two_speed = None

    # enclosed_cab_available
    if flags.get("enclosed_cab_available") is not None:
        enclosed_cab = flags["enclosed_cab_available"]
    else:
        cab_raw = (dealer.get("cab_type") or "").lower().strip()
        if cab_raw in ("enclosed", "erops", "closed", "cab"):
            enclosed_cab = True
        elif cab_raw in ("open", "rops", "canopy", "orops"):
            enclosed_cab = False
        else:
            enclosed_cab = None

    # ride_control_available
    if flags.get("ride_control_available") is not None:
        ride_control = flags["ride_control_available"]
    else:
        ride_raw = options.get("ride_control")
        ride_control = ride_raw if isinstance(ride_raw, bool) else None

    # joystick_controls_available
    if flags.get("joystick_controls_available") is not None:
        joystick = flags["joystick_controls_available"]
    else:
        joystick = None

    return SSLRecord(
        horsepower_hp=specs.get("horsepower_hp"),
        rated_operating_capacity_lbs=specs.get("rated_operating_capacity_lbs"),
        operating_weight_lbs=specs.get("operating_weight_lbs"),
        aux_flow_standard_gpm=specs.get("aux_flow_standard_gpm"),
        aux_flow_high_gpm=specs.get("aux_flow_high_gpm"),
        hydraulic_pressure_standard_psi=specs.get("hydraulic_pressure_standard_psi"),
        hydraulic_pressure_high_psi=specs.get("hydraulic_pressure_high_psi"),
        bucket_hinge_pin_height_in=specs.get("bucket_hinge_pin_height_in"),
        lift_path=specs.get("lift_path"),
        brand=reg.get("manufacturer") or reg.get("brand"),
        hours=dealer.get("hours"),
        tire_condition_pct=dealer.get("tire_condition_pct"),
        high_flow_available=high_flow,
        two_speed_available=two_speed,
        enclosed_cab_available=enclosed_cab,
        ride_control_available=ride_control,
        joystick_controls_available=joystick,
    )


# ---------------------------------------------------------------------------
# Mini ex adapter  (score_registry_record expects flat dict; registry is nested)
# ---------------------------------------------------------------------------

def mini_ex_adapter(reg: dict) -> MiniExRecord:
    """Build a MiniExRecord from a nested registry record."""
    specs  = reg.get("specs") or {}
    flags  = reg.get("feature_flags") or {}
    dealer = reg.get("dealer_inputs") or {}

    # tail_swing_type: prefer specs field; synthesize from zero_tail_swing flag if absent
    tail_swing = specs.get("tail_swing_type")
    if tail_swing is None:
        if flags.get("zero_tail_swing") is True:
            tail_swing = "zero"

    # two_speed_travel
    two_speed = flags.get("two_speed_travel_available")

    # blade_available: true if blade_width_in is set or a blade flag exists
    blade_width = specs.get("blade_width_in")
    blade_available = (blade_width is not None and blade_width > 0) or flags.get("blade_available") or False

    # year: take start year from years_supported
    years = reg.get("years_supported") or {}
    year = years.get("start") or years.get("end")

    return MiniExRecord(
        make=reg.get("manufacturer"),
        model=reg.get("model"),
        year=year,
        operating_weight_lbs=specs.get("operating_weight_lbs"),
        max_dig_depth_ft=specs.get("max_dig_depth_ft"),
        max_dump_height_ft=specs.get("max_dump_height_ft"),
        max_reach_ft=specs.get("max_reach_ft"),
        width_in=specs.get("width_in"),
        auxiliary_hydraulics_available=flags.get("auxiliary_hydraulics_available"),
        aux_flow_primary_gpm=specs.get("aux_flow_primary_gpm"),
        aux_pressure_primary_psi=specs.get("aux_pressure_primary_psi"),
        tail_swing_type=tail_swing,
        two_speed_travel=two_speed,
        enclosed_cab_available=flags.get("enclosed_cab_available"),
        hydraulic_thumb_available=flags.get("hydraulic_thumb_available"),
        retractable_undercarriage=specs.get("retractable_undercarriage") or flags.get("retractable_undercarriage"),
        angle_blade_available=flags.get("angle_blade_available"),
        blade_available=blade_available,
        brand=reg.get("manufacturer"),
        hours=dealer.get("hours"),
        track_condition_pct=dealer.get("track_condition_pct"),
    )


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

DIVIDER = "-" * 60

def label_bar(score) -> str:
    """Compact visual bar for a 0-100 score."""
    if score is None:
        return "[----]"
    filled = round(score / 10)
    return "[" + "#" * filled + "." * (10 - filled) + "]"


def print_machine_result(display_name: str, machine_type: str, result, note: str = "") -> None:
    """Print clean, readable output for one machine's scoring result."""
    print(f"\n{'=' * 60}")
    print(f"  Machine:  {display_name}")
    print(f"  Type:     {machine_type}")
    if note:
        print(f"  Note:     {note}")
    print(f"  Class:    {result.capability_class}  —  {result.capability_class_label}")

    # hydraulic_tier only exists on mini ex results
    if hasattr(result, "hydraulic_tier"):
        print(f"  Hyd Tier: {result.hydraulic_tier}")

    confidence = getattr(result, "confidence_level", None)
    if confidence:
        print(f"  Confidence: {confidence}")

    # ---- Top 5 Use Cases ----
    use_cases = getattr(result, "all_use_cases", [])
    # Sort descending by score (None treated as -1)
    use_cases_sorted = sorted(
        use_cases,
        key=lambda uc: uc.score if uc.score is not None else -1,
        reverse=True,
    )
    print(f"\n  Top Use Cases:")
    for i, uc in enumerate(use_cases_sorted[:5], 1):
        score_str = str(uc.score) if uc.score is not None else "N/A"
        bar = label_bar(uc.score)
        print(f"    {i}. {uc.use_case:<40} {score_str:>3}  {bar}  {uc.label}")

    # ---- Bottom 2 (lowest scoring) ----
    bottom = use_cases_sorted[-2:] if len(use_cases_sorted) >= 2 else []
    if bottom:
        print(f"\n  Lowest Use Cases:")
        for uc in bottom:
            score_str = str(uc.score) if uc.score is not None else "N/A"
            print(f"    - {uc.use_case:<40} {score_str:>3}  {uc.label}")

    # ---- Attachments ----
    attachment_scores = getattr(result, "attachment_scores", None)
    attachment_compatibility = getattr(result, "attachment_compatibility", None)

    if attachment_scores:
        # mini ex: dict[str, UseCaseScore]
        att_list = sorted(
            [(name, uc) for name, uc in attachment_scores.items() if uc.score is not None],
            key=lambda x: x[1].score,
            reverse=True,
        )
        print(f"\n  Top Attachments:")
        for i, (name, uc) in enumerate(att_list[:5], 1):
            bar = label_bar(uc.score)
            print(f"    {i}. {name:<36} {uc.score:>3}  {bar}  {uc.label}")

    elif attachment_compatibility:
        # ssl/ctl: dict[str, dict] with keys: compatible (bool), summary (str), attachments (list)
        # Structure: {"tier_1_low_demand": {...}, "tier_2_medium_demand": {...}, "tier_3_high_demand": {...}}
        TIER_LABELS = {
            "tier_1_low_demand":    "Tier 1 (standard)",
            "tier_2_medium_demand": "Tier 2 (medium demand)",
            "tier_3_high_demand":   "Tier 3 (high flow)",
        }
        print(f"\n  Attachment Tiers:")
        for tier_key in ("tier_1_low_demand", "tier_2_medium_demand", "tier_3_high_demand"):
            info = attachment_compatibility.get(tier_key)
            if info is None:
                continue
            compatible = info.get("compatible")
            status = "YES" if compatible else "NO "
            label = TIER_LABELS.get(tier_key, tier_key)
            summary = info.get("summary", "")
            print(f"    [{status}] {label}")
            print(f"          {summary}")
            examples = info.get("attachments", [])[:3]
            if examples:
                print(f"          e.g. {', '.join(examples)}")

    # ---- Scoring flags ----
    flags = getattr(result, "scoring_flags", [])
    if flags:
        print(f"\n  Scoring Flags:")
        for f in flags[:5]:
            print(f"    ! {f}")

    print(DIVIDER)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_tests():
    print("\nMTM Use Case Scorer — Integration Test")
    print("=" * 60)
    print("Loading registries...")

    ssl_registry = load_registry("mtm_skid_steer_registry_v1_11.json")
    ctl_registry = load_registry("mtm_ctl_registry_v1_17.json")
    mex_registry = load_registry("mtm_mini_ex_registry_v2.json")

    print(f"  SSL: {len(ssl_registry)} records")
    print(f"  CTL: {len(ctl_registry)} records")
    print(f"  Mini Ex: {len(mex_registry)} records")

    results_summary = []
    errors = []

    # ------------------------------------------------------------------
    # 1. Bobcat S650  (SSL)
    # ------------------------------------------------------------------
    try:
        rec = find_record(ssl_registry, "bobcat_s650")
        mr  = ssl_adapter(rec)
        res = score_skid_steer(mr)
        yr  = rec.get("years_supported", {})
        display = f"{yr.get('start', '?')}–{yr.get('end', '?')} Bobcat S650"
        print_machine_result(display, "Skid Steer", res)
        results_summary.append(("Bobcat S650 (SSL)", res.capability_class, getattr(res, "confidence_level", "—")))
    except Exception as e:
        errors.append(f"Bobcat S650: {e}")
        print(f"\n  ERROR — Bobcat S650: {e}")

    # ------------------------------------------------------------------
    # 2. John Deere 324G  (SSL — 325G is a CTL; 324G is nearest SSL)
    # ------------------------------------------------------------------
    try:
        rec = find_record(ssl_registry, "jd_324g")
        mr  = ssl_adapter(rec)
        res = score_skid_steer(mr)
        yr  = rec.get("years_supported", {})
        display = f"{yr.get('start', '?')}–{yr.get('end', '?')} John Deere 324G"
        print_machine_result(display, "Skid Steer",  res,
            note="JD 325G requested; 325G is a CTL — using 324G as SSL equivalent")
        results_summary.append(("JD 324G / 325G-SSL-equiv", res.capability_class, getattr(res, "confidence_level", "—")))
    except Exception as e:
        errors.append(f"JD 324G: {e}")
        print(f"\n  ERROR — JD 324G: {e}")

    # ------------------------------------------------------------------
    # 3. Caterpillar 259D3  (CTL)
    # ------------------------------------------------------------------
    try:
        rec = find_record(ctl_registry, "cat_259d3")
        res = ctl_score_registry_record(rec)
        yr  = rec.get("years_supported", {})
        display = f"{yr.get('start', '?')}–{yr.get('end', '?')} Caterpillar 259D3"
        print_machine_result(display, "CTL", res)
        results_summary.append(("Cat 259D3 (CTL)", res.capability_class, getattr(res, "confidence_level", "—")))
    except Exception as e:
        errors.append(f"Cat 259D3: {e}")
        print(f"\n  ERROR — Cat 259D3: {e}")

    # ------------------------------------------------------------------
    # 4. John Deere 325G  (CTL — note: was requested as SSL but is CTL)
    # ------------------------------------------------------------------
    try:
        rec = find_record(ctl_registry, "jd_325g")
        res = ctl_score_registry_record(rec)
        yr  = rec.get("years_supported", {})
        display = f"{yr.get('start', '?')}–{yr.get('end', '?')} John Deere 325G"
        print_machine_result(display, "CTL",
            res, note="Requested as SSL — JD 325G is a CTL; scored with CTL scorer")
        results_summary.append(("JD 325G (CTL, not SSL)", res.capability_class, getattr(res, "confidence_level", "—")))
    except Exception as e:
        errors.append(f"JD 325G: {e}")
        print(f"\n  ERROR — JD 325G: {e}")

    # ------------------------------------------------------------------
    # 5. Kubota KX057-6  (Mini Ex — KX057-5 not in registry)
    # ------------------------------------------------------------------
    try:
        rec = find_record(mex_registry, "kubota_kx057_6")
        mr  = mini_ex_adapter(rec)
        res = score_mini_ex(mr)
        yr  = rec.get("years_supported", {})
        display = f"{yr.get('start', '?')}–{yr.get('end', '?')} Kubota KX057-6"
        print_machine_result(display, "Mini Excavator", res,
            note="KX057-5 not in registry; using KX057-6 (same platform, updated tier)")
        results_summary.append(("Kubota KX057-6 (Mini Ex)", res.capability_class, res.hydraulic_tier))
    except Exception as e:
        errors.append(f"Kubota KX057-6: {e}")
        print(f"\n  ERROR — Kubota KX057-6: {e}")

    # ------------------------------------------------------------------
    # 6. John Deere 35G  (Mini Ex)
    # ------------------------------------------------------------------
    try:
        rec = find_record(mex_registry, "jd_35g")
        mr  = mini_ex_adapter(rec)
        res = score_mini_ex(mr)
        yr  = rec.get("years_supported", {})
        display = f"{yr.get('start', '?')}–{yr.get('end', '?')} John Deere 35G"
        print_machine_result(display, "Mini Excavator", res)
        results_summary.append(("JD 35G (Mini Ex)", res.capability_class, res.hydraulic_tier))
    except Exception as e:
        errors.append(f"JD 35G: {e}")
        print(f"\n  ERROR — JD 35G: {e}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("INTEGRATION TEST SUMMARY")
    print(f"{'=' * 60}")
    print(f"  {'Machine':<36} {'Class':>5}  {'Tier / Confidence'}")
    print(f"  {'-'*36}  {'-'*5}  {'-'*20}")
    for name, cls, tier in results_summary:
        print(f"  {name:<36} {cls:>5}  {tier}")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    !! {e}")
        print("\n  STATUS: INTEGRATION FAILED — see errors above")
        return False
    else:
        print(f"\n  Machines tested:  {len(results_summary)}")
        print(f"  Errors:           0")
        print(f"\n  STATUS: INTEGRATION PASSED")
        return True


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
