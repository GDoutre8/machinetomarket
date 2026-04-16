# MTM Use Case System — Canonical Rules Reference

**Status:** LOCKED — Production Baseline  
**Date Locked:** 2026-04-15  
**Version:** v1.0  
**Maintained by:** listing_use_case_enrichment.py + per-type scorer modules

This document is the authoritative reference for all MTM use case logic.  
Any change to scoring behavior, allowed use cases, gating rules, or output
structure requires a version increment in the affected file AND an update here.

---

## Global Output Structure

```
Best For:
• USE CASE — description of real actions performed
• USE CASE — description of real actions performed
• USE CASE — description (optional third, if justified)
```

**Rules (all equipment types):**

| Rule | Value |
|------|-------|
| Default use case count | 2 |
| Maximum use case count | 3 |
| Minimum score to include (scored types) | 70 |
| 3rd use case score threshold (scored types) | 85 |
| Descriptions | Must describe real actions, not generic "jobsite support" language |
| No variation by type | Same 2–3 format enforced universally |

---

## Equipment Types and Scorer Modules

| Equipment Type | Scorer / Logic | File |
|----------------|---------------|------|
| `skid_steer` | Dedicated scorer v1.0 | `scorers/skid_steer_use_case_scorer_v1_0.py` |
| `compact_track_loader` | Dedicated scorer v1.0 | `scorers/ctl_use_case_scorer_v1_0.py` |
| `mini_excavator` | Dedicated scorer v1.0 | `scorers/mini_ex_use_case_scorer_v1_0.py` |
| `backhoe_loader` | Dedicated scorer v1.0 | `scorers/backhoe/backhoe_use_case_scorer_v1_0.py` |
| `telehandler` | Inline rule-based | `listing_use_case_enrichment.py` → `_score_telehandler_inline()` |
| `dozer` | Inline rule-based | `listing_use_case_enrichment.py` → `_score_dozer_inline()` |
| `wheel_loader` | Inline rule-based | `listing_use_case_enrichment.py` → `_score_wheel_loader_inline()` |

All types route through `build_use_case_payload(equipment_type, dealer_input, resolved_specs)`.

---

## Skid Steer (`skid_steer`)

**Identity model:** Frame class + lift path + hydraulic capability.  
Wheeled machines — tire condition, lift geometry, and ROC drive scoring.

**Capability classes:**

| Class | ROC | HP | Weight | Buyer profile |
|-------|-----|----|--------|---------------|
| A | ≤1,749 lb | <60 | <6,500 lb | Landscapers, farms, tight-access |
| B | 1,750–2,499 lb | 60–74 | 6,500–8,500 lb | GCs, concrete, snow |
| C | 2,500–3,499 lb | 75–94 | 8,500–10,999 lb | Heavy construction, demo, loading |
| D | HF ≥36 GPM + HP ≥85 | — | — | Specialty/forestry/cold-planing |

**Allowed use cases (13 scored internally, mapped to display taxonomy):**

| Display label | Internal scorer label(s) |
|---------------|--------------------------|
| Grading & Site Prep | Grading / Site Prep, Landscaping / Irrigation |
| Material Handling | Material Handling / Pallet Forks |
| Truck Loading | Truck Loading |
| Concrete & Flatwork Prep | Concrete / Flatwork Prep |
| Demolition & Breaking | Demolition |
| Snow Removal | Snow Removal |
| Auger Work | Auger Work |
| Utility Trenching | Trenching (Standard / Soft Ground) |
| Rock Trenching | Trenching (Rock / Hard Ground) |
| Farm & Agriculture Work | Agriculture / Farm Use |
| Yard & Staging Work | Warehouse / Yard Use |
| Land Clearing | Light Land Clearing |
| Cold Planing / Asphalt Milling | Cold Planing / Asphalt Milling |
| Stump Grinding | Stump Grinding |
| Forestry Mulching | Forestry Mulching |

**Gating rules:**

| Gate | Rule |
|------|------|
| Snow Removal | Attachment-triggered: only appears when `snow_blade` detected in free text |
| Auger Work | Attachment-triggered: only appears when `auger` detected in free text |
| Forestry Mulching | Penalty: -18 if no mulcher attachment detected |
| Demolition & Breaking | Penalty: -15 if no breaker detected |
| Utility Trenching | Penalty: -10 if no trencher detected (SSL/CTL) |
| Cold Planing | Requires Class C/D + high-flow GPM ≥37 |
| Confidence Low | All claims suppressed → empty payload |

**What is explicitly NOT allowed:**
- Excavation & Digging (reserved for mini ex / backhoe)
- Rooftop Material Placement, High-Reach Loading (telehandler only)
- Material Handling & Yard Work, Pallet Handling & Loading (wheel loader labels — not used here)

---

## Compact Track Loader (`compact_track_loader`)

**Identity model:** ROC class + hydraulic flow tier + lift path.  
Track machines — grade-first use cases dominate at Class C/D.

**Capability classes:**

| Class | ROC | HP | Weight |
|-------|-----|----|--------|
| A | ≤2,199 lb | ≤67 | ≤8,499 lb |
| B | 2,200–2,999 lb | 68–84 | 8,500–9,699 lb |
| C | 3,000–3,999 lb | 85–105 | 9,700–12,499 lb |
| D | HF ≥37 GPM + HP ≥96 | — | — |

**Allowed use cases (11 scored):**

| Display label | Internal scorer label |
|---------------|-----------------------|
| Grading & Site Prep | Grading / Site Prep |
| Material Handling | Material Handling / Loading |
| Land Clearing | Light Land Clearing |
| Forestry Mulching | Forestry Mulching |
| Utility Trenching | Trenching (Standard -- Soft Ground) |
| Rock Trenching | Trenching (Rock / Hard Ground) |
| Demolition & Breaking | Demolition / Breaking |
| Snow Removal | Snow Removal |
| Cold Planing / Asphalt Milling | Cold Planing / Asphalt Milling |
| Stump Grinding | Stump Grinding |
| Auger Work | Auger Work (Light Soil / Small Diameter) |

**Class-based boosts (enrichment layer):**
- Large CTL (Class C/D) with no dominant attachment signal → Grading & Site Prep +20, Material Handling +18

**Gating rules:** Same attachment-triggered labels as SSL (Snow Removal, Auger Work).  
No confidence gating on CTL (scorer always returns result).

**What is explicitly NOT allowed:**
- Truck Loading (SSL-only label)
- Concrete & Flatwork Prep (SSL-only)
- Farm & Agriculture Work (SSL-only)
- Yard & Staging Work (SSL-only)
- Any excavation / digging labels

---

## Mini Excavator (`mini_excavator`)

**Identity model:** Dig depth class + auxiliary hydraulics + tail swing geometry.  
Job-first machine — excavation and utility trenching always dominate.

**Capability classes:** A (sub-1T), B (1–3T), C (3–6T), D (6–10T)

**Allowed use cases (display taxonomy):**

| Display label | Internal scorer functions |
|---------------|--------------------------|
| Excavation & Digging | footings/foundation, material loading, tight access, residential construction |
| Utility Trenching | utility trenching, deep trenching, septic installation |
| Demolition & Breaking | interior demolition |
| Land Clearing | land clearing / site grading |
| Truck Loading | truck loading (Class C/D only) |

**Priority boosts (enrichment layer):**
- Excavation & Digging: +5
- Utility Trenching: +15 (excavators are the primary trenching machine)

**Gating rules:**

| Gate | Rule |
|------|------|
| No aux hydraulics | All powered attachment use cases suppressed |
| Dig depth → deep utility work | Score 0 if depth insufficient |
| Tight access | Penalized if Class C/D with poor score |
| Confidence Low | All claims suppressed |

**Limitation sentences triggered by:**
- No aux hydraulics → attachment limitation
- Shallow dig depth → sewer/deep utility limitation
- Wide tail swing (Class C/D, low tight-access score) → site access limitation
- Canopy/open cab → operator exposure note

**What is explicitly NOT allowed:**
- Grading & Site Prep as a primary label (absorbed into Land Clearing)
- Snow Removal
- Any wheel-loader or SSL-style labels

---

## Backhoe Loader (`backhoe_loader`)

**Identity model:** Backhoe dig depth + loader arm capacity + 4WD configuration.  
Dual-function machine — trenching and loader work both scored.

**Allowed use cases (display taxonomy):**

| Display label | Internal scorer labels |
|---------------|------------------------|
| Utility Trenching | trenching, water_line_install, sewer_line_install, utility_work, drainage_work, septic_install |
| Grading & Site Prep | general_construction, road_work, landscaping |
| Excavation & Digging | foundation_digging |
| Truck Loading | loading_trucks |
| Demolition & Breaking | demolition_light |
| Farm & Agriculture Work | farm_use, property_maintenance |
| Material Handling | material_handling, pallet_handling |
| Snow Removal | snow_removal (attachment-triggered) |

**Score threshold:** 0.0 — backhoe always takes the top 2 by raw score (no 70-point floor).  
Reason: backhoe roles are well-defined; the scorer produces reliable rankings without a floor.

**What is explicitly NOT allowed:**
- Forestry Mulching, Cold Planing, Stump Grinding (specialty attachment categories)
- Rooftop placement, high-reach work
- Pure excavation-only labels (backhoe is not a mini ex substitute)

---

## Telehandler (`telehandler`)

**Identity model:** Max lift height tier. Spec-driven, not job-driven.  
Reach and placement work define the machine — not attachment capability.

**Lift height tiers and use cases:**

| Lift height | Use case 1 | Use case 2 |
|-------------|------------|------------|
| ≥50 ft | Rooftop Material Placement | High-Reach Loading |
| 42–49 ft | Jobsite Reach & Placement | Pallet Handling |
| <42 ft | Pallet Handling | Jobsite Reach & Placement |

**Conditional 3rd:**
- Agricultural Use: only when lift ≤44 ft AND `ag_use` flag set on DealerInput

**What is explicitly NOT allowed:**
- Grading & Site Prep
- Land Clearing, Forestry Mulching
- Snow Removal
- Any CTL/SSL-style use cases
- Truck Loading (merged into reach tiers)
- General Jobsite / Concrete Support (too generic)

**No attachment sentence, no limitation sentence** (inline logic returns None for both).

---

## Dozer (`dozer`)

**Identity model:** Grading is universal — every dozer grades.  
Simple 2-use-case output, grade control type drives attachment sentence only.

**Fixed use cases (all dozers):**
1. Grading & Site Prep
2. Land Clearing

**Attachment sentence:** Only when `grade_control_type` is "2D" or "3D" on DealerInput.  
→ `"{grade_control_type} grade control equipped."`

**No 3rd use case.** No limitation sentence.

**What is explicitly NOT allowed:**
- Material handling labels
- Snow Removal
- Trenching, demolition, excavation
- Any attachment-driven use cases beyond grade control note

---

## Wheel Loader (`wheel_loader`)

**Identity model:** Identity-driven, not job-first.  
Material handling + pallet/fork switching defines the machine.  
Coupler type (SSL-compatible) is the defining identity feature.

**Fixed use cases (all compact wheel loaders):**
1. Material Handling & Yard Work
2. Pallet Handling & Loading

**Conditional 3rd (first qualifying signal wins, in priority order):**

| Priority | Use case | Signal required |
|----------|----------|----------------|
| 1 | Snow Removal | "snow" in free text OR municipal context signal |
| 2 | Farm & Property Work | Ag brand (Deere, Kubota, New Holland, AGCO) AND no snow signal |
| 3 | Municipal / Utility Work | Municipal keyword in free text, no snow signal, not ag brand |

**Ag brands:** `deere`, `kubota`, `new holland`, `agco`, `fendt`, `massey` (substring match on make).  
**Municipal keywords:** `municipal`, `city`, `county`, `utility fleet`, `government`, `airport`, `public works`, `municipality`.

**Attachment sentence:**
- SSL coupler present (coupler_type set, not `pin-on`) → "Skid steer coupler compatible — accepts standard SSL attachments."
- No coupler info + forks in free text → "Pallet forks included."

**No limitation sentence** (no universal buyer-facing spec gap at this classification level).

**What is explicitly NOT allowed:**
- Grading & Site Prep (wheel loaders do not grade — CTL/dozer job)
- Land Clearing (dozer/CTL category)
- Utility Trenching (excavator/backhoe category)
- Demolition & Breaking
- Any CTL-style site prep logic
- Rooftop placement, high-reach labels (telehandler only)
- Auger Work, Forestry Mulching (not WL attachment categories)

**Snow is NOT attachment-gated** (unlike SSL/CTL where snow_blade must be detected).  
Snow Removal is a primary wheel loader use case — appear naturally from context.

---

## Attachment Gating — Global Reference

These labels only appear when a matching attachment is explicitly detected in free text.  
Applies to: `skid_steer`, `compact_track_loader` (via enrichment layer).

| Display label | Required attachment keyword |
|---------------|-----------------------------|
| Snow Removal | `snow_blade`, `snow pusher`, `snow` (SSL/CTL only; WL not gated) |
| Auger Work | `auger` |

Detection source: `dealer_input.attachments_included` (primary).

---

## Payload Schema (all types)

```python
{
    "top_use_cases_for_listing": list[str],   # 0–3 display labels
    "attachment_sentence":       str | None,   # one sentence or None
    "limitation_sentence":       str | None,   # one sentence or None
}
```

If `build_use_case_payload()` returns `None` (unsupported type or scorer exception),
listing generation continues unaffected — no Best For block is emitted.

Empty payload (suppressed due to Low confidence):
```python
{"top_use_cases_for_listing": [], "attachment_sentence": None, "limitation_sentence": None}
```

---

## What Changes Require a Version Increment

| Change type | Action required |
|-------------|----------------|
| Score threshold adjustment | New scorer version file |
| New use case added | New scorer version file + update this doc |
| Gating rule added or removed | New scorer version file + update this doc |
| Attachment detection keyword added | Update enrichment file, increment version comment, update this doc |
| New equipment type added | Update enrichment file, add section here |
| Display label renamed | Update `_UC_DISPLAY` in enrichment file, update this doc |
| Descriptor language changed | Update listing builder — does NOT require scorer version bump |
