from __future__ import annotations

import re
from collections import defaultdict

from shapely.geometry import box
from shapely.strtree import STRtree

from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_ORIENTATION_VERTICAL = "vertical"


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
    sheets: list[SheetRecord] | None = None,
) -> list[TerminalCandidate]:
    by_sheet_texts = defaultdict(list)
    for text in texts:
        by_sheet_texts[text.sheet_id].append(text)

    indexes = {sheet_id: TextSpatialIndex(sheet_texts) for sheet_id, sheet_texts in by_sheet_texts.items()}
    sheet_map = {sheet.sheet_id: sheet for sheet in sheets or []}
    group_map = {group.line_group_id: group for group in line_groups}
    candidate_ids = IdFactory("C")

    results: list[TerminalCandidate] = []
    for group in line_groups:
        index = indexes.get(group.sheet_id)
        if index is None:
            continue
        sheet = sheet_map.get(group.sheet_id)
        profile = _candidate_profile(config, sheet)
        radius_x = profile["radius_x"]
        radius_y = profile["radius_y"]
        min_height = profile["min_height"]
        max_height = profile["max_height"]
        orientation = group.orientation if group.orientation in {"horizontal", "vertical"} else "horizontal"
        for side, endpoint in _endpoints_for_group(group):
            bbox = (
                endpoint[0] - radius_x,
                endpoint[1] - radius_y,
                endpoint[0] + radius_x,
                endpoint[1] + radius_y,
            )
            for text in index.query(bbox):
                dx = text.insert_x - endpoint[0]
                dy = text.insert_y - endpoint[1]
                value = _candidate_numeric_value(text, profile["numeric_suffix_patterns"])
                within_height = min_height <= text.height <= max_height
                vertical_alignment_score = _cross_axis_alignment_score(dx, dy, radius_x, radius_y, orientation)
                horizontal_side_score = _side_alignment_score(dx, dy, radius_x, radius_y, side, orientation)
                text_type_score = 1.0 if value is not None else 0.0
                height_score = 1.0 if within_height else 0.0
                if value is None:
                    status = "rejected"
                    reason = "not_numeric"
                    score = 0.0
                elif not within_height:
                    status = "rejected"
                    reason = "height_out_of_range"
                    score = 0.0
                elif (
                    len(value.strip()) == 1
                    and text.layer.upper() in profile["single_char_reject_layers"]
                ):
                    status = "rejected"
                    reason = "single_char_layer_filtered"
                    score = 0.0
                else:
                    score = _candidate_score(
                        dx,
                        dy,
                        radius_x,
                        radius_y,
                        text.height,
                        side,
                        orientation=orientation,
                        layer=text.layer,
                        value=value,
                        deprioritized_layers=profile["deprioritized_layers"],
                        deprioritized_layer_penalty=profile["deprioritized_layer_penalty"],
                        single_char_penalty_layers=profile["single_char_penalty_layers"],
                        single_char_penalty=profile["single_char_penalty"],
                        derived_numeric_penalty=profile["derived_numeric_penalty"] if not text.is_numeric_candidate else 0.0,
                    )
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
                        value=value if status == "accepted" else None,
                        score=score,
                        status=status,
                        rejection_reason=reason,
                        endpoint_x=endpoint[0],
                        endpoint_y=endpoint[1],
                        distance_x=round(abs(dx), 4),
                        distance_y=round(abs(dy), 4),
                        text_insert_x=text.insert_x,
                        text_insert_y=text.insert_y,
                        vertical_alignment_score=vertical_alignment_score,
                        horizontal_side_score=horizontal_side_score,
                        text_type_score=text_type_score,
                        height_score=height_score,
                    )
                )
    _dedupe_shared_text_anchors(results, group_map, sheet_map)
    _assign_candidate_ranks(results)
    return results


def _endpoints_for_group(group: LineGroup) -> tuple[tuple[str, tuple[float, float]], tuple[str, tuple[float, float]]]:
    if group.orientation == _ORIENTATION_VERTICAL:
        return (("top", (group.start_x, group.start_y)), ("bottom", (group.end_x, group.end_y)))
    return (("left", (group.start_x, group.start_y)), ("right", (group.end_x, group.end_y)))


def _candidate_score(
    dx: float,
    dy: float,
    radius_x: float,
    radius_y: float,
    height: float,
    side: str,
    *,
    orientation: str,
    layer: str,
    value: str,
    deprioritized_layers: set[str],
    deprioritized_layer_penalty: float,
    single_char_penalty_layers: set[str],
    single_char_penalty: float,
    derived_numeric_penalty: float,
) -> float:
    if orientation == _ORIENTATION_VERTICAL:
        distance_term = 1.0 - min(abs(dx) / max(radius_x, 1.0), 1.0) * 0.35 - min(abs(dy) / max(radius_y, 1.0), 1.0) * 0.55
    else:
        distance_term = 1.0 - min(abs(dx) / max(radius_x, 1.0), 1.0) * 0.55 - min(abs(dy) / max(radius_y, 1.0), 1.0) * 0.35
    side_bonus = _side_bonus(dx, dy, side, orientation)
    height_bonus = 0.05 if 1.8 <= height <= 3.5 else 0.0
    penalty = 0.0
    normalized_layer = layer.upper()
    normalized_value = value.strip()
    if normalized_layer in deprioritized_layers:
        penalty += deprioritized_layer_penalty
    if len(normalized_value) == 1 and normalized_layer in single_char_penalty_layers:
        penalty += single_char_penalty
    penalty += derived_numeric_penalty
    return round(max(0.0, min(1.0, distance_term + side_bonus + height_bonus - penalty)), 4)


def _cross_axis_alignment_score(
    dx: float,
    dy: float,
    radius_x: float,
    radius_y: float,
    orientation: str,
) -> float:
    if orientation == _ORIENTATION_VERTICAL:
        return round(max(0.0, 1.0 - min(abs(dx) / max(radius_x, 1.0), 1.0)), 4)
    return round(max(0.0, 1.0 - min(abs(dy) / max(radius_y, 1.0), 1.0)), 4)


def _side_alignment_score(
    dx: float,
    dy: float,
    radius_x: float,
    radius_y: float,
    side: str,
    orientation: str,
) -> float:
    if orientation == _ORIENTATION_VERTICAL:
        return _vertical_side_score(dy, radius_y, side)
    return _horizontal_side_score(dx, radius_x, side)


def _side_bonus(dx: float, dy: float, side: str, orientation: str) -> float:
    if orientation == _ORIENTATION_VERTICAL:
        return 0.05 if (side == "top" and dy >= -2.5) or (side == "bottom" and dy <= 2.5) else 0.0
    return 0.05 if (side == "left" and dx <= 0) or (side == "right" and dx >= 0) else 0.0


def _horizontal_side_score(dx: float, radius_x: float, side: str) -> float:
    if (side == "left" and dx > 2.5) or (side == "right" and dx < -2.5):
        return 0.0
    if side == "left":
        normalized = 1.0 - min(max(dx, 0.0) / max(radius_x, 1.0), 1.0)
    else:
        normalized = 1.0 - min(max(-dx, 0.0) / max(radius_x, 1.0), 1.0)
    return round(max(0.0, min(1.0, normalized)), 4)


def _vertical_side_score(dy: float, radius_y: float, side: str) -> float:
    if (side == "top" and dy < -2.5) or (side == "bottom" and dy > 2.5):
        return 0.0
    if side == "top":
        normalized = 1.0 - min(max(-dy, 0.0) / max(radius_y, 1.0), 1.0)
    else:
        normalized = 1.0 - min(max(dy, 0.0) / max(radius_y, 1.0), 1.0)
    return round(max(0.0, min(1.0, normalized)), 4)


def _assign_candidate_ranks(candidates: list[TerminalCandidate]) -> None:
    by_group_side = defaultdict(list)
    for candidate in candidates:
        if candidate.status == "accepted" and candidate.value:
            by_group_side[(candidate.line_group_id, candidate.side)].append(candidate)

    for ranked_candidates in by_group_side.values():
        ranked_candidates.sort(key=lambda item: item.score, reverse=True)
        for index, candidate in enumerate(ranked_candidates, start=1):
            candidate.rank = index


def _dedupe_shared_text_anchors(
    candidates: list[TerminalCandidate],
    group_map: dict[str, LineGroup],
    sheet_map: dict[str, SheetRecord],
) -> None:
    by_anchor = defaultdict(list)
    for candidate in candidates:
        if candidate.status != "accepted" or not candidate.value:
            continue
        group = group_map.get(candidate.line_group_id)
        sheet = sheet_map.get(candidate.sheet_id)
        if group is None or sheet is None:
            continue
        if group.orientation != _ORIENTATION_VERTICAL or sheet.sheet_category != "元件接线图":
            continue
        by_anchor[(candidate.sheet_id, candidate.side, candidate.text_id)].append(candidate)

    for shared_candidates in by_anchor.values():
        if len(shared_candidates) <= 1:
            continue
        shared_candidates.sort(key=lambda item: (item.distance_x + item.distance_y, -item.score, item.candidate_id))
        for candidate in shared_candidates[1:]:
            candidate.status = "rejected"
            candidate.rejection_reason = "shared_text_anchor_reused"
            candidate.value = None
            candidate.rank = None


def _candidate_profile(config: dict, sheet: SheetRecord | None) -> dict[str, object]:
    geometry = config.get("geometry", {})
    text_config = config.get("text", {})
    profile: dict[str, object] = {
        "radius_x": float(geometry.get("endpoint_search_radius_x", 18.0)),
        "radius_y": float(geometry.get("endpoint_search_radius_y", 7.0)),
        "min_height": float(text_config.get("min_text_height", 1.0)),
        "max_height": float(text_config.get("max_text_height", 8.0)),
        "deprioritized_layers": {str(item).upper() for item in text_config.get("deprioritized_layers", [])},
        "deprioritized_layer_penalty": float(text_config.get("deprioritized_layer_penalty", 0.0)),
        "single_char_penalty_layers": {str(item).upper() for item in text_config.get("single_char_penalty_layers", [])},
        "single_char_penalty": float(text_config.get("single_char_penalty", 0.0)),
        "single_char_reject_layers": {str(item).upper() for item in text_config.get("single_char_reject_layers", [])},
        "numeric_suffix_patterns": [],
        "derived_numeric_penalty": 0.0,
    }
    category = sheet.sheet_category if sheet is not None else None
    override = config.get("page_category_overrides", {}).get(category or "", {})
    if not isinstance(override, dict):
        return profile

    geometry_override = override.get("geometry", {})
    if isinstance(geometry_override, dict):
        profile["radius_x"] = float(geometry_override.get("endpoint_search_radius_x", profile["radius_x"]))
        profile["radius_y"] = float(geometry_override.get("endpoint_search_radius_y", profile["radius_y"]))

    text_override = override.get("text", {})
    if isinstance(text_override, dict):
        profile["min_height"] = float(text_override.get("min_text_height", profile["min_height"]))
        profile["max_height"] = float(text_override.get("max_text_height", profile["max_height"]))
        if "deprioritized_layers" in text_override:
            profile["deprioritized_layers"] = {str(item).upper() for item in text_override.get("deprioritized_layers", [])}
        if "deprioritized_layer_penalty" in text_override:
            profile["deprioritized_layer_penalty"] = float(text_override.get("deprioritized_layer_penalty", profile["deprioritized_layer_penalty"]))
        if "single_char_penalty_layers" in text_override:
            profile["single_char_penalty_layers"] = {str(item).upper() for item in text_override.get("single_char_penalty_layers", [])}
        if "single_char_penalty" in text_override:
            profile["single_char_penalty"] = float(text_override.get("single_char_penalty", profile["single_char_penalty"]))
        if "single_char_reject_layers" in text_override:
            profile["single_char_reject_layers"] = {str(item).upper() for item in text_override.get("single_char_reject_layers", [])}
        profile["numeric_suffix_patterns"] = _compile_patterns(text_override.get("numeric_suffix_patterns", []))
        profile["derived_numeric_penalty"] = float(text_override.get("derived_numeric_penalty", profile["derived_numeric_penalty"]))
    return profile


def _compile_patterns(patterns: object) -> list[re.Pattern[str]]:
    if not isinstance(patterns, list):
        return []
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern.strip():
            continue
        compiled.append(re.compile(pattern))
    return compiled


def _candidate_numeric_value(text: TextItem, patterns: list[re.Pattern[str]]) -> str | None:
    if text.is_numeric_candidate:
        return text.normalized_text
    for pattern in patterns:
        match = pattern.search(text.normalized_text)
        if not match:
            continue
        if "value" in match.groupdict():
            return match.group("value")
        if match.groups():
            return match.group(match.lastindex or 1)
        return match.group(0)
    return None
