from __future__ import annotations

from collections import defaultdict

from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_ORIENTATION_HORIZONTAL = "horizontal"
_ORIENTATION_VERTICAL = "vertical"


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
) -> list[LineGroup]:
    by_sheet = defaultdict(list)
    for line in lines:
        by_sheet[line.sheet_id].append(line)
    by_sheet_texts = defaultdict(list)
    for text in texts or []:
        if text.is_numeric_candidate:
            by_sheet_texts[text.sheet_id].append(text)
    sheet_map = {sheet.sheet_id: sheet for sheet in sheets}
    group_ids = IdFactory("G")
    result: list[LineGroup] = []

    tol = float(config.get("geometry", {}).get("horizontal_angle_tolerance_deg", 2.0))
    min_length = float(config.get("geometry", {}).get("min_wire_length", 12.0))
    y_tol = float(config.get("geometry", {}).get("line_y_tolerance", 1.8))
    gap_tol = float(config.get("geometry", {}).get("line_gap_tolerance", 4.0))
    inline_bridge_gap = float(config.get("geometry", {}).get("inline_numeric_bridge_gap", 12.0))
    inline_bridge_y_tol = float(config.get("geometry", {}).get("inline_numeric_bridge_y_tolerance", 4.0))

    for sheet_id, sheet_lines in by_sheet.items():
        sheet = sheet_map.get(sheet_id)
        if sheet is None or not sheet.is_primary_audit_candidate or sheet.audit_area_bbox is None:
            continue
        sheet_texts = by_sheet_texts.get(sheet_id, [])
        orientation = _resolve_orientation(sheet_lines, sheet, config, tol, min_length)
        candidates = _line_candidates(sheet_lines, sheet, orientation, tol, min_length)
        candidates = _filter_component_vertical_length_outliers(candidates, sheet, orientation)

        candidates.sort(key=lambda item: (round(item["cross_axis"], 3), item["start_axis"]))
        active: list[dict] = []
        for candidate in candidates:
            cross_axis = candidate["cross_axis"]
            start_axis = candidate["start_axis"]
            end_axis = candidate["end_axis"]
            line = candidate["line"]
            placed = False
            for group in active:
                gap = start_axis - group["end_axis"]
                should_bridge = gap > gap_tol and _has_inline_numeric_bridge(
                    group["end_axis"],
                    start_axis,
                    group["cross_axis"],
                    cross_axis,
                    sheet_texts,
                    orientation=orientation,
                    inline_bridge_gap=inline_bridge_gap,
                    inline_bridge_y_tol=inline_bridge_y_tol,
                )
                if abs(group["cross_axis"] - cross_axis) <= y_tol and (gap <= gap_tol or should_bridge):
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
) -> str:
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
    return start_axis, cross_axis, end_axis, cross_axis


def _wire_score(line: LineEntity) -> float:
    score = 0.35
    if "CONNECT" in line.layer.upper():
        score += 0.35
    if line.length >= 25:
        score += 0.15
    if line.layer == "0":
        score += 0.05
    return min(score, 1.0)


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
            along_axis = text.insert_y
            cross_axis = text.insert_x
        else:
            along_axis = text.insert_x
            cross_axis = text.insert_y
        if not (previous_end_axis - 1.0 <= along_axis <= next_start_axis + 1.0):
            continue
        if abs(cross_axis - target_cross_axis) <= inline_bridge_y_tol:
            return True
    return False
