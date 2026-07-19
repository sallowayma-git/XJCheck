# Findings: Performance Optimization Phase 2

## Starting evidence
- `dwg_converter.py:293-303` submits every source file to a `ThreadPoolExecutor`, retaining N futures and allowing no runtime pressure feedback.
- Existing automatic worker resolution is a one-time memory tier (`dwg_converter.py:34-76`); explicit `convert_workers` is the existing ceiling contract.
- `oda_execution_environment` wraps the whole converter and mutates global reader environment; it must remain outside worker tasks.
- `artifacts.py:381-1215` computes legacy and diagnostic/shadow artifacts unconditionally. `rerun.py:226` calls export with no formats, causing default md/html/xlsx generation and a second full frame load.
- `sidecar.py:242-291` only requires manifest, findings JSON, pairs, and issues for the stored UI result; most diagnostic frames are not required after compaction.

## Parallel exploration notes
- ODA can sample memory through the existing platform API and CPU through injected `GetSystemTimes`/`/proc/stat` counters without adding psutil. Gate transitions need hysteresis and fail-open handling.
- Production profile should be one validated `runtime.profile` enum (`production`, `diagnostic`, `regression`) plus resolved `report.export_formats`; regression retains current behavior for goldens.

## ODA implementation
- Added a no-dependency `CpuUsageSampler` using Windows `GetSystemTimes`, Linux `/proc/stat`, and normalized load-average fallback.
- Added physical-memory percentage sampling and a fail-open `AdaptiveResourceGate` with 80/65 CPU and 80/70 memory hysteresis defaults.
- Replaced submit-all scheduling with a FIRST_COMPLETED bounded loop. Active work is never killed when pressure reduces the target; only future admission is reduced.
- Reader runs are stored by file ID and returned in source input order, while events remain real-time/completion ordered.

## Runtime profile implementation boundary
- The first production-profile slice will gate rerun diagnostics and automatic report formats, plus add projected parquet loading for rerun/export/desktop storage.
- Direct low-level callers passing `{}` retain regression behavior for compatibility; `load_config(None)` resolves the desktop/default workflow to `runtime.profile=production`.
- The large writer shadow block remains a separately recorded next cut; this slice must not claim those upstream computations are eliminated yet.

## Runtime profile implementation (completed)
- `rerun_audit_from_findings` resolves the profile before loading frames. Production projects request only `pages`, `texts`, `line_groups`, `terminal_candidates`, and `pairs`; diagnostic/regression retain the full frame set.
- Production returns after legacy issue/root-cause output and report export. Witness, Audit V2, failure queue, and topology shadow generation remain available to diagnostic/regression profiles.
- `audit/runtime_profile.json` records `run_profile`, resolved `report_formats`, and whether diagnostics were generated. Known stale optional artifacts and unselected report formats are removed before export; output copies only existing generated files.
- `sidecar._store_project_run` now requests only `pairs` and `issues`, avoiding unrelated Parquet reads during desktop result storage.
- Focused tests pass: `tests/unit/test_config.py` (12), `tests/unit/test_report_artifacts.py` (21), `tests/unit/test_rerun_regression.py` (3).

## Independent review findings
- `load_report_frames(names=None)` must include `audit/issues.parquet`; the first projection implementation accidentally limited the default request set to findings frames only and regressed metrics/sidecar callers.
- Existing rerun unit doubles accept the historical one-argument loader/export call shape. Production needs projected loading, but regression/diagnostic should retain the no-keyword call where possible and tests for production must explicitly model the new optional keywords.
- Rust preview state currently has no cancel-before-begin tombstone and no monotonic generation rejection. Async command registration can therefore resurrect a cancelled preview or let an older generation supersede a newer one.
- ODA adaptive admission invariants passed independent review. Remaining risk: an exception/cancel still exits the executor through `shutdown(wait=True)`, so already-started or hung ODA calls can delay failure indefinitely; this needs process-level cancellation/timeout work, not thread cancellation.
- Frontend navigation may invalidate an active analysis generation even when navigating to the already-active analyze screen; the completion path can then skip result loading and expose an empty result view.

## Review fixes
- Default report-frame loads once again include `issues`; explicit projected loads still read only requested files.
- Regression/diagnostic rerun paths preserve historical no-keyword loader calls, while production uses the new core projection.
- Preview state now retains the latest client request marker, rejects non-monotonic begins, and records cancellation tombstones before registration. Three Rust race tests cover cancel-before-begin, reverse begin order, and newer-cancel supersession.
- Same-screen navigation is a no-op for the analysis intent generation; a pure Node test covers this behavior.

## Next slice evidence
- `write_project_artifacts` interleaves core frame persistence with census/symbol/semantic/topology shadow work. A real production early return requires a dedicated core findings writer; merely gating the final reports would leave most CPU cost intact.
- Result preview can expose a compact three-mode control in the existing inspector header without changing the page layout: automatic, manual-only, and off. The current effect cleanup already provides the correct cancellation boundary when the mode becomes a dependency.
- The Rust preview high-water mark outlives WebView reloads while the React generation restarts from zero. Client-session namespacing is required; otherwise previews fail until the new renderer exceeds the old generation.

## Phase 3 implementation
- `previewPolicy.ts` parses persisted mode values defensively and admits automatic work only in `auto`; `manual-only` consumes an explicit nonce and `off` admits none.
- `desktopApi` carries an optional `clientSessionId` on render/cancel. Rust retires previous renderer sessions, scopes tombstones to a session, and rejects delayed old-session begin/cancel operations.
- `write_project_artifacts` resolves `runtime.profile` before expensive shadow work. Production writes only the core frame set needed by rerun, sidecar storage, and preview, plus findings metadata; direct callers with `{}`/`None` remain regression-compatible.
- Full-suite evidence: production-default tests pass with shadow-specific tests explicitly selecting diagnostic; no legacy regression failures remain.

## Residual lifecycle audit (2026-07-19)
- `apps/desktop/src/App.tsx` stores preview output without its target identity. A new request sets loading/error state but leaves the previous `previewSrc` visible for the debounce and timeout window.
- The preview effect depends on the whole `selectedIssue` object. Saving a status replaces that object even when `issue_id`, sheet, and line group are unchanged, causing cleanup to cancel a manual-only request and clear its committed image.
- The manual-only empty-state branch precedes `previewError`, so a failed manual request cannot show its actual error.
- `PreviewState::activate_client_session` treats any unknown ID as a new renderer after the bounded retired list evicts old IDs. Late begin/cancel calls can therefore clear the current owner before request/generation checks.
- A bounded admission gate cannot cancel a hung `ezdxf.odafc.convert` call: the installed ODA helper invokes `Popen(...).wait()` without timeout. Executor shutdown waits for the Python thread, so native child timeout/Job Object ownership remains a separate native-process task.

## Phase 5 implementation
- Preview output and status now carry independent context keys; a target switch immediately hides old image/loading/error state before the next effect commits.
- Preview requests use an explicit Tauri registration handshake with a server-owned epoch. Unknown, old, missing-epoch, and reserved legacy registrations cannot mutate the current owner.
- Preview request inputs are primitive identities, related-sheet line groups come from matching evidence refs, response project/issue/sheet targets are validated, and a stale debounce callback checks generation before spawning a sidecar.
- Production rerun writes plain issue frames and prunes root-cause/shadow diagnostics. Findings/report inventories honor configured formats, and diagnostic-to-production transitions remove owned stale findings and audit outputs.
- Production core parquet frames are serialized one at a time instead of retaining seven pandas DataFrames simultaneously.
- ODA admission now begins conservatively at two slots (one under startup pressure), clamps non-finite sampling intervals, and tolerates malformed resource-gate mappings.
