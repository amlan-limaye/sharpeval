# Changelog

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
