"""GAP2-PAIR checks (read-only): chain method census, open-end probes of the side-open population.

A. Population chain (method C on the 3028 population wires): adjacent identity-bearing terminal ports along each
   union wire. Each adjacent pair is classified as self (same identity), duplicate (an existing non-discard pair with
   the same identities), new, and whether its contact gap is a terminal body (<= 4.0) or a longer break (a component
   or a label sits in between).
B. Corpus chain census with the same classes (all 77 projects; wires with >= 3 identity-bearing terminal ports).
C. Open-end probes for the 945 side-open population ports: block vertex (unregistered-pin proxy), perpendicular
   model-space line at the free end (by layer), SuperWORKS connect dot within 1.5, text bbox within 2.0, connect
   label within 3.0.

Writes .tmp/gap2p_work/checks.json. Usage: python g2p_checks.py <classes.parquet> <out.json>
"""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

GAP_TOOLS = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")
sys.path.insert(0, str(GAP_TOOLS))
import gaplib as G  # noqa: E402
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP2-PAIR/tools")
from g2p_sim import line_and_group_dicts, port_dicts  # noqa: E402
from dwg_audit.audit.superworks_device_internal import wire_keys_from_lines  # noqa: E402

TERMS = ("端子", "装置端子")
BODY = 4.0


def chain_class(a_id, b_id, a_v, b_v, gap, existing):
    if a_v == b_v:
        return "self_same_identity"
    key = frozenset((a_v.casefold(), b_v.casefold()))
    if key in existing:
        return "duplicate_of_existing_pair"
    return "new_body_gap" if gap <= BODY else "new_spans_break"


def population_chain(cls: pd.DataFrame):
    stats = Counter()
    for r in cls.itertuples(index=False):
        pl = json.loads(r.port_list)
        pairs = json.loads(r.pairs_json)
        existing = set()
        for p in pairs:
            if p["status"] != "discard" and p["left"] and p["right"]:
                existing.add(frozenset((str(p["left"]).casefold(), str(p["right"]).casefold())))
        items = [p for p in pl if p["category"] in TERMS and p["identity"]]
        items.sort(key=lambda p: p["along"])
        for a, b in zip(items, items[1:]):
            c = chain_class(a["port_id"], b["port_id"], a["identity"], b["identity"], abs(b["along"] - a["along"]), existing)
            stats[(r.pop, c)] += 1
    return {f"{k[0]}|{k[1]}": v for k, v in stats.items()}


def corpus_chain():
    stats = Counter()
    for proj in G.iter_projects():
        ports = port_dicts(proj)
        lines, groups = line_and_group_dicts(proj)
        base_map = wire_keys_from_lines(lines, groups)
        pairs = pd.read_parquet(proj.findings / "pairs.parquet").to_dict("records")
        existing = set()
        for p in pairs:
            if p["status"] != "discard" and isinstance(p["left_value"], str) and isinstance(p["right_value"], str):
                existing.add(frozenset((p["left_value"].casefold(), p["right_value"].casefold())))
        key_ports = defaultdict(dict)
        for p in ports:
            if p["category"] not in TERMS or not p["endpoint_identity"]:
                continue
            for c in p["wire_contacts"]:
                h = G.text(c.get("wire_handle"))
                if h:
                    k = base_map.get((p["file_id"], h), (p["file_id"], h))
                    key_ports[k][p["record_id"]] = (p, float(c.get("x", 0.0)), float(c.get("y", 0.0)))
        for k, d in key_ports.items():
            items = list(d.values())
            if len(items) < 3:
                continue
            xs = [t[1] for t in items]
            ys = [t[2] for t in items]
            idx = 1 if (max(ys) - min(ys)) > (max(xs) - min(xs)) else 0
            items.sort(key=lambda t: (t[1], t[2]) if idx == 0 else (t[2], t[1]))
            stats["wires_ge3_terminals"] += 1
            for (a, ax, ay), (b, bx, by) in zip(items, items[1:]):
                gap = math.hypot(bx - ax, by - ay)
                c = chain_class(a["record_id"], b["record_id"], a["endpoint_identity"], b["endpoint_identity"], gap, existing)
                stats[c] += 1
    return dict(stats)


def open_end_probes(cls: pd.DataFrame):
    op = cls[cls["side_class"] == "side_open"]
    stats = Counter()
    cache = {}
    for r in op.itertuples(index=False):
        if r.project not in cache:
            base = Path("F:/workspace/XJToolkit/.tmp/superworks_round19_full") / r.project
            f = glob.glob(str(base / "*" / "findings"))[0]
            cache[r.project] = (pd.read_parquet(Path(f) / "lines.parquet"), pd.read_parquet(Path(f) / "sw_connect_dots.parquet"),
                                pd.read_parquet(Path(f) / "texts.parquet"), pd.read_parquet(Path(f) / "sw_connect_labels.parquet"))
        lines, dots, texts, labels = cache[r.project]
        L = lines[lines.sheet_id == r.sheet_id]
        blk = L[L.source_block_name.fillna("").astype(str) != ""]
        mod = L[L.source_block_name.fillna("").astype(str) == ""]
        end = float(r.wire_lo) if r.side == "left" else float(r.wire_hi)
        lat = float(r.contact_y) if r.wire_axis == "x" else float(r.contact_x)
        ex, ey = (end, lat) if r.wire_axis == "x" else (lat, end)
        # block vertex within 0.6
        if any(min(math.hypot(ex - b.start_x, ey - b.start_y), math.hypot(ex - b.end_x, ey - b.end_y)) <= 0.6
               for b in blk.itertuples(index=False)):
            stats["block_vertex_0.6"] += 1
        else:
            stats["no_block_vertex"] += 1
        perp = None
        for m in mod.itertuples(index=False):
            if r.wire_axis == "x":
                ok = abs(m.start_x - m.end_x) < 1e-6 and abs(m.start_x - ex) <= 0.6 and \
                    min(m.start_y, m.end_y) - 0.6 <= ey <= max(m.start_y, m.end_y) + 0.6
            else:
                ok = abs(m.start_y - m.end_y) < 1e-6 and abs(m.start_y - ey) <= 0.6 and \
                    min(m.start_x, m.end_x) - 0.6 <= ex <= max(m.start_x, m.end_x) + 0.6
            if ok:
                perp = m.layer
                break
        stats[f"perp_line:{perp}" if perp else "perp_line:none"] += 1
        D = dots[dots.sheet_id == r.sheet_id]
        dot = any(math.hypot(ex - d.x, ey - d.y) <= 1.5 for d in D.itertuples(index=False))
        stats["connect_dot_1.5:" + ("yes" if dot else "no")] += 1
        T = texts[texts.sheet_id == r.sheet_id]
        tt = False
        for t in T.itertuples(index=False):
            if any(pd.isna(v) for v in (t.bbox_min_x, t.bbox_max_x, t.bbox_min_y, t.bbox_max_y)):
                continue
            dx = max(t.bbox_min_x - ex, 0, ex - t.bbox_max_x)
            dy = max(t.bbox_min_y - ey, 0, ey - t.bbox_max_y)
            if math.hypot(dx, dy) <= 2.0:
                tt = True
                break
        stats["text_bbox_2.0:" + ("yes" if tt else "no")] += 1
        S = labels[labels.sheet_id == r.sheet_id] if len(labels) else labels
        lab = any(min(math.hypot(ex - s.start_x, ey - s.start_y), math.hypot(ex - s.end_x, ey - s.end_y)) <= 3.0
                  for s in S.itertuples(index=False)) if len(S) else False
        stats["connect_label_3.0:" + ("yes" if lab else "no")] += 1
    return dict(stats), len(op)


def main(cls_path: Path, out: Path):
    cls = pd.read_parquet(cls_path)
    result = {"population_chain": population_chain(cls)}
    print("population chain", result["population_chain"], flush=True)
    result["corpus_chain"] = corpus_chain()
    print("corpus chain", result["corpus_chain"], flush=True)
    probes, n = open_end_probes(cls)
    result["open_end_probes"] = {"n": n, **probes}
    print("open-end probes", result["open_end_probes"], flush=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
