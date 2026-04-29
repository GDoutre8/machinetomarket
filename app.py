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
from spec_sheet_renderer_adapter import build_spec_sheet_data as _build_ss_data
from spec_sheet_renderer import render_spec_sheet as _render_spec_sheet

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


def _ensure_playwright_chromium() -> None:
    """Install Playwright Chromium if the binary is not already present.

    Runs synchronously at startup.  Playwright caches the binary so
    subsequent restarts complete in < 1 s (just a path check).
    """
    import subprocess
    import sys
    from pathlib import Path

    cache_root = Path.home() / ".cache" / "ms-playwright"
    found = list(cache_root.glob("chromium-*/chrome-linux/chrome"))
    if found:
        print(f"  [Startup] Playwright Chromium already installed: {found[0]}")
        return
    print("  [Startup] Playwright Chromium not found — installing now...")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
            check=True,
        )
        print("  [Startup] Playwright Chromium installed OK.")
    except Exception as exc:
        print(f"  [Startup] WARNING: Playwright install failed: {exc}")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # On startup: ensure Playwright Chromium is present, purge stale
    # sessions from previous run, then start the hourly cleanup loop.
    _ensure_playwright_chromium()
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


# ── Equipment-type feature config ─────────────────────────────────────────────
# Defines which feature checkboxes appear in Step 2 for each equipment type.
# Each entry: {"name": DealerInput field name, "label": display label}

_FEATURE_CONFIG: dict[str, list[dict]] = {
    "compact_track_loader": [
        # ── Primary machine features ──────────────────────────────────────────
        {"name": "cab_type", "label": "Cab Type", "type": "select",
         "options": [{"value": "enclosed", "label": "Enclosed"}, {"value": "open", "label": "Open"}, {"value": "canopy", "label": "Canopy"}]},
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
        {"name": "cab_type", "label": "Cab Type", "type": "select",
         "options": [{"value": "enclosed", "label": "Enclosed"}, {"value": "open", "label": "Open"}, {"value": "canopy", "label": "Canopy"}]},
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
        {"name": "cab_type", "label": "Cab Type", "type": "select",
         "options": [{"value": "enclosed", "label": "Enclosed"}, {"value": "open", "label": "Open"}, {"value": "canopy", "label": "Canopy"}]},
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
        {"name": "cab_type", "label": "Cab Type", "type": "select",
         "options": [{"value": "enclosed", "label": "Enclosed"}, {"value": "open", "label": "Open"}, {"value": "canopy", "label": "Canopy"}]},
        {"name": "heater",            "label": "Heat"},
        {"name": "ac",                "label": "A/C"},
        {"name": "backup_camera",     "label": "Backup Camera"},
        {"name": "one_owner",         "label": "One Owner"},
    ],
    "wheel_loader": [
        {"name": "cab_type", "label": "Cab Type", "type": "select",
         "options": [{"value": "enclosed", "label": "Enclosed"}, {"value": "open", "label": "Open"}, {"value": "canopy", "label": "Canopy"}]},
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
        {"name": "cab_type", "label": "Cab Type", "type": "select",
         "options": [{"value": "enclosed", "label": "Enclosed"}, {"value": "open", "label": "Open"}, {"value": "canopy", "label": "Canopy"}]},
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
    # Wheel loader — only populated for wheel_loader records; silently absent for other types
    ("bucket_capacity_yd3", "Bucket",    "yd\u00b3"),
    ("breakout_force_lbs",  "Breakout",  "lbs"),
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
    # Legacy route — redirect all traffic to the current flow.
    return RedirectResponse(url="/build-listing", status_code=301)


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

    # Load explicit output paths written at build time (new sessions only).
    # Old sessions without this file fall back to the glob paths below.
    _explicit_path = os.path.join(pack_dir, "outputs_explicit.json")
    _explicit_outputs: dict = {}
    if os.path.isfile(_explicit_path):
        try:
            with open(_explicit_path, encoding="utf-8") as _ef:
                _explicit_outputs = json.load(_ef)
        except Exception:
            pass

    def _vq(abs_path: str | None) -> str:
        """Return ?v={mtime} cache-bust param for a generated asset."""
        try:
            return f"?v={int(os.path.getmtime(abs_path))}" if abs_path and os.path.isfile(abs_path) else ""
        except Exception:
            return ""

    # Spec sheet URL: prefer the explicit path recorded at build time.
    # Fall back to glob for sessions built before outputs_explicit.json existed.
    _ss_explicit = _explicit_outputs.get("spec_sheet_png")
    _ss_abs: str | None = None
    if _ss_explicit and os.path.isfile(_ss_explicit):
        _ss_abs = _ss_explicit
    else:
        _ss_matches = sorted(_glob.glob(
            os.path.join(pack_dir, "Listing_Photos", "*_02_spec_sheet.png")
        ))
        if _ss_matches:
            _ss_abs = _ss_matches[0]
        else:
            print(f"  [Result] WARNING: spec sheet not found in {pack_dir}/Listing_Photos/")
    spec_sheet_url = (
        f"{web_base}/Listing_Photos/{os.path.basename(_ss_abs)}{_vq(_ss_abs)}"
        if _ss_abs else None
    )

    def _load_image_urls(subfolder: str) -> list[str]:
        img_dir = os.path.join(pack_dir, subfolder)
        if not os.path.isdir(img_dir):
            return []
        found = sorted(
            p for p in _glob.glob(os.path.join(img_dir, "*"))
            if os.path.isfile(p) and p.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        )
        return [f"{web_base}/{subfolder}/{os.path.basename(p)}" for p in found]

    def _load_listing_photos() -> list[str]:
        """Return only real listing photos — *_listing.jpg / *_listing.jpeg only.
        Excludes *_card.png, *_spec_sheet.png, and all other PNG artifacts.

        UI-ONLY: feeds the Listing Photos carousel on the result page.
        Must NOT be used for ZIP assembly. ZIP is built by _zip_folder()
        in listing_pack_builder.py and includes card + spec sheet independently."""
        img_dir = os.path.join(pack_dir, "Listing_Photos")
        if not os.path.isdir(img_dir):
            return []
        found = sorted(
            p for p in _glob.glob(os.path.join(img_dir, "*"))
            if os.path.isfile(p) and (
                p.lower().endswith("_listing.jpg") or
                p.lower().endswith("_listing.jpeg")
            )
        )
        return [f"{web_base}/Listing_Photos/{os.path.basename(p)}" for p in found]

    image_packs = [
        {
            "folder":   "Listing_Photos",
            "label":    "Listing Photos",
            "tag":      "Ready to Post",
            "hint":     "Branded listing images with your logo and contact info. Use these for Facebook Marketplace, Craigslist, dealer sites, and all listing platforms.",
            "urls":     _load_listing_photos(),
        },
        {
            "folder":   "Original_Photos",
            "label":    "Original Photos",
            "tag":      "Full Size",
            "hint":     "Unmodified originals. Use these if you need to re-edit or upload to platforms with their own crop tool.",
            "urls":     _load_image_urls("Original_Photos"),
        },
    ]

    # Card PNG URL — "Featured Listing Image" on result page.
    _card_explicit = _explicit_outputs.get("card_png")
    card_png_url: str | None = None
    if _card_explicit and os.path.isfile(_card_explicit):
        card_png_url = f"{web_base}/Listing_Photos/{os.path.basename(_card_explicit)}{_vq(_card_explicit)}"

    # Primary preview for Image Pack: first real listing photo.
    # Card and spec sheet are displayed in their own dedicated sections above.
    _listing_urls = image_packs[0]["urls"]
    primary_preview_image: str | None = _listing_urls[0] if _listing_urls else None

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
    # Dealer's verify-page override (best_for_override.json) takes priority;
    # otherwise re-run the scorer from saved dealer_input.json + resolved_specs.json.
    best_for_ui: list[dict] = []
    _bf_override_path = os.path.join(session_dir, "best_for_override.json")
    _bf_override_labels: list[str] = []
    if os.path.isfile(_bf_override_path):
        try:
            with open(_bf_override_path, encoding="utf-8") as f:
                _bf_override_labels = list((json.load(f) or {}).get("best_for") or [])
        except Exception:
            _bf_override_labels = []

    _di_path  = os.path.join(session_dir, "dealer_input.json")
    _rs_path2 = os.path.join(session_dir, "resolved_specs.json")
    if _bf_override_labels:
        try:
            from listing_builder import _UC_DESCRIPTOR  # type: ignore
        except Exception:
            _UC_DESCRIPTOR = {}  # type: ignore
        for label in _bf_override_labels[:6]:
            best_for_ui.append({
                "label":      label,
                "descriptor": _UC_DESCRIPTOR.get(label, "") if isinstance(_UC_DESCRIPTOR, dict) else "",
            })
    elif os.path.isfile(_di_path) and os.path.isfile(_rs_path2):
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
        "spec_sheet_url":        spec_sheet_url,
        "card_png_url":          card_png_url,
        "image_packs":           image_packs,
        "primary_preview_image": primary_preview_image,
        "walkaround_url":        walkaround_url,
        "zip_url":               zip_url,
        "can_refine":            can_refine,
        "best_for_ui":           best_for_ui,
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

    # Always rebuild ZIP so it reflects any post-generation edits (title, listing text, notes).
    # Never fall back to a stale ZIP — if rebuild fails, surface the error.
    try:
        _zip_folder(pack_dir, zip_path)
    except Exception:
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
    DEPRECATED — legacy endpoint used by app_v2.js / index.html.
    The active flow is POST /build-listing (build_listing.html + build_listing_pack_v1).
    This endpoint still functions for backward compatibility but is no longer
    the primary path and does not generate a v10 hero card or spec sheet image.
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
            "spec_sheet_png":    _asset_url(pack["outputs"].get("spec_sheet_png"), session_web + "/listing_output/Listing_Photos"),
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
    condition_grade:        Optional[str]        = Form(None),
    # CTL core output fields (locked standard 2026-04-10)
    serial_number:          Optional[str]        = Form(None),
    stock_number:           Optional[str]        = Form(None),
    track_percent_remaining: Optional[int]       = Form(None),
    # CTL feature fields (locked standard 2026-04-10)
    air_ride_seat:          str                  = Form("false"),
    self_leveling:          str                  = Form("false"),
    reversing_fan:          str                  = Form("false"),
    bucket_included:        str                  = Form("false"),
    bucket_size:            Optional[str]        = Form(None),
    warranty_status:        Optional[str]        = Form(None),
    dealer_profile_json:    Optional[str]        = Form(None),
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
            track_percent_remaining=track_percent_remaining,
            attachments_included=attachments_included.strip() or None if attachments_included else None,
            condition_notes=condition_notes.strip() or None if condition_notes else None,
            condition_grade=condition_grade.strip() or None if condition_grade else None,
            serial_number=serial_number.strip() or None if serial_number else None,
            stock_number=stock_number.strip() or None if stock_number else None,
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

    # ── Dealer info for badge stamping ───────────────────────────────────────
    # dealer_profile_json arrives from the browser as:
    #   {"companyName": ..., "contactName": ..., "phone": ..., "logoDataUrl": "data:..."}
    # Decode the logo from base64 so listing_pack_builder can stamp Images 2+.
    dealer_info: dict | None = None
    if dealer_profile_json:
        try:
            import base64 as _b64
            _dp = json.loads(dealer_profile_json)
            if isinstance(_dp, dict) and (_dp.get("companyName") or "").strip():
                _logo_save_path: str | None = None
                _logo_url = (_dp.get("logoDataUrl") or "").strip()
                if _logo_url.startswith("data:") and "base64," in _logo_url:
                    _logo_bytes = _b64.b64decode(_logo_url.split("base64,", 1)[1])
                    _uploads_dir = os.path.join(session_dir, "_uploads")
                    os.makedirs(_uploads_dir, exist_ok=True)
                    _logo_save_path = os.path.join(_uploads_dir, "dealer_logo.png")
                    with open(_logo_save_path, "wb") as _lf:
                        _lf.write(_logo_bytes)
                dealer_info = {
                    "dealer_name":  (_dp.get("companyName")  or "").strip() or None,
                    "contact_name": (_dp.get("contactName")  or "").strip() or None,
                    "phone":        (_dp.get("phone")        or "").strip() or None,
                    "logo_path":    _logo_save_path,
                    # accent_color: not yet in dealer_profile_json schema — defaults to "yellow"
                    "accent_color": (_dp.get("accentColor") or "yellow"),
                }
        except Exception:
            pass  # non-fatal — badge silently skipped if profile is malformed

    # ── Build pack ────────────────────────────────────────────────────────────
    try:
        pack = build_listing_pack_v1(
            dealer_input=dealer_input,
            resolved_specs=resolved_specs,
            resolved_machine=resolved_machine,
            image_input_paths=photo_paths,
            dealer_info=dealer_info,
            session_dir=session_dir,
            session_web=session_web,
            full_record=_full_record,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pack generation error: {exc}")

    if not pack.get("success") or not pack.get("zip_path"):
        raise HTTPException(status_code=500, detail="Pack generation failed")

    # Persist inputs so the result page can offer listing refinement + tier toggle
    try:
        di_dict = dealer_input.model_dump()
        if dealer_profile_json:
            try:
                _dp = json.loads(dealer_profile_json)
                if isinstance(_dp, dict):
                    di_dict["dealer_profile"] = _dp
            except Exception:
                pass
        with open(os.path.join(session_dir, "dealer_input.json"), "w", encoding="utf-8") as f:
            json.dump(di_dict, f)

        # Use the enriched spec dict returned by build_listing_pack_v1 — this is the
        # exact same dict used to build the spec sheet PNG, so result page, HTML spec
        # sheet, and ZIP all read from a single source of truth.
        _persist_eq = (resolved_machine or {}).get("equipment_type", "").lower()
        _persist_rs = pack.get("enriched_specs") or dict(resolved_specs)

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
    except Exception:
        pass  # non-fatal — refinement just won't be offered for this session

    session_id = os.path.basename(session_dir)
    return JSONResponse({
        "success":      True,
        "result_url":   f"/build-listing/result/{session_id}",
        "spec_sheet_url": f"/build-listing/spec-sheet/{session_id}",
    })


# ─────────────────────────────────────────────────────────────────────────────
# /build-listing/verify — intermediate Verify Specs (Step 03 / 05) review page
# Sits between intake (POST /build-listing/verify) and final pack generation
# (POST /build-listing/generate/{session_id}). Photos are staged on disk in
# the session dir so they don't need to be re-uploaded by the verify form.
# ─────────────────────────────────────────────────────────────────────────────


def _verify_bool(v: str) -> bool:
    return str(v).lower() in ("true", "1", "on", "yes")


def _verify_tristatus(v: str) -> Optional[str]:
    s = str(v).lower().strip()
    if s in ("true", "1", "on", "yes"):    return "yes"
    if s in ("false", "0", "off", "no"):   return "no"
    if s == "optional":                    return "optional"
    return None


def _verify_build_dealer_input(d: dict) -> DealerInput:
    """Build DealerInput from a flat dict of form values.
    Mirrors the construction inside POST /build-listing — kept in sync."""
    asking_price_raw = (d.get("asking_price") or "").strip()
    price_int: Optional[int] = None
    if asking_price_raw:
        try:
            price_int = int(asking_price_raw.replace("$", "").replace(",", ""))
        except ValueError:
            raise HTTPException(status_code=422, detail="asking_price must be a number")

    cab_type_raw = d.get("cab_type")
    cab_type = ("enclosed" if cab_type_raw and cab_type_raw.strip().lower() == "true"
                else (cab_type_raw.strip() or None if cab_type_raw else None))

    control_type_raw = d.get("control_type")
    joystick = _verify_bool(d.get("joystick_controls", "false"))
    control_type = ((control_type_raw.strip() or None if control_type_raw else None)
                    or ("joystick" if joystick else None))

    coupler_raw = (d.get("coupler_type") or d.get("quick_attach") or "").strip().lower()
    coupler_type = coupler_raw if coupler_raw in {"hydraulic", "manual", "pin-on"} else None

    def _opt(key: str) -> Optional[str]:
        v = d.get(key)
        return v.strip() or None if isinstance(v, str) and v.strip() else None

    return DealerInput(
        year=int(d["year"]),
        make=str(d["make"]),
        model=str(d["model"]),
        hours=int(d["hours"]),
        asking_price=price_int,
        cab_type=cab_type,
        heater=_verify_bool(d.get("heater", "false")),
        ac=_verify_bool(d.get("ac", "false")),
        high_flow=_verify_tristatus(d.get("high_flow", "")),
        two_speed_travel=_verify_tristatus(d.get("two_speed", "")),
        ride_control=_verify_bool(d.get("ride_control", "false")),
        backup_camera=_verify_bool(d.get("backup_camera", "false")),
        radio=_verify_bool(d.get("radio", "false")),
        control_type=control_type,
        one_owner=_verify_bool(d.get("one_owner", "false")),
        thumb_type="hydraulic" if _verify_bool(d.get("thumb", "false")) else None,
        aux_hydraulics=_verify_bool(d.get("aux_hydraulics", "false")),
        blade_type="straight" if _verify_bool(d.get("blade", "false")) else None,
        zero_tail_swing=_verify_bool(d.get("zero_tail_swing", "false")),
        rubber_tracks=_verify_bool(d.get("rubber_tracks", "false")),
        coupler_type=coupler_type,
        tire_condition=_opt("tire_condition"),
        track_condition=_opt("track_condition"),
        track_percent_remaining=(int(d["track_percent_remaining"])
                                 if d.get("track_percent_remaining") is not None
                                 and str(d.get("track_percent_remaining")).strip() else None),
        attachments_included=_opt("attachments_included"),
        condition_notes=_opt("condition_notes"),
        condition_grade=_opt("condition_grade"),
        serial_number=_opt("serial_number"),
        stock_number=_opt("stock_number"),
        air_ride_seat=_verify_bool(d.get("air_ride_seat", "false")),
        self_leveling=_verify_bool(d.get("self_leveling", "false")),
        reversing_fan=_verify_bool(d.get("reversing_fan", "false")),
        bucket_included=_verify_bool(d.get("bucket_included", "false")),
        bucket_size=_opt("bucket_size"),
        warranty_status=_opt("warranty_status"),
    )


def _verify_resolve_specs(dealer_input: DealerInput):
    parsed = {
        "make":        dealer_input.make,
        "model":       dealer_input.model,
        "make_source": "explicit",
    }
    specs, confidence = safe_lookup_machine(parsed)
    full_record = specs.get("full_record") if specs else None
    resolved_machine = None
    resolved_specs: dict = {}
    if specs is not None:
        eq_type = (specs or {}).get("equipment_type", "").lower()
        is_ssl_or_ctl = eq_type in ("skid_steer", "compact_track_loader")
        modifiers = _structured_modifiers_from_flags({
            "high_flow": None if is_ssl_or_ctl else dealer_input.high_flow,
            "two_speed": None if is_ssl_or_ctl else dealer_input.two_speed_travel,
            "thumb": dealer_input.thumb_type,
        })
        resolved_machine = _run_spec_resolver(
            "", parsed, specs, confidence,
            parsed_year=dealer_input.year,
            detected_modifiers=modifiers,
        )
        if resolved_machine:
            resolved_specs = resolved_machine.get("resolved_specs") or {}
    else:
        resolved_machine = web_match_fallback(
            dealer_input.make, dealer_input.model, dealer_input.year,
        )
    return resolved_machine, resolved_specs, full_record, parsed


def _verify_decode_dealer_info(session_dir: str, dealer_profile_json: Optional[str]) -> Optional[dict]:
    if not dealer_profile_json:
        return None
    try:
        import base64 as _b64
        _dp = json.loads(dealer_profile_json)
        if not (isinstance(_dp, dict) and (_dp.get("companyName") or "").strip()):
            return None
        _logo_save_path: Optional[str] = None
        _logo_url = (_dp.get("logoDataUrl") or "").strip()
        if _logo_url.startswith("data:") and "base64," in _logo_url:
            _logo_bytes = _b64.b64decode(_logo_url.split("base64,", 1)[1])
            _uploads_dir = os.path.join(session_dir, "_uploads")
            os.makedirs(_uploads_dir, exist_ok=True)
            _logo_save_path = os.path.join(_uploads_dir, "dealer_logo.png")
            with open(_logo_save_path, "wb") as _lf:
                _lf.write(_logo_bytes)
        return {
            "dealer_name":  (_dp.get("companyName")  or "").strip() or None,
            "contact_name": (_dp.get("contactName")  or "").strip() or None,
            "phone":        (_dp.get("phone")        or "").strip() or None,
            "logo_path":    _logo_save_path,
            "accent_color": (_dp.get("accentColor") or "yellow"),
        }
    except Exception:
        return None


# Canonical spec key + alias mirrors. When the dealer overrides one of these,
# we mirror the value into every alias so downstream consumers (build_listing_text,
# build_spec_sheet_entries, build_use_case_payload) all see the override regardless
# of which key they read.
_VERIFY_SPEC_ALIASES: dict[str, list[str]] = {
    "engine_model":         ["engine_model"],
    "net_hp":               ["net_hp", "horsepower_hp"],
    "operating_weight_lb":  ["operating_weight_lb", "operating_weight_lbs"],
    "roc_lb":               ["roc_lb", "rated_operating_capacity_lbs"],
    "hydraulic_flow_gpm":   ["hydraulic_flow_gpm", "aux_flow_standard_gpm"],
    "track_width_in":       ["track_width_in", "width_over_tracks_in", "width_over_tires_in"],
}


def _verify_coerce_value(raw: str, type_hint: str):
    """Parse a dealer-edited value back to the type the spec field expects."""
    s = (raw or "").strip()
    if not s:
        return None
    if type_hint == "int":
        try:
            return int(s.replace(",", "").split(".")[0])
        except (ValueError, AttributeError):
            return None
    if type_hint == "float":
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return None
    return s


def _verify_apply_spec_overrides(resolved_specs: dict, spec_overrides_json: Optional[str]) -> dict:
    """Merge dealer spec overrides into a copy of resolved_specs (with alias mirrors).
    Returns the mutated dict and a normalized {key: value} audit dict."""
    if not spec_overrides_json:
        return {}
    try:
        payload = json.loads(spec_overrides_json)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    audit: dict = {}
    for key, entry in payload.items():
        if not isinstance(entry, dict):
            continue
        aliases = _VERIFY_SPEC_ALIASES.get(key, [key])
        coerced = _verify_coerce_value(entry.get("value", ""), entry.get("type", "string"))
        if coerced is None:
            continue
        for alias in aliases:
            resolved_specs[alias] = coerced
        audit[key] = coerced
    return audit


def _verify_patch_listing_text_best_for(listing_path: str, best_for_labels: list[str]) -> None:
    """Replace the 'Best For:' bullet block in listing_description.txt.
    No-op when the file has no Best For block (preserves existing layout)."""
    if not os.path.isfile(listing_path) or not best_for_labels:
        return
    try:
        with open(listing_path, "r", encoding="utf-8") as f:
            text = f.read()
        lines = text.split("\n")
        out: list[str] = []
        i = 0
        replaced = False
        while i < len(lines):
            ln = lines[i]
            if not replaced and ln.strip() == "Best For:":
                out.append("Best For:")
                for label in best_for_labels[:6]:
                    out.append(f"  • {label}")
                # Skip the original bullet lines (any line starting with "  •")
                j = i + 1
                while j < len(lines) and (lines[j].startswith("  •") or lines[j].startswith("  *")):
                    j += 1
                i = j
                replaced = True
                continue
            out.append(ln)
            i += 1
        if replaced:
            with open(listing_path, "w", encoding="utf-8") as f:
                f.write("\n".join(out))
    except Exception:
        pass


def _verify_safe_session_id(session_id: str) -> str:
    safe_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if not session_id or not all(c in safe_chars for c in session_id):
        raise HTTPException(status_code=400, detail="Invalid session id")
    return session_id


@app.post("/build-listing/verify")
async def build_listing_verify_create(
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
    condition_notes:      Optional[str]  = Form(None),
    condition_grade:      Optional[str]  = Form(None),
    serial_number:        Optional[str]  = Form(None),
    stock_number:         Optional[str]  = Form(None),
    track_percent_remaining: Optional[int] = Form(None),
    air_ride_seat:        str            = Form("false"),
    self_leveling:        str            = Form("false"),
    reversing_fan:        str            = Form("false"),
    bucket_included:      str            = Form("false"),
    bucket_size:          Optional[str]  = Form(None),
    warranty_status:      Optional[str]  = Form(None),
    dealer_profile_json:  Optional[str]  = Form(None),
    photos: List[UploadFile] = File(default=[]),
):
    """
    Stage intake → render Verify Specs (Step 03 / 05).

    Saves photos + dealer profile + intake snapshot to a session dir, runs
    registry lookup so OEM specs can be displayed for review, and returns
    {verify_url} pointing at the Verify Specs page. No pack is generated here.
    """
    form_values = {
        "year": year, "make": make, "model": model, "hours": hours,
        "cab_type": cab_type, "heater": heater, "ac": ac,
        "high_flow": high_flow, "two_speed": two_speed,
        "ride_control": ride_control, "backup_camera": backup_camera,
        "radio": radio, "control_type": control_type,
        "joystick_controls": joystick_controls, "one_owner": one_owner,
        "thumb": thumb, "aux_hydraulics": aux_hydraulics, "blade": blade,
        "zero_tail_swing": zero_tail_swing, "rubber_tracks": rubber_tracks,
        "quick_attach": quick_attach, "coupler_type": coupler_type,
        "tire_condition": tire_condition, "asking_price": asking_price,
        "track_condition": track_condition,
        "attachments_included": attachments_included,
        "condition_notes": condition_notes, "condition_grade": condition_grade,
        "serial_number": serial_number, "stock_number": stock_number,
        "track_percent_remaining": track_percent_remaining,
        "air_ride_seat": air_ride_seat, "self_leveling": self_leveling,
        "reversing_fan": reversing_fan, "bucket_included": bucket_included,
        "bucket_size": bucket_size, "warranty_status": warranty_status,
    }

    try:
        dealer_input = _verify_build_dealer_input(form_values)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    resolved_machine, resolved_specs, full_record, parsed = _verify_resolve_specs(dealer_input)

    session_dir, session_web = _make_session_dir(parsed)

    # Save photos to session staging dir
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
                pass

    dealer_info = _verify_decode_dealer_info(session_dir, dealer_profile_json)

    # Persist intake snapshot for the Verify GET + Generate POST round-trip.
    try:
        di_dict = dealer_input.model_dump()
        if dealer_profile_json:
            try:
                _dp = json.loads(dealer_profile_json)
                if isinstance(_dp, dict):
                    di_dict["dealer_profile"] = _dp
            except Exception:
                pass
        with open(os.path.join(session_dir, "dealer_input.json"), "w", encoding="utf-8") as f:
            json.dump(di_dict, f)
        with open(os.path.join(session_dir, "resolved_specs.json"), "w", encoding="utf-8") as f:
            json.dump(resolved_specs or {}, f)
        with open(os.path.join(session_dir, "ui_hints.json"), "w", encoding="utf-8") as f:
            json.dump((resolved_machine or {}).get("ui_hints") or {}, f)
        with open(os.path.join(session_dir, "verify_meta.json"), "w", encoding="utf-8") as f:
            json.dump({
                "equipment_type": (resolved_machine or {}).get("equipment_type"),
                "full_record_present": bool(full_record),
                "photo_filenames": [os.path.basename(p) for p in photo_paths],
                "dealer_info": {**dealer_info, "logo_path": None} if dealer_info else None,
            }, f)
    except Exception:
        pass

    session_id = os.path.basename(session_dir)
    return JSONResponse({
        "success":    True,
        "verify_url": f"/build-listing/verify/{session_id}",
    })


@app.get("/build-listing/verify/{session_id}", response_class=HTMLResponse)
async def build_listing_verify_view(request: Request, session_id: str):
    """Render the Verify Specs (Step 03 / 05) review page."""
    session_id = _verify_safe_session_id(session_id)
    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    def _read_json(name: str, default):
        path = os.path.join(session_dir, name)
        if not os.path.isfile(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    dealer_input_data = _read_json("dealer_input.json", {})
    resolved_specs    = _read_json("resolved_specs.json", {}) or {}
    verify_meta       = _read_json("verify_meta.json", {}) or {}

    equipment_type = (verify_meta.get("equipment_type") or "").lower()
    eq_label = _EQ_TYPE_LABELS.get(equipment_type, "Equipment")
    eq_code_map = {
        "compact_track_loader": "CTL",
        "skid_steer":           "SSL",
        "mini_excavator":       "MEX",
        "excavator":            "EXC",
        "wheel_loader":         "WL",
        "backhoe_loader":       "BHL",
        "telehandler":          "TH",
        "dozer":                "DZR",
        "scissor_lift":         "SL",
        "boom_lift":            "BL",
    }
    eq_code = eq_code_map.get(equipment_type, "MTM")

    # Hero photo URL — first staged photo if any
    hero_photo_url = ""
    photo_filenames = verify_meta.get("photo_filenames") or []
    if photo_filenames:
        hero_photo_url = f"/outputs/{session_id}/_uploads/{photo_filenames[0]}"

    # Dealer Identity prefill (block C1 — DEALER)
    _dp_pref = (dealer_input_data.get("dealer_profile") or {}) if isinstance(dealer_input_data, dict) else {}
    dealer_company = (_dp_pref.get("companyName")  or "").strip()
    dealer_contact = (_dp_pref.get("contactName")  or "").strip()
    dealer_phone   = (_dp_pref.get("phone")        or "").strip()
    _logo_disk_path = os.path.join(session_dir, "_uploads", "dealer_logo.png")
    dealer_logo_url = (
        f"/outputs/{session_id}/_uploads/dealer_logo.png"
        if os.path.isfile(_logo_disk_path) else ""
    )

    def _fmt_int(v) -> str:
        try:
            return f"{int(v):,}"
        except (TypeError, ValueError):
            return ""

    def _fmt_dec(v, places: int = 1) -> str:
        try:
            f = float(v)
            return f"{f:.{places}f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            return ""

    # OEM spec card payloads (A1–A6) sourced from resolved_specs
    engine_model_val   = (resolved_specs.get("engine_model")
                          or resolved_specs.get("engine_manufacturer")
                          or "OEM Data Pending")
    displacement_l     = resolved_specs.get("displacement_l")
    emissions_tier     = resolved_specs.get("emissions_tier") or ""
    fuel_type          = resolved_specs.get("fuel_type") or "Diesel"
    engine_sub_bits = []
    if displacement_l:
        engine_sub_bits.append(f"{_fmt_dec(displacement_l)}L")
    if emissions_tier:
        engine_sub_bits.append(str(emissions_tier))
    engine_sub_bits.append(fuel_type)
    engine_sub = " · ".join(b for b in engine_sub_bits if b) or "Engine details"

    hp_val = (resolved_specs.get("net_hp")
              or resolved_specs.get("horsepower_hp")
              or resolved_specs.get("gross_hp")
              or resolved_specs.get("horsepower_gross_hp"))
    hp_str = _fmt_int(hp_val) or "—"

    op_wt_val = resolved_specs.get("operating_weight_lb") or resolved_specs.get("operating_weight_lbs")
    op_wt_str = _fmt_int(op_wt_val) or "—"

    roc_val = resolved_specs.get("roc_lb") or resolved_specs.get("rated_operating_capacity_lbs")
    roc_str = _fmt_int(roc_val) or "—"

    aux_val = (resolved_specs.get("hydraulic_flow_gpm")
               or resolved_specs.get("aux_flow_standard_gpm"))
    aux_str = _fmt_dec(aux_val) or "—"

    track_w_val = (resolved_specs.get("track_width_in")
                   or resolved_specs.get("width_over_tracks_in")
                   or resolved_specs.get("width_over_tires_in"))
    track_w_str = _fmt_dec(track_w_val) or "—"

    # B-section seller inputs from staged dealer_input.
    # Hours staged as 0 from the homepage intake bootstrap renders as empty
    # so the input shows its placeholder instead of a literal "0". Real values
    # entered by the dealer (>0) format normally.
    _hours_raw = dealer_input_data.get("hours")
    try:
        _hours_int = int(_hours_raw) if _hours_raw is not None else 0
    except (TypeError, ValueError):
        _hours_int = 0
    hours_str = _fmt_int(_hours_raw) if _hours_int > 0 else ""
    track_pct = dealer_input_data.get("track_percent_remaining")
    track_pct_str = (f"{int(track_pct)}%" if isinstance(track_pct, (int, float)) and track_pct else "")
    grade_val = dealer_input_data.get("condition_grade") or "Like New"

    # Summary strip values
    year  = dealer_input_data.get("year") or ""
    make  = (dealer_input_data.get("make") or "").upper()
    model = dealer_input_data.get("model") or ""
    machine_label = f"{make} {model}".strip() or "Machine"
    asking_price = dealer_input_data.get("asking_price")
    price_str = f"${_fmt_int(asking_price)}" if asking_price else "—"
    stock_no = dealer_input_data.get("stock_number") or "—"

    # Pre-selection state for chips, derived from staged dealer_input
    def _b(k: str) -> bool:
        return bool(dealer_input_data.get(k))

    cab_t = (dealer_input_data.get("cab_type") or "")
    enclosed_cab = (cab_t.lower() == "enclosed") if isinstance(cab_t, str) else False
    high_flow_on = dealer_input_data.get("high_flow") == "yes"
    two_speed_on = dealer_input_data.get("two_speed_travel") == "yes"

    preselected = {
        "high_flow":     high_flow_on,
        "enclosed_cab":  enclosed_cab,
        "heat_ac":       _b("heater") or _b("ac"),
        "two_speed":     two_speed_on,
        "ride_control":  _b("ride_control"),
        "quick_attach":  bool((dealer_input_data.get("coupler_type") or "").strip()),
        "self_leveling": _b("self_leveling"),
        "backup_camera": _b("backup_camera"),
    }

    # Attachments (text → list)
    att_raw = (dealer_input_data.get("attachments_included") or "").strip()
    att_preselected = [a.strip() for a in att_raw.split(",") if a.strip()] or ["Bucket"]

    # Best For — dealer override takes priority, else run the same use-case
    # scorer used by /generate and the result page so chips match downstream.
    best_for_labels: list[str] = []
    _bf_override_path = os.path.join(session_dir, "best_for_override.json")
    if os.path.isfile(_bf_override_path):
        try:
            with open(_bf_override_path, encoding="utf-8") as f:
                best_for_labels = [
                    str(x).strip() for x in (json.load(f) or {}).get("best_for") or []
                    if str(x).strip()
                ]
        except Exception:
            best_for_labels = []
    if not best_for_labels and dealer_input_data:
        try:
            _di_obj = DealerInput(**{
                k: v for k, v in dealer_input_data.items() if k != "dealer_profile"
            })
            _uc_pay = build_use_case_payload(equipment_type, _di_obj, resolved_specs)
            best_for_labels = [
                it.get("label", "") for it in (build_use_case_ui_items(_uc_pay) or [])
                if it.get("label")
            ]
        except Exception:
            best_for_labels = []
    best_for_labels = best_for_labels[:6]

    # Headline — server-generated. Prefer saved title_override.json,
    # else compute via build_headline using session DealerInput + use-case payload.
    # Falls through to "" so the template can keep its client-side fallback.
    headline: str = ""
    _title_override_path = os.path.join(session_dir, "title_override.json")
    if os.path.isfile(_title_override_path):
        try:
            with open(_title_override_path, encoding="utf-8") as f:
                headline = ((json.load(f) or {}).get("title") or "").strip()
        except Exception:
            headline = ""
    if not headline and dealer_input_data:
        try:
            from listing_builder import build_headline as _build_headline
            _di_obj_h = DealerInput(**{
                k: v for k, v in dealer_input_data.items() if k != "dealer_profile"
            })
            _uc_pay_h = build_use_case_payload(equipment_type, _di_obj_h, resolved_specs)
            headline = (_build_headline(_di_obj_h, _uc_pay_h) or "").strip()
        except Exception:
            headline = ""

    ctx = {
        "request":        request,
        "session_id":     session_id,
        "year":           year,
        "make":           make,
        "model":          model,
        "machine_label":  machine_label,
        "equipment_type": equipment_type,
        "eq_label":       eq_label,
        "eq_code":        eq_code,
        "hours_str":      hours_str,
        "price_str":      price_str,
        "stock_no":       stock_no,
        "track_pct_str":  track_pct_str,
        "grade_val":      grade_val,
        "hero_photo_url": hero_photo_url,
        "engine_model":   engine_model_val,
        "engine_sub":     engine_sub,
        "hp_str":         hp_str,
        "op_wt_str":      op_wt_str,
        "roc_str":        roc_str,
        "aux_str":        aux_str,
        "track_w_str":    track_w_str,
        "preselected":    preselected,
        "att_preselected": att_preselected,
        "best_for":       best_for_labels,
        "headline":       headline,
        "dealer_company": dealer_company,
        "dealer_contact": dealer_contact,
        "dealer_phone":   dealer_phone,
        "dealer_logo_url": dealer_logo_url,
    }
    return templates.TemplateResponse("verify_specs.html", ctx)


def _verify_uploads_dir(session_id: str) -> str:
    session_id = _verify_safe_session_id(session_id)
    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")
    uploads_dir = os.path.join(session_dir, "_uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    return uploads_dir


def _verify_list_photos(uploads_dir: str) -> list[str]:
    if not os.path.isdir(uploads_dir):
        return []
    out = []
    for name in sorted(os.listdir(uploads_dir)):
        if name == "dealer_logo.png":
            continue
        if os.path.isfile(os.path.join(uploads_dir, name)):
            out.append(name)
    return out


@app.get("/build-listing/verify/{session_id}/photos")
async def build_listing_verify_photos_list(session_id: str):
    """List photos currently staged for a verify session (drives the thumb grid)."""
    uploads_dir = _verify_uploads_dir(session_id)
    return JSONResponse({"photos": _verify_list_photos(uploads_dir)})


@app.post("/build-listing/verify/{session_id}/photos")
async def build_listing_verify_photos_upload(
    session_id: str,
    photos: List[UploadFile] = File(default=[]),
):
    """
    Accept additional photos for a verify session and stage them in the
    session's _uploads/ dir. /generate already reads from that dir, so no
    pipeline change is needed — these photos flow into the pack on submit.
    """
    uploads_dir = _verify_uploads_dir(session_id)
    for upload in photos or []:
        if not upload.filename:
            continue
        safe_name = "".join(
            c for c in upload.filename if c.isalnum() or c in "._- "
        ).strip() or f"photo_{uuid.uuid4().hex[:6]}.jpg"
        # Avoid clobbering an existing file with the same name
        dest = os.path.join(uploads_dir, safe_name)
        if os.path.exists(dest):
            stem, ext = os.path.splitext(safe_name)
            safe_name = f"{stem}_{uuid.uuid4().hex[:4]}{ext}"
            dest = os.path.join(uploads_dir, safe_name)
        try:
            content = await upload.read()
            with open(dest, "wb") as f:
                f.write(content)
        except Exception:
            continue
    return JSONResponse({"photos": _verify_list_photos(uploads_dir)})


@app.get("/build-listing/verify/{session_id}/dealer")
async def build_listing_verify_dealer_get(session_id: str):
    """Return the staged dealer identity (company / contact / phone) and
    whether a session-scoped dealer logo has been uploaded. Drives the
    Dealer Identity block prefill on the Verify Specs page."""
    session_id = _verify_safe_session_id(session_id)
    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    di_path = os.path.join(session_dir, "dealer_input.json")
    profile: dict = {}
    if os.path.isfile(di_path):
        try:
            with open(di_path, "r", encoding="utf-8") as f:
                _di = json.load(f) or {}
            _dp = (_di or {}).get("dealer_profile") or {}
            if isinstance(_dp, dict):
                profile = _dp
        except Exception:
            profile = {}

    logo_path = os.path.join(session_dir, "_uploads", "dealer_logo.png")
    logo_url = (
        f"/outputs/{session_id}/_uploads/dealer_logo.png"
        if os.path.isfile(logo_path) else ""
    )
    return JSONResponse({
        "company_name":  (profile.get("companyName")  or "").strip(),
        "contact_name":  (profile.get("contactName")  or "").strip(),
        "contact_phone": (profile.get("phone")        or "").strip(),
        "logo_url":      logo_url,
    })


@app.post("/build-listing/verify/{session_id}/dealer")
async def build_listing_verify_dealer_save(
    session_id:    str,
    company_name:  Optional[str]      = Form(None),
    contact_name:  Optional[str]      = Form(None),
    contact_phone: Optional[str]      = Form(None),
    dealer_logo:   Optional[UploadFile] = File(None),
):
    """Persist dealer identity into the session's dealer_input.json (under the
    dealer_profile sub-dict) and optionally save an uploaded logo to
    _uploads/dealer_logo.png. Generate already reads dealer_profile from
    dealer_input.json, so no pipeline change is needed."""
    session_id = _verify_safe_session_id(session_id)
    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    uploads_dir = os.path.join(session_dir, "_uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    logo_dest = os.path.join(uploads_dir, "dealer_logo.png")

    if dealer_logo and dealer_logo.filename:
        ext = os.path.splitext(dealer_logo.filename)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            raise HTTPException(status_code=415, detail="Logo must be PNG, JPG, or WebP")
        try:
            content = await dealer_logo.read()
            with open(logo_dest, "wb") as f:
                f.write(content)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Logo save failed: {exc}")

    di_path = os.path.join(session_dir, "dealer_input.json")
    di_dict: dict = {}
    if os.path.isfile(di_path):
        try:
            with open(di_path, "r", encoding="utf-8") as f:
                di_dict = json.load(f) or {}
        except Exception:
            di_dict = {}

    profile = dict(di_dict.get("dealer_profile") or {})
    if company_name is not None:
        profile["companyName"] = (company_name or "").strip()
    if contact_name is not None:
        profile["contactName"] = (contact_name or "").strip()
    if contact_phone is not None:
        profile["phone"] = (contact_phone or "").strip()
    di_dict["dealer_profile"] = profile

    try:
        with open(di_path, "w", encoding="utf-8") as f:
            json.dump(di_dict, f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Persist failed: {exc}")

    logo_url = (
        f"/outputs/{session_id}/_uploads/dealer_logo.png"
        if os.path.isfile(logo_dest) else ""
    )
    return JSONResponse({
        "success":       True,
        "company_name":  profile.get("companyName", ""),
        "contact_name":  profile.get("contactName", ""),
        "contact_phone": profile.get("phone", ""),
        "logo_url":      logo_url,
    })


@app.post("/build-listing/generate/{session_id}")
async def build_listing_generate(
    session_id:           str,
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
    condition_notes:      Optional[str]  = Form(None),
    condition_grade:      Optional[str]  = Form(None),
    serial_number:        Optional[str]  = Form(None),
    stock_number:         Optional[str]  = Form(None),
    track_percent_remaining: Optional[int] = Form(None),
    air_ride_seat:        str            = Form("false"),
    self_leveling:        str            = Form("false"),
    reversing_fan:        str            = Form("false"),
    bucket_included:      str            = Form("false"),
    bucket_size:          Optional[str]  = Form(None),
    warranty_status:      Optional[str]  = Form(None),
    # Verify-page overrides (session-scoped; never write back to registry)
    spec_overrides_json:  Optional[str]  = Form(None),
    best_for_override:    Optional[str]  = Form(None),
    headline_override:    Optional[str]  = Form(None),
):
    """
    Generate the listing pack for a Verify-staged session.

    Reuses photos/dealer-profile already on disk in session_dir; runs the same
    registry-lookup + spec-resolver + listing_pack_builder pipeline as the
    legacy POST /build-listing endpoint (no schema, API, or output changes).
    """
    session_id = _verify_safe_session_id(session_id)
    session_dir = os.path.join(_OUTPUTS_DIR, session_id)
    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")
    session_web = f"/outputs/{session_id}"

    form_values = {
        "year": year, "make": make, "model": model, "hours": hours,
        "cab_type": cab_type, "heater": heater, "ac": ac,
        "high_flow": high_flow, "two_speed": two_speed,
        "ride_control": ride_control, "backup_camera": backup_camera,
        "radio": radio, "control_type": control_type,
        "joystick_controls": joystick_controls, "one_owner": one_owner,
        "thumb": thumb, "aux_hydraulics": aux_hydraulics, "blade": blade,
        "zero_tail_swing": zero_tail_swing, "rubber_tracks": rubber_tracks,
        "quick_attach": quick_attach, "coupler_type": coupler_type,
        "tire_condition": tire_condition, "asking_price": asking_price,
        "track_condition": track_condition,
        "attachments_included": attachments_included,
        "condition_notes": condition_notes, "condition_grade": condition_grade,
        "serial_number": serial_number, "stock_number": stock_number,
        "track_percent_remaining": track_percent_remaining,
        "air_ride_seat": air_ride_seat, "self_leveling": self_leveling,
        "reversing_fan": reversing_fan, "bucket_included": bucket_included,
        "bucket_size": bucket_size, "warranty_status": warranty_status,
    }

    try:
        dealer_input = _verify_build_dealer_input(form_values)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    resolved_machine, resolved_specs, full_record, _parsed = _verify_resolve_specs(dealer_input)

    # Apply dealer-supplied OEM spec overrides (package-scoped only).
    spec_override_audit = _verify_apply_spec_overrides(resolved_specs, spec_overrides_json)

    # Parse Best For override (if any)
    best_for_labels: list[str] = []
    if best_for_override:
        try:
            _bf = json.loads(best_for_override)
            if isinstance(_bf, list):
                best_for_labels = [str(x).strip() for x in _bf if str(x).strip()]
        except Exception:
            best_for_labels = []

    headline_override_clean = (headline_override or "").strip()

    # Persist override audit + best_for + title overrides BEFORE pack build so
    # the result page can read them even if pack assembly partially fails.
    try:
        if spec_override_audit or best_for_labels or headline_override_clean:
            with open(os.path.join(session_dir, "verify_overrides.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "spec_overrides": spec_override_audit,
                    "best_for":       best_for_labels,
                    "headline":       headline_override_clean,
                }, f)
        if best_for_labels:
            with open(os.path.join(session_dir, "best_for_override.json"), "w", encoding="utf-8") as f:
                json.dump({"best_for": best_for_labels}, f)
        else:
            _bf_path = os.path.join(session_dir, "best_for_override.json")
            if os.path.isfile(_bf_path):
                os.remove(_bf_path)
        if headline_override_clean:
            with open(os.path.join(session_dir, "title_override.json"), "w", encoding="utf-8") as f:
                json.dump({"title": headline_override_clean}, f)
        else:
            _t_path = os.path.join(session_dir, "title_override.json")
            if os.path.isfile(_t_path):
                os.remove(_t_path)
    except Exception:
        pass

    # Load photos from staged uploads dir
    staging_dir = os.path.join(session_dir, "_uploads")
    photo_paths: list[str] = []
    if os.path.isdir(staging_dir):
        for name in sorted(os.listdir(staging_dir)):
            if name == "dealer_logo.png":
                continue
            full = os.path.join(staging_dir, name)
            if os.path.isfile(full):
                photo_paths.append(full)

    # Re-hydrate dealer_info from the staged dealer_input.json (logo path on disk)
    dealer_info: Optional[dict] = None
    di_path = os.path.join(session_dir, "dealer_input.json")
    if os.path.isfile(di_path):
        try:
            with open(di_path, "r", encoding="utf-8") as f:
                _di = json.load(f)
            _dp = (_di or {}).get("dealer_profile") or {}
            if isinstance(_dp, dict) and (_dp.get("companyName") or "").strip():
                _logo_path = os.path.join(staging_dir, "dealer_logo.png")
                dealer_info = {
                    "dealer_name":  (_dp.get("companyName")  or "").strip() or None,
                    "contact_name": (_dp.get("contactName")  or "").strip() or None,
                    "phone":        (_dp.get("phone")        or "").strip() or None,
                    "logo_path":    _logo_path if os.path.isfile(_logo_path) else None,
                    "accent_color": (_dp.get("accentColor") or "yellow"),
                }
        except Exception:
            pass

    try:
        pack = build_listing_pack_v1(
            dealer_input=dealer_input,
            resolved_specs=resolved_specs,
            resolved_machine=resolved_machine,
            image_input_paths=photo_paths,
            dealer_info=dealer_info,
            session_dir=session_dir,
            session_web=session_web,
            full_record=full_record,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pack generation error: {exc}")

    if not pack.get("success") or not pack.get("zip_path"):
        raise HTTPException(status_code=500, detail="Pack generation failed")

    # ── Apply post-build text overrides (Best For + Headline) ────────────────
    # Both write to listing_description.txt inside the pack so the ZIP, the
    # result page, and any downstream consumer all see the dealer's edits.
    listing_txt_path = os.path.join(session_dir, "listing_output", "listing_description.txt")
    if best_for_labels:
        _verify_patch_listing_text_best_for(listing_txt_path, best_for_labels)
    if headline_override_clean and os.path.isfile(listing_txt_path):
        try:
            with open(listing_txt_path, "r", encoding="utf-8") as f:
                _existing = f.read()
            with open(listing_txt_path, "w", encoding="utf-8") as f:
                f.write(_apply_title_override(_existing, headline_override_clean))
        except Exception:
            pass

    # Rebuild the pack ZIP so it captures the post-build text overrides.
    # build_listing_pack_v1 writes the ZIP before the route patches Best For /
    # headline into listing_description.txt, which left the ZIP stale.
    if best_for_labels or headline_override_clean:
        try:
            from listing_pack_builder import _zip_folder as _rezip
            pack_dir = os.path.join(session_dir, "listing_output")
            zip_path = os.path.join(session_dir, "listing_output.zip")
            if os.path.isdir(pack_dir):
                _rezip(pack_dir, zip_path)
        except Exception:
            pass

    # Re-persist with edited values + enriched specs (overwrites verify-stage snapshot).
    try:
        di_dict = dealer_input.model_dump()
        # Preserve dealer_profile snapshot from the original verify stage.
        if os.path.isfile(di_path):
            try:
                with open(di_path, "r", encoding="utf-8") as f:
                    _prev = json.load(f)
                if isinstance(_prev, dict) and "dealer_profile" in _prev:
                    di_dict["dealer_profile"] = _prev["dealer_profile"]
            except Exception:
                pass
        with open(di_path, "w", encoding="utf-8") as f:
            json.dump(di_dict, f)

        _persist_eq = (resolved_machine or {}).get("equipment_type", "").lower()
        _persist_rs = pack.get("enriched_specs") or dict(resolved_specs)
        with open(os.path.join(session_dir, "resolved_specs.json"), "w", encoding="utf-8") as f:
            json.dump(_persist_rs, f)

        ui_hints = dict((resolved_machine or {}).get("ui_hints") or {})
        if _persist_eq in ("skid_steer", "compact_track_loader"):
            ui_hints.pop("_displayHiFlow",    None)
            ui_hints.pop("_detectedTwoSpeed", None)
        with open(os.path.join(session_dir, "ui_hints.json"), "w", encoding="utf-8") as f:
            json.dump(ui_hints, f)
    except Exception:
        pass

    return JSONResponse({
        "success":        True,
        "result_url":     f"/build-listing/result/{session_id}",
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

    equipment_type = ""
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            equipment_type = json.load(f).get("equipment_type") or ""

    dealer_contact: dict = {}
    if os.path.isfile(dc_path):
        with open(dc_path, encoding="utf-8") as f:
            dealer_contact = json.load(f)

    # Dealer info: accent_color/logo_path stored in dealer_profile sub-dict of dealer_input.json
    dealer_info: dict = di_data.get("dealer_profile") or {}

    # Scan session _uploads/ for machine photos to embed in the spec sheet
    _photo_paths: list[str] = []
    _uploads_dir = os.path.join(session_dir, "_uploads")
    if os.path.isdir(_uploads_dir):
        _supported = {".jpg", ".jpeg", ".png", ".webp"}
        for _fname in sorted(os.listdir(_uploads_dir)):
            if os.path.splitext(_fname)[1].lower() in _supported:
                _photo_paths.append(os.path.join(_uploads_dir, _fname))

    data = _build_ss_data(
        dealer_input_data=di_data,
        enriched_resolved_specs=rs_data,
        equipment_type=equipment_type,
        dealer_contact=dealer_contact,
        dealer_info=dealer_info,
        full_record={},
        photo_path=_photo_paths[0] if _photo_paths else None,
    )
    return HTMLResponse(_render_spec_sheet(data))


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
    condition_grade:      Optional[str] = Form(None),
    # CTL core output fields (locked standard 2026-04-10)
    serial_number:        Optional[str] = Form(None),
    stock_number:         Optional[str] = Form(None),
    track_percent_remaining: Optional[int] = Form(None),
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
            track_percent_remaining=track_percent_remaining,
            attachments_included=attachments_included.strip() or None if attachments_included else None,
            condition_notes=condition_notes.strip() or None if condition_notes else None,
            condition_grade=condition_grade.strip() or None if condition_grade else None,
            serial_number=serial_number.strip() or None if serial_number else None,
            stock_number=stock_number.strip() or None if stock_number else None,
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


# ── DEMO mode (dev scaffolding — remove by deleting demo_route.py + this block) ──
from demo_route import router as demo_router  # noqa: E402
app.include_router(demo_router)
