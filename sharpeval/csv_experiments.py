"""Strict schema-2 observation import; metadata owns run status and search history."""

import copy
import csv
from pathlib import Path
import re

from .csv_import import _number
from .experiments import validate_experiment
from .validation import InputError, integer, object_fields, stamp, text


def import_experiment_csv(path, metadata):
    object_fields(metadata, {"schema_version", "title", "synthetic", "agent_id", "versions",
                             "evaluation", "seed_ids", "windows", "runs"}, {"selection"}, "metadata")
    integer(metadata["schema_version"], "metadata.schema_version", 2, 2)
    document = copy.deepcopy(metadata)
    versions = document["versions"]
    object_fields(versions, {"old", "new"}, path="metadata.versions")
    for role in ("old", "new"):
        text(versions[role], f"metadata.versions.{role}", 120)
    if versions["old"] == versions["new"]:
        raise InputError("old and new version labels must differ")
    seeds = document["seed_ids"]
    if not isinstance(seeds, list) or not 1 <= len(seeds) <= 20:
        raise InputError("metadata.seed_ids must declare 1..20 planned execution identities")
    for seed in seeds:
        text(seed, "metadata.seed_id", 120)
    if len(seeds) != len(set(seeds)):
        raise InputError("duplicate seed_id")
    windows = document["windows"]
    if not isinstance(windows, list) or not 1 <= len(windows) <= 8:
        raise InputError("metadata.windows must contain 1..8 declared market windows")
    window_ids = set()
    for window in windows:
        object_fields(window, {"window_id", "timestamps", "notes"},
                      {"reference_series", "benchmark", "portfolio"}, "metadata.window")
        wid = text(window["window_id"], "metadata.window_id", 60)
        if wid in window_ids:
            raise InputError("duplicate window_id")
        window_ids.add(wid)
    runs = document["runs"]
    if not isinstance(runs, list) or len(runs) > 2 * len(seeds) * len(windows):
        raise InputError("metadata.runs must fit the declared version × seed × window matrix")
    by_id, cells = {}, set()
    for run in runs:
        object_fields(run, {"run_id", "window_id", "seed_id", "version", "status"},
                      {"history", "reason"}, "metadata.run")
        rid = text(run["run_id"], "metadata.run_id", 120)
        for key in ("window_id", "seed_id", "version"):
            text(run[key], f"{rid}.{key}", 120)
        if rid in by_id:
            raise InputError(f"duplicate run_id: {rid}")
        if run["window_id"] not in window_ids or run["seed_id"] not in seeds or run["version"] not in versions.values():
            raise InputError(f"{rid}: run is outside the declared evaluation matrix")
        cell = (run["window_id"], run["seed_id"], run["version"])
        if cell in cells:
            raise InputError("duplicate window/seed/version cell; run IDs cannot hide ambiguous pairing")
        cells.add(cell)
        by_id[rid] = run
        if run["status"] not in ("completed", "failed", "missing"):
            raise InputError(f"{rid}: run.status must be completed, failed or missing")
        if run["status"] != "completed":
            if "history" in run:
                raise InputError(f"{rid}: failed/missing runs cannot carry history")
            text(run.get("reason"), f"{rid}.reason")
        else:
            if "reason" in run:
                raise InputError(f"{rid}: completed runs use history, not a failure reason")
            object_fields(run.get("history"), {"return_basis", "costs"},
                          path=f"{rid}.history (observations belong in the CSV)")
            run["history"]["observations"] = []

    path = Path(path)
    if path.stat().st_size > 25_000_000:
        raise InputError("CSV input exceeds the 25 MB limit")
    locations = {}
    reader = None
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            required = {"run_id", "window_id", "seed_id", "version", "timestamp", "return", "cost"}
            if not header or len(header) != len(set(header)):
                raise InputError("CSV line 1: missing or duplicate column names")
            if set(header) not in (required, required | {"annotation"}):
                raise InputError("CSV line 1: schema-2 columns must be run_id,window_id,seed_id,version,timestamp,return,cost with optional annotation (any order)")
            for count, values in enumerate(reader, 1):
                label = f"CSV line {reader.line_num}"
                if count > 100_000:
                    raise InputError(f"{label}: schema 2 accepts at most 100,000 completed run observations")
                if len(values) != len(header):
                    raise InputError(f"{label}: expected {len(header)} columns, found {len(values)}; blank rows are invalid")
                row = dict(zip(header, values))
                rid = row["run_id"]
                if rid not in by_id:
                    raise InputError(f"{label}.run_id: unknown run {rid!r}; declare its identity and status in metadata")
                run = by_id[rid]
                for key in ("window_id", "seed_id", "version"):
                    if row[key] != run[key]:
                        raise InputError(f"{label}.{key}: does not match metadata for run {rid!r}; identities are never inferred")
                if run["status"] != "completed":
                    raise InputError(f"{label}: {rid} is {run['status']}; failed/missing runs cannot have CSV observations")
                records = run["history"]["observations"]
                if len(records) >= 10_000:
                    raise InputError(f"{label}: {rid} exceeds 10,000 observations")
                stamp(row["timestamp"], label + ".timestamp")
                if records and row["timestamp"] <= records[-1]["timestamp"]:
                    raise InputError(f"{label}: {rid} has a duplicate or unordered timestamp; rows are never sorted automatically")
                record = {"timestamp": row["timestamp"], "return": _number(row["return"], label + ".return"),
                          "cost": _number(row["cost"], label + ".cost", nullable=True)}
                if row.get("annotation"):
                    record["annotation"] = row["annotation"]
                locations[(rid, len(records))] = label
                records.append(record)
    except (csv.Error, UnicodeError) as exc:
        line = reader.line_num if reader is not None else 1
        raise InputError(f"CSV near line {line}: {exc}") from None
    try:
        validate_experiment(document)
    except InputError as exc:
        message = str(exc)
        for rid in by_id:
            prefix = f"{rid}.history: "
            if message.startswith(prefix):
                match = re.match(r"run-(?:old|new)\.observations\[(\d+)\]", message[len(prefix):])
                if match:
                    location = locations.get((rid, int(match.group(1))))
                    if location:
                        message = f"{location}: {message}"
                break
        raise InputError(message) from None
    return document
