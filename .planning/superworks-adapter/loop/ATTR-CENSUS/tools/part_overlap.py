"""PCL 引脚记录与流水线已提取的部件端口（sw_part_instances.ports）的重叠统计（只读）。

键: (项目编号 pNNN, 文件编号 file_id, 实例句柄, 端口号)
  - 部件端口 record_id 形如 SW:<file>:<sheet>:/<实例>:/<实例>/<子实例>:<标记句柄>:<端口号>；
    实例句柄取路径段中所有句柄（按 '/' 拆分），端口号取末段。
  - PCL 记录键: owner（元件 INSERT 句柄）与 pin（逻辑端号）。
用法: python part_overlap.py --round12 <dir> --pcl <dir> --index <page_index.json> --out <json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re

import pyarrow.parquet as pq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round12", required=True)
    ap.add_argument("--pcl", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    keys = set()
    for path in glob.glob(os.path.join(args.round12, "p*", "*", "findings", "sw_part_instances.parquet")):
        m = re.search(r"[\\/](p\d{3})[\\/]", path)
        pid = m.group(1) if m else "?"
        for r in pq.read_table(path, columns=["file_id", "ports"]).to_pylist():
            pl = r.get("ports") or []
            if isinstance(pl, str):
                try:
                    pl = json.loads(pl)
                except Exception:
                    pl = []
            for p in pl:
                segs = (p.get("record_id") or "").split(":")
                if len(segs) < 4:
                    continue
                pin = segs[-1]
                insts = {x for s in segs[3:-2] for x in s.split("/") if x}
                for h in insts:
                    keys.add((pid, r["file_id"], h.upper(), pin))
    c = collections.Counter()
    by_pt = collections.defaultdict(collections.Counter)
    for fp in glob.glob(os.path.join(args.pcl, "*.json")):
        d = json.load(open(fp, encoding="utf-8"))
        if d.get("error") or not d.get("records"):
            continue
        for rec in d["records"]:
            k = (d["project_id"], d["file_id"], (rec.get("owner") or "").upper(), (rec.get("pin") or "").strip())
            hit = k in keys
            c["pcl_pin_present_as_part_port" if hit else "pcl_pin_not_in_part_ports"] += 1
            by_pt[d["page_type"]]["hit" if hit else "miss"] += 1
    out = {"part_port_keys": len(keys), "counts": dict(c), "by_page_type": {k: dict(v) for k, v in by_pt.items()}}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
