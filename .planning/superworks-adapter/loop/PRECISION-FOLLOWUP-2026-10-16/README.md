# Precision follow-up — 2026-10-16

This follow-up resolves the 66 uncertain passing-pair judgments and implements a general rule for short terminal leads that end at a device frame. The passing-pair audit is recorded separately in [uncertain-66](uncertain-66/). The frame rule and its evidence are under [frame-rule](frame-rule/).

## Resolved passing pairs

- All 66 previously uncertain pairs now have a per-case judgment, independent source evidence, reviewer, screenshot references, and screenshot SHA-256 entries in `uncertain-66/case_review.csv` and `uncertain-66/screenshot_index.csv`.
- The result is 66 correct, 0 wrong, 0 uncertain, and 0 requiring manual review. Cross-page cases retain both page views; source checks use raw terminal-board rows, SuperWORKS records, or raw `LD_PARTCONNECTLINE` XRECORDs rather than pipeline-derived identity output.
- The source-stratified sample is 227/227 correct across 78,993 passing pairs. The point estimate is 100%; the exact simultaneous 95% finite-population interval is 92.58%–100%.
- Reproduce the merge and score with `python uncertain-66/merge_and_score.py`.

## Terminal short lead ending at a device frame

The production rule suppresses an actionable gap only when a short orthogonal lead (at most 50 drawing units) has exactly one intersection with one closed, captioned device frame, and that intersection is itself a segment endpoint. Its other endpoint must attach to exactly one inside SuperWORKS terminal port whose own label matches the frame caption exactly or by a numeric-only terminal suffix. An explicit SuperWORKS connection dot at the frame contact, a terminal contact on the frame edge, multiple candidate frames, or any frame intersection inside the segment prevents suppression. Confirmed conflicts remain issues. No project, handle, block-name, or terminal-value exceptions are used.

This endpoint requirement was added after six earlier candidate suppressions were visually and geometrically confirmed to cross the frame with electrical evidence on both sides. They remain manual issues. Two additional broad-review examples also have an interior frame intersection and are conservatively left open.

### Manual-review estimates and the separate 54-case review

The local probability sample contains 240 cases: 30 from each of eight `E_*` subclasses. Its final labels are:

| Subclass | Needs review | No review | Uncertain |
|---|---:|---:|---:|
| `E_rail_T` | 5 | 25 | 0 |
| `E_bus_T` | 16 | 14 | 0 |
| `E_reg_element_no_port` | 6 | 22 | 2 |
| `E_port_both_ends` | 23 | 7 | 0 |
| `E_unreg_pin` | 28 | 2 | 0 |
| `E_unreg_element` | 30 | 0 | 0 |
| `E_open` | 19 | 7 | 4 |
| `E_text_only` | 24 | 6 | 0 |
| **Total** | **151** | **83** | **6** |

Population weighting estimates 3,846–4,011 of the 7,527 in-scope gaps still need manual review (51.10%–53.28%). The design-based 95% intervals are 45.45%–56.76% for the lower estimate and 47.51%–59.06% for the upper estimate. The corresponding estimated no-review population is 3,516–3,681. A further 4,909 of the 12,436 total `R-RECOGNITION-GAP` records are outside these eight subclasses and are not covered by this estimate.

Separately, the user reported a targeted 54-case wide recheck: 24 visible frame stops, including 17/17 `E_rail_T` and 7/7 `E_port_both_ends`; those 24 do not require manual review. The user-provided estimate is that about 4,000 gaps can be removed from manual review. This targeted count is kept separate from the local probability sample and is not pooled into its weighted estimate. The aggregate is recorded in `frame-rule/manual_review_estimates.json`.

The local 60-case focused wide sample independently found 16/30 frame stops in `E_rail_T` and 6/30 in `E_port_both_ends`; every such stop was labeled no-review. These judgments and screenshot hashes are recorded case by case in `frame-rule/shape_samples_60/` and the wire-shape audit CSVs.

### Rule-level visual audit and replay

- All 78 broad candidate screenshots were adjudicated individually. Of 39 cases judged true frame stops, the final rule closed 37 and left 2 open because the frame contact lies inside the observed segment. It closed 37 reviewed cases and had 0 false suppressions. The six issue-ID rekey cases were also screenshot-checked individually and retained as manual issues.
- Full suite including integration tests: **2,248 passed, 1 skipped**.
- Single-page controls: the p000 labeled-frame stop closed; the p020 explicit-dot T, p013 frame-crossing wire, and p027 frame-crossing-to-terminal controls stayed open.
- Ten-project replay: **308** `R-RECOGNITION-GAP` issue IDs removed, **0** added; 19,038 pairs and checked coverage/evidence artifacts unchanged.
- Full 77-project replay: **2,238** `R-RECOGNITION-GAP` issue IDs removed, **0** added; 2,304 frame-boundary observations suppressed. All 172,193 pair IDs/status/non-evidence fields and all coverage views match the baseline. Three pair evidence cells differ from the previous replay. All removed issues belong to `R-RECOGNITION-GAP`.
- The exact comparison, sample score, single-page summary, source code, and focused tests are linked from `frame-rule/compare_final4_full/validation_summary.json`, `frame-rule/review_score_final4.json`, and the adjacent evidence files.

The weighted estimate describes the sampled E-subclass population. The replay counts describe actual rule decisions. They use different bases and should not be substituted for each other.
