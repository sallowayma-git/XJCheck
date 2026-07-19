# Progress: ODA Process Isolation

## 2026-07-19
- Read the planning skill and recovered the prior performance optimization session.
- Confirmed the previous optimization commit is `20381d7`; the only untracked file is the user-owned root `package-lock.json`.
- Completed clean-context probes of installed ezdxf, Python conversion/health boundaries, and Rust sidecar ownership.
- Selected one-shot worker isolation with pre-request OS ownership, bounded communicate/drain, and whole-tree termination.
- Located the source Typer CLI and the separate packaged sidecar entry point; the first guessed build-script path was wrong and has been recorded for corrected discovery.
- Confirmed the packaged entry has a lightweight command dispatcher before Typer imports, which is the preferred frozen-worker route.
- Read the complete converter and ODA reader implementations plus config defaults. The parent can retain all cache/event/provenance behavior while replacing the single `odafc.convert` call.
- Completed test-seam and packaging/Job Object probes. Added the PyInstaller inner-worker self-join handshake to the design and enumerated all 27 explicit test patch migrations.
- Added the parent runner, one-shot worker, Windows/POSIX termination paths, config defaults, packaged dispatcher, and conversion/health integration. Syntax/import checks pass.
- Focused Python run: 62 passed, 1 failed only on the expected legacy exact-kwargs assertion; packaging tests pass 14/14.
- Added worker protocol/large-output/crash/timeout coverage, timeout-continuation scheduling, built-in smoke mapping, reader isolation, config, and packaged dispatch tests. One 0.1s startup marker assertion was too aggressive on Windows and is being corrected to 0.75s.
- Phase 1 is complete; Phase 2 implementation is active.
