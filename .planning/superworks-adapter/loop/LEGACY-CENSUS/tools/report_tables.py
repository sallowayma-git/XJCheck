"""LEGACY-CENSUS step 5: final tables -> details.json (read-only inputs, writes only into LEGACY-CENSUS/).

Source tags: a | b1 | b2(e/p/v/c) | c | d ; c/d additionally carry sw_dup (same-sheet / project-only / none).
Issue counterfactual: an issue is affected when its primary pair or any related pair is c/d (dropping c/d
removes that member); removed when every member is c/d, otherwise 'shrinks' (partner count changes).
"""
from __future__ import annotations

import json
import os

import pandas as pd

ROOT = "F:/workspace/XJToolkit"
WORK = os.path.join(ROOT, ".tmp/legacy_census_work")
LOOP = os.path.join(ROOT, ".planning/superworks-adapter/loop/LEGACY-CENSUS")

# Visual verdicts written after reading the PNG sheets (see README section 3).
VERDICT = {
    "raw1": ("continuation, single-sided (terminal row to another page)", "one-sided by design; review only; no pass loss"),
    "raw2": ("explicit external lead: component pin to external label", "visually real straight wire in 3/3; SW pass pair with identical values on the same sheet in 3/3"),
    "raw3": ("backplate virtual table, identity elsewhere on both ends", "row alignment consistent; 91% already confirmed by an identical SW pass pair on the sheet"),
    "raw4": ("semantic terminal mapping, single-sided annotation", "one-sided; review only; no pass loss"),
    "raw5": ("backplate virtual table, one end with identity elsewhere", "row alignment consistent; 96% no SW counterpart (SW blind)"),
    "raw6": ("scoped visible prefix, component pin to external label", "mixed: 79% duplicate an SW pass pair; the rest include device-crossing runs"),
    "raw7": ("input matrix wire mapping, device pin to label", "straight wire visually real; 100% duplicate an SW pass pair"),
    "raw8": ("backplate virtual table, identity elsewhere on one end", "row alignment consistent; 95% duplicate an SW pass pair"),
    "raw9": ("backplate virtual table, neither end has identity", "row alignment consistent; 91% no SW counterpart (SW blind)"),
    "raw10": ("explicit external lead, short leads", "visually real short wire in 3/3; 100% duplicate an SW pass pair"),
    "d3_1": ("backplate virtual table, row label to label (identity on one side elsewhere)", "row alignment consistent; no SW counterpart; the largest pure-V1 pass bucket"),
    "d3_2": ("backplate virtual table, neither end has identity", "row alignment consistent; no SW counterpart"),
    "d3_3": ("scoped prefix, terminal to label", "3/3 sampled cross a device symbol on the path; likely over-merged, needs manual check"),
    "d3_4": ("scoped prefix, one side is a non-SW device pin", "straight device-pin-to-label wire, visually real; SW blind on non-SW block"),
    "d3_5": ("inline body port, one side is a non-SW device pin", "2/3 straight device-pin-to-label wires; 1/3 crosses a device circle on the path; SW blind on the device"),
    "d3_6": ("first-prefixed mapping, row wire spanning several devices", "3/3 span several device symbols; likely over-merged"),
    "d3_7": ("scoped prefix, one side with no wire contact in SW", "mixed: straight runs and device-crossing runs"),
}


def main():
    df = pd.read_parquet(os.path.join(WORK, "pairs_tagged_v2.parquet"))
    st = df.groupby(["tag", "status"]).size().unstack(fill_value=0)
    out = {"scope": {"projects": int(df.project_id.nunique()), "pairs_final": int(len(df)),
                     "pass": int((df.status == "pass").sum()), "review": int((df.status == "review").sum()),
                     "discard": int((df.status == "discard").sum())}}
    out["source_by_status"] = {t: {s: int(v) for s, v in row.items()} for t, row in st.iterrows()}
    b2 = df[df.tag == "b2"].groupby(["b2_sub", "status"]).size().unstack(fill_value=0)
    out["b2_sub_by_status"] = {t: {s: int(v) for s, v in row.items()} for t, row in b2.iterrows()}
    cd = df[df.tag.isin(["c", "d"]) & df.status.isin(["pass", "review"])]
    out["cd_pass_review_sw_dup"] = {f"{t}|{s}|{d}": int(v) for (t, s, d), v in
                                    cd.groupby(["tag", "status", "sw_dup"]).size().items()}
    # Pass-status accounting (pure V1 vs duplicated SW connection).
    pass_all = int((df.status == "pass").sum())
    legacy_pass = df[df.tag.isin(["c", "d"]) & (df.status == "pass")]
    out["pass_accounting"] = {
        "pass_total": pass_all,
        "legacy_only_pass_no_sw_counterpart": int((legacy_pass.sw_dup == "none").sum()),
        "legacy_pass_duplicate_of_sw_same_sheet_pass": int((legacy_pass.sw_dup == "same_sheet_sw_pass").sum()),
        "legacy_pass_same_values_sw_same_sheet_nonpass": int((legacy_pass.sw_dup == "same_sheet_sw_nonpass").sum()),
        "legacy_pass_same_values_sw_other_sheet": int((legacy_pass.sw_dup == "project_only").sum()),
    }

    def table(group_cols, name, top=None):
        g = df.groupby(group_cols + ["tag", "status"]).size().unstack(["tag", "status"], fill_value=0)
        g.columns = [f"{t}|{s}" for t, s in g.columns]
        g = g.reset_index()
        if top:
            g = g.sort_values(group_cols[0]).head(top)
        out[name] = g.to_dict(orient="records")

    table(["family"], "by_family")
    table(["pair_kind"], "by_pair_kind")
    df["page_kind"] = df.route_target.fillna("?") + "|" + df.page_subtype.fillna("-")
    table(["page_kind"], "by_page_kind")

    # Top buckets with duplicate share and sample pair ids.
    def bucket_rows(path_csv, samples_json, prefix, verdict_keys):
        csv = pd.read_csv(path_csv)
        samples = json.load(open(os.path.join(WORK, samples_json), encoding="utf-8"))
        rows = []
        for r in csv.itertuples(index=False):
            sub = df[(df.tag.isin(["c", "d"])) & df.status.isin(["pass", "review"])].copy()
            sub["bucket"] = sub.apply(lambda x: f"{x.tag} | {x.page_kind} | {x.pair_kind} | {x.obj_sub if isinstance(x.obj_sub, str) else ''} | "
                                      + (f"sw:{x.left_sw_reason}/{x.right_sw_reason}" if x.tag == "c" else f"{x.blind}:{x.left_match}/{x.right_match}"), axis=1)
            b = sub[sub.bucket == r.bucket]
            ss = [s for s in samples if s["rank"] == r.rank]
            rows.append({"rank": int(r.rank), "bucket": r.bucket, "pass": int(r.pass_n), "review": int(r.review_n),
                         "projects": int(r.projects),
                         "dup_same_sheet_share": round(float((b.sw_dup.str.startswith("same_sheet")).mean()), 3) if len(b) else None,
                         "no_sw_counterpart_share": round(float((b.sw_dup == "none").mean()), 3) if len(b) else None,
                         "verdict": VERDICT[verdict_keys[r.rank - 1]][0], "visual": VERDICT[verdict_keys[r.rank - 1]][1],
                         "png": f"png/{prefix}_{int(r.rank):02d}.png",
                         "samples": [{"project_id": s["project_id"], "pair_id": s["pair_id"], "sheet_id": s["sheet_id"],
                                      "status": s["status"], "left": s["left_value"], "right": s["right_value"]} for s in ss]})
        return rows

    out["top10_raw_cd_buckets"] = bucket_rows(os.path.join(LOOP, "top10_buckets.csv"), "samples.json", "bucket",
                                              [f"raw{i}" for i in range(1, 11)])
    out["top7_d3_pass_buckets"] = bucket_rows(os.path.join(LOOP, "top7_buckets_d3.csv"), "samples_d3.json", "d3",
                                              [f"d3_{i}" for i in range(1, 8)])

    # Issues: dependency and counterfactual.
    iss = pd.read_parquet(os.path.join(WORK, "issues_dependency.parquet"))
    key = df.set_index(["project_id", "pair_id"])
    rows = []
    issues_all = pd.read_parquet(os.path.join(WORK, "issues_all.parquet"))
    for r in issues_all.itertuples(index=False):
        members = [r.pair_id] + list(r.related_pair_ids)
        tags = []
        for m in members:
            if (r.project_id, m) in key.index:
                tags.append(key.loc[(r.project_id, m)].tag)
        cd_members = sum(1 for t in tags if t in ("c", "d"))
        if cd_members == 0:
            effect = "unchanged"
        elif cd_members == len(tags):
            effect = "removed"
        else:
            effect = "shrinks"
        rows.append({"project_id": r.project_id, "issue_id": r.issue_id, "rule_id": r.rule_id,
                     "primary_pair": r.pair_id, "member_tags": ",".join(tags), "effect_if_drop_cd": effect})
    eff = pd.DataFrame(rows)
    out["issues"] = {"total": int(len(eff)), "by_effect": eff.effect_if_drop_cd.value_counts().to_dict(),
                     "primary_tags": iss.primary_tag.value_counts().to_dict(),
                     "removed_rows": eff[eff.effect_if_drop_cd == "removed"].to_dict(orient="records"),
                     "shrinks_rows": eff[eff.effect_if_drop_cd == "shrinks"].to_dict(orient="records"),
                     "all_rows": eff.to_dict(orient="records")}
    analysis = json.load(open(os.path.join(WORK, "analysis.json"), encoding="utf-8"))
    out["v2"] = analysis["v2_proposals"]
    out["v2"]["panel_ignore_pairs_by_status"] = analysis["panel_ignore_pairs_by_status"]
    out["v2"]["low_conf_upper_bound_pure_pass_ordinary_or_component"] = analysis["upper_bound_low_conf_candidates_pure_pass"]
    pv = pd.read_parquet(os.path.join(WORK, "v2_proposals.parquet"))
    nsw = pv[(~pv.is_sw_definition) & (pv.n_ports > 0)]
    emit = nsw[nsw.allow_port_emission == True]  # noqa: E712
    out["v2"]["non_sw_rows_policy_emitting"] = int(len(emit))
    out["v2"]["non_sw_ports_policy_emitting"] = int(emit.n_ports.sum())
    out["v2"]["non_sw_emitting_by_family"] = {k: [int(a), int(b)] for k, (a, b) in
                                              emit.groupby("family_id").n_ports.agg(["size", "sum"]).iterrows()}
    out["v2"]["non_sw_behavior_mode_rows_with_ports"] = {k: int(v) for k, v in nsw.behavior_mode.value_counts().items()}
    usage = pd.read_parquet(os.path.join(WORK, "v2_port_usage.parquet"))
    out["v2"]["sw_labelled_terminal_pairs_by_status"] = {k: int(v) for k, v in usage.groupby("status").size().items()}
    out["v2"]["sw_labelled_terminal_pairs_by_b2_sub"] = "all b2p_partial_sw_side_missing (95 of 95)"
    json.dump(out, open(os.path.join(LOOP, "details.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("written", os.path.join(LOOP, "details.json"))
    print(json.dumps(out["pass_accounting"], ensure_ascii=False, indent=1))
    print(json.dumps(out["issues"]["by_effect"], ensure_ascii=False))
    print(json.dumps(out["issues"]["removed_rows"], ensure_ascii=False)[:800])


if __name__ == "__main__":
    main()
