"""Read-only census: legacy strip identity (header + row) vs DZ_SERIALNUMBER_NAME identity.

Walks modelspace only (same scope as extract_superworks_semantics' strip loop).
Usage: python identity_census.py --out <json> [--projects p000 p001 ...] [--workers 3]
"""
import argparse, json, sys, unicodedata
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import ezdxf

ROOT = Path(__file__).resolve().parents[5]
CORPUS = ROOT / ".planning/superworks-adapter/corpus_manifest.json"


def norm(value):
    # Same as dwg_audit.extract.superworks_semantics.normalize (NFKC + candidates helper).
    v = unicodedata.normalize("NFKC", value)
    import re
    v = re.sub(r"\s*/\s*", "/", v.strip())
    return re.sub(r"\s+", " ", v)


def xv(entity, app, code):
    if entity is None or not entity.xdata or app not in entity.xdata.data:
        return []
    return [str(t.value) for t in entity.xdata.data[app] if t.code == code and str(t.value) not in ("", "0")]


def text_of(entity):
    if entity is None:
        return None
    if entity.dxftype() == "MTEXT":
        return entity.plain_text()
    if entity.dxftype() in ("TEXT", "ATTRIB"):
        return entity.dxf.text
    return None


def scan_file(path):
    doc = ezdxf.readfile(path)
    out = []
    for e in doc.modelspace():
        if not e.xdata or "LD_DZPNO_HEADHANDLE" not in e.xdata.data:
            continue
        hh = (xv(e, "LD_DZPNO_HEADHANDLE", 1005) or [""])[0]
        header_text = text_of(doc.entitydb.get(hh)) if hh else None
        row_text = text_of(e)
        dz = xv(e, "DZ_SERIALNUMBER_NAME", 1000)
        dz_name = dz[0] if dz else None
        out.append({"row_handle": e.dxf.handle, "row_text": row_text, "header_text": header_text,
                    "header_handle": hh, "dz_name": dz_name})
    return out


def scan_project(job):
    pid, files = job
    rows = []
    for f in files:
        try:
            recs = scan_file(f["dxf_path"])
        except Exception as exc:  # keep census going, record the failure
            recs = [{"error": repr(exc)}]
        for r in recs:
            r["project_id"] = pid
            r["file_id"] = f["file_id"]
            r["filename"] = f["filename"]
        rows.extend(recs)
    return pid, rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--projects", nargs="*")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))["projects"]
    jobs = [(p["project_id"], p["files"]) for p in corpus
            if (not a.projects or p["project_id"] in a.projects)
            and not (outdir / f'{p["project_id"]}.json').exists()]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        for pid, rows in pool.map(scan_project, jobs):
            (outdir / f"{pid}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            print(pid, len(rows), flush=True)
    print("done", flush=True)
