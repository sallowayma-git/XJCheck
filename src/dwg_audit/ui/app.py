from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from dwg_audit.report import load_report_frames


def main() -> None:
    st.set_page_config(page_title="DWG Audit", layout="wide")
    st.title("DWG Audit Viewer")
    artifacts_root = Path(st.text_input("Artifacts root", value="artifacts"))
    if not artifacts_root.exists():
        st.info("Provide an artifacts directory produced by `dwg-audit analyze-project`.")
        return

    project_dirs = [path for path in artifacts_root.iterdir() if path.is_dir()]
    if not project_dirs:
        st.warning("No project artifact directories found.")
        return

    selected = st.selectbox("Project", project_dirs, format_func=lambda path: path.name)
    manifest = json.loads((selected / "manifest.json").read_text(encoding="utf-8"))
    frames = load_report_frames(selected)

    summary_tab, issues_tab, pairs_tab, files_tab = st.tabs(["Summary", "Issues", "Pairs", "Files"])
    with summary_tab:
        st.json(
            {
                "project_name": manifest["project_name"],
                "file_count": manifest["file_count"],
                "valid_dwg_files": manifest["valid_dwg_files"],
                "invalid_dwg_files": manifest["invalid_dwg_files"],
                "warnings": manifest["warnings"],
            }
        )
    with issues_tab:
        st.dataframe(frames["issues"] if not frames["issues"].empty else pd.DataFrame(columns=["message"]))
    with pairs_tab:
        st.dataframe(frames["pairs"] if not frames["pairs"].empty else pd.DataFrame(columns=["left_value", "right_value", "confidence"]))
    with files_tab:
        st.dataframe(pd.DataFrame(manifest["source_files"]))
