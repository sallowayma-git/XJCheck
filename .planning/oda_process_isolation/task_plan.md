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
- [x] Add one-shot worker protocol and parent runner.
- [x] Assign Windows workers to kill-on-close Job Objects before sending work.
- [x] Use POSIX process groups and bounded termination fallback.
- [x] Route conversion and default health smoke through the isolated runner.
- **Status:** complete

### Phase 3: Configuration and regression coverage
- [x] Add validated timeout settings and defaults.
- [x] Cover success, timeout, crash, invalid protocol, large output, and continued scheduling.
- [x] Preserve existing monkeypatched converter test seams explicitly.
- **Status:** complete

### Phase 4: Verification and handoff
- [x] Run focused Python tests, then the complete Python suite.
- [x] Run desktop Rust/Node/type/lint/build checks because packaged sidecar entry behavior is affected.
- [x] Reverify final deadline/reaping and packaged-smoke hardening.
- [x] Inspect diff, record residual risks, and prepare the scoped local commit.
- **Status:** complete

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
| Independent review reproduced nonzero-success protocol acceptance, spawn-after-serialization leakage, POSIX descendant leakage, unbounded temp output, and restrictive-Job fallback gaps | 1 | Replaced temp files with bounded drain threads, serialized before spawn, made cleanup universal, enforced exit/frame consistency, fixed killpg escalation, and added real descendant tests. |
| The worktree advanced to commits `a94467e` and `af34340` while hardening was in progress | 1 | Accepted the concurrent commits, confirmed the initial isolation slice is intact in `a94467e`, and kept only post-commit hardening changes unstaged. |
| A transient Python PID disappeared between two process-list probes after tests finished | 1 | Confirmed no running child remained; no repository or artifact change occurred. |
| Final review found kill-after-reap lacked a final wait, stream close could block on inherited pipes, and synchronous stdin writes were outside the deadline | 1 | Move request transport to a bounded writer thread, make stream collection close-safe, and guarantee kill plus final wait before return. |
| Final review found the automated packaged-worker test only exercised source mode and the staged sidecar can be stale | 1 | Keep the successful onefile smoke evidence, add a reusable post-build worker smoke to the build script, and update CI/checklist coverage. |
