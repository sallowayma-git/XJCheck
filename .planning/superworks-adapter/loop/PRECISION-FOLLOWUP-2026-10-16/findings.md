# Findings — 2026-10-16

## Passing-pair precision

- The requested source-stratum subset is exactly 66 rows from 227 source-stratified pass-pair judgments, not all 139 uncertain `pass` labels across overlapping audit margins.
- Independent review resolved the 66 as correct: 0 wrong, 0 uncertain, and 0 requiring manual review. p010 and p032 now use raw source records and terminal-board evidence; no pipeline-derived identity output was treated as independent proof.
- The updated source-stratified sample is 227/227 correct across 78,993 passing pairs. Its point estimate is 100%, with exact simultaneous 95% finite-population interval 92.58%–100%.
- Case judgments, screenshots, raw-source references, and hashes are under `uncertain-66/`.

## Device-frame short-lead rule

- The generic predicate requires a short orthogonal segment, a unique closed captioned frame, exactly one frame-edge intersection at a segment endpoint, and exactly one inside SuperWORKS terminal contact at the other endpoint. That port's label must match a frame caption exactly or by a numeric-only suffix. An explicit connection dot, ambiguous frame, frame-edge terminal contact, interior frame crossing, or confirmed conflict blocks suppression.
- Six false suppressions from an earlier relaxed predicate were individually screenshot-checked and rejected. Raw geometry showed interior frame crossings with electrical evidence on both sides. The strict endpoint rule retains them for review.
- The local focused 60-case sample found 16/30 true frame stops in `E_rail_T` and 6/30 in `E_port_both_ends`; all 22 were judged no-review. The local 240-case stratified sample has 151 manual-yes, 83 manual-no, and 6 uncertain labels.
- Weighted over the 7,527 records in the eight sampled E subclasses, estimated manual need is 3,846–4,011 (51.10%–53.28%), with design-based 95% intervals of 45.45%–56.76% and 47.51%–59.06%. The implied no-review population is 3,516–3,681. The other 4,909 R-GAP records are out of scope.
- The user separately reported a targeted 54-case review: 24 frame stops, including 17/17 rail-T and 7/7 both-end-port, all no-review, and an estimated ~4,000 gaps removable from manual review. This targeted aggregate is not pooled into the probability estimate.
- The final rule closed 37 of 39 visually confirmed frame stops in a 78-candidate screenshot audit, with 0 false suppressions. Two true stops remain open because their frame contact lies inside the observed segment.
- Final4 full replay removed 2,238 R-GAP issue IDs and added 0; it suppressed 2,304 frame-boundary observations. Pair count and coverage views are unchanged, and all removals are R-GAP. Three pair evidence cells differ from the preceding replay.
- Full suite passed: 2,248 passed, 1 skipped. Single-page positive and three negative controls, plus the 10-project replay, passed.

## Attribution correction

The earlier “mispaired shape disappeared” observation is attributable to retiring the FP-FIX lattice. It is not an outcome of this precision follow-up. Do not cite it as evidence for the frame rule or as a precision improvement.

Detailed counts and per-case evidence are in `frame-rule/manual_review_estimates.json`, `frame-rule/sample_frame_review.csv`, `frame-rule/review_score_final4.json`, `frame-rule/compare_final4_full/validation_summary.json`, and `GAP-TRIAGE/audits/current-wire-shapes-2026-10-16.md`.
