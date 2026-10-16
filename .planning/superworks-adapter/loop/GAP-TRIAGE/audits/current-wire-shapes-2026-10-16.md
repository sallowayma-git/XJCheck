# Current wire-shape residual audit — 2026-10-16

This read-only audit uses the complete current replay at `.tmp/precision_loop_20261015/p057_slice_10` (77 projects; 12,436 `R-RECOGNITION-GAP` rows). It reconciles historical wire-shape names against current fields before considering a repair.

## Findings

- Strict current populations for historical T7, T8, and T11 are all zero. Current production does not emit independent T7/T8/T11 fields.
- The current replay has 17 split refusals: 3 `gap_crossed`, 9 `body_too_narrow`, and 5 `components_not_two`. Rechecking the three `gap_crossed` rows while excluding line-group members found no non-member model line crossing the gap, so none qualifies as T7.
- Current broad GAP-TRIAGE populations are `E_rail_T` 1,777, `E_bus_T` 1,295, `E_reg_element_no_port` 1,453, `E_unreg_pin` 951, `E_unreg_element` 742, `E_port_both_ends` 708, `E_open` 505, and `E_text_only` 96.
- All eight E subclasses have 30 screenshots each, adjudicated one case at a time for whether the local issue still needs human review. These are manual-review labels, not a claim that a visible line proves canonical continuity or that every `yes` is a matching defect.

## Screenshot adjudication: manual-review need

| Current issue subclass | Population | Sample | Needs review | No review | Uncertain | Observed need range |
|---|---:|---:|---:|---:|---:|---:|
| `E_rail_T` | 1,777 | 30 | 4 | 26 | 0 | 13.3% |
| `E_bus_T` | 1,295 | 30 | 16 | 14 | 0 | 53.3% |
| `E_reg_element_no_port` | 1,453 | 30 | 23 | 3 | 4 | 76.7%–90.0% |
| `E_port_both_ends` | 708 | 30 | 22 | 8 | 0 | 73.3% |
| `E_unreg_pin` | 951 | 30 | 30 | 0 | 0 | 100.0% |
| `E_unreg_element` | 742 | 30 | 30 | 0 | 0 | 100.0% |
| `E_open` | 505 | 30 | 16 | 6 | 8 | 53.3%–80.0% |
| `E_text_only` | 96 | 30 | 30 | 0 | 0 | 100.0% |
| **E subclasses** | **7,527** | **240** | **158** | **90** | **14** | **61.4%–65.7% weighted** |

The E-population weighted estimate is **4,619–4,948 / 7,527 (61.4%–65.7%)** requiring human review, counting uncertain cases outside/inside the range. The 95% design-based intervals are 55.9%–66.9% for the lower estimate and 60.7%–70.8% for the upper estimate. Each subclass has a sample size of 30; the estimates weight classes by their current populations and use a finite-population correction.

### Wider screenshot recheck: vertical T and port-to-port

`E_rail_T` and `E_port_both_ends` each received 30 new 4× window screenshots. The reviewer checked whether the vertical line is a closed or dashed device/component outline, with the surrounding enclosure and device caption visible. Every frame-boundary case is recorded as **“terminal short ends at device frame”** and closed under the internal/non-wire rule, so it does not require manual review: all 17/17 frame cases in `E_rail_T` and 7/7 in `E_port_both_ends` are `no`. The port-to-port review also changed one non-frame case to `no` where the crossing node was clear. The rail-T review newly marked three internal T crossings without a black node as `yes`, and resolved two uncertain labels as `no` after the wider view. Across both strata, 29/60 labels changed; every row, reason, frame assessment, and wide screenshot path is retained in the audit CSVs.

This audit covers the eight E subclasses only (60.5% of all `R-RECOGNITION-GAP` rows). The remaining 4,909 rows are in A/B/C/D/X classes and were not adjudicated here. Keep this estimate separate from the rule-level Stage 0 estimate; a revised overall R-GAP manual-review rate needs a taxonomy-wide sample.

One preliminary label was corrected after a root and independent screenshot recheck: `E_text_only` sample 23 (`ISWaa07609ff55017cf8ea8`, p040/S0006) changed from `no` to `yes`. The blue segment reaches the LAN2 side, but the unresolved end is labeled only `MMS B`; that text does not establish canonical identity or cross-sheet continuity. The two wider screenshot reviews add 29 changed row judgments; the correction ledger has 30 rows total including this earlier `E_text_only` correction.

## Evidence and limits

- The population crosswalk, current row counts, split-refusal checks, and sampling scope are recorded in `.tmp/precision_loop_20261015/current_wire_shape_audit_20261016/current_wire_shape_population_20261016.md` and `.json`.
- Case-level judgments and screenshot paths are in [sample_judgments.csv](current-wire-shapes-2026-10-16/sample_judgments.csv); aggregate counts and weighted estimates are in [sample_summary.json](current-wire-shapes-2026-10-16/sample_summary.json); all corrections are in [judgment_corrections.csv](current-wire-shapes-2026-10-16/judgment_corrections.csv).
- The 60 new 4× screenshot records are [rail-T recheck](current-wire-shapes-2026-10-16/wide_recheck_rail_T_2026-10-16.csv) and [port-to-port recheck](current-wire-shapes-2026-10-16/wide_recheck_port_both_ends_2026-10-16.csv). Wide crops are in [wide_screenshots/](current-wire-shapes-2026-10-16/wide_screenshots/); 30 rail-T full-page contexts are in [fullpage_E_rail_T_screenshots/](current-wire-shapes-2026-10-16/fullpage_E_rail_T_screenshots/).
- The 240 cropped screenshots and source contact sheets are under `.tmp/precision_loop_20261015/current_wire_shape_audit_20261016/case_screenshots/` and `png/`. All sample screenshot references exist.
- Historical T7/T8/T11 labels do not map to current independent populations. The sampled E subclasses are broad residual shapes, not interchangeable error types.

No production matching rule or test was changed. This audit did not establish a generic wire-shape repair predicate, so no production repair slice was selected.
