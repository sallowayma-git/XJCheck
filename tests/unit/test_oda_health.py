from __future__ import annotations

import time
from pathlib import Path

from dwg_audit.readers.base import ReaderHealthStatus, ReaderProbe
from dwg_audit.readers.oda_reader import ODA_CAPABILITIES, OdaFileConverterReader


def _reader(tmp_path: Path, **kwargs: object) -> OdaFileConverterReader:
    executable = tmp_path / "ODAFileConverter 27.1.0.exe"
    executable.write_bytes(b"test ODA build")
    return OdaFileConverterReader(
        {"ingest": {"odafc_path": str(executable)}},
        **kwargs,  # type: ignore[arg-type]
    )


def test_health_reports_missing_executable(monkeypatch) -> None:
    missing = ReaderProbe(
        backend_name="odafc",
        available=False,
        capabilities=ODA_CAPABILITIES,
        detail="not installed",
    )
    monkeypatch.setattr(
        "dwg_audit.readers.oda_reader.discover_oda_file_converter",
        lambda config: missing,
    )

    health = OdaFileConverterReader({}).health_check()

    assert health.status is ReaderHealthStatus.UNAVAILABLE
    assert health.error_code == "odafc_not_found"
    assert health.checks["executable_exists"] is False


def test_health_reads_version_and_build_digest(tmp_path: Path) -> None:
    health = _reader(tmp_path, version_reader=lambda path: "27.1.2.3").health_check()

    assert health.status is ReaderHealthStatus.READY
    assert health.version == "27.1.2.3"
    assert health.build is not None and health.build.startswith("sha256:")
    assert health.checks == {
        "executable_exists": True,
        "executable_readable": True,
        "metadata": True,
    }


def test_health_infers_version_without_launching_converter(tmp_path: Path) -> None:
    health = _reader(tmp_path).health_check()

    assert health.version == "27.1.0"


def test_explicit_smoke_success(tmp_path: Path) -> None:
    health = _reader(tmp_path, smoke_check=lambda executable: executable.is_file()).health_check(
        smoke=True,
        smoke_timeout_seconds=0.1,
    )

    assert health.status is ReaderHealthStatus.READY
    assert health.checks["smoke"] is True


def test_explicit_smoke_failure_is_degraded(tmp_path: Path) -> None:
    health = _reader(tmp_path, smoke_check=lambda executable: False).health_check(smoke=True)

    assert health.status is ReaderHealthStatus.DEGRADED
    assert health.error_code == "odafc_smoke_failed"
    assert health.checks["smoke"] is False


def test_explicit_smoke_exception_is_degraded(tmp_path: Path) -> None:
    def fail(executable: Path) -> bool:
        raise RuntimeError("conversion readback failed")

    health = _reader(tmp_path, smoke_check=fail).health_check(smoke=True)

    assert health.status is ReaderHealthStatus.DEGRADED
    assert health.error_code == "odafc_smoke_error"
    assert health.detail == "conversion readback failed"


def test_explicit_smoke_timeout_is_bounded(tmp_path: Path) -> None:
    def hang(executable: Path) -> bool:
        time.sleep(1)
        return True

    started = time.monotonic()
    health = _reader(tmp_path, smoke_check=hang).health_check(
        smoke=True,
        smoke_timeout_seconds=0.01,
    )

    assert time.monotonic() - started < 0.5
    assert health.status is ReaderHealthStatus.DEGRADED
    assert health.error_code == "odafc_smoke_timeout"
