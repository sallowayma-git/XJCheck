"""MULTI-SEG final offline comparison: production (M_prod) against M2 (body + element cut), read-only.

Writes .tmp/multiseg_work/final_summary.json with:
  - outcome of every port of the 870 refused candidates under M2 (internal link / external candidate by class / none)
  - ports lost and gained between M_prod and M2 (device-internal links), with the reason class of each lost port
  - external candidate deltas (wires only in M2, only in production) with their pair classes
  - unknown-topology counts under M2 (wires with three or more SW ports, dot-less or corner ends, single-port wires
    without a link, by reason)
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ms_common as M  # noqa: E402
import ms_geom as G  # noqa: E402
import ms_sim as S  # noqa: E402

DI = M.DI
WORK = M.ROOT / ".tmp" / "multiseg_work"


def wires_of(proj, mapping, base):
    """wire key -> {record_id: port} for every external and internal SW port with a contact on it."""
    out = defaultdict(dict)
    for port in proj.ports:
        fid = M.text(port["file_id"])
        for c in DI._contacts_of(port):
            h = M.text(c.get("wire_handle"))
            if not h:
                continue
            key = mapping.get((fid, h), base.get((fid, h), (fid, h)))
            out[key][M.text(port["record_id"])] = port
    return out


def main():
    summary = {"ports_870": Counter(), "lost": Counter(), "gained": Counter(), "lost_reasons": Counter(),
               "gained_sources": Counter(), "ext_only_m2": Counter(), "ext_only_prod": Counter(),
               "unknown": Counter(), "unknown_examples": defaultdict(list), "per_project": []}
    refused_ports = {}
    per_project = []
    for proj in M.load_all():
        cands, groups, roots, segments = S.enumerate_all(proj)
        base = S.wire_keys_base(proj)
        inp = S.base_inputs(proj)
        ports_by_id = {M.text(p["record_id"]): p for p in proj.ports}
        partners, covered, _ = S.port_partner_index(proj, ports_by_id)
        prod = DI.build_device_internal_links(
            inp["ports"], inp["wire_routes"], unregistered=inp["unregistered"], wire_endpoints=inp["wire_endpoints"],
            terminal_split={"lines": S.dicts_of_lines(proj), "line_groups": S.groups_of(proj),
                            "connect_dots": S.dots_of(proj)})
        cut2 = S.cut_positions(proj, cands, groups, roots, segments, use_elements=True)
        mapping2 = S.mapping_from_cuts(groups, roots, base, cut2)
        m2 = DI.build_device_internal_links(inp["ports"], inp["wire_routes"], wire_group_of=mapping2,
                                            unregistered=inp["unregistered"], wire_endpoints=inp["wire_endpoints"],
                                            terminal_split=None)
        prod_ports = {l["port_id"]: l["source"] for l in prod["links"]}
        m2_ports = {l["port_id"]: l["source"] for l in m2["links"]}
        # 870 candidates: outcome per port under M2
        m2_ext = S.external_candidates(proj, mapping2, lambda fid, h: base.get((fid, h), (fid, h)))
        ext_by_port = defaultdict(list)
        for key, a, b, ia, ib in m2_ext:
            ext_by_port[M.text(a["record_id"])].append(M.text(b["record_id"]))
            ext_by_port[M.text(b["record_id"])].append(M.text(a["record_id"]))
        for c in cands:
            if c["reason"] != "components_not_two":
                continue
            for p in (c["port_a"], c["port_b"]):
                pid_ = M.text(p["record_id"])
                if pid_ in m2_ports:
                    outcome = "internal_link_" + m2_ports[pid_]
                elif pid_ in ext_by_port:
                    outcome = "external_candidate"
                else:
                    outcome = "unresolved"
                refused_ports.setdefault((proj.pid, pid_), outcome)
        # lost / gained device-internal links
        for pid_ in set(prod_ports) - set(m2_ports):
            summary["lost"][prod_ports[pid_]] += 1
            # reason: the wire of this port under M2
        for pid_ in set(m2_ports) - set(prod_ports):
            summary["gained"][m2_ports[pid_]] += 1
        # classify lost ports by the M2 wire they now sit on
        w2 = wires_of(proj, mapping2, base)
        for pid_ in set(prod_ports) - set(m2_ports):
            port = ports_by_id[pid_]
            keys = []
            for c in DI._contacts_of(port):
                h = M.text(c.get("wire_handle"))
                keys.append(mapping2.get((M.text(port["file_id"]), h), base.get((M.text(port["file_id"]), h), (0, h))))
            others = set()
            for k in keys:
                for rid, other in w2.get(k, {}).items():
                    if rid != pid_:
                        others.add(M.text(other.get("category")))
            label = "others:" + "/".join(sorted(others)) if others else "no_other_port_on_wire"
            summary["lost_reasons"][label] += 1
        # external candidate deltas
        prod_ext = S.external_candidates(proj, base, lambda fid, h: base.get((fid, h), (fid, h)))
        pe = {tuple(sorted([M.text(a["record_id"]), M.text(b["record_id"])])) for _, a, b, _, _ in prod_ext}
        me = {tuple(sorted([M.text(a["record_id"]), M.text(b["record_id"])])) for _, a, b, _, _ in m2_ext}
        cmp_map = {}
        for _, a, b, ia, ib in m2_ext:
            cmp_map[tuple(sorted([M.text(a["record_id"]), M.text(b["record_id"])]))] = (a, b, ia, ib)
        for _, a, b, ia, ib in prod_ext:
            cmp_map.setdefault(tuple(sorted([M.text(a["record_id"]), M.text(b["record_id"])])), (a, b, ia, ib))
        for k in me - pe:
            a, b, ia, ib = cmp_map[k]
            summary["ext_only_m2"][classify_pair(partners, a, b, ia, ib)] += 1
        for k in pe - me:
            a, b, ia, ib = cmp_map[k]
            summary["ext_only_prod"][classify_pair(partners, a, b, ia, ib)] += 1
        # unknown topology under M2: wires with >= 3 SW ports, and single-port wires without a link
        for key, ports in w2.items():
            if len(ports) >= 3:
                summary["unknown"]["multi_port_wire_ge3"] += 1
                if len(summary["unknown_examples"]["multi_port_wire_ge3"]) < 5:
                    summary["unknown_examples"]["multi_port_wire_ge3"].append(
                        [proj.pid, str(key), sorted(ports)[:4]])
        for reason, n in m2["stats"].items():
            if reason.startswith("excluded:") or reason.startswith("unregistered:") or reason.startswith("split"):
                summary["unknown"][reason] += n
        per_project.append({"pid": proj.pid, "prod_links": len(prod["links"]), "m2_links": len(m2["links"]),
                            "lost": len(set(prod_ports) - set(m2_ports)), "gained": len(set(m2_ports) - set(prod_ports))})
        print("done", proj.pid, flush=True)
    for (pid_, port_id), outcome in refused_ports.items():
        summary["ports_870"][outcome] += 1
    out = {k: (dict(v) if isinstance(v, Counter) else (dict(v) if isinstance(v, defaultdict) else v))
           for k, v in summary.items() if k != "per_project"}
    out["per_project"] = per_project
    out["ports_870_total"] = sum(summary["ports_870"].values())
    (WORK / "final_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "per_project"}, ensure_ascii=False, indent=1, default=str))


def classify_pair(partners, a, b, ia, ib):
    ra, rb = M.text(a["record_id"]), M.text(b["record_id"])
    x, y = ia.casefold(), ib.casefold()
    pa, pb = partners.get(ra, set()), partners.get(rb, set())
    if (bool(pa) and y not in pa) or (bool(pb) and x not in pb):
        return "conflict"
    if pa and pb:
        return "agree_both_already_paired"
    if pa or pb:
        return "agree_one_side_new_other"
    return "new_both_ports"


if __name__ == "__main__":
    main()
