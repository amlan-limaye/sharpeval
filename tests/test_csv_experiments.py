"""Independent explicit experiment versus the CSV representation; no inferred runs."""

import copy
import csv
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sharpeval import InputError, analyze
from sharpeval.csv_import import import_csv
from sharpeval.experiment_fixtures import make_experiment_fixture
from sharpeval.report import render_html


ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["run_id", "window_id", "seed_id", "version", "timestamp", "return", "cost", "annotation"]


def hand_built():
    windows = [{"window_id": wid, "timestamps": [(datetime(2025, month, 1) + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
               for i in range(24)], "notes": "Synthetic independently declared 24-session calendar."}
               for wid, month in (("development", 1), ("replay", 2))]
    runs = []
    for w in windows:
        for seed in ("a", "b"):
            for version in ("old", "new"):
                run = {"run_id": f"{w['window_id']}-{seed}-{version}", "window_id": w["window_id"],
                       "seed_id": seed, "version": version, "status": "completed"}
                if w["window_id"] == "replay":
                    if (seed, version) == ("b", "new"):
                        continue  # Planned cell remains absent, with no invented identity.
                    if (seed, version) in (("a", "new"), ("b", "old")):
                        run.update(status="failed" if seed == "a" else "missing", reason="Explicit synthetic failure/missing record.")
                        runs.append(run)
                        continue
                run["history"] = {"return_basis": "gross", "costs": {"included": ["fee"], "excluded": [],
                                   "notes": "Synthetic explicit cost."}, "observations": []}
                for i, t in enumerate(w["timestamps"]):
                    value = [0.010, -0.005, 0.000, 0.006][i % 4] + (0.001 if seed == "b" else 0) + (0.002 if version == "new" else 0)
                    run["history"]["observations"].append({"timestamp": t, "return": value,
                                                           "cost": 0.002 if version == "new" else 0.001})
                runs.append(run)
    return {"schema_version": 2, "title": "SYNTHETIC hand-built repeated CSV test", "synthetic": True,
            "agent_id": "hand-built", "versions": {"old": "old", "new": "new"}, "seed_ids": ["a", "b"],
            "evaluation": {"source_type": "backtest", "frequency_seconds": 86400, "periods_per_year": None,
                           "unit": "decimal", "currency": "USD", "cash_return_per_period": 0,
                           "notes": "Synthetic test of format equivalence only."}, "windows": windows, "runs": runs,
            "selection": [{"target_run_id": "development-a-new", "benchmark_sharpe_per_period": 0,
                           "sharpe_unit": "per_period", "assumptions": {k: "unknown" for k in (
                               "serial_independence", "stationarity", "finite_fourth_moment", "normal_trial_sharpes", "comparable_trial_sharpes")},
                           "notes": "Unknown search and dependence assumptions are deliberately retained.", "search": None}]}


def export(document):
    metadata = copy.deepcopy(document)
    rows = []
    for run in metadata["runs"]:
        if run["status"] == "completed":
            for obs in run["history"].pop("observations"):
                row = {key: run[key] for key in FIELDS[:4]}
                row.update(obs)
                row["cost"] = "null" if row["cost"] is None else row["cost"]
                rows.append(row)
    return metadata, rows


def csv_text(rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


class ExperimentCSVTests(unittest.TestCase):
    def setUp(self):
        self.hand = hand_built()
        self.metadata, self.rows = export(self.hand)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def read(self):
        path = self.root / "returns.csv"
        path.write_text(csv_text(self.rows), encoding="utf-8", newline="")
        return import_csv(path, self.metadata)

    def test_exact_equivalence_to_hand_built_document_and_reports(self):
        before = copy.deepcopy(self.metadata)
        imported = self.read()
        self.assertEqual(imported, self.hand)
        self.assertEqual(self.metadata, before)
        actual = analyze(imported, resamples=200, block_length=4, seed=42)
        expected = analyze(self.hand, resamples=200, block_length=4, seed=42)
        self.assertEqual(actual, expected)
        self.assertEqual(render_html(actual), render_html(expected))
        self.assertEqual(actual["coverage"], {"planned_runs": 8, "completed_runs": 5, "failed_runs": 1,
                                              "missing_runs": 2, "planned_pairs": 4, "complete_pairs": 2})
        change = actual["windows"][0]["aggregate"]["comparison"]["comparison"]["observed_change"]["mean_return"]
        self.assertAlmostEqual(change, 0.001)  # +0.002 gross minus +0.001 cost.
        self.assertEqual(actual["windows"][1]["aggregate"]["status"], "unavailable")
        self.assertIsNone([r for r in actual["runs"] if r["seed_id"] == "b" and r["window_id"] == "replay" and r["version"] == "new"][0]["run_id"])
        self.assertIsNone(imported["selection"][0]["search"])

    def test_csv_identity_mismatch_is_never_repaired(self):
        for key, value in (("run_id", "unknown"), ("window_id", "replay"), ("seed_id", "b"), ("version", "new")):
            with self.subTest(key=key):
                original = self.rows[0][key]
                self.rows[0][key] = value
                with self.assertRaisesRegex(InputError, f"CSV line 2.{key}"):
                    self.read()
                self.rows[0][key] = original

    def test_ambiguous_metadata_ids_and_cells_are_rejected(self):
        for key in ("run_id", "seed_id"):
            with self.subTest(key=key):
                self.metadata, self.rows = export(self.hand)
                if key == "run_id":
                    self.metadata["runs"][1][key] = self.metadata["runs"][0][key]
                else:
                    self.metadata["runs"][2][key] = "a"
                with self.assertRaisesRegex(InputError, "duplicate"):
                    self.read()

    def test_failed_and_missing_runs_cannot_hide_partial_observations(self):
        for rid in ("replay-a-new", "replay-b-old"):
            with self.subTest(rid=rid):
                self.metadata, self.rows = export(self.hand)
                run = next(r for r in self.metadata["runs"] if r["run_id"] == rid)
                self.rows[0].update({key: run[key] for key in FIELDS[:4]})
                with self.assertRaisesRegex(InputError, "cannot have CSV observations"):
                    self.read()

    def test_missing_cost_and_missing_calendar_session_have_locations(self):
        self.rows[0]["cost"] = ""
        with self.assertRaisesRegex(InputError, "CSV line 2.cost"):
            self.read()
        self.metadata, self.rows = export(self.hand)
        self.rows[0]["cost"] = "null"
        with self.assertRaisesRegex(InputError, r"CSV line 2: development-a-old.history:.*gross returns require"):
            self.read()
        self.metadata, self.rows = export(self.hand)
        del self.rows[5]
        with self.assertRaisesRegex(InputError, r"development-a-old.history:.*2025-01-06T00:00:00Z"):
            self.read()

    def test_unknown_net_costs_and_optional_annotations_round_trip(self):
        self.hand["runs"][0]["history"]["return_basis"] = "net"
        self.hand["runs"][0]["history"]["observations"][0].update(cost=None, annotation='Quoted, "context"\nsecond line')
        self.metadata, self.rows = export(self.hand)
        self.assertEqual(self.read(), self.hand)

    def test_inline_benchmark_and_portfolio_references_are_preserved(self):
        document = make_experiment_fixture(periods=24)
        self.metadata, self.rows = export(document)
        self.assertEqual(self.read(), document)

    def test_incomplete_search_ledger_is_preserved_without_invented_trials(self):
        search = {"observed_trial_count": 5, "effective_independent_trials": None, "completeness": "incomplete",
                  "dispersion_source": "observed_trial_sharpes", "trial_sharpe_std_per_period": None,
                  "trial_sharpes": [{"trial_id": "failed-attempt", "sharpe_per_period": None}],
                  "selected_trial_id": None, "null_mean_sharpe_per_period": 0,
                  "notes": "Only one of five actual attempts retained; never infer the remaining outcomes."}
        self.metadata["selection"][0]["search"] = search
        imported = self.read()
        self.assertEqual(imported["selection"][0]["search"], search)
        result = analyze(imported, resamples=200)
        self.assertEqual(result["selection"]["targets"][0]["dsr"]["status"], "unavailable")
        self.assertEqual(len(imported["selection"][0]["search"]["trial_sharpes"]), 1)

    def test_header_only_all_unobserved_matrix_remains_explicit(self):
        self.metadata["runs"] = [r for r in self.metadata["runs"] if r["status"] != "completed"]
        self.metadata["selection"] = []
        self.rows = []
        imported = self.read()
        self.assertEqual(imported, self.metadata)
        result = analyze(imported, resamples=200)
        self.assertEqual(result["coverage"]["completed_runs"], 0)
        self.assertEqual(result["coverage"]["missing_runs"], 7)

    def test_metadata_cannot_embed_completed_run_observations(self):
        self.metadata["runs"][0]["history"]["observations"] = []
        with self.assertRaisesRegex(InputError, "observations belong in the CSV"):
            self.read()

    def test_duplicate_out_of_order_and_missing_identity_columns_fail(self):
        self.rows.insert(1, copy.deepcopy(self.rows[0]))
        with self.assertRaisesRegex(InputError, "duplicate or unordered"):
            self.read()
        self.metadata, self.rows = export(self.hand)
        self.rows[0], self.rows[1] = self.rows[1], self.rows[0]
        with self.assertRaisesRegex(InputError, "duplicate or unordered"):
            self.read()
        path = self.root / "returns.csv"
        path.write_text("run_id,timestamp,return,cost\n", encoding="utf-8")
        with self.assertRaisesRegex(InputError, "schema-2 columns"):
            import_csv(path, self.metadata)

    def test_cli_import_validate_compare_and_invalid_input_safety(self):
        source, metadata, output = self.root / "returns.csv", self.root / "metadata.json", self.root / "input.json"
        source.write_text(csv_text(self.rows), encoding="utf-8")
        metadata.write_text(json.dumps(self.metadata), encoding="utf-8")
        def cli(*args):
            return subprocess.run([sys.executable, "-m", "sharpeval", *map(str, args)], cwd=ROOT,
                                  text=True, capture_output=True, timeout=30)
        args = ["import-csv", source, "--metadata", metadata, "--out", output]
        result = cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("7 explicit records / 8 planned runs", result.stdout)
        self.assertEqual(json.loads(output.read_text()), self.hand)
        self.assertEqual(cli("validate", output).returncode, 0)
        report = self.root / "report"
        self.assertEqual(cli("compare", output, "--output", report, "--resamples", 200).returncode, 0)
        before = output.read_bytes()
        self.rows[0]["seed_id"] = "unknown"
        source.write_text(csv_text(self.rows), encoding="utf-8")
        result = cli(*args, "--force")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
