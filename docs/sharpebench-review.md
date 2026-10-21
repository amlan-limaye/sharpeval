# SharpeBench review and reuse decision

Reviewed the public `main` branch on **2026-10-21**, before implementing SharpeVal. Links below are mutable upstream references, not an assertion that the current upstream revision is permanently pinned.

## Methodology reviewed

SharpeBench evaluates standalone entrants with Deflated Sharpe, repeated-run checks, bootstrap significance, process checks and drawdown constraints. Its methodology explicitly distinguishes standalone ranking from the marginal value of adding an agent to an existing portfolio. It also states the historical, ex-post boundary of its conclusions. [Methodology](https://github.com/general-liquidity/sharpebench/blob/main/docs/book/src/methodology.md)

Its significance chapter documents a seeded stationary bootstrap and shared resampling indexes for field-wide comparisons. SharpeVal instead uses the simpler paired circular moving-block percentile procedure documented locally, and emits no significance gate. [Significance](https://github.com/general-liquidity/sharpebench/blob/main/docs/book/src/methodology-significance.md)

Its DSR discussion makes search-trial inputs and serial-dependence assumptions explicit. SharpeVal v0.1 left DSR unimplemented; v0.2 implements the published formula conditionally. Neither version infers unknown search counts or claims a new discovery of these statistics. [Deflated Sharpe](https://github.com/general-liquidity/sharpebench/blob/main/docs/book/src/methodology-deflated-sharpe.md)

## Code license reviewed

The workspace manifest declares `MIT OR Apache-2.0`. Both root license texts were inspected. The MIT text identifies General Liquidity, Inc., copyright 2026, and requires its copyright/permission notice with copied or substantial portions. Apache-2.0 includes redistribution, modification-notice and attribution conditions. Any future reuse needs to follow the selected license and applicable notices for the exact source reused. [Manifest](https://github.com/general-liquidity/sharpebench/blob/main/Cargo.toml) · [MIT](https://github.com/general-liquidity/sharpebench/blob/main/LICENSE-MIT) · [Apache-2.0](https://github.com/general-liquidity/sharpebench/blob/main/LICENSE-APACHE)

**Decision:** independently implement this bounded Python core using the standard library and test its arithmetic directly. No SharpeBench source code, Rust/Python packages, compiled kernels or benchmark score artifacts are bundled. Its published methodology is cited as prior work. No enormous dependency build was attempted.

For v0.2, the public [`deflated_sharpe.rs`](https://github.com/general-liquidity/sharpebench/blob/main/crates/sharpebench-stats/src/deflated_sharpe.rs) and [`stats.rs`](https://github.com/general-liquidity/sharpebench/blob/main/crates/sharpebench-stats/src/stats.rs) were inspected alongside the original papers. The manifest at review declared version 0.28.0 and the same dual license. The implementation provided a useful cross-check of the paper's numerical examples. SharpeVal uses its own formula implementation and independently integrated numerical test oracle. No upstream source was copied or executed, and no market datasets were acquired. SharpeVal's serial-dependence screen and refusal conditions are local application choices, not the official benchmark's implementation or eligibility gates.

## Data rights and product boundary

SharpeBench's README expressly separates its code license from market-data redistribution rights. No market datasets were downloaded, copied or repackaged. SharpeVal's example data are original seeded synthetic constructions; the MIT license supplied here does not license any externally imported data. [Upstream data-rights notice](https://github.com/general-liquidity/sharpebench#readme)

SharpeVal produces local version comparisons and fixed-rule portfolio diagnostics. It does not reproduce the official SharpeBench benchmark, composite score, ranking or eligibility decisions, and makes no claim of affiliation or endorsement. No published dataset or official result is represented as SharpeVal evidence.
