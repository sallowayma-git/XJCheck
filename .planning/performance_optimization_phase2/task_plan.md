# Task Plan: Performance Optimization Phase 2

## Goal
Reduce conversion and analysis resource pressure without changing legacy findings: add bounded, resource-aware ODA admission and introduce an explicit production/diagnostic/regression artifact policy.

## Scope
- ODA conversion scheduler, CPU/memory sampling, hysteresis, and config/tests.
- Report/artifact runtime profile and automatic report format policy.
- Preserve legacy pair/issue semantics and existing regression behavior through explicit regression profile tests.
- Do not implement Windows Job Objects or the full lazy result API in this phase.

## Phases

### Phase 1: ODA bounded admission
- [x] Read exact converter/config/tests and choose no-heavy-dependency sampler.
- [x] Add pure resource gate with pressure/healthy hysteresis.
- [x] Replace submit-all with bounded in-flight scheduling and stable result order.
- [x] Add focused scheduler/sampler/config tests.
- **Status:** complete

### Phase 2: Runtime artifact profiles
- [x] Read exact artifact/rerun/config/test contracts and isolate core vs diagnostic work.
- [x] Add validated `runtime.profile` and resolved report formats.
- [x] Gate optional shadow/report work without changing legacy core output.
- [x] Add production vs regression parity and artifact-inventory tests.
- **Status:** complete

### Phase 3: Configurable preview policy and session ownership
- [x] Add persisted auto/manual-only/off preview policy with pure tests.
- [x] Make mode changes cancel active preview work and suppress new admissions.
- [x] Namespace Rust preview generations by renderer session so WebView reloads recover at generation 1.
- [x] Add reload/stale-session state-machine tests.
- **Status:** complete

### Phase 4: Verification and handoff
- [x] Run focused ODA, report, rerun, integration, and desktop checks.
- [x] Inspect diff against user-owned changes and record residual risks.
- **Status:** complete

### Phase 5: Residual lifecycle hardening
- [x] Make preview output context-aware so an old image/error cannot survive a target switch.
- [x] Make renderer sessions explicitly register a server-owned epoch before begin/cancel.
- [x] Add regression tests for unknown/evicted sessions and preview context/empty-state ordering.
- [x] Re-run the full verification matrix and document native ODA subprocess limitations.
- **Status:** complete

## Decisions
- `convert_workers` remains a hard ceiling; adaptive pressure only reduces future admissions.
- Unknown resource samples never make conversion fail; adaptive mode retains its safe two-slot startup cap until healthy telemetry supports recovery. Disabling the gate admits the explicit ceiling immediately.
- Production profile may omit diagnostics, but must record `run_profile` and `diagnostics_status=not_generated_for_profile` rather than pretending zeros.
- Regression profile preserves the current full artifact/report path for golden tests.
- Preview cancellation remains mandatory lifecycle correctness. Users may choose automatic, manual-only, or disabled preview admission; no mode may allow stale work to commit.
- Production short-circuiting uses a dedicated core writer before interleaved shadow calculations; diagnostic/regression retain the complete artifact path.
- Preview renderer sessions use an explicit registration handshake and a server-owned monotonic epoch; request/cancel calls never implicitly activate an unknown session.
- Preview UI output is tagged with a primitive context key (run/project/issue/sheet/line plus reload revision), so status-only result updates do not cancel a manual render and stale images are never displayed.
- Adaptive ODA admission starts at no more than two slots and immediately drops to one when the startup sample is already above a pressure threshold; healthy samples recover gradually to the configured ceiling.
- Production profile transitions clear owned stale findings/audit outputs only after new core findings are written successfully, and production rerun does not generate root-cause diagnostics.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
| The result-query exploration agent hit HTTP 429 | 1 | Defer that slice and continue with the two returned independent designs. |
| The first rerun profile patch used an incorrect duplicated copy-list context and was rejected before writing | 1 | Split the edit into exact small patches and preserve the original list verbatim. |
| Bundled `rg.exe` was denied by Windows while starting a parallel source scan | 1 | Fall back to PowerShell `Select-String` and direct targeted file reads. |
| Final review agents exceeded the repository ten-minute window after returning partial evidence | 1 | Kept the cited findings, stopped all three agents, and resumed targeted local verification. |
| Rust format check found one formatter-only layout difference | 1 | Run crate-scoped `cargo fmt`, then recheck. |
| Desktop package has no `typecheck` npm script | 1 | Inspect existing scripts and use the repository's build/lint commands instead. |
| PowerShell rejected a Bash-style heredoc while inspecting the installed ODA helper | 1 | Re-ran the same read with a PowerShell here-string; no source change was needed. |
| One JavaScript shell wrapper had a malformed `workdir` string while reading artifacts | 1 | Corrected the tool arguments and repeated the read once. |
| Full suite initially failed three symbol-shadow integration tests under the new production default | 1 | Made those tests explicitly select the diagnostic profile; rerun passed 1100 tests. |
| Final preview review found unknown/evicted renderer IDs could still activate a session | 1 | Replace bounded retired-ID detection with explicit server registration epochs and add unknown/late-session tests. |
| Final preview review found context-independent `previewSrc` and manual-only error ordering bugs | 1 | Add a stable context key/output tag, narrow effect dependencies to primitives, and prioritize errors before the manual-only empty state. |
