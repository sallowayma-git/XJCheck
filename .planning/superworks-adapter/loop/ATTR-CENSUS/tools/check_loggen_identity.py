"""检验 LOGGEN 导线记录“另一端”与端子排去向文字的一致性（只读）。

对每个被 LOGGEN 端点精确命中的未消费端口（同项目同文件，实例句柄+端口号）：
  - 取其 endpoint_identity（如 "7UD10"；区间写法 "ZD6~7" 取起点 "ZD6"）；
  - 在本项目端子排索引（strip_dest_index.py 输出）中按 "名称|行文字" 查找对应端子行，取其去向文字（如 "1ZKK-1"）；
  - 将 LOGGEN 记录中对端（非本端的端点）的 设备名+引脚 归一化（去 - 与空白）后，检查是否包含于去向文字归一化结果。
统计：身份在索引中找到的数量、找到去向文字的数量、一致/不一致数量。

用法: python check_loggen_identity.py --diag <json> --loggen <dir> --stripdest <dir> --index <page_index.json> --out <json>
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re

from analyze_unconsumed import _parse_port_id  # 同目录


def _norm(s: str) -> str:
    return re.sub(r"[\s\-_]", "", s or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag", required=True)
    ap.add_argument("--loggen", required=True)
    ap.add_argument("--stripdest", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    diag = json.load(open(args.diag, encoding="utf-8"))
    idx = {(r["project_id"], r["file_id"]): r["page_type"] for r in json.load(open(args.index, encoding="utf-8"))}
    sd_cache = {}

    def strip_index(pid):
        if pid not in sd_cache:
            p = os.path.join(args.stripdest, f"{pid}.json")
            sd_cache[pid] = json.load(open(p, encoding="utf-8")).get("index", {}) if os.path.exists(p) else {}
        return sd_cache[pid]

    lg_cache = {}

    def loggen(pid, fid):
        k = (pid, fid)
        if k not in lg_cache:
            p = os.path.join(args.loggen, f"{pid}_{fid}.json")
            lg_cache[k] = json.load(open(p, encoding="utf-8")).get("records", []) if os.path.exists(p) else []
        return lg_cache[k]

    C = collections.Counter()
    ex_bad = []
    for d in diag:
        pid = d["project_id"]
        pr = _parse_port_id(d["port_id"])
        if not pr:
            continue
        inst = pr["instance"].upper()
        port_no = str(pr["port_no"]).strip()
        recs = loggen(pid, pr["file_id"])
        hit = []
        for r in recs:
            for e in r.get("ends", []):
                if e.get("far_handle", "").upper() == inst and e.get("pin", "").strip() == port_no:
                    hit.append((r, e))
        if not hit:
            C["no_loggen_endpoint"] += 1
            continue
        C["loggen_endpoint"] += 1
        ident = (d.get("endpoint_identity") or "").strip()
        ident_key = ident.split("~")[0].strip()
        sidx = strip_index(pid)
        dests = None
        for k, v in sidx.items():
            if k.replace("|", "") == ident_key:
                dests = v
                break
        if not dests:
            C["identity_not_in_strip_index"] += 1
            continue
        C["identity_with_dest"] += 1
        dn = [_norm(x) for x in dests]
        agree = False
        others_any = False
        for r, e in hit:
            for o in r.get("ends", []):
                if o is e:
                    continue
                others_any = True
                cand = _norm(o.get("device", "") + o.get("pin", ""))
                if cand and any(cand in x for x in dn):
                    agree = True
        if not others_any:
            C["record_has_single_end"] += 1
        elif agree:
            C["other_end_agrees_with_dest"] += 1
        else:
            C["other_end_disagrees_with_dest"] += 1
            if len(ex_bad) < 10:
                ex_bad.append({"port": d["port_id"], "identity": ident, "dests": dests[:3],
                               "others": [[o.get("device"), o.get("pin")] for o in hit[0][0].get("ends", []) if o is not hit[0][1]][:3]})
    out = {"counts": dict(C), "disagree_examples": ex_bad}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
