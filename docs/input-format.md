# Input contract (schema version 1)

This contract remains supported without changed results in package v0.2. For repeated runs and conditional selection diagnostics, use [schema 2](schema-v02.md).

One UTF-8 JSON object is the complete portable input. Unknown fields and duplicate object keys are rejected so typos cannot silently change interpretation. There is no executable configuration, external file resolution or network lookup.

Start with [`examples/minimal.json`](../examples/minimal.json), generate an example using `fixture`, or use the [CSV importer](csv-import.md) to validate a flat export with separately declared metadata and calendar. All fields below are required unless explicitly optional.

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | Integer `1`. |
| `title` | Human-readable label, at most 200 characters. |
| `synthetic` | Boolean. `true` means all supplied values are synthetic. Do not mix real and synthetic histories in one evaluation. This is a producer declaration, not independently verified. |
| `calendar` | Explicit expected sessions, described below. |
| `cash_return_per_period` | Constant decimal simple cash return used only as the Sharpe/regression reference; declare `0` when intentionally using zero-return cash. Supported range `(-1, 1]`. |
| `series` | Two to twenty return-history objects. |
| `comparison` | `{"old":"agent-v1","new":"agent-v2"}`. Both IDs must exist, with the same `agent_id` and distinct `version` labels. |
| `benchmark` | Optional history ID, or `null`. No benchmark is inferred. |
| `portfolio` | Optional fixed-weight object, or `null`. |
| `search_trials` | Optional positive integer, or `null`/omitted for unknown. Disclosed only; selection correction is not implemented. Zero is rejected. |

## Calendar

```json
{
  "frequency_seconds": 86400,
  "periods_per_year": null,
  "timestamps": ["2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z"],
  "notes": "Daily period ends; complete expected session calendar supplied by the producer."
}
```

Each timestamp is the UTC end of the return period named by that session. Accepted syntax is exactly `YYYY-MM-DDTHH:MM:SSZ`. Timestamps must be unique and increasing, on a grid whose differences are positive whole multiples of `frequency_seconds`. A timestamp's return must describe that one session, never a multi-session cumulative catch-up return. DST-adjusted local closes and variable-length monthly bars need explicit upstream normalization; v1 does not guess.

The calendar is a producer-supplied list of **every expected session**. It may omit declared nontrading sessions such as weekends/holidays, with the convention explained in `notes`. The tool cannot infer whether a missing calendar date was a holiday, a silent data loss or cherry-picking. Provide the calendar from the evaluation schedule, not by taking the observed intersection. Blocks are consecutive *sessions on this calendar*, not necessarily consecutive wall-clock days.

`periods_per_year` must be positive or explicitly `null`. It is never inferred from frequency or gaps. A 24/7 synthetic daily calendar can declare `365`; a session calendar should declare the actual convention used by its producer. Leaving it null is valid and suppresses annualization.

## Each history

```json
{
  "id": "agent-v1",
  "agent_id": "my-agent",
  "version": "v1-frozen",
  "source_type": "backtest",
  "frequency_seconds": 86400,
  "unit": "decimal",
  "currency": "USD",
  "return_basis": "gross",
  "costs": {
    "included": ["commission", "slippage", "financing"],
    "excluded": ["tax", "infrastructure"],
    "notes": "Explain measured/modelled costs and any exclusions."
  },
  "observations": [
    {"timestamp": "2025-01-01T00:00:00Z", "return": 0.01, "cost": 0.001},
    {"timestamp": "2025-01-02T00:00:00Z", "return": -0.02, "cost": 0.001,
     "annotation": "Optional producer-supplied decision or trade context."}
  ]
}
```

IDs are unique and use letters, numbers, underscore, dot or hyphen; the prefix `portfolio.` is reserved. `source_type` is `backtest`, `paper` or `live`, referring only to imported historical records. Participating histories must share the same source type, frequency and valuation currency. Identical labels cannot guarantee comparable execution, data availability or leverage; those remain producer responsibilities.

Only decimal **simple equity returns** are accepted (`0.01` = 1%). Log returns, percentages, prices and currency P&L require explicit upstream conversion. Currency denotes the portfolio valuation numeraire, not a request for FX conversion. Cash flows, subscriptions, withdrawals, restarts and changing capital denominators are unsupported.

Each cost is a nonnegative fraction of that period's starting equity. For `gross`, subtract cost exactly once; cost cannot be null. For `net`, use the return unchanged; a known cost permits gross reconstruction as `net + cost`. A null cost is accepted only for net inputs and propagates to unavailable cost aggregates/gross returns. A stated zero means the producer asserts zero, not unknown. Nonlinear fee models must be converted to realized period equity fractions upstream.

Every observation must explicitly contain `cost` even when null. `included`, `excluded` and explanatory `notes` describe cost scope; an item cannot be both included and excluded. Differences in cost notes or coverage between versions are flagged. Known amounts do not imply complete or realistic costs.

Both gross and net returns must lie in `[-1, 1000]` (up to 100,000% per period); the ceiling is a documented v1 numeric bound. Cost fractions must be in `[0, 1000]`. Nonfinite values and booleans in numeric fields are invalid. Exactly `-1` is bankruptcy: subsequent net returns may only be zero. Equity never recovers; uncertainty and fixed-allocation portfolio calculations involving bankruptcy are withheld. Below `-1` is rejected.

## Optional fixed portfolio

```json
{
  "weights": {"existing-trend": 0.7, "existing-carry": 0.3},
  "candidate_weight": 0.25,
  "rebalance": "each_period",
  "overlay_cost_per_period": 0.00002,
  "overlay_cost_notes": "Additional 0.2 bp per period allocation cost; constituent trading costs already included.",
  "weights_declared_before_evaluation": true
}
```

Weights refer to supplied history IDs, must be finite and nonnegative, and sum to one (absolute tolerance `1e-10`). They are not normalized, optimized or drifted. No implicit cash, leverage or shorts are allowed in the allocation weights; underlying agents can nevertheless contain leveraged exposures, which the tool cannot audit. `candidate_weight` is between zero and one; zero is explicitly flagged as a degenerate allocation. `weights_declared_before_evaluation` must be true, representing a user assertion the tool cannot verify.

At every period: `base = sum(weight * constituent_net)`; `with_version = (1-candidate_weight) * base + candidate_weight * version_net - overlay_cost_per_period`. Both versions receive the same candidate weight and constant overlay cost. All remaining holdings are reduced proportionately. This is a hypothetical constant-mix calculation, not an execution simulation. If the assumed portfolio reaches/breaches bankruptcy it is rejected; no recapitalization is assumed.

The overlay is an additional fraction of total portfolio starting equity, in `[0,1)`. Zero must be declared explicitly and justified in notes. It should capture assumed costs of allocating/rebalancing beyond the constituents' existing net costs. If the versions require different or variable overlay costs, v1 cannot represent that comparison faithfully.

## Alignment and bounded execution

`strict` requires every participating history to cover every expected session. `intersection` must be explicitly selected and may trim only beginning/end coverage to a common contiguous calendar slice. Internal missing periods, duplicates and out-of-calendar records are rejected. No returns are filled, aggregated or stretched to a longer holding period. The report records all excluded calendar timestamps, observation counts and unused histories. Unused histories are validated but do not determine the common window.

Limits: 25 MB CLI file size, 1–10,000 calendar sessions, 2–20 histories, 200–10,000 bootstrap draws, block length 2–10,000, confidence 0.80–0.99, nonnegative integer seeds up to `2**63-1`. Bootstrap execution is capped at 40 million sampled cells across all streams and usable block-length variants; reduce draws or sample size when exceeded. These bounds keep this dependency-free first version practical. At most 20 annotations are shown in HTML; all are retained in JSON.
