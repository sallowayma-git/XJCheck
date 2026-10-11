"""端子排行身份缺陷检查（只读）。

  1. 全语料：流水线 sw_strip_rows.parquet 中表头文字为 "上接<端子排名><行号>" 等续接说明的行数，
     以及其 endpoint_identity（如 "上接1QD1516"），与 DZ_SERIALNUMBER_NAME 拼接得到的真实身份（如 "1QD16"）对比。
  2. 未消费端口：其 endpoint_identity 在 DZ 口径（stripdest 索引）中存在、但在流水线表头口径身份集合中缺失的数量。

用法: python strip_identity_check.py --round12 <dir> --stripdest <dir> --diag <json> --out <json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re

import pyarrow.parquet as pq


def _pid_of(path):
    parts = path.replace(chr(92), "/").split("/")
    return next(x for x in parts if re.fullmatch(r"p\d{3}", x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round12", required=True)
    ap.add_argument("--stripdest", required=True)
    ap.add_argument("--diag", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    C = collections.Counter()
    ex = []
    hdr_ids = collections.defaultdict(set)
    for f in glob.glob(os.path.join(args.round12, "p*", "*", "findings", "sw_strip_rows.parquet")):
        pid = _pid_of(f)
        for r in pq.read_table(f, columns=["header", "row", "endpoint_identity", "record_id"]).to_pylist():
            C["strip_rows"] += 1
            if r["endpoint_identity"]:
                hdr_ids[pid].add(r["endpoint_identity"])
            hd = json.loads(r["header"]) if isinstance(r["header"], str) else (r["header"] or {})
            htxt = (hd or {}).get("value", "") or ""
            if htxt.startswith("上接") or "上接" in htxt:
                C["header_continuation_shangjie"] += 1
                if len(ex) < 6:
                    rw = json.loads(r["row"]) if isinstance(r["row"], str) else (r["row"] or {})
                    ex.append({"record_id": r["record_id"], "header": htxt,
                               "row_text": (rw or {}).get("value", ""), "pipeline_identity": r["endpoint_identity"]})

    dz_ids = collections.defaultdict(set)
    for f in glob.glob(os.path.join(args.stripdest, "p*.json")):
        pid = os.path.basename(f).replace(".json", "")
        for k in json.load(open(f, encoding="utf-8")).get("index", {}).keys():
            n, t = k.split("|", 1)
            dz_ids[pid].add(n + t)

    diag = json.load(open(args.diag, encoding="utf-8"))
    for d in diag:
        ident = (d.get("endpoint_identity") or "").strip()
        if not ident:
            C["unconsumed_no_identity"] += 1
            continue
        pid = d["project_id"]
        base = ident.split("~")[0]
        in_dz = base in dz_ids[pid]
        in_hdr = any(x == ident or x.split("~")[0] == base for x in hdr_ids[pid])
        if in_dz and not in_hdr:
            C["unconsumed_dz_row_but_header_identity_missing"] += 1
        elif in_dz and in_hdr:
            C["unconsumed_identity_in_both"] += 1
        elif in_hdr:
            C["unconsumed_header_only"] += 1
        else:
            C["unconsumed_neither_strip_identity"] += 1
    out = {"counts": dict(C), "examples_header_continuation": ex}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
