"""
DEMO mode — temporary scaffolding for renderer iteration.
Bypasses the wizard; renders sample listings from hardcoded preset data.

REMOVAL:
  1. Delete demo_route.py
  2. Delete templates/demo.html
  3. Remove from app.py: the entire 3-line block ending with app.include_router(demo_router)
"""

from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dealer_input import DealerInput
from listing_pack_builder import build_listing_pack_v1
from mtm_service import (
    _make_session_dir,
    _run_spec_resolver,
    safe_lookup_machine,
    web_match_fallback,
)

_BASE = os.path.dirname(os.path.abspath(__file__))
_OUTPUTS_DIR = os.path.join(_BASE, "outputs")
_templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))

DEMO_IMAGE_PATH = os.path.join(_BASE, "static", "demo", "demo1.jpg")

router = APIRouter()

# ── Demo presets ──────────────────────────────────────────────────────────────
# Keys use human-friendly names; _preset_to_dealer_input() maps to DealerInput.
# Add t66_basic, e35_mini_ex, etc. here when ready.

DEMO_PRESETS: dict[str, dict] = {
    "t770_premium": {
        "year": 2019,
        "manufacturer": "Bobcat",
        "model": "T770",
        "serial_number": "DEMO-12345",
        "hours": 1850,
        "price": 42900,
        "location": "Boston, MA",

        "high_flow": True,
        "two_speed": True,
        "cab_type": "Enclosed",
        "ac": True,
        "heat": True,
        "condition": "Excellent",
        "owner_history": "One owner",
        "track_condition_pct": 75,
        "tracks_condition_label": "75% remaining",

        "attachments": [
            '72" bucket',
            "pallet forks",
        ],

        "features": [
            "Air ride seat",
            "Backup camera",
            "Radio",
        ],

        "additional_notes": (
            "Clean machine, well maintained, ready to work. "
            "No issues. Financing available."
        ),
    },
    # Future: "t66_basic": {...}, "e35_mini_ex": {...}
}

_DEFAULT_PRESET = "t770_premium"

# Human-readable feature label → DealerInput boolean field name
_FEATURE_NAME_MAP: dict[str, str] = {
    "air ride seat":  "air_ride_seat",
    "backup camera":  "backup_camera",
    "radio":          "radio",
    "ride control":   "ride_control",
    "self-leveling":  "self_leveling",
    "reversing fan":  "reversing_fan",
    "one owner":      "one_owner",
}


def _preset_to_dealer_input(preset: dict) -> DealerInput:
    """Map a DEMO_PRESETS entry to a valid DealerInput using production field names."""

    def _tristatus(v) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, bool):
            return "yes" if v else "no"
        return str(v)

    # Parse feature list → individual boolean kwargs
    feature_kwargs: dict = {}
    for feat_label in preset.get("features") or []:
        field = _FEATURE_NAME_MAP.get(feat_label.lower())
        if field:
            feature_kwargs[field] = True

    # Attachment list → free-text string
    attachments_str: Optional[str] = None
    if preset.get("attachments"):
        attachments_str = ", ".join(preset["attachments"])

    # owner_history → one_owner bool (if not already set via features list)
    if "one_owner" not in feature_kwargs:
        oh = (preset.get("owner_history") or "").lower()
        if "one owner" in oh or "1 owner" in oh:
            feature_kwargs["one_owner"] = True

    return DealerInput(
        year=preset["year"],
        make=preset.get("manufacturer") or preset.get("make", ""),
        model=preset["model"],
        hours=preset["hours"],
        asking_price=preset.get("price"),
        cab_type=(preset.get("cab_type") or "").lower() or None,
        heater=preset.get("heat"),
        ac=preset.get("ac"),
        high_flow=_tristatus(preset.get("high_flow")),
        two_speed_travel=_tristatus(preset.get("two_speed")),
        serial_number=preset.get("serial_number"),
        track_condition=(
            preset.get("tracks_condition_label")
            or (
                f"{preset['track_condition_pct']}% remaining"
                if preset.get("track_condition_pct")
                else None
            )
        ),
        condition_grade=preset.get("condition"),
        attachments_included=attachments_str,
        additional_details=preset.get("additional_notes"),
        **feature_kwargs,
    )


@router.get("/demo", response_class=HTMLResponse)
async def demo_preview(request: Request, preset: str = _DEFAULT_PRESET):
    """
    DEMO route — renders a hardcoded preset through the production pipeline.

    GET /demo               → default preset (t770_premium)
    GET /demo?preset=<name> → named preset
    GET /demo?preset=<bad>  → 404 with valid preset names
    """
    if preset not in DEMO_PRESETS:
        valid = sorted(DEMO_PRESETS.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown preset '{preset}'. Valid presets: {valid}",
        )

    p = DEMO_PRESETS[preset]
    dealer_input = _preset_to_dealer_input(p)

    parsed = {
        "make": dealer_input.make,
        "model": dealer_input.model,
        "make_source": "explicit",
    }

    specs, confidence = safe_lookup_machine(parsed)
    full_record: dict | None = specs.get("full_record") if specs else None

    resolved_machine: dict | None = None
    resolved_specs: dict = {}

    if specs is not None:
        eq_type = (specs.get("equipment_type") or "").lower()
        # SSL/CTL: suppress high_flow/two_speed from resolver;
        # unit-confirmed values are injected from DealerInput at the output layer.
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
            parsed_year=dealer_input.year,
            detected_modifiers=modifiers,
        )
        if resolved_machine:
            resolved_specs = resolved_machine.get("resolved_specs") or {}
    else:
        resolved_machine = web_match_fallback(
            dealer_input.make, dealer_input.model, dealer_input.year
        )

    session_dir, session_web = _make_session_dir(parsed)
    dealer_info = {"location": p.get("location")}

    try:
        _demo_images = [DEMO_IMAGE_PATH] if os.path.isfile(DEMO_IMAGE_PATH) else []
        pack = build_listing_pack_v1(
            dealer_input=dealer_input,
            resolved_specs=resolved_specs,
            resolved_machine=resolved_machine,
            image_input_paths=_demo_images,
            dealer_info=dealer_info,
            session_dir=session_dir,
            session_web=session_web,
            full_record=full_record,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pack generation error: {exc}")

    session_id = os.path.basename(session_dir)
    pack_dir = os.path.join(session_dir, "listing_output")
    web_base = f"/outputs/{session_id}/listing_output"

    # Listing text
    listing_text = ""
    lt_path = os.path.join(pack_dir, "listing_description.txt")
    if os.path.isfile(lt_path):
        with open(lt_path, encoding="utf-8") as f:
            listing_text = f.read()

    # Spec sheet PNG URL
    ss_path = os.path.join(pack_dir, "spec_sheet", "machine_spec_sheet.png")
    spec_sheet_url = (
        f"{web_base}/spec_sheet/machine_spec_sheet.png"
        if os.path.isfile(ss_path)
        else None
    )

    # ZIP download URL
    zip_abs = os.path.join(session_dir, "listing_output.zip")
    zip_url = f"/download-pack/{session_id}" if os.path.isfile(zip_abs) else None

    # Listing photo URLs — JPEGs first (processed input photos), then PNGs (cards)
    import glob as _glob
    _lp_dir = os.path.join(pack_dir, "Listing_Photos")
    listing_photos: list[str] = []
    if os.path.isdir(_lp_dir):
        _all = [
            _p for _p in sorted(_glob.glob(os.path.join(_lp_dir, "*")))
            if os.path.isfile(_p) and _p.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        ]
        _jpgs = [_p for _p in _all if _p.lower().endswith((".jpg", ".jpeg", ".webp"))]
        _pngs = [_p for _p in _all if _p.lower().endswith(".png")]
        for _p in (_jpgs or _pngs) + (_pngs if _jpgs else []):
            listing_photos.append(f"{web_base}/Listing_Photos/{os.path.basename(_p)}")

    machine_label = (
        f"{dealer_input.year} {dealer_input.make.upper()} {dealer_input.model}"
    )

    return _templates.TemplateResponse(
        "demo.html",
        {
            "request": request,
            "preset_name": preset,
            "preset_data_json": json.dumps(p, indent=2),
            "machine_label": machine_label,
            "listing_text": listing_text,
            "spec_sheet_url": spec_sheet_url,
            "listing_photos": listing_photos,
            "zip_url": zip_url,
            "result_url": f"/build-listing/result/{session_id}",
            "spec_sheet_view_url": f"/build-listing/spec-sheet/{session_id}",
            "valid_presets": sorted(DEMO_PRESETS.keys()),
        },
    )
