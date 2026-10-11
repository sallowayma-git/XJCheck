"""PIN-ID step 1b: raw category of the Pop-X pin ends, read from the LOGGEN dictionary of each frozen DXF (read-only).

The replay output keeps only the category of resolved ends (it overwrites the field for unresolved ones),
so the PART2_n category field (index 7) is read again here for the insert_not_sw ends.
Usage: python 09_loggen_raw_category.py <pop_x.pkl> <corpus_manifest.json> <out_json>
"""
import collections
import json
import pickle
import sys
from pathlib import Path

import ezdxf


def parse_part2(value):
    seg = str(value or "").split("||")

    def at(i):
        return seg[i].strip() if len(seg) > i else ""
    return {"device": at(1), "pin": at(2), "seq": at(3), "side": at(4), "block": at(5),
            "terminal": at(6).upper(), "category": at(7)}


def main(popx_pkl, manifest, out_json):
    px = pickle.load(open(popx_pkl, "rb"))
    man = json.loads(Path(manifest).read_text(encoding="utf-8"))
    dmap = {(p["project_id"], f["file_id"]): f["dxf_path"] for p in man["projects"] for f in p["files"]}
    need = collections.defaultdict(list)
    for x in px:
        need[(x["pid"], x["file"])].append(x)
    counts = collections.Counter()
    table = {}
    for (pid, fid), items in need.items():
        try:
            doc = ezdxf.readfile(dmap[(pid, fid)])
        except Exception:
            try:
                from ezdxf import recover
                doc, _ = recover.readfile(dmap[(pid, fid)])
            except Exception:
                counts["read_failed"] += len(items)
                continue
        root = doc.rootdict.get("LD_SYMB2LOGGEN_DICTIONARY")
        recs = {}
        if root is not None:
            for key, rec in root.items():
                if rec.dxftype() != "XRECORD":
                    continue
                recs[str(rec.dxf.handle)] = [str(t.value) for t in rec.tags if t.code == 1]
        for x in items:
            vals = recs.get(x["record"].split(":")[-1]) or []
            # record key is the dictionary key; match by record id suffix
            found = None
            for key, rec in root.items() if root is not None else []:
                if key == x["record"].split(":")[-1]:
                    found = [str(t.value) for t in rec.tags if t.code == 1]
                    break
            if found is None:
                # fall back to LD_SYMB2LOGGEN_<n> naming used by the replay
                tail = x["record"].split(":")[-1]
                if root is not None and tail in root:
                    found = [str(t.value) for t in root[tail].tags if t.code == 1]
            if not found:
                counts["record_not_found"] += 1
                continue
            cats = [parse_part2(v) for i, v in enumerate(found) if i and False]
            ends = []
            fields = {}
            for name, value in zip(found[::2], found[1::2]):
                fields.setdefault(name.strip().upper(), value)
            for name in sorted((k for k in fields if k.startswith("PART2_")), key=lambda k: int(k.split("_")[1])):
                ends.append(parse_part2(fields[name]))
            match = [e for e in ends if e["terminal"] == str(x["insert"]).upper() and e["pin"] == x["pin"]]
            cat = match[0]["category"] if match else None
            table[f"{x['pid']}|{x['file']}|{x['insert']}|{x['pin']}"] = cat
            counts[cat if cat is not None else "no_match"] += 1
    out = dict(counts=dict(counts), n=len(px))
    Path(out_json).write_text(json.dumps(dict(summary=out, table=table), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
