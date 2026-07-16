from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from itertools import combinations
import json
from pathlib import Path
from typing import Any

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import ConnectivityAssertionState
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SCHEMA_VERSION
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_library_review import REVIEW_SCHEMA_FILENAME
from dwg_audit.audit.symbol_library_review import REVIEW_WORKFLOW_VERSION
from dwg_audit.audit.symbol_library_review import ReviewDocumentStatus
from dwg_audit.audit.symbol_library_review import ReviewItemStatus
from dwg_audit.audit.symbol_library_review import build_symbol_review_document
from dwg_audit.audit.symbol_library_review import load_symbol_review_document


ARTIFACT_SCHEMA_VERSION = "symbol-review-artifacts-v1"
VALIDATION_SCHEMA_VERSION = "symbol-review-validation-v1"
SUMMARY_SCHEMA_VERSION = "symbol-review-summary-v1"

BACKLOG_FILENAME = "symbol_review_backlog.json"
VALIDATION_FILENAME = "symbol_review_validation.json"
SUMMARY_FILENAME = "symbol_review_summary.json"


def build_symbol_review_artifacts(
    source: Any,
    *,
    project_id: str,
) -> dict[str, dict[str, Any]]:
    """Build a deterministic, non-authoritative project review backlog.

    The resolved library may contain approved production definitions.  This
    export deliberately removes that authority before it becomes a new review
    task.  Build failures still produce a schema-valid empty pending document
    and an explicit error artifact.
    """

    normalized_project_id = str(project_id).strip()
    artifact_issues: list[dict[str, str]] = []
    if not normalized_project_id:
        normalized_project_id = "UNKNOWN_PROJECT"
        artifact_issues.append(
            _artifact_issue(
                "PROJECT_ID_INVALID",
                "project_id must be a non-empty string",
            )
        )

    source_metadata = _source_metadata(source)
    build_failed = False
    try:
        backlog = _canonicalize_document(build_symbol_review_document(source))
    except Exception as exc:  # The artifact boundary must fail closed.
        build_failed = True
        artifact_issues.append(
            _artifact_issue(
                "SYMBOL_REVIEW_BACKLOG_BUILD_FAILED",
                f"{type(exc).__name__}: {exc}",
            )
        )
        backlog = _empty_backlog()

    review_result = load_symbol_review_document(backlog)
    safety = _safety_contract(backlog, review_result.library)
    unsafe_replaced = not safety["safe_pending_contract"]
    if unsafe_replaced:
        artifact_issues.append(
            _artifact_issue(
                "UNSAFE_SYMBOL_REVIEW_BACKLOG_REPLACED",
                "generated backlog retained authoritative or non-pending state",
            )
        )
        backlog = _empty_backlog()
        review_result = load_symbol_review_document(backlog)
        safety = _safety_contract(backlog, review_result.library)

    artifact_issues = sorted(
        artifact_issues,
        key=lambda issue: (issue["code"], issue["message"]),
    )
    review_validation = review_result.validation
    artifact_valid = (
        not artifact_issues
        and source_metadata["valid"]
        and review_validation.valid
        and safety["safe_pending_contract"]
    )
    symbol_count = review_validation.symbol_count
    if build_failed or unsafe_replaced:
        status = "ERROR"
    elif not artifact_valid:
        status = "INVALID"
    elif symbol_count == 0:
        status = "EMPTY"
    else:
        status = "READY_FOR_REVIEW"

    validation = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "project_id": normalized_project_id,
        "status": status,
        "artifact_valid": artifact_valid,
        "source": source_metadata,
        "artifact_issue_count": len(artifact_issues),
        "artifact_issues": artifact_issues,
        "review_validation": review_validation.to_dict(),
        "safety_contract": safety,
    }
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "project_id": normalized_project_id,
        "status": status,
        "artifact_valid": artifact_valid,
        "review_ready": artifact_valid and symbol_count > 0,
        "promotion_ready": review_validation.promotion_ready,
        "source_status": source_metadata["status"],
        "source_valid": source_metadata["valid"],
        "source_error_count": source_metadata["error_count"],
        "source_warning_count": source_metadata["warning_count"],
        "symbol_count": symbol_count,
        "geometry_definition_count": len(backlog["geometry_definitions"]),
        "pending_symbol_count": review_validation.pending_symbol_count,
        "review_validation_error_count": len(review_validation.errors),
        "review_validation_warning_count": len(review_validation.warnings),
        "artifact_issue_count": len(artifact_issues),
        "critical_issue_eligible_count": safety[
            "critical_issue_eligible_count"
        ],
        "critical_capable_count": safety["critical_capable_count"],
        "asserted_connectivity_group_count": safety[
            "asserted_connectivity_group_count"
        ],
        "asserted_union_capable_pair_count": safety[
            "asserted_union_capable_pair_count"
        ],
        "safe_pending_contract": safety["safe_pending_contract"],
    }
    return {
        "backlog": backlog,
        "validation": validation,
        "summary": summary,
    }


def write_symbol_review_artifacts(
    source: Any,
    findings_dir: Path,
    *,
    project_id: str,
) -> dict[str, Any]:
    """Write the project symbol-review backlog and its validation artifacts."""

    artifacts = build_symbol_review_artifacts(source, project_id=project_id)
    target_dir = Path(findings_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    _write_json(target_dir / BACKLOG_FILENAME, artifacts["backlog"])
    _write_json(target_dir / VALIDATION_FILENAME, artifacts["validation"])
    _write_json(target_dir / SUMMARY_FILENAME, artifacts["summary"])
    return artifacts["summary"]


def _source_metadata(source: Any) -> dict[str, Any]:
    library = (
        source
        if isinstance(source, SymbolDependencyLibrary)
        else getattr(source, "library", None)
    )
    source_status = (
        "resolved_library"
        if isinstance(source, SymbolDependencyLibrary)
        else str(getattr(source, "source_status", "resolved_bundle"))
    )
    source_path = getattr(source, "source_path", None)
    issues: list[dict[str, Any]] = []
    if not isinstance(library, SymbolDependencyLibrary):
        issues.append(
            {
                "code": "SOURCE_SYMBOL_LIBRARY_UNAVAILABLE",
                "severity": "ERROR",
                "message": "source must be a SymbolDependencyLibrary or expose one",
                "source": "artifact_input",
            }
        )
    else:
        for issue in library.validate().issues:
            issues.append(
                {
                    **issue.to_dict(),
                    "source": "library_validation",
                }
            )
    for item in getattr(source, "load_issues", ()) or ():
        row = dict(item) if isinstance(item, Mapping) else {"message": str(item)}
        issues.append(
            {
                "code": str(row.get("code") or "SOURCE_LIBRARY_LOAD_FAILED"),
                "severity": "ERROR",
                "message": str(row.get("message") or "symbol library load failed"),
                "source": "library_load",
            }
        )
    issues = sorted(
        issues,
        key=lambda issue: (
            str(issue.get("severity") or ""),
            str(issue.get("code") or ""),
            str(issue.get("symbol_id") or ""),
            str(issue.get("message") or ""),
        ),
    )
    error_count = sum(issue.get("severity") == "ERROR" for issue in issues)
    warning_count = sum(issue.get("severity") == "WARNING" for issue in issues)
    resolved_library = (
        library if isinstance(library, SymbolDependencyLibrary) else None
    )
    return {
        "status": source_status,
        "path": str(source_path) if source_path is not None else None,
        "valid": error_count == 0,
        "symbol_count": (
            len(resolved_library.symbols) if resolved_library is not None else 0
        ),
        "geometry_definition_count": (
            len(resolved_library.geometry_definitions)
            if resolved_library is not None
            else 0
        ),
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }


def _safety_contract(
    document: Mapping[str, Any],
    library: SymbolDependencyLibrary,
) -> dict[str, Any]:
    symbols = list(library.symbols)
    rows = document.get("symbols")
    rows = rows if isinstance(rows, list) else []
    workflow = document.get("review_workflow")
    workflow = workflow if isinstance(workflow, Mapping) else {}

    review_status_counts = Counter(
        str((row.get("review") or {}).get("status") or "MISSING")
        for row in rows
        if isinstance(row, Mapping)
    )
    annotation_status_counts = Counter(
        symbol.annotation_status.value for symbol in symbols
    )
    registry_status_counts = Counter(
        symbol.registry_status.value for symbol in symbols
    )
    critical_count = sum(symbol.critical_issue_eligible for symbol in symbols)
    asserted_group_count = sum(
        group.state is ConnectivityAssertionState.ASSERTED
        for symbol in symbols
        for group in symbol.internal_connectivity_groups
    )
    non_pending_port_count = sum(
        port.annotation_status is not AnnotationStatus.PENDING_HUMAN_REVIEW
        for symbol in symbols
        for port in symbol.ports
    )
    non_pending_group_count = sum(
        group.annotation_status is not AnnotationStatus.PENDING_HUMAN_REVIEW
        for symbol in symbols
        for group in symbol.internal_connectivity_groups
    )
    critical_capable_count = sum(
        library.can_drive_critical(symbol.identity) for symbol in symbols
    )
    union_capable_pair_count = sum(
        library.can_assert_electrical_union(
            symbol.identity,
            first.port_id,
            second.port_id,
        )
        for symbol in symbols
        for first, second in combinations(symbol.ports, 2)
    )
    pending_review_count = review_status_counts.get(
        ReviewItemStatus.PENDING_HUMAN_REVIEW.value,
        0,
    )
    safe = (
        workflow.get("document_status")
        == ReviewDocumentStatus.PENDING_HUMAN_REVIEW.value
        and pending_review_count == len(symbols)
        and annotation_status_counts.get(
            AnnotationStatus.PENDING_HUMAN_REVIEW.value,
            0,
        )
        == len(symbols)
        and registry_status_counts.get(RegistryStatus.UNKNOWN.value, 0)
        == len(symbols)
        and non_pending_port_count == 0
        and non_pending_group_count == 0
        and critical_count == 0
        and asserted_group_count == 0
        and critical_capable_count == 0
        and union_capable_pair_count == 0
    )
    return {
        "safe_pending_contract": safe,
        "document_status": workflow.get("document_status"),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "annotation_status_counts": dict(
            sorted(annotation_status_counts.items())
        ),
        "registry_status_counts": dict(sorted(registry_status_counts.items())),
        "non_pending_port_count": non_pending_port_count,
        "non_pending_connectivity_group_count": non_pending_group_count,
        "critical_issue_eligible_count": critical_count,
        "critical_capable_count": critical_capable_count,
        "asserted_connectivity_group_count": asserted_group_count,
        "asserted_union_capable_pair_count": union_capable_pair_count,
    }


def _canonicalize_document(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(document, ensure_ascii=False))
    geometry = payload.get("geometry_definitions")
    if isinstance(geometry, list):
        for row in geometry:
            if isinstance(row, dict):
                _sort_aliases_and_sources(row)
        geometry.sort(key=_geometry_key)

    symbols = payload.get("symbols")
    if isinstance(symbols, list):
        symbols.sort(key=_symbol_key)
        for rank, row in enumerate(symbols, start=1):
            if not isinstance(row, dict):
                continue
            row["backlog_rank"] = rank
            for field in ("review_reason_codes", "definition_names"):
                if isinstance(row.get(field), list):
                    row[field].sort(key=_text_key)
            _sort_aliases_and_sources(row)
            _sort_dependencies(row, "geometry_dependencies", _geometry_dependency_key)
            _sort_dependencies(row, "symbol_dependencies", _symbol_dependency_key)
            ports = row.get("ports")
            if isinstance(ports, list):
                ports.sort(key=lambda item: _text_key(item.get("port_id")))
                for port in ports:
                    if not isinstance(port, dict):
                        continue
                    for field in ("aliases", "source_ids"):
                        if isinstance(port.get(field), list):
                            port[field].sort(key=_text_key)
            groups = row.get("internal_connectivity_groups")
            if isinstance(groups, list):
                groups.sort(key=lambda item: _text_key(item.get("group_id")))
                for group in groups:
                    if not isinstance(group, dict):
                        continue
                    for field in ("port_ids", "source_ids"):
                        if isinstance(group.get(field), list):
                            group[field].sort(key=_text_key)
    return payload


def _sort_aliases_and_sources(row: dict[str, Any]) -> None:
    aliases = row.get("aliases")
    if isinstance(aliases, list):
        aliases.sort(
            key=lambda item: (
                _text_key(item.get("namespace")),
                _text_key(item.get("value")),
                _text_key(item.get("source_id")),
            )
        )
    sources = row.get("sources")
    if isinstance(sources, list):
        sources.sort(
            key=lambda item: (
                _text_key(item.get("source_id")),
                _text_key(item.get("source_kind")),
                _text_key(item.get("locator")),
                _text_key(item.get("project_id")),
                bool(item.get("held_out")),
            )
        )


def _sort_dependencies(
    row: dict[str, Any],
    field: str,
    key: Any,
) -> None:
    items = row.get(field)
    if isinstance(items, list):
        items.sort(key=key)


def _geometry_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _text_key(row.get("definition_id")),
        _text_key(row.get("version")),
        _text_key(row.get("fingerprint")),
    )


def _symbol_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _text_key(row.get("family")),
        _text_key(row.get("version")),
        _text_key(row.get("fingerprint")),
    )


def _geometry_dependency_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    target = row.get("target")
    target = target if isinstance(target, Mapping) else {}
    return (
        _text_key(row.get("dependency_id")),
        *_geometry_key(target),
    )


def _symbol_dependency_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    target = row.get("target")
    target = target if isinstance(target, Mapping) else {}
    return (
        _text_key(row.get("dependency_id")),
        *_symbol_key(target),
    )


def _text_key(value: Any) -> tuple[str, str]:
    text = "" if value is None else str(value)
    return (text.casefold(), text)


def _empty_backlog() -> dict[str, Any]:
    return {
        "$schema": REVIEW_SCHEMA_FILENAME,
        "schema_version": SCHEMA_VERSION,
        "review_workflow": {
            "workflow_version": REVIEW_WORKFLOW_VERSION,
            "document_status": (
                ReviewDocumentStatus.PENDING_HUMAN_REVIEW.value
            ),
            "notes": None,
        },
        "geometry_definitions": [],
        "symbols": [],
    }


def _artifact_issue(code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "ERROR",
        "message": message,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "BACKLOG_FILENAME",
    "SUMMARY_FILENAME",
    "SUMMARY_SCHEMA_VERSION",
    "VALIDATION_FILENAME",
    "VALIDATION_SCHEMA_VERSION",
    "build_symbol_review_artifacts",
    "write_symbol_review_artifacts",
]
