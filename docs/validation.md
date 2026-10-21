# Delivery validation — 2026-10-21

Local project: `SharpeVal` / Python module and CLI `sharpeval`, version `0.1.0`.

Environment: macOS, existing `/opt/homebrew/bin/python3.13`, Python **3.13.7**, isolated `.venv` created with `--without-pip`. Runtime dependencies: **zero**. No installs, trust-store changes, shell changes, credentials, brokerage connections, deployment or publishing were used. No unrelated processes or apps were restarted. No existing browser sessions were modified.

## Tests actually run

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q sharpeval tests
```

Final regression result: **67 tests passed**, in **3.616 seconds** on the delivery machine. Compile checks passed. The full local log is `output/test-results.txt` (generated output, excluded from the source bundle).

Coverage includes hand-calculated compounding, sample variance, drawdown from initial capital, annualization suppression, benchmark beta, gross/net costs counted once, unknown costs, explicit fixed portfolio formulas, leveraged/bankrupt returns, tiny finite arithmetic, numeric overflow, missing/duplicate/out-of-order periods, mismatched frequency/currency/source/identity, explicit edge trimming, internal-gap rejection, invalid weights and inputs, paired shared resampling, temporal blocks, correlation sensitivity, an independent percentile oracle, reproducibility, and safe HTML escaping/file output.

All four synthetic baseline families were exercised in the tests and through the CLI. The duplicate-agent test also uses an identical single-agent base with zero overlay cost and verifies zero portfolio change; a duplicate of one member of a mixed portfolio can still alter the base's exposures.

## CLI runs actually completed

```sh
.venv/bin/python -m sharpeval validate examples/complementary.json
.venv/bin/python -m sharpeval compare examples/complementary.json \
  --output output/demo --block-length 8 --resamples 1000 --seed 42 --force
.venv/bin/python -m sharpeval compare examples/leveraged-beta.json \
  --output output/leveraged-beta --block-length 8 --resamples 1000 --seed 42
.venv/bin/python -m sharpeval compare examples/lucky-outlier.json \
  --output output/lucky-outlier --block-length 8 --resamples 1000 --seed 42
.venv/bin/python -m sharpeval compare examples/duplicate.json \
  --output output/duplicate --block-length 8 --resamples 1000 --seed 42
.venv/bin/python -m sharpeval compare examples/minimal.json \
  --output output/minimal --resamples 200 --seed 42
```

All completed with exit code 0 and produced JSON plus HTML. The minimal example correctly reports insufficient data, no benchmark/portfolio, and no annualized figures. Add `--force` to repeat any existing output path. The test suite independently exercises refusal to overwrite files, explicit forced replacement and byte-identical repeated JSON output at a fixed seed.

| Synthetic scenario | Periods | Observed mean change (bp/period) | 95% paired block interval (bp/period) |
|---|---:|---:|---:|
| Complementary | 252 | +13.279 | −17.506 to +38.908 |
| Leveraged beta | 252 | −8.291 | −30.581 to +17.684 |
| Lucky outlier | 252 | +11.905 | 0.000 to +35.714 |
| Duplicate versions | 252 | 0.000 | 0.000 to 0.000 |
| Minimal | 8 | −12.761 | Unavailable |

The complementary fixture's mean-change interval includes zero despite its large realized return difference. Its candidate/base correlation is approximately `−0.793`; the fixed 25% addition reduces observed per-period volatility by about `0.266` percentage points. These are properties of **generated test streams**, not evidence of real-world predictive skill. The leveraged fixture returns benchmark beta approximately `2.0` with an intercept numerically zero. The outlier fixture loses all observed mean improvement when the injected shock is excluded in the descriptive sensitivity check.

## Report inspection and remaining visual check

All five generated HTML files were parsed and checked: balanced tag structure, four explanatory sections, one or two SVG wealth charts, correct SharpeVal/synthetic labels, explicit DSR/search limitations, and no scripts, frames, linked resources or image resource elements. Numeric report content was checked against its JSON companion. `output/report-inspection.json` records those checks. Imported title, annotation and cost-note injection cases are escaped by automated tests. These checks **do not establish pixel-level rendering quality**.

Automated visual preview remains **blocked**, not completed:

- A loopback-only preview command, `python -m http.server 8766 --bind 127.0.0.1 --directory output`, failed at socket bind with sandbox `Operation not permitted`. It exited; no preview server is running and no escalation was requested.
- The Codex in-app browser was unavailable in this environment.
- Opening the generated local report via a new Brave tab was **denied by browser URL policy** because `file:` is not an allowed protocol. The target at that time was `file:…/output/demo/report.html`, before the project was renamed. No retry or policy workaround was attempted. The final report is now `sharpeval/output/demo/report.html`.

No browser permission change is needed to use the artifact normally: the owner can manually open the HTML file directly in a local browser. That manual visual check is still outstanding. The generated report is fully local; it contains no external data/assets and does not require a server.

## Packaging boundary

The source bundle excludes `.venv`, caches and generated reports. A fresh source extraction is smoke-tested using the existing isolated interpreter. The standard setuptools packaging configuration is supplied, but installing/building a wheel through pip was not exercised and would require a build backend in an isolated environment. No registry package name, domain or trademark availability has been claimed.
