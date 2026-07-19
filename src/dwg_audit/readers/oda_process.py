from __future__ import annotations

import ctypes
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


ODA_WORKER_COMMAND = "oda-worker"
ODA_JOB_ENV = "DWG_AUDIT_ODA_JOB_NAME"
DEFAULT_ODA_TIMEOUT_SECONDS = 300.0
MAX_WORKER_OUTPUT_BYTES = 1024 * 1024
_MAX_TIMEOUT_SECONDS = 24 * 60 * 60.0


class OdaProcessError(RuntimeError):
    """A bounded ODA worker failed before producing a valid result."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OdaProcessTimeout(OdaProcessError):
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(
            "ODA_CONVERSION_TIMEOUT",
            f"ODA worker timed out after {timeout_seconds:g}s.",
        )


@dataclass(frozen=True)
class WorkerCapture:
    returncode: int
    stdout: str
    stderr: str


def bounded_oda_timeout(value: object, *, default: float = DEFAULT_ODA_TIMEOUT_SECONDS) -> float:
    """Return a finite, positive wall-time limit for one ODA invocation."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result) or result <= 0:
        return default
    return min(_MAX_TIMEOUT_SECONDS, result)


def oda_timeout_from_config(config: object) -> float:
    if not isinstance(config, dict):
        return DEFAULT_ODA_TIMEOUT_SECONDS
    ingest = config.get("ingest", {})
    if not isinstance(ingest, dict):
        return DEFAULT_ODA_TIMEOUT_SECONDS
    return bounded_oda_timeout(ingest.get("oda_timeout_seconds"))


def oda_process_isolation_enabled(config: object) -> bool:
    if not isinstance(config, dict):
        return True
    ingest = config.get("ingest", {})
    if not isinstance(ingest, dict):
        return True
    value = ingest.get("oda_process_isolation", True)
    return value if isinstance(value, bool) else True


def worker_command() -> list[str]:
    """Build the source or frozen command that enters the worker dispatcher."""

    if getattr(sys, "frozen", False):
        return [sys.executable, ODA_WORKER_COMMAND]
    return [sys.executable, "-m", "dwg_audit.readers.oda_worker"]


def run_oda_conversion(
    source: Path,
    target: Path,
    *,
    executable: Path,
    timeout_seconds: float = DEFAULT_ODA_TIMEOUT_SECONDS,
    version: str = "R2018",
    audit: bool = True,
    replace: bool = True,
) -> None:
    response = _run_worker_request(
        {
            "operation": "convert",
            "source": str(source),
            "target": str(target),
            "executable": str(executable),
            "version": version,
            "audit": bool(audit),
            "replace": bool(replace),
        },
        timeout_seconds=timeout_seconds,
    )
    _require_success(response)


def run_oda_smoke(
    executable: Path,
    *,
    timeout_seconds: float = 10.0,
) -> bool:
    response = _run_worker_request(
        {
            "operation": "smoke",
            "executable": str(executable),
        },
        timeout_seconds=timeout_seconds,
    )
    _require_success(response)
    return bool(response.get("result"))


def _require_success(response: dict[str, Any]) -> None:
    if response.get("ok") is True:
        return
    code = str(response.get("error_code") or "ODA_WORKER_FAILED")
    detail = str(response.get("detail") or "ODA worker failed.")
    raise OdaProcessError(code, detail)


def _run_worker_request(
    request: dict[str, Any],
    *,
    timeout_seconds: float,
    command: Sequence[str] | None = None,
) -> dict[str, Any]:
    timeout = bounded_oda_timeout(timeout_seconds)
    command_line = list(command or worker_command())
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    environment.setdefault("PYTHONIOENCODING", "utf-8")

    job: _WindowsKillOnCloseJob | None = None
    try:
        if os.name == "nt":
            try:
                job = _WindowsKillOnCloseJob.create()
                environment[ODA_JOB_ENV] = job.name
            except OdaProcessError:
                # Some desktop hosts already place children in a restrictive Job.
                # Keep the bounded taskkill fallback rather than disabling ODA.
                job = None
                environment.pop(ODA_JOB_ENV, None)

        process, stdout_file, stderr_file = _spawn_worker(
            command_line,
            environment=environment,
            job=job,
        )
        try:
            payload = (json.dumps(request, ensure_ascii=True) + "\n").encode("utf-8")
            try:
                process.communicate(payload, timeout=timeout)
            except subprocess.TimeoutExpired:
                _terminate_worker(process, job)
                job = None
                _reap_worker(process)
                raise OdaProcessTimeout(timeout) from None

            capture = WorkerCapture(
                returncode=int(process.returncode or 0),
                stdout=_read_tail(stdout_file),
                stderr=_read_tail(stderr_file),
            )
        finally:
            stdout_file.close()
            stderr_file.close()
            if job is not None:
                job.close()
                job = None
    except OdaProcessError:
        if job is not None:
            job.close()
        raise
    except OSError as exc:
        if job is not None:
            job.close()
        raise OdaProcessError("ODA_WORKER_SPAWN_FAILED", str(exc)) from exc

    response = _decode_worker_response(capture)
    if capture.returncode != 0 and response is None:
        detail = capture.stderr or capture.stdout or f"worker exited with code {capture.returncode}"
        raise OdaProcessError("ODA_WORKER_FAILED", detail)
    if response is None:
        detail = capture.stderr or "ODA worker returned an invalid response."
        raise OdaProcessError("ODA_WORKER_PROTOCOL", detail)
    return response


def _spawn_worker(
    command: Sequence[str],
    *,
    environment: dict[str, str],
    job: _WindowsKillOnCloseJob | None,
) -> tuple[subprocess.Popen[bytes], Any, Any]:
    stdout_file = tempfile.TemporaryFile(mode="w+b")
    stderr_file = tempfile.TemporaryFile(mode="w+b")
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.PIPE,
            stdout=stdout_file,
            stderr=stderr_file,
            env=environment,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        if job is not None:
            try:
                job.assign_process(process.pid)
            except OdaProcessError:
                _terminate_worker(process, job)
                raise
        return process, stdout_file, stderr_file
    except BaseException:
        stdout_file.close()
        stderr_file.close()
        raise


def _read_tail(stream: Any, limit: int = MAX_WORKER_OUTPUT_BYTES) -> str:
    try:
        stream.seek(0, os.SEEK_END)
        size = int(stream.tell())
        stream.seek(max(0, size - limit), os.SEEK_SET)
        data = stream.read(limit)
    except (OSError, ValueError):
        return ""
    if not isinstance(data, bytes):
        return str(data)
    return data.decode("utf-8", errors="replace")


def _decode_worker_response(capture: WorkerCapture) -> dict[str, Any] | None:
    # A frozen bootloader or a diagnostic fake may write a preamble. The worker
    # response is always the last JSON object, so parse from the tail backwards.
    for line in reversed([line.strip() for line in capture.stdout.splitlines() if line.strip()]):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _reap_worker(process: subprocess.Popen[bytes]) -> None:
    try:
        process.communicate(timeout=2.0)
    except (subprocess.TimeoutExpired, OSError):
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=1.0)
        except (subprocess.TimeoutExpired, OSError):
            pass


def _terminate_worker(
    process: subprocess.Popen[bytes],
    job: _WindowsKillOnCloseJob | None,
) -> None:
    if job is not None:
        job.close()
    if os.name == "nt":
        _taskkill_tree(process.pid)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
        try:
            process.wait(timeout=0.25)
        except (subprocess.TimeoutExpired, OSError):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
    try:
        process.kill()
    except OSError:
        pass


def _taskkill_tree(pid: int) -> None:
    if os.name != "nt":
        return
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        killer = subprocess.Popen(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except OSError:
        return
    try:
        killer.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        try:
            killer.kill()
        except OSError:
            pass
        try:
            killer.wait(timeout=0.5)
        except (subprocess.TimeoutExpired, OSError):
            pass


if os.name == "nt":
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _JOB_OBJECT_ASSIGN_PROCESS = 0x0001
    _JOB_OBJECT_QUERY = 0x0004
    _PROCESS_TERMINATE = 0x0001
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _ERROR_ACCESS_DENIED = 5
    _ERROR_ALREADY_EXISTS = 183

    class _JobBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [("values", ctypes.c_uint64 * 6)]

    class _JobExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JobBasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]
else:
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _JOB_OBJECT_ASSIGN_PROCESS = 0x0001
    _JOB_OBJECT_QUERY = 0x0004
    _ERROR_ACCESS_DENIED = 5
    _ERROR_ALREADY_EXISTS = 183


class _WindowsKillOnCloseJob:
    def __init__(self, handle: int, name: str) -> None:
        self._handle = handle
        self.name = name

    @classmethod
    def create(cls) -> "_WindowsKillOnCloseJob":
        if os.name != "nt":
            raise OdaProcessError("ODA_JOB_UNAVAILABLE", "Windows Job Objects are unavailable.")
        kernel32 = _kernel32()
        name = f"Local\\dwg_audit_oda_{uuid.uuid4().hex}"
        ctypes.set_last_error(0)
        handle = kernel32.CreateJobObjectW(None, name)
        if not handle:
            raise _win32_error("ODA_JOB_CREATE_FAILED")
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            raise OdaProcessError("ODA_JOB_CREATE_FAILED", "ODA worker Job Object name collision.")
        info = _JobExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            code = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            raise OdaProcessError("ODA_JOB_CONFIG_FAILED", ctypes.WinError(code).__str__())
        return cls(int(handle), name)

    def assign_process(self, pid: int) -> None:
        if os.name != "nt":
            return
        kernel32 = _kernel32()
        access = _PROCESS_TERMINATE | _PROCESS_SET_QUOTA | _PROCESS_QUERY_LIMITED_INFORMATION
        process_handle = kernel32.OpenProcess(access, False, int(pid))
        if not process_handle:
            raise _win32_error("ODA_JOB_PROCESS_OPEN_FAILED")
        try:
            if kernel32.AssignProcessToJobObject(self._handle, process_handle):
                return
            code = ctypes.get_last_error()
            if code == _ERROR_ACCESS_DENIED and _is_process_in_job(kernel32, process_handle, self._handle):
                return
            raise OdaProcessError("ODA_JOB_ASSIGN_FAILED", ctypes.WinError(code).__str__())
        finally:
            kernel32.CloseHandle(process_handle)

    def close(self) -> None:
        handle = getattr(self, "_handle", 0)
        if not handle or os.name != "nt":
            return
        self._handle = 0
        try:
            _kernel32().CloseHandle(handle)
        except (AttributeError, OSError):
            pass


def _kernel32():
    if os.name != "nt":
        raise OdaProcessError("ODA_JOB_UNAVAILABLE", "Windows Job Objects are unavailable.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.SetInformationJobObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    kernel32.SetInformationJobObject.restype = ctypes.c_int
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.AssignProcessToJobObject.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.OpenJobObjectW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.OpenJobObjectW.restype = ctypes.c_void_p
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    kernel32.IsProcessInJob.restype = ctypes.c_int
    return kernel32


def _is_process_in_job(kernel32, process_handle: int, job_handle: int) -> bool:
    result = ctypes.c_int(0)
    if not kernel32.IsProcessInJob(process_handle, job_handle, ctypes.byref(result)):
        return False
    return bool(result.value)


def _win32_error(code: str) -> OdaProcessError:
    error = ctypes.get_last_error()
    return OdaProcessError(code, ctypes.WinError(error).__str__())


def join_named_windows_job(name: str | None = None) -> None:
    """Join the parent-created Job before a worker accepts its request."""

    if os.name != "nt" or not name:
        return
    kernel32 = _kernel32()
    handle = kernel32.OpenJobObjectW(
        _JOB_OBJECT_ASSIGN_PROCESS | _JOB_OBJECT_QUERY,
        False,
        name,
    )
    if not handle:
        raise _win32_error("ODA_JOB_OPEN_FAILED")
    try:
        current = kernel32.GetCurrentProcess()
        if kernel32.AssignProcessToJobObject(handle, current):
            return
        code = ctypes.get_last_error()
        if code == _ERROR_ACCESS_DENIED and _is_process_in_job(kernel32, current, handle):
            return
        raise OdaProcessError("ODA_JOB_JOIN_FAILED", ctypes.WinError(code).__str__())
    finally:
        kernel32.CloseHandle(handle)
