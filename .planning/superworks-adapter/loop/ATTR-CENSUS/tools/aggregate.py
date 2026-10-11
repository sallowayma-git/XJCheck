"""把逐文件深扫 JSON 汇总为全语料计数表（details.json 的原始素材）。

只读：输入为 build_index.py 的页面索引与 deep_scan.py 的工作目录；
代码引用核对只读扫描 src/dwg_audit/**/*.py。

用法: python aggregate.py --index <page_index.json> --work <deep dir> --out <details_raw.json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
SRC = os.path.join(REPO, "src", "dwg_audit")

# 代码中以 f-string / 正则 / 前缀方式引用的键族（字面量 grep 无法命中，需人工映射）
PATTERN_REFS = {
    # superworks_semantics.py:467  f"LDDZ_{side}TEXT_HANDLE{branch}"，branch 为 "" 或 "_2"
    r"^LDDZ_(LEFT|RIGHT)TEXT_HANDLE(_2)?$": "extract/superworks_semantics.py:467 f-string 拼接",
    # superworks_semantics.py:372 startswith；terminal_port_bindings.py:18 正则
    r"^LD_SYMB2_TERM_TEXT_\d+$": "extract/superworks_semantics.py:372 前缀 + terminal_port_bindings.py:18 正则",
    # terminal_port_bindings.py:21 对 XRECORD 键的正则（非 XDATA appid）
    r"^PART2_\d+$": "extract/terminal_port_bindings.py:21 XRECORD 键正则",
}


def _pattern_ref(app: str):
    for pat, note in PATTERN_REFS.items():
        if re.match(pat, app):
            return note
    return None


def _load_src():
    texts = {}
    for root, _, files in os.walk(SRC):
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                texts[os.path.relpath(p, SRC).replace(os.sep, "/")] = open(p, encoding="utf-8", errors="ignore").read()
    return texts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    index = json.load(open(args.index, encoding="utf-8"))
    idx_by_key = {(r["project_id"], r["file_id"]): r for r in index}
    files = glob.glob(os.path.join(args.work, "*.json"))
    total_pages = collections.Counter(r["page_type"] for r in index)
    total_fam = collections.Counter(r["family"] for r in index)

    ent_app = collections.Counter()              # scope|etype|app -> entities
    app_pages = collections.defaultdict(set)     # app -> {(pid,fid)}
    app_pt = collections.defaultdict(collections.Counter)   # app -> page_type -> pages
    app_fam = collections.defaultdict(collections.Counter)  # app -> family -> pages
    app_sig = collections.defaultdict(collections.Counter)  # app -> scope|etype|sig -> entities
    app_ex = collections.defaultdict(list)       # app -> examples
    str_vals = collections.defaultdict(collections.Counter)  # app|code -> value counts
    hlink = collections.Counter()                # app|target|resolved
    layer_all = collections.Counter()            # page_type|scope|etype|layer
    color_all = collections.Counter()            # page_type|scope|etype|color|lt
    ld_layer = collections.Counter()             # etype|app|layer
    attdef_tags = collections.Counter()
    attdef_default = collections.defaultdict(collections.Counter)
    attrib_tags = collections.Counter()
    attrib_vals = collections.defaultdict(collections.Counter)
    ext_keys = collections.Counter()
    xrec_kv = collections.Counter()              # label|key -> count
    xrec_kv_pages = collections.defaultdict(set)
    xrec_kv_ex = collections.defaultdict(list)
    xrec_sigs = collections.Counter()
    dict_keys = collections.Counter()
    obj_types = collections.Counter()
    obj_types_pt = collections.defaultdict(collections.Counter)
    group_stats = collections.Counter()
    group_member_types = collections.Counter()
    group_pages = set()
    root_dicts = collections.defaultdict(lambda: {"files": set(), "names": collections.Counter(), "types": collections.Counter(),
                                                  "tag_sigs": collections.Counter(), "examples": []})
    block_ld = collections.Counter()
    entity_total = collections.Counter()          # page_type|scope|etype -> entities
    entity_total_pt = collections.Counter()
    errors = collections.Counter()
    read_err = []
    n_ok = 0
    block_defs = 0
    appid_table_count = collections.Counter()
    files_seen = collections.Counter()

    for fp in files:
        d = json.load(open(fp, encoding="utf-8"))
        if d.get("error"):
            read_err.append({"project_id": d.get("project_id"), "file_id": d.get("file_id"), "error": d["error"]})
            continue
        n_ok += 1
        pid, fid = d["project_id"], d["file_id"]
        meta = idx_by_key[(pid, fid)]
        pt = meta["page_type"]
        fam = meta["family"]
        pk = (pid, fid)
        files_seen[pt] += 1
        block_defs += d.get("block_count", 0)
        for a in d.get("appid_table", []):
            appid_table_count[a] += 1
        for k, n in d["entity_total"].items():
            entity_total[k] += n
            entity_total_pt[f"{pt}|{k}"] += n
        apps_in_file = set()
        for k, n in d["ent_app"].items():
            ent_app[k] += n
            app = k.split("|", 2)[2]
            apps_in_file.add(app)
            app_pages[app].add(pk)
        for app in apps_in_file:
            app_pt[app][pt] += 1
            app_fam[app][fam] += 1
        for k, n in d["sig"].items():
            scope, etype, app, sig = k.split("|", 3)
            app_sig[app][f"{scope}|{etype}|{sig}"] += n
        for app, exs in d["examples"].items():
            for ex in exs:
                if len(app_ex[app]) < 400:
                    app_ex[app].append({"pid": pid, "fid": fid, "pt": pt, "subtype": meta.get("page_subtype"),
                                        "filename": meta["filename"], **ex})
        for k, vals in d["str_vals"].items():
            for v, n in vals.items():
                str_vals[k][v] += n
        for k, n in d["hlink"].items():
            hlink[k] += n
        for k, n in d["layer_all"].items():
            scope, etype, layer = k.split("|", 2)
            layer_all[f"{pt}|{scope}|{etype}|{layer}"] += n
        for k, n in d["color_all"].items():
            scope, etype, color, lt = k.split("|", 3)
            color_all[f"{pt}|{scope}|{etype}|{color}|{lt}"] += n
        for k, n in d["ld_layer"].items():
            ld_layer[k] += n
        for k, n in d["attdef_tags"].items():
            attdef_tags[k] += n
        for k, vals in d["attdef_default"].items():
            for v, n in vals.items():
                attdef_default[k][v] += n
        for k, n in d["attrib_tags"].items():
            attrib_tags[k] += n
        for k, vals in d["attrib_vals"].items():
            for v, n in vals.items():
                attrib_vals[k][v] += n
        for k, n in d["ext_keys"].items():
            ext_keys[f"{pt}|{k}"] += n
        for k, n in d.get("xrec_kv", {}).items():
            xrec_kv[k] += n
            xrec_kv_pages[k].add(pk)
        for k, exs in d.get("xrec_kv_ex", {}).items():
            for ex in exs:
                if len(xrec_kv_ex[k]) < 6:
                    xrec_kv_ex[k].append({"pid": pid, "fid": fid, "pt": pt, "filename": meta["filename"], **ex})
        for k, n in d["xrec_sigs"].items():
            xrec_sigs[k] += n
        for k, n in d["dict_keys"].items():
            dict_keys[k] += n
        for k, n in d["obj_types"].items():
            obj_types[k] += n
            obj_types_pt[pt][k] += 1
        for k, n in d["group_stats"].items():
            group_stats[k] += n
        if d["group_stats"].get("groups"):
            group_pages.add(pk)
        for k, n in d["group_member_types"].items():
            group_member_types[k] += n
        for k, v in d["root_dicts"].items():
            rd = root_dicts[k]
            rd["files"].add(pk)
            for e in v["entries"]:
                nm = re.sub(r"[0-9A-Fa-f]{2,}", "#", e["name"])  # 句柄样式的名称归一化
                rd["names"][nm] += 1
                rd["types"][e["type"]] += 1
                rd["tag_sigs"][f"{e['type']}|" + ",".join(str(c) for c, _ in e["tags"][:12])] += 1
                if len(rd["examples"]) < 12:
                    rd["examples"].append({"pid": pid, "fid": fid, "pt": pt, "name": e["name"], "type": e["type"],
                                           "tags": e["tags"][:8]})
        for k, n in d["block_names_ld"].items():
            block_ld[k] += n
        for k, n in d["errors"].items():
            errors[k] += n

    # 代码引用核对
    src = _load_src()
    keys = set(ent_app.keys())
    keys = {k.split("|", 2)[2] for k in keys} | set(attdef_tags) | set(attrib_tags)
    code_refs = {}
    for app in sorted(keys):
        hits = [p for p, t in src.items() if re.search(r"(?<![A-Za-z0-9_])" + re.escape(app) + r"(?![A-Za-z0-9_])", t)]
        note = _pattern_ref(app)
        code_refs[app] = {"literal_hits": hits, "pattern_note": note}

    out = {
        "n_files_ok": n_ok,
        "read_errors": read_err,
        "total_pages_by_type": dict(total_pages),
        "total_pages_by_family": dict(total_fam),
        "files_by_type_scanned": dict(files_seen),
        "block_definitions": block_defs,
        "entity_total_pt": dict(entity_total_pt),
        "entity_total": dict(entity_total),
        "errors": dict(errors),
        "appids": {},
        "str_vals": {k: dict(v.most_common(40)) for k, v in str_vals.items()},
        "hlink": dict(hlink),
        "layer_all": dict(layer_all),
        "color_all": dict(color_all),
        "ld_layer": dict(ld_layer),
        "attdef_tags": dict(attdef_tags),
        "attdef_default": {k: dict(v.most_common(10)) for k, v in attdef_default.items()},
        "attrib_tags": dict(attrib_tags),
        "attrib_vals": {k: dict(v.most_common(10)) for k, v in attrib_vals.items()},
        "ext_keys": dict(ext_keys),
        "xrec_kv": {k: {"n": v, "pages": len(xrec_kv_pages[k])} for k, v in xrec_kv.items()},
        "xrec_kv_ex": dict(xrec_kv_ex),
        "xrec_sigs_top": xrec_sigs.most_common(200),
        "dict_keys": dict(dict_keys),
        "obj_types": dict(obj_types),
        "obj_types_pt": {k: dict(v) for k, v in obj_types_pt.items()},
        "group_stats": dict(group_stats),
        "group_member_types": dict(group_member_types),
        "group_pages": len(group_pages),
        "root_dicts": {k: {"files": len(v["files"]), "names_top": v["names"].most_common(40),
                           "types": dict(v["types"]), "tag_sigs_top": v["tag_sigs"].most_common(30),
                           "examples": v["examples"]} for k, v in root_dicts.items()},
        "block_names_ld_top": block_ld.most_common(60),
        "code_refs": code_refs,
    }
    ent_by_app = collections.defaultdict(collections.Counter)
    for k, n in ent_app.items():
        s_, et_, a_ = k.split("|", 2)
        ent_by_app[a_][f"{s_}|{et_}"] += n
    for app in sorted(keys):
        sig_rows = app_sig.get(app, collections.Counter())
        exs = app_ex.get(app, [])
        # 样例：优先取不同页型
        picked, seen_pt = [], set()
        for ex in exs:
            if ex["pt"] not in seen_pt or len(picked) < 1:
                picked.append(ex)
                seen_pt.add(ex["pt"])
            if len(picked) >= 3:
                break
        if len(picked) < 3:
            for ex in exs:
                if ex not in picked:
                    picked.append(ex)
                if len(picked) >= 3:
                    break
        ent_by_scope_etype = ent_by_app.get(app, collections.Counter())
        out["appids"][app] = {
            "entities": sum(ent_by_scope_etype.values()),
            "by_scope_etype": dict(ent_by_scope_etype.most_common()),
            "files": len(app_pages.get(app, ())),
            "pages_by_type": dict(app_pt.get(app, {})),
            "pages_by_family": dict(app_fam.get(app, {})),
            "sigs_top": sig_rows.most_common(8),
            "examples": picked,
            "in_tables_files": appid_table_count.get(app, 0),
            "code_refs": code_refs.get(app, {}),
        }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("files ok", n_ok, "errors", len(read_err), "appids", len(out["appids"]))


if __name__ == "__main__":
    main()
