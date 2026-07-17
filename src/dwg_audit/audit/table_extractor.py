"""TableExtractor 雏形（任务书第 4 章 113-121 行）。

针对表格型图，识别表格骨架、行、列、单元格，并重点支持两类三列表格：
- 数值三列表格：左列 / 中列 / 右列数字
- 表头型三列表格：表头前缀 + 中列行号 + 左右接线端

两者都生成高置信 `table_mapping` Pair，供 RuleEngine 作为独立信源参与跨页校验。

当前实现是最小骨架：
- 从 polylines + 长水平/竖直线推断表格网格线
- 按 y 聚类水平网格线 → 行；按 x 聚类竖直网格线 → 列
- 三列模式检测（列数 == 3）
- 命中网格表头型三列表格时，合成 `logical_endpoint = header_prefix + row_number`
- 屏端子图表头条带（terminal_header_table）合成 `logical_endpoint = header_prefix + "-" + row_number`
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
_TERMINAL_ENDPOINT_PATTERN = re.compile(r"(?i).*(?:[a-z]\d+(?:-\d+)?)$")
_BACKPLATE_HEADER_PATTERN = re.compile(r"^[A-Za-z]{2,}[0-9]+[A-Za-z]?(?:[（(].*[）)])?$")
_BACKPLATE_ENDPOINT_PATTERN = re.compile(
    r"^(?:[0-9](?:-[0-9]+)?[A-Za-z]{1,5}[0-9]+(?:-[0-9]+)?|[A-Za-z]{1,5}[0-9]+(?:-[0-9]+)?)$",
    re.IGNORECASE,
)
# Whole-device instance labels on composite PMU/测控 rear wiring sheets: "1-25n", "2-21n".
_DEVICE_INSTANCE_PATTERN = re.compile(r"^\d+-\d+[A-Za-z]$", re.IGNORECASE)
_DEVICE_INSTANCE_TITLE_PATTERN = re.compile(
    r"(?i)(?:REAR\s*WIRING|背板)[^\n]{0,24}?(\d+-\d+[A-Za-z])\b|(\d+-\d+[A-Za-z])\b[^\n]{0,16}(?:REAR\s*WIRING|背板)"
)
_PLUGIN_TITLE_PATTERN = re.compile(r"插件")
# Short English/Chinese bay titles used as plugin headers on 测控 rear wiring.
# Exact titles only — do not match row labels like Power+ / Power- / BI_Local+.
_PLUGIN_BAY_TITLE_PATTERN = re.compile(
    r"^(?:Power|Analog|Binary|CPU|AC|Output|Extend|交流|直流|开入|开出|电源|电压|电流)(?:插件)?$",
    re.IGNORECASE,
)
# Bay labels stamped beside slot numbers (e.g. "2 BI1", "3 BI2") on 测控 multi-bay backplates.
_PLUGIN_BAY_SHORT_TITLE_PATTERN = re.compile(r"^[A-Za-z]{1,8}\d{0,2}$")
_PLUGIN_SLOT_PATTERN = re.compile(r"^\d{1,2}$")
_BACKPLATE_ROW_Y_TOL = 2.0
_BACKPLATE_HEADER_X_TOL = 28.0
_BACKPLATE_HEADER_Y_SPAN = 90.0
_BACKPLATE_ENDPOINT_X_TOL = 28.0
_BACKPLATE_MIN_HEADER_ENDPOINT_HITS = 3
_BACKPLATE_PIN_ENDPOINT_X_TOL = 36.0
_BACKPLATE_PLUGIN_X_TOL = 55.0
_BACKPLATE_PLUGIN_Y_ABOVE = 45.0
# Vertical reach from bay title down to its pin lattice (Power 01..32 is ~80 units).
_BACKPLATE_PLUGIN_PIN_Y_BELOW = 95.0
_BACKPLATE_COLUMN_X_CLUSTER = 12.0
_BACKPLATE_BAY_HALF_WIDTH_DEFAULT = 40.0
_TERMINAL_HEADER_ROW_X_TOL = 8.0
_TERMINAL_HEADER_ROW_Y_SPAN = 260.0
_TERMINAL_HEADER_ENDPOINT_Y_TOL = 1.2
_TERMINAL_HEADER_ENDPOINT_X_TOL = 80.0
_TERMINAL_HEADER_MIN_ENDPOINT_HITS = 2
_TERMINAL_HEADER_MIN_ENDPOINT_ROW_RATIO = 0.5
_TERMINAL_HEADER_SHUOMING_Y_TOL = 4.0
_TERMINAL_HEADER_SHUOMING_X_TOL = 90.0
_TERMINAL_HEADER_DESCRIPTION_LABEL = "说明"
_TERMINAL_HEADER_SEMANTIC_ENDPOINTS = {
    "I0",
    "I0'",
    "IA",
    "UA",
    "UB",
    "UC",
    "UN",
    "3U0",
    "3U0'",
}


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

        if sheet.sheet_category == "背板接线图":
            mappings = _build_backplate_virtual_mappings(sheet_texts, sheet)
            if mappings:
                for mapping in mappings:
                    table_pairs.extend(_build_table_pairs(mapping, sheet, pair_ids))
                table_mappings.append(
                    {
                        "sheet_id": sheet_id,
                        "filename": sheet.filename,
                        "sheet_no": sheet.sheet_no,
                        "row_count": len(mappings),
                        "col_count": 0,
                        "three_column": False,
                        "mappings": mappings,
                    }
                )
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


def extract_terminal_header_table_pairs(
    texts: list[TextItem],
    sheets: list[SheetRecord],
    *,
    pair_id_factory: IdFactory | None = None,
) -> tuple[list[Pair], list[dict[str, Any]]]:
    """Recover header-prefix table mappings inside terminal pages.

    These pages remain terminal diagrams, but a rectangular region can behave
    like a table: header prefix + row number + same-row terminal endpoint.
    """

    texts_by_sheet = _group_by_sheet(texts)
    pair_ids = pair_id_factory or IdFactory("PTM")
    table_pairs: list[Pair] = []
    table_mappings: list[dict[str, Any]] = []

    for sheet in sheets:
        if sheet.sheet_category != "屏端子图":
            continue
        mappings = _build_terminal_header_table_mappings(texts_by_sheet.get(sheet.sheet_id, []), sheet)
        if not mappings:
            continue
        for mapping in mappings:
            table_pairs.extend(_build_table_pairs(mapping, sheet, pair_ids))
        table_mappings.append(
            {
                "sheet_id": sheet.sheet_id,
                "filename": sheet.filename,
                "sheet_no": sheet.sheet_no,
                "row_count": len(mappings),
                "col_count": 3,
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


def _build_terminal_header_table_mappings(
    texts: list[TextItem],
    sheet: SheetRecord,
) -> list[dict[str, Any]]:
    audit_texts = [text for text in texts if _text_in_audit_area(text, sheet)]
    headers = [text for text in audit_texts if _looks_like_header_prefix(text.normalized_text)]
    row_numbers = [text for text in audit_texts if _looks_like_numeric_value(text.normalized_text)]
    endpoints = [text for text in audit_texts if _looks_like_table_endpoint(text.normalized_text)]
    if not headers or not row_numbers or not endpoints:
        return []

    shuoming_labels = [
        text
        for text in audit_texts
        if str(text.normalized_text).strip() == _TERMINAL_HEADER_DESCRIPTION_LABEL
    ]
    terminal_headers = [
        text
        for text in headers
        if _looks_like_terminal_header_prefix(
            text.normalized_text,
            allow_plain=_find_terminal_header_shuoming(text, shuoming_labels) is not None,
        )
    ]
    if not terminal_headers:
        return []

    mappings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for header in sorted(terminal_headers, key=lambda item: (-item.insert_y, item.insert_x, item.text_id)):
        header_prefix = header.normalized_text
        shuoming = _find_terminal_header_shuoming(header, shuoming_labels)
        ordered_rows = _collect_terminal_header_rows(
            header,
            row_numbers,
            terminal_headers,
            allow_rows_above=shuoming is not None,
        )
        if not ordered_rows:
            continue

        if not _terminal_header_group_has_structure(ordered_rows, endpoints, has_shuoming=shuoming is not None):
            continue

        for row in ordered_rows:
            row_number = int(row.normalized_text)
            row_endpoints = _same_row_terminal_endpoints(row, endpoints, shuoming=shuoming)
            if not row_endpoints:
                continue
            logical_endpoint = _compose_terminal_header_logical_endpoint(header_prefix, row_number)
            for endpoint in row_endpoints:
                dedupe_key = (header.text_id, row.text_id, endpoint.text_id)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                side_key = "left" if endpoint.insert_x < row.insert_x else "right"
                mappings.append(
                    {
                        "mapping_mode": "terminal_header_table",
                        "sheet_id": sheet.sheet_id,
                        "filename": sheet.filename,
                        "sheet_no": sheet.sheet_no,
                        "header_prefix": header_prefix,
                        "header_text_id": header.text_id,
                        "header_coord": [header.insert_x, header.insert_y],
                        "row_number": row_number,
                        "middle_value": row.normalized_text,
                        "middle_text_id": row.text_id,
                        "middle_coord": [row.insert_x, row.insert_y],
                        "logical_endpoint": logical_endpoint,
                        "left_value": endpoint.normalized_text if side_key == "left" else None,
                        "right_value": endpoint.normalized_text if side_key == "right" else None,
                        "left_text_id": endpoint.text_id if side_key == "left" else None,
                        "right_text_id": endpoint.text_id if side_key == "right" else None,
                        "left_coord": [endpoint.insert_x, endpoint.insert_y] if side_key == "left" else None,
                        "right_coord": [endpoint.insert_x, endpoint.insert_y] if side_key == "right" else None,
                        "row_number_sequence_valid": True,
                        "has_shuoming_column": shuoming is not None,
                        "shuoming_text_id": shuoming.text_id if shuoming is not None else None,
                        "column_roles": {
                            "left": "terminal_endpoint" if side_key == "left" else "empty",
                            "middle": "row_number",
                            "right": "terminal_endpoint" if side_key == "right" else "empty",
                            "description": "shuoming" if shuoming is not None else "empty",
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
    if mapping.get("mapping_mode") in {"header_semantic_three_column", "backplate_virtual_table", "terminal_header_table"}:
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
        "pair_kind": "table_mapping",
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
            pair_kind="table_mapping",
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
            "pair_kind": "table_mapping",
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
                rationale=_table_pair_rationale(mapping),
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
                pair_kind="table_mapping",
            )
        )
    return pairs


def _table_pair_rationale(mapping: dict[str, Any]) -> str:
    if mapping.get("mapping_mode") == "backplate_virtual_table":
        if mapping.get("composite_device_instance"):
            return (
                "Composite backplate mapping: device instance scopes plugin pin codes "
                "to external terminal designators (e.g. 1-25KLP1-2 → 1-25n201)."
            )
        return "Backplate virtual table mapping: normalized block header plus row number associated with external terminal endpoint."
    if mapping.get("mapping_mode") == "terminal_header_table":
        return "Terminal header table mapping: synthesized header-row endpoint associated with same-row terminal text."
    return "Header semantic three-column table mapping: synthesized logical endpoint associated with row endpoint text."


def _build_backplate_virtual_mappings(
    texts: list[TextItem],
    sheet: SheetRecord,
) -> list[dict[str, Any]]:
    """Build mappings from backplate INSERT virtual rows to external terminal texts."""
    audit_texts = [text for text in texts if _text_in_audit_area(text, sheet)]
    virtual_texts = [text for text in audit_texts if text.source_block_name]
    if not virtual_texts:
        return []

    free_texts = [text for text in audit_texts if not text.source_block_name]
    device_instance = _resolve_backplate_device_instance(free_texts, sheet)
    headers = [text for text in virtual_texts if _looks_like_backplate_header(text.normalized_text)]
    rows = [text for text in virtual_texts if _looks_like_backplate_row_number(text.normalized_text)]
    endpoints = [
        text
        for text in free_texts
        if _looks_like_backplate_endpoint(_normalize_backplate_endpoint(text.normalized_text))
    ]
    if not rows or not endpoints:
        return []

    plugin_slots = _collect_backplate_plugin_slots(virtual_texts)
    _annotate_plugin_bay_bounds(plugin_slots)
    mappings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    used_endpoint_ids: set[str] = set()
    used_pin_ids: set[str] = set()

    # Composite PMU / 测控 rear wiring: pin lattice under whole-device instance name.
    # Prefer pin→external mappings scoped as {instance}{plugin}{pin:02d} so that
    # template headers (Ia1/LAN2) reused across plugin columns do not collide.
    # Power dual-column bays must not steal BI bay endpoints — bay bounds enforce this.
    # Keep classic header mappings (BI1/BI2) after composite for template-scoped keys.
    if device_instance and plugin_slots:
        composite_mappings = _build_composite_pin_grid_mappings(
            sheet=sheet,
            device_instance=device_instance,
            rows=rows,
            endpoints=endpoints,
            virtual_texts=virtual_texts,
            plugin_slots=plugin_slots,
            seen=seen,
            used_endpoint_ids=used_endpoint_ids,
            used_pin_ids=used_pin_ids,
        )
        if len(composite_mappings) >= _BACKPLATE_MIN_HEADER_ENDPOINT_HITS:
            mappings.extend(composite_mappings)

    if not headers and not mappings:
        return mappings

    headers_by_prefix: dict[str, list[TextItem]] = defaultdict(list)
    for header in headers:
        prefix = _normalize_backplate_header_prefix(header.normalized_text)
        if prefix:
            headers_by_prefix[prefix].append(header)

    for header in sorted(headers, key=lambda item: (item.source_block_name or "", -item.insert_y, item.insert_x, item.text_id)):
        header_prefix = _normalize_backplate_header_prefix(header.normalized_text)
        if not header_prefix:
            continue
        # Skip signal-name headers already covered as pin-grid bays (e.g. BI1 when
        # collected as plugin slot 2). Prefer instance/header form only when the bay
        # was not fully mapped by the composite pin lattice.
        header_rows = [
            row
            for row in rows
            if row.source_block_name == header.source_block_name
            and 0.0 < header.insert_y - row.insert_y <= _BACKPLATE_HEADER_Y_SPAN
            and abs(row.insert_x - header.insert_x) <= _BACKPLATE_HEADER_X_TOL
            and row.text_id not in used_pin_ids
        ]
        # Dual pin columns under one header must not become @c1 collision keys.
        # Only disambiguate when the same header_prefix is stamped on multiple bays.
        multi_bay_headers = headers_by_prefix.get(header_prefix) or [header]
        use_column_key = len(multi_bay_headers) > 1
        header_mappings: list[dict[str, Any]] = []
        for row in sorted(header_rows, key=lambda item: (-item.insert_y, item.insert_x, item.text_id)):
            endpoint = _nearest_backplate_endpoint(
                row,
                [item for item in endpoints if item.text_id not in used_endpoint_ids],
            )
            if endpoint is None:
                continue
            # When composite pin-grid already bound this pin text or endpoint, skip
            # the template header-row alias that floods cross-page scope reviews.
            if endpoint.text_id in used_endpoint_ids or any(
                mapping.get("middle_text_id") == row.text_id
                or mapping.get("right_text_id") == endpoint.text_id
                for mapping in mappings
            ):
                continue
            row_number = int(row.normalized_text)
            endpoint_value = _normalize_backplate_endpoint(endpoint.normalized_text)
            column_key = (
                _backplate_column_key(header.insert_x, multi_bay_headers)
                if use_column_key
                else None
            )
            # Only attach a plugin bay when the pin actually sits inside that bay —
            # distant CPU/Power fallbacks must not rewrite BI1-1 into 1-21n601.
            plugin = _nearest_plugin_slot(row.insert_x, row.insert_y, plugin_slots)
            if plugin is not None and not _point_in_plugin_bay(row.insert_x, row.insert_y, plugin):
                plugin = None
            # Prefer instance/header-row for classic template headers (BI1/NDY) so
            # multi-device pages keep stable human-readable scope keys.
            use_plugin_for_key = bool(
                plugin
                and plugin.get("slot") is not None
                and _plugin_title_is_pin_grid_bay(plugin.get("title"))
            )
            logical_endpoint = _compose_backplate_logical_endpoint(
                device_instance=device_instance,
                header_prefix=header_prefix,
                row_number=row_number,
                plugin_slot=plugin if use_plugin_for_key else None,
                column_key=column_key,
            )
            dedupe_key = (header.text_id, row.text_id, endpoint.text_id, logical_endpoint)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            used_endpoint_ids.add(endpoint.text_id)
            used_pin_ids.add(row.text_id)
            header_mappings.append(
                {
                    "mapping_mode": "backplate_virtual_table",
                    "sheet_id": sheet.sheet_id,
                    "filename": sheet.filename,
                    "sheet_no": sheet.sheet_no,
                    "source_block_name": header.source_block_name,
                    "header_prefix": header_prefix,
                    "raw_header_text": header.normalized_text,
                    "header_text_id": header.text_id,
                    "header_coord": [header.insert_x, header.insert_y],
                    "row_number": row_number,
                    "raw_row_number": row.normalized_text,
                    "middle_value": row.normalized_text,
                    "middle_text_id": row.text_id,
                    "middle_coord": [row.insert_x, row.insert_y],
                    "logical_endpoint": logical_endpoint,
                    "left_value": None,
                    "right_value": endpoint_value,
                    "left_text_id": None,
                    "right_text_id": endpoint.text_id,
                    "left_coord": None,
                    "right_coord": [endpoint.insert_x, endpoint.insert_y],
                    "row_number_sequence_valid": True,
                    "semantic_notes": _nearby_backplate_notes(row, virtual_texts),
                    "composite_device_instance": device_instance,
                    "plugin_slot": plugin.get("slot") if plugin else None,
                    "plugin_title": plugin.get("title") if plugin else None,
                    "column_key": column_key,
                    "column_roles": {
                        "left": "virtual_row_number",
                        "middle": "virtual_row_number",
                        "right": "external_terminal_endpoint",
                    },
                }
            )
        if len(header_mappings) < _BACKPLATE_MIN_HEADER_ENDPOINT_HITS:
            continue
        mappings.extend(header_mappings)
    return mappings


def _resolve_backplate_device_instance(
    free_texts: list[TextItem],
    sheet: SheetRecord,
) -> str | None:
    """Whole-device instance above plugin tables, e.g. 1-25n / 2-21n."""
    candidates: list[tuple[float, float, str]] = []
    for text in free_texts:
        value = str(text.normalized_text or "").strip()
        if _DEVICE_INSTANCE_PATTERN.fullmatch(value):
            candidates.append((-text.insert_y, text.insert_x, value))
    if candidates:
        candidates.sort()
        return candidates[0][2]

    for blob in (sheet.sheet_title or "", sheet.filename or ""):
        match = _DEVICE_INSTANCE_TITLE_PATTERN.search(blob)
        if match:
            return next(group for group in match.groups() if group)
        bare = re.search(r"(\d+-\d+[A-Za-z])\b", blob)
        if bare and _DEVICE_INSTANCE_PATTERN.fullmatch(bare.group(1)):
            return bare.group(1)
    return None


def _looks_like_plugin_bay_title(value: str | None) -> bool:
    if not value:
        return False
    text = str(value).strip()
    if not text or _looks_like_numeric_value(text):
        return False
    # Row labels such as Power+ / Power- / BI_Local+ are not bay titles.
    if any(ch in text for ch in "+-/"):
        return False
    # Single-letter phase labels (A..G) and common pin silkscreen names.
    if len(text) == 1:
        return False
    if re.fullmatch(r"(?i)(?:GND|TXD|RXD|LAN\d*|U[ABC]\d*|DC\d+|Print|Timing|TD\d*)", text):
        return False
    if _PLUGIN_BAY_TITLE_PATTERN.fullmatch(text):
        return True
    if _PLUGIN_TITLE_PATTERN.search(text) and len(text) <= 16:
        return True
    # "BI1" / "BI2" appear as bay titles next to slot numbers on 测控 backplates.
    if re.fullmatch(r"(?i)BI\d{1,2}", text):
        return True
    return False


def _plugin_title_is_pin_grid_bay(title: str | None) -> bool:
    """True when the bay should use instance+slot+pin keys (Power/开入), not BI headers."""
    if not title:
        return False
    text = str(title).strip()
    if _PLUGIN_BAY_TITLE_PATTERN.fullmatch(text):
        return True
    if _PLUGIN_TITLE_PATTERN.search(text):
        return True
    return False


def _is_plugin_bay_number(raw: str) -> bool:
    """Bay slot ids are 1..16 without leading zeros; pin codes use 01..32."""
    if not _PLUGIN_SLOT_PATTERN.fullmatch(raw):
        return False
    if len(raw) >= 2 and raw.startswith("0"):
        return False
    value = int(raw)
    return 1 <= value <= 16


def _collect_backplate_plugin_slots(virtual_texts: list[TextItem]) -> list[dict[str, Any]]:
    """Locate plugin bay labels (Power/BI1/开入插件) and bay numbers above pin columns."""
    titles = [
        text
        for text in virtual_texts
        if text.normalized_text and _looks_like_plugin_bay_title(text.normalized_text)
    ]
    slots: list[dict[str, Any]] = []
    seen_slot_keys: set[tuple[int | None, str, float, float]] = set()
    for title in titles:
        slot_number: int | None = None
        nearest_num: TextItem | None = None
        best_dx = _BACKPLATE_PLUGIN_X_TOL
        for text in virtual_texts:
            if text.source_block_name != title.source_block_name:
                continue
            raw = str(text.normalized_text or "").strip()
            if not _is_plugin_bay_number(raw):
                continue
            # Bay number sits on the same title row (e.g. "1  Power", "2  BI1").
            if abs(text.insert_y - title.insert_y) > 3.0:
                continue
            # Prefer numbers immediately left of the title.
            if text.insert_x > title.insert_x + 1.0:
                continue
            dx = abs(text.insert_x - title.insert_x)
            if dx > best_dx:
                continue
            best_dx = dx
            nearest_num = text
            slot_number = int(raw)
        # Numbered multi-bay tables need a real slot id; unnumbered titles are ignored
        # so they cannot collapse neighboring bay midlines.
        if slot_number is None:
            continue
        slot_x = (title.insert_x + nearest_num.insert_x) / 2.0 if nearest_num is not None else title.insert_x
        slot_key = (slot_number, str(title.normalized_text).strip(), round(slot_x, 1), round(title.insert_y, 1))
        if slot_key in seen_slot_keys:
            continue
        seen_slot_keys.add(slot_key)
        slots.append(
            {
                "slot": slot_number,
                "title": str(title.normalized_text).strip(),
                "title_text_id": title.text_id,
                "x": slot_x,
                "y": title.insert_y,
                "source_block_name": title.source_block_name,
            }
        )
    return slots


def _annotate_plugin_bay_bounds(plugin_slots: list[dict[str, Any]]) -> None:
    """Set left/right x bounds per plugin row so Power never reaches into BI bays."""
    # Group by y-row first: top Power/BI row and lower CPU/AC row must not squeeze each other.
    y_groups: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for slot in plugin_slots:
        if slot.get("slot") is None:
            slot["x_min"] = float(slot["x"]) - _BACKPLATE_BAY_HALF_WIDTH_DEFAULT
            slot["x_max"] = float(slot["x"]) + _BACKPLATE_BAY_HALF_WIDTH_DEFAULT
            continue
        y_key = round(float(slot["y"]) / 4.0) * 4.0
        y_groups[y_key].append(slot)

    for group in y_groups.values():
        ordered = sorted(group, key=lambda item: (float(item["x"]), int(item.get("slot") or 0)))
        for index, slot in enumerate(ordered):
            if index == 0:
                left = float(slot["x"]) - _BACKPLATE_BAY_HALF_WIDTH_DEFAULT
            else:
                left = (float(ordered[index - 1]["x"]) + float(slot["x"])) / 2.0
            if index + 1 >= len(ordered):
                right = float(slot["x"]) + _BACKPLATE_BAY_HALF_WIDTH_DEFAULT
            else:
                right = (float(slot["x"]) + float(ordered[index + 1]["x"])) / 2.0
            slot["x_min"] = left
            slot["x_max"] = right

    for slot in plugin_slots:
        if "x_min" not in slot:
            slot["x_min"] = float(slot["x"]) - _BACKPLATE_BAY_HALF_WIDTH_DEFAULT
            slot["x_max"] = float(slot["x"]) + _BACKPLATE_BAY_HALF_WIDTH_DEFAULT


def _point_in_plugin_bay(x: float, y: float, plugin: dict[str, Any]) -> bool:
    """Pin belongs to a bay if it is under the title and inside the bay x corridor."""
    x_min = float(plugin.get("x_min", plugin["x"] - _BACKPLATE_BAY_HALF_WIDTH_DEFAULT))
    x_max = float(plugin.get("x_max", plugin["x"] + _BACKPLATE_BAY_HALF_WIDTH_DEFAULT))
    if not (x_min <= x <= x_max):
        return False
    if y > float(plugin["y"]) + 1.5:
        return False
    if float(plugin["y"]) - y > _BACKPLATE_PLUGIN_PIN_Y_BELOW:
        return False
    return True


def _nearest_plugin_slot(
    x: float,
    y: float,
    plugin_slots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not plugin_slots:
        return None
    # Prefer bay-bound membership first — prevents Power stealing BI pins.
    in_bay = [slot for slot in plugin_slots if _point_in_plugin_bay(x, y, slot)]
    if in_bay:
        return sorted(
            in_bay,
            key=lambda slot: (abs(float(slot["x"]) - x), abs(float(slot["y"]) - y), slot.get("slot") or 99),
        )[0]

    candidates = [
        slot
        for slot in plugin_slots
        if 0.0 <= (float(slot["y"]) - y) <= _BACKPLATE_PLUGIN_PIN_Y_BELOW
        and abs(float(slot["x"]) - x) <= _BACKPLATE_PLUGIN_X_TOL
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda slot: (abs(float(slot["x"]) - x), abs(float(slot["y"]) - y), slot.get("slot") or 99),
    )[0]


def _backplate_column_key(x: float, peer_headers: list[TextItem]) -> str:
    """Stable bay id when the same header text is stamped on multiple plugin bays."""
    xs = sorted(
        {
            round(item.insert_x / _BACKPLATE_COLUMN_X_CLUSTER) * _BACKPLATE_COLUMN_X_CLUSTER
            for item in peer_headers
        }
    )
    if not xs:
        return f"x{int(round(x))}"
    nearest = min(xs, key=lambda value: abs(value - x))
    return f"c{xs.index(nearest)}"


def _compose_backplate_logical_endpoint(
    *,
    device_instance: str | None,
    header_prefix: str | None,
    row_number: int,
    plugin_slot: dict[str, Any] | None,
    column_key: str | None,
) -> str:
    """Compose a scope-stable logical endpoint for composite / multi-bay backplates."""
    pin = f"{row_number:02d}"
    slot = plugin_slot.get("slot") if plugin_slot else None
    if device_instance and slot is not None:
        # Matches field convention seen elsewhere: 1-25n201 = instance + bay + pin.
        return f"{device_instance}{slot}{pin}"
    if device_instance and header_prefix:
        if column_key:
            return f"{device_instance}/{header_prefix}-{row_number}@{column_key}"
        return f"{device_instance}/{header_prefix}-{row_number}"
    if header_prefix:
        if column_key:
            return f"{header_prefix}-{row_number}@{column_key}"
        return f"{header_prefix}-{row_number}"
    if device_instance:
        return f"{device_instance}{pin}"
    return pin


def _build_composite_pin_grid_mappings(
    *,
    sheet: SheetRecord,
    device_instance: str,
    rows: list[TextItem],
    endpoints: list[TextItem],
    virtual_texts: list[TextItem],
    plugin_slots: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    used_endpoint_ids: set[str] | None = None,
    used_pin_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Map plugin pin codes next to external designators under a device instance."""
    used_endpoint_ids = used_endpoint_ids if used_endpoint_ids is not None else set()
    used_pin_ids = used_pin_ids if used_pin_ids is not None else set()

    # Only pin-grid bays (Power/CPU/开入) use instance+slot+pin keys. BI1/BI2 stay
    # as header-scoped keys via the classic header path.
    pin_grid_slots = [
        slot
        for slot in plugin_slots
        if slot.get("slot") is not None and _plugin_title_is_pin_grid_bay(slot.get("title"))
    ]
    if not pin_grid_slots:
        return []

    # Assign candidate pins to the nearest numbered plugin bay first so Power/BI
    # dual columns do not steal endpoints from the neighboring bay.
    pins_by_plugin: dict[str, list[TextItem]] = defaultdict(list)
    plugin_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.text_id in used_pin_ids:
            continue
        plugin = _nearest_plugin_slot(row.insert_x, row.insert_y, pin_grid_slots)
        if plugin is None or plugin.get("slot") is None:
            continue
        if not _point_in_plugin_bay(row.insert_x, row.insert_y, plugin):
            continue
        plugin_id = f"{plugin.get('title')}|{plugin.get('slot')}|{plugin.get('x')}"
        plugin_by_id[plugin_id] = plugin
        pins_by_plugin[plugin_id].append(row)

    mappings: list[dict[str, Any]] = []
    for plugin_id, plugin_rows in pins_by_plugin.items():
        plugin = plugin_by_id[plugin_id]
        bay_min = float(plugin.get("x_min", plugin["x"] - _BACKPLATE_BAY_HALF_WIDTH_DEFAULT))
        bay_max = float(plugin.get("x_max", plugin["x"] + _BACKPLATE_BAY_HALF_WIDTH_DEFAULT))
        pin_xs = [row.insert_x for row in plugin_rows]
        # Endpoint corridor: pin span padded, but never across bay midlines.
        min_x = max(bay_min, min(pin_xs) - _BACKPLATE_PIN_ENDPOINT_X_TOL)
        max_x = min(bay_max, max(pin_xs) + _BACKPLATE_PIN_ENDPOINT_X_TOL)
        median_x = sorted(pin_xs)[len(pin_xs) // 2]
        local_endpoints = [
            endpoint
            for endpoint in endpoints
            if endpoint.text_id not in used_endpoint_ids and min_x <= endpoint.insert_x <= max_x
        ]
        for row in sorted(plugin_rows, key=lambda item: (-item.insert_y, item.insert_x, item.text_id)):
            # Dual-column tables: left pin column prefers left-side designators,
            # right column prefers right-side (matches Power 01..32 layout).
            prefer_left = row.insert_x <= median_x
            endpoint = _nearest_backplate_endpoint_sided(
                row,
                local_endpoints,
                prefer_left=prefer_left,
                x_tol=_BACKPLATE_PIN_ENDPOINT_X_TOL,
            )
            if endpoint is None:
                # Do not fall back to the opposite side — empty Power rows must stay empty
                # rather than steal a BI bay designator.
                continue
            if endpoint.text_id in used_endpoint_ids:
                continue
            row_number = int(row.normalized_text)
            endpoint_value = _normalize_backplate_endpoint(endpoint.normalized_text)
            logical_endpoint = _compose_backplate_logical_endpoint(
                device_instance=device_instance,
                header_prefix=None,
                row_number=row_number,
                plugin_slot=plugin,
                column_key=None,
            )
            dedupe_key = ("pin-grid", row.text_id, endpoint.text_id, logical_endpoint)
            if dedupe_key in seen:
                continue
            if any(key[0] == "pin-grid" and key[1] == row.text_id for key in seen):
                continue
            seen.add(dedupe_key)
            used_endpoint_ids.add(endpoint.text_id)
            used_pin_ids.add(row.text_id)
            local_endpoints = [item for item in local_endpoints if item.text_id != endpoint.text_id]
            mappings.append(
                {
                    "mapping_mode": "backplate_virtual_table",
                    "sheet_id": sheet.sheet_id,
                    "filename": sheet.filename,
                    "sheet_no": sheet.sheet_no,
                    "source_block_name": row.source_block_name,
                    "header_prefix": f"{device_instance}{plugin['slot']}",
                    "raw_header_text": plugin.get("title") or f"plugin-{plugin['slot']}",
                    "header_text_id": plugin.get("title_text_id"),
                    "header_coord": [plugin["x"], plugin["y"]],
                    "row_number": row_number,
                    "raw_row_number": row.normalized_text,
                    "middle_value": row.normalized_text,
                    "middle_text_id": row.text_id,
                    "middle_coord": [row.insert_x, row.insert_y],
                    "logical_endpoint": logical_endpoint,
                    "left_value": None,
                    "right_value": endpoint_value,
                    "left_text_id": None,
                    "right_text_id": endpoint.text_id,
                    "left_coord": None,
                    "right_coord": [endpoint.insert_x, endpoint.insert_y],
                    "row_number_sequence_valid": True,
                    "semantic_notes": _nearby_backplate_notes(row, virtual_texts),
                    "composite_device_instance": device_instance,
                    "plugin_slot": plugin.get("slot"),
                    "plugin_title": plugin.get("title"),
                    "column_roles": {
                        "left": "virtual_row_number",
                        "middle": "virtual_row_number",
                        "right": "external_terminal_endpoint",
                    },
                }
            )
    return mappings


def _nearest_backplate_endpoint_sided(
    row: TextItem,
    endpoints: list[TextItem],
    *,
    prefer_left: bool,
    x_tol: float = _BACKPLATE_PIN_ENDPOINT_X_TOL,
) -> TextItem | None:
    """Nearest same-row endpoint on the preferred side of a dual pin column."""
    same_row = []
    for endpoint in endpoints:
        if abs(endpoint.insert_y - row.insert_y) > _BACKPLATE_ROW_Y_TOL:
            continue
        dx = endpoint.insert_x - row.insert_x
        if abs(dx) > x_tol or abs(dx) < 1e-6:
            continue
        if prefer_left and dx > 0:
            continue
        if not prefer_left and dx < 0:
            continue
        same_row.append(endpoint)
    if not same_row:
        return None
    return sorted(
        same_row,
        key=lambda endpoint: (
            abs(endpoint.insert_x - row.insert_x),
            abs(endpoint.insert_y - row.insert_y),
            endpoint.text_id,
        ),
    )[0]


def _nearest_backplate_endpoint(
    row: TextItem,
    endpoints: list[TextItem],
    *,
    x_tol: float = _BACKPLATE_ENDPOINT_X_TOL,
) -> TextItem | None:
    same_row = [
        endpoint
        for endpoint in endpoints
        if abs(endpoint.insert_y - row.insert_y) <= _BACKPLATE_ROW_Y_TOL
        and abs(endpoint.insert_x - row.insert_x) <= x_tol
    ]
    if not same_row:
        return None
    return sorted(
        same_row,
        key=lambda endpoint: (abs(endpoint.insert_x - row.insert_x), abs(endpoint.insert_y - row.insert_y), endpoint.text_id),
    )[0]


def _nearby_backplate_notes(row: TextItem, virtual_texts: list[TextItem]) -> list[str]:
    notes: list[str] = []
    for text in virtual_texts:
        value = text.normalized_text
        if text.text_id == row.text_id or _looks_like_backplate_row_number(value) or _looks_like_backplate_header(value):
            continue
        if abs(text.insert_y - row.insert_y) <= _BACKPLATE_ROW_Y_TOL and abs(text.insert_x - row.insert_x) <= 25.0:
            notes.append(value)
        if len(notes) >= 3:
            break
    return notes


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
    text = str(value).strip().upper()
    if text in _TERMINAL_HEADER_SEMANTIC_ENDPOINTS:
        return False
    return bool(_TERMINAL_ENDPOINT_PATTERN.fullmatch(text))


def _looks_like_terminal_header_prefix(
    value: str | None,
    *,
    allow_plain: bool = False,
) -> bool:
    if not _looks_like_header_prefix(value):
        return False
    text = str(value).strip()
    if not re.search(r"(?i)[A-Z]+$", text):
        return False
    if any(char.isdigit() for char in text):
        return True
    # Plain instance names such as YD are authoritative only when the caller
    # has already found an adjacent 说明 header. Semantic labels remain excluded.
    return (
        allow_plain
        and bool(re.fullmatch(r"[A-Za-z]{2,6}", text))
        and text.upper() not in _TERMINAL_HEADER_SEMANTIC_ENDPOINTS
    )


def _compose_terminal_header_logical_endpoint(header_prefix: str, row_number: int) -> str:
    """Compose panel terminal logical keys as header + '-' + row (e.g. 1C5D-10)."""
    return f"{header_prefix}-{row_number}"


def _collect_terminal_header_rows(
    header: TextItem,
    row_numbers: list[TextItem],
    terminal_headers: list[TextItem],
    *,
    allow_rows_above: bool = False,
) -> list[TextItem]:
    """Collect consecutive middle-column rows owned by one header strip.

    Multi-strip terminal pages stack several header blocks in the same x column
    (1C4D / 1C5D / 1C6D). Rows belonging to the next header below must not be
    absorbed into the upper group, otherwise 1..13 + 1..13 fails sequence checks.
    """
    next_header_y: float | None = None
    previous_header_y: float | None = None
    for other in terminal_headers:
        if other.text_id == header.text_id:
            continue
        if abs(other.insert_x - header.insert_x) > _TERMINAL_HEADER_ROW_X_TOL:
            continue
        if other.insert_y < header.insert_y:
            if next_header_y is None or other.insert_y > next_header_y:
                next_header_y = other.insert_y
        elif other.insert_y > header.insert_y:
            if previous_header_y is None or other.insert_y < previous_header_y:
                previous_header_y = other.insert_y

    rows_below = [
        row
        for row in row_numbers
        if 0.0 < header.insert_y - row.insert_y <= _TERMINAL_HEADER_ROW_Y_SPAN
        and abs(row.insert_x - header.insert_x) <= _TERMINAL_HEADER_ROW_X_TOL
        and (next_header_y is None or row.insert_y > next_header_y)
    ]
    candidates = [
        _take_leading_consecutive_terminal_rows(
            sorted(rows_below, key=lambda item: (-item.insert_y, item.insert_x, item.text_id))
        )
    ]

    # Some terminal strips place the instance header and 说明 footer below rows
    # 1..N in world coordinates. Only the explicit 说明 anchor authorizes this
    # reverse ownership, so unrelated numeric columns are not promoted.
    if allow_rows_above and not candidates[0]:
        rows_above = [
            row
            for row in row_numbers
            if 0.0 < row.insert_y - header.insert_y <= _TERMINAL_HEADER_ROW_Y_SPAN
            and abs(row.insert_x - header.insert_x) <= _TERMINAL_HEADER_ROW_X_TOL
            and (previous_header_y is None or row.insert_y < previous_header_y)
        ]
        candidates.append(
            _take_leading_consecutive_terminal_rows(
                sorted(rows_above, key=lambda item: (-item.insert_y, item.insert_x, item.text_id))
            )
        )

    return max(candidates, key=len)


def _take_leading_consecutive_terminal_rows(rows: list[TextItem]) -> list[TextItem]:
    """Keep only the leading 1..N run so a restarted strip cannot pollute the group."""
    taken: list[TextItem] = []
    expected = 1
    for row in rows:
        if not str(row.normalized_text).isdigit():
            break
        value = int(row.normalized_text)
        if value != expected:
            break
        taken.append(row)
        expected += 1
    return taken if expected > 2 else []


def _terminal_rows_start_at_one(rows: list[TextItem]) -> bool:
    expected = 1
    for row in rows:
        if not row.normalized_text.isdigit():
            return False
        value = int(row.normalized_text)
        if value != expected:
            return False
        expected += 1
    return expected > 2


def _find_terminal_header_shuoming(
    header: TextItem,
    shuoming_labels: list[TextItem],
) -> TextItem | None:
    """Locate the nearby 说明 column header that marks a three-column terminal strip."""
    candidates = [
        label
        for label in shuoming_labels
        if abs(label.insert_y - header.insert_y) <= _TERMINAL_HEADER_SHUOMING_Y_TOL
        and 0.0 < abs(label.insert_x - header.insert_x) <= _TERMINAL_HEADER_SHUOMING_X_TOL
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (abs(item.insert_x - header.insert_x), abs(item.insert_y - header.insert_y), item.text_id),
    )[0]


def _terminal_header_group_has_structure(
    rows: list[TextItem],
    endpoints: list[TextItem],
    *,
    has_shuoming: bool = False,
) -> bool:
    endpoint_counts = [len(_same_row_terminal_endpoints(row, endpoints)) for row in rows]
    endpoint_hit_count = sum(endpoint_counts)
    # 说明 locks the three-column strip identity; slightly looser endpoint density is ok.
    min_hits = _TERMINAL_HEADER_MIN_ENDPOINT_HITS
    if has_shuoming:
        min_hits = max(1, _TERMINAL_HEADER_MIN_ENDPOINT_HITS - 1)
    if endpoint_hit_count < min_hits:
        return False

    rows_with_endpoint = sum(1 for count in endpoint_counts if count > 0)
    if any(count >= _TERMINAL_HEADER_MIN_ENDPOINT_HITS for count in endpoint_counts):
        return True
    min_ratio = _TERMINAL_HEADER_MIN_ENDPOINT_ROW_RATIO
    if has_shuoming:
        min_ratio = min(min_ratio, 0.35)
    return rows_with_endpoint / len(rows) >= min_ratio and rows_with_endpoint >= 2


def _same_row_terminal_endpoints(
    row: TextItem,
    endpoints: list[TextItem],
    *,
    shuoming: TextItem | None = None,
) -> list[TextItem]:
    same_row = [
        endpoint
        for endpoint in endpoints
        if endpoint.text_id != row.text_id
        and abs(endpoint.insert_y - row.insert_y) <= _TERMINAL_HEADER_ENDPOINT_Y_TOL
        and 0.0 < abs(endpoint.insert_x - row.insert_x) <= _TERMINAL_HEADER_ENDPOINT_X_TOL
        and not _endpoint_beyond_shuoming_column(row, endpoint, shuoming)
    ]
    return sorted(same_row, key=lambda item: (abs(item.insert_x - row.insert_x), item.insert_x, item.text_id))


def _endpoint_beyond_shuoming_column(
    row: TextItem,
    endpoint: TextItem,
    shuoming: TextItem | None,
) -> bool:
    """Reject texts that sit past the 说明 column (description/notes, not terminal ends)."""
    if shuoming is None:
        return False
    # 说明 is typically on one side of the middle row column; endpoints live between
    # the row number and that label (or on the opposite outer side).
    shuoming_side = 1.0 if shuoming.insert_x >= row.insert_x else -1.0
    endpoint_side = 1.0 if endpoint.insert_x >= row.insert_x else -1.0
    if endpoint_side != shuoming_side:
        return False
    # Same side as 说明: keep only candidates between the middle column and 说明.
    if shuoming_side > 0:
        return endpoint.insert_x >= shuoming.insert_x
    return endpoint.insert_x <= shuoming.insert_x


def _normalize_backplate_header_prefix(value: str | None) -> str | None:
    if not value:
        return None
    prefix = re.split(r"[（(]", str(value).strip(), maxsplit=1)[0].strip()
    return prefix if _BACKPLATE_HEADER_PATTERN.fullmatch(prefix) else None


def _normalize_backplate_endpoint(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"^[^0-9A-Za-z]+", "", str(value).strip()).replace(" ", "")


def _looks_like_backplate_header(value: str | None) -> bool:
    return _normalize_backplate_header_prefix(value) is not None


def _looks_like_backplate_row_number(value: str | None) -> bool:
    if not value or not str(value).isdigit():
        return False
    number = int(str(value))
    return 1 <= number <= 64 and len(str(value)) <= 2


def _looks_like_backplate_endpoint(value: str | None) -> bool:
    if not value:
        return False
    return bool(_BACKPLATE_ENDPOINT_PATTERN.fullmatch(str(value).strip()))


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
