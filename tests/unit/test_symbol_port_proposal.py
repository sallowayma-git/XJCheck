from __future__ import annotations

import math

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


def test_exact_panel_internal_line_is_ignored_without_generalizing_to_wires() -> None:
    proposal = {
        "definition_name": "RENAMED_SINGLE_LINE",
        "definition_fingerprint": "cd0346ad16ba285a9950c48c0611017efcd9490cc6d6d78c81442860902a75cf",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [50.0, 0.0, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "width": 50.0,
                "height": 0.0,
                "primitive_count": 1,
                "primitive_histogram": {"LINE": 1},
                "entity_histogram": {"LINE": 1},
                "arc_radii": [],
                "circle_radii": [],
                "text_values": [],
            }
        },
    }
    exact = apply_human_symbol_policy_to_proposal_row(proposal)
    unseen = apply_human_symbol_policy_to_proposal_row(
        {**proposal, "definition_fingerprint": "unseen-single-line-definition"}
    )

    assert exact["family_id"] == "non_electrical.panel_internal_line.v1"
    assert exact["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert exact["behavior_mode"] == "IGNORE"
    assert exact["ports"] == []
    assert exact["allow_external_attachment"] is False
    assert exact["allow_internal_connectivity"] is False
    assert exact["allow_electrical_union"] is False
    assert unseen["family_id"] is None
    assert unseen["behavior_mode"] == "REVIEW_ONLY"
    assert unseen["suppressed_by_policy"] is False
    assert len(unseen["ports"]) == 2


def test_exact_panel_common_bus_is_scope_ignored_without_generalizing_vertical_lines() -> None:
    proposal = {
        "definition_name": "RENAMED_VERTICAL_SINGLE_LINE",
        "definition_fingerprint": "ae788d00fab7abcd6190c917d8f4c42e8613320b78143443b3849d7e9aea6e72",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [0.0, 180.0, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "width": 0.0,
                "height": 180.0,
                "primitive_count": 1,
                "primitive_histogram": {"LINE": 1},
                "entity_histogram": {"LINE": 1},
                "arc_radii": [],
                "circle_radii": [],
                "text_values": [],
            }
        },
    }
    exact = apply_human_symbol_policy_to_proposal_row(proposal)
    unseen = apply_human_symbol_policy_to_proposal_row(
        {**proposal, "definition_fingerprint": "unseen-vertical-single-line"}
    )

    assert exact["family_id"] == "non_electrical.panel_internal_bus_excluded.v1"
    assert exact["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert exact["behavior_mode"] == "IGNORE"
    assert exact["ports"] == []
    assert exact["allow_external_attachment"] is False
    assert exact["allow_internal_connectivity"] is False
    assert exact["allow_electrical_union"] is False
    assert unseen["family_id"] is None
    assert unseen["behavior_mode"] == "REVIEW_ONLY"
    assert unseen["suppressed_by_policy"] is False
    assert len(unseen["ports"]) == 2


def test_diode_ignore_family_exact_and_geometry_members_are_zero_port() -> None:
    contacts = [
        {"center": [0.25, 1.0], "radius": 0.066667},
        {"center": [0.25, 0.0], "radius": 0.066667},
    ]
    segments = [
        {"start": [0.0, 0.25], "end": [0.5, 0.25]},
        {"start": [0.0, 0.75], "end": [0.5, 0.75]},
        {"start": [0.0, 0.75], "end": [0.25, 0.25]},
        {"start": [0.25, 0.25], "end": [0.5, 0.75]},
        {"start": [0.25, 1.0], "end": [0.25, 0.0]},
    ]

    def rotate(point: list[float]) -> list[float]:
        angle = math.radians(37.0)
        return [
            point[0] * math.cos(angle) - point[1] * math.sin(angle),
            point[0] * math.sin(angle) + point[1] * math.cos(angle),
        ]

    variants = [
        (
            "765aa9ba366baffab5550e90512b94fb6bc312a9866af101fe7e9ae6571d1c02",
            contacts,
            segments,
        ),
        (
            "unseen-diode",
            [
                {"center": rotate(item["center"]), "radius": item["radius"]}
                for item in contacts
            ],
            [
                {"start": rotate(item["start"]), "end": rotate(item["end"])}
                for item in segments
            ],
        ),
    ]
    for fingerprint, variant_contacts, variant_segments in variants:
        row = {
            "definition_fingerprint": fingerprint,
            "ports": [{"port_id": "MP1"}, {"port_id": "MP2"}],
            "geometry_summary": {"shape_features": {
                "width": 3.75,
                "height": 7.5,
                "primitive_histogram": {"LINE": 5, "LWPOLYLINE": 2},
                "entity_histogram": {"LINE": 5, "LWPOLYLINE": 2},
                "closed_bulged_lwpolyline_count": 2,
                "normalized_closed_bulged_contacts": variant_contacts,
                "normalized_line_segments": variant_segments,
            }},
        }
        applied = apply_human_symbol_policy_to_proposal_row(row)
        assert applied["family_id"] == "electrical.diode_symbol_ignored.v1"
        assert applied["ports"] == []
        assert applied["allow_external_attachment"] is False


def test_boxed_diode_exact_is_refined_and_wrong_topology_is_not_generalized() -> None:
    shape = {"width": 6.0, "height": 6.872, "primitive_histogram": {"HATCH": 2, "LINE": 13, "LWPOLYLINE": 3},
             "entity_histogram": {"HATCH": 2, "LINE": 13, "LWPOLYLINE": 3}, "closed_bulged_lwpolyline_count": 2,
             "normalized_closed_bulged_contacts": [{"center": [0, 0], "radius": .02}, {"center": [1, 1], "radius": .02}],
             "normalized_line_segments": [{"start": [0, 0], "end": [1, 1]}] * 13,
             "boxed_diode_repeated_topology": True}
    row = {"definition_fingerprint": "9a1c6d15833092f32027442d19bd52f5f384395b0bb113e252e5bfbfe66cb85b", "ports": [{"port_id": str(i)} for i in range(4)], "geometry_summary": {"shape_features": shape}}
    applied = apply_human_symbol_policy_to_proposal_row(row)
    assert applied["family_id"] == "electrical.diode_symbol_ignored.v1"
    assert applied["ports"] == []
    shape["boxed_diode_repeated_topology"] = False
    negative = apply_human_symbol_policy_to_proposal_row({**row, "definition_fingerprint": "unseen-box"})
    assert negative["family_id"] != "electrical.diode_symbol_ignored.v1"


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


def _inline_indicator_proposal(
    *,
    rotation_deg: float,
    scale: float,
    fingerprint: str,
    exact_name: bool = False,
    offset_marker: bool = False,
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_INLINE_INDICATOR")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    marker_shift = 0.8 if offset_marker else 0.0
    segments = (
        ((-40.0, 0.0), (0.0, 0.0)),
        ((-16.68230167157606, 1.122675219712988), (-17.26099568549245, 0.2696727353923905)),
        ((-18.3593608986277, -0.3773155632455598), (-16.68230167157606, 1.122675219712988)),
        ((-16.01563910137213, 0.3773155632456167), (-16.59433311528869, -0.4756869210750381)),
        ((-17.69269832842394, -1.122675219712988), (-16.01563910137213, 0.3773155632456167)),
        ((-27.21814771951881, -2.5 + marker_shift), (-24.71814771951881, 2.5 + marker_shift)),
    )
    for start, end in segments:
        block.add_line(transform(start), transform(end))
    block.add_circle(transform((-17.1875, 0.0)), radius=1.25 * scale)
    for points in (
        ((-18.35, -0.38), (-16.68, 1.12), (-17.26, 0.27)),
        ((-17.69, -1.12), (-16.02, 0.38), (-16.59, -0.48)),
    ):
        hatch = block.add_hatch(color=1)
        hatch.paths.add_polyline_path([transform(point) for point in points], is_closed=True)
    return propose_ports_from_block(
        block,
        definition_name="A$C1D4D7376" if exact_name else "RENAMED_INLINE_INDICATOR",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_inline_indicator_ignore_generalizes_rotation_and_scale() -> None:
    exact = _inline_indicator_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="ea02de2d3b540c5240d289e863160289db7a720c8b7c9db2efbc52c321e45df6",
        exact_name=True,
    )
    unseen = _inline_indicator_proposal(
        rotation_deg=43.0,
        scale=2.1,
        fingerprint="unseen-rotated-inline-indicator",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.nonconnective_inline_indicator_ignored.v1"
        assert applied["matched_family_rule_id"] == "hatched-circle-inline-indicator-v1"
        assert applied["classifier_status"] in {"HUMAN_CONFIRMED_MEMBER", "MATCHED"}
        assert applied["ports"] == []
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_inline_indicator_offset_marker_stays_review() -> None:
    proposal = _inline_indicator_proposal(
        rotation_deg=19.0,
        scale=1.4,
        fingerprint="unseen-offset-inline-indicator",
        offset_marker=True,
    )

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied.get("matched_family_rule_id") != "hatched-circle-inline-indicator-v1"
    assert applied["suppressed_by_policy"] is False


def _circle_contact_marker_proposal(
    *, rotation_deg: float, scale: float, fingerprint: str, offset_contact: bool = False
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_CIRCLE_CONTACT_MARKER")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    contact_center = (0.45 if offset_contact else 0.0, -5.0)
    block.add_circle(transform((0.0, 0.0)), radius=2.0 * scale)
    block.add_line(transform((-2.0, 0.0)), transform((2.0, 0.0)))
    block.add_line(transform((0.0, -2.0)), transform((0.0, -5.0)))
    block.add_lwpolyline(
        [
            (*transform((contact_center[0] - 1.0, contact_center[1])), 1.0),
            (*transform((contact_center[0] + 1.0, contact_center[1])), 1.0),
        ],
        format="xyb",
        close=True,
    )
    hatch = block.add_hatch(color=1)
    hatch.paths.add_polyline_path(
        [transform(point) for point in ((-0.2, -0.2), (0.2, -0.2), (0.0, 0.2))],
        is_closed=True,
    )
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_CIRCLE_CONTACT_MARKER",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_circle_contact_marker_ignore_generalizes_rotation_and_scale() -> None:
    exact = _circle_contact_marker_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="a662de3d914d6b22aa1b0d6f9e4a0a090de1e0cd8461224860fc8199cba2bf0f",
    )
    unseen = _circle_contact_marker_proposal(
        rotation_deg=37.0,
        scale=1.8,
        fingerprint="unseen-rotated-circle-contact-marker",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.nonconnective_circle_contact_marker_ignored.v1"
        assert applied["matched_family_rule_id"] == "diameter-circle-offset-contact-marker-v1"
        assert applied["classifier_status"] in {"HUMAN_CONFIRMED_MEMBER", "MATCHED"}
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["ports"] == []
        assert applied["allow_port_emission"] is False
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_circle_contact_marker_offset_contact_stays_review() -> None:
    applied = apply_human_symbol_policy_to_proposal_row(
        _circle_contact_marker_proposal(
            rotation_deg=19.0,
            scale=1.4,
            fingerprint="unseen-offset-circle-contact-marker",
            offset_contact=True,
        )
    )

    assert applied.get("matched_family_rule_id") != "diameter-circle-offset-contact-marker-v1"
    assert applied["suppressed_by_policy"] is False


def _crossed_two_contact_switch_proposal(
    *, rotation_deg: float, scale: float, fingerprint: str, offset_diagonal: bool = False
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_CROSSED_TWO_CONTACT_SWITCH")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    for start, end in (((0.0, 0.0), (2.0, 0.0)), ((10.0, 0.0), (8.0, 0.0))):
        block.add_line(transform(start), transform(end))
    for center_x in (0.0, 10.0):
        block.add_lwpolyline(
            [
                (*transform((center_x - 0.5, 0.0)), 1.0),
                (*transform((center_x + 0.5, 0.0)), 1.0),
            ],
            format="xyb",
            close=True,
        )
    diagonal_offset = 0.4 if offset_diagonal else 0.0
    block.add_lwpolyline(
        [
            transform((6.8, 2.4 + diagonal_offset)),
            transform((3.2, -2.4 + diagonal_offset)),
        ]
    )
    block.add_lwpolyline(
        [transform((3.2, 2.4)), transform((6.8, -2.4))]
    )
    block.add_lwpolyline(
        [
            (*transform((2.0, 0.0)), 1.0),
            (*transform((8.0, 0.0)), 1.0),
            (*transform((2.0, 0.0)), -0.1851562949912785),
        ],
        format="xyb",
    )
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_CROSSED_TWO_CONTACT_SWITCH",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_crossed_two_contact_switch_ignore_generalizes_rotation_and_scale() -> None:
    exact = _crossed_two_contact_switch_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="8f7479379424184442b346891c2040fe047a8756561435f42095f4e088b39cf1",
    )
    unseen = _crossed_two_contact_switch_proposal(
        rotation_deg=37.0,
        scale=1.8,
        fingerprint="unseen-rotated-crossed-two-contact-switch",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "switch.open.v1"
        assert applied["matched_family_rule_id"] == "crossed-two-contact-open-switch-v1"
        assert applied["classifier_status"] in {"HUMAN_CONFIRMED_MEMBER", "MATCHED"}
        assert applied["ports"] == []
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_crossed_two_contact_switch_offset_diagonal_stays_review() -> None:
    proposal = _crossed_two_contact_switch_proposal(
        rotation_deg=19.0,
        scale=1.4,
        fingerprint="unseen-offset-crossed-two-contact-switch",
        offset_diagonal=True,
    )

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied.get("matched_family_rule_id") != "crossed-two-contact-open-switch-v1"
    assert applied["suppressed_by_policy"] is False


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


def test_large_text_dense_drawing_metadata_is_not_a_multi_port_component() -> None:
    proposal = {
        "definition_name": "REDRAWN_SIGN_BLOCK",
        "definition_fingerprint": "new-sign-block-fingerprint",
        "ports": [
            {"port_id": f"MP{index}", "local_position": [float(index), 0.0, 0.0]}
            for index in range(1, 7)
        ],
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [],
                "circle_radii": [],
                "primitive_count": 59,
                "primitive_histogram": {"LINE": 36, "LWPOLYLINE": 23},
                "entity_histogram": {
                    "ATTDEF": 1,
                    "LINE": 36,
                    "LWPOLYLINE": 23,
                    "TEXT": 46,
                },
                "text_count": 47,
                "width": 420.0,
                "height": 295.0,
            }
        },
    }

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] == "non_electrical.drawing_metadata.v1"
    assert applied["status"] == "GEOMETRY_FAMILY_NON_CONNECTIVE"
    assert applied["ports"] == []


def test_confirmed_dk_geometry_matches_multi_port_family_after_fingerprint_drift() -> None:
    proposal = {
        "definition_name": "REDRAWN_DK",
        "definition_fingerprint": "drifted-dk-fingerprint",
        "ports": [
            {"port_id": f"MP{index}", "local_position": [float(index), 0.0, 0.0]}
            for index in range(1, 5)
        ],
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [1.25, 1.25],
                "circle_radii": [],
                "primitive_count": 32,
                "primitive_histogram": {"ARC": 2, "LINE": 26, "LWPOLYLINE": 4},
                "entity_histogram": {"ARC": 2, "LINE": 26, "LWPOLYLINE": 4},
                "text_count": 0,
                "width": 21.0,
                "height": 15.125,
            }
        },
    }

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] == "component.external_multi_port.v1"
    assert applied["classifier_status"] == "MATCHED"
    assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
    assert applied["suppressed_by_policy"] is False


def test_ethernet_port_variants_generalize_ignore_without_external_mapping() -> None:
    def proposal(*, polylines: int, width: float, height: float, ports: int) -> dict:
        return {
            "definition_name": "REDRAWN_ETHERNET_PORT",
            "definition_fingerprint": f"new-ethernet-{polylines}-{ports}",
            "ports": [
                {"port_id": f"MP{index}", "local_position": [float(index), 0.0, 0.0]}
                for index in range(1, ports + 1)
            ],
            "geometry_summary": {
                "shape_features": {
                    "arc_radii": [],
                    "circle_radii": [],
                    "primitive_count": polylines,
                    "primitive_histogram": {"LWPOLYLINE": polylines},
                    "entity_histogram": {"LWPOLYLINE": polylines, "TEXT": 2},
                    "text_count": 2,
                    "width": width,
                    "height": height,
                }
            },
        }

    five_port = apply_human_symbol_policy_to_proposal_row(
        proposal(polylines=3, width=7.5, height=10.0, ports=5)
    )
    four_port = apply_human_symbol_policy_to_proposal_row(
        proposal(polylines=2, width=7.5, height=7.5, ports=4)
    )

    for applied in (five_port, four_port):
        assert applied["family_id"] == "communication.ethernet_port_ignored.v1"
        assert applied["status"] == "GEOMETRY_FAMILY_NON_CONNECTIVE"
        assert applied["ports"] == []
        assert applied["allow_external_attachment"] is False
        assert applied["allow_electrical_union"] is False


def test_wider_two_text_component_without_pwf330_topology_is_not_ignored() -> None:
    proposal = {
        "definition_name": "WIDER_TWO_TEXT_COMPONENT",
        "definition_fingerprint": "wider-two-text-fingerprint",
        "ports": [
            {"port_id": f"MP{index}", "local_position": [float(index), 0.0, 0.0]}
            for index in range(1, 5)
        ],
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [],
                "circle_radii": [],
                "primitive_count": 3,
                "primitive_histogram": {"LWPOLYLINE": 3},
                "entity_histogram": {"LWPOLYLINE": 3, "TEXT": 2},
                "text_count": 2,
                "width": 12.0,
                "height": 7.5,
            }
        },
    }

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] != "communication.ethernet_port_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def test_pwf330_lan_port_exact_and_unseen_geometry_are_non_connective() -> None:
    def row(fingerprint: str) -> dict:
        return {
            "definition_fingerprint": fingerprint,
            "ports": [{"port_id": "MP1"}],
            "geometry_summary": {"shape_features": {
                "text_values": ["ETHER", "NET"], "text_count": 2,
                "entity_histogram": {"LWPOLYLINE": 3, "TEXT": 2},
                "primitive_histogram": {"LWPOLYLINE": 3},
                "normalized_closed_straight_lwpolylines": [{
                    "center": [0.354167, 0.3125],
                    "width": 0.625,
                    "height": 0.625,
                    "edge_lengths": [0.625, 0.625, 0.625, 0.625],
                }],
                "normalized_closed_bulged_contacts": [
                    {"center": [0.041667, 0.3125], "radius": 0.041667},
                    {"center": [0.958333, 0.3125], "radius": 0.041667},
                ],
                "width": 1.0, "height": 0.625,
            }},
        }
    for proposal in (
        row("b65e304c63f2661098d380605c4000e75855fbfcc57985109fad3a21c1c88ed5"),
        row("unseen-pwf330"),
    ):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "communication.ethernet_port_ignored.v1"
        assert applied["ports"] == []
        assert applied["allow_external_attachment"] is False
        assert applied["allow_electrical_union"] is False


def test_pwf330_unseen_geometry_survives_arbitrary_rotation_and_scaling() -> None:
    document = ezdxf.new()
    block = document.blocks.new(name="ROTATED_UNSEEN_ETHERNET_LAN_PORT")
    angle = math.radians(37.0)
    scale = 2.3

    def transform(x: float, y: float) -> tuple[float, float]:
        return (
            scale * (x * math.cos(angle) - y * math.sin(angle)),
            scale * (x * math.sin(angle) + y * math.cos(angle)),
        )

    for value, position in (("ETHER", (0.5, 0.25)), ("NET", (0.5, -2.875))):
        block.add_text(
            value,
            dxfattribs={"insert": transform(*position), "rotation": 37.0},
        )
    block.add_lwpolyline(
        [transform(x, y) for x, y in ((0.0, -3.75), (0.0, 3.75), (7.5, 3.75), (7.5, -3.75))],
        close=True,
    )
    for left, right in (((-0.5, 0.0), (0.5, 0.0)), ((10.5, 0.0), (11.5, 0.0))):
        start = transform(*left)
        end = transform(*right)
        block.add_lwpolyline(
            [(start[0], start[1], 1.0), (end[0], end[1], 1.0)],
            format="xyb",
            close=True,
        )

    proposal = propose_ports_from_block(
        block,
        definition_name="ROTATED_UNSEEN_ETHERNET_LAN_PORT",
        definition_fingerprint="unseen-rotated-scaled-pwf330",
    ).to_dict()
    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] == "communication.ethernet_port_ignored.v1"
    assert applied["matched_family_rule_id"] == "ethernet-lan-wide-contact-body-topology-v1"
    assert applied["status"] == "GEOMETRY_FAMILY_NON_CONNECTIVE"
    assert applied["ports"] == []
    assert applied["allow_external_attachment"] is False
    assert applied["allow_internal_connectivity"] is False
    assert applied["allow_electrical_union"] is False


def test_pwf330_incomplete_text_or_socket_topology_is_not_absorbed() -> None:
    proposal = {
        "definition_fingerprint": "unseen-pwf330-negative",
        "ports": [{"port_id": "MP1"}],
        "geometry_summary": {"shape_features": {
            "text_values": ["ETHER", "NET"], "text_count": 2,
            "entity_histogram": {"LWPOLYLINE": 3, "TEXT": 2},
            "normalized_closed_straight_lwpolylines": [{
                "center": [0.35, 0.31],
                "edge_lengths": [0.625, 0.625, 0.625, 0.625],
            }],
            "normalized_closed_bulged_contacts": [
                {"center": [0.04, 0.31], "radius": 0.04}
            ],
        }},
    }
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied["family_id"] != "communication.ethernet_port_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def test_wire_crossover_jump_is_removed_from_symbol_review_without_ignore_semantics() -> None:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_WIRE_JUMP")
    block.add_line((0.0, 0.0), (3.75, 0.0))
    block.add_line((6.25, 0.0), (10.0, 0.0))
    block.add_arc((5.0, 0.0), radius=1.25, start_angle=0.0, end_angle=180.0)

    exact = propose_ports_from_block(
        block,
        definition_name="RENAMED_WIRE_JUMP",
        definition_fingerprint="f9d454c009fff6e62f248535070beb3ce1787db373d260f7159948192c492bb8",
    ).to_dict()
    unseen = {**exact, "definition_fingerprint": "unseen-wire-jump"}
    for proposal, expected_status in (
        (exact, "HUMAN_ADJUDICATED_WIRE_PRIMITIVE"),
        (unseen, "GEOMETRY_FAMILY_WIRE_PRIMITIVE"),
    ):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "wire.crossover_jump.v1"
        assert applied["status"] == expected_status
        assert applied["behavior_mode"] == "WIRE_PRIMITIVE"
        assert applied["ports"] == []
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False

    incomplete = propose_ports_from_block(
        document.blocks.new("NOT_A_JUMP"),
        definition_name="NOT_A_JUMP",
        definition_fingerprint="unseen-not-jump",
    ).to_dict()
    assert apply_human_symbol_policy_to_proposal_row(incomplete)["family_id"] != "wire.crossover_jump.v1"


def test_optical_st_port_generalizes_ignore_without_1t_1r_mapping() -> None:
    proposal = {
        "definition_name": "REDRAWN_ST_SINGLE_MODE_PORT",
        "definition_fingerprint": "new-optical-st-fingerprint",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [16.0, 0.0, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [2.5],
                "circle_radii": [],
                "primitive_count": 4,
                "primitive_histogram": {"ARC": 1, "LINE": 1, "LWPOLYLINE": 2},
                "entity_histogram": {"ARC": 1, "LINE": 1, "LWPOLYLINE": 2},
                "text_count": 0,
                "width": 16.0,
                "height": 8.76,
            }
        },
    }

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] == "communication.optical_st_port_ignored.v1"
    assert applied["status"] == "GEOMETRY_FAMILY_NON_CONNECTIVE"
    assert applied["ports"] == []
    assert applied["allow_external_attachment"] is False
    assert applied["allow_electrical_union"] is False


def test_two_arc_terminal_is_not_absorbed_by_optical_st_ignore_family() -> None:
    proposal = {
        "definition_name": "COMPACT_TERMINAL_CONTROL",
        "definition_fingerprint": "terminal-control-fingerprint",
        "ports": [
            {"port_id": "MP1", "local_position": [0.0, 0.0, 0.0]},
            {"port_id": "MP2", "local_position": [6.0, 0.0, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "arc_radii": [1.25, 1.25],
                "circle_radii": [],
                "primitive_count": 6,
                "primitive_histogram": {"ARC": 2, "LINE": 2, "LWPOLYLINE": 2},
                "entity_histogram": {"ARC": 2, "LINE": 2, "LWPOLYLINE": 2},
                "text_count": 0,
                "width": 6.0,
                "height": 2.5,
            }
        },
    }

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] == "labelled_terminal.generic.v1"
    assert applied["suppressed_by_policy"] is False


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


def _ground_variant(*, rotated: bool = False, scaled: float = 1.0) -> dict:
    segments = [
        {"start": [0.5, 0.2], "end": [0.5, 0.65]},
        {"start": [0.2, 0.65], "end": [0.8, 0.65]},
        {"start": [0.275, 0.75], "end": [0.725, 0.75]},
        {"start": [0.35, 0.85], "end": [0.65, 0.85]},
    ]
    contact = {"center": [0.5, 0.2], "radius": 0.05}
    if rotated:
        def rotate(point: list[float]) -> list[float]:
            return [1.0 - point[1], point[0]]

        segments = [
            {"start": rotate(item["start"]), "end": rotate(item["end"])}
            for item in segments
        ]
        contact = {"center": rotate(contact["center"]), "radius": contact["radius"]}
    return {
        "definition_fingerprint": "unseen-ground-variant",
        "ports": [{"port_id": f"MP{i}"} for i in range(5)],
        "geometry_summary": {"shape_features": {
            "width": 4.994 * scaled, "height": 3.749 * scaled,
            "primitive_count": 5, "arc_radii": [], "circle_radii": [],
            "primitive_histogram": {"LINE": 4, "LWPOLYLINE": 1},
            "entity_histogram": {"LINE": 4, "LWPOLYLINE": 1}, "text_count": 0,
            "closed_bulged_lwpolyline_count": 1,
            "parallel_line_group_max": 3,
            "normalized_parallel_line_lengths": [0.6, 0.8, 1.0],
            "normalized_line_lengths": [0.6, 0.8, 1.0, 0.4],
            "normalized_line_segments": segments,
            "normalized_closed_bulged_contacts": [contact],
        }}
    }


def test_pwf318_ground_symbol_exact_and_unseen_variants_are_non_connective() -> None:
    exact = _ground_variant()
    exact["definition_fingerprint"] = "a6c74f98075e063d0bd026cee40d021e30ded7fb6eabca346385d81d1f8f81e7"
    for proposal in (exact, _ground_variant(rotated=True, scaled=7.5)):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.ground_symbol_ignored.v1"
        assert applied["ports"] == []
        assert applied["allow_external_attachment"] is False
        assert applied["allow_electrical_union"] is False


def test_ground_same_count_non_ground_shape_is_not_absorbed() -> None:
    proposal = _ground_variant()
    shape = proposal["geometry_summary"]["shape_features"]
    # Keep all four LINEs and the closed bulged contact, but offset the lead so
    # it no longer joins the bar centers or the round contact.
    shape["normalized_line_segments"][0] = {
        "start": [0.75, 0.2],
        "end": [0.75, 0.65],
    }
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied["family_id"] != "electrical.ground_symbol_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def _stepped_ground_proposal(*, fingerprint: str, mirror: bool = False, offset: bool = False) -> dict:
    bars = [((1.0 - length / 2, y), (1.0 + length / 2, y)) for y, length in ((0.0, 2.0), (0.3, 1.4), (0.6, 0.8))]
    lines = bars + [((1.0, 0.0), (1.0, 1.0)), ((1.0, 0.0), (1.0, 1.0)), ((1.0, 1.0), (1.6, 1.0))]
    if offset:
        lines[-1] = ((1.0, 1.08), (1.6, 1.08))
    def item(segment):
        start, end = segment
        return {"start": [(-start[0] if mirror else start[0]), start[1]], "end": [(-end[0] if mirror else end[0]), end[1]]}
    return {"definition_fingerprint": fingerprint, "ports": [{"port_id": "P1"}],
            "geometry_summary": {"shape_features": {
                "width": 2.0, "height": 1.6, "primitive_count": 9,
                "primitive_histogram": {"LINE": 6, "LWPOLYLINE": 3},
                "entity_histogram": {"LINE": 6, "LWPOLYLINE": 3},
                "normalized_line_segments": [item(s) for s in lines],
                "normalized_open_lwpolyline_segments": [item(s) for s in bars],
            }}}


def test_ld_dzbjd_left_stepped_ground_ignore_is_invariant_and_fail_closed() -> None:
    exact = _stepped_ground_proposal(
        fingerprint="d2978aaddce462eeea764d8295a059d646b00da794aeab718a568e6470bbf56b"
    )
    exact_applied = apply_human_symbol_policy_to_proposal_row(exact)
    assert exact_applied["family_id"] == "electrical.ground_symbol_ignored.v1"
    assert exact_applied["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    unseen_applied = apply_human_symbol_policy_to_proposal_row(
        _stepped_ground_proposal(fingerprint="unseen-stepped-ground", mirror=True)
    )
    assert unseen_applied["family_id"] == "electrical.nonconnective_stepped_marker_ignored.v1"
    assert unseen_applied["matched_family_rule_id"] == "stepped-duplicate-bar-nonconnective-v1"
    for applied in (exact_applied, unseen_applied):
        assert applied["ports"] == []
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
    negative = apply_human_symbol_policy_to_proposal_row(
        _stepped_ground_proposal(fingerprint="unseen-same-count-offset", offset=True)
    )
    assert negative["family_id"] != "electrical.ground_symbol_ignored.v1"
    assert negative["suppressed_by_policy"] is False


def _kk2p_shape(*, rotated: bool = False, scaled: float = 1.0, text_values=None) -> dict:
    contacts = [{"center": [x, y], "radius": 0.03} for x, y in ((.25, .25), (.75, .25), (.25, .75), (.75, .75))]
    if rotated:
        angle = math.radians(37.0)
        cosine, sine = math.cos(angle), math.sin(angle)
        contacts = [{"center": [c["center"][0] * cosine - c["center"][1] * sine,
                                  c["center"][0] * sine + c["center"][1] * cosine],
                     "radius": c["radius"]} for c in contacts]
    return {"width": 30.0 * scaled, "height": 25.0 * scaled,
            "primitive_count": 13, "primitive_histogram": {"LINE": 9, "LWPOLYLINE": 4},
            "entity_histogram": {"LINE": 9, "LWPOLYLINE": 4, "TEXT": 4}, "text_count": 4,
            "text_values": text_values or ["1", "2", "3", "4"],
            "closed_bulged_lwpolyline_count": 4, "normalized_closed_bulged_contacts": contacts,
            "kk2p_2x2_topology": True}


def test_kk2p_exact_and_unseen_rotated_scaled_members_are_external_only() -> None:
    exact = {"definition_fingerprint": "3f7ef8a0ca8b88180e8cf7094e95355e6b2837e7e598cba3a19ce04e6445620a",
             "ports": [{"port_id": f"MP{i}"} for i in range(1, 5)],
             "geometry_summary": {"shape_features": _kk2p_shape()}}
    unseen = {"definition_fingerprint": "unseen-kk2p", "ports": [{"port_id": f"MP{i}"} for i in range(1, 5)],
              "geometry_summary": {"shape_features": _kk2p_shape(rotated=True, scaled=8.0)}}
    for row in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(row)
        assert applied["family_id"] == "component.external_multi_port.v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
        assert applied["ports"]


def test_kk2p_same_counts_wrong_text_or_topology_are_not_absorbed() -> None:
    for shape in (_kk2p_shape(text_values=["1", "2", "3", "X"]),
                  {**_kk2p_shape(), "kk2p_2x2_topology": False},
                  {**_kk2p_shape(), "normalized_closed_bulged_contacts": [
                      {"center": [i / 4, .5], "radius": .03} for i in range(4)]}):
        row = {"definition_fingerprint": "unseen-negative-kk2p", "ports": [{"port_id": f"MP{i}"} for i in range(1, 5)],
               "geometry_summary": {"shape_features": shape}}
        applied = apply_human_symbol_policy_to_proposal_row(row)
        assert applied["family_id"] != "component.external_multi_port.v1"


def test_kk2p_extracted_topology_is_invariant_under_arbitrary_rotation() -> None:
    document = ezdxf.new()
    block = document.blocks.new("ROTATED_FOUR_PORT")
    angle = math.radians(37.0)
    cosine, sine = math.cos(angle), math.sin(angle)

    def rotate(point: tuple[float, float]) -> tuple[float, float]:
        return (
            point[0] * cosine - point[1] * sine,
            point[0] * sine + point[1] * cosine,
        )

    for start, end in [
        ((0.0, 30.0), (12.5, 30.0)),
        ((0.0, 30.0), (0.0, 0.0)),
        ((12.5, 30.0), (25.0, 30.0)),
        ((25.0, 30.0), (25.0, 0.0)),
        ((25.0, 0.0), (0.0, 0.0)),
        ((0.0, 22.5), (25.0, 22.5)),
        ((12.5, 30.0), (12.5, 22.5)),
        ((0.0, 7.5), (25.0, 7.5)),
        ((12.5, 7.5), (12.5, 0.0)),
    ]:
        block.add_line(rotate(start), rotate(end))
    for center in ((2.5, 0.0), (2.5, 30.0), (22.5, 0.0), (22.5, 30.0)):
        first = rotate((center[0] - 0.5, center[1]))
        second = rotate((center[0] + 0.5, center[1]))
        block.add_lwpolyline(
            [(first[0], first[1], 1.0), (second[0], second[1], 1.0)],
            format="xyb",
            close=True,
        )
    for index, position in enumerate(
        ((5.0, 25.0), (5.0, 2.0), (20.0, 25.0), (20.0, 2.0)), 1
    ):
        block.add_text(str(index), dxfattribs={"insert": rotate(position)})

    proposal = propose_ports_from_block(
        block,
        definition_name="ROTATED_FOUR_PORT",
        definition_fingerprint="unseen-rotated-four-port",
        max_ports=4,
    ).to_dict()
    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert proposal["geometry_summary"]["shape_features"]["kk2p_2x2_topology"] is True
    assert applied["family_id"] == "component.external_multi_port.v1"
    assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
    assert applied["allow_electrical_union"] is False


def _kk3p_shape(*, collinear: bool = False) -> dict:
    centers = [
        (0.0625, 0.125),
        (0.0625, 0.875),
        (0.46875, 0.0),
        (0.46875, 1.0),
        (0.875, 0.125),
        (0.875, 0.875),
    ]
    if collinear:
        centers = [(index / 5.0, 0.5) for index in range(6)]
    return {
        "width": 37.5,
        "height": 40.0,
        "primitive_count": 22,
        "primitive_histogram": {"LINE": 16, "LWPOLYLINE": 6},
        "entity_histogram": {"LINE": 16, "LWPOLYLINE": 6, "TEXT": 6},
        "text_count": 6,
        "text_values": ["1", "3", "2", "4", "5", "6"],
        "closed_bulged_lwpolyline_count": 6,
        "normalized_closed_bulged_contacts": [
            {"center": list(center), "radius": 0.0125} for center in centers
        ],
    }


def test_kk3p_exact_and_unseen_geometry_are_six_port_external_only() -> None:
    for fingerprint in (
        "d5145e5846af5551739c9d3ad82699369c777651188a5b954725d414447dc42b",
        "unseen-six-port-grid",
    ):
        applied = apply_human_symbol_policy_to_proposal_row(
            {
                "definition_name": "RENAMED_SIX_PORT",
                "definition_fingerprint": fingerprint,
                "ports": [{"port_id": f"MP{index}"} for index in range(1, 7)],
                "geometry_summary": {"shape_features": _kk3p_shape()},
            }
        )

        assert applied["family_id"] == "component.external_multi_port.v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert len(applied["ports"]) == 6
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
        if fingerprint.startswith("unseen"):
            assert applied["classifier_status"] == "MATCHED"


def test_kk3p_same_counts_collinear_contacts_do_not_generalize() -> None:
    applied = apply_human_symbol_policy_to_proposal_row(
        {
            "definition_name": "NOT_A_SIX_PORT_GRID",
            "definition_fingerprint": "unseen-collinear-six-contact",
            "ports": [{"port_id": f"MP{index}"} for index in range(1, 7)],
            "geometry_summary": {"shape_features": _kk3p_shape(collinear=True)},
        }
    )

    assert applied["classifier_status"] != "MATCHED"


def test_numbered_six_contact_block_overrides_four_extreme_ports() -> None:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_SIX_CONTACT")
    segments = [
        ((0.0, 35.0), (12.5, 35.0)),
        ((0.0, 35.0), (0.0, 5.0)),
        ((12.5, 35.0), (25.0, 35.0)),
        ((37.5, 35.0), (37.5, 5.0)),
        ((0.0, 27.5), (37.5, 27.5)),
        ((12.5, 35.0), (12.5, 27.5)),
        ((0.0, 12.5), (37.5, 12.5)),
        ((12.5, 12.5), (12.5, 5.0)),
        ((25.0, 35.0), (25.0, 27.5)),
        ((25.0, 12.5), (25.0, 5.0)),
        ((0.0, 5.0), (12.5, 5.0)),
        ((12.5, 5.0), (25.0, 5.0)),
        ((25.0, 5.0), (37.5, 5.0)),
        ((25.0, 35.0), (37.5, 35.0)),
        ((18.75, 35.0), (18.75, 40.0)),
        ((18.75, 5.0), (18.75, 0.0)),
    ]
    for start, end in segments:
        block.add_line(start, end)
    contacts = [
        (2.5, 5.0),
        (2.5, 35.0),
        (18.75, 0.0),
        (18.75, 40.0),
        (35.0, 5.0),
        (35.0, 35.0),
    ]
    for center in contacts:
        block.add_lwpolyline(
            [
                (center[0] - 0.5, center[1], 1.0),
                (center[0] + 0.5, center[1], 1.0),
            ],
            format="xyb",
            close=True,
        )
    for value, position in zip(
        ("1", "2", "3", "4", "5", "6"),
        ((5.0, 30.0), (5.0, 7.0), (18.75, 30.0), (18.75, 7.0), (32.0, 30.0), (32.0, 7.0)),
    ):
        block.add_text(value, dxfattribs={"insert": position})

    proposal = propose_ports_from_block(
        block,
        definition_name="RENAMED_SIX_CONTACT",
        definition_fingerprint="unseen-six-contact-block",
        max_ports=4,
    ).to_dict()
    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert proposal["method"] == "numbered_contact_grid_v1"
    assert [port["port_id"] for port in proposal["ports"]] == [
        "MP1", "MP2", "MP3", "MP4", "MP5", "MP6"
    ]
    assert applied["family_id"] == "component.external_multi_port.v1"
    assert applied["allow_internal_connectivity"] is False


def _four_coil_proposal(*, rotation_deg: float, fingerprint: str) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_FOUR_COIL")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def rotate(point: tuple[float, float]) -> tuple[float, float]:
        return (
            point[0] * cosine - point[1] * sine,
            point[0] * sine + point[1] * cosine,
        )

    for center, start, end in (
        ((5.0, -1.875), 270.0, 90.0),
        ((5.0, -5.625), 270.0, 90.0),
        ((10.0, -1.875), 90.0, 270.0),
        ((10.0, -5.625), 90.0, 270.0),
    ):
        block.add_arc(
            rotate(center),
            radius=1.875,
            start_angle=start + rotation_deg,
            end_angle=end + rotation_deg,
        )
    for start, end in (
        ((5.0, 0.0), (2.5, 0.0)),
        ((5.0, -7.5), (2.5, -7.5)),
        ((10.0, 0.0), (12.5, 0.0)),
        ((10.0, -7.5), (12.5, -7.5)),
        ((12.5, -7.5), (17.5, -7.5)),
        ((0.0, 0.0), (2.5, 0.0)),
        ((0.0, -7.5), (2.5, -7.5)),
        ((12.5, 0.0), (22.5, 0.0)),
        ((17.5, -10.0), (22.5, -10.0)),
        ((17.5, -10.0), (17.5, -7.5)),
    ):
        block.add_line(rotate(start), rotate(end))
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_FOUR_COIL",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_four_coil_ignore_generalizes_across_fingerprint_and_rotation() -> None:
    exact = _four_coil_proposal(
        rotation_deg=0.0,
        fingerprint="ea5558fa7d8135a37f959d31a760327230b12ac52509307fec60274eb25768be",
    )
    unseen = _four_coil_proposal(
        rotation_deg=37.0,
        fingerprint="unseen-rotated-four-coil",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.nonconnective_four_coil_ignored.v1"
        assert applied["ports"] == []
        assert applied["allow_external_attachment"] is False
        assert applied["allow_electrical_union"] is False
    assert apply_human_symbol_policy_to_proposal_row(unseen)["classifier_status"] == "MATCHED"


def test_four_arc_same_counts_without_semicircle_grid_are_not_ignored() -> None:
    proposal = _four_coil_proposal(
        rotation_deg=0.0,
        fingerprint="unseen-four-arc-negative",
    )
    shape = proposal["geometry_summary"]["shape_features"]
    shape["normalized_arcs"] = [
        {**arc, "sweep_deg": 90.0} for arc in shape["normalized_arcs"]
    ]

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] != "electrical.nonconnective_four_coil_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def _repeated_coil_panel_proposal(
    *, rotation_deg: float, scale: float, fingerprint: str, offset_arc: bool = False
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_REPEATED_COIL_PANEL")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    for row_offset in (0.0, -10.0, -20.0):
        for center, start, end in (
            ((5.0, row_offset - 1.875), 270.0, 90.0),
            ((5.0, row_offset - 5.625), 270.0, 90.0),
            ((10.0, row_offset - 1.875), 90.0, 270.0),
            ((10.0, row_offset - 5.625), 90.0, 270.0),
        ):
            shifted = (
                (center[0] + 0.6, center[1])
                if offset_arc and row_offset == -10.0 and center == (10.0, row_offset - 5.625)
                else center
            )
            block.add_arc(
                transform(shifted),
                radius=1.875 * scale,
                start_angle=start + rotation_deg,
                end_angle=end + rotation_deg,
            )
        for start, end in (
            ((5.0, row_offset), (2.5, row_offset)),
            ((5.0, row_offset - 7.5), (2.5, row_offset - 7.5)),
            ((10.0, row_offset), (12.5, row_offset)),
            ((10.0, row_offset - 7.5), (12.5, row_offset - 7.5)),
        ):
            block.add_line(transform(start), transform(end))
    for start, end in (
        ((12.5, -7.5), (17.5, -7.5)),
        ((17.5, -7.5), (17.5, -30.0)),
        ((12.5, -17.5), (17.5, -17.5)),
        ((12.5, -27.5), (17.5, -27.5)),
        ((12.5, 0.0), (22.5, 0.0)),
        ((0.0, 0.0), (2.5, 0.0)),
        ((0.0, -7.5), (2.5, -7.5)),
        ((0.0, -10.0), (2.5, -10.0)),
        ((0.0, -17.5), (2.5, -17.5)),
        ((0.0, -20.0), (2.5, -20.0)),
        ((0.0, -27.5), (2.5, -27.5)),
        ((12.5, -10.0), (22.5, -10.0)),
        ((12.5, -20.0), (22.5, -20.0)),
        ((17.5, -30.0), (22.5, -30.0)),
    ):
        block.add_line(transform(start), transform(end))
    for center in ((17.5, -17.5), (17.5, -17.5), (17.5, -27.5), (17.5, -27.5)):
        block.add_lwpolyline(
            [
                (*transform((center[0] - 0.25, center[1])), 1.0),
                (*transform((center[0] + 0.25, center[1])), 1.0),
            ],
            format="xyb",
            close=True,
        )
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_REPEATED_COIL_PANEL",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_repeated_coil_panel_ignore_generalizes_across_rotation_and_scale() -> None:
    exact = _repeated_coil_panel_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="59cf96d51fc55afa4f77a383e0ecf990270dbafbbcd454943b3473039f1a9e5b",
    )
    unseen = _repeated_coil_panel_proposal(
        rotation_deg=31.0,
        scale=1.8,
        fingerprint="unseen-rotated-repeated-coil-panel",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.nonconnective_repeated_coil_panel_ignored.v1"
        assert applied["matched_family_rule_id"] == "repeated-three-row-semicircle-panel-v1"
        assert applied["ports"] == []
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
    assert apply_human_symbol_policy_to_proposal_row(unseen)["classifier_status"] == "MATCHED"


def test_repeated_coil_panel_same_counts_with_offset_arc_is_not_ignored() -> None:
    proposal = _repeated_coil_panel_proposal(
        rotation_deg=13.0,
        scale=1.3,
        fingerprint="unseen-offset-repeated-coil-panel",
        offset_arc=True,
    )

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] != "electrical.nonconnective_repeated_coil_panel_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def _dual_row_signal_panel_proposal(
    *, rotation_deg: float, scale: float, fingerprint: str, offset_circle: bool = False
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_DUAL_ROW_SIGNAL_PANEL")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    row_lines = (
        ((28.8748016716, -1.1226752197), (30.5518608986, 0.3773155632)),
        ((30.5518608986, 0.3773155632), (29.9731668847, -0.4756869211)),
        ((28.2081391014, -0.3773155632), (29.8851983284, 1.1226752197)),
        ((29.8851983284, 1.1226752197), (29.3065043145, 0.2696727354)),
        ((10.005, 0.0), (48.755, 0.0)),
    )
    for row_y in (0.0, -7.5):
        for start, end in row_lines:
            shifted_start = (start[0], start[1] + row_y)
            shifted_end = (end[0], end[1] + row_y)
            block.add_line(transform(shifted_start), transform(shifted_end))
        for min_x in (10.005, 46.255):
            block.add_lwpolyline(
                [
                    transform((min_x, row_y + 0.5)),
                    transform((min_x + 2.5, row_y + 0.5)),
                    transform((min_x + 2.5, row_y - 0.5)),
                    transform((min_x, row_y - 0.5)),
                ],
                close=True,
            )
        circle_center = (
            30.18 if offset_circle and row_y == -7.5 else 29.38,
            row_y,
        )
        block.add_circle(transform(circle_center), radius=1.25 * scale)
        for _ in range(4):
            block.add_hatch()
    for center_x in (0.0, 60.0):
        block.add_lwpolyline(
            [
                (*transform((center_x - 0.5, 0.0)), 1.0),
                (*transform((center_x + 0.5, 0.0)), 1.0),
            ],
            format="xyb",
            close=True,
        )
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_DUAL_ROW_SIGNAL_PANEL",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_dual_row_signal_panel_ignore_generalizes_across_rotation_and_scale() -> None:
    exact = _dual_row_signal_panel_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="c983989529487b8e3894fc9dfc0d0acab9c04fe6a66161f36b695e5c80571396",
    )
    unseen = _dual_row_signal_panel_proposal(
        rotation_deg=37.0,
        scale=1.9,
        fingerprint="unseen-rotated-dual-row-signal-panel",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.nonconnective_dual_row_signal_panel_ignored.v1"
        assert applied["matched_family_rule_id"] == "dual-row-hatched-circle-panel-v1"
        assert applied["classifier_status"] in {"HUMAN_CONFIRMED_MEMBER", "MATCHED"}
        assert applied["ports"] == []
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_dual_row_signal_panel_same_counts_with_offset_circle_is_not_ignored() -> None:
    proposal = _dual_row_signal_panel_proposal(
        rotation_deg=19.0,
        scale=1.4,
        fingerprint="unseen-offset-dual-row-signal-panel",
        offset_circle=True,
    )

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] != "electrical.nonconnective_dual_row_signal_panel_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def _dzb_right_marker_proposal(
    *, rotation_deg: float, scale: float, fingerprint: str, offset_short_duplicate: bool = False
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_DZB_RIGHT_MARKER")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    lines = (
        ((2.0, -2.0), (0.5, -2.0)),
        ((2.5, -1.5), (0.0, -1.5)),
        ((1.25, 0.0), (1.25, -1.5)),
        ((1.25, 0.0), (1.25, -1.5)),
        ((1.5, -2.5), (1.0, -2.5)),
        ((0.0, 0.0), (1.25, 0.0)),
    )
    for start, end in lines:
        block.add_line(transform(start), transform(end))
    duplicates = [lines[0], lines[1], lines[4]]
    if offset_short_duplicate:
        duplicates[-1] = ((1.5, -2.4), (1.0, -2.4))
    for start, end in duplicates:
        block.add_lwpolyline([transform(start), transform(end)])
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_DZB_RIGHT_MARKER",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_dzb_right_marker_ignore_generalizes_across_fingerprint_rotation_and_scale() -> None:
    exact = _dzb_right_marker_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="08a272799dbac4bf36f36ebcc1091f94b2273cf27fce8741a3cf31b150d5d123",
    )
    unseen = _dzb_right_marker_proposal(
        rotation_deg=37.0,
        scale=2.4,
        fingerprint="unseen-rotated-dzb-right-marker",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        expected_family = (
            "electrical.nonconnective_dzb_right_marker_ignored.v1"
            if proposal is exact
            else "electrical.nonconnective_stepped_marker_ignored.v1"
        )
        assert applied["family_id"] == expected_family
        assert applied["ports"] == []
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
    assert apply_human_symbol_policy_to_proposal_row(exact)["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert apply_human_symbol_policy_to_proposal_row(unseen)["classifier_status"] == "MATCHED"


def test_dzb_right_same_counts_with_offset_duplicate_is_not_geometry_ignored() -> None:
    proposal = _dzb_right_marker_proposal(
        rotation_deg=19.0,
        scale=1.7,
        fingerprint="unseen-offset-dzb-shape",
        offset_short_duplicate=True,
    )

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] != "electrical.nonconnective_dzb_right_marker_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def _three_lead_box_proposal(
    *, rotation_deg: float, scale: float, fingerprint: str, offset_right_lead: bool = False
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_THREE_LEAD_BOX")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    for points in (
        ((7.5, -7.5), (3.75, -7.5), (3.75, 1.875), (7.5, 1.875)),
        ((3.75, -5.625), (7.5, -5.625), (7.5, -7.5), (3.75, -7.5)),
    ):
        block.add_lwpolyline([transform(point) for point in points], close=True)
    right_start = (7.8, -2.5) if offset_right_lead else (7.5, -2.5)
    right_end = (11.55, -2.5) if offset_right_lead else (11.25, -2.5)
    for start, end in (
        ((0.0, -5.0), (3.75, -5.0)),
        ((3.75, -5.625), (7.5, -7.5)),
        (right_start, right_end),
        ((0.0, 0.0), (3.75, 0.0)),
    ):
        block.add_line(transform(start), transform(end))
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_THREE_LEAD_BOX",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_three_lead_box_ignore_generalizes_across_fingerprint_rotation_and_scale() -> None:
    exact = _three_lead_box_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="4f4abeddea8e309da9df83614ee3def2228b9e72a1f9a6e788b270ab13ec8fa1",
    )
    unseen = _three_lead_box_proposal(
        rotation_deg=41.0,
        scale=2.2,
        fingerprint="unseen-rotated-three-lead-box",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.nonconnective_three_lead_box_ignored.v1"
        assert applied["ports"] == []
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
    assert apply_human_symbol_policy_to_proposal_row(exact)["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert apply_human_symbol_policy_to_proposal_row(unseen)["classifier_status"] == "MATCHED"


def test_three_lead_box_same_counts_with_detached_lead_is_not_geometry_ignored() -> None:
    proposal = _three_lead_box_proposal(
        rotation_deg=23.0,
        scale=1.6,
        fingerprint="unseen-detached-three-lead-box",
        offset_right_lead=True,
    )

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["family_id"] != "electrical.nonconnective_three_lead_box_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def _named_four_contact_strip_proposal(
    *, rotation_deg: float, scale: float, fingerprint: str, offset_circle: bool = False
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_FOUR_CONTACT_STRIP")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    for start, end in (
        ((19.0, 0.0), (20.0, 0.0)),
        ((7.5, -2.5), (12.5, 0.0)),
        ((12.5, 0.0), (16.0, 0.0)),
        ((8.3838834765, 0.8838834765), (6.6161165235, -0.8838834765)),
        ((6.6161165235, 0.8838834765), (8.3838834765, -0.8838834765)),
        ((4.0, 0.0), (7.5, 0.0)),
        ((0.0, 0.0), (1.0, 0.0)),
    ):
        block.add_line(transform(start), transform(end))
    for center in (0.0, 2.5, 17.5, 20.0):
        block.add_lwpolyline(
            [transform((center - 0.5, 0.0)), transform((center + 0.5, 0.0))],
            format="xy",
            close=True,
        )
        polyline = list(block)[-1]
        polyline.set_points(
            [
                (*transform((center - 0.5, 0.0)), 1.0),
                (*transform((center + 0.5, 0.0)), 1.0),
            ],
            format="xyb",
        )
    right_circle = 17.0 if offset_circle else 17.5
    block.add_circle(transform((2.5, 0.0)), radius=1.5 * scale)
    block.add_circle(transform((right_circle, 0.0)), radius=1.5 * scale)
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_FOUR_CONTACT_STRIP",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_named_four_contact_strip_generalizes_with_external_ports_only() -> None:
    exact = _named_four_contact_strip_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="eec06b5aa9987f50b15e7871e0545c46d26b47ec64abdf9ff796d67c2e328bee",
    )
    unseen = _named_four_contact_strip_proposal(
        rotation_deg=37.0,
        scale=2.3,
        fingerprint="unseen-rotated-four-contact-strip",
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "component.external_strip_two_port.v1"
        assert applied["matched_family_rule_id"] == "four-contact-two-circle-named-strip-v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert len(applied["ports"]) == 2
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
    assert apply_human_symbol_policy_to_proposal_row(exact)["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert apply_human_symbol_policy_to_proposal_row(unseen)["classifier_status"] == "MATCHED"


def test_named_four_contact_strip_same_counts_with_offset_circle_stays_review() -> None:
    proposal = _named_four_contact_strip_proposal(
        rotation_deg=17.0,
        scale=1.4,
        fingerprint="unseen-offset-circle-strip",
        offset_circle=True,
    )

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["matched_family_rule_id"] != "four-contact-two-circle-named-strip-v1"
    assert applied["classifier_status"] != "MATCHED"
    assert applied["exact_human_member"] is False


def test_named_four_contact_strip_binds_ak_port_identities_to_own_networks() -> None:
    proposal = _named_four_contact_strip_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="unseen-named-four-contact-strip",
    )
    proposal["file_id"] = "F-AK"
    instance = {
        "symbol_instance_id": "SI-AK",
        "project_id": "P",
        "sheet_id": "S-AK",
        "file_id": "F-AK",
        "entity_handle": "H-AK",
        "definition_name": "RENAMED_FOUR_CONTACT_STRIP",
        "definition_fingerprint": "unseen-named-four-contact-strip",
        "transform_json": {
            "matrix44": [
                [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [100, 200, 0, 1]
            ]
        },
    }
    texts = [
        {"text_id": "T-AK", "handle": "HT-AK", "sheet_id": "S-AK", "file_id": "F-AK", "normalized_text": "AK", "insert_x": 110.0, "insert_y": 202.5},
        {"text_id": "T-1", "handle": "HT-1", "sheet_id": "S-AK", "file_id": "F-AK", "normalized_text": "1", "insert_x": 101.0, "insert_y": 199.0},
        {"text_id": "T-2", "handle": "HT-2", "sheet_id": "S-AK", "file_id": "F-AK", "normalized_text": "2", "insert_x": 119.0, "insert_y": 199.0},
    ]
    lines = [
        {"line_id": "L-LEFT", "handle": "HL-LEFT", "sheet_id": "S-AK", "file_id": "F-AK", "start_x": 100.0, "start_y": 200.0, "end_x": 90.0, "end_y": 200.0},
        {"line_id": "L-RIGHT", "handle": "HL-RIGHT", "sheet_id": "S-AK", "file_id": "F-AK", "start_x": 120.0, "start_y": 200.0, "end_x": 130.0, "end_y": 200.0},
    ]
    members = [
        {"member_type": "SOURCE_LINE", "source_handle": "HL-LEFT", "electrical_network_id": "NET-LEFT"},
        {"member_type": "SOURCE_LINE", "source_handle": "HL-RIGHT", "electrical_network_id": "NET-RIGHT"},
    ]

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )
    by_identity = {row["component_port_identity"]: row for row in rows}

    assert set(by_identity) == {"AK-1", "AK-2"}
    assert by_identity["AK-1"]["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
    assert by_identity["AK-1"]["attachment_side"] == "left"
    assert by_identity["AK-1"]["component_mapping_external_network_ids"] == ["NET-LEFT"]
    assert by_identity["AK-2"]["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
    assert by_identity["AK-2"]["attachment_side"] == "right"
    assert by_identity["AK-2"]["component_mapping_external_network_ids"] == ["NET-RIGHT"]
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)


def _named_two_row_box_proposal(
    *,
    rotation_deg: float,
    scale: float,
    fingerprint: str,
    offset_contact: bool = False,
) -> dict:
    document = ezdxf.new()
    child = document.blocks.new("RENAMED_TWO_ROW_STATE")
    child.add_point((0.0, 0.0))
    block = document.blocks.new("RENAMED_TWO_ROW_BOX")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    for insert in ((0.0, 0.0), (0.0, -10.0)):
        block.add_blockref(
            child.name,
            transform(insert),
            dxfattribs={
                "rotation": rotation_deg,
                "xscale": scale,
                "yscale": scale,
            },
        )
    block.add_lwpolyline(
        [
            transform((-2.5, 5.0)),
            transform((7.5, 5.0)),
            transform((7.5, -15.0)),
            transform((-2.5, -15.0)),
        ],
        close=True,
    )
    contact_centers = [(0.0, 0.0), (2.5, 2.5), (0.0, -10.0), (2.5, -7.5)]
    if offset_contact:
        contact_centers[-1] = (3.0, -7.5)
    for center_x, center_y in contact_centers:
        block.add_lwpolyline(
            [
                (*transform((center_x - 0.5, center_y)), 1.0),
                (*transform((center_x + 0.5, center_y)), 1.0),
            ],
            format="xyb",
            close=True,
        )
    return propose_ports_from_block(
        block,
        definition_name="RENAMED_TWO_ROW_BOX",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_named_two_row_box_exact_and_rotated_unseen_select_real_row_ports() -> None:
    exact = _named_two_row_box_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="55c2e04f990b264e93b235f7ed3c078a6034a853b3201192f447e7b346d8f06d",
    )
    unseen = _named_two_row_box_proposal(
        rotation_deg=31.0,
        scale=1.8,
        fingerprint="unseen-rotated-named-two-row-box",
    )

    assert exact["method"] == "named_two_row_box_ports_v1"
    assert [port["local_position"] for port in exact["ports"]] == [
        [0.0, 0.0, 0.0],
        [0.0, -10.0, 0.0],
    ]
    assert [port["component_pin"] for port in exact["ports"]] == ["1", "2"]
    assert [port["attachment_side"] for port in exact["ports"]] == [
        "upper",
        "lower",
    ]
    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "component.external_strip_two_port.v1"
        assert applied["matched_family_rule_id"] == "named-two-row-box-four-contact-v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert len(applied["ports"]) == 2
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
    assert apply_human_symbol_policy_to_proposal_row(exact)["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert apply_human_symbol_policy_to_proposal_row(unseen)["classifier_status"] == "MATCHED"


def test_named_two_row_box_offset_contact_is_not_promoted() -> None:
    proposal = _named_two_row_box_proposal(
        rotation_deg=19.0,
        scale=1.4,
        fingerprint="unseen-offset-named-two-row-box",
        offset_contact=True,
    )

    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied["matched_family_rule_id"] != "named-two-row-box-four-contact-v1"
    assert applied["exact_human_member"] is False


def test_named_two_row_box_binds_apostrophe_identity_to_upper_and_lower_networks() -> None:
    proposal = _named_two_row_box_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="unseen-bound-named-two-row-box",
    )
    proposal["file_id"] = "F-A-PRIME"
    instance = {
        "symbol_instance_id": "SI-A-PRIME",
        "project_id": "P",
        "sheet_id": "S-A-PRIME",
        "file_id": "F-A-PRIME",
        "entity_handle": "1D34C",
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
        {"text_id": "T-A-PRIME", "handle": "HT-A-PRIME", "sheet_id": "S-A-PRIME", "file_id": "F-A-PRIME", "normalized_text": "A'", "insert_x": 102.5, "insert_y": 205.0},
        {"text_id": "T-1", "handle": "HT-1", "sheet_id": "S-A-PRIME", "file_id": "F-A-PRIME", "normalized_text": "1", "insert_x": 99.0, "insert_y": 201.0},
        {"text_id": "T-2", "handle": "HT-2", "sheet_id": "S-A-PRIME", "file_id": "F-A-PRIME", "normalized_text": "2", "insert_x": 99.0, "insert_y": 191.0},
    ]
    lines = [
        {"line_id": "L-UPPER", "handle": "HL-UPPER", "sheet_id": "S-A-PRIME", "file_id": "F-A-PRIME", "start_x": 100.0, "start_y": 200.0, "end_x": 90.0, "end_y": 200.0},
        {"line_id": "L-LOWER", "handle": "HL-LOWER", "sheet_id": "S-A-PRIME", "file_id": "F-A-PRIME", "start_x": 100.0, "start_y": 190.0, "end_x": 90.0, "end_y": 190.0},
    ]
    members = [
        {"member_type": "SOURCE_LINE", "source_handle": "HL-UPPER", "electrical_network_id": "NET-UPPER"},
        {"member_type": "SOURCE_LINE", "source_handle": "HL-LOWER", "electrical_network_id": "NET-LOWER"},
    ]

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )
    by_identity = {row["component_port_identity"]: row for row in rows}

    assert set(by_identity) == {"A'-1", "A'-2"}
    assert by_identity["A'-1"]["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
    assert by_identity["A'-1"]["attachment_side"] == "upper"
    assert by_identity["A'-1"]["attached_line_handles"] == ["HL-UPPER"]
    assert by_identity["A'-1"]["component_mapping_external_network_ids"] == [
        "NET-UPPER"
    ]
    assert by_identity["A'-2"]["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
    assert by_identity["A'-2"]["attachment_side"] == "lower"
    assert by_identity["A'-2"]["attached_line_handles"] == ["HL-LOWER"]
    assert by_identity["A'-2"]["component_mapping_external_network_ids"] == [
        "NET-LOWER"
    ]
    assert all(row["relation_kind"] == "COMPONENT_PORT_TO_EXTERNAL_NETWORK" for row in rows)
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)


def _vertical_two_port_box_proposal(
    *,
    rotation_deg: float,
    scale: float,
    fingerprint: str,
    exact_name: bool = False,
    divider_offset: float = 0.0,
) -> dict:
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_VERTICAL_TWO_PORT_BOX")
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point[0] * scale, point[1] * scale
        return (x * cosine - y * sine, x * sine + y * cosine)

    for center_y in (-15.0, 15.0):
        block.add_lwpolyline(
            [
                (*transform((-0.5, center_y)), 1.0),
                (*transform((0.5, center_y)), 1.0),
            ],
            format="xyb",
            close=True,
        )
    for start, end in (
        ((-7.5, 15.0), (7.5, 15.0)),
        ((-7.5, 15.0), (-7.5, -15.0)),
        ((7.5, -15.0), (-7.5, -15.0)),
        ((-7.5, 7.5 + divider_offset), (7.5, 7.5 + divider_offset)),
        ((-7.5, -7.5), (7.5, -7.5)),
        ((7.5, 15.0), (7.5, -15.0)),
    ):
        block.add_line(transform(start), transform(end))
    block.add_text("1", dxfattribs={"insert": transform((-0.75, 9.8))})
    block.add_text("2", dxfattribs={"insert": transform((-0.75, -12.7))})
    return propose_ports_from_block(
        block,
        definition_name="KK1P" if exact_name else "RENAMED_VERTICAL_TWO_PORT_BOX",
        definition_fingerprint=fingerprint,
        max_ports=4,
    ).to_dict()


def test_vertical_two_port_box_exact_and_rotated_unseen_select_midpoint_ports() -> None:
    exact = _vertical_two_port_box_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="9321616869d2ccca1d1d6fc065a9a995ddf9d31ac8e207430b8eec6439e8ad6b",
        exact_name=True,
    )
    unseen = _vertical_two_port_box_proposal(
        rotation_deg=47.0,
        scale=2.2,
        fingerprint="unseen-rotated-vertical-two-port-box",
    )

    assert exact["method"] == "vertical_two_port_box_ports_v1"
    assert [port["local_position"] for port in exact["ports"]] == [
        [0.0, 15.0, 0.0],
        [0.0, -15.0, 0.0],
    ]
    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert [port["component_pin"] for port in applied["ports"]] == ["1", "2"]
        assert applied["family_id"] == "component.external_strip_two_port.v1"
        assert applied["matched_family_rule_id"] == "vertical-numbered-two-port-box-v1"
        assert applied["classifier_status"] in {"HUMAN_CONFIRMED_MEMBER", "MATCHED"}
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_vertical_two_port_box_offset_divider_stays_review() -> None:
    proposal = _vertical_two_port_box_proposal(
        rotation_deg=17.0,
        scale=1.5,
        fingerprint="unseen-offset-vertical-two-port-box",
        divider_offset=0.7,
    )
    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert applied.get("matched_family_rule_id") != "vertical-numbered-two-port-box-v1"


def test_vertical_two_port_box_binds_ak_to_measured_same_side_pairs() -> None:
    proposal = _vertical_two_port_box_proposal(
        rotation_deg=0.0,
        scale=1.0,
        fingerprint="unseen-bound-vertical-two-port-box",
    )
    proposal["file_id"] = "F"
    instance = {
        "symbol_instance_id": "SI-KK1P",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "H-KK1P",
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
        {"text_id": "TAK", "sheet_id": "S", "file_id": "F", "normalized_text": "AK", "insert_x": 100.0, "insert_y": 227.0},
        {"text_id": "TJD1", "sheet_id": "S", "file_id": "F", "normalized_text": "JD1", "insert_x": 100.0, "insert_y": 217.0},
        {"text_id": "TAP", "sheet_id": "S", "file_id": "F", "normalized_text": "A'-1", "insert_x": 100.0, "insert_y": 181.0},
    ]
    lines = [
        {"line_id": "L1", "handle": "HL1", "sheet_id": "S", "file_id": "F", "start_x": 100.0, "start_y": 215.0, "end_x": 100.0, "end_y": 216.0},
        {"line_id": "L2", "handle": "HL2", "sheet_id": "S", "file_id": "F", "start_x": 100.0, "start_y": 185.0, "end_x": 100.0, "end_y": 184.0},
    ]
    members = [
        {"member_type": "SOURCE_LINE", "source_handle": "HL1", "electrical_network_id": "NET-TOP"},
        {"member_type": "SOURCE_LINE", "source_handle": "HL2", "electrical_network_id": "NET-BOTTOM"},
    ]
    pairs = [
        {"pair_id": "P1", "sheet_id": "S", "pair_kind": "component_mapping", "left_value": "AK-1", "right_value": "JD1"},
        {"pair_id": "P2", "sheet_id": "S", "pair_kind": "component_mapping", "left_value": "AK-2", "right_value": "A'-1"},
    ]

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members, component_pairs=pairs
    )
    mappings = {
        row["component_port_identity"]: row["component_mapping_external_endpoints"]
        for row in rows
    }
    assert mappings == {"AK-1": ["JD1"], "AK-2": ["A'-1"]}
    assert all(row["status"] == "MEASURED_COMPONENT_PORT_MAPPING" for row in rows)
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)


def _communication_panel_block(*, include_groups: bool = True):
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_COMMUNICATION_PANEL")

    def add_rectangle(min_x: float, min_y: float, width: float, height: float) -> None:
        block.add_lwpolyline(
            [
                (min_x, min_y),
                (min_x + width, min_y),
                (min_x + width, min_y + height),
                (min_x, min_y + height),
            ],
            close=True,
        )

    groups = [
        ("COM1", 0.0, 10.0, 5),
        ("COM2", 35.0, 10.0, 5),
        ("CAN1", 70.0, 10.0, 3),
        ("COM3", 0.0, -10.0, 5),
        ("COM4", 35.0, -10.0, 5),
        ("CAN2", 70.0, -10.0, 3),
    ]
    for name, group_x, y, pin_count in groups:
        if include_groups:
            block.add_text(name, dxfattribs={"insert": (group_x, y)})
        for pin in range(1, pin_count + 1):
            min_x = group_x + 2.5 + (pin - 1) * 5.0
            add_rectangle(min_x, y - 2.5, 5.0, 5.0)
            block.add_text(
                str(pin),
                dxfattribs={"insert": (min_x + 2.5, y)},
            )

    for name, min_x, min_y in (
        ("LAN1", 90.0, 4.0),
        ("LAN2", 90.0, -16.0),
    ):
        add_rectangle(min_x, min_y, 12.5, 12.0)
        add_rectangle(min_x + 0.5, min_y + 10.5, 3.5, 1.4)
        add_rectangle(min_x + 8.5, min_y + 10.5, 3.5, 1.4)
        if include_groups:
            block.add_text(
                name,
                dxfattribs={"insert": (min_x + 3.0, min_y + 6.0)},
            )
    return block


def test_communication_panel_emits_all_pin_cells_and_geometry_only_lan_sockets() -> None:
    proposal = propose_ports_from_block(
        _communication_panel_block(),
        definition_name="RENAMED_COMMUNICATION_PANEL",
        definition_fingerprint="unseen-communication-panel",
        max_ports=4,
    ).to_dict()
    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    identities = [port["logical_port_identity"] for port in proposal["ports"]]
    features = proposal["geometry_summary"]["shape_features"]["communication_panel_features"]
    assert proposal["method"] == "repeated_communication_panel_ports_v1"
    assert len(proposal["ports"]) == 28
    assert identities[:5] == ["COM1-1", "COM1-2", "COM1-3", "COM1-4", "COM1-5"]
    assert identities[-2:] == ["LAN1", "LAN2"]
    assert features["mapped_cell_port_count"] == 26
    assert features["lan_socket_port_count"] == 2
    assert applied["family_id"] == "component.external_communication_panel.v1"
    assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
    assert applied["allow_internal_connectivity"] is False
    assert applied["allow_electrical_union"] is False


def test_many_numbered_rectangles_without_communication_groups_are_not_panel() -> None:
    proposal = propose_ports_from_block(
        _communication_panel_block(include_groups=False),
        definition_name="NUMBERED_RECTANGLE_ARRAY",
        definition_fingerprint="unseen-numbered-rectangle-array",
        max_ports=4,
    ).to_dict()
    applied = apply_human_symbol_policy_to_proposal_row(proposal)

    assert proposal["method"] != "repeated_communication_panel_ports_v1"
    assert applied["family_id"] != "component.external_communication_panel.v1"


def test_communication_panel_binding_requires_identity_label_and_exact_outward_line() -> None:
    proposal = {
        "file_id": "F-panel",
        "definition_name": "RENAMED_PANEL",
        "definition_fingerprint": "7248c0ad77ce6f3a36201f048652a9a63b49fa66a6541b1eb481ad44da886dd7",
        "ports": [
            {"port_id": "P1", "local_position": [0.0, 0.0, 0.0], "outward_direction": [0.0, 1.0, 0.0], "logical_port_identity": "COM1-3", "component_group": "COM1", "component_pin": "3", "attachment_side": "top"},
            {"port_id": "P2", "local_position": [10.0, -10.0, 0.0], "outward_direction": [0.0, -1.0, 0.0], "logical_port_identity": "COM2-4", "component_group": "COM2", "component_pin": "4", "attachment_side": "bottom"},
            {"port_id": "LAN", "local_position": [20.0, 0.0, 0.0], "outward_direction": [0.0, 1.0, 0.0], "logical_port_identity": "LAN1", "component_group": "LAN1", "attachment_side": "top"},
        ],
    }
    instance = {
        "symbol_instance_id": "SI-panel", "project_id": "P", "sheet_id": "S", "file_id": "F-panel",
        "entity_handle": "H-panel", "definition_name": "RENAMED_PANEL",
        "definition_fingerprint": proposal["definition_fingerprint"],
        "transform_json": {"matrix44": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [100, 200, 0, 1]]},
    }
    texts = [
        {"text_id": "T1", "handle": "HT1", "sheet_id": "S", "file_id": "F-panel", "normalized_text": "@1-42TD1", "insert_x": 100.0, "insert_y": 202.0},
        {"text_id": "T2", "handle": "HT2", "sheet_id": "S", "file_id": "F-panel", "normalized_text": "&1-42TD2", "insert_x": 110.0, "insert_y": 174.0},
    ]
    lines = [
        {"line_id": "L1", "handle": "HL1", "sheet_id": "S", "file_id": "F-panel", "start_x": 100.0, "start_y": 200.0, "end_x": 100.0, "end_y": 203.0},
        {"line_id": "L2", "handle": "HL2", "sheet_id": "S", "file_id": "F-panel", "start_x": 110.0, "start_y": 190.0, "end_x": 110.0, "end_y": 187.0},
    ]

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, []
    )
    by_identity = {row["component_port_identity"]: row for row in rows}

    assert by_identity["COM1-3"]["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
    assert by_identity["COM1-3"]["component_mapping_external_endpoints"] == ["1-42TD1"]
    assert by_identity["COM2-4"]["status"] == "MEASURED_COMPONENT_PORT_MAPPING"
    assert by_identity["COM2-4"]["component_mapping_external_endpoints"] == ["1-42TD2"]
    assert by_identity["LAN1"]["status"] == "PANEL_CELL_UNWIRED"
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)


def _kns_equipment_panel_proposal(*, fingerprint: str, omit_label: str | None = None) -> dict:
    text_values = [
        "PG", "P+", "P-", "1R", "1T", "ST", "+/L", "-/N", "PG",
        "A", "TX", "RX", "GND", "A", "B", "B",
        "COM1", "COM2", "COM3", "A", "TX", "RX", "GND", "A", "B", "B",
        "COM4", "COM5", "COM6",
    ]
    if omit_label is not None:
        text_values = [value for value in text_values if value != omit_label]
    return {
        "definition_name": "RENAMED_TALL_COMMUNICATION_EQUIPMENT",
        "definition_fingerprint": fingerprint,
        "ports": [
            {"port_id": "MP1", "local_position": [5.0, -107.5, 0.0]},
            {"port_id": "MP2", "local_position": [5.0, -7.5, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "width": 20.5,
                "height": 137.5,
                "oriented_aspect_ratio": 6.707317,
                "primitive_count": 47,
                "primitive_histogram": {"CIRCLE": 4, "LINE": 20, "LWPOLYLINE": 23},
                "entity_histogram": {"CIRCLE": 4, "INSERT": 1, "LINE": 20, "LWPOLYLINE": 23, "TEXT": len(text_values)},
                "text_count": len(text_values),
                "text_values": text_values,
                "arc_radii": [],
                "circle_radii": [2.363799, 2.363799, 3.056356, 3.056356],
                "closed_bulged_lwpolyline_count": 19,
                "parallel_line_group_max": 18,
            }
        },
    }


def test_kns_equipment_panel_exact_and_unseen_geometry_are_whole_region_ignore() -> None:
    for fingerprint in (
        "324c61d3d720cd06224bf81112169aa8a8cfdb5197a715181e376ea2cedfb2a5",
        "unseen-kns-equipment-panel",
    ):
        applied = apply_human_symbol_policy_to_proposal_row(
            _kns_equipment_panel_proposal(fingerprint=fingerprint)
        )

        assert applied["family_id"] == "communication.equipment_panel_ignored.v1"
        assert applied["ports"] == []
        assert applied["suppressed_by_policy"] is True
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
        if fingerprint.startswith("unseen"):
            assert applied["classifier_status"] == "MATCHED"


def test_dense_tall_panel_without_complete_com_and_optical_labels_is_not_ignored() -> None:
    for missing_label in ("COM6", "ST"):
        applied = apply_human_symbol_policy_to_proposal_row(
            _kns_equipment_panel_proposal(
                fingerprint=f"unseen-missing-{missing_label}",
                omit_label=missing_label,
            )
        )

        assert applied["family_id"] != "communication.equipment_panel_ignored.v1"
        assert applied["suppressed_by_policy"] is False


def _wide_ge_gx_switch_panel_proposal(
    *,
    fingerprint: str,
    angle_degrees: float = 0.0,
    scale: float = 1.0,
    omit_label: str | None = None,
    offset_circle_index: int | None = None,
) -> dict:
    labels = (
        [f"P{index}" for index in range(1, 25)]
        + [f"GE{index}" for index in range(1, 25)]
        + [f"GX{index}" for index in range(25, 29)]
        + [f"{index}{suffix}" for index in range(1, 5) for suffix in ("T", "R")]
        + ["Console", "FAULT", "PWR", "PWR1", "PWR2", "+/L", "-/N"]
    )
    if omit_label is not None:
        labels = [value for value in labels if value.upper() != omit_label.upper()]

    radius = 0.005
    gap_ratios = [3.36, 4.84, 3.36, 4.84, 3.36, 4.84, 3.36]
    positions = [0.0]
    for gap in gap_ratios:
        positions.append(positions[-1] + gap * radius)
    angle = math.radians(angle_degrees)
    axis = (math.cos(angle), math.sin(angle))
    normal = (-axis[1], axis[0])
    circles = []
    for index, position in enumerate(positions):
        normal_offset = radius * 0.25 if index == offset_circle_index else 0.0
        circles.append(
            {
                "center": [
                    0.2 + position * axis[0] + normal_offset * normal[0],
                    0.2 + position * axis[1] + normal_offset * normal[1],
                ],
                "radius": radius,
            }
        )

    return {
        "definition_name": "RENAMED_WIDE_SWITCH_PANEL",
        "definition_fingerprint": fingerprint,
        "ports": [
            {"port_id": "MP1", "local_position": [-175.0 * scale, -58.0 * scale, 0.0]},
            {"port_id": "MP2", "local_position": [175.0 * scale, -50.0 * scale, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "width": (380.0 if angle_degrees % 180 == 0 else 90.0) * scale,
                "height": (90.0 if angle_degrees % 180 == 0 else 380.0) * scale,
                "oriented_aspect_ratio": 4.222222,
                "primitive_count": 258,
                "primitive_histogram": {
                    "ARC": 24,
                    "CIRCLE": 8,
                    "LINE": 88,
                    "LWPOLYLINE": 138,
                },
                "entity_histogram": {
                    "ARC": 24,
                    "CIRCLE": 8,
                    "HATCH": 54,
                    "INSERT": 3,
                    "LINE": 88,
                    "LWPOLYLINE": 138,
                    "TEXT": 78,
                },
                "text_values": labels,
                "arc_radii": [0.1 * scale] * 24,
                "circle_radii": [2.132277 * scale] * 8,
                "closed_bulged_lwpolyline_count": 41,
                "normalized_circles": circles,
                "communication_panel_features": {
                    "square_cell_count": 25,
                    "dominant_cell_aspect": 1.03572,
                },
            }
        },
    }


def test_wide_ge_gx_switch_panel_exact_and_rotated_scaled_geometry_are_ignored() -> None:
    exact = apply_human_symbol_policy_to_proposal_row(
        _wide_ge_gx_switch_panel_proposal(
            fingerprint="9ab7144823696cf159b562ccd4a64c5801bdf99275c605494d4964302cc04bd1"
        )
    )
    unseen = apply_human_symbol_policy_to_proposal_row(
        _wide_ge_gx_switch_panel_proposal(
            fingerprint="unseen-wide-ge-gx-switch-panel",
            angle_degrees=90.0,
            scale=2.5,
        )
    )

    assert exact["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert unseen["classifier_status"] == "MATCHED"
    assert unseen["matched_family_rule_id"] == "wide-ge-gx-power-switch-panel-v1"
    for applied in (exact, unseen):
        assert applied["family_id"] == "communication.equipment_panel_ignored.v1"
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["ports"] == []
        assert applied["allow_port_emission"] is False
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_wide_switch_panel_requires_complete_arrays_and_collinear_circle_pitch() -> None:
    incomplete = apply_human_symbol_policy_to_proposal_row(
        _wide_ge_gx_switch_panel_proposal(
            fingerprint="unseen-wide-panel-missing-ge24",
            omit_label="GE24",
        )
    )
    displaced = apply_human_symbol_policy_to_proposal_row(
        _wide_ge_gx_switch_panel_proposal(
            fingerprint="unseen-wide-panel-displaced-circle",
            offset_circle_index=3,
        )
    )

    for applied in (incomplete, displaced):
        assert applied["family_id"] != "communication.equipment_panel_ignored.v1"
        assert applied["suppressed_by_policy"] is False


def _compact_ge_gx_switch_panel_proposal(
    *,
    fingerprint: str,
    angle_degrees: float = 0.0,
    scale: float = 1.0,
    omit_label: str | None = None,
    offset_circle_index: int | None = None,
) -> dict:
    labels = (
        [f"GE{index}" for index in range(1, 9)]
        + ["GX9", "GX10", "1GT", "1GR", "2GT", "2GR"]
        + ["Console", "+/L", "-/N"]
        + ["1", "2", "3", "4", "5", "6"]
    )
    if omit_label is not None:
        labels = [value for value in labels if value.upper() != omit_label.upper()]

    radius = 0.01
    angle = math.radians(angle_degrees)
    axis = (math.cos(angle), math.sin(angle))
    normal = (-axis[1], axis[0])
    circles = []
    for index, (axis_position, normal_position) in enumerate(
        ((0.0, 0.0), (0.0, 3.36), (9.38, 0.0), (9.38, 3.36))
    ):
        if index == offset_circle_index:
            normal_position += 0.8
        circles.append(
            {
                "center": [
                    0.2
                    + radius
                    * (axis_position * axis[0] + normal_position * normal[0]),
                    0.2
                    + radius
                    * (axis_position * axis[1] + normal_position * normal[1]),
                ],
                "radius": radius,
            }
        )

    return {
        "definition_name": "DGICOM3000-2GX8GE-HV",
        "definition_fingerprint": fingerprint,
        "ports": [
            {"port_id": "MP1", "local_position": [5.67 * scale, -152.57 * scale, 0.0]},
            {"port_id": "MP2", "local_position": [0.0, -15.0 * scale, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "width": 85.4 * scale,
                "height": 160.4 * scale,
                "oriented_aspect_ratio": 1.882353,
                "primitive_count": 128,
                "primitive_histogram": {
                    "ARC": 12,
                    "CIRCLE": 4,
                    "LINE": 60,
                    "LWPOLYLINE": 52,
                },
                "entity_histogram": {
                    "ARC": 12,
                    "CIRCLE": 4,
                    "HATCH": 18,
                    "INSERT": 1,
                    "LINE": 60,
                    "LWPOLYLINE": 52,
                    "TEXT": 32,
                },
                "text_values": labels,
                "arc_radii": [0.1 * scale] * 12,
                "circle_radii": [2.132277 * scale] * 4,
                "closed_bulged_lwpolyline_count": 18,
                "parallel_line_group_max": 29,
                "normalized_circles": circles,
                "communication_panel_features": {
                    "square_cell_count": 9,
                    "dominant_cell_aspect": 0.965512,
                },
            }
        },
    }


def test_compact_ge_gx_switch_panel_exact_and_rotated_scaled_geometry_are_ignored() -> None:
    exact = apply_human_symbol_policy_to_proposal_row(
        _compact_ge_gx_switch_panel_proposal(
            fingerprint="cb1abae65b4bcbd19aa91077fe008419f016357d08608f3712496374f8b8d325"
        )
    )
    unseen = apply_human_symbol_policy_to_proposal_row(
        _compact_ge_gx_switch_panel_proposal(
            fingerprint="unseen-compact-ge-gx-switch-panel",
            angle_degrees=57.0,
            scale=2.3,
        )
    )

    assert exact["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert unseen["classifier_status"] == "MATCHED"
    assert unseen["matched_family_rule_id"] == "compact-ge-gx-power-switch-panel-v1"
    for applied in (exact, unseen):
        assert applied["family_id"] == "communication.equipment_panel_ignored.v1"
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["ports"] == []
        assert applied["allow_port_emission"] is False
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_compact_switch_panel_requires_complete_labels_and_circle_grid() -> None:
    incomplete = apply_human_symbol_policy_to_proposal_row(
        _compact_ge_gx_switch_panel_proposal(
            fingerprint="unseen-compact-panel-missing-ge8",
            omit_label="GE8",
        )
    )
    displaced = apply_human_symbol_policy_to_proposal_row(
        _compact_ge_gx_switch_panel_proposal(
            fingerprint="unseen-compact-panel-displaced-circle",
            offset_circle_index=3,
        )
    )

    for applied in (incomplete, displaced):
        assert applied["family_id"] != "communication.equipment_panel_ignored.v1"
        assert applied["suppressed_by_policy"] is False


def _hykl_dual_row_panel_proposal(
    *,
    fingerprint: str,
    angle_degrees: float = 0.0,
    scale: float = 1.0,
    offset_contact_index: int | None = None,
) -> dict:
    angle = math.radians(angle_degrees)
    axis = (math.cos(angle), math.sin(angle))
    normal = (-axis[1], axis[0])
    circle_radius = 0.02 * scale
    small_radius = 0.00407 * scale
    circles = []
    contacts = []
    index = 0
    for row in (-1, 1):
        for column in range(4):
            axis_position = (column - 1.5) * 4.07 * circle_radius
            normal_position = row * 4.07 * circle_radius
            center = (
                0.3 + axis_position * axis[0] + normal_position * normal[0],
                0.4 + axis_position * axis[1] + normal_position * normal[1],
            )
            circles.append({"center": list(center), "radius": circle_radius})
            contact_offset = 1.02 * circle_radius
            if index == offset_contact_index:
                contact_offset = 1.5 * circle_radius
            contacts.append(
                {
                    "center": [
                        center[0] + row * contact_offset * normal[0],
                        center[1] + row * contact_offset * normal[1],
                    ],
                    "radius": small_radius,
                    "chord_radius": small_radius,
                }
            )
            index += 1
    contacts.append(
        {
            "center": [0.3, 0.4],
            "radius": 0.25 * scale,
            "chord_radius": 0.285 * scale,
        }
    )
    labels = [
        "PE2", "2", "2", "1", "OUT", "PE1", "1", "IN",
        "TX", "GND", "TX", "GND", "3", "3", "RX", "RX",
        "PE内部已短接",
    ]
    return {
        "definition_name": "HYKL-X12-02",
        "definition_fingerprint": fingerprint,
        "ports": [
            {"port_id": "MP1", "local_position": [-17.5 * scale, -35.0 * scale, 0.0]},
            {"port_id": "MP2", "local_position": [17.5 * scale, 35.0 * scale, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "width": 40.4 * scale,
                "height": 70.4 * scale,
                "oriented_aspect_ratio": 1.75,
                "primitive_count": 17,
                "primitive_histogram": {"CIRCLE": 8, "LWPOLYLINE": 9},
                "entity_histogram": {
                    "CIRCLE": 8,
                    "LWPOLYLINE": 9,
                    "TEXT": 16,
                    "MTEXT": 1,
                },
                "text_values": labels,
                "circle_radii": [2.458191 * scale] * 8,
                "closed_bulged_lwpolyline_count": 9,
                "normalized_circles": circles,
                "normalized_closed_bulged_contacts": contacts,
            }
        },
    }


def test_hykl_panel_exact_and_rotated_scaled_geometry_are_ignored() -> None:
    exact = apply_human_symbol_policy_to_proposal_row(
        _hykl_dual_row_panel_proposal(
            fingerprint="1726acf417090ce3ecbf6454bdb8321afb7c0025023b98e82d59a6b1476dd6dd"
        )
    )
    unseen = apply_human_symbol_policy_to_proposal_row(
        _hykl_dual_row_panel_proposal(
            fingerprint="unseen-rotated-hykl-panel",
            angle_degrees=61.0,
            scale=2.4,
        )
    )

    assert exact["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert unseen["classifier_status"] == "MATCHED"
    assert unseen["matched_family_rule_id"] == "dual-row-pe-tx-rx-interface-panel-v1"
    for applied in (exact, unseen):
        assert applied["family_id"] == "communication.equipment_panel_ignored.v1"
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["ports"] == []
        assert applied["allow_port_emission"] is False
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_hykl_panel_rejects_displaced_circle_contact_pair() -> None:
    applied = apply_human_symbol_policy_to_proposal_row(
        _hykl_dual_row_panel_proposal(
            fingerprint="unseen-hykl-displaced-contact",
            angle_degrees=23.0,
            scale=1.6,
            offset_contact_index=5,
        )
    )

    assert applied["family_id"] != "communication.equipment_panel_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def _firewall_eth_panel_proposal(
    *,
    fingerprint: str,
    angle_degrees: float = 0.0,
    scale: float = 1.0,
    omit_label: str | None = None,
    offset_large_circle: bool = False,
) -> dict:
    labels = (
        [f"ETH{index}" for index in range(0, 11)]
        + ["ETH12", "ETH13"]
        + [f"P{index}" for index in range(1, 13)]
        + [f"{index}{suffix}" for index in range(1, 5) for suffix in ("T", "R")]
        + ["USB", "Console", "L1", "N1", "PE1", "J1", "L2", "N2", "PE2", "J2"]
        + ["front", "rear", "device", "note"]
    )
    if omit_label is not None:
        labels = [value for value in labels if value.upper() != omit_label.upper()]
    angle = math.radians(angle_degrees)
    axis = (math.cos(angle), math.sin(angle))
    normal = (-axis[1], axis[0])

    def point(axis_position: float, normal_position: float) -> list[float]:
        return [
            0.3 + scale * (axis_position * axis[0] + normal_position * normal[0]),
            0.4 + scale * (axis_position * axis[1] + normal_position * normal[1]),
        ]

    small_radius = 0.004 * scale
    large_radius = 0.00672 * scale
    circles = [
        {"center": point(index * 3.2 * small_radius / scale, 0.0), "radius": small_radius}
        for index in range(4)
    ]
    axis_positions = (0.0, 3.36, 9.26, 12.62)
    for row in (-1, 1):
        for index, axis_position in enumerate(axis_positions):
            normal_position = row * 7.57
            if offset_large_circle and row == 1 and index == 2:
                normal_position += 0.8
            circles.append(
                {
                    "center": point(
                        axis_position * large_radius / scale,
                        normal_position * large_radius / scale,
                    ),
                    "radius": large_radius,
                }
            )
    return {
        "definition_name": "NGFW4000-UFTG-3100-GW",
        "definition_fingerprint": fingerprint,
        "ports": [
            {"port_id": "MP1", "local_position": [-94.0 * scale, -55.0 * scale, 0.0]},
            {"port_id": "MP2", "local_position": [152.0 * scale, -53.0 * scale, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "width": 380.4 * scale,
                "height": 97.9 * scale,
                "oriented_aspect_ratio": 3.897289,
                "primitive_count": 245,
                "primitive_histogram": {
                    "ARC": 24,
                    "CIRCLE": 12,
                    "LINE": 89,
                    "LWPOLYLINE": 120,
                },
                "entity_histogram": {
                    "ARC": 24,
                    "CIRCLE": 12,
                    "HATCH": 28,
                    "LINE": 89,
                    "LWPOLYLINE": 120,
                    "TEXT": 39,
                    "MTEXT": 8,
                },
                "text_values": labels,
                "closed_bulged_lwpolyline_count": 29,
                "parallel_line_group_max": 51,
                "normalized_circles": circles,
                "communication_panel_features": {
                    "square_cell_count": 13,
                    "dominant_cell_aspect": 1.03572,
                },
            }
        },
    }


def test_firewall_panel_exact_and_rotated_scaled_geometry_are_ignored() -> None:
    exact = apply_human_symbol_policy_to_proposal_row(
        _firewall_eth_panel_proposal(
            fingerprint="07d8f9b0bc6c61dd003c0d32861f58c0a1babc0be3cee88783f7dcbb4ab63e25"
        )
    )
    unseen = apply_human_symbol_policy_to_proposal_row(
        _firewall_eth_panel_proposal(
            fingerprint="unseen-rotated-firewall-panel",
            angle_degrees=38.0,
            scale=2.6,
        )
    )

    assert exact["classifier_status"] == "HUMAN_CONFIRMED_MEMBER"
    assert unseen["classifier_status"] == "MATCHED"
    assert unseen["matched_family_rule_id"] == "firewall-eth-usb-optical-power-panel-v1"
    for applied in (exact, unseen):
        assert applied["family_id"] == "communication.equipment_panel_ignored.v1"
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["ports"] == []
        assert applied["allow_port_emission"] is False
        assert applied["allow_external_attachment"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_firewall_panel_requires_complete_eth_labels_and_optical_grid() -> None:
    incomplete = apply_human_symbol_policy_to_proposal_row(
        _firewall_eth_panel_proposal(
            fingerprint="unseen-firewall-missing-eth13",
            omit_label="ETH13",
        )
    )
    displaced = apply_human_symbol_policy_to_proposal_row(
        _firewall_eth_panel_proposal(
            fingerprint="unseen-firewall-displaced-optical-circle",
            offset_large_circle=True,
        )
    )

    for applied in (incomplete, displaced):
        assert applied["family_id"] != "communication.equipment_panel_ignored.v1"
        assert applied["suppressed_by_policy"] is False


def _backplate_table_container_proposal(
    *, fingerprint: str, header_count: int = 4, max_row: int = 32
) -> dict:
    headers = ["NDY306A", "NKR308A(非电量选配)", "NTZ302A", "NPU316A"][:header_count]
    values = headers + [f"{row:02d}" for row in range(1, max_row + 1)] * 4
    values += [str(slot) for slot in range(1, 9)]
    return {
        "definition_name": "RENAMED_BACKPLATE_TABLE",
        "definition_fingerprint": fingerprint,
        "ports": [
            {"port_id": "MP1", "local_position": [-165.0, -90.0, 0.0]},
            {"port_id": "MP2", "local_position": [165.0, -15.0, 0.0]},
        ],
        "geometry_summary": {
            "shape_features": {
                "width": 380.0,
                "height": 205.0,
                "oriented_aspect_ratio": 1.853659,
                "primitive_count": 359,
                "primitive_histogram": {"LINE": 98, "LWPOLYLINE": 261},
                "entity_histogram": {"HATCH": 6, "INSERT": 1, "LINE": 98, "LWPOLYLINE": 261, "TEXT": 278},
                "text_count": 278,
                "text_values": values,
            }
        },
    }


def test_backplate_table_container_suppresses_outer_ports_but_preserves_table_route() -> None:
    for fingerprint in (
        "5299555132e52b11b5e4f3384c25f7e02a75673bd35ac5e632bceb33dcc9c2a5",
        "unseen-backplate-table-container",
    ):
        applied = apply_human_symbol_policy_to_proposal_row(
            _backplate_table_container_proposal(fingerprint=fingerprint)
        )

        assert applied["family_id"] == "structural.backplate_table_container.v1"
        assert applied["behavior_mode"] == "TABLE_CONTAINER"
        assert applied["ports"] == []
        assert applied["table_mapping_preserved"] is True
        assert applied["allow_port_emission"] is False
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
        if fingerprint.startswith("unseen"):
            assert applied["classifier_status"] == "MATCHED"
            assert applied["status"] == "GEOMETRY_FAMILY_TABLE_CONTAINER"


def test_dense_table_without_plugin_headers_or_full_row_grid_is_not_container() -> None:
    negatives = (
        _backplate_table_container_proposal(
            fingerprint="unseen-two-header-table", header_count=2
        ),
        _backplate_table_container_proposal(
            fingerprint="unseen-short-row-table", max_row=20
        ),
    )
    for proposal in negatives:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] != "structural.backplate_table_container.v1"
        assert applied["table_mapping_preserved"] is False


def test_backplate_table_container_emits_no_symbol_network_candidates() -> None:
    proposal = _backplate_table_container_proposal(
        fingerprint="5299555132e52b11b5e4f3384c25f7e02a75673bd35ac5e632bceb33dcc9c2a5"
    )
    instance = {
        "symbol_instance_id": "SI-backplate", "project_id": "P", "sheet_id": "S", "file_id": "F",
        "entity_handle": "388E1", "definition_name": "RENAMED_BACKPLATE_TABLE",
        "definition_fingerprint": proposal["definition_fingerprint"],
        "transform_json": {"matrix44": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [222.5, 257.5, 0, 1]]},
    }

    assert build_instance_port_network_candidates(
        [proposal], [instance], [], [], []
    ) == []


def _pwf4_ground_proposal(
    *, fingerprint: str, rotation_deg: float = 0.0, contact_offset: float = 0.0
) -> dict:
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> list[float]:
        x, y = point[0] * 2.0, point[1] * 2.0
        return [x * cosine - y * sine, x * sine + y * cosine]

    bars = [
        ((0.0, 0.4), (0.0, 0.6)),
        ((0.2, 0.2), (0.2, 0.8)),
        ((0.4, 0.0), (0.4, 1.0)),
    ]
    lead = ((1.0, 0.5), (0.4, 0.5))
    contact_center = transform((1.0 + contact_offset, 0.5))
    return {
        "definition_name": "RENAMED_CONTACT_GND",
        "definition_fingerprint": fingerprint,
        "ports": [{"port_id": "MP1"}, {"port_id": "MP2"}],
        "geometry_summary": {
            "shape_features": {
                "width": 5.5,
                "height": 5.0,
                "oriented_aspect_ratio": 1.1,
                "primitive_count": 8,
                "primitive_histogram": {"LINE": 4, "LWPOLYLINE": 4},
                "entity_histogram": {"LINE": 4, "LWPOLYLINE": 4},
                "text_count": 0,
                "text_values": [],
                "arc_radii": [],
                "circle_radii": [],
                "closed_bulged_lwpolyline_count": 1,
                "normalized_line_segments": [
                    {"start": transform(start), "end": transform(end)}
                    for start, end in (lead, *bars)
                ],
                "normalized_open_lwpolyline_segments": [
                    {"start": transform(start), "end": transform(end)}
                    for start, end in bars
                ],
                "normalized_closed_bulged_contacts": [
                    {"center": contact_center, "radius": 0.1 * 2.0}
                ],
            }
        },
    }


def test_pwf4_contact_ground_exact_and_rotated_unseen_are_ignored() -> None:
    variants = (
        _pwf4_ground_proposal(
            fingerprint="3f6efff7be570587c2e273a3f6755e21ff1e0b2036eec28ab5b07b5581e40a1e"
        ),
        _pwf4_ground_proposal(
            fingerprint="unseen-rotated-contact-ground", rotation_deg=37.0
        ),
    )
    for proposal in variants:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "electrical.ground_symbol_ignored.v1"
        assert applied["ports"] == []
        assert applied["behavior_mode"] == "IGNORE"
        assert applied["allow_external_attachment"] is False
        assert applied["allow_electrical_union"] is False


def test_pwf4_same_counts_with_detached_contact_is_not_ground() -> None:
    applied = apply_human_symbol_policy_to_proposal_row(
        _pwf4_ground_proposal(
            fingerprint="unseen-detached-contact", contact_offset=0.25
        )
    )
    assert applied["family_id"] != "electrical.ground_symbol_ignored.v1"
    assert applied["suppressed_by_policy"] is False


def _slash_circle_terminal_proposal(
    *, fingerprint: str, rotation_deg: float = 0.0, circle_offset: float = 0.0
) -> dict:
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> list[float]:
        x, y = point[0] * 2.0, point[1] * 2.0
        return [x * cosine - y * sine, x * sine + y * cosine]

    contact_centers = ((0.083333, 0.233308), (0.916667, 0.233308))
    circle_center = (0.5 + circle_offset, 0.233308)
    segments = (
        ((0.7, 0.233308), contact_centers[1]),
        (circle_center, (0.266692, 0.0)),
        (contact_centers[0], (0.3, 0.233308)),
        ((0.733308, 0.466616), circle_center),
    )
    return {
        "definition_name": "RENAMED_SLASH_TERMINAL",
        "definition_fingerprint": fingerprint,
        "ports": [{"port_id": "MP1"}, {"port_id": "MP2"}],
        "geometry_summary": {
            "shape_features": {
                "width": 6.0,
                "height": 2.799695,
                "oriented_aspect_ratio": 2.143091,
                "primitive_count": 7,
                "primitive_histogram": {"CIRCLE": 1, "LINE": 4, "LWPOLYLINE": 2},
                "entity_histogram": {"CIRCLE": 1, "LINE": 4, "LWPOLYLINE": 2},
                "text_count": 0,
                "text_values": [],
                "normalized_line_segments": [
                    {"start": transform(start), "end": transform(end)}
                    for start, end in segments
                ],
                "normalized_closed_bulged_contacts": [
                    {"center": transform(center), "radius": 0.083333 * 2.0}
                    for center in contact_centers
                ],
                "normalized_circles": [
                    {"center": transform(circle_center), "radius": 0.2 * 2.0}
                ],
            }
        },
    }


def test_slash_circle_terminal_exact_and_rotated_unseen_are_external_only() -> None:
    variants = (
        _slash_circle_terminal_proposal(
            fingerprint="8f7c185510e495dc79d94bdba73c1335ef0c64043045c388d16d039c52a0fc73"
        ),
        _slash_circle_terminal_proposal(
            fingerprint="unseen-rotated-slash-terminal", rotation_deg=37.0
        ),
    )
    for proposal in variants:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "labelled_terminal.generic.v1"
        assert applied["behavior_mode"] == "TERMINAL_NO_INTERNAL"
        assert len(applied["ports"]) == 2
        assert applied["allow_external_attachment"] is True
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_slash_circle_same_counts_with_offset_body_is_not_terminal() -> None:
    applied = apply_human_symbol_policy_to_proposal_row(
        _slash_circle_terminal_proposal(
            fingerprint="unseen-offset-slash-terminal", circle_offset=0.12
        )
    )
    assert applied["family_id"] != "labelled_terminal.generic.v1"
    assert applied["behavior_mode"] == "REVIEW_ONLY"


def _three_contact_socket_block(*, detach_contact: bool = False):
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_THREE_CONTACT_SOCKET")
    for start, end in (
        ((7.5, -5.0), (7.5, -7.5)),
        ((2.5, 0.0), (0.0, 0.0)),
        ((7.5, 5.0), (7.5, 7.5)),
        ((7.5, 0.0), (7.5, 0.0)),
    ):
        block.add_line(start, end)
    for center, radius in (
        ((8.75, -2.1650635), 2.0),
        ((8.75, 2.1650635), 2.0),
        ((5.0, 0.0), 2.0),
        ((7.5, 0.0), 5.0),
    ):
        block.add_circle(center, radius)
    contacts = [
        (7.5, 7.5),
        (8.75, 2.17),
        (7.5, -7.5),
        (8.75, -2.17),
        ((0.6 if detach_contact else 0.0), 0.0),
        (5.0, 0.0),
    ]
    for center in contacts:
        block.add_lwpolyline(
            [(center[0] - 0.5, center[1], 1.0), (center[0] + 0.5, center[1], 1.0)],
            format="xyb",
            close=True,
        )
    return block


def test_three_contact_socket_exact_and_unseen_emit_three_independent_ports() -> None:
    for fingerprint in (
        "9816226eb2abd1a692ea1af2ef528f5543dbfc10c8ca7d893de0692739019c6b",
        "unseen-three-contact-socket",
    ):
        proposal = propose_ports_from_block(
            _three_contact_socket_block(),
            definition_name="RENAMED_THREE_CONTACT_SOCKET",
            definition_fingerprint=fingerprint,
            max_ports=2,
        ).to_dict()
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert proposal["method"] == "three_contact_socket_ports_v1"
        assert len(proposal["ports"]) == 3
        assert applied["family_id"] == "component.external_multi_port.v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_three_contact_socket_same_counts_with_detached_contact_does_not_generalize() -> None:
    proposal = propose_ports_from_block(
        _three_contact_socket_block(detach_contact=True),
        definition_name="DETACHED_THREE_CONTACT_SOCKET",
        definition_fingerprint="unseen-detached-three-contact-socket",
    ).to_dict()
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied["family_id"] != "component.external_multi_port.v1"


def test_three_contact_socket_binds_cz_pins_to_network_scoped_endpoints() -> None:
    proposal = propose_ports_from_block(
        _three_contact_socket_block(),
        definition_name="RENAMED_THREE_CONTACT_SOCKET",
        definition_fingerprint="unseen-three-contact-binding",
    ).to_dict()
    proposal["file_id"] = "F"
    instance = {
        "symbol_instance_id": "SI-CZ", "project_id": "P", "sheet_id": "S", "file_id": "F",
        "entity_handle": "H-CZ", "definition_name": "RENAMED_THREE_CONTACT_SOCKET",
        "definition_fingerprint": "unseen-three-contact-binding",
        "transform_json": {"matrix44": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [332.488, 77.488, 0, 1]]},
    }
    texts = [
        {"text_id": "TCZ", "handle": "HCZ", "sheet_id": "S", "file_id": "F", "normalized_text": "CZ", "insert_x": 335.988, "insert_y": 82.488},
        {"text_id": "TE", "handle": "HE", "sheet_id": "S", "file_id": "F", "normalized_text": "E", "insert_x": 336.862, "insert_y": 76.294},
        {"text_id": "TL", "handle": "HL", "sheet_id": "S", "file_id": "F", "normalized_text": "L", "insert_x": 340.612, "insert_y": 78.464},
        {"text_id": "TN", "handle": "HN", "sheet_id": "S", "file_id": "F", "normalized_text": "N", "insert_x": 340.612, "insert_y": 74.124},
        {"text_id": "TJD11", "handle": "HJD11", "sheet_id": "S", "file_id": "F", "normalized_text": "JD11", "insert_x": 324.988, "insert_y": 79.888},
        {"text_id": "TJD2", "handle": "HJD2", "sheet_id": "S", "file_id": "F", "normalized_text": "JD2", "insert_x": 220.988, "insert_y": 89.988},
        {"text_id": "TJD7", "handle": "HJD7", "sheet_id": "S", "file_id": "F", "normalized_text": "JD7", "insert_x": 241.213, "insert_y": 67.488},
    ]
    lines = [
        {"line_id": "LE", "handle": "HEXT", "sheet_id": "S", "file_id": "F", "start_x": 332.488, "start_y": 77.488, "end_x": 327.488, "end_y": 77.488},
        {"line_id": "LL1", "handle": "HL1", "sheet_id": "S", "file_id": "F", "start_x": 339.988, "start_y": 84.988, "end_x": 339.988, "end_y": 89.988},
        {"line_id": "LL2", "handle": "HL2", "sheet_id": "S", "file_id": "F", "start_x": 339.988, "start_y": 89.988, "end_x": 227.488, "end_y": 89.988},
        {"line_id": "LN1", "handle": "HN1", "sheet_id": "S", "file_id": "F", "start_x": 339.988, "start_y": 69.988, "end_x": 339.988, "end_y": 64.988},
        {"line_id": "LN2", "handle": "HN2", "sheet_id": "S", "file_id": "F", "start_x": 339.988, "start_y": 64.988, "end_x": 237.488, "end_y": 64.988},
    ]
    members = [
        {"member_type": "SOURCE_LINE", "source_handle": handle, "electrical_network_id": network}
        for handle, network in (("HEXT", "ENE"), ("HL1", "ENL"), ("HL2", "ENL"), ("HN1", "ENN"), ("HN2", "ENN"))
    ]
    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )
    mappings = {
        row["component_port_identity"]: row["component_mapping_external_endpoints"]
        for row in rows
    }
    assert mappings == {"CZ-E": ["JD11"], "CZ-L": ["JD2"], "CZ-N": ["JD7"]}
    assert all(row["status"] == "MEASURED_COMPONENT_PORT_MAPPING" for row in rows)
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)


def _four_contact_isolated_frame_block(
    *, rotation_deg: float = 0.0, scale: float = 1.0, offset_outer_contact: bool = False
):
    document = ezdxf.new()
    block = document.blocks.new("RENAMED_KZKK_DEVICE")
    angle = math.radians(rotation_deg)

    def point(x: float, y: float) -> tuple[float, float]:
        return (
            scale * (x * math.cos(angle) - y * math.sin(angle)),
            scale * (x * math.sin(angle) + y * math.cos(angle)),
        )

    for start, end in (
        ((10.0, 8.75), (10.0, -1.25)),
        ((19.0, 0.0), (20.0, 0.0)),
        ((7.5, -2.5), (12.5, 0.0)),
        ((12.5, 0.0), (16.0, 0.0)),
        ((8.383883, 0.883883), (6.616117, -0.883883)),
        ((6.616117, 0.883883), (8.383883, -0.883883)),
        ((4.0, 0.0), (7.5, 0.0)),
        ((0.0, 0.0), (1.0, 0.0)),
        ((19.0, 10.0), (20.0, 10.0)),
        ((7.5, 7.5), (12.5, 10.0)),
        ((12.5, 10.0), (16.0, 10.0)),
        ((8.383883, 10.883883), (6.616117, 9.116117)),
        ((6.616117, 10.883883), (8.383883, 9.116117)),
        ((0.0, 10.0), (1.0, 10.0)),
        ((7.5, 10.0), (4.0, 10.0)),
    ):
        block.add_line(point(*start), point(*end))
    contacts = [
        (0.0, 0.0),
        (2.5, 0.0),
        (20.0, 0.0),
        (17.5, 0.0),
        (0.0, 10.0),
        (2.5, 10.0),
        (20.0, 10.0),
        (17.5, 10.0),
    ]
    if offset_outer_contact:
        contacts[0] = (0.4, 0.0)
    contact_radius = 0.5 * scale
    for center in contacts:
        transformed = point(*center)
        block.add_lwpolyline(
            [
                (transformed[0] - contact_radius * math.cos(angle), transformed[1] - contact_radius * math.sin(angle), 1.0),
                (transformed[0] + contact_radius * math.cos(angle), transformed[1] + contact_radius * math.sin(angle), 1.0),
            ],
            format="xyb",
            close=True,
        )
    for center in ((2.5, 0.0), (17.5, 0.0), (2.5, 10.0), (17.5, 10.0)):
        block.add_circle(point(*center), radius=1.5 * scale)
    return block


def test_four_contact_isolated_frame_exact_and_unseen_emit_four_independent_ports() -> None:
    cases = (
        (
            "deade9985bacdcfe78b87b08ce5dbb3b05a31ce41bc57086075826fe52baa56f",
            0.0,
            1.0,
            "HUMAN_CONFIRMED_MEMBER",
        ),
        ("unseen-four-contact-frame", 31.0, 1.7, "MATCHED"),
    )
    for fingerprint, rotation_deg, scale, expected_status in cases:
        definition_name = (
            "SYMB2_M_PWF102"
            if expected_status == "HUMAN_CONFIRMED_MEMBER"
            else "RENAMED_KZKK_DEVICE"
        )
        proposal = propose_ports_from_block(
            _four_contact_isolated_frame_block(
                rotation_deg=rotation_deg, scale=scale
            ),
            definition_name=definition_name,
            definition_fingerprint=fingerprint,
        ).to_dict()
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert len(applied["ports"]) == 4
        assert applied["classifier_status"] == expected_status
        assert applied["family_id"] == "component.external_multi_port.v1"
        assert applied["matched_family_rule_id"] == "four-contact-isolated-switch-frame-v1"
        assert applied["behavior_mode"] == "EXTERNAL_PORTS_ONLY"
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False


def test_four_contact_isolated_frame_rejects_offset_dual_grid() -> None:
    proposal = propose_ports_from_block(
        _four_contact_isolated_frame_block(offset_outer_contact=True),
        definition_name="OFFSET_KZKK_DEVICE",
        definition_fingerprint="unseen-offset-four-contact-frame",
    ).to_dict()
    applied = apply_human_symbol_policy_to_proposal_row(proposal)
    assert applied.get("matched_family_rule_id") != "four-contact-isolated-switch-frame-v1"


def test_four_contact_isolated_frame_binds_kzkk_same_side_endpoints() -> None:
    proposal = propose_ports_from_block(
        _four_contact_isolated_frame_block(),
        definition_name="RENAMED_KZKK_DEVICE",
        definition_fingerprint="unseen-four-contact-binding",
    ).to_dict()
    proposal["file_id"] = "F"
    instance = {
        "symbol_instance_id": "SI-KZKK",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F",
        "entity_handle": "H-KZKK",
        "definition_name": "RENAMED_KZKK_DEVICE",
        "definition_fingerprint": "unseen-four-contact-binding",
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
        {"text_id": "TK", "sheet_id": "S", "file_id": "F", "normalized_text": "KZKK", "insert_x": 110.0, "insert_y": 213.0},
        {"text_id": "T1", "sheet_id": "S", "file_id": "F", "normalized_text": "1", "insert_x": 102.0, "insert_y": 199.0},
        {"text_id": "T2", "sheet_id": "S", "file_id": "F", "normalized_text": "2", "insert_x": 117.0, "insert_y": 199.0},
        {"text_id": "T3", "sheet_id": "S", "file_id": "F", "normalized_text": "3", "insert_x": 102.0, "insert_y": 209.0},
        {"text_id": "T4", "sheet_id": "S", "file_id": "F", "normalized_text": "4", "insert_x": 117.0, "insert_y": 209.0},
        {"text_id": "TJD8", "sheet_id": "S", "file_id": "F", "normalized_text": "JD8", "insert_x": 86.0, "insert_y": 200.0},
        {"text_id": "TJD3", "sheet_id": "S", "file_id": "F", "normalized_text": "JD3", "insert_x": 86.0, "insert_y": 210.0},
        {"text_id": "T5", "sheet_id": "S", "file_id": "F", "normalized_text": "5", "insert_x": 132.0, "insert_y": 201.0},
        {"text_id": "T6", "sheet_id": "S", "file_id": "F", "normalized_text": "6", "insert_x": 132.0, "insert_y": 211.0},
        {"text_id": "TCD", "sheet_id": "S", "file_id": "F", "normalized_text": "CD-WSK-H-J-G", "insert_x": 125.0, "insert_y": 216.0},
    ]
    lines = [
        {"line_id": "L1", "handle": "HL1", "sheet_id": "S", "file_id": "F", "start_x": 100.0, "start_y": 200.0, "end_x": 90.0, "end_y": 200.0},
        {"line_id": "L2", "handle": "HL2", "sheet_id": "S", "file_id": "F", "start_x": 120.0, "start_y": 200.0, "end_x": 130.0, "end_y": 200.0},
        {"line_id": "L3", "handle": "HL3", "sheet_id": "S", "file_id": "F", "start_x": 100.0, "start_y": 210.0, "end_x": 90.0, "end_y": 210.0},
        {"line_id": "L4", "handle": "HL4", "sheet_id": "S", "file_id": "F", "start_x": 120.0, "start_y": 210.0, "end_x": 130.0, "end_y": 210.0},
    ]

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, []
    )
    mappings = {
        row["component_port_identity"]: row["component_mapping_external_endpoints"]
        for row in rows
    }
    assert mappings == {
        "KZKK-1": ["JD8"],
        "KZKK-2": ["CD-WSK-H-J-G-5"],
        "KZKK-3": ["JD3"],
        "KZKK-4": ["CD-WSK-H-J-G-6"],
    }
    assert all(row["status"] == "MEASURED_COMPONENT_PORT_MAPPING" for row in rows)
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)


def _four_way_slash_circle_terminal_proposal(
    *,
    fingerprint: str,
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    diagonal_offset: float = 0.0,
    contact_offset: float = 0.0,
) -> dict:
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)

    def transform(point: tuple[float, float]) -> list[float]:
        x, y = point[0] * scale, point[1] * scale
        return [x * cosine - y * sine, x * sine + y * cosine]

    center = (0.5, 0.416667)
    contact_centers = [
        (0.083333, 0.416667),
        (0.916667, 0.416667),
        (0.5 + contact_offset, 0.833333),
        (0.5, 0.0),
    ]
    radial_segments = [
        ((0.3, 0.416667), contact_centers[0]),
        ((0.7, 0.416667), contact_centers[1]),
        ((0.5, 0.616667), contact_centers[2]),
        ((0.5, 0.216667), contact_centers[3]),
    ]
    diagonal = (
        (0.261832, 0.178499 + diagonal_offset),
        (0.742122, 0.658789 + diagonal_offset),
    )
    ports = [
        {
            "port_id": "MP1",
            "local_position": [0.0, 0.0, 0.0],
            "outward_direction": [-1.0, 0.0, 0.0],
        },
        {
            "port_id": "MP2",
            "local_position": [5.0, 0.0, 0.0],
            "outward_direction": [1.0, 0.0, 0.0],
        },
        {
            "port_id": "MP3",
            "local_position": [2.5, -2.5, 0.0],
            "outward_direction": [0.0, -1.0, 0.0],
        },
        {
            "port_id": "MP4",
            "local_position": [2.5, 2.5, 0.0],
            "outward_direction": [0.0, 1.0, 0.0],
        },
    ]
    return {
        "file_id": "F-PWF89",
        "definition_name": "RENAMED_FOUR_WAY_TERMINAL",
        "definition_fingerprint": fingerprint,
        "ports": ports,
        "geometry_summary": {
            "shape_features": {
                "width": 6.0 * scale,
                "height": 5.0 * scale,
                "oriented_aspect_ratio": 1.2,
                "primitive_count": 10,
                "primitive_histogram": {
                    "CIRCLE": 1,
                    "LINE": 5,
                    "LWPOLYLINE": 4,
                },
                "entity_histogram": {
                    "CIRCLE": 1,
                    "LINE": 5,
                    "LWPOLYLINE": 4,
                },
                "text_count": 0,
                "text_values": [],
                "normalized_line_segments": [
                    {"start": transform(start), "end": transform(end)}
                    for start, end in [*radial_segments, diagonal]
                ],
                "normalized_closed_bulged_contacts": [
                    {
                        "center": transform(contact_center),
                        "radius": 0.083333 * scale,
                    }
                    for contact_center in contact_centers
                ],
                "normalized_circles": [
                    {"center": transform(center), "radius": 0.2 * scale}
                ],
            }
        },
    }


def test_four_way_terminal_exact_and_rotated_scaled_unseen_reuse_generic_family() -> None:
    exact = _four_way_slash_circle_terminal_proposal(
        fingerprint="84868127dc04f2454ab00c79d63b6d4a57792b2f47365725934a88bcf1986d65"
    )
    unseen = _four_way_slash_circle_terminal_proposal(
        fingerprint="unseen-rotated-scaled-four-way-terminal",
        rotation_deg=37.0,
        scale=1.7,
    )

    for proposal in (exact, unseen):
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["family_id"] == "labelled_terminal.generic.v1"
        assert applied["matched_family_rule_id"] == "four-orthogonal-contact-terminal-v1"
        assert applied["behavior_mode"] == "TERMINAL_NO_INTERNAL"
        assert len(applied["ports"]) == 4
        assert applied["allow_external_attachment"] is True
        assert applied["allow_internal_connectivity"] is False
        assert applied["allow_electrical_union"] is False
    assert exact["definition_name"] == unseen["definition_name"]
    assert apply_human_symbol_policy_to_proposal_row(unseen)["classifier_status"] == "MATCHED"


def test_four_way_terminal_same_counts_with_bad_topology_stays_review() -> None:
    negatives = (
        _four_way_slash_circle_terminal_proposal(
            fingerprint="unseen-off-centre-four-way-slash",
            diagonal_offset=0.12,
        ),
        _four_way_slash_circle_terminal_proposal(
            fingerprint="unseen-skewed-four-way-contact",
            contact_offset=0.12,
        ),
    )
    for proposal in negatives:
        applied = apply_human_symbol_policy_to_proposal_row(proposal)
        assert applied["matched_family_rule_id"] != "four-orthogonal-contact-terminal-v1"
        assert applied["family_id"] != "labelled_terminal.generic.v1"
        assert applied["behavior_mode"] == "REVIEW_ONLY"


def test_four_way_terminal_emits_only_wired_independent_jd1_attachments() -> None:
    proposal = _four_way_slash_circle_terminal_proposal(
        fingerprint="unseen-wired-four-way-terminal"
    )
    instance = {
        "symbol_instance_id": "SI-PWF89",
        "project_id": "P",
        "sheet_id": "S",
        "file_id": "F-PWF89",
        "entity_handle": "1D360",
        "definition_name": proposal["definition_name"],
        "definition_fingerprint": proposal["definition_fingerprint"],
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
        {
            "text_id": "T-JD1",
            "handle": "HT-JD1",
            "sheet_id": "S",
            "file_id": "F-PWF89",
            "normalized_text": "JD1",
            "insert_x": 12.5,
            "insert_y": 22.0,
        }
    ]
    lines = [
        {
            "line_id": "L-right",
            "handle": "H-right",
            "sheet_id": "S",
            "file_id": "F-PWF89",
            "start_x": 15.0,
            "start_y": 20.0,
            "end_x": 22.0,
            "end_y": 20.0,
        },
        {
            "line_id": "L-bottom",
            "handle": "H-bottom",
            "sheet_id": "S",
            "file_id": "F-PWF89",
            "start_x": 12.5,
            "start_y": 17.5,
            "end_x": 12.5,
            "end_y": 10.0,
        },
        {
            "line_id": "L-left-inward",
            "handle": "H-left-inward",
            "sheet_id": "S",
            "file_id": "F-PWF89",
            "start_x": 10.0,
            "start_y": 20.0,
            "end_x": 15.0,
            "end_y": 20.0,
        },
    ]
    members = [
        {
            "electrical_network_id": "EN-right",
            "member_type": "SOURCE_LINE",
            "source_handle": "H-right",
        },
        {
            "electrical_network_id": "EN-bottom",
            "member_type": "SOURCE_LINE",
            "source_handle": "H-bottom",
        },
    ]

    rows = build_instance_port_network_candidates(
        [proposal], [instance], texts, lines, members
    )

    assert len(rows) == 2
    assert {row["machine_port_id"] for row in rows} == {"MP2", "MP3"}
    assert {row["terminal_designator"] for row in rows} == {"JD1"}
    assert {tuple(row["external_network_ids"]) for row in rows} == {
        ("EN-right",),
        ("EN-bottom",),
    }
    assert all(row["status"] == "MEASURED_TERMINAL_ATTACHMENT" for row in rows)
    assert all(row["internal_connectivity_inferred"] is False for row in rows)
    assert all(row["electrical_union_eligible"] is False for row in rows)
