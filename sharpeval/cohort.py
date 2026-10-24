"""Versioned, conditional cohort evidence. No probability-of-skill claim."""

import hashlib
import json
import math
import platform
import re

from .selection import (dependence_screen, psr_from_summary, return_moments,
                        selection_diagnostics, unavailable, validate_selection)
from .statistics import correlation, diagnostics, mean, wealth_stats
from .validation import InputError, integer, number, object_fields, stamp, text


METHOD = "psr_holm_v1"
ASSUMPTIONS = ("serial_independence", "stationarity", "finite_fourth_moment")


def identity(value, label):
    text(value, label, 120)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise InputError(f"{label}: use letters, numbers, underscores, hyphens or dots")
    return value


def bounded(value, label, low, high):
    value = number(value, label)
    if not low <= value <= high:
        raise InputError(f"{label}: expected a value in [{low}, {high}]")
    return value


def choice(value, options, label):
    if value not in options:
        raise InputError(f"{label}: expected one of {', '.join(options)}")


def holm_adjust(p_values):
    """All registered slots, including p=1 placeholders; arbitrary peer dependence.

    Familywise control requires valid marginal p-values. It cannot repair invalid
    serial assumptions or holdout reuse. Equal p-values receive equal adjustments.
    """
    if not p_values:
        raise InputError("Holm correction requires a nonempty frozen family")
    for name, value in p_values.items():
        bounded(value, f"p[{name}]", 0, 1)
    ordered = sorted(p_values, key=lambda key: (p_values[key], key))
    adjusted, running, size = {}, 0.0, len(ordered)
    for i, key in enumerate(ordered):
        running = max(running, min(1.0, (size - i) * p_values[key]))
        adjusted[key] = running
    return adjusted


def validate_cohort(document):
    """One declared market window; planned primary/replay cells are never inferred away."""
    object_fields(document, {"schema_version", "cohort_id", "title", "synthetic", "calendar",
                             "protocol", "agents", "seed_ids", "runs", "reference"}, path="cohort")
    integer(document["schema_version"], "schema_version", 3, 3)
    identity(document["cohort_id"], "cohort_id")
    text(document["title"], "title", 200)
    if type(document["synthetic"]) is not bool:
        raise InputError("synthetic must be a boolean")
    calendar = document["calendar"]
    object_fields(calendar, {"window_id", "frequency_seconds", "timestamps", "notes"}, path="calendar")
    identity(calendar["window_id"], "calendar.window_id")
    frequency = integer(calendar["frequency_seconds"], "frequency_seconds", 1, 31_536_000)
    text(calendar["notes"], "calendar.notes")
    grid = calendar["timestamps"]
    if not isinstance(grid, list) or not 3 <= len(grid) <= 10_000:
        raise InputError("calendar.timestamps must contain 3..10,000 expected period ends")
    dates = [stamp(t, "calendar timestamp") for t in grid]
    if any((b - a).total_seconds() <= 0 or (b - a).total_seconds() % frequency for a, b in zip(dates, dates[1:])):
        raise InputError("calendar must be unique, chronological and on the declared frequency grid")
    protocol = document["protocol"]
    object_fields(protocol, {"method", "hurdle_sharpe_per_period", "hurdle_unit", "alpha", "minimum_observations",
                             "ranking_seed_id", "currency", "unit", "cash_return_per_period", "source_type",
                             "return_basis", "costs", "assumptions", "evaluation_status", "cohort_frozen",
                             "ranking_execution_frozen", "risk_limits", "notes"}, path="protocol")
    if protocol["method"] != METHOD or protocol["hurdle_unit"] != "per_period" or protocol["unit"] != "decimal":
        raise InputError("use method=psr_holm_v1, hurdle_unit=per_period and unit=decimal; no annualized conversion")
    hurdle = bounded(protocol["hurdle_sharpe_per_period"], "hurdle_sharpe_per_period", 0, 10)
    if hurdle == 0:
        raise InputError("choose an explicit positive common Sharpe hurdle before evaluation; no universal cutoff is inferred")
    bounded(protocol["alpha"], "alpha", 0.001, 0.1)
    integer(protocol["minimum_observations"], "minimum_observations", 60, 10_000)
    if not isinstance(protocol["currency"], str) or not re.fullmatch(r"[A-Z]{3}", protocol["currency"]):
        raise InputError("currency must be a three-letter valuation currency")
    bounded(protocol["cash_return_per_period"], "cash_return_per_period", -0.99, 1)
    choice(protocol["source_type"], ("backtest", "paper", "live"), "source_type")
    choice(protocol["return_basis"], ("gross", "net"), "return_basis")
    choice(protocol["evaluation_status"], ("untouched", "reused", "unknown"), "evaluation_status")
    for field in ("cohort_frozen", "ranking_execution_frozen"):
        choice(protocol[field], ("declared", "no", "unknown"), field)
    object_fields(protocol["assumptions"], ASSUMPTIONS, path="assumptions")
    for name in ASSUMPTIONS:
        choice(protocol["assumptions"][name], ("assumed", "unsupported", "unknown"), f"assumptions.{name}")
    text(protocol["notes"], "protocol.notes")
    costs = protocol["costs"]
    object_fields(costs, {"included", "excluded", "notes"}, path="costs")
    for key in ("included", "excluded"):
        if not isinstance(costs[key], list) or len(costs[key]) > 30:
            raise InputError(f"costs.{key}: expected at most 30 component names")
        for item in costs[key]:
            text(item, f"costs.{key}", 80)
        if len(set(costs[key])) != len(costs[key]):
            raise InputError(f"costs.{key}: duplicate component")
    if set(costs["included"]) & set(costs["excluded"]):
        raise InputError("a cost cannot be both included and excluded")
    text(costs["notes"], "costs.notes")
    limits = protocol["risk_limits"]
    object_fields(limits, {"max_drawdown", "max_period_loss", "max_peak_exposure"}, path="risk_limits")
    bounded(limits["max_drawdown"], "max_drawdown", 0, 1)
    bounded(limits["max_period_loss"], "max_period_loss", 0, 1)
    bounded(limits["max_peak_exposure"], "max_peak_exposure", 0, 100)
    seeds = document["seed_ids"]
    if not isinstance(seeds, list) or not 1 <= len(seeds) <= 10:
        raise InputError("seed_ids must contain 1..10 explicit identities")
    for seed in seeds:
        identity(seed, "seed_id")
    if len(set(seeds)) != len(seeds):
        raise InputError("duplicate seed identity")
    if protocol["ranking_seed_id"] not in seeds:
        raise InputError("ranking_seed_id must be a predeclared seed identity")
    raw_agents = document["agents"]
    if not isinstance(raw_agents, list) or not 2 <= len(raw_agents) <= 100:
        raise InputError("agents must contain 2..100 predeclared candidates")
    if len(raw_agents) * len(seeds) * len(grid) > 250_000:
        raise InputError("cohort exceeds 250,000 planned observation cells")
    agents = {}
    for agent in raw_agents:
        object_fields(agent, {"agent_id", "version"}, {"discovery"}, path="agent")
        aid = identity(agent["agent_id"], "agent_id")
        text(agent["version"], f"{aid}.version", 120)
        if aid in agents:
            raise InputError("duplicate agent_id in the frozen family")
        discovery = agent.get("discovery")
        if discovery is not None:
            object_fields(discovery, {"net_returns", "cash_return_per_period", "selection"}, path=f"{aid}.discovery")
            values = discovery["net_returns"]
            if not isinstance(values, list) or not 3 <= len(values) <= 10_000:
                raise InputError("discovery.net_returns requires 3..10,000 explicitly net observations")
            for value in values:
                bounded(value, "discovery net return", -1, 1000)
            bounded(discovery["cash_return_per_period"], "discovery cash", -0.99, 1)
            validate_selection(discovery["selection"])
        agents[aid] = agent
    runs, run_ids = {}, set()
    if not isinstance(document["runs"], list) or len(document["runs"]) > len(agents) * len(seeds):
        raise InputError("runs must fit the declared agent/seed matrix")
    for run in document["runs"]:
        object_fields(run, {"run_id", "agent_id", "version", "seed_id", "status", "reason", "observations"}, path="run")
        rid = identity(run["run_id"], "run_id")
        aid = identity(run["agent_id"], f"{rid}.agent_id")
        seed = identity(run["seed_id"], f"{rid}.seed_id")
        if rid in run_ids:
            raise InputError("duplicate run_id")
        run_ids.add(rid)
        if aid not in agents or seed not in seeds or run["version"] != agents[aid]["version"]:
            raise InputError(f"{rid}: run identity/version is outside the frozen cohort")
        key = (aid, seed)
        if key in runs:
            raise InputError(f"{rid}: duplicate agent/seed cell; ambiguous primary execution")
        choice(run["status"], ("completed", "failed", "missing"), f"{rid}.status")
        if run["status"] != "completed":
            text(run["reason"], f"{rid}.reason")
            if run["observations"] is not None:
                raise InputError(f"{rid}: failed/missing observations must be null, never partial winners")
            runs[key] = {**run, "explicit_record": True}
            continue
        if run["reason"] is not None:
            raise InputError(f"{rid}: completed reason must be null")
        rows = run["observations"]
        if not isinstance(rows, list) or len(rows) != len(grid):
            raise InputError(f"{rid}: completed observations must cover every expected calendar timestamp")
        nets, charges, exposures, peaks, ruined = [], [], [], [], False
        for i, row in enumerate(rows):
            label = f"{rid}.observations[{i}]"
            object_fields(row, {"timestamp", "return", "cost", "exposure", "peak_exposure"}, path=label)
            if row["timestamp"] != grid[i]:
                raise InputError(f"{label}: expected {grid[i]}; no gaps, duplicates, reordering or intersection")
            value = bounded(row["return"], label + ".return", -1, 1000)
            cost = None if row["cost"] is None else bounded(row["cost"], label + ".cost", 0, 1000)
            if protocol["return_basis"] == "gross" and cost is None:
                raise InputError(f"{label}: gross return requires explicit cost")
            net = value - cost if protocol["return_basis"] == "gross" else value
            if not -1 <= net <= 1000:
                raise InputError(f"{label}: net return outside supported range")
            if ruined and net != 0:
                raise InputError(f"{label}: recapitalization after bankruptcy is unsupported")
            ruined = ruined or net == -1
            exposure = None if row["exposure"] is None else bounded(row["exposure"], label + ".exposure", 0, 100)
            peak = None if row["peak_exposure"] is None else bounded(row["peak_exposure"], label + ".peak_exposure", 0, 100)
            if exposure is not None and peak is not None and exposure > peak:
                raise InputError(f"{label}: average exposure cannot exceed peak exposure")
            nets.append(net); charges.append(cost); exposures.append(exposure); peaks.append(peak)
        runs[key] = {**run, "explicit_record": True, "net": nets, "cost": charges, "exposure": exposures, "peaks": peaks}
    for aid in sorted(agents):
        for seed in seeds:
            runs.setdefault((aid, seed), {"run_id": None, "agent_id": aid, "version": agents[aid]["version"],
                                         "seed_id": seed, "status": "missing", "reason": "No record supplied for this planned cell.",
                                         "observations": None, "explicit_record": False})
    reference = document["reference"]
    if reference is not None:
        object_fields(reference, {"id", "frozen", "notes", "observations"}, path="reference")
        identity(reference["id"], "reference.id")
        choice(reference["frozen"], ("declared", "unknown", "no"), "reference.frozen")
        text(reference["notes"], "reference.notes")
        if reference["observations"] is not None:
            if not isinstance(reference["observations"], list) or len(reference["observations"]) != len(grid):
                raise InputError("reference must cover the common expected calendar exactly")
            for i, row in enumerate(reference["observations"]):
                object_fields(row, {"timestamp", "net_return"}, path="reference observation")
                if row["timestamp"] != grid[i]:
                    raise InputError("reference calendar mismatch")
                bounded(row["net_return"], "reference net_return", -1, 1000)
    return {"agents": agents, "runs": runs, "document": document}


def run_diagnostics(run, document):
    result = {key: run[key] for key in ("run_id", "agent_id", "version", "seed_id", "status", "reason", "explicit_record")}
    if run["status"] != "completed":
        return {**result, "metrics": None, "efficiency": unavailable("Run is not completed."),
                "independence": unavailable("Run is not completed.")}
    protocol = document["protocol"]
    net, cash = run["net"], protocol["cash_return_per_period"]
    metrics = diagnostics(net, cash, None)
    # The full input remains in the portable input file; avoid huge duplicated paths.
    metrics.pop("net_wealth")
    if any(x is None for x in run["exposure"]):
        efficiency = unavailable("Measured period-average gross exposure is incomplete; no proxy is inferred.")
    elif math.fsum(run["exposure"]) == 0:
        efficiency = unavailable("Gross exposure is zero; return per exposure is undefined.")
    else:
        average = mean(run["exposure"])
        value = (metrics["mean_return"] - cash) / average if average else None
        efficiency = (unavailable("Return per exposure is outside numeric resolution.")
                      if value is None or not math.isfinite(value) else
                      {"status": "descriptive", "value": value, "mean_gross_exposure": average,
                       "unit": "mean net excess return / mean measured gross exposure"})
    reference = document["reference"]
    if reference is None or reference["frozen"] != "declared" or reference["observations"] is None:
        independence = unavailable("No complete frozen reference supplied; low correlation cannot be inferred.")
    else:
        r = correlation(net, [row["net_return"] for row in reference["observations"]])
        independence = (unavailable("Correlation is undefined for a constant or numerically degenerate stream.") if r is None else
                        {"status": "descriptive", "value": r, "absolute_correlation": abs(r), "reference_id": reference["id"]})
    return {**result, "metrics": metrics, "efficiency": efficiency, "independence": independence,
            "costs_known": all(c is not None for c in run["cost"]),
            "mean_cost_fraction": mean(run["cost"]) if all(c is not None for c in run["cost"]) else None,
            "cost_operation": "net = return - cost" if protocol["return_basis"] == "gross" else "net = supplied return; costs are not deducted twice"}


def rank_cohort(document):
    data = validate_cohort(document)
    protocol, n = document["protocol"], len(document["calendar"]["timestamps"])
    runs = [run_diagnostics(data["runs"][key], document) for key in sorted(data["runs"])]
    by_key = {(r["agent_id"], r["seed_id"]): r for r in runs}
    agents, family_p = [], {}
    for aid, agent in sorted(data["agents"].items()):
        key = (aid, protocol["ranking_seed_id"])
        run, described = data["runs"][key], by_key[key]
        reasons, raw_psr, raw_p, screen, moments = [], None, None, None, None
        if protocol["evaluation_status"] != "untouched":
            reasons.append("The common evaluation window is reused or its untouched status is unknown.")
        for field in ("cohort_frozen", "ranking_execution_frozen"):
            if protocol[field] != "declared":
                reasons.append(f"Required {field} declaration is missing or unsupported.")
        for name in ASSUMPTIONS:
            if protocol["assumptions"][name] != "assumed":
                reasons.append(f"Required {name} assumption is {protocol['assumptions'][name]}.")
        if n < protocol["minimum_observations"]:
            reasons.append("History is shorter than the predeclared minimum; this is an operational floor, not proof of adequacy.")
        if run["status"] != "completed":
            reasons.append(f"Predeclared ranking execution is {run['status']}; no replay is substituted.")
        else:
            net, cash = run["net"], protocol["cash_return_per_period"]
            metrics, limits = described["metrics"], protocol["risk_limits"]
            if not described["costs_known"]:
                reasons.append("Primary cost amounts are unknown; common cost accounting is unverified.")
            if metrics["bankrupt"] or metrics["wealth_overflow"]:
                reasons.append("Bankruptcy or wealth overflow invalidates the ranking contract.")
            if metrics["max_drawdown"] > limits["max_drawdown"]:
                reasons.append("Observed drawdown exceeds the common limit.")
            if metrics["worst_period"] < -limits["max_period_loss"]:
                reasons.append("Observed period loss exceeds the common limit.")
            if any(p is None for p in run["peaks"]):
                reasons.append("Measured peak exposure is incomplete; the common risk limit cannot be checked.")
            elif max(run["peaks"]) > limits["max_peak_exposure"]:
                reasons.append("Measured peak exposure exceeds the common limit.")
            log_wealth = wealth_stats(net)["log_wealth"]
            if log_wealth is None or log_wealth <= n * math.log1p(cash):
                reasons.append("Net compounded wealth does not exceed the common cash comparator.")
            moments, screen = return_moments(net, cash), dependence_screen(net)
            if screen["flagged"]:
                reasons.append("Serial-dependence screen flagged returns or squared returns; standard PSR is withheld.")
            if moments["status"] != "available":
                reasons.extend(moments["reasons"])
            elif all(protocol["assumptions"][name] == "assumed" for name in ASSUMPTIONS) and not screen["flagged"] and n >= protocol["minimum_observations"]:
                try:
                    raw_psr = psr_from_summary(moments["sharpe_per_period"], n, moments["skewness"],
                                              moments["kurtosis_non_excess"], protocol["hurdle_sharpe_per_period"])
                    raw_p = 0.5 * math.erfc(raw_psr["z"] / math.sqrt(2))
                except InputError as error:
                    reasons.append(str(error))
        eligible = not reasons and raw_p is not None
        family_p[aid] = raw_p if eligible else 1.0
        discovery = agent.get("discovery")
        context = (unavailable("No discovery history supplied. Unknown search evidence is not scored.") if discovery is None else
                   selection_diagnostics(discovery["net_returns"], discovery["cash_return_per_period"], discovery["selection"]))
        replay = [r for r in runs if r["agent_id"] == aid]
        sharpes = [r["metrics"]["sharpe_per_period"] for r in replay if r["metrics"] is not None and r["metrics"]["sharpe_per_period"] is not None]
        agents.append({"agent_id": aid, "version": agent["version"], "status": "scored" if eligible else "unscored",
                       "reasons": reasons, "ranking_run_id": run["run_id"], "ranking_seed_id": run["seed_id"],
                       "score": None, "rank": None, "evidence_qualified": False, "raw_psr": raw_psr,
                       "raw_p": raw_p, "holm_adjusted_p": None, "family_p_used": family_p[aid],
                       "primary": described, "moments": moments, "dependence_screen": screen,
                       "sharpe_gap_to_hurdle": (moments["sharpe_per_period"] - protocol["hurdle_sharpe_per_period"]
                                                if moments and moments["status"] == "available" else None),
                       "discovery_context": context,
                       "replays": {"planned": len(replay), "completed": sum(r["status"] == "completed" for r in replay),
                                   "failed": sum(r["status"] == "failed" for r in replay), "missing": sum(r["status"] == "missing" for r in replay),
                                   "sharpe_range": [min(sharpes), max(sharpes)] if sharpes else None,
                                   "distinct_market_periods": n, "inferential_aggregation": "none; only the frozen execution contributes evidence"}})
    adjusted = holm_adjust(family_p)
    for agent in agents:
        agent["family_adjusted_p"] = adjusted[agent["agent_id"]]
        if agent["status"] == "scored":
            agent["holm_adjusted_p"] = adjusted[agent["agent_id"]]
            agent["score"] = 100 * (1 - agent["holm_adjusted_p"])
            agent["evidence_qualified"] = agent["holm_adjusted_p"] <= protocol["alpha"]
    agents.sort(key=lambda row: (row["score"] is None, -(row["score"] or 0), row["agent_id"]))
    scores = [row["score"] for row in agents if row["score"] is not None]
    for agent in agents:
        if agent["score"] is not None:
            agent["rank"] = 1 + sum(score > agent["score"] for score in scores)
    canonical = lambda obj: json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    design = {key: document[key] for key in ("cohort_id", "calendar", "protocol", "seed_ids")}
    design["agents"] = [{"agent_id": a["agent_id"], "version": a["version"]} for a in sorted(document["agents"], key=lambda a: a["agent_id"])]
    design["reference"] = None if document["reference"] is None else {key: value for key, value in document["reference"].items() if key != "observations"}
    result = {"schema_version": 3, "tool": {"name": "SharpeVal", "calculation_profile": METHOD, "python": platform.python_version()},
              "title": document["title"], "cohort_id": document["cohort_id"], "synthetic": document["synthetic"],
              "input_sha256": hashlib.sha256(canonical(document)).hexdigest(), "design_sha256": hashlib.sha256(canonical(design)).hexdigest(),
              "protocol": protocol, "calendar": document["calendar"], "family_size": len(agents), "agents": agents, "runs": runs,
              "coverage": {"planned_runs": len(runs), "completed_runs": sum(r["status"] == "completed" for r in runs),
                           "failed_runs": sum(r["status"] == "failed" for r in runs), "missing_runs": sum(r["status"] == "missing" for r in runs),
                           "scored_agents": len(scores)},
              "interpretation": "Conditional common-hurdle evidence score, not a posterior probability of skill, causal alpha, pairwise superiority or proven repeatability.",
              "formula": "One-sided p = 0.5*erfc(PSR z/sqrt(2)); Holm over every registered agent; score = 100*(1-p_Holm).",
              "warnings": ["Swing-inspired and independently specified; no claim to reproduce unpublished Swing formulas, weights or windows.",
                           "Holm permits dependent peers only when marginal p-values are valid. It does not fix serial dependence, selection on this window, or inaccurate producer declarations.",
                           "No screen can prove independence, stationarity or finite fourth moments. PSR is an asymptotic plug-in approximation.",
                           "Missing, failed and ineligible agents retain p=1 family slots but have null scores; a known zero score is different.",
                           "Efficiency and frozen-reference correlation are descriptive only. Low correlation never adds to the evidence score.",
                           "One execution and one common window determine this score. Replay seeds do not multiply market history; windows are not pooled.",
                           "Discovery DSR is separate context; it is never averaged across seeds or added to the untouched-holdout correction.",
                           "Declared cost coverage and measured risk inputs are not independently audited; excluded costs remain limitations.",
                           "A score rounded to 100 is not certainty. Ranking does not test whether one agent outperforms another."]}
    if document["synthetic"]:
        result["warnings"].insert(0, "SYNTHETIC controlled example: not actual trading, adoption, prospective evidence or proven skill.")
    json.dumps(result, allow_nan=False)
    return result
