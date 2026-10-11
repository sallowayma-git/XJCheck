"""Run the cross-page conflict runner on replayed p061 pairs, with trace of the 3-21GD17 group.

Usage: PYTHONPATH=<snapshot src> python harness.py <pairs.parquet> <project_root_for_issues.json>
"""
import json, math, sys
from dataclasses import fields
from pathlib import Path
import pandas as pd
from dwg_audit.domain.models import Pair
from dwg_audit.audit import rules as R
from dwg_audit.audit.rule_base import RuleContext, IssueFactory
from dwg_audit.utils.ids import IdFactory

PAIR_FIELDS = {f.name for f in fields(Pair)}


def _clean(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def load_pairs(path):
    df = pd.read_parquet(path)
    out = []
    for r in df.to_dict("records"):
        kw = {}
        for k, v in r.items():
            if k not in PAIR_FIELDS:
                continue
            v = _clean(v)
            if k == "evidence" and isinstance(v, str):
                v = json.loads(v)
            if k == "alternative_pair_candidate_ids" and v is not None and not isinstance(v, list):
                v = list(v)
            kw[k] = v
        out.append(Pair(**kw))
    return out


def run(path, trace_value="3-21GD17"):
    pairs = load_pairs(path)
    ctx = RuleContext(pairs=pairs, line_groups=[], sheets=[], config={}, terminal_candidates=[],
                      high_threshold=0.92, duplicate_delta=0.08, reciprocal_required=False,
                      group_map={}, sheet_map={},
                      issue_factory=IssueFactory(issue_ids=IdFactory("I"), group_map={}, sheet_map={}))
    issues = R._run_cross_page_conflict(ctx)
    return pairs, issues


if __name__ == "__main__":
    pairs, issues = run(sys.argv[1])
    print("pairs", len(pairs), "cross-page issues", len(issues))
    for i in issues:
        print(" ISSUE", i.rule_id, i.severity, i.message)
