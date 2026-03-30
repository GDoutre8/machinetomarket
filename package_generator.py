"""
package_generator.py
====================
Bundles MTM output assets into a single downloadable ZIP file.

Entry point:
    generate_listing_package(
        cleaned_listing,
        spec_sheet_path,
        spec_sheet_variants,
        output_path,
    ) -> str | None
"""

from __future__ import annotations

import os
import zipfile


def generate_listing_package(
    cleaned_listing:     str,
    spec_sheet_path:     str | None,
    spec_sheet_variants: dict[str, str] | None,
    output_path:         str | None = None,
) -> str | None:
    """
    Bundle MTM listing assets into a ZIP file.

    Parameters
    ----------
    cleaned_listing     : formatted listing text (always included as listing.txt)
    spec_sheet_path     : path to spec_sheet.png  (included if present)
    spec_sheet_variants : dict of { key: path } for sized variants (included if present)
    output_path         : destination path for the ZIP;
                          defaults to <spec_sheet dir>/listing_package.zip,
                          or <module dir>/outputs/listing_package.zip if no sheet

    Returns
    -------
    Absolute path to the written ZIP, or None if generation fails.

    ZIP contents
    ------------
    listing.txt
    spec_sheet.png              (if spec_sheet_path is set and file exists)
    spec_sheet_4x5.png          (if present in variants)
    spec_sheet_square.png       (if present in variants)
    spec_sheet_story.png        (if present in variants)
    spec_sheet_landscape.png    (if present in variants)
    """
    # ── Resolve output path ────────────────────────────────────────────────
    if output_path is None:
        if spec_sheet_path:
            out_dir = os.path.dirname(os.path.abspath(spec_sheet_path))
        else:
            here    = os.path.dirname(os.path.abspath(__file__))
            out_dir = os.path.join(here, "outputs")
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, "listing_package.zip")

    try:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:

            # listing.txt — always included
            zf.writestr("listing.txt", cleaned_listing)

            # spec_sheet.png — base image
            if spec_sheet_path and os.path.isfile(spec_sheet_path):
                zf.write(spec_sheet_path, arcname="spec_sheet.png")

            # Sized variants — use the canonical filename as the ZIP entry name
            for _key, file_path in (spec_sheet_variants or {}).items():
                if file_path and os.path.isfile(file_path):
                    zf.write(file_path, arcname=os.path.basename(file_path))

        return os.path.abspath(output_path)

    except Exception as exc:
        print(f"[MTM] listing_package generation failed: {exc}")
        return None


# ── Quick smoke-test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    _listing = (
        "2019 Bobcat T770\n"
        "1,800 hours on machine\n\n"
        "Machine Snapshot\n"
        "• Engine: 92 hp\n"
        "• Rated operating capacity: 3,475 lbs\n"
        "• Aux hydraulic flow: 37 gpm high\n\n"
        "#bobcat #t770 #heavyequipment\n"
    )

    # Point at whatever already exists in outputs/
    _here     = os.path.dirname(os.path.abspath(__file__))
    _out_dir  = os.path.join(_here, "outputs")
    _sheet    = os.path.join(_out_dir, "spec_sheet.png")
    _variants = {
        "4x5":       os.path.join(_out_dir, "spec_sheet_4x5.png"),
        "square":    os.path.join(_out_dir, "spec_sheet_square.png"),
        "story":     os.path.join(_out_dir, "spec_sheet_story.png"),
        "landscape": os.path.join(_out_dir, "spec_sheet_landscape.png"),
    }

    result = generate_listing_package(
        cleaned_listing     = _listing,
        spec_sheet_path     = _sheet     if os.path.isfile(_sheet)     else None,
        spec_sheet_variants = {k: v for k, v in _variants.items() if os.path.isfile(v)},
    )
    print(f"Package written: {result}")
    if result:
        with zipfile.ZipFile(result) as zf:
            print("ZIP contents:")
            for name in zf.namelist():
                info = zf.getinfo(name)
                print(f"  {name:<35} {info.file_size:>8} bytes")
