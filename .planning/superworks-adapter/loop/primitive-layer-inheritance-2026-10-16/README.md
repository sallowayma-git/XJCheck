# Block layer-0 inheritance fix — 2026-10-16

## Change

Nested block entities whose layer is `0` now retain the effective layer inherited from the containing INSERT. Explicit child layers continue to take precedence. ATTRIB layer `0` uses the same inherited layer for its emitted record and visibility check. The primitive algorithm version is now `ezdxf-normalizer-v2`.

The regression test creates nested OUTER/INNER blocks on `WIRE`, verifies both layer-0 children emit as `WIRE`, and verifies an explicit `PIN` child remains `PIN`.

## Validation

- Unit: `python -m pytest tests/unit/test_primitive_normalizer.py -q` — 4 passed.
- Full suite including integration tests: `python -m pytest tests -q` — 2,241 passed, 1 skipped.
- Single page: p000/F0010, representative HATCH `194B0`, three instances; emitted layer is `ECT_CONN_GENERAL_WIRES`. Pair status/value projection and issue projection match the full-project page. One locally generated pair is categorized as `ordinary_pair` instead of the project-context `bridge_mapping`; its endpoints and status are unchanged.
- Ten-project replay: p000–p009. Pairs, issues, coverage, and primitive fields other than layer/version are identical.
- Full replay: 77/77 projects compared against a same-HEAD baseline with only the pre-fix normalizer restored. Of 2,175,002 primitives, 2,951 effective layer values changed across 74 projects; all other primitive fields are identical. Issue and coverage outputs are identical across all projects. Pair outputs preserve all fields except five evidence-only values (four in p037 and one in p072); pair kind, status, endpoint values, and rationale are unchanged. No new issues were produced, so there were no new issue cases to screenshot-review.

The one-page, ten-project, and full replay summaries are retained in this directory. The full per-project comparison is in [`block_layer_full77_comparison.json`](block_layer_full77_comparison.json), with aggregate counts in [`full77_summary.json`](full77_summary.json).
