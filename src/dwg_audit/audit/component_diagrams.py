from __future__ import annotations

import re

from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_STRIP_BLOCK_NAME = "FJL-25-2A_Mirror"
_KK_MULTI_PORT_BLOCK_PORTS = {
    "KK2P": 4,
    "KK3P": 6,
}
_SMALL_PORT_BOX_BLOCK_PORTS = {
    "KK1P": {"1", "2"},
    "KK2P": {"1", "2", "3", "4"},
    "JR-01": {"1", "2"},
}
_COMPONENT_BODY_PATTERN = re.compile(r"^\d+(?:-\d+)?(?:KLP|CLP|ZLP)\d+$", re.IGNORECASE)
_KK_COMPONENT_BODY_PATTERN = re.compile(r"^\d+(?:-\d+)?[A-Za-z]{1,5}\d*$", re.IGNORECASE)
_SMALL_PORT_BOX_BODY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z']{0,4}$", re.IGNORECASE)
_STRIP_ENDPOINT_BRIDGE_TOP_PATTERN = re.compile(r"^(?P<prefix>\d+-\d+)ZK-(?P<port>\d+)$", re.IGNORECASE)
_STRIP_ENDPOINT_BRIDGE_BOTTOM_PATTERN = re.compile(r"^(?P<prefix>\d+-\d+)n(?P<number>\d{3,})$", re.IGNORECASE)
_EXTERNAL_ENDPOINT_PATTERN = re.compile(
    r"^(?:\d+(?:-\d+)?[A-Za-z]{1,4}\d+(?:-\d+)?|[A-Za-z]{1,4}\d+(?:-\d+)?)$",
    re.IGNORECASE,
)
_SMALL_PORT_EXTERNAL_ENDPOINT_PATTERN = re.compile(
    r"^(?:\d+(?:-\d+)?[A-Za-z]{1,4}\d+(?:-\d+)?|[A-Za-z][A-Za-z']{0,4}\d*(?:-\d+)?)$",
    re.IGNORECASE,
)
_PAIR_CONFIDENCE = 0.95
_PORT_X_TOL = 3.5
_PORT_Y_MIN_GAP = 8.0
_PORT_Y_MAX_GAP = 24.0
_BODY_X_TOL = 12.0
_BODY_Y_MIN_GAP = 8.0
_BODY_Y_MAX_GAP = 24.0
_ENDPOINT_X_TOL = 22.0
_TOP_ENDPOINT_Y_MIN_GAP = 1.0
_TOP_ENDPOINT_Y_MAX_GAP = 9.0
_BOTTOM_ENDPOINT_Y_MIN_GAP = 1.0
_BOTTOM_ENDPOINT_Y_MAX_GAP = 9.0
_VERTICAL_LINE_X_TOL = 4.0
_KK_PORT_BLOCK_X_TOL = 40.0
_KK_PORT_BLOCK_Y_TOL = 80.0
_KK_BODY_X_TOL = 32.0
_KK_BODY_Y_MIN_GAP = 3.0
_KK_BODY_Y_MAX_GAP = 36.0
_KK_HORIZONTAL_LINE_Y_TOL = 4.5
_KK_HORIZONTAL_LINE_X_TOL = 18.0
_KK_SLOT_ENDPOINT_X_TOL = 8.0
_KK_SLOT_ENDPOINT_Y_MIN_GAP = 1.0
_KK_SLOT_ENDPOINT_Y_MAX_GAP = 18.0
_SMALL_PORT_BLOCK_X_TOL = 26.0
_SMALL_PORT_BLOCK_Y_TOL = 42.0
_SMALL_PORT_BODY_X_TOL = 18.0
_SMALL_PORT_BODY_Y_MIN_GAP = 8.0
_SMALL_PORT_BODY_Y_MAX_GAP = 36.0
_SMALL_PORT_ENDPOINT_X_TOL = 9.0
_SMALL_PORT_ENDPOINT_Y_MIN_GAP = 2.0
_SMALL_PORT_ENDPOINT_Y_MAX_GAP = 12.0
_SMALL_PORT_SUPPORT_LINE_Y_TOL = 3.5
_SMALL_PORT_SUPPORT_LINE_X_TOL = 8.0


def extract_strip_two_port_component_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    line_groups: list[LineGroup],
    *,
    pair_id_factory: IdFactory | None = None,
) -> tuple[list[Pair], set[str]]:
    """Recover narrow strip two-port component mappings on component diagrams."""

    pair_ids = pair_id_factory or IdFactory("PCM")
    texts_by_sheet: dict[str, list[TextItem]] = {}
    for text in texts:
        texts_by_sheet.setdefault(text.sheet_id, []).append(text)
    groups_by_sheet: dict[str, list[LineGroup]] = {}
    for group in line_groups:
        groups_by_sheet.setdefault(group.sheet_id, []).append(group)

    pairs: list[Pair] = []
    consumed_group_ids: set[str] = set()
    for page in pages:
        if not _supports_strip_two_port_component(page):
            continue
        sheet_texts = texts_by_sheet.get(page.sheet_id, [])
        sheet_groups = groups_by_sheet.get(page.sheet_id, [])
        for port_top, port_bottom in _strip_port_pairs(sheet_texts):
            body = _nearest_component_body(port_top, sheet_texts)
            if body is None:
                continue
            top_endpoint = _nearest_strip_external_endpoints(port_top, sheet_texts, side="top")
            bottom_endpoint = _nearest_strip_external_endpoints(port_bottom, sheet_texts, side="bottom")
            if top_endpoint is None or bottom_endpoint is None:
                continue
            support_group = _nearest_supporting_vertical_group(port_top, port_bottom, sheet_groups)
            if support_group is None:
                continue

            endpoint_specs = [
                (port_top, top_endpoint, "top"),
                (port_bottom, bottom_endpoint, "bottom"),
            ]
            built_pairs: list[Pair] = []
            for port, endpoint_result, side_label in endpoint_specs:
                endpoint, endpoint_values = endpoint_result
                if not endpoint_values:
                    break
                logical_endpoint = f"{body.normalized_text}-{port.normalized_text}"
                for endpoint_value in endpoint_values:
                    built_pairs.append(
                        _build_strip_two_port_pair(
                            page=page,
                            body=body,
                            port=port,
                            endpoint=endpoint,
                            endpoint_value=endpoint_value,
                            side_label=side_label,
                            support_group=support_group,
                            pair_ids=pair_ids,
                            logical_endpoint=logical_endpoint,
                        )
                    )
            if len(built_pairs) < 2:
                continue
            consumed_group_ids.add(support_group.line_group_id)
            pairs.extend(built_pairs)
    return pairs, consumed_group_ids


def extract_strip_two_port_endpoint_bridge_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    line_groups: list[LineGroup],
    *,
    pair_id_factory: IdFactory | None = None,
) -> tuple[list[Pair], set[str]]:
    """Recover direct ZK-to-n endpoint bridges on strip two-port component blocks."""

    pair_ids = pair_id_factory or IdFactory("PCM")
    texts_by_sheet: dict[str, list[TextItem]] = {}
    for text in texts:
        texts_by_sheet.setdefault(text.sheet_id, []).append(text)
    groups_by_sheet: dict[str, list[LineGroup]] = {}
    for group in line_groups:
        groups_by_sheet.setdefault(group.sheet_id, []).append(group)

    pairs: list[Pair] = []
    consumed_group_ids: set[str] = set()
    for page in pages:
        if not _supports_strip_two_port_component(page):
            continue
        sheet_texts = texts_by_sheet.get(page.sheet_id, [])
        sheet_groups = groups_by_sheet.get(page.sheet_id, [])
        for port_top, port_bottom in _strip_port_pairs(sheet_texts):
            top_endpoint = _nearest_strip_endpoint_bridge_endpoint(port_top, sheet_texts, side="top")
            bottom_endpoint = _nearest_strip_endpoint_bridge_endpoint(port_bottom, sheet_texts, side="bottom")
            if top_endpoint is None or bottom_endpoint is None:
                continue
            top_value = _clean_external_endpoint(top_endpoint.normalized_text)
            bottom_value = _clean_external_endpoint(bottom_endpoint.normalized_text)
            if not _is_valid_strip_endpoint_bridge(top_value, bottom_value):
                continue
            support_group = _nearest_supporting_vertical_group(port_top, port_bottom, sheet_groups)
            if support_group is None:
                continue
            consumed_group_ids.add(support_group.line_group_id)
            pairs.append(
                _build_strip_endpoint_bridge_pair(
                    page=page,
                    port_top=port_top,
                    port_bottom=port_bottom,
                    top_endpoint=top_endpoint,
                    bottom_endpoint=bottom_endpoint,
                    top_value=top_value,
                    bottom_value=bottom_value,
                    support_group=support_group,
                    pair_ids=pair_ids,
                )
            )
    return pairs, consumed_group_ids


def extract_kk_multi_port_component_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    line_groups: list[LineGroup],
    blocks: list[BlockRecord],
    *,
    pair_id_factory: IdFactory | None = None,
) -> tuple[list[Pair], set[str]]:
    """Recover KK2P/KK3P multi-port component mappings on component diagrams."""

    pair_ids = pair_id_factory or IdFactory("PCM")
    texts_by_sheet: dict[str, list[TextItem]] = {}
    for text in texts:
        texts_by_sheet.setdefault(text.sheet_id, []).append(text)
    groups_by_sheet: dict[str, list[LineGroup]] = {}
    for group in line_groups:
        groups_by_sheet.setdefault(group.sheet_id, []).append(group)
    blocks_by_sheet: dict[str, list[BlockRecord]] = {}
    for block in blocks:
        blocks_by_sheet.setdefault(block.sheet_id, []).append(block)

    pairs: list[Pair] = []
    consumed_group_ids: set[str] = set()
    for page in pages:
        if not _supports_strip_two_port_component(page):
            continue
        sheet_texts = texts_by_sheet.get(page.sheet_id, [])
        sheet_groups = groups_by_sheet.get(page.sheet_id, [])
        sheet_blocks = blocks_by_sheet.get(page.sheet_id, [])
        for block in sheet_blocks:
            port_count = _kk_multi_port_count(block)
            if port_count is None:
                continue
            ports_by_number = _kk_ports_for_block(block, sheet_texts, sheet_blocks, port_count)
            if not ports_by_number:
                continue
            body = _nearest_kk_component_body(block, list(ports_by_number.values()), sheet_texts)
            if body is None:
                continue
            excluded_text_ids = {body.text_id, *(port.text_id for port in ports_by_number.values())}
            used_endpoint_text_ids: set[str] = set()
            for port_number in sorted(ports_by_number, key=int):
                port_slot = _kk_port_slot(port_count, port_number)
                if port_slot is None:
                    continue
                port = ports_by_number[port_number]
                endpoint = _nearest_kk_external_endpoint(
                    port,
                    sheet_texts,
                    port_slot=port_slot,
                    excluded_text_ids=excluded_text_ids,
                    used_endpoint_text_ids=used_endpoint_text_ids,
                )
                if endpoint is None:
                    continue
                endpoint_value = _clean_external_endpoint(endpoint.normalized_text)
                if not _is_valid_external_endpoint(endpoint_value):
                    continue
                support_group = _nearest_kk_slot_supporting_group(port, endpoint, sheet_groups)
                if support_group is None:
                    continue
                if endpoint.text_id in used_endpoint_text_ids:
                    continue
                logical_endpoint = f"{body.normalized_text}-{port.normalized_text}"
                used_endpoint_text_ids.add(endpoint.text_id)
                consumed_group_ids.add(support_group.line_group_id)
                pairs.append(
                    _build_kk_multi_port_pair(
                        page=page,
                        block=block,
                        body=body,
                        port=port,
                        endpoint=endpoint,
                        endpoint_value=endpoint_value,
                        support_group=support_group,
                        pair_ids=pair_ids,
                        logical_endpoint=logical_endpoint,
                    )
                )
    return pairs, consumed_group_ids


def extract_small_port_box_component_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    line_groups: list[LineGroup],
    blocks: list[BlockRecord],
    *,
    pair_id_factory: IdFactory | None = None,
) -> tuple[list[Pair], set[str]]:
    """Recover small port-box component mappings on component diagrams."""

    pair_ids = pair_id_factory or IdFactory("PCM")
    texts_by_sheet: dict[str, list[TextItem]] = {}
    for text in texts:
        texts_by_sheet.setdefault(text.sheet_id, []).append(text)
    groups_by_sheet: dict[str, list[LineGroup]] = {}
    for group in line_groups:
        groups_by_sheet.setdefault(group.sheet_id, []).append(group)
    blocks_by_sheet: dict[str, list[BlockRecord]] = {}
    for block in blocks:
        blocks_by_sheet.setdefault(block.sheet_id, []).append(block)

    pairs: list[Pair] = []
    consumed_group_ids: set[str] = set()
    for page in pages:
        if not _supports_strip_two_port_component(page):
            continue
        sheet_texts = texts_by_sheet.get(page.sheet_id, [])
        sheet_groups = groups_by_sheet.get(page.sheet_id, [])
        sheet_blocks = blocks_by_sheet.get(page.sheet_id, [])
        for block in sheet_blocks:
            allowed_ports = _small_port_box_allowed_ports(block)
            if not allowed_ports:
                continue
            ports_by_number = _small_port_box_ports_for_block(block, sheet_texts, sheet_blocks, allowed_ports)
            if set(ports_by_number) != allowed_ports:
                continue
            body = _nearest_small_port_box_body(block, list(ports_by_number.values()), sheet_texts)
            if body is None:
                continue
            excluded_text_ids = {body.text_id, *(port.text_id for port in ports_by_number.values())}
            for port_number in sorted(ports_by_number, key=int):
                port = ports_by_number[port_number]
                endpoint_side = _small_port_box_endpoint_side(port, ports_by_number)
                endpoint = _nearest_small_port_box_endpoint(
                    port,
                    sheet_texts,
                    side=endpoint_side,
                    excluded_text_ids=excluded_text_ids,
                )
                if endpoint is None:
                    continue
                endpoint_value = _clean_small_port_external_endpoint(endpoint.normalized_text)
                support_group = _nearest_small_port_support_group(port, endpoint, sheet_groups)
                if support_group is not None:
                    consumed_group_ids.add(support_group.line_group_id)
                logical_endpoint = f"{body.normalized_text}-{port.normalized_text}"
                pairs.append(
                    _build_small_port_box_pair(
                        page=page,
                        block=block,
                        body=body,
                        port=port,
                        endpoint=endpoint,
                        endpoint_value=endpoint_value,
                        endpoint_side=endpoint_side,
                        support_group=support_group,
                        pair_ids=pair_ids,
                        logical_endpoint=logical_endpoint,
                        instance_items=[body, port, endpoint],
                    )
                )
    return pairs, consumed_group_ids


def _supports_strip_two_port_component(page: SheetRecord) -> bool:
    return (
        page.sheet_category == "元件接线图"
        and page.page_subtype == "horizontal_component"
        and page.route_target == "ComponentDiagramExtractor"
    )


def _kk_multi_port_count(block: BlockRecord) -> int | None:
    return _KK_MULTI_PORT_BLOCK_PORTS.get((block.name or "").upper())


def _small_port_box_allowed_ports(block: BlockRecord) -> set[str]:
    return set(_SMALL_PORT_BOX_BLOCK_PORTS.get((block.name or "").upper(), set()))


def _kk_ports_for_block(
    block: BlockRecord,
    texts: list[TextItem],
    blocks: list[BlockRecord],
    port_count: int,
) -> dict[str, TextItem]:
    allowed_ports = {str(port_number) for port_number in range(1, port_count + 1)}
    matching_blocks = [
        other
        for other in blocks
        if other.sheet_id == block.sheet_id and (other.name or "").upper() == (block.name or "").upper()
    ]
    candidates_by_number: dict[str, list[TextItem]] = {}
    for text in texts:
        if (text.source_block_name or "").upper() != (block.name or "").upper():
            continue
        port_number = str(text.normalized_text or "").strip()
        if port_number not in allowed_ports:
            continue
        if abs(text.insert_x - block.insert_x) > _KK_PORT_BLOCK_X_TOL:
            continue
        if abs(text.insert_y - block.insert_y) > _KK_PORT_BLOCK_Y_TOL:
            continue
        if _nearest_block_to_text(text, matching_blocks) != block:
            continue
        candidates_by_number.setdefault(port_number, []).append(text)
    return {
        port_number: sorted(items, key=lambda item: (_block_text_distance(block, item), item.text_id))[0]
        for port_number, items in candidates_by_number.items()
    }


def _small_port_box_ports_for_block(
    block: BlockRecord,
    texts: list[TextItem],
    blocks: list[BlockRecord],
    allowed_ports: set[str],
) -> dict[str, TextItem]:
    matching_blocks = [
        other
        for other in blocks
        if other.sheet_id == block.sheet_id and (other.name or "").upper() == (block.name or "").upper()
    ]
    candidates_by_number: dict[str, list[TextItem]] = {}
    for text in texts:
        if (text.source_block_name or "").upper() != (block.name or "").upper():
            continue
        port_number = str(text.normalized_text or "").strip()
        if port_number not in allowed_ports:
            continue
        if abs(text.insert_x - block.insert_x) > _SMALL_PORT_BLOCK_X_TOL:
            continue
        if abs(text.insert_y - block.insert_y) > _SMALL_PORT_BLOCK_Y_TOL:
            continue
        if _nearest_block_to_text(text, matching_blocks) != block:
            continue
        candidates_by_number.setdefault(port_number, []).append(text)
    return {
        port_number: sorted(items, key=lambda item: (_block_text_distance(block, item), item.text_id))[0]
        for port_number, items in candidates_by_number.items()
    }


def _nearest_block_to_text(text: TextItem, blocks: list[BlockRecord]) -> BlockRecord | None:
    if not blocks:
        return None
    return sorted(blocks, key=lambda block: (_block_text_distance(block, text), block.block_id))[0]


def _block_text_distance(block: BlockRecord, text: TextItem) -> float:
    center_x, center_y = _text_center(text)
    return ((center_x - block.insert_x) ** 2) + ((center_y - block.insert_y) ** 2)


def _nearest_kk_component_body(
    block: BlockRecord,
    ports: list[TextItem],
    texts: list[TextItem],
) -> TextItem | None:
    anchor_x = sum(_text_center(port)[0] for port in ports) / len(ports)
    top_port_y = max(_text_center(port)[1] for port in ports)
    candidates = []
    for text in texts:
        if text.source_block_name:
            continue
        value = str(text.normalized_text or "").strip()
        if not _KK_COMPONENT_BODY_PATTERN.fullmatch(value):
            continue
        center_x, center_y = _text_center(text)
        if abs(center_x - anchor_x) > _KK_BODY_X_TOL:
            continue
        if not (_KK_BODY_Y_MIN_GAP <= center_y - top_port_y <= _KK_BODY_Y_MAX_GAP):
            continue
        candidates.append(text)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            abs(_text_center(item)[0] - anchor_x),
            abs(_text_center(item)[1] - block.insert_y),
            item.text_id,
        ),
    )[0]


def _nearest_small_port_box_body(
    block: BlockRecord,
    ports: list[TextItem],
    texts: list[TextItem],
) -> TextItem | None:
    anchor_x = sum(_text_center(port)[0] for port in ports) / len(ports)
    top_port_y = max(_text_center(port)[1] for port in ports)
    candidates = []
    for text in texts:
        if text.source_block_name:
            continue
        if text.layer.upper() != "MARK":
            continue
        value = str(text.normalized_text or "").strip()
        if not _SMALL_PORT_BOX_BODY_PATTERN.fullmatch(value):
            continue
        center_x, center_y = _text_center(text)
        if abs(center_x - anchor_x) > _SMALL_PORT_BODY_X_TOL:
            continue
        if not (_SMALL_PORT_BODY_Y_MIN_GAP <= center_y - top_port_y <= _SMALL_PORT_BODY_Y_MAX_GAP):
            continue
        candidates.append(text)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            abs(_text_center(item)[0] - anchor_x),
            abs(_text_center(item)[1] - block.insert_y),
            item.text_id,
        ),
    )[0]


def _nearest_supporting_horizontal_group(port: TextItem, line_groups: list[LineGroup]) -> LineGroup | None:
    port_x, port_y = _text_center(port)
    candidates = []
    for group in line_groups:
        if group.orientation != "horizontal":
            continue
        group_y = (group.start_y + group.end_y) / 2.0
        if abs(group_y - port_y) > _KK_HORIZONTAL_LINE_Y_TOL:
            continue
        min_x = min(group.start_x, group.end_x)
        max_x = max(group.start_x, group.end_x)
        x_gap = 0.0 if min_x <= port_x <= max_x else min(abs(port_x - min_x), abs(port_x - max_x))
        if x_gap > _KK_HORIZONTAL_LINE_X_TOL:
            continue
        candidates.append((group, x_gap))
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            abs(((item[0].start_y + item[0].end_y) / 2.0) - port_y),
            item[1],
            -item[0].length,
            item[0].line_group_id,
        ),
    )[0][0]


def _kk_port_slot(port_count: int, port_number: str) -> tuple[str, int] | None:
    try:
        number = int(port_number)
    except ValueError:
        return None
    if number < 1 or number > port_count:
        return None
    if port_count == 4:
        if number in {1, 2}:
            column = 0
        elif number in {3, 4}:
            column = 1
        else:
            return None
    elif port_count == 6:
        column = (number - 1) // 2
    else:
        return None
    row = "top" if number % 2 == 1 else "bottom"
    return row, column


def _nearest_kk_external_endpoint(
    port: TextItem,
    texts: list[TextItem],
    *,
    port_slot: tuple[str, int],
    excluded_text_ids: set[str],
    used_endpoint_text_ids: set[str],
) -> TextItem | None:
    row, _ = port_slot
    port_x, port_y = _text_center(port)
    candidates = []
    for text in texts:
        if text.text_id in excluded_text_ids or text.text_id in used_endpoint_text_ids:
            continue
        if text.source_block_name:
            continue
        if text.layer.upper() == "MARK":
            continue
        if not _is_valid_external_endpoint(_clean_external_endpoint(text.normalized_text)):
            continue
        center_x, center_y = _text_center(text)
        if abs(center_x - port_x) > _KK_SLOT_ENDPOINT_X_TOL:
            continue
        y_gap = center_y - port_y if row == "top" else port_y - center_y
        if not (_KK_SLOT_ENDPOINT_Y_MIN_GAP <= y_gap <= _KK_SLOT_ENDPOINT_Y_MAX_GAP):
            continue
        candidates.append((text, y_gap))
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            abs(_text_center(item[0])[0] - port_x),
            item[1],
            item[0].text_id,
        ),
    )[0][0]


def _nearest_kk_slot_supporting_group(
    port: TextItem,
    endpoint: TextItem,
    line_groups: list[LineGroup],
) -> LineGroup | None:
    port_x, port_y = _text_center(port)
    endpoint_x, endpoint_y = _text_center(endpoint)
    min_y = min(port_y, endpoint_y) - _KK_HORIZONTAL_LINE_Y_TOL
    max_y = max(port_y, endpoint_y) + _KK_HORIZONTAL_LINE_Y_TOL
    candidates = []
    for group in line_groups:
        if group.orientation != "horizontal":
            continue
        group_y = (group.start_y + group.end_y) / 2.0
        if not (min_y <= group_y <= max_y):
            continue
        min_x = min(group.start_x, group.end_x)
        max_x = max(group.start_x, group.end_x)
        port_gap = 0.0 if min_x <= port_x <= max_x else min(abs(port_x - min_x), abs(port_x - max_x))
        endpoint_gap = (
            0.0
            if min_x <= endpoint_x <= max_x
            else min(abs(endpoint_x - min_x), abs(endpoint_x - max_x))
        )
        if max(port_gap, endpoint_gap) > _KK_HORIZONTAL_LINE_X_TOL:
            continue
        mid_y = (port_y + endpoint_y) / 2.0
        candidates.append((group, abs(group_y - mid_y), port_gap + endpoint_gap))
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (item[1], item[2], -item[0].length, item[0].line_group_id),
    )[0][0]


def _small_port_box_endpoint_side(port: TextItem, ports_by_number: dict[str, TextItem]) -> str:
    port_y_values = [_text_center(item)[1] for item in ports_by_number.values()]
    if max(port_y_values) - min(port_y_values) <= 4.0:
        return "top"
    midpoint_y = (max(port_y_values) + min(port_y_values)) / 2.0
    _, port_y = _text_center(port)
    return "top" if port_y >= midpoint_y else "bottom"


def _nearest_small_port_box_endpoint(
    port: TextItem,
    texts: list[TextItem],
    *,
    side: str,
    excluded_text_ids: set[str],
) -> TextItem | None:
    port_x, port_y = _text_center(port)
    candidates = []
    for text in texts:
        if text.text_id in excluded_text_ids:
            continue
        if text.source_block_name:
            continue
        if text.layer.upper() == "MARK":
            continue
        endpoint_value = _clean_small_port_external_endpoint(text.normalized_text)
        if not _is_valid_small_port_external_endpoint(endpoint_value):
            continue
        _, center_y = _text_center(text)
        anchor_x = text.insert_x
        if abs(anchor_x - port_x) > _SMALL_PORT_ENDPOINT_X_TOL:
            continue
        if side == "top":
            if not (_SMALL_PORT_ENDPOINT_Y_MIN_GAP <= center_y - port_y <= _SMALL_PORT_ENDPOINT_Y_MAX_GAP):
                continue
        else:
            if not (_SMALL_PORT_ENDPOINT_Y_MIN_GAP <= port_y - center_y <= _SMALL_PORT_ENDPOINT_Y_MAX_GAP):
                continue
        candidates.append(text)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            abs(item.insert_x - port_x),
            abs(_text_center(item)[1] - port_y),
            item.text_id,
        ),
    )[0]


def _nearest_small_port_support_group(
    port: TextItem,
    endpoint: TextItem,
    line_groups: list[LineGroup],
) -> LineGroup | None:
    port_x, port_y = _text_center(port)
    endpoint_x, endpoint_y = _text_center(endpoint)
    target_y = (port_y + endpoint_y) / 2.0
    min_x = min(port_x, endpoint_x) - _SMALL_PORT_SUPPORT_LINE_X_TOL
    max_x = max(port_x, endpoint_x) + _SMALL_PORT_SUPPORT_LINE_X_TOL
    candidates = []
    for group in line_groups:
        if group.orientation != "horizontal":
            continue
        group_y = (group.start_y + group.end_y) / 2.0
        if abs(group_y - target_y) > _SMALL_PORT_SUPPORT_LINE_Y_TOL:
            continue
        group_min_x = min(group.start_x, group.end_x)
        group_max_x = max(group.start_x, group.end_x)
        if group_max_x < min_x or group_min_x > max_x:
            continue
        candidates.append(group)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda group: (
            abs(((group.start_y + group.end_y) / 2.0) - target_y),
            abs(((group.start_x + group.end_x) / 2.0) - port_x),
            group.line_group_id,
        ),
    )[0]


def _strip_port_pairs(texts: list[TextItem]) -> list[tuple[TextItem, TextItem]]:
    top_ports = [
        text
        for text in texts
        if text.source_block_name == _STRIP_BLOCK_NAME and text.normalized_text == "1"
    ]
    bottom_ports = [
        text
        for text in texts
        if text.source_block_name == _STRIP_BLOCK_NAME and text.normalized_text == "2"
    ]
    pairs: list[tuple[TextItem, TextItem]] = []
    used_bottom_ids: set[str] = set()
    for top in sorted(top_ports, key=lambda item: (item.insert_x, item.insert_y, item.text_id)):
        candidates = [
            bottom
            for bottom in bottom_ports
            if bottom.text_id not in used_bottom_ids
            and abs(bottom.insert_x - top.insert_x) <= _PORT_X_TOL
            and _PORT_Y_MIN_GAP <= top.insert_y - bottom.insert_y <= _PORT_Y_MAX_GAP
        ]
        if not candidates:
            continue
        bottom = sorted(candidates, key=lambda item: (abs(item.insert_x - top.insert_x), abs(top.insert_y - item.insert_y)))[0]
        used_bottom_ids.add(bottom.text_id)
        pairs.append((top, bottom))
    return pairs


def _nearest_component_body(port_top: TextItem, texts: list[TextItem]) -> TextItem | None:
    candidates = [
        text
        for text in texts
        if not text.source_block_name
        and _COMPONENT_BODY_PATTERN.fullmatch(text.normalized_text or "")
        and abs(text.insert_x - port_top.insert_x) <= _BODY_X_TOL
        and _BODY_Y_MIN_GAP <= text.insert_y - port_top.insert_y <= _BODY_Y_MAX_GAP
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (abs(item.insert_x - port_top.insert_x), item.insert_y, item.text_id))[0]


def _nearest_strip_external_endpoints(
    port: TextItem,
    texts: list[TextItem],
    *,
    side: str,
) -> tuple[TextItem, list[str]] | None:
    candidates = []
    for text in texts:
        if text.source_block_name:
            continue
        if text.layer.upper() == "MARK":
            continue
        endpoint_values = _strip_external_endpoint_values(text.normalized_text)
        if not endpoint_values:
            continue
        if abs(text.insert_x - port.insert_x) > _ENDPOINT_X_TOL:
            continue
        if side == "top":
            if not (_TOP_ENDPOINT_Y_MIN_GAP <= text.insert_y - port.insert_y <= _TOP_ENDPOINT_Y_MAX_GAP):
                continue
        else:
            if not (_BOTTOM_ENDPOINT_Y_MIN_GAP <= port.insert_y - text.insert_y <= _BOTTOM_ENDPOINT_Y_MAX_GAP):
                continue
        is_split_candidate = "," in _clean_external_endpoint(text.normalized_text)
        candidates.append((text, endpoint_values, is_split_candidate))
    if not candidates:
        return None
    best_text, best_values, _ = sorted(
        candidates,
        key=lambda item: (
            item[2],
            abs(item[0].insert_x - port.insert_x),
            abs(item[0].insert_y - port.insert_y),
            item[0].text_id,
        ),
    )[0]
    return best_text, best_values


def _nearest_strip_endpoint_bridge_endpoint(
    port: TextItem,
    texts: list[TextItem],
    *,
    side: str,
) -> TextItem | None:
    candidates = []
    for text in texts:
        if text.source_block_name:
            continue
        if text.layer.upper() == "MARK":
            continue
        value = _clean_external_endpoint(text.normalized_text)
        if side == "top":
            if _STRIP_ENDPOINT_BRIDGE_TOP_PATTERN.fullmatch(value) is None:
                continue
        elif _STRIP_ENDPOINT_BRIDGE_BOTTOM_PATTERN.fullmatch(value) is None:
            continue
        if abs(text.insert_x - port.insert_x) > _ENDPOINT_X_TOL:
            continue
        if side == "top":
            if not (_TOP_ENDPOINT_Y_MIN_GAP <= text.insert_y - port.insert_y <= _TOP_ENDPOINT_Y_MAX_GAP):
                continue
        else:
            if not (_BOTTOM_ENDPOINT_Y_MIN_GAP <= port.insert_y - text.insert_y <= _BOTTOM_ENDPOINT_Y_MAX_GAP):
                continue
        candidates.append(text)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            abs(item.insert_x - port.insert_x),
            abs(item.insert_y - port.insert_y),
            item.text_id,
        ),
    )[0]


def _is_valid_strip_endpoint_bridge(top_value: str, bottom_value: str) -> bool:
    top_match = _STRIP_ENDPOINT_BRIDGE_TOP_PATTERN.fullmatch(top_value)
    bottom_match = _STRIP_ENDPOINT_BRIDGE_BOTTOM_PATTERN.fullmatch(bottom_value)
    if top_match is None or bottom_match is None:
        return False
    return top_match.group("prefix").lower() == bottom_match.group("prefix").lower()


def _strip_external_endpoint_values(value: str | None) -> list[str]:
    cleaned = _clean_external_endpoint(value)
    if not cleaned:
        return []
    if "," not in cleaned:
        return [cleaned] if _is_valid_external_endpoint(cleaned) else []
    return [
        endpoint_value
        for endpoint_value in (_clean_external_endpoint(piece) for piece in cleaned.split(","))
        if _is_valid_external_endpoint(endpoint_value)
    ]


def _nearest_supporting_vertical_group(
    port_top: TextItem,
    port_bottom: TextItem,
    line_groups: list[LineGroup],
) -> LineGroup | None:
    x_mid = (port_top.insert_x + port_bottom.insert_x) / 2.0
    candidates = []
    for group in line_groups:
        if group.orientation != "vertical":
            continue
        group_x = (group.start_x + group.end_x) / 2.0
        if abs(group_x - x_mid) > _VERTICAL_LINE_X_TOL:
            continue
        min_y = min(group.start_y, group.end_y)
        max_y = max(group.start_y, group.end_y)
        if min_y > port_bottom.insert_y + 2.0 or max_y < port_top.insert_y - 2.0:
            continue
        candidates.append(group)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda group: (abs(((group.start_x + group.end_x) / 2.0) - x_mid), -group.length, group.line_group_id),
    )[0]


def _clean_external_endpoint(value: str | None) -> str:
    return str(value or "").strip().lstrip("&").strip()


def _clean_small_port_external_endpoint(value: str | None) -> str:
    return str(value or "").strip().strip("&").strip()


def _is_valid_external_endpoint(value: str | None) -> bool:
    cleaned = _clean_external_endpoint(value)
    if not cleaned or "," in cleaned:
        return False
    if len(cleaned) <= 1 or cleaned.isdigit():
        return False
    return _EXTERNAL_ENDPOINT_PATTERN.fullmatch(cleaned) is not None


def _is_valid_small_port_external_endpoint(value: str | None) -> bool:
    cleaned = _clean_small_port_external_endpoint(value)
    if not cleaned or "," in cleaned:
        return False
    if len(cleaned) <= 1 or cleaned.isdigit():
        return False
    return _SMALL_PORT_EXTERNAL_ENDPOINT_PATTERN.fullmatch(cleaned) is not None


def _text_center(text: TextItem) -> tuple[float, float]:
    return ((text.bbox_min_x + text.bbox_max_x) / 2.0, (text.bbox_min_y + text.bbox_max_y) / 2.0)


def _component_bbox_from_items(items: list[TextItem]) -> list[float]:
    return [
        min(item.bbox_min_x for item in items),
        min(item.bbox_min_y for item in items),
        max(item.bbox_max_x for item in items),
        max(item.bbox_max_y for item in items),
    ]


def _build_kk_multi_port_pair(
    *,
    page: SheetRecord,
    block: BlockRecord,
    body: TextItem,
    port: TextItem,
    endpoint: TextItem,
    endpoint_value: str,
    support_group: LineGroup,
    pair_ids: IdFactory,
    logical_endpoint: str,
) -> Pair:
    port_x, port_y = _text_center(port)
    endpoint_x, endpoint_y = _text_center(endpoint)
    body_x, body_y = _text_center(body)
    evidence = {
        "source": "component_mapping",
        "pair_kind": "component_mapping",
        "submode": "kk_multi_port_component",
        "component_submode": "kk_multi_port_component",
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "component_body": body.normalized_text,
        "component_body_text_id": body.text_id,
        "component_body_coord": [body_x, body_y],
        "component_port": port.normalized_text,
        "component_port_text_id": port.text_id,
        "component_port_coord": [port_x, port_y],
        "component_block_id": block.block_id,
        "component_block_name": block.name,
        "component_block_coord": [block.insert_x, block.insert_y],
        "external_endpoint": endpoint_value,
        "external_endpoint_raw": endpoint.normalized_text,
        "external_endpoint_text_id": endpoint.text_id,
        "external_endpoint_coord": [endpoint_x, endpoint_y],
        "logical_endpoint": logical_endpoint,
        "line_group_id": support_group.line_group_id,
        "supporting_line_ids": support_group.member_line_ids,
        "line_orientation": "kk_multi_port_horizontal",
        "left_side_label": "component_port",
        "right_side_label": "external_endpoint",
        "score_breakdown": {
            "left_score": 1.0,
            "right_score": 1.0,
            "wire_score": 1.0,
            "ambiguity_gap": None,
        },
    }
    return Pair(
        pair_id=pair_ids.next(),
        line_group_id=support_group.line_group_id,
        sheet_id=page.sheet_id,
        file_id=page.file_id,
        selected_pair_candidate_id=None,
        left_value=logical_endpoint,
        right_value=endpoint_value,
        confidence=_PAIR_CONFIDENCE,
        status="pass",
        rationale="KK multi-port component mapping: component body plus block port associated with horizontal endpoint.",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence=evidence,
        left_text_id=port.text_id,
        right_text_id=endpoint.text_id,
        left_coord_x=port_x,
        left_coord_y=port_y,
        right_coord_x=endpoint_x,
        right_coord_y=endpoint_y,
        pair_key=f"{logical_endpoint}->{endpoint_value}",
        left_score=1.0,
        right_score=1.0,
        wire_score=1.0,
        ambiguity_gap=None,
        pair_kind="component_mapping",
    )


def _build_small_port_box_pair(
    *,
    page: SheetRecord,
    block: BlockRecord,
    body: TextItem,
    port: TextItem,
    endpoint: TextItem,
    endpoint_value: str,
    endpoint_side: str,
    support_group: LineGroup | None,
    pair_ids: IdFactory,
    logical_endpoint: str,
    instance_items: list[TextItem],
) -> Pair:
    port_x, port_y = _text_center(port)
    endpoint_x, endpoint_y = _text_center(endpoint)
    body_x, body_y = _text_center(body)
    evidence = {
        "source": "component_mapping",
        "pair_kind": "component_mapping",
        "submode": "small_port_box_component",
        "component_submode": "small_port_box_component",
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "component_body": body.normalized_text,
        "component_body_text_id": body.text_id,
        "component_body_coord": [body_x, body_y],
        "component_port": port.normalized_text,
        "component_port_text_id": port.text_id,
        "component_port_coord": [port_x, port_y],
        "component_block_id": block.block_id,
        "component_block_name": block.name,
        "component_block_coord": [block.insert_x, block.insert_y],
        "component_instance_bbox": _component_bbox_from_items(instance_items),
        "external_endpoint": endpoint_value,
        "external_endpoint_raw": endpoint.normalized_text,
        "external_endpoint_text_id": endpoint.text_id,
        "external_endpoint_coord": [endpoint_x, endpoint_y],
        "logical_endpoint": logical_endpoint,
        "endpoint_side": endpoint_side,
        "line_group_id": support_group.line_group_id if support_group else None,
        "supporting_line_ids": support_group.member_line_ids if support_group else [],
        "line_orientation": "small_port_box",
        "left_side_label": "component_port",
        "right_side_label": "external_endpoint",
        "score_breakdown": {
            "left_score": 1.0,
            "right_score": 1.0,
            "wire_score": 1.0,
            "ambiguity_gap": None,
        },
    }
    return Pair(
        pair_id=pair_ids.next(),
        line_group_id=support_group.line_group_id if support_group else None,
        sheet_id=page.sheet_id,
        file_id=page.file_id,
        selected_pair_candidate_id=None,
        left_value=logical_endpoint,
        right_value=endpoint_value,
        confidence=_PAIR_CONFIDENCE,
        status="pass",
        rationale="Small port-box component mapping: component body plus local port associated with adjacent external endpoint.",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence=evidence,
        left_text_id=port.text_id,
        right_text_id=endpoint.text_id,
        left_coord_x=port_x,
        left_coord_y=port_y,
        right_coord_x=endpoint_x,
        right_coord_y=endpoint_y,
        pair_key=f"{logical_endpoint}->{endpoint_value}",
        left_score=1.0,
        right_score=1.0,
        wire_score=1.0,
        ambiguity_gap=None,
        pair_kind="component_mapping",
    )


def _build_strip_endpoint_bridge_pair(
    *,
    page: SheetRecord,
    port_top: TextItem,
    port_bottom: TextItem,
    top_endpoint: TextItem,
    bottom_endpoint: TextItem,
    top_value: str,
    bottom_value: str,
    support_group: LineGroup,
    pair_ids: IdFactory,
) -> Pair:
    evidence = {
        "source": "component_mapping",
        "pair_kind": "component_mapping",
        "component_submode": "strip_two_port_endpoint_bridge",
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "component_block_name": port_top.source_block_name,
        "top_port": port_top.normalized_text,
        "top_port_text_id": port_top.text_id,
        "top_port_coord": [port_top.insert_x, port_top.insert_y],
        "bottom_port": port_bottom.normalized_text,
        "bottom_port_text_id": port_bottom.text_id,
        "bottom_port_coord": [port_bottom.insert_x, port_bottom.insert_y],
        "top_endpoint": top_value,
        "top_endpoint_raw": top_endpoint.normalized_text,
        "top_endpoint_text_id": top_endpoint.text_id,
        "top_endpoint_coord": [top_endpoint.insert_x, top_endpoint.insert_y],
        "bottom_endpoint": bottom_value,
        "bottom_endpoint_raw": bottom_endpoint.normalized_text,
        "bottom_endpoint_text_id": bottom_endpoint.text_id,
        "bottom_endpoint_coord": [bottom_endpoint.insert_x, bottom_endpoint.insert_y],
        "logical_endpoint": top_value,
        "external_endpoint": bottom_value,
        "line_group_id": support_group.line_group_id,
        "supporting_line_ids": support_group.member_line_ids,
        "line_orientation": "strip_two_port_endpoint_bridge_vertical",
        "left_side_label": "top_endpoint",
        "right_side_label": "bottom_endpoint",
        "score_breakdown": {
            "left_score": 1.0,
            "right_score": 1.0,
            "wire_score": 1.0,
            "ambiguity_gap": None,
        },
    }
    return Pair(
        pair_id=pair_ids.next(),
        line_group_id=support_group.line_group_id,
        sheet_id=page.sheet_id,
        file_id=page.file_id,
        selected_pair_candidate_id=None,
        left_value=top_value,
        right_value=bottom_value,
        confidence=_PAIR_CONFIDENCE,
        status="pass",
        rationale="Strip two-port endpoint bridge: top ZK endpoint associated with bottom n endpoint.",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence=evidence,
        left_text_id=top_endpoint.text_id,
        right_text_id=bottom_endpoint.text_id,
        left_coord_x=top_endpoint.insert_x,
        left_coord_y=top_endpoint.insert_y,
        right_coord_x=bottom_endpoint.insert_x,
        right_coord_y=bottom_endpoint.insert_y,
        pair_key=f"{top_value}->{bottom_value}",
        left_score=1.0,
        right_score=1.0,
        wire_score=1.0,
        ambiguity_gap=None,
        pair_kind="component_mapping",
    )


def _build_strip_two_port_pair(
    *,
    page: SheetRecord,
    body: TextItem,
    port: TextItem,
    endpoint: TextItem,
    endpoint_value: str,
    side_label: str,
    support_group: LineGroup,
    pair_ids: IdFactory,
    logical_endpoint: str,
) -> Pair:
    evidence = {
        "source": "component_mapping",
        "pair_kind": "component_mapping",
        "component_submode": "strip_two_port_component",
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "component_body": body.normalized_text,
        "component_body_text_id": body.text_id,
        "component_body_coord": [body.insert_x, body.insert_y],
        "component_port": port.normalized_text,
        "component_port_text_id": port.text_id,
        "component_port_coord": [port.insert_x, port.insert_y],
        "component_block_name": port.source_block_name,
        "external_endpoint": endpoint_value,
        "external_endpoint_raw": endpoint.normalized_text,
        "external_endpoint_split": endpoint_value,
        "external_endpoint_text_id": endpoint.text_id,
        "external_endpoint_coord": [endpoint.insert_x, endpoint.insert_y],
        "logical_endpoint": logical_endpoint,
        "endpoint_side": side_label,
        "line_group_id": support_group.line_group_id,
        "supporting_line_ids": support_group.member_line_ids,
        "line_orientation": "strip_two_port_vertical",
        "left_side_label": "component_port",
        "right_side_label": "external_endpoint",
        "score_breakdown": {
            "left_score": 1.0,
            "right_score": 1.0,
            "wire_score": 1.0,
            "ambiguity_gap": None,
        },
    }
    return Pair(
        pair_id=pair_ids.next(),
        line_group_id=support_group.line_group_id,
        sheet_id=page.sheet_id,
        file_id=page.file_id,
        selected_pair_candidate_id=None,
        left_value=logical_endpoint,
        right_value=endpoint_value,
        confidence=_PAIR_CONFIDENCE,
        status="pass",
        rationale="Strip two-port component mapping: component body plus block port associated with external endpoint.",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence=evidence,
        left_text_id=port.text_id,
        right_text_id=endpoint.text_id,
        left_coord_x=port.insert_x,
        left_coord_y=port.insert_y,
        right_coord_x=endpoint.insert_x,
        right_coord_y=endpoint.insert_y,
        pair_key=f"{logical_endpoint}->{endpoint_value}",
        left_score=1.0,
        right_score=1.0,
        wire_score=1.0,
        ambiguity_gap=None,
        pair_kind="component_mapping",
    )
