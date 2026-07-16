from __future__ import annotations

from dwg_audit.audit.semantic_attachment import build_semantic_attachment_candidates
from dwg_audit.audit.semantic_attachment import summarize_semantic_attachments
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import TextItem


def _text(
    text_id: str,
    value: str,
    x: float,
    y: float,
    *,
    sheet_id: str = "S1",
) -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id=sheet_id,
        file_id="F1",
        handle=f"H{text_id}",
        entity_type="TEXT",
        text=value,
        normalized_text=value,
        is_numeric_candidate=value.isdigit(),
        layer="DIM",
        rotation_deg=0.0,
        height=2.5,
        insert_x=x,
        insert_y=y,
        bbox_min_x=x - 1.0,
        bbox_min_y=y - 1.0,
        bbox_max_x=x + 1.0,
        bbox_max_y=y + 1.0,
    )


def _line(
    line_id: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    *,
    sheet_id: str = "S1",
) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id=sheet_id,
        file_id="F1",
        handle=f"H{line_id}",
        source_entity_type="LINE",
        layer="WIRE",
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        length=((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5,
        angle_deg=0.0,
        bbox_min_x=min(start_x, end_x),
        bbox_min_y=min(start_y, end_y),
        bbox_max_x=max(start_x, end_x),
        bbox_max_y=max(start_y, end_y),
    )


def test_one_text_near_one_line_end_is_selected() -> None:
    texts = [_text("T1", "n105", 10.0, 10.0)]
    lines = [_line("L1", 0.0, 10.0, 10.5, 10.0)]

    rows = build_semantic_attachment_candidates(texts, lines, top_k=3)

    selected = [row for row in rows if row["selected"]]
    assert len(selected) == 1
    row = selected[0]
    assert row["token_id"] == "TK1-T1"
    assert row["token_kind"] == "WIRE_N_NUMBER"
    assert row["target_kind"] == "LINE_ENDPOINT"
    assert row["target_line_id"] == "L1"
    assert row["target_endpoint"] == "end"
    assert row["rank"] == 1
    assert row["state"] == "SELECTED"
    assert row["score"] == 1.0 / (1.0 + row["distance"])
    assert row["algorithm_version"] == "semantic-attachment-v1"
    assert "NEAREST_LINE_ENDPOINT" in row["reason_codes"]
    # With competing start endpoint farther away, margin is positive.
    assert row["margin"] >= 0.0


def test_two_competing_endpoints_compute_margin() -> None:
    texts = [_text("T1", "105", 5.0, 0.0)]
    # Two endpoints nearly equidistant: start at (0,0) distance=5, end at (10,0) distance=5.
    # Tilt slightly so start is nearer.
    lines = [_line("L1", 0.2, 0.0, 10.0, 0.0)]

    rows = build_semantic_attachment_candidates(texts, lines, top_k=2)

    assert len(rows) == 2
    selected = next(row for row in rows if row["rank"] == 1)
    rejected = next(row for row in rows if row["rank"] == 2)
    assert selected["selected"] is True
    assert selected["state"] == "SELECTED"
    assert rejected["selected"] is False
    assert rejected["state"] == "REJECTED"
    assert selected["target_endpoint"] == "start"
    assert selected["margin"] == selected["score"] - rejected["score"]
    assert selected["margin"] > 0.0
    assert rejected["margin"] == 0.0


def test_different_sheet_lines_are_ignored() -> None:
    texts = [_text("T1", "1QD12", 10.0, 10.0, sheet_id="S1")]
    lines = [
        _line("L_other", 10.0, 10.0, 20.0, 10.0, sheet_id="S2"),
        _line("L_same", 50.0, 50.0, 60.0, 50.0, sheet_id="S1"),
    ]

    rows = build_semantic_attachment_candidates(texts, lines, top_k=3)

    assert rows
    assert all(row["sheet_id"] == "S1" for row in rows)
    assert all(row["target_line_id"] == "L_same" for row in rows)
    assert "L_other" not in {row["target_line_id"] for row in rows}


def test_no_lines_on_sheet_emits_no_rows() -> None:
    texts = [_text("T1", "n105", 10.0, 10.0)]
    rows = build_semantic_attachment_candidates(texts, lines=[], top_k=3)
    assert rows == []


def test_non_attachable_kinds_are_skipped() -> None:
    texts = [
        _text("A1", "手合同期", 10.0, 10.0),
        _text("P1", "详见第3页", 10.0, 12.0),
        _text("C1", "1", 10.0, 14.0),  # COMPONENT_PORT not attachable
    ]
    lines = [_line("L1", 0.0, 10.0, 12.0, 10.0)]

    rows = build_semantic_attachment_candidates(texts, lines, top_k=3)
    assert rows == []


def test_summarize_semantic_attachments() -> None:
    texts = [
        _text("T1", "n105", 10.0, 10.0),
        _text("T2", "1QD5", 30.0, 10.0),
    ]
    lines = [
        _line("L1", 0.0, 10.0, 10.2, 10.0),
        _line("L2", 30.0, 10.0, 40.0, 10.0),
    ]
    rows = build_semantic_attachment_candidates(texts, lines, top_k=2)
    summary = summarize_semantic_attachments(rows)

    assert summary["selected_count"] == 2
    assert summary["rejected_count"] == len(rows) - 2
    assert summary["total_count"] == len(rows)
    assert summary["by_token_kind"]["WIRE_N_NUMBER"] == 1
    assert summary["by_token_kind"]["EXTERNAL_ENDPOINT"] == 1
    assert "low_margin_count" in summary
    assert summary["algorithm_version"] == "semantic-attachment-v1"


def test_preparsed_tokens_are_respected() -> None:
    texts = [_text("T1", "n105", 10.0, 10.0)]
    lines = [_line("L1", 0.0, 10.0, 10.0, 10.0)]
    tokens = [
        {
            "token_id": "TK1-T1",
            "text_id": "T1",
            "sheet_id": "S1",
            "file_id": "F1",
            "raw_text": "n105",
            "normalized_text": "n105",
            "token_kind": "WIRE_N_NUMBER",
            "insert_x": 10.0,
            "insert_y": 10.0,
        }
    ]

    rows = build_semantic_attachment_candidates(texts, lines, tokens=tokens, top_k=1)
    assert len(rows) == 1
    assert rows[0]["token_id"] == "TK1-T1"
    assert rows[0]["selected"] is True
