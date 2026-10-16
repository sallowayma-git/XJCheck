"""Merge the blinded screenshot decisions for the P4 prefix audit."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(".tmp/precision_loop_20261015/P4-PREFIX-v2")
SAMPLE = EVIDENCE / "sample.json"
CSV_OUT = ROOT / "judgements.csv"
SAMPLE_OUT = ROOT / "audit_sample.json"
SUMMARY_OUT = ROOT / "audit_summary.json"

# Per-case visual review: the target numeric identity is visibly aligned with
# the normalized SW port on the same conductor. Whole-pair review is separate.
PAIR_MANUAL_YES = (
    set(range(1, 24)) | {25, 26, 27, 28, 29, 30, 31, 33, 34, 39}
    | {46, 47, 48, 49, 55, 56, 58, 59, 60}
    | {61, 62, 63, 64, 66, 74}
    | {85, 86, 87, 94, 95, 96, 97, 107, 109, 111, 112}
)

SOURCE_ASSOCIATION_UNCLEAR = {39, 60, 63, 96, 111}


def wilson_95(successes: int, trials: int) -> list[float] | None:
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    den = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / den
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / den
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def pair_reason(row: dict[str, str], case_no: int) -> str:
    if case_no not in PAIR_MANUAL_YES:
        return "截图可见完整配对两端及相应导线关系。"
    if case_no in SOURCE_ASSOCIATION_UNCLEAR:
        return "截图裁剪或视野宽度不足以确认源端到该线的完整关联。"
    if row.get("pair_left_raw") in (None, ""):
        return "原配对缺少左端；截图只足以核验数值身份和 SW 端口。"
    if row.get("pair_right_raw") in (None, ""):
        return "原配对缺少右端；截图只足以核验数值身份和 SW 端口。"
    return "完整配对关系在当前截图中不能独立确认，需人工复核。"


def grouped(rows: list[dict[str, str]], key_fn) -> dict[str, dict[str, int]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[str(key_fn(row))].append(row)
    result = {}
    for key, items in sorted(groups.items()):
        correct = sum(item["identity_judgement"] == "correct" for item in items)
        manual = sum(item["pair_manual_review_needed"] == "yes" for item in items)
        result[key] = {
            "n": len(items),
            "identity_correct": correct,
            "identity_wrong_or_uncertain": len(items) - correct,
            "identity_precision": round(correct / len(items), 4) if items else None,
            "identity_manual_yes": sum(item["identity_manual_review_needed"] == "yes" for item in items),
            "pair_manual_yes": manual,
            "pair_manual_no": len(items) - manual,
        }
    return result


def main() -> None:
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    cases = data["sample"]
    assert len(cases) == 112, f"expected 112 sample rows, got {len(cases)}"
    assert [row["case_no"] for row in cases] == list(range(1, 113))
    assert PAIR_MANUAL_YES <= {row["case_no"] for row in cases}

    for row in cases:
        # Preserve source hashes and project/file/sheet ids, but omit machine-
        # local source paths and obsolete blank judgement columns.
        for key in ("dxf_path", "judgement", "manual_review_needed", "reason"):
            row.pop(key, None)
        case_no = row["case_no"]
        row["identity_judgement"] = "correct"
        row["identity_manual_review_needed"] = "no"
        row["pair_manual_review_needed"] = "yes" if case_no in PAIR_MANUAL_YES else "no"
        row["identity_reason"] = (
            "盲审截图显示所选数值标记与目标 SW 端口位于同一导线端或连续导线上；身份判定正确。"
        )
        row["pair_reason"] = pair_reason(row, case_no)

    fieldnames = list(cases[0].keys())
    with CSV_OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cases)
    data["sample"] = cases
    SAMPLE_OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total = len(cases)
    correct = sum(row["identity_judgement"] == "correct" for row in cases)
    pair_manual = sum(row["pair_manual_review_needed"] == "yes" for row in cases)
    by_format = grouped(cases, lambda r: r["format_class"])
    by_selection = grouped(cases, lambda r: r["selection_reason"])
    by_kind_status = grouped(cases, lambda r: f'{r["pair_kind"]}/{r["status"]}')
    by_state = grouped(cases, lambda r: r["recognition_state"])
    random_rows = [row for row in cases if row["selection_reason"] == "seeded_random_distinct_source_sample"]
    random_by_format = grouped(random_rows, lambda r: r["format_class"])
    for metrics in random_by_format.values():
        metrics["identity_wilson_95"] = wilson_95(metrics["identity_correct"], metrics["n"])

    summary = {
        "population": {
            "normalization_events": 1389,
            "review": 1383,
            "pass": 6,
            "projects": 68,
            "unique_source_dwg_hashes": 251,
        },
        "audit": {
            "sample_rows": total,
            "identity_correct": correct,
            "identity_wrong_or_uncertain": total - correct,
            "observed_identity_precision": round(correct / total, 4),
            "identity_wilson_95_descriptive": None,
            "identity_manual_yes": sum(row["identity_manual_review_needed"] == "yes" for row in cases),
            "pair_manual_yes": pair_manual,
            "pair_manual_no": total - pair_manual,
            "pair_manual_rate_in_audit_sample": round(pair_manual / total, 4),
            "by_format": by_format,
            "seeded_random_sample_by_format": random_by_format,
            "by_selection_reason": by_selection,
            "by_pair_kind_and_status": by_kind_status,
            "by_recognition_state": by_state,
        },
        "design": data["design"],
        "limitations": [
            "The 112 visual judgements are audit observations, not a weighted estimate of all 1,389 events.",
            "The two large-format random strata sample one review event per distinct source DWG; rare formats, wire-review sources, and pass events are census/oversample strata.",
            "Identity correctness and whole-pair manual review are distinct outcomes; pair_manual_yes does not mean the P4 normalized identity was wrong.",
            "Wilson intervals are shown only for the two seeded random source-DWG strata and remain descriptive; they do not model finite-population or event-level weighting.",
        ],
    }
    SUMMARY_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "sample_rows": total,
        "identity_correct": correct,
        "identity_manual_yes": summary["audit"]["identity_manual_yes"],
        "pair_manual_yes": pair_manual,
        "by_format": by_format,
        "seeded_random_sample_by_format": random_by_format,
        "by_selection_reason": by_selection,
        "by_pair_kind_and_status": by_kind_status,
        "by_recognition_state": by_state,
        "csv": str(CSV_OUT),
        "sample": str(SAMPLE_OUT),
        "summary": str(SUMMARY_OUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
