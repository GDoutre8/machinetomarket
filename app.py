"""
app.py — Machine-to-Market: Fix My Listing
FastAPI entry point. All business logic lives in mtm_service.py.
"""

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
import os
import shutil
import uuid

from mtm_service import (
    fix_listing_service,
    safe_parse_listing,
    safe_lookup_machine,
    _run_spec_resolver,
    _stub_build_listing_data,
    _stub_generate_listing_text,
    _make_session_dir,
    _asset_url,
    _build_scorer_input,
    build_spec_sheet_entries,
    build_confirm_required,
    build_rewritten_listing,
)
from mtm_scorer import score as _score_listing, build_fix_my_listing
from listing_pack_builder import build_listing_pack
from dealer_input import DealerInput  # noqa: F401 — imported here for API layer access

app = FastAPI(title="Machine-to-Market: Fix My Listing", docs_url=None, redoc_url=None)

# Use absolute paths so uvicorn always serves the correct files
# regardless of the working directory it is launched from
_BASE = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=os.path.join(_BASE, "static")), name="static")

_OUTPUTS_DIR = os.path.join(_BASE, "outputs")
os.makedirs(_OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=_OUTPUTS_DIR), name="outputs")
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))


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
        resolved_machine = _run_spec_resolver(raw, parsed, specs, confidence)

    listing_data    = _stub_build_listing_data(parsed, resolved_machine)
    listing_text    = _stub_generate_listing_text(listing_data, resolved_machine, spec_level)

    # ── Spec sheet entries ────────────────────────────────────────────────────
    spec_entries: list[tuple[str, str]] = []
    if generate_spec_sheet_flag and resolved_machine and resolved_machine.get("resolved_specs"):
        spec_entries = build_spec_sheet_entries(
            resolved_specs = resolved_machine["resolved_specs"],
            ui_hints       = resolved_machine.get("ui_hints") or {},
            equipment_type = parsed.get("equipment_type") or "",
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
