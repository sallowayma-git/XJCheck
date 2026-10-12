"""LEGACY-CENSUS step 2b: duplicate flags, source tables, issue dependencies and V2 usage (read-only).

Adds to pairs_tagged.parquet:
  sw_dup   'same_sheet' | 'project_only' | 'none' for c/d pairs: an SW-produced (tag a/b*) pair with the same
           unordered endpoint values exists on the same sheet / elsewhere in the project.
Writes .tmp/legacy_census_work/pairs_tagged_v2.parquet and .tmp/legacy_census_work/analysis.json.
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter

import pandas as pd

ROOT = "F:/workspace/XJToolkit"
WORK = os.path.join(ROOT, ".tmp/legacy_census_work")
RUN = os.path.join(ROOT, ".tmp/superworks_round23_full")


def vkey(l, r):
    if l and r:
        return "|".join(sorted([str(l), str(r)]))
    return None


def main():
    df = pd.read_parquet(os.path.join(WORK, "pairs_tagged.parquet"))
    df["page_kind"] = df.route_target.fillna("?") + "|" + df.page_subtype.fillna("-")
    df["vkey"] = [vkey(a, b) for a, b in zip(df.left_value, df.right_value)]
    sw = df[df.tag.isin(["a", "b1", "b2"]) & df.vkey.notna()]
    same_sheet = set(zip(sw.project_id, sw.sheet_id, sw.vkey))
    same_proj = set(zip(sw.project_id, sw.vkey))
    sw_pass_sheet = set(zip(sw[sw.status == "pass"].project_id, sw[sw.status == "pass"].sheet_id, sw[sw.status == "pass"].vkey))

    def dup(r):
        if r.tag not in ("c", "d") or r.vkey is None:
            return ""
        if (r.project_id, r.sheet_id, r.vkey) in same_sheet:
            return "same_sheet_sw_pass" if (r.project_id, r.sheet_id, r.vkey) in sw_pass_sheet else "same_sheet_sw_nonpass"
        if (r.project_id, r.vkey) in same_proj:
            return "project_only"
        return "none"

    df["sw_dup"] = df.apply(dup, axis=1)
    df.to_parquet(os.path.join(WORK, "pairs_tagged_v2.parquet"), index=False)

    out = {}
    tag_status = df.groupby(["tag", "status"]).size().unstack(fill_value=0)
    out["tag_by_status"] = {t: {s: int(v) for s, v in row.items()} for t, row in tag_status.iterrows()}
    b2 = df[df.tag == "b2"].groupby(["b2_sub", "status"]).size().unstack(fill_value=0)
    out["b2_sub_by_status"] = {t: {s: int(v) for s, v in row.items()} for t, row in b2.iterrows()}
    cd = df[df.tag.isin(["c", "d"])]
    out["cd_sw_dup_by_tag_status"] = {f"{k[0]}|{k[1]}|{k[2]}": int(v) for k, v in
                                      cd.groupby(["tag", "status", "sw_dup"]).size().items()}
    out["by_family"] = {f: {f"{t}|{s}": int(v) for (t, s), v in
                            df[df.family == f].groupby(["tag", "status"]).size().items()}
                        for f in sorted(df.family.unique())}
    out["by_pair_kind"] = {k: {f"{t}|{s}": int(v) for (t, s), v in g.groupby(["tag", "status"]).size().items()}
                           for k, g in df.groupby("pair_kind")}
    out["by_page_kind"] = {k: {f"{t}|{s}": int(v) for (t, s), v in g.groupby(["tag", "status"]).size().items()}
                           for k, g in df.groupby("page_kind")}

    # Issues: primary pair tag / dup, related pair tags, and offline counterfactual for dropping c/d pairs.
    issues = pd.read_parquet(os.path.join(WORK, "issues_all.parquet"))
    key = df.set_index(["project_id", "pair_id"])
    rows = []
    for r in issues.itertuples(index=False):
        prim = key.loc[(r.project_id, r.pair_id)] if (r.project_id, r.pair_id) in key.index else None
        rel = [key.loc[(r.project_id, x)] for x in r.related_pair_ids if (r.project_id, x) in key.index]
        ptag = prim.tag if prim is not None else "NA"
        rtags = [x.tag for x in rel]
        all_cd = (ptag in ("c", "d")) and all(t in ("c", "d") for t in rtags)
        # Primary-only c/d: the issue is anchored on pure legacy output, so dropping c/d removes it.
        rows.append({"project_id": r.project_id, "issue_id": r.issue_id, "rule_id": r.rule_id,
                     "primary_pair": r.pair_id, "primary_tag": ptag,
                     "primary_status": prim.status if prim is not None else None,
                     "primary_pair_kind": prim.pair_kind if prim is not None else None,
                     "primary_sw_dup": prim.sw_dup if prim is not None else None,
                     "related_tags": ",".join(rtags), "removed_if_drop_cd": bool(all_cd),
                     "message": r.message[:140]})
    iss = pd.DataFrame(rows)
    iss.to_parquet(os.path.join(WORK, "issues_dependency.parquet"), index=False)
    out["issues_primary_tag"] = iss.primary_tag.value_counts().to_dict()
    out["issues_removed_if_drop_cd"] = int(iss.removed_if_drop_cd.sum())
    out["issues_total"] = int(len(iss))

    # Potential new issues if V1 pass is downgraded: pure-legacy pass pairs that would become eligible for
    # R-PAIR-LOW-CONFIDENCE (ordinary_pair or component_mapping with both values), an upper bound.
    pure_pass = df[(df.tag.isin(["c", "d"])) & (df.status == "pass") & df.vkey.notna()]
    out["upper_bound_low_conf_candidates_pure_pass"] = int(pure_pass.pair_kind.isin(["ordinary_pair", "component_mapping"]).sum())

    # V2 usage: physical-endpoint evidence on pairs, joined to extraction-stage proposals.
    usage = pd.read_parquet(os.path.join(WORK, "v2_port_usage.parquet"))
    out["v2_usage_sides_by_status"] = {k: int(v) for k, v in usage.groupby("status").size().items()}
    out["v2_usage_pairs_by_status"] = {k: int(v) for k, v in usage.groupby("status").pair_id.nunique().items()}
    out["v2_usage_is_sw_definition"] = {str(k): int(v) for k, v in usage.groupby("is_sw", dropna=False).size().items()}
    out["v2_usage_family_rule"] = {k: int(v) for k, v in usage.family_rule.value_counts().items()}
    pv = pd.read_parquet(os.path.join(WORK, "v2_proposals.parquet"))
    nsw = pv[~pv.is_sw_definition]
    out["v2_proposals"] = {
        "file_definition_rows": int(len(pv)),
        "sw_definition_rows": int(pv.is_sw_definition.sum()),
        "non_sw_definition_rows": int(len(nsw)),
        "non_sw_rows_with_ports": int((nsw.n_ports > 0).sum()),
        "non_sw_raw_ports": int(nsw.n_ports.sum()),
        "non_sw_family_counts_with_ports": {k: int(v) for k, v in
                                            nsw[nsw.n_ports > 0].family_id.fillna("(none)").value_counts().items()},
        "non_sw_labelled_terminal_rows": int((nsw.family_id == "labelled_terminal.generic.v1").sum()),
        "sw_labelled_terminal_rows": int(((pv.is_sw_definition) & (pv.family_id == "labelled_terminal.generic.v1")).sum()),
        "sw_labelled_terminal_raw_ports": int(pv[(pv.is_sw_definition) & (pv.family_id == "labelled_terminal.generic.v1")].n_ports.sum()),
    }
    # Panel IGNORE pass (the only production consumer of non-SW proposals): pairs marked by it.
    ign = Counter()
    for pdir in sorted(glob.glob(os.path.join(RUN, "p[0-9][0-9][0-9]"))):
        pid = os.path.basename(pdir)
        fd = glob.glob(os.path.join(pdir, "*", "findings"))[0]
        p = pd.read_parquet(os.path.join(fd, "pairs.parquet"), columns=["pair_id", "status", "evidence"])
        for r in p.itertuples(index=False):
            if "ignored_panel_family_id" in (json.loads(r.evidence) or {}):
                ign[r.status] += 1
    out["panel_ignore_pairs_by_status"] = dict(ign)
    json.dump(out, open(os.path.join(WORK, "analysis.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ["tag_by_status", "b2_sub_by_status", "cd_sw_dup_by_tag_status",
                                          "issues_primary_tag", "issues_removed_if_drop_cd",
                                          "upper_bound_low_conf_candidates_pure_pass",
                                          "v2_usage_pairs_by_status", "v2_proposals",
                                          "panel_ignore_pairs_by_status"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
