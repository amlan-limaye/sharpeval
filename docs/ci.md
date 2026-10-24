# Read-only checks and local release verification

The [GitHub workflow](../.github/workflows/tests.yml) runs on pushes, pull requests
and manual dispatch. Its three jobs cover Python 3.11 and 3.13 on Linux and Python
3.13 on Windows. They run the stdlib test suite, build a wheel/source distribution,
then verify clean installs outside the checkout using packaged offline examples.
Windows can skip only the symlink-specific test if the runner lacks symlink
privileges; the workflow does not request or enable that privilege.
The repository pins text files to LF endings so the committed export-byte checks
also work on Windows; the job uses UTF-8 mode for Python's text I/O.

The workflow grants only `contents: read`; checkout does not persist credentials.
It references no repository secrets, write tokens, publishing steps, caches,
external services or artifact uploads. The checkout/setup-python actions are
pinned to full commits from their v6 lines, verified when this change was prepared:

- [checkout d23441a…](https://github.com/actions/checkout/commit/d23441a48e516b6c34aea4fa41551a30e30af803)
- [setup-python ece7cb0…](https://github.com/actions/setup-python/commit/ece7cb06caefa5fff74198d8649806c4678c61a1)

Setup can download Python and the existing declared setuptools build backend.
The verification phase sets `PIP_NO_INDEX=1`, rebuilds the sdist using the already
installed backend, and installs each wheel into a new virtual environment using
`--no-index --no-deps`. Each subprocess runs outside both the checkout and source
extraction, with `PYTHONPATH`/`PYTHONHOME` removed. The installed module path is
checked, preventing an accidental source-tree import from masking a broken wheel.
Schema-1 CSV, schema-2 CSV, explicit failed/missing runs and seeded report
reproducibility are exercised. Wheel/sdist reports must match within that runtime.
Schema 3 additionally checks generated fixture bytes, validation, rank JSON/HTML,
missing-primary family slots and all 1,600 frozen calibration worlds with each
clean installed package. The generated calibration is compared with the packaged
record after removing Python-version metadata. Structure, seeds, counts, statuses,
ranks and qualification decisions must match exactly; floats permit only roundoff
(`rel_tol=1e-12`, `abs_tol=1e-14`) across Python/platform math libraries. Wheel and
sdist output hashes must still match exactly within each runtime. Larger differences
fail the check and require investigation, not an outcome-driven tolerance change.

To run the same checks locally with an existing supported Python interpreter:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'setuptools>=68'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c "import setuptools.build_meta as b; b.build_sdist('dist'); b.build_wheel('dist')"
.venv/bin/python tools/verify_release.py --artifacts dist --evidence output/clean-install.json
```

Use a fresh artifact directory containing exactly one wheel and one source archive;
old versions are rejected rather than accidentally tested. Substitute Windows's
`.venv\Scripts\python.exe` as needed. No `build`, `pytest` or runtime dependency is
required. The JSON evidence includes command exits, installed paths and report
hashes; it is local diagnostic output and may contain workspace paths.

Preparing this workflow does not mean hosted CI has already passed. Check the
actual GitHub run for the published commit before claiming platform coverage.
Statistical tests and synthetic examples validate implementation behavior, not
data provenance, trading performance or real adoption.
