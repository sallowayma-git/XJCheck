"""Scan frozen DXFs (read-only) for SYMB2 INSERTs that carry label/term-text links, grouped by presence of LD_SYMB2_SPECIAL.
Usage: scan_symb2.py <out_pickle> [pid ...]"""
import json, sys, time, pickle
from pathlib import Path
import ezdxf
man = json.loads(Path("F:/workspace/XJToolkit/.planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
out = sys.argv[1]
only = set(sys.argv[2:])
def txt(doc, h):
    e = doc.entitydb.get(h) if h else None
    if e is None: return None
    if e.dxftype()=="MTEXT": return e.plain_text()
    if e.dxftype() in ("TEXT","ATTRIB"): return e.dxf.text
    return None
def xd(e, app):
    if not e.xdata or app not in e.xdata.data: return None
    return [(t.code, str(t.value)) for t in e.xdata.data[app]]
rows=[]
t0=time.time()
for proj in man["projects"]:
    pid=proj["project_id"]
    if only and pid not in only: continue
    for f in proj["files"]:
        path=f["dxf_path"]
        try:
            doc=ezdxf.readfile(path)
        except Exception as exc:
            try:
                from ezdxf import recover
                doc,_=recover.readfile(path)
            except Exception as exc2:
                rows.append(dict(pid=pid,file=f["file_id"],error=str(exc2)[:200])); continue
        seen=set()
        spaces=[("model", doc.modelspace())]+[("block:"+b.name, b) for b in doc.blocks if not b.name.startswith("*")]
        for owner, space in spaces:
            for e in space:
                if e.dxftype()!="INSERT" or not e.xdata: continue
                apps=set(e.xdata.data.keys())
                if not any(a.startswith("LD_SYMB2_") for a in apps): continue
                has_label = "LD_SYMB2_LABEL" in apps
                tt=[a for a in apps if a.startswith("LD_SYMB2_TERM_TEXT_")]
                rows.append(dict(pid=pid, file=f["file_id"], handle=e.dxf.handle, owner=owner, block=e.dxf.name,
                    special=next((v for c,v in (xd(e,"LD_SYMB2_SPECIAL") or []) if c==1000), None),
                    has_special="LD_SYMB2_SPECIAL" in apps, has_label=has_label,
                    label_text=txt(doc, (xd(e,"LD_SYMB2_LABEL") or [(0,None)])[-1][1]) if has_label else None,
                    term_texts={a.removeprefix("LD_SYMB2_TERM_TEXT_"): txt(doc, (xd(e,a) or [(0,None),(0,None),(0,None)])[-1][1]) for a in tt},
                    apps=sorted(a for a in apps)))
        doc=None
    print(pid, len(rows), round(time.time()-t0,1), flush=True)
pickle.dump(rows, open(out,"wb"))
print("saved", len(rows))
