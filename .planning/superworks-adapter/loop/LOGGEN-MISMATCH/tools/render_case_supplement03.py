"""LOGGEN-MISMATCH case figure for supplement_03 (read-only).

Usage: python render_case_supplement03.py <round14_dir> <out_png>

Project p061, file F0022 (backplate FCK-851C-G-1, insert 9B07). Panels:
 1. port 532 (column 5, row 32) with its row text "32", connect label EE4C "3-21n232" on wire EE4B
 2. port 232 (column 2, row 32) with connect label EE0A "3-21n231,3-21n532" on wire EE09
 3. the row of five columns: the "32" row text of each column, with the 5 ports 132..532 marked
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
R4 = ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"
MANIFEST = ROOT / ".planning/superworks-adapter/corpus_manifest.json"
spec = importlib.util.spec_from_file_location("r4", str(R4))
r4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r4)


def main(round_dir: Path, out_png: Path) -> None:
    fdir = next(c for c in (round_dir / "p061").glob("*/findings") if (c / "sw_wire_routes.parquet").exists())
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dxf = next(f["dxf_path"] for p in manifest["projects"] if p["project_id"] == "p061" for f in p["files"] if f["file_id"] == "F0022")
    tx = pd.read_parquet(fdir / "texts.parquet", columns=["file_id", "handle", "text", "normalized_text",
                                                        "bbox_min_x", "bbox_min_y", "bbox_max_x", "bbox_max_y"])
    tx = tx[tx.file_id == "F0022"].copy()
    tx["v"] = tx.normalized_text.where(tx.normalized_text.notna() & (tx.normalized_text != ""), tx.text).fillna("").astype(str)
    tx["cx"] = (tx.bbox_min_x + tx.bbox_max_x) / 2
    tx["cy"] = (tx.bbox_min_y + tx.bbox_max_y) / 2
    sp = pd.read_parquet(fdir / "sw_part_instances.parquet", columns=["insert_handle", "ports"])
    part = json.loads(sp[sp.insert_handle.astype(str) == "9B07"].iloc[0].ports)
    ports = {str(p["port_number"]): ((p["start_x"] + p["end_x"]) / 2, (p["start_y"] + p["end_y"]) / 2) for p in part}
    lines = pd.read_parquet(fdir / "lines.parquet", columns=["file_id", "handle", "start_x", "start_y", "end_x", "end_y"])
    lines = lines[lines.file_id == "F0022"]

    def wire(handle):
        r = lines[lines.handle.astype(str) == handle]
        return None if r.empty else tuple(float(v) for v in r.iloc[0][["start_x", "start_y", "end_x", "end_y"]])

    def boxes_for(x0, x1, y0, y1, extra=()):
        out = []
        for _, t in tx.iterrows():
            if x0 <= t.cx <= x1 and y0 <= t.cy <= y1:
                color = "gold" if t.v in ("32", "3-21n") else ("magenta" if t.v.startswith("3-21n2") or "3-21n231" in t.v else "gray")
                out.append((t.bbox_min_x, t.bbox_min_y, t.bbox_max_x, t.bbox_max_y, color))
        for e in extra:
            out.append(e)
        return out

    panels = []
    # 1. port 532 and connect label EE4C on wire EE4B
    x, y = ports["532"]
    w = wire("EE4B")
    head1 = ["案例1 端口 532（第 5 列第 32 行）",
             "身份 3-21n532：端口号 532 来自 TERMPOINT；图上行号 32 紧邻本端；",
             "接线标签 EE4C（挂在导线 EE4B 上）印 3-21n232，是本端导线的接线去向文字",
             "金=行号/标签 洋红=接线去向标签 橙=导线 绿=端口触点"]
    b1 = boxes_for(x - 14, x + 14, y - 10, y + 10, extra=[(w[0] - .4, min(w[1], w[3]) - .4, w[2] + .4, max(w[1], w[3]) + .4, "orange")] if w else [])
    panels.append(r4.Panel(head1, dxf_path=dxf, window=(x - 14, y - 10, x + 14, y + 10), boxes=b1, points=[(x, y, "lime")]))
    # 2. port 232 and its label EE0A
    x2, y2 = ports["232"]
    w2 = wire("EE09")
    head2 = ["案例1 端口 232（第 2 列第 32 行）",
             "身份 3-21n232，与 532 为不同端子；接线标签 EE0A 印 3-21n231,3-21n532",
             "（即 232 的导线去向列出 231 与 532）",
             "金=行号/标签 洋红=接线去向标签 橙=导线 绿=端口触点"]
    b2 = boxes_for(x2 - 14, x2 + 14, y2 - 10, y2 + 10, extra=[(w2[0] - .4, min(w2[1], w2[3]) - .4, w2[2] + .4, max(w2[1], w2[3]) + .4, "orange")] if w2 else [])
    panels.append(r4.Panel(head2, dxf_path=dxf, window=(x2 - 14, y2 - 10, x2 + 14, y2 + 10), boxes=b2, points=[(x2, y2, "lime")]))
    # 3. the whole row of five columns
    head3 = ["案例1 同一行的五列（背板第 32 行复制）",
             "端口 131/132、231/232、331/332、431/432、531/532 位于 5 个列副本；行号 32 按列重复",
             "列序 1..5 与端口首位数字一致（本例）"]
    xs = [ports[k][0] for k in ("132", "232", "332", "432", "532")]
    b3 = boxes_for(min(xs) - 30, max(xs) + 14, 145, 160)
    pts = [(ports[k][0], ports[k][1], "lime") for k in ("132", "232", "332", "432", "532")]
    panels.append(r4.Panel(head3, dxf_path=dxf, window=(min(xs) - 30, 140, max(xs) + 14, 175), boxes=b3, points=pts))

    cache = r4.DxfCache()
    r4._render_issue_png(out_png, ["补充 3（p061 F0022 背板 FCK-851C-G-1，记录 SWWR:F0022:PCL:9B07:532）"] + [""],
                         panels, cache)
    print("wrote", out_png.name)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
