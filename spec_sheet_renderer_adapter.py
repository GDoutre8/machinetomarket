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


# ── CTL readiness guard ───────────────────────────────────────────────────────
_CTL_REQUIRED_FIELDS = [
    "horsepower_hp",
    "rated_operating_capacity_lbs",
    "operating_weight_lbs",
    "aux_flow_standard_gpm",
    "lift_path",
    "width_over_tires_in",
    "bucket_hinge_pin_height_in",
]


def _ctl_is_spec_ready(specs: dict, full_record: dict | None) -> bool:
    """
    Return True when all 7 CTL required fields are present and the record is not
    a coverage stub or seed-only placeholder.  Returns False for any weak record
    that should not produce a full OEM-style spec sheet.
    """
    fr = full_record or {}
    if fr.get("coverage_stub") or fr.get("seed_only"):
        return False
    return all(specs.get(f) is not None for f in _CTL_REQUIRED_FIELDS)


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

    CTL (compact_track_loader) — locked reference implementation, do not alter:
      Slot 1: Rated Operating Capacity (LB)
      Slot 2: Net Power (HP)
      Slot 3: Aux Hydraulic Flow — "Aux Flow (Standard)" or "Aux Flow (High)" per unit config
      Slot 4: Lift Path — Vertical / Radial; fallback to Operating Weight if lift_path absent

    SSL (skid_steer) — locked, derived from CTL benchmark, do not alter:
      Slot 1: Rated Operating Capacity (LB)          [same as CTL]
      Slot 2: Net Power (HP)                          [same as CTL]
      Slot 3: Aux Hydraulic Flow — Standard or High   [same as CTL]
      Slot 4: Lift Type — Vertical / Radial; fallback to Operating Weight if absent
      NOTE: label is "Lift Type" (not "Lift Path") per SSL locked architecture.

    Mini Ex (mini_excavator) — locked, do not alter:
      Slot 1: Operating Weight (LB)
      Slot 2: Max Dig Depth (ft + in display)
      Slot 3: ROPS Type — DealerInput cab_type overrides registry value
      Slot 4: Tail Swing — Zero Tail / Reduced Tail / Conventional
    """
    tiles: list[dict] = []
    hero_keys: set[str] = set()

    def _push(label: str, value, unit: str, key: str, icon: str = "") -> bool:
        if len(tiles) >= 4:
            return False
        if value is None or (isinstance(value, str) and not value.strip()):
            return False
        tiles.append({"label": label, "value": str(value), "unit": unit, "icon": icon or key})
        hero_keys.add(key)
        return True

    def _hp():
        return _fmt_int(
            specs.get("net_hp") or specs.get("horsepower_hp")
            or specs.get("horsepower_gross_hp") or specs.get("engine_hp")
        )

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
        flow_high = (specs.get("aux_flow_high_gpm") or specs.get("hi_flow_gpm"))
        flow_std  = specs.get("aux_flow_standard_gpm") or specs.get("hydraulic_flow_gpm")
        if high_flow_active and flow_high is not None:
            return _fmt_int(flow_high), True
        if flow_std is not None:
            return _fmt_int(flow_std), False
        if flow_high is not None:
            return _fmt_int(flow_high), False
        return None, False

    def _dig_depth():
        _dd_in = specs.get("max_dig_depth") or specs.get("max_dig_depth_in")
        dd = specs.get("dig_depth_ft") or specs.get("max_dig_depth_ft")
        if dd is None and _dd_in is not None:
            try:
                dd = float(_dd_in) / 12.0
            except (TypeError, ValueError):
                dd = _dd_in   # resolver pre-formatted string; _fmt_ft_in returns it as-is
        return _fmt_ft_in(dd)

    eq = (eq_type or "").lower()

    # ── CTL benchmark — locked field order, do not alter ─────────────────────
    if eq == "compact_track_loader":
        _push("Rated Op Capacity", _roc(), "LB", "roc")   # slot 1: ROC at 35% tip
        _push("Net Power", _hp(), "HP", "hp")              # slot 2: net engine power
        flow_val, is_high = _aux_flow()
        if flow_val and len(tiles) < 4:                    # slot 3: aux flow, Standard or High
            tiles.append({"label": "Aux Flow (High)" if is_high else "Aux Flow (Standard)",
                          "value": flow_val, "unit": "GPM", "icon": "aux_flow"})
            hero_keys.add("aux_flow")
        # slot 4: Lift Path — Vertical or Radial; Operating Weight only if lift_path absent
        lp_raw = specs.get("lift_path") or specs.get("lift_type")
        if lp_raw and len(tiles) < 4:
            _LP = {"vertical": "Vertical", "radial": "Radial",
                   "high": "Vertical", "locked": "Vertical"}
            lp_display = _LP.get(str(lp_raw).lower(), str(lp_raw).title())
            tiles.append({"label": "Lift Path", "value": lp_display,
                          "unit": "", "icon": "lift_path"})
            hero_keys.add("lift_path")
        elif len(tiles) < 4:
            _push("Operating Weight", _weight(), "LB", "weight")

    # ── SSL locked hero — do not alter ───────────────────────────────────────────
    elif eq == "skid_steer":
        _push("Rated Op Capacity", _roc(), "LB", "roc")   # slot 1: ROC at 35% tip
        _push("Net Power", _hp(), "HP", "hp")              # slot 2: net engine power
        flow_val, is_high = _aux_flow()
        if flow_val and len(tiles) < 4:                    # slot 3: aux flow, Standard or High
            tiles.append({"label": "Aux Flow (High)" if is_high else "Aux Flow (Standard)",
                          "value": flow_val, "unit": "GPM", "icon": "aux_flow"})
            hero_keys.add("aux_flow")
        # slot 4: Lift Type — Vertical or Radial; Operating Weight only if lift_path absent
        lp_raw = specs.get("lift_path") or specs.get("lift_type")
        if lp_raw and len(tiles) < 4:
            _LP = {"vertical": "Vertical", "radial": "Radial",
                   "high": "Vertical", "locked": "Vertical"}
            lp_display = _LP.get(str(lp_raw).lower(), str(lp_raw).title())
            tiles.append({"label": "Lift Type", "value": lp_display,
                          "unit": "", "icon": "lift_path"})
            hero_keys.add("lift_path")
        elif len(tiles) < 4:
            _push("Operating Weight", _weight(), "LB", "weight")

    # ── Mini Ex locked hero — do not alter ───────────────────────────────────
    elif eq == "mini_excavator":
        _push("Operating Weight", _weight(), "LB", "weight")       # slot 1
        _push("Max Dig Depth", _dig_depth(), "", "dig_depth")       # slot 2

        # slot 3: ROPS Type — fallback: cab_type (di → specs) → rops_type (di → specs) → registry
        # full_record may be the raw lookup result (full_record["full_record"]["specs"])
        # or the nested record directly (full_record["specs"]); check both.
        _fr_rec   = (full_record or {})
        _fr_specs = (
            _fr_rec.get("specs")
            or (_fr_rec.get("full_record") or {}).get("specs")
            or {}
        )
        cab_raw = (
            di.get("cab_type") or specs.get("cab_type") or
            di.get("rops_type") or specs.get("rops_type") or
            _fr_specs.get("cab_type") or _fr_specs.get("rops_type") or ""
        ).lower().strip()
        _ROPS = {
            "enclosed": "Enclosed Cab", "erops": "Enclosed Cab", "cab": "Enclosed Cab",
            "canopy": "Open Canopy", "open": "Open Canopy", "rops": "Open Canopy",
            "orops": "Open Canopy",
        }
        rops_display = _ROPS.get(cab_raw, str(cab_raw).title() if cab_raw else None)
        if rops_display and len(tiles) < 4:
            tiles.append({"label": "ROPS Type", "value": rops_display, "unit": "", "icon": "default"})
            hero_keys.add("rops_type")

        # slot 4: Tail Swing Type — Zero Tail / Reduced Tail / Conventional
        ts_raw = specs.get("tail_swing_type") or specs.get("tail_swing") or di.get("tail_swing_type")
        if ts_raw is None and di.get("zero_tail_swing"):
            ts_raw = "zero"
        if ts_raw and len(tiles) < 4:
            ts_val = str(ts_raw).lower()
            if "zero" in ts_val:
                ts_display = "Zero Tail"
            elif any(x in ts_val for x in ("reduced", "minimal", "short")):
                ts_display = "Reduced Tail"
            else:
                ts_display = "Conventional"
            tiles.append({"label": "Tail Swing", "value": ts_display, "unit": "", "icon": "default"})
            hero_keys.add("tail_swing")

    # ── Large Excavator locked hero — do not alter ───────────────────────────
    elif eq in ("large_excavator", "excavator"):
        _push("Operating Weight", _weight(), "LB", "weight")       # slot 1
        _push("Max Dig Depth", _dig_depth(), "", "dig_depth")       # slot 2

        # slot 3: Arm Length — prefer listing value (stick_arm_length_ft), then registry
        arm_ft = di.get("stick_arm_length_ft") or specs.get("stick_arm_length_ft")
        if arm_ft is not None and len(tiles) < 4:
            try:
                arm_display = f"{_fmt_ft_in(float(arm_ft))} Arm"
                tiles.append({"label": "Arm Length", "value": arm_display, "unit": "", "icon": "arm_length"})
                hero_keys.add("arm_length")
            except (TypeError, ValueError):
                pass

        # slot 4: Boom Type — prefer listing value, then registry; normalize to buyer label
        boom_raw = di.get("boom_type") or specs.get("boom_type")
        if boom_raw and len(tiles) < 4:
            _BOOM = {
                "reach":              "Reach Boom",
                "reach_boom":         "Reach Boom",
                "standard":           "Standard Boom",
                "standard_boom":      "Standard Boom",
                "mono_boom":          "Standard Boom",
                "mono boom":          "Standard Boom",
                "mass_excavation":    "Mass Excavation Boom",
                "mass excavation":    "Mass Excavation Boom",
                "mass_excavation_boom": "Mass Excavation Boom",
            }
            b_val = str(boom_raw).lower().strip()
            boom_display = _BOOM.get(b_val)
            if not boom_display:
                boom_display = str(boom_raw).replace("_", " ").title()
                if "boom" not in boom_display.lower():
                    boom_display += " Boom"
            tiles.append({"label": "Boom Type", "value": boom_display, "unit": "", "icon": "default"})
            hero_keys.add("boom_type")

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
            tiles.append({"label": "Boom Type", "value": str(bt).title(), "unit": "", "icon": "default"})
            hero_keys.add("boom_type")

    else:
        # Generic fallback
        _push("Net Power", _hp(), "HP", "hp")
        _push("Operating Weight", _weight(), "LB", "weight")
        _push("Rated Op Capacity", _roc(), "LB", "roc")
        flow_val, is_high = _aux_flow()
        if flow_val and len(tiles) < 4:
            tiles.append({"label": "Aux Flow (High)" if is_high else "Aux Flow (Standard)",
                          "value": flow_val, "unit": "GPM", "icon": "aux_flow"})
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
        tw = specs.get("track_width_in") or specs.get("track_shoe_width_in")
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
        _dd_in = specs.get("max_dig_depth") or specs.get("max_dig_depth_in")
        dd = specs.get("dig_depth_ft") or specs.get("max_dig_depth_ft")
        if dd is None and _dd_in is not None:
            try:
                dd = float(_dd_in) / 12.0
            except (TypeError, ValueError):
                dd = _dd_in   # resolver pre-formatted string; _fmt_ft_in returns it as-is
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

    if eq == "compact_track_loader":
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

    elif eq == "skid_steer":
        # Hinge Pin Height moves to Performance Data for SSL — excluded here.
        # Track Info not applicable (SSL = tires).
        lp_raw = specs.get("lift_path") or specs.get("lift_type")
        if lp_raw and "lift_path" not in hero_keys:
            _LP = {"vertical": "Vertical", "radial": "Radial",
                   "high": "Vertical", "locked": "Vertical"}
            _row("Lift Path", _LP.get(str(lp_raw).lower(), str(lp_raw).title()))
        _width()
        _hyd_pressure()
        _weight_row()
        _serial()

    elif eq == "mini_excavator":
        _dig_depth_row()
        _track_info()
        _hpp()
        _weight_row()
        bt = di.get("blade_type") or specs.get("blade_type")
        if bt and str(bt).lower() not in ("none", ""):
            _row("Blade", str(bt).title())

    elif eq in ("large_excavator", "excavator"):
        # Dig depth, arm length, boom type, max reach, operating weight are in core/hero/performance.
        # Undercarriage % is in the condition section. Serial # is in core.
        # Additional shows supplementary physical data only.
        _track_info()
        bl = di.get("boom_length_ft") or specs.get("boom_length_ft")
        if bl is not None:
            try:
                _row("Boom Length", f"{float(bl):.1f}'")
            except (TypeError, ValueError):
                _row("Boom Length", str(bl))
        dh_in = (specs.get("max_dump_height_in") or specs.get("dump_height_in")
                 or specs.get("hinge_pin_height_in"))
        if dh_in is not None:
            try:
                _row("Max Dump Height", _fmt_ft_in(float(dh_in) / 12.0))
            except (TypeError, ValueError):
                _row("Max Dump Height", str(dh_in))
        _width()
        _hyd_pressure()

    elif eq == "wheel_loader":
        spd = specs.get("travel_speed_mph")
        if spd is not None:
            try:
                _row("Travel Speed", str(round(float(spd), 1)), "MPH")
            except (TypeError, ValueError):
                _row("Travel Speed", str(spd), "MPH")
        xmit = specs.get("transmission_type")
        if xmit:
            _row("Transmission", str(xmit))
        _width()
        bw = specs.get("bucket_width_in")
        if bw is not None:
            try:
                _row("Bucket Width", f'{int(float(bw))}"')
            except (TypeError, ValueError):
                _row("Bucket Width", str(bw))
        _hyd_pressure()
        _weight_row()
        _serial()

    elif eq == "telehandler":
        _weight_row()
        _width()
        _hp_row()
        ct = di.get("cab_type")
        if ct:
            _row("Cab Type", str(ct).title())
        if specs.get("has_stabilizers"):
            _row("Stabilizers", "Yes")
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


def _core_specs(di: dict, specs: dict, eq: str, hours_fmt: str | None) -> list[dict]:
    """
    Build the locked core spec rows (OEM VERIFIED section).

    Hero carries the four substantive specs for CTL and SSL, so core shows
    identity fields only. Mini Ex and Large Ex retain additional core rows
    because their hero slots use different fields.

    CTL (compact_track_loader) — locked, do not alter:
      1. Hours    — listing-driven
      2. Serial # — listing-driven; hidden if blank
      3. Stock #  — listing-driven; hidden if blank
      Hero carries: ROC / Net Power / Aux Flow / Lift Path (or Operating Weight).

    SSL (skid_steer) — locked, identical structure to CTL, do not alter:
      1. Hours
      2. Serial #
      3. Stock #
      Hero carries: ROC / Net Power / Aux Flow / Lift Type (or Operating Weight).

    Mini Ex (mini_excavator) — locked, do not alter:
      1. Hours
      2. Horsepower (HP) — registry-driven
      3. Arm Config      — DealerInput arm_length; omitted if not supplied
      4. Serial #
      5. Stock #
      Hero carries: Operating Weight / Max Dig Depth / ROPS Type / Tail Swing.

    Large Excavator (large_excavator) — locked, up to 7 rows:
      1. Hours
      2. Operating Weight (LB)
      3. Horsepower (HP)
      4. Max Dig Depth
      5. Pad Width — DealerInput track_shoe_width_in preferred over registry
      6. Serial #
      7. Stock #

    Serial/Stock hidden when blank. Empty/missing fields are omitted.
    """
    rows: list[dict] = []

    def _row(label: str, value, unit: str = "") -> None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return
        entry: dict = {"label": label, "value": str(value)}
        if unit:
            entry["unit"] = unit
        rows.append(entry)

    # ── Large Excavator core specs — locked 7-field order ────────────────────
    if eq in ("large_excavator", "excavator"):
        _row("Hours", hours_fmt)

        w = _fmt_int(
            specs.get("operating_weight_lbs") or specs.get("operating_weight_lb")
            or specs.get("machine_weight_lbs")
        )
        _row("Operating Weight", w, "LB")

        hp = _fmt_int(
            specs.get("horsepower_hp") or specs.get("net_hp") or specs.get("engine_hp")
            or specs.get("horsepower_gross_hp")
        )
        _row("Horsepower", hp, "HP")

        dd_ft = specs.get("max_dig_depth_ft") or specs.get("dig_depth_ft")
        if dd_ft is None:
            _dd_in = specs.get("max_dig_depth") or specs.get("max_dig_depth_in")
            if _dd_in is not None:
                try:
                    dd_ft = float(_dd_in) / 12.0
                except (TypeError, ValueError):
                    dd_ft = _dd_in  # pre-formatted string; _fmt_ft_in handles it as-is
        if dd_ft is not None:
            _row("Max Dig Depth", _fmt_ft_in(dd_ft))

        # Pad Width — prefer listing value (track_shoe_width_in), then registry
        pw = di.get("track_shoe_width_in") or specs.get("track_width_in") or specs.get("track_shoe_width_in")
        if pw is not None:
            try:
                _row("Pad Width", f'{int(float(pw))}" Pads')
            except (TypeError, ValueError):
                _row("Pad Width", str(pw))

        _row("Serial #", di.get("serial_number"))
        _row("Stock #", di.get("stock_number"))
        return rows

    # ── Mini Ex core specs ───────────────────────────────────────────────────────
    if eq == "mini_excavator":
        _row("Hours", hours_fmt)

        hp = _fmt_int(
            specs.get("horsepower_hp") or specs.get("net_hp") or specs.get("engine_hp")
        )
        _row("Horsepower", hp, "HP")

        w = specs.get("width_in") or specs.get("overall_width_in")
        if w is not None:
            try:
                _row("Machine Width", f'{int(float(w))}"')
            except (TypeError, ValueError):
                _row("Machine Width", str(w))

        flow = (specs.get("aux_flow_standard_gpm") or specs.get("hydraulic_flow_gpm")
                or specs.get("aux_flow_high_gpm") or specs.get("hi_flow_gpm"))
        if flow is not None:
            _row("Aux Hydraulic Flow", _fmt_int(flow), "GPM")

        arm_raw = di.get("arm_length")
        if arm_raw:
            _ARM = {
                "standard": "Standard Arm", "std": "Standard Arm",
                "long":     "Long Arm",
                "extenda":  "Extenda Arm",
            }
            _row("Arm Config", _ARM.get(str(arm_raw).lower().strip(), str(arm_raw).title()))

        _row("Serial #", di.get("serial_number"))
        _row("Stock #", di.get("stock_number"))
        return rows

    # ── SSL locked core — do not alter ───────────────────────────────────────────
    if eq == "skid_steer":
        _row("Hours", hours_fmt)
        _row("Serial #", di.get("serial_number"))
        _row("Stock #", di.get("stock_number"))
        return rows

    # ── Wheel Loader core specs ───────────────────────────────────────────────────
    if eq == "wheel_loader":
        _row("Hours", hours_fmt)
        _row("Serial #", di.get("serial_number"))
        _row("Stock #", di.get("stock_number"))
        return rows

    # ── CTL core ─────────────────────────────────────────────────────────────────
    _row("Hours", hours_fmt)

    # Machine Width — CTL registry field is width_over_tires_in, not width_in
    w = specs.get("width_over_tires_in") or specs.get("width_in") or specs.get("overall_width_in")
    if w is not None:
        try:
            _row("Machine Width", f'{int(float(w))}"')
        except (TypeError, ValueError):
            _row("Machine Width", str(w))

    _row("Serial #", di.get("serial_number"))
    _row("Stock #", di.get("stock_number"))

    return rows


def _performance_specs(di: dict, specs: dict, eq: str) -> list[dict]:
    """
    Build Performance Data rows.

    CTL (compact_track_loader) — locked, do not alter:
      Row 1: Tipping Load (LB) — always shown when available
      Row 2: High Flow Output (GPM) — only when high_flow == "yes" on unit
      "High Flow Output" (GPM rate) is distinct from "High Flow Equipped" (capability
      in features) and "Aux Hydraulic Flow (High)" (spec sheet core rate).

    SSL (skid_steer) — locked, do not alter:
      Row 1: Tipping Load (LB) — always shown when available  [same as CTL]
      Row 2: Hinge Pin Height  — replaces High Flow Output for SSL

    Mini Ex (mini_excavator) — locked, do not alter:
      Row 1: Max Reach (ft)
      Row 2: Bucket Breakout Force (LB)
      No tipping load for Mini Ex.
    """
    rows: list[dict] = []

    def _row(label: str, value, unit: str = "") -> None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return
        entry: dict = {"label": label, "value": str(value)}
        if unit:
            entry["unit"] = unit
        rows.append(entry)

    # ── Large Excavator performance — Max Reach + Bucket Breakout ────────────
    if eq in ("large_excavator", "excavator"):
        reach = specs.get("max_reach_ft") or specs.get("reach_ft") or specs.get("max_reach_ground_in")
        if reach is not None:
            try:
                # If value looks like inches (> 50), convert to feet
                r_val = float(reach)
                if r_val > 50:
                    r_val = r_val / 12.0
                _row("Max Reach", f"{r_val:.1f}'")
            except (TypeError, ValueError):
                _row("Max Reach", str(reach))
        bbf = (specs.get("bucket_breakout_force_lbs") or specs.get("breakout_force_lbs")
               or specs.get("bucket_dig_force_lbf"))
        _row("Bucket Breakout Force", _fmt_int(bbf), "LB")
        return rows

    # ── Mini Ex performance: Max Reach / Breakout / Arm Force / Pressure / Speed ─
    if eq == "mini_excavator":
        reach = specs.get("max_reach_ft") or specs.get("reach_ft")
        if reach is not None:
            try:
                _row("Max Reach", f"{float(reach):.1f}'")
            except (TypeError, ValueError):
                _row("Max Reach", str(reach))
        bbf = specs.get("bucket_breakout_force_lbs") or specs.get("breakout_force_lbs")
        _row("Bucket Breakout Force", _fmt_int(bbf), "LB")
        adf = (specs.get("arm_digging_force_lbs") or specs.get("arm_dig_force_lbs")
               or specs.get("arm_breakout_force_lbf") or specs.get("arm_breakout_force_lbs"))
        _row("Arm Digging Force", _fmt_int(adf), "LB")
        psi = (specs.get("hydraulic_pressure_psi") or specs.get("aux_pressure_psi")
               or specs.get("main_relief_pressure_psi"))
        if psi is not None:
            try:
                _row("Hydraulic Pressure", f"{int(float(psi)):,}", "PSI")
            except (TypeError, ValueError):
                _row("Hydraulic Pressure", str(psi), "PSI")
        ts_high = (specs.get("travel_speed_high_mph") or specs.get("max_travel_speed_mph")
                   or specs.get("travel_speed_mph"))
        if ts_high is not None:
            try:
                _row("Travel Speed (High)", f"{float(ts_high):.1f}", "MPH")
            except (TypeError, ValueError):
                _row("Travel Speed (High)", str(ts_high), "MPH")
        ts_low = specs.get("travel_speed_low_mph")
        if ts_low is not None:
            try:
                _row("Travel Speed (Low)", f"{float(ts_low):.1f}", "MPH")
            except (TypeError, ValueError):
                _row("Travel Speed (Low)", str(ts_low), "MPH")
        return rows

    # ── CTL + SSL shared row 1: Tipping Load ────────────────────────────────────
    tl = specs.get("tipping_load_lbs") or specs.get("tipping_load_lb")
    _row("Tipping Load", _fmt_int(tl), "LB")

    # ── SSL locked performance row 2: Hinge Pin Height — do not alter ────────────
    if eq == "skid_steer":
        hpp_in = (specs.get("hinge_pin_height_in") or specs.get("bucket_hinge_pin_height_in")
                  or specs.get("dump_height_in"))
        hpp_ft = specs.get("hinge_pin_height_ft") if not hpp_in else None
        if hpp_in:
            try:
                _row("Hinge Pin Height", f'{int(float(hpp_in))}"')
            except (TypeError, ValueError):
                _row("Hinge Pin Height", str(hpp_in))
        elif hpp_ft is not None:
            _row("Hinge Pin Height", _fmt_ft_in(hpp_ft))
    else:
        # CTL row 2: Hinge Pin Height — bucket_hinge_pin_height_in is the CTL registry field
        hpp_in = (specs.get("bucket_hinge_pin_height_in") or specs.get("hinge_pin_height_in")
                  or specs.get("dump_height_in"))
        if hpp_in is not None:
            try:
                _row("Hinge Pin Height", f'{int(float(hpp_in))}"')
            except (TypeError, ValueError):
                _row("Hinge Pin Height", str(hpp_in))
        # CTL row 3: High Flow Output — only shown when this unit has high flow active
        hfo = specs.get("aux_flow_high_gpm") or specs.get("hi_flow_gpm")
        if hfo is not None and di.get("high_flow") == "yes":
            _row("High Flow Output", _fmt_int(hfo), "GPM")

    return rows


def _features(di: dict, eq_type: str) -> list[str]:
    """
    Build a flat list of confirmed feature labels (max 8).

    CTL (compact_track_loader) — locked feature set, do not alter:
      Enclosed Cab / A/C + Heat / High Flow Equipped / 2-Speed /
      Quick Attach / Air Ride Seat / Ride Control / Backup Camera / Radio
      NOTE: "High Flow Equipped" (capability) is CTL-only.
            It is never conflated with "High Flow Output" (GPM in performance).

    SSL (skid_steer) — locked feature set, isolated branch, do not alter:
      Enclosed Cab / A/C + Heat / 2-Speed / Quick Attach / Air Ride Seat /
      Control Type (Hand & Foot / Joystick / EH / SJC) / Ride Control fallback /
      Backup Camera / Radio
      NOTE: "High Flow Equipped" is excluded — not a buyer-facing feature for SSL.

    Mini Ex (mini_excavator) — locked feature set, do not alter:
      Enclosed Cab (with A/C / Heat inline) / Thumb Config / Blade Type /
      Hydraulic Coupler / Aux Hydraulics / 2-Speed / ISO/SAE Pattern Changer
      NOTE: Tail Swing excluded here (already in hero slot 4).

    Universal rules:
      - Attachments do NOT belong in Key Features for any equipment type.
      - Each branch returns independently — no cross-type fallthrough.
    """
    feats: list[str] = []
    eq = (eq_type or "").lower()

    # ── Mini Ex locked feature set ────────────────────────────────────────────
    if eq == "mini_excavator":
        # 1. Cab Type / HVAC — combine into one entry
        cab_raw = (di.get("cab_type") or "").lower().strip()
        if cab_raw in ("enclosed", "erops", "cab"):
            if di.get("ac") and di.get("heater"):
                feats.append("Enclosed Cab — A/C + Heat")
            elif di.get("ac"):
                feats.append("Enclosed Cab — A/C")
            else:
                feats.append("Enclosed Cab")

        # 2. Thumb Configuration — hydraulic thumb is a machine config, not an attachment
        thumb_raw = (di.get("thumb_type") or "").lower().strip()
        _THUMB = {
            "hydraulic": "Hydraulic Thumb", "hyd": "Hydraulic Thumb",
            "pin":       "Pin-On Thumb",    "pin-on": "Pin-On Thumb",
            "manual":    "Pin-On Thumb",
        }
        thumb_label = _THUMB.get(thumb_raw)
        if thumb_label:
            feats.append(thumb_label)

        # 3. Blade Type
        blade_raw = (di.get("blade_type") or "").lower().strip()
        _BLADE = {
            "straight": "Standard Blade", "standard": "Standard Blade",
            "dozer":    "Dozer Blade",
            "angle":    "Angle Blade",
            "6-way":    "6-Way Blade",    "6way": "6-Way Blade", "6_way": "6-Way Blade",
        }
        blade_label = _BLADE.get(blade_raw)
        if blade_label:
            feats.append(blade_label)

        # 4. Hydraulic Coupler
        if (di.get("coupler_type") or "").lower() == "hydraulic":
            feats.append("Hydraulic Coupler")

        # 5. Aux Hydraulics
        if di.get("aux_hydraulics"):
            feats.append("Aux Hydraulics")

        # 6. 2-Speed Travel (optional)
        if di.get("two_speed_travel") == "yes":
            feats.append("2-Speed")

        # 7. Pattern Changer (optional) — do not duplicate Tail Swing from hero
        if di.get("pattern_changer"):
            feats.append("ISO/SAE Pattern Changer")

        # 8. Standard Bucket — only when bucket_type explicitly provided by dealer
        bucket_raw = (di.get("bucket_type") or "").lower().strip()
        if bucket_raw and bucket_raw not in ("none", ""):
            feats.append("Standard Bucket")

        # 9. One Owner — from dealer input flag
        if di.get("one_owner"):
            feats.append("One Owner")

        # Tail Swing excluded (already in hero).
        return feats[:8]

    # ── Large Excavator locked feature set ───────────────────────────────────
    if eq in ("large_excavator", "excavator"):
        # 1. Cab / HVAC — combine into one entry (same pattern as Mini Ex)
        cab_raw = (di.get("cab_type") or "").lower().strip()
        if cab_raw in ("enclosed", "erops", "cab"):
            if di.get("ac") and di.get("heater"):
                feats.append("Enclosed Cab — A/C + Heat")
            elif di.get("ac"):
                feats.append("Enclosed Cab — A/C")
            else:
                feats.append("Enclosed Cab")

        # 2. Grade Control / Tech Package
        gc_raw = (di.get("grade_control_type") or "").strip()
        if gc_raw and gc_raw.lower() != "none":
            _GC = {"2D": "2D Grade Control", "3D": "3D Grade Control"}
            feats.append(_GC.get(gc_raw, f"{gc_raw} Grade Control"))

        # 3. Hydraulic Coupler — type-specific labels
        coupler_raw = (di.get("coupler_type") or "").lower().strip()
        _COUPLER = {
            "hydraulic": "Hydraulic Coupler",
            "manual":    "Manual Coupler",
            "pin-on":    "Pin Grabber Coupler",
        }
        coupler_label = _COUPLER.get(coupler_raw)
        if coupler_label:
            feats.append(coupler_label)

        # 4. Thumb Configuration — machine-installed config, not attachment
        thumb_raw = (di.get("thumb_type") or "").lower().strip()
        _THUMB = {
            "hydraulic": "Hydraulic Thumb",
            "manual":    "Mechanical Thumb",
        }
        thumb_label = _THUMB.get(thumb_raw)
        if thumb_label:
            feats.append(thumb_label)

        # 5. Aux Hydraulics — type-aware label
        aux_type = (di.get("aux_hydraulics_type") or "").lower().strip()
        _AUX = {
            "standard":      "Auxiliary Hydraulics",
            "high_pressure": "High Flow Aux",
            "combined":      "2-Way Aux",
            "hammer":        "Auxiliary Hydraulics",
        }
        aux_label = _AUX.get(aux_type)
        if aux_label:
            feats.append(aux_label)

        # 6. Tail Swing Type (optional — only non-standard types shown)
        ts_raw = di.get("tail_swing_type")
        if ts_raw is None and di.get("zero_tail_swing"):
            ts_raw = "zero"
        if ts_raw:
            ts_val = str(ts_raw).lower()
            if "zero" in ts_val:
                feats.append("Zero Tail Swing")
            elif any(x in ts_val for x in ("reduced", "minimal", "short")):
                feats.append("Reduced Tail Swing")
            # Standard tail not surfaced as a feature

        # 7. Pattern Changer (optional)
        if di.get("pattern_changer"):
            feats.append("ISO/SAE Pattern Changer")

        # Attachments excluded. High Flow, Ride Control, Air Ride excluded for excavator.
        return feats[:8]

    # ── SSL locked feature set — do not alter ────────────────────────────────────
    if eq == "skid_steer":
        if (di.get("cab_type") or "").lower() == "enclosed":
            feats.append("Enclosed Cab")
        if di.get("ac") and di.get("heater"):
            feats.append("A/C + Heat")
        elif di.get("ac"):
            feats.append("A/C")
        elif di.get("heater"):
            feats.append("Heat")
        if di.get("two_speed_travel") == "yes":
            feats.append("2-Speed")
        if di.get("coupler_type"):
            feats.append("Quick Attach")
        if di.get("air_ride_seat"):
            feats.append("Air Ride Seat")
        ct = di.get("control_type")
        if ct:
            _CT_LABELS = {
                "hand_foot": "Hand & Foot Controls",
                "hand foot": "Hand & Foot Controls",
                "hand-foot": "Hand & Foot Controls",
                "joystick":  "Joystick Controls",
                "eh":        "EH Controls",
                "sjc":       "SJC Controls",
            }
            feats.append(_CT_LABELS.get(str(ct).lower().strip(), str(ct).replace("_", " ").title()))
        elif di.get("ride_control"):
            feats.append("Ride Control")
        if di.get("backup_camera") or di.get("rear_camera"):
            feats.append("Backup Camera")
        if di.get("radio"):
            feats.append("Radio")
        return feats[:8]

    # ── Wheel Loader feature set ──────────────────────────────────────────────────
    if eq == "wheel_loader":
        cab_raw = (di.get("cab_type") or "").lower().strip()
        if cab_raw in ("enclosed", "erops", "cab"):
            feats.append("Enclosed Cab")
        if di.get("ac") and di.get("heater"):
            feats.append("A/C + Heat")
        elif di.get("ac"):
            feats.append("A/C")
        elif di.get("heater"):
            feats.append("Heat")
        if di.get("ride_control"):
            feats.append("Ride Control")
        coupler_raw = (di.get("coupler_type") or "").lower().strip()
        if coupler_raw and coupler_raw not in ("none", ""):
            feats.append("Quick Coupler")
        if di.get("backup_camera") or di.get("rear_camera"):
            feats.append("Backup Camera")
        if di.get("radio"):
            feats.append("Radio")
        if di.get("air_ride_seat"):
            feats.append("Air Ride Seat")
        aux_type = (di.get("aux_hydraulics_type") or "").lower().strip()
        if aux_type and aux_type not in ("none", ""):
            feats.append("Auxiliary Hydraulics")
        elif di.get("aux_hydraulics"):
            feats.append("Auxiliary Hydraulics")
        return feats[:8]

    # ── CTL locked feature set — do not alter ────────────────────────────────────
    # Cab
    if (di.get("cab_type") or "").lower() == "enclosed":
        feats.append("Enclosed Cab")

    # Climate
    if di.get("ac") and di.get("heater"):
        feats.append("A/C + Heat")
    elif di.get("ac"):
        feats.append("A/C")
    elif di.get("heater"):
        feats.append("Heat")

    # High Flow capability — CTL benchmark label
    if di.get("high_flow") == "yes":
        feats.append("High Flow Equipped")

    if di.get("two_speed_travel") == "yes":
        feats.append("2-Speed")

    # Coupler — always "Quick Attach" per locked architecture
    if di.get("coupler_type"):
        feats.append("Quick Attach")

    # Comfort
    if di.get("air_ride_seat"):
        feats.append("Air Ride Seat")

    if di.get("ride_control"):
        feats.append("Ride Control")

    if di.get("backup_camera") or di.get("rear_camera"):
        feats.append("Backup Camera")
    if di.get("radio"):
        feats.append("Radio")

    # Attachments excluded from Key Features for all equipment types per CTL benchmark rule.

    # Backhoe thumb/hammer (large_excavator has its own feature branch above)
    if eq == "backhoe_loader":
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
    # Normalize short-code aliases to canonical registry eq types.
    _EQ_NORMALIZE = {
        "ctl":               "compact_track_loader",
        "ssl":               "skid_steer",
        "skid_steer_loader": "skid_steer",
        "mini ex":           "mini_excavator",
        "mini_ex":           "mini_excavator",
        "backhoe":           "backhoe_loader",
        "large ex":          "large_excavator",
        "large_ex":          "large_excavator",
    }
    eq = _EQ_NORMALIZE.get(eq, eq)

    cat = _EQ_TYPE_DISPLAY.get(eq, eq.replace("_", " ").title()) if eq else ""
    theme = ((dealer_info or {}).get("accent_color") or "yellow").lower()

    # Logo
    logo_path = (dealer_info or {}).get("logo_path")
    logo_uri  = _logo_data_uri(logo_path)

    # Contact
    raw_phone = (dealer_contact or {}).get("phone") or ""
    phone    = _fmt_phone(raw_phone) if raw_phone else ""
    location = (dealer_contact or {}).get("location") or ""
    d_name   = (dealer_contact or {}).get("dealer_name") or ""
    website  = (dealer_info or {}).get("website") or ""

    # Hours (pre-formatted for reuse in core specs and condition section)
    hours_raw = di.get("hours")
    hours_fmt = _fmt_int(hours_raw) if hours_raw is not None else None

    hero_tiles, hero_keys = _hero_specs(di, specs, eq, fr)
    add_rows  = _additional_specs(di, specs, eq, hero_keys)
    core_rows = _core_specs(di, specs, eq, hours_fmt)
    perf_rows = _performance_specs(di, specs, eq)

    # CTL readiness guard — flag weak/stub records so callers can suppress the OEM badge
    oem_verified = True
    ctl_spec_sheet_confidence: str | None = None
    if eq == "compact_track_loader":
        ready = _ctl_is_spec_ready(specs, fr)
        ctl_spec_sheet_confidence = "full" if ready else "limited"
        oem_verified = ready

    # Condition section: undercarriage % for excavators, track % for others
    if eq in ("large_excavator", "excavator"):
        uc_pct = di.get("undercarriage_percent_remaining")
        track_pct_val  = f"{uc_pct}%" if uc_pct is not None else None
        track_label_val = "Undercarriage % Remaining"
    elif eq in ("skid_steer", "wheel_loader"):
        _tp = di.get("track_percent_remaining")
        track_pct_val  = f"{_tp}%" if _tp is not None else None
        track_label_val = "Tire % Remaining"
    else:
        _tp = di.get("track_percent_remaining")
        track_pct_val  = f"{_tp}%" if _tp is not None else None
        track_label_val = "Track % Remaining"

    return {
        "machine": {
            "year":       di.get("year"),
            "make":       (di.get("make") or "").upper(),
            "model":      di.get("model") or "",
            "category":   cat,
            "photo_path": photo_path,
        },
        "listing": {
            "price_usd":       di.get("asking_price"),
            "hours":           hours_raw,
            "hours_qualifier": di.get("hours_qualifier"),
            "condition":       di.get("condition_grade"),
            "track_pct":       track_pct_val,
            "track_label":     track_label_val,
            "notes":           di.get("condition_notes") or di.get("additional_details"),
            "stock_number":    di.get("stock_number"),  # not in DealerInput v1 — None
        },
        "specs": {
            "hero":        hero_tiles,
            "core":        core_rows,
            "additional":  add_rows,
            "performance": perf_rows,
        },
        "features": _features(di, eq),
        "dealer": {
            "name":          d_name,
            "phone":         phone,
            "website":       website,
            "location":      location,
            "logo_data_uri": logo_uri,
            "theme":         theme,
        },
        "oem_verified":              oem_verified,
        "ctl_spec_sheet_confidence": ctl_spec_sheet_confidence,
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
        log.info("[spec_sheet_renderer] render_spec_sheet() start")
        html_str = render_spec_sheet(data)
        log.info(
            "[spec_sheet_renderer] HTML generated: %d chars | first 120: %s",
            len(html_str),
            html_str[:120].replace("\n", " "),
        )
        # Dump full HTML to a debug file alongside the output so it can be inspected.
        _debug_html = Path(output_path).with_suffix(".debug.html")
        try:
            _debug_html.parent.mkdir(parents=True, exist_ok=True)
            _debug_html.write_text(html_str, encoding="utf-8")
            log.info("[spec_sheet_renderer] debug HTML written -> %s", _debug_html)
        except Exception as _he:
            log.warning("[spec_sheet_renderer] could not write debug HTML: %s", _he)

        log.info("[spec_sheet_renderer] launching Playwright screenshot -> %s", output_path)
        _screenshot_spec_sheet(html_str, output_path)
        log.info("[spec_sheet_renderer] screenshot SUCCESS -> %s", output_path)
        return output_path
    except Exception as exc:
        log.error(
            "[spec_sheet_renderer] export FAILED: %s",
            exc,
            exc_info=True,
        )
        if not fail_silently:
            raise
        return None


def _screenshot_spec_sheet(html_str: str, output_path: Path) -> None:
    """Render HTML to PNG: 540px CSS × 4:5 aspect-ratio at device_scale_factor=2.0 → 1080×1350 px."""
    from playwright.sync_api import sync_playwright

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _render() -> None:
        log.info("[spec_sheet_pw] sync_playwright() enter")
        with sync_playwright() as pw:
            log.info("[spec_sheet_pw] launching Chromium headless")
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:
                log.error("[spec_sheet_pw] Chromium launch FAILED: %s", exc)
                raise
            log.info("[spec_sheet_pw] Chromium launched OK")
            try:
                page = browser.new_page(
                    viewport={"width": 560, "height": 700},
                    device_scale_factor=2.0,
                )
                # Use "domcontentloaded" instead of "networkidle" to avoid hanging
                # when the Google Fonts request stalls in a restricted environment.
                log.info("[spec_sheet_pw] set_content() start (wait_until=domcontentloaded)")
                page.set_content(html_str, wait_until="domcontentloaded")
                log.info("[spec_sheet_pw] set_content() done")
                el = page.query_selector(".sheet")
                if el is None:
                    # Log the first 300 chars of rendered body for diagnosis.
                    body_text = page.evaluate("document.body && document.body.innerHTML.slice(0, 300)")
                    log.error(
                        "[spec_sheet_pw] '.sheet' selector NOT FOUND. Body preview: %s",
                        body_text,
                    )
                    raise RuntimeError("'.sheet' selector not found in rendered spec sheet HTML")
                log.info("[spec_sheet_pw] '.sheet' element found, taking screenshot")
                el.screenshot(path=str(output_path))
                log.info("[spec_sheet_pw] screenshot written to %s", output_path)
            finally:
                browser.close()
                log.info("[spec_sheet_pw] browser closed")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_render).result()
