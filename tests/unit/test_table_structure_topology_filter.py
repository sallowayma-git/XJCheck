from dwg_audit.audit.geometry_graph import build_geometry_graph_frames
from dwg_audit.audit.wire_topology import build_wire_topology_frames
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord


def _line(line_id: str, x1: float, y1: float, x2: float, y2: float) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=line_id,
        source_entity_type="LINE",
        layer="WIRE",
        start_x=x1,
        start_y=y1,
        end_x=x2,
        end_y=y2,
        length=((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5,
        angle_deg=0.0 if y1 == y2 else 90.0,
        bbox_min_x=min(x1, x2),
        bbox_min_y=min(y1, y2),
        bbox_max_x=max(x1, x2),
        bbox_max_y=max(y1, y2),
    )


def _artifacts() -> ProjectArtifacts:
    sheet = SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="generic.dwg",
        sheet_order=1,
        sheet_no="01",
        sheet_title="generic",
        sheet_category="二次原理图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=(-10.0, -10.0, 100.0, 100.0),
        audit_disposition="audit_required",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="generic",
            project_name="generic",
            created_at="2026-07-11T00:00:00Z",
            tool_version="0.1.0",
            input_root="generic",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
        ),
        pages=[sheet],
        terminal_strips=[],
        project_root="generic",
    )
    return ProjectArtifacts(
        scan=scan,
        lines=[
            _line("GRID-H", 0.0, 0.0, 20.0, 0.0),
            _line("GRID-V", 10.0, -5.0, 10.0, 5.0),
            _line("WIRE-LEAD", 30.0, 0.0, 40.0, 0.0),
        ],
    )


def _config() -> dict:
    return {
        "geometry": {"horizontal_angle_tolerance_deg": 2.0},
        "topology": {
            "junction_snap_tolerance": 0.2,
            "geometry_graph_asserted_snap_tolerance": 0.2,
            "merge_crossings": True,
        },
    }


def test_excluded_table_structure_lines_are_filtered_from_shadow_topologies() -> None:
    artifacts = _artifacts()

    _, default_edges, _, default_geometry = build_geometry_graph_frames(
        artifacts, config=_config()
    )
    _, default_networks, default_wire = build_wire_topology_frames(
        artifacts, config=_config()
    )
    _, edges, _, geometry = build_geometry_graph_frames(
        artifacts,
        config=_config(),
        excluded_line_ids={"GRID-H", "GRID-V"},
    )
    _, networks, wire = build_wire_topology_frames(
        artifacts,
        config=_config(),
        excluded_line_ids={"GRID-H", "GRID-V"},
    )

    assert set(default_edges["source_line_id"]) == {"GRID-H", "GRID-V", "WIRE-LEAD"}
    assert default_geometry["geometry_source_line_count"] == 3
    assert default_wire["wire_network_count"] == 2
    assert {line_id for row in default_networks["member_line_ids"] for line_id in row} == {
        "GRID-H",
        "GRID-V",
        "WIRE-LEAD",
    }

    assert set(edges["source_line_id"]) == {"WIRE-LEAD"}
    assert geometry["geometry_source_line_count"] == 1
    assert len(networks) == 1
    assert networks.iloc[0]["member_line_ids"] == ["WIRE-LEAD"]
    assert wire["wire_network_count"] == 1


def test_none_exclusion_preserves_default_output() -> None:
    artifacts = _artifacts()

    default_geometry = build_geometry_graph_frames(artifacts, config=_config())
    none_geometry = build_geometry_graph_frames(
        artifacts, config=_config(), excluded_line_ids=None
    )
    default_wire = build_wire_topology_frames(artifacts, config=_config())
    none_wire = build_wire_topology_frames(
        artifacts, config=_config(), excluded_line_ids=None
    )

    for default, explicit_none in zip(default_geometry, none_geometry):
        if hasattr(default, "equals"):
            assert default.equals(explicit_none)
        else:
            assert default == explicit_none
    for default, explicit_none in zip(default_wire, none_wire):
        if hasattr(default, "equals"):
            assert default.equals(explicit_none)
        else:
            assert default == explicit_none
