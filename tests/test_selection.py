"""Published rounded cases plus a numerical-integration oracle, not production math."""

from copy import deepcopy
import math
import random
import statistics
import unittest

from sharpeval import InputError, validate
from sharpeval.experiment_fixtures import make_experiment_fixture, selection_spec
from sharpeval.selection import (dependence_screen, expected_max_sharpe,
                                psr_from_summary, return_moments,
                                selection_diagnostics, validate_selection)


def integrated_cdf(z):
    """Simpson quadrature of the Normal density; no NormalDist/erf helpers."""
    if z == 0:
        return 0.5
    n = 2048
    x = abs(z)
    step = x / n
    density = lambda value: math.exp(-value * value / 2) / math.sqrt(2 * math.pi)
    area = step / 3 * (density(0) + density(x) + sum(
        (4 if i % 2 else 2) * density(i * step) for i in range(1, n)))
    return 0.5 + (area if z > 0 else -area)


def integrated_quantile(p):
    left, right = -9.0, 9.0
    for _ in range(50):
        middle = (left + right) / 2
        if integrated_cdf(middle) < p:
            left = middle
        else:
            right = middle
    return (left + right) / 2


def reference_dsr(sr, observations, skew, kurtosis, trial_sd, trials):
    # Equations (1)-(2), Bailey & Lopez de Prado 2014. Independent evaluation.
    bar = 0 if trials == 1 else trial_sd * (
        (1 - 0.5772156649015329) * integrated_quantile(1 - 1 / trials)
        + 0.5772156649015329 * integrated_quantile(1 - 1 / (trials * math.exp(1))))
    variance = (1 - skew * sr + (kurtosis - 1) * sr**2 / 4) / (observations - 1)
    return bar, integrated_cdf((sr - bar) / math.sqrt(variance))


def selected_fixture(scenario="repeated"):
    document = make_experiment_fixture(scenario)
    checked = validate(document)
    spec = document["selection"][0]
    return list(checked["histories"][spec["target_run_id"]].net), spec


class PublishedFormulaTests(unittest.TestCase):
    def test_published_non_normal_examples(self):
        # Paper's annual SR=2.5, T=1250, 250 periods/year, annual trial variance=.5.
        # Convert both SR and trial SD to PER-PERIOD before applying either formula.
        sr, sd = 2.5 / math.sqrt(250), math.sqrt(0.5 / 250)
        for n, published in ((100, 0.9004), (46, 0.9505)):
            with self.subTest(n=n):
                bar = expected_max_sharpe(n, sd)
                actual = psr_from_summary(sr, 1250, -3, 10, bar)["value"]
                self.assertAlmostEqual(actual, published, delta=0.00005)
                oracle_bar, oracle_value = reference_dsr(sr, 1250, -3, 10, sd, n)
                self.assertAlmostEqual(bar, oracle_bar, places=10)
                self.assertAlmostEqual(actual, oracle_value, places=10)
        self.assertAlmostEqual(expected_max_sharpe(100, sd), 0.1132, delta=0.00005)

    def test_published_normal_case(self):
        sr, sd = 2.5 / math.sqrt(250), math.sqrt(0.5 / 250)
        bar = expected_max_sharpe(88, sd)
        value = psr_from_summary(sr, 1250, 0, 3, bar)["value"]
        self.assertAlmostEqual(value, 0.9505, delta=0.00005)
        self.assertAlmostEqual(value, reference_dsr(sr, 1250, 0, 3, sd, 88)[1], places=10)

    def test_psr_hand_null_and_standard_normal(self):
        self.assertEqual(psr_from_summary(0, 101, 0, 3)["value"], 0.5)
        value = psr_from_summary(0.1, 101, 0, 3)
        self.assertAlmostEqual(value["variance_factor"], 1.005)
        self.assertAlmostEqual(value["value"], integrated_cdf(1 / math.sqrt(1.005)), places=11)
        self.assertEqual(psr_from_summary(0.1, 101, 0, 3, 0.1)["value"], 0.5)

    def test_independent_oracle_under_skew_and_heavy_tails(self):
        for sr, skew, kurt in ((0.15, -1, 6), (-0.05, 0.8, 5), (0.07, 0, 1.5)):
            bar, expected = reference_dsr(sr, 240, skew, kurt, 0.04, 20)
            self.assertAlmostEqual(expected_max_sharpe(20, 0.04), bar, places=10)
            self.assertAlmostEqual(psr_from_summary(sr, 240, skew, kurt, bar)["value"], expected, places=10)

    def test_more_trials_cannot_raise_score_at_fixed_inputs(self):
        bars = [expected_max_sharpe(n, 0.045) for n in (1, 2, 5, 10, 50, 100, 1000, 1000000)]
        values = [psr_from_summary(0.16, 1250, -3, 10, b)["value"] for b in bars]
        self.assertEqual(bars, sorted(bars))
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertGreater(values[0], values[-1])

    def test_single_trial_and_zero_dispersion_boundaries(self):
        self.assertEqual(expected_max_sharpe(1, None), 0)
        self.assertEqual(expected_max_sharpe(1, 0.1), 0)
        self.assertEqual(expected_max_sharpe(100, 0), 0)

    def test_invalid_formula_arguments_rejected(self):
        for n, sd in ((0, 0.1), (-1, 0.1), (2.5, 0.1), (True, 0.1), (2, None), (2, -0.1), (2, math.inf)):
            with self.subTest(n=n, sd=sd), self.assertRaises(InputError):
                expected_max_sharpe(n, sd)
        for args in ((0.1, 2, 0, 3), (0.1, 100, -3, 3), (0.1, 100, 0, 0), (math.inf, 100, 0, 3)):
            with self.subTest(args=args), self.assertRaises(InputError):
                psr_from_summary(*args)


class MomentTests(unittest.TestCase):
    def test_hand_calculated_moments_and_cash(self):
        values = [-0.01, 0, 0.01, 0.02, 0.03]
        m = return_moments(values)
        self.assertAlmostEqual(m["sharpe_per_period"], 0.01 / math.sqrt(0.00025))
        self.assertAlmostEqual(m["skewness"], 0)
        self.assertAlmostEqual(m["kurtosis_non_excess"], 1.7)
        self.assertAlmostEqual(return_moments(values, 0.01)["sharpe_per_period"], 0)

    def test_asymmetric_moments_against_direct_sums(self):
        values = [0.01] * 7 + [-0.03, 0.04, -0.06]
        center = sum(values) / len(values)
        v = sum((x - center)**2 for x in values) / len(values)
        m = return_moments(values)
        self.assertAlmostEqual(m["skewness"], sum((x - center)**3 for x in values) / len(values) / v**1.5)
        self.assertAlmostEqual(m["kurtosis_non_excess"], sum((x - center)**4 for x in values) / len(values) / v**2)

    def test_scale_invariance_and_zero_variance(self):
        values = [-0.01, 0.02, 0.003, -0.006]
        for scale in (1e-250, 1e5):
            scaled = return_moments([x * scale for x in values])
            for key in ("sharpe_per_period", "skewness", "kurtosis_non_excess"):
                self.assertAlmostEqual(scaled[key], return_moments(values)[key])
        self.assertEqual(return_moments([0.01] * 30)["status"], "unavailable")
        self.assertEqual(return_moments([0.01, 0.02])["status"], "unavailable")


class SelectionContractTests(unittest.TestCase):
    def setUp(self):
        self.returns, self.spec = selected_fixture()

    def diagnostics(self):
        return selection_diagnostics(self.returns, 0, self.spec)

    def assumed_search(self, observed=100, effective=40):
        self.spec["search"].update(observed_trial_count=observed, effective_independent_trials=effective,
                                    dispersion_source="assumed", trial_sharpe_std_per_period=0.08)

    def test_single_trial_needs_no_extreme_value_assumption_or_dispersion(self):
        self.spec["assumptions"]["normal_trial_sharpes"] = "unknown"
        self.spec["assumptions"]["comparable_trial_sharpes"] = "unknown"
        r = self.diagnostics()
        self.assertEqual(r["dsr"]["status"], "conditional")
        self.assertEqual(r["dsr"]["value"], r["psr"]["value"])
        self.assertIsNone(r["trial_dispersion_used"]["value"])

    def test_psr_benchmark_is_not_silently_used_as_dsr_null(self):
        self.spec["benchmark_sharpe_per_period"] = 0.03
        r = self.diagnostics()
        self.assertLess(r["psr"]["value"], r["dsr"]["value"])
        self.assertEqual(r["dsr"]["benchmark_sharpe_per_period"], 0)

    def test_unknown_search_is_not_zero(self):
        self.spec["search"] = None
        r = self.diagnostics()
        self.assertEqual(r["psr"]["status"], "conditional")
        self.assertEqual(r["dsr"]["status"], "unavailable")
        self.assertIn("unknown trials", " ".join(r["dsr"]["reasons"]))

    def test_unknown_counts_and_dispersion_each_withhold_dsr(self):
        self.assumed_search()
        original = deepcopy(self.spec)
        for field in ("observed_trial_count", "effective_independent_trials", "trial_sharpe_std_per_period"):
            self.spec = deepcopy(original)
            self.spec["search"][field] = None
            with self.subTest(field=field):
                self.assertEqual(self.diagnostics()["dsr"]["status"], "unavailable")

    def test_incomplete_search_is_explicit(self):
        self.assumed_search()
        for completeness in ("unknown", "incomplete"):
            self.spec["search"]["completeness"] = completeness
            self.assertEqual(self.diagnostics()["dsr"]["status"], "unavailable")

    def test_observed_and_effective_counts_remain_distinct(self):
        self.assumed_search()
        r = self.diagnostics()
        self.assertEqual(r["dsr"]["observed_trial_count"], 100)
        self.assertEqual(r["dsr"]["effective_independent_trials"], 40)
        sensitivity = r["dsr"]["sensitivity"]
        self.assertEqual([s["effective_independent_trials"] for s in sensitivity], [1, 40, 100])
        self.assertGreater(sensitivity[0]["value"], sensitivity[1]["value"])
        self.assertGreater(sensitivity[1]["value"], sensitivity[2]["value"])
        self.assertEqual(r["trial_dispersion_used"]["source"], "user_assumed")

    def test_unit_and_effective_trial_constraints(self):
        for change in ({"observed_trial_count": 5, "effective_independent_trials": 6}, {"observed_trial_count": 0}):
            spec = deepcopy(self.spec)
            spec["search"].update(change)
            with self.assertRaises(InputError):
                validate_selection(spec)
        self.spec["sharpe_unit"] = "annualized"
        with self.assertRaisesRegex(InputError, "per_period"):
            validate_selection(self.spec)

    def test_unknown_time_assumptions_withhold_both(self):
        for assumption in ("serial_independence", "stationarity", "finite_fourth_moment"):
            spec = deepcopy(self.spec)
            spec["assumptions"][assumption] = "unknown"
            r = selection_diagnostics(self.returns, 0, spec)
            self.assertEqual(r["psr"]["status"], "unavailable")
            self.assertEqual(r["dsr"]["status"], "unavailable")

    def test_trial_assumptions_gate_dsr_only(self):
        self.assumed_search()
        for assumption in ("normal_trial_sharpes", "comparable_trial_sharpes"):
            spec = deepcopy(self.spec)
            spec["assumptions"][assumption] = "unsupported"
            r = selection_diagnostics(self.returns, 0, spec)
            self.assertEqual(r["psr"]["status"], "conditional")
            self.assertEqual(r["dsr"]["status"], "unavailable")

    def test_nonnormal_and_serial_fixtures(self):
        values, spec = selected_fixture("nonnormal")
        r = selection_diagnostics(values, 0, spec)
        self.assertLess(r["moments"]["skewness"], -0.5)
        self.assertGreater(r["moments"]["kurtosis_non_excess"], 3)
        self.assertEqual(r["psr"]["status"], "conditional")
        values, spec = selected_fixture("serial")
        spec["assumptions"]["serial_independence"] = "assumed"  # Screen still withholds.
        r = selection_diagnostics(values, 0, spec)
        self.assertEqual(r["dependence_screen"]["status"], "flagged")
        self.assertEqual(r["psr"]["status"], "unavailable")
        self.assertEqual(r["moments"]["observations"], len(values))

    def test_volatility_clustering_is_screened(self):
        rng = random.Random(1729)
        values = [rng.choice([-1, 1]) * (0.002 if i < 150 else 0.03) for i in range(300)]
        screen = dependence_screen(values)
        self.assertTrue(any(row["series"] == "squared_centered_returns" for row in screen["flagged"]))

    def test_too_short_constant_and_bankrupt_are_unavailable(self):
        for values in (self.returns[:19], [0] * 120, self.returns[:-1] + [-1]):
            r = selection_diagnostics(values, 0, self.spec)
            self.assertEqual(r["psr"]["status"], "unavailable")
            self.assertIsNone(r["dsr"]["value"])

    def test_unsupported_nonzero_trial_null_withheld(self):
        self.spec["search"]["null_mean_sharpe_per_period"] = 0.01
        self.assertEqual(self.diagnostics()["dsr"]["status"], "unavailable")


class TrialLedgerTests(unittest.TestCase):
    def setUp(self):
        self.values, self.spec = selected_fixture("lucky-search")

    def test_luckiest_of_100_zero_mean_trials_is_deflated(self):
        r = selection_diagnostics(self.values, 0, self.spec)
        self.assertEqual(r["dsr"]["status"], "conditional")
        self.assertGreater(r["psr"]["value"], 0.98)
        self.assertLess(r["dsr"]["value"], 0.4)
        self.assertEqual(r["dsr"]["observed_trial_count"], 100)
        ledger = self.spec["search"]["trial_sharpes"]
        self.assertAlmostEqual(r["trial_dispersion_used"]["value"], statistics.stdev(row["sharpe_per_period"] for row in ledger))
        self.assertAlmostEqual(r["moments"]["sharpe_per_period"], max(row["sharpe_per_period"] for row in ledger))

    def test_missing_loser_not_dropped_from_dispersion(self):
        self.spec["search"]["trial_sharpes"][0]["sharpe_per_period"] = None
        r = selection_diagnostics(self.values, 0, self.spec)
        self.assertEqual(r["dsr"]["status"], "unavailable")
        self.assertIsNone(r["trial_dispersion_used"])
        self.assertEqual(r["search"]["observed_trial_count"], 100)

    def test_missing_ledger_rows_and_selected_mismatch(self):
        for mismatch in (False, True):
            spec = deepcopy(self.spec)
            if mismatch:
                for row in spec["search"]["trial_sharpes"]:
                    if row["trial_id"] == spec["search"]["selected_trial_id"]:
                        row["sharpe_per_period"] += 0.01
            else:
                spec["search"]["trial_sharpes"].pop(0)
            self.assertEqual(selection_diagnostics(self.values, 0, spec)["dsr"]["status"], "unavailable")

    def test_duplicate_trial_identity_rejected(self):
        ledger = self.spec["search"]["trial_sharpes"]
        ledger[1]["trial_id"] = ledger[0]["trial_id"]
        with self.assertRaisesRegex(InputError, "duplicate trial"):
            validate_selection(self.spec)


if __name__ == "__main__":
    unittest.main()
