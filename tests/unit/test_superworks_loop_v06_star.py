from __future__ import annotations

from dataclasses import replace

import pytest

from dwg_audit.audit.superworks_extractor import _clean_sw_endpoint_value, extract_superworks_pairs
from dwg_audit.domain.models import LineGroup, Pair, SheetRecord, SwConnectLabel, SwPartInstance
from dwg_audit.extract.superworks_semantics import SuperworksData


@pytest.mark.parametrize("raw,expected", [
    ("* 1n2107", "1n2107"),
    ("1I2D1 *", "1I2D1"),
    ("** 1ID1", "1ID1"),
    ("1Bn1 **", "1Bn1"),
    ("*1n2107*", "1n2107"),
    ("& 1KD5", "1KD5"),
    ("1KD5 &", "1KD5"),
    ("* & 1KD5 & *", "1KD5"),
])
def test_leading_and_trailing_decoration_is_removed(raw, expected):
    assert _clean_sw_endpoint_value(raw) == expected


@pytest.mark.parametrize("raw", [
    "1I*2D1",
    "1I&2",
    "A * B",
    "1-42TD1",
    "1n2107",
])
def test_interior_characters_are_kept(raw):
    assert _clean_sw_endpoint_value(raw) == raw


@pytest.mark.parametrize("raw,expected", [
    ("@1-42TD1", "@1-42TD1"),
    ("1-42TD1 @", "1-42TD1 @"),
    ("* 1-42TD1 @ *", "1-42TD1 @"),
    ("1-42TD1@c1", "1-42TD1@c1"),
])
def test_at_marker_is_not_stripped(raw, expected):
    assert _clean_sw_endpoint_value(raw) == expected


def test_full_width_decoration_is_normalised_before_stripping():
    assert _clean_sw_endpoint_value("＊ 1n2107") == "1n2107"


def _page():
    return SheetRecord("S1", "F1", "test.dwg", 1, "1", "test", "二次原理图", "primary", "filename", True,
                       audit_disposition="audit")


def _legacy_pair():
    return Pair("PW1", "GW1", "S1", "F1", None, "323", "323", .7, "review", "legacy",
                left_text_id="same", right_text_id="same")


def test_superworks_destination_is_clean_and_raw_text_is_kept():
    part = SwPartInstance("PART", "S1", "F1", insert_handle="A", label={"handle": "B", "text_id": "TB"})
    labels = [
        SwConnectLabel(f"C{n}", "S1", "F1", text={"handle": f"H{n}", "text_id": "DEST", "value": value},
                       part_id="PART", port_number=str(n), endpoint_identity=f"1DK-{n}")
        for n, value in [(1, "* ZD1"), (2, "ZD2 *")]
    ]
    old = replace(_legacy_pair(), pair_kind="component_mapping", right_text_id="DEST")
    output, _, _ = extract_superworks_pairs(
        SuperworksData(part_instances=[part], connect_labels=labels),
        pages=[_page()], texts=[], lines=[], line_groups=[LineGroup("GW1", "S1", "F1", 0, 0, 20, 0, 20, 1)],
        pairs=[old], table_mappings=[])
    assert {p.right_value for p in output} == {"ZD1", "ZD2"}
    assert {p.evidence["external_endpoint_raw"] for p in output} == {"* ZD1", "ZD2 *"}
    assert all("*" not in p.right_value and "&" not in p.right_value for p in output)
