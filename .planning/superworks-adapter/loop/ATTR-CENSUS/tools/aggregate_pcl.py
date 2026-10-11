"""汇总 parse_pcl.py 的逐文件输出：引脚-导线记录的覆盖率、字段填充率、句柄解析情况。

用法: python aggregate_pcl.py --work <pcl dir> --out <pcl_summary.json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    files = glob.glob(args.work + "/*.json")
    per_pt_files = collections.Counter()
    pt_files_all = collections.Counter()
    per_pt_recs = collections.Counter()
    owner = collections.Counter()
    fill = collections.Counter()
    label_cls = collections.Counter()
    xref_here = collections.Counter()
    res = collections.Counter()
    far_comp = collections.Counter()
    far_kind = collections.Counter()
    wire_type = collections.Counter()
    pin_vals = collections.Counter()
    ex = []
    fam_files = collections.Counter()
    fam_recs = collections.Counter()
    files_with_any = set()
    fam_pages_all = collections.Counter()
    errors = []
    n_recs = 0
    linked_line = 0
    pagenames = collections.Counter()
    xref_pagenames = collections.Counter()
    for fp in files:
        d = json.load(open(fp, encoding="utf-8"))
        pt = d.get("page_type")
        fam = d.get("family")
        pt_files_all[pt] += 1
        if d.get("error"):
            errors.append((d.get("project_id"), d.get("file_id"), d["error"][:120]))
            continue
        recs = d.get("records", [])
        if recs:
            files_with_any.add((d["project_id"], d["file_id"]))
            per_pt_files[pt] += 1
            fam_files[fam] += 1
        per_pt_recs[pt] += len(recs)
        fam_recs[fam] += len(recs)
        n_recs += len(recs)
        for r in recs:
            owner[(r["owner_kind"], r["owner_type"])] += 1
            pin_vals[r.get("pin") or ""] += 0  # placeholder for distribution below
            for f in ("pin", "线号", "导线类型", "线号文字句柄", "导线颜色代号文字句柄", "接线文字句柄",
                      "直线句柄", "接地图块句柄", "接地文字句柄", "far_component", "far_pin"):
                if (r.get(f) or "").strip():
                    fill[f] += 1
            label_cls[r.get("wire_label_class")] += 1
            if r.get("xref_handle"):
                xref_here[(pt, r.get("xref_handle_resolves_here") or "NONE")] += 1
                xref_pagenames[r.get("xref_pagename", "")] += 1
            for f in ("直线句柄_resolves", "接线文字句柄_resolves", "线号文字句柄_resolves", "导线颜色代号文字句柄_resolves",
                      "接地图块句柄_resolves", "接地文字句柄_resolves"):
                v = r.get(f)
                if v:
                    res[f"{f}={v}"] += 1
            if r.get("far_component"):
                far_comp[r["far_component"]] += 1
                far_kind[r.get("far_kind", "")] += 1
            if r.get("导线类型"):
                wire_type[r["导线类型"]] += 1
            if r.get("直线句柄_resolves") == "LINE":
                linked_line += 1
            if len(ex) < 60 and r.get("owner_kind") == "ext":
                ex.append({"pid": d["project_id"], "fid": d["file_id"], "pt": pt, "filename": d.get("filename"),
                           "owner": r["owner"], "owner_type": r["owner_type"], "xrec": r["xrec"],
                           "pin": r.get("pin"), "线号": r.get("线号"), "导线类型": r.get("导线类型"),
                           "直线句柄": r.get("直线句柄"), "直线句柄_resolves": r.get("直线句柄_resolves"),
                           "接线文字句柄": r.get("接线文字句柄"), "接线文字句柄_resolves": r.get("接线文字句柄_resolves"),
                           "far_component": r.get("far_component"), "far_pin": r.get("far_pin"),
                           "far_kind": r.get("far_kind")})
    # 页型覆盖率
    pt_cov = {pt: {"pages": pt_files_all[pt], "pages_with_pcl": per_pt_files[pt], "records": per_pt_recs[pt]}
              for pt in pt_files_all}
    out = {
        "files_total": len(files),
        "files_with_pcl": len(files_with_any),
        "records_total": n_recs,
        "linked_line_records": linked_line,
        "per_page_type": pt_cov,
        "per_family_files_with_pcl": dict(fam_files),
        "per_family_records": dict(fam_recs),
        "owner_kind_type": {f"{k[0]}|{k[1]}": v for k, v in owner.items()},
        "field_fill_nonempty": dict(fill),
        "wire_label_class": dict(label_cls),
        "crosspage_handle_resolves_in_same_file": {f"{k[0]}|{k[1]}": v for k, v in xref_here.items()},
        "crosspage_pagenames_top": xref_pagenames.most_common(30),
        "handle_resolution": dict(res),
        "far_component_top": far_comp.most_common(40),
        "far_kind_top": far_kind.most_common(10),
        "wire_type_top": wire_type.most_common(20),
        "errors": errors[:20],
        "examples_ext": ex,
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("files_total", "files_with_pcl", "records_total", "linked_line_records")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
