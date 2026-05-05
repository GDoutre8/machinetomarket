"""
listing_copy_v3_hooks.py
========================
Job-first lead-hook selector for MTM Listing Copy Engine v3.

Loads the structured hook bank from docs/job_first_hook_bank_v1.yaml and
selects the highest-confidence hook whose required_fields and
trigger_conditions match the current listing context.

Each hook opens on a buyer's job — not the machine's identity — per the
research handoff (Layer 3, Lead hook selector).

Public API:
    select_hook(equipment_type, dealer_input, resolved_specs,
                scorer_top_use_case=None) -> str | None
"""

from __future__ import annotations

import hashlib
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional


_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


_EQ_NORM = {
    "compact_track_loader": "compact_track_loader",
    "ctl": "compact_track_loader",
    "skid_steer": "skid_steer",
    "skid_steer_loader": "skid_steer",
    "ssl": "skid_steer",
    "mini_excavator": "mini_excavator",
    "mini_ex": "mini_excavator",
    "telehandler": "telehandler",
    "excavator": "excavator",
    "large_excavator": "excavator",
    "wheel_loader": "wheel_loader",
    "dozer": "dozer",
}


@lru_cache(maxsize=1)
def _load_hook_bank() -> dict:
    path = os.path.join(_DOCS_DIR, "job_first_hook_bank_v1.yaml")
    try:
        import yaml  # type: ignore
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Context flattening — combine DealerInput + resolved_specs into one dict
# ─────────────────────────────────────────────────────────────────────────────

# Map hook YAML field names to the resolved-specs / dealer-input keys MTM uses.
# Hook YAML uses op_value_maps_v1.yaml field names; we translate into the
# canonical resolved keys.
_HOOK_FIELD_TO_SOURCES: Dict[str, tuple] = {
    "horsepower_hp":              ("net_hp", "horsepower_hp"),
    "operating_weight_lbs":       ("operating_weight_lb", "operating_weight_lbs"),
    "rated_operating_capacity_lbs": ("roc_lb", "rated_operating_capacity_lbs"),
    "tipping_load_lbs":           ("tipping_load_lb", "tipping_load_lbs"),
    "hydraulic_flow_gpm":         ("aux_flow_standard_gpm", "hydraulic_flow_gpm"),
    "aux_flow_standard_gpm":      ("aux_flow_standard_gpm", "hydraulic_flow_gpm"),
    "aux_flow_high_gpm":          ("aux_flow_high_gpm",),
    "travel_speed_high_mph":      ("travel_speed_high_mph",),
    "travel_speed_mph":           ("travel_speed_high_mph", "travel_speed_low_mph"),
    "fuel_capacity_gal":          ("fuel_capacity_gal",),
    "lift_capacity_lbs":          ("lift_capacity_lb", "max_lift_capacity_lbs", "lift_capacity_lbs"),
    "max_lift_height_ft":         ("max_lift_height_ft", "lift_height_ft"),
    "max_forward_reach_ft":       ("max_forward_reach_ft", "forward_reach_ft"),
    "dig_depth_ft":               ("max_dig_depth_ft", "max_dig_depth"),
    "max_reach_ft":               ("max_reach_ft",),
    "machine_width_inches":       ("width_over_tires_in", "width_in"),
    "track_percent_remaining":    ("track_percent_remaining",),
    "bucket_breakout_force":      ("bucket_breakout_lb", "bucket_dig_force_lbf"),
    "blade_width":                ("blade_width_in",),
    "lift_path":                  ("lift_path",),
    "tail_swing_type":            ("tail_swing_type",),
    "swing_type":                 ("tail_swing_type",),
}


def _build_eval_ctx(dealer_input: Any, resolved_specs: Dict) -> Dict[str, Any]:
    """
    Flat dict: hook_field_name → coerced value (numeric where possible, bool
    for yes/no/true/false fields, raw string otherwise).
    """
    di = dealer_input

    def _get(*keys):
        for k in keys:
            v = getattr(di, k, None)
            if v is None:
                v = resolved_specs.get(k)
            if v is not None and str(v).strip() != "":
                return v
        return None

    def _bool(v):
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("yes", "true", "1"):
            return True
        if s in ("no", "false", "0", "none", ""):
            return False
        return None

    def _num(v):
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            m = re.search(r"-?\d+(?:\.\d+)?", v)
            if m:
                try:
                    return float(m.group(0))
                except ValueError:
                    return None
        return None

    ctx: Dict[str, Any] = {}

    # Resolved-spec field translations
    for hook_key, sources in _HOOK_FIELD_TO_SOURCES.items():
        v = _get(*sources)
        if v is not None:
            n = _num(v)
            ctx[hook_key] = n if n is not None else v

    # Booleans / status fields from DealerInput
    for f in ("ac", "heater", "ride_control", "backup_camera", "one_owner",
              "radio", "rubber_tracks", "zero_tail_swing", "self_leveling",
              "reversing_fan", "rear_camera", "hammer_plumbing",
              "heated_seat", "pattern_changer", "air_ride_seat",
              "bucket_included"):
        val = getattr(di, f, None)
        if val is not None:
            b = _bool(val)
            ctx[f] = val if b is None else b

    # Status string fields → bool true when "yes"
    for f in ("high_flow", "two_speed_travel"):
        val = getattr(di, f, None)
        if val is not None:
            ctx[f] = (str(val).strip().lower() == "yes")
    # Hook YAML uses `two_speed`; alias.
    if "two_speed_travel" in ctx:
        ctx["two_speed"] = ctx["two_speed_travel"]
    # Hook YAML uses `aux_hydraulics` boolean
    aux = getattr(di, "aux_hydraulics", None)
    if aux is not None:
        b = _bool(aux)
        ctx["aux_hydraulics"] = aux if b is None else b

    # Cab type → enclosed_cab boolean
    cab = (getattr(di, "cab_type", "") or "").strip().lower()
    ctx["enclosed_cab"] = cab in ("enclosed", "erops", "closed", "cab")
    ctx["cab_type"] = cab or None
    if ctx["enclosed_cab"] and (getattr(di, "ac", None) and getattr(di, "heater", None)):
        ctx["heat_ac"] = True

    # Identity / hours
    ctx["year"] = getattr(di, "year", None)
    ctx["hours"] = getattr(di, "hours", None)
    ctx["asking_price"] = getattr(di, "asking_price", None)

    # Strings
    for f in ("thumb_type", "blade_type", "coupler_type", "control_type",
              "track_condition", "tire_condition", "arm_length",
              "boom_type", "grade_control_type", "aux_hydraulics_type",
              "track_type"):
        v = getattr(di, f, None)
        if v is not None and str(v).strip() != "":
            ctx[f] = str(v).strip().lower()

    # Hook YAML uses `quick_attach_type` — alias from coupler_type
    if "coupler_type" in ctx:
        ctx["quick_attach_type"] = ctx["coupler_type"]

    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Trigger-condition evaluator (small, safe subset of Python boolean expr)
# ─────────────────────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<lparen>\() |
        (?P<rparen>\)) |
        (?P<and>\band\b) |
        (?P<or>\bor\b) |
        (?P<not>\bnot\b) |
        (?P<op>>=|<=|==|!=|>|<) |
        (?P<bool>\b(?:true|false|True|False)\b) |
        (?P<num>-?\d+(?:\.\d+)?) |
        (?P<str>'[^']*'|"[^"]*") |
        (?P<ident>[A-Za-z_][A-Za-z_0-9]*)
    )
    """,
    re.VERBOSE,
)


def _tokenize(expr: str) -> List[tuple]:
    tokens: List[tuple] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m or m.end() == pos:
            # Skip unknown char
            pos += 1
            continue
        for name, val in m.groupdict().items():
            if val is not None:
                tokens.append((name, val))
                break
        pos = m.end()
    return tokens


def _eval_trigger(expr: Optional[str], ctx: Dict[str, Any]) -> bool:
    """
    Evaluate hook YAML trigger_conditions against a context dict.

    Grammar:
        expr    := orexpr
        orexpr  := andexpr ('or' andexpr)*
        andexpr := atom ('and' atom)*
        atom    := 'not' atom | '(' expr ')' | comparison
        comparison := ident (op value)?
        op      := == | != | > | < | >= | <=
        value   := number | bool | string | ident

    Returns True when expr is missing/empty/None.  Returns False when an
    identifier referenced in the expression is missing from ctx (silence-safe).
    """
    if expr is None:
        return True
    s = str(expr).strip()
    if not s or s.lower() == "null":
        return True

    tokens = _tokenize(s)
    if not tokens:
        return True

    pos = [0]  # mutable index

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else (None, None)

    def consume():
        t = peek()
        pos[0] += 1
        return t

    def parse_value():
        kind, val = consume()
        if kind == "num":
            return float(val)
        if kind == "bool":
            return val.lower() == "true"
        if kind == "str":
            return val[1:-1]
        if kind == "ident":
            # bare identifier RHS: treat as string literal (e.g. == hydraulic)
            return val
        return None

    def parse_comparison():
        kind, val = peek()
        if kind == "lparen":
            consume()
            v = parse_or()
            if peek()[0] == "rparen":
                consume()
            return v
        if kind == "not":
            consume()
            return not parse_atom()
        if kind != "ident":
            consume()
            return False
        # consume identifier
        consume()
        ident_val = ctx.get(val, None)
        # Operator?
        if peek()[0] == "op":
            _, op = consume()
            rhs = parse_value()
            if ident_val is None:
                return False
            try:
                if isinstance(rhs, (int, float)) and isinstance(ident_val, (int, float)):
                    a, b = float(ident_val), float(rhs)
                else:
                    # String compare — case-insensitive
                    if isinstance(rhs, bool):
                        a, b = bool(ident_val), bool(rhs)
                    else:
                        a, b = str(ident_val).lower(), str(rhs).lower() if not isinstance(rhs, bool) else rhs
                if op == "==": return a == b
                if op == "!=": return a != b
                if op == ">":  return a >  b
                if op == "<":  return a <  b
                if op == ">=": return a >= b
                if op == "<=": return a <= b
            except Exception:
                return False
            return False
        # bare identifier → truthy check
        return bool(ident_val)

    def parse_atom():
        return parse_comparison()

    def parse_and():
        v = parse_atom()
        while peek()[0] == "and":
            consume()
            v = parse_atom() and v
        return v

    def parse_or():
        v = parse_and()
        while peek()[0] == "or":
            consume()
            v = parse_and() or v
        return v

    try:
        return bool(parse_or())
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Field-presence check (required_fields)
# ─────────────────────────────────────────────────────────────────────────────

def _required_fields_present(required: List[str], ctx: Dict[str, Any]) -> bool:
    for f in required or []:
        v = ctx.get(f)
        if v is None:
            return False
        if isinstance(v, str) and v.strip() == "":
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Template substitution
# ─────────────────────────────────────────────────────────────────────────────

_TPL_TOKEN_RE = re.compile(r"\{([A-Za-z_][A-Za-z_0-9]*)\}")


def _format_value(v: Any) -> str:
    if isinstance(v, float):
        if v == int(v):
            v = int(v)
    if isinstance(v, int) and abs(v) >= 1000:
        return f"{v:,}"
    return str(v)


def _fill_template(text: str, ctx: Dict[str, Any]) -> Optional[str]:
    """Substitute {field} tokens. Return None if any required token missing."""
    def repl(m):
        key = m.group(1)
        v = ctx.get(key)
        if v is None or (isinstance(v, str) and not v.strip()):
            return "\x00MISSING\x00"
        return _format_value(v)

    out = _TPL_TOKEN_RE.sub(repl, text)
    if "\x00MISSING\x00" in out:
        return None
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Public selector
# ─────────────────────────────────────────────────────────────────────────────

def select_hook(
    equipment_type: str,
    dealer_input: Any,
    resolved_specs: Dict,
    scorer_top_use_case: Optional[str] = None,
) -> Optional[str]:
    """
    Return a single job-first opening sentence, or None when no hook qualifies.

    Selection:
      1. Equipment-type bucket from job_first_hook_bank_v1.yaml.
      2. Filter: required_fields all present AND trigger_conditions evaluates True.
      3. Filter: at least one opening_pattern fills with no missing tokens.
      4. Score: scorer_top_use_case match > confidence(high>medium) > spec count.
      5. Deterministic pick within tied group, keyed by year|make|model|hours.
    """
    bank = _load_hook_bank()
    if not bank:
        return None

    eq = _EQ_NORM.get((equipment_type or "").strip().lower())
    if not eq or eq not in bank:
        return None

    bucket = bank[eq] or {}
    if not isinstance(bucket, dict):
        return None

    ctx = _build_eval_ctx(dealer_input, resolved_specs)
    candidates: List[tuple] = []  # (score, key, filled_text)

    scorer_label = (scorer_top_use_case or "").strip().lower().replace(" ", "_").replace("&", "and")

    for hook_key, hook in bucket.items():
        if not isinstance(hook, dict):
            continue
        required = hook.get("required_fields") or []
        if not _required_fields_present(required, ctx):
            continue
        trig = hook.get("trigger_conditions")
        if not _eval_trigger(trig, ctx):
            continue

        patterns = hook.get("opening_patterns") or []
        filled = []
        for p in patterns:
            f = _fill_template(p, ctx)
            if f:
                filled.append(f)
        if not filled:
            continue

        confidence = (hook.get("confidence") or "medium").lower()
        score = 0
        # Use-case match boosts score
        hk_norm = hook_key.replace("-", "_").replace(" ", "_").lower()
        if scorer_label and (scorer_label == hk_norm or scorer_label in hk_norm or hk_norm in scorer_label):
            score += 100
        if confidence == "high":
            score += 10
        elif confidence == "medium":
            score += 5
        score += len(required)  # specificity tiebreaker

        # Deterministic pattern pick within this hook
        key = "|".join(str(getattr(dealer_input, a, "") or "") for a in ("year", "make", "model", "hours"))
        digest = hashlib.sha1(f"{eq}|{hook_key}|{key}".encode()).hexdigest()
        idx = int(digest[:8], 16) % len(filled)
        chosen = filled[idx]

        candidates.append((score, hook_key, chosen))

    if not candidates:
        return None

    candidates.sort(key=lambda t: (-t[0], t[1]))
    return candidates[0][2]
