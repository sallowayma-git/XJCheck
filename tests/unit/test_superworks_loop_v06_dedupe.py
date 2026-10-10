from __future__ import annotations

from dwg_audit.audit.superworks_extractor import supersede_equivalent_component_duplicates
from dwg_audit.domain.models import Pair


def _sw_row(pair_id="PSW-SW1", right_text_id="T4117", port="1", right="1QD2", left="1KLP1-1", status="pass"):
    return Pair(
        pair_id=pair_id, line_group_id=None, sheet_id="S0026", file_id="F0026",
        selected_pair_candidate_id=None, left_value=left, right_value=right,
        confidence=.99, status=status, rationale="sw", confidence_bucket="high",
        evidence={"source": "component_mapping", "component_submode": "superworks_connect_line_port",
                  "component_port": port, "component_body": "FJL-25-2A_Mirror",
                  "superworks": {"source": "superworks", "port_number": port}},
        left_text_id="T4056", right_text_id=right_text_id,
        pair_key=f"{left}->{right}", pair_kind="component_mapping",
    )


def _legacy_row(pair_id="PAB0103", right_text_id="T4117", port="1", right="1QD2", left="1KLP1-1",
                status="pass", submode="strip_two_port_component"):
    return Pair(
        pair_id=pair_id, line_group_id=None, sheet_id="S0026", file_id="F0026",
        selected_pair_candidate_id=None, left_value=left, right_value=right,
        confidence=.9, status=status, rationale="legacy", confidence_bucket="high",
        evidence={"source": "component_mapping", "component_submode": submode,
                  "component_port": port, "component_body": "1KLP1"},
        left_text_id="T4054", right_text_id=right_text_id,
        pair_key=f"{left}->{right}", pair_kind="component_mapping",
    )


def test_equivalent_legacy_row_is_retired_and_sw_row_kept():
    sw = _sw_row()
    legacy = _legacy_row()
    other = Pair(pair_id="OTHER", line_group_id=None, sheet_id="S0026", file_id="F0026",
                 selected_pair_candidate_id=None, left_value="X1", right_value="X2",
                 confidence=.9, status="pass", rationale="", pair_kind="ordinary_pair")
    ledger = []
    kept, ledger = supersede_equivalent_component_duplicates([legacy, sw, other], ledger)
    assert [p.pair_id for p in kept] == ["PSW-SW1", "OTHER"]
    assert len(ledger) == 1
    entry = ledger[0]
    assert entry["category"] == "G"
    assert entry["element_key"] == "component_duplicate:S0026:PAB0103"
    assert entry["old_pair"]["pair_id"] == "PAB0103"
    assert [p["pair_id"] for p in entry["new_pairs"]] == ["PSW-SW1"]


def test_legacy_row_with_inline_submode_is_retired_too():
    sw = _sw_row(right_text_id="T3855", right="1VD1", left="1F1-1")
    legacy = _legacy_row(pair_id="PAB0041", right_text_id="T3855", right="1VD1", left="1F1-1",
                         submode="inline_two_port_component")
    kept, ledger = supersede_equivalent_component_duplicates([legacy, sw], [])
    assert [p.pair_id for p in kept] == ["PSW-SW1"]
    assert len(ledger) == 1


def test_legacy_row_with_different_destination_text_is_kept():
    sw = _sw_row(right_text_id="T4117")
    legacy = _legacy_row(right_text_id="T4118")
    kept, ledger = supersede_equivalent_component_duplicates([legacy, sw], [])
    assert {p.pair_id for p in kept} == {"PAB0103", "PSW-SW1"}
    assert ledger == []


def test_legacy_row_with_different_port_is_kept():
    sw = _sw_row(port="1")
    legacy = _legacy_row(port="2")
    kept, ledger = supersede_equivalent_component_duplicates([legacy, sw], [])
    assert {p.pair_id for p in kept} == {"PAB0103", "PSW-SW1"}
    assert ledger == []


def test_legacy_row_with_different_destination_value_is_kept():
    sw = _sw_row(right="1QD2")
    legacy = _legacy_row(right="1QD3")
    kept, ledger = supersede_equivalent_component_duplicates([legacy, sw], [])
    assert {p.pair_id for p in kept} == {"PAB0103", "PSW-SW1"}
    assert ledger == []


def test_legacy_row_in_review_status_is_kept():
    sw = _sw_row()
    legacy = _legacy_row(status="review")
    kept, ledger = supersede_equivalent_component_duplicates([legacy, sw], [])
    assert {p.pair_id for p in kept} == {"PAB0103", "PSW-SW1"}
    assert ledger == []


def test_sw_rows_are_never_retired_by_each_other():
    first = _sw_row(pair_id="PSW-A")
    second = _sw_row(pair_id="PSW-B")
    kept, ledger = supersede_equivalent_component_duplicates([first, second], [])
    assert [p.pair_id for p in kept] == ["PSW-A", "PSW-B"]
    assert ledger == []


def test_no_sw_rows_returns_input_unchanged():
    legacy = _legacy_row()
    pairs = [legacy]
    ledger = []
    kept, out_ledger = supersede_equivalent_component_duplicates(pairs, ledger)
    assert kept is pairs
    assert out_ledger is ledger
    assert ledger == []


def test_sw_row_in_review_status_does_not_supersede():
    sw = _sw_row(status="review")
    legacy = _legacy_row()
    kept, ledger = supersede_equivalent_component_duplicates([legacy, sw], [])
    assert {p.pair_id for p in kept} == {"PAB0103", "PSW-SW1"}
    assert ledger == []


def test_accessory_legacy_row_is_retired_in_pipeline_order_and_ledger_g_is_written(tmp_path):
    # Mirrors pipeline.py: SW pairs first, then accessory legacy rows appended,
    # then the supersession call, then the ledger handed to the artifact writer.
    import json
    from types import SimpleNamespace

    import pandas as pd
    from test_backplate_components import _block, _line, _page, _text

    from dwg_audit.audit.backplate_components import extract_accessory_backplate_two_port_pairs
    from dwg_audit.extract.superworks_semantics import SuperworksData
    from dwg_audit.report.superworks_artifacts import write_superworks_artifacts

    texts = [
        _text("P1", "1", 50.0, 97.5, handle="H1:VIRTUAL:1", block="UNSEEN-CAPSULE"),
        _text("P2", "2", 50.0, 82.5, handle="H1:VIRTUAL:0", block="UNSEEN-CAPSULE"),
        _text("BODY", "1KLP7", 50.0, 112.0),
        _text("TOP", "1KLP6-1, 1KLP8-1", 50.0, 103.0),
        _text("BOTTOM", "1n407", 50.0, 77.0),
    ]
    lines = [_line("L1", 47.5, handle="H1:VIRTUAL:2"), _line("L2", 52.5, handle="H1:VIRTUAL:3")]
    accessory_pairs, _ = extract_accessory_backplate_two_port_pairs([_page()], texts, lines, [_block()])
    legacy_by_id = {p.pair_id: p for p in accessory_pairs}
    assert {"PAB0001", "PAB0002", "PAB0003"} <= set(legacy_by_id)

    # SW connect-line row with the identity of PAB0001 (same sheet, endpoints, port, destination text).
    sw = _sw_row(pair_id="PSW-1KLP7", right_text_id="TOP", port="1", right="1KLP6-1", left="1KLP7-1")
    sw.sheet_id = "S1"
    sw.file_id = "F1"
    pairs = [sw, *accessory_pairs]
    ledger = []

    pairs, ledger = supersede_equivalent_component_duplicates(pairs, ledger)

    kept_ids = [p.pair_id for p in pairs]
    assert "PAB0001" not in kept_ids
    assert {"PSW-1KLP7", "PAB0002", "PAB0003"} <= set(kept_ids)
    assert len(ledger) == 1
    entry = ledger[0]
    assert entry["category"] == "G"
    assert entry["old_pair"]["pair_id"] == "PAB0001"
    assert [p["pair_id"] for p in entry["new_pairs"]] == ["PSW-1KLP7"]

    artifacts = SimpleNamespace(
        superworks=SuperworksData(),
        superworks_supersession=ledger,
        scan=SimpleNamespace(manifest=SimpleNamespace(project_id="P1"), pages=[_page()]),
        pairs=pairs,
    )
    write_superworks_artifacts(artifacts, tmp_path)
    written = pd.read_parquet(tmp_path / "superworks_supersession.parquet")
    assert list(written["category"]) == ["G"]
    assert written.iloc[0]["reason"] == "superworks_connect_line_port_supersedes_equivalent_legacy_row"
    assert json.loads(written.iloc[0]["old_pair"])["pair_id"] == "PAB0001"
    summary = json.loads((tmp_path / "superworks_summary.json").read_text(encoding="utf-8"))
    assert summary["supersession_categories"] == {"G": 1}
