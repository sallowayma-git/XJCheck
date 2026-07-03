from dwg_audit.audit.rule_base import AuditRule
from dwg_audit.audit.rule_base import select_rules


def _noop(_context):
    return []


def test_select_rules_preserves_registry_order() -> None:
    registry = [
        AuditRule("R-B", "B", "desc", "review", _noop),
        AuditRule("R-A", "A", "desc", "review", _noop),
        AuditRule("R-C", "C", "desc", "review", _noop),
    ]

    selected = select_rules(registry, {"R-A", "R-C"})

    assert [rule.rule_id for rule in selected] == ["R-A", "R-C"]
