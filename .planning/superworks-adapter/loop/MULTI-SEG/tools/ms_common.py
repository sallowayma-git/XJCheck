"""MULTI-SEG shared loader (read-only). Reads a replay round's findings tables for every project.

Inputs: a replay root (default .tmp/superworks_round21_full) whose p*/<family>/findings/*.parquet hold the production
records. The device-internal module is the frozen reference copy .tmp/multiseg_src/superworks_device_internal_ref.py
(identical to src at the start of this slice), so the working tree can change without moving these numbers.
"""
from __future__ import annotations

import importlib.util
import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
ROUND = ROOT / ".tmp" / "superworks_round21_full"
MANIFEST = ROOT / ".planning" / "superworks-adapter" / "corpus_manifest.json"
REF_MODULE = ROOT / ".tmp" / "multiseg_src" / "superworks_device_internal_ref.py"

_spec = importlib.util.spec_from_file_location("sw_di_ref", str(REF_MODULE))
DI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DI)

PORT_TOL = 0.3  # contact-to-end-point tolerance used by the categoriser (drawing units)


def missing(value) -> bool:
    return value is None or (isinstance(value, float) and value != value)


def text(value) -> str:
    return "" if missing(value) else str(value).strip()


def jload(value, default):
    if missing(value):
        return default
    if isinstance(value, str):
        return json.loads(value or json.dumps(default))
    return value


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def manifest_info() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = {}
    for p in data["projects"]:
        out[p["project_id"]] = {"input_root": p["input_root"],
                                "files": {f["file_id"]: f for f in p["files"]}}
    return out


def project_dirs(round_root: Path = ROUND):
    for findings in sorted(round_root.glob("p*/*/findings")):
        yield findings.parent.parent.name, findings


class Project:
    """All tables of one project, as plain records, plus the per-file index used by the split replay."""

    def __init__(self, pid: str, findings: Path):
        self.pid = pid
        self.findings = findings
        rd = lambda n: pd.read_parquet(findings / f"{n}.parquet")  # noqa: E731
        self.ports = rd("sw_ports").to_dict("records")
        self.lines = rd("lines").to_dict("records")
        self.groups = rd("line_groups").to_dict("records")
        self.dots = rd("sw_connect_dots").to_dict("records")
        self.texts = rd("texts").to_dict("records")
        self.links = rd("sw_device_internal_links").to_dict("records")
        self.pairs = rd("pairs").to_dict("records")
        self.splits = rd("sw_terminal_splits").to_dict("records")
        self.unreg = rd("sw_unregistered_symb2").to_dict("records")
        self.routes = rd("sw_wire_routes").to_dict("records")
        self.port_by_id = {p["record_id"]: p for p in self.ports}
        self.line_by_key = {}
        for l in self.lines:
            self.line_by_key[(text(l["file_id"]), text(l["line_id"]))] = l

    def seg(self, file_id, line_id):
        l = self.line_by_key.get((file_id, line_id))
        if l is None:
            return None
        return {"file_id": file_id, "line_id": line_id, "handle": text(l["handle"]),
                "sx": float(l["start_x"]), "sy": float(l["start_y"]), "ex": float(l["end_x"]),
                "ey": float(l["end_y"]), "layer": text(l["layer"]), "block": text(l["source_block_name"]),
                "sheet_id": text(l["sheet_id"])}


def member_keys(group) -> list:
    members = jload(group.get("member_line_ids"), [])
    return [(text(group["file_id"]), text(m)) for m in members]


def enumerate_split_candidates(proj: Project):
    """Replays split_terminal_wires' candidate loop (same helpers, same order) and returns every examined pair.

    Each record: group index, the group's segment keys, end-point components, the two ports, contacts, reason
    (None when accepted), and the judged geometry. Used to reproduce the round21 counts exactly.
    """
    segments, handle_keys, model_segments = {}, defaultdict(list), defaultdict(list)
    for l in proj.lines:
        file_id, line_id = text(l["file_id"]), text(l["line_id"])
        coords = [DI._number(l.get(k)) for k in ("start_x", "start_y", "end_x", "end_y")]
        if not line_id or any(c is None for c in coords):
            continue
        handle = text(l["handle"])
        seg = {"file_id": file_id, "handle": handle, "sx": coords[0], "sy": coords[1], "ex": coords[2], "ey": coords[3]}
        segments[(file_id, line_id)] = seg
        if handle:
            handle_keys[(file_id, handle)].append((file_id, line_id))
        if not text(l.get("source_block_name")):
            model_segments[file_id].append(seg)
    groups = []
    for g in proj.groups:
        keys = list(dict.fromkeys(k for k in member_keys(g) if k in segments))
        if len(keys) >= 2:
            groups.append((g, keys))
    roots, members_of = [], defaultdict(list)
    for index, (g, keys) in enumerate(groups):
        roots.append(DI._end_point_components(keys, segments))
        for k in keys:
            members_of[k].append(index)
    dots = defaultdict(list)
    for d in proj.dots:
        x, y = DI._number(d.get("x")), DI._number(d.get("y"))
        if x is not None and y is not None:
            dots[text(d.get("file_id"))].append((x, y))
    contacts_in = defaultdict(list)
    for port in proj.ports:
        if text(port.get("category")) != DI.DEVICE_CATEGORY or not text(port.get("endpoint_identity")):
            continue
        file_id = text(port.get("file_id"))
        for contact in DI._contacts_of(port):
            handle = text(contact.get("wire_handle"))
            x, y = DI._number(contact.get("x")), DI._number(contact.get("y"))
            if not handle or x is None or y is None:
                continue
            for key in handle_keys.get((file_id, handle), ()):
                if not DI._at_endpoint(segments[key], (x, y)):
                    continue
                for index in members_of.get(key, ()):
                    contacts_in[index].append((port, handle, roots[index][key], (x, y)))
    out = []
    for index, items in contacts_in.items():
        g, keys = groups[index]
        comps = len(set(roots[index].values()))
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (a, ha, ra, ca), (b, hb, rb, cb) = items[i], items[j]
                if ra == rb or a.get("record_id") == b.get("record_id"):
                    continue
                if (a.get("file_id"), a.get("insert_handle")) != (b.get("file_id"), b.get("insert_handle")):
                    continue
                if text(a.get("endpoint_identity")).casefold() != text(b.get("endpoint_identity")).casefold():
                    continue
                file_id = text(a.get("file_id"))
                reason, geom = DI._judge_split(a, b, ca, cb, comps, file_id, dots, model_segments)
                out.append({"group_index": index, "line_group_id": text(g.get("line_group_id")), "file_id": file_id,
                            "sheet_id": text(g.get("sheet_id")), "orientation": text(g.get("orientation")),
                            "keys": keys, "components": comps, "roots": roots[index], "port_a": a, "port_b": b,
                            "handle_a": ha, "handle_b": hb, "ca": ca, "cb": cb, "root_a": ra, "root_b": rb,
                            "reason": reason, "geometry": geom or {}})
    return out, groups, roots, segments, model_segments, dots


def load_all(round_root: Path = ROUND):
    return [Project(pid, findings) for pid, findings in project_dirs(round_root)]
