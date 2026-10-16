from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[6]
BASE = ROOT / ".planning/superworks-adapter/loop/GAP-TRIAGE/audits/current-wire-shapes-2026-10-16"
RAIL = BASE / "wide_recheck_rail_T_2026-10-16.csv"
PORT = ROOT / ".tmp/precision_loop_20261015/current_wire_shape_audit_20261016/review_E_port_both_ends_wide_20261016.csv"
OUT = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule"
IMAGE_OUT = OUT / "shape_samples_60"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rail", type=Path, default=RAIL)
    parser.add_argument("--port", type=Path, default=PORT)
    parser.add_argument("--out", type=Path, default=OUT / "frame_shape_samples_60.csv")
    parser.add_argument("--image-out", type=Path, default=IMAGE_OUT)
    args = parser.parse_args()

    rail = pd.read_csv(args.rail, dtype=str).fillna("")
    port = pd.read_csv(args.port, dtype=str).fillna("")
    rows = []
    for group, data in (("E_rail_T", rail), ("E_port_both_ends", port)):
        for item in data.to_dict(orient="records"):
            project = item.get("project") or item.get("project_id") or ""
            issue_id = item.get("issue_id", "")
            before = item.get("original_verdict", "") if group == "E_rail_T" else item.get("old_manual_review_need", "")
            manual = item.get("new_verdict", "") if group == "E_rail_T" else item.get("new_manual_review_need", "")
            frame = "yes" if item.get("frame_boundary", "") in ("是", "yes", "true", "1") else "no"
            reason = item.get("reason", "")
            if group == "E_port_both_ends" and project == "p027" and issue_id == "ISWcaef9bdbcab72db473a1":
                frame = "no"
                manual = "yes"
                reason = ("导线穿过 From BCU 虚线框右边界后继续到框外 3-4QD11 端子；"
                          "框边交点位于线段内部，因此不是止于框边的端子短线，端点身份仍需人工核对。")
            screenshot_field = item.get("wide_screenshot_path", "")
            source = Path(screenshot_field)
            if not source.is_file():
                raise SystemExit(f"Wide screenshot missing for {project}/{issue_id}: {source}")
            args.image_out.mkdir(parents=True, exist_ok=True)
            target = args.image_out / source.name
            if not target.is_file():
                shutil.copy2(source, target)
            rows.append({
                "group": group, "sample_no": item.get("sample_no", ""), "issue_id": issue_id,
                "project_id": project, "file_id": item.get("file_id", ""), "sheet_id": item.get("sheet_id", ""),
                "manual_review_before_wide": before, "manual_review_need": manual, "frame_stop": frame,
                "reason": reason, "visible_shape": item.get("visible_shape", ""),
                "wide_screenshot": f"shape_samples_60/{target.name}", "sha256": sha256(target),
                "window_scale": "4x", "reviewer": "4x wide screenshot re-review",
            })
    frame = pd.DataFrame(rows)
    if len(frame) != 60 or frame.groupby("group").size().to_dict() != {"E_port_both_ends": 30, "E_rail_T": 30}:
        raise SystemExit(f"Expected 30 cases per class; got {frame.groupby('group').size().to_dict()}")
    if frame.duplicated(["project_id", "issue_id"]).any():
        raise SystemExit("Duplicate issue in the 60-case frame sample")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"cases={len(frame)}; frame_stops={int(frame.frame_stop.eq('yes').sum())}; output={args.out}")


if __name__ == "__main__":
    main()
