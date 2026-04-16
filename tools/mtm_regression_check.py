"""
MTM Tier A Regression Check
============================
Validates that all Tier A locked model fields match the lock file.

Usage:
    python tools/mtm_regression_check.py

Exit codes:
    0 = PASS — no regressions
    1 = FAIL — one or more regressions detected
"""

import json
import sys
import os

LOCK_FILE = os.path.join(os.path.dirname(__file__), "..", "registry", "locks", "mtm_tierA_lock_v1.json")

# Registry lookup config: maps equipment_type to (registry_path, record_match_fn)
REGISTRY_PATHS = {
    "compact_track_loader": "registry/active/mtm_ctl_registry_v1_19.json",
    "skid_steer_loader":    "registry/active/mtm_skid_steer_registry_v1_15.json",
    "mini_excavator":       "registry/active/mtm_mini_ex_registry_v2_1.json",
    "excavator":            "registry/mtm_excavator_registry_v2.json",
}

REGISTRY_ENCODING = {
    "registry/active/mtm_skid_steer_registry_v1_15.json": "utf-8",
}

# Maps model slug to (manufacturer, model) for registry lookup
SLUG_TO_RECORD = {
    "jd_333g":        ("John Deere", "333G"),
    "bobcat_t770":    ("Bobcat", "T770"),
    "jd_325g":        ("John Deere", "325G"),
    "cat_259d3":      ("Caterpillar", "259D3"),
    "cat_299d3":      ("Caterpillar", "299D3"),
    "bobcat_t66":     ("Bobcat", "T66"),
    "jd_317g":        ("John Deere", "317G"),
    "kubota_svl75":   ("Kubota", "SVL75"),
    "kubota_svl97_2": ("Kubota", "SVL97-2"),
    "cat_262d3":      ("Caterpillar", "262D3"),
    "cat_308_cr":     ("Caterpillar", "308"),
    "kubota_kx040_4": ("Kubota", "KX040-4"),
    "bobcat_e35":     ("Bobcat", "E35"),
    "jd_35g":         ("John Deere", "35G"),
    "cat_303_cr":     ("Caterpillar", "303 CR"),
}

VALID_LOCK_STATUSES = {"PENDING", "READY_FOR_LOCK", "LOCKED"}


def load_json(path, encoding=None):
    enc = encoding or REGISTRY_ENCODING.get(path, "utf-8")
    with open(path, encoding=enc) as f:
        return json.load(f)


def get_records(registry_data):
    if isinstance(registry_data, list):
        return registry_data
    return registry_data.get("records", [])


def find_record(records, display_name, registry_model_name=None):
    """Find a registry record by matching manufacturer + model against display_name."""
    search_name = (registry_model_name or display_name).lower().strip()

    # Strategy 1: exact match on "manufacturer model" concatenated
    for rec in records:
        mfr = rec.get("manufacturer", "").lower().strip()
        model = rec.get("model", "").lower().strip()
        full = f"{mfr} {model}"
        if full == search_name:
            return rec

    # Strategy 2: search_name starts with mfr and ends with model (handles multi-word mfr)
    for rec in records:
        mfr = rec.get("manufacturer", "").lower().strip()
        model = rec.get("model", "").lower().strip()
        if search_name.startswith(mfr) and search_name.endswith(model):
            return rec

    # Strategy 3: model exact match + manufacturer contained
    parts = search_name.split()
    for i in range(1, len(parts)):
        model_candidate = " ".join(parts[i:])
        mfr_candidate = " ".join(parts[:i])
        for rec in records:
            mfr = rec.get("manufacturer", "").lower().strip()
            model = rec.get("model", "").lower().strip()
            if mfr_candidate in mfr and model == model_candidate:
                return rec

    return None


def get_lock_status(locked_model):
    """
    Return the workflow status for a lock entry.

    `lock_status` is the source of truth. Legacy entries can still infer a
    safe state from the older boolean `locked` flag.
    """
    explicit = str(locked_model.get("lock_status", "")).strip().upper()
    if explicit:
        if explicit not in VALID_LOCK_STATUSES:
            raise ValueError(
                f"invalid lock_status={explicit!r}; expected one of "
                f"{sorted(VALID_LOCK_STATUSES)}"
            )
        return explicit

    if not locked_model.get("locked", True):
        return "PENDING"

    fields = locked_model.get("fields", {})
    if any(value is None for value in fields.values()):
        return "PENDING"
    return "LOCKED"


def validate_lock_entry(locked_model):
    """
    Enforce workflow-state invariants before live comparison.

    PENDING:
        Nulls allowed.
    READY_FOR_LOCK / LOCKED:
        Nulls are not allowed.
    """
    status = get_lock_status(locked_model)
    failures = []

    if status == "PENDING":
        return status, failures

    for field, value in locked_model.get("fields", {}).items():
        if value is None:
            failures.append((
                field,
                f"lock file value is null but lock_status={status}; fill all fields before promotion"
            ))

    return status, failures


def check_model(locked_model, registries):
    """
    Check a single locked model against its registry record.
    Returns list of (field, issue) tuples. Empty = clean.
    """
    display_name = locked_model.get("display_name") or locked_model.get("model", "unknown")
    equipment_type = locked_model["equipment_type"]
    registry_model_name = locked_model.get("registry_model_name")
    locked_fields = locked_model["fields"]
    failures = []

    # Load registry
    registry_path = REGISTRY_PATHS.get(equipment_type)
    if not registry_path:
        failures.append(("_registry", f"unknown equipment_type '{equipment_type}'"))
        return failures

    if registry_path not in registries:
        try:
            registries[registry_path] = load_json(registry_path)
        except FileNotFoundError:
            failures.append(("_registry", f"registry file not found: {registry_path}"))
            return failures

    records = get_records(registries[registry_path])
    slug = locked_model.get("model", "")
    if slug in SLUG_TO_RECORD:
        mfr, model_name = SLUG_TO_RECORD[slug]
        search = f"{mfr} {model_name}"
    else:
        search = display_name
    rec = find_record(records, search, registry_model_name)

    if rec is None:
        failures.append(("_record", f"model not found in registry ({registry_path})"))
        return failures

    specs = rec.get("specs", {})

    for field, locked_value in locked_fields.items():
        if locked_value is None:
            failures.append((field, "lock file value is null for LOCKED model"))
            continue

        # Check field existence
        if field not in specs:
            failures.append((field, "field missing from registry record"))
            continue

        live_value = specs[field]

        # Check for null regression (was a real value, now null)
        if live_value is None:
            failures.append((field, f"field is null (locked value was {locked_value})"))
            continue

        # Check value drift (numeric tolerance: exact match, since these are fixed spec values)
        if isinstance(locked_value, (int, float)) and isinstance(live_value, (int, float)):
            if abs(float(live_value) - float(locked_value)) > 0.001:
                failures.append((field, f"value changed: locked={locked_value}, current={live_value}"))
        else:
            if live_value != locked_value:
                failures.append((field, f"value changed: locked={locked_value!r}, current={live_value!r}"))

    # Check for duplicate/non-canonical field naming
    # If a locked field exists AND a known alias also exists with a different value, flag it
    # Note: horsepower_gross_hp intentionally excluded — gross vs net HP always differ by design.
    KNOWN_ALIASES = {
        "width_over_tires_in": ["width_over_tracks_in", "width_in"],
        "aux_flow_standard_gpm": ["aux_flow_primary_gpm", "aux_flow_gpm"],
    }
    for canonical, aliases in KNOWN_ALIASES.items():
        if canonical in locked_fields:
            for alias in aliases:
                if alias in specs and specs[alias] is not None:
                    canon_val = specs.get(canonical)
                    alias_val = specs[alias]
                    if canon_val is not None and alias_val is not None:
                        if abs(float(alias_val) - float(canon_val)) > 1.0:
                            failures.append((
                                canonical,
                                f"duplicate/conflicting alias '{alias}'={alias_val} vs canonical={canon_val}"
                            ))

    return failures


def run():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base_dir)

    # Load lock file
    try:
        lock = load_json(LOCK_FILE)
    except FileNotFoundError:
        print(f"ERROR: Lock file not found at {LOCK_FILE}")
        sys.exit(1)

    locked_models = lock.get("locked_models", [])
    registries = {}
    all_failures = []
    status_counts = {status: 0 for status in sorted(VALID_LOCK_STATUSES)}

    for locked_model in locked_models:
        status, preflight_failures = validate_lock_entry(locked_model)
        status_counts[status] += 1
        display_name = locked_model.get("display_name") or locked_model.get("model", "unknown")
        if preflight_failures:
            for field, issue in preflight_failures:
                all_failures.append((display_name, field, issue))
            continue

        if status != "LOCKED":
            continue

        failures = check_model(locked_model, registries)
        if failures:
            for field, issue in failures:
                all_failures.append((display_name, field, issue))

    if not all_failures:
        print(
            "PASS -- no regressions detected across LOCKED Tier A models "
            f"(PENDING={status_counts['PENDING']}, "
            f"READY_FOR_LOCK={status_counts['READY_FOR_LOCK']}, "
            f"LOCKED={status_counts['LOCKED']})"
        )
        sys.exit(0)
    else:
        print("FAIL -- Tier A regressions detected:\n")
        for model, field, issue in all_failures:
            print(f"  [{model}] field='{field}' => {issue}")
        print(f"\n{len(all_failures)} violation(s) found")
        sys.exit(1)


if __name__ == "__main__":
    run()
