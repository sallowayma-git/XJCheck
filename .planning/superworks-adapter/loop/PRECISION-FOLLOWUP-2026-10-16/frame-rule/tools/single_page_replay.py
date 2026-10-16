from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[6]
SNAPSHOT = ROOT / ".tmp/precision_loop_20261016/frame_rule_src_final4"
sys.path.insert(0, str(SNAPSHOT))
from dwg_audit.services.execution import run_analysis_workflow  # noqa: E402


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def close_to(actual, expected, tol=1e-6) -> bool:
    return isinstance(actual, (list, tuple)) and len(actual) == len(expected) and all(
        abs(float(left) - float(right)) <= tol for left, right in zip(actual, expected)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / ".tmp/precision_loop_20261016/frame_rule_single_page_final4_repro")
    parser.add_argument("--summary", type=Path,
                        default=ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/single_page_final4_repro_summary.json")
    args = parser.parse_args()
    out_dir = args.out.resolve()
    summary_path = args.summary.resolve()
    if out_dir.exists():
        raise FileExistsError(f"Refusing to reuse an existing replay directory: {out_dir}")
    corpus = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
    cases = [
        {"name": "positive_frame", "project_id": "p000", "file_id": "F0008",
         "coords": [187.5, 237.5, 190.0, 237.5], "expect_frame_suppression": True},
        {"name": "negative_real_T_dot", "project_id": "p020", "file_id": "F0016",
         "coords": [235.0, 105.0, 275.0, 105.0], "source_handle": "17F11",
         "expect_frame_suppression": False},
        {"name": "negative_wire_crosses_frame", "project_id": "p013", "file_id": "F0015",
         "coords": [135.0, 257.5, 157.5, 257.5], "source_handle": "167A0",
         "expect_frame_suppression": False},
        {"name": "negative_frame_crossing_to_terminal", "project_id": "p027", "file_id": "F0018",
         "coords": [92.92762555355648, 36.48699003722714, 102.9276255535565, 36.48699003722714],
         "source_handle": "1A008", "expect_frame_suppression": False},
    ]
    results = []
    for case in cases:
        project = next(row for row in corpus["projects"] if row["project_id"] == case["project_id"])
        source = next(row for row in project["files"] if row["file_id"] == case["file_id"])
        source_path, dxf_path = Path(source["path"]), Path(source["dxf_path"])
        if digest(source_path) != source["sha256"] or digest(dxf_path) != source["dxf_sha256"]:
            raise AssertionError(f"Frozen input hash mismatch for {case['project_id']}/{case['file_id']}")

        case_root = out_dir / case["name"]
        input_root, output_root = case_root / "input", case_root / "output"
        input_root.mkdir(parents=True)
        output_root.mkdir(parents=True)
        shutil.copy2(source_path, input_root / source_path.name)
        for xml_path in project["xml"]:
            shutil.copy2(xml_path, input_root / Path(xml_path).name)
        for prj in Path(project["input_root"]).glob("*.prj"):
            shutil.copy2(prj, input_root / prj.name)
        cache = output_root / "cache/converted_dxf"
        cache.mkdir(parents=True)
        shutil.copy2(dxf_path, cache / f"F0001_{source['sha256'][:8]}.dxf")

        run = run_analysis_workflow(input_root=input_root, output_root=output_root, include_audit=True)
        if len(run.project_dirs) != 1:
            raise AssertionError(f"Expected one-page analysis, got {len(run.project_dirs)} project outputs")
        project_dir = run.project_dirs[0]
        issues = json.loads((project_dir / "audit/issues.json").read_text(encoding="utf-8"))
        diagnostics = pd.read_parquet(project_dir / "audit/sw_recognition_diagnostics.parquet")
        frame_rows = diagnostics.loc[diagnostics.suppressed_by == "terminal_frame_boundary"].to_dict(orient="records")
        target_frame_rows = [row for row in frame_rows
                             if close_to(json.loads(row["coords"]) if isinstance(row["coords"], str) else row["coords"],
                                         case["coords"])
                             and (not case.get("record_id") or row.get("record_id") == case["record_id"])]
        frame_hit = bool(target_frame_rows)
        if frame_hit != case["expect_frame_suppression"]:
            raise AssertionError(f"{case['name']}: frame suppression={frame_hit}, expected={case['expect_frame_suppression']}")

        retained_candidate = False
        if case.get("source_handle"):
            for issue in issues:
                evidence = issue.get("evidence") or {}
                coords = evidence.get("coords")
                handles = evidence.get("source_handles") or []
                if case["source_handle"] in handles and close_to(coords, case["coords"]):
                    retained_candidate = issue.get("rule_id") == "R-RECOGNITION-GAP"
                    break
            if not retained_candidate:
                raise AssertionError(f"Negative control {case['name']} did not remain as R-RECOGNITION-GAP")
        if case.get("record_id") and not case["expect_frame_suppression"]:
            retained_candidate = any(
                issue.get("rule_id") == "R-RECOGNITION-GAP"
                and (issue.get("evidence") or {}).get("record_id") == case["record_id"]
                and close_to((issue.get("evidence") or {}).get("coords"), case["coords"])
                for issue in issues
            )
            if not retained_candidate:
                raise AssertionError("The known wire-crosses-frame negative control did not remain as R-RECOGNITION-GAP")

        gate = json.loads((project_dir / "audit/sw_recognition_gate.json").read_text(encoding="utf-8"))
        results.append({
            "case": case["name"], "project_id": case["project_id"], "file_id": case["file_id"],
            "input_sha256": source["sha256"], "dxf_sha256": source["dxf_sha256"],
            "analyzed_page_count": len(pd.read_parquet(project_dir / "findings/pages.parquet")),
            "issue_count": len(issues), "frame_suppression_count": len(frame_rows),
            "target_frame_suppressed": frame_hit, "negative_control_retained": retained_candidate,
            "target_suppression_details": [row for row in frame_rows if close_to(
                json.loads(row["coords"]) if isinstance(row["coords"], str) else row["coords"], case["coords"])],
            "gate_summary": gate,
            "project_dir": str(project_dir.relative_to(ROOT)),
        })

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({"snapshot": str(SNAPSHOT.relative_to(ROOT)), "cases": results}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
