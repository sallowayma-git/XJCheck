from __future__ import annotations

from dataclasses import replace

import ezdxf
import pytest
from ezdxf.lldxf.types import DXFTag

from dwg_audit.audit import page_extractors
from dwg_audit.audit.page_extractors import (
    _shadow_authoritative_multi_endpoint_terminal_network_pairs,
)
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalPortBinding
from dwg_audit.domain.models import TextItem
from dwg_audit.extract.terminal_port_bindings import extract_terminal_port_bindings
from dwg_audit.utils.config import DEFAULT_CONFIG


def _vendor_terminal_document(**overrides):
    options = {
        "special_value": "装置端子",
        "reciprocal": True,
        "cross_appid_reciprocal": False,
        "lineno_match": True,
        "part_insert_match": True,
        "part_definition_match": True,
        "part_text_match": True,
        "connect_value_mode": "single",
        "connect_start": (0.0, 10.0),
        "connect_end": (10.0, 10.0),
        "connect_layer": "CONNECT",
        "extra_child": False,
        "duplicate_record": False,
        "odd_record": False,
        "duplicate_lineno": False,
    }
    options.update(overrides)

    document = ezdxf.new("R2018")
    for appid in (
        "LD_SYMB2_SPECIAL",
        "LD_SYMB2_TERM_TEXT_1",
        "LD_SYMB2_TERM_TEXT_2",
    ):
        document.appids.add(appid)
    block = document.blocks.new("GENERIC_TERMINAL")
    definition_line = block.add_line((0.0, 0.0), (2.5, 0.0))
    if options["extra_child"]:
        block.add_line((0.0, 0.0), (0.0, 2.5))

    modelspace = document.modelspace()
    insert = modelspace.add_blockref("GENERIC_TERMINAL", (10.0, 10.0))
    text = modelspace.add_text("77", dxfattribs={"insert": (10.0, 11.0)})
    connect = modelspace.add_line(
        options["connect_start"],
        options["connect_end"],
        dxfattribs={"layer": options["connect_layer"]},
    )
    insert.set_xdata(
        "LD_SYMB2_SPECIAL",
        [(1000, options["special_value"])],
    )
    for index, appid in enumerate(("LD_SYMB2_TERM_TEXT_1", "LD_SYMB2_TERM_TEXT_2"), 1):
        insert_handle = text.dxf.handle
        reciprocal_handle = insert.dxf.handle if options["reciprocal"] else "FFFF"
        if options["cross_appid_reciprocal"]:
            insert_handle = text.dxf.handle if index == 1 else "0"
            reciprocal_handle = "0" if index == 1 else insert.dxf.handle
        insert.set_xdata(appid, [(1000, appid[-1]), (1005, insert_handle)])
        text.set_xdata(appid, [(1005, reciprocal_handle)])

    connect_value = connect.dxf.handle
    if options["connect_value_mode"] == "multiple":
        connect_value = f"{connect.dxf.handle}||FFFF"
    elif options["connect_value_mode"] == "missing":
        connect_value = "FFFF"
    lineno_handle = insert.dxf.handle if options["lineno_match"] else "FFFF"
    part_insert_handle = insert.dxf.handle if options["part_insert_match"] else "FFFF"
    definition_token = (
        insert.dxf.name if options["part_definition_match"] else "OTHER_DEFINITION"
    )
    text_token = text.dxf.text if options["part_text_match"] else "88"
    lineno_value = f"terminal-{lineno_handle}:1"
    if options["duplicate_lineno"]:
        lineno_value += f" terminal-{lineno_handle}:2"
    record_tags = [
        DXFTag(1, "LINENO"),
        DXFTag(1, lineno_value),
        DXFTag(1, "LINECOLOR"),
        DXFTag(1, ""),
        DXFTag(1, "CONNECTLINEHANDLE"),
        DXFTag(1, connect_value),
        DXFTag(1, "PART2_1"),
        DXFTag(
            1,
            f"||scope||1||{text_token}||{definition_token}||"
            f"{part_insert_handle}||装置端子||forward||",
        ),
    ]
    if options["odd_record"]:
        record_tags.append(DXFTag(1, "TRAILING_KEY"))
    record = document.rootdict.add_xrecord("LD_TERMINAL_1")
    record.extend(record_tags)
    if options["duplicate_record"]:
        duplicate = document.rootdict.add_xrecord("LD_TERMINAL_2")
        duplicate.extend(record_tags)
    return document, {
        "insert": insert,
        "text": text,
        "connect": connect,
        "definition_line": definition_line,
        "record": record,
    }


def test_extract_terminal_port_binding_requires_complete_native_contract() -> None:
    document, entities = _vendor_terminal_document()

    bindings = extract_terminal_port_bindings(
        document,
        sheet_id="S-GENERIC",
        file_id="F-GENERIC",
    )

    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.insert_handle == entities["insert"].dxf.handle
    assert binding.text_handle == entities["text"].dxf.handle
    assert binding.connect_line_handle == entities["connect"].dxf.handle
    assert binding.definition_line_handle == entities["definition_line"].dxf.handle
    assert binding.xrecord_handle == entities["record"].dxf.handle
    assert binding.definition_name == "GENERIC_TERMINAL"
    assert binding.text_value == "77"
    assert (binding.insert_x, binding.insert_y) == pytest.approx((10.0, 10.0))
    assert (binding.port_x, binding.port_y) == pytest.approx((12.5, 10.0))
    assert binding.metadata_special == "装置端子"
    assert binding.electrical_union_eligible is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"special_value": "普通符号"},
        {"reciprocal": False},
        {"cross_appid_reciprocal": True},
        {"lineno_match": False},
        {"part_insert_match": False},
        {"part_definition_match": False},
        {"part_text_match": False},
        {"connect_value_mode": "multiple"},
        {"connect_value_mode": "missing"},
        {"connect_start": (20.0, 10.0), "connect_end": (30.0, 10.0)},
        {"connect_layer": "0"},
        {"extra_child": True},
        {"duplicate_record": True},
        {"odd_record": True},
        {"duplicate_lineno": True},
    ],
)
def test_extract_terminal_port_binding_fails_closed(overrides: dict[str, object]) -> None:
    document, _ = _vendor_terminal_document(**overrides)

    assert (
        extract_terminal_port_bindings(document, sheet_id="S1", file_id="F1")
        == []
    )


@pytest.mark.parametrize(
    "tolerance",
    [True, None, "0.25", "bad", 0.0, -1.0, float("nan"), float("inf")],
)
def test_extract_terminal_port_binding_rejects_invalid_tolerance(tolerance: object) -> None:
    document, _ = _vendor_terminal_document()

    assert extract_terminal_port_bindings(
        document,
        sheet_id="S1",
        file_id="F1",
        tolerance=tolerance,
    ) == []


def test_extract_terminal_port_binding_skips_malformed_xrecord() -> None:
    document, entities = _vendor_terminal_document()
    entities["record"].tags = None

    assert extract_terminal_port_bindings(document, sheet_id="S1", file_id="F1") == []


def _binding(index: int, *, x: float | None = None) -> TerminalPortBinding:
    port_x = float(index * 20 if x is None else x)
    return TerminalPortBinding(
        schema_version="terminal-port-binding-v1",
        sheet_id="S1",
        file_id="F1",
        insert_handle=f"A{index}",
        text_handle=f"B{index}",
        connect_line_handle=f"C{index}",
        definition_line_handle="D0",
        xrecord_handle=f"E{index}",
        xrecord_owner_handle="F0",
        definition_name="GENERIC_TERMINAL",
        text_value=f"V{index}",
        insert_x=port_x,
        insert_y=-2.5,
        connect_start_x=port_x,
        connect_start_y=-10.0,
        connect_end_x=port_x,
        connect_end_y=-2.5,
        port_line_start_x=port_x,
        port_line_start_y=-2.5,
        port_line_end_x=port_x,
        port_line_end_y=0.0,
        port_x=port_x,
        port_y=0.0,
    )


def _text(index: int) -> TextItem:
    value = f"V{index}"
    return TextItem(
        text_id=f"T{index}",
        sheet_id="S1",
        file_id="F1",
        handle=f"B{index}",
        entity_type="TEXT",
        text=value,
        normalized_text=value,
        is_numeric_candidate=False,
        layer="DIM",
        rotation_deg=0.0,
        height=2.5,
        insert_x=float(index * 20),
        insert_y=-1.0,
        bbox_min_x=float(index * 20),
        bbox_min_y=-1.0,
        bbox_max_x=float(index * 20 + 4),
        bbox_max_y=1.0,
    )


def _group(group_id: str = "G1", *, y: float = 0.0) -> LineGroup:
    return LineGroup(
        line_group_id=group_id,
        sheet_id="S1",
        file_id="F1",
        start_x=0.0,
        start_y=y,
        end_x=80.0,
        end_y=y,
        length=80.0,
        wire_candidate_score=0.55,
        member_line_ids=["L-NETWORK"],
        layer_hints=["0"],
        orientation="horizontal",
    )


def _ordinary_pair() -> Pair:
    return Pair(
        pair_id="P1",
        line_group_id="G1",
        sheet_id="S1",
        file_id="F1",
        selected_pair_candidate_id="PC1",
        left_value="V1",
        right_value="V3",
        confidence=0.78,
        status="review",
        rationale="left=V1 right=V3 score=0.78",
        alternative_pair_candidate_ids=["PC2"],
        confidence_bucket="review",
        evidence={
            "line_group_id": "G1",
            "selected_left_text_id": "T1",
            "selected_right_text_id": "T3",
            "selected_left_raw_text": "V1",
            "selected_right_raw_text": "V3",
            "pair_kind": "ordinary_pair",
        },
        left_text_id="T1",
        right_text_id="T3",
        pair_kind="ordinary_pair",
    )


def test_multi_endpoint_terminal_network_shadows_only_the_legacy_two_end_pair() -> None:
    pair = _ordinary_pair()
    bindings = [_binding(1), _binding(2), _binding(3)]

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group()],
        [_text(1), _text(2), _text(3)],
        bindings,
    )

    assert pair.status == "review"
    assert pair.alternative_pair_candidate_ids == ["PC2"]
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["ordinary_pair_shadow_only"] is True
    assert (
        pair.evidence["ordinary_pair_shadow_reason"]
        == "authoritative_multi_endpoint_terminal_network"
    )
    network = pair.evidence["authoritative_multi_endpoint_terminal_network"]
    assert network["port_count"] == 3
    assert [row["text_handle"] for row in network["ports"]] == ["B1", "B2", "B3"]
    assert [row["selected_by_ordinary_pair"] for row in network["ports"]] == [
        True,
        False,
        True,
    ]
    assert network["membership_complete"] is True
    assert network["canonical_endpoint_selected"] is False
    assert network["pairwise_relations_emitted"] is False
    assert network["internal_connectivity_inferred"] is False
    assert network["electrical_union_eligible"] is False


def test_multi_endpoint_terminal_network_requires_three_ports() -> None:
    pair = _ordinary_pair()

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group()],
        [_text(1), _text(3)],
        [_binding(1), _binding(3)],
    )

    assert pair.evidence.get("ordinary_pair_eligible") is not False


def test_multi_endpoint_terminal_network_shadows_pass_pair_without_changing_status() -> None:
    pair = _ordinary_pair()
    pair.status = "pass"

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group()],
        [_text(1), _text(2), _text(3)],
        [_binding(1), _binding(2), _binding(3)],
    )

    assert pair.status == "pass"
    assert pair.evidence["ordinary_pair_eligible"] is False


def test_multi_endpoint_terminal_network_rejects_group_intersection_ambiguity() -> None:
    pair = _ordinary_pair()

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group("G1"), _group("G2")],
        [_text(1), _text(2), _text(3)],
        [_binding(1), _binding(2), _binding(3)],
    )

    assert pair.evidence.get("ordinary_pair_eligible") is not False


@pytest.mark.parametrize(
    ("replacement", "texts"),
    [
        ({"text_handle": "B1"}, [_text(1), _text(2), _text(3)]),
        ({"insert_handle": "A1"}, [_text(1), _text(2), _text(3)]),
        ({"connect_line_handle": "C1"}, [_text(1), _text(2), _text(3)]),
        ({"xrecord_handle": "E1"}, [_text(1), _text(2), _text(3)]),
        ({"port_x": 20.1}, [_text(1), _text(2), _text(3)]),
        ({"port_x": float("nan")}, [_text(1), _text(2), _text(3)]),
        ({"electrical_union_eligible": True}, [_text(1), _text(2), _text(3)]),
        ({"metadata_special": "other"}, [_text(1), _text(2), _text(3)]),
        ({"sheet_id": None}, [_text(1), _text(2), _text(3)]),
        ({"file_id": ""}, [_text(1), _text(2), _text(3)]),
        ({"insert_handle": "NOT-A-HANDLE"}, [_text(1), _text(2), _text(3)]),
    ],
)
def test_multi_endpoint_terminal_network_rejects_malformed_membership(
    replacement: dict[str, object],
    texts: list[TextItem],
) -> None:
    pair = _ordinary_pair()
    third = replace(_binding(3), **replacement)

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group()],
        texts,
        [_binding(1), _binding(2), third],
    )

    assert pair.evidence.get("ordinary_pair_eligible") is not False


@pytest.mark.parametrize("tolerance", [True, None, "0.25", "bad"])
def test_multi_endpoint_terminal_network_rejects_invalid_tolerance(
    tolerance: object,
) -> None:
    pair = _ordinary_pair()

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group()],
        [_text(1), _text(2), _text(3)],
        [_binding(1), _binding(2), _binding(3)],
        tolerance=tolerance,
    )

    assert pair.evidence.get("ordinary_pair_eligible") is not False


def test_multi_endpoint_terminal_network_requires_selected_pair_text_ownership() -> None:
    pair = _ordinary_pair()
    texts = [_text(1), _text(2), replace(_text(3), handle="UNOWNED")]

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group()],
        texts,
        [_binding(1), _binding(2), _binding(3)],
    )

    assert pair.evidence.get("ordinary_pair_eligible") is not False


def test_multi_endpoint_terminal_network_requires_selected_text_value_identity() -> None:
    pair = _ordinary_pair()
    texts = [replace(_text(1), text="STALE"), _text(2), _text(3)]

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group()],
        texts,
        [_binding(1), _binding(2), _binding(3)],
    )

    assert pair.evidence.get("ordinary_pair_eligible") is not False


def test_multi_endpoint_terminal_network_requires_pair_evidence_identity() -> None:
    pair = _ordinary_pair()
    pair.evidence["selected_right_raw_text"] = "OTHER"

    _shadow_authoritative_multi_endpoint_terminal_network_pairs(
        [pair],
        [_group()],
        [_text(1), _text(2), _text(3)],
        [_binding(1), _binding(2), _binding(3)],
    )

    assert pair.evidence.get("ordinary_pair_eligible") is not False


def test_wire_diagram_route_applies_multi_endpoint_terminal_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pair = _ordinary_pair()
    group = _group()
    texts = [_text(1), _text(2), _text(3)]
    bindings = [_binding(1), _binding(2), _binding(3)]
    page = SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="generic.dwg",
        sheet_order=1,
        sheet_no="01",
        sheet_title="Generic",
        sheet_category="二次原理图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        route_target="WireDiagramExtractor",
    )
    monkeypatch.setattr(
        page_extractors,
        "build_line_groups",
        lambda *_args, **_kwargs: [group],
    )
    monkeypatch.setattr(
        page_extractors,
        "build_terminal_candidates",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        page_extractors,
        "build_pairs",
        lambda *_args, **_kwargs: ([], [pair]),
    )
    monkeypatch.setattr(
        page_extractors,
        "extract_component_prefixed_signal_pairs",
        lambda *_args, **_kwargs: [],
    )

    result = page_extractors.extract_wire_pairs(
        [page],
        texts,
        [],
        DEFAULT_CONFIG,
        terminal_port_bindings=bindings,
    )

    assert result.pairs == [pair]
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert (
        pair.evidence["authoritative_multi_endpoint_terminal_network"]["port_count"]
        == 3
    )
