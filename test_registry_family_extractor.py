"""Session 3 test harness for the Family Relationship Graph.

Run: python test_registry_family_extractor.py
Builds the graph from the real active CTL + SSL registries (read-only),
verifies the locked extraction policy, the stable/variable rules, the
runtime hook, the gap-telemetry contract, and the Day 3 stop gate.
"""

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import registry_family_extractor as rfe
import registry_family_hook as hook
from registry_family_extractor import (
    ACTIVE_REGISTRIES, build_graph, compute_field_classes, load_registry,
    parse_model,
)
from registry_family_hook import find_best_family_match

_HERE = Path(__file__).resolve().parent
GRAPH_PATH = _HERE / "outputs" / "family_graph" / "ctl_ssl_family_graph.json"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _build_real_graph():
    """Build once from the active registries; verify they are untouched."""
    pre = {eq: _sha(p) for eq, p in ACTIVE_REGISTRIES.items()}
    records = {eq: load_registry(p) for eq, p in ACTIVE_REGISTRIES.items()}
    graph = build_graph(records, registry_checksums=pre)
    post = {eq: _sha(p) for eq, p in ACTIVE_REGISTRIES.items()}
    assert pre == post, "registry files must never be modified by the build"
    return graph


_GRAPH = _build_real_graph()


def _family_of(graph, mfr, eq, model_ident):
    """Return the family node containing the member with this identity."""
    for f in graph["families"]:
        if f["manufacturer"] != mfr or f["equipment_type"] != eq:
            continue
        for m in f["members"]:
            if m["model_ident"] == model_ident:
                return f
    return None


class TestGrammarsAndGrouping(unittest.TestCase):

    def test_kubota_svl75_family_grouped(self):
        f75 = _family_of(_GRAPH, "kubota", "compact_track_loader", "svl75")
        self.assertIsNotNone(f75)
        idents = {m["model_ident"] for m in f75["members"]}
        self.assertIn("svl752", idents)   # SVL75-2
        self.assertIn("svl753", idents)   # SVL75-3
        self.assertEqual(f75["family_root"], "svl75")
        # generations ordered 1 < 2 < 3
        gens = {m["model_ident"]: m["generation_ordinal"]
                for m in f75["members"]}
        self.assertEqual(gens["svl75"], 1)
        self.assertEqual(gens["svl752"], 2)
        self.assertEqual(gens["svl753"], 3)

    def test_cat_299d_generations_grouped(self):
        f = _family_of(_GRAPH, "caterpillar", "compact_track_loader", "299d")
        self.assertIsNotNone(f)
        idents = {m["model_ident"] for m in f["members"]}
        self.assertTrue({"299d", "299d2", "299d3"} <= idents)
        # XE / XHP / LAND MANAGEMENT records join as variants, not generations
        variants = {m["model_ident"]: m for m in f["members"]
                    if m["is_variant"]}
        self.assertIn("299d3xe", variants)
        self.assertIn("299d3xelandmanagement", variants)
        self.assertEqual(
            variants["299d3xe"]["generation_ordinal"],
            next(m["generation_ordinal"] for m in f["members"]
                 if m["model_ident"] == "299d3"))

    def test_bobcat_t650_and_t66_not_auto_grouped(self):
        # Grammar level: renumbered roots never collapse.
        p650 = parse_model("Bobcat", "T650")
        p66 = parse_model("Bobcat", "T66")
        self.assertEqual(p650.root, "t650")
        self.assertEqual(p66.root, "t66")
        self.assertNotEqual(p650.root, p66.root)
        # Build level (T66 is seed_only in the live registry, so prove the
        # rule with production-status records): two families, zero edges.
        recs = [
            {"manufacturer": "Bobcat", "model": "T650", "model_slug": "b_t650",
             "status": "current", "specs": {}},
            {"manufacturer": "Bobcat", "model": "T66", "model_slug": "b_t66",
             "status": "current", "specs": {}},
        ]
        g = build_graph({"compact_track_loader": recs})
        self.assertEqual(len(g["families"]), 2)
        self.assertEqual(g["relationships"], [],
                         "T650/T66 must not be linked automatically")
        # Live graph: T650 exists and its family contains no T66 member.
        f650 = _family_of(_GRAPH, "bobcat", "compact_track_loader", "t650")
        self.assertIsNotNone(f650)
        self.assertFalse(any(m["model_ident"] == "t66"
                             for m in f650["members"]))

    def test_cat_259d3_and_255_not_auto_grouped(self):
        f259 = _family_of(_GRAPH, "caterpillar", "compact_track_loader", "259d3")
        f255 = _family_of(_GRAPH, "caterpillar", "compact_track_loader", "255")
        self.assertIsNotNone(f259)
        self.assertIsNotNone(f255)
        self.assertNotEqual(f259["family_id"], f255["family_id"])
        self.assertEqual(f255["family_root"], "255")
        self.assertEqual(f259["family_root"], "259")

    def test_deere_323e_and_325g_not_auto_grouped(self):
        f323 = _family_of(_GRAPH, "john deere", "compact_track_loader", "323e")
        f325 = _family_of(_GRAPH, "john deere", "compact_track_loader", "325g")
        self.assertIsNotNone(f323)
        self.assertIsNotNone(f325)
        self.assertNotEqual(f323["family_id"], f325["family_id"])

    def test_deere_ptier_rename_joins_root(self):
        f = _family_of(_GRAPH, "john deere", "compact_track_loader", "333g")
        self.assertIsNotNone(f)
        idents = {m["model_ident"] for m in f["members"]}
        self.assertIn("333ptier", idents)
        self.assertIn("333d", idents)

    def test_no_automatic_cross_root_succession_edges(self):
        self.assertTrue(all(r["relation_type"] != "manual_successor"
                            for r in _GRAPH["relationships"]),
                        "no manual_successor edges may ship in Session 3")

    def test_gehl_mustang_not_cross_linked(self):
        # Identical model strings under Gehl and Mustang must produce two
        # distinct families — rebadge linking is forbidden.
        recs = [
            {"manufacturer": "Gehl", "model": "RT210", "model_slug": "gehl_rt210",
             "status": "current", "specs": {}},
            {"manufacturer": "Mustang", "model": "RT210", "model_slug": "mustang_rt210",
             "status": "current", "specs": {}},
        ]
        g = build_graph({"compact_track_loader": recs})
        fams = g["families"]
        self.assertEqual(len(fams), 2)
        mfrs = {f["manufacturer"] for f in fams}
        self.assertEqual(mfrs, {"gehl", "mustang"})
        self.assertEqual(g["relationships"], [])
        # real graph: no family ever spans manufacturers
        for f in _GRAPH["families"]:
            self.assertEqual(len({f["manufacturer"]}), 1)

    def test_model_family_marketing_string_cannot_merge_frames(self):
        # 259D / 279D / 299D all carry model_family='D Series' in the
        # registry; they must remain three distinct families.
        ids = set()
        for ident in ("259d", "279d", "299d"):
            f = _family_of(_GRAPH, "caterpillar", "compact_track_loader", ident)
            self.assertIsNotNone(f, ident)
            self.assertEqual(
                f["model_family_corroboration"]["identity_use"], "forbidden")
            ids.add(f["family_id"])
        self.assertEqual(len(ids), 3, "'D Series' must not merge frames")

    def test_equipment_type_is_hard_identity(self):
        # Deere 332 exists in SSL; 333G in CTL — never the same family, and
        # no family node mixes equipment types.
        types = {f["equipment_type"] for f in _GRAPH["families"]}
        self.assertEqual(types, {"compact_track_loader", "skid_steer"})


class TestAmbiguity(unittest.TestCase):

    def test_ambiguous_records_flagged_not_assigned(self):
        amb = _GRAPH["ambiguous_records"]
        self.assertGreater(len(amb), 0, "known ambiguous records exist")
        reasons = {a["model"]: a["reason"] for a in amb}
        self.assertIn("5240E P2", reasons)   # Gehl legacy unknown suffix
        member_slugs = {m["model_slug"] for f in _GRAPH["families"]
                        for m in f["members"]}
        for a in amb:
            self.assertNotIn(a["model_slug"], member_slugs,
                             f"ambiguous record assigned: {a}")

    def test_zero_silent_ambiguous_assignments(self):
        self.assertEqual(
            _GRAPH["metrics"]["totals"]["silent_ambiguous_assignments"], 0)

    def test_unknown_suffix_parses_ambiguous_not_guessed(self):
        p = parse_model("Caterpillar", "299D3 TURBO MAX")
        self.assertEqual(p.kind, "ambiguous")
        p = parse_model("Gehl", "5635SX II")
        self.assertEqual(p.kind, "ambiguous")


class TestStableVariableFields(unittest.TestCase):

    def _recs(self):
        return [
            {"model_slug": "a1", "model": "A1", "status": "current",
             "specs": {"lift_path": "radial", "horsepower_hp": 74.3,
                       "operating_weight_lbs": 9000, "fuel_capacity_gal": None,
                       "high_flow": True},
             "feature_flags": {"two_speed_available": True}},
            {"model_slug": "a2", "model": "A1-2", "status": "current",
             "specs": {"lift_path": "radial", "horsepower_hp": 74.3,
                       "operating_weight_lbs": 9300, "fuel_capacity_gal": 25.0,
                       "high_flow": True},
             "feature_flags": {"two_speed_available": True}},
        ]

    def test_stable_variable_and_indeterminate(self):
        stable, variable, indet = compute_field_classes(self._recs())
        self.assertEqual(stable["lift_path"], "radial")
        self.assertEqual(stable["horsepower_hp"], 74.3)
        self.assertIn("operating_weight_lbs", variable)
        v = variable["operating_weight_lbs"]
        self.assertEqual(v["min"], 9000)
        self.assertEqual(v["max"], 9300)
        self.assertEqual(v["member_values"], {"a1": 9000, "a2": 9300})
        self.assertIn("fuel_capacity_gal", indet)   # only one non-null vote

    def test_tristates_and_feature_flags_never_stable(self):
        stable, variable, _ = compute_field_classes(self._recs())
        for banned in ("high_flow", "two_speed", "high_flow_available",
                       "two_speed_available"):
            self.assertNotIn(banned, stable)
            self.assertNotIn(banned, variable)
        # and in the real graph
        for f in _GRAPH["families"]:
            for banned in ("high_flow", "two_speed", "high_flow_available",
                           "two_speed_available"):
                self.assertNotIn(banned, f["stable_fields"])

    def test_single_member_family_has_no_stable_fields(self):
        stable, variable, indet = compute_field_classes(self._recs()[:1])
        self.assertEqual(stable, {})
        self.assertEqual(variable, {})
        for f in _GRAPH["families"]:
            mainline_idents = {m["model_ident"] for m in f["members"]
                               if not m["is_variant"]}
            if len(mainline_idents) < 2:
                self.assertEqual(f["stable_fields"], {},
                                 f"{f['family_id']}: family with one unique "
                                 f"logical model must not expose stable fields")

    def test_real_graph_stable_fields_truly_stable(self):
        # Property check over the real registries: every stable value must
        # equal every mainline member's non-null registry value, and every
        # stable key must be on the conservative allowlist.
        recs = {}
        for eq, p in ACTIVE_REGISTRIES.items():
            for r in load_registry(p):
                slug = r.get("model_slug")
                if slug:
                    recs[slug] = r
        checked = 0
        for f in _GRAPH["families"]:
            mainline = [m for m in f["members"] if not m["is_variant"]]
            for fname, val in f["stable_fields"].items():
                self.assertIn(fname, rfe.FAMILY_STABLE_ALLOWED_FIELDS,
                              f"{f['family_id']}.{fname} not allowlisted")
                for m in mainline:
                    r = recs.get(m["model_slug"])
                    if r is None:
                        continue
                    actual = (r.get("specs") or {}).get(fname)
                    if actual is not None:
                        self.assertEqual(actual, val,
                                         f"{f['family_id']}.{fname}")
                        checked += 1
        self.assertGreater(checked, 0, "stable-field check must have teeth")


class TestP1AuditPatches(unittest.TestCase):
    """P1 audit: duplicate-row dedupe (Finding 1) and the option-dependent
    field allowlist (Finding 2)."""

    def _dup_recs(self):
        # Bobcat S510-style: three rows, same model, differing spec rows.
        return [
            {"manufacturer": "Bobcat", "model": "S510", "model_slug": "s510_a",
             "status": "current",
             "specs": {"lift_path": "radial", "horsepower_hp": 49.8,
                       "operating_weight_lbs": 6213}},
            {"manufacturer": "Bobcat", "model": "S510", "model_slug": "s510_b",
             "status": "current",
             "specs": {"lift_path": "radial", "horsepower_hp": 49.8,
                       "operating_weight_lbs": 6200}},
            {"manufacturer": "Bobcat", "model": "S510", "model_slug": "s510_c",
             "status": "active_used_market",
             "specs": {"lift_path": "radial", "horsepower_hp": 55.0,
                       "operating_weight_lbs": 6213}},
        ]

    def test_duplicate_rows_collapse_to_one_voter(self):
        voters, dups = rfe.dedupe_logical_models(self._dup_recs())
        self.assertEqual(len(voters), 1)
        self.assertEqual(dups, 2)
        self.assertEqual(voters[0]["model_slug"], "s510_a")  # first by slug

    def test_duplicate_only_family_has_empty_stable_fields(self):
        # One unique logical model => the single-member guard must hold even
        # though three rows agree on lift_path.
        stable, variable, indet = compute_field_classes(self._dup_recs())
        self.assertEqual(stable, {})
        self.assertEqual(variable, {})

    def test_duplicate_rows_preserved_as_member_refs_with_diagnostic(self):
        g = build_graph({"skid_steer": self._dup_recs()})
        self.assertEqual(len(g["families"]), 1)
        f = g["families"][0]
        self.assertEqual(len(f["members"]), 3)            # rows preserved
        self.assertEqual(f["unique_logical_models"], 1)
        self.assertEqual(f["duplicate_model_ident_count"], 2)
        self.assertEqual(f["stable_fields"], {})
        # and the metrics must count it as single-member
        self.assertEqual(g["metrics"]["totals"]["single_member_families"], 1)
        self.assertEqual(g["metrics"]["totals"]["multi_member_families"], 0)
        self.assertEqual(g["metrics"]["totals"]["duplicate_rows_collapsed"], 2)

    def test_real_graph_dup_families_not_multi_member(self):
        # Live S510/S550/S570/S590/S850 families: duplicate rows must not
        # produce stable fields or multi-member status.
        found = 0
        for root in ("s510", "s550", "s570", "s590", "s850"):
            for f in _GRAPH["families"]:
                if (f["manufacturer"] == "bobcat"
                        and f["equipment_type"] == "skid_steer"
                        and f["family_root"] == root):
                    found += 1
                    if f["unique_logical_models"] == 1:
                        self.assertEqual(f["stable_fields"], {}, root)
                        self.assertGreaterEqual(
                            f["duplicate_model_ident_count"],
                            len(f["members"]) - 1)
        self.assertGreaterEqual(found, 4, "expected live dup families")

    def _option_dep_recs(self):
        # Two DISTINCT models whose option-dependent values happen to agree.
        return [
            {"manufacturer": "Kubota", "model": "ZZ75", "model_slug": "zz75",
             "status": "current",
             "specs": {"lift_path": "radial", "aux_flow_high_gpm": 30.0,
                       "aux_flow_standard_gpm": 17.4,
                       "hydraulic_pressure_high_psi": 3500,
                       "hydraulic_pressure_standard_psi": 3000,
                       "travel_speed_high_mph": 7.1, "travel_speed_mph": 5.0,
                       "emissions_tier": "Tier 4 Final",
                       "standard_tire_size": "12x16.5"}},
            {"manufacturer": "Kubota", "model": "ZZ75-2", "model_slug": "zz752",
             "status": "current",
             "specs": {"lift_path": "radial", "aux_flow_high_gpm": 30.0,
                       "aux_flow_standard_gpm": 17.4,
                       "hydraulic_pressure_high_psi": 3500,
                       "hydraulic_pressure_standard_psi": 3000,
                       "travel_speed_high_mph": 7.1, "travel_speed_mph": 5.0,
                       "emissions_tier": "Tier 4 Final",
                       "standard_tire_size": "12x16.5"}},
        ]

    OPTION_FIELDS = ("aux_flow_high_gpm", "aux_flow_standard_gpm",
                     "hydraulic_pressure_high_psi",
                     "hydraulic_pressure_standard_psi",
                     "travel_speed_high_mph", "travel_speed_mph",
                     "emissions_tier")

    def test_option_dependent_fields_never_stable(self):
        stable, variable, indet = compute_field_classes(self._option_dep_recs())
        self.assertEqual(stable, {"lift_path": "radial"})
        for fname in self.OPTION_FIELDS:
            self.assertNotIn(fname, stable)
            self.assertNotIn(fname, variable)
            self.assertNotIn(fname, indet)

    def test_real_graph_stable_fields_allowlist_only(self):
        for f in _GRAPH["families"]:
            for fname in f["stable_fields"]:
                self.assertIn(fname, rfe.FAMILY_STABLE_ALLOWED_FIELDS,
                              f"{f['family_id']}.{fname}")
            for fname in self.OPTION_FIELDS + ("high_flow", "two_speed"):
                self.assertNotIn(fname, f["stable_fields"], f["family_id"])
                self.assertNotIn(fname, f["variable_fields"], f["family_id"])

    def test_hook_filters_stale_artifact_and_blocks_option_only_injection(self):
        # A stale/hand-edited graph whose stable_fields contain ONLY
        # option-dependent fields: the hook must filter them out and must
        # NOT mark the match safe_for_injection.
        stale = {
            "graph_version": "1.0",
            "families": [{
                "family_id": "kubota_compact_track_loader_svl75",
                "manufacturer": "kubota",
                "equipment_type": "compact_track_loader",
                "family_root": "svl75", "status": "confirmed",
                "display_name": "Kubota SVL75 family",
                "stable_fields": {"aux_flow_high_gpm": 30.0,
                                  "emissions_tier": "Tier 4 Final",
                                  "high_flow_available": True},
                "variable_fields": {"travel_speed_high_mph":
                                    {"min": 6.0, "max": 7.1}},
                "members": [
                    {"model_slug": "k1", "model": "SVL75", "model_ident": "svl75",
                     "generation_ordinal": 1, "generation_label": "",
                     "is_variant": False, "variant_suffixes": [],
                     "variant_of": None},
                    {"model_slug": "k2", "model": "SVL75-2",
                     "model_ident": "svl752", "generation_ordinal": 2,
                     "generation_label": "-2", "is_variant": False,
                     "variant_suffixes": [], "variant_of": None},
                ],
            }],
        }
        tmp = Path(tempfile.mkdtemp(prefix="fam_stale_")) / "stale_graph.json"
        tmp.write_text(json.dumps(stale), encoding="utf-8")
        hook.clear_cache()
        try:
            m = find_best_family_match("Kubota", "SVL75-3", "ctl",
                                       graph_path=tmp)
            self.assertEqual(m.match_basis, "family_root")
            self.assertEqual(m.stable_fields_available, {},
                             "option-dependent stable fields must be filtered")
            self.assertNotIn("travel_speed_high_mph",
                             m.variable_fields_blocked)
            self.assertFalse(m.safe_for_injection,
                             "option-dependent-only family must not be "
                             "injection-safe")
        finally:
            hook.clear_cache()


class TestRuntimeHook(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Real artifact must exist (built by the extractor run).
        if not GRAPH_PATH.exists():
            rfe.build_from_active()
        hook.clear_cache()

    def test_member_exact(self):
        m = find_best_family_match("Kubota", "SVL75-2", "ctl")
        self.assertEqual(m.match_basis, "member_exact")
        self.assertEqual(m.nearest_relatives[0]["score"], 100)

    def test_nearest_relative_scoring(self):
        # SVL90-3 does not exist; family svl90 = {SVL90 (g1), SVL90-2 (g2)}
        m = find_best_family_match("Kubota", "SVL90-3", "compact_track_loader")
        self.assertEqual(m.match_basis, "family_root")
        self.assertEqual(m.family_id, "kubota_compact_track_loader_svl90")
        scores = {r["model"]: r["score"] for r in m.nearest_relatives}
        self.assertEqual(scores["SVL90-2"], 75)    # 100 - 25*1
        self.assertEqual(scores["SVL90"], 50)      # 100 - 25*2, at threshold
        self.assertEqual(m.nearest_relatives[0]["model"], "SVL90-2")
        for r in m.nearest_relatives:
            self.assertGreaterEqual(r["score"], hook.MIN_ACCEPTABLE_SCORE)
        self.assertIn("not an exact match", m.ui_label)

    def test_hard_disqualifiers(self):
        # different manufacturer
        m = find_best_family_match("Bobcat", "SVL75-2", "ctl")
        self.assertEqual(m.match_basis, "none")
        # different equipment_type (SVL75 family is CTL-only)
        m = find_best_family_match("Kubota", "SVL75-2", "ssl")
        self.assertEqual(m.match_basis, "none")
        # ambiguous root
        m = find_best_family_match("Caterpillar", "299D3 TURBO MAX", "ctl")
        self.assertEqual(m.match_basis, "none")
        self.assertIn("ambiguous_root", m.ambiguity_flags)
        self.assertFalse(m.safe_for_injection)
        # no family
        m = find_best_family_match("Volvo", "MCT135D", "ctl")
        self.assertEqual(m.match_basis, "none")

    def test_t770_forestry_no_spec_inference(self):
        m = find_best_family_match("Bobcat", "T770 Forestry", "ctl")
        self.assertEqual(m.match_basis, "family_root")
        self.assertIn("query_variant_suffix", m.ambiguity_flags)
        self.assertFalse(m.safe_for_injection,
                         "variant query must not auto-inject")
        # T770 is a single-member family: no stable fields may surface
        self.assertEqual(m.stable_fields_available, {})
        for banned in ("high_flow", "two_speed"):
            self.assertNotIn(banned, m.stable_fields_available)

    def test_no_silent_exact_claims(self):
        # family_root basis must never present itself as member_exact
        m = find_best_family_match("Kubota", "SVL90-3", "ctl")
        self.assertNotEqual(m.match_basis, "member_exact")
        self.assertTrue(m.ui_label)

    def test_gap_telemetry_contract_no_writes(self):
        # The hook must perform zero telemetry writes: point gap_detector at
        # a fresh DB, run hook calls, DB must not even be created.
        import gap_detector
        tmp = str(Path(tempfile.mkdtemp(prefix="fam_hook_")) / "gap.db")
        gap_detector.configure(tmp)
        try:
            find_best_family_match("Kubota", "SVL90-3", "ctl")
            find_best_family_match("Caterpillar", "299D3 TURBO MAX", "ctl")
            self.assertFalse(Path(tmp).exists(),
                             "family hook must never touch gap telemetry")
            # and the miss path still works independently afterwards
            self.assertIsNotNone(gap_detector.record_miss(
                make="Kubota", model="SVL90-3", category="ctl"))
            conn = sqlite3.connect(tmp)
            n = conn.execute("SELECT COUNT(*) FROM lookup_event").fetchone()[0]
            conn.close()
            self.assertEqual(n, 1)
        finally:
            gap_detector.configure(tmp + ".closed")


class TestStopGate(unittest.TestCase):

    def test_ctl_assignment_rate(self):
        g = _GRAPH["metrics"]["stop_gate"]["compact_track_loader"]
        self.assertGreaterEqual(g["rate"], 0.80,
                                f"CTL assignment {g['rate']:.1%} below gate")

    def test_ssl_assignment_rate(self):
        g = _GRAPH["metrics"]["stop_gate"]["skid_steer"]
        self.assertGreaterEqual(g["rate"], 0.70,
                                f"SSL assignment {g['rate']:.1%} below gate")

    def test_overall_gate(self):
        self.assertEqual(_GRAPH["metrics"]["stop_gate"]["overall"], "PASS")

    def test_artifact_matches_live_build(self):
        if not GRAPH_PATH.exists():
            self.skipTest("artifact not yet written")
        artifact = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        self.assertEqual(artifact["metrics"]["stop_gate"]["overall"], "PASS")
        self.assertEqual(
            {f["family_id"] for f in artifact["families"]},
            {f["family_id"] for f in _GRAPH["families"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
