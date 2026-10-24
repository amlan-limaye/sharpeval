"""Practical CLI without services, credentials, packages or subscriptions."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from . import __version__
from .api import analyze, validate
from .csv_import import import_csv
from .experiment_fixtures import EXPERIMENT_SCENARIOS, make_experiment_fixture
from .fixtures import SCENARIOS, make_fixture
from .report import render_html
from .validation import InputError, align, load_input
from .cohort import rank_cohort
from .cohort_fixtures import make_cohort_fixture
from .cohort_report import render_cohort_html


def write_files(files, force=False):
    # Preflight all paths before writing either report. Each replacement is atomic.
    for path in files:
        if path.is_symlink() or path.is_dir():
            raise InputError(f"refusing to replace symlink/directory: {path}")
        if path.exists() and not force:
            raise InputError(f"output exists: {path}; use --force to replace generated files")
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                             prefix=".agent-edge-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def build_parser():
    parser = argparse.ArgumentParser(prog="sharpeval", description="Rank frozen cohorts with conditional evidence, or compare local agent versions and fixed portfolio additions. No skill certification.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    cohort = commands.add_parser("fixture-cohort", help="generate a controlled synthetic ranking input (schema 3)")
    cohort.add_argument("--periods", type=int, default=252)
    cohort.add_argument("--seed", type=int, default=20261022)
    cohort.add_argument("--out", type=Path, required=True)
    cohort.add_argument("--force", action="store_true")
    rank = commands.add_parser("rank", help="rank a frozen cohort using conditional PSR and Holm; no skill probability")
    rank.add_argument("input", type=Path)
    rank.add_argument("--output", type=Path, required=True)
    rank.add_argument("--force", action="store_true")
    fixture = commands.add_parser("fixture", help="generate a reproducible, clearly synthetic input")
    fixture.add_argument("--scenario", choices=SCENARIOS, default="complementary")
    fixture.add_argument("--periods", type=int, default=252)
    fixture.add_argument("--seed", type=int, default=20261021)
    fixture.add_argument("--out", type=Path, required=True)
    fixture.add_argument("--force", action="store_true")
    runs = commands.add_parser("fixture-runs", help="generate an explicit synthetic repeated-run experiment (schema 2)")
    runs.add_argument("--scenario", choices=EXPERIMENT_SCENARIOS, default="repeated")
    runs.add_argument("--periods", type=int, default=120)
    runs.add_argument("--seed", type=int, default=20261021)
    runs.add_argument("--out", type=Path, required=True)
    runs.add_argument("--force", action="store_true")
    check = commands.add_parser("validate", help="validate the schema, costs, chronology and alignment")
    check.add_argument("input", type=Path)
    check.add_argument("--alignment", choices=("strict", "intersection"), default="strict")
    importer = commands.add_parser("import-csv", help="validate CSV observations plus explicit schema-1 or schema-2 metadata")
    importer.add_argument("input", type=Path, help="UTF-8 CSV with series identity (schema 1) or run/window/seed/version identities (schema 2), timestamp,return,cost")
    importer.add_argument("--metadata", type=Path, required=True, help="JSON with candidate observations omitted; calendars, statuses and search metadata remain explicit")
    importer.add_argument("--out", type=Path, required=True)
    importer.add_argument("--force", action="store_true")
    compare = commands.add_parser("compare", help="write report.json and a self-contained report.html")
    compare.add_argument("input", type=Path)
    compare.add_argument("--output", type=Path, required=True)
    compare.add_argument("--alignment", choices=("strict", "intersection"), default="strict")
    compare.add_argument("--block-length", type=int, default=None, help="time-block length (>=2); default cube-root heuristic, always reported")
    compare.add_argument("--resamples", type=int, default=2000)
    compare.add_argument("--seed", type=int, default=42)
    compare.add_argument("--confidence", type=float, default=0.95)
    compare.add_argument("--force", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "fixture-cohort":
            document = make_cohort_fixture(args.periods, args.seed)
            write_files({args.out: json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"}, args.force)
            print(f"SYNTHETIC cohort written: {args.out}; no real-world skill claim.")
            return 0
        if args.command in ("fixture", "fixture-runs"):
            document = (make_fixture if args.command == "fixture" else make_experiment_fixture)(args.scenario, args.periods, args.seed)
            write_files({args.out: json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"}, args.force)
            print(f"SYNTHETIC fixture written: {args.out}")
            return 0
        if args.command == "import-csv":
            if args.out.resolve() in (args.input.resolve(), args.metadata.resolve()):
                raise InputError("output would overwrite an input (CSV or metadata)")
            document = import_csv(args.input, load_input(args.metadata))
            content = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
            if len(content.encode("utf-8")) > 25_000_000:
                raise InputError("converted JSON exceeds the 25 MB input limit; reduce the input size")
            write_files({args.out: content}, args.force)
            if document["schema_version"] == 2:
                count = sum(len(run["history"]["observations"]) for run in document["runs"] if run["status"] == "completed")
                planned = 2 * len(document["seed_ids"]) * len(document["windows"])
                print(f"Validated {count} CSV observations; {len(document['runs'])} explicit records / {planned} planned runs.")
                print("Failed/missing records and search metadata preserved; absent cells remain missing. Strict window alignment.")
            else:
                count = sum(len(history["observations"]) for history in document["series"])
                print(f"Validated {count} CSV observations in {len(document['series'])} histories; strict calendar alignment.")
            print(f"JSON: {args.out.resolve()}")
            if document["synthetic"]:
                print("SYNTHETIC: this example is not evidence of real-world alpha.")
            return 0
        document = load_input(args.input)
        if args.command == "rank":
            json_path, html_path = args.output / "report.json", args.output / "report.html"
            if args.input.resolve() in (json_path.resolve(), html_path.resolve()):
                raise InputError("output would overwrite the input")
            result = rank_cohort(document)
            write_files({json_path: json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                         html_path: render_cohort_html(result)}, args.force)
            print(f"Cohort: {result['family_size']} registered agents; {result['coverage']['scored_agents']} scored; all family slots retained.")
            print("Score = 100*(1-Holm p), conditional on declared assumptions; not a probability of skill.")
            print(f"JSON: {json_path.resolve()}\nHTML: {html_path.resolve()}")
            return 0
        if args.command == "validate":
            data = validate(document)
            if document["schema_version"] == 3:
                if args.alignment != "strict":
                    raise InputError("schema 3 requires strict alignment")
                print(f"Valid schema-3 cohort: {len(data['agents'])} registered agents; {len(data['runs'])} planned cells; no scoring implied.")
                return 0
            if document["schema_version"] == 2:
                if args.alignment != "strict":
                    raise InputError("schema 2 requires strict alignment")
                planned = 2 * len(document["seed_ids"]) * len(document["windows"])
                print(f"Valid schema-2 matrix: {planned} planned runs; {len(document['runs'])} explicit records; absent cells remain missing.")
                return 0
            _, info = align(data, args.alignment)
            sources = {data.histories[sid].source_type for sid in (data.old, data.new)}
            if len(sources) != 1:
                raise InputError("compared versions have incompatible source types")
            print(f"Valid: {len(data.histories)} histories; {info['periods']} common periods; alignment={args.alignment}.")
            return 0
        if document.get("schema_version") == 3:
            raise InputError("use rank for schema 3; compare preserves the schema-1/2 contracts")
        json_path, html_path = args.output / "report.json", args.output / "report.html"
        if args.input.resolve() in (json_path.resolve(), html_path.resolve()):
            raise InputError("output would overwrite the input")
        for path in (json_path, html_path):
            if path.exists() and not args.force:
                raise InputError(f"output exists: {path}; use --force to replace generated files")
        result = analyze(document, alignment=args.alignment, block_length=args.block_length,
                         resamples=args.resamples, seed=args.seed, confidence=args.confidence)
        files = {json_path: json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                 html_path: render_html(result)}
        write_files(files, args.force)
        if result["schema_version"] == 2:
            coverage = result["coverage"]
            print(f"Compared {coverage['complete_pairs']}/{coverage['planned_pairs']} complete pairs across {len(result['windows'])} windows.")
            print(f"Failed runs: {coverage['failed_runs']}; missing runs: {coverage['missing_runs']}. No pooled across-window inference.")
            print("PSR/DSR are conditional diagnostics when supported; no posterior skill probability or certification.")
            if result["synthetic"]:
                print("SYNTHETIC: this example is not evidence of real-world alpha.")
            print(f"JSON: {json_path.resolve()}\nHTML: {html_path.resolve()}")
            return 0
        comp = result["comparison"]
        primary = result["uncertainty"]["primary"]
        print(f"Compared {comp['new']} against {comp['old']} over {result['alignment']['periods']} aligned periods.")
        print(f"Observed average net change: {comp['observed_change']['mean_return'] * 10000:+.3f} bp/period.")
        print(f"Block uncertainty: {primary['status']}; seed={args.seed}; no selection correction or skill verdict.")
        if result["synthetic"]:
            print("SYNTHETIC: this example is not evidence of real-world alpha.")
        print(f"JSON: {json_path.resolve()}\nHTML: {html_path.resolve()}")
        return 0
    except (InputError, OSError, OverflowError, RecursionError) as exc:
        print(f"sharpeval: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
