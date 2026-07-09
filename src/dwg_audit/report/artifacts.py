from __future__ import annotations

from collections import Counter
from collections import defaultdict
import json
import re
from dataclasses import fields
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import ExtractionWarning
from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import PairCandidate
from dwg_audit.domain.models import PolylineRecord
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SidecarInfo
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TerminalStrip
from dwg_audit.domain.models import TextItem
from dwg_audit.domain.models import record_dict
from dwg_audit.audit.coverage import build_entity_coverage_summary
from dwg_audit.audit.coverage import build_text_assignment_frame
from dwg_audit.audit.wire_topology import build_wire_topology_frames

_REPORT_FORMATS = ("md", "html", "xlsx")
_ISSUE_STRUCTURED_COLUMNS = ("evidence", "related_pair_ids", "sheet_ids", "values", "evidence_refs")


def _frame(records: list[Any], cls: type) -> pd.DataFrame:
    columns = [field.name for field in fields(cls)]
    if not records:
        return pd.DataFrame(columns=columns)

    serialized: list[dict[str, Any]] = []
    for item in records:
        row = record_dict(item)
        for key, value in list(row.items()):
            if isinstance(value, (list, tuple, dict)):
                row[key] = json.dumps(value, ensure_ascii=False)
        serialized.append(row)
    return pd.DataFrame(serialized, columns=columns)


def _restore_jsonish_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    if frame.empty:
        return frame
    restored = frame.copy()
    for column in columns:
        if column not in restored.columns:
            continue
        restored[column] = restored[column].apply(_decode_jsonish)
    return restored


def _issue_frame(issues: list[Issue]) -> pd.DataFrame:
    frame = _restore_jsonish_columns(_frame(issues, Issue), _ISSUE_STRUCTURED_COLUMNS)
    if "evidence" in frame.columns:
        frame["evidence"] = frame["evidence"].apply(
            lambda value: None if isinstance(value, dict) and not value else value
        )
    frame = _backfill_issue_contract_fields(frame)
    return frame


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return slug or "project"


def write_project_artifacts(
    artifacts: ProjectArtifacts,
    output_dir: Path,
    config: dict | None = None,
    *,
    page_classifications: dict[str, PageClassification] | None = None,
    table_mappings: list[dict[str, Any]] | None = None,
) -> Path:
    project_slug = _slugify(artifacts.scan.manifest.project_id)
    project_dir = output_dir / project_slug
    findings_dir = project_dir / "findings"
    persist_page_findings = bool((config or {}).get("runtime", {}).get("persist_page_findings_files", False))
    page_findings_dir = findings_dir / "page_findings"
    project_dir.mkdir(parents=True, exist_ok=True)
    findings_dir.mkdir(parents=True, exist_ok=True)
    if persist_page_findings:
        page_findings_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = project_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(record_dict(artifacts.scan.manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _frame(artifacts.scan.manifest.source_files, SourceFileRecord).to_parquet(findings_dir / "source_files.parquet", index=False)
    _frame(artifacts.scan.manifest.sidecars, SidecarInfo).to_parquet(findings_dir / "sidecars.parquet", index=False)
    _frame(artifacts.scan.pages, SheetRecord).to_parquet(findings_dir / "pages.parquet", index=False)
    _frame(artifacts.scan.terminal_strips, TerminalStrip).to_parquet(findings_dir / "terminal_strips.parquet", index=False)
    _frame(artifacts.texts, TextItem).to_parquet(findings_dir / "texts.parquet", index=False)
    _frame(artifacts.lines, LineEntity).to_parquet(findings_dir / "lines.parquet", index=False)
    _frame(artifacts.blocks, BlockRecord).to_parquet(findings_dir / "blocks.parquet", index=False)
    _frame(artifacts.polylines, PolylineRecord).to_parquet(findings_dir / "polylines.parquet", index=False)
    _frame(artifacts.line_groups, LineGroup).to_parquet(findings_dir / "line_groups.parquet", index=False)
    _frame(artifacts.terminal_candidates, TerminalCandidate).to_parquet(findings_dir / "terminal_candidates.parquet", index=False)
    _frame(artifacts.pair_candidates, PairCandidate).to_parquet(findings_dir / "pair_candidates.parquet", index=False)
    _frame(artifacts.pairs, Pair).to_parquet(findings_dir / "pairs.parquet", index=False)
    _frame(artifacts.extraction_warnings, ExtractionWarning).to_parquet(findings_dir / "extraction_warnings.parquet", index=False)
    text_assignments = build_text_assignment_frame(
        artifacts,
        page_classifications=page_classifications,
    )
    entity_coverage_summary_frame, entity_coverage_summary = build_entity_coverage_summary(
        text_assignments,
        artifacts=artifacts,
        page_classifications=page_classifications,
    )
    wire_junctions, wire_networks, _ = build_wire_topology_frames(
        artifacts,
        config=config,
    )
    text_assignments.to_parquet(findings_dir / "text_assignments.parquet", index=False)
    entity_coverage_summary_frame.to_parquet(findings_dir / "entity_coverage_summary.parquet", index=False)
    wire_junctions.to_parquet(findings_dir / "wire_junctions.parquet", index=False)
    wire_networks.to_parquet(findings_dir / "wire_networks.parquet", index=False)

    findings_payload = _build_findings_payload(
        artifacts,
        config=config,
        page_classifications=page_classifications,
        table_mappings=table_mappings,
        entity_coverage_summary=entity_coverage_summary,
    )
    if persist_page_findings:
        for page_finding in findings_payload["page_findings"]:
            sheet_id = str(page_finding["sheet_id"])
            (page_findings_dir / f"{sheet_id}.json").write_text(
                json.dumps(page_finding, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (page_findings_dir / f"{sheet_id}.md").write_text(
                _build_page_finding_markdown(page_finding),
                encoding="utf-8",
            )
    (findings_dir / "findings.json").write_text(json.dumps(findings_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (findings_dir / "findings.md").write_text(_build_findings_markdown(findings_payload), encoding="utf-8")
    return project_dir


def write_audit_outputs(
    project_dir: Path,
    issues: list[Issue],
    pairs: list[Pair],
    source_files: list[SourceFileRecord],
    project_name: str,
    formats: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> Path:
    audit_dir = project_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    issues_frame = _issue_frame(issues)
    issues_frame.to_parquet(audit_dir / "issues.parquet", index=False)
    issues_frame.to_json(audit_dir / "issues.json", orient="records", force_ascii=False, indent=2)

    frames = {
        "issues": issues_frame,
        "pairs": _frame(pairs, Pair),
        "low_confidence_pairs": _frame([pair for pair in pairs if pair.status != "pass"], Pair),
        "files": _frame(source_files, SourceFileRecord),
    }
    _write_reports(audit_dir, project_name, frames, formats=formats)
    return audit_dir


def _stringify_summary_value(value: Any) -> str:
    value = _normalize_jsonish_value(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _is_blank_value(value: Any) -> bool:
    value = _normalize_jsonish_value(value)
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, tuple, dict)) and not value:
        return True
    if not isinstance(value, (list, tuple, dict)):
        try:
            if pd.isna(value):
                return True
        except TypeError:
            pass
    return False


def _display_value(value: Any, *, default: str = "-") -> str:
    return default if _is_blank_value(value) else str(value)


def _format_confidence(confidence: Any) -> str:
    if isinstance(confidence, (float, int)) and not pd.isna(confidence):
        return f"{confidence:.2f}"
    return _display_value(confidence)


def _count_labels(values: list[Any], *, missing_label: str = "unknown") -> dict[str, int]:
    counter: Counter[str] = Counter()
    for value in values:
        label = missing_label if _is_blank_value(value) else str(value)
        counter[label] += 1
    return dict(sorted(counter.items()))


def _format_pair_label(left_value: Any, right_value: Any) -> str:
    return f"{_display_value(left_value, default='?')} -> {_display_value(right_value, default='?')}"


def _pair_evidence_mapping(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("pair_evidence")
    if isinstance(nested, dict):
        return nested
    return payload


def _pair_semantics_parts(payload: Any) -> list[str]:
    evidence = _pair_evidence_mapping(payload)
    top_level = payload if isinstance(payload, dict) else {}
    parts: list[str] = []

    def semantic_value(key: str) -> Any:
        value = evidence.get(key)
        if not _is_blank_value(value):
            return value
        return top_level.get(key)

    pair_kind = semantic_value("pair_kind")
    if not _is_blank_value(pair_kind):
        parts.append(f"pair_kind={pair_kind}")
    continuation_kind = semantic_value("continuation_kind")
    if not _is_blank_value(continuation_kind):
        parts.append(f"continuation_kind={continuation_kind}")
    bridge_mapping_kind = semantic_value("bridge_mapping_kind")
    if not _is_blank_value(bridge_mapping_kind):
        parts.append(f"bridge_mapping_kind={bridge_mapping_kind}")
    semantic_mapping_kind = semantic_value("semantic_mapping_kind")
    if not _is_blank_value(semantic_mapping_kind):
        parts.append(f"semantic_mapping_kind={semantic_mapping_kind}")
    semantic_marker_texts = semantic_value("semantic_marker_texts")
    if isinstance(semantic_marker_texts, list) and semantic_marker_texts:
        parts.append(f"semantic_markers={'|'.join(str(item) for item in semantic_marker_texts[:3])}")
    component_submode = semantic_value("component_submode")
    if not _is_blank_value(component_submode):
        parts.append(f"component_submode={component_submode}")
    component_branch_kind = semantic_value("component_branch_kind")
    if not _is_blank_value(component_branch_kind):
        parts.append(f"component_branch_kind={component_branch_kind}")
    shared_endpoint = semantic_value("shared_endpoint")
    if not _is_blank_value(shared_endpoint):
        parts.append(f"shared_endpoint={shared_endpoint}")
    external_endpoint_splits = semantic_value("external_endpoint_splits")
    if isinstance(external_endpoint_splits, list) and external_endpoint_splits:
        parts.append(f"external_endpoint_splits={'|'.join(str(item) for item in external_endpoint_splits[:4])}")
    external_endpoint_split = semantic_value("external_endpoint_split")
    if not _is_blank_value(external_endpoint_split) and _is_blank_value(external_endpoint_splits):
        parts.append(f"external_endpoint_split={external_endpoint_split}")
    orientation = semantic_value("line_orientation")
    if not _is_blank_value(orientation):
        parts.append(f"orientation={orientation}")
    left_side = semantic_value("left_side_label")
    if not _is_blank_value(left_side):
        parts.append(f"left_side={left_side}")
    right_side = semantic_value("right_side_label")
    if not _is_blank_value(right_side):
        parts.append(f"right_side={right_side}")
    return parts


def _pair_semantics_summary(payload: Any) -> str:
    parts = _pair_semantics_parts(payload)
    return ", ".join(parts) if parts else ""


def _pair_evidence_summary(pair: Pair) -> str:
    evidence = pair.evidence or {}
    parts: list[str] = []

    for key in ("filename", "sheet_no", "sheet_order", "line_start", "line_end"):
        value = evidence.get(key)
        if _is_blank_value(value):
            continue
        parts.append(f"{key}={_stringify_summary_value(value)}")

    line_group = evidence.get("line_group_id") or evidence.get("line_group") or pair.line_group_id
    if line_group:
        parts.append(f"line_group={line_group}")

    if pair.left_value:
        parts.append(f"left_value={pair.left_value}")
    if pair.right_value:
        parts.append(f"right_value={pair.right_value}")
    parts.extend(_pair_semantics_parts(evidence))

    return ", ".join(parts) if parts else "no evidence"


def _pair_requires_review(pair: Pair) -> bool:
    return pair.status in {"review", "fail"} or pair.confidence_bucket == "review"


def _pair_review_sort_key(pair: Pair) -> tuple[int, int, float, str]:
    status_order = {"fail": 0, "review": 1, "discard": 2, "pass": 3}
    bucket_order = {"low": 0, "review": 1, "high": 2}
    return (
        status_order.get(pair.status, 99),
        bucket_order.get(pair.confidence_bucket or "", 98),
        pair.confidence,
        pair.pair_id,
    )


def _build_pair_example(pair: Pair) -> dict[str, Any]:
    return {
        "pair_id": pair.pair_id,
        "pair_kind": pair.pair_kind,
        "status": pair.status,
        "confidence": pair.confidence,
        "confidence_bucket": pair.confidence_bucket,
        "left_value": pair.left_value,
        "right_value": pair.right_value,
        "rationale": pair.rationale,
        "line_semantics": _pair_semantics_summary(pair.evidence or {}),
        "summary": _pair_evidence_summary(pair),
    }


def _build_pair_findings_summary(pairs: list[Pair]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    confidence_bucket_counts: dict[str, int] = {}
    pair_kind_counts: dict[str, int] = {}
    with_evidence = 0
    examples: list[dict[str, Any]] = []
    review_examples: list[dict[str, Any]] = []
    review_pairs = sorted((pair for pair in pairs if _pair_requires_review(pair)), key=_pair_review_sort_key)

    for pair in pairs:
        status_counts[pair.status] = status_counts.get(pair.status, 0) + 1
        bucket = pair.confidence_bucket or "unknown"
        confidence_bucket_counts[bucket] = confidence_bucket_counts.get(bucket, 0) + 1
        pair_kind = pair.pair_kind or "ordinary_pair"
        pair_kind_counts[pair_kind] = pair_kind_counts.get(pair_kind, 0) + 1
        if pair.evidence:
            with_evidence += 1
        if len(examples) >= 5:
            continue
        examples.append(_build_pair_example(pair))

    for pair in review_pairs[:5]:
        review_examples.append(_build_pair_example(pair))

    return {
        "total_pairs": len(pairs),
        "pairs_with_evidence": with_evidence,
        "review_pairs": len(review_pairs),
        "pair_kind_counts": dict(sorted(pair_kind_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "confidence_bucket_counts": dict(sorted(confidence_bucket_counts.items())),
        "examples": examples,
        "review_examples": review_examples,
    }


def _complete_pair(pair: Pair) -> bool:
    return pair.status != "discard" and bool(pair.left_value) and bool(pair.right_value)


def _high_confidence_pair(pair: Pair) -> bool:
    return pair.status == "pass" or pair.confidence_bucket == "high"


def _configured_one_to_many_branch_left_values(config: dict | None) -> set[str]:
    if not config:
        return set()
    configured = config.get("rules", {}).get("one_to_many_branch_left_values", [])
    return {str(value) for value in configured if value is not None}


def _one_to_many_cluster_sort_key(cluster: dict[str, Any]) -> tuple[int, int, str]:
    classification_order = {"conflict": 0, "review": 1, "branch": 2}
    return (
        classification_order.get(str(cluster.get("classification")), 99),
        -int(cluster.get("distinct_right_count", 0)),
        str(cluster.get("left_value", "")),
    )


def _build_one_to_many_review_table(pairs: list[Pair], config: dict | None = None) -> dict[str, Any]:
    complete_pairs = [pair for pair in pairs if _complete_pair(pair)]
    pair_lookup = {(pair.left_value, pair.right_value) for pair in complete_pairs}
    branch_allowlist = _configured_one_to_many_branch_left_values(config)
    left_to_pairs: dict[str, list[Pair]] = {}
    for pair in complete_pairs:
        left_to_pairs.setdefault(pair.left_value, []).append(pair)

    clusters: list[dict[str, Any]] = []
    for left_value, linked_pairs in left_to_pairs.items():
        right_values = sorted({pair.right_value for pair in linked_pairs if pair.right_value})
        if len(right_values) <= 1:
            continue

        sheet_ids = sorted({pair.sheet_id for pair in linked_pairs if pair.sheet_id})
        sheet_nos = sorted({pair.evidence.get("sheet_no") for pair in linked_pairs if pair.evidence.get("sheet_no")})
        filenames = sorted({pair.evidence.get("filename") for pair in linked_pairs if pair.evidence.get("filename")})
        pair_rows = []
        reciprocal_pair_count = 0
        high_confidence_pair_count = 0
        for pair in sorted(linked_pairs, key=lambda item: ((item.evidence or {}).get("sheet_order", 0), item.right_value or "", item.pair_id)):
            reciprocal = bool(pair.left_value and pair.right_value and (pair.right_value, pair.left_value) in pair_lookup)
            if reciprocal:
                reciprocal_pair_count += 1
            if _high_confidence_pair(pair):
                high_confidence_pair_count += 1
            pair_rows.append(
                {
                    "pair_id": pair.pair_id,
                    "sheet_id": pair.sheet_id,
                    "line_group_id": pair.line_group_id,
                    "right_value": pair.right_value,
                    "filename": pair.evidence.get("filename"),
                    "sheet_no": pair.evidence.get("sheet_no"),
                    "sheet_order": pair.evidence.get("sheet_order"),
                    "status": pair.status,
                    "confidence": pair.confidence,
                    "confidence_bucket": pair.confidence_bucket,
                    "has_reciprocal": reciprocal,
                    "location": {
                        "filename": pair.evidence.get("filename"),
                        "sheet_no": pair.evidence.get("sheet_no"),
                        "sheet_order": pair.evidence.get("sheet_order"),
                        "line_start": pair.evidence.get("line_start"),
                        "line_end": pair.evidence.get("line_end"),
                    },
                    "summary": _pair_evidence_summary(pair),
                }
            )

        cross_page = len(sheet_ids) > 1
        if left_value in branch_allowlist:
            classification = "branch"
            classification_reason = "allowlisted_branch"
        elif cross_page and high_confidence_pair_count == len(linked_pairs):
            classification = "conflict"
            classification_reason = "cross_page_multi_target"
        else:
            classification = "review"
            classification_reason = "weak_evidence"
        clusters.append(
            {
                "cluster_id": f"OTM:{left_value}",
                "left_value": left_value,
                "classification": classification,
                "classification_reason": classification_reason,
                "distinct_right_count": len(right_values),
                "pair_count": len(linked_pairs),
                "right_values": right_values,
                "sheet_ids": sheet_ids,
                "sheet_nos": sheet_nos,
                "filenames": filenames,
                "cross_page": cross_page,
                "high_confidence_pair_count": high_confidence_pair_count,
                "reciprocal_pair_count": reciprocal_pair_count,
                "status_counts": _count_labels([pair.status for pair in linked_pairs]),
                "confidence_bucket_counts": _count_labels([pair.confidence_bucket for pair in linked_pairs]),
                "pairs": pair_rows,
            }
        )

    ordered_clusters = sorted(clusters, key=_one_to_many_cluster_sort_key)
    return {
        "cluster_count": len(ordered_clusters),
        "branch_cluster_count": sum(1 for cluster in ordered_clusters if cluster["classification"] == "branch"),
        "review_cluster_count": sum(1 for cluster in ordered_clusters if cluster["classification"] == "review"),
        "conflict_cluster_count": sum(1 for cluster in ordered_clusters if cluster["classification"] == "conflict"),
        "clusters": ordered_clusters,
    }


def _per_sheet_counts(records: list[Any], sheet_attr: str = "sheet_id") -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        sheet_id = getattr(record, sheet_attr, None)
        if sheet_id:
            counts[str(sheet_id)] += 1
    return dict(counts)


def _per_sheet_candidate_channel_counts(candidates: list[TerminalCandidate]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for candidate in candidates:
        if not candidate.sheet_id:
            continue
        channel = candidate.channel or "unknown"
        counts[str(candidate.sheet_id)][str(channel)] += 1
    return {sheet_id: dict(channel_counts) for sheet_id, channel_counts in counts.items()}


def _per_sheet_pair_kind_counts(pairs: list[Pair]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for pair in pairs:
        if not pair.sheet_id:
            continue
        pair_kind = pair.pair_kind or "ordinary_pair"
        counts[str(pair.sheet_id)][str(pair_kind)] += 1
    return {sheet_id: dict(pair_kind_counts) for sheet_id, pair_kind_counts in counts.items()}


def _per_sheet_orientation_counts(line_groups: list[LineGroup]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for group in line_groups:
        if not group.sheet_id:
            continue
        orientation = group.orientation or "horizontal"
        counts[str(group.sheet_id)][str(orientation)] += 1
    return {sheet_id: dict(orientation_counts) for sheet_id, orientation_counts in counts.items()}


def _page_route_target(page: SheetRecord, *, table_like: bool) -> str:
    explicit_route = getattr(page, "route_target", None)
    if explicit_route:
        return str(explicit_route)
    if page.audit_role == "skip":
        return "SkipExtractor"
    if table_like:
        return "TableExtractor (planned)"
    if page.sheet_category == "二次原理图":
        return "WireDiagramExtractor"
    if page.sheet_category == "元件接线图":
        return "ComponentDiagramExtractor"
    if page.sheet_category == "屏端子图":
        return "TerminalDiagramExtractor"
    return "LayoutOnlyExtractor"


def _page_audit_disposition(
    page: SheetRecord,
    *,
    classification: PageClassification | None = None,
    route_target: str | None = None,
) -> str:
    if classification is not None and classification.audit_disposition:
        return classification.audit_disposition
    explicit_disposition = getattr(page, "audit_disposition", None)
    if explicit_disposition:
        return str(explicit_disposition)
    resolved_route_target = route_target or _page_route_target(page, table_like=False)
    if page.audit_role == "skip" or resolved_route_target == "SkipExtractor":
        return "skip_stable"
    if page.audit_role == "supplemental":
        return "audit_required"
    if resolved_route_target in {
        "WireDiagramExtractor",
        "ComponentDiagramExtractor",
        "TerminalDiagramExtractor",
        "TableExtractor",
    }:
        return "audit_required"
    return "classify_only"


def _page_type_confidence(page: SheetRecord) -> float:
    explicit_confidence = getattr(page, "page_type_confidence", None)
    if explicit_confidence is not None:
        return float(explicit_confidence)
    title = page.sheet_title or page.filename or ""
    category = page.sheet_category or ""
    if category in {"封面/目录", "屏面布置图", "屏端子图", "元件接线图", "背板接线图"} and category.replace("图", "")[:2] in title:
        return 0.98
    if category == "二次原理图":
        if any(keyword in title for keyword in ("回路", "信号", "保护", "出口", "操作", "开入", "控制")):
            return 0.9
        return 0.75
    if category:
        return 0.7
    return 0.25


def _dominant_orientation(orientation_counts: dict[str, int]) -> str:
    if not orientation_counts:
        return "none"
    if len(orientation_counts) == 1:
        return next(iter(orientation_counts))
    ordered = sorted(orientation_counts.items(), key=lambda item: (-item[1], item[0]))
    if len(ordered) >= 2 and ordered[0][1] == ordered[1][1]:
        return "mixed"
    return ordered[0][0]


def _page_high_confidence_signals(
    *,
    page: SheetRecord,
    audit_disposition: str,
    dominant_orientation: str,
    non_discard_pair_count: int,
    high_confidence_pair_count: int,
    line_group_count: int,
    issue_count: int,
    table_mapping_count: int,
) -> list[str]:
    signals: list[str] = []
    if audit_disposition == "skip_stable":
        signals.append("Configured as a non-audit page and excluded from downstream pairing.")
    else:
        signals.append(f"Current audit disposition is `{audit_disposition}` (scan role: `{page.audit_role}`).")
    if table_mapping_count:
        signals.append(f"Structured table mappings recovered: {table_mapping_count}.")
    if line_group_count:
        signals.append(f"Line groups formed: {line_group_count}.")
    if dominant_orientation != "none":
        signals.append(f"Dominant line-group orientation: {dominant_orientation}.")
    if non_discard_pair_count:
        signals.append(f"Non-discard pairs retained for review: {non_discard_pair_count}.")
    if high_confidence_pair_count:
        signals.append(f"High-confidence pairs available: {high_confidence_pair_count}.")
    if issue_count:
        signals.append(f"Current audit issues on this page: {issue_count}.")
    return signals


def _page_open_questions(
    *,
    page: SheetRecord,
    audit_disposition: str,
    table_like: bool,
    route_target: str,
    line_group_count: int,
    pair_count: int,
    non_discard_pair_count: int,
    high_confidence_pair_count: int,
    table_mapping_count: int,
) -> list[str]:
    questions: list[str] = []
    if audit_disposition == "classify_only":
        questions.append("Current audit disposition keeps this page in classification-only mode by default.")
    if audit_disposition == "audit_required" and page.audit_role == "supplemental" and line_group_count == 0:
        questions.append("This audit-required supplemental page is included, but the current extractor still produced no usable line groups.")
    if pair_count > 0 and high_confidence_pair_count == 0:
        questions.append("All current pairs still require manual review; high-confidence confirmation is not established yet.")
    if page.sheet_category == "元件接线图" and non_discard_pair_count > 0 and high_confidence_pair_count == 0:
        questions.append("Component-page semantics are partially understood, but the remaining mappings still need manual verification.")
    if table_like and route_target != "TableExtractor":
        questions.append("The page looks table-heavy, but it did not route into the dedicated table extractor.")
    elif route_target == "TableExtractor" and table_mapping_count == 0:
        questions.append("The page routed into the table extractor, but no stable three-column mappings were recovered yet.")
    if page.sheet_category is None:
        questions.append("Page category is unresolved and still depends on fallback routing.")
    return questions


def _page_recognition_strategy(
    page: SheetRecord,
    *,
    page_type: str,
    page_subtype: str | None,
    classification_features: dict[str, Any],
    audit_disposition: str,
    table_like: bool,
    grid_heavy: bool,
    route_target: str,
    table_mapping_count: int,
) -> str:
    feature_parts: list[str] = []
    for key in ("grid_band_count", "horizontal_line_ratio", "vertical_line_ratio", "polyline_count", "block_count"):
        if key not in classification_features:
            continue
        feature_parts.append(f"{key}={classification_features[key]}")
    if grid_heavy:
        feature_parts.append("grid_heavy=True")
    if table_like:
        feature_parts.append("table_like=True")
    feature_text = f" using features [{', '.join(feature_parts)}]" if feature_parts else ""
    subtype_text = f" / `{page_subtype}`" if page_subtype else ""
    if route_target == "TableExtractor":
        if table_mapping_count:
            return (
                f"PageClassifier labeled this page as `{page_type}`{subtype_text}{feature_text}, routed it to "
                f"`{route_target}`, and the dedicated table path recovered "
                f"{table_mapping_count} structured row mappings."
            )
        return (
            f"PageClassifier labeled this page as `{page_type}`{subtype_text}{feature_text}, routed it to "
            f"`{route_target}` because the geometry looks table-heavy, "
            "but stable row/column mappings have not been recovered yet."
        )
    if table_like:
        return (
            f"PageClassifier labeled this page as `{page_type}`{subtype_text}{feature_text}; "
            f"the geometry also looks table-heavy, but the current route target remains `{route_target}`."
        )
    return (
        f"PageClassifier labeled this page as `{page_type}`{subtype_text}{feature_text} and Page Router sent it to "
        f"`{route_target}` with audit disposition `{audit_disposition}` (scan role `{page.audit_role}`, "
        f"coarse category `{page.sheet_category or 'unknown'}`)."
    )


def _page_number_matching_strategy(
    page: SheetRecord,
    *,
    dominant_orientation: str,
    route_target: str,
    table_mapping_count: int,
) -> str:
    if route_target == "WireDiagramExtractor":
        return "Use horizontal line groups and left/right endpoint windows to score nearby numeric texts."
    if route_target == "ComponentDiagramExtractor":
        if dominant_orientation == "vertical":
            return "Use vertical line groups, top/bottom endpoint windows, scoped suffix parsing, and block-aware candidate filters."
        return "Use component-page line groups with scoped candidate rules while keeping horizontal pages conservative."
    if route_target == "TerminalDiagramExtractor":
        return "Use terminal-page endpoint windows with wider geometry tolerances and keep low-confidence candidates visible for review."
    if route_target == "SkipExtractor":
        return "No number matching is attempted because the page is currently marked as non-audit."
    if route_target.startswith("TableExtractor"):
        if table_mapping_count:
            if page.sheet_category == "背板接线图":
                return "Use expanded INSERT virtual text to combine normalized backplate headers and row numbers with same-row external terminal endpoints as high-confidence structured evidence."
            return "Use table grid rows/columns and emit middle-column-to-outer-column mappings as high-confidence structured evidence."
        return "Use the dedicated table path to search for stable row/column cell mappings before falling back to open questions."
    return "Only layout-level evidence is preserved for now; no dedicated number matching strategy is active on this page."


def _extractor_execution_by_sheet(
    extractor_runs: list[dict[str, Any]],
) -> dict[str, str]:
    execution_by_sheet: dict[str, str] = {}
    for run in extractor_runs:
        executed_extractor = str(run.get("executed_extractor") or "")
        if not executed_extractor:
            continue
        for sheet_id in run.get("sheet_ids", []):
            if sheet_id is None:
                continue
            execution_by_sheet[str(sheet_id)] = executed_extractor
    return execution_by_sheet


def _page_execution_status(
    *,
    route_target: str,
    audit_disposition: str,
    executed_extractor: str | None,
) -> str:
    if executed_extractor is not None:
        return "executed"
    if route_target == "LayoutOnlyExtractor" and audit_disposition == "classify_only":
        return "classify_only"
    if route_target == "SkipExtractor" and audit_disposition == "skip_stable":
        return "skipped"
    if route_target == "TableExtractor":
        return "table_route_not_executed"
    return "not_executed"


def _build_page_findings(
    artifacts: ProjectArtifacts,
    *,
    page_classifications: dict[str, PageClassification] | None = None,
    table_mappings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    text_counts = _per_sheet_counts(artifacts.texts)
    line_counts = _per_sheet_counts(artifacts.lines)
    block_counts = _per_sheet_counts(artifacts.blocks)
    polyline_counts = _per_sheet_counts(artifacts.polylines)
    line_group_counts = _per_sheet_counts(artifacts.line_groups)
    terminal_candidate_counts = _per_sheet_counts(artifacts.terminal_candidates)
    terminal_candidate_channel_counts = _per_sheet_candidate_channel_counts(artifacts.terminal_candidates)
    pair_kind_counts = _per_sheet_pair_kind_counts(artifacts.pairs)
    pair_candidate_counts = _per_sheet_counts(artifacts.pair_candidates)
    pair_counts = _per_sheet_counts(artifacts.pairs)
    issue_counts = _per_sheet_counts(artifacts.issues)
    orientation_counts = _per_sheet_orientation_counts(artifacts.line_groups)
    non_discard_pairs = _per_sheet_counts([pair for pair in artifacts.pairs if pair.status != "discard"])
    high_confidence_pairs = _per_sheet_counts([pair for pair in artifacts.pairs if _high_confidence_pair(pair)])
    table_mapping_rows: dict[str, int] = {}
    table_mapping_flags: dict[str, bool] = {}
    table_mapping_details: dict[str, dict[str, Any]] = {}
    executed_extractors = _extractor_execution_by_sheet(artifacts.extractor_runs)
    for item in table_mappings or []:
        sheet_id = str(item.get("sheet_id") or "")
        if not sheet_id:
            continue
        mappings = item.get("mappings", [])
        table_mapping_rows[sheet_id] = table_mapping_rows.get(sheet_id, 0) + len(mappings)
        table_mapping_flags[sheet_id] = bool(table_mapping_flags.get(sheet_id) or item.get("three_column"))
        detail = table_mapping_details.setdefault(
            sheet_id,
            {
                "mapping_modes": {},
                "header_prefixes": [],
                "logical_endpoint_examples": [],
                "row_number_sequence_valid": False,
            },
        )
        logical_examples = detail["logical_endpoint_examples"]
        header_prefixes = detail["header_prefixes"]
        mapping_mode_counts = detail["mapping_modes"]
        for mapping in mappings:
            mode = str(mapping.get("mapping_mode") or "unknown")
            mapping_mode_counts[mode] = mapping_mode_counts.get(mode, 0) + 1
            logical_endpoint = mapping.get("logical_endpoint")
            if logical_endpoint and logical_endpoint not in logical_examples and len(logical_examples) < 3:
                logical_examples.append(str(logical_endpoint))
            header_prefix = mapping.get("header_prefix")
            if header_prefix and header_prefix not in header_prefixes:
                header_prefixes.append(str(header_prefix))
            if mapping.get("row_number_sequence_valid"):
                detail["row_number_sequence_valid"] = True

    page_findings: list[dict[str, Any]] = []
    for page in artifacts.scan.pages:
        sheet_id = page.sheet_id
        polyline_count = polyline_counts.get(sheet_id, 0)
        line_group_count = line_group_counts.get(sheet_id, 0)
        classification = (page_classifications or {}).get(sheet_id)
        if classification is not None:
            page_type = classification.page_type
            page_subtype = classification.page_subtype
            page_type_confidence = classification.page_type_confidence
            route_target = classification.route_target
            table_like = classification.table_like
            grid_heavy = classification.grid_heavy
            classification_features = classification.features
        else:
            page_type = page.sheet_category or "unknown"
            page_subtype = None
            page_type_confidence = round(_page_type_confidence(page), 2)
            table_like = polyline_count >= 20 and line_group_count == 0
            grid_heavy = False
            classification_features = {}
            route_target = _page_route_target(page, table_like=table_like)
        audit_disposition = _page_audit_disposition(
            page,
            classification=classification,
            route_target=route_target,
        )
        orientation_summary = orientation_counts.get(sheet_id, {})
        dominant_orientation = _dominant_orientation(orientation_summary)
        non_discard_pair_count = non_discard_pairs.get(sheet_id, 0)
        high_confidence_pair_count = high_confidence_pairs.get(sheet_id, 0)
        pair_count = pair_counts.get(sheet_id, 0)
        issue_count = issue_counts.get(sheet_id, 0)
        table_mapping_count = table_mapping_rows.get(sheet_id, 0)
        table_detail = table_mapping_details.get(sheet_id, {})
        executed_extractor = executed_extractors.get(sheet_id)

        page_findings.append(
            {
                "sheet_id": page.sheet_id,
                "file_id": page.file_id,
                "filename": page.filename,
                "sheet_no": page.sheet_no,
                "sheet_order": page.sheet_order,
                "sheet_title": page.sheet_title,
                "page_type": page_type,
                "page_subtype": page_subtype,
                "page_type_confidence": page_type_confidence,
                "audit_role": page.audit_role,
                "audit_disposition": audit_disposition,
                "route_target": route_target,
                "executed_extractor": executed_extractor,
                "execution_status": _page_execution_status(
                    route_target=route_target,
                    audit_disposition=audit_disposition,
                    executed_extractor=executed_extractor,
                ),
                "grid_heavy": grid_heavy,
                "classification_features": classification_features,
                "layout_summary": {
                    "layout_name": page.layout_name,
                    "drawing_units": page.drawing_units,
                    "page_no_source": page.page_no_source,
                    "extent_bbox": list(page.extent_bbox) if page.extent_bbox else None,
                    "frame_bbox": list(page.frame_bbox) if page.frame_bbox else None,
                    "title_block_bbox": list(page.title_block_bbox) if page.title_block_bbox else None,
                    "audit_area_bbox": list(page.audit_area_bbox) if page.audit_area_bbox else None,
                },
                "structure_summary": {
                    "text_count": text_counts.get(sheet_id, 0),
                    "line_count": line_counts.get(sheet_id, 0),
                    "block_count": block_counts.get(sheet_id, 0),
                    "polyline_count": polyline_count,
                    "line_group_count": line_group_count,
                    "terminal_candidate_count": terminal_candidate_counts.get(sheet_id, 0),
                    "terminal_candidate_channel_counts": terminal_candidate_channel_counts.get(sheet_id, {}),
                    "pair_candidate_count": pair_candidate_counts.get(sheet_id, 0),
                    "pair_count": pair_count,
                    "pair_kind_counts": pair_kind_counts.get(sheet_id, {}),
                    "non_discard_pair_count": non_discard_pair_count,
                    "high_confidence_pair_count": high_confidence_pair_count,
                    "table_mapping_count": table_mapping_count,
                    "three_column_table": table_mapping_flags.get(sheet_id, False),
                    "table_mapping_modes": table_detail.get("mapping_modes", {}),
                    "table_header_prefixes": table_detail.get("header_prefixes", []),
                    "table_logical_endpoint_examples": table_detail.get("logical_endpoint_examples", []),
                    "table_row_number_sequence_valid": table_detail.get("row_number_sequence_valid", False),
                    "issue_count": issue_count,
                    "orientation_counts": orientation_summary,
                    "dominant_line_group_orientation": dominant_orientation,
                    "table_like_geometry": table_like,
                    "extractor_entry_executed": executed_extractor,
                },
                "recognition_strategy": _page_recognition_strategy(
                    page,
                    page_type=page_type,
                    page_subtype=page_subtype,
                    classification_features=classification_features,
                    audit_disposition=audit_disposition,
                    table_like=table_like,
                    grid_heavy=grid_heavy,
                    route_target=route_target,
                    table_mapping_count=table_mapping_count,
                ),
                "number_matching_strategy": _page_number_matching_strategy(
                    page,
                    dominant_orientation=dominant_orientation,
                    route_target=route_target,
                    table_mapping_count=table_mapping_count,
                ),
                "high_confidence_signals": _page_high_confidence_signals(
                    page=page,
                    audit_disposition=audit_disposition,
                    dominant_orientation=dominant_orientation,
                    non_discard_pair_count=non_discard_pair_count,
                    high_confidence_pair_count=high_confidence_pair_count,
                    line_group_count=line_group_count,
                    issue_count=issue_count,
                    table_mapping_count=table_mapping_count,
                ),
                "open_questions": _page_open_questions(
                    page=page,
                    audit_disposition=audit_disposition,
                    table_like=table_like,
                    route_target=route_target,
                    line_group_count=line_group_count,
                    pair_count=pair_count,
                    non_discard_pair_count=non_discard_pair_count,
                    high_confidence_pair_count=high_confidence_pair_count,
                    table_mapping_count=table_mapping_count,
                ),
                "warnings": list(page.warnings),
            }
        )
    return page_findings


def _build_table_extraction_summary(
    table_mappings: list[dict[str, Any]] | None,
    page_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    page_findings = page_findings or []
    routed_table_pages = [
        item
        for item in page_findings
        if item.get("route_target") == "TableExtractor"
    ]
    routed_table_sheet_ids = [str(item.get("sheet_id")) for item in routed_table_pages if item.get("sheet_id")]
    routed_table_filenames = [str(item.get("filename")) for item in routed_table_pages if item.get("filename")]
    table_like_non_routed = [
        {
            "sheet_id": item.get("sheet_id"),
            "filename": item.get("filename"),
            "page_type": item.get("page_type"),
            "route_target": item.get("route_target"),
        }
        for item in page_findings
        if bool((item.get("structure_summary") or {}).get("table_like_geometry"))
        and item.get("route_target") != "TableExtractor"
    ]

    if not table_mappings:
        if routed_table_pages:
            return {
                "status": "table_pages_routed_without_mappings",
                "status_reason": "Some pages were routed to TableExtractor, but no stable table mappings were recovered.",
                "table_pages": 0,
                "three_column_pages": 0,
                "total_mappings": 0,
                "classified_table_pages": len(routed_table_pages),
                "classified_table_sheet_ids": routed_table_sheet_ids,
                "classified_table_filenames": routed_table_filenames,
                "table_like_non_routed_pages": table_like_non_routed,
                "mappings": [],
            }
        return {
            "status": "no_table_pages_detected",
            "status_reason": "No page in this run was classified as a table page or routed to TableExtractor.",
            "table_pages": 0,
            "three_column_pages": 0,
            "total_mappings": 0,
            "classified_table_pages": 0,
            "classified_table_sheet_ids": [],
            "classified_table_filenames": [],
            "table_like_non_routed_pages": table_like_non_routed,
            "mappings": [],
        }
    mapped_sheet_ids = sorted({str(item.get("sheet_id")) for item in table_mappings if item.get("sheet_id")})
    mapped_filenames = sorted({str(item.get("filename")) for item in table_mappings if item.get("filename")})
    mapping_mode_counts: dict[str, int] = {}
    for item in table_mappings:
        for mapping in item.get("mappings", []):
            mode = str(mapping.get("mapping_mode") or "unknown")
            mapping_mode_counts[mode] = mapping_mode_counts.get(mode, 0) + 1
    three_column_pages = len({str(item.get("sheet_id")) for item in table_mappings if item.get("sheet_id") and item.get("three_column")})
    total_mappings = sum(len(item.get("mappings", [])) for item in table_mappings)
    return {
        "status": "table_mappings_recovered",
        "status_reason": f"Recovered {total_mappings} structured table mappings from {len(mapped_sheet_ids)} page(s).",
        "table_pages": len(mapped_sheet_ids),
        "three_column_pages": three_column_pages,
        "total_mappings": total_mappings,
        "mapping_modes": dict(sorted(mapping_mode_counts.items())),
        "mapped_sheet_ids": mapped_sheet_ids,
        "mapped_filenames": mapped_filenames,
        "classified_table_pages": len(routed_table_pages),
        "classified_table_sheet_ids": routed_table_sheet_ids,
        "classified_table_filenames": routed_table_filenames,
        "table_like_non_routed_pages": table_like_non_routed,
        "mappings": table_mappings,
    }


def _build_extractor_execution_summary(extractor_runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_extractor: dict[str, dict[str, Any]] = {}
    for run in extractor_runs:
        executed_extractor = str(run.get("executed_extractor") or "")
        if not executed_extractor:
            continue
        by_extractor[executed_extractor] = {
            "sheet_ids": list(run.get("sheet_ids", [])),
            "page_count": int(run.get("page_count", 0) or 0),
            "line_group_count": int(run.get("line_group_count", 0) or 0),
            "terminal_candidate_count": int(run.get("terminal_candidate_count", 0) or 0),
            "pair_candidate_count": int(run.get("pair_candidate_count", 0) or 0),
            "pair_count": int(run.get("pair_count", 0) or 0),
            "table_mapping_count": int(run.get("table_mapping_count", 0) or 0),
        }
    return {
        "executed_extractor_count": len(by_extractor),
        "executed_extractors": by_extractor,
    }


def _build_route_execution_summary(
    extractor_runs: list[dict[str, Any]],
    page_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical_routes = (
        "WireDiagramExtractor",
        "ComponentDiagramExtractor",
        "TerminalDiagramExtractor",
        "TableExtractor",
        "LayoutOnlyExtractor",
        "SkipExtractor",
    )
    route_runs: dict[str, dict[str, Any]] = {}
    for run in extractor_runs:
        route_target = str(run.get("route_target") or "")
        if route_target:
            route_runs[route_target] = run

    pages_by_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in page_findings:
        route_target = str(item.get("route_target") or "")
        if route_target:
            pages_by_route[route_target].append(item)

    route_targets: dict[str, dict[str, Any]] = {}
    all_routes = list(canonical_routes)
    all_routes.extend(
        sorted(route for route in pages_by_route if route not in route_targets and route not in canonical_routes)
    )

    for route_target in all_routes:
        routed_pages = pages_by_route.get(route_target, [])
        run = route_runs.get(route_target, {})
        routed_sheet_ids = [str(item.get("sheet_id")) for item in routed_pages if item.get("sheet_id")]
        routed_filenames = [str(item.get("filename")) for item in routed_pages if item.get("filename")]
        routed_dispositions = _count_labels(
            [item.get("audit_disposition") for item in routed_pages],
            missing_label="unknown",
        )
        executed_extractor = run.get("executed_extractor")
        if executed_extractor:
            status = "executed"
            status_reason = (
                f"Pages routed to `{route_target}` executed through `{executed_extractor}` "
                f"with {int(run.get('page_count', 0) or 0)} page(s)."
            )
        elif route_target == "TableExtractor":
            status = "no_pages_classified" if not routed_pages else "routed_without_execution"
            status_reason = (
                "No page in this run was classified as a table page or routed to TableExtractor."
                if not routed_pages
                else "Pages were routed to TableExtractor, but no execution record was captured."
            )
        elif route_target == "LayoutOnlyExtractor":
            status = "classify_only_pages_present" if routed_pages else "no_pages_classified"
            status_reason = (
                "Backplate/layout pages were classified and intentionally kept out of pairing audit."
                if routed_pages
                else "No page in this run was routed to LayoutOnlyExtractor."
            )
        elif route_target == "SkipExtractor":
            status = "skip_pages_present" if routed_pages else "no_pages_classified"
            status_reason = (
                "Stable non-audit pages were intentionally skipped after page classification."
                if routed_pages
                else "No page in this run was routed to SkipExtractor."
            )
        else:
            status = "no_pages_classified" if not routed_pages else "routed_without_execution"
            status_reason = (
                f"No page in this run was routed to `{route_target}`."
                if not routed_pages
                else f"Pages were routed to `{route_target}`, but no execution record was captured."
            )

        route_targets[route_target] = {
            "status": status,
            "status_reason": status_reason,
            "routed_page_count": len(routed_pages),
            "routed_sheet_ids": routed_sheet_ids,
            "routed_filenames": routed_filenames,
            "routed_audit_disposition_counts": routed_dispositions,
            "executed_extractor": executed_extractor,
            "executed_page_count": int(run.get("page_count", 0) or 0),
            "line_group_count": int(run.get("line_group_count", 0) or 0),
            "terminal_candidate_count": int(run.get("terminal_candidate_count", 0) or 0),
            "pair_candidate_count": int(run.get("pair_candidate_count", 0) or 0),
            "pair_count": int(run.get("pair_count", 0) or 0),
            "table_mapping_count": int(run.get("table_mapping_count", 0) or 0),
        }

    return {
        "route_target_count": len(route_targets),
        "route_targets": route_targets,
    }


def _build_findings_payload(
    artifacts: ProjectArtifacts,
    config: dict | None = None,
    *,
    page_classifications: dict[str, PageClassification] | None = None,
    table_mappings: list[dict[str, Any]] | None = None,
    entity_coverage_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = artifacts.scan.manifest
    primary_pages = [page for page in artifacts.scan.pages if page.audit_role == "primary"]
    supplemental_pages = [page for page in artifacts.scan.pages if page.audit_role == "supplemental"]
    secondary_pages = [page for page in artifacts.scan.pages if page.audit_role == "secondary"]
    skipped_pages = [page for page in artifacts.scan.pages if page.audit_role == "skip"]
    failed = [item for item in manifest.source_files if item.conversion_status.startswith("failed")]
    converted = [item for item in manifest.source_files if item.conversion_status in {"converted", "cached"}]
    page_findings = _build_page_findings(
        artifacts,
        page_classifications=page_classifications,
        table_mappings=table_mappings,
    )
    disposition_counts = _count_labels(
        [item.get("audit_disposition") for item in page_findings],
        missing_label="unknown",
    )
    included_audit_pages = sum(1 for item in page_findings if item.get("audit_disposition") == "audit_required")
    persisted_findings_artifacts = [
        "findings.md",
        "findings.json",
        "pages.parquet",
        "texts.parquet",
        "blocks.parquet",
        "lines.parquet",
        "polylines.parquet",
        "line_groups.parquet",
        "terminal_candidates.parquet",
        "pair_candidates.parquet",
        "pairs.parquet",
        "text_assignments.parquet",
        "entity_coverage_summary.parquet",
        "wire_junctions.parquet",
        "wire_networks.parquet",
        "extraction_warnings.parquet",
        "source_files.parquet",
        "sidecars.parquet",
        "terminal_strips.parquet",
    ]
    if bool((config or {}).get("runtime", {}).get("persist_page_findings_files", False)):
        persisted_findings_artifacts.insert(2, "page_findings/")
    return {
        "project_name": manifest.project_name,
        "project_id": manifest.project_id,
        "input_root": manifest.input_root,
        "file_count": manifest.file_count,
        "sheet_count": manifest.sheet_count,
        "valid_dwg_files": manifest.valid_dwg_files,
        "invalid_dwg_files": manifest.invalid_dwg_files,
        "primary_audit_pages": len(primary_pages),
        "supplemental_audit_pages": len(supplemental_pages),
        "included_audit_pages": included_audit_pages,
        "audit_page_counts": {
            "primary": len(primary_pages),
            "supplemental": len(supplemental_pages),
            "secondary": len(secondary_pages),
            "skip": len(skipped_pages),
        },
        "audit_disposition_counts": disposition_counts,
        "converted_pages": len(converted),
        "failed_pages": len(failed),
        "sidecars": [record_dict(sidecar) for sidecar in manifest.sidecars],
        "warnings": manifest.warnings,
        "stats": {
            "texts": len(artifacts.texts),
            "lines": len(artifacts.lines),
            "blocks": len(artifacts.blocks),
            "polylines": len(artifacts.polylines),
            "line_groups": len(artifacts.line_groups),
            "terminal_candidates": len(artifacts.terminal_candidates),
            "pair_candidates": len(artifacts.pair_candidates),
            "pairs": len(artifacts.pairs),
            "issues": len(artifacts.issues),
            "extraction_warnings": len(artifacts.extraction_warnings),
        },
        "pair_evidence_summary": _build_pair_findings_summary(artifacts.pairs),
        "entity_coverage_summary": entity_coverage_summary or {},
        "page_findings_count": len(page_findings),
        "page_findings": page_findings,
        "extractor_execution_summary": _build_extractor_execution_summary(artifacts.extractor_runs),
        "route_execution_summary": _build_route_execution_summary(artifacts.extractor_runs, page_findings),
        "table_extraction_summary": _build_table_extraction_summary(table_mappings, page_findings),
        "one_to_many_review_table": _build_one_to_many_review_table(artifacts.pairs, config=config),
        "failed_files": [
            {
                "filename": item.filename,
                "conversion_status": item.conversion_status,
                "conversion_detail": item.conversion_detail,
            }
            for item in failed
        ],
        "key_observations": [
            "当前流水线支持按文件级继续执行，坏页不会阻断整项目 findings 生成。",
            "ODA 转换使用 ASCII staging，以规避中文路径兼容问题。",
            "sheet_no 与 sheet_order 分离保存，避免重复页号覆盖。",
        ],
        "artifacts": {
            "findings": persisted_findings_artifacts,
            "audit": [
                "issues.parquet",
                "issues.json",
                "audit_report.md",
                "audit_report.html",
                "issues.xlsx",
                "topology_shadow_report.json",
                "topology_shadow_report.md",
            ],
        },
    }


def _build_page_finding_markdown(page_finding: dict[str, Any]) -> str:
    lines = [
        f"# Page Findings `{page_finding['sheet_id']}`",
        "",
        f"- Filename: `{_display_value(page_finding.get('filename'))}`",
        f"- SheetNo: `{_display_value(page_finding.get('sheet_no'))}`",
        f"- SheetOrder: `{_display_value(page_finding.get('sheet_order'))}`",
        f"- Title: `{_display_value(page_finding.get('sheet_title'))}`",
        f"- PageType: `{_display_value(page_finding.get('page_type'))}`",
        f"- PageTypeConfidence: `{_format_confidence(page_finding.get('page_type_confidence'))}`",
        f"- AuditRole: `{_display_value(page_finding.get('audit_role'))}`",
        f"- AuditDisposition: `{_display_value(page_finding.get('audit_disposition'))}`",
        f"- RouteTarget: `{_display_value(page_finding.get('route_target'))}`",
        "",
        "## Layout Summary",
        "",
    ]
    layout_summary = page_finding.get("layout_summary", {})
    for key in ("layout_name", "drawing_units", "page_no_source", "extent_bbox", "frame_bbox", "title_block_bbox", "audit_area_bbox"):
        lines.append(f"- {key}: `{_stringify_summary_value(layout_summary.get(key))}`")
    lines.extend(["", "## Structure Summary", ""])
    structure_summary = page_finding.get("structure_summary", {})
    for key in (
        "text_count",
        "line_count",
        "block_count",
        "polyline_count",
        "line_group_count",
        "terminal_candidate_count",
        "pair_candidate_count",
        "pair_count",
        "non_discard_pair_count",
        "high_confidence_pair_count",
        "issue_count",
        "dominant_line_group_orientation",
        "table_like_geometry",
    ):
        lines.append(f"- {key}: `{_stringify_summary_value(structure_summary.get(key))}`")
    lines.extend(
        [
            "",
            "## Recognition Strategy",
            "",
            page_finding.get("recognition_strategy", ""),
            "",
            "## Number Matching Strategy",
            "",
            page_finding.get("number_matching_strategy", ""),
            "",
            "## High Confidence Signals",
            "",
        ]
    )
    high_confidence_signals = page_finding.get("high_confidence_signals", [])
    if high_confidence_signals:
        lines.extend(f"- {signal}" for signal in high_confidence_signals)
    else:
        lines.append("- None recorded yet.")
    lines.extend(["", "## Open Questions", ""])
    open_questions = page_finding.get("open_questions", [])
    if open_questions:
        lines.extend(f"- {question}" for question in open_questions)
    else:
        lines.append("- No open questions recorded.")
    warnings = page_finding.get("warnings", [])
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def _build_findings_markdown(payload: dict[str, Any]) -> str:
    pair_summary = payload["pair_evidence_summary"]
    one_to_many_table = payload["one_to_many_review_table"]
    lines = [
        "# Findings",
        "",
        f"项目：{payload['project_name']}",
        f"输入目录：`{payload['input_root']}`",
        f"DWG 文件数：`{payload['file_count']}`",
        f"有效 DWG 头：`{payload['valid_dwg_files']}`",
        f"无效 DWG 头：`{payload['invalid_dwg_files']}`",
        f"主审计页数：`{payload['primary_audit_pages']}`",
        f"补充审计页数：`{payload['supplemental_audit_pages']}`",
        f"纳入审计总页数：`{payload['included_audit_pages']}`",
        f"成功转换页数：`{payload['converted_pages']}`",
        f"转换失败页数：`{payload['failed_pages']}`",
        "",
        "## Sidecars",
        "",
    ]
    for sidecar in payload["sidecars"]:
        lines.append(f"- `{sidecar['kind']}`: `{sidecar['status']}`")
    lines.extend(
        [
            "",
            "## 抽取统计",
            "",
            f"- AuditPageCounts: `{json.dumps(payload['audit_page_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- AuditDispositionCounts: `{json.dumps(payload['audit_disposition_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Texts: `{payload['stats']['texts']}`",
            f"- Lines: `{payload['stats']['lines']}`",
            f"- Blocks: `{payload['stats']['blocks']}`",
            f"- Polylines: `{payload['stats']['polylines']}`",
            f"- LineGroups: `{payload['stats']['line_groups']}`",
            f"- TerminalCandidates: `{payload['stats']['terminal_candidates']}`",
            f"- PairCandidates: `{payload['stats']['pair_candidates']}`",
            f"- Pairs: `{payload['stats']['pairs']}`",
            f"- Issues: `{payload['stats']['issues']}`",
            f"- ExtractionWarnings: `{payload['stats']['extraction_warnings']}`",
            "",
            "## Pair Evidence 摘要",
            "",
            f"- PairsWithEvidence: `{pair_summary['pairs_with_evidence']}/{pair_summary['total_pairs']}`",
            f"- PairKindCounts: `{json.dumps(pair_summary['pair_kind_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- StatusCounts: `{json.dumps(pair_summary['status_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- ConfidenceBuckets: `{json.dumps(pair_summary['confidence_bucket_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- ReviewPairs: `{pair_summary['review_pairs']}`",
            "",
            "## Coverage Contract",
            "",
            f"- TotalTexts: `{payload['entity_coverage_summary'].get('total_texts', 0)}`",
            f"- AuditScopeTexts: `{payload['entity_coverage_summary'].get('audit_scope_texts', 0)}`",
            f"- AssignedTexts: `{payload['entity_coverage_summary'].get('assigned_texts', 0)}`",
            f"- UnexplainedTexts: `{payload['entity_coverage_summary'].get('unexplained_texts', 0)}`",
            f"- UnexplainedNumericTexts: `{payload['entity_coverage_summary'].get('unexplained_numeric_texts', 0)}`",
            f"- UnassignedWireSegments: `{payload['entity_coverage_summary'].get('unassigned_wire_segments', 0)}`",
            f"- UnclassifiedBlocks: `{payload['entity_coverage_summary'].get('unclassified_blocks', 0)}`",
            f"- OutOfScopeTexts: `{payload['entity_coverage_summary'].get('out_of_scope_texts', 0)}`",
            f"- CoverageRatio: `{payload['entity_coverage_summary'].get('coverage_ratio', 0.0)}`",
            f"- AssignmentKindCounts: `{json.dumps(payload['entity_coverage_summary'].get('assignment_kind_counts', {}), ensure_ascii=False, sort_keys=True)}`",
            f"- ContractChecks: `{json.dumps(payload['entity_coverage_summary'].get('contract_checks', {}), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Table Extraction",
            "",
            f"- Status: `{payload['table_extraction_summary']['status']}`",
            f"- Reason: `{payload['table_extraction_summary']['status_reason']}`",
            f"- ClassifiedTablePages: `{payload['table_extraction_summary']['classified_table_pages']}`",
            f"- TablePagesWithMappings: `{payload['table_extraction_summary']['table_pages']}`",
            f"- ThreeColumnPages: `{payload['table_extraction_summary']['three_column_pages']}`",
            f"- TotalTableMappings: `{payload['table_extraction_summary']['total_mappings']}`",
            f"- ClassifiedTableFilenames: `{json.dumps(payload['table_extraction_summary']['classified_table_filenames'], ensure_ascii=False)}`",
            "",
            "## 待复核 Pair 概览",
            "",
        ]
    )
    if pair_summary["review_examples"]:
        for item in pair_summary["review_examples"]:
            semantics = item.get("line_semantics")
            semantics_text = f"; semantics={semantics}" if semantics else ""
            lines.append(
                f"- `{item['pair_id']}` {_format_pair_label(item['left_value'], item['right_value'])} "
                f"(status={item['status']}, bucket={_display_value(item['confidence_bucket'], default='unknown')}, "
                f"conf={_format_confidence(item['confidence'])}): {item['summary']}{semantics_text}; "
                f"rationale={_display_value(item['rationale'])}"
            )
    else:
        lines.append("- 当前没有待复核 pair。")
    lines.extend(["", "## 代表性 Pair 证据", ""])
    for item in pair_summary["examples"]:
        semantics = item.get("line_semantics")
        semantics_text = f"; semantics={semantics}" if semantics else ""
        lines.append(
            f"- `{item['pair_id']}` {_format_pair_label(item['left_value'], item['right_value'])} "
            f"(status={item['status']}, bucket={_display_value(item['confidence_bucket'], default='unknown')}, "
            f"conf={_format_confidence(item['confidence'])}): {item['summary']}{semantics_text}"
        )
    lines.extend(
        [
            "",
            "## 一对多簇复核表",
            "",
            f"- ClusterCount: `{one_to_many_table['cluster_count']}`",
            f"- BranchClusters: `{one_to_many_table['branch_cluster_count']}`",
            f"- ReviewClusters: `{one_to_many_table['review_cluster_count']}`",
            f"- ConflictClusters: `{one_to_many_table['conflict_cluster_count']}`",
            "",
        ]
    )
    if one_to_many_table["clusters"]:
        for cluster in one_to_many_table["clusters"][:5]:
            lines.append(
                f"- `{cluster['left_value']}` -> `{', '.join(cluster['right_values'])}` "
                f"(classification={cluster['classification']}, reason={cluster['classification_reason']}, "
                f"cross_page={cluster['cross_page']}, "
                f"sheets={json.dumps(cluster['sheet_nos'], ensure_ascii=False)}, "
                f"high_confidence_pairs={cluster['high_confidence_pair_count']}/{cluster['pair_count']}, "
                f"reciprocal_pairs={cluster['reciprocal_pair_count']}/{cluster['pair_count']})"
            )
    else:
        lines.append("- 当前没有发现完整 pair 形成的一对多簇。")
    lines.extend(["", "## 关键观察", ""])
    for item in payload["key_observations"]:
        lines.append(f"- {item}")
    if payload["failed_files"]:
        lines.extend(["", "## 转换失败页", ""])
        for item in payload["failed_files"]:
            lines.append(f"- `{item['filename']}`: {item['conversion_detail'] or item['conversion_status']}")
    return "\n".join(lines) + "\n"


def export_reports(
    project_dir: Path,
    artifacts: ProjectArtifacts,
    formats: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> None:
    frames = {
        "issues": _frame(artifacts.issues, Issue),
        "pairs": _frame(artifacts.pairs, Pair),
        "low_confidence_pairs": _frame(
            [pair for pair in artifacts.pairs if pair.status != "pass"],
            Pair,
        ),
        "files": _frame(artifacts.scan.manifest.source_files, SourceFileRecord),
    }
    _write_reports(project_dir / "audit", artifacts.scan.manifest.project_name, frames, formats=formats)


def _normalize_report_formats(formats: list[str] | tuple[str, ...] | set[str] | str | None) -> set[str]:
    if formats is None:
        return set(_REPORT_FORMATS)
    requested = formats.split(",") if isinstance(formats, str) else list(formats)
    normalized = {item.strip().lower().lstrip(".") for item in requested if item and item.strip()}
    unknown = normalized.difference(_REPORT_FORMATS)
    if unknown:
        raise ValueError(f"Unsupported report format(s): {', '.join(sorted(unknown))}")
    if not normalized:
        raise ValueError("At least one report format is required.")
    return normalized


def _decode_jsonish(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, float) and pd.isna(raw):
        return None
    if isinstance(raw, str) and not raw:
        return None
    if isinstance(raw, (list, tuple, dict)) and not raw:
        return None
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None
    return _normalize_jsonish_value(decoded)


def _backfill_issue_contract_fields(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    enriched = frame.copy()
    key_map = {
        "filename": "filename",
        "sheet_no": "sheet_no",
        "sheet_order": "sheet_order",
        "rationale": "rationale",
    }
    for column, key in key_map.items():
        if column not in enriched.columns:
            enriched[column] = None
        enriched[column] = enriched.apply(
            lambda row: row[column] if not _is_blank_value(row.get(column)) else _read_evidence_key(row, key),
            axis=1,
        )
    return enriched


def _normalize_jsonish_value(value: Any) -> Any:
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, bytearray)):
        value = value.tolist()
    if isinstance(value, dict):
        return {str(key): _normalize_jsonish_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_jsonish_value(item) for item in value]
    return value


def _read_evidence_key(row: pd.Series, key: str) -> Any:
    for column in ("evidence_refs", "evidence"):
        payload = _decode_jsonish(row.get(column))
        if isinstance(payload, dict) and key in payload:
            return payload.get(key)
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and key in item:
                    return item.get(key)
    return None


def _format_evidence_part(value: Any) -> str:
    value = _normalize_jsonish_value(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _format_evidence_mapping(payload: dict[str, Any]) -> str:
    preferred_keys = (
        "filename",
        "sheet_no",
        "sheet_order",
        "file_id",
        "sheet_id",
        "pair_id",
        "line_group_id",
        "left_value",
        "right_value",
        "line_start",
        "line_end",
        "confidence",
    )
    ordered_keys = [key for key in preferred_keys if key in payload]
    ordered_keys.extend(sorted(key for key in payload if key not in set(ordered_keys)))
    return ", ".join(f"{key}={_format_evidence_part(payload[key])}" for key in ordered_keys)


def _format_evidence_value(value: Any) -> str:
    payload = _decode_jsonish(value)
    if isinstance(payload, dict):
        return _format_evidence_mapping(payload)
    if isinstance(payload, list):
        parts = []
        for index, item in enumerate(payload, start=1):
            if isinstance(item, dict):
                parts.append(f"ref{index}: {_format_evidence_mapping(item)}")
            else:
                parts.append(f"ref{index}: {_format_evidence_part(item)}")
        return "; ".join(parts)
    return "" if payload is None else _format_evidence_part(payload)


def _format_terminal_header_table_display(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    classification = payload.get("one_to_many_classification")
    if classification == "terminal_header_table_multi_endpoint_review":
        return _format_terminal_header_table_compact_display(
            payload,
            classification,
            logical_key="aggregated_logical_endpoint_ranges",
            endpoint_label="terminal_endpoints",
            endpoint_key="aggregated_terminal_header_table_endpoint_ranges",
        )
    classification = payload.get("many_to_one_classification")
    if classification == "terminal_header_table_shared_endpoint_review":
        return _format_terminal_header_table_compact_display(
            payload,
            classification,
            logical_key="aggregated_logical_endpoint_ranges",
            endpoint_label="shared_endpoints",
            endpoint_key="aggregated_shared_endpoint_ranges",
        )
    return ""


def _format_terminal_header_table_compact_display(
    payload: dict[str, Any],
    classification: Any,
    *,
    logical_key: str,
    endpoint_label: str,
    endpoint_key: str,
) -> str:
    logical_ranges = _format_compact_evidence_list(
        payload.get(logical_key) or payload.get("aggregated_logical_endpoints")
    )
    endpoint_ranges = _format_compact_evidence_list(
        payload.get(endpoint_key)
        or payload.get("aggregated_terminal_header_table_endpoint_values")
        or payload.get("aggregated_shared_endpoints")
    )
    if not logical_ranges or not endpoint_ranges:
        return ""

    parts = [
        f"review={_format_evidence_part(classification)}",
        f"logical={logical_ranges}",
        f"{endpoint_label}={endpoint_ranges}",
    ]
    row_ranges = _format_compact_evidence_list(
        payload.get("aggregated_row_number_ranges") or payload.get("aggregated_row_numbers")
    )
    if row_ranges:
        parts.append(f"rows={row_ranges}")
    for key in ("header_prefix", "header_prefixes", "endpoint_columns"):
        value = _format_compact_evidence_list(payload.get(key))
        if value:
            parts.append(f"{key}={value}")
    cluster_size = payload.get("cluster_size")
    if cluster_size is not None:
        parts.append(f"cluster_size={_format_evidence_part(cluster_size)}")
    pair_ids = _decode_jsonish(payload.get("cluster_pair_ids"))
    if isinstance(pair_ids, list) and pair_ids:
        parts.append(f"pair_count={len(pair_ids)}")
    return ", ".join(parts)


def _format_compact_evidence_list(value: Any) -> str:
    payload = _decode_jsonish(value)
    if payload is None:
        return ""
    if isinstance(payload, list):
        return "|".join(_format_evidence_part(item) for item in payload)
    return _format_evidence_part(payload)


def _evidence_display(row: pd.Series) -> str:
    terminal_header_display = _format_terminal_header_table_display(
        _decode_jsonish(row.get("evidence"))
    )
    if terminal_header_display:
        return terminal_header_display
    refs = _format_evidence_value(row.get("evidence_refs"))
    if refs:
        return refs
    return _format_evidence_value(row.get("evidence"))


def _frame_value_counts(frame: pd.DataFrame, column: str, *, missing_label: str = "unknown") -> dict[str, int]:
    if frame.empty or column not in frame.columns:
        return {}
    return _count_labels(frame[column].tolist(), missing_label=missing_label)


def _row_requires_review(row: pd.Series) -> bool:
    status = row.get("status")
    bucket = row.get("confidence_bucket")
    return status in {"review", "fail"} or bucket == "review"


def _row_review_sort_key(row: pd.Series) -> tuple[int, int, float, str]:
    status_order = {"fail": 0, "review": 1, "discard": 2, "pass": 3}
    bucket_order = {"low": 0, "review": 1, "high": 2}
    confidence = row.get("confidence")
    confidence_value = float(confidence) if isinstance(confidence, (float, int)) and not pd.isna(confidence) else 1.0
    return (
        status_order.get(_display_value(row.get("status"), default=""), 99),
        bucket_order.get(_display_value(row.get("confidence_bucket"), default=""), 98),
        confidence_value,
        _display_value(row.get("pair_id"), default=""),
    )


def _review_pair_rows(frame: pd.DataFrame) -> list[pd.Series]:
    if frame.empty:
        return []
    rows = [row for _, row in frame.iterrows() if _row_requires_review(row)]
    return sorted(rows, key=_row_review_sort_key)


def _format_review_pair_row(row: pd.Series) -> str:
    evidence = row.get("evidence_display") or _evidence_display(row)
    semantics = _pair_semantics_summary(_decode_jsonish(row.get("evidence")))
    semantics_text = f", semantics={semantics}" if semantics else ""
    return (
        f"- `{_display_value(row.get('pair_id'))}` {_format_pair_label(row.get('left_value'), row.get('right_value'))} "
        f"(status={_display_value(row.get('status'))}, bucket={_display_value(row.get('confidence_bucket'), default='unknown')}, "
        f"conf={_format_confidence(row.get('confidence'))}): "
        f"file={_display_value(_read_evidence_key(row, 'filename'))}, "
        f"sheet_no={_display_value(_read_evidence_key(row, 'sheet_no'))}, "
        f"sheet_order={_display_value(_read_evidence_key(row, 'sheet_order'))}, "
        f"line_group={_display_value(row.get('line_group_id'))}, "
        f"evidence={_display_value(evidence)}{semantics_text}, "
        f"rationale={_display_value(row.get('rationale'))}"
    )


def _format_issue_markdown_block(row: pd.Series) -> list[str]:
    title = row.get("title")
    if _is_blank_value(title):
        title = row.get("message")
    evidence = row.get("evidence_display") or _evidence_display(row)
    semantics = _pair_semantics_summary(_decode_jsonish(row.get("evidence")))
    one_to_many_triage = row.get("one_to_many_classification")
    many_to_one_triage = row.get("many_to_one_classification")
    review_classification = row.get("review_classification")
    details = [
        f"### `{_display_value(row.get('issue_id'))}` {_display_value(title)}",
        "",
        f"- Rule / Severity: `{_display_value(row.get('rule_id'))}` / `{_display_value(row.get('severity'))}`",
        f"- Status / Confidence: `{_display_value(row.get('status'))}` / `{_format_confidence(row.get('confidence'))}`",
        f"- Pair / Line: `{_format_pair_label(row.get('left_value'), row.get('right_value'))}` / `line_group={_display_value(row.get('line_group_id'))}`",
        (
            f"- Location: file={_display_value(_read_evidence_key(row, 'filename'))}, "
            f"sheet_no={_display_value(_read_evidence_key(row, 'sheet_no'))}, "
            f"sheet_order={_display_value(_read_evidence_key(row, 'sheet_order'))}, "
            f"line_group={_display_value(row.get('line_group_id'))}, "
            f"line_start={_display_value(_read_evidence_key(row, 'line_start'))}, "
            f"line_end={_display_value(_read_evidence_key(row, 'line_end'))}"
        ),
        f"- Evidence: {_display_value(evidence)}",
    ]
    if semantics:
        details.append(f"- LineSemantics: `{semantics}`")
    if not _is_blank_value(review_classification):
        details.append(f"- ReviewClassification: `{review_classification}`")
    if not _is_blank_value(one_to_many_triage):
        details.append(f"- OneToManyTriage: `{one_to_many_triage}`")
    if not _is_blank_value(many_to_one_triage):
        details.append(f"- ManyToOneTriage: `{many_to_one_triage}`")
    root_cause = row.get("root_cause")
    if not _is_blank_value(root_cause):
        confidence = row.get("root_cause_confidence")
        rationale = row.get("root_cause_rationale")
        details.append(
            f"- RootCause: `{root_cause}`"
            f" (confidence={_format_confidence(confidence)}): {_display_value(rationale)}"
        )
    for label, key in (
        ("Summary", "summary"),
        ("Explanation", "explanation"),
        ("RecommendedAction", "recommended_action"),
    ):
        value = row.get(key)
        if not _is_blank_value(value):
            details.append(f"- {label}: {value}")
    details.append("")
    return details


def _prepare_report_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or ("evidence_refs" not in frame.columns and "evidence" not in frame.columns):
        return frame
    report_frame = frame.copy()
    report_frame["evidence_display"] = report_frame.apply(_evidence_display, axis=1)
    if "rule_id" in report_frame.columns:
        report_frame["one_to_many_classification"] = report_frame.apply(
            lambda row: _display_value(_read_evidence_key(row, "one_to_many_classification"), default=""),
            axis=1,
        )
        report_frame["many_to_one_classification"] = report_frame.apply(
            lambda row: _display_value(_read_evidence_key(row, "many_to_one_classification"), default=""),
            axis=1,
        )
        report_frame["review_classification"] = report_frame.apply(
            lambda row: _display_value(
                _read_evidence_key(row, "one_to_many_classification")
                or _read_evidence_key(row, "many_to_one_classification"),
                default="",
            ),
            axis=1,
        )
    return report_frame


def _write_reports(
    audit_dir: Path,
    project_name: str,
    frames: dict[str, pd.DataFrame],
    formats: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> None:
    selected_formats = _normalize_report_formats(formats)
    audit_dir.mkdir(parents=True, exist_ok=True)
    report_frames = {name: _prepare_report_frame(frame) for name, frame in frames.items()}

    if "md" in selected_formats:
        issues = report_frames["issues"]
        pairs = report_frames["pairs"]
        review_pairs = _review_pair_rows(pairs)
        markdown_lines = [
            "# Audit Report",
            "",
            f"项目：{project_name}",
            "",
            "## 审计概览",
            "",
            f"- IssueCount: `{len(issues)}`",
            f"- SeverityCounts: `{json.dumps(_frame_value_counts(issues, 'severity'), ensure_ascii=False, sort_keys=True)}`",
            f"- RuleCounts: `{json.dumps(_frame_value_counts(issues, 'rule_id'), ensure_ascii=False, sort_keys=True)}`",
            f"- PairStatusCounts: `{json.dumps(_frame_value_counts(pairs, 'status'), ensure_ascii=False, sort_keys=True)}`",
            f"- PairConfidenceBuckets: `{json.dumps(_frame_value_counts(pairs, 'confidence_bucket'), ensure_ascii=False, sort_keys=True)}`",
            f"- ReviewPairs: `{len(review_pairs)}`",
            "",
            "## 待复核 Pair",
            "",
            "## 异常清单",
            "",
        ]
        if review_pairs:
            markdown_lines.pop()
            markdown_lines.pop()
            for row in review_pairs[:5]:
                markdown_lines.append(_format_review_pair_row(row))
            markdown_lines.extend(["", "## 异常清单", ""])
        else:
            markdown_lines.pop()
            markdown_lines.pop()
            markdown_lines.append("- 当前没有待复核 pair。")
            markdown_lines.extend(["", "## 异常清单", ""])
        if issues.empty:
            markdown_lines.append("未发现异常。")
        else:
            for _, row in issues.iterrows():
                markdown_lines.extend(_format_issue_markdown_block(row))
        (audit_dir / "audit_report.md").write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    if "html" in selected_formats:
        html = ["<html><head><meta charset='utf-8'><title>Audit Report</title></head><body>"]
        html.append(f"<h1>{project_name}</h1>")
        for name, frame in report_frames.items():
            html.append(f"<h2>{name}</h2>")
            html.append(frame.to_html(index=False, escape=False))
        html.append("</body></html>")
        (audit_dir / "audit_report.html").write_text("".join(html), encoding="utf-8")

    if "xlsx" in selected_formats:
        with pd.ExcelWriter(audit_dir / "issues.xlsx", engine="openpyxl") as writer:
            for sheet_name, frame in report_frames.items():
                frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def load_report_frames(project_dir: Path) -> dict[str, pd.DataFrame]:
    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"
    frames = {}
    for name in (
        "pages",
        "texts",
        "lines",
        "blocks",
        "polylines",
        "line_groups",
        "terminal_candidates",
        "pair_candidates",
        "pairs",
        "text_assignments",
        "entity_coverage_summary",
        "wire_junctions",
        "wire_networks",
        "source_files",
        "sidecars",
        "terminal_strips",
        "extraction_warnings",
    ):
        path = findings_dir / f"{name}.parquet"
        frames[name] = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    issue_path = audit_dir / "issues.parquet"
    frames["issues"] = pd.read_parquet(issue_path) if issue_path.exists() else pd.DataFrame()
    return frames


def export_existing_reports(
    project_dir: Path,
    formats: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> None:
    manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
    frames = load_report_frames(project_dir)
    files = frames.get("source_files", pd.DataFrame())
    pairs = frames.get("pairs", pd.DataFrame())
    low_conf = pairs[pairs["status"] != "pass"] if not pairs.empty and "status" in pairs.columns else pd.DataFrame()
    _write_reports(
        project_dir / "audit",
        manifest["project_name"],
        {
            "issues": frames.get("issues", pd.DataFrame()),
            "pairs": pairs,
            "low_confidence_pairs": low_conf,
            "files": files,
        },
        formats=formats,
    )
