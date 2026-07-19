# Task Plan: ODA Process Isolation

## Goal
Ensure a permanently blocked ODA conversion cannot indefinitely hold the Python workflow, desktop sidecar, or machine resources. Every production ODA invocation must have bounded wall time, drained pipes, and owned process-tree cleanup.

## Scope
- Per-call ODA worker isolation for DWG conversion and the default ODA health smoke.
- Windows Job Object ownership at the worker boundary; POSIX process-group cleanup elsewhere.
- Configurable conversion timeout with deterministic timeout/crash/protocol errors.
- Preserve conversion cache names, source status/event ordering, and ReaderRun semantics.
- Keep Rust desktop cleanup-process ownership unchanged; a global desktop Job Object is out of scope because cleanup is intentionally detached.

## Phases

### Phase 1: Design and contracts
- [x] Verify installed ezdxf ODA process behavior and deadlock boundary.
- [x] Verify converter, health, cache, event, and test seams.
- [x] Verify Rust sidecar/cleanup ownership constraints.
- **Status:** complete

### Phase 2: Isolated ODA execution
- [ ] Add one-shot worker protocol and parent runner.
- [ ] Assign Windows workers to kill-on-close Job Objects before sending work.
- [ ] Use POSIX process groups and bounded termination fallback.
- [ ] Route conversion and default health smoke through the isolated runner.
- **Status:** in_progress

### Phase 3: Configuration and regression coverage
- [ ] Add validated timeout settings and defaults.
- [ ] Cover success, timeout, crash, invalid protocol, large output, and continued scheduling.
- [ ] Preserve existing monkeypatched converter test seams explicitly.
- **Status:** pending

### Phase 4: Verification and handoff
- [ ] Run focused Python tests, then the complete Python suite.
- [ ] Run desktop Rust/Node/type/lint/build checks because packaged sidecar entry behavior is affected.
- [ ] Inspect diff, record residual risks, and create a local commit if verification is clean.
- **Status:** pending

## Decisions
- Use a one-shot worker for each ODA call so native/Qt state cannot accumulate across files.
- The worker blocks on stdin before invoking ODA; the parent establishes OS ownership before sending the request.
- The parent retains cache validation, source mutation, events, timing, and ReaderRun recording.
- Timeout means the whole worker tree is terminated and reaped before the call returns.
- Do not rely on Python thread cancellation or ezdxf's internal Popen implementation.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
| Third initial read-only agent could not spawn because the concurrent thread limit was reached | 1 | Waited for the first two probes, released a slot, then ran the Rust ownership probe separately. |
| Assumed the PyInstaller build script was under the root `scripts` directory | 1 | The path did not exist; locate it under the desktop packaging tree before reading. |
| Timeout integration test used 0.1s, shorter than a fresh Windows Python startup, so its pre-sleep marker was never written | 1 | Raise only the test timeout to 0.75s while retaining a 5s total-return bound and late-side-effect assertion. |
| Called the long-running exec wait helper three times with nonexistent cell IDs while an agent review was active | 3 | No process or file was affected; stop attempting any exec-cell wait and use the direct collaboration agent wait tool only. |
