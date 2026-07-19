from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from dwg_audit.readers.oda_process import OdaProcessError
from dwg_audit.readers.oda_process import OdaProcessTimeout
from dwg_audit.readers.oda_process import _run_worker_request
from dwg_audit.readers.oda_process import bounded_oda_timeout
from dwg_audit.readers.oda_process import join_named_windows_job


def _command(source: str) -> list[str]:
    return [sys.executable, "-c", source]


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


def test_worker_timeout_returns_and_stops_late_side_effect(tmp_path: Path) -> None:
    started = tmp_path / "started.txt"
    finished = tmp_path / "finished.txt"
    child = (
        "import pathlib, sys, time; "
        f"sys.stdin.buffer.readline(); pathlib.Path({str(started)!r}).write_text('started'); "
        "time.sleep(30); "
        f"pathlib.Path({str(finished)!r}).write_text('finished')"
    )

    started_at = time.monotonic()
    with pytest.raises(OdaProcessTimeout):
        _run_worker_request(
            {"operation": "test"},
            timeout_seconds=0.75,
            command=_command(child),
        )
    elapsed = time.monotonic() - started_at

    assert elapsed < 5.0
    assert started.exists()
    time.sleep(0.2)
    assert not finished.exists()


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


def test_timeout_normalization_and_non_windows_job_noop() -> None:
    assert bounded_oda_timeout(float("nan")) == 300.0
    assert bounded_oda_timeout(-1) == 300.0
    assert bounded_oda_timeout(999999) == 86400.0
    join_named_windows_job(None)
