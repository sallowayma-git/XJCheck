from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[6]
AUDIT = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule"
GAP_AUDIT = ROOT / ".planning/superworks-adapter/loop/GAP-TRIAGE/audits/current-wire-shapes-2026-10-16"
REVIEW = AUDIT / "sample_frame_review.csv"
SAMPLE = GAP_AUDIT / "sample_judgments.csv"
SAMPLE_SUMMARY = GAP_AUDIT / "sample_summary.json"
CORRECTIONS = GAP_AUDIT / "judgment_corrections.csv"
SHAPE_SAMPLE = AUDIT / "frame_shape_samples_60.csv"
OUT = AUDIT / "manual_review_estimates.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--sample", type=Path, default=SAMPLE)
    parser.add_argument("--summary", type=Path, default=SAMPLE_SUMMARY)
    parser.add_argument("--corrections", type=Path, default=CORRECTIONS)
    parser.add_argument("--shape-sample", type=Path, default=SHAPE_SAMPLE)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    review = pd.read_csv(args.review, dtype=str).fillna("")
    sample = pd.read_csv(args.sample, dtype=str).fillna("")
    sample["_key"] = list(zip(sample.project, sample.issue_id))
    sample_index = {key: index for index, key in sample["_key"].items()}
    review_keys = set(zip(review.project_id, review.issue_id))
    if len(review) != 78 or len(review_keys) != 78 or not review_keys <= sample_index.keys():
        raise SystemExit("Expected 78 unique reviewed issue keys present in the 240-case sample")

    corrections = pd.read_csv(args.corrections, dtype=str).fillna("")
    new_corrections = []
    for row in review.to_dict(orient="records"):
        key = (row["project_id"], row["issue_id"])
        index = sample_index[key]
        before, after = row["manual_review_before_wide"], row["manual_review_need"]
        sample.loc[index, "manual_review_need"] = after
        sample.loc[index, "reason"] = row["wide_frame_reason"]
        sample.loc[index, "reviewer"] = row["wide_frame_reviewer"]
        if before != after:
            new_corrections.append({
                "group": row["group"], "sample_no": row["sample_no"], "issue_id": row["issue_id"],
                "project": row["project_id"], "original_verdict": before, "corrected_verdict": after,
                "reason": row["wide_frame_reason"], "reviewer": row["wide_frame_reviewer"],
            })

    # The focused 60-case review also records the terminal-frame interpretation for both requested classes.
    shape = pd.read_csv(args.shape_sample, dtype=str).fillna("")
    if len(shape) != 60 or shape.groupby("group").size().to_dict() != {"E_port_both_ends": 30, "E_rail_T": 30}:
        raise SystemExit("Expected 30 independently reviewed screenshots per focused class")
    for row in shape.to_dict(orient="records"):
        key = (row["project_id"], row["issue_id"])
        index = sample_index.get(key)
        if index is None:
            raise SystemExit(f"Focused screenshot case not present in the stratified sample: {key}")
        sample.loc[index, "manual_review_need"] = row["manual_review_need"]
        if row["group"] == "E_port_both_ends" and row["issue_id"] == "ISWcaef9bdbcab72db473a1":
            sample.loc[index, "reason"] = row["reason"]
            sample.loc[index, "reviewer"] = "independent raw-DXF re-review batch B"
            # Keep the earlier 4x classification in the correction ledger, then add its reversal below.
            already = corrections.issue_id.eq(row["issue_id"]).any()
            if already and not any(entry["issue_id"] == row["issue_id"] for entry in new_corrections):
                new_corrections.append({
                    "group": row["group"], "sample_no": row["sample_no"], "issue_id": row["issue_id"],
                    "project": row["project_id"], "original_verdict": "no", "corrected_verdict": "yes",
                    "reason": row["reason"], "reviewer": "independent raw-DXF re-review batch B",
                })

    # Add only audit corrections not already represented by the same reviewer/outcome pair.
    existing_keys = set(zip(corrections.issue_id, corrections.corrected_verdict, corrections.reviewer))
    additions = [row for row in new_corrections
                 if (row["issue_id"], row["corrected_verdict"], row["reviewer"]) not in existing_keys]
    if additions:
        corrections = pd.concat([corrections, pd.DataFrame(additions)], ignore_index=True)

    sample.drop(columns="_key", inplace=True)
    sample.to_csv(args.sample, index=False, encoding="utf-8-sig")
    corrections.to_csv(args.corrections, index=False, encoding="utf-8-sig")

    old_summary = json.loads(args.summary.read_text(encoding="utf-8"))
    populations = {group: item["population_n"] for group, item in old_summary["classes"].items()}
    classes = {}
    total_population = sum(populations.values())
    lower_total = upper_total = 0.0
    lower_variance = upper_variance = 0.0
    for group, population in populations.items():
        rows = sample.loc[sample.group.eq(group), "manual_review_need"].astype(str).str.casefold()
        yes = int(rows.eq("yes").sum())
        no = int(rows.eq("no").sum())
        uncertain = int(rows.eq("uncertain").sum())
        n = len(rows)
        if n != 30 or yes + no + uncertain != n:
            raise SystemExit(f"Invalid class labels for {group}: n={n}, yes={yes}, no={no}, uncertain={uncertain}")
        lower_y, upper_y = yes, yes + uncertain
        item = {
            "population_n": population, "sample_n": n, "manual_yes_n": yes, "manual_no_n": no,
            "uncertain_n": uncertain, "observed_manual_need_lower": yes / n,
            "observed_manual_need_upper": (yes + uncertain) / n,
            "estimated_manual_need_lower_n": population * yes / n,
            "estimated_manual_need_upper_n": population * (yes + uncertain) / n,
        }
        classes[group] = item
        lower_total += item["estimated_manual_need_lower_n"]
        upper_total += item["estimated_manual_need_upper_n"]
        for y, target in ((lower_y, "lower"), (upper_y, "upper")):
            p = y / n
            s2 = n / (n - 1) * p * (1.0 - p)
            variance = population * population * (1.0 - n / population) * s2 / n
            if target == "lower":
                lower_variance += variance
            else:
                upper_variance += variance

    lower_rate, upper_rate = lower_total / total_population, upper_total / total_population
    lower_margin = 1.96 * math.sqrt(lower_variance) / total_population
    upper_margin = 1.96 * math.sqrt(upper_variance) / total_population
    shape_classes = {}
    for group, data in shape.groupby("group"):
        frame_yes = int(data.frame_stop.eq("yes").sum())
        manual_yes = int(data.manual_review_need.eq("yes").sum())
        manual_no = int(data.manual_review_need.eq("no").sum())
        uncertain = int(data.manual_review_need.eq("uncertain").sum())
        shape_classes[group] = {
            "sample_n": len(data), "frame_stop_n": frame_yes,
            "frame_stop_manual_no_n": int(((data.frame_stop == "yes") & (data.manual_review_need == "no")).sum()),
            "manual_yes_n": manual_yes, "manual_no_n": manual_no, "uncertain_n": uncertain,
        }

    result = {
        "generated": "2026-10-16",
        "scope": "Eight E subclasses; 30 independently selected screenshot cases per class. The 78 expanded frame-candidate reviews update labels in the original stratified sample.",
        "sample_n": len(sample), "unique_project_issue_keys": int(sample[["project", "issue_id"]].drop_duplicates().shape[0]),
        "expanded_frame_candidate_reviews": len(review), "expanded_review_frame_stops": int(review.wide_frame_judgment.eq("yes").sum()),
        "expanded_review_non_stops": int(review.wide_frame_judgment.eq("no").sum()),
        "expanded_review_uncertain": int(review.wide_frame_judgment.eq("uncertain").sum()),
        "focused_wide_frame_recheck": {"sample_n": len(shape), "classes": shape_classes,
                                       "screenshot_hashes_recorded": int(shape.sha256.str.len().eq(64).sum())},
        "classes": classes,
        "population_weighted_manual_need": {
            "population_n": total_population, "manual_need_lower_n": lower_total,
            "manual_need_upper_n": upper_total, "manual_need_lower_rate": lower_rate,
            "manual_need_upper_rate": upper_rate,
            "lower_95_ci": [lower_rate - lower_margin, lower_rate + lower_margin],
            "upper_95_ci": [upper_rate - upper_margin, upper_rate + upper_margin],
            "method": "Population-weighted within eight E subclasses; stratified SRSWOR variance with finite population correction. Uncertain labels are excluded from the lower estimate and included in the upper estimate.",
        },
        "manual_label_corrections_added": len(additions),
        "review_evidence": "sample_frame_review.csv and frame_shape_samples_60.csv; every expanded sample row has a screenshot reference and SHA-256.",
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    old_summary.update({
        "classes": classes,
        "e_weighted_manual_need": {
            "manual_yes_estimate_n": lower_total,
            "manual_no_estimate_n": total_population - lower_total - (upper_total - lower_total),
            "uncertain_estimate_n": upper_total - lower_total,
            "manual_need_lower_n": lower_total, "manual_need_upper_n": upper_total,
            "manual_need_lower_rate": lower_rate, "manual_need_upper_rate": upper_rate,
            "lower_95_ci": result["population_weighted_manual_need"]["lower_95_ci"],
            "upper_95_ci": result["population_weighted_manual_need"]["upper_95_ci"],
            "method": result["population_weighted_manual_need"]["method"],
        },
        "wide_frame_recheck": {
            "date": "2026-10-16", "sample_n": len(shape), "window_scale": "4x",
            "classes": shape_classes,
            "changed_verdicts_after_raw_DXF_recheck": int((shape.manual_review_before_wide != shape.manual_review_need).sum()),
            "frame_boundary_rule": "A lead is a frame stop only when the frame edge contact is at a segment endpoint; lines crossing the frame to another terminal remain open. The frame must be a unique closed/dashed captioned equipment rectangle, the inside terminal's exact SuperWORKS label must appear in the caption, and no explicit SW connect-dot XDATA may mark the contact.",
            "p027_correction": "ISWcaef9bdbcab72db473a1 crosses the From BCU frame boundary and continues to the outside 3-4QD11 terminal; reverted from no-manual to manual=yes.",
            "screenshots": "Frame-rule audit records include per-case relative paths and SHA-256 hashes.",
        },
        "judgment_corrections": len(corrections),
    })
    args.summary.write_text(json.dumps(old_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "sample_n": len(sample), "manual_need_lower_n": lower_total, "manual_need_upper_n": upper_total,
        "manual_need_lower_rate": lower_rate, "manual_need_upper_rate": upper_rate,
        "lower_95_ci": result["population_weighted_manual_need"]["lower_95_ci"],
        "upper_95_ci": result["population_weighted_manual_need"]["upper_95_ci"],
        "classes": classes, "focused_wide_frame_recheck": shape_classes,
        "manual_label_corrections_added": len(additions),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
