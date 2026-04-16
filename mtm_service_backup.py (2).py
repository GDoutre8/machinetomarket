"""
mtm_service.py
==============
Adapter layer between the FastAPI web app and the MTM parser modules.

Pipeline:
    raw_text
      → safe_parse_listing        (regex fields: year, hours, location, contact, condition)
      → match_known_model         (alias enrichment: make, model, equipment_type)
      → safe_lookup_machine       (spec registry lookup — stub, swap when ready)
      → _stub_build_listing_data  (merge parsed + specs)
      → _stub_generate_listing_text (format output)
      → format_output_response
      → dict

Public API (called from app.py):
    fix_listing_service(raw_text: str) -> dict

Integration checklist for real modules:
    Search for "── SWAP ──" to find each replacement point.
"""

from __future__ import annotations
import re
from typing import Any

# ── Frozen parser modules ─────────────────────────────────────────────────────
from mtm_listing_parser_price       import extract_price
from mtm_listing_parser_attachments import extract_attachments
from mtm_listing_parser_model_alias import match_known_model


# ── Config ────────────────────────────────────────────────────────────────────

SPEC_CONFIDENCE_THRESHOLD = 0.75

SUPPORTED_PLATFORMS = [
    "Facebook Marketplace",
    "Craigslist",
    "IronPlanet",
    "MachineryTrader",
    "Equipment Trader",
]


# ══════════════════════════════════════════════════════════════════════════════
# STUB FUNCTIONS  (swap bodies when real modules are ready)
# ══════════════════════════════════════════════════════════════════════════════

def _stub_lookup_machine(parsed: dict) -> tuple[dict | None, float]:
    """
    ── SWAP body ──
        specs, conf = lookup_machine(parsed)
        if specs is None:
            specs, conf = search_by_model(parsed.get("make"), parsed.get("model"))
        return specs, conf
    """
    return None, 0.0


def _stub_build_listing_data(parsed: dict, specs: dict | None) -> dict:
    """── SWAP body ──  return build_listing_data(parsed, specs)"""
    data = dict(parsed)
    if specs:
        data["specs"] = specs
    return data


def _stub_generate_listing_text(listing_data: dict, added_specs: dict | None) -> str:
    """
    ── SWAP body ──  return generate_listing_text(listing_data)

    MTM output format:
        [Headline]
        Machine Snapshot • ...
        Attachments & Features
        Condition • ...
        Price
        Location
        Contact
        #hashtags
    """
    year      = listing_data.get("year") or ""
    make      = listing_data.get("make") or ""
    model     = listing_data.get("model") or ""
    hours     = listing_data.get("hours")
    price_int = listing_data.get("price_value")
    price_obo = listing_data.get("price_is_obo", False)
    location  = listing_data.get("location")
    contact   = listing_data.get("contact")
    condition = listing_data.get("condition")
    notes     = listing_data.get("notes")
    attachments = listing_data.get("attachments") or []
    features    = listing_data.get("features") or []

    # Headline — always emit year / make / model when available
    headline_parts = [str(p) for p in [year, make, model] if p]
    headline = " ".join(headline_parts) if headline_parts else "Heavy Equipment for Sale"

    lines = [headline]

    # Hours line immediately under headline
    if hours:
        lines.append(f"{hours:,} hours on machine")

    lines.append("")

    # Machine Snapshot
    bullets: list[str] = []
    if added_specs:
        spec_labels = {
            "horsepower":               "Gross horsepower",
            "operating_weight":         "Operating weight",
            "rated_operating_capacity": "Rated operating capacity",
            "hydraulic_flow":           "Auxiliary hydraulic flow",
            "bucket_capacity":          "Bucket capacity",
            "engine":                   "Engine",
            "max_travel_speed":         "Max travel speed",
            "ground_pressure":          "Ground pressure",
        }
        for key, label in spec_labels.items():
            if added_specs.get(key):
                bullets.append(f"{label}: {added_specs[key]}")

    if notes:
        bullets.append(notes.strip().rstrip(".").capitalize())

    if bullets:
        lines.append("Machine Snapshot")
        for b in bullets:
            lines.append(f"• {b.rstrip('.')}")
        lines.append("")

    # Features first (cab, controls, hydraulic options, camera, etc.)
    if features:
        lines.append("Features")
        for f in features:
            lines.append(f"• {f}")
        lines.append("")

    # Attachments (physical work tools only)
    if attachments:
        lines.append("Attachments")
        for a in attachments:
            lines.append(f"• {a}")
        lines.append("")

    # Condition
    lines.append("Condition")
    lines.append(f"• {condition}" if condition else "• Contact seller for condition details")
    lines.append("")

    # Price
    lines.append("Price")
    if price_int:
        price_str = f"${price_int:,}"
        if price_obo:
            price_str += " OBO"
        lines.append(price_str)
    else:
        lines.append("Contact for pricing")
    lines.append("")

    # Location
    lines.append("Location")
    lines.append(location if location else "Location not listed — contact seller")
    lines.append("")

    # Contact
    lines.append("Contact")
    lines.append(contact if contact else "Contact seller for details")

    # Hashtags
    tags = []
    if make:
        tags.append(f"#{re.sub(r'[^a-z0-9]', '', make.lower())}")
    if model:
        tags.append(f"#{re.sub(r'[^a-z0-9]', '', model.lower())}")
    tags += ["#heavyequipment", "#equipmentdealer", "#usedequipment"]
    lines.append("")
    lines.append(" ".join(tags))

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# PARSE LISTING  (regex fields + frozen module enrichment)
# ══════════════════════════════════════════════════════════════════════════════

def safe_parse_listing(raw_text: str) -> dict:
    """
    Extracts structured fields from raw listing text.

    Field sources:
      year, hours, location, contact, condition  — regex
      price_value, price_is_obo                 — extract_price()
      attachments                               — extract_attachments()
      make, model, equipment_type               — match_known_model() (gap-fill only)
    """
    try:
        result: dict[str, Any] = dict.fromkeys(
            ["year", "make", "model", "equipment_type",
             "hours", "price_value", "price_is_obo",
             "location", "contact", "condition", "notes",
             "attachments", "features"]
        )

        t = raw_text

        # Year ─────────────────────────────────────────────────────────────────
        m = re.search(r'\b(19[89]\d|20[0-3]\d)\b', t)
        if m:
            result["year"] = int(m.group())

        # Hours ────────────────────────────────────────────────────────────────
        m = re.search(r'(\d[\d,]*)\s*(?:hrs?\.?|hours?)', t, re.I)
        if m:
            result["hours"] = int(m.group(1).replace(",", ""))

        # Price — frozen module ────────────────────────────────────────────────
        price_val = extract_price(t)
        result["price_value"]  = price_val
        result["price_is_obo"] = bool(re.search(r'\bobo\b', t, re.I))

        # Location ─────────────────────────────────────────────────────────────
        m = re.search(
            r'(?:located?\s+in|location[:\s]+)\s*([A-Za-z][A-Za-z\s,]{2,40}?)(?:[.\n]|$)',
            t, re.I
        )
        if m:
            result["location"] = m.group(1).strip().rstrip(",")

        # Contact ──────────────────────────────────────────────────────────────
        m = re.search(r'\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}', t)
        if m:
            result["contact"] = m.group().strip()

        # Condition ────────────────────────────────────────────────────────────
        for kw in ["like new", "very good", "runs great", "excellent",
                   "good condition", "good", "fair", "needs work",
                   "project machine", "poor"]:
            if re.search(rf'\b{re.escape(kw)}\b', t, re.I):
                result["condition"] = kw.title()
                break

        # Make / Model — regex baseline ────────────────────────────────────────
        known_makes = [
            "Caterpillar", "CAT", "John Deere", "Komatsu", "Bobcat",
            "Case", "Volvo", "Doosan", "Hitachi", "JCB", "Kubota",
            "Takeuchi", "Liebherr", "Terex", "New Holland", "Hyundai",
            "Kobelco", "Genie", "JLG", "Skytrak", "Manitou", "Gradall",
            "Link-Belt", "Sany", "LiuGong", "Yanmar",
        ]
        for make in known_makes:
            if re.search(rf'\b{re.escape(make)}\b', t, re.I):
                result["make"] = make
                # Model-token blocklist: type/category words that follow a make
                # name but are not model numbers. Without this, "cat skid steer"
                # stores model=SKID, "jcb telehandler" stores model=TELEHANDLER, etc.
                _MODEL_BLOCKLIST = {
                    "MINI", "EXCAVATOR", "EXCAVTOR",
                    "SKID", "STEER",
                    "CTL", "TRACK", "LOADER",
                    "TELEHANDLER", "BACKHOE",
                    "DOZER", "CRAWLER",
                }
                m2 = re.search(
                    rf'\b{re.escape(make)}\s+([A-Z0-9][A-Za-z0-9\-]{{1,20}})',
                    t, re.I
                )
                if m2 and m2.group(1).upper() not in _MODEL_BLOCKLIST:
                    result["model"] = m2.group(1).upper()
                break

        # Normalise abbreviated/alternate make names to canonical display form
        _MAKE_CANONICAL = {
            "CAT":         "Caterpillar",
            "CATERPILLAR": "Caterpillar",
            "JOHN DEERE":  "John Deere",
            "JD":          "John Deere",
            "SKYTRAK":     "SkyTrak",
        }
        if result.get("make"):
            result["make"] = _MAKE_CANONICAL.get(
                result["make"].upper(), result["make"]
            )

                # Make / Model — alias enrichment (fills gaps, does not overwrite) ─────
        alias = match_known_model(t)
        if alias:
            if not result.get("make"):
                result["make"] = alias["manufacturer"]
            if not result.get("model"):
                result["model"] = alias["model"]
            # equipment_type not produced by regex — always store it
            result["equipment_type"] = alias["equipment_type"]

        # Attachments & Features — frozen module ──────────────────────────────
        att_result = extract_attachments(t)
        result["attachments"] = att_result.get("attachments", [])
        result["features"]    = att_result.get("features", [])

        return result

    except Exception as exc:
        print(f"[MTM] parse_listing error: {exc}")
        return dict.fromkeys(
            ["year", "make", "model", "equipment_type",
             "hours", "price_value", "price_is_obo",
             "location", "contact", "condition", "notes",
             "attachments", "features"]
        )


# ══════════════════════════════════════════════════════════════════════════════
# ADAPTER WRAPPERS
# ══════════════════════════════════════════════════════════════════════════════

def safe_lookup_machine(parsed: dict) -> tuple[dict | None, float]:
    """Calls lookup_machine; returns (None, 0.0) on failure or no identity."""
    if not parsed.get("make") and not parsed.get("model"):
        return None, 0.0
    try:
        return _stub_lookup_machine(parsed)   # ── SWAP ──
    except Exception as exc:
        print(f"[MTM] lookup_machine error: {exc}")
        return None, 0.0


def format_output_response(
    cleaned_listing: str,
    parsed: dict,
    added_specs: dict | None,
    confidence_note: str | None,
) -> dict:
    """Shapes final dict → FixListingResponse in app.py."""
    # Build the parsed_machine display dict — convert price fields to display string
    display = {}
    for k, v in parsed.items():
        if v is None or v == [] or v is False:
            continue
        if k == "hours" and v:
            display["machine_hours"] = v   # structured hours field for API consumers
        elif k == "price_value" and v:
            price_str = f"${v:,}"
            if parsed.get("price_is_obo"):
                price_str += " OBO"
            display["price"] = price_str
        elif k == "price_is_obo":
            continue   # already folded into price above
        elif k == "attachments" and v:
            display["attachments"] = ", ".join(v)
        elif k == "features" and v:
            display["features"] = ", ".join(v)
        else:
            display[k] = v

    return {
        "cleaned_listing": cleaned_listing,
        "parsed_machine":  display,
        "added_specs":     added_specs,
        "confidence_note": confidence_note,
        "error":           None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def fix_listing_service(raw_text: str) -> dict:
    """
    Full pipeline:
        raw_text
          → safe_parse_listing  (regex + price + attachments + alias enrichment)
          → safe_lookup_machine (spec registry — stub)
          → _stub_build_listing_data
          → _stub_generate_listing_text
          → format_output_response
          → dict
    """
    # IMAGE PIPELINE HOOK — Future Enhancement (v2+)
    # When ready: image_notes = analyze_listing_image(image_data: bytes | None)
    # Do not implement in v1. See README > Future Enhancements.

    parsed            = safe_parse_listing(raw_text)
    specs, confidence = safe_lookup_machine(parsed)

    added_specs:     dict | None = None
    confidence_note: str | None  = None

    if specs is not None:
        pct = int(confidence * 100)
        if confidence >= SPEC_CONFIDENCE_THRESHOLD:
            added_specs     = specs
            confidence_note = f"Specs sourced from MTM registry (match confidence: {pct}%)"
        else:
            confidence_note = (
                f"Possible machine match ({pct}% confidence) — "
                "specs not injected. Verify before publishing."
            )

    listing_data    = _stub_build_listing_data(parsed, added_specs)   # ── SWAP ──
    cleaned_listing = _stub_generate_listing_text(listing_data, added_specs)  # ── SWAP ──

    return format_output_response(
        cleaned_listing=cleaned_listing,
        parsed=parsed,
        added_specs=added_specs,
        confidence_note=confidence_note,
    )