from __future__ import annotations

import time
from pathlib import Path
from threading import Lock

import ezdxf

from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.ingest import dwg_converter


class DummyLogger:
    def info(self, *_args, **_kwargs) -> None:
        return None

    def warning(self, *_args, **_kwargs) -> None:
        return None


class NoopResourceSampler:
    sample_interval_seconds = 0.01

    def sample_if_due(self, *, force: bool = False):
        del force
        return None


def _source(
    path: Path,
    *,
    file_id: str = "F0001",
    skip_reason: str | None = None,
    valid_header: bool = True,
) -> SourceFileRecord:
    return SourceFileRecord(
        file_id=file_id,
        path=str(path),
        filename=path.name,
        ext=".dwg",
        sha256="a" * 64,
        size_bytes=path.stat().st_size if path.exists() else 0,
        sheet_order=1,
        detected_page_no="01",
        detected_from="filename",
        sheet_title="Demo",
        sheet_category="二次原理图",
        skip_reason=skip_reason,
        valid_dwg_header=valid_header,
    )


def test_default_convert_workers_are_memory_bounded(monkeypatch) -> None:
    monkeypatch.setattr(dwg_converter, "_available_memory_bytes", lambda: 16 * 1024**3)
    monkeypatch.setattr(dwg_converter.os, "cpu_count", lambda: 16)

    assert dwg_converter._resolve_convert_workers({}, file_count=40) == 2


def test_default_convert_workers_drop_to_one_on_low_memory(monkeypatch) -> None:
    monkeypatch.setattr(dwg_converter, "_available_memory_bytes", lambda: 3 * 1024**3)

    assert dwg_converter._resolve_convert_workers({}, file_count=40) == 1


def test_explicit_convert_workers_override_memory_default(monkeypatch) -> None:
    monkeypatch.setattr(dwg_converter, "_available_memory_bytes", lambda: 3 * 1024**3)

    assert dwg_converter._resolve_convert_workers(
        {"ingest": {"convert_workers": 3}},
        file_count=40,
    ) == 3


def test_cpu_and_memory_percent_helpers_are_bounded() -> None:
    assert dwg_converter._cpu_percent_from_times((100, 1000), (150, 1200)) == 75.0
    assert dwg_converter._cpu_percent_from_times((100, 1000), (90, 1200)) is None
    assert dwg_converter._memory_load_percent(1000, 200) == 80.0
    assert dwg_converter._memory_load_percent(None, 200) is None


def test_cpu_sampler_uses_counter_deltas() -> None:
    samples = iter([(100, 1000), (150, 1200)])
    sampler = dwg_converter.CpuUsageSampler(reader=lambda: next(samples))

    assert sampler.sample() is None
    assert sampler.sample() == 75.0


def test_resource_sampler_rejects_non_finite_or_unbounded_intervals() -> None:
    sampler = dwg_converter.SystemResourceSampler(float("inf"))
    assert sampler.sample_interval_seconds == 60.0
    assert dwg_converter._config_float({"sample": float("inf")}, "sample", 0.75) == 0.75


def test_resource_gate_downshifts_and_recovers_with_hysteresis() -> None:
    gate = dwg_converter.AdaptiveResourceGate(
        3,
        {
            "ingest": {
                "resource_gate": {
                    "pressure_samples": 2,
                    "recovery_samples": 2,
                }
            }
        },
    )
    pressure = dwg_converter.ResourceSnapshot(cpu_percent=85.0, memory_percent=60.0)
    healthy = dwg_converter.ResourceSnapshot(cpu_percent=40.0, memory_percent=50.0)

    assert gate.target_slots == 2
    assert gate.observe(pressure) is None
    assert gate.observe(pressure) == (2, 1)
    assert gate.observe(None) is None
    assert gate.target_slots == 1
    assert gate.observe(healthy) is None
    assert gate.observe(healthy) == (1, 2)
    assert gate.observe(healthy) is None
    assert gate.observe(healthy) == (2, 3)


def test_startup_pressure_never_admits_above_one_slot() -> None:
    gate = dwg_converter.AdaptiveResourceGate(8, {})
    pressure = dwg_converter.ResourceSnapshot(cpu_percent=90.0, memory_percent=85.0)

    assert gate.target_slots == 2
    assert gate.observe(pressure, startup=True) == (2, 1)
    assert gate.target_slots == 1


def test_malformed_resource_gate_config_fails_open() -> None:
    gate = dwg_converter.AdaptiveResourceGate(3, {"ingest": {"resource_gate": None}})
    assert gate.enabled is True
    assert gate.target_slots == 2


def test_bounded_scheduler_never_exceeds_gate_slots() -> None:
    gate = dwg_converter.AdaptiveResourceGate(
        2,
        {"ingest": {"resource_gate": {"enabled": False}}},
    )
    lock = Lock()
    active = 0
    max_active = 0
    completed: list[int] = []

    def convert_one(item: int) -> None:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.01)
        with lock:
            active -= 1
            completed.append(item)

    dwg_converter._run_bounded_conversions(
        list(range(12)),  # type: ignore[arg-type]
        convert_one,  # type: ignore[arg-type]
        workers=4,
        resource_gate=gate,
        resource_sampler=NoopResourceSampler(),  # type: ignore[arg-type]
        logger=DummyLogger(),
    )

    assert max_active == 2
    assert sorted(completed) == list(range(12))


def test_missing_converter_returns_reader_run(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "missing.dwg"
    source_path.write_bytes(b"AC1032")
    source = _source(source_path)
    monkeypatch.setattr(dwg_converter, "_detect_odafc_exe", lambda _config: None)

    runs = dwg_converter.convert_source_files(
        [source], tmp_path / "output", {}, DummyLogger()
    )

    assert source.conversion_status == "missing_converter"
    assert len(runs) == 1
    assert runs[0].status == "missing_converter"
    assert runs[0].error_code == "READER_UNAVAILABLE"
    assert runs[0].cache_identity_enforced is False


def test_skip_and_invalid_header_return_reader_runs(tmp_path: Path) -> None:
    executable = tmp_path / "ODAFileConverter 27.1.0.exe"
    executable.write_bytes(b"fake executable")
    skipped_path = tmp_path / "skipped.dwg"
    skipped_path.write_bytes(b"AC1032")
    invalid_path = tmp_path / "invalid.dwg"
    invalid_path.write_bytes(b"not a dwg")
    skipped = _source(skipped_path, file_id="F0001", skip_reason="duplicate")
    invalid = _source(invalid_path, file_id="F0002", valid_header=False)

    runs = dwg_converter.convert_source_files(
        [skipped, invalid],
        tmp_path / "output",
        {"ingest": {"odafc_path": str(executable)}},
        DummyLogger(),
    )

    assert [run.status for run in runs] == ["skipped", "failed_invalid_header"]
    assert runs[0].error_code is None
    assert runs[1].error_code == "INVALID_SOURCE_HEADER"
    assert all(run.cache_key for run in runs)
    assert all(run.backend_version == "27.1.0" for run in runs)


def test_converted_run_has_shadow_cache_identity_and_legacy_call_compatibility(
    tmp_path: Path, monkeypatch
) -> None:
    executable = tmp_path / "ODAFileConverter 27.1.0.exe"
    executable.write_bytes(b"fake executable")
    source_path = tmp_path / "page.dwg"
    source_path.write_bytes(b"AC1032")
    source = _source(source_path)
    calls: list[tuple[Path, Path, dict[str, object]]] = []

    monkeypatch.setattr(
        dwg_converter, "_detect_odafc_exe", lambda _config: executable
    )

    def fake_convert(staged: Path, target: Path, **kwargs) -> None:
        calls.append((staged, target, kwargs))
        ezdxf.new().saveas(target)

    monkeypatch.setattr(dwg_converter.odafc, "convert", fake_convert)

    runs = dwg_converter.convert_source_files(
        [source], tmp_path / "output", {}, DummyLogger()
    )

    assert source.conversion_status == "converted"
    assert len(calls) == 1
    assert calls[0][2] == {"version": "R2018", "audit": True, "replace": True}
    assert runs[0].status == "converted"
    assert runs[0].cache_key
    assert runs[0].cache_identity is not None
    assert runs[0].cache_identity_enforced is False
    assert runs[0].document_path == source.dxf_path


def test_corrupt_cached_dxf_is_reconverted_through_reader_contract(
    tmp_path: Path, monkeypatch
) -> None:
    executable = tmp_path / "ODAFileConverter 27.1.0.exe"
    executable.write_bytes(b"fake executable")
    source_path = tmp_path / "page.dwg"
    source_path.write_bytes(b"AC1032")
    source = _source(source_path)
    output = tmp_path / "output"
    cached = output / "cache" / "converted_dxf" / "F0001_aaaaaaaa.dxf"
    cached.parent.mkdir(parents=True)
    cached.write_text("not a dxf", encoding="utf-8")
    calls: list[Path] = []
    monkeypatch.setattr(dwg_converter, "_detect_odafc_exe", lambda _config: executable)

    def fake_convert(_staged: Path, target: Path, **_kwargs) -> None:
        calls.append(target)
        ezdxf.new().saveas(target)

    monkeypatch.setattr(dwg_converter.odafc, "convert", fake_convert)

    runs = dwg_converter.convert_source_files([source], output, {}, DummyLogger())

    assert calls == [cached]
    assert source.conversion_status == "converted"
    assert runs[0].cache_hit is False


def test_invalid_fresh_dxf_has_stable_validation_error(
    tmp_path: Path, monkeypatch
) -> None:
    executable = tmp_path / "ODAFileConverter 27.1.0.exe"
    executable.write_bytes(b"fake executable")
    source_path = tmp_path / "page.dwg"
    source_path.write_bytes(b"AC1032")
    source = _source(source_path)
    monkeypatch.setattr(dwg_converter, "_detect_odafc_exe", lambda _config: executable)

    def fake_convert(_staged: Path, target: Path, **_kwargs) -> None:
        target.write_text("not a dxf", encoding="utf-8")

    monkeypatch.setattr(dwg_converter.odafc, "convert", fake_convert)

    runs = dwg_converter.convert_source_files(
        [source], tmp_path / "output", {}, DummyLogger()
    )

    assert source.conversion_status == "failed"
    assert source.dxf_path is None
    assert runs[0].error_code == "DXF_VALIDATION_FAILED"
