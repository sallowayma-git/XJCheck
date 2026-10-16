# Current pin geometry and pin text audit — 2026-10-16

## Scope

The audit used the current complete replay at `.tmp/precision_loop_20261015/p057_slice_10` (77 projects; 12,436 `R-RECOGNITION-GAP` rows). Two distinct slices were sampled and visually reviewed: `E_reg_element_no_port` (population 1,453) and `E_unreg_pin` with nearby text candidates (population 823 of 951 `E_unreg_pin` rows). Each sample contains 60 unique cases from 60 projects. All 120 individual screenshots are archived under [`screenshots/`](screenshots/), with per-row SHA-256 values in the judgement table; 10 contact sheets and their hashes are under [`contact_sheets/`](contact_sheets/) and `contact_sheets_manifest.csv`. Sampling was stratified by page, project, candidate direction, and text/insert family; the observed rates below are descriptive sample results, not population-weighted estimates.

Per-row outcomes and screenshot references are in [`sample_judgments.csv`](sample_judgments.csv). Full source manifests, sampling metadata, contact sheets, and images remain in `.tmp/precision_loop_20261015/current_pin_attachment_audit_20261016/`.

## Results

### Registered INSERT geometry candidates

| Outcome | Count |
|---|---:|
| Correct: endpoint coincides with visible pin/terminal geometry | 12/60 |
| Wrong: endpoint is only near the INSERT box/text or unrelated graphic | 46/60 |
| Uncertain: `SolidNode` HATCH point at endpoint | 2/60 |

The strict observed candidate precision is **20.0%** (12/60). Counting both uncertain `SolidNode` cases as correct would raise it only to 23.3%. This broad geometry candidate is not suitable for automatic pin attachment. Keep it in review; do not treat INSERT bounding-box proximity as a pin contact.

### Unregistered pin number text candidates

| Question | Correct | Uncertain | Wrong |
|---|---:|---:|---:|
| Does the nearby text belong to the pin/device row? | 54/60 | 6/60 | 0/60 |
| Does the endpoint land on the depicted pin geometry? | 59/60 | 1/60 | 0/60 |
| Both text attribution and endpoint association are clear | 53/60 | 7/60 | 0/60 |

The seven uncertain combined cases are one with a visible device label but no pin number (`#31`), three with a clear endpoint at a `CZ` symbol terminal but no candidate pin number (`#34/#36/#37`), and three with a clear endpoint at an Ethernet symbol top contact but no candidate pin number (`#52/#54/#56`). None is a confirmed false association.

The evidence supports testing a narrow text-attachment path only when both the terminal geometry and the visible pin text are unambiguous. Uncertain cases stay in review. These sample results do not support raising every `E_unreg_pin` candidate to pass, nor using a nearby text as electrical continuity evidence by itself. The audit confirms visual text attribution at one endpoint; it does not establish how that printed number composes with the block label into the canonical cross-sheet endpoint identity.

## Decision

- Hold generic `E_reg_element_no_port` geometry attachment; observed precision is too low and most candidates are bbox-only.
- Do not yet add an automatic text-to-pin pairing rule. The 53 clear cases establish a promising candidate class, but the current evidence is descriptive, the 7 uncertain cases need a code-detectable exclusion, and the audit has not established how the visual pin number composes with the block label into the canonical cross-sheet identity. A future prototype may attach text as review evidence only until that identity mapping is validated; every uncertain case stays in review.
- Do not infer connectivity or a matching pair from a pin number alone. Keep all ambiguous text/geometry cases in the review path.

## Evidence files

- [`sample_judgments.csv`](sample_judgments.csv): 120 case-level outcomes, reason codes, relative screenshot paths, and screenshot SHA-256 values.
- [`e_reg_sample_manifest.csv`](e_reg_sample_manifest.csv) and [`e_unreg_sample_manifest.csv`](e_unreg_sample_manifest.csv): population strata and selected cases.
- [`population_and_sampling_summary.json`](population_and_sampling_summary.json) and [`population_reconciliation.json`](population_reconciliation.json): scope and sample design.
- [`contact_sheets_manifest.csv`](contact_sheets_manifest.csv): checksums for the 10 contact sheets.

No production code or tests were changed for this audit.
