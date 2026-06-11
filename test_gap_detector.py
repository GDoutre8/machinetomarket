"""Session 2 test harness for the Gap Detection Pipeline.

Run: python test_gap_detector.py
Prints session pass/fail metrics after the test cases.

Each test uses an isolated temporary SQLite database via
gap_detector.configure(); the production telemetry DB is never touched.
"""

import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

import gap_detector
from gap_detector import record_lookup, record_miss
from mtm_registry_lookup import lookup_machine


def _fresh_db(testcase) -> str:
    tmp = tempfile.mkdtemp(prefix="gap_test_")
    path = str(Path(tmp) / "gap_test.db")
    gap_detector.configure(path)
    testcase.addCleanup(gap_detector.configure, path + ".closed")
    return path


def _rows(db, table):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()


class TestGapDetector(unittest.TestCase):

    def test_1_twenty_synthetic_miss_events_all_logged(self):
        db = _fresh_db(self)
        ids = []
        for i in range(20):
            ids.append(record_miss(make="FakeCo", model=f"ZX{i}",
                                   category="compact_track_loader",
                                   session_id=f"s{i}", dealer_id=f"d{i % 4}"))
        self.assertTrue(all(ids), "every miss must return a lookup_event_id")
        events = _rows(db, "lookup_event")
        self.assertEqual(len(events), 20)
        self.assertTrue(all(e["match_tier"] == "miss" for e in events))
        gaps = _rows(db, "registry_gap")
        self.assertEqual(len(gaps), 20)  # 20 distinct models -> 20 gaps

    def test_2_duplicate_variants_collapse_into_one_gap(self):
        db = _fresh_db(self)
        variants = [
            ("Kubota", "SVL75-3"),
            ("kubota", "svl 75-3"),
            ("KUBOTA", "SVL753"),
            ("", "Kubota SVL75-3"),
            ("Kubota", "svl-75-3"),
        ]
        for i, (make, model) in enumerate(variants):
            record_miss(make=make, model=model, dealer_id=f"d{i}")
        gaps = _rows(db, "registry_gap")
        self.assertEqual(len(gaps), 1, f"expected 1 gap, got {len(gaps)}")
        gap = gaps[0]
        self.assertEqual(gap["normalized_make"], "kubota")
        self.assertEqual(gap["normalized_model"], "svl753")
        self.assertEqual(gap["miss_count_all_time"], 5)
        self.assertEqual(gap["miss_count_30d"], 5)
        self.assertEqual(gap["unique_dealer_count"], 5)
        self.assertGreaterEqual(len(json.loads(gap["raw_variants"])), 4)

    def test_3_p0_trigger_cases(self):
        # (a) 30 misses in 30d, one dealer -> P0 via miss_count_30d >= 30
        db = _fresh_db(self)
        for _ in range(30):
            record_miss(make="FakeCo", model="AAA1", dealer_id="d1")
        gap = _rows(db, "registry_gap")[0]
        self.assertEqual(gap["priority_tier"], "P0")
        self.assertEqual(gap["demand_score"], 30 * 3 + 30 * 1 + 1 * 5)

        # (b) 3 unique dealers, only 3 misses -> P0 via unique_dealer_count >= 3
        db = _fresh_db(self)
        for d in ("d1", "d2", "d3"):
            record_miss(make="FakeCo", model="BBB2", dealer_id=d)
        gap = _rows(db, "registry_gap")[0]
        self.assertEqual(gap["priority_tier"], "P0")

        # (c) must NOT fire: 29 misses / 2 dealers -> P1, not P0
        db = _fresh_db(self)
        for i in range(29):
            record_miss(make="FakeCo", model="CCC3", dealer_id=f"d{i % 2}")
        gap = _rows(db, "registry_gap")[0]
        self.assertEqual(gap["priority_tier"], "P1")

    def test_4_p1_p2_p3_tier_assignment(self):
        for count, expected in ((12, "P1"), (5, "P2"), (2, "P3")):
            db = _fresh_db(self)
            for _ in range(count):
                record_miss(make="FakeCo", model="TIER1", dealer_id="d1")
            gap = _rows(db, "registry_gap")[0]
            self.assertEqual(gap["priority_tier"], expected,
                             f"{count} misses should be {expected}")
        # pure-function boundary checks
        self.assertEqual(gap_detector.assign_priority_tier(29, 2), "P1")
        self.assertEqual(gap_detector.assign_priority_tier(10, 1), "P1")
        self.assertEqual(gap_detector.assign_priority_tier(9, 2), "P2")
        self.assertEqual(gap_detector.assign_priority_tier(3, 1), "P2")
        self.assertEqual(gap_detector.assign_priority_tier(2, 2), "P3")
        self.assertEqual(gap_detector.assign_priority_tier(0, 1), "P3")

    def test_5_telemetry_failure_does_not_break_lookup(self):
        # Point the detector at an impossible path: writes will raise inside
        # gap_detector, which must swallow them; lookup must return normally.
        gap_detector.configure(str(Path(tempfile.mkdtemp()) / "no" / "such" / "dir" / "x.db"))
        self.addCleanup(gap_detector.configure, str(Path(tempfile.mkdtemp()) / "y.db"))

        self.assertIsNone(record_miss(make="FakeCo", model="QQ9"))  # fail-open

        hit = lookup_machine("Kubota", "SVL75-2")
        self.assertTrue(hit.get("match"), "successful lookup broken by telemetry failure")
        miss = lookup_machine("FakeCo", "ZZZ999")
        self.assertFalse(miss.get("match"))
        self.assertIn("reason", miss)

    def test_6_successful_lookup_never_inserts_gap(self):
        db = _fresh_db(self)
        hit = lookup_machine("Kubota", "SVL75-2", session_id="s1", dealer_id="d1")
        self.assertTrue(hit.get("match"))
        ambiguous = lookup_machine(query="332G")  # known cross-registry collision
        self.assertEqual(_rows(db, "registry_gap"), [],
                         "matched/ambiguous lookups must never create gaps")
        events = _rows(db, "lookup_event")
        tiers = sorted(e["match_tier"] for e in events)
        self.assertNotIn("miss", tiers)
        self.assertEqual(len(events), 2)
        if not ambiguous.get("match"):
            self.assertIn("ambiguous", tiers)

    def test_7_every_lookup_attempt_gets_a_lookup_event(self):
        db = _fresh_db(self)
        calls = [
            dict(manufacturer="Kubota", model="SVL75-2"),        # hit
            dict(manufacturer="Bobcat", model="T770"),           # hit
            dict(manufacturer="FakeCo", model="ZZZ999"),         # miss
            dict(query="caterpillar 299d3"),                     # hit via query
            dict(query="totallyfake 000xx"),                     # miss via query
        ]
        for kwargs in calls:
            lookup_machine(**kwargs)
        events = _rows(db, "lookup_event")
        self.assertEqual(len(events), len(calls),
                         "exactly one lookup_event per public lookup call")
        misses = [e for e in events if e["match_tier"] == "miss"]
        self.assertEqual(len(misses), 2)
        gaps = _rows(db, "registry_gap")
        self.assertEqual(len(gaps), 2)


    # ── Codex audit patch tests ──────────────────────────────────────────

    def test_8_same_model_different_categories_separate_gaps(self):
        db = _fresh_db(self)
        record_miss(make="Acme", model="332G", category="skid_steer", dealer_id="d1")
        record_miss(make="Acme", model="332G", category="compact_track_loader", dealer_id="d1")
        record_miss(make="Acme", model="332g", category="compact_track_loader", dealer_id="d2")
        gaps = _rows(db, "registry_gap")
        self.assertEqual(len(gaps), 2, "different categories must be separate gaps")
        by_cat = {g["normalized_category"]: g for g in gaps}
        self.assertEqual(by_cat["skid_steer"]["miss_count_all_time"], 1)
        self.assertEqual(by_cat["compact_track_loader"]["miss_count_all_time"], 2)
        self.assertEqual(by_cat["compact_track_loader"]["unique_dealer_count"], 2)

    def test_9_anonymous_misses_count_zero_dealers(self):
        db = _fresh_db(self)
        record_miss(make="Acme", model="ANON1")
        record_miss(make="Acme", model="ANON1")
        gap = _rows(db, "registry_gap")[0]
        self.assertEqual(gap["unique_dealer_count"], 0,
                         "blank dealer_id must not count as a unique dealer")
        # demand_score gets no +5 dealer term: 2*3 + 2*1 + 0*5 = 8
        self.assertEqual(gap["demand_score"], 8.0)
        # one real dealer joins -> count 1, score adds exactly 5 (plus the new miss)
        record_miss(make="Acme", model="ANON1", dealer_id="d1")
        gap = _rows(db, "registry_gap")[0]
        self.assertEqual(gap["unique_dealer_count"], 1)
        self.assertEqual(gap["demand_score"], 3 * 3 + 3 * 1 + 1 * 5)

    def test_10_stub_and_candidate_matches_never_enter_registry_gap(self):
        db = _fresh_db(self)
        # Simulated matches for every non-production tier the lookup can return.
        for tier in ("coverage_stub", "coverage_only", "production_candidate"):
            record_lookup(
                make="Kubota", model=f"STUB-{tier}", category="compact_track_loader",
                result={"match": True, "match_method": "exact",
                        "full_record": {"model_slug": f"slug_{tier}",
                                        "registry_tier": tier}})
        # Real registry stub lookups through the live pipeline.
        import json as _json
        reg = _json.loads(
            (Path(__file__).parent / "registry" / "active"
             / "mtm_ctl_registry_v1_32.json").read_text(encoding="utf-8"))
        stub_hits = 0
        for rec in reg["records"]:
            if rec.get("registry_tier") != "coverage_stub":
                continue
            r = lookup_machine(rec["manufacturer"], rec["model"],
                               equipment_type="compact_track_loader")
            if r.get("match") and (r.get("full_record") or {}).get("registry_tier") == "coverage_stub":
                stub_hits += 1
            if stub_hits >= 3:
                break
        self.assertGreaterEqual(stub_hits, 1, "no stub record resolved; test inconclusive")
        self.assertEqual(_rows(db, "registry_gap"), [],
                         "stub/coverage_only/production_candidate matches must not create gaps")
        self.assertTrue(all(e["match_tier"] != "miss" for e in _rows(db, "lookup_event")))

    def test_11_invalid_input_logs_event_but_no_gap(self):
        db = _fresh_db(self)
        result = lookup_machine()
        self.assertFalse(result.get("match"))
        events = _rows(db, "lookup_event")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["match_tier"], "invalid_input")
        self.assertEqual(_rows(db, "registry_gap"), [])

    def test_12_gap_upsert_failure_preserves_lookup_event(self):
        db = _fresh_db(self)
        original = gap_detector._upsert_gap

        def boom(*args, **kwargs):
            raise RuntimeError("simulated gap upsert failure")

        gap_detector._upsert_gap = boom
        try:
            event_id = record_miss(make="Acme", model="CRASH1", dealer_id="d1")
        finally:
            gap_detector._upsert_gap = original
        self.assertIsNotNone(event_id, "event id must still be returned")
        events = _rows(db, "lookup_event")
        self.assertEqual(len(events), 1, "lookup_event must survive gap upsert failure")
        self.assertEqual(events[0]["match_tier"], "miss")
        self.assertEqual(_rows(db, "registry_gap"), [])

    def test_13_concurrent_duplicate_misses(self):
        import threading
        db = _fresh_db(self)
        threads = [
            threading.Thread(target=lambda i=i: [
                record_miss(make="Acme", model="RACE1", dealer_id=f"d{i}")
                for _ in range(5)])
            for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        events = _rows(db, "lookup_event")
        self.assertEqual(len(events), 40, "concurrent misses must not drop events")
        gaps = _rows(db, "registry_gap")
        self.assertEqual(len(gaps), 1, "atomic upsert must never duplicate a gap row")
        # One final sequential miss settles the recomputed counts deterministically.
        record_miss(make="Acme", model="RACE1", dealer_id="d0")
        gap = _rows(db, "registry_gap")[0]
        self.assertEqual(gap["miss_count_all_time"], 41)
        self.assertEqual(gap["unique_dealer_count"], 8)
        self.assertEqual(gap["priority_tier"], "P0")

    def test_14_sqlite_schema_matches_migration_intent(self):
        db = _fresh_db(self)
        record_miss(make="Acme", model="SCHEMA1")  # force schema creation
        conn = sqlite3.connect(db)
        try:
            gap_cols = {r[1] for r in conn.execute("PRAGMA table_info(registry_gap)")}
            self.assertIn("normalized_category", gap_cols)
            self.assertIn("miss_count_all_time", gap_cols)
            self.assertNotIn("miss_count", gap_cols)
            event_cols = {r[1] for r in conn.execute("PRAGMA table_info(lookup_event)")}
            self.assertIn("normalized_category", event_cols)
            # The triple unique constraint must reject duplicates.
            conn.execute(
                "INSERT INTO registry_gap (gap_id, normalized_make,"
                " normalized_model, normalized_category) VALUES ('x','a','b','c')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO registry_gap (gap_id, normalized_make,"
                    " normalized_model, normalized_category) VALUES ('y','a','b','c')")
            # ...but a different category is a distinct identity.
            conn.execute(
                "INSERT INTO registry_gap (gap_id, normalized_make,"
                " normalized_model, normalized_category) VALUES ('z','a','b','d')")
            # unique_dealer_count default is 0 (anonymous-safe), not 1.
            default = next(r for r in conn.execute("PRAGMA table_info(registry_gap)")
                           if r[1] == "unique_dealer_count")[4]
            self.assertEqual(str(default), "0")
        finally:
            conn.close()


def run_session_metrics():
    print("\n=== Gap Detection session metrics ===")
    import gap_detector as gd

    # Metric 1: 100% of synthetic misses produce a lookup_event row
    tmp = str(Path(tempfile.mkdtemp(prefix="gap_metrics_")) / "m.db")
    gd.configure(tmp)
    n = 20
    ok = sum(1 for i in range(n)
             if record_miss(make="FakeCo", model=f"MX{i}", dealer_id=f"d{i % 3}"))
    conn = sqlite3.connect(tmp)
    event_rows = conn.execute("SELECT COUNT(*) FROM lookup_event").fetchone()[0]
    conn.close()
    m1 = ok == n and event_rows == n
    print(f"synthetic misses -> lookup_event:  {event_rows}/{n} "
          f"[target 100%] {'PASS' if m1 else 'FAIL'}")

    # Metric 2: variant collapse
    tmp2 = str(Path(tempfile.mkdtemp(prefix="gap_metrics_")) / "m2.db")
    gd.configure(tmp2)
    for make, model in [("Kubota", "SVL75-3"), ("kubota", "svl 75-3"),
                        ("KUBOTA", "SVL753"), ("", "Kubota SVL75-3")]:
        record_miss(make=make, model=model)
    conn = sqlite3.connect(tmp2)
    gap_count = conn.execute("SELECT COUNT(*) FROM registry_gap").fetchone()[0]
    conn.close()
    m2 = gap_count == 1
    print(f"4 variants collapse to one gap:    {gap_count} row(s) "
          f"[target 1] {'PASS' if m2 else 'FAIL'}")

    # Metric 3: P0 fires correctly and not incorrectly
    m3 = (gd.assign_priority_tier(30, 1) == "P0"
          and gd.assign_priority_tier(1, 3) == "P0"
          and gd.assign_priority_tier(29, 2) == "P1"
          and gd.assign_priority_tier(9, 1) == "P2")
    print(f"P0 boundary behavior:              [fires at 30d>=30 or dealers>=3, "
          f"not below] {'PASS' if m3 else 'FAIL'}")

    # Metric 4: latency delta with instrumentation active vs disabled
    import mtm_registry_lookup as mrl
    tmp3 = str(Path(tempfile.mkdtemp(prefix="gap_metrics_")) / "m3.db")
    gd.configure(tmp3)
    cases = [("Kubota", "SVL75-2"), ("Bobcat", "T770"), ("FakeMake", "ZZZ999"),
             ("Caterpillar", "299D3"), ("Kubota", "NOPE-1")]
    lookup_machine(*cases[0])  # warm cache + db
    N = 40

    saved = mrl._gap_record_lookup
    mrl._gap_record_lookup = None
    t0 = time.perf_counter()
    for _ in range(N):
        for m, mo in cases:
            lookup_machine(m, mo)
    before = (time.perf_counter() - t0) * 1000 / (N * len(cases))
    mrl._gap_record_lookup = saved

    t0 = time.perf_counter()
    for _ in range(N):
        for m, mo in cases:
            lookup_machine(m, mo)
    after = (time.perf_counter() - t0) * 1000 / (N * len(cases))
    delta = after - before
    m4 = delta < 50
    print(f"lookup latency:                    {before:.2f} ms -> {after:.2f} ms "
          f"(delta {delta:+.2f} ms) [target <50ms] {'PASS' if m4 else 'FAIL'}")

    all_pass = all((m1, m2, m3, m4))
    print(f"\nALL SESSION METRICS: {'PASS' if all_pass else 'FAIL'}")
    return all_pass


if __name__ == "__main__":
    unittest.main(exit=False, verbosity=2)
    run_session_metrics()
