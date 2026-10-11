"""LOGGEN-MISMATCH: DXF close-ups for terminal ends whose identity label is not the nearest drawn label (read-only).

Usage: python render_terminal_nearest.py <scratch_dir> <round14_dir> <out_png> [n]

Samples identity_present_not_nearest rows with margin >= 2 units (seed fixed). Panel: port (green), identity
text (gold box, distance printed), nearest identity-like text (magenta box, distance printed).
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
R4 = ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"
MANIFEST = ROOT / ".planning/superworks-adapter/corpus_manifest.json"
SEED = 20261013
spec = importlib.util.spec_from_file_location("r4", str(R4))
r4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r4)


def main(scratch: Path, round_dir: Path, out_png: Path, n: int = 6) -> None:
    rows = pd.read_pickle(scratch / "nearest_terminal.pkl")
    rows = rows[rows.status == "identity_present_not_nearest"].copy()
    rows["margin"] = rows.identity_dist - rows.nearest_dist
    rows = rows[rows.margin >= 2]
    picked = rows.sample(n=min(n, len(rows)), random_state=SEED)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dxf = {p["project_id"]: {f["file_id"]: f["dxf_path"] for f in p["files"]} for p in manifest["projects"]}
    cache = r4.DxfCache()
    panels = []
    for _, r in picked.iterrows():
        fdir = next(c for c in (round_dir / r.project).glob("*/findings") if (c / "sw_wire_routes.parquet").exists())
        tx = pd.read_parquet(fdir / "texts.parquet", columns=["file_id", "normalized_text", "text", "bbox_min_x", "bbox_min_y",
                                                            "bbox_max_x", "bbox_max_y"])
        tx = tx[tx.file_id == r.file_id]
        tx["value"] = tx["normalized_text"].where(tx["normalized_text"].notna() & (tx["normalized_text"] != ""), tx["text"]).fillna("").astype(str)
        tx["cx"] = (tx.bbox_min_x + tx.bbox_max_x) / 2
        tx["cy"] = (tx.bbox_min_y + tx.bbox_max_y) / 2
        d = ((tx.cx - r.x) ** 2 + (tx.cy - r.y) ** 2) ** 0.5
        near = tx[d <= 20].assign(d=d[d <= 20])
        boxes = []
        for _, t in near.iterrows():
            if str(t.value) == str(r.identity):
                boxes.append((t.bbox_min_x, t.bbox_min_y, t.bbox_max_x, t.bbox_max_y, "gold"))
            elif str(t.value) == str(r.nearest):
                boxes.append((t.bbox_min_x, t.bbox_min_y, t.bbox_max_x, t.bbox_max_y, "magenta"))
        x0, x1 = r.x - 16, r.x + 16
        y0, y1 = r.y - 12, r.y + 12
        header = [f"{r.project} file={r.file_id} 身份={r.identity} 身份文字距离={r.identity_dist:.2f}",
                  f"最近身份型文字={r.nearest} 距离={r.nearest_dist:.2f} 差={r.margin:.2f}",
                  "金框=身份文字 洋红=最近文字 绿=端口触点",
                  "近旁文字: " + ", ".join(f"{t.value}({t.d:.1f})" for _, t in near.sort_values('d').head(8).iterrows())]
        panels.append(r4.Panel(header, dxf_path=dxf[r.project][r.file_id], window=(x0, y0, x1, y1), boxes=boxes,
                               points=[(r.x, r.y, "lime")]))
    head = ["端子端点：元数据身份文字不是图上最近的身份型文字（差 >= 2 单位）",
            f"随机抽样 {len(panels)} 例（固定种子），共 {len(rows)} 例满足条件"]
    r4._render_issue_png(out_png, head, panels, cache)
    print("wrote", out_png.name, len(panels))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 6)
