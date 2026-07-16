from __future__ import annotations

from types import SimpleNamespace

import pytest

from dwg_audit.audit.extraction_gate import evaluate_extraction_completeness


def _page(
    sheet_id: str = "S1",
    file_id: str = "F1",
    *,
    audit_role: str = "primary",
    audit_disposition: str | None = "audit_required",
) -> SimpleNamespace:
    return SimpleNamespace(
        sheet_id=sheet_id,
        file_id=file_id,
        filename=f"{file_id}.dwg",
        audit_role=audit_role,
        audit_disposition=audit_disposition,
    )


def _source(
    file_id: str = "F1",
    *,
    conversion_status: str = "converted",
    valid_dwg_header: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        file_id=file_id,
        conversion_status=conversion_status,
        valid_dwg_header=valid_dwg_header,
    )


def _primitive(sheet_id: str = "S1") -> SimpleNamespace:
    return SimpleNamespace(sheet_id=sheet_id)


def _run(sheet_id: str = "S1", executor: str = "WireDiagramExtractor") -> dict[str, object]:
    return {"executed_extractor": executor, "sheet_ids": [sheet_id], "pair_count": 0}


def _evaluate(
    *,
    pages=None,
    sources=None,
    texts=None,
    lines=None,
    blocks=None,
    polylines=None,
    warnings=None,
    runs=None,
    classifications=None,
    censuses=None,
):
    return evaluate_extraction_completeness(
        pages or [_page()],
        [_source()] if sources is None else sources,
        [_primitive()] if texts is None else texts,
        [] if lines is None else lines,
        [] if blocks is None else blocks,
        [] if polylines is None else polylines,
        [] if warnings is None else warnings,
        [_run()] if runs is None else runs,
        classifications=classifications,
        extraction_censuses=[] if censuses is None else censuses,
    )


@pytest.mark.parametrize(
    ("source", "failure_code"),
    [
        (_source(conversion_status="missing_converter"), "READER_UNAVAILABLE"),
        (_source(valid_dwg_header=False), "INVALID_SOURCE_HEADER"),
        (_source(conversion_status="failed"), "CONVERSION_FAILED"),
    ],
)
def test_source_failures_block_clean_conclusion(source, failure_code: str) -> None:
    result = _evaluate(sources=[source], texts=[], runs=[])

    assert result.analysis_status == "INCOMPLETE_EXTRACTION"
    assert result.clean_conclusion_allowed is False
    assert result.pages[0]["failure_codes"] == [failure_code]
    assert result.failure_code_counts == {failure_code: 1}


def test_dxf_read_failure_is_reported_from_extraction_warning() -> None:
    result = _evaluate(
        texts=[],
        runs=[],
        warnings=[{"sheet_id": "S1", "code": "read_dxf_failed"}],
    )

    assert result.pages[0]["failure_codes"] == ["DXF_READ_FAILED"]
    assert result.pages[0]["warning_codes"] == ["read_dxf_failed"]


def test_zero_primitives_is_a_hard_failure_even_when_extractor_ran() -> None:
    result = _evaluate(texts=[])

    assert result.pages[0]["primitive_counts"] == {
        "text": 0,
        "line": 0,
        "block": 0,
        "polyline": 0,
        "total": 0,
    }
    assert result.pages[0]["failure_codes"] == ["ZERO_PRIMITIVES"]


def test_audit_extractor_must_have_an_execution_record_for_the_page() -> None:
    result = _evaluate(runs=[])

    assert result.pages[0]["failure_codes"] == ["AUDIT_EXTRACTOR_NOT_EXECUTED"]


def test_sparse_page_with_zero_pairs_is_complete() -> None:
    result = _evaluate()

    assert result.analysis_status == "COMPLETE"
    assert result.clean_conclusion_allowed is True
    assert result.pages[0]["status"] == "COMPLETE"
    assert result.pages[0]["executed_extractor"] == "WireDiagramExtractor"


def test_structurally_incomplete_census_blocks_clean_conclusion() -> None:
    result = _evaluate(
        censuses=[
            {
                "file_id": "F1",
                "status": "INCOMPLETE",
                "errors": [
                    {"code": "XREF_CONTENT_NOT_LOADED"},
                    {"code": "LAYOUT_NOT_CONSUMED"},
                ],
                "warnings": [{"code": "UNITS_UNSPECIFIED"}],
                "scale_status": "UNRESOLVED",
                "paper_space_native_entity_count": 3,
                "paper_space_viewport_count": 1,
                "semantic_coverage_complete": False,
                "shadow_coverage_complete": True,
            }
        ]
    )

    assert result.clean_conclusion_allowed is False
    assert result.pages[0]["failure_codes"] == [
        "CENSUS_LAYOUT_NOT_CONSUMED",
        "CENSUS_XREF_CONTENT_NOT_LOADED",
    ]
    assert result.pages[0]["census_status"] == "INCOMPLETE"
    assert result.pages[0]["census_warning_codes"] == ["UNITS_UNSPECIFIED"]
    assert result.pages[0]["census_metrics"] == {
        "scale_status": "UNRESOLVED",
        "paper_space_native_entity_count": 3,
        "paper_space_viewport_count": 1,
        "semantic_coverage_complete": False,
        "shadow_coverage_complete": True,
    }


def test_stable_skip_page_is_not_applicable_despite_failed_conversion() -> None:
    result = _evaluate(
        pages=[_page(audit_role="skip", audit_disposition="skip_stable")],
        sources=[_source(conversion_status="failed")],
        texts=[],
        runs=[],
    )

    assert result.analysis_status == "COMPLETE"
    assert result.pages[0]["status"] == "NOT_APPLICABLE"
    assert result.pages[0]["failure_codes"] == []


def test_mixed_pages_use_classification_override_and_aggregate_failures() -> None:
    pages = [
        _page("S1", "F1"),
        _page("S2", "F2", audit_role="secondary", audit_disposition="classify_only"),
        _page("S3", "F3", audit_role="secondary", audit_disposition="classify_only"),
    ]
    result = _evaluate(
        pages=pages,
        sources=[_source("F1"), _source("F2"), _source("F3")],
        texts=[_primitive("S1"), _primitive("S3")],
        runs=[_run("S1")],
        classifications={"S3": {"audit_disposition": "audit_required"}},
    )

    payload = result.to_dict()
    assert [page["status"] for page in payload["pages"]] == [
        "COMPLETE",
        "NOT_APPLICABLE",
        "INCOMPLETE_EXTRACTION",
    ]
    assert payload["incomplete_page_count"] == 1
    assert payload["incomplete_sheet_ids"] == ["S3"]
    assert payload["failure_code_counts"] == {"AUDIT_EXTRACTOR_NOT_EXECUTED": 1}


def test_classification_cannot_downgrade_page_marked_audit_required() -> None:
    result = _evaluate(
        pages=[_page(audit_role="secondary", audit_disposition="audit_required")],
        classifications={"S1": {"audit_disposition": "classify_only"}},
    )

    assert result.pages[0]["status"] == "COMPLETE"
