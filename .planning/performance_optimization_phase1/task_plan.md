# Task Plan: Performance Optimization Phase 1

## Goal
Implement the first production optimization slice for desktop responsiveness: make project-result loading latest-request-wins, give preview requests explicit ownership, and strengthen cancellation/cleanup without changing audit semantics.

## Scope
- `apps/desktop/src/App.tsx` and desktop API request contracts.
- `apps/desktop/src-tauri/src/main.rs` preview request lifecycle and tests.
- Minimal related packaging/static tests when required.
- No changes to extraction, pairing, audit semantics, or the user's current wire-component work.

## Phases

### Phase 1: Recover exact contracts and tests
- [x] Read the exact React, API, Rust command, cancellation, and test code to be changed.
- [x] Record the dirty-worktree boundary and compatibility constraints.
- [x] Select the smallest request-ownership design that preserves current callers.
- **Status:** complete

### Phase 2: Implement latest-request-wins
- [x] Guard project-result success and failure commits by generation/project identity.
- [x] Add explicit preview request identity through React/API/Tauri.
- [x] Make cancellation target the owned request and prevent stale process/result commits.
- **Status:** complete

### Phase 3: Verify lifecycle behavior
- [x] Add focused Rust tests for request ownership and supersession.
- [x] Add the strongest feasible frontend/static regression test within the current toolchain.
- [x] Run Rust, TypeScript, lint, and relevant Python packaging tests.
- **Status:** complete

### Phase 4: Review and handoff
- [x] Inspect the final diff for unrelated changes and lifecycle regressions.
- [x] Record remaining Job Object and real-child integration work for the next slice.
- **Status:** complete

## Decisions
- Obsolete preview work is always cancelled; this is lifecycle correctness, not a user preference.
- A frontend timeout must never be treated as proof that the underlying command stopped.
- Keep compatibility changes narrowly scoped and test the ownership rules as pure helpers where practical.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
| The JavaScript orchestration array for four source slices had invalid nesting and failed before any shell command ran | 1 | Record separate parallel shell calls instead of dynamically combining heterogeneous path/range tuples. |
| Parallel validation used `Promise.all`; expected rustfmt differences caused sibling npm outputs to be discarded | 1 | Apply crate-scoped formatting, then rerun independent checks with `Promise.allSettled`. |
| The first independent Rust review agent returned a service `bad_response_status_code` without findings | 1 | Do not reuse it; fix the returned frontend/contract findings and request a smaller final Rust state-machine check from a fresh agent. |
