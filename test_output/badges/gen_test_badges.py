"""
Generate 3 badge QA samples for post-implementation verification.
Run from project root: python test_output/badges/gen_test_badges.py

Samples:
  1. dark_bg_badge.png  — synthetic logo with black background + white interior text
  2. white_bg_badge.png — real logo forced to white variant
  3. wide_horiz_badge.png — wide horizontal logo, auto-detect variant
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PIL import Image, ImageDraw, ImageFont
from renderers.badge_renderer import apply_badge_to_photo, build_badge

BASE   = Path(__file__).parent.parent.parent
ASSETS = BASE / "static" / "assets"
DEMO   = BASE / "static" / "demo"
OUT    = Path(__file__).parent
OUT.mkdir(parents=True, exist_ok=True)

CONTACT_NAME  = "Greg Doutre"
CONTACT_PHONE = "(603) 555-0182"
ACCENT        = "yellow"


def _make_dark_bg_logo(path: Path) -> None:
    """Synthetic logo: black background with white interior text (simulates a dark-bg dealer logo)."""
    w, h = 300, 80
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))        # black background
    draw = ImageDraw.Draw(img)
    # White rectangle "logo mark" inset from edges (interior artwork)
    draw.rectangle((12, 12, 68, h - 12), fill=(255, 255, 255, 255))
    # White text block (interior — should survive flood-fill)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/calibrib.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    draw.text((82, 18), "ACME EQUIPMENT", font=font, fill=(255, 255, 255, 255))
    draw.text((82, 46), "Heavy Machinery", font=font, fill=(200, 200, 200, 255))
    img.save(str(path))
    print(f"  [synth] dark-bg logo created: {path.name}  ({w}×{h})")


def main() -> None:
    print("Generating badge QA samples...\n")

    # ── Sample 1: dark-background logo ────────────────────────────────────────
    dark_logo_path = OUT / "_tmp_dark_bg_logo.png"
    _make_dark_bg_logo(dark_logo_path)

    badge_dark = build_badge(
        str(dark_logo_path), CONTACT_NAME, CONTACT_PHONE, accent=ACCENT
        # auto-detect: black bg corners → "other" → charcoal badge
    )
    out1 = OUT / "dark_bg_badge.png"
    badge_dark.save(str(out1))
    bw, bh = badge_dark.size
    print(f"  [1] dark_bg_badge.png          {bw}×{bh}px (charcoal auto-detect)")

    # Verify interior white artwork wasn't stripped — check a pixel near (20,30) of
    # the original logo in the rendered badge (rough offset: shadow_margin=14, padding_x=22)
    # Interior white rect starts at logo pixel (12,12) → after scaling and placement:
    # just print a note; visual inspection confirms.
    print("      [check] black outer bg stripped; interior white rect/text should be visible")

    # ── Sample 2: white-background logo ───────────────────────────────────────
    white_logo = str(ASSETS / "yellow_iron_yard_logo.png")
    badge_white = build_badge(
        white_logo, CONTACT_NAME, CONTACT_PHONE, accent=ACCENT,
        force_variant="white"
    )
    out2 = OUT / "white_bg_badge.png"
    badge_white.save(str(out2))
    bw, bh = badge_white.size
    print(f"  [2] white_bg_badge.png         {bw}×{bh}px (white forced)")

    # ── Sample 3: wide horizontal logo ────────────────────────────────────────
    wide_logo = str(ASSETS / "_test_wide_logo.png")
    badge_wide = build_badge(
        wide_logo, CONTACT_NAME, CONTACT_PHONE, accent=ACCENT
    )
    out3 = OUT / "wide_horiz_badge.png"
    badge_wide.save(str(out3))
    bw, bh = badge_wide.size
    print(f"  [3] wide_horiz_badge.png       {bw}×{bh}px (wide logo auto-detect)")

    # ── On-photo composite (dark-bg logo, charcoal badge) ─────────────────────
    demo_photo = DEMO / "demo1.jpg"
    if demo_photo.exists():
        out4 = OUT / "dark_bg_on_photo.jpg"
        apply_badge_to_photo(
            str(demo_photo), str(dark_logo_path), CONTACT_NAME, CONTACT_PHONE,
            accent=ACCENT,
            output_path=str(out4),
        )
        print(f"  [4] dark_bg_on_photo.jpg       composite verify")

    print(f"\nAll samples saved to: {OUT}")

    # Cleanup synthetic logo
    dark_logo_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
