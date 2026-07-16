"""Corpus-level Top-N symbol port review queue.

Aggregates non-held-out project symbol inventories into a deterministic backlog
for human port / internal-connectivity annotation.  Held-out projects may be
reported separately but never influence ranking when excluded.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.audit.symbol_registry import rank_symbol_annotation_backlog


QUEUE_SCHEMA_VERSION = "symbol-corpus-queue-v1"
SUMMARY_SCHEMA_VERSION = "symbol-corpus-queue-summary-v1"
BY_PROJECT_FILENAME = "symbol_corpus_queue_by_project.csv"
QUEUE_FILENAME = "symbol_corpus_queue_topn.csv"
SUMMARY_FILENAME = "symbol_corpus_queue_summary.json"
QUEUE_JSON_FILENAME = "symbol_corpus_queue_topn.json"


def _find_findings_dir(project_dir: Path) -> Path | None:
    from dwg_audit.report.project_bundle import find_findings_dir

    return find_findings_dir(project_dir)


def _load_definition_frame(findings_dir: Path, *, project_alias: str) -> pd.DataFrame:
    path = findings_dir / "symbol_definitions_v1.parquet"
    if not path.is_file():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    if frame.empty:
        return frame
    out = frame.copy()
    if "project_id" not in out.columns or out["project_id"].isna().all():
        out["project_id"] = project_alias
    else:
        # Keep original project_id values but ensure ranking can group by alias too.
        out["project_id"] = out["project_id"].astype(str)
    out["source_project_alias"] = project_alias
    return out


def _audit_impact(findings_dir: Path) -> dict[str, int]:
    pair_count = 0
    issue_count = 0
    pairs = findings_dir / "pairs.parquet"
    issues = findings_dir.parent / "audit" / "issues.parquet"
    if not issues.is_file():
        issues = findings_dir / "issues.parquet"
    try:
        if pairs.is_file():
            pair_count = int(len(pd.read_parquet(pairs, columns=[])))
    except Exception:
        try:
            pair_count = int(len(pd.read_parquet(pairs)))
        except Exception:
            pair_count = 0
    try:
        if issues.is_file():
            issue_count = int(len(pd.read_parquet(issues, columns=[])))
    except Exception:
        try:
            issue_count = int(len(pd.read_parquet(issues)))
        except Exception:
            issue_count = 0
    return {"pair_count": pair_count, "issue_count": issue_count}


def evaluate_symbol_corpus_queue(
    project_dirs: Mapping[str, Path],
    *,
    splits: Mapping[str, str] | None = None,
    held_out_projects: set[str] | None = None,
    top_n: int = 50,
    include_held_out_in_ranking: bool = False,
) -> dict[str, Any]:
    """Build a deterministic Top-N symbol review queue from persisted inventories."""

    splits = {str(key): str(value) for key, value in (splits or {}).items()}
    held_out = {str(item) for item in (held_out_projects or set())}
    top_n = max(1, int(top_n))

    project_rows: list[dict[str, Any]] = []
    ranking_frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []

    for alias in sorted(project_dirs):
        project_dir = Path(project_dirs[alias])
        split = splits.get(alias)
        is_held_out = alias in held_out or (
            split is not None and "heldout" in split.lower()
        )
        findings_dir = _find_findings_dir(project_dir)
        row: dict[str, Any] = {
            "project_alias": alias,
            "project_dir": str(project_dir),
            "split": split or ("heldout_test" if is_held_out else "unknown"),
            "is_held_out": bool(is_held_out),
            "status": "MISSING",
            "definition_count": 0,
            "instance_count": 0,
            "unknown_definition_count": 0,
            "pair_count": 0,
            "issue_count": 0,
            "included_in_ranking": False,
            "error": "",
        }
        if findings_dir is None:
            row["error"] = "findings directory not found"
            errors.append({"project_alias": alias, "code": "FINDINGS_MISSING", "message": row["error"]})
            project_rows.append(row)
            continue
        try:
            definitions = _load_definition_frame(findings_dir, project_alias=alias)
            impact = _audit_impact(findings_dir)
            row["pair_count"] = impact["pair_count"]
            row["issue_count"] = impact["issue_count"]
            if definitions.empty:
                row["status"] = "EMPTY"
                row["error"] = "symbol_definitions_v1.parquet missing or empty"
                errors.append(
                    {
                        "project_alias": alias,
                        "code": "SYMBOL_DEFINITIONS_MISSING",
                        "message": row["error"],
                    }
                )
            else:
                row["status"] = "VALID"
                row["definition_count"] = int(len(definitions))
                if "instance_count" in definitions.columns:
                    row["instance_count"] = int(definitions["instance_count"].fillna(0).sum())
                if "registry_status" in definitions.columns:
                    row["unknown_definition_count"] = int(
                        (definitions["registry_status"].astype(str) == "UNKNOWN").sum()
                    )
                else:
                    row["unknown_definition_count"] = row["definition_count"]
                # Ranking identity uses alias so multi-project coverage is path-stable.
                ranking_frame = definitions.copy()
                ranking_frame["project_id"] = alias
                include = (not is_held_out) or include_held_out_in_ranking
                row["included_in_ranking"] = bool(include)
                if include:
                    ranking_frames.append(ranking_frame)
        except Exception as exc:
            row["status"] = "INVALID"
            row["error"] = f"{type(exc).__name__}: {exc}"
            errors.append(
                {
                    "project_alias": alias,
                    "code": "SYMBOL_QUEUE_LOAD_FAILED",
                    "message": row["error"],
                }
            )
        project_rows.append(row)

    ranked = rank_symbol_annotation_backlog(ranking_frames)
    if ranked.empty:
        queue_rows: list[dict[str, Any]] = []
    else:
        # Enrich with audit-impact proxy: sum pair/issue from covered projects.
        impact_by_alias = {
            row["project_alias"]: {
                "pair_count": int(row["pair_count"]),
                "issue_count": int(row["issue_count"]),
            }
            for row in project_rows
            if row["included_in_ranking"]
        }
        queue_rows = []
        for _, item in ranked.iterrows():
            project_ids = list(item.get("project_ids") or [])
            pair_proxy = sum(
                impact_by_alias.get(pid, {}).get("pair_count", 0) for pid in project_ids
            )
            issue_proxy = sum(
                impact_by_alias.get(pid, {}).get("issue_count", 0) for pid in project_ids
            )
            priority = int(item["priority_score"])
            # Keep the registry rank primary; impact is an additive tie-visible score.
            audit_impact_score = priority + issue_proxy
            names = item.get("definition_names") or []
            if hasattr(names, "tolist"):
                names = list(names)
            pids = project_ids
            if hasattr(pids, "tolist"):
                pids = list(pids)
            queue_rows.append(
                {
                    "corpus_rank": int(item["corpus_rank"]),
                    "definition_fingerprint": str(item["definition_fingerprint"]),
                    "definition_names": list(names),
                    "definition_names_text": "|".join(str(name) for name in names),
                    "total_instance_count": int(item["total_instance_count"]),
                    "project_coverage": int(item["project_coverage"]),
                    "project_ids": list(pids),
                    "project_ids_text": "|".join(str(pid) for pid in pids),
                    "priority_score": priority,
                    "pair_count_proxy": int(pair_proxy),
                    "issue_count_proxy": int(issue_proxy),
                    "audit_impact_score": int(audit_impact_score),
                    "registry_status": "UNKNOWN",
                    "critical_issue_eligible": False,
                    "annotation_status": "PENDING_HUMAN_REVIEW",
                    "declared_port_count": 0,
                    "reason_code": str(item.get("reason_code") or "UNREGISTERED_DEFINITION_REVIEW_REQUIRED"),
                    "held_out_used_in_ranking": bool(include_held_out_in_ranking),
                }
            )
        queue_rows.sort(
            key=lambda row: (
                -int(row["audit_impact_score"]),
                -int(row["priority_score"]),
                -int(row["total_instance_count"]),
                str(row["definition_fingerprint"]),
            )
        )
        for rank, row in enumerate(queue_rows, start=1):
            row["review_rank"] = rank
        queue_rows = queue_rows[:top_n]

    ranking_project_count = sum(1 for row in project_rows if row["included_in_ranking"])
    valid_project_count = sum(1 for row in project_rows if row["status"] == "VALID")
    held_out_count = sum(1 for row in project_rows if row["is_held_out"])
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "queue_schema_version": QUEUE_SCHEMA_VERSION,
        "project_count": len(project_rows),
        "valid_project_count": valid_project_count,
        "ranking_project_count": ranking_project_count,
        "held_out_project_count": held_out_count,
        "held_out_usage": (
            "included_in_ranking"
            if include_held_out_in_ranking
            else "reporting_only"
        ),
        "top_n": top_n,
        "queue_row_count": len(queue_rows),
        "total_ranked_families": int(len(ranked)) if ranked is not None else 0,
        "pending_human_review_count": len(queue_rows),
        "critical_issue_eligible_count": 0,
        "declared_port_count_total": 0,
        "status": "VALID" if ranking_project_count > 0 and queue_rows else (
            "EMPTY" if ranking_project_count > 0 else "INVALID"
        ),
        "errors": errors,
        "split_counts": dict(
            sorted(Counter(str(row["split"]) for row in project_rows).items())
        ),
        "shadow_only": True,
        "promotion_ready": False,
    }
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "summary": summary,
        "by_project": project_rows,
        "queue": queue_rows,
    }


def write_symbol_corpus_queue_artifacts(
    evaluation: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    by_project_path = output / BY_PROJECT_FILENAME
    queue_csv_path = output / QUEUE_FILENAME
    queue_json_path = output / QUEUE_JSON_FILENAME
    summary_path = output / SUMMARY_FILENAME

    project_rows = list(evaluation.get("by_project") or [])
    queue_rows = list(evaluation.get("queue") or [])
    summary = dict(evaluation.get("summary") or {})

    _write_csv(by_project_path, project_rows)
    # Flatten list fields for CSV.
    csv_queue_rows = []
    for row in queue_rows:
        item = dict(row)
        item["definition_names"] = item.get("definition_names_text") or "|".join(
            str(value) for value in (item.get("definition_names") or [])
        )
        item["project_ids"] = item.get("project_ids_text") or "|".join(
            str(value) for value in (item.get("project_ids") or [])
        )
        csv_queue_rows.append(item)
    _write_csv(queue_csv_path, csv_queue_rows)
    queue_json_path.write_text(
        json.dumps(
            {
                "schema_version": QUEUE_SCHEMA_VERSION,
                "summary": summary,
                "queue": queue_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "by_project": by_project_path,
        "queue_csv": queue_csv_path,
        "queue_json": queue_json_path,
        "summary": summary_path,
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = {}
            for key in fieldnames:
                value = row.get(key)
                if isinstance(value, (list, tuple, set)):
                    payload[key] = "|".join(str(item) for item in value)
                elif isinstance(value, bool):
                    payload[key] = "true" if value else "false"
                else:
                    payload[key] = value
            writer.writerow(payload)


__all__ = [
    "BY_PROJECT_FILENAME",
    "QUEUE_FILENAME",
    "QUEUE_JSON_FILENAME",
    "QUEUE_SCHEMA_VERSION",
    "SUMMARY_FILENAME",
    "SUMMARY_SCHEMA_VERSION",
    "evaluate_symbol_corpus_queue",
    "write_symbol_corpus_queue_artifacts",
]
