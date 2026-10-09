"""Round-4 G: SuperWORKS false-positive exemptions (G1-G9) and their negative controls.

Every exemption here must remove only findings whose SuperWORKS evidence is
semantically equivalent to a legacy exemption. The negative cases keep real
conflicts visible.
"""

from __future__ import annotations

import pytest

from dwg_audit.audit import rules as R
from dwg_audit.audit.rule_base import RuleContext
from dwg_audit.audit.rule_base import IssueFactory
from dwg_audit.audit.series_chains import is_cross_view_terminal_series_chain
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.utils.config import DEFAULT_CONFIG
from dwg_audit.utils.ids import IdFactory


def _sheet(sheet_id: str) -> SheetRecord:
    return SheetRecord(
        sheet_id,
        sheet_id,
        f"{sheet_id}.dwg",
        1,
        "1",
        "WIRING",
        "wiring",
        "supplemental",
        "filename",
        True,
    )


def _ctx(pairs: list[Pair]) -> RuleContext:
    sheets = {pair.sheet_id: _sheet(pair.sheet_id) for pair in pairs}
    return RuleContext(
        pairs=pairs,
        line_groups=[],
        sheets=list(sheets.values()),
        config=DEFAULT_CONFIG,
        terminal_candidates=[],
        high_threshold=0.92,
        duplicate_delta=0.08,
        reciprocal_required=False,
        group_map={},
        sheet_map=sheets,
        issue_factory=IssueFactory(issue_ids=IdFactory("I"), group_map={}, sheet_map=sheets),
    )


def _plain(pair_id: str, sheet: str, left: str, right: str, *, evidence: dict | None = None,
           status: str = "pass", confidence: float = 0.99) -> Pair:
    return Pair(
        pair_id, f"G-{pair_id}", sheet, sheet, None, left, right, confidence, status,
        "round4 fixture", [], "high", dict(evidence or {}), pair_kind="ordinary_pair",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-R",
    )


def _component(pair_id: str, sheet: str, left: str, right: str, submode: str) -> Pair:
    return Pair(
        pair_id, f"G-{pair_id}", sheet, sheet, None, left, right, 0.99, "pass",
        "round4 component fixture", [], "high",
        {"source": "component_mapping", "component_submode": submode},
        pair_kind="component_mapping", left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-R",
    )


def _connect_pair(
    pair_id: str,
    sheet: str,
    logical: str,
    external: str,
    *,
    body: str = "1ZKK",
    port: str | None = None,
    source: str | None = "component_mapping",
    geometry_unique: bool = True,
) -> Pair:
    """SuperWORKS connect-line port (component_submode superworks_connect_line_port)."""
    port = port if port is not None else logical.rsplit("-", 1)[-1]
    evidence = {
        "structured_source": "component_mapping",
        "component_submode": "superworks_connect_line_port",
        "logical_endpoint": logical,
        "external_endpoint": external,
        "external_endpoint_raw": external,
        "external_endpoint_split": external,
        "external_endpoint_text_id": f"{pair_id}-EXT",
        "component_body": body,
        "component_body_text_id": f"{pair_id}-BODY",
        "component_port": port,
        "component_port_text_id": None,
        "component_block_name": body,
        "supporting_line_ids": [f"L-{pair_id}"],
        "ordinary_pair_eligible": False,
        "electrical_union_eligible": False,
        "superworks": {
            "source": "superworks",
            "part_id": f"SW:{sheet}:/{body}",
            "instance_path": f"/{body}",
            "symbol_handle": "SYM1",
            "port_id": f"PORT-{pair_id}",
            "label_handle": "LBL1",
            "connection_handle": "CON1",
            "connect_line_handle": "CL1",
            "connect_line_geometry_unique": geometry_unique,
            "port_resolution_method": "definition_text_nearest",
        },
        "sw_conflicts": [],
    }
    if source is not None:
        evidence["source"] = source
    return Pair(
        pair_id, None, sheet, sheet, None, logical, external, 0.99, "pass",
        "connect-line fixture", [], "high", evidence, pair_kind="component_mapping",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-EXT",
    )


def _sw_table_pair(
    pair_id: str,
    sheet: str,
    logical: str,
    terminal: str,
    *,
    side: str = "right",
    branch: str = "_1",
    row: int = 1,
    scope: str = "F1:STRIP1",
) -> Pair:
    """SuperWORKS terminal-header row; the terminal sits in the column named by side."""
    mapping = {
        "mapping_mode": "terminal_header_table",
        "sheet_id": sheet,
        "file_id": sheet,
        "header_prefix": "1UD",
        "header_text_id": f"HDR-{scope}",
        "row_number": row,
        "middle_value": str(row),
        "middle_text_id": f"MID-{pair_id}",
        "logical_endpoint": logical,
        "row_number_sequence_valid": True,
        "left_value": terminal if side == "left" else None,
        "left_text_id": f"{pair_id}-R" if side == "left" else None,
        "right_value": terminal if side == "right" else None,
        "right_text_id": f"{pair_id}-R" if side == "right" else None,
        "column_roles": {
            "left": "terminal_endpoint" if side == "left" else "empty",
            "middle": "row_number",
            "right": "terminal_endpoint" if side == "right" else "empty",
            "description": "empty",
        },
        "sw_branch": branch,
        "sw_side": side,
        "scope_key": scope,
        "same_strip_destination": False,
    }
    evidence = {
        "source": "superworks",
        "pair_kind": "table_mapping",
        "structured_source": "table_mapping",
        "table_mapping": mapping,
        "sw_conflicts": [],
        "sw_validation_reasons": [],
        "superworks": {
            "source": "superworks",
            "row_handle": f"RH-{pair_id}",
            "connection_handle": f"CH-{pair_id}",
            "side": side,
            "branch": branch,
        },
    }
    return Pair(
        pair_id, None, sheet, sheet, None, logical, terminal, 0.99, "pass",
        "sw strip row", [], "high", evidence, pair_kind="table_mapping",
        left_text_id=f"{pair_id}-LG", right_text_id=f"{pair_id}-R",
    )


def _issues(issues, rule_id: str):
    return [issue for issue in issues if issue.rule_id == rule_id]


# ---------------------------------------------------------------- G1 / G2 ----

def test_g1_connect_line_port_is_authoritative_component_mapping() -> None:
    pair = _connect_pair("C1", "S23", "1ZKK-1", "1YD3", source=None)

    assert R._authoritative_superworks_component_identity(pair) == ("1ZKK", "1", "1YD3")
    assert R._is_authoritative_component_mapping_pair(pair)


def test_g1_rejects_connect_line_port_without_unique_geometry() -> None:
    pair = _connect_pair("C1", "S23", "1ZKK-1", "1YD3", source=None, geometry_unique=False)

    assert R._authoritative_superworks_component_identity(pair) is None
    assert not R._is_authoritative_component_mapping_pair(pair)


def test_g2_identity_accepts_connect_line_port_without_legacy_submode() -> None:
    # The producer writes no legacy evidence["submode"]; the connect-line
    # component_submode is the component-diagram contract.
    pair = _connect_pair("C2", "S23", "1ZKK-1", "1YD3")
    assert "submode" not in pair.evidence

    assert R._authoritative_superworks_component_identity(pair) == ("1ZKK", "1", "1YD3")


def test_g2_rejects_connect_line_port_when_port_is_not_the_logical_suffix() -> None:
    pair = _connect_pair("C3", "S23", "1ZKK-2", "1YD3", port="1")

    assert R._authoritative_superworks_component_identity(pair) is None


# ------------------------------------------------------------------- G3 ----

def test_g3_same_schematic_port_in_two_views_is_one_corroborated_identity(monkeypatch) -> None:
    monkeypatch.setattr(R, "_is_authoritative_table_mapping_group", lambda pairs: True)
    schematic_a = _connect_pair("A", "S1", "1ZKK-1", "1YD3")
    schematic_b = _connect_pair("B", "S2", "1ZKK-1", "1YD3")
    backplate = Pair(
        "T", None, "S3", "S3", None, "1ZKK-1", "1YD3", 0.99, "pass", "backplate", [], "high",
        {"table_mapping": {"mapping_mode": "backplate_virtual_table"}},
        pair_kind="table_mapping",
    )

    assert R._is_authoritative_schematic_inline_backplate_endpoint_group([schematic_a, schematic_b, backplate])


def test_g3_distinct_schematic_ports_are_still_two_identities(monkeypatch) -> None:
    monkeypatch.setattr(R, "_is_authoritative_table_mapping_group", lambda pairs: True)
    schematic_a = _connect_pair("A", "S1", "1ZKK-1", "1YD3")
    schematic_b = _connect_pair("B", "S2", "1ZKK-2", "1YD3", port="2")
    backplate = Pair(
        "T", None, "S3", "S3", None, "1ZKK-1", "1YD3", 0.99, "pass", "backplate", [], "high",
        {"table_mapping": {"mapping_mode": "backplate_virtual_table"}},
        pair_kind="table_mapping",
    )

    assert not R._is_authoritative_schematic_inline_backplate_endpoint_group([schematic_a, schematic_b, backplate])


# ------------------------------------------------------------------- G4 ----

def test_g4_connect_line_port_joins_terminal_series_chain_with_strip_view() -> None:
    pairs = [
        _component("PT1", "S26", "1n2001", "1UD1", "terminal_strip_lattice"),
        _connect_pair("PK1", "S23", "1ZKK-1", "1UD1"),
    ]

    assert is_cross_view_terminal_series_chain(pairs)


def test_g4_two_connect_line_ports_on_one_sheet_remain_one_claim() -> None:
    pairs = [
        _component("PT1", "S26", "1n2001", "1UD1", "terminal_strip_lattice"),
        _connect_pair("PK1", "S23", "1ZKK-1", "1UD1"),
        _connect_pair("PK2", "S23", "1ZKK-2", "1UD1"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)


def test_g4_connect_line_port_corroborates_inline_view_of_the_same_port() -> None:
    pairs = [
        _component("PT1", "S26", "1n2001", "1UD1", "terminal_strip_lattice"),
        _component("PI1", "S23", "1ZKK-1", "1UD1", "inline_two_port_component"),
        _connect_pair("PK1", "S24", "1ZKK-1", "1UD1"),
    ]

    assert is_cross_view_terminal_series_chain(pairs)


# ------------------------------------------------------------------- G5 ----

@pytest.mark.parametrize(
    ("span", "members"),
    [
        ("7QD9~10", ("7QD9", "7QD10")),
        ("7UD16~18", ("7UD16", "7UD17")),
    ],
)
def test_g5_bridge_span_covers_its_member_terminals(span: str, members: tuple[str, str]) -> None:
    pairs = [
        _plain("M1", "S1", members[0], "1UD1"),
        _plain("M2", "S2", members[1], "1UD1"),
        _plain("SPAN", "S3", span, "1UD1"),
    ]

    assert not _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_g5_unrelated_terminal_still_conflicts_with_a_bridge_span() -> None:
    pairs = [
        _plain("M1", "S1", "7QD9", "1UD1"),
        _plain("M2", "S2", "7QD12", "1UD1"),
    ]

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_g5_span_on_a_different_terminal_does_not_hide_conflict() -> None:
    pairs = [
        _plain("M1", "S1", "7QD9", "1UD1"),
        _plain("M2", "S2", "7QD12", "1UD1"),
        _plain("SPAN", "S3", "7QD20~21", "1UD1"),
    ]

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


# ------------------------------------------------------------------- G6 ----

def test_g6_series_exemption_applies_to_the_non_bridge_subgroup() -> None:
    pairs = [
        _component("PT1", "S26", "1n2001", "1UD1", "terminal_strip_lattice"),
        _component("PK1", "S23", "1ZKK1-2", "1UD1", "kk_multi_port_component"),
        _plain("SPAN", "S27", "1QD39~40", "1UD1"),
    ]

    assert not _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_g6_non_chain_subgroup_is_still_reported() -> None:
    pairs = [
        _plain("M1", "S26", "1n2001", "1UD1"),
        _plain("M2", "S23", "1ZKK1-2", "1UD1"),
        _plain("SPAN", "S27", "1QD39~40", "1UD1"),
    ]

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


# ------------------------------------------------------------------- G7 ----

def test_g7_corroborated_cross_strip_link_is_a_bridge_claim() -> None:
    pair = _plain(
        "X1", "S1", "1QD4", "1QD7",
        evidence={"terminal_cross_strip_link": True, "strip_corroborated": True,
                  "strip_headers": ["H1", "H2"]},
    )

    assert R._is_terminal_strip_bridge_claim(pair)


@pytest.mark.parametrize(
    "evidence",
    [
        {"terminal_cross_strip_link": True, "strip_corroborated": False, "strip_headers": ["H1", "H2"]},
        {"terminal_cross_strip_link": True, "strip_headers": ["H1", "H2"]},
        {"strip_membership": "unknown"},
    ],
)
def test_g7_uncorroborated_cross_strip_link_stays_an_ordinary_pair(evidence: dict) -> None:
    pair = _plain("X1", "S1", "1QD4", "1QD7", evidence=evidence)

    assert not R._is_terminal_strip_bridge_claim(pair)


def test_g7_corroborated_cross_strip_link_does_not_count_as_a_competing_value() -> None:
    link = _plain(
        "X1", "S1", "1QD4", "1UD1",
        evidence={"terminal_cross_strip_link": True, "strip_corroborated": True,
                  "strip_headers": ["H1", "H2"]},
    )
    pairs = [_plain("M1", "S2", "1n2001", "1UD1"), link]

    assert not _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_g7_uncorroborated_cross_strip_link_still_counts() -> None:
    link = _plain(
        "X1", "S1", "1QD4", "1UD1",
        evidence={"terminal_cross_strip_link": True, "strip_corroborated": False,
                  "strip_headers": ["H1", "H2"]},
    )
    pairs = [_plain("M1", "S2", "1n2001", "1UD1"), link]

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


# ------------------------------------------------------------------- G8 ----

def _one_end_pairs(*, with_strip_rows: tuple[str, ...]) -> list[Pair]:
    pairs = [
        _plain("SCH1", "S09", "KD23", "1-2QD8"),
        _plain("SCH2", "S13", "KD23", "1-2QD7"),
    ]
    rows = {
        "1-2QD7": _sw_table_pair("ROW7", "S13", "1-2QD7", "KD23", side="right", branch="_1", row=7),
        "1-2QD8": _sw_table_pair("ROW8", "S09", "1-2QD8", "KD23", side="right", branch="_1", row=8),
    }
    pairs.extend(rows[name] for name in with_strip_rows)
    return pairs


def test_g8_strip_recorded_one_end_multi_wire_is_not_a_cross_page_conflict() -> None:
    pairs = _one_end_pairs(with_strip_rows=("1-2QD7", "1-2QD8"))

    assert not _issues(R._run_cross_page_conflict(_ctx(pairs)), "R-CROSS-PAGE-CONFLICT")


def test_g8_many_to_one_report_is_kept_because_baseline_real_issues_share_this_shape() -> None:
    """G8 is applied to R-CROSS-PAGE-CONFLICT only. On round-3 data the same strip-recorded
    shape removes 11 of the 13 baseline-real R-MANY-TO-ONE issues (e.g. KD26 on p038), so the
    many-to-one report must survive it."""
    pairs = _one_end_pairs(with_strip_rows=("1-2QD7", "1-2QD8"))

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_g8_missing_strip_record_keeps_cross_page_conflict() -> None:
    pairs = _one_end_pairs(with_strip_rows=())

    assert _issues(R._run_cross_page_conflict(_ctx(pairs)), "R-CROSS-PAGE-CONFLICT")


def test_g8_partial_strip_record_keeps_cross_page_conflict() -> None:
    pairs = _one_end_pairs(with_strip_rows=("1-2QD7",))

    assert _issues(R._run_cross_page_conflict(_ctx(pairs)), "R-CROSS-PAGE-CONFLICT")


# ------------------------------------------------------------------- G9 ----

def test_g9_range_and_its_member_are_one_end_across_pages() -> None:
    pairs = [
        _plain("R1", "S09", "1ZKK1", "1-4Q1D7~8"),
        _plain("R2", "S13", "1ZKK1", "1-4Q1D7"),
    ]

    assert not _issues(R._run_cross_page_conflict(_ctx(pairs)), "R-CROSS-PAGE-CONFLICT")


def test_g9_unrelated_member_still_conflicts_across_pages() -> None:
    pairs = [
        _plain("R1", "S09", "1ZKK1", "1-4Q1D7~8"),
        _plain("R2", "S13", "1ZKK1", "1-4Q1D9"),
    ]

    assert _issues(R._run_cross_page_conflict(_ctx(pairs)), "R-CROSS-PAGE-CONFLICT")


def test_g9_values_are_one_end_only_when_one_range_contains_the_rest() -> None:
    assert R._values_are_one_terminal_end(["1-4Q1D7~8", "1-4Q1D7"])
    assert R._values_are_one_terminal_end(["1-4Q1D7~8", "1-4Q1D8"])
    assert not R._values_are_one_terminal_end(["1-4Q1D7~8", "1-4Q1D9"])
    assert not R._values_are_one_terminal_end(["1-4Q1D7", "1-4Q1D8"])


# ------------------------------------------------- SW table column contract ----

@pytest.mark.parametrize("side", ["right", "left"])
def test_sw_table_kind_reads_the_endpoint_column(side: str) -> None:
    pair = _sw_table_pair("T1", "S17", "7UD16", "1UD4", side=side)

    assert R._superworks_structured_source_kind(pair) == "table_mapping"


def test_sw_table_kind_rejects_endpoint_value_from_the_wrong_column() -> None:
    pair = _sw_table_pair("T1", "S17", "7UD16", "1UD4", side="left")
    pair.evidence["table_mapping"]["left_value"] = "1UD9"

    assert R._superworks_structured_source_kind(pair) is None
