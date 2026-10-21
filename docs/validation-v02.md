# v0.2 validation record — 2026-10-21

SharpeVal package/CLI `0.2.0`, schema 2, Python **3.13.7** on macOS. The existing isolated `.venv` uses the protected existing Python 3.13 interpreter. Runtime dependencies remain **zero**. No installs, global interpreter/package changes, TLS overrides, credentials, broker connections, publishing or unrelated application/process changes were used. No browser or upload route was retried in this iteration.

## Automated checks actually run

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q sharpeval tests
```

**124 tests passed in 8.989 seconds** in the final workspace run. This includes all **67 unchanged v0.1 tests** and 57 v0.2 tests. Compile checks passed. The full generated local log is `output/v02-test-results.txt`.

The new coverage includes:

- Paper example values and an independent numerical oracle that integrates the Normal density with Simpson quadrature and finds quantiles by bisection. The oracle does not call production formula helpers, `NormalDist`, or `erf` to compute reference values.
- Hand-calculated sample Sharpe, skewness, non-excess kurtosis, cash subtraction and tiny-value scaling; short, constant, bankrupt, nonnormal, serially correlated and volatility-clustered cases.
- Single-trial/zero-dispersion boundaries; unknown/incomplete search, unknown dispersion, missing loser outcomes, incorrect selected-trial identity/value, duplicate attempt IDs and invalid units/counts. More trials never increase DSR with other valid inputs held fixed.
- Explicit run matrix coverage, failures, absent records, paired mean paths, costs counted once, unknown costs, incompatible cost declarations, bankruptcy not averaged away, undefined metrics not discarded, reference integrity, and fixed portfolio arithmetic.
- Correlated executions with descriptive spread only; duplicate seeds leaving the time sample/interval unchanged; overlapping and identical windows without pooled statistics; input immutability and deterministic RNG behavior.
- New CLI fixture/validate/compare flow, schema-2 strict alignment, overwrite refusal, byte-identical forced reruns, escaped imported text, self-contained HTML structure, and a frozen schema-1 JSON/HTML hash comparison.

## Formula cross-checks

The original [Bailey & López de Prado DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) gives the reference model and numerical example. SharpeBench's public implementation/tests were inspected as a cross-check, without copying code. For annual Sharpe `2.5`, 250 periods/year, `T=1250`, annual trial-Sharpe variance `0.5`, skewness `−3` and non-excess kurtosis `10`, both ratios/dispersion are first expressed per period:

| Assumed independent trials | Selection bar per period | Calculated DSR | Published rounded value |
|---:|---:|---:|---:|
| 100 | 0.113172001865 | 0.900396834449 | 0.9004 |
| 46 | 0.100362370618 | 0.950501706876 | 0.9505 |

The Normal-return case with 88 trials also matches its published rounded value `0.9505`. Formula calculations agree with the independent integration oracle to 10 decimal places in these cases and additional skew/heavy-tail cases. Matching a published formula validates this calculation, not its applicability to arbitrary market returns.

## CLI examples actually completed

For each of `repeated`, `missing-runs`, `overlap`, `serial`, `nonnormal`, and `lucky-search`:

```sh
.venv/bin/python -m sharpeval validate examples/v02-repeated.json
.venv/bin/python -m sharpeval compare examples/v02-repeated.json \
  --output output/v02-repeated --block-length 6 --resamples 1000 --seed 42 --force
```

Substitute the scenario name in both paths. All 12 validation/comparison invocations exited 0. Generated `output/v02-cli-results.json` records the exact commands, exit codes and output. Fixture generation uses 120 daily periods/window and seed `20261021`; all histories are synthetic.

| Scenario | Observed behavior |
|---|---|
| Repeated | 12/12 runs, 6/6 pairs, two separate 120-period window paths; the two 95% mean-change intervals include zero. |
| Missing runs | 10/12 completed, one failed and one absent run; first window aggregate withheld, second retained. |
| Overlap | Two 120-period windows share 60 periods; unique planned coverage is 180, with no pooled statistic/interval. |
| Serial | Conditional temporal-block comparison remains; standard PSR and DSR are unavailable due to declared/screened dependence. |
| Nonnormal | Empirical skewness/kurtosis enter the conditional formula; no claim that their estimates are sufficiently stable. |
| Lucky search | Named best of 100 generated zero-mean trial streams: unadjusted PSR `0.987384`, DSR `0.309892`, all attempts retained. |

In the repeated fixture, mean net changes are **+0.116** and **+0.928 bp/period** in the two windows. Their 95% temporal-block intervals are **−1.955 to +1.936** and **−0.772 to +2.519 bp/period**. These intervals condition on the three observed executions; they are not independent-seed confidence intervals. Single-trial example DSR equals PSR against zero because its declared selection bar is zero, not because search history was assumed absent.

## Report inspection and preserved artifacts

All six HTML reports were parsed locally and checked for balanced tags, four explanatory sections, correct synthetic labels and one/two inline SVG charts as appropriate. Script/frame/remote-resource elements and inline event handlers are absent. Missing/failed cells, overlap counts, per-window sample lengths, aggregate statuses and selection values were inspected against JSON. Automated escaping tests include hostile titles, cost notes and failure descriptions. `output/v02-report-inspection.json` records these checks.

**Pixel-level rendering remains unverified.** Earlier local-server/browser preview routes were blocked; none was retried or replaced during v0.2. Regular Chrome remained unused. The owner can manually open the standalone HTML file. This limitation does not prevent reading the local JSON or running the CLI, and structural inspection is not presented as a visual preview.

All ten v0.1 report files and `dist/sharpeval-0.1.0-source.zip` still match the SHA-256 values recorded before this iteration in `output/v01-preservation.json`. The v0.1 regression tests also remain unchanged. Schema-1 calculations retain their original profile version and selection status; see [migration details](schema-v02.md).

## Delivery boundary

The v0.2 source ZIP is built from an explicit allowlist: Python package, tests, original synthetic examples, Markdown documentation, license, packaging metadata and ignore rules. It excludes virtual environments, bytecode/caches, generated reports, other archives, credentials and unrelated files. Example provenance and archive paths are checked; local delivery hashes and extraction checks are recorded in `output/v02-delivery-manifest.json`.

The source extraction is exercised with the existing interpreter: tests, version, validation and a complete CLI comparison. No wheel installation/build or Python version other than 3.13.7 was exercised. The setuptools build backend remains optional packaging infrastructure, not a runtime dependency.

Delivery remains local. No private Library upload was attempted in this iteration. The earlier upload's remote save was uncertain after a DNS failure; it is not reconciled or retried here and no new Library file ID is claimed.

Next useful evaluation: freeze real agent artifacts, cost assumptions, fixed portfolio rules, seed/window plan and the full strategy-search ledger, then collect fresh held-out records. This version does not verify producer declarations or overcome a missing experimental history.
