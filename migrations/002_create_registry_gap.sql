-- Session 2: Gap Detection Pipeline — registry_gap table.
-- Postgres dialect (target for server-side promotion). The local SQLite
-- store created by gap_detector.py mirrors this schema 1:1 with type
-- mapping UUID/TIMESTAMPTZ/JSONB -> TEXT.
--
-- Patch (Codex audit):
--   #1 Gap identity is (normalized_make, normalized_model,
--      normalized_category) — same make/model in different equipment
--      categories are separate gaps. normalized_category is stored
--      explicitly (replaces the raw category column).
--   #2 Writers must use an atomic upsert against the unique constraint:
--        INSERT ... ON CONFLICT (normalized_make, normalized_model,
--                                normalized_category)
--        DO UPDATE SET last_seen, miss_count_all_time, miss_count_30d,
--                      unique_dealer_count, raw_variants, demand_score,
--                      priority_tier
--      (gap_id, first_seen, status, research_packet_id are never updated
--      on conflict).
--   #3 unique_dealer_count counts DISTINCT non-empty dealer_id only;
--      anonymous misses contribute 0, hence DEFAULT 0.
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
    normalized_category TEXT,
    first_seen          TIMESTAMPTZ,
    last_seen           TIMESTAMPTZ,
    miss_count_all_time INT DEFAULT 1,
    miss_count_30d      INT DEFAULT 1,
    unique_dealer_count INT DEFAULT 0,
    raw_variants        JSONB,
    status              TEXT DEFAULT 'open',
    demand_score        FLOAT,
    priority_tier       TEXT,
    research_packet_id  TEXT,
    UNIQUE (normalized_make, normalized_model, normalized_category)
);

CREATE INDEX IF NOT EXISTS idx_registry_gap_priority
    ON registry_gap (priority_tier, demand_score);

CREATE INDEX IF NOT EXISTS idx_registry_gap_status
    ON registry_gap (status);
