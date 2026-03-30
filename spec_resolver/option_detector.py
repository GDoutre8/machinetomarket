"""
option_detector.py
Detects configuration modifier keywords from raw listing text.

CRITICAL: This module must run BEFORE noise token stripping.
"high flow" must be captured before "high" is removed as noise.

Detected modifiers are returned as a frozenset of canonical option keys.
Each option key maps to a downstream effect in field_resolvers.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Tuple


# ---------------------------------------------------------------------------
# Option definitions
# Each entry: (canonical_key, [regex_patterns])
# Patterns are tried as whole-word / phrase matches.
# ---------------------------------------------------------------------------

_OPTION_PATTERNS: List[Tuple[str, List[str]]] = [
    # Hydraulics
    ("high_flow",       [r"high[\s\-]?flow", r"\bhi[\s\-]?flow\b", r"\bhiflow\b",
                         r"\bhf\b", r"\bxhp\b"]),
    # Cab / operator station
    ("has_cab",         [r"\bcab\b", r"\berops\b", r"\benclosed\b",
                         r"enclosed\s+cab", r"cab\s+heat", r"cab\s+ac",
                         r"cab\s+a/c", r"cab\s+hvac", r"hvac"]),
    ("has_canopy",      [r"\borops\b", r"\bcanopy\b", r"open\s+cab",
                         r"open\s+station", r"rops\s+canopy"]),
    # Ground pressure / undercarriage
    ("lgp",             [r"\blgp\b", r"low[\s\-]?ground[\s\-]?pressure"]),
    # Cat-specific CTL variants
    ("xe_variant",      [r"\bxe\b"]),
    ("land_management", [r"land[\s\-]?mgmt", r"land[\s\-]?management"]),
    # Excavator tail swing
    ("compact_radius",  [r"\bcr\b(?=\s|$)", r"compact[\s\-]?radius",
                         r"zero[\s\-]?tail[\s\-]?swing", r"zero\s+tail"]),
    # Dozer blade types
    ("pat_blade",       [r"\bpat\b", r"power[\s\-]?angle[\s\-]?tilt",
                         r"6[\s\-]?way\s+blade", r"6\s*way"]),
    ("s_blade",         [r"\bs[\s\-]?blade\b", r"straight\s+blade"]),
    ("u_blade",         [r"\bu[\s\-]?blade\b", r"universal\s+blade",
                         r"semi[\s\-]?u[\s\-]?blade"]),
    # Travel / powertrain
    ("two_speed",       [r"2[\s\-]?speed", r"two[\s\-]?speed", r"\b2spd\b"]),
    ("single_speed",    [r"1[\s\-]?speed", r"one[\s\-]?speed", r"single[\s\-]?speed"]),
    # Wheel loader coupler
    ("fusion_coupler",  [r"fusion\s+coupler", r"fusion\s+q/?c"]),
    ("std_coupler",     [r"pin[\s\-]?on", r"pin\s+coupler"]),
    # Telehandler
    ("with_outriggers", [r"\boutriggers?\b", r"\bstabilizers?\b"]),
    # Backhoe
    ("extendahoe",      [r"extend[\s\-]?a[\s\-]?hoe", r"extendahoe",
                         r"x[\s\-]?hoe", r"ext\s+hoe"]),
    ("four_wheel_drive", [r"\b4wd\b", r"\b4x4\b", r"four[\s\-]?wheel[\s\-]?drive",
                          r"mfwd", r"4\s*wheel\s*drive"]),
    # Emissions tier (affects year / spec confidence)
    ("tier4_final",     [r"tier\s*4\s*final", r"\bt4f\b", r"t4\s*final"]),
    ("pre_emissions",   [r"pre[\s\-]?emissions?", r"pre[\s\-]?def",
                         r"no\s+def", r"no\s+dpf"]),
]


@dataclass(frozen=True)
class DetectedOptions:
    """Immutable set of detected option keys plus raw snippet evidence."""
    keys: FrozenSet[str]
    # Maps option_key → list of raw text snippets that triggered it
    evidence: Dict[str, List[str]]

    def has(self, key: str) -> bool:
        return key in self.keys

    def to_list(self) -> List[str]:
        return sorted(self.keys)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_options(text: str) -> DetectedOptions:
    """
    Detect all configuration modifier keywords present in *text*.

    Must be called on ORIGINAL (pre-noise-strip) text.
    Returns a DetectedOptions with all matched option keys.
    """
    if not text:
        return DetectedOptions(keys=frozenset(), evidence={})

    lowered = text.lower()
    matched_keys: set[str] = set()
    evidence: Dict[str, List[str]] = {}

    for option_key, patterns in _OPTION_PATTERNS:
        for pattern in patterns:
            for m in re.finditer(pattern, lowered):
                matched_keys.add(option_key)
                evidence.setdefault(option_key, [])
                snippet = text[max(0, m.start()-10):m.end()+10].strip()
                if snippet not in evidence[option_key]:
                    evidence[option_key].append(snippet)

    # Mutual exclusivity: if both cab and canopy detected, prefer explicit cab
    # (listing might say "cab with canopy")
    if "has_cab" in matched_keys and "has_canopy" in matched_keys:
        matched_keys.discard("has_canopy")
        evidence.pop("has_canopy", None)

    return DetectedOptions(keys=frozenset(matched_keys), evidence=evidence)


def extract_numeric_claims(text: str) -> Dict[str, float]:
    """
    Extract numeric claims from listing text that a seller may assert.
    Returns a dict of {claim_type: value}.

    These are NEVER used to override locked registry specs.
    They surface in per_field_metadata as seller claims and may
    trigger conflict warnings.
    """
    claims: Dict[str, float] = {}
    lowered = text.lower()

    # HP / horsepower
    for m in re.finditer(r"(\d[\d,]*\.?\d*)\s*(?:hp|horse\s*power)", lowered):
        val = float(m.group(1).replace(",", ""))
        if 10 <= val <= 2000:   # sanity bounds
            claims["seller_hp"] = val

    # Operating weight
    for m in re.finditer(
        r"(?:operating\s+weight|op\s*wt|weight)[:\s]+(\d[\d,]*)\s*(?:lbs?|pounds?)?",
        lowered
    ):
        val = float(m.group(1).replace(",", ""))
        if 1000 <= val <= 300_000:
            claims["seller_op_weight_lb"] = val

    # Hours (not a spec but used for context)
    for m in re.finditer(r"(\d[\d,]*)\s*(?:hrs?|hours?)", lowered):
        val = float(m.group(1).replace(",", ""))
        if 1 <= val <= 50_000:
            claims["seller_hours"] = val
            break   # take first occurrence

    # ROC / rated operating capacity
    for m in re.finditer(
        r"(?:roc|rated\s+cap|operating\s+cap)[:\s]+(\d[\d,]*)\s*(?:lbs?|pounds?)?",
        lowered
    ):
        val = float(m.group(1).replace(",", ""))
        if 500 <= val <= 20_000:
            claims["seller_roc_lb"] = val

    return claims
