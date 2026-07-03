from __future__ import annotations

from collections import defaultdict

from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import SheetRecord
from dwg_audit.utils.ids import IdFactory


def _point_in_bbox(x: float, y: float, bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return True
    min_x, min_y, max_x, max_y = bbox
    return min_x <= x <= max_x and min_y <= y <= max_y


def build_line_groups(lines: list[LineEntity], sheets: list[SheetRecord], config: dict) -> list[LineGroup]:
    by_sheet = defaultdict(list)
    for line in lines:
        by_sheet[line.sheet_id].append(line)
    sheet_map = {sheet.sheet_id: sheet for sheet in sheets}
    group_ids = IdFactory("G")
    result: list[LineGroup] = []

    tol = float(config.get("geometry", {}).get("horizontal_angle_tolerance_deg", 2.0))
    min_length = float(config.get("geometry", {}).get("min_wire_length", 12.0))
    y_tol = float(config.get("geometry", {}).get("line_y_tolerance", 1.8))
    gap_tol = float(config.get("geometry", {}).get("line_gap_tolerance", 4.0))

    for sheet_id, sheet_lines in by_sheet.items():
        sheet = sheet_map.get(sheet_id)
        if sheet is None or not sheet.is_primary_audit_candidate or sheet.audit_area_bbox is None:
            continue
        candidates = []
        for line in sheet_lines:
            angle = abs(line.angle_deg)
            horizontal = angle <= tol or abs(angle - 180.0) <= tol
            if not horizontal or line.length < min_length:
                continue
            start_x = min(line.start_x, line.end_x)
            end_x = max(line.start_x, line.end_x)
            y = (line.start_y + line.end_y) / 2.0
            mid_x = (start_x + end_x) / 2.0
            if not _point_in_bbox(mid_x, y, sheet.audit_area_bbox):
                continue
            if sheet.title_block_bbox is not None and _point_in_bbox(mid_x, y, sheet.title_block_bbox):
                continue
            candidates.append((y, start_x, end_x, line))

        candidates.sort(key=lambda item: (round(item[0], 3), item[1]))
        active: list[dict] = []
        for y, start_x, end_x, line in candidates:
            placed = False
            for group in active:
                if abs(group["y"] - y) <= y_tol and start_x - group["end_x"] <= gap_tol:
                    group["start_x"] = min(group["start_x"], start_x)
                    group["end_x"] = max(group["end_x"], end_x)
                    group["members"].append(line)
                    group["layers"].add(line.layer)
                    group["scores"].append(_wire_score(line))
                    group["y_values"].append(y)
                    placed = True
                    break
            if not placed:
                active.append(
                    {
                        "start_x": start_x,
                        "end_x": end_x,
                        "y": y,
                        "members": [line],
                        "layers": {line.layer},
                        "scores": [_wire_score(line)],
                        "y_values": [y],
                    }
                )

        for group in active:
            avg_y = sum(group["y_values"]) / len(group["y_values"])
            score = round(sum(group["scores"]) / len(group["scores"]), 4)
            result.append(
                LineGroup(
                    line_group_id=group_ids.next(),
                    sheet_id=sheet_id,
                    file_id=sheet.file_id,
                    start_x=group["start_x"],
                    start_y=avg_y,
                    end_x=group["end_x"],
                    end_y=avg_y,
                    length=group["end_x"] - group["start_x"],
                    wire_candidate_score=score,
                    member_line_ids=[item.line_id for item in group["members"]],
                    layer_hints=sorted(group["layers"]),
                )
            )
    return result


def _wire_score(line: LineEntity) -> float:
    score = 0.35
    if "CONNECT" in line.layer.upper():
        score += 0.35
    if line.length >= 25:
        score += 0.15
    if line.layer == "0":
        score += 0.05
    return min(score, 1.0)
