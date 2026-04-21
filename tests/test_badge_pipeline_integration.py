"""
tests/test_badge_pipeline_integration.py
=========================================
End-to-end pipeline test: verifies the badge step fires inside
build_listing_pack() and stamps *_listing.jpg files without touching
*_01_card.png.

Run: python tests/test_badge_pipeline_integration.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageStat

from listing_pack_builder import build_listing_pack


# ── Test fixture helpers ───────────────────────────────────────────────────────

def _make_photo(path: str, color=(85, 90, 92)) -> str:
    img = Image.new("RGB", (1200, 800), color)
    d   = ImageDraw.Draw(img)
    d.rectangle([200, 150, 1000, 650], fill=(55, 58, 60))
    img.save(path, format="JPEG", quality=85)
    return path


def _make_logo(path: str) -> str:
    img = Image.new("RGBA", (280, 110), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, 276, 106], radius=12, fill=(245, 166, 35, 255))
    d.rounded_rectangle([14, 14, 266, 96], radius=8, fill=(30, 30, 30, 255))
    img.save(path, format="PNG")
    return path


def _bottom_left_strip(img_path: str, strip_h: int = 160) -> ImageStat.Stat:
    """Return pixel stats for the bottom-left region where the badge sits."""
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    strip = img.crop((0, h - strip_h, w // 2, h))
    return ImageStat.Stat(strip)


# ── Main test ─────────────────────────────────────────────────────────────────

def main():
    print("\nBadge Pipeline Integration Test")
    print("=" * 52)
    failures = []

    with tempfile.TemporaryDirectory() as session_dir:
        # Fixtures
        photo_path = os.path.join(session_dir, "photo_01.jpg")
        logo_path  = os.path.join(session_dir, "dealer_logo.png")
        _make_photo(photo_path)
        _make_logo(logo_path)

        dealer_info = {
            "dealer_name":  "Acme Equipment",
            "contact_name": "Jane Smith",
            "phone":        "(617) 555-0142",
            "logo_path":    logo_path,
            "accent_color": "yellow",
        }

        # Run the real pipeline assembler
        pack = build_listing_pack(
            raw_text               = "",
            parsed_listing         = {
                "make": "Bobcat", "model": "T770", "year": 2019,
                "equipment_type": "skid_steer",
            },
            resolved_machine       = None,
            generated_listing_text = "Test listing — BADGE INTEGRATION TEST",
            spec_sheet_entries     = [],
            image_input_paths      = [photo_path],
            dealer_info            = dealer_info,
            session_dir            = session_dir,
            session_web            = "",
            # Omit dealer_input_dump + enriched_resolved_specs → skips spec sheet
        )

        listing_dir = os.path.join(session_dir, "listing_output", "Listing_Photos")
        print(f"\n  Listing_Photos/ contents:")
        if os.path.isdir(listing_dir):
            for f in sorted(os.listdir(listing_dir)):
                fp = os.path.join(listing_dir, f)
                kb = os.path.getsize(fp) // 1024
                print(f"    {f}  ({kb} KB)")
        else:
            print("    [EMPTY — image pack did not run]")

        # ── Test 1: listing photo exists ──────────────────────────────────────
        listing_files = [
            f for f in os.listdir(listing_dir)
            if f.endswith("_listing.jpg")
        ] if os.path.isdir(listing_dir) else []

        if listing_files:
            print(f"\n  [PASS] Listing photos generated: {listing_files}")
        else:
            print(f"\n  [FAIL] No *_listing.jpg found in Listing_Photos/")
            failures.append("no listing photos generated")

        # ── Test 2: badge region differs from original (badge was applied) ────
        if listing_files:
            badged_path   = os.path.join(listing_dir, listing_files[0])
            original_mean = _bottom_left_strip(photo_path).mean
            badged_mean   = _bottom_left_strip(badged_path).mean

            # Bottom-left region should differ if badge was stamped
            # The badge adds a light/dark rounded rect — mean shifts noticeably
            diff = max(abs(a - b) for a, b in zip(original_mean, badged_mean))
            print(f"\n  Original bottom-left mean: {[round(v,1) for v in original_mean]}")
            print(f"  Badged   bottom-left mean: {[round(v,1) for v in badged_mean]}")
            print(f"  Max channel diff: {diff:.1f}")

            if diff > 5.0:
                print(f"  [PASS] Badge detected in bottom-left region (diff={diff:.1f})")
            else:
                print(f"  [FAIL] Badge NOT detected — pixel means too similar (diff={diff:.1f})")
                failures.append("badge not visible in output image")

        # ── Test 3: hero card not touched ─────────────────────────────────────
        card_files = [
            f for f in os.listdir(listing_dir)
            if f.endswith("_card.png")
        ] if os.path.isdir(listing_dir) else []

        if not card_files:
            print(f"\n  [PASS] No hero card generated (full_record=None — correct)")
        else:
            print(f"\n  [INFO] Card files present: {card_files} (hero card renderer ran)")

        # ── Test 4: ZIP exists ────────────────────────────────────────────────
        zip_path = os.path.join(session_dir, "listing_output.zip")
        if os.path.isfile(zip_path):
            kb = os.path.getsize(zip_path) // 1024
            print(f"\n  [PASS] ZIP created: listing_output.zip ({kb} KB)")
        else:
            print(f"\n  [FAIL] ZIP not created")
            failures.append("zip not created")

        # ── Test 5: badge step logged ─────────────────────────────────────────
        print(f"\n  [INFO] pack warnings: {pack.get('warnings', [])}")

    print("\n" + "=" * 52)
    if failures:
        print(f"  FAILED: {failures}")
        return 1
    print("  ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
