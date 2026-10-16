# Precision follow-up: uncertain pairs and device-frame short leads

## Objective

Resolve the 66 uncertain passing-pair judgments with independent evidence, then safely close actionable gaps where a terminal short lead ends at a device frame.

## Phases and status

1. **Resolve 66 uncertain pair judgments — complete.** All 66 have per-case screenshots and independent evidence; 66 correct, 0 wrong, 0 uncertain, 0 manual-review cases. The resulting 227/227 source-stratum sample has exact simultaneous 95% finite-population interval 92.58%–100%.
2. **Inspect frame recognition and define a generic predicate — complete.** Require a short orthogonal lead, one unique closed captioned frame, one frame-edge intersection that coincides with a segment endpoint, a matching inside terminal port at the opposite endpoint, and no connection-dot XDATA at the frame contact. Confirmed conflicts and interior frame crossings remain reviewable.
3. **Implement and validate — complete.** Full suite including integration: 2,248 passed / 1 skipped. The final4 single-page controls passed; 10-project replay removed 308 R-GAP issue IDs with 0 added; 77-project replay removed 2,238 with 0 added and suppressed 2,304 frame-boundary observations. Pair identifiers/status/non-evidence fields and coverage views are unchanged; three pair evidence cells differ from the preceding replay.
4. **Audit and deliver — complete.** Individually reviewed all 78 broad candidate screenshots and all six rekey screenshots. Final rule closed 37/39 visually confirmed stops with 0 false suppressions; two interior-crossing stops are conservatively left open. The user-supplied targeted 54-case review is documented separately from local probability samples. Full report, code, tests, and case evidence are delivered in this separate frame-rule slice.

## Sampling results

- Local eight-subclass sample: 240 cases, 151 manual-yes, 83 manual-no, 6 uncertain. Weighted manual need is 3,846–4,011 of 7,527 (51.10%–53.28%); implied no-review count 3,516–3,681. Another 4,909 of 12,436 R-GAP records are outside scope.
- Separate user-reported targeted audit: 24/54 frame stops, including 17/17 rail-T and 7/7 both-end-port, all no-review. The associated ~4,000 estimate is recorded as user-provided and is not pooled into the local weighted estimate.

## Constraints

- Do not use pipeline output as independent pair-identity evidence.
- Preserve SuperWORKS-first routing, coverage contracts, and real unresolved issues.
- Do not add project, handle, block-name, or terminal-value special cases.
- Preserve unresolved frame/lead shapes for review and record their evidence.
- The separate precision-pair slice is committed independently of this frame-rule slice.
