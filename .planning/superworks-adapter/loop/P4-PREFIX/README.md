# P4 device-prefix normalization audit

## Result

This is a read-only screenshot audit of the 1,389 P4 prefix-normalization events across 68 projects. The earlier 112/112 full-identity result came from a hardcoded judgement in the merge script and is withdrawn. A new case-by-case review of raw-DXF screenshots found 98 identities visually confirmed correct, 0 visually contradicted, and 14 uncertain. Accuracy among the 98 determinate cases is 100%; 98/112 (87.5%) are confirmed correct across the whole sample. The 14 uncertain identities remain unresolved and need independent evidence.

The whole-pair decision is separate: 54 cases need a person to confirm the complete pair, 56 can be closed, and 2 are uncertain. Among the 110 decided pairs, the observed manual-review rate is 54/110 (49.1%). In the 106 sampled review-state cases, the decisions are 54 yes, 50 no, and 2 uncertain; all six pass-state cases are no. A pair needing review does **not** indicate an incorrect P4 identity. These cases mainly have a missing pair endpoint or a cropped/unclear source-side connection.

No production source was changed, and no pair was promoted from review to pass. The 1,383 review states therefore remain intact. This audit does not estimate a weighted precision for all 1,389 events.

## Population

| P4 event group | Count |
|---|---:|
| Total normalization events | 1,389 |
| Review | 1,383 |
| Pass | 6 |
| Distinct source DWG hashes | 251 |
| Projects | 68 |

The 1,389 events match the same numeric-suffix rule: the fixed SW identity ends in the original numeric value, the preceding identity text contains a letter, and the original value contains a digit. No event matched through exact identity, range, or alias handling. The current rule is in [`superworks_extractor.py`](../../../../src/dwg_audit/audit/superworks_extractor.py#L809-L824), especially the final suffix branch.

| Prefix format after normalization | Population | Review | Pass |
|---|---:|---:|---:|
| `n-number` | 1,010 | 1,007 | 3 |
| `section-n-number` | 357 | 354 | 3 |
| `alpha-num-hyphen-num` | 13 | 13 | 0 |
| `alpha-num` | 9 | 9 | 0 |

## Sampling and results

Every sampled case was judged from its screenshot. The large-format review samples use a seeded draw of one event per selected source DWG hash. Rare-format events were fully enumerated, all six pass events were included, and every source DWG in the wire-component review cohort was represented. The cohort representation is source-level; it is not a census of all 142 wire-component review events.

| Format / inclusion | n | Identity correct | Wrong | Uncertain | Accuracy among determined | Pair yes | Pair no | Pair uncertain |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `n-number`, random review sample | 30 | 28 | 0 | 2 | 100% (28/28) | 17 | 13 | 0 |
| `n-number`, wire-source add-on and all pass events | 4 | 4 | 0 | 0 | 100% (4/4) | 0 | 4 | 0 |
| `section-n-number`, random review sample | 30 | 22 | 0 | 8 | 100% (22/22) | 15 | 13 | 2 |
| `section-n-number`, wire-source add-on and all pass events | 26 | 22 | 0 | 4 | 100% (22/22) | 0 | 26 | 0 |
| `alpha-num-hyphen-num`, full class census | 13 | 13 | 0 | 0 | 100% (13/13) | 13 | 0 | 0 |
| `alpha-num`, full class census | 9 | 9 | 0 | 0 | 100% (9/9) | 9 | 0 | 0 |
| **All reviewed cases** | **112** | **98** | **0** | **14** | **100% (98/98)** | **54** | **56** | **2** |

The two seeded random strata each sample 30 distinct DWG hashes. The `n-number` stratum has 28 confirmed correct and 2 uncertain; the `section-n-number` stratum has 22 confirmed correct and 8 uncertain. Among determinate cases, both observed 100% accuracy; their descriptive 95% Wilson intervals are 87.94%–100% and 85.13%–100%, respectively. Together, 50/60 (83.3%) are confirmed correct, with a 92.87%–100% Wilson interval among the 50 determinate cases. The rare-format rows are full event censuses, and all six pass pairs were audited, so those strata have no sampling uncertainty for the enumerated events. Add-on and overall counts are observed audit results, not binomial estimates.

By pair kind and status, whole-pair review was needed for 30/30 ordinary review pairs, 24/46 semantic review pairs (with 2 uncertain), 0/30 wire-component review pairs, and 0/6 pass pairs. Across the review-state sample this is 54 yes, 50 no, and 2 uncertain. Because the sample is stratified and oversamples rare formats and wire-component sources, this observed rate must not be projected onto the full 1,383 review population.

## Decision

No screenshot showed an incorrect numeric suffix or a contradicted full identity, so this slice produced no error class that justifies a general P4 rule change. Keep the generic suffix rule unchanged, retain the review statuses, and do not infer that identity accuracy alone resolves the full pair. The 14 unresolved identities and 54 whole-pair manual-review cases are separate evidence gaps.

The requested Stage 1 fix workflow (integration tests, single-page validation, 10-project replay, then full replay) was not triggered because this slice produced no source-code fix. The audit should not be read as completing the other Stage 0 source layers or the remaining candidate slices.

## Evidence files

- [`judgements.csv`](judgements.csv): one row per audited case, with screenshot filename and panel row, identity judgement, and separate whole-pair manual-review judgement.
- [`audit_summary.json`](audit_summary.json): population, sample design, counts, and limitations in machine-readable form.
- [`audit_sample.json`](audit_sample.json): the 112 case records with reviewer outcomes.
- [`screenshots/`](screenshots/): all 28 four-case screenshot sheets (112 cases total).
- [`independent_visual_judgments.csv`](independent_visual_judgments.csv) and [`independent_visual_summary.md`](independent_visual_summary.md): per-case raw-DXF identity and pair judgements, including reasons and uncertain cases.
- [`raw_identity_screenshots/`](raw_identity_screenshots/): 83 source screenshot files (28 sheets and 55 expanded single-case views), with SHA-256 and dimensions in [`raw_screenshot_validation.csv`](raw_screenshot_validation.csv).
- [`backplate_title_fallback_census_2026-10-16/README.md`](backplate_title_fallback_census_2026-10-16/README.md): 77-project backplate-page resolver census, including fallback hit/miss counts and the 95 p057 output rows.
- [`tools/build_p4_audit.py`](tools/build_p4_audit.py): deterministic sample and screenshot builder.
- [`tools/merge_p4_judgements.py`](tools/merge_p4_judgements.py): writes the row-level decisions and audit summary.

The CSV's `case_no` and `row_in_screenshot` fields map each decision directly to its screenshot panel. The earlier merge-script identity field is retained only as `legacy_script_identity_judgement`; it was not used as evidence.
