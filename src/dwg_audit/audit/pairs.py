from __future__ import annotations

from collections import defaultdict

from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import PairCandidate
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.utils.ids import IdFactory


def build_pairs(
    line_groups: list[LineGroup],
    terminal_candidates: list[TerminalCandidate],
    sheets: list[SheetRecord],
    config: dict,
) -> tuple[list[PairCandidate], list[Pair]]:
    by_group_side = defaultdict(list)
    for candidate in terminal_candidates:
        by_group_side[(candidate.line_group_id, candidate.side)].append(candidate)

    sheet_map = {sheet.sheet_id: sheet for sheet in sheets}
    top_k = int(config.get("text", {}).get("top_k_per_side", 3))
    high_threshold = float(config.get("confidence", {}).get("high_threshold", 0.92))
    review_threshold = float(config.get("confidence", {}).get("review_threshold", 0.75))
    pair_candidate_ids = IdFactory("PC")
    pair_ids = IdFactory("P")

    pair_candidates: list[PairCandidate] = []
    pairs: list[Pair] = []
    for group in line_groups:
        left = _accepted_sorted(by_group_side[(group.line_group_id, "left")])[:top_k]
        right = _accepted_sorted(by_group_side[(group.line_group_id, "right")])[:top_k]
        group_pair_candidates: list[PairCandidate] = []

        if not left or not right:
            left_item = left[0] if left else None
            right_item = right[0] if right else None
            if not left and not right:
                rationale = "missing numeric candidates on both sides"
                status = "discard"
            else:
                rationale = "missing left candidate" if not left else "missing right candidate"
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
            )
            pair_candidates.append(single)
            confidence = single.score
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
                    evidence=_pair_evidence(group, sheet_map.get(group.sheet_id), single, None),
                    left_candidate_id=single.left_candidate_id,
                    right_candidate_id=single.right_candidate_id,
                    left_text_id=single.left_text_id,
                    right_text_id=single.right_text_id,
                    left_coord_x=left_item.text_insert_x if left_item else None,
                    left_coord_y=left_item.text_insert_y if left_item else None,
                    right_coord_x=right_item.text_insert_x if right_item else None,
                    right_coord_y=right_item.text_insert_y if right_item else None,
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
                        rationale=f"left={left_item.value} right={right_item.value} score={score:.3f}",
                        left_text_id=left_item.text_id,
                        right_text_id=right_item.text_id,
                    )
                )

        group_pair_candidates.sort(key=lambda item: item.score, reverse=True)
        for index, candidate in enumerate(group_pair_candidates):
            candidate.status = "selected" if index == 0 else "alternative"
        pair_candidates.extend(group_pair_candidates)
        selected = group_pair_candidates[0]
        alternative_ids = [item.pair_candidate_id for item in group_pair_candidates[1:]]
        ambiguous = len(group_pair_candidates) > 1 and abs(group_pair_candidates[0].score - group_pair_candidates[1].score) < 0.08
        status = "pass" if selected.score >= high_threshold and not ambiguous else "review"
        if selected.score < review_threshold:
            status = "discard"
        rationale = selected.rationale
        if ambiguous:
            rationale += "; ambiguous candidate ordering"

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
                evidence=_pair_evidence(group, sheet_map.get(group.sheet_id), selected, alternative_ids),
                left_candidate_id=selected.left_candidate_id,
                right_candidate_id=selected.right_candidate_id,
                left_text_id=selected.left_text_id,
                right_text_id=selected.right_text_id,
                left_coord_x=_candidate_coord(terminal_candidates, selected.left_candidate_id, "x"),
                left_coord_y=_candidate_coord(terminal_candidates, selected.left_candidate_id, "y"),
                right_coord_x=_candidate_coord(terminal_candidates, selected.right_candidate_id, "x"),
                right_coord_y=_candidate_coord(terminal_candidates, selected.right_candidate_id, "y"),
            )
        )
    return pair_candidates, pairs


def _accepted_sorted(candidates: list[TerminalCandidate]) -> list[TerminalCandidate]:
    accepted = [item for item in candidates if item.status == "accepted" and item.value]
    return sorted(accepted, key=lambda item: item.score, reverse=True)


def _bucket_for_status(status: str) -> str:
    if status == "pass":
        return "high"
    if status == "review":
        return "review"
    return "low"


def _pair_score(left_score: float, right_score: float, wire_score: float) -> float:
    score = (left_score * 0.45) + (right_score * 0.45) + (wire_score * 0.10)
    return round(score, 4)


def _pair_evidence(
    group: LineGroup,
    sheet: SheetRecord | None,
    selected: PairCandidate,
    alternative_ids: list[str] | None,
) -> dict[str, object]:
    return {
        "filename": sheet.filename if sheet else None,
        "sheet_no": sheet.sheet_no if sheet else None,
        "sheet_order": sheet.sheet_order if sheet else None,
        "sheet_title": sheet.sheet_title if sheet else None,
        "line_group_id": group.line_group_id,
        "line_start": [group.start_x, group.start_y],
        "line_end": [group.end_x, group.end_y],
        "selected_pair_candidate_id": selected.pair_candidate_id,
        "selected_left_candidate_id": selected.left_candidate_id,
        "selected_right_candidate_id": selected.right_candidate_id,
        "selected_left_text_id": selected.left_text_id,
        "selected_right_text_id": selected.right_text_id,
        "selected_score": selected.score,
        "alternative_pair_candidate_ids": alternative_ids or [],
    }


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
