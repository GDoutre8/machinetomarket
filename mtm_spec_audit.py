#!/usr/bin/env python3
"""
mtm_spec_audit.py
=================
Thin Full-Spec audit for MTM launch readiness.

Loads the three canonical registry JSON files (SSL, CTL, mini ex),
checks how many must-have and nice-to-have Full Spec fields each
machine has populated, and writes a ranked CSV of weak records.

Usage
-----
    python mtm_spec_audit.py                          # writes spec_audit.csv
    python mtm_spec_audit.py --threshold 7            # override weak threshold
    python mtm_spec_audit.py --output my_audit.csv    # custom output path
    python mtm_spec_audit.py --type ssl               # one equipment type only
    python mtm_spec_audit.py --type ssl --threshold 6 --output ssl_audit.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

# -- Registry file locations ---------------------------------------------------
_HERE = Path(__file__).parent

REGISTRY_FILES = {
    "skid_steer_loader":    _HERE / "registry" / "mtm_skid_steer_registry_v1_5.json",
    "compact_track_loader": _HERE / "registry" / "mtm_ctl_registry_v1_6.json",
    "mini_excavator":       _HERE / "registry" / "mtm_mini_ex_registry_v1.json",
}

# -- Statuses that indicate a stub / placeholder record — always skipped -------
SKIP_STATUSES = {"seed_only"}

# -- Field definitions — raw registry key names --------------------------------
# This audit uses raw registry keys intentionally, to stay independent of the
# service translation layer (mtm_service._SPEC_KEY_MAP).  The mapping below
# records the canonical display key each raw key translates to.
#
#   Registry key                     Canonical (display) key
#   -----------------------------    ----------------------
#   horsepower_hp               →    net_hp
#   rated_operating_capacity_lbs→    roc_lb
#   tipping_load_lbs            →    tipping_load_lb
#   operating_weight_lbs        →    operating_weight_lb   ← "lbs" intentional in registry
#   aux_flow_standard_gpm       →    hydraulic_flow_gpm
#   hydraulic_pressure_standard_psi  (same key, SSL/CTL)
#   hydraulic_pressure_psi           (different key, mini ex)

SSL_CTL_MUST_HAVE = [
    "horsepower_hp",                    # → net_hp
    "rated_operating_capacity_lbs",     # → roc_lb
    "tipping_load_lbs",                 # → tipping_load_lb
    "operating_weight_lbs",             # → operating_weight_lb  ← most-common gap
    "aux_flow_standard_gpm",            # → hydraulic_flow_gpm
    "hydraulic_pressure_standard_psi",
    "lift_path",
    "fuel_type",
]

SSL_CTL_NICE_TO_HAVE = [
    "travel_speed_high_mph",            # ← second-most-common gap
    "travel_speed_low_mph",
    "frame_size",
]

MINI_EX_MUST_HAVE = [
    "horsepower_hp",
    "operating_weight_lbs",
    "max_dig_depth_in",
    "max_reach_ground_in",
    "hydraulic_flow_gpm",
    "tail_swing_type",
]

MINI_EX_NICE_TO_HAVE = [
    "hydraulic_pressure_psi",           # mini ex uses different key than SSL/CTL
    "travel_speed_high_mph",
    "fuel_type",
]

# -- Per-type configuration ----------------------------------------------------
TYPE_CONFIG: dict[str, dict] = {
    "skid_steer_loader": {
        "must_have":    SSL_CTL_MUST_HAVE,
        "nice_to_have": SSL_CTL_NICE_TO_HAVE,
        "threshold":    8,   # full_spec_count below this = weak
    },
    "compact_track_loader": {
        "must_have":    SSL_CTL_MUST_HAVE,
        "nice_to_have": SSL_CTL_NICE_TO_HAVE,
        "threshold":    8,
    },
    "mini_excavator": {
        "must_have":    MINI_EX_MUST_HAVE,
        "nice_to_have": MINI_EX_NICE_TO_HAVE,
        "threshold":    6,
    },
}

# Friendly canonical name for terminal output (raw key → display key)
_CANONICAL = {
    "horsepower_hp":                   "net_hp",
    "rated_operating_capacity_lbs":    "roc_lb",
    "tipping_load_lbs":                "tipping_load_lb",
    "operating_weight_lbs":            "operating_weight_lb",
    "aux_flow_standard_gpm":           "hydraulic_flow_gpm",
    "hydraulic_pressure_standard_psi": "hydraulic_pressure_standard_psi",
    "hydraulic_pressure_psi":          "hydraulic_pressure_psi",
}

_RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# -- Core audit logic ----------------------------------------------------------

def _launch_risk(missing_must_count: int) -> str:
    if missing_must_count >= 4:
        return "CRITICAL"
    if missing_must_count >= 2:
        return "HIGH"
    if missing_must_count == 1:
        return "MEDIUM"
    return "LOW"


def audit_record(record: dict, eq_type: str) -> dict:
    cfg          = TYPE_CONFIG[eq_type]
    must_have    = cfg["must_have"]
    nice_to_have = cfg["nice_to_have"]
    threshold    = cfg["threshold"]
    specs        = record.get("specs") or {}

    must_populated  = [f for f in must_have    if specs.get(f) is not None]
    nice_populated  = [f for f in nice_to_have if specs.get(f) is not None]
    must_missing    = [f for f in must_have    if specs.get(f) is None]
    nice_missing    = [f for f in nice_to_have if specs.get(f) is None]

    full_spec_count = len(must_populated) + len(nice_populated)
    ys  = record.get("years_supported") or {}

    return {
        "manufacturer":       record.get("manufacturer", ""),
        "model":              record.get("model", ""),
        "equipment_type":     eq_type,
        "years":              f"{ys.get('start', '?')}–{ys.get('end', '?')}",
        "status":             record.get("status", ""),
        "full_spec_count":    full_spec_count,
        "must_have_count":    len(must_populated),
        "must_have_total":    len(must_have),
        "nice_to_have_count": len(nice_populated),
        "nice_to_have_total": len(nice_to_have),
        "is_weak":            "YES" if full_spec_count < threshold else "no",
        "launch_risk":        _launch_risk(len(must_missing)),
        "missing_must":       ", ".join(must_missing)  or "none",
        "missing_nice":       ", ".join(nice_missing)  or "none",
    }


# -- Runner --------------------------------------------------------------------

def run_audit(
    types: list[str] | None = None,
    threshold_override: int | None = None,
    output_path: Path | None = None,
) -> None:

    if types is None:
        types = list(REGISTRY_FILES.keys())

    if output_path is None:
        output_path = _HERE / "spec_audit.csv"

    if threshold_override is not None:
        for cfg in TYPE_CONFIG.values():
            cfg["threshold"] = threshold_override

    all_rows: list[dict] = []
    missing_freq: dict[str, int] = {}

    print("-- Loading registries -----------------------------------------")
    for eq_type in types:
        path = REGISTRY_FILES.get(eq_type)
        if not path or not path.exists():
            print(f"  [SKIP] File not found: {path}")
            continue

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        records: list[dict] = data.get("records", [])
        kept = skipped = 0

        for record in records:
            if record.get("status") in SKIP_STATUSES:
                skipped += 1
                continue
            row = audit_record(record, eq_type)
            all_rows.append(row)
            kept += 1

            for field in row["missing_must"].split(", "):
                if field and field not in ("—", "none"):
                    missing_freq[field] = missing_freq.get(field, 0) + 1
            for field in row["missing_nice"].split(", "):
                if field and field not in ("—", "none"):
                    missing_freq[field] = missing_freq.get(field, 0) + 1

        print(f"  {eq_type:25}  {kept:3d} records  ({skipped} seed_only skipped)")

    if not all_rows:
        print("No records loaded — nothing to audit.")
        return

    # Sort: highest risk first, then most gaps, then alpha
    all_rows.sort(key=lambda r: (
        _RISK_ORDER.get(r["launch_risk"], 4),
        -(r["must_have_total"] - r["must_have_count"]),
        r["manufacturer"],
        r["model"],
    ))

    # -- Write CSV -------------------------------------------------------------
    columns = [
        "manufacturer", "model", "equipment_type", "years", "status",
        "full_spec_count", "must_have_count", "must_have_total",
        "nice_to_have_count", "nice_to_have_total",
        "is_weak", "launch_risk",
        "missing_must", "missing_nice",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_rows)

    # -- Summary ---------------------------------------------------------------
    total    = len(all_rows)
    weak     = sum(1 for r in all_rows if r["is_weak"] == "YES")
    critical = sum(1 for r in all_rows if r["launch_risk"] == "CRITICAL")
    high     = sum(1 for r in all_rows if r["launch_risk"] == "HIGH")
    medium   = sum(1 for r in all_rows if r["launch_risk"] == "MEDIUM")
    low      = sum(1 for r in all_rows if r["launch_risk"] == "LOW")

    print(f"\n-- Audit Summary ----------------------------------------------")
    print(f"  Records audited  : {total}")
    print(f"  Weak (< threshold): {weak}  ({100*weak//total}%)")
    print(f"  CRITICAL         : {critical}")
    print(f"  HIGH             : {high}")
    print(f"  MEDIUM           : {medium}")
    print(f"  LOW (launch-ready): {low}  ({100*low//total}%)")
    print(f"  CSV written      : {output_path}")

    print(f"\n-- Missing Field Frequency — patch these first ----------------")
    print(f"  {'Count':>5}  {'% of records':>13}  {'Registry key':<40}  Canonical")
    print(f"  {'-'*5}  {'-'*13}  {'-'*40}  {'-'*20}")
    for field, count in sorted(missing_freq.items(), key=lambda x: -x[1]):
        pct       = 100 * count // total
        canonical = _CANONICAL.get(field, field)
        print(f"  {count:5d}  {pct:12d}%  {field:<40}  {canonical}")

    print(f"\n-- Top 20 Weakest Records -------------------------------------")
    print(f"  {'Risk':8}  {'Make':12}  {'Model':14}  {'Specs':5}  Missing must-haves")
    print(f"  {'-'*8}  {'-'*12}  {'-'*14}  {'-'*5}  {'-'*40}")
    for row in all_rows[:20]:
        print(
            f"  {row['launch_risk']:8}  "
            f"{row['manufacturer']:12}  "
            f"{row['model']:14}  "
            f"{row['full_spec_count']:5d}  "
            f"{row['missing_must']}"
        )

    # -- Per-type breakdown ----------------------------------------------------
    print(f"\n-- Per-Type Breakdown -----------------------------------------")
    for eq_type in types:
        rows = [r for r in all_rows if r["equipment_type"] == eq_type]
        if not rows:
            continue
        type_weak  = sum(1 for r in rows if r["is_weak"] == "YES")
        avg_count  = sum(r["full_spec_count"] for r in rows) / len(rows)
        threshold  = TYPE_CONFIG[eq_type]["threshold"]
        must_total = TYPE_CONFIG[eq_type]["must_have"].__len__()
        nice_total = TYPE_CONFIG[eq_type]["nice_to_have"].__len__()
        print(
            f"  {eq_type:25}  {len(rows):3d} records  "
            f"avg {avg_count:.1f}/{must_total + nice_total} specs  "
            f"weak: {type_weak}  threshold: {threshold}"
        )


# -- CLI -----------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MTM Thin Full-Spec Audit — flags launch-risky registry records"
    )
    parser.add_argument(
        "--type", choices=["ssl", "ctl", "mini", "all"], default="all",
        help="Equipment type to audit (default: all)"
    )
    parser.add_argument(
        "--threshold", type=int, default=None,
        help="Override weak-record threshold for all types"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output CSV path (default: <project>/spec_audit.csv)"
    )
    args = parser.parse_args()

    _TYPE_MAP = {
        "ssl":  ["skid_steer_loader"],
        "ctl":  ["compact_track_loader"],
        "mini": ["mini_excavator"],
        "all":  None,
    }
    run_audit(
        types            = _TYPE_MAP[args.type],
        threshold_override = args.threshold,
        output_path      = Path(args.output) if args.output else None,
    )
