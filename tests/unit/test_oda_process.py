from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from dwg_audit.readers.oda_process import OdaProcessError
from dwg_audit.readers.oda_process import OdaProcessTimeout
from dwg_audit.readers.oda_process import _run_worker_request
from dwg_audit.readers.oda_process import _BoundedStreamCapture
from dwg_audit.readers.oda_process import bounded_oda_timeout
from dwg_audit.readers.oda_process import join_named_windows_job
from dwg_audit.readers.oda_process import MAX_WORKER_OUTPUT_BYTES


def _command(source: str) -> list[str]:
    return [sys.executable, "-c", source]


def _assert_pid_gone(pid: int, *, deadline: float) -> None:
    """Poll until a PID is no longer alive, or fail if ``deadline`` (monotonic) lapses."""

    while time.monotonic() < deadline:
        if not _pid_exists(pid):
            return
        time.sleep(0.1)
    if _pid_exists(pid):
        raise AssertionError(f"PID {pid} still alive past deadline {deadline:g}")


def test_worker_request_drains_large_stdout_without_deadlock() -> None:
    child = (
        "import sys; "
        "sys.stdin.buffer.readline(); "
        "sys.stdout.write('x' * 2000000); "
        "sys.stdout.write('\\n{\\\"ok\\\": true, \\\"result\\\": 7}\\n'); "
        "sys.stdout.flush()"
    )

    response = _run_worker_request(
        {"operation": "test"},
        timeout_seconds=5.0,
        command=_command(child),
    )

    assert response == {"ok": True, "result": 7}


def test_capture_shutdown_is_bounded_when_writer_keeps_pipe_open() -> None:
    read_fd, write_fd = os.pipe()
    stream = os.fdopen(read_fd, "rb")
    capture = _BoundedStreamCapture(stream)
    capture.start()
    started_at = time.monotonic()
    try:
        assert capture.text() == ""
        assert time.monotonic() - started_at < 2.0
        assert not capture._thread.is_alive()
    finally:
        os.close(write_fd)


def test_worker_write_timeout_is_bounded_when_child_never_reads() -> None:
    child = "import time; time.sleep(30)"
    started_at = time.monotonic()
    with pytest.raises(OdaProcessTimeout):
        _run_worker_request(
            {"operation": "test", "payload": "x" * 2_000_000},
            timeout_seconds=0.5,
            command=_command(child),
        )

    assert time.monotonic() - started_at < 5.0
    assert not any(thread.name == "oda-request-writer" for thread in threading.enumerate())


def test_worker_timeout_terminates_process_tree(tmp_path: Path) -> None:
    # The invariant this test protects is that a timed-out worker's whole native
    # subtree is reaped -- not just the Python parent. We assert it by polling
    # for the absence of both PIDs after the timeout fires, rather than by
    # timing a side-effect file write (which races with a generous timeout
    # against a cold Windows Python startup under load).
    grandchild_pid = tmp_path / "grandchild.pid"
    grandchild_code = "import time; time.sleep(60)"
    child = (
        "import pathlib, subprocess, sys, time, os; "
        "grandchild = subprocess.Popen("
        f"[sys.executable, '-c', {grandchild_code!r}], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        f"pathlib.Path({str(grandchild_pid)!r}).write_text(str(grandchild.pid)); "
        "sys.stdin.buffer.readline(); "
        "time.sleep(60)"
    )

    started_at = time.monotonic()
    with pytest.raises(OdaProcessTimeout):
        _run_worker_request(
            {"operation": "test"},
            timeout_seconds=3.0,
            command=_command(child),
        )
    elapsed = time.monotonic() - started_at
    assert elapsed < 8.0

    # If the grandchild pid file was written, the kill must have reached it too.
    if grandchild_pid.exists():
        grandchild = int(grandchild_pid.read_text(encoding="utf-8"))
        _assert_pid_gone(grandchild, deadline=started_at + 10.0)


def test_worker_invalid_protocol_is_reported() -> None:
    child = "import sys; sys.stdin.buffer.readline(); print('not-json'); sys.stdout.flush()"

    with pytest.raises(OdaProcessError, match="invalid response") as exc_info:
        _run_worker_request(
            {"operation": "test"},
            timeout_seconds=2.0,
            command=_command(child),
        )

    assert exc_info.value.code == "ODA_WORKER_PROTOCOL"


def test_worker_crash_is_bounded_and_structured() -> None:
    child = "import sys; sys.stdin.buffer.readline(); raise SystemExit(17)"

    with pytest.raises(OdaProcessError) as exc_info:
        _run_worker_request(
            {"operation": "test"},
            timeout_seconds=2.0,
            command=_command(child),
        )

    assert exc_info.value.code == "ODA_WORKER_FAILED"


def test_nonzero_worker_cannot_claim_success() -> None:
    child = (
        "import sys; sys.stdin.buffer.readline(); "
        "print('{\"ok\": true}'); sys.stdout.flush(); raise SystemExit(17)"
    )

    with pytest.raises(OdaProcessError) as exc_info:
        _run_worker_request(
            {"operation": "test"},
            timeout_seconds=2.0,
            command=_command(child),
        )

    assert exc_info.value.code == "ODA_WORKER_FAILED"


def test_trailing_output_after_worker_frame_is_protocol_error() -> None:
    child = (
        "import sys; sys.stdin.buffer.readline(); "
        "print('{\"ok\": true}'); print('diagnostic tail'); sys.stdout.flush()"
    )

    with pytest.raises(OdaProcessError) as exc_info:
        _run_worker_request(
            {"operation": "test"},
            timeout_seconds=2.0,
            command=_command(child),
        )

    assert exc_info.value.code == "ODA_WORKER_PROTOCOL"


def test_stderr_capture_is_bounded() -> None:
    child = (
        "import sys; sys.stdin.buffer.readline(); "
        "sys.stderr.write('e' * 2000000); sys.stderr.flush(); "
        "raise SystemExit(17)"
    )

    with pytest.raises(OdaProcessError) as exc_info:
        _run_worker_request(
            {"operation": "test"},
            timeout_seconds=2.0,
            command=_command(child),
        )

    assert exc_info.value.code == "ODA_WORKER_FAILED"
    assert len(str(exc_info.value)) <= MAX_WORKER_OUTPUT_BYTES


def test_worker_request_is_serialized_before_spawn() -> None:
    with pytest.raises(OdaProcessError) as exc_info:
        _run_worker_request(
            {"operation": object()},
            timeout_seconds=2.0,
            command=_command("raise SystemExit(99)"),
        )

    assert exc_info.value.code == "ODA_WORKER_REQUEST"


def test_packaged_worker_dispatcher_accepts_request() -> None:
    response = _run_worker_request(
        {"operation": "unsupported-test-operation"},
        timeout_seconds=5.0,
    )

    assert response["ok"] is False
    assert response["error_code"] == "ODA_WORKER_PROTOCOL"


def test_timeout_normalization_and_non_windows_job_noop() -> None:
    assert bounded_oda_timeout(float("nan")) == 300.0
    assert bounded_oda_timeout(-1) == 300.0
    assert bounded_oda_timeout(999999) == 86400.0
    join_named_windows_job(None)


def _pid_exists(pid: int) -> bool:
    if os.name == "nt":
        # Read tasklist output as bytes and decode leniently: on a Simplified
        # Chinese Windows the column headers contain GBK bytes (e.g. 0xd0)
        # which ``subprocess.run(text=True)`` fails to decode as strict utf-8
        # from an internal reader thread, surfacing as a
        # PytestUnhandledThreadExceptionWarning. Binary + errors="replace"
        # sidesteps that entirely.
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            check=False,
        )
        if result.stdout is None:
            return False
        return str(pid) in result.stdout.decode("utf-8", errors="replace")
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True
