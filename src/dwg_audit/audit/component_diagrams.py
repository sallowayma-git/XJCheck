from __future__ import annotations

import re

from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_STRIP_BLOCK_NAME = "FJL-25-2A_Mirror"
_COMPONENT_BODY_PATTERN = re.compile(r"^\d+(?:-\d+)?KLP\d+$", re.IGNORECASE)
_EXTERNAL_ENDPOINT_PATTERN = re.compile(
    r"^(?:\d+(?:-\d+)?[A-Za-z]{1,4}\d+(?:-\d+)?|[A-Za-z]{1,4}\d+(?:-\d+)?)$",
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
            top_endpoint = _nearest_external_endpoint(port_top, sheet_texts, side="top")
            bottom_endpoint = _nearest_external_endpoint(port_bottom, sheet_texts, side="bottom")
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
            for port, endpoint, side_label in endpoint_specs:
                endpoint_value = _clean_external_endpoint(endpoint.normalized_text)
                if not _is_valid_external_endpoint(endpoint_value):
                    break
                logical_endpoint = f"{body.normalized_text}-{port.normalized_text}"
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
            if len(built_pairs) != 2:
                continue
            consumed_group_ids.add(support_group.line_group_id)
            pairs.extend(built_pairs)
    return pairs, consumed_group_ids


def _supports_strip_two_port_component(page: SheetRecord) -> bool:
    return (
        page.sheet_category == "元件接线图"
        and page.page_subtype == "horizontal_component"
        and page.route_target == "ComponentDiagramExtractor"
    )


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


def _nearest_external_endpoint(port: TextItem, texts: list[TextItem], *, side: str) -> TextItem | None:
    candidates = []
    for text in texts:
        if text.source_block_name:
            continue
        if text.layer.upper() == "MARK":
            continue
        if not _is_valid_external_endpoint(_clean_external_endpoint(text.normalized_text)):
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
    return sorted(candidates, key=lambda item: (abs(item.insert_x - port.insert_x), abs(item.insert_y - port.insert_y), item.text_id))[0]


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


def _is_valid_external_endpoint(value: str | None) -> bool:
    cleaned = _clean_external_endpoint(value)
    if not cleaned or "," in cleaned:
        return False
    if len(cleaned) <= 1 or cleaned.isdigit():
        return False
    return _EXTERNAL_ENDPOINT_PATTERN.fullmatch(cleaned) is not None


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
