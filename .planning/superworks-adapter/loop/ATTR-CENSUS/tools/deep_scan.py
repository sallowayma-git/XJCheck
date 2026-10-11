"""逐文件深扫 DXF 的 XDATA / 块定义 / ATTRIB / 扩展字典 / OBJECTS 对象。

只读：不修改任何 DXF、清单或仓库源码。每个工作进程一次只读一份 DXF，
每份 DXF 输出一个小 JSON 摘要到工作目录（默认为系统临时目录下的 attr_census）。

用法:
  python deep_scan.py --index <page_index.json> --work <dir> [--workers 8] [--limit N]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import traceback
from multiprocessing import Pool

import ezdxf

LIST_CAP = 40        # 单实体 XDATA 签名最长记录的 group code 数
VAL_CAP = 30         # 每个 (app, code) 记录的字符串取值 distinct 上限
EX_PER_APP = 2       # 每个 appid 每文件保留的样例数
STR_CAP = 60         # 样例字符串截断长度


def _s(v, cap=STR_CAP):
    if isinstance(v, float):
        v = round(v, 4)
    s = str(v)
    return s if len(s) <= cap else s[:cap] + "..."


def _sig(codes):
    out = ",".join(str(c) for c in codes[:LIST_CAP])
    if len(codes) > LIST_CAP:
        out += f",+{len(codes) - LIST_CAP}"
    return out


class Acc:
    """单文件累加器。所有键都用 '|' 连接的字符串，便于 JSON 序列化。"""

    def __init__(self):
        self.ent_app = collections.Counter()      # scope|etype|app -> 实体数
        self.sig = collections.Counter()          # scope|etype|app|codesig -> 实体数
        self.examples = collections.defaultdict(list)   # app -> [样例]
        self.str_vals = collections.defaultdict(collections.Counter)  # app|code -> 取值计数
        self.hlink = collections.Counter()        # app|target_type|resolved -> 计数 (code 1005)
        self.layer_all = collections.Counter()    # etype|layer
        self.color_all = collections.Counter()    # etype|color|linetype
        self.ld_layer = collections.Counter()     # etype|app|layer
        self.attdef_tags = collections.Counter()  # tag -> 计数
        self.attdef_default = collections.defaultdict(collections.Counter)
        self.attrib_tags = collections.Counter()
        self.attrib_vals = collections.defaultdict(collections.Counter)
        self.ext_keys = collections.Counter()     # etype|key|type
        self.ext_sigs = collections.Counter()     # XRECORD 签名
        self.ext_examples = []
        self.obj_types = collections.Counter()
        self.dict_keys = collections.Counter()    # DICTIONARY 名称 -> 计数
        self.xrec_sigs = collections.Counter()
        self.xrec_examples = []
        self.xrec_kv = collections.Counter()          # 所属字典|键名 -> 计数 (XRECORD 代码1 键值对)
        self.xrec_kv_ex = collections.defaultdict(list)
        self.group_stats = collections.Counter()
        self.group_member_types = collections.Counter()
        self.group_examples = []
        self.root_dicts = {}                      # 自定义根字典 -> 条目摘要
        self.errors = collections.Counter()
        self.block_names_ld = collections.Counter()
        self.block_count = 0
        self.entity_total = collections.Counter()  # scope|etype -> 实体数


def _xdata_items(e):
    try:
        if e.xdata is None:
            return []
        return [(app, [(t.code, t.value) for t in tags]) for app, tags in e.xdata.data.items()]
    except Exception:
        return []


def _resolve(doc, h):
    try:
        ent = doc.entitydb.get(h)
    except Exception:
        ent = None
    return ent


def _scan_entity(doc, acc, scope, e):
    etype = e.dxftype()
    acc.entity_total[f"{scope}|{etype}"] += 1
    try:
        layer = e.dxf.layer
    except Exception:
        layer = ""
    acc.layer_all[f"{scope}|{etype}|{layer}"] += 1
    if etype in ("LINE", "LWPOLYLINE", "ARC", "CIRCLE", "POLYLINE"):
        color = getattr(e.dxf, "color", None)
        lt = getattr(e.dxf, "linetype", "")
        acc.color_all[f"{scope}|{etype}|{color}|{lt}"] += 1

    items = _xdata_items(e)
    for app, tags in items:
        vals = [(c, v) for c, v in tags if c != 1001]
        codes = [c for c, _ in vals]
        acc.ent_app[f"{scope}|{etype}|{app}"] += 1
        acc.sig[f"{scope}|{etype}|{app}|{_sig(codes)}"] += 1
        acc.ld_layer[f"{etype}|{app}|{layer}"] += 1
        if len(acc.examples[app]) < EX_PER_APP * 4:
            acc.examples[app].append({
                "scope": scope, "etype": etype, "handle": e.dxf.handle, "layer": layer,
                "vals": [[c, _s(v, 80)] for c, v in vals[:6]],
            })
        for c, v in vals:
            if c in (1000, 1004):
                key = f"{app}|{c}"
                if key not in acc.str_vals or len(acc.str_vals[key]) < VAL_CAP or _s(v) in acc.str_vals[key]:
                    acc.str_vals[key][_s(v, 40)] += 1
            elif c == 1005:
                tgt = _resolve(doc, str(v))
                if tgt is None:
                    acc.hlink[f"{app}|MISSING|no"] += 1
                else:
                    acc.hlink[f"{app}|{tgt.dxftype()}|yes"] += 1
    # 扩展字典
    try:
        if e.has_extension_dict:
            ext = e.get_extension_dict()
            d = ext.dictionary
            for k, v in d.items():
                acc.ext_keys[f"{scope}|{etype}|{k}|{v.dxftype()}"] += 1
                if v.dxftype() == "XRECORD":
                    _record_xrec(acc, v, f"ext:{etype}:{k}", e.dxf.handle)
    except Exception:
        acc.errors["ext_dict"] += 1


def _record_xrec(acc, obj, label, owner):
    try:
        tags = [(t.code, t.value) for t in obj.tags]
    except Exception:
        acc.errors["xrec_tags"] += 1
        return
    codes = [c for c, _ in tags]
    acc.xrec_sigs[f"{label}|{_sig(codes)}"] += 1
    if sum(1 for x in acc.xrec_examples if x["label"] == label) < 2:
        acc.xrec_examples.append({"label": label, "owner": owner, "tags": [[c, _s(v, 60)] for c, v in tags[:12]]})
    # 代码 1 的键值对解析：键名 -> 计数与样例（终端绑定用的 LINENO / CONNECTLINEHANDLE / PART2_n 即此类）
    strings = [str(v) for c, v in tags if c == 1]
    if strings and len(strings) % 2 == 0:
        for i in range(0, len(strings), 2):
            k = strings[i].strip()[:60]
            if not k:
                continue
            acc.xrec_kv[f"{label}|{k}"] += 1
            bucket = acc.xrec_kv_ex[f"{label}|{k}"]
            if len(bucket) < 2:
                bucket.append({"owner": owner, "value": _s(strings[i + 1], 80)})


def scan_file(row, work_dir):
    out = {k: row.get(k) for k in ("project_id", "file_id", "filename", "dxf_path",
                                   "page_type", "page_subtype", "sheet_category", "audit_role", "input_root")}
    acc = Acc()
    try:
        doc = ezdxf.readfile(row["dxf_path"])
    except Exception as ex:
        out["error"] = f"read: {ex!s}"[:300]
        return out
    out["appid_table"] = sorted(a.dxf.name for a in doc.appids)
    msp = doc.modelspace()
    for e in msp:
        _scan_entity(doc, acc, "MS", e)
        if e.dxftype() == "INSERT":
            try:
                for a in e.attribs:
                    acc.attrib_tags[a.dxf.tag] += 1
                    if len(acc.attrib_vals[a.dxf.tag]) < 3 or _s(a.dxf.text) in acc.attrib_vals[a.dxf.tag]:
                        acc.attrib_vals[a.dxf.tag][_s(a.dxf.text, 40)] += 1
                    _scan_entity(doc, acc, "ATTRIB", a)
            except Exception:
                acc.errors["attrib"] += 1
    for blk in doc.blocks:
        if blk.name in ("*Model_Space", "*Paper_Space") or blk.name.startswith("*Paper_Space"):
            continue
        acc.block_count += 1
        ld_in_block = False
        for e in blk:
            if e.dxftype() == "ATTDEF":
                acc.attdef_tags[e.dxf.tag] += 1
                acc.attdef_default[e.dxf.tag][_s(getattr(e.dxf, "default", ""), 30)] += 1
                _scan_entity(doc, acc, "ATTDEF", e)
                continue
            if e.xdata is not None and _xdata_items(e):
                ld_in_block = True
            _scan_entity(doc, acc, "BLK", e)
        if ld_in_block:
            acc.block_names_ld[blk.name[:40]] += 1

    # OBJECTS：字典、XRECORD、GROUP。先建立 XRECORD 句柄 -> (所属字典句柄, 键名) 映射
    parent_of = {}
    for o in doc.objects:
        if o.dxftype() == "DICTIONARY":
            try:
                for k, v in o.items():
                    if v is not None and v.dxftype() == "XRECORD":
                        parent_of[v.dxf.handle] = f"{o.dxf.handle}:{k[:40]}"
            except Exception:
                acc.errors["dict_items"] += 1
    for o in doc.objects:
        t = o.dxftype()
        acc.obj_types[t] += 1
        if t == "DICTIONARY":
            try:
                for k in o.keys():
                    acc.dict_keys[k[:60]] += 1
            except Exception:
                acc.errors["dict_keys"] += 1
        elif t == "XRECORD":
            parent = parent_of.get(o.dxf.handle, "orphan")
            _record_xrec(acc, o, "obj:XRECORD:" + parent.split(":", 1)[-1], o.dxf.handle)
        elif t == "GROUP":
            try:
                tags = [(tg.code, tg.value) for tg in o.tags]
                members = [v for c, v in tags if c == 340]
                acc.group_stats["groups"] += 1
                acc.group_stats["members_total"] += len(members)
                if members:
                    acc.group_stats["groups_nonempty"] += 1
                for h in members:
                    ent = _resolve(doc, h)
                    acc.group_member_types[ent.dxftype() if ent is not None else "MISSING"] += 1
                if len(acc.group_examples) < 3:
                    acc.group_examples.append({"name": [v for c, v in tags if c == 300][:1],
                                               "n": len(members),
                                               "member_types": [(_resolve(doc, h).dxftype() if _resolve(doc, h) else "MISSING") for h in members[:8]]})
            except Exception:
                acc.errors["group"] += 1

    # 自定义根字典
    for key in ("LD_DWG_DICITIONARY", "LD_SYMB2LOGGEN_DICTIONARY", "ACAD_GROUP", "AcDbVariableDictionary"):
        try:
            d = doc.rootdict.get(key)
            if d is None:
                continue
            entries = []
            for name, obj in list(d.items())[:200]:
                try:
                    tags = [(t.code, t.value) for t in obj.tags][:12]
                except Exception:
                    tags = []
                entries.append({"name": name[:80], "type": obj.dxftype(),
                                "tags": [[c, _s(v, 50)] for c, v in tags]})
            acc.root_dicts[key] = {"n": len(d), "entries": entries}
        except Exception:
            acc.errors["root_dict"] += 1

    out.update({
        "error": None,
        "block_count": acc.block_count,
        "entity_total": dict(acc.entity_total),
        "ent_app": dict(acc.ent_app),
        "sig": dict(acc.sig),
        "examples": dict(acc.examples),
        "str_vals": {k: dict(v) for k, v in acc.str_vals.items()},
        "hlink": dict(acc.hlink),
        "layer_all": dict(acc.layer_all),
        "color_all": dict(acc.color_all),
        "ld_layer": dict(acc.ld_layer),
        "attdef_tags": dict(acc.attdef_tags),
        "attdef_default": {k: dict(v) for k, v in acc.attdef_default.items()},
        "attrib_tags": dict(acc.attrib_tags),
        "attrib_vals": {k: dict(v) for k, v in acc.attrib_vals.items()},
        "ext_keys": dict(acc.ext_keys),
        "ext_sigs": dict(acc.ext_sigs),
        "obj_types": dict(acc.obj_types),
        "dict_keys": dict(acc.dict_keys),
        "xrec_sigs": dict(acc.xrec_sigs),
        "xrec_examples": acc.xrec_examples,
        "xrec_kv": dict(acc.xrec_kv),
        "xrec_kv_ex": {k: v for k, v in acc.xrec_kv_ex.items()},
        "group_stats": dict(acc.group_stats),
        "group_member_types": dict(acc.group_member_types),
        "group_examples": acc.group_examples,
        "root_dicts": acc.root_dicts,
        "errors": dict(acc.errors),
        "block_names_ld": dict(acc.block_names_ld),
    })
    return out


def _worker(args):
    row, work_dir = args
    name = f"{row['project_id']}_{row['file_id']}.json"
    path = os.path.join(work_dir, name)
    if os.path.exists(path):
        return name, "cached"
    try:
        res = scan_file(row, work_dir)
    except Exception:
        res = {"project_id": row.get("project_id"), "file_id": row.get("file_id"),
               "error": "crash: " + traceback.format_exc()[-400:]}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    return name, "error" if res.get("error") else "ok"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--page-types", default="")
    ap.add_argument("--sample-per-type", type=int, default=0,
                    help="每个页型最多取多少页（按 project 轮转，保证家族覆盖）；0 表示全量")
    args = ap.parse_args(argv)
    os.makedirs(args.work, exist_ok=True)
    rows = json.load(open(args.index, encoding="utf-8"))
    if args.page_types:
        wanted = set(args.page_types.split(","))
        rows = [r for r in rows if r["page_type"] in wanted]
    if args.sample_per_type:
        picked = []
        by_type = collections.defaultdict(list)
        for r in rows:
            by_type[r["page_type"]].append(r)
        for pt, rs in by_type.items():
            # 按项目轮转，覆盖各家族
            byproj = collections.defaultdict(list)
            for r in rs:
                byproj[r["project_id"]].append(r)
            queues = [list(v) for _, v in sorted(byproj.items())]
            got = []
            while queues and len(got) < args.sample_per_type:
                for q in queues:
                    if q and len(got) < args.sample_per_type:
                        got.append(q.pop(0))
                queues = [q for q in queues if q]
            picked.extend(got)
        rows = picked
    if args.limit:
        rows = rows[: args.limit]
    jobs = [(r, args.work) for r in rows]
    stat = collections.Counter()
    with Pool(args.workers) as pool:
        for i, (name, st) in enumerate(pool.imap_unordered(_worker, jobs, chunksize=1)):
            stat[st] += 1
            if (i + 1) % 100 == 0:
                print(f"[{i + 1}/{len(jobs)}] {dict(stat)}", flush=True)
    print("done", dict(stat), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
