"""TableExtractor 雏形（任务书第 4 章 113-121 行）。

针对表格型图，识别表格骨架、行、列、单元格，并重点支持两类三列表格：
- 数值三列表格：左列 / 中列 / 右列数字
- 表头型三列表格：表头前缀 + 中列行号 + 左右接线端

两者都生成高置信 `table_mapping` Pair，供 RuleEngine 作为独立信源参与跨页校验。

当前实现是最小骨架：
- 从 polylines + 长水平/竖直线推断表格网格线
- 按 y 聚类水平网格线 → 行；按 x 聚类竖直网格线 → 列
- 三列模式检测（列数 == 3）
- 命中表头型三列表格时，合成 `logical_endpoint = header_prefix + row_number`
- 否则回退到中列 → 左/右列的数值三列表格映射
"""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import PolylineRecord
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_TABLE_GRID_LINE_TOL = 3.0
_TABLE_MIN_ROWS = 2
_TABLE_MIN_COLS = 2
_TABLE_THREE_COLUMN_COUNT = 3
_TABLE_PAIR_CONFIDENCE = 0.95
_HEADER_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9\-_/]*[A-Za-z][A-Za-z0-9\-_/]*$")
_TERMINAL_ENDPOINT_PATTERN = re.compile(r"(?i).*[a-z]\d+$")


def extract_table_pairs(
    texts: list[TextItem],
    lines: list[LineEntity],
    polylines: list[PolylineRecord],
    sheets: list[SheetRecord],
    config: dict | None = None,
) -> tuple[list[Pair], list[dict[str, Any]]]:
    """对表格型页抽取三列映射 Pair。

    返回 (table_pairs, table_mappings)：
    - table_pairs：从表格单元格映射生成的 Pair，confidence >= 0.92，status=pass
    - table_mappings：结构化列映射记录，供 findings 展示和 RuleEngine 作为独立信源
    """
    config = config or {}
    texts_by_sheet = _group_by_sheet(texts)
    lines_by_sheet = _group_by_sheet(lines)
    polylines_by_sheet = _group_by_sheet(polylines)
    sheet_map = {sheet.sheet_id: sheet for sheet in sheets}
    pair_ids = IdFactory("P")

    table_pairs: list[Pair] = []
    table_mappings: list[dict[str, Any]] = []

    for sheet in sheets:
        if sheet.audit_role == "skip":
            continue
        sheet_id = sheet.sheet_id
        sheet_texts = texts_by_sheet.get(sheet_id, [])
        sheet_lines = lines_by_sheet.get(sheet_id, [])
        sheet_polylines = polylines_by_sheet.get(sheet_id, [])
        if not sheet_texts or not sheet.audit_area_bbox:
            continue

        grid = _detect_table_grid(sheet_lines, sheet_polylines, sheet)
        if grid is None:
            continue
        rows, cols = grid
        if len(rows) < _TABLE_MIN_ROWS or len(cols) < _TABLE_MIN_COLS:
            continue

        cells = _build_cells(rows, cols)
        cell_values = _assign_texts_to_cells(sheet_texts, cells, sheet)

        # 单元格列数 = 网格线列数 - 1；三列表格要求 3 个单元格列
        cell_col_count = len(cols) - 1
        if cell_col_count != _TABLE_THREE_COLUMN_COUNT:
            # 当前只对三列表格生成高置信映射；其他列数只记录结构
            table_mappings.append(
                {
                    "sheet_id": sheet_id,
                    "filename": sheet.filename,
                    "sheet_no": sheet.sheet_no,
                    "row_count": len(rows) - 1,
                    "col_count": cell_col_count,
                    "three_column": False,
                    "mappings": [],
                }
            )
            continue

        mappings = _build_three_column_mappings(cell_values, cols, rows, sheet)
        for mapping in mappings:
            table_pairs.extend(_build_table_pairs(mapping, sheet, pair_ids))
        table_mappings.append(
            {
                "sheet_id": sheet_id,
                "filename": sheet.filename,
                "sheet_no": sheet.sheet_no,
                "row_count": len(rows) - 1,
                "col_count": cell_col_count,
                "three_column": True,
                "mappings": mappings,
            }
        )

    return table_pairs, table_mappings


def _detect_table_grid(
    lines: list[LineEntity],
    polylines: list[PolylineRecord],
    sheet: SheetRecord,
) -> tuple[list[float], list[float]] | None:
    """从长水平线和长竖直线推断表格网格线，返回 (row_y_values, col_x_values)。"""
    audit_bbox = sheet.audit_area_bbox
    if audit_bbox is None:
        return None
    min_x, min_y, max_x, max_y = audit_bbox
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        return None

    # 收集水平网格线（y 值）
    horizontal_ys: list[float] = []
    tol = 2.0
    min_grid_length = width * 0.3
    for line in lines:
        if line.length < min_grid_length:
            continue
        angle = abs(line.angle_deg)
        if angle <= tol or abs(angle - 180.0) <= tol:
            mid_x = (line.start_x + line.end_x) / 2.0
            mid_y = (line.start_y + line.end_y) / 2.0
            if min_x <= mid_x <= max_x and min_y <= mid_y <= max_y:
                horizontal_ys.append(mid_y)

    # 收集竖直网格线（x 值）
    vertical_xs: list[float] = []
    min_grid_length_v = height * 0.3
    for line in lines:
        if line.length < min_grid_length_v:
            continue
        angle = abs(line.angle_deg)
        if abs(angle - 90.0) <= tol:
            mid_x = (line.start_x + line.end_x) / 2.0
            mid_y = (line.start_y + line.end_y) / 2.0
            if min_x <= mid_x <= max_x and min_y <= mid_y <= max_y:
                vertical_xs.append(mid_x)

    # polyline 也贡献网格线（闭合矩形的边）
    for polyline in polylines:
        if not _polyline_in_audit_area(polyline, sheet):
            continue
        # 用 bbox 中心判断，简化处理
        mid_x = (polyline.bbox_min_x + polyline.bbox_max_x) / 2.0
        mid_y = (polyline.bbox_min_y + polyline.bbox_max_y) / 2.0
        if not (min_x <= mid_x <= max_x and min_y <= mid_y <= max_y):
            continue
        poly_width = polyline.bbox_max_x - polyline.bbox_min_x
        poly_height = polyline.bbox_max_y - polyline.bbox_min_y
        if poly_width > width * 0.3:
            horizontal_ys.append((polyline.bbox_min_y + polyline.bbox_max_y) / 2.0)
        if poly_height > height * 0.3:
            vertical_xs.append((polyline.bbox_min_x + polyline.bbox_max_x) / 2.0)

    rows = _cluster_values(sorted(horizontal_ys), _TABLE_GRID_LINE_TOL)
    cols = _cluster_values(sorted(vertical_xs), _TABLE_GRID_LINE_TOL)
    if len(rows) < _TABLE_MIN_ROWS or len(cols) < _TABLE_MIN_COLS:
        return None
    return rows, cols


def _cluster_values(values: list[float], tol: float) -> list[float]:
    if not values:
        return []
    clusters: list[list[float]] = [[values[0]]]
    for value in values[1:]:
        cluster = clusters[-1]
        if abs(value - cluster[-1]) <= tol:
            cluster.append(value)
        else:
            clusters.append([value])
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _build_cells(rows: list[float], cols: list[float]) -> list[dict[str, float]]:
    """行列交叉形成单元格 bbox。"""
    cells: list[dict[str, float]] = []
    sorted_rows = sorted(rows)
    sorted_cols = sorted(cols)
    for row_index in range(len(sorted_rows) - 1):
        for col_index in range(len(sorted_cols) - 1):
            cells.append(
                {
                    "row_index": row_index,
                    "col_index": col_index,
                    "min_x": sorted_cols[col_index],
                    "max_x": sorted_cols[col_index + 1],
                    "min_y": sorted_rows[row_index],
                    "max_y": sorted_rows[row_index + 1],
                }
            )
    return cells


def _assign_texts_to_cells(
    texts: list[TextItem],
    cells: list[dict[str, float]],
    sheet: SheetRecord,
) -> dict[tuple[int, int], list[TextItem]]:
    """把审计区内文本分配到单元格。"""
    cell_values: dict[tuple[int, int], list[TextItem]] = defaultdict(list)
    for text in texts:
        if not _text_in_audit_area(text, sheet):
            continue
        for cell in cells:
            if cell["min_x"] <= text.insert_x <= cell["max_x"] and cell["min_y"] <= text.insert_y <= cell["max_y"]:
                cell_values[(cell["row_index"], cell["col_index"])].append(text)
                break
    return cell_values


def _build_three_column_mappings(
    cell_values: dict[tuple[int, int], list[TextItem]],
    cols: list[float],
    rows: list[float],
    sheet: SheetRecord,
) -> list[dict[str, Any]]:
    """对三列表格生成映射记录。

    优先识别“表头前缀 + 行号”的表头型三列表格；未命中时回退到数值三列表格。
    """
    header_mappings = _build_header_semantic_mappings(cell_values, rows, sheet)
    if header_mappings:
        return header_mappings

    mappings: list[dict[str, Any]] = []
    row_count = len(rows) - 1
    for row_index in range(row_count):
        left_text = _numeric_cell_text(cell_values.get((row_index, 0), []))
        middle_text = _numeric_cell_text(cell_values.get((row_index, 1), []))
        right_text = _numeric_cell_text(cell_values.get((row_index, 2), []))
        if middle_text is None:
            continue
        middle_value = middle_text.normalized_text
        left_value = left_text.normalized_text if left_text is not None else None
        right_value = right_text.normalized_text if right_text is not None else None
        if not _looks_like_numeric_value(middle_value):
            continue
        if left_value is None and right_value is None:
            continue
        mappings.append(
            {
                "mapping_mode": "numeric_three_column",
                "sheet_id": sheet.sheet_id,
                "filename": sheet.filename,
                "sheet_no": sheet.sheet_no,
                "row_index": row_index,
                "left_value": left_value,
                "middle_value": middle_value,
                "right_value": right_value,
                "left_text_id": left_text.text_id if left_text is not None else None,
                "middle_text_id": middle_text.text_id,
                "right_text_id": right_text.text_id if right_text is not None else None,
                "left_coord": [left_text.insert_x, left_text.insert_y] if left_text is not None else None,
                "middle_coord": [middle_text.insert_x, middle_text.insert_y],
                "right_coord": [right_text.insert_x, right_text.insert_y] if right_text is not None else None,
                "column_roles": {
                    "left": "numeric_outer",
                    "middle": "numeric_center",
                    "right": "numeric_outer",
                },
            }
        )
    return mappings


def _build_header_semantic_mappings(
    cell_values: dict[tuple[int, int], list[TextItem]],
    rows: list[float],
    sheet: SheetRecord,
) -> list[dict[str, Any]]:
    row_count = len(rows) - 1
    if row_count < 2:
        return []

    header_text = _header_prefix_cell_text(cell_values.get((0, 1), []))
    header_prefix = header_text.normalized_text if header_text is not None else None
    if not _looks_like_header_prefix(header_prefix):
        return []

    mappings: list[dict[str, Any]] = []
    expected_row_number = 1
    for row_index in range(1, row_count):
        left_text = _endpoint_cell_text(cell_values.get((row_index, 0), []))
        middle_text = _numeric_cell_text(cell_values.get((row_index, 1), []))
        right_text = _endpoint_cell_text(cell_values.get((row_index, 2), []))
        if middle_text is None or not _looks_like_numeric_value(middle_text.normalized_text):
            return []

        row_number = int(middle_text.normalized_text)
        if row_number != expected_row_number:
            return []
        expected_row_number += 1

        left_endpoint_value = left_text.normalized_text if left_text is not None else None
        right_endpoint_value = right_text.normalized_text if right_text is not None else None
        if left_endpoint_value is None and right_endpoint_value is None:
            continue

        logical_endpoint = f"{header_prefix}{row_number}"
        mappings.append(
            {
                "mapping_mode": "header_semantic_three_column",
                "sheet_id": sheet.sheet_id,
                "filename": sheet.filename,
                "sheet_no": sheet.sheet_no,
                "row_index": row_index,
                "header_prefix": header_prefix,
                "header_text_id": header_text.text_id if header_text is not None else None,
                "header_coord": [header_text.insert_x, header_text.insert_y] if header_text is not None else None,
                "row_number": row_number,
                "middle_value": middle_text.normalized_text,
                "middle_text_id": middle_text.text_id,
                "middle_coord": [middle_text.insert_x, middle_text.insert_y],
                "logical_endpoint": logical_endpoint,
                "left_value": left_endpoint_value,
                "right_value": right_endpoint_value,
                "left_text_id": left_text.text_id if left_text is not None else None,
                "right_text_id": right_text.text_id if right_text is not None else None,
                "left_coord": [left_text.insert_x, left_text.insert_y] if left_text is not None else None,
                "right_coord": [right_text.insert_x, right_text.insert_y] if right_text is not None else None,
                "row_number_sequence_valid": True,
                "column_roles": {
                    "left": "terminal_endpoint",
                    "middle": "row_number",
                    "right": "terminal_endpoint",
                },
            }
        )
    return mappings


def _build_table_pairs(
    mapping: dict[str, Any],
    sheet: SheetRecord,
    pair_ids: IdFactory,
) -> list[Pair]:
    """把一条三列映射记录转成 Pair。

    - 数值三列表格：优先生成 中列 -> 右列，若右列缺失则生成 中列 -> 左列
    - 表头型三列表格：为同一行左右两侧接线端分别生成 `logical_endpoint -> endpoint`
    """
    if mapping.get("mapping_mode") == "header_semantic_three_column":
        return _build_header_semantic_pairs(mapping, sheet, pair_ids)

    middle_value = mapping.get("middle_value")
    right_value = mapping.get("right_value")
    left_value = mapping.get("left_value")
    if middle_value is None:
        return []
    # 优先中列->右列，其次中列->左列
    if right_value is not None:
        left_pair_value = middle_value
        right_pair_value = right_value
        left_text_id = mapping.get("middle_text_id")
        right_text_id = mapping.get("right_text_id")
        left_coord = mapping.get("middle_coord")
        right_coord = mapping.get("right_coord")
    elif left_value is not None:
        left_pair_value = left_value
        right_pair_value = middle_value
        left_text_id = mapping.get("left_text_id")
        right_text_id = mapping.get("middle_text_id")
        left_coord = mapping.get("left_coord")
        right_coord = mapping.get("middle_coord")
    else:
        return []

    pair_key = f"{left_pair_value}->{right_pair_value}"
    evidence = {
        "source": "table_mapping",
        "filename": sheet.filename,
        "sheet_no": sheet.sheet_no,
        "sheet_order": sheet.sheet_order,
        "sheet_title": sheet.sheet_title,
        "line_orientation": "table",
        "row_band_id": None,
        "left_side_label": "middle",
        "right_side_label": "outer",
        "table_mapping": mapping,
        "score_breakdown": {
            "left_score": 1.0,
            "right_score": 1.0,
            "wire_score": 1.0,
            "ambiguity_gap": None,
        },
    }
    return [
        Pair(
            pair_id=pair_ids.next(),
            line_group_id=None,
            sheet_id=sheet.sheet_id,
            file_id=sheet.file_id,
            selected_pair_candidate_id=None,
            left_value=left_pair_value,
            right_value=right_pair_value,
            confidence=_TABLE_PAIR_CONFIDENCE,
            status="pass",
            rationale="Three-column table mapping: middle column associated with outer column as high-confidence source.",
            alternative_pair_candidate_ids=[],
            confidence_bucket="high",
            evidence=evidence,
            left_text_id=left_text_id,
            right_text_id=right_text_id,
            left_coord_x=left_coord[0] if left_coord else None,
            left_coord_y=left_coord[1] if left_coord else None,
            right_coord_x=right_coord[0] if right_coord else None,
            right_coord_y=right_coord[1] if right_coord else None,
            pair_key=pair_key,
            left_score=1.0,
            right_score=1.0,
            wire_score=1.0,
            ambiguity_gap=None,
        )
    ]


def _build_header_semantic_pairs(
    mapping: dict[str, Any],
    sheet: SheetRecord,
    pair_ids: IdFactory,
) -> list[Pair]:
    logical_endpoint = mapping.get("logical_endpoint")
    if not logical_endpoint:
        return []

    pairs: list[Pair] = []
    for side_key, side_label in (("left_value", "left_endpoint"), ("right_value", "right_endpoint")):
        endpoint_value = mapping.get(side_key)
        if not endpoint_value:
            continue
        endpoint_text_id = mapping.get("left_text_id") if side_key == "left_value" else mapping.get("right_text_id")
        endpoint_coord = mapping.get("left_coord") if side_key == "left_value" else mapping.get("right_coord")
        evidence = {
            "source": "table_mapping",
            "filename": sheet.filename,
            "sheet_no": sheet.sheet_no,
            "sheet_order": sheet.sheet_order,
            "sheet_title": sheet.sheet_title,
            "line_orientation": "table",
            "row_band_id": None,
            "left_side_label": "logical_endpoint",
            "right_side_label": side_label,
            "table_mapping": mapping,
            "score_breakdown": {
                "left_score": 1.0,
                "right_score": 1.0,
                "wire_score": 1.0,
                "ambiguity_gap": None,
            },
        }
        pairs.append(
            Pair(
                pair_id=pair_ids.next(),
                line_group_id=None,
                sheet_id=sheet.sheet_id,
                file_id=sheet.file_id,
                selected_pair_candidate_id=None,
                left_value=logical_endpoint,
                right_value=endpoint_value,
                confidence=_TABLE_PAIR_CONFIDENCE,
                status="pass",
                rationale="Header semantic three-column table mapping: synthesized logical endpoint associated with row endpoint text.",
                alternative_pair_candidate_ids=[],
                confidence_bucket="high",
                evidence=evidence,
                left_text_id=mapping.get("middle_text_id"),
                right_text_id=endpoint_text_id,
                left_coord_x=(mapping.get("middle_coord") or [None, None])[0],
                left_coord_y=(mapping.get("middle_coord") or [None, None])[1],
                right_coord_x=endpoint_coord[0] if endpoint_coord else None,
                right_coord_y=endpoint_coord[1] if endpoint_coord else None,
                pair_key=f"{logical_endpoint}->{endpoint_value}",
                left_score=1.0,
                right_score=1.0,
                wire_score=1.0,
                ambiguity_gap=None,
            )
        )
    return pairs


def _primary_cell_text(texts: list[TextItem]) -> TextItem | None:
    if not texts:
        return None
    return sorted(texts, key=lambda item: (item.insert_y, item.insert_x, item.text_id))[0]


def _preferred_cell_text(
    texts: list[TextItem],
    *,
    predicate,
) -> TextItem | None:
    preferred = [
        text
        for text in sorted(texts, key=lambda item: (item.insert_y, item.insert_x, item.text_id))
        if predicate(text.normalized_text)
    ]
    if preferred:
        return preferred[0]
    return _primary_cell_text(texts)


def _numeric_cell_text(texts: list[TextItem]) -> TextItem | None:
    return _preferred_cell_text(texts, predicate=_looks_like_numeric_value)


def _header_prefix_cell_text(texts: list[TextItem]) -> TextItem | None:
    return _preferred_cell_text(texts, predicate=_looks_like_header_prefix)


def _endpoint_cell_text(texts: list[TextItem]) -> TextItem | None:
    preferred = _preferred_cell_text(texts, predicate=_looks_like_table_endpoint)
    if preferred is not None and _looks_like_table_endpoint(preferred.normalized_text):
        return preferred
    return None


def _looks_like_numeric_value(value: str | None) -> bool:
    return bool(value) and str(value).isdigit()


def _looks_like_header_prefix(value: str | None) -> bool:
    if not value or _looks_like_numeric_value(value):
        return False
    text = str(value)
    return bool(_HEADER_PREFIX_PATTERN.fullmatch(text)) and not text[-1].isdigit()


def _looks_like_table_endpoint(value: str | None) -> bool:
    if not value:
        return False
    return bool(_TERMINAL_ENDPOINT_PATTERN.fullmatch(str(value)))


def _group_by_sheet(items) -> dict[str, list]:
    grouped: dict[str, list] = defaultdict(list)
    for item in items:
        grouped[getattr(item, "sheet_id")].append(item)
    return grouped


def _polyline_in_audit_area(polyline: PolylineRecord, sheet: SheetRecord) -> bool:
    bbox = sheet.audit_area_bbox
    if bbox is None:
        return True
    min_x, min_y, max_x, max_y = bbox
    mid_x = (polyline.bbox_min_x + polyline.bbox_max_x) / 2.0
    mid_y = (polyline.bbox_min_y + polyline.bbox_max_y) / 2.0
    return min_x <= mid_x <= max_x and min_y <= mid_y <= max_y


def _text_in_audit_area(text: TextItem, sheet: SheetRecord) -> bool:
    bbox = sheet.audit_area_bbox
    if bbox is None:
        return True
    min_x, min_y, max_x, max_y = bbox
    return min_x <= text.insert_x <= max_x and min_y <= text.insert_y <= max_y
