"""Paired circular moving-block percentile intervals, with explicit sensitivity."""

import math
import random

from .statistics import correlation, quantile, snapshot
from .validation import InputError, integer, number

METRICS = ("mean_return", "total_return", "volatility", "max_drawdown", "sharpe_per_period")


def block_indices(n, block_length, rng):
    result = []
    while len(result) < n:
        start = rng.randrange(n)
        result.extend((start + j) % n for j in range(min(block_length, n - len(result))))
    return result


def interval(values, resamples, confidence, estimate):
    valid = [v for v in values if v is not None and math.isfinite(v)]
    # Never condition a percentile interval on the subset where a ratio is defined.
    if len(valid) != resamples or estimate is None:
        return {"status": "unavailable", "estimate": estimate, "lower": None, "upper": None,
                "valid_resamples": len(valid),
                "reason": "Statistic undefined in the observed data or at least one resample (e.g. zero variance or overflow)."}
    valid.sort()
    tail = (1 - confidence) / 2
    return {"status": "available", "estimate": estimate, "lower": quantile(valid, tail),
            "upper": quantile(valid, 1 - tail), "valid_resamples": len(valid),
            "degenerate": valid[0] == valid[-1]}


def paired_bootstrap(streams, contrasts, correlation_pairs, *, cash, block_length=None,
                     resamples=2000, seed=42, confidence=0.95):
    integer(resamples, "resamples", 200, 10_000)
    integer(seed, "seed", 0, 2**63 - 1)
    confidence = number(confidence, "confidence")
    if not 0.8 <= confidence <= 0.99:
        raise InputError("confidence must be in [0.8, 0.99]")
    sizes = {len(values) for values in streams.values()}
    if len(sizes) != 1 or not sizes or next(iter(sizes)) == 0:
        raise InputError("bootstrap needs nonempty aligned streams")
    n = next(iter(sizes))
    automatic = block_length is None
    length = max(2, round(n ** (1 / 3))) if automatic else integer(block_length, "block_length", 2, 10_000)
    lengths = sorted({max(2, length // 2), length, min(10_000, 2 * length)})
    valid_lengths = [v for v in lengths if n >= max(20, 4 * v)]
    if n * len(streams) * resamples * len(valid_lengths) > 40_000_000:
        raise InputError("bootstrap exceeds the v1 40-million sampled-cell budget; reduce --resamples or the input size")
    result = {"method": "paired_circular_moving_block_percentile", "confidence": confidence,
              "seed": seed, "resamples": resamples, "block_length": length,
              "block_length_source": "cube-root heuristic" if automatic else "user declared",
              "minimum_observations_rule": "n >= max(20, 4 * block_length); operational floor, not proof of adequacy",
              "assumptions": ["Ordered observations form one contiguous declared session window.",
                              "Joint dependence is approximately stationary; block length captures relevant dependence.",
                              "One shared index path resamples all agents, benchmark and fixed-rule portfolios.",
                              "Circular blocks wrap last session to first; artificial joins remain at block boundaries.",
                              "Intervals are pointwise, unadjusted for strategy search or multiple comparisons.",
                              "A percentile interval is not a posterior probability, p-value, or skill verdict."],
              "primary": None, "sensitivity": []}
    bankrupt = any(-1 in r for r in streams.values())
    observed = {name: snapshot(values, cash) for name, values in streams.items()}
    for current_length in lengths:
        run = {"block_length": current_length, "approximate_blocks": n / current_length,
               "status": "available", "contrasts": {}, "correlations": {}}
        if bankrupt or n < max(20, 4 * current_length):
            run.update(status="insufficient_data", reason=("Bankruptcy makes return-path resampling unsuitable; recapitalization is unsupported."
                       if bankrupt else f"Only {n} observations; this block length needs at least {max(20, 4 * current_length)}."))
        else:
            draws = {name: {metric: [] for metric in METRICS} for name in contrasts}
            corrs = {name: [] for name in correlation_pairs}
            # Identical seed is deliberate: each sensitivity run is independently reproducible.
            rng = random.Random(seed)
            for _ in range(resamples):
                indexes = block_indices(n, current_length, rng)
                sampled = {name: [values[i] for i in indexes] for name, values in streams.items()}
                stats = {name: snapshot(values, cash) for name, values in sampled.items()}
                for name, (left, right) in contrasts.items():
                    for metric in METRICS:
                        a, b = stats[left][metric], stats[right][metric]
                        draws[name][metric].append(None if a is None or b is None else b - a)
                for name, (left, right) in correlation_pairs.items():
                    corrs[name].append(correlation(sampled[left], sampled[right]))
            for name, (left, right) in contrasts.items():
                run["contrasts"][name] = {}
                for metric in METRICS:
                    a, b = observed[left][metric], observed[right][metric]
                    estimate = None if a is None or b is None else b - a
                    run["contrasts"][name][metric] = interval(draws[name][metric], resamples, confidence, estimate)
            for name, (left, right) in correlation_pairs.items():
                run["correlations"][name] = interval(corrs[name], resamples, confidence, correlation(streams[left], streams[right]))
        if current_length == length:
            result["primary"] = run
        result["sensitivity"].append(run)
    return result
