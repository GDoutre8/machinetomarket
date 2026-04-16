# Machine-to-Market — V1 Soft Launch Baseline

**Status:** Soft launch ready — internal use.
**Locked:** 2026-04-05

---

## What MTM Does (V1)

A dealer fills out a short form (Year / Make / Model / Hours / features / photos) and clicks **Generate Listing Pack**.
MTM looks up the machine in its OEM registry, runs the spec resolver and use-case scorer, and outputs a downloadable ZIP containing:

- **listing.txt** — a complete, marketplace-ready listing description
- **spec_sheet/machine_spec_sheet.png** — a 1200×1200 branded spec sheet with OEM data and Best For block
- **images_4x5 / images_1x1 / images_9x16 / thumbnails** — resized photo sets for different platforms
- **metadata.json** — machine match, spec count, resolution confidence

---

## Supported Machine Types (V1)

| Type | Registry | Scorer | Spec Sheet | Use-Case Enrichment |
|------|----------|--------|------------|---------------------|
| Skid Steer Loader (SSL) | ✓ | ✓ | ✓ | ✓ |
| Compact Track Loader (CTL) | ✓ | ✓ | ✓ | ✓ |
| Mini Excavator | ✓ | ✓ | ✓ | ✓ |

Other types (backhoe, wheel loader, telehandler, etc.) — registry miss path only; listing and image pack generated, spec sheet skipped.

---

## Key Endpoints

| Route | Purpose |
|-------|---------|
| `GET  /build-listing` | Main dealer form UI |
| `POST /build-listing` | Submit form → returns ZIP download |
| `POST /build-listing/preview` | Live use-case preview (called by frontend on field blur) |
| `GET  /` | Fix My Listing (legacy text-paste flow) |
| `POST /fix-listing` | Fix My Listing API endpoint |

---

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open: http://localhost:8000/build-listing

---

## Known V1 Gaps (Acceptable for Soft Launch)

- No dealer contact fields on the Build Listing form — spec sheet footer is blank (add in V1.1)
- Track Condition % field appears in Machine Identity section (cosmetic — move in V1.1)
- Feature toggles have no sublabels (Cab / Hydraulic / Other groupings) — V1.1
- Debug print statements from spec resolver appear in server logs — internal only, not visible to dealers

---

## What Was Fixed in the Final Launch-Readiness Pass (2026-04-05)

| Fix | File |
|-----|------|
| Spec field key names corrected (`net_hp`, `roc_lb`, etc.) — only 3 of 8 specs were reaching listing text before this fix | `listing_builder.py` |
| `equipment_type` threaded into parsed_listing — spec sheet subtitle was always blank | `listing_pack_builder.py` |
| Mini ex width field normalized (`width_in` → `width_over_tires_in`) | `listing_pack_builder.py` |
| Removed auto-fill default condition text that appeared in all listings | `listing_builder.py` |
| CTA corrected: no longer promises photos/walkaround video that may not exist | `listing_builder.py` |
| "Use Case Preview" → "What This Machine Is Best For" (user-facing label) | `build_listing.html` |
| Registry miss now shows an explicit notice instead of silently hiding | `build_listing.html` |
| Post-submit summary: "Pack ready for [machine]. Includes OEM spec sheet + N use cases." | `build_listing.html` |
| "Machine Snapshot" → "Key Specs" in listing.txt (buyer-visible section header) | `listing_builder.py` |

---

## Project Structure

```
mtm_mvp3/
├── app.py                        # FastAPI routes
├── mtm_service.py                # Fix My Listing pipeline
├── listing_builder.py            # V1 listing text generator
├── listing_pack_builder.py       # V1 ZIP pack assembler
├── listing_use_case_enrichment.py# Scorer-backed use-case payload
├── dealer_input.py               # DealerInput schema (validated form input)
├── spec_sheet_generator.py       # Spec sheet PNG generator
├── image_pack_generator.py       # Resized image set generator
├── mtm_registry_lookup.py        # OEM registry lookup
├── spec_resolver/                # Per-field spec resolvers (SSL, CTL, mini ex)
├── scorers/                      # Locked use-case scorers (SSL v1.0, CTL v1.0, mini ex v1.0)
├── registry/                     # JSON registries for all supported machine types
├── templates/
│   ├── build_listing.html        # Build My Listing dealer form
│   └── index.html                # Fix My Listing UI
└── static/
    └── styles_v2.css
```
