"""Unit tests for the SuperWORKS wire-route diagnostic (LD_SYMB2LOGGEN / LD_PARTCONNECTLINE)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import ezdxf
import pytest

from dwg_audit.extract.superworks_loggen import (
    EndpointIndex,
    collect_wire_route_rows,
    read_page_wire_routes,
    resolve_wire_routes,
    write_wire_route_rows,
)


def _sw_port(file_id, insert, number, identity, category="端子", record="P", reasons=()):
    return SimpleNamespace(file_id=file_id, insert_handle=insert, port_number=number,
                           endpoint_identity=identity, category=category,
                           record_id=f"{record}:{insert}:{number}", reason_codes=list(reasons))


def _superworks(symbols=(), ports=(), parts=()):
    return SimpleNamespace(symbols=list(symbols), ports=list(ports), part_instances=list(parts))


def _loggen_document(records):
    """records: list of (key, [(name, value), ...]) placed in LD_SYMB2LOGGEN_DICTIONARY."""
    document = ezdxf.new("R2018")
    dictionary = document.rootdict.add_new_dict("LD_SYMB2LOGGEN_DICTIONARY")
    for key, pairs in records:
        record = dictionary.add_xrecord(key)
        record.reset([(1, value) for pair in pairs for value in pair])
    return document


def _two_end_record(wire="CC", extra=()):
    return [
        ("LINENO", "未定义AB:2"),
        ("LINESTYLE", "电流回路线:*"),
        ("CONNECTLINEHANDLE", wire),
        ("PART2_1", "||1ID||2||7||左||SYM||AB||端子||||正向"),
        ("PART2_2", "||1n||1||1506||||SYM||AC||装置端子||||正向"),
        *extra,
    ]


def test_loggen_two_end_record_resolves_both_ends_to_sw_identities() -> None:
    document = _loggen_document([("LD_SYMB2LOGGEN_1", _two_end_record())])
    superworks = _superworks(
        ports=[
            _sw_port("F1", "AB", "2", "1ID7", "端子"),
            _sw_port("F1", "AC", "1", "1n1506", "装置端子"),
        ],
    )
    page = read_page_wire_routes(document, file_id="F1", sheet_id="S1")
    rows = resolve_wire_routes([page], EndpointIndex(superworks))

    assert len(rows) == 1
    row = rows[0]
    assert row["source_kind"] == "LOGGEN"
    assert row["wire_handle"] == "CC"
    assert row["linestyle"] == "电流回路线:*"
    assert row["end_count"] == 2
    assert row["both_ends_resolved"] is True
    ends = json.loads(row["ends_json"])
    assert [e["identity"] for e in ends] == ["1ID7", "1n1506"]
    assert [e["port_number"] for e in ends] == ["2", "1"]
    assert all(e["identity_source"] == "sw_port" for e in ends)
    # LINENO names the first end (AB port 2), so it is matched to end 0.
    assert row["lineno_end_index"] == 0


def test_loggen_keeps_every_end_of_a_multi_end_record() -> None:
    pairs = [
        ("PART2_1", "||1ID||2||7||左||S||AB||端子||"),
        ("PART2_2", "||1n||1||1506||||S||AC||装置端子||"),
        ("PART2_3", "||1ID||3||9||右||S||AD||端子||"),
        ("PART2_4", "||2ID||1||9||右||S||AE||端子||"),
    ]
    document = _loggen_document([("LD_SYMB2LOGGEN_9", [("CONNECTLINEHANDLE", "CC"), *pairs])])
    superworks = _superworks(ports=[
        _sw_port("F1", "AB", "2", "1ID7"), _sw_port("F1", "AC", "1", "1n1506", "装置端子"),
        _sw_port("F1", "AD", "3", "1ID9"), _sw_port("F1", "AE", "1", "2ID9"),
    ])
    rows = resolve_wire_routes([read_page_wire_routes(document, file_id="F1", sheet_id="S1")],
                               EndpointIndex(superworks))
    ends = json.loads(rows[0]["ends_json"])
    assert rows[0]["end_count"] == 4
    assert rows[0]["both_ends_resolved"] is True
    assert [e["identity"] for e in ends] == ["1ID7", "1n1506", "1ID9", "2ID9"]


def test_loggen_skips_bookkeeping_entries_and_reports_unresolved_reasons() -> None:
    document = _loggen_document([
        ("FILEINFOR_OF_LAST_CREATED", [("$FILETIME", "2024,3,1,14,14,59")]),
        ("LD_SYMB2LOGGEN_2", [
            ("CONNECTLINEHANDLE", "CC"),
            ("PART2_1", "||1KLP||3||1||右||S||AB||||正向"),
            ("PART2_2", "||1ID||2||1||左||S||MISSING||端子||"),
        ]),
    ])
    superworks = _superworks(parts=[SimpleNamespace(file_id="F1", insert_handle="AB", ports=[])])
    rows = resolve_wire_routes([read_page_wire_routes(document, file_id="F1", sheet_id="S1")],
                               EndpointIndex(superworks))
    assert len(rows) == 1
    ends = json.loads(rows[0]["ends_json"])
    assert ends[0]["status"] == "port_number_absent"
    assert ends[1]["status"] == "handle_missing"
    assert rows[0]["both_ends_resolved"] is False
    assert "end_0_port_number_absent" in json.loads(rows[0]["reason_codes_json"])


def test_pcl_record_resolves_local_pin_and_cross_page_far_end() -> None:
    document = ezdxf.new("R2018")
    insert = document.modelspace().add_blockref("ELXAL5", (0, 0))
    owner = insert.dxf.handle
    xdict = insert.new_extension_dict()
    record = xdict.add_xrecord("LD_PARTCONNECTLINE")
    record.reset([
        (1, "逻辑端号:13"),
        (1, "线号:未定义8ED7:1_05 交直流回路图"),
        (1, "导线类型:电压回路线:&"),
        (1, "直线句柄:11EFF"),
        (1, "对端元件:1QD||||4||端子||导线类型:电压回路线:&||导线颜色代号:"),
        (1, "逻辑端号:14"),
        (1, "线号:"),
        (1, "直线句柄:11F01"),
        (1, "对端元件:1QD||||7||端子||导线类型:"),
    ])
    superworks = _superworks(
        parts=[SimpleNamespace(file_id="F1", insert_handle=owner, ports=[
            {"port_number": "13", "endpoint_identity": "1FA-13", "category": "", "record_id": "PP13", "reason_codes": []},
            {"port_number": "14", "endpoint_identity": "1FA-14", "category": "", "record_id": "PP14", "reason_codes": []},
        ])],
        ports=[_sw_port("F5", "8ED7", "1", "1n1506", "装置端子", record="XP")],
    )
    index = EndpointIndex(superworks, {"F1": "15", "F5": "05"})
    page = read_page_wire_routes(document, file_id="F1", sheet_id="S1")
    rows = resolve_wire_routes([page], index)
    by_pin = {row["logical_pin"]: row for row in rows}
    assert set(by_pin) == {"13", "14"}

    first = json.loads(by_pin["13"]["ends_json"])
    assert first[0]["role"] == "LOCAL"
    assert first[0]["identity"] == "1FA-13"
    # Cross-page target 8ED7 is a SW port in F5 (sheet 05); far end identity is resolved there.
    assert first[1]["far_source"] == "cross_page"
    assert first[1]["identity"] == "1n1506"
    assert first[1]["far_text_identity"] == "1QD4"
    assert by_pin["13"]["both_ends_resolved"] is True

    second = json.loads(by_pin["14"]["ends_json"])
    # No cross-page label: the far end is the text device/pin, identified by text only.
    assert second[1]["far_source"] == "text_only"
    assert second[1]["identity"] == "1QD7"
    assert second[1]["identity_source"] == "text"


def test_cross_page_target_ambiguous_without_page_number_is_reported() -> None:
    superworks = _superworks(ports=[
        _sw_port("F5", "8ED7", "1", "A1", "装置端子"),
        _sw_port("F6", "8ED7", "1", "B1", "装置端子"),
    ])
    index = EndpointIndex(superworks, {"F5": "05", "F6": "06"})
    assert index.cross_page_end("8ED7", "1", "")["status"] == "xpage_ambiguous"
    resolved = index.cross_page_end("8ED7", "1", "06")
    assert resolved["status"] == "resolved" and resolved["identity"] == "B1"
    assert index.cross_page_end("FFFF", "1", "")["status"] == "xpage_target_not_sw"


def test_collect_rows_from_saved_dxf_isolates_failing_page(tmp_path) -> None:
    document = _loggen_document([("LD_SYMB2LOGGEN_1", _two_end_record())])
    good = tmp_path / "good.dxf"
    document.saveas(good)
    bad = tmp_path / "bad.dxf"
    bad.write_text("not a dxf", encoding="utf-8")
    superworks = _superworks(ports=[_sw_port("F1", "AB", "2", "1ID7"), _sw_port("F1", "AC", "1", "1n1506", "装置端子")])

    rows, stats = collect_wire_route_rows(
        [("F1", "S1", good), ("F2", "S2", bad)], superworks, {"F1": "04"},
    )

    assert len(rows) == 1 and rows[0]["both_ends_resolved"] is True
    assert set(stats["page_failures"]) == {"F2"}
    assert stats["page_count"] == 2
    assert stats["schema_version"] == "sw-wire-route-v1"


def test_write_rows_round_trips_through_parquet(tmp_path) -> None:
    pd = pytest.importorskip("pandas")
    document = _loggen_document([("LD_SYMB2LOGGEN_1", _two_end_record())])
    rows = resolve_wire_routes([read_page_wire_routes(document, file_id="F1", sheet_id="S1")],
                               EndpointIndex(_superworks()))
    target = tmp_path / "sw_wire_routes.parquet"
    write_wire_route_rows(target, rows)
    frame = pd.read_parquet(target)
    assert list(frame.record_id) == [rows[0]["record_id"]]
    assert json.loads(frame.ends_json.iloc[0])[0]["role"] == "PART2_1"
