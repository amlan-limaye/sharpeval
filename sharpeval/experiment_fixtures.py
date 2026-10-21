"""Original synthetic v2 experiments, with an explicit planned-run matrix."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import random
import statistics

from .validation import InputError, integer

EXPERIMENT_SCENARIOS = ("repeated", "missing-runs", "overlap", "serial", "nonnormal", "lucky-search")


def selection_spec(run_id):
    return {"target_run_id": run_id, "benchmark_sharpe_per_period": 0.0, "sharpe_unit": "per_period",
            "assumptions": {"serial_independence": "assumed", "stationarity": "assumed",
                            "finite_fourth_moment": "assumed", "normal_trial_sharpes": "assumed",
                            "comparable_trial_sharpes": "assumed"},
            "notes": "SYNTHETIC generator assumptions only, not verified market properties.",
            "search": {"observed_trial_count": 1, "effective_independent_trials": 1,
                       "completeness": "complete", "dispersion_source": "unknown",
                       "trial_sharpe_std_per_period": None, "trial_sharpes": None, "selected_trial_id": None,
                       "null_mean_sharpe_per_period": 0.0,
                       "notes": "One predeclared synthetic candidate. Execution seeds are not automatically counted as strategy trials."}}


def make_experiment_fixture(scenario="repeated", periods=120, seed=20261021):
    if scenario not in EXPERIMENT_SCENARIOS:
        raise InputError("unknown repeated-run fixture scenario")
    integer(periods, "periods", 20, 1000)
    integer(seed, "fixture seed", 0, 2**63 - 1)
    rng = random.Random(seed)
    document = {"schema_version": 2, "title": f"SYNTHETIC • {scenario} • fixture seed {seed}", "synthetic": True,
                "agent_id": "synthetic-agent", "versions": {"old": "v1", "new": "v2"},
                "evaluation": {"source_type": "backtest", "frequency_seconds": 86400, "periods_per_year": 365,
                               "unit": "decimal", "currency": "USD", "cash_return_per_period": 0.0,
                               "notes": "Synthetic 24/7 daily records; paired versions share the window and execution seed. Costs and allocation rules are declared before generation."},
                "seed_ids": ["seed-1", "seed-2", "seed-3"], "windows": [], "runs": [], "selection": []}
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    costs = {"included": ["synthetic_fee", "synthetic_slippage"], "excluded": ["tax", "infrastructure"],
             "notes": "Synthetic fixed period cost; no execution calibration."}
    def payload(dates, returns):
        return {"return_basis": "gross", "costs": deepcopy(costs),
                "observations": [{"timestamp": t, "return": round(r + 0.0002, 12), "cost": 0.0002} for t, r in zip(dates, returns)]}
    window_count = 1 if scenario == "lucky-search" else 2
    if scenario == "lucky-search":
        document["seed_ids"] = ["seed-1"]
    # The same calendar date has the same generated reference market value even in overlapping windows.
    market_values = {}
    factor = 0.0
    for i in range(periods * 2):
        factor = (0.85 * factor if scenario == "serial" else 0.0) + rng.gauss(0, 0.006)
        market_values[i] = 0.0003 + factor
    for wi in range(window_count):
        offset = wi * (periods // 2 if scenario == "overlap" else periods)
        dates = [(start + timedelta(days=offset + i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(periods)]
        wid = f"window-{wi + 1}"
        reference = {"id": "existing", "agent_id": "synthetic-existing", "version": "fixed-1", "source_type": "backtest",
                     "frequency_seconds": 86400, "unit": "decimal", "currency": "USD", **payload(dates, [market_values[offset+i] for i in range(periods)])}
        window = {"window_id": wid, "timestamps": dates, "notes": "Declared synthetic daily sessions; overlapping windows are deliberately not independent.",
                  "reference_series": [reference], "benchmark": "existing",
                  "portfolio": {"weights": {"existing": 1.0}, "candidate_weight": 0.25, "rebalance": "each_period",
                                "overlay_cost_per_period": 0.00002, "overlay_cost_notes": "Synthetic constant added allocation cost of 0.2 bp/period.",
                                "weights_declared_before_evaluation": True}}
        document["windows"].append(window)
        for sid in document["seed_ids"]:
            old, new = [], []
            for i in range(periods):
                shared_noise = rng.gauss(0, 0.001)
                base = market_values[offset+i] + shared_noise
                old.append(base)
                shock = (-0.03 if rng.random() < 0.04 else 0.0013) if scenario == "nonnormal" else rng.gauss(0, 0.0015)
                new.append(base + 0.00015 + shock)
            for version, values in (("v1", old), ("v2", new)):
                document["runs"].append({"run_id": f"{wid}-{sid}-{version}", "window_id": wid, "seed_id": sid,
                                         "version": version, "status": "completed", "history": payload(dates, values)})
    selected_run = document["runs"][1]
    spec = selection_spec(selected_run["run_id"])
    if scenario == "serial":
        spec["assumptions"]["serial_independence"] = "unsupported"
        spec["notes"] = "Generator contains AR(1) memory. Standard PSR/DSR must be withheld, not repaired with invented effective T."
    if scenario == "missing-runs":
        failed = document["runs"][3]
        failed.pop("history")
        failed.update(status="failed", reason="Synthetic execution failure; outcome unknown, not a zero return.")
        document["runs"].pop(4)  # Planned old-version run remains visible as inferred missing.
    if scenario == "lucky-search":
        trials = [[round(rng.gauss(0, 0.01), 12) for _ in range(periods)] for _ in range(100)]
        # Use the final serialized net arithmetic for the ledger, independently of selection.py.
        histories = [payload(document["windows"][0]["timestamps"], values) for values in trials]
        sharpes = []
        for history in histories:
            net = [row["return"] - row["cost"] for row in history["observations"]]
            sharpes.append(statistics.mean(net) / statistics.stdev(net))
        selected = max(range(len(trials)), key=lambda i: sharpes[i])
        selected_run["history"] = histories[selected]
        spec["search"] = {"observed_trial_count": 100, "effective_independent_trials": 100,
                          "completeness": "complete", "dispersion_source": "observed_trial_sharpes",
                          "trial_sharpe_std_per_period": None,
                          "trial_sharpes": [{"trial_id": f"trial-{i+1}", "sharpe_per_period": value} for i, value in enumerate(sharpes)],
                          "selected_trial_id": f"trial-{selected+1}", "null_mean_sharpe_per_period": 0.0,
                          "notes": "All 100 independently generated zero-mean trial streams are counted. The maximum sample Sharpe was chosen on these same periods; this is intentionally synthetic selection bias."}
        spec["notes"] = "The new run is the luckiest of 100 zero-mean generated strategies. This construction demonstrates a selection adjustment, not real skill."
    document["selection"].append(spec)
    return document
