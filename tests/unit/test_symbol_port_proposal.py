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
