"""
MTM Spec Sheet Renderer — v2 (clean document style)

Clean, flat, single-column document spec sheet (1080×1350 px output).
Image #2 in the listing pack — lighter and calmer than the hero card.

Public API: render_spec_sheet(data: dict) -> str
Data schema unchanged from v1 (adapter-compatible).
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
    "family=Archivo+Black"
    "&family=JetBrains+Mono:wght@400;500;700"
    "&family=Inter:wght@400;500;600;700;800"
    "&display=swap"
)

_OEM_CHECK_SVG = (
    '<svg width="11" height="11" viewBox="0 0 12 12" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<path d="M2.5 6.5L5 9L9.5 3.5" stroke="#2C8A48" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #fff; display: flex; justify-content: center; align-items: flex-start; }

.theme-yellow { --accent: #FFC20E; --accent-text: #0D0D0D; --accent-muted: rgba(13,13,13,0.40); }
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
  background: #F8F6F2;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ── */
.hdr {
  background: var(--accent);
  padding: 17px 22px 15px;
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  flex-shrink: 0;
  min-height: 98px;
}
.hdr-left {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.hdr-year-make {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--accent-muted);
  margin-bottom: 5px;
}
.hdr-model {
  font-family: 'Archivo Black', sans-serif;
  font-size: 40px; line-height: 0.92;
  color: var(--accent-text);
  letter-spacing: -0.02em;
}
.hdr-category {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8px; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--accent-muted);
  margin-top: 8px;
}
.hdr-right {
  text-align: right;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding-top: 2px;
  gap: 6px;
}
.hdr-price {
  font-family: 'Archivo Black', sans-serif;
  font-size: 26px; line-height: 1;
  color: var(--accent-text);
}
.hdr-hours-val {
  font-family: 'Archivo Black', sans-serif;
  font-size: 20px; line-height: 1;
  color: var(--accent-text);
}
.hdr-hours-unit {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; font-weight: 700;
  margin-left: 3px;
  color: var(--accent-muted);
}

/* ── Photo + Hero Rail ── */
.photo-hero {
  display: grid;
  flex-shrink: 0;
  background: #C8C6C0;
}
/* has-photo: 60% image left, 40% light rail right */
.photo-hero.has-photo { grid-template-columns: 60% 40%; }
.photo-hero.no-photo  { grid-template-columns: 1fr; }

.photo-img { overflow: hidden; background: #E0DED9; }
/*
 * Square fix: align-self:start prevents the default grid stretch from overriding
 * aspect-ratio. With start, the image column sizes itself to width×width, which
 * then becomes the row height. The hero-rail (default stretch) fills that height.
 */
.photo-hero.has-photo .photo-img {
  aspect-ratio: 1 / 1;
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
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase;
  color: #B8B5AE;
}

.hero-rail {
  display: grid;
  gap: 1px;
  background: rgba(0,0,0,0.07);
  min-height: 0;
}
/* has-photo: vertical stack — 4 equal rows filling the image height */
.photo-hero.has-photo .hero-rail {
  grid-template-rows: repeat(4, 1fr);
  align-self: stretch;
}
.photo-hero.no-photo .hero-rail {
  grid-template-columns: repeat(2, 1fr);
}
/* Default tile style */
.hero-tile {
  background: #F4F3EF;
  padding: 0 16px;
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  text-align: center;
}
/* has-photo: icon left + text right, row layout */
.photo-hero.has-photo .hero-tile {
  flex-direction: row;
  align-items: center;
  text-align: left;
  gap: 10px;
  border-bottom: 1px solid rgba(0,0,0,0.08);
}
.photo-hero.has-photo .hero-tile:last-child { border-bottom: none; }
.hero-tile-icon { flex-shrink: 0; line-height: 0; }
.hero-tile-text { display: flex; flex-direction: column; }
.photo-hero.no-photo .hero-tile-icon { display: none; }
.photo-hero.no-photo .hero-tile-text { display: contents; }
.hero-val {
  font-family: 'Archivo Black', sans-serif;
  font-size: 22px; color: #1A1A1A; line-height: 1;
}
.hero-unit {
  font-family: 'JetBrains Mono', monospace;
  font-size: 7.5px; color: #999;
  margin-left: 2px;
}
.hero-lbl {
  font-family: 'JetBrains Mono', monospace;
  font-size: 7px; font-weight: 700;
  letter-spacing: 0.13em; text-transform: uppercase;
  color: #7A7875;
  margin-top: 3px;
}

/* ── Main body (two-column layout) ── */
.main {
  flex: 1;
  overflow: hidden;
  padding: 12px 22px 10px;
  display: flex;
  flex-direction: row;
  gap: 14px;
}
.main-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-width: 0;
}

/* ── Section block ── */
.sec { flex-shrink: 0; }
.sec-hdr {
  font-family: 'JetBrains Mono', monospace;
  font-size: 7px; font-weight: 700;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: #6B6967;
  padding-bottom: 5px;
  padding-left: 8px;
  border-bottom: 1px solid rgba(13,13,13,0.10);
  border-left: 3px solid var(--accent);
  margin-bottom: 6px;
}

/* ── Spec rows (dotted leaders) ── */
.spec-rows { display: flex; flex-direction: column; }
.spec-row {
  display: flex;
  align-items: baseline;
  padding: 2px 0;
}
.spec-lbl {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8.5px; font-weight: 500;
  color: #555;
  white-space: nowrap; flex-shrink: 0;
}
.spec-fill {
  flex: 1;
  border-bottom: 1px dotted #C5C2BB;
  margin: 0 5px 3px;
  min-width: 4px;
}
.spec-val {
  font-size: 10px; font-weight: 700;
  color: #1A1A1A;
  white-space: nowrap; flex-shrink: 0;
}
.spec-unit {
  font-family: 'JetBrains Mono', monospace;
  font-size: 7.5px; font-weight: 600;
  color: #999; text-transform: uppercase;
  letter-spacing: 0.04em; margin-left: 2px;
}
.spec-null { color: #C5C2BB; font-weight: 400; }

/* ── Feature list ── */
.feat-list { display: flex; flex-direction: column; }
.feat-item {
  display: flex; align-items: baseline; gap: 7px;
  font-size: 9.5px; font-weight: 500; color: #1E1E1E;
  padding: 3px 0;
}
.feat-bullet { font-size: 9px; line-height: 1; color: #2C8A48; flex-shrink: 0; }

/* ── Condition & Service (flat key: value) ── */
.cond-list { display: flex; flex-direction: column; }
.cond-item {
  font-size: 9px; color: #444; line-height: 1.55;
}
.cond-key {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8.5px; font-weight: 700; color: #1A1A1A;
}

/* ── Footer ── */
.footer {
  border-top: 1px solid #D5D2CC;
  padding: 8px 22px;
  display: flex; align-items: center; gap: 12px;
  flex-shrink: 0; background: #FFFFFF;
  min-height: 50px;
}
.logo-box {
  width: 52px; height: 40px;
  border: 1.5px solid #D5D2CC; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; overflow: hidden; background: #fff;
}
.logo-box img { max-width: 46px; max-height: 34px; object-fit: contain; display: block; }
.logo-placeholder {
  font-size: 7px; font-weight: 700; color: #CACAC5;
  letter-spacing: 0.06em; text-transform: uppercase;
  text-align: center; line-height: 1.4;
}
.dealer-info { flex: 1; min-width: 0; }
.dealer-name {
  font-size: 11px; font-weight: 700; color: #1A1A1A;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.dealer-sub { font-size: 8px; color: #888; margin-top: 2px; line-height: 1.4; }
.oem-badge { display: flex; align-items: center; gap: 5px; flex-shrink: 0; }
.oem-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8.5px; font-weight: 700; color: #2C8A48;
  letter-spacing: 0.03em; white-space: nowrap;
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


_HERO_ICONS: dict[str, str] = {
    "LB": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
        ' fill="none" stroke="#AAAAAA" stroke-width="1.8"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M6 7h12l-1.5-4h-9L6 7z"/>'
        '<rect x="4" y="7" width="16" height="12" rx="1"/>'
        '<path d="M9 12h6"/></svg>'
    ),
    "HP": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
        ' fill="none" stroke="#AAAAAA" stroke-width="1.8"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M5 4a7 7 0 0 0 0 14h2"/>'
        '<path d="M19 4a7 7 0 0 1 0 14h-2"/>'
        '<path d="M9 18v2m6-2v2M9 4V2m6 2V2"/></svg>'
    ),
    "GPM": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
        ' fill="none" stroke="#AAAAAA" stroke-width="1.8"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 2c-4 5-6 9-6 12a6 6 0 0 0 12 0c0-3-2-7-6-12z"/></svg>'
    ),
}
_HERO_ICON_DEFAULT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"'
    ' fill="none" stroke="#AAAAAA" stroke-width="1.8">'
    '<circle cx="12" cy="12" r="8"/></svg>'
)


def _icon_svg(unit: str) -> str:
    return _HERO_ICONS.get((unit or "").upper(), _HERO_ICON_DEFAULT)


def _spec_row_html(label: str, value: Any, unit: str = "") -> str:
    if value is None or value == "":
        val_html = '<span class="spec-val spec-null">\u2014</span>'
    else:
        unit_html = f'<span class="spec-unit">{_esc(unit)}</span>' if unit else ""
        val_html = f'<span class="spec-val">{_esc(str(value))}{unit_html}</span>'
    return (
        f'<div class="spec-row">'
        f'<span class="spec-lbl">{_esc(label)}</span>'
        f'<span class="spec-fill"></span>'
        f'{val_html}'
        f'</div>'
    )


def _section(title: str, inner_html: str) -> str:
    return (
        f'<div class="sec">'
        f'<div class="sec-hdr">{_esc(title)}</div>'
        f'{inner_html}'
        f'</div>'
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
        price_html = f'<div class="hdr-price">{_esc(p)}</div>'

    hours_html = ""
    raw_hrs = listing.get("hours")
    if raw_hrs is not None:
        hrs = _fmt_hours(raw_hrs)
        hours_html = (
            f'<div>'
            f'<span class="hdr-hours-val">{_esc(hrs)}</span>'
            f'<span class="hdr-hours-unit">HRS</span>'
            f'</div>'
        )

    # ── Photo + Hero Rail ──
    photo_uri   = _photo_data_uri(machine.get("photo_path"))
    hero_tiles  = specs.get("hero") or []
    photo_cls   = "has-photo" if photo_uri else "no-photo"

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
            f'<div class="hero-tile-icon">{_icon_svg(unit)}</div>'
            f'<div class="hero-tile-text">'
            f'<div class="hero-val">{val}{unit_html}</div>'
            f'<div class="hero-lbl">{lbl}</div>'
            f'</div>'
            f'</div>'
        )

    # ── Specifications section — split into primary (left) + secondary (right) ──
    additional = specs.get("additional") or []
    primary_specs   = additional[:4]
    secondary_specs = additional[4:8]

    add_rows_html = ""
    for row in primary_specs:
        add_rows_html += _spec_row_html(
            row.get("label", ""), row.get("value"), row.get("unit", "")
        )
    add_section = _section(
        "SPECIFICATIONS",
        f'<div class="spec-rows">{add_rows_html}</div>',
    ) if add_rows_html else ""

    sec_rows_html = ""
    for row in secondary_specs:
        sec_rows_html += _spec_row_html(
            row.get("label", ""), row.get("value"), row.get("unit", "")
        )
    sec_section = _section(
        "SECONDARY SPECS",
        f'<div class="spec-rows">{sec_rows_html}</div>',
    ) if sec_rows_html else ""

    # ── Key Features section ──
    feat_items = ""
    for feat in (features or [])[:8]:
        feat_items += (
            f'<div class="feat-item">'
            f'<span class="feat-bullet">✓</span>'
            f'{_esc(feat)}'
            f'</div>'
        )
    feat_section = _section(
        "KEY FEATURES",
        f'<div class="feat-list">{feat_items}</div>',
    ) if feat_items else ""

    # ── Dealer footer ──
    d_name  = dealer.get("name")          or ""
    d_phone = dealer.get("phone")         or ""
    d_loc   = dealer.get("location")      or ""
    d_logo  = dealer.get("logo_data_uri")

    if d_logo:
        logo_inner = f'<img src="{d_logo}" alt="dealer logo">'
    else:
        logo_inner = '<div class="logo-placeholder">YOUR<br>LOGO</div>'

    sub_parts = [x for x in [d_phone, d_loc] if x]
    sub_html = (
        f'<div class="dealer-sub">'
        + " &nbsp;&middot;&nbsp; ".join(_esc(x) for x in sub_parts)
        + '</div>'
    ) if sub_parts else ""

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
      {add_section}
      {feat_section}
    </div>
    <div class="main-col">
      {sec_section}
    </div>
  </div>

  <div class="footer">
    <div class="logo-box">{logo_inner}</div>
    {'<div class="dealer-info"><div class="dealer-name">' + _esc(d_name) + '</div>' + sub_html + '</div>' if d_name else ''}
    <div class="oem-badge">
      {_OEM_CHECK_SVG}
      <span class="oem-text">OEM Verified Specs</span>
    </div>
  </div>

</div>
</body>
</html>"""
