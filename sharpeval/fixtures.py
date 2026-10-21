"""Reproducible teaching examples. All streams are generated, never market data."""

from datetime import datetime, timedelta, timezone
import random

from .validation import InputError, integer

SCENARIOS = ("complementary", "leveraged-beta", "lucky-outlier", "duplicate")


def make_fixture(scenario="complementary", periods=252, seed=20261021):
    if scenario not in SCENARIOS:
        raise InputError("unknown synthetic scenario")
    integer(periods, "periods", 8, 3000)
    integer(seed, "fixture seed", 0, 2**63 - 1)
    rng = random.Random(seed)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    grid = [(start + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(periods)]
    market, diversifier, carry = [], [], []
    factor, independent = 0.0, 0.0
    for _ in grid:
        factor = 0.55 * factor + rng.gauss(0, 0.007)
        independent = 0.35 * independent + rng.gauss(0, 0.004)
        market.append(0.0004 + factor)
        diversifier.append(0.0003 - 0.65 * factor + independent)
        carry.append(0.0002 + 0.3 * factor + rng.gauss(0, 0.003))
    old = [0.8 * x + 0.0001 for x in market]
    if scenario == "complementary":
        new = diversifier
    elif scenario == "leveraged-beta":
        new = [2 * x for x in market]
    elif scenario == "duplicate":
        new = list(old)
    else:
        new = list(old)
        new[periods // 2] += 0.30
    def history(sid, agent, version, values, cost=0.0002, annotation=None):
        return {"id": sid, "agent_id": agent, "version": version, "source_type": "backtest",
                "frequency_seconds": 86400, "unit": "decimal", "currency": "USD", "return_basis": "gross",
                "costs": {"included": ["synthetic_fee", "synthetic_slippage"], "excluded": ["tax", "infrastructure"],
                          "notes": "Synthetic fixed cost per period, measured against start-of-period equity. No market or execution calibration."},
                "observations": [dict({"timestamp": t, "return": round(r + cost, 12), "cost": cost},
                                       **({"annotation": annotation} if annotation and i == periods // 2 else {}))
                                 for i, (t, r) in enumerate(zip(grid, values))]}
    return {"schema_version": 1, "title": f"SYNTHETIC • {scenario} • fixture seed {seed}", "synthetic": True,
            "calendar": {"frequency_seconds": 86400, "periods_per_year": 365, "timestamps": grid,
                         "notes": "Synthetic daily 24/7 calendar. Every listed timestamp ends one prior daily period; no market holidays."},
            "cash_return_per_period": 0.0, "search_trials": None,
            "series": [history("agent-v1", "demo-agent", "v1", old),
                       history("agent-v2", "demo-agent", "v2", new,
                               annotation="Generator injected a one-period +30 percentage-point shock. This is known construction, not inferred causality." if scenario == "lucky-outlier" else None),
                       history("market", "synthetic-market", "reference-1", market, 0),
                       history("existing-trend", "existing-trend", "v1", old),
                       history("existing-carry", "existing-carry", "v1", carry)],
            "comparison": {"old": "agent-v1", "new": "agent-v2"}, "benchmark": "market",
            "portfolio": {"weights": {"existing-trend": 0.7, "existing-carry": 0.3}, "candidate_weight": 0.25,
                          "rebalance": "each_period", "overlay_cost_per_period": 0.00002,
                          "overlay_cost_notes": "Synthetic extra 0.2 bp per period for the added allocation/rebalance, for both versions.",
                          "weights_declared_before_evaluation": True}}
