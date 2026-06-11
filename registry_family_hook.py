"""MTM Session 3 — Family Relationship Graph: runtime lookup hook.

Read-only nearest-relative ranking over the offline-built family graph
(``outputs/family_graph/ctl_ssl_family_graph.json``). Family membership is
decided offline by ``registry_family_extractor``; this module only ranks
within a pre-confirmed family. It never invents membership.

GAP TELEMETRY CONTRACT (locked, Session 3)
------------------------------------------
This module performs NO writes of any kind — no gap_detector calls, no
database access, no registry access. A family-resolved lookup is still a
registry gap for the exact model: callers integrating family fallback MUST
continue to fire the existing miss path (gap_detector.record_lookup /
record_miss) exactly as they do today, *before* consulting this hook.
Family fallback must never suppress or alter exact-model gap telemetry.

Scoring (locked): score = 100 - 25 * generation_distance, minimum
acceptable score 50. Hard disqualifiers: different manufacturer,
different equipment_type, ambiguous root parse, no family for the root.
Variant members are excluded from ranking; query variant suffixes on the
whitelist (e.g. 'T770 Forestry') do not block the family-root match but
the match carries the variant context. Stable fields are the ONLY specs a
family match may surface; variable fields are ranges, never single
values; tri-states and feature_flags are never family-resolvable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from registry_family_extractor import (
    DEFAULT_OUT_DIR, FAMILY_STABLE_ALLOWED_FIELDS, GRAPH_FILENAME,
    _is_excluded_field, normalize_equipment_type, normalize_manufacturer,
    parse_model, _ident,
)

DEFAULT_GRAPH_PATH = Path(DEFAULT_OUT_DIR) / GRAPH_FILENAME

MIN_ACCEPTABLE_SCORE = 50
GENERATION_DISTANCE_WEIGHT = 25
MAX_RELATIVES = 3

_graph_cache: dict = {}   # path -> index


@dataclass
class FamilyMatch:
    query_manufacturer: str
    query_model: str
    query_equipment_type: str
    normalized_root: str
    family_id: Optional[str]
    match_basis: str                      # 'member_exact' | 'family_root' | 'none'
    nearest_relatives: list = field(default_factory=list)
    stable_fields_available: dict = field(default_factory=dict)
    variable_fields_blocked: dict = field(default_factory=dict)
    safe_for_injection: bool = False
    ambiguity_flags: list = field(default_factory=list)
    ui_label: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _load_index(graph_path) -> Optional[dict]:
    key = str(graph_path)
    if key in _graph_cache:
        return _graph_cache[key]
    path = Path(graph_path)
    if not path.exists():
        return None
    graph = json.loads(path.read_text(encoding="utf-8"))
    index = {
        (f["manufacturer"], f["equipment_type"], f["family_root"]): f
        for f in graph.get("families", [])
    }
    _graph_cache[key] = index
    return index


def clear_cache() -> None:
    _graph_cache.clear()


def find_best_family_match(make: str, model: str, equipment_type: str,
                           graph_path=DEFAULT_GRAPH_PATH) -> FamilyMatch:
    """Rank nearest relatives for a model within its pre-confirmed family.

    Pure read; performs no telemetry writes (see module contract). Returns
    a FamilyMatch with match_basis='none' on every disqualifying condition
    — never raises, never guesses.
    """
    result = FamilyMatch(
        query_manufacturer=make or "", query_model=model or "",
        query_equipment_type=equipment_type or "",
        normalized_root="", family_id=None, match_basis="none")
    try:
        mfr = normalize_manufacturer(make or "")
        eq = normalize_equipment_type(equipment_type or "")
        if not mfr or not (model or "").strip() or not eq:
            result.ambiguity_flags.append("missing_input")
            return result

        parse = parse_model(mfr, model)
        result.normalized_root = parse.root
        if parse.kind == "ambiguous":
            # Hard disqualifier: ambiguous root is flagged, never assigned.
            result.ambiguity_flags.append("ambiguous_root")
            result.ui_label = (f"Model '{model}' could not be safely parsed "
                               f"({parse.ambiguity_reason}) — manual review.")
            return result

        index = _load_index(graph_path)
        if index is None:
            result.ambiguity_flags.append("graph_unavailable")
            return result
        node = index.get((mfr, eq, parse.root))
        if node is None or node.get("status") != "confirmed":
            return result   # no family (or unconfirmed): basis stays 'none'

        result.family_id = node["family_id"]
        members = node.get("members", [])
        query_ident = _ident(model)

        exact = next((m for m in members if m["model_ident"] == query_ident),
                     None)
        if exact is not None:
            result.match_basis = "member_exact"
            result.nearest_relatives = [{
                "model_slug": exact["model_slug"], "model": exact["model"],
                "score": 100, "generation_distance": 0}]
            result.ui_label = (f"Exact family member: {exact['model']} — "
                               f"use the registry record directly.")
            # Exact members resolve through the normal registry path; the
            # family hook adds nothing and injects nothing.
            return result

        result.match_basis = "family_root"
        if parse.is_variant:
            # Whitelisted variant suffix (e.g. Forestry): root match holds,
            # but flag the variant context — no spec inference from base.
            result.ambiguity_flags.append("query_variant_suffix")

        mainline = [m for m in members if not m["is_variant"]]
        ranked = []
        for m in mainline:
            dist = abs(parse.generation_ordinal - m["generation_ordinal"])
            score = 100 - GENERATION_DISTANCE_WEIGHT * dist
            if score >= MIN_ACCEPTABLE_SCORE:
                ranked.append({"model_slug": m["model_slug"],
                               "model": m["model"], "score": score,
                               "generation_distance": dist})
        ranked.sort(key=lambda r: (-r["score"], r["model"]))
        result.nearest_relatives = ranked[:MAX_RELATIVES]

        if not ranked:
            result.ui_label = (f"Family {node['display_name']} found but no "
                               f"relative within range — manufacturer-level "
                               f"result only.")
            return result

        # Allowlist enforcement at the exposure boundary too (P1 audit
        # Finding 2): even a stale/hand-edited graph artifact can never
        # surface option-dependent or non-allowlisted fields, and
        # safe_for_injection requires at least one ALLOWED stable field.
        result.stable_fields_available = {
            k: v for k, v in (node.get("stable_fields") or {}).items()
            if k in FAMILY_STABLE_ALLOWED_FIELDS and not _is_excluded_field(k)
        }
        result.variable_fields_blocked = {
            k: v for k, v in (node.get("variable_fields") or {}).items()
            if not _is_excluded_field(k)
        }
        result.safe_for_injection = (not result.ambiguity_flags
                                     and bool(result.stable_fields_available))
        top = ranked[0]
        result.ui_label = (f"Family match — closest relative {top['model']} "
                           f"(family {node['display_name']}). Family-stable "
                           f"specs only; this is not an exact match.")
        return result
    except Exception:
        # Fail closed to 'none' — the hook must never break a lookup.
        result.ambiguity_flags.append("hook_error")
        result.match_basis = "none"
        result.safe_for_injection = False
        return result
