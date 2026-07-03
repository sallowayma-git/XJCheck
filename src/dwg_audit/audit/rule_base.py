from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.utils.ids import IdFactory


@dataclass(slots=True)
class RuleContext:
    pairs: list[Pair]
    line_groups: list[LineGroup]
    sheets: list[SheetRecord]
    config: dict
    issue_ids: IdFactory
    terminal_candidates: list[TerminalCandidate]
    high_threshold: float
    duplicate_delta: float
    reciprocal_required: bool
    group_map: dict[str, LineGroup]
    sheet_map: dict[str, SheetRecord]


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
