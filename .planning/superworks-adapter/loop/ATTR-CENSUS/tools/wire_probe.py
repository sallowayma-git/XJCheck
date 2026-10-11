"""导线侧一致性探测（只读，仅处理含 LD_PARTCONNECTLINE 记录的文件）。

对每条引脚记录：
  - 直线句柄 -> LINE：读取该线上的 LD_LINE_STYLE / LD_LINE_COLORCODE / LD_LINE_DIAMETER / LD_LINE_COLORVALUE；
  - 接线文字句柄 -> TEXT：读取文字值；
  - 线号文字句柄 / 导线颜色代号文字句柄 / 接地文字句柄 -> TEXT：读取文字值（为空或 0 则记为 none）；
  - LINE 是否同时被 LDPARTLAYT_LINE_HANDLE 等元件侧 XDATA 引用（反向核对）；
  - 记录中的导线类型 与 LINE 的 LD_LINE_STYLE 是否一致。

用法: python wire_probe.py --index <page_index.json> --pcl <pcl dir> --work <dir> [--workers 8]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import traceback
from multiprocessing import Pool

import ezdxf


def _text(e):
    if e is None:
        return None
    t = e.dxftype()
    if t == "MTEXT":
        return e.plain_text()
    if t in ("TEXT", "ATTRIB"):
        return e.dxf.text
    return None


def _xd(e, app):
    if e is None or not e.xdata or app not in e.xdata.data:
        return []
    return [str(t.value) for t in e.xdata.data[app] if t.code != 1001]


def _job(args):
    row, pcl_path, work = args
    name = f"{row['project_id']}_{row['file_id']}.json"
    out_path = os.path.join(work, name)
    try:
        d = json.load(open(pcl_path, encoding="utf-8"))
        doc = ezdxf.readfile(row["dxf_path"])
        # 元件侧 LDPARTLAYT_LINE_HANDLE 的反向引用集合
        part_line_refs = set()
        for e in doc.modelspace():
            if e.xdata and "LDPARTLAYT_LINE_HANDLE" in e.xdata.data:
                for h in _xd(e, "LDPARTLAYT_LINE_HANDLE"):
                    part_line_refs.add(h.upper())
        c = collections.Counter()
        style_pairs = collections.Counter()
        ex = []
        for rec in d.get("records", []):
            h = (rec.get("直线句柄") or "").strip().upper()
            line = doc.entitydb.get(h) if h else None
            if line is None or line.dxftype() != "LINE":
                c["line_missing"] += 1
                continue
            style = (_xd(line, "LD_LINE_STYLE") or [""])[0]
            c["line_style_" + ("empty" if not style else "set")] += 1
            wt = (rec.get("导线类型") or "").strip()
            if wt and style:
                c["type_vs_style_" + ("agree" if wt == style else "differ")] += 1
            elif not wt and style:
                c["type_empty_style_set"] += 1
            elif wt and not style:
                c["type_set_style_empty"] += 1
            style_pairs[(wt or "-", style or "-")] += 1
            if h in part_line_refs:
                c["line_also_in_part_handle"] += 1
            for f in ("接线文字句柄", "线号文字句柄", "导线颜色代号文字句柄", "接地文字句柄"):
                hh = (rec.get(f) or "").strip().upper()
                te = doc.entitydb.get(hh) if hh else None
                t = _text(te)
                c[f"{f}_" + ("none" if t is None else ("empty" if not t.strip() else "text"))] += 1
            if len(ex) < 6:
                ex.append({"pin": rec.get("pin"), "line": h, "style": style, "wt": wt,
                           "text_conn": _text(doc.entitydb.get((rec.get("接线文字句柄") or "").strip().upper())),
                           "far": [rec.get("far_component"), rec.get("far_pin")]})
        res = {"project_id": row["project_id"], "file_id": row["file_id"], "page_type": row["page_type"],
               "family": row["family"], "counts": dict(c), "style_pairs": [[list(k), v] for k, v in style_pairs.most_common(60)],
               "examples": ex}
    except Exception:
        res = {"project_id": row["project_id"], "file_id": row["file_id"], "error": traceback.format_exc()[-300:]}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--pcl", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    rows = json.load(open(args.index, encoding="utf-8"))
    jobs = []
    for r in rows:
        p = os.path.join(args.pcl, f"{r['project_id']}_{r['file_id']}.json")
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            if d.get("records"):
                jobs.append((r, p, args.work))
    print("jobs", len(jobs), flush=True)
    with Pool(args.workers) as pool:
        for _ in pool.imap_unordered(_job, jobs, chunksize=1):
            pass
    print("done", flush=True)


if __name__ == "__main__":
    main()
