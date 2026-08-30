from dwg_audit.audit.rules import build_issues
from dwg_audit.audit.series_chains import build_terminal_series_chains
from dwg_audit.audit.series_chains import is_cross_view_terminal_series_chain
from dwg_audit.audit.series_chains import summarize_terminal_series_chains
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.utils.config import DEFAULT_CONFIG

_DEFAULT_TEST_CONFIG = DEFAULT_CONFIG


def _pair(
    pair_id: str,
    sheet_id: str,
    left: str,
    right: str,
    *,
    submode: str = "kk_multi_port_component",
    status: str = "pass",
    confidence: float = 0.95,
    pair_kind: str = "component_mapping",
    line_group_id: str | None = None,
) -> Pair:
    return Pair(
        pair_id,
        line_group_id,
        sheet_id,
        sheet_id,
        None,
        left,
        right,
        confidence,
        status,
        "chain test member",
        [],
        "high" if confidence >= 0.95 else "review",
        {
            "source": "component_mapping" if pair_kind == "component_mapping" else "table_mapping",
            "component_submode": submode,
            "filename": f"{sheet_id}.dwg",
            "sheet_no": "1",
        },
        pair_kind=pair_kind,
    )


def _strip_pair(pair_id: str, sheet_id: str, left: str, right: str) -> Pair:
    return _pair(pair_id, sheet_id, left, right, submode="terminal_strip_lattice", line_group_id=f"G-{pair_id}")


def _sheet(sheet_id: str) -> SheetRecord:
    return SheetRecord(
        sheet_id,
        sheet_id,
        f"{sheet_id}.dwg",
        1,
        "1",
        "WIRING",
        "元件接线图",
        "supplemental",
        "filename",
        True,
    )


def test_cross_view_strip_and_kk_junction_is_series_chain() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1"),
    ]

    assert is_cross_view_terminal_series_chain(pairs)
    chains = build_terminal_series_chains(pairs)

    assert len(chains) == 1
    chain = chains[0]
    assert chain["junction_value"] == "1UD1"
    assert chain["junction_kind"] == "device_terminal_series"
    assert chain["member_count"] == 2
    assert chain["circuit_side_values"] == ["1n2001"]
    assert chain["component_side_values"] == ["1ZKK1-2"]
    roles = {member["pair_id"]: member["role"] for member in chain["members"]}
    assert roles == {"PT1": "circuit_side", "PK1": "component_side"}


def test_series_chain_rules_skips_many_to_one_for_full_chain_group() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1"),
    ]
    sheets = [_sheet("S23"), _sheet("S26")]

    issues = build_issues(pairs, [], sheets, _DEFAULT_TEST_CONFIG)

    assert not any(issue.rule_id == "R-MANY-TO-ONE" for issue in issues)


def test_series_chain_requires_at_least_one_strip_member() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PX1", "S23", "1ZKK1-2", "1UD1", submode="mystery_future_producer"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)
    assert build_terminal_series_chains(pairs) == []

    sheets = [_sheet("S23"), _sheet("S26")]
    issues = build_issues(pairs, [], sheets, _DEFAULT_TEST_CONFIG)

    assert any(issue.rule_id == "R-MANY-TO-ONE" for issue in issues)


def test_series_chain_rejects_review_status_member() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1", status="review"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)


def test_series_chain_rejects_low_confidence_member() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1", confidence=0.9),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)


def test_series_chain_rejects_non_component_member_in_group() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1"),
        _pair("PB1", "S2", "NCK305-1@c0", "1UD1", pair_kind="table_mapping"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)


def test_series_chain_rules_keeps_group_with_extra_table_member_visible() -> None:
    # A duplicate left value breaks the junction (one view cannot claim the
    # same left twice), so the group must stay a visible many-to-one review.
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1"),
        _strip_pair("PT2", "S27", "1ZKK1-2", "1UD1"),
    ]
    sheets = [_sheet("S23"), _sheet("S26"), _sheet("S27")]

    issues = build_issues(pairs, [], sheets, _DEFAULT_TEST_CONFIG)

    assert any(issue.rule_id == "R-MANY-TO-ONE" for issue in issues)


def test_series_chain_rejects_duplicate_left_values() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _strip_pair("PT2", "S27", "1n2001", "1UD1"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)


def test_series_chain_ignores_single_member_value() -> None:
    pairs = [_strip_pair("PT1", "S26", "1n2001", "1UD1")]

    assert build_terminal_series_chains(pairs) == []


def test_series_chain_records_continuations_for_long_chains() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1"),
        _pair("PB1", "S2", "1UD1", "1XD14-1", submode="strip_two_port_endpoint_bridge"),
    ]

    chains = build_terminal_series_chains(pairs)

    assert len(chains) == 1
    chain = chains[0]
    assert chain["junction_value"] == "1UD1"
    assert chain["continuation_count"] == 1
    assert chain["continuations"][0]["left_value"] == "1UD1"
    assert chain["continuations"][0]["junction_value"] == "1XD14-1"
    summary = summarize_terminal_series_chains(chains)
    assert summary["chain_count"] == 1
    assert summary["continuation_count"] == 1


def test_series_chain_builder_ignores_unrelated_producers() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PW1", "S1", "1KLP1-1", "1UD1", submode="component_prefixed_signal_circuit"),
    ]

    assert build_terminal_series_chains(pairs) == []


def test_series_chain_accepts_schematic_kk_strip_three_view_junction() -> None:
    # The schematic inline view and the KK view describe the same
    # port-to-terminal fact; the strip row adds the circuit side.
    pairs = [
        _strip_pair("PT1", "S21", "1n2001", "1UD1"),
        _pair("PK1", "S19", "1ZKK1-2", "1UD1"),
        _pair("PA1", "S9", "1ZKK1-2", "1UD1", submode="inline_two_port_component"),
    ]

    assert is_cross_view_terminal_series_chain(pairs)
    chains = build_terminal_series_chains(pairs)

    assert len(chains) == 1
    chain = chains[0]
    assert chain["member_count"] == 3
    assert chain["circuit_side_values"] == ["1n2001"]
    assert chain["component_side_values"] == ["1ZKK1-2"]
    sheets = [_sheet("S9"), _sheet("S19"), _sheet("S21")]
    assert not any(issue.rule_id == "R-MANY-TO-ONE" for issue in build_issues(pairs, [], sheets, _DEFAULT_TEST_CONFIG))


def test_series_chain_rejects_duplicate_left_without_inline_corroboration() -> None:
    # Two strip views claiming the same wire onto the same terminal are two
    # circuit-side claims, not corroboration; the junction stays a review.
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1"),
        _strip_pair("PT2", "S27", "1ZKK1-2", "1UD1"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)
    sheets = [_sheet("S23"), _sheet("S26"), _sheet("S27")]
    assert any(issue.rule_id == "R-MANY-TO-ONE" for issue in build_issues(pairs, [], sheets, _DEFAULT_TEST_CONFIG))


def test_series_chain_rejects_triple_view_corroboration_without_pair_match() -> None:
    # Three members on one left value exceed the corroborated-fact shape.
    pairs = [
        _strip_pair("PT1", "S21", "1n2001", "1UD1"),
        _pair("PK1", "S19", "1ZKK1-2", "1UD1"),
        _pair("PA1", "S9", "1ZKK1-2", "1UD1", submode="inline_two_port_component"),
        _pair("PS1", "S20", "1ZKK1-2", "1UD1", submode="small_port_box_component"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)


def _terminal_chart_pair(pair_id: str, sheet_id: str, left: str, right: str, *, mode: str = "terminal_header_table") -> Pair:
    pair = _pair(pair_id, sheet_id, left, right, pair_kind="table_mapping")
    pair.evidence["table_mapping"] = {"mapping_mode": mode, "logical_endpoint": left}
    return pair


def test_series_chain_includes_terminal_chart_side_member() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2006", "1UD10"),
        _terminal_chart_pair("PTB1", "S29", "UD-10", "1UD10"),
    ]

    assert is_cross_view_terminal_series_chain(pairs)
    chains = build_terminal_series_chains(pairs)

    assert len(chains) == 1
    chain = chains[0]
    assert chain["junction_value"] == "1UD10"
    assert chain["circuit_side_values"] == ["1n2006"]
    assert chain["chart_side_values"] == ["UD-10"]
    assert chain["members"][1]["role"] == "chart_side"
    sheets = [_sheet("S26"), _sheet("S29")]
    assert not any(issue.rule_id == "R-MANY-TO-ONE" for issue in build_issues(pairs, [], sheets, _DEFAULT_TEST_CONFIG))


def test_series_chain_rejects_backplate_virtual_table_member() -> None:
    # Backplate virtual-table rows carry their own cross-page scope review
    # and must never be absorbed into a series chain.
    pairs = [
        _strip_pair("PT1", "S26", "1n2006", "1UD10"),
        _terminal_chart_pair("PB1", "S30", "NCK305-1@c0", "1UD10", mode="backplate_virtual_table"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)
    assert build_terminal_series_chains(pairs) == []
    sheets = [_sheet("S26"), _sheet("S30")]
    assert any(issue.rule_id == "R-MANY-TO-ONE" for issue in build_issues(pairs, [], sheets, _DEFAULT_TEST_CONFIG))


def test_series_chain_rejects_non_finite_confidence_member() -> None:
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _pair("PK1", "S23", "1ZKK1-2", "1UD1", confidence=float("nan")),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)
    assert build_terminal_series_chains(pairs) == []


def test_series_chain_rejects_pure_circuit_side_junction() -> None:
    # Two circuit wires claiming one device terminal is a genuine review
    # case; without any component/chart view the junction must stay visible.
    pairs = [
        _strip_pair("PT1", "S26", "1n2001", "1UD1"),
        _strip_pair("PT2", "S26", "1n2002", "1UD1"),
    ]

    assert not is_cross_view_terminal_series_chain(pairs)
    assert build_terminal_series_chains(pairs) == []
    sheets = [_sheet("S26")]
    issues = build_issues(pairs, [], sheets, _DEFAULT_TEST_CONFIG)

    assert any(issue.rule_id == "R-MANY-TO-ONE" for issue in issues)
