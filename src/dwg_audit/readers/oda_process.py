from __future__ import annotations

import ctypes
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

if os.name != "nt":
    import fcntl


ODA_WORKER_COMMAND = "oda-worker"
ODA_JOB_ENV = "DWG_AUDIT_ODA_JOB_NAME"
ODA_PARENT_WATCH_ENV = "DWG_AUDIT_ODA_PARENT_WATCH_FD"
DEFAULT_ODA_TIMEOUT_SECONDS = 300.0
MAX_WORKER_OUTPUT_BYTES = 1024 * 1024
_MAX_TIMEOUT_SECONDS = 24 * 60 * 60.0
_CAPTURE_DRAIN_TIMEOUT_SECONDS = 1.0
_CAPTURE_STOP_TIMEOUT_SECONDS = 0.25
_WORKER_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


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


class _BoundedStreamCapture:
    """Drain a child stream continuously while retaining only a bounded tail."""

    def __init__(self, stream: Any, *, limit: int = MAX_WORKER_OUTPUT_BYTES) -> None:
        self._stream = stream
        self._fd = os.dup(int(stream.fileno()))
        os.set_inheritable(self._fd, False)
        os.set_blocking(self._fd, False)
        self._limit = limit
        self._tail = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._fd_closed = False
        self._thread = threading.Thread(target=self._drain, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _drain(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    chunk = os.read(self._fd, 64 * 1024)
                except BlockingIOError:
                    self._stop.wait(0.02)
                    continue
                if not chunk:
                    return
                with self._lock:
                    if len(chunk) >= self._limit:
                        self._tail = bytearray(chunk[-self._limit :])
                    else:
                        self._tail.extend(chunk)
                        if len(self._tail) > self._limit:
                            del self._tail[: len(self._tail) - self._limit]
        except (OSError, ValueError):
            return
        finally:
            self._close_descriptors()

    def _close_descriptors(self) -> None:
        with self._lock:
            if self._fd_closed:
                return
            self._fd_closed = True
            fd = self._fd
            self._fd = -1
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            self._stream.close()
        except (OSError, ValueError):
            pass

    def text(self) -> str:
        self._thread.join(timeout=_CAPTURE_DRAIN_TIMEOUT_SECONDS)
        if self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=_CAPTURE_STOP_TIMEOUT_SECONDS)
        with self._lock:
            data = bytes(self._tail)
        return data.decode("utf-8", errors="replace")


class _WorkerRequestWriter:
    def __init__(self, stream: Any, payload: bytes) -> None:
        self._fd = os.dup(int(stream.fileno()))
        os.set_inheritable(self._fd, False)
        self._payload = payload
        self._error: BaseException | None = None
        self._closed = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._write,
            name="oda-request-writer",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def _write(self) -> None:
        fd = self._fd
        try:
            remaining = memoryview(self._payload)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("ODA worker stdin accepted no data.")
                remaining = remaining[written:]
        except BaseException as exc:
            self._error = exc
        finally:
            self.close()

    def wait(self, timeout: float) -> bool:
        self._thread.join(timeout=max(0.0, timeout))
        return not self._thread.is_alive()

    @property
    def error(self) -> BaseException | None:
        return self._error

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            fd = self._fd
            self._fd = -1
        try:
            os.close(fd)
        except OSError:
            pass


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
    if not isinstance(config, Mapping):
        return DEFAULT_ODA_TIMEOUT_SECONDS
    ingest = config.get("ingest", {})
    if not isinstance(ingest, dict):
        return DEFAULT_ODA_TIMEOUT_SECONDS
    return bounded_oda_timeout(ingest.get("oda_timeout_seconds"))


def oda_process_isolation_enabled(config: object) -> bool:
    if not isinstance(config, Mapping):
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


def apply_worker_resource_policy() -> None:
    """Give the foreground desktop priority over an ODA worker by default."""

    for variable in _WORKER_THREAD_ENV_VARS:
        os.environ[variable] = "1"
    if os.name == "nt":
        try:
            kernel32 = _kernel32()
            below_normal = 0x00004000
            kernel32.SetPriorityClass(
                kernel32.GetCurrentProcess(),
                below_normal,
            )
        except (OdaProcessError, OSError, AttributeError):
            pass
        return
    try:
        os.nice(5)
    except (AttributeError, OSError):
        pass


def start_parent_watchdog() -> None:
    """Kill the worker session if the supervising process disappears.

    POSIX has no Windows Job Object equivalent.  A pipe held only by the
    supervisor gives the worker an ownership signal that also works on
    platforms without Linux ``prctl``: EOF means the supervisor died.
    """

    if os.name == "nt":
        return
    raw_fd = os.environ.get(ODA_PARENT_WATCH_ENV)
    if not raw_fd:
        return
    try:
        read_fd = int(raw_fd)
    except ValueError:
        return

    def watch() -> None:
        parent_gone = False
        try:
            while True:
                if not os.read(read_fd, 1):
                    parent_gone = True
                    break
        except (OSError, ValueError):
            return
        finally:
            try:
                os.close(read_fd)
            except OSError:
                pass
        if not parent_gone:
            return
        try:
            os.killpg(os.getpgrp(), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            try:
                os.kill(os.getpid(), signal.SIGKILL)
            except OSError:
                pass

    threading.Thread(target=watch, name="oda-parent-watchdog", daemon=True).start()


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
    deadline = time.monotonic() + timeout
    command_line = list(command or worker_command())
    try:
        payload = (json.dumps(request, ensure_ascii=True) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OdaProcessError("ODA_WORKER_REQUEST", str(exc)) from exc
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    for variable in _WORKER_THREAD_ENV_VARS:
        environment[variable] = "1"

    job: _WindowsKillOnCloseJob | None = None
    process: subprocess.Popen[bytes] | None = None
    stdout_capture: _BoundedStreamCapture | None = None
    stderr_capture: _BoundedStreamCapture | None = None
    parent_watch_write: int | None = None
    parent_watch_read: int | None = None
    try:
        if os.name == "nt":
            job = _WindowsKillOnCloseJob.create()
            environment[ODA_JOB_ENV] = job.name
        else:
            parent_watch_read, parent_watch_write = _open_parent_watch_pipe()
            os.set_inheritable(parent_watch_read, True)
            environment[ODA_PARENT_WATCH_ENV] = str(parent_watch_read)

        process, stdout_capture, stderr_capture = _spawn_worker(
            command_line,
            environment=environment,
            job=job,
            pass_fds=(parent_watch_read,) if parent_watch_read is not None else (),
        )
        if parent_watch_read is not None:
            _close_fd(parent_watch_read)
        parent_watch_read = None

        if process.stdin is None:
            raise OdaProcessError("ODA_WORKER_IO_FAILED", "ODA worker stdin is unavailable.")
        _write_worker_request(process, payload, deadline=deadline, timeout_seconds=timeout)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OdaProcessTimeout(timeout)
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise OdaProcessTimeout(timeout) from None

        if job is not None:
            if not job.close():
                _taskkill_tree(process.pid)
            job = None
        _reap_worker(process)
        capture = WorkerCapture(
            returncode=int(process.returncode or 0),
            stdout=stdout_capture.text(),
            stderr=stderr_capture.text(),
        )
    except OdaProcessError:
        if process is not None:
            _terminate_worker(process, job)
            _reap_worker(process)
        if stdout_capture is not None:
            stdout_capture.text()
        if stderr_capture is not None:
            stderr_capture.text()
        if job is not None:
            job.close()
        raise
    except BaseException as exc:
        if process is not None:
            _terminate_worker(process, job)
            _reap_worker(process)
        if stdout_capture is not None:
            stdout_capture.text()
        if stderr_capture is not None:
            stderr_capture.text()
        if job is not None:
            job.close()
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise OdaProcessError("ODA_WORKER_FAILED", str(exc)) from exc
    finally:
        if parent_watch_read is not None:
            _close_fd(parent_watch_read)
        if parent_watch_write is not None:
            _close_fd(parent_watch_write)

    response = _decode_worker_response(capture)
    if response is None:
        code = "ODA_WORKER_FAILED" if capture.returncode != 0 else "ODA_WORKER_PROTOCOL"
        detail = capture.stderr or capture.stdout or f"worker exited with code {capture.returncode}"
        if code == "ODA_WORKER_PROTOCOL":
            detail = f"ODA worker returned an invalid response: {detail}"
        raise OdaProcessError(code, detail)
    ok = response.get("ok")
    if not isinstance(ok, bool):
        raise OdaProcessError("ODA_WORKER_PROTOCOL", "ODA worker response has no boolean ok field.")
    if capture.returncode == 0 and not ok:
        raise OdaProcessError(
            "ODA_WORKER_PROTOCOL",
            "ODA worker returned ok=false with exit code 0.",
        )
    if capture.returncode != 0 and ok:
        raise OdaProcessError(
            "ODA_WORKER_FAILED",
            f"ODA worker exited with code {capture.returncode} after reporting success.",
        )
    return response


def _spawn_worker(
    command: Sequence[str],
    *,
    environment: dict[str, str],
    job: _WindowsKillOnCloseJob | None,
    pass_fds: Sequence[int] = (),
) -> tuple[subprocess.Popen[bytes], Any, Any]:
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    process: subprocess.Popen[bytes] | None = None
    stdout_capture: _BoundedStreamCapture | None = None
    stderr_capture: _BoundedStreamCapture | None = None
    try:
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": environment,
            "creationflags": creationflags,
            "start_new_session": os.name != "nt",
        }
        if os.name != "nt":
            popen_kwargs["pass_fds"] = tuple(pass_fds)
        process = subprocess.Popen(list(command), **popen_kwargs)
        if os.name != "nt":
            process._oda_pgid = int(process.pid)  # type: ignore[attr-defined]
        if process.stdout is None or process.stderr is None:
            raise OdaProcessError("ODA_WORKER_SPAWN_FAILED", "ODA worker pipes are unavailable.")
        stdout_capture = _BoundedStreamCapture(process.stdout)
        stderr_capture = _BoundedStreamCapture(process.stderr)
        # Drop the Popen-owned file objects so that Popen.wait()/communicate() does
        # NOT spawn its own ``_readerthread`` readers on the same pipe handles we
        # already drain via the bounded capture. Without this, on Windows a
        # timed-out ``process.wait`` falls back to ``_communicate`` which performs
        # a strict ``utf-8`` decode of mixed worker+grandchild stdout bytes and
        # raises UnicodeDecodeError from a background reader thread.
        process.stdout = None
        process.stderr = None
        stdout_capture.start()
        stderr_capture.start()
        if job is not None:
            job.assign_process(process.pid)
        return process, stdout_capture, stderr_capture
    except OSError as exc:
        if process is not None:
            _terminate_worker(process, None)
            _reap_worker(process)
        if stdout_capture is not None:
            stdout_capture.text()
        if stderr_capture is not None:
            stderr_capture.text()
        raise OdaProcessError("ODA_WORKER_SPAWN_FAILED", str(exc)) from exc
    except BaseException:
        if process is not None:
            # Assignment may have failed before the process entered the Job.
            _terminate_worker(process, None)
            _reap_worker(process)
        if stdout_capture is not None:
            stdout_capture.text()
        if stderr_capture is not None:
            stderr_capture.text()
        raise


def _decode_worker_response(capture: WorkerCapture) -> dict[str, Any] | None:
    lines = [line.strip() for line in capture.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _write_worker_request(
    process: subprocess.Popen[bytes],
    payload: bytes,
    *,
    deadline: float,
    timeout_seconds: float,
) -> None:
    stream = process.stdin
    if stream is None:
        raise OdaProcessError("ODA_WORKER_IO_FAILED", "ODA worker stdin is unavailable.")
    writer = _WorkerRequestWriter(stream, payload)
    process._oda_request_writer = writer  # type: ignore[attr-defined]
    writer.start()
    remaining = max(0.0, deadline - time.monotonic())
    if not writer.wait(remaining):
        raise OdaProcessTimeout(timeout_seconds)
    if writer.error is not None:
        exc = writer.error
        if isinstance(exc, (BrokenPipeError, OSError, ValueError)):
            raise OdaProcessError("ODA_WORKER_IO_FAILED", str(exc)) from exc
        raise exc
    _close_worker_stdin(process)
    process._oda_request_writer = None  # type: ignore[attr-defined]


def _reap_worker(process: subprocess.Popen[bytes]) -> None:
    _close_worker_stdin(process)
    _join_worker_writer(process)
    try:
        process.wait(timeout=2.0)
    except (subprocess.TimeoutExpired, OSError):
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=1.0)
        except (subprocess.TimeoutExpired, OSError):
            pass


def _close_worker_stdin(process: subprocess.Popen[bytes]) -> None:
    stream = process.stdin
    if stream is None:
        return
    process.stdin = None
    try:
        stream.close()
    except (OSError, ValueError):
        pass


def _join_worker_writer(process: subprocess.Popen[bytes]) -> None:
    writer = getattr(process, "_oda_request_writer", None)
    if not isinstance(writer, _WorkerRequestWriter):
        return
    writer.close()
    if writer.wait(1.0):
        process._oda_request_writer = None  # type: ignore[attr-defined]


def _close_fd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


def _open_parent_watch_pipe() -> tuple[int, int]:
    read_fd, write_fd = os.pipe()
    try:
        read_fd = _move_fd_above_stdio(read_fd)
        write_fd = _move_fd_above_stdio(write_fd)
        return read_fd, write_fd
    except BaseException:
        _close_fd(read_fd)
        _close_fd(write_fd)
        raise


def _move_fd_above_stdio(fd: int) -> int:
    if fd > 2:
        return fd
    replacement = fcntl.fcntl(fd, fcntl.F_DUPFD, 3)
    os.close(fd)
    return replacement


def _terminate_worker(
    process: subprocess.Popen[bytes],
    job: _WindowsKillOnCloseJob | None,
) -> None:
    # A one-file frozen worker can spawn its inner process before the outer
    # bootloader is assigned to the Job Object.  Enumerate the live parent
    # tree first, then close the Job to catch workers that joined it later.
    if os.name == "nt":
        _taskkill_tree(process.pid)
    job_closed = True
    if job is not None:
        job_closed = job.close()
    if os.name == "nt":
        if not job_closed:
            _taskkill_tree(process.pid)
    else:
        pgid = int(getattr(process, "_oda_pgid", process.pid))
        _kill_process_group(pgid, signal.SIGTERM)
        _kill_process_group(pgid, signal.SIGKILL)
    try:
        process.kill()
    except OSError:
        pass
    _close_worker_stdin(process)
    _join_worker_writer(process)


def _kill_process_group(pgid: int, signum: int) -> None:
    if os.name == "nt":
        return
    try:
        os.killpg(pgid, signum)
    except (ProcessLookupError, OSError):
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

    def close(self) -> bool:
        handle = getattr(self, "_handle", 0)
        if not handle or os.name != "nt":
            return True
        try:
            kernel32 = _kernel32()
            if kernel32.CloseHandle(handle):
                self._handle = 0
                return True
        except (AttributeError, OSError):
            return False
        return False


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
    kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.SetPriorityClass.restype = ctypes.c_int
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
