import sys, json, collections
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
import ezdxf, ezdxf.bbox
from dwg_audit.extract.superworks_semantics import entity_insert_wcs, text_anchor_wcs
proj, fid, x0, y0, x1, y1 = sys.argv[1], sys.argv[2], *map(float, sys.argv[3:7])
doc = ezdxf.readfile(dxf_path(proj, fid))
def xd(e):
    try:
        return {a: [str(t.value)[:50] for t in tags][:12] for a, tags in e.xdata.items()}
    except Exception:
        return {}
rows = []
for e in doc.modelspace():
    t = e.dxftype()
    try:
        bb = ezdxf.bbox.extents([e])
    except Exception:
        continue
    if not bb.has_data:
        continue
    if bb.extmax.x < x0 or bb.extmin.x > x1 or bb.extmax.y < y0 or bb.extmin.y > y1:
        continue
    rec = {"type": t, "handle": e.dxf.handle, "layer": e.dxf.layer,
           "bbox": [round(bb.extmin.x, 2), round(bb.extmin.y, 2), round(bb.extmax.x, 2), round(bb.extmax.y, 2)]}
    if t == "INSERT":
        rec["block"] = e.dxf.name
        p = entity_insert_wcs(e); rec["insert"] = [round(p.x, 2), round(p.y, 2)]
    if t in ("TEXT", "MTEXT"):
        a = text_anchor_wcs(e)
        rec["text"] = e.dxf.text if t == "TEXT" else e.plain_text()
        rec["anchor"] = [round(a.x, 2), round(a.y, 2)]
    if t == "LINE":
        rec["start"] = [round(e.dxf.start.x, 2), round(e.dxf.start.y, 2)]
        rec["end"] = [round(e.dxf.end.x, 2), round(e.dxf.end.y, 2)]
    x = xd(e)
    if x:
        rec["xdata"] = x
    rows.append(rec)
print("n", len(rows))
c = collections.Counter((r["type"], r["layer"]) for r in rows)
print(dict(c))
for r in rows:
    print(json.dumps(r, ensure_ascii=False))
