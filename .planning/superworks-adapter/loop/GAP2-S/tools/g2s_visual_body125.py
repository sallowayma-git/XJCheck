"""GAP2-S check of the nine cuts whose body width is 1.25 (read-only; one PNG).

These are not in the 2.5 population of GAP2-PAIR, so they are drawn apart: wide view and zoom for four of the nine.
Usage: python g2s_visual_body125.py ROUND_ROOT OUT_PNG
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / ".planning/superworks-adapter/loop/GAP/tools"))
import gaplib as G  # noqa: E402
import gap_render as R  # noqa: E402

BLUE, ORANGE, MAGENTA = "#1f78b4", "#ff7f00", "#e7298a"
ROUND = Path(sys.argv[1])
OUT = Path(sys.argv[2])
CASES = [("p047", "F0010", "F2D9"), ("p059", "F0012", "9AC5"), ("p061", "F0011", "F5F2"), ("p006", "F0011", "242C6")]


def mid(row):
    return ((row["start_x"] + row["end_x"]) / 2, (row["start_y"] + row["end_y"]) / 2)


def main():
    dxf_of = G.manifest_map()[0]
    panels = []
    for pid, file_id, insert in CASES:
        findings = next((ROUND / pid).glob("*/findings"))
        ports = pd.read_parquet(findings / "sw_ports.parquet")
        lines = pd.read_parquet(findings / "lines.parquet")
        sel = ports[(ports["insert_handle"] == insert) & (ports["file_id"] == file_id) & (ports["category"] == "装置端子")]
        if len(sel) < 2:
            continue
        pts = [mid(r) for r in sel.to_dict("records")]
        segs = []
        for r in sel.to_dict("records"):
            contacts = __import__("json").loads(r["wire_contacts"]) if isinstance(r["wire_contacts"], str) else r["wire_contacts"]
            for c in contacts:
                seg = lines[(lines["file_id"] == file_id) & (lines["handle"] == c["wire_handle"])]
                for s in seg.itertuples():
                    segs.append((float(s.start_x), float(s.start_y), float(s.end_x), float(s.end_y), BLUE if r["port_number"] == sel.iloc[0]["port_number"] else ORANGE, 2.0))
        boxes = [(r["start_x"], r["start_y"] - 0.3, r["end_x"], r["end_y"] + 0.3, BLUE) for r in sel.to_dict("records")]
        identity = sel.iloc[0]["endpoint_identity"]
        title = [f"{pid} {file_id} insert {insert} {identity}", "端子本体宽 1.25，两端口 " + ", ".join(str(r) for r in sel["port_number"])]
        dxf = dxf_of.get((pid, file_id))
        cx, cy = pts[0]
        wide = R.window_around(pts, pad=8.0, min_size=20.0)
        zoom = R.window_around(pts, pad=2.0, min_size=6.0)
        panels.append(R.Panel(title, dxf, wide, segs=segs, pts=[(x, y, BLUE) for x, y in pts], boxes=boxes))
        panels.append(R.Panel(["近景"], dxf, zoom, segs=segs, pts=[(x, y, BLUE) for x, y in pts], boxes=boxes))
    R.render(OUT, ["GAP2-S 本体宽 1.25 的切开（9 例中的 4 例）：两端口 TERMPOINT 框，蓝/橙线为两端口所在导线。"], panels, cols=2)
    print("wrote", OUT, len(panels) // 2, "cases")


if __name__ == "__main__":
    main()
