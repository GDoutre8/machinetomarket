"""
Build the 5-card final comparison grid.
Renders each card to its own clean HTML file, then builds an iframe grid.
No CSS scoping — each card is isolated in its own iframe.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from card_renderer import render_card

OUT = Path(__file__).parent

SHARED = {
    "machine": {
        "year": 2019, "make": "Bobcat", "model": "E35",
        "photo_path": str(ROOT / "scripts" / "_sample_machine.jpg"),
        "equipment_type": "mini_excavator",
        "net_hp": 24.8,
        "operating_weight_lb": 8157,
        "max_dig_depth_str": "10' 2\"",
    },
    "dealer": {
        "name": "Iron Country Equipment",
        "phone": "(208) 555-0142",
        "theme": "yellow",
        "show_branding": True,
        "short_mark": "IC",
    },
    "listing": {"price_usd": 47500, "hours": 1842},
}

CARDS = [
    ("price_tag",         "Price Tag",          "Existing — spec rail + notched tag",        False),
    ("auction_ticket",    "Auction Ticket",      "Existing — white OEM/spec-style card",      False),
    ("tight_ad",          "Tight Ad",            "New — photo dominant, top-left price stack", True),
    ("clean_marketplace", "Clean Marketplace",   "New — restrained inventory, bulk-safe",      True),
    ("corner_tag",        "Corner Tag",          "New — full-bleed photo, accent corner price",True),
]

# Render each card to a standalone HTML file
for tpl, label, desc, is_new in CARDS:
    data = {**SHARED, "featured_template": tpl}
    html = render_card(data)
    fname = f"final_{tpl}.html"
    (OUT / fname).write_text(html, encoding="utf-8")
    print(f"  {fname}")

# Card display dimensions
SCALE = 0.285
DW = round(1080 * SCALE)   # 308
DH = round(1350 * SCALE)   # 385

# Build the grid HTML using iframes (relative src — works on local filesystem)
cols_html = ""
for tpl, label, desc, is_new in CARDS:
    badge = (
        '<span class="badge new">New</span>'
        if is_new else
        '<span class="badge existing">Existing</span>'
    )
    cols_html += f"""
  <div class="col">
    <div class="meta">
      <div class="lbl">{label}</div>
      <div class="dsc">{desc}</div>
      {badge}
    </div>
    <div class="frame">
      <iframe src="final_{tpl}.html" scrolling="no" frameborder="0"
              width="1080" height="1350"
              style="transform:scale({SCALE});transform-origin:top left;display:block;pointer-events:none;border:none;">
      </iframe>
    </div>
  </div>"""

grid_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MTM — Final Template Comparison</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: #0f0f0e;
    font-family: -apple-system, system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    padding: 40px;
  }}
  h1 {{ color: #fff; font-size: 13px; font-weight: 600;
        letter-spacing: .20em; text-transform: uppercase; margin-bottom: 4px; }}
  .sub {{ color: rgba(255,255,255,.32); font-size: 11px;
          letter-spacing: .10em; text-transform: uppercase; margin-bottom: 36px; }}
  .grid {{ display: flex; gap: 24px; align-items: flex-start; flex-wrap: nowrap; }}
  .col  {{ display: flex; flex-direction: column; gap: 10px; flex: 0 0 {DW}px; }}
  .meta {{ display: flex; flex-direction: column; gap: 3px; }}
  .lbl  {{ font-size: 13px; font-weight: 600; color: #fff; }}
  .dsc  {{ font-size: 11px; color: rgba(255,255,255,.38); line-height: 1.4; }}
  .badge {{
    display: inline-block; font-size: 10px; font-weight: 700;
    letter-spacing: .12em; text-transform: uppercase;
    padding: 3px 8px; border-radius: 2px; margin-top: 3px; width: fit-content;
  }}
  .badge.new      {{ background: #FFC600; color: #0d0d0c; }}
  .badge.existing {{ background: rgba(255,255,255,.07); color: rgba(255,255,255,.42);
                     border: 1px solid rgba(255,255,255,.12); }}
  .frame {{
    width: {DW}px; height: {DH}px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.09);
    flex: 0 0 auto;
  }}
</style>
</head>
<body>
<h1>MTM — Final Template Comparison</h1>
<p class="sub">2019 Bobcat E35 &nbsp;·&nbsp; $47,500 &nbsp;·&nbsp; 1,842 hrs &nbsp;·&nbsp; Iron Country Equipment &nbsp;·&nbsp; Yellow theme</p>
<div class="grid">
{cols_html}
</div>
</body>
</html>
"""

out = OUT / "final_comparison.html"
out.write_text(grid_html, encoding="utf-8")
print(f"\nGrid: {out} ({len(grid_html)//1024}KB)")
print("Open final_comparison.html in Chrome or Edge.")
