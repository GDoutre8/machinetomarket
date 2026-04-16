"""
mtm_registry_audit.py

Audits a registry JSON file for data quality issues.

Usage:
    python tools/mtm_registry_audit.py <registry.json>
"""

import json
import sys
import os


# --- Check functions ---

def check_derived_tipping(record):
    """
    DERIVED_TIPPING: Flag if tipping_load_lbs ≈ rated_operating_capacity_lbs * 2 (2% tolerance).
    This suggests the tipping load was derived rather than measured.
    """
    tipping = record.get("tipping_load_lbs")
    roc = record.get("rated_operating_capacity_lbs")
    if tipping is None or roc is None or roc == 0:
        return None
    expected = roc * 2
    tolerance = expected * 0.02
    if abs(tipping - expected) <= tolerance:
        return {
            "code": "DERIVED_TIPPING",
            "detail": f"tipping_load_lbs={tipping} ~= rated_operating_capacity_lbs * 2 ({expected})"
        }
    return None


def check_hp_net_gross_conflict(record):
    """
    HP_NET_GROSS_CONFLICT: Flag if both horsepower_hp and horsepower_gross_hp exist
    and their difference is less than 5.
    """
    net = record.get("horsepower_hp")
    gross = record.get("horsepower_gross_hp")
    if net is None or gross is None:
        return None
    diff = abs(net - gross)
    if diff < 5:
        return {
            "code": "HP_NET_GROSS_CONFLICT",
            "detail": f"horsepower_hp={net}, horsepower_gross_hp={gross}, diff={diff:.1f} (< 5)"
        }
    return None


def check_speed_conflict(record):
    """
    SPEED_CONFLICT: Flag if travel_speed_high_mph ≈ travel_speed_standard_mph.
    """
    high = record.get("travel_speed_high_mph")
    standard = record.get("travel_speed_standard_mph")
    if high is None or standard is None:
        return None
    if abs(high - standard) < 0.1:
        return {
            "code": "SPEED_CONFLICT",
            "detail": f"travel_speed_high_mph={high} ~= travel_speed_standard_mph={standard}"
        }
    return None


def check_missing_fields(record):
    """
    MISSING_FIELDS: Flag if any of the required fields are missing or null.
    """
    required = [
        "width_over_tires_in",
        "operating_weight_lbs",
        "bucket_hinge_pin_height_in",
    ]
    missing = [f for f in required if record.get(f) is None]
    if missing:
        return {
            "code": "MISSING_FIELDS",
            "detail": f"Missing or null: {', '.join(missing)}"
        }
    return None


def check_ratio_violation(record):
    """
    RATIO_VIOLATION: Flag if tipping_load_lbs / rated_operating_capacity_lbs
    is not between 1.8 and 2.3.
    """
    tipping = record.get("tipping_load_lbs")
    roc = record.get("rated_operating_capacity_lbs")
    if tipping is None or roc is None or roc == 0:
        return None
    ratio = tipping / roc
    if not (1.8 <= ratio <= 2.3):
        return {
            "code": "RATIO_VIOLATION",
            "detail": f"tipping/ROC ratio={ratio:.3f} (expected 1.8–2.3), tipping={tipping}, roc={roc}"
        }
    return None


# --- Audit runner ---

ALL_CHECKS = [
    check_derived_tipping,
    check_hp_net_gross_conflict,
    check_speed_conflict,
    check_missing_fields,
    check_ratio_violation,
]


def flatten_record(record):
    """
    Merge top-level fields with any nested 'specs' dict so checks work
    against both flat registries (list-of-dicts) and nested registries
    (dict with a 'specs' sub-key).
    """
    flat = dict(record)
    specs = record.get("specs")
    if isinstance(specs, dict):
        flat.update(specs)
    return flat


def audit_record(record):
    flat = flatten_record(record)
    flags = []
    for check in ALL_CHECKS:
        result = check(flat)
        if result:
            flags.append(result)
    return flags


def audit_registry(records):
    results = []
    for record in records:
        slug = record.get("model_slug") or record.get("slug") or record.get("id") or "(unknown)"
        flags = audit_record(record)
        if flags:
            results.append({
                "model_slug": slug,
                "flags": flags
            })
    return results


# --- Main ---

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/mtm_registry_audit.py <registry.json>")
        sys.exit(1)

    input_path = sys.argv[1]

    if not os.path.isfile(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8-sig") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON: {e}")
            sys.exit(1)

    if isinstance(data, dict):
        if "records" in data:
            records = data["records"]
        else:
            print("Error: Registry JSON is a dict but has no 'records' key.")
            sys.exit(1)
    elif isinstance(data, list):
        records = data
    else:
        print("Error: Registry JSON must be a list or a dict with a 'records' key.")
        sys.exit(1)

    results = audit_registry(records)
    data = records  # for len() count below
    total_flagged = len(results)

    print(f"\n=== MTM Registry Audit ===")
    print(f"Input:          {input_path}")
    print(f"Total records:  {len(data)}")
    print(f"Flagged models: {total_flagged}")
    print()

    preview = results[:20]
    if preview:
        print("--- Flagged models (first 20) ---")
        for entry in preview:
            print(f"\n  {entry['model_slug']}")
            for flag in entry["flags"]:
                print(f"    [{flag['code']}] {flag['detail']}")
    else:
        print("No issues found.")

    output_path = os.path.join(os.path.dirname(os.path.abspath(input_path)), "audit_report.json")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nFull report saved to: {output_path}")


if __name__ == "__main__":
    main()
