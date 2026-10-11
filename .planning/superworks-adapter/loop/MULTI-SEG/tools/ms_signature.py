"""MULTI-SEG: per-candidate signature of the 870 refused split candidates (read-only, reads cls870.json).

Signature = outer-end classes + gap classes, in axis order. Classes are drawn from measured features only:
  gap  BODY        the candidate's own terminal body (2 TERMPOINTs of one insert across the gap, width ~ body)
  gap  BODY_O      another terminal body (TERMPOINT of a device terminal inside the gap, no crossing/symbol pins)
  gap  SYM         a symbol: device/internal TERMPOINTs or a model line crossing the gap, with or without text
  gap  LBL         label-only gap: texts and nothing else (no TERMPOINT, no crossing line, no dot)
  gap  DOT         a connect dot in the gap (junction)
  gap  EMPTY       nothing in the gap
  end  TERM        touches a plain terminal (category 端子)
  end  ELEM        touches an internal element pin (内部元件 / 线圈)
  end  UNREG       touches an unregistered SYMB2 block pin (G1P)
  end  DEVTERM     touches a device terminal TERMPOINT that is not the candidate pair
  end  BRANCH      a non-member model line ends on it and it is a T (dot or through line)
  end  CORNER      a non-member model line ends on it (corner, no through line)
  end  BLANK       nothing touches it
Usage: python ms_signature.py  -> writes .tmp/multiseg_work/sig870.json and prints the stratum counts.
"""
from __future__ import annotations

import json
import collections
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/multiseg_work")


def gap_class(g) -> str:
    kinds = {t["kind"] for t in g["texts"]}
    cats = {t["category"] for t in g["termpoints"]}
    if g["is_candidate_gap"]:
        return "BODY"
    if cats & {"内部元件", "线圈"} or g["crossing_lines"] or ("装置端子" in cats and g["texts"] and g["width"] > 5):
        return "SYM"
    if "装置端子" in cats or "端子" in cats or "接地" in cats:
        return "BODY_O"
    if g["dots"]:
        return "DOT"
    if g["texts"]:
        return "LBL"
    return "EMPTY"


def end_class(tokens) -> str:
    t = set(tokens)
    if "port:端子" in t or "contact:端子" in t:
        return "TERM"
    if "port:内部元件" in t or "contact:内部元件" in t or "port:线圈" in t:
        return "ELEM"
    if "unreg_pin" in t:
        return "UNREG"
    if "port:装置端子" in t or "contact:装置端子" in t:
        return "DEVTERM"
    if "T" in t or "branch" in t:
        return "BRANCH"
    if "corner" in t:
        return "CORNER"
    if "dot" in t:
        return "DOT"
    return "BLANK"


def main():
    recs = json.loads((WORK / "cls870.json").read_text(encoding="utf-8"))
    out = []
    sig = collections.Counter()
    for i, r in enumerate(recs):
        gaps = [gap_class(g) for g in r["gaps"]]
        left, right = end_class(r["ends"]["outer_left"]), end_class(r["ends"]["outer_right"])
        signature = "%s|%s|%s" % (left, "-".join(gaps), right)
        rec = {"index": i, "pid": r["pid"], "file_id": r["file_id"], "sheet_id": r["sheet_id"],
               "line_group_id": r["line_group_id"], "identity": r["identity"], "n_pieces": r["n_pieces"],
               "n_lines": r["n_lines"], "orientation": r["orientation"], "signature": signature,
               "left": left, "right": right, "gaps": gaps, "ends_raw": r["ends"]}
        out.append(rec)
        sig[signature] += 1
    (WORK / "sig870.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("signatures", len(sig))
    for k, v in sig.most_common(60):
        print(v, k)


if __name__ == "__main__":
    main()
