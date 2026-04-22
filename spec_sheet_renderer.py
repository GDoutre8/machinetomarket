"""
MTM Spec Sheet Renderer — v1

Renders 4:5 Facebook-format spec sheet images (1080×1350 px output).
Image #2 in the listing pack — lighter and more document-like than the hero card.

Consumes a structured data dict:
  machine  : year / make / model / category / photo_path
  listing  : price_usd / hours
  specs    : core / secondary row lists
  features : list of feature label strings
  condition: grade / ownership / notes
  dealer   : name / phone / location / logo_data_uri / theme

Returns self-contained HTML string ready for Playwright Chromium PNG export.
"""

from __future__ import annotations

import base64
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


# ─────────────────────────────────────────────────────────────────────────────
# Photo embedding
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


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

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
        return f"{int(val):,} HRS"
    except (TypeError, ValueError):
        return str(val)


def _esc(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


# ─────────────────────────────────────────────────────────────────────────────
# HTML builder
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #fff; display: flex; justify-content: center; align-items: flex-start; }

.theme-yellow { --accent: #FFC20E; --accent-text: #0D0D0D; --accent-muted: rgba(13,13,13,0.42); }
.theme-red    { --accent: #C8102E; --accent-text: #fff;    --accent-muted: rgba(255,255,255,0.55); }
.theme-blue   { --accent: #1E4D8C; --accent-text: #fff;    --accent-muted: rgba(255,255,255,0.55); }
.theme-green  { --accent: #2C5F3E; --accent-text: #fff;    --accent-muted: rgba(255,255,255,0.55); }
.theme-orange { --accent: #D85A15; --accent-text: #fff;    --accent-muted: rgba(255,255,255,0.55); }

.sheet {
  width: 540px;
  height: 675px;
  font-family: 'Inter', sans-serif;
  -webkit-font-smoothing: antialiased;
  background: #F8F7F5;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Header ── */
.hdr {
  background: var(--accent);
  padding: 14px 20px 12px;
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  flex-shrink: 0;
  min-height: 116px;
}
.hdr-left {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.hdr-year-make {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--accent-muted);
}
.hdr-model {
  font-family: 'Oswald', sans-serif;
  font-size: 48px;
  font-weight: 700;
  line-height: 0.92;
  color: var(--accent-text);
  letter-spacing: -0.5px;
}
.hdr-category {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent-muted);
}
.hdr-right {
  text-align: right;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  flex-shrink: 0;
}
.hdr-price-val {
  font-family: 'Oswald', sans-serif;
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  color: var(--accent-text);
  letter-spacing: -0.5px;
}
.hdr-price-lbl {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--accent-muted);
  margin-top: 1px;
}
.hdr-hours-val {
  font-family: 'Oswald', sans-serif;
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
  color: var(--accent-text);
  letter-spacing: -0.5px;
}
.hdr-hours-unit {
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin-left: 2px;
}
.hdr-hours-lbl {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--accent-muted);
  margin-top: 1px;
}

/* ── Photo ── */
.photo {
  height: 190px;
  flex-shrink: 0;
  overflow: hidden;
  background: #E0DED9;
}
.photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  display: block;
}
.photo-pending {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Oswald', sans-serif;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: #B8B5AE;
  text-transform: uppercase;
}

/* ── Body: 2-column grid ── */
.body {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
  padding: 11px 18px 0;
  overflow: hidden;
  min-height: 0;
}
.col { display: flex; flex-direction: column; gap: 9px; overflow: hidden; }

/* ── Section title ── */
.sec-title {
  font-size: 7.5px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #1A1A1A;
  padding-bottom: 4px;
  border-bottom: 2px solid var(--accent);
  margin-bottom: 3px;
  flex-shrink: 0;
}

/* ── Dotted spec rows (Core Specs + Specifications) ── */
.spec-rows { display: flex; flex-direction: column; }
.spec-row { display: flex; align-items: baseline; padding: 3px 0; }
.spec-lbl {
  font-size: 9px;
  font-weight: 500;
  color: #555;
  white-space: nowrap;
  flex-shrink: 0;
}
.spec-fill {
  flex: 1;
  border-bottom: 1px dotted #C0BDB7;
  margin: 0 5px 3px;
  min-width: 6px;
}
.spec-val {
  font-size: 10px;
  font-weight: 700;
  color: #1A1A1A;
  white-space: nowrap;
  flex-shrink: 0;
}
.spec-unit {
  font-size: 7.5px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-left: 2px;
}
.spec-null { color: #C8C6C1; font-weight: 400; }

/* ── Features (bullets) ── */
.feat-list { display: flex; flex-direction: column; gap: 0; }
.feat-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 9.5px;
  font-weight: 500;
  color: #222;
  padding: 2.5px 0;
}
.feat-bullet {
  font-size: 13px;
  line-height: 0.85;
  color: #1A1A1A;
  flex-shrink: 0;
}

/* ── Condition & Service (inline key: value) ── */
.cond-list { display: flex; flex-direction: column; gap: 3px; }
.cond-item { font-size: 9px; color: #333; line-height: 1.4; }
.cond-key { font-weight: 700; color: #1A1A1A; }

/* ── Footer ── */
.footer {
  border-top: 1px solid #D5D3CE;
  padding: 8px 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  background: #fff;
}
.logo-box {
  width: 54px;
  height: 42px;
  border: 1.5px solid #C8C6C1;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
  background: #fff;
}
.logo-box img { max-width: 48px; max-height: 36px; object-fit: contain; display: block; }
.logo-placeholder {
  font-size: 7px;
  font-weight: 700;
  color: #C8C6C1;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  text-align: center;
  line-height: 1.4;
}
.dealer-info { flex: 1; min-width: 0; }
.dealer-name { font-size: 11px; font-weight: 700; color: #1A1A1A; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dealer-sub { font-size: 8.5px; color: #7A7875; margin-top: 2px; line-height: 1.5; }
.footer-divider { width: 1px; height: 36px; background: #D5D3CE; flex-shrink: 0; }
.oem-badge { display: flex; align-items: center; gap: 5px; flex-shrink: 0; }
.oem-text { font-size: 9.5px; font-weight: 700; color: #2C8A48; letter-spacing: 0.03em; white-space: nowrap; }
"""

_GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Oswald:wght@400;500;600;700"
    "&family=Inter:wght@400;500;600;700;800;900"
    "&display=swap"
)

_OEM_CHECK_SVG = (
    '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M2.5 6.5L5 9L9.5 3.5" stroke="#2C8A48" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def render_spec_sheet(data: dict) -> str:
    machine   = data.get("machine")   or {}
    listing   = data.get("listing")   or {}
    specs     = data.get("specs")     or {}
    features  = data.get("features")  or []
    condition = data.get("condition") or {}
    dealer    = data.get("dealer")    or {}

    # ── Theme ──
    theme = (dealer.get("theme") or "yellow").lower().strip()
    if theme not in _VALID_THEMES:
        theme = "yellow"
    theme_cls = f"theme-{theme}"

    # ── Header ──
    year  = machine.get("year")
    make  = (machine.get("make") or "").upper()
    model = machine.get("model") or ""
    cat_raw = machine.get("category") or ""
    cat   = _EQ_TYPE_DISPLAY.get(cat_raw, cat_raw)

    year_make = f"{year} \u00b7 {make}" if year and make else str(year or make or "")

    price_block = ""
    p = _fmt_price(listing.get("price_usd"))
    if p:
        price_block = (
            f'<div>'
            f'<div class="hdr-price-val">{_esc(p)}</div>'
            f'<div class="hdr-price-lbl">Asking Price</div>'
            f'</div>'
        )

    hours_block = ""
    raw_hrs = listing.get("hours")
    if raw_hrs is not None:
        try:
            hrs_fmt = f"{int(raw_hrs):,}"
        except (TypeError, ValueError):
            hrs_fmt = str(raw_hrs)
        hours_block = (
            f'<div>'
            f'<div class="hdr-hours-val">{_esc(hrs_fmt)}<span class="hdr-hours-unit">HRS</span></div>'
            f'<div class="hdr-hours-lbl">Hours</div>'
            f'</div>'
        )

    # ── Photo ──
    photo_uri = _photo_data_uri(machine.get("photo_path"))
    if photo_uri:
        photo_content = f'<img src="{photo_uri}" alt="machine photo">'
    else:
        photo_content = '<div class="photo-pending">Photo Pending</div>'

    # ── Core spec rows (dotted leaders) ──
    def _spec_row(label: str, value: Any, unit: str = "") -> str:
        if value is None or value == "":
            val_html = '<span class="spec-val spec-null">—</span>'
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

    core_rows_html = ""
    for row in (specs.get("core") or []):
        core_rows_html += _spec_row(
            row.get("label", ""), row.get("value"), row.get("unit", "")
        )

    # ── Features (bullet list) ──
    feat_html = ""
    for feat in (features or [])[:8]:
        feat_html += (
            f'<div class="feat-item">'
            f'<span class="feat-bullet">&bull;</span>'
            f'{_esc(feat)}'
            f'</div>'
        )
    if not feat_html:
        feat_html = '<div class="feat-item" style="color:#bbb">—</div>'

    # ── Condition & Service (inline key: value) ──
    cond_html = ""
    for lbl, key in [("Condition", "grade"), ("Ownership", "ownership")]:
        val = condition.get(key)
        if val:
            cond_html += (
                f'<div class="cond-item">'
                f'<span class="cond-key">{_esc(lbl)}:</span> {_esc(val)}'
                f'</div>'
            )
    notes = condition.get("notes")
    if notes:
        short = notes[:90] + ("\u2026" if len(notes) > 90 else "")
        cond_html += (
            f'<div class="cond-item">'
            f'<span class="cond-key">Notes:</span> {_esc(short)}'
            f'</div>'
        )
    if not cond_html:
        cond_html = '<div class="cond-item" style="color:#bbb">—</div>'

    # ── Secondary / Specifications rows ──
    sec_rows_html = ""
    for row in (specs.get("secondary") or [])[:6]:
        sec_rows_html += _spec_row(
            row.get("label", ""), row.get("value"), row.get("unit", "")
        )

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
    sub_html = "<br>".join(_esc(x) for x in sub_parts)

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
<div class="sheet {theme_cls}">

  <div class="hdr">
    <div class="hdr-left">
      <div class="hdr-year-make">{_esc(year_make)}</div>
      <div class="hdr-model">{_esc(model)}</div>
      {'<div class="hdr-category">' + _esc(cat) + '</div>' if cat else ''}
    </div>
    <div class="hdr-right">
      {price_block}
      {hours_block}
    </div>
  </div>

  <div class="photo">{photo_content}</div>

  <div class="body">
    <div class="col">
      <div>
        <div class="sec-title">Core Specs &mdash; Verified Against OEM</div>
        <div class="spec-rows">{core_rows_html}</div>
      </div>
      <div>
        <div class="sec-title">Condition &amp; Service</div>
        <div class="cond-list">{cond_html}</div>
      </div>
    </div>
    <div class="col">
      <div>
        <div class="sec-title">Key Features</div>
        <div class="feat-list">{feat_html}</div>
      </div>
      {'<div><div class="sec-title">Specifications</div><div class="spec-rows">' + sec_rows_html + '</div></div>' if sec_rows_html else ''}
    </div>
  </div>

  <div class="footer">
    <div class="logo-box">{logo_inner}</div>
    <div class="dealer-info">
      {'<div class="dealer-name">' + _esc(d_name) + '</div>' if d_name else ''}
      {'<div class="dealer-sub">' + sub_html + '</div>' if sub_html else ''}
    </div>
    {'<div class="footer-divider"></div>' if (d_name or sub_html) else ''}
    <div class="oem-badge">
      {_OEM_CHECK_SVG}
      <span class="oem-text">OEM Verified Specs</span>
    </div>
  </div>

</div>
</body>
</html>"""
