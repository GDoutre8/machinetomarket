# CTL + SSL Family Graph — Build Summary

Built: 2026-06-11T03:37:02Z  |  graph_version 1.0

## Stop Gate

| Equipment type | Target | Rate | Result |
|---|---|---|---|
| compact_track_loader | 80% | 99.5% | PASS |
| skid_steer | 70% | 98.6% | PASS |

**Overall stop gate: PASS** (silent ambiguous assignments: 0)

## Counts

- **compact_track_loader**: 211 records, 204 production, 203 assigned (99.5%), 1 ambiguous, 7 excluded by status
- **skid_steer**: 276 records, 276 production, 272 assigned (98.6%), 4 ambiguous, 0 excluded by status
- Families: 328 (69 multi-member, 259 single-member, by unique logical model)
- Duplicate same-model rows collapsed from voting: 9 across 5 families (rows remain as member references; one vote per logical model)
- Relationships: 137
- Manual successor seed edges: 0 (require OEM evidence; none shipped in Session 3)

## Top 10 Largest Families

| Family | Unique models | Duplicate rows | Models |
|---|---|---|---|
| caterpillar_compact_track_loader_299 | 8 | 0 | 299C, 299D, 299D XHP, 299D2, 299D2 XHP, 299D3, 299D3 XE, 299D3 XE LAND MANAGEMENT |
| caterpillar_skid_steer_272 | 7 | 0 | 272C, 272D, 272D XHP, 272D2, 272D2 XHP, 272D3, 272D3 XE |
| caterpillar_skid_steer_226 | 6 | 0 | 226, 226B, 226B2, 226B3, 226D, 226D3 |
| caterpillar_skid_steer_236 | 6 | 0 | 236, 236B, 236B2, 236B3, 236D, 236D3 |
| caterpillar_skid_steer_242 | 6 | 0 | 242, 242B, 242B2, 242B3, 242D, 242D3 |
| caterpillar_skid_steer_262 | 6 | 0 | 262, 262B, 262C, 262C2, 262D, 262D3 |
| caterpillar_compact_track_loader_257 | 5 | 0 | 257B, 257B2, 257B3, 257D, 257D3 |
| caterpillar_compact_track_loader_277 | 5 | 0 | 277, 277B, 277C, 277C2, 277D |
| caterpillar_compact_track_loader_287 | 5 | 0 | 287, 287B, 287C, 287C2, 287D |
| caterpillar_skid_steer_232 | 5 | 0 | 232, 232B, 232B2, 232D, 232D3 |

## Ambiguous Records (flagged, not assigned)

- `None 259D` (compact_track_loader): missing manufacturer
- `Gehl 5240E P2` (skid_steer): unknown suffix 'E P2'
- `Gehl 5635SX II` (skid_steer): unknown suffix 'SX II'
- `Gehl 5635SXT` (skid_steer): unknown suffix 'SXT'
- `Gehl 6635SXT II` (skid_steer): unknown suffix 'SXT II'

## Policy (locked)

- identity: manufacturer + equipment_type + grammar root only
- cross_manufacturer_linking: forbidden (incl. Gehl/Mustang)
- automatic_cross_root_succession: forbidden (manual seeds only)
- model_family_field: corroboration only, never identity
- tri_state_fields: never family-stable
- single_member_families: count as assigned
- production statuses counted: active_new_market, active_used_market, current, discontinued
