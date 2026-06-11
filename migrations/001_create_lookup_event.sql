-- Session 2: Gap Detection Pipeline — lookup_event table.
-- Postgres dialect (target for server-side promotion). The local SQLite
-- store created by gap_detector.py mirrors this schema 1:1 with type
-- mapping UUID/TIMESTAMPTZ/JSONB -> TEXT.

CREATE TABLE IF NOT EXISTS lookup_event (
    lookup_event_id     UUID PRIMARY KEY,
    timestamp           TIMESTAMPTZ NOT NULL,
    dealer_id           TEXT,
    make                TEXT,
    model               TEXT,
    year                INT,
    category            TEXT,
    normalized_make     TEXT,
    normalized_model    TEXT,
    matched_record_id   TEXT,
    match_tier          TEXT,
    resolution_path     TEXT,
    session_id          TEXT
);

CREATE INDEX IF NOT EXISTS idx_lookup_event_norm_key
    ON lookup_event (normalized_make, normalized_model, match_tier);

CREATE INDEX IF NOT EXISTS idx_lookup_event_timestamp
    ON lookup_event (timestamp);
