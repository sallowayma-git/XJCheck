"""汇总 value_probe.py 的逐文件输出：按 appid 给出页型覆盖、取值分布、句柄目标类型与文字。

用法: python aggregate_vp.py --work <vp dir> --out <vp_summary.json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    files = glob.glob(args.work + "/*.json")
    apps = collections.defaultdict(lambda: {
        "files": 0, "pages_by_type": collections.Counter(), "pages_by_family": collections.Counter(),
        "ents": collections.Counter(), "str": collections.Counter(), "h_type": collections.Counter(),
        "h_text": collections.Counter(), "num_codes": collections.Counter(), "num_min": None, "num_max": None,
        "examples": []})
    n_err = 0
    for fp in files:
        d = json.load(open(fp, encoding="utf-8"))
        if d.get("error"):
            n_err += 1
            continue
        pt, fam = d["page_type"], d["family"]
        for app, a in d["apps"].items():
            s = apps[app]
            s["files"] += 1
            s["pages_by_type"][pt] += 1
            s["pages_by_family"][fam] += 1
            for k, v in a["ents"].items():
                s["ents"][f"{pt}|{k}"] += v
            for k, v in a["str"].items():
                s["str"][k] += v
            for k, v in a["h_type"].items():
                s["h_type"][k] += v
            for k, v in a["h_text"].items():
                s["h_text"][k] += v
            for k, v in a["num_codes"].items():
                s["num_codes"][k] += v
            if a["num_min"] is not None:
                s["num_min"] = a["num_min"] if s["num_min"] is None else min(s["num_min"], a["num_min"])
                s["num_max"] = a["num_max"] if s["num_max"] is None else max(s["num_max"], a["num_max"])
            if len(s["examples"]) < 3 and a["ex"]:
                ex = dict(a["ex"][0])
                ex.update({"pid": d["project_id"], "fid": d["file_id"], "pt": pt, "filename": d["filename"]})
                s["examples"].append(ex)
    out = {"files": len(files), "errors": n_err, "apps": {}}
    for app, s in sorted(apps.items()):
        out["apps"][app] = {
            "files": s["files"],
            "pages_by_type": dict(s["pages_by_type"]),
            "pages_by_family": dict(s["pages_by_family"]),
            "entities_by_pt_scope_type": dict(s["ents"].most_common(12)),
            "str_top": s["str"].most_common(25),
            "h_type": dict(s["h_type"]),
            "h_text_top": s["h_text"].most_common(20),
            "num_codes": dict(s["num_codes"]),
            "num_range": [s["num_min"], s["num_max"]],
            "examples": s["examples"],
        }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("files", len(files), "errors", n_err, "apps", len(out["apps"]))


if __name__ == "__main__":
    main()
