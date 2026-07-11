from __future__ import annotations

from dwg_audit.audit.token_parser import parse_text_tokens
from dwg_audit.domain.models import TextItem


def _text(text_id: str, value: str, *, numeric: bool | None = None) -> TextItem:
    is_numeric = value.isdigit() if numeric is None else numeric
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H{text_id}",
        entity_type="TEXT",
        text=value,
        normalized_text=value,
        is_numeric_candidate=is_numeric,
        layer="DIM",
        rotation_deg=0.0,
        height=2.5,
        insert_x=10.0,
        insert_y=20.0,
        bbox_min_x=8.0,
        bbox_min_y=18.0,
        bbox_max_x=12.0,
        bbox_max_y=22.0,
    )


def _by_kind(tokens: list[dict]) -> dict[str, dict]:
    return {token["token_kind"]: token for token in tokens}


def test_parse_scoped_prefix_tokens() -> None:
    tokens = parse_text_tokens([_text("T1", "1n"), _text("T2", "5n"), _text("T3", "1-2n")])
    kinds = [token["token_kind"] for token in tokens]
    assert kinds == ["SCOPED_PREFIX", "SCOPED_PREFIX", "SCOPED_PREFIX"]
    assert tokens[0]["token_id"] == "TK1-T1"
    assert tokens[0]["prefix"] == "1"
    assert tokens[2]["prefix"] == "1-2"
    assert tokens[0]["confidence"] >= 0.9
    assert "MATCH_SCOPED_PREFIX" in tokens[0]["reason_codes"]


def test_parse_wire_n_number_tokens() -> None:
    tokens = parse_text_tokens([_text("W1", "n105"), _text("W2", "N012")])
    assert [token["token_kind"] for token in tokens] == ["WIRE_N_NUMBER", "WIRE_N_NUMBER"]
    assert tokens[0]["local_number"] == "105"
    assert tokens[1]["local_number"] == "012"
    assert tokens[0]["token_id"] == "TK1-W1"


def test_parse_component_body_tokens() -> None:
    tokens = parse_text_tokens([_text("C1", "5KLP10"), _text("C2", "1ZKK2"), _text("C3", "3-2KLP1")])
    assert all(token["token_kind"] == "COMPONENT_BODY" for token in tokens)
    assert tokens[0]["prefix"] == "5"
    assert tokens[0]["family"] == "KLP"
    assert tokens[0]["ordinal"] == "10"
    assert tokens[1]["family"] == "ZKK"
    assert tokens[2]["prefix"] == "3-2"


def test_parse_component_port_tokens() -> None:
    tokens = parse_text_tokens([_text("P1", "1"), _text("P2", "6"), _text("P3", "7")])
    assert tokens[0]["token_kind"] == "COMPONENT_PORT"
    assert tokens[0]["ordinal"] == "1"
    assert tokens[1]["token_kind"] == "COMPONENT_PORT"
    # 7 is not a component port; falls through to TERMINAL_LOCAL / ANNOTATION.
    assert tokens[2]["token_kind"] in {"TERMINAL_LOCAL", "ANNOTATION"}


def test_parse_external_endpoint_tokens() -> None:
    tokens = parse_text_tokens([_text("E1", "5FD4"), _text("E2", "1QD12"), _text("E3", "3-2QD2")])
    assert all(token["token_kind"] == "EXTERNAL_ENDPOINT" for token in tokens)
    assert tokens[0]["prefix"] == "5"
    assert tokens[0]["family"] == "FD"
    assert tokens[0]["ordinal"] == "4"
    assert tokens[1]["family"] == "QD"
    assert tokens[2]["prefix"] == "3-2"


def test_parse_terminal_local_tokens() -> None:
    tokens = parse_text_tokens(
        [
            _text("L1", "105", numeric=True),
            _text("L2", "12", numeric=True),
            _text("L3", "7", numeric=True),
        ]
    )
    # single digit 7 also matches COMPONENT_PORT first (1-6 only), so 7 -> TERMINAL_LOCAL
    assert tokens[0]["token_kind"] == "TERMINAL_LOCAL"
    assert tokens[0]["local_number"] == "105"
    assert tokens[1]["token_kind"] == "TERMINAL_LOCAL"
    assert tokens[2]["token_kind"] == "TERMINAL_LOCAL"


def test_parse_device_tag_tokens() -> None:
    tokens = parse_text_tokens([_text("D1", "1ID10"), _text("D2", "3CLP2")])
    assert tokens[0]["token_kind"] == "DEVICE_TAG"
    assert tokens[0]["prefix"] == "1"
    assert tokens[0]["family"] == "ID"
    assert tokens[0]["ordinal"] == "10"
    assert tokens[1]["token_kind"] == "DEVICE_TAG"
    assert tokens[1]["family"] == "CLP"


def test_parse_page_reference_tokens() -> None:
    tokens = parse_text_tokens(
        [
            _text("R1", "详见第3页"),
            _text("R2", "另页说明"),
            _text("R3", "see page 4"),
        ]
    )
    assert all(token["token_kind"] == "PAGE_REFERENCE" for token in tokens)
    assert "MATCH_PAGE_REFERENCE" in tokens[0]["reason_codes"]


def test_parse_annotation_fallback() -> None:
    tokens = parse_text_tokens([_text("A1", "手合同期"), _text("A2", "BI / BCD1")])
    assert all(token["token_kind"] == "ANNOTATION" for token in tokens)
    assert tokens[0]["token_id"] == "TK1-A1"
    assert "FALLBACK_ANNOTATION" in tokens[0]["reason_codes"]


def test_parse_skips_empty_text() -> None:
    tokens = parse_text_tokens([_text("E0", ""), _text("E1", "   ")])
    assert tokens == []


def test_parse_preserves_geometry_fields() -> None:
    tokens = parse_text_tokens([_text("G1", "n105")])
    assert tokens[0]["layer"] == "DIM"
    assert tokens[0]["insert_x"] == 10.0
    assert tokens[0]["insert_y"] == 20.0
    assert tokens[0]["bbox"] == [8.0, 18.0, 12.0, 22.0]
    assert tokens[0]["sheet_id"] == "S1"
    assert tokens[0]["file_id"] == "F1"
