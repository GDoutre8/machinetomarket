"""
spec_sheet_renderer_adapter.py
===============================
Adapter between the MTM listing pipeline and spec_sheet_renderer.render_spec_sheet().

Public API
----------
build_spec_sheet_data(
    dealer_input_data, enriched_resolved_specs, equipment_type,
    dealer_contact, dealer_info, full_record, photo_path
) -> dict
    Build the renderer's structured data dict.

export_spec_sheet(data, output_path, *, fail_silently) -> Path | None
    Render spec_sheet HTML → PNG via Playwright. Returns output_path or None.
"""

from __future__ import annotations

import base64
import concurrent.futures
import logging
import re
from pathlib import Path
from typing import Any

from spec_sheet_renderer import render_spec_sheet

log = logging.getLogger(__name__)

_EQ_TYPE_DISPLAY = {
    "compact_track_loader": "Compact Track Loader",
    "skid_steer":           "Skid Steer Loader",
    "mini_excavator":       "Mini Excavator",
    "backhoe_loader":       "Backhoe Loader",
    "large_excavator":      "Large Excavator",
    "excavator":            "Excavator",
    "telehandler":          "Telehandler",
}


def _fmt_int(v: Any) -> str | None:
    if v is None:
        return None
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_phone(raw: str) -> str:
    d = re.sub(r"\D", "", raw)[:10]
    if len(d) >= 7:
        return f"({d[:3]}) {d[3:6]}-{d[6:]}"
    if len(d) >= 4:
        return f"({d[:3]}) {d[3:]}"
    return raw


def _logo_data_uri(logo_path: str | None) -> str | None:
    if not logo_path:
        return None
    p = Path(logo_path)
    if not p.is_file():
        return None
    suffix = p.suffix.lower()
    mime = {
        ".png": "image/png", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(suffix, "image/png")
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _core_specs(di: dict, specs: dict, eq_type: str, full_record: dict) -> list[dict]:
    """Build the 'Core Specs — Verified Against OEM' rows."""
    rows: list[dict] = []

    # Hours — always first, always from dealer input
    hours = di.get("hours")
    rows.append({"label": "Hours", "value": _fmt_int(hours), "unit": "HRS"})

    # Net Power
    hp = specs.get("horsepower_hp")
    rows.append({"label": "Net Power", "value": _fmt_int(hp), "unit": "HP"})

    # Rated Operating Capacity (SSL/CTL) or Lift Capacity (telehandler)
    if eq_type in ("compact_track_loader", "skid_steer"):
        roc = specs.get("rated_operating_capacity_lbs")
        rows.append({"label": "Rated Op Capacity", "value": _fmt_int(roc), "unit": "LB"})
    elif eq_type == "telehandler":
        cap = specs.get("lift_capacity_lbs") or specs.get("lift_capacity_at_full_height_lbs")
        rows.append({"label": "Lift Capacity", "value": _fmt_int(cap), "unit": "LB"})
    else:
        # Generic: ROC / operating capacity
        roc = specs.get("rated_operating_capacity_lbs") or specs.get("operating_capacity_lbs")
        if roc:
            rows.append({"label": "Rated Op Capacity", "value": _fmt_int(roc), "unit": "LB"})

    # Aux flow — prefer high-flow value when active
    high_flow_active = (
        (di.get("high_flow") == "yes")
        or bool((full_record.get("feature_flags") or {}).get("high_flow_available"))
    )
    flow_high = specs.get("aux_flow_high_gpm")
    flow_std  = specs.get("aux_flow_standard_gpm") or specs.get("hydraulic_flow_gpm")
    if high_flow_active and flow_high is not None:
        rows.append({"label": "Aux Flow (High)", "value": _fmt_int(flow_high), "unit": "GPM"})
    elif flow_std is not None:
        rows.append({"label": "Aux Flow", "value": _fmt_int(flow_std), "unit": "GPM"})
    elif flow_high is not None:
        rows.append({"label": "Aux Flow", "value": _fmt_int(flow_high), "unit": "GPM"})

    # Operating weight
    weight = specs.get("operating_weight_lbs") or specs.get("machine_weight_lbs")
    if weight:
        rows.append({"label": "Operating Weight", "value": _fmt_int(weight), "unit": "LB"})

    return rows


def _secondary_specs(di: dict, specs: dict, eq_type: str) -> list[dict]:
    """Build supplementary spec rows (lift path, dimensions, pressure, etc.)."""
    rows: list[dict] = []

    # Lift path (SSL/CTL)
    lp_raw = specs.get("lift_path") or specs.get("lift_type")
    if lp_raw:
        _LP = {"vertical": "Vertical", "radial": "Radial", "high": "Vertical", "locked": "Vertical"}
        rows.append({"label": "Lift Path", "value": _LP.get(str(lp_raw).lower(), str(lp_raw).title())})

    # Hinge pin height
    hpp = specs.get("hinge_pin_height_in") or specs.get("dump_height_in")
    if hpp:
        try:
            rows.append({"label": "Hinge Pin Height", "value": f'{int(float(hpp))}"'})
        except (TypeError, ValueError):
            rows.append({"label": "Hinge Pin Height", "value": str(hpp)})

    # Width
    w = specs.get("width_in") or specs.get("overall_width_in")
    if w:
        try:
            rows.append({"label": "Width", "value": f'{int(float(w))}"'})
        except (TypeError, ValueError):
            rows.append({"label": "Width", "value": str(w)})

    # Hydraulic pressure
    psi = specs.get("hydraulic_pressure_psi") or specs.get("aux_pressure_psi")
    if psi:
        try:
            rows.append({"label": "Hyd Pressure", "value": f"{int(float(psi)):,}", "unit": "PSI"})
        except (TypeError, ValueError):
            rows.append({"label": "Hyd Pressure", "value": str(psi)})

    # Track/undercarriage specific
    if eq_type in ("compact_track_loader", "mini_excavator", "large_excavator", "excavator"):
        tw = specs.get("track_width_in")
        if tw:
            try:
                rows.append({"label": "Track Width", "value": f'{int(float(tw))}"'})
            except (TypeError, ValueError):
                rows.append({"label": "Track Width", "value": str(tw)})
        tc = di.get("track_condition")
        if tc:
            rows.append({"label": "Track Condition", "value": str(tc)})

    # Dig/dump depth for excavators
    if eq_type in ("mini_excavator", "large_excavator", "excavator"):
        dd = specs.get("dig_depth_ft") or specs.get("max_dig_depth_ft")
        if dd:
            try:
                ft = float(dd)
                f_int, f_dec = divmod(ft, 1)
                val = f"{int(f_int)}' {int(round(f_dec*12))}\"" if f_dec else f"{int(f_int)}'"
                rows.append({"label": "Dig Depth", "value": val})
            except (TypeError, ValueError):
                rows.append({"label": "Dig Depth", "value": str(dd)})

    # Serial number — always last in secondary if present
    sn = di.get("serial_number")
    if sn:
        rows.append({"label": "Serial #", "value": str(sn)})

    return rows


def _features(di: dict, eq_type: str) -> list[str]:
    """Build a flat list of confirmed feature labels (max 8)."""
    feats: list[str] = []

    # Cab
    if (di.get("cab_type") or "").lower() == "enclosed":
        if di.get("ac"):
            feats.append("Enclosed Cab, A/C + Heat" if di.get("heater") else "Enclosed Cab, A/C")
        elif di.get("heater"):
            feats.append("Enclosed Cab, Heat")
        else:
            feats.append("Enclosed Cab")
    elif di.get("ac"):
        feats.append("A/C + Heat" if di.get("heater") else "A/C")
    elif di.get("heater"):
        feats.append("Heat")

    # Hydraulics/drive
    if di.get("high_flow") == "yes":
        feats.append("High Flow Hydraulics")
    if di.get("two_speed_travel") == "yes":
        feats.append("2-Speed Travel")

    # Attachments
    if di.get("coupler_type") == "hydraulic":
        feats.append("Hydraulic Quick Attach")
    elif di.get("coupler_type"):
        feats.append("Quick Attach")

    # Comfort/utility
    if di.get("air_ride_seat"):
        feats.append("Air Ride Seat")
    if di.get("ride_control"):
        feats.append("Ride Control")
    if di.get("backup_camera") or di.get("rear_camera"):
        feats.append("Backup Camera")
    if di.get("radio"):
        feats.append("Radio")

    # Attachments included
    if di.get("attachments_included"):
        for att in str(di["attachments_included"]).split(",")[:3]:
            att = att.strip()
            if att:
                feats.append(att.title())

    # Excavator-specific
    if di.get("thumb_type") and di.get("thumb_type") not in ("none", ""):
        feats.append("Thumb")
    if di.get("hammer_plumbing"):
        feats.append("Hammer Plumbing")

    return feats[:8]


def _condition_block(di: dict) -> dict:
    grade = di.get("condition_grade")
    own = di.get("owner_history") or ("One Owner" if di.get("one_owner") else None)
    notes = di.get("additional_details")
    return {"grade": grade, "ownership": own, "notes": notes}


def build_spec_sheet_data(
    dealer_input_data: dict,
    enriched_resolved_specs: dict,
    equipment_type: str,
    dealer_contact: dict,
    dealer_info: dict,
    full_record: dict | None = None,
    photo_path: str | None = None,
) -> dict:
    """
    Build the structured data dict for render_spec_sheet().

    Parameters
    ----------
    dealer_input_data       : DealerInput.model_dump()
    enriched_resolved_specs : Merged spec dict from build_listing_pack_v1 (with DealerInput injections)
    equipment_type          : e.g. "compact_track_loader"
    dealer_contact          : {"dealer_name", "phone", "location"} from dealer_info
    dealer_info             : Full dealer_info dict (for logo_path, accent_color)
    full_record             : Registry full_record (for feature_flags)
    photo_path              : First uploaded photo path or None
    """
    di    = dealer_input_data or {}
    specs = enriched_resolved_specs or {}
    fr    = full_record or {}
    eq    = (equipment_type or "").lower()

    cat = _EQ_TYPE_DISPLAY.get(eq, eq.replace("_", " ").title()) if eq else ""
    theme = ((dealer_info or {}).get("accent_color") or "yellow").lower()

    # Logo
    logo_path = (dealer_info or {}).get("logo_path")
    logo_uri  = _logo_data_uri(logo_path)

    # Contact
    raw_phone = (dealer_contact or {}).get("phone") or ""
    phone = _fmt_phone(raw_phone) if raw_phone else ""
    location = (dealer_contact or {}).get("location") or ""
    d_name = (dealer_contact or {}).get("dealer_name") or ""

    return {
        "machine": {
            "year":       di.get("year"),
            "make":       (di.get("make") or "").upper(),
            "model":      di.get("model") or "",
            "category":   cat,
            "photo_path": photo_path,
        },
        "listing": {
            "price_usd": di.get("asking_price"),
            "hours":     di.get("hours"),
        },
        "specs": {
            "core":      _core_specs(di, specs, eq, fr),
            "secondary": _secondary_specs(di, specs, eq),
        },
        "features":  _features(di, eq),
        "condition": _condition_block(di),
        "dealer": {
            "name":          d_name,
            "phone":         phone,
            "location":      location,
            "logo_data_uri": logo_uri,
            "theme":         theme,
        },
    }


def export_spec_sheet(
    data: dict,
    output_path: Path,
    *,
    fail_silently: bool = True,
) -> Path | None:
    """
    Render the spec sheet and export to PNG via Playwright.

    Returns output_path on success, None on failure (when fail_silently=True).
    """
    try:
        html_str = render_spec_sheet(data)
        _screenshot_spec_sheet(html_str, output_path)
        log.info("[spec_sheet_renderer] exported %s", output_path)
        return output_path
    except Exception as exc:
        log.warning("[spec_sheet_renderer] export failed: %s", exc, exc_info=True)
        if not fail_silently:
            raise
        return None


def _screenshot_spec_sheet(html_str: str, output_path: Path) -> None:
    """Render HTML to PNG: 540px CSS × 4:5 aspect-ratio at device_scale_factor=2.0 → 1080×1350 px."""
    from playwright.sync_api import sync_playwright

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _render() -> None:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": 560, "height": 700},
                    device_scale_factor=2.0,
                )
                page.set_content(html_str, wait_until="networkidle")
                el = page.query_selector(".sheet")
                if el is None:
                    raise RuntimeError("'.sheet' selector not found in rendered spec sheet HTML")
                el.screenshot(path=str(output_path))
            finally:
                browser.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_render).result()
