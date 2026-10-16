# P4 device-prefix normalization audit

## Result

This is a read-only screenshot audit of the 1,389 P4 prefix-normalization events across 68 projects. The audit reviewed 112 cases and found 112/112 normalized identities correct, with zero identity-level cases requiring manual verification. It found no P4 misbinding to fix in this sample.

The whole-pair decision is separate: 59/112 audited cases need a person to confirm the complete pair from broader evidence. Of the 106 sampled review-state cases, 59 need that additional review (55.7%); the six pass-state cases need none. Those 59 cases do **not** indicate an incorrect P4 identity. They mainly have a missing pair endpoint or a cropped/unclear source-side connection.

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

| Format / inclusion | Screenshot cases | Identity correct | Observed precision | Whole pair needs review |
|---|---:|---:|---:|---:|
| `n-number`, random review sample | 30 | 30 | 100% | 17/30 |
| `n-number`, wire-source add-on and all pass events | 4 | 4 | 100% | 0/4 |
| `section-n-number`, random review sample | 30 | 30 | 100% | 18/30 |
| `section-n-number`, wire-source add-on and all pass events | 26 | 26 | 100% | 2/26 |
| `alpha-num-hyphen-num`, full class census | 13 | 13 | 100% | 13/13 |
| `alpha-num`, full class census | 9 | 9 | 100% | 9/9 |
| **All reviewed cases** | **112** | **112** | **100%** | **59/112** |

The two seeded random strata each have 30/30 correct identities. Their descriptive 95% Wilson intervals are 88.65%–100%; each draw samples distinct DWG hashes. The two rare-format rows are full event censuses, and all six pass pairs were audited, so those strata have no sampling uncertainty for the enumerated events. The add-on and overall counts are reported as observed audit results, not as binomial estimates.

By pair kind and status, whole-pair review was needed for 30/30 ordinary review pairs, 27/46 semantic review pairs, 2/30 wire-component review pairs, and 0/6 pass pairs. Across the review-state sample this is 59/106. Because the sample is stratified and oversamples rare formats and wire-component sources, the 55.7% rate must not be projected onto the full 1,383 review population.

## Decision

No screenshot showed an incorrect numeric identity, so this slice produced no error class that justifies a general P4 rule change. Keep the generic suffix rule unchanged for now, retain the review statuses, and do not infer that identity accuracy alone resolves the full pair. The 59 whole-pair manual-review cases are a separate evidence gap.

The requested Stage 1 fix workflow (integration tests, single-page validation, 10-project replay, then full replay) was not triggered because this slice produced no source-code fix. The audit should not be read as completing the other Stage 0 source layers or the remaining candidate slices.

## Evidence files

- [`judgements.csv`](judgements.csv): one row per audited case, with screenshot filename and panel row, identity judgement, and separate whole-pair manual-review judgement.
- [`audit_summary.json`](audit_summary.json): population, sample design, counts, and limitations in machine-readable form.
- [`audit_sample.json`](audit_sample.json): the 112 case records with reviewer outcomes.
- [`screenshots/`](screenshots/): all 28 four-case screenshot sheets (112 cases total).
- [`tools/build_p4_audit.py`](tools/build_p4_audit.py): deterministic sample and screenshot builder.
- [`tools/merge_p4_judgements.py`](tools/merge_p4_judgements.py): writes the row-level decisions and audit summary.

The CSV's `case_no` and `row_in_screenshot` fields map each decision directly to its screenshot panel.
