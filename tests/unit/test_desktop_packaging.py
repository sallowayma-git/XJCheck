from __future__ import annotations

import io
import json
from pathlib import Path

from dwg_audit.desktop.sidecar_entry import _configure_text_stream_utf8


REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_ROOT = REPO_ROOT / "apps" / "desktop"


def test_tauri_bundle_declares_sidecar_and_oda_resource_directories() -> None:
    config = json.loads((DESKTOP_ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))

    resources = config["bundle"]["resources"]

    assert resources["resources/sidecar/*"] == "sidecar/"
    assert resources["resources/oda/*"] == "oda/"
    # Tauri flattens a recursive glob into its destination. Map the Qt plugin
    # directory explicitly so qwindows.dll remains under oda/platforms/.
    assert resources["resources/oda/platforms/*"] == "oda/platforms/"
    assert config["bundle"]["targets"] == "nsis"


def test_sidecar_packaging_hook_matches_runtime_candidates() -> None:
    script = (DESKTOP_ROOT / "scripts" / "build-sidecar.ps1").read_text(encoding="utf-8")
    builder = (DESKTOP_ROOT / "scripts" / "build_sidecar_pyinstaller.py").read_text(
        encoding="utf-8"
    )
    runtime = (DESKTOP_ROOT / "src-tauri" / "src" / "sidecar_runtime.rs").read_text(encoding="utf-8")

    assert "dwg-audit-sidecar" in script
    assert "src-tauri\\resources\\sidecar" in script
    assert "build_sidecar_pyinstaller.py" in script
    assert "ezdxf.addons.odafc" in builder
    # Console-subsystem sidecar preserves JSON pipes; CREATE_NO_WINDOW prevents flashes.
    assert "console=True" in builder
    assert "console=False" not in builder
    assert "sidecar" in runtime
    assert "dwg-audit-sidecar.exe" in runtime
    assert "CREATE_NO_WINDOW" in runtime
    assert "Stdio::null()" in runtime
    assert "ODAFC_PATH" in runtime
    assert "DWG_AUDIT_RESOURCE_DIR" in runtime
    assert "oda" in runtime

    main_rs = (DESKTOP_ROOT / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    assert 'windows_subsystem = "windows"' in main_rs

    assert "PREVIEW_GATE" in main_rs
    assert "PREVIEW_TIMEOUT" in main_rs
    assert "Preview request superseded" in main_rs
    assert "desktop_cancel_preview" in main_rs
    assert "ExitRequested" in main_rs
    assert "taskkill" in main_rs
    assert "drain_preview_pipe" in main_rs
    assert "ACTIVE_SIDECAR_PIDS" in main_rs
    assert "force_shutdown" in main_rs
    assert "CreateToolhelp32Snapshot" in main_rs
    assert "terminate_descendant_processes" in main_rs
    assert "TerminateProcess" in main_rs
    assert "std::process::exit(0)" in main_rs

    app_tsx = (DESKTOP_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")
    assert ".onCloseRequested" not in app_tsx


def test_oda_staging_and_release_scripts_exist() -> None:
    stage = (DESKTOP_ROOT / "scripts" / "stage-oda-resources.ps1").read_text(encoding="utf-8")
    release = (DESKTOP_ROOT / "scripts" / "build-windows-release.ps1").read_text(encoding="utf-8")
    oda_readme = (DESKTOP_ROOT / "src-tauri" / "resources" / "oda" / "README.md").read_text(
        encoding="utf-8"
    )

    assert "ODAFileConverter.exe" in stage
    assert "platforms\\qwindows.dll" in stage
    assert "resources\\oda" in stage
    assert "stage-oda-resources.ps1" in release
    assert "platforms\\qwindows.dll" in release
    assert "build-sidecar.ps1" in release
    assert "tauri:build" in release
    assert "do not commit binaries" in oda_readme.lower() or "Binary ODA" in oda_readme


def test_python_sidecar_entrypoint_uses_existing_cli_contract() -> None:
    entrypoint = REPO_ROOT / "src" / "dwg_audit" / "desktop" / "sidecar_entry.py"
    content = entrypoint.read_text(encoding="utf-8")

    assert "from dwg_audit.cli import run" in content
    assert "run()" in content


def test_python_sidecar_entrypoint_forces_utf8_output() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="gb18030")

    _configure_text_stream_utf8(stream)
    stream.write("多对一配对")
    stream.flush()

    assert stream.encoding.lower().replace("-", "") == "utf8"
    assert raw.getvalue().decode("utf-8") == "多对一配对"


def test_default_config_does_not_hardcode_machine_oda_install() -> None:
    config_py = (REPO_ROOT / "src" / "dwg_audit" / "utils" / "config.py").read_text(encoding="utf-8")
    default_yml = (REPO_ROOT / "configs" / "default.yml").read_text(encoding="utf-8")

    assert '"odafc_path": ""' in config_py
    assert 'odafc_path: ""' in default_yml
    assert "Program Files\\ODA" not in config_py
    assert "Program Files\\ODA" not in default_yml


def test_sidecar_build_avoids_collect_all_bloat() -> None:
    script = (DESKTOP_ROOT / "scripts" / "build-sidecar.ps1").read_text(encoding="utf-8")
    builder = (DESKTOP_ROOT / "scripts" / "build_sidecar_pyinstaller.py").read_text(encoding="utf-8")

    # Size-first path uses the filtered builder, not CLI collect-all flags.
    assert "build_sidecar_pyinstaller.py" in script
    code_lines = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
    assert all("--collect-all" not in line for line in code_lines)
    assert "arrow_flight" in builder
    assert "streamlit" in builder
    assert "ezdxf.addons.odafc" in builder
    assert "pyarrow.flight" in builder
    # Unused / optional dependency pruning
    assert '"networkx"' in builder or "'networkx'" in builder
    assert "PIL" in builder  # excluded optional drawing stack
    assert "fontTools" in builder  # kept: ezdxf fonts require it
    assert "pygments" in builder
    assert "include/pyarrow" in builder


def test_oda_stage_prunes_optional_payloads() -> None:
    stage = (DESKTOP_ROOT / "scripts" / "stage-oda-resources.ps1").read_text(encoding="utf-8")

    assert "Optional payload prune" in stage
    assert "ModelerGeometry_27.1_16.tx" in stage
    assert "imageformats" in stage
    assert "W3Dtk.dll" in stage
    # Conversion-critical dim-block module must not be pruned.
    removals = stage.split("OptionalRemovals")[1] if "OptionalRemovals" in stage else stage
    assert "RecomputeDimBlock" not in removals

