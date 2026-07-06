from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import pandas as pd
import yaml
from typer.testing import CliRunner

from dwg_audit.cli import app


def test_analyze_project_records_failures_and_reuses_cached_dxf(
    monkeypatch,
    tmp_path: Path,
    sample_text_prj: str,
    sample_terminal_xml: str,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "demo.prj").write_text(sample_text_prj, encoding="gbk")
    (project / "LdDzbInfo.xml").write_text(sample_terminal_xml, encoding="utf-8")
    (project / "04 交流回路图1.dwg").write_bytes(b"AC1018demo")
    (project / "05 回路图测试.dwg").write_bytes(b"BROKEN")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    convert_calls: list[tuple[Path, Path]] = []

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        convert_calls.append((Path(source), Path(target)))
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_text("101", dxfattribs={"insert": (10, 10), "height": 2.5})
        msp.add_line((0, 10), (30, 10))
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"

    first = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert second.exit_code == 0, second.output

    assert len(convert_calls) == 1

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert run_summary[0]["project_name"] == "示例项目"

    project_dir = Path(run_summary[0]["artifact_dir"])
    manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
    source_files = {item["filename"]: item for item in manifest["source_files"]}

    assert source_files["04 交流回路图1.dwg"]["conversion_status"] == "cached"
    assert source_files["04 交流回路图1.dwg"]["dxf_path"]
    assert source_files["05 回路图测试.dwg"]["conversion_status"] == "failed_invalid_header"
    assert source_files["05 回路图测试.dwg"]["conversion_detail"] == "Non-standard DWG header."
    assert Path(source_files["04 交流回路图1.dwg"]["dxf_path"]).exists()

    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"

    assert (findings_dir / "findings.md").exists()
    assert (findings_dir / "findings.json").exists()
    assert not audit_dir.exists()

    audit = runner.invoke(app, ["run-audit", "--findings", str(findings_dir)])
    assert audit.exit_code == 0, audit.output
    assert str(audit_dir) in audit.output
    assert (audit_dir / "issues.json").exists()
    assert (audit_dir / "audit_report.md").exists()


def test_analyze_project_includes_supplemental_pages_in_downstream_audit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "04 回路图.dwg").write_bytes(b"AC1018demo")
    (project / "07 屏端子图.dwg").write_bytes(b"AC1018demo")
    (project / "08 封面.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        name = Path(source).name
        if name.startswith("F0001"):
            msp.add_text("101", dxfattribs={"insert": (10, 40), "height": 2.5})
            msp.add_text("202", dxfattribs={"insert": (90, 40), "height": 2.5})
            msp.add_line((20, 40), (80, 40))
        elif name.startswith("F0002"):
            msp.add_text("303", dxfattribs={"insert": (10, 40), "height": 2.5})
            msp.add_text("404", dxfattribs={"insert": (90, 40), "height": 2.5})
            msp.add_line((20, 40), (80, 40))
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"
    page_findings_dir = findings_dir / "page_findings"
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    line_groups = pd.read_parquet(findings_dir / "line_groups.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    page_roles = {row["filename"]: row["audit_role"] for _, row in pages.iterrows()}
    page_dispositions = {row["filename"]: row["audit_disposition"] for _, row in pages.iterrows()}
    page_primary = {row["filename"]: bool(row["is_primary_audit_candidate"]) for _, row in pages.iterrows()}
    sheet_by_file = {row["filename"]: row["sheet_id"] for _, row in pages.iterrows()}

    assert page_roles["04 回路图.dwg"] == "primary"
    assert page_dispositions["04 回路图.dwg"] == "audit_required"
    assert page_primary["04 回路图.dwg"] is True
    assert page_roles["07 屏端子图.dwg"] == "supplemental"
    assert page_dispositions["07 屏端子图.dwg"] == "audit_required"
    assert page_primary["07 屏端子图.dwg"] is True
    assert page_roles["08 封面.dwg"] == "skip"
    assert page_dispositions["08 封面.dwg"] == "skip_stable"
    assert page_primary["08 封面.dwg"] is False
    assert findings_payload["page_findings_count"] == len(findings_payload["page_findings"]) == len(pages)
    assert not page_findings_dir.exists()
    assert "page_findings/" not in findings_payload["artifacts"]["findings"]

    assert set(line_groups["sheet_id"].tolist()) == {
        sheet_by_file["04 回路图.dwg"],
        sheet_by_file["07 屏端子图.dwg"],
    }
    assert set(pairs["sheet_id"].tolist()) == {
        sheet_by_file["04 回路图.dwg"],
        sheet_by_file["07 屏端子图.dwg"],
    }
    assert sheet_by_file["08 封面.dwg"] not in set(line_groups["sheet_id"].tolist())
    assert findings_payload["primary_audit_pages"] == 1
    assert findings_payload["supplemental_audit_pages"] == 1
    assert findings_payload["included_audit_pages"] == 2
    assert findings_payload["audit_page_counts"] == {
        "primary": 1,
        "secondary": 0,
        "skip": 1,
        "supplemental": 1,
    }
    assert findings_payload["audit_disposition_counts"] == {
        "audit_required": 2,
        "skip_stable": 1,
    }


def test_analyze_project_routes_table_like_page_to_table_extractor_and_emits_table_mapping(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "04 回路图.dwg").write_bytes(b"AC1018demo")
    (project / "05 回路表格图.dwg").write_bytes(b"AC1018demo")
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "layout": {
                    "audit_area": {
                        "mode": "manual",
                        "manual_bbox": [0.0, 0.0, 320.0, 320.0],
                    }
                },
                "confidence": {
                    "high_threshold": 0.8,
                    "review_threshold": 0.75,
                },
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
        if staged_name.startswith("F0001_"):
            msp.add_text("101", dxfattribs={"insert": (10, 200), "height": 2.5})
            msp.add_text("202", dxfattribs={"insert": (90, 200), "height": 2.5})
            msp.add_line((20, 200), (80, 200), dxfattribs={"layer": "CONNECT"})
        else:
            for index, y in enumerate((60.0, 100.0, 140.0, 180.0, 220.0, 260.0), start=1):
                msp.add_line((10.0, y), (290.0, y), dxfattribs={"layer": "TABLE"})
            for index, x in enumerate((10.0, 100.0, 200.0, 290.0), start=1):
                msp.add_line((x, 60.0), (x, 260.0), dxfattribs={"layer": "TABLE"})
            for idx in range(20):
                base_x = 18.0 + (idx % 5) * 48.0
                base_y = (60.0, 100.0, 140.0, 180.0)[idx // 5]
                msp.add_lwpolyline(
                    [
                        (base_x, base_y),
                        (base_x + 22.0, base_y),
                    ],
                    dxfattribs={"layer": "TABLE"},
                )
                for text, x, y in (
                    ("101", 55.0, 80.0),
                    ("102", 150.0, 80.0),
                    ("103", 245.0, 80.0),
                    ("201", 55.0, 120.0),
                    ("202", 150.0, 120.0),
                    ("203", 245.0, 120.0),
                    ("301", 55.0, 160.0),
                    ("302", 150.0, 160.0),
                    ("303", 245.0, 160.0),
                ):
                    msp.add_text(text, dxfattribs={"insert": (x, y), "height": 2.5, "layer": "TEXT"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(
        app,
        ["analyze-project", "--input", str(project), "--output", str(output_dir), "--config", str(config_path)],
    )
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    line_groups = pd.read_parquet(findings_dir / "line_groups.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    page_findings = {item["filename"]: item for item in findings_payload["page_findings"]}
    table_page = page_findings["05 回路表格图.dwg"]
    wire_page = page_findings["04 回路图.dwg"]
    pages_by_file = {row["filename"]: row for _, row in pages.iterrows()}

    assert wire_page["page_type"] == "二次原理图"
    assert wire_page["audit_disposition"] == "audit_required"
    assert wire_page["route_target"] == "WireDiagramExtractor"
    assert table_page["page_type"] == "表格型图"
    assert table_page["audit_disposition"] == "audit_required"
    assert table_page["route_target"] == "TableExtractor"
    assert table_page["structure_summary"]["table_mapping_count"] == 3
    assert table_page["structure_summary"]["three_column_table"] is True
    assert "dedicated table path recovered 3 structured row mappings" in table_page["recognition_strategy"]
    assert "middle-column-to-outer-column mappings as high-confidence structured evidence" in table_page["number_matching_strategy"]
    assert findings_payload["table_extraction_summary"]["table_pages"] == 1
    assert findings_payload["table_extraction_summary"]["three_column_pages"] == 1
    assert findings_payload["table_extraction_summary"]["total_mappings"] == 3
    assert findings_payload["table_extraction_summary"]["status"] == "table_mappings_recovered"
    assert findings_payload["table_extraction_summary"]["classified_table_pages"] == 1
    assert findings_payload["table_extraction_summary"]["classified_table_filenames"] == ["05 回路表格图.dwg"]
    assert pages_by_file["04 回路图.dwg"]["page_type"] == "二次原理图"
    assert pages_by_file["04 回路图.dwg"]["route_target"] == "WireDiagramExtractor"
    assert bool(pages_by_file["04 回路图.dwg"]["grid_heavy"]) is False
    assert pages_by_file["05 回路表格图.dwg"]["page_type"] == "表格型图"
    assert pages_by_file["05 回路表格图.dwg"]["route_target"] == "TableExtractor"
    assert bool(pages_by_file["05 回路表格图.dwg"]["table_like"]) is True

    table_sheet_id = table_page["sheet_id"]
    wire_sheet_id = wire_page["sheet_id"]
    assert table_sheet_id not in set(line_groups["sheet_id"].tolist())
    assert wire_sheet_id in set(line_groups["sheet_id"].tolist())

    table_pairs = pairs[pairs["sheet_id"] == table_sheet_id]
    assert len(table_pairs) == 3
    assert table_pairs["line_group_id"].isna().all()
    first_evidence = json.loads(table_pairs.iloc[0]["evidence"])
    assert first_evidence["source"] == "table_mapping"
    assert first_evidence["table_mapping"]["sheet_id"] == table_sheet_id


def test_analyze_project_supports_header_semantic_three_column_table_mapping(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "04 回路图.dwg").write_bytes(b"AC1018demo")
    (project / "05 回路表格图.dwg").write_bytes(b"AC1018demo")
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "layout": {
                    "audit_area": {
                        "mode": "manual",
                        "manual_bbox": [0.0, 0.0, 320.0, 320.0],
                    }
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
        if staged_name.startswith("F0001_"):
            msp.add_text("101", dxfattribs={"insert": (10, 200), "height": 2.5})
            msp.add_text("202", dxfattribs={"insert": (90, 200), "height": 2.5})
            msp.add_line((20, 200), (80, 200), dxfattribs={"layer": "CONNECT"})
        else:
            for y in (60.0, 100.0, 140.0, 180.0):
                msp.add_line((10.0, y), (290.0, y), dxfattribs={"layer": "TABLE"})
            for y in (75.0, 165.0):
                msp.add_line((20.0, y), (80.0, y), dxfattribs={"layer": "TABLE"})
            for x in (10.0, 100.0, 200.0, 290.0):
                msp.add_line((x, 60.0), (x, 180.0), dxfattribs={"layer": "TABLE"})
            for idx in range(20):
                base_x = 18.0 + (idx % 5) * 48.0
                base_y = (60.0, 100.0, 140.0, 60.0)[idx // 5]
                msp.add_lwpolyline(
                    [
                        (base_x, base_y),
                        (base_x + 22.0, base_y),
                    ],
                    dxfattribs={"layer": "TABLE"},
                )
            for text, x, y in (
                ("1-21QD", 150.0, 80.0),
                ("1-21n552", 55.0, 120.0),
                ("1", 150.0, 120.0),
                ("1-21n553", 245.0, 120.0),
                ("1-21n554", 55.0, 160.0),
                ("2", 150.0, 160.0),
                ("1-21n555", 245.0, 160.0),
            ):
                msp.add_text(text, dxfattribs={"insert": (x, y), "height": 2.5, "layer": "TEXT"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(
        app,
        ["analyze-project", "--input", str(project), "--output", str(output_dir), "--config", str(config_path)],
    )
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    page_findings = {item["filename"]: item for item in findings_payload["page_findings"]}
    table_page = page_findings["05 回路表格图.dwg"]
    assert table_page["route_target"] == "TableExtractor"
    assert table_page["structure_summary"]["table_mapping_count"] == 2
    assert table_page["structure_summary"]["three_column_table"] is True
    assert table_page["structure_summary"]["table_mapping_modes"] == {"header_semantic_three_column": 2}
    assert table_page["structure_summary"]["table_header_prefixes"] == ["1-21QD"]
    assert table_page["structure_summary"]["table_logical_endpoint_examples"] == ["1-21QD1", "1-21QD2"]
    assert table_page["structure_summary"]["table_row_number_sequence_valid"] is True

    table_sheet_id = table_page["sheet_id"]
    table_pairs = pairs[pairs["sheet_id"] == table_sheet_id]
    assert len(table_pairs) == 4
    pair_values = {(row["left_value"], row["right_value"]) for _, row in table_pairs.iterrows()}
    assert pair_values == {
        ("1-21QD1", "1-21n552"),
        ("1-21QD1", "1-21n553"),
        ("1-21QD2", "1-21n554"),
        ("1-21QD2", "1-21n555"),
    }
    first_evidence = json.loads(table_pairs.iloc[0]["evidence"])
    assert first_evidence["table_mapping"]["mapping_mode"] == "header_semantic_three_column"
    assert first_evidence["table_mapping"]["logical_endpoint"] in {"1-21QD1", "1-21QD2"}


def test_run_audit_emits_mixed_source_conflict_for_table_mapping_vs_wire_pair(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "04 回路图.dwg").write_bytes(b"AC1018demo")
    (project / "05 回路表格图.dwg").write_bytes(b"AC1018demo")
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "layout": {
                    "audit_area": {
                        "mode": "manual",
                        "manual_bbox": [0.0, 0.0, 320.0, 320.0],
                    }
                },
                "confidence": {
                    "high_threshold": 0.8,
                    "review_threshold": 0.75,
                },
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
        if staged_name.startswith("F0001_"):
            msp.add_text("102", dxfattribs={"insert": (10, 200), "height": 2.5})
            msp.add_text("204", dxfattribs={"insert": (90, 200), "height": 2.5})
            msp.add_line((20, 200), (80, 200), dxfattribs={"layer": "CONNECT"})
        else:
            for y in (60.0, 100.0, 140.0, 180.0, 220.0, 260.0):
                msp.add_line((10.0, y), (290.0, y), dxfattribs={"layer": "TABLE"})
            for x in (10.0, 100.0, 200.0, 290.0):
                msp.add_line((x, 60.0), (x, 260.0), dxfattribs={"layer": "TABLE"})
            for idx in range(20):
                base_x = 18.0 + (idx % 5) * 48.0
                base_y = (60.0, 100.0, 140.0, 180.0)[idx // 5]
                msp.add_lwpolyline(
                    [
                        (base_x, base_y),
                        (base_x + 22.0, base_y),
                    ],
                    dxfattribs={"layer": "TABLE"},
                )
            for text, x, y in (
                ("101", 55.0, 80.0),
                ("102", 150.0, 80.0),
                ("103", 245.0, 80.0),
                ("201", 55.0, 120.0),
                ("202", 150.0, 120.0),
                ("203", 245.0, 120.0),
                ("301", 55.0, 160.0),
                ("302", 150.0, 160.0),
                ("303", 245.0, 160.0),
            ):
                msp.add_text(text, dxfattribs={"insert": (x, y), "height": 2.5, "layer": "TEXT"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(
        app,
        ["analyze-project", "--input", str(project), "--output", str(output_dir), "--config", str(config_path)],
    )
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    audit = runner.invoke(app, ["run-audit", "--findings", str(findings_dir), "--config", str(config_path)])
    assert audit.exit_code == 0, audit.output

    audit_dir = Path(run_summary[0]["artifact_dir"]) / "audit"
    issues = json.loads((audit_dir / "issues.json").read_text(encoding="utf-8"))

    mixed = next(item for item in issues if item["rule_id"] == "R-TABLE-MAPPING-SOURCE-CONFLICT")
    assert mixed["severity"] == "major"
    assert mixed["left_value"] == "102"
    assert mixed["filename"]
    assert mixed["sheet_no"]
    assert mixed["rationale"]
    assert mixed["evidence"]["source_conflict_kind"] == "table_mapping_vs_ordinary_pair"
    assert mixed["evidence"]["table_mapping_values"] == ["103"]
    assert mixed["evidence"]["ordinary_pair_values"] == ["204"]
    assert mixed["evidence"]["conflicting_values"] == ["103", "204"]

def test_analyze_project_can_include_backplate_pages_as_supplemental_audit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "04 回路图.dwg").write_bytes(b"AC1018demo")
    (project / "17 背板接线图1.dwg").write_bytes(b"AC1018demo")

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "project": {
                    "audit_supplemental_categories": ["背板接线图"],
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
        msp.add_text("101", dxfattribs={"insert": (10, 40), "height": 2.5})
        msp.add_text("202", dxfattribs={"insert": (90, 40), "height": 2.5})
        msp.add_line((20, 40), (80, 40))
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(
        app,
        ["analyze-project", "--input", str(project), "--output", str(output_dir), "--config", str(config_path)],
    )
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    line_groups = pd.read_parquet(findings_dir / "line_groups.parquet")

    page_roles = {row["filename"]: row["audit_role"] for _, row in pages.iterrows()}
    page_dispositions = {row["filename"]: row["audit_disposition"] for _, row in pages.iterrows()}
    page_primary = {row["filename"]: bool(row["is_primary_audit_candidate"]) for _, row in pages.iterrows()}
    sheet_by_file = {row["filename"]: row["sheet_id"] for _, row in pages.iterrows()}

    assert page_roles["04 回路图.dwg"] == "primary"
    assert page_roles["17 背板接线图1.dwg"] == "supplemental"
    assert page_dispositions["17 背板接线图1.dwg"] == "audit_required"
    assert page_primary["17 背板接线图1.dwg"] is True
    assert set(line_groups["sheet_id"].tolist()) == {
        sheet_by_file["04 回路图.dwg"],
        sheet_by_file["17 背板接线图1.dwg"],
    }
    assert findings_payload["primary_audit_pages"] == 1
    assert findings_payload["supplemental_audit_pages"] == 1
    assert findings_payload["included_audit_pages"] == 2
    assert findings_payload["audit_page_counts"] == {
        "primary": 1,
        "secondary": 0,
        "skip": 0,
        "supplemental": 1,
    }
    assert findings_payload["audit_disposition_counts"] == {"audit_required": 2}


def test_analyze_project_applies_terminal_page_numeric_suffix_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "07 屏端子图.dwg").write_bytes(b"AC1018demo")

    config_path = tmp_path / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "project": {
                    "audit_supplemental_categories": ["屏端子图"],
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
        msp.add_text("1-21n110", dxfattribs={"insert": (46, 40), "height": 2.5, "layer": "0"})
        msp.add_text("3-21n210", dxfattribs={"insert": (106, 40), "height": 2.5, "layer": "0"})
        msp.add_line((20, 40), (80, 40), dxfattribs={"layer": "CONNECT"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(
        app,
        ["analyze-project", "--input", str(project), "--output", str(output_dir), "--config", str(config_path)],
    )
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    terminal_candidates = pd.read_parquet(findings_dir / "terminal_candidates.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    page_roles = {row["filename"]: row["audit_role"] for _, row in pages.iterrows()}
    sheet_by_file = {row["filename"]: row["sheet_id"] for _, row in pages.iterrows()}
    terminal_sheet_id = sheet_by_file["07 屏端子图.dwg"]

    assert page_roles["07 屏端子图.dwg"] == "supplemental"

    accepted = terminal_candidates[
        (terminal_candidates["sheet_id"] == terminal_sheet_id)
        & (terminal_candidates["status"] == "accepted")
    ]
    pair = pairs[pairs["sheet_id"] == terminal_sheet_id].iloc[0]

    assert set(accepted["value"].tolist()) == {"110", "210"}
    assert pair["left_value"] == "110"
    assert pair["right_value"] == "210"


def test_analyze_project_row_locks_terminal_strip_candidates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "21 左侧端子图1.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        msp.add_line((127.5, 45.0), (202.5, 45.0), dxfattribs={"layer": "CONNECT"})
        msp.add_text("21", dxfattribs={"insert": (150.998, 46.0), "height": 2.5, "layer": "TEXT"})
        msp.add_text("22", dxfattribs={"insert": (150.998, 41.0), "height": 2.5, "layer": "TEXT"})
        msp.add_text("20", dxfattribs={"insert": (150.998, 51.0), "height": 2.5, "layer": "TEXT"})
        msp.add_text("3-21n211", dxfattribs={"insert": (158.5, 46.0), "height": 2.5, "layer": "TEXT"})
        msp.add_text("3-21n212", dxfattribs={"insert": (158.5, 41.0), "height": 2.5, "layer": "TEXT"})
        msp.add_text("3-21n210", dxfattribs={"insert": (158.5, 51.0), "height": 2.5, "layer": "TEXT"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    terminal_candidates = pd.read_parquet(findings_dir / "terminal_candidates.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    pair = pairs.iloc[0]
    row_locked = terminal_candidates[terminal_candidates["rejection_reason"] == "terminal_row_locked"]

    assert pair["left_value"] == "21"
    assert pair["right_value"] == "211"
    assert pair["status"] == "review"
    assert "ambiguous candidate ordering" not in pair["rationale"]
    assert pair["confidence"] > 0.75
    assert set(row_locked["text"].tolist()) == {"22", "20", "3-21n212", "3-21n210"}


def test_analyze_project_supports_mirrored_right_terminal_strip_candidates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "23 右侧端子图1.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        msp.add_line((40.0, 48.5), (115.0, 48.5), dxfattribs={"layer": "CONNECT"})
        msp.add_text("1-21n132", dxfattribs={"insert": (66.0, 48.5), "height": 2.5, "layer": "TEXT"})
        msp.add_text("1-21n231", dxfattribs={"insert": (66.0, 43.5), "height": 2.5, "layer": "TEXT"})
        msp.add_text("20", dxfattribs={"insert": (88.5, 48.5), "height": 2.5, "layer": "TEXT"})
        msp.add_text("21", dxfattribs={"insert": (88.5, 43.5), "height": 2.5, "layer": "TEXT"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    terminal_candidates = pd.read_parquet(findings_dir / "terminal_candidates.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    pair = pairs.iloc[0]
    row_locked = terminal_candidates[terminal_candidates["rejection_reason"] == "terminal_row_locked"]

    assert pair["left_value"] == "132"
    assert pair["right_value"] == "20"
    assert pair["status"] == "review"
    assert "ambiguous candidate ordering" not in pair["rationale"]
    assert set(row_locked["text"].tolist()) == {"1-21n231", "21"}


def test_analyze_project_extracts_line_groups_from_insert_virtual_entities_on_component_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "19 元件接线图1.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        block = doc.blocks.new(name="COMP_ROW")
        block.add_line((20, 40), (80, 40), dxfattribs={"layer": "CONNECT"})
        block.add_text("101", dxfattribs={"insert": (10, 40), "height": 2.5, "layer": "TEXT"})
        block.add_text("202", dxfattribs={"insert": (90, 40), "height": 2.5, "layer": "TEXT"})
        msp.add_blockref("COMP_ROW", (0, 0))
        msp.add_text("19/24", dxfattribs={"insert": (300, 5), "height": 2.5, "layer": "BOARD"})
        msp.add_text("TOP", dxfattribs={"insert": (300, 120), "height": 2.5, "layer": "BOARD"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    line_groups = pd.read_parquet(findings_dir / "line_groups.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    component_sheet = pages[pages["filename"] == "19 元件接线图1.dwg"].iloc[0]
    component_sheet_id = component_sheet["sheet_id"]

    component_groups = line_groups[line_groups["sheet_id"] == component_sheet_id]
    component_pairs = pairs[pairs["sheet_id"] == component_sheet_id]

    assert component_sheet["audit_role"] == "supplemental"
    assert len(component_groups) == 1
    assert len(component_pairs) == 1
    assert component_pairs.iloc[0]["left_value"] == "101"
    assert component_pairs.iloc[0]["right_value"] == "202"


def test_analyze_project_does_not_expand_insert_virtual_entities_on_primary_page_by_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "04 回路图.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        block = doc.blocks.new(name="PRIMARY_BLOCK")
        block.add_line((20, 40), (80, 40), dxfattribs={"layer": "CONNECT"})
        block.add_text("101", dxfattribs={"insert": (10, 40), "height": 2.5, "layer": "TEXT"})
        block.add_text("202", dxfattribs={"insert": (90, 40), "height": 2.5, "layer": "TEXT"})
        msp.add_blockref("PRIMARY_BLOCK", (0, 0))
        msp.add_text("TOP", dxfattribs={"insert": (300, 120), "height": 2.5, "layer": "BOARD"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    line_groups = pd.read_parquet(findings_dir / "line_groups.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    primary_sheet = pages[pages["filename"] == "04 回路图.dwg"].iloc[0]
    primary_sheet_id = primary_sheet["sheet_id"]

    assert primary_sheet["audit_role"] == "primary"
    assert len(line_groups[line_groups["sheet_id"] == primary_sheet_id]) == 0
    assert len(pairs[pairs["sheet_id"] == primary_sheet_id]) == 0


def test_analyze_project_extracts_vertical_component_pairs_on_component_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "20 元件接线图2.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        block = doc.blocks.new(name="COMP_COL")
        block.add_line((60, 80), (60, 40), dxfattribs={"layer": "CONNECT"})
        block.add_text("101", dxfattribs={"insert": (60, 84), "height": 2.5, "layer": "TEXT"})
        block.add_text("202", dxfattribs={"insert": (60, 36), "height": 2.5, "layer": "TEXT"})
        msp.add_blockref("COMP_COL", (0, 0))
        msp.add_text("20/24", dxfattribs={"insert": (300, 5), "height": 2.5, "layer": "BOARD"})
        msp.add_text("TOP", dxfattribs={"insert": (300, 120), "height": 2.5, "layer": "BOARD"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    line_groups = pd.read_parquet(findings_dir / "line_groups.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    component_sheet = pages[pages["filename"] == "20 元件接线图2.dwg"].iloc[0]
    component_sheet_id = component_sheet["sheet_id"]
    component_groups = line_groups[line_groups["sheet_id"] == component_sheet_id]
    component_pairs = pairs[pairs["sheet_id"] == component_sheet_id]

    assert component_sheet["audit_role"] == "supplemental"
    assert len(component_groups) == 1
    assert component_groups.iloc[0]["orientation"] == "vertical"
    assert len(component_pairs) == 1
    assert component_pairs.iloc[0]["left_value"] == "101"
    assert component_pairs.iloc[0]["right_value"] == "202"


def test_analyze_project_prefers_component_suffix_values_on_vertical_component_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "20 元件接线图2.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        block = doc.blocks.new(name="COMP_COL")
        block.add_line((60, 80), (60, 40), dxfattribs={"layer": "CONNECT"})
        block.add_text("1", dxfattribs={"insert": (61.8, 83.8), "height": 2.5, "layer": "0"})
        block.add_text("2", dxfattribs={"insert": (61.9, 36.2), "height": 2.5, "layer": "0"})
        block.add_text("3-21CD43", dxfattribs={"insert": (56.5, 84.1), "height": 3.0, "layer": "TEXT"})
        block.add_text("3-21n419", dxfattribs={"insert": (56.5, 33.5), "height": 3.0, "layer": "TEXT"})
        msp.add_blockref("COMP_COL", (0, 0))
        msp.add_text("20/24", dxfattribs={"insert": (300, 5), "height": 2.5, "layer": "BOARD"})
        msp.add_text("TOP", dxfattribs={"insert": (300, 120), "height": 2.5, "layer": "BOARD"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    terminal_candidates = pd.read_parquet(findings_dir / "terminal_candidates.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    component_sheet = pages[pages["filename"] == "20 元件接线图2.dwg"].iloc[0]
    component_sheet_id = component_sheet["sheet_id"]

    component_candidates = terminal_candidates[terminal_candidates["sheet_id"] == component_sheet_id]
    component_pairs = pairs[pairs["sheet_id"] == component_sheet_id]

    assert any(
        row["status"] == "accepted" and row["value"] == "43"
        for _, row in component_candidates.iterrows()
    )
    assert any(
        row["status"] == "accepted" and row["value"] == "419"
        for _, row in component_candidates.iterrows()
    )
    assert any(
        row["rejection_reason"] == "superseded_by_derived_numeric" and row["text"] == "1"
        for _, row in component_candidates.iterrows()
    )
    assert any(
        row["rejection_reason"] == "superseded_by_derived_numeric" and row["text"] == "2"
        for _, row in component_candidates.iterrows()
    )
    assert component_pairs.iloc[0]["left_value"] == "43"
    assert component_pairs.iloc[0]["right_value"] == "419"


def test_analyze_project_rejects_virtual_fjl_internal_pin_numbers_on_component_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "20 元件接线图2.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        block = doc.blocks.new(name="FJL-25-2A_Mirror")
        block.add_line((60, 135), (60, 120), dxfattribs={"layer": "CONNECT"})
        block.add_text("1", dxfattribs={"insert": (61.8, 133.8), "height": 2.5, "layer": "0"})
        block.add_text("2", dxfattribs={"insert": (61.9, 121.2), "height": 2.5, "layer": "0"})
        block.add_text("LP3", dxfattribs={"insert": (60.2, 149.0), "height": 3.0, "layer": "TEXT"})
        block.add_text("FJL1-2.5/2A", dxfattribs={"insert": (56.5, 150.5), "height": 3.0, "layer": "TEXT"})
        msp.add_blockref("FJL-25-2A_Mirror", (0, 0))
        msp.add_text("20/24", dxfattribs={"insert": (300, 5), "height": 2.5, "layer": "BOARD"})
        msp.add_text("TOP", dxfattribs={"insert": (300, 120), "height": 2.5, "layer": "BOARD"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    terminal_candidates = pd.read_parquet(findings_dir / "terminal_candidates.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    component_sheet = pages[pages["filename"] == "20 元件接线图2.dwg"].iloc[0]
    component_sheet_id = component_sheet["sheet_id"]

    component_candidates = terminal_candidates[terminal_candidates["sheet_id"] == component_sheet_id]
    component_pairs = pairs[pairs["sheet_id"] == component_sheet_id]

    assert any(
        row["rejection_reason"] == "block_internal_pin_number" and row["text"] == "1"
        for _, row in component_candidates.iterrows()
    )
    assert any(
        row["rejection_reason"] == "block_internal_pin_number" and row["text"] == "2"
        for _, row in component_candidates.iterrows()
    )
    assert len(component_pairs) == 1
    assert component_pairs.iloc[0]["status"] == "discard"


def test_analyze_project_discards_horizontal_component_internal_pin_pairs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "19 元件接线图1.dwg").write_bytes(b"AC1018demo")

    fake_exe = tmp_path / "ODAFileConverter.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    def fake_convert(source: Path, target: Path, **_: object) -> None:
        doc = ezdxf.new("R2018")
        msp = doc.modelspace()
        block = doc.blocks.new(name="KK2P")
        block.add_line((60, 40), (85, 40), dxfattribs={"layer": "CONNECT"})
        block.add_text("2", dxfattribs={"insert": (61.5, 40), "height": 2.5, "layer": "0"})
        block.add_text("4", dxfattribs={"insert": (83.5, 40), "height": 2.5, "layer": "0"})
        msp.add_blockref("KK2P", (0, 0))
        msp.add_text("19/24", dxfattribs={"insert": (300, 5), "height": 2.5, "layer": "BOARD"})
        msp.add_text("TOP", dxfattribs={"insert": (300, 120), "height": 2.5, "layer": "BOARD"})
        doc.saveas(target)

    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda config: fake_exe)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", fake_convert)

    runner = CliRunner()
    output_dir = tmp_path / "artifacts"
    result = runner.invoke(app, ["analyze-project", "--input", str(project), "--output", str(output_dir)])
    assert result.exit_code == 0, result.output

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    findings_dir = Path(run_summary[0]["artifact_dir"]) / "findings"

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    component_sheet = pages[pages["filename"] == "19 元件接线图1.dwg"].iloc[0]
    component_sheet_id = component_sheet["sheet_id"]
    component_pairs = pairs[pairs["sheet_id"] == component_sheet_id]

    assert len(component_pairs) == 1
    assert component_pairs.iloc[0]["status"] == "discard"
    assert component_pairs.iloc[0]["rationale"] == "block_internal_pin_pair"
