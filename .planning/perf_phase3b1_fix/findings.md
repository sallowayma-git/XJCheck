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
- Post-commit review confirmed result-load cancellation needs session isolation,
  a cancel-before-begin tombstone, and owned process handles rather than delayed
  termination by a bare PID.
- Source-development fallback must execute `dwg_audit.desktop.sidecar_entry`;
  lightweight paging commands are not registered on the Typer CLI.
- Recent-run selection must preserve run_id through summary, page, detail, and
  preview calls. Project-only selection silently opens the newest run.
- The explicit load-more action belongs in the result issue list; scroll-only
  loading makes later pages unreachable after restrictive filters or errors.
- Preview output paths need run identity, and selected evidence line groups must
  drive the preview request rather than only visual selection state.
- Store-level missing issue detail should return None consistently instead of a
  truthy wrapper whose issue field is None.

## Follow-up design
- Register a dedicated result renderer session and server-issued epoch. Every
  summary/page/detail/cancel call carries session id, epoch, and client
  generation so a WebView reload cannot inherit a stale generation namespace.
- Result cancellation records a tombstone even when it races ahead of begin.
- On Windows, keep an owned process handle for each result sidecar until
  cancellation/finish. `taskkill /T /F` terminates the tree and the handle
  terminates the root while preventing PID reuse across the unlocked gap.
- Keep issue payloads bounded by pushing search/facet filters into SQLite.
  Summary returns whole-run stats and filter options; page total represents the
  filtered query while issue_count remains the unfiltered total.
- Keep result identity as `(project_id, run_id)` in React selection and recent
  rows, and keep preview cache paths partitioned by run_id.

## Follow-up review resolution
- Keyed query refs and testable commit/reload guards close the A -> B -> A
  filter race; navigation clears both load-more and query-reload state.
- A shared registration promise prevents concurrent renderer-session callbacks
  from clearing a successfully registered epoch.
- SQLite now materializes handling_class for new rows and uses the same Python
  derivation UDF for legacy rows, so stats, filters, and returned rows agree.
- Triage uses one expression across direct columns and both evidence fallbacks;
  literal search text such as `all`, `%`, and `_` remains literal.
- Successful load-more requests clear prior errors, while failed query reloads
  retain an explicit retry action in the result list.
