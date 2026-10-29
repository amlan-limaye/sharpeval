"""CSV diagnostics must refer to physical lines, including multiline annotations."""
import copy
import csv
import io
from pathlib import Path
import tempfile
import unittest

from sharpeval import InputError, load_input
from sharpeval.csv_import import import_csv


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "csv"


class CSVErrorLocationTests(unittest.TestCase):
    def test_error_after_multiline_annotation_preserves_input_metadata(self):
        metadata = load_input(EXAMPLE / "metadata.json")
        before = copy.deepcopy(metadata)
        with (EXAMPLE / "returns.csv").open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames
            rows = list(reader)
        rows[0]["annotation"] = "first line\nsecond line"
        rows[1]["return"] = "NaN"
        content = io.StringIO(newline="")
        writer = csv.DictWriter(content, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "returns.csv"
            path.write_text(content.getvalue(), encoding="utf-8", newline="")
            with self.assertRaisesRegex(InputError, r"CSV line 4\.return:"):
                import_csv(path, metadata)
            self.assertEqual(path.read_text(encoding="utf-8"), content.getvalue())
        self.assertEqual(metadata, before)


if __name__ == "__main__":
    unittest.main()
