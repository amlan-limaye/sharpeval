# SharpeVal

A small, offline Python tool for developers evaluating trading agents:

1. Which agents show the strongest **conditional evidence above a common, predeclared Sharpe hurdle**, after accounting for selection among the registered cohort?
2. What changed between two versions on the same periods and after declared costs, including fixed-weight portfolio contribution?
3. How much do results vary across executions, and how does a declared strategy search affect a named run's Sharpe evidence?

The new `rank` command gives an inspectable evidence score: **100 × (1 − Holm-adjusted one-sided PSR p-value)**. It uses one frozen execution per agent on one common untouched evaluation window, with explicit assumptions, costs and risk limits. Missing evidence stays unscored. The score is not a probability of skill, pairwise superiority or proof of repeatable future performance. A lucky winner can still pass, and a genuine but modest effect can remain unconvincing.

Consistency (Sharpe), efficiency (return per measured exposure) and independence (correlation to a frozen reference) are shown separately. Only the common-hurdle evidence determines rank. This is **Swing-inspired and independently specified**, not a reproduction of unpublished Swing formulas, weights or windows. Low correlation never improves the score.

The runtime uses only Python's standard library. No AI, subscriptions, network calls, brokerage integrations, credentials or market-data downloads are required. All included data are reproducible **synthetic teaching fixtures**, not market observations or evidence of real-world alpha.

## Install and run

Use an existing Python **3.11 or newer** interpreter. Clone this repository or
extract a source release, then run from its root:

```sh
git clone https://github.com/amlan-limaye/sharpeval.git
cd sharpeval
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/sharpeval --version
.venv/bin/sharpeval fixture-cohort --out output/cohort.json
.venv/bin/sharpeval validate output/cohort.json
.venv/bin/sharpeval rank output/cohort.json --output output/cohort-report
```

If you extracted a release, skip the clone and enter the extracted directory.
Substitute your supported interpreter for `python3`. On Windows use
`.venv\Scripts\python.exe` and `.venv\Scripts\sharpeval.exe`. No environment is
bundled, and no shell activation or global package changes are needed. Installation
may download the declared setuptools build backend; the installed runtime has no
third-party dependencies. The wheel and source distribution are checked with a
fresh install; examples and docs are included in the source distribution.

For an **offline run without installation**, use `python3 -m sharpeval` from the
source directory in place of `.venv/bin/sharpeval`. A virtual environment is
optional for this route; no build backend, package installation or downloads are
needed. For example:

```sh
python3 -m sharpeval fixture-cohort --out output/cohort.json
python3 -m sharpeval validate output/cohort.json
python3 -m sharpeval rank output/cohort.json --output output/cohort-report
```

Read `output/cohort-report/report.html` locally and use `output/cohort-report/report.json` for
programmatic access. The HTML has no JavaScript, remote assets or telemetry.
Use `--force` to repeat an output path. Invalid inputs exit 2 with a reason;
a completed report with insufficient evidence exits 0 and carries explicit
statuses. Check those statuses before interpreting numbers.

The fixture contains six agents with known synthetic effects, two declared
execution seeds and one fixed primary seed. Replays do not add market history.
The [cohort guide](docs/cohort-ranking.md) specifies the score, JSON input contract,
own-data workflow and refusal rules. Schema-3 cohort import is JSON only; the
existing CSV importer remains available for schema-1/2 comparisons.

Choose the command for your JSON input:

| Command | Supported schemas | Result |
| --- | --- | --- |
| `compare` | 1 and 2 | Version-comparison reports, including declared portfolio and repeated-run diagnostics. |
| `rank` | 3 | Cohort evidence-ranking reports. Use this instead of `compare` for a cohort. |
| `validate` | 1, 2 and 3 | A validation summary only; it does not write reports or score agents. |

The [controlled calibration](docs/cohort-calibration.md) runs every one of 1,600
predeclared worlds, including all-null cohorts at the hurdle, correlated agents,
mixed known effects and unsupported stress cases. It reports familywise false
qualification, power, rank stability and Monte Carlo uncertainty. Reproduce it
offline from a checkout or source release:

```sh
python3 -m tools.calibrate_cohort \
  --protocol examples/cohort/calibration-protocol.json --output output/calibration
```

These tests show how the evaluator behaves under known synthetic assumptions.
They do not establish real-agent skill, adoption or universal statistical calibration.

For repeated-run and selection diagnostics:

```sh
.venv/bin/sharpeval validate examples/v02-repeated.json
.venv/bin/sharpeval compare examples/v02-repeated.json \
  --output output/v02-repeated --block-length 6 --resamples 1000 --seed 42
.venv/bin/sharpeval compare examples/v02-lucky-search.json \
  --output output/v02-lucky-search --block-length 6 --resamples 1000 --seed 42
```

The first declares two market windows and three paired execution seeds. The
second deliberately selects the luckiest of 100 synthetic zero-mean strategies.
Other `v02-*.json` examples exercise missing runs, overlapping windows, serial
dependence and nonnormal returns. All are synthetic implementation checks.

## Try the four baseline cases

```sh
.venv/bin/python -m sharpeval fixture --scenario complementary \
  --periods 252 --seed 20261021 --out output/my-synthetic-input.json
.venv/bin/python -m sharpeval compare examples/leveraged-beta.json \
  --output output/leveraged-beta --block-length 8 --resamples 1000 --seed 42
.venv/bin/python -m sharpeval compare examples/lucky-outlier.json \
  --output output/lucky-outlier --block-length 8 --resamples 1000 --seed 42
.venv/bin/python -m sharpeval compare examples/duplicate.json \
  --output output/duplicate --block-length 8 --resamples 1000 --seed 42
```

These scenarios demonstrate leveraged benchmark exposure, a single lucky shock, duplicated agents and constructed complementary streams. Their outcomes are controlled properties of the generator. Passing these tests validates specific implementation behavior, not a strategy's forecasting skill.

## Import your own records

Start with a flat CSV export and a small metadata file that declares your
identities, costs and expected calendar:

```sh
.venv/bin/sharpeval import-csv examples/csv/returns.csv \
  --metadata examples/csv/metadata.json --out output/csv-input.json
.venv/bin/sharpeval compare output/csv-input.json \
  --output output/csv-report --block-length 4 --resamples 200 --seed 42
```

The [CSV walkthrough](docs/csv-import.md) explains how to adapt these files,
interpret row/field errors and verify the example's arithmetic. This synthetic
example has a +7.5 bp/period mean change while both versions have negative mean
net returns. It demonstrates the workflow, not trading edge.

For repeated experiments, the same command accepts [schema-2 CSV exports](docs/csv-experiments.md)
with explicit run/window/seed/version identities and unchanged search metadata:

```sh
.venv/bin/sharpeval import-csv examples/repeated-csv/returns.csv \
  --metadata examples/repeated-csv/metadata.json --out output/repeated-input.json
.venv/bin/sharpeval compare output/repeated-input.json \
  --output output/repeated-report --block-length 6 --resamples 1000 --seed 42
```

The [retrospective synthetic case study](docs/case-study.md) retains a 40-variant
search ledger and three paired executions in each of two windows. Its apparent
gross improvement reverses after declared costs; uncertainty spans zero and DSR
is unavailable because the independent trial count is unknown. A companion export
shows why failed/missing runs withhold an affected window's aggregate. These are
original MIT-licensed teaching data, not market observations or adoption evidence.

Use schema 1 in [the original input contract](docs/input-format.md) for a single pair. `examples/minimal.json` is a compact example; richer examples add a benchmark and existing portfolio. Use [schema 2 and migration notes](docs/schema-v02.md) for explicit runs, seeds, windows and optional selection inputs. No seed identities or search histories are inferred from old files.

Required information includes explicit UTC period ends, an expected session calendar, frequency, decimal simple equity-return units, valuation currency, agent/version identities, live/paper/backtest provenance, return basis and cost coverage. Costs are fractions of equity at the start of each period:

- `gross`: `net_return = return - cost`; each cost is required, including explicit zero.
- `net`: the supplied return is already net. Cost is disclosure, not a second deduction. A `null` cost is permitted and reported as unknown; gross reconstruction is then unavailable.

No frequency conversion, automatic annualization, missing-return filling or timezone guessing occurs. Strict alignment is the default. In schema 1, `--alignment intersection` explicitly permits unequal starting/ending coverage, but still rejects an internal missing session. Schema 2 requires strict coverage of each declared market window. Failed/missing runs stay in the planned matrix. Every participating stream, including benchmark and portfolio members, uses the same window.

## Reuse the analysis core

```python
from sharpeval import analyze, load_input
from sharpeval.report import render_html

document = load_input("examples/complementary.json")
result = analyze(document, block_length=8, resamples=1000, seed=42)
change = result["comparison"]["observed_change"]
interval = result["uncertainty"]["primary"]["contrasts"]["new_minus_old"]["mean_return"]
html = render_html(result)
```

`analyze` validates the document and returns ordinary JSON-compatible objects. It performs no I/O, uses a local random generator and does not modify global random state. Identical inputs/settings on the same supported runtime produce identical report bytes; each report records a canonical input hash, calculation-profile version, Python version and resampling settings. Fixture randomness and bootstrap randomness use separate explicit seeds.

For schema 2, the same API returns `result["runs"]`, `result["pairs"]`, `result["windows"]`, `result["coverage"]` and `result["selection"]`. Each complete window's conditional mean-execution comparison is under `result["windows"][i]["aggregate"]["comparison"]`. Unavailable aggregates contain `comparison: null` and reasons; check statuses before reading numbers.

## What v0.2 covers

- Net compounding, mean return, sample volatility, maximum drawdown, per-period Sharpe against declared constant cash, lag-one correlation, first/second-half means and a one-period difference sensitivity check.
- Optional conventional annualization only when periods per year are supplied. Square-root scaling assumptions are clearly labelled.
- Paired circular moving-block percentile intervals for version and fixed-portfolio differences, using shared row indexes across every stream. Block-length sensitivity is always reported.
- Optional descriptive benchmark beta/intercept and Pearson correlations with the portfolio and its members, with paired block intervals for selected correlations.
- Existing, with-old and with-new portfolios at the same candidate weight, after explicit additional allocation cost; no optimized allocations.
- Missing evidence, unknown search counts, zero variance, bankruptcy and undefined resample statistics are visible in the results.
- Per-run metrics and paired execution dispersion. A complete window has one mean-execution return path, formed at each timestamp, with its original time sample length. Seed dispersion is descriptive; it is never divided by the square root of the seed count or combined with the temporal interval.
- Explicit failed/missing cells and overlapping-window coverage. An affected window aggregate is withheld. Windows are never pooled, including disjoint windows.
- Conditional Probabilistic/Deflated Sharpe diagnostics on named actual runs, with declared time assumptions, a serial-dependence screen, search completeness, observed and assumed independent trial counts, and measured or assumed cross-trial Sharpe dispersion. Missing required information produces unavailable results. No invented effective time sample correction is used.

Read the [original methodology](docs/methodology.md) and [v0.2 methodology and limits](docs/methodology-v02.md). PSR/DSR values are conditional approximate normal-tail areas, **not probabilities that an agent is truly skilled**, future-profit odds, or a paired test of version improvement. They do not correct the bootstrap intervals or all forms of selection bias. Input provenance, search completeness, independence and stationarity are not independently established by this tool.

Schema 1 retains the exact v0.1 compatibility calculation and report, including `selection_adjustment.status="not_implemented"` and its calculation-profile version `0.1.0`. The schema-2 report retains calculation-profile version `0.2.0`. The installed package/CLI is `0.4.0`; schema 3 uses the new `psr_holm_v1` profile. The CSV importer supports schemas 1 and 2 without changing their statistical interpretation. Record `sharpeval --version` alongside report files when tracking the package version.

Excluded: execution, market downloads, strategy search, calendar inference, causal attribution, varying cash rates, currency conversion, short/leverage portfolio weights, recapitalization, cross-window inference, seed-level confidence intervals, and serial-correlation-adjusted PSR/DSR. Conditional statistical qualification in schema 3 is not a prop challenge, funding decision or skill certification.

## Prior work and reuse

[SharpeBench](https://github.com/general-liquidity/sharpebench) was reviewed before implementation. Its methodology already addresses Deflated Sharpe, repeated runs, bootstrap significance and risk constraints. It also explains the boundary between standalone ranking and marginal portfolio contribution. We do not claim those statistics are new, and this tool does not emit its official benchmark score.

This implementation is independent Python code; no SharpeBench source, market datasets, artifacts or dependencies were copied. The PSR/DSR definitions are from Bailey & López de Prado's [PSR paper](https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf) and [DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf). See the [license/methodology review](docs/sharpebench-review.md). This project's MIT license covers its code and original synthetic fixtures; it does not confer rights to imported data.

## Develop and validate

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q sharpeval tests
```

The [read-only CI workflow and local release check](docs/ci.md) run tests, build
both distributions, and exercise clean installs and offline examples outside the
checkout. The hosted matrix targets Linux/Python 3.11 and 3.13 plus Windows/Python
3.13. Check the actual GitHub run before claiming that matrix passed.

Tests include hand-calculated wealth/variance/drawdown/weights, an independent bootstrap percentile oracle, published DSR examples and an independent normal-density quadrature oracle, duplicate seeds, overlapping windows, missing losers, unknown trial inputs, correlated and nonnormal streams, cost accounting, bankruptcy, strict integrity, and end-to-end CLI/report reproducibility. See [v0.2 validation evidence](docs/validation-v02.md) and the [preserved v0.1 record](docs/validation.md). The CSV workflow adds hand-calculated gross/net examples, missing-session and malformed-input cases, overwrite protection and deterministic CLI checks. See [the changelog](CHANGELOG.md). Browser rendering was not verified; HTML structure and numeric content were checked locally.

For a real cohort, freeze the agents, primary execution, calendar, common Sharpe hurdle, cost accounting, risk constraints and assumptions before evaluating fresh data. Preserve every registered candidate and execution, including failures. The tool fingerprints declarations; it cannot independently prove predeclaration or an untouched holdout. More statistics cannot substitute for better experimental records.
