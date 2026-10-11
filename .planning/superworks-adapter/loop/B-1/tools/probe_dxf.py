import sys, json
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
import ezdxf
from dwg_audit.extract.superworks_semantics import entity_insert_wcs, text_anchor_wcs
from ezdxf.math import Vec3
proj, file_id, cx, cy, r = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
doc = ezdxf.readfile(dxf_path(proj, file_id))
msp = doc.modelspace()
print("layers", len(doc.layers), "blocks", len(doc.blocks))
rows = []
def xd(e):
    out = {}
    try:
        for app, tags in e.xdata.items():
            out[app] = [ (t.code, str(t.value)[:60]) for t in tags][:14]
    except Exception:
        pass
    return out
for e in msp:
    t = e.dxftype()
    if t in ("INSERT",):
        p = entity_insert_wcs(e)
        name = e.dxf.name
        if abs(p.x-cx) <= r and abs(p.y-cy) <= r:
            rows.append(("INSERT", e.dxf.handle, e.dxf.layer, name, round(p.x,2), round(p.y,2), xd(e)))
    elif t in ("TEXT", "MTEXT", "ATTRIB"):
        p = text_anchor_wcs(e) if t != "ATTRIB" else entity_insert_wcs(e)
        txt = e.dxf.text if t == "TEXT" else (e.text if t=="MTEXT" else e.dxf.text)
        if t == "MTEXT":
            txt = e.plain_text()
        if abs(p.x-cx) <= r and abs(p.y-cy) <= r:
            rows.append((t, e.dxf.handle, e.dxf.layer, repr(txt)[:40], round(p.x,2), round(p.y,2), xd(e)))
    elif t in ("LINE",):
        s, en = e.dxf.start, e.dxf.end
        if min(s.x,en.x) <= cx+r and max(s.x,en.x) >= cx-r and min(s.y,en.y) <= cy+r and max(s.y,en.y) >= cy-r:
            rows.append(("LINE", e.dxf.handle, e.dxf.layer, "", (round(s.x,2),round(s.y,2)), (round(en.x,2),round(en.y,2)), xd(e)))
    elif t in ("LWPOLYLINE","POLYLINE","ARC","CIRCLE","SOLID","HATCH","ELLIPSE","SPLINE"):
        try:
            bb = ezdxf.bbox.extents([e])
            if bb.has_data and bb.extmin.x <= cx+r and bb.extmax.x >= cx-r and bb.extmin.y <= cy+r and bb.extmax.y >= cy-r:
                rows.append((t, e.dxf.handle, e.dxf.layer, "", (round(bb.extmin.x,2),round(bb.extmin.y,2)), (round(bb.extmax.x,2),round(bb.extmax.y,2)), xd(e)))
        except Exception as ex:
            pass
for row in rows:
    print(json.dumps(row, ensure_ascii=False, default=str))
print("n", len(rows))
