# Findings: XJToolkit Performance And Lifecycle Audit

## Initial user observations
- ODA DWG conversion currently appears to use fixed concurrency 4 and can make even high-end machines stutter.
- Desired behavior is adaptive admission: avoid starting more work near roughly 80% CPU or memory pressure and reduce active concurrency toward two or one.
- The extraction/pairing process lifecycle and concurrency are unclear; the responsible stalling process is not yet identified.
- Result-page project/issue switching can apparently leave prior rendering work alive while new rendering begins, causing cumulative CPU/memory pressure.
- A settings surface is desired so users can choose automatic performance protection or explicit behavior.

## Evidence
- Repository has a Python engine under `src/dwg_audit` and a React/Tauri desktop application under `apps/desktop`.
- Desktop packaging includes ODA and a Python sidecar under `apps/desktop/src-tauri/resources`.
- Root manifests are `pyproject.toml`; desktop manifests include `package.json`, `Cargo.toml`, `tauri.conf.json`, Vite, and TypeScript configuration.
- Worktree is not clean: root planning files plus `src/dwg_audit/audit/candidates.py` and `tests/unit/test_terminal_candidates.py` are already modified, and root `package-lock.json` is untracked. These are user-owned and must not be reverted or overwritten.
- Current branch is `master`, seven commits ahead of `origin/master`.
- Root README defines the product as a fully local/offline multi-page wiring audit: project scan and manifest, DWG-to-DXF via local ODA, DXF primitive extraction, candidate/pair construction, project-level audit, and Markdown/HTML/Excel output.
- Desktop README states the native call path as `Tauri command -> Python sidecar` with commands for analysis sessions, recent projects, result loading, preview rendering, and issue-status writes. CAD geometry inference belongs to the Python sidecar; the frontend is intended to orchestrate and display only.
- Sidecar resolution prefers an explicit executable, then packaged `sidecar/dwg-audit-sidecar.exe`, with source-Python fallback in development. ODA resolution similarly supports config/env/bundled resource/PATH/Program Files discovery.
- Python runtime has heavy native/data dependencies including pandas, PyArrow, Shapely, ezdxf, and NetworkX. No explicit thread-limiting dependency or runtime setting appears in `pyproject.toml`.
- Desktop stack is React 19 + Tauri 2. Rust enables Windows ToolHelp/process APIs, suggesting explicit process-tree management is present and must be audited.
- The task book's intended dependency order is `Ingest -> Extract -> Layout -> PageClassifier -> PageRouter -> Normalize/PerTypeExtractor -> PairBuilder/TableBuilder -> RuleEngine -> ConfidenceEngine -> Report/UI`; it explicitly forbids RuleEngine reading DWG/DXF and forbids UI rerunning geometry inference.
- The task book separates page-level findings from project audit and states that findings, page findings, conversion cache, previews, and parquet intermediates are session/runtime data that should be cleanable on exit unless debug persistence is enabled.
- It documents page-level parallelism as the natural unit, but also requires later project-level aggregation. This is a likely boundary for bounded scheduling and cancellation ownership.
- Stage A is evidence/candidate production; Stage B reads persisted pair data, builds a project graph, runs rules, and produces user-facing issues/reports. Recomputing geometry in the UI is explicitly out of bounds.
- The task book requires retaining candidates and evidence rather than only winners. Performance changes must control duplicate materialization without weakening traceability.
- The documented page-parallel model never defines a concurrency ceiling, admission policy, resource budget, or cancellation protocol. It states only that page findings may be produced in parallel and later aggregated.
- Stage A can persist many full-column artifacts (`texts`, `lines`, `line_groups`, `pair_candidates`, `pairs`, page findings) even though formal product mode may only need display/export data. This makes persistence mode and projection size explicit performance levers.
- The task book requires conversion logs to include ODA version, duration, audit flag, and failure information, but does not specify CPU/RAM samples, queue wait, process PID, exit reason, peak working set, or per-stage timings.
- A previous productization contract explicitly treated packaged-sidecar smoke as a separate slice from extraction/rule changes. Performance work should preserve that separation: lifecycle/scheduling changes can be tested independently from semantic correctness.
- The product contract favors a default issue list near zero while retaining diagnostic evidence internally. Loading/rendering the full evidence graph for the default list is therefore unnecessary if the backend offers bounded summary/detail projections.
- Findings are the single source of truth, but the documented models are intentionally evidence-rich: text/geometry rows, candidate alternatives, pair evidence arrays, related pair IDs, evidence references, and explanations. Sending these nested records eagerly for every issue/project switch is a likely avoidable payload and React allocation cost.
- The architecture already supplies stable IDs (`sheet_id`, `pair_id`, `text_id`, `line_group_id`) suitable for summary-first APIs and lazy detail hydration; no semantic redesign is needed to avoid full-project result materialization.
- Geometry recognition is designed around STRtree and per-type extractors, so a performance profile should separate indexed local queries from any remaining page-wide nested loops rather than assuming all geometry work is equally expensive.
- RuleEngine consumes categorized relationships and project graph data. It should be run once per completed project generation, not re-triggered by frontend filtering or selection.
- The product design explicitly calls for a temporary-workspace model, lightweight SQLite containing only recent-project summaries/final issues/minimal evidence, and on-demand preview regeneration. This strongly supports lazy preview/detail loading and aggressive cleanup of intermediate DXF/parquet/preview assets.
- The documented sidecar command/event contract includes analyze, load-result, render-preview, list-recent, purge-session, progress, page events, warnings, and terminal run events, but no `cancel-session`, `cancel-preview`, request ID/generation, queue state, or resource telemetry event.
- The sample YAML configuration has geometry/confidence/rule/report controls but no performance section, CPU/memory limits, concurrency cap, adaptive mode, cancellation behavior, cache budget, or debug-retention switch.
- Product UX says settings belong in a dialog or side drawer rather than first-level navigation. That is the established surface for an automatic performance-protection toggle and advanced manual limits.
- The process page requires real-time issue/log updates while analysis continues. Updates therefore need batching/throttling; emitting and rendering one state mutation per engine line/page/issue is not mandated by the product contract.
- Desktop acceptance currently says only that the UI should not crash at about 30 drawings. There are no responsiveness, peak-memory, CPU-headroom, switch-latency, cancellation-latency, or preview-cache acceptance metrics.
- The task book's test plan separates unit/integration/golden/manual evaluation from fault-injection tests. This permits adding deterministic lifecycle tests (cancel, stale generation, child-process cleanup) without changing semantic goldens.
- It identifies reproducibility as a core risk: findings are the single source of truth and rules should rerun from findings. A scheduler should therefore make generation/session IDs explicit and prevent late events from an older run being merged into a newer result.
- The planned future topology graph is substantially richer than the current line-group/pair path. It should not be introduced as an incidental performance fix; first measure current nested loops and materialization, then optimize the existing chain.
- The milestone section confirms desktop productization is still a separate track and explicitly requires sidecar failure recovery and session cleanup, both relevant to the user's lifecycle concern.
- The topology migration contracts add many more parquet relations (primitive segments, graph nodes/edges, decisions, symbol ports, network paths, semantic candidates, constraint alternatives). If eagerly held together or sent through IPC, this future model will amplify the current memory/rendering problem; production mode needs staged writes, bounded projections, and lazy evidence retrieval.
- Topology decisions require retaining possible/rejected/unknown alternatives and witness paths. This reinforces the need for storage-backed detail access rather than React state containing the entire traceability graph.
- The architecture already mandates `shadow -> compare -> primary -> legacy_off`. During compare mode, legacy and topology outputs coexist, so performance baselines must identify that mode explicitly; otherwise doubled CPU/memory can be mistaken for normal steady-state cost.
- No task-book section so far authorizes multiple simultaneous preview generations or retaining preview workers after selection changes. Latest-request-wins cancellation is compatible with all documented evidence requirements.
- Findings V2 defines layered cache keys for reader, geometry, symbol, semantic, and rule stages. Current performance work should preserve these stage boundaries and report cache hit/miss reasons; a coarse all-or-nothing rerun would discard an intended optimization contract.
- The migration gate requires `legacy primary + V2 shadow` and later engine comparison. Resource governance must treat shadow/compare as a distinct high-cost mode with a lower page concurrency ceiling, not use the same fixed setting as legacy-only production.
- Reader completeness and failure-queue rules require failed/incomplete work to remain explainable, but they do not require keeping failed subprocesses or large in-memory documents alive. Cleanup can be immediate after durable failure metadata is written.
- The task book's promotion metrics are almost entirely semantic/quality metrics. Performance metrics need to be added alongside them rather than substituted for them.
- Historical corpus evidence gives concrete scale: 19 non-held-out projects produced about 350,649 canonical-scene records, while a representative semantic shadow graph reached roughly 9,974 nodes and 6,330 relations. These volumes are acceptable on disk but risky when duplicated across pandas/Arrow/Python dicts/JSON/React state.
- Historical runs deliberately materialized census, scene, transform, topology, symbol, semantic, backlog, validation, and comparison artifacts while preserving legacy output. Profiling must record which optional evidence modes are enabled because they materially change peak memory and wall time.
- The production contract keeps all machine-proposed symbol relations shadow-only and forbids them changing legacy results. In a normal user run, such development-only proposal/evaluation artifacts can be disabled or written incrementally without affecting user-visible correctness.
- The long symbol-adjudication history confirms many recognizers retain source geometry, proposals, candidate status, behavior policy, and compatibility output concurrently. This is valuable for development replay but should be governed by a run profile so ordinary desktop analysis does not automatically retain every diagnostic layer in memory.
- Confirmed historical stability defect: the Windows full-corpus single Python process exited nonzero after accumulating four projects, while the same 12000 project succeeded in an isolated replay. The accepted 533-DWG run was recovered by launching each missing project in an independent Python process. The task book explicitly recommends project-level process isolation for roughly 40-drawing inputs to avoid cumulative memory/native-library state contamination.
- This evidence means reducing only ODA concurrency is insufficient. The design needs separate lifecycle control for ODA conversion children and for long-lived Python analysis state, with a bounded project worker process and durable stage outputs between them.
- Historical 533-page runs also show that semantic changes can add over one thousand mappings. Result payload/render cost therefore depends on relationship count, not merely issue count or drawing count.
- Current `configs/default.yml` does not set fixed ODA concurrency 4. It uses `ingest.convert_workers: 0`, documented as a one-time memory-aware default: one worker below 4 GiB available, otherwise two. This is only a static memory tier; it has no CPU sampling, dynamic downshift, hysteresis, foreground/UI reservation, or pressure telemetry.
- The only current runtime setting is `persist_page_findings_files: false`; there is no production/development evidence profile, preview cache budget, result-page projection limit, or cleanup TTL.
- Packaged sidecar retains core Arrow, Parquet, and OpenBLAS native libraries. Packaging evidence lists OpenBLAS around 19 MB and multiple Arrow DLLs; native thread oversubscription remains a concrete code/runtime item to verify.
- Packaging architecture is one Tauri app process, one PyInstaller sidecar executable per command invocation, and ODA as another external process tree. Lifecycle ownership crosses three process layers and cannot be solved by a frontend boolean alone.
- Located the primary implementation surfaces: `ingest/dwg_converter.py`, `readers/oda_reader.py`, `pipeline.py`; desktop Python `lifecycle.py`, `sidecar.py`, `state_store.py`, `preview.py`; Tauri `main.rs` and `sidecar_runtime.rs`; React `App.tsx` and `lib/desktopApi.ts`.
- `App.tsx` is about 101 KB and `symbol_port_proposal.py` about 564 KB, confirming that broad whole-file audits need narrow symbol/call-site targeting to avoid losing lifecycle evidence in unrelated UI/recognition logic.
- The packaged sidecar and ODA binaries are currently present in the workspace, enabling later read-only process/command smoke if needed without rebuilding.

## Confirmed ODA lifecycle
- `src/dwg_audit/ingest/dwg_converter.py:34-76::_available_memory_bytes/_resolve_convert_workers` reads only `ingest.convert_workers`; automatic mode samples available memory once and selects one or two workers. Explicit values override it, clamped only by file count.
- `convert_source_files` uses `ThreadPoolExecutor` and submits every source file immediately. Active conversions are bounded by workers, but queued futures are unbounded and there is no pressure-aware admission or cancellation token.
- `src/dwg_audit/ingest/dwg_converter.py:241-303::convert_one/convert_source_files` makes one synchronous `ezdxf.addons.odafc.convert` call per uncached file and eagerly submits all futures. Production conversion has no timeout, cancel, terminate, or child-tree cleanup; real process creation is delegated to ezdxf/ODA.
- Health-check smoke uses a daemon thread and queue timeout, but timeout only returns `degraded`; it does not stop the background thread or any converter child.
- ODA stage DWGs and converted DXFs are retained. Stage files are not removed on success; partial/failed targets can remain. Cache validation exists, but cache identity enforcement is disabled.

## Confirmed Tauri process lifecycle
- `apps/desktop/src-tauri/src/main.rs:48-138::desktop_analyze_session/analyze_session_blocking` launches a sidecar and later a detached cleanup sidecar; `main.rs:301-317::run_sidecar_json_*` launches a new sidecar for each ordinary JSON command.
- Only preview has a gate, supersession generation, 15-second timeout, and cancel command. Analyze and all ordinary JSON commands have no timeout or cancellation and may overlap.
- `apps/desktop/src-tauri/src/main.rs:518-576` tracks PIDs, not `Child` handles or sessions. `main.rs:579-695` uses ToolHelp/`taskkill`, not a Windows Job Object. Most tree-kill/wait results are ignored; forced shutdown snapshots descendants, protects cleanup, then calls `exit(0)`.
- Analyze stdout parse/read errors can return before `wait`, stderr join, and cleanup. The PID guard then removes the PID without proving child termination/reaping.
- Ordinary commands use unbounded `wait_with_output`; preview reads both streams to unbounded buffers; analyze captures unbounded stderr. Engine output can therefore become an additional memory source.

## Confirmed frontend switching behavior
- `apps/desktop/src/App.tsx:167-187::loadProjectResult` has no request generation or selected-project guard. Rapid A then B selection allows a late A success/error to overwrite B state.
- Each project open launches a fresh full result load; there is no dedupe or project result cache.
- `apps/desktop/src/App.tsx:651-701` has a 240 ms debounce, local cancelled guard, and global cancel on cleanup, so stale preview responses do not overwrite current UI state. `App.tsx:2564-2577::withTimeout` only rejects the wrapper.
- Frontend timeout wrappers reject promises but do not stop the underlying Tauri invoke. Preview cancel has no request ID; it is global.
- `apps/desktop/src/types.ts:75-79` defines full `issues[]` and `page_findings[]`; `apps/desktop/src/lib/desktopApi.ts:192-264` normalizes all rows; `App.tsx:1196-1236` renders every filtered issue. No paging or virtualization is present. `desktopApi.ts:315-321` cache-busts preview file URLs.
- No settings model, get/update-settings API, persistence contract, or settings UI currently exists.

## Existing lifecycle test boundary
- ODA worker selection/cache tests exist, but there is no real ODA subprocess timeout/cancel/tree-cleanup or multi-file pressure test.
- Rust tests cover only generation/PID-vector/parent-map helpers; Python packaging tests assert source tokens. No test launches a child to verify wait/reap/kill/timeout/pipe behavior.
- Frontend has no direct tests for result-load ordering, preview cancellation, large result rendering, or settings.

## Confirmed observability gap
- Repository-wide source search finds wall-clock timing only around individual ODA conversion. There are no extract/pair/audit/store/preview/IPC durations, queue-wait metrics, per-stage RSS/working-set samples, CPU samples, child PID/resource accounting, cache-hit timing, or cancellation-latency metrics.
- `report/artifacts.py` dominates pandas/parquet/JSON iteration and I/O call sites by a wide margin, followed by audit rerun. This proves the artifact layer does the most explicit tabular materialization; it does not alone prove it dominates wall time, so profiler evidence is still required.

## Confirmed Python pipeline lifecycle
- `src/dwg_audit/pipeline.py:analyze_input_root` discovers all project roots and processes them sequentially inside one Python process. This matches the historical cumulative-process failure: project isolation is not implemented in the normal pipeline.
- Each project is fully materialized as Python lists for texts, lines, blocks, polylines, pages, primitive segments, censuses, canonical scenes, symbol proposals, candidates, pairs, and mappings. Additional per-audit/per-route list comprehensions create overlapping list containers, and all route results are accumulated before writing artifacts.
- Extraction, classification, every route extractor, table extraction, accessory extraction, coverage/gate evaluation, and artifact writing are synchronous. There is no page worker pool in the current Python pipeline despite the task-book concept of page parallelism.
- `src/dwg_audit/desktop/sidecar.py:analyze_session` runs the whole workflow, then stores every project result, and only then compacts the session workspace. Failure deletes the entire session workspace.
- `_store_project_run` reads full `findings.json`, loads report frames into pandas, iterates every issue row into nested Python dictionaries, retains all page findings, writes both sets to SQLite, then compaction removes heavy artifacts. This produces a post-analysis memory spike from JSON + pandas + dict duplication.
- Issue status updates reload the latest full project result from SQLite before updating one issue, then may read and rewrite the entire `issues.parquet` and JSON artifact. For compacted runs artifact rewrite is skipped, but the full-result read remains.

## Confirmed persistence and cleanup behavior
- `DesktopStateStore.load_latest_project_result` always `fetchall()`s all issue summaries and all page findings, JSON-decodes every nested field, and returns one complete object. There is no summary/page/detail query, limit, cursor, or selected-issue API.
- SQLite opens a new connection per operation with default journal/timeout behavior; there is no WAL, busy timeout, connection reuse, or explicit cross-process serialization. Because Tauri launches independent sidecars concurrently, result loads/status writes/cleanup can contend on the same DB.
- `compact_session_workspace` calls `list_all_runs()` and then opens a separate update transaction for every matching run before recursively deleting the workspace. Cleanup cost grows with state history rather than querying by session directly.
- `cleanup_transient_workspaces` iterates and updates every stored run, then recursively removes every session and the complete preview cache. `cleanup_stale_workspaces` computes the latest mtime by recursively walking every file in each session/cache entry. These operations can create noticeable disk/CPU bursts and are launched as separate cleanup sidecars.
- SQLite intentionally stores full issue evidence JSON and page summaries. This is sufficient for lazy API projections; the current eager `load_latest_project_result` is the bottleneck, not a storage limitation.

## Confirmed preview/render path
- `src/dwg_audit/desktop/preview.py:render_project_preview` begins every preview by loading and decoding the complete project result from SQLite, then linearly scans the full issue list for one `issue_id`. This happens in a new sidecar process for every accepted preview request.
- If the selected issue has line geometry evidence, preview avoids parquet frames. Otherwise an un-compacted run may load the full report frames (issues/pages/lines/texts/line groups) before filtering one sheet.
- Rendering itself is capped at 240 lines and 160 texts, but only after full frame loading and sheet/extent filtering. It uses pandas `apply(axis=1)` and `iterrows`, which are expensive relative to the small final SVG.
- Each preview writes an SVG cache file and also returns the entire SVG inline. It does not first check whether an identical `(project, issue, sheet, line-group, data-version)` cache entry already exists. Frontend file URLs further bypass cache.
- Compacted completed sessions usually have no artifact directory. Preview then relies on SQLite evidence and synthetic geometry, so retaining or reloading multi-megabyte report frames is not required for the common completed-project path.
- `run_analysis_workflow` runs extraction for every discovered project first, then audits each project afterward. It does not persist/store/compact one project before moving to the next, which increases the lifetime of all per-project artifact directories and delays user-visible final results.
- `render-preview` is not in the sidecar entrypoint's lightweight command set. Every preview starts the full Typer CLI/import graph and pandas-based renderer inside a fresh 52 MB PyInstaller executable. Rapid switching therefore repeatedly pays process startup, one-file extraction/import, SQLite full-result decode, and rendering allocation.
- `list-recent-projects` is lightweight but can run `cleanup_stale_workspaces` before returning, causing recursive session/cache tree walks on what appears to be a simple recent-project query.

## Confirmed audit path
- `src/dwg_audit/report/rerun.py:rerun_audit_from_findings` loads the full report-frame bundle, converts pages/line groups/pairs/terminal candidates row-by-row from pandas into Python dataclasses, builds issues, then constructs more pandas frames and writes multiple audit/shadow/failure/report artifacts.
- Audit V2/shadow/failure evidence is always generated in the same production workflow; there is no desktop production profile to skip development comparison artifacts.
- The audit event stream emits one flushed JSON event per issue. The event path should be batched at the UI boundary; the engine currently cannot coalesce issue events.
- Codebase-wide concurrency search found only the ODA `ThreadPoolExecutor`; extraction, pairing, topology, audit, report generation, and SQLite storage are otherwise synchronous within the analysis sidecar. Apparent CPU saturation may therefore come from one hot process/native libraries plus ODA children, not a hidden Python worker pool.

## Confirmed artifact amplification
- `src/dwg_audit/report/artifacts.py:381-1215::write_project_artifacts` is not a simple writer. In every normal desktop run it builds scale/census/canonical-scene data, symbol inventory/dependency/review artifacts, semantic tokens/attachments/scopes/constraints/graphs, coverage, table structure, wire topology, geometry graph, topology decisions, asserted networks, witnesses, validation, boundaries, legacy equivalence, symbol-port network candidates, endpoint identities, project graph, and engine comparison.
- These V2/shadow computations run even while `recognition.primary_engine=legacy` and historical acceptance says they change zero legacy results. Unconditional shadow computation is therefore a confirmed production overhead and a prime candidate for a `runtime.profile=production|diagnostic|regression` gate.
- The same function constructs many intermediate DataFrames and Python dict/list copies, then writes dozens of Parquet/JSON files before building the final findings payload. Many coexist until function return, creating a high peak-memory region.
- `load_report_frames` unconditionally reads 18 parquet datasets plus issues. Callers that need only pairs/issues/pages still pay for texts, lines, blocks, polylines, candidates, topology, coverage, and other frames.
- `export_existing_reports` reloads this full bundle and `_write_reports` creates prepared-frame copies. HTML serializes whole frames to tables; XLSX writes each supplied frame. Default report formats include Markdown, HTML, and XLSX, so desktop analysis performs all three unless changed.

## Confirmed event and runtime controls
- React batches sidecar events for 80 ms before one state update and caps logs at 40/live issues at 50. Event delivery is not the primary rendering leak, although the reducer repeatedly clones bounded arrays within each batch.
- Frontend prevents a second analyze click only with an in-memory `analysisInFlightRef`; there is no backend session admission/cancel contract, so app reload/crash or a second desktop instance can start overlapping analyses.
- `apps/desktop/src-tauri/src/sidecar_runtime.rs:SidecarRuntime::command` sets only `CREATE_NO_WINDOW` on Windows. It does not set background/below-normal process priority, CPU affinity, Job Object membership, EcoQoS, or native thread caps.
- Sidecar environment injection includes ODA/resource paths but not `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, or Arrow-related limits. Native oversubscription is therefore uncontrolled by the desktop launcher.
- App progress events are batched, but the Python event writer flushes every event immediately. This adds pipe/JSON overhead but is lower priority than process startup, geometry computation, and full-result materialization.
- Desktop analysis does not pass a config path, so `load_config(None)` uses the in-code `DEFAULT_CONFIG`; the current automatic 1/2 ODA worker policy is the actual desktop default, not merely a YAML example.
- Cleanup sidecars alone are launched with `BELOW_NORMAL_PRIORITY_CLASS`; analysis, load, and preview sidecars run at normal priority. The code already demonstrates the desired Windows priority mechanism but applies it only to cleanup.
- Every recent-project query passes the workspace root and `older-than-seconds=3600`, so it synchronously performs stale-workspace/cache traversal before returning the recent list.
- App close always routes through forced shutdown rather than a bounded graceful close. This prioritizes UI exit latency but weakens proof that all descendant work is stopped.

## Hypotheses requiring proof
- Fixed conversion parallelism oversubscribes CPU, RAM, disk, or ODA-internal threads.
- Process concurrency may be bounded while internal native math/Arrow/BLAS threads remain unbounded.
- Desktop IPC may serialize/materialize entire project result sets on every switch.
- Render requests may lack AbortController/generation ownership and stale-response rejection.
- Hidden views, canvas/PDF/image resources, or event listeners may survive project switching.

## Environment constraints
- Packaged `rg.exe` cannot launch due to WindowsApps access denial. Repository discovery uses PowerShell `Get-ChildItem` and `Select-String`.

## Verified report amplification details
- `src/dwg_audit/report/rerun.py:37` loads the complete report-frame bundle at audit start. The same run unconditionally calls `export_existing_reports(project_dir)` at line 226, which calls `load_report_frames` again at `artifacts.py:3671`; a normal rerun therefore loads the bundle twice.
- `artifacts.py:3243-3245::_normalize_report_formats` resolves `formats=None` to `_REPORT_FORMATS = ("md", "html", "xlsx")`. The desktop audit path does not pass a narrower format set.
- `artifacts.py:3636-3663::load_report_frames` checks a fixed set of 17 findings parquet paths plus `audit/issues.parquet` and reads every one that exists. It does not attempt to read missing files, but neither caller intent nor report format narrows this set.
- `artifacts.py:3578::_write_reports` prepares a replacement frame for every supplied report frame. HTML calls `to_html` for each complete supplied frame at lines 3624-3626, and XLSX calls `to_excel` for each at lines 3631-3633. In `export_existing_reports`, those supplied frames are full issues, full pairs, non-pass pairs, and source files; this is not all 18 loaded parquet frames.

## Verified extraction and pairing hotspots
- `audit/line_groups.py:94-112::build_line_groups` scans every active group for each candidate line. For positive gaps it can call `_has_inline_numeric_bridge`, whose line 446 loop scans every text on the sheet. The confirmed worst-case shape is quadratic in candidate lines with an additional text factor on bridge checks; whether real drawings hit that worst case needs profiling.
- `audit/backplate_components.py:104::extract_accessory_backplate_two_port_pairs` repeatedly runs recognizers per block. `_insert_backed_inline_leads` contains a horizontal-line Cartesian loop and ownership helpers repeatedly scan page lines/texts. This is confirmed code behavior; its corpus share is unknown.
- `audit/candidates.py:424/538/654` has three schematic candidate additions that scan the growing global result list per line group before performing local spatial queries. This can approach quadratic behavior in groups/candidates on those routes.
- `audit/pairs.py:238-241::build_pairs` calls `_candidate_coord` four times for each selected pair. `_candidate_coord` linearly scans all terminal candidates even though `build_pairs` already constructs a `candidate_map`; this is a clear avoidable `O(pairs * candidates)` lookup cost.
- `audit/table_extractor.py:1016-1036::_assign_texts_to_cells` materializes every row/column cell and linearly probes cells for every text, giving `O(texts * rows * columns)` work and `O(rows * columns)` cell storage. Its matrix route already uses bisect, demonstrating an available cheaper pattern.
- `extract/cad_extract.py:728-835::extract_cad_artifacts` builds census, canonical scene, normalized primitives, and legacy entity records through multiple document/modelspace passes while retaining the representations together. This is confirmed repeated `O(entities)` work and overlapping memory, but its time share still requires stage profiling.
- Existing positives must be preserved: normal terminal candidate lookup builds one `STRtree` per sheet; pairing limits each side to `top_k=3`; several routes pre-index by sheet/id; and the table matrix route uses bisect. The audit does not support a blanket claim that all geometry code is unindexed.

## Verification inventory and gaps
- Low-risk Python coverage exists for ODA worker selection/cache/health, desktop sidecar/state/lifecycle/preview, CLI adapters, and cache reuse. The focused command set is recorded in `progress.md` and should run with bytecode/cache writes disabled.
- Rust unit coverage checks preview generation supersession, large pipe draining, PID registration cleanup, shutdown filtering, and sidecar runtime policy. It does not launch a real child to prove timeout, cancellation, process-tree termination, or reaping.
- The React package has build/check/lint scripts but no Vitest/Jest/RTL/Playwright test configuration. Rapid project switching, stale load rejection, preview cancellation, large-list rendering, and the proposed settings model currently have no component or end-to-end coverage.
- ODA tests fake the executable/callback and unit-test only worker resolution. There is no real converter concurrency-pressure test, child-tree timeout/cancel test, or cache invalidation test for ODA version/build/options.

## Hypothesis disposition
- The reported fixed ODA concurrency of four is disproven for the checked desktop default: it resolves to one or two workers once at startup. ODA/internal native thread count and resource pressure remain unmeasured.
- Full desktop IPC/result materialization and per-preview fresh sidecar startup are confirmed, not hypotheses.
- Preview stale UI overwrite is locally guarded, but cancellation is global and best-effort; project result loading has a confirmed stale-response race.
- No evidence was found for hidden React views/listeners retaining render work. That remains a profiler/browser-memory question and should not be presented as a confirmed leak.
