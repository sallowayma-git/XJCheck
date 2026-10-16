# Current zero-gap symbol-crossing discard audit

## Result

On the current 77-project replay (172,193 pairs), the residual population contains 283 `ordinary_pair` discards that `PathBodyChecker` classifies as crossing a symbol body. A stratified visual sample of 42 cases found **42 justified discards, 0 false discards, and 0 uncertain cases**. The observed sample precision is 100%; this is not evidence that every one of the 283 cases is correct.

No generic defect was found in this slice, so it does not support a production rule change. This audit measures the precision of the current discard decision. It does not measure missed wire cuts or recall.

## Sampling and review

- Replay snapshot: `.tmp/precision_loop_20261015/p057_slice_10` (77 projects / 172,193 pairs).
- Population: one `ordinary_pair` + `discard` + `PathBodyChecker` verdict `body` case per `(project, sheet, line_group_id)`; 283 cases across 68 projects.
- Selection: deterministic stratified random sample by body width, seed `20261016`; rare width strata were fully enumerated.

| Body width | Population | Sample | Justified discard | False discard | Uncertain |
|---:|---:|---:|---:|---:|---:|
| 11.25 | 245 | 30 | 30 | 0 | 0 |
| 10.0 | 32 | 6 | 6 | 0 | 0 |
| 7.5 | 4 | 4 | 4 | 0 | 0 |
| 2.5 | 2 | 2 | 2 | 0 | 0 |
| **Total** | **283** | **42** | **42** | **0** | **0** |

I reviewed all seven contact sheets (42 individual cases); an independent reviewer also judged all 42 screenshots. The visible path crosses device terminals and an internal contact or functional element in each case. Edge cases include a multi-contact path, AP2/AP3 multi-pin equipment, a coil, contactor-style blades, and the narrow 7.5/2.5 body-width strata. No case showed a path that only crossed an enclosure, annotation, or unrelated graphic.

## Evidence

- [`sample_index.csv`](sample_index.csv): population key, stratum, geometry, relative screenshot path, and screenshot SHA-256 for every sampled case.
- [`sample_judgments.csv`](sample_judgments.csv): row-level visual labels, notes, relative screenshot paths, and screenshot hashes.
- [`sample_summary.json`](sample_summary.json): replay and sampling counts emitted by the renderer.
- The 42 individual screenshots are under [`screenshots/`](screenshots/); the seven contact sheets and their hashes are under [`contact_sheets/`](contact_sheets/) and [`contact_sheets_manifest.csv`](contact_sheets_manifest.csv).
- The earlier source analysis is in the parent [`README.md`](../../README.md), section 6; current implementation is `src/dwg_audit/audit/line_groups.py` (`PathBodyChecker`).

