"""Generalized IGNORE contracts for the grounded three-row LVS-CB panel."""

from __future__ import annotations

import math

import ezdxf

from dwg_audit.audit.symbol_port_proposal import (
    apply_human_symbol_policy_to_proposal_row,
    propose_ports_from_block,
)


AC5_FINGERPRINT = "346f8b01c9cf292256cf0fecbd3c680e5e79471cfe21420fb1a2d311ed20007e"


def _panel_proposal(
    *,
    fingerprint: str,
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    offset_mechanism: bool = False,
) -> dict:
    document = ezdxf.new()
    mechanism = document.blocks.new("RENAMED_REPEATED_MECHANISM_CHILD")
    mechanism.add_lwpolyline([(-0.5, 0.0, 1.0), (0.5, 0.0, 1.0)], format="xyb", close=True)
    mechanism.add_lwpolyline([(-0.5, -7.5, 1.0), (0.5, -7.5, 1.0)], format="xyb", close=True)
    mechanism.add_arc((0.0, -2.5), 2.5, 0.0, 180.0)
    mechanism.add_arc((0.0, -5.0), 2.5, 180.0, 360.0)
    mechanism.add_line((-1.25, 0.0), (1.25, 0.0))
    mechanism.add_line((-1.25, -7.5), (1.25, -7.5))
    mechanism.add_line((-1.25, 2.5), (1.25, 2.5))

    ground = document.blocks.new("RENAMED_GROUND_CHILD")
    ground.add_lwpolyline([(-0.5, 0.0, 1.0), (0.5, 0.0, 1.0)], format="xyb", close=True)
    ground.add_line((0.0, 0.0), (-3.0, 0.0))
    ground.add_line((-3.0, -1.0), (-3.0, 1.0))
    ground.add_line((-3.75, -0.75), (-3.75, 0.75))
    ground.add_line((-4.5, -0.5), (-4.5, 0.5))

    panel = document.blocks.new("RENAMED_GROUNDED_THREE_ROW_PANEL")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    for start, end in (
        ((10.0, 0.0), (0.0, 0.0)),
        ((0.0, 0.0), (0.0, -32.5)),
        ((10.0, -10.0), (0.0, -10.0)),
        ((10.0, -20.0), (0.0, -20.0)),
        ((17.5, 0.0), (22.5, 0.0)),
        ((17.5, -10.0), (22.5, -10.0)),
        ((17.5, -20.0), (22.5, -20.0)),
        ((0.0, -30.0), (22.5, -30.0)),
    ):
        panel.add_line(transform(start), transform(end))
    for y in (-10.0, -20.0, -30.0):
        left = transform((-0.25, y))
        right = transform((0.25, y))
        panel.add_lwpolyline([(*left, 1.0), (*right, 1.0)], format="xyb", close=True)

    for index, y in enumerate((0.0, -10.0, -20.0)):
        x = 17.5 + (1.0 if offset_mechanism and index == 1 else 0.0)
        panel.add_blockref(
            mechanism.name,
            transform((x, y)),
            dxfattribs={
                "rotation": (270.0 + rotation_deg) % 360.0,
                "xscale": scale,
                "yscale": scale,
            },
        )
    panel.add_blockref(
        ground.name,
        transform((0.0, -32.505)),
        dxfattribs={
            "rotation": (90.0 + rotation_deg) % 360.0,
            "xscale": scale,
            "yscale": scale,
        },
    )
    return propose_ports_from_block(
        panel,
        definition_name=panel.name,
        definition_fingerprint=fingerprint,
        max_ports=3,
    ).to_dict()


def test_grounded_three_row_panel_exact_and_rotated_unseen_are_zero_port_ignore() -> None:
    variants = (
        _panel_proposal(fingerprint=AC5_FINGERPRINT),
        _panel_proposal(
            fingerprint="unseen-rotated-grounded-three-row-panel",
            rotation_deg=37.0,
            scale=1.8,
        ),
    )
    for proposal in variants:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.nonconnective_grounded_three_row_cb_panel_ignored.v1"
        assert applied["matched_family_rule_id"] == "grounded-three-row-repeated-mechanism-panel-v1"
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["ports"] == []
        assert applied["allow_port_emission"] is False
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_grounded_three_row_panel_with_displaced_child_stays_review() -> None:
    proposal = _panel_proposal(
        fingerprint="unseen-displaced-grounded-three-row-panel",
        offset_mechanism=True,
    )
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied.get("matched_family_rule_id") != "grounded-three-row-repeated-mechanism-panel-v1"
    assert applied["behavior_mode"] != "IGNORE"
    assert applied["ports"]
