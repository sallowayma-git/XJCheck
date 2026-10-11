"""Stratified sample of the remaining candidates for visual review (XPAGE-2).

Usage: python xp2_sample.py <eval_json> <iteration_tag> <out_dir> [--seed 17] [--n-family 18 --n-other 14]
Buckets (after the equivalence rules named by the tag):
  F  target is the shared 1n112 family (the 1C-112 block)           ->  n-family
  S  other target ports claimed by two or more rows                   ->  n-other
  U  target claimed by one row only                                   ->  all of them (max 10)
Renders two-panel PNGs with shot_render.draw_record and writes index.json.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / ".planning/superworks-adapter/loop/XPAGE/tools"))
import shot_render  # noqa: E402
import xpage_io  # noqa: E402
import xp2_load  # noqa: E402


def in_iteration(r):
    f = r["flags"]
    if f["target_in_group"] or f["other_in_group_identity"] or f["other_in_group_far"]:
        return False
    if f["target_in_hop"] or f["other_in_hop"]:
        return False
    return True


def bucket(r):
    if r["target_identity"] == "1n112":
        return "F"
    if r["flags"]["target_shared_by_rows"]:
        return "S"
    return "U"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("eval_json")
    p.add_argument("tag")
    p.add_argument("out_dir")
    p.add_argument("--run-dir", default=".tmp/superworks_round17_full")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--n-family", type=int, default=18)
    p.add_argument("--n-other", type=int, default=14)
    a = p.parse_args()
    recs = json.loads(Path(a.eval_json).read_text(encoding="utf-8"))["records"]
    pool = [r for r in recs if r["candidate"] == "contradiction_candidate" and in_iteration(r)]
    rng = random.Random(a.seed)
    buckets = {"F": [], "S": [], "U": []}
    for r in pool:
        buckets[bucket(r)].append(r)
    picks = []
    for key, n in (("F", a.n_family), ("S", a.n_other), ("U", 10)):
        items = sorted(buckets[key], key=lambda r: (r["project_id"], r["link_id"]))
        picks += [(key, r) for r in rng.sample(items, min(n, len(items)))]
    out = Path(a.out_dir)
    (out / "png").mkdir(parents=True, exist_ok=True)
    dxf_manifest = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
    dxf = {(q["project_id"], f["file_id"]): f["dxf_path"] for q in dxf_manifest["projects"] for f in q["files"]}
    cache = {}
    index = []
    for k, (key, r) in enumerate(picks, start=1):
        pid = r["project_id"]
        if pid not in cache:
            cache[pid] = xpage_io.load(xpage_io.findings_dir(Path(a.run_dir), pid))
        klass = f"{a.tag} {key}{k:02d} 组{r['group_size']}"
        png = out / "png" / f"{a.tag}_{key}{k:02d}_{pid}_{r['strip_identity']}.png".replace("~", "")
        row = shot_render.draw_record(png, pid, r, cache[pid], dxf, klass)
        index.append({**row, "bucket": key, "sample_no": k, "group_members": r.get("group_members"),
                      "consumer_other_values": r.get("consumer_other_values"), "flags": r.get("flags")})
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print("pool", len(pool), {k: len(v) for k, v in buckets.items()}, "picked", len(picks))


if __name__ == "__main__":
    main()
