# =============================================================================
# MTM Parser v1
# Status: Frozen
# Verified: 50/50 stress test pass
# Date: 2026-03-11
# =============================================================================
# MTM Parser Baseline — Frozen Demo Version
# Component: Model Alias Matcher
# Status: Frozen for demo integration
# Date: 2026-03-11

import re

# ══════════════════════════════════════════════════════════════════════════════
# MODEL ALIAS MATCHING
#
# Design:
#   - Each registry entry carries explicit alias strings (no generation magic)
#   - Aliases are stored in two forms: display string + normalized match key
#   - Matching runs on normalized input; winner is longest normalized alias
#   - Boundary check prevents alias matching inside longer tokens
#   - Return value uses the display alias, not the internal key
#   - Aliases must NOT over-promote a specific submodel from a generic mention
#
# To add a model: append a dict to MODEL_REGISTRY.
# To add variants: append to its "aliases" list.
# Nothing else changes.
#
# Identity rule: aliases must only match the exact model they name.
# Do NOT alias a generic family reference to a specific variant.
# Examples of what NOT to do:
#   "takeuchi tl12"  -> TL12R2   (wrong — TL12 != TL12R2)
#   "kx057"          -> KX057-5  (wrong — KX057 != KX057-5)
#   "svl95"          -> SVL95-2S (wrong — SVL95 != SVL95-2S)
#   "259d3"          -> 259D     (wrong — 259D3 is a newer variant)
# ══════════════════════════════════════════════════════════════════════════════


# ── Normalization ─────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """
    Prepare text for alias matching.

    Rules:
      - Lowercase
      - Collapse any run of non-alphanumeric characters to a single space
      - Strip edges

    Examples:
      "CAT 320 — Excavator"  ->  "cat 320 excavator"
      "kubota kx040-4"       ->  "kubota kx040 4"
      "kx0404"               ->  "kx0404"
      "JD310"                ->  "jd310"
    """
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def _a(display: str) -> tuple[str, str]:
    """Build an (display, normalized) alias pair."""
    return (display, normalize(display))


# ── Registry ──────────────────────────────────────────────────────────────────

MODEL_REGISTRY: list[dict] = [
    # ── Caterpillar ───────────────────────────────────────────────────────────
    {
        "manufacturer":   "Caterpillar",
        "model":          "320",
        "equipment_type": "Excavator",
        "aliases": [
            _a("caterpillar 320 excavator"),
            _a("cat 320 excavator"),
            _a("caterpillar 320"),
            _a("cat320"),
            _a("cat 320"),
            _a("320 cat"),
        ],
    },
    {
        "manufacturer":   "Caterpillar",
        "model":          "305",
        "equipment_type": "Mini Excavator",
        "aliases": [
            _a("caterpillar 305 mini excavator"),
            _a("cat 305 mini excavator"),
            _a("caterpillar 305 mini"),
            _a("cat 305 mini"),
            _a("caterpillar 305"),
            _a("cat305"),
            _a("cat 305"),
            _a("305 cat"),
        ],
    },
    {
        "manufacturer":   "Caterpillar",
        "model":          "259D",
        "equipment_type": "CTL",
        # 259D3 is a distinct newer model — do NOT alias it here.
        # A listing saying "259D3" should return no match rather than
        # be misidentified as a 259D.
        "aliases": [
            _a("caterpillar 259d"),
            _a("cat259d"),
            _a("cat 259d"),
            _a("259d cat"),
        ],
    },

    # ── Bobcat ────────────────────────────────────────────────────────────────
    {
        "manufacturer":   "Bobcat",
        "model":          "E35",
        "equipment_type": "Mini Excavator",
        "aliases": [
            _a("bobcat e35 mini excavator"),
            _a("bobcat e35i"),
            _a("bobcat e35"),
            _a("e35 bobcat"),
            _a("bobcate35"),
        ],
    },
    {
        "manufacturer":   "Bobcat",
        "model":          "E50",
        "equipment_type": "Mini Excavator",
        "aliases": [
            _a("bobcat e50 mini excavator"),
            _a("bobcat e50"),
            _a("e50 bobcat"),
            _a("bobcate50"),
        ],
    },
    {
        "manufacturer":   "Bobcat",
        "model":          "T770",
        "equipment_type": "CTL",
        "aliases": [
            _a("bobcat t770 ctl"),
            _a("bobcat t770"),
            _a("t770 bobcat"),
            _a("bobcatt770"),
        ],
    },
    {
        "manufacturer":   "Bobcat",
        "model":          "S650",
        "equipment_type": "Skid Steer",
        "aliases": [
            _a("bobcat s650 skid steer"),
            _a("bobcat s650"),
            _a("s650 bobcat"),
            _a("bobcats650"),
        ],
    },

    # ── Kubota ────────────────────────────────────────────────────────────────
    {
        "manufacturer":   "Kubota",
        "model":          "KX040-4",
        "equipment_type": "Mini Excavator",
        # kx040-4  -> normalizes to "kubota kx040 4"
        # kx0404   -> explicit alias for compact no-punctuation form
        "aliases": [
            _a("kubota kx040-4"),
            _a("kubota kx040 4"),
            _a("kx040 kubota"),
            _a("kubota kx0404"),
            _a("kx0404"),
            _a("kx040-4"),
        ],
    },
    {
        "manufacturer":   "Kubota",
        "model":          "KX057-5",
        "equipment_type": "Mini Excavator",
        # Only aliases that explicitly reference the -5 generation.
        # Generic "kx057" alone does not confirm KX057-5 identity.
        "aliases": [
            _a("kubota kx057-5"),
            _a("kubota kx057 5"),
            _a("kx057 5 kubota"),
            _a("kubota kx0575"),
            _a("kx0575"),
            _a("kx057-5"),
        ],
    },
    {
        "manufacturer":   "Kubota",
        "model":          "SVL95-2S",
        "equipment_type": "CTL",
        # Only aliases that explicitly reference -2S.
        # Generic "svl95" alone does not confirm SVL95-2S identity.
        "aliases": [
            _a("kubota svl95-2s"),
            _a("kubota svl95 2s"),
            _a("svl95 2s kubota"),
            _a("svl952s"),
            _a("svl95-2s"),
            _a("kubota svl952s"),
        ],
    },

    # ── John Deere ────────────────────────────────────────────────────────────
    # "310" alone is intentionally NOT an alias — too collision-prone.
    {
        "manufacturer":   "John Deere",
        "model":          "310",
        "equipment_type": "Backhoe",
        "aliases": [
            _a("john deere 310 backhoe"),
            _a("jd 310 backhoe"),
            _a("john deere 310"),
            _a("jd310"),
            _a("jd 310"),
            _a("deere 310"),
            _a("deere310"),
            _a("310 deere"),
        ],
    },
    {
        "manufacturer":   "John Deere",
        "model":          "35G",
        "equipment_type": "Mini Excavator",
        "aliases": [
            _a("john deere 35g mini excavator"),
            _a("john deere 35g mini"),
            _a("john deere 35g"),
            _a("jd35g"),
            _a("jd 35g"),
            _a("deere 35g"),
            _a("deere35g"),
            _a("35g deere"),
        ],
    },
    {
        "manufacturer":   "John Deere",
        "model":          "50G",
        "equipment_type": "Mini Excavator",
        "aliases": [
            _a("john deere 50g mini excavator"),
            _a("john deere 50g mini"),
            _a("john deere 50g"),
            _a("jd50g"),
            _a("jd 50g"),
            _a("deere 50g"),
            _a("deere50g"),
            _a("50g deere"),
        ],
    },

    # ── SkyTrak ───────────────────────────────────────────────────────────────
    {
        "manufacturer":   "SkyTrak",
        "model":          "8042",
        "equipment_type": "Telehandler",
        "aliases": [
            _a("skytrak 8042 telehandler"),
            _a("sky trak 8042"),
            _a("skytrak 8042"),
            _a("skytrak8042"),
            _a("8042 skytrak"),
        ],
    },

    # ── JLG ───────────────────────────────────────────────────────────────────
    {
        "manufacturer":   "JLG",
        "model":          "1055",
        "equipment_type": "Telehandler",
        "aliases": [
            _a("jlg 1055 telehandler"),
            _a("jlg 1055"),
            _a("jlg1055"),
            _a("1055 jlg"),
        ],
    },

    # ── Takeuchi ──────────────────────────────────────────────────────────────
    # TL12R2 is a specific model. Generic "tl12" or "tl12r" references
    # do NOT confirm TL12R2 identity — they are excluded.
    {
        "manufacturer":   "Takeuchi",
        "model":          "TL12R2",
        "equipment_type": "CTL",
        "aliases": [
            _a("takeuchi tl12r2"),
            _a("tl12r2 takeuchi"),
            _a("takeuchi tl12 r2"),
            _a("tl12 r2 takeuchi"),
            _a("tl12r2"),
            _a("tl12 r2"),
        ],
    },

    # ── Case ──────────────────────────────────────────────────────────────────
    # "580" alone excluded — too short and collision-prone.
    {
        "manufacturer":   "Case",
        "model":          "580",
        "equipment_type": "Backhoe",
        "aliases": [
            _a("case 580 super n"),
            _a("case 580 backhoe"),
            _a("case 580sn"),
            _a("case 580n"),
            _a("case 580"),
            _a("case580"),
            _a("580 case"),
        ],
    },
    {
        "manufacturer":   "Case",
        "model":          "TV370B",
        "equipment_type": "CTL",
        # TV370B is a distinct model from TV380 — do NOT conflate them.
        "aliases": [
            _a("case tv370b ctl"),
            _a("case tv370b"),
            _a("tv370b case"),
            _a("tv370b"),
            _a("casetv370b"),
        ],
    },

    # ── Komatsu ───────────────────────────────────────────────────────────────
    {
        "manufacturer":   "Komatsu",
        "model":          "PC200",
        "equipment_type": "Excavator",
        "aliases": [
            _a("komatsu pc200 excavator"),
            _a("komatsu pc200-8"),
            _a("komatsu pc200 8"),
            _a("komatsu pc200"),
            _a("pc200 komatsu"),
            _a("komatsupc200"),
            _a("pc200-8"),
        ],
    },
]


# ── Compiled lookup table ─────────────────────────────────────────────────────
# Built once at import time.
# Key: normalized alias string
# Value: (registry entry dict, display alias string, normalized alias length)
# On collision, longer normalized alias wins (more specific).

_ALIAS_INDEX: dict[str, tuple[dict, str, int]] = {}

for _entry in MODEL_REGISTRY:
    for _display, _norm_key in _entry["aliases"]:
        _length = len(_norm_key)
        if _norm_key not in _ALIAS_INDEX or _length > _ALIAS_INDEX[_norm_key][2]:
            _ALIAS_INDEX[_norm_key] = (_entry, _display, _length)


# ── Model-token → manufacturer index ─────────────────────────────────────────
# Used when a model token is detected in text but no make is present.
# Exact match only (model.upper() → manufacturer). Never fuzzy.
# Built once at import time from MODEL_REGISTRY.

_MODEL_TOKEN_INDEX: dict[str, tuple[str, str]] = {
    entry["model"].upper(): (entry["manufacturer"], entry["equipment_type"])
    for entry in MODEL_REGISTRY
}


def lookup_make_for_model(model: str) -> tuple[str | None, str | None]:
    """
    Given a detected model string, return (manufacturer, equipment_type) from
    the registry using exact model match only.

    Returns (None, None) if the model is not in the registry.
    Never performs fuzzy or partial matching.
    """
    return _MODEL_TOKEN_INDEX.get(model.upper(), (None, None))


def scan_bare_model_tokens(text: str) -> tuple[str | None, str | None, str | None]:
    """
    Scan raw listing text for bare known model tokens (e.g. 't770', 'kx040-4')
    when neither the make regex nor the alias matcher found a match.

    Uses the same word-boundary normalization as match_known_model.
    Returns (model, manufacturer, equipment_type) for the longest/best match,
    or (None, None, None) if nothing found.

    Exact match only — no fuzzy or partial matching.
    """
    norm_input = normalize(text)
    best_model: str | None = None
    best_mfr:   str | None = None
    best_eq:    str | None = None
    best_len: int = 0

    for model_upper, (mfr, eq_type) in _MODEL_TOKEN_INDEX.items():
        norm_model = normalize(model_upper)
        if len(norm_model) <= best_len:
            continue
        pattern = r'(?<![a-z0-9])' + re.escape(norm_model) + r'(?![a-z0-9])'
        if re.search(pattern, norm_input):
            best_model = model_upper
            best_mfr   = mfr
            best_eq    = eq_type
            best_len   = len(norm_model)

    return best_model, best_mfr, best_eq


# ── Matcher ───────────────────────────────────────────────────────────────────

def match_known_model(text: str) -> dict | None:
    """
    Identify a known equipment model from raw listing text.

    Returns the best match as a dict, or None if nothing matches.

    Match strategy:
      1. Normalize input.
      2. For every alias in the index, check whether its normalized form
         appears in the normalized input text with word boundaries on both
         sides (no partial-token matches).
      3. Among all hits, return the one with the longest normalized alias
         (most specific wins).

    Return shape:
      {
        "manufacturer":   "Caterpillar",
        "model":          "320",
        "equipment_type": "Excavator",
        "matched_alias":  "cat 320 excavator",   <- display form, not internal key
      }
    """
    norm_input = normalize(text)

    best_entry:   dict | None = None
    best_display: str         = ""
    best_length:  int         = 0

    for norm_key, (entry, display, length) in _ALIAS_INDEX.items():
        if length <= best_length:
            continue  # cannot beat current best; skip

        # Word-boundary pattern in normalized space.
        # In normalized text, token boundaries are spaces or string edges.
        pattern = r'(?<![a-z0-9])' + re.escape(norm_key) + r'(?![a-z0-9])'
        if re.search(pattern, norm_input):
            best_entry   = entry
            best_display = display
            best_length  = length

    if best_entry is None:
        return None

    return {
        "manufacturer":   best_entry["manufacturer"],
        "model":          best_entry["model"],
        "equipment_type": best_entry["equipment_type"],
        "matched_alias":  best_display,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

_TESTS: list[tuple[str, dict | None]] = [
    (
        # 1. Compact concatenated make+model
        "2017 cat320 5200 hrs hyd thumb enclosed cab 49k obo",
        {"manufacturer": "Caterpillar", "model": "320",
         "equipment_type": "Excavator", "matched_alias": "cat320"},
    ),
    (
        # 2. Spaced make + model + equipment type word
        "CAT 320 excavator clean machine low hours",
        {"manufacturer": "Caterpillar", "model": "320",
         "equipment_type": "Excavator", "matched_alias": "cat 320 excavator"},
    ),
    (
        # 3. Model before make (reversed order)
        "320 cat 2019 excellent condition",
        {"manufacturer": "Caterpillar", "model": "320",
         "equipment_type": "Excavator", "matched_alias": "320 cat"},
    ),
    (
        # 4. Full manufacturer name in text
        "Caterpillar 320 Excavator 2018 4100 hrs well maintained",
        {"manufacturer": "Caterpillar", "model": "320",
         "equipment_type": "Excavator", "matched_alias": "caterpillar 320 excavator"},
    ),
    (
        # 5. JD abbreviation compact, no spaces
        "jd310 backhoe 2015 4200 hrs runs great 4x4",
        {"manufacturer": "John Deere", "model": "310",
         "equipment_type": "Backhoe", "matched_alias": "jd310"},
    ),
    (
        # 6. Partial manufacturer name "deere"
        "deere 35g mini excavator 1800 hrs aux hyd thumb",
        {"manufacturer": "John Deere", "model": "35G",
         "equipment_type": "Mini Excavator", "matched_alias": "deere 35g"},
    ),
    (
        # 7. Bobcat reversed order
        "e35 bobcat mini 2020 900 hrs like new rubber tracks",
        {"manufacturer": "Bobcat", "model": "E35",
         "equipment_type": "Mini Excavator", "matched_alias": "e35 bobcat"},
    ),
    (
        # 8. Kubota KX040-4 with hyphen
        "2021 Kubota KX040-4 1200 hrs new tracks aux hyd $38,000",
        {"manufacturer": "Kubota", "model": "KX040-4",
         "equipment_type": "Mini Excavator", "matched_alias": "kubota kx040-4"},
    ),
    (
        # 9. Kubota compact no-punctuation form (kx0404)
        "kubota kx0404 mini excavator rubber tracks 2019",
        {"manufacturer": "Kubota", "model": "KX040-4",
         "equipment_type": "Mini Excavator", "matched_alias": "kubota kx0404"},
    ),
    (
        # 10. Kubota SVL95-2S — explicit -2S required; matched here
        "kubota svl95-2s ctl 2spd high flow enclosed cab 2200 hrs",
        {"manufacturer": "Kubota", "model": "SVL95-2S",
         "equipment_type": "CTL", "matched_alias": "kubota svl95-2s"},
    ),
    (
        # 11. Kubota SVL95 generic — must NOT match SVL95-2S
        "kubota svl95 ctl 2spd high flow enclosed cab 2200 hrs",
        None,
    ),
    (
        # 12. Bobcat T770 CTL full phrase
        "2019 Bobcat T770 CTL new tracks pilot controls $58,000",
        {"manufacturer": "Bobcat", "model": "T770",
         "equipment_type": "CTL", "matched_alias": "bobcat t770 ctl"},
    ),
    (
        # 13. Case with model variant suffix
        "case 580n backhoe 2016 4x4 extend-a-hoe 5800 hrs good shape",
        {"manufacturer": "Case", "model": "580",
         "equipment_type": "Backhoe", "matched_alias": "case 580n"},
    ),
    (
        # 14. Komatsu with dash variant (pc200-8)
        "2017 Komatsu PC200-8 excavator 7200 hrs $72,000 firm",
        {"manufacturer": "Komatsu", "model": "PC200",
         "equipment_type": "Excavator", "matched_alias": "komatsu pc200-8"},
    ),
    (
        # 15. JLG telehandler full phrase
        "JLG 1055 telehandler 2018 6000 hrs forks enclosed cab ready to work",
        {"manufacturer": "JLG", "model": "1055",
         "equipment_type": "Telehandler", "matched_alias": "jlg 1055 telehandler"},
    ),
    (
        # 16. Takeuchi TL12R2 explicit — must match
        "2020 Takeuchi TL12R2 CTL 900 hrs high flow aux hyd",
        {"manufacturer": "Takeuchi", "model": "TL12R2",
         "equipment_type": "CTL", "matched_alias": "takeuchi tl12r2"},
    ),
    (
        # 17. Takeuchi TL12 generic — must NOT match TL12R2
        "2018 takeuchi tl12 ctl 1800 hrs rubber tracks enclosed cab",
        None,
    ),
    (
        # 18. Caterpillar 259D exact — must match
        "2017 cat 259d ctl 2200 hrs new tracks high flow",
        {"manufacturer": "Caterpillar", "model": "259D",
         "equipment_type": "CTL", "matched_alias": "cat 259d"},
    ),
    (
        # 19. Caterpillar 259D3 — must NOT match 259D (different model)
        "2021 cat 259d3 ctl 800 hrs like new high flow",
        None,
    ),
    (
        # 20. Kubota KX057-5 explicit — must match
        "kubota kx057-5 mini 2019 1400 hrs clean machine",
        {"manufacturer": "Kubota", "model": "KX057-5",
         "equipment_type": "Mini Excavator", "matched_alias": "kubota kx057-5"},
    ),
    (
        # 21. Kubota KX057 generic — must NOT match KX057-5
        "kubota kx057 mini excavator 2018 2100 hrs rubber tracks",
        None,
    ),
    (
        # 22. Cat 305 mini — more specific alias beats bare "cat"
        "2016 cat 305 mini excavator 3200 hrs rubber tracks thumb",
        {"manufacturer": "Caterpillar", "model": "305",
         "equipment_type": "Mini Excavator", "matched_alias": "cat 305 mini excavator"},
    ),
    (
        # 23. SkyTrak telehandler full phrase
        "skytrak 8042 telehandler 2017 4800 hrs forks enclosed cab",
        {"manufacturer": "SkyTrak", "model": "8042",
         "equipment_type": "Telehandler", "matched_alias": "skytrak 8042 telehandler"},
    ),
    (
        # 24. No match — generic listing text, no known model tokens
        "used excavator for sale good condition call for price",
        None,
    ),
    (
        # 25. Collision guard — "310" alone must not match John Deere
        "2018 case 310 loader great shape 3100 hrs",
        None,
    ),
    (
        # 26. Collision guard — bare year and hours must not fire
        "2017 machine 5200 hrs runs good asking 49000",
        None,
    ),
    (
        # 27. Bobcat S650 compact concatenated
        "bobcats650 skid steer 2020 1100 hrs high flow new tracks",
        {"manufacturer": "Bobcat", "model": "S650",
         "equipment_type": "Skid Steer", "matched_alias": "bobcats650"},
    ),
    (
        # 28. Takeuchi TL12 R2 spaced — explicit R2 present, must match
        "takeuchi tl12 r2 ctl 2021 low hours",
        {"manufacturer": "Takeuchi", "model": "TL12R2",
         "equipment_type": "CTL", "matched_alias": "takeuchi tl12 r2"},
    ),
    (
        # 29. SVL95-2S bare alias without make name
        "svl95-2s ctl 2022 only 400 hrs like new",
        {"manufacturer": "Kubota", "model": "SVL95-2S",
         "equipment_type": "CTL", "matched_alias": "svl95-2s"},
    ),
]


def run_tests() -> None:
    passed = 0
    failed = 0
    for i, (text, expected) in enumerate(_TESTS, 1):
        result = match_known_model(text)
        ok = result == expected
        if ok:
            passed += 1
        else:
            failed += 1
        preview = text[:68].replace('\n', ' ')
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] #{i:02d}  {preview}")
        if not ok:
            print(f"       expected: {expected}")
            print(f"       got:      {result}")
    print(f"\n{passed}/{len(_TESTS)} passed")


if __name__ == "__main__":
    run_tests()


# ── Integration note ──────────────────────────────────────────────────────────
#
# In fix_listing_service() in mtm_service.py, call match_known_model()
# after safe_parse_listing() and before safe_lookup_machine().
# Alias match fills gaps only — it does not overwrite a confident regex parse.
#
#   parsed = safe_parse_listing(raw_text)
#
#   alias = match_known_model(raw_text)
#   if alias:
#       if not parsed.get("make"):
#           parsed["make"] = alias["manufacturer"]
#       if not parsed.get("model"):
#           parsed["model"] = alias["model"]
#       # equipment_type is not produced by the regex parser — always store it
#       parsed["equipment_type"] = alias["equipment_type"]
#
#   specs, confidence = safe_lookup_machine(parsed)
#   # ... rest of pipeline unchanged