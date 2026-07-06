from __future__ import annotations

import json
import math
import re
from pathlib import Path

import ezdxf

from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import ExtractionWarning
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import PolylineRecord
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory

_FILENAME_PAGE_PATTERN = re.compile(r"^(?P<page>\d+)\s+(?P<title>.+?)(?:\.dwg)?$", re.IGNORECASE)
_TITLE_BLOCK_PAGE_LABELS = ("页号", "page", "sheet", "图号")
_TITLE_BLOCK_TITLE_LABELS = ("图名", "图纸名称", "title")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _approx_text_bbox(text: str, x: float, y: float, height: float) -> tuple[float, float, float, float]:
    width = max(height * 0.7, len(text) * height * 0.62)
    return (x, y - height * 0.35, x + width, y + height * 0.8)


def _line_bbox(start_x: float, start_y: float, end_x: float, end_y: float) -> tuple[float, float, float, float]:
    return (
        min(start_x, end_x),
        min(start_y, end_y),
        max(start_x, end_x),
        max(start_y, end_y),
    )


def _angle_deg(start_x: float, start_y: float, end_x: float, end_y: float) -> float:
    return math.degrees(math.atan2(end_y - start_y, end_x - start_x))


def _extent_bbox(
    texts: list[TextItem],
    lines: list[LineEntity],
    blocks: list[BlockRecord],
) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for item in texts:
        xs.extend([item.bbox_min_x, item.bbox_max_x])
        ys.extend([item.bbox_min_y, item.bbox_max_y])
    for item in lines:
        xs.extend([item.bbox_min_x, item.bbox_max_x])
        ys.extend([item.bbox_min_y, item.bbox_max_y])
    for item in blocks:
        xs.append(item.insert_x)
        ys.append(item.insert_y)
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _coerce_bbox(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None


def _point_in_bbox(x: float, y: float, bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return False
    min_x, min_y, max_x, max_y = bbox
    return min_x <= x <= max_x and min_y <= y <= max_y


def _source_rank(source: str | None, config: dict) -> int:
    priority = config.get("layout", {}).get("page_no_source_priority", [])
    if source in priority:
        return priority.index(source)
    return len(priority) + 10


def _filename_title_hint(filename: str) -> str:
    match = _FILENAME_PAGE_PATTERN.match(Path(filename).stem)
    if match:
        return match.group("title")
    return Path(filename).stem


def _texts_in_title_block(
    texts: list[TextItem],
    title_bbox: tuple[float, float, float, float] | None,
) -> list[TextItem]:
    return [text for text in texts if _point_in_bbox(text.insert_x, text.insert_y, title_bbox)]


def _extract_inline_labeled_value(text: str, labels: tuple[str, ...], *, numeric_only: bool) -> str | None:
    for label in labels:
        escaped = re.escape(label)
        pattern = rf"(?i).*{escaped}\s*[:：]?\s*(?P<value>{'[0-9]+' if numeric_only else '.+'})$"
        match = re.match(pattern, text)
        if not match:
            continue
        value = _normalize_text(match.group("value"))
        if value and value.lower() != label.lower():
            return value
    return None


def _nearest_labeled_value(
    texts: list[TextItem],
    labels: tuple[str, ...],
    *,
    numeric_only: bool,
) -> str | None:
    label_texts = [text for text in texts if any(label.lower() in text.normalized_text.lower() for label in labels)]
    for label_text in label_texts:
        inline = _extract_inline_labeled_value(label_text.normalized_text, labels, numeric_only=numeric_only)
        if inline:
            return inline

        neighbors = []
        for candidate in texts:
            if candidate.text_id == label_text.text_id:
                continue
            if numeric_only and not candidate.is_numeric_candidate:
                continue
            if not numeric_only and candidate.is_numeric_candidate:
                continue
            dx = candidate.insert_x - label_text.insert_x
            dy = abs(candidate.insert_y - label_text.insert_y)
            if dx < -2.0 or dy > max(label_text.height * 3.0, 6.0):
                continue
            neighbors.append((dy, dx if dx >= 0 else 9999.0, candidate))
        if neighbors:
            neighbors.sort(key=lambda item: (item[0], item[1], -len(item[2].normalized_text)))
            return neighbors[0][2].normalized_text
    return None


def _fallback_title_block_page(texts: list[TextItem], title_bbox: tuple[float, float, float, float] | None) -> str | None:
    if title_bbox is None:
        return None
    min_x, min_y, max_x, max_y = title_bbox
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    candidates = [
        text
        for text in texts
        if text.is_numeric_candidate and 1 <= len(text.normalized_text) <= 4
    ]
    if not candidates:
        return None

    def score(item: TextItem) -> tuple[float, float, float]:
        rightness = (item.insert_x - min_x) / width
        lowness = 1.0 - ((item.insert_y - min_y) / height)
        return (rightness + lowness, item.height, -len(item.normalized_text))

    return max(candidates, key=score).normalized_text


def _fallback_title_block_title(texts: list[TextItem]) -> str | None:
    keywords = ("回路", "保护", "信号", "接线", "端子", "图")
    candidates = [
        text
        for text in texts
        if not text.is_numeric_candidate and len(text.normalized_text) >= 2 and not any(label.lower() == text.normalized_text.lower() for label in _TITLE_BLOCK_TITLE_LABELS)
    ]
    if not candidates:
        return None

    def score(item: TextItem) -> tuple[int, int, float]:
        keyword_bonus = 1 if any(keyword in item.normalized_text for keyword in keywords) else 0
        return (keyword_bonus, len(item.normalized_text), item.height)

    return max(candidates, key=score).normalized_text


def _extract_title_block_metadata(
    sheet_texts: list[TextItem],
    sheet: SheetRecord,
    config: dict,
) -> None:
    title_texts = _texts_in_title_block(sheet_texts, sheet.title_block_bbox)
    if not title_texts:
        return

    page_candidate = _nearest_labeled_value(title_texts, _TITLE_BLOCK_PAGE_LABELS, numeric_only=True)
    if page_candidate is None:
        page_candidate = _fallback_title_block_page(title_texts, sheet.title_block_bbox)

    title_candidate = _nearest_labeled_value(title_texts, _TITLE_BLOCK_TITLE_LABELS, numeric_only=False)
    if title_candidate is None:
        title_candidate = _fallback_title_block_title(title_texts)

    if page_candidate:
        current_page = sheet.sheet_no
        title_rank = _source_rank("title_block", config)
        current_rank = _source_rank(sheet.page_no_source, config)
        should_override = not current_page or title_rank < current_rank
        if should_override:
            sheet.sheet_no = page_candidate
            sheet.page_no_source = "title_block"
            if "title_block" not in sheet.source_refs:
                sheet.source_refs.append("title_block")
            if current_page and current_page != page_candidate:
                sheet.warnings.append(
                    f"Title block page number {page_candidate} overrides {current_page} based on source priority."
                )
        elif current_page != page_candidate:
            sheet.warnings.append(
                f"Title block page number {page_candidate} differs from {current_page}; kept existing source {sheet.page_no_source}."
            )

    if title_candidate:
        filename_title = _filename_title_hint(sheet.filename)
        current_title = sheet.sheet_title.strip()
        if current_title in {"", filename_title, Path(sheet.filename).stem} or sheet.page_no_source == "title_block":
            sheet.sheet_title = title_candidate
            if "title_block" not in sheet.source_refs:
                sheet.source_refs.append("title_block")


def _layout_boxes(
    extent: tuple[float, float, float, float],
    config: dict,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    min_x, min_y, max_x, max_y = extent
    width = max_x - min_x
    height = max_y - min_y

    title_cfg = config.get("layout", {}).get("title_block", {})
    audit_cfg = config.get("layout", {}).get("audit_area", {})

    title_manual = _coerce_bbox(title_cfg.get("manual_bbox"))
    if title_cfg.get("mode", "auto") == "manual" and title_manual is not None:
        title_bbox = title_manual
    else:
        title_width = width * float(title_cfg.get("width_ratio", 0.28))
        title_height = height * float(title_cfg.get("height_ratio", 0.22))
        title_bbox = (max_x - title_width, min_y, max_x, min_y + title_height)

    audit_manual = _coerce_bbox(audit_cfg.get("manual_bbox"))
    if audit_cfg.get("mode", "auto") == "manual" and audit_manual is not None:
        audit_bbox = audit_manual
    else:
        bottom_trim = height * float(audit_cfg.get("bottom_trim_ratio", 0.16))
        side_trim = width * float(audit_cfg.get("side_trim_ratio", 0.02))
        audit_bbox = (min_x + side_trim, min_y + bottom_trim, max_x - side_trim, max_y - side_trim)
    return title_bbox, audit_bbox


def _append_text(
    sheet_texts: list[TextItem],
    text_ids: IdFactory,
    numeric_pattern: re.Pattern[str],
    sheet: SheetRecord,
    handle: str,
    entity_type: str,
    layer: str,
    raw_text: str,
    insert_x: float,
    insert_y: float,
    height: float,
    rotation: float,
    source_block_name: str | None = None,
) -> None:
    text = _normalize_text(raw_text)
    if not text:
        return
    bbox = _approx_text_bbox(text, insert_x, insert_y, max(height, 1.0))
    sheet_texts.append(
        TextItem(
            text_id=text_ids.next(),
            sheet_id=sheet.sheet_id,
            file_id=sheet.file_id,
            handle=handle,
            entity_type=entity_type,
            text=text,
            normalized_text=text,
            is_numeric_candidate=bool(numeric_pattern.match(text)),
            layer=layer,
            rotation_deg=rotation,
            height=max(height, 1.0),
            insert_x=insert_x,
            insert_y=insert_y,
            bbox_min_x=bbox[0],
            bbox_min_y=bbox[1],
            bbox_max_x=bbox[2],
            bbox_max_y=bbox[3],
            source_block_name=source_block_name,
        )
    )


def _append_line(
    sheet_lines: list[LineEntity],
    line_ids: IdFactory,
    sheet: SheetRecord,
    handle: str,
    source_entity_type: str,
    layer: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> None:
    bbox = _line_bbox(start_x, start_y, end_x, end_y)
    sheet_lines.append(
        LineEntity(
            line_id=line_ids.next(),
            sheet_id=sheet.sheet_id,
            file_id=sheet.file_id,
            handle=handle,
            source_entity_type=source_entity_type,
            layer=layer,
            start_x=float(start_x),
            start_y=float(start_y),
            end_x=float(end_x),
            end_y=float(end_y),
            length=math.dist((start_x, start_y), (end_x, end_y)),
            angle_deg=_angle_deg(start_x, start_y, end_x, end_y),
            bbox_min_x=bbox[0],
            bbox_min_y=bbox[1],
            bbox_max_x=bbox[2],
            bbox_max_y=bbox[3],
        )
    )


def _extract_graphic_entity(
    entity,
    *,
    sheet: SheetRecord,
    numeric_pattern: re.Pattern[str],
    text_ids: IdFactory,
    line_ids: IdFactory,
    block_ids: IdFactory,
    polyline_ids: IdFactory,
    sheet_texts: list[TextItem],
    sheet_lines: list[LineEntity],
    sheet_blocks: list[BlockRecord],
    sheet_polylines: list[PolylineRecord],
    synthetic_handle: str | None = None,
    capture_block_record: bool = False,
    expand_virtual_insert: bool = False,
    source_block_name: str | None = None,
) -> None:
    dxftype = entity.dxftype()
    handle = synthetic_handle or str(getattr(entity.dxf, "handle", "") or f"virtual:{dxftype}")
    layer = str(getattr(entity.dxf, "layer", "0") or "0")

    if dxftype == "TEXT":
        insert = entity.dxf.insert
        _append_text(
            sheet_texts,
            text_ids,
            numeric_pattern,
            sheet,
            handle,
            dxftype,
            layer,
            entity.dxf.text,
            float(insert.x),
            float(insert.y),
            float(entity.dxf.height),
            float(entity.dxf.rotation),
            source_block_name,
        )
        return

    if dxftype == "MTEXT":
        insert = entity.dxf.insert
        _append_text(
            sheet_texts,
            text_ids,
            numeric_pattern,
            sheet,
            handle,
            dxftype,
            layer,
            entity.plain_text(),
            float(insert.x),
            float(insert.y),
            float(entity.dxf.char_height or 0.0),
            0.0,
            source_block_name,
        )
        return

    if dxftype in {"ATTRIB", "ATTDEF"}:
        insert = entity.dxf.insert
        _append_text(
            sheet_texts,
            text_ids,
            numeric_pattern,
            sheet,
            handle,
            dxftype,
            layer,
            entity.dxf.text,
            float(insert.x),
            float(insert.y),
            float(entity.dxf.height),
            float(entity.dxf.rotation),
            source_block_name,
        )
        return

    if dxftype == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end
        _append_line(
            sheet_lines,
            line_ids,
            sheet,
            handle,
            dxftype,
            layer,
            float(start.x),
            float(start.y),
            float(end.x),
            float(end.y),
        )
        return

    if dxftype == "LWPOLYLINE":
        points = [(float(x), float(y)) for x, y, *_ in entity.get_points("xy")]
        if not points:
            return
        bbox = _polyline_bbox(points)
        sheet_polylines.append(
            PolylineRecord(
                polyline_id=polyline_ids.next(),
                sheet_id=sheet.sheet_id,
                file_id=sheet.file_id,
                handle=handle,
                source_entity_type=dxftype,
                layer=layer,
                vertex_count=len(points),
                is_closed=bool(entity.closed),
                bbox_min_x=bbox[0],
                bbox_min_y=bbox[1],
                bbox_max_x=bbox[2],
                bbox_max_y=bbox[3],
            )
        )
        if entity.closed and len(points) > 1:
            points.append(points[0])
        for index, (start, end) in enumerate(zip(points, points[1:], strict=False)):
            _append_line(
                sheet_lines,
                line_ids,
                sheet,
                f"{handle}:{index}",
                dxftype,
                layer,
                start[0],
                start[1],
                end[0],
                end[1],
            )
        return

    if dxftype == "POLYLINE":
        points = [(float(vertex.dxf.location.x), float(vertex.dxf.location.y)) for vertex in entity.vertices]
        if not points:
            return
        bbox = _polyline_bbox(points)
        is_closed = bool(entity.is_closed)
        sheet_polylines.append(
            PolylineRecord(
                polyline_id=polyline_ids.next(),
                sheet_id=sheet.sheet_id,
                file_id=sheet.file_id,
                handle=handle,
                source_entity_type=dxftype,
                layer=layer,
                vertex_count=len(points),
                is_closed=is_closed,
                bbox_min_x=bbox[0],
                bbox_min_y=bbox[1],
                bbox_max_x=bbox[2],
                bbox_max_y=bbox[3],
            )
        )
        if is_closed and len(points) > 1:
            points.append(points[0])
        for index, (start, end) in enumerate(zip(points, points[1:], strict=False)):
            _append_line(
                sheet_lines,
                line_ids,
                sheet,
                f"{handle}:{index}",
                dxftype,
                layer,
                start[0],
                start[1],
                end[0],
                end[1],
            )
        return

    if dxftype == "INSERT":
        insert = entity.dxf.insert
        if capture_block_record:
            attributes = {attrib.dxf.tag: _normalize_text(attrib.dxf.text) for attrib in entity.attribs}
            sheet_blocks.append(
                BlockRecord(
                    block_id=block_ids.next(),
                    sheet_id=sheet.sheet_id,
                    file_id=sheet.file_id,
                    handle=handle,
                    name=str(entity.dxf.name),
                    layer=layer,
                    insert_x=float(insert.x),
                    insert_y=float(insert.y),
                    rotation_deg=float(entity.dxf.rotation),
                    attributes_json=json.dumps(attributes, ensure_ascii=False, sort_keys=True),
                )
            )
            for index, attrib in enumerate(entity.attribs):
                _extract_graphic_entity(
                    attrib,
                    sheet=sheet,
                    numeric_pattern=numeric_pattern,
                    text_ids=text_ids,
                    line_ids=line_ids,
                    block_ids=block_ids,
                    polyline_ids=polyline_ids,
                    sheet_texts=sheet_texts,
                    sheet_lines=sheet_lines,
                    sheet_blocks=sheet_blocks,
                    sheet_polylines=sheet_polylines,
                    synthetic_handle=f"{handle}:ATTRIB:{index}",
                    capture_block_record=False,
                    expand_virtual_insert=expand_virtual_insert,
                    source_block_name=str(entity.dxf.name),
                )

        if expand_virtual_insert:
            try:
                virtual_entities = list(entity.virtual_entities())
            except Exception:
                virtual_entities = []
            for index, virtual in enumerate(virtual_entities):
                _extract_graphic_entity(
                    virtual,
                    sheet=sheet,
                    numeric_pattern=numeric_pattern,
                    text_ids=text_ids,
                    line_ids=line_ids,
                    block_ids=block_ids,
                    polyline_ids=polyline_ids,
                    sheet_texts=sheet_texts,
                    sheet_lines=sheet_lines,
                    sheet_blocks=sheet_blocks,
                    sheet_polylines=sheet_polylines,
                    synthetic_handle=f"{handle}:VIRTUAL:{index}",
                    capture_block_record=False,
                    expand_virtual_insert=expand_virtual_insert,
                    source_block_name=str(entity.dxf.name),
                )
        return


def _polyline_bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def extract_cad_artifacts(
    scan: ProjectScanResult,
    source_files: list[SourceFileRecord],
    config: dict,
    logger,
) -> tuple[
    list[TextItem],
    list[LineEntity],
    list[BlockRecord],
    list[PolylineRecord],
    list[SheetRecord],
    list[ExtractionWarning],
]:
    sheet_map = {sheet.file_id: sheet for sheet in scan.pages}
    text_ids = IdFactory("T")
    line_ids = IdFactory("L")
    block_ids = IdFactory("B")
    polyline_ids = IdFactory("PL")
    warning_ids = IdFactory("W")

    all_texts: list[TextItem] = []
    all_lines: list[LineEntity] = []
    all_blocks: list[BlockRecord] = []
    all_polylines: list[PolylineRecord] = []
    extraction_warnings: list[ExtractionWarning] = []

    numeric_pattern = re.compile(config.get("text", {}).get("numeric_pattern", r"^[0-9]+$"))
    for source in source_files:
        sheet = sheet_map[source.file_id]
        if source.conversion_status not in {"converted", "cached"} or not source.dxf_path:
            extraction_warnings.append(
                ExtractionWarning(
                    warning_id=warning_ids.next(),
                    file_id=source.file_id,
                    sheet_id=sheet.sheet_id,
                    stage="extract",
                    code="missing_dxf",
                    message=source.conversion_detail or f"Skipping extraction for {source.filename} due to conversion status {source.conversion_status}.",
                )
            )
            continue

        try:
            doc = ezdxf.readfile(Path(source.dxf_path))
        except Exception as exc:  # pragma: no cover - depends on malformed DXF samples
            extraction_warnings.append(
                ExtractionWarning(
                    warning_id=warning_ids.next(),
                    file_id=source.file_id,
                    sheet_id=sheet.sheet_id,
                    stage="extract",
                    code="read_dxf_failed",
                    message=str(exc),
                    severity="error",
                )
            )
            sheet.warnings.append(f"Failed to read DXF: {exc}")
            continue

        msp = doc.modelspace()
        sheet.layout_name = "Model"
        sheet.drawing_units = getattr(doc, "units", None) or "unknown"

        sheet_texts: list[TextItem] = []
        sheet_lines: list[LineEntity] = []
        sheet_blocks: list[BlockRecord] = []
        sheet_polylines: list[PolylineRecord] = []
        expand_virtual_insert = sheet.sheet_category in {
            str(item)
            for item in config.get("extract", {}).get("insert_virtual_entity_categories", [])
        }

        for entity in msp:
            _extract_graphic_entity(
                entity,
                sheet=sheet,
                numeric_pattern=numeric_pattern,
                text_ids=text_ids,
                line_ids=line_ids,
                block_ids=block_ids,
                polyline_ids=polyline_ids,
                sheet_texts=sheet_texts,
                sheet_lines=sheet_lines,
                sheet_blocks=sheet_blocks,
                sheet_polylines=sheet_polylines,
                capture_block_record=True,
                expand_virtual_insert=expand_virtual_insert,
            )

        extent = _extent_bbox(sheet_texts, sheet_lines, sheet_blocks)
        if extent is not None:
            title_bbox, audit_bbox = _layout_boxes(extent, config)
            sheet.extent_bbox = extent
            sheet.frame_bbox = extent
            sheet.title_block_bbox = title_bbox
            sheet.audit_area_bbox = audit_bbox
            _extract_title_block_metadata(sheet_texts, sheet, config)
        else:
            message = "No extractable geometry found in DXF."
            sheet.warnings.append(message)
            extraction_warnings.append(
                ExtractionWarning(
                    warning_id=warning_ids.next(),
                    file_id=source.file_id,
                    sheet_id=sheet.sheet_id,
                    stage="extract",
                    code="empty_geometry",
                    message=message,
                )
            )

        logger.info(
            "Extracted %s: texts=%s lines=%s blocks=%s polylines=%s",
            source.filename,
            len(sheet_texts),
            len(sheet_lines),
            len(sheet_blocks),
            len(sheet_polylines),
        )
        all_texts.extend(sheet_texts)
        all_lines.extend(sheet_lines)
        all_blocks.extend(sheet_blocks)
        all_polylines.extend(sheet_polylines)

    return all_texts, all_lines, all_blocks, all_polylines, list(sheet_map.values()), extraction_warnings
