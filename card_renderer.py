"""
MTM Hero Listing Card Renderer — v10

Renders 4:5 Facebook-format hero listing cards (1080×1350 px output).
Consumes a structured data dict with machine / dealer / listing keys and
returns self-contained HTML ready for Playwright Chromium PNG export.

Design reference: hero_card_v10.html
"""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

_VALID_THEMES = {"yellow", "red", "blue", "green", "orange"}


# ─────────────────────────────────────────────────────────────────────────────
# Photo embedding
# ─────────────────────────────────────────────────────────────────────────────

def _photo_data_uri(photo_path: str | None) -> str | None:
    """Embed photo as base64 data URI so the rendered HTML is self-contained."""
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
# Value formatters
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_comma(v: Any) -> str:
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_flow(v: float) -> str:
    """Integer if whole, one decimal otherwise."""
    fv = float(v)
    if fv == int(fv):
        return str(int(fv))
    return f"{fv:.1f}"


def _fmt_price(price: Any) -> str:
    try:
        return f"${int(price):,}"
    except (TypeError, ValueError):
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Spec column builder
# ─────────────────────────────────────────────────────────────────────────────

def _spec_col(label: str, value: Any, unit: str, comma: bool = False, raw_label: bool = False) -> str:
    lbl_html = label if raw_label else html.escape(label)
    if value is None:
        val_html = '<div class="v">&#8212;</div>'
    else:
        if unit == "GPM":
            fmt = _fmt_flow(value)
        elif comma:
            fmt = _fmt_comma(value)
        else:
            fmt = _fmt_comma(value)
        val_html = (
            f'<div class="v">{html.escape(fmt)}'
            f'<span class="u">{html.escape(unit)}</span></div>'
        )
    return (
        f'<div class="spec">'
        f'<div class="lbl">{lbl_html}</div>'
        f'{val_html}'
        f'</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Type-aware spec column dispatch
# ─────────────────────────────────────────────────────────────────────────────

def _build_spec_cols(machine: dict, eq_type: str) -> tuple[str, str, str]:
    """Return (col1_html, col2_html, col3_html) keyed to equipment type."""
    hp = machine.get("net_hp") or machine.get("horsepower_hp")

    if eq_type in ("mini_excavator", "excavator", "large_excavator"):
        weight = machine.get("operating_weight_lb")
        dig    = machine.get("max_dig_depth_str")
        return (
            _spec_col("OP WEIGHT", weight, "LB", comma=True),
            _spec_col("NET HP",    hp,     "HP"),
            _spec_col("DIG DEPTH", dig,    ""),
        )

    if eq_type == "backhoe_loader":
        weight = machine.get("operating_weight_lb")
        dig    = machine.get("max_dig_depth_str")
        return (
            _spec_col("OP WEIGHT", weight, "LB", comma=True),
            _spec_col("NET HP",    hp,     "HP"),
            _spec_col("DIG DEPTH", dig,    ""),
        )

    if eq_type == "telehandler":
        cap    = machine.get("lift_capacity_lb")
        height = machine.get("max_lift_height_ft_str")
        return (
            _spec_col("LIFT CAP", cap,    "LB", comma=True),
            _spec_col("NET HP",   hp,     "HP"),
            _spec_col("LIFT HT",  height, ""),
        )

    if eq_type == "wheel_loader":
        weight = machine.get("operating_weight_lb")
        bucket = machine.get("bucket_capacity_yd3")
        return (
            _spec_col("OP WEIGHT", weight, "LB", comma=True),
            _spec_col("NET HP",    hp,     "HP"),
            _spec_col("BUCKET",    bucket, "YD\u00b3"),
        )

    if eq_type in ("dozer", "crawler_dozer"):
        weight = machine.get("operating_weight_lb")
        blade  = machine.get("blade_capacity_yd3")
        return (
            _spec_col("OP WEIGHT", weight, "LB", comma=True),
            _spec_col("NET HP",    hp,     "HP"),
            _spec_col("BLADE",     blade,  "YD\u00b3"),
        )

    if eq_type == "boom_lift":
        ph    = machine.get("platform_height_ft_str")
        reach = machine.get("horizontal_reach_ft_str")
        cap   = machine.get("platform_capacity_lbs")
        return (
            _spec_col("PLATFORM HT",  ph,    ""),
            _spec_col("HORIZ REACH",  reach, ""),
            _spec_col("PLATFORM CAP", cap,   "LB", comma=True),
        )

    if eq_type == "scissor_lift":
        ph    = machine.get("platform_height_ft_str")
        width = machine.get("platform_width_ft_str")
        cap   = machine.get("platform_capacity_lbs")
        return (
            _spec_col("PLATFORM HT",  ph,    ""),
            _spec_col("PLATFORM W",   width, ""),
            _spec_col("PLATFORM CAP", cap,   "LB", comma=True),
        )

    # Default: CTL / SSL
    roc       = machine.get("rated_operating_capacity_lbs")
    flags     = machine.get("feature_flags") or {}
    high_flow = bool(flags.get("high_flow_available", False))
    flow_high = machine.get("aux_flow_high_gpm")
    flow_std  = machine.get("aux_flow_standard_gpm")
    if high_flow and flow_high is not None:
        flow_val   = flow_high
        flow_label = "AUX FLOW<br>HIGH FLOW"
        flow_raw   = True
    else:
        flow_val   = flow_std
        flow_label = "AUX FLOW"
        flow_raw   = False
    return (
        _spec_col("ROC",      roc,      "LB",  comma=True),
        _spec_col("NET HP",   hp,       "HP"),
        _spec_col(flow_label, flow_val, "GPM", raw_label=flow_raw),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_card(data: dict) -> str:
    """
    Render the v10 hero listing card as self-contained HTML.

    Args:
        data: {
            "machine": {
                "year":                         int | None,
                "make":                         str,
                "model":                        str,
                "horsepower_hp":                int | None,
                "rated_operating_capacity_lbs": int | None,
                "aux_flow_standard_gpm":        float | None,
                "aux_flow_high_gpm":            float | None,
                "feature_flags": {
                    "high_flow_available": bool,
                    ...
                },
                "photo_path": str | None,
            },
            "dealer": {
                "theme": "yellow" | "red" | "blue" | "green" | "orange",
            },
            "listing": {
                "price_usd": int | None,
                "hours":     int | None,
            },
        }

    Returns:
        Complete self-contained HTML document string.
    """
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    # --- Machine fields ---
    year       = machine.get("year")
    make       = (machine.get("make") or "").upper()
    model      = machine.get("model") or ""
    photo_path = machine.get("photo_path")

    # --- Theme ---
    theme = (dealer.get("theme") or "yellow").lower().strip()
    if theme not in _VALID_THEMES:
        theme = "yellow"
    theme_classes = "theme-yellow" if theme == "yellow" else f"theme-dealer theme-{theme}"

    # --- Listing fields ---
    price = listing.get("price_usd")
    hours = listing.get("hours")

    # --- Year/make line ---
    if year and make:
        ym_html = (
            f'<span class="year">{html.escape(str(year))}</span>'
            f'<span class="sep">&middot;</span>'
            f'<span class="make">{html.escape(make)}</span>'
        )
    elif make:
        ym_html = f'<span class="make">{html.escape(make)}</span>'
    else:
        ym_html = ""

    # --- Price pill ---
    if price is not None:
        price_str  = _fmt_price(price)
        price_html = f'<div class="h-price"><div class="amt">{html.escape(price_str)}</div></div>'
        header_cls = "header"
    else:
        price_html = ""
        header_cls = "header no-price"

    # --- Photo ---
    photo_uri = _photo_data_uri(photo_path)
    if photo_uri:
        photo_cls      = "photo"
        machine_style  = f'style="background-image: url(\'{photo_uri}\');"'
    else:
        photo_cls      = "photo photo-missing"
        machine_style  = ""

    # --- Hours chip ---
    if hours is not None:
        hrs_str    = _fmt_comma(hours)
        hours_html = (
            f'<div class="hours-chip">'
            f'<span class="v">{html.escape(hrs_str)}</span>'
            f'<span class="u">HRS</span>'
            f'</div>'
        )
    else:
        hours_html = ""

    eq_type = (machine.get("equipment_type") or "").lower()
    roc_html, hp_html, flow_html = _build_spec_cols(machine, eq_type)

    return _build_html(
        theme_classes = theme_classes,
        header_cls    = header_cls,
        ym_html       = ym_html,
        model         = model,
        price_html    = price_html,
        photo_cls     = photo_cls,
        machine_style = machine_style,
        hours_html    = hours_html,
        roc_html      = roc_html,
        hp_html       = hp_html,
        flow_html     = flow_html,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HTML template
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(
    theme_classes: str,
    header_cls: str,
    ym_html: str,
    model: str,
    price_html: str,
    photo_cls: str,
    machine_style: str,
    hours_html: str,
    roc_html: str,
    hp_html: str,
    flow_html: str,
) -> str:
    model_esc = html.escape(model)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Listing Card</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  :root {{
    --mtm-yellow: #FFC20E;
    --mtm-ink:    #0D0D0D;
    --mtm-panel:  #141414;
    --mtm-muted:  #B8B8B8;
    --mtm-white:  #FFFFFF;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: #0A0A0A;
    font-family: 'Inter', sans-serif;
    padding: 20px;
    -webkit-font-smoothing: antialiased;
  }}

  /* ─── Card shell ─────────────────────────────────────────────────── */
  .card {{
    width: 540px;
    aspect-ratio: 4 / 5;
    background: #1A1A1A;
    position: relative;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.06);
    --gutter: 22px;
  }}

  /* ─── Header ─────────────────────────────────────────────────────── */
  .card .header {{
    padding: 14px var(--gutter) 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    position: relative;
    flex-shrink: 0;
  }}

  .card .header.no-price .h-id {{
    width: 100%;
  }}

  .card .h-id {{
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    flex: 1;
  }}

  .card .h-id .year-make {{
    display: flex;
    align-items: center;
    gap: 7px;
    font-family: 'Oswald', sans-serif;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1.2px;
  }}

  .card .h-id .year-make .year {{
    font-weight: 600;
  }}

  .card .h-id .model {{
    font-family: 'Oswald', sans-serif;
    font-size: 56px;
    font-weight: 700;
    line-height: 0.9;
    letter-spacing: -1.5px;
    margin-top: 3px;
  }}

  /* ─── Price pill ─────────────────────────────────────────────────── */
  .card .h-price {{
    flex-shrink: 0;
  }}

  .card .h-price .amt {{
    background: var(--mtm-ink);
    padding: 10px 16px;
    border-radius: 4px;
    box-shadow: 0 2px 0 rgba(0,0,0,0.25);
    font-family: 'Oswald', sans-serif;
    font-size: 42px;
    font-weight: 700;
    letter-spacing: -1.5px;
    line-height: 0.9;
    color: var(--mtm-white);
    white-space: nowrap;
    display: block;
  }}

  /* ─── Photo region ───────────────────────────────────────────────── */
  .card .photo {{
    flex: 1;
    position: relative;
    overflow: hidden;
    min-height: 0;
  }}

  .card .photo .machine {{
    position: absolute;
    inset: 0;
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
  }}

  /* Full-photo gradient overlay */
  .card .photo::after {{
    content: '';
    position: absolute;
    inset: 0;
    z-index: 1;
    pointer-events: none;
    background: linear-gradient(
      to bottom,
      rgba(0,0,0,0.18) 0%,
      rgba(0,0,0,0.06) 25%,
      rgba(0,0,0,0.00) 50%,
      rgba(0,0,0,0.10) 70%,
      rgba(0,0,0,0.32) 100%
    );
  }}

  /* Missing photo state */
  .card .photo.photo-missing .machine {{
    background: #2A2A2A;
    display: flex;
    align-items: center;
    justify-content: center;
  }}

  .card .photo.photo-missing .machine::after {{
    content: 'PHOTO PENDING';
    font-family: 'Oswald', sans-serif;
    font-size: 16px;
    font-weight: 600;
    color: #888;
    letter-spacing: 0.05em;
  }}

  .card .photo.photo-missing::after {{
    display: none;
  }}

  /* ─── Hours chip ─────────────────────────────────────────────────── */
  .card .hours-chip {{
    position: absolute;
    top: 12px;
    right: 12px;
    z-index: 2;
    background: rgba(13,13,13,0.9);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    padding: 5px 9px 5px 7px;
    display: flex;
    align-items: baseline;
    gap: 4px;
  }}

  .card .hours-chip .v {{
    font-family: 'Oswald', sans-serif;
    font-size: 14px;
    font-weight: 700;
    line-height: 1;
    color: var(--mtm-white);
  }}

  .card .hours-chip .u {{
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.5px;
    line-height: 1;
  }}

  /* ─── Spec block ─────────────────────────────────────────────────── */
  .card .spec-block {{
    background: var(--mtm-panel);
    padding: 14px var(--gutter) 22px;
    flex-shrink: 0;
  }}

  .card .specs {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
  }}

  .card .specs .spec:not(:last-child) {{
    border-right: 1px solid rgba(255,255,255,0.1);
    padding-right: 12px;
  }}

  .card .specs .lbl {{
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2.2px;
    text-transform: uppercase;
  }}

  .card .specs .v {{
    font-family: 'Oswald', sans-serif;
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -1px;
    line-height: 1;
    color: var(--mtm-white);
    margin-top: 7px;
    display: block;
  }}

  .card .specs .v .u {{
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 400;
    letter-spacing: 0;
    color: var(--mtm-muted);
    margin-left: 2px;
    vertical-align: baseline;
  }}

  /* ─── Theme: yellow (MTM default) ───────────────────────────────── */
  .theme-yellow .header                  {{ background: var(--mtm-yellow); }}
  .theme-yellow .h-id .year-make         {{ color: var(--mtm-ink); }}
  .theme-yellow .h-id .year-make .sep    {{ color: rgba(13,13,13,0.45); }}
  .theme-yellow .h-id .model             {{ color: var(--mtm-ink); }}
  .theme-yellow .spec-block              {{ border-top: 4px solid var(--mtm-yellow); }}
  .theme-yellow .specs .lbl              {{ color: var(--mtm-yellow); }}
  .theme-yellow .hours-chip              {{ border-left: 2px solid var(--mtm-yellow); }}
  .theme-yellow .hours-chip .u           {{ color: var(--mtm-yellow); }}

  /* ─── Theme: dealer (red / blue / green / orange) ────────────────── */
  .theme-dealer .header                  {{ background: var(--accent); }}
  .theme-dealer .h-id .year-make         {{ color: rgba(255,255,255,1); }}
  .theme-dealer .h-id .year-make .sep    {{ color: rgba(255,255,255,0.5); }}
  .theme-dealer .h-id .model             {{ color: var(--mtm-white); }}
  .theme-dealer .spec-block              {{ border-top: 4px solid var(--accent); }}
  .theme-dealer .specs .lbl              {{ color: var(--accent-bright); }}
  .theme-dealer .hours-chip              {{ border-left: 2px solid var(--accent-bright); }}
  .theme-dealer .hours-chip .u           {{ color: var(--accent-bright); }}

  .theme-red    {{ --accent: #C8102E; --accent-bright: #FF5A6E; }}
  .theme-blue   {{ --accent: #1E4D8C; --accent-bright: #5B9BE8; }}
  .theme-green  {{ --accent: #2C5F3E; --accent-bright: #6BC48A; }}
  .theme-orange {{ --accent: #D85A15; --accent-bright: #FF9456; }}
</style>
</head>
<body>
<div class="card {theme_classes}">
  <div class="{header_cls}">
    <div class="h-id">
      <div class="year-make">{ym_html}</div>
      <div class="model">{model_esc}</div>
    </div>
    {price_html}
  </div>
  <div class="{photo_cls}">
    <div class="machine" {machine_style}></div>
    {hours_html}
  </div>
  <div class="spec-block">
    <div class="specs">
      {roc_html}
      {hp_html}
      {flow_html}
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
    import json
    from pathlib import Path

    # --- CAT 299D3 — yellow theme (MTM default) ---
    _cat_data = {
        "machine": {
            "year":  2022,
            "make":  "CAT",
            "model": "299D3",
            "horsepower_hp":                110,
            "rated_operating_capacity_lbs": 3550,
            "aux_flow_standard_gpm":        23.0,
            "aux_flow_high_gpm":            40.0,
            "feature_flags": {"high_flow_available": True},
            "photo_path": None,
        },
        "dealer":  {"theme": "yellow"},
        "listing": {"price_usd": 89500, "hours": 425},
    }

    out_yellow = Path("test_card_yellow.html")
    out_yellow.write_text(render_card(_cat_data), encoding="utf-8")
    print(f"yellow -> {out_yellow}")

    # --- CAT 299D3 — red theme ---
    _red_data = dict(_cat_data)
    _red_data["dealer"] = {"theme": "red"}
    out_red = Path("test_card_red.html")
    out_red.write_text(render_card(_red_data), encoding="utf-8")
    print(f"red    -> {out_red}")

    # --- Null-handling: hours=None, hp=None ---
    _null_data = {
        "machine": {
            "year":  2019,
            "make":  "BOBCAT",
            "model": "S650",
            "horsepower_hp":                None,
            "rated_operating_capacity_lbs": 2690,
            "aux_flow_standard_gpm":        None,
            "aux_flow_high_gpm":            None,
            "feature_flags": {},
            "photo_path": None,
        },
        "dealer":  {"theme": "yellow"},
        "listing": {"price_usd": 45000, "hours": None},
    }
    out_null = Path("test_card_nulls.html")
    out_null.write_text(render_card(_null_data), encoding="utf-8")
    print(f"nulls  -> {out_null}")

    print("Open these HTML files in a browser to verify rendering.")
