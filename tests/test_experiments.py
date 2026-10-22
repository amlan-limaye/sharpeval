"""Run coverage, paired aggregation, dependence boundaries and compatibility."""

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import random
import unittest

from sharpeval import InputError, analyze, validate
from sharpeval.experiment_fixtures import make_experiment_fixture
from sharpeval.report import render_html


def one_window(periods=40, seeds=3, references=False):
    d = make_experiment_fixture(periods=periods)
    d["windows"] = d["windows"][:1]
    d["seed_ids"] = d["seed_ids"][:seeds]
    d["runs"] = [r for r in d["runs"] if r["window_id"] == "window-1" and r["seed_id"] in d["seed_ids"]]
    d["selection"] = []
    if not references:
        for key in ("reference_series", "benchmark", "portfolio"):
            d["windows"][0].pop(key)
    return d


def run(d, **settings):
    return analyze(d, resamples=200, block_length=4, seed=123, **settings)


class RunAggregationTests(unittest.TestCase):
    def test_mean_path_is_by_timestamp_and_costs_once(self):
        d = one_window(periods=20, seeds=2)
        for r in d["runs"]:
            r["history"]["return_basis"] = "gross"
            seed_shift = 0.02 if r["seed_id"] == "seed-2" else 0
            version_shift = 0.005 if r["version"] == "v2" else 0
            for i, row in enumerate(r["history"]["observations"]):
                row["return"] = (0.10 if i % 2 == 0 else -0.05) + seed_shift + version_shift
                row["cost"] = 0.01
        r = run(d)
        aggregate = r["windows"][0]["aggregate"]
        comp = aggregate["comparison"]
        old = comp["series"]["run-old"]["metrics"]
        # Mean net old path: +.10, -.05. Mean gross old path: +.11, -.04.
        self.assertAlmostEqual(old["mean_return"], 0.025)
        self.assertAlmostEqual(old["total_return"], (1.10 * 0.95)**10 - 1)
        self.assertEqual(old["observations"], 20)
        self.assertEqual(aggregate["seeds_averaged"], 2)
        self.assertEqual(aggregate["distinct_market_periods"], 20)
        costs = comp["series"]["run-old"]["cost_accounting"]
        self.assertAlmostEqual(costs["mean_period_cost_fraction"], 0.01)
        self.assertAlmostEqual(costs["gross_total_return"], (1.11 * 0.96)**10 - 1)
        interval = comp["uncertainty"]["primary"]["contrasts"]["new_minus_old"]["mean_return"]
        self.assertAlmostEqual(interval["lower"], 0.005)
        self.assertAlmostEqual(interval["upper"], 0.005)

    def test_net_and_gross_paths_are_equivalent(self):
        gross = one_window(seeds=2)
        net = deepcopy(gross)
        for r in net["runs"]:
            r["history"]["return_basis"] = "net"
            for row in r["history"]["observations"]:
                row["return"] -= row["cost"]
        a, b = run(gross), run(net)
        for left, right in zip(a["runs"], b["runs"]):
            self.assertEqual(left["metrics"], right["metrics"])
        self.assertEqual(a["windows"][0]["aggregate"]["comparison"], b["windows"][0]["aggregate"]["comparison"])

    def test_duplicating_every_seed_does_not_increase_time_sample(self):
        d = one_window(seeds=2)
        original = run(d)
        duplicates = []
        for seed in d["seed_ids"][:]:
            new_seed = seed + "-copy"
            for r in d["runs"]:
                if r["seed_id"] == seed:
                    clone = deepcopy(r)
                    clone.update(run_id=r["run_id"] + "-copy", seed_id=new_seed)
                    duplicates.append(clone)
            d["seed_ids"].append(new_seed)
        d["runs"].extend(duplicates)
        repeated = run(d)
        left = original["windows"][0]["aggregate"]["comparison"]
        right = repeated["windows"][0]["aggregate"]["comparison"]
        self.assertEqual(left, right)
        self.assertEqual(repeated["aggregate"]["unique_planned_market_periods"], 40)
        self.assertEqual(len(repeated["windows"][0]["identical_pair_seed_groups"]), 2)
        self.assertIsNone(repeated["aggregate"]["across_window_confidence_interval"])

    def test_correlated_seeds_have_spread_not_standard_error(self):
        d = one_window()
        r = run(d)
        spread = r["windows"][0]["execution_dispersion"]["paired_changes"]["mean_return"]
        values = [p["observed_change"]["mean_return"] for p in r["pairs"]]
        center = sum(values) / 3
        self.assertAlmostEqual(spread["mean"], center)
        self.assertAlmostEqual(spread["sample_std"], (sum((v - center)**2 for v in values) / 2)**0.5)
        self.assertIsNone(spread["confidence_interval"])
        self.assertIn("not a standard error", r["windows"][0]["execution_dispersion"]["warning"])

    def test_missing_and_failed_runs_withhold_affected_aggregate(self):
        r = run(make_experiment_fixture("missing-runs", periods=40))
        self.assertEqual(r["coverage"], {"planned_runs": 12, "completed_runs": 10, "failed_runs": 1,
                                        "missing_runs": 1, "planned_pairs": 6, "complete_pairs": 4})
        missing = [v for v in r["runs"] if v["status"] == "missing"][0]
        self.assertIsNone(missing["run_id"])
        self.assertIsNone(missing["metrics"])
        first, second = r["windows"]
        self.assertEqual(first["aggregate"]["status"], "unavailable")
        self.assertIsNone(first["aggregate"]["comparison"])
        self.assertIn("survivor", first["execution_dispersion"]["warning"])
        self.assertEqual(second["aggregate"]["status"], "conditional_on_observed_executions")

    def test_all_missing_records_still_produce_coverage(self):
        d = one_window(seeds=1)
        d["runs"] = []
        r = run(d)
        self.assertEqual(r["coverage"]["missing_runs"], 2)
        self.assertEqual(r["windows"][0]["aggregate"]["status"], "unavailable")
        self.assertEqual(r["selection"]["status"], "not_supplied")
        self.assertIn("Window aggregate unavailable", render_html(r))

    def test_overlapping_windows_are_not_pooled(self):
        r = run(make_experiment_fixture("overlap", periods=40))
        self.assertEqual(r["aggregate"]["unique_planned_market_periods"], 60)
        self.assertEqual(r["aggregate"]["overlap_pairs"][0]["shared_periods"], 20)
        self.assertIsNone(r["aggregate"]["pooled_statistics"])
        self.assertIsNone(r["aggregate"]["across_window_confidence_interval"])
        for window in r["windows"]:
            self.assertEqual(window["aggregate"]["comparison"]["alignment"]["periods"], 40)

    def test_identical_window_replication_keeps_unique_period_count(self):
        d = one_window(seeds=1)
        other = deepcopy(d["windows"][0])
        other["window_id"] = "window-copy"
        d["windows"].append(other)
        for r in d["runs"][:]:
            clone = deepcopy(r)
            clone.update(run_id=r["run_id"] + "-copy", window_id="window-copy")
            d["runs"].append(clone)
        r = run(d)
        self.assertEqual(r["aggregate"]["unique_planned_market_periods"], 40)
        self.assertEqual(r["aggregate"]["overlap_pairs"][0]["shared_periods"], 40)

    def test_unknown_costs_are_not_filled_or_subtracted(self):
        d = one_window(seeds=1)
        for r in d["runs"]:
            r["history"]["return_basis"] = "net"
            for row in r["history"]["observations"]:
                row["cost"] = None
        r = run(d)
        for result in r["runs"]:
            self.assertIsNone(result["cost_accounting"]["mean_period_cost_fraction"])
            self.assertIsNone(result["cost_accounting"]["gross_total_return"])
        comp = r["windows"][0]["aggregate"]["comparison"]
        self.assertIsNone(comp["series"]["run-old"]["cost_accounting"]["gross_total_return"])

    def test_inconsistent_cost_conditions_withhold_average(self):
        d = one_window()
        d["runs"][2]["history"]["costs"]["notes"] = "Different experiment conditions."
        r = run(d)
        self.assertEqual(r["windows"][0]["aggregate"]["status"], "unavailable")
        self.assertIn("cost coverage", " ".join(r["windows"][0]["aggregate"]["reasons"]))

    def test_one_bankrupt_execution_cannot_be_averaged_away(self):
        d = one_window()
        r = d["runs"][0]
        r["history"]["return_basis"] = "net"
        r["history"]["observations"][-1].update({"return": -1, "cost": 0})
        result = run(d)
        self.assertTrue(result["runs"][0]["metrics"]["bankrupt"])
        self.assertEqual(result["windows"][0]["aggregate"]["status"], "unavailable")

    def test_undefined_run_sharpe_not_removed_from_spread(self):
        d = one_window()
        for row in d["runs"][0]["history"]["observations"]:
            row["return"] = 0.001
        r = run(d)
        spread = r["windows"][0]["execution_dispersion"]["paired_changes"]["sharpe_per_period"]
        self.assertEqual(spread["status"], "unavailable")
        self.assertEqual(spread["expected_values"], 3)
        self.assertEqual(spread["defined_values"], 2)
        self.assertIsNone(spread["mean"])

    def test_portfolio_formula_on_mean_execution_path(self):
        d = one_window(references=True)
        r = run(d)
        checked = validate(d)
        comp = r["windows"][0]["aggregate"]["comparison"]
        p = comp["portfolio"]
        ref = d["windows"][0]["reference_series"][0]["observations"]
        for i in range(40):
            new_mean = sum(h.net[i] for rid, h in checked["histories"].items() if rid.endswith("v2")) / 3
            expected = 0.75 * (ref[i]["return"] - ref[i]["cost"]) + 0.25 * new_mean - 0.00002
            self.assertAlmostEqual(p["net_returns"]["with_new"][i], expected)

    def test_no_annualization_without_periods_per_year(self):
        d = one_window()
        d["evaluation"]["periods_per_year"] = None
        r = run(d)
        self.assertIsNone(r["runs"][0]["metrics"]["annualized"]["geometric_return"])

    def test_selection_uses_named_actual_run_not_averaged_path(self):
        d = make_experiment_fixture(periods=40)
        r = run(d)
        target = r["selection"]["targets"][0]
        actual = next(item for item in r["runs"] if item["run_id"] == target["target_run_id"])
        self.assertAlmostEqual(target["moments"]["sharpe_per_period"], actual["metrics"]["sharpe_per_period"])
        self.assertEqual(target["moments"]["observations"], 40)
        self.assertEqual(target["search"]["observed_trial_count"], 1)
        self.assertEqual(r["coverage"]["completed_runs"], 12)

    def test_selected_failed_run_visible_and_unavailable(self):
        d = make_experiment_fixture("missing-runs", periods=40)
        d["selection"][0]["target_run_id"] = next(r["run_id"] for r in d["runs"] if r["status"] == "failed")
        r = run(d)
        target = r["selection"]["targets"][0]
        self.assertIsNone(target["psr"]["value"])
        self.assertIsNone(target["dsr"]["value"])
        self.assertIn("Target run is missing or failed", render_html(r))

    def test_determinism_and_input_and_rng_untouched(self):
        d = one_window()
        before, state = deepcopy(d), random.getstate()
        a, b = run(d), run(d)
        self.assertEqual(a, b)
        self.assertEqual(d, before)
        self.assertEqual(random.getstate(), state)


class RunIntegrityTests(unittest.TestCase):
    def test_duplicate_id_and_duplicate_cell_rejected(self):
        for duplicate_id in (True, False):
            d = one_window()
            if duplicate_id:
                d["runs"][1]["run_id"] = d["runs"][0]["run_id"]
            else:
                d["runs"][1]["version"] = d["runs"][0]["version"]
            with self.assertRaisesRegex(InputError, "duplicate"):
                validate(d)

    def test_run_outside_declared_matrix_rejected(self):
        for key in ("window_id", "seed_id", "version"):
            d = one_window()
            d["runs"][0][key] = "undeclared"
            with self.assertRaisesRegex(InputError, "outside"):
                validate(d)

    def test_missing_completed_period_is_error_not_intersection(self):
        d = one_window()
        d["runs"][0]["history"]["observations"].pop(10)
        with self.assertRaisesRegex(InputError, "missing periods"):
            validate(d)
        with self.assertRaisesRegex(InputError, "strict"):
            run(one_window(), alignment="intersection")

    def test_failed_run_requires_reason_and_no_partial_history(self):
        d = one_window()
        d["runs"][0]["status"] = "failed"
        with self.assertRaisesRegex(InputError, "partial history"):
            validate(d)
        d["runs"][0].pop("history")
        with self.assertRaises(InputError):
            validate(d)
        d["runs"][0]["reason"] = "Known failure; outcome unknown."
        validate(d)

    def test_overlapping_intervals_with_shifted_grid_rejected(self):
        d = make_experiment_fixture("overlap", periods=20)
        def shifted(timestamp):
            return (datetime.fromisoformat(timestamp.replace("Z", "+00:00")) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        w = d["windows"][1]
        w["timestamps"] = [shifted(t) for t in w["timestamps"]]
        for series in w["reference_series"]:
            for row in series["observations"]:
                row["timestamp"] = shifted(row["timestamp"])
        with self.assertRaisesRegex(InputError, "grid phases"):
            validate(d)

    def test_explicit_units_and_reference_frequency_rejected_if_incompatible(self):
        d = one_window()
        d["evaluation"]["unit"] = "percent"
        with self.assertRaisesRegex(InputError, "decimal"):
            validate(d)
        d = one_window(references=True)
        d["windows"][0]["reference_series"][0]["frequency_seconds"] = 3600
        with self.assertRaisesRegex(InputError, "frequency"):
            validate(d)

    def test_invalid_portfolio_weight_rejected(self):
        d = one_window(references=True)
        d["windows"][0]["portfolio"]["candidate_weight"] = 1.1
        with self.assertRaises(InputError):
            validate(d)

    def test_unused_reference_still_requires_full_coverage_and_same_source(self):
        for field in ("coverage", "source"):
            d = one_window(references=True)
            window = d["windows"][0]
            window.pop("benchmark")
            window.pop("portfolio")
            reference = window["reference_series"][0]
            if field == "coverage":
                reference["observations"].pop(0)
            else:
                reference["source_type"] = "paper"
            with self.subTest(field=field), self.assertRaisesRegex(InputError, "reference"):
                validate(d)

    def test_selection_target_must_be_explicit_unique_run(self):
        d = make_experiment_fixture(periods=20)
        d["selection"].append(deepcopy(d["selection"][0]))
        with self.assertRaisesRegex(InputError, "unique explicit"):
            validate(d)
        d["selection"] = d["selection"][:1]
        d["selection"][0]["target_run_id"] = "unknown"
        with self.assertRaisesRegex(InputError, "unique explicit"):
            validate(d)


class FrozenSchemaOneTests(unittest.TestCase):
    def test_v01_minimal_json_and_html_byte_hashes(self):
        # Immutable v0.1 delivery hashes, verified before v0.2 implementation.
        path = Path(__file__).resolve().parents[1] / "examples" / "minimal.json"
        report = analyze(json.loads(path.read_text()), resamples=200, seed=42)
        self.assertEqual(report["tool"]["version"], "0.1.0")
        # Python version is diagnostic metadata; compare at the frozen delivery runtime.
        report["tool"]["python"] = "3.13.7"
        encoded = (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), "3b6e704d54f3e7d9f0b331f1feb769e128665bbcf7f4160412edf1619132b29a",
                         "FROZEN_REPORT_DIAGNOSTIC=" + json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
        self.assertEqual(hashlib.sha256(render_html(report).encode()).hexdigest(), "aa2c8c12d894f61ca9080ab6727d8f1a1adf557b31d637807adc75a8a63ed6be")


if __name__ == "__main__":
    unittest.main()
