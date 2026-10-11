"""LOGGEN-MISMATCH negative control (read-only): does the drawn-text check still accept a wrong identity?

Usage: python control_check.py <scratch_dir> <round14_dir> <out_json>

For a seeded random sample of ends whose verdict is an agreement, the identity's last digit is changed
(+1 mod 10 on the trailing digit run) and the same drawn-text verdict is recomputed. If the altered
identity is still judged as agreeing, the checker is too permissive for that case. The rate is reported
per end class; it is a false-agreement estimate under a random single-digit error.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ends as be  # noqa: E402

SEED = 20261012
SAMPLE = 4000


def mutate(identity: str) -> str | None:
    m = re.search(r"(\d+)(\D*)$", identity)
    if not m:
        return None
    digits = m[1]
    new = digits[:-1] + str((int(digits[-1]) + 1) % 10)
    return identity[:m.start(1)] + new + identity[m.end(1):]


def main(scratch: Path, round_dir: Path, out_json: Path) -> None:
    ends = pd.read_pickle(scratch / "ends.pkl")
    ends = ends[ends.geometry.fillna(False).astype(bool)]
    agree = ends[ends.verdict.str.startswith("agree")]
    sample = agree.sample(n=min(SAMPLE, len(agree)), random_state=SEED)
    rows = []
    cache = {}
    for pid, group in sample.groupby("project"):
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
            alt = mutate(str(r.identity))
            if not alt:
                continue
            wide = ft.near(r.x, r.y, be.R_WIDE)
            near = [(i, d) for i, d in wide if d <= be.R_NEAR]
            verdict, _ = be.verdict(alt, ft, bool(r.backplate), wide, near, r.x, r.y)
            rows.append({"project": pid, "file_id": r.file_id, "end_class": r.end_class, "identity": r.identity,
                         "mutated": alt, "original_verdict": r.verdict, "mutated_verdict": verdict,
                         "still_agree": verdict.startswith("agree")})
    out = pd.DataFrame(rows)
    summary = {"sampled": int(len(out)),
               "still_agree_total": int(out.still_agree.sum()) if len(out) else 0,
               "by_class": {k: {"n": int(len(g)), "still_agree": int(g.still_agree.sum())}
                            for k, g in out.groupby("end_class")} if len(out) else {},
               "mutated_verdict_counts": out.mutated_verdict.value_counts().to_dict() if len(out) else {}}
    out.to_pickle(scratch / "control.pkl")
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
