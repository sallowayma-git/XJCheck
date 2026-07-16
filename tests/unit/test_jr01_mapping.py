"""Geometry and binding contracts for the JR-01 two-port circle box."""

from __future__ import annotations

import math

import ezdxf

from dwg_audit.audit.symbol_port_proposal import (
    apply_human_symbol_policy_to_proposal_row,
    build_instance_port_network_candidates,
    propose_ports_from_block,
)


JR01_FINGERPRINT = (
    "4045826f53f309b218e477ae0163c871aa498b1e0f5c11bf377ee81d26820279"
)


def _jr01_proposal(
    *,
    fingerprint: str,
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    offset_contact: bool = False,
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_JR_TWO_PORT_BOX")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def point(x: float, y: float) -> tuple[float, float]:
        x, y = x * scale, y * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    block.add_lwpolyline(
        [point(-6.25, -5.0), point(6.25, -5.0), point(6.25, 0.0), point(-6.25, 0.0)],
        close=True,
    )
    for slot, x in (("1", -3.75), ("2", 3.75)):
        block.add_circle(point(x, -2.5), radius=2.091171 * scale)
        contact_x = x + (0.8 if offset_contact and slot == "1" else 0.0)
        center = point(contact_x, 0.0)
        radius_axis = (0.5 * scale * cosine, 0.5 * scale * sine)
        block.add_lwpolyline(
            [
                (center[0] - radius_axis[0], center[1] - radius_axis[1], 1.0),
                (center[0] + radius_axis[0], center[1] + radius_axis[1], 1.0),
            ],
            format="xyb",
            close=True,
        )
        block.add_text(
            slot,
            dxfattribs={"height": scale, "insert": point(x - 0.5, -4.0)},
        )
    proposal = propose_ports_from_block(
        block,
        definition_name=block.name,
        definition_fingerprint=fingerprint,
    ).to_dict()
    proposal["file_id"] = "F"
    return proposal


def test_jr01_exact_and_rotated_scaled_unseen_emit_two_isolated_ports() -> None:
    variants = (
        (_jr01_proposal(fingerprint=JR01_FINGERPRINT), "HUMAN_CONFIRMED_MEMBER"),
        (
            _jr01_proposal(
                fingerprint="unseen-rotated-jr01",
                rotation_deg=37.0,
                scale=1.8,
            ),
            "MATCHED",
        ),
    )
    for proposal, expected_status in variants:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert proposal["method"] == "horizontal_numbered_two_circle_box_ports_v1"
        assert {port["component_pin"] for port in proposal["ports"]} == {"1", "2"}
        assert applied["classifier_status"] == expected_status
        assert applied["family_id"] == "component.external_strip_two_port.v1"
        assert applied["matched_family_rule_id"] == "horizontal-numbered-two-circle-box-v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_jr01_same_counts_with_displaced_contact_does_not_generalize() -> None:
    proposal = _jr01_proposal(
        fingerprint="unseen-offset-jr01",
        offset_contact=True,
    )
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied.get("matched_family_rule_id") != "horizontal-numbered-two-circle-box-v1"


def test_jr01_binds_tagged_instance_to_k3_and_k4_without_union() -> None:
    proposal = _jr01_proposal(fingerprint="unseen-jr01-binding")
    instance = {
        "symbol_instance_id": "SI-JR",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "273A5",
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
        {
            "text_id": "TJR",
            "sheet_id": "S",
            "file_id": "F",
            "normalized_text": "JR",
            "insert_x": 100.0,
            "insert_y": 224.5,
        }
    ]
    component_pairs = [
        {
            "pair_id": "PAIR-1",
            "pair_kind": "component_mapping",
            "sheet_id": "S",
            "left_value": "JR-1",
            "right_value": "K-3",
        },
        {
            "pair_id": "PAIR-2",
            "pair_kind": "component_mapping",
            "sheet_id": "S",
            "left_value": "JR-2",
            "right_value": "K-4",
        },
    ]
    rows = build_instance_port_network_candidates(
        [proposal],
        [instance],
        texts,
        [],
        [],
        component_pairs=component_pairs,
    )
    by_identity = {row["component_port_identity"]: row for row in rows}
    assert set(by_identity) == {"JR-1", "JR-2"}
    assert by_identity["JR-1"]["component_mapping_external_endpoints"] == ["K-3"]
    assert by_identity["JR-2"]["component_mapping_external_endpoints"] == ["K-4"]
    assert all(row["status"] == "MEASURED_COMPONENT_PORT_MAPPING" for row in rows)
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)
