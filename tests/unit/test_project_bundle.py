from __future__ import annotations

from pathlib import Path

from dwg_audit.report.project_bundle import find_findings_dir, resolve_project_bundle_dir


def test_resolve_direct_bundle(tmp_path: Path) -> None:
    findings = tmp_path / "findings"
    findings.mkdir()
    assert find_findings_dir(tmp_path) == findings
    assert resolve_project_bundle_dir(tmp_path) == tmp_path


def test_resolve_nested_runner_bundle(tmp_path: Path) -> None:
    nested = tmp_path / "PROJECT_SLUG"
    findings = nested / "findings"
    findings.mkdir(parents=True)
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    assert find_findings_dir(tmp_path) == findings
    assert resolve_project_bundle_dir(tmp_path) == nested


def test_resolve_missing_findings_returns_input(tmp_path: Path) -> None:
    assert find_findings_dir(tmp_path) is None
    assert resolve_project_bundle_dir(tmp_path) == tmp_path
