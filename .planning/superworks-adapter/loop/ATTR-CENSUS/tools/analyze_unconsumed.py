"""估算新属性对“未消费端口”的潜在覆盖（只读）。

输入: unconsumed_port_diagnostics.json（4727 条未消费端口）、页面索引、parse_pcl.py 的逐文件输出。
port_id 段结构: SW:<file_id>:<sheet_id>:<instance 路径段...>:<标记句柄>:<端口号>
  - 实例句柄取 instance 段的最后一个句柄（去掉前导 '/'）。
检查项:
  1. 同文件 PCL 记录中是否存在 owner == 实例句柄 且 逻辑端号 == 端口号 （直接引脚命中）；
  2. 同文件内是否存在 owner == 实例句柄 的任意记录（实例命中，但引脚号可能不同）；
  3. 若 1 命中，其 对端元件+端子号 是否等于 端口的 endpoint_identity（去向一致性）；
  4. 页型分布。
用法: python analyze_unconsumed.py --diag <json> --index <page_index.json> --pcl <dir> --out <json>
"""
from __future__ import annotations

import argparse
import collections
import json
import os


def _parse_port_id(pid):
    parts = pid.split(":")
    if len(parts) < 6 or parts[0] != "SW":
        return None
    file_id, sheet_id = parts[1], parts[2]
    rest = parts[3:]
    # 末尾为 端口号；其前为 标记句柄；再往前为实例路径段
    port_no = rest[-1]
    marker = rest[-2]
    inst_segs = [s.strip("/") for s in rest[:-2] if s.strip("/")]
    inst = inst_segs[-1] if inst_segs else ""
    return {"file_id": file_id, "sheet_id": sheet_id, "instance": inst, "marker": marker, "port_no": port_no}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--pcl", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    diag = json.load(open(args.diag, encoding="utf-8"))
    idx = {(r["project_id"], r["file_id"]): r for r in json.load(open(args.index, encoding="utf-8"))}
    cache = {}

    def pcl_for(pid, fid):
        key = (pid, fid)
        if key not in cache:
            p = os.path.join(args.pcl, f"{pid}_{fid}.json")
            cache[key] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"records": []}
        return cache[key]

    c = collections.Counter()
    by_pt = collections.defaultdict(collections.Counter)
    ex = []
    for row in diag:
        pid = row["project_id"]
        pr = _parse_port_id(row["port_id"])
        if pr is None:
            c["unparsed"] += 1
            continue
        meta = idx.get((pid, pr["file_id"]))
        pt = meta["page_type"] if meta else "?"
        by_pt[pt]["ports"] += 1
        recs = pcl_for(pid, pr["file_id"]).get("records", [])
        same_inst = [r for r in recs if r.get("owner") == pr["instance"]]
        exact = [r for r in same_inst if (r.get("pin") or "").strip() == pr["port_no"]]
        if exact:
            c["exact_pin_in_same_file"] += 1
            by_pt[pt]["exact"] += 1
            far = [(r.get("far_component") or "") + (r.get("far_pin") or "") for r in exact]
            ident = row.get("endpoint_identity") or ""
            if ident and any(f == ident for f in far):
                c["far_identity_equals_endpoint_identity"] += 1
                by_pt[pt]["far_eq_identity"] += 1
            elif ident and any(f.replace("||", "") == ident for f in far):
                c["far_identity_equals_endpoint_identity_loose"] += 1
            if len(ex) < 12:
                ex.append({"port": row["port_id"], "identity": ident, "far": far[:2], "pt": pt})
        elif same_inst:
            c["instance_in_pcl_pin_differs"] += 1
            by_pt[pt]["inst_only"] += 1
        else:
            c["no_pcl_owner_in_file"] += 1
            by_pt[pt]["none"] += 1
    out = {"total": len(diag), "counts": dict(c), "by_page_type": {k: dict(v) for k, v in by_pt.items()},
           "examples": ex}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["counts"], ensure_ascii=False))
    print(json.dumps(out["by_page_type"], ensure_ascii=False))


if __name__ == "__main__":
    main()
