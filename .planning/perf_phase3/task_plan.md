# Task Plan: Performance Phase 3 (UX-layer optimization)

## Goal
Build on Phase 1/2 (lifecycle + production profile + ODA process isolation) by attacking the three remaining user-visible hot spots the audit flagged but did not implement:

1. **Settings page** so the user can actually override the optimizations already built (preview mode, ODA workers, timeout, cache cap). Defaults must equal current behavior exactly — no new feature is on-by-default.
2. **Result list virtualization + paginated sidecar API** so switching projects and rendering thousands of issues does not load full payload + render full DOM.
3. **Per-project Python worker isolation** so multi-project analysis does not accumulate native-lib state and die after a few projects (the historical regression cited in Phase 2 audit).
4. **Stage telemetry** so future stalls can be attributed to a real stage instead of guesswork.

## Scope / non-goals
- Out of scope: rewriting shadow/topology writer (Phase 4), native algorithm hotspot tuning (still needs profiler).
- No changes to default config contracts: every new toggle ships with the current observed default.
- The existing `load_project_result` (full-result) API MUST stay as the export/diagnostic fallback path; pagination is additive.

## Phases

### Phase 3a: Settings page + persisted overrides
- [ ] New `apps/desktop/src/lib/settings.ts`: typed `DesktopSettings`, `loadSettings()`, `saveSettings()`, localStorage key `xj-toolkit.settings`; one-time migration from legacy `PREVIEW_MODE_STORAGE_KEY`.
- [ ] Extend `Screen` union with `"settings"`; add nav-chip and render branch in `App.tsx`.
- [ ] Settings UI: preview-mode segmented control (reuse `.preview-mode-control`), ODA worker limit number/select (0=auto), ODA timeout seconds, auto-preview toggle, cache cap (null=unlimited). Defaults exactly equal current behavior.
- [ ] New Rust command `desktop_write_settings`: serializes overrides to a YAML fragment under app-data dir; desktop appends `--config <path>` to all sidecar spawns only when a user override exists. Absent → current behavior.
- [ ] Python `_validate_runtime_config` already validates `oda_timeout_seconds`; add validation for `convert_workers` (non-negative int ≤ some sane cap) when surfaced.

### Phase 3b: Virtualization + paginated API
- [ ] Add `@tanstack/react-virtual` to `apps/desktop/package.json`.
- [ ] State store: add `latest_run_for_project`, `count_issues`, `list_issue_summaries_page(run_id, *, limit, offset)`, `load_issue_summary(run_id, issue_id)`, `load_page_findings(run_id)` to `DesktopStateStore` — preserve `load_latest_project_result` verbatim.
- [ ] Sidecar wrappers + CLI subcommands: `load-result-summary`, `load-result-issues` (offset/limit), `load-result-issue-detail`. Tauri command registrations in `main.rs` `generate_handler!` macro.
- [ ] Frontend `desktopApi`: `loadResultSummary`, `loadIssuePage`, `loadIssueDetail` typed wrappers; extract `normalizeIssueSummary` from `normalizeProjectResult` so paginated rows get the same backfill.
- [ ] `App.tsx`: switch result screen to summary + first page; virtualize `<tbody>` via `useVirtualizer` keeping current row JSX; clicking a row below the loaded range fetches `loadIssueDetail`. Keep `loadResult` fallback for export-diagnostics entry (e.g. when total issues ≤ 200 still use the full path).
- [ ] Add types `IssuePage`, `ProjectSummary` in `types.ts`.
- [ ] Tests: new store tests paginating N=5000 synthetic issues; sidecar pagination contract tests; frontend request-generation test (reuses existing `requestGeneration.test.mjs`).

### Phase 3c: Per-project worker isolation
- [ ] New module `dwg_audit.desktop.project_worker`: one project → `run_analysis_workflow` + `_store_project_run` + per-project compact → `SystemExit(0)`.
- [ ] Mirror ODA-worker precedent in `sidecar_entry.py`: new `_run_analyze_project_worker_command` gated on `argv[0] == "analyze-project-worker"`, raising `SystemExit` on completion. Must run before `_run_lightweight_command` to avoid heavy imports polluting the parent.
- [ ] PyInstaller hidden imports: append `dwg_audit.desktop.project_worker` to `build_sidecar_pyinstaller.py:102-133` list (analogous to `dwg_audit.readers.oda_worker`).
- [ ] Rust: in `analyze_session_blocking` (main.rs:70-162), after the discover pass, loop one sidecar child per project using the new subcommand. Pipe children's stdout events through the same emit loop. Preserve `--defer-cleanup`, `spawn_session_cleanup` once at end. Keep current single-sidecar path as the fallback for the `oda_process_isolation: false` diagnostic mode? — decide during implementation.
- [ ] Tests: `test_sidecar.py` event contract (run_started first, run_finished last) must hold across per-project fan-out; new test exercising a single project worker command via `analyze_project_worker_main`.

### Phase 3d: Telemetry
- [ ] New `TelemetryStageWriter` wrapping `DesktopEventWriter`: emits `{"event":"stage_telemetry", stage, pid, rss_kb, elapsed_ms, ipc_bytes}` at stage boundaries.
- [ ] RSS via stdlib `ctypes` (psapi `GetProcessMemoryInfo` on Windows, `resource.getrusage` on POSIX) — do NOT add `psutil` (frozen-package footprint).
- [ ] Wire at `execution.py:47` right after `load_config`: `if config.get("runtime",{}).get("stage_telemetry"): event_sink = TelemetryStageWriter(event_sink)`. Default `stage_telemetry: false` to preserve current output shape.
- [ ] Add `runtime.stage_telemetry: false` to `DEFAULT_CONFIG` + validation; mirror the `oda_process_isolation` branch.

### Phase 3e: P3 audit edge cases
- [ ] Production inventory consistency: assert number of artifacts in manifest == number on disk after a switch from diagnostic → production.
- [ ] Half-DXF cleanup on timeout: verify `convert_one`'s `OdaProcessTimeout` branch removes `target` and clears `odafc_stage` partial output.
- [ ] `_build_findings_payload` production branch: confirm it does not materialize shadow DataFrames in memory even when not writing them.

## Decisions
- Per-project isolation: prefer **Plan A** (Rust-level fan-out) over an in-Python fork, because a forked Python child still shares the parent's loaded native libs (ezdxf/pyarrow/shapely). Re-exec via a fresh sidecar child is the only way to reset native-lib state.
- Pagination contract: rows from the paginated loader MUST be byte-equivalent to rows from `load_latest_project_result["issues"][i]`. The shared `normalizeIssueSummary` helper guarantees this.
- Telemetry default OFF: emitted lines flow through Rust → UI today (`app.emit`), so a new event type silently arrives in the React event handler — adding it ON by default would inflate the event stream under the existing UI even if the UI ignores it.

## Residual risks (carry to Phase 4)
- Native writer shadow compute inside `_build_findings_payload` confirmed not gated by profile — Phase 4.
- Large `reader_run.json` JSON inline in `load_project_result` — Phase 4 (split to Parquet).
- ODA native subprocess hang → PARTIALLY addressed by Phase 3 commit (Job Object isolation); cleanly covered.