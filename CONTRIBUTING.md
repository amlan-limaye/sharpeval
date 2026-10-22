# Contributing

Run the standard-library test suite with `python -m unittest discover -s tests -v` from the project root. Keep runtime dependencies at zero unless a concrete requirement justifies a change. Test calculations against independent hand-derived cases; do not merely snapshot the implementation's output.

Preserve explicit cost accounting, chronology, paired sampling and missing-evidence statuses. New diagnostics must document their estimands, units, uncertainty assumptions and failure conditions. Never replace uncertainty with a global skill score or silently treat absent search history as zero trials.

Add synthetic fixtures when possible. Do not commit credentials, private evaluation histories or third-party market data without independently established redistribution rights. Generated reports and virtual environments are ignored by Git. Before preparing a release, build both wheel and source distribution, verify a clean install from outside the checkout, and run the documented CSV workflow using only the source distribution. Keep private exports and generated reports out of release artifacts.

Schema 2 now records planned run identities and conditional selection inputs. Keep schema-1 compatibility outputs stable; new interpretation belongs in an explicitly versioned format. Useful next work is a small frozen evaluation with actual agent-artifact hashes, a complete search ledger and fresh held-out windows. These records should drive any stronger repeated-run or dependence inference.

The [CI/release guide](docs/ci.md) provides the exact local clean-install check.
Keep CI permissions read-only, action refs pinned to verified full commits and
checkout credentials unpersisted. The [case-study generator](examples/repeated-csv/generate.py)
must reproduce its committed exports; change its narrative if its assumptions or
outcomes change. Synthetic or retrospective fixtures must never be relabeled as
prospective evaluations or actual adoption.
