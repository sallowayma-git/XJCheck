"""汇总 parse_loggen.py 输出，并检验其对未消费端口的覆盖（只读）。

  A. 全语料统计：记录数、覆盖页数（按页型/家族）、导线类型（LINESTYLE）取值、颜色/线径非空率、端点数分布、
     CONNECTLINEHANDLE 解析类型（期望 LINE）、端子句柄解析类型（期望 INSERT）。
  B. 与未消费端口对齐（同项目、同文件）：
     B1 导线层：端口的接触导线句柄（sw_ports.parquet 的 wire_contacts）是否等于某条记录的 CONNECTLINEHANDLE；
     B2 端点层：某端点的 (端子句柄, 引脚) 与端口的 (实例句柄, 端口号) 相同；
     （身份一致性由 check_loggen_identity.py 以端子排去向索引检验，本脚本不做身份判断。）

用法: python analyze_loggen.py --loggen <dir> --diag <json> --round12 <dir> --index <page_index.json> --out <json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re

import pyarrow.parquet as pq

from analyze_unconsumed import _parse_port_id  # 同目录


def _norm_identity(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loggen", required=True)
    ap.add_argument("--diag", required=True)
    ap.add_argument("--round12", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    A = collections.Counter()
    by_pt = collections.Counter()
    pages_pt = collections.defaultdict(set)
    style = collections.Counter()
    color_nonempty = 0
    diam_nonempty = 0
    ends_hist = collections.Counter()
    wire_res = collections.Counter()
    far_res = collections.Counter()
    end_kind = collections.Counter()
    lineno_far_same_file = collections.Counter()
    recs_by_file = collections.defaultdict(list)
    for fp in glob.glob(os.path.join(args.loggen, "*.json")):
        d = json.load(open(fp, encoding="utf-8"))
        if d.get("error"):
            A["error_files"] += 1
            continue
        pt = d["page_type"]
        recs = d.get("records", [])
        if recs:
            pages_pt[pt].add((d["project_id"], d["file_id"]))
        for r in recs:
            A["records"] += 1
            by_pt[pt] += 1
            style[r.get("linestyle") or "(空)"] += 1
            if r.get("linecolor"):
                color_nonempty += 1
            if r.get("linediameter"):
                diam_nonempty += 1
            ends_hist[len(r.get("ends", []))] += 1
            wire_res[r.get("wire_type")] += 1
            if r.get("far_type") is not None:
                lineno_far_same_file[r.get("far_type") or "(无)"] += 1
            for e in r.get("ends", []):
                far_res[e.get("far_resolves_type") or "(无)"] += 1
                end_kind[e.get("kind") or "(空)"] += 1
            recs_by_file[(d["project_id"], d["file_id"])].append(r)
    A["pages_with_records"] = sum(len(v) for v in pages_pt.values())

    # B. 未消费端口对齐
    diag = json.load(open(args.diag, encoding="utf-8"))
    idx = json.load(open(args.index, encoding="utf-8"))
    pt_of = {(r["project_id"], r["file_id"]): r["page_type"] for r in idx}
    contacts = {}
    for p in glob.glob(os.path.join(args.round12, "p*", "*", "findings", "sw_ports.parquet")):
        m = re.search(r"[\\/](p\d{3})[\\/]", p)
        pid = m.group(1) if m else "?"
        for r in pq.read_table(p, columns=["record_id", "file_id", "wire_contacts"]).to_pylist():
            wc = r.get("wire_contacts") or "[]"
            if isinstance(wc, str):
                try:
                    wc = json.loads(wc)
                except Exception:
                    wc = []
            contacts[(pid, r["record_id"])] = (r["file_id"], [w.get("wire_handle", "").upper() for w in wc if w.get("wire_handle")])
    B = collections.Counter()
    B_by_pt = collections.defaultdict(collections.Counter)
    ex = []
    for d in diag:
        pid = d["project_id"]
        pr = _parse_port_id(d["port_id"])
        if pr is None:
            continue
        fid = pr["file_id"]
        pt = pt_of.get((pid, fid), "?")
        recs = recs_by_file.get((pid, fid), [])
        inst = pr["instance"].upper()
        port_no = str(pr["port_no"]).strip()
        ident = _norm_identity(d.get("endpoint_identity") or "")
        wires = set(contacts.get((pid, d["port_id"]), (None, []))[1])
        rec_wire = [r for r in recs if r.get("wire") in wires] if wires else []
        if rec_wire:
            B["B1_wire_in_loggen"] += 1
            B_by_pt[pt]["B1"] += 1
        exact = []
        for r in recs:
            for e in r.get("ends", []):
                if e.get("far_handle", "").upper() == inst and e.get("pin", "").strip() == port_no:
                    exact.append((r, e))
        if exact:
            B["B2_endpoint_exact"] += 1
            B_by_pt[pt]["B2"] += 1
        if not rec_wire and not exact:
            B["none"] += 1
            B_by_pt[pt]["none"] += 1
    # C. 两端记录与未消费端口的整条导线统计
    ukeys = set()
    for d in diag:
        pr = _parse_port_id(d["port_id"])
        if pr:
            ukeys.add((d["project_id"], pr["file_id"], pr["instance"].upper(), str(pr["port_no"]).strip()))
    C = collections.Counter()
    for (pid, fid), recs in recs_by_file.items():
        for r in recs:
            ends = r.get("ends", [])
            hit = [e for e in ends if (pid, fid, e.get("far_handle", "").upper(), e.get("pin", "").strip()) in ukeys]
            if hit:
                C["records_touching_unconsumed"] += 1
            if len(ends) == 2:
                C["two_end_records"] += 1
                if len(hit) == 2:
                    C["two_end_both_ends_unconsumed"] += 1
                elif len(hit) == 1:
                    C["two_end_one_end_unconsumed"] += 1
    out = {
        "C_pair_stats": dict(C),
        "A": dict(A),
        "by_page_type_records": dict(by_pt),
        "pages_by_type": {k: len(v) for k, v in pages_pt.items()},
        "linestyle_values": dict(style.most_common(30)),
        "linecolor_nonempty": color_nonempty,
        "linediameter_nonempty": diam_nonempty,
        "ends_per_record": dict(ends_hist),
        "wire_handle_type": dict(wire_res),
        "lineno_far_type": dict(lineno_far_same_file),
        "end_far_handle_type": dict(far_res),
        "B_unconsumed_total": len(diag),
        "B_counts": dict(B),
        "B_by_page_type": {k: dict(v) for k, v in B_by_pt.items()},
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("A", "B_counts", "pages_by_type")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
