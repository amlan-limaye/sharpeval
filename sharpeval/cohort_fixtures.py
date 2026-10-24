"""Original synthetic cohorts; generator parameters are known, not real agent skill."""

from datetime import datetime, timedelta, timezone
import math
import random

from .cohort import METHOD
from .validation import integer


def make_cohort_fixture(periods=252, seed=20261022, *, scenario="mixed", peer_correlation=0.4, replays=True):
    integer(periods, "periods", 60, 1000)
    integer(seed, "seed", 0, 2**63 - 1)
    if scenario not in ("mixed", "null", "serial", "reused") or not 0 <= peer_correlation < 1:
        raise ValueError("invalid synthetic cohort scenario or peer correlation")
    rng = random.Random(seed)
    timestamps = [(datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(periods)]
    names = ["strong-edge", "modest-edge", "boundary-a", "boundary-b", "zero-edge", "losing-independent"]
    hurdle, sigma, fee = 0.05, 0.01, 0.0001
    # Effects are population net Sharpe values under independent normal sessions.
    effects = [0.30, 0.15, hurdle, hurdle, 0.0, -0.10] if scenario != "null" else [hurdle] * 6
    seeds = ["primary", "replay"] if replays else ["primary"]
    shared = [rng.gauss(0, 1) for _ in timestamps]
    reference = [sigma * rng.gauss(0, 1) for _ in timestamps]
    document = {
        "schema_version": 3, "cohort_id": f"synthetic-{scenario}-{seed}",
        "title": f"SYNTHETIC cohort: {scenario}; fixed world {seed}", "synthetic": True,
        "calendar": {"window_id": "declared-evaluation", "frequency_seconds": 86400, "timestamps": timestamps,
                     "notes": "Synthetic equally spaced sessions, not real market observations or a prospective holdout."},
        "protocol": {"method": METHOD, "hurdle_sharpe_per_period": hurdle, "hurdle_unit": "per_period", "alpha": 0.05,
                     "minimum_observations": 60, "ranking_seed_id": "primary", "currency": "USD", "unit": "decimal",
                     "cash_return_per_period": 0.0, "source_type": "backtest", "return_basis": "gross",
                     "costs": {"included": ["synthetic_fee"], "excluded": [],
                               "notes": "Known teaching fee 0.0001 of starting equity per session. No real execution or calibrated costs."},
                     "assumptions": {"serial_independence": "unsupported" if scenario == "serial" else "assumed",
                                     "stationarity": "assumed", "finite_fourth_moment": "assumed"},
                     "evaluation_status": "reused" if scenario == "reused" else "untouched",
                     "cohort_frozen": "declared", "ranking_execution_frozen": "declared",
                     "risk_limits": {"max_drawdown": 0.8, "max_period_loss": 0.2, "max_peak_exposure": 1.0},
                     "notes": "Controlled simulation: candidates and primary seed fixed before drawing this world. The 0.05 per-session hurdle is an illustrative choice, not a universal economic cutoff."},
        "agents": [{"agent_id": name, "version": "fixed-generator-v1"} for name in names],
        "seed_ids": seeds, "runs": [],
        "reference": {"id": "frozen-independent-reference", "frozen": "declared",
                      "notes": "Exogenous synthetic reference generator, fixed independently of candidate outcomes; not proof of peer independence.",
                      "observations": [{"timestamp": t, "net_return": r} for t, r in zip(timestamps, reference)]},
    }
    for name, effect in zip(names, effects):
        rho = 0 if name == "losing-independent" and scenario != "null" else peer_correlation
        base_noise = [math.sqrt(rho) * common + math.sqrt(1 - rho) * rng.gauss(0, 1) for common in shared]
        if scenario == "serial":
            previous = rng.gauss(0, 1)
            for i in range(periods):
                previous = 0.7 * previous + math.sqrt(1 - 0.7**2) * base_noise[i]
                base_noise[i] = previous
        for execution in seeds:
            # Replays share the same market path and cannot add distinct time.
            noise = base_noise if execution == "primary" else [0.98 * x + 0.02 * rng.gauss(0, 1) for x in base_noise]
            observations = [{"timestamp": t, "return": effect * sigma + sigma * z + fee,
                             "cost": fee, "exposure": 0.75, "peak_exposure": 1.0}
                            for t, z in zip(timestamps, noise)]
            document["runs"].append({"run_id": f"{name}-{execution}", "agent_id": name, "version": "fixed-generator-v1",
                                     "seed_id": execution, "status": "completed", "reason": None, "observations": observations})
    return document
