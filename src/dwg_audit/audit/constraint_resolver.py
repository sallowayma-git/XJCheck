"""Shadow-only semantic constraint resolver (Phase 119, no OR-Tools).

Records constraint decisions over scoped attachment candidates without mutating
topology or Pair/Issue outputs. Strong constraints never apply illegal unions;
they only demote authority / mark VIOLATION on decision rows.
"""

from __future__ import annotations

from collections import Counter
from collections import defaultdict
from copy import deepcopy
from typing import Any


ALGORITHM_VERSION = "constraint-resolver-v1"
LOW_MARGIN_THRESHOLD = 0.02

_AMBIGUOUS_SCOPE_STATES = frozenset({"AMBIGUOUS", "CONFLICT"})


def resolve_semantic_constraints(
    scoped_attachments: list[dict[str, Any]],
    scope_decisions: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Annotate attachments with constraint authority and emit decision rows.

    Parameters
    ----------
    scoped_attachments:
        Attachment candidate rows, optionally already annotated by ScopeResolver.
    scope_decisions:
        Accepted for API compatibility; unused in v1.

    Returns
    -------
    annotated_attachments, constraint_decisions, summary
        Deep-copied attachments with constraint_* fields, decision rows, and summary.
    """
    _ = scope_decisions  # API compatibility; unused in v1
    annotated, decisions = _resolve_with_decisions(scoped_attachments)
    return annotated, decisions, _build_summary(annotated, decisions)


def _resolve_with_decisions(
    scoped_attachments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    material = [deepcopy(row) for row in (scoped_attachments or [])]
    decisions: list[dict[str, Any]] = []
    decision_counter = 0

    def next_decision_id() -> str:
        nonlocal decision_counter
        decision_counter += 1
        return f"CR{decision_counter:04d}"

    # Seed per-attachment constraint fields.
    for row in material:
        selected = bool(row.get("selected"))
        if "scope_state" not in row or row.get("scope_state") in (None, ""):
            row["scope_state"] = "UNSCOPED"
        row["constraint_authority"] = "AUTHORITATIVE" if selected else "REJECTED"
        row["constraint_state"] = "PASS"
        row["constraint_reason_codes"] = []

    # 1) ONE_SELECTED_PER_TOKEN (global grouping over selected rows).
    selected_by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in material:
        if bool(row.get("selected")):
            token_id = str(row.get("token_id") or "")
            selected_by_token[token_id].append(row)

    for _token_id, group in selected_by_token.items():
        ordered = sorted(
            group,
            key=lambda item: (
                -float(item.get("score") or 0.0),
                str(item.get("attachment_id") or ""),
            ),
        )
        winner = ordered[0]
        for loser in ordered[1:]:
            _append_reason(loser, "DUPLICATE_SELECTED")
            loser["constraint_authority"] = "REJECTED"
            loser["constraint_state"] = "VIOLATION"
            decisions.append(
                _decision_row(
                    decision_id=next_decision_id(),
                    attachment=loser,
                    constraint_kind="ONE_SELECTED_PER_TOKEN",
                    severity="STRONG",
                    state="VIOLATION",
                    authority="REJECTED",
                    reason_codes=["DUPLICATE_SELECTED"],
                )
            )
        # PASS row for the winner under this constraint (may later be demoted).
        decisions.append(
            _decision_row(
                decision_id=next_decision_id(),
                attachment=winner,
                constraint_kind="ONE_SELECTED_PER_TOKEN",
                severity="STRONG",
                state="PASS",
                authority="AUTHORITATIVE",
                reason_codes=[],
            )
        )

    # 2) SCOPE_AMBIGUITY_NOT_AUTHORITATIVE
    for row in material:
        scope_state = str(row.get("scope_state") or "UNSCOPED")
        if scope_state not in _AMBIGUOUS_SCOPE_STATES:
            continue
        if row["constraint_authority"] == "REJECTED" and row["constraint_state"] == "VIOLATION":
            if not bool(row.get("selected")):
                continue
        _append_reason(row, "SCOPE_AMBIGUITY")
        if row["constraint_authority"] != "REJECTED" or row["constraint_state"] != "VIOLATION":
            row["constraint_authority"] = "REVIEW_ONLY"
            if row["constraint_state"] == "PASS":
                row["constraint_state"] = "REVIEW"
        decisions.append(
            _decision_row(
                decision_id=next_decision_id(),
                attachment=row,
                constraint_kind="SCOPE_AMBIGUITY_NOT_AUTHORITATIVE",
                severity="STRONG",
                state="REVIEW",
                authority="REVIEW_ONLY",
                reason_codes=["SCOPE_AMBIGUITY"],
            )
        )

    # 3) LOW_MARGIN_REVIEW for selected
    for row in material:
        if not bool(row.get("selected")):
            continue
        margin = row.get("margin")
        if margin is None:
            continue
        try:
            margin_value = float(margin)
        except (TypeError, ValueError):
            continue
        if margin_value >= LOW_MARGIN_THRESHOLD:
            continue
        _append_reason(row, "LOW_MARGIN")
        if row["constraint_authority"] != "REJECTED" or row["constraint_state"] != "VIOLATION":
            row["constraint_authority"] = "REVIEW_ONLY"
            if row["constraint_state"] == "PASS":
                row["constraint_state"] = "REVIEW"
        decisions.append(
            _decision_row(
                decision_id=next_decision_id(),
                attachment=row,
                constraint_kind="LOW_MARGIN_REVIEW",
                severity="STRONG",
                state="REVIEW",
                authority="REVIEW_ONLY",
                reason_codes=["LOW_MARGIN"],
            )
        )

    # 4) CROSS_SCOPE_COMPETITION (weak) for selected pairs on same endpoint.
    selected_rows = [row for row in material if bool(row.get("selected"))]
    by_endpoint: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in selected_rows:
        sheet_id = str(row.get("sheet_id") or "")
        line_id = str(row.get("target_line_id") or "")
        endpoint = str(row.get("target_endpoint") or "")
        by_endpoint[(sheet_id, line_id, endpoint)].append(row)

    flagged: set[str] = set()
    for group in by_endpoint.values():
        if len(group) < 2:
            continue
        for i, left in enumerate(group):
            left_scope = _nonempty_scope_key(left)
            if left_scope is None:
                continue
            for right in group[i + 1 :]:
                right_scope = _nonempty_scope_key(right)
                if right_scope is None:
                    continue
                if left_scope == right_scope:
                    continue
                for item in (left, right):
                    attachment_id = str(item.get("attachment_id") or "")
                    if attachment_id in flagged:
                        continue
                    flagged.add(attachment_id)
                    _append_reason(item, "CROSS_SCOPE_COMPETITION")
                    if item["constraint_authority"] == "AUTHORITATIVE":
                        item["constraint_authority"] = "REVIEW_ONLY"
                        if item["constraint_state"] == "PASS":
                            item["constraint_state"] = "REVIEW"
                    decisions.append(
                        _decision_row(
                            decision_id=next_decision_id(),
                            attachment=item,
                            constraint_kind="CROSS_SCOPE_COMPETITION",
                            severity="WEAK",
                            state="REVIEW",
                            authority="REVIEW_ONLY",
                            reason_codes=["CROSS_SCOPE_COMPETITION"],
                        )
                    )

    # Re-align ONE_SELECTED_PER_TOKEN PASS authority if winner was later demoted.
    for decision in decisions:
        if (
            decision.get("constraint_kind") == "ONE_SELECTED_PER_TOKEN"
            and decision.get("state") == "PASS"
        ):
            attachment_id = str(decision.get("attachment_id") or "")
            for row in material:
                if str(row.get("attachment_id") or "") == attachment_id:
                    decision["authority"] = row.get("constraint_authority") or decision["authority"]
                    break

    return material, decisions


def _build_summary(
    annotated: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    by_kind: Counter[str] = Counter(
        str(row.get("constraint_kind") or "UNKNOWN") for row in decisions
    )
    strong_violation_count = sum(
        1
        for row in decisions
        if str(row.get("severity")) == "STRONG" and str(row.get("state")) == "VIOLATION"
    )
    review_only_count = sum(
        1 for row in annotated if str(row.get("constraint_authority")) == "REVIEW_ONLY"
    )
    authoritative_selected_count = sum(
        1
        for row in annotated
        if bool(row.get("selected"))
        and str(row.get("constraint_authority")) == "AUTHORITATIVE"
    )
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "strong_violation_count": strong_violation_count,
        "review_only_count": review_only_count,
        "authoritative_selected_count": authoritative_selected_count,
        "decision_count": len(decisions),
        "by_constraint_kind": dict(sorted(by_kind.items())),
        "inviolable_strong_constraints": True,
    }


def _decision_row(
    *,
    decision_id: str,
    attachment: dict[str, Any],
    constraint_kind: str,
    severity: str,
    state: str,
    authority: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "sheet_id": attachment.get("sheet_id"),
        "attachment_id": attachment.get("attachment_id"),
        "token_id": attachment.get("token_id"),
        "constraint_kind": constraint_kind,
        "severity": severity,
        "state": state,
        "authority": authority,
        "reason_codes": list(reason_codes),
        "algorithm_version": ALGORITHM_VERSION,
    }


def _append_reason(row: dict[str, Any], code: str) -> None:
    reasons = row.get("constraint_reason_codes")
    if not isinstance(reasons, list):
        reasons = []
        row["constraint_reason_codes"] = reasons
    if code not in reasons:
        reasons.append(code)


def _nonempty_scope_key(row: dict[str, Any]) -> str | None:
    value = row.get("scope_key")
    if value is None:
        return None
    text = str(value).strip()
    return text or None
