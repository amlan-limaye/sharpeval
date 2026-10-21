# SharpeVal

A small, offline Python tool for developers evaluating trading-agent changes:

1. What changed between two versions of the same trading agent, on the same periods and after declared costs?
2. What changes when the new version joins an existing portfolio under fixed, declared weights?
3. How much do results vary across executions, and how does a declared strategy search affect a named run's Sharpe evidence?

The output separates performance, risk, exposure, uncertainty and portfolio contribution. There is no opaque score, leaderboard, eligibility gate or certification of skill. Positive returns and low correlations do not establish predictive ability.

The runtime uses only Python's standard library. No AI, subscriptions, network calls, brokerage integrations, credentials or market-data downloads are required. All included data are reproducible **synthetic teaching fixtures**, not market observations or evidence of real-world alpha.

## Quickstart — no installation or downloads

From this directory, with an existing Python 3.11+ interpreter (tested with Python 3.13.7):

```sh
python3.13 -m venv --without-pip .venv
.venv/bin/python -m sharpeval validate examples/complementary.json
.venv/bin/python -m sharpeval compare examples/complementary.json \
  --output output/demo --block-length 8 --resamples 1000 --seed 42
.venv/bin/python -m unittest discover -s tests -v
```

For the **v0.2 repeated-run and selection diagnostics**:

```sh
.venv/bin/python -m sharpeval validate examples/v02-repeated.json
.venv/bin/python -m sharpeval compare examples/v02-repeated.json \
  --output output/v02-repeated --block-length 6 --resamples 1000 --seed 42
.venv/bin/python -m sharpeval compare examples/v02-lucky-search.json \
  --output output/v02-lucky-search --block-length 6 --resamples 1000 --seed 42
```

The first example declares two market windows and three paired execution seeds. The second deliberately selects the luckiest of 100 synthetic zero-mean strategies. `examples/v02-missing-runs.json`, `v02-overlap.json`, `v02-serial.json` and `v02-nonnormal.json` exercise incomplete coverage, shared periods, serial dependence and skewed returns. All are synthetic implementation checks. Add `--force` when repeating an already generated report path.

The isolated `.venv` is already present in the delivered local workspace. You can skip its creation there. No shell activation or global interpreter/package changes are needed. Substitute your existing supported interpreter for `python3.13` on another machine; on Windows the environment interpreter is `.venv\Scripts\python.exe`.

Open `output/demo/report.html` directly in a browser. It is a standalone local file, with no JavaScript, remote assets or telemetry. Its companion `output/demo/report.json` is structured evidence for downstream tools. Re-running an output path requires `--force`; the input is never intentionally overwritten. CLI errors exit with code 2 and a reason; a completed report with insufficient evidence exits 0 and carries explicit statuses.

You can also run directly with `python3.13 -m sharpeval` from this directory, without a virtual environment. A conventional `pyproject.toml` and `sharpeval` console entry point are provided for packaging. Optional installation into a separately managed environment with pip uses `python -m pip install .`; its setuptools build backend is a build dependency, not a runtime dependency. Packaging via pip was not needed or exercised for this local delivery. Nothing has been published; the local name selection is not a claim of package, domain or trademark availability.

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

`analyze` validates the document and returns ordinary JSON-compatible objects. It performs no I/O, uses a local random generator and does not modify global random state. Identical inputs/settings on the same supported runtime produce identical report bytes; each report records a canonical input hash, engine version, Python version and resampling settings. Fixture randomness and bootstrap randomness use separate explicit seeds.

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

Schema 1 retains the exact v0.1 compatibility calculation and report, including `selection_adjustment.status="not_implemented"` and its calculation-profile version `0.1.0`. The installed package/CLI is `0.2.0`; new features require schema 2. This preserves prior results instead of silently assigning new statistical meaning to them.

Excluded: execution, market downloads, strategy search, calendar inference, causal attribution, varying cash rates, currency conversion, short/leverage portfolio weights, recapitalization, cross-window inference, seed-level confidence intervals, and serial-correlation-adjusted PSR/DSR. There are no prop challenges, profit targets, funding rules or qualification stages.

## Prior work and reuse

[SharpeBench](https://github.com/general-liquidity/sharpebench) was reviewed before implementation. Its methodology already addresses Deflated Sharpe, repeated runs, bootstrap significance and risk constraints. It also explains the boundary between standalone ranking and marginal portfolio contribution. We do not claim those statistics are new, and this tool does not emit its official benchmark score.

This implementation is independent Python code; no SharpeBench source, market datasets, artifacts or dependencies were copied. The PSR/DSR definitions are from Bailey & López de Prado's [PSR paper](https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf) and [DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf). See the [license/methodology review](docs/sharpebench-review.md). This project's MIT license covers its code and original synthetic fixtures; it does not confer rights to imported data.

## Develop and validate

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q sharpeval tests
```

Tests include hand-calculated wealth/variance/drawdown/weights, an independent bootstrap percentile oracle, published DSR examples and an independent normal-density quadrature oracle, duplicate seeds, overlapping windows, missing losers, unknown trial inputs, correlated and nonnormal streams, cost accounting, bankruptcy, strict integrity, and end-to-end CLI/report reproducibility. See [v0.2 validation evidence](docs/validation-v02.md) and the [preserved v0.1 record](docs/validation.md). Browser rendering was not verified; HTML structure and numeric content were checked locally.

The next useful step is a small predeclared held-out evaluation: freeze two agent versions, the cost model, benchmark, weights, calendar and bootstrap settings before collecting fresh data. Record all attempted versions and separate execution runs. More statistics cannot substitute for better experimental records.
