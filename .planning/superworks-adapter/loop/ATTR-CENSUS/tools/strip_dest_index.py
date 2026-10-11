"""为每个项目建立 端子排行 身份 -> 去向文字 索引（只读，按项目并行）。

身份 = DZ_SERIALNUMBER_NAME（端子排名）+ 行文字（TEXT.text）；去向文字 = LDDZ_LEFT/RIGHTTEXT_HANDLE(_2) 指向的 TEXT/MTEXT 文字。
输出: work/<pid>.json = {"NAME|TEXT": [去向文字, ...], ...}
用法: python strip_dest_index.py --index <page_index.json> --work <dir> [--workers 8]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import traceback
from multiprocessing import Pool

import ezdxf

DEST_APPS = ("LDDZ_LEFTTEXT_HANDLE", "LDDZ_LEFTTEXT_HANDLE_2", "LDDZ_RIGHTTEXT_HANDLE", "LDDZ_RIGHTTEXT_HANDLE_2")


def _job(args):
    pid, rows, work = args
    out_path = os.path.join(work, f"{pid}.json")
    if os.path.exists(out_path):
        return pid
    try:
        idx = collections.defaultdict(list)
        for r in rows:
            if r["page_type"] != "屏端子图":
                continue
            doc = ezdxf.readfile(r["dxf_path"])
            for e in doc.modelspace():
                if e.dxftype() != "TEXT" or not e.xdata or "DZ_SERIALNUMBER_NAME" not in e.xdata.data:
                    continue
                name = next((str(t.value).strip() for t in e.xdata.data["DZ_SERIALNUMBER_NAME"] if t.code == 1000), "")
                key = f"{name}|{e.dxf.text.strip()}"
                for app in DEST_APPS:
                    for t in e.xdata.data.get(app, []):
                        if t.code != 1005 or str(t.value) in ("", "0"):
                            continue
                        x = doc.entitydb.get(str(t.value))
                        if x is None:
                            continue
                        txt = x.plain_text() if x.dxftype() == "MTEXT" else (x.dxf.text if x.dxftype() in ("TEXT", "ATTRIB") else "")
                        if txt:
                            idx[key].append(txt.strip())
        res = {"pid": pid, "index": dict(idx)}
    except Exception:
        res = {"pid": pid, "error": traceback.format_exc()[-300:]}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    return pid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    rows = json.load(open(args.index, encoding="utf-8"))
    by = collections.defaultdict(list)
    for r in rows:
        by[r["project_id"]].append(r)
    jobs = [(pid, rs, args.work) for pid, rs in sorted(by.items())]
    with Pool(args.workers) as pool:
        list(pool.imap_unordered(_job, jobs, chunksize=1))
    print("done", len(jobs), flush=True)


if __name__ == "__main__":
    main()
