from __future__ import annotations

import json
import os
from pathlib import Path

import ezdxf
import pytest

from dwg_audit.readers.base import (
    ReaderCapabilities,
    ReaderError,
    ReaderHealthStatus,
    ReaderOptions,
    ReaderProbe,
)
from dwg_audit.readers.ezdxf_reader import EzdxfReader
from dwg_audit.readers.oda_reader import (
    discover_oda_file_converter,
    oda_execution_environment,
)
from dwg_audit.readers.registry import ReaderRegistry
from dwg_audit.readers.provenance import (
    ReaderCacheIdentity,
    ReaderRun,
    ReaderRunManifest,
    build_cache_identity,
    infer_backend_version,
    normalized_reader_options,
)


def _config(path: Path | str = "") -> dict[str, object]:
    return {"ingest": {"dwg_reader": "odafc", "odafc_path": str(path)}}


def test_oda_probe_prefers_explicit_config_path(tmp_path: Path) -> None:
    executable = tmp_path / "custom-oda.AppImage"
    executable.touch()

    probe = discover_oda_file_converter(
        _config(executable),
        environ={},
        which=lambda _: None,
        system="Linux",
    )

    assert probe.available is True
    assert probe.executable_path == executable
    assert probe.discovery_source == "config"
    assert probe.capabilities.native_dwg is True


def test_oda_probe_falls_back_to_environment_for_invalid_config(tmp_path: Path) -> None:
    executable = tmp_path / "ODAFileConverter.AppImage"
    executable.touch()

    probe = discover_oda_file_converter(
        _config(tmp_path / "missing"),
        environ={"ODAFC_PATH": str(executable)},
        which=lambda _: None,
        system="Linux",
    )

    assert probe.executable_path == executable
    assert probe.discovery_source == "env:ODAFC_PATH"


def test_oda_probe_uses_path_on_unix(tmp_path: Path) -> None:
    executable = tmp_path / "ODAFileConverter"
    executable.touch()

    probe = discover_oda_file_converter(
        _config(),
        environ={},
        which=lambda command: str(executable) if command == "ODAFileConverter" else None,
        system="Linux",
    )

    assert probe.executable_path == executable
    assert probe.discovery_source == "path:ODAFileConverter"


def test_oda_probe_reports_unavailable_without_silently_selecting_backend() -> None:
    probe = discover_oda_file_converter(
        _config(),
        environ={},
        which=lambda _: None,
        system="Linux",
    )

    assert probe.available is False
    assert probe.executable_path is None
    assert probe.detail == "ODA File Converter executable not found."


def test_oda_probe_prefers_bundled_resource_before_path_or_windows_install(
    tmp_path: Path,
) -> None:
    resource_root = tmp_path / "resources"
    bundled = resource_root / "oda" / "ODAFileConverter.exe"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"bundled-oda")
    system_install = tmp_path / "Program Files" / "ODA" / "ODAFileConverter 27.1.0" / "ODAFileConverter.exe"
    system_install.parent.mkdir(parents=True)
    system_install.write_bytes(b"system-oda")
    path_candidate = tmp_path / "path-oda" / "ODAFileConverter.exe"
    path_candidate.parent.mkdir(parents=True)
    path_candidate.write_bytes(b"path-oda")

    probe = discover_oda_file_converter(
        _config(),
        environ={
            "DWG_AUDIT_RESOURCE_DIR": str(resource_root),
            "ProgramFiles": str(tmp_path / "Program Files"),
        },
        which=lambda command: str(path_candidate) if command == "ODAFileConverter.exe" else None,
        system="Windows",
    )

    assert probe.available is True
    assert probe.executable_path == bundled.resolve()
    assert probe.discovery_source == "bundled-resource"


def test_oda_probe_uses_sidecar_sibling_oda_layout(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar" / "dwg-audit-sidecar.exe"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_bytes(b"sidecar")
    bundled = tmp_path / "oda" / "ODAFileConverter.exe"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"bundled-oda")

    probe = discover_oda_file_converter(
        _config(),
        environ={"DWG_AUDIT_SIDECAR_EXE": str(sidecar)},
        which=lambda _: None,
        system="Linux",
    )

    assert probe.available is True
    assert probe.executable_path == bundled.resolve()
    assert probe.discovery_source == "bundled-resource"


def test_oda_execution_environment_sets_and_restores_explicit_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "custom-oda.AppImage"
    executable.touch()
    option = "win_exec_path" if os.name == "nt" else "unix_exec_path"
    original_option = ezdxf.options.get("odafc-addon", option)
    original_path = os.environ.get("PATH", "")

    with oda_execution_environment(executable):
        assert ezdxf.options.get("odafc-addon", option) == str(executable)
        assert os.environ["PATH"].split(os.pathsep, maxsplit=1)[0] == str(tmp_path)

    assert ezdxf.options.get("odafc-addon", option) == original_option
    assert os.environ.get("PATH", "") == original_path


def test_reader_registry_reports_unknown_backend() -> None:
    registry = ReaderRegistry.from_config(_config())

    with pytest.raises(ReaderError) as exc_info:
        registry.get("realdwg")

    assert exc_info.value.code == "unknown_backend"
    assert exc_info.value.backend_name == "realdwg"


def test_reader_registry_registers_ezdxf_without_changing_default() -> None:
    registry = ReaderRegistry.from_config(_config())

    assert registry.configured(_config()).backend_name == "odafc"
    assert registry.get("ezdxf").backend_name == "ezdxf"
    assert set(registry.probes()) == {"odafc", "ezdxf"}


def test_ezdxf_health_is_structured_and_ready() -> None:
    health = EzdxfReader().health_check()

    assert health.status is ReaderHealthStatus.READY
    assert health.backend == "ezdxf"
    assert health.version == ezdxf.__version__
    assert health.to_dict() == {
        "status": "READY",
        "backend": "ezdxf",
        "version": ezdxf.__version__,
        "build": None,
        "checks": {"package_importable": True, "dxf_read_support": True},
        "error_code": None,
        "detail": "ezdxf Python package is importable.",
    }


def test_ezdxf_reader_returns_native_document(tmp_path: Path) -> None:
    path = tmp_path / "minimal.dxf"
    document = ezdxf.new("R2018")
    document.modelspace().add_line((0, 0), (1, 1))
    document.saveas(path)

    result = EzdxfReader().read(path, ReaderOptions())

    assert result.source_path == path
    assert result.document_path == path
    assert result.backend_name == "ezdxf"
    assert result.native_document is not None
    assert len(result.native_document.modelspace()) == 1


@pytest.mark.parametrize(
    ("filename", "expected_code"),
    [("missing.dxf", "source_not_found"), ("drawing.dwg", "unsupported_format")],
)
def test_ezdxf_reader_uses_stable_validation_error_codes(
    tmp_path: Path, filename: str, expected_code: str
) -> None:
    with pytest.raises(ReaderError) as exc_info:
        EzdxfReader().read(tmp_path / filename, ReaderOptions())

    assert exc_info.value.code == expected_code
    assert exc_info.value.backend_name == "ezdxf"


def test_ezdxf_reader_wraps_invalid_document(tmp_path: Path) -> None:
    path = tmp_path / "broken.dxf"
    path.write_text("not a dxf", encoding="utf-8")

    with pytest.raises(ReaderError) as exc_info:
        EzdxfReader().read(path, ReaderOptions())

    assert exc_info.value.code == "invalid_dxf"


def _probe(
    *,
    discovery_source: str = "config",
    capabilities: ReaderCapabilities | None = None,
) -> ReaderProbe:
    return ReaderProbe(
        backend_name="odafc",
        available=True,
        capabilities=capabilities or ReaderCapabilities(native_dwg=True),
        discovery_source=discovery_source,
    )


def test_reader_cache_identity_is_canonical_for_option_key_order() -> None:
    first = ReaderCacheIdentity(
        source_sha256="abc123",
        reader_backend="odafc",
        reader_version="26.4",
        reader_build_id=None,
        reader_options={"target_version": "R2018", "audit": True},
    )
    second = ReaderCacheIdentity(
        source_sha256="abc123",
        reader_backend="odafc",
        reader_version="26.4",
        reader_build_id=None,
        reader_options={"audit": True, "target_version": "R2018"},
    )

    assert first.canonical_json() == second.canonical_json()
    assert first.cache_key() == second.cache_key()
    assert json.loads(first.canonical_json()) == first.payload()
    assert set(first.payload()) == {
        "source_sha256",
        "reader_backend",
        "reader_version",
        "reader_build_id",
        "reader_options",
        "reader_contract_version",
        "schema_version",
    }
    assert {"discovery_source", "status", "document_path", "duration_ms"}.isdisjoint(
        first.payload()
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("source_sha256", "different-source"),
        ("reader_backend", "realdwg"),
        ("reader_version", "27.0"),
        ("reader_build_id", "sha256:different"),
        ("reader_options", {"audit": False}),
        ("reader_contract_version", "2.0.0"),
        ("schema_version", "reader-cache/v2"),
    ],
)
def test_reader_cache_identity_key_is_sensitive_to_contract_fields(
    field: str,
    replacement: object,
) -> None:
    values = {
        "source_sha256": "abc123",
        "reader_backend": "odafc",
        "reader_version": "26.4",
        "reader_build_id": "sha256:build",
        "reader_options": {"audit": True},
        "reader_contract_version": "1.0.0",
        "schema_version": "reader-cache/v1",
    }
    original = ReaderCacheIdentity(**values)
    values[field] = replacement

    assert ReaderCacheIdentity(**values).cache_key() != original.cache_key()


def test_reader_cache_identity_ignores_probe_discovery_and_capabilities() -> None:
    options = normalized_reader_options(target_version="R2018", audit=True)
    first = build_cache_identity(
        source_sha256="abc123",
        probe=_probe(discovery_source="config"),
        backend_version="26.4",
        backend_build_id="sha256:build",
        options=options,
    )
    second = build_cache_identity(
        source_sha256="abc123",
        probe=_probe(
            discovery_source="path:ODAFileConverter",
            capabilities=ReaderCapabilities(native_dwg=True, preview=True),
        ),
        backend_version="26.4",
        backend_build_id="sha256:build",
        options=options,
    )

    assert first is not None
    assert second is not None
    assert first.cache_key() == second.cache_key()


def test_reader_cache_identity_requires_version_or_build_id() -> None:
    with pytest.raises(ValueError, match="version or build ID"):
        ReaderCacheIdentity(
            source_sha256="abc123",
            reader_backend="odafc",
            reader_version=None,
            reader_build_id=None,
            reader_options={},
        )

    assert build_cache_identity(
        source_sha256="abc123",
        probe=_probe(),
        backend_version=None,
        backend_build_id=None,
        options={},
    ) is None


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/opt/ODAFileConverter_26.4.0/ODAFileConverter", "26.4.0"),
        (r"C:\\Program Files\\ODAFileConverter 25.12\\ODAFileConverter.exe", "25.12"),
        ("/opt/ODAFileConverter.AppImage", None),
        (None, None),
    ],
)
def test_infer_backend_version_from_executable_path(
    path: str | None,
    expected: str | None,
) -> None:
    assert infer_backend_version(Path(path) if path is not None else None) == expected


def test_reader_run_manifest_serializes_nested_runs() -> None:
    run = ReaderRun(
        file_id="F001",
        backend_name="odafc",
        backend_version="26.4",
        backend_build_id="sha256:build",
        capabilities={"native_dwg": True},
        discovery_source="config",
        options={"audit": True},
        status="converted",
        cache_hit=False,
        cache_identity_enforced=False,
        document_path="cache/F001.dxf",
        error_code=None,
        detail=None,
        warnings=["fixture warning"],
        cache_identity={"source_sha256": "abc123"},
        cache_key="cache-key",
    )

    payload = ReaderRunManifest(project_id="demo", runs=[run]).to_dict()

    assert payload["schema_version"] == "reader-run-manifest/v1"
    assert payload["project_id"] == "demo"
    assert payload["runs"] == [run.to_dict()]
    assert payload["runs"][0]["schema_version"] == "reader-run/v1"
    assert payload["runs"][0]["warnings"] == ["fixture warning"]
