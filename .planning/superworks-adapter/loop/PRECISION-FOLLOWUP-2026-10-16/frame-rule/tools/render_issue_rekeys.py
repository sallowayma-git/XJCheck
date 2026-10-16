from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[6]
RENDERER = ROOT / ".planning/superworks-adapter/loop/GAP/tools/gap_render.py"
SPEC = importlib.util.spec_from_file_location("gap_render_issue_rekeys", RENDERER)
gap_render = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gap_render)
CASES = (
    ("p029", "PSW6d1c4e10124ee795"), ("p029", "PSWf41132244486f7ad"),
    ("p030", "PSW6d1c4e10124ee795"), ("p030", "PSWf41132244486f7ad"),
    ("p031", "PSW6d1c4e10124ee795"), ("p031", "PSWf41132244486f7ad"),
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=ROOT / ".tmp/precision_loop_20261016/frame_rule_final3_full77")
    parser.add_argument("--out", type=Path,
                        default=ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/issue_rekeys/screenshots")
    parser.add_argument("--index", type=Path,
                        default=ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/issue_rekeys/screenshot_index.csv")
    args = parser.parse_args()
    run_dir, output_dir, index_path = args.run.resolve(), args.out.resolve(), args.index.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    project_dirs = {row["project_id"]: Path(row["project_dir"]) for row in run["projects"]}
    rows = []
    for project_id, record_id in CASES:
        project_dir = project_dirs[project_id]
        issues = json.loads((project_dir / "audit/issues.json").read_text(encoding="utf-8"))
        issue = next(row for row in issues if (row.get("evidence") or {}).get("record_id") == record_id)
        evidence = issue["evidence"]
        coords = [float(value) for value in evidence["coords"]]
        file_id, sheet_id = str(issue["file_id"]), str(issue["sheet_id"])
        dxf_matches = sorted((project_dir.parent / "cache/converted_dxf").glob(f"{file_id}_*.dxf"))
        if len(dxf_matches) != 1:
            raise SystemExit(f"Expected one cached DXF for {project_id}/{file_id}, got {len(dxf_matches)}")
        dxf = dxf_matches[0]
        points = [(coords[0], coords[1]), (coords[2], coords[3])]
        local = gap_render.window_around(points, pad=4.0, min_size=18.0)
        context = gap_render.window_around(points, pad=22.0, min_size=52.0)
        common = [f"{project_id} {file_id}/{sheet_id} | {issue['issue_id']} | {record_id}",
                  f"R-RECOGNITION-GAP retained after frame-rule replay | handles={evidence.get('source_handles')}",
                  f"left={issue.get('left_value')} | right={issue.get('right_value')} | coords={coords}"]
        name = f"{project_id}_{file_id}_{sheet_id}_{record_id}.png"
        path = output_dir / name
        panels = [
            gap_render.Panel(common + ["Raw DXF, close window"], dxf, local),
            gap_render.Panel(common + ["Candidate observation overlay; raw context remains on right"], dxf, local,
                             segs=[(*coords, "#0066ff", 2.6)],
                             pts=[(coords[0], coords[1], "#ff8f00"), (coords[2], coords[3], "#ff8f00")]),
            gap_render.Panel(common + ["Raw DXF, wider window without overlays"], dxf, context),
        ]
        gap_render.render(path, ["Case-by-case visual check of issue identity changes after frame closures."], panels, cols=3)
        rows.append({
            "project_id": project_id, "issue_id": issue["issue_id"], "record_id": record_id,
            "file_id": file_id, "sheet_id": sheet_id, "source_handles": json.dumps(evidence.get("source_handles") or []),
            "left_value": issue.get("left_value"), "right_value": issue.get("right_value"),
            "coords": json.dumps(coords), "screenshot": str(path.relative_to(ROOT)), "sha256": digest(path),
        })
        print(f"rendered {project_id}/{record_id}", flush=True)
        gap_render.CACHE._docs.clear()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"rendered={len(rows)} index={index_path}")


if __name__ == "__main__":
    main()
