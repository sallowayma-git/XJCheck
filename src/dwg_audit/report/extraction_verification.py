"""Offline extraction health scorecard over persisted project bundles.

Answers a different question than issue counts: whether analyze-project artifacts
show complete conversion/primitives, healthy page routing, and residual gaps in
recognition coverage (wires/blocks/symbols/tables/scale). Never re-opens CAD.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dwg_audit.report.project_bundle import resolve_project_bundle_dir


SCHEMA_VERSION = "extraction-verification-v1"
SUMMARY_SCHEMA_VERSION = "extraction-verification-summary-v1"

_COMPLETE = frozenset({"COMPLETE", "COMPLETE_EXTRACTION", "PASS", "PASSED"})
_LOW_PAGE_CONFIDENCE = 0.6
_REVIEW_UNASSIGNED_WIRE_RATIO = 0.45
_REVIEW_UNCLASSIFIED_BLOCK_RATIO = 0.55
# Table/terminal/backplate pages leave most geometry outside pair member ids;
# score unassigned-wire health only on extractors that own conductive wires.
_WIRE_ROUTE_TARGETS = frozenset(
    {
        "WireDiagramExtractor",
        "ComponentDiagramExtractor",
    }
)

_PROJECT_CSV_COLUMNS = (
    "project_alias",
    "project_id",
    "health_status",
    "fail_reasons",
    "review_reasons",
    "gate_status",
    "incomplete_page_count",
    "sheet_count",
    "included_audit_pages",
    "file_count",
    "census_file_count",
    "census_complete_files",
    "semantic_unsupported_total",
    "texts",
    "lines",
    "blocks",
    "polylines",
    "pairs",
    "issues",
    "table_mapping_pairs",
    "component_mapping_pairs",
    "coverage_ratio",
    "unexplained_texts",
    "unassigned_wire_segments",
    "wire_scope_line_segments",
    "wire_scope_unassigned_segments",
    "unassigned_wire_ratio",
    "unclassified_blocks",
    "unknown_symbol_definitions",
    "unknown_symbol_instances",
    "page_type_counts",
    "route_target_counts",
    "low_confidence_page_count",
    "layout_only_audit_pages",
    "table_like_non_routed",
    "scale_unresolved_files",
    "scene_incomplete_count",
    "failure_queue_items",
    "failure_queue_critical",
    "project_dir",
)

_PAGE_CSV_COLUMNS = (
    "project_alias",
    "sheet_id",
    "filename",
    "sheet_no",
    "page_type",
    "page_type_confidence",
    "route_target",
    "audit_disposition",
    "audit_role",
    "table_like",
    "grid_heavy",
    "gate_status",
    "primitive_total",
    "text_count",
    "line_count",
    "block_count",
    "polyline_count",
    "pair_count",
    "table_mapping_count",
    "unassigned_wire_segments",
    "unclassified_blocks",
    "unexplained_texts",
    "coverage_ratio",
)


def collect_project_extraction_verification(
    project_alias: str,
    project_dir: Path,
) -> dict[str, Any]:
    """Collect a single-project extraction health scorecard from disk artifacts."""

    bundle = resolve_project_bundle_dir(Path(project_dir))
    findings_dir = bundle / "findings"
    audit_dir = bundle / "audit"

    missing: list[str] = []
    invalid: list[str] = []

    gate, gate_status = _load_json_artifact(
        bundle / "extraction_completeness.json",
        required_keys=("analysis_status",),
    )
    if gate_status != "valid":
        (missing if gate_status == "missing" else invalid).append("extraction_completeness.json")

    findings, findings_status = _load_json_artifact(
        findings_dir / "findings.json",
        required_keys=("project_id", "sheet_count"),
    )
    if findings_status != "valid":
        (missing if findings_status == "missing" else invalid).append("findings/findings.json")

    census_summary, census_status = _load_json_artifact(
        findings_dir / "extraction_census_summary.json",
        required_keys=("schema_version", "file_count"),
    )
    if census_status != "valid":
        (missing if census_status == "missing" else invalid).append(
            "findings/extraction_census_summary.json"
        )

    scale_summary = _load_json(findings_dir / "scale_evidence_summary.json") or {}
    scene_summary = _load_json(findings_dir / "canonical_scene_summary.json") or {}
    symbol_summary = _load_json(findings_dir / "symbol_inventory_summary.json") or {}
    failure_summary = _load_json(audit_dir / "failure_queue_summary.json") or {}

    pages_frame = _read_parquet(findings_dir / "pages.parquet")
    pairs_frame = _read_parquet(findings_dir / "pairs.parquet")
    coverage_rows = _read_parquet(findings_dir / "entity_coverage_summary.parquet")

    stats = findings.get("stats") if isinstance(findings.get("stats"), dict) else {}
    if isinstance(findings.get("entity_coverage_summary"), dict) and (
        "coverage_ratio" in findings["entity_coverage_summary"]
        or "unassigned_wire_segments" in findings["entity_coverage_summary"]
    ):
        coverage = findings["entity_coverage_summary"]
    else:
        coverage = _coverage_from_rows(coverage_rows)
    table_summary = (
        findings.get("table_extraction_summary")
        if isinstance(findings.get("table_extraction_summary"), dict)
        else {}
    )
    pair_kind_counts = _pair_kind_counts(pairs_frame, findings)

    page_rows = _build_page_rows(
        project_alias=project_alias,
        findings=findings,
        gate=gate,
        pages_frame=pages_frame,
        coverage_rows=coverage_rows,
    )
    page_type_counts = dict(Counter(str(row.get("page_type") or "") for row in page_rows))
    route_counts = dict(Counter(str(row.get("route_target") or "") for row in page_rows))
    low_conf_pages = sum(
        1
        for row in page_rows
        if _finite(row.get("page_type_confidence")) is not None
        and float(row["page_type_confidence"]) < _LOW_PAGE_CONFIDENCE
        and str(row.get("audit_disposition") or "") == "audit_required"
    )
    layout_only_audit = sum(
        1
        for row in page_rows
        if str(row.get("route_target") or "") == "LayoutOnlyExtractor"
        and str(row.get("audit_disposition") or "") in {"audit_required", "classify_only"}
        and str(row.get("page_type") or "") not in {"封面/目录", "屏面布置图"}
    )
    table_like_non_routed = int(table_summary.get("table_like_non_routed") or 0)
    if table_like_non_routed == 0:
        table_like_non_routed = sum(
            1
            for row in page_rows
            if bool(row.get("table_like"))
            and str(row.get("route_target") or "") != "TableExtractor"
            and str(row.get("page_type") or "") != "元件接线图"
        )

    census_status_counts = (
        census_summary.get("status_counts")
        if isinstance(census_summary.get("status_counts"), dict)
        else {}
    )
    semantic_unsupported = _sum_mapping(
        census_summary.get("semantic_unsupported_entity_counts")
        if isinstance(census_summary.get("semantic_unsupported_entity_counts"), dict)
        else {}
    )
    scale_status_counts = (
        scale_summary.get("scale_status_counts")
        if isinstance(scale_summary.get("scale_status_counts"), dict)
        else census_summary.get("scale_status_counts")
        if isinstance(census_summary.get("scale_status_counts"), dict)
        else {}
    )
    scale_unresolved = int(scale_status_counts.get("UNRESOLVED") or 0)
    scene_status_counts = (
        scene_summary.get("status_counts")
        if isinstance(scene_summary.get("status_counts"), dict)
        else {}
    )
    scene_incomplete = int(scene_status_counts.get("INCOMPLETE") or 0)

    gate_analysis = str(gate.get("analysis_status") or "").upper()
    incomplete_pages = int(gate.get("incomplete_page_count") or 0)
    unknown_defs = int(
        symbol_summary.get("unknown_definition_count")
        or symbol_summary.get("definition_count")
        or 0
    )
    unknown_instances = int(symbol_summary.get("instance_count") or 0)
    if symbol_summary.get("registered_definition_count") is not None:
        unknown_defs = int(symbol_summary.get("unknown_definition_count") or 0)

    coverage_ratio = _finite(coverage.get("coverage_ratio"))
    unassigned_wires = int(coverage.get("unassigned_wire_segments") or 0)
    unclassified_blocks = int(coverage.get("unclassified_blocks") or 0)
    lines = int(stats.get("lines") or 0)
    blocks = int(stats.get("blocks") or 0)
    wire_scope_lines, wire_scope_unassigned = _wire_scope_line_metrics(page_rows, coverage_rows)
    wire_ratio = (
        (wire_scope_unassigned / wire_scope_lines)
        if wire_scope_lines > 0
        else ((unassigned_wires / lines) if lines > 0 else 0.0)
    )
    block_ratio = (unclassified_blocks / blocks) if blocks > 0 else 0.0

    fail_reasons: list[str] = []
    review_reasons: list[str] = []
    if missing:
        fail_reasons.append(f"missing_artifacts:{','.join(missing)}")
    if invalid:
        fail_reasons.append(f"invalid_artifacts:{','.join(invalid)}")
    if gate and gate_analysis and gate_analysis not in _COMPLETE:
        fail_reasons.append(f"gate_status:{gate_analysis or 'UNKNOWN'}")
    if incomplete_pages > 0:
        fail_reasons.append(f"incomplete_pages:{incomplete_pages}")
    if census_summary and int(census_status_counts.get("FAILED") or 0) > 0:
        fail_reasons.append("census_failed_files")
    if int(failure_summary.get("critical_count") or 0) > 0:
        fail_reasons.append("failure_queue_critical")

    if semantic_unsupported > 0:
        review_reasons.append(f"semantic_unsupported_entities:{semantic_unsupported}")
    if coverage_ratio is not None and coverage_ratio < 1.0:
        review_reasons.append(f"text_coverage_ratio:{coverage_ratio:.3f}")
    if int(coverage.get("unexplained_texts") or 0) > 0:
        review_reasons.append(f"unexplained_texts:{coverage.get('unexplained_texts')}")
    if wire_ratio >= _REVIEW_UNASSIGNED_WIRE_RATIO:
        review_reasons.append(f"high_unassigned_wire_ratio:{wire_ratio:.2f}")
    if block_ratio >= _REVIEW_UNCLASSIFIED_BLOCK_RATIO:
        review_reasons.append(f"high_unclassified_block_ratio:{block_ratio:.2f}")
    if unknown_defs > 0:
        review_reasons.append(f"unknown_symbol_definitions:{unknown_defs}")
    if low_conf_pages > 0:
        review_reasons.append(f"low_page_type_confidence:{low_conf_pages}")
    if layout_only_audit > 0:
        review_reasons.append(f"layout_only_content_pages:{layout_only_audit}")
    if table_like_non_routed > 0:
        review_reasons.append(f"table_like_non_routed:{table_like_non_routed}")
    if scale_unresolved > 0:
        review_reasons.append(f"scale_unresolved_files:{scale_unresolved}")
    if scene_incomplete > 0:
        review_reasons.append(f"scene_incomplete:{scene_incomplete}")
    if int(failure_summary.get("item_count") or failure_summary.get("failure_count") or 0) > 0:
        review_reasons.append(
            f"failure_queue_items:{failure_summary.get('item_count') or failure_summary.get('failure_count')}"
        )

    if fail_reasons:
        health = "FAIL"
    elif review_reasons:
        health = "REVIEW"
    else:
        health = "PASS"

    project_id = str(findings.get("project_id") or gate.get("project_id") or bundle.name)
    row = {
        "project_alias": project_alias,
        "project_id": project_id,
        "health_status": health,
        "fail_reasons": ";".join(fail_reasons),
        "review_reasons": ";".join(review_reasons),
        "gate_status": gate_analysis or ("MISSING" if "extraction_completeness.json" in missing else "UNKNOWN"),
        "incomplete_page_count": incomplete_pages,
        "sheet_count": int(findings.get("sheet_count") or len(page_rows) or 0),
        "included_audit_pages": int(findings.get("included_audit_pages") or 0),
        "file_count": int(findings.get("file_count") or 0),
        "census_file_count": int(census_summary.get("file_count") or 0),
        "census_complete_files": int(census_status_counts.get("COMPLETE") or 0),
        "semantic_unsupported_total": semantic_unsupported,
        "texts": int(stats.get("texts") or 0),
        "lines": lines,
        "blocks": blocks,
        "polylines": int(stats.get("polylines") or 0),
        "pairs": int(stats.get("pairs") or 0),
        "issues": int(stats.get("issues") or 0),
        "table_mapping_pairs": int(pair_kind_counts.get("table_mapping") or 0),
        "component_mapping_pairs": int(pair_kind_counts.get("component_mapping") or 0),
        "coverage_ratio": coverage_ratio if coverage_ratio is not None else "",
        "unexplained_texts": int(coverage.get("unexplained_texts") or 0),
        "unassigned_wire_segments": unassigned_wires,
        "wire_scope_line_segments": wire_scope_lines,
        "wire_scope_unassigned_segments": wire_scope_unassigned,
        "unassigned_wire_ratio": round(wire_ratio, 4),
        "unclassified_blocks": unclassified_blocks,
        "unknown_symbol_definitions": unknown_defs,
        "unknown_symbol_instances": unknown_instances,
        "page_type_counts": _compact_counts(page_type_counts),
        "route_target_counts": _compact_counts(route_counts),
        "low_confidence_page_count": low_conf_pages,
        "layout_only_audit_pages": layout_only_audit,
        "table_like_non_routed": table_like_non_routed,
        "scale_unresolved_files": scale_unresolved,
        "scene_incomplete_count": scene_incomplete,
        "failure_queue_items": int(
            failure_summary.get("item_count") or failure_summary.get("failure_count") or 0
        ),
        "failure_queue_critical": int(failure_summary.get("critical_count") or 0),
        "project_dir": str(bundle),
    }
    detail = {
        "schema_version": SCHEMA_VERSION,
        "project_alias": project_alias,
        "project_id": project_id,
        "project_dir": str(bundle),
        "health_status": health,
        "fail_reasons": fail_reasons,
        "review_reasons": review_reasons,
        "artifact_status": {
            "gate": gate_status,
            "findings": findings_status,
            "census_summary": census_status,
        },
        "gate": {
            "analysis_status": gate_analysis,
            "incomplete_page_count": incomplete_pages,
            "failure_code_counts": gate.get("failure_code_counts") or {},
            "clean_conclusion_allowed": gate.get("clean_conclusion_allowed"),
        },
        "census": {
            "file_count": census_summary.get("file_count"),
            "status_counts": census_status_counts,
            "semantic_unsupported_entity_counts": census_summary.get(
                "semantic_unsupported_entity_counts"
            )
            or {},
            "warning_code_counts": census_summary.get("warning_code_counts") or {},
        },
        "stats": stats,
        "coverage": coverage,
        "pair_kind_counts": pair_kind_counts,
        "page_type_counts": page_type_counts,
        "route_target_counts": route_counts,
        "table_extraction_summary": table_summary,
        "symbol_inventory_summary": symbol_summary,
        "scale_status_counts": scale_status_counts,
        "scene_status_counts": scene_status_counts,
        "failure_queue_summary": failure_summary,
        "pages": page_rows,
        "row": row,
    }
    return detail


def evaluate_extraction_verification(
    project_dirs: Mapping[str, Path],
) -> dict[str, Any]:
    """Evaluate extraction health for one or more persisted project bundles."""

    projects: list[dict[str, Any]] = []
    page_rows: list[dict[str, Any]] = []
    by_status: Counter[str] = Counter()
    for alias, path in sorted(project_dirs.items(), key=lambda item: item[0]):
        detail = collect_project_extraction_verification(alias, Path(path))
        projects.append(detail)
        page_rows.extend(detail.get("pages") or [])
        by_status[str(detail.get("health_status") or "UNKNOWN")] += 1

    if by_status.get("FAIL"):
        overall = "FAIL"
    elif by_status.get("REVIEW"):
        overall = "REVIEW"
    elif by_status.get("PASS"):
        overall = "PASS"
    else:
        overall = "FAIL"

    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "project_count": len(projects),
            "status": overall,
            "by_health_status": dict(by_status),
            "fail_count": int(by_status.get("FAIL") or 0),
            "review_count": int(by_status.get("REVIEW") or 0),
            "pass_count": int(by_status.get("PASS") or 0),
            "page_row_count": len(page_rows),
        },
        "projects": projects,
        "page_rows": page_rows,
        "project_rows": [item["row"] for item in projects],
    }


def write_extraction_verification_artifacts(
    evaluation: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write CSV/JSON/Markdown scorecards for an extraction verification run."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    by_project = output_dir / "extraction_verification_by_project.csv"
    by_page = output_dir / "extraction_verification_by_page.csv"
    summary_path = output_dir / "extraction_verification_summary.json"
    markdown_path = output_dir / "extraction_verification.md"

    _write_csv(by_project, _PROJECT_CSV_COLUMNS, evaluation.get("project_rows") or [])
    _write_csv(by_page, _PAGE_CSV_COLUMNS, evaluation.get("page_rows") or [])
    summary_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "summary": evaluation.get("summary"),
                "projects": [
                    {
                        "project_alias": item.get("project_alias"),
                        "project_id": item.get("project_id"),
                        "health_status": item.get("health_status"),
                        "fail_reasons": item.get("fail_reasons"),
                        "review_reasons": item.get("review_reasons"),
                        "row": item.get("row"),
                    }
                    for item in evaluation.get("projects") or []
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_render_markdown(evaluation), encoding="utf-8")
    return {
        "by_project": by_project,
        "by_page": by_page,
        "summary": summary_path,
        "markdown": markdown_path,
    }


def _build_page_rows(
    *,
    project_alias: str,
    findings: dict[str, Any],
    gate: dict[str, Any],
    pages_frame: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gate_by_sheet = {}
    for page in gate.get("pages") or []:
        if isinstance(page, dict) and page.get("sheet_id"):
            gate_by_sheet[str(page["sheet_id"])] = page

    coverage_by_sheet: dict[str, dict[str, Any]] = {}
    for row in coverage_rows:
        if str(row.get("summary_scope") or "") != "page":
            continue
        sheet_id = str(row.get("sheet_id") or "")
        if not sheet_id:
            continue
        coverage_by_sheet[sheet_id] = row

    page_findings = {
        str(item.get("sheet_id")): item
        for item in findings.get("page_findings") or []
        if isinstance(item, dict) and item.get("sheet_id")
    }

    source_pages = pages_frame or [
        {
            "sheet_id": item.get("sheet_id"),
            "filename": item.get("filename"),
            "sheet_no": item.get("sheet_no"),
            "page_type": item.get("page_type"),
            "page_type_confidence": item.get("page_type_confidence"),
            "route_target": item.get("route_target"),
            "audit_disposition": item.get("audit_disposition"),
            "audit_role": item.get("audit_role"),
            "table_like": item.get("table_like"),
            "grid_heavy": item.get("grid_heavy"),
        }
        for item in findings.get("page_findings") or []
        if isinstance(item, dict)
    ]

    rows: list[dict[str, Any]] = []
    for page in source_pages:
        sheet_id = str(page.get("sheet_id") or "")
        gate_page = gate_by_sheet.get(sheet_id) or {}
        primitives = (
            gate_page.get("primitive_counts")
            if isinstance(gate_page.get("primitive_counts"), dict)
            else {}
        )
        pf = page_findings.get(sheet_id) or {}
        structure = pf.get("structure_summary") if isinstance(pf.get("structure_summary"), dict) else {}
        cov = coverage_by_sheet.get(sheet_id) or {}
        rows.append(
            {
                "project_alias": project_alias,
                "sheet_id": sheet_id,
                "filename": page.get("filename") or pf.get("filename") or "",
                "sheet_no": page.get("sheet_no") or pf.get("sheet_no") or "",
                "page_type": page.get("page_type") or pf.get("page_type") or "",
                "page_type_confidence": page.get("page_type_confidence")
                if page.get("page_type_confidence") is not None
                else pf.get("page_type_confidence"),
                "route_target": page.get("route_target") or pf.get("route_target") or "",
                "audit_disposition": page.get("audit_disposition")
                or pf.get("audit_disposition")
                or "",
                "audit_role": page.get("audit_role") or pf.get("audit_role") or "",
                "table_like": bool(page.get("table_like") if page.get("table_like") is not None else pf.get("table_like")),
                "grid_heavy": bool(page.get("grid_heavy") if page.get("grid_heavy") is not None else pf.get("grid_heavy")),
                "gate_status": str(gate_page.get("status") or gate_page.get("extraction_status") or ""),
                "primitive_total": int(primitives.get("total") or 0),
                "text_count": int(primitives.get("text") or structure.get("text_count") or 0),
                "line_count": int(primitives.get("line") or structure.get("line_count") or 0),
                "block_count": int(primitives.get("block") or structure.get("block_count") or 0),
                "polyline_count": int(primitives.get("polyline") or structure.get("polyline_count") or 0),
                "pair_count": int(structure.get("pair_count") or 0),
                "table_mapping_count": int(structure.get("table_mapping_count") or 0),
                "unassigned_wire_segments": int(cov.get("unassigned_wire_segments") or 0),
                "unclassified_blocks": int(cov.get("unclassified_blocks") or 0),
                "unexplained_texts": int(cov.get("unexplained_texts") or 0),
                "coverage_ratio": cov.get("coverage_ratio")
                if cov.get("coverage_ratio") is not None
                else "",
            }
        )
    return rows


def _pair_kind_counts(
    pairs_frame: list[dict[str, Any]],
    findings: dict[str, Any],
) -> dict[str, int]:
    if pairs_frame and any("pair_kind" in row for row in pairs_frame):
        return dict(Counter(str(row.get("pair_kind") or "ordinary_pair") for row in pairs_frame))
    summary = findings.get("pair_evidence_summary")
    if isinstance(summary, dict) and isinstance(summary.get("pair_kind_counts"), dict):
        return {str(k): int(v) for k, v in summary["pair_kind_counts"].items()}
    return {}


def _coverage_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        scope = str(row.get("summary_scope") or "")
        if scope in {"project", "all"}:
            return row
    page_rows = [row for row in rows if str(row.get("summary_scope") or "") == "page"]
    if not page_rows:
        return {}
    unexplained = sum(int(row.get("unexplained_texts") or 0) for row in page_rows)
    assigned = sum(int(row.get("assigned_texts") or 0) for row in page_rows)
    audit_scope = sum(int(row.get("audit_scope_texts") or 0) for row in page_rows)
    return {
        "unexplained_texts": unexplained,
        "unassigned_wire_segments": sum(
            int(row.get("unassigned_wire_segments") or 0) for row in page_rows
        ),
        "unclassified_blocks": sum(int(row.get("unclassified_blocks") or 0) for row in page_rows),
        "assigned_texts": assigned,
        "audit_scope_texts": audit_scope,
        "coverage_ratio": (assigned / audit_scope) if audit_scope > 0 else None,
    }


def _wire_scope_line_metrics(
    page_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> tuple[int, int]:
    """Restrict unassigned-wire ratio to wire/component extractors.

    Terminal/backplate table pages expose dense grid lines that are intentionally
    not members of pair line-groups; counting them as unassigned wires drowns
    the conductive-wire health signal.
    """

    wire_sheet_ids = {
        str(row.get("sheet_id") or "")
        for row in page_rows
        if str(row.get("route_target") or "") in _WIRE_ROUTE_TARGETS
        and str(row.get("sheet_id") or "")
    }
    if not wire_sheet_ids:
        return 0, 0
    lines = 0
    unassigned = 0
    for row in coverage_rows:
        if str(row.get("summary_scope") or "") != "page":
            continue
        sheet_id = str(row.get("sheet_id") or "")
        if sheet_id not in wire_sheet_ids:
            continue
        lines += int(row.get("line_segments") or 0)
        unassigned += int(row.get("unassigned_wire_segments") or 0)
    return lines, unassigned


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        import pandas as pd
    except ImportError:
        return []
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return []
    return frame.to_dict(orient="records")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _load_json_artifact(
    path: Path,
    *,
    required_keys: tuple[str, ...],
) -> tuple[dict[str, Any], str]:
    payload = _load_json(path)
    if payload is None:
        return {}, "missing" if not path.is_file() else "invalid"
    if any(key not in payload for key in required_keys):
        return payload, "invalid"
    return payload, "valid"


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed != parsed:  # NaN
        return None
    return parsed


def _sum_mapping(values: Mapping[str, Any]) -> int:
    total = 0
    for value in values.values():
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
    return total


def _compact_counts(counts: Mapping[str, int]) -> str:
    parts = [f"{key}:{counts[key]}" for key in sorted(counts) if key]
    return "|".join(parts)


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _render_markdown(evaluation: Mapping[str, Any]) -> str:
    summary = evaluation.get("summary") or {}
    lines = [
        "# Extraction Verification Scorecard",
        "",
        f"- overall_status: **{summary.get('status')}**",
        f"- projects: {summary.get('project_count')}",
        f"- PASS/REVIEW/FAIL: {summary.get('pass_count')}/{summary.get('review_count')}/{summary.get('fail_count')}",
        "",
        "## Projects",
        "",
        "| alias | health | gate | pages | pairs | table_map | component_map | unassigned_wires | unknown_symbols | review_reasons |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in evaluation.get("projects") or []:
        row = item.get("row") or {}
        lines.append(
            "| {alias} | {health} | {gate} | {pages} | {pairs} | {tm} | {cm} | {wires} | {syms} | {review} |".format(
                alias=row.get("project_alias"),
                health=row.get("health_status"),
                gate=row.get("gate_status"),
                pages=row.get("sheet_count"),
                pairs=row.get("pairs"),
                tm=row.get("table_mapping_pairs"),
                cm=row.get("component_mapping_pairs"),
                wires=row.get("unassigned_wire_segments"),
                syms=row.get("unknown_symbol_definitions"),
                review=(row.get("review_reasons") or row.get("fail_reasons") or "-")[:120],
            )
        )
    lines.extend(
        [
            "",
            "## How to read this",
            "",
            "- **FAIL**: conversion/gate incomplete, missing artifacts, or critical failure queue.",
            "- **REVIEW**: structure OK but residual recognition gaps (unsupported CAD types, "
            "unassigned conductive wires on wire/component pages, unknown symbols, scale unresolved, "
            "table routing gaps).",
            "- **PASS**: no FAIL and no REVIEW signals under current thresholds.",
            "- Text coverage_ratio=1.0 does **not** mean every wire/block is electrically recognized.",
            "- Unassigned-wire ratio is scoped to WireDiagram/ComponentDiagram pages; terminal/"
            "backplate table grid lines are excluded from that ratio.",
            "",
        ]
    )
    return "\n".join(lines)
