"""对指定 appid 做取值探测（只读，逐文件）。

每个 appid 输出：
  - 字符串取值（代码 1000/1004）计数（每文件 top 60）
  - 句柄取值（代码 1005）指向的实体类型计数，以及目标为 TEXT/MTEXT/ATTRIB 时的文字计数
  - 数值取值（代码 1040/1070/1010 等）的最小/最大/样例
  - 每个 appid 的前 3 个样例（句柄 + 页面）
按 (page_type) 分桶，便于判断“只在哪类页出现”。

用法: python value_probe.py --index <page_index.json> --work <dir> --apps A,B,C [--workers 8]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import traceback
from multiprocessing import Pool

import ezdxf


def _txt(e):
    try:
        if e.dxftype() == "MTEXT":
            return e.plain_text()
        if e.dxftype() in ("TEXT", "ATTRIB"):
            return e.dxf.text
    except Exception:
        return None
    return None


def _probe_file(row, apps):
    doc = ezdxf.readfile(row["dxf_path"])
    acc = collections.defaultdict(lambda: {"str": collections.Counter(), "h_type": collections.Counter(),
                                            "h_text": collections.Counter(), "num": [], "num_codes": collections.Counter(),
                                            "ex": [], "ents": collections.Counter()})

    def visit(entities, scope):
        for e in entities:
            if not e.xdata:
                continue
            for app, tags in e.xdata.data.items():
                if app not in apps:
                    continue
                a = acc[app]
                a["ents"][f"{scope}|{e.dxftype()}"] += 1
                vals = [(t.code, t.value) for t in tags if t.code != 1001]
                if len(a["ex"]) < 3:
                    a["ex"].append({"handle": e.dxf.handle, "scope": scope, "etype": e.dxftype(),
                                    "vals": [[c, str(v)[:60]] for c, v in vals[:6]]})
                for c, v in vals:
                    if c in (1000, 1004):
                        if len(a["str"]) < 60 or str(v)[:60] in a["str"]:
                            a["str"][str(v)[:60]] += 1
                    elif c == 1005:
                        tgt = doc.entitydb.get(str(v))
                        if tgt is None:
                            a["h_type"]["MISSING"] += 1
                        else:
                            a["h_type"][tgt.dxftype()] += 1
                            t = _txt(tgt)
                            if t is not None:
                                a["h_text"][t[:40]] += 1
                    elif isinstance(v, (int, float)):
                        a["num_codes"][c] += 1
                        if len(a["num"]) < 400:
                            a["num"].append(round(float(v), 3) if isinstance(v, float) else int(v))
                    elif isinstance(v, tuple):
                        a["num_codes"][c] += 1

    visit(doc.modelspace(), "MS")
    for blk in doc.blocks:
        if blk.name.startswith("*Paper"):
            continue
        visit(blk, "BLK")
    out = {}
    for app, a in acc.items():
        out[app] = {"str": dict(a["str"]), "h_type": dict(a["h_type"]), "h_text": dict(a["h_text"].most_common(40)),
                    "num_codes": {str(k): v for k, v in a["num_codes"].items()},
                    "num_min": min(a["num"]) if a["num"] else None, "num_max": max(a["num"]) if a["num"] else None,
                    "ents": dict(a["ents"]), "ex": a["ex"]}
    return out


def _worker(args):
    row, apps, work = args
    name = f"{row['project_id']}_{row['file_id']}.json"
    path = os.path.join(work, name)
    try:
        res = {"project_id": row["project_id"], "file_id": row["file_id"], "page_type": row["page_type"],
               "family": row["family"], "filename": row["filename"], "apps": _probe_file(row, apps)}
    except Exception:
        res = {"project_id": row["project_id"], "file_id": row["file_id"], "error": traceback.format_exc()[-300:]}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--apps", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    apps = set(args.apps.split(","))
    rows = json.load(open(args.index, encoding="utf-8"))
    jobs = [(r, apps, args.work) for r in rows]
    with Pool(args.workers) as pool:
        for i, _ in enumerate(pool.imap_unordered(_worker, jobs, chunksize=1)):
            if (i + 1) % 400 == 0:
                print("files", i + 1, flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
