"""
tests/test_zip_contents.py
==========================
Regression: ZIP must include card, spec sheet, listing photos, and listing text.
_load_listing_photos (UI-only) must NOT be the source for ZIP assembly.

Run: python tests/test_zip_contents.py
"""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from listing_pack_builder import _zip_folder


def test_zip_includes_all_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pack_dir = os.path.join(tmp, "listing_output")
        lp_dir = os.path.join(pack_dir, "Listing_Photos")
        os.makedirs(lp_dir)

        stub_files = {
            os.path.join(lp_dir, "Machine_01_card.png"):        b"\x89PNG\r\n",
            os.path.join(lp_dir, "Machine_02_spec_sheet.png"):  b"\x89PNG\r\n",
            os.path.join(lp_dir, "Machine_03_listing.jpg"):     b"\xff\xd8\xff",
            os.path.join(pack_dir, "listing_description.txt"):  b"Test listing.",
        }
        for path, content in stub_files.items():
            with open(path, "wb") as f:
                f.write(content)

        zip_path = os.path.join(tmp, "listing_output.zip")
        _zip_folder(pack_dir, zip_path)

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())

        expected = {
            "listing_output/Listing_Photos/Machine_01_card.png",
            "listing_output/Listing_Photos/Machine_02_spec_sheet.png",
            "listing_output/Listing_Photos/Machine_03_listing.jpg",
            "listing_output/listing_description.txt",
        }
        missing = expected - names
        assert not missing, f"ZIP missing expected files: {sorted(missing)}"
        print("PASS: ZIP contains all expected artifacts")
        for name in sorted(names):
            print(f"  {name}")


if __name__ == "__main__":
    test_zip_includes_all_artifacts()
