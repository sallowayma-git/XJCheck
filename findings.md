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

## 2026-07-15 Phase 130 cleanup inventory

- Phase 128/129 was committed locally as `4dc5d27 generalize adjudicated symbol families` before cleanup.
- `.tmp` contains 27 fully regenerable Phase 121-127 run directories totalling `3,331,372,586` bytes (~3.10 GiB); the largest is `phase124_corpus_502` at ~2.63 GiB.
- Ignored test residue consists of `.pytest_cache` plus Python `__pycache__` directories under source/tests.
- Tracked legacy documents are concentrated in `doc/architecture`, `doc/page_findings`, `doc/deep-research-report.md`, `doc/findings.md`, and `doc/page_task_queue.md`; no source/test code references those exact document paths. Runtime `page_findings` is an internal data concept and is unaffected by deleting old checked-in review snapshots.
- Preservation boundary: keep `doc/任务书.md` as the active specification and rewrite `doc/human_arbitration_phase98.md` as the single canonical historical arbitration record before deleting the stale documents.
- Cleanup completed within verified workspace paths: `.tmp` and all Python/pytest caches are absent; tracked legacy documents were removed. The canonical arbitration file now records current decisions and explicitly treats fingerprint drift as provenance rather than family identity.
- Clean full-suite verification passed `750 passed, 1 skipped`. Fresh raw-DWG analysis rebuilt P001 and P003 only; preliminary definition-family aggregation shows many queue rows are already covered by human/family evidence even though the legacy registry queue still labels every definition UNKNOWN, so the next review list must be derived from family/binding status rather than raw queue length.
- After excluding confirmed/consistent family matches and structural zero-port definitions, the fresh conservative queue contains 46 unique electrical definitions. Project counts are P001: 25 resolved / 38 needs-human / 4 metadata-or-zero; P003: 10 resolved / 18 needs-human / 5 metadata-or-zero.
- PWF324 is ranked first (100 instances) because the same stored fingerprint has inconsistent per-file geometry observations: two files show a 3-LWPOLYLINE/5-port ETHERNET block while another shows a 2-LWPOLYLINE/4-port shape that matches the functional-graphic IGNORE prototype. Any mixed family evidence is review-required, not auto-resolved.
- Final post-classifier test result is `752 passed, 1 skipped`. Heavy fresh-census data was deleted after extracting `.tmp/current_symbol_review/unresolved_symbols.json` and the PWF324 review crop; current temporary review artifacts total only about 626 KiB.
- User resolved the highest-priority PWF324 ambiguity: it is an Ethernet communication-port graphic with no required outward communication mappings. Both observed geometry states now enter `communication.ethernet_port_ignored.v1`; PWF330's wider aspect remains a tested negative.
- Fresh P003 replay produced 3/3 exact PWF324 suppressions under the Ethernet-ignore family. The conservative cross-project review queue is now 45; next is PWF316 with 38 instances across P001/P003.
- User confirmed PWF316 is an ST single-mode optical communication port with no required `1T/1R` mappings. It now forms `communication.optical_st_port_ignored.v1`; compact two-ARC terminals remain an explicit negative. The queue is now 44.
- PWF318 review localization caveat: the backlog representative `(40.0,220.0)` is the enclosing parent insertion coordinate, while canonical provenance expands nested handle `11176` to the actual PWF318 block-reference insertion `(40.0,232.495)` on the representative P001 page. Its world geometry spans approximately `x=38.126..41.874`, `y=228.001..232.995`; screenshots must mark this expanded geometry, not center a box on the enclosing insertion.
- User confirmed PWF318 is a ground symbol with no mapping or electrical-union semantics. The accepted family is `electrical.ground_symbol_ignored.v1`; generalization must use the closed round contact plus one lead and three parallel, monotonically shortening ground bars, with a same-count non-ground geometry negative. The compact queue moves from 44 to 43; KK2P (17 cross-project instances) is next.
- Subagent implementation correctly added exact-member fallback, normalized line lengths, largest parallel group, and a closed-bulged-polyline requirement. Main-thread review found one remaining overgeneralization risk: the initial rule did not prove that the fourth line is orthogonal to and centered on the three bars, nor that the round contact is attached to the lead. Integration must add these topology bindings before accepting the model.
- Integration now stores translation/rotation/scale-normalized line segments and closed-bulged contact center/radius evidence. A ground match requires three parallel bars centered on an orthogonal lead, the longest bar at the lead endpoint, two farther bars with monotonically decreasing lengths, and the round contact at the opposite lead endpoint. This closes the same-count branch/decoration false-positive path.
- Fresh `analyze-project` on the representative P001 page persisted only seven top-level definition proposals and did not include nested PWF318, even though canonical-scene expansion contains its handle and primitives. Direct block-level validation is therefore required now; separately, the default proposal artifact's nested-definition coverage is a V2 replacement gap that must remain visible rather than being mistaken for a failed ground-family classifier.
- Direct validation against the recovered real DXF block proves the finalized topology rule matches both the exact human fingerprint and an unseen fingerprint. The observed normalized evidence includes lead length `0.800242`, bar lengths `1.0/0.750227/0.500151`, one closed-bulged contact centered at the opposite lead end, and zero surviving ports.
- Nested-definition proposal recovery is now integrated at artifact-write time with per-DXF document caching and file-local instance provenance. A fresh P001 run includes PWF318 in `symbol_port_definition_proposals.json` as zero-port `HUMAN_ADJUDICATED_NON_CONNECTIVE`; the full suite passes `759 passed, 1 skipped`.
- KK2P human adjudication: treat it as an external four-port component with no internal connectivity. Real P001 source confirms the first instance label is exactly `1DK` (TEXT handle `27FE0` at `(45.2475,279.0)`), not an estimate. Port identities are `1DK-1..4`; observed external labels are `ZD9`, `1QD5`, `ZD1`, and `1QD1` for ports 1..4 respectively.
- Current component-page extractor already emits the four authoritative mappings at confidence `0.95` with `pair_kind=component_mapping` and `submode=kk_multi_port_component`; no business mapping rewrite is needed. The remaining gap is V2 definition classification: KK2P is still `UNKNOWN/REVIEW_ONLY` despite real geometry `LINE=9`, four closed-bulged LWPOLYLINE contacts, four numeric text slots, four machine ports, and a compact 25×30 body.
- Subagent implementation classifies the real block under both exact and unseen fingerprints without using the definition name; both preserve four ports under `EXTERNAL_PORTS_ONLY` and forbid internal connectivity/union. Main review found its initial claimed rotation invariance was only proven for 90°/precomputed flags: extractor line topology and contact-grid checks were still tied to drawing X/Y axes. Integration must replace them with relative parallel/perpendicular direction groups and pairwise-distance rectangle evidence.
- Rotation hardening is complete: arbitrary 37° block rotation now passes through extracted line-direction groups and pairwise contact distances, while collinear/same-count contacts remain negative. Fresh P001 replay classifies KK2P as exact `component.external_multi_port.v1 / EXTERNAL_PORTS_ONLY` with four retained ports and reproduces all four `1DK-*` mappings at confidence `0.95`.
- Final KK2P full-suite gate passes `762 passed, 1 skipped`; the compact queue is 42 with PWF171 next. PWF171 is a small vertical 5-LINE/2-LWPOLYLINE graphic between the `201` and `207` rows near the heavy-gas trip circuit; the adjacent large boxed diode is a separate component and not the review target.
- User adjudicated both the small PWF171 diode and the adjacent large boxed diode as non-connective IGNORE. Source localization identifies the boxed diode as `SYMB2_M_PWF191`, handle `2CE58` at `(165.0,240.0)`, fingerprint `9a1c6d...cb85b`; PWF191 was already suppressed under the earlier generic graphic IGNORE decision, so this turn refines its semantic family rather than discovering an unsuppressed component.
- Diode worker exact/bare paths pass, but real unseen PWF191 still falls through to the old `non_electrical.graphic.v1` rule because no boxed-diode topology evidence is extracted. The worker's bare helper also counts absolute X/Y-aligned lines and is not truly rotation invariant. Main integration must bind the bare motif to the two-contact axis and derive boxed outer-frame plus repeated-short-motif evidence before accepting the family unification.
- Real boxed PWF191 contains two closed bulged contact circles plus one closed straight 4-corner outer polyline spanning about `5.0×6.872`; its 13 lines split into one main five-line diode and two repeated four-line lower motifs, reflected by scale-normalized length multiplicities `2/4/2` for the short levels. These are sufficient rotation/scale-invariant boxed evidence when combined with HATCH=2.
- Final real-block validation succeeds for both states under exact and unseen fingerprints. PWF171 uses contact-axis-bound lead/bars/shared-apex topology; PWF191 exposes `outer_box_topology=true` and `boxed_diode_repeated_topology=true`. Both unseen paths now enter `electrical.diode_symbol_ignored.v1 / GEOMETRY_FAMILY_NON_CONNECTIVE` with zero ports.
- Full-suite verification after diode integration passes `769 passed, 1 skipped`. The post-diode queue had 40 definitions; concurrent WTX resolution subsequently reduced it to 39. It still begins with PWF330, and no PWF171/PWF191 review item remains.
- PWF330 human adjudication changes the earlier PWF324 negative boundary: the wider `ETHER/NET` LAN graphic is also non-connective IGNORE. It should become a separate strict geometry/text-topology subrule under `communication.ethernet_port_ignored.v1`, not a widening of PWF324's aspect threshold and not a fingerprint-only exception.
- Worker review exposed a rotation-generalization gap: `normalized_closed_straight_lwpolylines` currently stores axis-aligned bbox width/height, and the worker test only exchanges those fields for a 90° case. PWF330 must instead use polyline edge-length/parallel topology (or another orientation-free representation) and prove a non-right-angle transformed block.
- Fresh PWF330 replay reveals a stronger worker-fixture error: real geometry contains two closed bulged contact circles and only one closed straight body. The exact member still suppresses because fingerprint authority wins, but the worker's unseen rule requiring three straight bodies cannot generalize to the source drawing. Correct model must bind the two contacts to the body and `ETHER/NET` layout using real topology.
- Source topology for the corrected PWF330 rule: one closed square with four equal 7.5-unit edges, two equal radius-0.5 bulged contacts whose centers define the component axis, and body center lying on that axis; local contact-center spacing is 11. `ETHER` and `NET` are the only block texts. Edge lengths, distances, projection, and perpendicular offset are rotation/scale invariant.
- Accepted family design: retain the common business family `communication.ethernet_port_ignored.v1` and distinguish PWF330 with rule id `ethernet-lan-wide-contact-body-topology-v1`. This keeps PWF324/PWF330 semantics unified without broadening PWF324's old aspect-only branch.
- PWF330 real-block exact/unseen replay confirms the corrected geometry path and zero-port policy. The next unresolved `A$C2E3F2C02` is visually an inline semicircular rise on manual closing/tripping conductors; its connectivity semantics must be human-confirmed rather than inferred from its 2-LINE + semicircle geometry.
- Final PWF330 gate is `779 passed, 1 skipped`. Resolved replay/crop products are deleted; the main compact queue is now 35 after concurrent side resolutions, headed by `A$C2E3F2C02`.
- Human correction for `A$C2E3F2C02`: do not model the red-box object as IGNORE or as an electrical component. It is a wire crossover jump. The arc path joins its two leads; any conductor intersecting the raised arc remains a separate net with no junction. The engine therefore needs path-selective continuity, not zero-port suppression and not all-way intersection union.
- Next main item `Ld_DzbJD_Left` is the left-oriented duplicate-line/duplicate-polyline stepped marker at P001 `30F34`. Context places it beside `GND` and device row `01 电源地`; its drawing resembles a ground marker, but its port/mapping semantics remain a human question rather than an automatic mirror inference.
- Human adjudication resolves `Ld_DzbJD_Left` as a ground symbol with whole-symbol electrical IGNORE semantics. It should share business family `electrical.ground_symbol_ignored.v1` while using a separate strict duplicate-step geometry rule; exact fingerprint remains provenance only.
- The new crossover-jump module is not yet production-effective: its recognizer/tests are isolated and no default artifact or topology builder invokes it. Acceptance requires a main-chain call plus real-page evidence that the jump path unions only its own endpoints and rejects the crossing conductor.
- Integration audit locates the active topology boundary at `audit/wire_topology.py::build_wire_topology_frames`, called by `report/artifacts.py`. The isolated recognizer groups block-local LINE/ARC records and returns primitive-level pairs; integration must translate those facts into the topology graph's endpoint/network contract and validate real canonical rows plus INSERT transforms.
- `build_wire_topology_frames` currently consumes `artifacts.lines` only; normalized nested ARC/LINE geometry is separately available as `artifacts.primitive_segments`. A production jump bridge must identify the real INSERT's transformed outer attachment lines, merge their existing line-network groups, and emit auditable bridge evidence while leaving a crossing line in a separate group.
- Existing topology already supports generic `reason=block_span` gap bridging and keeps interior crossings separate by default. The key acceptance question is therefore whether A$C2E3F2C02's real external leads are already one network for the right reason; if yes, integration should add family-specific evidence/no-junction provenance without changing network cardinality.
- Ground-family collision: real `Ld_DzbJD_Left` exact policy reports family `electrical.ground_symbol_ignored.v1`, but classifier rule selection is the previously existing DZB-right geometry branch. Because the two shapes are reflection-equivalent, adding a later mirror-invariant ground rule cannot win. Main review must resolve ordering/family ambiguity without weakening zero-port behavior or pretending geometry can distinguish identical states.
- Real A$ jump attachment endpoints are measured: external legacy lines terminate at the INSERT's local x=0 and x=10 world transforms, while nested LINE/ARC primitives fill the gap. This provides an exact bridge contract and avoids proximity-only block-span guessing.
- The external jump leads are already in one legacy network due to generic block-span evidence. Correct integration is semantic refinement: identify block `B0062` as a certified crossover jump, retain that one bridge, and explicitly record that the crossing conductor at the raised arc is excluded from union.
- Because the long crossing conductor later connects elsewhere, global network IDs cannot prove local isolation. The durable evidence contract is: bridge event for external jump leads with `reason=crossover_jump` and `no_junction=true`, plus no junction row at the arc apex that lists the crossing line `L0088` with either jump lead.
- Left/right stepped glyphs are reflection-equivalent under the requested geometric invariances. Exact human policies can distinguish left ground from right marker provenance, but unseen geometry cannot truthfully infer which semantic label applies. A shared nonconnective geometry fallback with exact semantic refinement is safer than two overlapping rules where one is unreachable.
- Current tests encode a distinct right-marker family for unseen geometry. Therefore any ground-family fix must either prove a stable handed local topology difference or introduce a shared generic nonconnective fallback; changing branch order alone would satisfy one test by invalidating another semantic contract.
- Implemented the shared-fallback option: exact human policy retains the requested `electrical.ground_symbol_ignored.v1` for Ld_DzbJD_Left, while reflection-equivalent unseen redraws enter a generic stepped nonconnective IGNORE family. This preserves behavior and provenance without an unreachable duplicate rule.
- Crossover topology is now production-connected and auditable, but fresh-census recurrence still needs one final gate: A$C2E3F2C02 must be classified as a wire primitive in symbol inventory/proposal output so it does not reappear as an UNKNOWN symbol even though wire topology is correct.
- `WIRE_PRIMITIVE` must be semantically separate from IGNORE: both clear symbol-port proposals, but only wire topology creates the certified same-path bridge. Proposal status should say exact/geometry wire primitive, never `NON_CONNECTIVE`, and all component mapping flags remain false.
- The symbol inventory recurrence path is now closed in code: exact and unseen complete LINE-ARC-LINE geometry enter `wire.crossover_jump.v1 / WIRE_PRIMITIVE` and suppress component-style ports without suppressing the topology bridge.
- Fresh report evidence falsified the recurrence claim at artifact order: proposals are resolved, but `unknown_symbol_queue_v1` remains open because inventory is written before policy output. Queue filtering must happen after proposal generation. The jump recognizer also needs whole-group cardinality, otherwise a terminal containing a semicircle and two suitable leads is falsely promoted.
- Unknown-queue filtering must be conservative and behavior-based: only authoritative geometry/exact rows whose mode itself resolves symbol review are removed. A mere family candidate, terminal geometry, or external component family is insufficient because those may still require human binding semantics.
- Schema distinction: `unknown_symbol_queue_v1` means “not in formal registry,” not “still needs current human adjudication.” It legitimately retains human-policy definitions until registry promotion. The compact current-human queue is the filtered operational queue; proposal `behavior_mode/status` is the electrical authority. Preserving this distinction avoids silently redefining baseline metrics.
- Strict recognizer validation on real `primitive_segments.parquet` returns 5/5 A$ jump INSERTs and zero other definitions. This closes the most important overgeneralization risk from the first 41-match replay.
- Final full-suite result is `796 passed, 1 skipped`. Resolved temporary products are gone; the operational human queue is 28 and begins with PWF89.
- PWF89 context shows a circle with diagonal slash and four outward contact directions, used repeatedly as `JD1/JD2/JD6` around `AC230V L/N` conductors. Its internal connectivity and whether all four sides are functional cannot be inferred from the glyph; it is the next human-adjudication question.

## Reverse review: WTX-871 communication panel

- Do not classify the 380.4×85.4 outer INSERT bbox as one two-port device. It is a container for COM/LAN/CAN connector groups.
- Recognition target is the repeated small closed rectangular pin cell. Pin cells are arranged in horizontal rows or vertical columns; emit two opposite-side external attachments perpendicular to the row/column axis. Outer panel borders and large connector/socket contours are structural negatives.
- Default safety remains no-union: two attachment sides describe external mapping evidence for one cell, not conductivity between different cells or groups.
- Real WTX-871 block census: `LWPOLYLINE=210`, `TEXT=121`, `LINE=15`, `HATCH=8`, nested `INSERT=2`. Exactly 86 closed `5×5` rectangles form two horizontal rows of 43 cells; each rectangle contains one native pin text. X-spacing partitions each row into eight 5-cell COM groups and one 3-cell CAN group, matching the visible COM1..COM16 and CAN1/CAN2 layout. This repeated-cell structure is the primary geometry anchor; the outer 380.4×85.4 panel is a negative.
- Native group labels confirm upper/lower rows as `COM1..COM16` and `CAN1/CAN2`. Four LAN groups are drawn differently: each LAN1..LAN4 has a `12.5×12.0689` socket outline with two internal `3.4812×1.4` closed details, not 5×5 pin cells. The engine therefore needs two submodes under one panel family: repeated square-cell pins for COM/CAN and socket-level external ports for LAN; the tiny decorative LAN internals must not become independent electrical pins without stronger evidence.
- The 5×5 cells have no block-local line segment attached exactly at the side midpoint. Their top/bottom side points are intended as instance attachment loci for modelspace external lines, so definition proposal must emit those loci explicitly rather than rely on generic free-endpoint extraction.
- Current engine failure is now measured: generic free-endpoint extraction collapses WTX-871 to two panel-edge ports and misclassifies it as `switch.open.candidate.v1 / REVIEW_REQUIRED`; both candidates are `UNRESOLVED`, and the source page produces zero COM/LAN/CAN pairs. The replacement must bypass generic two-extreme selection for this family.
- Native cell contents supply pin identities (`1..5` for COM, `1..3` for CAN), while COM/CAN group labels are separate native texts (`COM1..COM16`, `CAN1/CAN2`). Composite identity must therefore be group label + cell label (for example `COM1-3`), not a globally assigned nearest numeric label.
- Source-page evidence resolves the two cell sides semantically: the panel-side identity is `group + pin` (for example `COM1-3`), while a short modelspace line at the outward side leads to a rotated external label (for example `1-42TD1`). Thus the required result is a no-union `component_mapping` such as `COM1-3 -> 1-42TD1`, not two unrelated machine ports and not a conductive bridge through the square.
- The first COM1 row proves the alignment: cell centers are approximately `x=95.172/100.172/105.172/110.172/115.172`; outward lines and labels exist for pins 3/4/5 at `x≈105.169/110.169/115.169`, with texts `1-42TD1/TD2/TD3`. Pins without an outward line remain absent/review rather than fabricated.
- The page is currently `page_type=unknown`, `route_target=LayoutOnlyExtractor`, `audit_disposition=classify_only`; therefore adding only a ComponentDiagramExtractor submode would never execute on the real page. WTX mapping extraction must be symbol-family driven (or explicitly routed for communication panels) and must run even when the enclosing page remains layout-only.
- Existing `extract_small_port_box_component_pairs` is structurally similar but gated to horizontal component pages and block-name allowlists. Reusing its evidence/pair contract is appropriate; reusing its page gate or nearest-global-numeric binding is not.
- Correct integration path is two-part: classify pages with repeated native `COM\d+` plus `CAN/LAN` groups and dense repeated `1..5` pin texts as `communication_multiport_panel -> ComponentDiagramExtractor/audit_required`, then run a dedicated communication-panel component-mapping submode. This avoids a block-name-only route and ensures the extractor actually runs.
- The mapping extractor can operate on transformed TextItems and line groups: partition COM/CAN labels into two y rows, assign native numeric pin texts to the nearest left group within a geometry-bounded span, choose outward side by row, and require a matching external rotated label plus a vertical support line. It must emit only evidenced pairs and leave unwired pins absent/review.
- LAN1..LAN4 have short external stubs on the source page but no nearby external endpoint text. They can support shadow port-to-line/network attachment under identities `LAN1..LAN4`, but cannot support a named `component_mapping` right endpoint on this page. COM/CAN named pairs can be implemented confidently; LAN named cross-page mapping remains fail-closed unless another page supplies identity evidence.
- Critical integration constraint: legacy `texts.parquet` contains 79 modelspace texts but none of WTX-871's 121 nested native texts (`COM/CAN/LAN` and pin numbers); those exist only in the DXF block/canonical scene. Therefore page-classifier or ComponentDiagramExtractor logic based only on `TextItem` cannot recover group+pin identity. The robust path is definition-level block parsing inside `propose_ports_from_block`, carrying explicit logical cell identities into instance binding.
- Symbol-port candidates are built for all symbol instances independently of page audit routing, so a specialized repeated-cell proposal can function even while the page remains `LayoutOnlyExtractor/classify_only`. This avoids broad nested-text promotion into legacy text extraction.
- `ProposedPort` currently drops semantic metadata in `to_review_port`; WTX support needs additive optional fields (`logical_port_identity`, group, pin, cell side) preserved by both `to_dict` and `to_review_port`. Existing ports remain backward compatible through `None` defaults.
- Instance binding already has the required mechanics: transforms local loci to world coordinates and matches exact external line endpoints. For WTX, add a panel-family branch that uses the carried logical identity instead of nearest numeric text, binds a cleaned nearby rotated endpoint label, and emits `MEASURED_COMPONENT_PORT_MAPPING` only when identity + external label + short outward line all agree.
- Real definition-level result is exact: 86 ports, two rows, group counts `COM=16/CAN=2/LAN=4`, dominant cells `5×5`, and identities `COM1-1..COM16-5` plus `CAN1-1..CAN2-3`. The special parser ignores `max_ports`, because limiting to generic 4/6 extremes would recreate the original defect.
- Real instance binding now produces 46/46 wired COM mappings: upper labels bind within 5 units of the outward side; lower labels are upward-rotated strings whose insertion point is up to 22 units below, so side-aware reach is required. Unique x alignment plus exact short-line endpoint prevents cross-column assignment. Remaining 40 COM/CAN cells are genuinely unwired on this page.
- CAN1/CAN2 cells are recognized but unwired. LAN1..LAN4 labels are recognized by the panel model but need explicit socket-level proposal rows so they remain visible as unresolved communication ports instead of disappearing; no named LAN endpoint can be fabricated from this page.
- LAN socket modeling is now explicit but deliberately weaker than the repeated pin-cell mapping model: each `LANn` label must be uniquely contained by one rectangle whose width and height are each 1.8–3.2 times the dominant pin-cell dimensions. The model emits only the outward socket boundary locus, excludes the two tiny decorative rectangles, and does not invent a named right endpoint. Real WTX yields exactly four such loci.
- Full source-page replay proves the complete family-driven path works even though the page remains layout-oriented: 90 WTX candidates survive definition-to-instance transformation, 46 have identity + cleaned external label + exact short line and become measured mappings, while all other rows fail closed. No WTX row retains the former two-port open-switch family.

## Reverse review: KNS2500-6RS1FSST-P1

- Human authority is whole-region electrical IGNORE: no internal connectivity and no external mapping. Visible power, serial, optical, and grounding labels are panel annotation only for this audit model and must not produce symbol-port candidates.
- The current V2 `component.external_strip_two_port.v1 / REVIEW_REQUIRED` classification is therefore semantically wrong and must be replaced by a geometry-generalized zero-port family, with the exact fingerprint retained only as provenance/fallback.
- Real definition evidence is `TEXT=29`, `LWPOLYLINE=23`, `LINE=20`, `CIRCLE=4`, one nested INSERT, aspect about `6.707`, 19 closed bulged polylines, and a maximum parallel-line group of 18. The four circles form two equal-radius pairs (`2.363799×2`, `3.056356×2`), while native labels include all `COM1..COM6`, `ST/1T/1R`, `P+/P-`, `+/L`, `-/N`, `TX/RX/GND` anchors.
- The generalized matcher combines those scale-invariant circle ratios and aspect/parallel-contact evidence with the complete native label set. This prevents arbitrary tall terminal strips or dense cabinets from inheriting whole-region IGNORE solely from primitive counts.

## Reverse review: WBH-814E-E1SA-101 backplate

- Human authority classifies the expanded backplate INSERT as a table-routing container, not drawing metadata and not whole-region IGNORE. Populated plugin slots and their numbered terminal rows must produce terminal mappings; empty slot outlines remain structural.
- The source INSERT spans nearly the full page and contains `TEXT=278`, `LWPOLYLINE=261`, `LINE=98`, `HATCH=6`, plus one nested INSERT. Visible populated slots are 1, 2, 3, 6, and 7; slots 4, 5, and 8 are empty outlines in the reviewed state.
- The existing table extractor was already semantically correct on this source page: 56 table mappings were present before and after the V2 symbol-family fix. Therefore the repair must not rewrite table mapping logic; it classifies the outer INSERT as a structural table container, removes only its two spurious machine ports, and explicitly preserves nested table routing.
- Geometry-family evidence combines the dense table primitive census with complete row-grid coverage, multiple structured plugin headers, slot-number coverage, and backplate-scale aspect. Same-density layouts lacking either enough independent plugin headers or the near-complete 01..32 terminal grid remain unclassified.
- Held-out-in-practice same-family proof: `WBH-812E-E1SA-101` has a different fingerprint and smaller census (`TEXT=194`, `LWPOLYLINE=188`, `LINE=74`) but the same table topology. It matches the generalized family and preserves 27 plugin-terminal mappings, demonstrating the rule is not memorizing the reviewed WBH-814 definition.

## Reverse review: SYMB2_S_PWF4 GND

- Human authority: PWF4 is a GND ground glyph and contributes no ports, mappings, connectivity, bridge, network, or union.
- Its geometry differs from the earlier four-line/one-contact ground and six-line duplicated stepped marker: PWF4 has four LINEs, four LWPOLYLINEs (three open duplicated bars plus one closed bulged contact), bar proportions about `1.0/0.6/0.2`, and a contact lead attached at the longest bar midpoint.
- The accepted topology is orientation-free and scale-free. It binds each open polyline to exactly one coincident line bar, checks stepped centre spacing, and requires both lead-to-longest-bar and lead-to-contact attachment. Moving the contact away while preserving all primitive counts is a tested negative.

## Reverse review: SYMB2_M_PWF87 generic terminal

- Human authority: the slash-circle body with two round side contacts is a generic terminal. The instance label `JD11` is its terminal designator; left and right external line contacts are retained independently, with no internal connection or electrical union between them.
- Real definition evidence is `LINE=4`, `LWPOLYLINE=2`, `CIRCLE=1`: two equal closed bulged contacts lie symmetrically on an axis through the central circle, two short collinear leads point from those contacts toward the circle, and two collinear diagonal segments form the slash through the circle centre.
- Instance binding proves the generic-terminal interpretation without inventing conductivity: both world ports independently bind the same nearby designator `JD11`, but each has its own exact line handle and external network. The outer network IDs remain distinct, so no hidden left-to-right bridge is introduced.

## Reverse review: SYMB2_M_PWF104 CZ socket

- Human authority: E/L/N are three independent ports under outer instance `CZ`; complete identities are `CZ-E`, `CZ-L`, and `CZ-N`, with no internal connection among them.
- Source-network evidence resolves the mappings without guessing from screen direction: the left E network contains endpoint label `JD11`, the upper L network contains `JD2`, and the lower N network contains `JD7`. Thus the measured mappings are `CZ-E→JD11`, `CZ-L→JD2`, and `CZ-N→JD7`.
- Generalization uses the outer-circle/three-inner-circle topology, six contact positions, T-shaped radial outer-contact layout, and inward lead attachment. E/L/N roles are assigned from instance text rather than hardcoded top/bottom orientation, preserving mirrored/rotated applicability.

## Main review: SYMB2_M_PWF89 four-direction generic terminal

- Human authority: central slash-circle plus four round contacts is a generic terminal. `JD1/JD2/JD6` is the per-instance terminal identity; each externally wired direction binds independently, and no direction connects internally to another.
- Real definition evidence is `LINE=5`, `LWPOLYLINE=4`, `CIRCLE=1`: four equal contacts form a centred orthogonal cross around one larger circle, four radial leads bind contacts to the body, and one diagonal mechanism/slash line crosses the centre.
- This must be a second strict geometry rule under `labelled_terminal.generic.v1`, reusing PWF87's instance designator/evidence binding while allowing four independent ports. No external line means no emitted attachment on that side.
- Final matcher validates equal contact radii, contact/body radius ratio, two perpendicular axes, four one-to-one contact-to-body radial leads, and a centred diagonal whose endpoints are opposite and off both contact axes. It is rotation/scale invariant; shifted slash and skewed-contact same-count drawings are tested negatives.
- Fresh P001 replay emits 14 rows for 14 genuinely wired directions across six instances and emits no row for ten unwired directions. Eleven rows have unique JD names and are `MEASURED_TERMINAL_ATTACHMENT`; the three wired directions on the unnamed instance remain `TERMINAL_WIRE_ONLY_REVIEW` rather than borrowing another JD name.
- Observed instance names include `JD1/JD6/JD2/JD3/JD8`. Every emitted direction retains its own line/network evidence, while all rows keep `internal_connectivity_inferred=false` and `electrical_union_eligible=false`.

## Main review: SYMB2_S_PWF12a pending human semantics

- Live queue successor after PWF89 removal is cross-project `SYMB2_S_PWF12a`, fingerprint `b440ea59c6edcaa2edd135cbfd3ca4d54f80bb2ea554a9ec7af3eeba5a6be3d0`, eight instances in P001/P003.
- P001 provenance is nested handle `1D2D4` inside parent `SYMB2_M_PWF105[1D34C]` on `06 直流回路图.dwg`. The queue stores the parent insertion `(297.4886,109.9881)`; the selected lower nested state resolves to world insertion approximately `(297.4886,99.9881)`.
- The crop shows the lower numbered `2` row inside the `A'` enclosure, with a small left round contact, a larger right circle, and a short mechanism above. No port, mapping, IGNORE, or internal-connectivity meaning has been assigned before human adjudication.
- Human adjudication now confirms PWF12a is the row-level mechanism used by PWF105: the pair must inherit the enclosing/nearby `A'` identity and form `A'-1 -> upper same-side line` plus `A'-2 -> lower same-side line`. The two rows remain internally isolated and never union.
- Current-head replay proves the newly landed PWF105 parent model already emits the two correct parent mappings, but PWF12a still emits 12 duplicate/partial `MEASURED_EXTERNAL_ATTACHMENT`, `GEOMETRY_ONLY_REVIEW`, and `LABEL_ONLY_REVIEW` rows with no component identity. Integration must preserve the two parent mappings while making nested PWF12a row mechanisms evidence rather than independent duplicate ports.
- Implemented geometry family `component.external_row_contact.v1`: one line-bound axial contact is the only port; the main circle, HATCH and orthogonally offset contact are mechanism graphics. The strict rule validates entity composition, equal contact radii, 2:1 circle/contact radius, a joined collinear two-line axis, one inline contact and one orthogonally offset contact.
- Parent ownership is resolved from instance `nested_path` plus the parent instance fingerprint/family, not from PWF names. A child under `named-two-row-box-four-contact-v1` emits no duplicate row; standalone row instances still bind their nearby component name, numeric pin, exact line and network.
- The nested transform reader now uses the last cumulative matrix in an outer-to-inner chain. The previous first-item behavior placed every child at its parent origin and was the cause of cross-row child attachments.
- Fresh P001 result is exactly two parent `A'-1/A'-2` mappings, two unnamed parent attachment reviews for the other box, plus standalone `K-6` and `K-5` component mappings. Fresh P003 result is exactly two parent `A'-1/A'-2` mappings. No nested PWF12a duplicate survives and no row is union-eligible.

## Main review: LA38-11-209B-G pending human semantics

- After current-engine revalidation automatically removed stale PWF317, the first genuinely unknown live row is P001 `LA38-11-209B-G`, fingerprint `5b68b544d3f7834a0b52c64fa69de4c3a0a64ed859e6c95e11957707e1151eeb`, six instances.
- Representative source is `21 元件接线图1.dwg`, handle `27F43`, insertion `(65.0,102.49837)`. The block contains four equal circles labelled `11/12/13/14`, four small outer round contacts, three mechanism lines, and four text entities; current V2 is `UNKNOWN / REVIEW_ONLY` with three arbitrary free-extreme ports.
- Context shows device name `5FA` above. The lower external labels visible on the selected instance are `5FD3` at contact 13 and `5n115` at contact 14; contact 11/12 external semantics and the internal switch/contact relationships cannot be inferred safely from geometry alone.
- Rendered `.tmp/current_symbol_review/P001_LA38_27F43.png` for human adjudication. No family, IGNORE behavior, mapping, or contact-pair conductivity has been assigned.
- Human adjudication confirms the instance name is `5FA`; `11/12/13/14` are four mutually isolated ports and only map outward. Confirmed examples are `5FA-13 -> 5FD3` and `5FA-14 -> 5n115`; no contact pair may be unioned through the internal mechanism lines.
- Implemented `four-numbered-independent-contact-panel-v1` under `component.external_multi_port.v1`. The numbered-grid proposer now accepts any consecutive four/six labels and carries native `component_pin`; LA38's four outer contact centers replace the old three free extrema.
- Strict geometry validates aligned 2x2 circle/contact grids, equal radii and circle/contact ratio, one-to-one outward circle/contact pairing, consecutive labels, and the internal T-shaped three-line proportions/midpoint binding. The T is recognition evidence only and never topology authority.
- Instance-name selection for this family uses the ordered first-two/last-two port rows to derive the upward centre axis, preventing nearby external endpoints such as `5FD3/5n115` from being mistaken for the component name.
- Fresh P001 replay emits 24 rows across six instances. Representative `27F43` is exactly `5FA-13 -> 5FD3` and `5FA-14 -> 5n115`; `5FA-11/12` have no actual external line and remain label-only. No row is internally connected or union-eligible.

## Main review: SYMB2_M_PWF176 pending human semantics

- Live main successor is P001 `SYMB2_M_PWF176`, fingerprint `8ffdfeebc545ed07bf9b740146cf2c8c729557b453649d679f18248d228d308e`, six instances. Representative source is `08 差动保护及信号回路.dwg`, handle `233C5`, insertion `(85.07056,167.50439)`.
- Definition geometry is `9 LINE + 2` closed bulged contacts with two machine endpoints. Both world endpoints are real external attachments: port near `13` binds line `233CE / EN2-bbf...`; port near `14` binds `233CB / EN2-fac...`.
- Context identifies the instance as `1FA` and shows an open slanted contact plus a mechanically linked lower actuator. Geometry alone cannot authorize 13↔14 conductivity, conditional switch semantics, permanent isolation, or IGNORE, so V2 remains `UNKNOWN / REVIEW_ONLY` pending human adjudication.
- Rendered `.tmp/current_symbol_review/P001_PWF176_233C5.png`; no engine family or internal connectivity has been assigned.

## Main review: SYMB2_M_PWF176 human ruling and geometry model

- Human ruling: `1FA-13` and `1FA-14` are permanently isolated. Each remains an outward component mapping port; the open blade and lower mechanical actuator never create body conductivity or electrical union. Confirmed relation: `1FA-13 -> 1QD3`.
- Definition geometry is exactly `9 LINE + 2` equal closed bulged contacts. The two opposed contacts are separated by `22.5` contact radii; two inward axial leads, one open oblique blade, and a six-line centered actuator form the complete rotation/scale-invariant topology.
- Implemented `component.external_strip_two_port.v1 / two-contact-mechanical-actuator-v1` with dedicated contact-center ports. An unseen `37°/1.8x` definition matches; shifting one actuator stroke leaves the exact counts unchanged but is rejected from the family.
- Full P001 replay finds all six real placements and emits 12 independent `MEASURED_COMPONENT_PORT_MAPPING` rows. Instance names are `1FA`, `1-2FA`, `3-2FA`, `5FA`, `1-4FA`, and `3-4FA`; each contributes only `-13/-14` outward rows. Representative `1FA-13` binds `1QD3 / 233CE / EN2-df468...`; `1FA-14` binds `233CB / EN2-0809...` without inventing an endpoint label.

## Main review: A$C5C9C7C64 pending human semantics

- Refreshed live head is P001 `A$C5C9C7C64`, fingerprint `346f8b01c9cf292256cf0fecbd3c680e5e79471cfe21420fb1a2d311ed20007e`, four instances. Representative is `04 交流回路图1.dwg`, handle `112A6`, insertion `(40.0,220.0)`.
- Current V2 remains genuinely `UNKNOWN / REVIEW_ONLY` with three arbitrary free-extreme ports. Definition geometry is `4 INSERT + 8 LINE + 3` closed bulged contacts: three nested PWF208 row mechanisms, three left-side contacts, a shared left vertical rail, three right leads, a bottom common line, and a nested PWF318 ground symbol.
- Source context labels the assembly `LVS CB`; its three rows continue toward `1ID7 / 1ID8 / 1ID9`. No whole-component IGNORE, row mapping, common-rail conductivity, or internal connectivity has been assigned before human review.
- Human ruling: ignore the complete red-box LVS-CB assembly. The three nested row mechanisms, three contacts, shared left rail, bottom line, nested ground graphic, and every visible lead produce zero component mapping, zero external attachment semantics, zero internal connectivity, and zero electrical union.
- Generalization must recognize the complete parent geometry and nested child geometry signatures. Exact fingerprint suppression alone is insufficient; a renamed/rotated/scaled equivalent must remain zero-port IGNORE while a displaced child or broken row/spine topology stays in review.
- Implemented `electrical.nonconnective_grounded_three_row_cb_panel_ignored.v1 / grounded-three-row-repeated-mechanism-panel-v1`. The parent matcher verifies `4 INSERT + 8 LINE + 3` round contacts, a `130r` shared spine, four `40r`-pitch rows, repeated `40r + 20r` split leads, one `90r` bottom line, three child signatures `{2 ARC,3 LINE,2 LWPOLYLINE}`, and one `{4 LINE,1 LWPOLYLINE}` ground child at the required offset/relative rotation.
- Nested INSERT evidence is now exported as normalized placement, rotation, scale, and child entity histogram. It contains no child block name and remains stable under parent rename, arbitrary rotation, and uniform scale.
- Fresh two-page replay covers all four real instances (`112A6`, `114FB`, `21681`, `21799`). Both per-file definitions persist as `HUMAN_ADJUDICATED_NON_CONNECTIVE / HUMAN_CONFIRMED_MEMBER / IGNORE`, ports are empty, all emission/attachment/connectivity/union flags are false, and instance candidate count is zero.

## Main review: A$C6A636705 pending human semantics

- Refreshed live head is P001 `A$C6A636705`, fingerprint `2c4f73274833c1b08e7320666b993c4bd5d3e1eedc7a3931b4075e334b8ec1f7`, four instances. Representative is `07 网络通讯回路图.dwg`, handle `1C298`, insertion `(345.0,270.0)`.
- Current code still reports `UNKNOWN / REVIEW_ONLY` with two draft extrema. Definition geometry is exactly `2 ARC + 2 LINE`: equal upper/lower semicircles joined by two parallel vertical sides, forming a narrow closed capsule around the B+/B- routes.
- Source context places the capsule between left terminals `TD1/TD4`, right WBH-812E device terminals `601/602`, and a separate `Shielding layer` route. No B+↔B- connectivity, shield mapping, whole-symbol IGNORE, or other behavior has been assigned before human review.
- Human ruling: the closed capsule is whole-symbol IGNORE. It must neither bridge nor interrupt the two modelspace conductors: B+ and B- continue independently, never connect to one another, and never map to `Shielding layer`. Confirmed B+ route remains `TD1 -> 1n601`.
- The geometry family must match the complete closed stadium: two equal 180-degree arcs bowing outward in opposite directions, joined by two equal parallel sides at both arc endpoints. A same-count open/misaligned arc-line arrangement must remain review.
- Implemented `non_electrical.cable_sleeve_ignored.v1 / closed-opposed-semicircle-cable-sleeve-v1`. Arc features now include a normalized arc midpoint, allowing the matcher to prove that the two semicircles bow outward in opposite directions rather than accepting a same-count S/open arrangement.
- Fresh page-07 replay finds all four instances (`1C298`, `1C2AB`, `1C2BB`, `1C2CB`), persists one zero-port `HUMAN_ADJUDICATED_NON_CONNECTIVE / IGNORE` definition, and emits zero capsule candidates.
- Underlying source lines remain ordinary modelspace conductors: B+ handle `1C28E` belongs only to `EN2-280c...`; B- handle `1C28F` belongs only to distinct `EN2-26a8...`. The existing semantic pair remains `TD1 -> 601` at confidence `0.9233`; the nearby `1n` device scope yields the human-confirmed full endpoint `1n601`. No shielding-layer relation is generated.

## 2026-07-15 midpoint adjudication: Ld_DzbJD_Right

- Human adjudication for fingerprint `08a272799dbac4bf36f36ebcc1091f94b2273cf27fce8741a3cf31b150d5d123`: the symbol has no connectivity and no external mapping; it must suppress every proposed port under a geometry-generalized IGNORE model.
- Representative provenance: P001 `27 右侧端子图2.dwg`, handle `2AF3`, insertion approximately `(115.000001674681, 157.5)`; the same definition also occurs in P003.
- Current defect: V2 reports `UNKNOWN / REVIEW_ONLY` and proposes one false port. The implementation must recognize the compact six-line/three-polyline step-like right-side marker by normalized geometry rather than by fingerprint alone, while preserving raw CAD provenance.
- Real topology is more specific than the primitive counts: three open two-point LWPOLYLINE segments exactly duplicate three parallel LINE bars with relative lengths `1.0/0.6/0.2`; all bar centres share one perpendicular axis. A doubled perpendicular stem joins the longest bar centre to a parallel side lead of relative length `0.5`.
- Implemented family `electrical.nonconnective_dzb_right_marker_ignored.v1` using relative segment coincidence, directions, length ratios and endpoint binding. A 37°/2.4× unseen-fingerprint variant matches; a same-count variant with one offset duplicate remains unsuppressed.
- Direct real-block validation succeeds for exact and unseen fingerprints with zero ports. Fresh single-page `analyze-project` persists `HUMAN_ADJUDICATED_NON_CONNECTIVE / IGNORE`, zero external attachment, zero internal connectivity/union, and no network-candidate row for the definition.
- Regression gates pass: symbol proposal `58 passed`; analyze-project integration `21 passed`.

## 2026-07-15 midpoint adjudication: A$C26C55624

- Human adjudication: the three-lead boxed graphic is internally disconnected and has no mapping meaning; suppress every proposed port and electrical relation.
- Representative provenance: P001 `14 高操作回路图.dwg`, handle `276B6`, insertion `(249.9986338,134.9945)`, fingerprint `4f4abeddea8e309da9df83614ee3def2228b9e72a1f9a6e788b270ab13ec8fa1`.
- Implemented `electrical.nonconnective_three_lead_box_ignored.v1` using two nested rectangle edge ratios/centre spacing, the small rectangle's opposite-corner diagonal, and three equal parallel leads attached to opposite body sides in a `2:1` distribution. No name, coordinate, or fingerprint is used by the geometry matcher.
- Arbitrary 41°/2.2× unseen-fingerprint geometry matches. A same-count variant with one detached lead remains unsuppressed. The rotation test also proved free-endpoint draft count can change `2 -> 3`, so the family accepts either count only as a prefilter and relies on full topology for authority.
- Fresh source-page replay persists the exact member as `HUMAN_ADJUDICATED_NON_CONNECTIVE / IGNORE`, zero ports and zero network candidates. Direct real-block replay under an unseen fingerprint emits `MATCHED / GEOMETRY_FAMILY_NON_CONNECTIVE`, also with zero ports.
- Regression gates pass: symbol proposal `61 passed`; analyze-project integration `21 passed`.

## 2026-07-15 midpoint adjudication: SYMB2_M_PWF103

- Human adjudication: this is a two-port external-mapping component. `AK-1` maps only to the left external line and `AK-2` maps only to the right external line; ports 1 and 2 are internally disconnected and must never union through the body.
- Representative provenance: P001 `06 直流回路图.dwg`, handle `1D348`, insertion `(252.5562897,109.9881375)`, fingerprint `eec06b5aa9987f50b15e7871e0545c46d26b47ec64abdf9ff796d67c2e328bee`; P003 has a second instance.
- Current V2 already locates both exact line attachments and local port numbers `1/2`, but only emits `MEASURED_EXTERNAL_ATTACHMENT`; `component_designator`, `component_port_identity`, and component mapping fields are null. The implementation must promote the strict definition geometry and bind nearby instance name `AK` into `AK-1/AK-2` without inferring any body-internal connectivity.
- Implemented strict `four-contact-two-circle-named-strip-v1`: four equal collinear contacts with `5:30:5` gap ratios, two equal circles concentric with the inner contacts at 3× contact radius, four axial lines, two equal crossing mechanism lines, and one longer diagonal. Geometry is rotation/scale invariant and a displaced-circle same-count negative remains unpromoted.
- Added `normalized_circles` and a compatibility-preserving `chord_radius` for two-point bulged contacts. Legacy bbox-derived `radius` remains unchanged for existing families; the new strip rule uses chord radius to avoid arbitrary-rotation shrinkage.
- Instance binding now accepts 2–5-letter names only for this strict family, centres the name search on the two world ports, forms `AK-1/AK-2`, and emits `MEASURED_COMPONENT_PORT_MAPPING / COMPONENT_PORT_TO_EXTERNAL_NETWORK` with side and network evidence.
- Final P001 replay: `AK-1` maps left through line handle `1D37A` to network `EN2-7865...`; `AK-2` maps right through `1D353` to `EN2-d1d...`. Both retain `internal_connectivity_inferred=false` and `electrical_union_eligible=false`. Unseen real fingerprint remains `MATCHED / EXTERNAL_PORTS_ONLY` with two ports.
- Regression gates pass: symbol proposal `68 passed`; analyze-project integration `21 passed`.

## 2026-07-15 midpoint adjudication: A$C08415381

- Human adjudication: the complete `HVS CB` repeated-coil panel has no mapping meaning and must be ignored as one non-connective graphic.
- Representative provenance: P001 `05 交流回路图2.dwg`, handle `216BC`, insertion `(37.5,149.9999997)`, fingerprint `59cf96d51fc55afa4f77a383e0ecf990270dbafbbcd454943b3473039f1a9e5b`; two instances occur in P001.
- Baseline V2 is `UNKNOWN / REVIEW_ONLY` and retains only three arbitrary free-end extremes despite real geometry containing 12 equal semicircular arcs, 26 lines, and four duplicate contact polylines.
- Implemented `electrical.nonconnective_repeated_coil_panel_ignored.v1` using a rotation/scale-invariant 2×6 equal-semicircle grid, `25 parallel + 1 perpendicular spine` line topology, and two duplicated contact loci attached to the spine. A same-count offset-arc negative stays outside the family.
- Direct real-block validation succeeds for exact and unseen fingerprints with zero ports. Fresh P001 page replay persists `HUMAN_ADJUDICATED_NON_CONNECTIVE / IGNORE`, zero external attachment/connectivity/union, and zero symbol network candidates.
- Regression gates pass: symbol proposal `73 passed`; analyze-project integration `21 passed`.

## 2026-07-15 midpoint adjudication: SYMB2_M_PWF105

- Human adjudication: form two independent mappings, `A'-1 -> upper same-side line` and `A'-2 -> lower same-side line`. Internal connectivity was not confirmed, so the safe behavior remains no internal connectivity and no union.
- Final clarification confirms that the mapping direction is defined by row position: port `1` follows the upper same-side conductor and port `2` follows the lower same-side conductor. It does not grant any row-to-row conductivity.
- Representative provenance: P001 `06 直流回路图.dwg`, handle `1D34C`, insertion `(297.4885578,109.9881378)`, fingerprint `55c2e04f990b264e93b235f7ed3c078a6034a853b3201192f447e7b346d8f06d`; P003 has the same definition.

## 2026-07-15 midpoint review: SYMB2_M_PWF270 pending human semantics

- Current queue midpoint is P003 `SYMB2_M_PWF270`, fingerprint `c983989529487b8e3894fc9dfc0d0acab9c04fe6a66161f36b695e5c80571396`, representative `05 信号回路图.dwg` handle `A22C` at `(647.5,513.125)`.
- Current V2 assigns only generic `component.external_multi_port.v1 / repeated-external-port-geometry-v1 / REVIEW_REQUIRED`. Its four free-endpoint ports are all `UNRESOLVED` and do not touch external lines, so no semantics are accepted.
- The highlighted INSERT is a long two-row repeated graphic beside `GXTX18`, with two parallel vertical strokes after the 270-degree instance transform. The definition contains `10 LINE + 6 LWPOLYLINE + 2 CIRCLE + 8 HATCH`; machine-selected local points `(10.005/48.755, 0/-7.5)` are visual extrema rather than proven terminals. Await human port/mapping/IGNORE/internal-connectivity adjudication.
- Human adjudication: all four machine candidates fail to touch an external line and the complete component has no mapping meaning. Classify the whole geometry as IGNORE with zero ports, zero external attachments, zero internal connectivity, and zero electrical union.

## 2026-07-15 midpoint review: SYMB2_M_PWF31 pending human semantics

- Current live midpoint after PWF11a auto-resolution is P001 `SYMB2_M_PWF31`, fingerprint `8f7479379424184442b346891c2040fe047a8756561435f42095f4e088b39cf1`, representative `06 直流回路图.dwg` handle `1D34F` at insertion `(339.9900961,99.9881378)`.
- Current V2 remains `UNKNOWN / REVIEW_ONLY` and proposes two geometric endpoints. Both are real line contacts: the lower world point binds line `1D352 / EN2-383b...`, and the upper point binds `1D351 / EN2-3883...`; both remain `GEOMETRY_ONLY_REVIEW`, with no component identity and no internal connectivity/union inferred.
- The highlighted source crop shows a vertical two-contact body crossing the `AC230V L/N` parallel conductors, with an X-shaped internal mark and nearby `A` text. Definition geometry is `2 LINE + 5 LWPOLYLINE`: two end contacts and leads, two open diagonals, and one open bulged central path. Human adjudication is required to decide whether the two external contacts are independent, internally conductive, or the whole switch/marker is IGNORE.
- Human adjudication: the complete X-marked component is IGNORE and its two visible contacts are internally disconnected. Suppress both external attachments as component semantics and never union the AC230V L/N conductors through this graphic.

## 2026-07-15 midpoint review: DGICOM4000-4GX24GE-HV-HV pending human semantics

- Current refreshed midpoint is P003 `DGICOM4000-4GX24GE-HV-HV`, fingerprint `9ab7144823696cf159b562ccd4a64c5801bdf99275c605494d4964302cc04bd1`, representative `09 交换机接线图1.dwg` handle `3B840` at `(220.5111363,170.9591146)`; four instances are queued.
- Current V2 incorrectly reduces the full equipment panel to generic `component.external_strip_two_port.v1 / elongated-round-end-two-port-v1 / REVIEW_REQUIRED`. Its two extrema are both `UNRESOLVED` with no external line/network contact.
- The red-box source crop is a complete DGICOM4000 switch panel containing 24 GE/P sockets, four GX optical pairs, Console, FAULT, dual PWR and GND graphics. Definition census is `24 ARC + 8 CIRCLE + 54 HATCH + 3 INSERT + 88 LINE + 138 LWPOLYLINE + 78 TEXT`; machine extrema at local `(-175.0431,-58.6592)` and `(175,-50)` are not proven ports. Human adjudication is required on whether the entire equipment graphic is IGNORE or any native connector mapping should survive.
- Human adjudication: the complete DGICOM4000 switch panel is IGNORE. None of the GE/P, GX, Console, FAULT, PWR or GND graphics creates a communication or electrical mapping, external attachment, internal connectivity, or union.
- Implemented `wide-ge-gx-power-switch-panel-v1` under `communication.equipment_panel_ignored.v1`. The strict geometry path combines complete P1..24/GE1..24/GX25..28/T-R/Console/FAULT/PWR labels, 25 square cells, eight equal collinear circles with alternating `3.36r/4.84r` pitch, at least 40 closed bulged outlines, narrow entity census, and `3.8..4.6` oriented aspect. A real-block unseen fingerprint still matches; missing GE24 or one circle shifted off-axis does not.

## 2026-07-15 midpoint review: SYMB2_S_PWF24a pending human semantics

- Refreshed midpoint after stale-row cleanup is P003 `SYMB2_S_PWF24a`, fingerprint `a662de3d914d6b22aa1b0d6f9e4a0a090de1e0cd8461224860fc8199cba2bf0f`, representative `06 交换机回路图1.dwg` handle `119F7` at `(287.3410777,85.0)`; two instances are queued.
- Fresh V2 remains `UNKNOWN / REVIEW_ONLY` with three free-extreme candidates at local `(0,0)`, `(1,2.5)`, and `(-1,2.5)`. The red-box source crop shows a vertical lead from an ETHER/NET panel through a small lower circle to a larger upper circle with a horizontal bar, near label `4-40nP24`; human semantics are required before engine changes.
- Human adjudication: ignore the complete PWF24a graphic. Implemented `electrical.nonconnective_circle_contact_marker_ignored.v1 / diameter-circle-offset-contact-marker-v1` over the exact barred-circle/radial-line/small-contact geometry. The real block and an unseen fingerprint are zero-port IGNORE; a rotated/scaled complete member matches while a laterally shifted small contact does not.

## 2026-07-15 midpoint review: A$C38910F98 pending human semantics

- Refreshed midpoint is P001 `A$C38910F98`, fingerprint `cd0346ad16ba285a9950c48c0611017efcd9490cc6d6d78c81442860902a75cf`, representative `11 非电量开入回路.dwg` handle `2CF8F` at `(160.0,250.0)`; one instance is queued.
- Fresh V2 is `UNKNOWN / REVIEW_ONLY`, proposing the two endpoints of a single local 50-unit straight line. Source context shows the line spanning horizontally from the left `132` route to the right `216`/vertical route inside the WBH-814E panel. Human evidence is required on whether it is a conductive wire primitive, a non-connective graphical span, or an ignorable container artifact.
- Human adjudication: ignore the whole horizontal span and keep its sides disconnected. Corpus audit found exactly one target instance and only two single-LINE block definitions across current P001/P003 artifacts; the other is vertical `A$C72EB63F1`. Because local geometry cannot distinguish these safely from valid wire, implementation is intentionally exact-fingerprint only under `non_electrical.panel_internal_line.v1`.
- Real replay proves target zero ports/candidates while the vertical single-line neighbor remains `UNKNOWN / REVIEW_ONLY`. The target nested LINE exists only in `primitive_segments`, not normal `lines.parquet` or wire networks, so exact port suppression cannot bridge the left/right networks.

## 2026-07-15 midpoint review: A$C72EB63F1 pending human semantics

- After exact horizontal-line cleanup, the live midpoint is the only other single-LINE block: P001 `A$C72EB63F1`, fingerprint `ae788d00fab7abcd6190c917d8f4c42e8613320b78143443b3849d7e9aea6e72`, `11 非电量开入回路.dwg` handle `2CF90` at `(210.0,70.0)`; one instance.
- Current V2 correctly remains `UNKNOWN / REVIEW_ONLY` with local endpoints `(0,0)` and `(0,180)`. Source context shows the vertical span along the right side of many horizontal device routes inside the WBH panel and adjacent to other vertical framework/bus lines. Human evidence is required on whether this span is an ignored panel framework line or a conductive common bus.
- Human adjudication distinguishes physical truth from audit scope: the line is physically a common bus, but current validation does not inspect its branch connections, so V2 must whole-region IGNORE it and connect neither its ends nor intersecting horizontal routes. Implemented exact-only `non_electrical.panel_internal_bus_excluded.v1`; an unseen same-geometry vertical line remains review.
- Fresh replay persists target zero ports/candidates and leaves the previously exact horizontal exclusion intact. This avoids introducing any broad single-line or vertical-bus suppression rule.
- Baseline V2 proposes the outer rectangle's top/bottom corners rather than the two real row contacts, so neither port attaches to a line or local number. The definition contains an outer rectangle, four round contact polylines, and two repeated nested mechanism inserts at row offsets 0/-10. A family-specific row-port proposer is required before instance-name binding.
- Reverse review `SYMB2_M_PWF102` (`KZKK`): human authority confirms four mutually isolated ports. Each port maps only to the external route attached on its own side; never infer conductivity through the drawn internal switch mechanism.
- Confirmed endpoint identities are `KZKK-1 -> JD8`, `KZKK-3 -> JD3`, while source-DWG topology shows the right upper/lower routes terminate at adjacent component pins `CD-WSK-H-J-G-6` and `CD-WSK-H-J-G-5`, yielding `KZKK-4 -> CD-WSK-H-J-G-6` and `KZKK-2 -> CD-WSK-H-J-G-5`.
- The generalized family is anchored on the complete four-port geometry: four outer round contacts and four concentric inner contacts forming aligned 2x2 grids, equal contact radii, four equal circles at the inner grid, a 3:1 circle/contact radius ratio, and the exact mechanism primitive census. Fingerprint remains provenance only.
- Reverse P003 review `A$C1D4D7376`: human authority is whole-component electrical IGNORE. The vertical source-page placement must emit no ports, external mappings, internal connectivity, or union.
- Representative provenance is P003 `07 交换机回路图.dwg`, handle `11F63`, insertion `(361.3088299, 242.5)`, fingerprint `ea02de2d3b540c5240d289e863160289db7a720c8b7c9db2efbc52c321e45df6`; one instance occurs in the current P003 project.
- Definition geometry is exactly `6 LINE + 1 CIRCLE + 2 HATCH`: one dominant line passes through the circle centre, four short joined mechanism strokes remain inside the circle-scale body, and one detached oblique marker is centred on the dominant axis at a fixed radius-normalized offset. This complete relative topology, not the anonymous block name or fingerprint, is the generalization boundary.
- Reverse P003 `DGICOM3000-2GX8GE-HV`: human authority is whole-device-region IGNORE. Power terminals, Console, GE1..GE8, GX9/GX10 and paired 1G/2G optical graphics are panel artwork for this audit and produce no communication/electrical mappings.
- Representative is P003 `11 元件接线图4.dwg`, handle `2C64D`, insertion `(152.5,250.0)`, fingerprint `cb1abae65b4bcbd19aa91077fe008419f016357d08608f3712496374f8b8d325`; a second instance is handle `2C70B`.
- This compact DGICOM panel differs from the independently adjudicated wide DGICOM4000 subtype but belongs to the same `communication.equipment_panel_ignored.v1` behavior family. Its complete geometry is `12 ARC + 4 CIRCLE + 18 HATCH + 1 INSERT + 60 LINE + 52 LWPOLYLINE + 32 TEXT`, with an 8-socket GE matrix, paired optical-circle grid and native power/Console/GE/GX labels.
- Reverse P003 `HYKL-X12-02`: human authority is whole-panel IGNORE. Both IN/OUT rows and every PE/GND/TX/RX label/contact are non-mapping equipment-face artwork.
- Representative is P003 `08 元件接线图1.dwg`, handle `295B7`, insertion `(234.6209764,74.35743)`, fingerprint `1726acf417090ce3ecbf6454bdb8321afb7c0025023b98e82d59a6b1476dd6dd`; the second instance is handle `295E4`.
- Complete geometry is `8 CIRCLE + 9` closed bulged `LWPOLYLINE + 16 TEXT + 1 MTEXT`: eight equal circles form a rotation-invariant 4x2 grid, eight equal small round contacts sit one circle radius outward from those circles, and one enclosing rounded body plus required PE1/PE2/GND/TX/RX/IN/OUT labels establishes the panel boundary.
- Reverse P003 `KK1P`: human authority confirms a generic two-port component with no internal connectivity. The enclosing instance name combines with native pins `1/2`; representative mappings are `AK-1 -> JD1` and `AK-2 -> A'-1`.
- Representative P003 `08 元件接线图1.dwg` handle `26AAC` is inserted at `(298.2909303,248.6735649)`, fingerprint `9321616869d2ccca1d1d6fc065a9a995ddf9d31ac8e207430b8eec6439e8ad6b`; second instance `26AC1` uses component name `A'`.
- Definition geometry is `6 LINE + 2` closed round `LWPOLYLINE + 2 TEXT`: a 1:2 rectangle, two full-width internal dividers, two equal round contacts at opposite outer-edge midpoints, and native pin labels `1/2`. Current free-extreme proposal is wrong because it emits four rectangle corners; the family-specific proposer must emit only the top/bottom contact centres.
- Existing component-diagram evidence already proves the representative pair contract: `AK-1 -> JD1` and `AK-2 -> A'-1`; the second instance includes reciprocal/cascaded mappings such as `A'-1 -> AK-2`. Symbol-port V2 should consume those measured component pairs while preserving no-union.
- Phase 148 stale-head audit replays the current `KK1P` geometry across P001 handles `280CB/280E0` and P003 handles `3B5CA/3B5DF`. Both definitions match `component.external_strip_two_port.v1 / vertical-numbered-two-port-box-v1`, each instance emits exactly pins `1/2` at the upper/lower contact centres, and all eight candidate rows are `MEASURED_COMPONENT_PORT_MAPPING` with `internal_connectivity_inferred=false` and `electrical_union_eligible=false`. This queue row requires no new human adjudication.

## 2026-07-15 main review: SYMB2_M_PWF182 pending human semantics

- Fresh replay source: P001 `14 高操作回路图.dwg`, representative handle `27718`, insertion `(82.4986339,57.4945)`, fingerprint `de637c582be8e821b1cead5224227ebf5bbfc30d10f68ca7a36f9d20a3295526`; the same definition also occurs at handle `27719` on the lower parallel route.
- Current V2 remains `UNKNOWN / REVIEW_ONLY`. It proposes the four endpoints of the two diagonal strokes as `MP1..MP4`; all eight candidates across the two instances are `UNRESOLVED`, touch no external line, and retain `internal_connectivity_inferred=false` plus `electrical_union_eligible=false`.
- Complete block geometry is `2 LINE + 1 CIRCLE + 2 closed invisible LWPOLYLINE`: two diagonals form an X inside the circle, while the two invisible closed polylines coincide with the left/right inline contact areas. Source context labels the upper instance `LD` and the lower instance `HD`, each placed directly on a horizontal route. Human authority is required on whole-symbol IGNORE versus left/right external mapping and any internal conductivity.
- Human adjudication: classify the complete PWF182 crossed-circle inline graphic as whole-symbol IGNORE. The left and right sides are internally disconnected; emit no ports or mappings and never union the two surrounding routes through this block. Generalization must use the complete circle/X/two-side-contact geometry rather than the exact fingerprint.
- PWF182 completion: implemented `electrical.nonconnective_crossed_circle_marker_ignored.v1 / crossed-circle-opposed-contact-regions-v1`. The matcher verifies two orthogonal circle diameters and the opposed equal side-contact regions using normalized radii, distances, and dot products; exact, unseen-fingerprint, and rotated/scaled positives suppress all ports while an offset-contact negative remains review. Dedicated fresh replay proves handles `27718/27719` are `IGNORE / ports=[]` with zero candidates, topology applications, semantic relations, network members, connectivity, or union.

## 2026-07-15 main review: SYMB2_M_PWF192 pending human semantics

- Fresh replay source: P001 `16 高低压侧操作箱信号回路.dwg`, representative handle `202A3`, insertion `(109.9963662,232.5055)`, fingerprint `994da514414fa6239674d36dfc616a87430a5dafbab56f009f77b04469580830`; four instances are present (`202A3/202D4/20325/20356`).
- Current V2 remains `UNKNOWN / REVIEW_ONLY`. It proposes local endpoints `(0,0)` and `(11.25,0)` as two ports; all eight instance-port rows touch distinct real lines/networks and remain `GEOMETRY_ONLY_REVIEW`, with no inferred internal connectivity or electrical union.
- Complete definition geometry is `7 LINE + 2 closed invisible LWPOLYLINE`: left/right inline leads and two contact areas, an oblique open-switch blade, plus a vertical/triangular actuator marker above the blade. The representative appears on the `保护跳闸 / Prot. trip` route beside terminal `220`; sibling instances are used for latch trip, latch close, and related signals. Human authority is required on whole-symbol IGNORE versus two external mappings and whether left/right are ever conductive.
- Human adjudication: classify the complete PWF192 actuated open-switch graphic as whole-symbol IGNORE. Its left/right sides are internally disconnected; emit no ports or mappings and never union the two surrounding signal routes. The implementation must generalize from the complete lead/contact/blade/actuator geometry rather than the exact fingerprint.
- PWF192 completion: implemented `electrical.nonconnective_actuated_open_switch_ignored.v1 / two-contact-actuated-open-switch-v1`. Two equal contact regions establish a local frame and scale; the complete seven-line multiset verifies both leads, the open blade, duplicated actuator strut, crossbar, and vertical rod under rotation/reflection/uniform scale. Unseen and transformed positives match; displaced blade/actuator negatives remain review. Dedicated replay proves all four real instances are `IGNORE / ports=[]`, zero candidates, and no connectivity/union-related artifacts.

## 2026-07-15 main review: SYMB2_S_PWF10 pending human semantics

- Source: P001 `14 高操作回路图.dwg`, representative handle `275F5`, insertion `(355.9986338,192.4945006)`, rotation approximately `180°`, fingerprint `25548c2e6081ebe78ea8777dd91b07d6d3f4114392d2c3dcebf79cb16b454f53`; sibling handle `275F7` appears on the lower parallel row.
- Current V2 remains `UNKNOWN / REVIEW_ONLY`. It proposes two local extrema; per instance only one touches the incoming horizontal line while the other is unresolved, and no internal connectivity or union is inferred.
- Complete definition contains only two LWPOLYLINE entities: one visible open line/contact/semicircular motif and one invisible closed contact area. In source context the upper/lower instances sit immediately before the QF/KO switch symbols. Human evidence is required on whole-symbol IGNORE versus a meaningful inline port or internal connection.
- Human adjudication: PWF10 is whole-symbol IGNORE with no port, mapping, or connectivity meaning. The accepted solution must recognize the complete visible two-contact/semicircular polyline plus its closed contact-area geometry under rotation and uniform scale; exact fingerprint matching alone is explicitly prohibited. Completion requires a dedicated original-page replay proving both real instances are zero-port/no-mapping/no-union, followed by queue-row and temporary-artifact cleanup before the next review item.
- PWF10 completion: implemented `electrical.nonconnective_wide_contact_cap_marker_ignored.v1 / straight-wide-two-contact-cap-marker-v1`. The matcher consumes newly persisted open-LWPOLYLINE vertex, width, bulge, and visibility features plus the closed invisible contact region; relative projections, width ratios, and endpoint spacing provide rotation/uniform-scale generalization. Exact, unseen, and transformed positives suppress all ports while close geometry negatives remain review. Dedicated replay proves `275F5/275F7` are `IGNORE / ports=[]`, zero candidates, and no topology/semantic/network or union output.

## 2026-07-15 FEIDIAO stale-queue validation

- Fresh P001 `21 元件接线图1.dwg` replay shows `FEIDIAO-10A-Z-3-AC30` is already generalized by `component.external_multi_port.v1 / three-contact-labelled-socket-v1`. It emits exactly `SOCKET:E/L/N` at the three radial contacts; all three are `MEASURED_COMPONENT_PORT_MAPPING`, bind designator `CZ`, and keep internal connectivity/union disabled.
- This is the already adjudicated CZ socket family rather than a new symbol. Existing tests cover renamed/unseen fingerprints and a `27°/1.6×` transformed rounded-panel member, and the canonical measured mappings are `CZ-E→JD11`, `CZ-L→JD2`, `CZ-N→JD7`. No new human annotation or fingerprint-specific rule is required.

## 2026-07-15 fresh census: SYMB2_S_PWF314 circled-ground variant

- Full current-code census reduces substantive unresolved geometry to five unique definitions. Queue leader PWF314 occurs across P001/P003 with ten real placements on backplate/equipment-panel pages.
- Complete local geometry is `4 LINE + 1 CIRCLE + 1` closed bulged contact region: three centered horizontal bars decrease in length and step vertically, one perpendicular lead joins the longest bar to a small top contact, and a larger enclosing circle surrounds the ground motif. Current generic extrema create four false review ports, several touching nested panel geometry.
- This is visually and geometrically a ground symbol, and prior human authority already states ground symbols create no mappings or connectivity and belong in the IGNORE model. Treat it as a new strict geometry subtype under the ground-symbol family rather than requesting duplicate semantic adjudication or adding fingerprint-only suppression.
- PWF314 completion: added `electrical.ground_symbol_ignored.v1 / circled-stepped-bar-ground-contact-v1`. Relative bar ratios/spacing, perpendicular lead binding, contact centre, and outer-circle containment provide rotation/reflection/uniform-scale matching; exact, unseen, transformed, and reflected positives match while an offset outer circle remains review. Eight-page fresh replay yields eight zero-port proposals covering twelve persisted placements (the duplicated parent-panel expansions on P003 09/10 explain the two extra rows), zero candidates and zero topology/semantic/network artifacts.

## 2026-07-15 ignored-parent inheritance gap

- Fresh queue items `A$C08084C19` and `A$C7E971F70` occur only as direct children of `DGICOM4000-4GX24GE-HV-HV` instances on P003 09/10. Every parent is already `communication.equipment_panel_ignored.v1 / wide-ge-gx-power-switch-panel-v1 / HUMAN_CONFIRMED_MEMBER / IGNORE` under the user's whole-panel authority.
- V2 currently still emits `GEOMETRY_ONLY_REVIEW` child candidates attached to the ignored parent's virtual lines. This is a containment-policy defect, not missing child semantics. The general fix is ancestor-aware candidate suppression for whole-symbol IGNORE, while explicitly preserving TABLE_CONTAINER and other non-IGNORE ancestor behavior.
- Completion: candidate binding now traverses every ancestor path and classifies/evaluates the ancestor proposal. Only an ancestor with `behavior_mode=IGNORE` and `suppressed_by_policy=true` suppresses descendants; TABLE_CONTAINER, EXTERNAL_PORTS_ONLY, TERMINAL_NO_INTERNAL, and ordinary ancestors retain children. P003 09/10 replay keeps both DGICOM parents as zero-port IGNORE and reduces all eight A$C080/A$C7E child placements to zero candidates/topology/semantic/network artifacts without child fingerprint rules.

## 2026-07-16 main review: A$C1DEA74F8 pending human semantics

- Fresh census source: P001 `21 元件接线图1.dwg`, nested handle `27268`, world `(143.75,40.0)`, fingerprint `0b72b0b02116d00c0a8c196e1b45c6d693450315f37e77ba636c0a03065f3785`; one instance occurs inside the CD-WSK panel.
- Current V2 assigns `switch.open.candidate.v1 / elongated-gap-two-port-candidate-v1 / REVIEW_ONLY`, proposing vertical endpoints `(143.75,35)` and `(143.75,40)`. Both touch separate virtual lines inside the CD-WSK body, but no connectivity or union is inferred.
- Complete block is `12 LINE + 1 closed LWPOLYLINE`: a narrow vertical rectangular element with four repeated diagonal/zigzag cells and short leads at top/bottom. Source context places it between the `SHARED/LOAD` artwork and parent rows 3/4. Human evidence is required on whole-element IGNORE versus two external/internal component ports and whether top/bottom are conductive.
- Human adjudication now resolves the complete element as whole-symbol IGNORE: the top and bottom are not ports, create no mappings, have no internal connectivity, and must never participate in electrical union. The implementation must generalize from the complete narrow-frame/repeated-zigzag/lead geometry; the fingerprint remains provenance only.
- Measured geometry contract for implementation: exactly `12 LINE + 1` closed straight four-vertex LWPOLYLINE and no text/arcs/circles/inserts. The frame long/short ratio is about `2.801`; two equal axial leads extend from opposite long-axis frame midpoints by `0.2143 × frame_length`; four equal-slope diagonals occupy the four intervals between five evenly spaced long-axis levels; and three interior levels each carry two coincident side-to-side bars that join adjacent diagonals on opposite frame sides. This complete relative topology is invariant to translation, rotation, reflection, and uniform scale.
- A same-count safety negative can keep all `12 LINE + 1 LWPOLYLINE` primitives while offsetting one of the duplicated interior bars away from its shared zigzag level. It must remain unsuppressed, proving the IGNORE model does not reduce to primitive census or fingerprint memory.
- Phase 155 completion: exact source geometry and an unseen `37° / 1.7×` member both match `electrical.nonconnective_vertical_zigzag_element_ignored.v1 / narrow-frame-four-cell-zigzag-v1`; the same-count displaced-bar negative remains review. Fresh original-DWG replay records handle `27268` as `MACHINE_GEOMETRY_RULE+HUMAN_EXACT_MEMBER / HUMAN_CONFIRMED_MEMBER / IGNORE / ports=[]`, with zero target candidates, topology applications, semantic nodes/relations, endpoint witnesses, and network members. All port emission, external attachment, internal connectivity, and electrical union flags are false.
- Final regression evidence for this shared state: focused geometry `2 passed`; full symbol proposal `128 passed`; analyze-project integration `23 passed`; repository `876 passed, 1 skipped`; `python -m compileall -q src tests` and `git diff --check` pass.

## 2026-07-16 test-set scope correction

- User confirms `F:\workspace\XJToolkit\test\【出原理图】N2604HBJ20732J合同` itself is a test-set root. The previous P003 census covered only its `11000 站控层网络通信柜` child and was incomplete.
- The full root contains 25 cabinet directories and 450 DWG files, including 10000 through 35000 cabinet groups plus the 8000~9000 clock cabinets. Rebuild P003 from the entire root before treating the compact queue as complete; preserve the current A$C1 pending item from P001 during replacement.
- Full recursive analysis succeeds for all 25 cabinet projects. Across 450 DWG source rows, 370 drawings are converted/analyzed and 80 cover/directory sheets are intentionally skipped; there are no failed conversion statuses. A synchronized post-PWF314 P001 census was also rebuilt so both test scopes use the same engine state.
- Final aggregation groups identical fingerprints across aliases, removes title metadata, and drops only instances whose complete ancestry is authoritative whole-symbol IGNORE. The new queue contains 76 substantive geometry groups / 1,088 live instance rows. Top coverage is PWF168 with 206 instances across four cabinet projects; the pending P001 A$C1 item remains present at rank 68 with its updated P001-current provenance.
- The locked next human item is `SYMB2_M_PWF168`, fingerprint `58325f4a...`, represented by full-root P003 cabinet `16000 220kV电压并列柜`, `06 开入回路图.dwg`, handle `28711`, world `(306.4530494,264.2319530)`. Current V2 reports `switch.open.candidate.v1 / REVIEW_REQUIRED`, up to two ports; no semantic decision has been assigned yet.
- Visual/source inspection shows a long narrow rectangular body inline on a horizontal route, with visible page annotation `R1XD`; the complete native definition is `2 LINE + 3 LWPOLYLINE`, including a central closed straight rectangle and two invisible bulged contact regions. Current drafts at local `(0,0)` and `(10,0)` both bind distinct external lines, but behavior remains shadow-only and no union is currently allowed. This needs human confirmation of whole IGNORE versus two outward ports and any internal conductivity.
- Human adjudication resolves every `SYMB2_M_PWF168` instance as whole-symbol IGNORE. Neither left nor right is a port; no external mapping, internal connectivity, or electrical union may be emitted. Generalize from the complete central closed rectangle, two collinear side leads, and paired equal contact regions; retain the fingerprint only as provenance and require transformed/unseen positives plus same-count close negatives.
- Next full-scope item `SYMB2_M_PWF209` has 89 instances across eight P003 cabinet projects. Representative `15000 220kV公用测控柜/04 交流回路图.dwg`, handle `F255`, world `(32.5,267.5)`, contains `4 LINE + 4 ARC + 4` closed bulged contact regions: two parallel rows, four outward contacts, and opposing paired semicircular lobes at the inner ends. Current V2 leaves it UNKNOWN with up to four drafts; source context repeats the motif on UA/UB/UC/UN voltage routes. Human mapping/internal-connectivity semantics are required.
- User confirms the PWF209 circular-arc wire motif is covered by the prior arc-wire IGNORE authority. Treat the complete definition as zero-port IGNORE and strengthen geometric generalization across its two parallel rows, four equal semicircular arcs, four outward contacts, and balanced spacing; transformed/unseen members must match while same-count displaced-arc/row negatives remain review.
- Full-scope rank-three `SYMB2_M_PWF163` occurs 63 times across seven P003 cabinet projects. Representative `15000/06 网络对时回路图.dwg`, handle `8047`, is an open switch/contact on the `Device alarm` route: three lines form collinear left/right leads plus one oblique blade, with paired line contacts and two displaced actuator/contact markers. This is the same switch class the user has repeatedly adjudicated whole-symbol IGNORE; its queue presence is a generalization gap, not a new semantic question.
- Next distinct `SYMB2_M_PWF175` occurs 63 times across six P003 cabinets. Representative `16000/06 开入回路图.dwg`, handle `287CD`, world `(122.510566,137.450110)`, has two equal visible circles separated by a wide gap, short collinear leads to the outer sides, and two equal closed bulged contact regions at the extreme ends. Source annotations show device text above and port numbers `1`/`2` below. It may be a numbered outward-only component or ignorable display/contact motif; human semantics are required.
- Human adjudication resolves PWF175 as a named two-port isolated component. The upper text supplies the instance name; left native pin `1` maps only to the same-side external route, right native pin `2` maps only to its same-side route, and pins 1/2 never connect internally or electrically union. Build a rotation/scale-invariant two-circle/two-lead/contact model with name/pin composition and measured same-side binding.
- Next live item `KK2P+OF11-12` occurs 30 times across ten P003 cabinets. Representative `10000/08 元件接线图1.dwg`, handle `2BF75`, world `(172.5,170)`, is a composite enclosure: main four numbered cells/pins `1..4` occupy the left 2x2 region, while a right auxiliary contact region carries circles/pins `11`, `12`, `14` and switch/mechanism lines. Source context exposes external labels such as JD16/JD12/JD30/JD24 and YD4/YD3, while the upper oval appears to carry the composite device name/type. Human authority is needed on which instance name applies, every outward mapping, and whether any main/auxiliary pins connect internally.
- Human adjudication defines a selective four-port component: compose the upper circular-tag instance name with main native pins `1/2/3/4`, and map each only to its same-side external route. The right OF auxiliary region, pins/text `11/12/14`, and mechanism graphics are ignored and must emit no ports/mappings. Main pins remain independent outward endpoints with no body union; the generalized model must validate the complete composite geometry but expose only four ports.
- `SYMB2_M_PWF216` occurs 52 times/four P003 cabinets. Representative `16000/06 开入回路图.dwg`, handle `28704`, is the same previously adjudicated ignorable vertical enclosure class: tall main rectangle, narrower bottom cell, one bottom-cell diagonal, two collinear external leads, and paired extreme contact regions. Prior human authority is whole-symbol IGNORE with no ports, mappings, internal connectivity, or union. Its reappearance requires a transformed complete-geometry model rather than another fingerprint.
- `SYMB2_M_PWF166` occurs 33 times across five P003 cabinets. Representative `10000/06 远动接口联系回路图.dwg`, handle `27ABF`, world `(170,215)`, has one short vertical line and six overlaid/stacked closed bulged contact regions at four levels. It lies on the HYKL panel's `PE1` route immediately above external `GND` bars. It resembles a grounding/contact-stack marker but is not identical to the stepped/circled ground families; human confirmation is needed before whole IGNORE versus terminal/mapping behavior.
- `SYMB2_M_PWF172` occurs 35 times/four P003 cabinets. Representative `16000/06 开入回路图.dwg`, handle `28712`, is the `LED1` graphic immediately left of PWF168: diode triangle/bar and through-line plus two oblique emission arrows, with two extreme contact regions. It is directly covered by prior human authority that small and large diode/LED symbols are whole-symbol IGNORE, internally disconnected for audit purposes, and create no ports/mappings/union. The current queue row is another generalization gap.
- Prepared next distinct `SYMB2_M_PWF115` (32 instances/three P003 cabinets), representative `23000/20 高压侧操作箱原理图2.dwg`, handle `1A00D`, inserted at `(122.5,53.992)` with 90° rotation and 0.5 scale. Native geometry is one central circle, four orthogonal short leads, and four extreme closed contact regions. In context it sits at a horizontal route crossing a vertical branch above `P1`; human authority is needed on IGNORE versus four-way junction/connectivity semantics. Keep the crop queued until PWF166 is answered.

## 2026-07-16 known-semantics queue reconciliation

- User's read-only audit correctly identifies that the full-root queue still mixes semantic uncertainty with geometry-generalization debt. Stop presenting further rows until known authority is replayed and removed.
- Current on-disk queue is `75` groups / `1,087` instances, not the earlier `76` groups: the one-group difference is the already verified and removed A$C1 row. The other named stale rows remain present.
- Exact fingerprint identity is mandatory. Current duplicate names are: `SYMB2_M_PWF166` fingerprints `5a5823...` (33 instances) and `f3a5a2...` (18); `*U17` fingerprints `fe6282...` (5) and `c2becb...` (4); `ELXAL5-B11-209B` fingerprints `caa420...` (6) and `e91786...` (2). Never merge these by definition name.
- The current file still contains A$C08084C19 (4) and A$C7E971F70 (8), now sourced from additional full-root cabinets. Their complete ancestry and current parent policy must be replayed before removal; do not merely delete rows based on name.
- Exact current ancestry is mixed: all four A$C080 instances are nested under `DGICOM4000-8G12GX8GE-HV-HV` in cabinet `14000_B`; A$C7E spans both that DGICOM parent and a distinct `WYD-811-401` parent in cabinet `10000`. The user authorizes both rows as non-independent child artwork, but engine cleanup must prove authoritative whole-parent suppression for each parent subtype rather than assuming every A$C7E placement has a DGICOM ancestor.
- Current `WYD-811-401` parent fingerprint `75436f14...` is only `line_break.non_connective.candidate.v1 / REVIEW_REQUIRED / REVIEW_ONLY`, with two false panel extrema; it is not yet an authoritative ancestor. The correct generalized path for the four WYD-nested A$C7E placements is to classify the complete WYD equipment panel (if full geometry satisfies existing panel IGNORE authority), then inherit suppression. Do not add A$C7E child-fingerprint memorization.
- Raw WYD definition confirms a complete dense device panel, not a line-break symbol: `189 LWPOLYLINE + 96 TEXT + 24 HATCH + 17 LINE + 15 CIRCLE + 5 INSERT + 4 ARC`, with native COM1..8, LAN1..12, USB, VGA, PWR1/2, B+/B-, DO1/2, power and alarm labels. This is high-confidence equipment-panel geometry covered by the user's whole-panel IGNORE authority. Add a strict WYD panel subtype and let ordinary ancestor inheritance suppress A$C7E children.
- The cabinet-14000 parent `DGICOM4000-8G12GX8GE-HV-HV` fingerprint `250a8a04...` is also not recognized by the existing DGICOM panel family; current V2 misclassifies it as `elongated-round-end-two-port-v1 / EXTERNAL_PORTS_ONLY`. Thus A$C080/A$C7E re-entry is not an ancestor-walk regression—the full-root census exposed two missing whole-panel subtypes (DGICOM 8G12 and WYD). Generalize both complete parents, then reuse the already-correct ancestor suppression policy.
- Raw DGICOM 8G12 definition is a complete dense panel: `379 LINE + 252 LWPOLYLINE + 120 ARC + 111 TEXT + 54 HATCH + 40 CIRCLE + 3 INSERT`, with GX1..28/1T..20R optical labels, GE1..16/P1..16 ports, Combo/Console/PWR1/PWR2 and power/fault labels. This is a distinct subtype from existing 4GX24GE and compact 2GX8GE models; preserve subtype-specific complete counts/grid evidence while sharing `communication.equipment_panel_ignored.v1`.
- After the already completed A$C1 removal, the user's known-semantics list corresponds to `18` rows / `630` instances still present in the current `75` / `1,087` queue. The earlier `19` / `631` total includes A$C1 itself.
- Known behavior lanes are: whole IGNORE PWF168/PWF209/PWF163; isolated outward two-port PWF175 and FJL-25-2A; geometry-distinct switch-IGNORE fingerprints; and selective named main ports for KK1P/2P/3P+OF with auxiliary OF contacts suppressed. Each lane requires transformed unseen positives, close negatives, source replay, and downstream no-union evidence.
- Phase 157-160 first implementation return is not acceptable yet. It added exact policies and four matcher helpers but no discoverable PWF168/PWF209/PWF163/PWF175 unit or integration tests. More importantly, each helper checks `entity_histogram.LWPOLYLINE` as if closed bulged contact regions had already been removed: it expects 1/0/0/0, while real definitions contain 3/4/4/2 LWPOLYLINE respectively. Because `entity_histogram` takes precedence, the real geometry branches cannot match; exact fingerprint policy can hide this defect. Require a replacement worker and raw-shape unseen-fingerprint proof.
- Fresh all-source replay now covers all 40 unique pages / 421 instances for PWF168/PWF209/PWF163/PWF175. Every proposal row uses `MACHINE_GEOMETRY_RULE+HUMAN_EXACT_MEMBER`; IGNORE totals are exactly PWF168=206, PWF209=89, PWF163=63 with zero ports/candidates/topology/semantic/witness/network artifacts. PWF175 emits exactly 126 outward candidates for 63 instances, all attached and no-union.
- PWF175 naming is not yet complete: only 102/126 candidates have `component_port_identity`. The missing 24 are confined to P003 `23000_A/09 通讯、对时及打印回路.dwg` and `27000/06 网络回路图.dwg` (12 candidates each). Do not remove PWF175 until these two pages are inspected and instance-name composition is resolved or explicitly proven unavailable.
- PWF175 naming gap is closed. Both affected pages use short alphabetic instance name `DYQK`; adding the new subtype to the existing short-alpha component-label path yields all `DYQK-1..12` identities. Final all-source aggregate is 126/126 named, 126/126 attached, and zero internal connectivity/union.
- Phase157-160 final gates pass after the real-arc and DYQK fixes: symbol-proposal unit `130 passed`, analyze-project integration `23 passed`, repository `878 passed, 1 skipped`, compileall and `git diff --check`. The live queue removes exactly four fingerprints / 421 instances and is now `71` groups / `666` instances.
- Switch IGNORE prep must use eight distinct fingerprints totaling `121` instances (not the explorer's arithmetic typo `116`). Two PWF166 subtypes are structurally separate: `5a5823... = 1 LINE + 6 closed contacts` and `f3a5a2... = 1 LINE + 4 closed contacts`; they share user-authorized IGNORE behavior but must be mutual geometry negatives. Other strict subtypes include PWF265 circle/contact frame, two four-line gap geometries, PWF26, nested DPDT artwork, and the dense NKP panel; the latter three require direct block parsing before implementation.
- FJL-25-2A and Mirror share the same complete `2 TEXT + 2 LINE + 2 CIRCLE + 4 LWPOLYLINE` geometry and isolated pins 1/2, while Mirror's native single-character pins retain their special terminal-candidate filter. KK+OF must share one hierarchical family but expose subtype-specific main pin sets `2/4/6`; OF `11/12/14` and mechanism geometry never become ports.
- Reverse P003 `NGFW4000-UFTG-3100-GW`: human authority is whole-device-panel IGNORE. ETH0..ETH13, USB, Console, optical 1T/1R..4T/4R, right-side L/N/PE/J terminals, and all visible leads create no mapping or connectivity.
- Representative is P003 `10 元件接线图3.dwg`, handle `2C18F`, insertion `(222.5,272.5)`, fingerprint `07d8f9b0bc6c61dd003c0d32861f58c0a1babc0be3cee88783f7dcbb4ab63e25`; second instance handle is `2C1B7`.
- Complete firewall-panel evidence is `24 ARC + 12 CIRCLE + 28 HATCH + 89 LINE + 120 LWPOLYLINE + 39 TEXT + 8 MTEXT`, 13 repeated square socket cells, four equal collinear USB circles, eight equal optical circles in a 4x2 grid, and native ETH/P/USB/Console/power labels. The current generic line-break two-port result is a false panel-extrema reduction.
- Side midpoint `CD-WSK-H-J-G` (`d1202915...`, P001 `21 元件接线图1.dwg`, handle `2739F`) is human-confirmed as eight mutually isolated outward-only ports. The upper circular tag supplies the instance name; the definition name is not the instance identity.
- Generalized family `component.external_multi_port.v1 / eight-numbered-side-contact-panel-v1` requires the complete `13 LINE + 17 LWPOLYLINE + 31 TEXT + 1 INSERT` census, aligned 2x4 round-contact and square-cell grids, unique native pins `1..8`, outward midpoint placement, and nested `12 LINE + 1 LWPOLYLINE` evidence. Exact and unseen rotated/scaled members emit eight ports; a displaced-contact same-count negative remains review.
- Fresh single-page replay binds circular-tag name `K` and persists `K-3→JR-1`, `K-4→JR-2`, `K-5→KZKK-2`, `K-6→KZKK-4`; unwired `K-1/K-2/K-7/K-8` stay label-only. All eight rows are no-internal-connectivity and no-union.
- Side midpoint `JR-01` (`4045826f...`, P001 `21 元件接线图1.dwg`, handle `273A5`) is human-confirmed as two mutually isolated outward ports. The upper circular tag supplies instance name `JR`; complete mappings are `JR-1→K-3` and `JR-2→K-4`.
- Generalized `component.external_strip_two_port.v1 / horizontal-numbered-two-circle-box-v1` uses the complete two-circle/two-contact/numbered/outer-box topology and replaces four false box corners with the two circle-bound contacts. Exact and rotated/scaled unseen members match; a displaced-contact same-count negative remains review.
- Fresh single-page replay persists exactly two `MEASURED_COMPONENT_PORT_MAPPING` rows (`PCS0001/PCS0002`) with internal connectivity and electrical union disabled.

## 2026-07-16 Phase 157-160 serial implementation acceptance notes

- Read-only representative DXF inspection confirms the requested complete geometry exactly. PWF168: contacts centered `(0,0)/(10,0)` with radius `.5`, equal 2.5-unit leads, and a closed `5 x 1.875` central rectangle. PWF209: four radius-.5 contacts on two rows 7.5 apart, four radius-1.875 semicircles centered at axis positions 7.5/15 and intermediate row levels, plus four equal 7.5-unit outward leads. PWF163: radius-.5 line contacts at `(0,0)/(7.5,0)`, actuator markers at `(-2.5,2.5)/(10,2.5)`, equal collinear leads, and one oblique blade from `(2.5,-1.25)` to `(5,0)`. PWF175: radius-.5 contacts at `(0,0)/(10,0)`, radius-.625 circles at `(1.875,0)/(8.125,0)`, and equal 1.25-unit same-side leads from each contact to the adjacent circle edge.
- These measurements provide strict transformed-family ratios and close-negative displacement axes without relying on definition names, coordinates, or fingerprints. PWF175's only defensible ports are the two contact centers, with outward vectors away from the circle-pair midpoint.
- Phase 157-160 matcher completion adds geometry-only contracts for PWF168
  inline rectangle, PWF209 dual-row semicircle arc-wire, PWF163 open switch,
  and PWF175 isolated named two-port. Exact fingerprints remain provenance.
- Repair evidence: the first helpers incorrectly expected contact polylines to be absent from `entity_histogram` (1/0/0/0), so exact policy masked failed geometry matching. Corrected contracts consume raw counts 3/4/4/2 and validate relative geometry; PWF163 validates contact rows and blade geometry. Unseen raw-shape proof passed and displaced same-count negatives stayed review.
- 2026-07-16 switch-class batch: added provenance-only policies for eight authorized digest prefixes (121 instances). Geometry matcher is independent of name/fingerprint. Safe generalized rules currently cover vertical six/four contact stacks, PWF265 circle/line/bulged-contact/hatch frame, and strict horizontal four-line gap geometry; PWF26, nested DPDT, and dense NKP artwork are intentionally not exact-only generalized.
- Phase166 accepted geometry contracts: PWF166's two distinct contact-stack shapes share grounding IGNORE semantics but remain separate subtypes; FJL selects the two contacts actually reached by source lines rather than the decorative outer pair; KK+OF derives 2/4/6 main-pin grids while the three circle-associated 11/12/14 contacts are recognition-only.
- Real replay distinguishes unwired component placements from recognition failures: FJL/KK proposals all machine-match, every physical main contact is emitted, all wired contacts attach, and no auxiliary/internal union is created. Missing external labels on genuinely unlabeled routes are not synthesized.
- PWF172 complete geometry is `7 LINE + 4 LWPOLYLINE`, including two equal contacts and two one-zero/three-equal-width open arrow paths; PWF216 is `3 LINE + 4 LWPOLYLINE`, including two contacts and two nested rectangles. Their matchers compare complete undirected segment graphs under rigid similarity, not primitive counts alone.
- DGICOM3000-4GX8GE-HV is not a line-break/two-port component. Its full `24 ARC + 8 CIRCLE + 20 HATCH + 1 INSERT + 96 LINE + 70 LWPOLYLINE + 38 TEXT` face, GE1..8/GX9..12/GT/GR/Console/power labels, nine square cells and eight-circle optical arrangement form a strict communication-panel IGNORE subtype.
- 2026-07-16 WFS/ELXAL closure: WFS uses a complete `2 CIRCLE + 3 bulged LWPOLYLINE + 2 polarity TEXT` contract. Rotation invariance must use bulged-contact chord radii, not axis-aligned bbox radii. Both ELXAL fingerprints share one strict `4 CIRCLE + 4 LINE + 4 contact LWPOLYLINE + labels 11..14` geometry subtype while remaining separate provenance members.
- Fresh replay of all seven occurrence DWGs proves WFS 7 instances / 14 named `instance-(+|-)` candidates are all attached to distinct external networks; ELXAL 8 instances expose four independent identities each, with only physically wired ports promoted to measured mappings. Every candidate has `internal_connectivity_inferred=false` and `electrical_union_eligible=false`.
- A six-agent independent audit of the remaining live queue found no further fingerprint that can be closed solely by an existing exact historical entry. `SignBlock_0.1` is the only immediately safe semantic candidate, and only under a verified title/sign-frame ancestor plus wrapper-only geometry. The remaining work must inspect complete source geometry/ancestry; names, `max_ports`, primitive counts, and fingerprint similarity are insufficient.
- Transparent wrapper rule: `local_geometry_signature_count=0` means the definition has no local port/connectivity question. Filter it from annotation ranking, but do not classify it as whole-symbol IGNORE because expanded descendants may remain meaningful. This removes all 14 SignBlock/A$C alias instances without ancestor suppression.
- Historical switch IGNORE now has four additional strict subtypes: PWF85 three radial contacts plus selector slash, PWF200 five-line offset actuator, PWF204 six-line/double-stem actuator, and PWF235 eleven-line crossed actuator. The latter three use complete primitive census plus invariant line-length, arc/contact-radius, and contact-span signatures, keeping them separate from outward 13/14 switch components.
- 2026-07-16 Phase166 isolated components: raw P003 geometry separates five previously UNKNOWN groups without name-based merging. PWF115 is `CIRCLE1/LINE4/LWPOLYLINE4` with four equal orthogonal contacts; PWF98 is `CIRCLE1/HATCH1/LINE3/LWPOLYLINE2` with two axial contacts; PWF218 is `LINE4/LWPOLYLINE4` with two contacts and two aligned frames; SYMB1_M_30401 is `LINE1/LWPOLYLINE3` with two contacts and one centred triangle. All four expose outward-only ports and explicitly forbid internal connectivity/union.
- PWF259 is not a four-port component: its four machine candidates were square bbox extrema. The complete `LINE1/LWPOLYLINE3` topology is one square, one corner-to-corner diagonal, and two contacts inset on a single edge; all nine corpus instances had no external attachment. It now belongs to a strict rectangular-diagonal mechanism IGNORE subtype, not a generic rectangle rule.
- All five new subtypes are independent of definition name and fingerprint. Real rows reach `MACHINE_GEOMETRY_RULE+HUMAN_EXACT_MEMBER`; renamed, rotated, uniformly scaled fixtures reach `MACHINE_GEOMETRY_RULE`; displaced-contact/frame/triangle/diagonal near-negatives are rejected. Fingerprints remain provenance only.
- Fresh replay covered 15 unique P003 DWGs / 132 instances: PWF115 32, PWF98 54, PWF218 16, PWF259 9, SYMB1_M_30401 21. PWF259 emits zero ports/candidates; the four outward-port classes emit 310 independent port candidates total, with 170 measured line attachments, zero internal connectivity, and zero electrical union. Missing external wires remain unwired identities and are not fabricated.

- XJDZ9-04 raw block geometry is exactly `11 CIRCLE + 11 TEXT + 12 LWPOLYLINE`; labels are `1..8/C+/G-/R-`. Eleven equal circles and eleven equal outward contacts form two regular columns with one extra end row, while the remaining polyline is a much larger rounded body. This creates a strict similarity-invariant subtype distinct from the even `2×N` numbered arrays.
- The first XJDZ9-04 replay exposed a component-name false positive (`1-21CD11`) because the even-array name window stopped at pins 7/8. Functional-array naming must use the full 11-port axial extreme and require the designator beyond the topmost port. The corrected replay binds `1-21KK/2-21KK/3-21KK`.
- Numeric hierarchical side endpoints such as `1-21ZK-2` require a subtype-scoped endpoint grammar and a measured 14-unit label reach; this is not a global relaxation. Three independent source occurrences of `1-21KK-1` all bind `1-21ZK-2` after the correction.

- Phase167 corpus scope is 502 DWGs: P003=450, P001=28, transformer-control=24. The first 11 completed/audited project bundles cover 179 pages. Current fresh engine has no `UNKNOWN/Fallback` page route and no filename-indicated terminal/backplate/component page routed to a generic extractor in that partial baseline.
- Partial audit is already far below the reported historical 300 issues/page failure: 314 issues across 179 pages, 38 pages with any issue, maximum 36 on `16000_220kV / 09 装置背板.dwg`; no page has >=100. Rule totals are `R-MANY-TO-ONE=131`, `R-ONE-TO-MANY=80`, `R-PAIR-MISSING-SIDE=40`, `R-CROSS-PAGE-CONFLICT=30`, `R-PAIR-LOW-CONFIDENCE=26`, `R-DUPLICATE-PAIR=7`.
- The current highest page is correctly recognized as `背板表格型图 / backplate_virtual_terminal_table -> TableExtractor`. Its 36 findings are all structured `table_mapping` scope reviews (`21 one-to-many + 15 many-to-one`) and every diagnostic root cause is `rule_too_strict`, not extractor missing. Taskbook authority says preserve these mappings and improve rules/aggregation/display rather than removing graph relations.


## 2026-07-16 15:55 Desktop industrial UI + backend runtime awareness

- Product language direction locked: pragmatic, concise, industrial — not marketing demo.
- Design tokens moved off cold corporate blue to 灰/黑/白/米/黄 workbench surfaces.
- Frontend empty-spin risk mitigated at UX level: topbar engine pill + launch warning when `!isTauri()` so users know browser mock is not a real audit.
- Backend contract unchanged and already wired: Tauri `desktop_*` commands → Python `dwg_audit.desktop.sidecar` (`analyze_session`, `list_recent_projects`, `load_project_result`, `render_project_preview`, `update_issue_status`) + SQLite state store.
- Safe UI-only surface continues: confidence breakdown, 1:N triage labels, coords/line_group from evidence, preview regenerate, status write-back.
- 2026-07-16 communication-marker closure: `SYMB2_S_PWF3` is a one-contact round remote-interface marker with a centre slash; `SYMB2_S_PWF303` is the two-contact parenthesis glyph used beside RX/ST; `A$C3CE477D4` and `A$C7ECC553D` share one closed two-semicircle/two-parallel-line routing capsule geometry. Historical communication/line-break adjudications authorize zero ports and zero mapping for these complete motifs.
- The three new matchers require complete normalized topology and reject displaced-contact, displaced-parenthesis-contact, and displaced-cap negatives. Fresh replay covers 6 unique source DWGs / 13 instances; every definition row is `MACHINE_GEOMETRY_RULE+HUMAN_EXACT_MEMBER`, and all emitted ports/network candidates are zero.
- 2026-07-16 numbered-array resumption: the clear batch is XJDZ9-06 (16 pins/5 instances), XJDZ9-02 (8/4), XJDZ4-18 (12/2), and XJDZ9-10 (28/3). Parameterize the existing numbered-contact proposal path; fingerprints remain provenance only and every pin remains outward-only/no-union. XJDZ9-04 pins 1..8 are certain, while C+/G-/R- is a genuine pending human distinction between auxiliary labels and additional ports.
- Diagnostic errors after restart: direct `ezdxf.readfile()` on DWG failed because ODA conversion is required; use converted-DXF cache or the normal pipeline. Packaged `rg.exe` also hit a Windows access error; use native PowerShell enumeration and `Select-String` in this session.
- Converted-DXF proof for the XJDZ array family: XJDZ9-02 is `8 CIRCLE / 9 closed-bulged LWPOLYLINE / 8 TEXT`; XJDZ4-18 is `12/13/12`; XJDZ9-06 is `16/17/16`; XJDZ9-10 is `28/29/28`. In every subtype, labels are exactly contiguous `1..N`, N equal circles and N equal small outer contacts form a rotation-invariant `2 × (N/2)` grid, and the remaining single much larger closed-bulged polyline is the body. Current outputs are incorrectly 2 or 4 free extrema because the old numbered helper allows only `{4,6,8}` and includes the body in its contact count.
- Phase167 parallel audit: 300 baseline pages currently exist; no table-like page routes to UNKNOWN/Fallback and `table_like_non_routed=0`. The current maximum is 43 issues on `15000_220kV / 14 测控1装置背板.dwg`; 307/314 audited issues are review-level, dominated by one-to-many/many-to-one rules rather than missing extraction.
- Coverage root cause is independent of routing: `_wire_segment_coverage_by_page` treats every in-bbox `LineEntity` as conductive and excludes only line-group members. This inflates table grids, frames, and component artwork into `unassigned_wire_segments` (3447/3444 on the two `14000_B` switch-table pages).
- `LineEntity` currently carries only source type/layer/geometry; richer provenance (`parent_handle`, `nested_path`, `layer_role_candidate`, `linetype`) exists in `primitive_normalizer` but is unavailable to coverage. Conductivity needs an explicit scope; bbox membership is not sufficient.
- Table review inflation occurs after correct extraction: `TableExtractor` emits structured `table_mapping` pairs, then ordinary graph rules re-interpret the same facts. Preserve mappings and introduce fact/scope-level aggregation instead of suppressing evidence.
- Fresh isolated replay of `14000_B/10-11 交换机接线图` exposed a real context-dependency: with the project PRJ both pages are `背板表格型图 -> TableExtractor`, but without the sidecar they become `unknown -> LayoutOnlyExtractor`. The cause is circular: virtual INSERT expansion is enabled only when the coarse scanner already knows `sheet_category in {元件接线图, 背板接线图}`; without expansion the classifier sees 14 endpoint labels and 516 polylines but no block-internal virtual row/header text.
- The isolated geometry remains strongly distinctive: about 1050 lines, 516 polylines, 6 blocks, 14 backplate-like endpoint texts, horizontal ratio 0.985/0.986, and 3 horizontal bands. A generalized context-free dense table/panel subtype must be corpus-negative checked before changing thresholds.
- Corpus-negative scan covered 399 completed pages. The safe discriminator is the conjunction of `polyline>=100`, horizontal ratio `>=0.9`, `3..6` grid bands, `endpoint>=8`, and `4..8` blocks. Similar wire pages have 13-22 bands and 60-170 blocks; component pages have 12-15 blocks. The resulting `dense_contact_panel_table` is geometric and sidecar-independent.
- Accepted replay: standalone 14000_B switch pages now route to `TableExtractor` with zero false pairs/mappings and zero conductive gaps. Fresh full 14000_B replay preserves all 14 page routes exactly; switch-page gaps remain 0/0 and audit issues improve from baseline 1 duplicate review to 0.
- Highest-page fact audit corrected the counting model: `15000_220kV` has 49 persisted issues total; pages 14/15 contain 21/11 issue rows, while larger UI numbers reflect related-pair/evidence expansion. Page 14 is 10 cross-page scopes plus 11 many-to-one endpoint scopes. Safe presentation aggregation must retain rule, sheet/cross-page scope, source block, header set, contiguous row range, and endpoint identity; mappings remain fully expandable.
- Full persisted `run-audit` initially produced 970 reviews versus 314 in the original baseline and 0 in fresh 16000 replay. One concrete serialization mismatch was found in the new authority gate: persisted parquet may expose `row_number_sequence_valid` as integer/numpy boolean, so identity comparison `is True` rejected otherwise identical complete table facts. Normalize true/1 while retaining all other completeness checks, then re-run the persisted audit before trusting the 970 count.
- Full current2 audit over all 502 pages now yields 703 issues, max 38/page. The next dominant clusters are component pages and terminal arrays, not table routing: 20000 pages 26/27 are ordinary-pair shadows around canonical component mappings; 23000/25000 share comma-split KLP chain cardinality, with 25000 additionally retaining 24 genuine extraction-gap candidates; 8000/9000 terminal pages contain 64 complete two-sided ordinary pairs whose confidence is depressed despite stable row/column arrays.
- Component-page representative: `20000_1/27`, ordinary `PC0177/GC0177` reports `?→113` at `(260,254.88756)→(260,239.88756)`, while canonical `PCM0002` already resolves `2-21KLP2-2→2-21n113`. Suppression must depend on measured component mapping coverage, never page type alone.
- Terminal-array representative: `8000_9000_-/17`, `PT0205/GT0205` maps `182→802` with both text handles and stable 5-unit row spacing; its root cause is insufficient confidence, not missing extraction. Array priors may raise confidence only for unique two-sided candidates in a stable row/column sequence.
- FJL component extractor contained a concrete name-normalization gap: `_strip_port_pairs` accepted only `FJL-25-2A_Mirror`, although the human-approved geometry family includes direct and mirrored definitions. Normalizing the optional `_Mirror` suffix raises 20000 page 26 component mappings from 1 to 15 and page 27 from 4 to 16.
- Fresh 20000 analyze + real run-audit confirms partial improvement with no route changes: project issues 96→82; page 26 issues 35→27 and page 27 issues 38→32. Pair totals increase only through new `component_mapping` facts (2413→2439); covered ordinary pairs are marked discard, not deleted. Remaining gaps require geometry/extractor work, not blanket component-page suppression.
- Hierarchical external endpoints such as `1-21C1D36` were rejected by the FJL extractor's flat endpoint grammar. Adding the cabinet-module form with a malformed `1-21C-D36` negative raises isolated page-26 component mappings to 63 and reduces its audit issues from 27 to 4 (3 residual low-confidence plus an isolated-page metadata mismatch); routes remain ComponentDiagramExtractor.
- Page 27's remaining 32 issues are a different HMC-3C device-panel family (`HMC-3C wiring diagram`, HD18..HD24, BCD/front-panel labels), not FJL. Its pin/internal-panel semantics are not present in current human arbitration authority, so do not suppress these 28 missing-side and 3 duplicate-line candidates by page type; retain for later source interpretation or human adjudication.
- Complete comma-group component authority reduces persisted 23000 page 29 from 35 to 2 and 25000 page 18 from 35 to 24 without touching missing-side candidates. After fresh extraction with the hierarchical endpoint fix, isolated page 29 has 76 component mappings and zero electrical issues; page 18 has 74 component mappings and only two shared-endpoint reviews (`1n201`, `1n202`). The former 24 missing sides were extraction gaps and are now genuinely resolved, not hidden.
- Stable terminal-row authority resolves the 8000/9000 pages without table fabrication: page 17 promotes 31 long-array rows plus a separate 3-row synchronized sequence; page 18 promotes 30 rows. Fresh replay removes all 64 low-confidence electrical reviews. The only remaining isolated replay issue is a page-number mismatch caused by removing the original PRJ context; the full-project baseline did not contain that mismatch.
- Phase167 restart risk review found two potential false-negative boundaries in the current uncommitted diff. First, `_is_authoritative_table_mapping_group()` validates each complete table row independently but does not yet prove that a cardinality group belongs to one coherent table scope; cross-sheet or cross-header collisions must remain review. Second, conductive coverage currently rejects every segment when `route_target` is missing or wrong before honoring positive line-group membership; measured line-group evidence should remain countable even on a misclassified page, while ungrouped geometry must not reintroduce table-grid inflation. Both require focused negative tests before the next corpus replay.
- Both restart risks now have narrow contracts. Complete table cardinality is authoritative only when the group shares one coherent source scope: backplate rows require the same sheet/file/source block, while terminal-header rows require the same sheet/file/header prefix/header text. A complete duplicate from two distinct sheets/tables remains `R-DUPLICATE-PAIR`. Conductive coverage now honors measured line-group membership before route gating, but still excludes ungrouped table grids and expanded block artwork.
- Current-head re-audit over the persisted 502-page baseline produces 677 independent issues: 294 low-confidence, 187 missing-side, 122 many-to-one, 65 cross-page, 6 duplicate-pair and 3 duplicate-same-line. This is a prioritization view, not final acceptance, because persisted pairs predate the fresh-extraction fixes: it still contains the 64 terminal-array low-confidence rows, old 20000 page-26 gaps, and old 25000 page-18 gaps already eliminated by focused fresh replays. The next loop must therefore fresh-replay candidate projects before classifying their residuals.
- Transfer-resume replay roots are confirmed from persisted manifests, including PRJ/XML context: `24000_220kV_A -> test/.../24000 220kV母线保护A柜` (target F0020 page 20), `29000 -> test/.../29000 电度表柜` (targets F0009/F0014), and `8000_9000_- -> test/.../8000~9000 主-扩展时钟同步柜` (targets F0005/F0016/F0019). Full project roots, not isolated DWGs, are the authoritative fresh-replay inputs so page numbering and terminal metadata remain valid.
- Fresh full-project replay of `24000 220kV母线保护A柜` proves page 20 is already fixed by current extraction: old `18 × R-PAIR-MISSING-SIDE` becomes zero issues, with 57 high-confidence `component_mapping` facts and 68 covered ordinary shadows marked discard. Project issues fall `62 -> 44`; all remaining rows are on pages 19/21/22/23 and are independent terminal/low-confidence clusters. No new page-20 suppression or code change is justified.
- Fresh `29000 电度表柜` is unchanged at 33 issues. Page 14 contains eight exact `KK2P+OF11-12` instances: geometry correctly emits only main ports `1/2/3/4` and suppresses OF `11/12/14`, but all 32 symbol-port rows remain `SHADOW_ONLY` with `terminal_designator=null`; ordinary pairing therefore misreads auxiliary graphics as sixteen `2 -> 14/12` low-confidence facts plus two missing sides. The next diagnosis is instance-name/port-to-external binding, not another geometry classifier. Page 09's ten missing sides cluster around repeated PWF165/PWF234/PWF231 communication/alarm blocks and must be checked against network-boundary semantics before suppression.
- Page-14 source evidence proves every KK instance has a valid upper designator and four same-side endpoints: `5DK/4DK/3DK/2DK/1DK/6DK/CJDK1/CJDK2`, with representative `1DK-1→ZD11`, `1DK-2→ZD29`, `1DK-3→ZD1`, `1DK-4→ZD21`. Existing synthetic KK binding uses a designator at the insertion centre; real designators sit about 26.5 units above the insertion and compete with item numbers/model text. The family/port geometry is already exact, so the generalized fix belongs in orientation-aware component-label selection and must reject pure item numbers/model strings.
- Exact binder inspection explains the miss: KK uses the mean of four world ports as its label centre, but the generic `component_label_radius=25` limit rejects the real upper labels at roughly 28 units. Numeric-leading `1DK..6DK` match the existing regex; letter-leading `CJDK1/CJDK2` do not. A safe generalized label rule must use transformed component orientation and port span to select a central label beyond the upper port row, reject nearer side endpoints (`ZD*`/`YD*`), and retain the existing centre-label fallback. Before editing, the canonical pair promotion path must also be checked because symbol candidates are intentionally shadow-only.
- Canonical promotion does not consume symbol candidates: `extract_kk_multi_port_component_pairs()` independently reconstructs KK2P/KK3P mappings from `BlockRecord + TextItem + LineGroup`. Therefore fixing only shadow label binding would improve diagnostics but not remove audit errors. This extractor already has digit-first body support and a 36-unit upper-body window, so the next exact read is its block-port/body/endpoint geometry helpers to find why all eight real blocks produce zero canonical pairs.
- Canonical root cause is now concrete: `_kk_multi_port_count()` performs an exact lookup against `KK2P/KK3P`, so real names `KK2P+OF11-12` never enter the extractor at all. Once the optional suffix is normalized, numeric bodies `1DK..6DK` fit the existing body window; `CJDK1/CJDK2` additionally require a guarded letter-first body grammar. Geometry/port/endpoint helpers already enforce main pins `1..4`, per-instance nearest-block ownership, same slot, valid external endpoint, and a supporting horizontal line, so the fix can remain narrow without fingerprint memory or auxiliary-port promotion.
- First KK canonical fix replay succeeds partially and safely: page 14 now emits all 32 expected KK mappings (`1DK..6DK/CJDK1/CJDK2 × pins 1..4`) plus the four existing AK/A' mappings; project issues fall `33 -> 24`, page 14 `18 -> 9`. The remaining eight low-confidence rows are exactly internal auxiliary artwork `2 -> 12` (one per KK block) and must be discarded without emitting OF mappings. One separate `missing -> 3` long line remains and requires source-line inspection before classification.
- Concurrent-agent review found multiple unsafe blanket shadows in commits `d0a935c..04f2744`: every ordinary pair on a broadly named signal/alarm page is excluded; any long component line with one bare digit is excluded; and CD/GD/ZK-derived ordinary rows are broadly excluded despite those being valid external endpoint families. These rules optimize issue counts without proving local geometry/structured coverage and can hide real errors. HMC panel IGNORE is now explicitly human-confirmed and may remain, provided its implementation stays limited to HMC title/HD+BCD panel evidence and does not suppress real KLP/GD/n### external mappings.


## 2026-07-17 Windows offline packaging

- Target: ship a Windows NSIS `.exe` installer so end users need neither Python nor ODA File Converter preinstalled.
- Existing shell already had Tauri 2 + NSIS target and a PyInstaller sidecar hook; gap was ODA bundling + discovery + release orchestration.
- Packaging layout now used by release builds:
  - `resources/sidecar/dwg-audit-sidecar.exe` (~92MB one-file PyInstaller engine)
  - `resources/oda/**` (~70MB staged ODA File Converter tree including `ODAFileConverter.exe` + Qt/TD DLLs)
  - Tauri maps these to installed resource roots `sidecar/` and `oda/`
- Runtime discovery order for ODA: config path → `ODAFC_PATH`/`ODA_FILE_CONVERTER` → bundled resource/sidecar sibling → PATH → Windows Program Files installs.
- Desktop shell injects `DWG_AUDIT_RESOURCE_DIR`, `DWG_AUDIT_SIDECAR_EXE`, and `ODAFC_PATH` into the sidecar process when bundled ODA is present.
- Default config no longer hard-codes a developer machine Program Files ODA path (`odafc_path: ""`).
- Build commands:
  - `apps/desktop/scripts/stage-oda-resources.ps1`
  - `apps/desktop/scripts/build-sidecar.ps1`
  - `apps/desktop/scripts/build-windows-release.ps1` (or `npm run package:windows`)
- Verified local release artifacts:
  - `apps/desktop/src-tauri/target/release/dwg_audit_desktop.exe`
  - `apps/desktop/src-tauri/target/release/bundle/nsis/DWG Audit Desktop_0.1.0_x64-setup.exe` (~113MB)
  - release tree contains both `target/release/sidecar/dwg-audit-sidecar.exe` and `target/release/oda/ODAFileConverter.exe`
- Binary payloads stay gitignored; only README placeholders are tracked under resources.
- Residual packaging risks: ODA redistribution rights must be confirmed for product distribution; clean-machine install smoke still recommended; code signing not yet configured.

## 2026-07-17 packaging CI trigger policy
- `windows-package.yml` is release-gated: tag `v*` / GitHub Release / manual dispatch only.
- Ordinary master pushes no longer start the Windows packaging job.


## 2026-07-17 installer size baseline

- NSIS installer: ~113MB
- Sidecar one-file: ~92MB
- ODA staged tree: ~70MB
- Desktop shell: ~9.5MB
- PyInstaller Analysis binary inventory shows ~270MB raw embedded binaries before one-file packing; top contributors:
  - pyarrow/arrow.dll 66MB
  - pyarrow/arrow_flight.dll 41MB
  - pyarrow/arrow_compute.dll 29MB
  - pyarrow/parquet.dll 21MB
  - numpy OpenBLAS 20MB
  - pyarrow/arrow_substrait.dll 8MB
- Root cause of sidecar bloat: `build-sidecar.ps1` uses `--collect-all pyarrow/pandas/openpyxl/yaml`, which over-includes optional PyArrow modules unused by desktop audit path.
- Streamlit is only for `serve-ui` and should be excluded from desktop sidecar.
- ODA stage currently mirrors full Program Files tree including Qt imageformats and many optional modules; conversion may not need all of them.

## 2026-07-17 Phase 170 installer size reduction

- Implemented slim packaging scripts and rebuilt the Windows NSIS installer.
- Sidecar build path:
  - `build-sidecar.ps1` → `build_sidecar_pyinstaller.py` filtered Analysis
  - removed `--collect-all pyarrow/pandas/...`
  - drops optional PyArrow natives (flight/substrait/dataset/orc/acero/cloud FS)
  - excludes Streamlit/matplotlib; keeps parquet/core for pandas artifacts
  - do **not** exclude `unittest` (pyparsing.testing imports it at import time)
- ODA stage path:
  - after robocopy, prune validated optional set (imageformats, BREP/ACIS DLLs, W3D/Whip, optional `.tx`, libcrypto)
  - keep conversion-critical modules including `RecomputeDimBlock_27.1_16.tx`
- Measured results (local):

  | Metric | Baseline | After slim |
  |---|---:|---:|
  | NSIS installer | ~113 MB | ~85 MB |
  | Sidecar | ~92 MB | ~69 MB |
  | ODA staged | ~70 MB | ~51 MB |
  | Shell | ~9.5 MB | ~9.4 MB |

- Verification:
  - packaging unit tests: `43 passed` (`test_desktop_packaging` + readers + oda_health)
  - sidecar smoke: `--help` and `analyze-project --help` OK
  - pruned ODA convert smoke via ezdxf odafc: 封面 / 交流回路 / 元件接线图 samples OK
- Residual headroom: arrow.dll + OpenBLAS + arrow_compute dominate remaining sidecar weight; further gains need engine dependency redesign, not more packaging filters.

## 2026-07-17 Phase 171 recognition flood diagnosis

### User symptom vs corpus evidence
- Claim: table-type misrecognition / unrecognizable pages still produce ~300 issues per set on test/ 502 DWGs.
- Evidence from `.tmp/phase167_full_corpus_baseline` + `phase167_full_corpus_audit_current3`:
  - 502 pages: **0** unknown page_type, **0** Fallback routes
  - page_type mass: 二次原理图 227, 屏端子图 76, 背板表格型图 55, 封面/目录 54, 元件接线图 52, 屏面布置图 33, 背板接线图 3, 表格型图 2
  - current3 total issues **677** (review 670); max single project **117** (`8000_9000_-`), not 300
  - top-3 projects sum **276** approx user "~300" if multi-cabinet raw rows are treated as one set
  - `root_cause=page_misclassified` **0**; issue mass is 元件接线图 288 + 屏端子图 259 ordinary_pair symptoms
  - real LayoutOnly residual only 3 backplate pages (0 issues): `21000/10 PMU集中器背板`, `28000/12 电能质量监测装置背板`, `30000/10 防火墙接线图`

### Cluster diagnoses (parallel agents)
1. **8000 terminal 16-19**: current3 low-confidence flood is **stale extraction**. Terminal row-array promotion only runs in `TerminalDiagramExtractor` extraction, not `run-audit`. Fresh extraction promotes 208->820 family to pass 0.92; project issues **117 -> 26**.
2. **20000 page 26/27**: correctly routed ComponentDiagramExtractor. Upper FJL strip recovers 16 `component_mapping`. Page 26 -> 0 issues. Page 27 HMC-3C pin-grid **human-adjudicated as silkscreen** → `_shadow_hmc_silkscreen_ordinary_pairs` (reason `hmc_panel_silkscreen`); offline 47/48 stubs shadowed, real KLP/GD/n### endpoints kept eligible.
3. **29000**: KK OF main ports already map 32; OF aux `2->12` groups consumed by `_kk_ignored_auxiliary_group_ids`. Serial media shadow clears page 08; signal-alarm shadow clears page 09 meter face pins. Project issues **33 -> 2** (1 long GC0013 residual + 1 terminal many-to-one).

### Engine generalizations landed
- `component_diagrams._kk_ignored_auxiliary_group_ids`: complete KK2P+OF11-12 consumes short OF aux horizontals (ports 11/12/14) without mapping them.
- `virtual_single_char_reject_blocks`: `FJL-25-2A` + `_Mirror` (+ basename mirror-tolerant match in candidates).
- `pairs._apply_component_pair_guards`: same-block digit<->digit (1-99) discard on **all orientations** (was horizontal-only; vertical covers XJDZ pin columns).
- `page_classifier` serial cues: bare `485` + `TXD\\d*` / `RXD\\d*`.
- `page_extractors`: shadow ordinary pairs on communication media pages; shadow ordinary pairs on signal/alarm sheets (`信号回路` / `电度表告警` / `空开断开告警`) without claiming serial media.

### Fresh replay deltas (head + uncommitted second wave)
| Project | current3 / pre | fresh | Notes |
|---|---:|---:|---|
| 29000 电度表柜 | 33 | **2** | page14 OF cleared; 08/09 shadowed |
| 8000_9000 时钟同步柜 | 117 | **26** | terminal arrays promoted; residual wire/component |
| 20000 主变测控柜1 | 97 | **41** | page26=0; page27 HMC=31; page25 CD residual=6 |

### Residual requiring human / next loop
- HMC-3C silkscreen: **closed** by user adjudication + generalized shadow (not filename-only).
- 20000 page25 residual external `CD*` ordinary pairs (not same-block).
- 29000 page14 long GC0013 `?->3` mixed geometry line.
- Full 502 fresh rebuild required before accepting corpus-wide issue totals (current3 is rules-only reaudit on stale pairs).

### Issue layering (frontend certainty)
- `handling_class`: error / warning / review
- Labels: 确定性错误 / 可能有错误 / 须人工校验
- Principle: 可以误报，但不能错过真实错误 (hard conflicts stay error even at lower confidence)

## 2026-07-17 Phase 170 deep unused-module prune

- Call-site / reachability audit of the desktop sidecar graph:
  - `networkx` is in pyproject but never imported by engine source (only forced previously as a hidden import).
  - `PIL` only required by optional `ezdxf.addons.drawing` (not used for DWG→DXF audit).
  - `jinja2`/`lxml`/`xlsxwriter`/`setuptools`/`requests` are optional/transitive and not needed for desktop artifact I/O.
  - Must keep: `fontTools` (ezdxf fonts import-time), `rich`+`pygments` (typer help/errors), `pandas.testing` (pandas init).
- Builder changes in `build_sidecar_pyinstaller.py`:
  - expanded excludes + pure-module drop list
  - strip pyarrow development DATA (`include/`, `.lib`, `.pyx`, `src/`)
  - force `pandas._config.localization` + keep pandas.testing
- Measured sidecar: **~52 MB** (was ~69 MB after first slim loop, ~92 MB baseline).
- Smoke: `--help`, `analyze-project --help`, `init-config`, `list-recent-projects` all OK.
- Packaging unit tests: 7 passed.

### Residual shadows (post HMC adjudication)
- `component_long_bare_digit`: 元件接线图 ordinary single bare digit (1-99) on line length ≥60 → shadow (closes 29000 GC0013 class).
- `external_designator_derived_ordinary`: CD/GD/ZK raw or derived-numeric ordinary stubs → shadow (closes 20000 page25 CD* class).
- Fail-closed: dual-side non-digit values and real n###/KLP ordinary pairs stay eligible.

### Phase 171 full 502 fresh rebuild (post residual shadows)
- Output: `.tmp/phase171_full_corpus_fresh` + `.tmp/phase171_full_corpus_audit` (27/27 ok, ~283s, 3 workers)
- **Total issues 327** (current3 stale reaudit was 677)
- Routes: Wire 227, Skip 87, Terminal 76, Table 57, Component 52, LayoutOnly 3, UNKNOWN 0
- Handling: error 65 / warning 13 / review 249 (确定性错误 / 可能有错误 / 须人工校验)
- Rules: MANY-TO-ONE 125, LOW-CONF 76, CROSS-PAGE 65, MISSING-SIDE 55, DUPLICATE-PAIR 6
- Key project deltas vs prior fresh: **20000 41→5**, **29000 2→1**, **8000 26→26**
- Top residual projects: 24000(42), 35000(29), WBH(28), 31000(27), 22000(26), 25000(26), 8000(26)
- Top pages: terminal strips (24000 left 21/22), PMU backplates (22000/35000 sheet13), 8000 signal page05

### Residual r3 after endpoint coverage + signal cue broaden
- 8000: **26 → 14** (page05 信号回路图 cleared by filename/title + 失电/失步/异常告警 cues)
- 20000: **5 → 4** (page27 n113 ordinary stub covered by component_mapping endpoint)
- 29000: **1** unchanged (terminal many-to-one on sheet16, likely real/review)
- Remaining 8000 mass: page04 直流回路 missing-side, component pages 14/15, terminal low-conf page16

### 2026-07-17 HMC / shadow safety review

- Human authority: HMC panel artwork is IGNORE; it creates no ports, mappings, connectivity, or union. Suppression must stay local to HMC evidence and must not hide real same-sheet KLP/GD/n### connections.
- `_shadow_signal_alarm_ordinary_pairs` is unsafe because a page-level alarm cue currently shadows every ordinary pair, including real two-sided conflicts.
- `_shadow_component_long_bare_digit_ordinary_pairs` is unsafe because line length plus a lone 1-2 digit endpoint is not proof of artwork; the known 29000 GC0013 missing-side case must remain reviewable.
- `_shadow_external_designator_derived_ordinary_pairs` is unsafe because CD/GD/ZK are valid external endpoint families; missing-side instances must not be silenced by name.
- `_mark_component_mapping_endpoint_covered_ordinary_pairs` is not sheet-scoped: endpoint keys can shadow a same-named endpoint on a different sheet.
- Component-page same-block 1..99 digit-pair discard also applies vertically; existing tests prove the guard executes but do not prove that all vertical same-block digit pairs are internal artwork.
- HMC cue detection currently checks sheet title/filename only when `texts` is empty, so metadata-only HMC titles can be missed whenever unrelated text entities exist.

### 2026-07-17 human adjudication: terminal tables and backplate plug-ins

- Three-column terminal table rule: locate the instance header near the Chinese `说明` heading; combine the header with the middle numeric column (`1C5D` + `10` => `1C5D-10`), then map that logical endpoint independently to each populated side cell (for example `1C5D-10 -> 1n519`). Bare residual `10 -> 519` is not an independent connection.
- Header rows may span multiple port rows. A logical endpoint can validly map to both sides: `1UD-1 -> 1ZKK1-2` and `1UD-1 -> 1n2001`; similarly for `1UD-2`, etc. This is normal fan-out, not many-to-one/internal connectivity.
- BI/voltage plug-in backplates are table-like multi-port components. The upper instance label plus each numbered port forms the endpoint; each port maps outward to the same-side external terminal. Interior labels such as Power/BI/input descriptions are annotations and do not imply internal connectivity.
- The pictured `开入插件/开出插件` blocks follow the same table-like model: numbered ports map to adjacent external designators; empty rows remain unmapped.

### B3/A2 parallel audit results

- Existing `.tmp/phase171_full_corpus_fresh` predates HEAD `0feefcf`; its 24000/25000/8000/20000 residuals are a pre-change baseline, not proof that the current extractor still fails. Current-HEAD fresh replay is required.
- Pre-change B3 residuals: 24000 sheets 21/22 had bare `10 -> 519`-style low-confidence ordinary pairs; 25000 sheet19 had 14 `1 -> n###`-derived ordinary pairs; 8000 sheet16 had four `10..13 -> 106..113` ordinary pairs; 20000 sheet28 had `13 -> 412`.
- Pre-change 24000 sheet23 had seven `R-MANY-TO-ONE` rows over `terminal_header_table` mappings. The repeated endpoint evidence is table-scoped and often reuses the same physical side-cell across multiple logical header rows; human adjudication says this is valid table mapping and must not imply union.
- HEAD `0feefcf` focused tests pass, but the full suite has one stale endpoint-format assertion: extractor now produces `1-21QD-1` while the integration test expects `1-21QD1`. Latest human rule explicitly requires `instance-port`, so the hyphenated logical endpoint is the intended form unless fresh source evidence proves otherwise.
- Fresh 15000 replay confirms A2 is already correct: sheets 14/15 route to `TableExtractor`, each emits 152 plugin-port mappings, Power/BI/Output/AC descriptions do not connect, empty rows do not map, and both pages produce zero issues. The same cluster spans 18 backplate pages.

### Current-HEAD B3 fresh replay

- Fresh extraction on HEAD `0feefcf`: 24000 target sheets 21/22/23 now have 2/0/0 issues; 25000 sheet19 has 0; 20000 sheet28 has 0. 24000 sheet23 explicitly emits `1UD-1 -> 1ZKK1-2` and `1UD-1 -> 1n2001` with no issue.
- 8000 sheet16 retains four low-confidence ordinary residuals (`11->106`, `10->113`, `13->113`, `12->110`). They are table rows under header `1-26TD`; the header and adjacent `说明` are at y≈128.5 while rows 1..13 are above it at y≈201..141. Current `_collect_terminal_header_rows` only accepts rows below the header in coordinate space, so it misses this inverted/header-below layout.
- Safe generalization: when a nearby `说明` anchors the terminal strip, allow consecutive 1..N middle rows on either side of the header, bounded by the nearest same-column header. Do not derive an instance name from external endpoint text and do not globally ignore numeric pairs.
- 24000 sheet21 remaining two issues are cross-page structured table sharing (`1QD-32 -> 1n114`, `1QD-33 -> 1n832`) between terminal-header and backplate virtual mappings. Geometry is valid; a later rule-level closure should require authoritative structured mapping scope rather than name-based suppression.

### B3 closure results

- Plain `YD` is a valid terminal-table instance name only when adjacent `说明` and a consecutive numbered strip provide authority. Fresh 8000 replay emits `YD-10 -> 1-26n113`, `YD-11 -> 2-26n106`, etc.; sheet16 issues 4 -> 0 while independent 100..112 terminal arrays remain active.
- A mixed `terminal_header_table` + `backplate_virtual_table` shared external endpoint is accepted only when every pair independently satisfies the strict authoritative table contract. This closes 24000 `1n114/1n832` redundant cross-diagram reviews without allowing ordinary pairs or incomplete mappings through.
- Rules-only 24000 replay after the bridge guard: total 5 -> 3 and sheets 21/22/23 all have zero issues.

### Fail-closed replay after removing broad shadows

- Fresh totals: 8000=22 (sheet16 B3 remains 0), 20000=19 (HMC sheet27 remains 0), 29000=10. Restored findings are now visible for structural modeling instead of being page/name/length-shadowed.
- 8000 sheet05: 12 missing-side rows are not IGNORE. They are repeated horizontal wire chains with numeric anchors (`105/106`, `108/110`, `111/113`) split into complementary halves; the correct next model is wire-chain/inline-number reconstruction.
- 29000 sheet09: 10 findings are communication/alarm panel silkscreen. Safe IGNORE requires combined evidence: repeated panel-symbol array, DIM numeric labels, matching relative geometry/layers, and no independent port/cross-page evidence. Text values 16/35 and page title alone are not authority.
- 20000 sheet25: six CD/XJDZ low-confidence pairs must become scoped structural mappings retaining complete endpoint identity (e.g. CD11->CD8 and XJDZ instance:port), not name-based shadows. Sheet26 CLP/backplate inconsistencies remain legitimate review and must not be auto-cleared.

- Signal-sheet inline reconstruction is now validated: a 20-unit numeric bridge is used only on signal/alarm sheets, while the default remains 13 elsewhere. Fresh 8000 replay reduces 22 -> 10, clears all 12 sheet05 false missing-side rows, and leaves sheet04/14/15 counts unchanged.
- Repeated panel silkscreen model validated on 29000 sheet09: it uses a communication/alarm routing cue only together with >=4 repeated block rows/columns, nearby DIM 1-2 digit text, no block-owned endpoint identity, and a single-sided ordinary pair. Fresh 29000 replay reduces 10 -> 0; exactly 10 pairs carry `repeated_panel_numeric_silkscreen`.

# Phase 172 packaged ODA crash diagnosis (2026-07-17)

- User logs show repeated ODA File Converter exit `3221226505`, which is hexadecimal `0xC0000409` (`STATUS_STACK_BUFFER_OVERRUN` / Windows fail-fast), not an executable-not-found error.
- `src/dwg_audit/ingest/dwg_converter.py` defaults `convert_workers <= 0` to up to four threads and submits one `odafc.convert` call per DWG, so the packaged run shown can have several native ODA processes active simultaneously.
- Packaged path propagation exists: Tauri sets `ODAFC_PATH` and `DWG_AUDIT_BUNDLED_ODA_DIR`; resources are expected under `resources/oda/ODAFileConverter.exe`.
- Staging copies the full ODA tree and then prunes optional payload, including `imageformats` and selected DLL/TX files. This remains a secondary hypothesis because a missing core runtime normally fails at process load (`0xC0000135`) rather than `0xC0000409` after several seconds.
- Required next experiment: same known DWG set with `convert_workers=1` and `2/4`, using clean output/cache. If only multi-worker mode fails, serialize ODA execution while retaining downstream parallelism where safe.
- Controlled staged-runtime probe used the exact eight filenames visible in the user log. All 8 succeeded sequentially and all 8 succeeded when eight ODA processes were launched together; every process returned `0`, and every output directory contained one DXF. Therefore neither the current staged resource pruning nor concurrency alone reproduces the installed-app crash on this machine.
- The next comparison must inspect the actually installed app's ODA resource tree/path or run the packaged sidecar environment. The installed artifact may differ from the freshly staged repository resources used by the successful probe.
- Root cause isolated by hash/tree comparison: `E:\TMPXJ\oda` is byte-identical to the repository staged ODA tree for every installed file, but the installed tree has 35 files versus 36 and specifically omits `platforms/qwindows.dll` (SHA-256 `FB641C...19828`). The ODA executable itself is identical.
- This missing Qt Windows platform plugin explains the fail-fast `0xC0000409`: ODA starts, Qt cannot initialize the `windows` platform plugin, and the GUI runtime aborts before producing stdout/stderr. The repository-stage direct probe succeeded because it still had `platforms/qwindows.dll`.
- Packaging uses a shallow ODA resource glob, so top-level DLLs are installed while the nested `platforms/` payload is omitted. The fix must make the Tauri resource inclusion recursive and add a packaging regression that asserts the nested Qt plugin is covered.
- Tauri's recursive glob includes nested files but flattens them into the mapped destination; `resources/oda/**/* -> oda/` installed the plugin incorrectly as `oda/qwindows.dll`. The accepted mapping is explicit: `resources/oda/* -> oda/` plus `resources/oda/platforms/* -> oda/platforms/`.
- Final clean proof: packaging tests `7 passed`; Tauri/NSIS build succeeded; silent installation returned `0`; installed `oda/platforms/qwindows.dll` matches the staged plugin hash; installed ODA converted the logged `12 交流电流回路2.dwg` with exit `0` and one DXF output; `git diff --check` passed.


## 2026-07-17 Phase 173: PAC-885G-H held-out evaluation

Artifacts: `.tmp/phase173_pac885g_h/findings/PAC-885G-H` + audit under same tree and `.tmp/phase173_pac885g_h/audit`.

### Does it crash / fail hard?
- **No process crash.** 31 headers valid; ODA converted 27; 4 skip-stable covers; analysis COMPLETE; audit produced 20 review issues.
- **Not false-clean free:** project `clean_conclusion_allowed=True` and `incomplete_page_count=0` despite three backplate/accessory pages with **zero mappings and coverage_ratio 0.0**, and matrix pages with zero recovered semantics.

### Recognition / route table (31 sheets)
| Sheets | Family | Route | Outcome |
|--------|--------|-------|---------|
| 01–04 | 封面/目录/屏面 | SkipExtractor | Expected skip |
| 05,11–22 | 二次原理/信号/通讯 | WireDiagramExtractor | Non-zero pairs; residual missing-side/review noise |
| 06 | 主接线图 | Wire | Near-empty (title only) |
| 07–10 | 出口矩阵图 | Wire (misroute) | Table geometry known; wire pairs all discard |
| 23–24 | 主保护箱背面 | TableExtractor | Good table_mapping |
| 25–26 | 空开/压板背板1 | TableExtractor | **Extract empty** |
| 27 | 压板背板2 | Wire (misroute) | **Extract empty** |
| 28–31 | 左右端子 | TerminalDiagramExtractor | Strong table_mapping; some review issues |

### Error / ignore modes
1. **认不出 / 错路由:** 出口矩阵当导线页；压板背板2 被 grid_heavy 拉成导线页。
2. **抽不出:** 空开按钮/压板背板1 虽进 TableExtractor 但 0 mapping；主接线几乎无几何文本。
3. **错误忽略 / 假覆盖:** 空页全部文本标 `out_of_scope`，项目级 coverage 仍 1.0 且允许 clean conclusion。
4. **误报倾向（review）:** 端子 many-to-one / bare-digit low-conf / 少量 missing-side；未见 severity=error。
5. **符号/尺度未闭环:** 53 unknown symbols, scale UNRESOLVED everywhere — 不阻断但限制跨页几何归一。


## 2026-07-17 Phase 173b: concurrent page drop lists (原图对照)

Three parallel read-only agents produced page-by-page dropped-instance inventories for PAC-885G-H:

| File | Scope |
|------|--------|
| `.tmp/phase173_pac885g_h/page_drop_list_backplates.md` | S0025–27 empty extract: 157 designators |
| `.tmp/phase173_pac885g_h/page_drop_list_matrix_sld.md` | S0006 SLD empty source; S0007–10 matrices CIRCLE marks |
| `.tmp/phase173_pac885g_h/page_drop_list_terminals_backplates.md` | S0023–24, S0028–31 recovered vs dropped + issues |
| `.tmp/phase173_pac885g_h/page_drop_list_MERGED.md` | Chinese executive index |

### Whole-page drops (instances never become pairs on that page)
- **S0025:** 1ZKK*/KZKK/1DK + 1U2D/1VD side tags + 13×1n### all unpaired
- **S0026:** 1CLP1–20, 1KLP1–16, 1KD1–20, 36×1n### all unpaired (0 mappings despite Table route)
- **S0027:** 1KLP17–30, 1VLP1, LP1–3, 15×1n###; Wire misroute
- **S0007–10:** entire trip-matrix connectivity (outlet×function + CIRCLE dots)
- **S0006:** source model title-only (not extractor leak)

### Partial drops on otherwise working pages
- **S0024:** worst residual (92 dropped): NTX310/NZL304 headers, many 1ID/1U2D, ~50 signal ports
- **S0031:** 20 accessory-strip drops
- **S0030:** 8 many-to-one review + CT/VT + 1n2508–2512
- **S0023/S0028/S0029:** near-complete; minor power labels / 1BD / bare-digit review
# Phase 174 desktop UTF-8 and issue preview repair (2026-07-17)

- Screenshot confirms selective corruption rather than a missing CJK font: static Chinese UI labels render correctly, while dynamic issue text, filenames, titles, rationale/details, and some extracted drawing text contain U+FFFD replacement glyphs. English dynamic fields and numeric endpoints remain intact.
- The right preview area remains on `正在生成问题区域预览...`, so generation or response completion is failing independently of the lower details pane rendering.
- `session-catchup.py` itself failed when the Windows console attempted to encode the request's existing U+FFFD characters as GBK. This is supporting evidence that packaged subprocess/stdout decoding and Windows code-page handling deserve direct inspection; it is not yet proof of the application root cause.
- Read-only artifact proof at `.tmp/phase173_pac885g_h/findings/PAC-885G-H/audit/issues.json`: valid UTF-8, 115,150 bytes, 3,356 Chinese characters, zero U+FFFD. Representative raw bytes for `可能有错误` are correct UTF-8 (`E5 8F AF ... E8 AF AF`). Filenames, issue titles/families, handling labels, JSON/MD/HTML outputs are intact. Corruption therefore occurs after artifact generation, in desktop state loading/normalization or a packaged-only bridge path.
- Preview state proof: React clears `isRefreshingPreview` only when the Tauri invoke promise settles; `<img>` load failure has a separate explicit error UI. The screenshot's permanent `正在生成...` means `desktop_render_preview` never returned. Rust `run_sidecar_json_owned` currently uses blocking `Command::output()` with no timeout. Geometry-less issues enter Python's heavier `load_report_frames` path.
- PAC reader provenance reports `capabilities.preview=false`, and the normal audit artifact tree contains no pre-rendered image. This does not by itself preclude generated SVG preview, but it means the desktop must rely on the synchronous render-preview path.
- Actual installed desktop state is `C:\Users\25788\AppData\Local\dwg-audit\desktop_state.db`; the webview directory contains only browser internals. The installed sidecar is `E:\TMPXJ\sidecar\dwg-audit-sidecar.exe`.
- Frontend search found no generic TextDecoder/mojibake decoder. Dynamic payload normalization is concentrated in `App.tsx` issue presentation helpers and `desktopApi.ts`; these exact functions require direct review against the persisted SQLite payload.
- Installed SQLite proof: latest PAC run and representative sheet-30 issue contain correct escaped Unicode in every dynamic field; replacement count is zero across `issue_summaries`, `page_findings`, and `runs`. The bridge from synchronous sidecar stdout to Rust JSON remains the only unverified text boundary.
- Latest run row has `artifact_dir=""`. Preview generation therefore cannot safely assume report parquet frames remain available after workspace cleanup.
- Definitive installed-sidecar byte probe: `load-result` exits 0 and emits 226,910 stdout bytes that are valid GB18030 but invalid UTF-8 (first invalid byte `0xB1` at offset 1209). Rust `String::from_utf8_lossy` produces 5,411 U+FFFD characters, matching the screenshot. Root cause is the windowed PyInstaller synchronous CLI stdout using the Windows code page; `DesktopEventWriter`'s UTF-8 reconfigure only covers analyze-session events.
- Installed `render-preview` now exits 2 with a clear ASCII error: `Page S0030 does not have ...` because the stored run has no artifact directory/page frames and the issue lacks direct line geometry. The UI must not spin forever even when a sidecar is slow, and the preview generator should return a useful SQLite-only fallback for this case rather than requiring purged artifacts.
- `analyze_session(..., compact_after_store=True)` intentionally compacts/deletes the session workspace immediately after persisting SQLite and clears every run's `artifact_dir`. Therefore artifact-backed preview is unavailable by design for normal desktop runs; only issues with retained direct line geometry currently render. Table/many-to-one issues like S0030 inevitably hit `Page ... does not have a usable extent bbox.`
- The encoding fix belongs at the packaged sidecar entrypoint before Typer runs, so every synchronous JSON command uses UTF-8 stdout/stderr. A producer-side UTF-8 contract is preferable to teaching Rust to guess GB18030 and keeps existing strict event streaming consistent.
- Preview fix should preserve compaction while returning an explicit SQLite-only SVG card for issues without coordinates, plus a frontend bounded timeout so the inspector cannot remain in a permanent loading state.
- Existing regression homes are `tests/unit/test_desktop_lifecycle.py` for post-compaction SQLite preview, `tests/unit/test_sidecar.py` for SVG rendering, and `tests/unit/test_desktop_packaging.py` for the packaged entrypoint contract.
- Existing lifecycle coverage proves SQLite-only preview only for direct `line_start/line_end` evidence. Add the missing no-geometry case and assert an SVG fallback is written with `source=sqlite_summary`, `focus_bbox=null`, and no false claim of CAD localization.
- Frontend effect has no deadline around `desktopApi.renderPreview`; add a small reusable promise deadline (about 20 seconds) so state always leaves loading and maps the timeout through the existing Chinese error helper.
- Source-level real PAC proof after the fix: packaged-entry module `load-result` emits 231,279 bytes of strict UTF-8 with zero U+FFFD and preserves Chinese filename `23 主保护箱背面接线图1.dwg`. `render-preview` for S0030/I0024 exits 0, returns `source=sqlite_summary`, contains Chinese `无坐标定位`, and reports `focus_bbox=null` rather than inventing geometry.
- Targeted Python tests pass `18 passed`; desktop TypeScript check passes.
- Browser-rasterized real S0030/I0024 SVG was visually checked: Chinese title, filename, issue title, terminal pair, rule label, table direction, and no-coordinate warning all render cleanly; the card does not draw a false CAD highlight.
- Release build succeeded with a 52.2 MB sidecar and 72,002,609-byte NSIS installer. Silent install to `E:\TMPXJ` returned 0.
- Final installed-binary proof: `E:\TMPXJ\sidecar\dwg-audit-sidecar.exe load-result` emits 231,279 strict UTF-8 bytes with zero U+FFFD and intact Chinese filename; installed `render-preview` for S0030/I0024 exits 0 with `source=sqlite_summary`, Chinese SVG content, and `focus_bbox=null`.
- Final gates: full unit suite `953 passed, 1 skipped`; TypeScript check and production frontend/Tauri/NSIS builds pass; oxlint exits 0 with three existing `useEffectEvent` dependency warnings; `git diff --check` passes.

## 2026-07-17 Phase 175: S0025 CD/XJDZ structural mapping recovery

- Recovery found `master == origin/master == 4590b37`; root `package-lock.json` remains unknown and excluded. Four tracked files contain existing uncommitted work (`coverage.py`, `table_extractor.py`, `artifacts.py`, `test_coverage.py`) and must be reviewed/preserved before integration.
- Six clean Luna probes were dispatched with `fork_context=false`, returned, and were immediately closed.
- Highest-probability S0025 failure chain: `_EXTERNAL_ENDPOINT_PATTERN` rejects an otherwise structured endpoint carrying a terminal suffix such as `XJDZ9-02-2B4-001:8`; `_strip_external_endpoint_values()` then drops it, `extract_strip_two_port_component_pairs()` cannot cover the supporting line group, and generic pairing leaks bare-number review pairs such as `11 -> 8`.
- Source evidence for S0025 is `test/.../20000 主变测控柜1/25 元件接线图2.dwg` (`S0025/F0025`). Representative CD texts include `3-21CD6`, `1-21CD6,1-21ZK-9`, `2-21CD6`, and `2-21CD11`; XJDZ instance text occurs near the corresponding terminal arrays.
- Required structural examples remain: `3-21CD6 -> XJDZ9-02-2B4-001:8`, `1-21CD6,1-21ZK-9 -> XJDZ9-02-2B4-001:7`, `3-21CD11 -> 3-21CD8`, `1-21CD11 -> 1-21CD8`, `2-21CD6 -> XJDZ9-02-2B4-001:8`, and `2-21CD11 -> 2-21CD8`. Exact final separator normalization must be derived from current source text/geometry rather than fingerprint memorization.
- S0026 is a required negative guard, not noise: backplate sheets S0020-S0022 state `1/2/3-21CLP9-2 -> 1/2/3-21n425`, while S0026 geometry extracts the same CLP9 port to `n427`. This is a real cross-page endpoint conflict and must remain review-visible even though each component mapping is individually high-confidence.
- Current PAC held-out replay at `.tmp/side_pac_matrix_replay` has 70 issues: 63 missing-side on sheets20-22, 3 low-confidence on sheet29, 1 backplate scope conflict cluster, and 2 many-to-one issues on sheet30. It is current-HEAD evidence only; it does not cover the present uncommitted changes.

### Phase 175 implementation and replay results

- Review of the inherited matrix coverage patch found a high-severity false-clean defect: PAC S0007-S0010 had zero recovered mappings, yet 438 bounded texts would have been marked `semantic_evidence`. The accepted repair derives structural text IDs only from actual recovered mapping references and ignores empty mapping sets. Focused coverage/table tests pass `33 passed`.
- The first XJDZ binder replay restored 32 measured candidates but incorrectly attached TEXT-layer stroke lines and produced false pin-to-CD mappings. TEXT lines are now excluded from symbol line attachment; this error was not hidden or accepted.
- S0025's six residuals are definition-owned XJDZ structural routes, not generic outward wires. A strict ComponentDiagram postprocessor requires an XJDZ-owned line group and then preserves either full hierarchical endpoint text or `XJDZ-definition:pin`; it emits no-union `component_mapping` evidence.
- Adjacent XJDZ definition lines can merge into one vertical line group. Native-pin `source_block_name` selects the owning definition; ambiguous groups without a unique pin owner remain review.
- Repeated `XJDZ-definition:pin` values on different INSERT handles are scoped as distinct physical instances for cardinality rules. Same-instance duplicate sources still emit `R-MANY-TO-ONE`.
- Fresh S0025 replay5 emits exactly six pass mappings and zero semantic issues: `3-21CD6 -> XJDZ9-02-2B4-001:8`, `1-21CD6,1-21ZK-9 -> XJDZ9-02-2B4-001:7`, three scoped `CD11 -> CD8` mappings, and `2-21CD6 -> XJDZ9-02-2B4-001:8`. The isolated page-number mismatch is an input-copy artifact.
- Fresh full 20000 replay (`.tmp/phase175_20000_replay1/20000_1`) has 13 reviews: S0020=4, S0021=4, S0022=2, S0026=3. S0025 is zero. The three S0026 reviews retain values `CLP9-2`, `n425`, and `n427`, proving the true cross-page inconsistency remains visible.
- Verification after these changes: related engine suites `312 passed`; complete repository `993 passed, 1 skipped`; diff whitespace gate clean.

### Phase 175 fresh 502-corpus acceptance

- Full repository after backplate authority generalization: `994 passed, 1 skipped`.
- Fresh run used the frozen 27-project manifest (502 DWGs), three concurrent project workers, per-project manifest count validation, and separate analyze/audit processes. Runtime was 414.7s.
- The first runner postcondition incorrectly required audit-v2/failure-queue files in the external `run-audit` root; those files are produced under each analyze project's internal `audit/` directory. Analyze and audit subprocesses themselves succeeded for every project. This was an acceptance-runner error, not an extraction failure.
- Independent validation of the produced bundles confirms: 27/27 valid projects, 502/502 valid DWGs, every extraction `COMPLETE`, incomplete pages 0, all internal audit-v2/failure-queue artifacts present, and internal/external issue counts identical.
- `evaluate-corpus-census` reports `VALID` and `all_projects_valid=true`. Extraction verification reports 27 REVIEW, 0 FAIL, 502 page rows; REVIEW is driven by known coverage/scale/unknown-symbol evidence rather than incomplete extraction.
- Current fresh corpus has 170 issue instances: `R-MANY-TO-ONE=111`, `R-PAIR-MISSING-SIDE=46`, `R-CROSS-PAGE-CONFLICT=8`, `R-PAIR-LOW-CONFIDENCE=4`, `R-DUPLICATE-PAIR=1`; one issue is critical.
- Highest-count projects: 35000_2=53, 110kV transformer protection set=19, 31000/32000=17, 26000=14, 10000=11, 23000=10, 8000/9000=10. These are the next fresh-loop priorities.
# 2026-07-17 Phase 176 B3/A2 human-confirmed semantics

- User crop 1 is a BI/voltage-style backplate plug-in. Odd/even numbered pins are independent external ports; the table body describes channels and must not imply pin-to-pin electrical union.
- User crop 2 is an authoritative three-column terminal table headed `1UD`. The middle column `1..9` is the port number, so logical endpoints are `1UD-1` ... `1UD-9`. Each logical port may have two valid external mappings, e.g. `1UD-1 -> 1ZKK1-2` and `1UD-1 -> 1n2001`; the two external targets are not thereby unioned through the component.
- User crop 3 is a normal open-input/open-output backplate. Numbered pins on both sides map independently to external `1-25QD*` endpoints; empty rows remain unmapped.
- Six parallel read-only audits found that current fresh artifacts already produce 152 high-confidence `backplate_virtual_table` mappings on each of 15000 S0014/S0015 with zero page issues, but no electrical union eligibility. This is the desired A2 authority boundary.
- Current B3 `terminal_header_table` extraction exists on 24000/25000/8000/20000, but old 24000 S0021/S0022 artifacts still contain residual bare-number ordinary pairs. The next fresh replay must prove those are shadowed by structured header mappings.
- A probe reported that 24000 S0023 contains no `1UD`; visual evidence proves the semantic model but not that page identity. Treat the probe as a scope mismatch and locate the exact source page before changing page-specific behavior.
- Independent safety review found the latest page-local `numeric_three_column` cross-page guard and opposite-side terminal-header many-to-one guard are too broad unless backed by explicit structural scope. Both require adversarial negative tests before acceptance.
- The exact fresh 24000 S0023 evidence proves `1UD` extraction already existed, but the previous broad x tolerance stole neighboring-table endpoints. Final ownership combines nearest-per-side selection with competing-header same-y row identity: an endpoint closer to another table is shared only for a same-number `n` row or an explicit known `header+row` reference.
- Final fresh 24000 replay preserves exactly 16 authoritative `1UD` mappings: rows 1-4 and 6-9 map to both outer sides; blank row 5 maps nowhere. It also preserves sparse reciprocal `UD-4 -> 1UD4`, `UD-9 -> 1UD9`, shared `1I4D-1/1I13D-1 -> 1n2401`, and `1I13D-1 -> 1n2507` from a vertically non-overlapping neighbor block.
- Page-local `numeric_three_column` facts now require exact row_index/text-id/column-role evidence before bypassing cross-page cardinality. 30000 rules replay is 0 issues; scoped/header-bearing negative cases still report conflict.
- Terminal-header many-to-one suppression now requires a closed reciprocal center-strip topology after separator-insensitive endpoint normalization. Same-row/same-name coincidences without the reciprocal strip remain review. Final fresh 35000_2 replay is 5 issues, all the pre-existing S0010 open-end `R-PAIR-MISSING-SIDE`; terminal-chain `R-MANY-TO-ONE` is 0.
- A2 remains a non-union structured table authority: 15000 S0014/S0015 each retain 152 high-confidence backplate mappings and zero page issues, while `electrical_union_eligible_count` remains 0.
- In the final 533-DWG fresh run the generalized A2 extractor recovered 158 pass mappings on each 15000 S0014/S0015 (up from the earlier 152 evidence) while the project remained at 0 issues; no electrical union was introduced.
- Full fresh acceptance is structurally healthy: 28 projects, 533 pages, 0 incomplete, 0 critical. Non-PAC issue count is 127; PAC-885G-H alone contributes 75 review issues, led by 64 missing-side, and remains the next fail-closed audit target.
- PAC S0025/S0026/S0027 are no longer empty: they now contain 40/88/36 component mappings (164 total), full scoped coverage, and zero page issues. The 64 PAC missing-side reviews instead cluster on wire sheets 20–22 (56 template-like rows), sheets 14–15 (7 open-end candidates), and one bare-local-number noise case on sheet 05.
- PAC's seven many-to-one findings are all structured table mappings. Two are reciprocal terminal chains and five bridge backplate/terminal scopes; evidence is not yet strong enough to erase all seven without risking true shared-terminal errors, so they remain fail-closed review.

# 2026-07-17 Phase 177 PAC signal-output endpoint evidence

- Parallel read-only probes confirmed PAC S0020 contains 20 and S0021 contains 19 missing-side ordinary pairs where the opposite endpoint text is present as a device endpoint such as `1XD3`, `1XD4`, `1XD28`, or `1XD49`; these texts were rejected by the numeric-only candidate channel as `not_numeric`.
- This evidence contradicts a blanket `template_endpoint`/open-end suppression for sheets 20–21. The correct first fix is a strict schematic logical-endpoint candidate that can pair `numeric <-> 1XDxx` while remaining distinct from numeric candidates and electrical union semantics.
- S0022 has 17 missing-side pairs and mixes the same repeated 30-unit horizontal templates with long routes ending at the right-side bus. Its `115` template is shifted to about `114.743938`; matching must tolerate local translation/float drift rather than memorize absolute coordinates.
- The long `114.74 -> 392.5` groups are composite topology, not one reusable primitive. They must not be blindly reclassified or completed without endpoint text evidence.
- Safe implementation boundary: WireDiagramExtractor only, endpoint text must strictly match a schematic device-terminal grammar, be spatially attached to the relevant line-group endpoint and same row, and form a complete Pair with an independently accepted numeric endpoint. Isolated annotation text, remote text, non-Wire pages, and genuine textless bus/open ends remain negative cases.
- The engine already has a fail-closed `wire_logic_endpoint_channel`, opposite-numeric-side scoping, pair evidence (`wire_component_mapping`), and a missing-side endpoint-radius extension. Phase177 should extend this existing grammar rather than introduce a parallel candidate/pair kind. The present grammar simply omits compact device endpoints such as `1XD28`.
- Corpus-wide evidence contains 318 strict `number+XD+number` texts, but only 162 are on schematic pages; backplate and terminal pages must remain excluded by the existing sheet-category gate. Candidate geometry has a strong bimodal row pattern: true-row examples cluster around `dy=1–3.5`, while adjacent rows commonly appear at `dy=7–9`.
- A compact-device gate of `abs(dx) <= 4` and `abs(dy) <= 4` covers the inspected PAC mappings (`1XD3 -> 723`, `729 -> 1XD28`, `531 -> 1XD49`) while rejecting the same label when merely visible to a neighboring 10-unit row. This gate applies only to compact `XD` endpoints; existing long hierarchical designators retain their current radius behavior.
- Fresh PAC replay proves the gate removes all 20 S0020 missing-side issues and creates 49 line-backed `numeric <-> 1XDxx` mappings. Exactly 118 adjacent/out-of-row XD candidate relationships remain explicitly rejected; S0021/S0022 are unchanged because they contain no compact XD endpoint text.
- The 49 direct mappings coexist with 29 structured `1XDxx -> 1n...` mappings. This represents the same physical terminal used by internal and external routes, not an electrical union between independent component ports; no new PAC cardinality or cross-page issue was introduced.
- Human-confirmed PAC S0014 semantics: the white rectangular `1F1` device exposes independent outward ports and is not internally electrically connected. Required mappings are `1F1-1 -> 1VD1` and `1F1-2 -> 1701`; the same geometry/text contract should generalize to sibling `1F2`, `1F3`, and `1F4`, not be memorized by instance name.
- Fresh S0014 evidence shows four repeated horizontal `SYMB2_M_PWF98` instances. Current line grouping spans through the component and emits only `? -> 1701/1707/1704/1710`; left `1VD1/1VD6/1VD3/1VD8` texts are present but rejected as non-numeric. Explicit port texts `1/2` and the rectangular body geometry are also present.
- Corpus risk scan found only eight `number+F+number` instance texts: four S0014 schematic positives and four S0025 backplate negatives. The safe model therefore cannot be name-only; it must require schematic route, closed rectangular body, two outward horizontal leads, explicit left/right port texts, same-row endpoints, and non-degenerate geometry.
- Existing `backplate_components.py` already defines the correct output contract (`component_instance`, `port_number`, `logical_endpoint`, independent outward mappings, `internal_connectivity=False`, `electrical_union_eligible=False`). A new horizontal schematic-body recognizer can reuse that evidence model while keeping the existing backplate and component-diagram routes separate.
- Direct artifact inspection corrected the initial block attribution: the central component INSERTs are `SYMB2_M_PWF20` at each row's left inner lead boundary; `SYMB2_M_PWF98` are right-side endpoint symbols. Recognition must therefore use the generic INSERT-in-gap geometry, not either definition name.
- Each positive row has two distinct free CONNECT leads (about 27–30 units) separated by a 10-unit gap, free port labels `1/2` at the two inner lead ends, an instance label 2 units above the gap center, and external endpoint text at each outer lead end. This is sufficient geometric ownership evidence even though the reader does not expand the central block's primitives into `lines.parquet`.
- Replay2 proves S0014/S0025 form eight cross-page corroborating component-port pairs: port 1 values are exact matches; port 2 values differ only by schematic bare number versus backplate `1n####` notation. These pairs must remain separate page evidence and must not create electrical union.
- Missing-side integration gap: component endpoint shadowing exists in `page_extractors.py` but runs only inside the ComponentDiagramExtractor branch. Supplemental AccessoryBackplate pairs are added later in `pipeline.py`, so a final same-sheet, single-sided ordinary-pair shadow pass is required after all routes are merged.
- Cardinality integration gap: cross-page and duplicate rules compare raw endpoint strings and treat corroborating `component_mapping / inline_two_port_component` pairs as conflicts. Safe equivalence requires the same logical component-port, authoritative geometry on both pages, distinct pages, and endpoint equality after a narrow backplate `1n#### -> ####` comparison-only normalization; true mismatches such as `1701` vs `1702` remain errors.
- Fresh replay3 closes the full S0014 chain: eight pass component mappings, all four residual ordinary stubs marked same-sheet shadow-only, zero S0014 issues, zero new duplicate/cross-page findings, and no electrical union. S0020 remains zero issues and PAC critical count remains zero.
- Phase177 full-current extraction completed for all 28 projects / 533 DWGs in 698.3s; all 533 pages are `COMPLETE`, incomplete=0, and the external audit has 0 critical issues. The full repository gate before final cardinality integration is `1021 passed, 1 skipped`.
- The generalized schematic two-port recognizer also found six valid `1ZKK*` mappings on 24000/25000 S0009. Independent geometry review proved each component has two outward leads separated by a 20-unit internal gap, explicit ports 1/2, and no internal connection; historical taskbook semantics independently require the same `instance-port -> outward endpoint` model.
- The resulting four 24000 duplicate findings are exact cross-diagram corroboration between `schematic_inline_two_port` and `kk_multi_port_component`, not duplicate extraction on one page. The new 24000/25000 many-to-one rows occur only where that schematic mapping joins an authoritative `backplate_virtual_table` endpoint on a different page.
- Safe rule boundary: accept only complete high-confidence schematic-inline mappings with `geometry_insert_backed_inline_two_port`, explicit no-union evidence, distinct sheets, and either an exact same component-port mapping from the KK component extractor or one authoritative backplate virtual-table mapping. Existing KK/table shared-endpoint reviews without the new schematic geometry must remain visible.
- Final strictness review added two geometry/provenance guards: the INSERT origin must anchor the left inner lead endpoint, and port/body/external labels must be free page text rather than borrowed block attributes. Fresh affected-project replay preserves all 14 valid mappings (PAC 8, 24000 4, 25000 2).
- Component endpoint shadowing no longer aliases arbitrary trailing digits. Only an optional numeric scope before an `n###` terminal is normalized (`1-2n414 <-> n414`); `1XD28` cannot shadow a separate bare `28`. All six existing full-corpus component shadows remain valid through exact text/raw identity or the strict n-terminal alias.
- Final authoritative evidence roots are `.tmp/phase177_full_533_fresh` and `.tmp/phase177_full_533_audit2`. They cover 28 projects / 533 pages, every project `COMPLETE`, 0 incomplete, 178 issues, and 0 critical. Relative to Phase176, PAC alone changes `75 -> 51`; every other project retains its exact issue count.
- Final rule counts are `R-CROSS-PAGE-CONFLICT=11`, `R-DUPLICATE-PAIR=1`, `R-MANY-TO-ONE=69`, `R-PAIR-LOW-CONFIDENCE=11`, and `R-PAIR-MISSING-SIDE=86`. PAC contributes 51; the non-PAC corpus remains 127.
- Both repository test entrypoints now work because pytest explicitly includes the repository root for `tests.support` imports. Final gate: `1027 passed, 1 skipped`; compileall and diff whitespace checks pass.

# 2026-07-18 Phase 178 final-533 residual evidence loop

- Six clean-context read-only audits covered the highest-volume residual families and were closed after one round.
- PAC S0021/S0022 contain 36 textless one-sided horizontal routes. Every known side has a numeric text, every missing side has no candidate text, and canonical/network evidence marks the geometry as open. These must not be fabricated into complete mappings; a future open-continuation classification needs stronger evidence than open degree alone so genuine omitted labels remain visible.
- 22000/35000 S0010 each contain two duplicate `605` component/dimension continuations plus real independent `TD1..TD4` routes. Suppression must prove shared text plus component/DIM continuation ownership; value-only `605/606` suppression would hide valid routes.
- 26000/31000 contain four duplicate-line/text-ownership clusters (eight ordinary pairs) and six genuine or unresolved open ends. The repair belongs in same-sheet candidate ownership, not cross-page value completion.
- Component-page bare digits in 10000, 8000/9000, and 21000 are not confirmed opens or ignore symbols; they are missing component-terminal mappings and require a separate geometry model before removal.
- In 23000/26000/31000, 25 of 29 component/table many-to-one reviews are cross-diagram shared-endpoint corroborations; four have same-sheet component-chain competition and must remain review. WBH contributes 13 more structured many-to-one corroborations plus five table-template scope conflicts.
- Safe next rule slice: exactly one complete high-confidence component mapping plus exactly one authoritative table mapping on a different sheet, sharing the exact external endpoint, with no same-sheet component mapping whose logical endpoint starts a component chain at that shared value. Keep groups with multiple table rows, same-sheet competitors, incomplete evidence, or raw string-only coincidence.

## Phase 178 rule-safety verification (2026-07-18)

- The first component/table bypass draft was too permissive at the rule boundary: `_high_confidence_pairs()` intentionally admits all `table_mapping` sources for graph inspection, so the bypass itself must enforce authority. It now requires the table pair to be `pass` and at least `0.95` confidence. Tests prove both `review` and `0.90` table rows retain `R-MANY-TO-ONE`.
- Same-sheet component-chain protection now uses `_terminal_endpoint_identity()` for the competing component's logical endpoint. This catches case/separator variants such as `1-21n427` versus `1-21N427`; the new regression retains the conflict.
- Duplicate missing-side ownership was changed from “adjacent to any existing member” to complete-linkage. Synthetic intervals `[0,100]`, `[60,160]`, `[120,220]` now produce one grouped duplicate issue plus one independent missing-side issue, rather than erasing the third line's review.
- Fresh rules-only replay output: `.tmp/phase178_full_533_audit4`. It contains 28 project outputs and exactly 133 issues, with no critical rows. Comparing issue identity tuples against `.tmp/phase178_full_533_audit3` yields zero additions or removals; this proves the new guards only affect adversarial/unit cases and do not alter current corpus semantics.
- The remaining 133 rows are still evidence-backed review work. In particular, PAC S0021/S0022's textless open routes remain unresolved by design, and real `605/606` continuation rows are not suppressed by value alone.
- Final local gates are `1037 passed, 1 skipped`, `104 passed` for the rule unit module, `python -m compileall -q src`, and `git diff --check`.

## Phase 179: equipment-panel proposal feedback and TS3000 boundary

- The remaining panel evidence-completeness fix belongs to `mark_ignored_equipment_panel_ordinary_pairs` in `src/dwg_audit/audit/page_extractors.py` (around line 611), with its pipeline-level regressions in `tests/unit/test_page_extractors.py`. The symbol family classifier itself is not the location of the runtime `fingerprint`/`definition_fingerprint` compatibility gap.
- Direct source inspection refines the handoff assumption: `SymbolPortProposal.to_dict()` currently emits `definition_fingerprint`, `cad_extract.py` spreads that payload unchanged, and `apply_human_symbol_policy_to_proposal_row()` copies the source row before adding policy fields. The persisted proposal artifact is a wrapper object with a `proposals` array, so a top-level array probe returning no rows is not evidence that the fingerprint key is absent. Inspect the nested real rows and pair evidence before adding any compatibility fallback.
- Nested artifact evidence proves the defect is real but farther downstream: Phase179 recheck2 persists non-empty `definition_fingerprint` for WYD, NGFW, and DGICOM proposal rows, while 141 shadowed Pair records serialize `ignored_panel_definition_fingerprint: null`. `classify_definition_family()` does not return or overwrite either fingerprint key. The pipeline input assignment must therefore be traced before deciding whether the narrow fallback is sufficient.
- The accepted evidence repair is deliberately non-authoritative: only after a row already satisfies the complete equipment-panel family/behavior contract does Pair evidence select `definition_fingerprint or fingerprint`. A legacy-key regression retains all family/behavior gates, while the normal-key regression proves current serialization stays intact.
- Fresh-533 disproved that field-alias repair as sufficient. CLI loads the repository source and contains the fallback, yet all panel-shadow Pair evidence remains null. The root cause is lifecycle ordering: `cad_extract` creates runtime proposals with `definition_fingerprint=None`; `report/artifacts.py` later binds a unique fingerprint from `symbol_definitions_v1` before writing `symbol_port_definition_proposals.json`. Pair suppression runs before that report-only enrichment. Fix the runtime proposal producer or pass the existing definition inventory mapping into the Pair stage; do not add more consumer-side key guesses.
- The canonical hash implementation is `audit.symbol_registry.definition_fingerprint_from_children()`. `build_project_symbol_inventory()` derives fingerprints from normalized non-INSERT primitive children and the report writer uses that inventory to enrich proposals. The runtime-safe repair is to bind proposals from the already-collected `primitive_segments` before returning `CadExtractionResult`, preserving the exact inventory hash rather than hashing block objects with a second algorithm.
- `PrimitiveSegment` is a dataclass carrying the exact child-signature fields, and all project segments exist before `CadExtractionResult` returns. A single `asdict` pass grouped by definition name plus the canonical helper reproduces report inventory binding without another DXF walk. Complexity is linear collection plus per-definition signature sorting; no ODA or page-level memory multiplier is introduced.
- Fresh 28000 proof after runtime binding: DGICOM3000's Pair evidence fingerprint equals the finalized proposal/inventory fingerprint `cb1abae...d325`; `GC0066` remains a strict `ignored_equipment_panel_mark_callout`; audit contains exactly one unrelated retained S0017 `231 -> 21` issue. The lifecycle defect is fixed without changing the semantic issue delta.
- Phase179 source review confirms the TS3000 classifier and extractor use independent fail-closed gates: full repeated pin cycles/protocol diversity/high-density geometry at classification, then component-page route, visible scoped instance/model, same-source horizontal lead, same-row external endpoint, and contiguous-row evidence at extraction. Focused affected-module tests pass `240 passed` and `git diff --check` passes.
- Residual audit risk: component-table virtual texts are grouped by `source_block_name`, and `_resolve_component_panel_instance()` selects the nearest free instance/model pair without explicitly separating multiple placements of the same definition on one sheet. Also, row matching scans all sheet line groups for each candidate endpoint. Inspect handle provenance and real corpus multiplicity before accepting or adding an instance-bound/performance index.
- Old Phase177 proposal artifacts produce zero matches under the new component-table classifier and cannot substitute for a fresh extraction because the required geometry statistics belong to the current extraction path. Phase179 real virtual handles do expose placement prefixes (`3214C:*` on S0014 and `3205D:*` on S0015), while each target sheet has one TS3000 placement. Keep multi-placement binding as a later generalization guard instead of expanding this validated batch without a failing corpus case.
- Route integration is ordered correctly: component-table pairs and table mappings are added inside `ComponentDiagramExtractor`; proven row/header group IDs shadow ordinary pairs before component mappings are appended, and project-level authoritative component coverage runs afterward. Terminal-table assignment remains isolated to the terminal route.
- The repository has no dedicated full-corpus runner under `scripts/`. The authoritative reusable entrypoints are the CLI `analyze-project` and `run-audit`; a Phase179 wrapper must derive only real project roots from `test/` and audit the known per-project findings directories, never enumerate output-root helper directories such as `cache/` or `logs/`.
- CLI contracts are `analyze-project --input DIRECTORY --output DIRECTORY` and `run-audit --findings DIRECTORY [--output DIRECTORY]`. `discover_project_roots(test/)` returns every parent directory that directly contains DWG files when the input root itself has none, so one root-level analyze command covers all projects without manual naming. Audit enumeration must still target generated project directories that contain `findings/`.
- Phase179 full fresh extraction completed in 705.8 seconds: 28/28 projects COMPLETE, 533 files/sheets, 533 valid DWG, 0 invalid, 0 incomplete. Sequential audit completed in 119.7 seconds and emitted all 28 project reports.
- Audit delta is 133 -> 118 with zero added issue identities. The 15 removals are 10000 panel rows (8), 21000 panel rows (2), TS3000 rows/header frames (4), and one 28000 DGICOM3000 strict MARK callout. The extra 28000 removal is covered by the same human-confirmed complete communication-panel IGNORE authority, but its null fingerprint evidence exposed the runtime lifecycle defect above.
- Final post-fix evidence is `.tmp/phase179_full_533_fresh2` plus `.tmp/phase179_full_533_audit2`: 28/28 projects, 533/533 valid DWG, 0 invalid, 0 incomplete, and 118 issues (117 review, 1 minor, 0 critical). Its issue identities exactly match the first Phase179 full audit, proving runtime fingerprint binding changes evidence only.
- Final TS3000 contract: 288 mappings, 144 per S0014/S0015; each sheet has slot counts 4/5/6=32 and 7/8=24. Row 32 maps `1-26n432 -> 1-26TD46` and `2-26n432 -> 2-26TD46`. The only 8000/9000 issues are four S0004 open endpoints (`1201/1204` twice each).
- Corpus-wide panel evidence contract: 221 shadowed ordinary pairs (214 panel geometry, 7 strict MARK callouts), with zero missing and zero mismatched fingerprints against finalized proposal inventory. 10000 and 21000 each audit to zero issues; 28000 retains one unrelated S0017 issue.
- Final extraction time is 723.3 seconds versus the pre-binding 705.8-second run (+2.5%); this is within full ODA conversion variability and shows no multiplicative performance regression from the linear primitive grouping.
- Documentation authority remains explicit: `doc/human_arbitration_phase98.md` is the sole human-adjudication history, while `doc/任务书.md` owns active implementation requirements. Phase179 must append rather than replace history, preserve fingerprint as provenance only, keep IGNORE CAD sources observable, and retain the rule that component port mappings never imply internal union.
- The symbol inventory pipeline persists raw proposals before family classification. Pair-level consumers therefore cannot assume `family_id` or `behavior_mode` is present; they must apply `apply_human_symbol_policy_to_proposal_row(...)` before selecting geometry authority. Real 10000/21000 fresh replay exercised this raw-proposal path.
- Whole-panel suppression is accepted only for complete `communication.equipment_panel_ignored.v1` geometry with `behavior_mode=IGNORE`, `allow_port_emission=False`, and `allow_external_attachment=False`. Definition names alone are not authority.
- Free MARK callouts near a panel require a horizontal MARK line, one bare numeric side, vertical distance at most 30 units, x-overlap with the panel, a nearby equipment-model label, and a scoped `1-40n`-style label. Missing any conjunction leaves the Pair reviewable.
- `TS3000-Z01` is a counterexample to the broad `large-text-dense-drawing-metadata-v1` fallback. Its high text/line census and size resemble metadata, but repeated aligned numeric ports and outward TD endpoints make it a structured electrical table. The classifier and extractor must preserve these rows while retaining real drawing metadata as a negative class.
- Confirmed target evidence from the existing baseline includes S0014 `PC0029` row 32 to `1-26TD46` and S0015 `PC0237` row 32 to `2-26TD46`; adjacent rows 27–31 continue to TD39/40/43/44/45. S0014/S0015 port-1 duplicate ownership and S0004 `1201/1204` open lines require separate fail-closed review.
- TS3000's complete logical identity is not the model label. S0014 free text `T2175=1-26n` plus bank header `4` plus port `32` forms `1-26n432`; S0015 `T2800=2-26n` forms `2-26n432`. The model text `TS3000-Z01` is provenance for the table container.
- Cross-page proof exists on S0006/S0009: high-confidence wire pairs already map bare `432` to `1-26TD46` / `2-26TD46`. The component-table pages must emit `1-26n432 -> 1-26TD46` and `2-26n432 -> 2-26TD46`, retaining scoped identity rather than flattening it to a naked number.
- Banks 4, 5, and 6 have populated outward TD rows; rows 27–32 map respectively to TD39/40/43/44/45/46, TD87/88/91/92/93/94, and TD135/136/139/140/141/142. Banks 7/8 have cells but no outward TD text and must remain unmapped.
- `GC0029/GC0237` merge the bottom border with the row-32 lead. The correct repair is a source-block-owned structured row mapping that shadows the ordinary Pair, not a generic missing-side completion or whole-panel IGNORE.
- Final fresh behavior: each TS3000 page emits 144 independent rows: banks 4/5/6 have 32 mappings each; banks 7/8 have 24 each and correctly omit their unpopulated 27–32 rows. All 288 associated ordinary line groups are ineligible for audit.
- The residual bank-1 duplicate was structural: `1/MGM` sits inside a 40-by-5 header cell whose LINE and LWPOLYLINE borders both borrowed the slot-number text. Once the same source block is proven as a structured table, these short enclosing borders are table structure, not electrical missing sides.
- `.tmp/phase179_ts3000_audit2` contains only four S0004 missing-side rows (`1201/1204` twice each), exactly preserving the fail-closed open-end guard. It contains no S0014/S0015 issue and no new many-to-one/cross-page issue from the 288 mappings.

## Phase 179 closure

- Final retained evidence is `.tmp/phase179_full_533_fresh2` plus `.tmp/phase179_full_533_audit2`. Fresh extraction covers 28/28 projects and 533/533 valid DWG with zero invalid or incomplete pages; audit2 contains 118 issues (117 review, 1 minor, 0 critical), with zero additions versus Phase178 and 15 authority-backed removals.
- Runtime proposal fingerprint binding is now performed from the same canonical primitive-child hash used by finalized symbol inventory before Pair suppression. This closes the lifecycle gap where report-time enrichment made panel Pair evidence appear fingerprint-less.
- The equipment-panel suppressor is intentionally narrow: complete geometry/behavior authority, instance-scoped approval, and complete MARK callout evidence are all required. Name-only, same-name-unapproved, NOTE, incomplete callout, and unrelated geometry cases remain reviewable.
- `TS3000-Z01` is accepted as `structural.component_port_table_container.v1`, not IGNORE. S0014/S0015 emit 144 mappings each (288 total), with independent `instance-prefix + bank + two-digit port -> same-row outward TD` identities. Row 32 is `1-26n432 -> 1-26TD46` and `2-26n432 -> 2-26TD46`.
- Banks 4/5/6 expose populated rows 27-32; banks 7/8 contain structural cells but no outward TD text on those rows, so no mappings are fabricated. All TS3000 ports remain non-union/non-connective. Four S0004 `1201/1204` open endpoints remain visible as intended fail-closed reviews.
- Corpus-wide proof contains 221 panel-shadowed ordinary pairs (214 geometry, 7 MARK callouts), all with non-null fingerprints matching finalized proposal inventory. The 2.5% extraction-time increase after linear runtime binding is within conversion variance and introduces no multiplicative memory path.
- Remaining 118 audit reviews are not silently resolved by this phase; they are the next geometry/extraction/cardinality loop.

## Phase 180 recovery checkpoint

- `master`, `origin/master`, and `HEAD` all point to `c43bd0f feat: generalize equipment panels and component port tables`; the only working-tree item is the user's untracked root `package-lock.json`, which remains out of scope for modification, cleanup, or commit.
- Phase179's retained acceptance artifacts are `.tmp/phase179_full_533_fresh2` and `.tmp/phase179_full_533_audit2`: 28 projects, 533 valid DWGs, zero incomplete pages, and 118 audit reviews with no critical issue.
- The next required proof is not name/fingerprint memorization. PAC S0014 must recognize the repeated closed-body, two-independent-outward-port geometry and emit complete instance-qualified mappings such as `1F1-1 -> 1VD1` and `1F1-2 -> 1701`, while the same `number+F+number` text on backplate pages remains a negative unless the full schematic geometry is present.
- The current generic implementation is in `src/dwg_audit/audit/backplate_components.py`, with dedicated `1F1/1VD1/1701` unit coverage in `tests/unit/test_backplate_components.py`; it predates `c43bd0f`, whose code changes instead concentrate in page extractors, symbol policy, table extraction, runtime fingerprint binding, and pipeline wiring.
- Both final Phase179 full-corpus extraction/audit trees and the PAC source page remain present. The next decision must use their actual mapping rows because unit tests already assert both an accessory form (`1n1701`) and the human-confirmed schematic form (`1701`).
- Direct Phase179 final Parquet proof: PAC S0014 emits exactly eight `component_mapping` pairs for 1F1..1F4. The requested rows are `1F1-1 -> 1VD1` and `1F1-2 -> 1701`; sibling rows are `1F2 -> 1VD6/1707`, `1F3 -> 1VD3/1704`, and `1F4 -> 1VD8/1710`. All have confidence 0.97, `recognition_mode=geometry_insert_backed_inline_two_port`, `internal_connectivity_inferred=false`, `electrical_union_eligible=false`, and `ordinary_pair_eligible=false`.
- The four original one-sided ordinary line pairs on S0014 remain in the artifact only as `ordinary_pair_shadow_only=true` with `covered_by_component_mapping_endpoint`; the final audit has zero S0014 issues. This proves the user-requested semantic mapping is already live at current HEAD, not only represented in a fixture.
- The recognizer remains potentially expensive: the page loop invokes it once per block; each invocation scans every line/text and `_insert_backed_inline_leads` evaluates every ordered pair of horizontal lines. This is approximately `O(blocks * (horizontal_lines^2 + texts))` on each eligible schematic page and should be reduced without weakening fail-closed geometry gates.
- PAC S0021/S0022's 36 missing-side rows are not random. Most short groups have a bare signal number on one side and a same-row compact endpoint such as `1YD28` or `1LD48` at the other line end, with `SYMB2_M_PWF98` and `SYMB2_M_PWF87` anchoring the two ends. This is geometrically analogous to Phase177's accepted compact `1XDxx` endpoint completion and is the leading generalized repair candidate.
- Several S0022 rows are instead anomalously merged 277.8-unit line groups crossing neighboring rows and multiple blocks. Those must not be silently promoted by a broader endpoint regex; the repair must require the same compact short-line/endpoint geometry as the accepted XD model and leave merged-line cases fail-closed.
- The accepted XD implementation is text-grammar plus geometry, not fingerprint: `_SCHEMATIC_COMPACT_DEVICE_ENDPOINT_PATTERN` and `_WIRE_LOGIC_ENDPOINT_PATTERN` currently admit only `digits + XD + digits`, while `_compact_device_endpoint_out_of_row` requires both endpoint-axis distances within 4 units. Extending the compact device family can therefore reuse the exact same fail-closed spatial contract.
- Candidate construction already uses an STRtree per sheet, so adding equivalent compact endpoint grammars does not add a page-wide scan. The missing PAC rows fail specifically because `1YDxx`/`1LDxx` never enter `wire_logic_endpoint_channel`; nearby numeric candidates are otherwise present.
- The implemented compact signal family is intentionally `XD|YD|LD`, not a broad `[A-Z]D`. This preserves S0014's `1VD1` ownership by the independent component mapper and leaves QD/ID/KD/CD/etc. on their existing domain-specific paths.
- Unit guards now cover YD/LD in both line directions, adjacent-row rejection, a 277.8-unit merged-line interior label, and the VD non-target family. The focused candidate suite passes `55 passed` (baseline was 51).
- Fresh PAC extraction is COMPLETE with zero incomplete pages. Fresh audit falls from 51 to 22 issues with zero additions and exactly 29 removed missing-side rows: S0021 drops 19 -> 0 and S0022 drops 17 -> 7.
- The remaining seven S0022 rows are all the measured 277.8-unit merged line groups; their interior `1LDxx` labels remain unbound as intended. New short-line outputs include `718 -> 1YD28`, `1YD3 -> 712`, `707 -> 1LD28`, and `1LD4 -> 501`.
- S0014 remains unchanged after the grammar expansion: exactly eight 1F1..1F4 component mappings, including the two human examples, all with `electrical_union_eligible=false`. No VD label entered the generic compact wire channel.
- Main-thread diff review confirms the code change is limited to the two shared endpoint grammars; no scoring, radius, page routing, pair shadowing, or audit suppression changed. The broader affected regression gate passes `231 passed`, and compileall/diff-check pass.
- Full Phase180 extraction validates 28 projects, 533 pages/source files, all COMPLETE, and zero incomplete pages. Full audit validates 28/28 projects and changes the issue corpus from 118 to 89 with zero additions.
- All 29 removals are the expected PAC missing-side rows (S0021 -19, S0022 -10). Every issue identity in the other 27 projects is unchanged; cross-page conflicts, many-to-one, low-confidence, duplicate, and genuine remaining missing-side rows remain visible.
- Full pair census adds 149 YD/LD `wire_component_mapping` rows and removes none. They occur on 12 signal/recorder/network-output pages across PAC plus 16000/23000/24000/25000/26000/27000/29000; all use the same line-end geometry. Despite this broader semantic recovery, non-PAC audit identities are unchanged.
- The Phase180 full extraction took 1036.5s versus Phase179's 723.3s (+43%). The grammar change retains the existing STRtree and adds only two regex alternatives/149 output rows, so code-level multiplicative work is not evident; nevertheless the slower wall time remains a performance observation to separate from ODA/system variance before final closure.

## Phase 180 residual low-confidence terminal audit

- Eight of the 11 low-confidence rows are not unresolved electrical semantics; they are small terminal-table continuations with a nearby `说明` anchor, a device header, consecutive middle port numbers, and scoped n-endpoints. Examples are `1-21QD` rows 19..21 (`1-21n231`), `4C2D` rows 13..16 (`4n1119/4n1107`), and `上接4Q1D37` rows 38..39 (`4n431`).
- Existing `terminal_header_table` extraction already emits large authoritative tables on the same sheets but misses these mini sections because their header/说明 band lies below the numbered rows instead of above them. The fallback ordinary Pair consequently strips the n-prefix and emits bare `231 -> 21`, `1119 -> 15`, or `38 -> 431` reviews.
- PAC S0029 has the same continuation shape: `上接1YD48` plus `说明` anchors rows 49..51 and scoped values `1n520/1n108/1n104`, while the main 1YD and 1LD tables are already fully extracted. A safe repair must extend the header-table geometry to reversed vertical orientation, not promote these bare ordinary pairs by confidence alone.
- The remaining three low-confidence schematic rows (`1309 -> 10` with six alternatives, `932 -> 932` with repeated anchors, and `1027 -> 1028`) are genuinely ambiguous/non-table line contexts and must stay review unless a separate component/semantic model proves them.
- Wider header-band inspection found explicit continuation authority for every one of the eight terminal rows: `上接1-21GD18` owns rows 19..21 in both 17000/28000, `上接4C1D12` owns rows 13..16 in 31000, `上接4Q1D37` owns rows 38..39 in 26000, and `上接1YD48` owns rows 49..51 in PAC.
- The safe logical identity is not the full continuation label. Parse `上接<prefix><last-row>` into the existing instance prefix plus a sequence boundary, then require the observed rows to begin exactly at `last-row + 1`. For example `上接1YD48` yields `1YD-49 -> 1n520`, not `1YD48-49` and not bare `49 -> 520`.
- The implementation now parses only exact `上接<prefix><N>` labels that also have an adjacent exact `说明` anchor, validates `<prefix>` with the existing terminal-header grammar, and accepts at least two consecutive rows beginning exactly at `N+1`. It records `continuation_from_row=N` in every mapping.
- Positive tests cover compact `1YD48 -> rows 49..51` and hyphenated `1-21GD18 -> rows 19..21`; negatives cover missing `说明` and a broken 49/51 sequence. The complete table extractor suite passes `34 passed`.
- Fresh replay proved the explicit continuation model on five target projects: `1-21GD-19/20/21`, `4Q1D-38`, `4C1D-13..16`, and PAC `1YD-49..51` are emitted as `0.95/pass` table mappings; blank row `4Q1D-39` remains unmapped. Their eight former bare-number low-confidence findings disappear with no semantic issue addition on those projects.
- The first 533-DWG replay exposed two non-target regressions that affected-project replay had not covered. Treating continuation headers as ordinary peer headers let `上接1I3D19` steal `1QD-2 -> 1KLP1-1` on 23000 S0032 and let `上接5FD19` steal `3-2QD-7/8 -> KD26` on the WBH S0025 table. Their historical many-to-one findings disappeared only because authoritative table mappings were lost, so the first full replay was rejected.
- The corrected ownership model separates regular headers from continuation headers for ordinary row bounds and endpoint competition. Continuation headers still compete within continuation extraction, but cannot become a closer peer for a regular `1QD/3-2QD` strip. Fresh eight-project replay restores all three table mappings and both historical many-to-one findings while preserving all eight intended low-confidence removals.
- Full-corpus replay also surfaced one newly visible structural fact requiring human arbitration rather than silent suppression: 8000/9000 maps `1-26TD-216 -> GND` on S0017 at about `(146,246)` and `2-26TD-216 -> GND` on S0019 at about `(106,146)`. Both are explicit `上接... + 说明 + row 216` table rows. The audit reports their shared GND as many-to-one; whether mirrored GND rows are an accepted common endpoint remains unadjudicated.
- The sole residual `R-DUPLICATE-PAIR` in 14000_B is not duplicate extraction. S0012 has two distinct `numeric_three_column` rows (`row_index=1/2`) with independent middle/right text IDs and coordinates, both legitimately spelling `1 -> 1`. Generic value-only duplicate grouping lost that physical-row identity.
- Added a fail-closed numeric-table duplicate exemption requiring one sheet, `0.95/pass`, exact numeric-three-column roles, matching persisted values, and unique row/middle/right identities for every occurrence. Re-emitting the same row or text IDs still reports `R-DUPLICATE-PAIR`. Fresh 14000_B replay changes its only issue from 1 to 0.

## Phase 180 final residual matrix and GND arbitration boundary

- Final audit3 contains 81 issues: 36 `R-PAIR-MISSING-SIDE`, 31 `R-MANY-TO-ONE`, 11 `R-CROSS-PAGE-CONFLICT`, and 3 `R-PAIR-LOW-CONFIDENCE`. Pair kinds are 36 ordinary missing-side, 22 component many-to-one, 9 table many-to-one, 11 table cross-page, and 3 ordinary low-confidence.
- Exactly three issues share the textual endpoint `GND`: 30000 (`1-JD-21 / 2-JD-19`), 8000/9000 (`1-26TD-216 / 2-26TD-216`), and PAC (`1ID-31 / 1ID-43 / 1ID-5 / 1ID-52 / JD-11`). All source facts are `terminal_header_table`, `0.95/pass`, with a valid row sequence, `说明`, complete header/middle/endpoint text identities, and independent logical ports. This is distinct from historical whole-symbol ground IGNORE authority.
- Human arbitration remains required only for whether multiple independent table ports may share the textual public endpoint `GND` without a many-to-one review. If accepted, preserve every port-to-GND mapping and continue to forbid port-to-port connectivity/electrical union; implement a strict structured-source exception with ordinary, low-confidence, non-GND, and mixed-source negatives.
- The remaining 78 issues must not be bulk-suppressed. PAC S0022's seven 277.8-unit merged lines and the three residual low-confidence schematic rows remain explicit fail-closed reviews. The next likely audit-classification defect is the five-row WBH backplate cross-page cluster, which may be merging distinct cabinet/instance scopes; verify complete mapping provenance before changing rules.
- WBH scope root cause is extraction precedence, not a cross-page exemption. Across 3502 composite backplate mappings / 33 independent scopes, 29 scopes already match their rear-wiring title. Only four WBH sheets disagree: titles `1n / 1-2n / 3-2n / 5n` were emitted as `1-1n / 1-20n / 1-20n / 1-20n` because the resolver selected the highest whole-page free-text device label before the explicit title.
- The accepted repair gives an explicit `REAR WIRING/背板` title first authority and admits short title instances such as `1n/5n`; unmarked short text remains too weak, while the historical compound-instance free-text fallback remains available. Fresh WBH extraction preserves 1957 pairs and every physical row/text identity, changing only 254 logical left scopes across the four affected backplates. Fresh audit is `9 -> 4`: five scope conflicts removed, four component many-to-one reviews retained, additions zero.
- The first 533-page fresh4 extraction was structurally complete but failed semantic-delta acceptance. Allowing short forms in the whole-page free-text candidate grammar changed six non-WBH projects and added 119 mappings in 23000; samples showed `1n/4n` page text incorrectly scoping NCK/PMU tables. The final design therefore keeps short forms only in explicit rear-wiring titles and restores the compound-only free-text grammar. fresh4 is rejected as final evidence and must be superseded.
- The seven-project post-tightening probe is accepted: 16000, 23000, 24000, 25000, and 31000 Pair identities exactly match fresh3; PAC's only changes are 316 title-scoped logical keys on explicit `1n/2n REAR WIRING` sheets, with unchanged external text identities and unchanged audit count (19); WBH has the intended 254 scope-key changes and removes five cross-page scope issues without touching the four component reviews. The PAC re-keyed many-to-one/one cross-page reviews remain visible, so title scope is not an issue suppression.
- Final fresh5 is authoritative for this slice: 28 projects / 533 files and pages / 533 valid / zero invalid or incomplete. Compared with fresh3, only PAC (316) and WBH (254) logical left identities change; both retain identical Pair counts and physical right/text identities, and all other 26 projects are exact. audit5 is 76 versus audit3 81: only five WBH cross-page scope reviews are removed; many-to-one remains 31, missing-side 36, low-confidence 3, and the three GND reviews remain pending.
- The six remaining `R-CROSS-PAGE-CONFLICT` rows are not currently safe to suppress. All are `0.95/pass` complete `backplate_virtual_table` facts: 24000/25000 NCK305 pages have no extractable device instance and distinct source-page variants; 26000's shared `1-8n` rows come from distinct WDLK and ZSZ source blocks with different external terminals; PAC's explicit `1n/NCK305-5` appears on two `1n` backplates but points to `1CD3` versus `1CD9`. Without a reciprocal scope/variant authority, keep these reviews fail-closed.

## Phase 180 QD wire-endpoint investigation

- The current secondary-schematic wire endpoint grammar in `src/dwg_audit/audit/candidates.py` accepts compact `XD/YD/LD`, `1-21...`, and hyphenated hierarchical device endpoints. It rejects unhyphenated breaker/contact designators such as `4Q2D20` and `4Q1D35~36` solely because `_WIRE_LOGIC_ENDPOINT_PATTERN` does not match them; the ordinary candidate is consequently recorded as `not_numeric`.
- Production admission is already limited to `二次原理图` and horizontal/grid line groups. The extended near-endpoint pass runs only when exactly one side has numeric candidates, then searches the missing endpoint and reuses spatial scoring. A safe QD extension still needs corpus evidence for short-line length, exact endpoint proximity, a numeric opposite endpoint, and explicit negatives for long merged lines, interior labels, and textless opposite sides.
- The actual focused test module is `tests/unit/test_terminal_candidates.py`; the previously guessed `tests/unit/test_candidates.py` does not exist.
- Fresh5 contains 176 exact `number-Q-number-D-port[/range]` texts: 78 in 26000 and 98 in 31000, spanning 100 secondary-schematic, 53 backplate, 14 component, and 9 terminal-table placements. Page category and local endpoint geometry are therefore mandatory; name grammar alone is unsafe.
- Thirty-eight rejected QD candidates lie within 4-by-4 units of a line endpoint. Only eight secondary-schematic candidates also have numeric candidates on the opposite side. Four unambiguous horizontal rows are the coherent 26000 AC/DC supply family: `4Q2D20 -> 829`, `4Q2D1 -> 803`, `4Q1D35~36 -> 831`, and `4Q1D1 -> 801`; every line is 47.5 units and every QD offset is about 2.5 by 2.4.
- The other four apparent positives are 31000 grid groups whose opposite side contains two or three competing numbers (`1729/929`, `1103/1703/903`, `1131/1731/931`, `1101/1701/901`). They cannot be promoted by the same strict rule. A valid first slice must require a horizontal group and exactly one accepted opposite numeric identity.
- Long/interior QD placements provide structural negatives: 26000/31000 groups of roughly 80 to 215 units have QD text near one endpoint but no unique numeric opposite side. PAC `1QD47~53` is a different grammar and remains outside this slice pending separate evidence.
- A rendered source crop of 26000 S0005 confirms all four accepted rows are one coherent structure entering the `ZSZ-812E` device: `4Q1D1 -> 801`, `4Q1D35~36 -> 831`, `4Q2D1 -> 803`, and `4Q2D20 -> 829`. The Q labels sit at the left ends of four parallel leads; this is not table text or a name-only match.
- The first rules replay changes 26000 issues `9 -> 8`, not `9 -> 7`: the old duplicate-line issue on `GW0032 ? -> 829` is removed, but the same `829` text becomes a new half-pair on `GW0029`. Visual evidence places `GW0029` on the nearby large device-outline rectangle rather than a second electrical lead. Verify its `LWPOLYLINE` closure metadata and fix outline-to-wire admission; do not suppress the review by value or pair identity.
- `GW0029` is segment `4C44:0` of a 5-vertex open-flagged LWPOLYLINE whose first and last vertices are identical. Its four extracted segments form an exact 40-by-45 axis-aligned rectangle; canonical scene marks it `topology_union_eligible=false`. The false half-pair is therefore a numeric-anchor ownership error on an enclosure edge.
- A corpus-wide rectangle filter is too broad: the same geometric closure test finds 1,117 parent polylines and 1,066 affected line groups across all 28 projects, including 271 non-empty pairs and nine retained issues such as TS3000 open stubs. The accepted direction is a Q-mapping-specific shared-anchor rule: when one exact numeric text is claimed by near-overlapping groups and exactly one group has an opposite strict Q-device endpoint, that complete mapping owns the numeric anchor. Far groups, multiple Q owners, and distinct text identities remain fail-closed.
- The accepted Q-device implementation keeps the exact `number-Q-number-D-port[~port]` grammar behind secondary-schematic, horizontal, line-length `<=50`, endpoint X/Y `<=4`, and opposite numeric-channel gates. Pair scoping removes a Q candidate when the other side has no numeric terminal; a dedicated regression now proves both non-schematic rejection and no single-sided Q mapping.
- Numeric-anchor ownership is intentionally narrower than outline classification: the same sheet/text/value must have exactly one complete Q owner, and only near-overlapping horizontal groups within six drawing units and at least 35% overlap lose the borrowed number. Ambiguous owners and farther groups remain untouched.
- Fresh6 is authoritative for this slice: 28 projects, 533 files/sheets, 533 valid, zero invalid/incomplete. Compared with fresh5, only 26000 changes, with four exact Q mappings and `GW0029` becoming an empty discard; all other 27 projects are Pair-identical.
- Audit6 contains 74 issues (`many-to-one 31`, `missing-side 34`, `cross-page 6`, `low-confidence 3`). The key-set comparison has zero additions and removes only 26000 S0005 `GW0032 ? -> 829` and `GW0043 ? -> 831`. The three GND shared-endpoint groups and all six cross-page conflicts remain visible.

## Phase 180 signal-page 605/606 residual audit

- The next 10-row cluster is exactly duplicated between 22000 and 35000 `S0010 / 10 信号回路图.dwg`: five missing-side identities per project have identical world geometry, line lengths, candidate offsets, and numeric values.
- Four rows per page are independent 80/90-unit horizontal lines ending near `605` or `606`; they have no nearby overlapping line group within eight drawing units. The fifth target is a 237.247-unit line that borrows the same `605` text as a 90-unit neighbor with a 4.65-unit row offset.
- This cluster does not satisfy the existing Phase173 inline-signal bridge contract, which requires a shared numeric text bbox spanning a same-row collinear split. Do not suppress or bridge it until source-page visual/component evidence identifies the short-line semantics.
- Structured source evidence resolves the semantics without a new ruling. Each page contains two `SPMU-857G-CG` panel instances headed `1-25n` and `2-25n`. Their left-side generic terminals are `TD1/TD3` and `TD2/TD4`; the same rows terminate at local panel numbers `605/606` through confirmed PWF165 line-break symbols.
- The historical human ruling for this exact B+/B-/Shielding-layer structure says the panel artwork is ignored, B+ and B- remain mutually isolated, Shielding layer forms no mapping, and the external route remains `TD1 -> instance+local-port`. Therefore the expected mappings are `TD1 -> 1-25n605`, `TD3 -> 1-25n606`, `TD2 -> 2-25n605`, and `TD4 -> 2-25n606` per page. The 40-by-30 panel-outline edges must not borrow `605` as an ordinary endpoint.
- Existing code recognizes the `A$C6A636705` closed cable sleeve as zero-port IGNORE and knows `TD#` only in narrow network/time semantic context, but it has no SPMU row extractor. Expanding page keywords would lose the required instance-qualified `1-25n605` identity and could over-admit unrelated signal pages. This belongs in structured wire-component extraction with explicit panel-instance/row evidence.
- The correct integration point is `extract_component_prefixed_signal_pairs()` inside `WireDiagramExtractor`. It runs after ordinary pair construction and before `_mark_wire_component_covered_ordinary_pairs`, so a dedicated SPMU component mapping can shadow only proven same-row residuals while preserving unrelated open ends and audit-visible conflicts.
- `wire_components.py` already has the required Pair/evidence conventions and receives page texts plus raw line segments. A strict SPMU row model can remain API-local by requiring the model label, scoped `n` prefix, one 40-by-30 enclosure, exactly the 605/606 row labels, same-row `TD#` terminals, and CONNECT support lines. It should emit external TD -> `prefix+local` with `internal_connectivity_inferred=false` and `electrical_union_eligible=false`; B+/B-/Shielding text is recognition context only.
- Existing coverage is text-identity scoped, not value scoped. Adding `spmu_signal_panel_row_mapping` to `_wire_component_local_number_text_reasons` will discard only ordinary pairs that reuse the exact 605/606 row text IDs. This covers the four real row residuals plus the two enclosure-edge borrows across both pages without suppressing unrelated occurrences of 605/606.
- Full fresh6 census finds 76 SPMU-related texts with models `SPMU-858G` and `SPMU-857G-CG`. Only 22000/35000 S0010 jointly contain an SPMU model, scoped n-prefixes, 605/606 rows, TD terminals, and B+/B-/Shielding cues. The matcher can accept the SPMU model family but must require this complete local structure, so the other 72 model labels remain untouched.
- Unit coverage can model the production geometry directly: model and scoped prefix above a four-edge enclosure, two distinct three-digit rows on the boundary, same-row TD labels connected by horizontal CONNECT lines, plus B+/B-/Shielding context. Negative cases should remove or misalign one authority at a time rather than test only the model string.
- Fresh 22000/35000 replay proves exact behavior. Each 19-file project adds four SPMU mappings and changes six ordinary rows from review to discard by exact local text identity; five were audit-visible and one extra enclosure edge was already collapsed by duplicate-issue aggregation. No other Pair identity changes.
- Both targeted audits fall `5 -> 0` with zero additions. Every emitted mapping is `0.95/pass`, records its four enclosure line IDs and CONNECT support line, and carries `internal_connectivity_inferred=false`, `electrical_union_eligible=false`, and `ordinary_pair_eligible=false`.
- Full fresh7 completes in 865.9 seconds with 28 projects, 533 files/sheets, 533 valid, and zero invalid/incomplete. Compared with fresh6, only 22000 and 35000 change, each by the exact four SPMU additions and six local-text ordinary status replacements; all other 26 projects are Pair-identical.
- Audit7 completes all 28 projects in 116.3 seconds and reduces issues `74 -> 64`: missing-side `34 -> 24`, while many-to-one 31, cross-page 6, and low-confidence 3 remain unchanged. Added issue identities are zero; removed identities are exactly the ten target SPMU rows.

## Phase 180 PAC S0022 disconnected-island line groups

- All seven retained PAC S0022 missing-side rows have the same malformed group structure. The true electrical lead is a 30-unit CONNECT segment from x=114.744 to 144.744 with numeric text on the left and `1LD20..27` at its right endpoint. Two duplicate 30-unit layer-0 segments at x=362.5..392.5 share the row but are separated by about 217.8 units.
- Line grouping reports each three-segment set as one 277.756-unit horizontal group, moving the logical endpoint into the interior and triggering the compact-device out-of-row/long-line guard. The correct fix must preserve the strict compact endpoint rule and separate disconnected islands or recover segment-backed ownership; globally raising the length/distance threshold is unsafe.
- Root cause is order-sensitive grouping in `src/dwg_audit/audit/line_groups.py`: candidates are sorted by rounded cross-axis before start-axis, so a right island at one exact Y can create the group before a slightly offset left CONNECT segment. The one-way `start_axis - group.end_axis <= gap_tol` condition then admits an arbitrarily negative gap and merges the disconnected intervals.
- The initial corpus census found 100 existing groups with disconnected gaps over 20 units across 16 projects, 11 of them audit-visible. Some currently carry valid component mappings, so a global interval-distance repair is acceptable only after focused ordering/grid tests, PAC replay, and exact full-corpus Pair/audit comparison.
- Direct source review confirms the ordinary path sorts by `(round(cross_axis, 3), start_axis)`, while grid bands re-sort members by `start_axis`. The PAC ordering defect is therefore directly reachable in ordinary horizontal/vertical mode; grid is less exposed but still duplicates the one-way gap calculation and should share the corrected invariant.
- A symmetric interval gap alone is insufficient for numeric bridging. When the later-processed candidate is spatially left of the existing group, `_has_inline_numeric_bridge` must receive the candidate end and group start as its ordered left/right boundaries, with their corresponding cross axes. Overlaps keep zero interval distance; only positive separated gaps invoke bridge evidence.
- Existing `tests/unit/test_line_groups.py` already covers forward ordinary/grid numeric bridges, missing bridge evidence, wide signal-page gaps, and component vertical orientation. The new regression boundary therefore focuses on the previously absent order inversion: PAC-shaped duplicated remote islands, reversed overlap/near-gap positives, reversed numeric bridge, vertical equivalence, and grid distant-island preservation.
- The public replay entrypoint is the `dwg-audit` script backed by `dwg_audit.cli:run`. The accepted fresh7 baseline stores PAC under its own `PAC-885G-H` project directory; all new extraction and audit evidence must use distinct output roots so fresh7/audit7 remain immutable comparison authorities.
- PAC's authoritative fresh7 manifest identifies `F:\workspace\XJToolkit\test\PAC-885G-H` as the input root and records 31 files/sheets, all valid. The project artifact directory has no `run_summary.json`; validation must use the real manifest/completeness files rather than a guessed summary path.
- Verified CLI contracts: `python -m dwg_audit analyze-project -i <project> -o <root>` creates the fresh project bundle, and `python -m dwg_audit run-audit --findings <project-bundle> --output <audit-root>` replays rules. The PAC acceptance probe uses a new root and compares manifest, completeness, `findings/pairs.parquet`, `findings/line_groups.parquet`, and audit `issues.json/parquet` against fresh7/audit7.
- Fresh PAC replay1 completed naturally after the outer shell timed out but left its Python child running. S0022 now has zero line groups longer than 250 units; every local x=114.744..144.744 CONNECT lead is an independent 30-unit group, and recovered component mappings include the target `704 -> 1LD27` and `703 -> 1LD26` rows. A concise expected-set probe remains required for all seven rows.
- The first completeness probe guessed `status` and `incomplete_sheets` fields, producing blank/one values from the wrong schema despite a 31/31 valid manifest. Inspect actual JSON keys before declaring completeness; do not treat those guessed-field values as extraction failure.
- Actual PAC completeness is `analysis_status=COMPLETE`, `clean_conclusion_allowed=true`, `incomplete_page_count=0`, and an empty incomplete-sheet list. All seven required mappings are present: `704/703 -> 1LD27/26` and `810..806 -> 1LD24..20`.
- Pair delta is confined to S0022: 45 additions and 21 removals by semantic/text-identity key, with zero change on the other 30 sheets. The corrected grouping recovers the whole repeated row family (22 `number <-> 1LDxx` component mappings, not only the seven audit-visible rows), emits separate empty remote-island discards, and removes former one-sided/borrowed candidates. This broader same-geometry recovery is expected but requires audit zero-addition and full-corpus comparison.
- PAC audit1 is accepted: issues fall `19 -> 12`, added issue identities are zero, and removed identities are exactly the seven target S0022 missing-side rows (`704`, `703`, `810`, `809`, `808`, `807`, `806`). All seven many-to-one, the four unrelated missing-side rows, and the one cross-page conflict remain visible.
- Pre-full gate is clean at `1086 passed, 1 skipped`. Full fresh8 must use one Python process per manifest-derived project input root, both to preserve the accepted Phase180 memory boundary and to exclude helper `cache/logs` directories from project enumeration.
- Fresh8 completed all 28 isolated project processes in 881.4 seconds and validates at 533 files/sheets, 533 valid, zero invalid, zero incomplete, with every required artifact present.
- Semantic/text-identity Pair comparison changes 16 projects and leaves 12 exact. This matches the earlier 16-project disconnected-island census, but the delta includes both empty-island splits and semantic/component remapping. The global repair is not accepted from extraction counts alone; audit8 and targeted high-confidence delta review are mandatory.
- Audit8 completes 28/28 projects in 117.4 seconds and changes total issues `64 -> 60`: missing-side `24 -> 20`, while many-to-one 31, cross-page 6, and low-confidence 3 are unchanged. Exact identity delta is five additions and nine removals, so fresh8/audit8 remain provisional.
- Seven removals are the intended PAC rows. One 31000 `1731` addition/removal pair is the same underlying one-sided anchor changing from generic missing-side to near-duplicate-line wording. The new semantic review candidates requiring source audit are 23000 `802`, 26000 `504` and `229`, and 31000 right-side `927`; removed 31000 `1105` also needs proof.
- Direct member-line inspection proves the added reviews expose previously hidden disconnected facts. 23000 `802` belonged to x=81.25..181.87 while the borrowed `TC2` island was x=281.25..336.87; 26000 `504` is a standalone 52.5-unit CONNECT lead and `229` is claimed by two distinct near-parallel 105/120-unit groups; 31000 `927` is a standalone 40-unit CONNECT lead. These additions should remain visible unless source text proves a local counterpart.
- The removed 31000 `1105` review changed from a falsely merged pair of CONNECT segments (x=82.5..104.04 and x=132.5..159.32) to a local `1105 -> 1105` discard on the first segment. Its surrounding text/second-segment ownership remains the final residual acceptance check.
- S0013 source text confirms `1105` is at x=81.22..87.42 and `1106` at x=131.22..137.42. The formerly merged group joined the first lead to the second lead across a large gap; fresh8 discards the self-pair on the 1105 lead and leaves the 1106 lead as an independent semantic-mapping review candidate. No physical 1105 endpoint was suppressed by the fix.
- Full group census is the decisive geometry acceptance: fresh7 had 100 groups with an internal axis gap >20 across 16 projects; fresh8 has zero such groups across 13,253 multi-member groups. This proves the shared interval predicate removes the order-sensitive disconnected-island defect without leaving large internal gaps behind.

## Phase 180 31000 operation-box residual investigation

- Audit8 retains seven related reviews in 31000 operation-box sheets S0013/S0014: missing-side `1731` on both sheets, `1729`, right-side `926/927`, and low-confidence `932->932` plus `1027->1028`. Earlier Q-device census found the same operation-box family contains competing numeric endpoint rows, so this slice must inspect complete local geometry rather than promote values by grammar alone.
- Fresh8 candidate evidence is fail-closed for the seven rows. `1027->1028` uses a 45-unit layer-0 line with the left text 8.78 units from its endpoint and the right text 3.78 units away; `932->932` has endpoint 932 candidates plus interior 932 and alternative left 1108/1506 candidates. S0013 `1731` and S0014 `1729` sit on 357.5/247.5-unit CONNECT lines beside rejected `4Q1D46/4Q2D31` labels; S0014 `1731` is on a 62.5-unit line beside rejected `4Q1D46`; 926/927 are 52.5/40-unit lines whose opposite sides have only TXJ/LED explanation text. No complete, unique opposite endpoint is currently proven.
- The authoritative fresh8 bundle has no rendered canonical-scene views (`canonical_scene_views.parquet` is empty), but retains 3,579 normalized scene records for S0013/S0014. The supported preview entrypoint is `dwg_audit.desktop.preview.render_project_preview`; use its actual signature if visual confirmation is needed rather than inventing a tools script.
- The desktop preview function reads `DesktopStateStore.load_latest_project_result`, so it cannot directly render an isolated CLI fresh8 bundle without a desktop SQLite record. For this slice, canonical scene records plus source line/polyline provenance are the authoritative visual substitute; they preserve handles, primitive kinds, world geometry and topology flags.
- Source provenance separates the seven rows: S13 `1027->1028` is a `LWPOLYLINE` segment `F41:0` on layer `0`, while S13/S14 1731/1729/926/927 are standalone `LINE` entities on `CONNECT`. The likely fix is a geometry/evidence-scoped enclosure-edge exclusion, not a numeric-value or page-name rule.
- A global rectangle filter is already known unsafe from the Q slice: it touches 1,117 parent polylines, 1,066 line groups and 271 non-empty Pair facts. Any operation-box exclusion must therefore require reconstructable polyline ownership and preserve component/structured mappings through a narrow route or coverage contract.
- F41 is exactly reconstructable from `F41:0..3`: four axis-aligned layer-0 LWPOLYLINE segments form a 45-by-190 rectangle. Although CAD `closed=false`, its five raw vertices repeat the first point at the end. The selected `1027->1028` pair is the 45-unit top enclosure edge; this is materially narrower evidence than the prior all-rectangle census.
