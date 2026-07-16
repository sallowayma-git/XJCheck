import json
from pathlib import Path

import pandas as pd

from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.report.artifacts import write_project_artifacts


def _artifacts(lines: list[LineEntity]) -> ProjectArtifacts:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/terminal.dwg",
        filename="terminal.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=1,
        detected_page_no="01",
        detected_from="filename",
        sheet_title="端子表",
        sheet_category="屏端子图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="table-artifact",
            project_name="table-artifact",
            created_at="2026-07-11T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[],
            project_name_sources={},
            warnings=[],
        ),
        pages=[
            SheetRecord(
                "S0001", "F0001", "terminal.dwg", 1, "01", "端子表",
                "屏端子图", "primary", "filename", True,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    return ProjectArtifacts(scan=scan, lines=lines)


def _line(line_id: str, start: tuple[float, float], end: tuple[float, float]) -> LineEntity:
    min_x, max_x = sorted((start[0], end[0]))
    min_y, max_y = sorted((start[1], end[1]))
    return LineEntity(
        line_id=line_id,
        sheet_id="S0001",
        file_id="F0001",
        handle=line_id,
        source_entity_type="LINE",
        layer="0",
        start_x=start[0],
        start_y=start[1],
        end_x=end[0],
        end_y=end[1],
        length=max(max_x - min_x, max_y - min_y),
        angle_deg=0.0 if start[1] == end[1] else 90.0,
        bbox_min_x=min_x,
        bbox_min_y=min_y,
        bbox_max_x=max_x,
        bbox_max_y=max_y,
    )


def test_table_structure_profiles_artifact_is_empty_when_no_verified_grid(tmp_path: Path) -> None:
    project_dir = write_project_artifacts(
        _artifacts([_line("L1", (0.0, 0.0), (10.0, 0.0))]), tmp_path
    )
    findings_dir = project_dir / "findings"
    frame = pd.read_parquet(findings_dir / "table_structure_profiles.parquet")
    payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    assert frame.empty
    assert "structural_line_ids" in frame.columns
    assert payload["table_structure_summary"]["profile_count"] == 0
    assert "table_structure_profiles.parquet" in payload["artifacts"]["findings"]


def test_table_structure_profiles_artifact_persists_verified_grid(tmp_path: Path) -> None:
    horizontal = [
        _line(f"H{index}", (0.0, y), (20.0, y))
        for index, y in enumerate((0.0, 10.0, 20.0), start=1)
    ]
    vertical = [
        _line(f"V{index}", (x, 0.0), (x, 20.0))
        for index, x in enumerate((0.0, 10.0, 20.0), start=1)
    ]
    project_dir = write_project_artifacts(_artifacts(horizontal + vertical), tmp_path)
    findings_dir = project_dir / "findings"
    frame = pd.read_parquet(findings_dir / "table_structure_profiles.parquet")
    payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    assert len(frame) == 1
    assert frame.loc[0, "sheet_id"] == "S0001"
    assert json.loads(frame.loc[0, "structural_line_ids"]) == ["H1", "H2", "H3", "V1", "V2", "V3"]
    assert json.loads(frame.loc[0, "row_axes"]) == [0.0, 10.0, 20.0]
    assert payload["table_structure_summary"] == {
        "schema_version": "table-structure-profile-summary-v1",
        "profile_count": 1,
        "sheet_count": 1,
        "profiles_by_sheet": {"S0001": 1},
        "structural_line_count": 6,
        "profiles_with_header_scope": 1,
        "reason_code_counts": {
            "GEOMETRY_COMPLETE_GRID": 1,
            "GRID_AXES_VERIFIED": 1,
            "STRUCTURAL_LINES_ONLY": 1,
        },
        "execution_contract": "Profiles are audit metadata; they do not alter legacy outputs or topology connectivity by themselves.",
    }


def test_verified_table_mapping_grid_is_excluded_only_from_v2_topology_inputs(tmp_path: Path) -> None:
    horizontal = [_line(f"H{index}", (0.0, y), (20.0, y)) for index, y in enumerate((0.0, 10.0, 20.0), start=1)]
    vertical = [_line(f"V{index}", (x, 0.0), (x, 20.0)) for index, x in enumerate((0.0, 10.0, 20.0), start=1)]
    classification = PageClassification(
        sheet_id="S0001",
        page_type="表格型图",
        page_subtype="three_column_candidate",
        page_type_confidence=0.82,
        table_like=True,
        grid_heavy=False,
        route_target="TableExtractor",
        capabilities=("TableMapping",),
    )

    project_dir = write_project_artifacts(
        _artifacts(horizontal + vertical),
        tmp_path,
        page_classifications={"S0001": classification},
    )
    findings_dir = project_dir / "findings"
    payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    assert pd.read_parquet(findings_dir / "geometry_shadow_edges.parquet").empty
    assert pd.read_parquet(findings_dir / "wire_networks.parquet").empty
    assert payload["table_structure_topology_exclusion"]["structural_line_ids"] == [
        "H1", "H2", "H3", "V1", "V2", "V3"
    ]


def test_verified_terminal_grid_is_excluded_from_v2_topology_inputs(tmp_path: Path) -> None:
    """TerminalGrid pages with complete grids exclude structural lines even without TableMapping."""
    horizontal = [_line(f"H{index}", (0.0, y), (20.0, y)) for index, y in enumerate((0.0, 10.0, 20.0), start=1)]
    vertical = [_line(f"V{index}", (x, 0.0), (x, 20.0)) for index, x in enumerate((0.0, 10.0, 20.0), start=1)]
    classification = PageClassification(
        sheet_id="S0001",
        page_type="terminal",
        page_subtype=None,
        page_type_confidence=0.8,
        table_like=False,
        grid_heavy=False,
        route_target="TerminalDiagramExtractor",
        capabilities=("TerminalGrid", "WireTopology"),
    )

    project_dir = write_project_artifacts(
        _artifacts(horizontal + vertical),
        tmp_path,
        page_classifications={"S0001": classification},
    )
    findings_dir = project_dir / "findings"
    payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    assert payload["table_structure_topology_exclusion"]["structural_line_count"] == 6
    assert set(payload["table_structure_topology_exclusion"]["structural_line_ids"]) == {
        "H1", "H2", "H3", "V1", "V2", "V3"
    }
    assert pd.read_parquet(findings_dir / "geometry_shadow_edges.parquet").empty

