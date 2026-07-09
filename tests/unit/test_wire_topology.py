import pandas as pd

from dwg_audit.audit.wire_topology import build_topology_shadow_report
from dwg_audit.audit.wire_topology import build_wire_topology_frames
from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.domain.models import TextItem


def _sheet() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="04.dwg",
        sheet_order=4,
        sheet_no="04",
        sheet_title="交流回路图1",
        sheet_category="二次原理图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=(0.0, 0.0, 100.0, 100.0),
        audit_disposition="audit_required",
    )


def _line(
    line_id: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=line_id,
        source_entity_type="LINE",
        layer="WIRE",
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        length=((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5,
        angle_deg=0.0 if start_y == end_y else 90.0,
        bbox_min_x=min(start_x, end_x),
        bbox_min_y=min(start_y, end_y),
        bbox_max_x=max(start_x, end_x),
        bbox_max_y=max(start_y, end_y),
    )


def _text(text_id: str, text: str, x: float, y: float) -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
        file_id="F1",
        handle=text_id,
        entity_type="TEXT",
        text=text,
        normalized_text=text,
        is_numeric_candidate=text.isdigit(),
        layer="TEXT",
        rotation_deg=0.0,
        height=2.5,
        insert_x=x,
        insert_y=y,
        bbox_min_x=x - 1.0,
        bbox_min_y=y - 1.0,
        bbox_max_x=x + 1.0,
        bbox_max_y=y + 1.0,
    )


def _block(block_id: str, x: float, y: float) -> BlockRecord:
    return BlockRecord(
        block_id=block_id,
        sheet_id="S1",
        file_id="F1",
        handle=block_id,
        name="BLOCK",
        layer="0",
        insert_x=x,
        insert_y=y,
        rotation_deg=0.0,
        attributes_json="{}",
    )


def _artifacts(
    *,
    lines: list[LineEntity],
    texts: list[TextItem] | None = None,
    blocks: list[BlockRecord] | None = None,
    line_groups: list[LineGroup] | None = None,
) -> ProjectArtifacts:
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="demo",
            project_name="demo",
            created_at="2026-07-08T00:00:00Z",
            tool_version="0.1.0",
            input_root="demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[
                SourceFileRecord(
                    file_id="F1",
                    path="04.dwg",
                    filename="04.dwg",
                    ext=".dwg",
                    sha256="x",
                    size_bytes=1,
                    sheet_order=4,
                    detected_page_no="04",
                    detected_from="filename",
                    sheet_title="交流回路图1",
                    sheet_category="二次原理图",
                    skip_reason=None,
                    valid_dwg_header=True,
                )
            ],
        ),
        pages=[_sheet()],
        terminal_strips=[],
        project_root="demo",
    )
    return ProjectArtifacts(
        scan=scan,
        lines=lines,
        texts=texts or [],
        blocks=blocks or [],
        line_groups=line_groups or [],
    )


def _config() -> dict:
    return {
        "geometry": {"horizontal_angle_tolerance_deg": 2.0},
        "topology": {
            "junction_snap_tolerance": 1.8,
            "cross_axis_tolerance": 2.5,
            "bridge_gap_tolerance": 18.0,
            "inline_text_bridge_gap": 18.0,
            "block_span_bridge_gap": 24.0,
            "text_touch_tolerance": 4.0,
            "merge_crossings": False,
        },
    }


def test_build_wire_topology_frames_merges_touching_endpoints() -> None:
    artifacts = _artifacts(
        lines=[
            _line("L1", 10.0, 20.0, 20.0, 20.0),
            _line("L2", 20.0, 20.0, 30.0, 20.0),
        ]
    )

    junctions, networks, summary = build_wire_topology_frames(artifacts, config=_config())

    assert summary["wire_network_count"] == 1
    assert len(networks) == 1
    assert set(networks.iloc[0]["member_line_ids"]) == {"L1", "L2"}
    assert "endpoint_merge" in set(junctions["kind"])
    assert len(networks.iloc[0]["open_endpoint_junctions"]) == 2


def test_build_wire_topology_frames_merges_t_cross() -> None:
    artifacts = _artifacts(
        lines=[
            _line("L1", 10.0, 20.0, 30.0, 20.0),
            _line("L2", 20.0, 20.0, 20.0, 30.0),
        ]
    )

    junctions, networks, _ = build_wire_topology_frames(artifacts, config=_config())

    assert len(networks) == 1
    assert "t_cross" in set(junctions["kind"])


def test_build_wire_topology_frames_keeps_crossing_unmerged() -> None:
    artifacts = _artifacts(
        lines=[
            _line("L1", 10.0, 20.0, 30.0, 20.0),
            _line("L2", 20.0, 10.0, 20.0, 30.0),
        ]
    )

    junctions, networks, _ = build_wire_topology_frames(artifacts, config=_config())

    assert len(networks) == 2
    assert "crossing_observation" in set(junctions["kind"])


def test_build_wire_topology_frames_bridges_inline_text_gap() -> None:
    artifacts = _artifacts(
        lines=[
            _line("L1", 10.0, 20.0, 20.0, 20.0),
            _line("L2", 25.0, 20.0, 35.0, 20.0),
        ],
        texts=[_text("T1", "105", 22.5, 20.0)],
    )

    _, networks, _ = build_wire_topology_frames(artifacts, config=_config())

    assert len(networks) == 1
    assert networks.iloc[0]["bridged_gaps"][0]["reason"] == "inline_text"
    assert networks.iloc[0]["touched_text_ids"] == ["T1"]


def test_build_wire_topology_frames_bridges_block_gap() -> None:
    artifacts = _artifacts(
        lines=[
            _line("L1", 10.0, 20.0, 20.0, 20.0),
            _line("L2", 26.0, 20.0, 36.0, 20.0),
        ],
        blocks=[_block("B1", 23.0, 20.0)],
    )

    _, networks, _ = build_wire_topology_frames(artifacts, config=_config())

    assert len(networks) == 1
    assert networks.iloc[0]["bridged_gaps"][0]["reason"] == "block_span"


def test_build_wire_topology_frames_keeps_double_network_isolation() -> None:
    artifacts = _artifacts(
        lines=[
            _line("L1", 10.0, 20.0, 20.0, 20.0),
            _line("L2", 20.0, 20.0, 30.0, 20.0),
            _line("L3", 60.0, 40.0, 70.0, 40.0),
            _line("L4", 70.0, 40.0, 80.0, 40.0),
        ]
    )

    _, networks, _ = build_wire_topology_frames(artifacts, config=_config())

    assert len(networks) == 2


def _build_shadow_payload(
    text_assignments: list[dict[str, object]],
    *,
    bridged_gaps: list[dict[str, object]] | None = None,
    open_endpoint_junctions: list[str] | None = None,
    open_junction_coords: list[tuple[float, float]] | None = None,
    pair_value: str = "101",
    line_group_start_x: float = 40.0,
    line_group_end_x: float = 60.0,
    line_group_y: float = 20.0,
    missing_side: str = "left",
) -> dict[str, object]:
    left_value = None if missing_side == "left" else pair_value
    right_value = pair_value if missing_side == "left" else None
    left_text_id = None if missing_side == "left" else "T1"
    right_text_id = "T1" if missing_side == "left" else None
    issues = pd.DataFrame(
        [
            {
                "issue_id": "I1",
                "rule_id": "R-PAIR-MISSING-SIDE",
                "pair_id": "P1",
                "line_group_id": "G1",
                "left_value": left_value,
                "right_value": right_value,
                "filename": "04.dwg",
                "sheet_no": "04",
                "sheet_order": 4,
                "evidence": {"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4},
            }
        ]
    )
    pairs = pd.DataFrame(
        [
            {
                "pair_id": "P1",
                "left_text_id": left_text_id,
                "right_text_id": right_text_id,
            }
        ]
    )
    junction_ids = open_endpoint_junctions or ["J1", "J2"]
    junction_coords = open_junction_coords or [(30.0, line_group_y), (70.0, line_group_y)]
    wire_junctions = pd.DataFrame(
        [
            {
                "junction_id": junction_id,
                "coord": [coord[0], coord[1]],
                "kind": "endpoint",
                "member_line_ids": ["Lx"],
            }
            for junction_id, coord in zip(junction_ids, junction_coords)
        ]
    )
    line_groups = pd.DataFrame(
        [
            {
                "line_group_id": "G1",
                "start_x": line_group_start_x,
                "start_y": line_group_y,
                "end_x": line_group_end_x,
                "end_y": line_group_y,
                "row_band_id": "RB1",
            }
        ]
    )
    networks = pd.DataFrame(
        [
            {
                "network_id": "N1",
                "line_group_ids": ["G1"],
                "open_endpoint_junctions": junction_ids,
                "bridged_gaps": bridged_gaps or [{"gap": 5.0, "reason": "inline_text"}],
                "touched_text_ids": [row["text_id"] for row in text_assignments],
            }
        ]
    )
    frame = pd.DataFrame(text_assignments)
    return build_topology_shadow_report(
        issues_frame=issues,
        pairs_frame=pairs,
        line_groups_frame=line_groups,
        wire_networks_frame=networks,
        wire_junctions_frame=wire_junctions,
        text_assignments_frame=frame,
    )


def test_build_topology_shadow_report_marks_recoverable_network() -> None:
    payload = _build_shadow_payload(
        [
            {"text_id": "T1", "text": "101", "is_numeric_like": True, "assignment_kind": "pair_endpoint"},
            {
                "text_id": "T2",
                "text": "1ID1",
                "is_numeric_like": False,
                "assignment_kind": "unexplained",
                "insert_x": 34.0,
                "insert_y": 20.0,
            },
        ]
    )

    assert payload["candidate_issue_count"] == 1
    assert payload["recoverable_issue_count"] == 1
    assert payload["issues"][0]["topology_recoverable"] is True
    assert payload["issues"][0]["topology_reason"] == "topology_recoverable_external_endpoint_present"
    assert payload["issues"][0]["text_role_counts"] == {"external_endpoint_candidate": 1}
    assert payload["issues"][0]["branch_local_status"] == "unique_candidate"
    assert payload["issues"][0]["branch_local_candidates"][0]["text"] == "1ID1"
    assert payload["issues"][0]["branch_local_candidates"][0]["anchored_open_endpoint_count"] == 1


def test_build_topology_shadow_report_marks_scoped_local_cluster_not_recoverable() -> None:
    payload = _build_shadow_payload(
        [
            {"text_id": "T1", "text": "101", "is_numeric_like": True, "assignment_kind": "pair_endpoint"},
            {"text_id": "T2", "text": "103", "is_numeric_like": True, "assignment_kind": "structured_mapping_endpoint"},
            {
                "text_id": "T3",
                "text": "1-2n",
                "is_numeric_like": False,
                "assignment_kind": "rejected_candidate",
                "candidate_channel": "noise_channel",
                "rejection_reason": "not_numeric",
                "explain_reason": "not_numeric",
                "insert_x": 50.0,
                "insert_y": 25.0,
            },
            {
                "text_id": "T4",
                "text": "1-2QD12",
                "is_numeric_like": False,
                "assignment_kind": "structured_mapping_endpoint",
                "insert_x": 34.0,
                "insert_y": 20.0,
            },
        ]
    )

    assert payload["recoverable_issue_count"] == 0
    assert payload["issues"][0]["topology_recoverable"] is False
    assert payload["issues"][0]["topology_reason"] == "scoped_local_number_cluster"
    assert payload["issues"][0]["text_role_counts"]["scoped_prefix"] == 1
    assert payload["issues"][0]["branch_local_status"] == "unique_candidate"
    assert payload["issues"][0]["branch_local_candidates"][0]["text"] == "1-2QD12"


def test_build_topology_shadow_report_marks_body_port_cluster_not_recoverable() -> None:
    payload = _build_shadow_payload(
        [
            {"text_id": "T1", "text": "14", "is_numeric_like": True, "assignment_kind": "pair_endpoint", "paired_value": "14"},
            {
                "text_id": "T2",
                "text": "1KLP1",
                "is_numeric_like": False,
                "assignment_kind": "rejected_candidate",
                "candidate_channel": "noise_channel",
                "rejection_reason": "not_numeric",
                "explain_reason": "not_numeric",
                "insert_x": 48.0,
                "insert_y": 20.0,
            },
            {
                "text_id": "T3",
                "text": "114",
                "is_numeric_like": True,
                "assignment_kind": "structured_mapping_endpoint",
                "insert_x": 52.0,
                "insert_y": 20.0,
            },
            {
                "text_id": "T4",
                "text": "1",
                "is_numeric_like": True,
                "assignment_kind": "rejected_candidate",
                "candidate_channel": "noise_channel",
                "rejection_reason": "single_char_layer_filtered",
                "explain_reason": "single_char_layer_filtered",
                "insert_x": 49.0,
                "insert_y": 20.0,
            },
            {
                "text_id": "T5",
                "text": "1FA",
                "is_numeric_like": False,
                "assignment_kind": "rejected_candidate",
                "candidate_channel": "noise_channel",
                "rejection_reason": "not_numeric",
                "explain_reason": "not_numeric",
                "insert_x": 47.0,
                "insert_y": 20.0,
            },
        ]
    )

    assert payload["recoverable_issue_count"] == 0
    assert payload["issues"][0]["topology_recoverable"] is False
    assert payload["issues"][0]["topology_reason"] == "body_port_cluster"
    assert payload["issues"][0]["text_role_counts"]["component_body"] == 2
    assert payload["issues"][0]["branch_local_status"] == "context_only"
    assert [item["text"] for item in payload["issues"][0]["branch_local_contexts"]] == [
        "1",
        "1KLP1",
        "1FA",
    ]


def test_build_topology_shadow_report_requires_more_than_single_port_noise() -> None:
    payload = _build_shadow_payload(
        [
            {"text_id": "T1", "text": "105", "is_numeric_like": True, "assignment_kind": "pair_endpoint"},
            {
                "text_id": "T2",
                "text": "2",
                "is_numeric_like": True,
                "assignment_kind": "rejected_candidate",
                "candidate_channel": "noise_channel",
                "rejection_reason": "single_char_layer_filtered",
                "explain_reason": "single_char_layer_filtered",
                "insert_x": 48.0,
                "insert_y": 20.0,
            },
        ]
    )

    assert payload["recoverable_issue_count"] == 0
    assert payload["issues"][0]["topology_recoverable"] is False
    assert payload["issues"][0]["topology_reason"] == "no_additional_topology_signal"
    assert payload["issues"][0]["branch_local_status"] == "no_candidate"


def test_build_topology_shadow_report_marks_ambiguous_same_row_candidates() -> None:
    payload = _build_shadow_payload(
        [
            {"text_id": "T1", "text": "224", "is_numeric_like": True, "assignment_kind": "pair_endpoint"},
            {
                "text_id": "T2",
                "text": "1-4QD24",
                "is_numeric_like": False,
                "assignment_kind": "structured_mapping_endpoint",
                "insert_x": 34.0,
                "insert_y": 20.5,
            },
            {
                "text_id": "T3",
                "text": "1-4QD5",
                "is_numeric_like": False,
                "assignment_kind": "rejected_candidate",
                "candidate_channel": "noise_channel",
                "rejection_reason": "not_numeric",
                "explain_reason": "not_numeric",
                "insert_x": 28.0,
                "insert_y": 20.2,
            },
        ],
        open_junction_coords=[(31.0, 20.0), (70.0, 20.0)],
    )

    assert payload["issues"][0]["branch_local_status"] == "ambiguous_candidates"
    assert payload["issues"][0]["branch_local_candidate_count"] == 2
    assert [item["text"] for item in payload["issues"][0]["branch_local_candidates"]] == [
        "1-4QD5",
        "1-4QD24",
    ]


def test_build_topology_shadow_report_prefers_open_endpoint_anchored_candidate() -> None:
    payload = _build_shadow_payload(
        [
            {"text_id": "T1", "text": "224", "is_numeric_like": True, "assignment_kind": "pair_endpoint"},
            {
                "text_id": "T2",
                "text": "1-4QD24",
                "is_numeric_like": False,
                "assignment_kind": "structured_mapping_endpoint",
                "insert_x": 34.0,
                "insert_y": 20.5,
            },
            {
                "text_id": "T3",
                "text": "1-4QD5",
                "is_numeric_like": False,
                "assignment_kind": "rejected_candidate",
                "candidate_channel": "noise_channel",
                "rejection_reason": "not_numeric",
                "explain_reason": "not_numeric",
                "insert_x": -5.0,
                "insert_y": 20.2,
            },
        ],
        line_group_start_x=40.0,
        line_group_end_x=100.0,
        open_junction_coords=[(-5.0, 20.0), (110.0, 20.0)],
    )

    assert payload["issues"][0]["branch_local_status"] == "unique_candidate"
    assert payload["issues"][0]["branch_local_reason"] == "single_same_side_open_endpoint_anchored_candidate"
    assert [item["text"] for item in payload["issues"][0]["branch_local_candidates"]] == ["1-4QD5"]
