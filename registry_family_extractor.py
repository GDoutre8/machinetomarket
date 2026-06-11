"""MTM Session 3 — Family Relationship Graph: offline extractor.

Builds the family graph sidecar artifact from the active CTL and SSL
registries. Implements the approved design in
``mtm_session3_family_graph_design.md``. Registry files are read-only
inputs; this module never writes to ``registry/``.

Locked policy (Session 3):
- Family identity = (canonical manufacturer, canonical equipment_type,
  grammar root). Nothing else may join records.
- No edit distance, no spec similarity, no substring-only matching.
- No cross-manufacturer linking, including Gehl/Mustang rebadges.
- No automatic cross-root succession edges; those require manual seed
  edges (none shipped this session — the seed list needs OEM evidence).
- Registry ``model_family`` is corroboration-only ("D Series" spans
  259D/279D/299D — three frames — and must never create identity).
- Ambiguous records are flagged and excluded from membership, never
  guessed into a family.
- Single-member families count as assigned for Day 3 metrics.

Grammar engine
--------------
Each manufacturer grammar parses a *root prefix* from the model string and
then classifies the remainder against known generation tokens and a
variant-suffix whitelist. Three outcomes:

- parsed:    root + generation ordinal (+ optional variant suffixes)
- ambiguous: the root matched but the remainder contains an unknown token
             ("5240E P2") — flagged for review, never assigned
- no match:  the generic fallback assigns root = the full normalized
             string as a single-member family identity (still "assigned")

Stable / variable fields (per family, mainline members only — variants are
excluded from voting per the approved design):
- stable:   >= 2 voting members, all non-null values exactly equal
- variable: differing non-null values; numeric fields carry min/max and
            per-member values
- Single-member families have NO stable fields (copying one model's specs
  to a missing relative is spec inference).
- Tri-states and feature_flags are never family-stable, regardless of
  votes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent

ACTIVE_REGISTRIES = {
    "compact_track_loader": _HERE / "registry" / "active" / "mtm_ctl_registry_v1_32.json",
    "skid_steer": _HERE / "registry" / "active" / "mtm_skid_steer_registry_v1_18.json",
}

DEFAULT_OUT_DIR = _HERE / "outputs" / "family_graph"
GRAPH_FILENAME = "ctl_ssl_family_graph.json"
SUMMARY_FILENAME = "ctl_ssl_family_summary.md"

# Registry statuses counted as production records for Day 3 metrics.
# (The registries do not carry literal "production"/"production_clean"
# statuses; these four are the production-grade tiers. seed_only,
# invalid_*, and deprecated_* records are excluded from the denominator.)
PRODUCTION_STATUSES = {
    "active_used_market", "current", "active_new_market", "discontinued",
}

STOP_GATE_TARGETS = {"compact_track_loader": 0.80, "skid_steer": 0.70}

GRAPH_VERSION = "1.0"

# Canonical manufacturer keys. Deliberately self-contained (gap_detector
# precedent) so the offline build has no import-order coupling.
# NOTE: Gehl and Mustang are distinct keys and must never be merged.
MANUFACTURER_ALIASES = {
    "bobcat": "bobcat",
    "caterpillar": "caterpillar", "cat": "caterpillar",
    "john deere": "john deere", "johndeere": "john deere",
    "deere": "john deere", "jd": "john deere",
    "new holland": "new holland", "newholland": "new holland",
    "nh": "new holland",
    "case": "case", "case ih": "case",
    "kubota": "kubota",
    "takeuchi": "takeuchi",
    "gehl": "gehl",
    "mustang": "mustang",
    "jcb": "jcb",
    "volvo": "volvo",
    "asv": "asv",
    "yanmar": "yanmar",
    "wacker neuson": "wacker neuson", "wackerneuson": "wacker neuson",
    "wacker": "wacker neuson",
    "toro": "toro", "dingo": "toro", "toro dingo": "toro",
}

EQUIPMENT_TYPE_ALIASES = {
    "ctl": "compact_track_loader",
    "compact track loader": "compact_track_loader",
    "compact_track_loader": "compact_track_loader",
    "track loader": "compact_track_loader",
    "ssl": "skid_steer",
    "skid steer": "skid_steer",
    "skid_steer": "skid_steer",
    "skid steer loader": "skid_steer",
    "skid_steer_loader": "skid_steer",
}

# Fields that may NEVER be family-stable. Tri-state discipline: option
# availability changes between generations; only an exact record may
# speak. feature_flags are excluded wholesale at the computation site.
NEVER_STABLE_FIELDS = {
    "high_flow", "two_speed",
    "high_flow_available", "two_speed_available",
}

# Option/package/config-dependent fields: excluded from family field
# classification entirely (P1 audit, Finding 2). These depend on the
# machine's option package, not its model identity — a family can never
# speak for them; only an exact registry record may.
OPTION_DEPENDENT_FIELDS = {
    "aux_flow_high_gpm", "aux_flow_standard_gpm",
    "hydraulic_pressure_high_psi", "hydraulic_pressure_standard_psi",
    "travel_speed_high_mph", "travel_speed_low_mph", "travel_speed_mph",
    "emissions_tier",
    "standard_tire_size",
}


def _is_excluded_field(fname: str) -> bool:
    """True for fields that may never participate in family voting:
    tri-states, option-dependent fields, and availability booleans."""
    return (fname in NEVER_STABLE_FIELDS
            or fname in OPTION_DEPENDENT_FIELDS
            or fname.endswith("_available"))


# Conservative allowlist (P1 audit, Finding 2): ONLY these fields may ever
# appear in stable_fields for CTL/SSL. Everything else — even if identical
# across the family — resolves from an exact registry record only.
FAMILY_STABLE_ALLOWED_FIELDS = {
    "lift_path",
    "frame_size",
    "fuel_type",
    "rated_operating_capacity_lbs",
    "horsepower_hp",
    "operating_weight_lbs",
}


def normalize_manufacturer(make: str) -> str:
    if not make:
        return ""
    key = re.sub(r"[^a-z0-9 ]", "", str(make).strip().lower())
    key = re.sub(r"\s+", " ", key)
    return MANUFACTURER_ALIASES.get(key, key)


def normalize_equipment_type(eq: str) -> str:
    if not eq:
        return ""
    key = re.sub(r"\s+", " ", str(eq).strip().lower())
    return EQUIPMENT_TYPE_ALIASES.get(
        key, EQUIPMENT_TYPE_ALIASES.get(key.replace("_", " "),
                                        re.sub(r"\s+", "_", key)))


def _norm_model(model: str) -> str:
    """Uppercased, whitespace-collapsed model string for parsing."""
    return re.sub(r"\s+", " ", str(model or "").strip().upper())


def _ident(model: str) -> str:
    """Lowercase alphanumeric identity string (member-exact comparisons)."""
    return re.sub(r"[^a-z0-9]", "", str(model or "").lower())


# ---------------------------------------------------------------------------
# Parse result
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    kind: str                       # 'parsed' | 'ambiguous' | 'generic'
    root: str = ""                  # family root token (lowercase)
    generation_ordinal: int = 0     # position within the family's gen scheme
    generation_label: str = ""      # human label ('', 'D3', '-2', 'P-TIER'...)
    variant_suffixes: list = field(default_factory=list)
    ambiguity_reason: str = ""

    @property
    def is_variant(self) -> bool:
        return bool(self.variant_suffixes)


def _parsed(root, ordinal, label="", variants=None) -> ParseResult:
    return ParseResult("parsed", root.lower(), ordinal, label,
                       list(variants or []))


def _ambiguous(root, reason) -> ParseResult:
    return ParseResult("ambiguous", root.lower(), ambiguity_reason=reason)


# ---------------------------------------------------------------------------
# Per-manufacturer grammars
# Each returns ParseResult or None (None -> generic fallback).
# ---------------------------------------------------------------------------

def _grammar_kubota(model: str) -> Optional[ParseResult]:
    # SVL{frame}[-{gen}][S|X]  /  SSV{frame}[-{gen}]
    m = re.match(r"^(SVL|SSV)\s*(\d+)(.*)$", model)
    if not m:
        return None
    root = f"{m.group(1).lower()}{m.group(2)}"
    rest = m.group(3).strip()
    variants = []
    gen = 1
    gm = re.match(r"^-(\d+)(.*)$", rest)
    if gm:
        gen = int(gm.group(1)) + 0
        rest = gm.group(2).strip()
    if rest in ("S", "X"):          # SVL65-2S, SVL50x — track/width variants
        variants.append(rest)
        rest = ""
    if rest:
        return _ambiguous(root, f"unknown suffix '{rest}'")
    label = f"-{gen}" if gen > 1 else ""
    return _parsed(root, gen, label, variants)


_CAT_SERIES_ORDINALS = {"": 0, "B": 1, "B2": 2, "B3": 3,
                        "C": 4, "C2": 5, "D": 6, "D2": 7, "D3": 8}
_CAT_VARIANT_WHITELIST = {"XE", "XHP", "LAND MANAGEMENT"}


def _grammar_caterpillar(model: str) -> Optional[ParseResult]:
    # {frame:3 digits}[{series letter}[{gen digit}]] [XE|XHP|LAND MANAGEMENT]*
    # New-scheme bare models (255, 265, 275, 285) parse as gen-0 of their own
    # roots; linkage to legacy roots (255 <- 259D3) is manual-seed-only.
    m = re.match(r"^(\d{3})(.*)$", model)
    if not m:
        return None
    root, rest = m.group(1), m.group(2).strip()
    sm = re.match(r"^([BCD])(\d)?\b(.*)$", rest)
    series = ""
    if sm:
        series = sm.group(1) + (sm.group(2) or "")
        rest = sm.group(3).strip()
    variants = []
    while rest:
        for token in sorted(_CAT_VARIANT_WHITELIST, key=len, reverse=True):
            if rest.startswith(token):
                variants.append(token)
                rest = rest[len(token):].strip()
                break
        else:
            return _ambiguous(root, f"unknown suffix '{rest}'")
    return _parsed(root, _CAT_SERIES_ORDINALS[series], series, variants)


_BOBCAT_GEN_LETTERS = {"": 0, "B": 1, "C": 2, "D": 3, "G": 4}
_BOBCAT_VARIANT_WHITELIST = {"F", "FORESTRY", "M-SERIES", "(PRE-T4)", "(T4)"}


def _grammar_bobcat(model: str) -> Optional[ParseResult]:
    # [T|S|A]{frame}[gen letter] [variant tokens]*
    # Bobcat encodes generation in frame renumbering (T650 -> T66), so
    # cross-root succession is manual-seed-only by design.
    m = re.match(r"^([TSA])?(\d+)(.*)$", model)
    if not m:
        return None
    root = f"{(m.group(1) or '').lower()}{m.group(2)}"
    rest = m.group(3).strip()
    gen, label = 0, ""
    gm = re.match(r"^([BCDG])\b(.*)$", rest)
    if gm:
        label = gm.group(1)
        gen = _BOBCAT_GEN_LETTERS[label]
        rest = gm.group(2).strip()
    variants = []
    while rest:
        for token in sorted(_BOBCAT_VARIANT_WHITELIST, key=len, reverse=True):
            if rest.startswith(token):
                variants.append("FORESTRY" if token == "F" else token)
                rest = rest[len(token):].strip()
                break
        else:
            return _ambiguous(root, f"unknown suffix '{rest}'")
    return _parsed(root, gen, label, variants)


_DEERE_GEN_LETTERS = {"": 0, "B": 1, "D": 2, "E": 3, "G": 4, "P-TIER": 5}


def _grammar_john_deere(model: str) -> Optional[ParseResult]:
    # {frame digits}[B|D|E|G|GR|P-TIER]; 333G and '333 P-Tier' share root 333.
    # CT-prefixed legacy CTLs (CT322) are their own roots.
    m = re.match(r"^CT(\d+)$", model)
    if m:
        return _parsed(f"ct{m.group(1)}", 0)
    m = re.match(r"^(\d{2,4})\s*(.*)$", model)
    if not m:
        return None
    root, rest = m.group(1), m.group(2).strip()
    variants = []
    if rest in ("GR",):             # 312GR/316GR: G-series rental variants
        return _parsed(root, _DEERE_GEN_LETTERS["G"], "G", ["R"])
    if rest in ("P-TIER", "PTIER", "P TIER"):
        return _parsed(root, _DEERE_GEN_LETTERS["P-TIER"], "P-TIER")
    if rest in _DEERE_GEN_LETTERS:
        return _parsed(root, _DEERE_GEN_LETTERS[rest], rest, variants)
    return _ambiguous(root, f"unknown suffix '{rest}'")


_CASE_GEN_LETTERS = {"": 0, "B": 1, "C": 2}


def _grammar_case(model: str) -> Optional[ParseResult]:
    # SR/SV (SSL) and TR/TV (CTL): {prefix}{digits}[B]
    # Legacy: {digits}[B|C], {digits}XT, {digits}CT each their own roots.
    m = re.match(r"^(SR|SV|TR|TV)(\d+)(.*)$", model)
    if m:
        root, rest = f"{m.group(1).lower()}{m.group(2)}", m.group(3).strip()
        if rest in _CASE_GEN_LETTERS:
            return _parsed(root, _CASE_GEN_LETTERS[rest], rest)
        return _ambiguous(root, f"unknown suffix '{rest}'")
    m = re.match(r"^(\d{2,4})(XT|CT)$", model)
    if m:
        return _parsed(f"{m.group(1)}{m.group(2).lower()}", 0)
    m = re.match(r"^(\d{3,4})(.*)$", model)
    if m:
        root, rest = m.group(1), m.group(2).strip()
        if rest in _CASE_GEN_LETTERS:
            return _parsed(root, _CASE_GEN_LETTERS[rest], rest)
        return _ambiguous(root, f"unknown suffix '{rest}'")
    return None


def _grammar_new_holland(model: str) -> Optional[ParseResult]:
    # {LS|LX|LT|L|C}{digits}[B]
    m = re.match(r"^(LS|LX|LT|L|C)\s*(\d+)(.*)$", model)
    if not m:
        return None
    root, rest = f"{m.group(1).lower()}{m.group(2)}", m.group(3).strip()
    if rest in ("", "B"):
        return _parsed(root, 1 if rest == "B" else 0, rest)
    return _ambiguous(root, f"unknown suffix '{rest}'")


def _grammar_takeuchi(model: str) -> Optional[ParseResult]:
    # {TL|TS}{frame}[R|V][gen digit | -gen]
    # The lift-path letter (R/V) is part of the root: TL12R2 and TL12V2 are
    # different machines and must not share a family.
    m = re.match(r"^(TL|TS)(\d+)(R|V)?(?:(\d)|-(\d+))?$", model)
    if not m:
        return None
    root = f"{m.group(1).lower()}{m.group(2)}{(m.group(3) or '').lower()}"
    gen_token = m.group(4) or m.group(5)
    gen = int(gen_token) if gen_token else 1
    return _parsed(root, gen, gen_token or "")


def _grammar_gehl(model: str) -> Optional[ParseResult]:
    # RT/VT/R/V {digits} (track + wheeled lines); legacy {4 digits}[E].
    m = re.match(r"^(RT|VT|R|V)(\d+)$", model)
    if m:
        return _parsed(f"{m.group(1).lower()}{m.group(2)}", 0)
    m = re.match(r"^(\d{4})(.*)$", model)
    if m:
        root, rest = m.group(1), m.group(2).strip()
        if rest in ("", "E"):
            return _parsed(root, 1 if rest == "E" else 0, rest)
        return _ambiguous(root, f"unknown suffix '{rest}'")
    return None


def _grammar_asv(model: str) -> Optional[ParseResult]:
    m = re.match(r"^(RT|VT)-?(\d+)$", model)
    if m:
        return _parsed(f"{m.group(1).lower()}{m.group(2)}", 0)
    return None


def _grammar_jcb(model: str) -> Optional[ParseResult]:
    # {digits}[T] — the T (track) marker is part of the identity.
    m = re.match(r"^(\d+)(T?)$", model)
    if m:
        return _parsed(f"{m.group(1)}{m.group(2).lower()}", 0)
    return None       # Teleskid / ROBOT lines fall to generic identity


GRAMMARS = {
    "kubota": _grammar_kubota,
    "caterpillar": _grammar_caterpillar,
    "bobcat": _grammar_bobcat,
    "john deere": _grammar_john_deere,
    "case": _grammar_case,
    "new holland": _grammar_new_holland,
    "takeuchi": _grammar_takeuchi,
    "gehl": _grammar_gehl,
    "asv": _grammar_asv,
    "jcb": _grammar_jcb,
}


def parse_model(manufacturer: str, model: str) -> ParseResult:
    """Parse one model string under its manufacturer's grammar.

    Returns kind='parsed' (root + generation), kind='ambiguous' (root
    recognized, unknown remainder — must be flagged, never assigned), or
    kind='generic' (no grammar match — full-string identity, a safe
    single-member family root).
    """
    norm = _norm_model(model)
    if not norm:
        return _ambiguous("", "empty model")
    grammar = GRAMMARS.get(normalize_manufacturer(manufacturer))
    if grammar:
        result = grammar(norm)
        if result is not None:
            return result
    return ParseResult("generic", root=_ident(norm))


# ---------------------------------------------------------------------------
# Graph structures
# ---------------------------------------------------------------------------

@dataclass
class FamilyMember:
    model_slug: str
    model: str
    model_ident: str            # lowercase alnum, for member-exact matching
    generation_ordinal: int
    generation_label: str
    is_variant: bool
    variant_suffixes: list
    variant_of: Optional[str]   # mainline sibling slug, if any

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class FamilyNode:
    family_id: str
    manufacturer: str
    equipment_type: str
    family_root: str
    display_name: str
    members: list                  # list[FamilyMember]
    unique_logical_models: int     # distinct model_idents across members
    duplicate_model_ident_count: int   # rows collapsed in dedupe (diagnostic)
    status: str                    # 'confirmed' | 'provisional' | 'manual_review'
    evidence: list
    stable_fields: dict
    variable_fields: dict
    indeterminate_fields: list
    model_family_corroboration: dict   # registry marketing strings, info only
    registry_checksum: str
    built_at: str

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["members"] = [m.to_dict() for m in self.members]
        d["member_slugs"] = [m.model_slug for m in self.members]
        return d


@dataclass
class FamilyRelationship:
    from_slug: str
    to_slug: str
    relation_type: str       # 'successor' | 'variant' | 'manual_successor'
    generation_delta: int
    evidence: list
    confidence: str          # 'HIGH' | 'MEDIUM' | 'MANUAL'
    status: str              # 'confirmed' | 'provisional'

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# Stable / variable field computation
# ---------------------------------------------------------------------------

def dedupe_logical_models(member_records: list) -> tuple:
    """Collapse duplicate logical models (P1 audit, Finding 1).

    Logical model identity inside a family is the model_ident (the family
    is already scoped to manufacturer + equipment_type + grammar root).
    Returns (voting_records, duplicate_count): one record per unique
    model_ident — deterministic first-by-slug — and the number of
    duplicate rows collapsed. Duplicate rows remain family members
    (record references); they just lose their vote.
    """
    seen = {}
    ordered = sorted(member_records,
                     key=lambda r: str(r.get("model_slug") or r.get("model")))
    for rec in ordered:
        ident = _ident(rec.get("model") or "")
        seen.setdefault(ident, rec)
    return list(seen.values()), len(member_records) - len(seen)


def compute_field_classes(member_records: list) -> tuple:
    """Classify spec fields across a family's mainline (non-variant) members.

    Returns (stable_fields, variable_fields, indeterminate_fields).
    - Callers must pass UNIQUE logical models (see dedupe_logical_models);
      duplicate same-model rows must not create false stable votes. This
      function re-dedupes defensively.
    - Voting input is each record's ``specs`` dict only. Tri-states,
      feature_flags/availability booleans, and option-dependent fields
      (OPTION_DEPENDENT_FIELDS) are excluded wholesale: never family-
      resolvable in any bucket.
    - stable requires: field in FAMILY_STABLE_ALLOWED_FIELDS, >= 2 unique
      voting members with non-null values, all exactly equal. Fields that
      are identical but not allowlisted are omitted entirely — the exact
      registry record remains their only source.
    - Single-member (post-dedupe) families return no stable fields (spec
      inference guard).
    - variable carries the distinct values; numeric fields add min/max and
      per-member values.
    """
    member_records, _ = dedupe_logical_models(member_records)
    stable, variable, indeterminate = {}, {}, []
    if len(member_records) < 2:
        return stable, variable, indeterminate

    all_fields = set()
    for rec in member_records:
        all_fields.update((rec.get("specs") or {}).keys())
    all_fields = {f for f in all_fields if not _is_excluded_field(f)}

    for fname in sorted(all_fields):
        votes = []   # (slug, value) for non-null values
        for rec in member_records:
            val = (rec.get("specs") or {}).get(fname)
            if val is not None:
                votes.append((rec.get("model_slug") or rec.get("model"), val))
        if len(votes) < 2:
            indeterminate.append(fname)
            continue
        values = [v for _, v in votes]
        if all(v == values[0] for v in values):
            if fname in FAMILY_STABLE_ALLOWED_FIELDS:
                stable[fname] = values[0]
            # identical but not allowlisted: omitted — exact-record only
            continue
        entry = {
            "values": sorted({json.dumps(v) for v in values}),
            "member_values": {slug: v for slug, v in votes},
        }
        numerics = [v for v in values if isinstance(v, (int, float))
                    and not isinstance(v, bool)]
        if len(numerics) == len(values):
            entry["min"] = min(numerics)
            entry["max"] = max(numerics)
        variable[fname] = entry
    return stable, variable, indeterminate


# ---------------------------------------------------------------------------
# Graph build
# ---------------------------------------------------------------------------

def _slug(rec: dict) -> str:
    return rec.get("model_slug") or _ident(
        f"{rec.get('manufacturer', '')}_{rec.get('model', '')}")


def load_registry(path) -> list:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = data["records"] if isinstance(data, dict) else data
    return [r for r in records if isinstance(r, dict)]


def _file_checksum(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_graph(records_by_type: dict, registry_checksums: Optional[dict] = None,
                built_at: str = "", manual_seeds: Optional[list] = None) -> dict:
    """Build the family graph from registry records grouped by canonical
    equipment type. Pure function over record dicts (testable with
    synthetic records). ``manual_seeds`` is accepted for forward
    compatibility but none ship in Session 3 (OEM evidence required).
    """
    registry_checksums = registry_checksums or {}
    built_at = built_at or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    families: dict = {}        # (mfr, eq, root) -> list[(rec, ParseResult)]
    ambiguous_records: list = []
    per_type_counts: dict = {}

    for eq_type, records in records_by_type.items():
        canon_eq = normalize_equipment_type(eq_type)
        counts = per_type_counts.setdefault(canon_eq, {
            "records_total": 0, "production_total": 0,
            "assigned": 0, "ambiguous": 0, "excluded_status": 0,
        })
        for rec in records:
            counts["records_total"] += 1
            status = rec.get("status") or ""
            production = status in PRODUCTION_STATUSES
            if not production:
                counts["excluded_status"] += 1
            else:
                counts["production_total"] += 1

            mfr = normalize_manufacturer(rec.get("manufacturer") or "")
            model = rec.get("model") or ""
            if not mfr:
                ambiguous_records.append({
                    "model_slug": _slug(rec), "manufacturer": None,
                    "model": model, "equipment_type": canon_eq,
                    "reason": "missing manufacturer", "status": status,
                    "counted_in_denominator": production,
                })
                if production:
                    counts["ambiguous"] += 1
                continue

            parse = parse_model(mfr, model)
            if parse.kind == "ambiguous":
                ambiguous_records.append({
                    "model_slug": _slug(rec),
                    "manufacturer": rec.get("manufacturer"),
                    "model": model, "equipment_type": canon_eq,
                    "reason": parse.ambiguity_reason, "status": status,
                    "counted_in_denominator": production,
                })
                if production:
                    counts["ambiguous"] += 1
                continue

            if not production:
                continue   # parseable but non-production: not in graph or metrics
            counts["assigned"] += 1
            families.setdefault((mfr, canon_eq, parse.root), []).append(
                (rec, parse))

    nodes, relationships = [], []
    for (mfr, eq, root), entries in sorted(families.items()):
        members = []
        for rec, parse in entries:
            members.append(FamilyMember(
                model_slug=_slug(rec), model=rec.get("model") or "",
                model_ident=_ident(rec.get("model") or ""),
                generation_ordinal=parse.generation_ordinal,
                generation_label=parse.generation_label,
                is_variant=parse.is_variant,
                variant_suffixes=parse.variant_suffixes,
                variant_of=None,
            ))
        members.sort(key=lambda m: (m.generation_ordinal, m.is_variant,
                                    m.model_ident))

        # variant_of: mainline sibling at the same generation ordinal
        mainline_by_gen = {m.generation_ordinal: m for m in members
                           if not m.is_variant}
        for m in members:
            if m.is_variant and m.generation_ordinal in mainline_by_gen:
                m.variant_of = mainline_by_gen[m.generation_ordinal].model_slug

        # successor edges between consecutive mainline generations
        mainline = sorted(mainline_by_gen.values(),
                          key=lambda m: m.generation_ordinal)
        for prev, nxt in zip(mainline, mainline[1:]):
            relationships.append(FamilyRelationship(
                from_slug=prev.model_slug, to_slug=nxt.model_slug,
                relation_type="successor",
                generation_delta=nxt.generation_ordinal - prev.generation_ordinal,
                evidence=[{"type": "naming_grammar",
                           "detail": f"{prev.model} -> {nxt.model}"}],
                confidence="MEDIUM", status="confirmed"))
        for m in members:
            if m.variant_of:
                relationships.append(FamilyRelationship(
                    from_slug=m.variant_of, to_slug=m.model_slug,
                    relation_type="variant", generation_delta=0,
                    evidence=[{"type": "naming_grammar",
                               "detail": f"variant suffix {m.variant_suffixes}"}],
                    confidence="MEDIUM", status="confirmed"))

        # stable/variable over mainline members only (variants excluded),
        # one vote per unique logical model (duplicate rows collapsed —
        # P1 audit Finding 1: dup S510/S550-style rows must not fake a
        # multi-member family past the single-member guard).
        mainline_recs = [rec for rec, parse in entries if not parse.is_variant]
        voting_recs, _ = dedupe_logical_models(mainline_recs)
        stable, variable, indet = compute_field_classes(voting_recs)
        all_idents = {m.model_ident for m in members}
        dup_rows = len(members) - len(all_idents)

        # model_family marketing strings: corroboration display only
        corro = sorted({rec.get("model_family") for rec, _ in entries
                       if rec.get("model_family")})

        evidence_type = ("naming_grammar"
                         if entries[0][1].kind == "parsed" else "generic_identity")
        nodes.append(FamilyNode(
            family_id=f"{mfr.replace(' ', '_')}_{eq}_{root}",
            manufacturer=mfr, equipment_type=eq, family_root=root,
            display_name=f"{mfr.title()} {root.upper()} family",
            members=members,
            unique_logical_models=len(all_idents),
            duplicate_model_ident_count=dup_rows,
            status="confirmed",
            evidence=[{"type": evidence_type, "detail": root}],
            stable_fields=stable, variable_fields=variable,
            indeterminate_fields=indet,
            model_family_corroboration={"values": corro,
                                        "identity_use": "forbidden"},
            registry_checksum=registry_checksums.get(eq, ""),
            built_at=built_at))

    # No automatic cross-root succession. Manual seeds would land here with
    # mandatory OEM evidence; none ship in Session 3.
    assert not manual_seeds, "manual seed edges require OEM evidence review"

    metrics = {"per_type": {}, "stop_gate": {}, "totals": {}}
    gate_pass = True
    for eq, c in per_type_counts.items():
        denom = c["production_total"]
        rate = (c["assigned"] / denom) if denom else 0.0
        target = STOP_GATE_TARGETS.get(eq)
        passed = (rate >= target) if target is not None else None
        if passed is False:
            gate_pass = False
        metrics["per_type"][eq] = {**c, "assignment_rate": round(rate, 4)}
        if target is not None:
            metrics["stop_gate"][eq] = {
                "target": target, "rate": round(rate, 4),
                "result": "PASS" if passed else "FAIL"}
    silently_assigned = [a for a in ambiguous_records
                         if any(a["model_slug"] == m.model_slug
                                for n in nodes for m in n.members)]
    metrics["totals"] = {
        "families": len(nodes),
        "relationships": len(relationships),
        "ambiguous_records": len(ambiguous_records),
        "silent_ambiguous_assignments": len(silently_assigned),
        # member counts by UNIQUE logical model — duplicate same-model rows
        # must not count a family as multi-member (P1 audit Finding 1)
        "single_member_families": sum(1 for n in nodes
                                      if n.unique_logical_models == 1),
        "multi_member_families": sum(1 for n in nodes
                                     if n.unique_logical_models > 1),
        "families_with_duplicate_rows": sum(
            1 for n in nodes if n.duplicate_model_ident_count > 0),
        "duplicate_rows_collapsed": sum(
            n.duplicate_model_ident_count for n in nodes),
    }
    metrics["stop_gate"]["overall"] = (
        "PASS" if gate_pass and not silently_assigned else "FAIL")

    return {
        "graph_version": GRAPH_VERSION,
        "built_at": built_at,
        "built_from": registry_checksums,
        "policy": {
            "identity": "manufacturer + equipment_type + grammar root only",
            "cross_manufacturer_linking": "forbidden (incl. Gehl/Mustang)",
            "automatic_cross_root_succession": "forbidden (manual seeds only)",
            "model_family_field": "corroboration only, never identity",
            "tri_state_fields": "never family-stable",
            "single_member_families": "count as assigned",
            "production_statuses": sorted(PRODUCTION_STATUSES),
        },
        "families": [n.to_dict() for n in nodes],
        "relationships": [r.to_dict() for r in relationships],
        "ambiguous_records": ambiguous_records,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Summary + CLI
# ---------------------------------------------------------------------------

def _write_summary(graph: dict, path: Path) -> None:
    m = graph["metrics"]
    fams = sorted(graph["families"],
                  key=lambda f: -f["unique_logical_models"])
    lines = [
        "# CTL + SSL Family Graph — Build Summary",
        "",
        f"Built: {graph['built_at']}  |  graph_version {graph['graph_version']}",
        "",
        "## Stop Gate",
        "",
        "| Equipment type | Target | Rate | Result |",
        "|---|---|---|---|",
    ]
    for eq, g in m["stop_gate"].items():
        if eq == "overall":
            continue
        lines.append(f"| {eq} | {g['target']:.0%} | {g['rate']:.1%} | {g['result']} |")
    lines += [
        "",
        f"**Overall stop gate: {m['stop_gate']['overall']}** "
        f"(silent ambiguous assignments: "
        f"{m['totals']['silent_ambiguous_assignments']})",
        "",
        "## Counts",
        "",
    ]
    for eq, c in m["per_type"].items():
        lines.append(
            f"- **{eq}**: {c['records_total']} records, "
            f"{c['production_total']} production, {c['assigned']} assigned "
            f"({c['assignment_rate']:.1%}), {c['ambiguous']} ambiguous, "
            f"{c['excluded_status']} excluded by status")
    t = m["totals"]
    lines += [
        f"- Families: {t['families']} "
        f"({t['multi_member_families']} multi-member, "
        f"{t['single_member_families']} single-member, by unique logical "
        f"model)",
        f"- Duplicate same-model rows collapsed from voting: "
        f"{t['duplicate_rows_collapsed']} across "
        f"{t['families_with_duplicate_rows']} families (rows remain as "
        f"member references; one vote per logical model)",
        f"- Relationships: {t['relationships']}",
        f"- Manual successor seed edges: 0 (require OEM evidence; none "
        f"shipped in Session 3)",
        "",
        "## Top 10 Largest Families",
        "",
        "| Family | Unique models | Duplicate rows | Models |",
        "|---|---|---|---|",
    ]
    for f in fams[:10]:
        models = ", ".join(mm["model"] for mm in f["members"])
        lines.append(f"| {f['family_id']} | {f['unique_logical_models']} | "
                     f"{f['duplicate_model_ident_count']} | {models} |")
    lines += ["", "## Ambiguous Records (flagged, not assigned)", ""]
    if graph["ambiguous_records"]:
        for a in graph["ambiguous_records"]:
            lines.append(f"- `{a['manufacturer']} {a['model']}` "
                         f"({a['equipment_type']}): {a['reason']}")
    else:
        lines.append("- none")
    lines += [
        "",
        "## Policy (locked)",
        "",
    ] + [f"- {k}: {v}" for k, v in graph["policy"].items()
         if k != "production_statuses"] + [
        f"- production statuses counted: "
        f"{', '.join(graph['policy']['production_statuses'])}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_from_active(out_dir=DEFAULT_OUT_DIR) -> dict:
    """Build the graph from the active CTL + SSL registries and write the
    JSON artifact + markdown summary. Prints the extraction summary."""
    records_by_type, checksums = {}, {}
    for eq, path in ACTIVE_REGISTRIES.items():
        records_by_type[eq] = load_registry(path)
        checksums[eq] = _file_checksum(path)
    graph = build_graph(records_by_type, registry_checksums=checksums)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / GRAPH_FILENAME).write_text(
        json.dumps(graph, indent=1), encoding="utf-8")
    _write_summary(graph, out_dir / SUMMARY_FILENAME)

    m = graph["metrics"]
    print("=== Family Graph extraction summary ===")
    for eq, c in m["per_type"].items():
        print(f"{eq}: {c['records_total']} reviewed | "
              f"{c['production_total']} production | "
              f"{c['assigned']} assigned ({c['assignment_rate']:.1%}) | "
              f"{c['ambiguous']} ambiguous")
    t = m["totals"]
    print(f"families: {t['families']} | relationships: {t['relationships']} | "
          f"ambiguous: {t['ambiguous_records']} | "
          f"silent ambiguous assignments: {t['silent_ambiguous_assignments']}")
    fams = sorted(graph["families"],
                  key=lambda f: -f["unique_logical_models"])[:10]
    print("top 10 families (by unique logical models):")
    for f in fams:
        dup = f["duplicate_model_ident_count"]
        print(f"  {f['family_id']}: {f['unique_logical_models']} models"
              + (f" (+{dup} duplicate rows)" if dup else ""))
    for eq, g in m["stop_gate"].items():
        if eq != "overall":
            print(f"stop gate {eq}: {g['rate']:.1%} vs {g['target']:.0%} "
                  f"-> {g['result']}")
    print(f"STOP GATE OVERALL: {m['stop_gate']['overall']}")
    return graph


if __name__ == "__main__":
    build_from_active()
