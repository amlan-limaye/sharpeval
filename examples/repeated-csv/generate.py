"""Original synthetic case study. No market data, network or SharpeVal imports.

Both windows are constructed retrospectively. The generator and all of its output
are covered by the repository's MIT license. The fixed seed is a reproducibility
choice, not evidence of preregistration, prospective performance or real adoption.
"""

import argparse
import copy
import csv
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import random
from statistics import mean, stdev


SEED = 20261022
PERIODS = 120
TRIALS = 40
EXECUTIONS = ("execution-a", "execution-b", "execution-c")
OLD_COSTS = (0.00010, 0.00012, 0.00008)
NEW_COSTS = (0.00080, 0.00110, 0.00090)
COLUMNS = ["run_id", "window_id", "seed_id", "version", "timestamp", "return", "cost", "annotation"]


def sharpe(values):
    return mean(values) / stdev(values)


def build_case():
    windows, bases, candidates, noise = [], {}, {}, {}
    for wi, (wid, start) in enumerate((("development", datetime(2024, 1, 1)),
                                      ("audit-replay", datetime(2024, 6, 1)))):
        windows.append({"window_id": wid,
                        "timestamps": [(start + timedelta(days=t)).strftime("%Y-%m-%dT%H:%M:%SZ") for t in range(PERIODS)],
                        "notes": "SYNTHETIC 24/7 daily sessions; independently declared schedule. Both windows are retrospective constructions, not observed market or prospective data."})
        market_rng = random.Random(SEED + wi * 10000)
        bases[wid] = [0.35 * market_rng.gauss(0.0002, 0.008) + market_rng.gauss(0, 0.0018) for _ in range(PERIODS)]
        candidates[wid] = []
        for trial in range(TRIALS):
            rng = random.Random(SEED + wi * 10000 + 100 + trial)
            candidates[wid].append([round(base + rng.gauss(0, 0.0045), 12) for base in bases[wid]])
        for si, execution in enumerate(EXECUTIONS):
            rng = random.Random(SEED + wi * 10000 + 1000 + si)
            noise[(wid, execution)] = ([rng.gauss(0, 0.0002) for _ in range(PERIODS)],
                                       [rng.gauss(0, 0.0009) for _ in range(PERIODS)])
    def old_values(wid, execution):
        return [round(v + e, 12) for v, e in zip(bases[wid], noise[(wid, execution)][0])]
    def trial_values(wid, execution, trial):
        return [round(v + e, 12) for v, e in zip(candidates[wid][trial], noise[(wid, execution)][1])]

    # This is deliberately a hindsight selection on ONE development execution.
    chosen = max(range(TRIALS), key=lambda i: sharpe(trial_values("development", EXECUTIONS[0], i)))
    version = f"selected-variant-{chosen:02d}"
    runs = []
    for window in windows:
        wid = window["window_id"]
        for si, execution in enumerate(EXECUTIONS):
            for role, values, cost in (("old", old_values(wid, execution), OLD_COSTS[si]),
                                       ("new", trial_values(wid, execution, chosen), NEW_COSTS[si])):
                runs.append({"run_id": f"{wid}-{execution}-{role}", "window_id": wid, "seed_id": execution,
                             "version": "baseline-v1" if role == "old" else version, "status": "completed",
                             "history": {"return_basis": "gross", "costs": {"included": ["assumed_fee_and_slippage"],
                                "excluded": ["tax", "infrastructure"],
                                "notes": "Assumed daily start-equity cost: baseline 0.8–1.2 bp, high-turnover candidate 8–11 bp across execution scenarios. These are teaching assumptions, not measured brokerage costs."},
                                "observations": [{"timestamp": t, "return": v, "cost": cost}
                                                 for t, v in zip(window["timestamps"], values)]}})
    ledger = [{"trial_id": f"variant-{i:02d}", "sharpe_per_period": round(sharpe([v - NEW_COSTS[0] for v in trial_values("development", EXECUTIONS[0], i)]), 12)}
              for i in range(TRIALS)]
    document = {"schema_version": 2, "title": "SYNTHETIC retrospective case: a selected high-turnover change",
                "synthetic": True, "agent_id": "synthetic-turnover-case", "versions": {"old": "baseline-v1", "new": version},
                "evaluation": {"source_type": "backtest", "frequency_seconds": 86400, "periods_per_year": None,
                               "unit": "decimal", "currency": "USD", "cash_return_per_period": 0,
                               "notes": "Retrospective simulation: choose the best gross Sharpe of 40 candidate variants on development execution-a, then replay that same variant. Shared market paths and paired execution labels; no prospective evaluation or real trading."},
                "seed_ids": list(EXECUTIONS), "windows": windows, "runs": runs,
                "selection": [{"target_run_id": "development-execution-a-new", "sharpe_unit": "per_period",
                               "benchmark_sharpe_per_period": 0,
                               "assumptions": {"serial_independence": "assumed", "stationarity": "assumed",
                                               "finite_fourth_moment": "assumed", "normal_trial_sharpes": "unknown",
                                               "comparable_trial_sharpes": "assumed"},
                               "notes": "The generator uses independent Gaussian time innovations, but selection is retrospective. The candidates share the same baseline component; execution seeds are not independent search trials.",
                               "search": {"observed_trial_count": TRIALS, "effective_independent_trials": None,
                                          "completeness": "complete", "dispersion_source": "observed_trial_sharpes",
                                          "trial_sharpe_std_per_period": None, "trial_sharpes": ledger,
                                          "selected_trial_id": f"variant-{chosen:02d}", "null_mean_sharpe_per_period": 0,
                                          "notes": "Complete ledger of this generator's 40 candidate variants, measured NET on development execution-a. Selection used gross Sharpe. Effective independent count is unknown because variants share a market/baseline component. No other search is claimed."}}]}
    return document


def export_files(document):
    metadata = copy.deepcopy(document)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for run in metadata["runs"]:
        if run["status"] == "completed":
            for obs in run["history"].pop("observations"):
                writer.writerow({**{k: run[k] for k in COLUMNS[:4]}, **obs})
    return json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False) + "\n", stream.getvalue()


def case_files():
    document = build_case()
    metadata, returns = export_files(document)
    incomplete = copy.deepcopy(document)
    for role, status in (("old", "failed"), ("new", "missing")):
        run = next(r for r in incomplete["runs"] if r["run_id"] == f"audit-replay-execution-c-{role}")
        run.pop("history")
        run.update(status=status, reason=f"SYNTHETIC {status} record for the missing-evidence demonstration; no partial or zero-filled history supplied.")
    missing_metadata, missing_returns = export_files(incomplete)
    provenance = {"kind": "original synthetic retrospective construction", "license": "MIT; repository LICENSE applies",
                  "third_party_data": False, "real_agent_execution": False, "prospective_evaluation": False,
                  "generator_seed": SEED, "periods_per_window": PERIODS, "candidate_variants": TRIALS,
                  "selected_version": document["versions"]["new"], "executions": list(EXECUTIONS),
                  "population_incremental_gross_mean": 0,
                  "baseline_mean_cost_bp": mean(OLD_COSTS) * 10000, "candidate_mean_cost_bp": mean(NEW_COSTS) * 10000,
                  "construction": "Shared Gaussian market/baseline component; independent zero-mean candidate perturbations; paired execution noise; explicit assumed cost scenarios. No empirical calibration.",
                  "selection": "Maximize development execution-a gross Sharpe across 40 variants. Both windows and the choice are constructed retrospectively.",
                  "limitations": "IID Gaussian time innovations omit market frictions, volatility clustering and regime shifts. Full synthetic search ledger does not establish an independent trial count. No actual adoption or market edge is demonstrated."}
    return {"metadata.json": metadata, "returns.csv": returns,
            "incomplete-metadata.json": missing_metadata, "incomplete-returns.csv": missing_returns,
            "provenance.json": json.dumps(provenance, indent=2, ensure_ascii=False) + "\n"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new output directory; existing directories are refused")
    args = parser.parse_args()
    files = case_files()
    args.out.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        with (args.out / name).open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    print(f"SYNTHETIC retrospective exports written to {args.out}; no real trading evidence.")


if __name__ == "__main__":
    main()
