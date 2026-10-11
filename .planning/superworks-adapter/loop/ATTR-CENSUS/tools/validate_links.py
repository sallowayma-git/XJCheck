"""校验 LD_PARTCONNECTLINE 记录中的两类去向引用（只读，按项目并行）。

  A. 跨页线号引用：线号 "未定义<H>:<端口>_<页号> <页名>" 中的句柄 H 是否存在于同项目
     中文件名为 "<页号> <页名>" 的 DXF 里（存在则给出目标实体类型）。
  B. 对端端子：对端元件 <X> + 端子号 <n> 能否在同项目 屏端子图 页中找到
     DZ_SERIALNUMBER_NAME == X 且 行文字 == n 的端子行（只统计 X 为普通端子名的记录）。

用法: python validate_links.py --index <page_index.json> --pcl <pcl dir> --work <dir> [--workers 8]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import traceback
from multiprocessing import Pool

import ezdxf

XREF_RE = re.compile(r"未定义([0-9A-Fa-f]+):(\w+?)_(\d+)\s*(.*)")


def _stem_of(path):
    return os.path.splitext(os.path.basename(path))[0]


def _project_job(args):
    pid, rows, pcl_dir, work = args
    out_path = os.path.join(work, f"{pid}.json")
    try:
        files = {}
        strip_rows = {}   # (name, text) -> [ {file, handle, dzlx, side} ]
        for r in rows:
            try:
                doc = ezdxf.readfile(r["dxf_path"])
            except Exception:
                continue
            stem = _stem_of(r["dxf_path"])
            handles = set()
            for h in doc.entitydb.keys():
                handles.add(h.upper())
            files[stem] = {"handles": handles, "page_type": r["page_type"], "file_id": r["file_id"]}
            if r["page_type"] == "屏端子图":
                for e in doc.modelspace():
                    if e.dxftype() != "TEXT" or not e.xdata or "DZ_SERIALNUMBER_NAME" not in e.xdata.data:
                        continue
                    name = ""
                    dzlx = ""
                    side = ""
                    for t in e.xdata.data["DZ_SERIALNUMBER_NAME"]:
                        if t.code == 1000:
                            name = str(t.value).strip()
                    for t in e.xdata.data.get("DZ_SERIALNUMBER_DZLX", []):
                        if t.code == 1000:
                            dzlx = str(t.value).strip()
                    for t in e.xdata.data.get("DZ_RightOrLeft", []):
                        if t.code == 1000:
                            side = str(t.value).strip()
                    key = (name, e.dxf.text.strip())
                    strip_rows.setdefault(key, []).append({"file": stem, "handle": e.dxf.handle, "dzlx": dzlx, "side": side})
        pcl_files = glob.glob(os.path.join(pcl_dir, f"{pid}_*.json"))
        a = collections.Counter()
        b = collections.Counter()
        a_ex, b_ex = [], []
        stems_by_pagekey = {}
        for s in files:
            m = re.match(r"^(\d+)\s+(.*)$", s)
            if m:
                stems_by_pagekey.setdefault(f"{m.group(1)} {m.group(2)}", []).append(s)
        for pf in pcl_files:
            d = json.load(open(pf, encoding="utf-8"))
            if d.get("error"):
                continue
            src_stem = _stem_of(d["dxf_path"])
            for rec in d.get("records", []):
                # A. 跨页线号
                if rec.get("xref_handle"):
                    key = f"{rec.get('xref_page')} {rec.get('xref_pagename', '').strip()}"
                    cands = stems_by_pagekey.get(key, [])
                    if not cands:
                        a["no_target_page_in_project"] += 1
                    else:
                        hit = any(rec["xref_handle"] in files[c]["handles"] for c in cands)
                        a["target_page_found_handle_" + ("yes" if hit else "no")] += 1
                        if hit and len(a_ex) < 15:
                            a_ex.append({"pid": pid, "src": src_stem, "xref": key, "handle": rec["xref_handle"]})
                    if rec.get("far_component", "").endswith("n"):
                        a["far_is_crosspage_marker_n"] += 1
                # B. 对端端子
                fc, fp = (rec.get("far_component") or "").strip(), (rec.get("far_pin") or "").strip()
                if fc and fp and not fc.endswith("n"):
                    hits = strip_rows.get((fc, fp), [])
                    b["strip_row_found" if hits else "strip_row_missing"] += 1
                    if hits:
                        b["dzlx_" + hits[0]["dzlx"]] += 1
                    if not hits and len(b_ex) < 15:
                        b_ex.append({"pid": pid, "src": src_stem, "far": [fc, fp]})
                    if hits and len(b_ex) < 15 and len(b_ex) < 30:
                        pass
                else:
                    b["far_not_terminal_or_marker"] += 1
        res = {"pid": pid, "files": len(files), "A": dict(a), "B": dict(b), "A_examples": a_ex, "B_missing_examples": b_ex,
               "strip_rows": sum(len(v) for v in strip_rows.values())}
    except Exception:
        res = {"pid": pid, "error": traceback.format_exc()[-500:]}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    return pid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--pcl", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    rows = json.load(open(args.index, encoding="utf-8"))
    by_pid = collections.defaultdict(list)
    for r in rows:
        by_pid[r["project_id"]].append(r)
    jobs = [(pid, rs, args.pcl, args.work) for pid, rs in sorted(by_pid.items())]
    with Pool(args.workers) as pool:
        done = 0
        for _ in pool.imap_unordered(_project_job, jobs, chunksize=1):
            done += 1
            if done % 10 == 0:
                print("projects", done, flush=True)
    print("done", len(jobs), flush=True)


if __name__ == "__main__":
    main()
