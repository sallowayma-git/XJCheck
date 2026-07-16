from __future__ import annotations

import json
from pathlib import Path
from shutil import copy2
from typing import Any

import pandas as pd

from dwg_audit.audit import build_issues
from dwg_audit.audit.data_quality import build_incomplete_extraction_issues
from dwg_audit.audit.wire_topology import build_topology_shadow_report
from dwg_audit.audit.wire_topology import render_topology_shadow_report_markdown
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.report.artifacts import _issue_frame
from dwg_audit.report.artifacts import _build_issue_witness_frame
from dwg_audit.report.artifacts import _dict_rows_frame
from dwg_audit.report.artifacts import export_existing_reports
from dwg_audit.report.artifacts import load_report_frames
from dwg_audit.audit.audit_v2 import build_audit_v2_issue_clusters
from dwg_audit.audit.audit_v2 import summarize_audit_v2
from dwg_audit.audit.failure_queue import build_failure_queue
from dwg_audit.audit.failure_queue import summarize_failure_queue
from dwg_audit.services.issue_diagnostics import write_issue_root_cause_audit


def rerun_audit_from_findings(
    project_dir: Path,
    config: dict,
    output_dir: Path | None = None,
    *,
    event_sink = None,
) -> Path:
    frames = load_report_frames(project_dir)
    pages = [_sheet_record(row) for _, row in frames.get("pages", pd.DataFrame()).iterrows()]
    line_groups = [_line_group(row) for _, row in frames.get("line_groups", pd.DataFrame()).iterrows()]
    pairs = [_pair(row) for _, row in frames.get("pairs", pd.DataFrame()).iterrows()]
    terminal_candidates = [
        _terminal_candidate(row)
        for _, row in frames.get("terminal_candidates", pd.DataFrame()).iterrows()
    ]

    issues = build_issues(pairs, line_groups, pages, config, terminal_candidates=terminal_candidates)
    issues.extend(build_incomplete_extraction_issues(project_dir, issues, pages))
    if event_sink is not None:
        event_sink.emit(
            "progress",
            stage="audit",
            project_dir=str(project_dir),
            pair_count=len(pairs),
            issue_count=len(issues),
        )
        for issue in issues:
            evidence = issue.evidence or {}
            event_sink.emit(
                "issue_found",
                project_dir=str(project_dir),
                issue_id=issue.issue_id,
                rule_id=issue.rule_id,
                issue_type=issue.issue_type or issue.rule_id,
                severity=issue.severity,
                title=issue.title or issue.message,
                filename=evidence.get("filename") or issue.filename,
                sheet_no=evidence.get("sheet_no") or issue.sheet_no,
                sheet_title=evidence.get("sheet_title"),
                left_value=issue.left_value,
                right_value=issue.right_value,
                confidence=issue.confidence,
                one_to_many_classification=evidence.get("one_to_many_classification"),
                handling_class=evidence.get("handling_class"),
                line_start=evidence.get("line_start"),
                line_end=evidence.get("line_end"),
            )
    audit_dir = project_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    issues_frame = write_issue_root_cause_audit(project_dir, frames, _issue_frame(issues))
    issue_witnesses, issue_witness_summary = _build_issue_witness_frame(
        project_dir, issues_frame
    )
    issue_witnesses.to_parquet(audit_dir / "issue_witnesses_v2.parquet", index=False)
    (audit_dir / "issue_witness_summary.json").write_text(
        json.dumps(issue_witness_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Phase 120: Audit V2 clusters + Failure Queue (shadow; legacy issues retained).
    findings_dir = project_dir / "findings"

    def _read_json_safe(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _parquet_count(path: Path) -> int:
        if not path.is_file():
            return 0
        try:
            return int(len(pd.read_parquet(path)))
        except Exception:
            return 0

    project_graph_summary = _read_json_safe(findings_dir / "project_graph_summary.json")
    engine_comparison = _read_json_safe(findings_dir / "engine_comparison_v1.json")
    constraint_summary = _read_json_safe(findings_dir / "constraint_resolution_summary.json")
    scope_summary = _read_json_safe(findings_dir / "scope_resolution_summary.json")
    findings_payload = _read_json_safe(findings_dir / "findings.json")
    extraction_gate = _read_json_safe(project_dir / "extraction_completeness.json")
    equivalence = None
    equivalence_path = findings_dir / "legacy_pair_network_equivalence.parquet"
    if equivalence_path.is_file():
        try:
            equivalence = pd.read_parquet(equivalence_path)
        except Exception:
            equivalence = None
    endpoint_identities = None
    endpoint_path = findings_dir / "endpoint_identities_v1.parquet"
    if endpoint_path.is_file():
        try:
            endpoint_identities = pd.read_parquet(endpoint_path)
        except Exception:
            endpoint_identities = None

    audit_v2_clusters = build_audit_v2_issue_clusters(
        issues,
        equivalence=equivalence,
        endpoint_identities=endpoint_identities,
    )
    for cluster in audit_v2_clusters:
        cluster.setdefault("issue_count", len(cluster.get("issue_ids") or []))
        cluster.setdefault("schema_version", "audit-v2-cluster-v1")
    audit_v2_summary = {
        **summarize_audit_v2(audit_v2_clusters, issues),
        "legacy_issue_stream_retained": True,
    }
    cross_page_candidate_count = _parquet_count(
        findings_dir / "cross_page_endpoint_candidates_v1.parquet"
    )
    if not cross_page_candidate_count and project_graph_summary:
        cross_page_candidate_count = int(
            ((project_graph_summary.get("edge_counts") or {}).get("cross_page_candidates"))
            or 0
        )
    failure_items = build_failure_queue(
        extraction_gate=extraction_gate or None,
        scope_summary=scope_summary or None,
        constraint_summary=constraint_summary or None,
        page_capability_matrix=findings_payload.get("page_capability_matrix"),
        audit_v2_summary=audit_v2_summary,
        engine_comparison=engine_comparison or None,
        open_endpoint_count=_parquet_count(findings_dir / "network_open_endpoints_v2.parquet"),
        cross_page_candidate_count=cross_page_candidate_count,
        project_graph_summary=project_graph_summary or None,
        project_id=str(findings_payload.get("project_id") or project_dir.name),
    )
    for item in failure_items:
        item.setdefault("schema_version", "failure-queue-v1")
    failure_summary = summarize_failure_queue(failure_items)
    failure_summary = {
        **failure_summary,
        "item_count": int(failure_summary.get("failure_count", len(failure_items))),
    }
    audit_v2_columns = (
        "cluster_id",
        "schema_version",
        "algorithm_version",
        "rule_id",
        "sheet_id",
        "severity_max",
        "issue_ids",
        "pair_ids",
        "issue_count",
        "root_kind",
        "witness_status",
        "message_summary",
    )
    failure_columns = (
        "failure_id",
        "schema_version",
        "algorithm_version",
        "category",
        "severity",
        "state",
        "page_or_project",
        "message",
        "suggested_routing",
        "evidence_ref",
    )
    _dict_rows_frame(audit_v2_clusters, audit_v2_columns).to_parquet(
        audit_dir / "audit_v2_issue_clusters.parquet", index=False
    )
    (audit_dir / "audit_v2_summary.json").write_text(
        json.dumps(audit_v2_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _dict_rows_frame(failure_items, failure_columns).to_parquet(
        audit_dir / "failure_queue.parquet", index=False
    )
    (audit_dir / "failure_queue_summary.json").write_text(
        json.dumps(failure_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    topology_shadow_payload = build_topology_shadow_report(
        issues_frame=issues_frame,
        pairs_frame=frames.get("pairs", pd.DataFrame()),
        line_groups_frame=frames.get("line_groups", pd.DataFrame()),
        wire_networks_frame=frames.get("wire_networks", pd.DataFrame()),
        wire_junctions_frame=frames.get("wire_junctions", pd.DataFrame()),
        text_assignments_frame=frames.get("text_assignments", pd.DataFrame()),
        config=config,
    )
    (audit_dir / "topology_shadow_report.json").write_text(
        json.dumps(topology_shadow_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (audit_dir / "topology_shadow_report.md").write_text(
        render_topology_shadow_report_markdown(topology_shadow_payload),
        encoding="utf-8",
    )
    export_existing_reports(project_dir)
    if event_sink is not None:
        event_sink.emit(
            "audit_finished",
            project_dir=str(project_dir),
            audit_dir=str(audit_dir),
            issue_count=len(issues),
        )

    if output_dir is not None and output_dir.resolve() != audit_dir.resolve():
        output_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "issues.parquet",
            "issues.json",
            "issue_root_cause_audit.json",
            "issue_root_cause_audit.md",
            "audit_report.md",
            "audit_report.html",
            "issues.xlsx",
            "topology_shadow_report.json",
            "topology_shadow_report.md",
            "issue_witnesses_v2.parquet",
            "issue_witness_summary.json",
        ):
            copy2(audit_dir / name, output_dir / name)
        return output_dir
    return audit_dir


def _sheet_record(row: pd.Series) -> SheetRecord:
    return SheetRecord(
        sheet_id=str(row["sheet_id"]),
        file_id=str(row["file_id"]),
        filename=str(row["filename"]),
        sheet_order=int(row["sheet_order"]),
        sheet_no=_nullable_str(row.get("sheet_no")),
        sheet_title=_nullable_str(row.get("sheet_title")) or "",
        sheet_category=_nullable_str(row.get("sheet_category")),
        audit_role=_nullable_str(row.get("audit_role")) or "secondary",
        page_no_source=_nullable_str(row.get("page_no_source")) or "unknown",
        is_primary_audit_candidate=bool(row.get("is_primary_audit_candidate", False)),
        source_refs=_json_list(row.get("source_refs")),
        warnings=_json_list(row.get("warnings")),
        layout_name=_nullable_str(row.get("layout_name")),
        drawing_units=_nullable_str(row.get("drawing_units")),
        extent_bbox=_json_bbox(row.get("extent_bbox")),
        frame_bbox=_json_bbox(row.get("frame_bbox")),
        title_block_bbox=_json_bbox(row.get("title_block_bbox")),
        audit_area_bbox=_json_bbox(row.get("audit_area_bbox")),
        page_type_confidence=_nullable_float(row.get("page_type_confidence")),
        route_target=_nullable_str(row.get("route_target")),
        audit_disposition=_nullable_str(row.get("audit_disposition")),
    )


def _line_group(row: pd.Series) -> LineGroup:
    return LineGroup(
        line_group_id=str(row["line_group_id"]),
        sheet_id=str(row["sheet_id"]),
        file_id=str(row["file_id"]),
        start_x=float(row["start_x"]),
        start_y=float(row["start_y"]),
        end_x=float(row["end_x"]),
        end_y=float(row["end_y"]),
        length=float(row["length"]),
        wire_candidate_score=float(row["wire_candidate_score"]),
        member_line_ids=_json_list(row.get("member_line_ids")),
        layer_hints=_json_list(row.get("layer_hints")),
        orientation=_nullable_str(row.get("orientation")) or "horizontal",
        row_band_id=_nullable_str(row.get("row_band_id")),
    )


def _pair(row: pd.Series) -> Pair:
    return Pair(
        pair_id=str(row["pair_id"]),
        line_group_id=str(row["line_group_id"]),
        sheet_id=str(row["sheet_id"]),
        file_id=str(row["file_id"]),
        selected_pair_candidate_id=_nullable_str(row.get("selected_pair_candidate_id")),
        left_value=_nullable_str(row.get("left_value")),
        right_value=_nullable_str(row.get("right_value")),
        confidence=float(row.get("confidence", 0.0)),
        status=_nullable_str(row.get("status")) or "review",
        rationale=_nullable_str(row.get("rationale")) or "",
        alternative_pair_candidate_ids=_json_list(row.get("alternative_pair_candidate_ids")),
        confidence_bucket=_nullable_str(row.get("confidence_bucket")),
        evidence=_json_dict(row.get("evidence")),
        left_candidate_id=_nullable_str(row.get("left_candidate_id")),
        right_candidate_id=_nullable_str(row.get("right_candidate_id")),
        left_text_id=_nullable_str(row.get("left_text_id")),
        right_text_id=_nullable_str(row.get("right_text_id")),
        left_coord_x=_nullable_float(row.get("left_coord_x")),
        left_coord_y=_nullable_float(row.get("left_coord_y")),
        right_coord_x=_nullable_float(row.get("right_coord_x")),
        right_coord_y=_nullable_float(row.get("right_coord_y")),
        pair_kind=_nullable_str(row.get("pair_kind")) or "ordinary_pair",
    )


def _terminal_candidate(row: pd.Series) -> TerminalCandidate:
    return TerminalCandidate(
        candidate_id=str(row["candidate_id"]),
        line_group_id=str(row["line_group_id"]),
        sheet_id=str(row["sheet_id"]),
        file_id=str(row["file_id"]),
        side=str(row["side"]),
        text_id=str(row["text_id"]),
        text=str(row["text"]),
        value=_nullable_str(row.get("value")),
        score=float(row.get("score", 0.0)),
        status=_nullable_str(row.get("status")) or "rejected",
        rejection_reason=_nullable_str(row.get("rejection_reason")),
        endpoint_x=float(row.get("endpoint_x", 0.0)),
        endpoint_y=float(row.get("endpoint_y", 0.0)),
        distance_x=float(row.get("distance_x", 0.0)),
        distance_y=float(row.get("distance_y", 0.0)),
        text_insert_x=_nullable_float(row.get("text_insert_x")),
        text_insert_y=_nullable_float(row.get("text_insert_y")),
        vertical_alignment_score=_nullable_float(row.get("vertical_alignment_score")),
        horizontal_side_score=_nullable_float(row.get("horizontal_side_score")),
        text_type_score=_nullable_float(row.get("text_type_score")),
        height_score=_nullable_float(row.get("height_score")),
        rank=_nullable_int(row.get("rank")),
        source_block_name=_nullable_str(row.get("source_block_name")),
        channel=_nullable_str(row.get("channel")) or "terminal_numeric_channel",
        channel_detail=_nullable_str(row.get("channel_detail")),
    )


def _nullable_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value)
    return None if text == "None" else text


def _nullable_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nullable_int(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_list(value: object) -> list[Any]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _json_dict(value: object) -> dict[str, Any]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _json_bbox(value: object) -> tuple[float, float, float, float] | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
    else:
        decoded = value
    if not isinstance(decoded, (list, tuple)) or len(decoded) != 4:
        return None
    return tuple(float(item) for item in decoded)
