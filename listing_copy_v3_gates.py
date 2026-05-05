"""
listing_copy_v3_gates.py
========================
Claim gates and proof checks for MTM Listing Copy Engine v3.

Implements proof-burden rules from:
  docs/low_hours_benchmarks_v1.yaml
  docs/listing_phrase_effectiveness_audit.md (Part 4 — Engine Guardrails)
  docs/high_inquiry_phrase_rankings_v1.md   (Tier-1/2/3 phrase classification)

Public API:
  low_hours_eligible(equipment_type, year, hours, hours_qualifier=None,
                     condition_notes="", strict=True) -> bool
  build_trust_lines(dealer_input, equipment_type, tier) -> list[str]
  strip_unsupported_low_hours(text, eligible: bool) -> str
"""

from __future__ import annotations

import datetime
import os
import re
from functools import lru_cache
from typing import Any, Optional


_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


# ─────────────────────────────────────────────────────────────────────────────
# Low-hours benchmark loader
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_benchmarks() -> dict:
    path = os.path.join(_DOCS_DIR, "low_hours_benchmarks_v1.yaml")
    try:
        import yaml  # type: ignore
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


_EQ_BENCH_MAP = {
    "compact_track_loader": "compact_track_loader",
    "ctl": "compact_track_loader",
    "skid_steer": "skid_steer",
    "skid_steer_loader": "skid_steer",
    "ssl": "skid_steer",
    "mini_excavator": "mini_excavator",
    "mini_ex": "mini_excavator",
    "telehandler": "telehandler",
    "excavator": "excavator",
    "wheel_loader": "wheel_loader",
    "dozer": "dozer",
}


_HOURS_QUAL_BAD = frozenset({
    "estimated", "unknown", "unverified", "broken", "replaced", "tampered",
    "guess", "approximate",
})


_HARSH_USE_KEYWORDS = (
    "demolition", "demo", "quarry", "forestry", "mulch", "land clearing",
    "rental fleet", "snow", "salt", "rock", "waste", "scrap",
)


def _age_bucket(years_old: int) -> str:
    if years_old <= 2:
        return "age_0_2_years"
    if years_old <= 5:
        return "age_3_5_years"
    if years_old <= 10:
        return "age_6_10_years"
    return "age_10_plus"


def low_hours_eligible(
    equipment_type: str,
    year: Optional[int],
    hours: Optional[int],
    hours_qualifier: Optional[str] = None,
    condition_notes: str = "",
    strict: bool = True,
) -> bool:
    """
    Gate for the phrase 'low hours' / 'low-hour'.

    Returns True only when the meter reading and age both clear the
    conservative threshold for the equipment type.  Returns False when:
      - hours or year missing
      - hours qualifier indicates unverified/estimated/broken meter
      - hours exceed conservative threshold for the age bucket
      - harsh-use signal present and strict=True (apply one stricter bucket)
    """
    if hours is None or year is None or hours <= 0:
        return False

    if hours_qualifier and hours_qualifier.strip().lower() in _HOURS_QUAL_BAD:
        return False

    benches = _load_benchmarks()
    key = _EQ_BENCH_MAP.get((equipment_type or "").strip().lower())
    if not key or key not in benches:
        return False

    current_year = datetime.date.today().year
    years_old = max(0, current_year - int(year))
    bucket = _age_bucket(years_old)

    notes_lc = (condition_notes or "").lower()
    if strict and any(kw in notes_lc for kw in _HARSH_USE_KEYWORDS):
        # Apply one stricter bucket
        order = ["age_0_2_years", "age_3_5_years", "age_6_10_years", "age_10_plus"]
        idx = order.index(bucket)
        bucket = order[max(0, idx - 1)] if idx > 0 else bucket

    cfg = benches[key].get(bucket) or {}
    threshold = cfg.get("conservative_threshold_hours")
    if not threshold:
        return False

    return int(hours) <= int(threshold)


# ─────────────────────────────────────────────────────────────────────────────
# Trust-line builder (proof-gated phrases)
# ─────────────────────────────────────────────────────────────────────────────

def build_trust_lines(
    dealer_input: Any,
    equipment_type: str,
    tier: str,
    low_hours_ok: bool = False,
) -> list[str]:
    """
    Return up to 3 short, proof-backed trust-builder sentences.

    Every sentence is gated by an actual DealerInput field — never invented.
    Trust phrases pulled from high_inquiry_phrase_rankings_v1.md (Tier 2).

    Suppressed for Tier C (issue-forward copy takes precedence).
    """
    lines: list[str] = []
    if tier == "C":
        return lines

    di = dealer_input

    # Verified hours — only when hours present
    hours = getattr(di, "hours", None)
    qualifier = (getattr(di, "hours_qualifier", "") or "").strip().lower()
    if hours and qualifier in ("verified", "actual", "metered", ""):
        if low_hours_ok:
            lines.append(f"Hours stated at {hours:,} — within MTM's low-hour band for this class and age.")
        # Otherwise we just state factual hours via the lead — no trust claim

    # One owner — only when flagged
    if getattr(di, "one_owner", False):
        lines.append("Single-owner machine — one consistent maintenance trail since new.")

    # Attachments included — only when explicit non-empty list
    att = (getattr(di, "attachments_included", "") or "").strip()
    if att:
        lines.append("Attachments listed below are confirmed included with the machine.")

    # Track / undercarriage / tire condition — only with explicit free text or pct
    tc = (getattr(di, "track_condition", "") or "").strip()
    if tc:
        lines.append(f"Tracks reported {tc} — visible wear-cost signal before inspection.")
    uc = (getattr(di, "undercarriage_condition_pct", "") or
          getattr(di, "undercarriage_percent_remaining", None))
    if uc and not tc:
        suffix = "%" if isinstance(uc, int) else ""
        lines.append(f"Undercarriage reported at {uc}{suffix} remaining.")
    tire = (getattr(di, "tire_condition", "") or "").strip()
    if tire and equipment_type in ("skid_steer_loader", "wheel_loader", "telehandler", "backhoe_loader"):
        lines.append(f"Tires reported {tire}.")

    # Warranty
    warr = (getattr(di, "warranty_status", "") or "").strip()
    if warr:
        lines.append(f"Warranty status: {warr}.")

    # Cap to 3 to avoid overstuffing
    return lines[:3]


# ─────────────────────────────────────────────────────────────────────────────
# Suppression helpers
# ─────────────────────────────────────────────────────────────────────────────

_LOW_HOUR_PHRASES = (
    "low-hour", "low hour", "low hours", "low-hours",
    "low-hr", "low hr",
)


def _drop_sentences(text: str, banned: tuple) -> str:
    """Drop banned-substring sentences while preserving newlines/paragraph breaks."""
    blocks = text.split("\n")
    out: list[str] = []
    for blk in blocks:
        if not blk.strip():
            out.append(blk)
            continue
        sentences = re.split(r"(?<=[.!?])[ \t]+", blk)
        kept = [s for s in sentences if not any(b in s.lower() for b in banned)]
        out.append(" ".join(kept))
    return "\n".join(out)


def strip_unsupported_low_hours(text: str, eligible: bool) -> str:
    """When low-hours not eligible, scrub low-hour phrasing from sentences."""
    if eligible or not text:
        return text
    return _drop_sentences(text, _LOW_HOUR_PHRASES)


# =============================================================================
# Risk-tiered claim gating (RED / YELLOW / GREEN)
# =============================================================================
# RED   — hard proof required. Sentence dropped unless source field passes.
# YELLOW — context-allowed sales language. Permitted in Tier A/B with clean
#          condition notes; suppressed for Tier C; capped to avoid stacking.
# GREEN — feature/spec-anchored sales phrases. Always allowed when their
#          underlying spec or feature template fired.

# ── RED claims ────────────────────────────────────────────────────────────────
# Each entry: (phrase substrings, predicate(dealer_input) -> bool).
# Predicate False → all sentences containing any of the substrings are dropped.

def _has(di, *attrs) -> bool:
    for a in attrs:
        v = getattr(di, a, None)
        if v is None:
            continue
        if isinstance(v, bool):
            if v:
                return True
            continue
        if isinstance(v, (int, float)):
            if v:
                return True
            continue
        if str(v).strip():
            return True
    return False


def _hours_lt(di, n: int) -> bool:
    h = getattr(di, "hours", None)
    return isinstance(h, (int, float)) and 0 < h < n


_RED_RULES: tuple = (
    # phrase substrings, predicate(dealer_input) -> True when allowed
    (("no leaks", "no visible leaks", "no active leaks", "leak-free"),
     lambda di: _has(di, "no_visible_leaks")),
    (("no active fault codes", "no codes", "no active codes", "no fault codes"),
     lambda di: _has(di, "no_active_fault_codes")),
    (("fresh service", "freshly serviced", "just serviced", "fully serviced", "needs nothing"),
     lambda di: _has(di, "service_date", "service_hours", "service_items")),
    (("warranty remaining", "factory warranty", "warranty until"),
     lambda di: _has(di, "warranty_status", "warranty_expiration_date", "warranty_hours_remaining")),
    (("certified pre-owned", "certified used", "mtm certified", "dealer certified"),
     lambda di: _has(di, "certified")),
    (("inspected", "inspection passed", "passed inspection", "fully inspected"),
     lambda di: _has(di, "inspection_passed_full_checklist", "inspection_report_available")),
    (("turnkey",),
     lambda di: (_has(di, "inspection_passed_full_checklist")
                 and _has(di, "no_visible_leaks")
                 and _has(di, "no_active_fault_codes")
                 and _has(di, "service_date"))),
    # Dealer-asserted ownership phrasing — allowed when dealer flagged
    # one_owner=True.  Documentary verification NOT required (matches real
    # equipment-sales behaviour).  Verified-language is gated separately below.
    (("one owner", "one-owner", "single owner", "1-owner",
      "contractor-owned", "contractor owned", "owner-operated"),
     lambda di: _has(di, "one_owner", "single_owner_verified")),
    # Verification-only ownership phrasing — stronger than dealer-asserted
    # "one-owner machine".  These specifically claim documentary verification.
    (("single-owner verified", "verified one-owner", "verified single owner",
      "verified one owner history", "ownership verified"),
     lambda di: _has(di, "single_owner_verified")),
    # Inventory claims — actual hardware listed as included.  Capability
    # language ("attachment-ready", "attachment package", "high-flow package",
    # "setup for mulching") is YELLOW and not gated here.  These phrases
    # specifically promise included items and need a non-empty attachment list.
    (("attachments included", "all attachments included",
      "includes bucket", "includes forks", "includes grapple",
      "includes thumb", "includes auger", "includes blade",
      "includes mulcher", "includes hammer",
      "comes with bucket", "comes with forks", "comes with grapple",
      "comes with auger", "comes with thumb", "comes with mulcher",
      "comes with hammer"),
     lambda di: bool((getattr(di, "attachments_included", "") or "").strip())),
    # "Like new" still bounded — overclaim risk on anything but very-low-hour units.
    (("like new", "as new", "practically new"),
     lambda di: _hours_lt(di, 200)),
)


def apply_red_gate(text: str, dealer_input: Any) -> str:
    """Drop any sentence containing a RED-claim phrase whose proof field is missing."""
    if not text:
        return text
    for phrases, predicate in _RED_RULES:
        if predicate(dealer_input):
            continue
        if any(p in text.lower() for p in phrases):
            text = _drop_sentences(text, phrases)
    return text


# ── YELLOW phrases ────────────────────────────────────────────────────────────
# Dealer-asserted commercial language.  Allowed without documentary proof.
# Suppressed only for Tier C, known issues, or condition notes that contain
# negative mechanical signals.  Not capped — dealers stack sales language;
# MTM should match real equipment-sales tone, not over-police it.

YELLOW_PHRASES: tuple = (
    # Hours / wear sales language
    "low-hour", "low hour", "low hours",
    # Condition / care
    "clean machine", "clean unit", "clean low-hour",
    "well maintained", "well-maintained",
    "solid unit", "solid machine",
    "fleet maintained", "fleet-maintained",
    # Ownership (dealer-asserted, not documentary)
    "one owner", "one-owner", "single owner", "1-owner",
    "contractor-owned", "contractor owned", "owner-operated",
    # Readiness / fit
    "work-ready", "work ready",
    "job-ready", "jobsite ready", "job ready",
    "contractor-ready", "contractor ready",
    "ready to go to work", "ready to work",
    # Capability / package language (NOT inventory — those are RED-gated above).
    "attachment package", "full attachment package",
    "attachment-ready", "attachment ready",
    "attachment-capable", "attachment capable",
    "setup for mulching", "set up for mulching",
    "high-flow package", "high flow package",
    "mulching setup", "forestry setup",
)

_TIER_C_PROBLEM_SIGNALS = (
    "leak", "code", "knock", "smoke", "blown", "non-running", "doesn't run",
    "won't start", "wont start", "needs", "issue", "broken", "bent",
    "cracked", "as-is", "as is", "mechanic special", "mechanic's special",
    "parts only", "parts or repair",
)


def _has_problem_signal(dealer_input: Any) -> bool:
    notes = " ".join([
        (getattr(dealer_input, "condition_notes", "") or ""),
        (getattr(dealer_input, "additional_details", "") or ""),
    ]).lower()
    return any(sig in notes for sig in _TIER_C_PROBLEM_SIGNALS)


def apply_yellow_gate(text: str, dealer_input: Any, tier: str) -> str:
    """
    Yellow phrases are dealer-asserted commercial language.  Rules:
      - Tier C → drop all yellow phrases.
      - Negative mechanical signal in condition notes → drop all yellow phrases.
      - Otherwise: allow without cap (match real dealer-sales tone).
    """
    if not text:
        return text
    if tier == "C" or _has_problem_signal(dealer_input):
        return _drop_sentences(text, YELLOW_PHRASES)
    return text


# ── Truly weak/spammy phrases (always dropped when sentence has no proof) ─────
# Trimmed from the prior over-broad list — yellow sales phrases moved out.
WEAK_GENERIC_PHRASES = (
    "great power", "powerful engine", "strong performance",
    "heavy duty", "well built", "solid build",
    "well kept",
    "good lifting capacity", "good hydraulic flow", "high flow capable",
    "good fuel capacity", "comfortable cab", "climate controlled",
    "smooth ride", "compact size", "good tracks", "good undercarriage",
    "good reach", "deep digging", "good lift", "high lift",
    "high capacity", "good capacity", "good dump height",
    "nice machine", "nice unit",
    "no excuses", "fully loaded",
    "monster", "beast", "mint", "cream puff", "bad boy",
    "money maker",
)


def strip_weak_generic_phrases(text: str) -> str:
    """
    Drop short sentences whose only substantive content is a weak/spammy phrase
    with no numeric or proof token.  Sentences that combine a weak phrase with
    concrete facts pass.  Preserves newline/section structure.
    """
    if not text:
        return text
    blocks = text.split("\n")
    out: list[str] = []
    for blk in blocks:
        if not blk.strip():
            out.append(blk)
            continue
        sentences = re.split(r"(?<=[.!?])[ \t]+", blk)
        kept: list[str] = []
        for s in sentences:
            sl = s.lower().strip()
            if not sl:
                continue
            has_weak = any(p in sl for p in WEAK_GENERIC_PHRASES)
            has_proof = bool(re.search(r"\d", sl))
            if has_weak and not has_proof and len(sl.split()) <= 10:
                continue
            kept.append(s)
        out.append(" ".join(kept))
    return "\n".join(out)
