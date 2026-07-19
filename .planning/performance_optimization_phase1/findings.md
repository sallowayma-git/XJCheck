# Findings: Performance Optimization Phase 1

## Starting evidence
- `App.tsx::loadProjectResult` currently commits success/error without checking whether the selected project changed while the invoke was in flight.
- Preview already has debounce, a local stale-response guard, a Rust serialization gate, generation supersession, timeout, and global cancellation.
- The missing boundary is explicit request ownership across React, Tauri IPC, PID tracking, cancellation, and returned result validation.
- Existing user changes in `src/dwg_audit/audit/page_extractors.py`, `src/dwg_audit/audit/wire_components.py`, `tests/unit/test_wire_components.py`, and root planning files are outside this slice and must remain untouched.

## Exact contract findings
- Rust currently stores preview generation, PID, and gate in separate globals. `cancel_preview_requests` invalidates generation and then reads a naked PID; a stale cancel can race with a new spawn/PID registration and terminate the new request.
- `ActivePreviewProcess` clears only by PID and cannot prove request ownership. The worker checks generation before spawn and in its polling loop, but not transactionally at PID registration or final result commit.
- React preview cleanup always calls a parameterless global cancel, including when debounce never started a render. The local `cancelled` flag protects UI state but cannot identify or terminate the owned backend request.
- `withTimeout` rejects only the Promise wrapper. Its timeout path must explicitly cancel the same request ID.
- Tauri invoke payload keys are camelCase (`requestId`) while Rust command parameters remain snake_case (`request_id`). Both sides must ship together.
- The frontend has no component test framework. A real asynchronous generation test can still use Node's built-in test runner if the coordinator is extracted as a DOM-free TypeScript/JavaScript helper; otherwise packaging regex tests are only a wiring sentinel.

## Selected design
- Keep the preview serialization gate, but replace the separate generation/PID globals with one mutex-protected `PreviewState` containing a token `(request_id, generation)` and optional PID.
- New render requests supersede the previous token. PID registration, cancellation, completion, and Drop cleanup succeed only for the exact owner token.
- Cancellation accepts a required `request_id`; unknown/stale IDs are idempotent no-ops and never affect the current request.
- The worker that owns `Child` performs kill/wait after observing lost ownership. This avoids a stale cancel command killing a reused or newly registered naked PID.
- Return `request_id` in the preview payload and validate it in React in addition to the local effect generation.
- Project loading uses a separate monotonic generation; both success and failure commits are guarded.
- Node 26 can execute erasable TypeScript directly. A DOM-free generation helper used by `App.tsx` will be exercised with `node:test`, avoiding new frontend dependencies.
- Rust ownership tests will instantiate local `PreviewState` values rather than mutating global state, so tests remain parallel-safe.

## Main-thread verification
- `main.rs:39-41` confirms generation, PID, and gate are separate globals. `cancel_preview_requests` at lines 420-425 invalidates generation and then terminates whatever PID is globally visible.
- `run_preview_sidecar_json_owned` checks generation before spawn and during polling, but the successful `try_wait` branch at lines 477-485 returns parsed output without a final ownership check.
- `ActivePreviewProcess` registers and clears only a PID. It cannot distinguish two generations or request IDs.
- `App.tsx:167-187` commits project load success and failure unconditionally after await.
- `App.tsx:651-701` uses a local `cancelled` flag for UI commits, then unconditionally sends global cancel during every cleanup.
- `desktopApi.renderPreview` and `cancelPreview` have exactly one production caller, both in `App.tsx`. The IPC contract can be upgraded atomically across the repository.
- Project deletion and analysis start are explicit abandonment points for any pending project load and must invalidate its generation.
- Preview ownership must also cover build/spawn/pipe setup failures; otherwise a token can remain active even though no worker is running.

## Implementation notes
- Preview cancel now invalidates only the matching request state. The worker holding `Child` observes lost ownership, kills/waits the tree, and releases the serialization gate before the next worker spawns.
- The Rust response adds `request_id` to the existing JSON object instead of wrapping the payload, preserving all existing preview fields.
- Frontend timeout now invokes cancellation for the same request ID; Promise timeout alone is no longer treated as backend cancellation.

## Independent review findings
- Explicit navigation to launch/process did not invalidate a pending project load, so a late success could still force the screen back to results.
- Project deletion captured the old selected project across an await. If the user opened another project during deletion, the old completion could clear the new selection/result.
- Invalidating a load before delete completion also discarded the load when deletion failed. Deletion should disable competing row actions and only clear current state after success with a current-identity check.
- The dependency-free `.ts` Node test works on the local Node 26 but is not portable to every Node version supported by Vite 8. The helper test should be plain ESM JavaScript importing a plain JavaScript runtime helper, or the project must add a runner dependency/version floor.
- The initial packaging regex for Rust's render signature could cross the function boundary and match cancel's `request_id`; it must constrain matching to the render parameter list.
- A sidecar descendant can inherit stdout/stderr. After the direct child exits, unbounded reader `join` may never observe EOF and can hold `PREVIEW_GATE` forever. Pipe collection needs a bounded receive path.
- `std::thread::spawn` can panic after the child is registered; using `thread::Builder::spawn` lets the worker kill/wait the child and return an error instead of poisoning the gate.
- Abandoning project A while retaining project B's result can leave selected project A paired with result B. Loading state must be explicit and abandoning a load must restore/clear the committed selection.
- Analysis completion needs its own screen-intent generation so a navigation made while analysis is running can prevent later auto-navigation.
- To make the ownership contract exact even if a caller accidentally reuses an ID, the next patch will pass the frontend client generation alongside `requestId`; Rust cancel will match both fields.
