"""LOGGEN-MISMATCH tight check for terminal ends (read-only).

Usage: python nearest_label_check.py <scratch_dir> <round14_dir> <out_pkl>

For every resolved terminal end ("端子", identity = its label), take the identity-like drawn texts within
R_WIDE of the port (own texts only: connect labels and cross-reference texts excluded) and find the nearest.
Terminal labels are printed in dense strips, so the loose check of build_ends (identity text anywhere within
R_WIDE) cannot tell a neighbouring label from the right one. This check reports whether the identity text is
the nearest identity-like drawn text, and if not, which text is nearest and how far each one is.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ends as be  # noqa: E402


def main(scratch: Path, round_dir: Path, out_pkl: Path) -> None:
    ends = pd.read_pickle(scratch / "ends.pkl")
    ends = ends[ends.geometry.fillna(False).astype(bool)]
    term = ends[ends.end_class == "端子"]
    rows = []
    for pid, group in term.groupby("project"):
        fdir = next(c for c in (round_dir / pid).glob("*/findings") if (c / "sw_wire_routes.parquet").exists())
        wr, sp, spi, tx, cl, page_types = be.load(fdir)
        conn = be.connect_text_ids(cl)
        tx = tx.copy()
        tx["value"] = tx["normalized_text"].where(tx["normalized_text"].notna() & (tx["normalized_text"] != ""), tx["text"]).fillna("").astype(str)
        tx["cx"] = (tx["bbox_min_x"] + tx["bbox_max_x"]) / 2
        tx["cy"] = (tx["bbox_min_y"] + tx["bbox_max_y"]) / 2
        files = {fid: be.FileTexts(f[f["value"].str.len() > 0].reset_index(drop=True), conn.get(fid, set()))
                 for fid, f in tx.groupby("file_id")}
        for r in group.itertuples():
            ft = files.get(r.file_id)
            if ft is None:
                continue
            wide = ft.near(r.x, r.y, be.R_WIDE)
            cands = sorted((d, ft.values[i]) for i, d in wide
                           if not ft.is_connect[i] and not ft.is_xref[i] and be.IDENT_LIKE.search(be.strict(ft.values[i])))
            own_ident = [d for d, v in cands if be.strict(v) == be.strict(r.identity)]
            id_dist = min(own_ident) if own_ident else None
            if not cands:
                status, nearest, nd = "no_identity_text", None, None
            else:
                nd, nearest = cands[0]
                if be.strict(nearest) == be.strict(r.identity):
                    status = "identity_is_nearest"
                elif id_dist is None:
                    status = "identity_absent"
                elif id_dist - nd < 1.0:
                    status = "identity_near_tie"
                else:
                    status = "identity_present_not_nearest"
            rows.append({"project": pid, "file_id": r.file_id, "port_id": r.port_id, "identity": r.identity,
                         "record_id": r.record_id, "x": r.x, "y": r.y, "status": status, "nearest": nearest,
                         "nearest_dist": nd, "identity_dist": id_dist, "backplate": bool(r.backplate), "verdict": r.verdict})
    out = pd.DataFrame(rows)
    out.to_pickle(out_pkl)
    print(out.status.value_counts().to_string())


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
