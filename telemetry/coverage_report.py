"""
Registry coverage report.
Reads telemetry/lookup_events.jsonl and prints a summary.

Usage:
    python telemetry/coverage_report.py
    python telemetry/coverage_report.py --days 30
    python telemetry/coverage_report.py --days 0   # all time
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lookup_events.jsonl")

OUTCOMES = ["exact_match", "family_match", "web_match", "no_match"]
MISSING_OUTCOMES = {"no_match", "web_match"}


def _load_events(days: int) -> list:
    if not os.path.exists(_LOG_PATH):
        return []
    cutoff = None
    if days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = []
    with open(_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if cutoff:
                    ts = datetime.fromisoformat(ev["ts"].replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue
                events.append(ev)
            except Exception:
                continue
    return events


def _hit_rate(events: list, category: str) -> float:
    cat_events = [e for e in events if e.get("category") == category]
    if not cat_events:
        return 0.0
    hits = sum(1 for e in cat_events if e.get("outcome") not in MISSING_OUTCOMES)
    return hits / len(cat_events) * 100


def run_report(days: int = 7) -> None:
    events = _load_events(days)

    period_label = f"last {days} days" if days > 0 else "all time"
    print(f"\n=== MTM Registry Coverage Report ===")
    print(f"Period: {period_label}  |  Events: {len(events):,}")

    if not events:
        print("\nNo events found.")
        return

    # ── Outcome distribution ──────────────────────────────────────────────────
    outcome_counts = Counter(e.get("outcome") for e in events)
    total = len(events)
    print(f"\nOUTCOME DISTRIBUTION")
    for outcome in OUTCOMES:
        count = outcome_counts.get(outcome, 0)
        pct = count / total * 100 if total else 0
        print(f"  {outcome:<18} {count:>6,}   {pct:5.1f}%")

    # ── Coverage by category ──────────────────────────────────────────────────
    categories = sorted({e.get("category") for e in events if e.get("category")})
    if categories:
        print(f"\nCOVERAGE BY CATEGORY")
        for cat in categories:
            rate = _hit_rate(events, cat)
            cat_total = sum(1 for e in events if e.get("category") == cat)
            print(f"  {cat:<35} {rate:5.1f}%   ({cat_total:,} lookups)")

    # ── Top missing models ────────────────────────────────────────────────────
    missing = [e for e in events if e.get("outcome") in MISSING_OUTCOMES]
    if missing:
        tally = Counter(
            (e.get("make", "").strip(), e.get("model", "").strip(), e.get("category", "").strip())
            for e in missing
            if e.get("model", "").strip()
        )
        print(f"\nTOP MISSING MODELS  (no_match + web_match)")
        for i, ((make, model, cat), count) in enumerate(tally.most_common(20), 1):
            label = f"{make} {model}".strip() or "(unknown)"
            print(f"  {i:>2}.  {label:<35} {count:>4} hits   [{cat}]")
    else:
        print(f"\nTOP MISSING MODELS  — none in period")

    print()


def main():
    parser = argparse.ArgumentParser(description="MTM registry coverage report")
    parser.add_argument("--days", type=int, default=7, help="Window in days (0 = all time)")
    args = parser.parse_args()
    run_report(days=args.days)


if __name__ == "__main__":
    main()
