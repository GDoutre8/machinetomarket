"""MTM Gap Detection Pipeline — lookup telemetry layer (Session 2).

Turns every registry lookup miss into structured, persistent, demand-scored
data. No dashboard, no research packets, no candidate generation, no
approval workflow — storage and scoring only.

Storage
-------
Local SQLite database (default ``telemetry/gap_telemetry.db``; override with
the ``MTM_GAP_DB`` environment variable or :func:`configure`). The schema
mirrors ``migrations/001_create_lookup_event.sql`` and
``migrations/002_create_registry_gap.sql`` exactly, with the Postgres types
UUID / TIMESTAMPTZ / JSONB stored as TEXT.

Definition of a miss (Session 2)
--------------------------------
A lookup is a miss only when the lookup returned NO registry record at all:
``result["match"] is False`` and ``reason != "ambiguous_model"`` and the
input carried a parseable make and/or model. Stub, coverage_only, and
production_candidate records return ``match=True`` and are therefore never
misses. Ambiguous results are logged to ``lookup_event`` with
``match_tier="ambiguous"`` only; inputs with no make and no model are logged
as ``match_tier="invalid_input"`` only. Neither touches ``registry_gap``.

Demand scoring
--------------
demand_score = (miss_count_30d * 3) + (miss_count_all_time * 1)
             + (unique_dealer_count * 5)

priority tiers:
    P0  miss_count_30d >= 30 OR unique_dealer_count >= 3
    P1  10 <= miss_count_30d <= 29
    P2  3 <= miss_count_30d <= 9
    P3  miss_count_30d < 3

Counts are recomputed from ``lookup_event`` rows on every upsert, so
``registry_gap`` can never drift from the event log.

Gap identity is ``(normalized_make, normalized_model, normalized_category)``
— the same make/model missed in two different equipment categories produces
two separate gaps. Anonymous misses (blank dealer_id) contribute 0 to
``unique_dealer_count``; the +5 score term requires a real dealer_id.

Fail-open guarantee
-------------------
Every public function catches all exceptions, logs a warning, and returns
``None``. Telemetry can never break or change a lookup result.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("gap_detector")

_DEFAULT_DB = Path(__file__).resolve().parent / "telemetry" / "gap_telemetry.db"
_db_path: str = os.environ.get("MTM_GAP_DB", str(_DEFAULT_DB))

MAX_RAW_VARIANTS = 25

# Minimal manufacturer alias map for normalization only (priority makes).
# Intentionally independent of mtm_registry_lookup to avoid a circular import.
MAKE_ALIASES = {
    "bobcat": "bobcat",
    "caterpillar": "caterpillar", "cat": "caterpillar",
    "john deere": "john deere", "johndeere": "john deere",
    "deere": "john deere", "jd": "john deere",
    "new holland": "new holland", "newholland": "new holland", "nh": "new holland",
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
    "komatsu": "komatsu",
    "hitachi": "hitachi",
    "doosan": "doosan",
    "develon": "develon",
    "hyundai": "hyundai",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lookup_event (
    lookup_event_id     TEXT PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    dealer_id           TEXT,
    make                TEXT,
    model               TEXT,
    year                INTEGER,
    category            TEXT,
    normalized_make     TEXT,
    normalized_model    TEXT,
    normalized_category TEXT,
    matched_record_id   TEXT,
    match_tier          TEXT,
    resolution_path     TEXT,
    session_id          TEXT
);
CREATE INDEX IF NOT EXISTS idx_lookup_event_norm_key
    ON lookup_event (normalized_make, normalized_model, normalized_category, match_tier);
CREATE INDEX IF NOT EXISTS idx_lookup_event_timestamp
    ON lookup_event (timestamp);

CREATE TABLE IF NOT EXISTS registry_gap (
    gap_id              TEXT PRIMARY KEY,
    normalized_make     TEXT,
    normalized_model    TEXT,
    normalized_category TEXT,
    first_seen          TEXT,
    last_seen           TEXT,
    miss_count_all_time INTEGER DEFAULT 1,
    miss_count_30d      INTEGER DEFAULT 1,
    unique_dealer_count INTEGER DEFAULT 0,
    raw_variants        TEXT,
    status              TEXT DEFAULT 'open',
    demand_score        REAL,
    priority_tier       TEXT,
    research_packet_id  TEXT,
    UNIQUE (normalized_make, normalized_model, normalized_category)
);
CREATE INDEX IF NOT EXISTS idx_registry_gap_priority
    ON registry_gap (priority_tier, demand_score);
CREATE INDEX IF NOT EXISTS idx_registry_gap_status
    ON registry_gap (status);
"""

# Paths whose schema has already been applied this process — avoids rerunning
# DDL on every lookup (Codex audit #4).
_initialized_paths: set[str] = set()


def configure(db_path: str) -> None:
    """Point the detector at a different database file (used by tests)."""
    global _db_path
    _db_path = db_path


def _connect() -> sqlite3.Connection:
    # TODO(production hardening): synchronous SQLite writes on the lookup
    # path should move to an async/queued telemetry writer. Deliberately not
    # redesigned in Session 2 — fail-open + sub-10ms writes are acceptable
    # for now.
    conn = sqlite3.connect(_db_path, timeout=2.0)
    if _db_path not in _initialized_paths:
        conn.executescript(_SCHEMA)
        _initialized_paths.add(_db_path)
    return conn


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_make(make: str) -> str:
    """Canonical lowercase manufacturer ('CAT ' -> 'caterpillar')."""
    if not make:
        return ""
    key = re.sub(r"[^a-z0-9 ]", "", make.strip().lower())
    key = re.sub(r"\s+", " ", key)
    return MAKE_ALIASES.get(key, key)


def _split_embedded_make(model: str) -> tuple[str, str]:
    """If the model string starts with a known make ('Kubota SVL75-3'),
    return (canonical_make, remainder); else ('', model)."""
    tokens = model.strip().split()
    for take in (2, 1):  # two-word makes first ("new holland", "wacker neuson")
        if len(tokens) > take:
            head = " ".join(tokens[:take]).lower()
            head = re.sub(r"[^a-z0-9 ]", "", head)
            if head in MAKE_ALIASES:
                return MAKE_ALIASES[head], " ".join(tokens[take:])
    return "", model


def normalize_model(model: str, make: str = "") -> tuple[str, str]:
    """Normalize a raw model string for dedup.

    Returns (normalized_make, normalized_model). The make is resolved from
    the explicit ``make`` argument first, falling back to a make embedded at
    the start of the model string ('Kubota SVL75-3'). The model is lowercased
    with the embedded make removed and all non-alphanumerics stripped, so
    'SVL75-3', 'svl 75-3', 'SVL753', and 'Kubota SVL75-3' all normalize to
    'svl753'.
    """
    norm_make = normalize_make(make)
    rest = model or ""
    embedded_make, remainder = _split_embedded_make(rest)
    if embedded_make:
        if not norm_make or norm_make == embedded_make:
            norm_make = embedded_make
            rest = remainder
    norm_model = re.sub(r"[^a-z0-9]", "", rest.lower())
    return norm_make, norm_model


def normalize_category(category: str) -> str:
    if not category:
        return ""
    return re.sub(r"\s+", "_", category.strip().lower())


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_demand_score(miss_count_30d: int, miss_count_all_time: int,
                         unique_dealer_count: int) -> float:
    return float((miss_count_30d * 3) + (miss_count_all_time * 1)
                 + (unique_dealer_count * 5))


def assign_priority_tier(miss_count_30d: int, unique_dealer_count: int) -> str:
    if miss_count_30d >= 30 or unique_dealer_count >= 3:
        return "P0"
    if miss_count_30d >= 10:
        return "P1"
    if miss_count_30d >= 3:
        return "P2"
    return "P3"


# ---------------------------------------------------------------------------
# Event + gap writes (internal, exceptions propagate to the public wrappers)
# ---------------------------------------------------------------------------

def _insert_lookup_event(conn, *, now, dealer_id, make, model, year, category,
                         norm_make, norm_model, norm_category,
                         matched_record_id, match_tier, resolution_path,
                         session_id) -> str:
    event_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO lookup_event (lookup_event_id, timestamp, dealer_id, make,"
        " model, year, category, normalized_make, normalized_model,"
        " normalized_category, matched_record_id, match_tier, resolution_path,"
        " session_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, _iso(now), dealer_id or "", make or "", model or "",
         int(year) if year else None, category or "", norm_make, norm_model,
         norm_category, matched_record_id, match_tier, resolution_path,
         session_id or ""),
    )
    return event_id


def _upsert_gap(conn, *, now, norm_make, norm_model, norm_category,
                raw_variant: str) -> None:
    """Atomic upsert keyed on (normalized_make, normalized_model,
    normalized_category). Counts are recomputed from lookup_event."""
    cutoff = _iso(now - timedelta(days=30))
    key = (norm_make, norm_model, norm_category)
    miss_all = conn.execute(
        "SELECT COUNT(*) FROM lookup_event WHERE normalized_make=? AND"
        " normalized_model=? AND normalized_category=? AND match_tier='miss'",
        key).fetchone()[0]
    miss_30d = conn.execute(
        "SELECT COUNT(*) FROM lookup_event WHERE normalized_make=? AND"
        " normalized_model=? AND normalized_category=? AND match_tier='miss'"
        " AND timestamp>=?",
        key + (cutoff,)).fetchone()[0]
    # Anonymous/blank dealer_id contributes 0 unique dealers (Codex audit #3).
    unique_dealers = conn.execute(
        "SELECT COUNT(DISTINCT dealer_id) FROM lookup_event WHERE"
        " normalized_make=? AND normalized_model=? AND normalized_category=?"
        " AND match_tier='miss' AND dealer_id != ''",
        key).fetchone()[0]

    score = compute_demand_score(miss_30d, miss_all, unique_dealers)
    tier = assign_priority_tier(miss_30d, unique_dealers)

    row = conn.execute(
        "SELECT raw_variants FROM registry_gap WHERE normalized_make=? AND"
        " normalized_model=? AND normalized_category=?",
        key).fetchone()
    try:
        variants = json.loads(row[0]) if row and row[0] else []
    except (TypeError, ValueError):
        variants = []
    if raw_variant and raw_variant not in variants and len(variants) < MAX_RAW_VARIANTS:
        variants.append(raw_variant)

    # Atomic upsert: concurrent writers cannot produce duplicate gap rows.
    # gap_id, first_seen, status, research_packet_id are preserved on conflict.
    conn.execute(
        "INSERT INTO registry_gap (gap_id, normalized_make, normalized_model,"
        " normalized_category, first_seen, last_seen, miss_count_all_time,"
        " miss_count_30d, unique_dealer_count, raw_variants, status,"
        " demand_score, priority_tier, research_packet_id)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,'open',?,?,NULL)"
        " ON CONFLICT (normalized_make, normalized_model, normalized_category)"
        " DO UPDATE SET last_seen=excluded.last_seen,"
        " miss_count_all_time=excluded.miss_count_all_time,"
        " miss_count_30d=excluded.miss_count_30d,"
        " unique_dealer_count=excluded.unique_dealer_count,"
        " raw_variants=excluded.raw_variants,"
        " demand_score=excluded.demand_score,"
        " priority_tier=excluded.priority_tier",
        (str(uuid.uuid4()), norm_make, norm_model, norm_category, _iso(now),
         _iso(now), miss_all, miss_30d, unique_dealers, json.dumps(variants),
         score, tier),
    )


def _classify_result(make: str, model: str, result: Optional[dict]) -> tuple[str, Optional[str], Optional[str]]:
    """Return (match_tier, matched_record_id, resolution_path) for a lookup result."""
    if result is None:
        result = {}
    if result.get("match"):
        record = result.get("full_record") or {}
        return (
            result.get("match_method") or "matched",
            record.get("model_slug") or result.get("model"),
            result.get("normalized_query"),
        )
    reason = result.get("reason") or ""
    if reason == "ambiguous_model":
        return "ambiguous", None, reason
    if not (make or "").strip() and not (model or "").strip():
        return "invalid_input", None, reason
    return "miss", None, reason


# ---------------------------------------------------------------------------
# Public API — all fail-open
# ---------------------------------------------------------------------------

def record_lookup(
    make: str = "",
    model: str = "",
    year=None,
    category: str = "",
    result: Optional[dict] = None,
    session_id: str = "",
    dealer_id: str = "",
) -> Optional[str]:
    """Record one lookup attempt (hit, miss, ambiguous, or invalid).

    Writes a ``lookup_event`` row for every attempt; upserts ``registry_gap``
    only when the attempt classifies as a true miss. Returns the
    lookup_event_id, or None on any telemetry failure (fail-open).
    """
    try:
        match_tier, matched_record_id, resolution_path = _classify_result(make, model, result)
        norm_make, norm_model = normalize_model(model or "", make or "")
        norm_category = normalize_category(category)
        now = _utcnow()
        conn = _connect()
        try:
            # Event insert commits on its own so the lookup_event row is
            # never lost if the gap upsert fails (Codex audit #2).
            event_id = _insert_lookup_event(
                conn, now=now, dealer_id=dealer_id, make=make, model=model,
                year=year, category=category, norm_make=norm_make,
                norm_model=norm_model, norm_category=norm_category,
                matched_record_id=matched_record_id, match_tier=match_tier,
                resolution_path=resolution_path, session_id=session_id)
            conn.commit()

            if match_tier == "miss" and norm_model:
                try:
                    raw_variant = " ".join(
                        p for p in ((make or "").strip(), (model or "").strip()) if p)
                    _upsert_gap(conn, now=now, norm_make=norm_make,
                                norm_model=norm_model,
                                norm_category=norm_category,
                                raw_variant=raw_variant)
                    conn.commit()
                except Exception:
                    logger.warning("registry_gap upsert failed; lookup_event"
                                   " preserved (fail-open)", exc_info=True)
            return event_id
        finally:
            conn.close()
    except Exception:
        logger.warning("gap telemetry write failed (fail-open)", exc_info=True)
        return None


def record_miss(
    make: str = "",
    model: str = "",
    year=None,
    category: str = "",
    session_id: str = "",
    dealer_id: str = "",
) -> Optional[str]:
    """Record a known lookup miss directly (Session 2 spec entry point)."""
    return record_lookup(
        make=make, model=model, year=year, category=category,
        result={"match": False, "reason": "no_match"},
        session_id=session_id, dealer_id=dealer_id,
    )
