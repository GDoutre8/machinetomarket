"""Tests for comparable_engine using production-clean CTL records.

Run: python test_comparable_engine.py
Prints session pass/fail metrics after the test cases.
"""

import json
import time
import unittest
from pathlib import Path

from comparable_engine import (
    ALLOWED_TIERS,
    ComparableResult,
    find_comparables,
    load_default_pool,
)

CTL_PATH = Path(__file__).resolve().parent / "registry" / "active" / "mtm_ctl_registry_v1_32.json"


def _load_ctl():
    with open(CTL_PATH, encoding="utf-8") as f:
        return json.load(f)["records"]


CTL_RECORDS = _load_ctl()
BY_SLUG = {r.get("model_slug"): r for r in CTL_RECORDS}
PRODUCTION_CLEAN = [r for r in CTL_RECORDS if r.get("registry_tier") == "production_clean"]


def _assert_no_stub_comparables(testcase, result: ComparableResult):
    for comp in result.comparables:
        testcase.assertIn(comp.registry_tier, ALLOWED_TIERS,
                          f"{comp.model_slug} drawn from disallowed tier {comp.registry_tier}")


class TestComparableEngine(unittest.TestCase):

    def test_1_machine_with_clear_advantages(self):
        # TX1000W (ROC 1075) out-lifts every nearby Dingo — should lead with a win.
        record = BY_SLUG["toro_dingo_tx1000w"]
        result = find_comparables(record)
        self.assertEqual(len(result.comparables), 2)
        self.assertFalse(result.comparable_count_warning)
        _assert_no_stub_comparables(self, result)
        self.assertNotEqual(result.positioning_confidence, "LOW")
        lead = result.comparables[0]
        self.assertTrue(lead.delta_lines, "lead comparable produced no bullets")
        self.assertTrue(
            lead.delta_lines[0].startswith("+") or lead.delta_lines[0].startswith("similar"),
            f"expected win/similar lead bullet, got: {lead.delta_lines[0]}")
        wins = [d for c in result.comparables for d in c.deltas.values()
                if d["direction"] == "win"]
        self.assertTrue(wins, "expected at least one winning field")
        self.assertIn("Why consider this machine?", result.spec_sheet_block)

    def test_2_machine_trailing_on_all_fields(self):
        # TX413 is the smallest production-clean Dingo: trails on ROC, HP, and
        # operating weight against every comparable -> LOW confidence, lead
        # bullet is the smallest deficit.
        record = BY_SLUG["toro_dingo_tx413"]
        result = find_comparables(record)
        _assert_no_stub_comparables(self, result)
        self.assertEqual(result.positioning_confidence, "LOW")
        numeric = [d for c in result.comparables for d in c.deltas.values()
                   if d["direction"] in ("win", "similar")]
        self.assertEqual(numeric, [], "expected no wins or similars for TX413")
        lead = result.comparables[0]
        trail_pcts = sorted(abs(d["delta_pct"]) for d in lead.deltas.values()
                            if d["direction"] == "trail")
        lead_delta = next(d for d in lead.deltas.values()
                          if d["text"] == lead.delta_lines[0])
        self.assertAlmostEqual(abs(lead_delta["delta_pct"]), trail_pcts[0],
                               msg="lead bullet should surface the smallest deficit")

    def test_3_thin_category_fewer_than_two_comparables(self):
        # Restrict the pool so TXL2000 only has its T-variant available.
        record = BY_SLUG["toro_dingo_txl2000"]
        pool = [record, BY_SLUG["toro_dingo_txl2000t"]]
        result = find_comparables(record, pool=pool)
        self.assertEqual(len(result.comparables), 1)
        self.assertTrue(result.comparable_count_warning)
        self.assertEqual(result.comparables[0].model_slug, "toro_dingo_txl2000t")
        _assert_no_stub_comparables(self, result)

        # And a fully empty category: no comparables at all.
        result_empty = find_comparables(record, pool=[record])
        self.assertEqual(result_empty.comparables, [])
        self.assertTrue(result_empty.comparable_count_warning)
        self.assertEqual(result_empty.positioning_confidence, "LOW")
        self.assertEqual(result_empty.spec_sheet_block, "")

    def test_4_large_frame_ctl(self):
        # TXL2000 (ROC 2000 / 49.6 hp) — largest production-clean record.
        record = BY_SLUG["toro_dingo_txl2000"]
        result = find_comparables(record)
        self.assertEqual(len(result.comparables), 2)
        self.assertFalse(result.comparable_count_warning)
        _assert_no_stub_comparables(self, result)
        for comp in result.comparables:
            roc = comp.deltas["rated_operating_capacity_lbs"]
            self.assertIsNotNone(roc["comparable_value"])
            self.assertLessEqual(abs(roc["comparable_value"] - 2000) / 2000, 0.35)

    def test_5_small_frame_ctl(self):
        # TX413 (ROC 420) — smallest production-clean record; the strict HP
        # band finds nothing, so the relaxation ladder must still yield 2.
        record = BY_SLUG["toro_dingo_tx413"]
        result = find_comparables(record)
        self.assertEqual(len(result.comparables), 2)
        self.assertFalse(result.comparable_count_warning)
        _assert_no_stub_comparables(self, result)
        for comp in result.comparables:
            self.assertLessEqual(
                abs(comp.deltas["rated_operating_capacity_lbs"]["comparable_value"] - 420) / 420,
                0.35)


def run_session_metrics():
    print("\n=== Comparable Engine session metrics (CTL production_clean) ===")
    load_default_pool()  # warm the cache so timing reflects per-record cost

    exactly_two = 0
    stub_drawn = 0
    timings = []
    low_fired = None
    for record in PRODUCTION_CLEAN:
        start = time.perf_counter()
        result = find_comparables(record)
        timings.append((time.perf_counter() - start) * 1000)
        if len(result.comparables) == 2:
            exactly_two += 1
        for comp in result.comparables:
            if comp.registry_tier not in ALLOWED_TIERS:
                stub_drawn += 1
        if record["model_slug"] == "toro_dingo_tx413":
            low_fired = result.positioning_confidence == "LOW"

    n = len(PRODUCTION_CLEAN)
    pct_two = 100.0 * exactly_two / n
    print(f"records evaluated:                 {n}")
    print(f"exactly 2 comparables:             {exactly_two}/{n} ({pct_two:.1f}%)  "
          f"[target >=90%] {'PASS' if pct_two >= 90 else 'FAIL'}")
    print(f"comparables from disallowed tiers: {stub_drawn}  [target 0] "
          f"{'PASS' if stub_drawn == 0 else 'FAIL'}")
    print(f"generation time per record:        max {max(timings):.1f} ms, "
          f"avg {sum(timings)/len(timings):.1f} ms  [target <100ms] "
          f"{'PASS' if max(timings) < 100 else 'FAIL'}")
    print(f"positioning_confidence=LOW fires on all-trailing machine (TX413): "
          f"{'PASS' if low_fired else 'FAIL'}")

    sample = find_comparables(BY_SLUG["toro_dingo_tx1000w"])
    print("\n--- sample spec sheet block (TX1000W) ---")
    print(sample.spec_sheet_block)


if __name__ == "__main__":
    unittest.main(exit=False, verbosity=2)
    run_session_metrics()
