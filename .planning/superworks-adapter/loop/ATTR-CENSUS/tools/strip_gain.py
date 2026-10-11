"""端子排行的去向覆盖增益估算（只读，按项目并行）。

- 端子行: 屏端子图 模型空间中带 DZ_SERIALNUMBER_NAME 的 TEXT（行号文字=TEXT 的 text，所属端子排=DZ_SERIALNUMBER_NAME）。
- 现有去向: LDDZ_LEFTTEXT_HANDLE / LDDZ_RIGHTTEXT_HANDLE（及 _2 分支）指向的非零且可解析的文字。
- PCL 去向: parse_pcl 输出中 对端元件+对端端子 命中 (端子排名, 行文字) 的行。
统计: 总行数、已有去向行数、PCL 引用行数、PCL 新增行数（无现有去向但被 PCL 引用）。

用法: python strip_gain.py --index <page_index.json> --pcl <dir> --work <dir> --out <json> [--workers 8]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import traceback
from multiprocessing import Pool

import ezdxf


def _job(args):
    pid, rows, pcl_dir, work = args
    if os.path.exists(os.path.join(work, f"{pid}.json")):
        return pid
    try:
        strips = {}     # (name, text) -> list of dict
        total = 0
        for r in rows:
            if r["page_type"] != "屏端子图":
                continue
            doc = ezdxf.readfile(r["dxf_path"])
            for e in doc.modelspace():
                if e.dxftype() != "TEXT" or not e.xdata or "DZ_SERIALNUMBER_NAME" not in e.xdata.data:
                    continue
                name = next((str(t.value).strip() for t in e.xdata.data["DZ_SERIALNUMBER_NAME"] if t.code == 1000), "")
                has_dest = False
                for app in ("LDDZ_LEFTTEXT_HANDLE", "LDDZ_LEFTTEXT_HANDLE_2", "LDDZ_RIGHTTEXT_HANDLE", "LDDZ_RIGHTTEXT_HANDLE_2"):
                    for t in e.xdata.data.get(app, []):
                        if t.code == 1005 and str(t.value) not in ("", "0") and doc.entitydb.get(str(t.value)) is not None:
                            has_dest = True
                key = (name, e.dxf.text.strip())
                strips.setdefault(key, []).append({"file": r["file_id"], "handle": e.dxf.handle, "has_dest": has_dest})
                total += 1
        pcl_refs = set()     # (file, handle) referenced by PCL far-end
        far_total = 0
        far_match = 0
        for r in rows:
            p = os.path.join(pcl_dir, f"{pid}_{r['file_id']}.json")
            if not os.path.exists(p):
                continue
            d = json.load(open(p, encoding="utf-8"))
            for rec in d.get("records", []):
                fc = (rec.get("far_component") or "").strip()
                fp = (rec.get("far_pin") or "").strip()
                if not fc or not fp or fc.endswith("n"):
                    continue
                far_total += 1
                hits = strips.get((fc, fp), [])
                if hits:
                    far_match += 1
                    for h in hits:
                        pcl_refs.add((h["file"], h["handle"]))
        all_rows = [h for v in strips.values() for h in v]
        res = {
            "pid": pid,
            "strip_rows": total,
            "rows_with_existing_dest": sum(1 for h in all_rows if h["has_dest"]),
            "rows_referenced_by_pcl": len(pcl_refs),
            "rows_pcl_gain_no_existing_dest": sum(1 for h in all_rows if (h["file"], h["handle"]) in pcl_refs and not h["has_dest"]),
            "pcl_far_terminal_records": far_total,
            "pcl_far_terminal_matched_records": far_match,
        }
    except Exception:
        res = {"pid": pid, "error": traceback.format_exc()[-300:]}
    with open(os.path.join(work, f"{pid}.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    return pid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--pcl", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    rows = json.load(open(args.index, encoding="utf-8"))
    by = collections.defaultdict(list)
    for r in rows:
        by[r["project_id"]].append(r)
    jobs = [(pid, rs, args.pcl, args.work) for pid, rs in sorted(by.items())]
    with Pool(args.workers) as pool:
        list(pool.imap_unordered(_job, jobs, chunksize=1))
    tot = collections.Counter()
    errs = []
    for pid, *_ in jobs:
        d = json.load(open(os.path.join(args.work, f"{pid}.json"), encoding="utf-8"))
        if "error" in d:
            errs.append((pid, d["error"][-200:]))
            continue
        for k, v in d.items():
            if k != "pid":
                tot[k] += v
    out = {"totals": dict(tot), "errors": errs}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
