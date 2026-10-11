"""未消费端口的接触导线属性覆盖（只读）。

数据源:
  - unconsumed_port_diagnostics.json: 4727 个未消费端口（port_id）
  - .tmp/superworks_round12_full/p*/*/findings/sw_ports.parquet: 端口记录与 wire_contacts（接触导线句柄）
  - 原始 DXF（经 corpus_manifest 定位）: 读取接触导线上的 LD_LINE_STYLE、LD_ConnectLine 关联
逐项目处理，单个项目内逐 DXF 读取。

用法: python analyze_wire_style.py --diag <json> --round12 <dir> --index <page_index.json> --out <json> [--workers 8]
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
import pyarrow.parquet as pq


def _xd(e, app):
    if e is None or not e.xdata or app not in e.xdata.data:
        return []
    return [str(t.value) for t in e.xdata.data[app] if t.code != 1001]


def _job(args):
    pid, port_ids, ports_by_fid, parquet_rows, idx_rows = args
    res = {"pid": pid, "ports": 0, "with_contacts": 0, "contact_lines": 0, "line_found": 0,
           "style_set": 0, "style_empty": 0, "style_values": collections.Counter(), "any_style_port": 0,
           "connect_label_on_line": 0, "port_types": collections.Counter(), "errors": []}
    try:
        by_fid = collections.defaultdict(list)
        for r in parquet_rows:
            if r["record_id"] in port_ids:
                by_fid[r["file_id"]].append(r)
        for fid, rows in by_fid.items():
            path = idx_rows.get(fid)
            if not path:
                res["errors"].append("no_dxf:" + fid)
                continue
            doc = ezdxf.readfile(path)
            for r in rows:
                res["ports"] += 1
                res["port_types"][r.get("category") or ""] += 1
                wcs = r.get("wire_contacts") or []
                if isinstance(wcs, str):
                    wcs = json.loads(wcs) if wcs.strip() else []
                if wcs:
                    res["with_contacts"] += 1
                any_style = False
                for wc in wcs:
                    h = (wc.get("wire_handle") if isinstance(wc, dict) else None)
                    if not h:
                        continue
                    res["contact_lines"] += 1
                    e = doc.entitydb.get(h)
                    if e is None:
                        continue
                    res["line_found"] += 1
                    st = (_xd(e, "LD_LINE_STYLE") or [""])[0]
                    if st:
                        res["style_set"] += 1
                        res["style_values"][st] += 1
                        any_style = True
                    else:
                        res["style_empty"] += 1
                    if _xd(e, "LD_ConnectLine"):
                        res["connect_label_on_line"] += 1
                if any_style:
                    res["any_style_port"] += 1
        res["port_types"] = dict(res["port_types"])
        res["style_values"] = dict(res["style_values"])
    except Exception:
        res["errors"].append(traceback.format_exc()[-300:])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag", required=True)
    ap.add_argument("--round12", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    diag = json.load(open(args.diag, encoding="utf-8"))
    idx_rows = json.load(open(args.index, encoding="utf-8"))
    fid_path = {(r["project_id"], r["file_id"]): r["dxf_path"] for r in idx_rows}
    by_pid_ports = collections.defaultdict(set)
    for d in diag:
        by_pid_ports[d["project_id"]].add(d["port_id"])
    jobs = []
    for pid, port_ids in sorted(by_pid_ports.items()):
        rows = []
        for p in glob.glob(os.path.join(args.round12, pid, "*", "findings", "sw_ports.parquet")):
            rows += pq.read_table(p, columns=["record_id", "file_id", "category", "wire_contacts"]).to_pylist()
        fmap = {fid: path for (p2, fid), path in fid_path.items() if p2 == pid}
        jobs.append((pid, port_ids, None, rows, fmap))
    total = collections.Counter()
    per_pid = []
    with Pool(args.workers) as pool:
        for r in pool.imap_unordered(_job, jobs, chunksize=1):
            per_pid.append(r)
            for k in ("ports", "with_contacts", "contact_lines", "line_found", "style_set", "style_empty",
                      "connect_label_on_line", "any_style_port"):
                total[k] += r[k]
            total.update({"style_" + k: v for k, v in r["style_values"].items()})
    out = {"totals": {k: v for k, v in total.items() if not k.startswith("style_") or k in ("style_set", "style_empty")},
           "style_value_counts": {k: v for k, v in total.items() if k.startswith("style_") and k not in ("style_set", "style_empty")},
           "per_project": sorted(per_pid, key=lambda x: x["pid"]),
           "errors": [e for r in per_pid for e in r["errors"]][:20]}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["totals"], ensure_ascii=False))


if __name__ == "__main__":
    main()
