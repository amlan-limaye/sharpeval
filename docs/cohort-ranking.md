# Cohort evidence ranking (schema 3, `psr_holm_v1`)

The question is narrow: **which registered agents have stronger conditional
evidence that their net excess-return Sharpe exceeds the same predeclared hurdle?**
The evaluator is Swing-inspired in its descriptive consistency, efficiency and
independence diagnostics. Its formulas and decisions are independently specified.
It is not an official Swing score or a faithful reconstruction of unpublished
weights, windows or formulas.

## The primary evidence score

Freeze the complete candidate roster, versions, primary execution seed, one common
evaluation window, positive per-period Sharpe hurdle, alpha, cash rate, costs and
risk limits before observing evaluation outcomes. `evaluation_status=untouched`
is a producer assertion; historical data already examined cannot become untouched
by being renamed. The tool does not attest to preregistration or data provenance.

For each eligible primary run, compute sample Sharpe from net simple equity returns
minus the declared constant per-period cash return, with sample standard deviation
(`ddof=1`). Central skewness and non-excess kurtosis use population central moments.
The existing PSR approximation is:

```
z = (observed_Sharpe - common_hurdle) * sqrt(T - 1)
    / sqrt(1 - skew * observed_Sharpe + (kurtosis - 1) * observed_Sharpe**2 / 4)
raw_PSR = Phi(z)
one_sided_p = 0.5 * erfc(z / sqrt(2))
```

The normal tail is computed directly to avoid cancellation from `1 - raw_PSR`.
It is an asymptotic plug-in approximation, not an exact finite-sample test.
Stationarity, serial independence and a finite fourth moment must all be
explicitly assumed. No data screen can establish those conditions. The existing
lag-correlation screen may conservatively withhold PSR for returns or squared
returns; it does not estimate an effective sample size or repair dependence.

Let **M be every registered candidate**, fixed before outcomes. Failed, missing or
ineligible agents retain a p = 1 placeholder for family correction; their displayed
score is null. Sort the M p-values ascending. For sorted position i starting at 1:

```
adjusted_p[i] = min(1, max((M - j + 1) * p[j] for j in 1..i))
score[i] = 100 * (1 - adjusted_p[i])  # eligible candidates only
evidence_qualified = adjusted_p <= alpha
```

This is Holm's step-down correction. It allows arbitrary correlation between
agents **if the marginal p-values are valid**. It does not fix serial dependence,
holdout reuse, omitted candidates or inaccurate declarations. Adding more searched
agents after observing results changes the experiment; silently dropping failed
agents would reduce the penalty and is prohibited. Complete malformed records
cause validation failure rather than silently removing the agent from the family.

Higher scores rank first; exactly equal score values share competition rank
(1, 1, 3). IDs only order the display within ties. Floating-point values very close
to 100 may round to 100; this is not certainty. A valid score of zero is different
from unknown/unscored. Rank does not establish pairwise superiority. This first
version is conditional one-window evidence, not a validated probability of skill
or proof of repeatability across regimes.

The hurdle must be chosen for the specific experiment before evaluation; there is
no universal economically meaningful value. It is strictly positive and per-period.
No automatic annualized-to-period conversion or frequency scaling occurs.
The teaching fixture's 0.05 is an illustrative protocol choice, not advice.

## Eligibility and diagnostic separation

An agent remains unscored when the primary run is failed/missing, the common
holdout is reused/unknown, the roster or primary execution is not declared frozen,
required assumptions are unsupported/unknown, the history is below the declared
minimum (at least 60), moments are invalid, dependence is flagged, costs are
unknown, wealth is bankrupt/overflowed, or a common risk limit cannot be checked
or is exceeded. The minimum is an operational floor, not proof of sufficient data.

The primary run must exceed the compounded common cash comparator, checked in log
wealth. This is a relative net-wealth gate; with negative declared cash returns,
outperforming cash need not mean a positive absolute return. Always inspect the
displayed net total return. No low-correlation bonus can offset a loss or failed gate.

Three descriptive components are separate:

| Component | Definition | Missing evidence |
| --- | --- | --- |
| Consistency | Net excess-return Sharpe per period, with raw PSR and common-hurdle gap | Undefined variance or unsupported PSR stays unavailable |
| Efficiency | Mean net excess return / mean **measured period-average gross exposure** | Unknown, zero or numerically degenerate exposure gives null; no return-volatility proxy |
| Independence diagnostic | Pearson correlation and absolute correlation to one complete frozen external reference | Missing, unfrozen, misaligned or constant reference cannot imply independence |

Exposure is absolute gross notional divided by equity, not net directional
exposure. Supply the time average within the period for efficiency and the measured
maximum within the period for the leverage constraint. A closing holding is not a
substitute for either. Unknown average exposure may leave primary evidence scored
when peak exposure is known; efficiency remains null. Unknown peak exposure
withholds primary ranking because the risk limit cannot be checked.

The reference must be chosen independently of evaluation results. For peer
comparison, supply a benchmark derived from a predeclared external reference
cohort with fixed construction. Do not select the least-correlated reference after
looking at outcomes. This MVP does not construct an optimized or leave-one-out
peer portfolio. Low measured correlation alone does not establish independence.

Optional `agents[].discovery` contains a separate net-return history, constant
cash return and the existing [selection specification](schema-v02.md). Its PSR/DSR
is discovery context only. Unknown trials stay unknown. It never substitutes an
agent-specific DSR hurdle into the common rank or automatically double-penalizes
an untouched holdout for development searches. DSR is never averaged across seeds.

## Export your own cohort

1. Before evaluation, save and independently date the roster, versions, calendar,
   primary seed, planned replay seeds, benchmark/reference construction, cost
   coverage, cash rate, hurdle, alpha, risk limits and assumptions. Keep your actual
   preregistration record; a hash made afterward is not evidence it was frozen earlier.
2. Export period equity returns for **every** registered agent from your simulator
   or recorder under that common setup. Use the same valuation currency, expected
   observation periods and cost policy. Schema 3 accepts JSON; do not pass it to the
   schema-1/2 CSV importer or `compare` command.
3. Record failed/missing executions explicitly. Never replace the primary seed
   with a successful replay. A missing whole planned cell remains in coverage; a
   completed run with a missing timestamp is rejected. No calendar intersection,
   forward fill, identity guessing or survivor-only family is allowed.
4. Run `sharpeval validate your-cohort.json`, then `sharpeval rank your-cohort.json
   --output output/your-cohort`. Invalid input exits 2. A valid all-unscored report
   exits 0; inspect statuses and reasons.
5. Save the JSON input, JSON/HTML report, package version and your original ledger.
   Check net returns, cost coverage, gate reasons, the common hurdle, raw and adjusted
   p-values, effect sizes and failures before interpreting the ranking.

Generate an annotated complete starting example:

```sh
python -m sharpeval fixture-cohort --out output/template.json
python -m sharpeval validate output/template.json
python -m sharpeval rank output/template.json --output output/ranking
```

The template contains **synthetic** values and assertions. Replace its data and
declarations with your actual records; never merely change `synthetic` to false.
All property names are strict; unknown or missing fields are rejected. The package
does not contain a backtester, execute trades or independently audit exposure/costs.

`rank` writes `report.json` and `report.html` in the output directory. It checks
both paths before writing: if either output file exists, the command fails without
writing the other unless `--force` is supplied. `--force` replaces existing report
files, so use a fresh directory to preserve an earlier report. The input cannot be
either output file, and symlinks and directories are refused as output files, even
with `--force`.

## Input field reference

Top-level fields are `schema_version: 3`, `cohort_id`, `title`, `synthetic` (boolean),
`calendar`, `protocol`, `agents`, `seed_ids`, `runs` and `reference`.

- `calendar`: `window_id`, `frequency_seconds`, `timestamps` and `notes`. Supply the
  expected UTC period ends independently of surviving exports, 3–10,000 unique
  ordered entries. Gaps must be whole frequency multiples (for example weekends);
  the tool cannot prove the producer's calendar is complete.
- `protocol`: `method: "psr_holm_v1"`, `hurdle_sharpe_per_period`, `hurdle_unit:
  "per_period"`, `alpha` (0.001–0.1), `minimum_observations` (60–10,000),
  `ranking_seed_id`, `currency` (three uppercase letters), `unit: "decimal"`,
  `cash_return_per_period`, `source_type` (`backtest`, `paper`, `live`),
  `return_basis` (`gross` or `net`), `costs`, `assumptions`, `evaluation_status`
  (`untouched`, `reused`, `unknown`), `cohort_frozen` and `ranking_execution_frozen`
  (each `declared`, `no`, `unknown`), `risk_limits` and `notes`.
- `costs`: unique `included` and `excluded` component-name lists and `notes`.
  Excluded costs remain limitations even when a score is emitted. Per-row cost is
  a fraction of equity at the beginning of the period, not basis points of turnover.
  Convert a notional fee upstream and retain that ledger for audit.
- `assumptions`: `serial_independence`, `stationarity`, `finite_fourth_moment`, each
  `assumed`, `unsupported` or `unknown`. Unsupported assumptions require a different
  statistical method, not a relabelled declaration to force a score.
- `risk_limits`: `max_drawdown`, `max_period_loss` (nonnegative loss magnitudes,
  0–1) and `max_peak_exposure` (0–100). These must be common and predeclared.
- `agents`: 2–100 unique `agent_id` / `version` pairs, optional `discovery`.
  `seed_ids`: 1–10 distinct planned execution identities. Their Cartesian product
  is the planned matrix, limited to 250,000 observation cells.
- `runs`: unique `run_id`, `agent_id`, `version`, `seed_id`, `status`, `reason`,
  `observations`. `status` is `completed`, `failed` or `missing`. Completed records
  require null reason and every calendar row. Failed/missing records require a
  nonempty reason and null observations; keep any partial raw ledger separately.
- Each completed observation: `timestamp`, `return`, `cost`, `exposure`,
  `peak_exposure`. Finite decimal simple returns only. Gross returns require an
  explicit cost including zero, and `net = return - cost`. Net returns are used
  unchanged; known cost is disclosure, never a second subtraction. Net cost may
  be null, making primary ranking unscored. Average/peak exposure may be null,
  with different consequences described above. Average cannot exceed known peak.
- `reference`: null, or `id`, `frozen` (`declared`, `no`, `unknown`), `notes` and
  `observations` (null or full matching `timestamp` / `net_return` rows).

IDs use letters, digits, underscores, dots and hyphens. Version strings may include
longer descriptive identifiers. Individual returns are bounded to [-1, 1000],
cash to [-0.99, 1], exposures to [0, 100] and costs to [0, 1000]. Recapitalization
after bankruptcy is unsupported. These are parser/numeric bounds, not sensible
investment parameters. Annualization, currency conversion and variable cash rates
are not inferred.

## Reproduction, compatibility and references

JSON reports include canonical input and design SHA-256 fingerprints, Python
version, the complete protocol, raw/adjusted p-values, effect sizes, statuses,
all planned execution records and missing reasons. The design fingerprint excludes
observed return values; it identifies declarations, not independent preregistration.
The example and reports are byte reproducible on the same runtime. Different
Python versions may differ in floating-point formatting and runtime metadata.

Schemas 1 and 2 retain their old comparison engines. The new score is not added
to their existing block intervals or used to reinterpret their outputs.
The [calibration record](cohort-calibration.md) and its full retained seeds describe
the narrow statistical validation and its limits.

Primary references: Bailey and López de Prado's [PSR paper](https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf)
and [DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf), and
[R's Holm adjustment documentation](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html).
Equations are independently implemented using the standard library. No third-party
code, private data or market data is added; the project's MIT license covers the
original generator and fixtures, not data a user imports.
