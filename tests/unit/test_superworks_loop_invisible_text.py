"""Invisible DXF text (raw height < 0.01) must not become a terminal candidate.

Background: cad_extract clamps TEXT height to >= 1.0 for the engine. SuperWORKS
hidden ordinal numerals are written at height 1e-05, so before raw_height was
kept they passed the min-height gate and were accepted as terminal numerals.
"""

from __future__ import annotations

import dataclasses
import math
import re
from pathlib import Path

import ezdxf
import pandas as pd

from dwg_audit.audit.candidates import build_terminal_candidates
from dwg_audit.audit.table_extractor import extract_table_pairs
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.domain.models import dxf_text_visibility
from dwg_audit.domain.models import is_dxf_invisible_text
from dwg_audit.domain.models import is_invisible_text
from dwg_audit.extract.cad_extract import _extract_graphic_entity
from dwg_audit.utils.config import DEFAULT_CONFIG
from dwg_audit.utils.ids import IdFactory

_NUMERIC = re.compile(r"^[0-9]+$")


def _sheet() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="x.dwg",
        sheet_order=1,
        sheet_no="1",
        sheet_title="T",
        sheet_category=None,
        audit_role="audit",
        page_no_source="test",
        is_primary_audit_candidate=True,
    )


def _extract_single_text(
    height: float,
    text: str = "7",
    *,
    invisible: bool = False,
    layer_visible: bool = True,
) -> list[TextItem]:
    doc = ezdxf.new("R2018")
    entity = doc.modelspace().add_text(text, dxfattribs={"height": height, "insert": (8.0, 20.0)})
    if invisible:
        entity.dxf.invisible = 1
    sheet_texts: list[TextItem] = []
    _extract_graphic_entity(
        entity,
        sheet=_sheet(),
        numeric_pattern=_NUMERIC,
        text_ids=IdFactory("T"),
        line_ids=IdFactory("L"),
        block_ids=IdFactory("B"),
        polyline_ids=IdFactory("P"),
        sheet_texts=sheet_texts,
        sheet_lines=[],
        sheet_blocks=[],
        sheet_polylines=[],
        layer_visibility_by_name={"0": layer_visible},
    )
    return sheet_texts


def _line_group() -> LineGroup:
    return LineGroup(
        line_group_id="G1",
        sheet_id="S1",
        file_id="F1",
        start_x=10.0,
        start_y=20.0,
        end_x=90.0,
        end_y=20.0,
        length=80.0,
        wire_candidate_score=0.9,
        member_line_ids=["L1"],
        layer_hints=["WIRE"],
    )


def _text(text_id: str, value: str, x: float, *, raw_height: float | None) -> TextItem:
    return TextItem(
        text_id, "S1", "F1", f"H_{text_id}", "TEXT", value, value, True, "MARK", 0.0,
        1.0, x, 20.0, x, 19.0, x + 4.0, 22.0,
        raw_height=raw_height,
    )


def test_extraction_keeps_raw_height_and_engine_height_unchanged() -> None:
    hidden = _extract_single_text(1e-05)[0]
    visible = _extract_single_text(2.5)[0]

    # Engine-facing height keeps the existing clamp; only raw_height is new.
    assert hidden.height == 1.0
    assert hidden.raw_height == 1e-05
    assert is_invisible_text(hidden) is True
    assert dxf_text_visibility(hidden) is True
    assert visible.height == 2.5
    assert visible.raw_height == 2.5
    assert is_invisible_text(visible) is False
    assert dxf_text_visibility(visible) is True


def test_dxf_visibility_captures_entity_and_layer_state() -> None:
    entity_hidden = _extract_single_text(2.5, invisible=True)[0]
    layer_hidden = _extract_single_text(2.5, layer_visible=False)[0]

    assert dxf_text_visibility(entity_hidden) is False
    assert is_dxf_invisible_text(entity_hidden) is True
    assert dxf_text_visibility(layer_hidden) is False


def test_hidden_numeral_is_rejected_as_invisible_text_candidate() -> None:
    texts = [_text("T1", "7", 8.0, raw_height=1e-05)]

    candidates = build_terminal_candidates([_line_group()], texts, DEFAULT_CONFIG)

    left = next(item for item in candidates if item.side == "left" and item.text_id == "T1")
    assert left.status == "rejected"
    assert left.rejection_reason == "invisible_text"
    assert left.value is None
    assert not [item for item in candidates if item.status == "accepted"]


def test_visible_numeral_at_same_position_is_still_accepted() -> None:
    texts = [_text("T1", "7", 8.0, raw_height=2.5)]

    candidates = build_terminal_candidates([_line_group()], texts, DEFAULT_CONFIG)

    left = next(item for item in candidates if item.side == "left" and item.text_id == "T1")
    assert left.status == "accepted"
    assert left.rejection_reason is None
    assert left.value == "7"


def test_legacy_text_without_raw_height_is_treated_as_visible() -> None:
    legacy = _text("T1", "7", 8.0, raw_height=None)
    assert is_invisible_text(legacy) is False

    candidates = build_terminal_candidates([_line_group()], [legacy], DEFAULT_CONFIG)

    left = next(item for item in candidates if item.side == "left" and item.text_id == "T1")
    assert left.status == "accepted"


def test_legacy_parquet_without_raw_height_column_reads_as_visible(tmp_path: Path) -> None:
    # Simulate an artifact written before raw_height existed: drop the column entirely.
    current = _text("T1", "7", 8.0, raw_height=None)
    row = dataclasses.asdict(current)
    row.pop("raw_height")
    row.pop("dxf_visible")
    path = tmp_path / "texts.parquet"
    pd.DataFrame([row]).to_parquet(path, index=False)

    frame = pd.read_parquet(path)
    assert "raw_height" not in frame.columns
    assert "dxf_visible" not in frame.columns
    legacy = TextItem(**{
        key: value for key, value in frame.iloc[0].to_dict().items()
        if key not in {"raw_height", "dxf_visible"}
    })
    assert is_invisible_text(legacy) is False
    assert dxf_text_visibility(legacy) is None

    candidates = build_terminal_candidates([_line_group()], [legacy], DEFAULT_CONFIG)
    left = next(item for item in candidates if item.side == "left" and item.text_id == "T1")
    assert left.status == "accepted"


def test_parquet_with_null_raw_height_column_reads_as_visible(tmp_path: Path) -> None:
    # New artifact written for a text whose raw height was not recorded: NaN, not invisible.
    row = dataclasses.asdict(_text("T1", "7", 8.0, raw_height=None))
    path = tmp_path / "texts.parquet"
    pd.DataFrame([row]).to_parquet(path, index=False)

    frame = pd.read_parquet(path)
    value = frame.iloc[0]["raw_height"]
    assert pd.isna(value)
    restored = TextItem(**frame.iloc[0].to_dict())
    assert is_invisible_text(restored) is False
    assert dxf_text_visibility(restored) is None


def test_hidden_text_does_not_suppress_visible_neighbour() -> None:
    texts = [
        _text("T1", "7", 8.0, raw_height=1e-05),
        _text("T2", "12", 22.0, raw_height=2.5),
    ]

    candidates = build_terminal_candidates([_line_group()], texts, DEFAULT_CONFIG)

    hidden = next(item for item in candidates if item.text_id == "T1" and item.side == "left")
    visible = next(item for item in candidates if item.text_id == "T2" and item.side == "left")
    assert hidden.rejection_reason == "invisible_text"
    assert visible.status == "accepted"
    assert visible.value == "12"


def _grid_sheet() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="table.dwg",
        sheet_order=1,
        sheet_no="01",
        sheet_title="table",
        sheet_category=None,
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=(0.0, 0.0, 300.0, 200.0),
    )


def _grid_line(line_id: str, *, horizontal: bool, pos: float) -> LineEntity:
    if horizontal:
        x1, y1, x2, y2 = 10.0, pos, 290.0, pos
    else:
        x1, y1, x2, y2 = pos, 10.0, pos, 190.0
    return LineEntity(
        line_id=line_id, sheet_id="S1", file_id="F1", handle=f"H{line_id}", source_entity_type="LINE",
        layer="TABLE", start_x=x1, start_y=y1, end_x=x2, end_y=y2,
        length=math.dist((x1, y1), (x2, y2)), angle_deg=0.0 if horizontal else 90.0,
        bbox_min_x=min(x1, x2), bbox_min_y=min(y1, y2), bbox_max_x=max(x1, x2), bbox_max_y=max(y1, y2),
    )


def _grid_text(text_id: str, x: float, y: float, value: str, *, raw_height: float | None) -> TextItem:
    return TextItem(
        text_id=text_id, sheet_id="S1", file_id="F1", handle=f"TH{text_id}", entity_type="TEXT",
        text=value, normalized_text=value, is_numeric_candidate=True, layer="MARK", rotation_deg=0.0,
        height=1.0, insert_x=x, insert_y=y, bbox_min_x=x - 2, bbox_min_y=y - 2, bbox_max_x=x + 2, bbox_max_y=y + 2,
        raw_height=raw_height,
    )


def _three_column_grid(middle_raw_height: float | None) -> tuple[list[LineEntity], list[TextItem]]:
    # 3 x 3 cells: horizontal y=10,60,110,160; vertical x=10,100,200,290.
    lines = [
        *[_grid_line(f"H{i}", horizontal=True, pos=y) for i, y in enumerate((10.0, 60.0, 110.0, 160.0))],
        *[_grid_line(f"V{i}", horizontal=False, pos=x) for i, x in enumerate((10.0, 100.0, 200.0, 290.0))],
    ]
    texts = [
        # Row 1 (y 35): visible left/middle/right numerals, always a normal pass.
        _grid_text("A1", 55, 35, "101", raw_height=2.5),
        _grid_text("A2", 150, 35, "102", raw_height=middle_raw_height),
        _grid_text("A3", 245, 35, "103", raw_height=2.5),
        # Row 2 (y 85): visible throughout.
        _grid_text("B1", 55, 85, "201", raw_height=2.5),
        _grid_text("B2", 150, 85, "202", raw_height=2.5),
        _grid_text("B3", 245, 85, "203", raw_height=2.5),
    ]
    return lines, texts


def test_table_channel_does_not_map_a_hidden_middle_cell() -> None:
    lines, texts = _three_column_grid(middle_raw_height=1e-05)

    pairs, _ = extract_table_pairs(texts, lines, [], [_grid_sheet()], DEFAULT_CONFIG)

    values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("102", "103") not in values
    assert ("202", "203") in values


def test_table_channel_still_maps_the_same_cell_when_visible() -> None:
    lines, texts = _three_column_grid(middle_raw_height=2.5)

    pairs, _ = extract_table_pairs(texts, lines, [], [_grid_sheet()], DEFAULT_CONFIG)

    values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("102", "103") in values
    assert ("202", "203") in values


def test_three_column_row_with_crowded_middle_cell_is_not_a_value_row() -> None:
    # A second numeral inside the middle cell of row 1 makes it a drawing region (for
    # example a port-number array), not a single-value table cell.
    lines, texts = _three_column_grid(middle_raw_height=2.5)
    texts.append(_grid_text("A4", 180, 30, "9", raw_height=2.5))

    pairs, _ = extract_table_pairs(texts, lines, [], [_grid_sheet()], DEFAULT_CONFIG)

    values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("102", "103") not in values
    assert ("202", "203") in values


def test_three_column_row_with_crowded_outer_cell_is_not_a_value_row() -> None:
    # The right cell of row 2 holds an array of numerals, so "202 -> 203" is not a value pair.
    lines, texts = _three_column_grid(middle_raw_height=2.5)
    texts.append(_grid_text("B4", 260, 85, "7", raw_height=2.5))

    pairs, _ = extract_table_pairs(texts, lines, [], [_grid_sheet()], DEFAULT_CONFIG)

    values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("202", "203") not in values
    assert ("102", "103") in values
