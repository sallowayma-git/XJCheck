# Phase 104 Baseline Freeze

- Freeze date: 2026-07-10
- HEAD: `dccd7d9df909a3e6904ab7a1d45493c09fe9678e`
- Frozen worktree fingerprint: recorded in each `baseline_manifest.json`; all three manifests must agree.
- Pre-change full test baseline: `328 passed in 9.82s`
- Phase A full test result: `333 passed in 9.63s`
- Scope: two established projects plus one held-out third-project probe

Each bundle contains `manifest.json`, complete `findings/`, complete `audit/`, copied `config.yml`, copied arbitration evidence, and `baseline/baseline_manifest.json`. The manifest hashes every artifact, records Parquet row counts, captures Git worktree identity, and checks pair/issue/coverage/topology invariants.

## Frozen Metrics

| Metric | First | Second | Third remote probe |
|---|---:|---:|---:|
| sheets | 28 | 24 | 12 |
| texts | 5,076 | 4,795 | 1,725 |
| lines | 9,441 | 9,465 | 4,819 |
| blocks | 1,117 | 1,206 | 304 |
| legacy pairs | 1,717 | 1,617 | 527 |
| issues | 70 | 6 | 17 |
| legacy wire junctions | 23,148 | 18,929 | 18,537 |
| legacy wire networks | 609 | 358 | 213 |
| unexplained numeric texts | 0 | 0 | 0 |
| unassigned wire segments | 6,868 | 5,305 | 3,683 |
| unclassified blocks | 1,034 | 1,126 | 251 |

Pair-kind baselines:

- First: `ordinary=728`, `table=299`, `continuation=231`, `wire_component=187`, `component=150`, `semantic=119`, `bridge=3`.
- Second: `ordinary=561`, `wire_component=400`, `continuation=204`, `semantic=191`, `table=174`, `component=84`, `bridge=3`.
- Third probe: `ordinary=491`, `component=28`, `table=6`, `continuation=2`; no `wire_component_mapping` or `semantic_mapping` was produced.

All frozen manifests report `true` for pair-kind identity, pair-status identity, issue-rule identity, issue pair-ID resolution, coverage identity, out-of-scope expansion guard, and topology-shadow bounds.

## Bundle Locations

- First: `.tmp/phase104_arch_baseline_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA`
- Second: `.tmp/phase104_arch_baseline_second/2_2`
- Third held-out probe: `.tmp/phase104_arch_probe_third_remote/10000`

These `.tmp` bundles are the local binary baseline. This document is the persistent metric index; future comparison runs must read the manifests rather than copy the numbers from this Markdown file.

## Held-Out Probe Finding

The third project validates the architecture pivot. Its component pages produced 16 ordinary missing-side/low-confidence issues dominated by local pin values (`1`, `2`, `4`, `5`, `6`, `12`, `14`) and only 28 structured component mappings. The established first/second-project `wire_component_mapping` and semantic families did not transfer.

This is evidence for Symbol-Port and semantic attachment work, not authorization to add third-project block names, values, filenames, or coordinates to legacy extractors.

## Interpretation Boundary

`wire_junctions.parquet` and `wire_networks.parquet` in these bundles are legacy T1 shadow artifacts. They are baseline inputs for comparison, not Graph Schema v1 Electrical Nets. Phase B must add new primitive, decision, network-member, open-endpoint, and witness-path artifacts without silently rebranding the legacy tables.
