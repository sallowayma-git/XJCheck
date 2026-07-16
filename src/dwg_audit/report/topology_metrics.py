from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.report.project_bundle import resolve_project_bundle_dir


SCHEMA_VERSION = "topology-metrics-v1"

_ARTIFACTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "lines": (
        "lines.parquet",
        ("line_id", "sheet_id", "handle"),
    ),
    "topology_decisions": (
        "topology_decisions.parquet",
        (
            "topology_decision_id",
            "junction_observation_id",
            "decision_kind",
            "decision_state",
            "union_eligible",
            "union_applied",
        ),
    ),
    "geometry_shadow_components": (
        "geometry_shadow_components.parquet",
        (
            "geometry_component_id",
            "sheet_id",
            "source_line_ids",
            "open_node_ids",
            "junction_node_ids",
        ),
    ),
    "electrical_networks_v2": (
        "electrical_networks_v2.parquet",
        (
            "electrical_network_id",
            "sheet_id",
            "source_line_ids",
            "node_ids",
            "junction_node_ids",
            "open_node_ids",
        ),
    ),
    "network_open_endpoints_v2": (
        "network_open_endpoints_v2.parquet",
        (
            "electrical_network_id",
            "sheet_id",
            "node_id",
            "source_line_ids",
            "source_handles",
            "boundary_state",
        ),
    ),
    "network_validation_suspicions_v2": (
        "network_validation_suspicions_v2.parquet",
        ("suspicion_id", "suspicion_kind", "review_only"),
    ),
    "legacy_pair_network_equivalence": (
        "legacy_pair_network_equivalence.parquet",
        ("pair_id", "equivalence_status", "v2_changes_legacy_result"),
    ),
}


def evaluate_project_topology_metrics(
    project_dir: Path,
    truth_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate one persisted Topology V2 project bundle without mutating it.

    Missing, corrupt, or schema-incomplete required artifacts make the overall
    evaluation invalid. Metrics whose own dependencies remain valid are retained
    for diagnosis, but callers must use ``evaluation_status``/``artifact_status``
    as the release gate rather than treating absent metrics as zeros.
    """
    project_dir = Path(project_dir)
    bundle_dir = resolve_project_bundle_dir(project_dir)
    findings_dir = bundle_dir / "findings"
    frames: dict[str, pd.DataFrame] = {}
    artifact_status: dict[str, str] = {}
    artifact_errors: dict[str, str] = {}

    for name, (filename, required_columns) in _ARTIFACTS.items():
        frame, status, error = _load_parquet(
            findings_dir / filename,
            required_columns=required_columns,
        )
        if (
            name == "network_validation_suspicions_v2"
            and status == "invalid"
            and frame.empty
            and error is not None
            and error.startswith("missing columns:")
        ):
            # Older healthy bundles wrote a readable zero-row Parquet without
            # columns. This compatibility applies only to the review-only
            # suspicion table; any non-empty or unreadable file remains invalid.
            frame = pd.DataFrame(columns=list(required_columns))
            status = "valid"
            error = None
        frames[name] = frame
        artifact_status[name] = status
        if error:
            artifact_errors[name] = error

    _validate_boolean_columns(
        frames,
        artifact_status,
        artifact_errors,
        {
            "topology_decisions": ("union_eligible", "union_applied"),
            "network_validation_suspicions_v2": ("review_only",),
            "legacy_pair_network_equivalence": ("v2_changes_legacy_result",),
        },
    )

    witness_summary, witness_status, witness_error = _load_witness_summary(
        findings_dir / "network_witness_summary.json"
    )
    artifact_status["network_witness_summary"] = witness_status
    if witness_error:
        artifact_errors["network_witness_summary"] = witness_error

    truth, truth_status, truth_error = _load_truth(truth_path)
    artifact_status["truth"] = truth_status
    if truth_error:
        artifact_errors["truth"] = truth_error

    required_valid = all(artifact_status[name] == "valid" for name in _ARTIFACTS) and witness_status == "valid"

    lines = frames["lines"]
    decisions = frames["topology_decisions"]
    components = frames["geometry_shadow_components"]
    networks = frames["electrical_networks_v2"]
    open_endpoints = frames["network_open_endpoints_v2"]
    suspicions = frames["network_validation_suspicions_v2"]
    equivalence = frames["legacy_pair_network_equivalence"]

    junction = _empty_binary_metrics()
    pairwise = _empty_binary_metrics(include_f1=True)
    open_metric = _empty_binary_metrics()
    truth_metric_status = {
        "junction": "unmeasured_no_labels",
        "pairwise_connectivity": "unmeasured_no_labels",
        "open_endpoint": "unmeasured_no_labels",
    }
    if truth_status == "valid":
        junction, truth_metric_status["junction"] = _evaluate_junction_truth(
            truth,
            decisions if artifact_status["topology_decisions"] == "valid" else None,
            components
            if artifact_status["geometry_shadow_components"] == "valid"
            else None,
            lines if artifact_status["lines"] == "valid" else None,
        )
        pairwise, truth_metric_status["pairwise_connectivity"] = (
            _evaluate_pairwise_truth(
                truth,
                networks
                if artifact_status["electrical_networks_v2"] == "valid"
                else None,
            )
        )
        open_metric, truth_metric_status["open_endpoint"] = (
            _evaluate_open_endpoint_truth(
                truth,
                open_endpoints
                if artifact_status["network_open_endpoints_v2"] == "valid"
                else None,
            )
        )
    elif truth_status in {"missing", "invalid"}:
        truth_metric_status = {
            "junction": "invalid_truth",
            "pairwise_connectivity": "invalid_truth",
            "open_endpoint": "invalid_truth",
        }

    truth_valid = truth_status == "not_provided" or (
        truth_status == "valid"
        and truth_metric_status["junction"] in {"measured_scoped", "measured_project"}
    )

    overmerge_count: int | None = None
    split_count: int | None = None
    if artifact_status["network_validation_suspicions_v2"] == "valid":
        kinds = suspicions["suspicion_kind"].fillna("").astype(str).str.upper()
        overmerge_count = int((kinds == "OVERMERGE_SUSPICION").sum())
        split_count = int((kinds == "SPLIT_SUSPICION").sum())

    non_asserted_union_violation_count: int | None = None
    if artifact_status["topology_decisions"] == "valid":
        states = decisions["decision_state"].fillna("UNKNOWN").astype(str).str.upper()
        eligible = decisions["union_eligible"].map(_as_bool)
        applied = decisions["union_applied"].map(_as_bool)
        non_asserted_union_violation_count = int(
            ((states != "ASSERTED") & (eligible.eq(True) | applied.eq(True))).sum()
        )

    v2_changes_legacy_result_count: int | None = None
    if artifact_status["legacy_pair_network_equivalence"] == "valid":
        changed = equivalence["v2_changes_legacy_result"].map(_as_bool)
        v2_changes_legacy_result_count = int(changed.eq(True).sum())

    witness_dependencies_valid = witness_status == "valid" and all(
        artifact_status[name] == "valid"
        for name in ("electrical_networks_v2", "network_open_endpoints_v2")
    )
    witness_complete_count = (
        witness_summary.get("resolved_count") if witness_dependencies_valid else None
    )
    witness_total_count = (
        witness_summary.get("witness_count") if witness_dependencies_valid else None
    )
    witness_completeness = (
        witness_summary.get("witness_completeness")
        if witness_dependencies_valid
        else None
    )

    measured_statuses = set(truth_metric_status.values())
    all_truth_metrics_measured = all(
        status in {"measured_scoped", "measured_project"}
        for status in truth_metric_status.values()
    )
    measurement_scope = (
        "project"
        if measured_statuses == {"measured_project"}
        else "scoped"
        if any(status == "measured_scoped" for status in measured_statuses)
        else None
    )
    evaluation_status = (
        "INVALID"
        if not required_valid or not truth_valid
        else "MEASURED_PROJECT"
        if all_truth_metrics_measured and measurement_scope == "project"
        else "MEASURED_SCOPED"
        if truth_status == "valid"
        else "STRUCTURAL_ONLY"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "project_dir": str(project_dir.resolve()),
        "truth_path": str(Path(truth_path).resolve()) if truth_path is not None else None,
        "evaluation_status": evaluation_status,
        "structural_metrics_complete": required_valid,
        "metrics_complete": bool(
            required_valid
            and all_truth_metrics_measured
            and measurement_scope == "project"
        ),
        "measurement_scope": measurement_scope,
        "truth_sample_count": int(len(truth)) if truth_status == "valid" else 0,
        "truth_sheet_count": int(truth["sheet_id"].nunique())
        if truth_status == "valid" and "sheet_id" in truth.columns
        else 0,
        "artifact_status": dict(sorted(artifact_status.items())),
        "artifact_errors": dict(sorted(artifact_errors.items())),
        "truth_metric_status": truth_metric_status,
        "junction_true_positive_count": junction["tp"],
        "junction_false_positive_count": junction["fp"],
        "junction_false_negative_count": junction["fn"],
        "junction_precision": junction["precision"],
        "junction_recall": junction["recall"],
        "network_overmerge_suspicion_count": overmerge_count,
        "network_split_suspicion_count": split_count,
        # Suspicion rows are structural review signals, not certified topology
        # gold.  Keep the real error counts unmeasured until a separate,
        # provenance-checked project gold contract exists.
        "network_overmerge_count": None,
        "network_split_count": None,
        "pairwise_connectivity_true_positive_count": pairwise["tp"],
        "pairwise_connectivity_false_positive_count": pairwise["fp"],
        "pairwise_connectivity_false_negative_count": pairwise["fn"],
        "pairwise_connectivity_precision": pairwise["precision"],
        "pairwise_connectivity_recall": pairwise["recall"],
        "pairwise_connectivity_f1": pairwise["f1"],
        "open_endpoint_true_positive_count": open_metric["tp"],
        "open_endpoint_false_positive_count": open_metric["fp"],
        "open_endpoint_false_negative_count": open_metric["fn"],
        "open_endpoint_precision": open_metric["precision"],
        "open_endpoint_recall": open_metric["recall"],
        "witness_complete_count": witness_complete_count,
        "witness_total_count": witness_total_count,
        "witness_completeness": witness_completeness,
        "non_asserted_union_violation_count": non_asserted_union_violation_count,
        "v2_changes_legacy_result_count": v2_changes_legacy_result_count,
    }


def _load_parquet(
    path: Path,
    *,
    required_columns: tuple[str, ...],
) -> tuple[pd.DataFrame, str, str | None]:
    if not path.is_file():
        return pd.DataFrame(), "missing", f"missing artifact: {path}"
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:
        return pd.DataFrame(), "invalid", f"unable to read parquet: {type(exc).__name__}"
    missing = sorted(set(required_columns).difference(frame.columns))
    if missing:
        return frame, "invalid", f"missing columns: {', '.join(missing)}"
    return frame, "valid", None


def _load_truth(path: Path | None) -> tuple[pd.DataFrame, str, str | None]:
    if path is None:
        return pd.DataFrame(), "not_provided", None
    path = Path(path)
    if not path.is_file():
        return pd.DataFrame(), "missing", f"missing truth CSV: {path}"
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        return pd.DataFrame(), "invalid", f"unable to read truth CSV: {type(exc).__name__}"
    if not isinstance(frame, pd.DataFrame) or not len(frame.columns):
        return pd.DataFrame(), "invalid", "truth CSV has no columns"
    return frame, "valid", None


def _load_witness_summary(path: Path) -> tuple[dict[str, Any], str, str | None]:
    if not path.is_file():
        return {}, "missing", f"missing artifact: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, "invalid", f"unable to read witness summary: {type(exc).__name__}"
    if not isinstance(payload, dict):
        return {}, "invalid", "witness summary must be a JSON object"
    required = ("witness_count", "resolved_count", "unresolved_count", "witness_completeness")
    if any(key not in payload for key in required):
        return payload, "invalid", "witness summary missing required fields"
    try:
        total = int(payload["witness_count"])
        resolved = int(payload["resolved_count"])
        unresolved = int(payload["unresolved_count"])
        completeness = float(payload["witness_completeness"])
    except (TypeError, ValueError, OverflowError):
        return payload, "invalid", "witness summary contains invalid numeric fields"
    if (
        total < 0
        or resolved < 0
        or unresolved < 0
        or resolved + unresolved != total
        or not 0.0 <= completeness <= 1.0
        or (total and abs(completeness - resolved / total) > 1e-6)
        or (not total and completeness != 1.0)
    ):
        return payload, "invalid", "witness summary counts/completeness are inconsistent"
    return {
        **payload,
        "witness_count": total,
        "resolved_count": resolved,
        "unresolved_count": unresolved,
        "witness_completeness": completeness,
    }, "valid", None


def _validate_boolean_columns(
    frames: dict[str, pd.DataFrame],
    statuses: dict[str, str],
    errors: dict[str, str],
    columns_by_artifact: dict[str, tuple[str, ...]],
) -> None:
    for name, columns in columns_by_artifact.items():
        if statuses.get(name) != "valid":
            continue
        frame = frames[name]
        invalid_columns = [
            column
            for column in columns
            if frame[column].map(_as_bool).isna().any()
        ]
        if invalid_columns:
            statuses[name] = "invalid"
            errors[name] = f"invalid boolean values: {', '.join(invalid_columns)}"


def _evaluate_junction_truth(
    truth: pd.DataFrame,
    decisions: pd.DataFrame | None,
    components: pd.DataFrame | None,
    lines: pd.DataFrame | None,
) -> tuple[dict[str, Any], str]:
    explicit_node_column = _first_column(truth, ("junction_node_id",))
    node_label_column = _first_column(
        truth,
        ("expected_junction", "is_junction", "junction_expected"),
    )
    if components is not None and (explicit_node_column or node_label_column):
        node_column = explicit_node_column or _first_column(truth, ("node_id",))
        if node_column:
            predicted = _component_node_keys(components, "junction_node_ids")
            return _evaluate_identity_truth(
                truth,
                predicted,
                identity_column=node_column,
                label_column=node_label_column,
            ), _measurement_status(truth)

    if decisions is None:
        return _empty_binary_metrics(), "artifact_unavailable"
    decision_id_column = _first_column(
        truth,
        ("topology_decision_id", "junction_observation_id"),
    )
    if decision_id_column and "expected_state" in truth.columns:
        prediction_column = decision_id_column
        predicted = {
            str(row[prediction_column]): str(row["decision_state"]).upper() == "ASSERTED"
            for _, row in decisions.iterrows()
            if not _blank(row.get(prediction_column))
        }
        rows: list[tuple[bool, bool]] = []
        for _, row in truth.iterrows():
            identity = row.get(decision_id_column)
            expected_state = row.get("expected_state")
            if _blank(identity) or _blank(expected_state):
                continue
            rows.append(
                (
                    bool(predicted.get(str(identity), False)),
                    str(expected_state).strip().upper() == "ASSERTED",
                )
            )
        return _binary_metrics(rows), _measurement_status(truth) if rows else "unsupported_schema"

    handle_signature_columns = {
        "sheet_id",
        "decision_kind",
        "reason_code",
        "source_handles",
        "expected_state",
    }
    if handle_signature_columns.issubset(truth.columns) and lines is not None:
        truth_signatures: list[
            tuple[str, str, str, tuple[str, ...]]
        ] = []
        seen_truth_signatures: set[tuple[str, str, str, tuple[str, ...]]] = set()
        expected_by_signature: dict[
            tuple[str, str, str, tuple[str, ...]], bool
        ] = {}
        for row in truth.to_dict(orient="records"):
            signature = (
                str(row.get("sheet_id") or ""),
                str(row.get("decision_kind") or ""),
                str(row.get("reason_code") or ""),
                tuple(sorted(str(value) for value in _listish(row.get("source_handles")))),
            )
            if signature in seen_truth_signatures:
                return _empty_binary_metrics(), "invalid_duplicate_signature"
            seen_truth_signatures.add(signature)
            truth_signatures.append(signature)
            expected_by_signature[signature] = (
                str(row.get("expected_state") or "").strip().upper() == "ASSERTED"
            )
        handle_by_line = {
            (str(row.get("sheet_id") or ""), str(row.get("line_id") or "")): str(
                row.get("handle") or ""
            )
            for row in lines.to_dict(orient="records")
        }
        predicted: dict[tuple[str, str, str, tuple[str, ...]], bool] = {}
        duplicate_prediction = False
        for row in decisions.to_dict(orient="records"):
            reasons = _listish(row.get("reason_codes"))
            sheet_id = str(row.get("sheet_id") or "")
            handles = tuple(
                sorted(
                    handle_by_line.get((sheet_id, str(line_id)), f"missing:{line_id}")
                    for line_id in _listish(row.get("source_line_ids"))
                )
            )
            signature = (
                sheet_id,
                str(row.get("decision_kind") or ""),
                str(reasons[0]) if reasons else "",
                handles,
            )
            if signature not in seen_truth_signatures:
                continue
            if signature in predicted:
                duplicate_prediction = True
            predicted[signature] = str(row.get("decision_state") or "").upper() == "ASSERTED"
        if duplicate_prediction:
            return _empty_binary_metrics(), "invalid_duplicate_signature"
        rows = [
            (bool(predicted.get(signature, False)), expected_by_signature[signature])
            for signature in truth_signatures
        ]
        return _binary_metrics(rows), _measurement_status(truth) if rows else "unsupported_schema"

    signature_columns = {"sheet_id", "decision_kind", "reason_code", "source_line_ids"}
    if signature_columns.issubset(truth.columns) and "expected_state" in truth.columns:
        predicted = {
            _decision_signature(row): str(row.get("decision_state") or "").upper()
            == "ASSERTED"
            for row in decisions.to_dict(orient="records")
        }
        rows = []
        for row in truth.to_dict(orient="records"):
            if _blank(row.get("expected_state")):
                continue
            rows.append(
                (
                    bool(predicted.get(_truth_decision_signature(row), False)),
                    str(row["expected_state"]).strip().upper() == "ASSERTED",
                )
            )
        return _binary_metrics(rows), _measurement_status(truth) if rows else "unsupported_schema"
    return _empty_binary_metrics(), "unsupported_schema"


def _evaluate_pairwise_truth(
    truth: pd.DataFrame,
    networks: pd.DataFrame | None,
) -> tuple[dict[str, Any], str]:
    if networks is None:
        return _empty_binary_metrics(include_f1=True), "artifact_unavailable"
    left_column = _first_column(
        truth,
        ("source_line_id_a", "line_a_id", "left_line_id", "member_a_id"),
    )
    right_column = _first_column(
        truth,
        ("source_line_id_b", "line_b_id", "right_line_id", "member_b_id"),
    )
    label_column = _first_column(
        truth,
        ("expected_connected", "is_connected", "pairwise_connected"),
    )
    if not left_column or not right_column or not label_column:
        return _empty_binary_metrics(include_f1=True), "unsupported_schema"

    networks_by_line: dict[str, set[str]] = {}
    for row in networks.to_dict(orient="records"):
        network_id = str(row.get("electrical_network_id") or "")
        for line_id in _listish(row.get("source_line_ids")):
            networks_by_line.setdefault(str(line_id), set()).add(network_id)
    rows: list[tuple[bool, bool]] = []
    for row in truth.to_dict(orient="records"):
        left = row.get(left_column)
        right = row.get(right_column)
        expected = _as_bool(row.get(label_column))
        if _blank(left) or _blank(right) or expected is None:
            continue
        predicted = bool(
            networks_by_line.get(str(left), set())
            & networks_by_line.get(str(right), set())
        )
        rows.append((predicted, expected))
    return (
        _binary_metrics(rows, include_f1=True),
        _measurement_status(truth) if rows else "unsupported_schema",
    )


def _evaluate_open_endpoint_truth(
    truth: pd.DataFrame,
    open_endpoints: pd.DataFrame | None,
) -> tuple[dict[str, Any], str]:
    if open_endpoints is None:
        return _empty_binary_metrics(), "artifact_unavailable"
    explicit_node_column = _first_column(
        truth,
        ("open_node_id", "endpoint_node_id"),
    )
    label_column = _first_column(
        truth,
        ("expected_open", "is_open_endpoint", "open_endpoint_expected"),
    )
    if not explicit_node_column and not label_column:
        return _empty_binary_metrics(), "unsupported_schema"
    node_column = explicit_node_column or _first_column(truth, ("node_id",))
    if not node_column:
        return _empty_binary_metrics(), "unsupported_schema"
    predicted = _row_node_keys(open_endpoints, "node_id")
    return _evaluate_identity_truth(
        truth,
        predicted,
        identity_column=node_column,
        label_column=label_column,
    ), _measurement_status(truth)


def _measurement_status(truth: pd.DataFrame) -> str:
    """Classify the current legacy CSV truth format as scoped evidence only.

    A CSV column is self-asserted metadata and cannot certify exhaustive
    project coverage.  A future project-gold pack needs its own validated
    provenance contract; until then even ``measurement_scope=project`` is
    deliberately downgraded to scoped measurement.
    """

    del truth
    return "measured_scoped"


def _evaluate_identity_truth(
    truth: pd.DataFrame,
    predicted_keys: set[str],
    *,
    identity_column: str,
    label_column: str | None,
) -> dict[str, Any]:
    has_sheet = "sheet_id" in truth.columns
    if label_column is None:
        truth_keys = {
            _node_key(row.get("sheet_id") if has_sheet else None, row.get(identity_column))
            for row in truth.to_dict(orient="records")
            if not _blank(row.get(identity_column))
        }
        if not has_sheet:
            predicted_keys = {_node_id_from_key(value) for value in predicted_keys}
        return _set_metrics(predicted_keys, truth_keys)

    rows: list[tuple[bool, bool]] = []
    for row in truth.to_dict(orient="records"):
        identity = row.get(identity_column)
        expected = _as_bool(row.get(label_column))
        if _blank(identity) or expected is None:
            continue
        key = _node_key(row.get("sheet_id") if has_sheet else None, identity)
        predicted = (
            key in predicted_keys
            if has_sheet
            else str(identity) in {_node_id_from_key(value) for value in predicted_keys}
        )
        rows.append((predicted, expected))
    return _binary_metrics(rows)


def _component_node_keys(frame: pd.DataFrame, column: str) -> set[str]:
    keys: set[str] = set()
    for row in frame.to_dict(orient="records"):
        for node_id in _listish(row.get(column)):
            keys.add(_node_key(row.get("sheet_id"), node_id))
    return keys


def _row_node_keys(frame: pd.DataFrame, column: str) -> set[str]:
    return {
        _node_key(row.get("sheet_id"), row.get(column))
        for row in frame.to_dict(orient="records")
        if not _blank(row.get(column))
    }


def _witness_counts(
    components: pd.DataFrame,
    networks: pd.DataFrame,
    open_endpoints: pd.DataFrame,
) -> tuple[int, int]:
    component_open_nodes = _component_node_keys(components, "open_node_ids")
    network_open_nodes: dict[str, set[str]] = {}
    for row in networks.to_dict(orient="records"):
        network_id = str(row.get("electrical_network_id") or "")
        network_open_nodes[network_id] = {
            _node_key(row.get("sheet_id"), node_id)
            for node_id in _listish(row.get("open_node_ids"))
        }

    complete = 0
    rows = open_endpoints.to_dict(orient="records")
    for row in rows:
        network_id = str(row.get("electrical_network_id") or "")
        key = _node_key(row.get("sheet_id"), row.get("node_id"))
        traceable = bool(
            _listish(row.get("source_line_ids"))
            and _listish(row.get("source_handles"))
        )
        if (
            network_id in network_open_nodes
            and key in network_open_nodes[network_id]
            and key in component_open_nodes
            and str(row.get("boundary_state") or "").strip().upper() == "OPEN"
            and traceable
        ):
            complete += 1
    return complete, len(rows)


def _binary_metrics(
    rows: list[tuple[bool, bool]],
    *,
    include_f1: bool = False,
) -> dict[str, Any]:
    if not rows:
        return _empty_binary_metrics(include_f1=include_f1)
    tp = sum(predicted and expected for predicted, expected in rows)
    fp = sum(predicted and not expected for predicted, expected in rows)
    fn = sum(not predicted and expected for predicted, expected in rows)
    precision = _ratio(tp, tp + fp, empty_value=0.0)
    recall = _ratio(tp, tp + fn, empty_value=0.0)
    result: dict[str, Any] = {
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "precision": precision,
        "recall": recall,
    }
    if include_f1:
        result["f1"] = _f1(precision, recall)
    return result


def _set_metrics(predicted: set[str], expected: set[str]) -> dict[str, Any]:
    if not predicted and not expected:
        return _empty_binary_metrics()
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": _ratio(tp, tp + fp, empty_value=0.0),
        "recall": _ratio(tp, tp + fn, empty_value=0.0),
    }


def _empty_binary_metrics(*, include_f1: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tp": None,
        "fp": None,
        "fn": None,
        "precision": None,
        "recall": None,
    }
    if include_f1:
        result["f1"] = None
    return result


def _ratio(numerator: int, denominator: int, *, empty_value: float) -> float:
    if denominator == 0:
        return empty_value
    return round(numerator / denominator, 6)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return round(2.0 * precision * recall / (precision + recall), 6)


def _first_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    return next((column for column in candidates if column in frame.columns), None)


def _decision_signature(row: dict[str, Any]) -> tuple[str, str, str, tuple[str, ...]]:
    reasons = _listish(row.get("reason_codes"))
    return (
        str(row.get("sheet_id") or ""),
        str(row.get("decision_kind") or ""),
        str(reasons[0]) if reasons else "",
        tuple(sorted(str(value) for value in _listish(row.get("source_line_ids")))),
    )


def _truth_decision_signature(
    row: dict[str, Any],
) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        str(row.get("sheet_id") or ""),
        str(row.get("decision_kind") or ""),
        str(row.get("reason_code") or ""),
        tuple(sorted(str(value) for value in _listish(row.get("source_line_ids")))),
    )


def _node_key(sheet_id: Any, node_id: Any) -> str:
    return f"{'' if _blank(sheet_id) else str(sheet_id)}\x1f{str(node_id)}"


def _node_id_from_key(value: str) -> str:
    return value.split("\x1f", 1)[-1]


def _listish(value: Any) -> list[Any]:
    if value is None or _blank(value):
        return []
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, bytearray)):
        converted = value.tolist()
        return converted if isinstance(converted, list) else [converted]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str) and "|" in value:
        return [part for part in value.split("|") if part]
    return [value]


def _as_bool(value: Any) -> bool | None:
    if value is None or _blank(value):
        return None
    if isinstance(value, bool):
        return value
    if type(value).__name__ == "bool_":
        return bool(value)
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "y", "asserted", "open", "connected"}:
            return True
        if normalized in {"false", "0", "no", "n", "rejected", "closed", "disconnected"}:
            return False
    return None


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return not value
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(result, bool):
        return result
    return False
