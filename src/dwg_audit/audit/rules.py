from __future__ import annotations

from collections import defaultdict

from dwg_audit.audit.graph_builder import PairGraphSummary
from dwg_audit.audit.graph_builder import build_pair_graph
from dwg_audit.audit.rule_base import AuditRule
from dwg_audit.audit.rule_base import RuleContext
from dwg_audit.audit.rule_base import select_rules
from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.utils.ids import IdFactory


_SEVERITY_MAP = {
    "high": "critical",
    "medium": "major",
    "low": "minor",
}


def build_issues(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    sheets: list[SheetRecord],
    config: dict,
    terminal_candidates: list[TerminalCandidate] | None = None,
) -> list[Issue]:
    enabled = set(config.get("rules", {}).get("enable", []))
    context = RuleContext(
        pairs=pairs,
        line_groups=line_groups,
        sheets=sheets,
        config=config,
        issue_ids=IdFactory("I"),
        terminal_candidates=terminal_candidates or [],
        high_threshold=float(config.get("confidence", {}).get("high_threshold", 0.92)),
        duplicate_delta=float(config.get("rules", {}).get("duplicate_same_line_score_delta", 0.08)),
        reciprocal_required=bool(config.get("rules", {}).get("reciprocal_required", False)),
        group_map={group.line_group_id: group for group in line_groups},
        sheet_map={sheet.sheet_id: sheet for sheet in sheets},
    )
    issues: list[Issue] = []
    for rule in select_rules(_RULES, enabled):
        issues.extend(rule.runner(context))
    return issues


def _run_pair_missing_side(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for pair in context.pairs:
        if pair.left_value and pair.right_value:
            continue
        issues.append(
            _issue(
                context.issue_ids,
                "R-PAIR-MISSING-SIDE",
                "review",
                pair,
                context.group_map,
                context.sheet_map,
                "Pair is missing one side.",
                title="端点数字缺失",
                explanation="该候选连接线仅匹配到一侧数字，需要人工复核另一端附近标注或图纸缺失情况。",
                recommended_action="检查该线两端附近的数字文本、图层过滤和标题栏裁剪配置。",
            )
        )
    return issues


def _run_pair_low_confidence(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for pair in context.pairs:
        if pair.confidence >= context.high_threshold and pair.status == "pass":
            continue
        issues.append(
            _issue(
                context.issue_ids,
                "R-PAIR-LOW-CONFIDENCE",
                "review",
                pair,
                context.group_map,
                context.sheet_map,
                "Pair requires review due to low confidence or ambiguity.",
                title="低置信度配对",
                explanation="该配对分数不足以自动通过，或多个候选之间分差过小。",
                recommended_action="检查候选数字距离、垂直偏差、文本高度和多候选竞争情况。",
            )
        )
    return issues


def _run_duplicate_same_line(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    ambiguous_groups = _ambiguous_candidate_groups(context.terminal_candidates, context.duplicate_delta)
    pair_by_group = {pair.line_group_id: pair for pair in context.pairs}
    for key, candidates in ambiguous_groups.items():
        line_group_id, side = key
        pair = pair_by_group.get(line_group_id)
        if pair is None:
            continue
        top_values = [candidate.value for candidate in candidates[:2] if candidate.value]
        top_scores = [candidate.score for candidate in candidates[:2]]
        issues.append(
            _issue(
                context.issue_ids,
                "R-DUPLICATE-SAME-LINE",
                "review",
                pair,
                context.group_map,
                context.sheet_map,
                "Multiple close numeric candidates appear on one side of a candidate line.",
                title="同端多候选数字",
                explanation="同一候选连接线的一侧存在多个分数接近的数字候选，不能自动选择唯一端点数字。",
                recommended_action="人工复核该线端点附近的数字标注，必要时调整搜索窗口、文字高度或图层过滤配置。",
                extra={"side": side, "candidate_values": top_values, "candidate_scores": top_scores},
            )
        )

    if not ambiguous_groups and not context.terminal_candidates:
        for pair in context.pairs:
            if pair.left_value and pair.right_value and pair.left_value == pair.right_value:
                issues.append(
                    _issue(
                        context.issue_ids,
                        "R-DUPLICATE-SAME-LINE",
                        "review",
                        pair,
                        context.group_map,
                        context.sheet_map,
                        "Same numeric value appears on both ends of one candidate line.",
                        title="同线两端同号",
                        explanation="缺少端点候选明细时的兼容检查：同一候选连接线两端出现相同数字，需要人工确认。",
                    )
                )
    return issues


def _run_cross_page_conflict(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    graph, left_to_pairs, _ = _graph_maps(_high_confidence_pairs(context))
    for left_value, rights in graph.left_to_rights.items():
        linked_pairs = left_to_pairs[left_value]
        sheet_ids = {pair.sheet_id for pair in linked_pairs}
        if len(rights) > 1 and len(sheet_ids) > 1:
            first = linked_pairs[0]
            issues.append(
                _issue(
                    context.issue_ids,
                    "R-CROSS-PAGE-CONFLICT",
                    "high",
                    first,
                    context.group_map,
                    context.sheet_map,
                    f"Left value {left_value} maps to multiple right values across pages.",
                    title="跨页配对冲突",
                    explanation="同一左侧数字在不同页映射到了不同右侧数字，存在跨页一致性冲突。",
                    recommended_action="核对相关页的引用关系、页号和重复配对来源。",
                    related_pairs=linked_pairs,
                    extra={"conflicting_values": sorted(rights), "sheet_ids": sorted(sheet_ids)},
                )
            )
    return issues


def _run_one_to_many(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    graph, left_to_pairs, _ = _graph_maps(_high_confidence_pairs(context))
    for left_value, rights in graph.left_to_rights.items():
        linked_pairs = left_to_pairs[left_value]
        if len(rights) > 1:
            first = linked_pairs[0]
            issues.append(
                _issue(
                    context.issue_ids,
                    "R-ONE-TO-MANY",
                    "high",
                    pair=first,
                    group_map=context.group_map,
                    sheet_map=context.sheet_map,
                    message=f"Left value {left_value} maps to multiple right values.",
                    title="一对多配对",
                    explanation="同一左值对应多个右值，需要人工确认是否属于合法分支还是错误配对。",
                    related_pairs=linked_pairs,
                    extra={"conflicting_values": sorted(rights)},
                )
            )
    return issues


def _run_many_to_one(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    graph, _, right_to_pairs = _graph_maps(_high_confidence_pairs(context))
    for right_value, lefts in graph.right_to_lefts.items():
        linked_pairs = right_to_pairs[right_value]
        if len(lefts) > 1:
            first = linked_pairs[0]
            issues.append(
                _issue(
                    context.issue_ids,
                    "R-MANY-TO-ONE",
                    "review",
                    pair=first,
                    group_map=context.group_map,
                    sheet_map=context.sheet_map,
                    message=f"Right value {right_value} maps back to multiple left values.",
                    title="多对一配对",
                    explanation="多个左值指向同一右值，存在回指冲突或重复引用。",
                    related_pairs=linked_pairs,
                    extra={"conflicting_values": sorted(lefts)},
                )
            )
    return issues


def _run_missing_reciprocal(context: RuleContext) -> list[Issue]:
    if not context.reciprocal_required:
        return []
    issues: list[Issue] = []
    graph, _, _ = _graph_maps(_high_confidence_pairs(context))
    for pair in context.pairs:
        if not pair.left_value or not pair.right_value:
            continue
        if (pair.right_value, pair.left_value) not in graph.pair_lookup:
            issues.append(
                _issue(
                    context.issue_ids,
                    "R-MISSING-RECIPROCAL",
                    "major",
                    pair,
                    context.group_map,
                    context.sheet_map,
                    "No reciprocal pair exists in the project.",
                    title="缺少反向配对",
                    explanation="项目中未找到反向引用配对，可能是漏页、漏标或同号引用不完整。",
                )
            )
    return issues


def _run_duplicate_pair(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    graph, _, _ = _graph_maps(_high_confidence_pairs(context))
    ordered_pairs = defaultdict(list)
    for pair in _high_confidence_pairs(context):
        ordered_pairs[(pair.left_value, pair.right_value)].append(pair)
    for key, occurrences in graph.ordered_pair_counts.items():
        if occurrences > 1:
            linked_pairs = ordered_pairs[key]
            first = linked_pairs[0]
            issues.append(
                _issue(
                    context.issue_ids,
                    "R-DUPLICATE-PAIR",
                    "minor",
                    pair=first,
                    group_map=context.group_map,
                    sheet_map=context.sheet_map,
                    message=f"Pair {key[0]} -> {key[1]} appears multiple times.",
                    title="重复配对",
                    explanation="相同有序配对在项目中出现多次，需要人工确认是否为合法重复或误识别。",
                    related_pairs=linked_pairs,
                    extra={"occurrences": occurrences},
                )
            )
    return issues


def _high_confidence_pairs(context: RuleContext) -> list[Pair]:
    return [
        pair
        for pair in context.pairs
        if pair.left_value
        and pair.right_value
        and pair.confidence >= context.high_threshold
        and (pair.status == "pass" or pair.confidence_bucket == "high")
    ]


def _graph_maps(
    pairs: list[Pair],
) -> tuple[PairGraphSummary, dict[str, list[Pair]], dict[str, list[Pair]]]:
    summary = build_pair_graph(pairs)
    left_to_pairs = defaultdict(list)
    right_to_pairs = defaultdict(list)
    for pair in pairs:
        left_to_pairs[pair.left_value].append(pair)
        right_to_pairs[pair.right_value].append(pair)
    return summary, left_to_pairs, right_to_pairs


def _ambiguous_candidate_groups(
    terminal_candidates: list[TerminalCandidate],
    duplicate_delta: float,
) -> dict[tuple[str, str], list[TerminalCandidate]]:
    by_group_side = defaultdict(list)
    for candidate in terminal_candidates:
        if candidate.status == "accepted" and candidate.value:
            by_group_side[(candidate.line_group_id, candidate.side)].append(candidate)

    ambiguous = {}
    for key, candidates in by_group_side.items():
        ordered = sorted(candidates, key=lambda item: item.score, reverse=True)
        if len(ordered) >= 2 and abs(ordered[0].score - ordered[1].score) < duplicate_delta:
            ambiguous[key] = ordered
    return ambiguous


_RULES = [
    AuditRule(
        rule_id="R-PAIR-MISSING-SIDE",
        name="Pair Missing Side",
        description="A candidate line only has one reliable side matched.",
        severity_default="review",
        runner=_run_pair_missing_side,
        input_tables=("pairs", "line_groups", "pages"),
        output_issue_type="pair_missing_side",
    ),
    AuditRule(
        rule_id="R-PAIR-LOW-CONFIDENCE",
        name="Pair Low Confidence",
        description="A pair remains ambiguous or below the automatic pass threshold.",
        severity_default="review",
        runner=_run_pair_low_confidence,
        input_tables=("pairs", "pair_candidates"),
        output_issue_type="pair_low_confidence",
    ),
    AuditRule(
        rule_id="R-DUPLICATE-SAME-LINE",
        name="Duplicate Same Line",
        description="One side of a candidate line contains multiple close numeric candidates.",
        severity_default="review",
        runner=_run_duplicate_same_line,
        input_tables=("pairs", "terminal_candidates"),
        parameters=("duplicate_same_line_score_delta",),
        output_issue_type="duplicate_same_line",
    ),
    AuditRule(
        rule_id="R-CROSS-PAGE-CONFLICT",
        name="Cross Page Conflict",
        description="The same left-side value maps to different right-side values across pages.",
        severity_default="high",
        runner=_run_cross_page_conflict,
        input_tables=("pairs", "pages"),
        output_issue_type="cross_page_conflict",
    ),
    AuditRule(
        rule_id="R-ONE-TO-MANY",
        name="One To Many",
        description="One left-side value maps to multiple right-side values.",
        severity_default="high",
        runner=_run_one_to_many,
        input_tables=("pairs",),
        output_issue_type="one_to_many",
    ),
    AuditRule(
        rule_id="R-MANY-TO-ONE",
        name="Many To One",
        description="Multiple left-side values map back to the same right-side value.",
        severity_default="review",
        runner=_run_many_to_one,
        input_tables=("pairs",),
        output_issue_type="many_to_one",
    ),
    AuditRule(
        rule_id="R-MISSING-RECIPROCAL",
        name="Missing Reciprocal",
        description="A pair has no reciprocal mapping in the project.",
        severity_default="major",
        runner=_run_missing_reciprocal,
        input_tables=("pairs",),
        parameters=("reciprocal_required",),
        output_issue_type="missing_reciprocal",
    ),
    AuditRule(
        rule_id="R-DUPLICATE-PAIR",
        name="Duplicate Pair",
        description="The same ordered pair appears multiple times.",
        severity_default="minor",
        runner=_run_duplicate_pair,
        input_tables=("pairs",),
        output_issue_type="duplicate_pair",
    ),
]


def _issue(
    issue_ids: IdFactory,
    rule_id: str,
    severity: str,
    pair: Pair,
    group_map: dict[str, LineGroup],
    sheet_map: dict[str, SheetRecord],
    message: str,
    title: str | None = None,
    explanation: str | None = None,
    recommended_action: str | None = None,
    related_pairs: list[Pair] | None = None,
    extra: dict | None = None,
) -> Issue:
    group = group_map.get(pair.line_group_id)
    sheet = sheet_map.get(pair.sheet_id)
    evidence = {
        "pair_id": pair.pair_id,
        "line_group_id": pair.line_group_id,
        "left_value": pair.left_value,
        "right_value": pair.right_value,
        "confidence": pair.confidence,
        "filename": sheet.filename if sheet else None,
        "sheet_no": sheet.sheet_no if sheet else None,
        "sheet_order": sheet.sheet_order if sheet else None,
        "line_start": [group.start_x, group.start_y] if group else None,
        "line_end": [group.end_x, group.end_y] if group else None,
        "rationale": pair.rationale,
        "pair_evidence": pair.evidence,
    }
    if extra:
        evidence.update(extra)

    related = related_pairs or [pair]
    evidence_refs = []
    for related_pair in related:
        related_sheet = sheet_map.get(related_pair.sheet_id)
        evidence_refs.append(
            {
                "pair_id": related_pair.pair_id,
                "sheet_id": related_pair.sheet_id,
                "filename": related_sheet.filename if related_sheet else None,
                "sheet_no": related_sheet.sheet_no if related_sheet else None,
                "sheet_order": related_sheet.sheet_order if related_sheet else None,
                "line_group_id": related_pair.line_group_id,
            }
        )

    values = [value for value in {pair.left_value, pair.right_value} if value]
    if extra:
        values.extend(str(value) for value in extra.get("conflicting_values", []) if value)

    return Issue(
        issue_id=issue_ids.next(),
        rule_id=rule_id,
        severity=_SEVERITY_MAP.get(severity, severity),
        status="open",
        confidence=pair.confidence,
        message=message,
        sheet_id=pair.sheet_id,
        file_id=pair.file_id,
        pair_id=pair.pair_id,
        line_group_id=pair.line_group_id,
        left_value=pair.left_value,
        right_value=pair.right_value,
        evidence=evidence,
        issue_type=rule_id,
        title=title or message,
        summary=message,
        explanation=explanation or message,
        recommended_action=recommended_action,
        primary_pair_id=pair.pair_id,
        related_pair_ids=[related_pair.pair_id for related_pair in related if related_pair.pair_id != pair.pair_id],
        sheet_ids=sorted({related_pair.sheet_id for related_pair in related}),
        values=sorted(set(values)),
        evidence_refs=evidence_refs,
    )
