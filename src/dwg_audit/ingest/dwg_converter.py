from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path
from shutil import copy2
from threading import Lock

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


def _detect_odafc_exe(config: dict) -> Path | None:
    reader = ReaderRegistry.from_config(config).get("odafc")
    return reader.probe().executable_path


def _available_memory_bytes() -> int | None:
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
                return int(status.ullAvailPhys)
        except (AttributeError, OSError, ValueError):
            return None
        return None

    try:
        return int(os.sysconf("SC_AVPHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, ValueError):
        return None


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
    runs: list[ReaderRun] = []
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
            runs.append(run)

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
        return runs

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
    with oda_execution_environment(odafc_exe):
        if workers == 1 or len(source_files) <= 1:
            for source in source_files:
                convert_one(source)
        else:
            logger.info("Converting %s DWG files with %s workers", len(source_files), workers)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(convert_one, source) for source in source_files]
                for future in as_completed(futures):
                    future.result()

    return runs
