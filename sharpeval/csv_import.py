"""Import explicit long-form CSV observations into the existing JSON contracts."""

import copy
import csv
import math
from pathlib import Path
import re

from .validation import InputError, align, integer, object_fields, stamp, text, validate


_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def _number(value, label, *, nullable=False):
    if nullable and value == "null":
        return None
    if not _DECIMAL.fullmatch(value):
        suffix = " or literal null for an unknown net cost" if nullable else ""
        raise InputError(f"{label}: expected a decimal number{suffix}; blanks, percentages and formulas are not accepted")
    result = float(value)
    if not math.isfinite(result):
        raise InputError(f"{label}: expected a finite decimal number")
    return result


def import_csv(path, metadata):
    """Return a fully validated, strictly aligned document; write nothing.

    Metadata is a schema-1 document with observations omitted from every series.
    It supplies the expected calendar independently of the CSV. Rows may interleave
    histories but must already be chronological within each history. No sorting,
    filling, unit conversion, calendar inference or return/cost deduction occurs.
    Schema 2 uses explicit experiment/run metadata and repeated identities in CSV.
    """
    if isinstance(metadata, dict) and metadata.get("schema_version") == 2:
        from .csv_experiments import import_experiment_csv
        if "series" in metadata:
            raise InputError("metadata.schema_version=2 requires explicit experiment metadata; changing the version alone cannot migrate run identities")
        return import_experiment_csv(path, metadata)
    object_fields(metadata, {"schema_version", "title", "synthetic", "calendar",
                             "cash_return_per_period", "series", "comparison"},
                  {"benchmark", "portfolio", "search_trials"}, path="metadata")
    integer(metadata["schema_version"], "metadata.schema_version", 1, 1)
    document = copy.deepcopy(metadata)
    series = document["series"]
    if not isinstance(series, list) or not 2 <= len(series) <= 20:
        raise InputError("metadata.series must contain 2 to 20 histories")
    histories = {}
    for i, history in enumerate(series):
        object_fields(history, {"id", "agent_id", "version", "source_type", "frequency_seconds",
                                "unit", "currency", "return_basis", "costs"},
                      path=f"metadata.series[{i}] (observations belong in the CSV)")
        sid = text(history["id"], f"metadata.series[{i}].id", 80)
        if sid in histories:
            raise InputError(f"duplicate series id in metadata: {sid}")
        history["observations"] = []
        histories[sid] = history

    path = Path(path)
    if path.stat().st_size > 25_000_000:
        raise InputError("CSV input exceeds the 25 MB limit")
    locations = {}
    reader = None
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            required = {"series_id", "timestamp", "return", "cost"}
            if not header or len(header) != len(set(header)):
                raise InputError("CSV line 1: missing or duplicate column names")
            if set(header) not in (required, required | {"annotation"}):
                raise InputError("CSV line 1: columns must be series_id,timestamp,return,cost with optional annotation (any order)")
            for count, values in enumerate(reader, 1):
                label = f"CSV line {reader.line_num}"
                if count > 200_000:
                    raise InputError(f"{label}: CSV exceeds 200,000 observations")
                if len(values) != len(header):
                    raise InputError(f"{label}: expected {len(header)} columns, found {len(values)}; blank rows are invalid")
                row = dict(zip(header, values))
                sid = row["series_id"]
                if sid not in histories:
                    raise InputError(f"{label}.series_id: unknown series {sid!r}; declare it in metadata")
                history = histories[sid]
                records = history["observations"]
                if len(records) >= 10_000:
                    raise InputError(f"{label}: {sid} exceeds 10,000 observations")
                stamp(row["timestamp"], label + ".timestamp")
                if records and row["timestamp"] <= records[-1]["timestamp"]:
                    raise InputError(f"{label}: {sid} has a duplicate or unordered timestamp; rows are never sorted automatically")
                record = {"timestamp": row["timestamp"],
                          "return": _number(row["return"], label + ".return"),
                          "cost": _number(row["cost"], label + ".cost", nullable=True)}
                if row.get("annotation"):
                    record["annotation"] = row["annotation"]
                locations[f"{sid}.observations[{len(records)}]"] = label
                records.append(record)
    except (csv.Error, UnicodeError) as exc:
        line = reader.line_num if reader is not None else 1
        raise InputError(f"CSV near line {line}: {exc}") from None

    # Reuse the core contract for costs, ranges, calendar, provenance and portfolio.
    # Translate observation paths into physical CSV lines without hiding the field.
    try:
        data = validate(document)
        align(data, "strict")
    except InputError as exc:
        message = str(exc)
        match = re.match(r"([^:]+\.observations\[\d+\])", message)
        location = locations.get(match.group(1)) if match else None
        raise InputError(f"{location}: {message}" if location else message) from None
    return document
