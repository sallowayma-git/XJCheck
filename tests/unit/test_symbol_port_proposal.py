from __future__ import annotations

import ezdxf

from dwg_audit.audit.symbol_library_review import load_symbol_review_document
from dwg_audit.audit.symbol_port_proposal import apply_proposals_to_review_document
from dwg_audit.audit.symbol_port_proposal import apply_human_symbol_policy_to_proposal_row
from dwg_audit.audit.symbol_port_proposal import build_instance_port_network_candidates
from dwg_audit.audit.symbol_port_proposal import classify_definition_family
from dwg_audit.audit.symbol_port_proposal import extract_block_shape_features
from dwg_audit.audit.symbol_port_proposal import propose_ports_from_block
from dwg_audit.audit.symbol_port_proposal import propose_ports_from_segments
from dwg_audit.audit.symbol_port_proposal import human_symbol_port_policy
from dwg_audit.audit.symbol_port_proposal import is_high_confidence_terminal_geometry
from dwg_audit.audit.symbol_port_proposal import summarize_instance_port_network_candidates
from dwg_audit.audit.symbol_port_proposal import write_machine_proposed_review_pack


def test_horizontal_series_symbol_gets_two_end_ports() -> None:
    segments = [
        ((-0.5, 0.0), (0.0, 0.0)),
        ((0.0, 0.0), (2.5, 0.0)),
        ((2.5, 0.0), (3.0, 0.0)),
        ((0.75, 0.0), (1.75, 0.0)),
    ]
    ports, summary, notes = propose_ports_from_segments(
        segments, source_id="machine_geometry_proposal:SYM", max_ports=4
    )
    assert len(ports) == 2
    xs = sorted(port.local_position[0] for port in ports)
    assert xs[0] <= -0.4
    assert xs[1] >= 2.9
    assert summary["principal_axis"] == "horizontal"
    assert ports[0].to_review_port()["annotation_status"] == "MACHINE_PROPOSED"


def test_repeated_full_width_rows_win_over_decorative_free_endpoints() -> None:
    segments = [
        ((0.0, 0.0), (8.0, 0.0)),
        ((8.0, 0.0), (20.0, 0.0)),
        ((0.0, 10.0), (8.0, 10.0)),
        ((8.0, 10.0), (20.0, 10.0)),
        ((4.0, -3.0), (10.0, 0.0)),
        ((4.0, 7.0), (10.0, 10.0)),
    ]

    ports, summary, notes = propose_ports_from_segments(
        segments,
        source_id="machine_geometry_proposal:FOUR_PORT",
        max_ports=4,
    )

    assert [port.local_position[:2] for port in ports] == [
        (0.0, 0.0),
        (20.0, 0.0),
        (0.0, 10.0),
        (20.0, 10.0),
    ]
    assert summary["selected_port_count"] == 4
    assert all(
        "REPEATED_FULL_WIDTH_ROW_PORT" in port.evidence_codes for port in ports
    )
    assert any("paired full-width row" in note for note in notes)


def test_two_point_closed_bulge_polylines_do_not_become_fake_ports() -> None:
    document = ezdxf.new()
    block = document.blocks.new(name="FOUR_PORT_WITH_CIRCLES")
    for y in (0.0, 10.0):
        block.add_line((0.0, y), (20.0, y))
        block.add_lwpolyline(
            [(-0.5, y, 1.0), (0.5, y, 1.0)],
            format="xyb",
            close=True,
        )
        block.add_lwpolyline(
            [(19.5, y, 1.0), (20.5, y, 1.0)],
            format="xyb",
            close=True,
        )

    proposal = propose_ports_from_block(
        block,
        definition_name="FOUR_PORT_WITH_CIRCLES",
        source_dxf="fixture.dxf",
        max_ports=6,
    )

    assert [port.local_position[:2] for port in proposal.ports] == [
        (0.0, 0.0),
        (20.0, 0.0),
        (0.0, 10.0),
        (20.0, 10.0),
    ]


def test_instance_ports_bind_explicit_labels_and_external_networks_only() -> None:
    proposal = {
        "file_id": "F0007",
        "definition_name": "FOUR_PORT",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [20.0, 0.0, 0.0]},
            {"port_id": "MP3", "local_position": [0.0, 10.0, 0.0]},
            {"port_id": "MP4", "local_position": [20.0, 10.0, 0.0]},
        ],
    }
    instance = {
        "symbol_instance_id": "SI-1",
        "project_id": "P001",
        "sheet_id": "S0007",
        "file_id": "F0007",
        "entity_handle": "B1",
        "definition_name": "FOUR_PORT",
        "definition_fingerprint": "fp1",
        "transform_json": {
            "matrix44": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [95.0, 65.0, 0.0, 1.0],
            ]
        },
    }
    texts = [
        {
            "text_id": f"T{label}",
            "handle": f"TH{label}",
            "sheet_id": "S0007",
            "file_id": "F0007",
            "text": label,
            "normalized_text": label,
            "insert_x": x - 0.6,
            "insert_y": y + 1.0,
        }
        for label, x, y in (
            ("1", 95.0, 65.0),
            ("2", 115.0, 65.0),
            ("3", 95.0, 75.0),
            ("4", 115.0, 75.0),
        )
    ]
    lines = [
        {
            "line_id": f"L{label}",
            "handle": f"LH{label}",
            "sheet_id": "S0007",
            "file_id": "F0007",
            "start_x": x,
            "start_y": y,
            "end_x": x + (-10.0 if x == 95.0 else 10.0),
            "end_y": y,
        }
        for label, x, y in (
            ("1", 95.0, 65.0),
            ("2", 115.0, 65.0),
            ("3", 95.0, 75.0),
            ("4", 115.0, 75.0),
        )
    ]
    members = [
        {
            "electrical_network_id": f"EN{label}",
            "member_type": "SOURCE_LINE",
            "source_handle": f"LH{label}",
        }
        for label in ("1", "2", "3", "4")
    ]

    candidates = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )

    assert [row["explicit_port_label"] for row in candidates] == ["1", "2", "3", "4"]
    assert all(row["status"] == "MEASURED_EXTERNAL_ATTACHMENT" for row in candidates)
    assert all(row["external_network_ids"] for row in candidates)
    assert all(row["internal_connectivity_inferred"] is False for row in candidates)
    assert all(row["dynamic_contact_state"] == "DEFER" for row in candidates)
    assert all(row["electrical_union_eligible"] is False for row in candidates)


def test_instance_rejects_same_name_proposal_with_different_fingerprint() -> None:
    proposal = {
        "file_id": "F0007",
        "definition_name": "SAME_NAME",
        "definition_fingerprint": "proposal-fingerprint",
        "ports": [{"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]}],
    }
    instance = {
        "symbol_instance_id": "SI-mismatch",
        "project_id": "P001",
        "sheet_id": "S0007",
        "file_id": "F0007",
        "entity_handle": "B-mismatch",
        "definition_name": "SAME_NAME",
        "definition_fingerprint": "instance-fingerprint",
        "transform_json": {
            "matrix44": [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ]
        },
    }

    candidates = build_instance_port_network_candidates(
        [proposal], [instance], [], [], []
    )

    assert len(candidates) == 1
    assert candidates[0]["status"] == "REJECTED_FINGERPRINT_MISMATCH"
    assert candidates[0]["binding_status"] == "REJECTED_FINGERPRINT_MISMATCH"
    assert candidates[0]["proposal_fingerprints"] == ["proposal-fingerprint"]
    assert candidates[0]["electrical_union_eligible"] is False


def test_apply_proposals_keeps_document_non_authoritative() -> None:
    document = {
        "schema_version": "symbol-dependency-library-v1",
        "review_workflow": {
            "workflow_version": "symbol-library-review-v1",
            "document_status": "PENDING_HUMAN_REVIEW",
            "notes": None,
        },
        "geometry_definitions": [],
        "symbols": [
            {
                "backlog_rank": 1,
                "review_reason_codes": ["UNREGISTERED_DEFINITION_REVIEW_REQUIRED"],
                "family": "SYM",
                "version": "inventory-v1",
                "fingerprint": "fp1",
                "definition_names": ["SYM"],
                "geometry_dependencies": [],
                "symbol_dependencies": [],
                "ports": [],
                "internal_connectivity_groups": [],
                "aliases": [],
                "sources": [
                    {
                        "source_id": "inventory:SYM:fp1",
                        "source_kind": "project_symbol_inventory",
                        "locator": "SYM",
                        "project_id": "P001",
                        "held_out": False,
                    }
                ],
                "annotation_status": "PENDING_HUMAN_REVIEW",
                "registry_status": "UNKNOWN",
                "critical_issue_eligible": False,
                "review": {
                    "status": "PENDING_HUMAN_REVIEW",
                    "reviewer": None,
                    "reviewed_at": None,
                    "evidence_source_ids": [],
                    "notes": None,
                },
            }
        ],
    }
    ports, _, _ = propose_ports_from_segments(
        [((-1.0, 0.0), (1.0, 0.0))],
        source_id="machine_geometry_proposal:SYM",
        max_ports=2,
    )
    from dwg_audit.audit.symbol_port_proposal import SymbolPortProposal

    proposal = SymbolPortProposal(
        definition_name="SYM",
        definition_fingerprint="fp1",
        source_dxf="x.dxf",
        ports=tuple(ports),
        method="free_endpoint_extremes_v1",
        status="PROPOSED",
    )
    drafted = apply_proposals_to_review_document(document, {"fp1": proposal})
    result = load_symbol_review_document(drafted)
    assert result.validation.valid
    assert not result.validation.promotion_ready
    symbol = result.library.symbols[0]
    assert symbol.annotation_status.value == "MACHINE_PROPOSED"
    assert symbol.registry_status.value == "UNKNOWN"
    assert symbol.critical_issue_eligible is False
    assert len(symbol.ports) == 2
    assert all(port.annotation_status.value == "MACHINE_PROPOSED" for port in symbol.ports)
    assert symbol.internal_connectivity_groups[0].state.value == "POSSIBLE"


def test_human_non_connective_policies_are_fingerprint_bound() -> None:
    ignored = apply_human_symbol_policy_to_proposal_row(
        {
            "definition_name": "SYMB2_M_PWF229",
            "definition_fingerprint": "4843ab10418b48bf18e403125a6c80ba490c88d0987c42f712b5c24c8503dc61",
            "ports": [{"port_id": "MP1"}, {"port_id": "MP2"}],
            "status": "PROPOSED",
        }
    )
    unrelated = apply_human_symbol_policy_to_proposal_row(
        {
            "definition_name": "SYMB2_M_PWF229",
            "definition_fingerprint": "different-geometry",
            "ports": [{"port_id": "MP1"}, {"port_id": "MP2"}],
            "status": "PROPOSED",
        }
    )

    assert ignored["ports"] == []
    assert ignored["status"] == "HUMAN_ADJUDICATED_NON_CONNECTIVE"
    assert ignored["electrical_union_eligible"] is False
    assert len(unrelated["ports"]) == 2
    assert "human_adjudication_mode" not in unrelated


def test_human_klp_policy_keeps_external_ports_but_suppresses_series_group() -> None:
    document = {
        "schema_version": "symbol-dependency-library-v1",
        "review_workflow": {
            "workflow_version": "symbol-library-review-v1",
            "document_status": "PENDING_HUMAN_REVIEW",
            "notes": None,
        },
        "geometry_definitions": [],
        "symbols": [
            {
                "backlog_rank": 1,
                "review_reason_codes": ["UNREGISTERED_DEFINITION_REVIEW_REQUIRED"],
                "family": "SYMB2_M_PWF224",
                "version": "inventory-v1",
                "fingerprint": "61255c39029679e1151d9d4e8fe3884a538ea97638fa6f605d8a1d17713d8dc2",
                "definition_names": ["SYMB2_M_PWF224"],
                "geometry_dependencies": [], "symbol_dependencies": [], "ports": [],
                "internal_connectivity_groups": [], "aliases": [],
                "sources": [], "annotation_status": "PENDING_HUMAN_REVIEW",
                "registry_status": "UNKNOWN", "critical_issue_eligible": False,
                "review": {"status": "PENDING_HUMAN_REVIEW", "reviewer": None,
                           "reviewed_at": None, "evidence_source_ids": [], "notes": None},
            }
        ],
    }
    ports, _, _ = propose_ports_from_segments(
        [((0.0, 0.0), (10.0, 0.0))],
        source_id="machine_geometry_proposal:SYMB2_M_PWF224",
        max_ports=2,
    )
    from dwg_audit.audit.symbol_port_proposal import SymbolPortProposal
    proposal = SymbolPortProposal(
        definition_name="SYMB2_M_PWF224",
        definition_fingerprint="61255c39029679e1151d9d4e8fe3884a538ea97638fa6f605d8a1d17713d8dc2",
        source_dxf="fixture.dxf", ports=tuple(ports), method="fixture", status="PROPOSED",
    )

    drafted = apply_proposals_to_review_document(document, {proposal.definition_fingerprint: proposal})

    assert len(drafted["symbols"][0]["ports"]) == 2
    assert drafted["symbols"][0]["internal_connectivity_groups"] == []


def test_labelled_terminal_binds_designator_without_internal_union() -> None:
    proposal = {
        "file_id": "F0005", "definition_name": "SYMB2_M_PWF231",
        "ports": [
            {"port_id": "MP1", "local_position": [-0.5, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [5.5, 0.0, 0.0]},
        ],
    }
    instance = {
        "symbol_instance_id": "SI-terminal", "project_id": "P001", "sheet_id": "S0005", "file_id": "F0005",
        "entity_handle": "112CE", "definition_name": "SYMB2_M_PWF231",
        "definition_fingerprint": "2ede8a4fcebd958209b99a25e477726c0b55f86b32d00650130a89acad0bf89c",
        "transform_json": {"matrix44": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [77.5, 220.0, 0, 1]]},
    }
    texts = [{"text_id": "T1", "handle": "TX1", "sheet_id": "S0005", "file_id": "F0005",
              "text": "1ID1", "normalized_text": "1ID1", "insert_x": 80.0, "insert_y": 222.0}]
    lines = [
        {"line_id": "L-left", "handle": "LH-left", "sheet_id": "S0005", "file_id": "F0005",
         "start_x": 77.0, "start_y": 220.0, "end_x": 60.0, "end_y": 220.0},
        {"line_id": "L-right", "handle": "LH-right", "sheet_id": "S0005", "file_id": "F0005",
         "start_x": 83.0, "start_y": 220.0, "end_x": 100.0, "end_y": 220.0},
    ]
    members = [
        {"electrical_network_id": "EN-left", "member_type": "SOURCE_LINE", "source_handle": "LH-left"},
        {"electrical_network_id": "EN-right", "member_type": "SOURCE_LINE", "source_handle": "LH-right"},
    ]

    candidates = build_instance_port_network_candidates([proposal], [instance], texts, lines, members)

    assert len(candidates) == 2
    assert {row["terminal_designator"] for row in candidates} == {"1ID1"}
    assert all(row["status"] == "MEASURED_TERMINAL_ATTACHMENT" for row in candidates)
    assert all(row["internal_connectivity_inferred"] is False for row in candidates)


def test_letter_first_terminal_designator_is_bound_for_pwf233() -> None:
    proposal = {
        "file_id": "F0007", "definition_name": "SYMB2_M_PWF233",
        "ports": [{"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]}],
    }
    instance = {
        "symbol_instance_id": "SI-zd1", "project_id": "P001", "sheet_id": "S0007", "file_id": "F0007",
        "entity_handle": "192A2", "definition_name": "SYMB2_M_PWF233",
        "definition_fingerprint": "e2e32701027b07d3f74b5941716ca9328daf926abad92f0b4b5f2081b3f52fe2",
        "transform_json": {"matrix44": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [50.0, 272.5, 0, 1]]},
    }
    texts = [{"text_id": "TZD1", "handle": "TXZD1", "sheet_id": "S0007", "file_id": "F0007",
              "text": "ZD1", "normalized_text": "ZD1", "insert_x": 50.5, "insert_y": 274.0}]
    lines = [{"line_id": "LZD1", "handle": "LHZD1", "sheet_id": "S0007", "file_id": "F0007",
              "start_x": 50.0, "start_y": 272.5, "end_x": 70.0, "end_y": 272.5}]
    members = [{"electrical_network_id": "EN-ZD1", "member_type": "SOURCE_LINE", "source_handle": "LHZD1"}]

    candidates = build_instance_port_network_candidates([proposal], [instance], texts, lines, members)

    assert candidates[0]["terminal_designator"] == "ZD1"
    assert candidates[0]["status"] == "MEASURED_TERMINAL_ATTACHMENT"
    assert candidates[0]["internal_connectivity_inferred"] is False


def test_pwf243_uses_the_same_labelled_terminal_policy() -> None:
    policy = human_symbol_port_policy(
        "b3115ea33fe4e1b57d4cfa6394c3125c42f5776b589f8297b4053cf3d7a7a073"
    )

    assert policy is not None
    assert policy["mode"] == "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY"


def test_fjl_strip_policy_preserves_ports_but_forbids_internal_connectivity() -> None:
    policy = human_symbol_port_policy(
        "69f5c09b9bfe7e7c3c9db62eaa577a51b98801ec22bb366b8d5d2513ae1b247b"
    )

    assert policy is not None
    assert policy["mode"] == "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY"


def test_pwf196_open_switch_policy_ignores_all_electrical_ports() -> None:
    policy = human_symbol_port_policy(
        "634756a0bafe88dd763d740c97fe13dbbd65921586360b6f96a87d2dc2a408f4"
    )

    assert policy is not None
    assert policy["mode"] == "IGNORE_ELECTRICAL"


def test_pwf206_functional_symbol_is_ignored_for_wire_connectivity() -> None:
    policy = human_symbol_port_policy(
        "b37828da29525da55540cc801a451c80b23b3b44b19cd00b7680ddfe1771f746"
    )

    assert policy is not None
    assert policy["mode"] == "IGNORE_ELECTRICAL"


def test_pwf208_left_equipment_graphic_is_ignored_by_exact_fingerprint() -> None:
    policy = human_symbol_port_policy(
        "cfe71411f229bb03fbcff9605b5b3dc0ace82f26b83a4d53fee308559e04412d"
    )

    assert policy is not None
    assert policy["mode"] == "IGNORE_ELECTRICAL"


def test_pwf210_non_semantic_placeholder_is_ignored() -> None:
    policy = human_symbol_port_policy(
        "ef9845390ad82463e1efac6f04551d65d189a6d9a311ce8c2b1398021e70c7cc"
    )

    assert policy is not None
    assert policy["mode"] == "IGNORE_ELECTRICAL"


def test_open_switch_geometry_generalizes_ignore_across_fingerprints_and_scale() -> None:
    proposal = {
        "definition_name": "UNSEEN_OPEN_SWITCH",
        "definition_fingerprint": "new-fingerprint-not-in-human-table",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [22.5, 0.0, 0.0]},
        ],
        "status": "PROPOSED",
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [],
                "circle_radii": [],
                "primitive_count": 6,
                "primitive_histogram": {"LINE": 4, "LWPOLYLINE": 2},
                "entity_histogram": {"LINE": 4, "LWPOLYLINE": 2},
                "text_count": 0,
                "width": 24.5,
                "height": 3.75,
            }
        },
    }

    classified = classify_definition_family(proposal)
    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert classified["family_id"] == "switch.open.v1"
    assert classified["family_evidence_source"] == "MACHINE_GEOMETRY_RULE"
    assert classified["exact_human_member"] is False
    assert applied["status"] == "GEOMETRY_FAMILY_NON_CONNECTIVE"
    assert applied["ports"] == []
    assert applied["suppressed_by_policy"] is True
    assert applied["decision_reason_codes"] == ["GEOMETRY_IGNORE_FAMILY_MATCH"]
    assert applied["electrical_union_eligible"] is False


def test_confirmed_line_break_geometry_generalizes_without_fingerprint() -> None:
    proposal = {
        "definition_name": "REDRAWN_LINE_BREAK",
        "definition_fingerprint": "another-new-fingerprint",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [10.0, 0.0, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [1.25, 1.25, 1.25, 1.25],
                "circle_radii": [],
                "primitive_count": 6,
                "primitive_histogram": {"ARC": 4, "LWPOLYLINE": 2},
                "entity_histogram": {"ARC": 4, "LWPOLYLINE": 2},
                "text_count": 0,
                "width": 12.0,
                "height": 1.25,
            }
        },
    }

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] == "line_break.non_connective.v1"
    assert applied["status"] == "GEOMETRY_FAMILY_NON_CONNECTIVE"
    assert applied["allow_port_emission"] is False


def test_near_open_switch_geometry_stays_review_only_when_model_is_incomplete() -> None:
    proposal = {
        "definition_name": "ELONGATED_UNKNOWN",
        "definition_fingerprint": "unknown-fingerprint",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [12.0, 0.0, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [],
                "circle_radii": [],
                "primitive_count": 4,
                "primitive_histogram": {"LINE": 2, "LWPOLYLINE": 2},
                "entity_histogram": {"LINE": 2, "LWPOLYLINE": 2},
                "text_count": 0,
                "width": 12.0,
                "height": 1.875,
            }
        },
    }

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] == "switch.open.candidate.v1"
    assert applied["classifier_status"] == "REVIEW_REQUIRED"
    assert applied["suppressed_by_policy"] is False
    assert len(applied["ports"]) == 2


def test_external_round_end_component_is_not_absorbed_by_ignore_models() -> None:
    proposal = {
        "definition_name": "UNSEEN_EXTERNAL_TWO_PORT",
        "definition_fingerprint": "unseen-external",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [10.0, 0.0, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [],
                "circle_radii": [0.625, 0.625],
                "primitive_count": 8,
                "primitive_histogram": {"CIRCLE": 2, "LINE": 4, "LWPOLYLINE": 2},
                "entity_histogram": {"CIRCLE": 2, "LINE": 4, "LWPOLYLINE": 2},
                "text_count": 0,
                "width": 11.0,
                "height": 1.25,
            }
        },
    }

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] == "component.external_strip_two_port.v1"
    assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
    assert applied["suppressed_by_policy"] is False
    assert len(applied["ports"]) == 2


def test_compact_terminal_geometry_is_high_confidence_but_tall_device_is_not() -> None:
    compact = {
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [1.25, 1.25],
                "primitive_count": 10,
                "text_count": 0,
                "width": 5.0,
                "height": 5.0,
            },
        }
    }
    tall = {
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [1.875, 1.875],
                "primitive_count": 7,
                "text_count": 0,
                "width": 1.75,
                "height": 12.5,
            },
        }
    }

    assert is_high_confidence_terminal_geometry(compact)
    assert not is_high_confidence_terminal_geometry(tall)


def test_terminal_shape_features_are_extracted_from_real_block_geometry() -> None:
    document = ezdxf.new()
    block = document.blocks.new(name="UNSEEN_TERMINAL_VARIANT")
    block.add_arc((0.0, 0.0), 1.25, 90.0, 270.0)
    block.add_arc((0.0, 0.0), 1.25, 270.0, 90.0)
    block.add_line((-3.0, 0.0), (-1.25, 0.0))
    block.add_line((1.25, 0.0), (3.0, 0.0))

    proposal = propose_ports_from_block(
        block,
        definition_name="UNSEEN_TERMINAL_VARIANT",
        source_dxf="fixture.dxf",
    )

    assert extract_block_shape_features(block) == proposal.geometry_summary["shape_features"]
    assert proposal.geometry_summary["shape_features"]["arc_radii"] == [1.25, 1.25]
    assert is_high_confidence_terminal_geometry(proposal.to_dict())


def test_similar_primitive_count_without_arc_body_is_not_a_terminal() -> None:
    proposal = {
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [],
                "primitive_count": 6,
                "text_count": 0,
                "width": 5.0,
                "height": 5.0,
            }
        }
    }

    assert not is_high_confidence_terminal_geometry(proposal)


def test_generic_terminal_requires_unique_label_and_wire_evidence() -> None:
    proposal = {
        "file_id": "F-new",
        "definition_name": "UNSEEN_TERMINAL",
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [1.25, 1.25],
                "primitive_count": 4,
                "text_count": 0,
                "width": 6.0,
                "height": 2.5,
            }
        },
        "ports": [{"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]}],
    }
    instance = {
        "symbol_instance_id": "SI-new",
        "project_id": "P-new",
        "sheet_id": "S-new",
        "file_id": "F-new",
        "entity_handle": "B-new",
        "definition_name": "UNSEEN_TERMINAL",
        "definition_fingerprint": "unreviewed-fingerprint",
        "transform_json": {
            "matrix44": [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [10, 20, 0, 1],
            ]
        },
    }
    label = {
        "text_id": "T-new",
        "handle": "HT-new",
        "sheet_id": "S-new",
        "file_id": "F-new",
        "normalized_text": "1QD9",
        "insert_x": 10.0,
        "insert_y": 22.0,
    }
    line = {
        "line_id": "L-new",
        "handle": "HL-new",
        "sheet_id": "S-new",
        "file_id": "F-new",
        "start_x": 10.0,
        "start_y": 20.0,
        "end_x": 20.0,
        "end_y": 20.0,
    }

    complete = build_instance_port_network_candidates(
        [proposal], [instance], [label], [line], []
    )[0]
    label_only = build_instance_port_network_candidates(
        [proposal], [instance], [label], [], []
    )[0]
    wire_only = build_instance_port_network_candidates(
        [proposal], [instance], [], [line], []
    )[0]
    geometry_only = build_instance_port_network_candidates(
        [proposal], [instance], [], [], []
    )[0]

    assert complete["status"] == "MEASURED_TERMINAL_ATTACHMENT"
    assert complete["terminal_independent_evidence_complete"] is True
    assert label_only["status"] == "TERMINAL_LABEL_ONLY_REVIEW"
    assert wire_only["status"] == "TERMINAL_WIRE_ONLY_REVIEW"
    assert geometry_only["status"] == "TERMINAL_GEOMETRY_ONLY_REVIEW"
    assert all(
        row["electrical_union_eligible"] is False
        for row in (complete, label_only, wire_only, geometry_only)
    )


def test_near_tied_terminal_designators_are_not_broadcast_to_ports() -> None:
    proposal = {
        "file_id": "F-ambiguous",
        "definition_name": "UNSEEN_TERMINAL",
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [1.25, 1.25],
                "primitive_count": 4,
                "text_count": 0,
                "width": 6.0,
                "height": 2.5,
            }
        },
        "ports": [{"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]}],
    }
    instance = {
        "symbol_instance_id": "SI-ambiguous",
        "project_id": "P-new",
        "sheet_id": "S-new",
        "file_id": "F-ambiguous",
        "entity_handle": "B-ambiguous",
        "definition_name": "UNSEEN_TERMINAL",
        "definition_fingerprint": "unreviewed-fingerprint",
        "transform_json": {
            "matrix44": [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [10, 20, 0, 1],
            ]
        },
    }
    texts = [
        {"text_id": "T1", "handle": "H1", "sheet_id": "S-new", "file_id": "F-ambiguous", "normalized_text": "1QD1", "insert_x": 10.0, "insert_y": 22.0},
        {"text_id": "T2", "handle": "H2", "sheet_id": "S-new", "file_id": "F-ambiguous", "normalized_text": "1QD2", "insert_x": 10.0, "insert_y": 22.25},
    ]
    lines = [
        {"line_id": "L1", "handle": "HL1", "sheet_id": "S-new", "file_id": "F-ambiguous", "start_x": 10.0, "start_y": 20.0, "end_x": 20.0, "end_y": 20.0}
    ]

    candidate = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, []
    )[0]

    assert candidate["status"] == "TERMINAL_BINDING_AMBIGUOUS"
    assert candidate["terminal_designator"] is None
    assert candidate["terminal_label_ambiguous"] is True
    assert [item["value"] for item in candidate["terminal_label_candidates"]] == [
        "1QD1",
        "1QD2",
    ]


def test_scaled_rotated_terminal_uses_relative_tolerance_and_outward_alignment() -> None:
    proposal = {
        "file_id": "F-rotated",
        "definition_name": "ROTATED_TERMINAL",
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [1.25, 1.25],
                "primitive_count": 4,
                "text_count": 0,
                "width": 6.0,
                "height": 2.5,
            }
        },
        "ports": [
            {
                "port_id": "MP1",
                "local_position": [0.0, 0.0, 0.0],
                "outward_direction": [1.0, 0.0, 0.0],
            }
        ],
    }
    instance = {
        "symbol_instance_id": "SI-rotated",
        "project_id": "P-new",
        "sheet_id": "S-rotated",
        "file_id": "F-rotated",
        "entity_handle": "B-rotated",
        "definition_name": "ROTATED_TERMINAL",
        "definition_fingerprint": "unreviewed-fingerprint",
        "transform_json": {
            "matrix44": [
                [0, 2, 0, 0],
                [-2, 0, 0, 0],
                [0, 0, 1, 0],
                [10, 20, 0, 1],
            ]
        },
    }
    texts = [
        {"text_id": "T-rotated", "handle": "HT-rotated", "sheet_id": "S-rotated", "file_id": "F-rotated", "normalized_text": "1QD9", "insert_x": 10.0, "insert_y": 22.0}
    ]
    outward_line = [
        {"line_id": "L-out", "handle": "HL-out", "sheet_id": "S-rotated", "file_id": "F-rotated", "start_x": 10.0, "start_y": 20.15, "end_x": 10.0, "end_y": 30.0}
    ]
    inward_line = [
        {"line_id": "L-in", "handle": "HL-in", "sheet_id": "S-rotated", "file_id": "F-rotated", "start_x": 10.0, "start_y": 20.0, "end_x": 10.0, "end_y": 10.0}
    ]

    accepted = build_instance_port_network_candidates(
        [proposal], [instance], texts, outward_line, []
    )[0]
    rejected = build_instance_port_network_candidates(
        [proposal], [instance], texts, inward_line, []
    )[0]

    assert accepted["status"] == "MEASURED_TERMINAL_ATTACHMENT"
    assert accepted["effective_endpoint_tolerance"] == 0.2
    assert "OUTWARD_LINE_ALIGNMENT" in accepted["evidence_codes"]
    assert rejected["status"] == "TERMINAL_LABEL_ONLY_REVIEW"
    assert rejected["attached_line_handles"] == []


def test_terminal_evidence_summary_separates_complete_and_review_only_rows() -> None:
    summary = summarize_instance_port_network_candidates(
        [
            {
                "status": "MEASURED_TERMINAL_ATTACHMENT",
                "terminal_geometry_recognized": True,
                "terminal_independent_evidence_complete": True,
                "terminal_label_ambiguous": False,
                "external_network_ids": ["EN1"],
                "electrical_union_eligible": False,
                "critical_issue_eligible": False,
            },
            {
                "status": "TERMINAL_BINDING_AMBIGUOUS",
                "terminal_geometry_recognized": True,
                "terminal_independent_evidence_complete": False,
                "terminal_label_ambiguous": True,
                "external_network_ids": [],
                "electrical_union_eligible": False,
                "critical_issue_eligible": False,
            },
        ]
    )

    assert summary["terminal_geometry_recognized_count"] == 2
    assert summary["independent_evidence_complete_count"] == 1
    assert summary["ambiguous_binding_count"] == 1
    assert summary["terminal_review_only_count"] == 1
    assert summary["status_counts"] == {
        "MEASURED_TERMINAL_ATTACHMENT": 1,
        "TERMINAL_BINDING_AMBIGUOUS": 1,
    }
    assert summary["family_counts"] == {"UNKNOWN": 2}
    assert summary["binding_status_counts"] == {"UNVERIFIED": 2}
    assert summary["electrical_union_eligible_count"] == 0


def test_pwf234_four_way_terminal_is_human_confirmed_terminal_model() -> None:
    policy = human_symbol_port_policy(
        "03db302eda788e4107a4dc2e882e6da52af3d56ea388d8a8f5789e6892a52211"
    )

    assert policy is not None
    assert policy["mode"] == "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY"


def test_component_port_uses_existing_mapping_for_cross_page_key() -> None:
    proposal = {
        "file_id": "F0007", "definition_name": "SYMB2_M_PWF236",
        "ports": [{"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]}],
    }
    instance = {
        "symbol_instance_id": "SI-dk", "project_id": "P001", "sheet_id": "S0007", "file_id": "F0007",
        "entity_handle": "EE97", "definition_name": "SYMB2_M_PWF236",
        "definition_fingerprint": "e84d37eab1d5e64b04de0e6aae32137b3ae80676267d6e24e71266aa4b9e7ee9",
        "transform_json": {"matrix44": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [95, 260, 0, 1]]},
    }
    texts = [
        {"text_id": "TDK", "handle": "HTDK", "sheet_id": "S0007", "file_id": "F0007", "text": "1DK", "normalized_text": "1DK", "insert_x": 95, "insert_y": 270},
        {"text_id": "T3", "handle": "HT3", "sheet_id": "S0007", "file_id": "F0007", "text": "3", "normalized_text": "3", "insert_x": 95, "insert_y": 260},
    ]
    pairs = [{"pair_id": "PC-DK3", "sheet_id": "S0007", "pair_kind": "component_mapping", "left_value": "1DK-3", "right_value": "ZD1"}]

    candidates = build_instance_port_network_candidates([proposal], [instance], texts, [], [], component_pairs=pairs)

    assert candidates[0]["component_port_identity"] == "1DK-3"
    assert candidates[0]["component_mapping_external_endpoints"] == ["ZD1"]
    assert candidates[0]["cross_page_match_eligible"] is True
    assert candidates[0]["internal_connectivity_inferred"] is False


def test_pwf237_multi_port_component_uses_external_port_policy() -> None:
    policy = human_symbol_port_policy(
        "835a7dcc7eae596a7b1a600a48f0e579bf800a22b1add1ffbcc44d2ddb95e054"
    )

    assert policy is not None
    assert policy["mode"] == "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY"


def test_pwf238_is_a_labelled_terminal() -> None:
    policy = human_symbol_port_policy(
        "cce15b281bc0c0ef0df95453bffcd991d28e73e7683a513b4c3e5f979c243438"
    )

    assert policy is not None
    assert policy["mode"] == "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY"
