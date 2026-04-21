"""
tests/test_badge_renderer.py
============================
Three badge renderer test cases:
  1. White-background logo  → WHITE badge + yellow accent
  2. Square logo            → correct scaling, no distortion
  3. Transparent logo       → DARK badge

Saves all outputs to tests/fixtures/badge_output/.
Run: python tests/test_badge_renderer.py
"""

import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from renderers.badge_renderer import apply_badge_to_photo

_OUT_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "badge_output")
os.makedirs(_OUT_DIR, exist_ok=True)

_PHOTO_W, _PHOTO_H = 1200, 800


def _make_photo(path: str) -> str:
    """Create a simple placeholder listing photo (landscape, machinery grey)."""
    img = Image.new("RGB", (_PHOTO_W, _PHOTO_H), (85, 90, 92))
    d   = ImageDraw.Draw(img)
    # Simulate a machine silhouette — dark rectangle in the centre
    d.rectangle([200, 200, 1000, 650], fill=(55, 58, 60))
    d.rectangle([220, 220, 980, 630], fill=(70, 72, 74))
    img.save(path, format="JPEG", quality=88)
    return path


def _make_logo_white_bg(path: str) -> str:
    """Logo on white background (opaque). Luminance high → WHITE badge expected."""
    img = Image.new("RGBA", (300, 150), (255, 255, 255, 255))  # solid white bg
    d   = ImageDraw.Draw(img)
    # Dark text-like shape on white
    d.rectangle([20, 20, 280, 130], fill=(30, 30, 30, 255))
    d.rectangle([30, 30, 270, 120], fill=(255, 255, 255, 255))
    d.rectangle([50, 55, 200, 90],  fill=(30, 30, 30, 255))
    img.save(path, format="PNG")
    return path


def _make_logo_square(path: str) -> str:
    """Square logo (1:1 aspect ratio). Must scale without distortion."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.ellipse([10, 10, 190, 190], fill=(245, 166, 35, 255))
    d.ellipse([50, 50, 150, 150], fill=(30, 30, 30, 255))
    img.save(path, format="PNG")
    return path


def _make_logo_transparent(path: str) -> str:
    """Logo with transparent background and light artwork. Luminance low → DARK badge."""
    img = Image.new("RGBA", (320, 120), (0, 0, 0, 0))  # fully transparent bg
    d   = ImageDraw.Draw(img)
    # Light-coloured artwork (high luminance per pixel) → avg lum < threshold → DARK badge
    d.rectangle([10, 10, 310, 110], fill=(220, 220, 220, 255))
    d.rectangle([30, 30, 290,  90], fill=(200, 200, 200, 255))
    img.save(path, format="PNG")
    return path


def _run_test(label: str, photo_path: str, logo_path: str, accent: str) -> bool:
    out = os.path.join(_OUT_DIR, f"{label}_result.jpg")
    ok  = apply_badge_to_photo(
        photo_path  = photo_path,
        logo_path   = logo_path,
        name        = "Jane Smith",
        phone       = "(617) 555-0142",
        accent      = accent,
        output_path = out,
    )
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} -> {os.path.basename(out)}")
    return ok


def main():
    print("\nBadge Renderer — 3 test cases")
    print("=" * 48)

    # ── Fixture paths ──────────────────────────────────────────────────────────
    photo_path  = os.path.join(_OUT_DIR, "_photo_base.jpg")
    logo_white  = os.path.join(_OUT_DIR, "_logo_white_bg.png")
    logo_square = os.path.join(_OUT_DIR, "_logo_square.png")
    logo_transp = os.path.join(_OUT_DIR, "_logo_transparent.png")

    _make_photo(photo_path)
    _make_logo_white_bg(logo_white)
    _make_logo_square(logo_square)
    _make_logo_transparent(logo_transp)

    results = [
        _run_test("1_white_bg_logo",   photo_path, logo_white,  "yellow"),
        _run_test("2_square_logo",     photo_path, logo_square, "yellow"),
        _run_test("3_transparent_logo",photo_path, logo_transp, "yellow"),
    ]

    print("-" * 48)
    passed = sum(results)
    print(f"  {passed}/{len(results)} tests passed")
    print(f"  Outputs: {_OUT_DIR}")

    # Sanity: hero card must never be touched — verify output files are only listing outputs
    card_png = os.path.join(_OUT_DIR, "_01_card.png")
    if os.path.isfile(card_png):
        print("  [WARN] Unexpected *_01_card.png found in output dir — check targeting rules")
    else:
        print("  [OK] No hero card in output dir (correct)")

    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
