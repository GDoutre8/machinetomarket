"""
MTM Spec Sheet Renderer — v3 (locked field architecture)

Locked layout: yellow header · photo/hero rail · core specs + features ·
               condition/service + performance data · 3-column footer.

Public API: render_spec_sheet(data: dict) -> str
Data schema:
  machine:  year, make, model, category, photo_path
  listing:  price_usd, hours, hours_qualifier, condition, track_pct, notes, stock_number
  specs:    hero (tiles w/ icon field), core (rows), performance (rows), additional (rows)
  features: [str]
  dealer:   name, phone, website, location, logo_data_uri, theme
"""

from __future__ import annotations

import base64
import concurrent.futures
import html
from pathlib import Path
from typing import Any

_VALID_THEMES = {"yellow", "red", "blue", "green", "orange"}

_EQ_TYPE_DISPLAY = {
    "compact_track_loader": "Compact Track Loader",
    "skid_steer":           "Skid Steer Loader",
    "mini_excavator":       "Mini Excavator",
    "backhoe_loader":       "Backhoe Loader",
    "large_excavator":      "Large Excavator",
    "excavator":            "Excavator",
    "telehandler":          "Telehandler",
}

_GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=JetBrains+Mono:wght@400;500;700"
    "&family=Inter:wght@400;500;600;700;800"
    "&display=swap"
)

_OEM_CHECK_SVG = (
    '<svg width="11" height="11" viewBox="0 0 12 12" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<path d="M2.5 6.5L5 9L9.5 3.5" stroke="#2C8A48" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)

# ── Hero tile icons ───────────────────────────────────────────────────────────
_ICON_ROC = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
    ' fill="none" stroke="#AAAAAA" stroke-width="1.8"'
    ' stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M5 8h14l-1.5 10h-11L5 8z"/>'
    '<path d="M9 8V6a3 3 0 0 1 6 0v2"/>'
    '</svg>'
)
_ICON_HP = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
    ' fill="none" stroke="#AAAAAA" stroke-width="1.8"'
    ' stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M13 2L4.5 13.5H12L11 22L19.5 10.5H12L13 2z"/>'
    '</svg>'
)
_ICON_DROPLET = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
    ' fill="none" stroke="#AAAAAA" stroke-width="1.8"'
    ' stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 2c-4 5-6 9-6 12a6 6 0 0 0 12 0c0-3-2-7-6-12z"/>'
    '</svg>'
)
_ICON_ARROW_UP = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
    ' fill="none" stroke="#AAAAAA" stroke-width="1.8"'
    ' stroke-linecap="round" stroke-linejoin="round">'
    '<line x1="12" y1="19" x2="12" y2="5"/>'
    '<polyline points="5 12 12 5 19 12"/>'
    '</svg>'
)
_ICON_WEIGHT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
    ' fill="none" stroke="#AAAAAA" stroke-width="1.8"'
    ' stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M5 8h14l-2 13H7L5 8z"/>'
    '<path d="M8 8a4 4 0 0 1 8 0"/>'
    '</svg>'
)
_ICON_DEFAULT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
    ' fill="none" stroke="#AAAAAA" stroke-width="1.8">'
    '<circle cx="12" cy="12" r="8"/>'
    '</svg>'
)

# Keyed by adapter icon name AND by unit for backwards compat.
_HERO_ICONS: dict[str, str] = {
    "roc":          _ICON_ROC,
    "hp":           _ICON_HP,
    "horsepower":   _ICON_HP,
    "aux_flow":     _ICON_DROPLET,
    "lift_path":    _ICON_ARROW_UP,
    "lift_height":  _ICON_ARROW_UP,
    "weight":       _ICON_WEIGHT,
    # Unit-based fallbacks
    "LB":           _ICON_WEIGHT,
    "HP":           _ICON_HP,
    "GPM":          _ICON_DROPLET,
}

# ── Footer contact icons ──────────────────────────────────────────────────────
_ICON_PHONE = (
    '<svg width="9" height="9" viewBox="0 0 24 24" fill="none"'
    ' stroke="#8A8784" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07'
    ' A19.5 19.5 0 0 1 3.09 11.9 19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3'
    'a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91'
    'a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7'
    'A2 2 0 0 1 22 16.92z"/>'
    '</svg>'
)
_ICON_GLOBE = (
    '<svg width="9" height="9" viewBox="0 0 24 24" fill="none"'
    ' stroke="#8A8784" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="10"/>'
    '<path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10'
    ' 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
    '</svg>'
)
_ICON_PIN = (
    '<svg width="9" height="9" viewBox="0 0 24 24" fill="none"'
    ' stroke="#8A8784" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>'
    '<circle cx="12" cy="10" r="3"/>'
    '</svg>'
)

# ── Stylesheet ────────────────────────────────────────────────────────────────
_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #fff; display: flex; justify-content: center; align-items: flex-start; }

.theme-yellow { --accent: #FFC20E; --accent-text: #0D0D0D; --accent-muted: rgba(13,13,13,0.38); }
.theme-red    { --accent: #C8102E; --accent-text: #fff;    --accent-muted: rgba(255,255,255,0.60); }
.theme-blue   { --accent: #1E4D8C; --accent-text: #fff;    --accent-muted: rgba(255,255,255,0.60); }
.theme-green  { --accent: #2C5F3E; --accent-text: #fff;    --accent-muted: rgba(255,255,255,0.60); }
.theme-orange { --accent: #D85A15; --accent-text: #fff;    --accent-muted: rgba(255,255,255,0.60); }

/* ── Sheet container ── */
.sheet {
  width: 540px;
  height: 675px;
  font-family: 'Inter', sans-serif;
  -webkit-font-smoothing: antialiased;
  background: #F7F5F1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ── */
.hdr {
  background: var(--accent);
  padding: 12px 22px 11px;
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  flex-shrink: 0;
  min-height: 88px;
}
.hdr-left {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.hdr-year-make {
  font-size: 9px; font-weight: 500;
  letter-spacing: 0.13em; text-transform: uppercase;
  color: var(--accent-muted);
  margin-bottom: 3px;
}
.hdr-model {
  font-size: 36px; line-height: 0.92; font-weight: 800;
  color: var(--accent-text);
  letter-spacing: -0.025em;
}
.hdr-category {
  font-size: 8px; font-weight: 600;
  letter-spacing: 0.17em; text-transform: uppercase;
  color: var(--accent-muted);
  margin-top: 6px;
}
.hdr-right {
  text-align: right;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
  gap: 5px;
}
.hdr-price-block { display: flex; flex-direction: column; align-items: flex-end; }
.hdr-price {
  font-size: 24px; line-height: 1; font-weight: 800;
  color: var(--accent-text);
  letter-spacing: -0.01em;
}
.hdr-sublabel {
  font-size: 7px; font-weight: 600;
  letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--accent-muted);
  margin-top: 3px;
}
.hdr-hours-block { display: flex; flex-direction: column; align-items: flex-end; }
.hdr-hours-val {
  font-size: 19px; line-height: 1; font-weight: 800;
  color: var(--accent-text);
}
.hdr-hours-unit {
  font-size: 9px; font-weight: 600;
  margin-left: 3px;
  color: var(--accent-muted);
}

/* ── Photo + Hero Rail ── */
/* 55/45 split: wider spec rail than v2 */
.photo-hero {
  display: grid;
  flex-shrink: 0;
  background: #CCCAC4;
}
.photo-hero.has-photo { grid-template-columns: 55% 45%; }
.photo-hero.no-photo  { grid-template-columns: 1fr; }

.photo-img { overflow: hidden; background: #E0DED9; }
.photo-hero.has-photo .photo-img {
  aspect-ratio: 4 / 3;
  width: 100%;
  align-self: start;
}
.photo-img img {
  width: 100%; height: 100%;
  object-fit: cover; object-position: center;
  display: block;
}
.photo-pending-bg {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  background: #E0DED9;
  font-size: 9px; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: #B8B5AE;
}

.hero-rail {
  display: grid;
  gap: 1px;
  background: rgba(0,0,0,0.06);
  min-height: 0;
}
.photo-hero.has-photo .hero-rail {
  grid-template-rows: repeat(4, 1fr);
  align-self: stretch;
}
.photo-hero.no-photo .hero-rail {
  grid-template-columns: repeat(2, 1fr);
}
.hero-tile {
  background: #F4F3EF;
  padding: 0 12px;
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  text-align: center;
}
.photo-hero.has-photo .hero-tile {
  flex-direction: row;
  align-items: center;
  text-align: left;
  gap: 8px;
  border-bottom: 1px solid rgba(0,0,0,0.07);
}
.photo-hero.has-photo .hero-tile:last-child { border-bottom: none; }
.hero-tile-icon { flex-shrink: 0; line-height: 0; opacity: 0.55; }
.hero-tile-text { display: flex; flex-direction: column; min-width: 0; }
.photo-hero.no-photo .hero-tile-icon { display: none; }
.photo-hero.no-photo .hero-tile-text { display: contents; }
.hero-val {
  font-size: 17px; font-weight: 800; color: #1A1A1A; line-height: 1;
  white-space: nowrap;
}
.hero-unit {
  font-size: 8px; font-weight: 600; color: #AAAAAA;
  margin-left: 2px; letter-spacing: 0.04em;
}
.hero-lbl {
  font-size: 6.5px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: #8A8784;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Mid body: core specs + features ── */
.main {
  flex: 1;
  overflow: hidden;
  padding: 9px 22px 0;
  display: flex;
  flex-direction: row;
  gap: 16px;
}
.main-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}

/* ── Lower section: condition + performance ── */
.lower {
  padding: 7px 22px 0;
  display: flex;
  flex-direction: row;
  gap: 16px;
  flex-shrink: 0;
}
.lower-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ── Section block ── */
.sec { flex-shrink: 0; }
.sec-hdr {
  font-size: 6.5px; font-weight: 700;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: #6B6967;
  padding-bottom: 5px;
  padding-left: 7px;
  border-bottom: 1px solid rgba(13,13,13,0.09);
  border-left: 3px solid var(--accent);
  margin-bottom: 5px;
}
.sec-footnote {
  font-size: 6px; color: #BBBBBB; line-height: 1.4;
  margin-top: 4px; padding-left: 1px;
}

/* ── Spec rows (dotted leaders) ── */
.spec-rows { display: flex; flex-direction: column; }
.spec-row {
  display: flex;
  align-items: baseline;
  padding: 1.5px 0;
}
.spec-lbl {
  font-size: 8px; font-weight: 400;
  color: #888888;
  white-space: nowrap; flex-shrink: 0;
}
.spec-fill {
  flex: 1;
  border-bottom: 1px dotted #C8C5BE;
  margin: 0 5px 3px;
  min-width: 4px;
}
.spec-val {
  font-size: 9px; font-weight: 700;
  color: #1A1A1A;
  white-space: nowrap; flex-shrink: 0;
}
.spec-unit {
  font-size: 7px; font-weight: 600;
  color: #AAAAAA; text-transform: uppercase;
  letter-spacing: 0.04em; margin-left: 2px;
}

/* ── Feature list ── */
.feat-list { display: flex; flex-direction: column; }
.feat-item {
  display: flex; align-items: baseline; gap: 6px;
  font-size: 8.5px; font-weight: 500; color: #1E1E1E;
  padding: 2px 0;
}
.feat-bullet {
  flex-shrink: 0; line-height: 0;
  margin-top: 1px;
}

/* ── Condition rows ── */
.cond-rows { display: flex; flex-direction: column; }
.cond-row {
  display: flex; align-items: baseline;
  padding: 1.5px 0;
}
.cond-lbl {
  font-size: 7.5px; font-weight: 600;
  color: #999; white-space: nowrap; flex-shrink: 0;
  text-transform: uppercase; letter-spacing: 0.09em;
  width: 56px;
}
.cond-val {
  font-size: 8.5px; font-weight: 600; color: #1A1A1A;
}

/* ── Notes inset block ── */
.notes-block {
  margin-top: 7px;
  background: rgba(255, 194, 14, 0.09);
  border-left: 3px solid var(--accent);
  padding: 5px 8px 6px;
}
.notes-hdr {
  font-size: 6px; font-weight: 700;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: #7A6E30;
  margin-bottom: 3px;
}
.notes-body {
  font-size: 7.5px; font-style: italic;
  color: #4A3F20;
  line-height: 1.45;
}

/* ── Footer — 3-column grid ── */
.footer {
  border-top: 1px solid rgba(0,0,0,0.08);
  padding: 6px 22px 5px;
  display: grid;
  grid-template-columns: 52px 1fr auto;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
  background: #FFFFFF;
  min-height: 46px;
}
.footer-left {
  display: flex;
  align-items: center;
  justify-content: flex-start;
}
.logo-box {
  width: 46px; height: 34px;
  border: 1.5px solid #E2DFD9; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden; background: #fff;
  flex-shrink: 0;
}
.logo-box img { max-width: 40px; max-height: 28px; object-fit: contain; display: block; }
.logo-placeholder {
  font-size: 7px; font-weight: 700; color: #CACAC5;
  letter-spacing: 0.06em; text-transform: uppercase;
  text-align: center; line-height: 1.4;
}
.footer-mid {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.dealer-name {
  font-size: 9.5px; font-weight: 700; color: #1A1A1A;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 2px;
}
.footer-contact-row {
  display: flex; align-items: center; gap: 4px;
  font-size: 7.5px; color: #666;
  line-height: 1.3;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.footer-contact-row svg { flex-shrink: 0; }
.footer-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.oem-badge {
  display: flex; flex-direction: column; align-items: flex-end;
  gap: 2px; flex-shrink: 0;
}
.oem-badge-row { display: flex; align-items: center; gap: 4px; }
.oem-text {
  font-size: 7.5px; font-weight: 700; color: #2C8A48;
  letter-spacing: 0.03em; white-space: nowrap;
}
.oem-sub {
  font-size: 6px; color: #AAA; white-space: nowrap;
}

/* ── Disclaimer ── */
.footer-disclaimer {
  background: #FFFFFF;
  padding: 0 22px 5px;
  font-size: 6px; color: #CCCCCC;
  text-align: center; line-height: 1.5;
  flex-shrink: 0;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _photo_data_uri(photo_path: str | None) -> str | None:
    if not photo_path:
        return None
    path = Path(photo_path)
    if not path.is_file():
        return None
    suffix = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp",
    }.get(suffix, "image/jpeg")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _fmt_price(val: Any) -> str | None:
    if val is None:
        return None
    try:
        return f"${int(val):,}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_hours(val: Any) -> str | None:
    if val is None:
        return None
    try:
        return f"{int(val):,}"
    except (TypeError, ValueError):
        return str(val)


def _esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def _icon_svg(tile: dict | str) -> str:
    """Return hero tile SVG icon. Accepts tile dict (uses 'icon' then 'unit') or plain key str."""
    if isinstance(tile, dict):
        key = (tile.get("icon") or "").lower()
        unit = (tile.get("unit") or "").upper()
    else:
        key = str(tile).lower()
        unit = str(tile).upper()
    return (
        _HERO_ICONS.get(key)
        or _HERO_ICONS.get(unit)
        or _ICON_DEFAULT
    )


def _spec_row_html(label: str, value: Any, unit: str = "") -> str:
    if value is None or value == "":
        return ""
    unit_html = f'<span class="spec-unit">{_esc(unit)}</span>' if unit else ""
    return (
        f'<div class="spec-row">'
        f'<span class="spec-lbl">{_esc(label)}</span>'
        f'<span class="spec-fill"></span>'
        f'<span class="spec-val">{_esc(str(value))}{unit_html}</span>'
        f'</div>'
    )


def _section(title: str, inner_html: str) -> str:
    return (
        f'<div class="sec">'
        f'<div class="sec-hdr">{_esc(title)}</div>'
        f'{inner_html}'
        f'</div>'
    )


_FEAT_CHECK_SVG = (
    '<svg width="9" height="9" viewBox="0 0 12 12" fill="none"'
    ' xmlns="http://www.w3.org/2000/svg">'
    '<path d="M2 6.5L4.5 9L10 3.5" stroke="#2C8A48" stroke-width="1.8"'
    ' stroke-linecap="round" stroke-linejoin="round"/>'
    '</svg>'
)


# ─────────────────────────────────────────────────────────────────────────────
# Main renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_spec_sheet(data: dict) -> str:
    machine   = data.get("machine")   or {}
    listing   = data.get("listing")   or {}
    specs     = data.get("specs")     or {}
    features  = data.get("features")  or []
    dealer    = data.get("dealer")    or {}

    # ── Theme ──
    theme = (dealer.get("theme") or "yellow").lower().strip()
    if theme not in _VALID_THEMES:
        theme = "yellow"

    # ── Header ──
    year  = machine.get("year")
    make  = (machine.get("make") or "").upper()
    model = machine.get("model") or ""
    cat   = machine.get("category") or ""

    year_make = " \u00b7 ".join(x for x in [str(year) if year else "", make] if x)

    price_html = ""
    p = _fmt_price(listing.get("price_usd"))
    if p:
        price_html = (
            f'<div class="hdr-price-block">'
            f'<div class="hdr-price">{_esc(p)}</div>'
            f'<div class="hdr-sublabel">Asking Price</div>'
            f'</div>'
        )

    hours_html = ""
    raw_hrs = listing.get("hours")
    hrs = _fmt_hours(raw_hrs)
    if hrs:
        hours_html = (
            f'<div class="hdr-hours-block">'
            f'<div>'
            f'<span class="hdr-hours-val">{_esc(hrs)}</span>'
            f'<span class="hdr-hours-unit">HRS</span>'
            f'</div>'
            f'<div class="hdr-sublabel">Hours</div>'
            f'</div>'
        )

    # ── Photo + Hero Rail ──
    photo_uri  = _photo_data_uri(machine.get("photo_path"))
    hero_tiles = specs.get("hero") or []
    photo_cls  = "has-photo" if photo_uri else "no-photo"

    if photo_uri:
        photo_cell = (
            f'<div class="photo-img">'
            f'<img src="{photo_uri}" alt="machine photo">'
            f'</div>'
        )
    else:
        photo_cell = (
            '<div class="photo-img">'
            '<div class="photo-pending-bg">Photo Pending</div>'
            '</div>'
        )

    tile_cells = ""
    for t in hero_tiles[:4]:
        val  = _esc(str(t.get("value", "\u2014")))
        unit = t.get("unit", "")
        lbl  = _esc(str(t.get("label", "")))
        unit_html = f'<span class="hero-unit">{_esc(unit)}</span>' if unit else ""
        tile_cells += (
            f'<div class="hero-tile">'
            f'<div class="hero-tile-icon">{_icon_svg(t)}</div>'
            f'<div class="hero-tile-text">'
            f'<div class="hero-val">{val}{unit_html}</div>'
            f'<div class="hero-lbl">{lbl}</div>'
            f'</div>'
            f'</div>'
        )

    # ── Core Specs ──
    # Use specs.core (locked field list from adapter). Fallback to additional[:5] for
    # backwards compat with older adapter versions that don't set specs.core.
    core_spec_rows = specs.get("core") or []
    if not core_spec_rows:
        core_spec_rows = (specs.get("additional") or [])[:5]

    core_rows_html = ""
    for row in core_spec_rows:
        core_rows_html += _spec_row_html(
            row.get("label", ""), row.get("value"), row.get("unit", "")
        )
    core_section = _section(
        "CORE SPECS \u2014 OEM VERIFIED",
        f'<div class="spec-rows">{core_rows_html}</div>'
        + '<div class="sec-footnote">*Sourced from OEM publications. May vary with options.</div>',
    ) if core_rows_html else ""

    # ── Key Features ──
    feat_items = ""
    for feat in (features or [])[:8]:
        feat_items += (
            f'<div class="feat-item">'
            f'<span class="feat-bullet">{_FEAT_CHECK_SVG}</span>'
            f'{_esc(feat)}'
            f'</div>'
        )
    feat_section = _section(
        "KEY FEATURES",
        f'<div class="feat-list">{feat_items}</div>',
    ) if feat_items else ""

    # ── Condition & Service ──
    hours_qualifier = listing.get("hours_qualifier")
    condition       = listing.get("condition")
    track_pct       = listing.get("track_pct")
    notes_text      = listing.get("notes")

    cond_rows_html = ""
    if hrs:
        hrs_display = (
            f"{_esc(hrs)} ({_esc(hours_qualifier)})"
            if hours_qualifier
            else _esc(hrs)
        )
        cond_rows_html += (
            f'<div class="cond-row">'
            f'<span class="cond-lbl">Hours</span>'
            f'<span class="cond-val">{hrs_display}</span>'
            f'</div>'
        )
    if track_pct:
        cond_rows_html += (
            f'<div class="cond-row">'
            f'<span class="cond-lbl">Track</span>'
            f'<span class="cond-val">{_esc(str(track_pct))}</span>'
            f'</div>'
        )
    if condition:
        cond_rows_html += (
            f'<div class="cond-row">'
            f'<span class="cond-lbl">Condition</span>'
            f'<span class="cond-val">{_esc(str(condition))}</span>'
            f'</div>'
        )

    notes_block_html = ""
    if notes_text:
        notes_block_html = (
            f'<div class="notes-block">'
            f'<div class="notes-hdr">Notes</div>'
            f'<div class="notes-body">{_esc(str(notes_text))}</div>'
            f'</div>'
        )

    cond_section = _section(
        "CONDITION & SERVICE",
        f'<div class="cond-rows">{cond_rows_html}</div>{notes_block_html}',
    ) if (cond_rows_html or notes_block_html) else ""

    # ── Performance Data ──
    perf_rows = specs.get("performance") or []
    perf_rows_html = ""
    for row in perf_rows:
        perf_rows_html += _spec_row_html(
            row.get("label", ""), row.get("value"), row.get("unit", "")
        )
    perf_section = _section(
        "PERFORMANCE DATA",
        f'<div class="spec-rows">{perf_rows_html}</div>',
    ) if perf_rows_html else ""

    has_lower = bool(cond_section or perf_section)

    # ── Footer ──
    d_name    = dealer.get("name")          or ""
    d_phone   = dealer.get("phone")         or ""
    d_website = dealer.get("website")       or ""
    d_loc     = dealer.get("location")      or ""
    d_logo    = dealer.get("logo_data_uri")

    if d_logo:
        logo_inner = f'<img src="{d_logo}" alt="dealer logo">'
    else:
        logo_inner = '<div class="logo-placeholder">YOUR<br>LOGO</div>'

    footer_mid_rows = ""
    if d_name:
        footer_mid_rows += f'<div class="dealer-name">{_esc(d_name)}</div>'
    if d_phone:
        footer_mid_rows += (
            f'<div class="footer-contact-row">'
            f'{_ICON_PHONE}<span>{_esc(d_phone)}</span>'
            f'</div>'
        )
    if d_website:
        footer_mid_rows += (
            f'<div class="footer-contact-row">'
            f'{_ICON_GLOBE}<span>{_esc(d_website)}</span>'
            f'</div>'
        )
    if d_loc:
        footer_mid_rows += (
            f'<div class="footer-contact-row">'
            f'{_ICON_PIN}<span>{_esc(d_loc)}</span>'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{_GOOGLE_FONTS}" rel="stylesheet">
<style>{_CSS}</style>
</head>
<body>
<div class="sheet theme-{theme}">

  <div class="hdr">
    <div class="hdr-left">
      <div class="hdr-year-make">{_esc(year_make)}</div>
      <div class="hdr-model">{_esc(model)}</div>
      {'<div class="hdr-category">' + _esc(cat) + '</div>' if cat else ''}
    </div>
    <div class="hdr-right">
      {price_html}
      {hours_html}
    </div>
  </div>

  <div class="photo-hero {photo_cls}">
    {photo_cell}
    <div class="hero-rail">{tile_cells}</div>
  </div>

  <div class="main">
    <div class="main-col">
      {core_section}
    </div>
    <div class="main-col">
      {feat_section}
    </div>
  </div>

  {('<div class="lower"><div class="lower-col">' + cond_section + '</div><div class="lower-col">' + perf_section + '</div></div>') if has_lower else ''}

  <div class="footer">
    <div class="footer-left">
      <div class="logo-box">{logo_inner}</div>
    </div>
    <div class="footer-mid">
      {footer_mid_rows}
    </div>
    <div class="footer-right">
      <div class="oem-badge">
        <div class="oem-badge-row">
          {_OEM_CHECK_SVG}
          <span class="oem-text">OEM Verified Specs</span>
        </div>
        <div class="oem-sub">Sourced from manufacturer data</div>
      </div>
    </div>
  </div>

  <div class="footer-disclaimer">
    Specifications sourced from OEM publications and may vary with options or configuration. Contact dealer to confirm availability and pricing.
  </div>

</div>
</body>
</html>"""
