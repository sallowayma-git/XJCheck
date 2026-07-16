from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable

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

_PAIR_SCOPED_RULES = frozenset(
    {
        "R-PAIR-MISSING-SIDE",
        "R-PAIR-LOW-CONFIDENCE",
        "R-DUPLICATE-SAME-LINE",
    }
)


@dataclass(slots=True)
class IssueFactory:
    issue_ids: IdFactory
    group_map: dict[str, LineGroup]
    sheet_map: dict[str, SheetRecord]

    def build(
        self,
        rule_id: str,
        severity: str,
        pair: Pair,
        message: str,
        title: str | None = None,
        explanation: str | None = None,
        recommended_action: str | None = None,
        related_pairs: list[Pair] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Issue:
        group = self.group_map.get(pair.line_group_id)
        sheet = self.sheet_map.get(pair.sheet_id)
        evidence = {
            "pair_id": pair.pair_id,
            "line_group_id": pair.line_group_id,
            "left_value": pair.left_value,
            "right_value": pair.right_value,
            "confidence": pair.confidence,
            "filename": sheet.filename if sheet else None,
            "sheet_no": sheet.sheet_no if sheet else None,
            "sheet_title": sheet.sheet_title if sheet else None,
            "sheet_order": sheet.sheet_order if sheet else None,
            "page_no_source": sheet.page_no_source if sheet else None,
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
            related_sheet = self.sheet_map.get(related_pair.sheet_id)
            related_group = self.group_map.get(related_pair.line_group_id)
            evidence_refs.append(
                {
                    "pair_id": related_pair.pair_id,
                    "sheet_id": related_pair.sheet_id,
                    "filename": related_sheet.filename if related_sheet else None,
                    "sheet_no": related_sheet.sheet_no if related_sheet else None,
                    "sheet_title": related_sheet.sheet_title if related_sheet else None,
                    "sheet_order": related_sheet.sheet_order if related_sheet else None,
                    "line_group_id": related_pair.line_group_id,
                    "line_start": (
                        [related_group.start_x, related_group.start_y] if related_group else None
                    ),
                    "line_end": (
                        [related_group.end_x, related_group.end_y] if related_group else None
                    ),
                }
            )

        values = [value for value in {pair.left_value, pair.right_value} if value]
        if extra:
            values.extend(str(value) for value in extra.get("conflicting_values", []) if value)

        from dwg_audit.audit.issue_triage import RULE_ISSUE_TYPES

        return Issue(
            issue_id=self.issue_ids.next(),
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
            filename=sheet.filename if sheet else None,
            sheet_no=sheet.sheet_no if sheet else None,
            sheet_order=sheet.sheet_order if sheet else None,
            rationale=pair.rationale,
            evidence=evidence,
            issue_type=RULE_ISSUE_TYPES.get(rule_id, rule_id),
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


@dataclass(slots=True)
class RuleContext:
    pairs: list[Pair]
    line_groups: list[LineGroup]
    sheets: list[SheetRecord]
    config: dict
    terminal_candidates: list[TerminalCandidate]
    high_threshold: float
    duplicate_delta: float
    reciprocal_required: bool
    group_map: dict[str, LineGroup]
    sheet_map: dict[str, SheetRecord]
    issue_factory: IssueFactory = field(repr=False)


RuleRunner = Callable[[RuleContext], list[Issue]]


@dataclass(frozen=True, slots=True)
class AuditRule:
    rule_id: str
    name: str
    description: str
    severity_default: str
    runner: RuleRunner
    input_tables: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()
    output_issue_type: str | None = None


def select_rules(registry: list[AuditRule], enabled_rule_ids: set[str]) -> list[AuditRule]:
    return [rule for rule in registry if rule.rule_id in enabled_rule_ids]


def cluster_issues(issues: list[Issue]) -> list[Issue]:
    clustered: list[Issue] = []
    index_by_key: dict[tuple[Any, ...], int] = {}
    for issue in issues:
        if _is_grid_row_band_endpoint_gap_aggregation_issue(issue):
            key = _grid_row_band_endpoint_gap_cluster_key(issue)
            existing_index = index_by_key.get(key)
            if existing_index is None:
                index_by_key[key] = len(clustered)
                clustered.append(issue)
                continue
            clustered[existing_index] = _merge_issue_cluster(clustered[existing_index], issue)
            continue

        if _is_backplate_scope_aggregation_issue(issue):
            key = _backplate_scope_cluster_key(issue)
            existing_index = index_by_key.get(key)
            if existing_index is None:
                index_by_key[key] = len(clustered)
                clustered.append(issue)
                continue
            clustered[existing_index] = _merge_issue_cluster(clustered[existing_index], issue)
            continue

        if _is_backplate_same_sheet_scope_aggregation_issue(issue):
            existing_index = _find_backplate_same_sheet_scope_cluster(clustered, issue)
            if existing_index is None:
                clustered.append(issue)
                continue
            clustered[existing_index] = _merge_issue_cluster(clustered[existing_index], issue)
            continue

        if _is_terminal_header_table_aggregation_issue(issue):
            existing_index = _find_terminal_header_table_cluster(clustered, issue)
            if existing_index is None:
                clustered.append(issue)
                continue
            clustered[existing_index] = _merge_issue_cluster(clustered[existing_index], issue)
            continue

        if _is_backplate_structured_shared_endpoint_aggregation_issue(issue):
            key = _backplate_structured_shared_endpoint_cluster_key(issue)
            existing_index = index_by_key.get(key)
            if existing_index is None:
                index_by_key[key] = len(clustered)
                clustered.append(issue)
                continue
            clustered[existing_index] = _merge_issue_cluster(clustered[existing_index], issue)
            continue

        key = _issue_cluster_key(issue)
        existing_index = index_by_key.get(key)
        if existing_index is None:
            index_by_key[key] = len(clustered)
            clustered.append(issue)
            continue
        clustered[existing_index] = _merge_issue_cluster(clustered[existing_index], issue)
    return clustered


def _issue_cluster_key(issue: Issue) -> tuple[Any, ...]:
    if issue.rule_id in _PAIR_SCOPED_RULES:
        return (
            issue.rule_id,
            issue.primary_pair_id or issue.pair_id or issue.line_group_id or issue.issue_id,
        )
    if issue.rule_id in {"R-CROSS-PAGE-CONFLICT", "R-ONE-TO-MANY"}:
        return (issue.rule_id, issue.left_value or "")
    if issue.rule_id == "R-MANY-TO-ONE":
        return (issue.rule_id, issue.right_value or "")
    if issue.rule_id in {"R-MISSING-RECIPROCAL", "R-DUPLICATE-PAIR"}:
        return (issue.rule_id, issue.left_value or "", issue.right_value or "")
    return (
        issue.rule_id,
        issue.sheet_id or "",
        issue.file_id or "",
        issue.line_group_id or "",
        issue.left_value or "",
        issue.right_value or "",
    )


def _merge_issue_cluster(primary: Issue, duplicate: Issue) -> Issue:
    primary.confidence = max(primary.confidence, duplicate.confidence)

    primary_pair_id = primary.primary_pair_id or primary.pair_id
    pair_ids = {
        pair_id
        for pair_id in [
            primary_pair_id,
            duplicate.primary_pair_id,
            duplicate.pair_id,
            *primary.related_pair_ids,
            *duplicate.related_pair_ids,
        ]
        if pair_id
    }
    if primary_pair_id is None and pair_ids:
        primary.primary_pair_id = sorted(pair_ids)[0]
        primary_pair_id = primary.primary_pair_id
    primary.related_pair_ids = sorted(pair_id for pair_id in pair_ids if pair_id != primary_pair_id)

    sheet_ids = {
        sheet_id
        for sheet_id in [primary.sheet_id, duplicate.sheet_id, *primary.sheet_ids, *duplicate.sheet_ids]
        if sheet_id
    }
    primary.sheet_ids = sorted(sheet_ids)

    values = {
        value
        for value in [primary.left_value, primary.right_value, duplicate.left_value, duplicate.right_value, *primary.values, *duplicate.values]
        if value
    }
    primary.values = sorted(values)

    primary.evidence_refs = _dedupe_dict_records([*primary.evidence_refs, *duplicate.evidence_refs])

    evidence = dict(primary.evidence)
    evidence["cluster_size"] = int(evidence.get("cluster_size", 1)) + int(duplicate.evidence.get("cluster_size", 1))
    if pair_ids:
        evidence["cluster_pair_ids"] = sorted(pair_ids)
    if sheet_ids:
        evidence["cluster_sheet_ids"] = sorted(sheet_ids)
    _merge_terminal_header_table_cluster_evidence(evidence, duplicate.evidence)
    _merge_grid_row_band_endpoint_gap_evidence(evidence, primary, duplicate)
    _merge_backplate_scope_cluster_evidence(evidence, primary, duplicate)
    _merge_backplate_same_sheet_scope_cluster_evidence(evidence, primary, duplicate)
    _merge_backplate_structured_shared_endpoint_cluster_evidence(evidence, duplicate.evidence)
    primary.evidence = evidence
    _refresh_grid_row_band_endpoint_gap_issue(primary)
    _refresh_terminal_header_table_interval_issue(primary)
    _refresh_backplate_structured_shared_endpoint_issue(primary)
    return primary


def _refresh_grid_row_band_endpoint_gap_issue(issue: Issue) -> None:
    evidence = issue.evidence
    if not evidence.get("grid_row_band_endpoint_gap_review"):
        return
    row_band_id = evidence.get("row_band_id")
    endpoint_values = _as_list(evidence.get("aggregated_endpoint_values"))
    rule_ids = _as_list(evidence.get("aggregated_rule_ids"))
    cluster_size = int(evidence.get("cluster_size", 1))
    values_text = ", ".join(str(value) for value in endpoint_values) if endpoint_values else "unknown"
    rules_text = ", ".join(str(value) for value in rule_ids) if rule_ids else "grid endpoint rules"

    issue.title = "网格行带端点缺口待复核"
    issue.summary = (
        f"Grid row-band {row_band_id} has {cluster_size} endpoint-gap symptoms "
        f"across {rules_text}; values={values_text}."
    )
    issue.explanation = (
        "同一 grid row-band 内同时出现缺侧端点或同号低置信短线，说明当前普通 Pair 仍按线段局部解释，"
        "更像行带级端点配对/续接解释缺口。该聚合不生成新的端点关系，只把同一行带的重复症状收拢为一条可复核 review。"
    )
    issue.recommended_action = (
        "按聚合后的 row_band_id、cluster_pair_ids、line_group_id 和端点值复核该行带，"
        "再决定是否进入下一轮 WireDiagramExtractor row-band endpoint inference。"
    )


def _refresh_terminal_header_table_interval_issue(issue: Issue) -> None:
    evidence = issue.evidence
    if (
        evidence.get("one_to_many_classification")
        == "terminal_header_table_multi_endpoint_review"
        and evidence.get("terminal_header_table_row_band_review")
    ):
        logical_ranges = _as_list(evidence.get("aggregated_logical_endpoint_ranges"))
        endpoint_ranges = _as_list(
            evidence.get("aggregated_terminal_header_table_endpoint_ranges")
        )
        row_ranges = _as_list(evidence.get("aggregated_row_number_ranges"))
        if not logical_ranges or not endpoint_ranges:
            return
        issue.summary = (
            "Terminal header table row-band multi-endpoint review: "
            f"logical={', '.join(str(value) for value in logical_ranges)}; "
            f"endpoints={', '.join(str(value) for value in endpoint_ranges)}."
        )
        issue.explanation = (
            "同页 terminal_header_table 表格映射中，连续行带内多个表头逻辑端分别关联多个端子文本；"
            "这更像端子表行带级多端点语义，需要按区间复核，而不是逐行当成普通一对多错误。"
        )
        row_text = (
            f"；行号区间：{', '.join(str(value) for value in row_ranges)}"
            if row_ranges
            else ""
        )
        issue.recommended_action = (
            "按聚合后的 logical/terminal endpoint 区间核对表头、行号、端子列和端子文本坐标"
            f"{row_text}。"
        )
        return

    if not evidence.get("terminal_header_table_interval_review"):
        return
    if (
        evidence.get("many_to_one_classification")
        != "terminal_header_table_shared_endpoint_review"
    ):
        return

    logical_ranges = _as_list(evidence.get("aggregated_logical_endpoint_ranges"))
    shared_ranges = _as_list(evidence.get("aggregated_shared_endpoint_ranges"))
    row_ranges = _as_list(evidence.get("aggregated_row_number_ranges"))
    if not logical_ranges or not shared_ranges:
        return

    issue.summary = (
        "Terminal header table shared endpoints form contiguous intervals: "
        f"logical={', '.join(str(value) for value in logical_ranges)}; "
        f"shared={', '.join(str(value) for value in shared_ranges)}."
    )
    issue.explanation = (
        "同页 terminal_header_table 表格映射中，多个表头逻辑端按连续行号区间共享端子列文本；"
        "这更像端子表跨表头/跨列的结构化共享端点区间，需要按区间复核，而不是逐行当成普通多对一错误。"
    )
    row_text = f"；行号区间：{', '.join(str(value) for value in row_ranges)}" if row_ranges else ""
    issue.recommended_action = (
        "按聚合后的 logical/shared endpoint 区间核对表头、行号和共享端子文本坐标"
        f"{row_text}。"
    )


def _merge_terminal_header_table_cluster_evidence(
    primary_evidence: dict[str, Any],
    duplicate_evidence: dict[str, Any],
) -> None:
    if (
        primary_evidence.get("one_to_many_classification")
        == "terminal_header_table_multi_endpoint_review"
    ):
        primary_evidence["terminal_header_table_aggregate_review"] = True
        primary_evidence["aggregated_logical_endpoints"] = _merge_sorted_values(
            _as_list(primary_evidence.get("aggregated_logical_endpoints"))
            + _as_list(primary_evidence.get("logical_endpoint"))
            + _as_list(duplicate_evidence.get("aggregated_logical_endpoints"))
            + _as_list(duplicate_evidence.get("logical_endpoint"))
        )
        primary_evidence["aggregated_row_numbers"] = _merge_sorted_values(
            _as_list(primary_evidence.get("aggregated_row_numbers"))
            + _as_list(primary_evidence.get("row_number"))
            + _as_list(duplicate_evidence.get("aggregated_row_numbers"))
            + _as_list(duplicate_evidence.get("row_number"))
        )
        primary_evidence["aggregated_conflicting_values"] = _merge_sorted_values(
            _as_list(primary_evidence.get("aggregated_conflicting_values"))
            + _as_list(primary_evidence.get("conflicting_values"))
            + _as_list(duplicate_evidence.get("aggregated_conflicting_values"))
            + _as_list(duplicate_evidence.get("conflicting_values"))
        )
        primary_evidence["aggregated_terminal_header_table_endpoint_values"] = (
            _merge_sorted_values(
                _as_list(
                    primary_evidence.get("aggregated_terminal_header_table_endpoint_values")
                )
                + _as_list(primary_evidence.get("terminal_header_table_endpoint_values"))
                + _as_list(
                    duplicate_evidence.get("aggregated_terminal_header_table_endpoint_values")
                )
                + _as_list(duplicate_evidence.get("terminal_header_table_endpoint_values"))
            )
        )
        _add_terminal_header_multi_endpoint_range_evidence(primary_evidence)
        return

    if (
        primary_evidence.get("many_to_one_classification")
        == "terminal_header_table_shared_endpoint_review"
    ):
        primary_evidence["terminal_header_table_aggregate_review"] = True
        primary_evidence["aggregated_logical_endpoints"] = _merge_sorted_values(
            _as_list(primary_evidence.get("aggregated_logical_endpoints"))
            + _as_list(primary_evidence.get("logical_endpoints"))
            + _as_list(duplicate_evidence.get("aggregated_logical_endpoints"))
            + _as_list(duplicate_evidence.get("logical_endpoints"))
        )
        primary_evidence["aggregated_row_numbers"] = _merge_sorted_values(
            _as_list(primary_evidence.get("aggregated_row_numbers"))
            + _as_list(primary_evidence.get("row_numbers"))
            + _as_list(duplicate_evidence.get("aggregated_row_numbers"))
            + _as_list(duplicate_evidence.get("row_numbers"))
        )
        primary_evidence["aggregated_shared_endpoints"] = _merge_sorted_values(
            _as_list(primary_evidence.get("aggregated_shared_endpoints"))
            + _as_list(primary_evidence.get("shared_endpoint"))
            + _as_list(duplicate_evidence.get("aggregated_shared_endpoints"))
            + _as_list(duplicate_evidence.get("shared_endpoint"))
        )
        primary_evidence["aggregated_shared_endpoint_text_ids"] = _merge_sorted_values(
            _as_list(primary_evidence.get("aggregated_shared_endpoint_text_ids"))
            + _as_list(primary_evidence.get("shared_endpoint_text_ids"))
            + _as_list(duplicate_evidence.get("aggregated_shared_endpoint_text_ids"))
            + _as_list(duplicate_evidence.get("shared_endpoint_text_ids"))
        )
        primary_evidence["header_prefixes"] = _merge_sorted_values(
            _as_list(primary_evidence.get("header_prefixes"))
            + _as_list(duplicate_evidence.get("header_prefixes"))
        )
        _add_terminal_header_shared_endpoint_interval_evidence(primary_evidence)


def _add_terminal_header_shared_endpoint_interval_evidence(
    evidence: dict[str, Any],
) -> None:
    evidence["terminal_header_table_interval_review"] = True
    logical_ranges = _numeric_suffix_range_labels(
        _as_list(evidence.get("aggregated_logical_endpoints"))
        + _as_list(evidence.get("logical_endpoints"))
    )
    if logical_ranges:
        evidence["aggregated_logical_endpoint_ranges"] = logical_ranges

    shared_ranges = _numeric_suffix_range_labels(
        _as_list(evidence.get("aggregated_shared_endpoints"))
        + _as_list(evidence.get("shared_endpoint"))
    )
    if shared_ranges:
        evidence["aggregated_shared_endpoint_ranges"] = shared_ranges

    row_ranges = _integer_range_labels(
        _integer_values(
            _as_list(evidence.get("aggregated_row_numbers"))
            + _as_list(evidence.get("row_numbers"))
        )
    )
    if row_ranges:
        evidence["aggregated_row_number_ranges"] = row_ranges


def _add_terminal_header_multi_endpoint_range_evidence(
    evidence: dict[str, Any],
) -> None:
    evidence["terminal_header_table_row_band_review"] = True
    logical_ranges = _numeric_suffix_range_labels(
        _as_list(evidence.get("aggregated_logical_endpoints"))
        + _as_list(evidence.get("logical_endpoint"))
    )
    if logical_ranges:
        evidence["aggregated_logical_endpoint_ranges"] = logical_ranges

    endpoint_ranges = _numeric_suffix_range_labels(
        _as_list(evidence.get("aggregated_terminal_header_table_endpoint_values"))
        + _as_list(evidence.get("terminal_header_table_endpoint_values"))
        + _as_list(evidence.get("aggregated_conflicting_values"))
        + _as_list(evidence.get("conflicting_values"))
    )
    if endpoint_ranges:
        evidence["aggregated_terminal_header_table_endpoint_ranges"] = endpoint_ranges

    row_ranges = _integer_range_labels(
        _integer_values(
            _as_list(evidence.get("aggregated_row_numbers"))
            + _as_list(evidence.get("row_number"))
        )
    )
    if row_ranges:
        evidence["aggregated_row_number_ranges"] = row_ranges


def _is_terminal_header_table_aggregation_issue(issue: Issue) -> bool:
    if (
        issue.rule_id == "R-ONE-TO-MANY"
        and issue.evidence.get("one_to_many_classification")
        == "terminal_header_table_multi_endpoint_review"
    ):
        return True
    return (
        issue.rule_id == "R-MANY-TO-ONE"
        and issue.evidence.get("many_to_one_classification")
        == "terminal_header_table_shared_endpoint_review"
    )


def _is_grid_row_band_endpoint_gap_aggregation_issue(issue: Issue) -> bool:
    if issue.rule_id not in {"R-PAIR-MISSING-SIDE", "R-PAIR-LOW-CONFIDENCE"}:
        return False
    pair_evidence = _pair_evidence(issue)
    if pair_evidence.get("pair_kind") not in {None, "", "ordinary_pair"}:
        return False
    if pair_evidence.get("line_orientation") != "grid":
        return False
    row_band_id = _string_value(pair_evidence.get("row_band_id"))
    if not row_band_id:
        return False
    left_value = _string_value(issue.left_value)
    right_value = _string_value(issue.right_value)
    if issue.rule_id == "R-PAIR-MISSING-SIDE":
        return bool(left_value) != bool(right_value)
    return bool(left_value) and left_value == right_value and left_value.isdigit()


def _grid_row_band_endpoint_gap_cluster_key(issue: Issue) -> tuple[Any, ...]:
    pair_evidence = _pair_evidence(issue)
    return (
        "grid_row_band_endpoint_gap",
        issue.sheet_id or "",
        issue.file_id or "",
        _string_value(pair_evidence.get("row_band_id")),
    )


def _is_backplate_scope_aggregation_issue(issue: Issue) -> bool:
    return (
        issue.rule_id == "R-CROSS-PAGE-CONFLICT"
        and issue.evidence.get("one_to_many_classification")
        == "backplate_table_scope_review"
        and issue.evidence.get("table_mapping_mode") == "backplate_virtual_table"
    )


def _is_backplate_same_sheet_scope_aggregation_issue(issue: Issue) -> bool:
    return (
        issue.rule_id == "R-ONE-TO-MANY"
        and issue.evidence.get("one_to_many_classification")
        == "backplate_table_same_sheet_scope_review"
        and issue.evidence.get("table_mapping_mode") == "backplate_virtual_table"
    )


def _is_backplate_structured_shared_endpoint_aggregation_issue(issue: Issue) -> bool:
    return (
        issue.rule_id == "R-MANY-TO-ONE"
        and issue.evidence.get("many_to_one_classification")
        == "backplate_structured_shared_endpoint_review"
        and _is_real_line_group(issue.line_group_id)
        and "component_mapping" in _as_list(issue.evidence.get("pair_kinds"))
        and "backplate_virtual_table" in _as_list(issue.evidence.get("table_mapping_modes"))
    )


def _backplate_scope_cluster_key(issue: Issue) -> tuple[Any, ...]:
    return (
        issue.rule_id,
        issue.evidence.get("one_to_many_classification"),
        issue.evidence.get("table_mapping_mode"),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("header_prefixes")))),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("source_block_names")))),
    )


def _backplate_structured_shared_endpoint_cluster_key(issue: Issue) -> tuple[Any, ...]:
    return (
        issue.rule_id,
        issue.evidence.get("many_to_one_classification"),
        issue.sheet_id or "",
        issue.file_id or "",
        issue.line_group_id or "",
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("pair_kinds")))),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("table_mapping_modes")))),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("component_submodes")))),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("source_block_names")))),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("header_prefixes")))),
    )


def _backplate_same_sheet_scope_cluster_base_key(issue: Issue) -> tuple[Any, ...]:
    return (
        issue.rule_id,
        issue.evidence.get("one_to_many_classification"),
        issue.evidence.get("table_mapping_mode"),
        issue.sheet_id or "",
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("source_block_names")))),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("header_prefixes")))),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("raw_header_texts")))),
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("header_text_ids")))),
    )


def _merge_grid_row_band_endpoint_gap_evidence(
    evidence: dict[str, Any],
    primary: Issue,
    duplicate: Issue,
) -> None:
    if not (
        _is_grid_row_band_endpoint_gap_aggregation_issue(primary)
        and _is_grid_row_band_endpoint_gap_aggregation_issue(duplicate)
    ):
        return

    primary_pair_evidence = _pair_evidence(primary)
    duplicate_pair_evidence = _pair_evidence(duplicate)
    evidence["grid_row_band_endpoint_gap_review"] = True
    evidence["row_band_id"] = _string_value(primary_pair_evidence.get("row_band_id")) or _string_value(
        duplicate_pair_evidence.get("row_band_id")
    )
    evidence["line_orientation"] = "grid"
    evidence["aggregated_rule_ids"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_rule_ids"))
        + _as_list(primary.rule_id)
        + _as_list(duplicate.rule_id)
    )
    evidence["aggregated_endpoint_values"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_endpoint_values"))
        + _as_list(primary.left_value)
        + _as_list(primary.right_value)
        + _as_list(duplicate.left_value)
        + _as_list(duplicate.right_value)
    )
    evidence["aggregated_missing_sides"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_missing_sides"))
        + _grid_row_band_missing_sides(primary)
        + _grid_row_band_missing_sides(duplicate)
    )
    evidence["aggregated_line_group_ids"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_line_group_ids"))
        + _as_list(primary.line_group_id)
        + _as_list(duplicate.line_group_id)
    )
    evidence["aggregated_line_spans"] = _dedupe_dict_records(
        _as_list(evidence.get("aggregated_line_spans"))
        + [_grid_row_band_line_span(primary), _grid_row_band_line_span(duplicate)]
    )


def _grid_row_band_missing_sides(issue: Issue) -> list[str]:
    if issue.rule_id != "R-PAIR-MISSING-SIDE":
        return []
    missing: list[str] = []
    if not _string_value(issue.left_value):
        missing.append("left")
    if not _string_value(issue.right_value):
        missing.append("right")
    return missing


def _grid_row_band_line_span(issue: Issue) -> dict[str, Any]:
    return {
        "pair_id": issue.primary_pair_id or issue.pair_id,
        "line_group_id": issue.line_group_id,
        "rule_id": issue.rule_id,
        "left_value": issue.left_value,
        "right_value": issue.right_value,
        "confidence": issue.confidence,
        "line_start": issue.evidence.get("line_start"),
        "line_end": issue.evidence.get("line_end"),
    }


def _merge_backplate_scope_cluster_evidence(
    evidence: dict[str, Any],
    primary: Issue,
    duplicate: Issue,
) -> None:
    if (
        evidence.get("one_to_many_classification") != "backplate_table_scope_review"
        or evidence.get("table_mapping_mode") != "backplate_virtual_table"
    ):
        return

    evidence["backplate_scope_aggregate_review"] = True
    evidence["aggregated_logical_endpoints"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_logical_endpoints"))
        + _as_list(primary.left_value)
        + _as_list(duplicate.left_value)
    )
    evidence["aggregated_conflicting_values"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_conflicting_values"))
        + _as_list(evidence.get("conflicting_values"))
        + _as_list(duplicate.evidence.get("aggregated_conflicting_values"))
        + _as_list(duplicate.evidence.get("conflicting_values"))
    )
    evidence["source_block_names"] = _merge_sorted_values(
        _as_list(evidence.get("source_block_names"))
        + _as_list(duplicate.evidence.get("source_block_names"))
    )
    evidence["header_prefixes"] = _merge_sorted_values(
        _as_list(evidence.get("header_prefixes"))
        + _as_list(duplicate.evidence.get("header_prefixes"))
    )


def _merge_backplate_same_sheet_scope_cluster_evidence(
    evidence: dict[str, Any],
    primary: Issue,
    duplicate: Issue,
) -> None:
    if (
        evidence.get("one_to_many_classification")
        != "backplate_table_same_sheet_scope_review"
        or evidence.get("table_mapping_mode") != "backplate_virtual_table"
    ):
        return

    evidence["backplate_scope_aggregate_review"] = True
    evidence["aggregated_logical_endpoints"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_logical_endpoints"))
        + _as_list(primary.left_value)
        + _as_list(duplicate.left_value)
    )
    evidence["aggregated_row_numbers"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_row_numbers"))
        + _as_list(evidence.get("row_numbers"))
        + _as_list(duplicate.evidence.get("aggregated_row_numbers"))
        + _as_list(duplicate.evidence.get("row_numbers"))
    )
    evidence["aggregated_conflicting_values"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_conflicting_values"))
        + _as_list(evidence.get("conflicting_values"))
        + _as_list(duplicate.evidence.get("aggregated_conflicting_values"))
        + _as_list(duplicate.evidence.get("conflicting_values"))
    )
    evidence["source_block_names"] = _merge_sorted_values(
        _as_list(evidence.get("source_block_names"))
        + _as_list(duplicate.evidence.get("source_block_names"))
    )
    evidence["header_prefixes"] = _merge_sorted_values(
        _as_list(evidence.get("header_prefixes"))
        + _as_list(duplicate.evidence.get("header_prefixes"))
    )
    evidence["raw_header_texts"] = _merge_sorted_values(
        _as_list(evidence.get("raw_header_texts"))
        + _as_list(duplicate.evidence.get("raw_header_texts"))
    )
    evidence["header_text_ids"] = _merge_sorted_values(
        _as_list(evidence.get("header_text_ids"))
        + _as_list(duplicate.evidence.get("header_text_ids"))
    )


def _merge_backplate_structured_shared_endpoint_cluster_evidence(
    evidence: dict[str, Any],
    duplicate_evidence: dict[str, Any],
) -> None:
    if (
        evidence.get("many_to_one_classification")
        != "backplate_structured_shared_endpoint_review"
    ):
        return

    evidence["backplate_structured_shared_endpoint_aggregate_review"] = True
    evidence["aggregated_shared_endpoints"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_shared_endpoints"))
        + _as_list(evidence.get("shared_endpoint"))
        + _as_list(duplicate_evidence.get("aggregated_shared_endpoints"))
        + _as_list(duplicate_evidence.get("shared_endpoint"))
    )
    evidence["aggregated_shared_endpoint_ranges"] = _numeric_suffix_range_labels(
        _as_list(evidence.get("aggregated_shared_endpoints"))
    )
    evidence["aggregated_logical_endpoints"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_logical_endpoints"))
        + _as_list(evidence.get("logical_endpoints"))
        + _as_list(duplicate_evidence.get("aggregated_logical_endpoints"))
        + _as_list(duplicate_evidence.get("logical_endpoints"))
    )
    evidence["aggregated_conflicting_values"] = _merge_sorted_values(
        _as_list(evidence.get("aggregated_conflicting_values"))
        + _as_list(evidence.get("conflicting_values"))
        + _as_list(duplicate_evidence.get("aggregated_conflicting_values"))
        + _as_list(duplicate_evidence.get("conflicting_values"))
    )
    for key in (
        "pair_kinds",
        "table_mapping_modes",
        "component_submodes",
        "source_block_names",
        "header_prefixes",
        "filenames",
    ):
        evidence[key] = _merge_sorted_values(
            _as_list(evidence.get(key)) + _as_list(duplicate_evidence.get(key))
        )


def _refresh_backplate_structured_shared_endpoint_issue(issue: Issue) -> None:
    evidence = issue.evidence
    if not evidence.get("backplate_structured_shared_endpoint_aggregate_review"):
        return
    if (
        evidence.get("many_to_one_classification")
        != "backplate_structured_shared_endpoint_review"
    ):
        return

    shared_values = _as_list(evidence.get("aggregated_shared_endpoint_ranges")) or _as_list(
        evidence.get("aggregated_shared_endpoints")
    )
    logical_values = _as_list(evidence.get("aggregated_logical_endpoints"))
    if not shared_values:
        return

    issue.summary = (
        "Backplate structured mappings share a component-scope endpoint cluster: "
        f"shared={', '.join(str(value) for value in shared_values)}."
    )
    if logical_values:
        issue.summary += f" logical={', '.join(str(value) for value in logical_values)}."
    issue.explanation = (
        "同一组件实例或线组内，背板虚拟表格与 component/table 结构化映射共同引用多个外部端点。"
        "这更像背板表格作用域与元件端口作用域在同一物理接线组内的汇合，需要按结构化 scope 复核，"
        "而不是逐个共享端点当成普通多对一错误。"
    )
    issue.recommended_action = (
        "按聚合后的共享端点、组件线组、背板表头、插件块和逻辑端列表核对这些结构化关系是否属于同一接线组。"
    )


def _find_backplate_same_sheet_scope_cluster(
    clustered: list[Issue],
    issue: Issue,
) -> int | None:
    base_key = _backplate_same_sheet_scope_cluster_base_key(issue)
    for index, existing in enumerate(clustered):
        if not _is_backplate_same_sheet_scope_aggregation_issue(existing):
            continue
        if _backplate_same_sheet_scope_cluster_base_key(existing) != base_key:
            continue
        if _terminal_header_table_ranges_touch(existing, issue):
            return index
    return None


def _find_terminal_header_table_cluster(
    clustered: list[Issue],
    issue: Issue,
) -> int | None:
    base_key = _terminal_header_table_cluster_base_key(issue)
    for index, existing in enumerate(clustered):
        if not _is_terminal_header_table_aggregation_issue(existing):
            continue
        if _terminal_header_table_cluster_base_key(existing) != base_key:
            continue
        if _terminal_header_table_ranges_touch(existing, issue):
            return index
    return None


def _terminal_header_table_cluster_base_key(issue: Issue) -> tuple[Any, ...]:
    if issue.rule_id == "R-ONE-TO-MANY":
        return (
            issue.rule_id,
            issue.evidence.get("one_to_many_classification"),
            issue.sheet_id or "",
            issue.evidence.get("header_prefix") or "",
        )
    return (
        issue.rule_id,
        issue.evidence.get("many_to_one_classification"),
        issue.sheet_id or "",
        tuple(_merge_sorted_values(_as_list(issue.evidence.get("header_prefixes")))),
    )


def _terminal_header_table_ranges_touch(primary: Issue, duplicate: Issue) -> bool:
    if primary.rule_id == "R-MANY-TO-ONE":
        primary_endpoints = _numeric_suffix_values(
            _as_list(primary.evidence.get("aggregated_shared_endpoints"))
            + _as_list(primary.evidence.get("shared_endpoint"))
        )
        duplicate_endpoints = _numeric_suffix_values(
            _as_list(duplicate.evidence.get("aggregated_shared_endpoints"))
            + _as_list(duplicate.evidence.get("shared_endpoint"))
        )
        if primary_endpoints and duplicate_endpoints:
            return _integer_ranges_touch(primary_endpoints, duplicate_endpoints)

    primary_rows = _integer_values(
        _as_list(primary.evidence.get("aggregated_row_numbers"))
        + _as_list(primary.evidence.get("row_number"))
        + _as_list(primary.evidence.get("row_numbers"))
    )
    duplicate_rows = _integer_values(
        _as_list(duplicate.evidence.get("aggregated_row_numbers"))
        + _as_list(duplicate.evidence.get("row_number"))
        + _as_list(duplicate.evidence.get("row_numbers"))
    )
    if not primary_rows or not duplicate_rows:
        return False
    return _integer_ranges_touch(primary_rows, duplicate_rows)


def _integer_ranges_touch(first: list[int], second: list[int]) -> bool:
    first_min, first_max = min(first), max(first)
    second_min, second_max = min(second), max(second)
    return first_min <= second_max + 1 and second_min <= first_max + 1


def _integer_values(values: list[Any]) -> list[int]:
    result: list[int] = []
    for value in values:
        try:
            result.append(int(str(value)))
        except (TypeError, ValueError):
            continue
    return result


def _numeric_suffix_values(values: list[Any]) -> list[int]:
    result: list[int] = []
    for value in values:
        text = str(value)
        digits = ""
        for char in reversed(text):
            if not char.isdigit():
                break
            digits = f"{char}{digits}"
        if not digits:
            continue
        result.append(int(digits))
    return result


def _numeric_suffix_range_labels(values: list[Any]) -> list[str]:
    groups: dict[str, set[int]] = {}
    passthrough: list[str] = []
    for value in _merge_sorted_values(values):
        prefix, number = _split_numeric_suffix(value)
        if number is None:
            passthrough.append(value)
            continue
        groups.setdefault(prefix, set()).add(number)

    labels = list(passthrough)
    for prefix in sorted(groups, key=_natural_sort_key):
        labels.extend(_prefixed_integer_range_labels(prefix, sorted(groups[prefix])))
    return labels


def _split_numeric_suffix(value: str) -> tuple[str, int | None]:
    digits = ""
    for char in reversed(value):
        if not char.isdigit():
            break
        digits = f"{char}{digits}"
    if not digits:
        return value, None
    return value[: -len(digits)], int(digits)


def _integer_range_labels(values: list[int]) -> list[str]:
    return _prefixed_integer_range_labels("", sorted(set(values)))


def _prefixed_integer_range_labels(prefix: str, values: list[int]) -> list[str]:
    if not values:
        return []
    labels: list[str] = []
    start = values[0]
    previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        labels.append(_format_integer_range(prefix, start, previous))
        start = previous = value
    labels.append(_format_integer_range(prefix, start, previous))
    return labels


def _format_integer_range(prefix: str, start: int, end: int) -> str:
    if start == end:
        return f"{prefix}{start}"
    return f"{prefix}{start}..{prefix}{end}"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def _pair_evidence(issue: Issue) -> dict[str, Any]:
    value = issue.evidence.get("pair_evidence")
    return value if isinstance(value, dict) else {}


def _is_real_line_group(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"nan", "none", "null"}


def _merge_sorted_values(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if value is not None}, key=_natural_sort_key)


def _natural_sort_key(value: str) -> list[tuple[int, Any]]:
    parts: list[tuple[int, Any]] = []
    current = ""
    current_is_digit: bool | None = None
    for char in value:
        is_digit = char.isdigit()
        if current and is_digit != current_is_digit:
            parts.append((0, int(current)) if current_is_digit else (1, current))
            current = ""
        current += char
        current_is_digit = is_digit
    if current:
        parts.append((0, int(current)) if current_is_digit else (1, current))
    return parts


def _dedupe_dict_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if payload in seen:
            continue
        seen.add(payload)
        deduped.append(record)
    return deduped
