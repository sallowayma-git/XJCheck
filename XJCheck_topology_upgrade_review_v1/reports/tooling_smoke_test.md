# Tooling Smoke Test

Date: 2026-07-10

The delivery scripts were smoke-tested against the supplied repository and corpus.

## Results

- `corpus_inventory.py`: PASS; found 27 projects, 502 valid DWGs, 505 terminal-strip records and no `.prj` page-list mismatch.
- `run_corpus_baseline.py`: PASS in degraded mode on one project; the current environment correctly recorded 28 `missing_converter` pages instead of claiming a clean audit.
- `build_failure_queue.py`: PASS; generated 28 Reader-critical records for the degraded project.
- `bootstrap_symbol_library.py`: PASS; generated an empty-but-valid backlog because the degraded run had no extracted block entities.
- `compare_engines.py`: PASS on a self-comparison baseline.
- `batch_extract_previews.py`: PASS on two DWGs.
- `validate_package.py`: PASS; all required files, JSON, YAML, Python syntax, CSV headers and PNG signatures were valid.

## Interpretation

These smoke tests validate orchestration, failure handling and artifact structure. They
do not validate entity recognition accuracy because ODA File Converter was not
available in this runtime. The full 27-project entity-level baseline must be run in
the target Windows/ODA environment.
