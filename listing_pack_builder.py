"""
listing_pack_builder.py
=======================
MTM Listing Pack Assembly

Combines cleaned listing text, spec sheet PNG, resized image pack, and
optional walkaround video into one downloadable ZIP.

Output structure:
    {session_dir}/listing_output/
        START_HERE.txt
        listing_description.txt
        Listing_Photos/
        Original_Photos/
        spec_sheet/
            machine_spec_sheet.png
        metadata_internal.json
        walkaround.mp4   (only if generated or provided)
    {session_dir}/listing_output.zip

Priority order (graceful fallback):
    1. listing_description.txt — always attempted
    2. spec sheet PNG   — skipped if no resolved specs
    3. image pack       — skipped if no photos
    4. walkaround video — last; failure never blocks ZIP

Usage:
    from listing_pack_builder import build_listing_pack
    result = build_listing_pack(...)
"""

from __future__ import annotations
import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from spec_sheet_context    import screenshot_spec_sheet
from image_pack_generator  import generate_image_pack, SUPPORTED_EXTENSIONS
from walkaround_generator  import generate_walkaround_video
from dealer_input          import DealerInput
from listing_builder              import build_listing_text
from listing_use_case_enrichment  import build_use_case_payload

_OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


# ─────────────────────────────────────────────────────────────────────────────
# Photo framing classifier
# ─────────────────────────────────────────────────────────────────────────────

def classify_photo_framing(image_path: str) -> dict:
    """
    V1 photo framing classifier.

    Classifies each source photo before processing so metadata can flag
    images that may look cropped or unprofessional on listing platforms.

    Returns
    -------
    dict with keys:
        filename       : str  — basename of the file
        classification : str  — "too_close_cropped" | "usable_but_tight" | "good"
        reason         : str  — short human-readable explanation

    Heuristics (V1, PIL-only, no numpy required)
    --------------------------------------------
    Rule 1 — Edge contact:
        Sample an 8-px border strip on each side.  If the strip std dev is
        > 22 (i.e. non-uniform, indicating subject content rather than plain
        sky / ground), that edge is "active."  Three or more active edges
        → the machine is touching the frame on multiple sides → too_close_cropped.

    Rule 2 — Frame fill:
        Downsample to 24×24, estimate background brightness from the four
        corners, then count pixels that diverge from background by > 35 DN.
        fill_ratio > 0.80  → too_close_cropped
        fill_ratio > 0.60 (or ≥ 1 active edge) → usable_but_tight
        otherwise          → good

    Failure is silent: any PIL or IO error returns classification="good" so
    the image pack pipeline is never blocked by the classifier.
    """
    from PIL import Image, ImageStat  # PIL is already a hard dependency

    filename = os.path.basename(image_path)
    try:
        img  = Image.open(image_path).convert("RGB")
        w, h = img.size
        gray = img.convert("L")

        EDGE_MARGIN    = 8    # px strip sampled from each border
        EDGE_THRESHOLD = 22   # stddev above which a strip is "active" (non-background)

        # ── Rule 1: edge contact ──────────────────────────────────────────────
        strips = [
            gray.crop((0,              0,              w,              EDGE_MARGIN)),  # top
            gray.crop((0,              h - EDGE_MARGIN, w,             h)),            # bottom
            gray.crop((0,              0,              EDGE_MARGIN,    h)),            # left
            gray.crop((w - EDGE_MARGIN, 0,             w,              h)),            # right
        ]
        active_edges = sum(1 for s in strips if ImageStat.Stat(s).stddev[0] > EDGE_THRESHOLD)

        if active_edges >= 3:
            return {
                "filename":       filename,
                "classification": "too_close_cropped",
                "reason":         f"subject_touches_border ({active_edges}/4 edges active)",
            }

        # ── Rule 2: frame fill via corner-relative background separation ──────
        SZ = 24
        small   = gray.resize((SZ, SZ), Image.LANCZOS)
        pixels  = list(small.getdata())
        corners = [pixels[0], pixels[SZ - 1], pixels[SZ * (SZ - 1)], pixels[SZ * SZ - 1]]
        bg      = sum(corners) / len(corners)
        non_bg  = sum(1 for p in pixels if abs(p - bg) > 35)
        fill    = non_bg / len(pixels)

        if fill > 0.80:
            return {
                "filename":       filename,
                "classification": "too_close_cropped",
                "reason":         f"subject_fills_frame ({fill:.0%} non-background)",
            }
        if fill > 0.60 or active_edges >= 1:
            return {
                "filename":       filename,
                "classification": "usable_but_tight",
                "reason":         f"moderate_fill ({fill:.0%} non-background, {active_edges}/4 edges active)",
            }
        return {
            "filename":       filename,
            "classification": "good",
            "reason":         f"well_framed ({fill:.0%} non-background)",
        }

    except Exception as exc:  # never block image pipeline
        return {
            "filename":       filename,
            "classification": "good",
            "reason":         f"classifier_error: {exc}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_machine_name(make: str, model: str) -> str:
    raw = f"{make}_{model}".replace(" ", "_")
    return "".join(c for c in raw if c.isalnum() or c in "_-")[:40] or "machine"


def _renumber_listing_photos(listing_dir: Path, machine_name: str) -> None:
    """
    Shift all {machine_name}_NN_listing.* files up by 1 index (01→02, 02→03, …)
    so position 01 is free for the card PNG. Renames in reverse index order to
    avoid collision when two files would otherwise share the same target name.
    """
    pattern = re.compile(
        rf"^{re.escape(machine_name)}_(\d+)_listing(\.[^.]+)$",
        re.IGNORECASE,
    )
    photos = sorted(
        [p for p in listing_dir.iterdir() if p.is_file() and pattern.match(p.name)],
        key=lambda p: p.name,
        reverse=True,  # highest index first to avoid collisions
    )
    for photo in photos:
        m = pattern.match(photo.name)
        if not m:
            continue
        new_idx = int(m.group(1)) + 1
        new_name = f"{machine_name}_{new_idx:02d}_listing{m.group(2)}"
        photo.rename(listing_dir / new_name)


# Desired top-level entry order in the ZIP (lower index = earlier)
# Files written to pack_dir for server-side use but excluded from the user ZIP
_ZIP_EXCLUDE = {"metadata_internal.json"}

_ZIP_ORDER = [
    "START_HERE.txt",
    "listing_description.txt",
    "Listing_Photos",
    "Original_Photos",
    "spec_sheet",
    "walkaround.mp4",
]


def _zip_sort_key(rel_path: Path) -> tuple:
    """Sort key that places top-level entries in _ZIP_ORDER, rest alphabetically."""
    top = rel_path.parts[1] if len(rel_path.parts) > 1 else rel_path.parts[0]
    try:
        pos = _ZIP_ORDER.index(top)
    except ValueError:
        pos = len(_ZIP_ORDER)
    return (pos, str(rel_path))


def _zip_folder(folder_path: str, zip_path: str) -> int:
    root = Path(folder_path)
    files = sorted(
        (fp for fp in root.rglob("*") if fp.is_file() and fp.name not in _ZIP_EXCLUDE),
        key=lambda fp: _zip_sort_key(fp.relative_to(root.parent)),
    )
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fp in files:
            zf.write(fp, fp.relative_to(root.parent))
    return os.path.getsize(zip_path)


def _fmt_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    return f"{n / 1_000:.0f} KB"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_listing_pack(
    raw_text: str,
    parsed_listing: dict,
    resolved_machine: "dict | None",
    generated_listing_text: str,
    spec_sheet_entries: "list[tuple[str, str]]",
    image_input_paths: "list[str]",
    dealer_info: "dict | None" = None,
    # Walkaround — two independent modes:
    generate_walkaround: bool = False,          # generate from photos via ffmpeg
    walkaround_video_path: "str | None" = None, # pass a pre-existing .mp4 to copy in
    session_dir: str = "",
    session_web: str = "",
    use_case_payload: "dict | None" = None,
    # Listing card PNG (card_renderer_adapter)
    full_record: "dict | None" = None,
    card_dealer_data: "dict | None" = None,
    # New spec sheet export (single source of truth)
    dealer_input_dump: "dict | None" = None,
    enriched_resolved_specs: "dict | None" = None,
) -> dict:
    """
    Assemble one complete MTM listing pack from pre-processed components.

    Parameters
    ----------
    raw_text               : Original listing text.
    parsed_listing         : Output of safe_parse_listing().
    resolved_machine       : Output of _run_spec_resolver(), or None.
    generated_listing_text : Cleaned formatted listing string.
    spec_sheet_entries     : [(label, value)] tuples for spec sheet PNG.
    image_input_paths      : Absolute paths to source photos.
    dealer_info            : Dict with dealer_name / phone / email / location.
    generate_walkaround    : If True, generate walkaround.mp4 from photos.
    walkaround_video_path  : Pre-existing video to copy in (ignores generate_walkaround).
    session_dir            : Per-request session directory (absolute path).
    session_web            : Web URL prefix for session_dir.

    Returns
    -------
    dict:
        success          bool
        machine_match    str
        spec_count       int
        output_folder    str
        zip_path         str | None
        zip_web_url      str | None
        zip_size_bytes   int
        outputs          dict  — per-asset absolute paths (None if not generated)
        walkaround       dict  — {requested, included, status, path}
        warnings         list[str]
    """
    warnings: list[str] = []
    outputs: dict = {
        "listing_txt":       None,
        "spec_sheet_png":    None,
        "brochure_png":      None,
        "image_pack_folder": None,
        "walkaround_mp4":    None,
        "zip_file":          None,
    }

    dealer      = dealer_info or {}
    make        = parsed_listing.get("make")           or ""
    model       = parsed_listing.get("model")          or ""
    year        = parsed_listing.get("year")
    eq_type     = parsed_listing.get("equipment_type") or ""
    machine_name  = _safe_machine_name(make, model)
    machine_match = " ".join(str(p) for p in [year, make.upper() if make else None, model] if p) or "Unknown Machine"

    walkaround_requested = generate_walkaround or bool(walkaround_video_path)
    walkaround_included  = False
    walkaround_status    = "not_requested"
    walkaround_final_path: str | None = None

    # ── Create listing_output/ folder ─────────────────────────────────────────
    pack_dir = os.path.join(session_dir, "listing_output")
    spec_dir = os.path.join(pack_dir, "spec_sheet")
    os.makedirs(spec_dir, exist_ok=True)

    # ── 1. listing_description.txt  (highest priority — always attempted) ──────
    listing_txt_path = os.path.join(pack_dir, "listing_description.txt")
    try:
        with open(listing_txt_path, "w", encoding="utf-8") as f:
            f.write(generated_listing_text)
        outputs["listing_txt"] = listing_txt_path
    except Exception as exc:
        warnings.append(f"listing_description.txt write failed: {exc}")

    # ── 2. Spec sheet PNG ─────────────────────────────────────────────────────
    spec_count = len(spec_sheet_entries)
    spec_sheet_path = None

    if dealer_input_dump is not None and enriched_resolved_specs is not None:
        spec_sheet_out = os.path.join(spec_dir, "machine_spec_sheet.png")
        # Remove any stale artifact before writing so re-downloads never serve old output
        if os.path.isfile(spec_sheet_out):
            os.remove(spec_sheet_out)
        session_id = os.path.basename(session_dir) if session_dir else ""
        dealer_contact = {
            "dealer_name": dealer.get("dealer_name"),
            "phone":       dealer.get("phone"),
            "location":    dealer.get("location"),
        }
        screenshot_spec_sheet(
            dealer_input_data=dealer_input_dump,
            resolved_specs=enriched_resolved_specs,
            ui_hints=(resolved_machine or {}).get("ui_hints") or {},
            equipment_type=eq_type or "",
            dealer_contact=dealer_contact,
            session_id=session_id,
            outputs_dir=_OUTPUTS_DIR,
            output_path=spec_sheet_out,
            field_confidence=(full_record or {}).get("field_confidence") or {},
        )
        print(f"  [Pack] spec_sheet path    : {spec_sheet_out}")
        spec_sheet_path = spec_sheet_out
        outputs["spec_sheet_png"] = spec_sheet_out
    else:
        warnings.append("No dealer input — spec sheet skipped.")

    # ── 3. Image pack ─────────────────────────────────────────────────────────
    valid_images = [
        p for p in (image_input_paths or [])
        if os.path.isfile(p) and Path(p).suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    # Classify framing of each source photo before processing.
    # Non-blocking: failures return classification="good" so generation is never stalled.
    photo_analysis: list[dict] = [classify_photo_framing(p) for p in valid_images]

    if valid_images:
        try:
            _img_tmp = os.path.join(session_dir, "_img_tmp")
            os.makedirs(_img_tmp, exist_ok=True)
            for src in valid_images:
                shutil.copy2(src, _img_tmp)
            _img_result = generate_image_pack(
                input_folder  = _img_tmp,
                output_folder = pack_dir,
                machine_name  = machine_name,
                skip_zip      = True,  # listing_pack_builder owns the final ZIP
            )
            outputs["image_pack_folder"] = pack_dir
            outputs["image_pack_count"]  = _img_result.get("image_count", 0)
            print(f"  [Pack] image_pack Listing  : {os.path.join(pack_dir, 'Listing_Photos')}")
            print(f"  [Pack] image_pack Original : {os.path.join(pack_dir, 'Original_Photos')}")
            shutil.rmtree(_img_tmp, ignore_errors=True)
        except Exception as exc:
            warnings.append(f"Image pack failed: {exc}")
            print(f"  [Pack] image_pack FAIL     : {exc}")
            shutil.rmtree(os.path.join(session_dir, "_img_tmp"), ignore_errors=True)
    else:
        for sub in ("Listing_Photos", "Original_Photos"):
            os.makedirs(os.path.join(pack_dir, sub), exist_ok=True)
        if not image_input_paths:
            warnings.append("No photos provided — image folders created but empty.")
            print(f"  [Pack] image_pack MISSING  : no photos provided — folders empty")

    # ── 3c. Listing card PNG ──────────────────────────────────────────────────
    # Card is always position _01. Existing listing photos are shifted up by 1
    # so the card sorts first in Listing_Photos/ and is image #1 in the FB batch.
    # Card generation does not require other photos to be present.
    if full_record and card_dealer_data:
        listing_photos_dir = Path(os.path.join(pack_dir, "Listing_Photos"))
        listing_photos_dir.mkdir(parents=True, exist_ok=True)
        try:
            _renumber_listing_photos(listing_photos_dir, machine_name)
            from card_renderer_adapter import export_listing_card
            card_out = listing_photos_dir / f"{machine_name}_01_card.png"
            result = export_listing_card(full_record, card_dealer_data, card_out)
            if result:
                print(f"  [Pack] card PNG           : OK -> {card_out.name}")
            else:
                warnings.append("Card render failed — see logs for details.")
                print("  [Pack] card PNG           : FAIL (see logs)")
        except Exception as exc:
            warnings.append(f"Card render failed: {exc}")
            print(f"  [Pack] card PNG           : FAIL ({exc})")

    # ── 3d. Spec sheet image — position _02 in Listing_Photos ────────────────
    # Rendered at 1080×1350 (same format as hero card). Sits at _02 so that
    # the pack order for Facebook posting is: hero → spec sheet → photos.
    # Requires the same pipeline data as build_listing_pack_v1 passes through.
    if dealer_input_dump is not None and enriched_resolved_specs is not None:
        try:
            from spec_sheet_renderer_adapter import build_spec_sheet_data, export_spec_sheet
            listing_photos_dir = Path(os.path.join(pack_dir, "Listing_Photos"))
            listing_photos_dir.mkdir(parents=True, exist_ok=True)
            # Shift existing _listing photos up by 1 (02→03, 03→04…) to open slot _02.
            _renumber_listing_photos(listing_photos_dir, machine_name)
            # Locate first uploaded photo for the spec sheet image.
            _ss_photo = valid_images[0] if valid_images else None
            _ss_data = build_spec_sheet_data(
                dealer_input_data       = dealer_input_dump,
                enriched_resolved_specs = enriched_resolved_specs,
                equipment_type          = eq_type,
                dealer_contact          = {
                    "dealer_name": dealer.get("dealer_name"),
                    "phone":       dealer.get("phone"),
                    "location":    dealer.get("location"),
                },
                dealer_info  = dealer,
                full_record  = full_record,
                photo_path   = _ss_photo,
            )
            ss_img_out = listing_photos_dir / f"{machine_name}_02_spec_sheet.png"
            ss_result  = export_spec_sheet(_ss_data, ss_img_out)
            if ss_result:
                print(f"  [Pack] spec sheet img     : OK -> {ss_img_out.name}")
            else:
                warnings.append("Spec sheet image render failed — see logs.")
                print("  [Pack] spec sheet img     : FAIL (see logs)")
        except Exception as exc:
            import traceback
            warnings.append(f"Spec sheet image render failed: {exc}")
            print(f"  [Pack] spec sheet img     : FAIL ({exc})")
            print(traceback.format_exc())

    # ── 3e. Light badge overlay on listing photos ─────────────────────────────
    # generate_image_pack() → APPLY BADGE → zip
    #
    # Targeting rules (non-negotiable):
    #   ONLY  *_listing.jpg  (glob pattern, applied after generate_image_pack)
    #   NEVER *_01_card.png / *_02_spec_sheet.png  (generated assets — untouched)
    #
    # Skips silently when logo_path is absent — never blocks ZIP.
    _logo_path = (dealer or {}).get("logo_path")
    if _logo_path and valid_images:
        try:
            from renderers.badge_renderer import apply_badge_to_photo
            _lp_badge      = Path(os.path.join(pack_dir, "Listing_Photos"))
            _badge_targets = sorted(_lp_badge.glob("*_listing.jpg"))
            _badge_name    = (dealer or {}).get("contact_name") or (dealer or {}).get("dealer_name") or None
            _badge_phone   = (dealer or {}).get("phone") or None
            _badge_accent  = (dealer or {}).get("accent_color", "yellow")
            _badged = sum(
                1 for _bp in _badge_targets
                if apply_badge_to_photo(
                    photo_path  = str(_bp),
                    logo_path   = _logo_path,
                    name        = _badge_name,
                    phone       = _badge_phone,
                    accent      = _badge_accent,
                    output_path = str(_bp),
                )
            )
            print(f"  [Pack] badge stamp        : {_badged}/{len(_badge_targets)} listing photo(s)")
        except Exception as _badge_exc:
            import traceback
            _tb = traceback.format_exc()
            warnings.append(f"Badge stamping failed: {_badge_exc}")
            print(f"  [Pack] badge stamp        : FAIL ({_badge_exc})")
            print(_tb)

    # ── 4. Walkaround video (lowest priority — failure never blocks ZIP) ───────
    if walkaround_requested:
        walkaround_status = "pending"

        # Mode A: a pre-generated video was supplied — just copy it in
        if walkaround_video_path and os.path.isfile(walkaround_video_path):
            try:
                dest = os.path.join(pack_dir, "walkaround.mp4")
                shutil.copy2(walkaround_video_path, dest)
                walkaround_included   = True
                walkaround_status     = "included"
                walkaround_final_path = dest
                outputs["walkaround_mp4"] = dest
            except Exception as exc:
                walkaround_status = "failed"
                warnings.append(f"Walkaround video copy failed: {exc}")

        # Mode B: generate from photos using ffmpeg
        elif generate_walkaround:
            if not valid_images:
                walkaround_status = "failed_no_photos"
                warnings.append("Walkaround video requested but no photos available.")
            else:
                try:
                    video_out = os.path.join(pack_dir, "walkaround.mp4")
                    generate_walkaround_video(
                        image_paths = valid_images,
                        output_path = video_out,
                    )
                    walkaround_included   = True
                    walkaround_status     = "included"
                    walkaround_final_path = video_out
                    outputs["walkaround_mp4"] = video_out
                except Exception as exc:
                    walkaround_status = "failed"
                    warnings.append(f"Walkaround video generation failed: {exc}")

        elif walkaround_video_path and not os.path.isfile(walkaround_video_path):
            walkaround_status = "failed_path_not_found"
            warnings.append(f"Walkaround video not found: {walkaround_video_path}")

    # ── 5. metadata_internal.json ────────────────────────────────────────────
    spec_level_label = (
        "FULL" if spec_count >= 8
        else "CORE" if spec_count >= 4
        else "ID_ONLY"
    )
    resolver_conf = (resolved_machine or {}).get("overall_resolution_status")

    included_outputs = []
    if outputs["listing_txt"]:       included_outputs.append("listing_description.txt")
    if outputs["spec_sheet_png"]:    included_outputs.append("spec_sheet/machine_spec_sheet.png")
    if outputs["image_pack_folder"]: included_outputs.append("images_*")
    if walkaround_included:          included_outputs.append("walkaround.mp4")

    # Optional photo-level warning: flag sessions where every image is too tight.
    _all_too_close = (
        bool(photo_analysis)
        and all(p["classification"] == "too_close_cropped" for p in photo_analysis)
    )

    metadata = {
        "make":                  make or None,
        "model":                 model or None,
        "year":                  year,
        "equipment_type":        eq_type or None,
        "resolver_confidence":   resolver_conf,
        "spec_level":            spec_level_label,
        "displayed_spec_count":  spec_count,
        "image_count":           len(valid_images),
        "generated_at":          datetime.now(timezone.utc).isoformat(),
        "included_outputs":      included_outputs,
        "walkaround_requested":  walkaround_requested,
        "walkaround_included":   walkaround_included,
        "walkaround_status":     walkaround_status,
        "walkaround_path":       walkaround_final_path,
        "photo_analysis":        photo_analysis,
        **({"photo_warning": "all_images_too_tight"} if _all_too_close else {}),
        "warnings":              warnings,
    }
    try:
        with open(os.path.join(pack_dir, "metadata_internal.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception as exc:
        warnings.append(f"metadata_internal.json write failed: {exc}")

    # ── 5b. START_HERE.txt ────────────────────────────────────────────────────
    start_here_content = """\
MTM LISTING PACK \u2013 HOW TO USE

1. listing_description.txt
Copy and paste this into Facebook Marketplace, Craigslist, or your website.

2. Listing_Photos
Branded listing images with your logo and contact info.
Use these for:
- Facebook Marketplace
- Craigslist
- EquipmentTrader, Iron Planet, Machinery Trader
- Your website and any dealer listing platform

3. Original_Photos
Your original uploaded photos (full quality).
Use these if you need to re-edit or upload to platforms with their own crop tool.
"""
    try:
        with open(os.path.join(pack_dir, "START_HERE.txt"), "w", encoding="utf-8") as f:
            f.write(start_here_content)
    except Exception as exc:
        warnings.append(f"START_HERE.txt write failed: {exc}")

    # ── 6. ZIP ────────────────────────────────────────────────────────────────
    zip_path = os.path.join(session_dir, "listing_output.zip")
    zip_size = 0
    try:
        zip_size = _zip_folder(pack_dir, zip_path)
        outputs["zip_file"] = zip_path
    except Exception as exc:
        warnings.append(f"ZIP creation failed: {exc}")
        zip_path = None

    zip_web_url = f"{session_web}/listing_output.zip" if (zip_path and session_web) else None

    # ── Summary ───────────────────────────────────────────────────────────────
    wk_tag = "OK" if walkaround_included else ("SKIP" if not walkaround_requested else f"FAIL ({walkaround_status})")
    print(f"\n  [Pack] {machine_match}")
    print(f"  [Pack] listing_description.txt : {'OK' if outputs['listing_txt'] else 'FAIL'}")
    print(f"  [Pack] spec_sheet.png : {'OK' if outputs['spec_sheet_png'] else 'SKIP'} ({spec_count} specs)")
    print(f"  [Pack] image_pack     : {'OK' if outputs['image_pack_folder'] else 'SKIP'} ({len(valid_images)} photos)")
    print(f"  [Pack] walkaround.mp4 : {wk_tag}")
    print(f"  [Pack] ZIP            : {_fmt_size(zip_size) if zip_size else 'FAILED'}")
    for w in warnings:
        print(f"  [Pack] WARNING: {w}")

    return {
        "success":        zip_path is not None,
        "machine_match":  machine_match,
        "spec_count":     spec_count,
        "output_folder":  pack_dir,
        "zip_path":       zip_path,
        "zip_web_url":    zip_web_url,
        "zip_size_bytes": zip_size,
        "outputs":        outputs,
        "walkaround": {
            "requested": walkaround_requested,
            "included":  walkaround_included,
            "status":    walkaround_status,
            "path":      walkaround_final_path,
        },
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# V1 Entry Point — DealerInput + resolved_specs
# ─────────────────────────────────────────────────────────────────────────────

def build_listing_pack_v1(
    dealer_input:          DealerInput,
    resolved_specs:        dict,
    resolved_machine:      "dict | None" = None,
    image_input_paths:     "list[str] | None" = None,
    dealer_info:           "dict | None" = None,
    generate_walkaround:   bool = False,
    walkaround_video_path: "str | None" = None,
    session_dir:           str = "",
    session_web:           str = "",
    equipment_type:        "str | None" = None,
    # Listing card PNG
    full_record:           "dict | None" = None,
) -> dict:
    """
    V1 pack generation entry point using structured DealerInput + resolved OEM specs.

    Generates listing text via build_listing_text(), builds spec sheet entries
    from resolved_specs, then delegates to build_listing_pack() for ZIP assembly.

    Parameters
    ----------
    dealer_input        : Validated DealerInput (year, make, model, hours, toggles, etc.)
    resolved_specs      : Dict of resolved OEM spec fields from the spec resolver.
    resolved_machine    : Full resolver output dict (for confidence metadata), or None.
    image_input_paths   : Absolute paths to source photos (optional).
    dealer_info         : Dict with dealer_name / phone / email / location (optional).
    generate_walkaround : Generate walkaround video from photos via ffmpeg.
    walkaround_video_path: Pre-existing .mp4 to copy into the pack.
    session_dir         : Per-request session directory (absolute path).
    session_web         : Web URL prefix for session_dir.
    equipment_type      : "skid_steer" | "compact_track_loader" | "mini_excavator"
                          When provided, scorer-backed use-case language is injected
                          into the listing. Falls back gracefully if scorer fails.

    Returns
    -------
    Same dict as build_listing_pack().
    """
    from mtm_service import build_spec_sheet_entries

    # 1a. Resolve equipment_type from resolved_machine if not explicitly passed
    if not equipment_type and resolved_machine:
        equipment_type = resolved_machine.get("equipment_type")

    # 1c. Run use-case scorer and build optional listing payload
    use_case_payload = build_use_case_payload(equipment_type, dealer_input, resolved_specs)

    # 1c. Generate listing text from structured inputs + optional scorer payload
    generated_listing_text = build_listing_text(
        dealer_input,
        resolved_specs,
        use_case_payload,
        equipment_type=equipment_type or "",
    )

    # 2. Build parsed_listing dict that build_listing_pack() expects.
    # Include dealer-entered fields needed by the brochure (hours, condition, price).
    parsed_listing = {
        "year":             dealer_input.year,
        "make":             dealer_input.make,
        "model":            dealer_input.model,
        "equipment_type":   equipment_type,   # resolved from registry above
        "hours":            dealer_input.hours,
        "price_value":      getattr(dealer_input, "asking_price", None),
        "track_condition":  getattr(dealer_input, "track_condition", None),
        "tire_condition":   getattr(dealer_input, "tire_condition", None),
        "features":         getattr(dealer_input, "features", None) or [],
    }

    # 3. Build spec sheet entries from resolved specs.
    # For SSL and CTL, inject unit-level status fields from DealerInput so
    # high_flow and two_speed surface as core output on the spec sheet.
    # Values are status strings: "yes" / "no" / "optional".
    # For CTL, also inject additional dealer-input core fields per locked standard.
    _resolved_for_sheet = dict(resolved_specs)
    _eq = (equipment_type or "").lower()

    if _eq in ("skid_steer", "compact_track_loader"):
        if dealer_input.high_flow is not None:
            _resolved_for_sheet["high_flow"] = dealer_input.high_flow
        if dealer_input.two_speed_travel is not None:
            _resolved_for_sheet["two_speed"] = dealer_input.two_speed_travel

    # SSL locked standard 2026-04-10: inject hours (always present, core output).
    if _eq == "skid_steer":
        _resolved_for_sheet["hours"] = dealer_input.hours

    # CTL locked standard 2026-04-10: inject dealer-input core output fields.
    # These are market-driven fields that appear on the CTL spec sheet by policy.
    # They are omitted only when the dealer has not supplied them (None / falsy).
    if _eq == "compact_track_loader":
        # hours: always present (dealer-entered), core CTL output.
        _resolved_for_sheet["hours"] = dealer_input.hours
        if dealer_input.cab_type:
            _resolved_for_sheet["cab_type"] = dealer_input.cab_type
        # ac: always injected for CTL (bool → "Yes"/"No" on spec sheet)
        _resolved_for_sheet["ac"] = dealer_input.ac
        if dealer_input.track_condition:
            # Free-text field — injected as-is (e.g. "70%", "Good", "Just replaced")
            _resolved_for_sheet["track_condition"] = dealer_input.track_condition
        if dealer_input.serial_number:
            _resolved_for_sheet["serial_number"] = dealer_input.serial_number
        # Feature fields: use locked standard buyer-facing key names.
        if dealer_input.heater is not None:
            _resolved_for_sheet["heat"] = dealer_input.heater
        if dealer_input.control_type:
            _resolved_for_sheet["controls_type"] = dealer_input.control_type
        if dealer_input.coupler_type:
            _resolved_for_sheet["quick_attach"] = dealer_input.coupler_type

    # Large excavator locked standard 2026-04-10: inject dealer-input core and feature fields.
    # aux_hydraulics_type is typed (not boolean). Boolean aux_hydraulics must not be injected.
    if _eq == "excavator":
        # Core fields (always injected when present)
        _resolved_for_sheet["hours"] = dealer_input.hours
        if dealer_input.ac is not None:
            _resolved_for_sheet["ac"] = dealer_input.ac
        if dealer_input.heater is not None:
            _resolved_for_sheet["heater"] = dealer_input.heater
        if dealer_input.aux_hydraulics_type:
            _resolved_for_sheet["aux_hydraulics_type"] = dealer_input.aux_hydraulics_type
        if dealer_input.coupler_type:
            _resolved_for_sheet["coupler_type"] = dealer_input.coupler_type
        if dealer_input.rear_camera is not None:
            _resolved_for_sheet["rear_camera"] = dealer_input.rear_camera
        if dealer_input.stick_arm_length_ft is not None:
            _resolved_for_sheet["stick_arm_length_ft"] = dealer_input.stick_arm_length_ft
        if dealer_input.track_shoe_width_in is not None:
            _resolved_for_sheet["track_shoe_width_in"] = dealer_input.track_shoe_width_in
        if dealer_input.undercarriage_condition_pct:
            _resolved_for_sheet["undercarriage_condition_pct"] = dealer_input.undercarriage_condition_pct
        if dealer_input.boom_length_ft is not None:
            _resolved_for_sheet["boom_length_ft"] = dealer_input.boom_length_ft
        if dealer_input.serial_number:
            _resolved_for_sheet["serial_number"] = dealer_input.serial_number
        # Feature fields
        if dealer_input.bucket_size_included:
            _resolved_for_sheet["bucket_size_included"] = dealer_input.bucket_size_included
        if dealer_input.grade_control_type:
            _resolved_for_sheet["grade_control_type"] = dealer_input.grade_control_type
        if dealer_input.thumb_type:
            _resolved_for_sheet["thumb_type"] = dealer_input.thumb_type
        if dealer_input.hammer_plumbing is not None:
            _resolved_for_sheet["hammer_plumbing"] = dealer_input.hammer_plumbing
        if dealer_input.track_type:
            _resolved_for_sheet["track_type"] = dealer_input.track_type
        if dealer_input.pattern_changer is not None:
            _resolved_for_sheet["pattern_changer"] = dealer_input.pattern_changer
        if dealer_input.heated_seat is not None:
            _resolved_for_sheet["heated_seat"] = dealer_input.heated_seat
        if dealer_input.air_ride_seat:
            _resolved_for_sheet["air_ride_seat"] = dealer_input.air_ride_seat
        if dealer_input.radio:
            _resolved_for_sheet["radio"] = dealer_input.radio
        if dealer_input.warranty_status:
            _resolved_for_sheet["warranty_status"] = dealer_input.warranty_status

    # Telehandler locked standard 2026-04-13: inject unit-level listing/config fields.
    # hours: always present, core output. cab_type and has_stabilizers suppressed when null.
    if _eq == "telehandler":
        _resolved_for_sheet["hours"] = dealer_input.hours
        if dealer_input.cab_type:
            _resolved_for_sheet["cab_type"] = dealer_input.cab_type
        if dealer_input.has_stabilizers is not None:
            _resolved_for_sheet["has_stabilizers"] = dealer_input.has_stabilizers

    # Mini ex locked standard 2026-04-10: inject dealer-input CORE OUTPUT fields.
    # aux_hydraulics is stored in registry as "auxiliary_hydraulics" — translated here
    # at the output layer only; registry key is not renamed.
    if _eq == "mini_excavator":
        # hours: always shown
        _resolved_for_sheet["hours"] = dealer_input.hours
        if dealer_input.cab_type:
            _resolved_for_sheet["cab_type"] = dealer_input.cab_type
        if dealer_input.ac is not None:
            _resolved_for_sheet["ac"] = dealer_input.ac
        if dealer_input.heater is not None:
            _resolved_for_sheet["heater"] = dealer_input.heater
        # aux_hydraulics: prefer dealer-confirmed value; fall back to registry-derived value
        if dealer_input.aux_hydraulics is not None:
            _resolved_for_sheet["aux_hydraulics"] = dealer_input.aux_hydraulics
        elif "auxiliary_hydraulics" in _resolved_for_sheet:
            _resolved_for_sheet["aux_hydraulics"] = _resolved_for_sheet["auxiliary_hydraulics"]
        if dealer_input.coupler_type:
            _resolved_for_sheet["coupler_type"] = dealer_input.coupler_type
        if dealer_input.thumb_type:
            _resolved_for_sheet["thumb_type"] = dealer_input.thumb_type
        if dealer_input.blade_type:
            _resolved_for_sheet["blade_type"] = dealer_input.blade_type
        if dealer_input.serial_number:
            _resolved_for_sheet["serial_number"] = dealer_input.serial_number
        if dealer_input.two_speed_travel is not None:
            _resolved_for_sheet["two_speed"] = dealer_input.two_speed_travel
        if dealer_input.track_condition:
            _resolved_for_sheet["track_condition"] = dealer_input.track_condition

    spec_sheet_entries = build_spec_sheet_entries(
        _resolved_for_sheet,
        {},
        equipment_type or "",
    )

    # 4. Build pre-adapted dealer dict for the card renderer (if full_record present)
    card_dealer_data: "dict | None" = None
    if full_record is not None:
        from card_renderer_adapter import adapt_dealer_input
        _theme = (dealer_info or {}).get("accent_color", "yellow")
        card_dealer_data = adapt_dealer_input(
            dealer_input, image_input_paths or [], theme=_theme
        )

    # 5. Delegate to the full pack assembler
    return build_listing_pack(
        raw_text                = "",
        parsed_listing          = parsed_listing,
        resolved_machine        = resolved_machine,
        generated_listing_text  = generated_listing_text,
        spec_sheet_entries      = spec_sheet_entries,
        image_input_paths       = image_input_paths or [],
        dealer_info             = dealer_info,
        generate_walkaround     = generate_walkaround,
        walkaround_video_path   = walkaround_video_path,
        session_dir             = session_dir,
        session_web             = session_web,
        use_case_payload        = use_case_payload,
        full_record             = full_record,
        card_dealer_data        = card_dealer_data,
        dealer_input_dump       = dealer_input.model_dump(),
        enriched_resolved_specs = _resolved_for_sheet,
    )
