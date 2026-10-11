"""GAP2-S visual sample (read-only; writes PNG and one JSON only).

Sample: 36 DEV-INT links added by the GAP2-S replay on the 10 review projects (split_reason = terminal_body).
Allocation: per project, proportional to its added links (largest remainder, every project with links gets at least
one), then seeded random choice (seed 20261011), within project stratified by PCL corroboration.
Each PNG holds two cases; each case has a wide view and a zoom on the terminal body (4 panels).
Overlays: device TERMPOINT (blue box), partner TERMPOINT of the other side (orange box), element pin (magenta square),
contact segments of device wire (blue), partner wire (orange), element wire (magenta); other model lines grey.
Usage: python g2s_visual.py RUN_ROOT PNG_DIR SAMPLE_JSON [SEED]
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

GAP_TOOLS = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")
sys.path.insert(0, str(GAP_TOOLS))
import gaplib as G  # noqa: E402
import gap_render as R  # noqa: E402

BLUE, ORANGE, MAGENTA, RED, GREY = "#1f78b4", "#ff7f00", "#e7298a", "#d7191c", "#9e9e9e"


def jload(value, default):
    if value is None or (isinstance(value, float) and value != value):
        return default
    return json.loads(value) if isinstance(value, str) else value


def findings_of(run_root: Path, pid: str) -> Path:
    return Path(json.loads((run_root / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"]) / "findings"


def allocate(counts: dict[str, int], total: int) -> dict[str, int]:
    """Largest-remainder allocation with at least one per project that has links."""
    alloc = {p: 1 for p in counts}
    left = total - len(alloc)
    weight = sum(counts.values())
    raw = {p: left * counts[p] / weight for p in counts}
    for p in counts:
        alloc[p] += int(raw[p])
    rest = total - sum(alloc.values())
    for p in sorted(counts, key=lambda p: raw[p] - int(raw[p]), reverse=True)[:rest]:
        alloc[p] += 1
    return alloc


def main(run_root: Path, png_dir: Path, sample_json: Path, seed: int) -> None:
    run = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
    pids = sorted({p["project_id"] for p in run["projects"]})
    links = []
    ports_by = {}
    lines_by = {}
    for pid in pids:
        fdir = findings_of(run_root, pid)
        if not (fdir / "sw_device_internal_links.parquet").exists():
            continue
        frame = pd.read_parquet(fdir / "sw_device_internal_links.parquet")
        added = [r for r in frame.to_dict("records") if r.get("split_reason") == "terminal_body"]
        if not added:
            continue
        ports = pd.read_parquet(fdir / "sw_ports.parquet")
        ports_by[pid] = {r["record_id"]: r for r in ports.to_dict("records")}
        lines = pd.read_parquet(fdir / "lines.parquet")
        lines_by[pid] = lines
        for r in added:
            r["project"] = pid
            r["pcl"] = bool(r.get("pcl_corroborated"))
            links.append(r)
    counts = defaultdict(int)
    for r in links:
        counts[r["project"]] += 1
    alloc = allocate(dict(counts), 36)
    rng = random.Random(seed)
    chosen = []
    for pid in sorted(alloc):
        pool = [r for r in links if r["project"] == pid]
        yes = sorted([r for r in pool if r["pcl"]], key=lambda r: r["link_id"])
        no = sorted([r for r in pool if not r["pcl"]], key=lambda r: r["link_id"])
        rng.shuffle(yes)
        rng.shuffle(no)
        want = alloc[pid]
        take_no = min(len(no), max(want // 2, want - len(yes)))
        take_yes = min(len(yes), want - take_no)
        take_no = min(len(no), want - take_yes)
        chosen += no[:take_no] + yes[:take_yes]
    chosen = chosen[:36]

    dxf_cache = G.manifest_map()[0]
    rows, cases = [], []
    for k, r in enumerate(chosen):
        pid = r["project"]
        ports = ports_by[pid]
        device = ports[r["port_id"]]
        element = ports.get(r.get("element_port_id")) if r.get("element_port_id") else None
        partner_id = (jload(r.get("split_partner_port_ids"), []) or [None])[0]
        partner = ports.get(partner_id) if partner_id else None
        lines = lines_by[pid]
        file_id = r["file_id"]
        cases.append({"index": k, "pid": pid, "sheet": r["sheet_id"], "file_id": file_id, "link": r, "device": device,
                      "element": element, "partner": partner, "lines": lines})
        rows.append({"case": k + 1, "project": pid, "sheet": r["sheet_id"], "link_id": r["link_id"],
                     "device_port": r["port_id"], "device_identity": r["endpoint_identity"],
                     "element_port": r.get("element_port_id"), "element_label": r.get("element_label"),
                     "element_port_number": r.get("element_port_number"), "partner_port": partner_id,
                     "wire_handle": r["wire_handle"], "pcl": r["pcl"], "source": r["source"],
                     "dxf_file": file_id})

    def handle_segments(lines_df, file_id, handles, colour, width):
        out = []
        sub = lines_df[(lines_df["file_id"] == file_id) & (lines_df["handle"].isin(list(handles)))]
        for seg in sub.itertuples():
            out.append((float(seg.start_x), float(seg.start_y), float(seg.end_x), float(seg.end_y), colour, width))
        return out

    def contacts_handles(port):
        return {str(c.get("wire_handle")) for c in jload(port.get("wire_contacts"), []) or []}

    panels_all = []
    png_index = []
    png_dir.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(cases), 2):
        pair = cases[start:start + 2]
        panels = []
        header = ["GAP2-S 目视样本：装置端子接本装置内部元件（新增 DEV-INT 链接）。蓝框=装置端子 TERMPOINT；橙框=另一侧端子 TERMPOINT；",
                  "品红方块=内部元件引脚；蓝线=装置端子所在导线段；橙线=另一侧导线段；品红线=元件导线段；灰=其它模型空间线。"]
        for c in pair:
            device, element, partner = c["device"], c["element"], c["partner"]
            dxf = dxf_cache.get((c["pid"], c["file_id"]))
            lines_df = c["lines"]
            def mid(port):
                return ((float(port["start_x"]) + float(port["end_x"])) / 2, (float(port["start_y"]) + float(port["end_y"])) / 2)

            dx, dy = mid(device)
            pts_common = [(dx, dy)] + ([mid(element)] if element is not None else []) + ([mid(partner)] if partner is not None else [])
            wide = R.window_around(pts_common, pad=8.0, min_size=24.0)
            zoom = R.window_around([(dx, dy)] + ([mid(partner)] if partner is not None else []), pad=2.5, min_size=8.0)
            dev_handles = contacts_handles(device)
            part_handles = contacts_handles(partner) if partner is not None else set()
            elem_handles = contacts_handles(element) if element is not None else set()
            segs = (handle_segments(lines_df, c["file_id"], dev_handles, BLUE, 2.2)
                    + handle_segments(lines_df, c["file_id"], part_handles, ORANGE, 2.2)
                    + handle_segments(lines_df, c["file_id"], elem_handles, MAGENTA, 2.2))
            boxes = [(float(device["start_x"]), float(device["start_y"]) - 0.3,
                      float(device["end_x"]), float(device["end_y"]) + 0.3, BLUE)]
            pts = [(dx, dy, BLUE)]
            if partner is not None:
                boxes.append((float(partner["start_x"]), float(partner["start_y"]) - 0.3,
                              float(partner["end_x"]), float(partner["end_y"]) + 0.3, ORANGE))
            if element is not None:
                pts.append((*mid(element), MAGENTA))
            title = [f"#{c['index'] + 1} {c['pid']} {c['sheet']}  {c['file_id']}",
                     f"装置端子 {device.get('endpoint_identity')} 端口 {device.get('port_number')} / 线 {r_handle(c)}",
                     f"元件 {c['link'].get('element_label')} 引脚 {c['link'].get('element_port_number')}  "
                     f"另一侧端子 {(partner or {}).get('endpoint_identity') or '-'}  PCL {'是' if c['link'].get('pcl_corroborated') else '否'}"]
            panels.append(R.Panel(title, dxf, wide, segs=segs, pts=pts, boxes=boxes))
            panels.append(R.Panel([f"#{c['index'] + 1} 近景（端子本体）"], dxf, zoom, segs=segs, pts=pts, boxes=boxes))
        name = f"G2S_{start // 2 + 1:02d}.png"
        R.render(png_dir / name, header, panels, cols=2)
        png_index.append({"png": name, "cases": [c["index"] + 1 for c in pair]})
        print("wrote", name, flush=True)
    sample_json.parent.mkdir(parents=True, exist_ok=True)
    sample_json.write_text(json.dumps({"seed": seed, "cases": rows, "png": png_index}, ensure_ascii=False, indent=1,
                                      default=str), encoding="utf-8")
    print("cases", len(rows))


def r_handle(c):
    return c["link"].get("wire_handle")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 20261011)
