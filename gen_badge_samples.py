"""
gen_badge_samples.py
====================
Regenerates badge QA samples in badge_samples/ using real dealer logos.

Logo routing:
  yellow_iron_yard_logo.png  white bg -> WHITE badge variant
  _test_wide_logo.png        dark bg  -> CHARCOAL badge variant

Run from project root:
  python gen_badge_samples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from renderers.badge_renderer import apply_badge_to_photo, build_badge

BASE   = Path(__file__).parent
ASSETS = BASE / "static" / "assets"
DEMO   = BASE / "static" / "demo"
OUT    = BASE / "badge_samples"

OUT.mkdir(exist_ok=True)

# yellow_iron_yard_logo.png has a transparent background (not opaque white), so:
#   force_variant="white"  -> white badge (QA the white variant with a real logo)
#   auto-detect (no force) -> charcoal badge (transparent bg -> "other")
LOGO_WHITE_BG = str(ASSETS / "yellow_iron_yard_logo.png")
LOGO_DARK_BG  = str(ASSETS / "yellow_iron_yard_logo.png")
PHOTO         = str(DEMO / "demo1.jpg")

CONTACT_NAME  = "Greg Doutre"
CONTACT_PHONE = "(603) 555-0182"
ACCENT        = "yellow"


def main() -> None:
    print("Generating badge samples...")

    # Standalone badge renders.
    # yellow_iron_yard_logo.png has a transparent bg (not opaque white), so auto-detection
    # returns "charcoal". force_variant="white" is used here to QA the white variant
    # with a real logo; production auto-detect is unchanged.
    badge_white    = build_badge(LOGO_WHITE_BG, CONTACT_NAME, CONTACT_PHONE, accent=ACCENT,
                                 force_variant="white")
    badge_charcoal = build_badge(LOGO_DARK_BG,  CONTACT_NAME, CONTACT_PHONE, accent=ACCENT)

    badge_white.save(str(OUT / "badge_white.png"))
    print("  [OK] badge_white.png")

    badge_charcoal.save(str(OUT / "badge_charcoal.png"))
    print("  [OK] badge_charcoal.png")

    # On-photo composites
    apply_badge_to_photo(
        PHOTO, LOGO_WHITE_BG, CONTACT_NAME, CONTACT_PHONE,
        accent=ACCENT,
        force_variant="white",
        output_path=str(OUT / "badge_white_on_photo.png"),
    )
    print("  [OK] badge_white_on_photo.png")

    apply_badge_to_photo(
        PHOTO, LOGO_DARK_BG, CONTACT_NAME, CONTACT_PHONE,
        accent=ACCENT,
        output_path=str(OUT / "badge_charcoal_on_photo.png"),
    )
    print("  [OK] badge_charcoal_on_photo.png")

    print(f"\nAll samples saved to: {OUT}")


if __name__ == "__main__":
    main()
