"""解析 LD_SYMB2LOGGEN_DICTIONARY 下的导线记录（OBJECTS 中的 XRECORD），逐文件只读统计。

记录结构（代码 1 的 键/值 交替串）:
  LINENO            : "未定义<句柄>:<端口>"  （对端端子 句柄:端口；未带页名，多为同页）
  LINECOLOR         : 颜色（多为空）
  LINEDIAMETER      : 线径（多为空）
  LINESTYLE         : 导线类型，如 "电流回路线:*" / "电压回路线:&" / "四芯屏蔽线:@"
  CONNECTLINEHANDLE : 导线实体句柄（LINE）
  PART2_<n>         : 端点 n 的串，以 '||' 分隔：
                      [0]'' [1]设备名 [2]引脚 [3]序号 [4]侧('左'/'右'/'') [5]符号块名 [6]端子实体句柄 [7]类别(端子/装置端子/…) [9]方向 ...

输出每文件一个 JSON，记录包括解析后的端点列表与句柄解析情况（句柄是否存在于本页、实体类型）。
用法: python parse_loggen.py --index <page_index.json> --work <dir> [--workers 8]
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

LINENO_RE = re.compile(r"未定义([0-9A-Fa-f]+):(\w+)")


def _parse_part2(s):
    t = s.split("||")
    g = lambda i: (t[i].strip() if len(t) > i else "")
    return {"device": g(1), "pin": g(2), "ord": g(3), "side": g(4), "block": g(5),
            "far_handle": g(6), "kind": g(7), "direction": g(9), "raw": s[:160]}


def _scan(row):
    doc = ezdxf.readfile(row["dxf_path"])
    out = {"project_id": row["project_id"], "file_id": row["file_id"], "filename": row["filename"],
           "page_type": row["page_type"], "family": row["family"], "dxf_path": row["dxf_path"], "records": []}
    if "LD_SYMB2LOGGEN_DICTIONARY" not in doc.rootdict:
        return out
    root = doc.rootdict["LD_SYMB2LOGGEN_DICTIONARY"]
    for name, x in root.items():
        pairs = {}
        parts = {}
        strings = [str(t.value) for t in x.tags if t.code == 1]
        for i in range(0, len(strings) - 1, 2):
            k, v = strings[i], strings[i + 1]
            if k.startswith("PART2_"):
                parts[k] = _parse_part2(v)
            else:
                pairs[k] = v
        if "CONNECTLINEHANDLE" not in pairs:
            continue
        ln = pairs.get("LINENO", "")
        m = LINENO_RE.search(ln)
        rec = {"name": name, "xrec": x.dxf.handle, "lineno_raw": ln,
               "far_handle": m.group(1).upper() if m else "", "far_port": m.group(2) if m else "",
               "linestyle": pairs.get("LINESTYLE", ""), "linecolor": pairs.get("LINECOLOR", ""),
               "linediameter": pairs.get("LINEDIAMETER", ""), "wire": pairs.get("CONNECTLINEHANDLE", "").strip().upper(),
               "ends": [parts[k] for k in sorted(parts, key=lambda s: int(s.split("_")[1]))]}
        ent = doc.entitydb.get(rec["wire"]) if rec["wire"] else None
        rec["wire_type"] = ent.dxftype() if ent is not None else "MISSING"
        fe = doc.entitydb.get(rec["far_handle"]) if rec["far_handle"] else None
        rec["far_type"] = fe.dxftype() if fe is not None else ("MISSING" if rec["far_handle"] else "")
        for e in rec["ends"]:
            h = e["far_handle"].upper()
            ee = doc.entitydb.get(h) if h else None
            e["far_resolves_type"] = ee.dxftype() if ee is not None else ("MISSING" if h else "")
        out["records"].append(rec)
    return out


def _job(args):
    row, work = args
    name = f"{row['project_id']}_{row['file_id']}.json"
    path = os.path.join(work, name)
    if os.path.exists(path):
        return name
    try:
        res = _scan(row)
    except Exception:
        res = {"project_id": row["project_id"], "file_id": row["file_id"], "error": traceback.format_exc()[-300:]}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    rows = json.load(open(args.index, encoding="utf-8"))
    jobs = [(r, args.work) for r in rows]
    with Pool(args.workers) as pool:
        n = 0
        for _ in pool.imap_unordered(_job, jobs, chunksize=1):
            n += 1
            if n % 400 == 0:
                print("files", n, flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
