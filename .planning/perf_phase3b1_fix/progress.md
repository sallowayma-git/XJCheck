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
- Full pre-commit verification passed: Python 1155 passed / 1 skipped, Rust 31,
  Node 14, TypeScript check, lint, build, cargo fmt, and Python compileall.
- Created local commit `7ccf3a7 Tighten result pagination, settings round-trip, and ODA cleanup`.
- Added a fixed result-list load-more footer so pagination remains reachable
  when filtering prevents the scroll threshold from firing.

## 2026-07-20
- Recovered the session and confirmed only unrelated user changes remain outside
  commit `7ccf3a7`.
- Completed independent post-commit backend, native, and frontend reviews.
- Confirmed follow-up work for sidecar fallback, result cancellation ownership,
  renderer session isolation, recent-run identity, preview cache identity,
  store detail null semantics, and result-page pagination controls.
- Chose server-side issue filtering/facets rather than hydrating the full result
  in the WebView, preserving the Phase 3b memory reduction.
- Chose an owned Windows process handle plus renderer session epoch and
  cancel-before-begin tombstone for deterministic native cancellation.
- Implemented parameterized SQLite issue filters, whole-run stats/facets, and
  deterministic server ordering without hydrating all issues in the WebView.
- Added result renderer session/epoch propagation, cancellation tombstones, and
  owned Windows process handles around taskkill tree termination.
- Preserved recent-run identity through project selection and pinned all result
  requests to the selected run_id.
- Moved load-more into the result list, added filter retry behavior, and made
  the selected evidence line group drive preview rendering.
- Partitioned default preview cache paths by a hashed run_id and aligned missing
  issue detail with the documented None/null contract.
- Current focused verification passes Python 33, Rust 32, TypeScript check, lint,
  build, Node 14, and Python compile checks.
- Addressed independent follow-up findings for A/B/A query races, stale loading
  flags, status-save query drift, shared session registration, triage evidence
  fallbacks, literal `all` search, and handling-bucket consistency.
- Added keyed request tests, filtered sidecar CLI coverage, default preview cache
  partition coverage, public missing-detail coverage, and legacy schema tests.
- Final verification passes: Python 1160 passed / 1 skipped, Node 16, Rust 32,
  TypeScript check, lint, production build, cargo fmt, compileall, source
  fallback help smoke, and git diff check.
- Created the scoped local follow-up commit.
