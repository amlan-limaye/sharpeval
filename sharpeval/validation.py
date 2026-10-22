"""Strict, deliberately small input contract. No implicit calendar or cost filling."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re


class InputError(ValueError):
    """An input cannot be interpreted unambiguously within the v1 contract."""


def object_fields(value, required, optional=(), path="input"):
    if not isinstance(value, dict):
        raise InputError(f"{path}: expected an object")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing:
        raise InputError(f"{path}: missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise InputError(f"{path}: unknown fields: {', '.join(sorted(extra))}")


def text(value, path, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise InputError(f"{path}: expected nonempty text, at most {limit} characters")
    return value


def number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{path}: expected a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise InputError(f"{path}: expected a finite number") from None
    if not math.isfinite(result):
        raise InputError(f"{path}: expected a finite number")
    return result


def integer(value, path, low, high):
    if type(value) is not int or not low <= value <= high:
        raise InputError(f"{path}: expected an integer in [{low}, {high}]")
    return value


def stamp(value, path):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise InputError(f"{path}: use an explicit UTC period end: YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise InputError(f"{path}: invalid calendar timestamp") from None


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_input(path):
    path = Path(path)
    if path.stat().st_size > 25_000_000:
        raise InputError("input exceeds the v1 25 MB limit")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json,
                          parse_constant=lambda x: (_ for _ in ()).throw(InputError(f"nonfinite JSON number: {x}")))
    except InputError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise InputError(f"invalid JSON: {exc}") from None


@dataclass(frozen=True)
class History:
    id: str
    agent_id: str
    version: str
    source_type: str
    return_basis: str
    costs: dict
    timestamps: tuple
    net: tuple
    gross: tuple
    cost: tuple
    annotations: tuple


@dataclass(frozen=True)
class Dataset:
    document: dict
    calendar: tuple
    histories: dict
    old: str
    new: str
    benchmark: str | None
    portfolio: dict | None


def validate(document):
    required = {"schema_version", "title", "synthetic", "calendar", "cash_return_per_period",
                "series", "comparison"}
    object_fields(document, required, {"benchmark", "portfolio", "search_trials"})
    integer(document["schema_version"], "schema_version", 1, 1)
    text(document["title"], "title", 200)
    if type(document["synthetic"]) is not bool:
        raise InputError("synthetic must be true or false")
    cash = number(document["cash_return_per_period"], "cash_return_per_period")
    if not -1 < cash <= 1:
        raise InputError("cash_return_per_period must be greater than -1 and at most 1")
    if document.get("search_trials") is not None:
        integer(document["search_trials"], "search_trials", 1, 1_000_000_000)
    calendar = document["calendar"]
    object_fields(calendar, {"frequency_seconds", "periods_per_year", "timestamps", "notes"}, path="calendar")
    freq = integer(calendar["frequency_seconds"], "calendar.frequency_seconds", 1, 31_536_000)
    ppy = calendar["periods_per_year"]
    if ppy is not None and not 0 < number(ppy, "calendar.periods_per_year") <= 31_536_000:
        raise InputError("calendar.periods_per_year must be positive or null")
    text(calendar["notes"], "calendar.notes")
    grid = calendar["timestamps"]
    if not isinstance(grid, list) or not 1 <= len(grid) <= 10_000:
        raise InputError("calendar.timestamps must contain 1 to 10,000 expected period ends")
    dates = [stamp(t, f"calendar.timestamps[{i}]") for i, t in enumerate(grid)]
    for before, after in zip(dates, dates[1:]):
        seconds = (after - before).total_seconds()
        if seconds <= 0 or seconds % freq != 0:
            raise InputError("calendar timestamps must be unique, increasing and on the declared frequency grid")
    grid_set = set(grid)
    raw_series = document["series"]
    if not isinstance(raw_series, list) or not 2 <= len(raw_series) <= 20:
        raise InputError("series must contain 2 to 20 histories")
    histories = {}
    for raw in raw_series:
        fields = {"id", "agent_id", "version", "source_type", "frequency_seconds", "unit",
                  "currency", "return_basis", "costs", "observations"}
        object_fields(raw, fields, path="series item")
        sid = text(raw["id"], "series.id", 80)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", sid) or sid.startswith("portfolio."):
            raise InputError(f"{sid}: id must use letters/numbers/_.- and cannot start with portfolio.")
        if sid in histories:
            raise InputError(f"duplicate series id: {sid}")
        agent = text(raw["agent_id"], f"{sid}.agent_id", 120)
        version = text(raw["version"], f"{sid}.version", 120)
        if raw["source_type"] not in ("backtest", "paper", "live"):
            raise InputError(f"{sid}.source_type must be backtest, paper or live (imported records only)")
        integer(raw["frequency_seconds"], f"{sid}.frequency_seconds", 1, 31_536_000)
        if raw["frequency_seconds"] != freq:
            raise InputError(f"{sid}: incompatible frequency_seconds; resample explicitly before importing")
        if raw["unit"] != "decimal":
            raise InputError(f"{sid}: unit must be decimal simple equity returns; percent/log returns unsupported")
        if not isinstance(raw["currency"], str) or not re.fullmatch("[A-Z]{3}", raw["currency"]):
            raise InputError(f"{sid}: currency must be a three-letter valuation currency")
        if raw["return_basis"] not in ("gross", "net"):
            raise InputError(f"{sid}.return_basis must be gross or net")
        costs = raw["costs"]
        object_fields(costs, {"included", "excluded", "notes"}, path=f"{sid}.costs")
        for field in ("included", "excluded"):
            items = costs[field]
            if not isinstance(items, list) or len(items) > 30:
                raise InputError(f"{sid}.costs.{field}: expected a list of at most 30 component names")
            for item in items:
                text(item, f"{sid}.costs.{field}", 80)
            if len(items) != len(set(items)):
                raise InputError(f"{sid}.costs.{field}: duplicate cost component")
        if set(costs["included"]) & set(costs["excluded"]):
            raise InputError(f"{sid}: a cost component cannot be both included and excluded")
        text(costs["notes"], f"{sid}.costs.notes")
        records = raw["observations"]
        if not isinstance(records, list) or not 1 <= len(records) <= len(grid):
            raise InputError(f"{sid}: observations must be nonempty and no longer than the calendar")
        ts, nets, grosses, charges, annotations = [], [], [], [], []
        ruined = False
        for i, row in enumerate(records):
            label = f"{sid}.observations[{i}]"
            object_fields(row, {"timestamp", "return", "cost"}, {"annotation"}, label)
            stamp(row["timestamp"], label + ".timestamp")
            t = row["timestamp"]
            if t not in grid_set:
                raise InputError(f"{label}: timestamp is outside the declared calendar")
            if ts and t <= ts[-1]:
                raise InputError(f"{label}: duplicate or unordered timestamp")
            value = number(row["return"], label + ".return")
            charge = None if row["cost"] is None else number(row["cost"], label + ".cost")
            if charge is not None and not 0 <= charge <= 1000:
                raise InputError(f"{label}: cost must be a nonnegative equity fraction no greater than 1000")
            if raw["return_basis"] == "gross" and charge is None:
                raise InputError(f"{label}: gross returns require an explicit cost, including explicit zero")
            net = value - charge if raw["return_basis"] == "gross" else value
            gross = value if raw["return_basis"] == "gross" else (None if charge is None else value + charge)
            if not -1 <= net <= 1000 or (gross is not None and not -1 <= gross <= 1000):
                raise InputError(f"{label}: supported simple return range is [-1, 1000] after and before costs")
            if ruined and net != 0:
                raise InputError(f"{label}: nonzero return after bankruptcy; recapitalization is not modeled")
            ruined = ruined or net == -1
            note = row.get("annotation")
            if note is not None:
                text(note, label + ".annotation")
            ts.append(t); nets.append(net); grosses.append(gross); charges.append(charge); annotations.append(note)
        histories[sid] = History(sid, agent, version, raw["source_type"], raw["return_basis"],
                                 costs, tuple(ts), tuple(nets), tuple(grosses), tuple(charges), tuple(annotations))
    currencies = {r["currency"] for r in raw_series}
    if len(currencies) != 1:
        raise InputError("incompatible valuation currencies; convert consistently before importing")
    comparison = document["comparison"]
    object_fields(comparison, {"old", "new"}, path="comparison")
    old, new = comparison["old"], comparison["new"]
    for sid in (old, new):
        if not isinstance(sid, str) or sid not in histories:
            raise InputError("comparison references an unknown series")
    if old == new or histories[old].agent_id != histories[new].agent_id or histories[old].version == histories[new].version:
        raise InputError("comparison needs two distinct versions of the same agent_id")
    benchmark = document.get("benchmark")
    if benchmark is not None and (not isinstance(benchmark, str) or benchmark not in histories):
        raise InputError("benchmark references an unknown series")
    portfolio = document.get("portfolio")
    if portfolio is not None:
        object_fields(portfolio, {"weights", "candidate_weight", "rebalance", "overlay_cost_per_period",
                                  "overlay_cost_notes", "weights_declared_before_evaluation"}, path="portfolio")
        if portfolio["rebalance"] != "each_period":
            raise InputError("portfolio.rebalance must be each_period; buy-and-hold weights unsupported")
        if portfolio["weights_declared_before_evaluation"] is not True:
            raise InputError("portfolio weights must be declared before evaluation; optimized hindsight weights unsupported")
        weights = portfolio["weights"]
        if not isinstance(weights, dict) or not weights:
            raise InputError("portfolio.weights must be a nonempty id-to-weight object")
        for sid, weight in weights.items():
            if sid not in histories or not 0 <= number(weight, f"portfolio weight {sid}") <= 1:
                raise InputError(f"invalid portfolio member/weight: {sid}; only long-only funded weights are supported")
        if not math.isclose(math.fsum(weights.values()), 1.0, abs_tol=1e-10, rel_tol=0):
            raise InputError("portfolio.weights must sum to 1; no hidden leverage, cash or normalization")
        if not 0 <= number(portfolio["candidate_weight"], "candidate_weight") <= 1:
            raise InputError("candidate_weight must be in [0, 1]")
        if not 0 <= number(portfolio["overlay_cost_per_period"], "overlay_cost_per_period") < 1:
            raise InputError("overlay_cost_per_period must be in [0, 1)")
        text(portfolio["overlay_cost_notes"], "overlay_cost_notes")
    return Dataset(document, tuple(grid), histories, old, new, benchmark, portfolio)


def align(data, mode):
    if mode not in ("strict", "intersection"):
        raise InputError("alignment must be strict or intersection")
    selected = {data.old, data.new}
    if data.benchmark:
        selected.add(data.benchmark)
    if data.portfolio:
        selected.update(data.portfolio["weights"])
    selected = sorted(selected)
    if len({data.histories[sid].source_type for sid in selected}) != 1:
        raise InputError("participating histories mix live/paper/backtest sources; import one comparable evaluation context")
    if mode == "strict":
        for sid in selected:
            if data.histories[sid].timestamps != data.calendar:
                observed = set(data.histories[sid].timestamps)
                missing = [t for t in data.calendar if t not in observed]
                preview = ", ".join(missing[:3]) + (", ..." if len(missing) > 3 else "")
                raise InputError(f"{sid}: strict alignment has {len(missing)} missing periods ({preview}); supply them or explicitly use intersection for trimmed edges")
        kept = data.calendar
    else:
        common = set(data.calendar)
        for sid in selected:
            common.intersection_update(data.histories[sid].timestamps)
        kept = tuple(t for t in data.calendar if t in common)
        if not kept:
            raise InputError("no common periods across all participating histories")
        start = data.calendar.index(kept[0])
        end = data.calendar.index(kept[-1])
        if data.calendar[start:end + 1] != kept:
            raise InputError("intersection contains internal missing periods; do not bridge gaps or fill returns")
        for sid in selected:
            h = data.histories[sid]
            if any(r == -1 and t < kept[0] for t, r in zip(h.timestamps, h.net)):
                raise InputError(f"{sid}: aligned window starts after bankruptcy; resetting equity would be misleading")
    positions = {sid: {t: i for i, t in enumerate(data.histories[sid].timestamps)} for sid in selected}
    indexes = {sid: tuple(positions[sid][t] for t in kept) for sid in selected}
    kept_set = set(kept)
    details = {
        "mode": mode, "periods": len(kept), "start": kept[0], "end": kept[-1],
        "calendar_periods": len(data.calendar), "timestamps": list(kept),
        "excluded_calendar_timestamps": [t for t in data.calendar if t not in kept_set],
        "dropped_observations": {sid: len(data.histories[sid].timestamps) - len(kept) for sid in selected},
        "unused_series": sorted(set(data.histories) - set(selected)),
        "rule": "All participating histories share one contiguous window on the declared session calendar. No filling or gap bridging.",
    }
    return indexes, details
