import copy
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

from sharpeval import InputError, analyze, load_input, validate
from sharpeval.bootstrap import block_indices, paired_bootstrap
from sharpeval.fixtures import make_fixture
from sharpeval.statistics import correlation, diagnostics, quantile, regression, snapshot
from sharpeval.validation import align


def document(old, new, *, cost=0, basis="net", ppy=None):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(len(old))]
    def history(sid, values):
        return {"id": sid, "agent_id": "agent", "version": sid, "source_type": "backtest",
                "frequency_seconds": 86400, "currency": "USD", "unit": "decimal", "return_basis": basis,
                "costs": {"included": ["fee"], "excluded": [], "notes": "Hand-calculated test costs."},
                "observations": [{"timestamp": t, "return": r, "cost": cost} for t, r in zip(dates, values)]}
    return {"schema_version": 1, "title": "Hand-calculated SYNTHETIC fixture", "synthetic": True,
            "calendar": {"frequency_seconds": 86400, "periods_per_year": ppy, "timestamps": dates,
                         "notes": "Explicit synthetic daily sessions."},
            "cash_return_per_period": 0, "series": [history("v1", old), history("v2", new)],
            "comparison": {"old": "v1", "new": "v2"}}


def run(doc, **kwargs):
    return analyze(doc, resamples=200, block_length=4, seed=123, **kwargs)


class HandCalculatedStatistics(unittest.TestCase):
    def test_compounding_drawdown_and_sample_variance(self):
        s = snapshot([0.1, -0.1, 0.05])
        self.assertAlmostEqual(s["total_return"], 0.0395)
        self.assertAlmostEqual(s["mean_return"], 1 / 60)
        self.assertAlmostEqual(s["volatility"], math.sqrt(0.010833333333333334))
        self.assertAlmostEqual(s["max_drawdown"], 0.1)
        self.assertAlmostEqual(s["sharpe_per_period"], (1 / 60) / math.sqrt(0.010833333333333334))

    def test_drawdown_includes_initial_equity(self):
        self.assertAlmostEqual(snapshot([-0.2, 0.25])["max_drawdown"], 0.2)
        self.assertAlmostEqual(snapshot([-0.2, 0.25])["total_return"], 0)

    def test_zero_variance_not_infinite_sharpe(self):
        self.assertIsNone(snapshot([0.01] * 20)["sharpe_per_period"])
        self.assertIsNone(correlation([1, 1, 1], [2, 3, 4]))

    def test_one_observation_is_descriptive_only(self):
        s = run(document([0.02], [0.03]))
        self.assertIsNone(s["series"]["v1"]["metrics"]["volatility"])
        self.assertEqual(s["uncertainty"]["primary"]["status"], "insufficient_data")

    def test_no_annualization_without_declaration(self):
        annual = diagnostics([0.1, 0.1], 0, None)["annualized"]
        self.assertIsNone(annual["geometric_return"])
        self.assertIsNone(annual["sharpe_iid_scaling"])

    def test_declared_annualization(self):
        s = diagnostics([0.1, 0.1], 0, 2)
        self.assertAlmostEqual(s["annualized"]["geometric_return"], 0.21)
        self.assertEqual(s["annualized"]["arithmetic_mean"], 0.2)

    def test_cash_rate_used_in_sharpe(self):
        s = snapshot([0.01, 0.03], 0.01)
        self.assertAlmostEqual(s["sharpe_per_period"], 0.01 / math.sqrt(0.0002))

    def test_leveraged_beta_not_intercept(self):
        x = [-0.02, 0.01, 0.03, -0.01]
        r = regression([2 * v for v in x], x, 0)
        self.assertAlmostEqual(r["beta"], 2)
        self.assertAlmostEqual(r["intercept_per_period"], 0)
        self.assertAlmostEqual(r["correlation"], 1)

    def test_constant_benchmark_regression_unavailable(self):
        self.assertEqual(regression([1, 2, 3], [0, 0, 0], 0)["status"], "unavailable")

    def test_tiny_values_do_not_underflow_covariance(self):
        x = [1e-300, 2e-300, 3e-300]
        y = [2e-300, 4e-300, 6e-300]
        self.assertAlmostEqual(correlation(x, y), 1)
        self.assertAlmostEqual(regression(y, x, 0)["beta"], 2)

    def test_unrepresentable_regression_is_unavailable(self):
        r = regression([100, 200, 300], [1e-310, 2e-310, 3e-310], 0)
        self.assertEqual(r["status"], "unavailable")

    def test_constant_agent_with_tiny_benchmark_has_zero_beta(self):
        r = regression([0, 0, 0], [1e-310, 2e-310, 3e-310], 0)
        self.assertEqual(r["beta"], 0)
        self.assertEqual(r["intercept_per_period"], 0)

    def test_unrepresentable_sharpe_is_unavailable(self):
        self.assertIsNone(snapshot([1e-310, 2e-310, 3e-310], 1)["sharpe_per_period"])

    def test_bankruptcy_is_absorbing_and_inference_withheld(self):
        r = run(document([0.1, -1, 0], [0.02, 0.01, 0]))
        m = r["series"]["v1"]["metrics"]
        self.assertEqual(m["total_return"], -1)
        self.assertEqual(m["max_drawdown"], 1)
        self.assertEqual(m["net_wealth"][-1], 0)
        self.assertTrue(m["bankrupt"])
        self.assertIn("Bankruptcy", r["uncertainty"]["primary"]["reason"])

    def test_wealth_overflow_is_explicit_not_invalid_json(self):
        r = run(document([1000] * 120, [1000] * 120))
        self.assertIsNone(r["series"]["v1"]["metrics"]["total_return"])
        self.assertTrue(r["series"]["v1"]["metrics"]["wealth_overflow"])
        json.dumps(r, allow_nan=False)

    def test_quantile_interpolates(self):
        self.assertEqual(quantile([0, 10, 20], 0.25), 5)


class Integrity(unittest.TestCase):
    def setUp(self):
        self.d = document([0.01, -0.01] * 12, [0.02, -0.01] * 12)

    def test_duplicate_timestamps(self):
        self.d["series"][0]["observations"][1]["timestamp"] = self.d["series"][0]["observations"][0]["timestamp"]
        with self.assertRaisesRegex(InputError, "duplicate"):
            validate(self.d)

    def test_unordered_timestamps(self):
        self.d["series"][0]["observations"].reverse()
        with self.assertRaisesRegex(InputError, "unordered"):
            validate(self.d)

    def test_explicit_utc_required(self):
        self.d["calendar"]["timestamps"][0] = "2025-01-01"
        with self.assertRaisesRegex(InputError, "explicit UTC"):
            validate(self.d)

    def test_duplicate_calendar(self):
        self.d["calendar"]["timestamps"][1] = self.d["calendar"]["timestamps"][0]
        with self.assertRaisesRegex(InputError, "unique"):
            validate(self.d)

    def test_off_grid_calendar(self):
        self.d["calendar"]["timestamps"][1] = "2025-01-02T01:00:00Z"
        with self.assertRaisesRegex(InputError, "frequency grid"):
            validate(self.d)

    def test_nonfinite_and_boolean_numbers(self):
        for bad in (math.nan, math.inf, -math.inf, True, 10**1000):
            with self.subTest(bad=str(bad)[:30]):
                self.d["series"][0]["observations"][0]["return"] = bad
                with self.assertRaisesRegex(InputError, "finite number"):
                    validate(self.d)

    def test_duplicate_json_keys_and_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "input.json"
            for text, message in (('{"x":1,"x":2}', "duplicate JSON key"), ('{"x":NaN}', "nonfinite")):
                p.write_text(text)
                with self.assertRaisesRegex(InputError, message):
                    load_input(p)

    def test_incompatible_frequencies(self):
        self.d["series"][0]["frequency_seconds"] = 3600
        with self.assertRaisesRegex(InputError, "incompatible frequency"):
            validate(self.d)

    def test_mixed_currencies(self):
        self.d["series"][0]["currency"] = "EUR"
        with self.assertRaisesRegex(InputError, "currencies"):
            validate(self.d)

    def test_units_are_not_guessed(self):
        self.d["series"][0]["unit"] = "percent"
        with self.assertRaisesRegex(InputError, "unit must be decimal"):
            validate(self.d)

    def test_unknown_fields_reject_typos(self):
        self.d["series"][0]["frequency"] = 86400
        with self.assertRaisesRegex(InputError, "unknown fields"):
            validate(self.d)

    def test_versions_must_be_distinct_same_agent(self):
        for field, value in (("version", "v1"), ("agent_id", "unrelated-agent")):
            d = copy.deepcopy(self.d)
            d["series"][1][field] = value
            with self.assertRaisesRegex(InputError, "distinct versions"):
                validate(d)

    def test_mixed_source_context_rejected(self):
        self.d["series"][1]["source_type"] = "paper"
        with self.assertRaisesRegex(InputError, "mix live/paper/backtest"):
            run(self.d)

    def test_missing_period_strict(self):
        self.d["series"][1]["observations"].pop(10)
        with self.assertRaisesRegex(InputError, "1 missing periods"):
            run(self.d)

    def test_explicit_intersection_only_trims_edges(self):
        self.d["series"][1]["observations"] = self.d["series"][1]["observations"][2:-1]
        r = run(self.d, alignment="intersection")
        self.assertEqual(r["alignment"]["periods"], 21)
        self.assertEqual(r["alignment"]["dropped_observations"], {"v1": 3, "v2": 0})
        self.assertEqual(len(r["alignment"]["excluded_calendar_timestamps"]), 3)

    def test_intersection_refuses_internal_holes(self):
        self.d["series"][1]["observations"].pop(10)
        with self.assertRaisesRegex(InputError, "internal missing periods"):
            run(self.d, alignment="intersection")

    def test_no_overlap(self):
        self.d["series"][0]["observations"] = self.d["series"][0]["observations"][:4]
        self.d["series"][1]["observations"] = self.d["series"][1]["observations"][-4:]
        with self.assertRaisesRegex(InputError, "no common periods"):
            run(self.d, alignment="intersection")

    def test_return_below_bankruptcy(self):
        self.d["series"][0]["observations"][0]["return"] = -1.01
        with self.assertRaisesRegex(InputError, "simple return range"):
            validate(self.d)

    def test_recapitalization_is_not_assumed(self):
        with self.assertRaisesRegex(InputError, "after bankruptcy"):
            validate(document([-1, 0.1], [0, 0]))

    def test_trimming_cannot_hide_prior_bankruptcy(self):
        d = document([-1, 0, 0], [0, 0, 0])
        d["series"][1]["observations"].pop(0)
        with self.assertRaisesRegex(InputError, "starts after bankruptcy"):
            run(d, alignment="intersection")

    def test_unknown_search_count_is_not_zero(self):
        r = run(self.d)
        self.assertIsNone(r["selection_adjustment"]["search_trials"])
        self.assertEqual(r["selection_adjustment"]["status"], "not_implemented")
        self.assertEqual(r["benchmark"]["status"], "not_supplied")
        self.assertEqual(r["portfolio"]["status"], "not_supplied")

    def test_search_count_is_disclosed_without_fake_correction(self):
        self.d["search_trials"] = 500
        r = run(self.d)
        self.assertEqual(r["selection_adjustment"]["search_trials"], 500)
        self.assertIsNone(r["selection_adjustment"]["deflated_sharpe"])


class CostAndPortfolioTests(unittest.TestCase):
    def test_gross_cost_subtracted_once(self):
        r = run(document([0.1, -0.05], [0.1, -0.05], cost=0.01, basis="gross"))
        self.assertAlmostEqual(r["series"]["v1"]["metrics"]["total_return"], 1.09 * 0.94 - 1)
        self.assertAlmostEqual(r["series"]["v1"]["cost_accounting"]["gross_total_return"], 1.1 * 0.95 - 1)

    def test_net_cost_not_subtracted_again(self):
        r = run(document([0.09, -0.06], [0.09, -0.06], cost=0.01, basis="net"))
        self.assertAlmostEqual(r["series"]["v1"]["metrics"]["total_return"], 1.09 * 0.94 - 1)

    def test_unknown_costs_are_not_zero(self):
        r = run(document([0.1, 0.2], [0.1, 0.2], cost=None))
        self.assertIsNone(r["series"]["v1"]["cost_accounting"]["gross_total_return"])
        self.assertIsNone(r["series"]["v1"]["cost_accounting"]["mean_period_cost_fraction"])

    def test_gross_requires_cost_amounts(self):
        with self.assertRaisesRegex(InputError, "gross returns require"):
            validate(document([0.1], [0.1], cost=None, basis="gross"))

    def test_negative_cost_rejected(self):
        with self.assertRaisesRegex(InputError, "nonnegative"):
            validate(document([0.1], [0.1], cost=-0.01))

    def test_fixed_weights_and_overlay_by_hand(self):
        d = document([0.1, -0.1], [-0.1, 0.1])
        d["portfolio"] = {"weights": {"v1": 1}, "candidate_weight": 0.25,
                          "rebalance": "each_period", "overlay_cost_per_period": 0.01,
                          "overlay_cost_notes": "Hand-calculated extra charge.", "weights_declared_before_evaluation": True}
        p = run(d)["portfolio"]
        self.assertAlmostEqual(p["net_returns"]["with_new"][0], 0.04)
        self.assertAlmostEqual(p["net_returns"]["with_new"][1], -0.06)
        self.assertAlmostEqual(p["metrics"]["with_new"]["total_return"], 1.04 * 0.94 - 1)
        self.assertAlmostEqual(p["metrics"]["base"]["total_return"], -0.01)

    def test_portfolio_constraints(self):
        for weights in ({"existing-trend": 1.2, "existing-carry": -0.2}, {"existing-trend": 0.9}, {"absent": 1}):
            d = make_fixture(periods=40)
            d["portfolio"]["weights"] = weights
            with self.assertRaises(InputError):
                run(d)
        for field, value in (("candidate_weight", 1.1), ("rebalance", "optimized"), ("weights_declared_before_evaluation", False)):
            d = make_fixture(periods=40)
            d["portfolio"][field] = value
            with self.assertRaises(InputError):
                run(d)

    def test_bankrupt_portfolio_withheld(self):
        d = make_fixture(periods=40)
        d["series"][0]["observations"][-1].update({"return": -0.9998, "cost": 0.0002})
        self.assertEqual(run(d)["portfolio"]["status"], "unavailable")

    def test_overlay_cannot_push_portfolio_below_zero(self):
        d = document([-0.99] * 2, [-0.99] * 2)
        d["portfolio"] = {"weights": {"v1": 1}, "candidate_weight": 0.25,
                          "rebalance": "each_period", "overlay_cost_per_period": 0.02,
                          "overlay_cost_notes": "Deliberately invalid.", "weights_declared_before_evaluation": True}
        with self.assertRaisesRegex(InputError, "bankruptcy"):
            run(d)


class PairedBlockTests(unittest.TestCase):
    def test_temporal_order_and_wrap(self):
        class FixedStarts:
            def __init__(self):
                self.starts = iter([4, 1])
            def randrange(self, n):
                return next(self.starts)
        self.assertEqual(block_indices(5, 3, FixedStarts()), [4, 0, 1, 1, 2])

    def test_paired_duplicate_has_exact_zero_change(self):
        values = [0.01, -0.02, 0.03, -0.01] * 12
        b = paired_bootstrap({"a": values, "b": list(values)}, {"delta": ("a", "b")}, {"same": ("a", "b")}, cash=0, resamples=200, block_length=4)
        for interval in b["primary"]["contrasts"]["delta"].values():
            self.assertEqual(interval["lower"], 0)
            self.assertEqual(interval["upper"], 0)
        self.assertAlmostEqual(b["primary"]["correlations"]["same"]["lower"], 1)

    def test_constant_shift_preserved_by_pairing(self):
        values = [0.01, -0.02, 0.03, -0.01] * 12
        r = run(document(values, [v + 0.001 for v in values]))
        interval = r["uncertainty"]["primary"]["contrasts"]["new_minus_old"]["mean_return"]
        self.assertAlmostEqual(interval["lower"], 0.001)
        self.assertAlmostEqual(interval["upper"], 0.001)

    def test_same_seed_reproduces_without_changing_global_rng(self):
        d = document([0.01, -0.02, 0.03, -0.01] * 8, [0.02, 0, -0.01, 0.01] * 8)
        state = random.getstate()
        first = run(d)
        self.assertEqual(random.getstate(), state)
        self.assertEqual(first, run(d))

    def test_block_mean_interval_against_independent_oracle(self):
        x = [0.01, 0.03, -0.02, 0.02, -0.01] * 8
        rng = random.Random(123)
        means = []
        for _ in range(200):
            sampled = []
            for _ in range(10):
                start = rng.randrange(40)
                sampled += [x[(start + j) % 40] for j in range(4)]
            means.append(sum(sampled) / 40)
        means.sort()
        # Independent linear-percentile calculation, no implementation helper.
        def oracle(p):
            position = 199 * p
            index = int(position)
            return means[index] + (means[index + 1] - means[index]) * (position - index)
        b = paired_bootstrap({"zero": [0] * 40, "x": x}, {"delta": ("zero", "x")}, {}, cash=0, resamples=200, block_length=4, seed=123)
        interval = b["primary"]["contrasts"]["delta"]["mean_return"]
        self.assertAlmostEqual(interval["lower"], oracle(0.025))
        self.assertAlmostEqual(interval["upper"], oracle(0.975))

    def test_correlated_samples_show_block_sensitivity(self):
        values = ([0.01] * 8 + [-0.01] * 8) * 8
        b = paired_bootstrap({"zero": [0] * 128, "x": values}, {"delta": ("zero", "x")}, {}, cash=0, resamples=400, block_length=4)
        intervals = {run["block_length"]: run["contrasts"]["delta"]["mean_return"] for run in b["sensitivity"]}
        width = lambda n: intervals[n]["upper"] - intervals[n]["lower"]
        self.assertGreater(width(8), width(2) * 1.2)

    def test_no_silent_discard_of_undefined_sharpe(self):
        r = run(document([0] * 40, [0.01] * 40))
        interval = r["uncertainty"]["primary"]["contrasts"]["new_minus_old"]["sharpe_per_period"]
        self.assertEqual(interval["status"], "unavailable")
        self.assertEqual(interval["valid_resamples"], 0)

    def test_small_sample_and_long_blocks(self):
        r = run(document([0.01, -0.01] * 4, [0.02, -0.02] * 4))
        self.assertEqual(r["uncertainty"]["primary"]["status"], "insufficient_data")
        b = paired_bootstrap({"a": [0] * 40, "b": [0] * 40}, {"d": ("a", "b")}, {}, cash=0, block_length=100, resamples=200)
        self.assertEqual(b["primary"]["status"], "insufficient_data")

    def test_invalid_resampling_settings(self):
        for kwargs in ({"block_length": 1}, {"resamples": 199}, {"confidence": 1.0}, {"seed": -1}):
            with self.assertRaises(InputError):
                paired_bootstrap({"a": [0] * 40, "b": [0] * 40}, {"d": ("a", "b")}, {}, cash=0, **kwargs)


class SyntheticBaselineTests(unittest.TestCase):
    def test_leveraged_beta_fixture(self):
        r = run(make_fixture("leveraged-beta", periods=80))
        reg = r["benchmark"]["regressions"]["agent-v2"]
        self.assertAlmostEqual(reg["beta"], 2, places=8)
        self.assertAlmostEqual(reg["intercept_per_period"], 0, places=8)

    def test_lucky_outlier_exposed_without_skill_verdict(self):
        r = run(make_fixture("lucky-outlier", periods=80))
        self.assertAlmostEqual(r["comparison"]["observed_change"]["mean_return"], 0.30 / 80)
        self.assertAlmostEqual(r["comparison"]["outlier_sensitivity"]["mean_change_excluding_that_period"], 0)
        interval = r["uncertainty"]["primary"]["contrasts"]["new_minus_old"]["mean_return"]
        self.assertLessEqual(interval["lower"], 1e-12)
        self.assertEqual(r["selection_adjustment"]["status"], "not_implemented")

    def test_duplicate_agent_adds_nothing_to_identical_base(self):
        d = make_fixture("duplicate", periods=80)
        d["portfolio"]["weights"] = {"existing-trend": 1}
        d["portfolio"]["overlay_cost_per_period"] = 0
        r = run(d)
        self.assertAlmostEqual(r["portfolio"]["candidate_vs_base_correlation"], 1)
        for value in r["portfolio"]["changes"]["with_new_minus_base"].values():
            self.assertAlmostEqual(value, 0, places=12)

    def test_complementary_stream_reduces_fixed_portfolio_risk(self):
        r = run(make_fixture("complementary", periods=80))
        self.assertLess(r["portfolio"]["candidate_vs_base_correlation"], -0.5)
        self.assertLess(r["portfolio"]["changes"]["with_new_minus_base"]["volatility"], 0)
        self.assertTrue(r["synthetic"])
        self.assertTrue(any("not evidence" in w for w in r["warnings"]))

    def test_fixture_reproducibility(self):
        self.assertEqual(make_fixture(), make_fixture())
        self.assertNotEqual(make_fixture(seed=1), make_fixture(seed=2))


if __name__ == "__main__":
    unittest.main()
