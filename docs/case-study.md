# Case study: a promising gross change does not survive the full comparison

This is an **original synthetic, retrospectively constructed teaching case**,
dated 2026-10-22. It is not real market data, an actual agent run, a prospective
evaluation or evidence of adoption. Its generator and exports are covered by this
repository's MIT license; no third-party data or code is included. The explicit
[provenance file](../examples/repeated-csv/provenance.json) records these limits.

The setting resembles a common development decision: a higher-turnover candidate
looks better before execution costs. A developer tries 40 candidate variants on
one development execution, chooses the highest gross Sharpe, then compares that
same selected version over three execution scenarios in each of two windows.
The [complete walkthrough](csv-experiments.md) reproduces the exports and reports.

## What was constructed

Each window contains 120 synthetic daily sessions. A shared market/baseline
component makes candidate outcomes correlated. Each of 40 variants adds independent
zero-mean noise to that baseline: the generator gives variants **zero population
incremental gross mean**. Choosing the best observed development result therefore
creates an apparent improvement through selection alone.

The baseline's assumed fee/slippage cost is 0.8–1.2 bp/day across executions; the
higher-turnover candidate costs 8–11 bp/day. These are transparent teaching
assumptions, not estimates from a broker, empirical turnover measurements or
realistic upper bounds. Execution scenarios share market paths and have paired
labels and noise. Three executions do not turn 120 market periods into 360
independent observations. Annualization is deliberately unspecified.

Both named windows, including `audit-replay`, are generated in one retrospective
script. The second window does not influence the variant selector, but calling it
a genuine prospective or pre-registered held-out evaluation would be incorrect.
The fixed generator seed reproduces the case; it does not prove that the analysis
was designed before any results were seen.

## Reproduced results

Using `--block-length 6 --resamples 1000 --seed 42` on Python 3.13.7:

| Mean-execution comparison | Development | Audit replay |
|---|---:|---:|
| New minus old gross mean, bp/day | +5.67 | +2.96 |
| Additional mean declared cost, bp/day | 8.33 | 8.33 |
| New minus old net mean, bp/day | **−2.66** | **−5.38** |
| 95% paired temporal-block interval, bp/day | −10.39 to +5.28 | −15.49 to +4.20 |
| Paired net mean changes across the three executions, bp/day | −0.15, −4.69, −3.15 | −3.83, −7.43, −4.86 |

The gross development advantage is smaller than the declared extra cost. Every
observed paired execution has a negative net mean change, yet the temporal-block
intervals span zero. These are conditional descriptive results; they neither prove
that the change is worse in the population nor establish that the assumed cost
model is accurate. The report includes block-length sensitivity, which should be
read alongside the primary interval. The windows are not pooled.

The net PSR for the selected development execution is approximately **0.6892**
under its declared assumptions and the existing dependence screen. It is a
conditional normal-tail area, not a 68.92% probability of skill or a test that the
new version improves on the old.

The search metadata retains all **40 candidate trial Sharpe values**, measured net
on the development execution, even though selection used gross Sharpe. DSR is
**unavailable**: an independent trial count is not supplied, and a normal
trial-Sharpe approximation is not asserted. Shared candidate components make it
misleading to equate 40 observed attempts with 40 independent trials. A complete
ledger is useful evidence, but it does not make those additional assumptions true.

## What happens if results are missing

The companion incomplete export keeps all 12 planned runs while marking one audit
baseline execution failed and its candidate execution missing. Those two histories
are absent from the CSV; their IDs and reasons remain in metadata. The report shows
10 completed runs, one failed and one missing, and withholds that window's
aggregate. It does not let a surviving subset stand in for the planned comparison.
This is a separate missing-evidence demonstration, not an additional observed loss.

## Decision this evidence supports

This case supports checking the cost model, retaining the full search/run record,
and collecting genuinely fresh data under frozen evaluation choices before
claiming an improvement. It does not support deploying a strategy or claiming
predictive edge. IID Gaussian innovations omit volatility clustering, market
impact, financing dynamics, capacity and regime changes; the case is realistic in
its workflow and failure modes, not an empirical model of tradable performance.
