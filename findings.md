# Findings: Topology Upgrade Review Migration

## 2026-07-10 Initial orientation

- The repository already has a long-running topology-first migration plan. The current recorded phase is Phase 105, with a geometry-only shadow graph and four-state observations already implemented.
- Existing retained assets include Geometry Graph shadow artifacts, legacy compatibility outputs, frozen baselines for two established projects plus one held-out project, and a documented five-layer target model.
- The new review package contains 16 documents (`00` through `15`) covering evidence, target architecture, algorithms, schemas, migration tasks, acceptance gates, dependencies, drawing-type strategies, and local-agent execution instructions.
- The immediate task is therefore a delta review: compare the package against the current Phase 104/105 implementation, identify authoritative differences, then begin the smallest safe migration slice without regressing frozen baselines.

## Tooling notes

- `rg.exe` is present through the desktop app bundle but fails to start with Access Denied in this workspace. Use PowerShell `Get-ChildItem`, `Select-String`, and `Get-Content` as the fallback.

## Review-package constraints and first delta

- The package explicitly optimizes for unseen-project generalization, not lower issue counts on the first two projects.
- Hard constraints align with the current architecture reset: no filename/page/value patches; text proximity cannot establish connectivity; POSSIBLE edges cannot be unioned; unknown symbols cannot yield critical conclusions; retain alternatives; extraction failure is not a clean result; core inference stays out of report/UI; legacy remains until V2 gates pass; every change needs reproducible commands and a comparison report.
- The package was produced against an older repository snapshot (`323 passed`, 46 source files / 33 test files). The current repository history records `342 passed` and already implements several requested first-loop items: topology shadow placement, four-state observations, ASSERTED-only geometry components, frozen legacy baselines, and pair-to-geometry comparison.
- The package's remaining first-loop sequence starts with cross-platform ODA discovery and a 27-project current-head baseline. Those may precede Symbol-Port work if current code still has fixed-path ODA detection.
- Required verification for each slice is broader than a unit/full test pair: targeted unit, synthetic fixture, full suite, first/second compatibility, validation projects, and engine comparison.

## Evidence, architecture, and topology algorithm delta (`01`-`05`)

- The review's central diagnosis matches the repository's Phase 104 reset: the old chain builds `Pair` before topology, so topology is evidence rather than connectivity truth; the target is `Topology + Symbol Port + Text Role + Constraint`.
- Third-group corpus evidence materially expands migration scope: communication pages, device-port layouts, terminal tables, backplates, and unknown pages are common. A single route target is insufficient; the package calls for multi-label capabilities such as wire network, symbol ports, terminal grid, table mapping, backplate layout, communication medium, and cross-page audit.
- `.prj` and `LdDzbInfo.xml` should become weak-semantic `ProjectProfile` inputs. Page numbers are not unique (duplicate `04` exists), and empty extraction must be marked `INCOMPLETE_EXTRACTION`.
- The target dependency direction is Reader -> Primitive -> Geometry/Symbol-Port -> Nets/Semantics -> Constraint -> Project Graph -> Audit -> UI/Report. No upper layer may mutate lower-layer facts.
- Current Phase 105 covers a subset of the topology algorithm: line-based geometry, strict snapping, T/intersection handling, marker evidence, four-state shadow observations, and asserted components.
- Important topology work still implied by the package: backend-neutral `CadDocument`; complete primitive normalization (polyline parent provenance, nested block transforms/ownership, curves, layer role); spatial index module; formal topology decision trace; SymbolPort-aware boundaries; ASSERTED-only `ElectricalNetwork`; open endpoints and witness paths; adaptive tolerance profiles; page-zone/table/communication exclusions; and debug overlays.
- Existing strict tolerance (`0.05`) is a deliberate Phase 105 redline. The package's adaptive tolerance formula should first generate/configure candidate tolerances and be proven against baselines; it must not silently widen asserted connectivity.
- The package confirms that neighborhood calculations remain valid only for candidate generation/features and legacy comparison, never as connectivity or final-pair truth.

## Symbols, inference, project graph, and Findings V2 (`06`-`10`)

- Symbol work is deliberately minimal-connectivity-oriented: recognize electrical object status, transformed ports, direction, internal connectivity, and text slots—not full device simulation. Only `permanent_connected` and `isolated` are safe for MVP automation; conditional/switch/pass-through/unknown remain boundaries or review.
- Symbol-library bootstrap is corpus-driven (`blocks.parquet` -> normalized definition hashes -> transforms/entry clusters/text slots -> impact-ranked human review). Block names are features, not identities. Every family needs provenance, version, verified instances, fixtures, and deprecation metadata.
- The inference order is deterministic candidates -> global constraints -> explainable ranker -> optional heterogeneous GNN. Models follow `OFF -> SHADOW -> REVIEW_ASSIST -> LIMITED_AUTO`, split strictly by project/near-duplicate block family, and never directly produce critical issues.
- Project-graph rules consume asserted networks, selected semantic attachments/cross-page matches, unresolved evidence, project profile, and a rule scheme. They must not compare all numeric texts globally. Endpoint identities retain namespace/strip/local scope, e.g. `terminal:5FD:25`.
- Issue clustering should group symptoms by shared topology decision/network/endpoint, so one bridge root cause does not surface as several independent issues.
- A structured failure queue is a required migration product, with page-level quality gates and decision-specific review labels. Review feedback must update a topology rule, symbol library, scope rule, constraint, dataset, profile, or whitelist—not an issue-specific patch.
- Findings V2 formalizes `PrimitiveSegment`, `TopologyDecision`, `SymbolPort`, `ElectricalNetwork`, `SemanticAttachment`, and `CrossPageMatch`; raw facts and inference are separated, alternatives and score breakdowns are retained, and every Issue must trace back to DWG handles.
- Version/cache contracts are explicit and layered. Current Phase 105 shadow tables should migrate through an additive schema path rather than be renamed in place before comparison coverage exists.

## Migration epics, acceptance gates, and page strategy (`11`-`14`)

- The package defines an ordered backlog from Baseline/Reader/Primitive/Geometry through Symbols/Networks/Semantics/Constraints/ProjectGraph/Audit, then Page Strategy/UI/Learning. This is more granular than current Phase 105-109 and should become the implementation checklist.
- Current recorded completion maps approximately to parts of Epic 0 and Epic 3, but not the full prerequisites: 27-project corpus baseline and confirmed project-level train/validation/test split are not recorded; Reader Adapter and Primitive Model are not recorded complete.
- This exposes an ordering correction: before promoting Phase 105 shadow observations to formal V2 networks, verify Reader completeness and primitive provenance contracts. Otherwise V2 would formalize a graph built on a backend-specific/incomplete input contract.
- Release gates prioritize safety: Reader completeness is 100% or explicitly incomplete; asserted-crossing false connects near zero; hard-issue precision >=99%; witness completeness 100%; unresolved topology and unknown high-impact symbols produce zero critical issues; held-out projects are reported separately.
- Overmerge is more dangerous than split. The existing ASSERTED-only/no-POSSIBLE-union policy is therefore the correct default, even if initial network recall is lower.
- Page handling must move from exclusive extractors to capability combinations (`WireTopology`, `SymbolPorts`, `TerminalGrid`, `TableMapping`, `CrossPageReference`, `CommunicationMedium`, `MetadataOnly`). Backplates must not remain LayoutOnly, communication networks require a medium, and table grid lines must not become electrical edges.
- Recommended dependencies include Shapely STRtree, NetworkX, optional OR-Tools, schema validation/YAML, and SVG diagnostics. Learning dependencies remain optional and are gated after deterministic migration milestones.
- The package's rollout example eventually makes topology V2 primary, but current repository config correctly remains legacy-primary until the documented gates and engine-comparison evidence are complete.

## Current code audit: first migration slice

- `src/dwg_audit/ingest/dwg_converter.py` still performs backend discovery directly and only checks a configured file plus two hard-coded Windows paths. It does not use `shutil.which`, Linux/AppImage discovery, capability probes, or a Reader abstraction.
- The default config itself hard-codes ODA 27.1, so an absent machine-specific default is indistinguishable from an intentional user override unless the detection API records provenance.
- Conversion status already preserves `missing_converter` and does not crash, but a formal project-level incomplete-extraction audit gate still needs separate verification.
- Core geometry dependencies (`networkx`, `shapely`, pandas/pyarrow, PyYAML, ezdxf) are already installed; OR-Tools and schema validation are not core dependencies, which is consistent with deferring constraint work.
- The package includes executable migration aids, schemas, configs, benchmark split proposal, pseudocode, and corpus scripts in addition to docs. These should be selectively imported or adapted, not treated as already integrated code.
- Recommended first implementation slice: introduce a small backend-neutral Reader probe/registry contract and route current ODA discovery through it, preserving `convert_source_files()` behavior and config compatibility while adding cross-platform executable discovery plus tests. This unlocks corpus baselining without touching recognition output.

## Package checklist alignment

- `MIGRATION_CHECKLIST.md` confirms Reader Adapter is the next incomplete foundation and expands it beyond path discovery: protocol, DXF reader, adapter stubs, preview, capabilities/probe, backend provenance, cache key, and failure taxonomy.
- The implementation should begin with a deliberately narrow contract (probe + registry + ODA backend) and leave explicit extension seams, rather than attempting all Reader checklist items in one change.
- `MASTER_TASKBOOK.md` confirms stable sheet identity must include order/file identity, current Page routing risks, and the same M0/M1 ordering. Its content substantially duplicates the detailed docs; no contradictory architecture requirement was found.
- The installed ezdxf API differs from the initially guessed public helper name: `odafc.get_odafc_path` does not exist; its helper is private (`_get_odafc_path`). Implementation should not couple the project registry to a private ezdxf function.

## ODA integration detail

- Installed ezdxf resolves ODA with `shutil.which("ODAFileConverter")`, then platform config (`odafc-addon.win_exec_path` on Windows or `unix_exec_path` on Linux/macOS). A configured Linux AppImage may have an arbitrary filename, so prepending only its parent to `PATH` is not sufficient.
- The adapter should set the appropriate ezdxf option for the duration of conversion and restore it afterward. This keeps explicit executable paths working on both Windows and Unix without calling ezdxf's private resolver.
- Adding Reader provenance fields directly to `SourceFileRecord` would change manifest/Parquet hashes and violate the first slice's zero-output-drift goal. Probe/provenance should initially be exposed through the new Reader contract; findings persistence can be a separately baselined additive change.

## First migration slice implemented

- Added a backend-neutral Reader contract and registry plus an ODA adapter/probe.
- ODA discovery now supports explicit config, `ODAFC_PATH` / `ODA_FILE_CONVERTER`, system `PATH`, and versioned Windows install directories.
- Explicit executable paths are applied through both `PATH` and ezdxf's platform-specific ODA option for the conversion scope, then restored.
- Existing converter function shape, `_detect_odafc_exe`, `odafc.convert` monkeypatch surface, conversion statuses, and findings fields remain unchanged.
- Targeted Reader/config tests pass: `9 passed`.
- Full suite passes with the compatibility surface intact: `348 passed in 17.83s` (previous recorded Phase 105 suite: `342 passed`).
- `git diff --check` passes; only Git line-ending conversion warnings were emitted. No recognition configuration, manifest schema, or findings artifact schema changed in this slice.
- Current-machine probe succeeds against `C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe` via the configured path, so the new registry is ready for a real corpus run.
- The review package inventory stores its original corpus path under `/mnt/data/xj_dataset/...`, but the full local Windows corpus was discovered under `F:\workspace\XJToolkit\test`.
- One-project corpus smoke completed successfully in 30.8s: 28 sheets, 0 conversion failures, analyze/audit exit code 0, `pairs=1717`, `issues=70`, `junctions=23148`, `networks=609`.
- Those counts exactly match the previously frozen Phase 104 first-project baseline, providing real-run evidence that the Reader refactor caused zero recognition drift.
- Smoke artifacts are retained under `.tmp/phase110_reader_corpus_smoke/`, including aggregate/run summaries and the self-contained project findings/audit output.

## 2026-07-10 Taskbook migration planning

- `doc/任务书.md` already contains Phase 104-era section 18.8 with the five-layer topology-first architecture, four-state decisions, legacy boundary, staged A-F migration, metrics, Agent loop, and GNN gates.
- The latest review package adds authoritative detail not yet fully represented in 18.8: Reader Adapter and incomplete-extraction prerequisites; Primitive Model before formal network promotion; Findings V2 schema/version/cache policy; multi-label page capabilities; structured failure queue; explicit M0-M8 milestones; and hard release gates.
- The taskbook should therefore receive an additive section 18.9 that supersedes only the execution ordering/details of 18.8, while retaining 18.8's architectural decisions and existing redline contracts.
- `task_plan.md` should stop treating Phase 104-109 as a flat forward sequence. It needs a dependency-correct Phase 111+ execution queue: corpus baseline -> Reader completeness/provenance -> Primitive Model -> formal Geometry/Network -> Symbol-Port -> Page Capabilities -> Semantics/Constraint -> ProjectGraph/AuditV2 -> Review Loop -> Learning gate.
- Requested `gpt-5.6-luna` execution dispatch cannot be performed by the available collaboration API because it exposes neither a model selector nor the mandatory `agent_role="default"` parameter required by the repository `AGENTS.md`.

## Canonical migration plan applied

- `doc/任务书.md` version is now v1.0 topology-migration baseline and includes section 18.9 as the authoritative execution contract.
- The plan preserves 18.8 architecture/redlines but corrects ordering so Reader completeness and Primitive provenance precede formal Geometry/Network promotion.
- It adds M0-M9 milestones, Findings V2 version/cache semantics, page capability matrix, failure/review loop, hard promotion gates, Agent orchestration constraints, and Batches 111-120.
- `task_plan.md` now contains detailed Phase 112-120 inputs, tasks, exit gates and a separately gated learning track.
- Section 20 was also updated so the final MVP definition no longer ends on the old exclusive-extractor/Pair truth model; it now requires Reader completeness, Primitive/Geometry/Network/Symbol/Semantic/ProjectGraph truth, witness completeness, review routing and legacy rollback.
- A concrete three-lane 5.6 Luna concurrency pack is recorded under Phase 112. It remains undispatched because the live spawn schema cannot express either the requested model or mandatory default role.

## 2026-07-11 Phase 112 dispatch restart

- No workspace `AGENTS.md` is currently present under `F:\workspace\XJToolkit` or `F:\workspace`; the prior role-parameter restriction is therefore no longer discoverable from the updated workspace instructions.
- The user explicitly authorized subagent scheduling. The live collaboration API still does not expose a model selector, so model identity cannot be programmatically guaranteed or asserted; tasks are dispatched through the available subagent runtime.
- Phase 112 is now in progress with three independent read-only lanes: corpus-runner preflight, Reader provenance insertion design, and incomplete-extraction gate/test design. Production edits remain in the main thread.

## Phase 112 parallel audit results

- Corpus discovery was independently verified at 27 project roots and 502 direct DWG files.
- The corpus runner cannot be trusted by exit code alone: its final return currently gates analyze success but not audit failure or conversion failures. Phase 112 must explicitly assert 27 analyze successes, 27 audit successes, zero unexplained conversion failures, 502 sheets, 27 run records, valid manifests, and no TIMEOUT logs.
- The first full run must use a brand-new output directory without `--resume`, `--limit`, `--only`, or `--skip-audit`. Existing resume markers do not bind source/config/Git/backend identity.
- Runner summary does not freeze coverage/topology-shadow. After corpus success, every project needs `freeze-baseline` or equivalent baseline-manifest inventory/redline verification.
- Reader provenance should be an additive side artifact (`reader_run.json`) rather than new `Manifest`/`SourceFileRecord` fields in the first slice, preserving existing manifest and Parquet hashes.
- Reader cache identity must canonically include source SHA, backend/version/build digest, contract version and normalized options; exclude paths/status/duration. The new key remains shadow-only until the 27-project zero-drift proof is complete.
- The false-clean path is real: missing converter/read failures/empty geometry can allow a successful pipeline with zero Pair/Issue, and `missing_converter` is not counted by current `failed_pages` logic.
- Incomplete extraction must be evaluated in the pipeline using pre-extraction audit scope, persisted as machine state, and consumed fail-closed by rerun/audit. It cannot be a report-only condition.
- Initial hard failure taxonomy: `READER_UNAVAILABLE`, `INVALID_SOURCE_HEADER`, `CONVERSION_FAILED`, `DXF_READ_FAILED`, `ZERO_PRIMITIVES`, `AUDIT_EXTRACTOR_NOT_EXECUTED`, `REQUIRED_ARTIFACT_MISSING/CORRUPT`.
- Gate acceptance: incomplete detection recall 100% on failure injections, false positives 0% on sparse/skip/healthy fixtures, `false_clean=0`, and healthy legacy Pair/Issue/topology counts unchanged.

## Phase 112 full corpus run

- A clean full-corpus run completed in 403.1 seconds under `.tmp/phase112_corpus_baseline_e8be15d` without resume/filter/skip-audit.
- Aggregate result: 27 projects, 502 sheets, 27 analyze successes, 27 audit successes, zero conversion-failure projects, 29,801 pairs, and 1,290 issues.
- Project 1 reproduced the frozen first-set metrics (`1717/70/23148/609`), project 2 reproduced the held-out remote-cabinet probe (`527 pairs/17 issues`), and project 27 reproduced the second-set metrics (`1617/6/18929/358`).
- Fresh conversion status is `converted + skipped` rather than cached for the reported projects, confirming this is a clean-run corpus baseline rather than reuse of the Phase 110 cache.
- Runner exit code was 0, but Phase 112 is not yet closed: independent hard validation, per-project baseline manifests/redlines, and split freeze remain.
- Independent corpus hard gate passed: 27 unique roots, sequential indices 1-27, 502 sheets, source/file counts aligned, all analyze/audit exit codes zero, conversion failures zero, valid manifests, status counts closed, 81 logs and no TIMEOUT marker.
- Generated 27 per-project `baseline_manifest.json` files under `.tmp/phase112_corpus_baseline_e8be15d/baselines/P001..P027`, freezing artifact SHA/Parquet rows, coverage, legacy topology, topology shadow, geometry shadow, config and dirty-worktree fingerprint.
- The first manifest validator used an outdated `git` key assumption. Current schema stores repository state under `worktree`; redline structure itself is present and all P001 values inspected are true.
- Final baseline validation passed for all 27 manifests: every redline is true; all share HEAD `e8be15d17740249dafdef8782552d58c3fc64996`, one config hash and one dirty diff fingerprint; frozen totals are 29,801 pairs, 1,290 issues, 558,079 legacy junctions and 13,070 legacy networks.
- The review proposal contains 27 rows/502 DWG with split distribution 2 calibration, 12 training candidates, 5 validation and 8 held-out. Its absolute Linux paths must not be used as identity; the repository copy will lock `Pxxx + project_name + dwg_count` and omit absolute source paths.
- Added `tests/fixtures/benchmark_split_v1.csv` and companion policy document. The split is project-level, path-independent, source-hash traceable, and explicitly invalidates held-out status if results influence development.
- Split gate passed against the clean-run summary: all P001-P027 names/counts align, total DWG=502 and distribution is exactly 2/12/5/8.
- Phase 112 exit gate is complete. Phase 113 begins with the additive Reader provenance/cache identity slice recommended by the parallel audit; incomplete-extraction gate follows as a separate implementation slice to keep review and regression scope controlled.

## Phase 113 Reader provenance implementation decision

- Keep `SourceFileRecord`, `Manifest`, existing Parquet columns and legacy cache lookup unchanged in this slice.
- Add dedicated provenance objects owned by the Reader layer: canonical cache identity, per-source ReaderRun, and a project envelope.
- `convert_source_files()` will preserve its arguments and legacy monkeypatch surface while returning `list[ReaderRun]`; ignored return values remain compatible.
- `pipeline.analyze_input_root()` transports reader runs through `ProjectArtifacts.reader_runs`; `write_project_artifacts()` writes additive root-level `reader_run.json`.
- Cache identity records source SHA, backend, inferred version, executable digest/build ID, contract version and normalized conversion options. It is shadow-only: the legacy cache path remains authoritative until a separate post-baseline promotion.
- `baseline._artifact_inventory()` will include `reader_run.json` when present but `_require_bundle()` will not require it, preserving old bundle readability.
- Tests must prove canonical key stability/sensitivity, missing-reader status, skipped/invalid status, additive artifact writing, baseline optional inventory and unchanged legacy schemas/counts.

## Phase 113 concurrent implementation review

- Three coding subagents completed disjoint files: converter/run production, pipeline/artifact transport, and baseline/cache-identity tests.
- The integrated diff follows the chosen contract: all conversion terminal states emit ReaderRun; pipeline tolerates legacy `None`; root `reader_run.json` is additive; baseline inventory is optional; old manifest/source-files/findings schemas are explicitly tested unchanged.
- Cache identity includes stable inputs only and explicitly excludes discovery/status/document path. It remains `cache_identity_enforced=false`.
- Main-thread review found no file overlap or schema contamination. Full validation is still required before accepting the slice.
- Main-thread targeted suite passed: 48 tests across Reader, converter, artifacts, baseline and config.
- Full suite passed: 367 tests in 9.16s (up from 348 before provenance additions).
- Fresh calibration-project run produced 28 ReaderRun records (`24 converted / 4 skipped`), backend version `27.1.0`, one executable build digest and shadow cache keys for every file.
- The fresh run retained `1717 pairs / 70 issues / 23148 junctions / 609 networks`; pairs, issues, legacy junctions/networks and geometry shadow nodes/edges are frame-equal to the Phase 112 baseline.
- `reader_run.json` is present while legacy `manifest.json` contains no reader-run fields, proving the additive boundary.

## Phase 113 incomplete-extraction concurrent implementation

- Gate Core now evaluates expected-audit pages from pre-extraction audit role plus audit disposition, short-circuits reader/conversion failures, maps read warnings, detects zero primitives/extractor non-execution, exempts stable skips, and never uses pair count.
- Pipeline now persists `extraction_completeness.json`, exposes project status in run summary/events/findings, and adds per-page extraction status/failure codes.
- Rerun audit now appends Pair-independent `R-DATA-INCOMPLETE-EXTRACTION` review Issues with stable `DQE####` IDs; legacy bundles without the sidecar remain compatible and corrupt JSON fails closed.
- Main-thread review identified one cross-lane serialization hazard: a fallback data-quality Issue can contain an empty `audit_scope` struct, which PyArrow cannot persist. This needs a non-empty sentinel or null normalization before the full suite.
- Baseline optional inventory currently includes `reader_run.json` but not yet the new root `extraction_completeness.json`; both additive sidecars should be frozen when present.
- Main thread normalized fallback audit scope to a non-empty project/page sentinel and added optional baseline inventory for `extraction_completeness.json`.
- Combined Gate/Reader/Artifact/Baseline/Data Quality targeted suite passed: 61 tests.
- Full suite passed: 383 tests in 7.62s.
- Fresh healthy calibration run is `COMPLETE`, allows clean conclusion, has zero incomplete pages/failure codes and produces no data-quality Issue.
- The run retained `1717 pairs / 70 issues`; six legacy/topology frames remain exactly equal to the Phase 112 corpus baseline while both Reader and extraction sidecars are present.
- End-to-end failure injection now proves an invalid audit-required DWG produces zero Pair but still writes one `R-DATA-INCOMPLETE-EXTRACTION` review Issue; false-clean is prevented at analyze and rerun layers.
- Final suite after the end-to-end assertion remains 383 passed; `git diff --check` passes.
- Phase 113 remains in progress only for the next Reader slice: explicit ODA health check and an independent DXF reader adapter. Provenance, taxonomy, incomplete gate, data-quality audit and zero-drift verification are complete.

## Phase 113 health/DXF adapter audit

- Current Registry registers only `odafc`; `CadReader` has no health method and `ReaderProbe` has no health state/detail beyond availability.
- CAD extraction still opens converted DXF directly inside `extract_cad_artifacts`, so an independent `EzdxfReader` can be added without changing ODA conversion semantics, then adopted in a separate integration step.
- ODA File Converter is a GUI-oriented executable: invoking `--help` did not terminate within the bounded shell window. Health checks must not depend on an unbounded help/version subprocess.
- Safe ODA health should combine executable existence/readability, file-version/build metadata where available, and a bounded synthetic DWG/DXF conversion with ezdxf readback; timeout/failure must produce explicit health codes.
- Selected next contract: add structured `ReaderHealth` to the Reader layer, implement an independent `EzdxfReader`, register both `odafc` and `ezdxf`, and integrate DXF extraction only after adapter tests stabilize.
- ODA metadata on this machine reports FileVersion/ProductVersion `27.1.0.0`. Health must retain actual version/build evidence instead of relying only on the install-directory name.
- Parallel work is split to avoid conflicts: base/Ezdxf/Registry, ODA health implementation, and read-only CAD-extraction integration audit. Main thread will own the final extraction switch.

## Phase 113 Reader implementation review

- `ReaderHealthStatus` and structured `ReaderHealth` are now implemented; `CadDocument` can carry the native parsed document.
- `EzdxfReader` is registered alongside ODA, reports ezdxf package health/capabilities, validates `.dxf`, and raises stable ReaderError codes.
- ODA health reads Windows VERSIONINFO without launching the GUI, hashes the executable build, and supports an explicitly requested bounded smoke callable with stable timeout/failure codes.
- Main-thread integration decision: switch only `extract_cad_artifacts` to EzdxfReader in this slice. Preserve entity iteration and all IDs/order; map ReaderError back to existing `missing_dxf/read_dxf_failed` warnings so the extraction gate remains authoritative.
- Converter cache validation/readback remains a separate next knife because its current `OSError`-only handling is a real but behavior-changing cache/status fix.
- To make ODA health operational rather than test-only, converter provenance should consume `health_check()` metadata and persist health status/checks/error alongside ReaderRun. Explicit smoke remains opt-in.
- Main thread integrated Reader health into every ReaderRun, including actual VERSIONINFO version/build evidence and health checks; cache identity now uses health metadata when available.
- Main thread switched CAD extraction to EzdxfReader while preserving the same native ezdxf Drawing, modelspace iteration and entity/ID order. Reader errors map to `missing_dxf/read_dxf_failed` so the existing gate cannot be bypassed.
- Added a real opt-in ODA smoke implementation using temporary DXF-to-DXF conversion plus ezdxf readback. On this machine metadata and smoke both report READY, version `27.1.0.0`, build digest `5889d643...`, and smoke=true.
- Reader/ODA/converter/CAD/gate targeted verification passed: 56 tests.
- Latest full suite passed: 401 tests in 9.18s.
- Fresh calibration P001 and validation P003 runs are both `COMPLETE` and clean-eligible. Each is frame-equal to its Phase 112 baseline across all 16 legacy/topology/geometry/audit artifacts.
- P001 retained `1717 pairs / 70 issues / 23148 junctions / 609 networks`; P003 retained `413 pairs / 3 issues / 28163 junctions / 1230 networks`.
- Every real-run ReaderRun reports health `READY`, backend version `27.1.0.0`, the same executable build digest, and `cache_identity_enforced=false`.
- Phase 113 has one deliberately isolated closure item: replace converter cache/fresh-output validation's `OSError`-only direct read with the independent DXF Reader contract and prove corrupt-cache recovery plus invalid-output failure semantics.
- That closure is now complete. Converter validation uses EzdxfReader for both cache hits and fresh ODA outputs; corrupt cache reconverts, while invalid fresh output records `DXF_VALIDATION_FAILED` and never publishes a document path.
- Closure tests passed: targeted 48 and full 403. A fresh P001 real run converted all 24 auditable DWGs, passed audit, and preserved 20/23 common Parquet frames byte-semantically; the remaining three differ only by runtime path/duration or nested-object representation, with Issue evidence and bridged-gap values string-normalized equal.
- Phase 113's exit gate is satisfied and Phase 114 is now the active phase.

## Phase 114 primitive-model entry audit

- Legacy CAD extraction mixes normalization with recognition and only persists TEXT/LINE/block insertion/polyline summaries. LWPOLYLINE/POLYLINE are flattened into legacy lines; ARC/CIRCLE are absent, and INSERT expansion is optional recognition behavior rather than a versioned primitive contract.
- The native ezdxf document exists only inside `extract_cad_artifacts`; artifact writing is too late to recover ARC/CIRCLE, definition paths, nested transforms or reader provenance. Primitive normalization therefore belongs beside extraction, before legacy line grouping, but its output must remain a separate shadow collection.
- Preserve the six-value public unpacking contract by returning a result envelope that iterates over the legacy six collections while exposing `primitive_segments` additively. Pipeline can consume the additive field without changing existing tests/callers.
- First owning-layer design: a dedicated primitive normalizer traverses modelspace and nested INSERT virtual entities, emits versioned deterministic records with entity/parent handles, definition/nested path, layout/layer/linetype, local/world geometry, transform decomposition, bbox and reader provenance. Unknown entities are retained as explicit unsupported records rather than deleted.
- `primitive_segments.parquet` will be shadow-only and optional for old bundles/baselines; no legacy Pair, Issue, wire topology or geometry-shadow consumer may read it in Phase 114.
- Implemented `primitive-segment-v1` plus `primitive-summary-v1`. Polyline pieces retain the original LWPOLYLINE/POLYLINE handle/type rather than virtual LINE handles; transformed world pieces remain LINE/ARC primitives.
- Synthetic coverage proves LINE, both polyline families, ARC, CIRCLE, nested INSERT and ATTRIB, including nested path, parent handle, rotation, mirror and non-uniform scale world coordinates. Unknown POINT is retained with `unsupported_retained` and is not connected.
- P001 produces 29,666 primitive rows, including 10,694 LWPOLYLINE-derived records, 10,194 LINE, 966 ARC, 539 CIRCLE, 1,144 INSERT and 24 ATTRIB; all polyline-derived records retain non-virtual source handles, 20,347 rows have nested paths, and all rows carry ezdxf Reader provenance.
- Real P001 legacy comparison remains 20 exact frames, two nested-representation-only frames, and one expected runtime source-path/duration frame. No Pair/Issue/topology semantic drift was observed.
- Remaining Phase 114 risk: non-uniformly transformed circle/arc may become ELLIPSE and currently remains unsupported; block transform needs explicit ellipse/local-world fixtures and a stable approximation/analytic policy before its checkbox or exit gate can close.
- Closed that risk by analytically persisting ELLIPSE center/major-axis/ratio/parameter bounds and attaching each nested primitive's ancestor transform chain including Matrix44. The synthetic nested mirror/non-uniform fixture now proves CIRCLE -> ELLIPSE while retaining the source CIRCLE handle/type.
- Layer role is deliberately `UNKNOWN` with reason `LAYER_ROLE_UNCLASSIFIED`; it is evidence only and cannot filter or connect primitives. Unsupported TEXT/MTEXT/HATCH records remain visible in the summary instead of disappearing.
- Healthy validation P003 produced 17,794 primitives. All 14,816 normalized rows have non-virtual source handles, non-empty world geometry, bbox and Reader provenance. P001 has the same completeness property for all 23,633 normalized rows.
- Formal P003 `compare-regression` report shows Pair 413 -> 413, Issue 3 -> 3, texts/lines/line-groups and every status/rule count delta zero. Together with the prior 20 exact + 2 representation-only frame comparison, this satisfies Phase 114 real-page zero-drift evidence.
- Phase 114 is complete. Phase 115 must consume only the primitive shadow plus existing Phase 105 observations into append-only four-state decisions; it must not union POSSIBLE/UNKNOWN/REJECTED.

## Phase 115 topology-decision entry audit

- Phase 105 already emits four-state geometry observations for asserted junctions, possible/unknown endpoint gaps and rejected crossings, with stable observation IDs, source/evidence line IDs and reason codes. It is the correct seed input for an append-only decision layer.
- Geometry graph component union currently consumes only actual split edges; endpoint gaps remain observations and are not unioned there. This boundary can be preserved by building decisions after geometry observations.
- Legacy `wire_topology.py` is unsafe as a V2 network source: it unions endpoint/T-cross connections, optional raw crossings, and inline-text/block spans. In particular inline text and block spans are directly unioned. Phase 115/116 must not reuse this union path for V2.
- First Phase 115 slice should produce `junction_observations_v2.parquet` as a lossless versioned projection and `topology_decisions.parquet` with decision/evidence/reason/provenance fields. A separate invariant verifier must prove `union_eligible == (decision_state == ASSERTED)` and count every non-ASSERTED union attempt as a hard contract violation.
- Decision promotion in this first slice is identity-preserving: existing Phase 105 ASSERTED remains ASSERTED; POSSIBLE/UNKNOWN/REJECTED remain unchanged. No score threshold or file/page-specific heuristic is introduced.
- Implemented `junction-observation-v2`, `topology-decision-v2` and a summary artifact. IDs are deterministic UUID5 projections; every decision stores reason codes, alternatives, score decomposition, evidence/source lines and review state.
- The invariant is mechanical: only ASSERTED may be `union_eligible`; Phase 115 sets `union_applied=false` for every row. Synthetic mutation proves the verifier catches a non-ASSERTED union attempt.
- Initial P001 projection: 8,583 decisions (`6372 ASSERTED / 362 POSSIBLE / 1339 REJECTED / 510 UNKNOWN`). Initial P003: 4,195 (`3443 / 78 / 295 / 379`). Both have unique stable IDs, complete reason traces and zero non-ASSERTED union violations.
- Added spatially bucketed collinear-overlap observation. It records ASSERTED geometric overlap but does not alter components or apply union. P003 now has 771 explicit overlap decisions and still zero union applications/violations; cached end-to-end runtime remains bounded at 7.75s.
- Formal Phase 115 P001 and P003 regression reports both show Pair delta 0 and Issue delta 0.
- Phase 115 remains open for inline text/block POSSIBLE evidence and an independently reviewed real-page junction/crossing ground-truth subset. The 771 validation overlaps are evidence volume, not yet a precision claim.
- Added inline text/block span observations as separate POSSIBLE decisions. They never promote the base gap, never become union-eligible, and never call a union path. P003 has 456 such rows (`386 text`, `70 text+block`), all review-only.
- Frozen `topology_ground_truth_v1.csv` from validation P003 with 12 handle/coordinate-backed samples: four explicit marker intersections, four unmarked interior crossings and four exact endpoint merges. Matching uses sheet/kind/reason/sorted source handles, not Pair/Issue outcomes.
- Ground-truth evaluation matches 12/12, state accuracy 1.0, asserted precision 1.0, four asserted crossing samples and zero asserted-crossing false connects. This is a bounded validation subset, not a claim over the whole corpus.
- Final P001 has 11,257 decisions (`8174 ASSERTED / 1234 POSSIBLE / 1339 REJECTED / 510 UNKNOWN`); P003 has 5,422 (`4214 / 534 / 295 / 379`). Both have union_applied=0 and non-ASSERTED violations=0.
- Final formal regression reports for P001 and P003 both have Pair delta 0 and Issue delta 0. Phase 115 exit gate is accepted; Phase 116 must materialize new networks exclusively from union-eligible ASSERTED decisions and preserve possible boundaries separately.

## Phase 116 asserted-network first slice

- Implemented a separate ASSERTED-only component consumer. Decision applications are append-only: ASSERTED overlap between distinct same-sheet components may apply; already-materialized ASSERTED junctions are recorded but not re-unioned; every non-ASSERTED row is rejected with `NON_ASSERTED_NOT_APPLIED`.
- P003 builds 452 electrical networks from geometry components with 288 asserted component unions and zero non-ASSERTED applications. It persists 9,385 members, 1,049 open endpoints and 1,208 possible/unknown/rejected boundaries.
- All 4,025 P003 SOURCE_LINE members have original handles; all 1,049 open endpoints have coordinates and source handles.
- Endpoint witness uses shortest ASSERTED geometry paths. It first targets another open endpoint, then a junction/network node for single-open components. P003 is 1,049/1,049 resolved, every witness has a handle path and weakest evidence ASSERTED.
- Read-only validation emits suspicions without changing networks. P003 has zero split suspicion and 64 `NON_ASSERTED_BOUNDARY_INSIDE_NETWORK` overmerge suspicions. They are not yet proven errors; Phase 116 cannot close until these are classified or bounded against equivalence/ground truth.
- Root cause of all 64 suspicions was generic: overlap assertion reused the 0.05 endpoint snap tolerance, promoting lines offset by ~0.0036 as direct overlap. Introduced independent `geometry_graph_overlap_alignment_tolerance=1e-6` plus a near-collinear rejection fixture. P003 overlap decisions fell 771 -> 707, networks 452 -> 484, asserted applications 288 -> 224, and both overmerge/split suspicions became zero.
- Added boundary observations for every open endpoint: drawing edge can be ASSERTED, block proximity is only POSSIBLE symbol-boundary evidence, and cross-page interruption stays UNKNOWN with an explicit semantic-resolver deferral reason. No boundary classifier changes connectivity.
- Added legacy Pair -> V2 network equivalence. P001: 1062 unique / 167 multiple / 488 no-network; P003: 389 unique / 24 multiple. `v2_changes_legacy_result=false` for every Pair.
- Issue witness is generated during rerun audit. P001 has 42 ASSERTED network paths plus 28 explicitly weaker legacy table/text-handle fallbacks; P003 has 3 ASSERTED network paths. Both are 100% resolved and handle-traceable. The fallback does not pretend a V2 network exists.
- Final P001: 1,934 V2 networks, 3,082 open endpoints, 3,083 possible boundaries, non-ASSERTED applications 0, endpoint witness 3,082/3,082, suspicion 0. P003: 484 networks, 1,049 opens, 1,208 boundaries, witness 1,049/1,049, suspicion 0.
- Full suite passes 418 tests; P001/P003 formal regression remains Pair/Issue delta zero. Phase 116 exit gate is accepted and Phase 117 begins with corpus block-definition frequency/fingerprint audit.

## Phase 117 symbol-registry entry audit

- Primitive v1 now has enough stable inputs for project-level definition fingerprints: INSERT definition name/transform plus child local geometry, entity kind, layer, linetype and ATTRIB/ATTDEF/TEXT slot records. Fingerprints must exclude instance handle, nested path and world coordinates.
- Existing symbol behavior is still dispersed across regex/constants in `component_diagrams.py`, `wire_components.py`, `wire_topology.py`, candidates/rules and diagnostics. The first migration target is `_INLINE_COMPONENT_BODY_FAMILIES={KLP,ZKK}`, but behavior must remain config-backed and zero-drift before removing the constant.
- Phase 117 should first write per-project `symbol_definitions_v1`, `symbol_instances_v1` and `unknown_symbol_queue_v1`; a corpus aggregator can then rank Top-50 by instance frequency × project coverage × audit impact proxy without touching held-out labels.
- Unknown definitions remain UNKNOWN/review-only. Project-level inventory must not infer electrical ports or internal connectivity merely from a block name.

## Phase 117 first inventory slice

- Project inventory builder lives in `src/dwg_audit/audit/symbol_registry.py`:
  - `definition_fingerprint_from_children` hashes only child `source_entity_type|primitive_kind|layer|linetype|local_geometry_json` (sorted set).
  - Fingerprint excludes instance handle, nested path, world geometry and instance transform translation.
  - `symbol_definition_id = SD1-{sha256(name + " " + fingerprint)[:32]}` so empty-geometry name collisions cannot share IDs while geometry families still share fingerprints.
  - Every definition starts `registry_status=UNKNOWN`, `symbol_family=None`, `internal_connectivity_state=UNKNOWN`, `declared_port_count=0`, `critical_issue_eligible=False`.
  - `rank_symbol_annotation_backlog` ranks geometry families by `total_instance_count * project_coverage` without held-out labels.
- Write path (derive-at-write, same as topology/electrical): `write_project_artifacts` builds four findings files from the primitive frame; no `ProjectArtifacts` symbol fields and no Pair/Issue consumers.
- Baseline: findings `rglob` already inventories symbol files when present; optional non-gating `metrics.symbol_inventory` is populated from `symbol_inventory_summary.json` when present, else `{}`. No mandatory symbol redlines.
- Real evidence offline from phase116 primitives (no held-out):
  - P001: 67 definitions, 1144 instances, 67 unknown, critical eligible 0.
  - P003: 33 definitions, 475 instances, 33 unknown, critical eligible 0.
  - Provisional two-project backlog: 79 geometry families; top family `SYMB2_M_PWF165` (333 instances, coverage 2, score 666). Rank-2 merges names `SYMB2_M_PWF231`/`SYMB2_M_PWF248` under one fingerprint (255 / coverage 2).
- Hardcoded family migration (`_INLINE_COMPONENT_BODY_FAMILIES={KLP,ZKK}` etc.) is deliberately deferred until config-backed zero-drift fixtures exist.
- Artifacts retained under `.tmp/phase117_symbol_inventory_p001|p003/` and `.tmp/phase117_symbol_backlog_p001_p003/`.
- Remaining for Phase 117 exit: full non-held-out corpus inventory, Top-50 annotation backlog with human port fixtures for Top N, and first zero-drift family YAML migration.

## Phase 117 write-path and non-held-out corpus inventory

- Fresh `analyze-project` write-path on calibration P001 and validation P003 produced symbol artifacts under `.tmp/phase117_symbol_writepath_{p001|p003}/`.
  - P001: 67 definitions / 1144 instances / unknown critical eligible 0; pairs 1717.
  - P003: 33 definitions / 475 instances / unknown critical eligible 0; pairs 413.
- Formal `compare-regression` vs phase116: pair_count delta 0, issue_count delta 0, texts/lines non-regression ok on both projects. Issues: P001 70, P003 3.
- Non-held-out corpus analyze (19 projects; held-out excluded by `benchmark_split_v1`): all 19 succeeded in ~269s under `.tmp/phase117_corpus_non_heldout/`.
  - Aggregate definition rows 847, instance rows 15,759, geometry families 165.
  - Every project summary has `unknown_critical_issue_eligible_count=0` and `registered_definition_count=0`.
- Top-50 annotation backlog written to `.tmp/phase117_symbol_backlog_non_heldout/`:
  - Rank1 `SYMB2_M_PWF165` 4220×18 = 75960
  - Rank2 shared fingerprint for `SYMB2_M_PWF231`/`SYMB2_M_PWF248` 2975×18 = 53550
  - Rank6 title block `Title_xjdw-yw` covers all 19 projects (306 instances)
  - Rank20 `KK2P` 77×18 (multi-port name feature only; ports still undeclared)
- No held-out project was analyzed for ranking. No family YAML migration yet. Port fixtures remain human-pending.

## Phase 117 Top-N fixtures and port scaffold

- Definition fixtures: `tests/fixtures/symbol_definition_fixtures_v1.json` + policy md.
  - Families: Top-5 geometry families from non-held-out corpus plus KK2P name example (6 total).
  - All fingerprints recompute from stored child signatures; no truncation (PWF165 11, shared PWF231/248 8, PWF191 22, PWF194 7, PWF243 11, KK2P 21).
  - `declared_port_count=0`, `critical_issue_eligible=false`, held-out excluded.
- Port fixtures: `tests/fixtures/symbol_port_fixtures_v1.json` pre-seeds Top-10 + KK2P with empty `ports`, `annotation_status=PENDING_HUMAN_REVIEW`.
- Unit coverage: definition fixtures + port fixtures + registry = 16 targeted; full suite 437 passed after fixtures.
- Symbol-aware baselines frozen: `.tmp/phase117_baseline_p001|p003/baseline_manifest.json` include four symbol files and non-gating `metrics.symbol_inventory` (P001 67/1144, P003 33/475, critical 0).
- Remaining exit item: config-backed zero-drift migration of `_INLINE_COMPONENT_BODY_FAMILIES={KLP,ZKK}` then human port annotation for Top N (ports stay empty until review).

## Phase 117 exit: family config zero-drift and acceptance

- Migrated `_INLINE_COMPONENT_BODY_FAMILIES` to config key `wire_components.inline_body_families: [KLP, ZKK]` in `DEFAULT_CONFIG` and `configs/default.yml`.
- `wire_components.py` resolves families from config with frozenset default fallback; pattern built from sorted escaped alternation; `page_extractors` passes config.
- Zero-drift proof after migration:
  - Full suite 443 passed.
  - Fresh P001/P003 analyze+audit vs pre-migration symbol write-path: pair_count delta 0, issue_count delta 0, pair key frames equal.
  - P001 inline_klp evidence 20 and inline_body 30 unchanged; P003 remains 0/0.
- Phase 117 products complete enough for exit:
  1. Project inventory + unknown queue + fingerprint (path-independent)
  2. 19 non-held-out corpus Top-50 backlog
  3. Top-N definition fixtures + port-fixture schema scaffold (ports empty / PENDING_HUMAN_REVIEW)
  4. First hard-coded family migration with zero-drift
  5. Unknown symbols never critical-eligible alone
- Explicitly deferred beyond Phase 117: human port coordinate annotation, electrical internal connectivity, held-out evaluation, broader family YAML beyond KLP/ZKK, and page multi-label capabilities (Phase 118).

## Phase 118 entry audit

- The current page model exposes one legacy `route_target`; it must remain the primary execution route during the first Phase 118 slice.  Multi-label capabilities are additive audit metadata, not a routing change.
- The stable labels are `WireTopology`, `SymbolPorts`, `TerminalGrid`, `TableMapping`, `CrossPageReference`, `CommunicationMedium`, and `MetadataOnly`.  They need sorted/deduplicated output plus evidence and confidence.
- Backplate and table pages cannot be safely re-routed yet: report generation currently still supplies raw line primitives to geometry/wire builders.  The next slice therefore records capabilities only; Phase 118's follow-up TableStructure profile will remove only validated grid structural line IDs from topology inputs.
- Communication-media detection is shadow-only.  It must require at least two local, non-title-block content cues, write a candidate/review artifact, and never change electrical connectivity.
- External Phase 117 changes were independently checked with `python -m pytest -q`: 443 passed.

## Phase 118 table-structure slice

- `table_structure_profiles` accepts only geometry-complete rectangular grids (at least 2x2 cells), with row/column axes, header scope, structural line IDs, evidence and confidence. It does not use filename, page number or layer; raw lines/primitives remain persisted.
- A complete grid alone is deliberately insufficient for topology filtering because ordinary circuit pages can contain grids. A second independent page-capability guard is required: `TableMapping` or `TerminalGrid`.
- Only those verified structural IDs are removed from V2 `geometry_shadow` and `wire_topology` inputs. Legacy Pair/Issue consumers and raw line artifacts are untouched. A synthetic 3x3 grid removes structural lines while retaining a short non-grid lead.
- Fresh non-held-out real proof:
  - P001 has profiles S0026 (45 cells) and S0028 (90 cells); 134 verified structural IDs are excluded. Their intersection with geometry edges and wire-network members is zero. V2 geometry edges reduce 10,585 -> 10,364 and networks change 1,934 -> 1,984 (expected splitting), while legacy Pair/Issue delta is 0/0.
  - P003 has no verified complete-grid profile. Its serial candidate on S0011 remains `candidate` only; V2 network and geometry-edge deltas are both zero.
- Full suite after integration: 452 passed in 15.21s.

## Phase 118 multi-label + TableStructure closure

- Another agent advanced Phase 118 while prior haiku dispatches failed on quota. Recovered state shows additive multi-label capabilities already live:
  - `PageClassification.capabilities` / `capability_evidence` / `communication_media`
  - `SheetRecord.capabilities` copied by page_router
  - findings `page_capability_matrix`, `communication_medium_candidates.parquet`
- TableStructure profile module (`audit/table_structure.py`) detects complete rectangular grids only (geometry-only; no filename/page patches). Writes `table_structure_profiles.parquet` with header_scope/cell_scope and structural_line_ids.
- Topology exclusion is dual-gated: verified complete grid **and** page capability in `{TableMapping, TerminalGrid}`. Wire-grid pages without those capabilities never exclude lines.
- Real evidence (fresh rerun under `.tmp/phase118_table_structure_rerun_{p001|p003}`):
  - P001: pairs 1717 (delta 0 vs phase117 family-config), issues delta 0; 2 table profiles on terminal pages S0026/S0028; **134 structural lines excluded** from V2 geometry/wire inputs; 0 excluded lines remain in geometry edges.
  - P001 V2 network counts moved 1934→1984 / legacy wire networks 609→623 because excluded terminal-grid lines no longer over-merge shadows; **legacy Pair/Issue unchanged**.
  - P003: pairs 413 / issues delta 0; 0 complete-grid profiles (no false exclusion); CommunicationMedium candidate=1 (serial, two-cue) on layout comm page; route unchanged.
- Backplate pages already emit hybrid shadow capabilities `SymbolPorts+TerminalGrid+TableMapping` while route stays TableExtractor (not pure LayoutOnly).
- Config now declares `table_structure.axis_tolerance/intersection_tolerance/min_axis_count` defaults.
- Full suite: 454 passed.
- Remaining non-blocking for Phase 118 exit: human review of medium candidates; optional later promotion of hybrid backplate route only after more corpus table-grid proofs. No held-out used.

## Phase 119 first slice: ProjectProfile + tokens + shadow attachments

- Pure builders:
  - `audit/project_profile.py` → `project-profile-v1` from existing scan/sidecars/strips/pages (no inventing).
  - `audit/token_parser.py` → specialized kinds SCOPED_PREFIX / WIRE_N_NUMBER / COMPONENT_BODY / COMPONENT_PORT / EXTERNAL_ENDPOINT / TERMINAL_LOCAL / DEVICE_TAG / PAGE_REFERENCE / ANNOTATION.
  - `audit/semantic_attachment.py` → geometry-only top-k line-endpoint candidates with SELECTED/REJECTED, margin, reason codes (`semantic-attachment-v1`).
- Write path emits `project_profile.json`, `text_tokens.parquet`, `semantic_attachment_candidates.parquet`, `semantic_attachment_summary.json` (shadow only; no Pair/Issue consumers).
- Real P001: tokens 5076 (TERMINAL_LOCAL 1111, COMPONENT_BODY 50, EXTERNAL_ENDPOINT 230, …); attachments 5670 with selected 1890 / rejected 3780 / low_margin 1431; profile sidecars prj+terminal_xml parsed, 28 pages / 27 strips.
- Real P003: tokens 2214; attachments 915 (selected 305); profile 13 pages / 6 strips.
- Formal compare vs Phase 118 rerun: pair/issue delta 0 on both; pair key frames equal.
- Full suite: 476 passed.
- Remaining for Phase 119 exit: ScopeResolver (semantic-row/body-port/scoped-prefix), optional global constraint/matching, strong-constraint inviolability metrics — still shadow/review-first.

## Phase 119 ScopeResolver + ConstraintResolver exit

- `scope_resolver.py` (`scope-resolver-v1`): SCOPED_PREFIX / BODY_PORT / SEMANTIC_ROW; priority BODY_PORT > SCOPED_PREFIX > SEMANTIC_ROW; states RESOLVED|AMBIGUOUS|UNSCOPED|CONFLICT. Geometry attachments remain non-authoritative for topology.
- `constraint_resolver.py` (`constraint-resolver-v1`): strong ONE_SELECTED_PER_TOKEN; weak/review LOW_MARGIN_REVIEW + SCOPE_AMBIGUITY_NOT_AUTHORITATIVE + CROSS_SCOPE_COMPETITION. Records only; `inviolable_strong_constraints=true`; never unions POSSIBLE/UNKNOWN/REJECTED; never mutates Pair/Issue.
- Write path emits `scope_decisions.parquet`, `scope_resolution_summary.json`, `constraint_decisions.parquet`, `constraint_resolution_summary.json`, and final scoped+constrained `semantic_attachment_candidates.parquet`.
- Real write-path evidence (`.tmp/phase119_scope_writepath_{p001|p003}`):
  - P001: scope resolved 1395 / ambiguous 279 / unscoped 3996; authoritative selected 402; review_only 1674; strong_violation 0; Pair/Issue delta 0 vs pre-scope Phase 119 (1717 pairs).
  - P003: scope resolved 276 / ambiguous 264; authoritative 38; review_only 443; strong_violation 0; Pair/Issue delta 0 (413 pairs).
- Full suite: 492 passed.
- Optional OR-Tools global matching deferred (not required for Phase 119 exit): weak competition already review-routed without solver.
- Phase 119 exit gate accepted: strong constraints inviolable (recorded, zero illegal application), weak/ambiguous → review, attachment top-k retained with authority demotion. Advancing to Phase 120.

## Phase 120 ProjectGraph / Audit V2 / promotion evidence

- Builders (shadow only):
  - `project_graph.py`: EndpointIdentity from ASSERTED open endpoints + AUTHORITATIVE attachments; cross-page candidates stay CANDIDATE; project graph redlines force `possible_union=false`.
  - `audit_v2.py`: issue clusters by (rule_id, sheet_id) with witness_status; legacy issue stream retained; engine comparison from pair↔network equivalence.
  - `failure_queue.py`: residual-risk routing to READER/PRIMITIVE/TOPOLOGY/TEXT_ATTACHMENT/CROSS_PAGE/ENDPOINT/CONSTRAINT/… without auto-critical from unknown attachments.
- Write path: analyze emits endpoint/cross-page/graph/engine artifacts; `rerun_audit_from_findings` emits audit_v2 clusters + failure queue (CLI run-audit path).
- Real P001: endpoints 3554 (auth 738 / geometry 2816), cross-page candidates 1221, networks 1984, audit clusters 18 / issues 70 / witness_completeness 1.0, failure critical 0, engine v2_changes_legacy=0, Pair/Issue delta 0 vs Phase 119.
- Real P003: endpoints 1087 (auth 65), cross-page 2, clusters 1 / issues 3 / witness 1.0, failure critical 0, engine delta 0, Pair/Issue delta 0.
- Extraction gate COMPLETE + clean_conclusion_allowed on both; constraint strong_violation 0 / inviolable true.
- Held-out projects (P002/P013–P016/P021/P025/P026) not used for tuning.
- Full suite: 517 passed.
- Promotion evidence: `.tmp/phase120_promotion_gate_evidence.json`.
- Product primary_engine remains legacy until explicit release decision; V2 shadow chain through ProjectGraph/AuditV2/FailureQueue is complete for Phase 120 exit.

## Held-out release evaluation (no tuning)

- Ran analyze+audit on all 8 held-out projects (P002/P013/P014/P015/P016/P021/P025/P026) under `.tmp/phase120_heldout_release/` **for release evaluation only**. No config/code changes were made based on held-out outcomes.
- Aggregate: 8/8 COMPLETE, false_clean=0, strong_violation=0, inviolable_strong_constraints=true, possible_union=false, engine v2_changes_legacy_result_count=0, unknown/unresolved critical=0, failure_queue critical=0.
- Witness completeness min/mean = 1.0 / 1.0 across held-out.
- Pair/Issue totals vs Phase 112 baseline: pair_delta=0, issue_delta=0 (exact compatibility on held-out).
- True hard-issue precision >=99% is **UNMEASURED** because the repository has no held-out human hard-issue label set. Proxy release gate passed under an explicit non-label definition (see `.tmp/phase120_promotion_gate_evidence_v2.json`).
- Therefore: Phases 113-120 + held-out release proxy are complete; **primary_engine remains legacy**; ready for review-only V2 assist, not automatic primary flip.

## Hard-issue precision measurement (cal/val frozen labels)

- Added `tests/fixtures/hard_issue_labels_calval_v1.json` freezing current-head hard-rule issues on P001/P003:
  - rules: `R-CROSS-PAGE-CONFLICT`, `R-DUPLICATE-PAIR`, `R-ONE-TO-MANY`, `R-MANY-TO-ONE`
  - P001: 65 labels; P003: 0 hard labels (only soft missing-side reviews)
- Added evaluator `report/hard_issue_eval.py` + CLI `evaluate-hard-issues` + unit tests.
- Measurement on Phase 120 writepaths: micro precision **1.0**, recall **1.0**, tp=65, fp=0, fn=0 (`precision_ge_99=true`).
- Explicitly **not** a human gold standard; held-out remains without human labels and was only used for structural release gates (already proxy-pass).
- Promotion evidence updated to v3: measurable hard precision on cal/val frozen labels + held-out structural pass; `primary_engine` still legacy pending product flip decision / human held-out labels.
