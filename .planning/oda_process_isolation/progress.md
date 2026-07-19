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
- Focused lifecycle and packaging coverage passed 93 tests after hardening, including a real grandchild process, large stdout/stderr, worker crash, invalid/trailing protocol, and onefile/source worker dispatch.
- Independent review findings were reproduced and fixed: strict protocol/exit consistency, bounded in-memory drains, universal spawn cleanup, POSIX group escalation, and restrictive Windows Job fallback.
- Initial isolation landed concurrently as `a94467e`; an unrelated evidence commit advanced HEAD to `af34340`. Current unstaged work is only the post-commit hardening slice plus the user-owned `package-lock.json`.
- Phase 2 and Phase 3 are complete; Phase 4 full verification is active.
- Full Python suite passed: 1123 passed, 1 skipped in 28.39s with bytecode and pytest cache writes disabled.
- Desktop verification passed: Rust 24, TypeScript check, oxlint, Vite production build, and cargo fmt check.
- PyInstaller onefile smoke passed: temporary 52.3 MB sidecar built and `oda-worker` returned the expected structured protocol error with exit code 1.
- Final independent review found additional deadline/reaping issues after the first full verification. Phase 4 is reopened until bounded stdin, pipe-handle closure, final wait, and packaged post-build smoke are implemented and reverified.
- Replaced cross-thread buffered pipe I/O with duplicated raw descriptors, added a deadline-bound request writer, guaranteed kill plus final wait, and made output-tail shutdown bounded without acquiring a reader thread's buffered-I/O lock.
- Added a POSIX supervisor-death pipe watchdog, fail-closed Windows Job creation/assignment behavior, Job-close fallback handling, lower worker priority, and pre-launch one-thread native-library limits.
- Added a frozen `oda-worker` protocol smoke to `build-sidecar.ps1` and a packaging contract assertion. Focused ODA/packaging tests passed 25/25.
- Repeated full verification after lifecycle hardening: Python 1129 passed/1 skipped; Rust 24 passed; TypeScript check, oxlint, Vite build, and cargo fmt check passed.

## 2026-07-19 (audit remediation — flaky full-suite run)
- Full Python suite surfaced a flaky `test_worker_timeout_returns_and_stops_late_side_effect` originally attributed to 0.75s Windows cold start. Re-investigation: timing was a red herring.
- True root cause: the test helper `_pid_exists` called `subprocess.run(["tasklist", ...], capture_output=True, text=True)`; on Simplified Chinese Windows the tasklist column headers are GBK-encoded (e.g. byte 0xd0), and `text=True` forces strict utf-8 decoding from a background `_readerthread`, surfacing as `PytestUnhandledThreadExceptionWarning: UnicodeDecodeError`. Independent of timing.
- Replacement test `test_worker_timeout_terminates_process_tree` reasserts the real invariant — worker PIDs are gone after the timeout — by polling PIDs, decoupled from the file-write race the previous test relied on.
- Test-side `_pid_exists` switched to binary read + `errors="replace"` decode. Production `oda_process.py` is unaffected by the GBK issue.
- Production-side hardening kept: `_spawn_worker` explicitly nulls `process.stdout/stderr` references after the bounded capture takes ownership, so any future `Popen.wait(timeout=)`/`communicate()` call cannot spawn a second reader on the same pipe handle. Robust against future regression in the bounded-capture path.
- Focused suite: 11 passed in 6.55s. Phase 4 reverified.
