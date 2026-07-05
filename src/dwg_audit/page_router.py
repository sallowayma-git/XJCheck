from __future__ import annotations

from collections import Counter

from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import PolylineRecord
from dwg_audit.domain.models import SheetRecord


PAIRING_ROUTE_TARGETS = {
    "WireDiagramExtractor",
    "ComponentDiagramExtractor",
    "TerminalDiagramExtractor",
}


def infer_page_type_confidence(page: SheetRecord) -> float:
    title = page.sheet_title or page.filename or ""
    category = page.sheet_category or ""
    if category in {"封面/目录", "屏面布置图", "屏端子图", "元件接线图", "背板接线图"} and category.replace("图", "")[:2] in title:
        return 0.98
    if category == "二次原理图":
        if any(keyword in title for keyword in ("回路", "信号", "保护", "出口", "操作", "开入", "控制")):
            return 0.9
        return 0.75
    if category:
        return 0.7
    return 0.25


def infer_route_target(
    page: SheetRecord,
    *,
    line_count: int = 0,
    polyline_count: int = 0,
) -> str:
    if page.audit_role == "skip":
        return "SkipExtractor"
    if page.sheet_category == "二次原理图":
        return "WireDiagramExtractor"
    if page.sheet_category == "元件接线图":
        return "ComponentDiagramExtractor"
    if page.sheet_category == "屏端子图":
        return "TerminalDiagramExtractor"
    if polyline_count >= 20 and line_count >= 40:
        return "TableExtractor"
    if page.sheet_category in {"背板接线图", "屏面布置图", "封面/目录"}:
        return "LayoutOnlyExtractor"
    return "LayoutOnlyExtractor"


def route_from_classification(classification: PageClassification) -> str:
    """基于 PageClassification 返回执行路由目标。

    这是 Page Router Layer 的主入口（任务书第 5 层），取代 scan 阶段的粗粒度推断。
    """
    return classification.route_target


def route_supports_pairing(route_target: str | None) -> bool:
    return route_target in PAIRING_ROUTE_TARGETS


def route_supports_table(route_target: str | None) -> bool:
    return route_target == "TableExtractor"


def disposition_requires_audit(audit_disposition: str | None) -> bool:
    return audit_disposition == "audit_required"


def enrich_pages_with_routing(
    pages: list[SheetRecord],
    lines: list[LineEntity],
    polylines: list[PolylineRecord],
) -> None:
    """旧接口：仅基于 sheet_category + line/polyline 计数回填 route_target。

    保留给 scan 阶段做粗粒度推断；pipeline 阶段应改用
    `enrich_pages_from_classifications` 消费 PageClassifier 输出。
    """
    line_counts = Counter(line.sheet_id for line in lines)
    polyline_counts = Counter(polyline.sheet_id for polyline in polylines)
    for page in pages:
        page.page_type_confidence = round(infer_page_type_confidence(page), 2)
        page.route_target = infer_route_target(
            page,
            line_count=line_counts.get(page.sheet_id, 0),
            polyline_count=polyline_counts.get(page.sheet_id, 0),
        )


def enrich_pages_from_classifications(
    pages: list[SheetRecord],
    classifications: dict[str, PageClassification],
) -> None:
    """用 PageClassifier 输出回填 route_target / page_type_confidence / audit_disposition。

    pipeline 在 extract 之后调用此函数，让真实几何特征驱动的路由覆盖 scan 阶段的粗推断。
    """
    for page in pages:
        classification = classifications.get(page.sheet_id)
        if classification is None:
            continue
        page.route_target = classification.route_target
        page.page_type_confidence = classification.page_type_confidence
        page.audit_disposition = classification.audit_disposition
        page.is_primary_audit_candidate = disposition_requires_audit(classification.audit_disposition)
