"""B-1 FIX step 6: static corpus impact of invisible text (raw DXF height < 0.01). Read-only.

1. Stream-scan every manifest DXF (frozen cache) for TEXT / MTEXT / ATTRIB / ATTDEF records
   with group-40 height < 0.01. Records are tagged ENTITIES or BLOCKS (block definitions).
2. Join ENTITIES-level invisible records to the round12 engine artifacts by
   (project, file_id, handle) using findings/texts.parquet, then take each text's consumers
   from terminal_candidates.parquet (accepted) and pairs.parquet (pair_kind via left/right text_id).
   BLOCKS-level records cannot be joined by handle (engine uses virtual handles
   "<insert>:VIRTUAL:n"), so they are reported as a population only.
3. Write detail CSV + summary JSON to .tmp/loop_invis_impact/ (kept for review).

Round12 artifacts pre-date the current HEAD, so consumer counts are the engine's behaviour
before this fix. Nothing is written inside the corpus or the round12 tree.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MANIFEST, ROOT, ROUND  # noqa: E402

OUT = ROOT / ".tmp" / "loop_invis_impact"
TYPES = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}


def scan_dxf(path: str) -> list[dict]:
    """Return tiny-height text records (TEXT/MTEXT/ATTRIB/ATTDEF) with section tag."""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        lines = fh.read().split("\n")
    out: list[dict] = []
    section = "?"
    expect_section_name = False
    rec: dict | None = None

    def flush(current: dict | None) -> None:
        if current is None or current.get("type") not in TYPES:
            return
        h = current.get("height")
        if h is not None and h < 0.01:
            out.append({
                "type": current["type"],
                "handle": current.get("handle", ""),
                "layer": current.get("layer", ""),
                "section": current.get("section", "?"),
                "height": h,
                "text": current.get("text", ""),
            })

    for k in range(0, len(lines) - 1, 2):
        code = lines[k].strip()
        val = lines[k + 1].strip()
        if code == "0":
            flush(rec)
            if val == "SECTION":
                expect_section_name = True
                rec = None
                continue
            if val == "ENDSEC":
                rec = None
                section = "?"
                continue
            rec = {"type": val, "section": section}
            continue
        if expect_section_name and code == "2":
            section = val.upper()
            expect_section_name = False
            continue
        if rec is None:
            continue
        if code == "5" and "handle" not in rec:
            rec["handle"] = val
        elif code == "8" and "layer" not in rec:
            rec["layer"] = val
        elif code == "40" and "height" not in rec:
            try:
                rec["height"] = float(val)
            except ValueError:
                pass
        elif code == "1" and "text" not in rec:
            rec["text"] = val
    flush(rec)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    scanned = 0
    population = []
    for proj in MANIFEST["projects"]:
        for f in proj["files"]:
            scanned += 1
            for rec in scan_dxf(f["dxf_path"]):
                rec.update(project=proj["project_id"], file_id=f["file_id"])
                population.append(rec)
    pop = pd.DataFrame(population)
    pop.to_csv(OUT / "invisible_dxf_population.csv", index=False, encoding="utf-8-sig")

    summary: dict = {
        "files_scanned": scanned,
        "scan_seconds": round(time.time() - t0, 1),
        "population_total": int(len(pop)),
        "population_by_section": pop.groupby("section").size().to_dict() if len(pop) else {},
        "population_by_type": pop.groupby("type").size().to_dict() if len(pop) else {},
        "population_numeric_entities": int(pop[(pop.section == "ENTITIES") & pop.text.fillna("").str.fullmatch(r"\d+")].shape[0]) if len(pop) else 0,
        "population_numeric_blocks": int(pop[(pop.section == "BLOCKS") & pop.text.fillna("").str.fullmatch(r"\d+")].shape[0]) if len(pop) else 0,
        "zero_height_records": int((pop.height == 0).sum()) if len(pop) else 0,
    }

    top = pop[pop.section == "ENTITIES"].copy() if len(pop) else pop
    joined_rows: list[dict] = []
    engine_runs = sorted(ROUND.glob("p*/*/findings/texts.parquet"))
    summary["round12_runs"] = len(engine_runs)
    handled_keys = set()
    for texts_path in engine_runs:
        fdir = texts_path.parent
        proj = fdir.relative_to(ROUND).parts[0]
        sub = top[top.project == proj] if len(top) else top
        if sub.empty:
            continue
        texts = pd.read_parquet(texts_path)
        texts["handle"] = texts["handle"].astype(str)
        cand_path = fdir / "terminal_candidates.parquet"
        cands = pd.read_parquet(cand_path) if cand_path.exists() else pd.DataFrame()
        pairs_path = fdir / "pairs.parquet"
        pairs = pd.read_parquet(pairs_path) if pairs_path.exists() else pd.DataFrame()
        assign_path = fdir / "text_assignments.parquet"
        assign = pd.read_parquet(assign_path) if assign_path.exists() else pd.DataFrame()
        m = texts.merge(sub[["file_id", "handle", "height", "layer", "text"]].rename(
            columns={"height": "dxf_height", "layer": "dxf_layer", "text": "dxf_text"}),
            on=["file_id", "handle"], how="inner")
        # Channel usage is read from the candidate and pair tables directly, because
        # text_assignments keeps a single row per text (it under-counts accepted candidates).
        cand_by_text = cands.groupby("text_id") if len(cands) else None
        pair_by_text: dict[str, list] = {}
        if len(pairs):
            for r in pairs[["pair_id", "pair_kind", "status", "left_text_id", "right_text_id"]].itertuples(index=False):
                for tid in (r.left_text_id, r.right_text_id):
                    if isinstance(tid, str) and tid:
                        pair_by_text.setdefault(tid, []).append((r.pair_id, r.pair_kind, r.status))
        for _, t in m.iterrows():
            handled_keys.add((proj, t["file_id"], t["handle"]))
            if cand_by_text is not None and t.text_id in cand_by_text.groups:
                c = cands.loc[cand_by_text.groups[t.text_id]]
            else:
                c = cands.iloc[0:0] if len(cands) else cands
            cand_status = sorted(set(c.status.dropna().astype(str))) if len(c) else []
            accepted_values = ";".join(sorted(set(c[c.status == "accepted"].value.dropna().astype(str)))) if len(c) else ""
            pr = pair_by_text.get(t.text_id, [])
            kinds = sorted({k for _, k, _ in pr if isinstance(k, str)})
            a = assign[assign.text_id == t.text_id] if len(assign) else assign
            in_audit = bool(a.in_audit_area.any()) if len(a) and "in_audit_area" in a.columns else None
            joined_rows.append({
                "project": proj,
                "sheet_id": t.sheet_id,
                "file_id": t["file_id"],
                "text_id": t.text_id,
                "handle": t.handle,
                "text": t.text,
                "layer": t.layer,
                "dxf_height": t.dxf_height,
                "is_numeric_candidate": bool(t.is_numeric_candidate),
                "in_audit_area": in_audit,
                "n_candidates": int(len(c)),
                "candidate_status": ";".join(cand_status),
                "accepted_terminal": "accepted" in cand_status,
                "accepted_values": accepted_values,
                "pair_ids": ";".join(str(p) for p, _, _ in pr),
                "pair_kinds": ";".join(kinds),
                "pair_status": ";".join(sorted({str(s) for _, _, s in pr})),
                "uses_table": "table_mapping" in kinds,
                "uses_component": any("component" in k for k in kinds),
                "uses_other_pair_channel": any(k in {"ordinary_pair", "semantic_mapping", "continuation", "bridge_mapping"} for k in kinds),
            })
    J = pd.DataFrame(joined_rows)
    J.to_csv(OUT / "invisible_engine_joined.csv", index=False, encoding="utf-8-sig")

    not_extracted = top[[ (p, f, h) not in handled_keys for p, f, h in zip(top.project, top.file_id, top.handle) ]] if len(top) else top
    summary["entities_invisible_joined_to_engine_text"] = int(len(J))
    summary["entities_invisible_not_in_engine_texts"] = int(len(not_extracted))
    summary["entities_invisible_not_in_engine_texts_numeric"] = int(not_extracted.text.fillna("").str.fullmatch(r"\d+").sum()) if len(not_extracted) else 0
    if len(J):
        summary["joined_numeric_candidates"] = int(J.is_numeric_candidate.sum())
        summary["joined_in_audit_area"] = int((J.in_audit_area == True).sum())
        summary["joined_accepted_terminal_candidate"] = int(J.accepted_terminal.sum())
        summary["joined_uses_table_mapping"] = int(J.uses_table.sum())
        summary["joined_uses_component_mapping"] = int(J.uses_component.sum())
        summary["joined_uses_other_pair_channel"] = int(J.uses_other_pair_channel.sum())
        summary["joined_any_consumer"] = int(((J.pair_kinds != "") | (J.n_candidates > 0)).sum())
        summary["joined_with_any_candidate"] = int((J.n_candidates > 0).sum())
        summary["joined_with_any_pair"] = int((J.pair_kinds != "").sum())
        summary["joined_by_project"] = J.groupby("project").size().sort_values(ascending=False).head(25).to_dict()
        summary["joined_accepted_terminal_by_project"] = J[J.accepted_terminal].groupby("project").size().to_dict()
        summary["joined_uses_table_by_project"] = J[J.uses_table].groupby("project").size().to_dict()
        summary["joined_uses_component_by_project"] = J[J.uses_component].groupby("project").size().to_dict()
    (OUT / "invisible_impact_static.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
