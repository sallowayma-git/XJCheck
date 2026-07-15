"""Geometry and binding contracts for the PWF176 two-contact actuator."""

from __future__ import annotations

import math

import ezdxf

from dwg_audit.audit.symbol_port_proposal import (
    apply_human_symbol_policy_to_proposal_row,
    build_instance_port_network_candidates,
    propose_ports_from_block,
)


PWF176_FINGERPRINT = "8ffdfeebc545ed07bf9b740146cf2c8c729557b453649d679f18248d228d308e"


def _pwf176_proposal(
    *,
    fingerprint: str,
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    offset_actuator: bool = False,
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_TWO_CONTACT_ACTUATOR")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    for start, end in (
        ((3.75, -1.875), (7.5, 0.0)),
        ((0.0, 0.0), (3.75, 0.0)),
        ((11.25, 0.0), (7.5, 0.0)),
        ((6.56193375, -4.53125), (6.56193375, -3.7832325033)),
        ((4.6875, -4.53125), (4.6875, -3.7832325033)),
        ((4.6875, -4.53125), (6.56193375, -4.53125)),
        ((5.624716875 + (0.6 if offset_actuator else 0.0), -3.7063215123), (5.624716875 + (0.6 if offset_actuator else 0.0), -4.53125)),
        ((5.624716875, -2.3245956935), (5.624716875, -3.1495241813)),
        ((5.624716875, -0.9376415625), (5.624716875, -1.7677983625)),
    ):
        block.add_line(transform(start), transform(end))
    for center_x in (0.0, 11.25):
        left = transform((center_x - 0.5, 0.0))
        right = transform((center_x + 0.5, 0.0))
        block.add_lwpolyline([(*left, 1.0), (*right, 1.0)], format="xyb", close=True)

    proposal = propose_ports_from_block(
        block,
        definition_name=block.name,
        definition_fingerprint=fingerprint,
        max_ports=2,
    ).to_dict()
    proposal["file_id"] = "F"
    return proposal


def test_pwf176_exact_and_rotated_scaled_unseen_emit_two_isolated_ports() -> None:
    variants = (
        _pwf176_proposal(fingerprint=PWF176_FINGERPRINT),
        _pwf176_proposal(
            fingerprint="unseen-rotated-pwf176",
            rotation_deg=37.0,
            scale=1.8,
        ),
    )
    for proposal in variants:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert proposal["method"] == "two_contact_mechanical_actuator_ports_v1"
        assert len(proposal["ports"]) == 2
        assert applied["family_id"] == "component.external_strip_two_port.v1"
        assert applied["matched_family_rule_id"] == "two-contact-mechanical-actuator-v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_pwf176_same_counts_with_offset_actuator_does_not_generalize() -> None:
    proposal = _pwf176_proposal(
        fingerprint="unseen-offset-pwf176",
        offset_actuator=True,
    )
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied.get("matched_family_rule_id") != "two-contact-mechanical-actuator-v1"


def test_pwf176_binds_1fa_13_to_1qd3_without_port_union() -> None:
    proposal = _pwf176_proposal(fingerprint="unseen-pwf176-binding")
    instance = {
        "symbol_instance_id": "SI-1FA",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "233C5",
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
    texts = [
        {"text_id": "T-1FA", "handle": "H-1FA", "sheet_id": "S", "file_id": "F", "normalized_text": "1FA", "insert_x": 105.625, "insert_y": 201.62},
        {"text_id": "T-13", "handle": "H-13", "sheet_id": "S", "file_id": "F", "normalized_text": "13", "insert_x": 98.75, "insert_y": 201.0},
        {"text_id": "T-14", "handle": "H-14", "sheet_id": "S", "file_id": "F", "normalized_text": "14", "insert_x": 110.0, "insert_y": 201.0},
        {"text_id": "T-1QD3", "handle": "H-1QD3", "sheet_id": "S", "file_id": "F", "normalized_text": "1QD3", "insert_x": 89.0, "insert_y": 202.0},
    ]
    lines = [
        {"line_id": "L-13", "handle": "HL-13", "sheet_id": "S", "file_id": "F", "start_x": 100.0, "start_y": 200.0, "end_x": 90.0, "end_y": 200.0},
        {"line_id": "L-14", "handle": "HL-14", "sheet_id": "S", "file_id": "F", "start_x": 111.25, "start_y": 200.0, "end_x": 121.25, "end_y": 200.0},
    ]
    members = [
        {"member_type": "SOURCE_LINE", "source_handle": "HL-13", "electrical_network_id": "NET-13"},
        {"member_type": "SOURCE_LINE", "source_handle": "HL-14", "electrical_network_id": "NET-14"},
    ]
    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )

    by_identity = {row["component_port_identity"]: row for row in rows}
    assert set(by_identity) == {"1FA-13", "1FA-14"}
    assert by_identity["1FA-13"]["component_mapping_external_endpoints"] == ["1QD3"]
    assert by_identity["1FA-14"]["component_mapping_external_endpoints"] == []
    assert by_identity["1FA-13"]["external_network_ids"] == ["NET-13"]
    assert by_identity["1FA-14"]["external_network_ids"] == ["NET-14"]
    for row in by_identity.values():
        assert row["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
        assert row["internal_connectivity_inferred"] is False
        assert row["electrical_union_eligible"] is False
