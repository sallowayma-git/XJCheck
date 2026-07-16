from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "corpus-extraction-census-v1"
SUMMARY_SCHEMA_VERSION = "corpus-extraction-census-summary-v1"

_PROJECT_CENSUS_SCHEMA = "extraction-census-project-v1"
_PROJECT_SUMMARY_SCHEMA = "extraction-census-summary-v1"
_FILE_CENSUS_SCHEMA = "extraction-census-v2"

_PROJECT_COUNT_FIELDS = (
    "paper_native_file_count",
    "viewport_layout_file_count",
    "xref_file_count",
    "proxy_file_count",
    "virtual_expansion_failure_file_count",
)
_PROJECT_MAPPING_FIELDS = (
    "status_counts",
    "scale_status_counts",
    "error_code_counts",
    "warning_code_counts",
    "semantic_unsupported_entity_counts",
    "shadow_unsupported_entity_counts",
)
_FILE_COUNT_FIELDS = (
    "paper_space_entity_count",
    "paper_space_native_entity_count",
    "paper_space_viewport_count",
    "xref_count",
    "proxy_entity_count",
    "unsupported_entity_count",
    "shadow_unsupported_entity_count",
)
_FILE_MAPPING_FIELDS = (
    "proxy_entity_counts",
    "unsupported_entity_counts",
    "shadow_unsupported_entity_counts",
)
_ROW_METRIC_FIELDS = (
    "file_count",
    "file_status_counts",
    "scale_status_counts",
    "paper_native_file_count",
    "paper_space_native_entity_count",
    "viewport_layout_file_count",
    "paper_space_viewport_count",
    "xref_file_count",
    "xref_count",
    "missing_xref_count",
    "proxy_file_count",
    "proxy_entity_count",
    "virtual_expansion_failure_file_count",
    "virtual_expansion_failure_count",
    "semantic_unsupported_entity_count",
    "semantic_unsupported_entity_counts",
    "shadow_unsupported_entity_count",
    "shadow_unsupported_entity_counts",
    "error_code_counts",
    "warning_code_counts",
)
_MAPPING_METRIC_FIELDS = frozenset(
    {
        "file_status_counts",
        "scale_status_counts",
        "semantic_unsupported_entity_counts",
        "shadow_unsupported_entity_counts",
        "error_code_counts",
        "warning_code_counts",
    }
)
_PREFERRED_COLUMNS = (
    "project_alias",
    "project_id",
    "split",
    "is_held_out",
    "status",
    "file_count",
    "file_status_counts",
    "scale_status_counts",
    "paper_native_file_count",
    "paper_space_native_entity_count",
    "viewport_layout_file_count",
    "paper_space_viewport_count",
    "xref_file_count",
    "xref_count",
    "missing_xref_count",
    "proxy_file_count",
    "proxy_entity_count",
    "virtual_expansion_failure_file_count",
    "virtual_expansion_failure_count",
    "semantic_unsupported_entity_count",
    "semantic_unsupported_entity_counts",
    "shadow_unsupported_entity_count",
    "shadow_unsupported_entity_counts",
    "error_code_counts",
    "warning_code_counts",
    "artifact_status",
    "artifact_errors",
    "project_dir",
)


def evaluate_corpus_census(
    project_dirs: Mapping[str, Path],
    *,
    splits: Mapping[str, str] | None = None,
    held_out_projects: Collection[str] | None = None,
) -> dict[str, Any]:
    """Evaluate persisted extraction censuses for a project corpus.

    Artifact validity and extraction health are intentionally separate. A
    ``VALID`` row means both JSON artifacts are readable, schema-valid, and
    mutually consistent; file-level ``status`` and ``scale_status`` values are
    retained as metrics rather than being reinterpreted as artifact validity.
    """

    split_map = {str(key): str(value) for key, value in (splits or {}).items()}
    held_out = {str(value) for value in (held_out_projects or ())}
    normalized_dirs = {str(alias): Path(path) for alias, path in project_dirs.items()}

    rows = [
        _evaluate_project(
            alias,
            normalized_dirs[alias],
            split=split_map.get(alias),
            is_held_out=alias in held_out or _is_held_out_split(split_map.get(alias)),
        )
        for alias in sorted(normalized_dirs)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "projects": rows,
        "summary": _summarize(rows),
    }


def write_corpus_census_artifacts(
    evaluation: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write deterministic per-project CSV and corpus-summary JSON artifacts."""

    rows = evaluation.get("projects")
    summary = evaluation.get("summary")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("evaluation projects must be a list of objects")
    if not isinstance(summary, dict):
        raise ValueError("evaluation summary must be an object")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "corpus_extraction_census_by_project.csv"
    summary_path = output_dir / "corpus_extraction_census_summary.json"
    _write_csv(rows, csv_path)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"by_project": csv_path, "summary": summary_path}


def _evaluate_project(
    alias: str,
    project_dir: Path,
    *,
    split: str | None,
    is_held_out: bool,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    findings_dir = project_dir / "findings"
    census, census_status, census_errors = _load_json_artifact(
        findings_dir / "extraction_census.json",
        _validate_project_census,
    )
    summary, summary_status, summary_errors = _load_json_artifact(
        findings_dir / "extraction_census_summary.json",
        _validate_project_summary,
    )

    artifact_status = {
        "extraction_census": census_status,
        "extraction_census_summary": summary_status,
    }
    artifact_errors: dict[str, list[str]] = {}
    if census_errors:
        artifact_errors["extraction_census"] = census_errors
    if summary_errors:
        artifact_errors["extraction_census_summary"] = summary_errors

    cross_errors: list[str] = []
    if census_status == "valid" and summary_status == "valid":
        cross_errors = _cross_validate(census, summary)
        artifact_status["cross_validation"] = "invalid" if cross_errors else "valid"
        if cross_errors:
            artifact_errors["cross_validation"] = cross_errors
    else:
        artifact_status["cross_validation"] = "not_evaluated"

    status = _project_status(artifact_status)
    project_id = None
    if census_status == "valid":
        project_id = census["project_id"]
    elif summary_status == "valid":
        project_id = summary["project_id"]

    row: dict[str, Any] = {
        "project_alias": alias,
        "project_id": project_id,
        "project_dir": str(project_dir),
        "split": split,
        "is_held_out": bool(is_held_out),
        "status": status,
        "artifact_status": artifact_status,
        "artifact_errors": artifact_errors,
    }
    row.update(_null_metrics())
    if status == "VALID":
        row.update(_derive_metrics(census["files"]))
    return row


def _load_json_artifact(
    path: Path,
    validator: Any,
) -> tuple[dict[str, Any], str, list[str]]:
    if not path.is_file():
        return {}, "missing", [f"missing artifact: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, "invalid", [f"unable to read JSON: {type(exc).__name__}"]
    if not isinstance(payload, dict):
        return {}, "invalid", ["artifact must be a JSON object"]
    errors = validator(payload)
    return payload, "invalid" if errors else "valid", errors


def _validate_project_census(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _require_schema(payload, _PROJECT_CENSUS_SCHEMA, errors)
    _require_nonempty_string(payload, "project_id", errors)
    file_count = _require_nonnegative_int(payload, "file_count", errors)
    files = payload.get("files")
    if not isinstance(files, list):
        errors.append("files must be a list")
        return errors
    if file_count is not None and file_count != len(files):
        errors.append(f"file_count mismatch: declared {file_count}, found {len(files)}")
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            errors.append(f"files[{index}] must be an object")
            continue
        errors.extend(_validate_file_census(item, index))
    return errors


def _validate_file_census(item: dict[str, Any], index: int) -> list[str]:
    prefix = f"files[{index}]"
    errors: list[str] = []
    if item.get("schema_version") != _FILE_CENSUS_SCHEMA:
        errors.append(f"{prefix}.schema_version must be {_FILE_CENSUS_SCHEMA!r}")
    for key in ("status", "scale_status"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            errors.append(f"{prefix}.{key} must be a non-empty string")
    if not isinstance(item.get("complete"), bool):
        errors.append(f"{prefix}.complete must be a boolean")
    status = item.get("status")
    if isinstance(status, str) and status not in {"COMPLETE", "INCOMPLETE", "FAILED"}:
        errors.append(f"{prefix}.status is unsupported: {status!r}")
    if isinstance(item.get("complete"), bool) and isinstance(status, str):
        expected_complete = status == "COMPLETE"
        if item["complete"] is not expected_complete:
            errors.append(
                f"{prefix}.complete does not match structural status {status!r}"
            )
    for key in _FILE_COUNT_FIELDS:
        _require_nonnegative_int(item, key, errors, prefix=prefix)
    for key in _FILE_MAPPING_FIELDS:
        _require_count_mapping(item, key, errors, prefix=prefix)
    xref_definitions = item.get("xref_definitions")
    if not isinstance(xref_definitions, list):
        errors.append(f"{prefix}.xref_definitions must be a list")
    elif any(not isinstance(value, dict) for value in xref_definitions):
        errors.append(f"{prefix}.xref_definitions entries must be objects")
    missing_xrefs = item.get("missing_xrefs")
    if not isinstance(missing_xrefs, list):
        errors.append(f"{prefix}.missing_xrefs must be a list")
    elif any(not isinstance(value, str) or not value for value in missing_xrefs):
        errors.append(f"{prefix}.missing_xrefs entries must be non-empty strings")
    _validate_diagnostics(
        item.get("virtual_expansion_failures"),
        f"{prefix}.virtual_expansion_failures",
        errors,
    )
    for key in ("warnings", "errors"):
        _validate_diagnostics(item.get(key), f"{prefix}.{key}", errors)

    _validate_declared_mapping_total(
        item,
        "proxy_entity_count",
        "proxy_entity_counts",
        prefix,
        errors,
    )
    _validate_declared_mapping_total(
        item,
        "unsupported_entity_count",
        "unsupported_entity_counts",
        prefix,
        errors,
    )
    _validate_declared_mapping_total(
        item,
        "shadow_unsupported_entity_count",
        "shadow_unsupported_entity_counts",
        prefix,
        errors,
    )
    xref_count = item.get("xref_count")
    if type(xref_count) is int and isinstance(xref_definitions, list):
        if xref_count != len(xref_definitions):
            errors.append(
                f"{prefix}.xref_count mismatch: declared {xref_count}, "
                f"found {len(xref_definitions)} definitions"
            )
    return errors


def _validate_project_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _require_schema(payload, _PROJECT_SUMMARY_SCHEMA, errors)
    _require_nonempty_string(payload, "project_id", errors)
    _require_nonnegative_int(payload, "file_count", errors)
    for key in _PROJECT_COUNT_FIELDS:
        _require_nonnegative_int(payload, key, errors)
    for key in _PROJECT_MAPPING_FIELDS:
        _require_count_mapping(payload, key, errors)
    return errors


def _cross_validate(census: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if census["project_id"] != summary["project_id"]:
        errors.append("project_id differs between census and summary")
    derived = _derive_metrics(census["files"])
    expected = {
        "file_count": derived["file_count"],
        "status_counts": derived["file_status_counts"],
        "scale_status_counts": derived["scale_status_counts"],
        "paper_native_file_count": derived["paper_native_file_count"],
        "viewport_layout_file_count": derived["viewport_layout_file_count"],
        "xref_file_count": derived["xref_file_count"],
        "proxy_file_count": derived["proxy_file_count"],
        "virtual_expansion_failure_file_count": derived[
            "virtual_expansion_failure_file_count"
        ],
        "error_code_counts": derived["error_code_counts"],
        "warning_code_counts": derived["warning_code_counts"],
        "semantic_unsupported_entity_counts": derived[
            "semantic_unsupported_entity_counts"
        ],
        "shadow_unsupported_entity_counts": derived[
            "shadow_unsupported_entity_counts"
        ],
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"summary {key} does not match extraction_census.json")
    return errors


def _derive_metrics(files: list[dict[str, Any]]) -> dict[str, Any]:
    statuses: Counter[str] = Counter()
    scales: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    semantic: Counter[str] = Counter()
    shadow: Counter[str] = Counter()

    for item in files:
        statuses[item["status"]] += 1
        scales[item["scale_status"]] += 1
        errors.update(value["code"] for value in item["errors"])
        warnings.update(value["code"] for value in item["warnings"])
        semantic.update(item["unsupported_entity_counts"])
        shadow.update(item["shadow_unsupported_entity_counts"])

    return {
        "file_count": len(files),
        "file_status_counts": dict(sorted(statuses.items())),
        "scale_status_counts": dict(sorted(scales.items())),
        "paper_native_file_count": sum(
            item["paper_space_native_entity_count"] > 0 for item in files
        ),
        "paper_space_native_entity_count": sum(
            item["paper_space_native_entity_count"] for item in files
        ),
        "viewport_layout_file_count": sum(
            item["paper_space_viewport_count"] > 0 for item in files
        ),
        "paper_space_viewport_count": sum(
            item["paper_space_viewport_count"] for item in files
        ),
        "xref_file_count": sum(item["xref_count"] > 0 for item in files),
        "xref_count": sum(item["xref_count"] for item in files),
        "missing_xref_count": sum(len(item["missing_xrefs"]) for item in files),
        "proxy_file_count": sum(item["proxy_entity_count"] > 0 for item in files),
        "proxy_entity_count": sum(item["proxy_entity_count"] for item in files),
        "virtual_expansion_failure_file_count": sum(
            bool(item["virtual_expansion_failures"]) for item in files
        ),
        "virtual_expansion_failure_count": sum(
            len(item["virtual_expansion_failures"]) for item in files
        ),
        "semantic_unsupported_entity_count": sum(semantic.values()),
        "semantic_unsupported_entity_counts": dict(sorted(semantic.items())),
        "shadow_unsupported_entity_count": sum(shadow.values()),
        "shadow_unsupported_entity_counts": dict(sorted(shadow.items())),
        "error_code_counts": dict(sorted(errors.items())),
        "warning_code_counts": dict(sorted(warnings.items())),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(row["status"] for row in rows)
    split_counts = Counter(str(row.get("split") or "UNSPECIFIED") for row in rows)
    valid_rows = [row for row in rows if row["status"] == "VALID"]
    if not rows:
        status = "INVALID"
    elif status_counts["INVALID"]:
        status = "INVALID"
    elif status_counts["MISSING"]:
        status = "MISSING"
    else:
        status = "VALID"

    observed = _aggregate_valid_rows(valid_rows)
    all_valid = bool(rows) and len(valid_rows) == len(rows)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": status,
        "project_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "valid_project_count": len(valid_rows),
        "missing_project_count": status_counts["MISSING"],
        "invalid_project_count": status_counts["INVALID"],
        "all_projects_valid": all_valid,
        "held_out_project_count": sum(bool(row["is_held_out"]) for row in rows),
        "held_out_valid_project_count": sum(
            bool(row["is_held_out"]) and row["status"] == "VALID" for row in rows
        ),
        "held_out_usage": "reporting_only",
        "observed_metrics": observed,
        "complete_corpus_metrics": observed if all_valid else None,
        "errors": ["NO_PROJECTS"] if not rows else [],
    }


def _aggregate_valid_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        result = _null_metrics()
        result["project_count"] = 0
        return result

    result: dict[str, Any] = {"project_count": len(rows)}
    for key in _ROW_METRIC_FIELDS:
        if key in _MAPPING_METRIC_FIELDS:
            counts: Counter[str] = Counter()
            for row in rows:
                counts.update(row[key])
            result[key] = dict(sorted(counts.items()))
        else:
            result[key] = sum(row[key] for row in rows)
    return result


def _null_metrics() -> dict[str, Any]:
    return {key: None for key in _ROW_METRIC_FIELDS}


def _project_status(artifact_status: Mapping[str, str]) -> str:
    statuses = set(artifact_status.values())
    if "invalid" in statuses:
        return "INVALID"
    if "missing" in statuses:
        return "MISSING"
    return "VALID" if statuses == {"valid"} else "INVALID"


def _require_schema(
    payload: Mapping[str, Any], expected: str, errors: list[str]
) -> None:
    if payload.get("schema_version") != expected:
        errors.append(f"schema_version must be {expected!r}")


def _require_nonempty_string(
    payload: Mapping[str, Any], key: str, errors: list[str]
) -> None:
    if not isinstance(payload.get(key), str) or not str(payload[key]).strip():
        errors.append(f"{key} must be a non-empty string")


def _require_nonnegative_int(
    payload: Mapping[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> int | None:
    value = payload.get(key)
    label = f"{prefix}.{key}" if prefix else key
    if type(value) is not int or value < 0:
        errors.append(f"{label} must be a non-negative integer")
        return None
    return value


def _require_count_mapping(
    payload: Mapping[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = payload.get(key)
    label = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    for item_key, count in value.items():
        if not isinstance(item_key, str) or not item_key:
            errors.append(f"{label} keys must be non-empty strings")
            return
        if type(count) is not int or count < 0:
            errors.append(f"{label}.{item_key} must be a non-negative integer")
            return


def _validate_diagnostics(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        if not isinstance(item.get("code"), str) or not item["code"].strip():
            errors.append(f"{label}[{index}].code must be a non-empty string")


def _validate_declared_mapping_total(
    payload: Mapping[str, Any],
    count_key: str,
    mapping_key: str,
    prefix: str,
    errors: list[str],
) -> None:
    count = payload.get(count_key)
    counts = payload.get(mapping_key)
    if type(count) is int and isinstance(counts, dict):
        if all(type(value) is int for value in counts.values()) and count != sum(
            counts.values()
        ):
            errors.append(
                f"{prefix}.{count_key} does not match {prefix}.{mapping_key}"
            )


def _is_held_out_split(value: str | None) -> bool:
    normalized = "".join(character for character in str(value or "").casefold() if character.isalnum())
    return normalized.startswith("heldout")


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    all_columns = {key for row in rows for key in row}
    fieldnames = [column for column in _PREFERRED_COLUMNS if column in all_columns]
    fieldnames.extend(sorted(all_columns - set(fieldnames)))
    if not fieldnames:
        fieldnames = list(_PREFERRED_COLUMNS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        serializable = sorted(value) if isinstance(value, set) else value
        return json.dumps(
            serializable,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return value


__all__ = [
    "SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "evaluate_corpus_census",
    "write_corpus_census_artifacts",
]
