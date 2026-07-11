"""Audit V2 shadow builders: issue clusters, summary, engine comparison.

Phase 120. Never mutates legacy Pair/Issue outputs. Clustering and comparison
are shadow-only overlays for residual-risk analysis.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

ALGORITHM_VERSION = "audit-v2-v1"

_SEVERITY_RANK = {
    "critical": 5,
    "major": 4,
    "review": 3,
    "warning": 3,  # treat warning as review-rank
    "minor": 2,
    "info": 1,
    "unknown": 0,
}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _listish(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return list(value.tolist())
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _records(value: Any) -> list[Any]:
    """Normalize DataFrame / list / None to a list of row-like objects.

    Dicts and dataclass-like objects are preserved as-is so _get works.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if hasattr(value, "to_dict"):
        if getattr(value, "empty", False):
            return []
        return list(value.to_dict("records"))
    return []


def _has_witness(issue: Any) -> bool:
    evidence = _get(issue, "evidence")
    if isinstance(evidence, dict) and evidence:
        return True
    if evidence:  # non-empty list/str
        return True
    evidence_refs = _get(issue, "evidence_refs")
    if evidence_refs:
        return True
    source_handles = _get(issue, "source_handles")
    if source_handles:
        return True
    if isinstance(evidence, dict):
        if evidence.get("handles") or evidence.get("source_handles"):
            return True
    return False


def _severity_rank(severity: Any) -> int:
    if severity is None:
        return _SEVERITY_RANK["unknown"]
    return _SEVERITY_RANK.get(str(severity).lower(), _SEVERITY_RANK["unknown"])


def _collect_pair_ids(issue: Any) -> list[str]:
    collected: list[str] = []
    for key in ("pair_id", "primary_pair_id"):
        value = _get(issue, key)
        if value is not None and value != "":
            collected.append(str(value))
    for value in _listish(_get(issue, "related_pair_ids")):
        if value is not None and value != "":
            collected.append(str(value))
    return collected


def build_audit_v2_issue_clusters(
    issues: list[Any] | None,
    equivalence: list | Any | None = None,
    endpoint_identities: list | None = None,
) -> list[dict[str, Any]]:
    """Cluster legacy issues by (rule_id, sheet_id).

    Issues may be dataclasses/SimpleNamespace objects or dicts.
    equivalence and endpoint_identities are accepted for API compat; unused in v1.
    """
    _ = equivalence  # API compatibility; unused in v1
    _ = endpoint_identities  # API compatibility; unused in v1

    if not issues:
        return []

    # Group by (rule_id, sheet_id)
    groups: dict[tuple[str, str | None], list[Any]] = {}
    for issue in issues:
        rule_id = str(_get(issue, "rule_id") or "")
        sheet_raw = _get(issue, "sheet_id")
        sheet_id: str | None = str(sheet_raw) if sheet_raw is not None else None
        key = (rule_id, sheet_id)
        groups.setdefault(key, []).append(issue)

    clusters: list[dict[str, Any]] = []
    for (rule_id, sheet_id), group in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        digest = hashlib.sha256(
            f"{rule_id}|{sheet_id}".encode()
        ).hexdigest()[:16]

        # severity_max: highest rank; keep original lowercased token
        best_severity = "unknown"
        best_rank = -1
        for issue in group:
            sev_raw = _get(issue, "severity") or "unknown"
            sev = str(sev_raw).lower()
            rank = _severity_rank(sev)
            if rank > best_rank:
                best_rank = rank
                best_severity = sev

        # issue_ids sorted
        issue_ids = sorted(
            str(_get(issue, "issue_id") or "")
            for issue in group
            if _get(issue, "issue_id") is not None
        )

        # pair_ids: unique sorted non-null
        pair_id_set: set[str] = set()
        for issue in group:
            pair_id_set.update(_collect_pair_ids(issue))
        pair_ids = sorted(pair_id_set)

        # witness_status
        witness_status = (
            "PRESENT" if any(_has_witness(issue) for issue in group) else "UNKNOWN"
        )

        # message_summary: first non-empty message/summary/title, stable by issue_id
        ordered = sorted(
            group,
            key=lambda issue: str(_get(issue, "issue_id") or ""),
        )
        message_summary = None
        for issue in ordered:
            for field in ("message", "summary", "title"):
                value = _get(issue, field)
                if value:
                    message_summary = str(value)
                    break
            if message_summary:
                break

        clusters.append(
            {
                "cluster_id": f"AC-{digest}",
                "rule_id": rule_id,
                "sheet_id": sheet_id,
                "severity_max": best_severity,
                "issue_ids": issue_ids,
                "issue_count": len(issue_ids),
                "pair_ids": pair_ids,
                "root_kind": "LEGACY_RULE",
                "witness_status": witness_status,
                "message_summary": message_summary,
                "algorithm_version": ALGORITHM_VERSION,
            }
        )

    return clusters


def summarize_audit_v2(
    clusters: list[dict[str, Any]] | None,
    issues: list[Any] | None = None,
) -> dict[str, Any]:
    """Summarize audit-v2 clusters into a compact status dict."""
    clusters = clusters or []
    issue_count = sum(len(c.get("issue_ids") or []) for c in clusters)
    if issue_count == 0 and issues:
        issue_count = len(issues)

    by_rule = Counter(str(c.get("rule_id") or "") for c in clusters)
    by_severity = Counter(str(c.get("severity_max") or "unknown") for c in clusters)
    present = sum(1 for c in clusters if c.get("witness_status") == "PRESENT")
    unknown = sum(1 for c in clusters if c.get("witness_status") == "UNKNOWN")
    total = len(clusters)
    completeness = (present / total) if total else 1.0

    return {
        "schema_version": "audit-v2-summary-v1",
        "algorithm_version": ALGORITHM_VERSION,
        "cluster_count": total,
        "issue_count": issue_count,
        "by_rule_id": dict(by_rule),
        "by_severity_max": dict(by_severity),
        "witness_present_count": present,
        "witness_unknown_count": unknown,
        "witness_completeness": completeness,
        "legacy_issue_stream_retained": True,
    }


def compare_legacy_new_relations(
    pairs: list | Any | None,
    equivalence_frame: list | Any | None,
) -> dict[str, Any]:
    """Shadow comparison of legacy pairs vs v2 network equivalence frame.

    Empty-safe. Does not mutate inputs. Notes that legacy is retained.
    """
    pairs_records = _records(pairs)
    eq_records = _records(equivalence_frame)

    # Normalize equivalence rows to dicts for field access
    eq_dicts: list[dict[str, Any]] = []
    for row in eq_records:
        if isinstance(row, dict):
            eq_dicts.append(row)
        else:
            eq_dicts.append(
                {
                    "equivalence_status": _get(row, "equivalence_status"),
                    "v2_changes_legacy_result": _get(row, "v2_changes_legacy_result"),
                }
            )

    status_counts = Counter(
        str(row.get("equivalence_status") or "") for row in eq_dicts
    )
    v2_changes = sum(1 for row in eq_dicts if row.get("v2_changes_legacy_result"))
    unique_count = sum(
        1
        for row in eq_dicts
        if row.get("equivalence_status") == "UNIQUE_V2_NETWORK"
    )
    unique_rate = (unique_count / len(eq_dicts)) if eq_dicts else 0.0

    return {
        "schema_version": "engine-comparison-v1",
        "pair_count": len(pairs_records),
        "equivalence_row_count": len(eq_dicts),
        "equivalence_status_counts": dict(status_counts),
        "v2_changes_legacy_result_count": v2_changes,
        "unique_v2_network_rate": unique_rate,
        "notes": "shadow comparison only; legacy retained",
    }
