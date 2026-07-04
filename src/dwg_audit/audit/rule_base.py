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
            related_sheet = self.sheet_map.get(related_pair.sheet_id)
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
    primary.evidence = evidence
    return primary


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
