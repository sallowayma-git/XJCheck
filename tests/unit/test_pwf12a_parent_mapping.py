"""Contracts for the generalized PWF12a row mechanism and PWF105 ownership."""

from __future__ import annotations

import math

import ezdxf

from dwg_audit.audit.symbol_port_proposal import (
    apply_human_symbol_policy_to_proposal_row,
    build_instance_port_network_candidates,
    propose_ports_from_block,
)


PWF12A_FINGERPRINT = "b440ea59c6edcaa2edd135cbfd3ca4d54f80bb2ea554a9ec7af3eeba5a6be3d0"


def _transformer(rotation_deg: float, scale: float):
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    return transform


def _row_mechanism_proposal(
    *,
    fingerprint: str,
    file_id: str = "F",
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    decorative_x_offset: float = 0.0,
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_ROW_MECHANISM")
    transform = _transformer(rotation_deg, scale)
    circle_center = transform((2.5, 0.0))
    block.add_circle(circle_center, 1.0 * scale)
    for start, end in (((3.5, 0.0), (1.3, 0.0)), ((1.3, 0.0), (0.0, 0.0))):
        block.add_line(transform(start), transform(end))
    for left, right in (
        ((-0.5, 0.0), (0.5, 0.0)),
        (
            (1.95 + decorative_x_offset, 2.16),
            (2.95 + decorative_x_offset, 2.16),
        ),
    ):
        block.add_lwpolyline(
            [(*transform(left), 1.0), (*transform(right), 1.0)],
            format="xyb",
            close=True,
        )
    hatch = block.add_hatch(color=7)
    hatch.paths.add_polyline_path(
        [transform((2.3, 2.0)), transform((2.6, 2.0)), transform((2.45, 2.3))],
        is_closed=True,
    )
    proposal = propose_ports_from_block(
        block,
        definition_name="RENAMED_ROW_MECHANISM",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()
    proposal["file_id"] = file_id
    return proposal


def _two_row_parent_proposal(*, file_id: str = "F") -> dict:
    document = ezdxf.new()
    child = document.blocks.new("RENAMED_CHILD_MARKER")
    child.add_point((0.0, 0.0))
    block = document.blocks.new("RENAMED_PARENT")
    block.add_blockref(child.name, (0.0, 0.0))
    block.add_blockref(child.name, (0.0, -10.0))
    block.add_lwpolyline(
        [(-2.5, 5.0), (7.5, 5.0), (7.5, -15.0), (-2.5, -15.0)],
        close=True,
    )
    for x, y in ((0.0, 0.0), (2.5, 2.5), (0.0, -10.0), (2.5, -7.5)):
        block.add_lwpolyline(
            [(x - 0.5, y, 1.0), (x + 0.5, y, 1.0)],
            format="xyb",
            close=True,
        )
    proposal = propose_ports_from_block(
        block,
        definition_name=block.name,
        definition_fingerprint="unseen-two-row-parent",
        max_ports=4,
    ).to_dict()
    proposal["file_id"] = file_id
    return proposal


def test_row_mechanism_exact_and_rotated_scaled_unseen_emit_one_external_port() -> None:
    exact = _row_mechanism_proposal(fingerprint=PWF12A_FINGERPRINT)
    unseen = _row_mechanism_proposal(
        fingerprint="unseen-rotated-row-mechanism",
        rotation_deg=37.0,
        scale=1.8,
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert proposal["method"] == "single_row_contact_mechanism_v1"
        assert len(proposal["ports"]) == 1
        assert applied["family_id"] == "component.external_row_contact.v1"
        assert applied["matched_family_rule_id"] == "single-row-circle-contact-mechanism-v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_row_mechanism_same_counts_with_offset_decorative_contact_stays_review() -> None:
    proposal = _row_mechanism_proposal(
        fingerprint="unseen-offset-row-mechanism",
        decorative_x_offset=0.5,
    )
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied["matched_family_rule_id"] != "single-row-circle-contact-mechanism-v1"
    assert applied["family_id"] != "component.external_row_contact.v1"


def test_standalone_row_inherits_k_and_pin_6_for_its_same_side_network() -> None:
    proposal = _row_mechanism_proposal(fingerprint="unseen-standalone-row")
    instance = {
        "symbol_instance_id": "ROW",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "HC",
        "definition_name": proposal["definition_name"],
        "definition_fingerprint": proposal["definition_fingerprint"],
        "nested_path": "RENAMED_ROW_MECHANISM[HC]",
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
        {"text_id": "TK", "handle": "HK", "sheet_id": "S", "file_id": "F", "normalized_text": "K", "insert_x": 106.0, "insert_y": 207.0},
        {"text_id": "T6", "handle": "H6", "sheet_id": "S", "file_id": "F", "normalized_text": "6", "insert_x": 101.0, "insert_y": 201.0},
    ]
    lines = [
        {"line_id": "L6", "handle": "HL6", "sheet_id": "S", "file_id": "F", "start_x": 100.0, "start_y": 200.0, "end_x": 90.0, "end_y": 200.0}
    ]
    members = [
        {"member_type": "SOURCE_LINE", "source_handle": "HL6", "electrical_network_id": "NET-K6"}
    ]

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )

    assert len(rows) == 1
    assert rows[0]["component_port_identity"] == "K-6"
    assert rows[0]["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
    assert rows[0]["component_mapping_external_network_ids"] == ["NET-K6"]
    assert rows[0]["internal_connectivity_inferred"] is False
    assert rows[0]["electrical_union_eligible"] is False


def test_reviewed_parent_owns_nested_row_and_emits_only_two_a_prime_mappings() -> None:
    parent_proposal = _two_row_parent_proposal()
    child_proposal = _row_mechanism_proposal(fingerprint="unseen-nested-row")
    parent_matrix = [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [100, 200, 0, 1],
    ]
    parent = {
        "symbol_instance_id": "PARENT",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "HP",
        "definition_name": parent_proposal["definition_name"],
        "definition_fingerprint": parent_proposal["definition_fingerprint"],
        "nested_path": "RENAMED_PARENT[HP]",
        "transform_json": {"matrix44": parent_matrix},
    }
    child = {
        "symbol_instance_id": "CHILD",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "HC",
        "definition_name": child_proposal["definition_name"],
        "definition_fingerprint": child_proposal["definition_fingerprint"],
        "nested_path": "RENAMED_PARENT[HP]/RENAMED_ROW_MECHANISM[HC]",
        "transform_json": {"chain": [{"matrix44": parent_matrix}, {"matrix44": parent_matrix}]},
    }
    texts = [
        {"text_id": "TA", "handle": "HA", "sheet_id": "S", "file_id": "F", "normalized_text": "A'", "insert_x": 102.5, "insert_y": 205.0},
        {"text_id": "T1", "handle": "H1", "sheet_id": "S", "file_id": "F", "normalized_text": "1", "insert_x": 99.0, "insert_y": 201.0},
        {"text_id": "T2", "handle": "H2", "sheet_id": "S", "file_id": "F", "normalized_text": "2", "insert_x": 99.0, "insert_y": 191.0},
    ]
    lines = [
        {"line_id": "LU", "handle": "HLU", "sheet_id": "S", "file_id": "F", "start_x": 100.0, "start_y": 200.0, "end_x": 90.0, "end_y": 200.0},
        {"line_id": "LL", "handle": "HLL", "sheet_id": "S", "file_id": "F", "start_x": 100.0, "start_y": 190.0, "end_x": 90.0, "end_y": 190.0},
    ]
    members = [
        {"member_type": "SOURCE_LINE", "source_handle": "HLU", "electrical_network_id": "NET-UPPER"},
        {"member_type": "SOURCE_LINE", "source_handle": "HLL", "electrical_network_id": "NET-LOWER"},
    ]

    rows = build_instance_port_network_candidates(
        [parent_proposal, child_proposal],
        [parent, child],
        texts,
        lines,
        members,
    )

    assert {row["component_port_identity"] for row in rows} == {"A'-1", "A'-2"}
    assert {tuple(row["external_network_ids"]) for row in rows} == {
        ("NET-UPPER",),
        ("NET-LOWER",),
    }
    assert all(row["symbol_instance_handle"] == "HP" for row in rows)
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)
