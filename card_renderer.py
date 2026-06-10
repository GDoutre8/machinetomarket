"""
MTM Hero Listing Card Renderer — Featured Listing Templates

Renders a featured listing card as self-contained HTML, ready for Playwright
Chromium PNG export at 1080×1350 px (4:5).

This module dispatches on `featured_template` to one of N template renderers.
Today only Template 1 ("price_tag") is implemented; Templates 2 and 3 will be
added as additional `_render_<key>()` functions and registered in `_TEMPLATES`.

Design reference for price_tag:
  design_handoff_hero_listing_pricetag/  (README, preview.html, source/*)
"""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Theme palette  (mirrors design_handoff/source/data.js ACCENTS)
# ─────────────────────────────────────────────────────────────────────────────

_THEMES: dict[str, dict[str, str]] = {
    "yellow": {"accent": "#FFC600", "accent_ink": "#0d0d0c"},
    "orange": {"accent": "#FF6A1F", "accent_ink": "#0d0d0c"},
    "red":    {"accent": "#E0252B", "accent_ink": "#ffffff"},
    "blue":   {"accent": "#1F6FEB", "accent_ink": "#ffffff"},
    "green":  {"accent": "#1F8A3B", "accent_ink": "#ffffff"},
    "black":  {"accent": "#0d0d0c", "accent_ink": "#ffffff"},
}

_EQ_TYPE_DISPLAY = {
    "compact_track_loader": "Compact Track Loader",
    "skid_steer":           "Skid Steer Loader",
    "skid_steer_loader":    "Skid Steer Loader",
    "mini_excavator":       "Mini Excavator",
    "backhoe_loader":       "Backhoe Loader",
    "large_excavator":      "Large Excavator",
    "excavator":            "Excavator",
    "telehandler":          "Telehandler",
    "wheel_loader":         "Wheel Loader",
    "dozer":                "Dozer",
    "crawler_dozer":        "Crawler Dozer",
    "boom_lift":            "Boom Lift",
    "scissor_lift":         "Scissor Lift",
}

# ─────────────────────────────────────────────────────────────────────────────
# Icons (24-px viewBox, currentColor) — ported from shared.jsx
# ─────────────────────────────────────────────────────────────────────────────

def _icon(key: str, size: int = 22, stroke: float = 2.0) -> str:
    s = f'width="{size}" height="{size}" style="display:block"'
    sw = stroke
    if key == "weight":
        return (
            f'<svg viewBox="0 0 24 24" {s} fill="none" stroke="currentColor" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M5 8h14l-1.6 11a2 2 0 0 1-2 1.7H8.6a2 2 0 0 1-2-1.7L5 8z"/>'
            '<path d="M9 8a3 3 0 0 1 6 0"/></svg>'
        )
    if key == "bolt":
        return (
            f'<svg viewBox="0 0 24 24" {s} fill="currentColor">'
            '<path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z"/></svg>'
        )
    if key == "drop":
        return (
            f'<svg viewBox="0 0 24 24" {s} fill="currentColor">'
            '<path d="M12 2.5c-1.6 3-7 8.4-7 13a7 7 0 0 0 14 0c0-4.6-5.4-10-7-13z"/></svg>'
        )
    if key == "clock":
        return (
            f'<svg viewBox="0 0 24 24" {s} fill="none" stroke="currentColor" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
        )
    if key == "arrow":
        return (
            f'<svg viewBox="0 0 24 24" {s} fill="none" stroke="currentColor" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>'
        )
    if key == "gauge":
        return (
            f'<svg viewBox="0 0 24 24" {s} fill="none" stroke="currentColor" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M4 17a8 8 0 1 1 16 0"/><path d="m12 13 4-3"/></svg>'
        )
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Photo embedding
# ─────────────────────────────────────────────────────────────────────────────

def _photo_data_uri(photo_path: str | None) -> str | None:
    if not photo_path:
        return None
    if isinstance(photo_path, str) and photo_path.startswith("data:"):
        return photo_path
    p = Path(photo_path)
    if not p.is_file():
        return None
    ext = p.suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    with open(p, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode("ascii")


# ─────────────────────────────────────────────────────────────────────────────
# Value formatters
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_comma(v: Any) -> str:
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        try:
            fv = float(v)
            return f"{int(fv):,}" if fv == int(fv) else f"{fv:,.1f}"
        except (TypeError, ValueError):
            return str(v)


def _fmt_flow(v: Any) -> str:
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(fv)) if fv == int(fv) else f"{fv:.1f}"


def _fmt_price(price: Any) -> str:
    try:
        return f"${int(price):,}"
    except (TypeError, ValueError):
        try:
            fv = float(price)
            return f"${int(fv):,}"
        except (TypeError, ValueError):
            return ""


def _initials(name: str | None, fallback: str = "MTM") -> str:
    if not name:
        return fallback[:2].upper()
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", name).strip()
    parts = [p for p in cleaned.split() if p]
    if not parts:
        return fallback[:2].upper()
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


# ─────────────────────────────────────────────────────────────────────────────
# Spec column dispatch — returns list of {label, value, unit, icon_key}
# ─────────────────────────────────────────────────────────────────────────────

def _spec_dict(label: str, value: Any, unit: str, icon_key: str, *, comma: bool = False, flow: bool = False) -> dict:
    if value is None or value == "":
        fmt: str | None = None
    elif flow:
        fmt = _fmt_flow(value)
    elif comma:
        fmt = _fmt_comma(value)
    else:
        s = str(value).strip()
        fmt = s if s else None
    return {"label": label, "value": fmt, "unit": unit, "icon_key": icon_key}


def _build_specs(machine: dict, eq_type: str, *, high_flow_confirmed: bool) -> list[dict]:
    hp = machine.get("net_hp") or machine.get("horsepower_hp")

    if eq_type in ("mini_excavator", "excavator", "large_excavator", "backhoe_loader"):
        return [
            _spec_dict("OP WEIGHT", machine.get("operating_weight_lb"), "LB", "weight", comma=True),
            _spec_dict("NET HP",    hp,                                  "HP", "bolt"),
            _spec_dict("DIG DEPTH", machine.get("max_dig_depth_str"),    "",   "arrow"),
        ]
    if eq_type == "telehandler":
        return [
            _spec_dict("LIFT CAP", machine.get("lift_capacity_lb"),       "LB", "weight", comma=True),
            _spec_dict("NET HP",   hp,                                     "HP", "bolt"),
            _spec_dict("LIFT HT",  machine.get("max_lift_height_ft_str"),  "",   "arrow"),
        ]
    if eq_type == "wheel_loader":
        return [
            _spec_dict("OP WEIGHT", machine.get("operating_weight_lb"),  "LB",   "weight", comma=True),
            _spec_dict("NET HP",    hp,                                  "HP",   "bolt"),
            _spec_dict("BUCKET",    machine.get("bucket_capacity_yd3"),  "YD³", "weight"),
        ]
    if eq_type in ("dozer", "crawler_dozer"):
        return [
            _spec_dict("OP WEIGHT", machine.get("operating_weight_lb"), "LB",       "weight", comma=True),
            _spec_dict("NET HP",    hp,                                 "HP",       "bolt"),
            _spec_dict("BLADE",     machine.get("blade_capacity_yd3"),  "YD³", "weight"),
        ]
    if eq_type == "boom_lift":
        return [
            _spec_dict("PLATFORM HT",  machine.get("platform_height_ft_str"),  "",  "arrow"),
            _spec_dict("HORIZ REACH",  machine.get("horizontal_reach_ft_str"), "",  "arrow"),
            _spec_dict("PLATFORM CAP", machine.get("platform_capacity_lbs"),   "LB","weight", comma=True),
        ]
    if eq_type == "scissor_lift":
        return [
            _spec_dict("PLATFORM HT",  machine.get("platform_height_ft_str"),  "",   "arrow"),
            _spec_dict("PLATFORM W",   machine.get("platform_width_ft_str"),   "",   "arrow"),
            _spec_dict("PLATFORM CAP", machine.get("platform_capacity_lbs"),   "LB", "weight", comma=True),
        ]

    # Default: CTL / SSL
    roc = machine.get("rated_operating_capacity_lbs")
    flow_high = machine.get("aux_flow_high_gpm")
    flow_std  = machine.get("aux_flow_standard_gpm")
    if high_flow_confirmed and flow_high is not None:
        flow_label = "HIGH FLOW"
        flow_val   = flow_high
    else:
        flow_label = "AUX FLOW"
        flow_val   = flow_std
    return [
        _spec_dict("RATED OP CAPACITY", roc,      "LB",  "weight", comma=True),
        _spec_dict("NET HORSEPOWER",    hp,       "HP",  "bolt"),
        _spec_dict(flow_label,          flow_val, "GPM", "drop",  flow=True),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_FEATURED_TEMPLATE = "inventory_clean"


def render_card(data: dict) -> str:
    """
    Render a featured listing card as a self-contained HTML document.

    Dispatches on `data["featured_template"]`; falls back to
    DEFAULT_FEATURED_TEMPLATE when missing or unknown.
    """
    template = (data.get("featured_template") or DEFAULT_FEATURED_TEMPLATE).strip().lower()
    renderer = _TEMPLATES.get(template) or _TEMPLATES[DEFAULT_FEATURED_TEMPLATE]
    return renderer(data)


def _render_price_tag(data: dict) -> str:
    """
    Render Featured Listing Template 1 ("price_tag") — the locked Price Tag
    design. See design_handoff_hero_listing_pricetag/README.md.

    All payload fields are optional and degrade cleanly when missing.
    """
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    # Theme
    theme_key = (dealer.get("theme") or "yellow").lower().strip()
    theme = _THEMES.get(theme_key, _THEMES["yellow"])
    accent = theme["accent"]
    accent_ink = theme["accent_ink"]
    # Dark accent variant flips the dealer-mark contrast
    is_dark_accent = theme_key in ("red", "blue", "green", "black")

    # Machine
    year  = machine.get("year")
    make  = (machine.get("make") or "").upper()
    model = (machine.get("model") or "").upper()
    photo_uri = _photo_data_uri(machine.get("photo_path"))
    eq_type = (machine.get("equipment_type") or "").lower()

    flags = machine.get("feature_flags") or {}
    high_flow = bool(flags.get("high_flow_available", False))

    # Listing
    price = listing.get("price_usd")
    hours = listing.get("hours")

    # Dealer badge — gated on dealer.name. Logo-only hero branding is deferred:
    # the per-template mark slot is sized for 2-letter initials, not horizontal
    # logos. See badge_only export for the photo+logo composite path.
    show_dealer = bool(dealer.get("show_branding", True)) and bool(dealer.get("name"))
    d_name  = dealer.get("name") or ""
    d_short = (dealer.get("short_mark") or _initials(d_name)).upper()[:2]
    d_rep   = dealer.get("rep") or ""
    d_phone = dealer.get("phone") or ""
    d_loc   = dealer.get("location") or ""
    meta_parts = [p for p in (d_rep or d_loc, d_phone) if p]
    d_meta = " · ".join(meta_parts)

    # ------- Composed HTML fragments -------
    # Year/make line (e.g. "2020  ·  BOBCAT")
    year_make_inner = ""
    if year and make:
        year_make_inner = f"{html.escape(str(year))} &nbsp;·&nbsp; {html.escape(make)}"
    elif make:
        year_make_inner = html.escape(make)
    elif year:
        year_make_inner = html.escape(str(year))
    if not year_make_inner:
        category = _EQ_TYPE_DISPLAY.get(eq_type, "")
        if category:
            year_make_inner = html.escape(category.upper())

    # Price tag
    if price is not None:
        price_str = _fmt_price(price)
        price_html = (
            f'<div class="pricetag">'
            f'<div class="amt">{html.escape(price_str)}</div>'
            f'<div class="sub">Easy Financing Available</div>'
            f'</div>'
        ) if price_str else ""
    else:
        price_html = ""

    # Trim/hours chip — pill (HIGH FLOW), bullet, hours
    chip_inner_parts: list[str] = []
    if high_flow:
        chip_inner_parts.append('<div class="hf-pill">HIGH FLOW</div>')
    if hours is not None:
        try:
            hrs_display = f"{int(hours):,}"
        except (TypeError, ValueError):
            hrs_display = str(hours)
        chip_inner_parts.append(
            '<div class="hours">'
            f'<span class="hclock">{_icon("clock", 22)}</span>'
            f'<span class="hv">{html.escape(hrs_display)}</span>'
            '<span class="hu">HRS</span>'
            '</div>'
        )
    if len(chip_inner_parts) == 2:
        chip_html = (
            '<div class="trim-strip">'
            + chip_inner_parts[0]
            + '<span class="dot">•</span>'
            + chip_inner_parts[1]
            + '</div>'
        )
    elif chip_inner_parts:
        chip_html = '<div class="trim-strip">' + chip_inner_parts[0] + '</div>'
    else:
        chip_html = ""

    # Dealer badge
    if show_dealer:
        dark_cls = " is-dark-accent" if is_dark_accent else ""
        meta_html = f'<div class="db-meta">{html.escape(d_meta)}</div>' if d_meta else ""
        dealer_html = (
            f'<div class="dealer-badge{dark_cls}">'
            f'  <div class="db-mark">{html.escape(d_short)}</div>'
            f'  <div class="db-text">'
            f'    <div class="db-name">{html.escape(d_name.upper())}</div>'
            f'    {meta_html}'
            f'  </div>'
            f'</div>'
        )
    else:
        dealer_html = ""

    # Spec rail
    specs = _build_specs(machine, eq_type, high_flow_confirmed=high_flow)
    spec_cells: list[str] = []
    for i, spec in enumerate(specs):
        sep_cls = "" if i == 0 else " has-sep"
        if spec["value"] is None:
            value_html = '<span class="spec-num">&mdash;</span>'
        else:
            unit_html = (
                f'<span class="spec-unit">{html.escape(spec["unit"])}</span>'
                if spec["unit"] else ""
            )
            value_html = (
                f'<span class="spec-num">{html.escape(spec["value"])}</span>'
                f'{unit_html}'
            )
        spec_cells.append(
            f'<div class="spec-cell{sep_cls}">'
            f'  <div class="spec-label-row">'
            f'    <span class="spec-icon">{_icon(spec["icon_key"], 20)}</span>'
            f'    <span class="spec-label">{html.escape(spec["label"])}</span>'
            f'  </div>'
            f'  <div class="spec-value-row">{value_html}</div>'
            f'</div>'
        )
    spec_rail_html = '<div class="spec-rail">' + "".join(spec_cells) + '</div>'

    # Photo backdrop
    if photo_uri:
        photo_html = (
            f'<img class="machine-img" src="{photo_uri}" alt=""/>'
        )
    else:
        photo_html = '<div class="photo-fallback"></div>'

    # Auto-shrink very long model names (>5 chars) so they stay on one line
    model_len = len(model)
    if model_len <= 5:
        model_size_px = 230
    elif model_len <= 7:
        model_size_px = 190
    elif model_len <= 9:
        model_size_px = 150
    else:
        model_size_px = 120

    return _PAGE_TEMPLATE.format(
        accent=accent,
        accent_ink=accent_ink,
        year_make_inner=year_make_inner,
        model=html.escape(model),
        model_size_px=model_size_px,
        price_html=price_html,
        chip_html=chip_html,
        dealer_html=dealer_html,
        spec_rail_html=spec_rail_html,
        photo_html=photo_html,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HTML template — native 1080×1350 design space
# ─────────────────────────────────────────────────────────────────────────────

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Featured Listing — Price Tag</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;800;900&family=Inter+Tight:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700;800&family=Archivo+Narrow:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: #1a1916;
    font-family: 'Inter Tight', system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .card {{
    width: 1080px;
    height: 1350px;
    position: relative;
    overflow: hidden;
    background: #0d0d0c;
    color: #fff;
    --accent: {accent};
    --accent-ink: {accent_ink};
    --ink: #0d0d0c;
  }}

  /* Photo + scrims */
  .photo-wrap {{ position: absolute; inset: 0; z-index: 0; overflow: hidden; }}
  .machine-img {{
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 55%;
    display: block;
    filter: brightness(1.08) contrast(1.04) saturate(1.05);
  }}
  .photo-fallback {{
    width: 100%; height: 100%;
    background: repeating-linear-gradient(135deg, #2a2926 0 22px, #232220 22px 44px);
  }}
  .scrim {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg,
      rgba(13,13,12,.78) 0%,
      rgba(13,13,12,.15) 22%,
      rgba(13,13,12,0) 35%,
      rgba(13,13,12,0) 52%,
      rgba(13,13,12,.7) 78%,
      rgba(13,13,12,.97) 100%);
    pointer-events: none;
  }}
  .lift {{
    position: absolute; inset: 0;
    background: radial-gradient(ellipse 55% 38% at 50% 55%,
      rgba(255,255,255,.10) 0%, rgba(255,255,255,0) 70%);
    mix-blend-mode: screen; pointer-events: none;
  }}

  /* Top yellow rule */
  .top-rule {{
    position: absolute; top: 0; left: 0; right: 0; height: 6px;
    background: var(--accent); z-index: 6;
  }}
  /* Dealer badge */
  .dealer-row {{
    position: absolute; top: 48px; left: 48px; right: 48px;
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 18px; z-index: 5;
  }}
  .dealer-badge {{
    display: inline-flex; align-items: center; gap: 14px;
    padding: 10px 16px 10px 12px;
    background: rgba(13,13,12,.85);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0,0,0,.18);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    white-space: nowrap;
  }}
  .dealer-badge .db-mark {{
    width: 38px; height: 38px;
    border-radius: 3px;
    background: var(--accent); color: var(--ink);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 22px; letter-spacing: -.02em;
    position: relative; flex: 0 0 auto;
  }}
  .dealer-badge.is-dark-accent .db-mark {{
    background: var(--ink); color: var(--accent);
  }}
  .dealer-badge .db-mark::after {{
    content: ""; position: absolute;
    right: -1px; bottom: -1px;
    width: 10px; height: 10px;
    background: var(--accent);
    clip-path: polygon(100% 0, 100% 100%, 0 100%);
  }}
  .dealer-badge .db-text {{
    display: flex; flex-direction: column; gap: 2px;
    line-height: 1; min-width: 0;
  }}
  .dealer-badge .db-name {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800; font-size: 19px; letter-spacing: .005em;
    text-transform: uppercase; color: #fff;
  }}
  .dealer-badge .db-meta {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-weight: 500; font-size: 11px; letter-spacing: .04em;
    color: rgba(255,255,255,.55); text-transform: uppercase;
  }}

  /* Price tag */
  .pricetag {{
    position: absolute; top: 140px; right: 48px; z-index: 6;
    background: var(--accent); color: var(--accent-ink);
    padding: 14px 26px 16px;
    box-shadow:
      0 22px 44px rgba(0,0,0,.55),
      0 4px 0 rgba(13,13,12,.35),
      inset 0 0 0 3px rgba(13,13,12,.1);
    clip-path: polygon(0% 8%, 4% 0%, 100% 0%, 100% 100%, 4% 100%, 0% 92%);
  }}
  .pricetag .amt {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 84px;
    line-height: .85; letter-spacing: -.015em;
    white-space: nowrap; text-transform: uppercase;
  }}
  .pricetag .sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-weight: 700; font-size: 11px; letter-spacing: .1em;
    margin-top: 6px; text-transform: uppercase;
  }}

  /* Title block */
  .title-block {{
    position: absolute; left: 48px; right: 48px; bottom: 316px;
    z-index: 3; color: #fff;
  }}
  .title-block .ym {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800; font-size: 26px;
    color: var(--accent);
    letter-spacing: .18em; text-transform: uppercase;
    margin-bottom: 10px;
  }}
  .title-block .model {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: {model_size_px}px;
    line-height: .86;
    letter-spacing: -.015em;
    color: #fff;
    margin-left: -4px;
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
  }}
  .trim-strip {{
    display: inline-flex; align-items: center; gap: 14px;
    margin-top: 14px;
    background: rgba(13,13,12,.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    padding: 8px 14px;
    border: 1px solid var(--accent);
  }}
  .trim-strip .hf-pill {{
    background: var(--accent); color: var(--accent-ink);
    padding: 5px 12px;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 24px; letter-spacing: .04em;
    line-height: 1; text-transform: uppercase;
  }}
  .trim-strip .dot {{
    color: rgba(255,255,255,.5);
    font-weight: 900; font-size: 22px; line-height: 1;
  }}
  .trim-strip .hours {{
    display: flex; align-items: baseline; gap: 8px;
    color: #fff;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700; font-size: 30px;
  }}
  .trim-strip .hclock {{
    color: var(--accent); display: inline-flex; align-self: center;
  }}
  .trim-strip .hv {{ color: #fff; }}
  .trim-strip .hu {{
    color: rgba(255,255,255,.7);
    font-size: 18px; font-weight: 700; letter-spacing: .14em;
  }}

  /* Spec rail */
  /* bottom offset reserves a clean bottom-left zone for the standard
     dealer badge composited by card_renderer_adapter. */
  .spec-rail {{
    position: absolute; left: 0; right: 0; bottom: 110px;
    background: #0d0d0c;
    border-top: 4px solid var(--accent);
    padding: 22px 28px 26px;
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    z-index: 5;
  }}
  .spec-cell {{
    padding: 0 14px;
    display: flex; flex-direction: column; gap: 4px; min-width: 0;
  }}
  .spec-cell.has-sep {{ border-left: 1px solid rgba(255,255,255,.14); }}
  .spec-label-row {{ display: flex; align-items: center; gap: 8px; }}
  .spec-icon {{ color: var(--accent); display: inline-flex; }}
  .spec-label {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 700; font-size: 16px; letter-spacing: .18em;
    text-transform: uppercase;
    color: rgba(255,255,255,.82);
    white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
  }}
  .spec-value-row {{ display: flex; align-items: baseline; gap: 6px; }}
  .spec-num {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 78px; line-height: .85;
    color: #fff;
  }}
  .spec-unit {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700; font-size: 26px;
    color: var(--accent);
  }}
</style>
</head>
<body>
<div class="card">
  <div class="photo-wrap">
    {photo_html}
    <div class="scrim"></div>
    <div class="lift"></div>
  </div>
  <div class="top-rule"></div>
  <div class="dealer-row">{dealer_html}</div>
  {price_html}
  <div class="title-block">
    <div class="ym">{year_make_inner}</div>
    <div class="model">{model}</div>
    {chip_html}
  </div>
  {spec_rail_html}
</div>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Template registry — add future templates here, one entry per featured_template
# key. Keep entries simple (key -> callable taking the payload dict).
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, Any] = {
    "price_tag":          _render_price_tag,
    "auction_ticket":     None,  # bound below once function is defined
    "simple_price_hero":  None,  # bound below once function is defined
    # "template_3": _render_template_3,   # planned
}


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template 2 — "auction_ticket"
# Reference: design_handoff_hero_listing_v2/source/concept-auctionticket.jsx
# ─────────────────────────────────────────────────────────────────────────────

def _render_auction_ticket(data: dict) -> str:
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    theme_key = (dealer.get("theme") or "yellow").lower().strip()
    theme = _THEMES.get(theme_key, _THEMES["yellow"])
    accent = theme["accent"]
    accent_ink = theme["accent_ink"]
    is_dark_accent = theme_key in ("red", "blue", "green", "black")

    year   = machine.get("year")
    make   = (machine.get("make") or "").upper()
    model  = (machine.get("model") or "").upper()
    photo_uri = _photo_data_uri(machine.get("photo_path"))
    eq_type = (machine.get("equipment_type") or "").lower()

    flags = machine.get("feature_flags") or {}
    high_flow = bool(flags.get("high_flow_available", False))

    price = listing.get("price_usd")
    hours = listing.get("hours")

    # ----- Year chip + make label -----
    year_chip_html = ""
    if year:
        year_chip_html = (
            f'<span class="yr-chip">{html.escape(str(year))}</span>'
        )
    make_text = make
    if not make_text and not year:
        make_text = _EQ_TYPE_DISPLAY.get(eq_type, "").upper()
    ym_inner = f'{year_chip_html}{html.escape(make_text)}' if make_text else year_chip_html
    ym_html = f'<div class="ym-row">{ym_inner}</div>' if ym_inner else ""

    # Model shrink for long model names
    mlen = len(model)
    if mlen <= 4:
        model_size_px = 240
    elif mlen <= 5:
        model_size_px = 220
    elif mlen <= 7:
        model_size_px = 180
    elif mlen <= 9:
        model_size_px = 140
    else:
        model_size_px = 110
    model_html = f'<div class="model">{html.escape(model)}</div>' if model else ""

    # ----- HIGH FLOW pill -----
    hf_html = (
        '<div class="hf-pill-row"><div class="hf-pill">HIGH FLOW</div></div>'
        if high_flow else
        '<div class="hf-pill-row hf-pill-row--empty"></div>'
    )

    # ----- Photo block -----
    if photo_uri:
        photo_inner = f'<img class="machine-img" src="{photo_uri}" alt=""/>'
    else:
        photo_inner = '<div class="photo-fallback"></div>'

    # Dealer badge (bottom-left of photo)
    show_dealer = bool(dealer.get("show_branding", True)) and bool(dealer.get("name"))
    if show_dealer:
        d_name  = dealer.get("name") or ""
        d_short = (dealer.get("short_mark") or _initials(d_name)).upper()[:2]
        d_rep   = dealer.get("rep") or ""
        d_phone = dealer.get("phone") or ""
        d_loc   = dealer.get("location") or ""
        meta_parts = [p for p in (d_rep or d_loc, d_phone) if p]
        d_meta = " · ".join(meta_parts)
        dark_cls = " is-dark-accent" if is_dark_accent else ""
        meta_html = f'<div class="db-meta">{html.escape(d_meta)}</div>' if d_meta else ""
        dealer_html = (
            f'<div class="dealer-badge{dark_cls}">'
            f'  <div class="db-mark">{html.escape(d_short)}</div>'
            f'  <div class="db-text">'
            f'    <div class="db-name">{html.escape(d_name.upper())}</div>'
            f'    {meta_html}'
            f'  </div>'
            f'</div>'
        )
    else:
        dealer_html = ""

    corners_html = "".join(
        f'<div class="corner corner-{c}"></div>' for c in ("tl", "tr", "bl", "br")
    )

    photo_html = (
        f'<div class="photo-block">'
        f'  {photo_inner}'
        f'  {corners_html}'
        f'  <div class="photo-badge">{dealer_html}</div>'
        f'</div>'
    )

    # ----- Hours pill -----
    if hours is not None:
        try:
            hrs_display = f"{int(hours):,}"
        except (TypeError, ValueError):
            hrs_display = str(hours)
        hours_html = (
            '<div class="hours-pill">'
            f'<span class="hp-icon">{_icon("clock", 20)}</span>'
            f'<span class="hp-val">{html.escape(hrs_display)}</span>'
            '<span class="hp-unit">HRS</span>'
            '</div>'
        )
    else:
        hours_html = ""

    # ----- Price card -----
    price_str = _fmt_price(price) if price is not None else ""
    if price_str:
        price_html = (
            '<div class="price-card">'
            f'  <div class="pc-amt">{html.escape(price_str)}</div>'
            '  <div class="pc-sub">FINANCING AVAILABLE</div>'
            '  <div class="pc-corner"></div>'
            '</div>'
        )
    else:
        price_html = ""

    left_col_inner = hours_html + price_html
    if left_col_inner:
        left_col_html = f'<div class="buyer-col">{left_col_inner}</div>'
        ledger_grid_cols = "320px 1fr"
    else:
        left_col_html = ""
        ledger_grid_cols = "1fr"

    # ----- Spec ledger -----
    specs = _build_specs(machine, eq_type, high_flow_confirmed=high_flow)
    spec_cells: list[str] = []
    short_map = {
        "RATED OP CAPACITY": "ROC",
        "NET HORSEPOWER":    "NET HP",
        "AUX FLOW":          "AUX FLOW",
        "HIGH FLOW":         "HIGH FLOW",
        "OP WEIGHT":         "OP WEIGHT",
        "NET HP":            "NET HP",
        "DIG DEPTH":         "DIG DEPTH",
        "LIFT CAP":          "LIFT CAP",
        "LIFT HT":           "LIFT HT",
        "BUCKET":            "BUCKET",
        "BLADE":             "BLADE",
        "PLATFORM HT":       "PLAT HT",
        "PLATFORM W":        "PLAT W",
        "PLATFORM CAP":      "PLAT CAP",
        "HORIZ REACH":       "REACH",
    }
    # Parallel full-name descriptors shown beneath each value. Keyed by the
    # internal spec label produced by _build_specs(); falls back to the spec
    # label itself if a key is unmapped.
    descriptor_map = {
        "RATED OP CAPACITY": "Rated Operating Capacity",
        "NET HORSEPOWER":    "Net Horsepower",
        "AUX FLOW":          "Auxiliary Hydraulic Flow",
        "HIGH FLOW":         "Auxiliary Hydraulic Flow",
    }
    for i, spec in enumerate(specs):
        sep_cls = "" if i == 0 else " has-sep"
        long_label = spec["label"]
        short_label = short_map.get(long_label, long_label[:9])
        if spec["value"] is None:
            value_html = '<span class="sl-val">&mdash;</span>'
        else:
            unit_html = (
                f'<span class="sl-unit">{html.escape(spec["unit"])}</span>'
                if spec["unit"] else ""
            )
            value_html = (
                f'<span class="sl-val">{html.escape(spec["value"])}</span>{unit_html}'
            )
        descriptor = descriptor_map.get(long_label, long_label)
        sub_html = f'<div class="sl-label">{html.escape(descriptor)}</div>'
        spec_cells.append(
            f'<div class="sl-cell{sep_cls}">'
            f'  <div class="sl-head">'
            f'    <span class="sl-icon">{_icon(spec["icon_key"], 18, stroke=2.2)}</span>'
            f'    <span class="sl-short">{html.escape(short_label)}</span>'
            f'  </div>'
            f'  <div class="sl-num-row">{value_html}</div>'
            f'  {sub_html}'
            f'</div>'
        )
    ledger_html = '<div class="spec-ledger">' + "".join(spec_cells) + '</div>'

    return _PAGE_TEMPLATE_AUCTION.format(
        accent=accent,
        accent_ink=accent_ink,
        ym_html=ym_html,
        model_html=model_html,
        model_size_px=model_size_px,
        hf_html=hf_html,
        photo_html=photo_html,
        left_col_html=left_col_html,
        ledger_grid_cols=ledger_grid_cols,
        ledger_html=ledger_html,
    )


_PAGE_TEMPLATE_AUCTION = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Featured Listing — Auction Ticket</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;800;900&family=Inter+Tight:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: #1a1916;
    font-family: 'Inter Tight', system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .card {{
    width: 1080px; height: 1350px;
    position: relative; overflow: hidden;
    background: #1a1916;
    --accent: {accent};
    --accent-ink: {accent_ink};
    --ink: #0d0d0c;
    --paper: #f3efe6;
  }}
  .paper {{
    position: absolute; inset: 30px;
    background: var(--paper);
    background-image: radial-gradient(rgba(13,13,12,.04) 1px, transparent 1.4px);
    background-size: 22px 22px;
    box-shadow: 0 30px 60px rgba(0,0,0,.4), 0 2px 0 rgba(0,0,0,.18);
    display: flex; flex-direction: column;
    overflow: hidden;
  }}

  /* HEADER */
  .hdr {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 22px 36px 16px;
    border-bottom: 1.5px solid var(--ink);
    flex: 0 0 auto;
  }}
  .hdr-l {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 800; font-size: 13px; letter-spacing: .32em;
    color: rgba(13,13,12,.55); text-transform: uppercase;
  }}
  .hdr-r {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-weight: 600; font-size: 11px; letter-spacing: .16em;
    color: rgba(13,13,12,.45); text-transform: uppercase;
  }}

  /* TITLE BLOCK */
  .title-wrap {{ padding: 16px 36px 0; flex: 0 0 auto; }}
  .ym-row {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 800; font-size: 18px; letter-spacing: .32em;
    color: var(--ink); text-transform: uppercase;
    display: flex; align-items: center;
  }}
  .yr-chip {{
    background: var(--accent); color: var(--accent-ink);
    padding: 3px 9px; margin-right: 10px;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 22px; letter-spacing: .05em;
  }}
  .model {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: {model_size_px}px;
    line-height: .78;
    color: var(--ink);
    margin-top: 4px; margin-left: -8px;
    text-transform: uppercase;
    white-space: nowrap; overflow: hidden;
  }}
  .hf-pill-row {{
    display: flex; align-items: center;
    padding-top: 8px; padding-bottom: 8px;
    border-bottom: 1px solid rgba(13,13,12,.18);
    min-height: 50px;
  }}
  .hf-pill-row--empty {{ min-height: 18px; padding-top: 4px; padding-bottom: 4px; }}
  .hf-pill {{
    background: var(--ink); color: var(--accent);
    padding: 6px 14px;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 26px;
    letter-spacing: .06em; line-height: 1;
  }}

  /* PHOTO */
  .photo-wrap {{ padding: 10px 36px 0; position: relative; flex: 0 0 auto; }}
  .photo-block {{
    position: relative;
    background: var(--ink);
    height: 540px;
    overflow: hidden;
  }}
  .machine-img {{
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 50%;
    display: block;
    filter: brightness(1.06) contrast(1.04) saturate(1.05);
  }}
  .photo-fallback {{
    width: 100%; height: 100%;
    background: repeating-linear-gradient(135deg, #2a2926 0 22px, #1f1e1c 22px 44px);
  }}
  .corner {{
    position: absolute; width: 24px; height: 24px;
  }}
  .corner-tl {{ top: 10px; left: 10px;
    border-top: 3px solid var(--accent); border-left: 3px solid var(--accent); }}
  .corner-tr {{ top: 10px; right: 10px;
    border-top: 3px solid var(--accent); border-right: 3px solid var(--accent); }}
  .corner-bl {{ bottom: 10px; left: 10px;
    border-bottom: 3px solid var(--accent); border-left: 3px solid var(--accent); }}
  .corner-br {{ bottom: 10px; right: 10px;
    border-bottom: 3px solid var(--accent); border-right: 3px solid var(--accent); }}
  .photo-badge {{
    position: absolute; left: 16px; bottom: 16px;
    transform: scale(1.18); transform-origin: left bottom;
  }}

  /* DEALER BADGE (dark variant on photo) */
  .dealer-badge {{
    display: inline-flex; align-items: center; gap: 14px;
    padding: 10px 16px 10px 12px;
    background: rgba(13,13,12,.85);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0,0,0,.35);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    white-space: nowrap;
  }}
  .dealer-badge .db-mark {{
    width: 38px; height: 38px;
    border-radius: 3px;
    background: var(--accent); color: var(--ink);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 22px; letter-spacing: -.02em;
    position: relative; flex: 0 0 auto;
  }}
  .dealer-badge.is-dark-accent .db-mark {{
    background: var(--ink); color: var(--accent);
  }}
  .dealer-badge .db-mark::after {{
    content: ""; position: absolute;
    right: -1px; bottom: -1px;
    width: 10px; height: 10px;
    background: var(--accent);
    clip-path: polygon(100% 0, 100% 100%, 0 100%);
  }}
  .dealer-badge .db-text {{
    display: flex; flex-direction: column; gap: 2px;
    line-height: 1; min-width: 0;
  }}
  .dealer-badge .db-name {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800; font-size: 19px; letter-spacing: .005em;
    text-transform: uppercase; color: #fff;
  }}
  .dealer-badge .db-meta {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-weight: 500; font-size: 11px; letter-spacing: .04em;
    color: rgba(255,255,255,.55); text-transform: uppercase;
  }}

  /* BOTTOM GRID */
  /* bottom padding reserves a clean badge zone inside the paper for the
     standard dealer badge composited by card_renderer_adapter. */
  .bottom-grid {{
    padding: 16px 36px 110px;
    display: grid;
    grid-template-columns: {ledger_grid_cols};
    gap: 22px;
    align-items: stretch;
    flex: 1 1 auto;
    min-height: 0;
  }}
  .buyer-col {{ display: flex; flex-direction: column; gap: 10px; min-width: 0; }}

  .hours-pill {{
    display: inline-flex; align-self: flex-start;
    align-items: baseline; gap: 10px;
    background: var(--ink); color: #fff;
    padding: 10px 14px;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800;
    border: 1px solid var(--accent);
    width: max-content;
  }}
  .hp-icon {{ color: var(--accent); display: inline-flex; align-self: center; }}
  .hp-val  {{ font-size: 32px; line-height: .9; }}
  .hp-unit {{
    font-size: 14px; letter-spacing: .18em;
    color: rgba(255,255,255,.7); font-weight: 700;
  }}

  .price-card {{
    border: 3px solid var(--ink);
    background: var(--accent); color: var(--accent-ink);
    padding: 26px 22px;
    display: flex; flex-direction: column; justify-content: center;
    position: relative;
    flex: 1 1 auto;
    min-height: 200px;
  }}
  .pc-amt {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 96px; line-height: .85;
    letter-spacing: -.015em; white-space: nowrap;
  }}
  .pc-sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 13px; letter-spacing: .12em; font-weight: 700;
    margin-top: 10px; text-transform: uppercase;
  }}
  .pc-corner {{
    position: absolute; top: -3px; right: -3px;
    width: 34px; height: 34px;
    background: var(--ink);
    clip-path: polygon(0 0, 100% 0, 100% 100%);
  }}

  /* SPEC LEDGER */
  .spec-ledger {{
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    border: 1.5px solid rgba(13,13,12,.62);
    background: var(--paper);
    align-self: stretch;
  }}
  .sl-cell {{
    padding: 24px 16px;
    display: flex; flex-direction: column; justify-content: flex-start;
    min-width: 0;
  }}
  .sl-cell.has-sep {{ border-left: 1.5px solid rgba(13,13,12,.62); }}
  .sl-head {{ display: flex; align-items: center; gap: 8px; }}
  .sl-icon {{ color: var(--ink); display: inline-flex; }}
  .sl-short {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 800; font-size: 13px; letter-spacing: .16em;
    color: var(--ink); text-transform: uppercase;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .sl-num-row {{
    display: flex; align-items: baseline; gap: 6px;
    margin-top: 14px;
  }}
  .sl-val {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 64px; line-height: .85;
    color: var(--ink);
  }}
  .sl-unit {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800; font-size: 22px;
    color: var(--ink); opacity: .85;
  }}
  .sl-label {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 700; font-size: 11px; letter-spacing: .14em;
    color: rgba(13,13,12,.65); text-transform: uppercase;
    margin-top: auto; padding-top: 10px; line-height: 1.2;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="paper">
    <div class="hdr">
      <div class="hdr-l">FEATURED&nbsp;LISTING</div>
      <div class="hdr-r">LISTING&nbsp;CARD</div>
    </div>
    <div class="title-wrap">
      {ym_html}
      {model_html}
      {hf_html}
    </div>
    <div class="photo-wrap">
      {photo_html}
    </div>
    <div class="bottom-grid">
      {left_col_html}
      {ledger_html}
    </div>
  </div>
</div>
</body>
</html>
"""


_TEMPLATES["auction_ticket"] = _render_auction_ticket


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template 3 — "wide_shot"
# Reference: design_handoff_wide_shot/source/concept-fieldcard.jsx
# ─────────────────────────────────────────────────────────────────────────────

def _render_wide_shot(data: dict) -> str:
    """
    Wide Shot — photo-dominant layout. Full-machine/wide-crop photo occupies the
    centre band; compact header carries title+price; clean KPI rail below; dark
    dealer footer anchors the bottom.

    All payload fields are optional and degrade cleanly when missing.
    """
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    theme_key = (dealer.get("theme") or "yellow").lower().strip()
    theme = _THEMES.get(theme_key, _THEMES["yellow"])
    accent = theme["accent"]
    accent_ink = theme["accent_ink"]

    year    = machine.get("year")
    make    = (machine.get("make") or "").upper()
    model   = (machine.get("model") or "").upper()
    eq_type = (machine.get("equipment_type") or "").lower()
    photo_uri = _photo_data_uri(machine.get("photo_path"))

    flags = machine.get("feature_flags") or {}
    high_flow = bool(flags.get("high_flow_available", False))

    price = listing.get("price_usd")
    hours = listing.get("hours")

    # ── Left title column ─────────────────────────────────────────────────────

    # Year · Make eyebrow
    ym_parts: list[str] = []
    if year:
        ym_parts.append(html.escape(str(year)))
    if make:
        ym_parts.append(html.escape(make))
    elif not year:
        cat = _EQ_TYPE_DISPLAY.get(eq_type, "")
        if cat:
            ym_parts.append(html.escape(cat.upper()))
    eyebrow_html = (
        f'<div class="ws-eyebrow">{" &nbsp;·&nbsp; ".join(ym_parts)}</div>'
        if ym_parts else ""
    )

    # Model — auto-shrink for long names
    mlen = len(model)
    if mlen <= 4:
        model_px = 170
    elif mlen <= 5:
        model_px = 155
    elif mlen <= 7:
        model_px = 125
    elif mlen <= 9:
        model_px = 100
    else:
        model_px = 82
    model_html = (
        f'<div class="ws-model" style="font-size:{model_px}px">'
        f'{html.escape(model)}</div>'
        if model else ""
    )

    # Trim chip — only when high flow confirmed
    trim_html = (
        '<div class="ws-trim">HIGH FLOW</div>'
        if high_flow else ""
    )

    left_col = eyebrow_html + model_html + trim_html

    # ── Right price cluster ───────────────────────────────────────────────────

    price_str = _fmt_price(price) if price is not None else ""
    price_line = (
        f'<div class="ws-price">{html.escape(price_str)}</div>'
        if price_str else ""
    )

    if hours is not None:
        try:
            hrs_display = f"{int(hours):,}"
        except (TypeError, ValueError):
            hrs_display = str(hours)
        hours_line = (
            f'<div class="ws-hours">'
            f'<span class="ws-hrs-val">{html.escape(hrs_display)}</span>'
            f'<span class="ws-hrs-unit">HRS</span>'
            f'</div>'
        )
    else:
        hours_line = ""

    financing_block = (
        f'<div class="ws-accent-rule"></div>'
        f'<div class="ws-financing">Financing Available</div>'
    ) if price_str else ""

    right_col_inner = price_line + hours_line + financing_block
    right_col = (
        f'<div class="ws-price-cluster">{right_col_inner}</div>'
        if right_col_inner else ""
    )

    # ── Photo band ────────────────────────────────────────────────────────────

    if photo_uri:
        photo_html = f'<img class="ws-photo-img" src="{photo_uri}" alt=""/>'
    else:
        photo_html = '<div class="ws-photo-fallback"></div>'

    # ── KPI rail ──────────────────────────────────────────────────────────────

    specs = _build_specs(machine, eq_type, high_flow_confirmed=high_flow)

    _SHORT_LABELS = {
        "RATED OP CAPACITY": "CAPACITY",
        "NET HORSEPOWER":    "NET HP",
        "AUX FLOW":          "AUX FLOW",
        "HIGH FLOW":         "HIGH FLOW",
        "OP WEIGHT":         "OP WEIGHT",
        "NET HP":            "NET HP",
        "DIG DEPTH":         "DIG DEPTH",
        "LIFT CAP":          "CAPACITY",
        "LIFT HT":           "LIFT",
        "BUCKET":            "BUCKET",
        "BLADE":             "BLADE",
        "PLATFORM HT":       "PLAT HT",
        "PLATFORM W":        "PLAT W",
        "PLATFORM CAP":      "PLAT CAP",
        "HORIZ REACH":       "REACH",
    }

    kpi_cells: list[str] = []
    for i, spec in enumerate(specs):
        is_last = i == len(specs) - 1
        sep_cls = "" if i == 0 else " ws-kpi-sep"
        pl = "56" if i == 0 else "32"
        pr = "56" if is_last else "32"
        short = _SHORT_LABELS.get(spec["label"], spec["label"][:9])
        if spec["value"] is None:
            num_html = '<span class="ws-kpi-val">&mdash;</span>'
        else:
            unit_html = (
                f'<span class="ws-kpi-unit">{html.escape(spec["unit"])}</span>'
                if spec["unit"] else ""
            )
            num_html = (
                f'<span class="ws-kpi-val">{html.escape(spec["value"])}</span>'
                f'{unit_html}'
            )
        kpi_cells.append(
            f'<div class="ws-kpi-cell{sep_cls}" style="padding-left:{pl}px;padding-right:{pr}px">'
            f'  <div class="ws-kpi-label">{html.escape(short)}</div>'
            f'  <div class="ws-kpi-num">{num_html}</div>'
            f'</div>'
        )
    kpi_rail_html = '<div class="ws-kpi-rail">' + "".join(kpi_cells) + '</div>'

    # ── Dealer footer ─────────────────────────────────────────────────────────

    show_dealer = bool(dealer.get("show_branding", True)) and bool(dealer.get("name"))
    if show_dealer:
        d_name  = dealer.get("name") or ""
        d_short = (dealer.get("short_mark") or _initials(d_name)).upper()[:2]
        d_rep   = dealer.get("rep") or ""
        d_phone = dealer.get("phone") or ""
        rep_html = f'<span class="ws-rep">{html.escape(d_rep)}</span>' if d_rep else ""
        divider_html = (
            '<span class="ws-rep-divider"></span>' if d_rep and d_phone else ""
        )
        phone_html = (
            f'<span class="ws-phone">{html.escape(d_phone)}</span>' if d_phone else ""
        )
        footer_html = (
            f'<div class="ws-footer">'
            f'  <div class="ws-footer-left">'
            f'    <div class="ws-mark">{html.escape(d_short)}</div>'
            f'    <div class="ws-dealer-text">'
            f'      <div class="ws-presented-by">Presented&nbsp;by</div>'
            f'      <div class="ws-dealer-name">{html.escape(d_name.upper())}</div>'
            f'    </div>'
            f'  </div>'
            f'  <div class="ws-footer-right">'
            f'    {rep_html}{divider_html}{phone_html}'
            f'  </div>'
            f'</div>'
        )
    else:
        footer_html = ""

    return _PAGE_TEMPLATE_WIDE.format(
        accent=accent,
        accent_ink=accent_ink,
        left_col=left_col,
        right_col=right_col,
        photo_html=photo_html,
        kpi_rail_html=kpi_rail_html,
        footer_html=footer_html,
    )


_PAGE_TEMPLATE_WIDE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Featured Listing — Wide Shot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;800;900&family=Inter+Tight:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: #fafaf7;
    font-family: 'Inter Tight', system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .card {{
    width: 1080px; height: 1350px;
    position: relative; overflow: hidden;
    background: #fafaf7;
    color: #0d0d0c;
    --accent: {accent};
    --accent-ink: {accent_ink};
    --ink: #0d0d0c;
  }}

  /* ── HEADER STRIP ─────────────────────────────── */
  .ws-header {{
    position: absolute; top: 0; left: 0; right: 0;
    height: 316px;
    display: flex; align-items: flex-start; justify-content: space-between;
    padding: 30px 56px 18px;
    z-index: 3;
  }}

  /* Left column */
  .ws-eyebrow {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 600; font-size: 17px;
    letter-spacing: .22em; text-transform: uppercase;
    color: rgba(13,13,12,.55); margin-bottom: 8px;
  }}
  .ws-model {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    line-height: .86; letter-spacing: -.02em;
    color: #0d0d0c; margin-left: -4px;
    text-transform: uppercase;
    white-space: nowrap; overflow: hidden;
  }}
  .ws-trim {{
    display: inline-flex; align-items: center;
    background: var(--accent); color: var(--accent-ink);
    padding: 8px 16px; margin-top: 14px;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 26px;
    letter-spacing: .06em; line-height: 1;
    text-transform: uppercase;
  }}

  /* Right column — price cluster */
  .ws-price-cluster {{
    text-align: right;
    display: flex; flex-direction: column; align-items: flex-end;
    padding-top: 25px;
    flex: 0 0 auto;
  }}
  .ws-price {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 96px;
    line-height: .88; letter-spacing: -.02em;
    color: #0d0d0c; white-space: nowrap;
  }}
  .ws-hours {{
    display: flex; align-items: baseline; gap: 8px;
    margin-top: 10px;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800;
  }}
  .ws-hrs-val {{
    font-size: 36px; line-height: .9;
    color: #0d0d0c; letter-spacing: -.01em;
  }}
  .ws-hrs-unit {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 700; font-size: 14px;
    letter-spacing: .18em; text-transform: uppercase;
    color: rgba(13,13,12,.55);
  }}
  .ws-accent-rule {{
    width: 120px; height: 3px;
    background: var(--accent);
    margin-top: 12px; margin-bottom: 8px;
  }}
  .ws-financing {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 700; font-size: 14px;
    letter-spacing: .10em; text-transform: uppercase;
    color: rgba(13,13,12,.78);
  }}

  /* ── DIVIDER ──────────────────────────────────── */
  .ws-divider-top {{
    position: absolute; top: 316px; left: 0; right: 0; height: 1px;
    background: rgba(13,13,12,.3); z-index: 2;
  }}

  /* ── PHOTO BAND ───────────────────────────────── */
  .ws-photo-band {{
    position: absolute; top: 332px; left: 0; right: 0; height: 746px;
    background: #0d0d0c; overflow: hidden;
  }}
  .ws-photo-img {{
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 50%;
    display: block;
    filter: brightness(1.04) contrast(1.03) saturate(1.04);
  }}
  .ws-photo-fallback {{
    width: 100%; height: 100%;
    background: repeating-linear-gradient(135deg, #2a2926 0 22px, #232220 22px 44px);
  }}

  /* ── KPI RAIL ─────────────────────────────────── */
  .ws-kpi-rail {{
    position: absolute; top: 1078px; left: 0; right: 0; height: 124px;
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    border-top: 1px solid rgba(13,13,12,.3);
    border-bottom: 1px solid rgba(13,13,12,.18);
    background: #fafaf7;
  }}
  .ws-kpi-cell {{
    padding-top: 22px; padding-bottom: 22px;
    display: flex; flex-direction: column; justify-content: center; gap: 10px;
    min-width: 0;
  }}
  .ws-kpi-sep {{ border-left: 1px solid rgba(13,13,12,.27); }}
  .ws-kpi-label {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 800; font-size: 15px;
    letter-spacing: .22em; text-transform: uppercase;
    color: rgba(13,13,12,.7);
  }}
  .ws-kpi-num {{ display: flex; align-items: baseline; gap: 8px; }}
  .ws-kpi-val {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 64px;
    line-height: .9; letter-spacing: -.015em;
    color: #0d0d0c;
  }}
  .ws-kpi-unit {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 700; font-size: 18px;
    letter-spacing: .12em; text-transform: uppercase;
    color: rgba(13,13,12,.6);
  }}

  /* ── DEALER FOOTER ────────────────────────────── */
  .ws-footer {{
    position: absolute; left: 0; right: 0; bottom: 0;
    height: 148px;
    padding: 24px 56px;
    background: #0d0d0c; color: #fff;
    display: flex; align-items: center; justify-content: space-between;
    border-top: 3px solid var(--accent);
  }}
  .ws-footer-left {{
    display: flex; align-items: center; gap: 18px;
  }}
  .ws-mark {{
    width: 42px; height: 42px; border-radius: 3px;
    background: var(--accent); color: #0d0d0c;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 22px; letter-spacing: -.02em;
    flex: 0 0 auto;
  }}
  .ws-dealer-text {{ display: flex; flex-direction: column; line-height: 1; }}
  .ws-presented-by {{
    font-family: 'Inter Tight', sans-serif;
    font-weight: 700; font-size: 11px;
    letter-spacing: .32em; text-transform: uppercase;
    color: rgba(255,255,255,.5); margin-bottom: 6px;
  }}
  .ws-dealer-name {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800; font-size: 30px;
    letter-spacing: .02em; text-transform: uppercase; color: #fff;
  }}
  .ws-footer-right {{
    display: flex; align-items: center; gap: 24px;
    font-family: 'Inter Tight', sans-serif;
    font-weight: 600; font-size: 14px;
    letter-spacing: .16em; text-transform: uppercase;
    color: rgba(255,255,255,.85);
  }}
  .ws-rep-divider {{
    width: 1px; height: 18px; background: rgba(255,255,255,.25);
    flex: 0 0 auto;
  }}
  .ws-phone {{ color: #fff; }}
</style>
</head>
<body>
<div class="card">
  <div class="ws-header">
    <div class="ws-left">{left_col}</div>
    {right_col}
  </div>
  <div class="ws-divider-top"></div>
  <div class="ws-photo-band">{photo_html}</div>
  {kpi_rail_html}
  {footer_html}
</div>
</body>
</html>
"""

_TEMPLATES["wide_shot"] = _render_wide_shot


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template — "inventory_clean"
# Marker-style marketplace card: full-bleed photo, Permanent Marker font,
# dealer name/phone top corners, make+model centered, price bottom-right.
# No spec rail. No composited badge (design rule: text overlay carries identity).
# ─────────────────────────────────────────────────────────────────────────────

def _render_inventory_clean(data: dict) -> str:
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    make      = (machine.get("make")  or "").upper()
    model     = (machine.get("model") or "").upper()
    photo_uri = _photo_data_uri(machine.get("photo_path"))
    price_str = _fmt_price(listing.get("price_usd"))
    d_name  = html.escape(dealer.get("name")  or "")
    d_phone = html.escape(dealer.get("phone") or "")

    if photo_uri:
        photo_html = f'<img class="ic-photo" src="{photo_uri}" alt=""/>'
    else:
        photo_html = '<div class="ic-photo ic-photo-fallback"></div>'

    price_html = (
        f'<div class="ic-price">{html.escape(price_str)}</div>'
    ) if price_str else ""

    return _INVENTORY_CLEAN_TEMPLATE.format(
        photo_html=photo_html,
        make_line=html.escape(make),
        model_line=html.escape(model),
        price_html=price_html,
        d_name=d_name,
        d_phone=d_phone,
    )


_INVENTORY_CLEAN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Featured Listing — Inventory Clean</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Permanent+Marker&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #1a1916; -webkit-font-smoothing: antialiased; }}
  .card {{
    width: 1080px; height: 1350px;
    position: relative; overflow: hidden; background: #0d0d0c;
  }}
  .ic-photo {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 55%;
    display: block;
  }}
  .ic-photo-fallback {{
    background: repeating-linear-gradient(135deg,#2a2926 0 22px,#232220 22px 44px);
  }}
  .ic-scrim {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg,
      rgba(0,0,0,.18) 0%,
      rgba(0,0,0,0)   30%,
      rgba(0,0,0,0)   55%,
      rgba(0,0,0,.30) 100%);
    pointer-events: none; z-index: 1;
  }}
  .ic-top-meta {{
    position: absolute; top: 44px; left: 60px; right: 60px;
    display: flex; justify-content: space-between; align-items: flex-start;
    z-index: 4;
    font-family: 'Permanent Marker', cursive;
    font-size: 28px; color: rgba(255,255,255,.88);
    text-shadow: 0 1px 6px rgba(0,0,0,.45);
  }}
  .ic-title {{
    position: absolute; left: 135px; top: 40%;
    z-index: 4;
    font-family: 'Permanent Marker', cursive;
    color: rgba(255,255,255,.90);
    text-shadow: 0 2px 8px rgba(0,0,0,.35);
    transform: rotate(-1.4deg);
    line-height: 0.82;
  }}
  .ic-line1, .ic-line2 {{ display: block; font-size: 146px; }}
  .ic-line2 {{ margin-left: 18px; }}
  .ic-price {{
    position: absolute; right: 110px; bottom: 150px;
    z-index: 4;
    font-family: 'Permanent Marker', cursive;
    font-size: 82px; color: rgba(255,255,255,.92);
    text-shadow: 0 2px 8px rgba(0,0,0,.25);
    transform: rotate(-1.8deg);
    text-align: right;
  }}
</style>
</head>
<body>
<div class="card">
  {photo_html}
  <div class="ic-scrim"></div>
  <div class="ic-top-meta">
    <span>{d_name}</span>
    <span>{d_phone}</span>
  </div>
  <div class="ic-title">
    <span class="ic-line1">{make_line}</span>
    <span class="ic-line2">{model_line}</span>
  </div>
  {price_html}
</div>
</body>
</html>
"""

_TEMPLATES["inventory_clean"] = _render_inventory_clean


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template 4 — "badge_only"
#
# Image-only export (no HTML render). The hero is the original machine photo,
# center-cropped to the 1080×1350 portrait frame, with the existing dealer
# badge composited bottom-left via renderers.badge_renderer. The PNG is
# produced directly by card_renderer_adapter._export_badge_only(), which
# export_listing_card() dispatches to before reaching render_card().
#
# This sentinel exists so introspection of _TEMPLATES (and any future
# template-aware tooling) sees badge_only as a first-class registered
# template. render_card() itself should never be called for badge_only —
# if it is, surface a clear error rather than silently rendering price_tag.
# ─────────────────────────────────────────────────────────────────────────────

def _render_badge_only(data: dict) -> str:  # noqa: ARG001
    raise NotImplementedError(
        "badge_only is an image-only featured template — use "
        "card_renderer_adapter.export_listing_card(), which dispatches to "
        "_export_badge_only() instead of render_card()."
    )

_TEMPLATES["badge_only"] = _render_badge_only


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template — "simple_price_hero"
#
# Marketplace-style hero: full-bleed photo, dominant price, minimal text.
# Spec-free by design — no OEM fields, no rail, no table.
# Intended as Photo #1 in the listing package.
# ─────────────────────────────────────────────────────────────────────────────

def _render_simple_price_hero(data: dict) -> str:
    """
    Dealer advertisement style — full-bleed photo, giant price, italic dealer
    wordmark. No footer bars, no content boxes, no spec sections.

    layout_variant in data: "A" (top-left price), "B" (bottom-left price),
    "C" (centered price). Defaults to "A".
    """
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    theme_key = (dealer.get("theme") or "orange").lower().strip()
    accent    = _THEMES.get(theme_key, _THEMES["orange"])["accent"]

    year      = machine.get("year")
    make      = (machine.get("make")  or "").upper()
    model     = (machine.get("model") or "").upper()
    photo_uri = _photo_data_uri(machine.get("photo_path"))

    price = listing.get("price_usd")
    hours = listing.get("hours")

    show_branding = bool(dealer.get("show_branding", True))
    d_name        = (dealer.get("name") or "").upper()

    variant = (data.get("layout_variant") or "A").upper().strip()
    if variant not in ("A", "B", "C"):
        variant = "A"

    # ── Shared elements ────────────────────────────────────────────────────────

    # Title: "2026 BOBCAT E35" — small supporting line
    title_parts = [p for p in (str(year) if year else "", make, model) if p]
    title_text  = " ".join(title_parts)
    t_len = len(title_text)
    t_size = 52 if t_len <= 20 else (44 if t_len <= 26 else 38)
    title_el = (
        f'<div class="sph-title" style="font-size:{t_size}px">'
        f'{html.escape(title_text)}</div>'
        if title_text else ""
    )

    # Price: dominant element
    if price is not None:
        pstr  = _fmt_price(price)
        plen  = len(pstr)
        psize = 200 if plen <= 7 else (178 if plen <= 8 else 152)
        price_el = (
            f'<div class="sph-price" style="font-size:{psize}px">'
            f'{html.escape(pstr)}</div>'
        )
    else:
        price_el = '<div class="sph-price" style="font-size:86px">CALL FOR PRICE</div>'

    # Hours: small line below price when present
    if hours is not None:
        try:
            hrs_str = f"{int(hours):,} HRS"
        except (TypeError, ValueError):
            hrs_str = f"{hours} HRS"
        hours_el = f'<div class="sph-hours">{html.escape(hrs_str)}</div>'
    else:
        hours_el = ""

    # Dealer wordmark: italic, accent-colored, corner brand
    dealer_el = (
        f'<div class="sph-dealer">{html.escape(d_name)}</div>'
        if show_branding and d_name else ""
    )

    # Photo
    if photo_uri:
        photo_html = f'<img class="sph-bg-img" src="{photo_uri}" alt=""/>'
    else:
        photo_html = '<div class="sph-bg-fallback"></div>'

    tmpl = {"A": _SPH_A, "B": _SPH_B, "C": _SPH_C}[variant]
    return tmpl.format(
        accent=accent,
        photo_html=photo_html,
        title_el=title_el,
        price_el=price_el,
        hours_el=hours_el,
        dealer_el=dealer_el,
    )


# ── Shared font import (inlined once per template to keep them self-contained) ──
_SPH_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed'
    ':ital,wght@0,800;0,900;1,900&family=Inter+Tight:wght@500;600'
    '&display=swap" rel="stylesheet">'
)

# ── Shared base CSS (included in all three variants) ──────────────────────────
_SPH_BASE_CSS = """\
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #111; -webkit-font-smoothing: antialiased; }}
  .card {{
    width: 1080px; height: 1350px;
    position: relative; overflow: hidden; background: #111;
    --accent: {accent};
  }}
  /* Full-bleed photo */
  .sph-bg {{ position: absolute; inset: 0; z-index: 0; overflow: hidden; }}
  .sph-bg-img {{
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 48%; display: block;
  }}
  .sph-bg-fallback {{
    width: 100%; height: 100%;
    background: repeating-linear-gradient(135deg,#1f1e1c 0 20px,#171614 20px 40px);
  }}
  /* Gradient layers */
  .sph-g {{ position: absolute; inset: 0; z-index: 1; pointer-events: none; }}
  /* Accent corner triangle — top right */
  .sph-corner {{
    position: absolute; top: 0; right: 0; z-index: 10;
    width: 80px; height: 80px; background: var(--accent);
    clip-path: polygon(100% 0, 0 0, 100% 100%);
  }}
  /* Title: small supporting line, white */
  .sph-title {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 800;
    color: #fff; text-transform: uppercase; letter-spacing: .01em;
    line-height: 1; white-space: nowrap;
    text-shadow: 0 2px 10px rgba(0,0,0,.62);
  }}
  /* Price: dominant element, accent color */
  .sph-price {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    color: var(--accent); letter-spacing: -.02em; line-height: .88;
    white-space: nowrap;
    text-shadow: 0 4px 30px rgba(0,0,0,.48);
    margin-top: 6px;
  }}
  /* Hours: small subordinate line */
  .sph-hours {{
    font-family: 'Inter Tight', sans-serif; font-weight: 600;
    font-size: 28px; color: rgba(255,255,255,.75);
    letter-spacing: .10em; text-transform: uppercase;
    margin-top: 16px;
    text-shadow: 0 1px 6px rgba(0,0,0,.55);
  }}
  /* Dealer wordmark: italic, accent-colored, positioned per variant */
  .sph-dealer {{
    position: absolute; z-index: 5;
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    font-style: italic; font-size: 96px;
    color: var(--accent); text-transform: uppercase; line-height: 1;
    white-space: nowrap;
    text-shadow: 0 3px 16px rgba(0,0,0,.45);
  }}"""


# ─────────────────────────────────────────────────────────────────────────────
# Variant A — top-left price (matches reference Bobcat E35 ad)
#
# Hierarchy:  photo → price (top-left) → title (above price) → dealer (bottom)
# Gradient:   diagonal from top-left corner, covers text zone
# ─────────────────────────────────────────────────────────────────────────────

_SPH_A = (
    "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
    "<title>MTM — Price Hero A</title>" + _SPH_FONTS +
    "<style>" + _SPH_BASE_CSS + """
  /* Diagonal gradient from top-left: darkens text zone, clears machine */
  .sph-g1 {{
    background: linear-gradient(148deg,
      rgba(0,0,0,.75) 0%,
      rgba(0,0,0,.48) 25%,
      rgba(0,0,0,.12) 46%,
      rgba(0,0,0,0)   62%);
  }}
  /* Bottom fade: legibility for dealer wordmark */
  .sph-g2 {{
    background: linear-gradient(to top,
      rgba(0,0,0,.52) 0%,
      rgba(0,0,0,0)   22%);
  }}
  /* Text stack: title then price, anchored top-left */
  .sph-stack {{
    position: absolute; top: 54px; left: 52px; z-index: 5;
  }}
  /* Dealer: bottom-left corner */
  .sph-dealer {{ bottom: 50px; left: 52px; }}
</style></head><body>
<div class="card">
  <div class="sph-bg">{photo_html}</div>
  <div class="sph-g sph-g1"></div>
  <div class="sph-g sph-g2"></div>
  <div class="sph-corner"></div>
  <div class="sph-stack">
    {title_el}
    {price_el}
    {hours_el}
  </div>
  {dealer_el}
</div></body></html>"""
)


# ─────────────────────────────────────────────────────────────────────────────
# Variant B — bottom-left price
#
# Machine fills the top ~70%; price + title stack near the bottom-left.
# Gradient:  strong bottom-up, barely touches the top
# ─────────────────────────────────────────────────────────────────────────────

_SPH_B = (
    "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
    "<title>MTM — Price Hero B</title>" + _SPH_FONTS +
    "<style>" + _SPH_BASE_CSS + """
  /* Strong bottom-up gradient; machine visible in top 65% */
  .sph-g1 {{
    background: linear-gradient(to top,
      rgba(0,0,0,.90) 0%,
      rgba(0,0,0,.65) 18%,
      rgba(0,0,0,.25) 40%,
      rgba(0,0,0,0)   58%);
  }}
  /* Subtle top atmosphere */
  .sph-g2 {{
    background: linear-gradient(to bottom,
      rgba(0,0,0,.20) 0%,
      rgba(0,0,0,0)   18%);
  }}
  /* Text stack: title then price, lower-left */
  .sph-stack {{
    position: absolute; bottom: 158px; left: 52px; z-index: 5;
  }}
  /* Dealer: bottom-left, directly below the price stack */
  .sph-dealer {{ bottom: 46px; left: 52px; }}
</style></head><body>
<div class="card">
  <div class="sph-bg">{photo_html}</div>
  <div class="sph-g sph-g1"></div>
  <div class="sph-g sph-g2"></div>
  <div class="sph-corner"></div>
  <div class="sph-stack">
    {title_el}
    {price_el}
    {hours_el}
  </div>
  {dealer_el}
</div></body></html>"""
)


# ─────────────────────────────────────────────────────────────────────────────
# Variant C — centered price overlay
#
# Title sits top-left (small); price is horizontally centered in the lower
# third; dealer wordmark anchors bottom-right.
# Gradient:   bottom-up behind the centered price zone
# ─────────────────────────────────────────────────────────────────────────────

_SPH_C = (
    "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
    "<title>MTM — Price Hero C</title>" + _SPH_FONTS +
    "<style>" + _SPH_BASE_CSS + """
  /* Bottom-center gradient for centered price legibility */
  .sph-g1 {{
    background: linear-gradient(to top,
      rgba(0,0,0,.80) 0%,
      rgba(0,0,0,.52) 22%,
      rgba(0,0,0,.16) 42%,
      rgba(0,0,0,0)   58%);
  }}
  /* Top subtle vignette */
  .sph-g2 {{
    background: linear-gradient(to bottom,
      rgba(0,0,0,.28) 0%,
      rgba(0,0,0,0)   18%);
  }}
  /* Title: top-left, small */
  .sph-title-wrap {{
    position: absolute; top: 58px; left: 52px; z-index: 5;
  }}
  /* Price + hours centered, lower third */
  .sph-price-wrap {{
    position: absolute; left: 0; right: 0; bottom: 185px;
    z-index: 5;
    display: flex; flex-direction: column; align-items: center;
    text-align: center;
  }}
  .sph-price {{ margin-top: 0; }}
  /* Dealer: bottom-right corner */
  .sph-dealer {{ bottom: 50px; right: 52px; text-align: right; }}
</style></head><body>
<div class="card">
  <div class="sph-bg">{photo_html}</div>
  <div class="sph-g sph-g1"></div>
  <div class="sph-g sph-g2"></div>
  <div class="sph-corner"></div>
  <div class="sph-title-wrap">{title_el}</div>
  <div class="sph-price-wrap">
    {price_el}
    {hours_el}
  </div>
  {dealer_el}
</div></body></html>"""
)


_TEMPLATES["simple_price_hero"] = _render_simple_price_hero


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template — "tight_ad"
#
# High-impact marketplace thumbnail: full-bleed photo, top-left price stack,
# left accent rule, italic dealer wordmark bottom-left. Spec-free.
# ─────────────────────────────────────────────────────────────────────────────

def _render_tight_ad(data: dict) -> str:
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    theme_key = (dealer.get("theme") or "yellow").lower().strip()
    accent    = _THEMES.get(theme_key, _THEMES["yellow"])["accent"]

    year      = machine.get("year")
    make      = (machine.get("make")  or "").upper()
    model     = (machine.get("model") or "").upper()
    photo_uri = _photo_data_uri(machine.get("photo_path"))

    price = listing.get("price_usd")
    hours = listing.get("hours")

    show_branding = bool(dealer.get("show_branding", True))
    d_name        = (dealer.get("name") or "").upper()

    # Machine identity line
    title_parts = [p for p in (str(year) if year else "", make, model) if p]
    title_text  = " ".join(title_parts)
    t_len  = len(title_text)
    t_size = 44 if t_len <= 22 else (38 if t_len <= 28 else 32)
    title_el = (
        f'<div class="ta-title" style="font-size:{t_size}px">'
        f'{html.escape(title_text)}</div>'
    ) if title_text else ""

    # Price — reduced ~17% from SPH variant
    if price is not None:
        pstr  = _fmt_price(price)
        plen  = len(pstr)
        psize = 164 if plen <= 7 else (146 if plen <= 8 else 124)
        price_el = (
            f'<div class="ta-price" style="font-size:{psize}px">'
            f'{html.escape(pstr)}</div>'
        )
    else:
        price_el = '<div class="ta-price" style="font-size:76px">CALL FOR PRICE</div>'

    # Hours
    if hours is not None:
        try:
            hrs_str = f"{int(hours):,} HRS"
        except (TypeError, ValueError):
            hrs_str = f"{hours} HRS"
        hours_el = f'<div class="ta-hours">{html.escape(hrs_str)}</div>'
    else:
        hours_el = ""

    # Dealer wordmark
    dealer_el = (
        f'<div class="ta-dealer">{html.escape(d_name)}</div>'
    ) if show_branding and d_name else ""

    if photo_uri:
        photo_html = f'<img class="ta-bg-img" src="{photo_uri}" alt=""/>'
    else:
        photo_html = '<div class="ta-bg-fallback"></div>'

    return _PAGE_TEMPLATE_TIGHT_AD.format(
        accent=accent,
        photo_html=photo_html,
        title_el=title_el,
        price_el=price_el,
        hours_el=hours_el,
        dealer_el=dealer_el,
    )


_PAGE_TEMPLATE_TIGHT_AD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Featured Listing — Tight Ad</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,700;0,800;0,900;1,900&family=Inter+Tight:wght@500;600&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #0d0d0c; -webkit-font-smoothing: antialiased; }}
  .card {{
    width: 1080px; height: 1350px;
    position: relative; overflow: hidden; background: #0d0d0c;
    --accent: {accent};
  }}
  .ta-bg {{ position: absolute; inset: 0; z-index: 0; overflow: hidden; }}
  .ta-bg-img {{
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 45%;
    display: block;
    filter: brightness(1.06) contrast(1.04) saturate(1.05);
  }}
  .ta-bg-fallback {{
    width: 100%; height: 100%;
    background: repeating-linear-gradient(135deg, #1f1e1c 0 20px, #171614 20px 40px);
  }}
  .ta-g1 {{
    position: absolute; inset: 0; z-index: 1; pointer-events: none;
    background: linear-gradient(152deg,
      rgba(0,0,0,.80) 0%,
      rgba(0,0,0,.55) 22%,
      rgba(0,0,0,.16) 40%,
      rgba(0,0,0,0)   54%);
  }}
  .ta-g2 {{
    position: absolute; inset: 0; z-index: 1; pointer-events: none;
    background: linear-gradient(to top,
      rgba(0,0,0,.44) 0%,
      rgba(0,0,0,0)   16%);
  }}
  .ta-rule {{
    position: absolute; top: 0; left: 0; width: 6px; height: 100%;
    background: var(--accent); z-index: 6;
  }}
  .ta-stack {{
    position: absolute; top: 52px; left: 58px; z-index: 5;
  }}
  .ta-title {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 800;
    color: rgba(255,255,255,.88); text-transform: uppercase;
    letter-spacing: .02em; line-height: 1;
    text-shadow: 0 2px 10px rgba(0,0,0,.62);
  }}
  .ta-price {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    color: var(--accent); letter-spacing: -.02em; line-height: .88;
    white-space: nowrap;
    text-shadow: 0 3px 24px rgba(0,0,0,.44);
    margin-top: 6px;
  }}
  .ta-hours {{
    font-family: 'Inter Tight', sans-serif; font-weight: 600;
    font-size: 24px; color: rgba(255,255,255,.62);
    letter-spacing: .10em; text-transform: uppercase;
    margin-top: 12px;
    text-shadow: 0 1px 6px rgba(0,0,0,.55);
  }}
  .ta-dealer {{
    position: absolute; bottom: 44px; left: 58px; z-index: 5;
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    font-style: italic; font-size: 46px;
    color: var(--accent); text-transform: uppercase; line-height: 1;
    white-space: nowrap;
    text-shadow: 0 2px 12px rgba(0,0,0,.48);
  }}
</style>
</head>
<body>
<div class="card">
  <div class="ta-bg">{photo_html}</div>
  <div class="ta-g1"></div>
  <div class="ta-g2"></div>
  <div class="ta-rule"></div>
  <div class="ta-stack">
    {title_el}
    {price_el}
    {hours_el}
  </div>
  {dealer_el}
</div>
</body>
</html>
"""

_TEMPLATES["tight_ad"] = _render_tight_ad


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template — "clean_marketplace"
#
# Restrained inventory card: photo-dominant, minimal overlay, large model
# name, modest price, quiet dealer ID. Safe across bulk inventory feeds.
# ─────────────────────────────────────────────────────────────────────────────

def _render_clean_marketplace(data: dict) -> str:
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    theme_key = (dealer.get("theme") or "yellow").lower().strip()
    accent    = _THEMES.get(theme_key, _THEMES["yellow"])["accent"]

    year      = machine.get("year")
    make      = (machine.get("make")  or "").upper()
    model     = (machine.get("model") or "").upper()
    photo_uri = _photo_data_uri(machine.get("photo_path"))

    price = listing.get("price_usd")
    hours = listing.get("hours")

    show_branding = bool(dealer.get("show_branding", True))
    d_name        = (dealer.get("name") or "").upper()

    # Eyebrow: year · make
    eyebrow_parts = [p for p in (str(year) if year else "", make) if p]
    eyebrow_text  = " · ".join(eyebrow_parts)
    eyebrow_el = (
        f'<div class="cm-eyebrow">{html.escape(eyebrow_text)}</div>'
    ) if eyebrow_text else ""

    # Model — auto-shrink for long names
    mlen = len(model)
    if mlen <= 3:   model_px = 210
    elif mlen <= 4: model_px = 195
    elif mlen <= 5: model_px = 172
    elif mlen <= 7: model_px = 138
    elif mlen <= 9: model_px = 110
    else:           model_px = 88
    model_el = (
        f'<div class="cm-model" style="font-size:{model_px}px">'
        f'{html.escape(model)}</div>'
    ) if model else ""

    # Price
    price_el = ""
    if price is not None:
        pstr = _fmt_price(price)
        if pstr:
            price_el = f'<span class="cm-price">{html.escape(pstr)}</span>'

    # Hours
    hours_el = ""
    if hours is not None:
        try:
            hrs_str = f"{int(hours):,} HRS"
        except (TypeError, ValueError):
            hrs_str = f"{hours} HRS"
        hours_el = f'<span class="cm-hours">{html.escape(hrs_str)}</span>'

    price_row_el = (
        f'<div class="cm-price-row">{price_el}{hours_el}</div>'
    ) if (price_el or hours_el) else ""

    if photo_uri:
        photo_html = f'<img class="cm-photo" src="{photo_uri}" alt=""/>'
    else:
        photo_html = '<div class="cm-photo cm-photo-fallback"></div>'

    dealer_el = (
        f'<div class="cm-dealer">{html.escape(d_name)}</div>'
    ) if show_branding and d_name else ""

    return _PAGE_TEMPLATE_CLEAN_MARKETPLACE.format(
        accent=accent,
        photo_html=photo_html,
        eyebrow_el=eyebrow_el,
        model_el=model_el,
        price_row_el=price_row_el,
        dealer_el=dealer_el,
    )


_PAGE_TEMPLATE_CLEAN_MARKETPLACE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Featured Listing — Clean Marketplace</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800;900&family=Inter+Tight:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #0d0d0c; -webkit-font-smoothing: antialiased; }}
  .card {{
    width: 1080px; height: 1350px;
    position: relative; overflow: hidden; background: #0d0d0c;
    --accent: {accent};
  }}
  .cm-photo {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 44%;
    display: block;
    filter: brightness(1.05) contrast(1.03) saturate(1.04);
  }}
  .cm-photo-fallback {{
    background: repeating-linear-gradient(135deg, #1f1e1c 0 20px, #171614 20px 40px);
  }}
  /* Gentle bottom gradient — enough to read text, no more */
  .cm-scrim {{
    position: absolute; inset: 0; z-index: 1; pointer-events: none;
    background: linear-gradient(to top,
      rgba(0,0,0,.90) 0%,
      rgba(0,0,0,.68) 14%,
      rgba(0,0,0,.28) 30%,
      rgba(0,0,0,.04) 46%,
      rgba(0,0,0,0)   58%);
  }}
  /* Text stack: bottom-left */
  .cm-stack {{
    position: absolute; left: 54px; bottom: 72px; z-index: 5;
  }}
  .cm-eyebrow {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 600;
    font-size: 22px; color: rgba(255,255,255,.58);
    text-transform: uppercase; letter-spacing: .18em;
    margin-bottom: 2px;
  }}
  .cm-model {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    line-height: .84; letter-spacing: -.02em;
    text-transform: uppercase; color: #fff;
    margin-left: -3px;
    text-shadow: 0 2px 18px rgba(0,0,0,.36);
    white-space: nowrap; overflow: hidden;
  }}
  .cm-price-row {{
    display: flex; align-items: baseline; gap: 20px;
    margin-top: 8px;
  }}
  .cm-price {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    font-size: 68px; line-height: .88; letter-spacing: -.02em;
    color: var(--accent);
  }}
  .cm-hours {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 600;
    font-size: 26px; letter-spacing: .12em; text-transform: uppercase;
    color: rgba(255,255,255,.48);
  }}
  /* Dealer: bottom-right, quiet */
  .cm-dealer {{
    position: absolute; bottom: 44px; right: 54px; z-index: 5;
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 20px; letter-spacing: .14em;
    text-transform: uppercase; color: rgba(255,255,255,.40);
    text-align: right; white-space: nowrap;
    text-shadow: 0 1px 6px rgba(0,0,0,.55);
  }}
</style>
</head>
<body>
<div class="card">
  {photo_html}
  <div class="cm-scrim"></div>
  <div class="cm-stack">
    {eyebrow_el}
    {model_el}
    {price_row_el}
  </div>
  {dealer_el}
</div>
</body>
</html>
"""

_TEMPLATES["clean_marketplace"] = _render_clean_marketplace


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template — "split_horizon"
#
# Structured two-zone card: photo fills top 71%, solid dark panel anchors
# bottom 29%. Machine is the hero. Price is clear, not obnoxious.
# ─────────────────────────────────────────────────────────────────────────────

def _render_split_horizon(data: dict) -> str:
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    theme_key = (dealer.get("theme") or "yellow").lower().strip()
    accent    = _THEMES.get(theme_key, _THEMES["yellow"])["accent"]

    year      = machine.get("year")
    make      = (machine.get("make")  or "").upper()
    model     = (machine.get("model") or "").upper()
    photo_uri = _photo_data_uri(machine.get("photo_path"))

    price = listing.get("price_usd")
    hours = listing.get("hours")

    show_branding = bool(dealer.get("show_branding", True))
    d_name        = (dealer.get("name") or "").upper()

    # Eyebrow: year · make · model
    eyebrow_parts = [p for p in (str(year) if year else "", make, model) if p]
    eyebrow_text  = " · ".join(eyebrow_parts)
    eyebrow_el = (
        f'<div class="sh-eyebrow">{html.escape(eyebrow_text)}</div>'
    ) if eyebrow_text else ""

    # Price — restrained, not dominant
    if price is not None:
        pstr  = _fmt_price(price)
        plen  = len(pstr)
        psize = 118 if plen <= 7 else (104 if plen <= 8 else 88)
        price_el = (
            f'<div class="sh-price" style="font-size:{psize}px">'
            f'{html.escape(pstr)}</div>'
        )
    else:
        price_el = '<div class="sh-price" style="font-size:64px">CALL FOR PRICE</div>'

    # Hours
    hours_el = ""
    if hours is not None:
        try:
            hrs_str = f"{int(hours):,} HRS"
        except (TypeError, ValueError):
            hrs_str = f"{hours} HRS"
        hours_el = f'<span class="sh-hours">{html.escape(hrs_str)}</span>'

    # Dealer in panel
    dealer_el = (
        f'<span class="sh-dealer">{html.escape(d_name)}</span>'
    ) if show_branding and d_name else ""

    meta_el = (
        f'<div class="sh-meta">{hours_el}{dealer_el}</div>'
    ) if (hours_el or dealer_el) else ""

    # Photo-zone dealer: small top-left on the photo
    photo_dealer_el = (
        f'<div class="sh-photo-dealer">{html.escape(d_name)}</div>'
    ) if show_branding and d_name else ""

    if photo_uri:
        photo_html = f'<img class="sh-photo-img" src="{photo_uri}" alt=""/>'
    else:
        photo_html = '<div class="sh-photo-fallback"></div>'

    return _PAGE_TEMPLATE_SPLIT_HORIZON.format(
        accent=accent,
        photo_html=photo_html,
        photo_dealer_el=photo_dealer_el,
        eyebrow_el=eyebrow_el,
        price_el=price_el,
        meta_el=meta_el,
    )


_PAGE_TEMPLATE_SPLIT_HORIZON = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Featured Listing — Split Horizon</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,600;0,700;0,800;0,900;1,700&family=Inter+Tight:wght@500;600&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #0d0d0c; -webkit-font-smoothing: antialiased; }}
  .card {{
    width: 1080px; height: 1350px;
    position: relative; overflow: hidden; background: #0d0d0c;
    --accent: {accent};
  }}
  /* Photo zone: top 71% = 960px */
  .sh-photo-zone {{
    position: absolute; top: 0; left: 0; right: 0; height: 960px;
    overflow: hidden;
  }}
  .sh-photo-img {{
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 40%;
    display: block;
    filter: brightness(1.06) contrast(1.04) saturate(1.05);
  }}
  .sh-photo-fallback {{
    width: 100%; height: 100%;
    background: repeating-linear-gradient(135deg, #1f1e1c 0 20px, #171614 20px 40px);
  }}
  /* Subtle top vignette — dealer label legibility */
  .sh-top-fade {{
    position: absolute; top: 0; left: 0; right: 0; height: 140px;
    background: linear-gradient(to bottom, rgba(0,0,0,.30) 0%, rgba(0,0,0,0) 100%);
    pointer-events: none;
  }}
  /* Dealer label: photo top-left */
  .sh-photo-dealer {{
    position: absolute; top: 32px; left: 52px; z-index: 5;
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 20px; color: rgba(255,255,255,.72);
    text-transform: uppercase; letter-spacing: .14em;
    text-shadow: 0 1px 8px rgba(0,0,0,.60);
  }}
  /* Info panel: bottom 29% = 390px */
  .sh-panel {{
    position: absolute; left: 0; right: 0; bottom: 0; height: 390px;
    background: #0d0d0c;
    border-top: 3px solid var(--accent);
    padding: 28px 54px 36px;
    display: flex; flex-direction: column; justify-content: flex-end;
  }}
  .sh-eyebrow {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 22px; color: var(--accent);
    text-transform: uppercase; letter-spacing: .20em;
    margin-bottom: 8px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .sh-price {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    color: #fff; letter-spacing: -.02em; line-height: .88;
    white-space: nowrap; margin-left: -3px;
  }}
  .sh-meta {{
    display: flex; align-items: baseline; justify-content: space-between;
    margin-top: 16px;
  }}
  .sh-hours {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 600;
    font-size: 28px; letter-spacing: .12em; text-transform: uppercase;
    color: rgba(255,255,255,.46);
  }}
  .sh-dealer {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-style: italic; font-size: 28px;
    color: rgba(255,255,255,.34); text-transform: uppercase;
    letter-spacing: .04em; white-space: nowrap;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="sh-photo-zone">
    {photo_html}
    <div class="sh-top-fade"></div>
  </div>
  {photo_dealer_el}
  <div class="sh-panel">
    {eyebrow_el}
    {price_el}
    {meta_el}
  </div>
</div>
</body>
</html>
"""

_TEMPLATES["split_horizon"] = _render_split_horizon


# ─────────────────────────────────────────────────────────────────────────────
# Featured Listing Template — "corner_tag"
#
# Full-bleed hero photo, machine identity top-left, accent price tag anchored
# bottom-right corner. No panel, no rail, no compressed photo zone.
# ─────────────────────────────────────────────────────────────────────────────

def _render_corner_tag(data: dict) -> str:
    machine = data.get("machine") or {}
    dealer  = data.get("dealer")  or {}
    listing = data.get("listing") or {}

    theme_key  = (dealer.get("theme") or "yellow").lower().strip()
    theme      = _THEMES.get(theme_key, _THEMES["yellow"])
    accent     = theme["accent"]
    accent_ink = theme["accent_ink"]

    year      = machine.get("year")
    make      = (machine.get("make")  or "").upper()
    model     = (machine.get("model") or "").upper()
    photo_uri = _photo_data_uri(machine.get("photo_path"))

    price = listing.get("price_usd")
    hours = listing.get("hours")

    show_branding = bool(dealer.get("show_branding", True))
    d_name        = (dealer.get("name") or "").upper()

    # Eyebrow: year · make
    eyebrow_parts = [p for p in (str(year) if year else "", make) if p]
    eyebrow_text  = " · ".join(eyebrow_parts)
    eyebrow_el = (
        f'<div class="ct-eyebrow">{html.escape(eyebrow_text)}</div>'
    ) if eyebrow_text else ""

    # Model — auto-shrink; smaller than clean_marketplace since tag competes
    mlen = len(model)
    if mlen <= 3:   model_px = 154
    elif mlen <= 4: model_px = 140
    elif mlen <= 5: model_px = 122
    elif mlen <= 7: model_px = 100
    elif mlen <= 9: model_px = 82
    else:           model_px = 66
    model_el = (
        f'<div class="ct-model" style="font-size:{model_px}px">'
        f'{html.escape(model)}</div>'
    ) if model else ""

    id_el = (
        f'<div class="ct-id">{eyebrow_el}{model_el}</div>'
    ) if (eyebrow_el or model_el) else ""

    # Price — Barlow Condensed, restrained size
    if price is not None:
        pstr  = _fmt_price(price)
        plen  = len(pstr)
        psize = 88 if plen <= 7 else (78 if plen <= 8 else 66)
        price_el = (
            f'<span class="ct-price" style="font-size:{psize}px">'
            f'{html.escape(pstr)}</span>'
        )
    else:
        price_el = '<span class="ct-price" style="font-size:52px">CALL FOR PRICE</span>'

    # Hours inside tag
    if hours is not None:
        try:
            hrs_str = f"{int(hours):,} HRS"
        except (TypeError, ValueError):
            hrs_str = f"{hours} HRS"
        hours_el = f'<span class="ct-hours">{html.escape(hrs_str)}</span>'
    else:
        hours_el = ""

    tag_el = f'<div class="ct-tag">{price_el}{hours_el}</div>'

    # Dealer: subtle bottom-left
    dealer_el = (
        f'<div class="ct-dealer">{html.escape(d_name)}</div>'
    ) if show_branding and d_name else ""

    if photo_uri:
        photo_html = f'<img class="ct-photo" src="{photo_uri}" alt=""/>'
    else:
        photo_html = '<div class="ct-photo ct-photo-fallback"></div>'

    return _PAGE_TEMPLATE_CORNER_TAG.format(
        accent=accent,
        accent_ink=accent_ink,
        photo_html=photo_html,
        id_el=id_el,
        tag_el=tag_el,
        dealer_el=dealer_el,
    )


_PAGE_TEMPLATE_CORNER_TAG = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM Featured Listing — Corner Tag</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800;900&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #0d0d0c; -webkit-font-smoothing: antialiased; }}
  .card {{
    width: 1080px; height: 1350px;
    position: relative; overflow: hidden; background: #0d0d0c;
    --accent: {accent};
    --accent-ink: {accent_ink};
  }}
  .ct-photo {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    object-fit: cover; object-position: center 42%;
    display: block;
    filter: brightness(1.06) contrast(1.04) saturate(1.05);
  }}
  .ct-photo-fallback {{
    background: repeating-linear-gradient(135deg, #1f1e1c 0 20px, #171614 20px 40px);
  }}
  /* Top-left diagonal scrim — machine ID legibility only */
  .ct-scrim-tl {{
    position: absolute; inset: 0; z-index: 1; pointer-events: none;
    background: linear-gradient(135deg,
      rgba(0,0,0,.50) 0%,
      rgba(0,0,0,.24) 22%,
      rgba(0,0,0,0)   40%);
  }}
  /* Bottom edge — dealer label legibility */
  .ct-scrim-bot {{
    position: absolute; inset: 0; z-index: 1; pointer-events: none;
    background: linear-gradient(to top,
      rgba(0,0,0,.28) 0%,
      rgba(0,0,0,0)   14%);
  }}
  /* Machine identity: top-left */
  .ct-id {{
    position: absolute; top: 46px; left: 54px; z-index: 5;
  }}
  .ct-eyebrow {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 600;
    font-size: 20px; color: rgba(255,255,255,.65);
    text-transform: uppercase; letter-spacing: .16em;
    margin-bottom: 4px;
    text-shadow: 0 1px 8px rgba(0,0,0,.60);
  }}
  .ct-model {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    line-height: .86; letter-spacing: -.02em;
    color: rgba(255,255,255,.92); text-transform: uppercase;
    margin-left: -3px;
    text-shadow: 0 2px 14px rgba(0,0,0,.58);
    white-space: nowrap;
  }}
  /* Price corner tag: bottom-right */
  .ct-tag {{
    position: absolute; right: 0; bottom: 0; z-index: 6;
    background: var(--accent);
    padding: 26px 52px 34px 68px;
    clip-path: polygon(22% 0%, 100% 0%, 100% 100%, 0% 100%);
    text-align: right;
  }}
  .ct-price {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
    color: var(--accent-ink); line-height: .88; letter-spacing: -.02em;
    display: block; white-space: nowrap;
  }}
  .ct-hours {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 22px; color: rgba(13,13,12,.55);
    letter-spacing: .12em; text-transform: uppercase;
    margin-top: 6px; display: block;
  }}
  /* Dealer: subtle bottom-left */
  .ct-dealer {{
    position: absolute; bottom: 44px; left: 54px; z-index: 5;
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 19px; letter-spacing: .14em;
    text-transform: uppercase; color: rgba(255,255,255,.44);
    text-shadow: 0 1px 6px rgba(0,0,0,.55);
    white-space: nowrap;
  }}
</style>
</head>
<body>
<div class="card">
  {photo_html}
  <div class="ct-scrim-tl"></div>
  <div class="ct-scrim-bot"></div>
  {id_el}
  {tag_el}
  {dealer_el}
</div>
</body>
</html>
"""

_TEMPLATES["corner_tag"] = _render_corner_tag


# ─────────────────────────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = {
        "machine": {
            "year": 2020,
            "make": "BOBCAT",
            "model": "T770",
            "equipment_type": "compact_track_loader",
            "horsepower_hp": 92,
            "rated_operating_capacity_lbs": 3475,
            "aux_flow_standard_gpm": 23.0,
            "aux_flow_high_gpm": 36.6,
            "feature_flags": {"high_flow_available": True},
            "photo_path": None,
        },
        "dealer": {
            "theme": "yellow",
            "name": "Coastline Equipment",
            "short_mark": "CE",
            "rep": "Jordan Reyes",
            "phone": "(562) 555-0182",
            "show_branding": True,
        },
        "listing": {"price_usd": 60000, "hours": 200},
    }
    Path("test_card_pricetag.html").write_text(render_card(sample), encoding="utf-8")
    print("wrote test_card_pricetag.html")
