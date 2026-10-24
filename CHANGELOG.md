# Changelog

## 0.4.0

- Add schema-3 `rank`, `fixture-cohort` and public `rank_cohort` for a frozen
  multi-agent cohort. Rank one primary execution on one common evaluation window
  by `100 * (1 - Holm-adjusted one-sided PSR p)`, under explicit supported
  assumptions and a common positive per-period Sharpe hurdle chosen by the user.
- Retain every registered candidate in the correction family; failed, missing and
  ineligible entries use p = 1 for correction and keep null scores. Equal scores
  share rank. Preserve planned replay failures without pooling market history.
- Validate expected timestamps, versions, decimal units, known cost accounting,
  measured peak exposure and common risk limits. Withhold scores for unsupported
  assumptions, reused holdouts, dependence flags, invalid moments or unmet limits.
- Display raw PSR, effect size and reasons beside separate exposure efficiency,
  frozen-reference correlation and discovery-context DSR. No arbitrary weighted
  composite, posterior skill probability, official Swing replication or claim of
  repeatability. Schema-1/2 statistical calculations and reports are unchanged.
- Add own-data JSON instructions, offline HTML/JSON reports, focused tests and a
  fixed 1,600-world synthetic calibration reporting all seeds, familywise false
  qualifications, power, rank stability and Monte Carlo intervals. Unsupported
  stress cases measure abstention only. No real trading edge or adoption claim.
- Extend clean wheel/source installation checks to the cohort workflow. No new
  runtime dependency, service, credentials or network requirement.

This release starts from published v0.3.0. The separately held ECB v0.3.1
candidate and its artifacts are preserved outside this package, not published or
silently folded into this release.

## 0.3.0

- Extend `import-csv` to schema 2 with explicit run/window/seed/version matching,
  strict window coverage and preserved failed/missing records and search metadata.
  Never infer paired identities, omitted trials, effective counts or cost amounts.
- Identify the affected run in schema-2 history errors. Prove CSV equivalence to
  hand-built JSON and its reports, while retaining schema-1 behavior.
- Add a reproducible, original MIT-licensed synthetic case and export-to-report
  walkthrough: 40 candidate variants, two retrospective windows, three paired
  executions, explicit costs and an incomplete-evidence companion. No prospective
  performance, real-market observations or adoption is claimed.
- Add a read-only GitHub test/build matrix with full-commit action pins and no
  persisted credentials. Verify wheel and source installs outside the checkout,
  using packaged offline examples and no package index during verification.

Statistical calculations, input contracts and report calculation-profile versions
remain unchanged. Hosted CI results are established by actual runs, not by adding
the workflow file.

## 0.2.1

- Add `import-csv` for flat history exports with explicit schema-1 metadata and an
  independently declared calendar. Validate before writing, report CSV line/field
  errors, retain unknown net costs, and protect both input files from overwrite.
- Include a reproducible CSV-to-report example with independently checked net
  means and compounded returns. No data downloads or new runtime dependencies.
- Report missing expected timestamps during strict alignment. Convert oversized
  JSON integer parse failures into the documented clean exit-code-2 input error.
- Include docs, examples and tests in source distributions; replace local-delivery
  README assumptions with fresh install and source-checkout instructions.

The statistical calculations and schema-1/schema-2 report calculation-profile
versions remain unchanged. Synthetic examples do not demonstrate genuine trading
edge or real usage.
