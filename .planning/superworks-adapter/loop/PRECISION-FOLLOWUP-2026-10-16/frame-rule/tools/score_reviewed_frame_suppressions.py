from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / ".tmp/precision_loop_20261016/frame_rule_final4_full77"
REVIEW = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/sample_frame_review.csv"
OUT = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/review_score_final4.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=RUN)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    run_path, review_path, out_path = args.run.resolve(), args.review.resolve(), args.out.resolve()
    run = json.loads((run_path / "run.json").read_text(encoding="utf-8"))
    if run.get("state") != "COMPLETE" or len(run.get("projects", [])) != 77:
        raise SystemExit("The complete 77-project replay is required")
    suppressed = set()
    for project in run["projects"]:
        project_dir = Path(project["project_dir"])
        path = project_dir / "audit/sw_recognition_diagnostics.parquet"
        if not path.is_file():
            continue
        diagnostics = pd.read_parquet(path, columns=["record_id", "suppressed_by"])
        rows = diagnostics.loc[diagnostics.suppressed_by.eq("terminal_frame_boundary"), "record_id"].dropna()
        suppressed.update((project["project_id"], str(record_id)) for record_id in rows)

    review = pd.read_csv(review_path, dtype=str).fillna("")
    review["_key"] = list(zip(review.project_id, review.record_id))
    review["strict_rule_suppressed"] = review._key.isin(suppressed)
    review["strict_rule_result"] = review.strict_rule_suppressed.map({True: "closed", False: "not closed"})
    false_suppressions = review.loc[
        review.strict_rule_suppressed & ~review.wide_frame_judgment.eq("yes"),
        ["project_id", "record_id", "wide_frame_judgment", "wide_frame_reason", "screenshot", "sha256"],
    ]
    result = {
        "run": str(run_path.relative_to(ROOT)), "reviewed_candidate_n": len(review),
        "actual_rule_closures_in_review": int(review.strict_rule_suppressed.sum()),
        "true_frame_stops_among_reviewed_candidates": int(review.wide_frame_judgment.eq("yes").sum()),
        "false_suppressions": false_suppressions.to_dict(orient="records"),
        "rule_closure_rows": review.loc[review.strict_rule_suppressed,
                                         ["project_id", "record_id", "wide_frame_judgment", "manual_review_need", "screenshot", "sha256"]].to_dict(orient="records"),
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rule_closure_rows"}, ensure_ascii=False, indent=2))
    if len(false_suppressions):
        raise SystemExit("The strict rule suppressed one or more reviewed non-frame/uncertain cases")


if __name__ == "__main__":
    main()
