from __future__ import annotations

from pathlib import Path

from dwg_audit.services import AnalysisRunResult
from dwg_audit.ui.actions import discover_project_outputs
from dwg_audit.ui.actions import run_ui_analysis


def test_discover_project_outputs_returns_only_manifest_dirs(tmp_path: Path) -> None:
    project_a = tmp_path / "a_project"
    project_b = tmp_path / "b_project"
    ignored = tmp_path / "logs"
    project_a.mkdir()
    project_b.mkdir()
    ignored.mkdir()
    (project_a / "manifest.json").write_text("{}", encoding="utf-8")
    (project_b / "manifest.json").write_text("{}", encoding="utf-8")

    result = discover_project_outputs(tmp_path)

    assert result == [project_a, project_b]


def test_run_ui_analysis_calls_pipeline_and_optional_audit(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    input_root.mkdir()
    project_dir = output_root / "projectA"
    project_dir.mkdir(parents=True)
    (output_root / "run_summary.json").write_text("[]", encoding="utf-8")

    calls: dict[str, object] = {}

    def fake_run_analysis_workflow(**kwargs):
        calls["workflow"] = kwargs
        audit_dir = project_dir / "audit"
        audit_dir.mkdir(exist_ok=True)
        return AnalysisRunResult(
            input_root=kwargs["input_root"],
            output_root=kwargs["output_root"],
            project_dirs=[project_dir],
            audit_dirs=[audit_dir],
            config_path=None,
            run_summary_path=output_root / "run_summary.json",
            config={"demo": True},
        )

    monkeypatch.setattr("dwg_audit.ui.actions.run_analysis_workflow", fake_run_analysis_workflow)

    result = run_ui_analysis(input_root, output_root, include_audit=True)

    assert result.project_dirs == [project_dir]
    assert result.audit_dirs == [project_dir / "audit"]
    assert result.run_summary_path == output_root / "run_summary.json"
    assert calls["workflow"]["input_root"] == input_root.resolve()
    assert calls["workflow"]["output_root"] == output_root.resolve()
    assert calls["workflow"]["config_path"] is None
    assert calls["workflow"]["include_audit"] is True
    assert calls["workflow"]["log_path"] == output_root / "logs" / "ui_analyze.log"


def test_run_ui_analysis_can_skip_audit(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    input_root.mkdir()
    project_dir = output_root / "projectA"
    project_dir.mkdir(parents=True)

    def fake_run_analysis_workflow(**kwargs):
        assert kwargs["include_audit"] is False
        return AnalysisRunResult(
            input_root=kwargs["input_root"],
            output_root=kwargs["output_root"],
            project_dirs=[project_dir],
            audit_dirs=[],
            config_path=None,
            run_summary_path=None,
            config={},
        )

    monkeypatch.setattr("dwg_audit.ui.actions.run_analysis_workflow", fake_run_analysis_workflow)

    result = run_ui_analysis(input_root, output_root, include_audit=False)

    assert result.project_dirs == [project_dir]
    assert result.audit_dirs == []
