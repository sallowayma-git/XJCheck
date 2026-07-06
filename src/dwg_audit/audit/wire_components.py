from __future__ import annotations

from collections import defaultdict
import re

from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_COMPONENT_PREFIX_PATTERN = re.compile(r"^\d+-2n$", re.IGNORECASE)
_LOCAL_NUMBER_PATTERN = re.compile(r"^\d{3}$")
_EXTERNAL_ENDPOINT_PATTERN = re.compile(r"^\d+-4[A-Za-z]{2}\d+$")
_ROW_Y_TOL = 1.5
_PREFIX_X_TOL = 36.0
_PREFIX_Y_SPAN = 130.0
_EXTERNAL_X_TOL = 45.0
_COMPONENT_PAIR_CONFIDENCE = 0.95


def extract_component_prefixed_signal_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    *,
    pair_id_factory: IdFactory | None = None,
) -> list[Pair]:
    """Recover `prefix + local number -> external endpoint` mappings on signal-circuit pages."""
    pair_ids = pair_id_factory or IdFactory("PWCM")
    texts_by_sheet: dict[str, list[TextItem]] = defaultdict(list)
    for text in texts:
        texts_by_sheet[text.sheet_id].append(text)

    pairs: list[Pair] = []
    for page in pages:
        if page.sheet_category != "二次原理图":
            continue
        sheet_texts = texts_by_sheet.get(page.sheet_id, [])
        prefixes = [text for text in sheet_texts if _looks_like_component_prefix(text.normalized_text)]
        if not prefixes:
            continue
        locals_ = [text for text in sheet_texts if _looks_like_local_number(text.normalized_text)]
        endpoints = [text for text in sheet_texts if _looks_like_external_endpoint(text.normalized_text)]
        if not locals_ or not endpoints:
            continue

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
