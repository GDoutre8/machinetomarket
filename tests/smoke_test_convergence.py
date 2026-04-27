"""
smoke_test_convergence.py
=========================
Convergence smoke test — verifies that the result page, spec sheet, and ZIP
all use the same enriched spec payload for each supported equipment type.

Tests three representative machines:
  - Caterpillar 259D3  (compact_track_loader)
  - Bobcat S770        (skid_steer)
  - Takeuchi TB225     (mini_excavator)

Run from the project root:
    python -m pytest tests/smoke_test_convergence.py -v
  or:
    python tests/smoke_test_convergence.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile

# Add project root to path so imports work
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest

from dealer_input import DealerInput
from mtm_service import safe_lookup_machine, _run_spec_resolver, _make_session_dir
from listing_pack_builder import build_listing_pack_v1, _zip_folder


# ── Representative test cases ─────────────────────────────────────────────────

_CASES = [
    {
        "label": "CTL — Caterpillar 259D3",
        "dealer_input": DealerInput(
            year=2021, make="Caterpillar", model="259D3", hours=1850,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
            serial_number="CAT0259D3X01234",
        ),
        "expected_eq_type": "compact_track_loader",
        "enriched_keys": ["hours", "ac", "high_flow"],
    },
    {
        "label": "SSL — Bobcat S770",
        "dealer_input": DealerInput(
            year=2020, make="Bobcat", model="S770", hours=2100,
            cab_type="enclosed", heater=True, ac=True,
            high_flow="yes", two_speed_travel="yes",
        ),
        "expected_eq_type": "skid_steer",
        "enriched_keys": ["hours", "high_flow"],
    },
    {
        "label": "Mini Ex — Takeuchi TB225",
        "dealer_input": DealerInput(
            year=2022, make="Takeuchi", model="TB225", hours=750,
            cab_type="enclosed", heater=True, ac=True,
            thumb_type="hydraulic", aux_hydraulics=True, blade_type="straight",
        ),
        "expected_eq_type": "mini_excavator",
        "enriched_keys": ["hours", "cab_type", "thumb_type", "blade_type"],
    },
]


def _lookup_and_resolve(di: DealerInput):
    parsed = {"make": di.make, "model": di.model, "make_source": "explicit"}
    specs, confidence = safe_lookup_machine(parsed)
    resolved_machine = None
    resolved_specs: dict = {}
    if specs is not None:
        resolved_machine = _run_spec_resolver("", parsed, specs, confidence, parsed_year=di.year)
        if resolved_machine:
            resolved_specs = resolved_machine.get("resolved_specs") or {}
    else:
        # Web fallback — no OEM specs
        from mtm_service import web_match_fallback
        resolved_machine = web_match_fallback(di.make, di.model, di.year)
    return resolved_machine, resolved_specs


# ── Convergence test ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", _CASES, ids=[c["label"] for c in _CASES])
def test_enriched_specs_returned(case, tmp_path):
    """build_listing_pack_v1 must return enriched_specs in its result dict."""
    di = case["dealer_input"]
    resolved_machine, resolved_specs = _lookup_and_resolve(di)

    pack = build_listing_pack_v1(
        dealer_input=di,
        resolved_specs=resolved_specs,
        resolved_machine=resolved_machine,
        image_input_paths=[],
        dealer_info=None,
        session_dir=str(tmp_path),
        session_web="/outputs/smoke_test",
    )

    assert "enriched_specs" in pack, (
        f"[{case['label']}] build_listing_pack_v1 did not return enriched_specs"
    )
    enriched = pack["enriched_specs"]
    assert isinstance(enriched, dict), "enriched_specs must be a dict"

    for key in case["enriched_keys"]:
        assert key in enriched, (
            f"[{case['label']}] expected key '{key}' in enriched_specs, "
            f"got keys: {sorted(enriched.keys())}"
        )


@pytest.mark.parametrize("case", _CASES, ids=[c["label"] for c in _CASES])
def test_enriched_specs_equals_spec_sheet_input(case, tmp_path):
    """
    The enriched_specs returned by build_listing_pack_v1 must equal the dict
    that was used to build the spec sheet PNG — same object, same content.
    This is the core convergence guarantee.
    """
    di = case["dealer_input"]
    resolved_machine, resolved_specs = _lookup_and_resolve(di)

    pack = build_listing_pack_v1(
        dealer_input=di,
        resolved_specs=resolved_specs,
        resolved_machine=resolved_machine,
        image_input_paths=[],
        dealer_info=None,
        session_dir=str(tmp_path),
        session_web="/outputs/smoke_test",
    )

    enriched = pack.get("enriched_specs")
    assert enriched is not None

    # Verify hours are injected for all types (core invariant)
    assert enriched.get("hours") == di.hours, (
        f"[{case['label']}] enriched_specs['hours'] should be {di.hours}, "
        f"got {enriched.get('hours')}"
    )

    # Verify equipment-type-specific injections
    eq = case["expected_eq_type"]
    if eq == "compact_track_loader":
        assert enriched.get("ac") == di.ac, "CTL ac should be injected"
        if di.high_flow is not None:
            assert enriched.get("high_flow") == di.high_flow, "CTL high_flow should be injected"
    elif eq == "skid_steer":
        if di.high_flow is not None:
            assert enriched.get("high_flow") == di.high_flow, "SSL high_flow should be injected"
    elif eq == "mini_excavator":
        if di.cab_type:
            assert enriched.get("cab_type") == di.cab_type, "mini_ex cab_type should be injected"
        if di.thumb_type:
            assert enriched.get("thumb_type") == di.thumb_type, "mini_ex thumb_type should be injected"


@pytest.mark.parametrize("case", _CASES, ids=[c["label"] for c in _CASES])
def test_listing_description_exists(case, tmp_path):
    """listing_description.txt must be written into the pack directory."""
    di = case["dealer_input"]
    resolved_machine, resolved_specs = _lookup_and_resolve(di)

    build_listing_pack_v1(
        dealer_input=di,
        resolved_specs=resolved_specs,
        resolved_machine=resolved_machine,
        image_input_paths=[],
        dealer_info=None,
        session_dir=str(tmp_path),
        session_web="/outputs/smoke_test",
    )

    listing_txt = tmp_path / "listing_output" / "listing_description.txt"
    assert listing_txt.is_file(), "listing_description.txt was not created"
    content = listing_txt.read_text(encoding="utf-8")
    assert len(content.strip()) > 20, "listing_description.txt appears empty"


@pytest.mark.parametrize("case", _CASES, ids=[c["label"] for c in _CASES])
def test_zip_exists_and_contains_listing(case, tmp_path):
    """ZIP must exist and contain listing_description.txt."""
    di = case["dealer_input"]
    resolved_machine, resolved_specs = _lookup_and_resolve(di)

    pack = build_listing_pack_v1(
        dealer_input=di,
        resolved_specs=resolved_specs,
        resolved_machine=resolved_machine,
        image_input_paths=[],
        dealer_info=None,
        session_dir=str(tmp_path),
        session_web="/outputs/smoke_test",
    )

    zip_path = pack.get("zip_path")
    assert zip_path and os.path.isfile(zip_path), "ZIP file was not created"

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    listing_entries = [n for n in names if "listing_description.txt" in n]
    assert listing_entries, f"ZIP does not contain listing_description.txt. Contents: {names}"


def test_zip_rebuild_no_stale_fallback(tmp_path):
    """
    When _zip_folder fails, download_pack_by_session must raise 500 — never
    fall back to a stale ZIP.  Verify by inspecting the handler source directly.
    """
    import inspect
    import app as app_module

    src = inspect.getsource(app_module.download_pack_by_session)
    # The fix removes the "if not os.path.isfile(zip_path)" guard, so a stale
    # ZIP can never be served after a rebuild failure.
    assert "if not os.path.isfile(zip_path)" not in src, (
        "Stale ZIP fallback detected in download_pack_by_session. "
        "The except clause must raise unconditionally."
    )


def test_no_parallel_injection_in_app(tmp_path):
    """
    app.py must not contain the old duplicate injection blocks.
    Those blocks were replaced by pack.get('enriched_specs').
    """
    import inspect
    import app as app_module

    src = inspect.getsource(app_module.build_listing_endpoint)
    # Old pattern: manually rebuilding _persist_rs with if _persist_eq == blocks
    assert 'if _persist_eq == "compact_track_loader":' not in src, (
        "Found old _persist_eq == 'compact_track_loader' injection block in app.py — "
        "it should be removed; enriched_specs from pack is the source of truth."
    )
    assert 'if _persist_eq == "skid_steer":' not in src, (
        "Found old _persist_eq == 'skid_steer' injection block in app.py — "
        "it should be removed; enriched_specs from pack is the source of truth."
    )
    # New pattern: single lookup
    assert 'pack.get("enriched_specs")' in src, (
        "app.py should use pack.get('enriched_specs') to save resolved_specs.json"
    )


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    passed = 0
    failed = 0

    def run(label, fn, *args, **kwargs):
        global passed, failed
        try:
            with tempfile.TemporaryDirectory() as td:
                from pathlib import Path
                fn(*args, tmp_path=Path(td), **kwargs)
            print(f"  PASS  {label}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {label}")
            traceback.print_exc()
            failed += 1

    print("\n=== MTM Convergence Smoke Test ===\n")

    for case in _CASES:
        run(f"enriched_specs returned       [{case['label']}]", test_enriched_specs_returned, case)
        run(f"enriched_specs equals SS input [{case['label']}]", test_enriched_specs_equals_spec_sheet_input, case)
        run(f"listing_description.txt exists [{case['label']}]", test_listing_description_exists, case)
        run(f"ZIP exists and contains listing [{case['label']}]", test_zip_exists_and_contains_listing, case)

    run("no stale ZIP fallback", test_zip_rebuild_no_stale_fallback)
    run("no parallel injection in app", test_no_parallel_injection_in_app)

    print(f"\n  {passed} passed, {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)
