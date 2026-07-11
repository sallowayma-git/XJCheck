
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_HARD_RULES = (
    "R-CROSS-PAGE-CONFLICT",
    "R-DUPLICATE-PAIR",
    "R-ONE-TO-MANY",
    "R-MANY-TO-ONE",
)


def load_hard_issue_label_pack(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_list(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                return [str(item) for item in parsed]
            except Exception:
                return [text]
        return [text]
    if hasattr(value, "tolist"):
        return [str(item) for item in value.tolist()]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _issue_match_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    evidence = row.get("evidence")
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except Exception:
            evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}
    filename = row.get("filename") or evidence.get("filename") or ""
    left = row.get("left_value")
    right = row.get("right_value")
    left_s = "" if left is None or (isinstance(left, float) and pd.isna(left)) else str(left)
    right_s = "" if right is None or (isinstance(right, float) and pd.isna(right)) else str(right)
    pair_id = row.get("pair_id")
    pair_s = "" if pair_id is None or (isinstance(pair_id, float) and pd.isna(pair_id)) else str(pair_id)
    sheet_id = row.get("sheet_id")
    sheet_s = "" if sheet_id is None or (isinstance(sheet_id, float) and pd.isna(sheet_id)) else str(sheet_id)
    values = tuple(sorted(_as_list(row.get("values"))))
    return (
        str(row.get("rule_id") or ""),
        sheet_s,
        str(filename),
        pair_s,
        left_s,
        right_s,
        values,
    )


def _label_match_tuple(label: dict[str, Any]) -> tuple[Any, ...]:
    values = tuple(sorted(str(v) for v in (label.get("values") or [])))
    return (
        str(label.get("rule_id") or ""),
        str(label.get("sheet_id") or ""),
        str(label.get("filename") or ""),
        str(label.get("pair_id") or ""),
        str(label.get("left_value") or ""),
        str(label.get("right_value") or ""),
        values,
    )


def predicted_hard_issues(
    issues: pd.DataFrame | list[dict[str, Any]],
    hard_rule_ids: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    rules = set(hard_rule_ids or DEFAULT_HARD_RULES)
    if isinstance(issues, pd.DataFrame):
        rows = issues.to_dict(orient="records") if not issues.empty else []
    else:
        rows = list(issues or [])
    return [row for row in rows if str(row.get("rule_id") or "") in rules]


def evaluate_hard_issue_precision(
    *,
    project_id: str,
    project_dir: Path,
    label_pack: dict[str, Any],
) -> dict[str, Any]:
    project_labels = (label_pack.get("projects") or {}).get(project_id) or {}
    labels = list(project_labels.get("labels") or [])
    hard_rules = list(label_pack.get("hard_rule_ids") or DEFAULT_HARD_RULES)

    issues_path = project_dir / "audit" / "issues.parquet"
    issues_json = project_dir / "audit" / "issues.json"
    if issues_path.is_file():
        issues_df = pd.read_parquet(issues_path)
    elif issues_json.is_file():
        issues_df = pd.DataFrame(json.loads(issues_json.read_text(encoding="utf-8")))
    else:
        issues_df = pd.DataFrame()

    predicted = predicted_hard_issues(issues_df, hard_rules)
    pred_keys = {_issue_match_tuple(row) for row in predicted}
    label_keys = {_label_match_tuple(row) for row in labels}

    tp_keys = pred_keys & label_keys
    fp_keys = pred_keys - label_keys
    fn_keys = label_keys - pred_keys
    precision = (len(tp_keys) / len(pred_keys)) if pred_keys else 1.0
    recall = (len(tp_keys) / len(label_keys)) if label_keys else 1.0

    # witness completeness from audit_v2 summary if present
    witness = None
    summary_path = project_dir / "audit" / "audit_v2_summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        witness = summary.get("witness_completeness")

    return {
        "schema_version": "hard-issue-eval-v1",
        "project_id": project_id,
        "project_dir": str(project_dir.resolve()),
        "hard_rule_ids": hard_rules,
        "label_count": len(label_keys),
        "predicted_count": len(pred_keys),
        "tp": len(tp_keys),
        "fp": len(fp_keys),
        "fn": len(fn_keys),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "precision_ge_99": bool(precision >= 0.99),
        "witness_completeness": witness,
        "label_basis": (label_pack.get("policy") or {}).get("label_basis"),
        "not_a_human_gold_standard": bool((label_pack.get("policy") or {}).get("not_a_human_gold_standard", True)),
    }


def evaluate_hard_issue_label_pack(
    label_pack_path: Path,
    project_dirs: dict[str, Path],
) -> dict[str, Any]:
    pack = load_hard_issue_label_pack(label_pack_path)
    evaluations = []
    for project_id, project_dir in project_dirs.items():
        evaluations.append(
            evaluate_hard_issue_precision(
                project_id=project_id,
                project_dir=project_dir,
                label_pack=pack,
            )
        )
    # micro totals
    tp = sum(int(item["tp"]) for item in evaluations)
    fp = sum(int(item["fp"]) for item in evaluations)
    fn = sum(int(item["fn"]) for item in evaluations)
    precision = (tp / (tp + fp)) if (tp + fp) else 1.0
    recall = (tp / (tp + fn)) if (tp + fn) else 1.0
    return {
        "schema_version": "hard-issue-eval-summary-v1",
        "label_pack_path": str(label_pack_path.resolve()),
        "project_count": len(evaluations),
        "micro_tp": tp,
        "micro_fp": fp,
        "micro_fn": fn,
        "micro_precision": round(precision, 6),
        "micro_recall": round(recall, 6),
        "micro_precision_ge_99": bool(precision >= 0.99),
        "projects": evaluations,
        "policy": pack.get("policy") or {},
    }
