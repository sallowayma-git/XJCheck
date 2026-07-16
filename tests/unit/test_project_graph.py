from __future__ import annotations

import pandas as pd

from dwg_audit.audit.project_graph import ALGORITHM_VERSION
from dwg_audit.audit.project_graph import ENDPOINT_IDENTITY_SCHEMA
from dwg_audit.audit.project_graph import (
    build_cross_page_endpoint_candidates,
    build_endpoint_identities,
    build_project_graph,
)
from dwg_audit.audit.audit_v2 import compare_legacy_new_relations


def test_build_endpoint_identities_from_open_and_authoritative_attachment() -> None:
    open_endpoints = [
        {
            "electrical_network_id": "EN1",
            "sheet_id": "S1",
            "node_id": "N1",
            "coord": [10.0, 20.0],
            "source_line_ids": ["L1"],
            "source_handles": ["H1"],
            "boundary_state": "OPEN",
        }
    ]
    attachments = [
        {
            "attachment_id": "A1",
            "sheet_id": "S1",
            "token_id": "T1",
            "token_kind": "TERMINAL_LOCAL",
            "token_text": "101",
            "target_line_id": "L1",
            "target_x": 10.5,
            "target_y": 20.0,
            "selected": True,
            "constraint_authority": "AUTHORITATIVE",
            "scope_state": "UNSCOPED",
        }
    ]
    identities = build_endpoint_identities(open_endpoints, attachments, project_id="P")
    network = [row for row in identities if row["identity_kind"] == "NETWORK_OPEN"]
    tokens = [row for row in identities if row["identity_kind"] == "ATTACHMENT_SELECTED"]
    assert len(network) == 1
    assert network[0]["authority"] == "AUTHORITATIVE"
    assert network[0]["label"] == "101"
    assert len(tokens) == 1
    assert tokens[0]["authority"] == "AUTHORITATIVE"


def test_cross_page_candidates_require_shared_authoritative_label() -> None:
    identities = [
        {
            "endpoint_id": "E1",
            "sheet_id": "S1",
            "label": "n105",
            "authority": "AUTHORITATIVE",
        },
        {
            "endpoint_id": "E2",
            "sheet_id": "S2",
            "label": "N105",
            "authority": "AUTHORITATIVE",
        },
        {
            "endpoint_id": "E3",
            "sheet_id": "S3",
            "label": "n105",
            "authority": "GEOMETRY_ONLY",
        },
    ]
    candidates = build_cross_page_endpoint_candidates(identities)
    assert len(candidates) == 1
    assert candidates[0]["state"] == "CANDIDATE"
    assert candidates[0]["relation"] == "CROSS_PAGE_LABEL"
    assert candidates[0]["reciprocal"] is True


def test_project_graph_redlines_forbid_possible_union() -> None:
    graph = build_project_graph(
        [{"endpoint_id": "E1", "authority": "GEOMETRY_ONLY", "identity_kind": "NETWORK_OPEN"}],
        [],
        [{"electrical_network_id": "EN1"}],
        constraint_summary={"review_only_count": 3},
        project_id="P",
    )
    assert graph["sources"]["possible_union"] is False
    assert graph["redlines"]["no_possible_union"] is True
    assert graph["node_counts"]["electrical_networks"] == 1
    assert graph["unresolved"]["review_only_attachments_excluded"] == 3


def test_engine_comparison_shadow_only() -> None:
    report = compare_legacy_new_relations(
        [{"pair_id": "P1"}, {"pair_id": "P2"}],
        [
            {"equivalence_status": "UNIQUE_V2_NETWORK", "v2_changes_legacy_result": False},
            {"equivalence_status": "NO_NETWORK", "v2_changes_legacy_result": False},
        ],
    )
    assert report["pair_count"] == 2
    assert report["v2_changes_legacy_result_count"] == 0
    assert report["unique_v2_network_rate"] == 0.5
    assert "legacy" in str(report.get("notes") or "").lower()


def test_empty_inputs_safe() -> None:
    assert build_endpoint_identities([], [], project_id="P") == []
    assert build_cross_page_endpoint_candidates([]) == []
    graph = build_project_graph([], [], [], project_id="P")
    assert graph["node_counts"]["endpoint_identities"] == 0


def _open_endpoint(
    *,
    node_id: str = "N1",
    sheet_id: str = "S1",
    network_id: str = "EN1",
    coord: list | None = None,
    source_line_ids: list | None = None,
    source_handles: list | None = None,
    boundary_state: str = "OPEN",
) -> dict:
    return {
        "electrical_network_id": network_id,
        "sheet_id": sheet_id,
        "node_id": node_id,
        "coord": coord if coord is not None else [0.0, 0.0],
        "source_line_ids": source_line_ids if source_line_ids is not None else ["L1"],
        "source_handles": source_handles if source_handles is not None else ["H1"],
        "boundary_state": boundary_state,
        "reason_code": "OPEN_ENDPOINT",
    }


def _attachment(
    *,
    attachment_id: str = "A1",
    sheet_id: str = "S1",
    token_id: str = "TK1",
    token_text: str = "X1",
    token_kind: str = "SIGNAL",
    selected: bool = True,
    score: float = 0.9,
    margin: float = 0.1,
    scope_state: str = "SCOPED",
    scope_key: str | None = "scope-a",
    target_line_id: str = "L1",
    target_endpoint: str = "start",
    target_x: float | None = 0.0,
    target_y: float | None = 0.0,
    constraint_authority: str | None = "AUTHORITATIVE",
) -> dict:
    row = {
        "attachment_id": attachment_id,
        "sheet_id": sheet_id,
        "token_id": token_id,
        "token_text": token_text,
        "token_kind": token_kind,
        "selected": selected,
        "score": score,
        "margin": margin,
        "scope_state": scope_state,
        "scope_key": scope_key,
        "target_line_id": target_line_id,
        "target_endpoint": target_endpoint,
        "target_x": target_x,
        "target_y": target_y,
    }
    if constraint_authority is not None:
        row["constraint_authority"] = constraint_authority
    return row


def test_open_endpoint_geometry_only_without_attachment() -> None:
    opens = [_open_endpoint()]
    identities = build_endpoint_identities(opens, project_id="P1")
    assert len(identities) == 1
    ident = identities[0]
    assert ident["endpoint_id"].startswith("EP1-")
    assert ident["identity_kind"] == "NETWORK_OPEN"
    assert ident["authority"] == "GEOMETRY_ONLY"
    assert ident["label"] is None
    assert ident["namespace"] == "sheet:S1"
    assert ident["local_key"] == "N1"


def test_distance_gate_rejects_far_attachment() -> None:
    opens = [_open_endpoint(coord=[0.0, 0.0], source_line_ids=["L1"])]
    far = _attachment(
        attachment_id="A_FAR",
        target_line_id="L99",
        target_x=100.0,
        target_y=100.0,
        token_text="FAR",
    )
    identities = build_endpoint_identities(opens, [far], project_id="P1")
    network_open = [i for i in identities if i["identity_kind"] == "NETWORK_OPEN"][0]
    assert network_open["authority"] == "GEOMETRY_ONLY"
    assert network_open["label"] is None

    near = _attachment(
        attachment_id="A_NEAR",
        target_line_id="L1",
        target_x=1.0,
        target_y=0.5,
        token_text="NEAR",
    )
    identities2 = build_endpoint_identities(opens, [near], project_id="P1")
    network_open2 = [i for i in identities2 if i["identity_kind"] == "NETWORK_OPEN"][0]
    assert network_open2["authority"] == "AUTHORITATIVE"
    assert network_open2["label"] == "NEAR"


def test_distance_gate_rejects_far_even_with_line_match() -> None:
    opens = [_open_endpoint(coord=[0.0, 0.0], source_line_ids=["L1"])]
    far_same_line = _attachment(
        target_line_id="L1",
        target_x=10.0,
        target_y=10.0,
        token_text="FARLINE",
    )
    identities = build_endpoint_identities(opens, [far_same_line], project_id="P1")
    network_open = [i for i in identities if i["identity_kind"] == "NETWORK_OPEN"][0]
    assert network_open["authority"] == "GEOMETRY_ONLY"
    assert network_open["label"] is None


def test_constraint_authority_missing_falls_back_to_selected() -> None:
    opens = [_open_endpoint(coord=[0.0, 0.0], source_line_ids=["L1"])]
    att = _attachment(
        constraint_authority=None,
        selected=True,
        scope_state="SCOPED",
        target_line_id="L1",
        target_x=0.0,
        target_y=0.0,
        token_text="FB",
    )
    att.pop("constraint_authority", None)
    identities = build_endpoint_identities(opens, [att], project_id="P1")
    network_open = [i for i in identities if i["identity_kind"] == "NETWORK_OPEN"][0]
    assert network_open["authority"] == "AUTHORITATIVE"
    assert network_open["label"] == "FB"

    amb = _attachment(
        constraint_authority=None,
        selected=True,
        scope_state="AMBIGUOUS",
        target_line_id="L1",
        target_x=0.0,
        target_y=0.0,
        token_text="AMB",
    )
    amb.pop("constraint_authority", None)
    identities2 = build_endpoint_identities(opens, [amb], project_id="P1")
    network_open2 = [i for i in identities2 if i["identity_kind"] == "NETWORK_OPEN"][0]
    assert network_open2["authority"] == "GEOMETRY_ONLY"
    token_ids = [i for i in identities2 if i["identity_kind"] == "ATTACHMENT_SELECTED"]
    assert token_ids == []


def test_cross_page_single_sheet_no_candidates() -> None:
    identities = [
        {
            "endpoint_id": "EP1-aaa",
            "sheet_id": "S1",
            "label": "X1",
            "authority": "AUTHORITATIVE",
        },
        {
            "endpoint_id": "EP1-bbb",
            "sheet_id": "S1",
            "label": "X1",
            "authority": "AUTHORITATIVE",
        },
    ]
    assert build_cross_page_endpoint_candidates(identities) == []


def test_dataframe_input_accepted() -> None:
    opens_df = pd.DataFrame([_open_endpoint(node_id="N9", sheet_id="S9")])
    atts_df = pd.DataFrame(
        [
            _attachment(
                sheet_id="S9",
                target_line_id="L1",
                target_x=0.0,
                target_y=0.0,
                token_text="DF",
            )
        ]
    )
    identities = build_endpoint_identities(opens_df, atts_df, project_id="P")
    assert any(i["identity_kind"] == "NETWORK_OPEN" for i in identities)
    assert any(i["identity_kind"] == "ATTACHMENT_SELECTED" for i in identities)
