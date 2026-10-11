import sys, json
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/MULTI-SEG/tools")
import ms_common as M
import ms_geom as G
import ms_sim as S

pid, port_id = sys.argv[1], sys.argv[2]
proj = M.Project(pid, next((M.ROUND / pid).glob("*/findings")))
cands, groups, roots, segments = S.enumerate_all(proj)
base = S.wire_keys_base(proj)
port = proj.port_by_id[port_id]
fid = M.text(port["file_id"])
print("port", port_id, "identity", port["endpoint_identity"], "cat", port["category"], "insert", port["insert_handle"])
contacts = M.DI._contacts_of(port)
print("contacts", contacts)
for c in contacts:
    h = M.text(c["wire_handle"])
    key = base.get((fid, h))
    print("handle", h, "base key", key)
    # find groups containing that handle
    for gi, (g, keys) in enumerate(groups):
        hs = [M.text(proj.line_by_key[k]["handle"]) for k in keys if k in proj.line_by_key]
        if h in hs:
            pieces = G.piece_extents(keys, segments, roots[gi])
            print(" group", gi, g["line_group_id"], "orient", g["orientation"], "lines", len(keys), "pieces", len(pieces))
            for p in pieces:
                print("   piece", round(p["xmin"], 3), round(p["xmax"], 3), round(p["y"], 3))
            cut1 = S.cut_positions(proj, cands, groups, roots, segments, use_elements=False)
            cut2 = S.cut_positions(proj, cands, groups, roots, segments, use_elements=True)
            print("   M1 cuts", sorted(cut1.get(gi, [])), "M2 cuts", sorted(cut2.get(gi, [])))
            for i in range(len(pieces) - 1):
                x0, x1 = pieces[i]["xmax"], pieces[i + 1]["xmin"]
                el = S.element_in_gap(proj, fid, x0, x1, pieces[0]["y"], keys)
                print("   gap", i, round(x0, 3), round(x1, 3), "element_in_gap", el)
                for port2 in proj.ports:
                    if M.text(port2["file_id"]) != fid:
                        continue
                    coords = [M.DI._number(port2.get(k)) for k in ("start_x", "start_y", "end_x", "end_y")]
                    if None in coords:
                        continue
                    mx, my = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
                    if x0 - 2 <= mx <= x1 + 2 and abs(my - pieces[0]["y"]) <= 2.5:
                        print("      TP near gap", M.text(port2["record_id"]), M.text(port2["category"]), M.text(port2["endpoint_identity"]), round(mx, 3), round(my, 3))
