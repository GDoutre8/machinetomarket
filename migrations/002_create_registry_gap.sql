-- Session 2: Gap Detection Pipeline — registry_gap table.
-- Postgres dialect (target for server-side promotion). The local SQLite
-- store created by gap_detector.py mirrors this schema 1:1 with type
-- mapping UUID/TIMESTAMPTZ/JSONB -> TEXT.
--
-- Explicit count naming per schema review: miss_count_all_time (not the
-- ambiguous miss_count).
--
-- demand_score = (miss_count_30d * 3) + (miss_count_all_time * 1)
--              + (unique_dealer_count * 5)
-- priority_tier: P0 if miss_count_30d >= 30 OR unique_dealer_count >= 3
--                P1 if 10 <= miss_count_30d <= 29
--                P2 if 3 <= miss_count_30d <= 9
--                P3 if miss_count_30d < 3

CREATE TABLE IF NOT EXISTS registry_gap (
    gap_id              UUID PRIMARY KEY,
    normalized_make     TEXT,
    normalized_model    TEXT,
    category            TEXT,
    first_seen          TIMESTAMPTZ,
    last_seen           TIMESTAMPTZ,
    miss_count_all_time INT DEFAULT 1,
    miss_count_30d      INT DEFAULT 1,
    unique_dealer_count INT DEFAULT 1,
    raw_variants        JSONB,
    status              TEXT DEFAULT 'open',
    demand_score        FLOAT,
    priority_tier       TEXT,
    research_packet_id  TEXT,
    UNIQUE (normalized_make, normalized_model)
);

CREATE INDEX IF NOT EXISTS idx_registry_gap_priority
    ON registry_gap (priority_tier, demand_score);

CREATE INDEX IF NOT EXISTS idx_registry_gap_status
    ON registry_gap (status);
