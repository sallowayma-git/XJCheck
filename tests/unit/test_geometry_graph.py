import pandas as pd

from dwg_audit.audit.geometry_graph import build_geometry_graph_frames
from dwg_audit.audit.geometry_graph import build_geometry_observation_frame
from dwg_audit.audit.geometry_graph import build_pair_geometry_shadow_frame
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem


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


def _artifacts(lines: list[LineEntity]) -> ProjectArtifacts:
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
        audit_area_bbox=(-100.0, -100.0, 200.0, 200.0),
        audit_disposition="audit_required",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="generic",
            project_name="generic",
            created_at="2026-07-10T00:00:00Z",
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
    return ProjectArtifacts(scan=scan, lines=lines)


def _config(*, merge_crossings: bool = False, snap: float = 0.2) -> dict:
    return {
        "geometry": {"horizontal_angle_tolerance_deg": 2.0},
        "topology": {
            "junction_snap_tolerance": snap,
            "geometry_graph_asserted_snap_tolerance": snap,
            "merge_crossings": merge_crossings,
        },
    }


def test_geometry_graph_splits_t_intersection_into_real_edges() -> None:
    artifacts = _artifacts(
        [_line("L1", 0.0, 0.0, 10.0, 0.0), _line("L2", 5.0, 0.0, 5.0, 5.0)]
    )

    nodes, edges, components, summary = build_geometry_graph_frames(
        artifacts, config=_config()
    )

    assert len(edges) == 3
    assert len(components) == 1
    assert summary["split_source_line_count"] == 1
    junction = nodes.loc[nodes["degree"] == 3].iloc[0]
    assert junction["kind"] == "t_cross"
    assert components.iloc[0]["degree_histogram"] == {"1": 3, "3": 1}


def test_geometry_graph_keeps_unasserted_crossing_disconnected() -> None:
    artifacts = _artifacts(
        [_line("L1", 0.0, 5.0, 10.0, 5.0), _line("L2", 5.0, 0.0, 5.0, 10.0)]
    )

    _, edges, components, _ = build_geometry_graph_frames(artifacts, config=_config())

    assert len(edges) == 2
    assert len(components) == 2
    assert all(histogram == {"1": 2} for histogram in components["degree_histogram"])


def test_geometry_observations_assert_collinear_overlap_without_legacy_union() -> None:
    artifacts = _artifacts(
        [_line("L1", 0.0, 0.0, 10.0, 0.0), _line("L2", 5.0, 0.0, 15.0, 0.0)]
    )
    nodes, edges, components, _ = build_geometry_graph_frames(artifacts, config=_config())

    observations, _ = build_geometry_observation_frame(
        artifacts, nodes, edges, components, config=_config()
    )

    overlap = observations.loc[observations["observation_kind"] == "overlap"]
    assert len(overlap) == 1
    assert overlap.iloc[0]["state"] == "ASSERTED"
    assert overlap.iloc[0]["source_line_ids"] == ["L1", "L2"]
    assert overlap.iloc[0]["reason_code"] == "asserted_collinear_overlap_v1"
    assert len(components) == 2


def test_near_collinear_lines_are_not_asserted_as_direct_overlap() -> None:
    artifacts = _artifacts(
        [_line("L1", 0.0, 0.0, 10.0, 0.0), _line("L2", 5.0, 0.01, 15.0, 0.01)]
    )
    nodes, edges, components, _ = build_geometry_graph_frames(
        artifacts, config=_config(snap=0.2)
    )

    observations, _ = build_geometry_observation_frame(
        artifacts, nodes, edges, components, config=_config(snap=0.2)
    )

    assert observations.loc[observations["observation_kind"] == "overlap"].empty
    assert len(components) == 2


def test_inline_text_is_possible_evidence_and_does_not_merge_components() -> None:
    artifacts = _artifacts(
        [_line("L1", 0.0, 0.0, 10.0, 0.0), _line("L2", 15.0, 0.0, 25.0, 0.0)]
    )
    artifacts.texts = [
        TextItem(
            "T1", "S1", "F1", "H1", "TEXT", "X", "X", False, "WIRE",
            0.0, 2.0, 12.0, 0.0, 10.5, -1.0, 14.0, 1.0,
        )
    ]
    nodes, edges, components, _ = build_geometry_graph_frames(artifacts, config=_config())

    observations, _ = build_geometry_observation_frame(
        artifacts, nodes, edges, components, config=_config()
    )

    spans = observations.loc[observations["observation_kind"] == "inline_span_candidate"]
    assert len(spans) == 1
    assert spans.iloc[0]["state"] == "POSSIBLE"
    assert spans.iloc[0]["evidence_ids"] == ["T1"]
    assert spans.iloc[0]["requires_review"]
    assert len(components) == 2


def test_geometry_graph_can_assert_and_split_configured_crossing() -> None:
    artifacts = _artifacts(
        [_line("L1", 0.0, 5.0, 10.0, 5.0), _line("L2", 5.0, 0.0, 5.0, 10.0)]
    )

    nodes, edges, components, _ = build_geometry_graph_frames(
        artifacts, config=_config(merge_crossings=True)
    )

    assert len(edges) == 4
    assert len(components) == 1
    assert nodes.loc[nodes["degree"] == 4].iloc[0]["kind"] == "crossing"


def test_geometry_graph_uses_degenerate_polyline_as_connection_marker() -> None:
    marker_left = _line("M1", 4.75, 5.0, 5.25, 5.0)
    marker_left.handle = "DOT:0"
    marker_left.source_entity_type = "LWPOLYLINE"
    marker_right = _line("M2", 5.25, 5.0, 4.75, 5.0)
    marker_right.handle = "DOT:1"
    marker_right.source_entity_type = "LWPOLYLINE"
    artifacts = _artifacts(
        [
            _line("L1", 0.0, 5.0, 10.0, 5.0),
            _line("L2", 5.0, 0.0, 5.0, 10.0),
            marker_left,
            marker_right,
        ]
    )

    nodes, edges, components, summary = build_geometry_graph_frames(
        artifacts, config=_config()
    )

    assert len(edges) == 4
    assert len(components) == 1
    assert summary["geometry_source_line_count"] == 2
    junction = nodes.loc[nodes["degree"] == 4].iloc[0]
    assert junction["kind"] == "connection_marker"
    assert junction["evidence_line_ids"] == ["M1", "M2"]


def test_geometry_graph_snaps_across_spatial_bucket_boundary() -> None:
    artifacts = _artifacts(
        [_line("L1", 0.0, 0.0, 1.99, 0.0), _line("L2", 2.01, 0.0, 4.0, 0.0)]
    )

    nodes, _, components, _ = build_geometry_graph_frames(
        artifacts, config=_config(snap=1.0)
    )

    assert len(components) == 1
    merged = nodes.loc[nodes["source_line_ids"].apply(lambda ids: len(ids) == 2)].iloc[0]
    assert merged["kind"] == "endpoint_merge"
    assert max(item["distance"] for item in merged["snap_offsets"]) == 0.01


def test_geometry_graph_topology_is_translation_invariant() -> None:
    base = _artifacts(
        [_line("L1", 0.0, 0.0, 10.0, 0.0), _line("L2", 5.0, 0.0, 5.0, 5.0)]
    )
    shifted = _artifacts(
        [_line("L1", 30.0, 40.0, 40.0, 40.0), _line("L2", 35.0, 40.0, 35.0, 45.0)]
    )

    _, base_edges, base_components, _ = build_geometry_graph_frames(base, config=_config())
    _, shifted_edges, shifted_components, _ = build_geometry_graph_frames(
        shifted, config=_config()
    )

    assert sorted(base_edges.groupby("source_line_id").size()) == sorted(
        shifted_edges.groupby("source_line_id").size()
    )
    pd.testing.assert_series_equal(
        base_components.iloc[0][["degree_histogram", "total_length"]],
        shifted_components.iloc[0][["degree_histogram", "total_length"]],
        check_names=False,
    )


def test_pair_geometry_shadow_reports_context_without_overriding_pair() -> None:
    artifacts = _artifacts(
        [
            _line("L1", 0.0, 0.0, 10.0, 0.0),
            _line("L2", 20.0, 0.0, 30.0, 0.0),
        ]
    )
    artifacts.line_groups = [
        LineGroup("G1", "S1", "F1", 0.0, 0.0, 10.0, 0.0, 10.0, 0.9, ["L1"], ["WIRE"]),
        LineGroup("G2", "S1", "F1", 0.0, 0.0, 30.0, 0.0, 30.0, 0.9, ["L1", "L2"], ["WIRE"]),
    ]
    artifacts.pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "102", 0.9, "pass", "legacy"),
        Pair("P2", "G2", "S1", "F1", "PC2", "201", None, 0.4, "review", "legacy"),
    ]
    _, _, components, _ = build_geometry_graph_frames(artifacts, config=_config())

    frame, summary = build_pair_geometry_shadow_frame(artifacts, components)

    assert frame.set_index("pair_id").loc["P1", "geometry_context_status"] == "unique_geometry_component"
    assert frame.set_index("pair_id").loc["P2", "geometry_context_status"] == "multiple_geometry_components"
    assert artifacts.pairs[1].status == "review"
    assert summary["ordinary_geometry_context_status_counts"] == {
        "multiple_geometry_components": 1,
        "unique_geometry_component": 1,
    }


def test_geometry_observations_keep_asserted_possible_and_rejected_states() -> None:
    artifacts = _artifacts(
        [
            _line("T1", 0.0, 30.0, 10.0, 30.0),
            _line("T2", 5.0, 30.0, 5.0, 35.0),
            _line("G1", 0.0, 10.0, 10.0, 10.0),
            _line("G2", 15.0, 10.0, 25.0, 10.0),
            _line("C1", 40.0, 5.0, 50.0, 5.0),
            _line("C2", 45.0, 0.0, 45.0, 10.0),
        ]
    )
    nodes, edges, components, _ = build_geometry_graph_frames(artifacts, config=_config())

    observations, summary = build_geometry_observation_frame(
        artifacts, nodes, edges, components, config=_config()
    )

    assert {"ASSERTED", "POSSIBLE", "REJECTED"}.issubset(set(observations["state"]))
    possible = observations.loc[observations["state"] == "POSSIBLE"].iloc[0]
    assert possible["distance"] == 5.0
    assert possible["reason_code"] == "unique_collinear_open_endpoint_gap_v1"
    assert summary["state_counts"]["REJECTED"] == 1


def test_geometry_observations_keep_ambiguous_gap_unknown() -> None:
    artifacts = _artifacts(
        [
            _line("L1", 0.0, 10.0, 10.0, 10.0),
            _line("L2", 15.0, 10.0, 20.0, 10.0),
            _line("L3", 18.0, 10.0, 25.0, 10.0),
        ]
    )
    nodes, edges, components, _ = build_geometry_graph_frames(artifacts, config=_config())

    observations, _ = build_geometry_observation_frame(
        artifacts, nodes, edges, components, config=_config()
    )

    unknown = observations.loc[observations["state"] == "UNKNOWN"]
    assert len(unknown) == 2
    assert set(unknown["reason_code"]) == {"ambiguous_collinear_open_endpoint_gap_v1"}
