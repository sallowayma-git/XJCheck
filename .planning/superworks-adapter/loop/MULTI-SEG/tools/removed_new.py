import sys, json, collections
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/MULTI-SEG/tools")
import ms_common as M
import ms_geom as G
import ms_sim as S

DI = M.DI
out = []
for proj in M.load_all():
    cands, groups, roots, segments = S.enumerate_all(proj)
    base = S.wire_keys_base(proj)
    ports_by_id = {M.text(p["record_id"]): p for p in proj.ports}
    partners, covered, _ = S.port_partner_index(proj, ports_by_id)
    prod_ext = S.external_candidates(proj, base, lambda fid, h: base.get((fid, h), (fid, h)))
    cut2 = S.cut_positions(proj, cands, groups, roots, segments, use_elements=True)
    mapping2 = S.mapping_from_cuts(groups, roots, base, cut2)
    m2_ext = S.external_candidates(proj, mapping2, lambda fid, h: base.get((fid, h), (fid, h)))
    m2_set = {tuple(sorted([M.text(a["record_id"]), M.text(b["record_id"])])) for _, a, b, _, _ in m2_ext}
    for key, a, b, ia, ib in prod_ext:
        k = tuple(sorted([M.text(a["record_id"]), M.text(b["record_id"])]))
        if k in m2_set:
            continue
        ra, rb = M.text(a["record_id"]), M.text(b["record_id"])
        if partners.get(ra) or partners.get(rb):
            continue  # only the 'new_both_ports' removals
        # find the group containing the wire
        fid = M.text(a["file_id"])
        h = None
        for c in DI._contacts_of(a):
            if M.text(c.get("wire_handle")):
                h = M.text(c["wire_handle"])
                break
        gi = None
        for i, (g, gk) in enumerate(groups):
            if any(M.text(proj.line_by_key[x]["handle"]) == h for x in gk if x in proj.line_by_key):
                gi = i
                break
        info = {"pid": proj.pid, "a": ra, "b": rb, "ia": ia, "ib": ib, "group": None}
        if gi is not None:
            g, gk = groups[gi]
            pieces = G.piece_extents(gk, segments, roots[gi])
            ys = [segments[x]["sy"] for x in gk]
            y = sum(ys) / len(ys)
            cuts = sorted(cut2.get(gi, []))
            gaps = []
            for i in range(len(pieces) - 1):
                x0, x1 = pieces[i]["xmax"], pieces[i + 1]["xmin"]
                gaps.append({"i": i, "w": round(x1 - x0, 2), "cut": i in cuts,
                             "unreg": S.unreg_span(proj, fid, x0, x1, y) if hasattr(S, "unreg_span") else None})
            info["group"] = {"gid": g["line_group_id"], "pieces": len(pieces), "lines": len(gk), "gaps": gaps,
                             "orient": g["orientation"]}
        out.append(info)
print("removed new_both candidates", len(out))
print(collections.Counter(len(x["group"]["gaps"]) if x["group"] else -1 for x in out))
gapc = collections.Counter()
for x in out:
    if x["group"]:
        for gp in x["group"]["gaps"]:
            if gp["cut"]:
                gapc[(gp["w"], bool(gp["unreg"]))] += 1
print("cut gap widths (width, unreg-span):", gapc.most_common(12))
json.dump(out, open("F:/workspace/XJToolkit/.tmp/multiseg_work/removed_new.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for x in out[:6]:
    print(x)
