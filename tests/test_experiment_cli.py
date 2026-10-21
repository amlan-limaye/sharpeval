from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sharpeval import analyze
from sharpeval.experiment_fixtures import make_experiment_fixture
from sharpeval.report import render_html

ROOT = Path(__file__).resolve().parents[1]


class OfflineStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.sections, self.charts = [], [], 0, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "iframe", "img", "link", "object", "embed", "audio", "video"):
            self.errors.append("Unexpected active or resource tag " + tag)
        if tag not in ("meta", "br", "hr", "input"):
            self.stack.append(tag)
        self.sections += tag == "section"
        self.charts += tag == "svg"
        if any(key.startswith("on") for key, _ in attrs):
            self.errors.append("Unexpected inline event handler")

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.errors.append("Unbalanced end tag " + tag)


class ExperimentCLITests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "sharpeval", *map(str, args)], cwd=ROOT,
                              capture_output=True, text=True, timeout=45)

    def test_cli_generates_validates_compares_and_reproduces_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "runs.json", root / "report"
            created = self.cli("fixture-runs", "--periods", 40, "--out", source)
            self.assertEqual(created.returncode, 0, created.stderr)
            checked = self.cli("validate", source)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("12 planned runs", checked.stdout)
            self.assertEqual(self.cli("validate", source, "--alignment", "intersection").returncode, 2)
            args = ["compare", source, "--output", destination, "--resamples", 200, "--block-length", 4, "--seed", 19]
            compared = self.cli(*args)
            self.assertEqual(compared.returncode, 0, compared.stderr)
            self.assertIn("6/6 complete pairs", compared.stdout)
            self.assertIn("SYNTHETIC", compared.stdout)
            before = {p.name: p.read_bytes() for p in destination.iterdir()}
            r = json.loads(before["report.json"])
            self.assertEqual(r["tool"]["version"], "0.2.0")
            self.assertEqual(r["analysis_settings"]["seed"], 19)
            self.assertEqual(r["schema_version"], 2)
            self.assertEqual(self.cli(*args).returncode, 2)
            self.assertEqual(self.cli(*args, "--force").returncode, 0)
            self.assertEqual(before, {p.name: p.read_bytes() for p in destination.iterdir()})
            parsed = OfflineStructure()
            parsed.feed(before["report.html"].decode())
            self.assertEqual(parsed.errors, [])
            self.assertEqual(parsed.stack, [])
            self.assertEqual(parsed.sections, 4)
            self.assertEqual(parsed.charts, 2)

    def test_missing_runs_are_visible_in_cli_json_and_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "missing.json"
            self.assertEqual(self.cli("fixture-runs", "--scenario", "missing-runs", "--periods", 20, "--out", source).returncode, 0)
            result = self.cli("compare", source, "--output", root / "report", "--resamples", 200, "--block-length", 8)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Failed runs: 1; missing runs: 1", result.stdout)
            html = (root / "report" / "report.html").read_text()
            self.assertIn("Window aggregate unavailable", html)
            self.assertIn("Planned run was not supplied", html)
            self.assertIn("this block length needs at least", html)
            self.assertIn("survivor-biased", html)
            self.assertIn("ratio", html)
            parsed = OfflineStructure()
            parsed.feed(html)
            self.assertEqual(parsed.errors, [])
            self.assertEqual(parsed.stack, [])

    def test_report_escapes_imported_title_seed_cost_and_failure_text(self):
        d = make_experiment_fixture("missing-runs", periods=20)
        d["title"] = '<script>alert("title")</script>'
        for r in d["runs"]:
            if r["status"] == "failed":
                r["reason"] = '<img src=x onerror=bad()>'
            else:
                r["history"]["costs"]["notes"] = '<iframe>costs</iframe>'
        d["selection"][0]["notes"] = '<script>notes</script>'
        html = render_html(analyze(d, resamples=200, block_length=4))
        for prohibited in ("<script", "<img", "<iframe"):
            self.assertNotIn(prohibited, html)
        for escaped in ("&lt;script", "&lt;img", "&lt;iframe"):
            self.assertIn(escaped, html)
        self.assertIn("Content-Security-Policy", html)


if __name__ == "__main__":
    unittest.main()
