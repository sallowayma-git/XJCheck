from __future__ import annotations

import math
import os
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from shutil import copy2
from threading import Lock
from typing import Callable

from ezdxf.addons import odafc

from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.readers.base import ReaderError, ReaderOptions
from dwg_audit.readers.ezdxf_reader import EzdxfReader
from dwg_audit.readers.oda_reader import OdaFileConverterReader
from dwg_audit.readers.oda_reader import oda_execution_environment
from dwg_audit.readers.provenance import (
    ReaderRun,
    build_cache_identity,
    capabilities_dict,
    executable_build_id,
    infer_backend_version,
    normalized_reader_options,
)
from dwg_audit.readers.registry import ReaderRegistry


@dataclass(frozen=True)
class ResourceSnapshot:
    cpu_percent: float | None
    memory_percent: float | None


class CpuUsageSampler:
    def __init__(self, reader: Callable[[], tuple[int, int] | None] | None = None) -> None:
        self._reader = reader or _read_system_cpu_times
        self._previous: tuple[int, int] | None = None

    def sample(self) -> float | None:
        current = self._reader()
        if current is None:
            return _normalized_load_average_percent()
        previous = self._previous
        self._previous = current
        if previous is None:
            return None
        return _cpu_percent_from_times(previous, current)


class SystemResourceSampler:
    def __init__(self, sample_interval_seconds: float) -> None:
        self._sample_interval_seconds = min(60.0, max(0.05, sample_interval_seconds))
        self._last_sample_at: float | None = None
        self._cpu = CpuUsageSampler()

    @property
    def sample_interval_seconds(self) -> float:
        return self._sample_interval_seconds

    def sample_if_due(self, *, force: bool = False) -> ResourceSnapshot | None:
        now = time.monotonic()
        if (
            not force
            and self._last_sample_at is not None
            and now - self._last_sample_at < self._sample_interval_seconds
        ):
            return None
        self._last_sample_at = now
        total_memory, available_memory = _physical_memory_bytes()
        return ResourceSnapshot(
            cpu_percent=self._cpu.sample(),
            memory_percent=_memory_load_percent(total_memory, available_memory),
        )


class AdaptiveResourceGate:
    def __init__(self, ceiling: int, config: dict) -> None:
        gate_config = _resource_gate_config(config)
        self.enabled = bool(gate_config.get("enabled", True))
        self.ceiling = max(1, ceiling)
        self.target_slots = self.ceiling if not self.enabled else min(self.ceiling, 2)
        self.cpu_high = _config_float(gate_config, "cpu_high_percent", 80.0)
        self.cpu_low = min(
            self.cpu_high,
            _config_float(gate_config, "cpu_low_percent", 65.0),
        )
        self.memory_high = _config_float(gate_config, "memory_high_percent", 80.0)
        self.memory_low = min(
            self.memory_high,
            _config_float(gate_config, "memory_low_percent", 70.0),
        )
        self.pressure_samples = _config_int(gate_config, "pressure_samples", 2, minimum=1)
        self.recovery_samples = _config_int(gate_config, "recovery_samples", 4, minimum=1)
        self._pressure_count = 0
        self._healthy_count = 0

    def observe(
        self,
        snapshot: ResourceSnapshot | None,
        *,
        startup: bool = False,
    ) -> tuple[int, int] | None:
        if not self.enabled or snapshot is None:
            return None
        metrics = [
            (snapshot.cpu_percent, self.cpu_low, self.cpu_high),
            (snapshot.memory_percent, self.memory_low, self.memory_high),
        ]
        known = [(value, low, high) for value, low, high in metrics if value is not None]
        if not known:
            return None

        under_pressure = any(value >= high for value, _low, high in known)
        healthy = all(value <= low for value, low, _high in known)
        if under_pressure:
            self._pressure_count += 1
            self._healthy_count = 0
        elif healthy:
            self._healthy_count += 1
            self._pressure_count = 0
        else:
            self._pressure_count = 0
            self._healthy_count = 0

        previous = self.target_slots
        if startup and under_pressure and self.target_slots > 1:
            self.target_slots = 1
            self._pressure_count = 0
        elif self._pressure_count >= self.pressure_samples and self.target_slots > 1:
            self.target_slots -= 1
            self._pressure_count = 0
        elif self._healthy_count >= self.recovery_samples and self.target_slots < self.ceiling:
            self.target_slots += 1
            self._healthy_count = 0
        if previous == self.target_slots:
            return None
        return previous, self.target_slots


def _config_float(config: dict, key: str, default: float) -> float:
    try:
        value = float(config.get(key, default))
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _resource_gate_config(config: dict) -> dict:
    if not isinstance(config, dict):
        return {}
    ingest = config.get("ingest", {})
    if not isinstance(ingest, dict):
        return {}
    gate_config = ingest.get("resource_gate", {})
    return gate_config if isinstance(gate_config, dict) else {}


def _config_int(config: dict, key: str, default: int, *, minimum: int) -> int:
    try:
        value = int(config.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _read_system_cpu_times() -> tuple[int, int] | None:
    if os.name == "nt":
        try:
            import ctypes

            class FileTime(ctypes.Structure):
                _fields_ = [
                    ("dwLowDateTime", ctypes.c_ulong),
                    ("dwHighDateTime", ctypes.c_ulong),
                ]

            idle = FileTime()
            kernel = FileTime()
            user = FileTime()
            if not ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
            ):
                return None

            def value(item: FileTime) -> int:
                return (int(item.dwHighDateTime) << 32) | int(item.dwLowDateTime)

            return value(idle), value(kernel) + value(user)
        except (AttributeError, OSError, ValueError):
            return None

    try:
        fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()
        if not fields or fields[0] != "cpu":
            return None
        values = [int(value) for value in fields[1:9]]
        if len(values) < 4:
            return None
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return idle, sum(values)
    except (IndexError, OSError, ValueError):
        return None


def _normalized_load_average_percent() -> float | None:
    try:
        load = os.getloadavg()[0]
    except (AttributeError, OSError):
        return None
    return max(0.0, min(100.0, load / max(1, os.cpu_count() or 1) * 100.0))


def _cpu_percent_from_times(
    previous: tuple[int, int],
    current: tuple[int, int],
) -> float | None:
    idle_delta = current[0] - previous[0]
    total_delta = current[1] - previous[1]
    if total_delta <= 0 or idle_delta < 0:
        return None
    busy_delta = max(0, total_delta - idle_delta)
    return max(0.0, min(100.0, busy_delta / total_delta * 100.0))


def _memory_load_percent(total_bytes: int | None, available_bytes: int | None) -> float | None:
    if total_bytes is None or available_bytes is None or total_bytes <= 0:
        return None
    used_bytes = max(0, total_bytes - max(0, available_bytes))
    return max(0.0, min(100.0, used_bytes / total_bytes * 100.0))


def _detect_odafc_exe(config: dict) -> Path | None:
    reader = ReaderRegistry.from_config(config).get("odafc")
    return reader.probe().executable_path


def _physical_memory_bytes() -> tuple[int | None, int | None]:
    if os.name == "nt":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys), int(status.ullAvailPhys)
        except (AttributeError, OSError, ValueError):
            return None, None
        return None, None

    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        total = int(os.sysconf("SC_PHYS_PAGES")) * page_size
        available = int(os.sysconf("SC_AVPHYS_PAGES")) * page_size
        return total, available
    except (AttributeError, OSError, ValueError):
        return None, None


def _available_memory_bytes() -> int | None:
    return _physical_memory_bytes()[1]


def _resolve_convert_workers(config: dict, *, file_count: int) -> int:
    raw = config.get("ingest", {}).get("convert_workers", 0)
    try:
        configured = int(raw or 0)
    except (TypeError, ValueError):
        configured = 0
    if configured <= 0:
        available_memory = _available_memory_bytes()
        low_memory = available_memory is not None and available_memory < 4 * 1024**3
        configured = 1 if low_memory else min(2, max(1, os.cpu_count() or 1))
    return max(1, min(configured, max(1, file_count)))


def _run_bounded_conversions(
    source_files: list[SourceFileRecord],
    convert_one: Callable[[SourceFileRecord], None],
    *,
    workers: int,
    resource_gate: AdaptiveResourceGate,
    resource_sampler: SystemResourceSampler,
    logger,
) -> None:
    if not source_files:
        return
    if workers == 1 or len(source_files) <= 1:
        for source in source_files:
            convert_one(source)
        return

    def observe_resources(*, force: bool = False, startup: bool = False) -> None:
        change = resource_gate.observe(
            resource_sampler.sample_if_due(force=force),
            startup=startup,
        )
        if change is not None:
            previous, current = change
            logger.info("Conversion resource gate adjusted slots %s -> %s", previous, current)

    observe_resources(force=True, startup=True)
    inflight: dict[Future[None], int] = {}
    next_index = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        while next_index < len(source_files) or inflight:
            while next_index < len(source_files) and len(inflight) < resource_gate.target_slots:
                future = executor.submit(convert_one, source_files[next_index])
                inflight[future] = next_index
                next_index += 1

            if not inflight:
                # A gate must always retain at least one slot, but keep this guard
                # to avoid a scheduler spin if a custom policy is misconfigured.
                resource_gate.target_slots = 1
                continue

            done, _pending = wait(
                tuple(inflight),
                timeout=resource_sampler.sample_interval_seconds,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                observe_resources()
                continue
            for future in done:
                inflight.pop(future, None)
                future.result()
            observe_resources()


def convert_source_files(
    source_files: list[SourceFileRecord],
    output_dir: Path,
    config: dict,
    logger,
    *,
    event_sink=None,
) -> list[ReaderRun]:
    odafc_exe = _detect_odafc_exe(config)
    reader = ReaderRegistry.from_config(config).get("odafc")
    probe = reader.probe()
    if odafc_exe is not None and probe.executable_path != odafc_exe:
        reader = OdaFileConverterReader({"ingest": {"odafc_path": str(odafc_exe)}})
        probe = reader.probe()
    health = reader.health_check()
    dxf_dir = output_dir / "cache" / "converted_dxf"
    stage_dir = output_dir / "cache" / "odafc_stage"
    dxf_dir.mkdir(parents=True, exist_ok=True)
    stage_dir.mkdir(parents=True, exist_ok=True)

    convert_version = str(config.get("ingest", {}).get("convert_version", "R2018"))
    audit_before_load = bool(config.get("ingest", {}).get("audit_before_load", True))
    options = normalized_reader_options(
        target_version=convert_version,
        audit=audit_before_load,
    )
    backend_version = health.version or probe.backend_version or infer_backend_version(odafc_exe)
    backend_build_id = health.build or executable_build_id(odafc_exe)
    runs: dict[str, ReaderRun] = {}
    runs_lock = Lock()
    dxf_reader = EzdxfReader()
    dxf_options = ReaderOptions()

    def record_run(
        source: SourceFileRecord,
        *,
        error_code: str | None = None,
    ) -> None:
        identity = build_cache_identity(
            source_sha256=source.sha256,
            probe=probe,
            backend_version=backend_version,
            backend_build_id=backend_build_id,
            options=options,
        )
        run = ReaderRun(
            file_id=source.file_id,
            backend_name=probe.backend_name,
            backend_version=backend_version,
            backend_build_id=backend_build_id,
            capabilities=capabilities_dict(probe.capabilities),
            discovery_source=probe.discovery_source,
            options=options,
            status=source.conversion_status,
            cache_hit=source.conversion_status == "cached",
            # Phase 112 records the new identity without changing legacy cache lookup.
            cache_identity_enforced=False,
            document_path=source.dxf_path,
            error_code=error_code,
            detail=source.conversion_detail,
            health_status=health.status.value,
            health_error_code=health.error_code,
            health_checks=dict(health.checks),
            warnings=list(source.warnings),
            cache_identity=identity.payload() if identity is not None else None,
            cache_key=identity.cache_key() if identity is not None else None,
        )
        with runs_lock:
            runs[source.file_id] = run

    if odafc_exe is None:
        for source in source_files:
            source.conversion_status = "missing_converter"
            source.conversion_detail = "ODA File Converter executable not found."
            source.conversion_version = convert_version
            source.conversion_audit = audit_before_load
            if event_sink is not None:
                event_sink.emit(
                    "warning",
                    stage="convert",
                    file_id=source.file_id,
                    filename=source.filename,
                    message=source.conversion_detail,
                )
                event_sink.emit(
                    "page_finished",
                    stage="convert",
                    file_id=source.file_id,
                    filename=source.filename,
                    status=source.conversion_status,
                )
            record_run(source, error_code="READER_UNAVAILABLE")
        return [runs[source.file_id] for source in source_files if source.file_id in runs]

    def convert_one(source: SourceFileRecord) -> None:
        if event_sink is not None:
            event_sink.emit(
                "page_started",
                stage="convert",
                file_id=source.file_id,
                filename=source.filename,
                sheet_order=source.sheet_order,
            )
        source.conversion_version = convert_version
        source.conversion_audit = audit_before_load
        if source.skip_reason:
            source.conversion_status = "skipped"
            source.conversion_detail = source.skip_reason
            if event_sink is not None:
                event_sink.emit(
                    "page_finished",
                    stage="convert",
                    file_id=source.file_id,
                    filename=source.filename,
                    status=source.conversion_status,
                )
            record_run(source)
            return
        if not source.valid_dwg_header:
            source.conversion_status = "failed_invalid_header"
            source.conversion_detail = "Non-standard DWG header."
            if event_sink is not None:
                event_sink.emit(
                    "warning",
                    stage="convert",
                    file_id=source.file_id,
                    filename=source.filename,
                    message=source.conversion_detail,
                )
                event_sink.emit(
                    "page_finished",
                    stage="convert",
                    file_id=source.file_id,
                    filename=source.filename,
                    status=source.conversion_status,
                )
            record_run(source, error_code="INVALID_SOURCE_HEADER")
            return

        sha_prefix = source.sha256[:8]
        staged = stage_dir / f"{source.file_id}_{sha_prefix}.dwg"
        target = dxf_dir / f"{source.file_id}_{sha_prefix}.dxf"

        if target.exists():
            try:
                dxf_reader.read(target, dxf_options)
                source.conversion_status = "cached"
                source.dxf_path = str(target.resolve())
                if event_sink is not None:
                    event_sink.emit(
                        "page_finished",
                        stage="convert",
                        file_id=source.file_id,
                        filename=source.filename,
                        status=source.conversion_status,
                        dxf_path=source.dxf_path,
                    )
                record_run(source)
                return
            except ReaderError:
                target.unlink()

        copy2(source.path, staged)
        started = time.perf_counter()
        try:
            odafc.convert(
                staged,
                target,
                version=convert_version,
                audit=audit_before_load,
                replace=True,
            )
            dxf_reader.read(target, dxf_options)
            source.conversion_status = "converted"
            source.dxf_path = str(target.resolve())
            source.conversion_duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info("Converted %s -> %s", source.filename, target.name)
            error_code = None
        except Exception as exc:  # pragma: no cover - exercised in integration runs
            source.conversion_status = "failed"
            source.conversion_duration_ms = int((time.perf_counter() - started) * 1000)
            source.conversion_detail = str(exc)
            if target.exists():
                try:
                    message = target.read_text(encoding="utf-8", errors="replace").strip()
                    if message:
                        source.conversion_detail = message
                except OSError:
                    pass
            logger.warning("Failed to convert %s: %s", source.filename, source.conversion_detail)
            if event_sink is not None:
                event_sink.emit(
                    "warning",
                    stage="convert",
                    file_id=source.file_id,
                    filename=source.filename,
                    message=source.conversion_detail,
                )
            error_code = (
                "DXF_VALIDATION_FAILED"
                if isinstance(exc, ReaderError)
                else "CONVERSION_FAILED"
            )
        if event_sink is not None:
            event_sink.emit(
                "page_finished",
                stage="convert",
                file_id=source.file_id,
                filename=source.filename,
                status=source.conversion_status,
                dxf_path=source.dxf_path,
            )
        record_run(source, error_code=error_code)

    workers = _resolve_convert_workers(config, file_count=len(source_files))
    resource_gate = AdaptiveResourceGate(workers, config)
    resource_sampler = SystemResourceSampler(
        _config_float(
            _resource_gate_config(config),
            "sample_interval_seconds",
            0.75,
        )
    )
    with oda_execution_environment(odafc_exe):
        if workers > 1 and len(source_files) > 1:
            logger.info("Converting %s DWG files with %s workers", len(source_files), workers)
        _run_bounded_conversions(
            source_files,
            convert_one,
            workers=workers,
            resource_gate=resource_gate,
            resource_sampler=resource_sampler,
            logger=logger,
        )

    with runs_lock:
        return [runs[source.file_id] for source in source_files if source.file_id in runs]
