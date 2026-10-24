from copy import deepcopy
import json
import hashlib
from pathlib import Path
import unittest

from tools.calibrate_cohort import calibrate, validate_protocol, wilson
from sharpeval.validation import InputError

ROOT = Path(__file__).resolve().parents[1]


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((ROOT/"examples/cohort/calibration-protocol.json").read_text())

    def test_wilson_reference_values_and_empty_denominator(self):
        self.assertEqual(wilson(0, 0)["wilson_95"], None)
        self.assertAlmostEqual(wilson(0, 100)["wilson_95"][1], 0.03699349820698568)
        self.assertAlmostEqual(wilson(50, 100)["wilson_95"][0], 0.4038315303659956)
        self.assertAlmostEqual(wilson(100, 100)["wilson_95"][0], 0.9630065017930143)

    def test_small_smoke_retains_all_seeds_and_stress_abstentions(self):
        # Distinct test worlds; the frozen 1,600-world run is a separate artifact.
        for index, case in enumerate(self.protocol["scenarios"]):
            case.update(worlds=2, seed_start=880000+index*10)
        result = calibrate(self.protocol)
        self.assertEqual([c["completed_worlds"] for c in result["scenarios"]], [2]*5)
        for case in result["scenarios"]:
            self.assertEqual(len(case["worlds"]), 2)
            self.assertEqual(case["familywise_false_qualification"]["worlds"], 2)
            for agent in case["agents"].values():
                self.assertEqual(sum(agent["rank_histogram"].values()), 2)
                self.assertEqual(agent["qualification"]["worlds"], 2)
            if not case["supported"]:
                self.assertEqual(case["all_unscored_worlds"], 2)
                self.assertEqual(case["familywise_false_qualification"]["count"], 0)

    def test_protocol_mismatch_overlap_and_unsupported_relabelling_rejected(self):
        original = deepcopy(self.protocol)
        self.protocol["hurdle_sharpe_per_period"] = 0.01
        with self.assertRaises(InputError):
            validate_protocol(self.protocol)
        self.protocol = deepcopy(original)
        self.protocol["scenarios"][1]["seed_start"] = self.protocol["scenarios"][0]["seed_start"]
        with self.assertRaises(InputError):
            validate_protocol(self.protocol)
        self.protocol = deepcopy(original)
        self.protocol["scenarios"][-1]["supported"] = True
        with self.assertRaises(InputError):
            validate_protocol(self.protocol)

    def test_frozen_record_covers_every_seed_and_reports_ties_and_abstentions(self):
        path = ROOT/"examples/cohort/calibration-protocol.json"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         "59f15c6565afcbab3ce741496ab57948a75ee0f0aa91079a33d9721b10131c5d")
        record = json.loads((ROOT/"examples/cohort/calibration.json").read_text())
        self.assertEqual(record["protocol"], self.protocol)
        for name, digest in record["source_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT/(name.replace(".", "/")+".py")).read_bytes()).hexdigest(), digest)
        for planned, case in zip(self.protocol["scenarios"], record["scenarios"]):
            self.assertEqual([w["seed"] for w in case["worlds"]],
                             list(range(planned["seed_start"], planned["seed_start"]+planned["worlds"])))
            false = 0
            for world in case["worlds"]:
                self.assertEqual({a["agent_id"] for a in world["agents"]}, set(self.protocol["agent_ids"]))
                observed = any(a["evidence_qualified"] and a["population_net_sharpe"] <= 0.05 for a in world["agents"])
                self.assertEqual(world["any_false_qualification"], observed)
                false += observed
            self.assertEqual(case["familywise_false_qualification"]["count"], false)
            for summary in case["agents"].values():
                self.assertEqual(sum(summary["rank_histogram"].values()), planned["worlds"])


if __name__ == "__main__":
    unittest.main()
