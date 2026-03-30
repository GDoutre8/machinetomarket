# =============================================================================
# MTM Parser v1
# Status: Frozen
# Verified: 50/50 stress test pass
# Date: 2026-03-11
# =============================================================================
# MTM Parser Baseline — Frozen Demo Version
# Component: Attachment Detection
# Status: Frozen for demo integration
# Date: 2026-03-11

import re

# ══════════════════════════════════════════════════════════════════════════════
# ATTACHMENT / FEATURE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

# ── Priority order for output grouping ───────────────────────────────────────

ATTACHMENT_PRIORITY = [
    # Work tools
    "Tooth Bucket",
    "Smooth Bucket",
    "Grading Bucket",
    "Bucket",
    "Pallet Forks",
    "Grapple",
    "Auger",
    "Trencher",
    "Broom",
    "Snow Blade",
    "Snow Pusher",
    "Mower",
    "Mulcher",
    "Brush Cutter",
    "Hydraulic Breaker",
    "Ripper",
    "Compactor",
    "Stump Grinder",
    # Hydraulic tools
    "Hydraulic Thumb",
    "Manual Thumb",
    "Thumb",
    "Hydraulic Coupler",
    "Quick Coupler",
    "Pin Grabber",
    # Hydraulic / flow
    "Auxiliary Hydraulics",
    "High Flow",
    "Standard Flow",
    "2-Speed",
    # Cab / operator
    "Enclosed Cab",
    "Cab",
    "Heat",
    "A/C",
    "Radio",
    "Backup Camera",
    "Ride Control",
    "Pilot Controls",
    "Hand/Foot Controls",
    "Hand Controls",
    "Joystick Controls",
    # Undercarriage
    "New Tracks",
    "Rubber Tracks",
    "Steel Tracks",
    "Over-the-Tire Tracks",
]

# Labels that describe machine features/options rather than physical work tools.
# Detected using the same patterns but rendered in a separate "Features" section.
FEATURE_LABELS: set[str] = {
    "2-Speed",
    "Enclosed Cab",
    "Cab",
    "Heat",
    "A/C",
    "Radio",
    "Backup Camera",
    "Ride Control",
    "Pilot Controls",
    "Hand/Foot Controls",
    "Hand Controls",
    "Joystick Controls",
    "High Flow",
    "Standard Flow",
    "Auxiliary Hydraulics",
}

# ── Keyword map ───────────────────────────────────────────────────────────────
# Ordered: specific phrases before generic ones.
# Each entry: (raw_pattern_string, normalized_label)

_RAW_PATTERNS = [
    # ── Work tools ────────────────────────────────────────────────────────────
    (r'\btooth\s*bucket\b',                                 "Tooth Bucket"),
    (r'\bsmooth\s*bucket\b',                                "Smooth Bucket"),
    (r'\bgrading\s*bucket\b',                               "Grading Bucket"),
    (r'\bbucket\b',                                         "Bucket"),
    # Forks: require "pallet", "fork attachment", or standalone "forks" (plural only)
    (r'\bpallet\s*forks?\b|\bfork\s*attachment\b|\bforks\b', "Pallet Forks"),
    (r'\bgrapple\b',                                        "Grapple"),
    (r'\bauger\b',                                          "Auger"),
    (r'\btrencher\b',                                       "Trencher"),
    (r'\bbroom\b',                                          "Broom"),
    (r'\bsnow\s*blade\b',                                   "Snow Blade"),
    (r'\bsnow\s*push(?:er)?\b',                             "Snow Pusher"),
    (r'\bmow(?:er)?\b',                                     "Mower"),
    (r'\bmulch(?:er)?\b',                                   "Mulcher"),
    (r'\bbrush\s*cut(?:ter)?\b',                            "Brush Cutter"),
    # TODO (post-demo): tighten hammer — consider requiring "hyd hammer" or
    # "hammer attachment" to avoid false positives like "hammer glass"
    (r'\bhyd(?:raulic)?\s*(?:breaker|hammer)\b'
     r'|\bbreaker\b|\bhammer\b',                            "Hydraulic Breaker"),
    (r'\bripper\b',                                         "Ripper"),
    (r'\bcompactor\b',                                      "Compactor"),
    (r'\bstump\s*grinder\b',                                "Stump Grinder"),

    # ── Hydraulic tools ───────────────────────────────────────────────────────
    (r'\bhyd(?:raulic)?\s*thumb\b',                         "Hydraulic Thumb"),
    (r'\bmanual\s*thumb\b',                                 "Manual Thumb"),
    (r'\bthumb\b',                                          "Thumb"),
    (r'\bhyd(?:raulic)?\s*coupler\b',                       "Hydraulic Coupler"),
    # Quick coupler: explicit phrases only
    (r'\bquick\s*coupler\b|(?<!\w)q/c(?!\w)|\bqc\b',       "Quick Coupler"),
    (r'\bpin\s*grab(?:ber)?\b',                             "Pin Grabber"),

    # ── Hydraulic / flow ──────────────────────────────────────────────────────
    (r'\baux(?:iliary)?\s*hyd(?:raulics?)?\b'
     r'|\bauxiliary\s*hydraulics?\b',                       "Auxiliary Hydraulics"),
    (r'\b(?:hi|high)[\s\-]*flow\b',                         "High Flow"),
    (r'\bstandard\s*flow\b|\bstd\s*flow\b',                 "Standard Flow"),
    (r'\b2\s*spd\b|\btwo\s*speed\b|\b2\s*speed\b',          "2-Speed"),

    # ── Cab / operator ────────────────────────────────────────────────────────
    (r'\benclosed\s*cab\b|\bcab\s*enclosed\b',              "Enclosed Cab"),
    (r'\bcab\b',                                            "Cab"),
    (r'\bheat(?:er)?\b',                                    "Heat"),
    # A/C: explicit variants only — bare "ac" excluded (too collision-prone)
    (r'\ba/c\b|\bair\s*con(?:d(?:itioning)?)?\b',           "A/C"),
    (r'\bradio\b',                                          "Radio"),
    (r'\bback(?:up)?\s*cam(?:era)?\b',                      "Backup Camera"),
    (r'\bride\s*control\b',                                 "Ride Control"),
    (r'\bpilot\s*controls?\b',                              "Pilot Controls"),
    (r'\bhand\s*/?\s*foot\s*controls?\b'
     r'|\bhand\s+foot\s+controls?\b',                       "Hand/Foot Controls"),
    (r'\bhand\s*controls?\b',                               "Hand Controls"),
    (r'\bjoystick\s*controls?\b|\biso\s*pattern\b|\bh\s*pattern\b', "Joystick Controls"),

    # ── Undercarriage ─────────────────────────────────────────────────────────
    (r'\bnew\s*tracks?\b',                                  "New Tracks"),
    (r'\brubber\s*tracks?\b',                               "Rubber Tracks"),
    (r'\bsteel\s*tracks?\b',                                "Steel Tracks"),
    (r'\bover\s*the\s*tire\s*tracks?\b|\bott\s*tracks?\b',  "Over-the-Tire Tracks"),
]

ATTACHMENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(pat, re.I), label)
    for pat, label in _RAW_PATTERNS
]

# Suppress a generic label when a more specific one is also present.
# "New Tracks" + "Rubber Tracks" intentionally NOT in this table —
# "new rubber tracks" should surface both labels.
_SPECIFICITY_RULES: dict[str, str] = {
    "Hydraulic Thumb":   "Thumb",
    "Manual Thumb":      "Thumb",
    "Hydraulic Coupler": "Quick Coupler",
    "Enclosed Cab":      "Cab",
    "Tooth Bucket":      "Bucket",
    "Smooth Bucket":     "Bucket",
    "Grading Bucket":    "Bucket",
}


def extract_attachments(text: str) -> dict:
    """
    Detect attachments, options, and features from raw equipment listing text.

    Returns a dict with two keys:
      "attachments" — physical work tools (bucket, forks, grapple, thumb, etc.)
      "features"    — machine options/cab features (2-speed, A/C, backup camera, etc.)

    Each list is deduplicated and priority-ordered.
    Example:
      {
        "attachments": ["Hydraulic Thumb", "Quick Coupler"],
        "features":    ["2-Speed", "Enclosed Cab", "A/C"],
      }
    """
    detected: set[str] = set()

    for pattern, label in ATTACHMENT_PATTERNS:
        if pattern.search(text):
            detected.add(label)

    # Specificity suppression
    to_suppress: set[str] = set()
    for child, parent in _SPECIFICITY_RULES.items():
        if child in detected and parent in detected:
            to_suppress.add(parent)

    detected -= to_suppress

    # Priority ordering then split
    ordered = [label for label in ATTACHMENT_PRIORITY if label in detected]
    ordered += sorted(detected - set(ATTACHMENT_PRIORITY))

    attachments = [lbl for lbl in ordered if lbl not in FEATURE_LABELS]
    features    = [lbl for lbl in ordered if lbl in FEATURE_LABELS]

    return {"attachments": attachments, "features": features}


# ── Tests ─────────────────────────────────────────────────────────────────────

_TESTS: list[tuple[str, dict]] = [
    (
        # 1. Classic excavator — hyd thumb, aux hyd, quick coupler, enclosed cab
        "2017 CAT 320 5200 hrs hyd thumb aux hyd quick coupler enclosed cab a/c heat",
        {"attachments": ["Hydraulic Thumb", "Quick Coupler"],
         "features":    ["Auxiliary Hydraulics", "Enclosed Cab", "Heat", "A/C"]},
    ),
    (
        # 2. Skid steer — high flow explicitly present
        "2019 Bobcat T590 1800 hrs high flow aux hyd pallet forks backup cam enclosed cab",
        {"attachments": ["Pallet Forks"],
         "features":    ["Auxiliary Hydraulics", "High Flow", "Enclosed Cab", "Backup Camera"]},
    ),
    (
        # 3. "hyd thumb" suppresses bare "Thumb"
        "cat 308 thumb hyd thumb bucket quick coupler",
        {"attachments": ["Bucket", "Hydraulic Thumb", "Quick Coupler"],
         "features":    []},
    ),
    (
        # 4. Enclosed cab suppresses bare "cab"; new tracks preserved
        "2015 deere 35g cab enclosed new tracks ride control",
        {"attachments": ["New Tracks"],
         "features":    ["Enclosed Cab", "Ride Control"]},
    ),
    (
        # 5. Messy Facebook post — no a/c marker present
        "kubota svl75 2spd rubber tracks hand controls radio heat 2200 hrs",
        {"attachments": ["Rubber Tracks"],
         "features":    ["2-Speed", "Heat", "Radio", "Hand Controls"]},
    ),
    (
        # 6. Grading bucket suppresses bare bucket; pilot controls
        "2018 takeuchi tl12 grading bucket aux hydraulics pilot controls",
        {"attachments": ["Grading Bucket"],
         "features":    ["Auxiliary Hydraulics", "Pilot Controls"]},
    ),
    (
        # 7. Snow attachments + new rubber tracks — both track labels returned
        "2020 ASV RT-75 snow blade snow pusher new rubber tracks enclosed cab",
        {"attachments": ["Snow Blade", "Snow Pusher", "Rubber Tracks"],
         "features":    ["Enclosed Cab"]},
    ),
    (
        # 8. Hydraulic hammer + pin grabber + steel tracks
        "2014 komatsu pc138 hyd hammer pin grabber 4100 hrs steel tracks",
        {"attachments": ["Hydraulic Breaker", "Pin Grabber", "Steel Tracks"],
         "features":    []},
    ),
    (
        # 9. OTT tracks + aux hyd + 2-speed + hand/foot controls
        "2016 cat 259d over the tire tracks aux hyd 2 speed hand foot controls",
        {"attachments": ["Over-the-Tire Tracks"],
         "features":    ["Auxiliary Hydraulics", "2-Speed", "Hand/Foot Controls"]},
    ),
    (
        # 10. Multiple work tools
        "JD 317G grapple auger trencher bucket aux hyd enclosed cab backup camera",
        {"attachments": ["Bucket", "Grapple", "Auger", "Trencher"],
         "features":    ["Auxiliary Hydraulics", "Enclosed Cab", "Backup Camera"]},
    ),
    (
        # 11. Manual thumb — does not also output generic "Thumb"
        "2013 volvo ec140 manual thumb std flow steel tracks cab heat",
        {"attachments": ["Manual Thumb", "Steel Tracks"],
         "features":    ["Standard Flow", "Cab", "Heat"]},
    ),
    (
        # 12. No attachments or features detected
        "2010 cat d6 dozer 8200 hrs runs good call for price",
        {"attachments": [], "features": []},
    ),
    (
        # 13. A/C variants — "air conditioning" normalises to A/C
        "2021 bobcat s76 air conditioning heat radio ride control pilot controls new tracks",
        {"attachments": ["New Tracks"],
         "features":    ["Heat", "A/C", "Radio", "Ride Control", "Pilot Controls"]},
    ),
    (
        # 14. Tooth bucket suppresses bare bucket; q/c variant for quick coupler
        "2020 JD 35G tooth bucket hyd thumb q/c aux hyd",
        {"attachments": ["Tooth Bucket", "Hydraulic Thumb", "Quick Coupler"],
         "features":    ["Auxiliary Hydraulics"]},
    ),
    (
        # 15. "forks" (plural, standalone) matches; bare "fork" does not
        "2017 jcb telehandler forks radio enclosed cab",
        {"attachments": ["Pallet Forks"],
         "features":    ["Enclosed Cab", "Radio"]},
    ),
    (
        # 16. bare "ac" in model-number context — must NOT fire A/C
        "2019 kubota kx040-4 ac series 1600 hrs rubber tracks",
        {"attachments": ["Rubber Tracks"], "features": []},
    ),
    (
        # 17. "air con" abbreviation fires A/C
        "2022 cat 299d3 air con heat enclosed cab high flow aux hyd new tracks",
        {"attachments": ["New Tracks"],
         "features":    ["Auxiliary Hydraulics", "High Flow", "Enclosed Cab", "Heat", "A/C"]},
    ),
]


def run_tests() -> None:
    passed = 0
    failed = 0
    for i, (text, expected) in enumerate(_TESTS, 1):
        result = extract_attachments(text)
        ok = result == expected
        if ok:
            passed += 1
        else:
            failed += 1
        preview = text[:65].replace('\n', ' ')
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] #{i:02d}  {preview}")
        if not ok:
            print(f"       expected attachments: {expected['attachments']}")
            print(f"       got     attachments: {result['attachments']}")
            print(f"       expected features:    {expected['features']}")
            print(f"       got     features:    {result['features']}")
    print(f"\n{passed}/{len(_TESTS)} passed")


if __name__ == "__main__":
    run_tests()