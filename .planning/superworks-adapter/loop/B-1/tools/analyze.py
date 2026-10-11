"""Collect per-target evidence for the five R-PAIR-MISSING-SIDE items (read-only)."""
import sys, json, re, math
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
import ezdxf, ezdxf.bbox
from dwg_audit.extract.superworks_semantics import text_anchor_wcs


def pj(v):
    try:
        return json.loads(v) if isinstance(v, str) else v
    except Exception:
        return v


def nz(v):
    return None if v is None or (isinstance(v, float) and v != v) else v


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(px - qx, py - qy), (qx, qy)


def xdata_apps(e):
    """XDATA keys (ezdxf XData.data is keyed by the application/record name)."""
    try:
        data = e.xdata.data
    except Exception:
        return {}
    out = {}
    for key, tags in data.items():
        vals = []
        for t in list(tags)[:6]:
            vals.append(str(getattr(t, "value", t))[:40])
        out[str(key)] = vals
    return out


results = {}
for proj, run, pid, fid, sid, name in TARGETS:
    print("analyzing", name, flush=True)
    pairs = table(proj, run, "pairs")
    lgs = table(proj, run, "line_groups")
    tx = table(proj, run, "texts")
    tc = table(proj, run, "terminal_candidates")
    ps = table(proj, run, "primitive_segments")
    pi = table(proj, run, "sw_part_instances")
    sup = table(proj, run, "superworks_supersession")
    pg = table(proj, run, "pages")
    lines_round = table(proj, run, "lines")
    pr = pairs[pairs.pair_id == pid].iloc[0]
    lg = lgs[lgs.line_group_id == pr.line_group_id].iloc[0]
    members = json.loads(lg.member_line_ids) if isinstance(lg.member_line_ids, str) else list(lg.member_line_ids)
    left_tid = pr.left_text_id
    lt = tx[tx.text_id == left_tid].iloc[0]
    pgrow = pg[pg.sheet_id == sid].iloc[0]

    doc = ezdxf.readfile(dxf_path(proj, fid))
    msp = doc.modelspace()
    by_handle = {str(e.dxf.handle): e for e in msp if e.dxf.hasattr("handle")}

    sx, sy, ex, ey = float(lg.start_x), float(lg.start_y), float(lg.end_x), float(lg.end_y)
    lr = lines_round[(lines_round.sheet_id == sid) & (lines_round.file_id == fid)]
    cand_lines = lr[((lr.start_y - sy).abs() < 0.01) & ((lr.end_y - ey).abs() < 0.01) & ((lr.start_x - sx).abs() < 0.05)]
    stub_handles = [str(h) for h in cand_lines.handle.tolist()]

    if abs(sx - lt.insert_x) < abs(ex - lt.insert_x):
        identified = (sx, sy)
        missing = (ex, ey)
        side_name = "left"
    else:
        identified = (ex, ey)
        missing = (sx, sy)
        side_name = "right"

    numeral_e = by_handle.get(str(lt.handle))
    num_info = dict(
        text_id=lt.text_id, handle=str(lt.handle), text=lt.text, layer=lt.layer,
        raw_dxf_height=(float(numeral_e.dxf.height) if numeral_e is not None and numeral_e.dxftype() == "TEXT" else None),
        engine_clamped_height=float(lt.height),
        engine_insert=[round(float(lt.insert_x), 4), round(float(lt.insert_y), 4)],
        xdata_apps=xdata_apps(numeral_e) if numeral_e is not None else [])

    cand = tc[tc.line_group_id == pr.line_group_id]
    cand_rows = cand[["candidate_id", "side", "text_id", "text", "score", "status", "rejection_reason", "channel",
                      "endpoint_x", "endpoint_y"]].to_dict("records")

    cx, cy = (sx + ex) / 2, (sy + ey) / 2
    near = tx[(tx.sheet_id == sid) & ((tx.insert_x - cx).abs() <= 28) & ((tx.insert_y - cy).abs() <= 28)]
    near_rows = []
    for _, t in near.iterrows():
        e = by_handle.get(str(t.handle))
        ap = text_anchor_wcs(e) if (e is not None and e.dxftype() in ("TEXT", "MTEXT")) else None
        near_rows.append(dict(
            text_id=t.text_id, handle=str(t.handle), layer=t.layer, text=t.text,
            engine_insert=[round(float(t.insert_x), 3), round(float(t.insert_y), 3)],
            dxf_anchor=None if ap is None else [round(ap.x, 3), round(ap.y, 3)],
            dxf_halign=None if e is None else nz(e.dxf.get("halign")),
            dxf_valign=None if e is None else nz(e.dxf.get("valign")),
            dxf_height=(float(e.dxf.height) if (e is not None and e.dxftype() == "TEXT") else None),
            engine_height=float(t.height),
            is_numeric_candidate=bool(t.is_numeric_candidate),
            dist_to_stub_mid=round(dist(t.insert_x, t.insert_y, cx, cy), 2),
            xdata_apps=xdata_apps(e) if e is not None else []))

    pss = ps[(ps.sheet_id == sid) & (ps.file_id == fid)]
    best = []
    for _, p in pss.iterrows():
        if p.primitive_kind not in ("LINE", "CIRCLE", "ARC"):
            continue
        if str(p.entity_handle) in stub_handles:
            continue
        g = pj(p.world_geometry_json)
        if not isinstance(g, dict):
            continue
        if p.primitive_kind == "LINE":
            s = g.get("start")
            en = g.get("end")
            if not s or not en:
                continue
            d, q = seg_dist(missing[0], missing[1], s[0], s[1], en[0], en[1])
            best.append((d, "LINE", str(p.entity_handle), p.layer, p.definition_name,
                         [round(q[0], 3), round(q[1], 3)], [round(s[0], 3), round(s[1], 3), round(en[0], 3), round(en[1], 3)]))
        elif p.primitive_kind == "CIRCLE":
            c = g.get("center")
            r = g.get("radius", 0)
            if not c:
                continue
            d = abs(dist(missing[0], missing[1], c[0], c[1]) - r)
            best.append((d, "CIRCLE", str(p.entity_handle), p.layer, p.definition_name,
                         [round(c[0], 3), round(c[1], 3)], [round(r, 3)]))
    best.sort(key=lambda x: x[0])
    nearest_geom = [dict(distance=round(b[0], 3), kind=b[1], handle=b[2], layer=b[3], block=b[4],
                         closest_point_or_center=b[5], geom=b[6]) for b in best[:5]]

    tb = []
    for _, t in tx[tx.sheet_id == sid].iterrows():
        if str(t.handle) == str(lt.handle):
            continue
        dx = max(t.bbox_min_x - missing[0], 0, missing[0] - t.bbox_max_x)
        dy = max(t.bbox_min_y - missing[1], 0, missing[1] - t.bbox_max_y)
        tb.append((math.hypot(dx, dy), t.text_id, str(t.handle), t.layer, t.text))
    tb.sort(key=lambda x: x[0])
    nearest_text = [dict(distance_to_bbox=round(a, 3), text_id=b, handle=c, layer=d, text=e) for a, b, c, d, e in tb[:5]]

    sw_inst = []
    for _, x in pi[pi.sheet_id == sid].iterrows():
        lab = pj(x.label) or {}
        pn = pj(x.part_no) or {}
        ports = pj(x.ports) or []
        port_rows = []
        for p in ports:
            c = []
            if p.get("start_x") is not None:
                c.append((p["start_x"], p["start_y"]))
            if p.get("end_x") is not None:
                c.append((p["end_x"], p["end_y"]))
            dmis = min([dist(mx, my, missing[0], missing[1]) for mx, my in c]) if c else None
            port_rows.append(dict(port=str(p.get("port_number")), endpoint=p.get("endpoint_identity"),
                                  coords=[[round(a, 3), round(b, 3)] for a, b in c],
                                  dist_to_missing_end=None if dmis is None else round(dmis, 3)))
        sw_inst.append(dict(instance_path=x.instance_path, block_name=x.block_name, insert_handle=x.insert_handle,
                            label=dict(value=lab.get("value"), text_id=lab.get("text_id"), handle=lab.get("handle")),
                            part_no=dict(value=pn.get("value"), text_id=pn.get("text_id"), handle=pn.get("handle")),
                            part_type=x.part_type, n_ports=len(ports), ports=port_rows[:10]))
    stub_sw = [s for s in sw_inst if s["part_no"]["text_id"] == lt.text_id]

    sup_hits = int(sup.astype(str).apply(lambda c: c.str.contains(str(lt.text_id)), axis=0).any(axis=1).sum())
    stub_xd = {h: xdata_apps(by_handle[h]) for h in stub_handles if h in by_handle}

    inserts = []
    for e in msp:
        if e.dxftype() != "INSERT":
            continue
        if e.dxf.name.startswith("*"):
            continue
        try:
            bb = ezdxf.bbox.extents([e])
        except Exception:
            continue
        if not bb.has_data:
            continue
        if bb.extmax.x < sx - 30 or bb.extmin.x > ex + 30 or bb.extmax.y < sy - 40 or bb.extmin.y > sy + 40:
            continue
        if bb.extmax.x - bb.extmin.x > 300:
            continue
        x0, y0, x1, y1 = bb.extmin.x, bb.extmin.y, bb.extmax.x, bb.extmax.y
        gap = None
        if x0 <= cx <= x1:
            gap = round(min(abs(sy - y1), abs(sy - y0)), 2) if not (y0 <= sy <= y1) else 0.0
        inserts.append(dict(handle=e.dxf.handle, block=e.dxf.name, layer=e.dxf.layer,
                            bbox=[round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                            xdata_apps=xdata_apps(e), gap_to_stub_line=gap))

    touch = []
    for e in msp:
        if e.dxf.hasattr("handle") and str(e.dxf.handle) in stub_handles:
            continue
        try:
            bb = ezdxf.bbox.extents([e])
        except Exception:
            continue
        if not bb.has_data:
            continue
        if bb.extmax.x < missing[0] - 1.0 or bb.extmin.x > missing[0] + 1.0 or bb.extmax.y < missing[1] - 1.0 or bb.extmin.y > missing[1] + 1.0:
            continue
        touch.append(dict(type=e.dxftype(), handle=e.dxf.handle, layer=e.dxf.layer,
                          bbox=[round(bb.extmin.x, 2), round(bb.extmin.y, 2), round(bb.extmax.x, 2), round(bb.extmax.y, 2)]))

    results[name] = dict(
        project=proj, run=run, pair_id=pid, file_id=fid, sheet_id=sid,
        filename=pgrow.filename, sheet_no=pgrow.sheet_no, sheet_title=pgrow.sheet_title,
        sheet_category=pgrow.sheet_category, page_type=pgrow.page_type,
        pair=dict(status=pr.status, rationale=pr.rationale, confidence=float(pr.confidence), pair_kind=pr.pair_kind,
                  selected_pair_candidate_id=pr.selected_pair_candidate_id, left_value=str(pr.left_value),
                  left_text_id=left_tid, left_candidate_id=pr.left_candidate_id),
        line_group=dict(line_group_id=pr.line_group_id, member_line_ids=members, layer_hints=pj(lg.layer_hints),
                        start=[round(sx, 3), round(sy, 3)], end=[round(ex, 3), round(ey, 3)],
                        length=round(float(lg.length), 3), orientation=lg.orientation,
                        stub_handles=stub_handles, stub_xdata=stub_xd),
        identified_side=side_name,
        identified_point=[round(identified[0], 3), round(identified[1], 3)],
        missing_point=[round(missing[0], 3), round(missing[1], 3)],
        numeral=num_info,
        terminal_candidates_of_group=cand_rows,
        nearby_texts=near_rows,
        nearest_geometry_to_missing_end=nearest_geom,
        nearest_text_bbox_to_missing_end=nearest_text,
        entities_touching_missing_end_1unit=touch,
        inserts_near_stub=inserts,
        sw_part_instances_on_sheet=sw_inst,
        sw_part_with_numeral=stub_sw,
        supersession_rows_mentioning_numeral=sup_hits,
    )
    print("  ok", name, "missing", results[name]["missing_point"], "touch", len(touch),
          "nearest geom", (nearest_geom[0]["distance"] if nearest_geom else None), flush=True)

json.dump(results, open(OUT / "tools" / "_facts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("written")
