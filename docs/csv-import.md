# Import your own return records

`import-csv` turns a flat export into a portable schema-1 JSON input, validates it,
and refuses to write output on invalid data. It supports a single old/new version
pair with optional benchmark and fixed-portfolio histories. For repeated runs,
use the [schema-2 CSV walkthrough](csv-experiments.md): run/window/seed/version
identities and search metadata must be explicitly declared.

## Run the complete example

From a source checkout or extracted source distribution, using Python 3.11+:

```sh
python3 -m sharpeval import-csv examples/csv/returns.csv \
  --metadata examples/csv/metadata.json --out output/csv-input.json
python3 -m sharpeval validate output/csv-input.json
python3 -m sharpeval compare output/csv-input.json \
  --output output/csv-report --block-length 4 --resamples 200 --seed 42
```

If installed, substitute `sharpeval` for `python3 -m sharpeval`; the example files
come from the source download, not the installed wheel. The importer reports 48
observations in two histories and the report covers 24 daily sessions. Read
`output/csv-report/report.html` or its companion `report.json`. Repeating a command
at the same output path requires `--force`; neither input can be the output.
Identical inputs, settings and Python runtime give identical JSON and HTML bytes.

This deliberately small **synthetic** fixture repeats four gross returns six times:

| History | Gross pattern | Cost each period | Mean net return |
|---|---|---|---|
| agent-v1 | 0.010, -0.020, 0.005, 0.000 | 0.001 | -0.00225 |
| agent-v2 | 0.012, -0.018, 0.003, 0.001 | 0.001 | -0.00150 |

The mean change is `0.00075`, or **+7.5 bp/period**; both versions still have
negative average net returns. Compounded net returns are
`(1.009 * 0.979 * 1.004 * 0.999)^6 - 1` and
`(1.011 * 0.981 * 1.002 * 1.000)^6 - 1`. Tests check these independent arithmetic
values. This patterned fixture demonstrates parsing, cost handling and
reproducibility; its bootstrap output is not evidence of trading edge, a realistic
uncertainty model, or actual adoption.

## Prepare your export

Copy `examples/csv/metadata.json` and replace its declarations with your own.
Metadata follows [schema 1](input-format.md), with `observations` **omitted** from
each series. Keep all other required fields, including:

- The complete expected session calendar, taken from your evaluation schedule.
  Do not construct it from the intersection of observed dates: that can hide
  missing data. Missing expected sessions are errors, with timestamps shown.
- Stable history IDs, the same agent ID and distinct old/new version labels,
  provenance (`backtest`, `paper` or imported `live` histories), currency and
  explicit decimal simple-return units and frequency.
- `synthetic: false` for actual observations; do not mix actual and synthetic
  records. Declare cash return, cost coverage and gross/net basis accurately.
  Leave `periods_per_year` and `search_trials` null when unknown.

Export one row per history and period, using this header (column order may vary):

```csv
series_id,timestamp,return,cost,annotation
agent-v1,2025-01-01T00:00:00Z,0.010,0.001,Synthetic example only
agent-v2,2025-01-01T00:00:00Z,0.012,0.001,Synthetic example only
```

`annotation` is optional; its cells may be blank. All other columns and cells are
required. UTF-8, an optional UTF-8 BOM, LF/CRLF and ordinary quoted CSV fields are
supported. `return` and `cost` accept decimal/scientific notation, never `%`,
thousands separators, formulas or nonfinite values. `0.01` means 1%. Surrounding
whitespace in IDs, timestamps or numbers is rejected, not silently normalized.

For **gross** returns, every cost must be a number, including explicit `0` when
zero is intended. For **net** returns, the literal `null` means an unknown cost;
blank costs are always errors. Net returns are never charged a second time.
Costs are fractions of start-of-period equity, not dollars or basis points.
Convert prices, P&L, log returns, timezones and any variable capital base upstream.

Rows may interleave histories. Within each history they must be unique and
chronological, and participating histories must cover the declared calendar
exactly. The importer never sorts, fills, trims or infers the calendar. Unknown
history IDs, duplicate columns, extra/missing cells and blank rows are rejected.
Optional benchmarks and portfolio members must also be declared in metadata and
supplied as CSV histories. Metadata and CSV each have a 25 MB limit; the generated
JSON must also fit 25 MB. Existing 20-history/10,000-session bounds apply.

Errors exit with code 2 and include a field and physical CSV line where available,
for example `CSV line 2.cost: expected a decimal number ...`. Multiline quoted
records use their ending physical line. Fix the export and retry; no output file
is created or replaced after validation fails. The full schema contract remains
the final authority. A successful import validates format and internal consistency,
not the producer's provenance, data completeness or experimental design.

## Privacy and sharing

Conversion and analysis are local. Metadata has no executable settings or external
file references. Annotations, identifiers, cost notes and per-period returns can
appear in the JSON/HTML reports; inspect them before sharing. Keep private exports
and generated reports outside source control. The MIT license covers this code and
the original synthetic examples, not data imported from other sources.
