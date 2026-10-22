import copy
import csv
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sharpeval import InputError, analyze, load_input
from sharpeval.csv_import import import_csv
from sharpeval.fixtures import make_fixture


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "csv"


class CSVImportTests(unittest.TestCase):
    def setUp(self):
        self.metadata = load_input(EXAMPLE / "metadata.json")
        self.csv = (EXAMPLE / "returns.csv").read_text(encoding="utf-8")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "returns.csv"

    def read(self, content=None, metadata=None):
        self.path.write_text(self.csv if content is None else content, encoding="utf-8", newline="")
        return import_csv(self.path, self.metadata if metadata is None else metadata)

    def test_hand_calculated_costed_example_and_no_metadata_mutation(self):
        before = copy.deepcopy(self.metadata)
        d = self.read()
        r = analyze(d, resamples=200, block_length=4, seed=42)
        self.assertEqual(self.metadata, before)
        self.assertTrue(d["synthetic"])
        self.assertEqual(r["alignment"]["periods"], 24)
        self.assertAlmostEqual(r["comparison"]["observed_change"]["mean_return"], 0.00075)
        self.assertAlmostEqual(r["series"]["agent-v1"]["metrics"]["mean_return"], -0.00225)
        self.assertAlmostEqual(r["series"]["agent-v2"]["metrics"]["mean_return"], -0.0015)
        self.assertAlmostEqual(r["series"]["agent-v1"]["metrics"]["total_return"],
                               (1.009 * 0.979 * 1.004 * 0.999) ** 6 - 1)
        self.assertAlmostEqual(r["series"]["agent-v2"]["metrics"]["total_return"],
                               (1.011 * 0.981 * 1.002 * 1.0) ** 6 - 1)
        self.assertEqual(r["uncertainty"]["primary"]["status"], "available")

    def test_net_unknown_cost_is_not_zero_or_double_deducted(self):
        self.metadata["series"][0]["return_basis"] = "net"
        d = self.read(self.csv.replace("0.010,0.001", "0.010,null"))
        r = analyze(d, resamples=200)
        self.assertIsNone(d["series"][0]["observations"][0]["cost"])
        self.assertEqual(r["series"]["agent-v1"]["net_returns"][0], 0.01)
        self.assertIsNone(r["series"]["agent-v1"]["cost_accounting"]["gross_total_return"])

    def test_invalid_values_have_csv_line_and_field(self):
        for value in ("", "NaN", "Infinity", "1e9999", "1%", "=1/100", "1_000", " 0.01"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(InputError, r"CSV line 2.return"):
                    self.read(self.csv.replace("0.010,0.001", value + ",0.001", 1))
        with self.assertRaisesRegex(InputError, r"CSV line 2.cost"):
            self.read(self.csv.replace("0.010,0.001", "0.010,", 1))

    def test_core_contract_errors_retain_csv_locations(self):
        for replacement, reason in (("0.010,null", "gross returns require"),
                                    ("0.010,-0.001", "nonnegative"),
                                    ("-1.1,0.001", "simple return range")):
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(InputError, r"CSV line 2: agent-v1.observations\[0\].*" + reason):
                    self.read(self.csv.replace("0.010,0.001", replacement, 1))

    def test_missing_session_identifies_history_and_expected_timestamp(self):
        lines = self.csv.splitlines()
        del lines[11]  # agent-v1 on January 6, while the independent calendar remains intact
        with self.assertRaisesRegex(InputError, r"agent-v1: strict alignment has 1 missing periods \(2025-01-06T00:00:00Z\)"):
            self.read("\n".join(lines) + "\n")

    def test_order_duplicate_and_unknown_id_are_not_repaired(self):
        lines = self.csv.splitlines()
        for body, message in (([lines[0], lines[1], lines[1]] + lines[2:], "duplicate or unordered"),
                              ([lines[0], lines[3], lines[1]] + lines[2:], "duplicate or unordered")):
            with self.subTest(message=message):
                with self.assertRaisesRegex(InputError, message):
                    self.read("\n".join(body))
        with self.assertRaisesRegex(InputError, "CSV line 2.series_id: unknown series"):
            self.read(self.csv.replace("agent-v1,", "typo-v1,", 1))
        with self.assertRaisesRegex(InputError, "CSV line 2.timestamp: use an explicit UTC"):
            self.read(self.csv.replace("2025-01-01T00:00:00Z", "2025-01-01", 1))

    def test_malformed_csv_does_not_silently_drop_columns_or_rows(self):
        cases = [("", "CSV line 1"),
                 (self.csv.replace("return,cost", "return,return", 1), "duplicate column"),
                 (self.csv.replace("annotation", "unexpected", 1), "columns must be"),
                 (self.csv + "\n", "blank rows are invalid"),
                 (self.csv.replace("0.010,0.001", "0.010,0.001,extra", 1), "expected 5 columns"),
                 (self.csv + '"unterminated', "CSV near line")]
        for body, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(InputError, message):
                    self.read(body)

    def test_bom_crlf_reordered_columns_and_quoted_annotation(self):
        rows = list(csv.DictReader(io.StringIO(self.csv)))
        content = io.StringIO(newline="")
        columns = ["annotation", "cost", "timestamp", "return", "series_id"]
        writer = csv.DictWriter(content, fieldnames=columns, lineterminator="\r\n")
        writer.writeheader()
        rows[0]["annotation"] = 'Synthetic, "quoted"\nsecond line'
        writer.writerows(rows)
        d = self.read("\ufeff" + content.getvalue())
        self.assertEqual(d["series"][0]["observations"][0]["annotation"], rows[0]["annotation"])

    def test_metadata_is_explicit_and_schema_one_only(self):
        cases = []
        for schema in (2, True):
            d = copy.deepcopy(self.metadata)
            d["schema_version"] = schema
            cases.append((d, "metadata.schema_version"))
        d = copy.deepcopy(self.metadata)
        d["series"][0]["observations"] = []
        cases.append((d, "observations belong in the CSV"))
        d = copy.deepcopy(self.metadata)
        d["series"][1]["id"] = d["series"][0]["id"]
        cases.append((d, "duplicate series id"))
        d = copy.deepcopy(self.metadata)
        del d["calendar"]
        cases.append((d, "missing fields: calendar"))
        for metadata, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(InputError, message):
                    self.read(metadata=metadata)

    def test_benchmark_and_portfolio_import_use_existing_contract(self):
        d = make_fixture(periods=24)
        metadata = copy.deepcopy(d)
        content = io.StringIO(newline="")
        writer = csv.DictWriter(content, fieldnames=["series_id", "timestamp", "return", "cost", "annotation"])
        writer.writeheader()
        for history in metadata["series"]:
            for record in history.pop("observations"):
                writer.writerow({"series_id": history["id"], **record})
        imported = self.read(content.getvalue(), metadata)
        self.assertEqual(imported, d)


class CSVCLITests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "sharpeval", *map(str, args)], cwd=ROOT,
                              capture_output=True, text=True, timeout=30)

    def test_import_validate_compare_and_reproduce(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "input.json"
            args = ["import-csv", EXAMPLE / "returns.csv", "--metadata", EXAMPLE / "metadata.json", "--out", out]
            result = self.cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("48 CSV observations", result.stdout)
            before = out.read_bytes()
            self.assertEqual(self.cli(*args).returncode, 2)
            self.assertEqual(self.cli(*args, "--force").returncode, 0)
            self.assertEqual(out.read_bytes(), before)
            self.assertEqual(self.cli("validate", out).returncode, 0)
            compare = ["compare", out, "--output", root / "report", "--resamples", 200, "--block-length", 4, "--seed", 42]
            self.assertEqual(self.cli(*compare).returncode, 0)
            reports = {p.name: p.read_bytes() for p in (root / "report").iterdir()}
            self.assertEqual(self.cli(*compare, "--force").returncode, 0)
            self.assertEqual(reports, {p.name: p.read_bytes() for p in (root / "report").iterdir()})

    def test_bad_csv_never_creates_output_and_inputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, metadata, output = root / "returns.csv", root / "metadata.json", root / "out.json"
            source.write_bytes((EXAMPLE / "returns.csv").read_bytes())
            metadata.write_bytes((EXAMPLE / "metadata.json").read_bytes())
            for target in (source, metadata):
                before = target.read_bytes()
                result = self.cli("import-csv", source, "--metadata", metadata, "--out", target, "--force")
                self.assertEqual(result.returncode, 2)
                self.assertIn("overwrite an input", result.stderr)
                self.assertEqual(target.read_bytes(), before)
            source.write_text(source.read_text().replace("0.010,0.001", "0.010,", 1))
            result = self.cli("import-csv", source, "--metadata", metadata, "--out", output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("CSV line 2.cost", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(output.exists())

    def test_oversized_json_integer_is_documented_cli_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bad.json"
            source.write_text('{"schema_version":' + '9' * 5000 + '}')
            for args in (["validate", source], ["compare", source, "--output", root / "report"]):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("invalid JSON", result.stderr)
            self.assertFalse((root / "report").exists())
            with self.assertRaises(InputError):
                load_input(source)


if __name__ == "__main__":
    unittest.main()
