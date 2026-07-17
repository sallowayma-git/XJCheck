from __future__ import annotations

from collections import defaultdict
import re

from dwg_audit.audit.graph_builder import PairGraphSummary
from dwg_audit.audit.graph_builder import build_pair_graph
from dwg_audit.audit.rule_base import AuditRule
from dwg_audit.audit.rule_base import IssueFactory
from dwg_audit.audit.rule_base import RuleContext
from dwg_audit.audit.issue_triage import classify_and_group_issues
from dwg_audit.audit.rule_base import cluster_issues
from dwg_audit.audit.rule_base import select_rules
from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.utils.ids import IdFactory

_SEMANTIC_ENDPOINT_PATTERNS = (
    re.compile(r"(KLP\d+-\d+)", re.IGNORECASE),
    re.compile(r"(CLP\d+-\d+)", re.IGNORECASE),
    re.compile(r"(DK\d*-\d+)", re.IGNORECASE),
    re.compile(r"((?:K)?ZKK-\d+)", re.IGNORECASE),
    re.compile(r"(KK-[A-Z0-9+\-]+)", re.IGNORECASE),
    re.compile(r"(ZK-\d+)", re.IGNORECASE),
)
_HIGH_CONFIDENCE_STRUCTURED_SOURCES = {"table_mapping", "component_mapping"}


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
    # First merge technical duplicates, then attach user-facing handling buckets
    # and review groups so the workbench can triage hundreds of findings.
    return classify_and_group_issues(cluster_issues(issues))


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
        if not _ordinary_pair_eligible(pair):
            continue
        if pair.pair_id in aggregated_pair_ids:
            continue
        if pair.left_value and pair.right_value:
            continue
        if not _missing_side_line_group_candidate(pair, context.group_map):
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
        if not _ordinary_pair_eligible(pair):
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
    if not _complementary_half_pair_orientation(left_group, right_group):
        return None
    if not _line_groups_wire_chain_compatible(left_group, right_group, inline_y_tol):
        return None

    bridge_gap = right_group.start_x - left_group.end_x
    min_gap, max_gap = _complementary_half_pair_gap_bounds(left_group, right_group, inline_gap)
    if bridge_gap < min_gap or bridge_gap > max_gap:
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
        "bridge_gap_min": round(min_gap, 4),
        "bridge_gap_max": round(max_gap, 4),
        "bridge_y_delta": round(bridge_y_delta, 4),
        "line_group_y_delta": round(abs(left_group.start_y - right_group.start_y), 4),
    }


def _complementary_half_pair_orientation(left_group: LineGroup, right_group: LineGroup) -> bool:
    allowed = {"horizontal", "grid"}
    return left_group.orientation in allowed and right_group.orientation in allowed


def _complementary_half_pair_gap_bounds(
    left_group: LineGroup,
    right_group: LineGroup,
    inline_gap: float,
) -> tuple[float, float]:
    if "grid" in {left_group.orientation, right_group.orientation}:
        return -3.0, max(inline_gap, 20.0)
    return 0.0, inline_gap


def _line_groups_wire_chain_compatible(
    left_group: LineGroup,
    right_group: LineGroup,
    inline_y_tol: float,
) -> bool:
    if abs(left_group.start_y - right_group.start_y) > inline_y_tol:
        return False
    return _wire_chain_group_candidate(left_group) and _wire_chain_group_candidate(right_group)


def _wire_chain_group_candidate(group: LineGroup) -> bool:
    layers = {str(layer).upper() for layer in group.layer_hints}
    if layers and layers.issubset({"DIM"}):
        return False
    return group.wire_candidate_score >= 0.55


def _missing_side_line_group_candidate(
    pair: Pair,
    group_map: dict[str, LineGroup],
) -> bool:
    group = group_map.get(pair.line_group_id)
    if group is None:
        return True
    layers = {str(layer).upper() for layer in group.layer_hints}
    return not (layers and layers.issubset({"DIM"}))


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
            if _is_backplate_virtual_table_scope_review(linked_pairs):
                table_mappings = [_table_mapping_evidence(pair) for pair in linked_pairs]
                issues.append(
                    context.issue_factory.build(
                        "R-CROSS-PAGE-CONFLICT",
                        "review",
                        first,
                        f"Backplate table endpoint {left_value} maps to multiple scoped terminals across pages.",
                        title="背板表格作用域待复核",
                        explanation=(
                            "同型背板插件表格中的逻辑端在不同背板页或装置作用域下指向不同外部端。"
                            "这通常表示同一表头/行号模板在不同装置实例中复用，应作为作用域待复核，"
                            "不直接按全项目同名端子 critical 冲突处理。"
                        ),
                        recommended_action="核对背板页、插件块名、表头和行号，确认这些表格行是否属于不同装置作用域。",
                        related_pairs=linked_pairs,
                        extra={
                            "conflicting_values": sorted(rights),
                            "sheet_ids": sorted(sheet_ids),
                            "one_to_many_classification": "backplate_table_scope_review",
                            "table_mapping_mode": "backplate_virtual_table",
                            "source_block_names": sorted(
                                {
                                    str(mapping.get("source_block_name"))
                                    for mapping in table_mappings
                                    if mapping.get("source_block_name")
                                }
                            ),
                            "header_prefixes": sorted(
                                {
                                    str(mapping.get("header_prefix"))
                                    for mapping in table_mappings
                                    if mapping.get("header_prefix")
                                }
                            ),
                        },
                    )
                )
                continue
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


def _run_semantic_mapping_conflict(context: RuleContext) -> list[Issue]:
    by_terminal_sheet: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for pair in context.pairs:
        if getattr(pair, "pair_kind", "ordinary_pair") != "semantic_mapping":
            continue
        terminal_value = _semantic_mapping_terminal_value(pair)
        if not terminal_value:
            continue
        terminal_scope_key = _semantic_mapping_terminal_scope_key(pair, terminal_value)
        endpoints = _normalized_semantic_endpoints(pair)
        if len(endpoints) != 1:
            continue
        sheet_entry = by_terminal_sheet[terminal_scope_key].setdefault(
            pair.sheet_id,
            {"targets": set(), "pairs": [], "terminal_values": set()},
        )
        sheet_entry["targets"].update(endpoints)
        sheet_entry["pairs"].append(pair)
        sheet_entry["terminal_values"].add(terminal_value)

    issues: list[Issue] = []
    for terminal_scope_key, sheet_entries in by_terminal_sheet.items():
        stable_entries = {
            sheet_id: entry
            for sheet_id, entry in sheet_entries.items()
            if len(entry["targets"]) == 1
        }
        if len(stable_entries) <= 1:
            continue

        endpoint_by_sheet = {
            sheet_id: next(iter(entry["targets"]))
            for sheet_id, entry in stable_entries.items()
        }
        distinct_endpoints = sorted(set(endpoint_by_sheet.values()))
        if len(distinct_endpoints) <= 1:
            continue

        ordered_sheet_entries = sorted(
            stable_entries.items(),
            key=lambda item: (
                _sheet_order_key(context.sheet_map.get(item[0])),
                item[0],
            ),
        )
        primary_sheet_id, primary_entry = ordered_sheet_entries[0]
        primary_pair = _semantic_conflict_primary_pair(primary_entry["pairs"])
        terminal_values = sorted(
            {
                str(value)
                for _, entry in ordered_sheet_entries
                for value in entry.get("terminal_values", set())
                if value
            }
        )
        terminal_value = terminal_values[0] if len(terminal_values) == 1 else terminal_scope_key

        related_pairs: list[Pair] = []
        for _, entry in ordered_sheet_entries:
            related_pairs.extend(entry["pairs"])

        issues.append(
            context.issue_factory.build(
                "R-SEMANTIC-MAPPING-CONFLICT",
                "review",
                primary_pair,
                f"Terminal value {terminal_value} maps to different semantic endpoints across sheets.",
                title="端子-语义映射冲突",
                explanation="同一端子号在不同图页被稳定映射到不同的语义端，存在 terminal-to-semantic consistency 风险。",
                recommended_action="优先复核相关端子页的语义行、端子列和跨页引用，确认这些 semantic endpoint 是否本应一致。",
                related_pairs=related_pairs,
                extra={
                    "terminal_value": terminal_value,
                    "terminal_scope_key": terminal_scope_key,
                    "semantic_targets": {
                        sheet_id: endpoint_by_sheet[sheet_id]
                        for sheet_id, _ in ordered_sheet_entries
                    },
                    "conflicting_values": distinct_endpoints,
                    "semantic_conflict_kind": "cross_sheet_semantic_endpoint_mismatch",
                },
            )
        )
    return issues


def _run_table_mapping_source_conflict(context: RuleContext) -> list[Issue]:
    grouped: dict[str, dict[str, list[Pair]]] = defaultdict(lambda: {"table_mapping": [], "ordinary_pair": []})
    for pair in _high_confidence_pairs(context):
        if not pair.left_value or not pair.right_value:
            continue
        source_kind = _table_mapping_source_kind(pair)
        if source_kind not in {"table_mapping", "ordinary_pair"}:
            continue
        grouped[pair.left_value][source_kind].append(pair)

    issues: list[Issue] = []
    for left_value, source_pairs in grouped.items():
        table_pairs = source_pairs["table_mapping"]
        ordinary_pairs = source_pairs["ordinary_pair"]
        if not table_pairs or not ordinary_pairs:
            continue

        table_values = {pair.right_value for pair in table_pairs if pair.right_value}
        ordinary_values = {pair.right_value for pair in ordinary_pairs if pair.right_value}
        if not table_values or not ordinary_values:
            continue
        if table_values == ordinary_values:
            continue

        related_pairs = sorted(
            [*table_pairs, *ordinary_pairs],
            key=lambda pair: (
                _sheet_order_key(pair),
                pair.pair_id,
            ),
        )
        primary_pair = sorted(
            table_pairs,
            key=lambda pair: (
                _sheet_order_key(pair),
                pair.pair_id,
            ),
        )[0]

        issues.append(
            context.issue_factory.build(
                "R-TABLE-MAPPING-SOURCE-CONFLICT",
                "major",
                primary_pair,
                f"Table mapping for left value {left_value} conflicts with ordinary terminal mapping.",
                title="表格映射与图内配对不一致",
                explanation="同一左值在表格映射和图内普通配对中指向了不同右值，存在 mixed-source consistency 风险。",
                recommended_action="优先复核表格行的中列/外列含义，以及相关图内端子配对是否引用了同一编号。",
                related_pairs=related_pairs,
                extra={
                    "source_conflict_kind": "table_mapping_vs_ordinary_pair",
                    "table_mapping_values": sorted(table_values),
                    "ordinary_pair_values": sorted(ordinary_values),
                    "conflicting_values": sorted(table_values | ordinary_values),
                    "table_sheet_ids": sorted({pair.sheet_id for pair in table_pairs}),
                    "ordinary_sheet_ids": sorted({pair.sheet_id for pair in ordinary_pairs}),
                    "source_pair_counts": {
                        "table_mapping": len(table_pairs),
                        "ordinary_pair": len(ordinary_pairs),
                    },
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
        if _is_authoritative_structured_cardinality_group(linked_pairs):
            # A complete backplate table row is already a machine-extracted
            # structured fact. Repeated scoped rows may intentionally fan out;
            # graph-shape rules must not reinterpret that evidence as an
            # ordinary wire ambiguity. Source conflicts remain covered by the
            # dedicated table-vs-ordinary rule.
            continue
        backplate_scope_info = _backplate_virtual_table_same_sheet_scope_info(linked_pairs)
        if backplate_scope_info is not None:
            issues.append(
                context.issue_factory.build(
                    "R-ONE-TO-MANY",
                    "review",
                    pair=first,
                    message=f"Backplate table endpoint {left_value} maps to multiple scoped terminals on the same sheet.",
                    title="背板表格同页作用域待复核",
                    explanation=(
                        "同页背板虚拟表格中，同一表头行号在不同表格区域或装置作用域下指向多个外部端。"
                        "这通常表示同一插件/表头模板在同一背板页内分区复用，应按背板表格作用域复核，"
                        "不直接按普通端子一对多解释。"
                    ),
                    recommended_action="核对背板页、插件块名、表头文本、行号和表格区域，确认这些端点是否属于不同背板表格作用域。",
                    related_pairs=linked_pairs,
                    extra={
                        "conflicting_values": sorted(rights),
                        "sheet_ids": sorted(sheet_ids),
                        "one_to_many_classification": "backplate_table_same_sheet_scope_review",
                        **backplate_scope_info,
                    },
                )
            )
            continue

        terminal_header_info = _terminal_header_table_multi_endpoint_info(linked_pairs)
        if terminal_header_info is not None:
            # Same-row left+right dual endpoints are normal terminal-sheet facts
            # (e.g. 1UD-1 → 1n2001 and 1UD-1 → 1ZKK1-2). Keep both table_mapping
            # pairs; do not raise cardinality issues for that pattern.
            if _is_terminal_header_dual_endpoint_normal(terminal_header_info):
                continue
            # Same-side multi-endpoint remains soft review only (geometry ambiguous).
            issues.append(
                context.issue_factory.build(
                    "R-ONE-TO-MANY",
                    "review",
                    pair=first,
                    message=f"Terminal header table logical endpoint {left_value} maps to multiple terminal endpoints on the same row.",
                    title="端子表多端点行映射待复核",
                    explanation="同页 terminal_header_table 表格映射中，同一表头逻辑端在同一侧列关联多个端子文本，几何位置不够明确，需要按表格行复核。",
                    recommended_action="核对端子表表头、行号、端子列和端子文本坐标，确认这些端点是否属于同一表格行的多端映射。",
                    related_pairs=linked_pairs,
                    extra={
                        "conflicting_values": sorted(rights),
                        "sheet_ids": sorted(sheet_ids),
                        "one_to_many_classification": "terminal_header_table_multi_endpoint_review",
                        **terminal_header_info,
                    },
                )
            )
            continue

        split_endpoint_info = _strip_two_port_component_split_endpoint_info(linked_pairs)
        if split_endpoint_info is not None:
            issues.append(
                context.issue_factory.build(
                    "R-ONE-TO-MANY",
                    "review",
                    pair=first,
                    message=f"Left value {left_value} maps to multiple endpoints split from the same component text.",
                    title="组件逗号端点拆分待复核",
                    explanation=(
                        "同页 strip_two_port_component 组件映射中，同一组件端子关联的多个邻接端来自逗号分隔文本拆分。"
                        "这通常表示同一标注文本内列出了多个邻接端，应按组件端口和原始文本一起复核。"
                    ),
                    recommended_action="核对组件本体、端口、原始逗号文本和拆分端点，确认这些拆分端是否都属于同一组件邻接关系。",
                    related_pairs=linked_pairs,
                    extra={
                        "conflicting_values": sorted(rights),
                        "sheet_ids": sorted(sheet_ids),
                        "one_to_many_classification": "component_split_endpoint_group_review",
                        **split_endpoint_info,
                    },
                )
            )
            continue

        if _is_same_sheet_strip_two_port_component_mapping(linked_pairs):
            issues.append(
                context.issue_factory.build(
                    "R-ONE-TO-MANY",
                    "review",
                    pair=first,
                    message=f"Left value {left_value} maps to multiple strip two-port component endpoints on the same page.",
                    title="组件端子分支映射待复核",
                    explanation="同页 strip_two_port_component 组件映射中，同一组件端子关联多个邻接端点，更可能表示组件分支/邻接关系，需要按组件上下文复核。",
                    recommended_action="核对组件本体、端子标注和相邻连接关系，确认这些端点是否属于同一组件分支映射。",
                    related_pairs=linked_pairs,
                    extra={
                        "conflicting_values": sorted(rights),
                        "sheet_ids": sorted(sheet_ids),
                        "one_to_many_classification": "component_branch_review",
                        "component_submode": "strip_two_port_component",
                    },
                )
            )
            continue

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
            if _is_authoritative_structured_cardinality_group(linked_pairs):
                continue
            terminal_header_info = _terminal_header_table_shared_endpoint_info(
                linked_pairs,
                right_value,
            )
            if terminal_header_info is not None:
                # Same physical terminal text (shared text_id/coords) claimed by
                # neighboring header rows is normal adjacent-column bridging on
                # terminal sheets (e.g. right of 1I16D3 and left of 1XD14 both
                # bind 1n102). Keep both table_mapping facts; not a conflict.
                if _is_terminal_header_shared_endpoint_normal(terminal_header_info):
                    continue
                sheet_ids = {pair.sheet_id for pair in linked_pairs}
                issues.append(
                    context.issue_factory.build(
                        "R-MANY-TO-ONE",
                        "review",
                        pair=first,
                        message=f"Terminal header table endpoint {right_value} is shared by multiple logical header rows.",
                        title="端子表共享端点待复核",
                        explanation="同页 terminal_header_table 表格映射中，多个表头逻辑端共享同一个端子文本，更可能是端子表跨列/跨表头的共享端点语义，需要按表格行列复核。",
                        recommended_action="核对相关表头、行号和共享端子文本坐标，确认这些逻辑端是否共同引用同一个端子列文本。",
                        related_pairs=linked_pairs,
                        extra={
                            "conflicting_values": sorted(lefts),
                            "sheet_ids": sorted(sheet_ids),
                            "many_to_one_classification": "terminal_header_table_shared_endpoint_review",
                            **terminal_header_info,
                        },
                    )
                )
                continue

            split_endpoint_info = _strip_two_port_component_split_endpoint_info(
                linked_pairs,
                require_same_sheet=False,
                shared_value=right_value,
            )
            if split_endpoint_info is not None:
                sheet_ids = {pair.sheet_id for pair in linked_pairs}
                issues.append(
                    context.issue_factory.build(
                        "R-MANY-TO-ONE",
                        "review",
                        pair=first,
                        message=f"Right value {right_value} is referenced by multiple component endpoints from comma-split text groups.",
                        title="组件逗号端点邻接待复核",
                        explanation=(
                            "同页 strip_two_port_component 组件映射中，共享邻接端来自一个或多个逗号分隔端点组。"
                            "这更像组件链路中的拆分端点邻接关系，需要按原始文本组和组件端口复核。"
                        ),
                        recommended_action="核对共享端点、逗号原始文本、组件本体和端口序号，确认这些入口是否属于同一组件链路邻接。",
                        related_pairs=linked_pairs,
                        extra={
                            "conflicting_values": sorted(lefts),
                            "sheet_ids": sorted(sheet_ids),
                            "many_to_one_classification": "component_split_endpoint_group_review",
                            **split_endpoint_info,
                        },
                    )
                )
                continue

            if _is_same_sheet_strip_two_port_component_mapping(linked_pairs):
                sheet_ids = {pair.sheet_id for pair in linked_pairs}
                issues.append(
                    context.issue_factory.build(
                        "R-MANY-TO-ONE",
                        "review",
                        pair=first,
                        message=f"Right value {right_value} receives multiple strip two-port component endpoints on the same page.",
                        title="组件端子多入口映射待复核",
                        explanation="同页 strip_two_port_component 组件映射中，多个组件端子指向同一邻接端点，可能是组件端子多入口/邻接映射，需要按组件上下文复核。",
                        recommended_action="核对组件本体、端子标注和相邻连接关系，确认这些入口是否属于同一组件邻接映射。",
                        related_pairs=linked_pairs,
                        extra={
                            "conflicting_values": sorted(lefts),
                            "sheet_ids": sorted(sheet_ids),
                            "many_to_one_classification": "component_branch_review",
                            "component_submode": "strip_two_port_component",
                        },
                    )
                )
                continue

            structured_scope_info = _structured_mapping_shared_endpoint_scope_info(
                linked_pairs,
                shared_value=right_value,
            )
            if structured_scope_info is not None:
                sheet_ids = {pair.sheet_id for pair in linked_pairs}
                issue_text = _structured_mapping_shared_endpoint_issue_text(
                    right_value,
                    structured_scope_info,
                )
                issues.append(
                    context.issue_factory.build(
                        "R-MANY-TO-ONE",
                        "review",
                        pair=first,
                        message=issue_text["message"],
                        title=issue_text["title"],
                        explanation=issue_text["explanation"],
                        recommended_action=issue_text["recommended_action"],
                        related_pairs=linked_pairs,
                        extra={
                            "conflicting_values": sorted(lefts),
                            "sheet_ids": sorted(sheet_ids),
                            "many_to_one_classification": "backplate_structured_shared_endpoint_review",
                            **structured_scope_info,
                        },
                    )
                )
                continue

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
            if _is_authoritative_structured_cardinality_group(linked_pairs):
                continue
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
        if _high_confidence_source_eligible(pair)
        if pair.left_value
        and pair.right_value
        and (
            (pair.confidence >= context.high_threshold and (pair.status == "pass" or pair.confidence_bucket == "high"))
            or _structured_source_kind(pair) == "table_mapping"
        )
    ]


def _high_confidence_source_eligible(pair: Pair) -> bool:
    if _structured_source_kind(pair) in _HIGH_CONFIDENCE_STRUCTURED_SOURCES:
        return True
    return _ordinary_pair_eligible(pair)


def _is_backplate_virtual_table_scope_review(linked_pairs: list[Pair]) -> bool:
    if not linked_pairs:
        return False
    for pair in linked_pairs:
        if getattr(pair, "pair_kind", "ordinary_pair") != "table_mapping":
            return False
        mapping = _table_mapping_evidence(pair)
        if mapping.get("mapping_mode") != "backplate_virtual_table":
            return False
    return True


def _is_authoritative_table_mapping_group(linked_pairs: list[Pair]) -> bool:
    """Recognize complete table facts that need no generic graph review."""

    if not linked_pairs:
        return False
    scope_keys: set[tuple[str, ...]] = set()
    for pair in linked_pairs:
        if getattr(pair, "pair_kind", "ordinary_pair") != "table_mapping":
            return False
        mapping = _table_mapping_evidence(pair)
        mapping_mode = str(mapping.get("mapping_mode") or "")
        if mapping_mode not in {"backplate_virtual_table", "terminal_header_table"}:
            return False
        row_sequence_valid = mapping.get("row_number_sequence_valid")
        if not (row_sequence_valid is True or row_sequence_valid == 1):
            return False
        if str(mapping.get("sheet_id") or "") != str(pair.sheet_id or ""):
            return False
        if str(mapping.get("logical_endpoint") or "") != str(pair.left_value or ""):
            return False
        mapped_endpoint = mapping.get("right_value") or mapping.get("left_value")
        if str(mapped_endpoint or "") != str(pair.right_value or ""):
            return False
        if not all(
            mapping.get(key)
            for key in (
                "header_prefix",
                "header_text_id",
                "middle_text_id",
            )
        ):
            return False
        if mapping.get("row_number") is None:
            return False
        column_roles = mapping.get("column_roles")
        if not isinstance(column_roles, dict):
            return False
        if mapping_mode == "backplate_virtual_table":
            if not mapping.get("source_block_name") or not mapping.get("right_text_id"):
                return False
            if column_roles.get("middle") != "virtual_row_number":
                return False
            if column_roles.get("right") != "external_terminal_endpoint":
                return False
            scope_keys.add(
                (
                    mapping_mode,
                    str(pair.sheet_id or ""),
                    str(pair.file_id or ""),
                    str(mapping.get("source_block_name") or ""),
                )
            )
        else:
            if column_roles.get("middle") != "row_number":
                return False
            left_is_endpoint = (
                bool(mapping.get("left_text_id"))
                and not mapping.get("right_text_id")
                and column_roles.get("left") == "terminal_endpoint"
                and column_roles.get("right") == "empty"
            )
            right_is_endpoint = (
                bool(mapping.get("right_text_id"))
                and not mapping.get("left_text_id")
                and column_roles.get("right") == "terminal_endpoint"
                and column_roles.get("left") == "empty"
            )
            if not (left_is_endpoint or right_is_endpoint):
                return False
            scope_keys.add(
                (
                    mapping_mode,
                    str(pair.sheet_id or ""),
                    str(pair.file_id or ""),
                    str(mapping.get("header_prefix") or ""),
                    str(mapping.get("header_text_id") or ""),
                )
            )
    return len(scope_keys) == 1


def _is_authoritative_structured_cardinality_group(linked_pairs: list[Pair]) -> bool:
    return _is_authoritative_table_mapping_group(
        linked_pairs
    ) or _is_authoritative_comma_component_mapping_group(linked_pairs)


def _is_authoritative_comma_component_mapping_group(linked_pairs: list[Pair]) -> bool:
    """Accept complete component-chain facts sourced from comma endpoint groups."""

    if len(linked_pairs) < 2:
        return False
    has_comma_group = False
    for pair in linked_pairs:
        if getattr(pair, "pair_kind", "ordinary_pair") != "component_mapping":
            return False
        if pair.status != "pass" or float(pair.confidence or 0.0) < 0.95:
            return False
        evidence = pair.evidence or {}
        if evidence.get("source") != "component_mapping":
            return False
        if evidence.get("component_submode") != "strip_two_port_component":
            return False
        if str(evidence.get("logical_endpoint") or "") != str(pair.left_value or ""):
            return False
        if str(evidence.get("external_endpoint") or "") != str(pair.right_value or ""):
            return False
        if not all(
            evidence.get(key)
            for key in (
                "component_body",
                "component_body_text_id",
                "component_port",
                "component_port_text_id",
                "component_block_name",
                "external_endpoint_text_id",
                "line_group_id",
                "supporting_line_ids",
            )
        ):
            return False
        raw_endpoint = str(evidence.get("external_endpoint_raw") or "")
        split_endpoint = str(evidence.get("external_endpoint_split") or "")
        if not raw_endpoint or split_endpoint != str(pair.right_value or ""):
            return False
        if "," in raw_endpoint or "，" in raw_endpoint:
            has_comma_group = True
    return has_comma_group


def _structured_mapping_shared_endpoint_scope_info(
    linked_pairs: list[Pair],
    *,
    shared_value: str,
) -> dict[str, object] | None:
    if not linked_pairs:
        return None

    pair_kinds = {getattr(pair, "pair_kind", "ordinary_pair") for pair in linked_pairs}
    if not pair_kinds.issubset({"table_mapping", "component_mapping"}):
        return None

    table_modes: set[str] = set()
    component_submodes: set[str] = set()
    source_block_names: set[str] = set()
    header_prefixes: set[str] = set()
    logical_endpoints: set[str] = set()
    filenames: set[str] = set()
    for pair in linked_pairs:
        if pair.right_value != shared_value:
            return None
        if pair.left_value:
            logical_endpoints.add(str(pair.left_value))
        evidence = pair.evidence or {}
        filename = evidence.get("filename")
        if filename:
            filenames.add(str(filename))

        if getattr(pair, "pair_kind", "ordinary_pair") == "table_mapping":
            mapping = _table_mapping_evidence(pair)
            mode = mapping.get("mapping_mode")
            if isinstance(mode, str) and mode:
                table_modes.add(mode)
            source_block_name = mapping.get("source_block_name")
            if source_block_name:
                source_block_names.add(str(source_block_name))
            header_prefix = mapping.get("header_prefix")
            if header_prefix:
                header_prefixes.add(str(header_prefix))
        elif getattr(pair, "pair_kind", "ordinary_pair") == "component_mapping":
            submode = evidence.get("component_submode") or evidence.get("submode")
            if isinstance(submode, str) and submode:
                component_submodes.add(submode)

    if "backplate_virtual_table" in table_modes:
        structured_scope_kind = (
            "backplate_table_shared_endpoint"
            if pair_kinds == {"table_mapping"}
            else "backplate_table_component_shared_endpoint"
        )
        classification = "backplate_structured_shared_endpoint_review"
    elif (
        pair_kinds == {"component_mapping", "table_mapping"}
        and table_modes == {"terminal_header_table"}
    ):
        structured_scope_kind = "terminal_header_component_shared_endpoint"
        classification = "terminal_header_component_shared_endpoint_review"
    else:
        return None

    result: dict[str, object] = {
        "shared_endpoint": shared_value,
        "pair_kinds": sorted(str(kind) for kind in pair_kinds),
        "many_to_one_classification": classification,
        "structured_scope_kind": structured_scope_kind,
        "logical_endpoints": sorted(logical_endpoints),
    }
    if table_modes:
        result["table_mapping_modes"] = sorted(table_modes)
    if component_submodes:
        result["component_submodes"] = sorted(component_submodes)
    if source_block_names:
        result["source_block_names"] = sorted(source_block_names)
    if header_prefixes:
        result["header_prefixes"] = sorted(header_prefixes)
    if filenames:
        result["filenames"] = sorted(filenames)
    return result


def _structured_mapping_shared_endpoint_issue_text(
    shared_value: str,
    structured_scope_info: dict[str, object],
) -> dict[str, str]:
    structured_scope_kind = structured_scope_info.get("structured_scope_kind")
    if structured_scope_kind == "backplate_table_shared_endpoint":
        return {
            "message": f"Backplate table mappings share endpoint {shared_value} across table scopes.",
            "title": "背板表格共享端点待复核",
            "explanation": (
                "多个背板虚拟表格或端子表结构化映射共同指向同一个外部端点。"
                "这通常是表格作用域、表头或行号复用造成的结构化共享端点现象，"
                "应按表格证据复核，而不是按普通线端多对一直接解释。"
            ),
            "recommended_action": "核对共享端点、背板表格行、端子表行、source block 和表头前缀，确认这些表格关系是否共同引用同一物理端子。",
        }
    if structured_scope_kind == "terminal_header_component_shared_endpoint":
        return {
            "message": f"Terminal header table and component mappings share endpoint {shared_value}.",
            "title": "端子表组件共享端点待复核",
            "explanation": (
                "端子表 terminal_header_table 映射与元件端口 component_mapping 共同指向同一个端点。"
                "这通常表示端子表行与元件端口在同一接线端汇合，应按结构化证据复核，"
                "而不是按普通线端多对一直接解释。"
            ),
            "recommended_action": "核对共享端点、端子表表头/行号、组件本体和端口序号，确认这些结构化关系是否共同引用同一物理端子。",
        }
    return {
        "message": f"Backplate structured mappings share endpoint {shared_value} across table/component scopes.",
        "title": "背板结构化端点汇合待复核",
        "explanation": (
            "背板虚拟表格与其他结构化 table/component 映射共同指向同一个外部端点。"
            "这通常是背板表格、端子表或元件端口在同一物理端子处汇合的作用域现象，"
            "应按结构化证据复核，而不是按普通线端多对一直接解释。"
        ),
        "recommended_action": "核对共享端点、背板表格行、端子表行和元件端口，确认这些结构化关系是否共同引用同一物理端子。",
    }


def _backplate_virtual_table_same_sheet_scope_info(linked_pairs: list[Pair]) -> dict[str, object] | None:
    if not linked_pairs:
        return None
    if len({pair.sheet_id for pair in linked_pairs}) != 1:
        return None
    if not _is_backplate_virtual_table_scope_review(linked_pairs):
        return None

    mappings = [_table_mapping_evidence(pair) for pair in linked_pairs]
    source_block_names = _sorted_mapping_values(mappings, "source_block_name")
    header_prefixes = _sorted_mapping_values(mappings, "header_prefix")
    raw_header_texts = _sorted_mapping_values(mappings, "raw_header_text")
    header_text_ids = _sorted_mapping_values(mappings, "header_text_id")
    header_coords = sorted(
        {
            _format_coord(mapping.get("header_coord"))
            for mapping in mappings
            if _format_coord(mapping.get("header_coord")) is not None
        }
    )
    row_numbers = sorted(
        {
            str(mapping.get("row_number"))
            for mapping in mappings
            if mapping.get("row_number") is not None
        }
    )

    # Same-sheet backplate fanout is only treated as scope review when there is
    # evidence of multiple table regions or block/header scopes.
    scope_variants = [
        len(source_block_names),
        len(raw_header_texts),
        len(header_text_ids),
        len(header_coords),
    ]
    if max(scope_variants, default=0) <= 1:
        return None

    semantic_notes = sorted(
        {
            str(note)
            for mapping in mappings
            for note in (
                mapping.get("semantic_notes")
                if isinstance(mapping.get("semantic_notes"), list)
                else []
            )
            if note is not None
        }
    )
    result: dict[str, object] = {
        "table_mapping_mode": "backplate_virtual_table",
        "backplate_scope_kind": "same_sheet_virtual_table",
        "source_block_names": source_block_names,
        "header_prefixes": header_prefixes,
        "raw_header_texts": raw_header_texts,
        "header_text_ids": header_text_ids,
        "header_coords": header_coords,
        "row_numbers": row_numbers,
    }
    if semantic_notes:
        result["semantic_notes"] = semantic_notes
    return result


def _sorted_mapping_values(mappings: list[dict[str, object]], key: str) -> list[str]:
    return sorted({str(mapping.get(key)) for mapping in mappings if mapping.get(key) is not None})


def _format_coord(value: object) -> str | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    x, y = value
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return f"{x:.3f},{y:.3f}"


def _table_mapping_evidence(pair: Pair) -> dict[str, object]:
    evidence = pair.evidence or {}
    table_mapping = evidence.get("table_mapping")
    if isinstance(table_mapping, dict):
        return table_mapping
    return {}


def _ordinary_pair_eligible(pair: Pair) -> bool:
    if getattr(pair, "pair_kind", "ordinary_pair") != "ordinary_pair":
        return False
    return pair.evidence.get("ordinary_pair_eligible", True) is not False


def _structured_source_kind(pair: Pair) -> str | None:
    source = pair.evidence.get("source")
    if isinstance(source, str) and source in _HIGH_CONFIDENCE_STRUCTURED_SOURCES:
        return source
    pair_kind = getattr(pair, "pair_kind", "ordinary_pair")
    if isinstance(pair_kind, str) and pair_kind in _HIGH_CONFIDENCE_STRUCTURED_SOURCES:
        return pair_kind
    return None


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
                filename=sheet.filename,
                sheet_no=sheet.sheet_no,
                sheet_order=sheet.sheet_order,
                rationale="filename_title_block_page_mismatch",
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


def _is_same_sheet_strip_two_port_component_mapping(linked_pairs: list[Pair]) -> bool:
    if not linked_pairs:
        return False
    if len({pair.sheet_id for pair in linked_pairs}) != 1:
        return False
    return all(
        pair.pair_kind == "component_mapping"
        and (pair.evidence or {}).get("component_submode") == "strip_two_port_component"
        for pair in linked_pairs
    )


def _strip_two_port_component_split_endpoint_info(
    linked_pairs: list[Pair],
    *,
    require_same_sheet: bool = True,
    shared_value: str | None = None,
) -> dict[str, object] | None:
    if not linked_pairs:
        return None
    if require_same_sheet and len({pair.sheet_id for pair in linked_pairs}) != 1:
        return None
    if not all(
        pair.pair_kind == "component_mapping"
        and (pair.evidence or {}).get("component_submode") == "strip_two_port_component"
        for pair in linked_pairs
    ):
        return None

    split_mappings: list[dict[str, object]] = []
    for pair in linked_pairs:
        evidence = pair.evidence or {}
        raw_value = evidence.get("external_endpoint_raw")
        split_value = evidence.get("external_endpoint_split")
        if not isinstance(raw_value, str) or "," not in raw_value:
            continue
        if not isinstance(split_value, str) or not split_value:
            continue
        if shared_value is not None and pair.right_value != shared_value:
            continue
        split_mappings.append(evidence)

    if not split_mappings:
        return None

    if shared_value is None:
        raw_text_ids = {
            str(mapping.get("external_endpoint_text_id"))
            for mapping in split_mappings
            if mapping.get("external_endpoint_text_id")
        }
        raw_values = {
            str(mapping.get("external_endpoint_raw"))
            for mapping in split_mappings
            if mapping.get("external_endpoint_raw")
        }
        if len(split_mappings) < 2 or (len(raw_text_ids) != 1 and len(raw_values) != 1):
            return None

    result: dict[str, object] = {
        "component_submode": "strip_two_port_component",
        "component_branch_kind": "split_endpoint_group",
        "external_endpoint_splits": sorted(
            {
                str(mapping.get("external_endpoint_split"))
                for mapping in split_mappings
                if mapping.get("external_endpoint_split")
            }
        ),
        "external_endpoint_raw_values": sorted(
            {
                str(mapping.get("external_endpoint_raw"))
                for mapping in split_mappings
                if mapping.get("external_endpoint_raw")
            }
        ),
    }
    text_ids = sorted(
        {
            str(mapping.get("external_endpoint_text_id"))
            for mapping in split_mappings
            if mapping.get("external_endpoint_text_id")
        }
    )
    if text_ids:
        result["external_endpoint_text_ids"] = text_ids
    logical_endpoints = sorted(
        {
            str(mapping.get("logical_endpoint"))
            for mapping in split_mappings
            if mapping.get("logical_endpoint")
        }
    )
    if logical_endpoints:
        result["logical_endpoints"] = logical_endpoints
    if shared_value is not None:
        result["shared_endpoint"] = shared_value
    return result


def _is_terminal_header_dual_endpoint_normal(info: dict[str, object]) -> bool:
    """Same-row left+right dual endpoints are structured terminal-sheet facts."""

    endpoint_columns = {
        str(value)
        for value in (info.get("endpoint_columns") or [])
        if value is not None and str(value)
    }
    return "left_endpoint" in endpoint_columns and "right_endpoint" in endpoint_columns


def _is_terminal_header_shared_endpoint_normal(info: dict[str, object]) -> bool:
    """Same physical text shared across header rows is adjacent-column bridging."""

    text_ids = [
        value
        for value in (info.get("shared_endpoint_text_ids") or [])
        if value is not None and str(value)
    ]
    coords = [
        value
        for value in (info.get("shared_endpoint_coords") or [])
        if value is not None
    ]
    # Detector already requires a single text_id or coordinate; treat that as
    # authoritative shared-label geometry, not many-to-one conflict.
    return bool(text_ids) or bool(coords)


def _terminal_header_table_multi_endpoint_info(
    linked_pairs: list[Pair],
) -> dict[str, object] | None:
    if not linked_pairs:
        return None
    if len({pair.sheet_id for pair in linked_pairs}) != 1:
        return None

    mappings: list[dict[str, object]] = []
    for pair in linked_pairs:
        if pair.pair_kind != "table_mapping":
            return None
        mapping = _table_mapping_evidence(pair)
        if mapping.get("mapping_mode") != "terminal_header_table":
            return None
        if mapping.get("row_number_sequence_valid") is False:
            return None
        mappings.append(mapping)

    logical_endpoints = {
        str(mapping.get("logical_endpoint"))
        for mapping in mappings
        if mapping.get("logical_endpoint")
    }
    row_numbers = {
        str(mapping.get("row_number"))
        for mapping in mappings
        if mapping.get("row_number") is not None
    }
    header_prefixes = {
        str(mapping.get("header_prefix"))
        for mapping in mappings
        if mapping.get("header_prefix")
    }
    if len(logical_endpoints) != 1 or len(row_numbers) != 1:
        return None

    endpoint_columns: set[str] = set()
    endpoint_values: set[str] = set()
    for mapping in mappings:
        if mapping.get("left_value"):
            endpoint_columns.add("left_endpoint")
            endpoint_values.add(str(mapping.get("left_value")))
        if mapping.get("right_value"):
            endpoint_columns.add("right_endpoint")
            endpoint_values.add(str(mapping.get("right_value")))
    if len(endpoint_values) < 2:
        return None

    result: dict[str, object] = {
        "table_mapping_mode": "terminal_header_table",
        "terminal_header_table_classification": "multi_endpoint_row_review",
        "logical_endpoint": next(iter(logical_endpoints)),
        "row_number": next(iter(row_numbers)),
        "endpoint_columns": sorted(endpoint_columns),
        "terminal_header_table_endpoint_values": sorted(endpoint_values),
    }
    if len(header_prefixes) == 1:
        result["header_prefix"] = next(iter(header_prefixes))
    return result


def _terminal_header_table_shared_endpoint_info(
    linked_pairs: list[Pair],
    shared_value: str,
) -> dict[str, object] | None:
    if not linked_pairs:
        return None
    if len({pair.sheet_id for pair in linked_pairs}) != 1:
        return None

    header_prefixes: set[str] = set()
    logical_endpoints: set[str] = set()
    row_numbers: set[str] = set()
    endpoint_columns: set[str] = set()
    endpoint_text_ids: set[str] = set()
    endpoint_coords: set[tuple[float, float]] = set()
    for pair in linked_pairs:
        if pair.pair_kind != "table_mapping":
            return None
        mapping = _table_mapping_evidence(pair)
        if mapping.get("mapping_mode") != "terminal_header_table":
            return None
        if mapping.get("row_number_sequence_valid") is False:
            return None

        if mapping.get("header_prefix"):
            header_prefixes.add(str(mapping.get("header_prefix")))
        if mapping.get("logical_endpoint"):
            logical_endpoints.add(str(mapping.get("logical_endpoint")))
        if mapping.get("row_number") is not None:
            row_numbers.add(str(mapping.get("row_number")))

        matched_column: str | None = None
        if mapping.get("left_value") == shared_value:
            matched_column = "left_endpoint"
            text_id = mapping.get("left_text_id")
            coord = mapping.get("left_coord")
        elif mapping.get("right_value") == shared_value:
            matched_column = "right_endpoint"
            text_id = mapping.get("right_text_id")
            coord = mapping.get("right_coord")
        else:
            return None

        endpoint_columns.add(matched_column)
        if text_id:
            endpoint_text_ids.add(str(text_id))
        if isinstance(coord, (list, tuple)) and len(coord) >= 2:
            endpoint_coords.add((round(float(coord[0]), 3), round(float(coord[1]), 3)))

    if len(logical_endpoints) <= 1:
        return None
    if len(endpoint_text_ids) > 1 or len(endpoint_coords) > 1:
        return None
    if not endpoint_text_ids and not endpoint_coords:
        return None

    result: dict[str, object] = {
        "table_mapping_mode": "terminal_header_table",
        "terminal_header_table_classification": "shared_endpoint_review",
        "shared_endpoint": shared_value,
        "logical_endpoints": sorted(logical_endpoints),
        "row_numbers": sorted(row_numbers),
        "endpoint_columns": sorted(endpoint_columns),
    }
    if header_prefixes:
        result["header_prefixes"] = sorted(header_prefixes)
    if endpoint_text_ids:
        result["shared_endpoint_text_ids"] = sorted(endpoint_text_ids)
    if endpoint_coords:
        result["shared_endpoint_coords"] = [list(coord) for coord in sorted(endpoint_coords)]
    return result


def _semantic_mapping_terminal_value(pair: Pair) -> str | None:
    if pair.left_value:
        return str(pair.left_value)
    if pair.right_value:
        return str(pair.right_value)
    return None


def _semantic_mapping_terminal_scope_key(pair: Pair, terminal_value: str) -> str:
    evidence = pair.evidence if isinstance(pair.evidence, dict) else {}
    raw_text_keys = (
        "selected_left_raw_text" if pair.left_value else None,
        "selected_right_raw_text" if pair.right_value else None,
        "selected_left_raw_text",
        "selected_right_raw_text",
    )
    for key in raw_text_keys:
        if not key:
            continue
        raw_text = evidence.get(key)
        if not isinstance(raw_text, str):
            continue
        normalized = _normalize_semantic_terminal_scope(raw_text, terminal_value)
        if normalized:
            return normalized
    return str(terminal_value)


def _normalize_semantic_terminal_scope(raw_text: str, terminal_value: str) -> str | None:
    text = re.sub(r"\s+", "", raw_text).upper()
    if not text:
        return None
    terminal = str(terminal_value).strip().upper()
    if not terminal:
        return None
    match = re.search(rf"[A-Z0-9\-]*N{re.escape(terminal)}\b", text)
    if match:
        return match.group(0)
    if text == terminal:
        return None
    if text.endswith(terminal):
        return text
    return None


def _normalized_semantic_endpoints(pair: Pair) -> set[str]:
    evidence = pair.evidence or {}
    marker_texts = evidence.get("semantic_marker_texts")
    if not isinstance(marker_texts, list):
        return set()

    endpoints: set[str] = set()
    for marker_text in marker_texts:
        if not isinstance(marker_text, str):
            continue
        normalized = _normalize_semantic_endpoint(marker_text)
        if normalized:
            endpoints.add(normalized)
    return endpoints


def _normalize_semantic_endpoint(marker_text: str) -> str | None:
    for pattern in _SEMANTIC_ENDPOINT_PATTERNS:
        match = pattern.search(marker_text)
        if match:
            return match.group(1).upper()
    return None


def _semantic_conflict_primary_pair(pairs: list[Pair]) -> Pair:
    return sorted(
        pairs,
        key=lambda pair: (
            _sheet_order_key(pair),
            pair.pair_id,
        ),
    )[0]


def _sheet_order_key(sheet_or_pair) -> int:
    if isinstance(sheet_or_pair, SheetRecord):
        return int(sheet_or_pair.sheet_order or 0)
    if isinstance(sheet_or_pair, Pair):
        evidence = sheet_or_pair.evidence or {}
        sheet_order = evidence.get("sheet_order")
        if isinstance(sheet_order, int):
            return sheet_order
        try:
            return int(sheet_order)
        except (TypeError, ValueError):
            return 0
    return 0


def _table_mapping_source_kind(pair: Pair) -> str:
    if pair.evidence.get("source") == "table_mapping":
        return "table_mapping"
    if getattr(pair, "pair_kind", "ordinary_pair") == "ordinary_pair":
        return "ordinary_pair"
    return getattr(pair, "pair_kind", "ordinary_pair")


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
        rule_id="R-SEMANTIC-MAPPING-CONFLICT",
        name="Semantic Mapping Conflict",
        description="The same terminal value maps to different normalized semantic endpoints across sheets.",
        severity_default="review",
        runner=_run_semantic_mapping_conflict,
        input_tables=("pairs", "pages"),
        output_issue_type="semantic_mapping_conflict",
    ),
    AuditRule(
        rule_id="R-TABLE-MAPPING-SOURCE-CONFLICT",
        name="Table Mapping Source Conflict",
        description="Table-mapping evidence conflicts with ordinary terminal mapping for the same left value.",
        severity_default="major",
        runner=_run_table_mapping_source_conflict,
        input_tables=("pairs", "pages"),
        output_issue_type="table_mapping_source_conflict",
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
