"""
Test: Bobcat T770 spec sheet render (locked field architecture).
Verifies output path, ZIP exclusion of debug HTML, and section fields.

Run:
    python test_spec_sheet_t770.py
"""

import json
import os
import sys
import zipfile
from pathlib import Path

from mtm_service import (
    safe_parse_listing,
    safe_lookup_machine,
    _run_spec_resolver,
    _stub_build_listing_data,
    _stub_generate_listing_text,
    _make_session_dir,
    build_spec_sheet_entries,
)
from listing_pack_builder import build_listing_pack_v1
from dealer_input import DealerInput

RAW_LISTING = """
2021 Bobcat T770
1,840 hours
Enclosed cab, heat and AC
2-speed high flow
74" construction bucket, tooth bar forks
Like new condition. Just serviced.
$72,500 OBO
Located in Sioux Falls, SD
Call 605-555-0142
""".strip()

DEALER_INFO = {
    "dealer_name":  "Summit Equipment Sales",
    "phone":        "(605) 555-0142",
    "email":        "sales@summitequip.com",
    "location":     "Sioux Falls, SD",
    "website":      "summitequip.com",
    "accent_color": "yellow",
}

# ── Parse ──────────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
print("  MTM Spec Sheet Test — Bobcat T770")
print("=" * 64)

parsed = safe_parse_listing(RAW_LISTING)
print(f"\n  [1] Parsed equipment_type: {parsed.get('equipment_type')}")

specs, confidence = safe_lookup_machine(parsed)
print(f"  [2] Registry: {'HIT' if specs else 'MISS'} (conf={confidence:.2f})")

session_dir, session_web = _make_session_dir(parsed)

resolved = None
if specs:
    resolved = _run_spec_resolver(RAW_LISTING, parsed, specs, confidence)
    if resolved:
        rs = resolved.get("resolved_specs") or {}
        print(f"  [3] Resolved specs ({len(rs)} fields)")
        # Print key fields for verification
        for k in ("roc_lb", "rated_operating_capacity_lbs", "net_hp", "horsepower_hp",
                  "aux_flow_standard_gpm", "aux_flow_high_gpm", "operating_weight_lbs",
                  "lift_path", "tipping_load_lbs"):
            v = rs.get(k)
            if v is not None:
                print(f"       {k:<35} {v}")

# ── Build DealerInput ─────────────────────────────────────────────────────────
dealer_input = DealerInput(
    year=2021,
    make="Bobcat",
    model="T770",
    hours=1840,
    cab_type="enclosed",
    ac=True,
    heater=True,
    high_flow="yes",
    two_speed_travel="yes",
    coupler_type="hydraulic",
    condition_grade="Excellent",
    track_condition="80%",
    track_percent_remaining=85,
    condition_notes="Like new condition. Just serviced. All maintenance up to date.",
    asking_price=72500,
    serial_number="B3S612345",
    stock_number="STK-1042",
)
print(f"\n  [4] DealerInput: {dealer_input.make} {dealer_input.model} {dealer_input.year}")

# ── Use demo photos (if available) ───────────────────────────────────────────
PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "inputs", "demo_images")
photo_paths = []
if os.path.isdir(PHOTOS_DIR):
    photo_paths = sorted([
        str(p) for p in Path(PHOTOS_DIR).iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ])[:6]
print(f"  [5] Photos: {len(photo_paths)} found")

# ── Build pack via v1 pipeline ────────────────────────────────────────────────
print(f"\n  [6] Building listing pack (v1 pipeline)...")
# Do NOT pass equipment_type — let it resolve from resolved_machine (registry value)
result = build_listing_pack_v1(
    dealer_input       = dealer_input,
    resolved_specs     = (resolved or {}).get("resolved_specs") or {},
    resolved_machine   = resolved,
    image_input_paths  = photo_paths,
    dealer_info        = DEALER_INFO,
    session_dir        = session_dir,
    session_web        = session_web,
    full_record        = specs,
)

# ── Verification ──────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
print("  Verification")
print("=" * 64)

pack_dir = result.get("output_folder") or ""
print(f"  success        : {result.get('success')}")
print(f"  machine_match  : {result.get('machine_match')}")

# Check spec sheet PNG path
ss_png = result.get("outputs", {}).get("spec_sheet_png")
photos_dir_path = Path(pack_dir) / "Listing_Photos" if pack_dir else None

# Also scan folder
if photos_dir_path and photos_dir_path.exists():
    ss_files = sorted(photos_dir_path.glob("*_02_spec_sheet.png"))
    if ss_files:
        ss_png = str(ss_files[0])

print(f"\n  Spec sheet PNG :")
if ss_png and os.path.isfile(ss_png):
    sz = os.path.getsize(ss_png) / 1024
    print(f"    FOUND: {ss_png}")
    print(f"    Size : {sz:.0f} KB")
    expected_name = "Bobcat_T770_02_spec_sheet.png"
    if os.path.basename(ss_png) == expected_name:
        print(f"    Name : CORRECT ({expected_name})")
    else:
        print(f"    Name : WARNING — expected {expected_name}, got {os.path.basename(ss_png)}")
else:
    print(f"    MISSING — {ss_png}")
    sys.exit(1)

# Confirm spec sheet data fields
print(f"\n  Adapter data fields:")
from spec_sheet_renderer_adapter import build_spec_sheet_data
_rs = (resolved or {}).get("resolved_specs") or {}
# Merge DealerInput serial/track into resolved specs (as listing_pack_builder does)
import copy
_rs2 = copy.copy(_rs)
if dealer_input.serial_number:
    _rs2["serial_number"] = dealer_input.serial_number
if dealer_input.track_condition:
    _rs2["track_condition"] = dealer_input.track_condition

# Use registry's equipment_type (compact_track_loader), not parser short code
_registry_eq = (resolved or {}).get("equipment_type") or "compact_track_loader"
ss_data = build_spec_sheet_data(
    dealer_input_data       = dealer_input.model_dump(),
    enriched_resolved_specs = _rs2,
    equipment_type          = _registry_eq,
    dealer_contact          = {
        "dealer_name": DEALER_INFO["dealer_name"],
        "phone":       DEALER_INFO["phone"],
        "location":    DEALER_INFO["location"],
    },
    dealer_info  = DEALER_INFO,
    full_record  = specs,
    photo_path   = photo_paths[0] if photo_paths else None,
)

print(f"\n  HERO TILES:")
for t in ss_data["specs"]["hero"]:
    print(f"    {t.get('label'):<22} {t.get('value')} {t.get('unit',''):<5} icon={t.get('icon','')}")

print(f"\n  CORE SPECS:")
for r in ss_data["specs"]["core"]:
    print(f"    {r.get('label'):<22} {r.get('value')} {r.get('unit','')}")

print(f"\n  KEY FEATURES:")
for f in ss_data["features"]:
    print(f"    - {f}")

print(f"\n  CONDITION & SERVICE fields:")
lst = ss_data["listing"]
print(f"    hours          : {lst.get('hours')}")
print(f"    hours_qualifier: {lst.get('hours_qualifier')}")
print(f"    condition      : {lst.get('condition')}")
print(f"    track_pct      : {lst.get('track_pct')}")
print(f"    notes          : {lst.get('notes')}")

print(f"\n  PERFORMANCE DATA:")
for r in ss_data["specs"]["performance"]:
    print(f"    {r.get('label'):<22} {r.get('value')} {r.get('unit','')}")

# ZIP check
zip_path = result.get("zip_path")
print(f"\n  ZIP contents: {zip_path}")
if zip_path and os.path.isfile(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        names = [i.filename for i in zf.infolist()]
        debug_files = [n for n in names if n.endswith(".debug.html")]
        for info in sorted(zf.infolist(), key=lambda x: x.filename):
            print(f"    {info.filename:<52}  {info.file_size/1024:>5.0f} KB")
        if debug_files:
            print(f"\n  WARNING: debug HTML found in ZIP: {debug_files}")
        else:
            print(f"\n  ZIP: *.debug.html excluded — CORRECT")

if result.get("warnings"):
    print(f"\n  Warnings:")
    for w in result["warnings"]:
        print(f"    {w}")

print(f"\n  Done. Spec sheet: {ss_png}\n")
