"""
card_renderer_adapter.py
========================
Thin adapter between the MTM listing pipeline and card_renderer.render_card().

Resolves 5 schema mismatches identified during integration audit (2026-04-17):

  1. machine_record shape  — renderer expects the raw registry full_record dict
                             (with 'specs', 'feature_flags', 'field_confidence'),
                             not a MachineRecord scorer dataclass
  2. make key name         — full_record uses 'manufacturer'; renderer calls .get('make')
  3. price key name        — DealerInput uses 'asking_price'; renderer expects 'price'
  4. photo_path source     — not on DealerInput; taken from image_input_paths[0]
  5. high_flow type        — DealerInput stores "yes"/"no"/"optional"/None (str);
                             renderer badge condition tests == True (bool)

Public API
----------
adapt_dealer_input(dealer_input, image_input_paths) -> dict
    Build the renderer's dealer dict from a DealerInput + photo path list.
    Call this before passing to export_listing_card().

export_listing_card(full_record, dealer_dict, output_path, fail_silently) -> Path | None
    Full render + Playwright PNG export. Returns output_path on success,
    None on failure when fail_silently=True (default).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from card_renderer import render_card

if TYPE_CHECKING:
    from dealer_input import DealerInput

log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).with_name("card_spec_hierarchy.json")


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


# Loaded once at import time; safe because the file is read-only at runtime.
_CARD_CONFIG: dict = _load_config()


# ─────────────────────────────────────────────────────────────────────────────
# Adapters
# ─────────────────────────────────────────────────────────────────────────────

def _adapt_machine_record(full_record: dict) -> dict:
    """Inject 'make' alias for 'manufacturer' so renderer .get('make') resolves."""
    record = dict(full_record)
    if "make" not in record:
        record["make"] = record.get("manufacturer", "")
    return record


def adapt_dealer_input(dealer_input: "DealerInput", image_input_paths: list[str]) -> dict:
    """
    Build the renderer's dealer dict from a validated DealerInput object.

    Parameters
    ----------
    dealer_input       : Validated DealerInput from the form.
    image_input_paths  : Ordered list of uploaded photo filesystem paths.
                         First path is used as photo_path for the card.

    Returns
    -------
    dict with keys: year, hours, price, photo_path, high_flow
    """
    high_flow_raw: Any = getattr(dealer_input, "high_flow", None)
    return {
        "year":       dealer_input.year,
        "hours":      dealer_input.hours,
        "price":      getattr(dealer_input, "asking_price", None),
        "photo_path": image_input_paths[0] if image_input_paths else None,
        # DealerInput.high_flow is Optional[str]: "yes"/"no"/"optional"/None
        "high_flow":  (high_flow_raw == "yes"),
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
    Render the listing card HTML and export it to a PNG via Playwright.

    Parameters
    ----------
    full_record     : Raw registry record from lookup_machine()['full_record'].
                      Must have top-level keys: equipment_type, manufacturer,
                      model, specs, feature_flags, field_confidence.
    dealer_dict     : Pre-adapted dealer dict (from adapt_dealer_input()).
                      Keys: year, hours, price, photo_path, high_flow.
    output_path     : Destination path for the card PNG.
    fail_silently   : If True (default), log errors and return None instead of
                      raising. Set False in tests to surface full tracebacks.

    Returns
    -------
    output_path on success, None on failure (when fail_silently=True).
    """
    try:
        adapted_record = _adapt_machine_record(full_record)
        html_str = render_card(adapted_record, _CARD_CONFIG, dealer_dict)
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

    Viewport 450×560 at device_scale_factor=2.4 produces ~1080×1344 output
    (Facebook portrait format). Screenshot targets the .card selector only,
    not the full page. Fonts load via Google Fonts CDN; wait_until="networkidle"
    ensures they render before capture.
    """
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": 450, "height": 560},
                device_scale_factor=2.4,
            )
            page.set_content(html_str, wait_until="networkidle")
            card_el = page.query_selector(".card")
            if card_el is None:
                raise RuntimeError("'.card' selector not found in rendered HTML")
            card_el.screenshot(path=str(output_path))
        finally:
            browser.close()
