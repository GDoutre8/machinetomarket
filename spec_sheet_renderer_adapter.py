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
    "wheel_loader":         "Wheel Loader",
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


def _fmt_ft_in(raw_ft) -> str | None:
    """Convert feet (float) to feet+inches display string, e.g. 12.5 → 12' 6\"."""
    if raw_ft is None:
        return None
    try:
        ft = float(raw_ft)
        f_int, f_dec = divmod(ft, 1)
        inches = int(round(f_dec * 12))
        if inches == 12:
            f_int += 1; inches = 0
        return f"{int(f_int)}' {inches}\"" if inches else f"{int(f_int)}'"
    except (TypeError, ValueError):
        return str(raw_ft)


def _fmt_yd3(raw) -> str | None:
    """Format a cubic-yard float as a clean string, e.g. 1.0 → '1', 1.25 → '1.25'."""
    if raw is None:
        return None
    try:
        bv = float(raw)
        return str(int(bv)) if bv == int(bv) else f"{bv:.2f}".rstrip("0")
    except (TypeError, ValueError):
        return str(raw)


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


def _hero_specs(
    di: dict, specs: dict, eq_type: str, full_record: dict
) -> tuple[list[dict], set[str]]:
    """
    Build up to 4 hero tiles for the photo rail.
    Returns (tiles[:4], hero_key_set).
    hero_key_set contains logical field names to exclude from additional specs.
    Rules: hard cap 4, null-safe promotion, no duplication with additional.
    """
    tiles: list[dict] = []
    hero_keys: set[str] = set()

    def _push(label: str, value, unit: str, key: str) -> bool:
        if len(tiles) >= 4:
            return False
        if value is None or (isinstance(value, str) and not value.strip()):
            return False
        tiles.append({"label": label, "value": str(value), "unit": unit})
        hero_keys.add(key)
        return True

    def _hp():
        return _fmt_int(specs.get("net_hp") or specs.get("horsepower_hp"))

    def _weight():
        return _fmt_int(
            specs.get("operating_weight_lb") or specs.get("operating_weight_lbs")
            or specs.get("machine_weight_lbs")
        )

    def _roc():
        return _fmt_int(
            specs.get("roc_lb") or specs.get("rated_operating_capacity_lbs")
            or specs.get("operating_capacity_lbs")
        )

    def _aux_flow():
        high_flow_active = (
            (di.get("high_flow") == "yes")
            or bool((full_record.get("feature_flags") or {}).get("high_flow_available"))
        )
        flow_high = specs.get("aux_flow_high_gpm")
        flow_std  = specs.get("aux_flow_standard_gpm") or specs.get("hydraulic_flow_gpm")
        if high_flow_active and flow_high is not None:
            return _fmt_int(flow_high), True
        if flow_std is not None:
            return _fmt_int(flow_std), False
        if flow_high is not None:
            return _fmt_int(flow_high), False
        return None, False

    def _dig_depth():
        _dd_in = specs.get("max_dig_depth")
        dd = (specs.get("dig_depth_ft") or specs.get("max_dig_depth_ft")
              or (float(_dd_in) / 12.0 if _dd_in is not None else None))
        return _fmt_ft_in(dd)

    eq = (eq_type or "").lower()

    if eq in ("compact_track_loader", "skid_steer"):
        _push("Rated Op Capacity", _roc(), "LB", "roc")
        _push("Net Power", _hp(), "HP", "hp")
        flow_val, is_high = _aux_flow()
        if flow_val and len(tiles) < 4:
            tiles.append({"label": "Aux Flow (High)" if is_high else "Aux Flow",
                          "value": flow_val, "unit": "GPM"})
            hero_keys.add("aux_flow")
        _push("Operating Weight", _weight(), "LB", "weight")

    elif eq == "mini_excavator":
        _push("Operating Weight", _weight(), "LB", "weight")
        _push("Max Dig Depth", _dig_depth(), "", "dig_depth")
        _push("Engine HP", _hp(), "HP", "hp")
        ts = specs.get("tail_swing_type") or specs.get("tail_swing")
        if ts is None and di.get("zero_tail_swing"):
            ts = "Zero"
        if ts and len(tiles) < 4:
            val = str(ts).lower()
            display = "Zero" if "zero" in val else ("Conventional" if "conv" in val else str(ts).title())
            tiles.append({"label": "Tail Swing", "value": display, "unit": ""})
            hero_keys.add("tail_swing")
        if len(tiles) < 4:
            bbf = specs.get("bucket_breakout_force_lbs") or specs.get("breakout_force_lbs")
            _push("Bucket Breakout", _fmt_int(bbf), "LB", "bucket_breakout")

    elif eq in ("large_excavator", "excavator"):
        _push("Operating Weight", _weight(), "LB", "weight")
        _push("Max Dig Depth", _dig_depth(), "", "dig_depth")
        _push("Engine HP", _hp(), "HP", "hp")
        _push("Bucket Capacity", _fmt_yd3(specs.get("bucket_capacity_yd3")), "YD\u00b3", "bucket_capacity")
        if len(tiles) < 4:
            reach = specs.get("max_reach_ft") or specs.get("reach_ft")
            if reach:
                try:
                    _push("Max Reach", f"{float(reach):.0f}'", "", "reach")
                except (TypeError, ValueError):
                    pass

    elif eq == "wheel_loader":
        _push("Operating Weight", _weight(), "LB", "weight")
        _push("Horsepower", _hp(), "HP", "hp")
        _push("Bucket Capacity", _fmt_yd3(specs.get("bucket_capacity_yd3")), "YD\u00b3", "bucket_capacity")
        bf = specs.get("breakout_force_lbs") or specs.get("breakout_force_lb")
        _push("Breakout Force", _fmt_int(bf), "LB", "breakout_force")
        if len(tiles) < 4:
            _push("Tipping Load", _fmt_int(specs.get("tipping_load_lbs")), "LB", "tipping_load")

    elif eq == "telehandler":
        lc = (specs.get("lift_capacity_lb") or specs.get("lift_capacity_lbs")
              or specs.get("lift_capacity_at_full_height_lbs"))
        _push("Lift Capacity", _fmt_int(lc), "LB", "lift_capacity")
        lh = specs.get("max_lift_height_ft")
        if lh is not None:
            try:
                _push("Max Lift Height", f"{float(lh):.0f}'", "", "lift_height")
            except (TypeError, ValueError):
                _push("Max Lift Height", str(lh), "", "lift_height")
        fr = specs.get("max_forward_reach_ft")
        if fr is not None:
            try:
                _push("Max Fwd Reach", f"{float(fr):.0f}'", "", "fwd_reach")
            except (TypeError, ValueError):
                _push("Max Fwd Reach", str(fr), "", "fwd_reach")
        _push("Horsepower", _hp(), "HP", "hp")
        _push("Operating Weight", _weight(), "LB", "weight")

    elif eq == "backhoe_loader":
        _push("Horsepower", _hp(), "HP", "hp")
        _push("Operating Weight", _weight(), "LB", "weight")
        _push("Max Dig Depth", _dig_depth(), "", "dig_depth")
        lbc = specs.get("loader_bucket_capacity_yd3") or specs.get("bucket_capacity_yd3")
        _push("Loader Bucket", _fmt_yd3(lbc), "YD\u00b3", "loader_bucket")
        if len(tiles) < 4:
            bf = specs.get("loader_breakout_force_lbs") or specs.get("breakout_force_lbs")
            _push("Loader Breakout", _fmt_int(bf), "LB", "breakout_force")

    elif eq == "boom_lift":
        ph = specs.get("platform_height_ft") or specs.get("max_platform_height_ft")
        if ph is not None:
            try:
                _push("Platform Height", f"{float(ph):.0f}'", "", "platform_height")
            except (TypeError, ValueError):
                _push("Platform Height", str(ph), "", "platform_height")
        hr = specs.get("horizontal_reach_ft") or specs.get("max_horizontal_reach_ft")
        if hr is not None:
            try:
                _push("Horizontal Reach", f"{float(hr):.0f}'", "", "horizontal_reach")
            except (TypeError, ValueError):
                _push("Horizontal Reach", str(hr), "", "horizontal_reach")
        pc = specs.get("platform_capacity_lbs") or specs.get("platform_capacity_lb")
        _push("Platform Capacity", _fmt_int(pc), "LB", "platform_capacity")
        bt = specs.get("boom_type")
        if bt and len(tiles) < 4:
            tiles.append({"label": "Boom Type", "value": str(bt).title(), "unit": ""})
            hero_keys.add("boom_type")

    else:
        # Generic fallback
        _push("Net Power", _hp(), "HP", "hp")
        _push("Operating Weight", _weight(), "LB", "weight")
        _push("Rated Op Capacity", _roc(), "LB", "roc")
        flow_val, is_high = _aux_flow()
        if flow_val and len(tiles) < 4:
            tiles.append({"label": "Aux Flow", "value": flow_val, "unit": "GPM"})
            hero_keys.add("aux_flow")

    return tiles[:4], hero_keys


def _additional_specs(
    di: dict, specs: dict, eq_type: str, hero_keys: set[str]
) -> list[dict]:
    """
    Build additional spec rows shown below the hero rail.
    Fields already captured in hero_keys are skipped to prevent duplication.
    """
    rows: list[dict] = []
    eq = (eq_type or "").lower()

    def _row(label: str, value, unit: str = "", key: str = "") -> None:
        if key and key in hero_keys:
            return
        if value is None:
            return
        entry: dict = {"label": label, "value": str(value)}
        if unit:
            entry["unit"] = unit
        rows.append(entry)

    def _hpp() -> None:
        hpp_in = specs.get("hinge_pin_height_in") or specs.get("dump_height_in")
        hpp_ft = specs.get("hinge_pin_height_ft") if not hpp_in else None
        if hpp_in:
            try:
                _row("Hinge Pin Height", f'{int(float(hpp_in))}"')
            except (TypeError, ValueError):
                _row("Hinge Pin Height", str(hpp_in))
        elif hpp_ft is not None:
            _row("Hinge Pin Height", _fmt_ft_in(hpp_ft))

    def _width() -> None:
        w = specs.get("width_in") or specs.get("overall_width_in")
        if w:
            try:
                _row("Width", f'{int(float(w))}"')
            except (TypeError, ValueError):
                _row("Width", str(w))

    def _hyd_pressure() -> None:
        psi = specs.get("hydraulic_pressure_psi") or specs.get("aux_pressure_psi")
        if psi:
            try:
                _row("Hyd Pressure", f"{int(float(psi)):,}", "PSI")
            except (TypeError, ValueError):
                _row("Hyd Pressure", str(psi), "PSI")

    def _track_info() -> None:
        tw = specs.get("track_width_in")
        if tw:
            try:
                _row("Track Width", f'{int(float(tw))}"')
            except (TypeError, ValueError):
                _row("Track Width", str(tw))
        tc = di.get("track_condition")
        if tc:
            _row("Track Condition", str(tc))

    def _dig_depth_row() -> None:
        if "dig_depth" in hero_keys:
            return
        _dd_in = specs.get("max_dig_depth")
        dd = (specs.get("dig_depth_ft") or specs.get("max_dig_depth_ft")
              or (float(_dd_in) / 12.0 if _dd_in is not None else None))
        if dd:
            _row("Max Dig Depth", _fmt_ft_in(dd))

    def _weight_row() -> None:
        if "weight" in hero_keys:
            return
        w = (specs.get("operating_weight_lb") or specs.get("operating_weight_lbs")
             or specs.get("machine_weight_lbs"))
        _row("Operating Weight", _fmt_int(w), "LB")

    def _hp_row() -> None:
        if "hp" in hero_keys:
            return
        hp = specs.get("net_hp") or specs.get("horsepower_hp") or specs.get("engine_hp")
        _row("Engine HP", _fmt_int(hp), "HP")

    def _serial() -> None:
        sn = di.get("serial_number")
        if sn:
            rows.append({"label": "Serial #", "value": str(sn)})

    # ── Per equipment type ────────────────────────────────────────────────────

    if eq in ("compact_track_loader", "skid_steer"):
        lp_raw = specs.get("lift_path") or specs.get("lift_type")
        if lp_raw:
            _LP = {"vertical": "Vertical", "radial": "Radial",
                   "high": "Vertical", "locked": "Vertical"}
            _row("Lift Path", _LP.get(str(lp_raw).lower(), str(lp_raw).title()))
        _hpp()
        _width()
        _hyd_pressure()
        _track_info()
        _weight_row()
        _serial()

    elif eq == "mini_excavator":
        _dig_depth_row()
        _track_info()
        if "bucket_breakout" not in hero_keys:
            bbf = specs.get("bucket_breakout_force_lbs") or specs.get("breakout_force_lbs")
            _row("Bucket Breakout", _fmt_int(bbf), "LB")
        _hpp()
        _width()
        _hyd_pressure()
        _weight_row()
        _serial()

    elif eq in ("large_excavator", "excavator"):
        _dig_depth_row()
        if "bucket_capacity" not in hero_keys:
            _row("Bucket Capacity", _fmt_yd3(specs.get("bucket_capacity_yd3")), "YD³")
        if "reach" not in hero_keys:
            reach = specs.get("max_reach_ft") or specs.get("reach_ft")
            if reach:
                try:
                    _row("Max Reach", f"{float(reach):.0f}'")
                except (TypeError, ValueError):
                    pass
        _track_info()
        _hpp()
        _width()
        _weight_row()
        _serial()

    elif eq == "wheel_loader":
        if "tipping_load" not in hero_keys:
            _row("Tipping Load", _fmt_int(specs.get("tipping_load_lbs")), "LB")
        spd = specs.get("travel_speed_mph")
        if spd is not None:
            try:
                _row("Travel Speed", str(round(float(spd), 1)), "MPH")
            except (TypeError, ValueError):
                _row("Travel Speed", str(spd), "MPH")
        xmit = specs.get("transmission_type")
        if xmit:
            _row("Transmission", str(xmit))
        _hpp()
        _width()
        _weight_row()
        _serial()

    elif eq == "telehandler":
        _weight_row()
        _width()
        _hp_row()
        _serial()

    elif eq == "backhoe_loader":
        _dig_depth_row()
        if "loader_bucket" not in hero_keys:
            lbc = specs.get("loader_bucket_capacity_yd3") or specs.get("bucket_capacity_yd3")
            _row("Loader Bucket", _fmt_yd3(lbc), "YD³")
        if "breakout_force" not in hero_keys:
            bf = specs.get("loader_breakout_force_lbs") or specs.get("breakout_force_lbs")
            _row("Loader Breakout", _fmt_int(bf), "LB")
        _width()
        _weight_row()
        _serial()

    elif eq == "boom_lift":
        _weight_row()
        ft = specs.get("fuel_type")
        if ft:
            _row("Fuel Type", str(ft).title())
        ds = specs.get("drive_speed_mph")
        if ds is not None:
            try:
                _row("Drive Speed", str(round(float(ds), 1)), "MPH")
            except (TypeError, ValueError):
                _row("Drive Speed", str(ds), "MPH")
        _serial()

    else:
        _weight_row()
        _hpp()
        _width()
        _hyd_pressure()
        _serial()

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

    hero_tiles, hero_keys = _hero_specs(di, specs, eq, fr)
    add_rows = _additional_specs(di, specs, eq, hero_keys)

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
            "hero":       hero_tiles,
            "additional": add_rows,
        },
        "features": _features(di, eq),
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
