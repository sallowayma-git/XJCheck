from __future__ import annotations

from collections import Counter
from collections import defaultdict
from typing import Any

import pandas as pd

from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TextItem


_PAIR_ENDPOINT_KINDS = {"ordinary_pair"}
_STRUCTURED_MAPPING_KINDS = {
    "wire_component_mapping",
    "component_mapping",
    "table_mapping",
    "bridge_mapping",
}
_SEMANTIC_MAPPING_KINDS = {"semantic_mapping"}
_CONTINUATION_KINDS = {"continuation"}
_COVERED_PAIR_KINDS = (
    _PAIR_ENDPOINT_KINDS
    | _STRUCTURED_MAPPING_KINDS
    | _SEMANTIC_MAPPING_KINDS
    | _CONTINUATION_KINDS
)

_ASSIGNED_KINDS = {
    "pair_endpoint",
    "structured_mapping_endpoint",
    "semantic_evidence",
    "continuation_evidence",
    "covered_discard",
    "rejected_candidate",
}

_OUT_OF_SCOPE_DISPOSITIONS = {"skip_stable", "classify_only"}
_CONDUCTIVE_WIRE_ROUTES = {"WireDiagramExtractor", "ComponentDiagramExtractor"}
_NON_CONTRACT_SCOPE_REASONS = {
    "title_block_bbox",
    "frame_bbox",
    "outside_audit_area",
}
_ALLOWED_OUT_OF_SCOPE_REASONS = _NON_CONTRACT_SCOPE_REASONS | {
    "page_disposition:skip_stable",
    "page_disposition:classify_only",
}

_TEXT_ASSIGNMENT_COLUMNS = [
    "entity_type",
    "sheet_id",
    "file_id",
    "text_id",
    "filename",
    "sheet_no",
    "sheet_order",
    "page_type",
    "page_subtype",
    "route_target",
    "audit_disposition",
    "audit_role",
    "text",
    "normalized_text",
    "is_numeric_like",
    "channel",
    "layer",
    "source_block_name",
    "color_index",
    "true_color",
    "insert_x",
    "insert_y",
    "bbox_min_x",
    "bbox_min_y",
    "bbox_max_x",
    "bbox_max_y",
    "in_audit_area",
    "counts_toward_contract",
    "assignment_kind",
    "consumed_by_pair_ids",
    "consumed_by_kinds",
    "consumed_by_candidate_ids",
    "consumed_by_line_group_ids",
    "consumed_by_mapping_modes",
    "explain_reason",
    "assignment_source",
    "paired_side",
    "paired_value",
    "pair_status",
    "pair_confidence_bucket",
    "candidate_channel",
    "candidate_status",
    "rejection_reason",
]

_SUMMARY_COLUMNS = [
    "summary_scope",
    "sheet_id",
    "filename",
    "sheet_no",
    "sheet_order",
    "page_type",
    "route_target",
    "assignment_kind",
    "count",
    "audit_scope_texts",
    "assigned_texts",
    "unexplained_texts",
    "unexplained_numeric_texts",
    "line_segments",
    "unassigned_wire_segments",
    "blocks",
    "unclassified_blocks",
    "out_of_scope_texts",
    "coverage_ratio",
    "identity_ok",
    "unexplained_text_ids",
    "unexplained_numeric_text_ids",
]


def _sheet_contexts(
    pages: list[SheetRecord],
    page_classifications: dict[str, PageClassification] | None,
) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    classifications = page_classifications or {}
    for page in pages:
        classification = classifications.get(page.sheet_id)
        page_type = classification.page_type if classification is not None else page.page_type or page.sheet_category
        page_subtype = classification.page_subtype if classification is not None else page.page_subtype
        route_target = classification.route_target if classification is not None else page.route_target
        audit_disposition = (
            classification.audit_disposition
            if classification is not None and classification.audit_disposition
            else page.audit_disposition
        ) or ("audit_required" if page.audit_role != "skip" else "skip_stable")
        contexts[page.sheet_id] = {
            "filename": page.filename,
            "sheet_no": page.sheet_no,
            "sheet_order": page.sheet_order,
            "page_type": page_type,
            "page_subtype": page_subtype,
            "route_target": route_target,
            "audit_disposition": audit_disposition,
            "audit_role": page.audit_role,
            "audit_area_bbox": page.audit_area_bbox,
            "title_block_bbox": page.title_block_bbox,
            "frame_bbox": page.frame_bbox,
        }
    return contexts


def _point_in_bbox(x: float, y: float, bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return False
    min_x, min_y, max_x, max_y = bbox
    return min_x <= x <= max_x and min_y <= y <= max_y


def _candidate_lookup(candidates: list[TerminalCandidate]) -> dict[str, list[TerminalCandidate]]:
    by_text_id: dict[str, list[TerminalCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.text_id:
            by_text_id[candidate.text_id].append(candidate)
    return by_text_id


def _pair_assignment_kind(pair_kind: str, status: str | None) -> str:
    if status == "discard":
        return "covered_discard"
    if pair_kind in _PAIR_ENDPOINT_KINDS:
        return "pair_endpoint"
    if pair_kind in _STRUCTURED_MAPPING_KINDS:
        return "structured_mapping_endpoint"
    if pair_kind in _SEMANTIC_MAPPING_KINDS:
        return "semantic_evidence"
    if pair_kind in _CONTINUATION_KINDS:
        return "continuation_evidence"
    return "pair_endpoint"


def _pair_assignments(pairs: list[Any]) -> dict[str, list[dict[str, Any]]]:
    assignments: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        pair_kind = getattr(pair, "pair_kind", None) or "ordinary_pair"
        if pair_kind not in _COVERED_PAIR_KINDS:
            continue
        status = getattr(pair, "status", None)
        evidence = getattr(pair, "evidence", {}) or {}
        assignment_kind = _pair_assignment_kind(pair_kind, status)
        for side in ("left", "right"):
            text_id = getattr(pair, f"{side}_text_id", None)
            if not text_id:
                continue
            assignments[text_id].append(
                {
                    "assignment_kind": assignment_kind,
                    "explain_reason": f"covered_by_{pair_kind}",
                    "assignment_source": "pair",
                    "pair_id": pair.pair_id,
                    "candidate_id": getattr(pair, f"{side}_candidate_id", None),
                    "line_group_id": pair.line_group_id,
                    "mapping_mode": evidence.get("mapping_mode"),
                    "pair_kind": pair_kind,
                    "paired_side": side,
                    "paired_value": getattr(pair, f"{side}_value", None),
                    "pair_status": status,
                    "pair_confidence_bucket": getattr(pair, "confidence_bucket", None),
                }
            )
    return assignments


def _table_structure_assignments(
    table_mappings: list[dict[str, Any]] | None,
) -> dict[str, list[dict[str, Any]]]:
    assignments: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for table in table_mappings or []:
        is_matrix = bool(table.get("matrix_table") and table.get("mappings"))
        is_component_backplate = bool(table.get("component_backplate"))
        if not (is_matrix or is_component_backplate):
            continue
        sheet_id = str(table.get("sheet_id") or "")
        mapping_mode = (
            "output_contact_matrix"
            if is_matrix
            else "accessory_backplate_two_port"
        )
        for text_id in table.get("structural_text_ids", []) or []:
            if not text_id:
                continue
            assignments[str(text_id)].append(
                {
                    "assignment_kind": "semantic_evidence",
                    "explain_reason": "covered_by_output_contact_matrix_structure",
                    "assignment_source": "table_mapping_structure",
                    "mapping_id": f"{sheet_id}:{mapping_mode}",
                    "mapping_mode": mapping_mode,
                    "pair_kind": "table_mapping_structure",
                }
            )
    return assignments


def _best_pair_assignment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    priority = {
        "pair_endpoint": 0,
        "structured_mapping_endpoint": 1,
        "semantic_evidence": 2,
        "continuation_evidence": 3,
        "covered_discard": 4,
    }
    return sorted(rows, key=lambda item: (priority[item["assignment_kind"]], item["pair_id"]))[0]


def _candidate_assignment(candidate: TerminalCandidate) -> dict[str, Any]:
    channel = candidate.channel
    if channel == "semantic_channel":
        assignment_kind = "semantic_evidence"
    elif channel == "continuation_channel":
        assignment_kind = "continuation_evidence"
    else:
        assignment_kind = "rejected_candidate"
    detail = candidate.channel_detail or candidate.rejection_reason or candidate.status or assignment_kind
    return {
        "assignment_kind": assignment_kind,
        "explain_reason": detail,
        "assignment_source": "candidate",
        "consumed_by_candidate_id": candidate.candidate_id,
        "consumed_by_line_group_id": candidate.line_group_id,
        "candidate_channel": channel,
        "candidate_status": candidate.status,
        "rejection_reason": candidate.rejection_reason,
        "paired_side": candidate.side,
        "paired_value": candidate.value,
    }


def _best_candidate(candidates: list[TerminalCandidate]) -> TerminalCandidate:
    priority = {
        "semantic_channel": 0,
        "continuation_channel": 1,
        "noise_channel": 3,
        "terminal_numeric_channel": 4,
    }
    return sorted(
        candidates,
        key=lambda item: (
            priority.get(item.channel or "", 2),
            0 if item.status == "rejected" else 1,
            -(item.score or 0.0),
            item.candidate_id,
        ),
    )[0]


def _out_of_scope_reason(text: TextItem, context: dict[str, Any]) -> str | None:
    disposition = context.get("audit_disposition")
    if disposition in _OUT_OF_SCOPE_DISPOSITIONS:
        return f"page_disposition:{disposition}"
    if _point_in_bbox(text.insert_x, text.insert_y, context.get("title_block_bbox")):
        return "title_block_bbox"
    if _point_in_bbox(text.insert_x, text.insert_y, context.get("frame_bbox")):
        return "frame_bbox"
    if context.get("audit_area_bbox") is not None and not _point_in_bbox(
        text.insert_x,
        text.insert_y,
        context.get("audit_area_bbox"),
    ):
        return "outside_audit_area"
    return None


def _json_list(values: list[Any]) -> list[Any]:
    return [value for value in values if value not in (None, "")]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def build_text_assignment_frame(
    artifacts: ProjectArtifacts,
    *,
    page_classifications: dict[str, PageClassification] | None = None,
    table_mappings: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    contexts = _sheet_contexts(artifacts.scan.pages, page_classifications)
    candidates_by_text_id = _candidate_lookup(artifacts.terminal_candidates)
    assignments_by_text_id = _pair_assignments(artifacts.pairs)
    table_assignments_by_text_id = _table_structure_assignments(table_mappings)

    rows: list[dict[str, Any]] = []
    for text in artifacts.texts:
        context = contexts.get(text.sheet_id, {})
        out_reason = _out_of_scope_reason(text, context)
        in_audit_area = out_reason not in {"outside_audit_area", "title_block_bbox", "frame_bbox"}
        row = {
            "entity_type": "text",
            "sheet_id": text.sheet_id,
            "file_id": text.file_id,
            "text_id": text.text_id,
            "filename": context.get("filename"),
            "sheet_no": context.get("sheet_no"),
            "sheet_order": context.get("sheet_order"),
            "page_type": context.get("page_type"),
            "page_subtype": context.get("page_subtype"),
            "route_target": context.get("route_target"),
            "audit_disposition": context.get("audit_disposition"),
            "audit_role": context.get("audit_role"),
            "text": text.text,
            "normalized_text": text.normalized_text,
            "is_numeric_like": bool(text.is_numeric_candidate),
            "channel": None,
            "layer": text.layer,
            "source_block_name": text.source_block_name,
            "color_index": text.color_index,
            "true_color": text.true_color,
            "insert_x": text.insert_x,
            "insert_y": text.insert_y,
            "bbox_min_x": text.bbox_min_x,
            "bbox_min_y": text.bbox_min_y,
            "bbox_max_x": text.bbox_max_x,
            "bbox_max_y": text.bbox_max_y,
            "in_audit_area": in_audit_area,
            "counts_toward_contract": True,
            "assignment_kind": "unexplained",
            "consumed_by_pair_ids": [],
            "consumed_by_kinds": [],
            "consumed_by_candidate_ids": [],
            "consumed_by_line_group_ids": [],
            "consumed_by_mapping_modes": [],
            "explain_reason": "unexplained_text",
            "assignment_source": "coverage_contract",
            "paired_side": None,
            "paired_value": None,
            "pair_status": None,
            "pair_confidence_bucket": None,
            "candidate_channel": None,
            "candidate_status": None,
            "rejection_reason": None,
        }

        pair_rows = assignments_by_text_id.get(text.text_id, [])
        if pair_rows:
            chosen = _best_pair_assignment(pair_rows)
            row.update(
                {
                    "assignment_kind": chosen["assignment_kind"],
                    "explain_reason": chosen["explain_reason"],
                    "assignment_source": chosen["assignment_source"],
                    "consumed_by_pair_ids": _json_list([item["pair_id"] for item in pair_rows]),
                    "consumed_by_kinds": _json_list([item["pair_kind"] for item in pair_rows]),
                    "consumed_by_candidate_ids": _json_list([item["candidate_id"] for item in pair_rows]),
                    "consumed_by_line_group_ids": _json_list([item["line_group_id"] for item in pair_rows]),
                    "consumed_by_mapping_modes": _json_list([item["mapping_mode"] for item in pair_rows]),
                    "paired_side": chosen["paired_side"],
                    "paired_value": chosen["paired_value"],
                    "pair_status": chosen["pair_status"],
                    "pair_confidence_bucket": chosen["pair_confidence_bucket"],
                }
            )
        else:
            table_rows = table_assignments_by_text_id.get(text.text_id, [])
            if table_rows:
                row.update(
                    {
                        "assignment_kind": "semantic_evidence",
                        "explain_reason": table_rows[0]["explain_reason"],
                        "assignment_source": table_rows[0]["assignment_source"],
                        "consumed_by_kinds": _json_list([item["pair_kind"] for item in table_rows]),
                        "consumed_by_mapping_modes": _json_list([item["mapping_mode"] for item in table_rows]),
                    }
                )
            else:
                candidates = candidates_by_text_id.get(text.text_id, [])
                if candidates:
                    chosen_candidate = _best_candidate(candidates)
                    candidate_row = _candidate_assignment(chosen_candidate)
                    row.update(candidate_row)
                    row.update(
                        {
                            "channel": chosen_candidate.channel,
                            "consumed_by_candidate_ids": _json_list([item.candidate_id for item in candidates]),
                            "consumed_by_line_group_ids": _json_list([item.line_group_id for item in candidates]),
                        }
                    )
                elif out_reason is not None:
                    row.update(
                        {
                            "assignment_kind": "out_of_scope",
                            "explain_reason": out_reason,
                            "assignment_source": "page_scope",
                            "counts_toward_contract": False,
                        }
                    )

        rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=_TEXT_ASSIGNMENT_COLUMNS)
    return frame.sort_values(["sheet_order", "text_id"], kind="stable").reset_index(drop=True)


def _line_group_member_ids(artifacts: ProjectArtifacts) -> set[str]:
    member_ids: set[str] = set()
    for group in artifacts.line_groups:
        for attr in ("member_line_ids", "line_ids", "source_line_ids"):
            value = getattr(group, attr, None)
            if isinstance(value, (list, tuple, set)):
                member_ids.update(str(item) for item in value)
        line_id = getattr(group, "line_id", None)
        if line_id:
            member_ids.add(str(line_id))
    return member_ids


def _line_entity_id(line: Any) -> str | None:
    for attr in ("line_id", "entity_id", "handle"):
        value = getattr(line, attr, None)
        if value:
            return str(value)
    return None


def _line_in_audit_scope(line: Any, context: dict[str, Any]) -> bool:
    if context.get("audit_disposition") in _OUT_OF_SCOPE_DISPOSITIONS:
        return False
    audit_bbox = context.get("audit_area_bbox")
    if audit_bbox is None:
        return True
    start_inside = _point_in_bbox(getattr(line, "start_x", 0.0), getattr(line, "start_y", 0.0), audit_bbox)
    end_inside = _point_in_bbox(getattr(line, "end_x", 0.0), getattr(line, "end_y", 0.0), audit_bbox)
    return start_inside or end_inside


def _line_in_conductive_wire_scope(
    line: Any,
    context: dict[str, Any],
    *,
    is_line_group_member: bool,
) -> bool:
    """Return whether a segment belongs in conductive-wire coverage.

    A CAD LINE is not automatically an electrical wire. Table grids, title
    frames, polylines used as device outlines, and expanded block artwork are
    drawing geometry. Existing line-group membership is positive electrical
    evidence; otherwise only top-level LINE entities on wire/component routes
    enter this coverage contract.
    """

    if not _line_in_audit_scope(line, context):
        return False
    if is_line_group_member:
        return True
    if context.get("route_target") not in _CONDUCTIVE_WIRE_ROUTES:
        return False
    if str(getattr(line, "source_entity_type", "") or "").upper() != "LINE":
        return False
    if getattr(line, "source_block_name", None):
        return False
    return True


def _block_in_audit_scope(block: Any, context: dict[str, Any]) -> bool:
    if context.get("audit_disposition") in _OUT_OF_SCOPE_DISPOSITIONS:
        return False
    audit_bbox = context.get("audit_area_bbox")
    if audit_bbox is None:
        return True
    return _point_in_bbox(getattr(block, "insert_x", 0.0), getattr(block, "insert_y", 0.0), audit_bbox)


def _wire_segment_coverage_by_page(
    artifacts: ProjectArtifacts,
    contexts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, int]]:
    member_ids = _line_group_member_ids(artifacts)
    by_page: dict[str, dict[str, int]] = defaultdict(lambda: {"line_segments": 0, "unassigned_wire_segments": 0})
    for line in artifacts.lines:
        context = contexts.get(getattr(line, "sheet_id", ""), {})
        line_id = _line_entity_id(line)
        is_member = line_id is not None and line_id in member_ids
        if not _line_in_conductive_wire_scope(line, context, is_line_group_member=is_member):
            continue
        sheet_id = getattr(line, "sheet_id", "")
        by_page[sheet_id]["line_segments"] += 1
        if is_member:
            continue
        by_page[sheet_id]["unassigned_wire_segments"] += 1
    return dict(by_page)


def _block_coverage_by_page(
    artifacts: ProjectArtifacts,
    contexts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, int]]:
    by_page: dict[str, dict[str, int]] = defaultdict(lambda: {"blocks": 0, "unclassified_blocks": 0})
    for block in artifacts.blocks:
        context = contexts.get(getattr(block, "sheet_id", ""), {})
        if not _block_in_audit_scope(block, context):
            continue
        sheet_id = getattr(block, "sheet_id", "")
        by_page[sheet_id]["blocks"] += 1
        classified = False
        for attr in ("symbol_family", "component_submode", "matched_submode", "classification"):
            value = getattr(block, attr, None)
            if value:
                classified = True
                break
        if not classified:
            by_page[sheet_id]["unclassified_blocks"] += 1
    return dict(by_page)


def _page_summary_rows(
    text_assignments: pd.DataFrame,
    *,
    wire_coverage_by_page: dict[str, dict[str, int]] | None = None,
    block_coverage_by_page: dict[str, dict[str, int]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    wire_coverage_by_page = wire_coverage_by_page or {}
    block_coverage_by_page = block_coverage_by_page or {}
    for sheet_id, group in text_assignments.groupby("sheet_id", sort=False):
        contract_mask = group["counts_toward_contract"].astype(bool)
        assigned_mask = group["assignment_kind"].isin(_ASSIGNED_KINDS)
        unexplained_mask = group["assignment_kind"] == "unexplained"
        out_of_scope_mask = group["assignment_kind"] == "out_of_scope"
        audit_scope_texts = int(contract_mask.sum())
        assigned_texts = int((assigned_mask & contract_mask).sum())
        unexplained_texts = int((unexplained_mask & contract_mask).sum())
        unexplained_numeric_texts = int(
            (unexplained_mask & contract_mask & group["is_numeric_like"].astype(bool)).sum()
        )
        wire_metrics = wire_coverage_by_page.get(sheet_id, {})
        block_metrics = block_coverage_by_page.get(sheet_id, {})
        rows.append(
            {
                "summary_scope": "page",
                "sheet_id": sheet_id,
                "filename": group["filename"].iloc[0],
                "sheet_no": group["sheet_no"].iloc[0],
                "sheet_order": group["sheet_order"].iloc[0],
                "page_type": group["page_type"].iloc[0],
                "route_target": group["route_target"].iloc[0],
                "assignment_kind": None,
                "count": int(len(group)),
                "audit_scope_texts": audit_scope_texts,
                "assigned_texts": assigned_texts,
                "unexplained_texts": unexplained_texts,
                "unexplained_numeric_texts": unexplained_numeric_texts,
                "line_segments": int(wire_metrics.get("line_segments", 0)),
                "unassigned_wire_segments": int(wire_metrics.get("unassigned_wire_segments", 0)),
                "blocks": int(block_metrics.get("blocks", 0)),
                "unclassified_blocks": int(block_metrics.get("unclassified_blocks", 0)),
                "out_of_scope_texts": int(out_of_scope_mask.sum()),
                "coverage_ratio": round(assigned_texts / audit_scope_texts, 4) if audit_scope_texts else 0.0,
                "identity_ok": assigned_texts + unexplained_texts == audit_scope_texts,
                "unexplained_text_ids": group.loc[
                    unexplained_mask & contract_mask,
                    "text_id",
                ].tolist(),
                "unexplained_numeric_text_ids": group.loc[
                    unexplained_mask & contract_mask & group["is_numeric_like"].astype(bool),
                    "text_id",
                ].tolist(),
            }
        )
    return rows


def build_entity_coverage_summary(
    text_assignments: pd.DataFrame,
    *,
    artifacts: ProjectArtifacts | None = None,
    page_classifications: dict[str, PageClassification] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if text_assignments.empty:
        empty_summary = {
            "total_texts": 0,
            "audit_scope_texts": 0,
            "assigned_texts": 0,
            "unexplained_texts": 0,
            "unexplained_numeric_texts": 0,
            "unassigned_wire_segments": 0,
            "unclassified_blocks": 0,
            "out_of_scope_texts": 0,
            "coverage_ratio": 0.0,
            "identity_ok": True,
            "suspicious_out_of_scope_expansion": False,
            "out_of_scope_reason_counts": {},
            "assignment_kind_counts": {},
            "page_summaries": [],
            "route_summaries": [],
            "page_type_summaries": [],
            "contract_checks": {
                "identity_ok": True,
                "single_assignment_per_text": True,
                "suspicious_out_of_scope_expansion": False,
                "unassigned_defaults_to_unexplained": True,
            },
        }
        return pd.DataFrame(columns=_SUMMARY_COLUMNS), empty_summary

    contract_mask = text_assignments["counts_toward_contract"].astype(bool)
    assigned_mask = text_assignments["assignment_kind"].isin(_ASSIGNED_KINDS)
    unexplained_mask = text_assignments["assignment_kind"] == "unexplained"
    out_of_scope_mask = text_assignments["assignment_kind"] == "out_of_scope"

    total_texts = int(len(text_assignments))
    audit_scope_texts = int(contract_mask.sum())
    assigned_texts = int((assigned_mask & contract_mask).sum())
    unexplained_texts = int((unexplained_mask & contract_mask).sum())
    unexplained_numeric_texts = int(
        (unexplained_mask & contract_mask & text_assignments["is_numeric_like"].astype(bool)).sum()
    )
    out_of_scope_texts = int(out_of_scope_mask.sum())
    identity_ok = assigned_texts + unexplained_texts == audit_scope_texts
    out_of_scope_reason_counts = dict(
        sorted(Counter(text_assignments.loc[out_of_scope_mask, "explain_reason"]).items())
    )
    suspicious_out_of_scope_expansion = any(
        reason not in _ALLOWED_OUT_OF_SCOPE_REASONS for reason in out_of_scope_reason_counts
    )

    contexts = _sheet_contexts(artifacts.scan.pages, page_classifications) if artifacts is not None else {}
    wire_coverage_by_page = _wire_segment_coverage_by_page(artifacts, contexts) if artifacts is not None else {}
    block_coverage_by_page = _block_coverage_by_page(artifacts, contexts) if artifacts is not None else {}
    unassigned_wire_segments = sum(
        item.get("unassigned_wire_segments", 0) for item in wire_coverage_by_page.values()
    )
    unclassified_blocks = sum(item.get("unclassified_blocks", 0) for item in block_coverage_by_page.values())

    page_rows = _page_summary_rows(
        text_assignments,
        wire_coverage_by_page=wire_coverage_by_page,
        block_coverage_by_page=block_coverage_by_page,
    )
    assignment_rows = [
        {
            "summary_scope": "assignment_kind",
            "sheet_id": None,
            "filename": None,
            "sheet_no": None,
            "sheet_order": None,
            "page_type": None,
            "route_target": None,
            "assignment_kind": kind,
            "count": int(count),
            "audit_scope_texts": None,
            "assigned_texts": None,
            "unexplained_texts": None,
            "unexplained_numeric_texts": None,
            "line_segments": None,
            "unassigned_wire_segments": None,
            "blocks": None,
            "unclassified_blocks": None,
            "out_of_scope_texts": None,
            "coverage_ratio": None,
            "identity_ok": None,
            "unexplained_text_ids": None,
            "unexplained_numeric_text_ids": None,
        }
        for kind, count in sorted(Counter(text_assignments["assignment_kind"]).items())
    ]

    route_rows = []
    for route_target, group in text_assignments.groupby("route_target", dropna=False, sort=False):
        route_contract = group["counts_toward_contract"].astype(bool)
        route_rows.append(
            {
                "summary_scope": "route_target",
                "sheet_id": None,
                "filename": None,
                "sheet_no": None,
                "sheet_order": None,
                "page_type": None,
                "route_target": route_target,
                "assignment_kind": None,
                "count": int(len(group)),
                "audit_scope_texts": int(route_contract.sum()),
                "assigned_texts": int((group["assignment_kind"].isin(_ASSIGNED_KINDS) & route_contract).sum()),
                "unexplained_texts": int(((group["assignment_kind"] == "unexplained") & route_contract).sum()),
                "unexplained_numeric_texts": int(
                    (
                        (group["assignment_kind"] == "unexplained")
                        & route_contract
                        & group["is_numeric_like"].astype(bool)
                    ).sum()
                ),
                "line_segments": None,
                "unassigned_wire_segments": None,
                "blocks": None,
                "unclassified_blocks": None,
                "out_of_scope_texts": int((group["assignment_kind"] == "out_of_scope").sum()),
                "coverage_ratio": None,
                "identity_ok": None,
                "unexplained_text_ids": None,
                "unexplained_numeric_text_ids": None,
            }
        )

    page_type_rows = []
    for page_type, group in text_assignments.groupby("page_type", dropna=False, sort=False):
        page_type_contract = group["counts_toward_contract"].astype(bool)
        page_type_rows.append(
            {
                "summary_scope": "page_type",
                "sheet_id": None,
                "filename": None,
                "sheet_no": None,
                "sheet_order": None,
                "page_type": page_type,
                "route_target": None,
                "assignment_kind": None,
                "count": int(len(group)),
                "audit_scope_texts": int(page_type_contract.sum()),
                "assigned_texts": int((group["assignment_kind"].isin(_ASSIGNED_KINDS) & page_type_contract).sum()),
                "unexplained_texts": int(((group["assignment_kind"] == "unexplained") & page_type_contract).sum()),
                "unexplained_numeric_texts": int(
                    (
                        (group["assignment_kind"] == "unexplained")
                        & page_type_contract
                        & group["is_numeric_like"].astype(bool)
                    ).sum()
                ),
                "line_segments": None,
                "unassigned_wire_segments": None,
                "blocks": None,
                "unclassified_blocks": None,
                "out_of_scope_texts": int((group["assignment_kind"] == "out_of_scope").sum()),
                "coverage_ratio": None,
                "identity_ok": None,
                "unexplained_text_ids": None,
                "unexplained_numeric_text_ids": None,
            }
        )

    summary_frame = pd.DataFrame([*page_rows, *assignment_rows, *route_rows, *page_type_rows])
    summary_frame = summary_frame.reindex(columns=_SUMMARY_COLUMNS)
    summary_payload = {
        "total_texts": total_texts,
        "audit_scope_texts": audit_scope_texts,
        "assigned_texts": assigned_texts,
        "unexplained_texts": unexplained_texts,
        "unexplained_numeric_texts": unexplained_numeric_texts,
        "unassigned_wire_segments": unassigned_wire_segments,
        "unclassified_blocks": unclassified_blocks,
        "out_of_scope_texts": out_of_scope_texts,
        "coverage_ratio": round(assigned_texts / audit_scope_texts, 4) if audit_scope_texts else 0.0,
        "identity_ok": identity_ok,
        "suspicious_out_of_scope_expansion": suspicious_out_of_scope_expansion,
        "out_of_scope_reason_counts": out_of_scope_reason_counts,
        "assignment_kind_counts": dict(sorted(Counter(text_assignments["assignment_kind"]).items())),
        "page_summaries": sorted(page_rows, key=lambda item: (item["sheet_order"], item["sheet_id"])),
        "route_summaries": route_rows,
        "page_type_summaries": page_type_rows,
        "contract_checks": {
            "identity_ok": identity_ok,
            "single_assignment_per_text": bool(text_assignments["text_id"].is_unique),
            "suspicious_out_of_scope_expansion": suspicious_out_of_scope_expansion,
            "unassigned_defaults_to_unexplained": bool(
                not text_assignments[
                    (~assigned_mask)
                    & (~out_of_scope_mask)
                    & (text_assignments["assignment_kind"] != "unexplained")
                ].any().any()
            ),
        },
    }
    return summary_frame, _jsonable(summary_payload)
