from dwg_audit.audit.backplate_components import extract_accessory_backplate_two_port_pairs
from dwg_audit.audit.rules import build_issues
from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.domain.models import Pair
from dwg_audit.utils.config import DEFAULT_CONFIG


def _page() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="held-out.dwg",
        sheet_order=1,
        sheet_no="1",
        sheet_title="Accessories",
        sheet_category="背板接线图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=(0.0, 0.0, 200.0, 200.0),
    )


def _schematic_page() -> SheetRecord:
    page = _page()
    page.filename = "14 交流电压回路2.dwg"
    page.sheet_title = "VT INPUT 2"
    page.sheet_category = "二次原理图"
    page.route_target = "WireDiagramExtractor"
    return page


def _text(text_id: str, value: str, x: float, y: float, *, handle: str | None = None, block: str | None = None) -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
        file_id="F1",
        handle=handle or text_id,
        entity_type="TEXT",
        text=value,
        normalized_text=value,
        is_numeric_candidate=value.isdigit(),
        layer="MARK" if block is None else "0",
        rotation_deg=0.0,
        height=2.5,
        insert_x=x,
        insert_y=y,
        bbox_min_x=x - 1.0,
        bbox_min_y=y - 1.0,
        bbox_max_x=x + 1.0,
        bbox_max_y=y + 1.0,
        source_block_name=block,
    )


def _line(line_id: str, x: float, *, handle: str, y1: float = 80.0, y2: float = 100.0) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=handle,
        source_entity_type="LINE",
        layer="0",
        start_x=x,
        start_y=y1,
        end_x=x,
        end_y=y2,
        length=abs(y2 - y1),
        angle_deg=90.0,
        bbox_min_x=x,
        bbox_min_y=min(y1, y2),
        bbox_max_x=x,
        bbox_max_y=max(y1, y2),
        source_block_name="UNSEEN-CAPSULE",
    )


def _block() -> BlockRecord:
    return BlockRecord(
        block_id="B1",
        sheet_id="S1",
        file_id="F1",
        handle="H1",
        name="UNSEEN-CAPSULE",
        layer="0",
        insert_x=50.0,
        insert_y=90.0,
        rotation_deg=0.0,
        attributes_json="{}",
    )


def _custom_block(name: str = "UNSEEN-COMPONENT") -> BlockRecord:
    block = _block()
    block.name = name
    return block


def _owned_line(
    line_id: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    block: str = "UNSEEN-COMPONENT",
) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H1:VIRTUAL:{line_id}",
        source_entity_type="LINE",
        layer="0",
        start_x=x1,
        start_y=y1,
        end_x=x2,
        end_y=y2,
        length=((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5,
        angle_deg=0.0,
        bbox_min_x=min(x1, x2),
        bbox_min_y=min(y1, y2),
        bbox_max_x=max(x1, x2),
        bbox_max_y=max(y1, y2),
        source_block_name=block,
    )


def _free_horizontal_line(line_id: str, x1: float, x2: float, y: float = 80.0) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=line_id,
        source_entity_type="LINE",
        layer="CONNECT",
        start_x=x1,
        start_y=y,
        end_x=x2,
        end_y=y,
        length=abs(x2 - x1),
        angle_deg=0.0,
        bbox_min_x=min(x1, x2),
        bbox_min_y=y,
        bbox_max_x=max(x1, x2),
        bbox_max_y=y,
        source_block_name=None,
    )


def test_extracts_geometry_owned_two_port_component_without_name_memory() -> None:
    texts = [
        _text("P1", "1", 50.0, 97.5, handle="H1:VIRTUAL:1", block="UNSEEN-CAPSULE"),
        _text("P2", "2", 50.0, 82.5, handle="H1:VIRTUAL:0", block="UNSEEN-CAPSULE"),
        _text("BODY", "1KLP7", 50.0, 112.0),
        _text("TOP", "1KLP6-1, 1KLP8-1", 50.0, 103.0),
        _text("BOTTOM", "1n407", 50.0, 77.0),
    ]
    lines = [
        _line("L1", 47.5, handle="H1:VIRTUAL:2"),
        _line("L2", 52.5, handle="H1:VIRTUAL:3"),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [_block()])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1KLP7-1", "1KLP6-1"),
        ("1KLP7-1", "1KLP8-1"),
        ("1KLP7-2", "1n407"),
    }
    assert all(pair.evidence["electrical_union_eligible"] is False for pair in pairs)
    assert records[0]["component_count"] == 1
    assert set(records[0]["structural_text_ids"]) == {"P1", "P2", "BODY", "TOP", "BOTTOM"}
    issues = build_issues(pairs, [], [_page()], DEFAULT_CONFIG)
    assert not any(issue.rule_id == "R-ONE-TO-MANY" for issue in issues)


def test_recognizes_unconnected_component_without_inventing_mapping() -> None:
    texts = [
        _text("P1", "1", 50.0, 97.5, handle="H1:VIRTUAL:1", block="UNSEEN-CAPSULE"),
        _text("P2", "2", 50.0, 82.5, handle="H1:VIRTUAL:0", block="UNSEEN-CAPSULE"),
        _text("BODY", "LP1", 50.0, 112.0),
    ]
    lines = [
        _line("L1", 47.5, handle="H1:VIRTUAL:2"),
        _line("L2", 52.5, handle="H1:VIRTUAL:3"),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [_block()])

    assert pairs == []
    assert records[0]["component_count"] == 1
    assert records[0]["mappings"] == []


def test_rejects_two_digits_without_parallel_component_geometry() -> None:
    texts = [
        _text("P1", "1", 50.0, 97.5, handle="H1:VIRTUAL:1", block="UNSEEN-CAPSULE"),
        _text("P2", "2", 50.0, 82.5, handle="H1:VIRTUAL:0", block="UNSEEN-CAPSULE"),
        _text("BODY", "1KLP7", 50.0, 112.0),
    ]
    lines = [_line("L1", 47.5, handle="H1:VIRTUAL:2")]

    pairs, records = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [_block()])

    assert pairs == []
    assert records == []


def test_authoritative_geometry_chain_does_not_raise_many_to_one() -> None:
    def component_pair(
        pair_id: str,
        logical_endpoint: str,
        endpoint: str,
        raw_endpoint: str,
        group_id: str,
        coord_x: float,
    ) -> Pair:
        body, port = logical_endpoint.rsplit("-", 1)
        port_text_id = f"PORT-{group_id}"
        endpoint_text_id = f"END-{group_id}"
        return Pair(
            pair_id=pair_id,
            line_group_id=None,
            sheet_id="S1",
            file_id="F1",
            selected_pair_candidate_id=None,
            left_value=logical_endpoint,
            right_value=endpoint,
            confidence=0.97,
            status="pass",
            rationale="geometry-owned component",
            confidence_bucket="high",
            evidence={
                "source": "component_mapping",
                "component_submode": "strip_two_port_component",
                "mapping_mode": "accessory_backplate_two_port",
                "recognition_mode": "geometry_owned_two_port_capsule",
                "component_body": body,
                "component_body_text_id": f"BODY-{group_id}",
                "component_port": port,
                "component_port_text_id": port_text_id,
                "component_port_coord": [coord_x, 20.0],
                "component_block_name": "FJL-25-2A_Mirror",
                "component_block_handle": f"BLOCK-{group_id}",
                "external_endpoint": endpoint,
                "external_endpoint_raw": raw_endpoint,
                "external_endpoint_split": endpoint,
                "external_endpoint_text_id": endpoint_text_id,
                "external_endpoint_coord": [coord_x + 2.0, 21.0],
                "logical_endpoint": logical_endpoint,
                "endpoint_side": "top",
                "electrical_union_eligible": False,
                "internal_connectivity_inferred": False,
                "ordinary_pair_eligible": False,
            },
            left_text_id=port_text_id,
            right_text_id=endpoint_text_id,
            left_coord_x=coord_x,
            left_coord_y=20.0,
            right_coord_x=coord_x + 2.0,
            right_coord_y=21.0,
            pair_kind="component_mapping",
        )

    pairs = [
        component_pair("P1", "1KLP1-1", "1KLP2-1", "1KLP2-1,AUX1", "A", 10.0),
        component_pair("P1A", "1KLP1-1", "AUX1", "1KLP2-1,AUX1", "A", 10.0),
        component_pair("P2", "1KLP3-1", "1KLP2-1", "1KLP2-1,AUX2", "B", 30.0),
        component_pair("P2A", "1KLP3-1", "AUX2", "1KLP2-1,AUX2", "B", 30.0),
    ]

    issues = build_issues(pairs, [], [_page()], DEFAULT_CONFIG)

    assert not any(issue.rule_id == "R-MANY-TO-ONE" for issue in issues)


def test_extracts_unknown_opposed_port_panel_by_geometry() -> None:
    texts = [
        _text("P1", "1", 45.0, 100.0, handle="H1:VIRTUAL:1", block="UNSEEN-COMPONENT"),
        _text("P2", "2", 45.0, 80.0, handle="H1:VIRTUAL:2", block="UNSEEN-COMPONENT"),
        _text("P3", "3", 65.0, 100.0, handle="H1:VIRTUAL:3", block="UNSEEN-COMPONENT"),
        _text("P4", "4", 65.0, 80.0, handle="H1:VIRTUAL:4", block="UNSEEN-COMPONENT"),
        _text("BODY", "1DK", 55.0, 116.0),
        # A centered external terminal can look instance-like, but it is still
        # inside the endpoint band and must not replace the actual body label.
        _text("CENTER_ENDPOINT", "1U2D2", 55.0, 110.0),
        _text("E1", "ZD5", 45.0, 106.0),
        _text("E2", "1QD46", 45.0, 74.0),
        _text("E3", "ZD1", 65.0, 106.0),
        _text("E4", "1QD1", 65.0, 74.0),
    ]
    lines = [
        _owned_line("L1", 35.0, 105.0, 75.0, 105.0),
        _owned_line("L2", 35.0, 75.0, 75.0, 75.0),
        _owned_line("L3", 35.0, 75.0, 35.0, 105.0),
        _owned_line("L4", 75.0, 75.0, 75.0, 105.0),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [_custom_block()])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1DK-1", "ZD5"),
        ("1DK-2", "1QD46"),
        ("1DK-3", "ZD1"),
        ("1DK-4", "1QD1"),
    }
    assert records[0]["component_observations"][0]["recognition_mode"] == "geometry_owned_opposed_port_panel"
    assert records[0]["component_observations"][0]["component_instance"] == "1DK"


def test_extracts_unknown_inline_two_port_component_by_geometry() -> None:
    texts = [
        _text("P1", "1", 40.0, 80.0, handle="H1:VIRTUAL:1", block="UNSEEN-COMPONENT"),
        _text("P2", "2", 60.0, 80.0, handle="H1:VIRTUAL:2", block="UNSEEN-COMPONENT"),
        _text("BODY", "1F1", 50.0, 94.0),
        _text("LEFT", "1VD1", 30.0, 80.0),
        _text("RIGHT", "1n1701", 70.0, 80.0),
    ]
    lines = [
        _owned_line("L1", 46.0, 79.0, 54.0, 79.0),
        _owned_line("L2", 46.0, 81.0, 54.0, 81.0),
        _owned_line("L3", 46.0, 79.0, 46.0, 81.0),
        _owned_line("L4", 54.0, 79.0, 54.0, 81.0),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [_custom_block()])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1F1-1", "1VD1"),
        ("1F1-2", "1n1701"),
    }
    assert records[0]["component_observations"][0]["recognition_mode"] == "geometry_owned_inline_two_port"


def test_extracts_insert_backed_schematic_inline_two_port_component() -> None:
    block = _custom_block()
    block.insert_x = 40.0
    block.insert_y = 80.0
    texts = [
        _text("P1", "1", 39.4, 80.5),
        _text("P2", "2", 49.4, 80.5),
        _text("BODY", "1F1", 45.0, 82.5),
        _text("LEFT", "1VD1", 29.0, 82.0),
        _text("RIGHT", "1701", 80.0, 81.0),
    ]
    lines = [
        _free_horizontal_line("LEFT_LEAD", 30.0, 40.0),
        _free_horizontal_line("RIGHT_LEAD", 50.0, 80.0),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs([_schematic_page()], texts, lines, [block])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1F1-1", "1VD1"),
        ("1F1-2", "1701"),
    }
    observation = records[0]["component_observations"][0]
    assert observation["recognition_mode"] == "geometry_insert_backed_inline_two_port"
    assert observation["supporting_line_ids"] == ["LEFT_LEAD", "RIGHT_LEAD"]
    assert observation["internal_connectivity"] is False
    assert observation["electrical_union_eligible"] is False
    assert all(pair.evidence["ordinary_pair_eligible"] is False for pair in pairs)


def test_rejects_free_inline_labels_without_two_outward_leads() -> None:
    block = _custom_block()
    block.insert_x = 40.0
    block.insert_y = 80.0
    texts = [
        _text("P1", "1", 39.4, 80.5),
        _text("P2", "2", 49.4, 80.5),
        _text("BODY", "1F1", 45.0, 82.5),
        _text("LEFT", "1VD1", 29.0, 82.0),
        _text("RIGHT", "1701", 80.0, 81.0),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs(
        [_schematic_page()],
        texts,
        [_free_horizontal_line("LEFT_LEAD", 30.0, 40.0)],
        [block],
    )

    assert pairs == []
    assert records == []


def test_rejects_insert_merely_centered_between_unowned_inline_leads() -> None:
    block = _custom_block()
    block.insert_x = 45.0
    block.insert_y = 80.0
    texts = [
        _text("P1", "1", 39.4, 80.5),
        _text("P2", "2", 49.4, 80.5),
        _text("BODY", "1F1", 45.0, 82.5),
        _text("LEFT", "1VD1", 29.0, 82.0),
        _text("RIGHT", "1701", 80.0, 81.0),
    ]
    lines = [
        _free_horizontal_line("LEFT_LEAD", 30.0, 40.0),
        _free_horizontal_line("RIGHT_LEAD", 50.0, 80.0),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs(
        [_schematic_page()], texts, lines, [block]
    )

    assert pairs == []
    assert records == []


def test_does_not_apply_free_inline_schematic_model_to_backplate_page() -> None:
    block = _custom_block()
    block.insert_x = 40.0
    block.insert_y = 80.0
    texts = [
        _text("P1", "1", 39.4, 80.5),
        _text("P2", "2", 49.4, 80.5),
        _text("BODY", "1F1", 45.0, 82.5),
        _text("LEFT", "1VD1", 29.0, 82.0),
        _text("RIGHT", "1701", 80.0, 81.0),
    ]
    lines = [
        _free_horizontal_line("LEFT_LEAD", 30.0, 40.0),
        _free_horizontal_line("RIGHT_LEAD", 50.0, 80.0),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [block])

    assert pairs == []
    assert records == []


def test_extracts_only_externally_labelled_contact_ports() -> None:
    texts = [
        _text("P11", "11", 45.0, 90.0, handle="H1:VIRTUAL:11", block="UNSEEN-COMPONENT"),
        _text("P12", "12", 55.0, 90.0, handle="H1:VIRTUAL:12", block="UNSEEN-COMPONENT"),
        _text("P13", "13", 45.0, 80.0, handle="H1:VIRTUAL:13", block="UNSEEN-COMPONENT"),
        _text("P14", "14", 55.0, 80.0, handle="H1:VIRTUAL:14", block="UNSEEN-COMPONENT"),
        _text("BODY", "1FA", 50.0, 108.0),
        _text("LEFT", "1QD4", 35.0, 80.0),
        _text("RIGHT", "1QD35", 65.0, 80.0),
    ]
    lines = [
        _owned_line("L1", 50.0, 80.0, 50.0, 95.0),
        _owned_line("L2", 45.0, 85.0, 55.0, 85.0),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [_custom_block()])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1FA-13", "1QD4"),
        ("1FA-14", "1QD35"),
    }
    observation = records[0]["component_observations"][0]
    assert observation["internal_connectivity"] is False
    assert {port["port_number"] for port in observation["ports"]} == {"11", "12", "13", "14"}


def test_does_not_promote_narrow_jr_like_box_to_inline_component() -> None:
    texts = [
        _text("P1", "1", 45.0, 80.0, handle="H1:VIRTUAL:1", block="UNSEEN-COMPONENT"),
        _text("P2", "2", 52.5, 80.0, handle="H1:VIRTUAL:2", block="UNSEEN-COMPONENT"),
        _text("BODY", "JR", 48.75, 94.0),
        _text("LEFT", "K-3", 35.0, 80.0),
        _text("RIGHT", "K-4", 62.5, 80.0),
    ]
    lines = [
        _owned_line("L1", 43.0, 77.0, 55.0, 77.0),
        _owned_line("L2", 43.0, 83.0, 55.0, 83.0),
        _owned_line("L3", 43.0, 77.0, 43.0, 83.0),
        _owned_line("L4", 55.0, 77.0, 55.0, 83.0),
    ]

    pairs, records = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [_custom_block()])

    assert pairs == []
    assert records == []
