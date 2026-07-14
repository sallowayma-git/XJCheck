from __future__ import annotations

import csv
import json
from pathlib import Path

from dwg_audit.report.corpus_census import evaluate_corpus_census
from dwg_audit.report.corpus_census import write_corpus_census_artifacts


def _file_census(
    *,
    status: str = "COMPLETE",
    scale_status: str = "DECLARED",
    paper_native: int = 0,
    viewports: int = 0,
    xrefs: int = 0,
    missing_xrefs: list[str] | None = None,
    proxies: dict[str, int] | None = None,
    virtual_failures: int = 0,
    semantic: dict[str, int] | None = None,
    shadow: dict[str, int] | None = None,
    error_codes: tuple[str, ...] = (),
    warning_codes: tuple[str, ...] = (),
) -> dict[str, object]:
    proxies = proxies or {}
    semantic = semantic or {}
    shadow = shadow or {}
    return {
        "schema_version": "extraction-census-v2",
        "status": status,
        "complete": status == "COMPLETE",
        "scale_status": scale_status,
        "paper_space_entity_count": paper_native + viewports,
        "paper_space_native_entity_count": paper_native,
        "paper_space_viewport_count": viewports,
        "xref_count": xrefs,
        "xref_definitions": [{} for _ in range(xrefs)],
        "missing_xrefs": list(missing_xrefs or []),
        "proxy_entity_count": sum(proxies.values()),
        "proxy_entity_counts": proxies,
        "unsupported_entity_count": sum(semantic.values()),
        "unsupported_entity_counts": semantic,
        "shadow_unsupported_entity_count": sum(shadow.values()),
        "shadow_unsupported_entity_counts": shadow,
        "virtual_expansion_failures": [
            {"code": "VIRTUAL_EXPANSION_FAILED"} for _ in range(virtual_failures)
        ],
        "errors": [{"code": code} for code in error_codes],
        "warnings": [{"code": code} for code in warning_codes],
    }


def _write_project(
    project_dir: Path,
    project_id: str,
    files: list[dict[str, object]],
) -> None:
    findings = project_dir / "findings"
    findings.mkdir(parents=True)
    census = {
        "schema_version": "extraction-census-project-v1",
        "project_id": project_id,
        "file_count": len(files),
        "files": files,
    }
    status_counts: dict[str, int] = {}
    scale_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    warning_counts: dict[str, int] = {}
    semantic_counts: dict[str, int] = {}
    shadow_counts: dict[str, int] = {}
    for item in files:
        _increment(status_counts, str(item["status"]))
        _increment(scale_counts, str(item["scale_status"]))
        for diagnostic in item["errors"]:  # type: ignore[index]
            _increment(error_counts, diagnostic["code"])
        for diagnostic in item["warnings"]:  # type: ignore[index]
            _increment(warning_counts, diagnostic["code"])
        _merge_counts(semantic_counts, item["unsupported_entity_counts"])  # type: ignore[arg-type]
        _merge_counts(shadow_counts, item["shadow_unsupported_entity_counts"])  # type: ignore[arg-type]
    summary = {
        "schema_version": "extraction-census-summary-v1",
        "project_id": project_id,
        "file_count": len(files),
        "status_counts": status_counts,
        "scale_status_counts": scale_counts,
        "paper_native_file_count": sum(
            int(item["paper_space_native_entity_count"]) > 0 for item in files
        ),
        "viewport_layout_file_count": sum(
            int(item["paper_space_viewport_count"]) > 0 for item in files
        ),
        "xref_file_count": sum(int(item["xref_count"]) > 0 for item in files),
        "proxy_file_count": sum(
            int(item["proxy_entity_count"]) > 0 for item in files
        ),
        "virtual_expansion_failure_file_count": sum(
            bool(item["virtual_expansion_failures"]) for item in files
        ),
        "error_code_counts": error_counts,
        "warning_code_counts": warning_counts,
        "semantic_unsupported_entity_counts": semantic_counts,
        "shadow_unsupported_entity_counts": shadow_counts,
    }
    (findings / "extraction_census.json").write_text(
        json.dumps(census), encoding="utf-8"
    )
    (findings / "extraction_census_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )


def _increment(counts: dict[str, int], key: str, value: int = 1) -> None:
    counts[key] = counts.get(key, 0) + value


def _merge_counts(target: dict[str, int], values: dict[str, int]) -> None:
    for key, value in values.items():
        _increment(target, key, value)


def test_evaluate_corpus_census_aggregates_valid_projects_deterministically(
    tmp_path: Path,
) -> None:
    p001 = tmp_path / "P001"
    p003 = tmp_path / "P003"
    _write_project(
        p001,
        "Transformer protection",
        [
            _file_census(
                paper_native=4,
                viewports=2,
                xrefs=1,
                missing_xrefs=["missing.dwg"],
                proxies={"ACAD_PROXY_ENTITY": 3},
                virtual_failures=2,
                semantic={"CIRCLE": 5, "ARC": 2},
                shadow={"HATCH": 7},
                warning_codes=("UNITS_UNSPECIFIED",),
            ),
            _file_census(
                scale_status="UNRESOLVED",
                semantic={"CIRCLE": 1},
                error_codes=("READ_FAILED",),
            ),
        ],
    )
    _write_project(
        p003,
        "Station network",
        [_file_census(semantic={"SPLINE": 6}, shadow={"SPLINE": 6})],
    )

    result = evaluate_corpus_census(
        {"P003": p003, "P001": p001},
        splits={"P001": "calibration", "P003": "held-out-validation"},
    )

    assert [row["project_alias"] for row in result["projects"]] == ["P001", "P003"]
    assert [row["status"] for row in result["projects"]] == ["VALID", "VALID"]
    assert result["projects"][1]["is_held_out"] is True
    assert result["projects"][0]["semantic_unsupported_entity_counts"] == {
        "ARC": 2,
        "CIRCLE": 6,
    }
    assert result["projects"][0]["xref_count"] == 1
    assert result["projects"][0]["missing_xref_count"] == 1
    assert result["projects"][0]["virtual_expansion_failure_count"] == 2

    summary = result["summary"]
    assert summary["status"] == "VALID"
    assert summary["held_out_usage"] == "reporting_only"
    assert summary["held_out_project_count"] == 1
    assert summary["observed_metrics"]["file_status_counts"] == {"COMPLETE": 3}
    assert summary["observed_metrics"]["scale_status_counts"] == {
        "DECLARED": 2,
        "UNRESOLVED": 1,
    }
    assert summary["observed_metrics"]["semantic_unsupported_entity_count"] == 14
    assert summary["observed_metrics"]["shadow_unsupported_entity_counts"] == {
        "HATCH": 7,
        "SPLINE": 6,
    }
    assert summary["complete_corpus_metrics"] == summary["observed_metrics"]


def test_missing_project_remains_unavailable_and_corpus_is_not_clean(
    tmp_path: Path,
) -> None:
    healthy = tmp_path / "healthy"
    _write_project(healthy, "Healthy", [_file_census()])

    result = evaluate_corpus_census(
        {"MISSING": tmp_path / "not-written", "VALID": healthy},
        held_out_projects={"MISSING"},
    )

    missing = result["projects"][0]
    assert missing["status"] == "MISSING"
    assert missing["file_count"] is None
    assert missing["semantic_unsupported_entity_count"] is None
    assert missing["artifact_status"] == {
        "cross_validation": "not_evaluated",
        "extraction_census": "missing",
        "extraction_census_summary": "missing",
    }
    summary = result["summary"]
    assert summary["status"] == "MISSING"
    assert summary["all_projects_valid"] is False
    assert summary["valid_project_count"] == 1
    assert summary["observed_metrics"]["project_count"] == 1
    assert summary["observed_metrics"]["file_count"] == 1
    assert summary["complete_corpus_metrics"] is None
    assert summary["held_out_valid_project_count"] == 0


def test_invalid_or_inconsistent_artifacts_fail_closed(tmp_path: Path) -> None:
    invalid_json = tmp_path / "invalid-json" / "findings"
    invalid_json.mkdir(parents=True)
    (invalid_json / "extraction_census.json").write_text("{", encoding="utf-8")
    (invalid_json / "extraction_census_summary.json").write_text("{}", encoding="utf-8")

    mismatch = tmp_path / "mismatch"
    _write_project(mismatch, "Mismatch", [_file_census(semantic={"ARC": 2})])
    summary_path = mismatch / "findings" / "extraction_census_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["semantic_unsupported_entity_counts"] = {}
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    result = evaluate_corpus_census(
        {"INVALID_JSON": invalid_json.parent, "MISMATCH": mismatch}
    )

    assert result["summary"]["status"] == "INVALID"
    assert result["summary"]["valid_project_count"] == 0
    assert result["summary"]["observed_metrics"]["file_count"] is None
    assert result["summary"]["complete_corpus_metrics"] is None
    assert all(row["status"] == "INVALID" for row in result["projects"])
    mismatch_row = result["projects"][1]
    assert mismatch_row["artifact_status"]["cross_validation"] == "invalid"
    assert mismatch_row["semantic_unsupported_entity_count"] is None


def test_file_complete_flag_must_match_structural_status(tmp_path: Path) -> None:
    project = tmp_path / "project"
    file_census = _file_census(status="INCOMPLETE")
    file_census["complete"] = True
    _write_project(project, "Mismatch", [file_census])

    result = evaluate_corpus_census({"P001": project})

    assert result["projects"][0]["status"] == "INVALID"
    assert any(
        "complete does not match structural status"
        in message
        for message in result["projects"][0]["artifact_errors"][
            "extraction_census"
        ]
    )


def test_write_corpus_census_artifacts_serializes_nested_metrics(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    _write_project(
        project,
        "项目 A",
        [_file_census(semantic={"CIRCLE": 2}, warning_codes=("WARN",))],
    )
    evaluation = evaluate_corpus_census({"P001": project})

    paths = write_corpus_census_artifacts(evaluation, tmp_path / "evidence")

    with paths["by_project"].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["project_id"] == "项目 A"
    assert rows[0]["semantic_unsupported_entity_counts"] == '{"CIRCLE":2}'
    assert rows[0]["warning_code_counts"] == '{"WARN":1}'
    written_summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert written_summary == evaluation["summary"]
