"""Page Classification Layer（任务书第 4 层）。

基于几何统计特征判定页型，独立于文件名/sidecar 启发式。输出 `PageClassification`，
供 Page Router Layer 做执行路由，并供 page_findings 写出结构化页级理解。

与 `ingest/project_scanner.py` 的 `sheet_category` 关系：
- `sheet_category` 来自文件名/sidecar，是粗粒度先验
- `PageClassification` 基于 extract 后的真实几何特征，是更可解释的页型判定
- 当几何特征足够强（如 grid_heavy、table_like）时，PageClassification 会覆盖 sheet_category
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import re
from typing import Any

from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import PolylineRecord
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem


_TABLE_MIN_POLYLINE = 20
_TABLE_MIN_GRID_BAND = 5
_TABLE_MIN_HORIZONTAL_RATIO = 0.6
_GRID_HEAVY_MIN_BAND = 8
_GRID_HEAVY_MIN_HORIZONTAL_RATIO = 0.7
_VERTICAL_COMPONENT_MIN_VERTICAL_RATIO = 0.55
_BACKPLATE_TABLE_MIN_ENDPOINTS = 8
_BACKPLATE_TABLE_MIN_ROW_NUMBERS = 6
_BACKPLATE_ENDPOINT_PATTERN = re.compile(r"^[&@\s]*[0-9][A-Za-z]{1,5}[0-9]+(?:-[0-9]+)?$")
_BACKPLATE_HEADER_PATTERN = re.compile(r"^[A-Za-z]{2,}[0-9]+[A-Za-z]?(?:[（(].*[）)])?$")
_AUDIT_ROUTE_TARGETS = {
    "WireDiagramExtractor",
    "ComponentDiagramExtractor",
    "TerminalDiagramExtractor",
    "TableExtractor",
}
_PAGE_CAPABILITIES = (
    "WireTopology",
    "SymbolPorts",
    "TerminalGrid",
    "TableMapping",
    "CrossPageReference",
    "CommunicationMedium",
    "MetadataOnly",
)
_CROSS_PAGE_REFERENCE_PATTERN = re.compile(r"(?:见|参见|转|续)[^\n]{0,12}(?:第\s*)?\d+\s*页|(?:第\s*)?\d+\s*页(?:续|见)")
_MEDIUM_CUE_PATTERNS = {
    "fiber_optic": {
        "fiber_lc": re.compile(r"(?<![A-Z0-9])LC(?![A-Z0-9])", re.IGNORECASE),
        "fiber_rx_tx": re.compile(r"(?<![A-Z0-9])(?:RX|TX)(?![A-Z0-9])", re.IGNORECASE),
    },
    "serial": {
        "serial_protocol": re.compile(r"RS\s*[-－]?\s*(?:232|485)", re.IGNORECASE),
        "serial_port": re.compile(r"(?<![A-Z0-9])(?:TX|RX|GND|DATA\s*[+-])(?![A-Z0-9])", re.IGNORECASE),
    },
    "ethernet": {
        "ethernet_eth": re.compile(r"(?<![A-Z0-9])(?:ETH|ETHERNET)(?![A-Z0-9])", re.IGNORECASE),
        "ethernet_physical": re.compile(r"(?<![A-Z0-9])(?:RJ45|100BASE)(?![A-Z0-9])", re.IGNORECASE),
    },
    "time_sync": {
        "time_sync_protocol": re.compile(r"(?<![A-Z0-9])(?:PTP|NTP|IRIG)(?![A-Z0-9])", re.IGNORECASE),
        "time_sync_signal": re.compile(r"(?<![A-Z0-9])(?:PPS|IRIG)(?![A-Z0-9])", re.IGNORECASE),
    },
    "logical": {
        "logical_goose": re.compile(r"(?<![A-Z0-9])GOOSE(?![A-Z0-9])", re.IGNORECASE),
        "logical_service": re.compile(r"(?<![A-Z0-9])(?:MMS|SV)(?![A-Z0-9])", re.IGNORECASE),
    },
}


def classify_pages(
    pages: list[SheetRecord],
    texts: list[TextItem],
    lines: list[LineEntity],
    polylines: list[PolylineRecord],
    blocks: list[BlockRecord],
    config: dict | None = None,
) -> dict[str, PageClassification]:
    """对每页做几何特征统计 + 页型分类。

    返回 `{sheet_id: PageClassification}`。未纳入审计的页也会返回分类（route_target=SkipExtractor）。
    """
    config = config or {}
    grid_band_tol = float(config.get("geometry", {}).get("grid_band_y_tolerance", 5.0))
    grid_min_band = int(config.get("geometry", {}).get("grid_min_band_count", _GRID_HEAVY_MIN_BAND))

    texts_by_sheet = _group_by_sheet(texts)
    lines_by_sheet = _group_by_sheet(lines)
    polylines_by_sheet = _group_by_sheet(polylines)
    blocks_by_sheet = _group_by_sheet(blocks)

    classifications: dict[str, PageClassification] = {}
    for page in pages:
        sheet_id = page.sheet_id
        sheet_texts = texts_by_sheet.get(sheet_id, [])
        sheet_lines = lines_by_sheet.get(sheet_id, [])
        sheet_polylines = polylines_by_sheet.get(sheet_id, [])
        sheet_blocks = blocks_by_sheet.get(sheet_id, [])
        features = _page_features(
            page,
            sheet_texts,
            sheet_lines,
            sheet_polylines,
            sheet_blocks,
            grid_band_tol,
        )
        classification = _classify(
            page,
            features,
            grid_min_band,
            [text for text in sheet_texts if _text_in_audit_area(text, page)],
        )
        classifications[sheet_id] = classification
    return classifications


def _page_features(
    page: SheetRecord,
    texts: list[TextItem],
    lines: list[LineEntity],
    polylines: list[PolylineRecord],
    blocks: list[BlockRecord],
    grid_band_tol: float,
) -> dict[str, Any]:
    tol = 2.0
    horizontal_count = 0
    vertical_count = 0
    horizontal_y_values: list[float] = []
    for line in lines:
        if not _line_in_audit_area(line, page):
            continue
        angle = abs(line.angle_deg)
        if angle <= tol or abs(angle - 180.0) <= tol:
            horizontal_count += 1
            horizontal_y_values.append((line.start_y + line.end_y) / 2.0)
        elif abs(angle - 90.0) <= tol:
            vertical_count += 1
    total = horizontal_count + vertical_count
    horizontal_ratio = horizontal_count / total if total else 0.0
    vertical_ratio = vertical_count / total if total else 0.0
    grid_band_count = _count_grid_bands(horizontal_y_values, grid_band_tol)

    audit_area = page.audit_area_bbox
    if audit_area is not None:
        min_x, min_y, max_x, max_y = audit_area
        area = max((max_x - min_x) * (max_y - min_y), 1.0)
    else:
        area = 1.0

    audit_texts = [text for text in texts if _text_in_audit_area(text, page)]
    numeric_text_count = sum(1 for text in audit_texts if text.is_numeric_candidate)
    backplate_endpoint_count = sum(1 for text in audit_texts if _looks_like_backplate_endpoint(text.normalized_text))
    backplate_virtual_row_count = sum(1 for text in audit_texts if text.source_block_name and _looks_like_backplate_row_number(text.normalized_text))
    backplate_virtual_header_count = sum(1 for text in audit_texts if text.source_block_name and _looks_like_backplate_header(text.normalized_text))

    return {
        "text_count": len(texts),
        "numeric_text_count": numeric_text_count,
        "backplate_endpoint_text_count": backplate_endpoint_count,
        "backplate_virtual_row_number_count": backplate_virtual_row_count,
        "backplate_virtual_header_count": backplate_virtual_header_count,
        "line_count": len(lines),
        "horizontal_line_count": horizontal_count,
        "vertical_line_count": vertical_count,
        "horizontal_line_ratio": round(horizontal_ratio, 3),
        "vertical_line_ratio": round(vertical_ratio, 3),
        "polyline_count": len(polylines),
        "block_count": len(blocks),
        "grid_band_count": grid_band_count,
        "polyline_density": round(len(polylines) / area, 6),
        "block_density": round(len(blocks) / area, 6),
    }


def _count_grid_bands(y_values: list[float], tol: float) -> int:
    if not y_values:
        return 0
    sorted_y = sorted(y_values)
    bands = 1
    previous = sorted_y[0]
    for value in sorted_y[1:]:
        if value - previous > tol:
            bands += 1
        previous = value
    return bands


def _classify(
    page: SheetRecord,
    features: dict[str, Any],
    grid_min_band: int,
    audit_texts: list[TextItem],
) -> PageClassification:
    category = page.sheet_category or ""
    horizontal_ratio = float(features.get("horizontal_line_ratio", 0.0))
    vertical_ratio = float(features.get("vertical_line_ratio", 0.0))
    polyline_count = int(features.get("polyline_count", 0))
    grid_band_count = int(features.get("grid_band_count", 0))
    backplate_endpoint_count = int(features.get("backplate_endpoint_text_count", 0))
    backplate_virtual_row_count = int(features.get("backplate_virtual_row_number_count", 0))
    backplate_virtual_header_count = int(features.get("backplate_virtual_header_count", 0))

    grid_heavy = (
        grid_band_count >= grid_min_band
        and horizontal_ratio >= _GRID_HEAVY_MIN_HORIZONTAL_RATIO
    )
    table_like = (
        polyline_count >= _TABLE_MIN_POLYLINE
        and horizontal_ratio >= _TABLE_MIN_HORIZONTAL_RATIO
        and grid_band_count >= _TABLE_MIN_GRID_BAND
        and not grid_heavy
    )
    backplate_table_like = (
        category == "背板接线图"
        and backplate_endpoint_count >= _BACKPLATE_TABLE_MIN_ENDPOINTS
        and backplate_virtual_row_count >= _BACKPLATE_TABLE_MIN_ROW_NUMBERS
        and backplate_virtual_header_count >= 1
    )
    backplate_table_routed = category == "背板接线图" and (backplate_table_like or table_like)

    if page.audit_role == "skip":
        page_type = category or "非审计页"
        subtype = None
        confidence = 0.95
        route_target = "SkipExtractor"
    elif category == "元件接线图":
        # 元件接线图优先保留组件页身份：
        # 即使横线/polyline 很多，看起来像 grid/table，真实识别目标仍应是 component extractor。
        page_type = "元件接线图"
        subtype = "vertical_component" if vertical_ratio >= _VERTICAL_COMPONENT_MIN_VERTICAL_RATIO else "horizontal_component"
        confidence = 0.85 if subtype == "vertical_component" else 0.82
        route_target = "ComponentDiagramExtractor"
    elif backplate_table_routed:
        page_type = "背板表格型图"
        subtype = "backplate_virtual_terminal_table" if backplate_table_like else "backplate_geometric_table"
        confidence = 0.86
        route_target = "TableExtractor"
    elif table_like:
        page_type = "表格型图"
        subtype = "three_column_candidate"
        confidence = 0.82
        route_target = "TableExtractor"
    elif grid_heavy:
        page_type = "二次原理图"
        subtype = "grid_heavy_wire_diagram"
        confidence = 0.88
        route_target = "WireDiagramExtractor"
    elif category == "屏端子图":
        page_type = "屏端子图"
        subtype = None
        confidence = 0.8
        route_target = "TerminalDiagramExtractor"
    elif category == "二次原理图":
        page_type = "二次原理图"
        subtype = None
        confidence = 0.8
        route_target = "WireDiagramExtractor"
    elif category in {"背板接线图", "屏面布置图"}:
        page_type = category
        subtype = None
        confidence = 0.75
        route_target = "LayoutOnlyExtractor"
    elif category:
        page_type = category
        subtype = None
        confidence = 0.7
        route_target = "LayoutOnlyExtractor"
    else:
        page_type = "unknown"
        subtype = None
        confidence = 0.3
        route_target = "LayoutOnlyExtractor"

    audit_disposition = _infer_audit_disposition(page, route_target)
    capabilities, capability_evidence, communication_media = _derive_page_capabilities(
        page,
        features,
        route_target=route_target,
        audit_disposition=audit_disposition,
        table_like=table_like or backplate_table_routed,
        grid_heavy=grid_heavy,
        audit_texts=audit_texts,
    )

    return PageClassification(
        sheet_id=page.sheet_id,
        page_type=page_type,
        page_subtype=subtype,
        page_type_confidence=round(confidence, 2),
        table_like=table_like or backplate_table_routed,
        grid_heavy=grid_heavy,
        route_target=route_target,
        features=features,
        audit_disposition=audit_disposition,
        capabilities=capabilities,
        capability_evidence=capability_evidence,
        communication_media=communication_media,
    )


def _derive_page_capabilities(
    page: SheetRecord,
    features: dict[str, Any],
    *,
    route_target: str,
    audit_disposition: str,
    table_like: bool,
    grid_heavy: bool,
    audit_texts: list[TextItem],
) -> tuple[tuple[str, ...], dict[str, dict[str, Any]], tuple[str, ...]]:
    """Return additive page capabilities without changing the legacy execution route."""
    labels: set[str] = set()
    evidence: dict[str, dict[str, Any]] = {}

    def add(label: str, *, confidence: float, reason_codes: list[str], evidence_ids: list[str] | None = None, **extra: Any) -> None:
        labels.add(label)
        evidence[label] = {
            "confidence": round(confidence, 2),
            "reason_codes": sorted(set(reason_codes)),
            "evidence_ids": sorted(set(evidence_ids or [])),
            **extra,
        }

    if route_target in {"WireDiagramExtractor", "ComponentDiagramExtractor", "TerminalDiagramExtractor"}:
        add("WireTopology", confidence=0.8, reason_codes=["PRIMARY_ROUTE_TOPOLOGY_CANDIDATE"])
    if route_target == "ComponentDiagramExtractor" or int(features.get("block_count", 0)) > 0 or page.sheet_category == "背板接线图":
        add("SymbolPorts", confidence=0.72, reason_codes=["BLOCK_OR_BACKPLATE_SYMBOL_CANDIDATE"])
    if route_target == "TerminalDiagramExtractor" or (page.sheet_category == "背板接线图" and table_like):
        add("TerminalGrid", confidence=0.76, reason_codes=["TERMINAL_OR_BACKPLATE_GRID_CANDIDATE"])
    if table_like:
        add("TableMapping", confidence=0.78, reason_codes=["TABLE_GEOMETRY_OR_BACKPLATE_STRUCTURE"])
    cross_page_ids = [text.text_id for text in audit_texts if _CROSS_PAGE_REFERENCE_PATTERN.search(text.normalized_text or text.text or "")]
    if cross_page_ids:
        add("CrossPageReference", confidence=0.7, reason_codes=["IN_AREA_CROSS_PAGE_REFERENCE"], evidence_ids=cross_page_ids)

    communication_media, medium_evidence = _detect_communication_media(audit_texts)
    if communication_media:
        add(
            "CommunicationMedium",
            confidence=min(item["confidence"] for item in medium_evidence.values()),
            reason_codes=[code for item in medium_evidence.values() for code in item["reason_codes"]],
            evidence_ids=[text_id for item in medium_evidence.values() for text_id in item["evidence_ids"]],
            media=list(communication_media),
            media_evidence=medium_evidence,
            state="candidate",
        )
    if not labels:
        # A metadata-only classification is explicitly not a clean conclusion.
        add(
            "MetadataOnly",
            confidence=0.4 if audit_disposition != "skip_stable" else 0.9,
            reason_codes=["NO_STRUCTURAL_CAPABILITY_EVIDENCE"],
        )

    ordered = tuple(label for label in _PAGE_CAPABILITIES if label in labels)
    return ordered, {label: evidence[label] for label in ordered}, communication_media


def _detect_communication_media(audit_texts: list[TextItem]) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    """Require two independent in-area content cues before emitting a shadow medium candidate."""
    media: list[str] = []
    evidence: dict[str, dict[str, Any]] = {}
    for medium, cues in _MEDIUM_CUE_PATTERNS.items():
        matched_ids: dict[str, list[str]] = {}
        for cue_name, pattern in cues.items():
            matched_ids[cue_name] = sorted(
                text.text_id
                for text in audit_texts
                if pattern.search(text.normalized_text or text.text or "")
            )
        if not all(matched_ids.values()):
            continue
        reason_codes = [f"COMM_{medium.upper()}_{cue_name.upper()}" for cue_name in sorted(matched_ids)]
        media.append(medium)
        evidence[medium] = {
            "confidence": 0.82,
            "reason_codes": reason_codes,
            "evidence_ids": sorted({item for values in matched_ids.values() for item in values}),
        }
    return tuple(media), evidence


def _infer_audit_disposition(page: SheetRecord, route_target: str) -> str:
    if page.audit_role == "skip" or route_target == "SkipExtractor":
        return "skip_stable"
    if page.audit_role == "supplemental":
        return "audit_required"
    if route_target in _AUDIT_ROUTE_TARGETS:
        return "audit_required"
    return "classify_only"


def classification_to_dict(classification: PageClassification) -> dict[str, Any]:
    data = asdict(classification)
    return data


def _group_by_sheet(items) -> dict[str, list]:
    grouped: dict[str, list] = defaultdict(list)
    for item in items:
        grouped[getattr(item, "sheet_id")].append(item)
    return grouped


def _line_in_audit_area(line: LineEntity, page: SheetRecord) -> bool:
    bbox = page.audit_area_bbox
    if bbox is None:
        return True
    min_x, min_y, max_x, max_y = bbox
    mid_x = (line.start_x + line.end_x) / 2.0
    mid_y = (line.start_y + line.end_y) / 2.0
    return min_x <= mid_x <= max_x and min_y <= mid_y <= max_y


def _text_in_audit_area(text: TextItem, page: SheetRecord) -> bool:
    bbox = page.audit_area_bbox
    if bbox is None:
        return True
    min_x, min_y, max_x, max_y = bbox
    return min_x <= text.insert_x <= max_x and min_y <= text.insert_y <= max_y


def _looks_like_backplate_endpoint(value: str | None) -> bool:
    if not value:
        return False
    return bool(_BACKPLATE_ENDPOINT_PATTERN.fullmatch(str(value).strip()))


def _looks_like_backplate_row_number(value: str | None) -> bool:
    if not value or not str(value).isdigit():
        return False
    number = int(str(value))
    return 1 <= number <= 64 and len(str(value)) <= 2


def _looks_like_backplate_header(value: str | None) -> bool:
    if not value:
        return False
    return bool(_BACKPLATE_HEADER_PATTERN.fullmatch(str(value).strip()))
