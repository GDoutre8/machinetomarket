"""spec_sheet_context.py
======================
Shared spec sheet context builder and Playwright screenshot helper.

Used by both app.py (browser route) and listing_pack_builder.py (export PNG)
so the exported spec sheet is pixel-identical to the in-app view.
"""

from __future__ import annotations
import base64
import os
from pathlib import Path

# ─── Display mappings ─────────────────────────────────────────────────────────

_EQ_TYPE_DISPLAY = {
    "compact_track_loader": "Compact Track Loader",
    "skid_steer":           "Skid Steer Loader",
    "mini_excavator":       "Mini Excavator",
    "backhoe_loader":       "Backhoe Loader",
    "large_excavator":      "Large Excavator",
}

_LIFT_PATH_DISPLAY = {
    "vertical": "Vertical",
    "radial":   "Radial",
    "high":     "Vertical",
    "locked":   "Vertical",
}

_CONTROL_DISPLAY = {
    "joystick":  "Joystick",
    "hand_foot": "Hand/Foot",
    "pilot":     "Pilot",
    "iso":       "ISO",
    "h":         "H-Pattern",
}


def _fmt_number(value: object) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and value.is_integer():
            return f"{int(value):,}"
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _logo_is_light(logo_path: str) -> bool:
    """Corner-sample 8×8px from each corner; light if avg brightness > 200.
    Matches dealer_badge_renderer.js detectWhiteLogo() exactly."""
    try:
        from PIL import Image as _PILImage
        img = _PILImage.open(logo_path).convert("RGBA")
        w, h = img.size
        size = 8
        corners = [
            (0, 0),
            (max(0, w - size), 0),
            (0, max(0, h - size)),
            (max(0, w - size), max(0, h - size)),
        ]
        total, count = 0, 0
        for cx, cy in corners:
            patch = img.crop((cx, cy, min(w, cx + size), min(h, cy + size)))
            for r, g, b, a in patch.getdata():
                if a > 10:
                    total += (r + g + b) / 3
                    count += 1
        return count > 0 and (total / count) > 200
    except Exception:
        return False


def build_spec_sheet_context(
    dealer_input_data: dict,
    resolved_specs: dict,
    ui_hints: dict,
    equipment_type: str,
    dealer_contact: dict,
    session_id: str,
    outputs_dir: str = "",
    logo_as_data_uri: bool = False,
) -> dict:
    """
    Assemble the full Jinja2 context dict for spec_sheet.html.

    Parameters
    ----------
    logo_as_data_uri
        When True the dealer logo is embedded as a base64 data URI instead of
        a web-relative URL.  Use this for offline Playwright export so no live
        server is required.
    outputs_dir
        Absolute path to the outputs/ directory (needed for logo path lookup
        when logo_filename is a relative name rather than an absolute path).
    """
    di = dealer_input_data
    rs = resolved_specs

    year  = di.get("year")
    make  = (di.get("make") or "").strip()
    model = (di.get("model") or "").strip()

    eq_display = _EQ_TYPE_DISPLAY.get(
        (equipment_type or "").lower(),
        (equipment_type or "").replace("_", " ").title(),
    )

    serial_number = di.get("serial_number") or rs.get("serial_number") or None
    location      = dealer_contact.get("location") or None

    # ── Headline strip ────────────────────────────────────────────────────────
    headline_cells = []
    roc = rs.get("roc_lb") or rs.get("rated_operating_capacity_lbs")
    if roc is not None:
        headline_cells.append({"label": "ROC", "value": _fmt_number(roc), "unit": "LB"})
    net_hp = rs.get("net_hp") or rs.get("horsepower_hp")
    if net_hp is not None:
        headline_cells.append({
            "label": "Net Power",
            "value": str(int(net_hp)) if isinstance(net_hp, float) and net_hp.is_integer() else str(net_hp),
            "unit": "HP",
        })
    aux_flow = rs.get("hydraulic_flow_gpm") or rs.get("aux_flow_standard_gpm")
    if aux_flow is not None:
        headline_cells.append({
            "label": "Aux Flow",
            "value": str(int(aux_flow)) if isinstance(aux_flow, float) and aux_flow.is_integer() else str(round(aux_flow, 1)),
            "unit": "GPM",
        })
    hours = di.get("hours")
    if hours is not None:
        headline_cells.append({"label": "Hours", "value": _fmt_number(hours), "unit": "HRS"})

    # ── Spec rows ─────────────────────────────────────────────────────────────
    spec_rows = []
    _eq = (equipment_type or "").lower()

    lift_raw = rs.get("lift_path")
    if lift_raw:
        lift_display = _LIFT_PATH_DISPLAY.get(str(lift_raw).lower(), str(lift_raw).title())
        spec_rows.append({"key": "Lift Path", "value": lift_display, "unit": ""})

    op_weight = rs.get("operating_weight_lb") or rs.get("operating_weight_lbs")
    if op_weight is not None:
        spec_rows.append({"key": "Op Weight", "value": _fmt_number(op_weight), "unit": "LB"})

    hinge_pin = rs.get("bucket_hinge_pin_height_in")
    if hinge_pin is not None:
        spec_rows.append({
            "key": "Hinge Pin",
            "value": str(int(hinge_pin)) if isinstance(hinge_pin, float) and hinge_pin.is_integer() else str(round(hinge_pin, 1)),
            "unit": "IN",
        })

    if _eq == "mini_excavator":
        width = rs.get("width_in")
    else:
        width = rs.get("width_over_tires_in") or rs.get("width_in")
    if width is not None:
        spec_rows.append({
            "key": "Width",
            "value": str(int(width)) if isinstance(width, float) and width.is_integer() else str(round(width, 1)),
            "unit": "IN",
        })

    hi_flow_gpm = rs.get("hi_flow_gpm") or rs.get("aux_flow_high_gpm")
    if hi_flow_gpm is not None:
        spec_rows.append({
            "key": "High Flow",
            "value": str(int(hi_flow_gpm)) if isinstance(hi_flow_gpm, float) and hi_flow_gpm.is_integer() else str(round(hi_flow_gpm, 1)),
            "unit": "GPM",
        })

    hyd_psi = rs.get("hydraulic_pressure_standard_psi") or rs.get("hydraulic_pressure_psi")
    if hyd_psi is not None:
        spec_rows.append({"key": "Hyd Pressure", "value": _fmt_number(hyd_psi), "unit": "PSI"})

    ctrl = di.get("control_type") or rs.get("controls_type") or rs.get("control_pattern")
    if ctrl:
        ctrl_display = _CONTROL_DISPLAY.get(str(ctrl).lower(), str(ctrl).title())
        spec_rows.append({"key": "Controls", "value": ctrl_display, "unit": ""})

    # ── Feature chips ─────────────────────────────────────────────────────────
    feature_chips = []
    if di.get("high_flow") == "yes":
        feature_chips.append({"label": "High Flow", "premium": True})
    if di.get("two_speed_travel") == "yes":
        feature_chips.append({"label": "2-Speed", "premium": True})
    if di.get("cab_type") == "enclosed":
        feature_chips.append({"label": "Enclosed Cab", "premium": True})
    if di.get("ac"):
        feature_chips.append({"label": "A/C + Heat", "premium": True})
    if di.get("ride_control"):
        feature_chips.append({"label": "Ride Control", "premium": False})
    if di.get("coupler_type") == "hydraulic":
        feature_chips.append({"label": "Hyd Quick Attach", "premium": False})
    if di.get("backup_camera"):
        feature_chips.append({"label": "Backup Camera", "premium": False})
    if di.get("heater") and not di.get("ac"):
        feature_chips.append({"label": "Heat", "premium": False})

    # ── Condition stats ───────────────────────────────────────────────────────
    condition_stats = []
    track_cond = di.get("track_condition") or rs.get("track_condition")
    if track_cond:
        condition_stats.append({"label": "Tracks", "value": str(track_cond)})
    undercarriage_pct = rs.get("undercarriage_percent") or di.get("undercarriage_condition_pct")
    if undercarriage_pct is not None:
        condition_stats.append({"label": "Undercarriage", "value": f"{undercarriage_pct}%"})
    condition_overall = rs.get("condition_overall")
    if condition_overall:
        condition_stats.append({"label": "Overall", "value": str(condition_overall)})

    n = len(condition_stats)
    condition_grid_class = {1: "one-up", 2: "two-up", 3: "three-up"}.get(n, "two-up")

    dealer_notes = (di.get("condition_notes") or di.get("additional_details") or "").strip() or None

    # ── Dealer footer ─────────────────────────────────────────────────────────
    contact_name  = dealer_contact.get("contact_name") or dealer_contact.get("dealer_name") or ""
    contact_phone = dealer_contact.get("contact_phone") or dealer_contact.get("phone") or ""
    dealer_role   = dealer_contact.get("dealer_role") or ""

    logo_filename = dealer_contact.get("logo_filename")
    logo_path = None
    if logo_filename:
        # Accept absolute path directly
        if os.path.isabs(logo_filename) and os.path.isfile(logo_filename):
            logo_path = logo_filename
        elif outputs_dir and session_id:
            candidate = os.path.join(outputs_dir, session_id, logo_filename)
            if os.path.isfile(candidate):
                logo_path = candidate

    dealer_logo_url = None
    badge_style   = "dark"
    logo_bg       = "dark"
    divider_color = "yellow"
    if logo_path:
        if logo_as_data_uri:
            ext  = Path(logo_path).suffix.lower().lstrip(".")
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
            with open(logo_path, "rb") as _f:
                b64 = base64.b64encode(_f.read()).decode()
            dealer_logo_url = f"data:image/{mime};base64,{b64}"
        else:
            dealer_logo_url = f"/outputs/{session_id}/{logo_filename}"
        if _logo_is_light(logo_path):
            badge_style   = "white"
            logo_bg       = "white"
            divider_color = "red"
        else:
            logo_bg = "yellow"

    words = [w for w in (contact_name or "").split() if w]
    dealer_initials = "".join(w[0].upper() for w in words[:2]) or "?"

    return {
        "year":                   year,
        "make":                   make,
        "model":                  model,
        "equipment_type_display": eq_display,
        "serial_number":          serial_number,
        "location":               location,
        "headline_cells":         headline_cells,
        "spec_rows":              spec_rows,
        "feature_chips":          feature_chips,
        "condition_stats":        condition_stats,
        "condition_grid_class":   condition_grid_class,
        "dealer_notes":           dealer_notes,
        "dealer_name":            contact_name or "Your Dealer",
        "dealer_role":            dealer_role,
        "dealer_phone":           contact_phone,
        "dealer_logo_url":        dealer_logo_url,
        "dealer_initials":        dealer_initials,
        "badge_style":            badge_style,
        "logo_bg":                logo_bg,
        "divider_color":          divider_color,
    }


def screenshot_spec_sheet(
    dealer_input_data: dict,
    resolved_specs: dict,
    ui_hints: dict,
    equipment_type: str,
    dealer_contact: dict,
    session_id: str,
    outputs_dir: str,
    output_path: str,
) -> None:
    """
    Render spec_sheet.html to a PNG via Playwright headless Chromium.

    Uses the identical context builder as the /build-listing/spec-sheet/{id}
    browser route — guaranteed single source of truth for spec sheet content.

    The dealer logo (if any) is embedded as a base64 data URI so no live
    server is required during pack assembly.

    Viewport 500×900 at device_scale_factor=2 captures the 440 px wide .sheet
    element at high resolution (≈880 px effective width).
    """
    import concurrent.futures
    import jinja2
    from playwright.sync_api import sync_playwright

    print(">>> USING NEW SPEC SHEET PIPELINE")

    ctx = build_spec_sheet_context(
        dealer_input_data=dealer_input_data,
        resolved_specs=resolved_specs,
        ui_hints=ui_hints,
        equipment_type=equipment_type,
        dealer_contact=dealer_contact,
        session_id=session_id,
        outputs_dir=outputs_dir,
        logo_as_data_uri=True,
    )

    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir), autoescape=True)
    html_str = env.get_template("spec_sheet.html").render(**ctx)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    def _playwright_render() -> None:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": 500, "height": 900},
                    device_scale_factor=2.0,
                )
                page.set_content(html_str, wait_until="networkidle")
                sheet_el = page.query_selector(".sheet")
                if sheet_el is None:
                    raise RuntimeError("'.sheet' selector not found in rendered spec sheet HTML")
                sheet_el.screenshot(path=str(output_path))
            finally:
                browser.close()

    # sync_playwright creates its own event loop internally and will raise
    # "Please use the Async API instead" if called directly inside FastAPI's
    # asyncio loop.  Running it in a ThreadPoolExecutor worker thread gives it
    # a clean context with no active event loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_playwright_render).result()
