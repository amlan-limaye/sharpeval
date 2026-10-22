# CSV exports for repeated experiments

`import-csv` dispatches on the metadata's `schema_version`. Existing schema-1 CSV
commands and results stay unchanged. Schema 2 requires the experiment identities
you actually recorded; changing the version number on a single-pair file cannot
recover runs, pairing, failures or a search history.

## Export → validate → report

From a source checkout or extracted source distribution with Python 3.11+:

```sh
python3 -m sharpeval import-csv examples/repeated-csv/returns.csv \
  --metadata examples/repeated-csv/metadata.json --out output/repeated-input.json
python3 -m sharpeval validate output/repeated-input.json
python3 -m sharpeval compare output/repeated-input.json \
  --output output/repeated-report --block-length 6 --resamples 1000 --seed 42
```

An installed environment can use `sharpeval` in place of `python3 -m sharpeval`.
The source distribution provides the example files; wheels provide the program.
Expect **1,440 observations, 12 explicit runs, 6 complete pairs and 2 windows**.
Read `output/repeated-report/report.html` and its `report.json` companion.
Both windows are synthetic retrospective constructions, as explained in the
[case study](case-study.md). They are not a pre-registered forward evaluation.

The command needs no network. Repeating an output path requires `--force`.
Conversion validates before writing and never overwrites either input file.
Invalid input exits 2. A successfully generated report can still contain
unavailable diagnostics; check statuses before using its values.

## The two export files

Metadata is the existing [schema-2 JSON contract](schema-v02.md), with
`observations` **omitted only from completed candidate run histories**. Retain:

- `agent_id`, the exact old/new version labels, the shared evaluation protocol,
  all planned `seed_ids`, and every window's independent expected calendar.
- Explicit run IDs and their window/seed/version mappings. A seed label declares
  paired executions under comparable conditions; equal row numbers do not create
  a valid pair. The importer checks consistency, not the truth of that assertion.
- `status: completed` with history `return_basis` and `costs`; or `failed`/`missing`
  with a nonempty reason and **no** history. Status is never taken from the CSV.
- Optional `selection` specifications and search ledger exactly as known. Counts
  and dispersion are not inferred from run IDs, execution seeds, file length or
  successful outcomes. Null/unknown/incomplete inputs stay that way.

Optional window benchmark/portfolio `reference_series` stay as complete JSON
histories in metadata for this bounded importer. They retain the same validation
and complete-window requirements. They are not candidate runs and do not use
candidate CSV rows.

Export one row per completed run and expected session:

```csv
run_id,window_id,seed_id,version,timestamp,return,cost,annotation
dev-a-old,development,execution-a,baseline-v1,2024-01-01T00:00:00Z,0.001,0.0001,Synthetic illustration
```

The first seven columns are required; `annotation` is optional. Column order may
vary. All four identity columns must match that run's metadata exactly; none is
guessed or silently corrected. Rows can interleave runs, but each run must already
be chronological, unique and complete for its declared window. There is no
intersection/edge trimming for schema 2.

Use decimal simple equity returns and start-equity cost fractions (`0.01` = 1%).
Gross costs must be numeric, even if zero. For net histories, literal `null` means
unknown cost; it is never converted to zero or deducted again. Blank numeric cells,
percentages, formulas, duplicate columns, extra cells, unknown run IDs and
observations for failed/missing runs are errors. UTF-8/BOM, LF/CRLF and quoted
annotations are supported as in the [single-pair CSV guide](csv-import.md).

Limits remain 25 MB per input/output JSON, 1–8 windows, 1–20 execution identities,
10,000 periods per window and 100,000 completed candidate observations overall.
The importer adds no assumptions or statistics. It creates the same document and
report as hand-built schema-2 JSON, covered by exact-equivalence tests.

## Preserve failures and missing evidence

Run the companion export containing one failed and one missing execution:

```sh
python3 -m sharpeval import-csv examples/repeated-csv/incomplete-returns.csv \
  --metadata examples/repeated-csv/incomplete-metadata.json \
  --out output/incomplete-input.json
python3 -m sharpeval compare output/incomplete-input.json \
  --output output/incomplete-report --block-length 6 --resamples 200 --seed 42
```

Expect **12 planned runs, 10 completed, 1 failed and 1 missing**. The audit-replay
window has no aggregate or confidence interval. Failed/missing runs must have no
CSV observations; do not insert zero returns or delete them from the planned
matrix. An entirely absent planned cell remains absent in the JSON and appears as
missing in the report, with no invented run ID. That is distinct from an explicit
missing record with its original ID and reason. A header-only CSV is valid when
metadata contains no completed runs.

CSV row errors include a physical line and field; core history errors also identify
the run. For example, a swapped seed gives `CSV line 2.seed_id: does not match
metadata ...`. Missing sessions name the run and expected timestamps. Errors in
search assumptions or the metadata calendar remain metadata errors. Search
completeness is a producer assertion, never established merely by valid syntax.

## Regenerate and adapt

```sh
python3 examples/repeated-csv/generate.py --out output/regenerated-case
```

The output directory must be new. This stdlib-only generator writes both export
variants and `provenance.json`; tests verify the committed exports reproduce
exactly. To use actual records, replace the metadata and returns with your own,
set `synthetic: false`, and preserve your real evaluation and search records.
Remove unsupported assumptions rather than copying this case's assumptions.
Inspect identifiers, notes and returns before sharing reports, and ensure you have
rights to redistribute any imported data. No actual or third-party data is included
in this example.
