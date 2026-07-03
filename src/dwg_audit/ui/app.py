from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dwg_audit.report import load_report_frames


ISSUE_STATUS_OPTIONS = ("open", "ignored", "resolved", "false_positive")


def _jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _issue_sheet_no(row: pd.Series) -> str:
    evidence = _jsonish(row.get("evidence"))
    if isinstance(evidence, dict) and evidence.get("sheet_no") is not None:
        return str(evidence["sheet_no"])
    return str(row.get("sheet_id") or "")


def _issue_values_text(row: pd.Series) -> str:
    values = _jsonish(row.get("values"))
    if isinstance(values, list):
        return ",".join(str(item) for item in values)
    parts = [row.get("left_value"), row.get("right_value")]
    return ",".join(str(item) for item in parts if item)


def _filter_issues(
    issues: pd.DataFrame,
    *,
    severities: list[str] | None = None,
    rules: list[str] | None = None,
    statuses: list[str] | None = None,
    sheet_query: str = "",
    value_query: str = "",
) -> pd.DataFrame:
    if issues.empty:
        return issues

    filtered = issues.copy()
    if severities:
        filtered = filtered[filtered["severity"].astype(str).isin(severities)]
    if rules:
        filtered = filtered[filtered["rule_id"].astype(str).isin(rules)]
    if statuses:
        filtered = filtered[filtered["status"].astype(str).isin(statuses)]

    if sheet_query.strip():
        needle = sheet_query.strip().lower()
        filtered = filtered[filtered.apply(lambda row: needle in _issue_sheet_no(row).lower(), axis=1)]
    if value_query.strip():
        needle = value_query.strip().lower()
        filtered = filtered[filtered.apply(lambda row: needle in _issue_values_text(row).lower(), axis=1)]
    return filtered


def _sort_issues(issues: pd.DataFrame, sort_key: str) -> pd.DataFrame:
    if issues.empty:
        return issues
    ranked = issues.copy()
    if sort_key == "severity":
        order = {"critical": 0, "major": 1, "minor": 2, "review": 3}
        ranked["_sort"] = ranked["severity"].astype(str).map(order).fillna(99)
        return ranked.sort_values(by=["_sort", "confidence"], ascending=[True, False]).drop(columns=["_sort"])
    if sort_key == "confidence":
        return ranked.sort_values(by=["confidence"], ascending=[False])
    if sort_key == "sheet_no":
        ranked["_sheet_no"] = ranked.apply(_issue_sheet_no, axis=1)
        return ranked.sort_values(by=["_sheet_no", "confidence"], ascending=[True, False]).drop(columns=["_sheet_no"])
    return ranked


def _persist_issue_status(project_dir: Path, issue_id: str, status: str) -> None:
    audit_dir = project_dir / "audit"
    parquet_path = audit_dir / "issues.parquet"
    json_path = audit_dir / "issues.json"
    if not parquet_path.exists() or not json_path.exists():
        raise FileNotFoundError("Missing audit issue artifacts.")

    frame = pd.read_parquet(parquet_path)
    if "issue_id" not in frame.columns or issue_id not in set(frame["issue_id"].astype(str)):
        raise KeyError(f"Unknown issue_id: {issue_id}")
    frame.loc[frame["issue_id"].astype(str) == issue_id, "status"] = status
    frame.to_parquet(parquet_path, index=False)
    frame.to_json(json_path, orient="records", force_ascii=False, indent=2)


def _project_dirs(root: Path) -> list[Path]:
    return sorted([path for path in root.iterdir() if path.is_dir() and (path / "manifest.json").exists()])


def _summary_metrics(manifest: dict[str, Any], frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    pairs = frames.get("pairs", pd.DataFrame())
    issues = frames.get("issues", pd.DataFrame())
    return {
        "files": int(manifest.get("file_count", 0)),
        "valid_dwg": int(manifest.get("valid_dwg_files", 0)),
        "pairs": int(len(pairs)),
        "issues": int(len(issues)),
    }


def _issue_detail(issue_row: pd.Series) -> None:
    st.subheader(f"Issue {issue_row.get('issue_id')}")
    left, right = st.columns([1, 1])
    with left:
        st.write(
            {
                "rule_id": issue_row.get("rule_id"),
                "severity": issue_row.get("severity"),
                "status": issue_row.get("status"),
                "confidence": issue_row.get("confidence"),
                "sheet_no": _issue_sheet_no(issue_row),
                "values": _issue_values_text(issue_row),
            }
        )
    with right:
        st.write(
            {
                "title": issue_row.get("title"),
                "summary": issue_row.get("summary") or issue_row.get("message"),
                "explanation": issue_row.get("explanation"),
                "recommended_action": issue_row.get("recommended_action"),
            }
        )

    evidence = _jsonish(issue_row.get("evidence"))
    evidence_refs = _jsonish(issue_row.get("evidence_refs"))
    if evidence is not None:
        st.markdown("**Evidence**")
        st.json(evidence)
    if evidence_refs:
        st.markdown("**Evidence Refs**")
        st.json(evidence_refs)


def _pair_detail(pair_row: pd.Series) -> None:
    st.subheader(f"Pair {pair_row.get('pair_id')}")
    st.write(
        {
            "left_value": pair_row.get("left_value"),
            "right_value": pair_row.get("right_value"),
            "confidence": pair_row.get("confidence"),
            "status": pair_row.get("status"),
            "confidence_bucket": pair_row.get("confidence_bucket"),
            "line_group_id": pair_row.get("line_group_id"),
            "left_text_id": pair_row.get("left_text_id"),
            "right_text_id": pair_row.get("right_text_id"),
            "left_coord": [pair_row.get("left_coord_x"), pair_row.get("left_coord_y")],
            "right_coord": [pair_row.get("right_coord_x"), pair_row.get("right_coord_y")],
        }
    )
    evidence = _jsonish(pair_row.get("evidence"))
    if evidence is not None:
        st.markdown("**Pair Evidence**")
        st.json(evidence)


def main() -> None:
    st.set_page_config(page_title="DWG Audit", layout="wide")
    st.title("DWG Audit Viewer")

    with st.sidebar:
        artifacts_root = Path(st.text_input("Artifacts root", value="artifacts"))
        if not artifacts_root.exists():
            st.info("Provide an artifacts directory produced by `dwg-audit analyze-project`.")
            return
        project_dirs = _project_dirs(artifacts_root)
        if not project_dirs:
            st.warning("No project artifact directories found.")
            return
        selected = st.selectbox("Project", project_dirs, format_func=lambda path: path.name)

    manifest = json.loads((selected / "manifest.json").read_text(encoding="utf-8"))
    frames = load_report_frames(selected)
    metrics = _summary_metrics(manifest, frames)

    summary_tab, issues_tab, pairs_tab, files_tab, reports_tab = st.tabs(
        ["Summary", "Issues", "Pairs", "Files", "Reports"]
    )

    with summary_tab:
        metric_cols = st.columns(4)
        metric_cols[0].metric("Files", metrics["files"])
        metric_cols[1].metric("Valid DWG", metrics["valid_dwg"])
        metric_cols[2].metric("Pairs", metrics["pairs"])
        metric_cols[3].metric("Issues", metrics["issues"])
        st.json(
            {
                "project_name": manifest["project_name"],
                "input_root": manifest.get("input_root"),
                "warnings": manifest.get("warnings", []),
            }
        )

    with issues_tab:
        issues = frames.get("issues", pd.DataFrame())
        if issues.empty:
            st.info("No issues available yet. Run `dwg-audit run-audit` for this project.")
        else:
            filter_cols = st.columns(5)
            severity_options = sorted(issues["severity"].dropna().astype(str).unique().tolist()) if "severity" in issues.columns else []
            rule_options = sorted(issues["rule_id"].dropna().astype(str).unique().tolist()) if "rule_id" in issues.columns else []
            status_options = sorted(issues["status"].dropna().astype(str).unique().tolist()) if "status" in issues.columns else []
            severities = filter_cols[0].multiselect("Severity", severity_options)
            rules = filter_cols[1].multiselect("Rule", rule_options)
            statuses = filter_cols[2].multiselect("Status", status_options)
            sheet_query = filter_cols[3].text_input("Sheet No")
            value_query = filter_cols[4].text_input("Value")
            sort_key = st.selectbox("Sort By", ["severity", "confidence", "sheet_no"])

            filtered = _sort_issues(
                _filter_issues(
                    issues,
                    severities=severities,
                    rules=rules,
                    statuses=statuses,
                    sheet_query=sheet_query,
                    value_query=value_query,
                ),
                sort_key,
            )

            display_columns = [
                column
                for column in ("issue_id", "severity", "rule_id", "status", "confidence", "title", "left_value", "right_value")
                if column in filtered.columns
            ]
            st.dataframe(filtered[display_columns] if display_columns else filtered, use_container_width=True)

            issue_ids = filtered["issue_id"].astype(str).tolist()
            if issue_ids:
                selected_issue_id = st.selectbox("Issue Detail", issue_ids)
                issue_row = filtered[filtered["issue_id"].astype(str) == selected_issue_id].iloc[0]
                _issue_detail(issue_row)
                new_status = st.selectbox("Update Status", ISSUE_STATUS_OPTIONS, index=ISSUE_STATUS_OPTIONS.index(str(issue_row.get("status") or "open")))
                if st.button("Save Issue Status"):
                    _persist_issue_status(selected, selected_issue_id, new_status)
                    st.success(f"Saved {selected_issue_id} -> {new_status}. Reload the page to refresh tables.")

    with pairs_tab:
        pairs = frames.get("pairs", pd.DataFrame())
        if pairs.empty:
            st.info("No pairs available yet.")
        else:
            filter_cols = st.columns(3)
            pair_statuses = sorted(pairs["status"].dropna().astype(str).unique().tolist()) if "status" in pairs.columns else []
            confidence_buckets = sorted(pairs["confidence_bucket"].dropna().astype(str).unique().tolist()) if "confidence_bucket" in pairs.columns else []
            selected_statuses = filter_cols[0].multiselect("Pair Status", pair_statuses)
            selected_buckets = filter_cols[1].multiselect("Confidence Bucket", confidence_buckets)
            value_query = filter_cols[2].text_input("Pair Value Search")
            filtered = pairs.copy()
            if selected_statuses:
                filtered = filtered[filtered["status"].astype(str).isin(selected_statuses)]
            if selected_buckets and "confidence_bucket" in filtered.columns:
                filtered = filtered[filtered["confidence_bucket"].astype(str).isin(selected_buckets)]
            if value_query.strip():
                needle = value_query.strip().lower()
                filtered = filtered[
                    filtered.apply(
                        lambda row: needle in f"{row.get('left_value', '')},{row.get('right_value', '')}".lower(),
                        axis=1,
                    )
                ]
            filtered = filtered.sort_values(by=["confidence"], ascending=[False]) if "confidence" in filtered.columns else filtered
            display_columns = [
                column
                for column in (
                    "pair_id",
                    "left_value",
                    "right_value",
                    "confidence",
                    "status",
                    "confidence_bucket",
                    "line_group_id",
                )
                if column in filtered.columns
            ]
            st.dataframe(filtered[display_columns] if display_columns else filtered, use_container_width=True)
            pair_ids = filtered["pair_id"].astype(str).tolist() if "pair_id" in filtered.columns else []
            if pair_ids:
                selected_pair_id = st.selectbox("Pair Detail", pair_ids)
                pair_row = filtered[filtered["pair_id"].astype(str) == selected_pair_id].iloc[0]
                _pair_detail(pair_row)

    with files_tab:
        st.dataframe(pd.DataFrame(manifest["source_files"]), use_container_width=True)

    with reports_tab:
        audit_dir = selected / "audit"
        for filename in ("audit_report.md", "audit_report.html", "issues.json", "issues.xlsx"):
            path = audit_dir / filename
            if not path.exists():
                continue
            mime = {
                ".md": "text/markdown",
                ".html": "text/html",
                ".json": "application/json",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }.get(path.suffix.lower(), "application/octet-stream")
            st.download_button(
                label=f"Download {filename}",
                data=path.read_bytes(),
                file_name=filename,
                mime=mime,
            )


if __name__ == "__main__":
    main()
