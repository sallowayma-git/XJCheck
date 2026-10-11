"""Render DXF close-ups for LOGGEN samples (read-only).

Usage: python render_loggen.py <eval_dir> <replay_dir> <out_dir>
Panels reuse the round4 drawing helpers. Marks: orange box = the record wire (LINE bbox);
green = end 0 contact, blue = end 1 contact (far end, may sit on another page).
Samples: conflicts (all), supplement (stratified), strict potentials (a few).
"""
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
SPEC = importlib.util.spec_from_file_location("r4", str(ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"))
r4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r4)

PROJECTS = ["p001", "p003", "p022", "p044", "p050", "p051", "p061", "p071", "p075", "p076"]
MANIFEST = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))


def dxf_map(pid):
    project = next(p for p in MANIFEST["projects"] if p["project_id"] == pid)
    return {f["file_id"]: f["dxf_path"] for f in project["files"]}


def findings_dir(replay, pid):
    return Path(json.loads((replay / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"]) / "findings"


def fnum(value):
    try:
        x = float(value)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


class Geometry:
    def __init__(self, fdir):
        self.lines = pd.read_parquet(fdir / "lines.parquet", columns=["file_id", "handle", "start_x", "start_y", "end_x", "end_y"])
        self.ports = pd.read_parquet(fdir / "sw_ports.parquet", columns=["file_id", "insert_handle", "port_number", "start_x", "start_y", "end_x", "end_y"])
        self.parts = pd.read_parquet(fdir / "sw_part_instances.parquet", columns=["file_id", "insert_handle", "ports"])
        self.part_port = {}
        for row in self.parts.itertuples():
            try:
                ports = json.loads(row.ports) if isinstance(row.ports, str) else (row.ports or [])
            except Exception:
                ports = []
            for port in ports:
                self.part_port[(row.file_id, str(row.insert_handle), str(port.get("port_number")))] = port
        self.port_index = {(r.file_id, str(r.insert_handle), str(r.port_number)): r for r in self.ports.itertuples()}
        self.line_index = {(r.file_id, str(r.handle)): r for r in self.lines.itertuples()}

    def wire(self, file_id, handle):
        row = self.line_index.get((file_id, str(handle)))
        if row is None:
            return None
        return (fnum(row.start_x), fnum(row.start_y), fnum(row.end_x), fnum(row.end_y))

    def contact(self, file_id, handle, port):
        key = (file_id, str(handle), str(port))
        row = self.port_index.get(key)
        if row is not None:
            x = (fnum(row.start_x) + fnum(row.end_x)) / 2
            y = (fnum(row.start_y) + fnum(row.end_y)) / 2
            return x, y
        part = self.part_port.get(key)
        if part is not None:
            sx, sy, ex, ey = (fnum(part.get(k)) for k in ("start_x", "start_y", "end_x", "end_y"))
            if None not in (sx, sy, ex, ey):
                return (sx + ex) / 2, (sy + ey) / 2
        return None


def wire_window(wire, points, pad=14.0):
    xs = [wire[0], wire[2]] + [p[0] for p in points]
    ys = [wire[1], wire[3]] + [p[1] for p in points]
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    span = max(x1 - x0, y1 - y0)
    if span < 40:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x0, x1, y0, y1 = cx - 20, cx + 20, cy - 20, cy + 20
    return x0, y0, x1, y1


def build_panels(pid, sample, geo, files, label):
    """One panel for the record page (wire + end 0) and one per end on another page (its own DXF)."""
    file_id = sample["file_id"]
    wire = geo.wire(file_id, sample["wire"]) if sample.get("wire") else None
    ends = sample.get("ends") or [
        {"terminal_handle": sample.get("terminal"), "port_number": sample.get("port"), "file_id": sample.get("end_file"),
         "identity": sample.get("identity"), "role": "END"}
    ]
    main_points, other = [], []
    for index, end in enumerate(ends[:2]):
        if not end.get("terminal_handle"):
            continue
        end_file = end.get("file_id") or file_id
        xy = geo.contact(end_file, end["terminal_handle"], end.get("port_number"))
        if xy is None:
            continue
        color = "green" if index == 0 else "blue"
        if end_file == file_id:
            main_points.append((xy[0], xy[1], color))
        else:
            other.append((index, end_file, xy, end))
    panels = []
    header = [
        f"[{label}] {pid} file={file_id} {sample.get('source_kind', sample.get('kind', ''))} record={sample['record_id']}",
        f"wire={sample.get('wire')} 线型={sample.get('linestyle', '')}",
    ]
    for index, end in enumerate(ends[:2]):
        header.append(f"端{index}: 端子={end.get('terminal_handle')} 端口={end.get('port_number')} "
                      f"设备={end.get('device', '')} 身份={end.get('identity')} 状态={end.get('status', '')}")
    if "pair_id" in sample:
        header.append(f"生产配对 {sample['pair_id']} 状态={sample['pair_status']} 侧={sample['side']} "
                      f"侧值={sample['pair_value']} 类型={sample['pair_kind']}")
    if wire is None and main_points:
        wire = (main_points[0][0], main_points[0][1], main_points[0][0], main_points[0][1])
    if wire is not None and files.get(file_id):
        pts = [(x, y) for x, y, _ in main_points]
        x0, y0, x1, y1 = wire_window(wire, pts)
        boxes = [(min(wire[0], wire[2]) - 1.2, min(wire[1], wire[3]) - 1.2,
                  max(wire[0], wire[2]) + 1.2, max(wire[1], wire[3]) + 1.2, "orange")]
        panels.append(r4.Panel(header + ["主页：橙框=导线，绿=端0（本页）"], dxf_path=files[file_id],
                               window=(x0, y0, x1, y1), boxes=boxes, points=main_points))
    for index, end_file, xy, end in other:
        if not files.get(end_file):
            continue
        panels.append(r4.Panel([f"端{index} 位于目标页 file={end_file}: 端子={end['terminal_handle']} 端口={end.get('port_number')} "
                                f"身份={end.get('identity')} 状态={end.get('status', '')}", "蓝=该端在目标页上的触点"],
                               dxf_path=files[end_file], window=(xy[0] - 14, xy[1] - 10, xy[0] + 14, xy[1] + 10),
                               points=[(xy[0], xy[1], "blue")]))
    return panels


def render(out_png, header, panels, cache):
    r4._render_issue_png(out_png, header, [p for p in panels if p is not None], cache)


def main(eval_dir: Path, replay: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    cache = r4.DxfCache()
    conflicts, supplements, potentials = [], [], []
    for pid in PROJECTS:
        d = json.loads((eval_dir / f"{pid}.json").read_text(encoding="utf-8"))
        conflicts += [dict(s, project=pid) for s in d["conflict_samples"]]
        supplements += [dict(s, project=pid) for s in d["supplement_samples"]]
        potentials += [dict(s, project=pid) for s in d["strict_samples"]]
    rng = random.Random(20260710)

    # Conflicts: all of them (8 in the ten-project sample).
    for index, s in enumerate(conflicts, 1):
        fdir = findings_dir(replay, s["project"])
        geo = Geometry(fdir)
        files = dxf_map(s["project"])
        panels = build_panels(s["project"], s, geo, files, f"冲突{index}")
        if not panels:
            continue
        render(out / f"conflict_{index:02d}_{s['project']}_{s['wire']}.png",
               [f"冲突 {index}: 记录端身份 {s['identity']} 与生产配对侧值 {s['pair_value']} 不一致",
                f"配对 {s['pair_id']} 状态 {s['pair_status']} 类型 {s['pair_kind']} 侧 {s['side']}"],
               panels, cache)

    # Supplement: stratified (klass x category) draw of 10.
    buckets = {}
    for s in supplements:
        key = (s["klass"], "-".join(sorted(s["cats"])))
        buckets.setdefault(key, []).append(s)
    plan = [
        ("no_active_end", "内部元件-装置端子", 2), ("no_active_end", "内部元件-端子", 2),
        ("no_active_end", "端子-端子", 2), ("no_active_end", "内部元件-未分类", 1),
        ("one_end_active", "内部元件-端子", 2), ("one_end_active", "内部元件-装置端子", 1),
    ]
    chosen = []
    for klass, cats, n in plan:
        pool = buckets.get((klass, cats), [])
        pool = sorted(pool, key=lambda s: (s["project"], s["record_id"]))
        chosen += [("补充", s) for s in rng.sample(pool, min(n, len(pool)))]
    chosen = chosen[:10]
    for index, (label, s) in enumerate(chosen, 1):
        fdir = findings_dir(replay, s["project"])
        geo = Geometry(fdir)
        files = dxf_map(s["project"])
        s = dict(s, sheet_id=s.get("sheet_id"))
        panels = build_panels(s["project"], s, geo, files, f"{label}{index}")
        if not panels:
            continue
        render(out / f"supplement_{index:02d}_{s['project']}_{s['wire']}.png",
               [f"补充 {index}: 记录两端均解析、无单一生产配对覆盖两端（{s['klass']}，端类别 {'/'.join(s['cats'])}，{s['wire_state']}）",
                f"记录 {s['record_id']} 导线 {s['wire']}"],
               panels, cache)

    # Strict potentials: a few, to confirm the uplift is a real physical connection.
    rng2 = random.Random(7)
    for index, s in enumerate(rng2.sample(potentials, min(4, len(potentials))), 1):
        fdir = findings_dir(replay, s["project"])
        geo = Geometry(fdir)
        files = dxf_map(s["project"])
        xy = geo.contact(s["file_id"], s["insert"], s["port"])
        if xy is None:
            continue
        wire_handle = None
        panel = r4.Panel([f"严格口径潜在 {index}: {s['project']} {s['file_id']} 端口 {s['insert']}:{s['port']} 身份 {s['identity']} 类别 {s['category']}"],
                         dxf_path=files.get(s["file_id"]),
                         window=(xy[0] - 16, xy[1] - 12, xy[0] + 16, xy[1] + 12),
                         points=[(xy[0], xy[1], "green")])
        render(out / f"strict_potential_{index:02d}_{s['project']}_{s['insert']}_{s['port']}.png",
               [f"严格口径潜在提升 {index}: 未消费端口 {s['identity']} 与一条两端已解析的导线记录一致"], [panel], cache)
    print("rendered", out, flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
