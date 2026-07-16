"""Geometry and binding contracts for the CD-WSK eight-port component."""

from __future__ import annotations

import math

import ezdxf

from dwg_audit.audit.symbol_port_proposal import (
    apply_human_symbol_policy_to_proposal_row,
    build_instance_port_network_candidates,
    propose_ports_from_block,
)


CD_WSK_FINGERPRINT = (
    "d1202915a0dee8f65d4024cd3a144cf7de7147bacc5916dc7cd4b0ebad124bda"
)


def _cd_wsk_proposal(
    *,
    fingerprint: str,
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    offset_contact: bool = False,
) -> dict:
    document = ezdxf.new()
    nested = document.blocks.new("CD_WSK_INTERNAL_SENSOR")
    for index in range(12):
        nested.add_line((index * 0.1, 0.0), (index * 0.1, 1.0))
    nested.add_lwpolyline([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)], close=True)
    block = document.blocks.new("RENAMED_EIGHT_PORT_UNIT")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def point(x: float, y: float) -> tuple[float, float]:
        x, y = x * scale, y * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    def rectangle(min_x: float, min_y: float, max_x: float, max_y: float) -> None:
        block.add_lwpolyline(
            [
                point(min_x, min_y),
                point(max_x, min_y),
                point(max_x, max_y),
                point(min_x, max_y),
            ],
            close=True,
        )

    rectangle(-18.0, -10.0, 18.0, 10.0)
    slots = {
        7: (-15.5, 7.5, -18.0),
        8: (-15.5, 2.5, -18.0),
        1: (-15.5, -2.5, -18.0),
        2: (-15.5, -7.5, -18.0),
        6: (15.5, 7.5, 18.0),
        5: (15.5, 2.5, 18.0),
        4: (15.5, -2.5, 18.0),
        3: (15.5, -7.5, 18.0),
    }
    contact_radius = 0.5 * scale
    for slot, (cell_x, cell_y, contact_x) in slots.items():
        rectangle(cell_x - 2.5, cell_y - 2.5, cell_x + 2.5, cell_y + 2.5)
        contact_y = cell_y + (2.0 if offset_contact and slot == 7 else 0.0)
        center = point(contact_x, contact_y)
        radius_axis = (contact_radius * cosine, contact_radius * sine)
        block.add_lwpolyline(
            [
                (center[0] - radius_axis[0], center[1] - radius_axis[1], 1.0),
                (center[0] + radius_axis[0], center[1] + radius_axis[1], 1.0),
            ],
            format="xyb",
            close=True,
        )
        block.add_text(
            str(slot),
            dxfattribs={"height": scale, "insert": point(cell_x, cell_y)},
        )

    internal_lines = (
        ((-12.5, 7.5), (-9.0, 7.5)),
        ((-12.5, 2.5), (-9.5, 2.5)),
        ((-12.5, -2.5), (-9.5, -2.5)),
        ((-12.5, -7.5), (-9.0, -7.5)),
        ((-9.5, -6.0), (-9.5, 6.0)),
        ((-9.5, 6.0), (-8.5, 6.0)),
        ((-8.5, 6.0), (-8.5, -6.0)),
        ((-8.5, -6.0), (-9.5, -6.0)),
        ((-9.0, 6.0), (-9.0, 7.5)),
        ((-9.0, -7.5), (-9.0, -6.0)),
        ((12.5, -7.5), (10.0, -7.5)),
        ((12.5, -2.5), (10.0, -2.5)),
        ((-10.2, -2.3), (-8.0, 0.7)),
    )
    for start, end in internal_lines:
        block.add_line(point(*start), point(*end))

    filler_labels = [
        "SHARED",
        "LOAD",
        "RED",
        "BLACK",
        "YELLOW",
        "GREEN",
        "L",
        "N",
        "PHASE",
        "NEUTRAL",
        "TEMP",
        "HUMID",
        "SENSOR",
        "COMMON",
        "AC220V",
        "50HZ",
        "R",
        "B",
        "Y",
        "G",
        "T",
        "H",
        "UNIT",
    ]
    for index, value in enumerate(filler_labels):
        block.add_text(
            value,
            dxfattribs={
                "height": 0.7 * scale,
                "insert": point(-7.0 + index % 8, -7.0 + (index // 8) * 2.0),
            },
        )
    nested_insert = point(10.0, -2.5)
    block.add_blockref(
        nested.name,
        nested_insert,
        dxfattribs={
            "rotation": rotation_deg,
            "xscale": scale,
            "yscale": scale,
        },
    )
    proposal = propose_ports_from_block(
        block,
        definition_name=block.name,
        definition_fingerprint=fingerprint,
        max_ports=8,
    ).to_dict()
    proposal["file_id"] = "F"
    return proposal


def test_cd_wsk_exact_and_rotated_scaled_unseen_emit_eight_isolated_ports() -> None:
    variants = (
        (_cd_wsk_proposal(fingerprint=CD_WSK_FINGERPRINT), "HUMAN_CONFIRMED_MEMBER"),
        (
            _cd_wsk_proposal(
                fingerprint="unseen-rotated-cd-wsk",
                rotation_deg=37.0,
                scale=1.8,
            ),
            "MATCHED",
        ),
    )
    for proposal, expected_status in variants:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert proposal["method"] == "numbered_contact_grid_v1"
        assert {port["component_pin"] for port in proposal["ports"]} == {
            str(slot) for slot in range(1, 9)
        }
        assert applied["classifier_status"] == expected_status
        assert applied["family_id"] == "component.external_multi_port.v1"
        assert applied["matched_family_rule_id"] == "eight-numbered-side-contact-panel-v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_cd_wsk_same_counts_with_displaced_contact_does_not_generalize() -> None:
    proposal = _cd_wsk_proposal(
        fingerprint="unseen-offset-cd-wsk",
        offset_contact=True,
    )
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied.get("matched_family_rule_id") != "eight-numbered-side-contact-panel-v1"


def test_cd_wsk_binds_circular_tag_name_to_eight_same_side_routes() -> None:
    proposal = _cd_wsk_proposal(fingerprint="unseen-cd-wsk-binding")
    instance = {
        "symbol_instance_id": "SI-CD-WSK",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "2739F",
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
    endpoints = {
        "1": "JD1",
        "2": "JD2",
        "3": "JR-1 &",
        "4": "JR-2 &",
        "5": "KZKK-2",
        "6": "KZKK-4",
        "7": "JD7",
        "8": "JD8",
    }
    slot_positions = {
        "7": (-18.0, 7.5),
        "8": (-18.0, 2.5),
        "1": (-18.0, -2.5),
        "2": (-18.0, -7.5),
        "6": (18.0, 7.5),
        "5": (18.0, 2.5),
        "4": (18.0, -2.5),
        "3": (18.0, -7.5),
    }
    texts = [
        {"text_id": "TK", "sheet_id": "S", "file_id": "F", "normalized_text": "K", "insert_x": 100.0, "insert_y": 222.0},
        {"text_id": "TL", "sheet_id": "S", "file_id": "F", "normalized_text": "L", "insert_x": 106.0, "insert_y": 205.0},
        {"text_id": "TN", "sheet_id": "S", "file_id": "F", "normalized_text": "N", "insert_x": 106.0, "insert_y": 200.0},
    ]
    lines = []
    members = []
    for slot, (local_x, local_y) in slot_positions.items():
        world_x, world_y = 100.0 + local_x, 200.0 + local_y
        direction = -1.0 if local_x < 0.0 else 1.0
        far_x = world_x + direction * 12.0
        handle = f"HL-{slot}"
        lines.append(
            {
                "line_id": f"L-{slot}",
                "handle": handle,
                "sheet_id": "S",
                "file_id": "F",
                "start_x": world_x,
                "start_y": world_y,
                "end_x": far_x,
                "end_y": world_y,
            }
        )
        members.append(
            {
                "member_type": "SOURCE_LINE",
                "source_handle": handle,
                "electrical_network_id": f"NET-{slot}",
            }
        )
        texts.append(
            {
                "text_id": f"TE-{slot}",
                "sheet_id": "S",
                "file_id": "F",
                "normalized_text": endpoints[slot],
                "insert_x": far_x,
                "insert_y": world_y,
            }
        )

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )
    by_identity = {row["component_port_identity"]: row for row in rows}
    assert set(by_identity) == {f"K-{slot}" for slot in range(1, 9)}
    for slot in range(1, 9):
        row = by_identity[f"K-{slot}"]
        assert row["component_mapping_external_endpoints"] == [
            endpoints[str(slot)].removesuffix(" &")
        ]
        assert row["external_network_ids"] == [f"NET-{slot}"]
        assert row["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
        assert row["internal_connectivity_inferred"] is False
        assert row["electrical_union_eligible"] is False
