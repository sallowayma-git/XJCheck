"""检验 PCL 跨页线号引用能否覆盖未消费的原理图端口（只读）。

PCL 线号 "未定义<H>:<端口>_<页号> <页名>" 指向目标页上的 装置端子 INSERT（句柄 H）与端口 端口号。
对每个未消费端口 (project, file_id, 实例句柄 instance, 端口号 port_no)，若存在某条 PCL 跨页引用
其 (目标文件 file_id, 目标句柄 H, 端口) 与之相同，则判为“跨页引用可覆盖”。
同时统计：反向（引用指向的目标端子，是否落在 未消费 集合中）。

用法: python crosspage_cover.py --diag <json> --index <page_index.json> --pcl <dir> --out <json>
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re

from analyze_unconsumed import _parse_port_id  # noqa: E402  (同目录)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--pcl", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    diag = json.load(open(args.diag, encoding="utf-8"))
    index = json.load(open(args.index, encoding="utf-8"))
    stem2fid = {}
    for r in index:
        stem = os.path.splitext(os.path.basename(r["dxf_path"]))[0]
        stem2fid[(r["project_id"], stem)] = r["file_id"]
    pid_set = {d["project_id"] for d in diag}
    refs = set()          # (pid, target_fid, handle, port)
    far_by_ref = collections.defaultdict(list)   # ref -> [对端标识（对端元件+端子号）]
    ref_src = collections.Counter()
    for r in index:
        if r["project_id"] not in pid_set:
            continue
    seen_files = set()
    for r in index:
        pid, fid = r["project_id"], r["file_id"]
        if pid not in pid_set or (pid, fid) in seen_files:
            continue
        seen_files.add((pid, fid))
        p = os.path.join(args.pcl, f"{pid}_{fid}.json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        for rec in d.get("records", []):
            if not rec.get("xref_handle"):
                continue
            key = f"{rec.get('xref_page')} {(rec.get('xref_pagename') or '').strip()}"
            tfid = stem2fid.get((pid, key))
            if not tfid:
                ref_src["target_page_missing"] += 1
                continue
            refs.add((pid, tfid, rec["xref_handle"].upper(), str(rec.get("xref_port") or "").strip()))
            far_by_ref[(pid, tfid, rec["xref_handle"].upper(), str(rec.get("xref_port") or "").strip())].append(
                (rec.get("far_component") or "") + (rec.get("far_pin") or ""))
    inst_index = {(x[0], x[1], x[2]) for x in refs}
    c = collections.Counter()
    by_pt = collections.defaultdict(collections.Counter)
    ex = []
    pt_map = {(r["project_id"], r["file_id"]): r["page_type"] for r in index}
    hit_keys = set()
    for d in diag:
        pr = _parse_port_id(d["port_id"])
        if not pr:
            continue
        pid = d["project_id"]
        key = (pid, pr["file_id"], pr["instance"].upper(), str(pr["port_no"]).strip())
        pt = pt_map.get((pid, pr["file_id"]), "?")
        by_pt[pt]["ports"] += 1
        if (pid, pr["file_id"], pr["instance"].upper(), str(pr["port_no"]).strip()) in refs:
            c["covered_by_crosspage_ref"] += 1
            by_pt[pt]["covered"] += 1
            hit_keys.add(key)
            fars = far_by_ref.get(key, [])
            ident = (d.get("endpoint_identity") or "").strip()
            if fars and ident:
                if any(f == ident for f in fars):
                    c["identity_equal"] += 1
                elif "~" in ident and any(re.match(r"^" + re.escape(f) + r"$", ident.split("~")[0]) or ident.startswith(f) for f in fars):
                    c["identity_range_prefix"] += 1
                else:
                    c["identity_differs"] += 1
            if len(ex) < 10:
                ex.append({"port": d["port_id"], "identity": d.get("endpoint_identity"), "far": fars[:2]})
        else:
            # 只记录实例句柄匹配但端口号不同的情况
            if (pid, pr["file_id"], pr["instance"].upper()) in inst_index:
                c["instance_referenced_port_differs"] += 1
                by_pt[pt]["inst_ref_port_differs"] += 1
            else:
                c["not_referenced"] += 1
                by_pt[pt]["not_referenced"] += 1
    out = {"total_unconsumed": len(diag), "crosspage_refs_unique": len(refs),
           "ref_source": dict(ref_src), "counts": dict(c),
           "by_page_type": {k: dict(v) for k, v in by_pt.items()}, "examples": ex}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["counts"], ensure_ascii=False), out["crosspage_refs_unique"])
    print(json.dumps(out["by_page_type"], ensure_ascii=False))


if __name__ == "__main__":
    main()
