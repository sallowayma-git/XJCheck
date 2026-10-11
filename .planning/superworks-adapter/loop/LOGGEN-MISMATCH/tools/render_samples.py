"""LOGGEN-MISMATCH step 3 (read-only): DXF close-ups of sampled endpoints, one PNG per bucket.

Usage: python render_samples.py <scratch_dir> <round14_dir> <out_png_dir> <out_sample_json>

Each panel: DXF window around the port contact (green box), own drawn texts within R_NEAR (yellow boxes),
connect-label texts (magenta boxes), the record wire (orange box). Title lines give identity, verdict and the texts.
Samples are drawn with a fixed seed; the sample list (ids, bucket, reason) is written to out_sample_json.
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
import re
import sys
from pathlib import Path

import pandas as pd
from matplotlib.patches import Rectangle  # noqa: F401  (used through r4)

ROOT = Path("F:/workspace/XJToolkit")
R4 = ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"
MANIFEST = ROOT / ".planning/superworks-adapter/corpus_manifest.json"
SEED = 20261011
R_NEAR = 12.0
PAD = 14.0

spec = importlib.util.spec_from_file_location("r4", str(R4))
r4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r4)


def strict(s) -> str:
    return re.sub(r"\s+", "", str(s or "")).casefold()


def fdir_of(round_dir: Path, pid: str) -> Path:
    return next(c for c in (round_dir / pid).glob("*/findings") if (c / "sw_wire_routes.parquet").exists())


def dxf_map():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = {}
    for p in manifest["projects"]:
        out[p["project_id"]] = {f["file_id"]: f["dxf_path"] for f in p["files"]}
    return out


class ProjectTables:
    def __init__(self, fdir: Path):
        tx = pd.read_parquet(fdir / "texts.parquet", columns=["text_id", "file_id", "handle", "text", "normalized_text",
                                                            "bbox_min_x", "bbox_min_y", "bbox_max_x", "bbox_max_y"])
        tx["value"] = tx["normalized_text"].where(tx["normalized_text"].notna() & (tx["normalized_text"] != ""), tx["text"])
        tx["value"] = tx["value"].fillna("").astype(str)
        tx["cx"] = (tx.bbox_min_x + tx.bbox_max_x) / 2
        tx["cy"] = (tx.bbox_min_y + tx.bbox_max_y) / 2
        self.tx = tx
        self.lines = pd.read_parquet(fdir / "lines.parquet", columns=["file_id", "handle", "start_x", "start_y", "end_x", "end_y"])
        cl = pd.read_parquet(fdir / "sw_connect_labels.parquet", columns=["file_id", "text"])
        ids = set()
        for row in cl.itertuples():
            try:
                ids.add((row.file_id, json.loads(row.text).get("text_id")))
            except (TypeError, ValueError):
                pass
        self.connect_ids = ids

    def texts_near(self, file_id, x, y, radius):
        f = self.tx[self.tx.file_id == file_id]
        d = ((f.cx - x) ** 2 + (f.cy - y) ** 2) ** 0.5
        sel = f[d <= radius].assign(d=d[d <= radius]).sort_values("d")
        return sel

    def wire(self, file_id, handle):
        r = self.lines[(self.lines.file_id == file_id) & (self.lines.handle.astype(str) == str(handle))]
        if r.empty:
            return None
        r = r.iloc[0]
        return float(r.start_x), float(r.start_y), float(r.end_x), float(r.end_y)


def window(x, y, extra_pts=()):
    xs = [x] + [p[0] for p in extra_pts]
    ys = [y] + [p[1] for p in extra_pts]
    x0, x1 = min(xs) - PAD, max(xs) + PAD
    y0, y1 = min(ys) - PAD, max(ys) + PAD
    span = max(x1 - x0, y1 - y0)
    if span < 40:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x0, x1, y0, y1 = cx - 20, cx + 20, cy - 15, cy + 15
    return x0, y0, x1, y1


def make_panel(end: dict, tables: ProjectTables, dxf: str, label: str):
    fid = end["file_id"]
    x, y = float(end["x"]), float(end["y"])
    near = tables.texts_near(fid, x, y, R_NEAR)
    wire = tables.wire(fid, end["wire_handle"]) if end.get("wire_handle") else None
    pts = [(x, y)]
    if wire:
        pts += [(wire[0], wire[1]), (wire[2], wire[3])]
    x0, y0, x1, y1 = window(x, y, pts)
    boxes = []
    if wire:
        boxes.append((min(wire[0], wire[2]) - 0.6, min(wire[1], wire[3]) - 0.6,
                      max(wire[0], wire[2]) + 0.6, max(wire[1], wire[3]) + 0.6, "orange"))
    own_lines, conn_lines = [], []
    for _, t in near.iterrows():
        is_conn = (fid, t.text_id) in tables.connect_ids
        color = "magenta" if is_conn else "gold"
        boxes.append((t.bbox_min_x, t.bbox_min_y, t.bbox_max_x, t.bbox_max_y, color))
        (conn_lines if is_conn else own_lines).append(f"{t.value}({t.d:.1f})")
    header = [
        f"{label} {end['project']} file={fid} port={end['port_id'][-40:]}",
        f"身份={end['identity']} 类别={end['end_class']} 判定={end['verdict']} 详情={end.get('detail_text', '')}",
        f"橙=导线 绿=本端触点 金=本端近旁文字 洋红=接线去向标签",
        f"近旁本端文字(R<={R_NEAR}): {', '.join(own_lines) or '无'}",
        f"近旁接线标签: {', '.join(conn_lines) or '无'}",
    ]
    return r4.Panel(header, dxf_path=dxf, window=(x0, y0, x1, y1), boxes=boxes,
                    points=[(x, y, "lime")]), header


def pick(df: pd.DataFrame, n: int, rng: random.Random, key) -> pd.DataFrame:
    """Up to n rows, at most one per key value (diverse), then random fill."""
    rows = df.sample(frac=1.0, random_state=rng.randint(0, 10**6))
    seen, out = set(), []
    for _, r in rows.iterrows():
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
        if len(out) == n:
            break
    if len(out) < n:
        for _, r in rows.iterrows():
            if all(r.name != o.name for o in out):
                out.append(r)
            if len(out) == n:
                break
    return pd.DataFrame(out)


def main(scratch: Path, round_dir: Path, out_png: Path, out_json: Path) -> None:
    out_png.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    ends = pd.read_pickle(scratch / "ends.pkl")
    ends = ends[ends.geometry.fillna(False).astype(bool)].copy()
    ends["detail_text"] = ends.detail.map(lambda d: json.dumps(d, ensure_ascii=False) if isinstance(d, dict) and d else "")
    ends["wire_handle"] = ends.wire_handle.astype(str)
    dxfs = dxf_map()
    cache = r4.DxfCache()
    tables = {}

    def table(pid):
        if pid not in tables:
            tables[pid] = ProjectTables(fdir_of(round_dir, pid))
        return tables[pid]

    # (bucket key, filter, n, diversity key, title)
    plan = [
        ("G1_group_header_left", ends.verdict == "agree_group_header_left", 6,
         lambda r: (r.project, r.file_id, str(r.identity)[:9]),
         "agreement through a left-anchored group header (COM3 + cell 5)"),
        ("U1_unrelated_nearby", ends.verdict == "unrelated_text_nearby", 6,
         lambda r: (r.end_class, re.sub(r"\d", "9", str(r.identity))[:10]),
         "nearest identity-like text is unrelated"),
        ("C1_connect_only_differs", ends.verdict == "connect_only_differs", 6,
         lambda r: (r.end_class, str(r.identity)[:6], r.project),
         "no own text; only connect-label destination differs"),
        ("N1_unverifiable", ends.verdict == "unverifiable", 6,
         lambda r: (r.end_class, r.project),
         "no drawn text near the port"),
        ("R1_row_partial_connect_differs", (ends.verdict == "agree_row_partial") & ends.connect_near.map(lambda x: bool(x)), 4,
         lambda r: (r.project, r.file_id),
         "backplate row-only agreement with a differing connect label (supplement_03 type)"),
    ]
    manifest_rows = []
    counter = 0
    for bucket, mask, n, key, title in plan:
        sub = ends[mask]
        if bucket == "R1_row_partial_connect_differs":
            # ensure the supplement_03 port is present
            extra = sub[(sub.project == "p061") & (sub.port_id.str.contains("F0022:S0022:/9B07:/9B07:9863:532"))]
            sub = pd.concat([extra, sub]).drop_duplicates("port_id")
        picked = pick(sub, n, rng, key)
        panels, headers = [], []
        for _, r in picked.iterrows():
            counter += 1
            t = table(r.project)
            label = f"{bucket}-{counter:02d}"
            dxf = dxfs[r.project][r.file_id]
            panel, header = make_panel(r.to_dict(), t, dxf, label)
            panels.append(panel)
            headers.append(header)
            manifest_rows.append({"sample": label, "bucket": bucket, "project": r.project, "file_id": r.file_id,
                                  "port_id": r.port_id, "record_id": r.record_id, "wire": r.wire_handle,
                                  "identity": r.identity, "verdict": r.verdict, "end_class": r.end_class,
                                  "detail": r.detail_text, "connect_near": list(r.connect_near) if isinstance(r.connect_near, list) else [],
                                  "x": float(r.x), "y": float(r.y)})
        head = [f"{bucket}：{title}（本桶样例 {len(panels)} 例，共 {int(mask.sum())} 例）",
                "绿框=端口触点；金框=本端近旁文字；洋红=接线去向标签；橙=导线"]
        out = out_png / f"{bucket}.png"
        r4._render_issue_png(out, head, panels, cache)
        print("wrote", out.name, len(panels), flush=True)
    out_json.write_text(json.dumps(manifest_rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
