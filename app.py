"""
app.py — Machine-to-Market: Fix My Listing
FastAPI entry point. All business logic lives in mtm_service.py.
"""

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager
import asyncio
import glob as _glob
import json
import os
import shutil
import time
import uuid

from mtm_service import (
    fix_listing_service,
    safe_parse_listing,
    safe_lookup_machine,
    web_match_fallback,
    _run_spec_resolver,
    _stub_build_listing_data,
    _stub_generate_listing_text,
    _make_session_dir,
    _asset_url,
    _build_scorer_input,
    build_spec_sheet_entries,
    build_confirm_required,
    build_rewritten_listing,
    build_tiered_specs,
)
from mtm_scorer import score as _score_listing, build_fix_my_listing
from listing_pack_builder import build_listing_pack, build_listing_pack_v1, _zip_folder
from listing_use_case_enrichment import build_use_case_payload
from listing_builder import build_listing_text, build_use_case_ui_items
from dealer_input import DealerInput
from fastapi.responses import JSONResponse
from spec_sheet_context import (
    build_spec_sheet_context as _build_spec_sheet_context_impl,
    _fmt_number,
    _EQ_TYPE_DISPLAY,
    _LIFT_PATH_DISPLAY,
    _CONTROL_DISPLAY,
    _logo_is_light,
)

# ── Session cleanup ───────────────────────────────────────────────────────────
_SESSION_MAX_AGE_SECS = 86400 * 7  # 7 days
_CLEANUP_INTERVAL_SECS = 3600  # run every hour


def _cleanup_old_sessions() -> int:
    """Delete output session directories older than _SESSION_MAX_AGE_SECS.
    Returns the number of directories removed."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
    if not os.path.isdir(base):
        return 0
    cutoff = time.time() - _SESSION_MAX_AGE_SECS
    removed = 0
    for entry in os.scandir(base):
        if entry.is_dir(follow_symlinks=False):
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry.path, ignore_errors=True)
                    removed += 1
            except Exception:
                pass
    return removed


async def _cleanup_loop() -> None:
    """Background task: clean up old sessions every hour."""
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL_SECS)
        try:
            removed = _cleanup_old_sessions()
            if removed:
                print(f"  [Cleanup] Removed {removed} expired session(s).")
        except Exception as exc:
            print(f"  [Cleanup] Error during session cleanup: {exc}")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # On startup: purge any sessions left over from a previous run, then
    # start the hourly background cleanup loop.
    removed = _cleanup_old_sessions()
    if removed:
        print(f"  [Startup] Cleaned up {removed} stale session(s) from previous run.")
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="Machine-to-Market: Fix My Listing", docs_url=None, redoc_url=None, lifespan=_lifespan)

# Use absolute paths so uvicorn always serves the correct files
# regardless of the working directory it is launched from
_BASE = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=os.path.join(_BASE, "static")), name="static")
app.mount("/images", StaticFiles(directory=os.path.join(_BASE, "public", "images")), name="images")

_OUTPUTS_DIR = os.path.join(_BASE, "outputs")
os.makedirs(_OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=_OUTPUTS_DIR), name="outputs")
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))


templates.env.filters["format_number"] = _fmt_number


def _build_spec_sheet_context(
    dealer_input_data: dict,
    resolved_specs: dict,
    ui_hints: dict,
    equipment_type: str,
    dealer_contact: dict,
    session_id: str,
) -> dict:
    """Assemble the full Jinja2 context dict for spec_sheet.html."""
    return _build_spec_sheet_context_impl(
        dealer_input_data=dealer_input_data,
        resolved_specs=resolved_specs,
        ui_hints=ui_hints,
        equipment_type=equipment_type,
        dealer_contact=dealer_contact,
        session_id=session_id,
        outputs_dir=_OUTPUTS_DIR,
        logo_as_data_uri=False,
    )


# ── Equipment-type feature config ─────────────────────────────────────────────
# Defines which feature checkboxes appear in Step 2 for each equipment type.
# Each entry: {"name": DealerInput field name, "label": display label}

_FEATURE_CONFIG: dict[str, list[dict]] = {
    "compact_track_loader": [
        # ── Primary machine features ──────────────────────────────────────────
        {"name": "cab_type",          "label": "Cab Type"},
        {"name": "heater",            "label": "Heat"},
        {"name": "ac",                "label": "A/C"},
        {"name": "high_flow",         "label": "High Flow"},
        {"name": "two_speed",         "label": "Two Speed"},
        {"name": "ride_control",      "label": "Ride Control"},
        {"name": "joystick_controls", "label": "Joystick Controls"},
        {"name": "backup_camera",     "label": "Backup Camera"},
        {"name": "air_ride_seat",     "label": "Air Ride Seat"},
        {"name": "self_leveling",     "label": "Self-Leveling"},
        {"name": "radio",             "label": "Radio"},
        {"name": "one_owner",         "label": "One Owner"},
        # ── Lower priority ────────────────────────────────────────────────────
        {"name": "reversing_fan",     "label": "Reversing Fan"},
    ],
    "skid_steer": [
        {"name": "cab_type",          "label": "Cab Type"},
        {"name": "heater",            "label": "Heat"},
        {"name": "ac",                "label": "A/C"},
        {"name": "high_flow",         "label": "High Flow"},
        {"name": "two_speed",         "label": "Two Speed"},
        {"name": "ride_control",      "label": "Ride Control"},
        {"name": "joystick_controls", "label": "Joystick Controls"},
        {"name": "backup_camera",     "label": "Backup Camera"},
        {"name": "radio",             "label": "Radio"},
        {"name": "one_owner",         "label": "One Owner"},
    ],
    "mini_excavator": [
        # ── Mini ex CORE OUTPUT (locked standard 2026-04-10) ─────────────────
        {"name": "cab_type",             "label": "Cab Type"},
        {"name": "heater",               "label": "Heater"},
        {"name": "ac",                   "label": "A/C"},
        {"name": "aux_hydraulics",       "label": "Aux Hydraulics"},
        {"name": "thumb",                "label": "Thumb"},
        {"name": "blade",                "label": "Blade"},
        # ── Mini ex FEATURES (secondary output) ──────────────────────────────
        {"name": "two_speed",            "label": "2-Speed Travel"},
        {"name": "pattern_changer",      "label": "Pattern Changer"},
        {"name": "rubber_tracks",        "label": "Rubber Tracks"},
        {"name": "zero_tail_swing",      "label": "Zero Tail Swing"},
        {"name": "backup_camera",        "label": "Backup Camera"},
        {"name": "one_owner",            "label": "One Owner"},
    ],
    "backhoe_loader": [
        {"name": "cab_type",          "label": "Cab Type"},
        {"name": "heater",            "label": "Heat"},
        {"name": "ac",                "label": "A/C"},
        {"name": "backup_camera",     "label": "Backup Camera"},
        {"name": "one_owner",         "label": "One Owner"},
    ],
    "wheel_loader": [
        {"name": "cab_type",          "label": "Cab Type"},
        {"name": "heater",            "label": "Heat"},
        {"name": "ac",                "label": "A/C"},
        {"name": "backup_camera",     "label": "Backup Camera"},
        {"name": "one_owner",         "label": "One Owner"},
    ],
    # ── Large excavator LOCKED standard 2026-04-10 ───────────────────────────
    # Boolean feature fields only:
    "excavator": [
        {"name": "ac",                "label": "A/C"},
        {"name": "heater",            "label": "Heater"},
        {"name": "rear_camera",       "label": "Rear Camera"},
        {"name": "hammer_plumbing",   "label": "Hammer Plumbing"},
        {"name": "pattern_changer",   "label": "Pattern Changer"},
        {"name": "heated_seat",       "label": "Heated Seat"},
        {"name": "air_ride_seat",     "label": "Air Ride Seat"},
        {"name": "radio",             "label": "Radio"},
    ],
    "_default": [
        {"name": "cab_type",          "label": "Cab Type"},
        {"name": "heater",            "label": "Heat"},
        {"name": "ac",                "label": "A/C"},
        {"name": "backup_camera",     "label": "Backup Camera"},
        {"name": "one_owner",         "label": "One Owner"},
    ],
}

_EQ_TYPE_LABELS: dict[str, str] = {
    "compact_track_loader": "Compact Track Loader",
    "skid_steer":           "Skid Steer",
    "mini_excavator":       "Mini Excavator",
    "backhoe_loader":       "Backhoe Loader",
    "wheel_loader":         "Wheel Loader",
    "dozer":                "Dozer",
    "scissor_lift":         "Scissor Lift",
    "boom_lift":            "Boom Lift",
    "excavator":            "Excavator",
    "telehandler":          "Telehandler",
}

# Condition % field label varies by equipment type
_CONDITION_PCT_LABEL: dict[str, str] = {
    "compact_track_loader": "Track Condition %",
    "mini_excavator":       "Track Condition %",
    "excavator":            "Track Condition %",
    "skid_steer":           "Tire Condition %",
    "wheel_loader":         "Tire Condition %",
    "backhoe_loader":       "Tire / Track Condition %",
}


# ── Spec preview fields for identify response ─────────────────────────────────
_IDENTIFY_SPEC_FIELDS: list[tuple[str, str, str]] = [
    ("net_hp",              "Engine",    "hp"),
    ("roc_lb",              "Op. Cap.",  "lbs"),
    ("operating_weight_lb", "Weight",    "lbs"),
    ("hydraulic_flow_gpm",  "Aux Flow",  "gpm"),
]


def _fmt_spec_pill_value(val: float | int, unit: str) -> str:
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    if isinstance(val, int) and val >= 1000:
        return f"{val:,} {unit}"
    return f"{val} {unit}"


def _structured_modifiers_from_flags(flags: dict) -> list[str]:
    modifier_map = {
        "high_flow": "high_flow",
        "two_speed": "two_speed",
        "thumb": "thumb",
        "extendahoe": "extendahoe",
    }
    result = []
    for field, modifier in modifier_map.items():
        val = flags.get(field)
        if val is None:
            continue
        # Status string fields (high_flow, two_speed): only "yes" means installed.
        # "optional" = OEM offers it but unit may not have it — do NOT pass as modifier.
        if field in ("high_flow", "two_speed"):
            if val == "yes":
                result.append(modifier)
        elif val:
            result.append(modifier)
    return sorted(result)


# ── Request / Response models ─────────────────────────────────────────────────

class FixListingRequest(BaseModel):
    raw_text:   str
    spec_level: str  = "essential"  # "essential" | "standard" | "technical"
    # Legacy values "quick" / "dealer" / "full" are accepted and remapped automatically.

    # ── Output toggles (all default True) ────────────────────────────────
    generate_spec_sheet:          bool = True
    generate_spec_sheet_variants: bool = True
    generate_listing_package:     bool = True


class FixListingResponse(BaseModel):
    cleaned_listing:            str
    parsed_machine:             dict | None = None
    spec_level:                 str  | None = None
    display_specs:              list | None = None   # pre-formatted [{key, label, value}]
    output_assets:              dict | None = None
    resolved_specs:             dict | None = None   # raw canonical values for debug / reuse
    requires_confirm:           list | None = None
    ui_hints:                   dict | None = None
    warnings:                   list | None = None
    overall_resolution_status:  str  | None = None
    safe_for_listing_injection: bool | None = None
    confidence_note:            str  | None = None
    scoring:                    dict | None = None   # spec_completeness, grade, strengths, top_fixes, …
    fix_my_listing:             dict | None = None   # dealer-facing: tier, next_tier, structured fixes
    confirm_required:           dict | None = None   # fields needing dealer verification before publish
    rewritten_listing:          dict | None = None   # title, description, spec_bullets, platform variants
    error:                      str  | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/build-listing", status_code=302)


@app.get("/fix-listing", response_class=HTMLResponse)
async def fix_listing_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/download-pack")
async def download_pack(path: str):
    """Serve a ZIP file for download given its absolute server path."""
    if not path or not os.path.isfile(path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
    # Security: only serve files inside the outputs directory
    abs_out = os.path.abspath(_OUTPUTS_DIR)
    abs_req = os.path.abspath(path)
    if not abs_req.startswith(abs_out):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(
        abs_req,
        media_type="application/zip",
        filename=os.path.basename(abs_req),
    )


def _apply_title_override(listing_text: str, title: str) -> str:
    """Replace the first line of listing_text with the given title."""
    rest = listing_text.split("\n", 1)
    return title + ("\n" + rest[1] if len(rest) > 1 else "")


@app.get("/build-listing/result/{session_id}", response_class=HTMLResponse)
async def build_listing_result(request: Request, session_id: str):
    """Preview page shown after pack generation."""
    # Validate session_id — only allow safe directory name characters
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if not all(c in safe_chars for c in session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")

    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    pack_dir = os.path.join(session_dir, "listing_output")
    web_base = f"/outputs/{session_id}/listing_output"

    # Load metadata
    metadata: dict = {}
    meta_path = os.path.join(pack_dir, "metadata_internal.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            pass

    # Load listing text
    listing_text: str = ""
    listing_txt_path = os.path.join(pack_dir, "listing_description.txt")
    if os.path.isfile(listing_txt_path):
        try:
            with open(listing_txt_path, encoding="utf-8") as f:
                listing_text = f.read()
        except Exception:
            pass

    # Listing title: saved override takes priority, otherwise first line of listing
    listing_title: str = listing_text.split("\n")[0] if listing_text else ""
    title_override_path = os.path.join(session_dir, "title_override.json")
    if os.path.isfile(title_override_path):
        try:
            with open(title_override_path, encoding="utf-8") as f:
                saved_title = json.load(f).get("title", "")
            if saved_title:
                listing_title = saved_title
        except Exception:
            pass

    # Spec sheet web URL — prefer brochure (Panel 1+2), fall back to legacy spec sheet
    _brochure_abs   = os.path.join(pack_dir, "spec_sheet", "machine_brochure.png")
    _spec_sheet_abs = os.path.join(pack_dir, "spec_sheet", "machine_spec_sheet.png")
    if os.path.isfile(_brochure_abs):
        spec_sheet_abs = _brochure_abs
        spec_sheet_url = f"{web_base}/spec_sheet/machine_brochure.png"
    elif os.path.isfile(_spec_sheet_abs):
        spec_sheet_abs = _spec_sheet_abs
        spec_sheet_url = f"{web_base}/spec_sheet/machine_spec_sheet.png"
    else:
        spec_sheet_abs = _spec_sheet_abs
        spec_sheet_url = None

    def _load_image_urls(subfolder: str) -> list[str]:
        img_dir = os.path.join(pack_dir, subfolder)
        if not os.path.isdir(img_dir):
            return []
        found = sorted(
            p for p in _glob.glob(os.path.join(img_dir, "*"))
            if os.path.isfile(p) and p.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        )
        return [f"{web_base}/{subfolder}/{os.path.basename(p)}" for p in found]

    image_packs = [
        {
            "folder":   "Listing_Photos",
            "label":    "Listing Photos",
            "tag":      "Ready to Post",
            "hint":     "Branded listing images with your logo and contact info. Use these for Facebook Marketplace, Craigslist, dealer sites, and all listing platforms.",
            "urls":     _load_image_urls("Listing_Photos"),
        },
        {
            "folder":   "Original_Photos",
            "label":    "Original Photos",
            "tag":      "Full Size",
            "hint":     "Unmodified originals. Use these if you need to re-edit or upload to platforms with their own crop tool.",
            "urls":     _load_image_urls("Original_Photos"),
        },
    ]

    # Walkaround video
    walkaround_abs = os.path.join(pack_dir, "walkaround.mp4")
    walkaround_url = f"{web_base}/walkaround.mp4" if os.path.isfile(walkaround_abs) else None

    # ZIP download URL
    zip_abs = os.path.join(session_dir, "listing_output.zip")
    zip_url = f"/download-pack/{session_id}" if os.path.isfile(zip_abs) else None

    # Tiered spec sets for the live spec toggle (Core / Dealer / Full)
    spec_tiers: dict = {}
    _rs_path = os.path.join(session_dir, "resolved_specs.json")
    if os.path.isfile(_rs_path):
        try:
            with open(_rs_path, encoding="utf-8") as f:
                _rs = json.load(f)
            _ui: dict = {}
            _ui_path = os.path.join(session_dir, "ui_hints.json")
            if os.path.isfile(_ui_path):
                with open(_ui_path, encoding="utf-8") as f:
                    _ui = json.load(f)
            spec_tiers = build_tiered_specs(_rs, _ui, metadata.get("equipment_type") or "")
        except Exception:
            pass

    _meta_make = metadata.get("make") or ""
    machine_label = " ".join(
        str(x) for x in [metadata.get("year"), _meta_make.upper() if _meta_make else None, metadata.get("model")] if x
    ) or "Your Machine"

    can_refine = os.path.isfile(os.path.join(session_dir, "dealer_input.json"))

    # Derive Best For UI items (label + descriptor) for the result page card.
    # Requires saved dealer_input.json + resolved_specs.json; fails silently.
    best_for_ui: list[dict] = []
    _di_path  = os.path.join(session_dir, "dealer_input.json")
    _rs_path2 = os.path.join(session_dir, "resolved_specs.json")
    if os.path.isfile(_di_path) and os.path.isfile(_rs_path2):
        try:
            with open(_di_path, encoding="utf-8") as f:
                _di_data = json.load(f)
            with open(_rs_path2, encoding="utf-8") as f:
                _rs_data = json.load(f)
            _eq_type = metadata.get("equipment_type") or ""
            _di_obj  = DealerInput(**_di_data)
            _uc_pay  = build_use_case_payload(_eq_type, _di_obj, _rs_data)
            best_for_ui = build_use_case_ui_items(_uc_pay)
        except Exception:
            pass

    return templates.TemplateResponse("build_listing_result.html", {
        "request":        request,
        "session_id":     session_id,
        "machine_label":  machine_label,
        "metadata":       metadata,
        "listing_text":   listing_text,
        "listing_title":  listing_title,
        "spec_tiers":     spec_tiers,
        "spec_sheet_url": spec_sheet_url,
        "image_packs":    image_packs,
        "walkaround_url": walkaround_url,
        "zip_url":        zip_url,
        "can_refine":     can_refine,
        "best_for_ui":    best_for_ui,
    })


@app.post("/build-listing/result/{session_id}", response_class=HTMLResponse)
async def update_listing_text(
    request: Request,
    session_id: str,
    additional_features: str = Form(""),
    additional_details: str = Form(""),
    comparable_models: str = Form(""),
):
    """Regenerate listing.txt with dealer-added notes and redirect back to the result page."""
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if not all(c in safe_chars for c in session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")

    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    dealer_input_path  = os.path.join(session_dir, "dealer_input.json")
    resolved_specs_path = os.path.join(session_dir, "resolved_specs.json")
    if not os.path.isfile(dealer_input_path) or not os.path.isfile(resolved_specs_path):
        raise HTTPException(status_code=422, detail="Session data not available for refinement")

    with open(dealer_input_path, encoding="utf-8") as f:
        di_data = json.load(f)
    with open(resolved_specs_path, encoding="utf-8") as f:
        resolved_specs = json.load(f)

    # Pull equipment_type from stored metadata
    equipment_type = None
    meta_path = os.path.join(session_dir, "listing_output", "metadata_internal.json")
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            equipment_type = json.load(f).get("equipment_type")

    # Inject the new dealer inputs
    di_data["additional_features"] = additional_features.strip() or None
    di_data["additional_details"] = additional_details.strip() or None
    di_data["comparable_models"] = comparable_models.strip() or None
    dealer_input = DealerInput(**di_data)

    use_case_payload = build_use_case_payload(equipment_type, dealer_input, resolved_specs)
    new_listing_text = build_listing_text(
        dealer_input,
        resolved_specs,
        use_case_payload,
        equipment_type=equipment_type or "",
    )

    # Re-apply stored title override if present
    title_override_path = os.path.join(session_dir, "title_override.json")
    if os.path.isfile(title_override_path):
        try:
            with open(title_override_path, encoding="utf-8") as f:
                saved_title = json.load(f).get("title", "")
            if saved_title:
                new_listing_text = _apply_title_override(new_listing_text, saved_title)
        except Exception:
            pass

    listing_txt_path = os.path.join(session_dir, "listing_output", "listing_description.txt")
    with open(listing_txt_path, "w", encoding="utf-8") as f:
        f.write(new_listing_text)

    return RedirectResponse(url=f"/build-listing/result/{session_id}", status_code=303)


@app.post("/build-listing/result/{session_id}/title", response_class=HTMLResponse)
async def update_listing_title(
    request: Request,
    session_id: str,
    title_override: str = Form(""),
):
    """Save a manual title override and patch listing.txt first line."""
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if not all(c in safe_chars for c in session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")

    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    title = title_override.strip()
    title_override_path = os.path.join(session_dir, "title_override.json")

    if title:
        with open(title_override_path, "w", encoding="utf-8") as f:
            json.dump({"title": title}, f)
    else:
        if os.path.isfile(title_override_path):
            os.remove(title_override_path)

    # Patch the first line of listing.txt
    listing_txt_path = os.path.join(session_dir, "listing_output", "listing_description.txt")
    if title and os.path.isfile(listing_txt_path):
        try:
            with open(listing_txt_path, encoding="utf-8") as f:
                existing = f.read()
            with open(listing_txt_path, "w", encoding="utf-8") as f:
                f.write(_apply_title_override(existing, title))
        except Exception:
            pass

    return RedirectResponse(url=f"/build-listing/result/{session_id}", status_code=303)


@app.post("/build-listing/result/{session_id}/text", response_class=HTMLResponse)
async def save_listing_text_direct(
    request: Request,
    session_id: str,
    listing_text_edit: str = Form(""),
):
    """Overwrite listing.txt with the dealer's direct manual edits."""
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if not all(c in safe_chars for c in session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")

    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    listing_txt_path = os.path.join(session_dir, "listing_output", "listing_description.txt")
    text = listing_text_edit  # preserve exactly what the dealer typed
    if text.strip():
        with open(listing_txt_path, "w", encoding="utf-8") as f:
            f.write(text)

    return RedirectResponse(url=f"/build-listing/result/{session_id}", status_code=303)


@app.get("/download-pack/{session_id}")
async def download_pack_by_session(session_id: str):
    """Return the listing pack ZIP for a given session."""
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if not all(c in safe_chars for c in session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")

    pack_dir = os.path.join(_OUTPUTS_DIR, session_id, "listing_output")
    zip_path = os.path.join(_OUTPUTS_DIR, session_id, "listing_output.zip")
    if not os.path.isdir(pack_dir):
        raise HTTPException(status_code=404, detail="Pack not found")

    # Always rebuild ZIP so it reflects any post-generation edits (title, listing text, notes)
    try:
        _zip_folder(pack_dir, zip_path)
    except Exception:
        if not os.path.isfile(zip_path):
            raise HTTPException(status_code=500, detail="ZIP build failed")

    # Read machine label from metadata for the download filename
    meta_path = os.path.join(_OUTPUTS_DIR, session_id, "listing_output", "metadata_internal.json")
    filename = "listing_pack.zip"
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            parts = [str(meta.get("year") or ""), meta.get("make") or "", meta.get("model") or ""]
            label = "_".join(p for p in parts if p).replace(" ", "_") or "machine"
            filename = f"{label}_listing_pack.zip"
        except Exception:
            pass

    return FileResponse(zip_path, media_type="application/zip", filename=filename)


@app.post("/generate-listing-pack")
async def generate_listing_pack_endpoint(
    raw_text:     str  = Form(""),
    spec_level:   str  = Form("technical"),
    dealer_name:  str  = Form(""),
    phone:        str  = Form(""),
    email:        str  = Form(""),
    location:     str  = Form(""),
    generate_spec_sheet_flag:   bool = Form(True),
    generate_image_pack_flag:   bool = Form(True),
    generate_walkaround_flag:   bool = Form(False),
    photos: List[UploadFile] = File(default=[]),
):
    """
    Full listing-pack assembly endpoint.

    Accepts multipart/form-data with:
      - raw_text       : raw listing text
      - photos         : zero or more image files
      - dealer_*       : optional dealer contact fields
      - generate_*     : optional output toggles

    Returns JSON manifest with paths + download URL.
    """
    raw = (raw_text or "").strip()
    if not raw:
        return {"success": False, "error": "No listing text provided.", "warnings": []}

    warnings: list[str] = []

    # ── Parse + resolve ───────────────────────────────────────────────────────
    parsed            = safe_parse_listing(raw)
    specs, confidence = safe_lookup_machine(parsed)
    session_dir, session_web = _make_session_dir(parsed)

    resolved_machine: dict | None = None
    if specs is not None:
        resolved_machine = _run_spec_resolver(
            raw,
            parsed,
            specs,
            confidence,
            parsed_year=parsed.get("year"),
        )

    listing_data    = _stub_build_listing_data(parsed, resolved_machine)
    listing_text    = _stub_generate_listing_text(listing_data, resolved_machine, spec_level)

    # ── Spec sheet entries ────────────────────────────────────────────────────
    spec_entries: list[tuple[str, str]] = []
    if generate_spec_sheet_flag and resolved_machine and resolved_machine.get("resolved_specs"):
        _rs_for_sheet = dict(resolved_machine["resolved_specs"])
        _ui_for_sheet = resolved_machine.get("ui_hints") or {}
        _eq_t         = (parsed.get("equipment_type") or "").lower()
        spec_entries = build_spec_sheet_entries(
            resolved_specs = _rs_for_sheet,
            ui_hints       = _ui_for_sheet,
            equipment_type = _eq_t,
        )

    # ── Save uploaded photos to a temp staging area ───────────────────────────
    photo_paths: list[str] = []
    if generate_image_pack_flag and photos:
        staging_dir = os.path.join(session_dir, "_uploads")
        os.makedirs(staging_dir, exist_ok=True)
        for upload in photos:
            if not upload.filename:
                continue
            # Sanitise filename — keep only safe chars
            safe_name = "".join(
                c for c in upload.filename if c.isalnum() or c in "._- "
            ).strip() or f"photo_{uuid.uuid4().hex[:6]}.jpg"
            dest = os.path.join(staging_dir, safe_name)
            try:
                content = await upload.read()
                with open(dest, "wb") as f:
                    f.write(content)
                photo_paths.append(dest)
            except Exception as exc:
                warnings.append(f"Could not save {upload.filename}: {exc}")

    dealer_info = {
        "dealer_name": dealer_name.strip() or None,
        "phone":       phone.strip()       or None,
        "email":       email.strip()       or None,
        "location":    location.strip()    or None,
    }

    # ── Assemble pack ─────────────────────────────────────────────────────────
    try:
        pack = build_listing_pack(
            raw_text               = raw,
            parsed_listing         = parsed,
            resolved_machine       = resolved_machine,
            generated_listing_text = listing_text,
            spec_sheet_entries     = spec_entries,
            image_input_paths      = photo_paths,
            dealer_info            = dealer_info,
            generate_walkaround    = generate_walkaround_flag,
            session_dir            = session_dir,
            session_web            = session_web,
        )
    except Exception as exc:
        return {
            "success": False,
            "error":   f"Pack assembly error: {exc}",
            "warnings": warnings,
        }

    # ── Merge upload warnings + pack warnings ─────────────────────────────────
    all_warnings = warnings + (pack.get("warnings") or [])

    wk      = pack.get("walkaround") or {}
    wk_path = pack["outputs"].get("walkaround_mp4")

    # ── Scoring ───────────────────────────────────────────────────────────────
    pack_scoring:           dict | None = None
    pack_fix_my_listing:    dict | None = None
    pack_confirm_required:  dict | None = None
    pack_rewritten:         dict | None = None
    try:
        _registry_eq_type = (specs.get("equipment_type") if specs else "") or ""
        scorer_input = _build_scorer_input(
            parsed, resolved_machine,
            raw_text             = raw,
            photo_count          = len(photo_paths),
            eq_type_fallback     = _registry_eq_type,
            has_walkaround_video = wk.get("included", False),
            has_spec_sheet_pdf   = bool(pack["outputs"].get("spec_sheet_png")),
        )
        pack_scoring        = _score_listing(scorer_input)
        pack_fix_my_listing = build_fix_my_listing(pack_scoring)
    except Exception as _exc:
        all_warnings.append(f"Scoring error (non-fatal): {_exc}")

    if resolved_machine:
        try:
            pack_confirm_required = build_confirm_required(
                requires_confirm           = resolved_machine.get("requires_confirm") or [],
                resolved_specs             = resolved_machine.get("resolved_specs")   or {},
                overall_resolution_status  = resolved_machine.get("overall_resolution_status") or "",
                safe_for_listing_injection = resolved_machine.get("safe_for_listing_injection", True),
            )
        except Exception as _exc:
            all_warnings.append(f"Confirm-required error (non-fatal): {_exc}")

    try:
        pack_rewritten = build_rewritten_listing(
            listing_data           = listing_data,
            added_specs            = resolved_machine,
            spec_level             = spec_level,
            generated_listing_text = listing_text,
        )
    except Exception as _exc:
        all_warnings.append(f"Rewrite error (non-fatal): {_exc}")

    return {
        "success":            pack["success"],
        "machine_match":      pack["machine_match"],
        "spec_count":         pack["spec_count"],
        "image_count":        len(photo_paths),
        "scoring":            pack_scoring,
        "fix_my_listing":     pack_fix_my_listing,
        "confirm_required":   pack_confirm_required,
        "rewritten_listing":  pack_rewritten,
        "outputs": {
            "listing_txt":       _asset_url(pack["outputs"].get("listing_txt"),    session_web),
            "spec_sheet_png":    _asset_url(pack["outputs"].get("spec_sheet_png"), session_web + "/listing_output/spec_sheet"),
            "image_pack_folder": session_web + "/listing_output" if pack["outputs"].get("image_pack_folder") else None,
            "walkaround_mp4":    _asset_url(wk_path, session_web + "/listing_output") if wk_path else None,
            "zip_file":          pack.get("zip_web_url"),
            "zip_path":          pack.get("zip_path"),
        },
        "walkaround": {
            "requested": wk.get("requested", False),
            "included":  wk.get("included",  False),
            "status":    wk.get("status",    "not_requested"),
        },
        "warnings": all_warnings,
    }


@app.get("/build-listing", response_class=HTMLResponse)
async def build_listing_form(request: Request):
    return templates.TemplateResponse("build_listing.html", {"request": request})


@app.post("/build-listing/identify")
async def build_listing_identify(
    year:  int = Form(...),
    make:  str = Form(...),
    model: str = Form(...),
):
    """
    Step 1 of the two-step Build My Listing flow.

    Runs registry lookup + spec resolver for the given machine and returns:
      - match status and confidence
      - equipment type label
      - short OEM spec preview for display
      - equipment-type-specific feature checklist config
      - condition % field label
    No session dir, no ZIP, no photos — identification only.
    """
    parsed = {"make": make.strip(), "model": model.strip(), "make_source": "explicit"}
    specs, confidence = safe_lookup_machine(parsed)

    equipment_type: str | None = None
    spec_preview:   list[dict] = []
    web_assisted = False

    if specs is not None:
        # ── Registry hit path (unchanged) ─────────────────────────────────────
        resolved_machine = _run_spec_resolver(
            "",
            parsed,
            specs,
            confidence,
            parsed_year=year,
        )
        if resolved_machine:
            equipment_type  = resolved_machine.get("equipment_type")
            resolved_specs  = resolved_machine.get("resolved_specs") or {}
            for field, label, unit in _IDENTIFY_SPEC_FIELDS:
                val = resolved_specs.get(field)
                if val is not None:
                    spec_preview.append({
                        "label": label,
                        "value": _fmt_spec_pill_value(val, unit),
                    })
    else:
        # ── Web-assisted fallback — no registry match ─────────────────────────
        fallback = web_match_fallback(make.strip(), model.strip(), year)
        equipment_type = fallback.get("equipment_type")
        web_assisted   = True

    # ── Match quality label ───────────────────────────────────────────────────
    if specs is not None:
        if confidence >= 0.80:
            match_quality = "strong"
        elif confidence >= 0.65:
            match_quality = "moderate"
        else:
            match_quality = "weak"
    elif web_assisted:
        match_quality = "web_assisted"
    else:
        match_quality = "none"

    match_found = specs is not None or web_assisted

    features   = _FEATURE_CONFIG.get(equipment_type or "", _FEATURE_CONFIG["_default"])
    eq_label   = _EQ_TYPE_LABELS.get(equipment_type or "", "Unknown Equipment Type")
    cond_label = _CONDITION_PCT_LABEL.get(equipment_type or "", "Condition %")

    # UX message: only shown when spec_preview is empty and web fallback was used
    match_message = (
        "Model not found in our database — identified via web search. "
        "Your listing will be generated with available information."
        if web_assisted else ""
    )

    return JSONResponse({
        "match_found":         match_found,
        "match_quality":       match_quality,
        "machine_label":       f"{year} {make.strip().upper()} {model.strip()}",
        "year":                year,
        "make":                make.strip().upper(),
        "model":               model.strip(),
        "equipment_type":      equipment_type,
        "eq_type_label":       eq_label,
        "spec_preview":        spec_preview,
        "features":            features,
        "condition_pct_label": cond_label,
        "web_assisted":        web_assisted,
        "match_message":       match_message,
    })


@app.post("/build-listing")
async def build_listing_endpoint(
    year:                 int            = Form(...),
    make:                 str            = Form(...),
    model:                str            = Form(...),
    hours:                int            = Form(...),
    cab_type:             Optional[str]  = Form(None),
    heater:               str            = Form("false"),
    ac:                   str            = Form("false"),
    high_flow:            str            = Form("false"),
    two_speed:            str            = Form("false"),
    ride_control:         str            = Form("false"),
    backup_camera:        str            = Form("false"),
    radio:                str            = Form("false"),
    control_type:         Optional[str]  = Form(None),
    joystick_controls:    str            = Form("false"),
    one_owner:            str            = Form("false"),
    # Equipment-type-specific features
    thumb:                str            = Form("false"),
    aux_hydraulics:       str            = Form("false"),
    blade:                str            = Form("false"),
    zero_tail_swing:      str            = Form("false"),
    rubber_tracks:        str            = Form("false"),
    quick_attach:         Optional[str]  = Form(None),
    coupler_type:         Optional[str]  = Form(None),
    tire_condition:       Optional[str]  = Form(None),
    asking_price:         Optional[str]  = Form(None),
    track_condition:      Optional[str]  = Form(None),
    attachments_included: Optional[str]  = Form(None),
    condition_notes:        Optional[str]        = Form(None),
    # CTL core output field (locked standard 2026-04-10)
    serial_number:          Optional[str]        = Form(None),
    # CTL feature fields (locked standard 2026-04-10)
    air_ride_seat:          str                  = Form("false"),
    self_leveling:          str                  = Form("false"),
    reversing_fan:          str                  = Form("false"),
    bucket_included:        str                  = Form("false"),
    bucket_size:            Optional[str]        = Form(None),
    warranty_status:        Optional[str]        = Form(None),
    overlay_contact_name:   Optional[str]        = Form(None),
    overlay_contact_phone:  Optional[str]        = Form(None),
    overlay_logo:           Optional[UploadFile] = File(None),
    photos: List[UploadFile] = File(default=[]),
):
    """
    V1 Build My Listing endpoint.
    Accepts dealer inputs + photos, runs registry lookup + spec resolver,
    assembles a listing pack ZIP, and returns it for download.
    """
    def _bool(v: str) -> bool:
        return str(v).lower() in ("true", "1", "on", "yes")

    def _tristatus(v: str) -> Optional[str]:
        """Status field: 'true'/'yes'→'yes', 'false'/'no'→'no', 'optional'→'optional', else→None."""
        s = str(v).lower().strip()
        if s in ("true", "1", "on", "yes"):    return "yes"
        if s in ("false", "0", "off", "no"):   return "no"
        if s == "optional":                     return "optional"
        return None

    price_int: Optional[int] = None
    if asking_price and asking_price.strip():
        try:
            price_int = int(asking_price.strip().replace("$", "").replace(",", ""))
        except ValueError:
            raise HTTPException(status_code=422, detail="asking_price must be a number")

    try:
        dealer_input = DealerInput(
            year=year,
            make=make,
            model=model,
            hours=hours,
            asking_price=price_int,
            cab_type=("enclosed" if cab_type and cab_type.strip().lower() == "true" else (cab_type.strip() or None if cab_type else None)),
            heater=_bool(heater),
            ac=_bool(ac),
            high_flow=_tristatus(high_flow),
            two_speed_travel=_tristatus(two_speed),
            ride_control=_bool(ride_control),
            backup_camera=_bool(backup_camera),
            radio=_bool(radio),
            control_type=(control_type.strip() or None if control_type else None) or ("joystick" if _bool(joystick_controls) else None),
            one_owner=_bool(one_owner),
            # thumb_type: mini_ex feature config now sends name="thumb" (boolean checkbox).
            # Map thumb=True → "hydraulic" (presence-only; type is not captured via checkbox).
            thumb_type="hydraulic" if _bool(thumb) else None,
            aux_hydraulics=_bool(aux_hydraulics),
            # blade_type: same approach — blade=True → "straight" (most common mini-ex blade).
            blade_type="straight" if _bool(blade) else None,
            zero_tail_swing=_bool(zero_tail_swing),
            rubber_tracks=_bool(rubber_tracks),
            # coupler_type: JS sends coupler_type="hydraulic" when checked, "" when unchecked.
            # Falls back to quick_attach for any legacy callers. Guard rejects non-enum strings.
            coupler_type=(lambda q: q if q and q.strip().lower() in {"hydraulic", "manual", "pin-on"} else None)(
                (coupler_type or quick_attach or "").strip().lower()
            ),
            tire_condition=tire_condition.strip() or None if tire_condition else None,
            track_condition=track_condition.strip() or None if track_condition else None,
            attachments_included=attachments_included.strip() or None if attachments_included else None,
            condition_notes=condition_notes.strip() or None if condition_notes else None,
            serial_number=serial_number.strip() or None if serial_number else None,
            air_ride_seat=_bool(air_ride_seat),
            self_leveling=_bool(self_leveling),
            reversing_fan=_bool(reversing_fan),
            bucket_included=_bool(bucket_included),
            bucket_size=bucket_size.strip() or None if bucket_size else None,
            warranty_status=warranty_status.strip() or None if warranty_status else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # ── Registry lookup + spec resolver ───────────────────────────────────────
    parsed = {
        "make":        dealer_input.make,
        "model":       dealer_input.model,
        "make_source": "explicit",
    }
    specs, confidence = safe_lookup_machine(parsed)
    _full_record: dict | None = specs.get("full_record") if specs else None

    resolved_machine: dict | None = None
    resolved_specs: dict = {}
    if specs is not None:
        # ── Registry hit (unchanged) ───────────────────────────────────────────
        # For skid steer: high_flow and two_speed are unit-level config booleans injected
        # from DealerInput at the output layer (listing_pack_builder / persistence).
        # Passing them as spec-resolver modifiers causes hydraulic_flow.py to switch
        # hydraulic_flow_gpm to the hi-flow registry value, which breaks SSL standard-flow
        # display. SSL must always show standard hydraulic flow from the registry.
        _eq_type = (specs or {}).get("equipment_type", "").lower()
        _is_ssl_or_ctl = _eq_type in ("skid_steer", "compact_track_loader")
        detected_modifiers = _structured_modifiers_from_flags({
            # SSL and CTL: high_flow / two_speed are injected at the output layer (listing_pack_builder
            # / persistence) as unit-level config booleans.  Passing them as resolver modifiers causes
            # hydraulic_flow.py to switch hydraulic_flow_gpm to the hi-flow registry value, which
            # violates the locked standard (aux_flow_standard_gpm must remain standard-flow OEM spec).
            "high_flow": None if _is_ssl_or_ctl else dealer_input.high_flow,
            "two_speed": None if _is_ssl_or_ctl else dealer_input.two_speed_travel,
            "thumb": dealer_input.thumb_type,
        })
        resolved_machine = _run_spec_resolver(
            "",
            parsed,
            specs,
            confidence,
            parsed_year=dealer_input.year,
            detected_modifiers=detected_modifiers,
        )
        if resolved_machine:
            resolved_specs = resolved_machine.get("resolved_specs") or {}
    else:
        # ── Web-assisted fallback — no registry match ──────────────────────────
        # Populates equipment_type so the pack builder picks the right template.
        # resolved_specs stays {} — no OEM specs are injected from web results.
        resolved_machine = web_match_fallback(
            dealer_input.make, dealer_input.model, dealer_input.year
        )

    # ── Session dir ───────────────────────────────────────────────────────────
    session_dir, session_web = _make_session_dir(parsed)

    # ── Save uploaded photos ──────────────────────────────────────────────────
    photo_paths: list[str] = []
    if photos:
        staging_dir = os.path.join(session_dir, "_uploads")
        os.makedirs(staging_dir, exist_ok=True)
        for upload in photos:
            if not upload.filename:
                continue
            safe_name = "".join(
                c for c in upload.filename if c.isalnum() or c in "._- "
            ).strip() or f"photo_{uuid.uuid4().hex[:6]}.jpg"
            dest = os.path.join(staging_dir, safe_name)
            try:
                content = await upload.read()
                with open(dest, "wb") as f:
                    f.write(content)
                photo_paths.append(dest)
            except Exception:
                pass  # non-fatal; photo skipped

    # ── Save overlay logo if provided ─────────────────────────────────────────
    overlay_logo_path: Optional[str] = None
    if overlay_logo and overlay_logo.filename:
        ext = os.path.splitext(overlay_logo.filename)[1].lower() or ".png"
        if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            ext = ".png"
        logo_dest = os.path.join(session_dir, f"overlay_logo{ext}")
        try:
            logo_content = await overlay_logo.read()
            with open(logo_dest, "wb") as f:
                f.write(logo_content)
            overlay_logo_path = logo_dest
        except Exception:
            pass  # non-fatal — overlay just won't include logo

    # ── Build pack ────────────────────────────────────────────────────────────
    _contact_name  = (overlay_contact_name  or "").strip() or None
    _contact_phone = (overlay_contact_phone or "").strip() or None
    _dealer_info   = (
        {"contact_name": _contact_name, "contact_phone": _contact_phone}
        if (_contact_name or _contact_phone) else None
    )
    try:
        pack = build_listing_pack_v1(
            dealer_input=dealer_input,
            resolved_specs=resolved_specs,
            resolved_machine=resolved_machine,
            image_input_paths=photo_paths,
            session_dir=session_dir,
            session_web=session_web,
            overlay_logo_path=overlay_logo_path,
            overlay_contact_name=_contact_name,
            overlay_contact_phone=_contact_phone,
            dealer_info=_dealer_info,
            full_record=_full_record,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pack generation error: {exc}")

    if not pack.get("success") or not pack.get("zip_path"):
        raise HTTPException(status_code=500, detail="Pack generation failed")

    # Persist inputs so the result page can offer listing refinement + tier toggle
    try:
        with open(os.path.join(session_dir, "dealer_input.json"), "w", encoding="utf-8") as f:
            json.dump(dealer_input.model_dump(), f)

        # Build the same enriched resolved_specs that listing_pack_builder uses for
        # the spec sheet, so the result page tier toggle and the spec sheet are identical.
        _persist_eq = (resolved_machine or {}).get("equipment_type", "").lower()
        _persist_rs = dict(resolved_specs)
        if _persist_eq == "skid_steer":
            # Inject dealer-confirmed booleans exactly as listing_pack_builder does.
            # None stays None (unknown) — no inference or fallback.
            if dealer_input.high_flow is not None:
                _persist_rs["high_flow"] = dealer_input.high_flow
            if dealer_input.two_speed_travel is not None:
                _persist_rs["two_speed"] = dealer_input.two_speed_travel
            # hours: always present (dealer-entered), core SSL output.
            _persist_rs["hours"] = dealer_input.hours

        if _persist_eq == "compact_track_loader":
            # Mirror exactly what listing_pack_builder injects for CTL spec sheet.
            # None stays None — no inference.
            if dealer_input.high_flow is not None:
                _persist_rs["high_flow"] = dealer_input.high_flow
            if dealer_input.two_speed_travel is not None:
                _persist_rs["two_speed"] = dealer_input.two_speed_travel
            # hours: always present, core CTL output.
            _persist_rs["hours"] = dealer_input.hours
            # Dealer-input core output fields (locked CTL standard 2026-04-10).
            if dealer_input.cab_type:
                _persist_rs["cab_type"] = dealer_input.cab_type
            _persist_rs["ac"] = dealer_input.ac
            if dealer_input.track_condition:
                _persist_rs["track_condition"] = dealer_input.track_condition
            if dealer_input.serial_number:
                _persist_rs["serial_number"] = dealer_input.serial_number
            # Feature fields: use locked standard buyer-facing key names.
            if dealer_input.heater is not None:
                _persist_rs["heat"] = dealer_input.heater
            if dealer_input.control_type:
                _persist_rs["controls_type"] = dealer_input.control_type
            if dealer_input.coupler_type:
                _persist_rs["quick_attach"] = dealer_input.coupler_type

        with open(os.path.join(session_dir, "resolved_specs.json"), "w", encoding="utf-8") as f:
            json.dump(_persist_rs, f)

        ui_hints = dict((resolved_machine or {}).get("ui_hints") or {})
        # For SSL and CTL: strip text-inference hints so result page never uses them.
        # high_flow / two_speed come only from DealerInput; _displayHiFlow is not
        # a valid display signal (std flow is always shown, not hi-flow).
        if _persist_eq in ("skid_steer", "compact_track_loader"):
            ui_hints.pop("_displayHiFlow",    None)
            ui_hints.pop("_detectedTwoSpeed", None)

        with open(os.path.join(session_dir, "ui_hints.json"), "w", encoding="utf-8") as f:
            json.dump(ui_hints, f)

        # Save dealer contact for spec sheet rendering
        _logo_fn = os.path.basename(overlay_logo_path) if overlay_logo_path else None
        dealer_contact_data = {
            "contact_name":  _contact_name,
            "contact_phone": _contact_phone,
            "logo_filename": _logo_fn,
        }
        with open(os.path.join(session_dir, "dealer_contact.json"), "w", encoding="utf-8") as f:
            json.dump(dealer_contact_data, f)
    except Exception:
        pass  # non-fatal — refinement just won't be offered for this session

    session_id = os.path.basename(session_dir)
    return JSONResponse({
        "success":      True,
        "result_url":   f"/build-listing/result/{session_id}",
        "spec_sheet_url": f"/build-listing/spec-sheet/{session_id}",
    })


@app.get("/build-listing/spec-sheet/{session_id}", response_class=HTMLResponse)
async def spec_sheet_view(request: Request, session_id: str):
    """Render the HTML spec sheet for a completed build-listing session."""
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if not all(c in safe_chars for c in session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")

    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    di_path   = os.path.join(session_dir, "dealer_input.json")
    rs_path   = os.path.join(session_dir, "resolved_specs.json")
    ui_path   = os.path.join(session_dir, "ui_hints.json")
    meta_path = os.path.join(session_dir, "listing_output", "metadata_internal.json")
    dc_path   = os.path.join(session_dir, "dealer_contact.json")

    if not os.path.isfile(di_path):
        raise HTTPException(status_code=404, detail="Listing data not found for this session")

    with open(di_path, encoding="utf-8") as f:
        di_data = json.load(f)

    rs_data: dict = {}
    if os.path.isfile(rs_path):
        with open(rs_path, encoding="utf-8") as f:
            rs_data = json.load(f)

    ui_hints: dict = {}
    if os.path.isfile(ui_path):
        with open(ui_path, encoding="utf-8") as f:
            ui_hints = json.load(f)

    equipment_type = ""
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            equipment_type = json.load(f).get("equipment_type") or ""

    dealer_contact: dict = {}
    if os.path.isfile(dc_path):
        with open(dc_path, encoding="utf-8") as f:
            dealer_contact = json.load(f)

    ctx = _build_spec_sheet_context(
        dealer_input_data=di_data,
        resolved_specs=rs_data,
        ui_hints=ui_hints,
        equipment_type=equipment_type,
        dealer_contact=dealer_contact,
        session_id=session_id,
    )
    ctx["request"] = request
    return templates.TemplateResponse("spec_sheet.html", ctx)


@app.post("/build-listing/preview")
async def build_listing_preview(
    year:                 int           = Form(...),
    make:                 str           = Form(...),
    model:                str           = Form(...),
    hours:                int           = Form(...),
    cab_type:             Optional[str] = Form(None),
    heater:               str           = Form("false"),
    ac:                   str           = Form("false"),
    high_flow:            str           = Form("false"),
    two_speed:            str           = Form("false"),
    ride_control:         str           = Form("false"),
    backup_camera:        str           = Form("false"),
    radio:                str           = Form("false"),
    control_type:         Optional[str] = Form(None),
    joystick_controls:    str           = Form("false"),
    one_owner:            str           = Form("false"),
    thumb:                str           = Form("false"),
    aux_hydraulics:       str           = Form("false"),
    blade:                str           = Form("false"),
    zero_tail_swing:      str           = Form("false"),
    rubber_tracks:        str           = Form("false"),
    quick_attach:         Optional[str] = Form(None),
    coupler_type:         Optional[str] = Form(None),
    tire_condition:       Optional[str] = Form(None),
    track_condition:      Optional[str] = Form(None),
    attachments_included: Optional[str] = Form(None),
    condition_notes:      Optional[str] = Form(None),
    # CTL core output field (locked standard 2026-04-10)
    serial_number:        Optional[str] = Form(None),
    # CTL feature fields (locked standard 2026-04-10)
    air_ride_seat:        str           = Form("false"),
    self_leveling:        str           = Form("false"),
    reversing_fan:        str           = Form("false"),
    bucket_included:      str           = Form("false"),
    bucket_size:          Optional[str] = Form(None),
    warranty_status:      Optional[str] = Form(None),
):
    """
    Lightweight preview endpoint for Build My Listing.
    Runs registry lookup + use-case scorer; returns scorer-backed
    enrichment payload as JSON — no photos, no ZIP, no session dir.
    Called by the frontend to populate the live preview block.
    """
    def _bool(v: str) -> bool:
        return str(v).lower() in ("true", "1", "on", "yes")

    def _tristatus(v: str) -> Optional[str]:
        """Status field: 'true'/'yes'→'yes', 'false'/'no'→'no', 'optional'→'optional', else→None."""
        s = str(v).lower().strip()
        if s in ("true", "1", "on", "yes"):    return "yes"
        if s in ("false", "0", "off", "no"):   return "no"
        if s == "optional":                     return "optional"
        return None

    try:
        dealer_input = DealerInput(
            year=year, make=make, model=model, hours=hours,
            cab_type=("enclosed" if cab_type and cab_type.strip().lower() == "true" else (cab_type.strip() or None if cab_type else None)),
            heater=_bool(heater),
            ac=_bool(ac),
            high_flow=_tristatus(high_flow),
            two_speed_travel=_tristatus(two_speed),
            ride_control=_bool(ride_control),
            backup_camera=_bool(backup_camera),
            radio=_bool(radio),
            control_type=(control_type.strip() or None if control_type else None) or ("joystick" if _bool(joystick_controls) else None),
            one_owner=_bool(one_owner),
            thumb_type="hydraulic" if _bool(thumb) else None,
            aux_hydraulics=_bool(aux_hydraulics),
            blade_type="straight" if _bool(blade) else None,
            zero_tail_swing=_bool(zero_tail_swing),
            rubber_tracks=_bool(rubber_tracks),
            coupler_type=(lambda q: q if q and q.strip().lower() in {"hydraulic", "manual", "pin-on"} else None)(
                (coupler_type or quick_attach or "").strip().lower()
            ),
            tire_condition=tire_condition.strip() or None if tire_condition else None,
            track_condition=track_condition.strip() or None if track_condition else None,
            attachments_included=attachments_included.strip() or None if attachments_included else None,
            condition_notes=condition_notes.strip() or None if condition_notes else None,
            serial_number=serial_number.strip() or None if serial_number else None,
            air_ride_seat=_bool(air_ride_seat),
            self_leveling=_bool(self_leveling),
            reversing_fan=_bool(reversing_fan),
            bucket_included=_bool(bucket_included),
            bucket_size=bucket_size.strip() or None if bucket_size else None,
            warranty_status=warranty_status.strip() or None if warranty_status else None,
        )
    except Exception:
        return JSONResponse({"ok": False, "payload": None, "machine_match": None})

    # Registry lookup
    parsed = {"make": dealer_input.make, "model": dealer_input.model, "make_source": "explicit"}
    specs, confidence = safe_lookup_machine(parsed)

    resolved_machine: dict | None = None
    resolved_specs: dict = {}
    equipment_type: str | None = None
    if specs is not None:
        # ── Registry hit (unchanged) ───────────────────────────────────────────
        # SSL and CTL: suppress high_flow/two_speed modifiers — same rule as /build-listing.
        _eq_type_prev = (specs or {}).get("equipment_type", "").lower()
        _is_ssl_or_ctl_prev = _eq_type_prev in ("skid_steer", "compact_track_loader")
        detected_modifiers = _structured_modifiers_from_flags({
            "high_flow": None if _is_ssl_or_ctl_prev else dealer_input.high_flow,
            "two_speed": None if _is_ssl_or_ctl_prev else dealer_input.two_speed_travel,
            "thumb": dealer_input.thumb_type,
        })
        resolved_machine = _run_spec_resolver(
            "",
            parsed,
            specs,
            confidence,
            parsed_year=dealer_input.year,
            detected_modifiers=detected_modifiers,
        )
        if resolved_machine:
            resolved_specs = resolved_machine.get("resolved_specs") or {}
            equipment_type = resolved_machine.get("equipment_type")
    else:
        # ── Web-assisted fallback — no registry match ──────────────────────────
        resolved_machine = web_match_fallback(
            dealer_input.make, dealer_input.model, dealer_input.year
        )
        equipment_type = resolved_machine.get("equipment_type")

    # Run scorer enrichment
    payload = build_use_case_payload(equipment_type, dealer_input, resolved_specs)

    machine_match = " ".join(str(p) for p in [year, make, model] if p) or None

    return JSONResponse({
        "ok":           True,
        "machine_match": machine_match,
        "spec_found":   resolved_machine is not None,
        "equipment_type": equipment_type,
        "payload": {
            "best_for":           payload.get("top_use_cases_for_listing", []) if payload else [],
            "best_for_ui":        build_use_case_ui_items(payload) if payload else [],
            "attachment_sentence": payload.get("attachment_sentence") if payload else None,
            "limitation_sentence": payload.get("limitation_sentence") if payload else None,
        } if payload else None,
    })


@app.post("/fix-listing", response_model=FixListingResponse)
async def fix_listing(payload: FixListingRequest):
    if not payload.raw_text or not payload.raw_text.strip():
        return FixListingResponse(
            cleaned_listing="",
            error="No listing text provided."
        )
    try:
        result = fix_listing_service(
            payload.raw_text.strip(),
            spec_level        = payload.spec_level,
            generate_spec_sheet = payload.generate_spec_sheet,
            generate_variants   = payload.generate_spec_sheet_variants,
            generate_package    = payload.generate_listing_package,
        )
        return FixListingResponse(**result)
    except Exception as exc:
        return FixListingResponse(
            cleaned_listing="",
            error=f"Processing error: {str(exc)}"
        )
