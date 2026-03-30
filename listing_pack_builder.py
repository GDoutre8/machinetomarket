"""
listing_pack_builder.py
=======================
MTM Listing Pack Assembly

Combines cleaned listing text, spec sheet PNG, resized image pack, and
optional walkaround video into one downloadable ZIP.

Output structure:
    {session_dir}/listing_output/
        images_original/
        images_4x5/
        images_1x1/
        images_9x16/
        thumbnails/
        spec_sheet/
            machine_spec_sheet.png
        listing.txt
        metadata.json
        walkaround.mp4   (only if generated or provided)
    {session_dir}/listing_output.zip

Priority order (graceful fallback):
    1. listing.txt      — always attempted
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
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from spec_sheet_generator  import generate_spec_sheet
from image_pack_generator  import generate_image_pack, SUPPORTED_EXTENSIONS
from walkaround_generator  import generate_walkaround_video


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_machine_name(make: str, model: str) -> str:
    raw = f"{make}_{model}".replace(" ", "_")
    return "".join(c for c in raw if c.isalnum() or c in "_-")[:40] or "machine"


def _zip_folder(folder_path: str, zip_path: str) -> int:
    root = Path(folder_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fp in sorted(root.rglob("*")):
            if fp.is_file():
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
    machine_match = " ".join(str(p) for p in [year, make, model] if p) or "Unknown Machine"

    walkaround_requested = generate_walkaround or bool(walkaround_video_path)
    walkaround_included  = False
    walkaround_status    = "not_requested"
    walkaround_final_path: str | None = None

    # ── Create listing_output/ folder ─────────────────────────────────────────
    pack_dir = os.path.join(session_dir, "listing_output")
    spec_dir = os.path.join(pack_dir, "spec_sheet")
    os.makedirs(spec_dir, exist_ok=True)

    # ── 1. listing.txt  (highest priority — always attempted) ─────────────────
    listing_txt_path = os.path.join(pack_dir, "listing.txt")
    try:
        with open(listing_txt_path, "w", encoding="utf-8") as f:
            f.write(generated_listing_text)
        outputs["listing_txt"] = listing_txt_path
    except Exception as exc:
        warnings.append(f"listing.txt write failed: {exc}")

    # ── 2. Spec sheet PNG ─────────────────────────────────────────────────────
    spec_count = len(spec_sheet_entries)
    spec_sheet_path = None
    if spec_sheet_entries:
        try:
            spec_sheet_out = os.path.join(spec_dir, "machine_spec_sheet.png")
            generate_spec_sheet(
                make           = make or "Unknown",
                model          = model or "Machine",
                year           = year,
                equipment_type = eq_type.replace("_", " ").title() if eq_type else None,
                spec_sheet     = spec_sheet_entries,
                dealer_name    = dealer.get("dealer_name"),
                phone          = dealer.get("phone"),
                email          = dealer.get("email"),
                location       = dealer.get("location"),
                output_path    = spec_sheet_out,
            )
            spec_sheet_path = spec_sheet_out
            outputs["spec_sheet_png"] = spec_sheet_out
        except Exception as exc:
            warnings.append(f"Spec sheet generation failed: {exc}")
    else:
        warnings.append("No spec sheet entries — spec sheet skipped.")

    # ── 3. Image pack ─────────────────────────────────────────────────────────
    valid_images = [
        p for p in (image_input_paths or [])
        if os.path.isfile(p) and Path(p).suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if valid_images:
        try:
            _img_tmp = os.path.join(session_dir, "_img_tmp")
            os.makedirs(_img_tmp, exist_ok=True)
            for src in valid_images:
                shutil.copy2(src, _img_tmp)
            generate_image_pack(
                input_folder  = _img_tmp,
                output_folder = pack_dir,
                machine_name  = machine_name,
            )
            outputs["image_pack_folder"] = pack_dir
            shutil.rmtree(_img_tmp, ignore_errors=True)
        except Exception as exc:
            warnings.append(f"Image pack failed: {exc}")
            shutil.rmtree(os.path.join(session_dir, "_img_tmp"), ignore_errors=True)
    else:
        for sub in ("images_original", "images_4x5", "images_1x1", "images_9x16", "thumbnails"):
            os.makedirs(os.path.join(pack_dir, sub), exist_ok=True)
        if not image_input_paths:
            warnings.append("No photos provided — image folders created but empty.")

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

    # ── 5. metadata.json ─────────────────────────────────────────────────────
    spec_level_label = (
        "FULL" if spec_count >= 8
        else "CORE" if spec_count >= 4
        else "ID_ONLY"
    )
    resolver_conf = (resolved_machine or {}).get("overall_resolution_status")

    included_outputs = []
    if outputs["listing_txt"]:       included_outputs.append("listing.txt")
    if outputs["spec_sheet_png"]:    included_outputs.append("spec_sheet/machine_spec_sheet.png")
    if outputs["image_pack_folder"]: included_outputs.append("images_*")
    if walkaround_included:          included_outputs.append("walkaround.mp4")

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
        "warnings":              warnings,
    }
    try:
        with open(os.path.join(pack_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception as exc:
        warnings.append(f"metadata.json write failed: {exc}")

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
    print(f"  [Pack] listing.txt    : {'OK' if outputs['listing_txt'] else 'FAIL'}")
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
