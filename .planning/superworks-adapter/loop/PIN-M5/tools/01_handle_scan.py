"""PIN-M5 step 1: handle-link census (read-only).

Pass A: for every frozen DXF, list every 1005 (handle) XDATA / XRECORD value that does NOT resolve
        inside its own file, with owner kind and appid.
Pass B: for every project, check whether those dangling values resolve in another file of the same
        project (cross-drawing handle link). Resolved hits report the target entity type.
Usage: python -X utf8 01_handle_scan.py <out_dir> [workers]
Outputs: <out_dir>/passA/<fid>.json, <out_dir>/dangling_by_project.json, <out_dir>/passB/<fid>.json,
         <out_dir>/summary.json
"""
import json, os, sys, collections
from multiprocessing import Pool
import ezdxf

ROOT = "F:/workspace/XJToolkit"
MAN = json.load(open(os.path.join(ROOT, ".planning/superworks-adapter/corpus_manifest.json"), encoding="utf-8"))
OUT = sys.argv[1]
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
FILES = []
for p in MAN["projects"]:
    for f in p["files"]:
        FILES.append({"pid": p["project_id"], "fid": f["file_id"], "dxf": f["dxf_path"]})


def iter_owners(doc):
    """Yield (owner_kind, owner_handle, owner_dxftype, xdata_dict) for entities and XRECORDs."""
    seen = set()
    for layout in [doc.modelspace()] + [b for b in doc.blocks]:
        for e in layout:
            if e.dxftype() in ("INSERT",) or True:
                if e.xdata is not None:
                    yield ("xdata_" + ("model" if layout is doc.modelspace() else "block"), e.dxf.handle, e.dxftype(),
                           e.xdata.data)
                if e.dxftype() in ("INSERT", "LINE", "TEXT", "MTEXT", "LWPOLYLINE") and e.has_extension_dict:
                    try:
                        d = e.get_extension_dict().dictionary
                        for k in d.keys():
                            x = d[k]
                            if x.dxftype() == "XRECORD":
                                tags = [(t.code, t.value) for t in x.tags]
                                yield ("extdict:" + k, e.dxf.handle, e.dxftype(), {"__xrec": tags})
                    except Exception:
                        pass
    for o in doc.objects:
        if o.dxftype() == "XRECORD" and o.dxf.handle not in seen:
            seen.add(o.dxf.handle)
            yield ("objects_xrecord", o.dxf.handle, "XRECORD", {"__xrec": [(t.code, t.value) for t in o.tags]})


def handle_refs(data):
    """Yield (appid, value) for every 1005 tag in an xdata dict or an XRECORD."""
    if "__xrec" in data:
        for code, val in data["__xrec"]:
            if code == 1005:
                yield ("XRECORD", str(val).strip().upper())
        return
    for appid, tags in data.items():
        for code, val in tags:
            if code == 1005:
                yield (appid, str(val).strip().upper())


def pass_a(item):
    fid, dxf = item["fid"], item["dxf"]
    out = {"pid": item["pid"], "fid": fid, "dangling": [], "n_refs": 0, "error": None}
    try:
        doc = ezdxf.readfile(dxf)
        db = doc.entitydb
        for kind, owner, otype, data in iter_owners(doc):
            for appid, h in handle_refs(data):
                out["n_refs"] += 1
                if not h or h in ("0",):
                    continue
                if db.get(h) is None:
                    out["dangling"].append({"kind": kind, "owner": owner, "otype": otype, "appid": appid, "h": h})
    except Exception as ex:
        out["error"] = repr(ex)[:300]
    with open(os.path.join(OUT, "passA", fid + "_" + item["pid"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    return fid, len(out["dangling"]), out["error"]


def pass_b(args):
    item, cand = args
    out = {"pid": item["pid"], "fid": item["fid"], "hits": [], "error": None}
    try:
        doc = ezdxf.readfile(item["dxf"])
        db = doc.entitydb
        for h in cand:
            e = db.get(h)
            if e is not None:
                out["hits"].append({"h": h, "type": e.dxftype()})
    except Exception as ex:
        out["error"] = repr(ex)[:300]
    with open(os.path.join(OUT, "passB", item["fid"] + "_" + item["pid"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    return item["fid"], len(out["hits"])


if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "passA"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "passB"), exist_ok=True)
    with Pool(WORKERS) as pool:
        resA = list(pool.imap_unordered(pass_a, FILES, chunksize=2))
    errs = [r for r in resA if r[2]]
    print("passA done", len(resA), "errors", len(errs), flush=True)
    # dangling candidate handles per project (union over files)
    per_proj = collections.defaultdict(set)
    for item in FILES:
        path = os.path.join(OUT, "passA", item["fid"] + "_" + item["pid"] + ".json")
        d = json.load(open(path, encoding="utf-8"))
        for r in d["dangling"]:
            per_proj[item["pid"]].add(r["h"])
    json.dump({k: sorted(v) for k, v in per_proj.items()}, open(os.path.join(OUT, "dangling_by_project.json"), "w", encoding="utf-8"))
    jobs = [(item, sorted(per_proj.get(item["pid"], ()))) for item in FILES if per_proj.get(item["pid"])]
    with Pool(WORKERS) as pool:
        resB = list(pool.imap_unordered(pass_b, jobs, chunksize=2))
    print("passB done", len(resB), flush=True)
