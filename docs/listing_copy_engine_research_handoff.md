# MTM Listing Copy Engine Research Handoff

## 1. Current Product Goal

Machine-to-Market (MTM) is building a deterministic, trust-safe, equipment-aware listing copy engine. The goal is not a generic AI writer.

The engine should take structured machine facts, dealer-confirmed fields, resolved OEM specs, and use-case scoring output, then produce dealer-ready sales copy that is credible, varied, and platform-aware.

Core product principle:

> Silence is safer than false specificity.

The listing engine should omit unsupported claims rather than invent condition, service, ownership, warranty, emissions, or readiness language.

## 2. Current Listing Output Problem

The current listing output is improving, but the weak pattern to avoid is still visible in parts of the system:

- Spec dump: output can lean heavily on bullets and raw specs without buyer framing.
- Repetitive lead: many machines can open with the same structure, especially similar CTL, skid steer, and mini excavator listings.
- Weak CTA: current CTAs are short and generic, usually "Call or text to schedule a look" or "Call or text for pricing and availability."
- Little buyer framing: copy often says what the machine has, but not enough about why it matters to a contractor, dealer, farm, rental yard, or homeowner buyer.
- Little platform variation: the same core listing text is mostly used for dealer pack output, with only early `copy_mode` support for tone differences.

Example weak pattern:

```text
2021 BOBCAT T770
$51,900

Core Specs:
  - 1,193 hours
  - Horsepower: 92 HP
  - Rated Operating Capacity: 3,515 lb

Features:
  - Enclosed cab with heat & A/C
  - High-flow hydraulics
  - 2-speed travel

Contact Details:
Call or text to schedule a look.
```

This is factual, but it reads like a spec card. It does not yet fully explain the buyer value of high flow, low hours, enclosed cab, track condition, attachment compatibility, or platform-specific next steps.

## 3. Current Code Map

### `listing_builder.py`

What it currently does:

- Builds listing text from `DealerInput`, `resolved_specs`, optional use-case payload, equipment type, and tone profile.
- Contains headline logic, feature formatting, spec formatting, attachment formatting, details formatting, and use-case display helpers.
- Calls `listing_copy_v2.build_opening_paragraph()` for the first prose paragraph.
- Calls `listing_copy_v2.build_contact_cta()` for tone-aware CTA text.
- Has special handling for mini excavator listings through `_build_mini_ex_listing()`.
- Builds "Best For" output from scorer payload labels.

What data it receives:

- `dealer_input`: structured dealer-entered fields from `DealerInput`.
- `resolved_specs`: flat dict of resolved OEM/spec fields.
- `use_case_payload`: optional dict from `listing_use_case_enrichment.build_use_case_payload()`.
- `equipment_type`: canonical type such as `compact_track_loader`, `skid_steer`, `mini_excavator`, `telehandler`, `excavator`, `wheel_loader`, or `backhoe_loader`.
- `tone_profile`: currently `dealer_clean`, `marketplace_direct`, or `premium_spec_sheet`.

What it outputs:

- One complete listing description string with sections such as title, price, opening paragraph, Core Specs, Features, Attachments Included, Best For, Additional Details, and Contact Details.
- UI helper data for Best For labels and descriptors.

Constraints Claude Research should respect:

- Do not assume unsupported facts.
- Best For labels are scorer-backed and should not be replaced by generic prose.
- Current output format is section-based and plain text.
- Production code already has some tone profile plumbing; research should provide structured phrase banks and gating notes, not app redesign.

### `dealer_input.py`

What it currently does:

- Defines the Pydantic `DealerInput` model for structured dealer-entered listing fields.
- Separates manual dealer fields from registry lookup and resolved OEM specs.
- Validates required identity fields, status fields, price, condition grade, copy mode, coupler type, thumb type, blade type, arm length, excavator hydraulic type, undercarriage percent, boom type, tail swing type, grade control type, and track type.

What data it receives:

- Required identity fields: `year`, `make`, `model`, `hours`.
- Dealer-selected feature/status fields.
- Free-text dealer notes, attachments, condition notes, and comparable models.
- Optional `copy_mode`.

What it outputs:

- A validated `DealerInput` instance used by listing text, spec sheet, use-case scoring, and listing pack generation.

Constraints Claude Research should respect:

- High-flow and two-speed are status fields: `yes`, `no`, `optional`, or unknown. `optional` means OEM offers it, not that the unit has it.
- Many fields are dealer-entered and not independently verified.
- Research phrases requiring verification must name their required source fields.

### `mtm_service.py`

What it currently does:

- Serves the older Fix Listing parser/service path.
- Parses raw listing text, matches known models, performs registry lookup, runs the spec resolver, builds display specs, scoring, confirm-required output, and rewritten listing output.
- Defines equipment type to resolver category mapping.
- Maps registry spec fields to canonical resolver fields.
- Contains supported platform labels for the older Fix Listing flow: Facebook Marketplace, Craigslist, IronPlanet, MachineryTrader, Equipment Trader.
- Contains `_stub_generate_listing_text()`, a legacy generator that emits a simpler cleaned listing from parsed raw text plus injected specs.

What data it receives:

- Raw listing text from the Fix Listing endpoint.
- Parsed machine identity and extracted fields such as price, location, contact, condition, attachments, and features.
- Registry lookup result and resolver output.

What it outputs:

- API response data including cleaned listing, parsed machine, display specs, resolved specs, warnings, confirmation requirements, scoring, fix-my-listing suggestions, rewritten listing, and output assets.

Constraints Claude Research should respect:

- This is not the same path as the structured Build Listing workflow.
- Raw parser data is thinner and less reliable than `DealerInput`.
- Research should not assume the Fix Listing path has all structured trust fields.
- Platform names exist, but platform-specific copy adaptation is not deeply implemented yet.

### `app.py`

What it currently does:

- Defines the FastAPI app and routes.
- Hosts the Build Listing flow, Fix Listing flow, preview endpoints, result pages, spec sheet views, session assets, and file outputs.
- Defines feature UI config by equipment type in `_FEATURE_CONFIG`.
- Builds `DealerInput` from form data.
- Calls registry lookup, spec resolver, use-case enrichment, listing pack generation, and output persistence.
- Accepts `copy_mode` on the build listing submit route.

What data it receives:

- Structured form fields from the Build Listing UI.
- Uploaded photos and dealer profile data.
- Raw text for the legacy Fix Listing route.
- Spec overrides, Best For overrides, and headline overrides in later verification flows.

What it outputs:

- JSON responses for preview/submit endpoints.
- HTML result/spec-sheet pages.
- Session files under `outputs`.
- Listing pack ZIPs and generated assets.

Constraints Claude Research should respect:

- The UI exposes different feature fields by equipment type.
- The app persists dealer input and resolved specs, then uses `build_listing_pack_v1()`.
- Research should not redesign UI flows; it should identify missing fields needed to unlock safer copy.

### `listing_pack_builder.py`

What it currently does:

- Assembles the listing pack folder and ZIP.
- Writes `listing_description.txt`.
- Builds branded listing photos, spec sheet image, metadata, and `START_HERE.txt`.
- Calls `build_use_case_payload()` and `build_listing_text()` in `build_listing_pack_v1()`.
- Passes `dealer_input.copy_mode` as the tone profile unless an explicit tone is provided.
- Injects dealer-entered fields into resolved specs for spec sheet display.

What data it receives:

- `DealerInput`, `resolved_specs`, optional `resolved_machine`, image paths, dealer info, session info, equipment type, and full record.

What it outputs:

- Pack result dict, generated listing text file, image folders, spec sheet/card assets, metadata, ZIP, and enriched specs.

Constraints Claude Research should respect:

- Listing text is one part of a broader listing pack.
- The engine should produce text that works alongside cards/spec sheets, not duplicate every visual asset.
- `copy_mode` is already available as a lightweight platform/tone selector.

### Current Use-Case / Best-For Logic

Current use-case logic lives mainly in `listing_use_case_enrichment.py`.

What it currently does:

- Bridges equipment-specific scorers into listing payloads.
- Supports `skid_steer`, `compact_track_loader`, `mini_excavator`, `backhoe_loader`, `telehandler`, `dozer`, and `wheel_loader`.
- Returns `top_use_cases_for_listing`, `attachment_sentence`, and `limitation_sentence`.
- Suppresses low-confidence claims and attachment-triggered use cases unless supported.
- Uses inline rule logic for telehandler, dozer, and wheel loader where dedicated scorers do not exist.

Important constraints:

- Use cases must remain grounded in scorer logic or explicit inline rules.
- Research can suggest wording for use-case labels and descriptors, but should not loosen scoring thresholds or invent use cases from thin data.

### Current Platform Output Logic

Current platform variation is limited.

- `DealerInput.copy_mode` supports `dealer_clean`, `marketplace_direct`, and `premium_spec_sheet`.
- `listing_copy_v2.py` changes opening length and CTA by tone profile.
- `mtm_service.py` has old platform labels but not a full platform-specific composition engine.
- `listing_pack_builder.py` START_HERE mentions Facebook Marketplace, Craigslist, EquipmentTrader, Iron Planet, Machinery Trader, and dealer websites as upload destinations.

Claude Research should treat platform adapters as a design target, not a completed implementation.

## 4. Existing Engine Architecture Decision

The intended architecture is a 4-layer model:

### Layer 1 - Registry Layer

Machine facts only.

This layer should contain OEM and registry-backed information such as make, model, equipment type, horsepower, rated operating capacity, lift capacity, dig depth, operating weight, hydraulic flow, bucket capacity, reach, dimensions, and machine-class facts.

It should not contain sales claims.

### Layer 2 - Trust Layer

Claim eligibility and safety gate.

This layer decides what the copy engine is allowed to say. It should gate phrases such as:

- one owner
- no leaks
- fresh service
- service records
- no active codes
- no DEF
- factory warranty
- like new
- ready to work
- low hours
- new tracks
- undercarriage percent
- tire percent

No phrase should pass this layer without a supporting field or rule.

### Layer 3 - Strategy Layer

Platform, audience, condition tier, and slot budget.

This layer decides:

- output platform: Facebook, dealer website, MachineryTrader/Equipment Trader, auction, spec sheet
- audience: contractor, dealer, homeowner, farm/ranch, rental/fleet, exporter
- condition tier: Tier A, Tier B, Tier C, or unknown
- which slots to fill: lead, buyer-value sentence, trust sentence, feature sentence, CTA
- how many words/sentences each platform gets

### Layer 4 - Composition Layer

Phrase-bank rendering.

This layer chooses eligible phrase patterns, fills tokens, and renders final copy. Phrase selection can vary deterministically, but it must not change claim eligibility.

Root rule:

> Silence is safer than false specificity.

## 5. Research Inputs Already Available

Two research inputs are part of the current listing-copy planning context. During this code inspection, files with these exact names were not found in the repo root or `docs/`; the following summary reflects the working research context already provided for MTM.

### `MTM-listing-copy-research.md`

Purpose:

- v1 language and phrase-bank layer.
- Captures common listing structures, buyer hooks, spec callouts, attachment/feature language, CTA examples, weak phrases, lead patterns, operational-value sentence patterns, financing/contact CTA patterns, and platform differences.

Main value:

- Gives the copy engine the raw language inventory.
- Helps avoid generic AI prose by using equipment-specific sentence patterns.
- Covers telehandlers, compact track loaders, skid steers, mini excavators, wheel loaders, and backhoes.

### `MTM-listing-copy-research-v2.md`

Purpose:

- v2 safety, slot, and trust-governance layer.

Adds:

- Tier A/B/C condition classification.
- Hard gated claims table.
- Feature priority maps.
- Best-for use-case mappings.
- Platform adapters.
- Failure-mode taxonomy.
- Deterministic slot model.
- Full-size excavator treatment.
- Boom & Bucket platform treatment.

Main value:

- Turns the phrase-bank work into an implementable safety model.
- Clarifies when the engine can speak confidently, when it should use softer language, and when it should stay silent.

## 6. Current Equipment Types

Current / relevant equipment types:

- `compact_track_loader` - high priority.
- `skid_steer` - high priority.
- `mini_excavator` - high priority.
- `telehandler` - high priority.
- `wheel_loader` - relevant and supported in use-case logic.
- `backhoe_loader` - relevant and supported in use-case logic.
- `excavator` / full-size excavator - relevant and increasingly supported in dealer input/spec sheet logic.
- `dozer` - supported in use-case enrichment but not part of the user's requested listing-copy research set.
- `boom_lift` - recognized by registry/service mappings and app labels; lower priority because listing-copy research is thinner.
- `scissor_lift` - recognized by registry/service mappings and app labels; lower priority because listing-copy research is thinner.

## 7. Data Fields Available Today

### Machine Identity Fields

From `DealerInput`:

- `year`
- `make`
- `model`
- `hours`

From resolved machine / metadata:

- `equipment_type`
- resolver confidence/status
- registry match metadata

### Specs

Common resolved/canonical spec fields, depending on equipment type and registry coverage:

- `net_hp`
- `horsepower_hp`
- `roc_lb`
- `rated_operating_capacity_lbs`
- `tipping_load_lb`
- `tipping_load_lbs`
- `operating_weight_lb`
- `operating_weight_lbs`
- `hydraulic_flow_gpm`
- `hi_flow_gpm`
- `aux_flow_standard_gpm`
- `aux_flow_high_gpm`
- `hydraulic_pressure_standard_psi`
- `bucket_hinge_pin_height_in`
- `width_over_tires_in`
- `width_in`
- `lift_path`
- `max_dig_depth`
- `max_dig_depth_ft`
- `max_dump_height_ft`
- `max_reach_ft`
- `bucket_breakout_lb`
- `bucket_dig_force_lbf`
- `tail_swing_type`
- `lift_capacity_lb`
- `lift_capacity_lbs`
- `max_lift_capacity_lbs`
- `max_lift_height_ft`
- `lift_height_ft`
- `max_forward_reach_ft`
- `forward_reach_ft`
- `bucket_capacity_yd3`
- `breakout_force_lb`
- `breakout_force_lbs`

Large excavator dealer/spec fields:

- `aux_hydraulics_type`
- `undercarriage_condition_pct`
- `undercarriage_percent_remaining`
- `stick_arm_length_ft`
- `track_shoe_width_in`
- `boom_length_ft`
- `boom_type`
- `rear_camera`
- `grade_control_type`
- `hammer_plumbing`
- `heated_seat`
- `track_type`
- `hours_qualifier`

### Dealer-Entered Fields

From `DealerInput`:

- `asking_price`
- `serial_number`
- `stock_number`
- `attachments_included`
- `condition_notes`
- `additional_features`
- `additional_details`
- `comparable_models`
- `copy_mode`

### Condition Fields

Available today:

- `hours`
- `condition_grade`
- `condition_notes`
- `track_condition`
- `track_percent_remaining`
- `tire_condition`
- `undercarriage_condition_pct`
- `undercarriage_percent_remaining`
- `hours_qualifier`

Important limitation:

- Most of these are dealer-entered or free text.
- They are not equivalent to verified inspection results unless separate verification fields are added.

### Attachments / Features

Universal or cross-type fields:

- `cab_type`
- `heater`
- `ac`
- `ride_control`
- `backup_camera`
- `one_owner`
- `radio`
- `control_type`
- `coupler_type`
- `bucket_size_included`
- `attachments_included`
- `additional_features`

CTL / skid steer fields:

- `high_flow`
- `two_speed_travel`
- `air_ride_seat`
- `self_leveling`
- `reversing_fan`
- `bucket_included`
- `bucket_size`
- `warranty_status`
- `tire_condition`
- `track_condition`

Mini excavator fields:

- `thumb_type`
- `aux_hydraulics`
- `blade_type`
- `arm_length`
- `pattern_changer`
- `zero_tail_swing`
- `rubber_tracks`

Telehandler field:

- `has_stabilizers`

Large excavator fields:

- `aux_hydraulics_type`
- `boom_type`
- `rear_camera`
- `grade_control_type`
- `hammer_plumbing`
- `heated_seat`
- `track_type`
- `stick_arm_length_ft`
- `track_shoe_width_in`
- `boom_length_ft`

### Dealer Contact Fields

Contact fields are not in `DealerInput` directly. They are passed through `dealer_info`, dealer profile snapshots, or parsed raw listing data depending on route.

Currently observed contact-related fields include:

- dealer/company name
- contact name
- phone
- email or contact URL when parsed/provided
- location
- dealer logo path
- accent color

### Currently Missing Trust Fields

The product does not currently expose enough structured fields for many high-trust claims. Claude Research should tag those requirements explicitly.

Missing or not consistently available:

- inspection checklist status
- active fault code status
- leak inspection status
- cold start status/video
- service record attachment status
- service date
- service hours
- ownership count verification
- warranty date and warranty hours remaining
- emissions verification
- DEF/DPF status verification
- tire percent verification source
- track/undercarriage percent verification source
- oil sample availability
- financing eligibility details

## 8. Trust Fields Missing Today

Research may assume fields that MTM does not collect yet. Do not write copy as if these fields exist. Instead, tag phrase patterns with required fields.

Important missing / desired trust fields:

- `inspection_passed_full_checklist`
- `no_active_fault_codes`
- `no_visible_leaks`
- `service_date`
- `service_hours`
- `owner_count`
- `single_owner_verified`
- `service_records_attached`
- `warranty_expiration_date`
- `warranty_hours_remaining`
- `emissions_verified`
- `def_required_verified`
- `dpf_present_verified`
- `cold_start_video_url`
- `cold_start_verified`
- `walkaround_video_url`
- `oil_sample_report_url`
- `undercarriage_pct`
- `undercarriage_pct_verified_source`
- `track_pct`
- `track_pct_verified_source`
- `tire_pct`
- `tire_pct_verified_source`
- `recent_repairs`
- `known_issues`
- `mechanical_issue_flags`
- `inspection_disclosures`

Claude Research should tag phrases requiring these fields, not assume they exist.

Example:

- Phrase: "No active codes and no visible leaks."
- Required claims: `no_active_fault_codes == true`, `no_visible_leaks == true`.
- If either field is missing, the engine must not say it.

## 9. Desired Claude Research Output

Claude Research should return YAML-ready content blocks, not prose essays.

Research should produce:

- improved lead patterns
- operational-value patterns
- CTA patterns
- buyer-trust wording
- Tier A/B/C wording menus
- platform-specific variants
- forbidden / weak phrase lists
- claim-gating notes
- missing trust-signal recommendations

Each phrase should be structured so Claude Code/Codex can convert it into deterministic engine files and tests.

## 10. Boundaries / Non-Goals

Claude Research should NOT:

- redesign the app
- write production code
- invent facts
- loosen claim rules
- use unsupported claims without source-field requirements

Unsupported unless gated:

- "no leaks"
- "fresh service"
- "one owner"
- "no DEF"
- "no DPF"
- "ready to work"
- "like new"
- "dealer serviced"
- "factory warranty"
- "tracks like new"
- "new tires"
- "no active codes"
- "starts cold"
- "no smoke"
- "rental fleet maintained"
- "owner-operated"

## 11. Recommended Output Format for Claude Research

Claude Research should use this YAML-ready shape:

```yaml
equipment_type:
  lead_patterns:
    - text:
      required_tokens:
      required_claims:
      tier_eligibility:
      platform_fit:

  operational_value_patterns:
    - text:
      required_tokens:
      required_claims:
      tier_eligibility:
      platform_fit:

  cta_patterns:
    - text:
      required_tokens:
      required_claims:
      platform_fit:

  trust_phrases:
    - text:
      required_tokens:
      required_claims:
      tier_eligibility:

  forbidden_phrases:
    - phrase:
      reason:
      allowed_only_if:

  feature_priority:
    - field:
      priority:
      buyer_reason:
      platforms:

  best_for_rules:
    - use_case:
      display_label:
      required_specs:
      required_features:
      suppress_if:
      wording:

  missing_fields_to_unlock_better_copy:
    - field:
      unlocks_claims:
      collection_note:
```

Recommended top-level organization:

```yaml
compact_track_loader:
  ...
skid_steer:
  ...
mini_excavator:
  ...
telehandler:
  ...
wheel_loader:
  ...
backhoe_loader:
  ...
excavator:
  ...
boom_lift:
  priority: lower
  ...
scissor_lift:
  priority: lower
  ...
```

## 12. Final Handoff Summary

Claude Research's job is to refine the language and research-backed wording.

Codex/Claude Code's job is to convert the final structured outputs into engine files and tests.

The research output should strengthen the deterministic engine by giving it better phrase banks, safer trust gates, equipment-specific feature priorities, and platform-specific copy strategies.

The implementation must continue to follow the root rule:

> Silence is safer than false specificity.
