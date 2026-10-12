"""LEGACY-CENSUS step 2: Top-10 buckets of legacy-only (c, d) pass/review pairs and render samples.

Bucket key = tag | page kind (route_target|page_subtype) | pair_kind | object subtype | blind/SW reason.
Samples: 3 per bucket, drawn with a fixed seed, spread over projects where possible.
Writes .tmp/legacy_census_work/buckets.parquet and samples.json (inputs to render_buckets.py).
"""
from __future__ import annotations

import glob
import json
import os
import random
import sys

import pandas as pd

ROOT = "F:/workspace/XJToolkit"
WORK = os.path.join(ROOT, ".tmp/legacy_census_work")
RUN = os.path.join(ROOT, ".tmp/superworks_round23_full")
MANIFEST = os.path.join(ROOT, ".planning/superworks-adapter/corpus_manifest.json")
LOOP = os.path.join(ROOT, ".planning/superworks-adapter/loop/LEGACY-CENSUS")


def reason_of(r):
    if r.tag == "c":
        return f"sw:{r.left_sw_reason}/{r.right_sw_reason}"
    return f"{r.blind}:{r.left_match}/{r.right_match}"


def main():
    # mode "raw": all c/d pass+review (Top 10); mode "d3": c/d pass with no SW counterpart in the project (Top 7).
    mode = sys.argv[1] if len(sys.argv) > 1 else "raw"
    suffix = "" if mode == "raw" else "_d3"
    df = pd.read_parquet(os.path.join(WORK, "pairs_tagged_v2.parquet"))
    df["page_kind"] = df.route_target.fillna("?") + "|" + df.page_subtype.fillna("-")
    if mode == "raw":
        L = df[df.tag.isin(["c", "d"]) & df.status.isin(["pass", "review"])].copy()
        n_top = 10
    else:
        L = df[df.tag.isin(["c", "d"]) & (df.status == "pass") & (df.sw_dup == "none")].copy()
        n_top = 7
    L["reason"] = L.apply(reason_of, axis=1)
    L["bucket"] = (L.tag + " | " + L.page_kind + " | " + L.pair_kind + " | " + L.obj_sub.fillna("")
                   + " | " + L.reason)
    agg = (L.groupby(["bucket", "tag", "page_kind", "pair_kind", "obj_sub", "reason"])
             .agg(pass_n=("status", lambda s: int((s == "pass").sum())),
                  review_n=("status", lambda s: int((s == "review").sum())),
                  projects=("project_id", "nunique"))
             .reset_index())
    agg["total"] = agg.pass_n + agg.review_n
    agg = agg.sort_values("total", ascending=False).reset_index(drop=True)
    agg.to_parquet(os.path.join(WORK, f"buckets{suffix}.parquet"), index=False)
    top = agg.head(n_top).copy()
    top.insert(0, "rank", range(1, len(top) + 1))
    top.to_csv(os.path.join(LOOP, f"top{n_top}_buckets{suffix}.csv"), index=False, encoding="utf-8-sig")

    rng = random.Random(20261012)
    samples = []
    for rank, b in enumerate(top.itertuples(index=False), 1):
        rows = L[L.bucket == b.bucket]
        # Prefer distinct projects, then mix pass/review when both exist.
        picked = []
        for pid, grp in rows.groupby("project_id"):
            picked.append(grp.sample(1, random_state=rng.randint(0, 10**6)).iloc[0])
        rng.shuffle(picked)
        picked = picked[:3] if len(picked) >= 3 else picked
        if len(picked) < 3:
            extra = rows.sample(min(len(rows), 3 - len(picked)), random_state=rng.randint(0, 10**6))
            picked += [r for _, r in extra.iterrows()]
        for k, r in enumerate(picked, 1):
            samples.append({"rank": rank, "k": k, "bucket": b.bucket, "project_id": r.project_id,
                            "pair_id": r.pair_id, "sheet_id": r.sheet_id, "status": r.status,
                            "tag": r.tag, "pair_kind": r.pair_kind, "page_kind": r.page_kind,
                            "obj_sub": r.obj_sub, "reason": r.reason,
                            "left_value": r.left_value, "right_value": r.right_value,
                            "left_text_id": r.left_text_id, "right_text_id": r.right_text_id,
                            "left_xy": [r.left_x, r.left_y], "right_xy": [r.right_x, r.right_y],
                            "line_group_id": r.line_group_id, "rationale": r.rationale,
                            "left_match": r.left_match, "right_match": r.right_match})
    # Resolve file ids and frozen DXF paths; attach SW port anchors for the matched texts.
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    dxf_by_file = {}
    for p in manifest["projects"]:
        for f in p["files"]:
            dxf_by_file[(p["project_id"], f["file_id"])] = f["dxf_path"]
    file_by_sheet = {}
    for pdir in sorted(d for d in os.listdir(RUN) if len(d) == 4 and d.startswith("p") and d[1:].isdigit()):
        fdirs = glob.glob(os.path.join(RUN, pdir, "*", "findings"))
        if not fdirs:
            continue
        pages = pd.read_parquet(os.path.join(fdirs[0], "pages.parquet"), columns=["sheet_id", "file_id"])
        for r in pages.itertuples(index=False):
            file_by_sheet[(pdir, r.sheet_id)] = r.file_id
    for s in samples:
        s["file_id"] = file_by_sheet.get((s["project_id"], s["sheet_id"]))
        s["dxf"] = dxf_by_file.get((s["project_id"], s["file_id"]))
        fdir = glob.glob(os.path.join(RUN, s["project_id"], "*", "findings"))[0]
        sp = pd.read_parquet(os.path.join(fdir, "sw_ports.parquet"))
        anchors = []
        for r in sp[sp.sheet_id == s["sheet_id"]].itertuples(index=False):
            lab = json.loads(r.label) if r.label else {}
            pin = json.loads(r.pin) if r.pin else {}
            tids = {lab.get("text_id"), pin.get("text_id")}
            for side, t in (("L", s["left_text_id"]), ("R", s["right_text_id"])):
                if t and t in tids:
                    anchors.append({"side": side, "port_id": r.record_id, "identity": r.endpoint_identity,
                                    "start": [r.start_x, r.start_y], "end": [r.end_x, r.end_y]})
        s["sw_anchors"] = anchors
        tx = pd.read_parquet(os.path.join(fdir, "texts.parquet"), columns=["text_id", "sheet_id", "insert_x", "insert_y", "text"])
        tx = tx[tx.sheet_id == s["sheet_id"]].set_index("text_id")
        s["text_anchors"] = {}
        for side, t in (("L", s["left_text_id"]), ("R", s["right_text_id"])):
            if t and t in tx.index:
                row = tx.loc[t]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                s["text_anchors"][side] = {"text_id": t, "text": str(row.text), "xy": [float(row.insert_x), float(row.insert_y)]}
        if s["line_group_id"]:
            lg = pd.read_parquet(os.path.join(fdir, "line_groups.parquet"))
            g = lg[lg.line_group_id == s["line_group_id"]]
            s["group_xy"] = [[float(g.start_x.iloc[0]), float(g.start_y.iloc[0]), float(g.end_x.iloc[0]), float(g.end_y.iloc[0])]] if len(g) else []
        else:
            s["group_xy"] = []
    json.dump(samples, open(os.path.join(WORK, f"samples{suffix}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(top[["rank", "bucket", "pass_n", "review_n", "projects"]].to_string())
    print("samples", len(samples), "missing dxf", sum(1 for s in samples if not s["dxf"]))


if __name__ == "__main__":
    main()
