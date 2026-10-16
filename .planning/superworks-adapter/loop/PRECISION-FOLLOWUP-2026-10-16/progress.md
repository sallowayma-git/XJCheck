# Progress — 2026-10-16

## Completed

- Resolved all 66 uncertain passing-pair judgments with enlarged/cross-page screenshots and independent terminal-board or SuperWORKS source evidence. Result: 66 correct, 0 wrong, 0 uncertain, 0 manual review. p010/p032 conclusions use non-pipeline evidence.
- Implemented a generic short-lead-to-frame rule. The unique frame-edge intersection must be a segment endpoint; interior crossings remain actionable. The rule also requires a unique closed captioned frame, a matching inside terminal port at the opposite endpoint, and no connection-dot XDATA at the frame contact.
- Individually reviewed the 60 focused wide screenshots, 78 broad frame-candidate screenshots, and six issue-rekey screenshots. The final rule closed 37/39 visually confirmed frame stops, with 0 false suppressions; two interior-crossing examples remain open. The six rekey cases also remain open.
- Recorded the user's separate 54-case wide review as an independent aggregate: 24 frame stops (17/17 rail-T, 7/7 both-end-port), all no-review; its ~4,000 estimate is kept out of the local weighted sample.
- Updated the random stratified manual-review estimate for the eight E subclasses to 3,846–4,011 needing review and 3,516–3,681 implied no-review, out of 7,527. The remaining 4,909 R-GAP rows are out of scope.
- Corrected attribution: disappearance of the mispaired shape came from retiring the FP-FIX lattice, not from this precision follow-up.
- Full test suite, including integration: **2,248 passed, 1 skipped**.
- Final4 single-page replay passed the positive p000 frame stop and retained the p020 explicit-dot T, p013 frame-crossing wire, and p027 frame-crossing-to-terminal controls.
- Final4 10-project replay removed 308 R-GAP issue IDs, added 0, and preserved 19,038 pairs and checked coverage/evidence artifacts.
- Final4 77-project replay removed 2,238 R-GAP issue IDs, added 0, and suppressed 2,304 frame-boundary observations. It preserved 172,193 pair IDs/status/non-evidence fields and all coverage views; three pair evidence cells differ from the previous replay.

## Audit cautions

- The local probability sample, user-reported targeted 54-case audit, 78 broad candidate screenshots, and full replay counts have different sampling bases. Keep them separate.
- `E_rail_T` sample 13 remains a real interior T: raw geometry and explicit connection-dot XDATA show the conductor meeting an internal CONNECT bus before the frame edge.
- p024 and p029 also have interior frame crossings. They remain reviewable because their geometry overlaps false-crossing examples; do not loosen the generic rule based on those two cases.
- The first single-page attempt was stopped because its output directory already existed. It did not overwrite data. A unique retry directory was used for the passing final4 run.

## Delivery

The 66-pair audit is already committed separately. The frame-rule code, tests, audit record, estimates, screenshots, and replay summaries are included in this separate frame-rule commit.
