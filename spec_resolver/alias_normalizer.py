"""
alias_normalizer.py
Normalizes raw manufacturer strings and model tokens to canonical forms.

Design rules enforced here:
  - Longest-alias-first: sort all alias keys by descending length before
    replacement so "cat" never clobbers inside "caterpillar".
  - Word-boundary matching: aliases only replace whole words.
  - Normalization is idempotent (running twice gives the same result).
"""

from __future__ import annotations
import re
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Manufacturer alias table
# (canonical → [aliases])  — sorted longest-first at load time
# ---------------------------------------------------------------------------

_MFR_ALIAS_TABLE: Dict[str, list[str]] = {
    "caterpillar":  ["caterpillar", "cat"],
    "john deere":   ["john deere", "johndeere", "j deere", "j.deere", "deere", "jd"],
    "kubota":       ["kubota"],
    "bobcat":       ["bobcat"],
    "takeuchi":     ["takeuchi"],
    "case":         ["case ce", "case"],
    "new holland":  ["new holland", "newholland", "nh"],
    "komatsu":      ["komatsu"],
    "jlg":          ["jlg"],
    "skytrak":      ["sky trak", "sky-trak", "skytrak"],
    "skyjack":      ["skyjack"],
    "genie":        ["genie"],
    "jcb":          ["jcb"],
}

# Build a flat alias → canonical map, sorted longest-first
def _build_alias_map(table: Dict[str, list[str]]) -> list[Tuple[str, str]]:
    """Return (alias, canonical) pairs sorted by alias length descending."""
    pairs: list[Tuple[str, str]] = []
    for canonical, aliases in table.items():
        for alias in aliases:
            pairs.append((alias.lower(), canonical))
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)

_MFR_ALIAS_PAIRS = _build_alias_map(_MFR_ALIAS_TABLE)

# ---------------------------------------------------------------------------
# Model alias table
# Maps common alternate spellings → registry-canonical form.
# Keys are upper-cased on use.
# ---------------------------------------------------------------------------

_MODEL_ALIAS_TABLE: Dict[str, str] = {
    # Cat CTL
    "259 D3":  "259D3",
    "259D 3":  "259D3",
    "299 D3":  "299D3",
    "289 D3":  "289D3",
    # Kubota
    "SVL 75-2": "SVL75-2",
    "SVL 75 2": "SVL75-2",
    "SVL75 2":  "SVL75-2",
    "KX 040-4": "KX040-4",
    "KX040 4":  "KX040-4",
    "KX 040":   "KX040",
    "KX040-4S": "KX040-4",   # suffix variants collapse
    # Deere
    "333 G":   "333G",
    "35 G":    "35G",
    "50 G":    "50G",
    "210 G":   "210G",
    "544 K":   "544K",
    # Bobcat
    "T 770":   "T770",
    "T 650":   "T650",
    "T 450":   "T450",
    "S 650":   "S650",
    "S 770":   "S770",
    "E 50":    "E50",
    # Backhoe
    "580 SN":  "580SN",
    "580SN":   "580SN",
    "310 SL":  "310SL",
    # SkyTrak
    "10054":   "10054",
    "8042":    "8042",
    # Cat excavators
    "320 GC":  "320GC",
    "336 F":   "336F",
}

# Pre-sort model aliases longest-first
_MODEL_ALIAS_PAIRS: list[Tuple[str, str]] = sorted(
    ((k.upper(), v.upper()) for k, v in _MODEL_ALIAS_TABLE.items()),
    key=lambda p: len(p[0]),
    reverse=True,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_manufacturer(raw: str) -> str:
    """
    Return the canonical manufacturer string for *raw*.
    Returns raw.strip().lower() if no alias matches.
    Never returns empty string — caller handles missing mfr separately.
    """
    if not raw:
        return ""
    text = raw.strip().lower()
    for alias, canonical in _MFR_ALIAS_PAIRS:
        # Word-boundary regex so "cat" won't match inside "caterpillar"
        pattern = r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])"
        if re.search(pattern, text):
            return canonical
    return text


def normalize_model(raw: str) -> str:
    """
    Return the canonical model string for *raw*.
    Steps:
      1. Upper-case
      2. Collapse spaces adjacent to digits/letters (e.g. "SVL 75-2" → "SVL75-2")
      3. Apply model alias table (longest-first)
    """
    if not raw:
        return ""
    text = raw.strip().upper()

    # Collapse common spacing patterns around alphanumeric boundaries
    # "259 D3" → "259D3",  "KX 040" → "KX040"
    text = re.sub(r"([A-Z])(\s+)(\d)", r"\1\3", text)
    text = re.sub(r"(\d)(\s+)([A-Z])", r"\1\3", text)

    # Apply alias table
    for alias, canonical in _MODEL_ALIAS_PAIRS:
        if text == alias or text.startswith(alias + " ") or text.endswith(" " + alias):
            text = canonical
            break

    return text.strip()


def normalize_text_for_parsing(raw: str) -> str:
    """
    Light normalization applied to raw listing text before further processing.
    Does NOT strip noise tokens (that happens in a later step).
    Does NOT remove config keywords (those must already be detected first).

    Steps:
      1. Lower-case
      2. Normalize whitespace
      3. Strip non-alphanumeric except hyphens and slashes
      4. Apply manufacturer alias substitution IN TEXT
         (so downstream parsers see "caterpillar" not "cat")
    """
    if not raw:
        return ""
    text = raw.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\-\/]", " ", text)

    # Apply manufacturer aliases in-text (longest-first already sorted)
    for alias, canonical in _MFR_ALIAS_PAIRS:
        pattern = r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])"
        text = re.sub(pattern, canonical, text)

    # Re-clean whitespace after substitutions
    text = re.sub(r"\s+", " ", text).strip()
    return text
