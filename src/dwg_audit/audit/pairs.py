from __future__ import annotations

from collections import defaultdict
import re

from dwg_audit.audit.candidates import _CHANNEL_CONTINUATION
from dwg_audit.audit.candidates import _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT
from dwg_audit.audit.candidates import _CHANNEL_TERMINAL_NUMERIC
from dwg_audit.audit.candidates import _CHANNEL_WIRE_LOGIC_ENDPOINT
from dwg_audit.audit.candidates import _looks_like_terminal_semantic_marker
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import PairCandidate
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.utils.ids import IdFactory

_CONTINUATION_SUFFIX_PATTERN = re.compile(r"(?i)n\d{3,}$")


def build_pairs(
    line_groups: list[LineGroup],
    terminal_candidates: list[TerminalCandidate],
    sheets: list[SheetRecord],
    config: dict,
    pair_candidate_id_factory: IdFactory | None = None,
    pair_id_factory: IdFactory | None = None,
) -> tuple[list[PairCandidate], list[Pair]]:
    by_group_side = defaultdict(list)
    by_group_candidates = defaultdict(list)
    for candidate in terminal_candidates:
        by_group_side[(candidate.line_group_id, candidate.side)].append(candidate)
        by_group_candidates[candidate.line_group_id].append(candidate)

    candidate_map = {candidate.candidate_id: candidate for candidate in terminal_candidates}
    sheet_map = {sheet.sheet_id: sheet for sheet in sheets}
    top_k = int(config.get("text", {}).get("top_k_per_side", 3))
    high_threshold = float(config.get("confidence", {}).get("high_threshold", 0.92))
    review_threshold = float(config.get("confidence", {}).get("review_threshold", 0.75))
    pair_candidate_ids = pair_candidate_id_factory or IdFactory("PC")
    pair_ids = pair_id_factory or IdFactory("P")

    pair_candidates: list[PairCandidate] = []
    pairs: list[Pair] = []
    for group in line_groups:
        left_side, right_side = _pair_side_labels(group)
        left = _accepted_sorted(by_group_side[(group.line_group_id, left_side)])[:top_k]
        right = _accepted_sorted(by_group_side[(group.line_group_id, right_side)])[:top_k]
        left, right = _scope_wire_logic_endpoint_candidates(left, right)
        left, right = _scope_schematic_semantic_endpoint_candidates(left, right)
        group_pair_candidates: list[PairCandidate] = []

        if not left or not right:
            left_item = left[0] if left else None
            right_item = right[0] if right else None
            if not left and not right:
                rationale = "missing numeric candidates on both sides"
                status = "discard"
            else:
                rationale = f"missing {left_side} candidate" if not left else f"missing {right_side} candidate"
                status = "review"
            single = PairCandidate(
                pair_candidate_id=pair_candidate_ids.next(),
                line_group_id=group.line_group_id,
                sheet_id=group.sheet_id,
                file_id=group.file_id,
                left_candidate_id=left_item.candidate_id if left_item else None,
                right_candidate_id=right_item.candidate_id if right_item else None,
                left_value=left_item.value if left_item else None,
                right_value=right_item.value if right_item else None,
                score=_pair_score(left_item.score if left_item else 0.0, right_item.score if right_item else 0.0, group.wire_candidate_score),
                status="selected",
                rationale=rationale,
                left_text_id=left_item.text_id if left_item else None,
                right_text_id=right_item.text_id if right_item else None,
                pair_key=_pair_key(left_item.value if left_item else None, right_item.value if right_item else None),
                left_score=left_item.score if left_item else 0.0,
                right_score=right_item.score if right_item else 0.0,
                wire_score=group.wire_candidate_score,
            )
            pair_candidates.append(single)
            confidence = single.score
            evidence = _pair_evidence(
                group,
                sheet_map.get(group.sheet_id),
                single,
                None,
                candidate_map,
                by_group_candidates.get(group.line_group_id, []),
            )
            pair_kind = _pair_kind_from_evidence(evidence)
            if _backfill_continuation_candidate_channels(pair_kind, evidence, left_item, right_item):
                evidence = _pair_evidence(
                    group,
                    sheet_map.get(group.sheet_id),
                    single,
                    None,
                    candidate_map,
                    by_group_candidates.get(group.line_group_id, []),
                )
                pair_kind = _pair_kind_from_evidence(evidence)
            status, rationale = _apply_special_pair_semantics(
                status=status,
                rationale=rationale,
                pair_kind=pair_kind,
            )
            pairs.append(
                Pair(
                    pair_id=pair_ids.next(),
                    line_group_id=group.line_group_id,
                    sheet_id=group.sheet_id,
                    file_id=group.file_id,
                    selected_pair_candidate_id=single.pair_candidate_id,
                    left_value=single.left_value,
                    right_value=single.right_value,
                    confidence=confidence,
                    status=status,
                    rationale=rationale,
                    alternative_pair_candidate_ids=[],
                    confidence_bucket=_bucket_for_status(status),
                    evidence=evidence,
                    left_candidate_id=single.left_candidate_id,
                    right_candidate_id=single.right_candidate_id,
                    left_text_id=single.left_text_id,
                    right_text_id=single.right_text_id,
                    left_coord_x=left_item.text_insert_x if left_item else None,
                    left_coord_y=left_item.text_insert_y if left_item else None,
                    right_coord_x=right_item.text_insert_x if right_item else None,
                    right_coord_y=right_item.text_insert_y if right_item else None,
                    pair_key=single.pair_key,
                    left_score=single.left_score,
                    right_score=single.right_score,
                    wire_score=single.wire_score,
                    ambiguity_gap=single.ambiguity_gap,
                    pair_kind=pair_kind,
                )
            )
            continue

        for left_item in left:
            for right_item in right:
                score = _pair_score(left_item.score, right_item.score, group.wire_candidate_score)
                group_pair_candidates.append(
                    PairCandidate(
                        pair_candidate_id=pair_candidate_ids.next(),
                        line_group_id=group.line_group_id,
                        sheet_id=group.sheet_id,
                        file_id=group.file_id,
                        left_candidate_id=left_item.candidate_id,
                        right_candidate_id=right_item.candidate_id,
                        left_value=left_item.value,
                        right_value=right_item.value,
                        score=score,
                        status="candidate",
                        rationale=f"{left_side}={left_item.value} {right_side}={right_item.value} score={score:.3f}",
                        left_text_id=left_item.text_id,
                        right_text_id=right_item.text_id,
                        pair_key=_pair_key(left_item.value, right_item.value),
                        left_score=left_item.score,
                        right_score=right_item.score,
                        wire_score=group.wire_candidate_score,
                    )
                )

        group_pair_candidates.sort(key=lambda item: item.score, reverse=True)
        ambiguity_gap = None
        if len(group_pair_candidates) > 1:
            ambiguity_gap = round(group_pair_candidates[0].score - group_pair_candidates[1].score, 4)
        for index, candidate in enumerate(group_pair_candidates):
            candidate.status = "selected" if index == 0 else "alternative"
            if index == 0:
                candidate.ambiguity_gap = ambiguity_gap
        pair_candidates.extend(group_pair_candidates)
        selected = group_pair_candidates[0]
        alternative_ids = [item.pair_candidate_id for item in group_pair_candidates[1:]]
        ambiguous = ambiguity_gap is not None and ambiguity_gap < 0.08
        status = "pass" if selected.score >= high_threshold and not ambiguous else "review"
        if selected.score < review_threshold:
            status = "discard"
        rationale = selected.rationale
        if ambiguous:
            rationale += "; ambiguous candidate ordering"
        status, rationale = _apply_component_pair_guards(
            status=status,
            rationale=rationale,
            group=group,
            sheet=sheet_map.get(group.sheet_id),
            selected=selected,
            candidate_map=candidate_map,
        )
        evidence = _pair_evidence(
            group,
            sheet_map.get(group.sheet_id),
            selected,
            alternative_ids,
            candidate_map,
            by_group_candidates.get(group.line_group_id, []),
        )
        pair_kind = _pair_kind_from_evidence(evidence)
        left_candidate = candidate_map.get(selected.left_candidate_id or "")
        right_candidate = candidate_map.get(selected.right_candidate_id or "")
        if _backfill_continuation_candidate_channels(pair_kind, evidence, left_candidate, right_candidate):
            evidence = _pair_evidence(
                group,
                sheet_map.get(group.sheet_id),
                selected,
                alternative_ids,
                candidate_map,
                by_group_candidates.get(group.line_group_id, []),
            )
            pair_kind = _pair_kind_from_evidence(evidence)
        status, rationale = _apply_special_pair_semantics(
            status=status,
            rationale=rationale,
            pair_kind=pair_kind,
        )

        pairs.append(
            Pair(
                pair_id=pair_ids.next(),
                line_group_id=group.line_group_id,
                sheet_id=group.sheet_id,
                file_id=group.file_id,
                selected_pair_candidate_id=selected.pair_candidate_id,
                left_value=selected.left_value,
                right_value=selected.right_value,
                confidence=selected.score,
                status=status,
                rationale=rationale,
                alternative_pair_candidate_ids=alternative_ids,
                confidence_bucket=_bucket_for_status(status),
                evidence=evidence,
                left_candidate_id=selected.left_candidate_id,
                right_candidate_id=selected.right_candidate_id,
                left_text_id=selected.left_text_id,
                right_text_id=selected.right_text_id,
                left_coord_x=_candidate_coord(terminal_candidates, selected.left_candidate_id, "x"),
                left_coord_y=_candidate_coord(terminal_candidates, selected.left_candidate_id, "y"),
                right_coord_x=_candidate_coord(terminal_candidates, selected.right_candidate_id, "x"),
                right_coord_y=_candidate_coord(terminal_candidates, selected.right_candidate_id, "y"),
                pair_key=selected.pair_key,
                left_score=selected.left_score,
                right_score=selected.right_score,
                wire_score=selected.wire_score,
                ambiguity_gap=selected.ambiguity_gap,
                pair_kind=pair_kind,
            )
        )
    return pair_candidates, pairs


def _accepted_sorted(candidates: list[TerminalCandidate]) -> list[TerminalCandidate]:
    accepted = [
        item
        for item in candidates
        if item.status == "accepted"
        and item.value
        and item.channel
        in {
            _CHANNEL_TERMINAL_NUMERIC,
            _CHANNEL_WIRE_LOGIC_ENDPOINT,
            _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT,
        }
    ]
    return sorted(accepted, key=lambda item: item.score, reverse=True)


def _scope_wire_logic_endpoint_candidates(
    left: list[TerminalCandidate],
    right: list[TerminalCandidate],
) -> tuple[list[TerminalCandidate], list[TerminalCandidate]]:
    left_has_numeric = any(item.channel == _CHANNEL_TERMINAL_NUMERIC for item in left)
    right_has_numeric = any(item.channel == _CHANNEL_TERMINAL_NUMERIC for item in right)
    if not right_has_numeric:
        left = [item for item in left if item.channel != _CHANNEL_WIRE_LOGIC_ENDPOINT]
    if not left_has_numeric:
        right = [item for item in right if item.channel != _CHANNEL_WIRE_LOGIC_ENDPOINT]
    return left, right


def _scope_schematic_semantic_endpoint_candidates(
    left: list[TerminalCandidate],
    right: list[TerminalCandidate],
) -> tuple[list[TerminalCandidate], list[TerminalCandidate]]:
    left_has_numeric = any(item.channel == _CHANNEL_TERMINAL_NUMERIC for item in left)
    right_has_numeric = any(item.channel == _CHANNEL_TERMINAL_NUMERIC for item in right)
    if not right_has_numeric:
        left = [item for item in left if item.channel != _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT]
    if not left_has_numeric:
        right = [item for item in right if item.channel != _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT]
    return left, right


def _pair_side_labels(group: LineGroup) -> tuple[str, str]:
    if group.orientation == "vertical":
        return "top", "bottom"
    # horizontal 和 grid 都走 left/right 侧别语义
    return "left", "right"


def _bucket_for_status(status: str) -> str:
    if status == "pass":
        return "high"
    if status == "review":
        return "review"
    return "low"


def _pair_score(left_score: float, right_score: float, wire_score: float) -> float:
    score = (left_score * 0.45) + (right_score * 0.45) + (wire_score * 0.10)
    return round(score, 4)


def _pair_key(left_value: str | None, right_value: str | None) -> str:
    return f"{left_value or '?'}->{right_value or '?'}"


def _pair_evidence(
    group: LineGroup,
    sheet: SheetRecord | None,
    selected: PairCandidate,
    alternative_ids: list[str] | None,
    candidate_map: dict[str, TerminalCandidate],
    group_candidates: list[TerminalCandidate],
) -> dict[str, object]:
    left_side, right_side = _pair_side_labels(group)
    left_candidate = candidate_map.get(selected.left_candidate_id or "")
    right_candidate = candidate_map.get(selected.right_candidate_id or "")
    evidence = {
        "filename": sheet.filename if sheet else None,
        "sheet_no": sheet.sheet_no if sheet else None,
        "sheet_order": sheet.sheet_order if sheet else None,
        "sheet_title": sheet.sheet_title if sheet else None,
        "line_group_id": group.line_group_id,
        "line_orientation": group.orientation,
        "line_start": [group.start_x, group.start_y],
        "line_end": [group.end_x, group.end_y],
        "row_band_id": group.row_band_id,
        "left_side_label": left_side,
        "right_side_label": right_side,
        "selected_pair_candidate_id": selected.pair_candidate_id,
        "selected_left_candidate_id": selected.left_candidate_id,
        "selected_right_candidate_id": selected.right_candidate_id,
        "selected_left_text_id": selected.left_text_id,
        "selected_right_text_id": selected.right_text_id,
        "selected_left_raw_text": left_candidate.text if left_candidate else None,
        "selected_right_raw_text": right_candidate.text if right_candidate else None,
        "selected_left_channel": left_candidate.channel if left_candidate else None,
        "selected_right_channel": right_candidate.channel if right_candidate else None,
        "selected_left_channel_detail": left_candidate.channel_detail if left_candidate else None,
        "selected_right_channel_detail": right_candidate.channel_detail if right_candidate else None,
        "selected_left_is_derived_numeric": _is_derived_numeric_candidate(left_candidate, selected.left_value),
        "selected_right_is_derived_numeric": _is_derived_numeric_candidate(right_candidate, selected.right_value),
        "selected_left_source_block_name": left_candidate.source_block_name if left_candidate else None,
        "selected_right_source_block_name": right_candidate.source_block_name if right_candidate else None,
        "selected_score": selected.score,
        "pair_key": selected.pair_key,
        "score_breakdown": {
            "left_score": selected.left_score,
            "right_score": selected.right_score,
            "wire_score": selected.wire_score,
            "ambiguity_gap": selected.ambiguity_gap,
        },
        "alternative_pair_candidate_ids": alternative_ids or [],
        "pair_kind": "ordinary_pair",
    }
    evidence.update(
        _schematic_wire_logic_endpoint_mapping(
            sheet=sheet,
            selected=selected,
            left_candidate=left_candidate,
            right_candidate=right_candidate,
        )
    )
    evidence.update(
        _schematic_semantic_endpoint_mapping(
            sheet=sheet,
            selected=selected,
            left_candidate=left_candidate,
            right_candidate=right_candidate,
        )
    )
    evidence.update(
        _terminal_continuation_semantics(
            group=group,
            sheet=sheet,
            selected=selected,
            left_candidate=left_candidate,
            right_candidate=right_candidate,
            group_candidates=group_candidates,
        )
    )
    return evidence


def _apply_component_pair_guards(
    *,
    status: str,
    rationale: str,
    group: LineGroup,
    sheet: SheetRecord | None,
    selected: PairCandidate,
    candidate_map: dict[str, TerminalCandidate],
) -> tuple[str, str]:
    if sheet is None or sheet.sheet_category != "元件接线图" or group.orientation != "horizontal":
        return status, rationale

    left_candidate = candidate_map.get(selected.left_candidate_id or "")
    right_candidate = candidate_map.get(selected.right_candidate_id or "")
    if left_candidate is None or right_candidate is None:
        return status, rationale

    left_value = (selected.left_value or "").strip()
    right_value = (selected.right_value or "").strip()
    left_block = (left_candidate.source_block_name or "").strip()
    right_block = (right_candidate.source_block_name or "").strip()

    if (
        selected.left_text_id
        and selected.left_text_id == selected.right_text_id
        and len(left_value) == 1
        and left_value == right_value
    ):
        return "discard", "self_pair_from_same_virtual_text"

    if (
        left_block
        and left_block == right_block
        and len(left_value) == 1
        and len(right_value) == 1
    ):
        return "discard", "block_internal_pin_pair"

    return status, rationale


def _candidate_coord(
    terminal_candidates: list[TerminalCandidate],
    candidate_id: str | None,
    axis: str,
) -> float | None:
    if candidate_id is None:
        return None
    for candidate in terminal_candidates:
        if candidate.candidate_id != candidate_id:
            continue
        return candidate.text_insert_x if axis == "x" else candidate.text_insert_y
    return None


def _terminal_continuation_semantics(
    *,
    group: LineGroup,
    sheet: SheetRecord | None,
    selected: PairCandidate,
    left_candidate: TerminalCandidate | None,
    right_candidate: TerminalCandidate | None,
    group_candidates: list[TerminalCandidate],
) -> dict[str, object]:
    if not _is_terminal_continuation_scope(group=group, sheet=sheet):
        return {}
    same_value_continuation = _same_value_terminal_continuation_semantics(
        selected=selected,
        left_candidate=left_candidate,
        right_candidate=right_candidate,
    )
    if same_value_continuation:
        return same_value_continuation
    bridge_mapping = _terminal_bridge_mapping_semantics(
        group=group,
        selected=selected,
        left_candidate=left_candidate,
        right_candidate=right_candidate,
    )
    if bridge_mapping:
        return bridge_mapping
    semantic_mapping = _terminal_semantic_mapping_semantics(
        selected=selected,
        left_candidate=left_candidate,
        right_candidate=right_candidate,
        group_candidates=group_candidates,
    )
    if semantic_mapping:
        return semantic_mapping
    return _single_sided_terminal_continuation_semantics(
        group=group,
        selected=selected,
        left_candidate=left_candidate,
        right_candidate=right_candidate,
    )


def _schematic_wire_logic_endpoint_mapping(
    *,
    sheet: SheetRecord | None,
    selected: PairCandidate,
    left_candidate: TerminalCandidate | None,
    right_candidate: TerminalCandidate | None,
) -> dict[str, object]:
    if sheet is None or sheet.sheet_category != "二次原理图":
        return {}
    if not selected.left_value or not selected.right_value:
        return {}
    if left_candidate is None or right_candidate is None:
        return {}

    left_is_logic = left_candidate.channel == _CHANNEL_WIRE_LOGIC_ENDPOINT
    right_is_logic = right_candidate.channel == _CHANNEL_WIRE_LOGIC_ENDPOINT
    if left_is_logic == right_is_logic:
        return {}

    logic_candidate = left_candidate if left_is_logic else right_candidate
    numeric_candidate = right_candidate if left_is_logic else left_candidate
    if numeric_candidate.channel != _CHANNEL_TERMINAL_NUMERIC:
        return {}

    logic_endpoint = selected.left_value if left_is_logic else selected.right_value
    numeric_endpoint = selected.right_value if left_is_logic else selected.left_value
    logic_side = "left" if left_is_logic else "right"
    numeric_side = "right" if left_is_logic else "left"
    return {
        "source": "wire_component_mapping",
        "pair_kind": "wire_component_mapping",
        "component_submode": "schematic_wire_logic_endpoint",
        "logical_endpoint": logic_endpoint,
        "logical_endpoint_text_id": logic_candidate.text_id,
        "logical_endpoint_raw": logic_candidate.text,
        "logical_endpoint_side": logic_side,
        "numeric_endpoint": numeric_endpoint,
        "numeric_endpoint_text_id": numeric_candidate.text_id,
        "numeric_endpoint_raw": numeric_candidate.text,
        "numeric_endpoint_side": numeric_side,
        "ordinary_pair_eligible": False,
    }


def _schematic_semantic_endpoint_mapping(
    *,
    sheet: SheetRecord | None,
    selected: PairCandidate,
    left_candidate: TerminalCandidate | None,
    right_candidate: TerminalCandidate | None,
) -> dict[str, object]:
    if sheet is None or sheet.sheet_category != "二次原理图":
        return {}
    if not selected.left_value or not selected.right_value:
        return {}
    if left_candidate is None or right_candidate is None:
        return {}

    left_is_semantic = left_candidate.channel == _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT
    right_is_semantic = right_candidate.channel == _CHANNEL_SCHEMATIC_SEMANTIC_ENDPOINT
    if left_is_semantic == right_is_semantic:
        return {}

    semantic_candidate = left_candidate if left_is_semantic else right_candidate
    numeric_candidate = right_candidate if left_is_semantic else left_candidate
    if numeric_candidate.channel != _CHANNEL_TERMINAL_NUMERIC:
        return {}

    semantic_endpoint = selected.left_value if left_is_semantic else selected.right_value
    numeric_endpoint = selected.right_value if left_is_semantic else selected.left_value
    semantic_side = "left" if left_is_semantic else "right"
    numeric_side = "right" if left_is_semantic else "left"
    mapping_kind = semantic_candidate.channel_detail or "schematic_semantic_endpoint"
    return {
        "source": "semantic_mapping",
        "pair_kind": "semantic_mapping",
        "semantic_kind": "schematic_semantic_endpoint",
        "semantic_mapping_kind": mapping_kind,
        "semantic_endpoint": semantic_endpoint,
        "semantic_endpoint_text_id": semantic_candidate.text_id,
        "semantic_endpoint_raw": semantic_candidate.text,
        "semantic_endpoint_side": semantic_side,
        "numeric_endpoint": numeric_endpoint,
        "numeric_endpoint_text_id": numeric_candidate.text_id,
        "numeric_endpoint_raw": numeric_candidate.text,
        "numeric_endpoint_side": numeric_side,
        "ordinary_pair_eligible": False,
    }


def _is_terminal_continuation_scope(*, group: LineGroup, sheet: SheetRecord | None) -> bool:
    if sheet is None or sheet.sheet_category != "屏端子图":
        return False
    if group.orientation != "horizontal":
        return False
    if not (70.0 <= group.length <= 80.0):
        return False
    return True


def _same_value_terminal_continuation_semantics(
    *,
    selected: PairCandidate,
    left_candidate: TerminalCandidate | None,
    right_candidate: TerminalCandidate | None,
) -> dict[str, object]:
    if not selected.left_value or selected.left_value != selected.right_value:
        return {}
    if not selected.left_text_id or not selected.right_text_id or selected.left_text_id == selected.right_text_id:
        return {}
    if not _is_derived_numeric_candidate(left_candidate, selected.left_value):
        return {}
    if not _is_derived_numeric_candidate(right_candidate, selected.right_value):
        return {}
    left_raw = (left_candidate.text if left_candidate else "").strip()
    right_raw = (right_candidate.text if right_candidate else "").strip()
    if not _CONTINUATION_SUFFIX_PATTERN.search(left_raw):
        return {}
    if not _CONTINUATION_SUFFIX_PATTERN.search(right_raw):
        return {}
    return {
        "pair_kind": "continuation",
        "semantic_kind": "continuation_same_value",
        "ordinary_pair_eligible": False,
        "continuation_kind": "terminal_same_value_bridge",
    }


def _terminal_bridge_mapping_semantics(
    *,
    group: LineGroup,
    selected: PairCandidate,
    left_candidate: TerminalCandidate | None,
    right_candidate: TerminalCandidate | None,
) -> dict[str, object]:
    if not selected.left_value or not selected.right_value:
        return {}
    if selected.left_value == selected.right_value:
        return {}
    if min(group.start_x, group.end_x) < 300.0:
        return {}
    if not _is_derived_numeric_candidate(left_candidate, selected.left_value):
        return {}
    if not _is_derived_numeric_candidate(right_candidate, selected.right_value):
        return {}
    left_raw = (left_candidate.text if left_candidate else "").strip()
    right_raw = (right_candidate.text if right_candidate else "").strip()
    if not _CONTINUATION_SUFFIX_PATTERN.search(left_raw):
        return {}
    if not _CONTINUATION_SUFFIX_PATTERN.search(right_raw):
        return {}
    return {
        "pair_kind": "bridge_mapping",
        "semantic_kind": "terminal_bridge_mapping",
        "ordinary_pair_eligible": False,
        "bridge_mapping_kind": "terminal_short_bridge_cross_column",
    }


def _single_sided_terminal_continuation_semantics(
    *,
    group: LineGroup,
    selected: PairCandidate,
    left_candidate: TerminalCandidate | None,
    right_candidate: TerminalCandidate | None,
) -> dict[str, object]:
    if bool(selected.left_value) == bool(selected.right_value):
        return {}
    selected_candidate = left_candidate if selected.left_value else right_candidate
    selected_value = selected.left_value if selected.left_value else selected.right_value
    if not selected_candidate or not selected_value:
        return {}

    missing_side = "left" if not selected.left_value else "right"
    continuation_kind = f"terminal_missing_{missing_side}_continuation"
    selected_raw = selected_candidate.text.strip()
    if (
        _is_derived_numeric_candidate(selected_candidate, selected_value)
        and _CONTINUATION_SUFFIX_PATTERN.search(selected_raw)
    ):
        return {
            "pair_kind": "continuation",
            "semantic_kind": "continuation_single_sided",
            "ordinary_pair_eligible": False,
            "continuation_kind": continuation_kind,
            "continuation_missing_side": missing_side,
        }
    if min(group.start_x, group.end_x) < 300.0:
        return {}
    return {
        "pair_kind": "continuation",
        "semantic_kind": "continuation_single_sided",
        "ordinary_pair_eligible": False,
        "continuation_kind": continuation_kind,
        "continuation_missing_side": missing_side,
    }


def _terminal_semantic_mapping_semantics(
    *,
    selected: PairCandidate,
    left_candidate: TerminalCandidate | None,
    right_candidate: TerminalCandidate | None,
    group_candidates: list[TerminalCandidate],
) -> dict[str, object]:
    if bool(selected.left_value) == bool(selected.right_value):
        return {}
    selected_candidate = left_candidate if selected.left_value else right_candidate
    selected_value = selected.left_value if selected.left_value else selected.right_value
    if not selected_candidate or not selected_value:
        return {}
    selected_raw = selected_candidate.text.strip()
    if not (
        _is_derived_numeric_candidate(selected_candidate, selected_value)
        and _CONTINUATION_SUFFIX_PATTERN.search(selected_raw)
    ):
        return {}
    semantic_marker_texts = _terminal_semantic_marker_texts(group_candidates)
    if not semantic_marker_texts:
        return {}
    missing_side = "left" if not selected.left_value else "right"
    return {
        "pair_kind": "semantic_mapping",
        "semantic_kind": "terminal_semantic_mapping",
        "ordinary_pair_eligible": False,
        "semantic_mapping_kind": "terminal_semantic_row",
        "semantic_mapping_missing_side": missing_side,
        "semantic_marker_texts": semantic_marker_texts,
    }


def _terminal_semantic_marker_texts(group_candidates: list[TerminalCandidate]) -> list[str]:
    marker_texts = {
        candidate.text.strip()
        for candidate in group_candidates
        if _looks_like_terminal_semantic_marker(candidate.text)
    }
    return sorted(text for text in marker_texts if text)


def _pair_kind_from_evidence(evidence: dict[str, object]) -> str:
    pair_kind = evidence.get("pair_kind")
    if isinstance(pair_kind, str) and pair_kind.strip():
        return pair_kind.strip()
    return "ordinary_pair"


def _backfill_continuation_candidate_channels(
    pair_kind: str,
    evidence: dict[str, object],
    left_candidate: TerminalCandidate | None,
    right_candidate: TerminalCandidate | None,
) -> bool:
    if pair_kind not in {"continuation", "bridge_mapping"}:
        return False

    if pair_kind == "continuation":
        raw_detail = evidence.get("continuation_kind") or evidence.get("semantic_kind")
    else:
        raw_detail = evidence.get("bridge_mapping_kind") or evidence.get("semantic_kind")
    channel_detail = raw_detail.strip() if isinstance(raw_detail, str) and raw_detail.strip() else None

    changed = False
    for candidate in (left_candidate, right_candidate):
        if candidate is None or candidate.status != "accepted" or not candidate.value:
            continue
        if candidate.channel not in {_CHANNEL_TERMINAL_NUMERIC, _CHANNEL_CONTINUATION}:
            continue
        if candidate.channel == _CHANNEL_CONTINUATION and candidate.channel_detail == channel_detail:
            continue
        candidate.channel = _CHANNEL_CONTINUATION
        candidate.channel_detail = channel_detail
        changed = True
    return changed


def _apply_special_pair_semantics(
    *,
    status: str,
    rationale: str,
    pair_kind: str,
) -> tuple[str, str]:
    if pair_kind == "continuation":
        if "continuation" not in rationale:
            rationale = f"{rationale}; continuation relation"
        return "review", rationale
    if pair_kind == "bridge_mapping":
        if "bridge mapping" not in rationale:
            rationale = f"{rationale}; bridge mapping relation"
        return "review", rationale
    if pair_kind == "semantic_mapping":
        if "semantic mapping" not in rationale:
            rationale = f"{rationale}; semantic mapping relation"
        return "review", rationale
    if pair_kind == "wire_component_mapping":
        if "wire component mapping" not in rationale:
            rationale = f"{rationale}; wire component mapping relation"
        return status, rationale
    return status, rationale


def _is_derived_numeric_candidate(candidate: TerminalCandidate | None, value: str | None) -> bool:
    if candidate is None or not value:
        return False
    return candidate.text.strip() != value.strip()
