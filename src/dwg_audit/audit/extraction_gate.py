from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any


COMPLETE = "COMPLETE"
INCOMPLETE_EXTRACTION = "INCOMPLETE_EXTRACTION"
NOT_APPLICABLE = "NOT_APPLICABLE"

_SUCCESSFUL_CONVERSION_STATUSES = {"cached", "converted"}
_WARNING_FAILURE_CODES = {
    "read_dxf_failed": "DXF_READ_FAILED",
    "dxf_read_failed": "DXF_READ_FAILED",
    "missing_dxf": "CONVERSION_FAILED",
}


@dataclass(frozen=True, slots=True)
class ExtractionGateResult:
    analysis_status: str
    clean_conclusion_allowed: bool
    incomplete_page_count: int
    incomplete_sheet_ids: list[str]
    failure_code_counts: dict[str, int]
    pages: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _value(record: object | None, name: str, default: Any = None) -> Any:
    if record is None:
        return default
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _classification_map(classifications: object | None) -> dict[str, object]:
    if classifications is None:
        return {}
    if isinstance(classifications, Mapping):
        return {str(key): value for key, value in classifications.items()}
    return {
        str(sheet_id): item
        for item in classifications  # type: ignore[union-attr]
        if (sheet_id := _value(item, "sheet_id")) is not None
    }


def _records_by_sheet(records: Iterable[object]) -> Counter[str]:
    return Counter(
        str(sheet_id)
        for record in records
        if (sheet_id := _value(record, "sheet_id")) is not None
    )


def _warning_map(warnings: Iterable[object]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for warning in warnings:
        sheet_id = _value(warning, "sheet_id")
        if sheet_id is None:
            continue
        code = str(_value(warning, "code", "")).strip()
        if code:
            result.setdefault(str(sheet_id), []).append(code)
    return result


def _executors_by_sheet(extractor_runs: Iterable[object]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for run in extractor_runs:
        executor = _value(run, "executed_extractor")
        if not executor:
            continue
        sheet_ids = _value(run, "sheet_ids")
        if sheet_ids is None:
            single_sheet_id = _value(run, "sheet_id")
            sheet_ids = [] if single_sheet_id is None else [single_sheet_id]
        if isinstance(sheet_ids, str):
            sheet_ids = [sheet_ids]
        for sheet_id in sheet_ids:
            key = str(sheet_id)
            name = str(executor)
            if name not in result.setdefault(key, []):
                result[key].append(name)
    return result


def _census_map(censuses: Iterable[object]) -> dict[str, object]:
    return {
        str(file_id): item
        for item in censuses
        if (file_id := _value(item, "file_id")) is not None
    }


def _diagnostic_codes(record: object | None, field: str) -> list[str]:
    values = _value(record, field, []) or []
    return sorted(
        {
            str(code)
            for item in values
            if (code := _value(item, "code")) is not None
        }
    )


def _source_failure(source: object | None) -> str | None:
    if source is None:
        return "CONVERSION_FAILED"
    status = str(_value(source, "conversion_status", "")).strip().casefold()
    if status == "missing_converter":
        return "READER_UNAVAILABLE"
    if not bool(_value(source, "valid_dwg_header", True)) or status == "failed_invalid_header":
        return "INVALID_SOURCE_HEADER"
    if status not in _SUCCESSFUL_CONVERSION_STATUSES:
        return "CONVERSION_FAILED"
    return None


def evaluate_extraction_completeness(
    pages: Iterable[object],
    source_files: Iterable[object],
    texts: Iterable[object],
    lines: Iterable[object],
    blocks: Iterable[object],
    polylines: Iterable[object],
    extraction_warnings: Iterable[object],
    extractor_runs: Iterable[object],
    classifications: object | None = None,
    extraction_censuses: Iterable[object] = (),
) -> ExtractionGateResult:
    """Evaluate whether every audit-required page was actually extractable.

    The gate deliberately evaluates CAD primitives and extractor execution, not
    pair counts: a valid, sparse drawing may legitimately produce zero pairs.
    Inputs accept domain dataclasses or dict-shaped records so the function can
    also evaluate persisted artifacts without mutation.
    """

    page_list = list(pages)
    sources = {str(_value(item, "file_id")): item for item in source_files}
    classifications_by_sheet = _classification_map(classifications)
    primitive_counters = {
        "text": _records_by_sheet(texts),
        "line": _records_by_sheet(lines),
        "block": _records_by_sheet(blocks),
        "polyline": _records_by_sheet(polylines),
    }
    warnings_by_sheet = _warning_map(extraction_warnings)
    executors_by_sheet = _executors_by_sheet(extractor_runs)
    censuses_by_file = _census_map(extraction_censuses)

    page_results: list[dict[str, Any]] = []
    incomplete_sheet_ids: list[str] = []
    failure_counts: Counter[str] = Counter()

    for page in page_list:
        sheet_id = str(_value(page, "sheet_id", ""))
        file_id = str(_value(page, "file_id", ""))
        audit_role = str(_value(page, "audit_role", "") or "")
        classification = classifications_by_sheet.get(sheet_id)
        classification_disposition = _value(classification, "audit_disposition")
        page_disposition = _value(page, "audit_disposition")
        audit_disposition = (
            classification_disposition
            or page_disposition
            or ("audit_required" if audit_role in {"primary", "supplemental"} else None)
        )
        audit_disposition = str(audit_disposition or "")
        expected_audit = (
            audit_role in {"primary", "supplemental"}
            or classification_disposition == "audit_required"
            or page_disposition == "audit_required"
        )
        stable_skip = audit_role == "skip" or audit_disposition == "skip_stable"

        primitive_counts = {
            name: counter[sheet_id]
            for name, counter in primitive_counters.items()
        }
        primitive_counts["total"] = sum(primitive_counts.values())
        warning_codes = sorted(set(warnings_by_sheet.get(sheet_id, [])))
        census = censuses_by_file.get(file_id)
        census_status = str(_value(census, "status", "") or "") or None
        census_error_codes = _diagnostic_codes(census, "errors")
        census_warning_codes = _diagnostic_codes(census, "warnings")
        executors = executors_by_sheet.get(sheet_id, [])
        executed_extractor = executors[0] if executors else None
        failure_codes: list[str] = []

        if stable_skip or not expected_audit:
            status = NOT_APPLICABLE
        else:
            source_failure = _source_failure(sources.get(file_id))
            if source_failure is not None:
                failure_codes.append(source_failure)
            else:
                for warning_code in warning_codes:
                    failure_code = _WARNING_FAILURE_CODES.get(warning_code.casefold())
                    if failure_code and failure_code not in failure_codes:
                        failure_codes.append(failure_code)
                if census_status in {"INCOMPLETE", "FAILED"}:
                    if census_error_codes:
                        failure_codes.extend(
                            f"CENSUS_{code}"
                            for code in census_error_codes
                            if f"CENSUS_{code}" not in failure_codes
                        )
                    else:
                        failure_codes.append(
                            f"EXTRACTION_CENSUS_{census_status}"
                        )
                if not failure_codes and primitive_counts["total"] == 0:
                    failure_codes.append("ZERO_PRIMITIVES")
                if not failure_codes and executed_extractor is None:
                    failure_codes.append("AUDIT_EXTRACTOR_NOT_EXECUTED")
            status = INCOMPLETE_EXTRACTION if failure_codes else COMPLETE

        if status == INCOMPLETE_EXTRACTION:
            incomplete_sheet_ids.append(sheet_id)
            failure_counts.update(failure_codes)

        page_results.append(
            {
                "sheet": sheet_id,
                "file": file_id,
                "filename": str(_value(page, "filename", "") or ""),
                "audit_role": audit_role,
                "audit_disposition": audit_disposition,
                "status": status,
                "failure_codes": failure_codes,
                "primitive_counts": primitive_counts,
                "warning_codes": warning_codes,
                "census_status": census_status,
                "census_error_codes": census_error_codes,
                "census_warning_codes": census_warning_codes,
                "census_metrics": {
                    "scale_status": _value(census, "scale_status"),
                    "paper_space_native_entity_count": _value(
                        census, "paper_space_native_entity_count", 0
                    ),
                    "paper_space_viewport_count": _value(
                        census, "paper_space_viewport_count", 0
                    ),
                    "semantic_coverage_complete": _value(
                        census, "semantic_coverage_complete"
                    ),
                    "shadow_coverage_complete": _value(
                        census, "shadow_coverage_complete"
                    ),
                },
                "executed_extractor": executed_extractor,
            }
        )

    analysis_status = INCOMPLETE_EXTRACTION if incomplete_sheet_ids else COMPLETE
    return ExtractionGateResult(
        analysis_status=analysis_status,
        clean_conclusion_allowed=analysis_status == COMPLETE,
        incomplete_page_count=len(incomplete_sheet_ids),
        incomplete_sheet_ids=incomplete_sheet_ids,
        failure_code_counts=dict(sorted(failure_counts.items())),
        pages=page_results,
    )
