# Schema 2 and backward compatibility

Schema 2 is opt-in through `"schema_version": 2`. The same `validate` and `compare` CLI commands and public `sharpeval.analyze`, `validate`, `load_input` API accept both formats. Inputs are strict JSON; duplicate keys, unknown fields, ambiguous timestamps and nonfinite numbers are errors. No executable configuration, network references or automatic file imports are supported.

Use [`examples/v02-repeated.json`](../examples/v02-repeated.json) as the complete runnable template, or generate one:

```sh
.venv/bin/python -m sharpeval fixture-runs --scenario repeated \
  --periods 120 --seed 20261021 --out output/my-runs.json
.venv/bin/python -m sharpeval validate output/my-runs.json
.venv/bin/python -m sharpeval compare output/my-runs.json \
  --output output/my-runs-report --resamples 1000 --block-length 6 --seed 42
```

Fixture seeds reproduce generated data; `compare --seed` independently reproduces the temporal resampling. No attempt to execute an agent is made.

## Required top-level fields

| Field | Contract |
|---|---|
| `schema_version` | Integer `2`. |
| `title`, `synthetic`, `agent_id` | Nonempty title (up to 200 characters), boolean provenance label, agent identity (up to 120 characters). |
| `versions` | Exactly `old` and `new`, two distinct nonempty version strings. |
| `evaluation` | Shared protocol described below. |
| `seed_ids` | 1–20 unique planned execution identity strings. IDs may be actual RNG seeds or recorded execution labels; do not invent unrecorded pairing. |
| `windows` | 1–8 declared calendars, described below. |
| `runs` | List of explicit results. May be empty; absent planned cells remain missing. At most one result per seed × window × version. |
| `selection` | Optional list of independent diagnostic specifications for unique explicit run IDs. Omitted/empty means not supplied. |

`evaluation` has exactly:

```json
{
  "source_type": "backtest",
  "frequency_seconds": 86400,
  "periods_per_year": 365,
  "unit": "decimal",
  "currency": "USD",
  "cash_return_per_period": 0.0,
  "notes": "Describe shared evaluation conditions and what was fixed before seeing results."
}
```

`source_type` is `live`, `paper` or `backtest` provenance of imported records; this does not connect to any trading system. Units must be decimal simple equity returns. All histories share one positive integer frequency and valuation currency. `periods_per_year` is positive or `null` (no annualized outputs); frequency alone never supplies it. Cash is a finite constant per-period return. Frequency, period count, currency and numeric bounds inherit the [schema-1 contract](input-format.md).

## Windows and runs

Each window requires `window_id` (unique, up to 60 characters), `timestamps` (the explicit ordered expected period ends, canonical UTC `YYYY-MM-DDTHH:MM:SSZ`) and nonempty `notes`. Timestamps are unique within a window, increasing, and lie on the shared frequency grid. Expected sessions may omit declared nontrading sessions; an observed history may not omit an expected session. All windows share a consistent grid phase. A maximum of 10,000 expected periods per window is inherited from schema 1.

Optional `reference_series` is a list of complete schema-1 history objects; optional `benchmark` names one of these; optional `portfolio` uses schema-1 fixed weights, candidate weight, `each_period` rebalancing, declared-before-evaluation flag and overlay costs. References must cover the full window and have compatible units, frequency, currency and source context. Candidate placeholder IDs `run-old` and `run-new` are reserved, and cannot be used as reference IDs or portfolio/benchmark references. References can have the same IDs in different windows; their overlap is disclosed, never pooled.

Each explicit run requires:

```json
{
  "run_id": "window-1-seed-1-v1",
  "window_id": "window-1",
  "seed_id": "seed-1",
  "version": "v1",
  "status": "failed",
  "reason": "Execution failed before a complete comparable history was recorded."
}
```

`run_id` is globally unique. Other identity fields must name declared matrix members. `status` is `completed`, `failed` or `missing`. Failed/missing results require a nonempty `reason` and forbid `history`. An absent result has no invented run ID and is reported as missing. Completed results forbid `reason` and require `history` with exactly:

- `return_basis`: `gross` or `net`;
- `costs`: `included`, `excluded` lists and nonempty `notes`, using schema-1 definitions;
- `observations`: a complete ordered list for this window, each containing `timestamp`, `return`, `cost`, and optional source `annotation`.

Gross returns require a known nonnegative cost per period, subtracted once. Net returns are used unchanged; a null cost remains unknown. Fees/slippage/funding/borrow coverage are producer declarations. Returns below −1, post-bankruptcy recapitalization, duplicate/nonfinite observations, or missing expected periods are rejected. Schema 2 does not support `--alignment intersection`: record a failure/missing run honestly, or declare a separate evaluation window with a documented reason.

There are at most 100,000 completed-run observations per input. JSON size and per-history limits from schema 1 still apply. The total temporal resampling work is capped at 40 million sampled stream cells across windows; lower `--resamples` or use a smaller, clearly labelled experiment if needed. These are bounded implementation limits, not statistical sufficiency criteria.

## Optional selection specification

A complete specification for a predeclared single candidate:

```json
{
  "target_run_id": "window-1-seed-1-v2",
  "sharpe_unit": "per_period",
  "benchmark_sharpe_per_period": 0.0,
  "assumptions": {
    "serial_independence": "assumed",
    "stationarity": "assumed",
    "finite_fourth_moment": "assumed",
    "normal_trial_sharpes": "unknown",
    "comparable_trial_sharpes": "unknown"
  },
  "notes": "State why these assumptions and this target are appropriate; do not copy assumed values without evidence.",
  "search": {
    "observed_trial_count": 1,
    "effective_independent_trials": 1,
    "completeness": "complete",
    "dispersion_source": "unknown",
    "trial_sharpe_std_per_period": null,
    "trial_sharpes": null,
    "selected_trial_id": null,
    "null_mean_sharpe_per_period": 0.0,
    "notes": "One predeclared candidate, not a history reconstructed from successful runs."
  }
}
```

All fields shown are required when a selection specification is supplied. Every assumption is `assumed`, `unknown` or `unsupported`. The first three are needed for PSR and DSR; the last two additionally apply to DSR for more than one effective trial. A failed/missing explicit target is allowed but returns unavailable diagnostics. No aggregate path or absent cell can be a target.

`search` may be `null`, preserving PSR while making DSR unavailable. Within search, observed/effective counts can be `null` (unknown); otherwise they are integers in `[1, 1,000,000,000]` and effective count cannot exceed observed count. `completeness` is `complete`, `incomplete` or `unknown`. A large declared count is not evidence that the history is complete.

`dispersion_source` is `observed_trial_sharpes`, `assumed` or `unknown`. For `assumed`, supply a finite nonnegative `trial_sharpe_std_per_period` up to 1,000. Otherwise that field must be null: measured dispersion is calculated from the ledger, and unknown dispersion remains unavailable. `N=1` needs no dispersion. This input is a **standard deviation of trial Sharpe estimates**, not return volatility, variance, a count, or an annualized value.

`trial_sharpes` is null or a list of 1–10,000 entries, each exactly `{"trial_id": "unique-attempt", "sharpe_per_period": 0.04}`. Unknown/undefined outcomes use `null`, keeping the attempt visible. The ledger can contain no more than the declared observed count; a shorter or incomplete ledger withholds DSR. `selected_trial_id` must identify the target's entry when a ledger is supplied. Its Sharpe must match the target run within `1e-8` absolute/relative tolerance under the documented moment and cash conventions. Duplicate IDs are rejected. The tool cannot verify the histories behind other trial Sharpe values.

The supplied PSR comparison bar can be any supported finite per-period ratio in `[−1000,1000]`. DSR currently supports only `null_mean_sharpe_per_period: 0`; another finite value gives unavailable DSR rather than silently changing the null. See [methodology](methodology-v02.md) for all conditional assumptions and failure rules.

## Output and migration

Schema-2 JSON separates `coverage`, `runs`, `pairs`, `windows`, `aggregate`, `selection`, `analysis_settings`, `warnings` and a canonical input hash. `windows[i].execution_dispersion` is descriptive. A complete window's `aggregate.comparison` contains the unchanged core net/risk/portfolio/block calculation under reserved stream IDs `run-old`/`run-new`; the nested legacy selection field is removed. `selection.targets` contains only requested actual runs. Selection values have `status: conditional` or `unavailable`, never a skill verdict. Null values are not zero. HTML uses the same JSON results and embeds no scripts or remote assets.

Old input files and commands remain valid. The schema-1 calculation profile deliberately reports `tool.version: 0.1.0`, including its original selection-not-implemented output and rendering; `sharpeval --version` reports package `0.2.0`. Tests compare frozen schema-1 JSON/HTML hashes. Existing v0.1 generated files and source ZIP remain separate and unchanged.

There is no automatic migration command because source files cannot reveal real seed identities, failed attempts, a planned run matrix or search history. To migrate deliberately: declare the actual experiment protocol, copy the explicit calendar into a named window, copy each candidate history's basis/costs/observations into the corresponding run, retain all missing/failed executions, and move benchmark/portfolio histories into that window's references. Add selection specifications only when their required evidence is known; otherwise leave them out or explicitly unknown. Changing only `schema_version` is not a valid migration.
