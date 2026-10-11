"""Build the uncovered eligible-port table (one row per port not consumed_with_internal), read-only.

Output: <out>/uncovered.parquet, one row per uncovered eligible port with its wire signature, route note and the
line-group geometry of its first contact wire. The DEV-INT bucket keys are reproduced exactly so the counts can be
checked against stats_and_gaps.py (5144 / 2056 / 972 / 926 ...).

Usage: python build_table.py <out_dir>
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaplib as G  # noqa: E402
from dwg_audit.audit.superworks_device_internal import INTERNAL_CATEGORIES  # noqa: E402


def route_note(proj: G.Project, port, keys_of_wire) -> tuple[str, list]:
    routes = []
    for c in G.contacts_of(port):
        k = G.wire_key(proj, port["file_id"], str(c.get("wire_handle") or ""))
        routes.extend(proj.route_by_wire.get(k, []))
    if not routes:
        return "无路由记录", []
    ends = [e for r in routes for e in G.jload(r.get("ends_json"), [])]
    if any(e.get("category") == "接地" for e in ends):
        return "接地端", routes
    if any(e.get("far_source") == "cross_page" for e in ends):
        return "跨页远端", routes
    if all(int(r.get("end_count") or 0) < 2 for r in routes):
        return "单端记录(另一端未记录)", routes
    return "双端记录未准入", routes


def main(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    dxf, family, source = G.manifest_map()
    rows = []
    for proj in G.iter_projects():
        # wire membership: wire key -> ports (all categories) touching it
        wire_members = defaultdict(dict)
        for p in proj.ports.to_dict("records"):
            for c in G.contacts_of(p):
                h = str(c.get("wire_handle") or "")
                if h:
                    wire_members[G.wire_key(proj, p["file_id"], h)][p["record_id"]] = p
        proj.route_by_wire = defaultdict(list)
        for r in proj.routes.to_dict("records"):
            proj.route_by_wire[G.wire_key(proj, r["file_id"], str(r["wire_handle"]))].append(r)
        sym_block = {(r["file_id"], str(r["insert_handle"])): r.get("block_name") for r in proj.symbols.to_dict("records")}
        cov = proj.coverage[proj.coverage["eligible"].astype(bool) & ~proj.coverage["consumed_with_internal"].astype(bool)]
        for cr in cov.to_dict("records"):
            port = proj.port_by_id.get(cr["port_id"], {})
            other_ports = {}
            for c in G.contacts_of(port):
                h = str(c.get("wire_handle") or "")
                if not h:
                    continue
                k = G.wire_key(proj, port["file_id"], h)
                for oid, o in wire_members.get(k, {}).items():
                    if oid != port["record_id"]:
                        other_ports[oid] = o
            cats = set()
            for o in other_ports.values():
                cat = o.get("category") or "未分类"
                if cat in INTERNAL_CATEGORIES and not G.text(o.get("endpoint_identity")):
                    cat = f"{cat}(无身份)"
                cats.add(cat)
            signature = " + ".join(sorted(cats)) if cats else "悬空(无其它端口)"
            note, routes = route_note(proj, port, None)
            if cats:
                note = "-"
            # first contact wire geometry
            contacts = G.contacts_of(port)
            first = contacts[0] if contacts else {}
            fh = str(first.get("wire_handle") or "")
            k = G.wire_key(proj, port.get("file_id"), fh) if fh else None
            mem = proj.members.get(k, []) if k else []
            ends = []
            for l in mem:
                ends.append((float(l["start_x"]), float(l["start_y"])))
                ends.append((float(l["end_x"]), float(l["end_y"])))
            cx, cy = float(first.get("x", 0.0)), float(first.get("y", 0.0))
            far = max(ends, key=lambda e: G.dist(e, (cx, cy))) if ends else None
            grp = proj.group_by_key.get(k) if k else None
            rows.append({
                "project": proj.pid, "family": proj.family, "file_id": port["file_id"], "sheet_id": port.get("sheet_id"),
                "port_id": port["record_id"], "category": port.get("category"), "port_number": G.text(port.get("port_number")),
                "identity": G.text(port.get("endpoint_identity")), "label": G.label_norm(port),
                "block": sym_block.get((port["file_id"], str(port.get("insert_handle")))),
                "insert_handle": str(port.get("insert_handle")), "marker_handle": str(port.get("marker_handle")),
                "reason": (G.jload(cr.get("reason_codes"), []) or ["none"])[0],
                "signature": signature, "other_port_ids": sorted(other_ports), "route_note": note,
                "route_kinds": ",".join(sorted({str(r.get("source_kind")) for r in routes})),
                "route_end_counts": ",".join(str(int(r.get("end_count") or 0)) for r in routes),
                "n_contacts": len(contacts), "wire_handle": fh, "wire_key": str(k) if k else "",
                "contact_x": cx, "contact_y": cy, "wire_line_count": len(mem),
                "far_x": far[0] if far else None, "far_y": far[1] if far else None,
                "far_dist": G.dist(far, (cx, cy)) if far else None,
                "group_start_x": grp["start_x"] if grp is not None else None,
                "group_start_y": grp["start_y"] if grp is not None else None,
                "group_end_x": grp["end_x"] if grp is not None else None,
                "group_end_y": grp["end_y"] if grp is not None else None,
                "group_orientation": grp["orientation"] if grp is not None else None,
                "group_id": grp["line_group_id"] if grp is not None else "",
                "group_kind": ("GWSW" if str(grp["line_group_id"]).startswith("GWSW") else "legacy") if grp is not None else "none",
                "wire_in_group": bool(grp is not None),
                "wire_len_max": max((G.dist((float(l["start_x"]), float(l["start_y"])), (float(l["end_x"]), float(l["end_y"]))) for l in mem), default=None),
                "dxf": dxf.get((proj.pid, port["file_id"])),
            })
    frame = pd.DataFrame(rows)
    frame.to_parquet(out_dir / "uncovered.parquet", index=False)
    print("uncovered rows", len(frame))
    dev = frame[frame.category == "装置端子"]
    print(dev.groupby(["signature", "route_note"]).size().sort_values(ascending=False).head(12).to_string())
    print("eligible uncovered total", len(frame))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
