"""Verify built distributions offline, with clean installs outside the checkout.

Run with the already declared setuptools backend installed. No network, build
frontend, third-party test tool, credentials or platform-specific shell is needed.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_source(archive, destination):
    # Avoid version-dependent tar extraction defaults, links and path traversal.
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"unexpected source archive member: {member.name}")
            target = destination.joinpath(*path.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError(f"source archive path escapes extraction directory: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("source archive must contain one project directory")
    return roots[0]


def verify(artifacts):
    wheels, sources = list(artifacts.glob("*.whl")), list(artifacts.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("artifacts must contain exactly one wheel and one source distribution; use a clean build directory")
    evidence = {"python": sys.version, "platform": sys.platform, "artifacts": {
        p.name: digest(p) for p in (wheels[0], sources[0])}, "commands": [], "installs": []}
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    env.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_CACHE_DIR="1", PYTHONUTF8="1")
    with tempfile.TemporaryDirectory(prefix="sharpeval-release-") as temporary:
        root = Path(temporary).resolve()
        outside = root / "outside-checkout"
        outside.mkdir()
        def run(args, cwd=outside):
            args = [str(a) for a in args]
            process = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
            evidence["commands"].append({"argv": args, "cwd": str(cwd), "exit": process.returncode,
                                         "stdout": process.stdout, "stderr": process.stderr})
            if process.returncode:
                raise RuntimeError(f"command failed: {args}\n{process.stdout}\n{process.stderr}")
            return process.stdout

        source = extract_source(sources[0], root / "source")
        project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        if project["dependencies"]:
            raise ValueError("unexpected runtime dependencies")
        for name in ("docs/csv-experiments.md", "docs/case-study.md", "examples/repeated-csv/generate.py",
                     "examples/repeated-csv/returns.csv", "examples/repeated-csv/metadata.json", "tests/test_csv_experiments.py"):
            if not (source / name).is_file():
                raise ValueError(f"source distribution omitted {name}")
        with zipfile.ZipFile(wheels[0]) as wheel:
            licenses = [name for name in wheel.namelist() if name.endswith("/LICENSE")]
            if not licenses or wheel.read(licenses[0]) != (source / "LICENSE").read_bytes():
                raise ValueError("wheel license is missing or inconsistent")

        # Rebuild the source distribution using only the caller's existing backend.
        rebuilt = root / "rebuilt"
        run([sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps", "--no-build-isolation",
             "--wheel-dir", rebuilt, source])
        rebuilt_wheels = list(rebuilt.glob("*.whl"))
        if len(rebuilt_wheels) != 1:
            raise ValueError("source build did not produce exactly one wheel")
        shared_hashes = None
        for label, wheel in (("wheel", wheels[0]), ("sdist", rebuilt_wheels[0])):
            environment = root / f"{label}-environment"
            venv.EnvBuilder(with_pip=True).create(environment)
            bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
            python = bin_dir / ("python.exe" if os.name == "nt" else "python")
            cli = bin_dir / ("sharpeval.exe" if os.name == "nt" else "sharpeval")
            run([python, "-m", "pip", "install", "--no-index", "--no-deps", wheel])
            installed = json.loads(run([python, "-c", "import json,sharpeval; print(json.dumps([sharpeval.__version__,sharpeval.__file__]))"]))
            if installed[0] != project["version"] or not Path(installed[1]).resolve().is_relative_to(environment):
                raise ValueError(f"import did not use the clean installed package: {installed}")
            work = outside / label
            work.mkdir()
            run([cli, "fixture", "--periods", "24", "--out", work / "fixture.json"])
            run([cli, "validate", work / "fixture.json"])
            run([cli, "compare", work / "fixture.json", "--output", work / "fixture-report", "--resamples", "200", "--seed", "42"])
            hashes = {}
            for case, location, metadata_name, returns_name in (
                    ("single", "csv", "metadata.json", "returns.csv"),
                    ("repeated", "repeated-csv", "metadata.json", "returns.csv"),
                    ("incomplete", "repeated-csv", "incomplete-metadata.json", "incomplete-returns.csv")):
                example = source / "examples" / location
                document = work / f"{case}.json"
                report_dir = work / f"{case}-report"
                run([cli, "import-csv", example / returns_name, "--metadata", example / metadata_name, "--out", document])
                run([cli, "validate", document])
                settings = ["--block-length", "6" if case != "single" else "4", "--resamples", "1000" if case == "repeated" else "200", "--seed", "42"]
                command = [cli, "compare", document, "--output", report_dir, *settings]
                run(command)
                first = {name: digest(report_dir / name) for name in ("report.json", "report.html")}
                run([*command, "--force"])
                if first != {name: digest(report_dir / name) for name in first}:
                    raise ValueError("fixed-seed report is not byte reproducible")
                hashes[case] = first
                report = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
                if case == "single":
                    if not math.isclose(report["comparison"]["observed_change"]["mean_return"], 0.00075):
                        raise ValueError("single-pair arithmetic changed")
                elif case == "repeated":
                    if report["coverage"]["complete_pairs"] != 6 or report["selection"]["targets"][0]["dsr"]["status"] != "unavailable":
                        raise ValueError("repeated case coverage/search contract changed")
                    change = report["windows"][0]["aggregate"]["comparison"]["comparison"]["observed_change"]["mean_return"]
                    if not math.isclose(change, -0.0002664142746, abs_tol=1e-14):
                        raise ValueError("case-study net arithmetic changed")
                else:
                    if report["coverage"]["failed_runs"] != 1 or report["coverage"]["missing_runs"] != 1:
                        raise ValueError("explicit failure/missing records were lost")
                    if report["windows"][1]["aggregate"]["status"] != "unavailable":
                        raise ValueError("incomplete window unexpectedly received an aggregate")
            if shared_hashes is not None and hashes != shared_hashes:
                raise ValueError("wheel and source-distribution reports differ")
            shared_hashes = hashes
            evidence["installs"].append({"kind": label, "version": installed[0], "installed_module": installed[1],
                                         "reports": hashes, "network_index_disabled": True})
        evidence["status"] = "passed"
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.artifacts.resolve())
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Passed: wheel and sdist clean installs outside checkout; schema-1, schema-2 and incomplete CSV examples; reproducible JSON/HTML. No package index used.")


if __name__ == "__main__":
    main()
