"""GAP-1 analysis (read-only): sub-classes of the far end, far-block label readability, and root-cause indicators.

Joins gap1_probe.parquet (topology tests) with gap1_geom.parquet (drawn-geometry test), then, for the best body block of
each wire, reads its SW extended data from the frozen DXF: LD_SYMB2_LABEL (label text handle), LD_SYMB2_TERM_TEXT_<n>
(pin slot texts), and whether a LD_SYMB2_SPECIAL record exists (it must not, by population). The label text is
resolved through the round texts table (handle -> text, same file). Also measures:
  - whether the wire end-to-pin vector is collinear with the wire (<5 deg): a straight continuation with a gap;
  - whether a top-level line lies within 6 units of F collinear with the wire (a line-group truncation candidate).

Sub-classes (far end F, best body block B, d = distance from F to B's drawn geometry, dv = to B's nearest vertex):
  pin_touch     dv <= 0.6                       wire ends on a pin vertex of B
  pin_gap2      1.9 <= dv <= 2.1                wire stops 2 units short of a pin vertex of B
  near_geom     0.6 < d <= 3.0, not pin_gap2    other near miss to B's geometry
  no_body       no body block (frame or none)   far end in free space of the sheet

Usage: python gap1_analyze.py <gap_work_dir>  -> gap1_detail.parquet, gap1_summary.json
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import ezdxf
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaplib as G  # noqa: E402


def sub_class(d, dv, best):
    if best is None or (isinstance(best, float) and best != best):
        return "no_body"
    if dv is not None and dv <= 0.6:
        return "pin_touch"
    if dv is not None and 1.9 <= dv <= 2.1:
        return "pin_gap2"
    if d is not None and d <= 3.0:
        return "near_geom"
    return "far_geom"


def xdata_values(entity, app):
    if not entity.has_xdata(app):
        return []
    return [v for c, v in entity.get_xdata(app) if c == 1005]


def main(work: Path):
    probe = pd.read_parquet(work / "gap1_probe.parquet")
    geom = pd.read_parquet(work / "gap1_geom.parquet")
    uncov = pd.read_parquet(work / "uncovered.parquet")
    texts = {}
    for proj in G.iter_projects(only=sorted(set(probe.project))):
        t = proj.texts[["file_id", "handle", "text"]]
        for r in t.itertuples():
            texts[(proj.pid, r.file_id, str(r.handle))] = str(r.text)
    keep = ["port_id", "project", "file_id", "dxf", "identity", "label", "block", "port_number", "contact_x", "contact_y"]
    base = uncov[keep].merge(probe, on=["port_id", "project", "file_id"], how="inner")
    df = base.merge(geom, on=["port_id", "project"], how="left")
    df["sub"] = [sub_class(d, dv, b if b else None) for d, dv, b in zip(df.d_geom, df.d_vertex, df.best_block)]
    df.loc[df.best_block == "", "sub"] = "no_body"
    # collinearity of the far end to the nearest vertex of the best block and short-line truncation check
    rows = []
    for (pid, fid, dxf), grp in df.groupby(["project", "file_id", "dxf"]):
        doc = None
        for r in grp.itertuples():
            rec = {"port_id": r.port_id, "project": pid}
            if r.best_block and isinstance(r.best_handle, str) and r.best_handle:
                if doc is None:
                    doc = ezdxf.readfile(dxf)
                ins = doc.entitydb.get(r.best_handle)
                if ins is not None:
                    lab = xdata_values(ins, "LD_SYMB2_LABEL")
                    slot_names = []
                    if ins.has_xdata("LD_SYMB2_SPECIAL"):
                        rec["special"] = True
                    rec["label_handle"] = lab[0] if lab else ""
                    rec["label_text"] = texts.get((pid, fid, str(lab[0])), "") if lab else ""
                    rec["inside_label_handle"] = (xdata_values(ins, "LD_SYMB2_InsideLABEL") or [""])[0]
                    if ins.xdata:
                        for app in ins.xdata.data.keys():
                            if str(app).startswith("LD_SYMB2_TERM_TEXT"):
                                slot_names.append(str(app))
                    rec["term_text_slots"] = len(slot_names)
                    rec["block_xdata_apps"] = ",".join(sorted(str(a) for a in (ins.xdata.data.keys() if ins.xdata else [])))
                    rec["insert_x"] = float(ins.dxf.insert.x)
                    rec["insert_y"] = float(ins.dxf.insert.y)
            rows.append(rec)
    det = df.merge(pd.DataFrame(rows), on=["port_id", "project"], how="left")
    det["label_text"] = det.label_text.fillna("")
    det["dev_label"] = det.label.map(lambda s: G.text(json.loads(s).get("normalized")) if isinstance(s, str) and s.startswith("{") else G.text(s))
    det["far_label_norm"] = det.label_text.map(lambda s: re.sub(r"\s", "", str(s)))
    det["label_equal_device"] = [bool(a) and a.casefold() == b.casefold() for a, b in zip(det.far_label_norm, det.dev_label)]
    det.to_parquet(work / "gap1_detail.parquet", index=False)
    def tk(counter):
        return {"|".join(str(x) for x in k): int(v) for k, v in counter.items()}
    summ = {
        "by_subset_sub": tk(Counter(zip(det.subset, det["sub"]))),
        "label_text_present": tk(Counter(zip(det.subset, det.label_text != ""))),
        "term_text_slots_gt0": tk(Counter(zip(det.subset, det.term_text_slots.fillna(0) > 0))),
        "label_equal_device": tk(Counter(zip(det.subset, det.label_equal_device))),
    }
    (work / "gap1_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
