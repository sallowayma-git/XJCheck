from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dwg_audit.report import load_report_frames
from dwg_audit.ui.actions import discover_project_outputs
from dwg_audit.ui.actions import run_ui_analysis
from dwg_audit.utils.config import load_config


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


def _issue_one_to_many_classification(row: pd.Series) -> str:
    evidence = _jsonish(row.get("evidence"))
    if isinstance(evidence, dict) and evidence.get("one_to_many_classification") is not None:
        return str(evidence["one_to_many_classification"])
    return ""


def _pair_evidence_mapping(value: Any) -> dict[str, Any]:
    payload = _jsonish(value)
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("pair_evidence")
    if isinstance(nested, dict):
        return nested
    return payload


def _line_semantics_dict(value: Any) -> dict[str, str]:
    payload = _pair_evidence_mapping(value)
    semantics: dict[str, str] = {}
    for source_key, target_key in (
        ("line_orientation", "line_orientation"),
        ("left_side_label", "left_side_label"),
        ("right_side_label", "right_side_label"),
    ):
        raw = payload.get(source_key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            semantics[target_key] = text
    return semantics


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


def _default_project_index(project_dirs: list[Path]) -> int:
    preferred = st.session_state.get("selected_project_name")
    if not preferred:
        return 0
    for index, project_dir in enumerate(project_dirs):
        if project_dir.name == preferred:
            return index
    return 0


def _summary_metrics(manifest: dict[str, Any], frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    pairs = frames.get("pairs", pd.DataFrame())
    issues = frames.get("issues", pd.DataFrame())
    return {
        "files": int(manifest.get("file_count", 0)),
        "valid_dwg": int(manifest.get("valid_dwg_files", 0)),
        "pairs": int(len(pairs)),
        "issues": int(len(issues)),
    }


def _load_findings_payload(project_dir: Path) -> dict[str, Any]:
    findings_path = project_dir / "findings" / "findings.json"
    if not findings_path.exists():
        return {}
    return json.loads(findings_path.read_text(encoding="utf-8"))


def _one_to_many_cluster_rows(findings_payload: dict[str, Any]) -> pd.DataFrame:
    table = findings_payload.get("one_to_many_review_table")
    if not isinstance(table, dict):
        return pd.DataFrame()
    clusters = table.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        return pd.DataFrame()

    rows = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        rows.append(
            {
                "left_value": cluster.get("left_value"),
                "classification": cluster.get("classification"),
                "classification_reason": cluster.get("classification_reason"),
                "right_values": ",".join(str(item) for item in cluster.get("right_values", []) if item is not None),
                "sheet_nos": ",".join(str(item) for item in cluster.get("sheet_nos", []) if item is not None),
                "high_confidence_pairs": (
                    f"{cluster.get('high_confidence_pair_count', 0)}/{cluster.get('pair_count', 0)}"
                ),
                "reciprocal_pairs": f"{cluster.get('reciprocal_pair_count', 0)}/{cluster.get('pair_count', 0)}",
            }
        )
    return pd.DataFrame(rows)


def _issue_detail(issue_row: pd.Series) -> None:
    st.subheader(f"Issue {issue_row.get('issue_id')}")
    semantics = _line_semantics_dict(issue_row.get("evidence"))
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
                "one_to_many_classification": _issue_one_to_many_classification(issue_row),
                **semantics,
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
    semantics = _line_semantics_dict(pair_row.get("evidence"))
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
            **semantics,
        }
    )
    evidence = _jsonish(pair_row.get("evidence"))
    if evidence is not None:
        st.markdown("**Pair Evidence**")
        st.json(evidence)


def _render_analyze_tab(artifacts_root: Path) -> Path:
    st.subheader("Project Import")
    st.caption("Select an input project directory, choose an output artifacts root, and optionally rerun audit immediately after analysis.")

    with st.form("analyze_project_form"):
        input_root_text = st.text_input("Input Project Directory", value=st.session_state.get("ui_input_root", ""))
        output_root_text = st.text_input("Output Artifacts Root", value=st.session_state.get("ui_output_root", str(artifacts_root)))
        config_path_text = st.text_input("Config Path", value=st.session_state.get("ui_config_path", ""))
        include_audit = st.checkbox("Run Audit After Analyze", value=st.session_state.get("ui_include_audit", True))
        submitted = st.form_submit_button("Analyze Project")

    with st.expander("Resolved Config Preview", expanded=False):
        try:
            config_preview = load_config(Path(config_path_text).expanduser() if config_path_text.strip() else None)
            st.json(config_preview)
        except Exception as exc:
            st.warning(str(exc))

    if submitted:
        st.session_state["ui_input_root"] = input_root_text
        st.session_state["ui_output_root"] = output_root_text
        st.session_state["ui_config_path"] = config_path_text
        st.session_state["ui_include_audit"] = include_audit

        if not input_root_text.strip():
            st.error("Input Project Directory is required.")
            return artifacts_root

        try:
            result = run_ui_analysis(
                Path(input_root_text),
                Path(output_root_text),
                Path(config_path_text) if config_path_text.strip() else None,
                include_audit=include_audit,
            )
        except Exception as exc:
            st.error(str(exc))
            return artifacts_root

        project_count = len(result.project_dirs)
        audit_count = len(result.audit_dirs)
        st.session_state["artifacts_root"] = str(result.output_root)
        if result.project_dirs:
            st.session_state["selected_project_name"] = result.project_dirs[0].name
        st.success(
            f"Analysis completed. Projects={project_count}, audit_runs={audit_count}, output={result.output_root}"
        )
        if result.run_summary_path is not None:
            st.caption(f"Run summary: {result.run_summary_path}")
        return result.output_root

    return artifacts_root


def main() -> None:
    st.set_page_config(page_title="DWG Audit", layout="wide")
    st.title("DWG Audit Viewer")

    artifacts_root = Path(st.text_input("Artifacts Root", value=st.session_state.get("artifacts_root", "artifacts")))
    analyze_tab, summary_tab, issues_tab, pairs_tab, files_tab, reports_tab = st.tabs(
        ["Analyze", "Summary", "Issues", "Pairs", "Files", "Reports"]
    )

    with analyze_tab:
        artifacts_root = _render_analyze_tab(artifacts_root)

    project_dirs = discover_project_outputs(artifacts_root)
    selected: Path | None = None
    if project_dirs:
        selected = st.selectbox(
            "Project",
            project_dirs,
            index=_default_project_index(project_dirs),
            format_func=lambda path: path.name,
        )
        st.session_state["selected_project_name"] = selected.name

    manifest: dict[str, Any] = {}
    frames: dict[str, pd.DataFrame] = {}
    findings_payload: dict[str, Any] = {}
    metrics = {"files": 0, "valid_dwg": 0, "pairs": 0, "issues": 0}
    if selected is not None:
        manifest = json.loads((selected / "manifest.json").read_text(encoding="utf-8"))
        frames = load_report_frames(selected)
        findings_payload = _load_findings_payload(selected)
        metrics = _summary_metrics(manifest, frames)

    with summary_tab:
        if selected is None:
            st.info("No project artifacts found yet. Use the Analyze tab to import and process a project directory.")
        else:
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
            one_to_many_rows = _one_to_many_cluster_rows(findings_payload)
            if not one_to_many_rows.empty:
                review_table = findings_payload.get("one_to_many_review_table", {})
                st.markdown("### One-to-Many Review Table")
                st.write(
                    {
                        "cluster_count": review_table.get("cluster_count", 0),
                        "branch_cluster_count": review_table.get("branch_cluster_count", 0),
                        "review_cluster_count": review_table.get("review_cluster_count", 0),
                        "conflict_cluster_count": review_table.get("conflict_cluster_count", 0),
                    }
                )
                st.dataframe(one_to_many_rows, use_container_width=True)

    with issues_tab:
        if selected is None:
            st.info("No project selected.")
        else:
            issues = frames.get("issues", pd.DataFrame())
            if issues.empty:
                st.info("No issues available yet. Analyze with audit enabled or run `dwg-audit run-audit` for this project.")
            else:
                issues = issues.copy()
                issues["one_to_many_classification"] = issues.apply(_issue_one_to_many_classification, axis=1)
                issues["line_orientation"] = issues["evidence"].apply(
                    lambda value: _line_semantics_dict(value).get("line_orientation", "")
                )
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
                    for column in (
                        "issue_id",
                        "severity",
                        "rule_id",
                        "one_to_many_classification",
                        "status",
                        "confidence",
                        "line_orientation",
                        "title",
                        "left_value",
                        "right_value",
                    )
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
        if selected is None:
            st.info("No project selected.")
        else:
            pairs = frames.get("pairs", pd.DataFrame())
            if pairs.empty:
                st.info("No pairs available yet.")
            else:
                pairs = pairs.copy()
                pairs["line_orientation"] = pairs["evidence"].apply(
                    lambda value: _line_semantics_dict(value).get("line_orientation", "")
                )
                pairs["left_side_label"] = pairs["evidence"].apply(
                    lambda value: _line_semantics_dict(value).get("left_side_label", "")
                )
                pairs["right_side_label"] = pairs["evidence"].apply(
                    lambda value: _line_semantics_dict(value).get("right_side_label", "")
                )
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
                        "line_orientation",
                        "left_side_label",
                        "right_side_label",
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
        if selected is None:
            st.info("No project selected.")
        else:
            st.dataframe(pd.DataFrame(manifest["source_files"]), use_container_width=True)

    with reports_tab:
        if selected is None:
            st.info("No project selected.")
        else:
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
