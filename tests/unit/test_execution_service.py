from __future__ import annotations

from pathlib import Path

from dwg_audit.services.execution import run_analysis_workflow


class _EventSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def emit(self, event: str, **payload: object) -> None:
        self.events.append((event, payload))


def test_run_analysis_workflow_runs_analyze_and_optional_audit(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    project_dir = output_root / "demo_project"
    log_path = output_root / "logs" / "custom.log"
    input_root.mkdir()
    project_dir.mkdir(parents=True)
    (output_root / "run_summary.json").write_text("[]", encoding="utf-8")
    sink = _EventSink()
    calls: dict[str, object] = {}
    event_order: list[str] = []

    monkeypatch.setattr("dwg_audit.services.execution.load_config", lambda path: {"demo": True})
    monkeypatch.setattr("dwg_audit.services.execution.configure_logging", lambda path: ("logger", path))

    def fake_analyze_input_root(input_path, output_path, config, logger, *, event_sink=None):
        calls["analyze"] = (input_path, output_path, config, logger, event_sink)
        return [project_dir]

    def fake_rerun(project_path, config, output_dir=None, *, event_sink=None):
        event_order.append("audit")
        calls["audit"] = (project_path, config, output_dir, event_sink)
        return project_path / "audit"

    monkeypatch.setattr("dwg_audit.services.execution.analyze_input_root", fake_analyze_input_root)
    monkeypatch.setattr("dwg_audit.services.execution.rerun_audit_from_findings", fake_rerun)

    result = run_analysis_workflow(
        input_root=input_root,
        output_root=output_root,
        include_audit=True,
        log_path=log_path,
        event_sink=sink,
        on_project_artifacts_ready=lambda path: event_order.append(f"ready:{path.name}"),
    )

    assert result.input_root == input_root.resolve()
    assert result.output_root == output_root.resolve()
    assert result.project_dirs == [project_dir]
    assert result.audit_dirs == [project_dir / "audit"]
    assert result.run_summary_path == output_root / "run_summary.json"
    assert result.config == {"demo": True}
    assert calls["analyze"] == (
        input_root.resolve(),
        output_root.resolve(),
        {"demo": True},
        ("logger", log_path),
        sink,
    )
    assert calls["audit"] == (project_dir, {"demo": True}, None, sink)
    assert event_order == ["ready:demo_project", "audit"]


def test_run_analysis_workflow_can_skip_audit(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    project_dir = output_root / "demo_project"
    input_root.mkdir()
    project_dir.mkdir(parents=True)

    monkeypatch.setattr("dwg_audit.services.execution.load_config", lambda path: {})
    monkeypatch.setattr("dwg_audit.services.execution.configure_logging", lambda path: object())
    monkeypatch.setattr("dwg_audit.services.execution.analyze_input_root", lambda *args, **kwargs: [project_dir])
    monkeypatch.setattr(
        "dwg_audit.services.execution.rerun_audit_from_findings",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("audit should not run")),
    )

    result = run_analysis_workflow(
        input_root=input_root,
        output_root=output_root,
        include_audit=False,
    )

    assert result.project_dirs == [project_dir]
    assert result.audit_dirs == []
