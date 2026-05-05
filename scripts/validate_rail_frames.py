"""
validate_rail_frames.py
=======================
Renders 5 rail validation frames (1080x1920) and prints a per-frame report.
All frames saved to static/assets/previews/_rail_test/validate/
Run from project root: python scripts/validate_rail_frames.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont
from walkaround_generator import (
    _apply_lower_rail, _load_font_condensed, _load_font_mono,
    _fit_text, score_dealer_logo,
    TARGET_W, TARGET_H, RAIL_H, RAIL_ACCENT_H,
    LOGO_MAX_H, LOGO_MAX_W, LOGO_LEFT_PAD, LOGO_TEXT_GAP,
    TEXT_ZONE_MIN_W, RAIL_RIGHT_PAD, RAIL_NAME_SIZE, RAIL_PHONE_SIZE,
)

OUT_DIR = "static/assets/previews/_rail_test/validate"
os.makedirs(OUT_DIR, exist_ok=True)

ACCENT = (255, 204, 0)  # MTM yellow

LOGO_LONG     = "static/assets/lockup-dark-transparent.png"   # 2247×152 very wide
LOGO_NORMAL   = "static/assets/previews/_rail_test/_test_logo.png"  # 600×160

CASES = [
    {
        "id":    "01_long_horizontal_logo",
        "label": "Long horizontal logo (MTM lockup 2247×152)",
        "dealer_name":  "Machine To Market",
        "dealer_phone": "(800) 555-0100",
        "logo":  LOGO_LONG,
    },
    {
        "id":    "02_normal_logo",
        "label": "Normal logo (600×160)",
        "dealer_name":  "Travis Boone Equipment",
        "dealer_phone": "(555) 867-5309",
        "logo":  LOGO_NORMAL,
    },
    {
        "id":    "03_no_logo_text_fallback",
        "label": "No logo — text fallback",
        "dealer_name":  "Travis Boone Equipment",
        "dealer_phone": "(555) 867-5309",
        "logo":  None,
    },
    {
        "id":    "04_very_long_dealer_name",
        "label": "Very long dealer name",
        "dealer_name":  "Mountain West Heavy Equipment Solutions LLC",
        "dealer_phone": "(800) 555-0199",
        "logo":  None,
    },
    {
        "id":    "05_long_phone_string",
        "label": "Long phone/contact string",
        "dealer_name":  "Iron Ridge Equipment",
        "dealer_phone": "(555) 867-5309 EXT. 1234 SALES DEPT",
        "logo":  None,
    },
]


def _make_bg() -> Image.Image:
    """Dark gradient background simulating a photo slide."""
    img = Image.new("RGB", (TARGET_W, TARGET_H), (28, 32, 38))
    draw = ImageDraw.Draw(img)
    # Subtle gradient suggestion
    for y in range(0, TARGET_H, 4):
        v = int(28 + (y / TARGET_H) * 12)
        draw.line([(0, y), (TARGET_W, y)], fill=(v, v+4, v+10))
    return img


def _measure_rail(case: dict) -> dict:
    """
    Reproduce the layout math from _apply_lower_rail to capture measurements
    without modifying the production function.
    """
    logo_path = case.get("logo")
    dealer_name = case.get("dealer_name", "")
    dealer_phone = case.get("dealer_phone", "")

    rail_top = TARGET_H - RAIL_H
    usable_h = RAIL_H - RAIL_ACCENT_H

    name_font  = _load_font_condensed(RAIL_NAME_SIZE)
    phone_font = _load_font_mono(RAIL_PHONE_SIZE)

    # Reproduce phone formatting
    raw_phone = (dealer_phone or "").strip()
    if raw_phone and not raw_phone.upper().startswith(("CALL", "TEXT")):
        phone_str = f"CALL/TEXT {raw_phone}"
    else:
        phone_str = raw_phone.upper()
    name_str = (dealer_name or "").strip().upper()

    logo_score = score_dealer_logo(logo_path) if logo_path else 0
    use_logo   = logo_score >= 60 and bool(logo_path and os.path.isfile(logo_path))

    logo_rendered_w = logo_rendered_h = 0
    x_text = RAIL_RIGHT_PAD  # text-only default

    if use_logo:
        try:
            with Image.open(logo_path) as lim:
                lw, lh = lim.size
                fit_h = min(LOGO_MAX_H, usable_h - 16)
                fit_w = max(1, int(lw * fit_h / max(lh, 1)))
                if fit_w > LOGO_MAX_W:
                    fit_w = LOGO_MAX_W
                    fit_h = max(1, int(lh * LOGO_MAX_W / max(lw, 1)))
                candidate_x = LOGO_LEFT_PAD + fit_w + LOGO_TEXT_GAP
                text_zone_w = TARGET_W - RAIL_RIGHT_PAD - candidate_x
                if text_zone_w < TEXT_ZONE_MIN_W:
                    use_logo = False  # fell back
                else:
                    logo_rendered_w, logo_rendered_h = fit_w, fit_h
                    x_text = candidate_x
        except Exception:
            use_logo = False

    text_available_w = TARGET_W - RAIL_RIGHT_PAD - x_text

    # Measure truncation
    tmp_img = Image.new("RGB", (TARGET_W, TARGET_H))
    tdraw   = ImageDraw.Draw(tmp_img)

    phone_clipped = name_clipped = False
    phone_final = phone_str
    name_final  = name_str

    if phone_str:
        pb = tdraw.textbbox((0, 0), phone_str, font=phone_font)
        if pb[2] - pb[0] > text_available_w:
            phone_final   = _fit_text(tdraw, phone_str, phone_font, text_available_w)
            phone_clipped = True

    if name_str:
        nb = tdraw.textbbox((0, 0), name_str, font=name_font)
        if nb[2] - nb[0] > text_available_w:
            name_final   = _fit_text(tdraw, name_str, name_font, text_available_w)
            name_clipped = True

    return {
        "logo_used":        use_logo,
        "logo_score":       logo_score,
        "logo_w":           logo_rendered_w,
        "logo_h":           logo_rendered_h,
        "text_available_w": text_available_w,
        "name_final":       name_final,
        "phone_final":      phone_final,
        "name_clipped":     name_clipped,
        "phone_clipped":    phone_clipped,
    }


def run():
    print(f"\n{'='*62}")
    print("  MTM Walkaround Rail Validation Frames")
    print(f"{'='*62}\n")

    all_pass = True

    for case in CASES:
        cid   = case["id"]
        label = case["label"]

        bg = _make_bg()
        fg_bottom_y = int(TARGET_H * 0.78)  # machine body ends ~78% down

        result = _apply_lower_rail(
            bg,
            case.get("dealer_name"),
            case.get("dealer_phone"),
            ACCENT,
            case.get("logo"),
            fg_bottom_y,
        )

        out_path = os.path.join(OUT_DIR, f"{cid}.png")
        result.save(out_path, "PNG")

        m = _measure_rail(case)

        clipped = m["name_clipped"] or m["phone_clipped"]
        status  = "FAIL [X]" if clipped else "PASS [OK]"
        if clipped:
            all_pass = False

        print(f"  [{status}] {label}")
        print(f"           logo used       : {m['logo_used']} (score={m['logo_score']})")
        if m["logo_used"]:
            print(f"           logo rendered   : {m['logo_w']}×{m['logo_h']} px")
        print(f"           text avail width: {m['text_available_w']} px")
        print(f"           dealer name     : {m['name_final']}"
              + (" [TRUNCATED]" if m["name_clipped"] else ""))
        print(f"           phone           : {m['phone_final']}"
              + (" [TRUNCATED]" if m["phone_clipped"] else ""))
        print(f"           saved           : {out_path}")
        print()

    print(f"{'='*62}")
    print(f"  Overall: {'ALL PASS [OK]' if all_pass else 'FAILURES DETECTED [X]'}")
    print(f"{'='*62}\n")
    return all_pass


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
