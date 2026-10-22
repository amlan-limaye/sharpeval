"""Reproduce original licensed exports and audit the narrative against calculations."""

import importlib.util
import json
from pathlib import Path
from statistics import mean
import unittest

from sharpeval import analyze, load_input
from sharpeval.csv_import import import_csv


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "repeated-csv"
spec = importlib.util.spec_from_file_location("synthetic_case_generator", EXAMPLE / "generate.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class CaseStudyTests(unittest.TestCase):
    def test_committed_exports_reproduce_from_original_stdlib_generator(self):
        for name, content in generator.case_files().items():
            with self.subTest(name=name):
                self.assertEqual((EXAMPLE / name).read_bytes(), content.encode("utf-8"))
        provenance = load_input(EXAMPLE / "provenance.json")
        self.assertFalse(provenance["third_party_data"])
        self.assertFalse(provenance["prospective_evaluation"])
        self.assertFalse(provenance["real_agent_execution"])

    def test_export_report_equivalence_and_narrative_arithmetic(self):
        d = import_csv(EXAMPLE / "returns.csv", load_input(EXAMPLE / "metadata.json"))
        self.assertEqual(d, generator.build_case())
        self.assertEqual(d["versions"]["new"], "selected-variant-13")
        report = analyze(d, resamples=1000, block_length=6, seed=42)
        self.assertEqual(report["coverage"]["complete_pairs"], 6)
        expected_net = [-0.0002664142746, -0.0005375663789805554]
        for i, window in enumerate(report["windows"]):
            gross, costs = {}, {}
            for role in ("old", "new"):
                rows = [o for r in d["runs"] if r["window_id"] == window["window_id"] and r["version"] == d["versions"][role]
                        for o in r["history"]["observations"]]
                gross[role] = mean(o["return"] for o in rows)
                costs[role] = mean(o["cost"] for o in rows)
            self.assertGreater(gross["new"] - gross["old"], 0)
            delta = gross["new"] - gross["old"] - (costs["new"] - costs["old"])
            self.assertAlmostEqual(delta, expected_net[i])
            aggregate = window["aggregate"]
            self.assertEqual(aggregate["distinct_market_periods"], 120)
            comparison = aggregate["comparison"]
            self.assertAlmostEqual(comparison["comparison"]["observed_change"]["mean_return"], delta)
            interval = comparison["uncertainty"]["primary"]["contrasts"]["new_minus_old"]["mean_return"]
            self.assertLess(interval["lower"], 0)
            self.assertGreater(interval["upper"], 0)
        target = report["selection"]["targets"][0]
        self.assertEqual(target["search"]["observed_trial_count"], 40)
        self.assertEqual(len(target["search"]["trial_sharpes"]), 40)
        self.assertIsNone(target["search"]["effective_independent_trials"])
        self.assertEqual(target["dsr"]["status"], "unavailable")
        self.assertAlmostEqual(target["psr"]["value"], 0.6892344234201228, places=10)
        self.assertIsNone(report["aggregate"]["pooled_statistics"])

    def test_incomplete_case_keeps_planned_failures_and_withholds_window(self):
        document = import_csv(EXAMPLE / "incomplete-returns.csv", load_input(EXAMPLE / "incomplete-metadata.json"))
        report = analyze(document, resamples=200, block_length=6, seed=42)
        self.assertEqual(report["coverage"], {"planned_runs": 12, "completed_runs": 10, "failed_runs": 1,
                                              "missing_runs": 1, "planned_pairs": 6, "complete_pairs": 5})
        self.assertEqual(report["windows"][1]["aggregate"]["status"], "unavailable")
        self.assertIsNone(report["windows"][1]["aggregate"]["comparison"])
        missing = [r for r in report["runs"] if r["status"] == "missing"]
        self.assertEqual(missing[0]["run_id"], "audit-replay-execution-c-new")


if __name__ == "__main__":
    unittest.main()
