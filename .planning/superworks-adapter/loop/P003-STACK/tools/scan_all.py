"""Read-only scan of p003 frozen DXF cache: every TEXT/MTEXT/ATTRIB whose text matches the 8n label family.
Covers modelspace, INSERT-exploded virtual entities (nested) and ATTRIBs. Writes JSON for README table."""
import sys, json, re
from pathlib import Path
sys.path.insert(0, "F:/workspace/XJToolkit/src")
import ezdxf
from dwg_audit.extract.superworks_semantics import entity_insert_wcs, text_anchor_wcs

MAN = json.load(open("F:/workspace/XJToolkit/.planning/superworks-adapter/corpus_manifest.json", encoding="utf-8"))
P3 = [p for p in MAN["projects"] if p["project_id"] == "p003"][0]
PAT = re.compile(r"^(8n[A-Za-z]?\d{2,3}|8[nN][A-Za-z]\d{2}|\d{3})$")  # 8nB01, 8n401, 8nD02, 8n818 ...; bare 3-digit
PAT8 = re.compile(r"8n")
def txt(e):
    if e.dxftype() == "MTEXT":
        return e.plain_text()
    return e.dxf.get("text", "") or ""
def hx(e):
    return e.dxf.handle if e.dxf.hasattr("handle") else ""
out = []
for f in P3["files"]:
    doc = ezdxf.readfile(f["dxf_path"])
    msp = doc.modelspace()
    title = ""
    for e in msp:
        if e.dxftype() in ("TEXT", "MTEXT") and e.dxf.layer == "BOARD" and "图" in txt(e):
            title = txt(e); break
    rows = []
    def collect(entities, container):
        for e in entities:
            if e.dxftype() in ("TEXT", "MTEXT", "ATTRIB"):
                s = txt(e).strip()
                if PAT8.search(s) or re.fullmatch(r"(401|402|405|818|820|821|822|8[0-9]{2})", s):
                    a = text_anchor_wcs(e)
                    rows.append(dict(file=f["file_id"], sheet_title=title, filename=f["filename"], container=container,
                                     text=s, type=e.dxftype(), handle=e.dxf.handle, layer=e.dxf.layer,
                                     ax=round(a.x, 3), ay=round(a.y, 3)))
    collect(msp, "modelspace")
    # INSERT-exploded nested text (block definitions, attributes)
    for ins in msp.query("INSERT"):
        try:
            vents = list(ins.virtual_entities())
        except Exception:
            vents = []
        collect(vents, f"INSERT {ins.dxf.name}@{ins.dxf.handle}")
        collect(ins.attribs, f"INSERT {ins.dxf.name}@{ins.dxf.handle} (ATTRIB)")
    out.extend(rows)
    print(f["file_id"], f["filename"], "title=", title, "hits=", len(rows), file=sys.stderr)
Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/P003-STACK/tools/scan_all.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("total", len(out))
