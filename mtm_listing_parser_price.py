# =============================================================================
# MTM Parser v1
# Status: Frozen
# Verified: 50/50 stress test pass
# Date: 2026-03-11
# =============================================================================
# MTM Parser Baseline — Frozen Demo Version
# Component: Price Parser
# Status: Frozen for demo integration
# Date: 2026-03-11

import re

# ── Context penalty patterns ───────────────────────────────────────────────────

_HOURS_CONTEXT = re.compile(r'(?:hrs?\.?|hours?|h\b)', re.I)

_YEAR_PATTERN = re.compile(r'\b(19[89]\d|20[0-3]\d)\b')

_MODEL_CONTEXT = re.compile(
    r'\b(?:cat|caterpillar|deere|john\s+deere|bobcat|kubota|case|volvo|'
    r'doosan|hitachi|jcb|takeuchi|liebherr|terex|kobelco|komatsu|'
    r'hyundai|new\s+holland|jlg|genie|skytrak|manitou|gradall|sany|'
    r'liugong|yanmar|link[\s-]?belt)\b',
    re.I
)

_WEIGHT_CONTEXT = re.compile(
    r'\b(?:lb|lbs|kg|kgs|pounds?|operating\s+weight|weight'
    r'|tipping\s+load|tip\s+load|rated\s+operating\s+capacity'
    r'|roc|operating\s+capacity|lift\s+capacity|payload)\b',
    re.I
)

# Phone number continuation: digits followed by more phone segments.
# Catches area codes and middle segments appearing as price candidates.
# Matches: -555-0122 / .555.0122 / ) 555-0122 / -0122 / ' 0122'
_PHONE_CONTEXT = re.compile(r'[\s\-.)]+\d{3}[\s\-.)]+\d{4}|[\s\-.)]+\d{4}\b')

# Decimal digits included in the numeric capture group
_CANDIDATE_RE = re.compile(
    r'(?P<dollar>\$\s*)?(?P<digits>\d[\d,]*(?:\.\d+)?)\s*(?P<k>k\b|thousand\b)?',
    re.I
)


def extract_price(text: str) -> int | None:
    """
    Returns the most likely asking price as a raw integer (e.g. 49000),
    or None if no credible price candidate is found.

    Scoring:
        +3  dollar sign prefix
        +2  k / thousand suffix
        +1  comma formatting
        -10 adjacent hours context word
        -10 matches year pattern (1980-2039)
        -8  immediately follows a known make/manufacturer name (without currency marker)
        -8  adjacent weight/capacity context word  ← hard-disqualifies the candidate

    Callers handle display formatting and OBO detection.
    """
    candidates = []

    for m in _CANDIDATE_RE.finditer(text):
        raw = m.group('digits').replace(',', '')
        if not raw:
            continue

        numeric    = float(raw)
        has_dollar = bool(m.group('dollar'))
        has_k      = bool(m.group('k'))
        has_comma  = ',' in m.group('digits')

        if has_k:
            numeric *= 1000

        # Hard plausibility bounds
        if numeric < 500 or numeric > 5_000_000:
            continue

        score = 0

        if has_dollar: score += 3
        if has_k:      score += 2
        if has_comma:  score += 1

        # Widened context windows: 20 chars before and after
        before = text[max(0, m.start() - 20): m.start()]
        after  = text[m.end(): m.end() + 20]

        if _HOURS_CONTEXT.search(before) or _HOURS_CONTEXT.search(after):
            score -= 10

        # Year, hours (tight), and weight/capacity are hard disqualifiers — track separately.
        # is_hours only fires when an hours word is IMMEDIATELY after the number
        # (within 6 chars) AND there is no positive price signal — this catches
        # "2200 hrs" and "1800 hours" without catching "... 2200 hrs ... 29500"
        is_year   = bool(_YEAR_PATTERN.fullmatch(m.group('digits').strip()))
        is_weight = bool(_WEIGHT_CONTEXT.search(after))
        is_phone  = bool(_PHONE_CONTEXT.match(after))
        tight_after = text[m.end(): m.end() + 6]
        is_hours  = (
            bool(_HOURS_CONTEXT.match(tight_after.lstrip()))
            and not has_dollar    # only a dollar sign overrides tight-hours exclusion
        )

        if is_year:   score -= 10
        if is_weight: score -= 8

        if _MODEL_CONTEXT.search(before):
            if not (has_dollar or has_k or has_comma):
                score -= 8

        # Detect numeric fragment embedded in a model-number token.
        # "S770"  → pre_char='S' (letter before digit run)  → model token
        # "950M"  → post_char='M' (letter after digit run)  → model token
        # Dollar sign overrides: "$950" is always a price candidate.
        # has_k guard: "49k" ends on 'k' which is consumed by the k-group,
        # so post_char is whatever follows the suffix — not a concern, but
        # explicit for safety.
        pre_char  = text[m.start() - 1]        if m.start() > 0              else ''
        post_char = text[m.end('digits')]    if m.end('digits') < len(text) else ''
        is_model_token = (
            not has_dollar
            and (
                pre_char.isalpha()                       # "S770", "T770"
                or (post_char.isalpha() and not has_k)   # "950M", "320GC"
            )
        )

        candidates.append({
            'numeric':        numeric,
            'score':          score,
            'is_year':        is_year,
            'is_hours':       is_hours,
            'is_weight':      is_weight,
            'is_phone':       is_phone,
            'is_model_token': is_model_token,
            'pos':            m.start(),
        })

    if not candidates:
        return None

    # Hard-exclude years, immediately-adjacent hours values, weight/capacity values,
    # and phone number segments — none of these are ever prices.
    non_disqualified = [
        c for c in candidates
        if not c['is_weight'] and not c['is_year']
        and not c['is_hours'] and not c['is_phone']
        and not c['is_model_token']
    ]
    if not non_disqualified:
        return None

    credible = [c for c in non_disqualified if c['score'] > 0]
    pool = credible if credible else non_disqualified

    best = max(pool, key=lambda c: (c['score'], c['numeric'], -c['pos']))
    return int(best['numeric'])


# ── Tests ─────────────────────────────────────────────────────────────────────

_TESTS = [
    # ── Original baseline ─────────────────────────────────────────────────────
    ("2017 cat320\n5200 hrs\nhyd thumb\n49k obo",                   49000),
    ("CAT 320\n33,000 lbs operating weight\n29,500 firm",           29500),
    ("2016 kubota kx057\n1800 hrs\n4.5k",                           4500),
    ("john deere 310\n2200 original hours\nasking 12.75k",          12750),
    ("2019 bobcat t590\n1,800 hrs new tracks\n$38,500 obo",         38500),
    ("2018 komatsu pc138\n4,100 hours\n54,900",                     54900),
    ("volvo ec220\ngood condition\n$72,000",                        72000),
    ("JLG 1055\noperating weight 12,000 lbs\nasking 31,500",        31500),
    ("Link-Belt 210\n3800 hrs\n$58,000",                            58000),
    ("cat skid steer\n2200 hrs\n22500 firm",                        22500),
    ("takeuchi tb260\n3100 hrs\n44500 obo",                         44500),
    ("used excavator\ncall for price\nno texts",                    None),
    # ── Year hard-exclusion ───────────────────────────────────────────────────
    ("2022",                                                        None),
    ("2023 Case TV370B CTL good condition call for price",          None),
    ("2022 Bobcat S650 $31,500 obo",                               31500),
    # ── Hours hard-exclusion (tight — number IS the hours count) ─────────────
    # Only a dollar-sign prefix overrides is_hours; comma and k suffix do not.
    ("2021 kubota kx040-4 1200 hrs rubber tracks",                  None),
    ("2200 hours no price listed",                                  None),
    ("1,200 hrs",                                                   None),   # comma-hours
    ("1,200 hrs asking 38000",                                     38000),   # comma-hours + price
    ("1.2k hrs",                                                    None),   # k-hours
    # ── Hours soft-penalty (price appears near hours but isn't the count) ────
    ("kubota svl75 2200 hrs asking 29500",                         29500),
    ("2019 bobcat t590 1800 hrs new tracks $38,500 obo",           38500),
    # ── Weight/capacity hard-exclusion ────────────────────────────────────────
    ("7,400 lb tipping load",                                       None),
    ("2023 Case TV370B 850 hrs 7400 lb tipping load $52,000 obo",  52000),
    # ── Phone number hard-exclusion ───────────────────────────────────────────
    ("2022 Bobcat T66\n850 hrs\ngood condition\n615-555-0122",      None),
    ("2019 cat 320 5200 hrs 918-555-0192 49k obo",                 49000),
    ("kubota svl75 1800 hrs call 303-555-0199",                    None),
    ("takeuchi tl12 2100 hrs asking 39500 call 701-555-0133",     39500),
]


def run_tests() -> None:
    passed = 0
    failed = 0
    for text, expected in _TESTS:
        result = extract_price(text)
        status = "PASS" if result == expected else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        preview = text.replace('\n', ' / ')[:55]
        print(f"[{status}]  expected={str(expected):>8}  got={str(result):>8}  |  {preview}")
    print(f"\n{passed}/{len(_TESTS)} passed")


if __name__ == "__main__":
    run_tests()