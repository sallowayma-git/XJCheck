# Benchmark split v1

Locked on 2026-07-11 for the Topology V2 migration plan.

- Source proposal: `XJCheck_topology_upgrade_review_v1/reports/benchmark_split_proposal.csv`
- Source proposal SHA-256: `eaa6bc1a05cda5d2bb63f02a799aafd5d1d44ac7408dfcd17cfa46248b9e27f5`
- Corpus identity: 27 projects / 502 DWG, verified by Phase 112 clean run.
- Stable identity: `project_id + project_name + dwg_count`; absolute source paths are intentionally excluded.
- Distribution: 2 `calibration_legacy`, 12 `training_candidate`, 5 `validation`, 8 `heldout_test`.

Rules:

1. Splits are project-level; pages from one project must never cross splits.
2. `calibration_legacy` preserves the two historically tuned projects and is not generalization evidence.
3. `validation` may be used for threshold and implementation selection.
4. `heldout_test` is release-gate only. If its result influences a code, rule, symbol-library, threshold, or model change, that project loses held-out status and this fixture must be versioned again.
5. Similar block definitions and contract-family near-duplicates must be checked for leakage before any learning dataset is exported.
