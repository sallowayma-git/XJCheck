from __future__ import annotations

from collections import defaultdict
import re

from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.domain.models import LineEntity
from dwg_audit.utils.ids import IdFactory


_COMPONENT_PREFIX_PATTERN = re.compile(r"^\d+-2n$", re.IGNORECASE)
_LOCAL_NUMBER_PATTERN = re.compile(r"^\d{3}$")
_EXTERNAL_ENDPOINT_PATTERN = re.compile(r"^\d+-4[A-Za-z]{2}\d+$")
_INLINE_KLP_BODY_PATTERN = re.compile(r"^(?:\d+(?:-\d+)?)?KLP\d+$", re.IGNORECASE)
_INLINE_KLP_ENDPOINT_PATTERN = re.compile(r"^\d+(?:-\d+)?(?:QD\d+|n\d+)$", re.IGNORECASE)
_INLINE_KLP_LOCAL_NUMBER_PATTERN = re.compile(r"^\d{3}$")
_INPUT_MATRIX_PREFIX_PATTERN = re.compile(r"^\d+-21n$", re.IGNORECASE)
_INPUT_MATRIX_ROW_ENDPOINT_PATTERN = re.compile(r"^\d+-21QD\d+$", re.IGNORECASE)
_ROW_Y_TOL = 1.5
_PREFIX_X_TOL = 36.0
_PREFIX_Y_SPAN = 130.0
_EXTERNAL_X_TOL = 45.0
_COMPONENT_PAIR_CONFIDENCE = 0.95
_INPUT_MATRIX_ROW_Y_TOL = 2.5
_INPUT_MATRIX_PREFIX_X_TOL = 46.0
_INPUT_MATRIX_PREFIX_Y_GAP_MIN = 25.0
_INPUT_MATRIX_ROW_ENDPOINT_X_TOL = 55.0
_INLINE_KLP_BODY_X_TOL = 48.0
_INLINE_KLP_BODY_Y_TOL = 18.0
_INLINE_KLP_PORT_ROW_TOL = 2.0
_INLINE_KLP_ENDPOINT_X_TOL = 85.0
_INLINE_KLP_ENDPOINT_ROW_Y_TOL = 2.5
_INLINE_KLP_AMBIGUITY_GAP = 3.0
_INLINE_KLP_LINE_Y_TOL = 2.0
_INLINE_KLP_LINE_PORT_Y_OFFSET = 8.0


def extract_component_prefixed_signal_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    lines: list[LineEntity] | None = None,
    *,
    pair_id_factory: IdFactory | None = None,
) -> list[Pair]:
    """Recover narrow wire-component mappings on signal-circuit pages."""
    pair_ids = pair_id_factory or IdFactory("PWCM")
    texts_by_sheet: dict[str, list[TextItem]] = defaultdict(list)
    for text in texts:
        texts_by_sheet[text.sheet_id].append(text)
    lines_by_sheet: dict[str, list[LineEntity]] = defaultdict(list)
    for line in lines or []:
        lines_by_sheet[line.sheet_id].append(line)

    pairs: list[Pair] = []
    for page in pages:
        if page.sheet_category != "二次原理图":
            continue
        sheet_texts = texts_by_sheet.get(page.sheet_id, [])
        prefixes = [text for text in sheet_texts if _looks_like_component_prefix(text.normalized_text)]
        if prefixes:
            locals_ = [text for text in sheet_texts if _looks_like_local_number(text.normalized_text)]
            endpoints = [text for text in sheet_texts if _looks_like_external_endpoint(text.normalized_text)]
            if locals_ and endpoints:
                seen: set[tuple[str, str, str]] = set()
                for prefix in sorted(prefixes, key=lambda item: (item.insert_x, item.insert_y, item.text_id)):
                    for local in _local_numbers_for_prefix(prefix, locals_):
                        endpoint = _nearest_external_endpoint(prefix, local, endpoints)
                        if endpoint is None:
                            continue
                        logical_endpoint = f"{prefix.normalized_text}{local.normalized_text}"
                        dedupe_key = (prefix.text_id, local.text_id, endpoint.text_id)
                        if dedupe_key in seen:
                            continue
                        seen.add(dedupe_key)
                        pairs.append(_build_component_pair(page, prefix, local, endpoint, logical_endpoint, pair_ids))
        pairs.extend(
            _extract_input_matrix_wire_pairs(
                page,
                sheet_texts,
                pair_ids,
            )
        )
        pairs.extend(
            _extract_inline_klp_port_pairs(
                page,
                sheet_texts,
                lines_by_sheet.get(page.sheet_id, []),
                pair_ids,
            )
        )
    return pairs


def _extract_input_matrix_wire_pairs(
    page: SheetRecord,
    sheet_texts: list[TextItem],
    pair_ids: IdFactory,
) -> list[Pair]:
    prefixes = [text for text in sheet_texts if _looks_like_input_matrix_prefix(text.normalized_text)]
    row_endpoints = [text for text in sheet_texts if _looks_like_input_matrix_row_endpoint(text.normalized_text)]
    local_numbers = [text for text in sheet_texts if _looks_like_local_number(text.normalized_text)]
    if len(prefixes) < 2 or len(row_endpoints) < 2 or len(local_numbers) < 2:
        return []

    deduped_prefixes = _dedupe_input_matrix_prefixes(prefixes)
    if len(deduped_prefixes) < 2:
        return []

    pairs: list[Pair] = []
    seen: set[tuple[str, str, str]] = set()
    for local in sorted(local_numbers, key=lambda item: (item.insert_y, item.insert_x, item.text_id)):
        prefix = _nearest_input_matrix_prefix(local, deduped_prefixes)
        row_endpoint = _nearest_input_matrix_row_endpoint(local, row_endpoints)
        if prefix is None or row_endpoint is None:
            continue
        logical_endpoint = f"{prefix.normalized_text}{local.normalized_text}"
        dedupe_key = (row_endpoint.normalized_text, local.normalized_text, logical_endpoint)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        pairs.append(_build_input_matrix_wire_pair(page, prefix, row_endpoint, local, logical_endpoint, pair_ids))
    return pairs


def _extract_inline_klp_port_pairs(
    page: SheetRecord,
    sheet_texts: list[TextItem],
    sheet_lines: list[LineEntity],
    pair_ids: IdFactory,
) -> list[Pair]:
    bodies = [text for text in sheet_texts if _looks_like_inline_klp_body(text.normalized_text)]
    ports = [text for text in sheet_texts if _looks_like_inline_klp_port(text.normalized_text)]
    endpoints = [text for text in sheet_texts if _looks_like_inline_klp_endpoint(text.normalized_text)]
    if not bodies or len(ports) < 2 or len(endpoints) < 2:
        return []

    pairs: list[Pair] = []
    seen: set[tuple[str, str, str]] = set()
    for body in sorted(bodies, key=lambda item: (item.insert_y, item.insert_x, item.text_id)):
        port_1 = _nearest_inline_klp_port(body, ports, "1")
        port_2 = _nearest_inline_klp_port(body, ports, "2")
        if port_1 is None or port_2 is None:
            continue
        if abs(port_1.insert_y - port_2.insert_y) > _INLINE_KLP_PORT_ROW_TOL:
            continue
        if port_1.insert_x >= port_2.insert_x:
            continue

        left_endpoint = _nearest_inline_klp_endpoint(body, port_1, endpoints, side="left")
        right_endpoint = _nearest_inline_klp_endpoint(body, port_2, endpoints, side="right")
        if left_endpoint is None or right_endpoint is None:
            continue

        support_lines = _supporting_inline_klp_lines(
            sheet_lines,
            row_y=(port_1.insert_y + port_2.insert_y) / 2.0,
            min_x=left_endpoint.insert_x,
            max_x=right_endpoint.insert_x,
        )
        if len(support_lines) < 2:
            continue
        component_bbox = _component_bbox_from_items([body, port_1, port_2])
        for port, endpoint, side_label in (
            (port_1, left_endpoint, "left"),
            (port_2, right_endpoint, "right"),
        ):
            logical_endpoint = f"{body.normalized_text}-{port.normalized_text}"
            endpoint_value = _normalize_inline_klp_endpoint_value(body, endpoint)
            dedupe_key = (body.text_id, port.text_id, endpoint.text_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            pairs.append(
                _build_inline_klp_component_pair(
                    page=page,
                    body=body,
                    port=port,
                    endpoint=endpoint,
                    endpoint_value=endpoint_value,
                    logical_endpoint=logical_endpoint,
                    side_label=side_label,
                    component_bbox=component_bbox,
                    support_lines=support_lines,
                    pair_ids=pair_ids,
                )
            )
    return pairs


def _build_component_pair(
    page: SheetRecord,
    prefix: TextItem,
    local: TextItem,
    endpoint: TextItem,
    logical_endpoint: str,
    pair_ids: IdFactory,
) -> Pair:
    component_bbox = [
        prefix.insert_x - _PREFIX_X_TOL,
        max(prefix.insert_y - _PREFIX_Y_SPAN, 0.0),
        prefix.insert_x + _PREFIX_X_TOL,
        prefix.insert_y,
    ]
    evidence = {
        "source": "wire_component_mapping",
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "pair_kind": "wire_component_mapping",
        "component_submode": "component_prefixed_signal_circuit",
        "component_prefix": prefix.normalized_text,
        "component_prefix_text_id": prefix.text_id,
        "component_prefix_coord": [prefix.insert_x, prefix.insert_y],
        "local_number": local.normalized_text,
        "local_number_text_id": local.text_id,
        "local_number_coord": [local.insert_x, local.insert_y],
        "external_endpoint": endpoint.normalized_text,
        "external_endpoint_text_id": endpoint.text_id,
        "external_endpoint_coord": [endpoint.insert_x, endpoint.insert_y],
        "logical_endpoint": logical_endpoint,
        "component_bbox": component_bbox,
        "line_orientation": "component_prefixed_signal",
        "row_band_id": None,
        "left_side_label": "logical_endpoint",
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
        line_group_id=None,
        sheet_id=page.sheet_id,
        file_id=page.file_id,
        selected_pair_candidate_id=None,
        left_value=logical_endpoint,
        right_value=endpoint.normalized_text,
        confidence=_COMPONENT_PAIR_CONFIDENCE,
        status="pass",
        rationale="Component-prefixed signal circuit mapping: component prefix plus local number associated with same-row external endpoint.",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence=evidence,
        left_text_id=local.text_id,
        right_text_id=endpoint.text_id,
        left_coord_x=local.insert_x,
        left_coord_y=local.insert_y,
        right_coord_x=endpoint.insert_x,
        right_coord_y=endpoint.insert_y,
        pair_key=f"{logical_endpoint}->{endpoint.normalized_text}",
        left_score=1.0,
        right_score=1.0,
        wire_score=1.0,
        ambiguity_gap=None,
        pair_kind="wire_component_mapping",
    )


def _build_input_matrix_wire_pair(
    page: SheetRecord,
    prefix: TextItem,
    row_endpoint: TextItem,
    local: TextItem,
    logical_endpoint: str,
    pair_ids: IdFactory,
) -> Pair:
    component_bbox = _component_bbox_from_items([prefix, row_endpoint, local])
    evidence = {
        "source": "wire_component_mapping",
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "pair_kind": "wire_component_mapping",
        "component_submode": "input_matrix_wire_mapping",
        "matrix_prefix": prefix.normalized_text,
        "matrix_prefix_text_id": prefix.text_id,
        "matrix_prefix_coord": [prefix.insert_x, prefix.insert_y],
        "row_endpoint": row_endpoint.normalized_text,
        "row_endpoint_text_id": row_endpoint.text_id,
        "row_endpoint_coord": [row_endpoint.insert_x, row_endpoint.insert_y],
        "local_number": local.normalized_text,
        "local_number_text_id": local.text_id,
        "local_number_coord": [local.insert_x, local.insert_y],
        "logical_endpoint": logical_endpoint,
        "component_bbox": component_bbox,
        "line_orientation": "input_matrix_row_column",
        "row_band_id": f"row:{round(local.insert_y, 1)}",
        "column_band_id": f"col:{prefix.normalized_text}:{round(prefix.insert_x, 1)}",
        "row_y_delta": abs(row_endpoint.insert_y - local.insert_y),
        "column_x_delta": abs(prefix.insert_x - local.insert_x),
        "prefix_y_gap": prefix.insert_y - local.insert_y,
        "left_side_label": "row_endpoint",
        "right_side_label": "logical_endpoint",
        "score_breakdown": {
            "left_score": 1.0,
            "right_score": 1.0,
            "wire_score": 1.0,
            "ambiguity_gap": None,
        },
    }
    return Pair(
        pair_id=pair_ids.next(),
        line_group_id=None,
        sheet_id=page.sheet_id,
        file_id=page.file_id,
        selected_pair_candidate_id=None,
        left_value=row_endpoint.normalized_text,
        right_value=logical_endpoint,
        confidence=_COMPONENT_PAIR_CONFIDENCE,
        status="pass",
        rationale="Input matrix wire mapping: same-row QD endpoint associated with local number under the matrix n-prefix column.",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence=evidence,
        left_text_id=row_endpoint.text_id,
        right_text_id=local.text_id,
        left_coord_x=row_endpoint.insert_x,
        left_coord_y=row_endpoint.insert_y,
        right_coord_x=local.insert_x,
        right_coord_y=local.insert_y,
        pair_key=f"{row_endpoint.normalized_text}->{logical_endpoint}",
        left_score=1.0,
        right_score=1.0,
        wire_score=1.0,
        ambiguity_gap=None,
        pair_kind="wire_component_mapping",
    )


def _build_inline_klp_component_pair(
    *,
    page: SheetRecord,
    body: TextItem,
    port: TextItem,
    endpoint: TextItem,
    endpoint_value: str,
    logical_endpoint: str,
    side_label: str,
    component_bbox: list[float],
    support_lines: list[LineEntity],
    pair_ids: IdFactory,
) -> Pair:
    evidence = {
        "source": "wire_component_mapping",
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "pair_kind": "wire_component_mapping",
        "component_submode": "inline_klp_component_port_mapping",
        "component_body": body.normalized_text,
        "component_body_text_id": body.text_id,
        "component_body_coord": [body.insert_x, body.insert_y],
        "component_port": port.normalized_text,
        "component_port_text_id": port.text_id,
        "component_port_coord": [port.insert_x, port.insert_y],
        "external_endpoint": endpoint_value,
        "external_endpoint_raw": endpoint.normalized_text,
        "external_endpoint_text_id": endpoint.text_id,
        "external_endpoint_coord": [endpoint.insert_x, endpoint.insert_y],
        "logical_endpoint": logical_endpoint,
        "component_bbox": component_bbox,
        "line_orientation": "inline_klp_horizontal",
        "supporting_line_ids": [line.line_id for line in support_lines],
        "row_band_id": None,
        "left_side_label": "logical_endpoint",
        "right_side_label": "external_endpoint",
        "endpoint_side": side_label,
        "score_breakdown": {
            "left_score": 1.0,
            "right_score": 1.0,
            "wire_score": 1.0,
            "ambiguity_gap": None,
        },
    }
    return Pair(
        pair_id=pair_ids.next(),
        line_group_id=None,
        sheet_id=page.sheet_id,
        file_id=page.file_id,
        selected_pair_candidate_id=None,
        left_value=logical_endpoint,
        right_value=endpoint_value,
        confidence=_COMPONENT_PAIR_CONFIDENCE,
        status="pass",
        rationale="Inline KLP component mapping: KLP body plus explicit port associated with same-row external endpoint.",
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
        pair_kind="wire_component_mapping",
    )


def _local_numbers_for_prefix(prefix: TextItem, locals_: list[TextItem]) -> list[TextItem]:
    return [
        local
        for local in locals_
        if 0.0 < prefix.insert_y - local.insert_y <= _PREFIX_Y_SPAN
        and abs(local.insert_x - prefix.insert_x) <= _PREFIX_X_TOL
    ]


def _nearest_external_endpoint(
    prefix: TextItem,
    local: TextItem,
    endpoints: list[TextItem],
) -> TextItem | None:
    local_is_left_column = local.insert_x <= prefix.insert_x
    candidates = []
    for endpoint in endpoints:
        if abs(endpoint.insert_y - local.insert_y) > _ROW_Y_TOL:
            continue
        dx = endpoint.insert_x - local.insert_x
        if local_is_left_column and not (-_EXTERNAL_X_TOL <= dx < 0):
            continue
        if not local_is_left_column and not (0 < dx <= _EXTERNAL_X_TOL):
            continue
        candidates.append(endpoint)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda endpoint: (abs(endpoint.insert_x - local.insert_x), abs(endpoint.insert_y - local.insert_y), endpoint.text_id),
    )[0]


def _looks_like_component_prefix(value: str | None) -> bool:
    return bool(value) and bool(_COMPONENT_PREFIX_PATTERN.fullmatch(str(value).strip()))


def _looks_like_local_number(value: str | None) -> bool:
    return bool(value) and bool(_LOCAL_NUMBER_PATTERN.fullmatch(str(value).strip()))


def _looks_like_external_endpoint(value: str | None) -> bool:
    return bool(value) and bool(_EXTERNAL_ENDPOINT_PATTERN.fullmatch(str(value).strip()))


def _looks_like_input_matrix_prefix(value: str | None) -> bool:
    return bool(value) and bool(_INPUT_MATRIX_PREFIX_PATTERN.fullmatch(str(value).strip()))


def _looks_like_input_matrix_row_endpoint(value: str | None) -> bool:
    return bool(value) and bool(_INPUT_MATRIX_ROW_ENDPOINT_PATTERN.fullmatch(str(value).strip()))


def _looks_like_inline_klp_body(value: str | None) -> bool:
    return bool(value) and bool(_INLINE_KLP_BODY_PATTERN.fullmatch(str(value).strip()))


def _looks_like_inline_klp_port(value: str | None) -> bool:
    return str(value or "").strip() in {"1", "2"}


def _looks_like_inline_klp_endpoint(value: str | None) -> bool:
    if not value:
        return False
    normalized = str(value).strip()
    return bool(_INLINE_KLP_ENDPOINT_PATTERN.fullmatch(normalized)) or bool(
        _INLINE_KLP_LOCAL_NUMBER_PATTERN.fullmatch(normalized)
    )


def _nearest_inline_klp_port(body: TextItem, ports: list[TextItem], value: str) -> TextItem | None:
    body_min_x = body.bbox_min_x - _INLINE_KLP_BODY_X_TOL
    body_max_x = body.bbox_max_x + _INLINE_KLP_BODY_X_TOL
    body_mid_x = _text_mid_x(body)
    body_mid_y = _text_mid_y(body)
    candidates = [
        port
        for port in ports
        if port.normalized_text.strip() == value
        and body_min_x <= port.insert_x <= body_max_x
        and abs(port.insert_y - body_mid_y) <= _INLINE_KLP_BODY_Y_TOL
    ]
    return _nearest_unambiguous(
        candidates,
        key=lambda item: (abs(item.insert_y - body_mid_y) + abs(item.insert_x - body_mid_x) * 0.1, item.text_id),
    )


def _nearest_inline_klp_endpoint(
    body: TextItem,
    port: TextItem,
    endpoints: list[TextItem],
    *,
    side: str,
) -> TextItem | None:
    candidates = []
    for endpoint in endpoints:
        if abs(endpoint.insert_y - body.insert_y) > _INLINE_KLP_ENDPOINT_ROW_Y_TOL:
            continue
        dx = endpoint.insert_x - port.insert_x
        if side == "left" and not (-_INLINE_KLP_ENDPOINT_X_TOL <= dx < 0):
            continue
        if side == "right" and not (0 < dx <= _INLINE_KLP_ENDPOINT_X_TOL):
            continue
        candidates.append(endpoint)
    return _nearest_unambiguous(
        candidates,
        key=lambda item: (abs(item.insert_x - port.insert_x), abs(item.insert_y - body.insert_y), item.text_id),
    )


def _normalize_inline_klp_endpoint_value(body: TextItem, endpoint: TextItem) -> str:
    endpoint_value = endpoint.normalized_text.strip()
    if not _INLINE_KLP_LOCAL_NUMBER_PATTERN.fullmatch(endpoint_value):
        return endpoint_value
    body_value = body.normalized_text.strip()
    prefix = body_value.split("KLP", 1)[0]
    return f"{prefix}n{endpoint_value}"


def _nearest_unambiguous(
    candidates: list[TextItem],
    *,
    key,
) -> TextItem | None:
    if not candidates:
        return None
    ordered = sorted(candidates, key=key)
    if len(ordered) >= 2:
        first_distance = key(ordered[0])[0]
        second_distance = key(ordered[1])[0]
        if abs(second_distance - first_distance) < _INLINE_KLP_AMBIGUITY_GAP:
            return None
    return ordered[0]


def _dedupe_input_matrix_prefixes(prefixes: list[TextItem]) -> list[TextItem]:
    buckets: dict[tuple[str, int, int], TextItem] = {}
    for prefix in sorted(prefixes, key=lambda item: (item.insert_y, item.insert_x, item.text_id)):
        key = (prefix.normalized_text, round(prefix.insert_x / 2.0), round(prefix.insert_y / 2.0))
        buckets.setdefault(key, prefix)
    return sorted(buckets.values(), key=lambda item: (item.insert_x, item.insert_y, item.text_id))


def _nearest_input_matrix_prefix(local: TextItem, prefixes: list[TextItem]) -> TextItem | None:
    candidates = [
        prefix
        for prefix in prefixes
        if prefix.insert_y - local.insert_y >= _INPUT_MATRIX_PREFIX_Y_GAP_MIN
        and abs(prefix.insert_x - local.insert_x) <= _INPUT_MATRIX_PREFIX_X_TOL
    ]
    return _nearest_unambiguous(
        candidates,
        key=lambda item: (abs(item.insert_x - local.insert_x), -(item.insert_y - local.insert_y), item.text_id),
    )


def _nearest_input_matrix_row_endpoint(local: TextItem, row_endpoints: list[TextItem]) -> TextItem | None:
    candidates = [
        row_endpoint
        for row_endpoint in row_endpoints
        if row_endpoint.insert_x < local.insert_x
        and abs(row_endpoint.insert_y - local.insert_y) <= _INPUT_MATRIX_ROW_Y_TOL
        and local.insert_x - row_endpoint.insert_x <= _INPUT_MATRIX_ROW_ENDPOINT_X_TOL
    ]
    return _nearest_unambiguous(
        candidates,
        key=lambda item: (abs(item.insert_y - local.insert_y), local.insert_x - item.insert_x, item.text_id),
    )


def _supporting_inline_klp_lines(
    lines: list[LineEntity],
    *,
    row_y: float,
    min_x: float,
    max_x: float,
) -> list[LineEntity]:
    support = []
    for line in lines:
        if abs(line.start_y - line.end_y) > _INLINE_KLP_LINE_Y_TOL:
            continue
        line_y = (line.start_y + line.end_y) / 2.0
        if abs(line_y - row_y) > _INLINE_KLP_LINE_PORT_Y_OFFSET:
            continue
        if line.bbox_max_x < min_x or line.bbox_min_x > max_x:
            continue
        support.append(line)
    return sorted(support, key=lambda item: (item.bbox_min_x, item.bbox_max_x, item.line_id))


def _component_bbox_from_items(items: list[TextItem]) -> list[float]:
    return [
        min(item.bbox_min_x for item in items),
        min(item.bbox_min_y for item in items),
        max(item.bbox_max_x for item in items),
        max(item.bbox_max_y for item in items),
    ]


def _text_mid_x(text: TextItem) -> float:
    return (text.bbox_min_x + text.bbox_max_x) / 2.0


def _text_mid_y(text: TextItem) -> float:
    return (text.bbox_min_y + text.bbox_max_y) / 2.0
