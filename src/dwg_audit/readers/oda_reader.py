from __future__ import annotations

import os
import platform
import shutil
import hashlib
import queue
import re
import threading
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc

from dwg_audit.readers.base import (
    CadDocument,
    ReaderCapabilities,
    ReaderError,
    ReaderHealth,
    ReaderHealthStatus,
    ReaderOptions,
    ReaderProbe,
)

VersionReader = Callable[[Path], str | None]
SmokeCheck = Callable[[Path], bool]


ODA_CAPABILITIES = ReaderCapabilities(
    native_dwg=True,
    blocks=True,
    xdata=False,
    layouts=True,
    preview=False,
    write_support=True,
)


def _existing_file(value: str | os.PathLike[str] | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_file() else None


def _windows_install_candidates(environ: Mapping[str, str]) -> list[Path]:
    roots = [
        environ.get("ProgramFiles"),
        environ.get("ProgramW6432"),
        environ.get("ProgramFiles(x86)"),
    ]
    candidates: set[Path] = {
        Path(r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"),
        Path(r"C:\Program Files\ODA\ODAFileConverter 26.9.0\ODAFileConverter.exe"),
    }
    for root in roots:
        if not root:
            continue
        oda_root = Path(root) / "ODA"
        if oda_root.is_dir():
            candidates.update(oda_root.glob("ODAFileConverter */ODAFileConverter.exe"))
    return sorted(candidates, key=lambda item: str(item).casefold(), reverse=True)


def _bundled_oda_candidates(
    environ: Mapping[str, str],
    *,
    resource_dir: Path | None = None,
) -> list[Path]:
    """Return packaged-layout ODA executable candidates (install-dir free)."""
    roots: list[Path] = []
    if resource_dir is not None:
        roots.append(resource_dir)
    for variable in ("DWG_AUDIT_RESOURCE_DIR", "DWG_AUDIT_BUNDLED_ODA_DIR"):
        raw = environ.get(variable)
        if raw and raw.strip():
            roots.append(Path(raw).expanduser())
    # When the desktop sidecar is a one-file exe, its sibling `oda/` folder is
    # the primary offline fallback for machines without a system ODA install.
    for variable in ("DWG_AUDIT_SIDECAR_EXE", "DWG_AUDIT_SIDECAR_DIR"):
        raw = environ.get(variable)
        if not raw or not raw.strip():
            continue
        path = Path(raw).expanduser()
        if path.is_file():
            roots.append(path.parent)
            roots.append(path.parent.parent)
        else:
            roots.append(path)

    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        for relative in (
            Path("oda") / "ODAFileConverter.exe",
            Path("oda") / "ODAFileConverter",
            Path("ODAFileConverter") / "ODAFileConverter.exe",
            Path("ODAFileConverter") / "ODAFileConverter",
            Path("ODAFileConverter.exe"),
            Path("ODAFileConverter"),
        ):
            candidate = (root / relative).resolve()
            key = str(candidate).casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def discover_oda_file_converter(
    config: Mapping[str, object],
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    system: str | None = None,
    resource_dir: Path | None = None,
) -> ReaderProbe:
    environment = os.environ if environ is None else environ
    ingest = config.get("ingest", {})
    ingest_config = ingest if isinstance(ingest, Mapping) else {}

    configured = _existing_file(ingest_config.get("odafc_path"))
    if configured is not None:
        return ReaderProbe(
            backend_name="odafc",
            available=True,
            capabilities=ODA_CAPABILITIES,
            executable_path=configured,
            discovery_source="config",
        )

    for variable in ("ODAFC_PATH", "ODA_FILE_CONVERTER"):
        candidate = _existing_file(environment.get(variable))
        if candidate is not None:
            return ReaderProbe(
                backend_name="odafc",
                available=True,
                capabilities=ODA_CAPABILITIES,
                executable_path=candidate,
                discovery_source=f"env:{variable}",
            )

    for candidate in _bundled_oda_candidates(environment, resource_dir=resource_dir):
        if candidate.is_file():
            return ReaderProbe(
                backend_name="odafc",
                available=True,
                capabilities=ODA_CAPABILITIES,
                executable_path=candidate,
                discovery_source="bundled-resource",
            )

    for command in ("ODAFileConverter", "ODAFileConverter.exe"):
        candidate = _existing_file(which(command))
        if candidate is not None:
            return ReaderProbe(
                backend_name="odafc",
                available=True,
                capabilities=ODA_CAPABILITIES,
                executable_path=candidate,
                discovery_source=f"path:{command}",
            )

    current_system = platform.system() if system is None else system
    if current_system == "Windows":
        for candidate in _windows_install_candidates(environment):
            if candidate.is_file():
                return ReaderProbe(
                    backend_name="odafc",
                    available=True,
                    capabilities=ODA_CAPABILITIES,
                    executable_path=candidate,
                    discovery_source="windows-install",
                )

    return ReaderProbe(
        backend_name="odafc",
        available=False,
        capabilities=ODA_CAPABILITIES,
        detail="ODA File Converter executable not found.",
    )


def _infer_version_from_path(executable: Path) -> str | None:
    """Return a conservative version hint without executing the converter."""
    match = re.search(r"(?<!\d)(\d{2,4}(?:\.\d+){1,3})(?!\d)", str(executable))
    return match.group(1) if match else None


def _windows_file_version(executable: Path) -> str | None:
    """Read the Windows VERSIONINFO resource; never launches the executable."""
    if platform.system() != "Windows":
        return _infer_version_from_path(executable)
    try:
        import ctypes
        from ctypes import wintypes

        version = ctypes.windll.version
        handle = wintypes.DWORD()
        size = version.GetFileVersionInfoSizeW(str(executable), ctypes.byref(handle))
        if not size:
            return _infer_version_from_path(executable)
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(executable), 0, size, buffer):
            return _infer_version_from_path(executable)
        value = ctypes.c_void_p()
        length = wintypes.UINT()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(value), ctypes.byref(length)):
            return _infer_version_from_path(executable)
        # VS_FIXEDFILEINFO: dwFileVersionMS/LS are fields 2 and 3 after signature/version.
        words = ctypes.cast(value, ctypes.POINTER(wintypes.DWORD * 13)).contents
        major, minor = words[2] >> 16, words[2] & 0xFFFF
        patch, build = words[3] >> 16, words[3] & 0xFFFF
        return f"{major}.{minor}.{patch}.{build}"
    except (AttributeError, OSError, ValueError):
        return _infer_version_from_path(executable)


def _build_digest(executable: Path) -> str:
    digest = hashlib.sha256()
    with executable.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _bounded_smoke(check: SmokeCheck, executable: Path, timeout: float) -> tuple[str, object]:
    results: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def invoke() -> None:
        try:
            results.put_nowait(("result", check(executable)))
        except BaseException as exc:  # preserve a stable health result for plugin failures
            results.put_nowait(("error", exc))

    thread = threading.Thread(target=invoke, name="odafc-health-smoke", daemon=True)
    thread.start()
    try:
        return results.get(timeout=max(0.001, timeout))
    except queue.Empty:
        return "timeout", timeout


@contextmanager
def oda_execution_environment(executable: Path) -> Iterator[None]:
    section = "odafc-addon"
    option = "win_exec_path" if platform.system() == "Windows" else "unix_exec_path"
    original_option = ezdxf.options.get(section, option)
    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(executable.parent) + os.pathsep + original_path
    ezdxf.options.set(section, option, str(executable))
    try:
        yield
    finally:
        ezdxf.options.set(section, option, original_option)
        os.environ["PATH"] = original_path


def _oda_conversion_smoke(executable: Path) -> bool:
    """Run an explicit DXF-to-DXF conversion and validate the readback.

    This check is opt-in through ``health_check(smoke=True)`` because it starts
    the external converter. The caller wraps it in the bounded smoke runner.
    """

    with tempfile.TemporaryDirectory(prefix="xjcheck_odafc_health_") as temp_dir:
        root = Path(temp_dir)
        source = root / "health_input.dxf"
        target = root / "health_output.dxf"
        document = ezdxf.new("R2018")
        document.modelspace().add_line((0, 0), (10, 0))
        document.saveas(source)
        with oda_execution_environment(executable):
            odafc.convert(
                source,
                target,
                version="R2018",
                audit=True,
                replace=True,
            )
        readback = ezdxf.readfile(target)
        return len(readback.modelspace()) == 1


class OdaFileConverterReader:
    backend_name = "odafc"

    def __init__(
        self,
        config: Mapping[str, object],
        *,
        version_reader: VersionReader = _windows_file_version,
        smoke_check: SmokeCheck | None = _oda_conversion_smoke,
    ) -> None:
        self._config = config
        self._probe = discover_oda_file_converter(config)
        self._version_reader = version_reader
        self._smoke_check = smoke_check

    def probe(self) -> ReaderProbe:
        return self._probe

    def health_check(
        self,
        *,
        smoke: bool = False,
        smoke_timeout_seconds: float = 10.0,
    ) -> ReaderHealth:
        probe = self.probe()
        executable = probe.executable_path
        if not probe.available or executable is None or not executable.is_file():
            return ReaderHealth(
                status=ReaderHealthStatus.UNAVAILABLE,
                backend=self.backend_name,
                checks={"executable_exists": False, "executable_readable": False},
                error_code="odafc_not_found",
                detail=probe.detail or "ODA File Converter executable not found.",
            )
        readable = os.access(executable, os.R_OK)
        if not readable:
            return ReaderHealth(
                status=ReaderHealthStatus.UNAVAILABLE,
                backend=self.backend_name,
                checks={"executable_exists": True, "executable_readable": False},
                error_code="odafc_not_readable",
                detail="ODA File Converter executable is not readable.",
            )

        try:
            version = self._version_reader(executable)
            build = _build_digest(executable)
        except (OSError, ValueError) as exc:
            return ReaderHealth(
                status=ReaderHealthStatus.DEGRADED,
                backend=self.backend_name,
                checks={"executable_exists": True, "executable_readable": True, "metadata": False},
                error_code="odafc_metadata_failed",
                detail=str(exc),
            )

        checks = {"executable_exists": True, "executable_readable": True, "metadata": True}
        if not smoke:
            return ReaderHealth(
                status=ReaderHealthStatus.READY,
                backend=self.backend_name,
                version=version,
                build=build,
                checks=checks,
            )
        if self._smoke_check is None:
            return ReaderHealth(
                status=ReaderHealthStatus.DEGRADED,
                backend=self.backend_name,
                version=version,
                build=build,
                checks={**checks, "smoke": False},
                error_code="odafc_smoke_not_configured",
                detail="Explicit conversion smoke check was requested but is not configured.",
            )

        outcome, value = _bounded_smoke(self._smoke_check, executable, smoke_timeout_seconds)
        if outcome == "result" and value is True:
            return ReaderHealth(
                status=ReaderHealthStatus.READY,
                backend=self.backend_name,
                version=version,
                build=build,
                checks={**checks, "smoke": True},
            )
        if outcome == "timeout":
            code, detail = "odafc_smoke_timeout", f"ODA conversion smoke timed out after {value:g}s."
        elif outcome == "error":
            code, detail = "odafc_smoke_error", str(value)
        else:
            code, detail = "odafc_smoke_failed", "ODA conversion smoke check failed."
        return ReaderHealth(
            status=ReaderHealthStatus.DEGRADED,
            backend=self.backend_name,
            version=version,
            build=build,
            checks={**checks, "smoke": False},
            error_code=code,
            detail=detail,
        )

    def read(self, path: Path, options: ReaderOptions) -> CadDocument:
        probe = self.probe()
        if not probe.available or probe.executable_path is None:
            raise ReaderError(
                "backend_unavailable",
                probe.detail or "ODA File Converter executable not found.",
                backend_name=self.backend_name,
            )
        if options.output_path is None:
            raise ReaderError(
                "output_path_required",
                "ODA conversion requires ReaderOptions.output_path.",
                backend_name=self.backend_name,
            )

        with oda_execution_environment(probe.executable_path):
            odafc.convert(
                path,
                options.output_path,
                version=options.target_version,
                audit=options.audit,
                replace=options.replace,
            )
        ezdxf.readfile(options.output_path)
        return CadDocument(
            source_path=path,
            document_path=options.output_path,
            backend_name=self.backend_name,
            backend_version=probe.backend_version,
            metadata={"discovery_source": probe.discovery_source},
        )
