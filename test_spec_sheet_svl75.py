"""
Test: Kubota SVL75-2 spec sheet render — verifies no Track % row when track_percent_remaining is None.

Run:
    python test_spec_sheet_svl75.py
"""

import os
import sys
from pathlib import Path

from mtm_service import (
    safe_parse_listing,
    safe_lookup_machine,
    _run_spec_resolver,
    _make_session_dir,
)
from listing_pack_builder import build_listing_pack_v1
from dealer_input import DealerInput

RAW_LISTING = """
2020 Kubota SVL75-2
2,100 hours
Enclosed cab, heat and AC
High flow
2-speed
Quick attach
$58,900
Located in Des Moines, IA
""".strip()

DEALER_INFO = {
    "dealer_name":  "Heartland Equipment Co.",
    "phone":        "(515) 555-0199",
    "email":        "info@heartlandequip.com",
    "location":     "Des Moines, IA",
    "website":      "heartlandequip.com",
    "accent_color": "orange",
}

print("\n" + "=" * 64)
print("  MTM Spec Sheet Test — Kubota SVL75-2")
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

dealer_input = DealerInput(
    year=2020,
    make="Kubota",
    model="SVL75-2",
    hours=2100,
    cab_type="enclosed",
    ac=True,
    heater=True,
    high_flow="yes",
    two_speed_travel="yes",
    coupler_type="hydraulic",
    condition_grade="Good",
    # track_percent_remaining intentionally omitted — Track % row must NOT appear
    asking_price=58900,
)
print(f"\n  [4] DealerInput: {dealer_input.make} {dealer_input.model} — track_percent_remaining={dealer_input.track_percent_remaining}")

result = build_listing_pack_v1(
    dealer_input       = dealer_input,
    resolved_specs     = (resolved or {}).get("resolved_specs") or {},
    resolved_machine   = resolved,
    image_input_paths  = [],
    dealer_info        = DEALER_INFO,
    session_dir        = session_dir,
    session_web        = session_web,
    full_record        = specs,
)

print("\n" + "=" * 64)
print("  Verification")
print("=" * 64)

pack_dir = result.get("output_folder") or ""
print(f"  success        : {result.get('success')}")

photos_dir_path = Path(pack_dir) / "Listing_Photos" if pack_dir else None
ss_png = None
if photos_dir_path and photos_dir_path.exists():
    ss_files = sorted(photos_dir_path.glob("*_02_spec_sheet.png"))
    if ss_files:
        ss_png = str(ss_files[0])

if ss_png and os.path.isfile(ss_png):
    print(f"\n  Spec sheet PNG : FOUND — {os.path.basename(ss_png)}")
else:
    print(f"\n  Spec sheet PNG : MISSING")
    sys.exit(1)

from spec_sheet_renderer_adapter import build_spec_sheet_data
import copy
_rs = (resolved or {}).get("resolved_specs") or {}
_rs2 = copy.copy(_rs)
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
    photo_path   = None,
)

track_pct = ss_data["listing"].get("track_pct")
print(f"\n  track_pct field : {repr(track_pct)}")
if track_pct is None:
    print("  CORRECT — Track % row will be suppressed (track_percent_remaining=None)")
else:
    print(f"  WARNING — Expected None, got {track_pct!r}")

print(f"\n  HERO TILES:")
for t in ss_data["specs"]["hero"]:
    print(f"    {t.get('label'):<22} {t.get('value')} {t.get('unit','')}")

print(f"\n  CONDITION & SERVICE fields:")
lst = ss_data["listing"]
print(f"    condition : {lst.get('condition')}")
print(f"    track_pct : {lst.get('track_pct')}")
print(f"    notes     : {lst.get('notes')}")

print(f"\n  Done.\n")
