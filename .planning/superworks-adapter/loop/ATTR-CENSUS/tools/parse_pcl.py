"""解析 LD_PARTCONNECTLINE 扩展字典 / OBJECTS 中的 XRECORD（元件引脚 -> 导线 记录）并做全语料统计。

记录结构（代码 1 字符串序列，每个逻辑端号占 10 段，顺序固定）：
  逻辑端号:<pin> | 线号:<wire label，可含 未定义<句柄>:<端口>_<页号> <页名>> | 导线类型:<类型>
  | 线号文字句柄:<h> | 导线颜色代号文字句柄:<h> | 接线文字句柄:<h> | 直线句柄:<h>
  | 接地图块句柄:<h> | 接地文字句柄:<h> | 对端元件:<元件>||<空>||<端子号>||端子||导线类型:..||导线颜色代号:..

只读。逐文件处理，输出每文件一个 JSON 到工作目录。
用法: python parse_pcl.py --index <page_index.json> --work <dir> [--workers 8]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import traceback
from multiprocessing import Pool

import ezdxf

FIELD_ORDER = ["逻辑端号", "线号", "导线类型", "线号文字句柄", "导线颜色代号文字句柄", "接线文字句柄",
               "直线句柄", "接地图块句柄", "接地文字句柄", "对端元件"]
XREF_RE = re.compile(r"未定义([0-9A-Fa-f]+):(\w+?)_(\d+)\s*(.*)")


def parse_records(strings):
    """把代码 1 字符串序列切成引脚记录。"""
    recs, cur = [], None
    for s in strings:
        if ":" not in s:
            continue
        key, val = s.split(":", 1)
        key = key.strip()
        if key == "逻辑端号":
            if cur:
                recs.append(cur)
            cur = {"pin": val.strip()}
            continue
        if cur is None:
            continue
        if key == "对端元件":
            parts = val.split("||")
            cur["far_component"] = parts[0].strip()
            cur["far_pin"] = parts[2].strip() if len(parts) > 2 else ""
            cur["far_kind"] = parts[3].strip() if len(parts) > 3 else ""
            cur["far_raw"] = val
        elif key in FIELD_ORDER:
            cur[key] = val.strip()
    if cur:
        recs.append(cur)
    return recs


def _classify_wire_label(v):
    if not v:
        return "empty"
    m = XREF_RE.search(v)
    if m:
        return "crosspage_undefined_handle"
    return "plain"


def scan_file(row, doc_cache=None):
    doc = ezdxf.readfile(row["dxf_path"])
    out = {"project_id": row["project_id"], "file_id": row["file_id"], "filename": row["filename"],
           "page_type": row["page_type"], "family": row["family"], "dxf_path": row["dxf_path"]}
    entities = []        # (owner_kind, owner_handle, owner_type, xrec_handle, records)
    seen_xrec = set()

    def add_xrec(x, owner_kind, owner_handle, owner_type):
        if x.dxf.handle in seen_xrec:
            return
        seen_xrec.add(x.dxf.handle)
        strings = [str(t.value) for t in x.tags if t.code == 1]
        recs = parse_records(strings)
        if recs:
            entities.append((owner_kind, owner_handle, owner_type, x.dxf.handle, recs))

    for e in doc.modelspace():
        if e.has_extension_dict:
            try:
                d = e.get_extension_dict().dictionary
                if "LD_PARTCONNECTLINE" in d:
                    add_xrec(d["LD_PARTCONNECTLINE"], "ext", e.dxf.handle, e.dxftype())
            except Exception:
                out.setdefault("errors", []).append("ext")
    for o in doc.objects:
        if o.dxftype() == "DICTIONARY":
            try:
                for k, v in o.items():
                    if k == "LD_PARTCONNECTLINE" and v.dxftype() == "XRECORD":
                        out.setdefault("dict_owner_handles", []).append(o.dxf.handle)
            except Exception:
                pass
    for o in doc.objects:
        if o.dxftype() == "XRECORD" and o.dxf.handle not in seen_xrec:
            strings = [str(t.value) for t in o.tags if t.code == 1]
            if any(s.startswith("逻辑端号:") for s in strings):
                add_xrec(o, "obj", "", "XRECORD")

    def resolve(h):
        if not h:
            return None
        try:
            ent = doc.entitydb.get(h)
        except Exception:
            ent = None
        return ent.dxftype() if ent is not None else "MISSING"

    rows = []
    for owner_kind, owner_handle, owner_type, xh, recs in entities:
        for r in recs:
            rec = {"owner_kind": owner_kind, "owner": owner_handle, "owner_type": owner_type, "xrec": xh}
            rec.update({k: r.get(k) for k in FIELD_ORDER + ["far_component", "far_pin", "far_kind"]})
            rec["pin"] = r.get("pin")  # 逻辑端号的规范化键名（同时保留原始键 逻辑端号）
            rec["wire_label_class"] = _classify_wire_label(r.get("线号", ""))
            m = XREF_RE.search(r.get("线号", "") or "")
            if m:
                rec["xref_handle"] = m.group(1).upper()
                rec["xref_port"] = m.group(2)
                rec["xref_page"] = m.group(3)
                rec["xref_pagename"] = m.group(4).strip()
                rec["xref_handle_resolves_here"] = resolve(m.group(1).upper())
            for f in ("直线句柄", "接线文字句柄", "线号文字句柄", "导线颜色代号文字句柄", "接地图块句柄", "接地文字句柄"):
                h = (r.get(f) or "").strip()
                rec[f + "_resolves"] = resolve(h) if h else None
            rows.append(rec)
    out["records"] = rows
    out["n_xrec"] = len(entities)
    return out


def _worker(args):
    row, work = args
    name = f"{row['project_id']}_{row['file_id']}.json"
    path = os.path.join(work, name)
    if os.path.exists(path):
        return name, "cached"
    try:
        res = scan_file(row)
    except Exception:
        res = {"project_id": row["project_id"], "file_id": row["file_id"],
               "error": traceback.format_exc()[-400:]}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    return name, "error" if res.get("error") else "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    rows = json.load(open(args.index, encoding="utf-8"))
    jobs = [(r, args.work) for r in rows]
    stat = collections.Counter()
    with Pool(args.workers) as pool:
        for i, (_, st) in enumerate(pool.imap_unordered(_worker, jobs, chunksize=1)):
            stat[st] += 1
    print("done", dict(stat), flush=True)


if __name__ == "__main__":
    main()
