# Methodology and limits

This is the preserved **schema-1 / v0.1 calculation contract**. For repeated runs and conditional PSR/DSR, use schema 2 and read [the v0.2 extension](methodology-v02.md). Schema-1 outputs deliberately keep their original unimplemented-selection status.

SharpeVal is a descriptive experiment-comparison tool. It asks what changed in imported observations, and what would change under a specified portfolio allocation. It does not certify skill or predict future profit. Its statistics are established methods implemented independently in a small Python core.

## 1. One comparable sample

Every participating history is aligned to one producer-declared session calendar and one common contiguous window. Optional benchmark/portfolio histories can shorten that window only with explicit intersection alignment. There is no silent filling or stitching across missing sessions. Costs, currencies, frequency, source type, version identity and excluded coverage are recorded. Strict validation is necessary but cannot establish that the underlying data are accurate or free from leakage.

The producer must supply simple, time-weighted equity returns with a consistent starting-equity denominator and no capital flows. All figures describe the retained periods only, even if longer input histories are available.

## 2. Net performance and risk

For period `t`, gross return `g_t` and declared cost fraction `c_t`, `r_t = g_t - c_t`. A supplied net return is used unchanged; known cost is only used to reconstruct gross performance as `g_t = r_t + c_t`.

- Net wealth starts at `W_0 = 1`; `W_t = W_(t-1) * (1 + r_t)`. Total return is `W_n - 1`.
- Arithmetic mean is `sum(r_t) / n`.
- Sample volatility uses denominator `n-1`.
- Per-period Sharpe is `(mean(r) - declared_constant_cash_return) / sample_stdev(r)`. It is unavailable with fewer than two observations, zero variance or a ratio beyond numeric range.
- Maximum drawdown is `max_t(1 - W_t / max(W_0, …, W_t))`, reported as a positive loss magnitude. Initial equity is included in the peak.
- Lag-one Pearson correlation and first/second-half means are descriptive stability checks, not formal stationarity tests.
- The largest absolute paired period difference and the mean difference with that one observation excluded expose single-period sensitivity. The primary calculation retains every period.

Wealth is calculated using log compounding to reduce numeric overflow. Unrepresentable totals or chart points become null; no NaN/Infinity is serialized. Extremely small positive wealth can round to zero; the bankruptcy flag specifically records an observed return of `-1`. Exactly `-1` is absorbing bankruptcy. Later nonzero returns are rejected because the starting-equity return convention cannot model a recapitalization. Portfolio calculations involving a bankrupt component/version and all resampling involving bankruptcy are withheld.

Known cost fractions are disclosed as means/sums, and gross and net compound returns are displayed separately. Summing fractions of changing equity is **not** a dollar total or a directly subtractable compounded wealth drag. Costs omitted by a producer remain omitted, with the exclusion displayed. A net series with unknown cost amounts can still be compared, but its cost and gross aggregates are null.

With declared `P = periods_per_year`, geometric annual return is `W_n ** (P/n) - 1`, arithmetic annual mean is `P*mean(r)`, volatility is `sqrt(P)*stdev(r)`, and Sharpe is `sqrt(P)*Sharpe_period`. Without `P`, all annualized metrics are null. The volatility/Sharpe scaling assumes uncorrelated, stable returns; it is conventional display scaling, not a dependence correction. Short-window annualization magnifies estimation noise. Primary results stay per period.

## 3. Paired uncertainty preserving dependence

The primary estimand is the difference in average per-period net return, **new minus old**. Other reported contrasts are differences in compounded return over `n` periods, volatility, maximum drawdown and Sharpe. These path/ratio statistics are secondary descriptive resampling diagnostics, with less reliable finite-sample coverage than the mean, especially near zero variance or bankruptcy.

The implementation uses a **paired circular moving-block percentile bootstrap**, not an independent-observation bootstrap or SharpeBench's stationary-bootstrap significance test:

1. Select a random start from `0 … n-1`, uniformly with replacement.
2. Take `L` consecutive rows, wrapping the last row to the first. Repeat starts until `n` rows have been selected; truncate the final block to exactly `n` rows.
3. Apply that **same index sequence** to every version, benchmark and portfolio constituent. Fixed-weight net portfolios are linear row functions, so resampling their precomputed rows is exactly equivalent to rebuilding them from the jointly resampled constituents.
4. Recompute all compared statistics and their paired differences. For confidence level `C`, report the empirical `(1-C)/2` and `(1+C)/2` quantiles with linear interpolation at index `(B-1)*q`.

The RNG is a dedicated `random.Random(seed)`. Defaults: `B=2000`, confidence `0.95`, seed `42`. Reproducibility is specified for the recorded Python runtime and engine version; do not assume byte-identical behavior across future runtime implementations.

If no block length is supplied, use `max(2, round(n**(1/3)))`, explicitly labelled a heuristic. Every run also reports sensitivity at the unique lengths `max(2, floor(L/2))`, `L`, and `min(10000, 2L)`. Each sensitivity run restarts the same seed for reproducibility. Do not choose the most favorable length after inspecting intervals.

Intervals are withheld when `n < max(20, 4L)`. This operational floor avoids obviously unsupported settings; it is **not** a validated effective sample-size threshold. The displayed `n/L` is an approximate number of blocks, not a measured number of independent observations. A chosen length may fail while shorter sensitivity settings still produce intervals; the primary remains unavailable and is not silently replaced.

No undefined resample is silently discarded. If a statistic is undefined in the original sample or any draw, its interval is unavailable, with the valid-draw count and reason. This matters for zero-variance Sharpe/correlation samples and wealth overflow. A degenerate interval (for example identical agents yielding exact zero difference) describes that empirical structure; it does not guarantee future equivalence.

The procedure assumes approximate joint stationarity and dependence adequately captured within blocks. It retains contemporaneous cross-agent correlation and short-range time order, but it breaks dependence at block joins and introduces a circular end/start join. It cannot recreate unseen crises, regime changes, structural strategy drift, changing liquidity, long memory or execution failures. Too-short blocks understate long dependence; too-long blocks give few independent starts. Percentile intervals are neither bias-corrected nor studentized. `B` controls Monte Carlo noise, not how much independent history exists; this version does not estimate interval-endpoint Monte Carlo error.

Intervals are **pointwise and unadjusted** for inspecting multiple metrics, pairs, parameter settings or searched strategies. A 95% interval is not a 95% probability of future outperformance or a skill certificate. No p-value, winner label or pass/fail decision is emitted. Drawdown/compounded-return intervals describe resampled historical paths of this length, not a calibrated distribution of the next `n` periods.

Block resampling is established prior work, including [Künsch (1989), *The Jackknife and the Bootstrap for General Stationary Observations*](https://projecteuclid.org/journals/annals-of-statistics/volume-17/issue-3/The-Jackknife-and-the-Bootstrap-for-General-Stationary-Observations/10.1214/aos/1176347265.full). SharpeVal's exact circular paired algorithm is specified above and tested against an independent small percentile calculation; no third-party implementation is embedded.

## 4. Exposure and portfolio contribution

Pearson correlations are computed on aligned net returns. A constant series has undefined correlation. The optional benchmark regression is ordinary least squares:

`agent_t - cash = intercept + beta * (benchmark_t - cash) + residual_t`

At least three periods and a variable benchmark are required. Beta identifies sample association with the supplied benchmark; the intercept is not causal attribution and does not establish alpha. Omitted factors, nonlinear exposure and a poor benchmark can all mislead. No confidence interval or significance test for the regression is supplied in v1.

For predeclared long-only funded weights `w_i` summing to one, candidate allocation `a` and extra portfolio-level cost `k`:

```text
base_t       = sum_i(w_i * constituent_net_i,t)
with_old_t   = (1-a) * base_t + a * old_net_t - k
with_new_t   = (1-a) * base_t + a * new_net_t - k
```

Weights reset every period; this is a hypothetical constant-mix rule. Existing positions shrink proportionately to fund the candidate. Constituent trading costs are already deducted, so only `k` is newly subtracted. `k` is explicitly declared even if zero; no execution model estimates it. V1 assumes the same constant overlay cost for both versions. Buy-and-hold drift, varying overlay costs, leverage/short weights and optimization are unsupported. A producer can falsely assert that weights were predeclared; the tool cannot verify that claim.

The report shows the base, both additions, each addition versus base, and new versus old at the same allocation, with paired uncertainty. Correlation is displayed alongside changes in outcomes. A duplicated stream can have no benefit when added to an identical base; a low-correlation losing stream can lower risk but destroy return. Neither correlation nor portfolio improvement alone establishes independent predictive skill.

## 5. Evidence still missing

Deflated Sharpe, search-trial dispersion, multiplicity adjustment, repeated-run aggregation and out-of-sample experiment management are **not implemented**. Unknown search counts stay null/unknown; a provided positive count is merely disclosed. Do not concatenate repeated executions of the same market period as extra time observations. Duplicate timestamps are rejected; disjoint histories from different experiments must not be disguised as one stationary track.

All historical input quality, cost realism, evaluation freezing and held-out collection remain user responsibilities. Optional decision/trade annotations are displayed as producer text. Returns alone cannot establish why a change occurred. Synthetic fixtures and their tests establish only specific implementation behavior. They cannot validate real-world skill, market capacity or future profitability.
