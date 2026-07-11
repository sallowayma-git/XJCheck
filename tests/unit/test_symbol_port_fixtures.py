from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"
PORT_FIXTURE_PATH = FIXTURES_DIR / "symbol_port_fixtures_v1.json"
BENCHMARK_SPLIT_PATH = FIXTURES_DIR / "benchmark_split_v1.csv"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_REGISTRY_STATUS = frozenset({"UNKNOWN", "CANDIDATE", "REGISTERED"})


@pytest.fixture(scope="module")
def port_fixture() -> dict:
    payload = json.loads(PORT_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@pytest.fixture(scope="module")
def heldout_project_ids() -> set[str]:
    split = pd.read_csv(BENCHMARK_SPLIT_PATH)
    held = split.loc[split["split"] == "heldout_test", "project_id"].astype(str)
    return set(held)


def test_port_fixture_root_versions(port_fixture: dict) -> None:
    assert port_fixture["fixture_version"] == "symbol-port-fixtures-v1"
    assert port_fixture["fingerprint_version"] == "local-geometry-fingerprint-v1"
    assert isinstance(port_fixture["entries"], list)
    assert len(port_fixture["entries"]) >= 10


def test_port_fixture_entries_are_unknown_empty_ports(port_fixture: dict) -> None:
    fingerprints: list[str] = []
    for entry in port_fixture["entries"]:
        assert entry["critical_issue_eligible"] is False
        assert entry["declared_port_count"] == 0
        assert entry["ports"] == []
        assert len(entry["ports"]) == 0
        assert entry["declared_port_count"] == len(entry["ports"])
        assert entry["internal_connectivity_state"] == "UNKNOWN"
        assert entry["registry_status"] == "UNKNOWN"
        assert entry["registry_status"] in _ALLOWED_REGISTRY_STATUS
        assert entry["symbol_family"] is None
        assert entry["annotation_status"] == "PENDING_HUMAN_REVIEW"
        assert isinstance(entry["notes"], str)
        assert isinstance(entry["definition_names"], list)
        assert all(isinstance(n, str) and n for n in entry["definition_names"])

        fp = entry["definition_fingerprint"]
        assert isinstance(fp, str)
        assert _HEX64.fullmatch(fp), f"fingerprint must be 64-char hex: {fp!r}"
        fingerprints.append(fp)

    assert len(fingerprints) == len(set(fingerprints))


def test_port_fixture_contains_top10_and_kk2p(port_fixture: dict) -> None:
    names = {
        name
        for entry in port_fixture["entries"]
        for name in entry["definition_names"]
    }
    assert "KK2P" in names
    # Top-10 geometry families from non-heldout backlog ranks 1–10.
    expected_top_names = {
        "SYMB2_M_PWF165",
        "SYMB2_M_PWF231",
        "SYMB2_M_PWF248",
        "SYMB2_M_PWF191",
        "SYMB2_M_PWF194",
        "SYMB2_M_PWF243",
        "Title_xjdw-yw",
        "SYMB2_M_PWF233",
        "FJL-25-2A_Mirror",
        "SYMB2_M_PWF224",
        "SYMB2_M_PWF229",
    }
    assert expected_top_names.issubset(names)
    assert len(port_fixture["entries"]) == 11


def test_port_fixture_has_no_heldout_project_ids(
    heldout_project_ids: set[str],
) -> None:
    raw = PORT_FIXTURE_PATH.read_text(encoding="utf-8")
    for project_id in sorted(heldout_project_ids):
        assert project_id not in raw, f"held-out project id leaked: {project_id}"
