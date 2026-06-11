"""
Registry coverage telemetry.
Appends one JSONL event per lookup to telemetry/lookup_events.jsonl.
Fails silently — never raises, never breaks a lookup.
"""

import json
import os
from datetime import datetime, timezone

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lookup_events.jsonl")

VALID_OUTCOMES = frozenset({"exact_match", "family_match", "web_match", "no_match"})


def log_lookup(
    make: str,
    model: str,
    year,
    category: str,
    outcome: str,
    registry: str = None,
    alias_used: str = None,
) -> None:
    """Append one lookup event to the telemetry log. Silently swallows all errors."""
    try:
        event = {
            "ts":         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "make":       make or "",
            "model":      model or "",
            "year":       int(year) if year and str(year).isdigit() else None,
            "category":   category or "",
            "outcome":    outcome if outcome in VALID_OUTCOMES else "no_match",
            "registry":   registry or None,
            "alias_used": alias_used or None,
        }
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass
