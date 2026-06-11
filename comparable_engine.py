"""MTM Comparable Engine.

Selects comparable machines for a resolved registry record and produces
field-level deltas plus positioning language ready for spec sheet injection.

Input
-----
A full registry record dict (CTL or SSL registry shape): must carry
``equipment_type``, ``manufacturer``, ``model``, ``model_slug``,
``registry_tier``, and a ``specs`` dict.

Output schema (ComparableResult)
--------------------------------
ComparableResult:
    listed_slug              str   model_slug of the listed machine
    equipment_type           str
    comparables              list[ComparableMatch]  (0-2 entries)
    delta_fields             dict  {comparable_slug: {field: FieldDelta-as-dict}}
    positioning_lines        list[str]  flat bullet strings, lead comparable first
    spec_sheet_block         str   ready-to-inject "Why consider this machine?" block
    comparable_count_warning bool  True when fewer than 2 comparables qualified
    positioning_confidence   str   "HIGH" | "MEDIUM" | "LOW"

ComparableMatch:
    manufacturer, model, model_slug, registry_tier
    match_quality    "strict" | "relaxed_hp" | "relaxed_frame" | "relaxed_roc"
    similarity_score float (lower = more similar)
    deltas           dict {field: FieldDelta}
    delta_lines      list[str]  ordered bullets (wins first, then similar,
                                then smallest deficits), max 3

FieldDelta:
    listed_value, comparable_value, delta, delta_pct
    direction  "win" | "trail" | "similar" | "info" | "missing"
    text       rendered delta string or None

Selection rules
---------------
Hard constraints (never relaxed):
  * candidate ``equipment_type`` equals the listed record's (same category only)
  * candidate ``registry_tier`` in {"production", "production_clean"} —
    never stubs, never production_candidate
  * candidate is not the listed machine itself (model_slug match)

Similarity criteria, applied as an ordered relaxation ladder. Each level is
tried only if the previous level yielded fewer than 2 candidates; results
accumulate across levels:
  L0 strict        frame_size equal (both missing also matches; one-sided
                   missing fails), ROC within ±20%, HP within ±15%
  L1 relaxed_hp    drop the HP band
  L2 relaxed_frame frame_size ignored
  L3 relaxed_roc   ROC band widened to ±35%
If fewer than 2 candidates qualify after L3, the result returns however many
qualified and sets ``comparable_count_warning = True``.

A missing (null) value on either side of a numeric band check cannot
disqualify a candidate (registries use null for OEM-unpublished specs); it
passes the band with a similarity penalty instead.

Win directions (numeric comparison fields):
  rated_operating_capacity_lbs  higher wins
  horsepower_hp                 higher wins
  aux_flow_high_gpm             higher wins
  operating_weight_lbs          higher wins (more machine / stability
                                convention for equipment comps)
``lift_path`` is informational only ("vertical lift path vs radial"); it
never counts as a win or a deficit.

Positioning: bullets lead with fields where the listed machine wins (largest
advantage first). If the listed machine trails on every numeric comparison
across all comparables, the smallest deficit is surfaced first and
``positioning_confidence`` is set to "LOW".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

ALLOWED_TIERS = frozenset({"production", "production_clean"})

REGISTRY_DIR = Path(__file__).resolve().parent / "registry" / "active"
DEFAULT_REGISTRY_FILES = (
    "mtm_ctl_registry_v1_32.json",
    "mtm_skid_steer_registry_v1_18.json",
)

SIMILAR_PCT = 0.05  # within 5% reads as "similar"
MAX_BULLETS = 3

# (field, label, unit, higher_wins)
NUMERIC_FIELDS = (
    ("rated_operating_capacity_lbs", "rated operating capacity", "lb", True),
    ("horsepower_hp", "horsepower", "hp", True),
    ("aux_flow_high_gpm", "high-flow auxiliary hydraulics", "gpm", True),
    ("operating_weight_lbs", "operating weight", "lb", True),
)
LIFT_PATH_FIELD = "lift_path"


@dataclass
class FieldDelta:
    listed_value: Optional[float | str]
    comparable_value: Optional[float | str]
    delta: Optional[float]
    delta_pct: Optional[float]
    direction: str  # win | trail | similar | info | missing
    text: Optional[str]


@dataclass
class ComparableMatch:
    manufacturer: str
    model: str
    model_slug: str
    registry_tier: str
    match_quality: str
    similarity_score: float
    deltas: dict = field(default_factory=dict)
    delta_lines: list = field(default_factory=list)


@dataclass
class ComparableResult:
    listed_slug: str
    equipment_type: str
    comparables: list = field(default_factory=list)
    delta_fields: dict = field(default_factory=dict)
    positioning_lines: list = field(default_factory=list)
    spec_sheet_block: str = ""
    comparable_count_warning: bool = False
    positioning_confidence: str = "MEDIUM"


_POOL_CACHE: Optional[list[dict]] = None


def load_default_pool() -> list[dict]:
    """Load and cache tier-eligible records from the active CTL and SSL registries."""
    global _POOL_CACHE
    if _POOL_CACHE is None:
        pool = []
        for name in DEFAULT_REGISTRY_FILES:
            with open(REGISTRY_DIR / name, encoding="utf-8") as f:
                data = json.load(f)
            for rec in data.get("records", []):
                if rec.get("registry_tier") in ALLOWED_TIERS:
                    pool.append(rec)
        _POOL_CACHE = pool
    return _POOL_CACHE


def _num(record: dict, key: str) -> Optional[float]:
    val = (record.get("specs") or {}).get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _within(listed: Optional[float], cand: Optional[float], tol: float) -> bool:
    """Band check; a null on either side passes (cannot disqualify)."""
    if listed is None or cand is None or listed == 0:
        return True
    return abs(cand - listed) / abs(listed) <= tol


def _frame_match(listed: dict, cand: dict) -> bool:
    lf = (listed.get("specs") or {}).get("frame_size")
    cf = (cand.get("specs") or {}).get("frame_size")
    if lf and cf:
        return lf == cf
    return not lf and not cf  # both missing matches; one-sided missing fails


def _similarity_score(listed: dict, cand: dict, level: int) -> float:
    score = float(level)  # prefer candidates found at stricter levels
    for key, tol_penalty in (("rated_operating_capacity_lbs", 0.5), ("horsepower_hp", 0.5)):
        lv, cv = _num(listed, key), _num(cand, key)
        if lv is None or cv is None or lv == 0:
            score += tol_penalty
        else:
            score += abs(cv - lv) / abs(lv)
    if not _frame_match(listed, cand):
        score += 0.25
    if listed.get("model_family") and listed.get("model_family") == cand.get("model_family"):
        score += 0.3  # sibling variants make weak positioning comparisons
    return score


def _passes_level(listed: dict, cand: dict, level: int) -> bool:
    roc_tol = 0.35 if level >= 3 else 0.20
    if not _within(_num(listed, "rated_operating_capacity_lbs"),
                   _num(cand, "rated_operating_capacity_lbs"), roc_tol):
        return False
    if level < 1 and not _within(_num(listed, "horsepower_hp"),
                                 _num(cand, "horsepower_hp"), 0.15):
        return False
    if level < 2 and not _frame_match(listed, cand):
        return False
    return True


_LEVEL_NAMES = {0: "strict", 1: "relaxed_hp", 2: "relaxed_frame", 3: "relaxed_roc"}


def _fmt_value(value: float, unit: str) -> str:
    if unit == "gpm":
        return f"{value:+.1f} {unit}"
    return f"{value:+,.0f} {unit}"


def _build_deltas(listed: dict, cand: dict) -> dict[str, FieldDelta]:
    deltas: dict[str, FieldDelta] = {}
    for key, label, unit, higher_wins in NUMERIC_FIELDS:
        lv, cv = _num(listed, key), _num(cand, key)
        if lv is None or cv is None:
            deltas[key] = FieldDelta(lv, cv, None, None, "missing", None)
            continue
        diff = lv - cv
        pct = diff / cv if cv else None
        if pct is not None and abs(pct) <= SIMILAR_PCT:
            deltas[key] = FieldDelta(lv, cv, diff, pct, "similar",
                                     f"similar {label} (within 5%)")
            continue
        wins = (diff > 0) == higher_wins
        deltas[key] = FieldDelta(lv, cv, diff, pct, "win" if wins else "trail",
                                 f"{_fmt_value(diff, unit)} {label}")
    lp_l = (listed.get("specs") or {}).get(LIFT_PATH_FIELD)
    lp_c = (cand.get("specs") or {}).get(LIFT_PATH_FIELD)
    if lp_l and lp_c and lp_l != lp_c:
        deltas[LIFT_PATH_FIELD] = FieldDelta(lp_l, lp_c, None, None, "info",
                                             f"{lp_l} lift path vs {lp_c}")
    elif lp_l or lp_c:
        deltas[LIFT_PATH_FIELD] = FieldDelta(lp_l, lp_c, None, None,
                                             "missing" if not (lp_l and lp_c) else "info",
                                             None)
    return deltas


def _order_bullets(deltas: dict[str, FieldDelta]) -> list[str]:
    wins = sorted((d for d in deltas.values() if d.direction == "win"),
                  key=lambda d: -(abs(d.delta_pct) if d.delta_pct is not None else 0))
    similar = [d for d in deltas.values() if d.direction == "similar"]
    trails = sorted((d for d in deltas.values() if d.direction == "trail"),
                    key=lambda d: abs(d.delta_pct) if d.delta_pct is not None else 0)
    info = [d for d in deltas.values() if d.direction == "info" and d.text]
    ordered = wins + similar + trails + info
    return [d.text for d in ordered if d.text][:MAX_BULLETS]


def find_comparables(record: dict, pool: Optional[list[dict]] = None) -> ComparableResult:
    """Select up to two comparables for ``record`` and build positioning output."""
    if pool is None:
        pool = load_default_pool()

    eq_type = record.get("equipment_type")
    listed_slug = record.get("model_slug") or ""

    candidates: dict[str, tuple[dict, int]] = {}
    for level in range(4):
        for cand in pool:
            if cand.get("equipment_type") != eq_type:
                continue
            if cand.get("registry_tier") not in ALLOWED_TIERS:
                continue
            slug = cand.get("model_slug") or f"{cand.get('manufacturer')}|{cand.get('model')}"
            if cand is record or (listed_slug and slug == listed_slug):
                continue
            if slug in candidates:
                continue
            if _passes_level(record, cand, level):
                candidates[slug] = (cand, level)
        if len(candidates) >= 2:
            break

    ranked = sorted(candidates.items(),
                    key=lambda kv: _similarity_score(record, kv[1][0], kv[1][1]))[:2]

    result = ComparableResult(listed_slug=listed_slug, equipment_type=eq_type or "")
    result.comparable_count_warning = len(ranked) < 2

    any_win = False
    any_numeric = False
    wins_vs_every = bool(ranked)

    for slug, (cand, level) in ranked:
        deltas = _build_deltas(record, cand)
        match = ComparableMatch(
            manufacturer=cand.get("manufacturer", ""),
            model=cand.get("model", ""),
            model_slug=slug,
            registry_tier=cand.get("registry_tier", ""),
            match_quality=_LEVEL_NAMES[level],
            similarity_score=round(_similarity_score(record, cand, level), 4),
            deltas={k: asdict(d) for k, d in deltas.items()},
            delta_lines=_order_bullets(deltas),
        )
        result.comparables.append(match)
        result.delta_fields[slug] = match.deltas

        numeric = [d for d in deltas.values() if d.direction in ("win", "trail", "similar")]
        any_numeric = any_numeric or bool(numeric)
        cand_win = any(d.direction == "win" for d in numeric)
        any_win = any_win or cand_win
        wins_vs_every = wins_vs_every and cand_win

    if not ranked or not any_numeric:
        result.positioning_confidence = "LOW"
    elif not any_win:
        result.positioning_confidence = "LOW"  # trails on all numeric fields
    elif wins_vs_every:
        result.positioning_confidence = "HIGH"
    else:
        result.positioning_confidence = "MEDIUM"

    blocks = []
    for match in result.comparables:
        if not match.delta_lines:
            continue
        lines = "\n".join(f"• {t}" for t in match.delta_lines)
        blocks.append(f"Compared to a {match.manufacturer} {match.model}:\n{lines}")
        result.positioning_lines.extend(match.delta_lines)
    if blocks:
        result.spec_sheet_block = "Why consider this machine?\n\n" + "\n\n".join(blocks) + "\n"

    return result
