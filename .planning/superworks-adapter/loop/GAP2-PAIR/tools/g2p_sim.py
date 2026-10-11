"""GAP2-PAIR offline simulation on round19 (read-only, no src change).

Three things per project (all 77 projects):
1. Baseline: the production build_device_internal_links on round19 inputs. Checked against the round19
   sw_device_internal_links.parquet (must match, as round19 equals HEAD).
2. Split variant (method S): a union wire (line-group union) is cut at every gap that lies between two device-terminal
   ports of the SAME identity and the SAME insert (the two sides of one device terminal, gap 0.5 to 4.0 units). Each
   piece gets its own wire key; the production DEV-INT function is then re-run unchanged. Links that appear are
   coverage only (no Pair, no issue). Method S does not touch pairs, so R-* counts are unchanged by construction.
3. Chain census (method C): along-order adjacent pairs of identity-bearing terminal ports on each union wire,
   excluding same-identity neighbours. Counted against the round19 pairs: new distinct identity pairs, duplicates of
   existing pairs, and identity-degree conflicts (an identity already in another pair), the inputs of
   R-MANY-TO-ONE / R-ONE-TO-MANY / R-DUPLICATE-PAIR.

Output: .tmp/gap2p_work/sim_<tag>.json (per-project counts) and sim_links.parquet (new links of method S).
Usage: python g2p_sim.py <out_dir>
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

GAP_TOOLS = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")
sys.path.insert(0, str(GAP_TOOLS))
import gaplib as G  # noqa: E402
sys.path.insert(0, "F:/workspace/XJToolkit/src")
from dwg_audit.audit.superworks_device_internal import build_device_internal_links, wire_keys_from_lines  # noqa: E402

GAP_MIN, GAP_MAX = 0.5, 4.0
DEVICE = "装置端子"
TERMS = ("端子", "装置端子")


def records(df):
    return df.to_dict("records")


def port_dicts(proj):
    out = []
    for p in records(proj.ports):
        out.append({"record_id": p["record_id"], "file_id": p["file_id"], "sheet_id": p["sheet_id"],
                    "insert_handle": p["insert_handle"], "port_number": p["port_number"], "category": p["category"],
                    "endpoint_identity": G.text(p.get("endpoint_identity")), "label": G.jload(p.get("label"), {}) or {},
                    "wire_contacts": G.jload(p.get("wire_contacts"), []) or []})
    return out


def route_dicts(proj):
    return [dict(r) for r in records(proj.routes)]


def line_and_group_dicts(proj):
    lines = [{"file_id": G.text(l["file_id"]), "line_id": G.text(l["line_id"]), "handle": G.text(l["handle"]),
              "source_block_name": G.text(l.get("source_block_name")),
              "sx": float(l["start_x"]), "sy": float(l["start_y"]), "ex": float(l["end_x"]), "ey": float(l["end_y"])}
             for l in records(proj.lines)]
    groups = [{"file_id": G.text(g["file_id"]), "member_line_ids": G.jload(g.get("member_line_ids"), []) or []}
              for g in records(proj.groups)]
    return lines, groups


def split_mapping(proj, base_map, ports, lines):
    """Method S: cut union wires at same-identity device-terminal gaps. Returns (mapping, gaps_info)."""
    key_lines = defaultdict(list)
    for l in lines:
        k = base_map.get((l["file_id"], l["handle"]))
        if k is not None:
            key_lines[k].append(l)
    key_ports = defaultdict(list)
    for p in ports:
        for c in p["wire_contacts"]:
            h = G.text(c.get("wire_handle"))
            if not h:
                continue
            k = base_map.get((p["file_id"], h), (p["file_id"], h))
            key_ports[k].append((p, float(c.get("x", 0.0)), float(c.get("y", 0.0))))
    mapping = dict(base_map)
    info = []
    for k, plist in key_ports.items():
        if len(key_lines.get(k, [])) < 2:
            continue
        dev = [(p, x, y) for p, x, y in plist if p["category"] == DEVICE and p["endpoint_identity"]]
        if len(dev) < 2:
            continue
        lxs, lys = [], []
        for l in key_lines[k]:
            lxs += [l["sx"], l["ex"]]
            lys += [l["sy"], l["ey"]]
        axis = "x" if (max(lxs) - min(lxs)) >= (max(lys) - min(lys)) else "y"
        along = (lambda x, y: x) if axis == "x" else (lambda x, y: y)
        lat = (lambda x, y: y) if axis == "x" else (lambda x, y: x)
        gaps = []
        for i in range(len(dev)):
            for j in range(i + 1, len(dev)):
                (a, ax_, ay_), (b, bx, by_) = dev[i], dev[j]
                if a["record_id"] == b["record_id"]:
                    continue
                if a["endpoint_identity"] != b["endpoint_identity"] or a["insert_handle"] != b["insert_handle"]:
                    continue
                d = abs(along(ax_, ay_) - along(bx, by_))
                if not (GAP_MIN <= d <= GAP_MAX) or abs(lat(ax_, ay_) - lat(bx, by_)) > 1.0:
                    continue
                gaps.append((min(along(ax_, ay_), along(bx, by_)), max(along(ax_, ay_), along(bx, by_)),
                             a["record_id"], b["record_id"]))
        if not gaps:
            continue
        gaps.sort()
        # reassign every line of k to a piece by midpoint; lines crossing a gap stay in the left piece (counted)
        crossing = 0
        for l in key_lines[k]:
            mid = (along(l["sx"], l["sy"]) + along(l["ex"], l["ey"])) / 2.0
            lo_a, hi_a = min(along(l["sx"], l["sy"]), along(l["ex"], l["ey"])), max(along(l["sx"], l["sy"]), along(l["ex"], l["ey"]))
            if any(lo_a < g[1] - 0.05 and hi_a > g[0] + 0.05 for g in gaps):
                crossing += 1
            idx = sum(1 for g in gaps if g[1] <= mid)
            mapping[(l["file_id"], l["handle"])] = (k[0], f"{k[1]}|s{idx}")
        info.append({"key": f"{k[0]}:{k[1]}", "gaps": len(gaps), "crossing_lines": crossing,
                     "pairs": [[g[2], g[3]] for g in gaps]})
    return mapping, info


def chain_census(proj, ports, base_map, pairs):
    """Method C: adjacent identity pairs along each union wire, against round19 pairs."""
    key_ports = defaultdict(list)
    for p in ports:
        if p["category"] not in TERMS or not p["endpoint_identity"]:
            continue
        for c in p["wire_contacts"]:
            h = G.text(c.get("wire_handle"))
            if not h:
                continue
            k = base_map.get((p["file_id"], h), (p["file_id"], h))
            key_ports[k].append((p, float(c.get("x", 0.0)), float(c.get("y", 0.0))))
    existing = set()
    deg = Counter()
    for pr in pairs:
        lv, rv = G.text(pr.get("left_value")), G.text(pr.get("right_value"))
        if pr.get("status") == "discard" or not lv or not rv:
            continue
        existing.add(frozenset((lv.casefold(), rv.casefold())))
        deg[lv.casefold()] += 1
        deg[rv.casefold()] += 1
    stats = Counter()
    for k, plist in key_ports.items():
        seen = {}
        for p, x, y in plist:
            seen[p["record_id"]] = (p, x, y)
        items = list(seen.values())
        if len(items) < 3:
            continue
        items.sort(key=lambda t: t[1])  # x; vertical wires are rare in the population, handled by y below
        lxs = [t[1] for t in items]
        lys = [t[2] for t in items]
        if (max(lys) - min(lys)) > (max(lxs) - min(lxs)):
            items.sort(key=lambda t: t[2])
        stats["union_wires_ge3_terminals"] += 1
        for (a, *_), (b, *__) in zip(items, items[1:]):
            av, bv = a["endpoint_identity"].casefold(), b["endpoint_identity"].casefold()
            if av == bv:
                stats["self_same_identity_neighbour"] += 1
                continue
            stats["candidate"] += 1
            if frozenset((av, bv)) in existing:
                stats["duplicate_of_existing_pair"] += 1
                continue
            stats["new_distinct"] += 1
            if deg[av] > 0 or deg[bv] > 0:
                stats["new_identity_degree_conflict"] += 1
    return stats


def main(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    per_project = {}
    link_rows = []
    total = Counter()
    for proj in G.iter_projects():
        ports = port_dicts(proj)
        routes = route_dicts(proj)
        lines, groups = line_and_group_dicts(proj)
        base_map = wire_keys_from_lines(lines, groups)
        base = build_device_internal_links(ports, routes, wire_group_of=base_map)
        stored = pd.read_parquet(proj.findings / "sw_device_internal_links.parquet")
        stored_ids = set(stored["link_id"]) if len(stored) else set()
        base_ids = {l["link_id"] for l in base["links"]}
        mapping, info = split_mapping(proj, base_map, ports, lines)
        var = build_device_internal_links(ports, routes, wire_group_of=mapping)
        var_ids = {l["link_id"] for l in var["links"]}
        new_links = [l for l in var["links"] if l["link_id"] not in base_ids]
        lost = base_ids - var_ids
        pairs = records(pd.read_parquet(proj.findings / "pairs.parquet"))
        chain = chain_census(proj, ports, base_map, pairs)
        rec = {"base_links": len(base_ids), "stored_links": len(stored_ids), "match_stored": base_ids == stored_ids,
               "var_links": len(var_ids), "new_links": len(new_links), "lost_links": len(lost),
               "split_wires": len(info), "split_gaps": sum(i["gaps"] for i in info),
               "crossing_lines": sum(i["crossing_lines"] for i in info),
               "base_stats": {k: v for k, v in base["stats"].items()}, "var_stats": {k: v for k, v in var["stats"].items()},
               "chain": dict(chain)}
        per_project[proj.pid] = rec
        for l in new_links:
            link_rows.append({**{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                                 for k, v in l.items()}, "project": proj.pid, "family": proj.family})
        total.update({"base_links": len(base_ids), "var_links": len(var_ids), "new_links": len(new_links),
                      "lost_links": len(lost), "split_gaps": rec["split_gaps"], "split_wires": rec["split_wires"]})
        total.update({f"chain_{k}": v for k, v in chain.items()})
        print(proj.pid, rec["base_links"], rec["stored_links"], rec["match_stored"], "->", rec["var_links"],
              "new", rec["new_links"], "lost", rec["lost_links"], "gaps", rec["split_gaps"], flush=True)
    (out_dir / "sim_projects.json").write_text(json.dumps(per_project, ensure_ascii=False, indent=1), encoding="utf-8")
    pd.DataFrame(link_rows).to_parquet(out_dir / "sim_links.parquet", index=False)
    (out_dir / "sim_total.json").write_text(json.dumps(dict(total), ensure_ascii=False, indent=1), encoding="utf-8")
    print("TOTAL", dict(total))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
