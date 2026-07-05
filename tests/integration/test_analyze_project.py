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
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    pages = pd.read_parquet(findings_dir / "pages.parquet")
    line_groups = pd.read_parquet(findings_dir / "line_groups.parquet")
    pairs = pd.read_parquet(findings_dir / "pairs.parquet")

    page_roles = {row["filename"]: row["audit_role"] for _, row in pages.iterrows()}
    page_primary = {row["filename"]: bool(row["is_primary_audit_candidate"]) for _, row in pages.iterrows()}
    sheet_by_file = {row["filename"]: row["sheet_id"] for _, row in pages.iterrows()}

    assert page_roles["04 回路图.dwg"] == "primary"
    assert page_primary["04 回路图.dwg"] is True
    assert page_roles["07 屏端子图.dwg"] == "supplemental"
    assert page_primary["07 屏端子图.dwg"] is True
    assert page_roles["08 封面.dwg"] == "skip"
    assert page_primary["08 封面.dwg"] is False

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
    page_primary = {row["filename"]: bool(row["is_primary_audit_candidate"]) for _, row in pages.iterrows()}
    sheet_by_file = {row["filename"]: row["sheet_id"] for _, row in pages.iterrows()}

    assert page_roles["04 回路图.dwg"] == "primary"
    assert page_roles["17 背板接线图1.dwg"] == "supplemental"
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
