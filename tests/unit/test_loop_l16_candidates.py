from __future__ import annotations

from dwg_audit.audit.candidates import build_terminal_candidates
from dwg_audit.audit.rules import _ambiguous_candidate_groups
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.config import DEFAULT_CONFIG


_PHASE = "schematic_ac_phase_label"
_SEMANTIC_CHANNEL = "schematic_semantic_endpoint_channel"
_NUMERIC_CHANNEL = "terminal_numeric_channel"


def _line_group() -> LineGroup:
    return LineGroup(
        line_group_id="G1",
        sheet_id="S1",
        file_id="F1",
        start_x=180.0,
        start_y=140.0,
        end_x=215.0,
        end_y=140.0,
        length=35.0,
        wire_candidate_score=0.55,
        member_line_ids=["L1"],
        layer_hints=["0"],
        orientation="grid",
    )


def _sheet() -> SheetRecord:
    return SheetRecord("S1", "F1", "04 交流回路图1.dwg", 4, "04", "CT AND VT INPUT 1", "二次原理图", "primary", "filename", True)


def _text(text_id: str, value: str, x: float, y: float) -> TextItem:
    return TextItem("T" + text_id, "S1", "F1", "H" + text_id, "TEXT", value, value, True, "DIM", 0.0, 2.5, x, y, x, y - 1.0, x + 4.0, y + 2.0)


def _accepted_left(candidates: list[TerminalCandidate]) -> list[TerminalCandidate]:
    return sorted(
        (c for c in candidates if c.line_group_id == "G1" and c.side == "left" and c.status == "accepted" and c.value),
        key=lambda c: c.score,
        reverse=True,
    )


def test_ac_phase_label_stays_in_semantic_channel_next_to_terminal_number() -> None:
    texts = [
        _text("1", "721", 178.0, 140.7),
        _text("2", "3U0", 184.0, 141.0),
    ]
    candidates = build_terminal_candidates([_line_group()], texts, DEFAULT_CONFIG, [_sheet()])

    phase = next(c for c in candidates if c.text == "3U0")
    assert phase.channel == _SEMANTIC_CHANNEL
    assert phase.channel_detail == _PHASE


def test_terminal_number_ranks_above_same_side_ac_phase_label() -> None:
    texts = [
        _text("1", "721", 178.0, 140.7),
        _text("2", "3U0", 184.0, 141.0),
    ]
    candidates = build_terminal_candidates([_line_group()], texts, DEFAULT_CONFIG, [_sheet()])

    left = _accepted_left(candidates)
    assert left[0].value == "721"
    assert left[0].channel == _NUMERIC_CHANNEL
    assert left[0].rank == 1
    phase = next(c for c in left if c.channel_detail == _PHASE)
    assert phase.rank is not None and phase.rank > 1


def test_lone_ac_phase_label_is_not_promoted_to_terminal_identity() -> None:
    texts = [_text("2", "3U0", 184.0, 141.0)]
    candidates = build_terminal_candidates([_line_group()], texts, DEFAULT_CONFIG, [_sheet()])

    assert not any(c.channel == _NUMERIC_CHANNEL and c.value == "3U0" for c in candidates)
    for candidate in candidates:
        if candidate.channel_detail == _PHASE:
            assert candidate.channel == _SEMANTIC_CHANNEL


def test_same_side_ac_phase_label_does_not_compete_for_terminal_identity() -> None:
    def make(candidate_id: str, value: str, score: float, channel: str, detail: str | None) -> TerminalCandidate:
        return TerminalCandidate(
            candidate_id=candidate_id,
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            side="left",
            text_id="T" + candidate_id,
            text=value,
            value=value,
            score=score,
            status="accepted",
            rejection_reason=None,
            endpoint_x=180.0,
            endpoint_y=140.0,
            distance_x=1.0,
            distance_y=0.0,
            channel=channel,
            channel_detail=detail,
        )

    candidates = [
        make("C1", "UD4", 1.0, "wire_logic_endpoint_channel", "cad_owned_physical_terminal_label"),
        make("C2", "UN", 0.9244, _SEMANTIC_CHANNEL, _PHASE),
    ]

    assert _ambiguous_candidate_groups(candidates, duplicate_delta=0.08) == {}
