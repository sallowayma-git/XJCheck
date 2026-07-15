"""Geometry and binding contracts for the LA38-style four-port panel."""

from __future__ import annotations

import math

import ezdxf

from dwg_audit.audit.symbol_port_proposal import (
    apply_human_symbol_policy_to_proposal_row,
    build_instance_port_network_candidates,
    propose_ports_from_block,
)


LA38_FINGERPRINT = "5b68b544d3f7834a0b52c64fa69de4c3a0a64ed859e6c95e11957707e1151eeb"


def _la38_proposal(
    *,
    fingerprint: str,
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    offset_contact: bool = False,
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_FOUR_NUMBERED_PANEL")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    circle_radius = 2.416739
    contact_radius = 0.5
    slots = {
        11: (-5.0, 7.5, -1.0),
        12: (5.0, 7.5, 1.0),
        13: (-5.0, 0.0, -1.0),
        14: (5.0, 0.0, 1.0),
    }
    for slot, (circle_x, circle_y, side) in slots.items():
        block.add_circle(transform((circle_x, circle_y)), circle_radius * scale)
        contact_center = (
            circle_x + side * circle_radius,
            circle_y + (0.8 if offset_contact and slot == 11 else 0.0),
        )
        left = transform((contact_center[0] - contact_radius, contact_center[1]))
        right = transform((contact_center[0] + contact_radius, contact_center[1]))
        block.add_lwpolyline(
            [(*left, 1.0), (*right, 1.0)],
            format="xyb",
            close=True,
        )
        block.add_text(
            str(slot),
            dxfattribs={"height": 1.0 * scale, "insert": transform((circle_x, circle_y))},
        )
    for start, end in (
        ((-5.0, 3.75), (5.0, 3.75)),
        ((-2.5, 12.5), (2.5, 12.5)),
        ((0.0, 3.75), (0.0, 12.5)),
    ):
        block.add_line(transform(start), transform(end))
    proposal = propose_ports_from_block(
        block,
        definition_name=block.name,
        definition_fingerprint=fingerprint,
        max_ports=3,
    ).to_dict()
    proposal["file_id"] = "F"
    return proposal


def test_la38_exact_and_rotated_scaled_unseen_emit_four_isolated_ports() -> None:
    variants = (
        _la38_proposal(fingerprint=LA38_FINGERPRINT),
        _la38_proposal(
            fingerprint="unseen-rotated-la38",
            rotation_deg=37.0,
            scale=1.8,
        ),
    )
    for proposal in variants:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert proposal["method"] == "numbered_contact_grid_v1"
        assert {port["component_pin"] for port in proposal["ports"]} == {
            "11",
            "12",
            "13",
            "14",
        }
        assert applied["family_id"] == "component.external_multi_port.v1"
        assert applied["matched_family_rule_id"] == "four-numbered-independent-contact-panel-v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_la38_same_counts_with_offset_contact_does_not_generalize() -> None:
    proposal = _la38_proposal(
        fingerprint="unseen-offset-la38",
        offset_contact=True,
    )
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied.get("matched_family_rule_id") != "four-numbered-independent-contact-panel-v1"


def test_la38_binds_5fa_ports_to_their_own_outward_lines_only() -> None:
    proposal = _la38_proposal(fingerprint="unseen-la38-binding")
    instance = {
        "symbol_instance_id": "SI-5FA",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "27F43",
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
        {"text_id": "T-5FA", "handle": "H-5FA", "sheet_id": "S", "file_id": "F", "normalized_text": "5FA", "insert_x": 100.0, "insert_y": 220.0},
        {"text_id": "T-11", "handle": "H-11", "sheet_id": "S", "file_id": "F", "normalized_text": "5UP11", "insert_x": 82.0, "insert_y": 207.5},
        {"text_id": "T-12", "handle": "H-12", "sheet_id": "S", "file_id": "F", "normalized_text": "5UP12", "insert_x": 118.0, "insert_y": 207.5},
        {"text_id": "T-13", "handle": "H-13", "sheet_id": "S", "file_id": "F", "normalized_text": "5FD3", "insert_x": 82.0, "insert_y": 200.0},
        {"text_id": "T-14", "handle": "H-14", "sheet_id": "S", "file_id": "F", "normalized_text": "5n115", "insert_x": 118.0, "insert_y": 200.0},
    ]
    port_world = {
        "11": (100.0 - 5.0 - 2.416739, 207.5, 80.0, 207.5),
        "12": (100.0 + 5.0 + 2.416739, 207.5, 120.0, 207.5),
        "13": (100.0 - 5.0 - 2.416739, 200.0, 80.0, 200.0),
        "14": (100.0 + 5.0 + 2.416739, 200.0, 120.0, 200.0),
    }
    lines = []
    members = []
    for slot, (start_x, start_y, end_x, end_y) in port_world.items():
        handle = f"HL-{slot}"
        lines.append(
            {"line_id": f"L-{slot}", "handle": handle, "sheet_id": "S", "file_id": "F", "start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y}
        )
        members.append(
            {"member_type": "SOURCE_LINE", "source_handle": handle, "electrical_network_id": f"NET-{slot}"}
        )

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )

    by_identity = {row["component_port_identity"]: row for row in rows}
    assert set(by_identity) == {"5FA-11", "5FA-12", "5FA-13", "5FA-14"}
    assert by_identity["5FA-13"]["component_mapping_external_endpoints"] == ["5FD3"]
    assert by_identity["5FA-14"]["component_mapping_external_endpoints"] == ["5n115"]
    for slot in ("11", "12", "13", "14"):
        row = by_identity[f"5FA-{slot}"]
        assert row["external_network_ids"] == [f"NET-{slot}"]
        assert row["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
        assert row["internal_connectivity_inferred"] is False
        assert row["electrical_union_eligible"] is False
