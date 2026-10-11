"""MULTI-SEG offline simulation of connection methods on the round21 products (read-only; writes JSON only).

Methods compared (all call the production device-internal function, reference copy of the final GAP2-S module):
  M0  unsplit: line groups as they are (wire key = line group; the pre-GAP2-S rule plus the element guard)
  M1  body cut, any number of pieces: every device-terminal body (two TERMPOINTs of one insert and identity, gap at
      body width, no crossing, no dot) cuts its group, whatever the number of pieces
  M2  body cut plus element cut: as M1, and also every gap that holds a symbol (unregistered two-pin block spanning the
      gap, SuperWORKS internal element or coil TERMPOINT in the gap, another device terminal TERMPOINT in the gap, a model
      line crossing the gap). Label-only gaps and dot gaps stay merged; small empty gaps stay merged.
Check run: M_prod uses the production terminal_split path (GAP2-S); its link total should be 18646 (final 77 projects)
and M0 should be 14704 (= round20 14801 minus 97 guard removals), which validates the approximated inputs.

External-pair metric: a wire key with exactly two distinct SW ports of category 端子 or 装置端子 at its contacts and
different identities. Compared with the pair table: agree (a pass pair with the same identity set), conflict (a pass pair
on either identity with a different partner), new (neither identity has a pass pair).
Output: .tmp/multiseg_work/sim_results.json and per-project counts. Usage: python ms_sim.py [methods...]
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ms_common as M  # noqa: E402
import ms_geom as G  # noqa: E402

DI = M.DI
WORK = M.ROOT / ".tmp" / "multiseg_work"
EXT_CATS = {"端子", "装置端子"}


def wire_endpoints_of(proj):
    out = defaultdict(dict)
    for l in proj.lines:
        if M.text(l.get("source_block_name")):
            continue
        fid, handle = M.text(l["file_id"]), M.text(l["handle"])
        sx, sy, ex, ey = (M.DI._number(l.get(k)) for k in ("start_x", "start_y", "end_x", "end_y"))
        if None in (sx, sy, ex, ey) or not handle:
            continue
        out[(fid, handle)][0] = (sx, sy)
        out[(fid, handle)][1] = (ex, ey)
    return dict(out)


def unreg_blocks(proj):
    rows = []
    for b in proj.unreg:
        rows.append({"record_id": M.text(b["record_id"]), "file_id": M.text(b["file_id"]),
                     "insert_handle": M.text(b["insert_handle"]), "label_value": M.text(b["label_value"]),
                     "label_resolved": bool(b["label_resolved"]),
                     "termpoints": M.jload(b.get("termpoints"), [])})
    return rows


def dicts_of_lines(proj):
    out = []
    for l in proj.lines:
        out.append({"file_id": M.text(l["file_id"]), "line_id": M.text(l["line_id"]), "handle": M.text(l["handle"]),
                    "source_block_name": M.text(l["source_block_name"]),
                    "sx": l["start_x"], "sy": l["start_y"], "ex": l["end_x"], "ey": l["end_y"]})
    return out


def groups_of(proj):
    return [{"file_id": M.text(g["file_id"]), "member_line_ids": M.jload(g.get("member_line_ids"), [])}
            for g in proj.groups]


def dots_of(proj):
    return [{"file_id": M.text(d["file_id"]), "x": d["x"], "y": d["y"]} for d in proj.dots]


def ports_of(proj):
    return proj.ports


def base_inputs(proj):
    return dict(ports=ports_of(proj), wire_routes=proj.routes,
                unregistered=unreg_blocks(proj), wire_endpoints=wire_endpoints_of(proj))


# ---- cut rules -------------------------------------------------------------------------------------------------

def cut_positions(proj, cands, groups, roots, segments, use_elements):
    """{group index: set of gap indices} for the chosen rule. Gap i lies between pieces i and i+1 (axis order)."""
    body_gaps = defaultdict(set)
    for c in cands:
        if c["reason"] not in (None, "components_not_two"):
            continue
        pieces = G.piece_extents(c["keys"], segments, c["roots"])
        ia = _piece_at(pieces, c["ca"][0])
        ib = _piece_at(pieces, c["cb"][0])
        if ia is None or ib is None or abs(ia - ib) != 1:
            continue
        body_gaps[c["group_index"]].add(min(ia, ib))
    cut = defaultdict(set)
    for gi, gaps in body_gaps.items():
        cut[gi] |= gaps
    if not use_elements:
        return cut
    for gi, (g, keys) in enumerate(groups):
        if len(keys) < 2:
            continue
        pieces = G.piece_extents(keys, segments, roots[gi])
        if len(pieces) < 2:
            continue
        fid = keys[0][0]
        y = sum(segments[k]["sy"] for k in keys) / len(keys)
        for i in range(len(pieces) - 1):
            if i in cut[gi]:
                continue
            x0, x1 = pieces[i]["xmax"], pieces[i + 1]["xmin"]
            if element_in_gap(proj, fid, x0, x1, y, keys):
                cut[gi].add(i)
    return cut


def _piece_at(pieces, x):
    for i, p in enumerate(pieces):
        if p["xmin"] - 0.05 <= x <= p["xmax"] + 0.05:
            return i
    return None


_ELEM_CATS = {"内部元件", "线圈", "装置端子"}


def element_in_gap(proj, fid, x0, x1, y, keys):
    """True when the gap between two pieces holds a symbol: unregistered two-pin span, an element or device TERMPOINT,
    or a model line crossing it."""
    cache = proj.__dict__.setdefault("_ms_gapcache", {})
    key = fid
    if key not in cache:
        cache[key] = {
            "ports": [(M.text(p["category"]), (M.DI._number(p["start_x"]), M.DI._number(p["start_y"]),
                                                 M.DI._number(p["end_x"]), M.DI._number(p["end_y"])),
                       M.text(p["insert_handle"]))
                      for p in proj.ports if M.text(p["file_id"]) == fid],
            "unreg": [b for b in proj.unreg if M.text(b["file_id"]) == fid],
            "model": [(M.text(l["line_id"]), M.DI._number(l["start_x"]), M.DI._number(l["start_y"]),
                       M.DI._number(l["end_x"]), M.DI._number(l["end_y"]))
                      for l in proj.lines if M.text(l["file_id"]) == fid and not M.text(l["source_block_name"])],
        }
    c = cache[key]
    member = {k[1] for k in keys}
    # unregistered two-pin block spanning the gap
    for b in c["unreg"]:
        left = right = False
        for tp in M.jload(b.get("termpoints"), []):
            for p in (tp["a"], tp["b"]):
                if abs(p[1] - y) <= 0.6:
                    left = left or abs(p[0] - x0) <= 0.6
                    right = right or abs(p[0] - x1) <= 0.6
        if left and right:
            return True
    # SuperWORKS element or device block whose two TERMPOINTs (same insert) bracket the gap: a symbol between the pieces.
    elems = []
    for cat, (ax, ay, bx, by), insert in c["ports"]:
        if None in (ax, ay, bx, by) or cat not in _ELEM_CATS:
            continue
        if abs((ay + by) / 2 - y) > 2.0:
            continue
        elems.append(((ax + bx) / 2, insert, (ax, ay, bx, by)))
    # (a single TERMPOINT inside the gap is an element hanging on one piece, not a symbol between two pieces)
    for mx1, ins1, _ in elems:
        for mx2, ins2, _ in elems:
            if ins1 == ins2 and abs(mx1 - x0) <= 0.6 and abs(mx2 - x1) <= 0.6 and mx1 < mx2:
                return True
    # a model line crossing the gap (passes through it, does not end on it: a line ending on the gap is a T, kept)
    for lid, sx, sy, ex, ey in c["model"]:
        if lid in member or None in (sx, sy, ex, ey):
            continue
        if not (min(sx, ex) < x1 and max(sx, ex) > x0):
            continue
        if (sy - y) * (ey - y) < -1e-6 and abs(sx - ex) < 1e-6 and x0 <= sx <= x1:
            return True
        if abs(sy - y) < 1e-6 or abs(ey - y) < 1e-6:
            continue
    return False


def mapping_from_cuts(groups, roots, base_map, cut):
    """Wire key for every line handle: pieces between cuts become separate wire keys."""
    mapping = dict(base_map)
    for gi, (g, keys) in enumerate(groups):
        if gi not in cut or not cut[gi]:
            continue
        pieces = defaultdict(list)
        for k in keys:
            pieces[roots[gi][k]].append(k)
        ordered = sorted(pieces.items(), key=lambda kv: _piece_x(kv[1]))
        run = 0
        for i, (root, members) in enumerate(ordered):
            if i - 1 in cut[gi]:
                run += 1
            for (fid, line_id) in members:
                handle = _handle_of(fid, line_id)
                if handle:
                    mapping[(fid, handle)] = (fid, "C%d:%d" % (gi, run))
    return mapping


_HANDLE = {}


def _handle_of(fid, line_id):
    return _HANDLE.get((fid, line_id), "")


def _piece_x(members):
    return min(_SEG[k]["sx"] for k in members) if members else 0


_SEG = {}


def enumerate_all(proj):
    cands, groups, roots, segments, model, dots = M.enumerate_split_candidates(proj)
    _SEG.clear()
    _SEG.update(segments)
    _HANDLE.clear()
    for l in proj.lines:
        _HANDLE[(M.text(l["file_id"]), M.text(l["line_id"]))] = M.text(l["handle"])
    return cands, groups, roots, segments


def wire_keys_base(proj):
    lines = dicts_of_lines(proj)
    groups = groups_of(proj)
    return DI.wire_keys_from_lines(lines, groups)


# ---- metrics ----------------------------------------------------------------------------------------------------

def external_candidates(proj, mapping, base_key):
    """Wire keys with exactly two distinct external-category ports of different identity, on their contacts."""
    by_wire = defaultdict(dict)
    for port in proj.ports:
        cat = M.text(port.get("category"))
        if cat not in EXT_CATS:
            continue
        fid = M.text(port["file_id"])
        for c in DI._contacts_of(port):
            h = M.text(c.get("wire_handle"))
            if not h:
                continue
            key = mapping.get((fid, h), base_key(fid, h))
            by_wire[key][M.text(port["record_id"])] = port
    out = []
    for key, ports in by_wire.items():
        if len(ports) != 2:
            continue
        a, b = list(ports.values())
        ia, ib = M.text(a["endpoint_identity"]), M.text(b["endpoint_identity"])
        if not ia or not ib or ia.casefold() == ib.casefold():
            continue
        out.append((key, a, b, ia, ib))
    return out


def port_partner_index(proj, ports_by_id):
    """Port record id -> set of partner identities (casefold) of its PASS pairs, from sw_port_coverage.production_pairs.

    side 'right' means the port's identity is the right value, so its partner is the left value (and the reverse).
    mismatches counts rows where the port identity is not the value on the side it names (should be 0).
    """
    import pandas as pd
    cov = pd.read_parquet(proj.findings / "sw_port_coverage.parquet")
    pair_vals = {}
    for p in proj.pairs:
        pair_vals[M.text(p["pair_id"])] = (M.text(p.get("left_value")).casefold(), M.text(p.get("right_value")).casefold(),
                                            M.text(p.get("status")))
    partners = defaultdict(set)
    mismatches = 0
    for rec in cov.to_dict("records"):
        port = ports_by_id.get(M.text(rec["port_id"]))
        for item in M.jload(rec.get("production_pairs"), []):
            if M.text(item.get("status")) != "pass":
                continue
            vals = pair_vals.get(M.text(item.get("pair_id")))
            if not vals:
                continue
            left, right, _ = vals
            side = M.text(item.get("side"))
            own = text_casefold(port.get("endpoint_identity")) if port else ""
            if side == "right":
                if own and own != right:
                    mismatches += 1
                partners[M.text(rec["port_id"])].add(left)
            elif side == "left":
                if own and own != left:
                    mismatches += 1
                partners[M.text(rec["port_id"])].add(right)
    covered = set(partners)
    return partners, covered, mismatches


def text_casefold(value):
    return M.text(value).casefold()


def compare_ports(cands_ext, partners):
    """Per external candidate wire: agree / conflict / new, and which of its ports are not pass-covered yet."""
    res = Counter()
    new_ports = set()
    for key, a, b, ia, ib in cands_ext:
        ra, rb = M.text(a["record_id"]), M.text(b["record_id"])
        x, y = ia.casefold(), ib.casefold()
        pa, pb = partners.get(ra, set()), partners.get(rb, set())
        conflict = bool(pa) and y not in pa or bool(pb) and x not in pb
        if conflict:
            res["conflict"] += 1
        elif pa and pb:
            res["agree_both_already_paired"] += 1
        elif pa or pb:
            res["agree_one_side_new_other"] += 1
        else:
            res["new_both_ports"] += 1
        if not pa:
            new_ports.add(ra)
        if not pb:
            new_ports.add(rb)
    return res, new_ports


def simulate(proj, methods):
    cands, groups, roots, segments = enumerate_all(proj)
    base = wire_keys_base(proj)
    inp = base_inputs(proj)
    ports_by_id = {M.text(p["record_id"]): p for p in proj.ports}
    partners, covered, mismatches = port_partner_index(proj, ports_by_id)
    res = {"pid": proj.pid, "pair_side_mismatches": mismatches}
    for method in methods:
        if method == "M_prod":
            out = DI.build_device_internal_links(
                inp["ports"], inp["wire_routes"], unregistered=inp["unregistered"],
                wire_endpoints=inp["wire_endpoints"],
                terminal_split={"lines": dicts_of_lines(proj), "line_groups": groups_of(proj),
                                "connect_dots": dots_of(proj)})
            wire_key = None
            mapping_final = None
        else:
            if method == "M0":
                cut = {}
            elif method == "M1":
                cut = cut_positions(proj, cands, groups, roots, segments, use_elements=False)
            elif method == "M2":
                cut = cut_positions(proj, cands, groups, roots, segments, use_elements=True)
            else:
                raise ValueError(method)
            mapping_final = mapping_from_cuts(groups, roots, base, cut) if cut else dict(base)
            out = DI.build_device_internal_links(
                inp["ports"], inp["wire_routes"], wire_group_of=mapping_final, unregistered=inp["unregistered"],
                wire_endpoints=inp["wire_endpoints"], terminal_split=None)
        links = out["links"]
        res[method] = {
            "links": len(links), "stats": {k: v for k, v in out["stats"].items() if isinstance(v, (int, float))},
            "by_source": dict(Counter(l["source"] for l in links)),
            "link_ports": sorted({l["port_id"] for l in links}),
            "link_ids": sorted(l["link_id"] for l in links),
            "split_links": sum(1 for l in links if l.get("split_reason")),
        }
        if mapping_final is None:
            mapping_final = dict(base)
        ext = external_candidates(proj, mapping_final, lambda fid, h: base.get((fid, h), (fid, h)))
        cmp_, new_ports = compare_ports(ext, partners)
        res[method]["ext_candidates"] = len(ext)
        res[method]["ext_vs_pairs"] = dict(cmp_)
        res[method]["ext_new_ports"] = len(new_ports)
        res[method]["ext_pairs"] = sorted([[a.get("record_id"), b.get("record_id"), ia, ib] for _, a, b, ia, ib in ext])
    return res


def main(methods):
    t0 = time.time()
    results = []
    for proj in M.load_all():
        results.append(simulate(proj, methods))
        print("done", proj.pid, round(time.time() - t0, 1), flush=True)
    totals = {}
    for m in methods:
        tot = Counter()
        ext = Counter()
        bysrc = Counter()
        for r in results:
            tot["links"] += r[m]["links"]
            tot["split_links"] += r[m]["split_links"]
            tot["ext_candidates"] += r[m]["ext_candidates"]
            for k, v in r[m]["ext_vs_pairs"].items():
                ext[k] += v
            tot["ext_new_ports"] += r[m]["ext_new_ports"]
            for k, v in r[m]["by_source"].items():
                bysrc[k] += v
        totals[m] = {"links": tot["links"], "split_links": tot["split_links"], "by_source": dict(bysrc),
                     "ext_candidates": tot["ext_candidates"], "ext_vs_pairs": dict(ext),
                     "ext_new_ports": tot["ext_new_ports"]}
    out = {"methods": methods, "totals": totals, "projects": [
        {"pid": r["pid"], **{m: {k: v for k, v in r[m].items() if k not in ("link_ids", "link_ports", "ext_pairs")}
                             for m in methods}} for r in results]}
    # keep the per-link ids for cross-method comparison
    detail_path = WORK / ("sim_detail_%s.json" % "_".join(methods))
    detail_path.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    (WORK / ("sim_totals_%s.json" % "_".join(methods))).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                                   encoding="utf-8")
    print(json.dumps(totals, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:] or ["M_prod", "M0", "M1", "M2"])
