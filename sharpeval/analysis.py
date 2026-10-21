"""Public analysis entry point. Returns ordinary JSON-serializable Python objects."""

import hashlib
import json
import math
import platform

from .bootstrap import METRICS, paired_bootstrap
from .statistics import correlation, diagnostics, mean, regression, wealth_stats
from .validation import InputError, align, validate


def difference(left, right):
    return {key: None if left[key] is None or right[key] is None else right[key] - left[key]
            for key in METRICS}


def analyze(document, *, alignment="strict", block_length=None, resamples=2000, seed=42, confidence=0.95):
    """Validate and compare a v1 document. No I/O, network access or global RNG changes."""
    data = validate(document)
    indexes, alignment_info = align(data, alignment)
    cash = document["cash_return_per_period"]
    ppy = document["calendar"]["periods_per_year"]
    sources = {data.histories[sid].source_type for sid in indexes}
    if len(sources) != 1:
        raise InputError("participating histories mix live/paper/backtest sources; import one comparable evaluation context")
    streams, histories, warnings = {}, {}, []
    for sid, rows in indexes.items():
        h = data.histories[sid]
        net = tuple(h.net[i] for i in rows)
        streams[sid] = net
        gross = [h.gross[i] for i in rows]
        costs = [h.cost[i] for i in rows]
        known = all(c is not None for c in costs)
        cost_summary = {"input_basis": h.return_basis,
                        "operation": "net = input return - cost" if h.return_basis == "gross" else "net = input return; cost disclosure is NOT subtracted again",
                        "amount_unit": "fraction of start-of-period equity", "known_for_all_periods": known,
                        "sum_period_cost_fractions": math.fsum(costs) if known else None,
                        "mean_period_cost_fraction": mean(costs) if known else None,
                        "gross_total_return": wealth_stats(gross)["total_return"] if known else None,
                        "included": h.costs["included"], "excluded": h.costs["excluded"], "notes": h.costs["notes"],
                        "sum_note": "Sum of period cost fractions is a disclosure, not a dollar cost or compounded wealth drag."}
        stats = diagnostics(net, cash, ppy)
        histories[sid] = {"id": sid, "agent_id": h.agent_id, "version": h.version, "source_type": h.source_type,
                          "metrics": stats, "cost_accounting": cost_summary,
                          "net_returns": list(net),
                          "annotations": [{"timestamp": h.timestamps[i], "text": h.annotations[i]} for i in rows if h.annotations[i] is not None]}
        if not known:
            warnings.append(f"{sid}: net returns accepted, but cost amounts and reconstructed gross performance are unavailable.")
        if h.costs["excluded"]:
            warnings.append(f"{sid}: declared costs exclude {', '.join(h.costs['excluded'])}.")
        if stats["sharpe_per_period"] is None:
            warnings.append(f"{sid}: Sharpe is unavailable with fewer than two periods, zero variance or a ratio outside numeric range.")
        if stats["bankrupt"]:
            warnings.append(f"{sid}: net equity reached zero; no recovery or recapitalization is modeled.")
        if stats["wealth_overflow"]:
            warnings.append(f"{sid}: wealth exceeds floating-point range; affected values are unavailable.")
    if data.histories[data.old].costs != data.histories[data.new].costs:
        warnings.append("Versions declare different cost coverage or notes; inspect the cost table before interpreting the difference.")
    if document["synthetic"]:
        warnings.append("SYNTHETIC fixture: generated behavior exercises this tool; it is not evidence of real-world predictive skill.")
    if ppy is None:
        warnings.append("No periods_per_year supplied. All annualized figures are unavailable.")
    if alignment_info["excluded_calendar_timestamps"]:
        warnings.append("Explicit intersection trimmed the calendar edges. All figures describe only the retained common window.")
    if alignment_info["unused_series"]:
        warnings.append("Unreferenced histories are validated but not analyzed: " + ", ".join(alignment_info["unused_series"]))
    old, new = streams[data.old], streams[data.new]
    diffs = [b - a for a, b in zip(old, new)]
    biggest = max(range(len(diffs)), key=lambda i: abs(diffs[i]))
    observed = difference(histories[data.old]["metrics"], histories[data.new]["metrics"])
    comparison = {"old": data.old, "new": data.new, "direction": "new minus old", "observed_change": observed,
                  "correlation_between_versions": correlation(old, new),
                  "outlier_sensitivity": {"timestamp": alignment_info["timestamps"][biggest], "largest_absolute_period_change": diffs[biggest],
                                          "mean_change_excluding_that_period": mean(diffs[:biggest] + diffs[biggest + 1:]) if len(diffs) > 1 else None,
                                          "note": "Leave-one-period descriptive sensitivity only; this neither removes the period from the analysis nor establishes a cause."}}
    contrasts = {"new_minus_old": (data.old, data.new)}
    correlation_pairs = {"versions": (data.old, data.new)}
    benchmark = {"status": "not_supplied", "reason": "No benchmark supplied. Market exposure and benchmark-relative diagnostics are unavailable."}
    if data.benchmark:
        bm = streams[data.benchmark]
        benchmark = {"status": "available", "id": data.benchmark, "regressions": {}, "mean_excess_return": {}}
        for sid in (data.old, data.new):
            benchmark["regressions"][sid] = regression(streams[sid], bm, cash)
            benchmark["mean_excess_return"][sid] = mean([x - y for x, y in zip(streams[sid], bm)])
        correlation_pairs["new_vs_benchmark"] = (data.new, data.benchmark)
    portfolio = {"status": "not_supplied", "reason": "No existing-agent portfolio supplied; marginal contribution is unavailable."}
    if data.portfolio:
        p = data.portfolio
        if any(-1 in streams[sid] for sid, w in p["weights"].items() if w > 0) or -1 in old or -1 in new:
            portfolio = {"status": "unavailable", "reason": "A component or compared version went bankrupt. Constant allocation after failure requires unsupported recapitalization rules.", "rules": p}
            warnings.append(portfolio["reason"])
        else:
            base = tuple(math.fsum(w * streams[sid][i] for sid, w in p["weights"].items()) for i in range(len(old)))
            weight, overlay = p["candidate_weight"], p["overlay_cost_per_period"]
            with_old = tuple((1 - weight) * a + weight * b - overlay for a, b in zip(base, old))
            with_new = tuple((1 - weight) * a + weight * b - overlay for a, b in zip(base, new))
            if min(with_old + with_new) <= -1:
                raise InputError("fixed-weight portfolio plus overlay cost reaches/breaches bankruptcy; portfolio recapitalization is unsupported")
            streams.update({"portfolio.base": base, "portfolio.with_old": with_old, "portfolio.with_new": with_new})
            pm = {key: diagnostics(values, cash, ppy) for key, values in (("base", base), ("with_old", with_old), ("with_new", with_new))}
            new_costs = [data.histories[data.new].cost[i] for i in indexes[data.new]]
            known_portfolio_costs = all(histories[sid]["cost_accounting"]["known_for_all_periods"] for sid in p["weights"] if p["weights"][sid] > 0)
            base_cost = math.fsum(w * histories[sid]["cost_accounting"]["mean_period_cost_fraction"] for sid, w in p["weights"].items() if w > 0) if known_portfolio_costs else None
            candidate_cost = mean(new_costs) if all(v is not None for v in new_costs) else None
            combined_cost = None if base_cost is None or candidate_cost is None else (1 - weight) * base_cost + weight * candidate_cost + overlay
            portfolio = {"status": "available", "rules": p,
                         "formula": "base[t] = sum(weight[i] * agent_net[i,t]); with_version[t] = (1-candidate_weight)*base[t] + candidate_weight*version_net[t] - overlay_cost_per_period",
                         "metrics": pm,
                         "changes": {"with_new_minus_base": difference(pm["base"], pm["with_new"]),
                                     "with_old_minus_base": difference(pm["base"], pm["with_old"]),
                                     "with_new_minus_with_old": difference(pm["with_old"], pm["with_new"])},
                         "correlations": {sid: correlation(new, streams[sid]) for sid in p["weights"]},
                         "candidate_vs_base_correlation": correlation(new, base),
                         "cost_accounting": {"base_mean_period_cost_fraction": base_cost,
                                             "with_new_mean_period_cost_fraction": combined_cost,
                                             "overlay_cost_per_period": overlay,
                                             "note": "Constituent returns are already net. Only the separately declared overlay cost is additionally subtracted."},
                         "net_returns": {"base": list(base), "with_old": list(with_old), "with_new": list(with_new)},
                         "note": "Fixed funded long-only weights, reset each period; the candidate dilutes existing holdings proportionally. No weights are optimized. Low correlation is not skill."}
            contrasts.update({"with_new_minus_base": ("portfolio.base", "portfolio.with_new"),
                              "with_old_minus_base": ("portfolio.base", "portfolio.with_old"),
                              "with_new_minus_with_old": ("portfolio.with_old", "portfolio.with_new")})
            correlation_pairs["new_vs_portfolio"] = (data.new, "portfolio.base")
            for sid in p["weights"]:
                correlation_pairs[f"new_vs_member:{sid}"] = (data.new, sid)
            if weight == 0:
                warnings.append("Candidate weight is zero. Portfolio differences can only reflect the declared overlay cost.")
    uncertainty = paired_bootstrap(streams, contrasts, correlation_pairs, cash=cash, block_length=block_length,
                                   resamples=resamples, seed=seed, confidence=confidence)
    primary = uncertainty["primary"]
    if primary["status"] != "available":
        warnings.append("Uncertainty unavailable: " + primary["reason"])
    else:
        unavailable = sum(stat["status"] != "available" for contrast in primary["contrasts"].values() for stat in contrast.values())
        if unavailable:
            warnings.append(f"{unavailable} primary interval(s) are undefined; inspect valid-resample counts. Undefined draws are never silently dropped.")
    warnings.extend(["Historical observations and model assumptions do not establish future skill or causal attribution.",
                     "Deflated Sharpe, trial-selection adjustment, multiple-testing correction and repeated-run aggregation are not implemented."])
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    result = {"schema_version": 1, "tool": {"name": "SharpeVal", "version": "0.1.0", "working_title": False,
                                           "python": platform.python_version()},
              "input_sha256": hashlib.sha256(canonical).hexdigest(), "title": document["title"],
              "synthetic": document["synthetic"], "source_type": next(iter(sources)),
              "currency": document["series"][0]["currency"], "calendar": {k: v for k, v in document["calendar"].items() if k != "timestamps"},
              "cash_return_per_period": cash, "alignment": alignment_info, "series": histories,
              "comparison": comparison, "benchmark": benchmark, "portfolio": portfolio, "uncertainty": uncertainty,
              "selection_adjustment": {"status": "not_implemented", "deflated_sharpe": None,
                                       "search_trials": document.get("search_trials"),
                                       "search_trials_status": "unknown" if document.get("search_trials") is None else "user_declared_unverified",
                                       "note": "Unknown search counts are not zero. A declared count is disclosed but no selection correction is computed."},
              "warnings": warnings,
              "scope": "Local descriptive version and fixed-portfolio comparisons. No official SharpeBench score, eligibility decision, skill certification or trading execution."}
    # Guarantee interoperable JSON; accidental NaN/Infinity is an implementation error.
    json.dumps(result, allow_nan=False)
    return result
