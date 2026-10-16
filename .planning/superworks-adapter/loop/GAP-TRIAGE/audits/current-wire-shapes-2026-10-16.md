# Current wire-shape residual audit — 2026-10-16

This audit uses the 77-project current replay (`.tmp/precision_loop_20261015/p057_slice_10`), containing 12,436 `R-RECOGNITION-GAP` records. Historical wire-shape labels were reconciled to current fields before reviewing potential fixes.

## Population and scope

- Current strict populations for historical T7, T8, and T11 are zero; production does not emit those as independent fields.
- The replay has 17 split refusals: 3 `gap_crossed`, 9 `body_too_narrow`, and 5 `components_not_two`. Rechecking the three `gap_crossed` rows while excluding line-group members found no non-member model line crossing the gap, so none qualifies as T7.
- Broad current populations are `E_rail_T` 1,777, `E_bus_T` 1,295, `E_reg_element_no_port` 1,453, `E_unreg_pin` 951, `E_unreg_element` 742, `E_port_both_ends` 708, `E_open` 505, and `E_text_only` 96.
- The eight sampled E subclasses contain 7,527 records, 60.5% of the total. The remaining 4,909 records are outside this audit's manual-review estimate.

## Random stratified sample: need for manual review

Each E subclass has 30 sampled cases. A screenshot judgment answers whether the current issue still needs human review; it does not assert canonical continuity or that every `yes` is a matching defect.

| Current issue subclass | Population | Sample | Needs review | No review | Uncertain |
|---|---:|---:|---:|---:|---:|
| `E_rail_T` | 1,777 | 30 | 5 | 25 | 0 |
| `E_bus_T` | 1,295 | 30 | 16 | 14 | 0 |
| `E_reg_element_no_port` | 1,453 | 30 | 6 | 22 | 2 |
| `E_port_both_ends` | 708 | 30 | 23 | 7 | 0 |
| `E_unreg_pin` | 951 | 30 | 28 | 2 | 0 |
| `E_unreg_element` | 742 | 30 | 30 | 0 | 0 |
| `E_open` | 505 | 30 | 19 | 7 | 4 |
| `E_text_only` | 96 | 30 | 24 | 6 | 0 |
| **Total / weighted estimate** | **7,527** | **240** | **151** | **83** | **6** |

Population weighting gives **3,846–4,011 / 7,527** requiring manual review (51.10%–53.28%). Design-based 95% intervals are 45.45%–56.76% for the lower estimate and 47.51%–59.06% for the upper estimate. The implied no-review estimate is **3,516–3,681**. Uncertain cases are excluded from the lower estimate and included in the upper estimate. Per-case judgments are in `current-wire-shapes-2026-10-16/sample_judgments.csv`; aggregate calculations are in `sample_summary.json`.

## Expanded frame checks

### Local 60-case focused sample

The local random wide recheck used 4× windows and recorded each case, rationale, and screenshot path. It found 16/30 frame stops in `E_rail_T` and 6/30 in `E_port_both_ends`. All 22 were classified as no-manual. Other sample cases remain classified by their own manual-review evidence; frame appearance alone does not prove the connection.

`E_rail_T` sample 13 remains a real interior T: raw source line L2364 reaches CONNECT bus L2294 at (275,105), an explicit SuperWORKS connection-dot XDATA marks the junction, and the nearest frame edge is x=280. Both endpoints are internal-element contacts without a terminal-port attachment. It remains a manual issue. Its screenshot is `current-wire-shapes-2026-10-16/wide_screenshots/E_rail_T_13.png`; the row and correction are in `wide_recheck_rail_T_2026-10-16.csv` and `judgment_corrections.csv`.

The local sample and its corrected manual-review labels are kept distinct: the 60-case focused recheck has its own screenshot manifest, while the 240-case class sample feeds the weighted estimate. Do not substitute the focused frame-stop fraction for the population-weighted estimate.

### Separate user-reported targeted review

The user separately reported a 54-case wide review with 24 true frame stops: 17/17 `E_rail_T` and 7/7 `E_port_both_ends`, all requiring no manual review. The associated estimate is approximately 4,000 gaps that can leave manual review. This targeted aggregate is not pooled into the local stratified estimate. The current workspace records the aggregate in `frame-rule/manual_review_estimates.json`; it does not contain a 54-row screenshot index.

### Production rule and broad screenshot audit

The generic `terminal_frame_boundary` rule in `src/dwg_audit/audit/recognition_coordinator.py` accepts only a short orthogonal lead with one unique closed, captioned frame intersection at the segment endpoint, plus one matching inside SuperWORKS terminal port at the other endpoint. Explicit connection-dot XDATA at the contact, a terminal contact on the frame edge, ambiguous frame candidates, confirmed conflicts, and any frame intersection in the segment interior prevent suppression. This endpoint check preserves real wires that cross the frame.

All 78 broad candidate screenshots were reviewed individually: 39 true frame stops, 37 non-stops, and 2 uncertain. Final4 suppressed 37 of the 39 confirmed stops; 0 reviewed non-stop or uncertain cases were suppressed. The remaining two confirmed stops have an interior frame intersection and stay open under the conservative generic rule. Six cases whose issue IDs changed as adjacent groups shrank were also individually screenshot-checked; all six remain manual issues because they are conductor crossings with visible electrical evidence, not frame stops.

Final4 full replay results: **2,238** R-GAP issue IDs removed, **0** added, and **2,304** frame-boundary observations suppressed across 77 projects. All 172,193 pair IDs/status/non-evidence columns and all coverage views match the baseline; three pair evidence cells differ from the previous replay. See `frame-rule/compare_final4_full/validation_summary.json` and `frame-rule/review_score_final4.json`.

The full suite, including integration tests, passed (**2,248 passed, 1 skipped**). Single-page positive and negative controls and the 10-project replay also passed; the 10-project replay removed 308 R-GAP issue IDs with none added.

## Evidence and limits

- 240-class sample records: `current-wire-shapes-2026-10-16/sample_judgments.csv`, `sample_summary.json`, and `judgment_corrections.csv`.
- Local wide sample rows/screenshots: `wide_recheck_rail_T_2026-10-16.csv`, `wide_recheck_port_both_ends_2026-10-16.csv`, and `wide_screenshots/`.
- Population crosswalk and split-refusal checks: `.tmp/precision_loop_20261015/current_wire_shape_audit_20261016/current_wire_shape_population_20261016.md` and `.json`.
- The local probability estimate covers only the eight E subclasses. The targeted 54-case audit is a separate user-provided aggregate. The replay issue-removal count is an implementation result, not an extrapolated manual-review estimate.
- Historical T7/T8/T11 names do not map to current independent populations. Sampled E subclasses are broad residual shapes and should not be treated as interchangeable error types.
