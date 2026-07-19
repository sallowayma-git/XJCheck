# Phase 3b.1 Progress

## 2026-07-19
- Recovered the prior review context and inspected the dirty worktree.
- Preserved unrelated root planning, audit-rule, rule-test, and package-lock changes.
- Created this isolated implementation plan.
- Completed three independent read-only design probes for ODA, state, and desktop.
- Selected existing-schema and existing-dependency fixes; no new dependency is needed.
- Implemented immutable run ordering, pinned run lookup, and snapshot-consistent summary/page reads.
- Added optional run_id through Python sidecar and public CLI paths.
- Pinned preview reads to one run and removed its full-result issue scan.
- Added Windows tree-kill fallback before Job close and hardened packaging smoke cleanup.
- Made unknown startup CPU pressure admit one ODA slot.
- Added a Rust result-load generation registry that kills stale sidecar trees.
- Converted native settings responses to flat frontend shape and propagated delete failures.
- Removed cache-cap and telemetry controls because no backend consumers exist.
- Migrated App result loading to a pinned first page plus scroll-driven additional pages.
- Added dynamic virtual-row measurement, stable keys, row counts, and keyboard selection.
- Focused verification currently passes Python 61, Rust 31, and Node 14 tests.
