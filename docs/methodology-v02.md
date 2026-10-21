# v0.2 methodology: runs, market time and selection

These are three distinct questions. A seed changes an agent execution; a market window changes the observed environment; a strategy search changes which result is shown. SharpeVal reports each separately. A favorable value in one section does not establish the others.

The original net-performance, fixed-weight portfolio and temporal-block calculations remain as documented in [schema-1 methodology](methodology.md). All v0.2 examples are synthetic; testing their designed properties establishes no real-world predictive skill.

## Repeated runs: declared matrix, descriptive execution spread

The input declares two versions, seed identities and window calendars before listing results. Each window × seed × version cell is planned. An absent cell becomes `missing`; explicit failures retain their reasons. Zero is a return, never a substitute for an unknown result. Partial histories must not masquerade as completed runs: the bounded schema accepts complete histories or a failed/missing status. Keep partial execution artifacts separately.

Old and new are paired by the same declared window and seed. A seed label is a producer's pairing claim; the tool cannot verify that the agents actually shared random numbers or equivalent evaluation conditions. Each completed run has its own net/risk/cost metrics. Each complete pair has observed new-minus-old changes. These are descriptive; run-specific confidence intervals are not supplied.

For each metric and window, the report shows mean, median, range and sample standard deviation across observed executions or complete pairs. Standard deviation uses `K-1`, but **is not a standard error** and does not assume the runs are independent. With one value it is unavailable. If any supplied value is undefined, that metric summary is unavailable rather than silently excluding it. Missing runs remain in the coverage table; any remaining complete-case dispersion is labelled potentially survivor-biased. There is no inferential across-seed average or seed-based confidence interval.

## One conditional mean-execution path per complete window

Only when every planned pair in a window is complete, no execution is bankrupt and each version's cost coverage/notes are consistent across seeds:

```text
mean_path[version, t] = sum(net_return[version, seed, t] for every planned seed) / K
```

Costs are first handled once for each run: gross minus cost, or unchanged supplied net. Cost disclosure on the mean path is the arithmetic mean at that timestamp when every seed's cost is known; otherwise it is unknown. Gross and net representations of the same net data therefore produce identical aggregate paths. Different realized cost amounts across seeds are allowed; different declared coverage/notes within a version withhold its window aggregate. Versions can have different costs, which remain disclosed.

The path is a **summary conditional on the observed executions**. Its compounded wealth is neither the average compounded wealth of a single execution nor a promised deployable portfolio of seeds. Averaging returns before applying a nonlinear metric can give a different result from averaging that metric across runs; both views are shown with different labels.

The temporal sample size remains `T` market periods, never `T × K`. Circular moving-block intervals apply one shared sequence of timestamp indexes to the old/new mean paths, references and fixed-rule portfolios. Pointwise seed averaging commutes with applying that same index sequence to all seeds, preserving their joint timestamp dependence. Seeds are not independently resampled. This addresses market-time variability conditional on the observed execution sample; it does not propagate uncertainty about which executions would occur in the future.

The original block-length sensitivity, artificial circular joins, pointwise interval interpretation and stationarity limits still apply. A missing/failed run or bankruptcy withholds the affected window's aggregate, so it cannot disappear through averaging. Identical paired paths are listed; duplicating every seed leaves the temporal input and intervals unchanged. Unevenly duplicating some seeds changes the declared equal-weight mixture and is not corrected automatically.

Every window remains separate, even when dates are disjoint. Overlap is measured from explicit period-end timestamps; shared dates count once in the coverage union. Incompatible timestamp-grid phases are rejected because shared intervals would otherwise be ambiguous. There is no pooled statistic, across-window confidence interval, meta-analysis, deduplicated profit series or implied independent number of market experiments. The union count measures planned coverage, not a statistical sample size.

## Conditional PSR and DSR definitions

The published PSR/DSR definitions use a Sharpe estimate and a comparison bar. For `T` excess returns, Sharpe `s`, skewness `g3`, non-excess kurtosis `g4`, and bar `b`, SharpeVal independently implements:

```text
V = 1 - g3*s + (g4-1)*s*s/4
PSR(s, b) = Phi((s-b)*sqrt(T-1)/sqrt(V))
```

For `N >= 2` independent, zero-centered Normal trial Sharpe estimates with standard deviation `sigma`, the expected-maximum approximation gives:

```text
b(N) = sigma * [(1-gamma)*Phi_inverse(1-1/N)
               + gamma*Phi_inverse(1-1/(N*e))]
DSR = PSR(s, b(N)); gamma = 0.5772156649015329
```

`N=1` has bar exactly zero and requires no trial dispersion or extreme-value Normal approximation. DSR then equals PSR against zero; it need not equal a PSR requested against a different bar. These definitions and the original nonnormal example are from Bailey & López de Prado, [PSR (2012)](https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf) and [DSR (2014), equations (1)–(2)](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

## SharpeVal's calculation contract and availability rules

All selection ratios and trial dispersions are **per period**. The CLI does not infer conversion from annualized values or substitute the expected sample variance of a Sharpe estimate for supplied search dispersion. For a separately justified annual-to-period conversion, the SR and its standard deviation would both divide by `sqrt(periods_per_year)`; the variance would divide by `periods_per_year`. A known period count does not establish that square-root scaling is valid.

For the named completed run, excess returns subtract the declared constant cash return. Sharpe uses sample standard deviation (`ddof=1`). Empirical skewness and kurtosis use population central moments `m_k = sum((x-mean)^k)/T`, with `g3=m3/m2^(3/2)` and `g4=m4/m2^2`. Normal kurtosis is **3**, not 0. There is no finite-sample moment bias adjustment. The variance expression is evaluated at the observed Sharpe (the published plug-in form), not at the bar. A nonpositive or unrepresentable variance factor is unavailable; no denominator flooring is used.

PSR requires an actual named run with at least 20 periods, nonzero variance, no bankruptcy, and explicit assumptions of serial independence, stationarity and a finite fourth moment. The 20-period requirement is an operational floor, not a sufficiency claim. Estimates from short, skewed or heavy-tailed samples may be unstable even when all fields are present. Repeated execution averages are not valid selection targets in v0.2.

The output is an approximate Normal tail area, equivalently one minus the corresponding plug-in one-sided p-value **conditional on the stated model and assumptions**. It is not a posterior probability of skill, odds of future profit, or a paired version-improvement test. There are no thresholds, pass/fail stages or composite scores. Inspect the bar, uncertainty, data coverage and assumptions alongside the scalar.

### Serial dependence

The standard time-series formula is not serial-correlation robust. SharpeVal computes Pearson lag correlations of both returns and squared centered returns for lags `1..min(10,floor(T/5))`. Any absolute correlation above `3/sqrt(T)` withholds standard PSR/DSR. This prespecified heuristic also catches some volatility clustering. It is not a calibrated hypothesis test, and its lack of a flag does not establish independence, stationarity or finite moments. It can miss dependence beyond its lags or detect chance correlations. An `unknown` or `unsupported` producer assumption also withholds results even if the screen is quiet.

No effective-time-sample-size correction is invented. The actual `T` is always shown. This refusal applies to PSR/DSR, while paired temporal-block diagnostics remain separately available under their own assumptions.

### Search history and dispersion

- `observed_trial_count` records the declared number of attempted strategies or selection alternatives, including failed/undefined outcomes. It is not inferred from the run matrix. A seed may be just an execution replicate; selecting the best seed, window or cost convention can itself create selection trials. The producer must account for the actual search.
- `effective_independent_trials` is a distinct, explicit integer assumption in `[1, observed_trial_count]`. SharpeVal does not estimate it from correlations or use it as an effective market sample size. Fewer effective trials is a stronger modeling choice that weakens the correction; the assumption stays visible.
- DSR requires complete declared search history and a zero-centered trial-Sharpe null. Incomplete or unknown search history, an unknown count, a missing effective count, or an unsupported nonzero null produces unavailable DSR. It does not turn unknown search history into one or zero trials.
- For more than one effective trial, declare comparable trial Sharpes and the Normal trial-Sharpe approximation. Comparability includes period frequency, cash benchmark, cost convention, history length and evaluation protocol. These declarations are not audited. Nonnormal **returns** can still have modeled asymptotically Normal **Sharpe estimates**; those are different assumptions.
- Dispersion is either explicitly assumed, or the sample standard deviation (`ddof=1`) of a supplied complete ledger of trial Sharpe estimates. A ledger must account for every observed attempt, retain null outcomes, identify the selected trial, and match its Sharpe to the target run under the stated convention. Unknown/failed trial outcomes are never removed before measuring dispersion. Missing required dispersion makes DSR unavailable; it is not replaced with zero.
- A supplied/measured dispersion of zero is distinct from unknown and gives a zero selection bar under this degenerate model. It does not establish skill or validate an independence claim. A single effective trial needs no dispersion. Trial correlations, uncertainty in dispersion and moment estimates, and uncertainty in the effective-trial assumption are not propagated.

When a non-null dispersion is used, the report shows sensitivity at one, assumed-effective and observed trial counts while fixing everything else. Increasing `N` cannot improve DSR under this fixed-input formula. This is sensitivity analysis, not a confidence interval for the correct `N`. A search ledger may still be falsely claimed complete; the tool cannot reconstruct unseen attempts, leakage, cherry-picked markets or altered cost assumptions.

## Scope and interpretation

No selection correction is applied to version-change bootstrap intervals, correlations or portfolio metrics. PSR/DSR do not infer alpha relative to an optional risky benchmark. The PSR bar is a supplied Sharpe ratio, the cash rate sets excess returns, and the optional benchmark history is a separate exposure diagnostic. These inputs serve different purposes.

Read individual paths, failed-run coverage, execution spread and window stability before assigning weight to a selection tail area. Predeclared held-out observations remain more useful than converting a short or selected record into a high confidence-looking number. No causal explanation of an agent change is fabricated from returns.
