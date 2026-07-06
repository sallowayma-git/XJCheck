from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.report.artifacts import load_report_frames


def evaluate_acceptance_project(
    project_dir: Path,
    spec_path: Path,
) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))
    issues_payload = json.loads((project_dir / "audit" / "issues.json").read_text(encoding="utf-8"))
    frames = load_report_frames(project_dir)
    pages = frames.get("pages", pd.DataFrame())
    pairs = frames.get("pairs", pd.DataFrame())

    golden_pairs = spec.get("golden_pairs", [])
    expected_skip_pages = spec.get("expected_skip_pages", [])
    expected_conflicts = spec.get("expected_conflicts", [])
    expected_missing_issues = spec.get("expected_missing_issues", [])
    expected_review_pairs = spec.get("expected_review_pairs", [])
    pair_recall_threshold = float(spec.get("pair_recall_threshold", 0.9))
    pair_scope = spec.get("pair_scope") or {}
    scoped_pairs = _scoped_pairs(pairs, pair_scope)

    matched_golden_pairs = _matched_golden_pairs(scoped_pairs, golden_pairs)
    extracted_complete_pairs = _extracted_complete_pairs(scoped_pairs)
    golden_pair_keys = {_pair_spec_key(item) for item in golden_pairs}
    matched_pair_keys = {_pair_spec_key(item) for item in matched_golden_pairs}
    pair_precision = _safe_ratio(len(matched_golden_pairs), len(extracted_complete_pairs))
    pair_recall = _safe_ratio(len(matched_golden_pairs), len(golden_pairs))

    matched_skip_pages = _matched_skip_pages(findings_payload.get("page_findings", []), expected_skip_pages)
    matched_conflicts = _matched_conflict_issues(issues_payload, expected_conflicts)
    matched_missing_issues = _matched_missing_issues(issues_payload, expected_missing_issues)
    matched_review_pairs = _matched_review_pairs(scoped_pairs, expected_review_pairs)
    issue_field_coverage = _issue_field_coverage(issues_payload)

    evaluation = {
        "spec_name": spec.get("name", spec_path.stem),
        "project_dir": str(project_dir.resolve()),
        "spec_path": str(spec_path.resolve()),
        "pair_scope": pair_scope,
        "pair_metrics": {
            "expected_pair_count": len(golden_pairs),
            "extracted_complete_pair_count": len(extracted_complete_pairs),
            "matched_pair_count": len(matched_golden_pairs),
            "precision": pair_precision,
            "recall": pair_recall,
            "threshold": pair_recall_threshold,
            "matched_pairs": matched_golden_pairs,
            "missing_pairs": [item for item in golden_pairs if _pair_spec_key(item) not in matched_pair_keys],
            "unexpected_pairs": [
                item
                for item in extracted_complete_pairs
                if _pair_spec_key(item) not in golden_pair_keys
            ],
        },
        "skip_page_metrics": {
            "expected_count": len(expected_skip_pages),
            "matched_count": len(matched_skip_pages),
            "recall": _safe_ratio(len(matched_skip_pages), len(expected_skip_pages)),
            "matched_pages": matched_skip_pages,
        },
        "conflict_issue_metrics": {
            "expected_count": len(expected_conflicts),
            "matched_count": len(matched_conflicts),
            "recall": _safe_ratio(len(matched_conflicts), len(expected_conflicts)),
            "matched_items": matched_conflicts,
        },
        "missing_issue_metrics": {
            "expected_count": len(expected_missing_issues),
            "matched_count": len(matched_missing_issues),
            "recall": _safe_ratio(len(matched_missing_issues), len(expected_missing_issues)),
            "matched_items": matched_missing_issues,
        },
        "review_pair_metrics": {
            "expected_count": len(expected_review_pairs),
            "matched_count": len(matched_review_pairs),
            "recall": _safe_ratio(len(matched_review_pairs), len(expected_review_pairs)),
            "matched_items": matched_review_pairs,
        },
        "issue_field_coverage": issue_field_coverage,
    }
    evaluation["acceptance_passed"] = _acceptance_passed(evaluation)
    return evaluation


def write_acceptance_report(
    project_dir: Path,
    spec_path: Path,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluation = evaluate_acceptance_project(project_dir, spec_path)
    (output_dir / "acceptance_report.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "acceptance_report.md").write_text(
        _format_acceptance_markdown(evaluation),
        encoding="utf-8",
    )
    return output_dir


def evaluate_acceptance_suite(
    suite_path: Path,
    project_aliases: dict[str, Path],
) -> dict[str, Any]:
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    evaluations: list[dict[str, Any]] = []
    missing_project_alias_cases: list[dict[str, Any]] = []
    for case in suite.get("cases", []):
        case_id = str(case.get("case_id") or "")
        project_alias = str(case.get("project_alias") or "")
        required = bool(case.get("required", True))
        spec_path = _resolve_suite_spec_path(suite_path, case.get("spec"))
        project_dir = project_aliases.get(project_alias)
        if project_dir is None:
            missing_project_alias_cases.append(
                {
                    "case_id": case_id,
                    "project_alias": project_alias,
                    "required": required,
                    "spec_path": str(spec_path.resolve()),
                }
            )
            evaluations.append(
                {
                    "case_id": case_id,
                    "project_alias": project_alias,
                    "required": required,
                    "project_dir": None,
                    "spec_path": str(spec_path.resolve()),
                    "acceptance_passed": False,
                    "status": "missing_project_alias",
                    "status_reason": f"No project directory was provided for alias `{project_alias}`.",
                }
            )
            continue
        evaluation = evaluate_acceptance_project(project_dir, spec_path)
        evaluations.append(
            {
                "case_id": case_id,
                "project_alias": project_alias,
                "required": required,
                "project_dir": str(project_dir.resolve()),
                "spec_path": str(spec_path.resolve()),
                "acceptance_passed": bool(evaluation.get("acceptance_passed")),
                "status": "evaluated",
                "status_reason": "Acceptance case evaluated successfully.",
                "evaluation": evaluation,
            }
        )
    required_cases = [item for item in evaluations if bool(item.get("required", True))]
    required_passed_cases = [item for item in required_cases if bool(item.get("acceptance_passed"))]
    return {
        "suite_name": suite.get("name", suite_path.stem),
        "suite_path": str(suite_path.resolve()),
        "case_count": len(evaluations),
        "required_case_count": len(required_cases),
        "passed_case_count": sum(1 for item in evaluations if bool(item.get("acceptance_passed"))),
        "required_passed_case_count": len(required_passed_cases),
        "missing_project_alias_cases": missing_project_alias_cases,
        "cases": evaluations,
        "acceptance_passed": (
            len(required_cases) > 0 and len(required_cases) == len(required_passed_cases)
        ),
    }


def write_acceptance_suite_report(
    suite_path: Path,
    project_aliases: dict[str, Path],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    suite_result = evaluate_acceptance_suite(suite_path, project_aliases)
    (output_dir / "acceptance_suite_report.json").write_text(
        json.dumps(suite_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "acceptance_suite_report.md").write_text(
        _format_acceptance_suite_markdown(suite_result),
        encoding="utf-8",
    )
    return output_dir


def _matched_golden_pairs(pairs: pd.DataFrame, golden_pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    extracted = {
        (
            _pair_filename(row),
            str(row.get("left_value") or ""),
            str(row.get("right_value") or ""),
        )
        for row in _rows(pairs)
        if row.get("status") != "discard" and _present(row.get("left_value")) and _present(row.get("right_value"))
    }
    matched: list[dict[str, Any]] = []
    for item in golden_pairs:
        key = (
            str(item.get("filename") or ""),
            str(item.get("left_value") or ""),
            str(item.get("right_value") or ""),
        )
        if key in extracted:
            matched.append(item)
    return matched


def _extracted_complete_pairs(pairs: pd.DataFrame) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in _rows(pairs):
        if row.get("status") == "discard":
            continue
        if not _present(row.get("left_value")) or not _present(row.get("right_value")):
            continue
        key = (
            _pair_filename(row),
            str(row.get("left_value") or ""),
            str(row.get("right_value") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "filename": key[0],
                "left_value": key[1],
                "right_value": key[2],
                "status": str(row.get("status") or ""),
                "pair_key": str(row.get("pair_key") or ""),
            }
        )
    return results


def _matched_skip_pages(page_findings: list[dict[str, Any]], expected_skip_pages: list[str]) -> list[str]:
    actual = {
        str(item.get("filename") or "")
        for item in page_findings
        if item.get("audit_disposition") == "skip_stable" and item.get("route_target") == "SkipExtractor"
    }
    return [filename for filename in expected_skip_pages if filename in actual]


def _matched_conflict_issues(
    issues_payload: list[dict[str, Any]],
    expected_conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for item in expected_conflicts:
        expected_left = str(item.get("left_value") or "")
        expected_rights = {str(value) for value in item.get("right_values", [])}
        for issue in issues_payload:
            if issue.get("rule_id") != "R-CROSS-PAGE-CONFLICT":
                continue
            if str(issue.get("left_value") or "") != expected_left:
                continue
            issue_values = {str(value) for value in issue.get("values", [])}
            if expected_rights.issubset(issue_values):
                matched.append(item)
                break
    return matched


def _matched_missing_issues(
    issues_payload: list[dict[str, Any]],
    expected_missing_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for item in expected_missing_issues:
        expected_filename = str(item.get("filename") or "")
        expected_pair_key = str(item.get("pair_key") or "")
        for issue in issues_payload:
            if issue.get("rule_id") != "R-PAIR-MISSING-SIDE":
                continue
            evidence = issue.get("evidence") or {}
            pair_evidence = evidence.get("pair_evidence") or {}
            if str(evidence.get("filename") or "") != expected_filename:
                continue
            if str(pair_evidence.get("pair_key") or "") == expected_pair_key:
                matched.append(item)
                break
    return matched


def _matched_review_pairs(pairs: pd.DataFrame, expected_review_pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    review_pairs = {
        (
            _pair_filename(row),
            str(row.get("left_value") or ""),
            str(row.get("right_value") or ""),
        )
        for row in _rows(pairs)
        if row.get("status") == "review" and _present(row.get("left_value")) and _present(row.get("right_value"))
    }
    matched: list[dict[str, Any]] = []
    for item in expected_review_pairs:
        key = (
            str(item.get("filename") or ""),
            str(item.get("left_value") or ""),
            str(item.get("right_value") or ""),
        )
        if key in review_pairs:
            matched.append(item)
    return matched


def _issue_field_coverage(issues_payload: list[dict[str, Any]]) -> dict[str, Any]:
    required = {
        "rule_id": True,
        "confidence": True,
        "sheet_id": True,
        "line_group_id_or_anchor": True,
        "left_or_right_value": True,
        "filename": True,
        "sheet_no": True,
        "evidence_refs": True,
    }
    for issue in issues_payload:
        evidence = issue.get("evidence") or {}
        pair_evidence = evidence.get("pair_evidence") or {}
        refs = issue.get("evidence_refs") or []
        if not issue.get("rule_id"):
            required["rule_id"] = False
        if issue.get("confidence") is None:
            required["confidence"] = False
        if not _present(issue.get("sheet_id")):
            required["sheet_id"] = False
        if not any(
            [
                _present(issue.get("line_group_id")),
                _present(pair_evidence.get("pair_key")),
                _present(evidence.get("shared_text_id")),
                _present(evidence.get("table_mapping")),
                bool(evidence.get("line_start")) and bool(evidence.get("line_end")),
            ]
        ):
            required["line_group_id_or_anchor"] = False
        if not any([_present(issue.get("left_value")), _present(issue.get("right_value")), bool(issue.get("values"))]):
            required["left_or_right_value"] = False
        if not _present(evidence.get("filename")):
            required["filename"] = False
        if not _present(evidence.get("sheet_no")):
            required["sheet_no"] = False
        if not refs:
            required["evidence_refs"] = False
    return {
        "required_fields_present": required,
        "all_required_fields_present": all(required.values()),
    }


def _acceptance_passed(evaluation: dict[str, Any]) -> bool:
    pair_metrics = evaluation.get("pair_metrics", {})
    pair_required = int(pair_metrics.get("expected_pair_count") or 0) > 0
    pair_passed = True
    if pair_required:
        pair_passed = (
            pair_metrics.get("precision") is not None
            and pair_metrics.get("recall") is not None
            and float(pair_metrics.get("recall") or 0.0) >= float(pair_metrics.get("threshold") or 0.0)
        )
    return all(
        [
            pair_passed,
            _optional_recall_check(evaluation.get("skip_page_metrics", {})),
            _optional_recall_check(evaluation.get("conflict_issue_metrics", {})),
            _optional_recall_check(evaluation.get("missing_issue_metrics", {})),
            _optional_recall_check(evaluation.get("review_pair_metrics", {})),
            bool(evaluation.get("issue_field_coverage", {}).get("all_required_fields_present")),
        ]
    )


def _format_acceptance_markdown(evaluation: dict[str, Any]) -> str:
    pair_metrics = evaluation.get("pair_metrics", {})
    skip_metrics = evaluation.get("skip_page_metrics", {})
    conflict_metrics = evaluation.get("conflict_issue_metrics", {})
    missing_metrics = evaluation.get("missing_issue_metrics", {})
    review_metrics = evaluation.get("review_pair_metrics", {})
    field_coverage = evaluation.get("issue_field_coverage", {})
    pair_scope = evaluation.get("pair_scope") or {}
    lines = [
        "# Acceptance Report",
        "",
        f"- Spec: `{evaluation.get('spec_name')}`",
        f"- Project: `{evaluation.get('project_dir')}`",
        f"- Passed: `{evaluation.get('acceptance_passed')}`",
    ]
    if pair_scope:
        lines.append(f"- Pair scope: `{json.dumps(pair_scope, ensure_ascii=False, sort_keys=True)}`")
    lines.extend(
        [
            "",
            "## Pair Metrics",
            "",
            f"- Expected complete pairs: `{pair_metrics.get('expected_pair_count', 0)}`",
            f"- Extracted complete pairs: `{pair_metrics.get('extracted_complete_pair_count', 0)}`",
            f"- Matched complete pairs: `{pair_metrics.get('matched_pair_count', 0)}`",
            f"- Precision: `{pair_metrics.get('precision')}`",
            f"- Recall: `{pair_metrics.get('recall')}`",
            f"- Recall threshold: `{pair_metrics.get('threshold')}`",
            "",
            "## Acceptance Checks",
            "",
            f"- Skip pages recall: `{skip_metrics.get('matched_count', 0)}` / `{skip_metrics.get('expected_count', 0)}`",
            f"- Conflict issue recall: `{conflict_metrics.get('matched_count', 0)}` / `{conflict_metrics.get('expected_count', 0)}`",
            f"- Missing issue recall: `{missing_metrics.get('matched_count', 0)}` / `{missing_metrics.get('expected_count', 0)}`",
            f"- Review pair recall: `{review_metrics.get('matched_count', 0)}` / `{review_metrics.get('expected_count', 0)}`",
            f"- Issue evidence fields complete: `{field_coverage.get('all_required_fields_present')}`",
            "",
            "## Field Coverage",
            "",
            f"- Required fields: `{json.dumps(field_coverage.get('required_fields_present', {}), ensure_ascii=False, sort_keys=True)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_acceptance_suite_markdown(suite_result: dict[str, Any]) -> str:
    lines = [
        "# Acceptance Suite Report",
        "",
        f"- Suite: `{suite_result.get('suite_name')}`",
        f"- Passed: `{suite_result.get('acceptance_passed')}`",
        f"- Required passed: `{suite_result.get('required_passed_case_count', 0)}` / `{suite_result.get('required_case_count', 0)}`",
        f"- Total passed: `{suite_result.get('passed_case_count', 0)}` / `{suite_result.get('case_count', 0)}`",
        "",
        "## Cases",
        "",
    ]
    for item in suite_result.get("cases", []):
        lines.append(
            f"- `{item.get('case_id')}` "
            f"(alias={item.get('project_alias')}, required={item.get('required')}, status={item.get('status')}, passed={item.get('acceptance_passed')})"
        )
        evaluation = item.get("evaluation") or {}
        if evaluation:
            pair_metrics = evaluation.get("pair_metrics", {})
            lines.append(
                f"  pair_precision={pair_metrics.get('precision')}, pair_recall={pair_metrics.get('recall')}, "
                f"expected_pairs={pair_metrics.get('expected_pair_count')}, matched_pairs={pair_metrics.get('matched_pair_count')}"
            )
        else:
            lines.append(f"  reason={item.get('status_reason')}")
    return "\n".join(lines) + "\n"


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _present(value: object) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except TypeError:
        pass
    return str(value) != ""


def _pair_filename(row: dict[str, Any]) -> str:
    evidence = row.get("evidence") or {}
    if _present(row.get("filename")):
        return str(row.get("filename"))
    if _present(evidence.get("filename")):
        return str(evidence.get("filename"))
    return ""


def _pair_spec_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("filename") or ""),
        str(item.get("left_value") or ""),
        str(item.get("right_value") or ""),
    )


def _optional_recall_check(metrics: dict[str, Any]) -> bool:
    if int(metrics.get("expected_count") or 0) <= 0:
        return True
    return float(metrics.get("recall") or 0.0) >= 1.0


def _resolve_suite_spec_path(suite_path: Path, raw_value: object) -> Path:
    candidate = Path(str(raw_value or "")).expanduser()
    if not candidate.is_absolute():
        candidate = (suite_path.parent / candidate).resolve()
    return candidate


def _scoped_pairs(pairs: pd.DataFrame, pair_scope: dict[str, Any]) -> pd.DataFrame:
    if pairs is None or pairs.empty or not pair_scope:
        return pairs
    filenames = {str(value) for value in pair_scope.get("included_filenames", []) if _present(value)}
    sheet_ids = {str(value) for value in pair_scope.get("included_sheet_ids", []) if _present(value)}
    pair_kinds = {str(value) for value in pair_scope.get("pair_kinds", []) if _present(value)}
    pair_keys = {str(value) for value in pair_scope.get("included_pair_keys", []) if _present(value)}
    pair_refs = _pair_ref_scope(pair_scope.get("included_pair_refs", []))
    statuses = {str(value) for value in pair_scope.get("statuses", []) if _present(value)}
    filtered: list[dict[str, Any]] = []
    for row in _rows(pairs):
        filename = _pair_filename(row)
        pair_key = str(row.get("pair_key") or "")
        if filenames and _pair_filename(row) not in filenames:
            continue
        if sheet_ids and str(row.get("sheet_id") or "") not in sheet_ids:
            continue
        if pair_kinds and str(row.get("pair_kind") or "") not in pair_kinds:
            continue
        if pair_keys and pair_key not in pair_keys:
            continue
        if pair_refs and (filename, pair_key) not in pair_refs:
            continue
        if statuses and str(row.get("status") or "") not in statuses:
            continue
        filtered.append(row)
    return pd.DataFrame(filtered)


def _pair_ref_scope(values: list[dict[str, Any]]) -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or "")
        pair_key = str(item.get("pair_key") or "")
        if filename and pair_key:
            refs.add((filename, pair_key))
    return refs


def _rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    rows = frame.to_dict(orient="records")
    decoded: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key in ("evidence", "alternative_pair_candidate_ids", "related_pair_ids", "sheet_ids", "values", "evidence_refs"):
            value = item.get(key)
            if isinstance(value, str):
                try:
                    item[key] = json.loads(value)
                except json.JSONDecodeError:
                    item[key] = value
        decoded.append(item)
    return decoded
