#!/usr/bin/env python3
"""scripts/refresh_demo_assets.py
===============================
Regenerates all homepage demo preview assets using real machine photos
and the production rendering pipeline.

Run from the project root:
    python scripts/refresh_demo_assets.py

Outputs written to:  static/demo_outputs/
  demo_price_tag_card.png  — 2024 Cat 299D3 XE  (Clean Marketplace Hero Card)
  demo_spec_sheet.png      — 2024 Cat 299D3 XE  (OEM-Backed Spec Sheet)
  demo_image_pack.png      — 2023 SkyTrak 8042  (Branded Image Pack first photo)
  demo_listing_copy.png    — 2024 Cat 299D3 XE  (Buyer-Oriented Listing Copy)
  sample_mtm_package.zip   — 2024 Cat 299D3 XE  (Full listing package)

Legacy aliases removed (no longer referenced in templates):
  demo_01_card.png, demo_02_spec_sheet.png
"""

from __future__ import annotations

import glob
import os
import shutil
import sys

# ── Add project root to sys.path ─────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from dealer_input import DealerInput
from listing_pack_builder import build_listing_pack_v1
from mtm_service import _make_session_dir, _run_spec_resolver, safe_lookup_machine

DEMO_OUTPUTS = os.path.join(_ROOT, "static", "demo_outputs")
os.makedirs(DEMO_OUTPUTS, exist_ok=True)

# ── Demo dealer identity ──────────────────────────────────────────────────────
_LOGO_PNG = os.path.join(_ROOT, "static", "assets", "brand", "icon-square-dark-transparent.png")
_DEMO_DEALER_BASE = {
    "dealer_name":       "Iron Valley Equipment",
    "phone":             "(800) 555-0174",
    "location":          "Columbus, OH",
    "logo_path":         _LOGO_PNG if os.path.isfile(_LOGO_PNG) else None,
    "accent_color":      "yellow",
    "featured_template": "clean_marketplace",
}

# ── Photo folder constants ────────────────────────────────────────────────────
_CAT_PHOTOS_DIR      = r"C:\Users\Greg\OneDrive\Pictures\2024 Caterpillar 299D3"
_SKYTRAK_PHOTOS_DIR  = r"C:\Users\Greg\OneDrive\Pictures\2023 SKYTRAK 8042"
_STATIC_CAT_FALLBACK = os.path.join(_ROOT, "static", "assets", "source_photos", "homepage", "cat_262d3_front_3q.jpg")


def _sorted_photos(folder: str) -> list[str]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    files = []
    if not os.path.isdir(folder):
        print(f"  WARN: folder not found: {folder}")
        return files
    for f in sorted(os.listdir(folder)):
        if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in exts:
            files.append(os.path.join(folder, f))
    return files


def _photo_list(folder: str, fallback: str | None = None, limit: int = 10) -> list[str]:
    """Return up to `limit` photos from folder, falling back to a single static photo."""
    photos = _sorted_photos(folder)[:limit]
    if not photos and fallback and os.path.isfile(fallback):
        print(f"  WARN: no photos in {folder!r} — using static fallback")
        photos = [fallback]
    return photos


def _find_output(listing_dir: str, pattern: str) -> str | None:
    matches = sorted(glob.glob(os.path.join(listing_dir, pattern)))
    return matches[0] if matches else None


def _copy_to_demo(src: str | None, dest_name: str) -> str | None:
    if not src or not os.path.isfile(src):
        print(f"  SKIP  {dest_name}  (source not found: {src})")
        return None
    dest = os.path.join(DEMO_OUTPUTS, dest_name)
    shutil.copy2(src, dest)
    size_kb = os.path.getsize(dest) // 1024
    print(f"  OK    {dest_name}  ({size_kb} KB)")
    return dest


def run_pack(
    year: int,
    make: str,
    model: str,
    hours: int,
    price: int,
    photos: list[str],
    accent_color: str = "yellow",
    featured_template: str = "clean_marketplace",
    extra_input: dict | None = None,
) -> dict:
    """Run one machine through the full production pipeline. Returns the pack result dict."""
    extra = dict(extra_input or {})

    dealer_input = DealerInput(
        year=year,
        make=make,
        model=model,
        hours=hours,
        asking_price=price,
        condition_grade="Well Maintained",
        cab_type=extra.pop("cab_type", "enclosed"),
        ac=extra.pop("ac", True),
        heater=extra.pop("heater", True),
        **extra,
    )

    parsed = {"make": make, "model": model, "make_source": "explicit"}
    specs, confidence = safe_lookup_machine(parsed)
    full_record = specs.get("full_record") if specs else None

    resolved_machine = None
    resolved_specs: dict = {}

    if specs is not None:
        eq_type = (specs.get("equipment_type") or "").lower()
        is_ssl_or_ctl = eq_type in ("skid_steer", "compact_track_loader")
        modifiers: list[str] = []
        if not is_ssl_or_ctl:
            if dealer_input.high_flow == "yes":
                modifiers.append("high_flow")
            if dealer_input.two_speed_travel == "yes":
                modifiers.append("two_speed")

        resolved_machine = _run_spec_resolver(
            "",
            parsed,
            specs,
            confidence,
            parsed_year=year,
            detected_modifiers=modifiers,
        )
        if resolved_machine:
            resolved_specs = resolved_machine.get("resolved_specs") or {}
    else:
        print(f"  WARN: no registry match for {make} {model}")

    session_dir, session_web = _make_session_dir(parsed)
    dealer_info = dict(_DEMO_DEALER_BASE)
    dealer_info["accent_color"] = accent_color
    dealer_info["featured_template"] = featured_template

    print(f"  Photos: {[os.path.basename(p) for p in photos]}")

    pack = build_listing_pack_v1(
        dealer_input=dealer_input,
        resolved_specs=resolved_specs,
        resolved_machine=resolved_machine,
        image_input_paths=photos,
        dealer_info=dealer_info,
        session_dir=session_dir,
        session_web=session_web,
        full_record=full_record,
    )

    pack["_session_dir"] = session_dir
    pack["_listing_text"] = pack.get("listing_text") or ""
    return pack


def render_listing_copy_png(listing_text: str, output_path: str) -> bool:
    """Render listing copy as a styled 1080x1350 PNG using Playwright."""
    import html as _html

    lines = listing_text.strip().splitlines()
    headline = lines[0] if lines else ""
    body_lines = lines[1:] if len(lines) > 1 else []
    body_html = "<br>".join(_html.escape(ln) for ln in body_lines)

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800;900&family=Inter+Tight:wght@500;600&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #f6f4ef; -webkit-font-smoothing: antialiased; }}
  .card {{
    width: 1080px; min-height: 1350px;
    background: #f6f4ef;
    display: flex; flex-direction: column;
    padding: 72px 80px 64px;
  }}
  .kicker {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; letter-spacing: .18em; text-transform: uppercase;
    color: #999990; margin-bottom: 28px;
  }}
  .headline {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900; font-size: 52px; line-height: 1.0;
    color: #0d0d0c; margin-bottom: 32px;
    text-transform: uppercase; letter-spacing: .01em;
  }}
  .accent-rule {{
    width: 48px; height: 4px; background: #FFC600;
    margin-bottom: 32px;
  }}
  .body {{
    font-family: 'Inter Tight', sans-serif;
    font-size: 22px; line-height: 1.65;
    color: #3a3a35; flex: 1;
    white-space: pre-wrap;
  }}
  .footer {{
    margin-top: 48px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
    color: #bbb8af;
    border-top: 1px solid #e0ddd4; padding-top: 20px;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="kicker">Buyer-Oriented Listing Copy &middot; MTM v3 Engine</div>
  <div class="headline">{_html.escape(headline)}</div>
  <div class="accent-rule"></div>
  <div class="body">{body_html}</div>
  <div class="footer">Generated by Machine-to-Market &middot; OEM-Registry-Verified &middot; Posting-Ready</div>
</div>
</body>
</html>"""

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1080, "height": 1350})
            page.set_content(page_html, wait_until="networkidle")
            page.screenshot(path=output_path, full_page=True)
            browser.close()
        size_kb = os.path.getsize(output_path) // 1024
        print(f"  OK    demo_listing_copy.png  ({size_kb} KB)")
        return True
    except Exception as exc:
        print(f"  ERROR listing copy PNG: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 1. Hero Card + Spec Sheet + Listing Copy — 2024 Cat 299D3 XE
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/3] Hero Card + Spec Sheet — 2024 Caterpillar 299D3 XE  (clean_marketplace)")
cat_photos = _photo_list(_CAT_PHOTOS_DIR, fallback=_STATIC_CAT_FALLBACK)
cat_pack = run_pack(
    year=2024, make="Caterpillar", model="299D3 XE",
    hours=320, price=119500,
    photos=cat_photos,
    accent_color="yellow",
    featured_template="clean_marketplace",
    extra_input={
        "high_flow":        "yes",
        "two_speed_travel": "yes",
        "ride_control":     True,
        "backup_camera":    True,
        "air_ride_seat":    True,
        "track_condition":  "95% remaining",
    },
)

_cat_listing_photos = os.path.join(cat_pack["_session_dir"], "listing_output", "Listing_Photos")

# Hero card
_card = _find_output(_cat_listing_photos, "*_01_card.png")
_copy_to_demo(_card, "demo_price_tag_card.png")

# Spec sheet
_spec_sheet = _find_output(_cat_listing_photos, "*_02_spec_sheet.png")
_copy_to_demo(_spec_sheet, "demo_spec_sheet.png")

# Listing copy PNG (generated from real listing text)
print("\n[2/3] Listing Copy PNG — 2024 Caterpillar 299D3 XE")
_listing_txt_path = os.path.join(cat_pack["_session_dir"], "listing_output", "listing_description.txt")
_listing_text = ""
if os.path.isfile(_listing_txt_path):
    with open(_listing_txt_path, encoding="utf-8") as _f:
        _listing_text = _f.read()
elif cat_pack.get("outputs", {}).get("listing_txt"):
    _lt = cat_pack["outputs"]["listing_txt"]
    if os.path.isfile(_lt):
        with open(_lt, encoding="utf-8") as _f:
            _listing_text = _f.read()

_copy_out = os.path.join(DEMO_OUTPUTS, "demo_listing_copy.png")
if _listing_text:
    render_listing_copy_png(_listing_text, _copy_out)
else:
    print("  SKIP  demo_listing_copy.png  (no listing text found)")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Branded Image Pack — 2023 SkyTrak 8042
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/3] Branded Image Pack — 2023 SkyTrak 8042")
skytrak_photos = _photo_list(_SKYTRAK_PHOTOS_DIR)
if skytrak_photos:
    skytrak_pack = run_pack(
        year=2023, make="SkyTrak", model="8042",
        hours=780, price=89000,
        photos=skytrak_photos,
        accent_color="yellow",
        featured_template="clean_marketplace",
        extra_input={"has_stabilizers": True},
    )
    _st_listing_photos = os.path.join(skytrak_pack["_session_dir"], "listing_output", "Listing_Photos")
    _img_pack_photo = (
        _find_output(_st_listing_photos, "*_03_listing.jpg")
        or _find_output(_st_listing_photos, "*_03_listing.jpeg")
        or _find_output(_st_listing_photos, "*_listing.jpg")
        or _find_output(_st_listing_photos, "*_listing.jpeg")
    )
    if not _img_pack_photo:
        _img_pack_photo = _find_output(_st_listing_photos, "*_01_card.png")
    _copy_to_demo(_img_pack_photo, "demo_image_pack.png")
else:
    # Fall back to the Cat card as the image pack preview
    print("  WARN: no SkyTrak photos — using Cat card as image pack preview")
    if _card and os.path.isfile(_card):
        _copy_to_demo(_card, "demo_image_pack.png")
    else:
        print("  SKIP  demo_image_pack.png")


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup — remove legacy aliases no longer referenced in any template
# ─────────────────────────────────────────────────────────────────────────────
for _alias in ("demo_01_card.png", "demo_02_spec_sheet.png"):
    _alias_path = os.path.join(DEMO_OUTPUTS, _alias)
    if os.path.isfile(_alias_path):
        os.remove(_alias_path)
        print(f"  DEL   {_alias}  (unreferenced legacy alias)")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- static/demo_outputs/ ---------------------------------------------------")
for f in sorted(os.listdir(DEMO_OUTPUTS)):
    fp = os.path.join(DEMO_OUTPUTS, f)
    if os.path.isfile(fp):
        size_kb = os.path.getsize(fp) // 1024
        print(f"  {f:<50}  {size_kb:>7} KB")
print()
