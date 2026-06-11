-- Session 3: Family Relationship Graph — registry_family tables.
-- Postgres dialect (target for server-side promotion). The local artifact
-- is the JSON graph at outputs/family_graph/ctl_ssl_family_graph.json;
-- these tables mirror it 1:1 for when the graph is promoted server-side.
--
-- Locked policy (Session 3):
--   * Family identity is (manufacturer, equipment_type, family_root) —
--     grammar root only. model_family marketing strings are
--     corroboration-only and must never create identity.
--   * No cross-manufacturer linking (including Gehl/Mustang rebadges).
--   * No automatic cross-root succession: relation_type
--     'manual_successor' rows require OEM evidence (evidence JSONB) and a
--     reviewer; none ship in Session 3.
--   * Tri-states and feature_flags are never family-stable; stable_fields
--     may not contain high_flow / two_speed / *_available keys.
--   * Ambiguous records are flagged (registry_family_ambiguous), never
--     assigned membership.
--
-- GAP TELEMETRY CONTRACT: family fallback is read-only over these tables
-- and must never suppress or alter exact-model gap telemetry
-- (lookup_event / registry_gap writes fire exactly as without the graph).

CREATE TABLE IF NOT EXISTS registry_family (
    family_id            TEXT PRIMARY KEY,
    manufacturer         TEXT NOT NULL,
    equipment_type       TEXT NOT NULL,
    family_root          TEXT NOT NULL,
    display_name         TEXT,
    status               TEXT DEFAULT 'confirmed',  -- confirmed|provisional|manual_review
    evidence             JSONB,
    stable_fields        JSONB,
    variable_fields      JSONB,
    indeterminate_fields JSONB,
    model_family_corroboration JSONB,               -- info only, never identity
    registry_checksum    TEXT,
    built_at             TIMESTAMPTZ,
    UNIQUE (manufacturer, equipment_type, family_root)
);

CREATE TABLE IF NOT EXISTS registry_family_member (
    family_id            TEXT NOT NULL REFERENCES registry_family (family_id),
    model_slug           TEXT NOT NULL,
    model                TEXT NOT NULL,
    model_ident          TEXT NOT NULL,             -- lowercase alnum identity
    generation_ordinal   INT  NOT NULL DEFAULT 0,
    generation_label     TEXT,
    is_variant           BOOLEAN NOT NULL DEFAULT FALSE,
    variant_suffixes     JSONB,
    variant_of           TEXT,                      -- mainline sibling slug
    PRIMARY KEY (family_id, model_slug)
);

CREATE TABLE IF NOT EXISTS registry_family_relationship (
    relationship_id      UUID PRIMARY KEY,
    from_slug            TEXT NOT NULL,
    to_slug              TEXT NOT NULL,
    relation_type        TEXT NOT NULL,  -- successor|variant|manual_successor
    generation_delta     INT,
    evidence             JSONB,          -- manual_successor REQUIRES OEM evidence
    confidence           TEXT,           -- HIGH|MEDIUM|MANUAL
    status               TEXT DEFAULT 'confirmed',
    reviewed_by          TEXT,           -- required when relation_type = 'manual_successor'
    UNIQUE (from_slug, to_slug, relation_type)
);

CREATE TABLE IF NOT EXISTS registry_family_ambiguous (
    model_slug           TEXT PRIMARY KEY,
    manufacturer         TEXT,
    model                TEXT,
    equipment_type       TEXT,
    reason               TEXT,
    flagged_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_registry_family_identity
    ON registry_family (manufacturer, equipment_type, family_root);

CREATE INDEX IF NOT EXISTS idx_registry_family_member_ident
    ON registry_family_member (model_ident);

CREATE INDEX IF NOT EXISTS idx_registry_family_rel_from
    ON registry_family_relationship (from_slug);
