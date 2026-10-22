import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sharpeval import analyze
from sharpeval.fixtures import make_fixture
from sharpeval.report import chart, render_html


ROOT = Path(__file__).resolve().parents[1]


class EndToEndTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "sharpeval", *map(str, args)], cwd=ROOT,
                              capture_output=True, text=True, timeout=45)

    def test_complete_cli_and_reproducible_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "input.json", root / "report"
            self.assertEqual(self.cli("fixture", "--periods", 40, "--out", source).returncode, 0)
            self.assertEqual(self.cli("validate", source).returncode, 0)
            args = ["compare", source, "--output", destination, "--resamples", 200, "--block-length", 4, "--seed", 44]
            first = self.cli(*args)
            self.assertEqual(first.returncode, 0, first.stderr)
            content = (destination / "report.json").read_bytes()
            r = json.loads(content)
            self.assertEqual(r["uncertainty"]["seed"], 44)
            self.assertTrue(r["synthetic"])
            self.assertIn("SYNTHETIC", first.stdout)
            html = (destination / "report.html").read_text()
            self.assertIn("Low correlation is not skill", html)
            self.assertIn("Content-Security-Policy", html)
            self.assertIn("Deflated Sharpe", html)
            self.assertEqual(self.cli(*args).returncode, 2)
            self.assertEqual(self.cli(*args, "--force").returncode, 0)
            self.assertEqual(content, (destination / "report.json").read_bytes())

    def test_bad_input_is_clean_error_without_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bad.json"
            source.write_text('{"schema_version":1,"schema_version":2}')
            result = self.cli("compare", source, "--output", root / "output")
            self.assertEqual(result.returncode, 2)
            self.assertIn("duplicate JSON key", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((root / "output").exists())

    def test_input_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            self.cli("fixture", "--periods", 8, "--out", path)
            before = path.read_bytes()
            result = self.cli("compare", path, "--output", directory, "--force")
            self.assertEqual(result.returncode, 2)
            self.assertIn("overwrite the input", result.stderr)
            self.assertEqual(path.read_bytes(), before)

    def test_symlink_output_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            self.cli("fixture", "--periods", 8, "--out", source)
            out = root / "output"
            out.mkdir()
            target = root / "target.txt"
            target.write_text("untouched")
            try:
                (out / "report.html").symlink_to(target)
            except OSError as exc:
                if sys.platform == "win32" and getattr(exc, "winerror", None) == 1314:
                    self.skipTest("Windows runner does not grant symlink creation")
                raise
            result = self.cli("compare", source, "--output", out, "--force", "--resamples", 200)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_text(), "untouched")
            self.assertFalse((out / "report.json").exists())

    def test_html_escapes_imported_content_and_loads_no_scripts(self):
        d = make_fixture(periods=8)
        d["title"] = '<script>alert("title")</script>'
        d["series"][0]["observations"][0]["annotation"] = '<img src=x onerror=alert(1)>'
        d["series"][0]["costs"]["notes"] = '</details><script>bad()</script>'
        html = render_html(analyze(d, resamples=200))
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<iframe", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)
        self.assertNotIn("<link", html)

    def test_plotting_range_is_reported_without_invalid_coordinates(self):
        html = chart([("extreme", [1.0, 1.7e308])], "Extreme finite wealth")
        self.assertIn("unavailable", html)
        self.assertNotIn("polyline", html)


if __name__ == "__main__":
    unittest.main()
