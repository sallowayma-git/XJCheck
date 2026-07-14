from __future__ import annotations

import ezdxf

from dwg_audit.audit.symbol_library_review import load_symbol_review_document
from dwg_audit.audit.symbol_port_proposal import apply_proposals_to_review_document
from dwg_audit.audit.symbol_port_proposal import apply_human_symbol_policy_to_proposal_row
from dwg_audit.audit.symbol_port_proposal import build_instance_port_network_candidates
from dwg_audit.audit.symbol_port_proposal import propose_ports_from_block
from dwg_audit.audit.symbol_port_proposal import propose_ports_from_segments
from dwg_audit.audit.symbol_port_proposal import human_symbol_port_policy
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
