import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SymbolDefinition
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_dependency_library import SymbolIdentity
from dwg_audit.cli import app
from dwg_audit.report.topology_gold import TopologyGoldValidation


def test_init_config_writes_file(tmp_path: Path) -> None:
    runner = CliRunner()
    target = tmp_path / "config.yml"

    result = runner.invoke(app, ["init-config", "--output", str(target)])

    assert result.exit_code == 0
    assert target.exists()
    assert "project:" in target.read_text(encoding="utf-8")


def test_help_lists_taskbook_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init-config" in result.stdout
    assert "analyze-project" in result.stdout
    assert "export-findings" in result.stdout
    assert "run-audit" in result.stdout
    assert "export-report" in result.stdout
    assert "analyze-session" in result.stdout
    assert "list-recent-projects" in result.stdout
    assert "load-result" in result.stdout
    assert "set-issue-status" in result.stdout
    assert "render-preview" in result.stdout
    assert "purge-session" in result.stdout
    assert "serve" in result.stdout
    assert "evaluate-promotion-gate" in result.stdout
    assert "evaluate-corpus-census" in result.stdout
    assert "validate-symbol-review" in result.stdout
    assert "promote-symbol-review" in result.stdout
    assert "build-topology-gold-template" in result.stdout
    assert "validate-topology-gold" in result.stdout
    assert "build-electrical-connection-review-pack" in result.stdout
    assert "validate-electrical-connection-review-pack" in result.stdout


def _topology_gold_validation(
    *,
    valid: bool = True,
    certified: bool = False,
) -> TopologyGoldValidation:
    return TopologyGoldValidation(
        valid=valid,
        certification_ready=certified,
        project_scope=certified,
        status="HUMAN_CERTIFIED" if certified else "PENDING",
        errors=() if valid else ("INVALID_TEST_PACK",),
        page_count=1,
        junction_count=0,
        connectivity_member_count=0,
        open_endpoint_count=0,
    )


def test_build_topology_gold_template_cli_keeps_pack_pending(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    project = tmp_path / "project"
    project.mkdir()
    output = tmp_path / "pack"
    captured: dict[str, object] = {}

    def fake_build(project_dir, **kwargs):
        captured["project_dir"] = project_dir
        captured.update(kwargs)

    monkeypatch.setattr("dwg_audit.cli.build_topology_gold_template", fake_build)
    monkeypatch.setattr(
        "dwg_audit.cli.validate_topology_gold_pack",
        lambda *_args, **_kwargs: _topology_gold_validation(),
    )

    result = runner.invoke(
        app,
        [
            "build-topology-gold-template",
            "--project",
            str(project),
            "--project-id",
            "P001",
            "--split",
            "calibration",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["certification_ready"] is False
    assert captured["project_dir"] == project.resolve()
    assert captured["project_id"] == "P001"
    assert captured["split"] == "calibration"
    assert captured["output_dir"] == output


def test_build_electrical_connection_review_pack_cli_keeps_machine_authority(
    monkeypatch, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    pack_dir = tmp_path / "pack"

    def fake_write(*_args, **_kwargs):
        pack_dir.mkdir(parents=True, exist_ok=True)
        return {
            "pack_dir": str(pack_dir),
            "summary": {
                "proposal_count": 2,
                "by_family": {"CROSS_PAGE_ENDPOINT_MATCH": 2},
            },
            "validation": {
                "valid": True,
                "promotion_ready": False,
                "certification_ready": False,
            },
            "checklist_path": str(pack_dir / "HUMAN_REVIEW_CHECKLIST.md"),
        }

    monkeypatch.setattr(
        "dwg_audit.cli.write_electrical_connection_review_pack",
        fake_write,
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "build-electrical-connection-review-pack",
            "--project",
            str(project),
            "--project-id",
            "P001",
            "--split",
            "calibration_legacy",
            "--output",
            str(pack_dir),
            "--max-proposals",
            "10",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["proposal_count"] == 2
    assert payload["validation"]["promotion_ready"] is False


def test_validate_electrical_connection_review_pack_cli_rejects_invalid(
    monkeypatch, tmp_path: Path
) -> None:
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()

    class _Validation:
        valid = False
        promotion_ready = False
        certification_ready = False

        def to_dict(self):
            return {
                "valid": False,
                "promotion_ready": False,
                "certification_ready": False,
                "errors": ["MACHINE_PACK_MARKED_HUMAN_CONFIRMED"],
            }

    monkeypatch.setattr(
        "dwg_audit.cli.validate_electrical_connection_review_pack",
        lambda *_args, **_kwargs: _Validation(),
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "validate-electrical-connection-review-pack",
            "--pack",
            str(pack_dir),
        ],
    )
    assert result.exit_code == 2


def test_validate_topology_gold_cli_can_require_certification(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    project = tmp_path / "project"
    pack = tmp_path / "pack"
    project.mkdir()
    pack.mkdir()
    monkeypatch.setattr(
        "dwg_audit.cli.validate_topology_gold_pack",
        lambda *_args, **_kwargs: _topology_gold_validation(),
    )

    pending = runner.invoke(
        app,
        [
            "validate-topology-gold",
            "--pack",
            str(pack),
            "--project",
            str(project),
            "--project-id",
            "P001",
            "--split",
            "calibration",
        ],
    )
    required = runner.invoke(
        app,
        [
            "validate-topology-gold",
            "--pack",
            str(pack),
            "--project",
            str(project),
            "--project-id",
            "P001",
            "--split",
            "calibration",
            "--require-certified",
        ],
    )

    assert pending.exit_code == 0, pending.output
    assert required.exit_code == 2


def test_validate_symbol_review_reports_pending_document_as_valid() -> None:
    runner = CliRunner()
    source = Path("configs/symbol_dependency_library.example.json")

    result = runner.invoke(
        app,
        ["validate-symbol-review", "--input", str(source)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["promotion_ready"] is False
    assert payload["document_status"] == "PENDING_HUMAN_REVIEW"


def test_promote_symbol_review_rejects_pending_document(tmp_path: Path) -> None:
    runner = CliRunner()
    target = tmp_path / "production_library.json"

    result = runner.invoke(
        app,
        [
            "promote-symbol-review",
            "--input",
            "configs/symbol_dependency_library.example.json",
            "--output",
            str(target),
        ],
    )

    assert result.exit_code == 2
    assert not target.exists()
    assert "not promotion-ready" in result.output


def test_promote_symbol_review_writes_validated_library(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    source = tmp_path / "review.json"
    target = tmp_path / "production_library.json"
    source.write_text("{}", encoding="utf-8")
    library = SymbolDependencyLibrary(
        symbols=(
            SymbolDefinition(
                identity=SymbolIdentity("relay", "1", "fp-relay"),
                annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
                registry_status=RegistryStatus.REGISTERED,
            ),
        )
    )
    monkeypatch.setattr(
        "dwg_audit.cli.promote_symbol_review_document",
        lambda _source: library,
    )

    result = runner.invoke(
        app,
        [
            "promote-symbol-review",
            "--input",
            str(source),
            "--output",
            str(target),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == library.to_dict()


def test_export_findings_lists_project_findings(tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "demo_project"
    findings = project / "findings"
    findings.mkdir(parents=True)
    (project / "manifest.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["export-findings", "--output", str(tmp_path)])

    assert result.exit_code == 0
    assert str(findings) in result.stdout


def test_run_audit_generates_audit_from_findings_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    findings = tmp_path / "demo_project" / "findings"
    findings.mkdir(parents=True)
    (findings.parent / "manifest.json").write_text('{"project_name": "demo"}', encoding="utf-8")
    (findings / "findings.json").write_text("{}", encoding="utf-8")
    (findings / "findings.md").write_text("# Findings\n", encoding="utf-8")

    audit_dir = findings.parent / "audit"
    assert not audit_dir.exists()

    result = runner.invoke(app, ["run-audit", "--findings", str(findings)])

    assert result.exit_code == 0
    assert str(audit_dir) in result.stdout
    assert (audit_dir / "issues.json").exists()
    assert (audit_dir / "audit_report.md").exists()


def test_serve_outputs_streamlit_command(tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "artifacts"
    project.mkdir()

    result = runner.invoke(app, ["serve", "--project", str(project)])

    assert result.exit_code == 0
    assert "streamlit run" in result.stdout
    assert str(project) in result.stdout


def test_export_report_passes_requested_formats(tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "demo_project"
    findings = project / "findings"
    audit = project / "audit"
    findings.mkdir(parents=True)
    audit.mkdir()
    (project / "manifest.json").write_text('{"project_name": "demo"}', encoding="utf-8")
    pd.DataFrame([{"pair_id": "P1", "status": "pass"}]).to_parquet(findings / "pairs.parquet", index=False)
    pd.DataFrame([{"file_id": "F1", "filename": "a.dwg"}]).to_parquet(findings / "source_files.parquet", index=False)
    pd.DataFrame([{"issue_id": "I1", "rule_id": "R1", "severity": "review", "status": "open"}]).to_parquet(
        audit / "issues.parquet",
        index=False,
    )

    result = runner.invoke(app, ["export-report", "--artifacts", str(project), "--format", "md"])

    assert result.exit_code == 0, result.output
    assert (audit / "audit_report.md").exists()
    assert not (audit / "audit_report.html").exists()
    assert not (audit / "issues.xlsx").exists()


def test_compare_regression_writes_report_files(tmp_path: Path) -> None:
    runner = CliRunner()
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    output = tmp_path / "regression"
    for project_dir, pair_count, issue_rules in (
        (baseline, 2, ["R-CROSS-PAGE-CONFLICT"]),
        (current, 3, ["R-CROSS-PAGE-CONFLICT", "R-ONE-TO-MANY"]),
    ):
        findings = project_dir / "findings"
        audit = project_dir / "audit"
        findings.mkdir(parents=True)
        audit.mkdir()
        (project_dir / "manifest.json").write_text(f'{{"project_name": "{project_dir.name}", "project_id": "{project_dir.name}"}}', encoding="utf-8")
        pd.DataFrame([{"pair_id": f"P{index}", "status": "pass"} for index in range(pair_count)]).to_parquet(findings / "pairs.parquet", index=False)
        pd.DataFrame([{"issue_id": f"I{index}", "rule_id": rule_id, "status": "open"} for index, rule_id in enumerate(issue_rules, start=1)]).to_parquet(
            audit / "issues.parquet",
            index=False,
        )

    result = runner.invoke(
        app,
        ["compare-regression", "--baseline", str(baseline), "--current", str(current), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert (output / "regression_report.json").exists()
    assert (output / "regression_report.md").exists()
    assert "pair_count delta: 1" in result.stdout
    assert "issue_count delta: 1" in result.stdout


def test_list_recent_projects_cli_reads_state_db(tmp_path: Path) -> None:
    runner = CliRunner()
    state_db = tmp_path / "desktop_state.db"

    from dwg_audit.desktop.state_store import DesktopStateStore

    DesktopStateStore(state_db).record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(tmp_path / "workspace" / "session-a" / "demo_project"),
        status="completed",
        sheet_count=1,
        pair_count=2,
        issue_count=1,
        metadata={"demo": True},
    )

    result = runner.invoke(app, ["list-recent-projects", "--state-db", str(state_db)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["projects"][0]["project_id"] == "demo-project"


def test_load_result_cli_returns_project_payload(tmp_path: Path) -> None:
    runner = CliRunner()
    state_db = tmp_path / "desktop_state.db"

    from dwg_audit.desktop.state_store import DesktopStateStore

    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(tmp_path / "workspace" / "session-a" / "demo_project"),
        status="completed",
        sheet_count=1,
        pair_count=2,
        issue_count=1,
        metadata={"demo": True},
    )
    store.replace_issue_summaries(
        "session-a:demo-project",
        [
            {
                "issue_id": "I1",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "issue_type": "pair_low_confidence",
                "title": "Low Confidence",
                "summary": "Low confidence pair",
                "explanation": "Pair score is below the automatic pass threshold.",
                "recommended_action": "Review both endpoint labels.",
                "severity": "review",
                "status": "open",
                "confidence": 0.74,
                "sheet_id": "S1",
                "file_id": "F1",
                "filename": "01.dwg",
                "sheet_no": "01",
                "line_group_id": "G1",
                "left_value": "101",
                "right_value": "201",
                "primary_pair_id": "P1",
                "one_to_many_classification": "review",
                "evidence": {"filename": "01.dwg"},
                "evidence_refs": [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}],
                "related_pair_ids": ["P2"],
                "sheet_ids": ["S1"],
                "values": ["101", "201"],
            }
        ],
    )

    result = runner.invoke(app, ["load-result", "--project-id", "demo-project", "--state-db", str(state_db)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["run"]["project_id"] == "demo-project"
    assert payload["issues"][0]["issue_id"] == "I1"
    assert payload["issues"][0]["issue_type"] == "pair_low_confidence"
    assert payload["issues"][0]["related_pair_ids"] == ["P2"]
    assert payload["issues"][0]["evidence_refs"] == [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}]


def test_analyze_session_cli_emits_final_result_line(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    def fake_analyze_session(**kwargs):
        kwargs["event_writer"].emit("run_started", session_id="session-a")
        return [{"project_id": "demo-project", "project_name": "Demo Project"}]

    monkeypatch.setattr("dwg_audit.cli.run_desktop_session", fake_analyze_session)

    input_root = tmp_path / "input"
    input_root.mkdir()

    result = runner.invoke(app, ["analyze-session", "--input", str(input_root), "--workspace-root", str(tmp_path / "workspace")])

    assert result.exit_code == 0, result.output
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert lines[0]["event"] == "run_started"
    assert lines[-1]["event"] == "run_result"
    assert lines[-1]["projects"][0]["project_id"] == "demo-project"


def test_analyze_session_cli_can_defer_workspace_cleanup(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_analyze_session(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr("dwg_audit.cli.run_desktop_session", fake_analyze_session)
    input_root = tmp_path / "input"
    input_root.mkdir()

    result = CliRunner().invoke(
        app,
        [
            "analyze-session",
            "--input",
            str(input_root),
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--defer-cleanup",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["compact_after_store"] is False


def test_render_preview_cli_returns_preview_payload(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    preview_path = tmp_path / "preview.svg"
    captured: dict[str, object] = {}

    def fake_render_project_preview(**kwargs):
        captured.update(kwargs)
        return {"project_id": "demo-project", "preview_path": str(preview_path)}

    monkeypatch.setattr("dwg_audit.cli.render_project_preview", fake_render_project_preview)

    result = runner.invoke(
        app,
        ["render-preview", "--project-id", "demo-project", "--issue-id", "I1", "--line-group-id", "G2"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["project_id"] == "demo-project"
    assert payload["preview_path"] == str(preview_path)
    assert captured["line_group_id"] == "G2"


def test_set_issue_status_cli_returns_updated_payload(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(
        "dwg_audit.cli.update_desktop_issue_status",
        lambda **kwargs: {"project_id": "demo-project", "issue_id": "I1", "status": "resolved"},
    )

    result = runner.invoke(
        app,
        ["set-issue-status", "--project-id", "demo-project", "--issue-id", "I1", "--status", "resolved"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["issue_id"] == "I1"
    assert payload["status"] == "resolved"


def test_promotion_gate_cli_rejects_primary_engine_mismatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config.yml"
    config.write_text("recognition:\n  primary_engine: legacy\n", encoding="utf-8")
    called = False

    def unexpected_evaluation(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("evaluation must not run after a config mismatch")

    monkeypatch.setattr("dwg_audit.cli.evaluate_promotion_gate", unexpected_evaluation)

    result = runner.invoke(
        app,
        [
            "evaluate-promotion-gate",
            "--project",
            f"P001={project}",
            "--config",
            str(config),
            "--primary-engine",
            "topology",
        ],
    )

    assert result.exit_code == 2
    assert called is False


def test_promotion_gate_cli_returns_nonzero_for_structural_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    project = tmp_path / "project"
    project.mkdir()
    output = tmp_path / "gate"
    evidence = {
        "project_count": 1,
        "structural_pass_all": False,
        "decision": {
            "hard_issue_precision_status": "UNMEASURED_NO_LABELS",
            "ready_for_review_only_v2_assist": False,
            "ready_for_primary_engine_flip": False,
        },
        "projects": [],
    }
    monkeypatch.setattr("dwg_audit.cli.evaluate_promotion_gate", lambda **kwargs: evidence)
    monkeypatch.setattr(
        "dwg_audit.cli.write_promotion_gate_evidence",
        lambda *_args, **_kwargs: {
            "promotion_gate_evidence": output / "promotion_gate_evidence.json",
            "metrics_by_project": output / "metrics_by_project.csv",
            "decision_log": output / "decision_log.md",
            "topology_metrics_by_project": output / "topology_metrics_by_project.csv",
            "topology_metrics_summary": output / "topology_metrics_summary.json",
        },
    )

    result = runner.invoke(
        app,
        ["evaluate-promotion-gate", "--project", f"P001={project}", "--output", str(output)],
    )

    assert result.exit_code == 2
    assert "structural_pass_all: False" in result.output


def test_corpus_census_cli_passes_splits_and_writes_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    project = tmp_path / "project"
    project.mkdir()
    output = tmp_path / "corpus"
    captured: dict[str, object] = {}
    evaluation = {
        "projects": [],
        "summary": {
            "project_count": 1,
            "status": "VALID",
            "all_projects_valid": True,
        },
    }

    def fake_evaluate(project_dirs, **kwargs):
        captured["project_dirs"] = project_dirs
        captured.update(kwargs)
        return evaluation

    monkeypatch.setattr("dwg_audit.cli.evaluate_corpus_census", fake_evaluate)
    monkeypatch.setattr(
        "dwg_audit.cli.write_corpus_census_artifacts",
        lambda _evaluation, _output: {
            "by_project": output / "by_project.csv",
            "summary": output / "summary.json",
        },
    )

    result = runner.invoke(
        app,
        [
            "evaluate-corpus-census",
            "--project",
            f"P001:calibration={project}",
            "--held-out",
            "P003",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["splits"] == {"P001": "calibration"}
    assert captured["held_out_projects"] == {"P003"}
    assert captured["project_dirs"] == {"P001": project.resolve()}
    assert "status: VALID" in result.output


def test_corpus_census_cli_returns_nonzero_for_invalid_corpus(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    project = tmp_path / "project"
    project.mkdir()
    output = tmp_path / "corpus"
    evaluation = {
        "projects": [],
        "summary": {
            "project_count": 1,
            "status": "INVALID",
            "all_projects_valid": False,
        },
    }
    monkeypatch.setattr(
        "dwg_audit.cli.evaluate_corpus_census", lambda *_args, **_kwargs: evaluation
    )
    monkeypatch.setattr(
        "dwg_audit.cli.write_corpus_census_artifacts",
        lambda _evaluation, _output: {
            "by_project": output / "by_project.csv",
            "summary": output / "summary.json",
        },
    )

    result = runner.invoke(
        app,
        ["evaluate-corpus-census", "--project", f"P001={project}"],
    )

    assert result.exit_code == 2
    assert "status: INVALID" in result.output
