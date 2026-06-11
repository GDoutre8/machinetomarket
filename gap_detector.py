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

``miss_count_all_time`` advances by an atomic SQL increment (one per miss);
``miss_count_30d`` and ``unique_dealer_count`` are recomputed from
``lookup_event`` on every upsert and merged non-regressively on conflict
(see ``_UPSERT_SQL``), so stale concurrent writers can never lower a
fresher aggregate.

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
import time
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

# Current local schema version, stored in PRAGMA user_version. Bump whenever
# the SQLite schema changes; _init_schema migrates or safely resets old DBs.
SCHEMA_VERSION = 2

# How many times the lookup_event insert is retried on transient SQLite
# write contention (database locked) before failing open.
EVENT_INSERT_RETRIES = 2

# Paths whose schema has already been verified this process — avoids
# rerunning DDL/migration checks on every lookup (Codex audit #4).
_initialized_paths: set[str] = set()


def configure(db_path: str) -> None:
    """Point the detector at a different database file (used by tests)."""
    global _db_path
    _db_path = db_path


def _table_columns(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_sqlite(conn) -> None:
    """Upgrade a pre-patch local DB in place (SQLite mirror of migration 003).

    - lookup_event: add normalized_category (backfilled from raw category).
    - registry_gap: rebuild with normalized_category (backfilled from the old
      raw category column), miss_count -> miss_count_all_time if present, and
      the three-column unique identity.
    Raises on failure; the caller backs up and recreates the DB.
    """
    event_cols = _table_columns(conn, "lookup_event")
    if event_cols and "normalized_category" not in event_cols:
        conn.execute("ALTER TABLE lookup_event ADD COLUMN normalized_category TEXT")
        conn.execute("UPDATE lookup_event SET normalized_category ="
                     " LOWER(COALESCE(category, ''))")
        conn.execute("DROP INDEX IF EXISTS idx_lookup_event_norm_key")

    gap_cols = _table_columns(conn, "registry_gap")
    if gap_cols and "normalized_category" not in gap_cols:
        count_col = "miss_count_all_time" if "miss_count_all_time" in gap_cols else (
            "miss_count" if "miss_count" in gap_cols else "1")
        category_src = "LOWER(COALESCE(category, ''))" if "category" in gap_cols else "''"
        conn.execute("ALTER TABLE registry_gap RENAME TO registry_gap_old")
        conn.execute("DROP INDEX IF EXISTS idx_registry_gap_priority")
        conn.execute("DROP INDEX IF EXISTS idx_registry_gap_status")
        conn.executescript(_SCHEMA)  # recreate registry_gap with current DDL
        conn.execute(
            "INSERT INTO registry_gap (gap_id, normalized_make, normalized_model,"
            " normalized_category, first_seen, last_seen, miss_count_all_time,"
            " miss_count_30d, unique_dealer_count, raw_variants, status,"
            " demand_score, priority_tier, research_packet_id)"
            f" SELECT gap_id, normalized_make, normalized_model, {category_src},"
            f" first_seen, last_seen, COALESCE({count_col}, 1),"
            " COALESCE(miss_count_30d, 1), COALESCE(unique_dealer_count, 0),"
            " raw_variants, status, demand_score, priority_tier,"
            " research_packet_id FROM registry_gap_old")
        conn.execute("DROP TABLE registry_gap_old")


def _init_schema(conn) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < SCHEMA_VERSION:
        _migrate_sqlite(conn)          # no-op on fresh or already-current DBs
        conn.executescript(_SCHEMA)    # create anything missing + indexes
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()


def _reset_db() -> None:
    """Back up an unreadable/unmigratable local DB and start fresh."""
    backup = f"{_db_path}.unmigratable.bak"
    try:
        if os.path.exists(backup):
            os.remove(backup)
        os.replace(_db_path, backup)
    except OSError:
        os.remove(_db_path)
        backup = "(deleted — backup rename failed)"
    logger.warning(
        "gap telemetry DB at %s could not be migrated to schema v%s; "
        "it was moved to %s and a fresh DB was created. Lookup behavior "
        "is unaffected.", _db_path, SCHEMA_VERSION, backup)


def _connect() -> sqlite3.Connection:
    # TODO(production hardening): synchronous SQLite writes on the lookup
    # path should move to an async/queued or Postgres-backed telemetry
    # writer. Deliberately not redesigned in Session 2 — WAL + busy timeout
    # + fail-open + sub-10ms writes are acceptable for now.
    conn = sqlite3.connect(_db_path, timeout=2.0)
    if _db_path not in _initialized_paths:
        try:
            conn.execute("PRAGMA busy_timeout = 2000")
            _init_schema(conn)
        except Exception:
            logger.warning("gap telemetry schema init/migration failed; "
                           "resetting local DB", exc_info=True)
            conn.close()
            _reset_db()
            conn = sqlite3.connect(_db_path, timeout=2.0)
            conn.execute("PRAGMA busy_timeout = 2000")
            _init_schema(conn)
        _initialized_paths.add(_db_path)
    else:
        conn.execute("PRAGMA busy_timeout = 2000")
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


# Fallback alias map used only if mtm_registry_lookup is unavailable.
_CATEGORY_FALLBACK_ALIASES = {
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


def normalize_category(category: str) -> str:
    """Resolve category aliases to the canonical MTM equipment_type.

    Reuses the canonical alias logic in mtm_registry_lookup (lazy import —
    that module imports gap_detector, so a top-level import would be
    circular). Unrecognized categories fall back to a stable
    lowercase/underscore form so they still dedup against themselves.
    """
    if not category:
        return ""
    key = re.sub(r"\s+", " ", category.strip().lower())
    try:
        from mtm_registry_lookup import _resolve_eq_type
        canonical = _resolve_eq_type(key) or _resolve_eq_type(key.replace("_", " "))
        if canonical:
            return canonical
    except Exception:
        canonical = _CATEGORY_FALLBACK_ALIASES.get(key)
        if canonical:
            return canonical
    return re.sub(r"\s+", "_", key)


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


# Stale-writer protection window for miss_count_30d (seconds). Within this
# window of the row's last_seen, concurrent recomputes merge via MAX (a stale
# writer can never lower a fresher writer's count); outside it, the fresh
# recompute wins so the rolling 30-day window can decay correctly.
CONCURRENCY_WINDOW_S = 60

# Non-regressing aggregate expressions used in the ON CONFLICT clause.
#   miss_count_all_time: pure atomic increment — exact under concurrency
#       (one increment per miss event), never overwritten by a stale
#       precomputed total.
#   miss_count_30d: MAX merge inside the concurrency window, fresh recompute
#       outside it (documented trade-off: exact rolling recompute inside a
#       single upsert is not race-safe).
#   unique_dealer_count: all-time distinct count never legitimately
#       decreases -> plain MAX merge.
_SQL_ALL = "registry_gap.miss_count_all_time + 1"
_SQL_30D = ("CASE WHEN registry_gap.last_seen >= :recent"
            " THEN MAX(registry_gap.miss_count_30d, :miss_30d)"
            " ELSE :miss_30d END")
_SQL_DLR = "MAX(registry_gap.unique_dealer_count, :dealers)"

_UPSERT_SQL = f"""
INSERT INTO registry_gap (gap_id, normalized_make, normalized_model,
 normalized_category, first_seen, last_seen, miss_count_all_time,
 miss_count_30d, unique_dealer_count, raw_variants, status, demand_score,
 priority_tier, research_packet_id)
VALUES (:gap_id, :make, :model, :category, :now, :now, 1, :miss_30d,
 :dealers, :variants, 'open', :score, :tier, NULL)
ON CONFLICT (normalized_make, normalized_model, normalized_category)
DO UPDATE SET
 last_seen = :now,
 miss_count_all_time = {_SQL_ALL},
 miss_count_30d = {_SQL_30D},
 unique_dealer_count = {_SQL_DLR},
 raw_variants = :variants,
 demand_score = ({_SQL_30D}) * 3.0 + ({_SQL_ALL}) * 1.0 + ({_SQL_DLR}) * 5.0,
 priority_tier = CASE
     WHEN ({_SQL_30D}) >= 30 OR ({_SQL_DLR}) >= 3 THEN 'P0'
     WHEN ({_SQL_30D}) >= 10 THEN 'P1'
     WHEN ({_SQL_30D}) >= 3 THEN 'P2'
     ELSE 'P3' END
"""


def _upsert_gap(conn, *, now, norm_make, norm_model, norm_category,
                raw_variant: str) -> None:
    """Atomic, non-regressing upsert keyed on (normalized_make,
    normalized_model, normalized_category).

    The caller's lookup_event row is already committed, so the recomputed
    miss_count_30d / unique_dealer_count include this event. On conflict the
    aggregates are merged in SQL (see _SQL_* above) so a stale writer can
    never overwrite a newer/larger value, and miss_count_all_time advances
    by exactly one per recorded miss. gap_id, first_seen, status, and
    research_packet_id are never modified on conflict.
    """
    cutoff = _iso(now - timedelta(days=30))
    key = (norm_make, norm_model, norm_category)
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

    conn.execute(_UPSERT_SQL, {
        "gap_id": str(uuid.uuid4()),
        "make": norm_make, "model": norm_model, "category": norm_category,
        "now": _iso(now),
        "recent": _iso(now - timedelta(seconds=CONCURRENCY_WINDOW_S)),
        "miss_30d": miss_30d,
        "dealers": unique_dealers,
        "variants": json.dumps(variants),
        # Insert-path score/tier; the conflict path recomputes them in SQL.
        "score": compute_demand_score(miss_30d, 1, unique_dealers),
        "tier": assign_priority_tier(miss_30d, unique_dealers),
    })


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
            # never lost if the gap upsert fails (Codex audit #2), and is
            # retried on transient write contention (Codex P2 #4).
            for attempt in range(EVENT_INSERT_RETRIES + 1):
                try:
                    event_id = _insert_lookup_event(
                        conn, now=now, dealer_id=dealer_id, make=make,
                        model=model, year=year, category=category,
                        norm_make=norm_make, norm_model=norm_model,
                        norm_category=norm_category,
                        matched_record_id=matched_record_id,
                        match_tier=match_tier,
                        resolution_path=resolution_path,
                        session_id=session_id)
                    conn.commit()
                    break
                except sqlite3.OperationalError:
                    if attempt >= EVENT_INSERT_RETRIES:
                        raise
                    time.sleep(0.005 * (attempt + 1))

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
