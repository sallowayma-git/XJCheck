from __future__ import annotations

import math
from collections import defaultdict

from shapely.geometry import box
from shapely.strtree import STRtree

from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


class TextSpatialIndex:
    def __init__(self, texts: list[TextItem]) -> None:
        self.texts = texts
        self.boxes = [box(item.bbox_min_x, item.bbox_min_y, item.bbox_max_x, item.bbox_max_y) for item in texts]
        self.tree = STRtree(self.boxes) if self.boxes else None

    def query(self, bbox: tuple[float, float, float, float]) -> list[TextItem]:
        if self.tree is None:
            return []
        try:
            indices = self.tree.query(box(*bbox))
            return [self.texts[int(index)] for index in indices]
        except Exception:
            min_x, min_y, max_x, max_y = bbox
            return [
                item
                for item in self.texts
                if item.bbox_min_x <= max_x
                and item.bbox_max_x >= min_x
                and item.bbox_min_y <= max_y
                and item.bbox_max_y >= min_y
            ]


def build_terminal_candidates(
    line_groups: list[LineGroup],
    texts: list[TextItem],
    config: dict,
) -> list[TerminalCandidate]:
    by_sheet_texts = defaultdict(list)
    for text in texts:
        by_sheet_texts[text.sheet_id].append(text)

    indexes = {sheet_id: TextSpatialIndex(sheet_texts) for sheet_id, sheet_texts in by_sheet_texts.items()}
    candidate_ids = IdFactory("C")
    radius_x = float(config.get("geometry", {}).get("endpoint_search_radius_x", 18.0))
    radius_y = float(config.get("geometry", {}).get("endpoint_search_radius_y", 7.0))
    min_height = float(config.get("text", {}).get("min_text_height", 1.0))
    max_height = float(config.get("text", {}).get("max_text_height", 8.0))

    results: list[TerminalCandidate] = []
    for group in line_groups:
        index = indexes.get(group.sheet_id)
        if index is None:
            continue
        for side, endpoint in (("left", (group.start_x, group.start_y)), ("right", (group.end_x, group.end_y))):
            bbox = (
                endpoint[0] - radius_x,
                endpoint[1] - radius_y,
                endpoint[0] + radius_x,
                endpoint[1] + radius_y,
            )
            for text in index.query(bbox):
                dx = text.insert_x - endpoint[0]
                dy = text.insert_y - endpoint[1]
                side_ok = dx <= 2.5 if side == "left" else dx >= -2.5
                within_height = min_height <= text.height <= max_height
                if not text.is_numeric_candidate:
                    status = "rejected"
                    reason = "not_numeric"
                    score = 0.0
                elif not within_height:
                    status = "rejected"
                    reason = "height_out_of_range"
                    score = 0.0
                elif not side_ok:
                    status = "rejected"
                    reason = "wrong_side"
                    score = 0.0
                else:
                    score = _candidate_score(dx, dy, radius_x, radius_y, text.height, side)
                    status = "accepted"
                    reason = None
                results.append(
                    TerminalCandidate(
                        candidate_id=candidate_ids.next(),
                        line_group_id=group.line_group_id,
                        sheet_id=group.sheet_id,
                        file_id=group.file_id,
                        side=side,
                        text_id=text.text_id,
                        text=text.text,
                        value=text.normalized_text if status == "accepted" else None,
                        score=score,
                        status=status,
                        rejection_reason=reason,
                        endpoint_x=endpoint[0],
                        endpoint_y=endpoint[1],
                        distance_x=round(abs(dx), 4),
                        distance_y=round(abs(dy), 4),
                        text_insert_x=text.insert_x,
                        text_insert_y=text.insert_y,
                    )
                )
    return results


def _candidate_score(dx: float, dy: float, radius_x: float, radius_y: float, height: float, side: str) -> float:
    distance_term = 1.0 - min(abs(dx) / max(radius_x, 1.0), 1.0) * 0.55 - min(abs(dy) / max(radius_y, 1.0), 1.0) * 0.35
    side_bonus = 0.05 if (side == "left" and dx <= 0) or (side == "right" and dx >= 0) else 0.0
    height_bonus = 0.05 if 1.8 <= height <= 3.5 else 0.0
    return round(max(0.0, min(1.0, distance_term + side_bonus + height_bonus)), 4)
