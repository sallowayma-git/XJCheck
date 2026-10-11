"""GAP (uncovered-port classification) shared loader, read-only.

Reads the round replay findings (.tmp/superworks_round19_full/p*/<family>/findings/*.parquet) and the frozen corpus
manifest. Builds, per project, the SuperWORKS wire key of every LINE (line-group union, as the production device-internal
module does), the wire members (lines, ports, route rows) and the eligible-port coverage row.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
ROUND = ROOT / ".tmp" / "superworks_round19_full"
MANIFEST = ROOT / ".planning" / "superworks-adapter" / "corpus_manifest.json"
sys.path.insert(0, str(ROOT / "src"))
from dwg_audit.audit.superworks_device_internal import INTERNAL_CATEGORIES, wire_keys_from_lines  # noqa: E402

TERMINAL_CATS = ("端子", "装置端子")


def is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and value != value)


def jload(value, default):
    if is_missing(value):
        return default
    if isinstance(value, str):
        return json.loads(value or json.dumps(default))
    return value


def text(value) -> str:
    return "" if is_missing(value) else str(value).strip()


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def manifest_map():
    """(project_id, file_id) -> frozen DXF path, and project_id -> family (top-level test folder)."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dxf, family, source = {}, {}, {}
    for project in data["projects"]:
        pid = project["project_id"]
        family[pid] = Path(project["input_root"]).relative_to(ROOT / "test").parts[0]
        for f in project["files"]:
            dxf[(pid, f["file_id"])] = f["dxf_path"]
            source[(pid, f["file_id"])] = f["path"]
    return dxf, family, source


@dataclass
class Project:
    pid: str
    family: str
    findings: Path
    ports: pd.DataFrame
    coverage: pd.DataFrame
    lines: pd.DataFrame
    groups: pd.DataFrame
    routes: pd.DataFrame
    symbols: pd.DataFrame
    texts: pd.DataFrame
    keys: dict = field(default_factory=dict)          # (file_id, handle) -> wire key
    members: dict = field(default_factory=dict)       # wire key -> list of line dicts
    group_by_key: dict = field(default_factory=dict)  # wire key -> line group dict (or None)
    port_by_id: dict = field(default_factory=dict)


def load_project(findings: Path, pid: str, family: str) -> Project:
    rd = lambda n: pd.read_parquet(findings / f"{n}.parquet")  # noqa: E731
    ports = rd("sw_ports")
    coverage = rd("sw_port_coverage")
    lines = rd("lines")
    groups = rd("line_groups")
    routes = rd("sw_wire_routes")
    symbols = rd("sw_symbols")
    texts = rd("texts")
    keys = wire_keys_from_lines(lines.to_dict("records"), groups.to_dict("records"))
    members = defaultdict(list)
    for line in lines.to_dict("records"):
        key = keys.get((text(line["file_id"]), text(line["handle"])), (text(line["file_id"]), text(line["handle"])))
        members[key].append(line)
    # keys are indexed by (file_id, handle); group members are line_ids, so map line_id -> handle first
    handle_of = {(text(l["file_id"]), text(l["line_id"])): text(l["handle"]) for l in lines.to_dict("records")}
    group_by_key = {}
    for g in groups.to_dict("records"):
        members_list = jload(g.get("member_line_ids"), [])
        if members_list:
            fid = text(g["file_id"])
            hd = handle_of.get((fid, text(members_list[0])))
            if hd is not None:
                group_by_key[keys.get((fid, hd), (fid, hd))] = g
    return Project(pid, family, findings, ports, coverage, lines, groups, routes, symbols, texts, keys, dict(members),
                   group_by_key, {p["record_id"]: p for p in ports.to_dict("records")})


def iter_projects(round_dir: Path = ROUND, only=None):
    _, family, _ = manifest_map()
    for findings in sorted(round_dir.glob("p*/*/findings")):
        pid = findings.parent.parent.name
        if only and pid not in only:
            continue
        yield load_project(findings, pid, family.get(pid, "unknown"))


def wire_key(proj: Project, file_id: str, handle: str):
    return proj.keys.get((file_id, handle), (file_id, handle))


def contacts_of(port) -> list:
    return jload(port.get("wire_contacts"), [])


def label_norm(port) -> str:
    return text(jload(port.get("label"), {}).get("normalized"))
