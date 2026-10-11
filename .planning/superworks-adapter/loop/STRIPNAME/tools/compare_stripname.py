"""Compare round13 (before) and STRIPNAME replay (after) per project.

Pairs are keyed by pair_id (derived from the strip row record id, side, branch and destination);
issues by (rule_id, pair_id, message). Ports are compared through sw_port_coverage.
Usage: python compare_stripname.py --before .tmp/superworks_round13_full --after .tmp/loop_stripname --out <json>
"""
import argparse, glob, json
from pathlib import Path
import pandas as pd


def project_dir(root, pid):
    hits = sorted(Path(root, pid).glob("*/findings/pairs.parquet"))
    assert len(hits) == 1, (root, pid, hits)
    return hits[0].parent.parent


def load(root, pid):
    d = project_dir(root, pid)
    pairs = pd.read_parquet(d / "findings/pairs.parquet")
    issues = json.loads((d / "audit/issues.json").read_text(encoding="utf-8"))
    cov = pd.read_parquet(d / "findings/sw_port_coverage.parquet")
    strip = pd.read_parquet(d / "findings/sw_strip_rows.parquet")
    return pairs, issues, cov, strip


def _v(x):
    """Missing values (None/NaN) compare equal; everything else compares by value."""
    if x is None or (isinstance(x, float) and x != x):
        return None
    return x


def pair_view(df):
    return {r.pair_id: r for r in df.itertuples(index=False)}


def issue_key(i):
    return (i.get("rule_id"), i.get("pair_id"), i.get("message"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--projects", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    report = {}
    for pid in a.projects:
        bp, bi, bc, bs = load(a.before, pid)
        ap_, ai, ac, as_ = load(a.after, pid)
        bpv, apv = pair_view(bp), pair_view(ap_)
        added = sorted(set(apv) - set(bpv))
        removed = sorted(set(bpv) - set(apv))
        changed = []
        for k in sorted(set(bpv) & set(apv)):
            b, x = bpv[k], apv[k]
            fields = {}
            for f in ("status", "left_value", "right_value", "confidence", "pair_kind"):
                if _v(getattr(b, f)) != _v(getattr(x, f)):
                    fields[f] = [str(_v(getattr(b, f))), str(_v(getattr(x, f)))]
            if fields:
                changed.append({"pair_id": k, "fields": fields})
        def counts(df):
            return {str(s): int(n) for s, n in df.status.value_counts().items()}
        bkeys = [issue_key(i) for i in bi]
        akeys = [issue_key(i) for i in ai]
        from collections import Counter
        bc_, ac_ = Counter(bkeys), Counter(akeys)
        cov_b = bc.set_index("port_id"); cov_a = ac.set_index("port_id")
        common = cov_b.index.intersection(cov_a.index)
        port_changes = {"consumed_false_to_true": 0, "consumed_true_to_false": 0}
        ch_ports = []
        for pid_ in common:
            cb, ca = bool(cov_b.at[pid_, "consumed"]), bool(cov_a.at[pid_, "consumed"])
            if cb != ca:
                port_changes["consumed_false_to_true" if ca else "consumed_true_to_false"] += 1
                ch_ports.append({"port_id": pid_, "endpoint_identity": str(cov_a.at[pid_, "endpoint_identity"]),
                                 "before": cb, "after": ca})
        report[pid] = {
            "pairs": {"before": len(bp), "after": len(ap_), "before_status": counts(bp), "after_status": counts(ap_)},
            "pairs_added": len(added), "pairs_removed": len(removed), "pairs_changed": len(changed),
            "added": [{"pair_id": k, "left": str(apv[k].left_value), "right": str(apv[k].right_value),
                       "status": str(apv[k].status), "pair_kind": str(apv[k].pair_kind)} for k in added],
            "removed": [{"pair_id": k, "left": str(bpv[k].left_value), "right": str(bpv[k].right_value),
                         "status": str(bpv[k].status), "pair_kind": str(bpv[k].pair_kind)} for k in removed],
            "changed": changed,
            "issues": {"before": len(bi), "after": len(ai),
                       "new": [list(k) for k in (ac_ - bc_).elements()],
                       "resolved": [list(k) for k in (bc_ - ac_).elements()]},
            "ports": {"total": len(common), "consumed_before": int(cov_b.consumed.sum()),
                      "consumed_after": int(cov_a.consumed.sum()), **port_changes},
            "port_changes": ch_ports,
            "strip_identity_changes": 0,
        }
        bsi = dict(zip(bs.record_id, bs.endpoint_identity))
        asi = dict(zip(as_.record_id, as_.endpoint_identity))
        report[pid]["strip_identity_changes"] = sum(1 for k in bsi if bsi.get(k) != asi.get(k))
        report[pid]["strip_identity_examples"] = [{"record_id": k, "before": bsi[k], "after": asi.get(k)}
                                                  for k in bsi if bsi.get(k) != asi.get(k)][:5]
        print(pid, {k: report[pid][k] for k in ("pairs_added", "pairs_removed", "pairs_changed", "ports")}, "issues", report[pid]["issues"]["before"], "->", report[pid]["issues"]["after"], flush=True)
    Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
