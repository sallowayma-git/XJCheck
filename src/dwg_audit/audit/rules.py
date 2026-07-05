from __future__ import annotations

from collections import defaultdict

from dwg_audit.audit.graph_builder import PairGraphSummary
from dwg_audit.audit.graph_builder import build_pair_graph
from dwg_audit.audit.rule_base import AuditRule
from dwg_audit.audit.rule_base import IssueFactory
from dwg_audit.audit.rule_base import RuleContext
from dwg_audit.audit.rule_base import cluster_issues
from dwg_audit.audit.rule_base import select_rules
from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.utils.ids import IdFactory


def build_issues(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    sheets: list[SheetRecord],
    config: dict,
    terminal_candidates: list[TerminalCandidate] | None = None,
) -> list[Issue]:
    enabled = set(config.get("rules", {}).get("enable", []))
    group_map = {group.line_group_id: group for group in line_groups}
    sheet_map = {sheet.sheet_id: sheet for sheet in sheets}
    context = RuleContext(
        pairs=pairs,
        line_groups=line_groups,
        sheets=sheets,
        config=config,
        terminal_candidates=terminal_candidates or [],
        high_threshold=float(config.get("confidence", {}).get("high_threshold", 0.92)),
        duplicate_delta=float(config.get("rules", {}).get("duplicate_same_line_score_delta", 0.08)),
        reciprocal_required=bool(config.get("rules", {}).get("reciprocal_required", False)),
        group_map=group_map,
        sheet_map=sheet_map,
        issue_factory=IssueFactory(issue_ids=IdFactory("I"), group_map=group_map, sheet_map=sheet_map),
    )
    issues: list[Issue] = []
    for rule in select_rules(_RULES, enabled):
        issues.extend(rule.runner(context))
    return cluster_issues(issues)


def _run_pair_missing_side(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    aggregated_pair_ids: set[str] = set()
    for pair, related_pair, evidence in _complementary_half_pair_matches(context):
        aggregated_pair_ids.add(pair.pair_id)
        aggregated_pair_ids.add(related_pair.pair_id)
        issues.append(
            context.issue_factory.build(
                "R-PAIR-MISSING-SIDE",
                "review",
                pair,
                "Complementary half-pairs share a text anchor and likely belong to one broken wire chain.",
                title="互补半链待复核",
                explanation="两条单侧配对共享同一个数字文本锚点，且几何上表现为被 inline 数字切开的相邻线段，通常需要作为同一条连接链一起复核。",
                recommended_action="优先检查共享数字附近是否存在被切断的同一根导线，再决定是否调整桥接阈值或保留为真实单侧缺失。",
                related_pairs=[pair, related_pair],
                extra=evidence,
            )
        )

    for pair in context.pairs:
        if pair.status == "discard":
            continue
        if pair.pair_id in aggregated_pair_ids:
            continue
        if pair.left_value and pair.right_value:
            continue
        issues.append(
            context.issue_factory.build(
                "R-PAIR-MISSING-SIDE",
                "review",
                pair,
                "Pair is missing one side.",
                title="端点数字缺失",
                explanation="该候选连接线仅匹配到一侧数字，需要人工复核另一端附近标注或图纸缺失情况。",
                recommended_action="检查该线两端附近的数字文本、图层过滤和标题栏裁剪配置。",
            )
        )
    return issues


def _complementary_half_pair_matches(
    context: RuleContext,
) -> list[tuple[Pair, Pair, dict[str, object]]]:
    missing_left: list[Pair] = []
    missing_right_by_key = defaultdict(list)
    for pair in context.pairs:
        if pair.status == "discard":
            continue
        if pair.left_value is None and pair.right_value and pair.right_text_id:
            missing_left.append(pair)
            continue
        if pair.right_value is None and pair.left_value and pair.left_text_id:
            key = (pair.sheet_id, pair.left_text_id, pair.left_value)
            missing_right_by_key[key].append(pair)

    inline_gap = float(context.config.get("geometry", {}).get("inline_numeric_bridge_gap", 13.0))
    inline_y_tol = float(context.config.get("geometry", {}).get("inline_numeric_bridge_y_tolerance", 4.0))
    used_pair_ids: set[str] = set()
    matches: list[tuple[Pair, Pair, dict[str, object]]] = []

    for pair in missing_left:
        if pair.pair_id in used_pair_ids:
            continue
        key = (pair.sheet_id, pair.right_text_id, pair.right_value)
        candidates = [item for item in missing_right_by_key.get(key, []) if item.pair_id not in used_pair_ids]
        if not candidates:
            continue

        compatible: list[tuple[float, Pair, dict[str, object]]] = []
        for candidate in candidates:
            evidence = _complementary_half_pair_evidence(
                pair,
                candidate,
                context.group_map,
                inline_gap=inline_gap,
                inline_y_tol=inline_y_tol,
            )
            if evidence is None:
                continue
            compatible.append((float(evidence["bridge_gap"]), candidate, evidence))
        if not compatible:
            continue

        compatible.sort(key=lambda item: item[0])
        _, related_pair, evidence = compatible[0]
        primary_pair, secondary_pair = _order_half_pairs(pair, related_pair, context.group_map)
        used_pair_ids.add(primary_pair.pair_id)
        used_pair_ids.add(secondary_pair.pair_id)
        matches.append((primary_pair, secondary_pair, evidence))
    return matches


def _complementary_half_pair_evidence(
    missing_left: Pair,
    missing_right: Pair,
    group_map: dict[str, LineGroup],
    *,
    inline_gap: float,
    inline_y_tol: float,
) -> dict[str, object] | None:
    left_group = group_map.get(missing_left.line_group_id)
    right_group = group_map.get(missing_right.line_group_id)
    if left_group is None or right_group is None:
        return None
    if left_group.orientation != "horizontal" or right_group.orientation != "horizontal":
        return None

    bridge_gap = right_group.start_x - left_group.end_x
    if bridge_gap < 0 or bridge_gap > inline_gap:
        return None

    left_anchor_y = missing_left.right_coord_y
    right_anchor_y = missing_right.left_coord_y
    if left_anchor_y is None or right_anchor_y is None:
        return None
    bridge_y_delta = abs(left_anchor_y - right_anchor_y)
    if bridge_y_delta > inline_y_tol:
        return None

    return {
        "chain_kind": "complementary_half_pair",
        "shared_text_id": missing_left.right_text_id,
        "shared_value": missing_left.right_value,
        "bridge_gap": round(bridge_gap, 4),
        "bridge_y_delta": round(bridge_y_delta, 4),
    }


def _order_half_pairs(
    first: Pair,
    second: Pair,
    group_map: dict[str, LineGroup],
) -> tuple[Pair, Pair]:
    first_group = group_map.get(first.line_group_id)
    second_group = group_map.get(second.line_group_id)
    if first_group is None or second_group is None:
        return first, second
    if first_group.start_x <= second_group.start_x:
        return first, second
    return second, first


def _run_pair_low_confidence(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for pair in context.pairs:
        if pair.status == "discard":
            continue
        if not _ordinary_pair_eligible(pair):
            continue
        if not pair.left_value or not pair.right_value:
            continue
        if pair.confidence >= context.high_threshold and pair.status == "pass":
            continue
        issues.append(
            context.issue_factory.build(
                "R-PAIR-LOW-CONFIDENCE",
                "review",
                pair,
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
        if pair is None or pair.status == "discard":
            continue
        if not _ordinary_pair_eligible(pair):
            continue
        top_values = [candidate.value for candidate in candidates[:2] if candidate.value]
        top_scores = [candidate.score for candidate in candidates[:2]]
        issues.append(
            context.issue_factory.build(
                "R-DUPLICATE-SAME-LINE",
                "review",
                pair,
                "Multiple close numeric candidates appear on one side of a candidate line.",
                title="同端多候选数字",
                explanation="同一候选连接线的一侧存在多个分数接近的数字候选，不能自动选择唯一端点数字。",
                recommended_action="人工复核该线端点附近的数字标注，必要时调整搜索窗口、文字高度或图层过滤配置。",
                extra={"side": side, "candidate_values": top_values, "candidate_scores": top_scores},
            )
        )

    if not ambiguous_groups and not context.terminal_candidates:
        for pair in context.pairs:
            if not _ordinary_pair_eligible(pair):
                continue
            if pair.left_value and pair.right_value and pair.left_value == pair.right_value:
                issues.append(
                    context.issue_factory.build(
                        "R-DUPLICATE-SAME-LINE",
                        "review",
                        pair,
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
                context.issue_factory.build(
                    "R-CROSS-PAGE-CONFLICT",
                    "high",
                    first,
                    f"Left value {left_value} maps to multiple right values across pages.",
                    title="跨页配对冲突",
                    explanation="同一左侧数字在不同页映射到了不同右侧数字，存在跨页一致性冲突。",
                    recommended_action="核对相关页的引用关系、页号和重复配对来源。",
                    related_pairs=linked_pairs,
                    extra={
                        "conflicting_values": sorted(rights),
                        "sheet_ids": sorted(sheet_ids),
                        "one_to_many_classification": "conflict",
                    },
                )
            )
    return issues


def _run_one_to_many(context: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    graph, left_to_pairs, _ = _graph_maps(_high_confidence_pairs(context))
    branch_allowlist = _one_to_many_branch_left_values(context.config)
    for left_value, rights in graph.left_to_rights.items():
        linked_pairs = left_to_pairs[left_value]
        if len(rights) <= 1:
            continue

        sheet_ids = {pair.sheet_id for pair in linked_pairs}
        if len(sheet_ids) > 1:
            continue

        first = linked_pairs[0]
        if left_value in branch_allowlist:
            issues.append(
                context.issue_factory.build(
                    "R-ONE-TO-MANY",
                    "low",
                    pair=first,
                    message=f"Left value {left_value} fans out to multiple right values under an allowed branch rule.",
                    title="一对多合法分支",
                    explanation="该左值命中了项目允许的一对多配置，作为结构现象保留可见，但默认不记为错误。",
                    recommended_action="若该左值不应再允许分支，请移除项目配置并重新复核相关配对。",
                    related_pairs=linked_pairs,
                    extra={
                        "conflicting_values": sorted(rights),
                        "sheet_ids": sorted(sheet_ids),
                        "one_to_many_classification": "branch",
                    },
                )
            )
            continue

        issues.append(
            context.issue_factory.build(
                "R-ONE-TO-MANY",
                "review",
                pair=first,
                message=f"Left value {left_value} maps to multiple right values and requires review.",
                title="一对多待复核",
                explanation="同一左值对应多个右值，但当前缺少足够证据判定为合法分支或明确冲突，默认保守进入 review。",
                recommended_action="人工核对相关页上下文、反向引用和项目允许分支规则，再决定是否升级为 branch 或 conflict。",
                related_pairs=linked_pairs,
                extra={
                    "conflicting_values": sorted(rights),
                    "sheet_ids": sorted(sheet_ids),
                    "one_to_many_classification": "review",
                },
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
                context.issue_factory.build(
                    "R-MANY-TO-ONE",
                    "review",
                    pair=first,
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
        if not _ordinary_pair_eligible(pair):
            continue
        if not pair.left_value or not pair.right_value:
            continue
        if (pair.right_value, pair.left_value) not in graph.pair_lookup:
            issues.append(
                context.issue_factory.build(
                    "R-MISSING-RECIPROCAL",
                    "major",
                    pair,
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
                context.issue_factory.build(
                    "R-DUPLICATE-PAIR",
                    "minor",
                    pair=first,
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
        if _ordinary_pair_eligible(pair)
        if pair.left_value
        and pair.right_value
        and (
            (pair.confidence >= context.high_threshold and (pair.status == "pass" or pair.confidence_bucket == "high"))
            or pair.evidence.get("source") == "table_mapping"
        )
    ]


def _ordinary_pair_eligible(pair: Pair) -> bool:
    if getattr(pair, "pair_kind", "ordinary_pair") != "ordinary_pair":
        return False
    return pair.evidence.get("ordinary_pair_eligible", True) is not False


def _run_sheet_page_mismatch(context: RuleContext) -> list[Issue]:
    """R-SHEET-PAGE-MISMATCH：文件名页码与标题栏页码不一致。

    触发条件：当 page_no_source 包含 filename 和 title_block 两个来源，
    且两者解析出的页码不一致时，输出 major 级 issue。
    """
    issues: list[Issue] = []
    for sheet in context.sheets:
        filename_page_no = _extract_filename_page_no(sheet.filename)
        title_block_page_no = _extract_title_block_page_no(sheet)
        if filename_page_no is None or title_block_page_no is None:
            continue
        if filename_page_no == title_block_page_no:
            continue
        issue_id = context.issue_factory.issue_ids.next()
        evidence = {
            "filename": sheet.filename,
            "sheet_no": sheet.sheet_no,
            "sheet_order": sheet.sheet_order,
            "filename_page_no": filename_page_no,
            "title_block_page_no": title_block_page_no,
            "page_no_source": sheet.page_no_source,
        }
        issues.append(
            Issue(
                issue_id=issue_id,
                rule_id="R-SHEET-PAGE-MISMATCH",
                severity="major",
                status="open",
                confidence=0.9,
                message=f"Filename page no '{filename_page_no}' differs from title block page no '{title_block_page_no}'.",
                sheet_id=sheet.sheet_id,
                file_id=sheet.file_id,
                pair_id=None,
                line_group_id=None,
                left_value=None,
                right_value=None,
                evidence=evidence,
                issue_type="sheet_page_mismatch",
                title="页码不一致",
                summary=f"文件名页码 {filename_page_no} 与标题栏页码 {title_block_page_no} 不一致。",
                explanation="文件名推断的页码与标题栏推断的页码不匹配，可能存在命名错误或标题栏填写错误。",
                recommended_action="核对文件名与标题栏页码，确认哪个是正确的页码并修正另一个。",
                primary_pair_id=None,
                related_pair_ids=[],
                sheet_ids=[sheet.sheet_id] if sheet.sheet_id else [],
                values=[filename_page_no, title_block_page_no],
                evidence_refs=[
                    {
                        "sheet_id": sheet.sheet_id,
                        "filename": sheet.filename,
                        "sheet_no": sheet.sheet_no,
                        "sheet_order": sheet.sheet_order,
                    }
                ],
            )
        )
    return issues


def _extract_filename_page_no(filename: str) -> str | None:
    """从文件名前缀提取页码，例如 '08 测控1开入回路图1.dwg' -> '08'。"""
    if not filename:
        return None
    # 取文件名开头连续数字
    stripped = filename.strip()
    digits = ""
    for char in stripped:
        if char.isdigit():
            digits += char
        else:
            break
    return digits if digits else None


def _extract_title_block_page_no(sheet: SheetRecord) -> str | None:
    """从 sheet_no 提取标题栏页码。

    当 page_no_source 标记为 title_block 时，sheet_no 即来自标题栏；
    当 page_no_source 为 filename 时，sheet_no 也可能来自文件名。
    这里保守地返回 sheet_no，让上游对比逻辑只在两者都有值时触发。
    """
    if sheet.page_no_source not in {"title_block", "filename", "prj"}:
        return None
    return sheet.sheet_no


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


def _one_to_many_branch_left_values(config: dict) -> set[str]:
    configured = config.get("rules", {}).get("one_to_many_branch_left_values", [])
    return {str(value) for value in configured if value is not None}


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
        description="One left-side value maps to multiple right-side values and must be triaged as branch or review.",
        severity_default="review",
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
    AuditRule(
        rule_id="R-SHEET-PAGE-MISMATCH",
        name="Sheet Page Mismatch",
        description="Filename page number differs from title block page number.",
        severity_default="major",
        runner=_run_sheet_page_mismatch,
        input_tables=("pages",),
        output_issue_type="sheet_page_mismatch",
    ),
]
