-- Session 2 patch 2 (Codex P1): upgrade pre-patch gap-detection schemas
-- (databases created from the original 001/002) to the current schema.
-- Postgres dialect; idempotent — safe to run on already-current databases.
--
-- Upgrades performed:
--   * lookup_event: add normalized_category where missing; rebuild the
--     norm-key index to include it.
--   * registry_gap: add normalized_category where missing (backfilled from
--     the old raw category column when present); migrate any legacy
--     miss_count column to miss_count_all_time; replace the old
--     (normalized_make, normalized_model) unique identity with
--     (normalized_make, normalized_model, normalized_category);
--     default unique_dealer_count to 0.
--
-- The local SQLite store performs the equivalent upgrade automatically in
-- gap_detector.py (schema-version detection via PRAGMA user_version; see
-- _init_schema/_migrate_sqlite). An unreadable/unmigratable local DB is
-- backed up and recreated with a loud warning — telemetry is never allowed
-- to break lookups.

-- ── lookup_event ───────────────────────────────────────────────────────────

ALTER TABLE lookup_event ADD COLUMN IF NOT EXISTS normalized_category TEXT;

UPDATE lookup_event
   SET normalized_category = COALESCE(normalized_category, LOWER(category), '')
 WHERE normalized_category IS NULL;

DROP INDEX IF EXISTS idx_lookup_event_norm_key;
CREATE INDEX IF NOT EXISTS idx_lookup_event_norm_key
    ON lookup_event (normalized_make, normalized_model, normalized_category, match_tier);

-- ── registry_gap ───────────────────────────────────────────────────────────

ALTER TABLE registry_gap ADD COLUMN IF NOT EXISTS normalized_category TEXT;

DO $$
BEGIN
    -- Backfill from the legacy raw category column when it exists.
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'registry_gap' AND column_name = 'category') THEN
        UPDATE registry_gap
           SET normalized_category = COALESCE(normalized_category, LOWER(category), '')
         WHERE normalized_category IS NULL;
        ALTER TABLE registry_gap DROP COLUMN category;
    ELSE
        UPDATE registry_gap
           SET normalized_category = COALESCE(normalized_category, '')
         WHERE normalized_category IS NULL;
    END IF;

    -- Legacy count column rename (only if a pre-rename database exists).
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'registry_gap' AND column_name = 'miss_count')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'registry_gap' AND column_name = 'miss_count_all_time') THEN
        ALTER TABLE registry_gap RENAME COLUMN miss_count TO miss_count_all_time;
    END IF;

    -- Replace the two-column unique identity with the three-column identity.
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'registry_gap_normalized_make_normalized_model_key') THEN
        ALTER TABLE registry_gap
            DROP CONSTRAINT registry_gap_normalized_make_normalized_model_key;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'registry_gap_norm_identity_key') THEN
        ALTER TABLE registry_gap
            ADD CONSTRAINT registry_gap_norm_identity_key
            UNIQUE (normalized_make, normalized_model, normalized_category);
    END IF;
END $$;

ALTER TABLE registry_gap ALTER COLUMN unique_dealer_count SET DEFAULT 0;
