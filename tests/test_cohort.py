from copy import deepcopy
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import unittest

from sharpeval import rank_cohort, validate
from sharpeval.cohort import holm_adjust
from sharpeval.cohort_fixtures import make_cohort_fixture
from sharpeval.cohort_report import render_cohort_html
from sharpeval.validation import InputError

ROOT = Path(__file__).resolve().parents[1]


def indexed(report):
    return {a["agent_id"]: a for a in report["agents"]}


def scores(report):
    return {a["agent_id"]: (a["score"], a["rank"], a["evidence_qualified"]) for a in report["agents"]}


class HolmTests(unittest.TestCase):
    def test_hand_calculated_running_max_and_cap(self):
        actual = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.2})
        for key, expected in {"a": 0.04, "b": 0.09, "c": 0.09, "d": 0.2}.items():
            self.assertAlmostEqual(actual[key], expected)
        self.assertEqual(holm_adjust({"a": 0.8, "b": 0.9}), {"a": 1, "b": 1})

    def test_ties_permutation_and_failed_family_slots(self):
        values = {"a": 0.01, "b": 0.01, "missing": 1, "failed": 1}
        self.assertEqual(holm_adjust(values), holm_adjust(dict(reversed(list(values.items())))))
        self.assertEqual(holm_adjust(values)["a"], 0.04)
        self.assertEqual(holm_adjust(values)["b"], 0.04)
        self.assertEqual(holm_adjust({"a": 0.01, "b": 0.01})["a"], 0.02)

    def test_invalid_probabilities(self):
        for values in ({}, {"a": -0.1}, {"a": 1.1}, {"a": float("nan")}, {"a": True}):
            with self.subTest(values=values), self.assertRaises(InputError):
                holm_adjust(values)


class CohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = make_cohort_fixture()
        cls.report = rank_cohort(cls.fixture)

    def setUp(self):
        self.d = deepcopy(self.fixture)

    def strong(self):
        return indexed(rank_cohort(self.d))["strong-edge"]

    def primary(self):
        return next(r for r in self.d["runs"] if r["run_id"] == "strong-edge-primary")

    def test_public_api_and_no_mutation(self):
        before = deepcopy(self.d)
        self.assertEqual(len(validate(self.d)["runs"]), 12)
        self.assertEqual(rank_cohort(self.d), self.report)
        self.assertEqual(before, self.d)
        self.assertEqual(self.report["family_size"], 6)
        self.assertEqual(self.report["coverage"]["planned_runs"], 12)

    def test_raw_tail_and_holm_match_independent_oracle(self):
        values = [r["return"] - r["cost"] for r in self.primary()["observations"]]
        mu = statistics.mean(values)
        sr = mu / statistics.stdev(values)
        centered = [x - mu for x in values]
        m2 = statistics.mean(x*x for x in centered)
        skew = statistics.mean(x**3 for x in centered) / m2**1.5
        kurt = statistics.mean(x**4 for x in centered) / m2**2
        z = (sr - 0.05) * math.sqrt(251) / math.sqrt(1 - skew*sr + (kurt-1)*sr*sr/4)
        p = math.erfc(z / math.sqrt(2))/2
        a = self.strong()
        self.assertAlmostEqual(a["raw_p"], p, places=15)
        self.assertAlmostEqual(a["holm_adjusted_p"], 6*p, places=15)
        self.assertAlmostEqual(a["score"], 100*(1-6*p))
        self.assertAlmostEqual(a["sharpe_gap_to_hurdle"], sr-0.05)
        self.assertEqual(a["moments"]["observations"], 252)

    def test_permutation_invariance(self):
        self.d["runs"].reverse()
        self.d["agents"].reverse()
        self.assertEqual(scores(rank_cohort(self.d)), scores(self.report))
        self.assertEqual(rank_cohort(self.d)["design_sha256"], self.report["design_sha256"])

    def test_equal_scores_share_statistical_rank(self):
        primary = deepcopy(self.primary()["observations"])
        for r in self.d["runs"]:
            r["observations"] = deepcopy(primary)
        report = rank_cohort(self.d)
        self.assertEqual({a["rank"] for a in report["agents"]}, {1})
        self.assertEqual(len({a["score"] for a in report["agents"]}), 1)
        self.assertEqual([a["agent_id"] for a in report["agents"]], sorted(a["agent_id"] for a in report["agents"]))

    def test_failed_and_omitted_primary_retain_family_slots(self):
        for run in self.d["runs"]:
            if run["run_id"] == "modest-edge-primary":
                run.update(status="failed", reason="Execution timed out.", observations=None)
        self.d["runs"] = [r for r in self.d["runs"] if r["run_id"] != "boundary-a-primary"]
        report = rank_cohort(self.d)
        agents = indexed(report)
        self.assertEqual(report["family_size"], 6)
        self.assertEqual(report["coverage"]["failed_runs"], 1)
        self.assertEqual(report["coverage"]["missing_runs"], 1)
        self.assertEqual(report["coverage"]["planned_runs"], 12)
        for aid in ("modest-edge", "boundary-a"):
            a = agents[aid]
            self.assertIsNone(a["score"])
            self.assertIsNone(a["holm_adjusted_p"])
            self.assertEqual(a["family_p_used"], 1)
            self.assertEqual(a["replays"]["completed"], 1)
        self.assertFalse(agents["boundary-a"]["primary"]["explicit_record"])
        self.assertAlmostEqual(agents["strong-edge"]["holm_adjusted_p"], 6*agents["strong-edge"]["raw_p"])

    def test_explicit_missing_record_is_preserved(self):
        self.primary().update(status="missing", reason="Expected file was absent.", observations=None)
        a = self.strong()
        self.assertTrue(a["primary"]["explicit_record"])
        self.assertEqual(a["primary"]["reason"], "Expected file was absent.")
        self.assertIsNone(a["rank"])

    def test_known_zero_score_is_not_unscored(self):
        self.d["protocol"]["hurdle_sharpe_per_period"] = 5.0
        a = self.strong()
        self.assertEqual(a["score"], 0)
        self.assertEqual(a["status"], "scored")
        self.assertIsNotNone(a["rank"])
        self.assertIsNone(indexed(rank_cohort(self.d))["losing-independent"]["score"])

    def test_duplicate_replay_does_not_multiply_history_or_evidence(self):
        self.d["seed_ids"].append("copy")
        for run in list(self.d["runs"]):
            if run["seed_id"] == "primary":
                copy = deepcopy(run)
                copy.update(run_id=run["agent_id"]+"-copy", seed_id="copy")
                self.d["runs"].append(copy)
        report = rank_cohort(self.d)
        self.assertEqual(scores(report), scores(self.report))
        for a in report["agents"]:
            self.assertEqual(a["replays"]["distinct_market_periods"], 252)
            self.assertEqual(a["replays"]["planned"], 3)
            if a["moments"]:
                self.assertEqual(a["moments"]["observations"], 252)

    def test_bad_replay_does_not_replace_frozen_primary(self):
        for run in self.d["runs"]:
            if run["seed_id"] == "replay":
                run.update(status="failed", reason="Replay failure remains visible.", observations=None)
        report = rank_cohort(self.d)
        self.assertEqual(scores(report), scores(self.report))
        self.assertEqual(report["coverage"]["failed_runs"], 6)

    def test_gross_net_equivalence_and_cash_consistency(self):
        self.d["protocol"]["return_basis"] = "net"
        for r in self.d["runs"]:
            for row in r["observations"]:
                row["return"] -= row["cost"]
        self.assertEqual(scores(rank_cohort(self.d)), scores(self.report))
        original = indexed(self.report)["strong-edge"]["raw_p"]
        self.d["protocol"]["cash_return_per_period"] = 0.001
        for r in self.d["runs"]:
            for row in r["observations"]:
                row["return"] += 0.001
        a = self.strong()
        self.assertAlmostEqual(a["raw_p"], original, places=14)
        self.assertIsNone(a["primary"]["metrics"]["annualized"]["sharpe_iid_scaling"])

    def test_unknown_net_costs_abstain_and_unknown_gross_costs_reject(self):
        self.primary()["observations"][0]["cost"] = None
        with self.assertRaises(InputError):
            rank_cohort(self.d)
        self.d["protocol"]["return_basis"] = "net"
        a = self.strong()
        self.assertIsNone(a["score"])
        self.assertIn("cost amounts are unknown", " ".join(a["reasons"]))

    def test_unsupported_or_unknown_global_contracts_abstain(self):
        cases = [("evaluation_status", "reused"), ("evaluation_status", "unknown"),
                 ("cohort_frozen", "unknown"), ("ranking_execution_frozen", "no")]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.d = deepcopy(self.fixture)
                self.d["protocol"][field] = value
                self.assertTrue(all(a["score"] is None for a in rank_cohort(self.d)["agents"]))
        for name in self.d["protocol"]["assumptions"]:
            self.d = deepcopy(self.fixture)
            self.d["protocol"]["assumptions"][name] = "unknown"
            self.assertTrue(all(a["raw_psr"] is None and a["score"] is None for a in rank_cohort(self.d)["agents"]))

    def test_declared_independence_does_not_override_screen(self):
        self.d = make_cohort_fixture(scenario="serial")
        self.d["protocol"]["assumptions"]["serial_independence"] = "assumed"
        a = self.strong()
        self.assertTrue(a["dependence_screen"]["flagged"])
        self.assertIsNone(a["score"])
        self.assertIsNone(a["raw_psr"])

    def test_short_and_constant_histories_abstain(self):
        self.d["protocol"]["minimum_observations"] = 300
        self.assertIsNone(self.strong()["score"])
        self.d = deepcopy(self.fixture)
        for row in self.primary()["observations"]:
            row["return"] = 0.001
        a = self.strong()
        self.assertIsNone(a["score"])
        self.assertEqual(a["moments"]["status"], "unavailable")

    def test_common_risk_limits_and_missing_peak(self):
        for name, value in (("max_drawdown", 0.0), ("max_period_loss", 0.0), ("max_peak_exposure", 0.5)):
            self.d = deepcopy(self.fixture)
            self.d["protocol"]["risk_limits"][name] = value
            self.assertIsNone(self.strong()["score"])
        self.d = deepcopy(self.fixture)
        self.primary()["observations"][0]["peak_exposure"] = None
        self.assertIsNone(self.strong()["score"])

    def test_undefined_exposure_and_reference_never_boost_score(self):
        expected = indexed(self.report)["strong-edge"]["score"]
        for value in (None, 0.0, 5e-324):
            self.d = deepcopy(self.fixture)
            for row in self.primary()["observations"]:
                row["exposure"] = value
            for row in self.d["reference"]["observations"]:
                row["net_return"] = 0
            a = self.strong()
            self.assertEqual(a["score"], expected)
            self.assertIsNone(a["primary"]["efficiency"]["value"])
            self.assertIsNone(a["primary"]["independence"]["value"])
        self.d["reference"] = None
        self.assertEqual(self.strong()["score"], expected)

    def test_losing_independent_agent_does_not_receive_evidence(self):
        a = indexed(self.report)["losing-independent"]
        self.assertLess(a["primary"]["metrics"]["total_return"], 0)
        self.assertIsNotNone(a["primary"]["independence"]["value"])
        self.assertIsNone(a["score"])
        self.assertFalse(a["evidence_qualified"])

    def test_discovery_is_separate_and_never_averaged(self):
        self.d["agents"][0]["discovery"] = {
            "net_returns": [row["return"]-row["cost"] for row in self.primary()["observations"]],
            "cash_return_per_period": 0,
            "selection": {"target_run_id": "separate-development-history", "benchmark_sharpe_per_period": 0,
                          "sharpe_unit": "per_period", "notes": "Separate search context, no holdout reranking.",
                          "assumptions": {key: "assumed" for key in ("serial_independence", "stationarity", "finite_fourth_moment", "normal_trial_sharpes", "comparable_trial_sharpes")},
                          "search": None}}
        report = rank_cohort(self.d)
        self.assertEqual(scores(report), scores(self.report))
        self.assertEqual(indexed(report)["strong-edge"]["discovery_context"]["dsr"]["status"], "unavailable")

    def test_calendar_gaps_duplicates_and_reordering_rejected(self):
        for kind in ("missing", "duplicate", "reorder"):
            self.d = deepcopy(self.fixture)
            rows = self.primary()["observations"]
            if kind == "missing":
                rows.pop(12)
            elif kind == "duplicate":
                rows[12] = deepcopy(rows[11])
            else:
                rows[12], rows[11] = rows[11], rows[12]
            with self.subTest(kind=kind), self.assertRaises(InputError):
                rank_cohort(self.d)

    def test_duplicate_identity_and_version_mismatch_rejected(self):
        mutations = [lambda d: d["seed_ids"].append("primary"),
                     lambda d: d["agents"].append(deepcopy(d["agents"][0])),
                     lambda d: d["runs"].append(deepcopy(d["runs"][0])),
                     lambda d: d["runs"][0].update(version="unregistered"),
                     lambda d: d["runs"][0].update(agent_id="unregistered"),
                     lambda d: d["runs"][0].update(seed_id="unregistered")]
        for mutate in mutations:
            self.d = deepcopy(self.fixture)
            mutate(self.d)
            with self.assertRaises(InputError):
                rank_cohort(self.d)
        self.d = deepcopy(self.fixture)
        self.d["runs"][1].update(seed_id="primary", run_id="unique-but-ambiguous")
        with self.assertRaisesRegex(InputError, "duplicate agent/seed"):
            rank_cohort(self.d)

    def test_nonfinite_or_ambiguous_units_rejected(self):
        for value in (True, float("inf"), float("nan"), "0.01"):
            self.d = deepcopy(self.fixture)
            self.primary()["observations"][0]["return"] = value
            with self.assertRaises(InputError):
                rank_cohort(self.d)
        for key, value in (("hurdle_unit", "annualized"), ("hurdle_sharpe_per_period", 0), ("unit", "percent")):
            self.d = deepcopy(self.fixture)
            self.d["protocol"][key] = value
            with self.assertRaises(InputError):
                rank_cohort(self.d)

    def test_failed_partial_history_and_exposure_contradiction_rejected(self):
        self.primary().update(status="failed", reason="Failed halfway.")
        with self.assertRaises(InputError):
            rank_cohort(self.d)
        self.d = deepcopy(self.fixture)
        self.primary()["observations"][0]["exposure"] = 2
        with self.assertRaises(InputError):
            rank_cohort(self.d)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "iframe", "img", "link", "object", "embed") or any(k.startswith("on") for k, _ in attrs):
            self.errors.append("active content")
        if tag not in ("meta", "br"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.errors.append("unbalanced markup")


class CohortCLITests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "sharpeval", *map(str, args)], cwd=ROOT,
                              capture_output=True, text=True, timeout=45)

    def test_fresh_fixture_validate_rank_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, dest = root/"cohort.json", root/"report"
            self.assertEqual(self.cli("fixture-cohort", "--out", source).returncode, 0)
            checked = self.cli("validate", source)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("12 planned cells", checked.stdout)
            self.assertEqual(self.cli("validate", source, "--alignment", "intersection").returncode, 2)
            self.assertEqual(self.cli("compare", source, "--output", dest).returncode, 2)
            args = ("rank", source, "--output", dest)
            run = self.cli(*args)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("not a probability of skill", run.stdout)
            before = {p.name: p.read_bytes() for p in dest.iterdir()}
            self.assertEqual(self.cli(*args).returncode, 2)
            self.assertEqual(self.cli(*args, "--force").returncode, 0)
            self.assertEqual(before, {p.name: p.read_bytes() for p in dest.iterdir()})
            protected = dest/"report.json"
            protected.write_bytes(source.read_bytes())
            self.assertEqual(self.cli("rank", protected, "--output", dest, "--force").returncode, 2)
            self.assertEqual(protected.read_bytes(), source.read_bytes())

    def test_html_escapes_data_and_has_offline_balanced_structure(self):
        d = make_cohort_fixture()
        d["title"] = '<script>alert("title")</script>'
        d["protocol"]["notes"] = '<img src=x onerror="oops">'
        d["runs"][0].update(status="failed", reason="<iframe>failure</iframe>", observations=None)
        html = render_cohort_html(rank_cohort(d))
        parser = Structure()
        parser.feed(html)
        self.assertEqual(parser.errors, [])
        self.assertEqual(parser.stack, [])
        self.assertIn("&lt;script", html)
        self.assertIn("&lt;img", html)
        self.assertIn("&lt;iframe", html)
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("Unscored", html)
        self.assertIn("not a probability of skill", html)


if __name__ == "__main__":
    unittest.main()
