# Phase 3b.1 Findings

## Reviewed defects
- Windows ODA children can escape before the outer worker is assigned to its Job Object.
- Project switching ignores stale results but does not cancel full-result sidecars.
- Mutable updated_at is incorrectly used as the latest-run identity.
- COUNT and page SELECT are not in one read transaction.
- Rust settings use nested snake_case while the frontend expects flat camelCase.
- Resetting settings does not remove the persisted backend override.
- Cache-cap and stage-telemetry controls have no Python consumers.
- The first Windows CPU sample has no delta and cannot gate startup on CPU pressure.
- Virtual rows assume 44 px despite wrapping content.
- Native missing issue detail errors while the typed API promises null.

## Verification baseline
- Review-only focused tests passed: Python 39, Node 15, Rust 29.

## Design decisions
- Keep the existing schema and order latest runs by created_at DESC, run_id DESC.
- Pin modern page/detail/status requests to the run_id returned by summary.
- Start an explicit SQLite read transaction before COUNT plus page SELECT.
- Preserve legacy project-only load-result as a compatibility path.
- On Windows timeout, taskkill the visible tree before closing the named Job.
- Preserve the worker's named-Job self-join before stdin request processing.
- Treat an unknown first CPU sample as startup pressure and admit one slot.
- Return flat camelCase settings to the frontend while persisting nested config.
- Remove cache-cap and telemetry controls until Python consumers exist.
- Reset defaults through the native write command so the override file is removed.
- Hydrate issues in bounded pages pinned to one run; cancel superseded native loads.
- Measure virtual rows dynamically and add keyboard/row-count semantics.

## Independent review notes
- PowerShell 5.1 cannot rely on Process.Kill(entireProcessTree); use taskkill /T /F.
- Missing issue detail must emit JSON null while missing runs remain errors.
- Preview also needs an optional run_id pin to avoid summary/preview run drift.
