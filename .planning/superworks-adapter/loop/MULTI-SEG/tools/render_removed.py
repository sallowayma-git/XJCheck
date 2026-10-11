import sys, json
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/MULTI-SEG/tools")
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")
import ms_common as M
import ms_geom as G
import ms_sim as S
import ms_render as RN
import gap_render as R

items = json.load(open("F:/workspace/XJToolkit/.tmp/multiseg_work/removed_new.json", encoding="utf-8"))
picks = [items[0], items[4], items[60], items[90]]
cache = {}
panels = []
header = []
for it in picks:
    pid = it["pid"]
    if pid not in cache:
        proj = M.Project(pid, next((M.ROUND / pid).glob("*/findings")))
        cands, groups, roots, segments = S.enumerate_all(proj)
        cache[pid] = (proj, cands, groups, roots, segments)
    proj, cands, groups, roots, segments = cache[pid]
    ports = {M.text(p["record_id"]): p for p in proj.ports}
    pa, pb = ports[it["a"]], ports[it["b"]]
    base = S.wire_keys_base(proj)
    # the production group containing port a's contact handle
    h = next(M.text(c["wire_handle"]) for c in M.DI._contacts_of(pa) if M.text(c.get("wire_handle")))
    gi = next(i for i, (g, gk) in enumerate(groups) if any(M.text(proj.line_by_key[x]["handle"]) == h for x in gk if x in proj.line_by_key))
    g, keys = groups[gi]
    cand = {"keys": keys, "roots": roots[gi], "port_a": pa, "port_b": pb, "file_id": M.text(pa["file_id"]),
            "orientation": g["orientation"], "ca": (0, 0), "cb": (0, 0)}
    pieces = G.piece_extents(keys, segments, roots[gi])
    ys = [segments[x]["sy"] for x in keys]
    y = sum(ys) / len(ys)
    x_lo = min(p["xmin"] for p in pieces) - 14
    x_hi = max(p["xmax"] for p in pieces) + 14
    wide = (x_lo, y - 12, x_hi, y + 12)
    zc = (pieces[0]["xmax"] + pieces[1]["xmin"]) / 2
    zoom = (zc - 9, y - 9, zc + 9, y + 9)
    head = "removed %s  %s  %s|%s  group %s" % (pid, g["line_group_id"], it["ia"], it["ib"], g["line_group_id"])
    panels.append(RN.panel_for(proj, None, cand, groups, roots, segments, wide, head + "\nwide view"))
    panels.append(RN.panel_for(proj, None, cand, groups, roots, segments, zoom, head + "\nzoom on the M2 cut"))
    header.append(head)
R.render(M.ROOT / ".tmp" / "multiseg_work" / "removed_new_check.png", header, panels, cols=2)
print("ok")
