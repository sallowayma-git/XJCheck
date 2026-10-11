"""GAP2-PAIR stratified case sampling, DXF renders and per-case details (read-only; writes PNG and JSON only).

Sample: 2a = 10 (internal_same_label 6, internal_label_unresolved 2, multi_or_other 2);
        2b = 10 (side_open 6, multi_or_other 3, no_partner 1). Seed 20261011.
Each PNG holds two cases, each with a wide view and a zoom on the terminal body gap (2 cases x 2 panels).
Usage: python g2p_render.py <classes.parquet> <png_dir> <details.json>
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

GAP_TOOLS = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")
G2_TOOLS = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP2-PAIR/tools")
sys.path.insert(0, str(GAP_TOOLS))
sys.path.insert(0, str(Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")))
import gaplib as G  # noqa: E402
import gap_render as R  # noqa: E402

SEED = 20261011
QUOTA = {("2a", "internal_same_label"): 6, ("2a", "internal_label_unresolved"): 2, ("2a", "multi_or_other"): 2,
         ("2b", "side_open"): 6, ("2b", "multi_or_other"): 3, ("2b", "no_partner"): 1}
COL = {"装置端子": "#1a9850", "端子": "#7b3294", "内部元件": "#777777", "线圈": "#777777"}


def pick(cls: pd.DataFrame):
    rng = random.Random(SEED)
    chosen = []
    for (pop, sc), n in QUOTA.items():
        pool = cls[(cls["pop"] == pop) & (cls["side_class"] == sc)].sort_values("port_id")
        idx = list(pool.index)
        rng.shuffle(idx)
        for i in idx[:n]:
            chosen.append((pop, sc, i))
    return chosen


def case_geometry(proj, row):
    """Member segments of the port's wire (union of its contacts' wire keys) and the wire's texts."""
    keys = {G.wire_key(proj, row["file_id"], str(c.get("wire_handle") or "")) for c in G.contacts_of(proj.port_by_id[row["port_id"]])}
    segs = []
    for k in keys:
        for l in proj.members.get(k, []):
            segs.append((float(l["start_x"]), float(l["start_y"]), float(l["end_x"]), float(l["end_y"]), l["layer"]))
    return segs


def main(cls_path: Path, png_dir: Path, details_path: Path):
    cls = pd.read_parquet(cls_path)
    chosen = pick(cls)
    sel = cls.loc[[i for _, _, i in chosen]].copy()
    sel["sample_pop"] = [p for p, _, _ in chosen]
    sel["sample_class"] = [s for _, s, _ in chosen]
    pids = set(sel.project)
    projs = {p.pid: p for p in G.iter_projects(only=pids)}
    details, cases = [], []
    for _, r in sel.iterrows():
        proj = projs[r.project]
        segs = case_geometry(proj, r)
        texts = pd.read_parquet(proj.findings / "texts.parquet")
        texts = texts[texts.sheet_id == r.sheet_id]
        pl = json.loads(r.port_list)
        me = next(p for p in pl if p["is_self"])
        partner = next((p for p in pl if r.partner_port_id == p["port_id"]), None) if isinstance(r.partner_port_id, str) else None
        detail = {
            "project": r.project, "family": r.family, "sheet_id": r.sheet_id, "port_id": r.port_id,
            "pop": r.sample_pop, "side_class": r.sample_class, "identity": r.identity, "label": r.label,
            "port_number": r.port_number, "block": r.block, "signature": r.signature,
            "wire_axis": r.wire_axis, "wire_span": [round(float(r.wire_lo), 2), round(float(r.wire_hi), 2)],
            "n_wire_ports": int(r.n_wire_ports), "n_wire_groups": int(r.n_wire_groups),
            "port_sequence": [{"along": round(p["along"], 2), "category": p["category"], "identity": p["identity"],
                               "port_number": p["port_number"], "at_extreme": p["at_extreme"], "is_self": p["is_self"]}
                              for p in pl],
            "groups": json.loads(r.groups_json),
            "observations": [{"line_group_id": o.get("line_group_id"), "endpoint_side": o.get("endpoint_side"),
                              "identity_resolved": o.get("identity_resolved"), "wire_touched": o.get("wire_touched")}
                             for o in json.loads(r.obs_json)],
            "pairs": json.loads(r.pairs_json),
            "reason_codes": json.loads(r.reason_codes),
            "gap": {"width": None if pd.isna(r.gap_w) else round(float(r.gap_w), 3),
                    "texts": json.loads(r.gap_texts) if isinstance(r.gap_texts, str) else [],
                    "dots": int(r.gap_dots) if not pd.isna(r.gap_dots) else None,
                    "partner": partner["port_number"] if partner else None,
                    "partner_port_id": r.partner_port_id if isinstance(r.partner_port_id, str) else None},
            "side_ports": json.loads(r.side_ports) if isinstance(r.side_ports, str) else [],
            "side_labels": json.loads(r.side_labels) if isinstance(r.side_labels, str) else {},
            "S_link": bool(r.S_link),
            "dxf": r.dxf,
        }
        details.append(detail)
        # geometry for the render
        pts = [(p["x"], p["y"]) for p in pl]
        all_xy = pts + [(s[0], s[1]) for s in segs] + [(s[2], s[3]) for s in segs]
        wide = R.window_around(all_xy, pad=6.0, min_size=30.0)
        gx = [me["x"]] + ([partner["x"]] if partner else [])
        zoom = R.window_around([(x, y) for x, y in zip(gx, [me["y"]] + ([partner["y"]] if partner else []))],
                               pad=5.0, min_size=16.0)
        boxes_p = []
        for p in pl:
            boxes_p.append((p["x"], p["y"], COL.get(p["category"], "#333333"), p))
        ov_segs = [(s[0], s[1], s[2], s[3], "#1f5fbf", 1.8) for s in segs]
        ov_pts = [(p["x"], p["y"], "#e41a1c" if p["is_self"] else COL.get(p["category"], "#333333")) for p in pl]
        ov_texts = []
        for _, t in texts.iterrows():
            x, y = t["insert_x"], t["insert_y"]
            if x is None or y is None or pd.isna(x) or pd.isna(y):
                continue
            ov_texts.append((float(x), float(y), str(t["text"])[:12], "#b35806"))
        seq = " - ".join(f"{p['category'][:2]}:{p['identity'] or '-'}#{p['port_number']}{'*' if p['is_self'] else ''}"
                          for p in pl)
        head = [f"{r.project} {r.family[:6]} {r.sheet_id} | {r.sample_pop} | side={r.sample_class}",
                f"P={r.identity} #{r.port_number} (red) partner={partner['identity'] if partner else '-'}",
                f"seq: {seq[:150]}"]
        pair_txt = "; ".join(f"{p['status']} {p['left']}-{p['right']}" for p in detail["pairs"][:3]) or "no pair"
        head2 = [f"pairs: {pair_txt[:120]}", f"gap texts: {detail['gap']['texts'][:4]}"]
        cases.append({"head": head, "head2": head2, "wide": wide, "zoom": zoom, "dxf": r.dxf,
                      "segs": ov_segs, "pts": ov_pts, "texts": ov_texts, "label": f"{r.project}-{r.port_number}"})
    details_path.write_text(json.dumps(details, ensure_ascii=False, indent=1), encoding="utf-8")
    png_dir.mkdir(parents=True, exist_ok=True)
    # two cases per PNG
    for n in range(0, len(cases), 2):
        panels = []
        for c in cases[n:n + 2]:
            for view, win in (("宽视图", c["wide"]), ("端子本体间隙", c["zoom"])):
                title = c["head"] + c["head2"] + [view]
                panels.append(R.Panel(title, c["dxf"], win, segs=c["segs"], pts=c["pts"], texts=c["texts"]))
        name = f"GAP2P_{'_'.join(c['label'] for c in cases[n:n + 2])}.png"
        name = name.replace("/", "_").replace(" ", "")[:120] + ".png"
        R.render(png_dir / f"GAP2P_{n // 2 + 1:02d}.png", [f"GAP2-PAIR sample {n // 2 + 1:02d}: {name}"], panels, cols=2)
        print("png", n // 2 + 1, flush=True)
    print("cases", len(cases))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
