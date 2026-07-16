from __future__ import annotations

from pathlib import Path

import ezdxf

from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.ingest import dwg_converter


class DummyLogger:
    def info(self, *_args, **_kwargs) -> None:
        return None

    def warning(self, *_args, **_kwargs) -> None:
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
