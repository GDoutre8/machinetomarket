-- Session 2 patch 3 (final blocker audit, Codex P1 #1): canonical category
-- backfill. Postgres dialect; idempotent.
--
-- Migration 003 backfilled normalized_category with LOWER(category), which
-- fragments identities: an old row backfilled to 'ctl' never merges with new
-- writes normalized to 'compact_track_loader'. This migration re-normalizes
-- both tables through the canonical alias map (mirrors
-- EQUIPMENT_TYPE_ALIASES in mtm_registry_lookup.py / normalize_category in
-- gap_detector.py), then collapses any registry_gap rows that now share an
-- identity. Counts on surviving rows may be temporarily stale; they are
-- healed on the next miss because every gap upsert recomputes aggregates
-- from lookup_event (the append-only source of truth).

CREATE OR REPLACE FUNCTION _mtm_canonical_category(raw TEXT) RETURNS TEXT AS $$
DECLARE
    key TEXT := LOWER(TRIM(COALESCE(raw, '')));
BEGIN
    RETURN CASE key
        -- skid_steer
        WHEN 'skid_steer' THEN 'skid_steer'
        WHEN 'skidsteer' THEN 'skid_steer'
        WHEN 'skid_steer_loader' THEN 'skid_steer'
        WHEN 'skidsteerloader' THEN 'skid_steer'
        WHEN 'ssl' THEN 'skid_steer'
        WHEN 'skid steer' THEN 'skid_steer'
        WHEN 'skid steer loader' THEN 'skid_steer'
        -- compact_track_loader
        WHEN 'compact_track_loader' THEN 'compact_track_loader'
        WHEN 'compacttrackloader' THEN 'compact_track_loader'
        WHEN 'ctl' THEN 'compact_track_loader'
        WHEN 'compact track loader' THEN 'compact_track_loader'
        WHEN 'track loader' THEN 'compact_track_loader'
        -- mini_excavator
        WHEN 'mini_excavator' THEN 'mini_excavator'
        WHEN 'miniexcavator' THEN 'mini_excavator'
        WHEN 'mini excavator' THEN 'mini_excavator'
        WHEN 'mini ex' THEN 'mini_excavator'
        WHEN 'miniex' THEN 'mini_excavator'
        WHEN 'mini_ex' THEN 'mini_excavator'
        -- backhoe_loader
        WHEN 'backhoe_loader' THEN 'backhoe_loader'
        WHEN 'backhoe' THEN 'backhoe_loader'
        WHEN 'backhoe loader' THEN 'backhoe_loader'
        WHEN 'bhl' THEN 'backhoe_loader'
        WHEN 'tractor loader backhoe' THEN 'backhoe_loader'
        WHEN 'tlb' THEN 'backhoe_loader'
        -- dozer
        WHEN 'dozer' THEN 'dozer'
        WHEN 'crawler_dozer' THEN 'dozer'
        WHEN 'crawler dozer' THEN 'dozer'
        WHEN 'bulldozer' THEN 'dozer'
        WHEN 'crawler tractor' THEN 'dozer'
        -- scissor_lift
        WHEN 'scissor_lift' THEN 'scissor_lift'
        WHEN 'scissor lift' THEN 'scissor_lift'
        WHEN 'scissors' THEN 'scissor_lift'
        WHEN 'scissorlift' THEN 'scissor_lift'
        WHEN 'slab scissor' THEN 'scissor_lift'
        -- boom_lift
        WHEN 'boom_lift' THEN 'boom_lift'
        WHEN 'boom lift' THEN 'boom_lift'
        WHEN 'boomlift' THEN 'boom_lift'
        WHEN 'articulating boom' THEN 'boom_lift'
        WHEN 'telescopic boom' THEN 'boom_lift'
        WHEN 'manlift' THEN 'boom_lift'
        WHEN 'man lift' THEN 'boom_lift'
        -- unrecognized: stable lowercase/underscore form
        ELSE REGEXP_REPLACE(key, '\s+', '_', 'g')
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

UPDATE lookup_event
   SET normalized_category = _mtm_canonical_category(normalized_category)
 WHERE normalized_category IS DISTINCT FROM _mtm_canonical_category(normalized_category);

UPDATE registry_gap
   SET normalized_category = _mtm_canonical_category(normalized_category)
 WHERE normalized_category IS DISTINCT FROM _mtm_canonical_category(normalized_category)
   AND NOT EXISTS (
        SELECT 1 FROM registry_gap g2
        WHERE g2.normalized_make = registry_gap.normalized_make
          AND g2.normalized_model = registry_gap.normalized_model
          AND g2.normalized_category = _mtm_canonical_category(registry_gap.normalized_category)
          AND g2.gap_id <> registry_gap.gap_id);

-- Rows that could not be re-pointed above already have a canonical twin:
-- drop the younger duplicate (keep earliest first_seen). Aggregate counts on
-- the survivor heal on the next miss via recompute-from-lookup_event.
DELETE FROM registry_gap
 WHERE gap_id IN (
    SELECT gap_id FROM (
        SELECT gap_id,
               ROW_NUMBER() OVER (
                   PARTITION BY normalized_make, normalized_model,
                                _mtm_canonical_category(normalized_category)
                   ORDER BY first_seen, gap_id) AS rn
        FROM registry_gap) ranked
    WHERE rn > 1);

UPDATE registry_gap
   SET normalized_category = _mtm_canonical_category(normalized_category)
 WHERE normalized_category IS DISTINCT FROM _mtm_canonical_category(normalized_category);

DROP FUNCTION _mtm_canonical_category(TEXT);
