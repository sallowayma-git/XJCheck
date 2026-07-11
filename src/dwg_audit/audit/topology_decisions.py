from __future__ import annotations

import json
import uuid
from typing import Any

import pandas as pd


OBSERVATION_SCHEMA_VERSION = "junction-observation-v2"
DECISION_SCHEMA_VERSION = "topology-decision-v2"
DECISION_ALGORITHM_VERSION = "geometry-observation-identity-v1"
VALID_STATES = {"ASSERTED", "POSSIBLE", "REJECTED", "UNKNOWN"}
_ID_NAMESPACE = uuid.UUID("225e7111-e772-5df1-8f92-c0ab248d160f")

_OBSERVATION_V2_COLUMNS = [
    "junction_observation_id",
    "schema_version",
    "algorithm_version",
    "source_observation_id",
    "project_id",
    "sheet_id",
    "observation_kind",
    "decision_kind",
    "state",
    "node_a_id",
    "node_b_id",
    "component_a_id",
    "component_b_id",
    "distance",
    "alignment_error",
    "source_line_ids",
    "evidence_ids",
    "reason_code",
    "requires_review",
]

_DECISION_COLUMNS = [
    "topology_decision_id",
    "schema_version",
    "algorithm_version",
    "junction_observation_id",
    "project_id",
    "sheet_id",
    "decision_kind",
    "decision_state",
    "node_a_id",
    "node_b_id",
    "component_a_id",
    "component_b_id",
    "source_line_ids",
    "evidence_ids",
    "reason_codes",
    "score_decomposition_json",
    "alternatives_json",
    "union_eligible",
    "union_applied",
    "requires_review",
]


def build_topology_decision_frames(
    geometry_observations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Project Phase 105 observations into append-only V2 decisions.

    This identity projection deliberately does not promote uncertain evidence and
    never applies union. Phase 116 may consume only rows marked union_eligible.
    """
    observation_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    for source in geometry_observations.to_dict(orient="records"):
        state = str(source.get("state") or "UNKNOWN").upper()
        if state not in VALID_STATES:
            state = "UNKNOWN"
        source_id = str(source.get("observation_id") or "")
        project_id = str(source.get("project_id") or "")
        sheet_id = str(source.get("sheet_id") or "")
        reason_code = str(source.get("reason_code") or "missing_reason_code")
        decision_kind = _decision_kind(source)
        observation_id = _stable_id(
            "JO2", project_id, sheet_id, source_id, decision_kind, state
        )
        decision_id = _stable_id("TD2", observation_id, DECISION_ALGORITHM_VERSION)
        source_line_ids = _list_value(source.get("source_line_ids"))
        evidence_ids = _list_value(source.get("evidence_ids"))
        requires_review = bool(source.get("requires_review")) or state in {
            "POSSIBLE",
            "UNKNOWN",
        }
        observation_rows.append(
            {
                "junction_observation_id": observation_id,
                "schema_version": OBSERVATION_SCHEMA_VERSION,
                "algorithm_version": DECISION_ALGORITHM_VERSION,
                "source_observation_id": source_id,
                "project_id": project_id,
                "sheet_id": sheet_id,
                "observation_kind": str(source.get("observation_kind") or "unknown"),
                "decision_kind": decision_kind,
                "state": state,
                "node_a_id": _nullable_string(source.get("node_a_id")),
                "node_b_id": _nullable_string(source.get("node_b_id")),
                "component_a_id": _nullable_string(source.get("component_a_id")),
                "component_b_id": _nullable_string(source.get("component_b_id")),
                "distance": _nullable_float(source.get("distance")),
                "alignment_error": _nullable_float(source.get("alignment_error")),
                "source_line_ids": source_line_ids,
                "evidence_ids": evidence_ids,
                "reason_code": reason_code,
                "requires_review": requires_review,
            }
        )
        decision_rows.append(
            {
                "topology_decision_id": decision_id,
                "schema_version": DECISION_SCHEMA_VERSION,
                "algorithm_version": DECISION_ALGORITHM_VERSION,
                "junction_observation_id": observation_id,
                "project_id": project_id,
                "sheet_id": sheet_id,
                "decision_kind": decision_kind,
                "decision_state": state,
                "node_a_id": _nullable_string(source.get("node_a_id")),
                "node_b_id": _nullable_string(source.get("node_b_id")),
                "component_a_id": _nullable_string(source.get("component_a_id")),
                "component_b_id": _nullable_string(source.get("component_b_id")),
                "source_line_ids": source_line_ids,
                "evidence_ids": evidence_ids,
                "reason_codes": [reason_code, "identity_projection_no_promotion_v1"],
                "score_decomposition_json": json.dumps(
                    {
                        "distance": _nullable_float(source.get("distance")),
                        "alignment_error": _nullable_float(source.get("alignment_error")),
                        "promotion_score": None,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "alternatives_json": json.dumps(
                    {
                        "selected": state,
                        "alternatives": sorted(VALID_STATES - {state}),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "union_eligible": state == "ASSERTED",
                "union_applied": False,
                "requires_review": requires_review,
            }
        )

    observations_v2 = pd.DataFrame(observation_rows).reindex(
        columns=_OBSERVATION_V2_COLUMNS
    )
    decisions = pd.DataFrame(decision_rows).reindex(columns=_DECISION_COLUMNS)
    violations = topology_decision_invariant_violations(decisions)
    summary = {
        "schema_version": "topology-decision-summary-v1",
        "observation_count": len(observations_v2),
        "decision_count": len(decisions),
        "state_counts": _counts(decisions, "decision_state"),
        "kind_counts": _counts(decisions, "decision_kind"),
        "union_eligible_count": int(decisions["union_eligible"].sum())
        if not decisions.empty
        else 0,
        "union_applied_count": int(decisions["union_applied"].sum())
        if not decisions.empty
        else 0,
        "non_asserted_union_violation_count": len(violations),
    }
    return observations_v2, decisions, summary


def topology_decision_invariant_violations(
    decisions: pd.DataFrame,
) -> list[str]:
    if decisions.empty:
        return []
    violations = decisions.loc[
        (decisions["decision_state"] != "ASSERTED")
        & (decisions["union_eligible"] | decisions["union_applied"])
    ]
    return sorted(str(value) for value in violations["topology_decision_id"])


def _decision_kind(source: dict[str, Any]) -> str:
    observation_kind = str(source.get("observation_kind") or "unknown")
    reason = str(source.get("reason_code") or "")
    if observation_kind == "endpoint_gap":
        return "endpoint_endpoint_gap"
    if observation_kind == "inline_span_candidate":
        return "inline_span"
    if observation_kind == "crossing":
        return "intersection"
    if observation_kind == "overlap":
        return "overlap"
    if "endpoint_merge" in reason:
        return "endpoint_endpoint"
    if "t_cross" in reason:
        return "endpoint_on_segment"
    if "crossing" in reason or "connection_marker" in reason:
        return "intersection"
    if "overlap" in reason:
        return "overlap"
    return observation_kind


def _stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}-{uuid.uuid5(_ID_NAMESPACE, '|'.join(parts))}"


def _list_value(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, (list, tuple, set)):
        return sorted(str(item) for item in value)
    return [str(value)]


def _nullable_string(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def _nullable_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty:
        return {}
    return {
        str(key): int(value)
        for key, value in frame[column].value_counts().sort_index().items()
    }
