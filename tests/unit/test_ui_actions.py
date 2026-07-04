from __future__ import annotations

from pathlib import Path

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

    def fake_load_config(path):
        calls["config_path"] = path
        return {"demo": True}

    def fake_logger(path):
        calls["log_path"] = path
        return object()

    def fake_analyze_input_root(input_path, output_path, config, logger):
        calls["analyze"] = (input_path, output_path, config, logger)
        return [project_dir]

    def fake_rerun(project_path, config):
        calls["rerun"] = (project_path, config)
        audit_dir = project_path / "audit"
        audit_dir.mkdir(exist_ok=True)
        return audit_dir

    monkeypatch.setattr("dwg_audit.ui.actions.load_config", fake_load_config)
    monkeypatch.setattr("dwg_audit.ui.actions.configure_logging", fake_logger)
    monkeypatch.setattr("dwg_audit.ui.actions.analyze_input_root", fake_analyze_input_root)
    monkeypatch.setattr("dwg_audit.ui.actions.rerun_audit_from_findings", fake_rerun)

    result = run_ui_analysis(input_root, output_root, include_audit=True)

    assert result.project_dirs == [project_dir]
    assert result.audit_dirs == [project_dir / "audit"]
    assert result.run_summary_path == output_root / "run_summary.json"
    assert calls["config_path"] is None
    assert calls["log_path"] == output_root / "logs" / "ui_analyze.log"
    assert calls["analyze"][0] == input_root.resolve()
    assert calls["analyze"][1] == output_root.resolve()
    assert calls["rerun"] == (project_dir, {"demo": True})


def test_run_ui_analysis_can_skip_audit(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    input_root.mkdir()
    project_dir = output_root / "projectA"
    project_dir.mkdir(parents=True)

    monkeypatch.setattr("dwg_audit.ui.actions.load_config", lambda path: {})
    monkeypatch.setattr("dwg_audit.ui.actions.configure_logging", lambda path: object())
    monkeypatch.setattr("dwg_audit.ui.actions.analyze_input_root", lambda *args, **kwargs: [project_dir])
    monkeypatch.setattr(
        "dwg_audit.ui.actions.rerun_audit_from_findings",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("rerun should not be called")),
    )

    result = run_ui_analysis(input_root, output_root, include_audit=False)

    assert result.project_dirs == [project_dir]
    assert result.audit_dirs == []
