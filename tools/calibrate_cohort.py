"""Execute the frozen synthetic protocol; retain every planned seed and outcome.

From a checkout: python -m tools.calibrate_cohort --protocol ... --output ...
With SharpeVal installed: python /path/to/tools/calibrate_cohort.py ...
No network, fitted parameters, resampling of rejected worlds or dependencies.
"""

import argparse
from collections import Counter
import hashlib
import inspect
import json
import math
from pathlib import Path
import platform

from sharpeval import rank_cohort
from sharpeval import cohort, cohort_fixtures
from sharpeval.cli import write_files
from sharpeval.cohort_fixtures import make_cohort_fixture
from sharpeval.validation import InputError, integer, load_input, object_fields


def wilson(successes, total):
    """Two-sided 95% Wilson interval for Monte Carlo Bernoulli world counts."""
    if total == 0:
        return {"count": successes, "worlds": 0, "fraction": None, "wilson_95": None}
    z = 1.959963984540054
    p = successes / total
    scale = 1 + z*z/total
    center = (p + z*z/(2*total))/scale
    half = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/scale
    return {"count": successes, "worlds": total, "fraction": p,
            "wilson_95": [max(0.0, center-half), min(1.0, center+half)]}


def validate_protocol(protocol):
    expected = {"protocol_version": "cohort-calibration-v1", "method": "psr_holm_v1",
                "generator": "sharpeval.cohort_fixtures.make_cohort_fixture", "periods": 252,
                "hurdle_sharpe_per_period": 0.05, "alpha": 0.05,
                "population_net_sharpes_mixed": [0.30, 0.15, 0.05, 0.05, 0.0, -0.10],
                "agent_ids": ["strong-edge", "modest-edge", "boundary-a", "boundary-b", "zero-edge", "losing-independent"],
                "sigma_per_period": 0.01, "cost_fraction_per_period": 0.0001, "replays": False}
    object_fields(protocol, {*expected, "scenarios", "outcomes", "notes"}, path="calibration protocol")
    if any(protocol[key] != value for key, value in expected.items()):
        raise InputError("protocol parameters do not match the versioned fixed generator")
    if not isinstance(protocol["scenarios"], list) or not 1 <= len(protocol["scenarios"]) <= 5:
        raise InputError("protocol requires 1..5 explicit scenarios")
    ids, seeds = set(), set()
    for case in protocol["scenarios"]:
        object_fields(case, {"id", "scenario", "peer_correlation", "seed_start", "worlds", "supported"}, path="scenario")
        cohort.identity(case["id"], "scenario.id")
        cohort.choice(case["scenario"], ("mixed", "null", "serial", "reused"), "scenario")
        cohort.bounded(case["peer_correlation"], "peer_correlation", 0, 0.99)
        integer(case["worlds"], "worlds", 1, 10_000)
        integer(case["seed_start"], "seed_start", 0, 2**63-10_001)
        if type(case["supported"]) is not bool or case["supported"] != (case["scenario"] in ("mixed", "null")):
            raise InputError("unsupported stress must be labelled separately")
        if case["id"] in ids:
            raise InputError("duplicate scenario identity")
        ids.add(case["id"])
        planned = set(range(case["seed_start"], case["seed_start"] + case["worlds"]))
        if planned & seeds:
            raise InputError("world seeds overlap across scenarios")
        seeds.update(planned)


def calibrate(protocol, progress=None):
    validate_protocol(protocol)
    names = protocol["agent_ids"]
    output = {"protocol": protocol, "python": platform.python_version(), "source_sha256": {}, "scenarios": []}
    for module in (cohort, cohort_fixtures):
        output["source_sha256"][module.__name__] = hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest()
    output["protocol_sha256_canonical"] = hashlib.sha256(json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    for case in protocol["scenarios"]:
        truths = dict(zip(names, [protocol["hurdle_sharpe_per_period"]]*6 if case["scenario"] == "null" else protocol["population_net_sharpes_mixed"]))
        worlds = []
        for offset in range(case["worlds"]):
            seed = case["seed_start"] + offset
            document = make_cohort_fixture(protocol["periods"], seed, scenario=case["scenario"],
                                           peer_correlation=case["peer_correlation"], replays=protocol["replays"])
            report = rank_cohort(document)  # A failing world stops; it is never replaced.
            agents = []
            for a in report["agents"]:
                agents.append({key: a[key] for key in ("agent_id", "status", "score", "rank", "evidence_qualified",
                                                       "raw_p", "holm_adjusted_p", "family_p_used", "reasons")})
                agents[-1]["observed_sharpe_per_period"] = a["primary"]["metrics"]["sharpe_per_period"]
                agents[-1]["population_net_sharpe"] = truths[a["agent_id"]]
            false = any(a["evidence_qualified"] and truths[a["agent_id"]] <= protocol["hurdle_sharpe_per_period"] for a in agents)
            worlds.append({"seed": seed, "any_false_qualification": false, "agents": agents})
            if progress and ((offset+1) % 50 == 0 or offset+1 == case["worlds"]):
                progress(f"{case['id']}: {offset+1}/{case['worlds']} worlds complete")
        n = len(worlds)
        summaries = {}
        for name in names:
            rows = [next(a for a in w["agents"] if a["agent_id"] == name) for w in worlds]
            summaries[name] = {"population_net_sharpe": truths[name],
                               "qualification": wilson(sum(a["evidence_qualified"] for a in rows), n),
                               "eligibility": wilson(sum(a["status"] == "scored" for a in rows), n),
                               "top_rank": wilson(sum(a["rank"] == 1 for a in rows), n),
                               "rank_histogram": dict(sorted(Counter(str(a["rank"]) if a["rank"] is not None else "unscored" for a in rows).items())),
                               "abstention_reasons": dict(sorted(Counter(reason for a in rows for reason in a["reasons"]).items()))}
        paired, recovered, tied = 0, 0, 0
        for w in worlds:
            by_id = {a["agent_id"]: a for a in w["agents"]}
            strong, modest = by_id["strong-edge"]["rank"], by_id["modest-edge"]["rank"]
            if strong is not None and modest is not None:
                paired += 1
                recovered += strong < modest
                tied += strong == modest
        summary = {"id": case["id"], "supported": case["supported"], "planned_worlds": case["worlds"], "completed_worlds": n,
                   "familywise_false_qualification": wilson(sum(w["any_false_qualification"] for w in worlds), n),
                   "agents": summaries,
                   "strong_above_modest": {"interpretation": "Rank recovery descriptive only; known ordering exists in mixed worlds, not all-null worlds.",
                                           "unconditional": wilson(recovered, n), "both_scored": paired, "ties": tied,
                                           "conditional_on_both_scored": wilson(recovered, paired)},
                   "all_unscored_worlds": sum(all(a["status"] == "unscored" for a in w["agents"]) for w in worlds),
                   "worlds": worlds}
        output["scenarios"].append(summary)
    output["limitations"] = [
        "All worlds and population effects are original synthetic teaching data, not actual agent capability or market evidence.",
        "PSR supplies approximate marginal p-values. Holm controls familywise error only when those p-values are valid; finite simulations cannot prove universal calibration.",
        "All rates include eligibility and positive-wealth gates. Their abstentions reduce power and can reduce familywise error.",
        "Wilson intervals describe Monte Carlo world-count uncertainty, not uncertainty in a real strategy or a posterior probability of skill.",
        "Correlated agents are supported only with valid serially independent marginal returns. Unsupported serial/reused scenarios test refusal, not robust inference.",
        "Rank stability is not a statistical test of pairwise superiority. One window cannot establish repeatable performance across markets or regimes."
    ]
    return output


def markdown(result):
    def rate(value):
        if value["fraction"] is None:
            return "Unavailable"
        lo, hi = value["wilson_95"]
        return f"{value['count']}/{value['worlds']} ({value['fraction']:.1%}; 95% MC interval {lo:.1%}–{hi:.1%})"
    lines = ["# Fixed-world synthetic calibration", "", "Every predeclared world is included. These are known generator effects, not demonstrated real trading skill.", "",
             "The common per-period Sharpe hurdle is 0.05, alpha is 0.05, and each world has six registered candidates and 252 distinct sessions. Primary runs only; no seed pooling.", "",
             "Rank 1 includes ties and does not imply qualification: several agents can share a zero score and rank 1. Rank-1 fractions can therefore sum above 100%.", "",
             "| Scenario | Supported assumptions | Any false qualification | Completed worlds |", "| --- | --- | --- | --- |"]
    for case in result["scenarios"]:
        lines.append(f"| {case['id']} | {case['supported']} | {rate(case['familywise_false_qualification'])} | {case['completed_worlds']} |")
    for case in result["scenarios"]:
        lines += ["", f"## {case['id']}", "", "Qualification is power only for population Sharpe above the hurdle. The other rows are nulls; their qualification is a false positive. Rates include abstentions.", "",
                  "| Agent | Population net Sharpe | Qualified | Eligible | Rank 1 |", "| --- | ---: | --- | --- | --- |"]
        for name, a in case["agents"].items():
            lines.append(f"| {name} | {a['population_net_sharpe']:.2f} | {rate(a['qualification'])} | {rate(a['eligibility'])} | {rate(a['top_rank'])} |")
        paired = case["strong_above_modest"]
        lines += ["", f"Strong-edge ranks above modest-edge in {rate(paired['unconditional'])}; both were scored in {paired['both_scored']} worlds, with {paired['ties']} ties. This is rank recovery only in mixed worlds; all-null agent names carry no effect ordering.",
                  f"All candidates were unscored in {case['all_unscored_worlds']} worlds. Full rank histograms, refusal reasons and every seed are in calibration.json."]
    lines += ["", "## Limits", "", *[f"- {note}" for note in result["limitations"]], "", "## Reproduction fingerprints", "",
              f"Python: {result['python']}. Canonical protocol SHA-256: {result['protocol_sha256_canonical']}.", "", "```json", json.dumps(result["source_sha256"], indent=2), "```", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    targets = [args.output/"calibration.json", args.output/"summary.md"]
    if args.protocol.resolve() in [p.resolve() for p in targets]:
        parser.error("output would overwrite the protocol")
    if not args.force and any(p.exists() for p in targets):
        parser.error("output exists; use a fresh directory or --force")
    protocol = load_input(args.protocol)
    result = calibrate(protocol, progress=lambda message: print(message, flush=True))
    write_files({targets[0]: json.dumps(result, indent=2, allow_nan=False)+"\n", targets[1]: markdown(result)}, args.force)
    print(f"Saved every world and summary in {args.output}")


if __name__ == "__main__":
    main()
