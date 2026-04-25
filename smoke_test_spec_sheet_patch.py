"""
MTM Spec Sheet Post-Patch Smoke Test
=====================================
Tests: CTL, SSL (skid_steer), SSL (skid_steer_loader normalization), Mini Ex

Section A: Adapter-level field checks (no Playwright, fast)
Section B: Full pipeline checks — PNG render + ZIP contents (Playwright required)

Run:
    python smoke_test_spec_sheet_patch.py
"""

from __future__ import annotations
import copy
import json
import os
import sys
import zipfile
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dealer_input import DealerInput
from spec_sheet_renderer_adapter import build_spec_sheet_data
from mtm_service import safe_parse_listing, safe_lookup_machine, _run_spec_resolver, _make_session_dir
from listing_pack_builder import build_listing_pack_v1

# ── Shared test state ─────────────────────────────────────────────────────────
_results: dict[str, str] = {}
_errors:  list[str]      = []

def _ok(name: str, detail: str = "") -> None:
    _results[name] = "PASS"
    print(f"  [OK] {name}" + (f" — {detail}" if detail else ""))

def _fail(name: str, detail: str = "") -> None:
    _results[name] = "FAIL"
    _errors.append(name)
    print(f"  [!!] {name}: FAIL" + (f" — {detail}" if detail else ""))

def _section(title: str) -> None:
    print(f"\n{'='*66}")
    print(f"  {title}")
    print(f"{'='*66}")

def _check(name: str, cond: bool, detail: str = "") -> bool:
    (_ok if cond else _fail)(name, detail)
    return cond

# ── Shared dealer info ────────────────────────────────────────────────────────
DEALER_INFO = {
    "dealer_name":  "Smoke Test Equipment",
    "phone":        "(605) 555-0100",
    "email":        "test@smoketest.com",
    "location":     "Sioux Falls, SD",
    "website":      "smoketest.com",
    "accent_color": "yellow",
}
DEALER_CONTACT = {
    "dealer_name": DEALER_INFO["dealer_name"],
    "phone":       DEALER_INFO["phone"],
    "location":    DEALER_INFO["location"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Hardcoded resolved specs (registry-accurate, no AI call needed for field checks)
# ─────────────────────────────────────────────────────────────────────────────

CTL_SPECS = {
    "roc_lb":                    2200,
    "net_hp":                    74,
    "aux_flow_standard_gpm":     21,
    "aux_flow_high_gpm":         34,
    "operating_weight_lbs":      8675,
    "lift_path":                 "vertical",
    "tipping_load_lbs":          4400,
}

# Full registry-accurate CTL specs including the two audit-flagged fields
CTL_SPECS_FULL = {
    "rated_operating_capacity_lbs": 3255,
    "horsepower_hp":                100,
    "aux_flow_standard_gpm":        26,
    "aux_flow_high_gpm":            40,
    "operating_weight_lbs":         11540,
    "lift_path":                    "vertical",
    "tipping_load_lbs":             6510,
    "width_over_tires_in":          90,       # audit-flagged field
    "bucket_hinge_pin_height_in":   130,      # audit-flagged field
}

# Minimal stub — missing required fields to exercise limited-confidence guard
CTL_SPECS_WEAK = {
    "lift_path":      "radial",
    "tipping_load_lbs": 3200,
}

SSL_SPECS = {
    "rated_operating_capacity_lbs": 2100,
    "horsepower_hp":                66,
    "aux_flow_standard_gpm":        17,
    "aux_flow_high_gpm":            27,
    "operating_weight_lbs":         6594,
    "lift_path":                    "vertical",
    "tipping_load_lbs":             4200,
    "bucket_hinge_pin_height_in":   119,
}

MINI_EX_SPECS = {
    "operating_weight_lbs":     5787,
    "max_dig_depth_ft":         8.42,
    "net_hp":                   24,
    "horsepower_hp":            24,
    "max_reach_ft":             14.3,
    "bucket_breakout_force_lbs": 5291,
    "tail_swing_type":          "zero",
}


# =============================================================================
# SECTION A — Adapter-level field content checks (no Playwright)
# =============================================================================

_section("SECTION A — Adapter field checks (no Playwright)")

# ─── A1: CTL ─────────────────────────────────────────────────────────────────
print("\n  [A1] CTL — Bobcat T770")
di_ctl = DealerInput(
    year=2021, make="Bobcat", model="T770",
    hours=1840, cab_type="enclosed", ac=True, heater=True,
    high_flow="yes", two_speed_travel="yes", coupler_type="hydraulic",
    condition_grade="Excellent", track_percent_remaining=85,
    asking_price=72500, serial_number="B3S612345", stock_number="STK-1042",
)
ctl_data = build_spec_sheet_data(
    dealer_input_data       = di_ctl.model_dump(),
    enriched_resolved_specs = CTL_SPECS,
    equipment_type          = "compact_track_loader",
    dealer_contact          = DEALER_CONTACT,
    dealer_info             = DEALER_INFO,
    full_record             = {},
    photo_path              = None,
)
ctl_hero_labels = [t["label"] for t in ctl_data["specs"]["hero"]]
ctl_core_labels = [r["label"] for r in ctl_data["specs"]["core"]]
ctl_perf_labels = [r["label"] for r in ctl_data["specs"]["performance"]]

print(f"     Hero : {ctl_hero_labels}")
print(f"     Core : {ctl_core_labels}")
print(f"     Perf : {ctl_perf_labels}")
print(f"     track_label : {ctl_data['listing']['track_label']}")

_check("CTL.hero.roc",        "Rated Op Capacity" in ctl_hero_labels)
_check("CTL.hero.hp",         "Net Power"         in ctl_hero_labels)
_check("CTL.hero.aux_flow",   any("Aux Flow" in l for l in ctl_hero_labels))
_check("CTL.hero.lift_path",  any(l in ctl_hero_labels for l in ("Lift Path","Operating Weight")))
_check("CTL.core.no_roc",     "Rated Op Capacity"       not in ctl_core_labels, "removed from core")
_check("CTL.core.no_net_power","Net Power"               not in ctl_core_labels, "removed from core")
_check("CTL.core.no_aux_flow", not any("Aux Hydraulic" in l for l in ctl_core_labels), "removed from core")
_check("CTL.core.no_weight",  "Operating Weight"         not in ctl_core_labels, "removed from core")
_check("CTL.core.hours",      "Hours"    in ctl_core_labels)
_check("CTL.core.serial",     "Serial #" in ctl_core_labels)
_check("CTL.track_label",     ctl_data["listing"]["track_label"] == "Track % Remaining")
_check("CTL.track_pct",       ctl_data["listing"]["track_pct"] == "85%")

# ─── A2: SSL (skid_steer) ─────────────────────────────────────────────────────
print("\n  [A2] SSL — Bobcat S590 (equipment_type=skid_steer)")
di_ssl = DealerInput(
    year=2020, make="Bobcat", model="S590",
    hours=2100, cab_type="enclosed", ac=True, heater=True,
    high_flow="yes", two_speed_travel="yes", coupler_type="hydraulic",
    control_type="hand_foot",
    condition_grade="Good", track_percent_remaining=70,
    asking_price=39500, serial_number="SSL123456", stock_number="STK-SSL-01",
)
ssl_data = build_spec_sheet_data(
    dealer_input_data       = di_ssl.model_dump(),
    enriched_resolved_specs = SSL_SPECS,
    equipment_type          = "skid_steer",
    dealer_contact          = DEALER_CONTACT,
    dealer_info             = DEALER_INFO,
    full_record             = {},
    photo_path              = None,
)
ssl_hero_labels = [t["label"] for t in ssl_data["specs"]["hero"]]
ssl_core_labels = [r["label"] for r in ssl_data["specs"]["core"]]
ssl_perf_labels = [r["label"] for r in ssl_data["specs"]["performance"]]

print(f"     Hero : {ssl_hero_labels}")
print(f"     Core : {ssl_core_labels}")
print(f"     Perf : {ssl_perf_labels}")
print(f"     Features: {ssl_data['features']}")
print(f"     track_label : {ssl_data['listing']['track_label']}")

_check("SSL.hero.roc",         "Rated Op Capacity" in ssl_hero_labels)
_check("SSL.hero.hp",          "Net Power"         in ssl_hero_labels)
_check("SSL.hero.aux_flow",    any("Aux Flow" in l for l in ssl_hero_labels))
_check("SSL.hero.lift_type",   any(l in ssl_hero_labels for l in ("Lift Type", "Operating Weight")))
_check("SSL.core.no_roc",      "Rated Op Capacity"       not in ssl_core_labels, "removed from core")
_check("SSL.core.no_net_power","Net Power"               not in ssl_core_labels, "removed from core")
_check("SSL.core.no_aux_flow", not any("Aux Hydraulic" in l for l in ssl_core_labels), "removed from core")
_check("SSL.core.no_weight",   "Operating Weight"         not in ssl_core_labels, "removed from core")
_check("SSL.core.hours",       "Hours"    in ssl_core_labels)
_check("SSL.core.serial",      "Serial #" in ssl_core_labels)
_check("SSL.tire_label",       ssl_data["listing"]["track_label"] == "Tire % Remaining")
_check("SSL.tire_pct",         ssl_data["listing"]["track_pct"] == "70%")
# SSL features must not enter CTL fallthrough (no "High Flow Equipped" for SSL)
_check("SSL.features.no_high_flow_equipped",
       "High Flow Equipped" not in ssl_data["features"],
       "CTL-only label excluded from SSL")
# SSL must have control type (isolated SSL branch)
_check("SSL.features.control_type",
       any("Hand" in f or "Foot" in f or "Joystick" in f or "Controls" in f
           for f in ssl_data["features"]),
       "SSL control type label present")

# ─── A3: SSL (skid_steer_loader normalization) ────────────────────────────────
print("\n  [A3] SSL normalization — equipment_type='skid_steer_loader'")
ssl_loader_data = build_spec_sheet_data(
    dealer_input_data       = di_ssl.model_dump(),
    enriched_resolved_specs = SSL_SPECS,
    equipment_type          = "skid_steer_loader",   # should normalize to skid_steer
    dealer_contact          = DEALER_CONTACT,
    dealer_info             = DEALER_INFO,
    full_record             = {},
    photo_path              = None,
)
sll_hero_labels = [t["label"] for t in ssl_loader_data["specs"]["hero"]]
sll_core_labels = [r["label"] for r in ssl_loader_data["specs"]["core"]]
sll_perf_labels = [r["label"] for r in ssl_loader_data["specs"]["performance"]]
sll_track_label = ssl_loader_data["listing"]["track_label"]

print(f"     Hero : {sll_hero_labels}")
print(f"     Core : {sll_core_labels}")
print(f"     Perf : {sll_perf_labels}")
print(f"     track_label : {sll_track_label}")
print(f"     machine.category : {ssl_loader_data['machine']['category']}")

_check("SLL.normalizes_to_ssl",
       ssl_loader_data["machine"]["category"] == "Skid Steer Loader",
       f"got: {ssl_loader_data['machine']['category']}")
_check("SLL.tire_label",          sll_track_label == "Tire % Remaining",
       "not CTL Track % or generic")
_check("SLL.hero_matches_ssl",    sll_hero_labels == ssl_hero_labels,
       "identical to skid_steer branch")
_check("SLL.core_matches_ssl",    sll_core_labels == ssl_core_labels)
_check("SLL.no_generic_hero_fallback",
       "Net Power" not in sll_hero_labels or "Rated Op Capacity" in sll_hero_labels,
       "not generic fallback order (which puts Net Power first)")
_check("SLL.no_ctl_core_fallthrough",
       not any("Aux Hydraulic" in l for l in sll_core_labels),
       "CTL core not entered")
_check("SLL.no_ctl_features_fallthrough",
       "High Flow Equipped" not in ssl_loader_data["features"],
       "CTL feature fallthrough not entered")

# ─── A5: CTL strong — Machine Width in core, Hinge Pin Height in performance ──
print("\n  [A5] CTL strong specs — Cat 299D3 profile (width + hinge pin)")
di_ctl_strong = DealerInput(
    year=2022, make="Cat", model="299D3",
    hours=950, cab_type="enclosed", ac=True, heater=True,
    high_flow="yes", two_speed_travel="yes", coupler_type="hydraulic",
    condition_grade="Excellent", track_percent_remaining=92,
    asking_price=89500, serial_number="CAT299XYZ", stock_number="STK-2991",
)
ctl_strong_data = build_spec_sheet_data(
    dealer_input_data       = di_ctl_strong.model_dump(),
    enriched_resolved_specs = CTL_SPECS_FULL,
    equipment_type          = "compact_track_loader",
    dealer_contact          = DEALER_CONTACT,
    dealer_info             = DEALER_INFO,
    full_record             = {},
    photo_path              = None,
)
ctl_s_hero   = [t["label"] for t in ctl_strong_data["specs"]["hero"]]
ctl_s_core   = [r["label"] for r in ctl_strong_data["specs"]["core"]]
ctl_s_perf   = [r["label"] for r in ctl_strong_data["specs"]["performance"]]

print(f"     Hero : {ctl_s_hero}")
print(f"     Core : {ctl_s_core}")
print(f"     Perf : {ctl_s_perf}")
print(f"     oem_verified              : {ctl_strong_data.get('oem_verified')}")
print(f"     ctl_spec_sheet_confidence : {ctl_strong_data.get('ctl_spec_sheet_confidence')}")

_check("A5.CTL.core.machine_width",     "Machine Width"   in ctl_s_core,   "width_over_tires_in shown")
_check("A5.CTL.perf.hinge_pin",         "Hinge Pin Height" in ctl_s_perf,  "bucket_hinge_pin_height_in shown")
_check("A5.CTL.hero.roc_not_in_core",   "Rated Op Capacity" not in ctl_s_core)
_check("A5.CTL.hero.hp_not_in_core",    "Net Power"         not in ctl_s_core)
_check("A5.CTL.hero.aux_not_in_core",   not any("Aux" in l for l in ctl_s_core))
_check("A5.CTL.oem_verified",           ctl_strong_data.get("oem_verified") is True)
_check("A5.CTL.confidence_full",        ctl_strong_data.get("ctl_spec_sheet_confidence") == "full")
# Machine Width must NOT duplicate in performance (it lives in core)
_check("A5.CTL.no_width_in_perf",       not any("Width" in l for l in ctl_s_perf))

# ─── A6: CTL weak/stub — limited confidence guard ────────────────────────────
print("\n  [A6] CTL weak stub — limited confidence / quarantine guard")
di_ctl_weak = DealerInput(
    year=2019, make="Unknown", model="CTL-X",
    hours=3500,
    condition_grade="Fair",
    asking_price=18000,
)
ctl_weak_data = build_spec_sheet_data(
    dealer_input_data       = di_ctl_weak.model_dump(),
    enriched_resolved_specs = CTL_SPECS_WEAK,
    equipment_type          = "compact_track_loader",
    dealer_contact          = DEALER_CONTACT,
    dealer_info             = DEALER_INFO,
    full_record             = {},
    photo_path              = None,
)
ctl_w_core = [r["label"] for r in ctl_weak_data["specs"]["core"]]
ctl_w_perf = [r["label"] for r in ctl_weak_data["specs"]["performance"]]

print(f"     Core : {ctl_w_core}")
print(f"     Perf : {ctl_w_perf}")
print(f"     oem_verified              : {ctl_weak_data.get('oem_verified')}")
print(f"     ctl_spec_sheet_confidence : {ctl_weak_data.get('ctl_spec_sheet_confidence')}")

_check("A6.CTL.no_machine_width",   "Machine Width"    not in ctl_w_core,
       "absent because width_over_tires_in is None")
_check("A6.CTL.no_hinge_pin",       "Hinge Pin Height" not in ctl_w_perf,
       "absent because bucket_hinge_pin_height_in is None")
_check("A6.CTL.oem_not_verified",   ctl_weak_data.get("oem_verified") is False)
_check("A6.CTL.confidence_limited", ctl_weak_data.get("ctl_spec_sheet_confidence") == "limited")

# coverage_stub flag path
ctl_stub_data = build_spec_sheet_data(
    dealer_input_data       = di_ctl_weak.model_dump(),
    enriched_resolved_specs = CTL_SPECS_FULL,   # all fields present BUT record is a stub
    equipment_type          = "compact_track_loader",
    dealer_contact          = DEALER_CONTACT,
    dealer_info             = DEALER_INFO,
    full_record             = {"coverage_stub": True},
    photo_path              = None,
)
_check("A6.CTL.coverage_stub_limited",
       ctl_stub_data.get("ctl_spec_sheet_confidence") == "limited",
       "coverage_stub=True -> limited regardless of spec values")
_check("A6.CTL.coverage_stub_oem_false",
       ctl_stub_data.get("oem_verified") is False)

# ─── A4: Mini Excavator ───────────────────────────────────────────────────────
print("\n  [A4] Mini Excavator — Bobcat E26")
di_mini = DealerInput(
    year=2022, make="Bobcat", model="E26",
    hours=1200, cab_type="enclosed", ac=True, heater=True,
    two_speed_travel="yes", coupler_type="pin-on",
    thumb_type="hydraulic", blade_type="straight",
    condition_grade="Good", track_percent_remaining=80,
    asking_price=34500, serial_number="MINI123456", stock_number="STK-MINI-01",
)
mini_data = build_spec_sheet_data(
    dealer_input_data       = di_mini.model_dump(),
    enriched_resolved_specs = MINI_EX_SPECS,
    equipment_type          = "mini_excavator",
    dealer_contact          = DEALER_CONTACT,
    dealer_info             = DEALER_INFO,
    full_record             = {},
    photo_path              = None,
)
mini_hero_labels = [t["label"] for t in mini_data["specs"]["hero"]]
mini_core_labels = [r["label"] for r in mini_data["specs"]["core"]]
mini_perf_labels = [r["label"] for r in mini_data["specs"]["performance"]]

print(f"     Hero : {mini_hero_labels}")
print(f"     Core : {mini_core_labels}")
print(f"     Perf : {mini_perf_labels}")
print(f"     track_label : {mini_data['listing']['track_label']}")

_check("MiniEx.hero.weight",      "Operating Weight" in mini_hero_labels)
_check("MiniEx.hero.dig_depth",   "Max Dig Depth"    in mini_hero_labels)
_check("MiniEx.core.no_weight",   "Operating Weight" not in mini_core_labels, "removed from core")
_check("MiniEx.core.no_dig_depth","Max Dig Depth"    not in mini_core_labels, "removed from core")
_check("MiniEx.core.hours",       "Hours"    in mini_core_labels)
_check("MiniEx.core.hp",          "Horsepower" in mini_core_labels)
_check("MiniEx.core.serial",      "Serial #"  in mini_core_labels)
_check("MiniEx.no_roc",
       "Rated Op Capacity" not in mini_hero_labels
       and "Rated Op Capacity" not in mini_core_labels,
       "ROC absent from both hero and core")
_check("MiniEx.no_aux_flow",
       not any("Aux Flow" in l or "Aux Hydraulic" in l
               for l in mini_hero_labels + mini_core_labels),
       "Aux Flow absent")
_check("MiniEx.no_tipping_load",
       "Tipping Load" not in mini_perf_labels,
       "Tipping Load absent from performance")
_check("MiniEx.track_label",
       mini_data["listing"]["track_label"] == "Track % Remaining")


# =============================================================================
# SECTION B — Full pipeline checks (PNG render + ZIP)
# =============================================================================

_section("SECTION B — Full pipeline (Playwright PNG + ZIP)")

def _run_full_pipeline(
    make: str, model: str, year: int, hours: int,
    eq_type: str, di_kwargs: dict, label: str,
) -> tuple[dict, DealerInput, str]:
    """Run build_listing_pack_v1 and return (result, dealer_input, pack_dir)."""
    raw = f"{year} {make} {model}\n{hours:,} hours\n$49,900"
    parsed = safe_parse_listing(raw)
    specs, conf = safe_lookup_machine(parsed)
    session_dir, session_web = _make_session_dir(parsed)
    resolved = None
    resolved_specs: dict = {}
    if specs:
        resolved = _run_spec_resolver(raw, parsed, specs, conf)
        resolved_specs = (resolved or {}).get("resolved_specs") or {}
    di = DealerInput(year=year, make=make, model=model, hours=hours, **di_kwargs)
    result = build_listing_pack_v1(
        dealer_input       = di,
        resolved_specs     = resolved_specs,
        resolved_machine   = resolved,
        image_input_paths  = [],
        dealer_info        = DEALER_INFO,
        session_dir        = session_dir,
        session_web        = session_web,
        equipment_type     = eq_type,
        full_record        = specs,
    )
    print(f"     Registry hit : {specs is not None} (conf={conf:.2f})")
    print(f"     success      : {result.get('success')}")
    print(f"     warnings     : {result.get('warnings', [])}")
    return result, di, result.get("output_folder") or ""


def _check_pipeline_outputs(result: dict, pack_dir: str, machine_name: str, label: str) -> None:
    """Standard file + ZIP checks for a completed pipeline run."""
    lp_dir = Path(pack_dir) / "Listing_Photos"
    spec_sheet_files = sorted(lp_dir.glob("*_02_spec_sheet.png")) if lp_dir.exists() else []

    png_ok = bool(spec_sheet_files and spec_sheet_files[0].stat().st_size > 10_000)
    _check(f"{label}.png_renders",
           png_ok,
           f"{spec_sheet_files[0].name} ({spec_sheet_files[0].stat().st_size//1024}KB)"
           if spec_sheet_files else "FILE MISSING")

    if spec_sheet_files:
        png_path = str(spec_sheet_files[0])
        _check(f"{label}.png_in_Listing_Photos",
               "Listing_Photos" in png_path and "_02_spec_sheet.png" in png_path,
               png_path)

    # ZIP checks
    zip_path = result.get("zip_path")
    if zip_path and os.path.isfile(zip_path):
        with zipfile.ZipFile(zip_path) as zf:
            names = [i.filename for i in zf.infolist()]

        ss_in_zip  = [n for n in names if "_02_spec_sheet.png" in n and "Listing_Photos" in n]
        brochure   = [n for n in names if "brochure" in n.lower()]
        debug_html = [n for n in names if n.endswith(".debug.html")]
        root_ss    = [n for n in names
                      if "_spec_sheet" in n.lower() and "/" not in n.replace("\\","")]

        _check(f"{label}.zip_has_spec_sheet",
               bool(ss_in_zip), f"found: {ss_in_zip}")
        _check(f"{label}.zip_no_brochure",
               not brochure, f"excluded: {brochure or 'none'}")
        _check(f"{label}.zip_no_debug_html",
               not debug_html, f"excluded: {debug_html or 'none'}")
        _check(f"{label}.zip_no_root_spec_sheet",
               not root_ss, f"excluded: {root_ss or 'none'}")

        print(f"\n     ZIP contents ({zip_path}):")
        for n in sorted(names):
            print(f"       {n}")
    else:
        _fail(f"{label}.zip_created", f"zip_path={zip_path}")

    # Spurious machine_brochure.png — plant a fake one then re-zip to test exclusion
    # (only if we need to verify exclusion logic directly; skip if already clean)


# ── B1: CTL full pipeline ─────────────────────────────────────────────────────
print("\n  [B1] CTL full pipeline — Bobcat T770")
try:
    b1_result, b1_di, b1_pack = _run_full_pipeline(
        make="Bobcat", model="T770", year=2021, hours=1840,
        eq_type="compact_track_loader",
        di_kwargs=dict(
            cab_type="enclosed", ac=True, heater=True,
            high_flow="yes", two_speed_travel="yes", coupler_type="hydraulic",
            condition_grade="Excellent", track_percent_remaining=85,
            asking_price=72500, serial_number="B3S612345", stock_number="STK-1042",
        ),
        label="B1-CTL",
    )
    _check_pipeline_outputs(b1_result, b1_pack, "Bobcat_T770", "B1-CTL")
    # Verify track label from adapter (quick)
    b1_lp = Path(b1_pack) / "Listing_Photos"
    b1_ss_files = sorted(b1_lp.glob("*_02_spec_sheet.png")) if b1_lp.exists() else []
    print(f"     Spec sheet PNG: {b1_ss_files[0] if b1_ss_files else 'MISSING'}")
except Exception as exc:
    import traceback
    _fail("B1-CTL.pipeline", str(exc))
    traceback.print_exc()

# ── B2: SSL full pipeline (skid_steer) ────────────────────────────────────────
print("\n  [B2] SSL full pipeline — Bobcat S590 (skid_steer)")
try:
    b2_result, b2_di, b2_pack = _run_full_pipeline(
        make="Bobcat", model="S590", year=2020, hours=2100,
        eq_type="skid_steer",
        di_kwargs=dict(
            cab_type="enclosed", ac=True, heater=True,
            high_flow="yes", two_speed_travel="yes", coupler_type="hydraulic",
            control_type="hand_foot",
            condition_grade="Good", track_percent_remaining=70,
            asking_price=39500, serial_number="SSL123456", stock_number="STK-SSL-01",
        ),
        label="B2-SSL",
    )
    _check_pipeline_outputs(b2_result, b2_pack, "Bobcat_S590", "B2-SSL")
    b2_lp = Path(b2_pack) / "Listing_Photos"
    b2_ss_files = sorted(b2_lp.glob("*_02_spec_sheet.png")) if b2_lp.exists() else []
    print(f"     Spec sheet PNG: {b2_ss_files[0] if b2_ss_files else 'MISSING'}")
except Exception as exc:
    import traceback
    _fail("B2-SSL.pipeline", str(exc))
    traceback.print_exc()

# ── B3: SSL (skid_steer_loader) normalization — adapter path ──────────────────
print("\n  [B3] SSL normalization path check — skid_steer_loader via adapter")
# Confirms the normalized category string reaches the renderer correctly
_check("B3.category_display",
       ssl_loader_data["machine"]["category"] == "Skid Steer Loader",
       f"got '{ssl_loader_data['machine']['category']}'")
_check("B3.tire_label",
       ssl_loader_data["listing"]["track_label"] == "Tire % Remaining")
_check("B3.no_ctl_perf_branch",
       "High Flow Output" not in [r["label"] for r in ssl_loader_data["specs"]["performance"]],
       "CTL performance branch not entered")
_check("B3.ssl_perf_present",
       any("Hinge Pin" in r["label"] for r in ssl_loader_data["specs"]["performance"])
       or any("Tipping" in r["label"] for r in ssl_loader_data["specs"]["performance"]),
       "SSL performance rows rendered")

# ── B4: Mini Ex full pipeline ─────────────────────────────────────────────────
print("\n  [B4] Mini Ex full pipeline — Bobcat E26")
try:
    b4_result, b4_di, b4_pack = _run_full_pipeline(
        make="Bobcat", model="E26", year=2022, hours=1200,
        eq_type="mini_excavator",
        di_kwargs=dict(
            cab_type="enclosed", ac=True, heater=True,
            two_speed_travel="yes", coupler_type="pin-on",
            thumb_type="hydraulic", blade_type="straight",
            condition_grade="Good", track_percent_remaining=80,
            asking_price=34500, serial_number="MINI123456", stock_number="STK-MINI-01",
        ),
        label="B4-MiniEx",
    )
    _check_pipeline_outputs(b4_result, b4_pack, "Bobcat_E26", "B4-MiniEx")
    b4_lp = Path(b4_pack) / "Listing_Photos"
    b4_ss_files = sorted(b4_lp.glob("*_02_spec_sheet.png")) if b4_lp.exists() else []
    print(f"     Spec sheet PNG: {b4_ss_files[0] if b4_ss_files else 'MISSING'}")
except Exception as exc:
    import traceback
    _fail("B4-MiniEx.pipeline", str(exc))
    traceback.print_exc()


# =============================================================================
# SECTION C — Sparseness report
# =============================================================================

_section("SECTION C — Core sparseness report after hero dedup")

print()
print("  CTL core after patch:")
for r in ctl_data["specs"]["core"]:
    print(f"    {r['label']:<22} {r['value']} {r.get('unit','')}")
print(f"  --> {len(ctl_data['specs']['core'])} rows (down from 7; hero carries ROC/HP/AuxFlow/Weight)")

print()
print("  SSL core after patch:")
for r in ssl_data["specs"]["core"]:
    print(f"    {r['label']:<22} {r['value']} {r.get('unit','')}")
print(f"  --> {len(ssl_data['specs']['core'])} rows (down from 7; hero carries same 4 fields)")

print()
print("  Mini Ex core after patch:")
for r in mini_data["specs"]["core"]:
    print(f"    {r['label']:<22} {r['value']} {r.get('unit','')}")
print(f"  --> {len(mini_data['specs']['core'])} rows (down from 7; hero carries Weight+DigDepth)")

# CTL/SSL sparseness judgement
ctl_sparse = len(ctl_data["specs"]["core"]) <= 2
ssl_sparse = len(ssl_data["specs"]["core"]) <= 2
print()
if ctl_sparse:
    print("  SPARSENESS FLAG: CTL core has only Hours + Serial/Stock — renderer may show empty OEM section.")
if ssl_sparse:
    print("  SPARSENESS FLAG: SSL core has only Hours + Serial/Stock — renderer may show empty OEM section.")
if not ctl_sparse and not ssl_sparse:
    print("  Core density: OK for both CTL and SSL.")


# =============================================================================
# FINAL SUMMARY
# =============================================================================

_section("FINAL SUMMARY")
passed = sum(1 for v in _results.values() if v == "PASS")
failed = sum(1 for v in _results.values() if v == "FAIL")
total  = len(_results)
print(f"\n  {passed}/{total} checks passed")
if _errors:
    print(f"\n  FAILED checks ({len(_errors)}):")
    for e in _errors:
        print(f"    - {e}")
else:
    print("\n  ALL CHECKS PASSED")
print()
