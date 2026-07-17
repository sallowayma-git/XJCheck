from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TextItem
from dwg_audit.audit.coverage import build_entity_coverage_summary
from dwg_audit.audit.coverage import build_text_assignment_frame


def _artifacts(*, texts, candidates=None, pairs=None, pages=None) -> ProjectArtifacts:
    pages = pages or [
        SheetRecord(
            sheet_id="S1",
            file_id="F1",
            filename="demo.dwg",
            sheet_order=1,
            sheet_no="01",
            sheet_title="Demo",
            sheet_category="二次原理图",
            audit_role="primary",
            page_no_source="filename",
            is_primary_audit_candidate=True,
            audit_disposition="audit_required",
            audit_area_bbox=(0.0, 0.0, 100.0, 100.0),
            title_block_bbox=(80.0, 0.0, 100.0, 20.0),
            route_target="WireDiagramExtractor",
        )
    ]
    manifest = Manifest(
        project_id="demo",
        project_name="demo",
        created_at="2026-07-07T00:00:00Z",
        tool_version="0.1.0",
        input_root="demo",
        file_count=1,
        sheet_count=len(pages),
        valid_dwg_files=1,
        invalid_dwg_files=0,
        source_files=[
            SourceFileRecord(
                file_id="F1",
                path="demo.dwg",
                filename="demo.dwg",
                ext=".dwg",
                sha256="x",
                size_bytes=1,
                sheet_order=1,
                detected_page_no="01",
                detected_from="filename",
                sheet_title="Demo",
                sheet_category="二次原理图",
                skip_reason=None,
                valid_dwg_header=True,
            )
        ],
    )
    scan = ProjectScanResult(manifest=manifest, pages=pages, terminal_strips=[], project_root="demo")
    return ProjectArtifacts(
        scan=scan,
        texts=texts,
        terminal_candidates=candidates or [],
        pairs=pairs or [],
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
        bbox_min_x=x - 1,
        bbox_min_y=y - 1,
        bbox_max_x=x + 1,
        bbox_max_y=y + 1,
    )


def _candidate(
    candidate_id: str,
    text_id: str,
    text: str,
    *,
    channel: str | None,
    channel_detail: str | None = None,
    status: str = "rejected",
    rejection_reason: str | None = None,
) -> TerminalCandidate:
    return TerminalCandidate(
        candidate_id=candidate_id,
        line_group_id="G1",
        sheet_id="S1",
        file_id="F1",
        side="left",
        text_id=text_id,
        text=text,
        value=text if text.isdigit() else None,
        score=0.2,
        status=status,
        rejection_reason=rejection_reason,
        endpoint_x=0.0,
        endpoint_y=0.0,
        distance_x=1.0,
        distance_y=0.0,
        channel=channel,
        channel_detail=channel_detail,
    )


def _pair(pair_id: str, text_id: str, value: str, *, pair_kind: str, status: str = "pass") -> Pair:
    return Pair(
        pair_id=pair_id,
        line_group_id="G1",
        sheet_id="S1",
        file_id="F1",
        selected_pair_candidate_id="PC1",
        left_value=value,
        right_value=None,
        confidence=0.98,
        status=status,
        rationale="ok",
        left_text_id=text_id,
        pair_kind=pair_kind,
        evidence={"mapping_mode": "demo_mode"},
    )


def test_build_text_assignment_frame_uses_contract_assignment_kinds() -> None:
    texts = [
        _text("T1", "101", 10, 10),
        _text("T2", "202", 20, 10),
        _text("T3", "UA", 30, 10),
        _text("T4", "n101", 40, 10),
        _text("T5", "303", 50, 10),
        _text("T6", "MARK", 60, 10),
        _text("T7", "TITLE", 90, 10),
        _text("T8", "909", 70, 10),
    ]
    pairs = [
        _pair("P1", "T1", "101", pair_kind="ordinary_pair"),
        _pair("P2", "T2", "202", pair_kind="wire_component_mapping"),
        _pair("P3", "T3", "UA", pair_kind="semantic_mapping"),
        _pair("P4", "T4", "n101", pair_kind="continuation"),
        _pair("P5", "T5", "303", pair_kind="ordinary_pair", status="discard"),
    ]
    candidates = [
        _candidate("C6", "T6", "MARK", channel="noise_channel", rejection_reason="not_numeric"),
    ]

    frame = build_text_assignment_frame(_artifacts(texts=texts, candidates=candidates, pairs=pairs))
    by_text = {row["text_id"]: row for _, row in frame.iterrows()}

    assert by_text["T1"]["assignment_kind"] == "pair_endpoint"
    assert by_text["T2"]["assignment_kind"] == "structured_mapping_endpoint"
    assert by_text["T3"]["assignment_kind"] == "semantic_evidence"
    assert by_text["T4"]["assignment_kind"] == "continuation_evidence"
    assert by_text["T5"]["assignment_kind"] == "covered_discard"
    assert by_text["T6"]["assignment_kind"] == "rejected_candidate"
    assert by_text["T7"]["assignment_kind"] == "out_of_scope"
    assert by_text["T8"]["assignment_kind"] == "unexplained"
    assert by_text["T2"]["consumed_by_pair_ids"] == ["P2"]
    assert by_text["T2"]["consumed_by_kinds"] == ["wire_component_mapping"]
    assert by_text["T7"]["counts_toward_contract"] is False


def test_build_text_assignment_frame_prefers_semantic_candidate_evidence() -> None:
    texts = [_text("T1", "UA", 10, 10)]
    candidates = [
        _candidate(
            "C1",
            "T1",
            "UA",
            channel="semantic_channel",
            channel_detail="terminal_ac_marker",
        )
    ]

    frame = build_text_assignment_frame(_artifacts(texts=texts, candidates=candidates))
    row = frame.iloc[0]

    assert row["assignment_kind"] == "semantic_evidence"
    assert row["channel"] == "semantic_channel"
    assert row["explain_reason"] == "terminal_ac_marker"


def test_build_text_assignment_frame_does_not_count_empty_matrix_structure() -> None:
    text = _text("T1", "出口1 Output 1", 50, 50)
    frame = build_text_assignment_frame(
        _artifacts(texts=[text]),
        table_mappings=[
            {
                "sheet_id": "S1",
                "matrix_table": True,
                "structural_text_ids": ["T1"],
                "mappings": [],
            }
        ],
    )
    row = frame.iloc[0]

    assert row["assignment_kind"] == "unexplained"
    assert row["assignment_source"] == "coverage_contract"
    assert bool(row["counts_toward_contract"]) is True
    assert row["consumed_by_mapping_modes"] == []


def test_build_text_assignment_frame_counts_recovered_matrix_mapping_text() -> None:
    text = _text("T1", "出口1 Output 1", 90, 10)
    frame = build_text_assignment_frame(
        _artifacts(texts=[text]),
        table_mappings=[
            {
                "sheet_id": "S1",
                "matrix_table": True,
                "structural_text_ids": ["T1"],
                "mappings": [{"row_text_id": "T1"}],
            }
        ],
    )
    row = frame.iloc[0]

    assert row["assignment_kind"] == "semantic_evidence"
    assert row["assignment_source"] == "table_mapping_structure"
    assert bool(row["counts_toward_contract"]) is True
    assert row["consumed_by_mapping_modes"] == ["output_contact_matrix"]


def test_build_entity_coverage_summary_preserves_identity_and_metrics() -> None:
    texts = [
        _text("T1", "101", 10, 10),
        _text("T2", "UA", 20, 10),
        _text("T3", "909", 40, 40),
        _text("T4", "TITLE", 90, 10),
    ]
    candidates = [
        _candidate(
            "C2",
            "T2",
            "UA",
            channel="semantic_channel",
            channel_detail="terminal_ac_marker",
        )
    ]
    pairs = [_pair("P1", "T1", "101", pair_kind="ordinary_pair")]

    artifacts = _artifacts(texts=texts, candidates=candidates, pairs=pairs)
    frame = build_text_assignment_frame(artifacts)
    summary_frame, summary_payload = build_entity_coverage_summary(frame, artifacts=artifacts)

    assert not summary_frame.empty
    assert summary_payload["identity_ok"] is True
    assert summary_payload["assigned_texts"] == 2
    assert summary_payload["unexplained_texts"] == 1
    assert summary_payload["unexplained_numeric_texts"] == 1
    assert summary_payload["audit_scope_texts"] == 3
    assert summary_payload["unassigned_wire_segments"] == 0
    assert summary_payload["unclassified_blocks"] == 0
    assert summary_payload["contract_checks"]["unassigned_defaults_to_unexplained"] is True


def test_build_entity_coverage_summary_page_rows_include_line_and_block_gaps() -> None:
    from dwg_audit.domain.models import BlockRecord
    from dwg_audit.domain.models import LineEntity
    from dwg_audit.domain.models import LineGroup

    artifacts = _artifacts(texts=[_text("T1", "101", 10, 10)])
    artifacts.lines = [
        LineEntity(
            line_id="L1",
            sheet_id="S1",
            file_id="F1",
            handle="L1",
            source_entity_type="LINE",
            layer="WIRE",
            start_x=10.0,
            start_y=10.0,
            end_x=20.0,
            end_y=10.0,
            length=10.0,
            angle_deg=0.0,
            bbox_min_x=10.0,
            bbox_min_y=10.0,
            bbox_max_x=20.0,
            bbox_max_y=10.0,
        ),
        LineEntity(
            line_id="L2",
            sheet_id="S1",
            file_id="F1",
            handle="L2",
            source_entity_type="LINE",
            layer="WIRE",
            start_x=30.0,
            start_y=10.0,
            end_x=40.0,
            end_y=10.0,
            length=10.0,
            angle_deg=0.0,
            bbox_min_x=30.0,
            bbox_min_y=10.0,
            bbox_max_x=40.0,
            bbox_max_y=10.0,
        ),
    ]
    artifacts.line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=10.0,
            end_x=20.0,
            end_y=10.0,
            length=10.0,
            wire_candidate_score=1.0,
            member_line_ids=["L1"],
        )
    ]
    artifacts.blocks = [
        BlockRecord(
            block_id="B1",
            sheet_id="S1",
            file_id="F1",
            handle="B1",
            name="UNKNOWN",
            layer="0",
            insert_x=50.0,
            insert_y=50.0,
            rotation_deg=0.0,
            attributes_json="{}",
        )
    ]

    frame = build_text_assignment_frame(artifacts)
    summary_frame, summary_payload = build_entity_coverage_summary(frame, artifacts=artifacts)
    page_row = summary_frame[summary_frame["summary_scope"] == "page"].iloc[0]

    assert summary_payload["unassigned_wire_segments"] == 1
    assert summary_payload["unclassified_blocks"] == 1
    assert page_row["line_segments"] == 2
    assert page_row["unassigned_wire_segments"] == 1
    assert page_row["blocks"] == 1
    assert page_row["unclassified_blocks"] == 1


def test_wire_coverage_excludes_non_conductive_page_and_block_artwork() -> None:
    from dwg_audit.domain.models import LineEntity

    table_page = SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="switch-table.dwg",
        sheet_order=1,
        sheet_no="01",
        sheet_title="Switch table",
        sheet_category="背板接线图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_disposition="audit_required",
        audit_area_bbox=(0.0, 0.0, 100.0, 100.0),
        route_target="TableExtractor",
    )
    artifacts = _artifacts(texts=[_text("T1", "101", 10, 10)], pages=[table_page])
    artifacts.lines = [
        LineEntity(
            line_id="GRID",
            sheet_id="S1",
            file_id="F1",
            handle="GRID",
            source_entity_type="LINE",
            layer="0",
            start_x=0.0,
            start_y=10.0,
            end_x=100.0,
            end_y=10.0,
            length=100.0,
            angle_deg=0.0,
            bbox_min_x=0.0,
            bbox_min_y=10.0,
            bbox_max_x=100.0,
            bbox_max_y=10.0,
        )
    ]

    frame = build_text_assignment_frame(artifacts)
    summary_frame, summary_payload = build_entity_coverage_summary(frame, artifacts=artifacts)
    page_row = summary_frame[summary_frame["summary_scope"] == "page"].iloc[0]

    assert summary_payload["unassigned_wire_segments"] == 0
    assert page_row["line_segments"] == 0
    assert page_row["unassigned_wire_segments"] == 0


def test_wire_coverage_keeps_positive_line_group_evidence_on_non_wire_route() -> None:
    from dwg_audit.domain.models import LineEntity
    from dwg_audit.domain.models import LineGroup

    table_page = SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="switch-table.dwg",
        sheet_order=1,
        sheet_no="01",
        sheet_title="Switch table",
        sheet_category="背板接线图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_disposition="audit_required",
        audit_area_bbox=(0.0, 0.0, 100.0, 100.0),
        route_target="TableExtractor",
    )
    artifacts = _artifacts(texts=[_text("T1", "101", 10, 10)], pages=[table_page])
    artifacts.lines = [
        LineEntity(
            line_id="PROVEN_WIRE",
            sheet_id="S1",
            file_id="F1",
            handle="PROVEN_WIRE",
            source_entity_type="LWPOLYLINE",
            layer="0",
            start_x=30.0,
            start_y=10.0,
            end_x=40.0,
            end_y=10.0,
            length=10.0,
            angle_deg=0.0,
            bbox_min_x=30.0,
            bbox_min_y=10.0,
            bbox_max_x=40.0,
            bbox_max_y=10.0,
        )
    ]
    artifacts.line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=30.0,
            start_y=10.0,
            end_x=40.0,
            end_y=10.0,
            length=10.0,
            wire_candidate_score=1.0,
            member_line_ids=["PROVEN_WIRE"],
        )
    ]

    frame = build_text_assignment_frame(artifacts)
    summary_frame, summary_payload = build_entity_coverage_summary(frame, artifacts=artifacts)
    page_row = summary_frame[summary_frame["summary_scope"] == "page"].iloc[0]

    assert summary_payload["unassigned_wire_segments"] == 0
    assert page_row["line_segments"] == 1
    assert page_row["unassigned_wire_segments"] == 0


def test_wire_coverage_keeps_group_evidence_but_excludes_expanded_block_geometry() -> None:
    from dwg_audit.domain.models import LineEntity
    from dwg_audit.domain.models import LineGroup

    artifacts = _artifacts(texts=[_text("T1", "101", 10, 10)])
    artifacts.lines = [
        LineEntity(
            line_id="BLOCK_LINE",
            sheet_id="S1",
            file_id="F1",
            handle="BLOCK_LINE",
            source_entity_type="LINE",
            layer="0",
            start_x=10.0,
            start_y=10.0,
            end_x=20.0,
            end_y=10.0,
            length=10.0,
            angle_deg=0.0,
            bbox_min_x=10.0,
            bbox_min_y=10.0,
            bbox_max_x=20.0,
            bbox_max_y=10.0,
            source_block_name="DEVICE_BODY",
        ),
        LineEntity(
            line_id="PROVEN_WIRE",
            sheet_id="S1",
            file_id="F1",
            handle="PROVEN_WIRE",
            source_entity_type="LWPOLYLINE",
            layer="0",
            start_x=30.0,
            start_y=10.0,
            end_x=40.0,
            end_y=10.0,
            length=10.0,
            angle_deg=0.0,
            bbox_min_x=30.0,
            bbox_min_y=10.0,
            bbox_max_x=40.0,
            bbox_max_y=10.0,
        ),
    ]
    artifacts.line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=30.0,
            start_y=10.0,
            end_x=40.0,
            end_y=10.0,
            length=10.0,
            wire_candidate_score=1.0,
            member_line_ids=["PROVEN_WIRE"],
        )
    ]

    frame = build_text_assignment_frame(artifacts)
    summary_frame, summary_payload = build_entity_coverage_summary(frame, artifacts=artifacts)
    page_row = summary_frame[summary_frame["summary_scope"] == "page"].iloc[0]

    assert summary_payload["unassigned_wire_segments"] == 0
    assert page_row["line_segments"] == 1
    assert page_row["unassigned_wire_segments"] == 0
