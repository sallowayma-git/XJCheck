from __future__ import annotations

import math
import re
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SwConnectDot
from dwg_audit.domain.models import SwPort
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_ORIENTATION_HORIZONTAL = "horizontal"
_ORIENTATION_VERTICAL = "vertical"
_ORIENTATION_GRID = "grid"
_SIGNAL_INLINE_BRIDGE_GAP = 20.0
_NAMED_COMPONENT_BARRIER_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,11}$", re.IGNORECASE)
# A wire end "sits on" a SuperWORKS port when it lies within this distance of the port marker.
_TERMINAL_TOUCH_TOLERANCE = 1.0
# A text or connect dot counts as inside an empty gap when it reaches this far past either gap end.
_GAP_EDGE_MARGIN = 0.6
# WIRE-BREAK: a symbol body is spanned by two TERMPOINT marks of one symbol, one on each side of a gap.
# A gap narrower than this is not a two-port body (three-pin symbols have a 1.25 pitch) and is kept merged.
SYMBOL_MIN_BODY_WIDTH = 2.0
_MARK_CELL = 5.0
# Unknown-shape reason codes (sw_topology_unknown.parquet). The gap keeps its legacy decision for each.
UNKNOWN_DOT_IN_SYMBOL_GAP = "dot_in_symbol_gap"
UNKNOWN_BODY_WIDTH_BELOW_MIN = "body_width_below_min"
UNKNOWN_NODE_MULTI_SYMBOL = "node_multi_symbol_at_end"


@dataclass(frozen=True)
class WireBreakEvidence:
    """One sheet's SuperWORKS evidence for telling a real wire break from a merged wire.

    ports: (record_id, x1, y1, x2, y2) marker segments of the sheet's SuperWORKS ports (G2).
    dots: (x, y) centers of the sheet's LD_CONNECT_DOT junction markers.
    marks: (symbol_key, record_id, x1, y1, x2, y2) TERMPOINT marks of every symbol of the sheet: registered
        SuperWORKS ports and TERMPOINTs of unregistered SYMB2 blocks. Marks of one symbol share symbol_key.
    stats / log: filled while the line groups are built (cut counts; unknown-shape rows for the audit table).
    """

    ports: tuple[tuple[str, float, float, float, float], ...] = ()
    dots: tuple[tuple[float, float], ...] = ()
    marks: tuple[tuple[str, str, float, float, float, float], ...] = ()
    stats: Counter = field(default_factory=Counter, compare=False)
    log: list = field(default_factory=list, compare=False)
    cuts: list = field(default_factory=list, compare=False)


def wire_break_evidence_by_sheet(
    ports: Iterable[SwPort] | None,
    connect_dots: Iterable[SwConnectDot] | None,
    unregistered: Iterable[dict[str, Any]] | None = None,
) -> dict[str, WireBreakEvidence]:
    """Group SuperWORKS ports, connect dots and unregistered SYMB2 TERMPOINTs by sheet_id.

    unregistered: the SuperworksData.unregistered_symb2 records (each with file_id, sheet_id, instance_path and
    termpoints [{number, a, b}]). Their symbol key uses the same format as a registered port's symbol_id.
    """
    port_rows: dict[str, list[tuple[str, float, float, float, float]]] = defaultdict(list)
    mark_rows: dict[str, list[tuple[str, str, float, float, float, float]]] = defaultdict(list)
    for port in ports or []:
        segment = (float(port.start_x), float(port.start_y), float(port.end_x), float(port.end_y))
        port_rows[port.sheet_id].append((port.record_id, *segment))
        symbol_key = port.symbol_id or f"PORT:{port.record_id}"
        mark_rows[port.sheet_id].append((symbol_key, port.record_id, *segment))
    for block in unregistered or []:
        sheet_id = str(block.get("sheet_id") or "")
        symbol_key = f"SW:{block.get('file_id')}:{sheet_id}:{block.get('instance_path')}"
        for termpoint in block.get("termpoints") or []:
            (ax, ay), (bx, by) = termpoint.get("a") or (0.0, 0.0), termpoint.get("b") or (0.0, 0.0)
            record_id = f"{block.get('record_id')}#{termpoint.get('number')}"
            mark_rows[sheet_id].append((symbol_key, record_id, float(ax), float(ay), float(bx), float(by)))
    dot_rows: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for dot in connect_dots or []:
        dot_rows[dot.sheet_id].append((float(dot.x), float(dot.y)))
    sheet_ids = set(port_rows) | set(dot_rows) | set(mark_rows)
    return {
        sheet_id: WireBreakEvidence(
            ports=tuple(port_rows.get(sheet_id, ())),
            dots=tuple(dot_rows.get(sheet_id, ())),
            marks=tuple(mark_rows.get(sheet_id, ())),
        )
        for sheet_id in sheet_ids
    }


class _MarkIndex:
    """Grid index of symbol TERMPOINT marks: which marks lie within the touch tolerance of a point."""

    def __init__(self, marks: tuple[tuple[str, str, float, float, float, float], ...]) -> None:
        self._cells: dict[tuple[int, int], list[tuple[str, str, float, float, float, float]]] = defaultdict(list)
        pad = _TERMINAL_TOUCH_TOLERANCE
        for mark in marks:
            _, _, x1, y1, x2, y2 = mark
            lo_x, hi_x = min(x1, x2) - pad, max(x1, x2) + pad
            lo_y, hi_y = min(y1, y2) - pad, max(y1, y2) + pad
            for cx in range(math.floor(lo_x / _MARK_CELL), math.floor(hi_x / _MARK_CELL) + 1):
                for cy in range(math.floor(lo_y / _MARK_CELL), math.floor(hi_y / _MARK_CELL) + 1):
                    self._cells[(cx, cy)].append(mark)

    def overlapping(self, x0: float, y0: float, x1: float, y1: float) -> list[tuple[str, str, float, float, float, float]]:
        """Marks whose bounding box overlaps the rectangle (x0, y0)-(x1, y1), each once."""
        found: dict[tuple[str, str], tuple[str, str, float, float, float, float]] = {}
        for cx in range(math.floor(min(x0, x1) / _MARK_CELL), math.floor(max(x0, x1) / _MARK_CELL) + 1):
            for cy in range(math.floor(min(y0, y1) / _MARK_CELL), math.floor(max(y0, y1) / _MARK_CELL) + 1):
                for mark in self._cells.get((cx, cy), ()):
                    key, record_id, mx1, my1, mx2, my2 = mark
                    if max(mx1, mx2) < min(x0, x1) or min(mx1, mx2) > max(x0, x1):
                        continue
                    if max(my1, my2) < min(y0, y1) or min(my1, my2) > max(y0, y1):
                        continue
                    found[(key, record_id)] = mark
        return list(found.values())


def _point_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _point_in_bbox(x: float, y: float, bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return True
    min_x, min_y, max_x, max_y = bbox
    return min_x <= x <= max_x and min_y <= y <= max_y


def build_line_groups(
    lines: list[LineEntity],
    sheets: list[SheetRecord],
    config: dict,
    texts: list[TextItem] | None = None,
    classifications: dict[str, PageClassification] | None = None,
    group_id_factory: IdFactory | None = None,
    band_id_factory: IdFactory | None = None,
    wire_break_evidence: dict[str, WireBreakEvidence] | None = None,
) -> list[LineGroup]:
    by_sheet = defaultdict(list)
    for line in lines:
        by_sheet[line.sheet_id].append(line)
    by_sheet_texts = defaultdict(list)
    for text in texts or []:
        by_sheet_texts[text.sheet_id].append(text)
    sheet_map = {sheet.sheet_id: sheet for sheet in sheets}
    group_ids = group_id_factory or IdFactory("G")
    band_ids = band_id_factory or IdFactory("RB")
    result: list[LineGroup] = []

    tol = float(config.get("geometry", {}).get("horizontal_angle_tolerance_deg", 2.0))
    min_length = float(config.get("geometry", {}).get("min_wire_length", 12.0))
    y_tol = float(config.get("geometry", {}).get("line_y_tolerance", 1.8))
    gap_tol = float(config.get("geometry", {}).get("line_gap_tolerance", 4.0))
    inline_bridge_gap = float(config.get("geometry", {}).get("inline_numeric_bridge_gap", 12.0))
    inline_bridge_y_tol = float(config.get("geometry", {}).get("inline_numeric_bridge_y_tolerance", 4.0))
    grid_band_tol = float(config.get("geometry", {}).get("grid_band_y_tolerance", 5.0))

    for sheet_id, sheet_lines in by_sheet.items():
        sheet = sheet_map.get(sheet_id)
        if sheet is None or not sheet.is_primary_audit_candidate or sheet.audit_area_bbox is None:
            continue
        sheet_texts = by_sheet_texts.get(sheet_id, [])
        sheet_break_evidence = (wire_break_evidence or {}).get(sheet_id)
        sheet_inline_bridge_gap = _inline_bridge_gap_for_sheet(sheet, inline_bridge_gap)
        classification = classifications.get(sheet_id) if classifications else None
        orientation = _resolve_orientation(
            sheet_lines,
            sheet,
            config,
            tol,
            min_length,
            classification=classification,
        )
        # grid 模式需要水平线做行带聚类；vertical 需要竖直线；horizontal 需要水平线
        candidate_orientation = _ORIENTATION_HORIZONTAL if orientation == _ORIENTATION_GRID else orientation
        candidates = _line_candidates(sheet_lines, sheet, candidate_orientation, tol, min_length)
        candidates = _filter_component_vertical_length_outliers(candidates, sheet, orientation)
        # WIRE-BREAK: gaps that are symbol bodies (two TERMPOINTs of one symbol on the two sides) never merge.
        symbol_cuts = _symbol_body_cuts(
            candidates,
            sheet_break_evidence,
            sheet,
            candidate_orientation,
            max_gap=sheet_inline_bridge_gap,
            cross_tol=y_tol,
        )
        if sheet_break_evidence is not None and symbol_cuts:
            sheet_break_evidence.cuts.extend(symbol_cuts)

        if orientation == _ORIENTATION_GRID:
            grid_groups = _build_grid_row_bands(
                candidates,
                sheet,
                sheet_id,
                sheet.file_id,
                group_ids,
                band_ids,
                sheet_texts,
                gap_tol,
                y_tol,
                sheet_inline_bridge_gap,
                inline_bridge_y_tol,
                wire_break_evidence=sheet_break_evidence,
                symbol_cuts=symbol_cuts,
            )
            result.extend(grid_groups)
            continue

        candidates.sort(key=lambda item: (round(item["cross_axis"], 3), item["start_axis"]))
        active: list[dict] = []
        for candidate in candidates:
            cross_axis = candidate["cross_axis"]
            start_axis = candidate["start_axis"]
            end_axis = candidate["end_axis"]
            line = candidate["line"]
            placed = False
            for group in active:
                if _can_merge_axis_intervals(
                    group["start_axis"],
                    group["end_axis"],
                    group["cross_axis"],
                    start_axis,
                    end_axis,
                    cross_axis,
                    sheet_texts,
                    orientation=orientation,
                    gap_tol=gap_tol,
                    cross_axis_tol=y_tol,
                    inline_bridge_gap=sheet_inline_bridge_gap,
                    inline_bridge_y_tol=inline_bridge_y_tol,
                    wire_break_evidence=sheet_break_evidence,
                    symbol_cuts=symbol_cuts,
                ):
                    group["start_axis"] = min(group["start_axis"], start_axis)
                    group["end_axis"] = max(group["end_axis"], end_axis)
                    group["members"].append(line)
                    group["layers"].add(line.layer)
                    group["scores"].append(_wire_score(line))
                    group["cross_values"].append(cross_axis)
                    placed = True
                    break
            if not placed:
                active.append(
                    {
                        "start_axis": start_axis,
                        "end_axis": end_axis,
                        "cross_axis": cross_axis,
                        "members": [line],
                        "layers": {line.layer},
                        "scores": [_wire_score(line)],
                        "cross_values": [cross_axis],
                    }
                )

        for group in active:
            avg_cross_axis = sum(group["cross_values"]) / len(group["cross_values"])
            score = round(sum(group["scores"]) / len(group["scores"]), 4)
            start_x, start_y, end_x, end_y = _line_group_endpoints(
                orientation,
                group["start_axis"],
                group["end_axis"],
                avg_cross_axis,
            )
            result.append(
                LineGroup(
                    line_group_id=group_ids.next(),
                    sheet_id=sheet_id,
                    file_id=sheet.file_id,
                    start_x=start_x,
                    start_y=start_y,
                    end_x=end_x,
                    end_y=end_y,
                    length=group["end_axis"] - group["start_axis"],
                    wire_candidate_score=score,
                    member_line_ids=[item.line_id for item in group["members"]],
                    layer_hints=sorted(group["layers"]),
                    orientation=orientation,
                )
            )
    return result


def _resolve_orientation(
    lines: list[LineEntity],
    sheet: SheetRecord,
    config: dict,
    tol: float,
    min_length: float,
    *,
    classification: PageClassification | None = None,
) -> str:
    # 元件接线图不走 grid 模式：
    # 它们即使呈现强网格感，真正需要的仍是 horizontal / vertical component 链，
    # 否则会把块内引脚桩误吸进 grid-aware wire 逻辑。
    if sheet.sheet_category == "元件接线图":
        mode = _sheet_geometry_value(config, sheet, "line_group_orientation", _ORIENTATION_HORIZONTAL)
        normalized_mode = str(mode).lower()
        if normalized_mode in {_ORIENTATION_HORIZONTAL, _ORIENTATION_VERTICAL}:
            return normalized_mode
        if normalized_mode != "auto":
            return _ORIENTATION_HORIZONTAL
        horizontal_count = len(_line_candidates(lines, sheet, _ORIENTATION_HORIZONTAL, tol, min_length))
        vertical_count = len(_line_candidates(lines, sheet, _ORIENTATION_VERTICAL, tol, min_length))
        if vertical_count > horizontal_count:
            return _ORIENTATION_VERTICAL
        return _ORIENTATION_HORIZONTAL

    # PageClassifier 明确判定为 grid_heavy 时，优先走 grid 行带聚类。
    if (
        classification is not None
        and classification.grid_heavy
    ):
        return _ORIENTATION_GRID
    mode = _sheet_geometry_value(config, sheet, "line_group_orientation", _ORIENTATION_HORIZONTAL)
    normalized_mode = str(mode).lower()
    if normalized_mode in {_ORIENTATION_HORIZONTAL, _ORIENTATION_VERTICAL}:
        return normalized_mode
    if normalized_mode != "auto":
        return _ORIENTATION_HORIZONTAL

    horizontal_count = len(_line_candidates(lines, sheet, _ORIENTATION_HORIZONTAL, tol, min_length))
    vertical_count = len(_line_candidates(lines, sheet, _ORIENTATION_VERTICAL, tol, min_length))
    if vertical_count > horizontal_count:
        return _ORIENTATION_VERTICAL
    return _ORIENTATION_HORIZONTAL


def _build_grid_row_bands(
    candidates: list[dict[str, object]],
    sheet: SheetRecord,
    sheet_id: str,
    file_id: str,
    group_ids: IdFactory,
    band_ids: IdFactory,
    sheet_texts: list[TextItem],
    gap_tol: float,
    y_tol: float,
    inline_bridge_gap: float,
    inline_bridge_y_tol: float,
    *,
    wire_break_evidence: WireBreakEvidence | None = None,
    symbol_cuts: list[dict[str, float]] | None = None,
) -> list[LineGroup]:
    """grid 模式行带聚类：先按 y 容差把水平线分到行带，再在行带内做共线合并。

    目标是让被 inline 数字切断的同一根线重新合并成一条 LineGroup，
    同时保留 row_band_id 供候选搜索做列锚点统计。
    """
    if not candidates:
        return []
    grid_band_tol = float(_sheet_geometry_value_for_grid(sheet, "grid_band_y_tolerance", 5.0))

    # 第一步：按 cross_axis（y 值）聚类成行带
    sorted_by_y = sorted(candidates, key=lambda item: item["cross_axis"])
    bands: list[list[dict[str, object]]] = [[sorted_by_y[0]]]
    for candidate in sorted_by_y[1:]:
        band = bands[-1]
        band_y = sum(item["cross_axis"] for item in band) / len(band)
        if abs(candidate["cross_axis"] - band_y) <= grid_band_tol:
            band.append(candidate)
        else:
            bands.append([candidate])

    result: list[LineGroup] = []
    for band_index, band in enumerate(bands):
        band_id = band_ids.next()
        band.sort(key=lambda item: item["start_axis"])
        active: list[dict] = []
        for candidate in band:
            cross_axis = candidate["cross_axis"]
            start_axis = candidate["start_axis"]
            end_axis = candidate["end_axis"]
            line = candidate["line"]
            placed = False
            for group in active:
                if _can_merge_axis_intervals(
                    group["start_axis"],
                    group["end_axis"],
                    group["cross_axis"],
                    start_axis,
                    end_axis,
                    cross_axis,
                    sheet_texts,
                    orientation=_ORIENTATION_HORIZONTAL,
                    gap_tol=gap_tol,
                    cross_axis_tol=y_tol,
                    inline_bridge_gap=inline_bridge_gap,
                    inline_bridge_y_tol=inline_bridge_y_tol,
                    wire_break_evidence=wire_break_evidence,
                    symbol_cuts=symbol_cuts,
                ):
                    group["start_axis"] = min(group["start_axis"], start_axis)
                    group["end_axis"] = max(group["end_axis"], end_axis)
                    group["members"].append(line)
                    group["layers"].add(line.layer)
                    group["scores"].append(_wire_score(line))
                    group["cross_values"].append(cross_axis)
                    placed = True
                    break
            if not placed:
                active.append(
                    {
                        "start_axis": start_axis,
                        "end_axis": end_axis,
                        "cross_axis": cross_axis,
                        "members": [line],
                        "layers": {line.layer},
                        "scores": [_wire_score(line)],
                        "cross_values": [cross_axis],
                    }
                )

        for group in active:
            avg_cross_axis = sum(group["cross_values"]) / len(group["cross_values"])
            score = round(sum(group["scores"]) / len(group["scores"]), 4)
            start_x, start_y, end_x, end_y = _line_group_endpoints(
                _ORIENTATION_GRID,
                group["start_axis"],
                group["end_axis"],
                avg_cross_axis,
            )
            result.append(
                LineGroup(
                    line_group_id=group_ids.next(),
                    sheet_id=sheet_id,
                    file_id=file_id,
                    start_x=start_x,
                    start_y=start_y,
                    end_x=end_x,
                    end_y=end_y,
                    length=group["end_axis"] - group["start_axis"],
                    wire_candidate_score=score,
                    member_line_ids=[item.line_id for item in group["members"]],
                    layer_hints=sorted(group["layers"]),
                    orientation=_ORIENTATION_GRID,
                    row_band_id=band_id,
                )
            )
    return result


def _sheet_geometry_value(config: dict, sheet: SheetRecord, key: str, default: object) -> object:
    value = config.get("geometry", {}).get(key, default)
    override = config.get("page_category_overrides", {}).get(sheet.sheet_category or "", {})
    if isinstance(override, dict):
        geometry_override = override.get("geometry", {})
        if isinstance(geometry_override, dict):
            value = geometry_override.get(key, value)
    return value


def _line_candidates(
    lines: list[LineEntity],
    sheet: SheetRecord,
    orientation: str,
    tol: float,
    min_length: float,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for line in lines:
        if line.length < min_length:
            continue
        candidate = _normalize_line_candidate(line, orientation, tol)
        if candidate is None:
            continue
        mid_x, mid_y = candidate["midpoint"]
        if not _point_in_bbox(mid_x, mid_y, sheet.audit_area_bbox):
            continue
        if sheet.title_block_bbox is not None and _point_in_bbox(mid_x, mid_y, sheet.title_block_bbox):
            continue
        candidates.append(candidate)
    return candidates


def _filter_component_vertical_length_outliers(
    candidates: list[dict[str, object]],
    sheet: SheetRecord,
    orientation: str,
) -> list[dict[str, object]]:
    if orientation != _ORIENTATION_VERTICAL or sheet.sheet_category != "元件接线图":
        return candidates
    lengths = sorted(float(candidate["line"].length) for candidate in candidates)
    if len(lengths) < 5:
        return candidates
    median_length = lengths[len(lengths) // 2]
    threshold = median_length * 3.0
    if threshold <= 0:
        return candidates
    return [candidate for candidate in candidates if float(candidate["line"].length) <= threshold]


def _normalize_line_candidate(
    line: LineEntity,
    orientation: str,
    tol: float,
) -> dict[str, object] | None:
    angle = abs(line.angle_deg)
    horizontal = angle <= tol or abs(angle - 180.0) <= tol
    vertical = abs(angle - 90.0) <= tol
    if orientation == _ORIENTATION_HORIZONTAL:
        if not horizontal:
            return None
        start_axis = min(line.start_x, line.end_x)
        end_axis = max(line.start_x, line.end_x)
        cross_axis = (line.start_y + line.end_y) / 2.0
        midpoint = ((start_axis + end_axis) / 2.0, cross_axis)
    else:
        if not vertical:
            return None
        start_axis = min(line.start_y, line.end_y)
        end_axis = max(line.start_y, line.end_y)
        cross_axis = (line.start_x + line.end_x) / 2.0
        midpoint = (cross_axis, (start_axis + end_axis) / 2.0)
    return {
        "start_axis": start_axis,
        "end_axis": end_axis,
        "cross_axis": cross_axis,
        "midpoint": midpoint,
        "line": line,
    }


def _line_group_endpoints(
    orientation: str,
    start_axis: float,
    end_axis: float,
    cross_axis: float,
) -> tuple[float, float, float, float]:
    if orientation == _ORIENTATION_VERTICAL:
        return cross_axis, end_axis, cross_axis, start_axis
    # horizontal 和 grid 都走水平端点语义
    return start_axis, cross_axis, end_axis, cross_axis


def _can_merge_axis_intervals(
    first_start_axis: float,
    first_end_axis: float,
    first_cross_axis: float,
    second_start_axis: float,
    second_end_axis: float,
    second_cross_axis: float,
    texts: list[TextItem],
    *,
    orientation: str,
    gap_tol: float,
    cross_axis_tol: float,
    inline_bridge_gap: float,
    inline_bridge_y_tol: float,
    wire_break_evidence: WireBreakEvidence | None = None,
    symbol_cuts: list[dict[str, float]] | None = None,
) -> bool:
    if abs(first_cross_axis - second_cross_axis) > cross_axis_tol:
        return False

    if first_end_axis < second_start_axis:
        gap = second_start_axis - first_end_axis
        previous_end_axis = first_end_axis
        next_start_axis = second_start_axis
        previous_cross_axis = first_cross_axis
        next_cross_axis = second_cross_axis
    elif second_end_axis < first_start_axis:
        gap = first_start_axis - second_end_axis
        previous_end_axis = second_end_axis
        next_start_axis = first_start_axis
        previous_cross_axis = second_cross_axis
        next_cross_axis = first_cross_axis
    else:
        return True

    # WIRE-BREAK: a symbol body between the two sides is a wire break whatever bridges it (text or gap width).
    if _symbol_body_between(
        symbol_cuts,
        previous_end_axis,
        next_start_axis,
        (previous_cross_axis + next_cross_axis) / 2.0,
        cross_axis_tol,
    ):
        return False

    if gap <= gap_tol:
        # A small empty gap between two terminals is a wire break at a terminal strip frame,
        # not a continuous wire. Text (wire-number label), a connect dot, or a single terminal
        # spanning the gap keeps the legacy merge.
        return not _is_terminal_wire_break(
            previous_end_axis,
            next_start_axis,
            previous_cross_axis,
            next_cross_axis,
            texts,
            wire_break_evidence,
            orientation=orientation,
            cross_axis_tolerance=inline_bridge_y_tol,
        )
    if _has_named_component_barrier(
        previous_end_axis,
        next_start_axis,
        previous_cross_axis,
        next_cross_axis,
        texts,
        orientation=orientation,
        cross_axis_tolerance=inline_bridge_y_tol,
    ):
        return False
    return _has_inline_numeric_bridge(
        previous_end_axis,
        next_start_axis,
        previous_cross_axis,
        next_cross_axis,
        texts,
        orientation=orientation,
        inline_bridge_gap=inline_bridge_gap,
        inline_bridge_y_tol=inline_bridge_y_tol,
    )


_ZERO_GAP = 1e-9


def _symbol_body_cuts(
    candidates: list[dict[str, object]],
    evidence: WireBreakEvidence | None,
    sheet: SheetRecord,
    orientation: str,
    *,
    max_gap: float,
    cross_tol: float,
) -> list[dict[str, float]]:
    """WIRE-BREAK: the gaps between two candidate segments that are symbol bodies.

    A gap is a symbol body when, on one line, a symbol has two TERMPOINT marks (distinct marks of one symbol key)
    that touch the two wire ends on either side of the gap. Such a gap is never merged, whatever lies in it.
    Ambiguous gaps keep their legacy decision and are logged as unknown shapes (see UNKNOWN_* codes):
    a connect dot in the gap, a gap narrower than SYMBOL_MIN_BODY_WIDTH, and a wire end that also touches
    marks of another symbol (the body is still cut).
    """
    if evidence is None or not evidence.marks or len(candidates) < 2:
        return []
    index = _MarkIndex(evidence.marks)
    ordered = sorted(candidates, key=lambda item: item["start_axis"])
    starts = [float(item["start_axis"]) for item in ordered]
    cuts: list[dict[str, float]] = []
    seen: set[tuple[float, float, float]] = set()
    for first in candidates:
        lo = float(first["end_axis"])
        for second in ordered[bisect_left(starts, lo):]:
            hi = float(second["start_axis"])
            if hi - lo > max_gap:
                break
            if hi - lo <= _ZERO_GAP or abs(float(first["cross_axis"]) - float(second["cross_axis"])) > cross_tol:
                continue
            cross = (float(first["cross_axis"]) + float(second["cross_axis"])) / 2.0
            key = (round(lo, 3), round(hi, 3), round(cross, 3))
            if key in seen:
                continue
            verdict, detail = _symbol_gap_verdict(index, evidence.dots, lo, hi, cross, orientation)
            if verdict is None:
                continue
            seen.add(key)
            if verdict == "body":
                cuts.append({"lo": lo, "hi": hi, "cross": cross})
                evidence.stats["symbol_body_gap"] += 1
                if detail["multi"]:
                    evidence.stats[UNKNOWN_NODE_MULTI_SYMBOL] += 1
                    _log_unknown(evidence, sheet, UNKNOWN_NODE_MULTI_SYMBOL, "cut", orientation, lo, hi, cross,
                                 first, second, detail)
                continue
            evidence.stats[verdict] += 1
            _log_unknown(evidence, sheet, verdict, "kept_merged", orientation, lo, hi, cross, first, second, detail)
    return cuts


def _symbol_gap_verdict(
    index: _MarkIndex,
    dots: tuple[tuple[float, float], ...],
    lo: float,
    hi: float,
    cross: float,
    orientation: str,
) -> tuple[str | None, dict[str, Any]]:
    """("body" | unknown reason | None, detail) for the gap (lo, hi) on the line at cross.

    The gap is a symbol body when one symbol has two distinct TERMPOINT marks inside the gap window, one on each
    side of the gap centre, and at least one of the two touches a wire end of the gap (the symbol spans the break).
    A symbol whose marks lie wholly on one side is not a body (a terminal hanging on a wire end).
    """
    tol = _TERMINAL_TOUCH_TOLERANCE
    if orientation == _ORIENTATION_VERTICAL:
        rect = (cross - tol, lo - tol, cross + tol, hi + tol)
    else:
        rect = (lo - tol, cross - tol, hi + tol, cross + tol)
    mid = (lo + hi) / 2.0
    inside: list[dict[str, Any]] = []
    for key, record_id, x1, y1, x2, y2 in index.overlapping(*rect):
        a1, a2 = (y1, y2) if orientation == _ORIENTATION_VERTICAL else (x1, x2)
        c1, c2 = (x1, x2) if orientation == _ORIENTATION_VERTICAL else (y1, y2)
        if min(a1, a2) < lo - tol or max(a1, a2) > hi + tol:
            continue
        if max(c1, c2) < cross - tol or min(c1, c2) > cross + tol:
            continue
        touch_lo = _point_segment_distance(*_axis_point(orientation, lo, cross), x1, y1, x2, y2) <= tol + 1e-8
        touch_hi = _point_segment_distance(*_axis_point(orientation, hi, cross), x1, y1, x2, y2) <= tol + 1e-8
        inside.append({"key": key, "rid": record_id, "centre": (a1 + a2) / 2.0,
                       "touch_lo": touch_lo, "touch_hi": touch_hi})
    if not any(m["touch_lo"] or m["touch_hi"] for m in inside):
        return None, {}
    spans = any(
        a["key"] == b["key"] and a["rid"] != b["rid"] and a["centre"] < mid < b["centre"]
        and (a["touch_lo"] or b["touch_hi"])
        for a in inside for b in inside
    )
    if not spans:
        return None, {}
    detail = {
        "left_marks": sorted({m["rid"] for m in inside if m["touch_lo"]}),
        "right_marks": sorted({m["rid"] for m in inside if m["touch_hi"]}),
        "multi": len({m["key"] for m in inside if m["touch_lo"]}) > 1
        or len({m["key"] for m in inside if m["touch_hi"]}) > 1,
    }
    if _gap_has_dot(lo, hi, cross, dots, orientation=orientation, cross_axis_tolerance=tol):
        return UNKNOWN_DOT_IN_SYMBOL_GAP, detail
    if hi - lo < SYMBOL_MIN_BODY_WIDTH - 1e-9:
        return UNKNOWN_BODY_WIDTH_BELOW_MIN, detail
    return "body", detail


def _log_unknown(
    evidence: WireBreakEvidence,
    sheet: SheetRecord,
    reason: str,
    action: str,
    orientation: str,
    lo: float,
    hi: float,
    cross: float,
    first: dict[str, object],
    second: dict[str, object],
    detail: dict[str, Any],
) -> None:
    first_line, second_line = first["line"], second["line"]
    evidence.log.append(
        {
            "sheet_id": sheet.sheet_id,
            "file_id": sheet.file_id,
            "reason_code": reason,
            "action": action,
            "orientation": orientation,
            "gap_start": round(lo, 4),
            "gap_end": round(hi, 4),
            "gap_width": round(hi - lo, 4),
            "cross": round(cross, 4),
            "wire_handles": [first_line.handle, second_line.handle],
            "line_ids": [first_line.line_id, second_line.line_id],
            "left_marks": detail.get("left_marks", []),
            "right_marks": detail.get("right_marks", []),
        }
    )


def symbol_cut_group_ids(line_groups: list[LineGroup], evidence: dict[str, WireBreakEvidence] | None) -> set[str]:
    """WIRE-BREAK: ids of the line groups that have an end on a symbol-body cut (the pieces a cut created).

    A group end matches a cut when it lies on the cut's end point (lo or hi) at the cut's cross axis (0.5 tolerance).
    """
    result: set[str] = set()
    for group in line_groups:
        ev = (evidence or {}).get(group.sheet_id)
        if ev is None or not ev.cuts:
            continue
        vertical = group.orientation == _ORIENTATION_VERTICAL
        ends = [(group.start_x, group.start_y), (group.end_x, group.end_y)]
        for cut in ev.cuts:
            cross = cut["cross"]
            for lo_or_hi in (cut["lo"], cut["hi"]):
                for x, y in ends:
                    axis_value, cross_value = (y, x) if vertical else (x, y)
                    if abs(axis_value - lo_or_hi) <= 0.5 and abs(cross_value - cross) <= 0.5:
                        result.add(group.line_group_id)
    return result


# P3-CROSS-DEVICE: a straight path between two anchors must end this far inside a mark for the mark to count as on the path.
_PATH_END_MARGIN = 1.0
# Anchors closer than this on the minor axis count as one row (or one column) for the path test.
_PATH_ALIGN_TOLERANCE = 2.5


class PathBodyChecker:
    """P3-CROSS-DEVICE: does the straight path between two anchors run through a symbol body?

    The rule is the WIRE-BREAK body rule applied to a path instead of a gap: a symbol body is crossed when one
    symbol has two distinct TERMPOINT marks strictly inside the path and on its line, so the path enters the
    symbol at one terminal and leaves at another (a direct mapping would skip the terminal or component).
    Unknown shapes keep the pair out of pass: a connect dot between the marks, or marks closer than
    SYMBOL_MIN_BODY_WIDTH, return "ambiguous". Other paths return None with the reason in the detail
    (not_axis_aligned, no_body_on_path).
    Built once per sheet from the same marks and dots as the line-group cuts.
    """

    def __init__(self, evidence: WireBreakEvidence) -> None:
        self._index = _MarkIndex(evidence.marks)
        self._dots = evidence.dots

    def verdict(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        *,
        start_on_wire: bool = False,
        end_on_wire: bool = False,
    ) -> tuple[str | None, dict[str, Any]]:
        """("body" | "ambiguous" | None, detail) for the path from start to end.

        start_on_wire / end_on_wire: that end is a wire end (a line-group end), so a mark touching it is a
        terminal the path starts at and counts. Otherwise the end is a text anchor and a mark must lie strictly
        inside it (a text sitting on a terminal does not make the terminal part of the path).
        """
        (x1, y1), (x2, y2) = start, end
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        if min(dx, dy) > _PATH_ALIGN_TOLERANCE or max(dx, dy) <= _PATH_ALIGN_TOLERANCE:
            return None, {"reason": "not_axis_aligned"}
        if dx > dy:
            orientation = _ORIENTATION_HORIZONTAL
            lo, hi = sorted((x1, x2))
            lo_on_wire, hi_on_wire = (start_on_wire, end_on_wire) if x1 <= x2 else (end_on_wire, start_on_wire)
            cross = (y1 + y2) / 2.0
        else:
            orientation = _ORIENTATION_VERTICAL
            lo, hi = sorted((y1, y2))
            lo_on_wire, hi_on_wire = (start_on_wire, end_on_wire) if y1 <= y2 else (end_on_wire, start_on_wire)
            cross = (x1 + x2) / 2.0
        # The anchors are text insert points, a few units off the wire row they label: the band must reach the row.
        tol = max(_TERMINAL_TOUCH_TOLERANCE + min(dx, dy) / 2.0, _PATH_ALIGN_TOLERANCE)
        if orientation == _ORIENTATION_VERTICAL:
            rect = (cross - tol, lo - tol, cross + tol, hi + tol)
        else:
            rect = (lo - tol, cross - tol, hi + tol, cross + tol)
        low_bound = lo - _TERMINAL_TOUCH_TOLERANCE if lo_on_wire else lo + _PATH_END_MARGIN
        high_bound = hi + _TERMINAL_TOUCH_TOLERANCE if hi_on_wire else hi - _PATH_END_MARGIN
        inside: dict[str, list[tuple[float, str]]] = defaultdict(list)
        for key, record_id, mx1, my1, mx2, my2 in self._index.overlapping(*rect):
            a1, a2 = (my1, my2) if orientation == _ORIENTATION_VERTICAL else (mx1, mx2)
            c1, c2 = (mx1, mx2) if orientation == _ORIENTATION_VERTICAL else (my1, my2)
            centre = (a1 + a2) / 2.0
            if not (low_bound < centre < high_bound):
                continue
            if max(c1, c2) < cross - tol or min(c1, c2) > cross + tol:
                continue
            inside[key].append((centre, record_id))
        best: tuple[float, str, list[tuple[float, str]]] | None = None
        for key, items in inside.items():
            if len({rid for _, rid in items}) < 2:
                continue
            width = max(c for c, _ in items) - min(c for c, _ in items)
            if best is None or width > best[0]:
                best = (width, key, items)
        if best is None:
            return None, {"reason": "no_body_on_path"}
        width, key, items = best
        centres = [c for c, _ in items]
        span_lo, span_hi = min(centres), max(centres)
        detail: dict[str, Any] = {
            "orientation": orientation,
            "span": [round(lo, 3), round(hi, 3)],
            "cross": round(cross, 3),
            "symbol_key": key,
            "marks": sorted({rid for _, rid in items}),
            "body_width": round(width, 3),
        }
        if _gap_has_dot(span_lo, span_hi, cross, self._dots, orientation=orientation, cross_axis_tolerance=tol):
            detail["reason"] = UNKNOWN_DOT_IN_SYMBOL_GAP
            return "ambiguous", detail
        if width < SYMBOL_MIN_BODY_WIDTH - 1e-9:
            detail["reason"] = UNKNOWN_BODY_WIDTH_BELOW_MIN
            return "ambiguous", detail
        return "body", detail


def path_body_checkers(wire_break_evidence: dict[str, WireBreakEvidence] | None) -> dict[str, PathBodyChecker]:
    """One PathBodyChecker per sheet that has symbol marks."""
    return {
        sheet_id: PathBodyChecker(evidence)
        for sheet_id, evidence in (wire_break_evidence or {}).items()
        if evidence is not None and evidence.marks
    }


def _symbol_body_between(
    symbol_cuts: list[dict[str, float]] | None,
    lo: float,
    hi: float,
    cross: float,
    cross_tol: float,
) -> bool:
    """True when a symbol body lies inside the gap (lo, hi) of a merge decision."""
    if not symbol_cuts:
        return False
    for cut in symbol_cuts:
        if cut["lo"] >= lo - 1e-6 and cut["hi"] <= hi + 1e-6 and abs(cut["cross"] - cross) <= cross_tol + 1e-9:
            return True
    return False


def _is_terminal_wire_break(
    previous_end_axis: float,
    next_start_axis: float,
    previous_cross_axis: float,
    next_cross_axis: float,
    texts: list[TextItem],
    evidence: WireBreakEvidence | None,
    *,
    orientation: str,
    cross_axis_tolerance: float,
) -> bool:
    """True when an empty gap separates the wire ends of two different terminals.

    Both gap ends must sit on SuperWORKS ports, and they must be different ports (one
    terminal spanning the whole gap is one wire passing through, not a break). Any text
    or connect dot that touches the gap keeps the legacy merge.
    """
    if evidence is None or not evidence.ports:
        return False
    left_ports = _ports_touching(
        _axis_point(orientation, previous_end_axis, previous_cross_axis), evidence.ports
    )
    if not left_ports:
        return False
    right_ports = _ports_touching(
        _axis_point(orientation, next_start_axis, next_cross_axis), evidence.ports
    )
    if not any(left != right for left in left_ports for right in right_ports):
        return False
    target_cross_axis = (previous_cross_axis + next_cross_axis) / 2.0
    if _gap_has_text(
        previous_end_axis,
        next_start_axis,
        target_cross_axis,
        texts,
        orientation=orientation,
        cross_axis_tolerance=cross_axis_tolerance,
    ):
        return False
    return not _gap_has_dot(
        previous_end_axis,
        next_start_axis,
        target_cross_axis,
        evidence.dots,
        orientation=orientation,
        cross_axis_tolerance=cross_axis_tolerance,
    )


def _axis_point(orientation: str, axis_value: float, cross_value: float) -> tuple[float, float]:
    if orientation == _ORIENTATION_VERTICAL:
        return cross_value, axis_value
    return axis_value, cross_value


def _ports_touching(point: tuple[float, float], ports: tuple[tuple[str, float, float, float, float], ...]) -> set[str]:
    touching: set[str] = set()
    px, py = point
    for record_id, x1, y1, x2, y2 in ports:
        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq <= 0:
            nearest_x, nearest_y = x1, y1
        else:
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
            nearest_x, nearest_y = x1 + t * dx, y1 + t * dy
        if math.hypot(px - nearest_x, py - nearest_y) <= _TERMINAL_TOUCH_TOLERANCE + 1e-8:
            touching.add(record_id)
    return touching


def _gap_has_text(
    previous_end_axis: float,
    next_start_axis: float,
    target_cross_axis: float,
    texts: list[TextItem],
    *,
    orientation: str,
    cross_axis_tolerance: float,
) -> bool:
    """Any text whose drawn extent covers the gap (a wire-number label knocks out the wire under it)."""
    for text in texts:
        if not (text.text or "").strip():
            continue
        if orientation == _ORIENTATION_VERTICAL:
            axis_min = min(text.bbox_min_y, text.bbox_max_y)
            axis_max = max(text.bbox_min_y, text.bbox_max_y)
            cross_min = min(text.bbox_min_x, text.bbox_max_x)
            cross_max = max(text.bbox_min_x, text.bbox_max_x)
        else:
            axis_min = min(text.bbox_min_x, text.bbox_max_x)
            axis_max = max(text.bbox_min_x, text.bbox_max_x)
            cross_min = min(text.bbox_min_y, text.bbox_max_y)
            cross_max = max(text.bbox_min_y, text.bbox_max_y)
        if axis_max < previous_end_axis - _GAP_EDGE_MARGIN or axis_min > next_start_axis + _GAP_EDGE_MARGIN:
            continue
        if cross_max < target_cross_axis - cross_axis_tolerance or cross_min > target_cross_axis + cross_axis_tolerance:
            continue
        return True
    return False


def _gap_has_dot(
    previous_end_axis: float,
    next_start_axis: float,
    target_cross_axis: float,
    dots: tuple[tuple[float, float], ...],
    *,
    orientation: str,
    cross_axis_tolerance: float,
) -> bool:
    for x, y in dots:
        axis_value, cross_value = (y, x) if orientation == _ORIENTATION_VERTICAL else (x, y)
        if previous_end_axis - _GAP_EDGE_MARGIN <= axis_value <= next_start_axis + _GAP_EDGE_MARGIN:
            if abs(cross_value - target_cross_axis) <= cross_axis_tolerance:
                return True
    return False


def _has_named_component_barrier(
    previous_end_axis: float,
    next_start_axis: float,
    previous_cross_axis: float,
    next_cross_axis: float,
    texts: list[TextItem],
    *,
    orientation: str,
    cross_axis_tolerance: float,
) -> bool:
    """Keep wire segments separate when an instance label occupies their gap."""

    target_cross_axis = (previous_cross_axis + next_cross_axis) / 2.0
    for text in texts:
        instance = str(text.normalized_text or text.text or "").strip()
        if (
            text.is_numeric_candidate
            or text.source_block_name
            or text.entity_type.upper() != "MTEXT"
            or not _NAMED_COMPONENT_BARRIER_PATTERN.fullmatch(instance)
        ):
            continue
        if orientation == _ORIENTATION_VERTICAL:
            text_axis_min = min(text.bbox_min_y, text.bbox_max_y)
            text_axis_max = max(text.bbox_min_y, text.bbox_max_y)
            cross_axis = (text.bbox_min_x + text.bbox_max_x) / 2.0
        else:
            text_axis_min = min(text.bbox_min_x, text.bbox_max_x)
            text_axis_max = max(text.bbox_min_x, text.bbox_max_x)
            cross_axis = (text.bbox_min_y + text.bbox_max_y) / 2.0
        if text_axis_max < previous_end_axis - 1.0 or text_axis_min > next_start_axis + 1.0:
            continue
        if abs(cross_axis - target_cross_axis) <= cross_axis_tolerance:
            return True
    return False


def _sheet_geometry_value_for_grid(sheet: SheetRecord, key: str, default: object) -> object:
    """grid 模式专用配置读取，不走 page_category_overrides（grid 是跨页型的子模式）。"""
    return default


def _wire_score(line: LineEntity) -> float:
    score = 0.35
    if "CONNECT" in line.layer.upper():
        score += 0.35
    if line.length >= 25:
        score += 0.15
    if line.layer == "0":
        score += 0.05
    return min(score, 1.0)


def _inline_bridge_gap_for_sheet(sheet: SheetRecord, default_gap: float) -> float:
    """Signal/alarm rows often leave a wider label gap; other sheets stay strict."""
    blob = f"{sheet.sheet_title or ''} {sheet.filename or ''}".lower()
    if any(token in blob for token in ("信号回路", "告警", "signal circuit", "alarm")):
        return max(default_gap, _SIGNAL_INLINE_BRIDGE_GAP)
    return default_gap


def _has_inline_numeric_bridge(
    previous_end_axis: float,
    next_start_axis: float,
    previous_cross_axis: float,
    next_cross_axis: float,
    texts: list[TextItem],
    *,
    orientation: str,
    inline_bridge_gap: float,
    inline_bridge_y_tol: float,
) -> bool:
    gap = next_start_axis - previous_end_axis
    if gap <= 0 or gap > inline_bridge_gap:
        return False
    target_cross_axis = (previous_cross_axis + next_cross_axis) / 2.0
    for text in texts:
        if not text.is_numeric_candidate:
            continue
        if orientation == _ORIENTATION_VERTICAL:
            text_axis_min = min(text.bbox_min_y, text.bbox_max_y)
            text_axis_max = max(text.bbox_min_y, text.bbox_max_y)
            cross_axis = (text.bbox_min_x + text.bbox_max_x) / 2.0
        else:
            text_axis_min = min(text.bbox_min_x, text.bbox_max_x)
            text_axis_max = max(text.bbox_min_x, text.bbox_max_x)
            cross_axis = (text.bbox_min_y + text.bbox_max_y) / 2.0
        if text_axis_max < previous_end_axis - 1.0 or text_axis_min > next_start_axis + 1.0:
            continue
        if abs(cross_axis - target_cross_axis) <= inline_bridge_y_tol:
            return True
    return False
