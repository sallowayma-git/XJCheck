"""Failure queue builders: residual-risk routing for Phase 120.

Shadow-only. Emits failure items only for real residual risks.
Empty list when inputs are clean. Never auto-accepts cross-page candidates.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

ALGORITHM_VERSION = "failure-queue-v1"

ROUTING = frozenset(
    {
        "READER",
        "PRIMITIVE",
        "PAGE_CAPABILITY",
        "TOPOLOGY",
        "SYMBOL",
        "ENDPOINT",
        "TEXT_ATTACHMENT",
        "CROSS_PAGE",
        "CONSTRAINT",
        "PROFILE",
        "DATASET",
    }
)

_INCOMPLETE_STATUSES = frozenset(
    {
        "INCOMPLETE_EXTRACTION",
        "INCOMPLETE",
        "FAILED",
        "PARTIAL",
    }
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _page_capability_risk(page_capability_matrix: Any) -> bool:
    """Return True if any page has low confidence or missing route."""
    if page_capability_matrix is None:
        return False

    pages: list[Any] = []
    if isinstance(page_capability_matrix, list):
        pages = page_capability_matrix
    elif isinstance(page_capability_matrix, dict):
        pages = list(page_capability_matrix.values())
    else:
        return False

    for page in pages:
        if not isinstance(page, dict):
            # nested dict values may themselves be page dicts
            if hasattr(page, "get"):
                page = dict(page)  # type: ignore[arg-type]
            else:
                continue
        confidence = page.get("page_type_confidence")
        if confidence is not None:
            try:
                if float(confidence) < 0.6:
                    return True
            except (TypeError, ValueError):
                pass
        if "route" in page:
            route = page.get("route")
            if route is None or route == "":
                return True
        else:
            # missing route key is a risk when page dict looks page-like
            if "page_type_confidence" in page or "page_id" in page or "sheet_id" in page:
                return True
    return False


def build_failure_queue(
    *,
    extraction_gate: dict | Any | None = None,
    scope_summary: dict | None = None,
    constraint_summary: dict | None = None,
    page_capability_matrix: dict | list | None = None,
    audit_v2_summary: dict | None = None,
    engine_comparison: dict | None = None,
    open_endpoint_count: int | None = None,
    cross_page_candidate_count: int | None = None,
    project_graph_summary: dict | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Emit residual-risk failure items. Returns [] when clean.

    open_endpoint_count alone never triggers an item; unlabeled open endpoints
    from project_graph_summary do. project_graph_summary also supplies
    cross-page candidate counts when cross_page_candidate_count is absent.
    """
    items: list[dict[str, Any]] = []
    page_or_project = project_id or "project"
    seq = 0

    def _next_id() -> str:
        nonlocal seq
        seq += 1
        return f"FQ-{seq:04d}"

    def _append(
        *,
        category: str,
        severity: str,
        message: str,
        routing: str,
        evidence_ref: Any,
    ) -> None:
        items.append(
            {
                "failure_id": _next_id(),
                "category": category,
                "severity": severity,
                "state": "OPEN",
                "page_or_project": page_or_project,
                "message": message,
                "suggested_routing": routing,
                "evidence_ref": evidence_ref,
                "algorithm_version": ALGORITHM_VERSION,
            }
        )

    # Resolve cross-page count from explicit arg or project_graph_summary
    resolved_cross_page = cross_page_candidate_count
    if resolved_cross_page is None and project_graph_summary is not None:
        edge_counts = project_graph_summary.get("edge_counts") or {}
        resolved_cross_page = edge_counts.get("cross_page_candidates")

    # Resolve unlabeled open endpoints from project_graph_summary
    unlabeled_open = 0
    if project_graph_summary is not None:
        unresolved = project_graph_summary.get("unresolved") or {}
        unlabeled_open = int(unresolved.get("unlabeled_open_endpoints") or 0)

    # 1) extraction_gate incomplete
    if extraction_gate is not None:
        analysis_status = _get(extraction_gate, "analysis_status")
        clean_allowed = _get(extraction_gate, "clean_conclusion_allowed")
        incomplete_count = _get(extraction_gate, "incomplete_page_count") or 0
        status_str = str(analysis_status or "").upper()
        is_incomplete = (
            status_str in _INCOMPLETE_STATUSES
            or clean_allowed is False
            or (isinstance(incomplete_count, (int, float)) and incomplete_count > 0)
        )
        if is_incomplete:
            failure_code_counts = _get(extraction_gate, "failure_code_counts") or {}
            keys = (
                list(failure_code_counts.keys())
                if hasattr(failure_code_counts, "keys")
                else []
            )
            has_reader = any(
                "conversion" in str(k).lower() or "dxf" in str(k).lower()
                for k in keys
            )
            # Emit READER when conversion/dxf codes present; always emit PRIMITIVE
            # for residual incomplete-page risk so both routings surface when
            # extraction is incomplete without specific codes.
            if has_reader:
                _append(
                    category="incomplete_extraction",
                    severity="critical",
                    message=(
                        f"extraction incomplete (reader/conversion): "
                        f"status={analysis_status}, incomplete_pages={incomplete_count}"
                    ),
                    routing="READER",
                    evidence_ref={
                        "source": "extraction_gate",
                        "analysis_status": analysis_status,
                        "incomplete_page_count": incomplete_count,
                        "failure_code_counts": failure_code_counts,
                    },
                )
            # Always emit PRIMITIVE for incomplete extraction residual
            _append(
                category="incomplete_extraction",
                severity="critical",
                message=(
                    f"extraction incomplete: status={analysis_status}, "
                    f"incomplete_pages={incomplete_count}"
                ),
                routing="PRIMITIVE",
                evidence_ref={
                    "source": "extraction_gate",
                    "analysis_status": analysis_status,
                    "incomplete_page_count": incomplete_count,
                },
            )
            # When no conversion codes, still surface READER as a residual path
            # so operators can triage conversion vs primitive causes.
            if not has_reader:
                _append(
                    category="incomplete_extraction",
                    severity="critical",
                    message=(
                        f"extraction incomplete (possible reader path): "
                        f"status={analysis_status}"
                    ),
                    routing="READER",
                    evidence_ref={
                        "source": "extraction_gate",
                        "analysis_status": analysis_status,
                    },
                )

    # 2) constraint strong violations
    if constraint_summary is not None:
        strong_count = constraint_summary.get("strong_violation_count") or 0
        if strong_count > 0:
            _append(
                category="constraint_violation",
                severity="critical",
                message=f"strong constraint violations present: count={strong_count}",
                routing="CONSTRAINT",
                evidence_ref={
                    "source": "constraint_summary",
                    "strong_violation_count": strong_count,
                },
            )

    # 3) scope ambiguous attachments
    if scope_summary is not None:
        ambiguous = scope_summary.get("ambiguous_count") or 0
        if ambiguous > 0:
            _append(
                category="ambiguous_scope",
                severity="review",
                message=f"ambiguous scope attachments present: count={ambiguous}",
                routing="TEXT_ATTACHMENT",
                evidence_ref={
                    "source": "scope_summary",
                    "ambiguous_count": ambiguous,
                },
            )

    # 4) audit_v2 witness completeness
    if audit_v2_summary is not None:
        completeness = audit_v2_summary.get("witness_completeness")
        if completeness is not None and float(completeness) < 1.0:
            _append(
                category="witness_incomplete",
                severity="major",
                message=f"audit-v2 witness completeness {float(completeness):.3f} < 1.0",
                routing="TOPOLOGY",
                evidence_ref={
                    "source": "audit_v2_summary",
                    "witness_completeness": completeness,
                },
            )

    # 5) engine comparison: v2 changes legacy results
    if engine_comparison is not None:
        v2_changes = engine_comparison.get("v2_changes_legacy_result_count") or 0
        if v2_changes > 0:
            _append(
                category="engine_divergence",
                severity="major",
                message=f"v2 changes legacy result count={v2_changes}",
                routing="TOPOLOGY",
                evidence_ref={
                    "source": "engine_comparison",
                    "v2_changes_legacy_result_count": v2_changes,
                },
            )

    # 6) cross-page candidates require review
    if resolved_cross_page is not None and int(resolved_cross_page) > 0:
        _append(
            category="cross_page_candidates",
            severity="review",
            message="cross-page candidates require review; never auto-accept",
            routing="CROSS_PAGE",
            evidence_ref={
                "source": "cross_page_candidate_count",
                "count": int(resolved_cross_page),
            },
        )

    # 7) unlabeled open endpoints (from project graph, not bare count alone)
    if unlabeled_open > 0:
        _append(
            category="unlabeled_open_endpoints",
            severity="review",
            message=f"unlabeled open endpoints present: count={unlabeled_open}",
            routing="ENDPOINT",
            evidence_ref={
                "source": "project_graph_summary",
                "unlabeled_open_endpoints": unlabeled_open,
            },
        )

    # 8) bare open_endpoint_count intentionally skipped as sole signal
    _ = open_endpoint_count

    # 9) page capability risks
    if _page_capability_risk(page_capability_matrix):
        _append(
            category="page_capability",
            severity="review",
            message="one or more pages have low type confidence or missing route",
            routing="PAGE_CAPABILITY",
            evidence_ref={"source": "page_capability_matrix"},
        )

    return items


def summarize_failure_queue(items: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Summarize a failure-queue item list."""
    items = items or []
    by_severity = Counter(str(i.get("severity") or "") for i in items)
    return {
        "schema_version": "failure-queue-summary-v1",
        "algorithm_version": ALGORITHM_VERSION,
        "failure_count": len(items),
        "item_count": len(items),  # alias used by tests
        "critical_count": int(by_severity.get("critical", 0)),
        "by_category": dict(Counter(str(i.get("category") or "") for i in items)),
        "by_severity": dict(by_severity),
        "by_routing": dict(
            Counter(str(i.get("suggested_routing") or "") for i in items)
        ),
        "open_count": sum(1 for i in items if i.get("state") == "OPEN"),
    }
