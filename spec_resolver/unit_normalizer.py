"""
unit_normalizer.py
Unit conversion and normalization utilities.

All spec values are stored and returned in a single canonical unit per field.
This module handles conversions from alternate units found in registry data
or seller claims.

Canonical units:
  Weight:    lbs (pounds)
  Power:     hp (net horsepower)
  Flow:      gpm (US gallons per minute)
  Speed:     mph
  Depth:     "X ft Y in" string (for human display)
  Capacity:  yd³ (cubic yards)
  Pressure:  psi
"""

from __future__ import annotations
import re
from typing import Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Weight conversions
# ---------------------------------------------------------------------------

def kg_to_lb(kg: float) -> float:
    """Convert kilograms to pounds."""
    return round(kg * 2.20462, 1)

def tonne_to_lb(t: float) -> float:
    """Convert metric tonnes to pounds."""
    return round(t * 2204.62, 1)

def lb_to_kg(lb: float) -> float:
    return round(lb / 2.20462, 1)


# ---------------------------------------------------------------------------
# Power conversions
# ---------------------------------------------------------------------------

def kw_to_hp(kw: float) -> float:
    """Convert kilowatts to horsepower (mechanical)."""
    return round(kw * 1.34102, 1)

def hp_to_kw(hp: float) -> float:
    return round(hp / 1.34102, 1)


# ---------------------------------------------------------------------------
# Flow conversions
# ---------------------------------------------------------------------------

def lpm_to_gpm(lpm: float) -> float:
    """Convert litres per minute to US gallons per minute."""
    return round(lpm * 0.264172, 1)

def gpm_to_lpm(gpm: float) -> float:
    return round(gpm / 0.264172, 1)


# ---------------------------------------------------------------------------
# Speed conversions
# ---------------------------------------------------------------------------

def kph_to_mph(kph: float) -> float:
    return round(kph * 0.621371, 1)

def mph_to_kph(mph: float) -> float:
    return round(mph / 0.621371, 1)


# ---------------------------------------------------------------------------
# Capacity conversions
# ---------------------------------------------------------------------------

def m3_to_yd3(m3: float) -> float:
    """Convert cubic metres to cubic yards."""
    return round(m3 * 1.30795, 2)

def yd3_to_m3(yd3: float) -> float:
    return round(yd3 / 1.30795, 2)


# ---------------------------------------------------------------------------
# Dig depth: parse various string formats → canonical "X ft Y in"
# ---------------------------------------------------------------------------

def normalize_dig_depth(raw: Union[str, float, int]) -> Optional[str]:
    """
    Normalize dig depth to canonical "X ft Y in" string.

    Accepts:
      - "10 ft 0 in"     → "10 ft 0 in"
      - "10'0\""         → "10 ft 0 in"
      - "3.06 m"         → "10 ft 0 in"
      - 3.06             → interpreted as metres → "10 ft 0 in"
      - 120              → interpreted as inches → "10 ft 0 in"

    Returns None if value cannot be parsed.
    """
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        # Heuristic: values ≤ 30 are metres, larger are inches
        if raw <= 30:
            return _metres_to_ft_in(float(raw))
        else:
            return _inches_to_ft_in(float(raw))

    text = str(raw).strip()

    # "X ft Y in" already
    m = re.match(r"(\d+)\s*ft\s*(\d+)\s*in", text, re.I)
    if m:
        return f"{int(m.group(1))} ft {int(m.group(2))} in"

    # "X'Y\""
    m = re.match(r"(\d+)'\s*(\d+)\"?", text)
    if m:
        return f"{int(m.group(1))} ft {int(m.group(2))} in"

    # Metres: "3.06 m" or "3.06m"
    m = re.match(r"([\d.]+)\s*m$", text, re.I)
    if m:
        return _metres_to_ft_in(float(m.group(1)))

    # Plain number — apply heuristic
    m = re.match(r"^([\d.]+)$", text)
    if m:
        v = float(m.group(1))
        if v <= 30:
            return _metres_to_ft_in(v)
        return _inches_to_ft_in(v)

    return None  # cannot parse


def decimal_ft_to_ft_in(ft: float) -> str:
    """
    Convert decimal feet (e.g. 7.18) to canonical "X ft Y in" string.

    Used for v2 mini-ex registry fields stored as decimal feet (max_dig_depth_ft,
    max_dump_height_ft, max_reach_ft).  Do NOT use normalize_dig_depth() for
    these values — its heuristic treats any value ≤ 30 as metres.

    Examples:
      7.18  → "7 ft 2 in"
      10.0  → "10 ft 0 in"
      8.5   → "8 ft 6 in"
    """
    feet = int(ft)
    inches = round((ft - feet) * 12)
    if inches == 12:
        feet += 1
        inches = 0
    return f"{feet} ft {inches} in"


def _metres_to_ft_in(m: float) -> str:
    total_inches = m * 39.3701
    feet = int(total_inches // 12)
    inches = round(total_inches % 12)
    if inches == 12:
        feet += 1
        inches = 0
    return f"{feet} ft {inches} in"


def _inches_to_ft_in(total_in: float) -> str:
    feet = int(total_in // 12)
    inches = round(total_in % 12)
    if inches == 12:
        feet += 1
        inches = 0
    return f"{feet} ft {inches} in"


# ---------------------------------------------------------------------------
# Numeric range string utilities
# ---------------------------------------------------------------------------

def format_range(low: float, high: float, unit: str = "") -> str:
    """Format a numeric range as a display string: "3,400–3,700" or "23–30 gpm"."""
    def fmt(v: float) -> str:
        if v == int(v):
            return f"{int(v):,}"
        return f"{v:,.1f}"
    s = f"{fmt(low)}–{fmt(high)}"
    if unit:
        s += f" {unit}"
    return s


def parse_range_string(s: str) -> Optional[Tuple[float, float]]:
    """
    Parse a range string like "3,400–3,700" → (3400.0, 3700.0).
    Returns None if parsing fails.
    """
    # Normalize various dash characters to ASCII hyphen
    s = s.replace("–", "-").replace("—", "-").replace(",", "")
    m = re.match(r"([\d.]+)\s*[-–—]\s*([\d.]+)", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None
