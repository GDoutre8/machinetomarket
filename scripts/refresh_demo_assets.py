#!/usr/bin/env python3
"""scripts/refresh_demo_assets.py
===============================
Regenerates all homepage demo preview assets using real machine photos
and the production rendering pipeline.

Run from the project root:
    python scripts/refresh_demo_assets.py

Outputs written to:  static/demo_outputs/
  demo_price_tag_card.png  — Kubota SVL 97-2     (Marketplace Hero Card)
  demo_01_card.png         — Kubota SVL 97-2     (legacy alias)
  demo_spec_sheet.png      — 2024 Cat 299D3      (Dealer Spec Sheet)
  demo_02_spec_sheet.png   — 2024 Cat 299D3      (legacy alias)
  demo_image_pack.png      — 2023 SkyTrak 8042   (Branded Image Pack first photo)
  2020_Bobcat_E35_*.mp4    — 2020 Bobcat E35     (Walkaround Video, no UI slot)
"""

from __future__ import annotations

import glob
import os
import shutil
import sys

# ── Add project root to sys.path ─────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from dealer_input import DealerInput
from listing_pack_builder import build_listing_pack_v1
from mtm_service import _make_session_dir, _run_spec_resolver, safe_lookup_machine

DEMO_OUTPUTS = os.path.join(_ROOT, "static", "demo_outputs")
os.makedirs(DEMO_OUTPUTS, exist_ok=True)

# ── Demo dealer identity ──────────────────────────────────────────────────────
_LOGO_PNG = os.path.join(_ROOT, "static", "assets", "brand", "icon-square-dark-transparent.png")
_DEMO_DEALER_BASE = {
    "dealer_name":  "Iron Valley Equipment",
    "phone":        "(800) 555-0174",
    "location":     "Columbus, OH",
    "logo_path":    _LOGO_PNG if os.path.isfile(_LOGO_PNG) else None,
    "accent_color": "yellow",
}


def _sorted_photos(folder: str) -> list[str]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    files = []
    if not os.path.isdir(folder):
        print(f"  ERROR: folder not found: {folder}")
        return files
    for f in sorted(os.listdir(folder)):
        if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in exts:
            files.append(os.path.join(folder, f))
    return files


def _find_output(listing_dir: str, pattern: str) -> str | None:
    matches = sorted(glob.glob(os.path.join(listing_dir, pattern)))
    return matches[0] if matches else None


def _copy_to_demo(src: str | None, dest_name: str) -> str | None:
    if not src or not os.path.isfile(src):
        print(f"  SKIP  {dest_name}  (source not found: {src})")
        return None
    dest = os.path.join(DEMO_OUTPUTS, dest_name)
    shutil.copy2(src, dest)
    size_kb = os.path.getsize(dest) // 1024
    print(f"  OK    {dest_name}  ({size_kb} KB)")
    return dest


def run_pack(
    year: int,
    make: str,
    model: str,
    hours: int,
    price: int,
    photo_folder: str,
    accent_color: str = "yellow",
    extra_input: dict | None = None,
) -> dict:
    """Run one machine through the full production pipeline. Returns the pack result dict."""
    extra = extra_input or {}

    dealer_input = DealerInput(
        year=year,
        make=make,
        model=model,
        hours=hours,
        asking_price=price,
        condition_grade="Well Maintained",
        cab_type=extra.pop("cab_type", "enclosed"),
        ac=extra.pop("ac", True),
        heater=extra.pop("heater", True),
        **extra,
    )

    parsed = {"make": make, "model": model, "make_source": "explicit"}
    specs, confidence = safe_lookup_machine(parsed)
    full_record = specs.get("full_record") if specs else None

    resolved_machine = None
    resolved_specs: dict = {}

    if specs is not None:
        eq_type = (specs.get("equipment_type") or "").lower()
        is_ssl_or_ctl = eq_type in ("skid_steer", "compact_track_loader")
        modifiers: list[str] = []
        if not is_ssl_or_ctl:
            if dealer_input.high_flow == "yes":
                modifiers.append("high_flow")
            if dealer_input.two_speed_travel == "yes":
                modifiers.append("two_speed")

        resolved_machine = _run_spec_resolver(
            "",
            parsed,
            specs,
            confidence,
            parsed_year=year,
            detected_modifiers=modifiers,
        )
        if resolved_machine:
            resolved_specs = resolved_machine.get("resolved_specs") or {}
    else:
        print(f"  WARN: no registry match for {make} {model}")

    session_dir, session_web = _make_session_dir(parsed)
    dealer_info = dict(_DEMO_DEALER_BASE)
    dealer_info["accent_color"] = accent_color

    photos = _sorted_photos(photo_folder)[:10]
    print(f"  Photos: {[os.path.basename(p) for p in photos]}")

    pack = build_listing_pack_v1(
        dealer_input=dealer_input,
        resolved_specs=resolved_specs,
        resolved_machine=resolved_machine,
        image_input_paths=photos,
        dealer_info=dealer_info,
        session_dir=session_dir,
        session_web=session_web,
        full_record=full_record,
    )

    pack["_session_dir"] = session_dir
    return pack


# ─────────────────────────────────────────────────────────────────────────────
# 1. Marketplace Hero Card — Kubota SVL 97-2
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/4] Marketplace Hero Card — Kubota SVL 97-2")
kubota_pack = run_pack(
    year=2021, make="Kubota", model="SVL97-2", hours=1240, price=54900,
    photo_folder="C:/Users/Greg/OneDrive/Pictures/Kubota SVL 97-2",
    accent_color="yellow",
    extra_input={
        "high_flow": "yes",
        "two_speed_travel": "yes",
        "serial_number": "SVL97DEMO01",
        "track_condition": "85% remaining",
        "one_owner": True,
        "backup_camera": True,
    },
)
_listing_photos = os.path.join(kubota_pack["_session_dir"], "listing_output", "Listing_Photos")
_card = _find_output(_listing_photos, "*_01_card.png")
_copy_to_demo(_card, "demo_price_tag_card.png")
_copy_to_demo(_card, "demo_01_card.png")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dealer Spec Sheet — 2024 Caterpillar 299D3
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/4] Dealer Spec Sheet — 2024 Caterpillar 299D3")
cat_pack = run_pack(
    year=2024, make="Caterpillar", model="299D3", hours=320, price=119500,
    photo_folder="C:/Users/Greg/OneDrive/Pictures/2024 Caterpillar 299D3",
    accent_color="yellow",
    extra_input={
        "high_flow": "yes",
        "two_speed_travel": "yes",
        "serial_number": "299D3DEMO02",
        "track_condition": "95% remaining",
        "air_ride_seat": True,
        "backup_camera": True,
    },
)
_listing_photos = os.path.join(cat_pack["_session_dir"], "listing_output", "Listing_Photos")
_spec_sheet = _find_output(_listing_photos, "*_02_spec_sheet.png")
_copy_to_demo(_spec_sheet, "demo_spec_sheet.png")
_copy_to_demo(_spec_sheet, "demo_02_spec_sheet.png")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Branded Image Pack — 2023 SkyTrak 8042
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/4] Branded Image Pack — 2023 SkyTrak 8042")
skytrak_pack = run_pack(
    year=2023, make="SkyTrak", model="8042", hours=780, price=89000,
    photo_folder="C:/Users/Greg/OneDrive/Pictures/2023 SKYTRAK 8042",
    accent_color="yellow",
    extra_input={
        "serial_number": "8042DEMO03",
        "has_stabilizers": True,
    },
)
_listing_photos = os.path.join(skytrak_pack["_session_dir"], "listing_output", "Listing_Photos")
# First badged listing photo (03+)
_img_pack_photo = (
    _find_output(_listing_photos, "*_03_listing.jpg")
    or _find_output(_listing_photos, "*_03_listing.jpeg")
    or _find_output(_listing_photos, "*_listing.jpg")
    or _find_output(_listing_photos, "*_listing.jpeg")
)
# Fall back to the hero card if no listing photo was generated (photo count < 1)
if not _img_pack_photo:
    _img_pack_photo = _find_output(_listing_photos, "*_01_card.png")
_copy_to_demo(_img_pack_photo, "demo_image_pack.png")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Walkaround Video — 2020 Bobcat E35
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/4] Walkaround Video — 2020 Bobcat E35")
_e35_photos = _sorted_photos("C:/Users/Greg/OneDrive/Pictures/2020 Bobcat E35")[:10]
print(f"  Photos: {[os.path.basename(p) for p in _e35_photos]}")

try:
    from walkaround_generator import (
        check_ffmpeg_available,
        generate_walkaround_video,
        walkaround_filename,
    )
    check_ffmpeg_available()
    _wk_name = walkaround_filename(2020, "Bobcat", "E35")
    _wk_out = os.path.join(DEMO_OUTPUTS, _wk_name)
    generate_walkaround_video(
        photos=_e35_photos,
        output_path=_wk_out,
        year=2020,
        make="Bobcat",
        model="E35",
        dealer_name="Iron Valley Equipment",
        dealer_phone="(800) 555-0174",
        accent_color="yellow",
        dealer_logo_path=_LOGO_PNG if os.path.isfile(_LOGO_PNG) else None,
    )
    _wk_size_mb = os.path.getsize(_wk_out) / 1_000_000
    print(f"  OK    {_wk_name}  ({_wk_size_mb:.1f} MB)")
    print("  NOTE: Homepage has no walkaround tab — video saved to demo_outputs/ but not wired.")
except RuntimeError as exc:
    print(f"  SKIP  Walkaround: {exc}")
except Exception as exc:
    print(f"  ERROR Walkaround: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n─── static/demo_outputs/ ───────────────────────────────────────────────────")
for f in sorted(os.listdir(DEMO_OUTPUTS)):
    fp = os.path.join(DEMO_OUTPUTS, f)
    if os.path.isfile(fp):
        size_kb = os.path.getsize(fp) // 1024
        print(f"  {f:<50}  {size_kb:>7} KB")
print()
