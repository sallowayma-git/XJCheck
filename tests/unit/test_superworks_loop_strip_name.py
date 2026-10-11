"""SuperWORKS terminal-strip identity: the strip's own name (DZ_SERIALNUMBER_NAME) is the prefix.

A continuation header ("上接1QD15") names the rows above it, not the strip. The identity of its
row 16 is "1QD16", not "上接1QD1516". Header text is kept as evidence and only checked.
"""
from __future__ import annotations

import ezdxf

from dwg_audit.extract.superworks_semantics import extract_superworks_semantics, bind_text_ids
from test_superworks_semantics import text_items


def _xdata(entity, app, values):
    if app not in entity.doc.appids:
        entity.doc.appids.new(app)
    entity.set_xdata(app, values)


def _strip(header_text, row_text, dz_name=None):
    """One terminal-strip row (TEXT with LD_DZPNO_HEADHANDLE) under a header TEXT."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    head = msp.add_text(header_text)
    row = msp.add_text(row_text)
    _xdata(head, "LD_DZPHEAD_NOHANDLE", [(1005, row.dxf.handle)])
    _xdata(row, "LD_DZPNO_HEADHANDLE", [(1005, head.dxf.handle)])
    if dz_name is not None:
        _xdata(row, "DZ_SERIALNUMBER_NAME", [(1000, dz_name)])
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    bind_text_ids(data, text_items(doc))
    assert len(data.strip_rows) == 1
    return data.strip_rows[0]


def test_continuation_header_takes_the_real_strip_name():
    row = _strip("上接1QD15", "16", dz_name="1QD")
    assert row.endpoint_identity == "1QD16"
    assert row.validation["strip_name"] == "1QD"
    assert row.validation["strip_name_source"] == "dz_serialnumber_name"
    assert row.validation["header_text"] == "上接1QD15"
    assert row.validation["header_mismatch"] is True
    # The header text is still the header of the strip row, not replaced.
    assert row.header["normalized"] == "上接1QD15"


def test_hyphenated_device_prefix_continuation_header():
    row = _strip("上接1-21QD15", "16", dz_name="1-21QD")
    assert row.endpoint_identity == "1-21QD16"
    assert row.validation["header_mismatch"] is True


def test_normal_header_identity_is_unchanged():
    row = _strip("7UD", "2", dz_name="7UD")
    assert row.endpoint_identity == "7UD2"
    assert row.validation["strip_name_source"] == "dz_serialnumber_name"
    assert row.validation["header_mismatch"] is False


def test_missing_dz_name_falls_back_to_header_logic():
    row = _strip("1XD", "2")
    assert row.endpoint_identity == "1XD2"
    assert row.validation["strip_name"] == "1XD"
    assert row.validation["strip_name_source"] == "header"
    assert row.validation["header_mismatch"] is False


def test_missing_dz_name_with_continuation_header_keeps_legacy_identity():
    # Fallback is the legacy concatenation; the continuation case is only fixed when the DZ name exists.
    row = _strip("上接1QD15", "16")
    assert row.endpoint_identity == "上接1QD1516"
    assert row.validation["strip_name_source"] == "header"
    assert row.validation["header_mismatch"] is False


def test_empty_header_text_uses_dz_name():
    row = _strip("", "5", dz_name="1C2D")
    assert row.endpoint_identity == "1C2D5"
    assert row.validation["header_mismatch"] is True


def _two_strip_rows():
    """Rows 16 (normal header "3-21GD") and 17 (continuation "上接3-21GD16") of one strip."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    rows = []
    for header_text, row_text in [("3-21GD", "16"), ("上接3-21GD16", "17")]:
        head = msp.add_text(header_text)
        row = msp.add_text(row_text)
        _xdata(head, "LD_DZPHEAD_NOHANDLE", [(1005, row.dxf.handle)])
        _xdata(row, "LD_DZPNO_HEADHANDLE", [(1005, head.dxf.handle)])
        _xdata(row, "DZ_SERIALNUMBER_NAME", [(1000, "3-21GD")])
        rows.append(row)
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    bind_text_ids(data, text_items(doc))
    return data


def test_continuation_row_is_in_the_same_strip_as_its_neighbour():
    from dwg_audit.audit.superworks_extractor import StripMembership, _strip_contract_fields
    data = _two_strip_rows()
    membership = StripMembership(data)
    # Both rows are the strip "3-21GD", whatever their header text says.
    assert membership.header_for("3-21GD17")[0] == "3-21GD"
    assert membership.header_for("3-21GD16")[0] == "3-21GD"
    fields = _strip_contract_fields(membership, "3-21GD17", (), "3-21GD16", ())
    assert fields.get("terminal_short_bridge") is True
    assert fields.get("strip_membership") == "same_strip"
    assert "terminal_cross_strip_link" not in fields


def _pair(pair_id, sheet, left, right, evidence):
    from dwg_audit.domain.models import Pair
    return Pair(pair_id=pair_id, line_group_id="G", sheet_id=sheet, file_id="F", selected_pair_candidate_id=None,
                left_value=left, right_value=right, confidence=0.99, status="pass", rationale="t",
                confidence_bucket="high", evidence=evidence, pair_kind="ordinary_pair")


def _cross_page_issues(pairs):
    from dwg_audit.audit import rules
    from dwg_audit.audit.rule_base import RuleContext, IssueFactory
    from dwg_audit.utils.ids import IdFactory
    ctx = RuleContext(pairs=pairs, line_groups=[], sheets=[], config={}, terminal_candidates=[],
                      high_threshold=0.92, duplicate_delta=0.08, reciprocal_required=False, group_map={}, sheet_map={},
                      issue_factory=IssueFactory(issue_ids=IdFactory("I"), group_map={}, sheet_map={}))
    return rules._run_cross_page_conflict(ctx)


def test_same_strip_short_does_not_make_a_cross_page_conflict():
    """3-21GD17 has a schematic partner on S8 and a short to 3-21GD16 (same strip) on S8 and S14.

    The short is a bridge (terminal_short_bridge), so 3-21GD16 is not a second independent destination.
    """
    ordinary = {"source": "superworks", "ordinary_pair_eligible": True, "electrical_union_eligible": False,
                "pair_kind": "ordinary_pair", "superworks": {"source": "superworks"}}
    bridge = {**ordinary, "terminal_short_bridge": True, "strip_membership": "same_strip"}
    pairs = [
        _pair("P1", "S8", "3-21GD17", "3-21QD31", ordinary),
        _pair("P2", "S8", "3-21GD17", "3-21GD16", bridge),
        _pair("P3", "S14", "3-21GD17", "3-21GD16", bridge),
    ]
    assert _cross_page_issues(pairs) == []


def test_uncorroborated_cross_strip_link_still_counts_as_a_destination():
    """The same shape without the bridge flag is a real second destination (control for the case above)."""
    ordinary = {"source": "superworks", "ordinary_pair_eligible": True, "electrical_union_eligible": False,
                "pair_kind": "ordinary_pair", "superworks": {"source": "superworks"},
                "terminal_cross_strip_link": True, "strip_corroborated": False}
    pairs = [
        _pair("P1", "S8", "3-21GD17", "3-21QD31", ordinary),
        _pair("P2", "S8", "3-21GD17", "3-21GD16", ordinary),
        _pair("P3", "S14", "3-21GD17", "3-21GD16", ordinary),
    ]
    issues = _cross_page_issues(pairs)
    assert [i.rule_id for i in issues] == ["R-CROSS-PAGE-CONFLICT"]
