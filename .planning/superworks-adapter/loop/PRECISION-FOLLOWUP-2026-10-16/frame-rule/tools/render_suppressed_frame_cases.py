from __future__ import annotations

import csv
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[6]
DEFAULT_RUN = ROOT / ".tmp/precision_loop_20261016/frame_rule_full77"
DEFAULT_INDEX = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/frame_suppression_screenshots.csv"
RENDERER = ROOT / ".planning/superworks-adapter/loop/GAP/tools/gap_render.py"
spec = importlib.util.spec_from_file_location("gap_render_frame", RENDERER)
gap_render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gap_render)


def parse(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_panel(title, dxf, window, coords, rect, contact):
    x0, y0, x1, y1 = window
    x_a, y_a, x_b, y_b = map(float, coords)
    segs = [(x_a, y_a, x_b, y_b, "#0066ff", 2.6)]
    boxes = [(*map(float, rect), "#e53935")]
    pts = [(float(contact[0]), float(contact[1]), "#d000d0")]
    # Distinguish the in-frame end from the out-of-frame end where possible.
    for x, y in ((x_a, y_a), (x_b, y_b)):
        if x0 <= x <= x1 and y0 <= y <= y1:
            pts.append((x, y, "#ff8f00"))
    label = title[2] if len(title) > 2 else ""
    texts = [(float(rect[0]) + 1.0, float(rect[3]) + 1.0, label[:90], "#c62828")]
    return gap_render.Panel(title, dxf, window, segs=segs, pts=pts, boxes=boxes, texts=texts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--sample-judgments", type=Path,
                        help="Render only old sampled issues that the current replay suppresses.")
    parser.add_argument("--removed-issues", type=Path,
                        help="Removed-issue manifest used with --sample-judgments.")
    args = parser.parse_args()
    if bool(args.sample_judgments) != bool(args.removed_issues):
        raise SystemExit("--sample-judgments and --removed-issues must be supplied together")
    run_dir = args.run.resolve()
    output_dir = (args.out or (run_dir / "frame_screenshots")).resolve()
    index_path = args.index.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    if args.sample_judgments:
        sampled = pd.read_csv(args.sample_judgments, dtype=str).fillna("")
        sampled = sampled.rename(columns={"project": "project_id"})
        removed = pd.read_csv(args.removed_issues, dtype=str).fillna("")
        joined = removed.merge(sampled, on=["project_id", "issue_id"], how="inner", validate="one_to_one")
        sample_record_keys = set(zip(joined.project_id, joined.record_id))
        expected_sample_rows = len(joined)
    else:
        sample_record_keys = None
        expected_sample_rows = None
    completed = sorted(run_dir.glob("p*/complete.json"))
    run_summary = run_dir / "run.json"
    expected = len(json.loads(run_summary.read_text(encoding="utf-8"))["projects"]) if run_summary.is_file() else None
    if not completed or (expected is not None and len(completed) != expected):
        raise SystemExit(f"Expected {expected or 'all selected'} completed projects, found {len(completed)}")
    for complete_path in completed:
        pid = complete_path.parent.name
        complete = json.loads(complete_path.read_text(encoding="utf-8"))
        project_dir = Path(complete["project_dir"])
        diag_path = project_dir / "audit/sw_recognition_diagnostics.parquet"
        if not diag_path.is_file():
            continue
        diagnostics = pd.read_parquet(diag_path)
        selected = diagnostics.loc[diagnostics.suppressed_by == "terminal_frame_boundary"]
        if sample_record_keys is not None:
            selected = selected.loc[
                selected.record_id.map(lambda record_id: (pid, str(record_id)) in sample_record_keys)
            ]
        cache = complete_path.parent / "cache/converted_dxf"
        for ordinal, row in enumerate(selected.to_dict(orient="records"), 1):
            coords, rect, contact = parse(row["coords"]), parse(row["frame_rect"]), parse(row["frame_contact"])
            if not (coords and rect and contact):
                raise SystemExit(f"Missing geometric evidence in {pid}/{row.get('record_id')}")
            dxf_matches = sorted(cache.glob(f"{row['file_id']}_*.dxf"))
            if len(dxf_matches) != 1:
                raise SystemExit(f"Expected one cached DXF for {pid}/{row['file_id']}, got {len(dxf_matches)}")
            x0, y0, x1, y1 = map(float, rect)
            sx0, sy0, sx1, sy1 = map(float, coords)
            local = gap_render.window_around([(sx0, sy0), (sx1, sy1), tuple(contact)], pad=8.0, min_size=24.0)
            whole = gap_render.window_around([(x0, y0), (x1, y1), (sx0, sy0), (sx1, sy1)], pad=16.0, min_size=32.0)
            label = str(row.get("frame_label") or "")
            common = [
                f"{pid} {row['file_id']}/{row['sheet_id']} | {row.get('record_id')} | {row.get('line_group_id')}",
                f"terminal_frame_boundary | contact=({contact[0]}, {contact[1]}) | rect={tuple(rect)}",
                f"frame caption: {label[:160]}",
            ]
            name = f"{pid}_{ordinal:04d}_{row.get('record_id')}.png"
            output = output_dir / name
            panels = [
                make_panel(common + ["local contact and observed segment"], dxf_matches[0], local, coords, rect, contact),
                make_panel(common + ["full closed frame and nearby drawing"], dxf_matches[0], whole, coords, rect, contact),
                gap_render.Panel(common[:2] + ["original DXF frame and label; no geometry or caption overlays"],
                                 dxf_matches[0], whole),
            ]
            gap_render.render(output, ["Left: annotated local contact. Center: geometry overlays. Right: original DXF with no overlays."], panels, cols=3)
            rows.append({
                "project_id": pid, "record_id": row.get("record_id"), "object_key": row.get("object_key"),
                "file_id": row.get("file_id"), "sheet_id": row.get("sheet_id"),
                "line_group_id": row.get("line_group_id"), "coords": json.dumps(coords),
                "frame_rect": json.dumps(rect), "frame_contact": json.dumps(contact),
                "frame_label": label, "screenshot": str(output.relative_to(ROOT)), "sha256": sha256(output),
            })
            if len(rows) % 100 == 0:
                print(f"rendered {len(rows)} frame suppressions", flush=True)
        gap_render.CACHE._docs.clear()
    if expected_sample_rows is not None and len(rows) != expected_sample_rows:
        seen = {(row["project_id"], str(row["record_id"])) for row in rows}
        missing = sorted(sample_record_keys - seen)
        raise SystemExit(
            f"Expected {expected_sample_rows} sampled closures, rendered {len(rows)}; missing={missing[:10]}"
        )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"rendered={len(rows)} screenshots={output_dir} index={index_path}", flush=True)


if __name__ == "__main__":
    main()
