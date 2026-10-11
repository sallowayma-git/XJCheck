"""Stratified sample of the candidates that the production module leaves (XPAGE-2 iterations).

Usage: python xp2_sample_prod.py <offline_json> <tag> <out_dir> [--seed 17] [--n-wire 16 --n-device 14 --n-range 10]
Strata for identity_mismatch_unconsumed (free target):
  W  target identity is a wire label (n-number, no device prefix)
  D  target identity is a device terminal
  R  target identity is a range (contains '~')
contradiction_candidate (consumed target): all of them.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / ".planning/superworks-adapter/loop/XPAGE/tools"))
import shot_render  # noqa: E402
import xpage_io  # noqa: E402


def stratum(c):
    t = c["target_identity"]
    if c["candidate"] == "contradiction_candidate":
        return "C"
    if "~" in t:
        return "R"
    if re.fullmatch(r"\d*n\d+", t.casefold()):
        return "W"
    return "D"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("offline_json")
    p.add_argument("tag")
    p.add_argument("out_dir")
    p.add_argument("--run-dir", default=".tmp/superworks_round17_full")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--n-wire", type=int, default=16)
    p.add_argument("--n-device", type=int, default=14)
    p.add_argument("--n-range", type=int, default=10)
    p.add_argument("--exclude", default=None, help="index.json of an earlier sample; its records are skipped")
    a = p.parse_args()
    excluded = set()
    if a.exclude:
        for row in json.loads(Path(a.exclude).read_text(encoding="utf-8")):
            excluded.add((row["project_id"], row["strip_record_id"], row["target_port_id"]))
    data = json.loads(Path(a.offline_json).read_text(encoding="utf-8"))
    pool = []
    for proj in data["projects"]:
        for c in proj["candidates"]:
            if (proj["project_id"], c["strip_record_id"], c["target_port_id"]) in excluded:
                continue
            pool.append({**c, "project_id": proj["project_id"]})
    buckets = {}
    for c in pool:
        buckets.setdefault(stratum(c), []).append(c)
    rng = random.Random(a.seed)
    picks = []
    quota = {"C": None, "W": a.n_wire, "D": a.n_device, "R": a.n_range}
    for key in ("C", "W", "D", "R"):
        items = sorted(buckets.get(key, []), key=lambda r: (r["project_id"], r["link_id"]))
        n = len(items) if quota[key] is None else min(quota[key], len(items))
        picks += [(key, r) for r in rng.sample(items, n)]
    out = Path(a.out_dir)
    (out / "png").mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
    dxf = {(q["project_id"], f["file_id"]): f["dxf_path"] for q in manifest["projects"] for f in q["files"]}
    cache, index = {}, []
    for k, (key, r) in enumerate(picks, start=1):
        pid = r["project_id"]
        if pid not in cache:
            cache[pid] = xpage_io.load(xpage_io.findings_dir(Path(a.run_dir), pid))
        klass = f"{a.tag} {key}{k:02d}"
        name = f"{a.tag}_{key}{k:02d}_{pid}_{r['strip_identity']}_{r['target_identity']}"
        name = re.sub(r"[^0-9A-Za-z_\-]+", "_", name)
        png = out / "png" / f"{name}.png"
        row = shot_render.draw_record(png, pid, r, cache[pid], dxf, klass)
        index.append({**row, "bucket": key, "sample_no": k, "project_id": pid, "ref_page_no": r["ref_page_no"],
                      "consumer_other_values": r.get("consumer_other_values")})
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print("pool", len(pool), {k: len(v) for k, v in buckets.items()}, "picked", len(picks))


if __name__ == "__main__":
    main()
