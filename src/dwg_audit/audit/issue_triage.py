"""User-facing issue triage: handling class + review groups.

Electrical reviewers need three clear certainty buckets, not raw rule IDs:

- error:   确定性错误 — hard conflicts the engine is confident about (fail-closed)
- warning: 可能有错误 — important anomalies / topology that may still be wrong
- review:  须人工校验 — machine-uncertain extraction; must not be auto-cleared

Principle: 可以误报，但不能错过真实错误 (false positives allowed; false
negatives on real conflicts are not).

Also assigns review_group_* so the desktop can collapse hundreds of
similar symptoms (e.g. low-confidence pairs on the same sheet) into
actionable groups without discarding member issues.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from dwg_audit.domain.models import Issue

# rule_id -> stable issue_type (reserved catalog on AuditRule.output_issue_type)
RULE_ISSUE_TYPES: dict[str, str] = {
    "R-PAIR-MISSING-SIDE": "pair_missing_side",
    "R-PAIR-LOW-CONFIDENCE": "pair_low_confidence",
    "R-DUPLICATE-SAME-LINE": "duplicate_same_line",
    "R-CROSS-PAGE-CONFLICT": "cross_page_conflict",
    "R-SEMANTIC-MAPPING-CONFLICT": "semantic_mapping_conflict",
    "R-TABLE-MAPPING-SOURCE-CONFLICT": "table_mapping_source_conflict",
    "R-ONE-TO-MANY": "one_to_many",
    "R-MANY-TO-ONE": "many_to_one",
    "R-MISSING-RECIPROCAL": "missing_reciprocal",
    "R-DUPLICATE-PAIR": "duplicate_pair",
    "R-SHEET-PAGE-MISMATCH": "sheet_page_mismatch",
}

RULE_HANDLING_DEFAULT: dict[str, str] = {
    "R-CROSS-PAGE-CONFLICT": "error",
    "R-TABLE-MAPPING-SOURCE-CONFLICT": "error",
    "R-SEMANTIC-MAPPING-CONFLICT": "error",
    "R-MISSING-RECIPROCAL": "warning",
    "R-MANY-TO-ONE": "warning",
    "R-DUPLICATE-PAIR": "warning",
    "R-SHEET-PAGE-MISMATCH": "warning",
    "R-ONE-TO-MANY": "warning",
    "R-PAIR-MISSING-SIDE": "review",
    "R-PAIR-LOW-CONFIDENCE": "review",
    "R-DUPLICATE-SAME-LINE": "review",
}

RULE_FAMILY_LABELS: dict[str, str] = {
    "R-CROSS-PAGE-CONFLICT": "跨页端子冲突",
    "R-TABLE-MAPPING-SOURCE-CONFLICT": "表格与图内映射不一致",
    "R-SEMANTIC-MAPPING-CONFLICT": "端子语义映射冲突",
    "R-MISSING-RECIPROCAL": "缺少对端回指",
    "R-MANY-TO-ONE": "多对一连接",
    "R-DUPLICATE-PAIR": "重复配对",
    "R-SHEET-PAGE-MISMATCH": "页码不一致",
    "R-ONE-TO-MANY": "一对多连接",
    "R-PAIR-MISSING-SIDE": "端子缺侧",
    "R-PAIR-LOW-CONFIDENCE": "端子配对不确定",
    "R-DUPLICATE-SAME-LINE": "同线重复端子",
}

# Frontend-facing certainty labels (error / warning / review).
HANDLING_LABELS = {
    "error": "确定性错误",
    "warning": "可能有错误",
    "review": "须人工校验",
}

# Short chip labels for dense UI; full labels stay in HANDLING_LABELS.
HANDLING_CHIP_LABELS = {
    "error": "错误",
    "warning": "可能错",
    "review": "待校验",
}

_SEVERITY_RANK = {
    "critical": 0,
    "error": 1,
    "high": 1,
    "major": 2,
    "medium": 2,
    "warning": 3,
    "warn": 3,
    "minor": 4,
    "low": 4,
    "review": 5,
    "info": 6,
}


def classify_and_group_issues(issues: list[Issue]) -> list[Issue]:
    """Annotate issues with handling_class / issue_type / review groups."""
    if not issues:
        return issues

    for issue in issues:
        _normalize_issue_type(issue)
        handling = _resolve_handling_class(issue)
        issue.evidence = dict(issue.evidence or {})
        issue.evidence["handling_class"] = handling
        issue.evidence["handling_label"] = HANDLING_LABELS.get(handling, handling)
        issue.evidence["handling_chip_label"] = HANDLING_CHIP_LABELS.get(
            handling, HANDLING_LABELS.get(handling, handling)
        )
        family = RULE_FAMILY_LABELS.get(issue.rule_id) or (issue.title or issue.rule_id)
        issue.evidence["issue_family"] = family
        group_key = _review_group_key(issue, handling)
        issue.evidence["review_group_key"] = group_key

    group_sizes = Counter(
        str((issue.evidence or {}).get("review_group_key") or issue.issue_id) for issue in issues
    )

    for issue in issues:
        evidence = dict(issue.evidence or {})
        group_key = str(evidence.get("review_group_key") or issue.issue_id)
        size = int(group_sizes.get(group_key, 1))
        evidence["review_group_id"] = group_key
        evidence["review_group_size"] = size
        evidence["review_group_label"] = _review_group_label(issue, size)
        issue.evidence = evidence

    return sorted(issues, key=_issue_sort_key)


def summarize_handling(issues: list[Issue] | list[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "review": 0, "other": 0}
    for item in issues:
        if isinstance(item, Issue):
            handling = str((item.evidence or {}).get("handling_class") or "")
            if not handling:
                handling = _resolve_handling_class(item)
        else:
            evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
            handling = str(
                item.get("handling_class")
                or evidence.get("handling_class")
                or ""
            )
            if not handling:
                # Lightweight dict path for desktop payloads / tests.
                handling = _resolve_handling_class_from_fields(
                    rule_id=str(item.get("rule_id") or ""),
                    severity=str(item.get("severity") or ""),
                    evidence=evidence if isinstance(evidence, dict) else {},
                    confidence=float(item.get("confidence") or 0.0),
                )
        if handling in counts:
            counts[handling] += 1
        else:
            counts["other"] += 1
    return counts


def _normalize_issue_type(issue: Issue) -> None:
    mapped = RULE_ISSUE_TYPES.get(issue.rule_id)
    current = (issue.issue_type or "").strip()
    if not current or current == issue.rule_id or current.startswith("R-"):
        if mapped:
            issue.issue_type = mapped
    elif mapped and current != mapped and current.replace("-", "_").lower() == issue.rule_id.lower().replace("r-", "").replace("-", "_"):
        issue.issue_type = mapped


def _resolve_handling_class(issue: Issue) -> str:
    return _resolve_handling_class_from_fields(
        rule_id=issue.rule_id,
        severity=issue.severity,
        evidence=issue.evidence or {},
        confidence=float(issue.confidence or 0.0),
    )


def _resolve_handling_class_from_fields(
    *,
    rule_id: str,
    severity: str,
    evidence: dict[str, Any],
    confidence: float,
) -> str:
    # Explicit triage marks from rule runners take precedence.
    one_to_many = str(evidence.get("one_to_many_classification") or "").strip().lower()
    many_to_one = str(evidence.get("many_to_one_classification") or "").strip().lower()
    triage = one_to_many or many_to_one

    if triage in {"conflict"} or "conflict" in triage:
        return "error"
    if triage in {"branch"} or triage.endswith("_branch"):
        # Legitimate branch topology → softer bucket.
        return "warning"
    if triage in {"review"} or triage.endswith("_review") or "review" in triage:
        # Structured review aggregates stay in 须人工校验 unless rule is a hard conflict.
        if rule_id in {"R-CROSS-PAGE-CONFLICT", "R-TABLE-MAPPING-SOURCE-CONFLICT"}:
            return "error"
        return "review"

    severity_norm = (severity or "").strip().lower()
    if severity_norm in {"critical", "error", "high"}:
        return "error"

    default = RULE_HANDLING_DEFAULT.get(rule_id)
    if default:
        # Low-confidence hard conflicts remain error; low-confidence pair noise stays review.
        if default == "error":
            return "error"
        if default == "review":
            return "review"
        # warning default: demote very low confidence to review.
        if confidence and confidence < 0.55:
            return "review"
        return "warning"

    if severity_norm in {"major", "medium", "warning", "warn"}:
        return "warning"
    if severity_norm in {"review", "info", "minor", "low"}:
        return "review"
    return "review"


def _review_group_key(issue: Issue, handling: str) -> str:
    """Collapse similar symptoms for the workbench without dropping members."""
    rule_id = issue.rule_id or "unknown"
    sheet = issue.sheet_id or "project"
    left = (issue.left_value or "").strip()
    right = (issue.right_value or "").strip()
    evidence = issue.evidence or {}

    if rule_id in {"R-CROSS-PAGE-CONFLICT", "R-ONE-TO-MANY", "R-MISSING-RECIPROCAL"}:
        anchor = left or right or "value"
        return f"{handling}|{rule_id}|value:{anchor}"

    if rule_id == "R-MANY-TO-ONE":
        anchor = right or left or "value"
        return f"{handling}|{rule_id}|value:{anchor}"

    if rule_id in {
        "R-PAIR-LOW-CONFIDENCE",
        "R-PAIR-MISSING-SIDE",
        "R-DUPLICATE-SAME-LINE",
    }:
        # Flooding rules: group per sheet + family so one page is one work item.
        return f"{handling}|{rule_id}|sheet:{sheet}"

    if rule_id in {
        "R-TABLE-MAPPING-SOURCE-CONFLICT",
        "R-SEMANTIC-MAPPING-CONFLICT",
        "R-DUPLICATE-PAIR",
        "R-SHEET-PAGE-MISMATCH",
    }:
        anchor = left or right or str(evidence.get("logical_endpoint") or sheet)
        return f"{handling}|{rule_id}|{sheet}|{anchor}"

    return f"{handling}|{rule_id}|{sheet}|{issue.issue_id}"


def _review_group_label(issue: Issue, size: int) -> str:
    family = RULE_FAMILY_LABELS.get(issue.rule_id) or (issue.title or "相关问题")
    sheet_no = (issue.sheet_no or "").strip()
    left = (issue.left_value or "").strip()
    right = (issue.right_value or "").strip()
    handling = str((issue.evidence or {}).get("handling_class") or "review")
    bucket = HANDLING_LABELS.get(handling, "须人工校验")

    if issue.rule_id in {"R-CROSS-PAGE-CONFLICT", "R-ONE-TO-MANY", "R-MISSING-RECIPROCAL"} and left:
        core = f"端子 {left}"
        if right:
            core = f"{core} → {right}"
        label = f"{bucket} · {family} · {core}"
    elif issue.rule_id == "R-MANY-TO-ONE" and right:
        label = f"{bucket} · {family} · 端子 {right}"
    elif sheet_no:
        label = f"{bucket} · 图 {sheet_no} · {family}"
    else:
        label = f"{bucket} · {family}"

    if size > 1:
        label = f"{label}（共 {size} 处）"
    return label


def _issue_sort_key(issue: Issue) -> tuple[Any, ...]:
    evidence = issue.evidence or {}
    handling = str(evidence.get("handling_class") or "review")
    handling_rank = {"error": 0, "warning": 1, "review": 2}.get(handling, 9)
    severity_rank = _SEVERITY_RANK.get(str(issue.severity or "").lower(), 9)
    group_key = str(evidence.get("review_group_id") or "")
    return (
        handling_rank,
        severity_rank,
        -float(issue.confidence or 0.0),
        group_key,
        issue.sheet_order if issue.sheet_order is not None else 10**9,
        issue.issue_id,
    )
