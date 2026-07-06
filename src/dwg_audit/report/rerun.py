from __future__ import annotations

import json
from pathlib import Path
from shutil import copy2
from typing import Any

import pandas as pd

from dwg_audit.audit import build_issues
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.report.artifacts import _issue_frame
from dwg_audit.report.artifacts import export_existing_reports
from dwg_audit.report.artifacts import load_report_frames
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
                filename=evidence.get("filename"),
                sheet_no=evidence.get("sheet_no"),
                left_value=issue.left_value,
                right_value=issue.right_value,
                confidence=issue.confidence,
                one_to_many_classification=evidence.get("one_to_many_classification"),
            )
    audit_dir = project_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    issues_frame = write_issue_root_cause_audit(project_dir, frames, _issue_frame(issues))
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
