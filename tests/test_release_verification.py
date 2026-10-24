"""The fixture release gate accepts only exact, reviewed platform outputs."""

import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

from sharpeval.cohort_fixtures import make_cohort_fixture
from tools.verify_release import verify_cohort_fixture


FROZEN = Path(__file__).resolve().parents[1] / "examples/cohort/example.json"


def encode(document):
    return (json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


class CohortFixtureReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.actual = Path(self.temporary.name) / "actual.json"
        self.frozen = Path(self.temporary.name) / "frozen.json"
        self.frozen.write_bytes(FROZEN.read_bytes())

    def test_original_frozen_record_is_accepted_without_platform_exception(self):
        self.actual.write_bytes(FROZEN.read_bytes())
        for name in ("darwin", "linux", "win32", "unreviewed-platform"):
            with self.subTest(platform=name):
                verify_cohort_fixture(self.actual, self.frozen, platform_name=name)

    @unittest.skipUnless(sys.platform in ("darwin", "linux"), "platform fingerprint has not been reviewed")
    def test_unchanged_generator_matches_reviewed_platform_output(self):
        first = encode(make_cohort_fixture())
        self.assertEqual(first, encode(make_cohort_fixture()))
        self.actual.write_bytes(first)
        verify_cohort_fixture(self.actual, self.frozen)

    @unittest.skipUnless(sys.platform == "linux", "requires the reviewed Linux math output")
    def test_linux_exception_is_not_accepted_on_unreviewed_platform(self):
        self.actual.write_bytes(encode(make_cohort_fixture()))
        self.assertNotEqual(self.actual.read_bytes(), self.frozen.read_bytes())
        with self.assertRaisesRegex(ValueError, "platform=win32"):
            verify_cohort_fixture(self.actual, self.frozen, platform_name="win32")

    def test_even_one_ulp_of_unreviewed_numeric_drift_is_rejected(self):
        document = json.loads(self.frozen.read_bytes())
        row = document["runs"][0]["observations"][0]
        row["return"] = math.nextafter(row["return"], math.inf)
        self.actual.write_bytes(encode(document))
        for name in ("darwin", "linux", "win32"):
            with self.subTest(platform=name), self.assertRaises(ValueError):
                verify_cohort_fixture(self.actual, self.frozen, platform_name=name)

    def test_changed_identity_or_structure_is_rejected(self):
        for change in ("identity", "missing-run"):
            document = json.loads(self.frozen.read_bytes())
            if change == "identity":
                document["cohort_id"] += "-changed"
            else:
                document["runs"].pop()
            self.actual.write_bytes(encode(document))
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_cohort_fixture(self.actual, self.frozen, platform_name="linux")

    def test_replacing_frozen_and_actual_together_does_not_refresh_expectation(self):
        document = json.loads(self.frozen.read_bytes())
        document["title"] += " changed"
        changed = encode(document)
        self.frozen.write_bytes(changed)
        self.actual.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "changed from the frozen record"):
            verify_cohort_fixture(self.actual, self.frozen, platform_name="linux")

    def test_failure_reports_actual_fingerprint_and_retains_gate(self):
        self.actual.write_bytes(b"unreviewed output\n")
        fingerprint = hashlib.sha256(self.actual.read_bytes()).hexdigest()
        with self.assertRaises(ValueError) as failure:
            verify_cohort_fixture(self.actual, self.frozen, platform_name="win32")
        self.assertIn("actual_sha256=" + fingerprint, str(failure.exception))
        self.assertIn("platform=win32", str(failure.exception))


if __name__ == "__main__":
    unittest.main()
