"""LOGGEN-MISMATCH: DXF close-ups of the PWR header-number conflict candidates (read-only).

Usage: python render_pwr_conflict.py <scratch_dir> <round14_dir> <out_png> [n]

Candidates: PWR-type identities (PWRk) whose nearest PWR header on the same row band, left of the port
(<= 45 units), carries another number (PWRj, j != k). Seeded sample; panel = port (green), identity text
(gold), PWR header texts (magenta).
"""
from __future__ import annotations

import glob
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
R4 = ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"
MANIFEST = ROOT / ".planning/superworks-adapter/corpus_manifest.json"
SEED = 20261014
spec = importlib.util.spec_from_file_location("r4", str(R4))
r4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r4)


def candidates(scratch: Path, round_dir: Path) -> pd.DataFrame:
    e = pd.read_pickle(scratch / "ends.pkl")
    e = e[e.geometry.fillna(False).astype(bool)].copy()
    p = e[e.identity.astype(str).str.match(r"^.*PWR\d$")].copy()
    rows = []
    for (pid, fid), g in p.groupby(["project", "file_id"]):
        fd = next(c for c in glob.glob(str(round_dir / pid / "*/findings")) if Path(c, "sw_wire_routes.parquet").exists())
        tx = pd.read_parquet(Path(fd) / "texts.parquet", columns=["file_id", "normalized_text", "text", "bbox_min_x", "bbox_min_y", "bbox_max_x", "bbox_max_y"])
        tx = tx[tx.file_id == fid].copy()
        tx["v"] = tx.normalized_text.where(tx.normalized_text.notna() & (tx.normalized_text != ""), tx.text).fillna("").astype(str)
        tx["cx"] = (tx.bbox_min_x + tx.bbox_max_x) / 2
        tx["cy"] = (tx.bbox_min_y + tx.bbox_max_y) / 2
        hdr = tx[tx.v.str.fullmatch(r"PWR\d")]
        for r in g.itertuples():
            left = hdr[(hdr.cx <= r.x) & (r.x - hdr.cx <= 45) & (np.abs(hdr.cy - r.y) <= 40)]
            if left.empty:
                continue
            h = left.loc[(r.x - left.cx).idxmin()]
            if h.v[-1] != str(r.identity)[-1]:
                rows.append({"project": pid, "file_id": fid, "identity": r.identity, "verdict": r.verdict,
                             "header": h.v, "dx": round(float(r.x - h.cx), 2), "x": float(r.x), "y": float(r.y),
                             "port_id": r.port_id, "record_id": r.record_id, "wire_handle": r.wire_handle,
                             "end_class": r.end_class, "detail": json.dumps(r.detail, ensure_ascii=False) if isinstance(r.detail, dict) else ""})
    return pd.DataFrame(rows)


def main(scratch: Path, round_dir: Path, out_png: Path, n: int = 6) -> None:
    cand = candidates(scratch, round_dir)
    cand.to_pickle(scratch / "pwr_conflict.pkl")
    print("candidates:", len(cand), "by sheet:", cand.groupby(["project", "file_id"]).size().to_dict())
    picked = cand.sample(n=min(n, len(cand)), random_state=SEED)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dxf = {p["project_id"]: {f["file_id"]: f["dxf_path"] for f in p["files"]} for p in manifest["projects"]}
    cache = r4.DxfCache()
    panels = []
    for _, r in picked.iterrows():
        fd = next(c for c in glob.glob(str(round_dir / r.project / "*/findings")) if Path(c, "sw_wire_routes.parquet").exists())
        tx = pd.read_parquet(Path(fd) / "texts.parquet", columns=["file_id", "normalized_text", "text", "bbox_min_x", "bbox_min_y", "bbox_max_x", "bbox_max_y"])
        tx = tx[tx.file_id == r.file_id].copy()
        tx["v"] = tx.normalized_text.where(tx.normalized_text.notna() & (tx.normalized_text != ""), tx.text).fillna("").astype(str)
        tx["cx"] = (tx.bbox_min_x + tx.bbox_max_x) / 2
        tx["cy"] = (tx.bbox_min_y + tx.bbox_max_y) / 2
        boxes = []
        near = tx[(np.abs(tx.cx - r.x) <= 25) & (np.abs(tx.cy - r.y) <= 25)]
        for _, t in near.iterrows():
            if t.v == r.identity:
                boxes.append((t.bbox_min_x, t.bbox_min_y, t.bbox_max_x, t.bbox_max_y, "gold"))
            elif t.v.startswith("PWR"):
                boxes.append((t.bbox_min_x, t.bbox_min_y, t.bbox_max_x, t.bbox_max_y, "magenta"))
        header = [f"{r.project} file={r.file_id} 身份={r.identity} 判定={r.verdict}",
                  f"左侧最近 PWR 标题={r.header} dx={r.dx}（端口在其右侧）",
                  "金=身份文字 洋红=PWR 标题 绿=端口触点"]
        panels.append(r4.Panel(header, dxf_path=dxf[r.project][r.file_id], window=(r.x - 22, r.y - 14, r.x + 22, r.y + 14),
                               boxes=boxes, points=[(r.x, r.y, "lime")]))
    head = ["PWR 族候选：身份编号与左侧同行 PWR 标题编号不同",
            f"共 {len(cand)} 例，固定种子抽样 {len(panels)} 例"]
    r4._render_issue_png(out_png, head, panels, cache)
    picked.drop(columns=["detail"]).to_json(scratch / "pwr_sample.json", orient="records", force_ascii=False, indent=1)
    print("wrote", out_png.name, len(panels))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 6)
