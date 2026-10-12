"""P1-DEDUPE comparison: round-23 baseline vs a new replay, per project (read-only).

Usage: compare_runs.py BASE_DIR NEW_DIR OUT_JSON [project ...]
Compares, per project: issues (multiset of rule_id|message|sheet_id), pair status by pair_kind,
supersession categories and counts by page type, and the SuperWORKS port coverage views.
"""
import collections
import glob
import json
import os
import sys

import pandas as pd


def project_dir(root, pid):
    hits = glob.glob(os.path.join(root, pid, "*", "findings", "pairs.parquet"))
    if not hits:
        return None
    return os.path.dirname(os.path.dirname(hits[0]))


def issues_multiset(pdir):
    df = pd.read_parquet(os.path.join(pdir, "audit", "issues.parquet"))
    keys = [f"{r.rule_id}|{r.message}|{r.sheet_id}" for r in df.itertuples(index=False)]
    return collections.Counter(keys), df


def page_types(pdir):
    pages = pd.read_parquet(os.path.join(pdir, "findings", "pages.parquet"))
    out = {}
    for r in pages.itertuples(index=False):
        out[r.sheet_id] = f"{r.route_target}|{r.page_subtype}"
    return out


def load_pairs(pdir):
    return pd.read_parquet(os.path.join(pdir, "findings", "pairs.parquet"))


def summarize(pdir):
    pairs = load_pairs(pdir)
    ptype = page_types(pdir)
    status = collections.Counter()
    for r in pairs.itertuples(index=False):
        status[f"{r.pair_kind}|{r.status}"] += 1
    superseded = collections.Counter()
    superseded_pass = collections.Counter()
    for r in pairs.itertuples(index=False):
        ev = json.loads(r.evidence) if isinstance(r.evidence, str) and r.evidence else {}
        if ev.get("supersession_category") == "I":
            key = f"{r.pair_kind}|{ptype.get(r.sheet_id, '?')}"
            superseded[key] += 1
    sup = pd.read_parquet(os.path.join(pdir, "findings", "superworks_supersession.parquet"))
    cats = collections.Counter(sup.category)
    summary = json.load(open(os.path.join(pdir, "findings", "superworks_summary.json"), encoding="utf-8"))
    cov = {"port_coverage": summary.get("port_coverage"),
           "port_coverage_with_continuity": summary.get("port_coverage_with_continuity"),
           "coverage_views": summary.get("coverage_views")}
    iss, _ = issues_multiset(pdir)
    return {"pairs": int(len(pairs)), "pair_status": dict(status), "supersession_categories": dict(cats),
            "category_I_by_kind_page": dict(superseded), "coverage": cov,
            "issues": dict(iss), "issue_count": int(sum(iss.values()))}


def main():
    base_root, new_root, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    pids = sys.argv[4:]
    result = {}
    for pid in pids:
        b, n = project_dir(base_root, pid), project_dir(new_root, pid)
        if not b or not n:
            result[pid] = {"missing": {"base": b is None, "new": n is None}}
            continue
        bs, ns = summarize(b), summarize(n)
        bi, ni = collections.Counter(bs["issues"]), collections.Counter(ns["issues"])
        diff_issues = {"only_base": {k: v for k, v in (bi - ni).items()},
                       "only_new": {k: v for k, v in (ni - bi).items()}}
        result[pid] = {"base": bs, "new": ns, "issue_diff": diff_issues,
                       "issues_identical": not diff_issues["only_base"] and not diff_issues["only_new"]}
        print(pid, "pairs", bs["pairs"], "->", ns["pairs"], "| issues", bs["issue_count"], "->", ns["issue_count"],
              "| identical", result[pid]["issues_identical"], "| I", sum(ns["category_I_by_kind_page"].values()),
              flush=True)
    for pid, item in result.items():
        if "base" not in item:
            continue
        for key in sorted(set(item["base"]["pair_status"]) | set(item["new"]["pair_status"])):
            pass
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
