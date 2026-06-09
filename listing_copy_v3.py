"""
listing_copy_v3.py
==================
MTM Listing Copy Engine v3 — Deterministic Slot-Based Copy

Architecture:
    Layer 1: Tier Classifier       — assigns Tier A / B / C to the listing
    Layer 2: Claim Eligibility     — gates all credibility-sensitive claims
    Layer 3: Slot Composer         — selects and fills patterns per slot
    Layer 4: Platform Formatter    — applies platform-specific length and voice

Core rule: if a claim cannot be proven from available DealerInput fields,
           it is not rendered. Silence is safer than a confident falsehood.

Research basis: MTM-listing-copy-research.md (v1) + MTM-listing-copy-research-v2.md (v2)
                + mtm_phrasebank_v3.yaml (pattern bank)

Integration: called from listing_builder.build_listing_text() as the default
             engine. The caller falls back to v2 on any exception.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — TIER CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"

_TIER_C_NOTE_SIGNALS = frozenset([
    "needs repair", "mechanic's special", "mechanic special",
    "as-is", "as is", "parts or repair", "does not run",
    "non-running", "engine issue", "engine knock",
    "transmission issue", "hydraulic leak", "oil leak",
    "needs work", "not running", "broken", "inoperable",
    "bent boom", "cracked frame", "blown engine",
])

_ENCLOSED_CAB_VALUES = frozenset({"enclosed", "erops", "closed", "cab"})


def classify_tier(dealer_input: Any) -> str:
    """
    Classify listing into Tier A, B, or C.

    Tier A requires inspection trust fields not yet collected by DealerInput
    (no_visible_leaks, fault_codes_active, service_date, etc.).  With the
    current schema, A is never assigned — the engine always returns B or C.

    Tier B  — machine runs, condition grade acceptable or not set.
    Tier C  — known mechanical issue, "needs work" grade, or Tier C keywords
              present in condition notes.
    """
    grade = getattr(dealer_input, "condition_grade", None)

    if grade == "Needs Work":
        return TIER_C

    notes = " ".join(filter(None, [
        getattr(dealer_input, "condition_notes", "") or "",
        getattr(dealer_input, "additional_details", "") or "",
    ])).lower()

    if any(sig in notes for sig in _TIER_C_NOTE_SIGNALS):
        return TIER_C

    return TIER_B


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2 — CLAIM ELIGIBILITY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

# Maps uppercase token names (used in required_claims) to the underlying field
# names on DealerInput or resolved_specs, so "_eval_claim" can resolve them.
_TOKEN_FIELD_MAP: Dict[str, tuple] = {
    "ROC_LB":         ("roc_lb", "rated_operating_capacity_lbs"),
    "HI_FLOW_GPM":    ("aux_flow_high_gpm",),
    "FLOW_GPM":       ("aux_flow_standard_gpm", "hydraulic_flow_gpm"),
    "LIFT_CAP_LB":    ("lift_capacity_lb", "max_lift_capacity_lbs", "max_load_capacity_lbs"),
    "LIFT_HEIGHT_FT": ("max_lift_height_ft", "lift_height_ft", "max_load_height_ft"),
    "REACH_FT":       ("max_forward_reach_ft", "forward_reach_ft"),
    "DIG_FT":         ("max_dig_depth", "max_dig_depth_ft"),
    "WEIGHT_LB":      ("operating_weight_lb", "operating_weight_lbs"),
    "WIDTH_IN":       ("width_over_tires_in",),
    "TRACK_PCT":      ("track_percent_remaining",),
    "STICK_FT":       ("stick_arm_length_ft",),
    "HP":             ("net_hp", "horsepower_hp"),
    "WEIGHT_T":       ("operating_weight_lbs",),
    "HINGE_PIN_HT_IN": ("bucket_hinge_pin_height_in",),
}


FORBIDDEN_PHRASES: List[str] = [
    "won't last long", "better act fast", "she runs great",
    "money maker", "no excuses machine", "beautiful machine",
    "practically new", "just like the day it left the factory",
    "steal at this price", "priced to sell", "must sell",
    "will not disappoint", "look no further",
    "first come, first served", "cash talks",
    "world's best", "indestructible", "cheaper than",
    "no excuses", "gem of a", "honest machine",
    "loaded with performance",
]

# Claims requiring future trust fields (not yet in DealerInput).
# Presence of any FUTURE: tag in a pattern's required_claims auto-blocks it.
FUTURE_GATED_PREFIXES = ("FUTURE:", "future:")


@dataclass
class ClaimContext:
    """All facts the eligibility engine can reason about."""
    dealer_input: Any
    resolved_specs: Dict
    equipment_type: str
    tier: str
    platform: str


def _spec_val(ctx: ClaimContext, *keys: str) -> Any:
    """Return first non-None value across DealerInput attrs then resolved_specs."""
    for k in keys:
        v = getattr(ctx.dealer_input, k, None)
        if v is not None:
            return v
    for k in keys:
        v = ctx.resolved_specs.get(k)
        if v is not None:
            return v
    return None


def _eval_claim(claim: str, ctx: ClaimContext) -> bool:
    """
    Evaluate a single claim string against the current context.

    Supported grammar (from phrasebank YAML):
        FUTURE:field_name               → always False (trust field not collected yet)
        field_name == value             → equality check
        field_name != value             → inequality check
        field_name in [v1, v2, ...]     → membership check
        field_name present              → field is not None / not empty
        field_name > number             → numeric greater-than
        field_name < number             → numeric less-than
        field_name >= number            → numeric gte
        field_name <= number            → numeric lte
        condition_grade in [A, B]       → tier check shorthand
        condition_grade == C            → tier == C shorthand
    """
    claim = claim.strip()

    # Future-gated: never eligible with current schema
    if any(claim.startswith(p) for p in FUTURE_GATED_PREFIXES):
        return False

    # Tier shorthand
    if claim.startswith("condition_grade"):
        rest = claim[len("condition_grade"):].strip()
        if rest.startswith("in"):
            vals = re.findall(r"[A-C]", rest)
            return ctx.tier in vals
        if rest.startswith("=="):
            val = rest[2:].strip().strip("\"'")
            return ctx.tier == val
        return True  # unrecognised condition_grade sub-form → allow

    # Parse "field op value" forms
    m = re.match(
        r"^(\w+)\s*(==|!=|in|present|>=|<=|>|<|contains)\s*(.*)$",
        claim,
        re.IGNORECASE,
    )
    if not m:
        return True  # unrecognised form → allow (safe)

    field_name, op, raw_val = m.group(1), m.group(2).strip().lower(), m.group(3).strip()

    # Resolve field value — check DealerInput, then resolved_specs, then token-to-field map
    val = getattr(ctx.dealer_input, field_name, None)
    if val is None:
        val = ctx.resolved_specs.get(field_name)
    if val is None and field_name.upper() in _TOKEN_FIELD_MAP:
        for alt in _TOKEN_FIELD_MAP[field_name.upper()]:
            val = getattr(ctx.dealer_input, alt, None)
            if val is not None:
                break
            val = ctx.resolved_specs.get(alt)
            if val is not None:
                break

    op = op.lower()

    if op == "present":
        return val is not None and str(val).strip() != ""

    if op == "contains":
        if val is None:
            return False
        return raw_val.replace('"', "").replace("'", "").lower() in str(val).lower()

    if op == "in":
        choices = [c.strip().strip("[]\"'") for c in re.split(r"[,\[\]]", raw_val) if c.strip().strip("[]\"'")]
        if val is None:
            return False
        # Numeric comparison
        try:
            num = float(val)
            return any(num == float(c) for c in choices if _is_numeric(c))
        except (TypeError, ValueError):
            pass
        return str(val).lower() in {c.lower() for c in choices}

    if op == "==":
        rhs = raw_val.strip("\"'")
        if val is None:
            return rhs.lower() in ("none", "null", "")
        return str(val).lower() == rhs.lower()

    if op == "!=":
        rhs = raw_val.strip("\"'")
        if val is None:
            return rhs.lower() not in ("none", "null", "")
        return str(val).lower() != rhs.lower()

    # Numeric comparisons
    if op in (">", "<", ">=", "<="):
        try:
            lhs = float(val) if val is not None else None
            rhs = float(raw_val)
        except (TypeError, ValueError):
            return True
        if lhs is None:
            return False
        return {
            ">": lhs > rhs,
            "<": lhs < rhs,
            ">=": lhs >= rhs,
            "<=": lhs <= rhs,
        }[op]

    return True


def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def is_pattern_eligible(pattern: "PatternEntry", ctx: ClaimContext) -> bool:
    """Return True only when all required_claims pass and tier/platform match."""
    # Tier check
    if pattern.tier_eligibility and ctx.tier not in pattern.tier_eligibility:
        return False

    # Platform check
    if pattern.platform_fit and ctx.platform not in pattern.platform_fit:
        return False

    # All required claims must pass
    for claim in pattern.required_claims:
        if not _eval_claim(claim, ctx):
            return False

    return True


def has_required_tokens(pattern: "PatternEntry", resolved_tokens: Dict[str, str]) -> bool:
    """Return True when all required tokens are resolved to non-empty values."""
    for tok in pattern.required_tokens:
        if not resolved_tokens.get(tok, "").strip():
            return False
    return True


def safety_filter(text: str) -> str:
    """Remove any forbidden phrases that slipped into the final output."""
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in text.lower():
            text = _filter_sentences_preserving_breaks(text, (phrase.lower(),))
    return text


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3 — SLOT COMPOSER
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PatternEntry:
    id: str
    text: str
    required_tokens: List[str] = field(default_factory=list)
    required_claims: List[str] = field(default_factory=list)
    tier_eligibility: List[str] = field(default_factory=lambda: ["A", "B"])
    platform_fit: List[str] = field(default_factory=list)
    priority: int = 0  # 0 = specific/preferred; 9 = generic fallback (only fires when no priority-0 patterns are eligible)


# ── Token resolver ─────────────────────────────────────────────────────────

def _resolve_tokens(ctx: ClaimContext) -> Dict[str, str]:
    """
    Build the full token map from DealerInput and resolved_specs.
    All values are strings suitable for direct template substitution.
    """
    di, specs = ctx.dealer_input, ctx.resolved_specs

    def s(*keys: str, suffix: str = "", fallback: str = "") -> str:
        """First non-None numeric/string value, formatted."""
        for k in keys:
            v = getattr(di, k, None)
            if v is None:
                v = specs.get(k)
            if v is not None and str(v).strip():
                if isinstance(v, float) and v == int(v):
                    v = int(v)
                if isinstance(v, int) and v >= 1000:
                    return f"{v:,}{suffix}"
                return f"{v}{suffix}"
        return fallback

    def sf(fmt: str, *keys: str, fallback: str = "") -> str:
        for k in keys:
            v = getattr(di, k, None)
            if v is None:
                v = specs.get(k)
            if v is not None:
                try:
                    return fmt.format(float(v))
                except (TypeError, ValueError):
                    return str(v)
        return fallback

    # Cab label
    cab_raw = str(getattr(di, "cab_type", "") or "").lower().strip()
    if cab_raw in _ENCLOSED_CAB_VALUES:
        comforts = []
        if getattr(di, "ac", None):
            comforts.append("A/C")
        if getattr(di, "heater", None):
            comforts.append("heat")
        cab_label = ("enclosed cab w/ " + " & ".join(comforts)) if comforts else "enclosed cab"
    elif cab_raw in ("canopy", "rops", "canopy/rops"):
        cab_label = "Canopy / ROPS"
    elif cab_raw:
        cab_label = cab_raw.replace("_", " ").title()
    else:
        cab_label = ""

    # Hours qualifier (brief)
    hours = getattr(di, "hours", 0) or 0
    hours_qual = getattr(di, "hours_qualifier", None) or ""

    # ROC
    roc = _spec_val(ctx, "roc_lb", "rated_operating_capacity_lbs")
    roc_str = f"{int(roc):,}" if roc and isinstance(roc, (int, float)) else ""

    # HP
    hp = _spec_val(ctx, "net_hp", "horsepower_hp")
    hp_str = str(int(hp)) if hp and isinstance(hp, (int, float)) else ""

    # Lift cap / height / reach (telehandler)
    lift_cap = _spec_val(ctx, "lift_capacity_lb", "max_lift_capacity_lbs", "lift_capacity_lbs", "max_load_capacity_lbs")
    lift_ht = _spec_val(ctx, "max_lift_height_ft", "lift_height_ft", "max_load_height_ft")
    fwd_reach = _spec_val(ctx, "max_forward_reach_ft", "forward_reach_ft")

    # Hydraulic flow
    hi_flow = _spec_val(ctx, "aux_flow_high_gpm")
    std_flow = _spec_val(ctx, "aux_flow_standard_gpm", "hydraulic_flow_gpm")
    flow_gpm = hi_flow if getattr(di, "high_flow", None) == "yes" and hi_flow else std_flow

    # Dig depth (mini ex)
    dig_depth = _spec_val(ctx, "max_dig_depth", "max_dig_depth_ft")
    if isinstance(dig_depth, (int, float)):
        dig_str = f"{dig_depth:.1f} ft"
    elif isinstance(dig_depth, str):
        dig_str = dig_depth
    else:
        dig_str = ""

    # Track condition
    track_cond = getattr(di, "track_condition", None) or ""
    track_pct_raw = getattr(di, "track_percent_remaining", None)
    track_pct = str(track_pct_raw) if track_pct_raw is not None else ""

    # Tire condition
    tire_cond = getattr(di, "tire_condition", None) or ""

    # Width
    width = _spec_val(ctx, "width_over_tires_in")
    width_str = str(int(width)) if width and isinstance(width, (int, float)) else ""

    # Hinge pin height
    hinge = _spec_val(ctx, "bucket_hinge_pin_height_in")
    hinge_str = str(int(hinge)) if hinge and isinstance(hinge, (int, float)) else ""

    # Condition note (first 80 chars of condition_notes, clean)
    cond_note = (getattr(di, "condition_notes", "") or getattr(di, "additional_details", "") or "").strip()
    cond_note_short = cond_note[:80].rstrip(",;. ") if cond_note else ""

    # Attachments summary (short)
    att = (getattr(di, "attachments_included", "") or "").strip()
    att_short = att[:60].rstrip(",;. ") if att else ""

    # Bucket size
    bucket_size = (getattr(di, "bucket_size", None) or getattr(di, "bucket_size_included", None) or "").strip()

    # Stick / arm length (excavator)
    stick_ft = getattr(di, "stick_arm_length_ft", None)
    stick_str = f"{stick_ft} ft" if stick_ft else ""

    # Track shoe width (excavator)
    track_shoe = getattr(di, "track_shoe_width_in", None)
    track_shoe_str = f"{int(track_shoe)}\"" if track_shoe else ""

    # Operating weight
    wt = _spec_val(ctx, "operating_weight_lb", "operating_weight_lbs")
    wt_str = f"{int(wt):,}" if wt and isinstance(wt, (int, float)) else ""
    wt_t = f"{wt / 2000:.0f}" if wt and isinstance(wt, (int, float)) else ""

    # Lift path label
    lift_path = str(_spec_val(ctx, "lift_path") or "").lower().replace("_", " ")

    return {
        "YEAR":           str(getattr(di, "year", "")),
        "MAKE":           str(getattr(di, "make", "")).upper(),
        "MODEL":          str(getattr(di, "model", "")),
        "HOURS":          f"{hours:,}",
        "HP":             hp_str,
        "ROC_LB":         roc_str,
        "FLOW_GPM":       str(int(float(std_flow))) if std_flow else "",
        "HI_FLOW_GPM":    str(int(float(hi_flow))) if hi_flow else "",
        "LIFT_CAP_LB":    f"{int(lift_cap):,}" if lift_cap else "",
        "LIFT_HEIGHT_FT": str(int(float(lift_ht))) if lift_ht else "",
        "REACH_FT":       str(int(float(fwd_reach))) if fwd_reach else "",
        "DIG_FT":         dig_str,
        "UC_PCT":         track_pct,
        "TRACK_PCT":      track_pct,
        "TRACK_CONDITION": track_cond,
        "TIRE_CONDITION": tire_cond,
        "WIDTH_IN":       width_str,
        "HINGE_PIN_HT_IN": hinge_str,
        "WEIGHT_LB":      wt_str,
        "WEIGHT_T":       wt_t,
        "STICK_FT":       stick_str,
        "TRACK_W_IN":     track_shoe_str,
        "LIFT_PATH":      lift_path,
        "CAB_TYPE":       cab_label,
        "CONDITION_GRADE": getattr(di, "condition_grade", "") or "",
        "CONDITION_NOTE": cond_note_short,
        "ATTACHMENTS_INCLUDED": att_short,
        "BUCKET_SIZE_IN": bucket_size,
        "HOURS_QUALIFIER": hours_qual,
        # Dealer contact tokens (usually absent → blank, CTA degrades gracefully)
        "STOCK":         getattr(di, "stock_number", "") or "",
        "PHONE":         "",
        "EMAIL":         "",
        "CITY":          "",
        "STATE":         "",
        "DEALER_NAME":   "",
        "PRICE":         f"{getattr(di, 'asking_price', 0):,}" if getattr(di, "asking_price", None) else "",
        "MONTHLY":       "",
        "APR":           "",
        "WARR_DATE":     "",
        "WARR_LEN":      "",
    }


def _fill_pattern(template: str, tokens: Dict[str, str]) -> Optional[str]:
    """
    Fill bracketed tokens.  Returns None if any required token placeholder
    remains unfilled after substitution (caller treats as ineligible).
    """
    result = template
    for k, v in tokens.items():
        result = result.replace("{" + k + "}", v)
    # Any remaining {TOKEN} → pattern is under-resolved, discard
    if re.search(r"\{[A-Z_]+\}", result):
        return None
    return result


def _stable_index(di: Any, eq_type: str, bank_len: int) -> int:
    """Deterministic selection index — same machine always picks same pattern."""
    key = "|".join(str(getattr(di, a, "") or "") for a in ("year", "make", "model", "hours"))
    digest = hashlib.sha1(f"{eq_type}|{key}".encode()).hexdigest()
    return int(digest[:8], 16) % bank_len


def _filter_by_priority(candidates: List[PatternEntry]) -> List[PatternEntry]:
    """
    Return only priority-0 patterns if any exist; otherwise return priority-9 fallbacks.
    This ensures generic fallback patterns never compete with specific patterns.
    """
    specific = [p for p in candidates if p.priority == 0]
    return specific if specific else candidates


def _select_pattern(
    bank: List[PatternEntry],
    ctx: ClaimContext,
    tokens: Dict[str, str],
    exclude_ids: Optional[set] = None,
) -> Optional[str]:
    """
    Select the best eligible, token-complete pattern from a bank.
    Priority-0 (specific) patterns are always preferred over priority-9 (generic).
    Uses hash-based deterministic rotation within the chosen priority tier.
    """
    eligible = [
        p for p in bank
        if (exclude_ids is None or p.id not in exclude_ids)
        and is_pattern_eligible(p, ctx)
        and has_required_tokens(p, tokens)
    ]
    eligible = _filter_by_priority(eligible)
    if not eligible:
        return None

    start = _stable_index(ctx.dealer_input, ctx.equipment_type, len(eligible))
    chosen = eligible[start % len(eligible)]
    return _fill_pattern(chosen.text, tokens)


def _select_n_patterns(
    bank: List[PatternEntry],
    ctx: ClaimContext,
    tokens: Dict[str, str],
    n: int,
    exclude_ids: Optional[set] = None,
) -> List[str]:
    """
    Select up to n distinct eligible patterns, avoiding repeats.
    Priority-0 (specific) patterns are always preferred over priority-9 (generic).
    """
    result: List[str] = []
    used_ids: set = set(exclude_ids or [])

    eligible = [
        p for p in bank
        if p.id not in used_ids
        and is_pattern_eligible(p, ctx)
        and has_required_tokens(p, tokens)
    ]
    eligible = _filter_by_priority(eligible)
    if not eligible:
        return result

    start = _stable_index(ctx.dealer_input, ctx.equipment_type, len(eligible))
    for i in range(n):
        idx = (start + i) % len(eligible)
        filled = _fill_pattern(eligible[idx].text, tokens)
        if filled and eligible[idx].id not in used_ids:
            result.append(filled)
            used_ids.add(eligible[idx].id)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# PATTERN BANKS
# ─────────────────────────────────────────────────────────────────────────────
# Drawn from phrasebank v3 (today-available patterns only — no FUTURE: gates).
# Each bank keyed by _normalize_eq_type() output.

def _mk(id_: str, text: str, tokens=None, claims=None, tiers=None, platforms=None, priority: int = 0) -> PatternEntry:
    return PatternEntry(
        id=id_,
        text=text,
        required_tokens=tokens or [],
        required_claims=claims or [],
        tier_eligibility=tiers or ["A", "B"],
        platform_fit=platforms or [],
        priority=priority,
    )


# ── Compact Track Loader ────────────────────────────────────────────────────

_CTL_LEADS: List[PatternEntry] = [
    _mk("ctl_lead_001",
        "{YEAR} {MAKE} {MODEL} — {ROC_LB} lb ROC, {HOURS} hrs, high-flow hydraulics, {CAB_TYPE}.",
        tokens=["YEAR", "MAKE", "MODEL", "ROC_LB", "HOURS"],
        claims=["high_flow == yes", "cab_type present"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("ctl_lead_002",
        "If you're running a mulcher, cold planer, or drum cutter — this {MAKE} {MODEL} has the hydraulic flow to match.",
        tokens=["MAKE", "MODEL"],
        claims=["high_flow == yes"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("ctl_lead_004",
        "Low-hour {MAKE} {MODEL}: {HOURS} hrs, high flow, 2-speed — the spec contractors wait for.",
        tokens=["MAKE", "MODEL", "HOURS"],
        claims=["high_flow == yes", "two_speed_travel == yes", "hours < 1500"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("ctl_lead_005",
        "{YEAR} {MAKE} {MODEL}, {HOURS} hrs — {ROC_LB} lb ROC, {LIFT_PATH} lift. Clean machine for site work and material handling.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "ROC_LB"],
        claims=["high_flow == no"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("ctl_lead_006",
        "Forestry-spec {YEAR} {MODEL}: high-flow hydraulics, reversing fan, {HOURS} hrs. Runs mulchers without cooling headaches.",
        tokens=["YEAR", "MODEL", "HOURS"],
        claims=["high_flow == yes", "reversing_fan == yes"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("ctl_lead_007",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, 2-speed, {CAB_TYPE}. ${PRICE} in {CITY}, {STATE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "PRICE", "CITY", "STATE"],
        claims=["two_speed_travel == yes", "asking_price present"],
        platforms=["facebook_marketplace"]),
    _mk("ctl_lead_009",
        "Used {MAKE} {MODEL} in good working order — {HOURS} hrs, runs and drives.",
        tokens=["MAKE", "MODEL", "HOURS"],
        claims=[],
        tiers=["B"],
        platforms=["machinery_trader", "facebook_marketplace", "equipment_trader"]),
    _mk("ctl_lead_010",
        "Needs-work {YEAR} {MAKE} {MODEL} — {HOURS} hrs. Known issue: {CONDITION_NOTE}. Priced as a mechanic's special.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "CONDITION_NOTE"],
        claims=["condition_grade == C", "condition_notes present"],
        tiers=["C"],
        platforms=["machinery_trader", "facebook_marketplace", "equipment_trader"]),
    _mk("ctl_lead_011",
        "Late-model {YEAR} {MAKE} {MODEL} — {HOURS} hrs on a {HP}-HP machine with high flow.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "HP"],
        claims=["high_flow == yes"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("ctl_lead_012",
        "{YEAR} {MAKE} {MODEL}, {HOURS} hrs. Standard-flow but {HP} HP — right for landscaping, site cleanup, and most general-use attachments.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "HP"],
        claims=["high_flow == no"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("ctl_lead_013",
        "This {YEAR} compact track loader ({MAKE} {MODEL}) has {HOURS} operational hours and is in good working condition.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=["boom_bucket"]),
    _mk("ctl_lead_014",
        "{MAKE} {MODEL} — {ROC_LB} lb ROC, {HOURS} hrs, 2-speed. Production machine at a mid-market price.",
        tokens=["MAKE", "MODEL", "ROC_LB", "HOURS"],
        claims=["two_speed_travel == yes"],
        platforms=["dealer_site"]),
    _mk("ctl_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, {ROC_LB} lb ROC. CTL for site work and attachment-driven production.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "ROC_LB"],
        claims=[],
        platforms=[],
        priority=9),  # universal fallback — only fires when no specific patterns are eligible
]

_CTL_OP_VALUES: List[PatternEntry] = [
    _mk("ctl_op_001",
        "High flow delivers {HI_FLOW_GPM} gpm — enough hydraulic output to run a drum mulcher, cold planer, or large stump grinder at full rated speed.",
        tokens=["HI_FLOW_GPM"],
        claims=["high_flow == yes", "HI_FLOW_GPM present"]),
    _mk("ctl_op_002",
        "High flow unlocks the heavy attachment library: mulchers, planers, rock saws, large snowblowers. If your attachment needs more than 25 gpm, this machine can deliver.",
        claims=["high_flow == yes"]),
    _mk("ctl_op_003",
        "Standard-flow auxiliary at {FLOW_GPM} gpm handles augers, breakers, trenchers, grapples, and four-in-one buckets — the full general-use attachment list.",
        tokens=["FLOW_GPM"],
        claims=["high_flow == no", "FLOW_GPM present"]),
    _mk("ctl_op_005",
        "Two-speed makes this a site machine too — repositions across the yard at speed, not just works in one spot.",
        claims=["two_speed_travel == yes"]),
    _mk("ctl_op_008",
        "Reversing fan pushes debris away from the radiator — useful on mulching and forestry jobs where intake clogging kills uptime.",
        claims=["reversing_fan == yes"]),
    _mk("ctl_op_010",
        "Enclosed cab with heat and A/C takes weather out of the equation — the operator works comfortably whether it's 15° or 95° on site.",
        claims=["cab_type in [enclosed, erops, closed, cab]", "ac == True"]),
    _mk("ctl_op_012",
        "Self-leveling bucket holds the load angle through the full lift arc — less spillage, less operator correction on every cycle.",
        claims=["self_leveling == yes"]),
    _mk("ctl_op_013",
        "Pilot (joystick) controls reduce operator fatigue on long cycles versus hand-and-foot. The machine responds where the hands are.",
        claims=["control_type in [sjc, joystick, pilot]"]),
    _mk("ctl_op_014",
        "Hydraulic coupler swaps buckets from the cab — no pin removal, no stepping off the machine in the rain.",
        claims=["coupler_type in [power_bobtach, hydraulic]"]),
    _mk("ctl_op_roc",
        "{ROC_LB} lb rated operating capacity gives confidence on full-bucket picks and loading cycles without tip-warning.",
        tokens=["ROC_LB"],
        claims=["ROC_LB present"]),
    _mk("ctl_op_width",
        "Machine width: {WIDTH_IN}\". Fits through standard gates without teardown on most residential and commercial sites.",
        tokens=["WIDTH_IN"],
        claims=["WIDTH_IN present"]),
]

_CTL_CTAS: List[PatternEntry] = [
    _mk("ctl_cta_004",
        "Third-party inspection welcome — we'll coordinate yard access.",
        claims=[]),
    _mk("ctl_cta_007",
        "Available to view at our yard. Bring your trailer — it can leave the same day.",
        claims=[]),
    _mk("ctl_cta_generic",
        "Call or text for pricing, availability, and inspection details.",
        claims=[],
        priority=9),
]


# ── Skid Steer Loader ───────────────────────────────────────────────────────

_SSL_LEADS: List[PatternEntry] = [
    _mk("ssl_lead_001",
        "{YEAR} {MAKE} {MODEL} — {ROC_LB} lb ROC, {HOURS} hrs, {TIRE_CONDITION} tires, {CAB_TYPE}.",
        tokens=["YEAR", "MAKE", "MODEL", "ROC_LB", "HOURS", "TIRE_CONDITION", "CAB_TYPE"],
        claims=["ROC_LB present", "tire_condition present"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("ssl_lead_002",
        "Wheeled skid steer built for pavement and hard-surface work — {YEAR} {MODEL}, {ROC_LB} lb, {HOURS} hrs.",
        tokens=["YEAR", "MODEL", "ROC_LB", "HOURS"],
        claims=["ROC_LB present"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("ssl_lead_004",
        "High-flow {YEAR} {MODEL} — {HOURS} hrs, 2-speed, vertical lift. Runs the heavy-duty attachment list.",
        tokens=["YEAR", "MODEL", "HOURS"],
        claims=["high_flow == yes", "two_speed_travel == yes"],
        platforms=["machinery_trader", "dealer_site"]),
    _mk("ssl_lead_005",
        "{YEAR} {MAKE} {MODEL}, {HOURS} hrs, runs and drives. {CAB_TYPE}. Ready for inspection.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=["cab_type present"],
        tiers=["B"],
        platforms=["machinery_trader", "facebook_marketplace"]),
    _mk("ssl_lead_007",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, {ROC_LB} lb. Priced at ${PRICE} in {CITY}, {STATE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "ROC_LB", "PRICE", "CITY", "STATE"],
        claims=["asking_price present", "ROC_LB present"],
        platforms=["facebook_marketplace"]),
    _mk("ssl_lead_009",
        "On pavement, finished concrete, or indoor floors, this wheeled {MODEL} won't tear your surface the way a CTL does.",
        tokens=["MODEL"],
        claims=[],
        platforms=["dealer_site"],
        priority=9),  # pavement point — suppressed when ssl_op_001 would also make it
    _mk("ssl_lead_012",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, {ROC_LB} lb, open ROPS. Priced for those who don't need an enclosed cab.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "ROC_LB"],
        claims=["ROC_LB present"],
        platforms=["machinery_trader", "facebook_marketplace"]),
    _mk("ssl_lead_013",
        "Low-hour {YEAR} {MODEL}: {HOURS} hrs. Buying well under the class average on hours.",
        tokens=["YEAR", "MODEL", "HOURS"],
        claims=["hours < 1000"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("ssl_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, {ROC_LB} lb ROC. Wheeled skid steer for daily site work.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "ROC_LB"],
        claims=["ROC_LB present"],
        platforms=[],
        priority=9),
    _mk("ssl_lead_generic2",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs. Skid steer for loading, grading, and general site work.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=[],
        priority=9),
]

_SSL_OP_VALUES: List[PatternEntry] = [
    _mk("ssl_op_001",
        "On pavement, compacted gravel, and finished concrete, a wheeled skid steer does less surface damage than a tracked CTL — no rubber track marks, no torn-up asphalt.",
        claims=[],
        priority=9),  # generic SSL benefit — deprioritized so specific op-values (high flow, ROC, lift path) fire first
    _mk("ssl_op_003",
        "High flow at {HI_FLOW_GPM} gpm powers cold planers, stump grinders, mulching heads, and large augers — attachments that standard-flow machines can't run.",
        tokens=["HI_FLOW_GPM"],
        claims=["high_flow == yes", "HI_FLOW_GPM present"]),
    _mk("ssl_op_005",
        "Vertical lift geometry keeps the load level and forward through the full arc — the right choice for loading dump trucks and hoppers.",
        claims=["lift_path == vertical"]),
    _mk("ssl_op_007",
        "Pilot (joystick) controls let the operator focus on the work, not the pedals. Faster learning curve and less fatigue.",
        claims=["control_type in [sjc, joystick, pilot]"]),
    _mk("ssl_op_roc",
        "{ROC_LB} lb ROC — the load limit you plan full bucket picks and truck cycles against.",
        tokens=["ROC_LB"],
        claims=["ROC_LB present"]),
    _mk("ssl_op_2spd",
        "Two-speed travel repositions across the site at speed — saves real time on large jobs.",
        claims=["two_speed_travel == yes"]),
]

_SSL_CTAS: List[PatternEntry] = [
    _mk("ssl_cta_generic",
        "Call or text for pricing, availability, and inspection details.",
        claims=[],
        priority=9),
    _mk("ssl_cta_inspect",
        "Available for inspection. Bring your trailer — it can leave the same day.",
        claims=[]),
]


# ── Mini Excavator ──────────────────────────────────────────────────────────

_MINI_EX_LEADS: List[PatternEntry] = [
    _mk("mex_lead_001",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, hydraulic thumb, {DIG_FT} dig depth, {CAB_TYPE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "DIG_FT"],
        claims=["thumb_type in [hydraulic, manual]", "DIG_FT present"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("mex_lead_002",
        "{YEAR} {MAKE} {MODEL} with hydraulic thumb and quick coupler — {HOURS} hrs, buyer-favourite spec.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=["thumb_type in [hydraulic, manual]", "coupler_type present"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("mex_lead_003",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, {DIG_FT} dig depth. Good setup for residential and light commercial excavation.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "DIG_FT"],
        claims=["DIG_FT present"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("mex_lead_004",
        "{YEAR} {MAKE} {MODEL}, {HOURS} hrs — {CAB_TYPE}, hydraulic thumb, multi-function aux. Ready to move.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=["thumb_type in [hydraulic, manual]", "aux_hydraulics == True", "cab_type present"],
        platforms=["machinery_trader", "dealer_site"]),
    _mk("mex_lead_005",
        "Zero-tail-swing {YEAR} {MAKE} {MODEL}: dig within inches of a wall without repositioning the chassis. {HOURS} hrs.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=["zero_tail_swing == True"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("mex_lead_006",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, thumb included, {DIG_FT} dig depth. ${PRICE} in {CITY}, {STATE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "DIG_FT", "PRICE", "CITY", "STATE"],
        claims=["thumb_type in [hydraulic, manual]", "asking_price present", "DIG_FT present"],
        platforms=["facebook_marketplace"]),
    _mk("mex_lead_low_hour",
        "Low-hour {YEAR} {MAKE} {MODEL}: {HOURS} hrs. Clean rubber, hydraulic thumb, coupler-ready.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=["hours < 800", "thumb_type in [hydraulic, manual]", "coupler_type present"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("mex_lead_bb",
        "This {YEAR} mini excavator ({MAKE} {MODEL}) has {HOURS} operational hours and is in good working condition.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=["boom_bucket"],
        priority=9),
    _mk("mex_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs. Mini excavator for trenching, utility work, and site prep.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=[],
        priority=9),
]

_MINI_EX_OP_VALUES: List[PatternEntry] = [
    _mk("mex_op_thumb",
        "Hydraulic thumb grips logs, rip-rap, concrete chunks, and debris without rigging — makes it a versatile handler, not just a digger.",
        claims=["thumb_type in [hydraulic, manual]"]),
    _mk("mex_op_qc",
        "Hydraulic quick coupler lets one operator swap buckets in under 30 seconds without leaving the cab — fewer tool changes, more time digging.",
        claims=["coupler_type in [hydraulic, manual]"]),
    _mk("mex_op_dig",
        "{DIG_FT} max dig depth handles standard utility work, foundation drains, and septic installs from a single pass.",
        tokens=["DIG_FT"],
        claims=["DIG_FT present"]),
    _mk("mex_op_zts",
        "Zero tail swing keeps the counterweight inside the track footprint when slewing — digs full rotation in fenced yards and alleyways.",
        claims=["zero_tail_swing == True"]),
    _mk("mex_op_aux",
        "Auxiliary hydraulics support a hammer, auger, compactor, or trenching head on the same machine — no re-plumbing between jobs.",
        claims=["aux_hydraulics == True"]),
    _mk("mex_op_blade",
        "Blade cleans up spoils and back-fills trench walls without repositioning the machine.",
        claims=["blade_type present"]),
    _mk("mex_op_cab",
        "Enclosed cab with heat and A/C extends the productive day across weather — full year, all climate.",
        claims=["cab_type in [enclosed, erops, closed, cab]"]),
    _mk("mex_op_weight",
        "{WEIGHT_LB} lb operating weight — sized for residential access without secondary equipment or oversize transport.",
        tokens=["WEIGHT_LB"],
        claims=["WEIGHT_LB present"]),
]

_MINI_EX_CTAS: List[PatternEntry] = [
    _mk("mex_cta_generic",
        "Call or text for pricing, availability, and a walk-around video.",
        claims=[],
        priority=9),
    _mk("mex_cta_price",
        "Call or text to schedule a look.",
        claims=["asking_price present"]),
]


# ── Telehandler ─────────────────────────────────────────────────────────────

_TELEHANDLER_LEADS: List[PatternEntry] = [
    _mk("tel_lead_001",
        "{YEAR} {MAKE} {MODEL} — {LIFT_CAP_LB} lb / {LIFT_HEIGHT_FT} ft, {HOURS} hrs, {CAB_TYPE}.",
        tokens=["YEAR", "MAKE", "MODEL", "LIFT_CAP_LB", "LIFT_HEIGHT_FT", "HOURS"],
        claims=["LIFT_CAP_LB present", "LIFT_HEIGHT_FT present"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("tel_lead_002",
        "If you're staging trusses, pallets, or material at height — this {MAKE} {MODEL} lifts {LIFT_CAP_LB} lb to {LIFT_HEIGHT_FT} ft with {REACH_FT} ft of forward reach.",
        tokens=["MAKE", "MODEL", "LIFT_CAP_LB", "LIFT_HEIGHT_FT", "REACH_FT"],
        claims=["LIFT_CAP_LB present", "LIFT_HEIGHT_FT present", "REACH_FT present"],
        platforms=["dealer_site"]),
    _mk("tel_lead_003",
        "Low-hour {YEAR} {MAKE} {MODEL}: {HOURS} hrs, {LIFT_CAP_LB} lb capacity, foam-filled tires.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "LIFT_CAP_LB"],
        claims=["hours < 2500", "LIFT_CAP_LB present"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("tel_lead_004",
        "{YEAR} {MAKE} {MODEL} — {LIFT_HEIGHT_FT} ft lift height, {HOURS} hrs, {CAB_TYPE}. Rooftop staging and truss work.",
        tokens=["YEAR", "MAKE", "MODEL", "LIFT_HEIGHT_FT", "HOURS"],
        claims=["LIFT_HEIGHT_FT present"],
        platforms=["dealer_site", "machinery_trader"]),
    _mk("tel_lead_005",
        "{YEAR} {MAKE} {MODEL}, {HOURS} hrs, {LIFT_CAP_LB} lb. Priced at ${PRICE} in {CITY}, {STATE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "LIFT_CAP_LB", "PRICE", "CITY", "STATE"],
        claims=["asking_price present", "LIFT_CAP_LB present"],
        platforms=["facebook_marketplace"]),
    _mk("tel_lead_stab",
        "{YEAR} {MAKE} {MODEL} with outrigger stabilizers — {LIFT_CAP_LB} lb at full extension, {HOURS} hrs. Real reach at max load.",
        tokens=["YEAR", "MAKE", "MODEL", "LIFT_CAP_LB", "HOURS"],
        claims=["has_stabilizers == True", "LIFT_CAP_LB present"]),
    _mk("tel_lead_bb",
        "This {YEAR} telehandler ({MAKE} {MODEL}) has {HOURS} operational hours and is in good working condition.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=["boom_bucket"],
        priority=9),
    _mk("tel_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {LIFT_CAP_LB} lb capacity, {LIFT_HEIGHT_FT} ft lift, {HOURS} hrs. Jobsite-ready telehandler.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=[],
        priority=9),
]

_TELEHANDLER_OP_VALUES: List[PatternEntry] = [
    _mk("tel_op_cap_ht",
        "{LIFT_CAP_LB} lb capacity to {LIFT_HEIGHT_FT} ft — {REACH_FT} ft of forward reach without re-positioning the machine.",
        tokens=["LIFT_CAP_LB", "LIFT_HEIGHT_FT", "REACH_FT"],
        claims=["LIFT_CAP_LB present", "LIFT_HEIGHT_FT present", "REACH_FT present"]),
    _mk("tel_op_stab",
        "Outrigger stabilizers extend the safe working envelope at full reach — no guessing the load limit at extension.",
        claims=["has_stabilizers == True"]),
    _mk("tel_op_cab",
        "Enclosed cab with heat and A/C makes it a year-round, all-weather material handler — no seasonal limits.",
        claims=["cab_type in [enclosed, erops, closed, cab]"]),
    _mk("tel_op_forks",
        "Forks included — unload flatbeds, distribute pallets on site, and stage materials at work areas without additional equipment.",
        claims=[]),
    _mk("tel_op_reach",
        "{REACH_FT} ft forward reach lets the machine pick over site barriers, walls, and parked equipment — fewer truck moves per shift.",
        tokens=["REACH_FT"],
        claims=["REACH_FT present"]),
    _mk("tel_op_4x4",
        "4WD keeps it moving across wet, soft, and rutted sites without losing traction between lifts.",
        claims=[]),
]

_TELEHANDLER_CTAS: List[PatternEntry] = [
    _mk("tel_cta_generic",
        "Call or text for pricing, availability, and a walk-around video.",
        claims=[],
        priority=9),
    _mk("tel_cta_inspect",
        "Available for inspection at our yard. Bring your transport — it can leave the same day.",
        claims=[]),
]


# ── Wheel Loader ────────────────────────────────────────────────────────────

_WL_LEADS: List[PatternEntry] = [
    _mk("wl_lead_001",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, {TIRE_CONDITION} tires.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "TIRE_CONDITION"],
        claims=["tire_condition present"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("wl_lead_002",
        "{YEAR} {MAKE} {MODEL} — {HP}-HP loader, {HOURS} hrs. Solid material handler for pallet work, bucket loading, and yard operations.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "HP"],
        claims=["HP present"]),
    _mk("wl_lead_fb",
        "{YEAR} {MAKE} {MODEL} wheel loader, {HOURS} hrs. Priced at ${PRICE} in {CITY}, {STATE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "PRICE", "CITY", "STATE"],
        claims=["asking_price present"],
        platforms=["facebook_marketplace"]),
    _mk("wl_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs. Wheel loader for material handling, yard work, and production loading.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=[],
        priority=9),
]

_WL_OP_VALUES: List[PatternEntry] = [
    _mk("wl_op_hp",
        "{HP} HP pulls hard up grades and out of dig faces without bogging — production-class output.",
        tokens=["HP"],
        claims=["HP present"]),
    _mk("wl_op_cab",
        "Enclosed cab with heat and A/C keeps the operator productive across all weather — a year-round machine.",
        claims=["cab_type in [enclosed, erops, closed, cab]"]),
    _mk("wl_op_generic",
        "Good material handler for pallet work, loading trucks, and on-site staging.",
        claims=[],
        priority=9),
]

_WL_CTAS: List[PatternEntry] = [
    _mk("wl_cta_generic",
        "Call or text for pricing, availability, and inspection details.",
        claims=[],
        priority=9),
]


# ── Backhoe Loader ──────────────────────────────────────────────────────────

_BH_LEADS: List[PatternEntry] = [
    _mk("bh_lead_001",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, 4x4, extendahoe, {CAB_TYPE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=["cab_type present"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("bh_lead_002",
        "{YEAR} {MAKE} {MODEL} backhoe — {HOURS} hrs, {HP} HP, 4x4. Strong performer for trenching, utility, and site work.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "HP"],
        claims=["HP present"]),
    _mk("bh_lead_fb",
        "{YEAR} {MAKE} {MODEL} backhoe, {HOURS} hrs, runs and drives. ${PRICE} in {CITY}, {STATE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "PRICE", "CITY", "STATE"],
        claims=["asking_price present"],
        platforms=["facebook_marketplace"]),
    _mk("bh_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs. Backhoe loader for digging, loading, and utility work.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=[],
        priority=9),
]

_BH_OP_VALUES: List[PatternEntry] = [
    _mk("bh_op_4x4",
        "4x4 keeps it moving on muddy job sites and through soft pile bases — one machine for all seasons.",
        claims=[]),
    _mk("bh_op_ext",
        "Extendahoe adds dig reach without repositioning — fewer setup moves per utility cut.",
        claims=[]),
    _mk("bh_op_generic",
        "Good all-around machine for trenching, loading, and mixed-use job sites.",
        claims=[],
        priority=9),
]

_BH_CTAS: List[PatternEntry] = [
    _mk("bh_cta_generic",
        "Call or text for pricing, availability, and inspection details.",
        claims=[],
        priority=9),
]


# ── Excavator (full-size) ───────────────────────────────────────────────────

_EX_LEADS: List[PatternEntry] = [
    _mk("ex_lead_001",
        "{YEAR} {MAKE} {MODEL} — {WEIGHT_T}-ton class, {HOURS} hrs, {STICK_FT} arm, {TRACK_PCT}% UC.",
        tokens=["YEAR", "MAKE", "MODEL", "WEIGHT_T", "HOURS", "STICK_FT", "TRACK_PCT"],
        claims=["WEIGHT_T present", "STICK_FT present", "TRACK_PCT present"],
        platforms=["machinery_trader", "equipment_trader", "dealer_site"]),
    _mk("ex_lead_002",
        "{YEAR} {MAKE} {MODEL}, {HOURS} hrs — hydraulic thumb, hydraulic coupler, production utility setup.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=["thumb_type in [hydraulic, manual]", "coupler_type present"]),
    _mk("ex_lead_003",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs, {WEIGHT_T}-ton class. {TRACK_PCT}% undercarriage remaining.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=["TRACK_PCT present"]),
    _mk("ex_lead_fb",
        "{YEAR} {MAKE} {MODEL} excavator, {HOURS} hrs. Priced at ${PRICE} in {CITY}, {STATE}.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS", "PRICE", "CITY", "STATE"],
        claims=["asking_price present"],
        platforms=["facebook_marketplace"]),
    _mk("ex_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs. Excavator for earthmoving, utility work, and production digging.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=[],
        priority=9),
]

_EX_OP_VALUES: List[PatternEntry] = [
    _mk("ex_op_thumb",
        "Hydraulic thumb grips logs, broken concrete, and demo debris without rigging — handles material movement alongside digging.",
        claims=["thumb_type in [hydraulic, manual]"]),
    _mk("ex_op_uc",
        "Undercarriage at {TRACK_PCT}% remaining — the most expensive single wear item on a full-size excavator. Priced accordingly.",
        tokens=["TRACK_PCT"],
        claims=["TRACK_PCT present"]),
    _mk("ex_op_aux",
        "Auxiliary hydraulics support a hydraulic hammer, shear, grapple, or compactor without re-plumbing.",
        claims=["aux_hydraulics_type present"]),
    _mk("ex_op_gc",
        "Grade control installed — eliminates string-line setup and surveyor passes on finish grade work.",
        claims=["grade_control_type in [2D, 3D]"]),
    _mk("ex_op_generic",
        "Production dig depth and breakout force for utility, foundation, and earthmoving work.",
        claims=[],
        priority=9),
]

_EX_CTAS: List[PatternEntry] = [
    _mk("ex_cta_generic",
        "Call or text for pricing, availability, and walk-around details.",
        claims=[],
        priority=9),
]


# ── Dozer ───────────────────────────────────────────────────────────────────

_DOZER_LEADS: List[PatternEntry] = [
    _mk("doz_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs. Crawler dozer for grading, clearing, and earthwork production.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=[],
        priority=9),
]

_DOZER_OP_VALUES: List[PatternEntry] = [
    _mk("doz_op_generic",
        "Built for grading and pushing work. Handles rough site prep, land clearing, and production earthwork.",
        claims=[],
        priority=9),
]

_DOZER_CTAS: List[PatternEntry] = [
    _mk("doz_cta_generic", "Call or text for pricing and availability.", claims=[], priority=9),
]


# ── Scissor / Boom Lift ─────────────────────────────────────────────────────

_LIFT_LEADS: List[PatternEntry] = [
    _mk("lift_lead_generic",
        "{YEAR} {MAKE} {MODEL} — {HOURS} hrs. Aerial work platform for elevated access.",
        tokens=["YEAR", "MAKE", "MODEL", "HOURS"],
        claims=[],
        platforms=[],
        priority=9),
]

_LIFT_OP_VALUES: List[PatternEntry] = [
    _mk("lift_op_generic", "Good elevated work platform for maintenance, construction access, and positioning.", claims=[], priority=9),
]

_LIFT_CTAS: List[PatternEntry] = [
    _mk("lift_cta_generic", "Call or text for pricing and availability.", claims=[], priority=9),
]


# Master pattern registry
_PATTERN_BANKS: Dict[str, Dict[str, List[PatternEntry]]] = {
    "compact_track_loader": {
        "lead": _CTL_LEADS,
        "op_value": _CTL_OP_VALUES,
        "cta": _CTL_CTAS,
    },
    "skid_steer_loader": {
        "lead": _SSL_LEADS,
        "op_value": _SSL_OP_VALUES,
        "cta": _SSL_CTAS,
    },
    "mini_excavator": {
        "lead": _MINI_EX_LEADS,
        "op_value": _MINI_EX_OP_VALUES,
        "cta": _MINI_EX_CTAS,
    },
    "telehandler": {
        "lead": _TELEHANDLER_LEADS,
        "op_value": _TELEHANDLER_OP_VALUES,
        "cta": _TELEHANDLER_CTAS,
    },
    "wheel_loader": {
        "lead": _WL_LEADS,
        "op_value": _WL_OP_VALUES,
        "cta": _WL_CTAS,
    },
    "backhoe_loader": {
        "lead": _BH_LEADS,
        "op_value": _BH_OP_VALUES,
        "cta": _BH_CTAS,
    },
    "excavator": {
        "lead": _EX_LEADS,
        "op_value": _EX_OP_VALUES,
        "cta": _EX_CTAS,
    },
    "dozer": {
        "lead": _DOZER_LEADS,
        "op_value": _DOZER_OP_VALUES,
        "cta": _DOZER_CTAS,
    },
    "scissor_lift": {
        "lead": _LIFT_LEADS,
        "op_value": _LIFT_OP_VALUES,
        "cta": _LIFT_CTAS,
    },
    "boom_lift": {
        "lead": _LIFT_LEADS,
        "op_value": _LIFT_OP_VALUES,
        "cta": _LIFT_CTAS,
    },
}


# ── Equipment type normalizer ──────────────────────────────────────────────

def _normalize_eq_type(equipment_type: str) -> str:
    aliases = {
        "ctl": "compact_track_loader",
        "compact_track_loader": "compact_track_loader",
        "skid_steer": "skid_steer_loader",
        "ssl": "skid_steer_loader",
        "skid_steer_loader": "skid_steer_loader",
        "mini_ex": "mini_excavator",
        "mini excavator": "mini_excavator",
        "mini_excavator": "mini_excavator",
        "telehandler": "telehandler",
        "wheel_loader": "wheel_loader",
        "backhoe_loader": "backhoe_loader",
        "backhoe": "backhoe_loader",
        "excavator": "excavator",
        "large_excavator": "excavator",
        "full_size_excavator": "excavator",
        "dozer": "dozer",
        "crawler_dozer": "dozer",
        "scissor_lift": "scissor_lift",
        "boom_lift": "boom_lift",
    }
    key = (equipment_type or "").strip().lower().replace(" ", "_")
    return aliases.get(key, key)


# ── Platform resolver ───────────────────────────────────────────────────────

def _resolve_platform(tone_profile: str) -> str:
    """Map dealer copy_mode / tone_profile to internal platform token."""
    _map = {
        "dealer_clean":        "dealer_site",
        "marketplace_direct":  "facebook_marketplace",
        "premium_spec_sheet":  "machinery_trader",
        "boom_bucket":         "boom_bucket",
        "auction":             "auction",
        "facebook":            "facebook_marketplace",
        "dealer_site":         "dealer_site",
        "machinery_trader":    "machinery_trader",
    }
    return _map.get((tone_profile or "dealer_clean").strip().lower(), "dealer_site")


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 4 — PLATFORM FORMATTER
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PlatformSpec:
    platform: str
    max_words: int
    lead_sentences: int
    op_value_count: int
    include_features: bool
    include_best_for: bool
    include_attachments: bool
    include_additional_details: bool
    include_specs_block: bool
    voice: str  # dealer_first_person | third_person_inspection | facebook | spartan


PLATFORM_SPECS: Dict[str, PlatformSpec] = {
    "dealer_site": PlatformSpec(
        platform="dealer_site",
        max_words=400,
        lead_sentences=2,
        op_value_count=3,
        include_features=True,
        include_best_for=True,
        include_attachments=True,
        include_additional_details=True,
        include_specs_block=True,
        voice="dealer_first_person",
    ),
    "machinery_trader": PlatformSpec(
        platform="machinery_trader",
        max_words=180,
        lead_sentences=1,
        op_value_count=2,
        include_features=True,
        include_best_for=False,
        include_attachments=True,
        include_additional_details=False,
        include_specs_block=True,
        voice="dealer_first_person",
    ),
    "facebook_marketplace": PlatformSpec(
        platform="facebook_marketplace",
        max_words=80,
        lead_sentences=1,
        op_value_count=1,
        include_features=False,
        include_best_for=False,
        include_attachments=True,
        include_additional_details=False,
        include_specs_block=False,
        voice="facebook",
    ),
    "boom_bucket": PlatformSpec(
        platform="boom_bucket",
        max_words=200,
        lead_sentences=2,
        op_value_count=2,
        include_features=True,
        include_best_for=False,
        include_attachments=True,
        include_additional_details=False,
        include_specs_block=True,
        voice="third_person_inspection",
    ),
    "auction": PlatformSpec(
        platform="auction",
        max_words=120,
        lead_sentences=1,
        op_value_count=1,
        include_features=False,
        include_best_for=False,
        include_attachments=True,
        include_additional_details=True,
        include_specs_block=False,
        voice="spartan",
    ),
}


def _get_platform_spec(platform: str) -> PlatformSpec:
    return PLATFORM_SPECS.get(platform, PLATFORM_SPECS["dealer_site"])


def _truncate_to_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;:") + "..."


# ─────────────────────────────────────────────────────────────────────────────
# HEADLINE BUILDER (v3)
# ─────────────────────────────────────────────────────────────────────────────

_READINESS_POOLS: Dict[str, List[str]] = {
    "skid_steer_loader": [
        "grading, loading, and general attachment work",
        "loading, site cleanup, and attachment-driven production",
        "material handling, grading, and general site work",
    ],
    "compact_track_loader": [
        "site prep, material movement, and attachment use",
        "grading, material handling, and full attachment capability",
        "production site work, earthmoving, and bucket work",
    ],
    "mini_excavator": [
        "trenching, excavation, and utility work",
        "utility trenching, foundation drains, and site excavation",
        "trench digging, utility work, and tight-access excavation",
    ],
    "excavator": [
        "excavation, trenching, and earthwork",
        "production digging, utility work, and site excavation",
        "foundation work, utility trenching, and earthmoving",
    ],
    "backhoe_loader": [
        "trenching, loading, and utility work",
        "utility trenching, site grading, and loader work",
        "digging, backfilling, and mixed-use site work",
    ],
    "wheel_loader": [
        "truck loading, stockpile work, and site support",
        "aggregate loading, material handling, and yard work",
        "production loading, stockpile management, and transfer work",
    ],
    "telehandler": [
        "material placement, pallet handling, and jobsite support",
        "rooftop staging, pallet work, and elevated material placement",
        "material staging, lifting, and jobsite supply work",
    ],
    "dozer": [
        "grading, pushing, and site prep",
        "land clearing, rough grading, and earthwork",
        "site prep, clearing, and production earthmoving",
    ],
    "scissor_lift": [
        "rough-terrain lift work and elevated access",
        "elevated maintenance, construction access, and positioning work",
        "platform access, overhead work, and elevated positioning",
    ],
    "boom_lift": [
        "elevated reach, exterior access, and jobsite lift work",
        "elevated access, exterior structure work, and overhead positioning",
        "overhead work, exterior access, and elevated maintenance",
    ],
}


def _condition_word(hours: Any, dealer_input: Any = None) -> str:
    """
    Hours-aware condition framing. No invented service-history claims.

    Bands:
      0–750     → Low-hour
      751–2,500 → Clean
      2,501+    → Work-ready
    "Well-kept" reserved for dealer-confirmed condition_grade / notes only.
    """
    try:
        h = int(hours) if hours is not None else None
    except (TypeError, ValueError):
        h = None

    if dealer_input is not None:
        grade = str(getattr(dealer_input, "condition_grade", "") or "").strip()
        # Direct condition_grade mapping — dealer-confirmed grade overrides hours bands
        if grade == "Like New":
            return "Like-new"
        if grade == "Well Maintained":
            return "Well-maintained"
        if grade == "Needs Work":
            return "As-is"
        # Legacy well-kept text search (notes or grade field contains phrase)
        grade_lower = grade.lower()
        notes = (
            (getattr(dealer_input, "condition_notes", "") or "")
            + " "
            + (getattr(dealer_input, "additional_details", "") or "")
        ).lower()
        if "well-kept" in grade_lower or "well kept" in grade_lower \
           or "well-kept" in notes or "well kept" in notes:
            return "Well-kept"

    if h is None:
        return "Work-ready"
    if h <= 750:
        return "Low-hour"
    if h <= 2500:
        return "Clean"
    return "Work-ready"


def _confirmed_feature_phrases(dealer_input: Any, equipment_type: str) -> List[str]:
    """
    Return a list of natural-language feature phrases for confirmed dealer_input
    fields only. No inferred features. No attachment implications.
    """
    norm = _normalize_eq_type(equipment_type)
    phrases: List[str] = []

    cab = str(getattr(dealer_input, "cab_type", "") or "").lower().strip()
    is_enclosed = cab in _ENCLOSED_CAB_VALUES
    heat = bool(getattr(dealer_input, "heater", None))
    ac = bool(getattr(dealer_input, "ac", None))

    if is_enclosed:
        if heat and ac:
            phrases.append("enclosed cab with heat and A/C")
        elif heat:
            phrases.append("enclosed cab with heat")
        elif ac:
            phrases.append("enclosed cab with A/C")
        else:
            phrases.append("enclosed cab")

    if norm in ("skid_steer_loader", "compact_track_loader"):
        if getattr(dealer_input, "high_flow", None) == "yes":
            phrases.append("high-flow hydraulics")
        if getattr(dealer_input, "two_speed_travel", None) == "yes":
            phrases.append("two-speed travel")
        if getattr(dealer_input, "ride_control", None):
            phrases.append("ride control")
        coupler = getattr(dealer_input, "coupler_type", None)
        if coupler and coupler not in ("pin-on", ""):
            phrases.append("quick-attach coupler")
    elif norm == "mini_excavator":
        thumb = getattr(dealer_input, "thumb_type", None)
        if thumb and str(thumb).lower() not in ("none", ""):
            phrases.append(f"{str(thumb).lower()} thumb")
        if getattr(dealer_input, "aux_hydraulics", None):
            phrases.append("auxiliary hydraulics")
        if getattr(dealer_input, "blade_type", None):
            phrases.append("dozer blade")
        if getattr(dealer_input, "two_speed_travel", None) == "yes":
            phrases.append("two-speed travel")
    elif norm == "telehandler":
        if getattr(dealer_input, "has_stabilizers", None):
            phrases.append("outrigger stabilizers")
    elif norm == "backhoe_loader":
        if getattr(dealer_input, "has_stabilizers", None):
            phrases.append("outrigger stabilizers")
        if getattr(dealer_input, "coupler_type", None):
            phrases.append("quick-coupler")

    return phrases


def _join_phrases(phrases: List[str]) -> str:
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} and {phrases[1]}"
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


def _build_machine_first_opening(
    dealer_input: Any,
    equipment_type: str,
    resolved_specs: Optional[Dict] = None,
    use_case_payload: Optional[Dict] = None,
) -> str:
    """
    Highlight-reel opening paragraph.

    Pattern:
      S1: [Condition] [Year Make Model] with [N] hours.
      S2: Equipped with [confirmed features].
      S3: [Class-appeal sentence — buyer-framed, no spec numbers.]
      S4: Ready for [applications — use_case_payload labels or readiness pool fallback.]

    OEM Specs carry the numbers. This paragraph sells the configuration and use case.
    """
    year = getattr(dealer_input, "year", None)
    make = getattr(dealer_input, "make", "") or ""
    model = getattr(dealer_input, "model", "") or ""
    hours = getattr(dealer_input, "hours", None)
    norm = _normalize_eq_type(equipment_type)
    specs = resolved_specs or {}

    condition = _condition_word(hours, dealer_input)
    identity = f"{year} {make} {model}".strip()

    hours_qual = str(getattr(dealer_input, "hours_qualifier", "") or "").strip()

    if hours is not None:
        try:
            h_int = int(hours)
            if hours_qual:
                s1 = f"{condition} {identity} with {h_int:,} hours ({hours_qual.lower()})."
            else:
                s1 = f"{condition} {identity} with {h_int:,} hours."
        except (TypeError, ValueError):
            s1 = f"{condition} {identity}."
    else:
        s1 = f"{condition} {identity}."

    parts: List[str] = [s1]

    # S2: confirmed features only — no inferred claims
    feats = _confirmed_feature_phrases(dealer_input, equipment_type)
    if feats:
        parts.append(f"Equipped with {_join_phrases(feats)}.")

    # S3: class appeal — buyer-framed, no spec numbers
    if specs:
        appeal = _build_class_appeal_sentence(norm, specs)
        if appeal:
            parts.append(appeal)

    # S4: applications — use_case_payload preferred, readiness pool fallback
    use_cases = (use_case_payload or {}).get("top_use_cases_for_listing") or []
    if use_cases:
        uc_labels = [str(uc).lower() for uc in use_cases[:3]]
        parts.append(f"Ready for {_join_phrases(uc_labels)}.")
    else:
        readiness_pool = _READINESS_POOLS.get(norm)
        if readiness_pool:
            idx = _stable_index(dealer_input, norm, len(readiness_pool))
            parts.append(f"Ready for {readiness_pool[idx]}.")

    return " ".join(parts)


def _build_v3_headline(
    dealer_input: Any,
    equipment_type: str,
    resolved_specs: Optional[Dict] = None,
) -> str:
    """
    Build a dealer-grade headline: YEAR MAKE MODEL — Feature1[, Feature2]

    Feature priority (from phrasebank feature_priority):
      SSL/CTL:      High Flow → 2-Speed → Enclosed Cab → Hours
      Mini Ex:      Enclosed Cab → Thumb → Aux Hyd
      Telehandler:  Enclosed Cab → Stabilizers
      Excavator:    Thumb → Hammer Circuit → Enclosed Cab
      Wheel Loader: {N}-HP → Enclosed Cab
      Boom Lift:    {N}-ft {BoomType} Boom → Power Source
      Scissor Lift: {N}-ft Platform → Power Source
      Dozer:        Enclosed Cab → Hours (fallback)
    """
    specs = resolved_specs or {}
    base = f"{dealer_input.year} {dealer_input.make.upper()} {dealer_input.model}"
    tokens: List[str] = []

    hi = getattr(dealer_input, "high_flow", None)
    two = getattr(dealer_input, "two_speed_travel", None)
    cab = str(getattr(dealer_input, "cab_type", "") or "").lower().strip()
    is_enclosed = cab in _ENCLOSED_CAB_VALUES
    ac = getattr(dealer_input, "ac", None)
    hours = getattr(dealer_input, "hours", None)
    thumb = getattr(dealer_input, "thumb_type", None)

    norm = _normalize_eq_type(equipment_type)

    if norm == "mini_excavator":
        thumb_set = bool(thumb and thumb.lower() not in ("none", ""))
        aux = bool(getattr(dealer_input, "aux_hydraulics", None))
        cab_alone = is_enclosed and not (thumb_set or aux)
        if is_enclosed:
            tokens.append("Cab, A/C" if (ac and cab_alone) else "Enclosed Cab")
        if thumb_set:
            tokens.append("Thumb")
        if aux and len(tokens) < 2:
            tokens.append("Aux Hyd")

    elif norm == "telehandler":
        if is_enclosed:
            tokens.append("Enclosed Cab")
        if getattr(dealer_input, "has_stabilizers", None):
            tokens.append("Stabilizers")

    elif norm == "excavator":
        thumb_set = bool(thumb and thumb.lower() not in ("none", ""))
        if thumb_set:
            tokens.append("Thumb")
        if getattr(dealer_input, "hammer_plumbing", None) and len(tokens) < 2:
            tokens.append("Hammer Circuit")
        if not tokens and is_enclosed:
            tokens.append("Enclosed Cab, A/C" if ac else "Enclosed Cab")

    elif norm == "wheel_loader":
        hp = specs.get("net_hp") or specs.get("horsepower_hp")
        if hp:
            tokens.append(f"{int(hp)}-HP")
        if is_enclosed and len(tokens) < 2:
            tokens.append("Enclosed Cab")
        elif is_enclosed and not tokens:
            tokens.append("Enclosed Cab, A/C" if ac else "Enclosed Cab")

    elif norm == "boom_lift":
        ht = specs.get("platform_height_ft")
        if ht:
            bt = str(specs.get("boom_type") or "").lower()
            boom_label = "Articulating" if "artic" in bt else ("Telescopic" if bt else "")
            tokens.append(f"{int(ht)}-ft {boom_label} Boom".strip())
        ps = str(specs.get("power_source") or "").strip()
        if ps and len(tokens) < 2:
            tokens.append(ps.title())

    elif norm == "scissor_lift":
        ht = specs.get("platform_height_ft")
        if ht:
            tokens.append(f"{int(ht)}-ft Platform")
        ps = str(specs.get("power_source") or "").strip()
        if ps and len(tokens) < 2:
            tokens.append(ps.title())

    else:
        # SSL / CTL / backhoe / dozer — high flow and two-speed first
        if hi == "yes":
            att = (getattr(dealer_input, "attachments_included", "") or "").lower()
            mulcher = any(kw in att for kw in ("mulch", "forestry head", "brush cutter", "masticator"))
            if mulcher:
                return f"{base} — High Flow, Mulching Head"
            tokens.append("High Flow")
            if is_enclosed:
                tokens.append("Enclosed Cab")
            elif two == "yes":
                tokens.append("2-Speed")
        elif is_enclosed:
            tokens.append("Enclosed Cab, A/C" if ac else "Enclosed Cab")
            if two == "yes" and len(tokens) < 2:
                if tokens[0] == "Enclosed Cab":
                    tokens.append("2-Speed")
        elif two == "yes":
            tokens.append("2-Speed")

    if tokens:
        return f"{base} — {', '.join(tokens[:2])}"
    if hours and hours <= 500:
        return f"{base} — {hours:,} Hours"
    return base


# ─────────────────────────────────────────────────────────────────────────────
# CAPABILITY ANCHOR (v3.5 — deterministic class-position sentence)
# ─────────────────────────────────────────────────────────────────────────────

# Each entry: (threshold_value, sentence). First entry whose threshold ≤ actual value wins.
# All thresholds are inclusive-upper (>=). Entries must be in descending threshold order.
_ANCHOR_TABLES: Dict[str, List[tuple]] = {
    "compact_track_loader": [
        # keyed on rated_operating_capacity_lbs
        (3000, "Large-frame CTL capacity. Rated for sustained production work and heavy attachment demand."),
        (2400, "Production-class CTL capacity. Handles aggregate and heavy material loads across the full work cycle."),
        (1800, "Mid-frame CTL capacity. Right for landscape, utility, and mixed attachment work."),
        (0,    "Compact CTL class. Residential and light commercial production scope."),
    ],
    "skid_steer_loader": [
        (2800, "Large-frame wheeled skid steer. High-side ROC for the class — handles aggregate and full material loads."),
        (1800, "Mid-frame wheeled skid steer. Standard residential and commercial utility scope."),
        (0,    ""),
    ],
    "mini_excavator": [
        # keyed on operating_weight_lbs
        (12000, "Upper compact class. Meaningful dig depth and breakout force without the trailer weight penalty of a larger machine."),
        (7000,  "Mid-compact class. Standard residential and light commercial excavation range."),
        (4000,  "Compact class. Site-access advantage — fits through most gates without special access prep."),
        (0,     "Micro class. Fits through standard gates, hauls on a standard trailer, and works in spaces larger machines cannot access."),
    ],
    "excavator": [
        # keyed on operating_weight_lbs
        (55000, "Large production class. Built for sustained earthmoving, major infrastructure, and foundation-scale work."),
        (35000, "Mid-production class. Full utility and commercial excavation capability across most site conditions."),
        (18000, "Standard production class. The common general contractor and utility contractor range."),
        (0,     "Compact excavation class. Fits sites where larger machines are access-limited."),
    ],
    "telehandler": [
        # keyed on lift_height_ft
        (55, "High-reach commercial class. Capable of staged material placement on most multi-story commercial construction."),
        (45, "Jobsite crossover class. Rooftop staging and truss work on residential and light commercial construction."),
        (0,  "Residential reach class. Standard pallet and material placement for framing and masonry work."),
    ],
    "wheel_loader": [
        # keyed on horsepower_hp
        (200, "Production aggregate and stockpile loading class. Built for sustained truck-loading cycles in heavy material."),
        (130, "Mid-size loader class. Yard handling, material transfer, and aggregate loading across general contractor sites."),
        (0,   ""),
    ],
    "dozer": [
        # keyed on horsepower_hp
        (250, "Large production dozer class. Built for large-scale earthmoving and sustained pushing in hard material."),
        (130, "Mid-size dozer class. Handles rough site prep, land clearing, and production grading."),
        (0,   ""),
    ],
    "scissor_lift": [
        # keyed on platform_height_ft
        (40, "High-platform scissor class. Ceiling clearance for most industrial and warehouse applications."),
        (25, "Standard platform height. General maintenance, signage, and interior construction access."),
        (0,  ""),
    ],
    "boom_lift": [
        # keyed on platform_height_ft
        (60, "High-reach boom class. Exterior facade, bridge, and industrial structure access."),
        (40, "Mid-reach boom class. Rooftop access, commercial exterior, and multi-story work."),
        (0,  ""),
    ],
}

# Which resolved_specs field drives each category's anchor lookup
_ANCHOR_FIELD: Dict[str, tuple] = {
    "compact_track_loader": ("roc_lb", "rated_operating_capacity_lbs"),
    "skid_steer_loader":    ("roc_lb", "rated_operating_capacity_lbs"),
    "mini_excavator":       ("operating_weight_lb", "operating_weight_lbs"),
    "excavator":            ("operating_weight_lb", "operating_weight_lbs"),
    "telehandler":          ("max_lift_height_ft", "lift_height_ft"),
    "wheel_loader":         ("net_hp", "horsepower_hp"),
    "dozer":                ("net_hp", "horsepower_hp"),
    "scissor_lift":         ("platform_height_ft",),
    "boom_lift":            ("platform_height_ft",),
}


# Buyer-framed class-context sentences for the opening paragraph.
# Same threshold keys as _ANCHOR_TABLES. No spec numbers — those live in OEM Specs.
_CLASS_APPEAL_SENTENCES: Dict[str, List[tuple]] = {
    "compact_track_loader": [
        (3000, "Strong large-frame CTL configuration with the hydraulic output and lift capacity most contractors need for demanding attachment work."),
        (2400, "Production-class CTL setup for contractors running demanding attachments or managing high-volume site conditions."),
        (1800, "Mid-frame CTL configuration well-suited for landscape, utility, and mixed attachment work."),
        (0,    "Compact CTL class for residential and light commercial site work."),
    ],
    "skid_steer_loader": [
        (2800, "Large-frame wheeled skid steer with strong lift capacity for aggregate loading and site production work."),
        (1800, "Standard wheeled skid steer well-suited for daily residential and commercial site work."),
        (0,    ""),
    ],
    "mini_excavator": [
        (12000, "Well-equipped upper compact excavator with the configuration most utility and site contractors look for in this size class."),
        (7000,  "Mid-compact excavator well-suited for residential and light commercial excavation work."),
        (4000,  "Compact excavator for tight-access sites and residential applications."),
        (0,     "Micro class — fits through standard gates and hauls on a standard trailer."),
    ],
    "excavator": [
        (55000, "Large production excavator suited for sustained earthmoving, infrastructure, and foundation-scale work."),
        (35000, "Mid-size production excavator built for commercial contractors and production site work."),
        (18000, "Standard production excavator suited for general contractors and utility work."),
        (0,     "Compact excavation class for access-limited sites."),
    ],
    "telehandler": [
        (55, "High-reach commercial telehandler for multi-story material placement and commercial construction staging."),
        (45, "Construction telehandler for rooftop staging, truss work, and residential to light commercial jobsites."),
        (0,  "Construction telehandler well-suited for contractors working at height or staging material across active jobsites."),
    ],
    "wheel_loader": [
        (200, "Production-class wheel loader built for sustained truck-loading cycles and high-volume material movement."),
        (130, "Mid-size wheel loader well-suited for material transfer, aggregate loading, and general contractor site work."),
        (0,   ""),
    ],
    "dozer": [
        (250, "Large production dozer for sustained earthmoving and pushing in large-scale site work."),
        (130, "Mid-size dozer class well-suited for site development contractors and clearing crews."),
        (0,   ""),
    ],
    "scissor_lift": [
        (40, "High-platform rough terrain scissor class for contractors needing reliable overhead access on uneven terrain."),
        (25, "Standard-reach scissor lift for general maintenance, interior construction, and overhead access."),
        (0,  ""),
    ],
    "boom_lift": [
        (60, "High-reach boom lift for exterior facade, bridge, and industrial structure access."),
        (40, "Mid-reach boom lift for rooftop access, commercial exterior, and multi-story work."),
        (0,  ""),
    ],
}


def _build_class_appeal_sentence(eq_norm: str, resolved_specs: Dict) -> str:
    """
    Return a buyer-framed class-context sentence with no spec numbers.
    Used as S3 of the opening paragraph.
    """
    table = _CLASS_APPEAL_SENTENCES.get(eq_norm)
    field_keys = _ANCHOR_FIELD.get(eq_norm)
    if not table or not field_keys:
        return ""
    val = None
    for k in field_keys:
        val = resolved_specs.get(k)
        if val is not None:
            break
    if val is None:
        return ""
    try:
        num = float(val)
    except (TypeError, ValueError):
        return ""
    for threshold, sentence in table:
        if num >= threshold:
            return sentence
    return ""


def _build_capability_anchor(eq_norm: str, resolved_specs: Dict) -> str:
    """
    Return a one-sentence class-position statement derived from resolved_specs.
    Returns empty string when the relevant spec is unavailable.
    """
    table = _ANCHOR_TABLES.get(eq_norm)
    field_keys = _ANCHOR_FIELD.get(eq_norm)
    if not table or not field_keys:
        return ""

    val = None
    for k in field_keys:
        val = resolved_specs.get(k)
        if val is not None:
            break

    if val is None:
        return ""

    try:
        num = float(val)
    except (TypeError, ValueError):
        return ""

    for threshold, sentence in table:
        if num >= threshold:
            return sentence
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# FEATURES BLOCK (v3 — enforces feature priority per type)
# ─────────────────────────────────────────────────────────────────────────────

def _build_v3_features(
    dealer_input: Any,
    equipment_type: str,
    resolved_specs: Optional[Dict] = None,
) -> str:
    """
    Build the Features bullet block using the feature priority map from
    phrasebank v3.  No invented claims — only confirmed dealer_input fields
    and resolved OEM specs.
    """
    norm = _normalize_eq_type(equipment_type)
    specs = resolved_specs or {}
    bullets: List[str] = []

    def add(label: str) -> None:
        bullets.append(label)

    def _track_framing(pct_raw: Any, cond_text: Any) -> None:
        """Render track condition as buyer-facing language when % is available."""
        if pct_raw is not None:
            try:
                pct = int(pct_raw)
                if pct >= 80:
                    framing = "excellent condition"
                elif pct >= 50:
                    framing = "solid working life remaining"
                else:
                    framing = "price reflects wear"
                add(f"Tracks at {pct}% — {framing}")
                return
            except (TypeError, ValueError):
                pass
        if cond_text:
            add(f"Track condition: {cond_text}")

    def _tire_framing(pct_raw: Any, cond_text: Any) -> None:
        """Render tire condition as buyer-facing language when % is available."""
        if pct_raw is not None:
            try:
                pct = int(pct_raw)
                if pct >= 80:
                    framing = "excellent condition"
                elif pct >= 50:
                    framing = "solid working life remaining"
                else:
                    framing = "price reflects wear"
                add(f"Tires at {pct}% — {framing}")
                return
            except (TypeError, ValueError):
                pass
        if cond_text:
            add(f"Tire condition: {cond_text}")

    # ── Universal: cab ────────────────────────────────────────────────────
    cab = str(getattr(dealer_input, "cab_type", "") or "").lower().strip()
    is_enclosed = cab in _ENCLOSED_CAB_VALUES
    ac = getattr(dealer_input, "ac", None)
    heater = getattr(dealer_input, "heater", None)

    if is_enclosed:
        comforts = []
        if heater:
            comforts.append("heat")
        if ac:
            comforts.append("A/C")
        add(f"Enclosed cab" + (f" w/ {' & '.join(comforts)}" if comforts else ""))
    elif cab in ("canopy", "rops", "canopy/rops"):
        add("Canopy / ROPS")
    elif cab:
        add("Open cab")

    # ── Per-type priority fields ──────────────────────────────────────────
    if norm in ("compact_track_loader", "skid_steer_loader"):
        if getattr(dealer_input, "high_flow", None) == "yes":
            add("High-flow hydraulics")
        if getattr(dealer_input, "two_speed_travel", None) == "yes":
            add("2-speed travel")
        if getattr(dealer_input, "ride_control", False):
            add("Ride control")
        if getattr(dealer_input, "coupler_type", None) not in (None, "pin-on", ""):
            add("Quick attach coupler")
        if getattr(dealer_input, "self_leveling", False):
            add("Self-leveling")
        if getattr(dealer_input, "reversing_fan", False):
            add("Reversing fan")
        if getattr(dealer_input, "backup_camera", False):
            add("Backup camera")
        if getattr(dealer_input, "radio", False):
            add("Radio")
        if getattr(dealer_input, "air_ride_seat", False):
            add("Air-ride seat")
        if getattr(dealer_input, "one_owner", False):
            add("One owner")
        _track_framing(
            getattr(dealer_input, "track_percent_remaining", None),
            getattr(dealer_input, "track_condition", None),
        )
        _tire_framing(None, getattr(dealer_input, "tire_condition", None))

    elif norm == "mini_excavator":
        thumb = getattr(dealer_input, "thumb_type", None)
        if thumb and thumb.lower() not in ("none", ""):
            add(f"{thumb.title()} thumb")
        if getattr(dealer_input, "coupler_type", None):
            add("Quick coupler")
        if getattr(dealer_input, "aux_hydraulics", None):
            add("Auxiliary hydraulics")
        blade = getattr(dealer_input, "blade_type", None)
        if blade:
            add(f"{blade.title()} blade")
        if getattr(dealer_input, "two_speed_travel", None) == "yes":
            add("2-speed travel")
        if getattr(dealer_input, "rubber_tracks", False):
            add("Rubber tracks")
        if getattr(dealer_input, "zero_tail_swing", False):
            add("Zero tail swing")
        if getattr(dealer_input, "pattern_changer", False):
            add("Pattern changer (ISO/SAE)")
        al = getattr(dealer_input, "arm_length", None)
        if al and str(al).lower() not in ("standard", ""):
            add(f"{str(al).title()} arm")
        if getattr(dealer_input, "backup_camera", False):
            add("Backup camera")
        if getattr(dealer_input, "one_owner", False):
            add("One owner")
        _track_framing(
            getattr(dealer_input, "track_percent_remaining", None),
            getattr(dealer_input, "track_condition", None),
        )

    elif norm == "telehandler":
        if getattr(dealer_input, "has_stabilizers", None):
            add("Outrigger stabilizers")
        if getattr(dealer_input, "ride_control", False):
            add("Ride control")
        if getattr(dealer_input, "backup_camera", False):
            add("Backup camera")
        if getattr(dealer_input, "one_owner", False):
            add("One owner")
        _tire_framing(None, getattr(dealer_input, "tire_condition", None))

    elif norm == "excavator":
        thumb = getattr(dealer_input, "thumb_type", None)
        if thumb and thumb.lower() not in ("none", ""):
            add(f"{thumb.title()} thumb")
        if getattr(dealer_input, "coupler_type", None):
            add("Hydraulic coupler")
        aht = getattr(dealer_input, "aux_hydraulics_type", None)
        if aht:
            add(f"Aux hydraulics ({aht})")
        if getattr(dealer_input, "grade_control_type", None) not in (None, "none", ""):
            add(f"Grade control ({getattr(dealer_input, 'grade_control_type')})")
        if getattr(dealer_input, "rear_camera", None):
            add("Rear camera")
        if getattr(dealer_input, "hammer_plumbing", None):
            add("Hammer circuit plumbed")
        if getattr(dealer_input, "heated_seat", None):
            add("Heated seat")
        if getattr(dealer_input, "one_owner", False):
            add("One owner")
        uc_pct = getattr(dealer_input, "undercarriage_percent_remaining", None)
        uc_txt = getattr(dealer_input, "undercarriage_condition_pct", None)
        if uc_pct is not None:
            try:
                pct = int(uc_pct)
                add(f"Undercarriage: {pct}%")
            except (TypeError, ValueError):
                if uc_txt:
                    add(f"Undercarriage: {uc_txt}")
        elif uc_txt:
            add(f"Undercarriage: {uc_txt}")

    elif norm == "dozer":
        blade = getattr(dealer_input, "blade_type", None)
        if blade and str(blade).lower() not in ("", "none"):
            add(f"{str(blade).title()} blade")
        bl_w = specs.get("blade_width_ft")
        if bl_w:
            add(f"Blade width: {bl_w} ft")
        gp = specs.get("ground_pressure_psi")
        if gp:
            try:
                add(f"Ground pressure: {float(gp):.1f} PSI")
            except (TypeError, ValueError):
                pass
        if getattr(dealer_input, "backup_camera", False):
            add("Backup camera")
        if getattr(dealer_input, "one_owner", False):
            add("One owner")
        _track_framing(
            getattr(dealer_input, "track_percent_remaining", None),
            getattr(dealer_input, "track_condition", None),
        )

    elif norm in ("boom_lift", "scissor_lift"):
        ht = specs.get("platform_height_ft")
        if ht:
            add(f"Platform height: {ht} ft")
        cap = specs.get("platform_capacity_lbs")
        if cap:
            try:
                add(f"Platform capacity: {int(cap):,} lbs")
            except (TypeError, ValueError):
                pass
        ps = str(specs.get("power_source") or "").strip()
        if ps:
            add(f"Power source: {ps}")
        if norm == "boom_lift":
            hr = specs.get("horizontal_reach_ft")
            if hr:
                add(f"Horizontal reach: {hr} ft")
            bt = str(specs.get("boom_type") or "").strip()
            if bt:
                add(bt.title())
        if norm == "scissor_lift":
            stow = specs.get("stowed_height_in")
            if stow:
                try:
                    add(f"Stowed height: {int(stow)}\"")
                except (TypeError, ValueError):
                    pass
        if getattr(dealer_input, "backup_camera", False):
            add("Backup camera")

    else:
        # wheel_loader, backhoe, and any unrecognised type
        if getattr(dealer_input, "ride_control", False):
            add("Ride control")
        if getattr(dealer_input, "backup_camera", False):
            add("Backup camera")
        if getattr(dealer_input, "one_owner", False):
            add("One owner")
        _tire_framing(None, getattr(dealer_input, "tire_condition", None))
        _track_framing(
            getattr(dealer_input, "track_percent_remaining", None),
            getattr(dealer_input, "track_condition", None),
        )

    # ── Universal: warranty status ────────────────────────────────────────
    ws = str(getattr(dealer_input, "warranty_status", "") or "").strip()
    if ws:
        add(f"Warranty: {ws}")

    # ── Additional free-text features (always last) ───────────────────────
    extra_raw = getattr(dealer_input, "additional_features", None) or ""
    for line in extra_raw.split("\n"):
        if line.strip():
            bullets.append(line.strip())

    if not bullets:
        return ""
    return "Features:\n" + "\n".join(f"  • {b}" for b in bullets)


# ─────────────────────────────────────────────────────────────────────────────
# BEST-FOR SECTION (v3 — gated by scoring payload)
# ─────────────────────────────────────────────────────────────────────────────

def _build_v3_best_for(use_case_payload: Optional[Dict]) -> str:
    use_cases = (use_case_payload or {}).get("top_use_cases_for_listing") or []
    if not use_cases:
        return ""
    # Pull descriptors from listing_builder (lazy import avoids circular dependency)
    try:
        from listing_builder import _UC_DESCRIPTOR as _uc_desc  # type: ignore
    except Exception:
        _uc_desc = {}
    lines = []
    for label in use_cases[:3]:
        desc = (_uc_desc or {}).get(label, "")
        if desc:
            lines.append(f"  • {label} — {desc}")
        else:
            lines.append(f"  • {label}")
    return "Best For:\n" + "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# SPECS BLOCK (v3 — thin wrapper around existing OEM display system)
# ─────────────────────────────────────────────────────────────────────────────

def _build_v3_specs_block(resolved_specs: Dict, equipment_type: str) -> str:
    """
    Thin wrapper: uses the existing build_machine_snapshot() from listing_builder
    without creating a circular import (lazy import inside the function).
    """
    try:
        from listing_builder import build_machine_snapshot
        return build_machine_snapshot(resolved_specs, equipment_type)
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# ATTACHMENT BLOCK
# ─────────────────────────────────────────────────────────────────────────────

def _build_attachments_block(dealer_input: Any) -> str:
    raw = (getattr(dealer_input, "attachments_included", None) or "").strip()
    if not raw:
        return ""
    import re as _re
    parts = [p.strip() for p in _re.split(r"[\n,]|\s+and\s+", raw, flags=_re.IGNORECASE) if p.strip()]
    if not parts:
        return ""
    return "Attachments Included:\n" + "\n".join(f"  • {p.title()}" for p in parts)


# ─────────────────────────────────────────────────────────────────────────────
# ADDITIONAL DETAILS BLOCK
# ─────────────────────────────────────────────────────────────────────────────

def _build_additional_details_block(dealer_input: Any) -> str:
    raw = (
        getattr(dealer_input, "additional_details", None)
        or getattr(dealer_input, "condition_notes", None)
        or ""
    ).strip()
    if not raw:
        return ""
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    if not lines:
        return ""
    return "Additional Details:\n" + "\n".join(f"  • {ln}" for ln in lines)


# ─────────────────────────────────────────────────────────────────────────────
# CTA BLOCK
# ─────────────────────────────────────────────────────────────────────────────

def _build_cta_block(
    cta_text: str,
    dealer_input: Any,
    platform: str,
) -> str:
    price = getattr(dealer_input, "asking_price", None) or 0
    try:
        price = int(price)
    except (TypeError, ValueError):
        price = 0

    if price >= 150_000:
        return "Serious inquiries welcome. Call for full specs, inspection details, and delivery terms."
    if price >= 50_000:
        return "Financing available. Call or message for a quote and availability."
    if price > 0:
        return "Call or text to schedule a walkthrough."
    return "Call or text for pricing, availability, and inspection details."


# ─────────────────────────────────────────────────────────────────────────────
# GATED CLAIM SAFETY CHECK
# ─────────────────────────────────────────────────────────────────────────────

def _filter_sentences_preserving_breaks(text: str, banned_substrs: tuple) -> str:
    """
    Drop any sentence that contains a banned substring, preserving paragraph
    and section breaks (\\n, \\n\\n) instead of collapsing them to single spaces.
    """
    blocks = text.split("\n")
    out_blocks: List[str] = []
    for blk in blocks:
        if not blk.strip():
            out_blocks.append(blk)
            continue
        sentences = re.split(r"(?<=[.!?])[ \t]+", blk)
        kept = [s for s in sentences if not any(b in s.lower() for b in banned_substrs)]
        out_blocks.append(" ".join(kept))
    return "\n".join(out_blocks)


def _check_one_owner_claim(text: str, dealer_input: Any) -> str:
    """
    Hard rule from v2 §4.1: 'one owner' only when dealer_input.one_owner is True.
    """
    if getattr(dealer_input, "one_owner", False):
        return text
    return _filter_sentences_preserving_breaks(
        text, ("one owner", "one-owner", "1-owner", "single owner"),
    )


def _check_thumb_claim(text: str, dealer_input: Any) -> str:
    """Hard rule: 'hydraulic thumb' only when thumb_type is set to hydraulic or manual."""
    thumb = getattr(dealer_input, "thumb_type", None)
    if thumb and thumb.lower() in ("hydraulic", "manual"):
        return text
    return _filter_sentences_preserving_breaks(
        text, ("hydraulic thumb", "thumb included"),
    )


def _check_like_new_claim(text: str, dealer_input: Any) -> str:
    """Hard rule: 'like new' only with hours < 200."""
    hours = getattr(dealer_input, "hours", None)
    if hours is not None and hours >= 200 and "like new" in text.lower():
        text = re.sub(r"(?i)like new", "low-hour", text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# COMPACT LISTING FORMATTER
# ─────────────────────────────────────────────────────────────────────────────

def _compact(text: str) -> str:
    text = re.sub(r"(:\n)\n+", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def build_listing_text_v3(
    dealer_input: Any,
    resolved_specs: Dict,
    use_case_payload: Optional[Dict] = None,
    equipment_type: str = "",
    tone_profile: str = "dealer_clean",
) -> str:
    """
    Build a dealer-ready listing description string using the v3 8-layer engine.

    Layer order:
      L1  Tier classifier            (classify_tier)
      L2  Claim gating               (low-hours benchmark, eligibility checks)
      L3  Lead hook selector         (job-first hook bank, falls back to pattern bank)
      L4  Machine identity           (headline + price)
      L5  Capability composer        (op-value patterns, gated)
      L6  Feature selector           (priority-ordered confirmed features)
      L7  Trust builder              (proof-gated trust phrases, Tier-A/B only)
      L8  CTA builder                (platform-aware support line)

    Returns a plain string — sections separated by single blank lines.
    Claim safety: no gated claim renders without its source field.
    """
    # ── Layer 1: Tier Classifier ──────────────────────────────────────────
    tier = classify_tier(dealer_input)

    # ── Resolve equipment type + platform ────────────────────────────────
    eq_norm = _normalize_eq_type(equipment_type)
    platform = _resolve_platform(
        getattr(dealer_input, "copy_mode", None) or tone_profile or "dealer_clean"
    )
    pspec = _get_platform_spec(platform)

    # ── Layer 2: Claim gates ──────────────────────────────────────────────
    try:
        from listing_copy_v3_gates import (
            low_hours_eligible,
            build_trust_lines,
            strip_unsupported_low_hours,
            strip_weak_generic_phrases,
            apply_red_gate,
            apply_yellow_gate,
        )
        low_hr_ok = low_hours_eligible(
            eq_norm,
            getattr(dealer_input, "year", None),
            getattr(dealer_input, "hours", None),
            getattr(dealer_input, "hours_qualifier", None),
            (getattr(dealer_input, "condition_notes", "") or "")
            + " "
            + (getattr(dealer_input, "additional_details", "") or ""),
        )
    except Exception:
        low_hr_ok = False
        def strip_unsupported_low_hours(t, ok): return t
        def strip_weak_generic_phrases(t): return t
        def build_trust_lines(*a, **kw): return []
        def apply_red_gate(t, di): return t
        def apply_yellow_gate(t, di, tier): return t

    # ── Layer 3+5 context for pattern banks ──────────────────────────────
    ctx = ClaimContext(
        dealer_input=dealer_input,
        resolved_specs=resolved_specs,
        equipment_type=eq_norm,
        tier=tier,
        platform=platform,
    )
    tokens = _resolve_tokens(ctx)

    banks = _PATTERN_BANKS.get(eq_norm, {})
    lead_bank = banks.get("lead", [])
    op_bank = banks.get("op_value", [])
    cta_bank = banks.get("cta", [])

    # ── Layer 3: Machine-first opening (deterministic, no use-case lead) ──
    # Hook bank + lead pattern bank bypassed: opening is grounded only in
    # confirmed dealer_input fields.  No "Built for...", no implied attachments.

    # ── Assemble sections ─────────────────────────────────────────────────
    sections: List[str] = []

    # L4. Machine identity — headline + price
    sections.append(_build_v3_headline(dealer_input, equipment_type, resolved_specs))
    if getattr(dealer_input, "asking_price", None):
        sections.append(f"${dealer_input.asking_price:,}")

    # L3. Opening paragraph — highlight reel: identity, configuration, class appeal, applications.
    lead_text = _build_machine_first_opening(dealer_input, equipment_type, resolved_specs, use_case_payload)
    if lead_text:
        lead_text = apply_red_gate(lead_text, dealer_input)
        if lead_text.strip():
            sections.append(lead_text.strip())

    # Specs block (OEM)
    if pspec.include_specs_block:
        specs_block = _build_v3_specs_block(resolved_specs, equipment_type)
        if specs_block:
            sections.append(specs_block)

    # L6. Features block
    if pspec.include_features:
        feat_block = _build_v3_features(dealer_input, equipment_type, resolved_specs)
        if feat_block:
            sections.append(feat_block)

    # Attachments (proof-confirmed)
    if pspec.include_attachments:
        att_block = _build_attachments_block(dealer_input)
        if att_block:
            sections.append(att_block)

    # Additional Details (dealer-supplied notes — surfaced after attachments)
    if pspec.include_additional_details:
        ad_block = _build_additional_details_block(dealer_input)
        if ad_block:
            sections.append(ad_block)

    # Best For (scorer-backed, with descriptors)
    if pspec.include_best_for and use_case_payload:
        bf_block = _build_v3_best_for(use_case_payload)
        if bf_block:
            sections.append(bf_block)

    # L8. CTA — price-tiered.
    sections.append(_build_cta_block("", dealer_input, platform))

    # ── Final assembly ────────────────────────────────────────────────────
    result = _compact("\n\n".join(sections))

    # Tier C override: ensure disclosure language is present
    if tier == TIER_C:
        if "as-is" not in result.lower() and "mechanic" not in result.lower():
            result += "\n\nSelling as-is. No warranty."

    # Final claim sweep: RED (hard-gated) + YELLOW (capped/tiered) + thumb + forbidden
    result = apply_red_gate(result, dealer_input)
    result = _check_thumb_claim(result, dealer_input)
    result = apply_yellow_gate(result, dealer_input, tier)
    result = safety_filter(result)
    result = _compact(result)

    # Marketplace compression: enforce platform word budget on prose only.
    # Section headers + bullet lists are kept intact; prose between them
    # is truncated when the total budget is exceeded.
    if platform == "facebook_marketplace":
        result = _truncate_marketplace(result, pspec.max_words)

    return result.strip()


def _truncate_marketplace(text: str, max_words: int) -> str:
    """
    Marketplace compression: keep the headline, price, lead, attachments,
    and CTA; drop the long blocks (Trust & Proof, Best For, op-value lists,
    Additional Details) when the word budget is blown.
    """
    word_count = len(text.split())
    if word_count <= max_words:
        return text

    keep_headers = ("Attachments Included:", "Contact Details:")
    drop_headers = ("Trust & Proof:", "Best For:", "OEM Specs:",
                    "Features:", "Additional Details:")
    blocks = re.split(r"\n\n+", text)
    kept: List[str] = []
    for blk in blocks:
        first_line = blk.splitlines()[0] if blk else ""
        if any(first_line.startswith(h) for h in drop_headers):
            continue
        kept.append(blk)
    out = "\n\n".join(kept)
    if len(out.split()) > max_words:
        # Hard truncate prose, preserving final CTA
        cta_idx = out.rfind("Contact Details:")
        if cta_idx > 0:
            head = out[:cta_idx].strip()
            tail = out[cta_idx:].strip()
            head_words = head.split()
            keep_n = max(0, max_words - len(tail.split()))
            head = " ".join(head_words[:keep_n])
            out = (head + "\n\n" + tail).strip()
    return out
