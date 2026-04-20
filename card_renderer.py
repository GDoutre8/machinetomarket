"""
MTM Listing Card Renderer — Reference Implementation

Renders Option C (Frame / Trading Card) 4:5 Facebook listing cards
for MTM. Consumes a resolved MachineRecord (pipeline output),
the card_spec_hierarchy.json config, and a DealerInput dict.
Returns fully-populated HTML ready for Playwright PNG export.

Design reference: mtm_card_c.html
Config reference: card_spec_hierarchy.json (post-2026-04-17 corrections)

Author notes for Claude Code integration:

- Assumes MachineRecord is POST-normalization (pipeline output names,
  not raw registry storage names). The MEX hydraulic_flow_gpm
  translation happens upstream in listing_use_case_enrichment.py.
- Confidence values are assumed to live on the record at
  machine_record['field_confidence'][field_name]. Adjust the accessor
  in _get_confidence() if the actual schema differs.
- feature_flags fields are accessed via machine_record['feature_flags']
  and are exempt from the confidence gate (require_confidence: NONE).
- Photo is embedded as base64 data URI so the HTML is self-contained
  (same pattern used in mtm_card_c.html).
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Confidence ordering
# ─────────────────────────────────────────────────────────────────────────────

_CONFIDENCE_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "NONE": -1}


def _confidence_passes(actual: str | None, required: str) -> bool:
    """
    Check if actual confidence meets the required threshold.

    NONE bypasses the check entirely (used for feature_flags with no
    field_confidence entry).
    """
    if required == "NONE":
        return True
    if actual is None:
        return False
    return _CONFIDENCE_ORDER.get(actual.upper(), -1) >= _CONFIDENCE_ORDER.get(required.upper(), 99)


# ─────────────────────────────────────────────────────────────────────────────
# MachineRecord accessors
# ─────────────────────────────────────────────────────────────────────────────

def _get_field_value(record: dict, field_name: str, source: str) -> Any:
    """
    Pull a field value from the resolved MachineRecord based on its source.

    Sources:
      registry_specs         - machine_record['specs'][field_name]
      registry_feature_flags - machine_record['feature_flags'][field_name]
      dealer_input           - dealer_input dict (handled separately in badge eval)
    """
    if source == "registry_specs":
        return record.get("specs", {}).get(field_name)
    if source == "registry_feature_flags":
        return record.get("feature_flags", {}).get(field_name)
    # dealer_input is not read from the machine record
    return None


def _get_confidence(record: dict, field_name: str) -> str | None:
    """
    Pull field_confidence for a given field. Returns None if not present
    (which is expected for feature_flags fields).
    """
    return record.get("field_confidence", {}).get(field_name)


# ─────────────────────────────────────────────────────────────────────────────
# Spec strip evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_spec_cell(cell_config: dict, record: dict) -> dict | None:
    """
    Resolve a single spec strip cell using primary → fallback cascade +
    confidence gating.

    Returns a dict with 'value', 'display_label', 'unit' if resolved,
    or None if the cell should be dropped.
    """
    source = cell_config.get("source", "registry_specs")
    require_conf = cell_config.get("require_confidence", "NONE")
    candidates = [cell_config["primary"], *cell_config.get("fallbacks", [])]

    for field_name in candidates:
        value = _get_field_value(record, field_name, source)
        if value is None or value == "":
            continue

        # Confidence check (skipped for NONE, which covers feature_flags
        # and any field without a confidence entry by design)
        if require_conf != "NONE":
            conf = _get_confidence(record, field_name)
            if not _confidence_passes(conf, require_conf):
                continue

        return {
            "value":         value,
            "display_label": cell_config["display_label"],
            "unit":          cell_config.get("unit"),
            "render_hint":   cell_config.get("render_hint"),
            "resolved_field": field_name,
        }

    # No candidate passed. Drop the cell.
    return None


def _format_cell_value(value: Any, render_hint: str | None) -> str:
    """Format a resolved cell value for display."""
    # Boolean with "Enclosed" / drop-on-false pattern
    if isinstance(value, bool):
        return "Enclosed" if value else ""  # caller will drop on empty

    # Enum like lift_path: capitalize
    if render_hint and render_hint.startswith("enum"):
        return str(value).capitalize()

    # Numbers: add thousand separators for ints, keep decimals for floats
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value != int(value):
            return f"{value:,.1f}"
        return f"{int(value):,}"

    return str(value)


# ─────────────────────────────────────────────────────────────────────────────
# Badge zone evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_badge_condition(
    condition: dict, record: dict, dealer_input: dict, source: str
) -> bool:
    """Evaluate a single badge condition against the record + dealer input."""
    # Composite condition: all_of
    if "all_of" in condition:
        return all(
            _evaluate_badge_condition(
                {**sub, "_inherited_source": source}, record, dealer_input, source
            )
            for sub in condition["all_of"]
        )

    # Simple equality: { "equals": "zero" }
    if "equals" in condition:
        # Need to know which field. If this is a top-level condition on a
        # badge, the field is in the parent badge config.
        field_name = condition.get("_field")  # populated by caller
        if not field_name:
            return False
        actual = (
            dealer_input.get(field_name)
            if source == "dealer_input"
            else _get_field_value(record, field_name, source)
        )
        return actual == condition["equals"]

    # Comparison: { "field": "horsepower_hp", "gte": 85 }
    if "field" in condition and "gte" in condition:
        field_name = condition["field"]
        actual = _get_field_value(record, field_name, "registry_specs")
        if actual is None:
            return False
        try:
            return float(actual) >= float(condition["gte"])
        except (TypeError, ValueError):
            return False

    return False


def _resolve_badges(badge_zone_config: dict, record: dict, dealer_input: dict) -> list[dict]:
    """Return the ordered list of badges that should render."""
    active = []
    for badge in badge_zone_config.get("badges", []):
        source = badge["source"]
        condition = dict(badge.get("condition", {}))

        # Attach the field name to the condition for equality checks
        if "equals" in condition and "field" in badge:
            condition["_field"] = badge["field"]

        if _evaluate_badge_condition(condition, record, dealer_input, source):
            active.append(
                {
                    "id":    badge["id"],
                    "label": badge["label"],
                    "style": badge.get("style", "primary"),
                }
            )
    return active


# ─────────────────────────────────────────────────────────────────────────────
# Photo handling
# ─────────────────────────────────────────────────────────────────────────────

def _photo_data_uri(photo_path: str | None) -> str | None:
    """Embed the photo as a base64 data URI so the HTML is self-contained."""
    if not photo_path:
        return None
    path = Path(photo_path)
    if not path.is_file():
        return None
    ext = path.suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_card(
    machine_record: dict,
    config: dict,
    dealer_input: dict,
) -> str:
    """
    Render the Option C listing card as self-contained HTML.

    Args:
        machine_record: Resolved MachineRecord (pipeline output, not raw registry).
            Expected shape:
              {
                'equipment_type': 'mini_excavator',
                'make': 'KUBOTA',
                'model': 'KX040-4',
                'specs': { ... },
                'feature_flags': { ... },
                'field_confidence': { field_name: 'HIGH'|'MEDIUM'|'LOW', ... }
              }

        config: Parsed card_spec_hierarchy.json.

        dealer_input: Dealer-entered fields. Expected keys:
              {
                'year': 2022,
                'hours': 425,
                'price': 89500,
                'photo_path': '/path/to/photo.jpg',  # optional
                'high_flow': True,                    # optional
              }

    Returns:
        A complete HTML document string.
    """
    eq_type = machine_record.get("equipment_type")
    if not eq_type:
        raise ValueError("machine_record is missing 'equipment_type'")

    type_config = config.get("equipment_types", {}).get(eq_type)
    if not type_config:
        raise ValueError(f"No hierarchy defined for equipment type: {eq_type}")

    # --- Resolve spec strip ----------------------------------------------
    strip_cells = []
    for cell_config in type_config.get("spec_strip", []):
        resolved = _resolve_spec_cell(cell_config, machine_record)
        if resolved is None:
            strip_cells.append(None)  # empty slot; preserved per config
            continue
        formatted = _format_cell_value(resolved["value"], resolved.get("render_hint"))
        if formatted == "":
            strip_cells.append(None)  # boolean False → drop
            continue
        resolved["formatted"] = formatted
        strip_cells.append(resolved)

    # --- Resolve badges --------------------------------------------------
    badges = _resolve_badges(
        type_config.get("badge_zone", {}), machine_record, dealer_input
    )

    # --- Prepare header values -------------------------------------------
    year       = dealer_input.get("year", "")
    make       = (machine_record.get("make") or "").upper()
    model      = machine_record.get("model") or ""
    eq_display = {
        "compact_track_loader": "COMPACT TRACK LOADER",
        "skid_steer":           "SKID STEER LOADER",
        "mini_excavator":       "MINI EXCAVATOR",
    }.get(eq_type, eq_type.upper().replace("_", " "))

    hours     = dealer_input.get("hours")
    price     = dealer_input.get("price")
    photo_uri = _photo_data_uri(dealer_input.get("photo_path"))

    # --- Build HTML ------------------------------------------------------
    return _build_html(
        year=year,
        make=make,
        model=model,
        eq_display=eq_display,
        hours=hours,
        price=price,
        photo_uri=photo_uri,
        strip_cells=strip_cells,
        badges=badges,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HTML template
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_hours(hours: Any) -> str:
    if hours is None or hours == "":
        return ""
    try:
        return f"{int(hours):,}"
    except (TypeError, ValueError):
        return str(hours)


def _fmt_price(price: Any) -> str:
    if price is None or price == "":
        return ""
    try:
        return f"${int(price):,}"
    except (TypeError, ValueError):
        return str(price)


def _price_font_size(price_str: str) -> int:
    """Auto-scale the price font so long prices don't overflow."""
    n = len(price_str)
    if n <= 7:   # $89,500
        return 28
    if n <= 8:   # $189,500
        return 24
    return 20    # $1,189,500


def _hours_font_size(hours_str: str) -> int:
    """Auto-scale hours font for long values."""
    n = len(hours_str)
    if n <= 3:
        return 17
    if n <= 5:   # 12,450
        return 15
    return 13


def _render_strip_cell(cell: dict | None) -> str:
    """Render a single spec strip cell (or an empty placeholder)."""
    if cell is None:
        return '<div class="spec empty"></div>'
    value      = html.escape(cell["formatted"])
    label      = html.escape(cell["display_label"])
    unit       = cell.get("unit")
    unit_html  = f'<span class="unit">{html.escape(unit)}</span>' if unit else ""
    return (
        f'<div class="spec">'
        f'<div class="num">{value}{unit_html}</div>'
        f'<div class="lbl">{label}</div>'
        f"</div>"
    )


def _render_badges(badges: list[dict]) -> str:
    if not badges:
        return ""
    chips = "".join(
        f'<div class="badge badge-{html.escape(b["style"])}">{html.escape(b["label"])}</div>'
        for b in badges
    )
    return f'<div class="badge-zone">{chips}</div>'


def _render_photo_area(photo_uri: str | None) -> str:
    if photo_uri:
        return f'<div class="photo-middle" style="background-image: url(\'{photo_uri}\');">'
    # Fallback: branded black panel
    return (
        '<div class="photo-middle photo-missing">'
        '<div class="missing-text">PHOTO PENDING</div>'
    )


def _build_html(
    year: Any,
    make: str,
    model: str,
    eq_display: str,
    hours: Any,
    price: Any,
    photo_uri: str | None,
    strip_cells: list[dict | None],
    badges: list[dict],
) -> str:
    year_str  = html.escape(str(year))
    make_str  = html.escape(make)
    model_str = html.escape(model)
    eq_str    = html.escape(eq_display)

    hours_fmt  = _fmt_hours(hours)
    price_fmt  = _fmt_price(price)
    price_font = _price_font_size(price_fmt) if price_fmt else 28
    hours_font = _hours_font_size(hours_fmt) if hours_fmt else 17

    hours_stamp = (
        f'<div class="hours-stamp">'
        f'<span class="big" style="font-size:{hours_font}px;">{hours_fmt}</span>HRS'
        f"</div>"
        if hours_fmt
        else ""
    )

    price_stamp = (
        f'<div class="price-stamp" style="font-size:{price_font}px;">'
        f'<span class="price-label">ASKING</span>'
        f"{price_fmt}"
        f"</div>"
        if price_fmt
        else ""
    )

    strip_html = "".join(_render_strip_cell(c) for c in strip_cells)
    badge_html = _render_badges(badges)
    photo_open = _render_photo_area(photo_uri)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MTM Listing \u2014 {year_str} {make_str} {model_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --mtm-yellow: #F5C400;
  --mtm-black: #0D0D0D;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: #E8E8E8;
  font-family: 'Inter', sans-serif;
  padding: 32px 16px;
  -webkit-font-smoothing: antialiased;
  display: flex;
  justify-content: center;
  min-height: 100vh;
}}
.card {{
  width: 440px;
  aspect-ratio: 4 / 5;
  background: var(--mtm-black);
  position: relative;
  overflow: hidden;
  color: white;
  box-shadow: 0 12px 40px rgba(0,0,0,0.2);
  display: flex;
  flex-direction: column;
}}
/* TOP YELLOW BAR */
.top-frame {{
  background: var(--mtm-yellow);
  color: var(--mtm-black);
  padding: 16px 22px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 4px solid var(--mtm-black);
}}
.top-frame .year {{
  font-family: 'Archivo Black', sans-serif;
  font-size: 32px;
  line-height: 1;
  letter-spacing: -0.02em;
}}
.top-frame .make {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.25em;
  font-weight: 700;
  margin-top: 3px;
}}
.top-frame .right-stack {{ text-align: right; }}
.top-frame .model {{
  font-family: 'Archivo Black', sans-serif;
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.02em;
}}
.top-frame .type {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.2em;
  font-weight: 700;
  margin-top: 4px;
}}
/* BADGE ZONE (above photo) */
.badge-zone {{
  background: var(--mtm-black);
  padding: 8px 16px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  border-bottom: 2px solid rgba(245,196,0,0.3);
}}
.badge {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.15em;
  font-weight: 700;
  text-transform: uppercase;
  padding: 5px 10px;
  border: 1px solid var(--mtm-yellow);
  color: var(--mtm-yellow);
}}
.badge-primary {{ background: transparent; }}
.badge-premium {{ background: var(--mtm-yellow); color: var(--mtm-black); }}
/* PHOTO */
.photo-middle {{
  flex: 1;
  background-size: cover;
  background-position: center;
  position: relative;
}}
.photo-missing {{
  background: linear-gradient(135deg, #2a2a2a 0%, #1e1e1e 50%, #0d0d0d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.missing-text {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.3em;
  color: rgba(245,196,0,0.6);
  font-weight: 700;
}}
.hours-stamp {{
  position: absolute;
  top: 14px;
  right: 14px;
  background: rgba(13,13,13,0.92);
  color: white;
  padding: 9px 13px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.18em;
  font-weight: 700;
  border: 1px solid var(--mtm-yellow);
}}
.hours-stamp .big {{
  font-family: 'Archivo Black', sans-serif;
  color: var(--mtm-yellow);
  letter-spacing: -0.02em;
  margin-right: 5px;
}}
.price-stamp {{
  position: absolute;
  bottom: 14px;
  left: 14px;
  background: var(--mtm-yellow);
  color: var(--mtm-black);
  padding: 10px 16px;
  font-family: 'Archivo Black', sans-serif;
  letter-spacing: -0.02em;
  line-height: 1;
}}
.price-stamp .price-label {{
  display: block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.2em;
  font-weight: 700;
  margin-bottom: 4px;
}}
/* BOTTOM SPEC STRIP */
.bottom-frame {{
  background: var(--mtm-black);
  padding: 14px 18px;
  border-top: 4px solid var(--mtm-yellow);
}}
.spec-row {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  margin-bottom: 10px;
}}
.spec-row .spec {{
  text-align: center;
  padding: 2px;
}}
.spec-row .spec:not(:last-child) {{
  border-right: 1px solid rgba(255,255,255,0.14);
}}
.spec-row .spec.empty {{
  opacity: 0;
}}
.spec-row .num {{
  font-family: 'Archivo Black', sans-serif;
  font-size: 19px;
  line-height: 1;
  letter-spacing: -0.02em;
}}
.spec-row .unit {{
  color: var(--mtm-yellow);
  font-size: 10px;
  margin-left: 1px;
}}
.spec-row .lbl {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.15em;
  color: rgba(255,255,255,0.55);
  text-transform: uppercase;
  font-weight: 700;
  margin-top: 4px;
}}
.footer {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid rgba(255,255,255,0.14);
  padding-top: 9px;
}}
.footer .brand {{
  font-family: 'Archivo Black', sans-serif;
  font-size: 11px;
  color: var(--mtm-yellow);
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.footer .brand::before {{
  content: '';
  width: 10px;
  height: 10px;
  background: var(--mtm-yellow);
  clip-path: polygon(0 100%, 50% 0, 100% 100%);
}}
.footer .url {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.12em;
  color: rgba(255,255,255,0.55);
}}
</style>
</head>
<body>
<div class="card">
  <div class="top-frame">
    <div class="left-stack">
      <div class="year">{year_str}</div>
      <div class="make">{make_str}</div>
    </div>
    <div class="right-stack">
      <div class="model">{model_str}</div>
      <div class="type">{eq_str}</div>
    </div>
  </div>
  {badge_html}
  {photo_open}
    {hours_stamp}
    {price_stamp}
  </div>
  <div class="bottom-frame">
    <div class="spec-row">
      {strip_html}
    </div>
    <div class="footer">
      <div class="brand">MACHINE TO MARKET</div>
      <div class="url">machinetomarket.com</div>
    </div>
  </div>
</div>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Test / demo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with open("card_spec_hierarchy.json") as f:
        config = json.load(f)

    # Example: CAT 299D3
    machine_record = {
        "equipment_type": "compact_track_loader",
        "make": "CATERPILLAR",
        "model": "299D3",
        "specs": {
            "rated_operating_capacity_lbs": 3550,
            "horsepower_hp": 110,
            "aux_flow_standard_gpm": 23,
        },
        "feature_flags": {
            "enclosed_cab_available": True,
        },
        "field_confidence": {
            "rated_operating_capacity_lbs": "HIGH",
            "horsepower_hp": "HIGH",
            "aux_flow_standard_gpm": "HIGH",
        },
    }
    dealer_input = {
        "year": 2022,
        "hours": 425,
        "price": 89500,
        "photo_path": "/mnt/user-data/uploads/IMG_2846.jpeg",
        "high_flow": True,
    }

    html_output = render_card(machine_record, config, dealer_input)
    out_path = Path("/home/claude/test_render.html")
    out_path.write_text(html_output)
    print(f"Rendered: {len(html_output):,} chars → {out_path}")
