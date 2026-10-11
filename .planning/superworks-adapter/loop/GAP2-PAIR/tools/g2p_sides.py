"""GAP2-PAIR side analysis (read-only).

Each population port P (2a/2b) sits on a union wire together with a partner port Q of the same identity
(the two SuperWORKS ports of one device terminal). The gap between P and Q is the terminal body. This script
splits the union at that gap and describes P's own side (the segment(s) away from Q): which ports lie on that side,
whether the side ends open, and what text and connect dots lie inside the gap.

Output: one row per population port, written to the given parquet.
Usage: python g2p_sides.py <pop.parquet> <out.parquet>
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
sys.path.insert(0, "F:/workspace/XJToolkit/src")
from dwg_audit.audit.superworks_device_internal import _label_of  # noqa: E402

BODY_TOL = 0.6
LATERAL_TOL = 4.0


def norm(s):
    return G.text(s).casefold()


def main(pop_path: Path, out: Path):
    pop = pd.read_parquet(pop_path)
    rows = []
    for proj in G.iter_projects(only=set(pop.project)):
        sub = pop[pop.project == proj.pid]
        texts = proj.texts.to_dict("records")
        dot_df = pd.read_parquet(proj.findings / "sw_connect_dots.parquet").to_dict("records")
        for r in sub.to_dict("records"):
            pl = json.loads(r["port_list"])
            me = next(p for p in pl if p["is_self"])
            partners = sorted([p for p in pl if not p["is_self"] and p["identity"] and p["identity"] == me["identity"]
                               and p["category"] in ("装置端子", "端子")], key=lambda p: abs(p["along"] - me["along"]))
            res = {"port_id": r["port_id"], "project": r["project"], "pop": r["pop"], "identity": me["identity"],
                   "n_wire_ports": r["n_wire_ports"], "n_partners": len(partners), "axis": r["wire_axis"]}
            if not partners:
                rows.append({**res, "side": "none"})
                continue
            q = partners[0]
            lo, hi = sorted([me["along"], q["along"]])
            res["gap_w"] = round(hi - lo, 3)
            # P's side: ports on the far side from Q relative to the gap
            if me["along"] <= q["along"]:
                side_ports = [p for p in pl if not p["is_self"] and p["along"] <= lo + BODY_TOL]
                side = "left"
            else:
                side_ports = [p for p in pl if not p["is_self"] and p["along"] >= hi - BODY_TOL]
                side = "right"
            if me["along"] == q["along"]:
                side = "coincident"
            res["side"] = side
            res["side_ports"] = json.dumps([{k: p[k] for k in ("port_id", "category", "identity", "port_number", "along")}
                                            for p in side_ports], ensure_ascii=False)
            # labels of side ports (device label of P vs the component label)
            lab = {}
            for p in side_ports:
                port = proj.port_by_id.get(p["port_id"]) or {}
                lbl, resolved = _label_of(port)
                lab[p["port_id"]] = {"label": lbl, "resolved": resolved, "insert": G.text(port.get("insert_handle"))}
            res["side_labels"] = json.dumps(lab, ensure_ascii=False)
            cats = sorted({p["category"] for p in side_ports})
            res["side_cats"] = "+".join(cats) if cats else "none"
            p_port = proj.port_by_id.get(me["port_id"]) or {}
            dev_label, dev_resolved = _label_of(p_port)
            res["device_label"] = dev_label if dev_resolved else ""
            res["same_insert_as_partner"] = G.text((proj.port_by_id.get(q["port_id"]) or {}).get("insert_handle")) == G.text(p_port.get("insert_handle"))
            res["partner_port_id"] = q["port_id"]
            res["partner_cat"] = q["category"]
            # text and dots inside the gap
            lat = me.get("y") if r["wire_axis"] == "x" else me.get("x")
            tl = [t for t in texts if t["sheet_id"] == r["sheet_id"]]
            hits = []
            for t in tl:
                if r["wire_axis"] == "x":
                    a0, a1, l0, l1 = t["bbox_min_x"], t["bbox_max_x"], t["bbox_min_y"], t["bbox_max_y"]
                else:
                    a0, a1, l0, l1 = t["bbox_min_y"], t["bbox_max_y"], t["bbox_min_x"], t["bbox_max_x"]
                if None in (a0, a1, l0, l1):
                    continue
                if a1 < lo - BODY_TOL or a0 > hi + BODY_TOL:
                    continue
                if l1 < lat - LATERAL_TOL or l0 > lat + LATERAL_TOL:
                    continue
                hits.append(G.text(t["normalized_text"]) or G.text(t["text"]))
            res["gap_texts"] = json.dumps(hits, ensure_ascii=False)
            res["gap_text_is_identity"] = any(norm(h) in (norm(me["identity"]), norm(dev_label)) for h in hits) if hits else False
            dhits = 0
            for d in dot_df:
                if d["sheet_id"] != r["sheet_id"]:
                    continue
                ax, ay = (d["x"], d["y"])
                along_d = ax if r["wire_axis"] == "x" else ay
                lat_d = ay if r["wire_axis"] == "x" else ax
                if lo - BODY_TOL <= along_d <= hi + BODY_TOL and abs(lat_d - lat) <= LATERAL_TOL:
                    dhits += 1
            res["gap_dots"] = dhits
            rows.append(res)
        print(proj.pid, len(sub), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_parquet(out, index=False)
    print("rows", len(frame))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
