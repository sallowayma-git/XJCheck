# Task Plan: XJToolkit Performance And Lifecycle Audit

## Goal
Map the complete desktop audit workflow and identify evidence-backed causes of UI stalls, CPU saturation, memory growth, unbounded concurrency, stale work, and uncancelled result rendering. Produce an actionable optimization design with exact source locations, lifecycle boundaries, priority, and verification criteria.

## Scope
- Desktop launch, project selection, conversion, extraction, pairing/audit, persistence, IPC, and result rendering.
- ODA process concurrency and lifecycle.
- CPU/memory-aware admission control and backpressure.
- Cancellation and latest-request-wins behavior when switching projects/issues.
- User-facing performance settings and observability.
- Read-only audit in this phase; no production implementation unless separately requested.

## Phases

### Phase 1: Repository and architecture recovery
- [x] Inspect foundational architecture/design documents directly.
- [x] Map applications, runtimes, entry points, and end-to-end data flow.
- [x] Record current tests, scripts, and performance instrumentation.
- **Status:** complete

### Phase 2: Parallel lifecycle audits
- [x] Audit ODA conversion process creation, concurrency, cleanup, and failure handling.
- [x] Audit extraction/pairing/audit worker scheduling, subprocess/thread use, and IPC.
- [x] Audit desktop result-loading/rendering, switching, cancellation, and stale updates.
- **Status:** complete

### Phase 3: Cross-cutting resource analysis
- [x] Locate large materializations, copies, caches, polling loops, and blocking UI work.
- [x] Distinguish confirmed defects from hypotheses requiring profiling.
- [x] Design adaptive resource admission and cancellation ownership.
- **Status:** complete

### Phase 4: Verification and recommendations
- [x] Independently verify high-impact findings at exact source locations.
- [x] Define prioritized implementation slices and acceptance metrics.
- [x] Deliver the business-flow map and optimization backlog to the user.
- **Status:** complete

## Decisions
- Treat responsiveness as a first-class resource constraint, not merely maximum throughput.
- Prefer one centralized admission controller over independent per-stage concurrency knobs.
- Require cooperative cancellation plus hard subprocess termination where external tools cannot cooperate.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
| Three broad read-only subagent audits remained running for 10 minutes without returning any result | 1 | Interrupted all three; do not reuse them. Narrow future tasks to already-located modules and shorter questions. |
| Packaged `rg.exe` failed to launch with WindowsApps access denied; `Promise.all` discarded sibling command results | 1 | Use PowerShell `Get-ChildItem`/`Select-String` and `Promise.allSettled` for independent read-only discovery. Do not retry `rg`. |
| Findings append patch used a semicolon where the existing sentence had a period, so context verification failed | 1 | Read the small target tail and reapplied a narrower exact-context patch; no file changed on the failed attempt. |
| PowerShell cross-directory `Get-ChildItem` passed two paths positionally and joined them into a nonexistent `src/apps/...` path; parallel sibling output was discarded | 1 | Use explicit `-Path @('src', 'apps/...')` and `Promise.allSettled`; do not repeat the positional form. |
| Two narrow static hotspot subagents were rejected by the service with HTTP 429 before returning repository evidence | 1 | Use main-thread bounded searches for this phase; do not retry the same delegation batch. Earlier ODA/Tauri/frontend agent evidence remains valid. |
