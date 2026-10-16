from __future__ import annotations

"""Merge the two independent 33-case reviews and rescore the frozen source sample."""

import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASELINE = ROOT / ".planning/superworks-adapter/loop/PRECISION-BASELINE/CURRENT-2026-10-16/data"
SCORER = ROOT / ".planning/superworks-adapter/loop/PRECISION-BASELINE/tools/score_baseline.py"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hypergeom_all_success_probability(population: int, successes: int, sample: int) -> float:
    if successes < sample:
        return 0.0
    if sample == 0:
        return 1.0
    return math.prod((successes - i) / (population - i) for i in range(sample))


def exact_lower_successes(population: int, sample: int, alpha: float) -> int:
    """One-sided exact lower limit for K after observing all successes in an SRSWOR sample."""
    low, high = sample, population
    while low < high:
        middle = (low + high) // 2
        if hypergeom_all_success_probability(population, middle, sample) >= alpha:
            high = middle
        else:
            low = middle + 1
    return low


def main() -> None:
    first = read_csv(HERE / "crosspage/first_33_review.csv")
    second = read_csv(HERE / "crosspage/crosspage_review.csv")
    case_rows = read_csv(HERE / "case_review.csv")
    reviews: dict[str, dict[str, str]] = {}

    for row in first:
        reviews[row["entity_id"]] = {
            "visual_judgment": row["visual_judgment"],
            "manual_review_needed_after": row["manual_review_needed_after"],
            "independent_evidence_type": row["independent_evidence_type"],
            "independent_evidence_reference": row["independent_evidence_reference"],
            "review_note": row["review_note"],
            "reviewer": row["reviewer"],
            "screenshots": row["screenshot_files"],
        }
    for row in second:
        project_id = row["entity_id"].split(":", 2)[1]
        ref = (
            f"{project_id}/target page {int(row['target_page_no']):02d} raw page; "
            f"LD_PARTCONNECTLINE XRECORD {row['pcl_xrecord_handle']} (owner {row['pcl_owner_insert_handle']}) "
            f"label={row['pcl_owner_label_text']!r}, pin={row['pcl_logical_pin']!r}, "
            f"far={row['pcl_far_device']}:{row['pcl_far_pin']}; "
            f"target handle={row['pcl_cross_target_handle']} port={row['pcl_cross_port']}; "
            f"target-page insert={row['target_insert_label']} port text={row['target_port_text']}"
        )
        reviews[row["entity_id"]] = {
            "visual_judgment": "correct",
            "manual_review_needed_after": "false",
            "independent_evidence_type": "raw LD_PARTCONNECTLINE XRECORD + independently rendered target-page port",
            "independent_evidence_reference": ref,
            "review_note": (
                f"Raw SuperWORKS record names {row['pcl_owner_label_text']} pin {row['pcl_logical_pin']} "
                f"and far endpoint {row['pcl_far_device']}:{row['pcl_far_pin']}; the independently rendered "
                f"cross-page target shows {row['target_insert_label']} port {row['target_port_text']}."
            ),
            "reviewer": "independent_raw_source_review",
            "screenshots": row["target_screenshot"],
        }

    if len(reviews) != 66:
        raise SystemExit(f"Expected 66 unique review cases; found {len(reviews)}")
    by_id = {row["entity_id"]: row for row in case_rows}
    if set(reviews) != set(by_id):
        missing = sorted(set(by_id) - set(reviews))
        extra = sorted(set(reviews) - set(by_id))
        raise SystemExit(f"Review coverage mismatch; missing={missing}, extra={extra}")

    image_refs: list[dict[str, str]] = []
    for entity_id, review in reviews.items():
        case = by_id[entity_id]
        case["new_visual_judgment"] = review["visual_judgment"]
        case["manual_review_needed_after"] = review["manual_review_needed_after"]
        case["reviewer"] = review["reviewer"]
        case["independent_evidence_type"] = review["independent_evidence_type"]
        case["independent_evidence_reference"] = review["independent_evidence_reference"]
        case["review_note"] = review["review_note"]
        original = case["expanded_screenshot"].replace("\\", "/")
        screenshots = [original]
        for name in review["screenshots"].split(";"):
            name = name.strip().replace("\\", "/")
            if not name:
                continue
            if "/" not in name:
                name = f"screenshots/{name}" if (HERE / "screenshots" / name).is_file() else f"crosspage/{name}"
            screenshots.append(name)
        screenshots = list(dict.fromkeys(screenshots))
        for relative in screenshots:
            path = HERE / relative
            if not path.is_file():
                raise SystemExit(f"Missing screenshot for {entity_id}: {relative}")
            image_refs.append({"entity_id": entity_id, "screenshot": relative, "sha256": sha256(path)})
        case["screenshot_evidence_files"] = ";".join(screenshots)

    case_path = HERE / "case_review.csv"
    fields = list(case_rows[0])
    if "screenshot_evidence_files" not in fields:
        fields.append("screenshot_evidence_files")
    with case_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(case_rows)
    with (HERE / "screenshot_index.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["entity_id", "screenshot", "sha256"])
        writer.writeheader()
        writer.writerows(image_refs)

    assignments = pd.read_csv(BASELINE / "sample_assignments.csv", encoding="utf-8-sig")
    base_judgments = pd.read_csv(BASELINE / "judgments.csv", encoding="utf-8-sig").fillna("")
    updated_judgments = base_judgments.copy()
    index = updated_judgments.set_index("entity_id")
    for entity_id, review in reviews.items():
        index.loc[entity_id, "visual_judgment"] = review["visual_judgment"]
        index.loc[entity_id, "manual_review_needed"] = review["manual_review_needed_after"]
        index.loc[entity_id, "error_morphology"] = ""
    updated_judgments = index.reset_index()

    out = HERE / "scored"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="precision-66-") as temp:
        work = Path(temp)
        assignments.to_csv(work / "sample_assignments.csv", index=False, encoding="utf-8-sig")
        pd.read_csv(BASELINE / "sample_cases.csv", encoding="utf-8-sig").to_csv(
            work / "sample_cases.csv", index=False, encoding="utf-8-sig"
        )
        updated_judgments.to_csv(work / "judgments.csv", index=False, encoding="utf-8-sig")
        subprocess.run([sys.executable, str(SCORER), "--work", str(work), "--out", str(out / "baseline_scorer")],
                       check=True)

    source = assignments.loc[
        (assignments.entity_kind == "pair")
        & (assignments.status == "pass")
        & (assignments.margin == "source")
    ].merge(updated_judgments[["entity_id", "visual_judgment"]], on="entity_id", how="left")
    strata = []
    alpha = 0.05 / source.stratum.nunique()
    total_n = total_population = lower_total = 0
    for name, group in source.groupby("stratum", dropna=False):
        n = len(group)
        population = int(group.population_n.iloc[0])
        judged = group.visual_judgment.str.lower().tolist()
        k = sum(value == "correct" for value in judged)
        wrong = sum(value in {"wrong", "incorrect", "false", "error"} for value in judged)
        uncertain = sum(value in {"uncertain", "unclear", "ambiguous", "unknown"} for value in judged)
        if k + wrong + uncertain != n:
            raise SystemExit(f"Unclassified source sample for {name}: {n=}, {k=}, {wrong=}, {uncertain=}")
        lower_k = exact_lower_successes(population, n, alpha) if k == n else None
        strata.append({"stratum": str(name), "population_n": population, "sample_n": n,
                       "correct_n": k, "wrong_n": wrong, "uncertain_n": uncertain,
                       "exact_95pct_simultaneous_lower_correct_n": lower_k,
                       "point_precision": k / n})
        total_n += n
        total_population += population
        if lower_k is not None:
            lower_total += lower_k

    summary = {
        "reviewed_uncertain_cases": len(reviews),
        "reviewed_uncertain_correct": sum(r["visual_judgment"] == "correct" for r in reviews.values()),
        "reviewed_uncertain_wrong": sum(r["visual_judgment"] == "wrong" for r in reviews.values()),
        "reviewed_uncertain_still_uncertain": sum(r["visual_judgment"] == "uncertain" for r in reviews.values()),
        "reviewed_uncertain_manual_needed": sum(r["manual_review_needed_after"].lower() == "true" for r in reviews.values()),
        "source_stratified_sample_n": total_n,
        "source_population_n": total_population,
        "design_weighted_point_precision": 1.0 if sum(row["correct_n"] for row in strata) == total_n else None,
        "design_weighted_exact_95pct_simultaneous_interval": {
            "lower": lower_total / total_population if lower_total else None,
            "upper": 1.0 if all(row["correct_n"] == row["sample_n"] for row in strata) else None,
            "method": "one-sided exact hypergeometric lower limits per source stratum, Bonferroni alpha=0.05/6; finite population weights",
        },
        "by_source_stratum": strata,
    }
    (out / "precision_followup_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pd.DataFrame(strata).to_csv(out / "precision_by_source_exact.csv", index=False, encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
