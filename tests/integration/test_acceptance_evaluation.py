from __future__ import annotations

import json
import shutil
from pathlib import Path

import ezdxf
import yaml
from typer.testing import CliRunner

from dwg_audit.cli import app


def _add_complete_pair(msp, left: str, right: str, y: float) -> None:
    msp.add_text(left, dxfattribs={"insert": (18.0, y), "height": 2.5, "layer": "TEXT"})
    msp.add_text(right, dxfattribs={"insert": (82.0, y), "height": 2.5, "layer": "TEXT"})
    msp.add_line((20.0, y), (80.0, y), dxfattribs={"layer": "CONNECT"})


def _add_missing_right_pair(msp, left: str, y: float) -> None:
    msp.add_text(left, dxfattribs={"insert": (18.0, y), "height": 2.5, "layer": "TEXT"})
    msp.add_line((20.0, y), (80.0, y), dxfattribs={"layer": "CONNECT"})


def _add_missing_left_pair(msp, right: str, y: float) -> None:
    msp.add_text(right, dxfattribs={"insert": (82.0, y), "height": 2.5, "layer": "TEXT"})
    msp.add_line((20.0, y), (80.0, y), dxfattribs={"layer": "CONNECT"})


def _add_ambiguous_review_pair(msp, left: str, selected_right: str, alt_right: str, y: float) -> None:
    msp.add_text(left, dxfattribs={"insert": (18.0, y), "height": 2.5, "layer": "TEXT"})
    msp.add_text(selected_right, dxfattribs={"insert": (82.0, y), "height": 2.5, "layer": "TEXT"})
    msp.add_text(alt_right, dxfattribs={"insert": (83.5, y), "height": 2.5, "layer": "TEXT"})
    msp.add_line((20.0, y), (80.0, y), dxfattribs={"layer": "CONNECT"})


def _add_page_no_marker(msp, value: str) -> None:
    msp.add_text(value, dxfattribs={"insert": (108.0, 12.0), "height": 2.5, "layer": "TITLE"})


def test_acceptance_mini_project_produces_quantified_acceptance_report(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures" / "acceptance_mini"
    project = tmp_path / "project"
    shutil.copytree(fixture_root / "project", project)
    spec_path = fixture_root / "spec.json"

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
                {
                    "layout": {
                        "audit_area": {
                            "mode": "manual",
                            "manual_bbox": [0.0, 0.0, 120.0, 320.0],
                        },
                        "title_block": {
                            "mode": "manual",
                            "manual_bbox": [100.0, 0.0, 120.0, 24.0],
                        },
                    }
                },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        staged_name = Path(target).name
        if staged_name.startswith("F0002_"):
            _add_page_no_marker(msp, "04")
            for left, right, y in (
                ("101", "201", 40.0),
                ("102", "202", 80.0),
                ("103", "203", 120.0),
                ("104", "204", 160.0),
                ("301", "401", 200.0),
                ("302", "501", 240.0),
            ):
                _add_complete_pair(msp, left, right, y)
        elif staged_name.startswith("F0003_"):
            _add_page_no_marker(msp, "05")
            for left, right, y in (
                ("101", "201", 40.0),
                ("102", "202", 80.0),
                ("105", "205", 120.0),
                ("301", "402", 160.0),
            ):
                _add_complete_pair(msp, left, right, y)
            _add_missing_right_pair(msp, "701", 200.0)
        elif staged_name.startswith("F0004_"):
            _add_page_no_marker(msp, "06")
            for left, right, y in (
                ("103", "203", 40.0),
                ("104", "204", 80.0),
                ("106", "206", 120.0),
                ("302", "502", 160.0),
            ):
                _add_complete_pair(msp, left, right, y)
            _add_missing_left_pair(msp, "702", 200.0)
        elif staged_name.startswith("F0005_"):
            _add_page_no_marker(msp, "07")
            _add_ambiguous_review_pair(msp, "801", "901", "902", 60.0)
            _add_ambiguous_review_pair(msp, "802", "903", "904", 120.0)
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    analyze = runner.invoke(
        app,
        ["analyze-project", "--input", str(project), "--output", str(output_dir), "--config", str(config_path)],
    )
    assert analyze.exit_code == 0, analyze.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    project_dir = Path(run_summary[0]["artifact_dir"])

    audit = runner.invoke(app, ["run-audit", "--findings", str(project_dir / "findings")])
    assert audit.exit_code == 0, audit.output

    acceptance_dir = tmp_path / "acceptance_report"
    evaluate = runner.invoke(
        app,
        [
            "evaluate-acceptance",
            "--project",
            str(project_dir),
            "--spec",
            str(spec_path),
            "--output",
            str(acceptance_dir),
        ],
    )
    assert evaluate.exit_code == 0, evaluate.output

    payload = json.loads((acceptance_dir / "acceptance_report.json").read_text(encoding="utf-8"))
    assert payload["acceptance_passed"] is True
    assert payload["pair_metrics"]["expected_pair_count"] == 16
    assert payload["pair_metrics"]["matched_pair_count"] == 16
    assert payload["pair_metrics"]["precision"] == 1.0
    assert payload["pair_metrics"]["recall"] == 1.0
    assert payload["skip_page_metrics"]["matched_count"] == 1
    assert payload["conflict_issue_metrics"]["matched_count"] == 2
    assert payload["missing_issue_metrics"]["matched_count"] == 2
    assert payload["review_pair_metrics"]["matched_count"] == 2
    assert payload["issue_field_coverage"]["all_required_fields_present"] is True

    markdown = (acceptance_dir / "acceptance_report.md").read_text(encoding="utf-8")
    assert "Acceptance Report" in markdown
    assert "Precision: `1.0`" in markdown
    assert "Recall: `1.0`" in markdown
