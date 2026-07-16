from __future__ import annotations

import pandas as pd

from dwg_audit.audit.symbol_registry import (
    build_project_symbol_inventory,
    definition_fingerprint_from_children,
    rank_symbol_annotation_backlog,
)


def _insert_row(
    *,
    primitive_id: str,
    sheet_id: str,
    file_id: str,
    entity_handle: str,
    definition_name: str,
    nested_path: str,
    transform_json: str,
    local_geometry_json: str = '{"insert":[0,0,0]}',
) -> dict:
    return {
        "primitive_id": primitive_id,
        "sheet_id": sheet_id,
        "file_id": file_id,
        "entity_handle": entity_handle,
        "primitive_kind": "INSERT",
        "source_entity_type": "INSERT",
        "definition_name": definition_name,
        "nested_path": nested_path,
        "transform_json": transform_json,
        "layer": "0",
        "linetype": "BYLAYER",
        "local_geometry_json": local_geometry_json,
    }


def _line_child(
    *,
    primitive_id: str,
    sheet_id: str,
    file_id: str,
    entity_handle: str,
    definition_name: str,
    nested_path: str,
    local_geometry_json: str = '{"end":[1,0,0],"start":[0,0,0]}',
) -> dict:
    return {
        "primitive_id": primitive_id,
        "sheet_id": sheet_id,
        "file_id": file_id,
        "entity_handle": entity_handle,
        "primitive_kind": "LINE",
        "source_entity_type": "LINE",
        "definition_name": definition_name,
        "nested_path": nested_path,
        "transform_json": "{}",
        "layer": "PORT",
        "linetype": "BYLAYER",
        "local_geometry_json": local_geometry_json,
    }


def test_symbol_fingerprint_excludes_instance_world_transform_and_handle() -> None:
    rows = [
        _insert_row(
            primitive_id="P1",
            sheet_id="S1",
            file_id="F1",
            entity_handle="I1",
            definition_name="DEVICE",
            nested_path="DEVICE[I1]",
            transform_json='{"translation":[0,0,0]}',
            local_geometry_json='{"insert":[0,0,0]}',
        ),
        _insert_row(
            primitive_id="P2",
            sheet_id="S2",
            file_id="F2",
            entity_handle="I2",
            definition_name="DEVICE",
            nested_path="DEVICE[I2]",
            transform_json='{"translation":[100,50,0]}',
            local_geometry_json='{"insert":[100,50,0]}',
        ),
        _line_child(
            primitive_id="P3",
            sheet_id="S1",
            file_id="F1",
            entity_handle="L1",
            definition_name="DEVICE",
            nested_path="DEVICE[I1]",
        ),
        _line_child(
            primitive_id="P4",
            sheet_id="S2",
            file_id="F2",
            entity_handle="L2",
            definition_name="DEVICE",
            nested_path="DEVICE[I2]",
        ),
    ]

    definitions, instances, unknown, summary = build_project_symbol_inventory(
        pd.DataFrame(rows), project_id="PROJECT"
    )

    assert len(definitions) == 1
    assert definitions.iloc[0]["instance_count"] == 2
    assert definitions.iloc[0]["sheet_count"] == 2
    assert definitions.iloc[0]["local_geometry_signature_count"] == 1
    assert definitions.iloc[0]["transform_variant_count"] == 2
    assert str(definitions.iloc[0]["symbol_definition_id"]).startswith("SD1-")
    assert len(str(definitions.iloc[0]["symbol_definition_id"])) == len("SD1-") + 32
    assert len(instances) == 2
    assert unknown.iloc[0]["critical_issue_eligible"] == False
    assert summary["unknown_critical_issue_eligible_count"] == 0


def test_empty_children_different_names_share_fingerprint_distinct_definition_ids() -> None:
    rows = [
        _insert_row(
            primitive_id="P1",
            sheet_id="S1",
            file_id="F1",
            entity_handle="I1",
            definition_name="RELAY_A",
            nested_path="RELAY_A[I1]",
            transform_json='{"translation":[0,0,0]}',
        ),
        _insert_row(
            primitive_id="P2",
            sheet_id="S1",
            file_id="F1",
            entity_handle="I2",
            definition_name="RELAY_B",
            nested_path="RELAY_B[I2]",
            transform_json='{"translation":[10,0,0]}',
        ),
    ]

    definitions, _instances, unknown, summary = build_project_symbol_inventory(
        pd.DataFrame(rows), project_id="P1"
    )

    assert len(definitions) == 2
    fingerprints = set(definitions["definition_fingerprint"])
    definition_ids = set(definitions["symbol_definition_id"])
    assert len(fingerprints) == 1
    assert len(definition_ids) == 2
    empty_fp = definition_fingerprint_from_children(pd.DataFrame())
    assert fingerprints == {empty_fp}
    assert set(unknown["symbol_definition_id"]) == definition_ids
    assert unknown["unknown_symbol_id"].nunique() == 2
    assert summary["definition_count"] == 2
    assert summary["unknown_definition_count"] == 2


def test_same_name_local_geometry_collapses_across_world_transforms() -> None:
    rows = [
        _insert_row(
            primitive_id="P1",
            sheet_id="S1",
            file_id="F1",
            entity_handle="H1",
            definition_name="CB01",
            nested_path="CB01[H1]",
            transform_json='{"translation":[0,0,0]}',
        ),
        _insert_row(
            primitive_id="P2",
            sheet_id="S2",
            file_id="F2",
            entity_handle="H2",
            definition_name="CB01",
            nested_path="CB01[H2]",
            transform_json='{"translation":[200,10,0]}',
        ),
        _line_child(
            primitive_id="C1",
            sheet_id="S1",
            file_id="F1",
            entity_handle="L1",
            definition_name="CB01",
            nested_path="CB01[H1]",
            local_geometry_json='{"end":[2,0,0],"start":[0,0,0]}',
        ),
        _line_child(
            primitive_id="C2",
            sheet_id="S2",
            file_id="F2",
            entity_handle="L2",
            definition_name="CB01",
            nested_path="CB01[H2]",
            local_geometry_json='{"end":[2,0,0],"start":[0,0,0]}',
        ),
    ]

    definitions, instances, unknown, summary = build_project_symbol_inventory(
        pd.DataFrame(rows), project_id="PROJ"
    )

    assert len(definitions) == 1
    assert definitions.iloc[0]["definition_name"] == "CB01"
    assert definitions.iloc[0]["instance_count"] == 2
    assert definitions["definition_fingerprint"].nunique() == 1
    assert len(instances) == 2
    assert instances["definition_fingerprint"].nunique() == 1
    assert len(unknown) == 1
    assert summary["instance_count"] == 2


def test_unknown_queue_never_critical_and_ranked_by_priority() -> None:
    rows = [
        _insert_row(
            primitive_id="P1",
            sheet_id="S1",
            file_id="F1",
            entity_handle="I1",
            definition_name="RARE",
            nested_path="RARE[I1]",
            transform_json="{}",
        ),
        _insert_row(
            primitive_id="P2",
            sheet_id="S1",
            file_id="F1",
            entity_handle="I2",
            definition_name="COMMON",
            nested_path="COMMON[I2]",
            transform_json="{}",
        ),
        _insert_row(
            primitive_id="P3",
            sheet_id="S1",
            file_id="F1",
            entity_handle="I3",
            definition_name="COMMON",
            nested_path="COMMON[I3]",
            transform_json="{}",
        ),
        _insert_row(
            primitive_id="P4",
            sheet_id="S1",
            file_id="F1",
            entity_handle="I4",
            definition_name="COMMON",
            nested_path="COMMON[I4]",
            transform_json="{}",
        ),
    ]

    _definitions, _instances, unknown, summary = build_project_symbol_inventory(
        pd.DataFrame(rows), project_id="RANK"
    )

    assert (unknown["critical_issue_eligible"] == False).all()
    assert summary["unknown_critical_issue_eligible_count"] == 0
    assert list(unknown["definition_name"]) == ["COMMON", "RARE"]
    assert list(unknown["project_rank"]) == [1, 2]
    assert list(unknown["priority_score"]) == [3, 1]


def test_rank_symbol_annotation_backlog_orders_by_priority_and_coverage() -> None:
    proj_a = pd.DataFrame(
        [
            {
                "project_id": "A",
                "definition_name": "DEV_A",
                "definition_fingerprint": "fp_high",
                "instance_count": 5,
            },
            {
                "project_id": "A",
                "definition_name": "DEV_LOCAL",
                "definition_fingerprint": "fp_local",
                "instance_count": 10,
            },
        ]
    )
    proj_b = pd.DataFrame(
        [
            {
                "project_id": "B",
                "definition_name": "DEV_B",
                "definition_fingerprint": "fp_high",
                "instance_count": 3,
            },
            {
                "project_id": "B",
                "definition_name": "DEV_MID",
                "definition_fingerprint": "fp_mid",
                "instance_count": 4,
            },
        ]
    )
    proj_c = pd.DataFrame(
        [
            {
                "project_id": "C",
                "definition_name": "DEV_C",
                "definition_fingerprint": "fp_high",
                "instance_count": 2,
            },
        ]
    )

    backlog = rank_symbol_annotation_backlog([proj_a, proj_b, proj_c])

    assert list(backlog["definition_fingerprint"]) == ["fp_high", "fp_local", "fp_mid"]
    assert list(backlog["corpus_rank"]) == [1, 2, 3]
    high = backlog.iloc[0]
    assert high["total_instance_count"] == 10
    assert high["project_coverage"] == 3
    assert high["priority_score"] == 30
    assert high["project_ids"] == ["A", "B", "C"]
    assert high["definition_names"] == ["DEV_A", "DEV_B", "DEV_C"]
    assert high["registry_status"] == "UNKNOWN"
    assert high["critical_issue_eligible"] == False
    assert backlog.iloc[1]["project_coverage"] == 1
    assert backlog.iloc[1]["priority_score"] == 10
    assert backlog.iloc[2]["priority_score"] == 4


def test_rank_symbol_annotation_backlog_excludes_transparent_insert_wrappers() -> None:
    frame = pd.DataFrame(
        [
            {
                "project_id": "P",
                "definition_name": "SignBlock_0.1",
                "definition_fingerprint": "empty-wrapper",
                "instance_count": 14,
                "local_geometry_signature_count": 0,
            },
            {
                "project_id": "P",
                "definition_name": "REAL_CHILD",
                "definition_fingerprint": "real-child",
                "instance_count": 2,
                "local_geometry_signature_count": 3,
            },
        ]
    )

    backlog = rank_symbol_annotation_backlog([frame])

    assert list(backlog["definition_fingerprint"]) == ["real-child"]


def test_empty_primitive_segments_returns_empty_frames_and_zero_summary() -> None:
    definitions, instances, unknown, summary = build_project_symbol_inventory(
        pd.DataFrame(), project_id="EMPTY"
    )

    assert definitions.empty
    assert instances.empty
    assert unknown.empty
    assert summary["definition_count"] == 0
    assert summary["instance_count"] == 0
    assert summary["unknown_definition_count"] == 0
    assert summary["registered_definition_count"] == 0
    assert summary["unknown_critical_issue_eligible_count"] == 0

    backlog = rank_symbol_annotation_backlog([])
    assert backlog.empty
    assert list(backlog.columns) == [
        "corpus_rank",
        "definition_fingerprint",
        "definition_names",
        "total_instance_count",
        "project_coverage",
        "project_ids",
        "priority_score",
        "registry_status",
        "critical_issue_eligible",
        "reason_code",
    ]
