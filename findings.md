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
  - `symbol_definition_id = SD1-{sha256(name + "\0" + fingerprint)[:32]}` so empty-geometry name collisions cannot share IDs while geometry families still share fingerprints.
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
## Phase 121 Reproducible Promotion Gate Evidence

- Gap closed: after `.tmp` wipe, taskbook 18.9.9 loop deliverables (`metrics_by_project.csv`, `decision_log.md`, promotion evidence JSON) had no first-class recompute entrypoint.
- Implementation (architecture-correct, evaluation layer only):
  - `src/dwg_audit/report/promotion_gate.py`
  - CLI `evaluate-promotion-gate`
  - unit tests `tests/unit/test_promotion_gate.py`
- Evaluator is read-only over project bundles. It never:
  - unions POSSIBLE/UNKNOWN/REJECTED
  - treats incomplete extraction as clean
  - deletes legacy
  - flips `recognition.primary_engine`
  - uses held-out for tuning (held-out hard labels are excluded)
- Fresh cal/val evidence (2026-07-12):
  - P001: pairs=1717, issues=70, hard=65, COMPLETE, witness=1.0, possible_union=false, v2_changes_legacy=0, failure critical=0, non_asserted_union_violation=0
  - P003: pairs=413, issues=3, hard=0, COMPLETE, witness=1.0, possible_union=false, v2_changes_legacy=0, failure critical=0
  - hard-issue micro precision/recall = 1.0/1.0 on frozen cal/val labels
  - decision: `ready_for_review_only_v2_assist=true`, `ready_for_primary_engine_flip=false`, `primary_engine=legacy`
- Artifacts:
  - `.tmp/phase121_promotion_gate_calval/`
  - `.tmp/phase121_promotion_gate_evidence/{promotion_gate_evidence.json,metrics_by_project.csv,decision_log.md}`
  - `.tmp/phase121_hard_issue_eval/hard_issue_eval.json`
- Full suite: 523 passed, 1 skipped.
- Integrity: removed a stray NUL byte in `findings.md` (inside a sha256 description) that caused some tools to treat the file as binary.
- Remaining for true primary promotion (non-code / product):
  - human held-out hard-issue gold labels
  - explicit product approval to flip `primary_engine`
  - optional UI surface for review-only V2 assist

## Phase 121 recovery audit (2026-07-12)

- The current worktree contains only the Phase 121 promotion-gate implementation and planning evidence as uncommitted changes; earlier Phase 113-120 code is already present in the checkout.
- The evaluator is read-only and correctly keeps `primary_engine=legacy` in its decision output. Its current implementation must still be independently checked for fail-closed behavior when required artifacts are missing or malformed; a missing extraction gate, witness, or engine comparison must not accidentally satisfy a structural pass.
- The session-catchup helper was unavailable because sandbox process creation was denied and the escalation review service returned HTTP 503. Direct worktree/planning recovery was used instead; this is an environment limitation, not evidence of project completion.

## Phase 121 fail-closed hardening

- The initial evaluator could treat missing engine comparison, project graph, topology summary or failure queue as zero risk; it also failed to apply unknown-critical thresholds and allowed NaN/Infinity witness values to pass the `>=1.0` check.
- Hard-issue evaluation now records prediction artifact validity and requires non-empty labels and predictions plus both precision and recall thresholds. Missing issues no longer becomes a vacuous precision pass.
- Primary-flip readiness now requires all structural artifacts valid, cal/val hard pass, held-out human-gold hard pass, explicit product approval and configured `primary_engine=legacy`. Frozen cal/val labels alone can only authorize review-only evidence.
- CLI derives the primary engine from config, rejects a conflicting assertion, normalizes held-out split names, validates label paths and returns nonzero when the structural gate fails.
- Fresh P001/P003 output under `.tmp/phase121_promotion_gate_evidence_fail_closed/`: every required artifact status is `valid`; structural pass=true; cal/val TP=65/FP=0/FN=0; precision/recall=1.0/1.0; review-only=true; primary flip=false.
- Targeted promotion/hard-eval/CLI tests: 36 passed. Full suite: 540 passed, 1 skipped.

## Topology metrics entry audit

- P003's existing `topology_ground_truth_v1.csv` is a 12-row scoped junction fixture, not project-wide gold. Any computed junction result must be labelled `MEASURED_SCOPED` with sample/sheet coverage; pairwise-connectivity and open-endpoint precision/recall remain `UNMEASURED_NO_PROJECT_LABELS` until dedicated truth exists.
- Structural facts are still useful and reproducible without gold: overmerge/split suspicion counts, non-ASSERTED union violations, actual witness completeness and legacy-result divergence. They must not be renamed as precision/recall.
- The first delegated metrics module needs main-thread integration review before promotion use: the current fixture keys junction truth by `source_handles`, so evaluation must map decision line IDs through `lines.parquet`; witness completeness must consume the persisted witness artifact/summary rather than a new surrogate definition.
- Real Phase 121 bundles persist an empty `network_validation_suspicions_v2.parquet` with zero columns when there are no suspicions. The evaluator accepts only this readable zero-row legacy shape as count=0; missing, unreadable, non-empty or partially-schema'd suspicion files remain fail-closed.

## Phase 122 topology metrics implementation

- `evaluate_project_topology_metrics` now distinguishes structural evidence from measured truth scope. `STRUCTURAL_ONLY` is sufficient for structural review-only gating; `MEASURED_SCOPED` reports local fixture metrics; only complete `MEASURED_PROJECT` metrics may contribute to primary promotion readiness.
- Existing P003 truth is 12 scoped junction observations across two sheets. It can measure scoped junction TP/FP/FN, but has no network-partition, pairwise-connectivity or open-endpoint labels; those metrics remain null and explicitly unmeasured.
- Witness completeness uses the persisted `network_witness_summary.json` counts rather than a surrogate traceability definition. Non-ASSERTED union and legacy-result divergence remain direct persisted invariants.
- Promotion evidence now writes `topology_metrics_by_project.csv` and `topology_metrics_summary.json`; primary readiness requires project-scope topology gold in addition to hard-issue human held-out gold and product approval.
- First real run correctly failed closed because older zero-suspicion Parquet files contain no columns. A narrowly-scoped compatibility fix accepts only readable zero-row legacy suspicion files. The post-fix real rerun could not execute because the approval backend returned HTTP 503; no alternate execution was used.
- Targeted suite: 43 passed. Full suite: 547 passed, 1 skipped. Diff check has no whitespace errors.
## 2026-07-12 Recovery Boundary Before Recognition-Engine Work

- The Phase 122 implementation is present and unit/full-suite verified, but `.tmp/phase122_topology_metrics_evidence` is pre-fix diagnostic evidence only. It must not be used as proof that the compatibility-fixed real run passed.
- The next engine work must verify the supplied audit against current code and original DWG files under `test/`; the audit text is background evidence, not an accepted statement of current behavior.
- Priority is architecture-level extraction and semantic capability. Avoid filename, page-number, project-number, or individual-symbol production patches.

## Phase 123 Real-Corpus And Parallel Foundation Entry

- `test/` contains 502 original DWG files, spanning protection cabinets, communication cabinets, circuit schematics, backplanes, component wiring, and terminal drawings. The corpus is large enough to evaluate generic extraction and semantic behavior instead of tuning only P001/P003.
- Three isolated modules now exist for main-thread review: `extract/extraction_census.py`, `audit/electrical_semantics.py`, and `audit/symbol_dependency_library.py`, each with dedicated unit tests. They are not yet accepted as pipeline-integrated evidence.
- The current worktree still includes the uncommitted Phase 121/122 evaluation batch. Integration must preserve those changes and keep the new engine modules shadow-only until real-corpus evidence is generated.

## Phase 123 Extraction Census Main-Thread Review (Initial)

- `build_extraction_census()` correctly records non-consumed layouts, block definitions and nested depth, XREF resolution versus explicit load proof, unitless drawings, proxy/unsupported entities, MINSERT instances, and `virtual_entities()` exceptions/skips.
- Its default `consumed_layout_names=("Model",)` deliberately proves the current production limitation instead of pretending PaperSpace is covered.
- Integration must distinguish semantic-consumer support from shadow primitive retention. The module currently treats every entity outside the legacy semantic extractor's supported set as a blocking error; the configured set must be reconciled with `primitive_normalizer` so coverage dimensions remain explicit rather than conflated.
- Conversion warnings are retained but not automatically blocking. The write-path integration needs a severity contract rather than assuming every ODA warning is either harmless or fatal.

## Phase 123 Semantic And Symbol Model Main-Thread Review (Initial)

- `electrical_semantics.py` is correctly shadow-only and carries explicit evidence state, authority, confidence, source IDs, constraints, and relation-level union eligibility. `UNKNOWN`, `POSSIBLE`, and `REJECTED` cannot satisfy the union gate.
- `symbol_dependency_library.py` supplies the missing reusable concepts: versioned identities/fingerprints, geometry and nested-symbol dependencies, local ports, internal connectivity, aliases/sources, registry/annotation status, cycle and dangling-reference validation.
- Critical and ASSERTED connectivity require human-confirmed registered symbols and ports, including nested dependencies. This preserves the Phase 117-120 unknown-symbol safety invariant.
- Both modules are intentionally broad and currently independent of the persisted artifact schemas. Acceptance requires adapters and real artifact round-trip tests; adding them to the write path without that step would create an unverified parallel ontology.

## Phase 123 Current Extractor Audit Verification

- The supplied audit's ModelSpace limitation remains true in current code: `extract_cad_artifacts()` calls `doc.modelspace()`, sets `sheet.layout_name="Model"`, and only iterates that layout.
- Legacy semantic block expansion is still category-gated through `extract.insert_virtual_entity_categories`. An INSERT expansion exception is converted to an empty list without an entity-level warning.
- `primitive_normalizer.py` is a meaningful Phase 113+ improvement: it recursively retains INSERT children and normalizes LINE/ARC/CIRCLE/ELLIPSE/polyline segments into shadow primitives. However, it also starts only from `document.modelspace()` and returns silently when block expansion fails.
- Therefore the next generic slice should integrate document-level census before changing recognition heuristics. Census can prove what the current semantic and shadow paths did not consume, while preserving legacy Pair/Issue outputs.

## Phase 123 Census Integration Decision

- The correct construction point is inside `extract_cad_artifacts()`, immediately after the native DXF document is read and before ModelSpace-only extraction starts. This avoids reopening every converted file and preserves reader backend context.
- `CadExtractionResult` and `ProjectArtifacts` can carry one census record per source file without changing the public six-value unpacking contract.
- `write_project_artifacts()` should persist a stable project summary plus per-file census records. The existing extraction completeness gate should consume census failures instead of creating a separate competing gate.
- First integration remains behavior-compatible for Pair/Issue generation. The only intended product behavior change is fail-closed clean-conclusion eligibility when source content is demonstrably unconsumed or unsupported.

## Phase 123 Existing Extraction Gate Gap

- `evaluate_extraction_completeness()` currently gates only conversion/read failure, zero legacy primitives, and missing extractor execution. It cannot detect populated PaperSpace, unloaded XREFs, proxy/custom entities, or failed block expansion.
- Census results should be mapped by `file_id` into audit-required page results with stable diagnostic codes. Stable skip/non-audit pages can remain `NOT_APPLICABLE` under the current project contract.
- A measured severity policy is required before treating every legacy-unsupported entity as fatal. The real corpus must distinguish: content retained by shadow primitives, electrically meaningful unsupported entities, decorative entities, proxy/custom objects, and missing external/layout content.

## Phase 123 Available Real Census Inputs

- Fresh Phase 121 cal/val bundles still contain `findings/source_files.parquet` for P001 and P003 with converted DXF paths. Census can be measured without invoking ODA again.
- Existing extraction-gate and artifact tests use optional/default-empty artifact fields, so adding `extraction_censuses` can remain backward compatible for skip pages, malformed inputs, and direct writer tests.
- The first real measurement should remain diagnostic-only until unsupported severity is calibrated. Populated non-consumed layouts, unloaded XREFs, unreadable documents, proxy/custom objects, and virtual expansion loss can already be treated as structurally blocking.

## Phase 123 P001/P003 Census Measurement

- Measured 24 converted P001 files and 10 converted P003 files from Phase 121 bundles. With the initial strict policy, all 34 report `INCOMPLETE`.
- Every measured file is unitless (`$INSUNITS=0`). Unitless must therefore be `scale_unresolved/review` until a deterministic scale inference exists; making it immediately fatal would invalidate the entire known corpus without improving extraction.
- Legacy-unsupported totals are substantial: P001 includes CIRCLE 386, ARC 216, HATCH 100; P003 includes ARC 562, HATCH 529, CIRCLE 466, SPLINE 6, POINT 1. ARC/CIRCLE are already retained by primitive normalization, HATCH/SPLINE are not equivalently normalized for electrical semantics.
- P001's two populated PaperSpace layouts contain only two VIEWPORT entities each. The census must report `viewport_count` separately from paper-native content; viewport presence is a layout coverage concern, but is not proof that four independent paper annotations were lost.
- No XREF or proxy entity was observed in this P001/P003 slice. This does not establish absence across the 502-file corpus.
- P003 `12 元件接线图.dwg` contains two non-uniformly scaled nested block instances. Expansion did not fail, but transform fidelity must remain an explicit review warning.

## Phase 123 Census V2 Re-Measurement

- Focused tests pass: 11 census tests.
- After tiering severity, all 24 P001 and 10 P003 files are structurally `COMPLETE`; no census error is hidden.
- Review evidence remains explicit: all 34 have `scale_status=UNRESOLVED`; P001 has 2 viewport-only layouts and 100 HATCH entities outside shadow normalization; P003 has 529 HATCH, 6 SPLINE, and 1 POINT outside shadow normalization plus one file with non-uniform INSERT warnings.
- ARC/CIRCLE are reported as unsupported by the legacy semantic extractor while correctly excluded from shadow-unsupported counts because primitive normalization retains them.
- This v2 contract is suitable for main-pipeline persistence and structural gating: fatal status represents demonstrable content loss, while coverage/scale gaps remain measurable review dimensions.

## Phase 123 Census Pipeline Integration

- Census is now built while each native DXF is open, carried through `CadExtractionResult` and `ProjectArtifacts`, and persisted as `findings/extraction_census.json` plus `extraction_census_summary.json`.
- The existing extraction gate consumes census status by `file_id`. Structural errors become stable `CENSUS_<diagnostic>` page failure codes; review-only scale/coverage warnings do not alter clean status.
- The legacy six-value extraction-result unpacking contract is unchanged, and Pair/Issue generation is untouched.
- Targeted propagation suite passes: 52 tests across census, CAD extraction, extraction gate, artifact writing, and incomplete-input pipeline behavior.

## Phase 123 Electrical Semantic Artifact Integration Decision

- The new builder consumes the exact persisted Phase 119 inputs: `text_tokens`, final constrained semantic attachments, scope decisions, constraint decisions, and project profile.
- Persist separate node, relation, evidence, and constraint Parquet artifacts plus a summary JSON. Structured columns can reuse `_dict_rows_frame()` JSON serialization.
- This is a shadow artifact only. Integration acceptance requires `shadow_only=true`, graph validity, and `electrical_union_eligible_count=0` on current real projects.

## Phase 123 Symbol Library Integration Boundary

- Current project symbol inventory already provides stable definition names/fingerprints and marks every discovered definition `registry_status=UNKNOWN`, `declared_port_count=0`, `critical_issue_eligible=false`.
- The existing Top-N port fixtures live under `tests/fixtures` and remain empty with `PENDING_HUMAN_REVIEW`. Production code must not load test fixtures or promote these entries to registered/ASSERTED state.
- Integration should therefore add a config-backed production library loader/adapter. Project inventory definitions become UNKNOWN/CANDIDATE library entries by default; only explicit production library records with human-confirmed ports/connectivity may become registered or critical eligible.

## Phase 123 Symbol Adapter Design

- Add a runtime adapter separate from `symbol_registry.py`: inventory rows provide stable identity/aliases/source evidence; an optional `config.symbol_library.path` supplies human-reviewed ports, nested dependencies, and internal connectivity.
- Missing or malformed library files must produce a validation artifact and retain UNKNOWN/PENDING states, not silently promote symbols or abort the whole project.
- Persist the resolved library, validation issues, and summary alongside the existing symbol inventory. This keeps symbol knowledge inspectable and allows later human annotation without changing legacy Pair/Issue behavior.

## Phase 123 Fresh Real-Run Method

- P001 source root is the `110kV变压器保护柜/...WBH-812E...` directory; P003 source root is `【出原理图】N2604HBJ20732J合同/11000 站控层网络通信柜`.
- Phase 121 bundles include converted DXF cache files keyed by the same source IDs. A new temporary output can preload those caches and exercise the normal `analyze-project` and `run-audit` paths without invoking ODA again.
- Local ODA File Converter 27.1.0 is currently discoverable. The converter checks a valid target cache before conversion, so preloaded Phase 121 DXFs will be recorded as `cached` through the normal reader provenance path.

## Phase 123 Fresh P001/P003 Engine-Foundation Evidence

- Fresh normal pipeline outputs: `.tmp/phase123_engine_foundation_real/P001/...` and `.tmp/phase123_engine_foundation_real/P003/11000`, including analyze and audit.
- Census: P001 24/24 COMPLETE, P003 10/10 COMPLETE; all 34 remain `UNRESOLVED` scale. P001 reports two viewport-layout files, zero paper-native content; both projects report zero XREF/proxy/virtual-expansion-failure files.
- Electrical semantic graph:
  - P001: 9,974 nodes, 6,330 relations, 14,766 evidence records, 31,650 constraints.
  - P003: 2,869 nodes, 1,095 relations, 4,036 evidence records, 5,475 constraints.
  - Both: `shadow_only=true`, `valid=true`, constraint violations=0, electrical union eligible=0.
- Symbol dependency library:
  - P001: 67 inventory symbols; P003: 33.
  - Both: source not configured, library valid, ports=0, critical eligible=0, critical capable=0, validation/load errors=0.
- Compatibility: P001 pairs/issues remain 1717/70; P003 remain 413/3. Pair identity sets equal Phase 121 baselines and issue rule distributions are unchanged.
- Extraction gate remains COMPLETE/clean for both because all new findings are review coverage dimensions rather than demonstrated structural loss.

## Phase 122 Re-run Boundary

- The historical `.tmp/phase122_topology_metrics_evidence` remains invalid because it points at pre-compatibility bundles whose zero-suspicion validation Parquet lacks schema columns. It is diagnostic only.
- The fresh Phase 123 bundles are the only candidates for the post-fix evaluator run. P003 topology truth remains scoped (12 rows across two sheets); no project-wide topology gold exists.

## Phase 122 Post-Fix Completion Evidence

- `.tmp/phase123_promotion_gate_evidence` is the valid post-fix evidence set.
- `structural_pass_all=true`; review-only V2 assist=true; primary flip=false; primary engine remains legacy.
- P001 topology status is `STRUCTURAL_ONLY`; P003 is `MEASURED_SCOPED`. P003 scoped junction precision/recall are 1.0/1.0.
- Overmerge/split totals are 0 across both projects. Pairwise connectivity and open-endpoint precision/recall remain unmeasured because project-scope labels do not exist.

## Taskbook Source Availability

- The referenced `XJCheck_topology_upgrade_review_v1/docs/` directory is not present in the current checkout. The existing `doc/任务书.md` already contains the migrated 18.9 plan and remains the authoritative source; this session appended the 2026-07-12 status refresh as section 18.9.12 rather than inventing missing source text.

## Phase 124 Recovery Boundary (2026-07-13)

- The corpus census and document walker files are present after delegated development, but have not yet passed main-thread integration review.
- The symbol-review delegated turn ended with remote HTTP 502. `symbol_library_review.py` and the two config assets are present in the shared worktree, but their implementation and tests are untrusted until independently inspected and executed.
- No primary engine change is authorized; `recognition.primary_engine=legacy` remains the invariant.

## Phase 124 Corpus Census Main-Thread Review

- `report/corpus_census.py` correctly separates artifact validity from extraction health, validates project/summary/file schemas, cross-checks summaries, and leaves invalid project metrics null.
- `complete_corpus_metrics` is emitted only when every requested project artifact is valid; held-out projects are reporting-only.
- Before integration, add consistency validation between each file's `complete` boolean and structural `status`, then expose the evaluator through a reproducible CLI entrypoint and real split evidence.

## Phase 124 Corpus Census CLI Contract

- Reuse `alias:split=project_dir` syntax from the promotion evaluator, with explicit `--held-out` marking and no tuning behavior.
- Write deterministic project CSV and corpus summary JSON; return exit code 2 unless the requested corpus artifact status is VALID.
- The command evaluates persisted census evidence only and does not mutate project outputs.

## Phase 124 Integrated Targeted Verification

- Corpus census CLI, canonical scene artifacts, CAD propagation, report artifacts, and CLI contracts pass `60 passed`.
- The remaining symbol workflow gap is runtime promotion enforcement: a configured review document must be REVIEW_COMPLETE before the adapter can consume it, and each project should emit an editable pending review backlog.

## Phase 124 Canonical Scene Main-Thread Review

- `extract/document_walker.py` provides the intended shadow-only document layer: all Model/Paper layouts, separate VIEWPORT records, recursive INSERT/MINSERT provenance, nested transforms, retained unsupported entities, and explicit XREF/expansion diagnostics.
- Canonical scene records and layout views are never topology-union eligible. Unresolved XREF or transform/expansion loss makes the scene incomplete.
- Remaining review items before pipeline integration: diagnostic/source deduplication, real-project output volume, coexistence with `primitive_segments`, and explicit limitations for viewport projection, XREF loading, OCS/WCS, and unit normalization.

## Phase 124 Canonical Scene Integration Verification

- Canonical scenes now flow from CAD extraction into `ProjectArtifacts` and persist as per-file JSON plus records, views, diagnostics, unresolved-source Parquet files and a project summary.
- An initial wiring mistake was caught before real runs: scenes were passed to the extraction gate instead of the artifact container. The gate remains census-only; the corrected targeted suite passes `40 passed`.
- Legacy Pair/Issue consumers do not read canonical scene artifacts.

## Phase 124 Symbol Review Initial Main-Thread Review

- Despite the delegated HTTP 502, `symbol_library_review.py`, its tests, JSON Schema, and safe pending example are structurally complete in the worktree.
- Generated review documents deliberately remove authority from source libraries; pending items cannot be registered, critical eligible, or ASSERTED-connected. Promotion requires a valid REVIEW_COMPLETE document with zero pending items.
- Before acceptance, independently verify review metadata/evidence rules, decide whether rejected symbols remain in the promoted library or should be filtered, and confirm the placeholder pending port cannot be mistaken for approved production data.

## Phase 124 Symbol Review Verification

- Independent focused suite passed: `35 passed` across corpus census, document walker, symbol review, symbol dependency adapter, and core symbol-library validation.
- Rejected definitions may remain in a promoted document as audit history; core `can_drive_critical()` and `can_assert_electrical_union()` still reject them unless they are registered, human-confirmed, and structurally valid. No filtering is required for safety.
- The example asset is explicitly pending/unknown with `critical_issue_eligible=false`; it is a template and is not loaded by the runtime adapter unless explicitly configured.

## Phase 124 Recovery Verification Addendum (2026-07-13)

- The last unverified runtime change is now independently exercised: configured review documents must pass the promotion workflow before becoming a production symbol library. Focused symbol tests pass `24 passed`.
- A new project-level symbol review artifact writer is present in the shared worktree. Its intended contract is to emit an authority-stripped pending backlog plus validation and summary JSON; it still requires main-thread integration into the normal findings writer.
- The topology metrics artifact writer was hardened so invalid, partial, null, and `STRUCTURAL_ONLY` rows cannot manufacture corpus precision/recall or totals. Main-thread review must confirm compatibility with the existing promotion evaluator and persisted evidence schema.
- The additional non-held-out real-project run was not delegated because the active agent-slot limit was reached by completed agents and no `close_agent` tool is available. This is an orchestration limitation, not an engine blocker; the main thread will execute the run.
- The symbol review artifact is now integrated into the normal findings path. Every project emits `symbol_review_backlog.json`, `symbol_review_validation.json`, and `symbol_review_summary.json`; the explicit `findings.json` artifact inventory is covered by the report contract test.
- Main-thread accepted targeted evidence: `51 passed` for symbol/review/report integration and `44 passed` for topology metrics/promotion/CLI. The next gate is fresh P001/P003 plus an additional non-held-out real project.
- The real corpus has three top-level families. Historical documentation identifies the third remote/communication-cabinet probe (`10000`) as held-out, so it cannot be used as the Phase 124 additional tunable project. The extra run must come from another project directory in the established non-held-out families and remain free of sample-specific tuning.
- Frozen `benchmark_split_v1.csv` selects P004 (`12000 主变及35kV网络通信柜`, 11 DWG) as `training_candidate`. Phase 124 will use P004 as the additional non-held-out evidence project; P002/10000 and all other `heldout_test` projects remain untouched for tuning.

## Phase 124 Fresh Three-Project Evidence

- Fresh normal analyze + audit completed for P001, P003, and training-candidate P004 under `.tmp/phase124_real_engine_evidence/`.
- Corpus census is `VALID`: 3/3 projects valid, 42/42 extracted files `COMPLETE`, all 42 scale `UNRESOLVED`, 4 PaperSpace VIEWPORTs across two P001 files, zero paper-native entities, XREFs, proxies, or virtual-expansion failures.
- Corpus unsupported evidence remains explicit: legacy semantic unsupported 3,321 (ARC 1,158; CIRCLE 1,171; HATCH 978; POINT 2; SPLINE 12); shadow unsupported 992 (HATCH 978; POINT 2; SPLINE 12).
- P004 canonical scene: 8 scenes, 16 layouts, 7,582 records, zero diagnostics/unresolved sources, shadow contract valid, topology union eligible 0.
- P004 electrical semantic graph: 1,397 nodes, 324 relations, 1,681 evidence records, 1,620 constraints, zero violations, zero eligible union.
- P004 symbol dependency/review: 28 UNKNOWN/PENDING definitions, ports 0, critical/ASSERTED capability 0; review backlog is `READY_FOR_REVIEW`, promotion-ready false, safe pending contract true.
- Engine comparison changes legacy result count by 0 for P001 (1,717 pairs), P003 (413), and P004 (223). P001/P003 regression counts, rule distributions, statuses, texts, and lines match the Phase 121 baseline; exact Pair/Issue identity-set verification remains pending.
- P001/P003 exact compatibility is now proven: Pair identity sets, Issue identity sets, canonical full-row Pair hashes, and canonical full-row Issue hashes all match the Phase 121 baseline.
- The production review loop now has CLI boundaries: `validate-symbol-review` reports schema/evidence/readiness without promoting; `promote-symbol-review` writes a production library only after `REVIEW_COMPLETE`, zero pending items, valid human evidence, and core library validation. It never edits runtime config automatically.
- Fresh Phase 124 promotion evidence at `.tmp/phase124_promotion_gate_evidence/` remains structural-pass, frozen cal/val precision/recall 1.0/1.0, review-only assist true, primary flip false, primary engine legacy. The hardened topology summary correctly leaves corpus minimum precision/recall null because only scoped/no-label topology truth exists.

## Phase 124 Full 502-DWG Corpus Evidence

- Frozen `benchmark_split_v1.csv` mapped exactly to 27 projects / 502 raw DWGs. Fresh analysis under `.tmp/phase124_corpus_502/` completed 27/27 projects with zero failures in 637.2 seconds.
- The normal routing path extracted 415 auditable pages; the remaining raw DWGs were stable skip pages such as cover, catalog, and layout sheets. Corpus census is `VALID`, with 415/415 extracted files structurally `COMPLETE`.
- All-corpus reporting-only summary: 8 held-out projects are valid; held-out details were not used for code, rules, thresholds, or symbol knowledge.
- Non-held-out evidence (19 projects / 285 extracted pages): all 285 scale states remain `UNRESOLVED`; 4 VIEWPORT records occur in two P001 files; paper-native content, XREF, proxy, missing XREF, and virtual expansion failures are all zero.
- Non-held-out semantic unsupported total is 11,529: CIRCLE 5,598; ARC 3,537; HATCH 2,350; ELLIPSE 16; SPLINE 24; POINT 4. Shadow unsupported is 2,378, dominated by HATCH 2,350 plus SPLINE 24 and POINT 4.
- Non-held-out canonical scene totals: 285 scenes, 350,649 records, 4 VIEWPORT records, zero diagnostics/unresolved sources/invalid scenes, and zero topology-union-eligible records.
- Non-held-out symbol/semantic safety totals: 847 pending symbols, zero unsafe review projects, zero promotion-ready projects, zero invalid semantic graphs, zero constraint violations, and zero eligible semantic union.
- Across 19 non-held-out projects, 19,723 legacy pairs were compared and `v2_changes_legacy_result_count=0`.
- The dominant next evidence gap is not XREF/proxy loss in this corpus; it is universal unresolved scale plus a reviewable symbol-port knowledge backlog. HATCH/SPLINE/POINT require relevance classification before any electrical geometry adapter is authorized.

## Phase 125 Scale Evidence, Transform Fidelity, Shadow Gap, And Top-N Queue

- Added fail-closed `extract/scale_evidence.py`:
  - States: `DECLARED` / `CANDIDATE` / `CONFLICT` / `UNRESOLVED` / `INVALID`
  - `applied_to_geometry` is always false in this phase
  - lexical unit candidates (mm/cm/m/in/ft and Chinese equivalents) never auto-resolve scale
  - declared-vs-candidate conflicts are explicit
- Transform fidelity is recorded per file from census virtual-expansion warnings/failures:
  - non-uniform INSERT scale is counted and blocks millimetre readiness
  - OCS/WCS and nested block units remain `UNMEASURED`
  - `canonical_millimetre_ready` is hard-false until scale and transform contracts both pass
- Shadow-gap triage classifies unsupported entities without authorizing adapters:
  - HATCH/SOLID -> `LIKELY_DECORATIVE`
  - SPLINE -> `POSSIBLE_ELECTRICAL_GEOMETRY` (review sample sheets first)
  - POINT -> `POSSIBLE_MARKER`
  - ACAD_TABLE -> table pipeline, not wire geometry
  - OLE2FRAME -> external embedded content, fail closed
- Normal findings write path now emits:
  - `scale_evidence.json` / `scale_evidence_summary.json`
  - `transform_fidelity.json`
  - `shadow_gap_triage.json` / `shadow_gap_triage_summary.json`
- Symbol corpus queue CLI `evaluate-symbol-corpus-queue`:
  - ranks non-held-out inventories only by default
  - Top-50 from 19 ranking projects / 165 families
  - all queue rows `PENDING_HUMAN_REVIEW`, ports=0, critical_eligible=0
  - held-out usage remains reporting-only
- Real evidence:
  - Offline P001/P003/P004 scale: 24/10/8 files all `UNRESOLVED`, applied=0, mm_ready=false
  - P003/P004 non-uniform INSERT counts = 2 each
  - Fresh P001 write-path: pairs=1717 identity-equal to Phase 124 baseline; scale all UNRESOLVED; gap HATCH=100 and no adapter authorized
  - Corpus queue top families: `SYMB2_M_PWF165` (4220×18), shared `PWF231/PWF248` (2975×18)
- Verification: targeted 51 passed; full suite `641 passed, 1 skipped`; `primary_engine=legacy`; `git diff --check` has no whitespace errors (CRLF warnings only).

## Phase 126 Evidence (2026-07-13)

### Top-N review pack + consumption (no auto-critical)
- Generated editable packs from Phase 125 Top-50 queue:
  - `.tmp/phase126_symbol_review_pack_top5/`
  - `.tmp/phase126_symbol_review_pack_top10/`
- Combined + per-symbol templates are `PENDING_HUMAN_REVIEW`, `registry_status=UNKNOWN`, `critical_issue_eligible=0`, `ports=[]`.
- `consume-symbol-review` on pending pack: `valid=true`, `promotion_ready=false`, `promoted=false`.
- Human-confirmed fixture can promote and feed shadow port placements; union/critical remain false on placements.
- CLI: `generate-symbol-corpus-review-pack`, `consume-symbol-review` (plus existing validate/promote).

### Measured OCS/WCS + nested block units
- Census now measures extrusion identity and block definition units.
- Real P001 (8 converted DXFs under phase125 writepath):
  - `ocs_wcs_status=MEASURED_IDENTITY` (all 8 files)
  - `nested_block_units_status=MEASURED_UNITLESS` (drawing units unresolved / unitless)
  - `millimetre_readiness=NOT_READY_SCALE` for all 8
  - `canonical_millimetre_ready=false`, `applied_to_geometry_count=0`
- When scale is declared AND OCS identity AND nested aligned AND no transform failures → `MEASURED_PENDING_PROMOTION` (still not applied, still review-required).
- Evidence: `.tmp/phase126_ocs_wcs_measurement/`

### Shadow port consumer
- `audit/symbol_port_shadow.py` + findings `symbol_port_shadow_*.json`.
- Only REGISTERED + HUMAN_CONFIRMED ports emit placements; inventory PENDING libraries write empty placements.
- `electrical_union_eligible` and `critical_issue_eligible` always false on shadow placements.

### Verification
- Targeted + full suite: **649 passed, 1 skipped**.
- `recognition.primary_engine` remains `legacy`.

## Phase 127 Evidence (2026-07-13)

### Nested project bundle path resolution
- Real runner layout is `alias_root/<project_slug>/{findings,audit,extraction_completeness.json}` with sibling `cache`/`logs`.
- Added shared `report/project_bundle.py` (`find_findings_dir`, `resolve_project_bundle_dir`).
- Consumers updated: promotion_gate, topology_metrics, hard_issue_eval, symbol_corpus_queue.
- Flat fixture layout still resolves as `bundle_layout=direct`.

### Promotion gate on real nested evidence
- Projects available under `.tmp/phase124_real_engine_evidence/`: P001, P003, P004.
- After path fix: **structural_pass_all=true**, **ready_for_review_only_v2_assist=true**.
- Frozen cal/val hard labels (`tests/fixtures/hard_issue_labels_calval_v1.json`): micro precision/recall **1.0**, status `PASS_ON_FROZEN_CALVAL_LABELS`.
- Topology metrics: structural complete, measurement_scope still none → `topology_metrics_primary_ready=false` (needs project-scope human topology gold).
- Held-out human hard gold: `UNMEASURED_NO_HELDOUT_HUMAN_GOLD`.
- product_approval=false.
- **ready_for_primary_engine_flip=false**; `primary_engine` remains `legacy`.
- Evidence: `.tmp/phase127_promotion_gate_nested_fix/`.

### MACHINE_PROPOSED port drafts (DXF geometry)
- CLI/API: `propose-symbol-ports` / `audit/symbol_port_proposal.py`.
- Top-10 pack: `.tmp/phase127_machine_port_proposals_top10/` (9 with ports, 22 ports).
- Top-50 pack: `.tmp/phase127_machine_port_proposals_top50/`
  - proposal_count=50, proposed_with_ports=46, block_not_found=2, total_ports=125
  - draft validates: valid=true, promotion_ready=false, critical_issue_eligible=0
  - all ports annotation_status=`MACHINE_PROPOSED` only
  - checklist: `HUMAN_REVIEW_CHECKLIST.md`
- Review pack alias de-dupe: same CAD definition_name across fingerprints keeps alias only on highest-ranked family (avoids `LIBRARY_AMBIGUOUS_SYMBOL_ALIAS`).
- Templates: `.tmp/phase127_symbol_review_pack_top50/`.

### Remaining blockers to archive legacy primary
1. Human confirm Top-N (and broader) MACHINE_PROPOSED ports → REGISTERED + HUMAN_CONFIRMED
2. Held-out **human** hard-issue gold pack
3. Project-scope topology truth labels (junction/connectivity/open-endpoint)
4. Full-corpus structural coverage beyond the 3 real evidence projects currently on disk
5. Explicit product_approval
6. Declared/unit gold for millimetre promotion (still NOT_READY_SCALE / unitless drawings)

### Verification
- Full unit suite: **626 passed, 1 skipped** (627 collected).
- `recognition.primary_engine` remains `legacy`.

### Full-corpus structural promotion pass (audit backfill)
- Re-ran `rerun_audit_from_findings` on all 27 corpus_502 projects missing audit artifacts (non-held-out + held-out reporting).
- Promotion gate on all 27 aliases: **structural_pass_all=true** (27/27), including held-out structural.
- Evidence: `.tmp/phase127_promotion_gate_full_corpus_audit/`.
- Still blocked for primary flip: held-out human hard gold, project-scope topology gold, product_approval.
- Held-out human gold template (empty, not certified): `.tmp/phase127_heldout_hard_issue_gold_template/`.

### Non-held-out hard-label freeze v2 (emission fidelity only)
- After full audit backfill, re-froze current-head hard issues for all 19 non-held-out projects (341 labels).
- Path: `.tmp/phase127_hard_issue_labels_nonheldout_freeze_v2.json`
- Policy still `not_a_human_gold_standard=true` → cannot authorize primary flip.
- Gate with this freeze: micro precision/recall 1.0, calval_hard_pass=true, structural 27/27, primary flip false.
- Historical fixture `tests/fixtures/hard_issue_labels_calval_v1.json` left unchanged for unit tests (P001/P003 only).

### Phase 127 takeover boundary (2026-07-13)

- The referenced task has been taken over in a new Codex thread; the filesystem, not the older chat summary, is authoritative.
- Phase 125 and Phase 126 are already complete. Phase 127 is the active phase, with Top-50 MACHINE_PROPOSED port drafts and full 27-project structural promotion evidence present.
- The remaining promotion blockers are human/authority inputs (Top-N port confirmation, project-scope topology gold, held-out human hard-issue gold, product approval, and unit gold). They must remain fail-closed and cannot be synthesized by an agent.
- The worktree is intentionally dirty with the accumulated topology/semantics/symbol migration. Preserve all existing changes and continue from them without resetting or switching the primary engine from `legacy`.

### Phase 127 delegated safety audit (2026-07-13)

- Topology gold is still structural-only across 27/27 projects. The legacy truth CSV can currently self-declare `measurement_scope=project` without certified page coverage, source hashes, or human provenance; primary topology readiness also does not enforce non-zero/thresholded junction, connectivity, endpoint, or real overmerge/split metrics.
- Symbol review currently validates evidence references syntactically but permits machine-only sources (`symbol_corpus_queue`, `machine_geometry_proposal`) to be the sole evidence for a manually edited `HUMAN_CONFIRMED` record. This is a production-authority bypass and must fail closed.
- Unit/scale readiness has two false-ready paths: `MEASURED_IDENTITY_PARTIAL` OCS and `MEASURED_ALIGNED_PARTIAL` nested-unit measurements are accepted as ready. A unitless census can also be upgraded from a contradictory nonzero units field.
- The next implementation slice is safety hardening only: legacy topology CSV remains scoped; topology promotion requires meaningful metrics and certified packages later; machine-only/held-out symbol evidence cannot promote; partial/contradictory scale evidence cannot become millimetre-ready. No human labels will be synthesized.

### Phase 127 safety patch return (2026-07-13)

- Scale patch rejects partial OCS/nested-unit measurements and contradictory `UNRESOLVED` census plus nonzero INSUNITS; complete measured paths remain pending-promotion and geometry remains unchanged.
- Topology patch keeps all legacy CSV truth scoped, separates suspicion from real overmerge/split gold, and requires finite positive three-family metrics plus zero real overmerge/split before primary topology readiness.
- Symbol patch requires a non-held-out primary drawing or human-review source for completed promotion; machine/corpus sources may only support, never authorize. One old cross-module positive fixture now fails because it encoded the former machine-only authority assumption and must be corrected.
- The affected Phase 127 modules are still untracked in Git, so ordinary `git diff -- <file>` is empty; main-thread review must read their current contents directly. Existing source kinds already include `HUMAN_REVIEW_INPUT`, making the cross-module fixture repair compatible with the new classification without inventing a new runtime type.
- Main-thread source review confirmed the scale patch changes only evidence/readiness state and leaves geometry untouched. The symbol gate is fail-closed for unknown kinds and can repair the old fixture with an explicit non-held-out `HUMAN_REVIEW_INPUT` source while retaining the queue source as supporting provenance.
- Topology primary readiness now rejects scoped/zero/non-finite evidence and requires zero real overmerge/split. This is safe for the current state because no legacy CSV can produce `MEASURED_PROJECT`; certified gold-pack thresholds remain a separate future contract and must be frozen before held-out evaluation.

### Phase 127 real safety readback (2026-07-13)

- Real Top-50 machine review remains valid but non-authoritative: 50 pending symbols, `promotion_ready=false`, zero validation errors.
- Real P003 legacy junction truth remains `MEASURED_SCOPED` over 12 samples / 2 sheets; `metrics_complete=false`, real overmerge/split are null rather than suspicion aliases.
- Real P001 census remains 24/24 `UNRESOLVED` and `NOT_READY_SCALE`; `applied_to_geometry_count=0` and `canonical_millimetre_ready=false`.
- These results close the three safety-hardening tasks but do not close Phase 127. The next automatable slice is a pending-only topology gold template/validator; human labels and certification remain external authority.

### Topology gold module main-thread review (2026-07-13)

- The five-file template, exact source/page/hash binding, and pending non-authority contract are sound.
- Two certification gaps must be closed before promotion integration: `HUMAN_CERTIFIED` can currently pass with all three label tables empty, and the source-handle inventory mixes line, text, block, and primitive handles rather than proving complete classification of topology input lines.
- The validator must require review-complete annotation status plus non-vacuous/candidate coverage tied to topology artifacts; otherwise page-level booleans merely replace the former self-declared CSV scope.
- User clarified that `doc/任务书.md` already contains many electrical definitions and wants subagents to inspect real DWGs semantically to reduce manual review effort. The authorized design is machine-assisted pre-annotation with source handles/coordinates/rule citations and explicit confidence/reasoning; human certification remains a separate state transition.
- The attached takeover record ended immediately after dispatching the intended three semantic audits, but no durable audit result was recorded. Re-run them as fresh one-shot, read-only subagents against non-held-out evidence before selecting an implementation slice.

## Phase 127 main-thread semantic audit + connection review pack (2026-07-13)

### Three-perspective audit (non-held-out only)
- **Symbol/port:** Production inventories remain UNKNOWN/PENDING with ports=0. Geometry-driven Top-50 drafts are `MACHINE_PROPOSED` only and fail closed for promotion without non-held-out human primary evidence.
- **Wire/cross-page:** Project graph keeps `possible_union=false`. P001 emits 1221 cross-page CANDIDATE edges with severe label fan-out (e.g. bare `103/105/132`), plus 2816 geometry-only open endpoints. These are high-value human review targets, not ASSERTED connectivity.
- **Semantic/constraint:** Attachments stay shadow-only. P001 has 402 authoritative selected attachments vs 1674 review-only; electrical semantic union eligible remains 0. Strong constraints are inviolable and only demote authority.
- Taskbook citations used for proposal rationales: 18.8.2/18.8.3/18.8.7 and 18.9.2/18.9.8 (no POSSIBLE union; text proximity ≠ geometry; human labels route to schema/library/rule).

### MACHINE_PROPOSED electrical connection review pack
- New pack schema `electrical-connection-review-pack-v1` writes `manifest.json`, `proposals.json`, `summary.json`, `HUMAN_REVIEW_CHECKLIST.md`.
- Families: `CROSS_PAGE_ENDPOINT_MATCH`, `OPEN_ENDPOINT_LABEL`, `SEMANTIC_ATTACHMENT_REVIEW`, `LEGACY_PAIR_CONNECTION_REVIEW`.
- Safety: every proposal `annotation_status=MACHINE_PROPOSED`, `human_decision=PENDING`, `shadow_only=true`, `critical_issue_eligible=false`, `electrical_union_eligible=false`, `not_a_human_gold_standard=true`.
- Soft family quotas (≈40/20/20/10) keep mixed evidence when cross-page candidates dominate.
- CLI does not mutate config, geometry, Pair/Issue, or primary engine.

### Real pack measurements
- P001 top-100: 50 cross-page / 20 attachment / 20 open-endpoint / 10 pair review.
- P003 top-100: 2 cross-page / 73 attachment / 20 open-endpoint / 5 pair review.
- Both packs validate `valid=true`, `promotion_ready=false`, `certification_ready=false`.

### Remaining Phase 127 blockers (external authority)
1. Human confirm Top-N symbol ports
2. Human fill topology gold pack (`MEASURED_PROJECT`)
3. Held-out human hard-issue gold
4. Unit/scale gold or declared drawing units
5. Explicit product approval for primary flip

## 2026-07-14 collaboration status audit boundary

- The repository now contains and has published the MACHINE_PROPOSED connection-review module and its unit tests, but Phase 127 remains open.
- The next decision must be based on production-chain integration, not module existence: verify whether human decisions can be validated, routed to symbol/topology/rule knowledge, replayed in shadow mode, and measured without granting direct authority.
- Preserve the staged authority model: machine proposal -> human decision ledger -> validated knowledge candidate -> shadow replay -> measured promotion. No direct review-row-to-ASSERTED-union transition.

## 2026-07-14 direct DWG/visual agent adjudication trial

- Two fresh one-shot agents independently reviewed non-held-out P001 `S0007/F0007` (`06 直流回路图.dwg`): one from raw DWG/DXF objects and findings, one from a real high-resolution render plus CAD handle lookup.
- Raw-object review produced 8 external symbol-port connections and 2 negative same-symbol/cross-row relations at confidence 0.99-0.995, all bound to handles and coordinates. It showed `SYMB2_M_PWF236` has six identical-transform instances on the page but remains UNKNOWN with zero declared ports, causing false geometry-degree-one open endpoints.
- Visual review independently confirmed symbol-gap bridging, terminal internal pass-through, and mechanical linkage not being electrical connectivity. Render evidence lives only under ignored `.tmp/visual_dwg_trial/`.
- Important disagreement: visual state reading treated open DK/KZKK contacts as `NOT_CONNECTED`, while raw-object review correctly deferred internal contact conductivity to a component-state model. External port attachment is consensus-safe; internal dynamic contact state is not.
- The taskbook contains an orientation wording conflict around lines 127/129: prose says upper ports 1/3 while the CAD text and explicit mapping examples show upper 3/4 and lower 1/2. Runtime truth must bind instance-local port text + coordinates + block handles, not hard-code prose orientation.
- Conclusion: direct agent adjudication is feasible without a production CLI. It should enter the existing engine through a validated, dual-review consensus artifact; conflicts remain review/defer and never directly mutate ASSERTED union.
- The first reusable engine improvement is now measured in the native service path. PWF236 yields 24/24 explicit-label external-network attachments across six instances; every relation keeps internal conductivity false/deferred and union eligibility false.
- Single-page F0007 native evidence: 20 definition proposals / 58 ports; 232 instance candidates; 52 measured external attachments; 58 explicit labels; 138 network-bound candidates. Legacy pairs and pair candidates are full-row hash identical before/after.

## 2026-07-14 Current Recognition Blind-Spot Audit

- Current evidence does not support a truthful per-DWG list of every failed image because project-scope human gold is still pending. The defensible output is a capability-boundary list plus measured corpus risks.
- Layout-only/non-pairing classes remain non-semantic: screen layout pages, non-table backplates, unknown categories, and other unmatched categories route to `LayoutOnlyExtractor`.
- Communication-medium pages and dense cross-page continuation diagrams are review-only for connectivity. P001 has 1,221 cross-page CANDIDATE edges and 2,816 geometry-only open endpoints; none may be treated as asserted connection truth.
- Unknown/unreviewed symbol definitions remain non-authoritative. Existing P001/P003 evidence measured 67/33 unknown definitions and zero registered definitions, so novel or unconfirmed device symbols and their ports/internal connectivity cannot be reliably recognized.
- Viewport-only layouts are not interpreted, and HATCH/SPLINE/POINT remain outside equivalent shadow semantic normalization. The three-project census measured 978 HATCH, 12 SPLINE, 2 POINT shadow-unsupported entities and two viewport-layout warnings.
- All 42 files in the three-project census had unresolved drawing scale. This blocks trustworthy physical-distance interpretation, especially for non-uniform/nested transforms, even when ordinary topology extraction completes.
- The primary engine remains `legacy`; V2 is review-assist only and is not ready for a primary flip. Therefore any clean automatic conclusion on the above classes must remain fail-closed/review-required.
## 2026-07-15 Phase 128 basic-terminal generalization audit

- Three concurrent one-shot audits converged: exact fingerprint policies are safe adjudication overrides, but the generic terminal classifier is overfit to primitive-count ranges.
- Stable positive geometry is two equal ARC bodies at radius about 1.25 with compact radius-normalized extents and short 2/3/4-way leads; PWF231/232/233/234/238/239/243 form this family across rotation variants.
- Negative families remain distinguishable without names or coordinates: PWF208 is tall with radius about 1.875; PWF236/PWF237 and FJL are much larger/repetitive multi-port components; PWF194/PWF196 have no terminal ARC body.
- Automatic `MEASURED_TERMINAL_ATTACHMENT` requires three independent evidence families: terminal geometry, one unambiguous structured designator, and explicit external wire contact. Missing or ambiguous evidence must stay review-only, with no electrical union or critical eligibility.
- Human-confirmed PWF239 representative provenance: P001 `06 直流回路图.dwg`, converted `F0007_51ec3d17.dxf`, INSERT `EEB7` at `(150.0, 252.5)`, fingerprint `c578f4c57480a4eabf4f0affb3ac93a9ca7e3eef23ca67e810605b48f06ac99b`.
- Integration audit found the immediate defect: `is_high_confidence_terminal_geometry()` consumes `geometry_summary.shape_features`, but `propose_ports_from_block()` does not populate that field yet, so generic geometry recognition currently cannot activate.
- Existing terminal binding chooses one nearest center label without ambiguity semantics and promotes any label+line result directly. Phase 128 must distinguish unique vs near-tied structured labels before emitting a complete attachment.
- Existing summary exposes candidate/external-label/network totals only; additive geometry-recognized, complete-independent-evidence, ambiguous-binding, and status-count fields are required for measurable rollout.
- Real P001 F0007 validation after integration: PWF231/PWF233/PWF234/PWF239 classify as terminals with 2/2/4/3 proposed ports respectively; PWF239 measures two ARC radii `1.25`, local size `4.25 x 3.75`, and six geometry primitives. PWF236 is rejected despite the same ARC radii because its `21.0 x 15.125` body and 32 primitives identify a multi-port component rather than a compact terminal.

## 2026-07-15 Phase 129 adjudicated-component family audit

- Three fresh one-shot agents completed and were closed after an earlier batch hit two refresh-token failures and one non-returning run. The successful audits covered geometry, business semantics, and exact-fingerprint code dependencies.
- Shared architecture: `definition family classifier -> instance evidence binder -> behavior policy`. Fingerprints become versioned family-member/provenance evidence and exact human fallbacks, not family identity.
- Safe machine-generalizable families: `labelled_terminal.generic`, `component.external_multi_port`, `component.external_strip_two_port`, plus review-only candidates for open switches and line-break markers. `IGNORE_ELECTRICAL` cannot be inherited by visual similarity; machine similarity only yields review.
- Highest-risk code defect: instance proposals are indexed by `(file_id, definition_name)` while the human policy is read from the instance fingerprint. If proposal and instance fingerprints differ, binding must fail explicitly rather than share geometry silently.
- Real geometry anchors: terminal positives PWF231/232/233/234/238/239/243 are compact equal-ARC bodies; PWF208 is a tall negative; PWF236/237 are large repeated multi-port structures; FJL/PWF224 are elongated external-only two-port structures. Geometry classification alone never grants internal connectivity or IGNORE behavior.
- User explicitly authorized geometry-family IGNORE behavior rather than exact-fingerprint-only suppression. Revised boundary: high-confidence matches to separately modelled confirmed IGNORE subfamilies may suppress electrical semantics across fingerprints; approximate/tied matches remain review-only. Provenance and raw geometry are never deleted.
- Measured P001 IGNORE prototypes: PWF194/196 share no-ARC, two-port, `LINE=3..4/LWPOLYLINE=2`, aspect about `6.53`; PWF229 is `ARC=4/LWPOLYLINE=2`, aspect `9.6`; PWF208 is `ARC=2(r=1.875)/LINE=3/LWPOLYLINE=2`, aspect `3.45`; PWF191 uniquely includes two HATCH with dense linework; PWF206 uniquely includes two TEXT and four geometric ports; PWF165 and PWF210 have distinct compact no-ARC histograms/aspects.
- Implemented versioned family classification and centralized behavior policy. High-confidence IGNORE geometry matches now suppress across fingerprints; partial switch/line-break similarity stays `REVIEW_REQUIRED`. External terminal/component families remain shadow external-only.
- Added strict instance/proposal fingerprint binding: exact fingerprint wins; legacy no-fingerprint proposals are explicitly `LEGACY_NAME_FALLBACK_UNVERIFIED`; conflicting same-name fingerprints emit `REJECTED_FINGERPRINT_MISMATCH` with no electrical eligibility.
- Real synthetic-fingerprint cross-check passed 8/8 IGNORE positives and 7/7 non-IGNORE controls; FJL also generalized as `component.external_strip_two_port.v1`. Full suite passes `750 passed, 1 skipped`.
