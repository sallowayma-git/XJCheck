# Findings: ODA Process Isolation

## Confirmed failure mode
- Installed ezdxf 1.4.4 uses Windows `Popen(stdout=PIPE, stderr=PIPE)`, calls `wait()` with no timeout, and only then reads both pipes. A chatty ODA process can fill a pipe and deadlock before exit.
- `ThreadPoolExecutor` cannot terminate that native child. Leaving the executor calls `shutdown(wait=True)`, so a blocked conversion can hold the full workflow forever.
- The existing health smoke uses a daemon thread timeout. Returning `degraded` does not terminate the callback or any ODA descendant.

## Integration contracts
- `convert_one` owns cache checks, status/error mapping, event emission, source mutation, timing, and ReaderRun creation. Only the external ODA call should move to the worker.
- Converted targets remain `converted_dxf/{file_id}_{sha-prefix}.dxf`; stage files remain under `odafc_stage`.
- Reader runs are returned in source order while completion events are emitted in completion order.
- Existing tests monkeypatch `dwg_converter.odafc.convert`; the new code needs an explicit parent-process injection seam because Windows child processes cannot inherit monkeypatches.
- Conversion currently wraps the entire bounded thread batch in `oda_execution_environment`. With per-call workers, production can stop mutating parent-global `PATH`/ezdxf options; a deliberately injected in-process test runner may still need that context.
- Default health checks used by conversion call `health_check(smoke=False)`, so they do not launch ODA. Explicit `smoke=True` is the leaked-daemon-thread path that must use the isolated runner for the built-in smoke callback.
- `OdaFileConverterReader.read` is another synchronous ODA entry point and should use the same isolated runner, then retain its existing parent-side `ezdxf.readfile` validation.
- Current ingest defaults have no timeout. Add a finite per-conversion setting while preserving the existing adaptive worker/resource gate.

## OS ownership
- Windows needs a per-worker Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
- To avoid assignment races, the worker must wait for a stdin request; the parent assigns it to the Job before sending work.
- PyInstaller onefile uses an outer bootloader and an inner Python process. Parent-side PID assignment alone can race the inner spawn, so the parent creates a uniquely named Job and passes its name in the environment; the actual worker must join that Job before reading the request.
- Worker Job assignment is fail-closed: if the inner process cannot join, it must exit before ODA starts. The parent remains the last Job handle owner and closing it terminates the full assigned tree.
- POSIX workers should start in a new session and use `killpg` on timeout.
- Rust currently stores PIDs, not owned handles. Its detached cleanup sidecars intentionally survive desktop exit, so a global Tauri Job Object would violate existing behavior.

## Packaging
- Source development can launch `python -m dwg_audit.readers.oda_worker`.
- Frozen/PyInstaller execution must route an internal worker command through the packaged sidecar executable rather than assume `-m` works.
- The normal source entry point is `dwg_audit.cli`, while the packaged application has a dedicated `dwg_audit.desktop.sidecar_entry`; worker routing must be supported by both entry paths.
- `desktop.sidecar_entry` already has an argparse-based lightweight-command fast path before importing the large Typer CLI graph. The internal ODA worker should use this same early dispatch so each conversion does not import unrelated report/UI modules.
- The packaged worker can invoke `sys.executable <internal-command>`; the source worker can invoke `sys.executable -m dwg_audit.readers.oda_worker`.
- The worker dispatch must run before `_run_lightweight_command`, because that function imports the SQLite state store before parsing. The PyInstaller spec should explicitly include the worker module.

## Test seam
- There are 27 existing `dwg_converter.odafc.convert` patches: 23 in `test_analyze_project.py`, one in `acceptance_mini.py`, and three in `test_dwg_converter.py`.
- All fake converters accept source/target positionally and extra keywords, so an explicit module-level `_oda_conversion_runner` can preserve the call shape. Tests should patch that seam directly; production must never auto-detect pytest or monkeypatches to disable isolation.
- The first focused run passed 62/63 Python tests; the only failure was the historical exact-kwargs assertion, which now needs to include the worker executable and timeout fields.
