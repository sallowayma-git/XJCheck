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
_ORIENTATION_GRID = "grid"
_CHANNEL_TERMINAL_NUMERIC = "terminal_numeric_channel"
_CHANNEL_WIRE_LOGIC_ENDPOINT = "wire_logic_endpoint_channel"
_CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT = "schematic_semantic_endpoint_channel"
_CHANNEL_CONTINUATION = "continuation_channel"
_CHANNEL_SEMANTIC = "semantic_channel"
_CHANNEL_NOISE = "noise_channel"
_WIRE_LOGIC_ENDPOINT_PATTERN = re.compile(r"^[13]-21[A-Z]{2,4}\d{1,3}$", re.IGNORECASE)
_SCHEMATIC_DC_SEMANTIC_ENDPOINT_PATTERNS = (
    re.compile(r"^DC\s+0-5V/4-20mA\s*[+-]$", re.IGNORECASE),
    re.compile(r"^GND$", re.IGNORECASE),
)
_SCHEMATIC_NETWORK_TIME_SEMANTIC_ENDPOINT_PATTERNS = (
    re.compile(r"^TD\d+$", re.IGNORECASE),
    re.compile(r"^B\s*code\s*[+-]$", re.IGNORECASE),
    re.compile(r"^B[+-]$", re.IGNORECASE),
    re.compile(r"^Device alarm$", re.IGNORECASE),
)
_SCHEMATIC_AC_PHASE_SEMANTIC_ENDPOINT_PATTERNS = (
    re.compile(r"^(?:UA|UB|UC|UN|UX'?|3U0'?)$", re.IGNORECASE),
)
_SCHEMATIC_BINARY_INPUT_SEMANTIC_ENDPOINT_PATTERNS = (
    re.compile(r"^BI\s*\d+\s*/\s*BCD\d+$", re.IGNORECASE),
    re.compile(r"^开入\s*\d+\s*/\s*BCD\d+$", re.IGNORECASE),
)
_SCHEMATIC_BINARY_INPUT_DESCRIPTION_ENDPOINT_PATTERNS = (
    re.compile(r"^Manual closing of synchronization$", re.IGNORECASE),
    re.compile(r"^手合同期$"),
)
_TERMINAL_SEMANTIC_ROW_PATTERNS = (
    re.compile(r"^(?:UA|UB|UC|UN|3U0'?)$", re.IGNORECASE),
    re.compile(r"^(?:I0|I0'|IA|IA'|IB|IB'|IC|IC'|IN)$", re.IGNORECASE),
    re.compile(r"^AC230V(?:\s+[LN])?$", re.IGNORECASE),
    re.compile(r"^Shielding layer$", re.IGNORECASE),
    re.compile(r"^B code\s*[+-]$", re.IGNORECASE),
    re.compile(r"^(?:CZ|AK)-", re.IGNORECASE),
    re.compile(r"^(?!.*n\d{3,}$).*(?:DK|KLP|(?:K)?ZKK|CLP|KK-|ZK-).*$", re.IGNORECASE),
)


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
    candidate_id_factory: IdFactory | None = None,
) -> list[TerminalCandidate]:
    by_sheet_texts = defaultdict(list)
    for text in texts:
        by_sheet_texts[text.sheet_id].append(text)

    indexes = {sheet_id: TextSpatialIndex(sheet_texts) for sheet_id, sheet_texts in by_sheet_texts.items()}
    sheet_map = {sheet.sheet_id: sheet for sheet in sheets or []}
    group_map = {group.line_group_id: group for group in line_groups}
    candidate_ids = candidate_id_factory or IdFactory("C")

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
        orientation = group.orientation if group.orientation in {"horizontal", "vertical", "grid"} else "horizontal"
        profile = _orientation_scoped_profile(profile, sheet, orientation)
        terminal_strip_mode = _is_terminal_strip_mode(sheet, orientation)
        for side, endpoint in _endpoints_for_group(group):
            bbox = _candidate_search_bbox(group, endpoint, radius_x, radius_y, terminal_strip_mode=terminal_strip_mode)
            for text in index.query(bbox):
                dx = text.insert_x - endpoint[0]
                dy = text.insert_y - endpoint[1]
                value = _candidate_numeric_value(text, profile["numeric_suffix_patterns"])
                if value is None:
                    value = _candidate_wire_logic_endpoint_value(text, sheet, orientation)
                if value is None:
                    value = _candidate_schematic_semantic_endpoint_value(text, sheet, orientation)
                within_height = min_height <= text.height <= max_height
                vertical_alignment_score = _cross_axis_alignment_score(dx, dy, radius_x, radius_y, orientation)
                horizontal_side_score = _side_alignment_score(dx, dy, radius_x, radius_y, side, orientation)
                text_type_score = 1.0 if value is not None else 0.0
                height_score = 1.0 if within_height else 0.0
                matched_terminal_strip_bypass = _matches_terminal_strip_bypass_pattern(
                    text,
                    sheet,
                    orientation,
                    profile["terminal_strip_bypass_patterns"],
                )
                channel, channel_detail = _candidate_channel_hint(
                    text=text,
                    value=value,
                    sheet=sheet,
                    orientation=orientation,
                    matched_terminal_strip_bypass=matched_terminal_strip_bypass,
                )
                if matched_terminal_strip_bypass:
                    status = "rejected"
                    reason = "terminal_strip_bypass_text"
                    score = 0.0
                elif value is None:
                    status = "rejected"
                    reason = "not_numeric"
                    score = 0.0
                elif not within_height:
                    status = "rejected"
                    reason = "height_out_of_range"
                    score = 0.0
                elif (
                    channel == _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT
                    and channel_detail == "schematic_ac_phase_label"
                    and vertical_alignment_score <= 0.0
                ):
                    status = "rejected"
                    reason = "schematic_semantic_out_of_row"
                    score = 0.0
                    channel = _CHANNEL_NOISE
                    channel_detail = reason
                elif (
                    channel == _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT
                    and channel_detail == "schematic_binary_input_function_label"
                    and abs(dy) > 3.0
                ):
                    status = "rejected"
                    reason = "schematic_semantic_out_of_row"
                    score = 0.0
                    channel = _CHANNEL_NOISE
                    channel_detail = reason
                elif (
                    channel == _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT
                    and channel_detail == "schematic_binary_input_function_description"
                    and abs(dy) > 6.0
                ):
                    status = "rejected"
                    reason = "schematic_semantic_out_of_row"
                    score = 0.0
                    channel = _CHANNEL_NOISE
                    channel_detail = reason
                elif (
                    len(value.strip()) == 1
                    and text.layer.upper() in profile["single_char_reject_layers"]
                ):
                    status = "rejected"
                    reason = "single_char_layer_filtered"
                    score = 0.0
                    channel = _CHANNEL_NOISE
                    channel_detail = reason
                elif _is_virtual_block_internal_pin_candidate(
                    text,
                    value,
                    sheet,
                    orientation,
                    profile["virtual_single_char_reject_blocks"],
                ):
                    status = "rejected"
                    reason = "block_internal_pin_number"
                    score = 0.0
                    channel = _CHANNEL_NOISE
                    channel_detail = reason
                elif _is_terminal_strip_column_filtered(text, group, side, sheet, orientation):
                    status = "rejected"
                    reason = "terminal_strip_column_filtered"
                    score = 0.0
                else:
                    is_block_internal = ":VIRTUAL:" in text.handle.upper() and orientation == _ORIENTATION_GRID
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
                        block_internal_numeric_penalty=profile["block_internal_numeric_penalty"],
                        is_block_internal=is_block_internal,
                        terminal_strip_mode=terminal_strip_mode,
                        horizontal_distance_weight=profile["terminal_strip_distance_x_weight"],
                        cross_axis_distance_weight=profile["terminal_strip_distance_y_weight"],
                    )
                    if channel_detail in {
                        "schematic_binary_input_function_label",
                        "schematic_binary_input_function_description",
                    }:
                        score = round(0.35 + (min(score, 1.0) * 0.1), 4)
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
                        source_block_name=text.source_block_name,
                        channel=channel,
                        channel_detail=channel_detail if status == "accepted" else (reason or channel_detail),
                    )
                )
        _add_schematic_ac_phase_line_span_candidates(
            results=results,
            index=index,
            group=group,
            sheet=sheet,
            profile=profile,
            candidate_ids=candidate_ids,
        )
    _dedupe_shared_text_anchors(results, group_map, sheet_map)
    _apply_terminal_strip_row_lock(results, group_map, sheet_map)
    _apply_terminal_short_bridge_roles(results, group_map, sheet_map)
    _apply_terminal_row_number_local_numeric_filter(results, group_map, sheet_map)
    _apply_terminal_semantic_row_local_numeric_filter(results, group_map, sheet_map)
    _prefer_derived_numeric_on_vertical_component_page(results, group_map, sheet_map)
    _assign_candidate_ranks(results)
    return results


def _candidate_search_bbox(
    group: LineGroup,
    endpoint: tuple[float, float],
    radius_x: float,
    radius_y: float,
    *,
    terminal_strip_mode: bool,
) -> tuple[float, float, float, float]:
    if terminal_strip_mode:
        min_x = min(group.start_x, group.end_x) - radius_x
        max_x = max(group.start_x, group.end_x) + radius_x
        min_y = min(group.start_y, group.end_y) - radius_y
        max_y = max(group.start_y, group.end_y) + radius_y
        return (min_x, min_y, max_x, max_y)
    return (
        endpoint[0] - radius_x,
        endpoint[1] - radius_y,
        endpoint[0] + radius_x,
        endpoint[1] + radius_y,
    )


def _add_schematic_ac_phase_line_span_candidates(
    *,
    results: list[TerminalCandidate],
    index: TextSpatialIndex,
    group: LineGroup,
    sheet: SheetRecord | None,
    profile: dict[str, object],
    candidate_ids: IdFactory,
) -> None:
    if sheet is None or sheet.sheet_category != "二次原理图":
        return
    orientation = group.orientation if group.orientation in {"horizontal", "grid"} else "horizontal"
    if orientation not in {"horizontal", _ORIENTATION_GRID}:
        return

    by_side = defaultdict(list)
    existing_text_ids: set[str] = set()
    for candidate in results:
        if candidate.line_group_id != group.line_group_id:
            continue
        existing_text_ids.add(candidate.text_id)
        if candidate.status == "accepted" and candidate.channel == _CHANNEL_TERMINAL_NUMERIC:
            by_side[candidate.side].append(candidate)
    numeric_sides = {side for side, candidates in by_side.items() if candidates}
    if len(numeric_sides) != 1:
        return

    side = next(iter(numeric_sides))
    endpoint_map = dict(_endpoints_for_group(group))
    endpoint = endpoint_map[side]
    min_x = min(group.start_x, group.end_x)
    max_x = max(group.start_x, group.end_x)
    y = (group.start_y + group.end_y) / 2.0
    y_tolerance = 2.5
    min_height = float(profile["min_height"])
    max_height = float(profile["max_height"])
    radius_x = float(profile["radius_x"])
    radius_y = float(profile["radius_y"])
    bbox = (min_x, y - y_tolerance, max_x, y + y_tolerance)

    for text in index.query(bbox):
        if text.text_id in existing_text_ids:
            continue
        if not (min_height <= text.height <= max_height):
            continue
        if not (min_x <= text.insert_x <= max_x and abs(text.insert_y - y) <= y_tolerance):
            continue
        value = _candidate_schematic_semantic_endpoint_value(text, sheet, orientation)
        detail = _candidate_schematic_semantic_endpoint_detail(text, sheet, orientation)
        if value is None or detail != "schematic_ac_phase_label":
            continue
        dx = text.insert_x - endpoint[0]
        dy = text.insert_y - endpoint[1]
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
            deprioritized_layer_penalty=float(profile["deprioritized_layer_penalty"]),
            single_char_penalty_layers=profile["single_char_penalty_layers"],
            single_char_penalty=float(profile["single_char_penalty"]),
            derived_numeric_penalty=0.0,
            block_internal_numeric_penalty=float(profile["block_internal_numeric_penalty"]),
            is_block_internal=False,
            terminal_strip_mode=False,
            horizontal_distance_weight=float(profile["terminal_strip_distance_x_weight"]),
            cross_axis_distance_weight=float(profile["terminal_strip_distance_y_weight"]),
        )
        results.append(
            TerminalCandidate(
                candidate_id=candidate_ids.next(),
                line_group_id=group.line_group_id,
                sheet_id=group.sheet_id,
                file_id=group.file_id,
                side=side,
                text_id=text.text_id,
                text=text.text,
                value=value,
                score=score,
                status="accepted",
                rejection_reason=None,
                endpoint_x=endpoint[0],
                endpoint_y=endpoint[1],
                distance_x=round(abs(dx), 4),
                distance_y=round(abs(dy), 4),
                text_insert_x=text.insert_x,
                text_insert_y=text.insert_y,
                vertical_alignment_score=_cross_axis_alignment_score(dx, dy, radius_x, radius_y, orientation),
                horizontal_side_score=_side_alignment_score(dx, dy, radius_x, radius_y, side, orientation),
                text_type_score=1.0,
                height_score=1.0,
                source_block_name=text.source_block_name,
                channel=_CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT,
                channel_detail=detail,
            )
        )
        existing_text_ids.add(text.text_id)


def _endpoints_for_group(group: LineGroup) -> tuple[tuple[str, tuple[float, float]], tuple[str, tuple[float, float]]]:
    if group.orientation == _ORIENTATION_VERTICAL:
        return (("top", (group.start_x, group.start_y)), ("bottom", (group.end_x, group.end_y)))
    # horizontal 和 grid 都走 left/right 端点语义
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
    block_internal_numeric_penalty: float = 0.0,
    is_block_internal: bool = False,
    terminal_strip_mode: bool = False,
    horizontal_distance_weight: float = 0.55,
    cross_axis_distance_weight: float = 0.35,
) -> float:
    if orientation == _ORIENTATION_VERTICAL:
        distance_term = 1.0 - min(abs(dx) / max(radius_x, 1.0), 1.0) * 0.35 - min(abs(dy) / max(radius_y, 1.0), 1.0) * 0.55
    elif terminal_strip_mode:
        distance_term = 1.0 - min(abs(dx) / max(radius_x, 1.0), 1.0) * horizontal_distance_weight - min(abs(dy) / max(radius_y, 1.0), 1.0) * cross_axis_distance_weight
    else:
        # horizontal 和 grid 都走水平距离语义
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
    if is_block_internal and block_internal_numeric_penalty != 0.0:
        penalty += block_internal_numeric_penalty
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
    # horizontal 和 grid 都看 dy（垂直对齐）
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
    # horizontal 和 grid 都看 dx（左右侧对齐）
    return _horizontal_side_score(dx, radius_x, side)


def _side_bonus(dx: float, dy: float, side: str, orientation: str) -> float:
    if orientation == _ORIENTATION_VERTICAL:
        return 0.05 if (side == "top" and dy >= -2.5) or (side == "bottom" and dy <= 2.5) else 0.0
    # horizontal 和 grid 都看 dx 方向
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


def _apply_terminal_strip_row_lock(
    candidates: list[TerminalCandidate],
    group_map: dict[str, LineGroup],
    sheet_map: dict[str, SheetRecord],
) -> None:
    by_group_side = defaultdict(list)
    for candidate in candidates:
        if candidate.status != "accepted" or not candidate.value:
            continue
        group = group_map.get(candidate.line_group_id)
        sheet = sheet_map.get(candidate.sheet_id)
        if group is None or sheet is None:
            continue
        if not _is_terminal_strip_mode(sheet, group.orientation):
            continue
        by_group_side[(candidate.line_group_id, candidate.side)].append(candidate)

    for terminal_candidates in by_group_side.values():
        if len(terminal_candidates) <= 1:
            continue
        min_distance_y = min(candidate.distance_y for candidate in terminal_candidates)
        keep_threshold = min_distance_y + 1.5
        for candidate in terminal_candidates:
            if candidate.distance_y <= keep_threshold:
                continue
            candidate.status = "rejected"
            candidate.rejection_reason = "terminal_row_locked"
            candidate.value = None
            candidate.rank = None


def _apply_terminal_short_bridge_roles(
    candidates: list[TerminalCandidate],
    group_map: dict[str, LineGroup],
    sheet_map: dict[str, SheetRecord],
) -> None:
    by_group = defaultdict(list)
    for candidate in candidates:
        if candidate.status != "accepted" or not candidate.value:
            continue
        group = group_map.get(candidate.line_group_id)
        sheet = sheet_map.get(candidate.sheet_id)
        if group is None or sheet is None:
            continue
        if not _is_terminal_short_bridge_group(group, sheet):
            continue
        by_group[candidate.line_group_id].append(candidate)

    for line_group_id, grouped_candidates in by_group.items():
        group = group_map.get(line_group_id)
        if group is None:
            continue
        preferred_columns = _terminal_short_bridge_preferred_columns(grouped_candidates, group)
        if preferred_columns is None:
            continue
        for candidate in grouped_candidates:
            target_x = preferred_columns.get(candidate.side)
            if target_x is None:
                _reject_candidate(candidate, "terminal_short_bridge_single_column")
                continue
            if abs(candidate.text_insert_x - target_x) <= 4.0:
                continue
            _reject_candidate(candidate, "terminal_short_bridge_role_filtered")


def _apply_terminal_semantic_row_local_numeric_filter(
    candidates: list[TerminalCandidate],
    group_map: dict[str, LineGroup],
    sheet_map: dict[str, SheetRecord],
) -> None:
    by_group = defaultdict(list)
    for candidate in candidates:
        group = group_map.get(candidate.line_group_id)
        sheet = sheet_map.get(candidate.sheet_id)
        if group is None or sheet is None:
            continue
        if not _is_terminal_semantic_filter_group(group, sheet):
            continue
        by_group[candidate.line_group_id].append(candidate)

    for grouped_candidates in by_group.values():
        if not _has_terminal_semantic_row_marker(grouped_candidates):
            continue
        for candidate in grouped_candidates:
            if candidate.status != "accepted" or not candidate.value:
                continue
            if not _is_terminal_semantic_local_numeric_candidate(candidate):
                continue
            _reject_candidate(candidate, "terminal_semantic_local_numeric")
            candidate.channel = _CHANNEL_SEMANTIC


def _apply_terminal_row_number_local_numeric_filter(
    candidates: list[TerminalCandidate],
    group_map: dict[str, LineGroup],
    sheet_map: dict[str, SheetRecord],
) -> None:
    row_text_ids = _terminal_row_number_text_ids(candidates, group_map, sheet_map)
    if not row_text_ids:
        return
    for candidate in candidates:
        if candidate.status != "accepted" or candidate.text_id not in row_text_ids:
            continue
        _reject_candidate(candidate, "terminal_row_number_local_numeric")
        candidate.channel = _CHANNEL_SEMANTIC


def _prefer_derived_numeric_on_vertical_component_page(
    candidates: list[TerminalCandidate],
    group_map: dict[str, LineGroup],
    sheet_map: dict[str, SheetRecord],
) -> None:
    by_group_side = defaultdict(list)
    for candidate in candidates:
        if candidate.status != "accepted" or not candidate.value:
            continue
        group = group_map.get(candidate.line_group_id)
        sheet = sheet_map.get(candidate.sheet_id)
        if group is None or sheet is None:
            continue
        if group.orientation != _ORIENTATION_VERTICAL or sheet.sheet_category != "元件接线图":
            continue
        by_group_side[(candidate.line_group_id, candidate.side)].append(candidate)

    for grouped_candidates in by_group_side.values():
        has_derived_numeric = any(candidate.text.strip() != (candidate.value or "").strip() for candidate in grouped_candidates)
        if not has_derived_numeric:
            continue
        for candidate in grouped_candidates:
            if candidate.text.strip() == (candidate.value or "").strip():
                candidate.status = "rejected"
                candidate.rejection_reason = "superseded_by_derived_numeric"
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
        "virtual_single_char_reject_blocks": {str(item).upper() for item in text_config.get("virtual_single_char_reject_blocks", [])},
        "block_internal_numeric_penalty": float(text_config.get("block_internal_numeric_penalty", 0.0)),
        "terminal_strip_bypass_patterns": [],
        "terminal_strip_distance_x_weight": float(text_config.get("terminal_strip_distance_x_weight", 0.55)),
        "terminal_strip_distance_y_weight": float(text_config.get("terminal_strip_distance_y_weight", 0.35)),
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
        if "virtual_single_char_reject_blocks" in text_override:
            profile["virtual_single_char_reject_blocks"] = {
                str(item).upper() for item in text_override.get("virtual_single_char_reject_blocks", [])
            }
        if "terminal_strip_bypass_patterns" in text_override:
            profile["terminal_strip_bypass_patterns"] = _compile_patterns(text_override.get("terminal_strip_bypass_patterns", []))
        if "terminal_strip_distance_x_weight" in text_override:
            profile["terminal_strip_distance_x_weight"] = float(text_override.get("terminal_strip_distance_x_weight", profile["terminal_strip_distance_x_weight"]))
        if "terminal_strip_distance_y_weight" in text_override:
            profile["terminal_strip_distance_y_weight"] = float(text_override.get("terminal_strip_distance_y_weight", profile["terminal_strip_distance_y_weight"]))
    return profile


def _orientation_scoped_profile(
    profile: dict[str, object],
    sheet: SheetRecord | None,
    orientation: str,
) -> dict[str, object]:
    scoped = dict(profile)
    if sheet is None:
        return scoped
    if sheet.sheet_category == "元件接线图" and orientation != _ORIENTATION_VERTICAL:
        scoped["numeric_suffix_patterns"] = []
        scoped["derived_numeric_penalty"] = 0.0
    return scoped


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


def _candidate_wire_logic_endpoint_value(
    text: TextItem,
    sheet: SheetRecord | None,
    orientation: str,
) -> str | None:
    if sheet is None or sheet.sheet_category != "二次原理图":
        return None
    if orientation not in {"horizontal", _ORIENTATION_GRID}:
        return None
    normalized = text.normalized_text.strip()
    if not _WIRE_LOGIC_ENDPOINT_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _candidate_schematic_semantic_endpoint_value(
    text: TextItem,
    sheet: SheetRecord | None,
    orientation: str,
) -> str | None:
    if _candidate_schematic_semantic_endpoint_detail(text, sheet, orientation) is None:
        return None
    return _normalize_schematic_semantic_endpoint_value(text.normalized_text.strip())


def _candidate_schematic_semantic_endpoint_detail(
    text: TextItem,
    sheet: SheetRecord | None,
    orientation: str,
) -> str | None:
    if sheet is None or sheet.sheet_category != "二次原理图":
        return None
    if orientation not in {"horizontal", _ORIENTATION_GRID}:
        return None
    sheet_context = f"{sheet.filename} {sheet.sheet_title}".upper()
    normalized = text.normalized_text.strip()
    if (
        ("直流" in sheet_context or "DC" in sheet_context)
        and any(pattern.fullmatch(normalized) for pattern in _SCHEMATIC_DC_SEMANTIC_ENDPOINT_PATTERNS)
    ):
        return "schematic_dc_function_label"
    if (
        any(marker in sheet_context for marker in ("网络", "对时", "COMMUNICATION", "TIME SYNCHRONIZATION"))
        and any(pattern.fullmatch(normalized) for pattern in _SCHEMATIC_NETWORK_TIME_SEMANTIC_ENDPOINT_PATTERNS)
    ):
        return "schematic_network_time_label"
    if (
        any(marker in sheet_context for marker in ("交流", "AC", "CT AND VT", "VOLTAGE", "CURRENT"))
        and any(pattern.fullmatch(normalized) for pattern in _SCHEMATIC_AC_PHASE_SEMANTIC_ENDPOINT_PATTERNS)
    ):
        return "schematic_ac_phase_label"
    if (
        any(marker in sheet_context for marker in ("BINARY INPUT", "开入", "测控"))
        and any(pattern.fullmatch(normalized) for pattern in _SCHEMATIC_BINARY_INPUT_SEMANTIC_ENDPOINT_PATTERNS)
    ):
        return "schematic_binary_input_function_label"
    if (
        any(marker in sheet_context for marker in ("BINARY INPUT", "开入"))
        and any(pattern.fullmatch(normalized) for pattern in _SCHEMATIC_BINARY_INPUT_DESCRIPTION_ENDPOINT_PATTERNS)
    ):
        return "schematic_binary_input_function_description"
    return None


def _normalize_schematic_semantic_endpoint_value(normalized: str) -> str:
    value = re.sub(r"\s*/\s*", "/", normalized.strip())
    value = re.sub(r"\s+", " ", value)
    return value


def _is_terminal_strip_mode(sheet: SheetRecord | None, orientation: str) -> bool:
    return sheet is not None and sheet.sheet_category == "屏端子图" and orientation != _ORIENTATION_VERTICAL


def _matches_terminal_strip_bypass_pattern(
    text: TextItem,
    sheet: SheetRecord | None,
    orientation: str,
    patterns: list[re.Pattern[str]],
) -> bool:
    if not patterns or not _is_terminal_strip_mode(sheet, orientation):
        return False
    normalized = text.normalized_text.strip()
    return any(pattern.search(normalized) for pattern in patterns)


def _is_terminal_strip_column_filtered(
    text: TextItem,
    group: LineGroup,
    side: str,
    sheet: SheetRecord | None,
    orientation: str,
) -> bool:
    if not _is_terminal_strip_mode(sheet, orientation):
        return False
    layout_mode = _terminal_strip_layout_mode(sheet)
    if layout_mode is None:
        return False
    if not (70.0 <= group.length <= 80.0):
        return False
    if group.start_x >= 300.0:
        return False
    offset = text.insert_x - min(group.start_x, group.end_x)
    allowed = _terminal_strip_allowed_offset_range(layout_mode, side)
    if allowed is None:
        return False
    min_offset, max_offset = allowed
    return not (min_offset <= offset <= max_offset)
    return False


def _is_terminal_short_bridge_group(group: LineGroup, sheet: SheetRecord | None) -> bool:
    return (
        sheet is not None
        and sheet.sheet_category == "屏端子图"
        and group.orientation != _ORIENTATION_VERTICAL
        and 70.0 <= group.length <= 80.0
        and min(group.start_x, group.end_x) >= 300.0
    )


def _is_terminal_semantic_filter_group(group: LineGroup, sheet: SheetRecord | None) -> bool:
    return (
        sheet is not None
        and sheet.sheet_category == "屏端子图"
        and group.orientation != _ORIENTATION_VERTICAL
        and 70.0 <= group.length <= 80.0
        and min(group.start_x, group.end_x) < 300.0
    )


def _terminal_strip_layout_mode(sheet: SheetRecord | None) -> str | None:
    if sheet is None or sheet.sheet_category != "屏端子图":
        return None
    filename = (sheet.filename or "").strip()
    title = (sheet.sheet_title or "").strip()
    combined = f"{filename} {title}"
    if "左侧" in combined:
        return "left_terminal"
    if "右侧" in combined:
        return "right_terminal"
    return None


def _terminal_strip_allowed_offset_range(layout_mode: str, side: str) -> tuple[float, float] | None:
    if layout_mode == "left_terminal":
        if side == "left":
            return (22.5, 25.5)
        if side == "right":
            return (29.5, 32.5)
        return None
    if layout_mode == "right_terminal":
        if side == "left":
            return (24.5, 28.5)
        if side == "right":
            return (47.0, 50.5)
        return None
    return None


def _terminal_short_bridge_preferred_columns(
    candidates: list[TerminalCandidate],
    group: LineGroup,
) -> dict[str, float] | None:
    clusters = _cluster_terminal_short_bridge_columns(candidates)
    if not clusters:
        return None

    derived_clusters = [cluster["center_x"] for cluster in clusters if cluster["has_derived_numeric"]]
    if len(derived_clusters) >= 2:
        return {"left": min(derived_clusters), "right": max(derived_clusters)}
    if len(derived_clusters) == 1:
        centers = [cluster["center_x"] for cluster in clusters]
        if len(centers) > 1:
            if derived_clusters[0] == min(centers):
                return {"left": derived_clusters[0], "right": None}
            if derived_clusters[0] == max(centers):
                return {"left": None, "right": derived_clusters[0]}
        preferred_side = _nearest_terminal_side(group, derived_clusters[0])
        other_side = "right" if preferred_side == "left" else "left"
        return {preferred_side: derived_clusters[0], other_side: None}

    if len(clusters) == 1:
        preferred_side = _nearest_terminal_side(group, clusters[0]["center_x"])
        other_side = "right" if preferred_side == "left" else "left"
        return {preferred_side: clusters[0]["center_x"], other_side: None}

    centers = [cluster["center_x"] for cluster in clusters]
    return {"left": min(centers), "right": max(centers)}


def _cluster_terminal_short_bridge_columns(candidates: list[TerminalCandidate]) -> list[dict[str, object]]:
    unique_candidates: dict[str, TerminalCandidate] = {}
    for candidate in candidates:
        unique_candidates.setdefault(candidate.text_id, candidate)

    ordered = sorted(unique_candidates.values(), key=lambda item: item.text_insert_x)
    clusters: list[dict[str, object]] = []
    for candidate in ordered:
        is_derived_numeric = candidate.text.strip() != (candidate.value or "").strip()
        if not clusters or abs(candidate.text_insert_x - float(clusters[-1]["center_x"])) > 4.0:
            clusters.append(
                {
                    "center_x": candidate.text_insert_x,
                    "has_derived_numeric": is_derived_numeric,
                }
            )
            continue
        last = clusters[-1]
        last["center_x"] = round((float(last["center_x"]) + candidate.text_insert_x) / 2.0, 4)
        last["has_derived_numeric"] = bool(last["has_derived_numeric"]) or is_derived_numeric
    return clusters


def _nearest_terminal_side(group: LineGroup, x_coord: float) -> str:
    left_edge = min(group.start_x, group.end_x)
    right_edge = max(group.start_x, group.end_x)
    if abs(x_coord - left_edge) <= abs(right_edge - x_coord):
        return "left"
    return "right"


def _has_terminal_semantic_row_marker(candidates: list[TerminalCandidate]) -> bool:
    for candidate in candidates:
        if _looks_like_terminal_semantic_marker(candidate.text):
            return True
    return False


def _is_terminal_semantic_local_numeric_candidate(candidate: TerminalCandidate) -> bool:
    text = candidate.text.strip()
    value = (candidate.value or "").strip()
    return text == value and value.isdigit() and len(value) <= 2


def _terminal_row_number_text_ids(
    candidates: list[TerminalCandidate],
    group_map: dict[str, LineGroup],
    sheet_map: dict[str, SheetRecord],
) -> set[str]:
    by_sheet_column: dict[tuple[str, int], dict[str, TerminalCandidate]] = defaultdict(dict)
    for candidate in candidates:
        if candidate.status != "accepted" or not _is_terminal_row_number_candidate(candidate):
            continue
        group = group_map.get(candidate.line_group_id)
        sheet = sheet_map.get(candidate.sheet_id)
        if group is None or sheet is None:
            continue
        if not _is_terminal_strip_mode(sheet, group.orientation):
            continue
        column_key = int(round(candidate.text_insert_x / 1.0))
        by_sheet_column[(candidate.sheet_id, column_key)].setdefault(candidate.text_id, candidate)

    row_text_ids: set[str] = set()
    for column_candidates in by_sheet_column.values():
        ordered = sorted(
            column_candidates.values(),
            key=lambda item: (-item.text_insert_y, int(item.value or "0"), item.text_id),
        )
        for run in _terminal_row_number_runs(ordered):
            if len(run) >= 5:
                row_text_ids.update(item.text_id for item in run)
    return row_text_ids


def _terminal_row_number_runs(candidates: list[TerminalCandidate]) -> list[list[TerminalCandidate]]:
    runs: list[list[TerminalCandidate]] = []
    current: list[TerminalCandidate] = []
    for candidate in candidates:
        if not current:
            current = [candidate]
            continue
        previous = current[-1]
        if _continues_terminal_row_number_run(previous, candidate):
            current.append(candidate)
            continue
        runs.append(current)
        current = [candidate]
    if current:
        runs.append(current)
    return runs


def _continues_terminal_row_number_run(previous: TerminalCandidate, candidate: TerminalCandidate) -> bool:
    previous_value = int(previous.value or "0")
    value = int(candidate.value or "0")
    return (
        abs(candidate.text_insert_y - previous.text_insert_y) <= 6.0
        and abs(candidate.text_insert_x - previous.text_insert_x) <= 1.0
        and abs(value - previous_value) == 1
    )


def _is_terminal_row_number_candidate(candidate: TerminalCandidate) -> bool:
    text = candidate.text.strip()
    value = (candidate.value or "").strip()
    if text != value or not value.isdigit() or len(value) > 2:
        return False
    number = int(value)
    return 1 <= number <= 99


def _reject_candidate(candidate: TerminalCandidate, reason: str) -> None:
    candidate.status = "rejected"
    candidate.rejection_reason = reason
    candidate.value = None
    candidate.rank = None
    candidate.channel_detail = reason


def _is_virtual_block_internal_pin_candidate(
    text: TextItem,
    value: str,
    sheet: SheetRecord | None,
    orientation: str,
    reject_blocks: set[str],
) -> bool:
    if not reject_blocks or sheet is None:
        return False
    if sheet.sheet_category != "元件接线图" or orientation != _ORIENTATION_VERTICAL:
        return False
    if ":VIRTUAL:" not in text.handle.upper():
        return False
    if len(value.strip()) != 1:
        return False
    source_block_name = (text.source_block_name or "").upper()
    return source_block_name in reject_blocks


def _candidate_channel_hint(
    *,
    text: TextItem,
    value: str | None,
    sheet: SheetRecord | None,
    orientation: str,
    matched_terminal_strip_bypass: bool,
) -> tuple[str, str | None]:
    if (
        sheet is not None
        and sheet.sheet_category == "屏端子图"
        and (
            matched_terminal_strip_bypass
            or _looks_like_terminal_semantic_marker(text.text)
        )
    ):
        return _CHANNEL_SEMANTIC, "terminal_semantic_marker"
    if value is not None:
        if _candidate_wire_logic_endpoint_value(text, sheet, orientation) == value:
            return _CHANNEL_WIRE_LOGIC_ENDPOINT, "schematic_wire_logic_endpoint"
        if _candidate_schematic_semantic_endpoint_value(text, sheet, orientation) == value:
            return _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT, _candidate_schematic_semantic_endpoint_detail(
                text, sheet, orientation
            )
        return _CHANNEL_TERMINAL_NUMERIC, None
    return _CHANNEL_NOISE, "not_numeric"


def _looks_like_terminal_semantic_marker(text: str) -> bool:
    normalized = text.strip()
    return any(pattern.search(normalized) for pattern in _TERMINAL_SEMANTIC_ROW_PATTERNS)
