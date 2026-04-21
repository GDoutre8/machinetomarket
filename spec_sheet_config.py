"""spec_sheet_config.py
=======================
Configuration constants and utility helpers for the MTM spec sheet.
Imported by spec_sheet_context.py — no circular dependencies.
"""
from __future__ import annotations

import base64
from pathlib import Path

# ── Condition sublabels ───────────────────────────────────────────────────────

CONDITION_CONTEXT: dict[str, str] = {
    "Excellent": "No visible damage",
    "Good":      "Minor cosmetic wear",
    "Fair":      "Works as-is",
}

# ── Supported photo extensions ────────────────────────────────────────────────

_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ── Unit formatters ───────────────────────────────────────────────────────────

def format_feet_inches(feet_decimal: float | None) -> str | None:
    """Convert decimal feet to ft' in\" display (e.g. 9.97 → \"9' 11\\\"\").

    Accepts feet as a decimal float.  Returns None for None input.
    """
    if feet_decimal is None:
        return None
    feet = int(feet_decimal)
    inches = round((feet_decimal - feet) * 12)
    if inches == 12:
        feet += 1
        inches = 0
    if inches == 0:
        return f"{feet}'"
    return f"{feet}' {inches}\""


# ── Photo helpers ─────────────────────────────────────────────────────────────

def photo_data_uri(photo_path: str | None) -> str | None:
    """Embed a photo as a base64 data URI so the HTML is fully self-contained."""
    if not photo_path:
        return None
    path = Path(photo_path)
    if not path.is_file():
        return None
    ext = path.suffix.lower().lstrip(".")
    mime = {
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "png":  "image/png",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def find_first_photo(directory: str) -> str | None:
    """Return path to the first supported image in directory, sorted by name."""
    d = Path(directory)
    if not d.is_dir():
        return None
    candidates: list[Path] = []
    for ext in _PHOTO_EXTS:
        candidates.extend(d.glob(f"*{ext}"))
        candidates.extend(d.glob(f"*{ext.upper()}"))
    if not candidates:
        return None
    return str(sorted(candidates)[0])
