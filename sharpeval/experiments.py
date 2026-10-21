"""Schema v2: explicit run matrix, per-window summaries, no pseudo-replication."""

import hashlib
import json
import math
import platform
from statistics import median, stdev

from .analysis import analyze as analyze_v1, difference
from .bootstrap import METRICS
from .selection import selection_diagnostics, unavailable, validate_selection
from .statistics import diagnostics, mean, wealth_stats
from .validation import InputError, align, integer, number, object_fields, stamp, text, validate as validate_v1

OLD_ID, NEW_ID = "run-old", "run-new"


def _history(document, version, sid, payload):
    protocol = document["evaluation"]
    return {"id": sid, "agent_id": document["agent_id"], "version": version,
            "source_type": protocol["source_type"], "frequency_seconds": protocol["frequency_seconds"],
            "unit": protocol["unit"], "currency": protocol["currency"], **payload}


def _empty_payload(window):
    return {"return_basis": "net", "costs": {"included": [], "excluded": [], "notes": "Validation placeholder only."},
            "observations": [{"timestamp": t, "return": 0, "cost": 0} for t in window["timestamps"]]}


def window_bundle(document, window, old_payload, new_payload):
    protocol = document["evaluation"]
    return {"schema_version": 1, "title": f"{document['title'][:120]} / {window['window_id']}",
            "synthetic": document["synthetic"],
            "calendar": {"frequency_seconds": protocol["frequency_seconds"],
                         "periods_per_year": protocol["periods_per_year"], "timestamps": window["timestamps"], "notes": window["notes"]},
            "cash_return_per_period": protocol["cash_return_per_period"],
            "series": [_history(document, document["versions"]["old"], OLD_ID, old_payload),
                       _history(document, document["versions"]["new"], NEW_ID, new_payload)] + window.get("reference_series", []),
            "comparison": {"old": OLD_ID, "new": NEW_ID}, "benchmark": window.get("benchmark"), "portfolio": window.get("portfolio")}


def validate_experiment(document):
    object_fields(document, {"schema_version", "title", "synthetic", "agent_id", "versions", "evaluation",
                             "seed_ids", "windows", "runs"}, {"selection"}, "experiment")
    integer(document["schema_version"], "schema_version", 2, 2)
    text(document["title"], "title", 200)
    text(document["agent_id"], "agent_id", 120)
    if type(document["synthetic"]) is not bool:
        raise InputError("synthetic must be true or false")
    versions = document["versions"]
    object_fields(versions, {"old", "new"}, path="versions")
    for role in ("old", "new"):
        text(versions[role], f"versions.{role}", 120)
    if versions["old"] == versions["new"]:
        raise InputError("old and new version labels must differ")
    protocol = document["evaluation"]
    object_fields(protocol, {"source_type", "frequency_seconds", "periods_per_year", "unit", "currency", "cash_return_per_period", "notes"}, path="evaluation")
    text(protocol["notes"], "evaluation.notes")
    # Remaining protocol fields are checked by the legacy strict history contract below.
    seed_ids = document["seed_ids"]
    if not isinstance(seed_ids, list) or not 1 <= len(seed_ids) <= 20:
        raise InputError("seed_ids must declare 1..20 planned execution seed identities")
    for sid in seed_ids:
        text(sid, "seed_id", 120)
    if len(seed_ids) != len(set(seed_ids)):
        raise InputError("duplicate seed_id")
    windows = document["windows"]
    if not isinstance(windows, list) or not 1 <= len(windows) <= 8:
        raise InputError("windows must contain 1..8 declared market windows")
    by_window, anchor = {}, None
    for window in windows:
        object_fields(window, {"window_id", "timestamps", "notes"}, {"reference_series", "benchmark", "portfolio"}, "window")
        wid = text(window["window_id"], "window_id", 60)
        if wid in by_window:
            raise InputError("duplicate window_id")
        if "reference_series" in window and not isinstance(window["reference_series"], list):
            raise InputError("reference_series must be a list of schema-1 history objects")
        placeholder = _empty_payload(window) if isinstance(window["timestamps"], list) else {"return_basis": "net", "costs": {}, "observations": []}
        validated = validate_v1(window_bundle(document, window, placeholder, placeholder))
        align(validated, "strict")
        for history in validated.histories.values():
            if history.timestamps != validated.calendar:
                raise InputError("every schema-2 reference history must cover the complete declared window")
            if history.source_type != protocol["source_type"]:
                raise InputError("schema-2 references must share the declared live/paper/backtest source context")
        if window.get("benchmark") in (OLD_ID, NEW_ID) or any(sid in (OLD_ID, NEW_ID) for sid in (window.get("portfolio") or {}).get("weights", {})):
            raise InputError("v2 reference benchmark/portfolio must use reference_series, not a validation placeholder")
        first = stamp(window["timestamps"][0], "window timestamp")
        anchor = first if anchor is None else anchor
        if (first - anchor).total_seconds() % protocol["frequency_seconds"] != 0:
            raise InputError("windows have incompatible timestamp-grid phases; overlapping intervals would be ambiguous")
        by_window[wid] = window
    raw_runs = document["runs"]
    if not isinstance(raw_runs, list) or len(raw_runs) > 2 * len(seed_ids) * len(windows):
        raise InputError("runs must be a list within the declared version × seed × window matrix")
    run_by_cell, run_ids, validated_histories = {}, set(), {}
    observations = 0
    for run in raw_runs:
        object_fields(run, {"run_id", "window_id", "seed_id", "version", "status"}, {"history", "reason"}, "run")
        rid = text(run["run_id"], "run_id", 120)
        for key in ("window_id", "seed_id", "version"):
            text(run[key], f"run.{key}", 120)
        if rid in run_ids:
            raise InputError("duplicate run_id")
        run_ids.add(rid)
        if run["window_id"] not in by_window or run["seed_id"] not in seed_ids or run["version"] not in versions.values():
            raise InputError(f"{rid}: run is outside the declared evaluation matrix")
        cell = (run["window_id"], run["seed_id"], run["version"])
        if cell in run_by_cell:
            raise InputError("duplicate window/seed/version cell; run IDs cannot hide repeated observations")
        run_by_cell[cell] = run
        if run["status"] not in ("completed", "failed", "missing"):
            raise InputError("run.status must be completed, failed or missing")
        if run["status"] != "completed":
            if "history" in run:
                raise InputError("failed/missing runs cannot carry a partial history in v0.2; retain the failure reason explicitly")
            text(run.get("reason"), "failed/missing run.reason")
            continue
        if "reason" in run:
            raise InputError("completed runs use history, not a failure reason")
        payload = run.get("history")
        object_fields(payload, {"return_basis", "costs", "observations"}, path=f"{rid}.history")
        window = by_window[run["window_id"]]
        old_payload = payload if run["version"] == versions["old"] else _empty_payload(window)
        new_payload = payload if run["version"] == versions["new"] else _empty_payload(window)
        checked = validate_v1(window_bundle(document, window, old_payload, new_payload))
        align(checked, "strict")
        validated_histories[rid] = checked.histories[OLD_ID if run["version"] == versions["old"] else NEW_ID]
        observations += len(payload["observations"])
    if observations > 100_000:
        raise InputError("v0.2 accepts at most 100,000 completed run observations per experiment")
    specs = document.get("selection", [])
    if not isinstance(specs, list) or len(specs) > len(run_ids):
        raise InputError("selection must be a list with at most one specification per explicit run")
    selected = set()
    for spec in specs:
        validate_selection(spec)
        rid = spec["target_run_id"]
        if rid not in run_ids or rid in selected:
            raise InputError("selection target must be a unique explicit run_id")
        selected.add(rid)
    return {"document": document, "by_window": by_window, "run_by_cell": run_by_cell, "histories": validated_histories}


def _dispersion(values):
    defined = [v for v in values if v is not None]
    result = {"expected_values": len(values), "defined_values": len(defined), "status": "descriptive_only",
              "mean": None, "median": None, "min": None, "max": None, "sample_std": None,
              "confidence_interval": None}
    if len(defined) != len(values) or not defined:
        result["status"] = "unavailable"
        result["reason"] = "No values or at least one undefined statistic; no silent complete-case metric filtering."
    else:
        result.update(mean=mean(defined), median=median(defined), min=min(defined), max=max(defined),
                      sample_std=stdev(defined) if len(defined) > 1 else None)
    return result


def analyze_experiment(document, *, alignment="strict", block_length=None, resamples=2000, seed=42, confidence=0.95):
    if alignment != "strict":
        raise InputError("schema 2 requires strict complete-session alignment; declare the planned matrix instead of trimming failed coverage")
    validated = validate_experiment(document)
    integer(resamples, "resamples", 200, 10000)
    integer(seed, "seed", 0, 2**63 - 1)
    if block_length is not None:
        integer(block_length, "block_length", 2, 10000)
    if not 0.8 <= number(confidence, "confidence") <= 0.99:
        raise InputError("confidence must be in [0.8,0.99]")
    protocol = document["evaluation"]
    cash, ppy = protocol["cash_return_per_period"], protocol["periods_per_year"]
    versions = document["versions"]
    run_results, pairs, windows, warnings = [], [], [], []
    result_by_id, cell_results = {}, {}
    for window in document["windows"]:
        wid = window["window_id"]
        for sid in document["seed_ids"]:
            for role in ("old", "new"):
                version = versions[role]
                raw = validated["run_by_cell"].get((wid, sid, version))
                result = {"run_id": raw["run_id"] if raw else None, "window_id": wid, "seed_id": sid,
                          "version": version, "role": role, "status": raw["status"] if raw else "missing",
                          "reason": (raw.get("reason") if raw else "Planned run was not supplied."),
                          "metrics": None, "cost_accounting": None, "net_returns": None,
                          "market_time_uncertainty": "Reported only for the complete per-window mean-execution path; no per-run or cross-run confidence interval is inferred."}
                if raw and raw["status"] == "completed":
                    h = validated["histories"][raw["run_id"]]
                    result["metrics"] = diagnostics(h.net, cash, ppy)
                    result["net_returns"] = list(h.net)
                    known = all(v is not None for v in h.cost)
                    result["cost_accounting"] = {"input_basis": h.return_basis, **h.costs,
                        "mean_period_cost_fraction": mean(h.cost) if known else None,
                        "gross_total_return": wealth_stats(h.gross)["total_return"] if known else None,
                        "note": "Gross input costs subtracted once; net input cost disclosures are not deducted again."}
                run_results.append(result)
                cell_results[(wid, sid, version)] = result
                if raw:
                    result_by_id[raw["run_id"]] = result
            old = cell_results[(wid, sid, versions["old"])]
            new = cell_results[(wid, sid, versions["new"])]
            complete = old["status"] == new["status"] == "completed"
            pairs.append({"window_id": wid, "seed_id": sid, "old_run_id": old["run_id"], "new_run_id": new["run_id"],
                          "status": "complete_pair" if complete else "incomplete_pair",
                          "old_status": old["status"], "new_status": new["status"],
                          "observed_change": difference(old["metrics"], new["metrics"]) if complete else None})
    total_budget = 0
    for window in document["windows"]:
        n = len(window["timestamps"])
        length = max(2, round(n ** (1 / 3))) if block_length is None else block_length
        lengths = {max(2, length // 2), length, min(10000, 2 * length)}
        variants = sum(n >= max(20, 4 * v) for v in lengths)
        streams = 2 + len(window.get("reference_series", [])) + (3 if window.get("portfolio") else 0)
        total_budget += n * streams * resamples * variants
    if total_budget > 40_000_000:
        raise InputError("v0.2 experiment exceeds 40-million sampled-cell budget across windows; reduce --resamples or the experiment size")
    for window in document["windows"]:
        wid = window["window_id"]
        wpairs = [pair for pair in pairs if pair["window_id"] == wid]
        completed = [pair for pair in wpairs if pair["status"] == "complete_pair"]
        coverage = {"planned_pairs": len(wpairs), "complete_pairs": len(completed),
                    "incomplete_pairs": len(wpairs) - len(completed)}
        duplicate_groups = {}
        for pair in completed:
            key = json.dumps([result_by_id[pair["old_run_id"]]["net_returns"], result_by_id[pair["new_run_id"]]["net_returns"]], separators=(",", ":"))
            duplicate_groups.setdefault(hashlib.sha256(key.encode()).hexdigest(), []).append(pair["seed_id"])
        dispersion = {"paired_changes": {metric: _dispersion([p["observed_change"][metric] for p in completed]) for metric in METRICS},
                      "versions": {role: {metric: _dispersion([cell_results[(wid, sid, versions[role])]["metrics"][metric]
                                    for sid in document["seed_ids"] if cell_results[(wid, sid, versions[role])]["status"] == "completed"])
                                    for metric in METRICS} for role in ("old", "new")},
                      "scope": "Descriptive spread of observed completed executions; incomplete pairs are listed separately. This is not uncertainty over independent market samples.",
                      "warning": "Complete-case descriptive summaries may be survivor-biased." if coverage["incomplete_pairs"] else "Executions share the same market path and may be correlated; sample_std is not a standard error."}
        withheld = []
        if coverage["incomplete_pairs"]:
            withheld.append("At least one planned paired execution is missing or failed. No aggregate path or interval is computed from survivors.")
        for role in ("old", "new"):
            results = [cell_results[(wid, sid, versions[role])] for sid in document["seed_ids"]]
            complete_results = [r for r in results if r["status"] == "completed"]
            if any(r["metrics"]["bankrupt"] for r in complete_results):
                withheld.append(f"{role}: a completed execution went bankrupt; averaging must not conceal it.")
            policies = [validated["histories"][r["run_id"]].costs for r in complete_results]
            if policies and any(p != policies[0] for p in policies[1:]):
                withheld.append(f"{role}: cost coverage/notes differ across seeds; the execution conditions are not consistently declared.")
        summary = {"window_id": wid, "timestamps": window["timestamps"], "coverage": coverage,
                   "execution_dispersion": dispersion, "identical_pair_seed_groups": [ids for ids in duplicate_groups.values() if len(ids) > 1],
                   "aggregate": {"status": "unavailable", "reasons": withheld, "comparison": None},
                   "market_periods": len(window["timestamps"])}
        if not withheld:
            payloads = {}
            for role in ("old", "new"):
                hs = [validated["histories"][cell_results[(wid, sid, versions[role])]["run_id"]] for sid in document["seed_ids"]]
                records = []
                for i, timestamp in enumerate(window["timestamps"]):
                    costs = [h.cost[i] for h in hs]
                    records.append({"timestamp": timestamp, "return": mean([h.net[i] for h in hs]),
                                    "cost": mean(costs) if all(c is not None for c in costs) else None})
                payloads[role] = {"return_basis": "net", "costs": hs[0].costs, "observations": records}
            result = analyze_v1(window_bundle(document, window, payloads["old"], payloads["new"]),
                                block_length=block_length, resamples=resamples, seed=seed, confidence=confidence)
            # Nested legacy calculation is arithmetic evidence; v2 owns its interpretation.
            result.pop("selection_adjustment")
            result["warnings"] = [w for w in result["warnings"] if not w.startswith("Deflated Sharpe,")]
            summary["aggregate"] = {"status": "conditional_on_observed_executions", "comparison": result,
                "seeds_averaged": len(document["seed_ids"]), "distinct_market_periods": len(window["timestamps"]),
                "rule": "Equal-weight arithmetic mean of net returns across every declared seed at each timestamp, separately for each version.",
                "interpretation": "A mean-execution return path, not expected compounded wealth of one execution or a deployable seed portfolio. Temporal block intervals condition on these observed executions; seed dispersion is not resampled or divided by sqrt(seed count)."}
        windows.append(summary)
    overlaps = []
    for i, left in enumerate(document["windows"]):
        for right in document["windows"][i + 1:]:
            shared = sorted(set(left["timestamps"]) & set(right["timestamps"]))
            if shared:
                overlaps.append({"left_window": left["window_id"], "right_window": right["window_id"],
                                 "shared_periods": len(shared), "timestamps": shared})
    union = set(t for window in document["windows"] for t in window["timestamps"])
    planned = len(run_results)
    coverage = {"planned_runs": planned, "completed_runs": sum(r["status"] == "completed" for r in run_results),
                "failed_runs": sum(r["status"] == "failed" for r in run_results), "missing_runs": sum(r["status"] == "missing" for r in run_results),
                "planned_pairs": len(pairs), "complete_pairs": sum(p["status"] == "complete_pair" for p in pairs)}
    selected = []
    for spec in document.get("selection", []):
        target = result_by_id[spec["target_run_id"]]
        if target["status"] != "completed":
            selected.append({"target_run_id": spec["target_run_id"], "psr": unavailable("Target run is missing or failed."),
                             "dsr": unavailable("Target run is missing or failed."), "search": spec["search"],
                             "assumptions": spec["assumptions"], "notes": spec["notes"]})
        else:
            selected.append(selection_diagnostics(target["net_returns"], cash, spec))
    if coverage["missing_runs"] or coverage["failed_runs"]:
        warnings.append("Missing/failed planned runs are visible. Affected window aggregates are withheld; observed-run dispersion can be survivor-biased.")
    if overlaps:
        warnings.append("Market windows overlap. Shared periods are counted once in the coverage union; windows are not pooled or treated as independent replications.")
    if document["synthetic"]:
        warnings.append("SYNTHETIC: these fixtures test implementation behavior, not real-world predictive skill.")
    warnings.extend(["Run dispersion and market-time intervals answer different questions and must not be combined as if all observations were independent.",
                     "No pooled across-window statistic or confidence interval is produced, even for disjoint windows; regime dependence is not established.",
                     "PSR/DSR are conditional diagnostics for individually named target runs, not paired version tests, future-profit probabilities or skill certificates."])
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    report = {"schema_version": 2, "tool": {"name": "SharpeVal", "version": "0.2.0", "python": platform.python_version()},
              "input_sha256": hashlib.sha256(canonical).hexdigest(), "title": document["title"], "synthetic": document["synthetic"],
              "agent_id": document["agent_id"], "versions": versions, "evaluation": protocol, "seed_ids": document["seed_ids"],
              "coverage": coverage, "runs": run_results, "pairs": pairs, "windows": windows,
              "aggregate": {"status": "by_window_only", "unique_planned_market_periods": len(union),
                            "overlap_pairs": overlaps, "pooled_statistics": None, "across_window_confidence_interval": None,
                            "rule": "No concatenation of seeds or windows; each complete window has one mean-execution path with its original temporal sample length."},
              "selection": {"status": "evaluated" if selected else "not_supplied", "targets": selected,
                            "unrequested_run_ids": [r["run_id"] for r in run_results if r["run_id"] and r["run_id"] not in {s["target_run_id"] for s in selected}]},
              "analysis_settings": {"alignment": alignment, "block_length": block_length, "resamples": resamples, "seed": seed, "confidence": confidence},
              "warnings": warnings, "scope": "Repeated-run evidence and conditional selection diagnostics; no score, certification or trading execution."}
    json.dumps(report, allow_nan=False)
    return report
