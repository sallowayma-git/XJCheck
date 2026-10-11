"""把冻结语料清单与 round12 pages.parquet 按 (file_id, filename) 关联，生成页面索引。

只读：读取 corpus_manifest.json 与 .tmp/superworks_round12_full/p*/*/findings/pages.parquet。
用法: python build_index.py --out <page_index.json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os

import pyarrow.parquet as pq

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
MANIFEST = os.path.join(REPO, ".planning", "superworks-adapter", "corpus_manifest.json")
ROUND12 = os.path.join(REPO, ".tmp", "superworks_round12_full")


def family_of(input_root: str) -> str:
    """把 input_root 归入任务书列出的项目家族（用于覆盖率统计）。"""
    s = input_root
    if "N2604" in s:
        return "N2604合同"
    if "PAC-885" in s:
        return "PAC-885G-H"
    if "变压器测控" in s or "35kV变压器保护测控柜" in s:
        return "变压器测控柜"
    if "110kV变压器保护柜" in s or "WBH-812E" in s:
        return "110kV变压器保护柜"
    return "正式典设(test)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    rows = []
    missing = []
    for p in manifest["projects"]:
        pid = p["project_id"]
        pages = {}
        for path in glob.glob(os.path.join(ROUND12, pid, "*", "findings", "pages.parquet")):
            for r in pq.read_table(path).to_pylist():
                pages[(r["file_id"], r["filename"])] = r
        for f in p["files"]:
            r = pages.get((f["file_id"], f["filename"]))
            if r is None:
                missing.append((pid, f["file_id"], f["filename"]))
            r = r or {}
            rows.append({
                "project_id": pid,
                "family": family_of(p["input_root"]),
                "input_root": p["input_root"],
                "file_id": f["file_id"],
                "filename": f["filename"],
                "dxf_path": f["dxf_path"],
                "dxf_sha256": f["dxf_sha256"],
                "page_type": r.get("page_type"),
                "page_subtype": r.get("page_subtype"),
                "sheet_category": r.get("sheet_category"),
                "audit_role": r.get("audit_role"),
                "route_target": r.get("route_target"),
                "sheet_id": r.get("sheet_id"),
                "sheet_title": r.get("sheet_title"),
            })
    print("rows", len(rows), "missing", len(missing))
    print(collections.Counter(r["page_type"] for r in rows).most_common())
    print(collections.Counter(r["family"] for r in rows).most_common())
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
