"""Geometry-backed component extraction for accessory/backplate pages."""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_BODY_PATTERN = re.compile(
    r"^(?:\d+(?:-\d+)?)?(?:[A-Z]*LP\d+|[A-Z]+\d*LP\d+)$",
    re.IGNORECASE,
)
_ENDPOINT_PATTERN = re.compile(
    r"^(?=.*\d)[A-Z0-9']+(?:-[A-Z0-9']+)*$",
    re.IGNORECASE,
)
_INSTANCE_PATTERN = re.compile(
    r"^(?:\d+(?:-\d+)?[A-Z][A-Z0-9']*|[A-Z][A-Z0-9']*)$",
    re.IGNORECASE,
)
_PORT_X_TOL = 4.0
_PORT_Y_MIN_GAP = 8.0
_PORT_Y_MAX_GAP = 30.0
_BODY_X_TOL = 12.0
_BODY_Y_MIN_GAP = 8.0
_BODY_Y_MAX_GAP = 26.0
_ENDPOINT_X_TOL = 14.0
_ENDPOINT_Y_MIN_GAP = 1.0
_ENDPOINT_Y_MAX_GAP = 10.0
_SIDE_LINE_X_TOL = 8.0
_PAIR_CONFIDENCE = 0.97
_PANEL_PORT_COUNTS = {2, 4, 6}
_PANEL_ROW_Y_TOL = 1.5
_PANEL_COLUMN_X_TOL = 3.0
_PANEL_ROW_GAP_MIN = 10.0
_PANEL_ROW_GAP_MAX = 35.0
_PANEL_BODY_X_TOL = 18.0
_PANEL_BODY_Y_MIN_GAP = 13.0
_PANEL_BODY_Y_MAX_GAP = 30.0
_PANEL_ENDPOINT_X_TOL = 10.0
_PANEL_ENDPOINT_Y_MIN_GAP = 1.0
_PANEL_ENDPOINT_Y_MAX_GAP = 12.0
_INLINE_PORT_Y_TOL = 2.0
_INLINE_PORT_X_MIN_GAP = 10.0
_INLINE_PORT_X_MAX_GAP = 26.0
_INLINE_BODY_X_TOL = 14.0
_INLINE_BODY_Y_MIN_GAP = 7.0
_INLINE_BODY_Y_MAX_GAP = 22.0
_INLINE_ENDPOINT_Y_TOL = 3.0
_INLINE_ENDPOINT_X_MIN_GAP = 1.0
_INLINE_ENDPOINT_X_MAX_GAP = 20.0
_CONTACT_BODY_X_TOL = 16.0
_CONTACT_BODY_Y_MIN_GAP = 8.0
_CONTACT_BODY_Y_MAX_GAP = 28.0
_CONTACT_ENDPOINT_Y_TOL = 3.0
_CONTACT_ENDPOINT_X_MIN_GAP = 1.0
_CONTACT_ENDPOINT_X_MAX_GAP = 18.0


def extract_accessory_backplate_two_port_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    lines: list[LineEntity],
    blocks: list[BlockRecord],
    *,
    pair_id_factory: IdFactory | None = None,
) -> tuple[list[Pair], list[dict[str, Any]]]:
    """Return independent port mappings plus page-level component evidence."""

    page_by_sheet = {page.sheet_id: page for page in pages}
    texts_by_sheet: dict[str, list[TextItem]] = defaultdict(list)
    lines_by_sheet: dict[str, list[LineEntity]] = defaultdict(list)
    blocks_by_sheet: dict[str, list[BlockRecord]] = defaultdict(list)
    for text in texts:
        texts_by_sheet[text.sheet_id].append(text)
    for line in lines:
        lines_by_sheet[line.sheet_id].append(line)
    for block in blocks:
        blocks_by_sheet[block.sheet_id].append(block)

    pair_ids = pair_id_factory or IdFactory("PAB")
    pairs: list[Pair] = []
    page_observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sheet_id, page in page_by_sheet.items():
        sheet_texts = texts_by_sheet.get(sheet_id, [])
        sheet_lines = lines_by_sheet.get(sheet_id, [])
        for block in blocks_by_sheet.get(sheet_id, []):
            component = None
            for recognizer in (
                _recognize_two_port_component,
                _recognize_vertical_panel_component,
                _recognize_inline_two_port_component,
                _recognize_four_port_contact_component,
            ):
                component = recognizer(block, sheet_texts, sheet_lines)
                if component is not None:
                    break
            if component is None:
                continue
            page_observations[sheet_id].append(component)
            for port_spec in component["ports"]:
                for endpoint_value in port_spec["external_endpoint_values"]:
                    pairs.append(
                        _build_pair(page, block, component, port_spec, endpoint_value, pair_ids)
                    )

    records: list[dict[str, Any]] = []
    for sheet_id, observations in sorted(page_observations.items()):
        page = page_by_sheet[sheet_id]
        structural_text_ids = sorted(
            {
                str(text_id)
                for observation in observations
                for text_id in observation.get("structural_text_ids", [])
                if text_id
            }
        )
        mappings = [
            {
                "mapping_mode": observation["mapping_mode"],
                "component_instance": observation["component_instance"],
                "component_block_handle": observation["component_block_handle"],
                "component_block_name": observation["component_block_name"],
                "port_number": port["port_number"],
                "logical_endpoint": f"{observation['component_instance']}-{port['port_number']}",
                "external_endpoint_values": port["external_endpoint_values"],
                "external_endpoint_raw": port["external_endpoint_raw"],
                "endpoint_side": port["endpoint_side"],
                "internal_connectivity": False,
                "electrical_union_eligible": False,
            }
            for observation in observations
            for port in observation["ports"]
            if port["external_endpoint_values"]
        ]
        records.append(
            {
                "sheet_id": sheet_id,
                "filename": page.filename,
                "sheet_no": page.sheet_no,
                "component_backplate": True,
                "component_count": len(observations),
                "mapping_semantics": "independent_external_ports",
                "structural_text_ids": structural_text_ids,
                "component_observations": observations,
                "mappings": mappings,
            }
        )
    return pairs, records


def _recognize_two_port_component(
    block: BlockRecord,
    texts: list[TextItem],
    lines: list[LineEntity],
) -> dict[str, Any] | None:
    prefix = f"{str(block.handle).strip()}:VIRTUAL:"
    owned_texts = [text for text in texts if str(text.handle).startswith(prefix)]
    port_one = [text for text in owned_texts if str(text.normalized_text).strip() == "1"]
    port_two = [text for text in owned_texts if str(text.normalized_text).strip() == "2"]
    if len(port_one) != 1 or len(port_two) != 1:
        return None
    top, bottom = port_one[0], port_two[0]
    if top.insert_y < bottom.insert_y:
        top, bottom = bottom, top
    if abs(top.insert_x - bottom.insert_x) > _PORT_X_TOL:
        return None
    port_gap = top.insert_y - bottom.insert_y
    if not (_PORT_Y_MIN_GAP <= port_gap <= _PORT_Y_MAX_GAP):
        return None

    owned_lines = [line for line in lines if str(line.handle).startswith(prefix)]
    vertical_sides = [
        line
        for line in owned_lines
        if abs(line.end_x - line.start_x) <= 0.5
        and abs(line.end_y - line.start_y) >= port_gap * 0.7
        and abs(((line.start_x + line.end_x) / 2.0) - top.insert_x) <= _SIDE_LINE_X_TOL
    ]
    side_xs = sorted({round((line.start_x + line.end_x) / 2.0, 3) for line in vertical_sides})
    if len(side_xs) < 2 or not (side_xs[0] < top.insert_x < side_xs[-1]):
        return None

    free_texts = [text for text in texts if not text.source_block_name]
    body = _nearest_body(top, free_texts)
    if body is None:
        return None
    top_endpoint = _nearest_endpoint(top, free_texts, side="top", excluded={body.text_id})
    bottom_endpoint = _nearest_endpoint(bottom, free_texts, side="bottom", excluded={body.text_id})
    ports = [
        _port_observation("1", "top", top, top_endpoint),
        _port_observation("2", "bottom", bottom, bottom_endpoint),
    ]
    structural_text_ids = {
        body.text_id,
        top.text_id,
        bottom.text_id,
        *(port["external_endpoint_text_id"] for port in ports if port["external_endpoint_text_id"]),
    }
    return {
        "recognition_mode": "geometry_owned_two_port_capsule",
        "mapping_mode": "accessory_backplate_two_port",
        "component_submode": "strip_two_port_component",
        "component_instance": body.normalized_text.strip(),
        "component_instance_text_id": body.text_id,
        "component_block_handle": block.handle,
        "component_block_name": block.name,
        "component_block_id": block.block_id,
        "ports": ports,
        "structural_text_ids": sorted(structural_text_ids),
        "internal_connectivity": False,
        "electrical_union_eligible": False,
        "reason_codes": [
            "INSTANCE_OWNED_PORT_LABELS_1_2",
            "PARALLEL_SIDE_GEOMETRY",
            "ABOVE_INSTANCE_LABEL",
            "INDEPENDENT_OUTWARD_PORTS",
        ],
    }


def _recognize_vertical_panel_component(
    block: BlockRecord,
    texts: list[TextItem],
    lines: list[LineEntity],
) -> dict[str, Any] | None:
    """Recognize a boxed panel whose odd/even ports face opposite sides."""

    owned_texts = _owned_texts(block, texts)
    numeric_ports = [text for text in owned_texts if str(text.normalized_text).strip().isdigit()]
    port_count = len(numeric_ports)
    if port_count not in _PANEL_PORT_COUNTS or len(owned_texts) != port_count:
        return None
    ports_by_number = {str(text.normalized_text).strip(): text for text in numeric_ports}
    if set(ports_by_number) != {str(number) for number in range(1, port_count + 1)}:
        return None

    top_ports = [ports_by_number[str(number)] for number in range(1, port_count + 1, 2)]
    bottom_ports = [ports_by_number[str(number)] for number in range(2, port_count + 1, 2)]
    if not _ports_form_opposed_rows(top_ports, bottom_ports):
        return None
    owned_lines = _owned_lines(block, lines)
    if not _has_panel_enclosure(top_ports, bottom_ports, owned_lines):
        return None

    free_texts = [text for text in texts if not text.source_block_name]
    body = _nearest_instance_above(
        top_ports,
        free_texts,
        x_tol=_PANEL_BODY_X_TOL,
        y_min_gap=_PANEL_BODY_Y_MIN_GAP,
        y_max_gap=_PANEL_BODY_Y_MAX_GAP,
    )
    if body is None:
        return None

    port_specs = []
    for number in range(1, port_count + 1):
        port = ports_by_number[str(number)]
        side = "top" if number % 2 else "bottom"
        endpoint = _nearest_vertical_endpoint(
            port,
            free_texts,
            side=side,
            excluded={body.text_id},
        )
        port_specs.append(_port_observation(str(number), side, port, endpoint))
    return _component_observation(
        block,
        body,
        port_specs,
        recognition_mode="geometry_owned_opposed_port_panel",
        mapping_mode="accessory_backplate_multi_port",
        component_submode="opposed_port_panel",
        reason_codes=[
            "INSTANCE_OWNED_CONTIGUOUS_PORTS",
            "ODD_EVEN_OPPOSED_ROWS",
            "ENCLOSING_PANEL_GEOMETRY",
            "ABOVE_INSTANCE_LABEL",
            "INDEPENDENT_OUTWARD_PORTS",
        ],
    )


def _recognize_inline_two_port_component(
    block: BlockRecord,
    texts: list[TextItem],
    lines: list[LineEntity],
) -> dict[str, Any] | None:
    """Recognize a compact horizontal component with independent left/right ports."""

    owned_texts = _owned_texts(block, texts)
    if len(owned_texts) != 2:
        return None
    ports_by_number = {str(text.normalized_text).strip(): text for text in owned_texts}
    if set(ports_by_number) != {"1", "2"}:
        return None
    left, right = ports_by_number["1"], ports_by_number["2"]
    if left.insert_x > right.insert_x:
        left, right = right, left
    x_gap = right.insert_x - left.insert_x
    if abs(left.insert_y - right.insert_y) > _INLINE_PORT_Y_TOL:
        return None
    if not (_INLINE_PORT_X_MIN_GAP <= x_gap <= _INLINE_PORT_X_MAX_GAP):
        return None
    owned_lines = _owned_lines(block, lines)
    if not _has_inline_component_geometry(left, right, owned_lines):
        return None

    free_texts = [text for text in texts if not text.source_block_name]
    body = _nearest_instance_above(
        [left, right],
        free_texts,
        x_tol=_INLINE_BODY_X_TOL,
        y_min_gap=_INLINE_BODY_Y_MIN_GAP,
        y_max_gap=_INLINE_BODY_Y_MAX_GAP,
    )
    if body is None:
        return None
    left_endpoint = _nearest_horizontal_endpoint(
        left,
        free_texts,
        side="left",
        excluded={body.text_id},
        max_gap=_INLINE_ENDPOINT_X_MAX_GAP,
    )
    right_endpoint = _nearest_horizontal_endpoint(
        right,
        free_texts,
        side="right",
        excluded={body.text_id},
        max_gap=_INLINE_ENDPOINT_X_MAX_GAP,
    )
    port_specs = [
        _port_observation("1", "left", ports_by_number["1"], left_endpoint),
        _port_observation("2", "right", ports_by_number["2"], right_endpoint),
    ]
    return _component_observation(
        block,
        body,
        port_specs,
        recognition_mode="geometry_owned_inline_two_port",
        mapping_mode="accessory_backplate_inline_two_port",
        component_submode="inline_two_port_component",
        reason_codes=[
            "INSTANCE_OWNED_PORT_LABELS_1_2",
            "HORIZONTAL_PORT_AXIS",
            "CENTRAL_COMPACT_COMPONENT_GEOMETRY",
            "ABOVE_INSTANCE_LABEL",
            "INDEPENDENT_OUTWARD_PORTS",
        ],
    )


def _recognize_four_port_contact_component(
    block: BlockRecord,
    texts: list[TextItem],
    lines: list[LineEntity],
) -> dict[str, Any] | None:
    """Recognize a 11/12/13/14 contact block without inferring contact closure."""

    owned_texts = _owned_texts(block, texts)
    ports_by_number = {str(text.normalized_text).strip(): text for text in owned_texts}
    if len(owned_texts) != 4 or set(ports_by_number) != {"11", "12", "13", "14"}:
        return None
    left_ports = [ports_by_number["11"], ports_by_number["13"]]
    right_ports = [ports_by_number["12"], ports_by_number["14"]]
    if max(abs(port.insert_x - left_ports[0].insert_x) for port in left_ports) > _PANEL_COLUMN_X_TOL:
        return None
    if max(abs(port.insert_x - right_ports[0].insert_x) for port in right_ports) > _PANEL_COLUMN_X_TOL:
        return None
    if right_ports[0].insert_x - left_ports[0].insert_x < 5.0:
        return None
    if abs(ports_by_number["11"].insert_y - ports_by_number["12"].insert_y) > _PANEL_ROW_Y_TOL:
        return None
    if abs(ports_by_number["13"].insert_y - ports_by_number["14"].insert_y) > _PANEL_ROW_Y_TOL:
        return None
    if ports_by_number["11"].insert_y - ports_by_number["13"].insert_y < 5.0:
        return None
    if not _has_contact_component_geometry(left_ports, right_ports, _owned_lines(block, lines)):
        return None

    free_texts = [text for text in texts if not text.source_block_name]
    body = _nearest_instance_above(
        list(ports_by_number.values()),
        free_texts,
        x_tol=_CONTACT_BODY_X_TOL,
        y_min_gap=_CONTACT_BODY_Y_MIN_GAP,
        y_max_gap=_CONTACT_BODY_Y_MAX_GAP,
    )
    if body is None:
        return None
    port_specs = []
    for number in ("11", "12", "13", "14"):
        port = ports_by_number[number]
        side = "left" if number in {"11", "13"} else "right"
        endpoint = _nearest_horizontal_endpoint(
            port,
            free_texts,
            side=side,
            excluded={body.text_id},
            max_gap=_CONTACT_ENDPOINT_X_MAX_GAP,
            y_tol=_CONTACT_ENDPOINT_Y_TOL,
        )
        port_specs.append(_port_observation(number, side, port, endpoint))
    return _component_observation(
        block,
        body,
        port_specs,
        recognition_mode="geometry_owned_four_port_contact",
        mapping_mode="accessory_backplate_four_port_contact",
        component_submode="four_port_contact_component",
        reason_codes=[
            "INSTANCE_OWNED_CONTACT_PORTS_11_12_13_14",
            "TWO_ROW_TWO_COLUMN_CONTACT_GEOMETRY",
            "ABOVE_INSTANCE_LABEL",
            "NO_INTERNAL_CONTACT_CLOSURE_INFERRED",
        ],
    )


def _owned_texts(block: BlockRecord, texts: list[TextItem]) -> list[TextItem]:
    prefix = f"{str(block.handle).strip()}:VIRTUAL:"
    return [text for text in texts if str(text.handle).startswith(prefix)]


def _owned_lines(block: BlockRecord, lines: list[LineEntity]) -> list[LineEntity]:
    prefix = f"{str(block.handle).strip()}:VIRTUAL:"
    return [line for line in lines if str(line.handle).startswith(prefix)]


def _ports_form_opposed_rows(top_ports: list[TextItem], bottom_ports: list[TextItem]) -> bool:
    if len(top_ports) != len(bottom_ports) or not top_ports:
        return False
    top_y = sum(port.insert_y for port in top_ports) / len(top_ports)
    bottom_y = sum(port.insert_y for port in bottom_ports) / len(bottom_ports)
    if max(abs(port.insert_y - top_y) for port in top_ports) > _PANEL_ROW_Y_TOL:
        return False
    if max(abs(port.insert_y - bottom_y) for port in bottom_ports) > _PANEL_ROW_Y_TOL:
        return False
    row_gap = top_y - bottom_y
    if not (_PANEL_ROW_GAP_MIN <= row_gap <= _PANEL_ROW_GAP_MAX):
        return False
    paired = zip(
        sorted(top_ports, key=lambda item: item.insert_x),
        sorted(bottom_ports, key=lambda item: item.insert_x),
    )
    return all(abs(top.insert_x - bottom.insert_x) <= _PANEL_COLUMN_X_TOL for top, bottom in paired)


def _has_panel_enclosure(
    top_ports: list[TextItem],
    bottom_ports: list[TextItem],
    lines: list[LineEntity],
) -> bool:
    all_ports = [*top_ports, *bottom_ports]
    min_x = min(port.insert_x for port in all_ports)
    max_x = max(port.insert_x for port in all_ports)
    top_y = sum(port.insert_y for port in top_ports) / len(top_ports)
    bottom_y = sum(port.insert_y for port in bottom_ports) / len(bottom_ports)
    row_gap = top_y - bottom_y
    minimum_width = max(10.0, (max_x - min_x) + 6.0)
    horizontal_boundaries = [
        line
        for line in lines
        if abs(line.end_y - line.start_y) <= 0.6
        and abs(line.end_x - line.start_x) >= minimum_width
        and bottom_y - 8.0 <= (line.start_y + line.end_y) / 2.0 <= top_y + 8.0
    ]
    vertical_boundaries = [
        line
        for line in lines
        if abs(line.end_x - line.start_x) <= 0.6
        and abs(line.end_y - line.start_y) >= row_gap * 0.8
        and min_x - 12.0 <= (line.start_x + line.end_x) / 2.0 <= max_x + 12.0
    ]
    side_xs = {round((line.start_x + line.end_x) / 2.0, 3) for line in vertical_boundaries}
    return len(horizontal_boundaries) >= 2 and len(side_xs) >= 2


def _has_inline_component_geometry(left: TextItem, right: TextItem, lines: list[LineEntity]) -> bool:
    internal_verticals = [
        line
        for line in lines
        if abs(line.end_x - line.start_x) <= 0.6
        and 0.8 <= abs(line.end_y - line.start_y) <= 6.0
        and left.insert_x + 1.0 < (line.start_x + line.end_x) / 2.0 < right.insert_x - 1.0
        and abs(((line.start_y + line.end_y) / 2.0) - left.insert_y) <= 3.0
    ]
    side_xs = {round((line.start_x + line.end_x) / 2.0, 3) for line in internal_verticals}
    central_horizontals = [
        line
        for line in lines
        if abs(line.end_y - line.start_y) <= 0.6
        and abs(line.end_x - line.start_x) >= 2.0
        and min(line.start_x, line.end_x) < right.insert_x
        and max(line.start_x, line.end_x) > left.insert_x
        and abs(((line.start_y + line.end_y) / 2.0) - left.insert_y) <= 3.0
    ]
    return len(side_xs) >= 2 and len(central_horizontals) >= 2


def _has_contact_component_geometry(
    left_ports: list[TextItem],
    right_ports: list[TextItem],
    lines: list[LineEntity],
) -> bool:
    left_x = sum(port.insert_x for port in left_ports) / len(left_ports)
    right_x = sum(port.insert_x for port in right_ports) / len(right_ports)
    top_y = max(port.insert_y for port in [*left_ports, *right_ports])
    bottom_y = min(port.insert_y for port in [*left_ports, *right_ports])
    central_verticals = [
        line
        for line in lines
        if abs(line.end_x - line.start_x) <= 0.6
        and left_x < (line.start_x + line.end_x) / 2.0 < right_x
        and abs(line.end_y - line.start_y) >= (top_y - bottom_y) * 0.8
    ]
    cross_lines = [
        line
        for line in lines
        if abs(line.end_y - line.start_y) <= 0.6
        and abs(line.end_x - line.start_x) >= (right_x - left_x) * 0.45
        and min(line.start_x, line.end_x) <= (left_x + right_x) / 2.0
        and max(line.start_x, line.end_x) >= (left_x + right_x) / 2.0
    ]
    return bool(central_verticals and cross_lines)


def _nearest_instance_above(
    ports: list[TextItem],
    texts: list[TextItem],
    *,
    x_tol: float,
    y_min_gap: float,
    y_max_gap: float,
) -> TextItem | None:
    center_x = sum(port.insert_x for port in ports) / len(ports)
    top_y = max(port.insert_y for port in ports)
    candidates = []
    for text in texts:
        value = str(text.normalized_text or text.text or "").strip().strip("@&").strip()
        if not _INSTANCE_PATTERN.fullmatch(value):
            continue
        x_gap = abs(text.insert_x - center_x)
        y_gap = text.insert_y - top_y
        if x_gap > x_tol or not (y_min_gap <= y_gap <= y_max_gap):
            continue
        candidates.append((text, x_gap, y_gap))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[1], item[2], item[0].text_id))[0]


def _nearest_vertical_endpoint(
    port: TextItem,
    texts: list[TextItem],
    *,
    side: str,
    excluded: set[str],
) -> TextItem | None:
    candidates = []
    for text in texts:
        if text.text_id in excluded or not _split_external_endpoints(text.normalized_text):
            continue
        x_gap = abs(text.insert_x - port.insert_x)
        if x_gap > _PANEL_ENDPOINT_X_TOL:
            continue
        y_gap = text.insert_y - port.insert_y if side == "top" else port.insert_y - text.insert_y
        if not (_PANEL_ENDPOINT_Y_MIN_GAP <= y_gap <= _PANEL_ENDPOINT_Y_MAX_GAP):
            continue
        candidates.append((text, x_gap, y_gap))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[1], item[2], item[0].text_id))[0]


def _nearest_horizontal_endpoint(
    port: TextItem,
    texts: list[TextItem],
    *,
    side: str,
    excluded: set[str],
    max_gap: float,
    y_tol: float = _INLINE_ENDPOINT_Y_TOL,
) -> TextItem | None:
    candidates = []
    for text in texts:
        if text.text_id in excluded or not _split_external_endpoints(text.normalized_text):
            continue
        y_gap = abs(text.insert_y - port.insert_y)
        if y_gap > y_tol:
            continue
        x_gap = port.insert_x - text.insert_x if side == "left" else text.insert_x - port.insert_x
        if not (_INLINE_ENDPOINT_X_MIN_GAP <= x_gap <= max_gap):
            continue
        candidates.append((text, x_gap, y_gap))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[1], item[2], item[0].text_id))[0]


def _component_observation(
    block: BlockRecord,
    body: TextItem,
    ports: list[dict[str, Any]],
    *,
    recognition_mode: str,
    mapping_mode: str,
    component_submode: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    structural_text_ids = {
        body.text_id,
        *(port["port_text_id"] for port in ports),
        *(port["external_endpoint_text_id"] for port in ports if port["external_endpoint_text_id"]),
    }
    return {
        "recognition_mode": recognition_mode,
        "mapping_mode": mapping_mode,
        "component_submode": component_submode,
        "component_instance": str(body.normalized_text).strip().strip("@&").strip(),
        "component_instance_text_id": body.text_id,
        "component_block_handle": block.handle,
        "component_block_name": block.name,
        "component_block_id": block.block_id,
        "ports": ports,
        "structural_text_ids": sorted(structural_text_ids),
        "internal_connectivity": False,
        "electrical_union_eligible": False,
        "reason_codes": reason_codes,
    }


def _nearest_body(port: TextItem, texts: list[TextItem]) -> TextItem | None:
    candidates = []
    for text in texts:
        value = str(text.normalized_text or text.text or "").strip().strip("@&").strip()
        if not _BODY_PATTERN.fullmatch(value):
            continue
        if abs(text.insert_x - port.insert_x) > _BODY_X_TOL:
            continue
        y_gap = text.insert_y - port.insert_y
        if not (_BODY_Y_MIN_GAP <= y_gap <= _BODY_Y_MAX_GAP):
            continue
        candidates.append((text, abs(text.insert_x - port.insert_x), y_gap))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[1], item[2], item[0].text_id))[0]


def _nearest_endpoint(
    port: TextItem,
    texts: list[TextItem],
    *,
    side: str,
    excluded: set[str],
) -> TextItem | None:
    candidates = []
    for text in texts:
        if text.text_id in excluded:
            continue
        values = _split_external_endpoints(text.normalized_text)
        if not values:
            continue
        if abs(text.insert_x - port.insert_x) > _ENDPOINT_X_TOL:
            continue
        y_gap = text.insert_y - port.insert_y if side == "top" else port.insert_y - text.insert_y
        if not (_ENDPOINT_Y_MIN_GAP <= y_gap <= _ENDPOINT_Y_MAX_GAP):
            continue
        candidates.append((text, abs(text.insert_x - port.insert_x), y_gap))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[1], item[2], item[0].text_id))[0]


def _split_external_endpoints(value: str | None) -> list[str]:
    cleaned = str(value or "").strip().strip("@&").strip()
    if not cleaned:
        return []
    pieces = [piece.strip().strip("@&").strip() for piece in re.split(r"[,，]", cleaned)]
    if not pieces or any(not _ENDPOINT_PATTERN.fullmatch(piece) for piece in pieces):
        return []
    return pieces


def _port_observation(
    port_number: str,
    side: str,
    port: TextItem,
    endpoint: TextItem | None,
) -> dict[str, Any]:
    return {
        "port_number": port_number,
        "port_text_id": port.text_id,
        "port_coord": [port.insert_x, port.insert_y],
        "endpoint_side": side,
        "external_endpoint_raw": endpoint.normalized_text if endpoint is not None else None,
        "external_endpoint_text_id": endpoint.text_id if endpoint is not None else None,
        "external_endpoint_coord": [endpoint.insert_x, endpoint.insert_y] if endpoint is not None else None,
        "external_endpoint_values": _split_external_endpoints(endpoint.normalized_text) if endpoint is not None else [],
    }


def _build_pair(
    page: SheetRecord,
    block: BlockRecord,
    component: dict[str, Any],
    port: dict[str, Any],
    endpoint_value: str,
    pair_ids: IdFactory,
) -> Pair:
    logical_endpoint = f"{component['component_instance']}-{port['port_number']}"
    evidence = {
        "source": "component_mapping",
        "pair_kind": "component_mapping",
        "component_submode": component["component_submode"],
        "mapping_mode": component["mapping_mode"],
        "recognition_mode": component["recognition_mode"],
        "filename": page.filename,
        "sheet_no": page.sheet_no,
        "sheet_order": page.sheet_order,
        "sheet_title": page.sheet_title,
        "component_body": component["component_instance"],
        "component_body_text_id": component["component_instance_text_id"],
        "component_port": port["port_number"],
        "component_port_text_id": port["port_text_id"],
        "component_port_coord": port["port_coord"],
        "component_block_name": block.name,
        "component_block_handle": block.handle,
        "external_endpoint": endpoint_value,
        "external_endpoint_raw": port["external_endpoint_raw"],
        "external_endpoint_split": endpoint_value,
        "external_endpoint_text_id": port["external_endpoint_text_id"],
        "external_endpoint_coord": port["external_endpoint_coord"],
        "logical_endpoint": logical_endpoint,
        "endpoint_side": port["endpoint_side"],
        "internal_connectivity_inferred": False,
        "electrical_union_eligible": False,
        "ordinary_pair_eligible": False,
        "score_breakdown": {"left_score": 1.0, "right_score": 1.0, "wire_score": 1.0, "ambiguity_gap": None},
    }
    return Pair(
        pair_id=pair_ids.next(),
        line_group_id=None,
        sheet_id=page.sheet_id,
        file_id=page.file_id,
        selected_pair_candidate_id=None,
        left_value=logical_endpoint,
        right_value=endpoint_value,
        confidence=_PAIR_CONFIDENCE,
        status="pass",
        rationale="Accessory backplate mapping: independent instance port associated with same-side external endpoint.",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence=evidence,
        left_text_id=port["port_text_id"],
        right_text_id=port["external_endpoint_text_id"],
        left_coord_x=port["port_coord"][0],
        left_coord_y=port["port_coord"][1],
        right_coord_x=port["external_endpoint_coord"][0],
        right_coord_y=port["external_endpoint_coord"][1],
        pair_key=f"{logical_endpoint}->{endpoint_value}",
        left_score=1.0,
        right_score=1.0,
        wire_score=1.0,
        ambiguity_gap=None,
        pair_kind="component_mapping",
    )
