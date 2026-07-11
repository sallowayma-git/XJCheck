from __future__ import annotations

import pandas as pd

from dwg_audit.audit.electrical_networks import build_asserted_electrical_network_frames
from dwg_audit.audit.electrical_networks import build_network_endpoint_witness_frame
from dwg_audit.audit.electrical_networks import build_network_validation_suspicions
from dwg_audit.audit.electrical_networks import build_network_boundary_frame
from dwg_audit.audit.electrical_networks import build_legacy_pair_network_equivalence_frame
from dwg_audit.domain.models import LineGroup, Pair
from types import SimpleNamespace


def test_only_asserted_decisions_can_union_components() -> None:
    components = pd.DataFrame(
        [
            {"geometry_component_id": "C1", "sheet_id": "S", "node_ids": ["N1", "N2"], "edge_ids": ["E1"], "source_line_ids": ["L1"], "open_node_ids": ["N1", "N2"], "junction_node_ids": [], "bbox": [0, 0, 1, 0], "total_length": 1.0},
            {"geometry_component_id": "C2", "sheet_id": "S", "node_ids": ["N3", "N4"], "edge_ids": ["E2"], "source_line_ids": ["L2"], "open_node_ids": ["N3", "N4"], "junction_node_ids": [], "bbox": [2, 0, 3, 0], "total_length": 1.0},
            {"geometry_component_id": "C3", "sheet_id": "S", "node_ids": ["N5", "N6"], "edge_ids": ["E3"], "source_line_ids": ["L3"], "open_node_ids": ["N5", "N6"], "junction_node_ids": [], "bbox": [4, 0, 5, 0], "total_length": 1.0},
        ]
    )
    decisions = pd.DataFrame(
        [
            {"topology_decision_id": "D1", "sheet_id": "S", "decision_kind": "overlap", "decision_state": "ASSERTED", "component_a_id": "C1", "component_b_id": "C2", "reason_codes": ["asserted"], "union_eligible": True, "requires_review": False},
            {"topology_decision_id": "D2", "sheet_id": "S", "decision_kind": "inline_span", "decision_state": "POSSIBLE", "component_a_id": "C2", "component_b_id": "C3", "reason_codes": ["possible"], "union_eligible": False, "requires_review": True},
        ]
    )

    edges = pd.DataFrame(
        [
            {"geometry_edge_id": "E1", "start_node_id": "N1", "end_node_id": "N2", "source_line_id": "L1", "length": 1.0},
            {"geometry_edge_id": "E2", "start_node_id": "N3", "end_node_id": "N4", "source_line_id": "L2", "length": 1.0},
            {"geometry_edge_id": "E3", "start_node_id": "N5", "end_node_id": "N6", "source_line_id": "L3", "length": 1.0},
        ]
    )
    networks, members, opens, boundaries, applications, summary = (
        build_asserted_electrical_network_frames(
            pd.DataFrame(
                [
                    {"geometry_node_id": f"N{index}", "coord": [index, 0.0], "source_line_ids": [f"L{(index + 1) // 2}"]}
                    for index in range(1, 7)
                ]
            ),
            edges,
            components,
            decisions,
            source_handle_by_line={"L1": "H1", "L2": "H2", "L3": "H3"},
        )
    )

    assert len(networks) == 2
    merged = networks.loc[networks["geometry_component_ids"].map(len) == 2].iloc[0]
    assert merged["geometry_component_ids"] == ["C1", "C2"]
    assert applications.set_index("topology_decision_id").loc["D1", "applied"]
    assert not applications.set_index("topology_decision_id").loc["D2", "applied"]
    assert len(boundaries) == 1
    assert boundaries.iloc[0]["decision_state"] == "POSSIBLE"
    assert summary["asserted_union_application_count"] == 1
    assert summary["non_asserted_union_application_count"] == 0
    assert len(members) == 6
    assert len(opens) == 6
    assert set(members.loc[members["member_type"] == "SOURCE_LINE", "source_handle"]) == {"H1", "H2", "H3"}
    assert opens["coord"].map(len).eq(2).all()
    assert opens["source_handles"].map(len).eq(1).all()

    witnesses, witness_summary = build_network_endpoint_witness_frame(
        networks,
        opens,
        edges,
        source_handle_by_line={"L1": "H1", "L2": "H2", "L3": "H3"},
    )
    assert len(witnesses) == 6
    assert witnesses["resolved"].all()
    assert witnesses["source_handles"].map(len).eq(1).all()
    assert witness_summary["witness_completeness"] == 1.0


def test_single_open_endpoint_witness_falls_back_to_asserted_network_node() -> None:
    networks = pd.DataFrame(
        [
            {
                "electrical_network_id": "N",
                "sheet_id": "S",
                "geometry_edge_ids": ["E"],
                "node_ids": ["A", "B"],
                "junction_node_ids": [],
            }
        ]
    )
    opens = pd.DataFrame(
        [{"electrical_network_id": "N", "sheet_id": "S", "node_id": "A"}]
    )
    edges = pd.DataFrame(
        [
            {
                "geometry_edge_id": "E",
                "start_node_id": "A",
                "end_node_id": "B",
                "source_line_id": "L",
                "length": 2.0,
            }
        ]
    )

    witnesses, summary = build_network_endpoint_witness_frame(
        networks, opens, edges, source_handle_by_line={"L": "H"}
    )

    assert witnesses.iloc[0]["resolved"]
    assert witnesses.iloc[0]["target_node_id"] == "B"
    assert witnesses.iloc[0]["target_kind"] == "NETWORK_NODE"
    assert witnesses.iloc[0]["source_handles"] == ["H"]
    assert summary["witness_completeness"] == 1.0


def test_boundary_and_legacy_equivalence_are_shadow_only() -> None:
    opens = pd.DataFrame(
        [
            {
                "electrical_network_id": "N1",
                "sheet_id": "S",
                "node_id": "A",
                "coord": [0.0, 5.0],
                "source_handles": ["H1"],
            }
        ]
    )
    page = SimpleNamespace(sheet_id="S", audit_area_bbox=(0.0, 0.0, 10.0, 10.0))
    block = SimpleNamespace(sheet_id="S", block_id="B1", insert_x=0.5, insert_y=5.0)
    boundaries, boundary_summary = build_network_boundary_frame(
        opens, [page], [block]
    )

    assert boundaries.iloc[0]["drawing_boundary_state"] == "ASSERTED"
    assert boundaries.iloc[0]["symbol_boundary_state"] == "POSSIBLE"
    assert boundaries.iloc[0]["cross_page_interruption_state"] == "UNKNOWN"
    assert boundary_summary["drawing_asserted_count"] == 1

    pair = Pair("P1", "G1", "S", "F", "PC1", "101", "102", 0.9, "pass", "legacy")
    group = LineGroup("G1", "S", "F", 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, ["L1"], ["WIRE"])
    members = pd.DataFrame(
        [
            {
                "electrical_network_id": "N1",
                "member_type": "SOURCE_LINE",
                "member_id": "L1",
            }
        ]
    )
    equivalence, summary = build_legacy_pair_network_equivalence_frame(
        [pair], [group], members
    )

    assert equivalence.iloc[0]["equivalence_status"] == "UNIQUE_V2_NETWORK"
    assert not equivalence.iloc[0]["v2_changes_legacy_result"]
    assert summary["legacy_result_change_count"] == 0


def test_network_validator_reports_suspicion_without_mutating_network() -> None:
    networks = pd.DataFrame(
        [
            {
                "electrical_network_id": "N",
                "geometry_component_ids": ["C1", "C2"],
            }
        ]
    )
    boundaries = pd.DataFrame(
        [
            {
                "topology_decision_id": "P",
                "geometry_component_ids": ["C1", "C2"],
                "electrical_network_ids": ["N"],
            }
        ]
    )
    applications = pd.DataFrame(
        [
            {
                "topology_decision_id": "A",
                "decision_state": "ASSERTED",
                "union_eligible": True,
                "applied": True,
                "application_reason_code": "ASSERTED_COMPONENT_UNION",
                "component_a_id": "C1",
                "component_b_id": "C2",
            }
        ]
    )
    original = networks.copy(deep=True)

    suspicions, summary = build_network_validation_suspicions(
        networks, boundaries, applications
    )

    assert len(suspicions) == 1
    assert suspicions.iloc[0]["reason_code"] == "NON_ASSERTED_BOUNDARY_INSIDE_NETWORK"
    assert suspicions.iloc[0]["review_only"]
    assert summary["overmerge_suspicion_count"] == 1
    pd.testing.assert_frame_equal(networks, original)
