"""G1P visual sample: stratified draw of unregistered-pin device-internal links and negative decisions, two-panel renders.

Input: the replay output directory (findings of each project: sw_device_internal_links, sw_ports,
sw_unregistered_symb2, sw_unregistered_pin_decisions) and the frozen corpus manifest (DXF paths). Output: PNG sheets
(two samples per sheet, a wide and a tight panel each) and samples.json. Read-only: DXF files are opened, never written.

Marks: blue = device terminal contact on its wire; red = far end of the single-end wire; magenta = TERMPOINT end of the
unregistered block; green boxes = the device label text and the block label text.
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
_SPEC = importlib.util.spec_from_file_location("r4", str(ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"))
r4 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(r4)


def _json(value, default):
    if isinstance(value, str):
        return json.loads(value or json.dumps(default))
    if value is None or (isinstance(value, float) and value != value):
        return default
    return value


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def load_project_tables(findings: Path):
    ports = {r["record_id"]: r for r in pd.read_parquet(findings / "sw_ports.parquet").to_dict("records")}
    blocks = {r["record_id"]: r for r in pd.read_parquet(findings / "sw_unregistered_symb2.parquet").to_dict("records")}
    decisions = pd.read_parquet(findings / "sw_unregistered_pin_decisions.parquet")
    return ports, blocks, decisions


def label_box(doc, insert_handle: str):
    """Box of the block's own LD_SYMB2_LABEL text (model space); None when it is not drawn there."""
    insert = doc.entitydb.get(insert_handle)
    if insert is None or not insert.xdata or "LD_SYMB2_LABEL" not in insert.xdata.data:
        return None
    handles = [t.value for t in insert.xdata.data["LD_SYMB2_LABEL"] if t.code == 1005]
    if not handles:
        return None
    text = doc.entitydb.get(handles[0])
    if text is None or text.dxftype() not in ("TEXT", "MTEXT", "ATTRIB"):
        return None
    x, y = float(text.dxf.insert.x), float(text.dxf.insert.y)
    height = float((text.dxf.char_height if text.dxftype() == "MTEXT" else text.dxf.get("height", 3.0)) or 3.0)
    return (x - height / 2, y - height / 2, x + height / 2, y + height / 2, "green")


def device_label_box(port):
    label = _json(port.get("label"), {}) or {}
    x, y, h = _num(label.get("x")), _num(label.get("y")), _num(label.get("height")) or 3.0
    if x is None or y is None:
        return None
    return (x - h / 2, y - h / 2, x + h / 2, y + h / 2, "green")


def draw(link: dict, ports, blocks, cache, dxf_path, family: str, project: str, sample_tag: str):
    device = ports[link["port_id"]]
    block = blocks.get(link.get("element_block_record_id")) if link.get("element_block_record_id") else None
    contacts = [(_num(c.get("x")), _num(c.get("y"))) for c in _json(device.get("wire_contacts"), [])]
    contacts = [c for c in contacts if None not in c]
    far = (_num(link.get("far_x")), _num(link.get("far_y")))
    pin = (_num(link.get("pin_x")), _num(link.get("pin_y")))
    terms = []
    for term in _json(block.get("termpoints"), []) if block is not None else []:
        terms.append(tuple(term["a"]))
        terms.append(tuple(term["b"]))
    points = [(x, y, "blue") for x, y in contacts]
    if None not in far:
        points.append((far[0], far[1], "red"))
    points += [(x, y, "magenta") for x, y in terms]
    boxes = [b for b in (device_label_box(device),) if b]
    doc = cache.get(dxf_path)[0] if dxf_path else None
    if doc is not None and block is not None:
        box = label_box(doc, str(block.get("insert_handle")))
        if box:
            boxes.append(box)
    every = [(x, y) for x, y, _ in points] + [(bx, by) for b in boxes for bx, by in ((b[0], b[1]), (b[2], b[3]))]
    if not every:
        every = [(0.0, 0.0)]
    xs = [p[0] for p in every]
    ys = [p[1] for p in every]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    wide_half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 9
    anchor = contacts[0] if contacts else every[0]
    tight_half = 7.0
    title_wide = [
        f"[{family}] {project} 文件 {link['file_id']} 页 {link['sheet_id']}  导线 {link['wire_handle']}  {sample_tag}",
        f"装置端子（蓝） {link['endpoint_identity']}  标签 {link['device_label']}  脚 {link['pin_tail']}",
        f"未登记块 标签 {link['element_label']}  块句柄 {link['element_insert_handle']}  TERMPOINT 端（品红）",
        f"远端（红） 与块端距离 {_dist(far, pin):.3f}  来源 {link['source']}",
    ]
    title_tight = ["紧邻视图", f"{link['link_id']}"]
    wide = r4.Panel(title_wide, dxf_path=dxf_path, window=(cx - wide_half, cy - wide_half, cx + wide_half, cy + wide_half),
                    points=points, boxes=boxes)
    tight = r4.Panel(title_tight, dxf_path=dxf_path,
                     window=(anchor[0] - tight_half, anchor[1] - tight_half, anchor[0] + tight_half, anchor[1] + tight_half),
                     points=points, boxes=boxes)
    return [wide, tight]


def _pair_of(value):
    """(x, y) of a decision field stored as JSON text, or (None, None)."""
    try:
        x, y = _json(value, [None, None])[:2]
        return float(x), float(y)
    except (TypeError, ValueError):
        return None, None


def _dist(a, b):
    if None in a or None in b:
        return float("nan")
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def stratified(frame: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Round-robin over (family, project, station-prefixed label, block label family) strata, largest first."""
    rng = random.Random(seed)
    groups = defaultdict(list)
    for index, row in frame.iterrows():
        prefixed = "-" in str(row["device_label"])
        groups[(row["family"], row["project"], prefixed, str(row["element_label"])[:3])].append(index)
    keys = sorted(groups, key=lambda k: (-len(groups[k]), str(k)))
    for key in keys:
        rng.shuffle(groups[key])
    picked = []
    while len(picked) < n and any(groups.values()):
        for key in keys:
            if groups[key] and len(picked) < n:
                picked.append(groups[key].pop())
    return frame.loc[picked]


def main(replay: Path, manifest_path: Path, out_dir: Path, n_pos: int = 30, n_neg: int = 6, seed: int = 20261011):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "png").mkdir(exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    family = {p["project_id"]: Path(p["input_root"]).relative_to(ROOT / "test").parts[0] for p in manifest["projects"]}
    dxf = {(p["project_id"], s["file_id"]): s["dxf_path"] for p in manifest["projects"] for s in p["files"]}
    cache = r4.DxfCache()
    links, tables = [], {}
    for findings in sorted(replay.glob("p*/*/findings")):
        pid = findings.parent.parent.name
        frame = pd.read_parquet(findings / "sw_device_internal_links.parquet")
        frame = frame[frame.source == "unregistered_symb2_pin"].assign(project=pid)
        links.append(frame)
        tables[pid] = load_project_tables(findings)
    links = pd.concat(links, ignore_index=True)
    links = links.assign(family=links.project.map(family), element_label=links.element_label.fillna(""))
    pos = stratified(links, n_pos, seed)
    decisions = pd.concat([d.assign(project=p) for p, (_, _, d) in tables.items()], ignore_index=True)
    neg_frame = decisions[decisions.reason == "label_differs"].assign(family=lambda f: f.project.map(family))
    neg = neg_frame.sample(n=min(n_neg, len(neg_frame)), random_state=seed) if len(neg_frame) else neg_frame
    records = []
    rows = list(pos.iterrows())
    for sheet, start in enumerate(range(0, len(rows), 2)):
        panels, header = [], []
        for position in range(start, min(start + 2, len(rows))):
            link = rows[position][1]
            ports, blocks, _ = tables[link.project]
            dxf_path = dxf.get((link.project, link.file_id))
            tag = f"S{position:02d}"
            panels.extend(draw(link.to_dict(), ports, blocks, cache, dxf_path, link.family, link.project, tag))
            header.append(f"{tag} {link.family} {link.project} {link.endpoint_identity} <- {link.element_label}")
            records.append({"sample": tag, "sheet": f"G1P_{sheet + 1:02d}.png", "kind": "positive",
                            "link_id": link.link_id, "project": link.project, "family": link.family,
                            "file_id": link.file_id, "port_id": link.port_id, "endpoint_identity": link.endpoint_identity,
                            "device_label": link.device_label, "element_label": link.element_label,
                            "element_block_record_id": link.element_block_record_id,
                            "element_insert_handle": link.element_insert_handle, "wire_handle": link.wire_handle})
        r4._render_issue_png(out_dir / "png" / f"G1P_{sheet + 1:02d}.png",
                             ["G1P 目视样例：装置端子 单端导线 止于 未登记 SYMB2 块的 TERMPOINT（标签一致，建覆盖）",
                              "蓝 = 装置端子导线接点；红 = 单端导线远端；品红 = 未登记块 TERMPOINT 端；绿框 = 标签文字"]
                             + header, panels, cache)
    base = len(records) // 2 + (1 if len(records) % 2 else 0)
    neg_rows = list(neg.iterrows())
    for sheet, start in enumerate(range(0, len(neg_rows), 2)):
        panels, header = [], []
        for position in range(start, min(start + 2, len(neg_rows))):
            decision = neg_rows[position][1]
            far = _pair_of(decision.far)
            pin = _pair_of(decision.pin)
            ports, blocks, _ = tables[decision.project]
            link_like = {"port_id": decision.port_id, "file_id": decision.file_id, "sheet_id": decision.sheet_id,
                         "endpoint_identity": decision.endpoint_identity, "device_label": decision.device_label,
                         "element_label": decision.block_label, "element_insert_handle": decision.block_insert_handle,
                         "element_block_record_id": decision.block_record_id, "wire_handle": decision.wire_handle,
                         "link_id": f"NEG:{decision.port_id}", "pin_tail": "", "source": "label_differs (negative)",
                         "far_x": far[0], "far_y": far[1], "pin_x": pin[0], "pin_y": pin[1]}
            tag = f"N{position:02d}"
            dxf_path = dxf.get((decision.project, decision.file_id))
            panels.extend(draw(link_like, ports, blocks, cache, dxf_path, decision.family, decision.project, tag))
            header.append(f"{tag} {decision.family} {decision.project} 装置标签 {decision.device_label} 块标签 {decision.block_label}")
            records.append({"sample": tag, "sheet": f"G1P_{base + sheet + 1:02d}.png", "kind": "negative_label_differs",
                            "project": decision.project, "family": decision.family, "file_id": decision.file_id,
                            "port_id": decision.port_id, "device_label": decision.device_label,
                            "element_label": decision.block_label, "element_insert_handle": decision.block_insert_handle,
                            "wire_handle": decision.wire_handle})
        r4._render_issue_png(out_dir / "png" / f"G1P_{base + sheet + 1:02d}.png",
                             ["G1P 负例：装置端子 单端导线 止于 标签不同的 未登记块（应不建链）"] + header,
                             panels, cache)
    (out_dir / "samples.json").write_text(json.dumps(records, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return records


if __name__ == "__main__":
    replay, manifest, out = (Path(p) for p in sys.argv[1:4])
    recs = main(replay, manifest, out)
    print(len(recs), "samples")
