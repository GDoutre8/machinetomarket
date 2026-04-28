"""
MTM Spec Sheet Renderer — v4 (handoff-aligned layout)

Locked layout: black top rule · CAT-yellow header · photo + 4-row KPI rail ·
               core specs · features (with optional attachment chips) ·
               condition + performance · dealer footer with OEM verified mark.

CSS canvas is 540 x 675; export pipeline screenshots .sheet at
device_scale_factor=2.0 → final PNG is 1080 x 1350. All design tokens from the
handoff README are halved so visual proportions match the 1080-native spec.

Public API: render_spec_sheet(data: dict) -> str
Data schema (unchanged from v3):
  machine:  year, make, model, category, photo_path
  listing:  price_usd, hours, hours_qualifier, condition, track_pct, notes
  specs:    hero (4 KPI tiles), core (rows), performance (rows), additional (rows)
  features: [str]
  dealer:   name, phone, website, location, logo_data_uri, theme
"""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from typing import Any

_VALID_THEMES = {"yellow", "red", "blue", "green", "orange"}

_GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Barlow+Condensed:wght@700;800;900"
    "&family=Inter+Tight:wght@500;600;700;800"
    "&family=JetBrains+Mono:wght@500;700"
    "&display=swap"
)

# Brand tokens (handoff README)
_INK      = "#0d0d0c"
_PAPER    = "#f6f4ef"
_PANEL    = "#ffffff"
_CHIP_BG  = "#f1ede2"
_VERIFIED = "#1F8A3B"

_THEME_ACCENTS = {
    "yellow": "#FFC600",
    "red":    "#C8102E",
    "blue":   "#1E4D8C",
    "green":  "#2C5F3E",
    "orange": "#D85A15",
}


# ── Stylesheet (all px values halved from 1080-native handoff spec) ──────────
_CSS_TEMPLATE = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { background: #fff; }
body { display: flex; justify-content: center; align-items: flex-start;
       font-family: 'Inter Tight', system-ui, sans-serif;
       -webkit-font-smoothing: antialiased; }

.sheet {
  position: relative;
  width: 540px;
  height: 675px;
  flex-shrink: 0;
  background: __PAPER__;
  color: __INK__;
  overflow: hidden;
  font-family: 'Inter Tight', system-ui, sans-serif;
}

/* 4px black top rule (2px in half-scale) above the yellow header */
.top-rule {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: __INK__; z-index: 2;
}

/* ── HEADER ── (61px = 122/2) */
.hdr {
  position: absolute; top: 0; left: 0; right: 0; height: 61px;
  background: __ACCENT__;
  box-shadow: inset 0 -4px 6px -4px rgba(0,0,0,.18);
  display: flex; justify-content: space-between; align-items: stretch;
  padding: 8px 22px 8px;
}
.hdr-left  { display: flex; flex-direction: column; justify-content: flex-start; min-width: 0; }
.hdr-right { display: flex; flex-direction: column; align-items: flex-end; justify-content: space-between; flex-shrink: 0; }

.hdr-eyebrow {
  font: 700 7px/1 'Inter Tight', sans-serif;
  letter-spacing: .32em; text-transform: uppercase;
  color: rgba(13,13,12,.70);
  white-space: nowrap;
}
.hdr-model {
  font: 900 42px/.86 'Barlow Condensed', Impact, sans-serif;
  letter-spacing: -.02em; color: __INK__;
  margin-top: 4px;
  white-space: nowrap;
}
.hdr-accent {
  width: 36px; height: 1px; background: __INK__;
  margin-top: 4px;
}

.hdr-price {
  font: 900 30px/1 'Barlow Condensed', Impact, sans-serif;
  letter-spacing: -.01em; color: __INK__;
  white-space: nowrap;
}
.hdr-divider { width: 48px; height: 1px; background: rgba(13,13,12,.40); margin: 3px 0; }
.hdr-hours-row { display: flex; align-items: baseline; gap: 4px; }
.hdr-hours-val { font: 800 14px/1 'Barlow Condensed', Impact, sans-serif; color: __INK__; }
.hdr-hours-lbl { font: 700 6px/1 'Inter Tight', sans-serif; letter-spacing: .2em; color: rgba(13,13,12,.70); }

/* ── PHOTO + KPI BAND ── (top 61, height 240) */
.photo-band {
  position: absolute; top: 61px; left: 0; right: 0; height: 240px;
  display: grid; grid-template-columns: 280px 1fr;
  background: __PANEL__;
}
.photo-cell {
  position: relative; overflow: hidden; background: __INK__;
}
.photo-cell img {
  position: absolute; top: -6%; left: -6%;
  width: 112%; height: 112%;
  object-fit: cover;
  filter: brightness(1.04) contrast(1.03) saturate(1.04);
  display: block;
}
.photo-pending {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font: 700 8px/1 'Inter Tight', sans-serif;
  letter-spacing: .22em; text-transform: uppercase;
  color: rgba(255,255,255,.55);
  background: __INK__;
}

.kpi-rail { display: grid; grid-template-rows: repeat(4, 1fr); background: __PANEL__; }
.kpi-row {
  display: flex; align-items: center; padding: 0 18px;
  border-bottom: 1px solid rgba(13,13,12,.07);
}
.kpi-row:last-child { border-bottom: none; }
.kpi-text { display: flex; flex-direction: column; min-width: 0; }
.kpi-numeric {
  display: flex; align-items: baseline; gap: 4px;
  font: 900 34px/.95 'Barlow Condensed', Impact, sans-serif;
  letter-spacing: -.005em; color: __INK__;
  white-space: nowrap;
}
.kpi-numeric.text-only { font-size: 26px; }
.kpi-unit {
  font: 700 8.5px/1 'Inter Tight', sans-serif;
  letter-spacing: .16em; text-transform: uppercase;
  color: rgba(13,13,12,.50);
}
.kpi-label {
  font: 700 6px/1 'Inter Tight', sans-serif;
  letter-spacing: .22em; text-transform: uppercase;
  color: rgba(13,13,12,.78);
  margin-top: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ── SECTION TITLE pattern ── */
.sec {
  position: absolute; left: 22px; right: 22px;
}
.sec-title {
  position: relative;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 0 3px 8px;
  border-bottom: 1px solid rgba(13,13,12,.14);
}
.sec-title::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 2px;
  width: 2.5px; background: __ACCENT__;
}
.sec-title-text {
  font: 800 7px/1 'Inter Tight', sans-serif;
  letter-spacing: .24em; text-transform: uppercase;
  color: __INK__;
}
.sec-title-right {
  display: flex; align-items: center; gap: 5px;
  font: 700 5px/1 'Inter Tight', sans-serif;
  letter-spacing: .28em; text-transform: uppercase;
  color: rgba(13,13,12,.55);
}

/* ── CORE SPECS ── (top 313, two columns × three rows, normal density) */
.core { top: 313px; }
.core-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  column-gap: 20px;
  margin-top: 4px;
}
.spec-row {
  display: flex; align-items: baseline;
  padding: 5px 0;
  border-bottom: 1px solid rgba(13,13,12,.10);
  white-space: nowrap;
}
.spec-row.dense { padding: 3.5px 0; }
.spec-lbl {
  font: 600 7.5px/1.1 'Inter Tight', sans-serif;
  color: rgba(13,13,12,.60);
  flex-shrink: 0;
  width: 90px;
}
.core .spec-lbl { width: 86px; }
.spec-val {
  font: 900 12.5px/.95 'Barlow Condensed', Impact, sans-serif;
  letter-spacing: -.005em; color: __INK__;
}
.spec-unit {
  font: 700 6px/1 'Inter Tight', sans-serif;
  letter-spacing: .16em; text-transform: uppercase;
  color: rgba(13,13,12,.50);
  margin-left: 3px;
}

/* ── FEATURES ── (top 427) */
.features { top: 427px; }
.feat-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  column-gap: 24px; row-gap: 5px;
  margin-top: 7px;
}
.feat-item {
  display: flex; align-items: center; gap: 6px;
  font: 600 8px/1 'Inter Tight', sans-serif;
  color: __INK__;
  white-space: nowrap;
}
.feat-check {
  width: 9px; height: 9px; border-radius: 1.5px;
  background: __VERIFIED__;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font: 900 6px/1 'Inter Tight', sans-serif;
  flex-shrink: 0;
}

.chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 6px;
  background: __CHIP_BG__;
  border: 1px solid rgba(13,13,12,.10);
  border-radius: 1px;
  font: 600 6.5px/1 'Inter Tight', sans-serif;
  color: __INK__;
  white-space: nowrap;
}
.chip-dot { width: 3.5px; height: 3.5px; background: __ACCENT__; flex-shrink: 0; }

/* ── BOTTOM GRID ── (top 524, height ~95, dense rows) */
.bottom-grid {
  position: absolute; left: 22px; right: 22px; top: 524px; bottom: 60px;
  display: grid; grid-template-columns: 1fr 1fr; column-gap: 16px;
}
.bottom-col { display: flex; flex-direction: column; min-width: 0; }
.bottom-col .spec-row { padding: 3.5px 0; }
.bottom-col .spec-lbl { width: 78px; }

/* ── FOOTER ── (bottom 0, height 56) */
.footer {
  position: absolute; left: 0; right: 0; bottom: 0; height: 56px;
  background: __PANEL__;
  border-top: 1px solid rgba(13,13,12,.14);
  padding: 7px 22px 5px;
  display: grid; grid-template-columns: auto 1fr auto;
  column-gap: 10px; row-gap: 0;
  align-items: center;
}
.footer-logo {
  width: 28px; height: 28px;
  background: __ACCENT__;
  display: flex; align-items: center; justify-content: center;
  font: 900 13px/1 'Barlow Condensed', Impact, sans-serif;
  color: __INK__;
  overflow: hidden;
  flex-shrink: 0;
}
.footer-logo img { width: 100%; height: 100%; object-fit: contain; }
.footer-mid { display: flex; flex-direction: column; min-width: 0; gap: 1px; }
.footer-eyebrow {
  font: 700 5.5px/1 'Inter Tight', sans-serif;
  letter-spacing: .28em; text-transform: uppercase;
  color: rgba(13,13,12,.50);
}
.footer-name {
  font: 900 15px/1 'Barlow Condensed', Impact, sans-serif;
  letter-spacing: .01em; text-transform: uppercase;
  color: __INK__;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.footer-sub {
  font: 600 6px/1.2 'Inter Tight', sans-serif;
  color: rgba(13,13,12,.60);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.footer-right { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.oem-row { display: flex; align-items: center; gap: 4px; }
.oem-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: __VERIFIED__; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font: 900 6.5px/1 'Inter Tight', sans-serif;
}
.oem-text { font: 700 7.5px/1 'Inter Tight', sans-serif; color: __VERIFIED__; }
.oem-sub  { font: 500 6px/1 'Inter Tight', sans-serif; color: rgba(13,13,12,.55); }

.disclaimer {
  position: absolute; left: 0; right: 0; bottom: 4px;
  text-align: center;
  font: 500 5px/1.3 'Inter Tight', sans-serif;
  color: rgba(13,13,12,.45);
  white-space: nowrap;
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


def _initials(name: str | None) -> str:
    if not name:
        return ""
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _spec_row(label: str, value: Any, unit: str = "") -> str:
    if value is None or value == "":
        return ""
    unit_html = f'<span class="spec-unit">{_esc(unit)}</span>' if unit else ""
    return (
        f'<div class="spec-row">'
        f'<span class="spec-lbl">{_esc(label)}</span>'
        f'<span class="spec-val">{_esc(value)}{unit_html}</span>'
        f'</div>'
    )


_ATTACHMENT_HINTS = (
    "bucket", "fork", "grapple", "auger", "broom", "rake",
    "breaker", "hammer", "trencher", "blade", "sweeper", "mulcher",
)


def _split_attachments(features: list[str]) -> tuple[list[str], list[str]]:
    """Split features into (regular, attachments) — attachments shown as chips."""
    regular: list[str] = []
    chips: list[str] = []
    for f in features or []:
        low = (f or "").lower()
        if any(h in low for h in _ATTACHMENT_HINTS):
            chips.append(f)
        else:
            regular.append(f)
    return regular, chips[:2]


# ─────────────────────────────────────────────────────────────────────────────
# Main renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_spec_sheet(data: dict) -> str:
    machine      = data.get("machine")  or {}
    listing      = data.get("listing")  or {}
    specs        = data.get("specs")    or {}
    features     = data.get("features") or []
    dealer       = data.get("dealer")   or {}
    oem_verified = data.get("oem_verified", True)

    theme = (dealer.get("theme") or "yellow").lower().strip()
    if theme not in _VALID_THEMES:
        theme = "yellow"
    accent = _THEME_ACCENTS[theme]

    css = (
        _CSS_TEMPLATE
        .replace("__ACCENT__", accent)
        .replace("__INK__", _INK)
        .replace("__PAPER__", _PAPER)
        .replace("__PANEL__", _PANEL)
        .replace("__CHIP_BG__", _CHIP_BG)
        .replace("__VERIFIED__", _VERIFIED)
    )

    # ── Header ──
    year  = machine.get("year")
    make  = (machine.get("make") or "").strip()
    model = (machine.get("model") or "").strip()
    eyebrow_parts = [str(year) if year else "", make.upper()]
    eyebrow = " · ".join(p for p in eyebrow_parts if p)

    price_str = _fmt_price(listing.get("price_usd"))
    hours_str = _fmt_hours(listing.get("hours"))

    price_html = f'<div class="hdr-price">{_esc(price_str)}</div>' if price_str else ""
    hours_html = (
        f'<div class="hdr-hours-row">'
        f'<span class="hdr-hours-val">{_esc(hours_str)}</span>'
        f'<span class="hdr-hours-lbl">HRS</span>'
        f'</div>'
    ) if hours_str else ""
    divider_html = '<div class="hdr-divider"></div>' if (price_html and hours_html) else ""

    # ── Photo ──
    photo_uri = _photo_data_uri(machine.get("photo_path"))
    if photo_uri:
        photo_cell = f'<div class="photo-cell"><img src="{photo_uri}" alt="machine"></div>'
    else:
        photo_cell = '<div class="photo-cell"><div class="photo-pending">Photo Pending</div></div>'

    # ── KPI rail (4 tiles) ──
    hero_tiles = (specs.get("hero") or [])[:4]
    kpi_rows_html = ""
    for t in hero_tiles:
        val   = str(t.get("value", "—"))
        unit  = t.get("unit") or ""
        label = t.get("label") or ""
        text_only = not unit and not any(c.isdigit() for c in val)
        cls = "kpi-numeric text-only" if text_only else "kpi-numeric"
        unit_html = f'<span class="kpi-unit">{_esc(unit)}</span>' if unit else ""
        kpi_rows_html += (
            f'<div class="kpi-row"><div class="kpi-text">'
            f'<div class="{cls}"><span>{_esc(val)}</span>{unit_html}</div>'
            f'<div class="kpi-label">{_esc(label)}</div>'
            f'</div></div>'
        )
    # Pad to 4 rows so dividers stay even when data is sparse.
    for _ in range(4 - len(hero_tiles)):
        kpi_rows_html += '<div class="kpi-row"></div>'

    # ── Core specs (up to 6 rows in a 2-col grid) ──
    core_rows = specs.get("core") or specs.get("additional") or []
    core_html = ""
    for r in core_rows[:6]:
        core_html += _spec_row(r.get("label", ""), r.get("value"), r.get("unit", ""))
    core_section = (
        '<div class="sec core">'
        '<div class="sec-title"><span class="sec-title-text">Core Specs &mdash; OEM Verified</span></div>'
        f'<div class="core-grid">{core_html}</div>'
        '</div>'
    ) if core_html else ""

    # ── Features (up to 8) + attachment chips ──
    regular_feats, chips = _split_attachments(features)
    feat_items = ""
    for f in regular_feats[:8]:
        feat_items += (
            f'<div class="feat-item">'
            f'<span class="feat-check">&#10003;</span>'
            f'<span>{_esc(f)}</span>'
            f'</div>'
        )

    chips_html = ""
    if chips:
        chip_inner = "".join(
            f'<span class="chip"><span class="chip-dot"></span>{_esc(c)}</span>'
            for c in chips
        )
        chips_html = (
            f'<div class="sec-title-right">'
            f'<span>Includes</span>{chip_inner}'
            f'</div>'
        )

    feat_section = (
        '<div class="sec features">'
        '<div class="sec-title">'
        '<span class="sec-title-text">Features &amp; Options</span>'
        f'{chips_html}'
        '</div>'
        f'<div class="feat-grid">{feat_items}</div>'
        '</div>'
    ) if feat_items else ""

    # ── Condition rows ──
    cond_rows: list[tuple[str, Any]] = []
    if hours_str:
        hq = listing.get("hours_qualifier")
        cond_rows.append(("Hours", f"{hours_str} ({hq})" if hq else hours_str))
    track_pct = listing.get("track_pct")
    if track_pct:
        cond_rows.append((listing.get("track_label") or "Track %", track_pct))
    last_svc = listing.get("last_service") or listing.get("last_service_date")
    if last_svc:
        cond_rows.append(("Last Service", last_svc))
    condition = listing.get("condition")
    if condition:
        cond_rows.append(("Condition", condition))

    cond_html = "".join(
        _spec_row(lbl, val) for lbl, val in cond_rows[:4]
    )
    cond_section = (
        '<div class="bottom-col">'
        '<div class="sec-title"><span class="sec-title-text">Condition &amp; Service</span></div>'
        f'<div style="margin-top:4px;">{cond_html}</div>'
        '</div>'
    ) if cond_html else '<div class="bottom-col"></div>'

    # ── Performance rows (up to 4) ──
    perf_rows = specs.get("performance") or []
    perf_html = "".join(
        _spec_row(r.get("label", ""), r.get("value"), r.get("unit", ""))
        for r in perf_rows[:4]
    )
    perf_section = (
        '<div class="bottom-col">'
        '<div class="sec-title"><span class="sec-title-text">Performance Data</span></div>'
        f'<div style="margin-top:4px;">{perf_html}</div>'
        '</div>'
    ) if perf_html else '<div class="bottom-col"></div>'

    bottom_grid = (
        f'<div class="bottom-grid">{cond_section}{perf_section}</div>'
        if (cond_html or perf_html) else ""
    )

    # ── Footer ──
    d_name  = (dealer.get("name") or "").strip()
    d_phone = (dealer.get("phone") or "").strip()
    d_loc   = (dealer.get("location") or "").strip()
    d_logo  = dealer.get("logo_data_uri")

    if d_logo:
        logo_inner = f'<img src="{d_logo}" alt="logo">'
    else:
        logo_inner = _esc(_initials(d_name) or "MTM")

    sub_bits = [b for b in [d_phone, d_loc] if b]
    sub_line = "  ·  ".join(sub_bits)

    if oem_verified:
        oem_html = (
            '<div class="footer-right">'
            '<div class="oem-row">'
            '<span class="oem-dot">&#10003;</span>'
            '<span class="oem-text">OEM Verified Specs</span>'
            '</div>'
            '<div class="oem-sub">Sourced from manufacturer data</div>'
            '</div>'
        )
    else:
        oem_html = (
            '<div class="footer-right">'
            '<div class="oem-sub" style="font-style:italic;color:#999">Specs may be incomplete</div>'
            '</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{_GOOGLE_FONTS}" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="sheet theme-{theme}">

  <div class="top-rule"></div>

  <div class="hdr">
    <div class="hdr-left">
      <div class="hdr-eyebrow">{_esc(eyebrow)}</div>
      <div class="hdr-model">{_esc(model)}</div>
      <div class="hdr-accent"></div>
    </div>
    <div class="hdr-right">
      {price_html}
      {divider_html}
      {hours_html}
    </div>
  </div>

  <div class="photo-band">
    {photo_cell}
    <div class="kpi-rail">{kpi_rows_html}</div>
  </div>

  {core_section}
  {feat_section}
  {bottom_grid}

  <div class="footer">
    <div class="footer-logo">{logo_inner}</div>
    <div class="footer-mid">
      <div class="footer-eyebrow">Presented by</div>
      <div class="footer-name">{_esc(d_name) or 'MTM Dealer'}</div>
      <div class="footer-sub">{_esc(sub_line)}</div>
    </div>
    {oem_html}
  </div>

  <div class="disclaimer">
    Specifications sourced from OEM publications and may vary with options or configuration. Contact dealer to confirm availability and pricing.
  </div>

</div>
</body>
</html>"""
