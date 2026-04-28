"""
card_renderer_adapter.py
========================
Thin adapter between the MTM listing pipeline and card_renderer.render_card().

Bridges the existing pipeline data shapes (full_record dict + DealerInput) to
the v10 renderer's structured { machine / dealer / listing } payload.

Public API
----------
adapt_dealer_input(dealer_input, image_input_paths, *, theme) -> dict
    Build the renderer's listing + photo fields from a DealerInput + photo paths.

export_listing_card(full_record, dealer_dict, output_path, *, fail_silently) -> Path | None
    Full render + Playwright PNG export. Returns output_path on success,
    None on failure when fail_silently=True (default).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from card_renderer import render_card

if TYPE_CHECKING:
    from dealer_input import DealerInput

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Spec formatting helpers (adapter-local)
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_ft_in(feet: float | None) -> str | None:
    """Convert decimal feet to a display string like 9' 11\" or 19'."""
    if feet is None:
        return None
    f_int = int(feet)
    inches = round((feet - f_int) * 12)
    if inches == 12:
        f_int += 1
        inches = 0
    return f"{f_int}' {inches}\"" if inches else f"{f_int}'"


def _dig_depth_str(specs: dict) -> str | None:
    """Return formatted dig depth string from raw registry specs."""
    val_in = specs.get("max_dig_depth_in")   # excavator / mini_ex: stored in inches
    if val_in is not None:
        return _fmt_ft_in(float(val_in) / 12.0)
    val_ft = specs.get("max_dig_depth_ft")   # backhoe_loader: stored in feet
    if val_ft is not None:
        return _fmt_ft_in(float(val_ft))
    return None


def _fmt_yd3_str(v: float | None) -> str | None:
    """Format a cubic-yard capacity value as a short display string (e.g. 1.75 → '1.75')."""
    if v is None:
        return None
    fv = float(v)
    return str(int(fv)) if fv == int(fv) else f"{fv:.2f}".rstrip("0")


# ─────────────────────────────────────────────────────────────────────────────
# Adapters
# ─────────────────────────────────────────────────────────────────────────────

def adapt_dealer_input(
    dealer_input: "DealerInput",
    image_input_paths: list[str],
    *,
    theme: str = "yellow",
    dealer_info: "dict | None" = None,
    featured_template: "str | None" = None,
) -> dict:
    """
    Build the renderer data dict from a validated DealerInput object.

    Parameters
    ----------
    dealer_input       : Validated DealerInput from the form.
    image_input_paths  : Ordered list of uploaded photo filesystem paths.
                         First path is used as the machine photo_path.
    theme              : Dealer theme ("yellow" | "red" | "blue" | "green" | "orange").
                         Sourced from dealer_info["accent_color"]; defaults to "yellow".

    Returns
    -------
    dict ready to pass as the 'dealer_dict' argument of export_listing_card().
    Keys: photo_path, listing_price, listing_hours, theme, high_flow.
    """
    high_flow_raw: Any = getattr(dealer_input, "high_flow", None)
    info = dealer_info or {}
    # Featured template — explicit kwarg wins, then dealer_info, then default.
    chosen_template = (
        featured_template
        or info.get("featured_template")
        or "price_tag"
    )
    return {
        "photo_path":     image_input_paths[0] if image_input_paths else None,
        "listing_price":  getattr(dealer_input, "asking_price", None),
        "listing_hours":  dealer_input.hours,
        "year":           dealer_input.year,
        "theme":          theme,
        # Kept for callers that still inspect this flag directly
        "high_flow":      (high_flow_raw == "yes"),
        # Dealer identity — drives the dealer badge in templates that show it.
        "dealer_name":    info.get("dealer_name") or info.get("name"),
        "dealer_rep":     info.get("contact_name") or info.get("rep"),
        "dealer_phone":   info.get("phone"),
        "dealer_location":info.get("location") or info.get("city"),
        "dealer_logo":    info.get("logo_path") or info.get("logo"),
        "show_branding":  info.get("show_branding", True),
        "featured_template": chosen_template,
    }


def _build_render_payload(full_record: dict, dealer_dict: dict) -> dict:
    """
    Assemble the { machine / dealer / listing } dict expected by render_card().
    """
    specs = full_record.get("specs") or {}
    flags = full_record.get("feature_flags") or {}

    # high_flow_available: prefer registry feature flag; fall back to dealer-entered bool
    high_flow_flag = flags.get("high_flow_available")
    if high_flow_flag is None:
        high_flow_flag = bool(dealer_dict.get("high_flow", False))

    make = (
        full_record.get("make")
        or full_record.get("manufacturer")
        or ""
    ).upper()

    eq_type = (full_record.get("equipment_type") or "").lower()

    return {
        "machine": {
            "year":                         dealer_dict.get("year") or full_record.get("year"),
            "make":                         make,
            "model":                        full_record.get("model") or "",
            "equipment_type":               eq_type,
            # CTL / SSL columns
            "horsepower_hp":                specs.get("horsepower_hp"),
            "rated_operating_capacity_lbs": specs.get("rated_operating_capacity_lbs"),
            "aux_flow_standard_gpm":        specs.get("aux_flow_standard_gpm"),
            "aux_flow_high_gpm":            specs.get("aux_flow_high_gpm"),
            "feature_flags": {
                "high_flow_available": high_flow_flag,
            },
            # Non-CTL columns (pre-formatted where needed)
            "net_hp":                   specs.get("horsepower_hp") or specs.get("net_power_hp"),
            "operating_weight_lb":      specs.get("operating_weight_lbs"),
            "lift_capacity_lb":         specs.get("lift_capacity_lbs") or specs.get("max_lift_capacity_lbs"),
            "max_lift_height_ft_str":   _fmt_ft_in(specs.get("lift_height_ft")),
            "max_forward_reach_ft_str": _fmt_ft_in(specs.get("forward_reach_ft")),
            "max_dig_depth_str":        _dig_depth_str(specs),
            "bucket_capacity_yd3":      _fmt_yd3_str(specs.get("bucket_capacity_yd3")),
            "blade_capacity_yd3":       _fmt_yd3_str(specs.get("blade_capacity_yd3")),
            "platform_height_ft_str":   _fmt_ft_in(specs.get("platform_height_ft")),
            "platform_capacity_lbs":    specs.get("platform_capacity_lbs"),
            "platform_width_ft_str":    _fmt_ft_in(specs.get("platform_width_ft")),
            "horizontal_reach_ft_str":  _fmt_ft_in(specs.get("horizontal_reach_ft")),
            "photo_path": dealer_dict.get("photo_path"),
        },
        "dealer": {
            "theme":         dealer_dict.get("theme") or "yellow",
            "name":          dealer_dict.get("dealer_name"),
            "rep":           dealer_dict.get("dealer_rep"),
            "phone":         dealer_dict.get("dealer_phone"),
            "location":      dealer_dict.get("dealer_location"),
            "logo_path":     dealer_dict.get("dealer_logo"),
            "show_branding": dealer_dict.get("show_branding", True),
        },
        "listing": {
            "price_usd": dealer_dict.get("listing_price") or dealer_dict.get("price"),
            "hours":     dealer_dict.get("listing_hours") or dealer_dict.get("hours"),
        },
        "featured_template": dealer_dict.get("featured_template") or "price_tag",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

def export_listing_card(
    full_record: dict,
    dealer_dict: dict,
    output_path: Path,
    *,
    fail_silently: bool = True,
) -> Path | None:
    """
    Render the v10 hero listing card and export it to a PNG via Playwright.

    Parameters
    ----------
    full_record   : Raw registry record from lookup_machine()['full_record'].
                    Must have top-level keys: manufacturer/make, model, specs,
                    feature_flags.
    dealer_dict   : Pre-adapted dealer dict (from adapt_dealer_input()).
    output_path   : Destination path for the card PNG.
    fail_silently : If True (default), log errors and return None instead of
                    raising. Set False in tests to surface full tracebacks.

    Returns
    -------
    output_path on success, None on failure (when fail_silently=True).
    """
    try:
        payload  = _build_render_payload(full_record, dealer_dict)
        html_str = render_card(payload)
        _screenshot_card(html_str, output_path)
        log.info("[card] exported %s", output_path)
        return output_path
    except Exception as exc:
        log.warning("[card] export failed: %s", exc, exc_info=True)
        if not fail_silently:
            raise
        return None


def _screenshot_card(html_str: str, output_path: Path) -> None:
    """
    Render HTML to PNG using Playwright headless Chromium.

    Card CSS is 1080×1350 (the design's native 4:5 frame). At
    device_scale_factor 1.0 the element screenshot is exactly 1080×1350 px
    (Facebook portrait recommended size).

    Fonts load via Google Fonts CDN; wait_until="networkidle" ensures they
    render before capture.
    """
    import concurrent.futures
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _playwright_render() -> None:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": 1100, "height": 1400},
                    device_scale_factor=1.0,
                )
                page.set_content(html_str, wait_until="networkidle")
                card_el = page.query_selector(".card")
                if card_el is None:
                    raise RuntimeError("'.card' selector not found in rendered HTML")
                card_el.screenshot(path=str(output_path))
            finally:
                browser.close()

    # sync_playwright creates its own event loop internally and will raise
    # "Please use the Async API instead" if called inside FastAPI's asyncio loop.
    # Running in a ThreadPoolExecutor worker gives it a clean, loop-free context.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_playwright_render).result()
