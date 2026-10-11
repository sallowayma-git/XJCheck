"""Run the production cross-page module over a run directory and sample the results for review.

Usage (PYTHONIOENCODING=utf-8):
  python xpage_study.py <run_dir> <out_dir> [--projects p001 ...] [--render-seed 1 --per-class 3]

Writes <out_dir>/study.json (stats per project and in total, record counts), <out_dir>/links.json and
<out_dir>/candidates.json (all records), and with --render-*: <out_dir>/png/<class>_<k>.png and index.json.
Read-only with respect to the run directory; the module itself never writes pairs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from dwg_audit.audit.superworks_cross_page import build_cross_page_links  # noqa: E402
import xpage_io  # noqa: E402

R4_PATH = ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"
MANIFEST = ROOT / ".planning/superworks-adapter/corpus_manifest.json"


def _dxf_map():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {(p["project_id"], f["file_id"]): f["dxf_path"] for p in manifest["projects"] for f in p["files"]}


def run(run_dir: Path, projects: list[str]):
    totals, per_project, links, candidates = Counter(), {}, [], []
    for pid in projects:
        findings = xpage_io.findings_dir(run_dir, pid)
        data = xpage_io.load(findings)
        result = build_cross_page_links(data["strips"], data["ports"], data["pairs"], data["pages"])
        per_project[pid] = result["stats"]
        for key, value in result["stats"].items():
            if key != "covered_targets":
                totals[key] += value
        totals["covered_targets"] += len(result["covered"])
        for record in result["links"]:
            links.append({**record, "project_id": pid})
        for record in result["candidates"]:
            candidates.append({**record, "project_id": pid})
    return {"totals": dict(totals), "per_project": per_project, "links": links, "candidates": candidates}


def classify(record: dict) -> str:
    """Review class of one record (the sample key)."""
    if "candidate" in record and record.get("candidate"):
        return record["candidate"]
    explained = {(record.get("strip_identity") or "").casefold()} | set(record.get("far_values") or [])
    if record.get("covers_target"):
        return "covers_" + ("row" if record["relation"] == "continuity_row" else "conn")
    if record.get("consumer_pair_ids"):
        agrees = bool(set(record.get("consumer_other_values") or []) & explained)
        return "consumed_agrees" if agrees else "consumed_other_differs"
    return "no_wire_contact"


def render_samples(run_dir: Path, out_dir: Path, study: dict, seed: int, per_class: int):
    import shot_render  # local helper module (renderer), imported late: needs matplotlib/ezdxf
    rng = random.Random(seed)
    dxf = _dxf_map()
    buckets = defaultdict(list)
    for record in study["links"] + study["candidates"]:
        buckets[classify(record)].append(record)
    index = []
    cache = {}
    for klass in sorted(buckets):
        pool = sorted(buckets[klass], key=lambda r: (r["project_id"], r.get("link_id") or r.get("strip_record_id")))
        picks = rng.sample(pool, min(per_class, len(pool)))
        for k, record in enumerate(picks, start=1):
            pid = record["project_id"]
            if pid not in cache:
                findings = xpage_io.findings_dir(run_dir, pid)
                cache[pid] = (xpage_io.load(findings), findings)
            data, _ = cache[pid]
            index_row = shot_render.draw_record(out_dir / "png" / f"{klass}_{k}.png", pid, record, data, dxf, klass)
            index.append(index_row)
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("out_dir")
    parser.add_argument("--projects", nargs="*", default=None)
    parser.add_argument("--render-seed", type=int, default=None)
    parser.add_argument("--per-class", type=int, default=3)
    args = parser.parse_args()
    run_dir, out_dir = Path(args.run_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    projects = args.projects or sorted(p.name for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("p"))
    study = run(run_dir, projects)
    (out_dir / "links.json").write_text(json.dumps(study["links"], ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out_dir / "candidates.json").write_text(json.dumps(study["candidates"], ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    summary = {"projects": projects, "totals": study["totals"], "per_project": study["per_project"],
               "class_counts": dict(Counter(classify(r) for r in study["links"] + study["candidates"]))}
    (out_dir / "study.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["totals"], ensure_ascii=False, indent=1))
    print(json.dumps(summary["class_counts"], ensure_ascii=False, indent=1))
    if args.render_seed is not None:
        index = render_samples(run_dir, out_dir, study, args.render_seed, args.per_class)
        print("rendered", len(index))


if __name__ == "__main__":
    main()
