from __future__ import annotations

import os
import time
from pathlib import Path
from shutil import copy2

import ezdxf
from ezdxf.addons import odafc

from dwg_audit.domain.models import SourceFileRecord


def _detect_odafc_exe(config: dict) -> Path | None:
    configured = config.get("ingest", {}).get("odafc_path", "")
    if configured and Path(configured).is_file():
        return Path(configured)

    candidates = [
        Path(r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"),
        Path(r"C:\Program Files\ODA\ODAFileConverter 26.9.0\ODAFileConverter.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def convert_source_files(
    source_files: list[SourceFileRecord],
    output_dir: Path,
    config: dict,
    logger,
) -> None:
    odafc_exe = _detect_odafc_exe(config)
    dxf_dir = output_dir / "cache" / "converted_dxf"
    stage_dir = output_dir / "cache" / "odafc_stage"
    dxf_dir.mkdir(parents=True, exist_ok=True)
    stage_dir.mkdir(parents=True, exist_ok=True)

    convert_version = str(config.get("ingest", {}).get("convert_version", "R2018"))
    audit_before_load = bool(config.get("ingest", {}).get("audit_before_load", True))
    if odafc_exe is None:
        for source in source_files:
            source.conversion_status = "missing_converter"
            source.conversion_detail = "ODA File Converter executable not found."
            source.conversion_version = convert_version
            source.conversion_audit = audit_before_load
        return

    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(odafc_exe.parent) + os.pathsep + original_path
    try:
        for source in source_files:
            source.conversion_version = convert_version
            source.conversion_audit = audit_before_load
            if source.skip_reason:
                source.conversion_status = "skipped"
                source.conversion_detail = source.skip_reason
                continue
            if not source.valid_dwg_header:
                source.conversion_status = "failed_invalid_header"
                source.conversion_detail = "Non-standard DWG header."
                continue

            sha_prefix = source.sha256[:8]
            staged = stage_dir / f"{source.file_id}_{sha_prefix}.dwg"
            target = dxf_dir / f"{source.file_id}_{sha_prefix}.dxf"

            if target.exists():
                try:
                    ezdxf.readfile(target)
                    source.conversion_status = "cached"
                    source.dxf_path = str(target.resolve())
                    continue
                except OSError:
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
                ezdxf.readfile(target)
                source.conversion_status = "converted"
                source.dxf_path = str(target.resolve())
                source.conversion_duration_ms = int((time.perf_counter() - started) * 1000)
                logger.info("Converted %s -> %s", source.filename, target.name)
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
    finally:
        os.environ["PATH"] = original_path
