"""Generalized IGNORE contracts for the closed B+/B- cable sleeve."""

from __future__ import annotations

import math

import ezdxf

from dwg_audit.audit.symbol_port_proposal import (
    apply_human_symbol_policy_to_proposal_row,
    build_instance_port_network_candidates,
    propose_ports_from_block,
)


AC6_FINGERPRINT = "2c4f73274833c1b08e7320666b993c4bd5d3e1eedc7a3931b4075e334b8ec1f7"


def _sleeve_proposal(
    *,
    fingerprint: str,
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    inward_bottom_arc: bool = False,
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_CLOSED_CABLE_SLEEVE")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    block.add_arc(
        transform((0.0, 2.0)),
        1.0 * scale,
        rotation_deg,
        180.0 + rotation_deg,
    )
    block.add_arc(
        transform((0.0, -2.0)),
        1.0 * scale,
        rotation_deg if inward_bottom_arc else 180.0 + rotation_deg,
        180.0 + rotation_deg if inward_bottom_arc else 360.0 + rotation_deg,
    )
    block.add_line(transform((-1.0, 2.0)), transform((-1.0, -2.0)))
    block.add_line(transform((1.0, -2.0)), transform((1.0, 2.0)))
    proposal = propose_ports_from_block(
        block,
        definition_name=block.name,
        definition_fingerprint=fingerprint,
        max_ports=2,
    ).to_dict()
    proposal["file_id"] = "F"
    return proposal


def test_closed_cable_sleeve_exact_and_rotated_unseen_are_zero_port_ignore() -> None:
    variants = (
        _sleeve_proposal(fingerprint=AC6_FINGERPRINT),
        _sleeve_proposal(
            fingerprint="unseen-rotated-cable-sleeve",
            rotation_deg=37.0,
            scale=1.8,
        ),
    )
    for proposal in variants:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "non_electrical.cable_sleeve_ignored.v1"
        assert applied["matched_family_rule_id"] == "closed-opposed-semicircle-cable-sleeve-v1"
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["ports"] == []
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_same_count_capsule_with_inward_bottom_arc_stays_review() -> None:
    proposal = _sleeve_proposal(
        fingerprint="unseen-inward-bottom-arc",
        inward_bottom_arc=True,
    )
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied.get("matched_family_rule_id") != "closed-opposed-semicircle-cable-sleeve-v1"
    assert applied["behavior_mode"] != "IGNORE"
    assert applied["ports"]


def test_ignored_sleeve_emits_no_candidate_over_independent_underlying_lines() -> None:
    proposal = _sleeve_proposal(fingerprint=AC6_FINGERPRINT)
    instance = {
        "symbol_instance_id": "SI-SLEEVE",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "1C298",
        "definition_name": proposal["definition_name"],
        "definition_fingerprint": proposal["definition_fingerprint"],
        "transform_json": {
            "matrix44": [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [100, 200, 0, 1],
            ]
        },
    }
    lines = [
        {"line_id": "B+", "handle": "H-B+", "sheet_id": "S", "file_id": "F", "start_x": 80.0, "start_y": 202.0, "end_x": 120.0, "end_y": 202.0},
        {"line_id": "B-", "handle": "H-B-", "sheet_id": "S", "file_id": "F", "start_x": 80.0, "start_y": 198.0, "end_x": 120.0, "end_y": 198.0},
    ]
    rows = build_instance_port_network_candidates(
        [proposal], [instance], [], lines, []
    )
    assert rows == []
    assert lines[0]["line_id"] == "B+"
    assert lines[1]["line_id"] == "B-"
    assert lines[0]["start_y"] != lines[1]["start_y"]
