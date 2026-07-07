from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_ROOT = REPO_ROOT / "apps" / "desktop"


def test_tauri_bundle_declares_sidecar_resource_directory() -> None:
    config = json.loads((DESKTOP_ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))

    resources = config["bundle"]["resources"]

    assert resources["resources/sidecar/*"] == "sidecar/"


def test_sidecar_packaging_hook_matches_runtime_candidates() -> None:
    script = (DESKTOP_ROOT / "scripts" / "build-sidecar.ps1").read_text(encoding="utf-8")
    runtime = (DESKTOP_ROOT / "src-tauri" / "src" / "sidecar_runtime.rs").read_text(encoding="utf-8")

    assert "dwg-audit-sidecar" in script
    assert "src-tauri\\resources\\sidecar" in script
    assert "sidecar" in runtime
    assert "dwg-audit-sidecar.exe" in runtime


def test_python_sidecar_entrypoint_uses_existing_cli_contract() -> None:
    entrypoint = REPO_ROOT / "src" / "dwg_audit" / "desktop" / "sidecar_entry.py"
    content = entrypoint.read_text(encoding="utf-8")

    assert "from dwg_audit.cli import run" in content
    assert "run()" in content
