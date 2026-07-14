from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from dwg_audit.report.hard_issue_eval import evaluate_hard_issue_label_pack
from dwg_audit.report.project_bundle import resolve_project_bundle_dir
from dwg_audit.report.topology_metrics import evaluate_project_topology_metrics
from dwg_audit.report.topology_metrics_artifacts import write_topology_metrics_artifacts


SCHEMA_VERSION = "promotion-gate-evidence-v1"
METRICS_SCHEMA = "metrics-by-project-v1"

# Structural release checks that do not require human hard labels.
STRUCTURAL_THRESHOLDS = {
    "false_clean_max": 0,
    "witness_completeness_min": 1.0,
    "unknown_unresolved_critical_max": 0,
    "failure_queue_critical_max": 0,
    "v2_changes_legacy_max": 0,
    "possible_union_allowed": False,
    "strong_violation_max": 0,
}

# Primary-engine flip requires labeled hard precision plus product approval.
PRIMARY_FLIP_THRESHOLDS = {
    "hard_issue_precision_min": 0.99,
    "hard_issue_recall_min": 0.99,
    "minimum_label_count": 1,
    "minimum_prediction_count": 1,
    "require_heldout_human_gold": True,
    "require_product_approval": True,
    "require_project_scope_topology_gold": True,
}

_COMPLETE_STATUSES = frozenset({"COMPLETE", "COMPLETE_EXTRACTION", "PASS", "PASSED"})

_TOPOLOGY_PRIMARY_RATIO_FIELDS = (
    "junction_precision",
    "junction_recall",
    "pairwise_connectivity_precision",
    "pairwise_connectivity_recall",
    "pairwise_connectivity_f1",
    "open_endpoint_precision",
    "open_endpoint_recall",
)

_TOPOLOGY_PRIMARY_STATUS_FIELDS = (
    "junction",
    "pairwise_connectivity",
    "open_endpoint",
)


def _normalized_split(value: str | None) -> str:
    return str(value or "").strip().casefold()


def _is_heldout_split(value: str | None) -> bool:
    return _normalized_split(value).startswith("heldout")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _load_json_artifact(
    path: Path,
    *,
    required_keys: tuple[str, ...],
) -> tuple[dict[str, Any], str]:
    payload = _load_json(path)
    if payload is None:
        return {}, "missing" if not path.is_file() else "invalid"
    if any(key not in payload for key in required_keys):
        return payload, "invalid"
    return payload, "valid"


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _finite_ratio(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        return None
    return parsed


def _topology_row_primary_ready(row: dict[str, Any]) -> bool:
    """Return whether one topology evidence row can support primary release.

    This validates the release contract only; it does not create or certify
    project gold.  Review-only suspicion counts are intentionally ignored.
    Real overmerge/split counts must be independently measured and exactly
    zero.
    """

    if (
        row.get("evaluation_status") != "MEASURED_PROJECT"
        or row.get("structural_metrics_complete") is not True
        or row.get("metrics_complete") is not True
        or row.get("measurement_scope") != "project"
    ):
        return False

    truth_metric_status = row.get("truth_metric_status")
    if not isinstance(truth_metric_status, dict) or any(
        truth_metric_status.get(name) != "measured_project"
        for name in _TOPOLOGY_PRIMARY_STATUS_FIELDS
    ):
        return False

    if any(
        (_finite_ratio(row.get(field)) or 0.0) <= 0.0
        for field in _TOPOLOGY_PRIMARY_RATIO_FIELDS
    ):
        return False

    if (_nonnegative_int(row.get("truth_sample_count")) or 0) <= 0:
        return False
    if (_nonnegative_int(row.get("truth_sheet_count")) or 0) <= 0:
        return False

    return (
        _nonnegative_int(row.get("network_overmerge_count")) == 0
        and _nonnegative_int(row.get("network_split_count")) == 0
    )


def _frame_count(path: Path, *, required_columns: tuple[str, ...]) -> tuple[int | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        import pandas as pd

        frame = pd.read_parquet(path)
    except Exception:
        return None, "invalid"
    if any(column not in frame.columns for column in required_columns):
        return None, "invalid"
    return int(len(frame)), "valid"


def _pair_issue_counts(
    project_dir: Path,
) -> tuple[int | None, int | None, dict[str, str]]:
    bundle_dir = resolve_project_bundle_dir(project_dir)
    findings = bundle_dir / "findings"
    pairs_path = findings / "pairs.parquet"
    issues_path = bundle_dir / "audit" / "issues.parquet"
    pair_count, pair_status = _frame_count(pairs_path, required_columns=("pair_id",))
    issue_count, issue_status = _frame_count(issues_path, required_columns=("issue_id", "rule_id"))
    return pair_count, issue_count, {
        "pairs": pair_status,
        "issues": issue_status,
    }


def _unknown_unresolved_critical_count(path: Path) -> tuple[int | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        import pandas as pd

        frame = pd.read_parquet(path)
    except Exception:
        return None, "invalid"
    required = {"severity", "category", "suggested_routing"}
    if not required.issubset(frame.columns):
        return None, "invalid"
    count = 0
    for row in frame.to_dict(orient="records"):
        if str(row.get("severity") or "").strip().casefold() != "critical":
            continue
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("category", "suggested_routing", "message")
        ).casefold()
        if "unknown" in haystack or "unresolved" in haystack:
            count += 1
    return count, "valid"


def collect_project_promotion_metrics(
    *,
    project_id: str,
    project_dir: Path,
    split: str | None = None,
) -> dict[str, Any]:
    """Collect promotion-relevant metrics from an already-written project bundle.

    Read-only. Does not mutate artifacts and does not flip primary_engine.
    """
    project_dir = Path(project_dir)
    bundle_dir = resolve_project_bundle_dir(project_dir)
    findings = bundle_dir / "findings"
    audit = bundle_dir / "audit"
    artifact_status: dict[str, str] = {}

    def load_artifact(
        name: str,
        path: Path,
        required_keys: tuple[str, ...],
    ) -> dict[str, Any]:
        payload, status = _load_json_artifact(path, required_keys=required_keys)
        artifact_status[name] = status
        return payload

    extraction = load_artifact(
        "extraction_gate",
        bundle_dir / "extraction_completeness.json",
        ("analysis_status", "clean_conclusion_allowed", "incomplete_page_count", "pages"),
    )
    engine = load_artifact(
        "engine_comparison",
        findings / "engine_comparison_v1.json",
        ("v2_changes_legacy_result_count",),
    )
    graph = load_artifact(
        "project_graph",
        findings / "project_graph_summary.json",
        ("sources",),
    )
    constraint = load_artifact(
        "constraint_summary",
        findings / "constraint_resolution_summary.json",
        ("strong_violation_count", "inviolable_strong_constraints"),
    )
    audit_v2 = load_artifact(
        "audit_v2_summary",
        audit / "audit_v2_summary.json",
        ("witness_completeness",),
    )
    failure = load_artifact(
        "failure_queue_summary",
        audit / "failure_queue_summary.json",
        ("critical_count", "by_category", "by_routing", "by_severity"),
    )
    topology_summary = load_artifact(
        "topology_summary",
        findings / "topology_decision_summary.json",
        ("non_asserted_union_violation_count",),
    )

    pair_count, issue_count, frame_status = _pair_issue_counts(project_dir)
    artifact_status.update(frame_status)
    unknown_critical, queue_status = _unknown_unresolved_critical_count(
        audit / "failure_queue.parquet"
    )
    artifact_status["failure_queue"] = queue_status

    analysis_status = str(extraction.get("analysis_status") or "INVALID_EXTRACTION_GATE").strip().upper()
    clean_allowed = extraction.get("clean_conclusion_allowed")
    incomplete_page_count = _nonnegative_int(extraction.get("incomplete_page_count"))
    pages = extraction.get("pages")
    if not isinstance(clean_allowed, bool) or incomplete_page_count is None or not isinstance(pages, list):
        artifact_status["extraction_gate"] = "invalid"
    audit_required_incomplete_page_count = 0
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, dict):
                artifact_status["extraction_gate"] = "invalid"
                continue
            disposition = str(page.get("audit_disposition") or "").strip().casefold()
            role = str(page.get("audit_role") or "").strip().casefold()
            expected_audit = disposition == "audit_required" or role in {"primary", "supplemental"}
            if expected_audit and str(page.get("status") or "").strip().upper() not in _COMPLETE_STATUSES:
                audit_required_incomplete_page_count += 1

    incomplete = analysis_status not in _COMPLETE_STATUSES or bool(incomplete_page_count)
    false_clean = bool(
        incomplete
        and (
            clean_allowed is True
            or (pair_count == 0 and issue_count == 0)
            or issue_count == 0
        )
    )

    witness = _finite_ratio(audit_v2.get("witness_completeness"))
    if witness is None and artifact_status["audit_v2_summary"] == "valid":
        artifact_status["audit_v2_summary"] = "invalid"

    strong_violation = _nonnegative_int(constraint.get("strong_violation_count"))
    inviolable = constraint.get("inviolable_strong_constraints")
    if strong_violation is None or not isinstance(inviolable, bool):
        artifact_status["constraint_summary"] = "invalid"

    sources = graph.get("sources")
    graph_possible_union = None
    if isinstance(sources, dict) and isinstance(sources.get("possible_union"), bool):
        graph_possible_union = bool(sources["possible_union"])
    else:
        artifact_status["project_graph"] = "invalid"

    non_asserted_union = _nonnegative_int(
        topology_summary.get("non_asserted_union_violation_count")
    )
    if non_asserted_union is None:
        artifact_status["topology_summary"] = "invalid"
    possible_union = bool(graph_possible_union) or bool(non_asserted_union)

    failure_critical = _nonnegative_int(failure.get("critical_count"))
    if (
        failure_critical is None
        or not isinstance(failure.get("by_category"), dict)
        or not isinstance(failure.get("by_routing"), dict)
        or not isinstance(failure.get("by_severity"), dict)
    ):
        artifact_status["failure_queue_summary"] = "invalid"

    v2_changes = _nonnegative_int(engine.get("v2_changes_legacy_result_count"))
    if v2_changes is None:
        artifact_status["engine_comparison"] = "invalid"

    return {
        "schema_version": METRICS_SCHEMA,
        "project_id": project_id,
        "split": split,
        "project_dir": str(project_dir.resolve()),
        "bundle_dir": str(bundle_dir.resolve()),
        "bundle_layout": (
            "direct"
            if bundle_dir.resolve() == project_dir.resolve()
            else "nested_project_slug"
        ),
        "analysis_status": analysis_status,
        "clean_conclusion_allowed": clean_allowed if isinstance(clean_allowed, bool) else None,
        "incomplete_page_count": incomplete_page_count,
        "audit_required_incomplete_page_count": audit_required_incomplete_page_count,
        "false_clean": false_clean,
        "pair_count": pair_count,
        "issue_count": issue_count,
        "witness_completeness": witness,
        "strong_violation_count": strong_violation,
        "inviolable_strong_constraints": inviolable,
        "possible_union": possible_union,
        "v2_changes_legacy_result_count": v2_changes,
        "failure_queue_critical_count": failure_critical,
        "unknown_or_unresolved_critical_count": unknown_critical,
        "non_asserted_union_violation_count": non_asserted_union,
        "artifact_status": dict(sorted(artifact_status.items())),
        "engine_comparison_present": artifact_status["engine_comparison"] == "valid",
        "audit_v2_present": artifact_status["audit_v2_summary"] == "valid",
        "project_graph_present": artifact_status["project_graph"] == "valid",
        "extraction_gate_present": artifact_status["extraction_gate"] == "valid",
    }


def _structural_pass(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for artifact, status in (metrics.get("artifact_status") or {}).items():
        if status != "valid":
            reasons.append(f"{artifact}_missing_or_invalid")
    if metrics.get("false_clean"):
        reasons.append("false_clean")
    if metrics.get("clean_conclusion_allowed") is not True:
        reasons.append("clean_conclusion_not_allowed")
    if metrics.get("incomplete_page_count") != 0:
        reasons.append("incomplete_pages")
    if metrics.get("audit_required_incomplete_page_count") != 0:
        reasons.append("audit_required_page_incomplete")
    witness = metrics.get("witness_completeness")
    if witness is None:
        reasons.append("witness_missing")
    elif float(witness) < STRUCTURAL_THRESHOLDS["witness_completeness_min"]:
        reasons.append("witness_below_threshold")
    if metrics.get("unknown_or_unresolved_critical_count") is None:
        reasons.append("unknown_unresolved_critical_missing")
    elif int(metrics.get("unknown_or_unresolved_critical_count") or 0) > STRUCTURAL_THRESHOLDS[
        "unknown_unresolved_critical_max"
    ]:
        reasons.append("unknown_unresolved_critical")
    if int(metrics.get("failure_queue_critical_count") or 0) > STRUCTURAL_THRESHOLDS[
        "failure_queue_critical_max"
    ]:
        reasons.append("failure_queue_critical")
    if int(metrics.get("v2_changes_legacy_result_count") or 0) > STRUCTURAL_THRESHOLDS[
        "v2_changes_legacy_max"
    ]:
        reasons.append("v2_changes_legacy")
    if metrics.get("possible_union") and not STRUCTURAL_THRESHOLDS["possible_union_allowed"]:
        reasons.append("possible_union")
    if int(metrics.get("strong_violation_count") or 0) > STRUCTURAL_THRESHOLDS[
        "strong_violation_max"
    ]:
        reasons.append("strong_violation")
    if metrics.get("inviolable_strong_constraints") is not True:
        reasons.append("strong_constraints_not_inviolable")
    if metrics.get("analysis_status") not in _COMPLETE_STATUSES:
        # incomplete is allowed only when not false-clean and explicitly gated;
        # for promotion structural pass on healthy corpus we require COMPLETE.
        reasons.append("analysis_not_complete")
    return (len(reasons) == 0, reasons)


def evaluate_promotion_gate(
    *,
    projects: dict[str, Path],
    splits: dict[str, str] | None = None,
    hard_issue_label_pack: Path | None = None,
    heldout_hard_issue_label_pack: Path | None = None,
    topology_truth_paths: dict[str, Path] | None = None,
    heldout_project_ids: set[str] | None = None,
    primary_engine: str = "legacy",
    product_approval: bool = False,
) -> dict[str, Any]:
    """Aggregate project metrics into promotion-gate evidence.

    Rules:
    - Never mutates recognition.primary_engine.
    - Held-out projects may be reported structurally but must not be used for tuning.
    - Hard precision uses frozen label pack only when provided.
    """
    splits = splits or {}
    topology_truth_paths = topology_truth_paths or {}
    heldout_project_ids = {
        str(project_id).strip()
        for project_id in (heldout_project_ids or set())
        if str(project_id).strip()
    }
    for project_id, split in splits.items():
        if _is_heldout_split(split):
            heldout_project_ids.add(project_id)
    if primary_engine not in {"legacy", "topology"}:
        raise ValueError(f"Unsupported primary_engine: {primary_engine}")
    metrics_rows: list[dict[str, Any]] = []
    topology_metrics_rows: list[dict[str, Any]] = []
    for project_id, project_dir in projects.items():
        row = collect_project_promotion_metrics(
            project_id=project_id,
            project_dir=Path(project_dir),
            split=splits.get(project_id),
        )
        topology_metrics = evaluate_project_topology_metrics(
            Path(project_dir),
            topology_truth_paths.get(project_id),
        )
        topology_metrics = {
            "project_id": project_id,
            "split": splits.get(project_id),
            **topology_metrics,
        }
        topology_metrics_rows.append(topology_metrics)
        row["topology_metrics_status"] = topology_metrics["evaluation_status"]
        row["topology_structural_metrics_complete"] = topology_metrics[
            "structural_metrics_complete"
        ]
        row["topology_metrics_complete"] = topology_metrics["metrics_complete"]
        row["topology_measurement_scope"] = topology_metrics["measurement_scope"]
        ok, reasons = _structural_pass(row)
        if not topology_metrics["structural_metrics_complete"]:
            ok = False
            reasons.append("topology_metrics_artifacts_missing_or_invalid")
        row["structural_pass"] = ok
        row["structural_fail_reasons"] = reasons
        row["is_heldout"] = project_id in heldout_project_ids or _is_heldout_split(row.get("split"))
        metrics_rows.append(row)

    non_heldout = [row for row in metrics_rows if not row.get("is_heldout")]
    heldout = [row for row in metrics_rows if row.get("is_heldout")]

    structural_all = all(row["structural_pass"] for row in metrics_rows) if metrics_rows else False
    structural_non_heldout = (
        all(row["structural_pass"] for row in non_heldout) if non_heldout else False
    )
    structural_heldout = all(row["structural_pass"] for row in heldout) if heldout else None

    hard_eval = None
    heldout_hard_eval = None
    hard_status = "UNMEASURED_NO_LABELS"
    hard_precision = None
    hard_precision_ge_99 = None
    not_human_gold = True
    if hard_issue_label_pack is not None:
        pack_projects = {
            pid: path
            for pid, path in projects.items()
            if pid not in heldout_project_ids
            and not _is_heldout_split(splits.get(pid))
        }
        hard_eval = evaluate_hard_issue_label_pack(hard_issue_label_pack, pack_projects)
        hard_precision = hard_eval.get("micro_precision")
        hard_precision_ge_99 = hard_eval.get("micro_precision_ge_99")
        policy = hard_eval.get("policy") or {}
        not_human_gold = bool(policy.get("not_a_human_gold_standard", True))

    if heldout_hard_issue_label_pack is not None:
        heldout_projects = {
            pid: path
            for pid, path in projects.items()
            if pid in heldout_project_ids or _is_heldout_split(splits.get(pid))
        }
        heldout_hard_eval = evaluate_hard_issue_label_pack(
            heldout_hard_issue_label_pack,
            heldout_projects,
        )

    calval_hard_pass = bool(
        hard_eval
        and hard_eval.get("micro_precision_ge_99") is True
        and hard_eval.get("micro_recall_ge_99") is True
        and hard_eval.get("non_vacuous") is True
        and hard_eval.get("prediction_artifacts_valid") is True
    )
    heldout_human_gold = bool(
        heldout_hard_eval
        and (heldout_hard_eval.get("policy") or {}).get("not_a_human_gold_standard") is False
    )
    heldout_hard_pass = bool(
        heldout_human_gold
        and heldout_hard_eval.get("micro_precision_ge_99") is True
        and heldout_hard_eval.get("micro_recall_ge_99") is True
        and heldout_hard_eval.get("non_vacuous") is True
        and heldout_hard_eval.get("prediction_artifacts_valid") is True
    )
    topology_metrics_primary_ready = bool(
        topology_metrics_rows
        and all(_topology_row_primary_ready(row) for row in topology_metrics_rows)
    )
    if hard_eval is not None:
        hard_status = (
            "PASS_ON_FROZEN_CALVAL_LABELS"
            if calval_hard_pass and not_human_gold
            else "PASS_ON_HUMAN_GOLD"
            if calval_hard_pass
            else "FAIL_ON_FROZEN_LABELS"
        )
    heldout_hard_status = (
        "PASS_ON_HUMAN_GOLD"
        if heldout_hard_pass
        else "FAIL_ON_HELDOUT_LABELS"
        if heldout_hard_eval is not None
        else "UNMEASURED_NO_HELDOUT_HUMAN_GOLD"
    )

    # Review-only assist is gated on non-held-out structural health only.
    ready_review_only = bool(structural_non_heldout)
    # Primary flip remains product-gated and blocked while labels are not human gold.
    ready_primary_flip = bool(
        structural_all
        and calval_hard_pass
        and heldout_hard_pass
        and topology_metrics_primary_ready
        and bool(product_approval)
        and primary_engine == "legacy"
    )

    decision = {
        "ready_for_review_only_v2_assist": ready_review_only and structural_non_heldout,
        "ready_for_primary_engine_flip": ready_primary_flip,
        "primary_engine_current": primary_engine,
        "primary_engine_recommended": "topology" if ready_primary_flip else primary_engine,
        "heldout_used_for_tuning": False,
        "heldout_project_ids": sorted(heldout_project_ids),
        "product_approval": bool(product_approval),
        "calval_hard_pass": calval_hard_pass,
        "heldout_hard_pass": heldout_hard_pass,
        "topology_metrics_primary_ready": topology_metrics_primary_ready,
        "hard_issue_precision_status": hard_status,
        "heldout_hard_issue_precision_status": heldout_hard_status,
        "notes": [
            "Shadow/compare/rollback path only; primary_engine is not flipped by this evaluator.",
            "Held-out projects are evaluation-only and never used for tuning.",
            "Frozen cal/val labels measure emission fidelity; human held-out gold is still required for primary flip.",
        ],
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "thresholds": {
            "structural": STRUCTURAL_THRESHOLDS,
            "primary_flip": PRIMARY_FLIP_THRESHOLDS,
        },
        "project_count": len(metrics_rows),
        "non_heldout_count": len(non_heldout),
        "heldout_count": len(heldout),
        "structural_pass_all": structural_all,
        "structural_pass_non_heldout": structural_non_heldout,
        "structural_pass_heldout": structural_heldout,
        "hard_issue_eval": hard_eval,
        "heldout_hard_issue_eval": heldout_hard_eval,
        "topology_metrics_by_project": topology_metrics_rows,
        "hard_issue_precision": hard_precision,
        "hard_issue_precision_ge_99": hard_precision_ge_99,
        "hard_issue_recall": hard_eval.get("micro_recall") if hard_eval else None,
        "hard_issue_recall_ge_99": hard_eval.get("micro_recall_ge_99") if hard_eval else None,
        "decision": decision,
        "projects": metrics_rows,
    }


def write_metrics_by_project_csv(rows: list[dict[str, Any]], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "project_id",
        "split",
        "is_heldout",
        "analysis_status",
        "clean_conclusion_allowed",
        "incomplete_page_count",
        "audit_required_incomplete_page_count",
        "false_clean",
        "pair_count",
        "issue_count",
        "witness_completeness",
        "strong_violation_count",
        "possible_union",
        "v2_changes_legacy_result_count",
        "failure_queue_critical_count",
        "unknown_or_unresolved_critical_count",
        "non_asserted_union_violation_count",
        "engine_comparison_present",
        "audit_v2_present",
        "project_graph_present",
        "extraction_gate_present",
        "artifact_status",
        "structural_pass",
        "structural_fail_reasons",
        "project_dir",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            reasons = out.get("structural_fail_reasons") or []
            out["structural_fail_reasons"] = "|".join(str(r) for r in reasons)
            out["artifact_status"] = json.dumps(
                out.get("artifact_status") or {},
                ensure_ascii=False,
                sort_keys=True,
            )
            writer.writerow(out)
    return path


def write_decision_log(evidence: dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    decision = evidence.get("decision") or {}
    lines = [
        "# Promotion Gate Decision Log",
        "",
        f"- schema: {evidence.get('schema_version')}",
        f"- structural_pass_all: {evidence.get('structural_pass_all')}",
        f"- structural_pass_non_heldout: {evidence.get('structural_pass_non_heldout')}",
        f"- structural_pass_heldout: {evidence.get('structural_pass_heldout')}",
        f"- hard_issue_precision_status: {decision.get('hard_issue_precision_status')}",
        f"- hard_issue_precision: {evidence.get('hard_issue_precision')}",
        f"- hard_issue_recall: {evidence.get('hard_issue_recall')}",
        f"- heldout_hard_issue_precision_status: {decision.get('heldout_hard_issue_precision_status')}",
        f"- product_approval: {decision.get('product_approval')}",
        f"- calval_hard_pass: {decision.get('calval_hard_pass')}",
        f"- heldout_hard_pass: {decision.get('heldout_hard_pass')}",
        f"- topology_metrics_primary_ready: {decision.get('topology_metrics_primary_ready')}",
        f"- ready_for_review_only_v2_assist: {decision.get('ready_for_review_only_v2_assist')}",
        f"- ready_for_primary_engine_flip: {decision.get('ready_for_primary_engine_flip')}",
        f"- primary_engine_current: {decision.get('primary_engine_current')}",
        f"- heldout_used_for_tuning: {decision.get('heldout_used_for_tuning')}",
        "",
        "## Notes",
    ]
    for note in decision.get("notes") or []:
        lines.append(f"- {note}")
    lines.extend(["", "## Projects"])
    for row in evidence.get("projects") or []:
        lines.append(
            f"- {row.get('project_id')} split={row.get('split')} "
            f"structural_pass={row.get('structural_pass')} "
            f"status={row.get('analysis_status')} "
            f"witness={row.get('witness_completeness')} "
            f"false_clean={row.get('false_clean')} "
            f"unknown_critical={row.get('unknown_or_unresolved_critical_count')}"
        )
        lines.append(
            f"  - artifacts: {json.dumps(row.get('artifact_status') or {}, ensure_ascii=False, sort_keys=True)}"
        )
        if row.get("structural_fail_reasons"):
            lines.append(f"  - fail: {', '.join(row['structural_fail_reasons'])}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_promotion_gate_evidence(
    evidence: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Persist promotion gate artifacts required by the taskbook loop deliverables."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / "promotion_gate_evidence.json"
    metrics_path = output_dir / "metrics_by_project.csv"
    decision_path = output_dir / "decision_log.md"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_metrics_by_project_csv(list(evidence.get("projects") or []), metrics_path)
    write_decision_log(evidence, decision_path)
    topology_paths = write_topology_metrics_artifacts(
        list(evidence.get("topology_metrics_by_project") or []),
        output_dir,
    )
    return {
        "promotion_gate_evidence": evidence_path,
        "metrics_by_project": metrics_path,
        "decision_log": decision_path,
        "topology_metrics_by_project": topology_paths["by_project"],
        "topology_metrics_summary": topology_paths["summary"],
    }
