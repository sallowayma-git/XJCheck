"""端子排行属性的冗余检查（只读）：判断未被引用的属性是否与已用信息等价。

对每个 屏端子图 页（模型空间）的端子行 TEXT（带 DZ_SERIALNUMBER_NAME）统计：
  R1 DZ_SERIALNUMBER_NAME == LD_DZPNO_HEADHANDLE 指向文字（表头名）
  R2 DZ_SERIALNUMBER_DZLX == "试验端子:粗线" 与 LD_DZPNO_DZLX 指向实体为 LWPOLYLINE（已用）是否一致
  R3 LD_DZPNO_DXLX_OUT 指向文字 == LD_DZPNO_DXLX 指向文字 的比例
  R4 行文字为空的比例（DZ_SERIALNUMBER_NAME 有值但行号为空）

用法: python strip_redundancy.py --index <page_index.json> --out <json> [--workers 8]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from multiprocessing import Pool

import ezdxf


def _xv(e, app, code=1000):
    if not e.xdata or app not in e.xdata.data:
        return []
    return [str(t.value) for t in e.xdata.data[app] if t.code == code]


def _txt(x):
    if x is None:
        return None
    if x.dxftype() == "MTEXT":
        return x.plain_text().strip()
    if x.dxftype() in ("TEXT", "ATTRIB"):
        return x.dxf.text.strip()
    return None


def _job(row):
    c = collections.Counter()
    try:
        doc = ezdxf.readfile(row["dxf_path"])
        for e in doc.modelspace():
            if e.dxftype() != "TEXT" or not e.xdata or "DZ_SERIALNUMBER_NAME" not in e.xdata.data:
                continue
            c["rows"] += 1
            name = (_xv(e, "DZ_SERIALNUMBER_NAME") or [""])[0].strip()
            hh = (_xv(e, "LD_DZPNO_HEADHANDLE", 1005) or [""])[0]
            hdr = _txt(doc.entitydb.get(hh)) if hh and hh != "0" else None
            if hdr is not None:
                c["R1_header_present"] += 1
                if hdr.strip() == name:
                    c["R1_name_equals_header"] += 1
            dz = (_xv(e, "DZ_SERIALNUMBER_DZLX") or [""])[0].strip()
            ph = (_xv(e, "LD_DZPNO_DZLX", 1005) or [""])[0]
            pe = doc.entitydb.get(ph) if ph and ph != "0" else None
            poly = pe is not None and pe.dxftype() == "LWPOLYLINE"
            if dz == "试验端子:粗线":
                c["R2_dzlx_test"] += 1
                if poly:
                    c["R2_test_and_used_polyline"] += 1
            elif poly:
                c["R2_polyline_but_dzlx_not_test"] += 1
            if poly:
                c["R2_polyline_total"] += 1
            outh = (_xv(e, "LD_DZPNO_DXLX_OUT", 1005) or [""])[0]
            inh = (_xv(e, "LD_DZPNO_DXLX", 1005) or [""])[0]
            ot = _txt(doc.entitydb.get(outh)) if outh and outh != "0" else None
            it = _txt(doc.entitydb.get(inh)) if inh and inh != "0" else None
            if ot is not None:
                c["R3_out_present"] += 1
                if it is not None:
                    c["R3_out_and_in_present"] += 1
                    if ot == it:
                        c["R3_out_equals_in"] += 1
                    else:
                        c["R3_out_differs_in"] += 1
            if not (e.dxf.text or "").strip():
                c["R4_empty_row_text"] += 1
    except Exception as ex:  # noqa: BLE001
        c["error"] += 1
    return dict(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    rows = [r for r in json.load(open(args.index, encoding="utf-8")) if r["page_type"] == "屏端子图"]
    tot = collections.Counter()
    with Pool(args.workers) as pool:
        for res in pool.imap_unordered(_job, rows, chunksize=2):
            tot.update(res)
    json.dump({"pages": len(rows), "counts": dict(tot)}, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"pages": len(rows), "counts": dict(tot)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
