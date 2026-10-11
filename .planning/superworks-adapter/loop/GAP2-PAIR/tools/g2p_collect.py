"""GAP2-PAIR population collector (read-only).

For every uncovered eligible device terminal of signature 2a (internal + terminal + device terminal) or 2b
(terminal + device terminal) it gathers: all ports on the same wire (union of line groups), the position of each
port along the wire, whether the port sits at a wire extreme, the coverage observations of the port, and the
non-discard pairs that touch the wire. Output: one row per port.

Usage: python g2p_collect.py <base_dir_with_uncovered.parquet> <out_parquet>
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

GAP_TOOLS = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")
sys.path.insert(0, str(GAP_TOOLS))
import gaplib as G  # noqa: E402

POP = {"内部元件(无身份) + 端子 + 装置端子": "2a", "端子 + 装置端子": "2b"}
EXT_TOL = 1.0


def axis_of(members):
    xs = [v for l in members for v in (l["start_x"], l["end_x"])]
    ys = [v for l in members for v in (l["start_y"], l["end_y"])]
    return ("x", xs, ys) if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else ("y", xs, ys)


def pair_sides(pr):
    ev = G.jload(pr.get("evidence"), {}) or {}
    sw = ev.get("superworks") or {}
    out = {}
    for side in ("left", "right"):
        for pid in (sw.get(side) or {}).get("port_ids") or []:
            out.setdefault(pid, []).append(side)
    return out


def main(base: Path, out: Path):
    unc = pd.read_parquet(base / "uncovered.parquet")
    unc = unc[(unc.category == "装置端子") & unc.signature.isin(POP.keys())]
    rows = []
    for proj in G.iter_projects():
        sub = unc[unc.project == proj.pid]
        if sub.empty:
            continue
        pairs = pd.read_parquet(proj.findings / "pairs.parquet").to_dict("records")
        cov = {r["port_id"]: r for r in proj.coverage.to_dict("records")}
        wire_ports = defaultdict(dict)
        for p in proj.ports.to_dict("records"):
            for c in G.contacts_of(p):
                h = str(c.get("wire_handle") or "")
                if h:
                    wire_ports[G.wire_key(proj, p["file_id"], h)][p["record_id"]] = (p, c)
        wire_groups = defaultdict(list)
        handle_of = {(G.text(l["file_id"]), G.text(l["line_id"])): G.text(l["handle"]) for l in proj.lines.to_dict("records")}
        for g in proj.groups.to_dict("records"):
            keys = set()
            for lid in G.jload(g.get("member_line_ids"), []):
                hd = handle_of.get((G.text(g["file_id"]), G.text(lid)))
                if hd is not None:
                    keys.add(G.wire_key(proj, G.text(g["file_id"]), hd))
            for k in keys:
                wire_groups[k].append(g)
        pair_by_group = defaultdict(list)
        pair_by_port = defaultdict(list)
        for pr in pairs:
            pair_by_group[pr["line_group_id"]].append(pr)
            for pid, sides in pair_sides(pr).items():
                pair_by_port[pid].append((pr, sides))
        for r in sub.to_dict("records"):
            port = proj.port_by_id.get(r["port_id"]) or {}
            if not port:
                continue
            contacts = G.contacts_of(port)
            keys = {G.wire_key(proj, port["file_id"], str(c.get("wire_handle") or "")) for c in contacts if c.get("wire_handle")}
            members = []
            for k in keys:
                members.extend(proj.members.get(k, []))
            if not members:
                rows.append({**r, "n_wire_ports": 0, "note": "no_members"})
                continue
            ax, xs, ys = axis_of(members)
            vals = xs if ax == "x" else ys
            lo, hi = min(vals), max(vals)
            port_list, seen = [], set()
            for k in keys:
                for pid, (p, c) in wire_ports.get(k, {}).items():
                    if pid in seen:
                        continue
                    seen.add(pid)
                    cx, cy = float(c.get("x", 0.0)), float(c.get("y", 0.0))
                    a = cx if ax == "x" else cy
                    port_list.append({"port_id": pid, "category": p.get("category") or "未分类",
                                      "identity": G.text(p.get("endpoint_identity")), "port_number": G.text(p.get("port_number")),
                                      "x": cx, "y": cy, "along": a,
                                      "at_extreme": bool(min(abs(a - lo), abs(a - hi)) <= EXT_TOL),
                                      "is_self": pid == r["port_id"]})
            port_list.sort(key=lambda d: d["along"])
            wg = []
            for k in keys:
                wg.extend(wire_groups.get(k, []))
            seg_groups = [{"gid": g["line_group_id"], "start": [g["start_x"], g["start_y"]], "end": [g["end_x"], g["end_y"]],
                           "orientation": g["orientation"],
                           "origin": "gwsw" if str(g["line_group_id"]).startswith("GWSW") else "legacy",
                           "n_members": len(G.jload(g.get("member_line_ids"), []))} for g in wg]
            c = cov.get(r["port_id"], {})
            obs = G.jload(c.get("wire_group_observations"), []) or []
            reasons = G.jload(c.get("reason_codes"), []) or []
            found = {}
            for d in port_list:
                for pr, sides in pair_by_port.get(d["port_id"], []):
                    found[pr["pair_id"]] = {"pair_id": pr["pair_id"], "status": pr["status"], "pair_kind": pr.get("pair_kind"),
                                            "line_group_id": pr["line_group_id"], "left": pr.get("left_value"),
                                            "right": pr.get("right_value"), "port_ids_hit": d["port_id"], "sides": sides}
            for sg in seg_groups:
                for pr in pair_by_group.get(sg["gid"], []):
                    found.setdefault(pr["pair_id"], {"pair_id": pr["pair_id"], "status": pr["status"],
                                                     "pair_kind": pr.get("pair_kind"), "line_group_id": sg["gid"],
                                                     "left": pr.get("left_value"), "right": pr.get("right_value"),
                                                     "port_ids_hit": None, "sides": []})
            rows.append({**r, "n_wire_ports": len(port_list), "port_list": json.dumps(port_list, ensure_ascii=False),
                         "wire_axis": ax, "wire_lo": lo, "wire_hi": hi,
                         "self_at_extreme": next((d["at_extreme"] for d in port_list if d["is_self"]), None),
                         "n_wire_groups": len(seg_groups), "groups_json": json.dumps(seg_groups, ensure_ascii=False),
                         "obs_json": json.dumps(obs, ensure_ascii=False), "n_obs": len(obs),
                         "reason_codes": json.dumps(reasons, ensure_ascii=False),
                         "pairs_json": json.dumps(list(found.values()), ensure_ascii=False),
                         "n_members": len(members), "note": ""})
        print(proj.pid, len(sub), flush=True)
    frame = pd.DataFrame(rows)
    frame["pop"] = frame.signature.map(POP)
    frame.to_parquet(out, index=False)
    print("rows", len(frame), frame["pop"].value_counts().to_dict())


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
