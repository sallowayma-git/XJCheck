"""Unit tests for Phase 117 Top-N symbol definition fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dwg_audit.audit.symbol_registry import (
    SYMBOL_FINGERPRINT_VERSION,
    build_project_symbol_inventory,
    definition_fingerprint_from_children,
)

FIXTURE_JSON = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "symbol_definition_fixtures_v1.json"
)

P001_PRIMITIVES = Path(
    ".tmp/phase117_corpus_non_heldout/P001/"
    "WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings/"
    "primitive_segments.parquet"
)


def _load_fixture() -> dict:
    assert FIXTURE_JSON.is_file(), f"missing fixture: {FIXTURE_JSON}"
    return json.loads(FIXTURE_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture_doc() -> dict:
    return _load_fixture()


def test_fixture_policy_and_schema(fixture_doc: dict) -> None:
    assert fixture_doc["schema_version"] == "symbol-definition-fixtures-v1"
    assert fixture_doc["fingerprint_version"] == SYMBOL_FINGERPRINT_VERSION
    assert fixture_doc["fingerprint_version"] == "local-geometry-fingerprint-v1"

    policy = fixture_doc["policy"]
    assert policy["held_out_excluded"] is True
    assert policy["fingerprint_algorithm_version"] == "local-geometry-fingerprint-v1"
    assert policy["no_port_or_internal_connectivity_claimed"] is True
    assert policy["names_are_features_not_identities"] is True
    assert policy["critical_issue_eligible_until_human_registration"] is False

    source = fixture_doc["source"]
    assert source["held_out_excluded"] is True
    assert source["project_id"] == "P001"
    assert "non_heldout" in source["corpus"]

    families = fixture_doc["families"]
    assert len(families) >= 6
    family_ids = {f["family_id"] for f in families}
    assert "top1_pwf165" in family_ids
    assert "top2_pwf231_pwf248" in family_ids
    assert "top3_pwf191" in family_ids
    assert "top4_pwf194" in family_ids
    assert "top5_pwf243" in family_ids
    assert "name_example_kk2p" in family_ids


def test_recompute_fingerprint_from_fixture_children(fixture_doc: dict) -> None:
    for family in fixture_doc["families"]:
        children = family["child_signatures"]
        assert children, f"empty signatures for {family['family_id']}"
        assert family["signatures_truncated"] is False
        assert family["stored_signature_count"] == family["source_unique_signature_count"]
        assert len(children) == family["stored_signature_count"]

        for sig in children:
            assert set(sig.keys()) == {
                "source_entity_type",
                "primitive_kind",
                "layer",
                "linetype",
                "local_geometry_json",
            }
            assert "entity_handle" not in sig
            assert "nested_path" not in sig
            assert "transform_json" not in sig

        fp = definition_fingerprint_from_children(children)
        assert fp == family["definition_fingerprint"], family["family_id"]
        assert family["fingerprint_version"] == SYMBOL_FINGERPRINT_VERSION
        assert family["critical_issue_eligible"] is False
        assert family["declared_port_count"] == 0
        assert family["internal_connectivity_state"] == "UNKNOWN"
        assert family["registry_status"] == "UNKNOWN"


def test_shared_geometry_family_lists_multiple_names(fixture_doc: dict) -> None:
    shared = next(
        f for f in fixture_doc["families"] if f["family_id"] == "top2_pwf231_pwf248"
    )
    assert set(shared["definition_names"]) == {
        "SYMB2_M_PWF231",
        "SYMB2_M_PWF248",
    }
    assert shared["definition_fingerprint"].startswith("2ede8a4fcebd9582")


def test_kk2p_name_example_has_no_ports(fixture_doc: dict) -> None:
    kk2p = next(
        f for f in fixture_doc["families"] if f["family_id"] == "name_example_kk2p"
    )
    assert kk2p["definition_names"] == ["KK2P"]
    assert kk2p["declared_port_count"] == 0
    assert kk2p["critical_issue_eligible"] is False
    assert kk2p["internal_connectivity_state"] == "UNKNOWN"
    for sig in kk2p["child_signatures"]:
        assert "declared_port" not in sig
        assert "port_id" not in sig



def _synthetic_rows_for_family(family: dict, project_tag: str) -> list[dict]:
    """Build minimal INSERT + child rows for inventory (no ports)."""
    rows: list[dict] = []
    names = family["definition_names"]
    inserts = family.get("sample_inserts") or []
    # Prefer real sample_inserts; fall back to one synthetic insert per name.
    if not inserts:
        inserts = [
            {
                "definition_name": name,
                "local_geometry_json": '{"insert":[0,0,0]}',
                "layer": "0",
                "linetype": "BYLAYER",
                "source_entity_type": "INSERT",
                "primitive_kind": "INSERT",
            }
            for name in names
        ]
    # Cap to 1–2 inserts total for inventory shape (one per name, max 2 names).
    inserts = inserts[:2]

    for idx, insert in enumerate(inserts):
        name = str(insert["definition_name"])
        handle = f"I{project_tag}{idx}"
        rows.append(
            {
                "primitive_id": f"P{project_tag}-INS-{idx}",
                "sheet_id": f"S{project_tag}",
                "file_id": f"F{project_tag}",
                "entity_handle": handle,
                "primitive_kind": "INSERT",
                "source_entity_type": str(
                    insert.get("source_entity_type") or "INSERT"
                ),
                "definition_name": name,
                "nested_path": f"{name}[{handle}]",
                "transform_json": '{"translation":[0,0,0]}',
                "layer": str(insert.get("layer") or "0"),
                "linetype": str(insert.get("linetype") or "BYLAYER"),
                "local_geometry_json": str(
                    insert.get("local_geometry_json") or '{"insert":[0,0,0]}'
                ),
            }
        )
        # Attach full unique child signature set under this definition_name.
        # For multi-name families, each name gets the same geometry children.
        for cidx, sig in enumerate(family["child_signatures"]):
            rows.append(
                {
                    "primitive_id": f"P{project_tag}-C-{idx}-{cidx}",
                    "sheet_id": f"S{project_tag}",
                    "file_id": f"F{project_tag}",
                    "entity_handle": f"C{project_tag}{idx}{cidx}",
                    "primitive_kind": sig["primitive_kind"],
                    "source_entity_type": sig["source_entity_type"],
                    "definition_name": name,
                    "nested_path": f"{name}[{handle}]",
                    "transform_json": "{}",
                    "layer": sig["layer"],
                    "linetype": sig["linetype"],
                    "local_geometry_json": sig["local_geometry_json"],
                }
            )
    return rows


def test_build_inventory_from_fixture_yields_unknown_and_matching_fingerprint(
    fixture_doc: dict,
) -> None:
    for family in fixture_doc["families"]:
        rows = _synthetic_rows_for_family(family, project_tag=family["family_id"][:8])
        definitions, instances, unknown, summary = build_project_symbol_inventory(
            pd.DataFrame(rows), project_id="FIXTURE"
        )

        expected_names = set(family["definition_names"][:2])
        assert set(definitions["definition_name"]) == expected_names
        assert (definitions["definition_fingerprint"] == family["definition_fingerprint"]).all()
        assert (definitions["registry_status"] == "UNKNOWN").all()
        assert (definitions["critical_issue_eligible"] == False).all()
        assert (definitions["declared_port_count"] == 0).all()
        assert (definitions["fingerprint_version"] == SYMBOL_FINGERPRINT_VERSION).all()

        assert len(instances) == len(expected_names)
        assert (instances["definition_fingerprint"] == family["definition_fingerprint"]).all()
        assert (instances["registry_status"] == "UNKNOWN").all()

        assert len(unknown) == len(expected_names)
        assert (unknown["critical_issue_eligible"] == False).all()
        assert (unknown["definition_fingerprint"] == family["definition_fingerprint"]).all()
        assert summary["unknown_critical_issue_eligible_count"] == 0
        assert summary["registered_definition_count"] == 0


def test_optional_p001_parquet_full_children_fingerprint_for_pwf165(
    fixture_doc: dict,
) -> None:
    if not P001_PRIMITIVES.is_file():
        pytest.skip(f"P001 primitives not present: {P001_PRIMITIVES}")

    family = next(f for f in fixture_doc["families"] if f["family_id"] == "top1_pwf165")
    prims = pd.read_parquet(P001_PRIMITIVES)
    children = prims.loc[
        (prims["primitive_kind"] != "INSERT")
        & (prims["definition_name"] == "SYMB2_M_PWF165")
    ]
    assert not children.empty
    fp = definition_fingerprint_from_children(children)
    assert fp == family["definition_fingerprint"]
    assert fp.startswith("39b95b5118323d4d")
