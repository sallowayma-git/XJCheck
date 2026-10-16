from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[6]
DEFAULT_SAMPLE = ROOT / ".planning/superworks-adapter/loop/GAP-TRIAGE/audits/current-wire-shapes-2026-10-16/sample_judgments.csv"
DEFAULT_REMOVED = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/removed_issues.csv"
DEFAULT_SCREENSHOTS = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/sample_frame_screenshots.csv"
DEFAULT_OUT = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/sample_frame_review.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--removed", type=Path, default=DEFAULT_REMOVED)
    parser.add_argument("--screenshots", type=Path, default=DEFAULT_SCREENSHOTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    sampled = pd.read_csv(args.sample, dtype=str).fillna("").rename(columns={"project": "project_id"})
    sampled = sampled[["project_id", "issue_id", "group", "sample_no", "manual_review_need",
                       "reason", "screenshot_path", "reviewer"]]
    removed = pd.read_csv(args.removed, dtype=str).fillna("")
    screenshots = pd.read_csv(args.screenshots, dtype=str).fillna("")
    screenshots = screenshots[["project_id", "record_id", "coords", "frame_rect", "frame_contact",
                               "frame_label", "screenshot", "sha256"]]
    joined = removed.merge(sampled, on=["project_id", "issue_id"], how="inner", validate="one_to_one")
    joined = joined.merge(screenshots, on=["project_id", "record_id"], how="left", validate="one_to_one",
                          suffixes=("_old", "_wide"))
    if len(joined) != 78 or joined.screenshot.isna().any() or (joined.screenshot == "").any():
        missing = joined.loc[joined.screenshot.eq(""), ["project_id", "issue_id", "record_id"]]
        raise SystemExit(f"Expected 78 matched and rendered sample rows; got {len(joined)}. Missing:\n{missing}")

    fields = [
        "group", "sample_no", "issue_id", "project_id", "file_id", "sheet_id", "line_group_id", "record_id",
        "manual_review_need", "reason", "screenshot_path", "reviewer", "coords", "frame_rect", "frame_contact",
        "frame_label", "screenshot", "sha256",
    ]
    out = joined.loc[:, fields].copy()
    out.insert(out.columns.get_loc("screenshot"), "wide_frame_judgment", "")
    out.insert(out.columns.get_loc("screenshot"), "wide_frame_reason", "")
    out.insert(out.columns.get_loc("screenshot"), "wide_frame_reviewer", "")
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"rows={len(out)}; screenshot_refs={out.screenshot.notna().sum()}; output={args.out}")


if __name__ == "__main__":
    main()
