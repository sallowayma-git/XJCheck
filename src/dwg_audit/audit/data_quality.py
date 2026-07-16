from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import SheetRecord


DATA_QUALITY_RULE_ID = "R-DATA-INCOMPLETE-EXTRACTION"


def load_extraction_completeness(project_dir: Path) -> dict[str, Any] | None:
    """Load the extraction gate sidecar, preserving pre-gate bundle compatibility."""

    path = project_dir / "extraction_completeness.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid extraction completeness artifact: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(
            f"Invalid extraction completeness artifact: {path}: expected a JSON object"
        )
    return payload


def build_incomplete_extraction_issues(
    project_dir: Path,
    existing_issues: list[Issue],
    pages: list[SheetRecord],
) -> list[Issue]:
    """Build pair-independent review issues for an incomplete extraction run."""

    payload = load_extraction_completeness(project_dir)
    if payload is None or _is_complete(payload):
        return []

    page_map = {page.sheet_id: page for page in pages}
    failures = _failed_pages(payload)
    if not failures:
        failures = [{}]

    used_ids = {issue.issue_id for issue in existing_issues}
    issues: list[Issue] = []
    next_id = 1
    for failure in failures:
        while f"DQE{next_id:04d}" in used_ids:
            next_id += 1
        issue_id = f"DQE{next_id:04d}"
        used_ids.add(issue_id)
        next_id += 1

        sheet_id = _optional_text(failure.get("sheet_id", failure.get("sheet")))
        page = page_map.get(sheet_id or "")
        failure_codes = _failure_codes(failure, payload)
        warnings = _string_list(failure.get("warnings", failure.get("warning_codes")))
        primitive_count, primitive_counts = _primitive_evidence(failure)
        audit_scope = _audit_scope(failure, page, payload)
        filename = _optional_text(failure.get("filename")) or (page.filename if page else None)
        sheet_no = _optional_text(failure.get("sheet_no")) or (page.sheet_no if page else None)
        file_id = _optional_text(failure.get("file_id", failure.get("file"))) or (
            page.file_id if page else None
        )
        sheet_order = _optional_int(failure.get("sheet_order"))
        if sheet_order is None and page is not None:
            sheet_order = page.sheet_order

        scope_label = filename or sheet_id or "project"
        codes_label = ", ".join(failure_codes) if failure_codes else "unspecified gate failure"
        evidence = {
            "failure_codes": failure_codes,
            "primitive_count": primitive_count,
            "primitive_counts": primitive_counts,
            "warnings": warnings,
            "audit_scope": audit_scope,
            "filename": filename,
            "sheet_no": sheet_no,
            "sheet_order": sheet_order,
            "completeness_status": _status(payload),
        }
        issues.append(
            Issue(
                issue_id=issue_id,
                rule_id=DATA_QUALITY_RULE_ID,
                issue_type=DATA_QUALITY_RULE_ID,
                severity="review",
                status="review",
                confidence=1.0,
                message=f"Extraction is incomplete for {scope_label}: {codes_label}.",
                title="识别数据不完整",
                summary=f"{scope_label} 未通过识别完整性门禁，审计结果不得视为 clean。",
                explanation=(
                    "该页需要审计，但转换或实体抽取未达到完整性要求；当前 Pair/Issue "
                    "结果可能只是输入数据不完整造成的假阴性。"
                ),
                recommended_action=(
                    "检查 Reader/ODA 转换日志、failure codes 与 warnings，修复转换或关键实体抽取后"
                    "重新执行 analyze-project 和 run-audit；在复跑成功前保持人工复核状态。"
                ),
                sheet_id=sheet_id or (page.sheet_id if page else None),
                file_id=file_id,
                pair_id=None,
                line_group_id=None,
                left_value=None,
                right_value=None,
                filename=filename,
                sheet_no=sheet_no,
                sheet_order=sheet_order,
                evidence=evidence,
                sheet_ids=[sheet_id] if sheet_id else [],
            )
        )
    return issues


def _is_complete(payload: dict[str, Any]) -> bool:
    explicit = payload.get("complete", payload.get("is_complete"))
    if isinstance(explicit, bool):
        return explicit
    return _status(payload) in {"COMPLETE", "COMPLETE_EXTRACTION", "PASS", "PASSED"}


def _status(payload: dict[str, Any]) -> str:
    value = payload.get(
        "analysis_status",
        payload.get("status", payload.get("project_status", "")),
    )
    return str(value).strip().upper()


def _failed_pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_pages: object = payload.get("page_results")
    if raw_pages is None:
        raw_pages = payload.get("pages", payload.get("sheets", []))
    if not isinstance(raw_pages, list):
        raise ValueError(
            "Invalid extraction completeness artifact: page_results/pages must be an array"
        )

    failures: list[dict[str, Any]] = []
    for index, item in enumerate(raw_pages):
        if not isinstance(item, dict):
            raise ValueError(
                "Invalid extraction completeness artifact: "
                f"page result at index {index} must be an object"
            )
        if _page_is_incomplete(item):
            failures.append(item)
    return sorted(
        failures,
        key=lambda item: (
            _optional_int(item.get("sheet_order")) or 0,
            _optional_text(item.get("sheet_id", item.get("sheet"))) or "",
            _optional_text(item.get("file_id", item.get("file"))) or "",
            _optional_text(item.get("filename")) or "",
        ),
    )


def _page_is_incomplete(item: dict[str, Any]) -> bool:
    explicit = item.get("complete", item.get("is_complete"))
    if isinstance(explicit, bool):
        return not explicit
    status = str(item.get("status", "")).strip().upper()
    if status:
        return status in {"INCOMPLETE", "INCOMPLETE_EXTRACTION", "FAILED", "FAIL"}
    return bool(_failure_codes(item, {}))


def _failure_codes(page: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    values = page.get("failure_codes")
    if values is None:
        values = page.get("failures")
    if values is None:
        values = payload.get("failure_codes", payload.get("failures", []))
    if not isinstance(values, list):
        values = [values]
    codes: list[str] = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("code", value.get("failure_code"))
        text = _optional_text(value)
        if text and text not in codes:
            codes.append(text)
    return codes


def _primitive_evidence(page: dict[str, Any]) -> tuple[int | None, dict[str, int]]:
    primitive_counts = page.get("primitive_counts", {})
    if not isinstance(primitive_counts, dict):
        primitive_counts = {}
    normalized_counts: dict[str, int] = {}
    for key, value in primitive_counts.items():
        count = _optional_int(value)
        if count is not None:
            normalized_counts[str(key)] = count
    primitive_count = _optional_int(page.get("primitive_count"))
    if primitive_count is None and normalized_counts:
        primitive_count = normalized_counts.get("total")
        if primitive_count is None:
            primitive_count = sum(normalized_counts.values())
    return primitive_count, normalized_counts


def _audit_scope(
    failure: dict[str, Any],
    page: SheetRecord | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    scope = failure.get("audit_scope")
    if isinstance(scope, dict):
        return scope
    flat_scope = {
        key: failure.get(key)
        for key in ("audit_disposition", "audit_role", "executed_extractor")
        if failure.get(key) is not None
    }
    if page is not None:
        page_scope = {
            "scope_type": "page",
            "audit_disposition": page.audit_disposition,
            "audit_role": page.audit_role,
            "route_target": page.route_target,
            "is_primary_audit_candidate": page.is_primary_audit_candidate,
        }
        return {**page_scope, **flat_scope}
    if flat_scope:
        return {"scope_type": "page", **flat_scope}
    project_scope = payload.get("audit_scope")
    if isinstance(project_scope, dict) and project_scope:
        return {"scope_type": "project", **project_scope}
    return {"scope_type": "project"}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        value = [] if value is None else [value]
    return [text for item in value if (text := _optional_text(item))]


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
