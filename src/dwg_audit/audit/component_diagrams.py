from __future__ import annotations

import re
from math import isfinite

from dataclasses import dataclass

from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_STRIP_BLOCK_BASENAME = "FJL-25-2A"
_KK_MULTI_PORT_BLOCK_PORTS = {
    "KK2P": 4,
    "KK3P": 6,
}
_KK_MULTI_PORT_BLOCK_PATTERN = re.compile(
    r"^(?P<base>KK[23]P)(?:\+OF11-12)?$",
    re.IGNORECASE,
)
_KK_IGNORED_AUXILIARY_PORTS = {"11", "12", "14"}
_SMALL_PORT_BOX_BLOCK_PORTS = {
    "KK1P": {"1", "2"},
    "KK2P": {"1", "2", "3", "4"},
    "JR-01": {"1", "2"},
}
# Accept classic 1KLP9 / 1-4CLP2 and cabinet module tags like 1C3LP4 / 5C1LP2.
_COMPONENT_BODY_PATTERN = re.compile(
    r"^\d+(?:-\d+)?(?:(?:KLP|CLP|ZLP)\d+|[A-Za-z]\d+LP\d+)$",
    re.IGNORECASE,
)
_KK_COMPONENT_BODY_PATTERN = re.compile(
    r"^(?:\d+(?:-\d+)?[A-Za-z]{1,5}\d*|[A-Za-z]{2,8}\d+)$",
    re.IGNORECASE,
)
_SMALL_PORT_BOX_BODY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z']{0,4}$", re.IGNORECASE)
_STRIP_ENDPOINT_BRIDGE_TOP_PATTERN = re.compile(r"^(?P<prefix>\d+-\d+)ZK-(?P<port>\d+)$", re.IGNORECASE)
_STRIP_ENDPOINT_BRIDGE_BOTTOM_PATTERN = re.compile(r"^(?P<prefix>\d+-\d+)n(?P<number>\d{3,})$", re.IGNORECASE)
_EXTERNAL_ENDPOINT_PATTERN = re.compile(
    r"^(?:"
    r"\d+(?:-\d+)?[A-Za-z]\d+[A-Za-z]{1,4}\d+(?:-\d+)?"
    r"|\d+(?:-\d+)?[A-Za-z]{1,4}\d+(?:-\d+)?"
    r"|[A-Za-z]{1,4}\d+(?:-\d+)?"
    r")$",
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
            if len(ports_by_number) == port_count:
                consumed_group_ids.update(
                    _kk_ignored_auxiliary_group_ids(
                        block,
                        sheet_texts,
                        sheet_blocks,
                        sheet_groups,
                    )
                )
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


_TERMINAL_STRIP_PIN_PATTERN = re.compile(r"^\d{1,3}$")
_TERMINAL_STRIP_INSTANCE_LABEL_PATTERN = re.compile(r"^[A-Za-z]{1,6}\d*$")
_TERMINAL_STRIP_DECORATION_CLEAN_PATTERN = re.compile(r"^[&*]\s*|\s*[&*]$")
_TERMINAL_STRIP_MIN_PIN_ROWS = 8
_TERMINAL_STRIP_PIN_COLUMN_X_TOL = 2.5
_TERMINAL_STRIP_PIN_COLUMN_SPLIT_Y_GAP = 12.0
_TERMINAL_STRIP_PITCH_MIN = 2.5
_TERMINAL_STRIP_PITCH_MAX = 8.0
_TERMINAL_STRIP_PITCH_UNIFORM_TOL = 0.2
_TERMINAL_STRIP_COLUMN_GAP_MIN = 6.0
_TERMINAL_STRIP_COLUMN_GAP_MAX = 14.0
_TERMINAL_STRIP_ROW_ALIGN_TOL = 1.0
_TERMINAL_STRIP_INSTANCE_LABEL_MIN_PITCHES = 0.5
_TERMINAL_STRIP_INSTANCE_LABEL_MAX_PITCHES = 4.0
_TERMINAL_STRIP_FLANK_X_TOL = 4.0
_TERMINAL_STRIP_FLANK_COVER_TOL = 1.0
_TERMINAL_STRIP_FLANK_MAX_PITCHES = 1.0
_TERMINAL_STRIP_LABEL_ROW_MAX_PITCHES = 0.2
_TERMINAL_STRIP_LABEL_X_REACH = 25.0
_TERMINAL_STRIP_PIN_RADIUS = 1.0


def extract_terminal_strip_lattice_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    line_groups: list[LineGroup],
    *,
    lines: list[LineEntity] | None = None,
    consumption_evidence: dict[str, dict[str, object]] | None = None,
    pair_id_factory: IdFactory | None = None,
) -> tuple[list[Pair], set[str]]:
    """Recover terminal-strip row mappings on component diagrams.

    Detection is structural: a two-column numeric pin lattice with uniform row
    pitch, an instance label above the lattice and flanking vertical border
    groups. Pin and border geometry must share an INSERT owner. No particular
    block name is required, so renamed blocks retain the same recognition.
    """

    pair_ids = pair_id_factory or IdFactory("PCM")
    texts_by_sheet: dict[tuple[str, str], list[TextItem]] = {}
    for text in texts:
        texts_by_sheet.setdefault((text.sheet_id, text.file_id), []).append(text)
    groups_by_sheet: dict[tuple[str, str], list[LineGroup]] = {}
    for group in line_groups:
        groups_by_sheet.setdefault((group.sheet_id, group.file_id), []).append(group)
    lines_by_sheet: dict[tuple[str, str], list[LineEntity]] = {}
    for line in lines or []:
        lines_by_sheet.setdefault((line.sheet_id, line.file_id), []).append(line)

    pairs: list[Pair] = []
    consumed_group_ids: set[str] = set()
    for page in pages:
        if not _supports_strip_two_port_component(page):
            continue
        scope = (page.sheet_id, page.file_id)
        sheet_texts = texts_by_sheet.get(scope, [])
        sheet_groups = groups_by_sheet.get(scope, [])
        strips = _detect_terminal_strips(sheet_texts, sheet_groups, lines=lines_by_sheet.get(scope, []))
        for strip in strips:
            consumed_group_ids.update(group.line_group_id for group in strip.flank_groups)
            if consumption_evidence is not None:
                border_evidence = {
                    "source": "terminal_strip_lattice",
                    "sheet_id": page.sheet_id,
                    "file_id": page.file_id,
                    "insert_handle": strip.insert_handle,
                    "block_names": sorted(strip.block_names),
                    "instance_text_id": strip.instance_label.text_id if strip.instance_label else None,
                    "pin_row_text_ids": [[left.text_id, right.text_id] for left, right in strip.pin_rows],
                    "pitch": strip.pitch,
                    "flank_group_ids": [group.line_group_id for group in strip.flank_groups],
                    "flank_line_ids": [line_id for group in strip.flank_groups for line_id in group.member_line_ids],
                    "bbox": [strip.flank_groups[0].start_x, min(strip.flank_groups[0].start_y, strip.flank_groups[0].end_y),
                             strip.flank_groups[1].start_x, max(strip.flank_groups[0].start_y, strip.flank_groups[0].end_y)],
                }
                for group in strip.flank_groups:
                    consumption_evidence[group.line_group_id] = border_evidence
            for row_index, left_label, right_label in strip.paired_row_labels:
                left_value = _clean_terminal_strip_label_value(left_label.normalized_text)
                right_value = _clean_terminal_strip_label_value(right_label.normalized_text)
                if not _is_valid_external_endpoint(left_value):
                    continue
                if not _is_valid_external_endpoint(right_value):
                    continue
                pairs.append(
                    _build_terminal_strip_pair(
                        page=page,
                        strip=strip,
                        row_index=row_index,
                        left_label=left_label,
                        right_label=right_label,
                        left_value=left_value,
                        right_value=right_value,
                        pair_ids=pair_ids,
                    )
                )
    return pairs, consumed_group_ids


@dataclass(slots=True)
class _TerminalStrip:
    instance_label: TextItem | None
    block_names: set[str]
    insert_handle: str
    pin_rows: list[tuple[TextItem, TextItem]]
    left_edge_x: float
    right_edge_x: float
    top_y: float
    bottom_y: float
    pitch: float
    flank_groups: list[LineGroup]
    paired_row_labels: list[tuple[int, TextItem, TextItem]]


def _detect_terminal_strips(
    sheet_texts: list[TextItem],
    sheet_groups: list[LineGroup],
    *,
    lines: list[LineEntity] | None = None,
) -> list[_TerminalStrip]:
    line_by_id = {line.line_id: line for line in lines or []}
    if len(line_by_id) != len(lines or []):
        return []
    sides = _terminal_strip_pin_sides(sheet_texts)
    strips: list[_TerminalStrip] = []
    used_side_ids: set[int] = set()
    for left_index, left_side in enumerate(sides):
        if left_index in used_side_ids:
            continue
        right_index = _matching_terminal_strip_side(sides, left_side, used_side_ids, left_index)
        if right_index is None:
            continue
        right_side = sides[right_index]
        insert_handle = _terminal_strip_pin_owner([*left_side, *right_side])
        if insert_handle is None:
            continue
        left_edge_x = min(text.bbox_min_x for text in left_side) - _TERMINAL_STRIP_PIN_RADIUS
        right_edge_x = max(text.bbox_max_x for text in right_side) + _TERMINAL_STRIP_PIN_RADIUS
        top_y = max(max(text.insert_y for text in left_side), max(text.insert_y for text in right_side))
        bottom_y = min(min(text.insert_y for text in left_side), min(text.insert_y for text in right_side))
        pitch = _terminal_strip_row_pitch([text.insert_y for text in left_side])
        instance_label = _terminal_strip_instance_label(sheet_texts, left_side, right_side, top_y, pitch)
        if instance_label is None:
            continue
        flank_groups = _terminal_strip_flank_groups(
            sheet_groups,
            left_edge_x=left_edge_x,
            right_edge_x=right_edge_x,
            top_y=top_y,
            bottom_y=bottom_y,
            pitch=pitch,
            insert_handle=insert_handle,
            source_block_name=left_side[0].source_block_name,
            line_by_id=line_by_id,
        )
        left_frame_x = [
            group.start_x
            for group in flank_groups
            if group.start_x < (left_edge_x + right_edge_x) / 2
        ]
        right_frame_x = [
            group.start_x
            for group in flank_groups
            if group.start_x >= (left_edge_x + right_edge_x) / 2
        ]
        if len(left_frame_x) != 1 or len(right_frame_x) != 1:
            continue
        pin_rows = _terminal_strip_pin_rows(left_side, right_side)
        paired_row_labels = _terminal_strip_paired_row_labels(
            sheet_texts,
            left_frame_x=max(left_frame_x),
            right_frame_x=min(right_frame_x),
            top_y=top_y,
            bottom_y=bottom_y,
            pitch=pitch,
            instance_label=instance_label,
            pin_rows=pin_rows,
        )
        block_names = {
            text.source_block_name
            for text in [*left_side, *right_side]
            if text.source_block_name
        }
        used_side_ids.add(right_index)
        strips.append(
            _TerminalStrip(
                instance_label=instance_label,
                block_names=block_names,
                insert_handle=insert_handle,
                pin_rows=pin_rows,
                left_edge_x=left_edge_x,
                right_edge_x=right_edge_x,
                top_y=top_y,
                bottom_y=bottom_y,
                pitch=pitch,
                flank_groups=flank_groups,
                paired_row_labels=paired_row_labels,
            )
        )
        used_side_ids.add(left_index)
    return strips


def _terminal_strip_pin_sides(texts: list[TextItem]) -> list[list[TextItem]]:
    pin_texts = [
        text
        for text in texts
        if text.source_block_name
        and _terminal_strip_insert_handle(text.handle)
        and _terminal_strip_text_geometry_valid(text)
        and text.is_numeric_candidate
        and _TERMINAL_STRIP_PIN_PATTERN.fullmatch(text.normalized_text or "")
    ]
    column_order = {
        text.text_id: index
        for index, column in enumerate(_cluster_texts_by_x(pin_texts, _TERMINAL_STRIP_PIN_COLUMN_X_TOL))
        for text in column
    }
    by_owner: dict[tuple[str | None, str | None], list[TextItem]] = {}
    for text in pin_texts:
        by_owner.setdefault((_terminal_strip_insert_handle(text.handle), text.source_block_name), []).append(text)
    columns = [column for owned in by_owner.values()
               for column in _cluster_texts_by_x(owned, _TERMINAL_STRIP_PIN_COLUMN_X_TOL)]
    sides: list[list[TextItem]] = []
    for column in columns:
        segments = _split_column_into_row_segments(column)
        for segment in segments:
            if len(segment) < _TERMINAL_STRIP_MIN_PIN_ROWS:
                continue
            pitch = _terminal_strip_row_pitch([text.insert_y for text in segment])
            if not _TERMINAL_STRIP_PITCH_MIN <= pitch <= _TERMINAL_STRIP_PITCH_MAX:
                continue
            if not _terminal_strip_pitch_uniform([text.insert_y for text in segment], pitch):
                continue
            sides.append(sorted(segment, key=lambda text: (-text.insert_y, text.text_id)))
    # Keep tolerance-cluster ordering stable for Pair IDs, without merging owners.
    return sorted(sides, key=lambda side: (column_order[side[0].text_id], -side[0].insert_y, side[0].text_id))


def _cluster_texts_by_x(texts: list[TextItem], tolerance: float) -> list[list[TextItem]]:
    ordered = sorted(texts, key=lambda text: (text.insert_x, text.text_id))
    clusters: list[list[TextItem]] = []
    for text in ordered:
        if clusters and abs(text.insert_x - clusters[-1][-1].insert_x) <= tolerance:
            clusters[-1].append(text)
        else:
            clusters.append([text])
    return clusters


def _split_column_into_row_segments(column: list[TextItem]) -> list[list[TextItem]]:
    ordered = sorted(column, key=lambda text: (-text.insert_y, text.text_id))
    segments: list[list[TextItem]] = [[ordered[0]]]
    for text in ordered[1:]:
        gap = segments[-1][-1].insert_y - text.insert_y
        if gap > _TERMINAL_STRIP_PIN_COLUMN_SPLIT_Y_GAP:
            segments.append([text])
        else:
            segments[-1].append(text)
    return segments


def _terminal_strip_row_pitch(ys: list[float]) -> float:
    ordered = sorted(ys, reverse=True)
    diffs = [above - below for above, below in zip(ordered, ordered[1:])]
    if not diffs:
        return 0.0
    return sorted(diffs)[len(diffs) // 2]


def _terminal_strip_pitch_uniform(ys: list[float], pitch: float) -> bool:
    ordered = sorted(ys, reverse=True)
    diffs = [above - below for above, below in zip(ordered, ordered[1:])]
    return all(abs(diff - pitch) <= _TERMINAL_STRIP_PITCH_UNIFORM_TOL * pitch for diff in diffs)


def _matching_terminal_strip_side(
    sides: list[list[TextItem]],
    left_side: list[TextItem],
    used_side_ids: set[int],
    left_index: int,
) -> int | None:
    left_mean_x = sum(text.insert_x for text in left_side) / len(left_side)
    best_index: int | None = None
    best_gap = float("inf")
    owner = _terminal_strip_pin_owner(left_side)
    if owner is None:
        return None
    for index, side in enumerate(sides):
        if index == left_index or index in used_side_ids:
            continue
        gap = sum(text.insert_x for text in side) / len(side) - left_mean_x
        if not _TERMINAL_STRIP_COLUMN_GAP_MIN <= gap <= _TERMINAL_STRIP_COLUMN_GAP_MAX:
            continue
        if len(side) != len(left_side):
            continue
        if _terminal_strip_pin_owner([*left_side, *side]) != owner:
            continue
        if not _terminal_strip_rows_aligned(left_side, side):
            continue
        if gap < best_gap:
            best_gap = gap
            best_index = index
    return best_index


def _terminal_strip_rows_aligned(left_side: list[TextItem], right_side: list[TextItem]) -> bool:
    left_rows = sorted((text.insert_y for text in left_side), reverse=True)
    right_rows = sorted((text.insert_y for text in right_side), reverse=True)
    return all(
        abs(left_y - right_y) <= _TERMINAL_STRIP_ROW_ALIGN_TOL
        for left_y, right_y in zip(left_rows, right_rows)
    )


def _terminal_strip_pin_rows(left_side: list[TextItem], right_side: list[TextItem]) -> list[tuple[TextItem, TextItem]]:
    rights_by_row = [
        text
        for text in sorted(right_side, key=lambda item: -item.insert_y)
    ]
    lefts_by_row = sorted(left_side, key=lambda item: -item.insert_y)
    rows: list[tuple[TextItem, TextItem]] = []
    for left, right in zip(lefts_by_row, rights_by_row):
        if abs(left.insert_y - right.insert_y) <= _TERMINAL_STRIP_ROW_ALIGN_TOL:
            rows.append((left, right))
    return rows


def _terminal_strip_instance_label(
    texts: list[TextItem],
    left_side: list[TextItem],
    right_side: list[TextItem],
    top_y: float,
    pitch: float,
) -> TextItem | None:
    min_x = min(text.insert_x for text in left_side)
    max_x = max(text.insert_x for text in right_side)
    candidates = []
    for text in texts:
        if not _terminal_strip_text_geometry_valid(text):
            continue
        if text.is_numeric_candidate:
            continue
        if not _TERMINAL_STRIP_INSTANCE_LABEL_PATTERN.fullmatch(text.normalized_text or ""):
            continue
        if not min_x - 3.0 <= text.insert_x <= max_x + 3.0:
            continue
        gap = text.insert_y - top_y
        if not _TERMINAL_STRIP_INSTANCE_LABEL_MIN_PITCHES * pitch <= gap <= _TERMINAL_STRIP_INSTANCE_LABEL_MAX_PITCHES * pitch:
            continue
        candidates.append(text)
    if not candidates:
        return None
    return sorted(candidates, key=lambda text: (abs(text.insert_y - top_y), text.text_id))[0]


def _terminal_strip_insert_handle(handle: str) -> str | None:
    parent, separator, child = str(handle or "").rpartition(":VIRTUAL:")
    return parent if separator and parent and child.split(":")[0].isdigit() else None


def _terminal_strip_pin_owner(pins: list[TextItem]) -> str | None:
    owners = {(_terminal_strip_insert_handle(pin.handle), pin.source_block_name) for pin in pins}
    if len(owners) != 1:
        return None
    owner, block_name = next(iter(owners))
    return owner if owner and block_name else None


def _terminal_strip_text_geometry_valid(text: TextItem) -> bool:
    return (
        all(isfinite(value) for value in (text.insert_x, text.insert_y, text.bbox_min_x,
                                         text.bbox_min_y, text.bbox_max_x, text.bbox_max_y))
        and text.bbox_min_x <= text.bbox_max_x
        and text.bbox_min_y <= text.bbox_max_y
    )


def _terminal_strip_flank_members_match(
    group: LineGroup,
    line_by_id: dict[str, LineEntity],
    insert_handle: str,
    source_block_name: str | None,
) -> bool:
    if not group.member_line_ids or len(set(group.member_line_ids)) != len(group.member_line_ids):
        return False
    coords = (group.start_x, group.start_y, group.end_x, group.end_y)
    if not all(isfinite(value) for value in coords) or abs(group.start_x - group.end_x) > 1e-6:
        return False
    intervals = []
    layers = set()
    for line_id in group.member_line_ids:
        line = line_by_id.get(line_id)
        if line is None or (line.sheet_id, line.file_id) != (group.sheet_id, group.file_id):
            return False
        if _terminal_strip_insert_handle(line.handle) != insert_handle or line.source_block_name != source_block_name:
            return False
        if line.layer.upper() != "BORDER":
            return False
        layers.add(line.layer)
        coords = (line.start_x, line.start_y, line.end_x, line.end_y)
        if not all(isfinite(value) for value in coords):
            return False
        if max(abs(group.start_x - line.start_x), abs(group.start_x - line.end_x)) > 1e-6:
            return False
        bottom, top = sorted((line.start_y, line.end_y))
        if top - bottom <= 1e-6:
            return False
        intervals.append((bottom, top))
    if layers != set(group.layer_hints):
        return False
    intervals.sort()
    # A merged group is a border only if its physical members form one edge.
    if any(abs(lower[1] - upper[0]) > 1e-6 for lower, upper in zip(intervals, intervals[1:])):
        return False
    return (
        abs(intervals[0][0] - min(group.start_y, group.end_y)) <= 1e-6
        and abs(intervals[-1][1] - max(group.start_y, group.end_y)) <= 1e-6
    )


def _terminal_strip_flank_groups(
    sheet_groups: list[LineGroup],
    *,
    left_edge_x: float,
    right_edge_x: float,
    top_y: float,
    bottom_y: float,
    pitch: float,
    insert_handle: str,
    source_block_name: str | None,
    line_by_id: dict[str, LineEntity],
) -> list[LineGroup]:
    flanks: list[LineGroup] = []
    for group in sheet_groups:
        if group.orientation != "vertical":
            continue
        if not _terminal_strip_flank_members_match(group, line_by_id, insert_handle, source_block_name):
            continue
        if not (
            left_edge_x - _TERMINAL_STRIP_FLANK_X_TOL <= group.start_x <= left_edge_x + 1.0
            or right_edge_x - 1.0 <= group.start_x <= right_edge_x + _TERMINAL_STRIP_FLANK_X_TOL
        ):
            continue
        group_top = max(group.start_y, group.end_y)
        group_bottom = min(group.start_y, group.end_y)
        if group_bottom > bottom_y - _TERMINAL_STRIP_FLANK_COVER_TOL:
            continue
        if group_top < top_y + _TERMINAL_STRIP_FLANK_COVER_TOL:
            continue
        if max(group_top - top_y, bottom_y - group_bottom) > _TERMINAL_STRIP_FLANK_MAX_PITCHES * pitch:
            continue
        flanks.append(group)
    return sorted(flanks, key=lambda group: (group.start_x, group.line_group_id))


def _terminal_strip_paired_row_labels(
    sheet_texts: list[TextItem],
    *,
    left_frame_x: float,
    right_frame_x: float,
    top_y: float,
    bottom_y: float,
    pitch: float,
    instance_label: TextItem,
    pin_rows: list[tuple[TextItem, TextItem]],
) -> list[tuple[int, TextItem, TextItem]]:
    left_labels: dict[int, list[TextItem]] = {}
    right_labels: dict[int, list[TextItem]] = {}
    for text in sheet_texts:
        if text is instance_label:
            continue
        if not _terminal_strip_text_geometry_valid(text):
            continue
        if not (bottom_y - 0.75 * pitch <= text.insert_y <= top_y + 0.75 * pitch):
            continue
        center_x = (text.bbox_min_x + text.bbox_max_x) / 2
        # Grammar-gate before pairing so junk labels (e.g. sheet-grid letters)
        # cannot consume a valid partner label of a real row.
        if not _is_valid_external_endpoint(_clean_terminal_strip_label_value(text.normalized_text)):
            continue
        if left_frame_x - _TERMINAL_STRIP_LABEL_X_REACH <= center_x < left_frame_x:
            labels, pin_side = left_labels, 0
        elif right_frame_x < center_x <= right_frame_x + _TERMINAL_STRIP_LABEL_X_REACH:
            labels, pin_side = right_labels, 1
        else:
            continue
        matches = [index for index, pins in enumerate(pin_rows)
                   if abs(text.insert_y - pins[pin_side].insert_y) <= _TERMINAL_STRIP_LABEL_ROW_MAX_PITCHES * pitch]
        if len(matches) == 1:
            labels.setdefault(matches[0], []).append(text)
    # Both sides must have a unique physical label on the same pin row.
    return [(index, left_labels[index][0], right_labels[index][0]) for index in range(len(pin_rows))
            if len(left_labels.get(index, [])) == 1 and len(right_labels.get(index, [])) == 1]


def _clean_terminal_strip_label_value(value: str | None) -> str:
    cleaned = (value or "").strip()
    return _TERMINAL_STRIP_DECORATION_CLEAN_PATTERN.sub("", cleaned).strip()


def _build_terminal_strip_pair(
    *,
    page: SheetRecord,
    strip: _TerminalStrip,
    row_index: int,
    left_label: TextItem,
    right_label: TextItem,
    left_value: str,
    right_value: str,
    pair_ids: IdFactory,
) -> Pair:
    support_group = strip.flank_groups[0]
    instance_name = strip.instance_label.normalized_text if strip.instance_label else None
    left_pin, right_pin = strip.pin_rows[row_index]
    evidence = {
        "source": "component_mapping",
        "pair_kind": "component_mapping",
        "component_submode": "terminal_strip_lattice",
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "terminal_strip_instance": instance_name,
        "terminal_strip_instance_text_id": strip.instance_label.text_id if strip.instance_label else None,
        "terminal_strip_block_names": sorted(strip.block_names),
        "terminal_strip_insert_handle": strip.insert_handle,
        "terminal_strip_pin_row": row_index + 1,
        "terminal_strip_pitch": strip.pitch,
        "terminal_strip_left_pin": {"text_id": left_pin.text_id, "value": left_pin.normalized_text, "coord": [left_pin.insert_x, left_pin.insert_y], "handle": left_pin.handle},
        "terminal_strip_right_pin": {"text_id": right_pin.text_id, "value": right_pin.normalized_text, "coord": [right_pin.insert_x, right_pin.insert_y], "handle": right_pin.handle},
        "terminal_strip_flank_group_ids": [group.line_group_id for group in strip.flank_groups],
        "terminal_strip_flank_line_ids": [line_id for group in strip.flank_groups for line_id in group.member_line_ids],
        "terminal_strip_row_y": left_label.insert_y,
        "terminal_strip_pin_row_count": len(strip.pin_rows),
        "left_terminal_raw": left_label.normalized_text,
        "left_terminal": left_value,
        "left_terminal_text_id": left_label.text_id,
        "left_terminal_coord": [left_label.insert_x, left_label.insert_y],
        "right_terminal_raw": right_label.normalized_text,
        "right_terminal": right_value,
        "right_terminal_text_id": right_label.text_id,
        "right_terminal_coord": [right_label.insert_x, right_label.insert_y],
        "left_side_label": "circuit_wire",
        "right_side_label": "device_terminal",
        "line_group_id": support_group.line_group_id,
        "supporting_line_ids": support_group.member_line_ids,
        "line_orientation": "terminal_strip_lattice_row",
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
        left_value=left_value,
        right_value=right_value,
        confidence=_PAIR_CONFIDENCE,
        status="pass",
        rationale="Terminal-strip lattice row mapping: structural strip detection paired row labels.",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence=evidence,
        left_text_id=left_label.text_id,
        right_text_id=right_label.text_id,
        left_coord_x=left_label.insert_x,
        left_coord_y=left_label.insert_y,
        right_coord_x=right_label.insert_x,
        right_coord_y=right_label.insert_y,
        pair_key=f"{left_value}->{right_value}",
        left_score=1.0,
        right_score=1.0,
        wire_score=1.0,
        ambiguity_gap=None,
        pair_kind="component_mapping",
    )


def _supports_strip_two_port_component(page: SheetRecord) -> bool:
    return (
        page.sheet_category == "元件接线图"
        and page.page_subtype == "horizontal_component"
        and page.route_target == "ComponentDiagramExtractor"
    )


def _kk_multi_port_count(block: BlockRecord) -> int | None:
    match = _KK_MULTI_PORT_BLOCK_PATTERN.fullmatch((block.name or "").strip())
    if match is None:
        return None
    return _KK_MULTI_PORT_BLOCK_PORTS.get(match.group("base").upper())


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
        if text.layer.upper() != "MARK":
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


def _kk_ignored_auxiliary_group_ids(
    block: BlockRecord,
    texts: list[TextItem],
    blocks: list[BlockRecord],
    line_groups: list[LineGroup],
) -> set[str]:
    block_name = (block.name or "").strip()
    if not block_name.upper().endswith("+OF11-12"):
        return set()
    matching_blocks = [
        other
        for other in blocks
        if other.sheet_id == block.sheet_id
        and (other.name or "").strip().upper() == block_name.upper()
    ]
    auxiliary_texts = [
        text
        for text in texts
        if (text.source_block_name or "").strip().upper() == block_name.upper()
        and str(text.normalized_text or "").strip() in _KK_IGNORED_AUXILIARY_PORTS
        and _nearest_block_to_text(text, matching_blocks) == block
    ]
    consumed: set[str] = set()
    for text in auxiliary_texts:
        text_x, text_y = _text_center(text)
        for group in line_groups:
            if group.orientation != "horizontal":
                continue
            group_y = (group.start_y + group.end_y) / 2.0
            if abs(group_y - text_y) > _KK_HORIZONTAL_LINE_Y_TOL:
                continue
            min_x = min(group.start_x, group.end_x)
            max_x = max(group.start_x, group.end_x)
            x_gap = 0.0 if min_x <= text_x <= max_x else min(abs(text_x - min_x), abs(text_x - max_x))
            if x_gap > _KK_HORIZONTAL_LINE_X_TOL:
                continue
            if max(abs(group.start_x - block.insert_x), abs(group.end_x - block.insert_x)) > _KK_PORT_BLOCK_X_TOL:
                continue
            consumed.add(group.line_group_id)
    return consumed


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
        if _is_strip_block_name(text.source_block_name) and text.normalized_text == "1"
    ]
    bottom_ports = [
        text
        for text in texts
        if _is_strip_block_name(text.source_block_name) and text.normalized_text == "2"
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


def _is_strip_block_name(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().casefold()
    mirror_suffix = "_mirror"
    if normalized.endswith(mirror_suffix):
        normalized = normalized[: -len(mirror_suffix)]
    return normalized == _STRIP_BLOCK_BASENAME.casefold()


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
    # ``&`` is a decorative boundary marker in the source drawings.  Trim it
    # only at the boundaries after the endpoint text has already been selected
    # by the geometry/row-scoped caller; interior ``&`` remains invalidated by
    # the endpoint grammar below.  Keep the original text in pair evidence.
    return str(value or "").strip().strip("&").strip()


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
