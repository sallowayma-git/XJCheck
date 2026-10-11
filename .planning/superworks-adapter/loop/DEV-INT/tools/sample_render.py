"""DEV-INT visual sample: stratified draw of device-internal links and two-panel DXF renders (read-only).

Input: a links table (parquet, one row per link, from the production run or the explore harness), the round
findings directories (sw_ports, sw_symbols), and the frozen corpus manifest (DXF paths). Output: PNG sheets (two
samples per sheet, a wide and a tight panel each) and samples.json.

Marks: blue = device terminal marker and its wire contacts; magenta = internal element pin; red = wire contacts
of the element pin; green boxes = the two label texts. Titles carry identities, labels and the PCL evidence.
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


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _json(value, default):
    if isinstance(value, str):
        return json.loads(value or json.dumps(default))
    if value is None or (isinstance(value, float) and value != value):
        return default
    return value


def load_context(round_dir: Path, manifest_path: Path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dxf = {}
    for project in manifest["projects"]:
        for source in project["files"]:
            dxf[(project["project_id"], source["file_id"])] = source["dxf_path"]
    ports, symbols = {}, {}
    for findings in round_dir.glob("p*/*/findings"):
        project = findings.parent.parent.name
        for row in pd.read_parquet(findings / "sw_ports.parquet").to_dict("records"):
            ports[(project, row["record_id"])] = row
        for row in pd.read_parquet(findings / "sw_symbols.parquet").to_dict("records"):
            symbols[(project, row["file_id"], row["insert_handle"])] = row.get("block_name")
    return dxf, ports, symbols


def points_of(port):
    points = []
    for end in ("start", "end"):
        x, y = _num(port.get(f"{end}_x")), _num(port.get(f"{end}_y"))
        if x is not None and y is not None:
            points.append((x, y))
    contacts = []
    for contact in _json(port.get("wire_contacts"), []):
        x, y = _num(contact.get("x")), _num(contact.get("y"))
        if x is not None and y is not None:
            contacts.append((x, y))
    return points, contacts


def anchor_of(port):
    points, contacts = points_of(port)
    pts = points or contacts or [(0.0, 0.0)]
    return pts[0]


def draw_link(link, project, ports, symbols, dxf, family):
    device = ports[(project, link["port_id"])]
    element = ports[(project, link["element_port_id"])]
    d_marks, d_contacts = points_of(device)
    e_marks, e_contacts = points_of(element)
    label_boxes = []
    for owner in (device, element):
        label = _json(owner.get("label"), {}) or {}
        x, y, h = _num(label.get("x")), _num(label.get("y")), _num(label.get("height")) or 3.0
        if x is not None and y is not None:
            label_boxes.append((x - h / 2, y - h / 2, x + h / 2, y + h / 2, "green"))
    every = d_marks + d_contacts + e_marks + e_contacts + [(bx, by) for bx0, by0, bx1, by1, _ in label_boxes
                                                           for bx, by in ((bx0, by0), (bx1, by1))]
    xs = [x for x, _ in every]
    ys = [y for _, y in every]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    wide_half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 9
    dx, dy = anchor_of(device)
    tight_half = 7.0
    dev_block = symbols.get((project, device["file_id"], device["insert_handle"]))
    el_block = symbols.get((project, element["file_id"], element["insert_handle"]))
    dev_points = [(x, y, "blue") for x, y in d_marks + d_contacts]
    el_points = [(x, y, "magenta") for x, y in e_marks] + [(x, y, "red") for x, y in e_contacts]
    file_id = device["file_id"]
    pcl = bool(link["pcl_corroborated"])
    title_wide = [
        f"[{family}] {project} 文件 {file_id} 页 {device.get('sheet_id')}  导线 {link['wire_handle']}",
        f"装置端子（蓝） {link['endpoint_identity']}  块 {dev_block}  标签 {link['device_label']} 脚 {link['pin_tail']}",
        f"内部元件（品红） 标签 {link['element_label']} 引脚 {link['element_port_number']}  块 {el_block}",
        f"PCL 佐证 {pcl}",
    ]
    title_tight = ["紧邻视图", f"{link['link_id']}  PCL 佐证 {pcl}"]
    wide = r4.Panel(title_wide, dxf_path=dxf.get((project, file_id)),
                    window=(cx - wide_half, cy - wide_half, cx + wide_half, cy + wide_half),
                    points=dev_points + el_points, boxes=label_boxes)
    tight = r4.Panel(title_tight, dxf_path=dxf.get((project, file_id)),
                     window=(dx - tight_half, dy - tight_half, dx + tight_half, dy + tight_half),
                     points=dev_points + el_points, boxes=label_boxes)
    return [wide, tight]


def stratified(frame, n, seed):
    """Round-robin over (family, pcl, element block) strata, largest first, random within each stratum."""
    rng = random.Random(seed)
    groups = defaultdict(list)
    for index, row in frame.iterrows():
        groups[(row["family"], bool(row["pcl_corroborated"]), row["element_block"] or "?")].append(index)
    keys = sorted(groups, key=lambda k: (-len(groups[k]), str(k)))
    for key in keys:
        rng.shuffle(groups[key])
    picked = []
    while len(picked) < n and any(groups.values()):
        for key in keys:
            if groups[key] and len(picked) < n:
                picked.append(groups[key].pop())
    return frame.loc[picked]


# Visual verdicts recorded by the reviewer from the rendered sheets (wide and tight panels). Every sample is an
# internal connection (terminal wired to a pin of an internal element of its own device). "清晰" = both marks and
# the wire read at sheet scale; "小图" = legible only with the tight panel and the labels.
VERDICTS = {
    "S00": "小图", "S01": "小图", "S02": "清晰", "S03": "清晰", "S04": "清晰", "S05": "小图", "S06": "清晰",
    "S07": "小图", "S08": "小图", "S09": "清晰", "S10": "清晰", "S11": "清晰", "S12": "清晰", "S13": "小图",
    "S14": "小图", "S15": "清晰", "S16": "小图", "S17": "清晰", "S18": "清晰", "S19": "小图", "S20": "清晰",
    "S21": "清晰", "S22": "小图", "S23": "小图", "S24": "清晰", "S25": "清晰", "S26": "小图", "S27": "小图",
    "S28": "清晰", "S29": "清晰", "S30": "清晰", "S31": "小图", "S32": "清晰", "S33": "小图", "S34": "清晰",
    "S35": "小图", "S36": "清晰", "S37": "清晰", "S38": "小图", "S39": "小图", "S40": "清晰", "S41": "小图",
    "S42": "小图", "S43": "小图", "S44": "小图", "S45": "清晰", "S46": "清晰", "S47": "清晰",
}


def family_of(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = ROOT / "test"
    return {p["project_id"]: Path(p["input_root"]).relative_to(root).parts[0] for p in manifest["projects"]}


def main(links_path, round_dir, manifest_path, out_dir, n=48, seed=20261011):
    out_dir = Path(out_dir)
    (out_dir / "png").mkdir(parents=True, exist_ok=True)
    links = pd.read_parquet(links_path)
    dxf, ports, symbols = load_context(Path(round_dir), Path(manifest_path))
    links = links.assign(family=links.project.map(family_of(Path(manifest_path))))
    links = links.assign(element_block=[symbols.get((p, f, h)) for p, f, h in
                                        zip(links.project, links.file_id, links.element_insert_handle)])
    sample = stratified(links, n, seed)
    records = []
    rows = list(sample.iterrows())
    for sheet, start in enumerate(range(0, len(rows), 2)):
        panels, header = [], []
        for position in range(start, min(start + 2, len(rows))):
            link = rows[position][1]
            panels.extend(draw_link(link.to_dict(), link.project, ports, symbols, dxf, link.family))
            header.append(f"S{position:02d} {link.family} {link.project} {link.endpoint_identity} <- {link.element_label}")
            records.append({"sample": f"S{position:02d}", "sheet": f"DEVINT_{sheet + 1:02d}.png",
                            "link_id": link.link_id, "project": link.project, "family": link.family,
                            "port_id": link.port_id, "element_port_id": link.element_port_id,
                            "endpoint_identity": link.endpoint_identity, "device_label": link.device_label,
                            "element_label": link.element_label, "element_port_number": link.element_port_number,
                            "element_block": link.element_block,
                            "wire_handle": link.wire_handle, "pcl_corroborated": bool(link.pcl_corroborated),
                            "verdict": "内部连接（装置端子接本装置内部元件）", "clarity": VERDICTS.get(f"S{position:02d}")})
        r4._render_issue_png(out_dir / "png" / f"DEVINT_{sheet + 1:02d}.png",
                             ["DEV-INT 目视样例：装置端子 与 本装置内部元件（蓝/品红为两端标记）"] + header,
                             panels, r4.DxfCache())
    (out_dir / "samples.json").write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    return records


if __name__ == "__main__":
    links_path, round_dir, manifest_path, out_dir = sys.argv[1:5]
    records = main(links_path, round_dir, manifest_path, out_dir)
    print(len(records), "samples")
