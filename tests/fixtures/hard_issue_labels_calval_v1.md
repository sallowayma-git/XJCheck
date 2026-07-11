# Hard-issue labels v1 (calibration/validation freeze)

This fixture freezes **current-head hard-rule issue emissions** on calibration `P001` and validation `P003`.

## Purpose
Provide a measurable hard-issue precision/recall signal for promotion evidence when human held-out labels are unavailable.

## Hard rules
- `R-CROSS-PAGE-CONFLICT`
- `R-DUPLICATE-PAIR`
- `R-ONE-TO-MANY`
- `R-MANY-TO-ONE`

## Non-goals / redlines
- Not a human gold standard of electrical truth.
- Must not be used to tune thresholds against held-out projects.
- Held-out evaluation remains label-free except for structural gates (false-clean, witness, unknown-critical, engine delta).
- True taskbook hard precision >=99% still requires independent human labels before `primary_engine=topology`.

## Matching key
`rule_id + sheet_id + filename + pair_id/left_value/right_value/values`

## Provenance
Frozen from Phase 120 writepath outputs after suite 517 green.
