"""
listing_builder.py
==================
MTM V1 Listing Text Generator

Combines DealerInput (manual dealer fields) with resolved OEM specs to produce
a clean, dealer-ready listing description string.

Public API
----------
    build_feature_list(dealer_input)                   -> List[str]
    build_headline(dealer_input)                       -> str
    build_machine_snapshot(resolved_specs)             -> str
    build_spec_sheet_entries(resolved_specs)           -> List[tuple[str, str]]
    build_listing_text(dealer_input, resolved_specs)   -> str

The output of build_listing_text() is the generated_listing_text consumed by
listing_pack_builder.build_listing_pack() / build_listing_pack_v1().
"""

from __future__ import annotations

import re
from typing import List

from dealer_input import DealerInput


# ─────────────────────────────────────────────────────────────────────────────
# Feature toggle → human-readable label mapping
# ─────────────────────────────────────────────────────────────────────────────

_FEATURE_MAP: list[tuple[str, str]] = [
    # SSL / CTL
    ("cab_type",          "Cab"),              # string field: truthy when any cab type set
    ("heater",            "Heat"),             # renamed from heat in Phase 1
    ("ac",                "Air Conditioning"),
    ("high_flow",         "High Flow Hydraulics"),
    ("two_speed_travel",  "2-Speed Travel"),   # renamed from two_speed in Phase 1
    ("ride_control",      "Ride Control"),
    ("backup_camera",     "Backup Camera"),
    ("radio",             "Radio"),
    ("control_type",      "Controls"),         # string field: truthy when controls type set
    ("coupler_type",      "Quick Attach"),     # renamed from quick_attach in Phase 1
    ("tire_condition",    "Tires"),            # string field: truthy when condition described
    # Mini excavator
    ("thumb_type",        "Thumb"),            # renamed from thumb in Phase 1
    ("aux_hydraulics",    "Aux Hydraulics"),
    ("blade_type",        "Dozer Blade"),      # renamed from blade in Phase 1
    ("zero_tail_swing",   "Zero Tail Swing"),
    ("rubber_tracks",     "Rubber Tracks"),
    # Universal
    ("one_owner",         "One Owner Machine"),
]

# Features worth calling out in the headline (priority order)
_HEADLINE_FEATURES = ["cab_type", "high_flow", "two_speed", "ac"]


# ─────────────────────────────────────────────────────────────────────────────
# OEM spec field → display label mapping (ordered)
# ─────────────────────────────────────────────────────────────────────────────

_SPEC_LABELS: list[tuple[str, str, str]] = [
    # (field_key, display_label, unit_suffix)
    # Keys match spec resolver output field names exactly.
    ("net_hp",                    "Horsepower",               " HP"),
    ("roc_lb",                    "Rated Operating Capacity", " lbs"),
    ("tipping_load_lb",           "Tipping Load",             " lbs"),
    ("operating_weight_lb",       "Operating Weight",         " lbs"),
    ("hydraulic_flow_gpm",        "Auxiliary Hydraulic Flow", " GPM"),
    ("travel_speed_high_mph",     "Top Travel Speed",         " mph"),
    ("width_over_tires_in",       "Machine Width",            " in"),
    ("bucket_hinge_pin_height_in","Hinge Pin Height",         " in"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Task 1 — Feature list
# ─────────────────────────────────────────────────────────────────────────────

def build_feature_list(dealer_input: DealerInput) -> List[str]:
    """Return list of human-readable feature labels for all enabled toggles.

    Status string fields (high_flow, two_speed_travel): show only when "yes".
    "optional" means OEM offers it — not shown as a confirmed unit feature.
    """
    _STATUS_FIELDS = {"high_flow", "two_speed_travel"}
    result = []
    for field, label in _FEATURE_MAP:
        val = getattr(dealer_input, field, None)
        if field in _STATUS_FIELDS:
            if val == "yes":
                result.append(label)
        elif val:
            result.append(label)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Task 2 — Headline
# ─────────────────────────────────────────────────────────────────────────────

def _title_feature_tokens(
    dealer_input: DealerInput,
    use_case_payload: "dict | None" = None,
) -> list[str]:
    """
    Return 1–2 value-driver tokens for the listing title.

    Priority order:
      1. High flow + mulcher attachment → ["High Flow", "Mulching Head"]
      2. High flow confirmed            → ["High Flow"] + best structural feature
      3. Enclosed cab + A/C             → ["Enclosed Cab, A/C"]
      4. Enclosed cab only              → ["Enclosed Cab"]
      5. 2-speed confirmed              → ["2-Speed"]
    No fallback — hours-in-title is handled by build_headline when hours ≤ 500.
    """
    att_text = (dealer_input.attachments_included or "").lower()
    has_mulcher = any(kw in att_text for kw in (
        "mulch", "forestry head", "brush cutter", "masticator", "rotary cutter"
    ))

    _ENCLOSED = frozenset({"enclosed", "erops", "closed", "cab"})

    is_enclosed = bool(
        dealer_input.cab_type
        and dealer_input.cab_type.lower().strip() in _ENCLOSED
    )
    has_high_flow = dealer_input.high_flow == "yes"
    has_two_speed = dealer_input.two_speed_travel == "yes"

    tokens: list[str] = []

    if has_high_flow:
        if has_mulcher:
            # NO IMPLIED ATTACHMENTS RULE: only use attachment name if confirmed in
            # attachments_included — "Mulching Head" confirms included; "Mulcher Ready"
            # would imply capability, not a confirmed attachment.
            return ["High Flow", "Mulching Head"]
        tokens.append("High Flow")
        # Pair with second-best structural feature
        if is_enclosed:
            tokens.append("Enclosed Cab, A/C" if dealer_input.ac else "Enclosed Cab")
        elif has_two_speed:
            tokens.append("2-Speed")
        return tokens[:2]

    if is_enclosed:
        tokens.append("Enclosed Cab, A/C" if dealer_input.ac else "Enclosed Cab")
        if has_two_speed:
            tokens.append("2-Speed")
        return tokens[:2]

    if has_two_speed:
        tokens.append("2-Speed")

    return tokens


def build_headline(dealer_input: DealerInput, use_case_payload: "dict | None" = None) -> str:
    """
    Dealer-grade headline: YEAR MAKE MODEL — KEY VALUE DRIVER(S)

    Feature tokens take priority. When no tokens and hours ≤ 500, appends
    the actual hour count ("— 312 Hours") instead of a bare label.

    Examples:
        2021 CAT 299D3 XPS — High Flow, Enclosed Cab
        2019 Bobcat S650 — Enclosed Cab, 2-Speed
        2022 Kubota SVL75-2 — 312 Hours
        2018 JD 333G — High Flow, Mulching Head
    """
    base = f"{dealer_input.year} {dealer_input.make.upper()} {dealer_input.model}"
    tokens = _title_feature_tokens(dealer_input, use_case_payload)
    if tokens:
        return f"{base} \u2014 {', '.join(tokens)}"
    if dealer_input.hours and dealer_input.hours <= 500:
        return f"{base} \u2014 {dealer_input.hours:,} Hours"
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Task 3 — Machine Snapshot (OEM specs)
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_spec_value(value: float | int) -> str:
    """Format a spec value: collapse whole floats, comma-separate thousands."""
    if isinstance(value, float) and value == int(value):
        value = int(value)
    if isinstance(value, int) and value >= 1000:
        return f"{value:,}"
    return str(value)


def _display_items_for_listing(resolved_specs: dict, equipment_type: str = "") -> list[dict]:
    from mtm_service import build_tiered_specs

    tiers = build_tiered_specs(resolved_specs, {}, equipment_type)
    return tiers.get("technical") or tiers.get("standard") or tiers.get("essential") or []


def build_machine_snapshot(resolved_specs: dict, equipment_type: str = "") -> str:
    """
    Format available OEM spec fields into a clean block.
    Returns empty string if no relevant specs are present.
    """
    lines = [
        f"  \u2022 {item['label']}: {item['value']}"
        for item in _display_items_for_listing(resolved_specs, equipment_type)
    ]

    if not lines:
        return ""

    return "OEM Specs:\n" + "\n".join(lines)


def build_spec_sheet_entries(resolved_specs: dict, equipment_type: str = "") -> list[tuple[str, str]]:
    """
    Return [(label, value_string)] tuples for use with spec_sheet_generator.
    Only includes fields present and non-null in resolved_specs.
    """
    return [
        (item["label"], item["value"])
        for item in _display_items_for_listing(resolved_specs, equipment_type)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Presentation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_attachments_bullets(raw: str) -> str:
    """
    Render a free-text attachments string as a bulleted list.

    Splits on commas and/or line breaks so both "bucket, forks, auger"
    and multi-line dealer input produce individual bullets.
    Returns empty string if raw is blank.
    """
    parts = [p.strip() for p in re.split(r"[\n,]|\s+and\s+", raw, flags=re.IGNORECASE) if p.strip()]
    if not parts:
        return ""
    return "Attachments Included:\n" + "\n".join(f"  \u2022 {p.title()}" for p in parts)


def _fmt_details_bullets(raw: str) -> str:
    """
    Render free-text dealer details as a bulleted list, one bullet per line.

    Used for Additional Details (sales notes / remarks).
    Preserves dealer wording; only strips surrounding whitespace and drops
    blank lines.  Returns empty string if nothing survives.
    """
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    if not lines:
        return ""
    return "Additional Details:\n" + "\n".join(f"  \u2022 {ln}" for ln in lines)


def _fmt_feature_bullets(raw: str) -> list[str]:
    """
    Parse free-text additional features into a list of label strings.

    Splits on newlines so each line becomes its own bullet, merged into
    the Features section by the caller.  Returns empty list if blank.
    """
    return [ln.strip() for ln in raw.split("\n") if ln.strip()]


def _fmt_comparable_models(raw: str) -> str:
    """
    Render a free-text comparable models string as a bulleted list.

    Splits on commas and/or newlines so both "Cat 259, Kubota SVL65-2"
    and multi-line input produce individual bullets.
    Returns empty string if raw is blank.
    """
    parts = [p.strip() for p in re.split(r"[\n,]", raw) if p.strip()]
    if not parts:
        return ""
    return "Comparable Models:\n" + "\n".join(f"  \u2022 {p}" for p in parts)


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compact_listing(text: str) -> str:
    """
    Normalize listing text spacing:
    - Remove blank lines immediately after section headers (Header:\\n\\n → Header:\\n)
    - Collapse 3+ consecutive newlines to exactly 2 (one blank line between sections)
    """
    # Collapse blank line directly after any "Header:" or "Header" line
    text = re.sub(r'(:\n)\n+', r'\1', text)
    # Collapse any run of 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Mini Excavator — Dealer-quality listing builder
# ─────────────────────────────────────────────────────────────────────────────

_TAIL_SWING_SHORT: dict[str, str] = {
    "zero":         "Zero tail swing",
    "reduced":      "Reduced tail swing",
    "conventional": "Conventional tail swing",
}


def _build_mini_ex_headline(dealer_input: DealerInput) -> str:
    """
    Dealer-style mini ex headline: YEAR MAKE MODEL — Key Feature 1, Key Feature 2

    Matches V1 title style: em dash, title-case features, up to 2 value drivers.
    Price is rendered separately (below the title) in the listing body.
    """
    base = f"{dealer_input.year} {dealer_input.make.upper()} {dealer_input.model}"

    tokens: list[str] = []
    if dealer_input.cab_type and dealer_input.cab_type.lower().strip() in _ENCLOSED_CAB_VALUES:
        tokens.append("Cab, A/C" if dealer_input.ac else "Enclosed Cab")
    if dealer_input.thumb_type and dealer_input.thumb_type.lower() != "none":
        tokens.append("Thumb")
    if dealer_input.aux_hydraulics:
        tokens.append("Aux Hydraulics")

    if tokens:
        return f"{base} \u2014 {', '.join(tokens[:2])}"
    if dealer_input.hours and dealer_input.hours <= 500:
        return f"{base} \u2014 {dealer_input.hours:,} Hours"
    return base


def _build_mini_ex_opening(dealer_input: DealerInput) -> str:
    """1–2 sentence dealer-quality opening paragraph for mini ex listings."""
    model_id = f"{dealer_input.make} {dealer_input.model}"

    # Sentence 1: cab configuration
    if dealer_input.cab_type:
        extras: list[str] = []
        if dealer_input.heater:
            extras.append("heat")
        if dealer_input.ac:
            extras.append("A/C")
        cab_desc = "enclosed cab"
        if extras:
            cab_desc += f", {' & '.join(extras)}"
        s1 = f"Clean, well-maintained {model_id} with {cab_desc}."
    else:
        s1 = f"Clean, well-maintained {model_id} with open canopy."

    # Sentence 2: key work features
    work_parts: list[str] = []
    if dealer_input.thumb_type:
        work_parts.append("hydraulic thumb")
    if dealer_input.aux_hydraulics:
        work_parts.append("auxiliary hydraulics")

    if work_parts:
        s2 = f"Tight machine with {' and '.join(work_parts)} \u2014 ready to go straight to work."
    else:
        s2 = "Tight machine ready to go straight to work."

    return f"{s1} {s2}"


def _build_mini_ex_key_features(dealer_input: DealerInput) -> list[str]:
    """Ordered market-facing key features for mini ex listings. Hours goes first."""
    lines: list[str] = []

    # Hours — always first
    lines.append(f"~{dealer_input.hours:,} hours")

    # Cab + comfort
    if dealer_input.cab_type:
        extras: list[str] = []
        if dealer_input.heater:
            extras.append("heat")
        if dealer_input.ac:
            extras.append("A/C")
        if extras:
            lines.append(f"Enclosed cab w/ {' & '.join(extras)}")
        else:
            lines.append("Enclosed cab")

    # Work attachments / features in buyer-priority order
    if dealer_input.thumb_type:
        lines.append("Hydraulic thumb")
    if dealer_input.aux_hydraulics:
        lines.append("Auxiliary hydraulics")
    if dealer_input.coupler_type:
        lines.append("Quick attach coupler")
    if dealer_input.blade_type:
        lines.append("Dozer blade")
    if dealer_input.two_speed_travel == "yes":
        lines.append("2-speed travel")
    if dealer_input.rubber_tracks:
        lines.append("Rubber tracks")
    if dealer_input.zero_tail_swing:
        lines.append("Zero tail swing")
    if dealer_input.backup_camera:
        lines.append("Backup camera")
    if dealer_input.one_owner:
        lines.append("One owner")

    # Track condition — free text, show if provided
    if dealer_input.track_condition:
        lines.append(f"Tracks: {dealer_input.track_condition}")

    # Additional free-text features
    lines.extend(_fmt_feature_bullets(dealer_input.additional_features or ""))

    return lines


def _build_mini_ex_specs_block(resolved_specs: dict, make: str = "") -> str:
    """OEM-backed specs section for mini ex listings, formatted for dealer use."""
    lines: list[str] = []

    # HP / Engine
    hp = resolved_specs.get("net_hp")
    if hp is not None:
        hp_str = _fmt_spec_value(hp)
        engine_line = f"~{hp_str} HP"
        if make:
            engine_line += f" {make} diesel"
        else:
            engine_line += " diesel"
        lines.append(engine_line)

    # Operating weight
    wt = resolved_specs.get("operating_weight_lb")
    if wt is not None:
        lines.append(f"~{int(round(wt)):,} lb operating weight")

    # Max dig depth (pre-formatted "X ft Y in" string from resolver)
    depth = resolved_specs.get("max_dig_depth")
    if depth is not None:
        lines.append(f"~{depth} max dig depth")

    # Auxiliary hydraulic flow
    flow = resolved_specs.get("hydraulic_flow_gpm")
    if flow is not None:
        lines.append(f"~{_fmt_spec_value(flow)} GPM auxiliary hydraulic flow")

    # Bucket breakout force
    bbf = resolved_specs.get("bucket_breakout_lb")
    if bbf is not None:
        lines.append(f"~{int(round(bbf)):,} lbf bucket breakout force")

    # Tail swing
    tail = resolved_specs.get("tail_swing_type")
    if tail is not None:
        tail_label = _TAIL_SWING_SHORT.get(str(tail).lower(), str(tail).replace("_", " ").title())
        lines.append(tail_label)

    # Machine width
    width = resolved_specs.get("width_in")
    if width is not None:
        lines.append(f"~{int(round(width))}\" machine width")

    if not lines:
        return ""
    return "Core Specs:\n" + "\n".join(f"  \u2022 {ln}" for ln in lines)


def _mini_ex_context_sentence(
    dealer_input: "DealerInput | None",
    resolved_specs: "dict | None",
) -> str:
    """
    Return a single spec-driven context sentence for the Why This Machine block.
    Priority order: thumb confirmed > machine size / dig depth > tail swing > aux hydraulics.
    Avoids generic filler — returns empty string rather than a weak sentence.
    """
    specs = resolved_specs or {}
    di    = dealer_input

    # Resolve weight from either spec-resolver name or registry schema name.
    weight: "float | None" = specs.get("operating_weight_lb") or specs.get("operating_weight_lbs")
    dig:    "float | None" = None
    tail:   str             = str(specs.get("tail_swing_type") or "").lower()
    width:  "float | None" = specs.get("width_in")

    # Parse dig depth from "X ft Y in" string if present (spec resolver format)
    raw_dig = specs.get("max_dig_depth")
    if isinstance(raw_dig, (int, float)):
        dig = float(raw_dig)
    elif isinstance(raw_dig, str):
        import re as _re
        m = _re.match(r"(\d+)\s*ft(?:\s*(\d+)\s*in)?", raw_dig.strip())
        if m:
            dig = int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)
    if dig is None:
        dig = specs.get("max_dig_depth_ft")

    has_thumb = di and bool(getattr(di, "thumb_type", None) and
                            getattr(di, "thumb_type") not in ("none", ""))
    has_aux   = di and bool(getattr(di, "aux_hydraulics", None))

    # 1. Thumb — confirms versatility beyond pure trenching
    if has_thumb:
        return "Hydraulic thumb makes it effective for moving debris, rock, and brush on the same pass."

    # 2. Weight class + dig depth drive the primary context
    if weight:
        if weight < 5000:
            # Compact / micro — access is the story
            if "zero" in tail:
                return "Compact size and zero tail swing get into gate-restricted yards and tight urban sites."
            return "Compact size fits through standard gates and into backyard or interior-access sites."
        elif weight < 8500:
            # Mid range — balance of access and productivity
            if "zero" in tail:
                return "Zero tail swing allows full rotation in fenced yards and alleyways without swinging over the work area."
            if width and width <= 60:
                return "Narrow footprint and zero tail swing handle residential and backyard work without secondary equipment."
            return "Well-proportioned for residential and light commercial jobs with standard transport."
        elif weight < 13000:
            # Production class — dig depth and commercial work
            if dig and dig >= 14.0:
                return "Dig depth handles septic systems, utility crossings, and deep footing work in full commercial production."
            if dig and dig >= 11.0:
                return "Dig depth covers standard utility and septic work — strong performer for residential and light commercial jobs."
            return "Production-class machine handles utility, footing, and commercial site work at full rates."
        else:
            # Large mini / full production
            if dig and dig >= 16.0:
                return "Full-production dig depth suited for deep utility infrastructure, large septic systems, and commercial excavation."
            return "Production-class dig depth and reach suited for commercial utility and infrastructure work."

    # 3. Tail swing — relevant when weight is unknown
    if "zero" in tail:
        return "Zero tail swing allows rotation in confined spaces without the machine overhanging the work area."

    # 4. Aux hydraulics without thumb — attachment versatility
    if has_aux:
        return "Auxiliary hydraulics support trenching heads, augers, and breaker attachments on the same machine."

    # 5. Nothing useful known — return empty; caller handles gracefully
    return ""


# Short noun phrases for each mini ex use case label (used in "Why This Machine" 2-use-case join)
_MEX_UC_SHORT: dict[str, str] = {
    "Excavation & Digging": "excavation",
    "Utility Trenching":    "utility trenching",
    "Land Clearing":        "land clearing",
    "Demolition & Breaking": "demolition",
    "Auger Work":           "auger work",
    "Farm & Agriculture Work": "farm work",
}


def _build_mini_ex_why(
    use_case_payload: "dict | None",
    dealer_input: "DealerInput | None" = None,
    resolved_specs: "dict | None" = None,
) -> str:
    """
    Why This Machine section for mini excavator listings.

    Sentence 1: use-case-derived primary claim (short, no comma-heavy joining).
    Sentence 2: spec/feature-driven context sentence.
    """
    use_cases = (use_case_payload or {}).get("top_use_cases_for_listing") or []

    if use_cases:
        if len(use_cases) >= 2:
            # Use short phrases to avoid joining two long comma-heavy descriptor strings
            d1 = _MEX_UC_SHORT.get(use_cases[0], use_cases[0].lower())
            d2 = _MEX_UC_SHORT.get(use_cases[1], use_cases[1].lower())
            s1 = f"Strong mini excavator for {d1} and {d2}."
        else:
            descriptor = _UC_DESCRIPTOR.get(use_cases[0], use_cases[0].lower())
            s1 = f"Strong mini excavator for {descriptor}."
    else:
        s1 = "Good machine for trenching, utility work, and site prep."

    s2 = _mini_ex_context_sentence(dealer_input, resolved_specs)
    para = f"{s1} {s2}".strip() if s2 else s1

    return f"Why This Machine:\n  {para}"


def _build_mini_ex_listing(
    dealer_input: DealerInput,
    resolved_specs: dict,
    use_case_payload: "dict | None" = None,
) -> str:
    """
    Build a dealer-quality mini excavator listing with enforced section structure:
      1. Headline
      2. $Price (if set)
      3. Core Specs (OEM-backed)
      4. Features (market-facing, hours first)
      5. Best For (scorer-backed bullets)
      6. Attachments Included (if provided)
      7. Additional Details (if provided)
      8. Contact Details
    """
    sections: list[str] = []

    # 1. Headline
    sections.append(_build_mini_ex_headline(dealer_input))

    # 2. Asking price (if provided)
    if dealer_input.asking_price:
        sections.append(f"${dealer_input.asking_price:,}")

    # 3. Core Specs (OEM-backed)
    specs_block = _build_mini_ex_specs_block(resolved_specs, make=dealer_input.make)
    if specs_block:
        sections.append(specs_block)

    # 4. Features (market-facing, hours first)
    feat_lines = _build_mini_ex_key_features(dealer_input)
    if feat_lines:
        sections.append("Features:\n" + "\n".join(f"  \u2022 {f}" for f in feat_lines))

    # 5. Attachments Included (if provided)
    if dealer_input.attachments_included and dealer_input.attachments_included.strip():
        att_block = _fmt_attachments_bullets(dealer_input.attachments_included.strip())
        if att_block:
            sections.append(att_block)

    # 6. Best For (scorer-backed, optional)
    if use_case_payload:
        uc_section = _build_use_case_section(use_case_payload)
        if uc_section:
            sections.append(uc_section)

    # 7. Additional Details (if provided)
    details_raw = (dealer_input.additional_details or dealer_input.condition_notes or "").strip()
    if details_raw:
        details_block = _fmt_details_bullets(details_raw)
        if details_block:
            sections.append(details_block)

    # 8. Contact Details (always last)
    sections.append("Contact Details:\nCall or text to schedule a look.")

    return _compact_listing("\n\n".join(sections))


# ─────────────────────────────────────────────────────────────────────────────
# Dealer-grade prose description builders (V1 non-mini-ex flow)
# ─────────────────────────────────────────────────────────────────────────────

_ENCLOSED_CAB_VALUES = frozenset({"enclosed", "erops", "closed", "cab"})


def _build_p1_identity(dealer_input: DealerInput) -> str:
    """
    Para 1 — machine identity, hours, and top config fact.

    Pattern: "[Condition] [Year] [Make] [Model] with [hours] hours. [Config clause]."
    """
    make_model = f"{dealer_input.make} {dealer_input.model}"
    hours_str  = f"{dealer_input.hours:,}"

    # Condition phrase keyed on hours
    if dealer_input.hours < 1000:
        condition = "Low-hour"
    elif dealer_input.hours < 2500:
        condition = "Clean"
    elif dealer_input.hours < 4500:
        condition = "Well-used"
    else:
        condition = "High-hour working"

    # Top config clause — one concise statement
    config: str = ""
    is_enclosed = (
        dealer_input.cab_type
        and dealer_input.cab_type.lower().strip() in _ENCLOSED_CAB_VALUES
    )

    if dealer_input.high_flow == "yes" and is_enclosed:
        comforts = []
        if dealer_input.heater:
            comforts.append("heat")
        if dealer_input.ac:
            comforts.append("A/C")
        comforts.append("high-flow hydraulics")
        config = f"Enclosed cab with {', '.join(comforts[:-1])}, and {comforts[-1]}." \
            if len(comforts) > 1 else f"Enclosed cab with {comforts[0]}."
    elif dealer_input.high_flow == "yes":
        config = "High-flow hydraulics ready for demanding attachments."
    elif is_enclosed:
        comforts = []
        if dealer_input.heater:
            comforts.append("heat")
        if dealer_input.ac:
            comforts.append("A/C")
        comfort_str = f" with {' and '.join(comforts)}" if comforts else ""
        config = f"Enclosed cab{comfort_str}."

    base = f"{condition} {dealer_input.year} {make_model} with {hours_str} hours."
    return f"{base} {config}".strip() if config else base


def _build_p2_capability(
    use_cases: list[str],
    dealer_input: DealerInput,
    equipment_type: str = "",
) -> str:
    """
    Para 2 — what this machine does well.

    Informed by use case labels but NOT a copy of them.
    Uses natural contractor language, no marketing fluff.
    """
    uc_set = set(use_cases[:2])

    # Telehandler — spec-driven prose
    if equipment_type == "telehandler":
        if "Rooftop Material Placement" in uc_set or "High-Reach Loading" in uc_set:
            return (
                "Lift height and reach make it effective on commercial sites for truss placement, "
                "rooftop staging, and reaching over obstacles. Gets the job done without a crane."
            )
        return (
            "Good jobsite machine for material staging, pallet distribution, and placement at height. "
            "Works well on standard construction sites for keeping trades supplied."
        )

    # Dozer
    if equipment_type == "dozer":
        return (
            "Built for grading and pushing work. "
            "Handles rough site prep, land clearing, and production earthwork without issue."
        )

    # Wheel loader
    if equipment_type == "wheel_loader":
        return (
            "Solid material handler for pallet work, bucket loading, and yard operations. "
            "Works well in yards, on job sites, and for high-cycle loading work."
        )

    # Backhoe
    if equipment_type == "backhoe_loader":
        if "Utility Trenching" in uc_set:
            return (
                "Good all-around machine for trenching, utility work, and light excavation. "
                "Loader end handles material movement and backfill on the same pass."
            )
        return (
            "Versatile machine that handles digging, loading, and utility work without swapping equipment. "
            "Good choice for mixed-use residential and light commercial sites."
        )

    # Combo — Forestry Mulching + Land Clearing
    if "Forestry Mulching" in uc_set and "Land Clearing" in uc_set:
        return (
            "Good setup for clearing lots and running production mulching. "
            "High-flow output handles a forestry head or rotary cutter at full production rates."
        )

    # Land Clearing primary
    if "Land Clearing" in uc_set and "Grading & Site Prep" in uc_set:
        return (
            "Handles lot clearing, rough grading, and site preparation. "
            "Good daily driver for mixed earthwork on residential and commercial jobs."
        )

    if "Forestry Mulching" in uc_set:
        return (
            "High-flow setup for production mulching work. "
            "Runs a forestry head or heavy rotary cutter at full output without restriction."
        )

    if "Land Clearing" in uc_set:
        return (
            "Good machine for lot clearing, brush removal, and general site cleanup. "
            "Handles the push-and-lift work that clearing jobs require."
        )

    # Grading + Material Handling
    if "Grading & Site Prep" in uc_set and "Material Handling" in uc_set:
        return (
            "Solid all-around machine for site work, backfilling, and material handling. "
            "Good daily driver for contractors who need one machine that covers multiple jobs."
        )

    # Material Handling + Truck Loading
    if "Material Handling" in uc_set and "Truck Loading" in uc_set:
        return (
            "Strong performer for pallet handling, truck loading, and on-site material staging. "
            "Works well in yards and on active job sites with high material throughput."
        )

    # Demolition
    if "Demolition & Breaking" in uc_set:
        att_text = (dealer_input.attachments_included or "").lower()
        has_breaker = any(kw in att_text for kw in ("breaker", "hammer", "hoe ram"))
        if has_breaker:
            return (
                "Hydraulic setup runs a breaker without issue for concrete demolition, "
                "slab removal, and structure work."
            )
        return (
            "Capable of demolition and site clearing work. "
            "Aux hydraulics support a hydraulic breaker on this setup."
        )

    # Utility Trenching
    if "Utility Trenching" in uc_set:
        pair = (uc_set - {"Utility Trenching"})
        if "Rock Trenching" in pair:
            return (
                "Set up for trenching through hard ground and rock. "
                "Handles ground conditions that stop standard machines."
            )
        return (
            "Handles trenching, utility installs, and drainage runs. "
            "Good fit for residential and light commercial utility work."
        )

    # Excavation & Digging
    if "Excavation & Digging" in uc_set:
        return (
            "Strong performer for footings, drainage excavation, and general digging. "
            "Good capability for residential and light commercial job sites."
        )

    # Auger
    if "Auger Work" in uc_set:
        return (
            "Good machine for post hole drilling, pier installation, and soil boring. "
            "Aux hydraulics support a standard auger without issue."
        )

    # Cold planing
    if "Cold Planing / Asphalt Milling" in uc_set:
        return (
            "High-flow output supports a cold planer or milling head for asphalt work. "
            "Runs at full milling capacity without restriction."
        )

    # Grading only
    if "Grading & Site Prep" in uc_set:
        return (
            "Solid performer for grading, backfilling, and site prep. "
            "Good daily driver for earthwork production on residential and commercial sites."
        )

    # Material Handling only
    if "Material Handling" in uc_set or "Truck Loading" in uc_set:
        return (
            "Good material handler for pallet work, loading trucks, and on-site staging. "
            "Works well in yards and on production sites."
        )

    # Farm & Agriculture
    if "Farm & Agriculture Work" in uc_set:
        return (
            "Good farm machine for irrigation work, field grading, and ag material handling. "
            "Well-suited for day-to-day property and farm work."
        )

    # Generic fallback
    return (
        "Well-maintained machine ready for production work. "
        "Good general-purpose fit for a wide range of job site applications."
    )


def _build_p3_config(dealer_input: DealerInput) -> str:
    """
    Para 3 — configuration: cab, hydraulics, speed, quick attach, key extras.

    Short sentences. No repetition of para 1 facts.
    """
    is_enclosed = (
        dealer_input.cab_type
        and dealer_input.cab_type.lower().strip() in _ENCLOSED_CAB_VALUES
    )

    sentences: list[str] = []

    # Cab — only if not already in P1 (P1 mentions it when paired with high flow or standalone)
    # P3 mentions cab regardless since it's structural config info
    if is_enclosed:
        comforts = []
        if dealer_input.heater:
            comforts.append("heat")
        if dealer_input.ac:
            comforts.append("A/C")
        if comforts:
            sentences.append(f"Enclosed cab with {' and '.join(comforts)}.")
        else:
            sentences.append("Enclosed cab.")
    elif dealer_input.cab_type:
        sentences.append("Open cab.")

    # Hydraulics + speed + quick attach as one sentence if multiple
    config_items: list[str] = []
    if dealer_input.high_flow == "yes":
        config_items.append("high-flow hydraulics")
    if dealer_input.two_speed_travel == "yes":
        config_items.append("2-speed travel")
    if dealer_input.coupler_type and dealer_input.coupler_type != "pin-on":
        config_items.append("quick attach")
    if dealer_input.ride_control:
        config_items.append("ride control")
    if dealer_input.has_stabilizers:
        config_items.append("outrigger stabilizers")
    if dealer_input.backup_camera:
        config_items.append("backup camera")
    if dealer_input.radio:
        config_items.append("radio")

    if config_items:
        if len(config_items) == 1:
            sentences.append(f"{config_items[0].capitalize()}.")
        elif len(config_items) == 2:
            sentences.append(f"{config_items[0].capitalize()} and {config_items[1]}.")
        else:
            mid = ", ".join(c.capitalize() if i == 0 else c for i, c in enumerate(config_items[:-1]))
            sentences.append(f"{mid}, and {config_items[-1]}.")

    # Track / tire condition
    if dealer_input.track_condition:
        sentences.append(f"Tracks: {dealer_input.track_condition}.")
    if dealer_input.tire_condition:
        sentences.append(f"Tires: {dealer_input.tire_condition}.")

    # One-owner callout
    if dealer_input.one_owner:
        sentences.append("One owner.")

    return " ".join(sentences)


def _build_features_block(dealer_input: DealerInput) -> str:
    """
    FEATURES section — bulleted list of confirmed configuration items.

    Locked order:
      1. Cab + comforts (enclosed with heat & A/C, or open cab)
      2. High-flow hydraulics
      3. 2-speed travel
      4. Ride control
      5. Quick attach
      6. Backup camera
      7. Radio
      8. Air ride seat
      9. One owner
      10. Track / tire condition
      11. Additional dealer-entered features (free text, one bullet per line)

    Returns empty string if nothing to show.
    """
    bullets: list[str] = []

    is_enclosed = (
        dealer_input.cab_type
        and dealer_input.cab_type.lower().strip() in _ENCLOSED_CAB_VALUES
    )

    if is_enclosed:
        comforts = []
        if dealer_input.heater:
            comforts.append("heat")
        if dealer_input.ac:
            comforts.append("A/C")
        if comforts:
            bullets.append(f"Enclosed cab with {' & '.join(comforts)}")
        else:
            bullets.append("Enclosed cab")
    elif dealer_input.cab_type:
        bullets.append("Open cab")

    if dealer_input.high_flow == "yes":
        bullets.append("High-flow hydraulics")
    if dealer_input.two_speed_travel == "yes":
        bullets.append("2-speed travel")
    if dealer_input.ride_control:
        bullets.append("Ride control")
    if dealer_input.coupler_type and dealer_input.coupler_type not in ("pin-on", ""):
        bullets.append("Quick attach")
    if dealer_input.backup_camera:
        bullets.append("Backup camera")
    if dealer_input.radio:
        bullets.append("Radio")
    if getattr(dealer_input, "air_ride_seat", None):
        bullets.append("Air ride seat")
    if dealer_input.one_owner:
        bullets.append("One owner")

    if dealer_input.track_condition:
        bullets.append(f"Tracks: {dealer_input.track_condition}")
    if dealer_input.tire_condition:
        bullets.append(f"Tires: {dealer_input.tire_condition}")

    # Dealer free-text additional features (one line = one bullet)
    extra = _fmt_feature_bullets(dealer_input.additional_features or "")
    bullets.extend(extra)

    if not bullets:
        return ""
    return "Features:\n" + "\n".join(f"  \u2022 {b}" for b in bullets)


def _build_p4_close(dealer_input: DealerInput) -> str:
    """Para 4 — simple close. No repeated features. No marketing language."""
    if dealer_input.asking_price:
        return "Call or text to schedule a look."
    return "Call or text for pricing and availability."


def _build_key_details(
    dealer_input: DealerInput,
    resolved_specs: dict,
    equipment_type: str = "",
) -> str:
    """
    KEY DETAILS block — factual bullet list.

    Hours always first. OEM specs follow. Confirmed features last.
    Skipped entirely if nothing meaningful to show beyond hours.
    """
    lines: list[str] = []

    # Hours — always first
    lines.append(f"{dealer_input.hours:,} hours")

    # OEM specs via the existing tiered display system
    spec_items = _display_items_for_listing(resolved_specs, equipment_type)
    for item in spec_items:
        lines.append(f"{item['label']}: {item['value']}")

    # Confirmed configuration features (not already in spec items)
    if dealer_input.high_flow == "yes":
        lines.append("High-flow hydraulics")
    if dealer_input.two_speed_travel == "yes":
        lines.append("2-speed travel")

    if not lines:
        return ""

    return "Core Specs:\n" + "\n".join(f"  \u2022 {ln}" for ln in lines)


# ─────────────────────────────────────────────────────────────────────────────
# Task 4 + 5 — Full listing builder
# ─────────────────────────────────────────────────────────────────────────────

def build_listing_text(
    dealer_input: DealerInput,
    resolved_specs: dict,
    use_case_payload: "dict | None" = None,
    equipment_type: str = "",
) -> str:
    """
    Produce a complete dealer-ready listing description string.

    LOCKED STRUCTURE (all equipment types):

      TITLE
      $Price               (if set)

      Core Specs:          (hours + OEM specs)
      • ...

      Features:            (confirmed config bullets)
      • ...

      Best For:            (scorer-backed, optional)
      • ...

      Attachments Included: (if provided)
      • ...

      Extras:              (dealer notes, if provided)
      • ...

      Contact Details:
      Call or text to schedule a look.

    No prose paragraphs. No --- dividers. One blank line between sections.
    Empty sections are suppressed cleanly.
    """
    # Mini excavator: enforced dealer-quality structure (separate builder)
    if equipment_type == "mini_excavator":
        return _build_mini_ex_listing(dealer_input, resolved_specs, use_case_payload)

    sections: list[str] = []

    # 1. Title
    sections.append(build_headline(dealer_input, use_case_payload))

    # 2. Asking price (if provided)
    if dealer_input.asking_price:
        sections.append(f"${dealer_input.asking_price:,}")

    # 3. Core Specs (hours + OEM specs)
    key_details = _build_key_details(dealer_input, resolved_specs, equipment_type)
    if key_details:
        sections.append(key_details)

    # 4. Features block (cab, comforts, hydraulics, radio, condition, etc.)
    features_block = _build_features_block(dealer_input)
    if features_block:
        sections.append(features_block)

    # 5. Attachments Included
    if dealer_input.attachments_included and dealer_input.attachments_included.strip():
        att_block = _fmt_attachments_bullets(dealer_input.attachments_included.strip())
        if att_block:
            sections.append(att_block)

    # 6. Best For (scorer-backed, optional)
    if use_case_payload:
        uc_section = _build_use_case_section(use_case_payload)
        if uc_section:
            sections.append(uc_section)

    # 7. Extras / dealer notes (optional)
    details_raw = (dealer_input.additional_details or dealer_input.condition_notes or "").strip()
    if details_raw:
        details_block = _fmt_details_bullets(details_raw)
        if details_block:
            sections.append(details_block)

    # 8. Contact Details (always last)
    sections.append("Contact Details:\nCall or text to schedule a look.")

    return _compact_listing("\n\n".join(sections))


# ─────────────────────────────────────────────────────────────────────────────
# Use case descriptor lookup
# ─────────────────────────────────────────────────────────────────────────────
# Jobsite-specific descriptors for each taxonomy use case label.
# These are used only in listing text (not spec sheet or preview UI,
# which display the short label only).

_UC_DESCRIPTOR: dict[str, str] = {
    "Grading & Site Prep":              "rough grading, backfilling, and pad preparation",
    "Utility Trenching":                "utility trenching, drainage runs, and conduit installation",
    "Rock Trenching":                   "trenching through rock, caliche, and hard compacted ground",
    "Material Handling":                "pallet handling, loading trucks, and on-site material staging",
    "Truck Loading":                    "loading dump trucks, bucket staging, and bulk material transfer",
    "Excavation & Digging":             "footings, drainage excavation, and site preparation",
    "Land Clearing":                    "brush clearing, lot cleanup, and site clearing",
    "Forestry Mulching":                "brush mulching, right-of-way clearing, and heavy vegetation removal",
    "Demolition & Breaking":            "concrete breaking, slab demolition, and structure teardown",
    "Auger Work":                       "post hole drilling, pier installation, and soil boring",
    "Cold Planing / Asphalt Milling":   "milling passes, asphalt removal, and surface preparation",
    "Stump Grinding":                   "stump removal, below-grade grinding, and root zone clearing",
    "Snow Removal":                     "snow pushing, parking lot clearing, and pile loading",
    "Concrete & Flatwork Prep":         "sub-base preparation, slab forming, and pour cleanup",
    "Farm & Agriculture Work":          "irrigation ditch digging, field grading, and ag material hauling",
    # New labels added with engine rebuild
    "Yard & Staging Work":              "yard handling, staging operations, and loading in covered work areas",
    "Elevated Material Placement":      "rooftop staging, truss placement, and elevated material handling",
    # Telehandler-specific labels
    "Rooftop Material Placement":       "setting roof trusses, placing shingle bundles, and staging HVAC units on decks",
    "Jobsite Reach & Placement":        "placing loads at height, reaching over obstacles, and keeping trades supplied with material",
    "High-Reach Loading":               "reaching over site barriers, staging on elevated decks, and loading at extended heights",
    "Pallet Handling":                  "unloading flatbeds, distributing pallets on site, and staging materials at work areas",
    "Framing Support":                  "lifting wall panels, placing ridge beams, and staging framing materials at height",
    "Masonry Support":                  "placing block cubes, staging mortar boards, and lifting masonry to floor levels",
    "Agricultural Use":                 "loading bale wagons, stacking hay, and moving bulk ag material around the yard",
}


def _build_use_case_section(payload: dict) -> str:
    """
    Format the scorer payload as a clean Best For bullet block.

    Renders as:
        Best For:
          • Label
          • Label

    No descriptors. No trailing sentences. Logic layer only.
    Attachment sentences and limitations are rendered in the description prose.
    """
    use_cases = payload.get("top_use_cases_for_listing") or []
    if not use_cases:
        return ""

    lines = [f"  \u2022 {label}" for label in use_cases[:3]]
    return "Best For:\n" + "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Dual-output: UI layer (label + descriptor) vs listing layer (label only)
# ─────────────────────────────────────────────────────────────────────────────

def build_use_case_ui_items(use_case_payload: "dict | None") -> "list[dict]":
    """
    Return UI-layer Best For items: label + descriptor for rich display.

    Each item:
        {"label": "Land Clearing", "descriptor": "clearing brush, opening lots, and site cleanup"}

    Descriptors come from _UC_DESCRIPTOR — the single source of truth for
    use-case language.  All descriptors are grounded in actual scoring logic,
    not generic filler.

    Used for the result page UI card only.  Listing export (listing_description.txt)
    uses the label-only output from _build_use_case_section().

    Returns empty list when payload is None, empty, or has no qualifying use cases.
    """
    use_cases = (use_case_payload or {}).get("top_use_cases_for_listing") or []
    items: list[dict] = []
    for label in use_cases[:3]:
        descriptor = _UC_DESCRIPTOR.get(label, "")
        items.append({"label": label, "descriptor": descriptor})
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Example / smoke test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample_input = DealerInput(
        year=2019,
        make="Kubota",
        model="SVL75-2",
        hours=3250,
        cab_type="enclosed",
        heat=True,
        ac=False,
        high_flow=True,
        two_speed=True,
        ride_control=False,
        backup_camera=True,
        one_owner=True,
        track_condition="70%",
        attachments_included="72\" bucket, pallet forks",
        condition_notes="Machine is ready to work. No known issues.",
    )

    sample_specs = {
        "horsepower_hp": 74.3,
        "rated_operating_capacity_lbs": 2690,
        "tipping_load_lbs": 5380,
        "operating_weight_lbs": 10053,
        "aux_flow_standard_gpm": 22.4,
        "travel_speed_high_mph": 7.1,
        "width_over_tires_in": 72.2,
        "bucket_hinge_pin_height_in": 122.0,
    }

    print(build_listing_text(sample_input, sample_specs))
