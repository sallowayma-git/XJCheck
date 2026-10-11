"""Build details.json: layer tables (from aggregate.json) + verification checks + top-8 bucket narrative.

Read-only over .tmp/superworks_round12_full and the frozen DXF cache. Usage: build_details.py <scratch_dir>
"""
import glob, json, re, sys, collections, random
from pathlib import Path
import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
OUT = ROOT / ".planning/superworks-adapter/loop/COV-GAP"
RUN = ROOT / ".tmp/superworks_round12_full"
SCR = Path(sys.argv[1])
R = json.loads((SCR / "aggregate.json").read_text(encoding="utf-8"))
run = json.loads((RUN / "run.json").read_text(encoding="utf-8"))
manifest = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
checks = {}

# ---- 1. DXF XDATA: strip _2 / FENGE slots (frozen DXF cache)
pat = {s: re.compile(r"\n1001\n" + s + r"\n(?:.*\n){0,2}?\s*1005\n(\S+)\n") for s in
       ["LDDZ_LEFTTEXT_HANDLE", "LDDZ_RIGHTTEXT_HANDLE", "LDDZ_LEFTTEXT_HANDLE_2", "LDDZ_RIGHTTEXT_HANDLE_2", "LDDZ_LEFT_FENGEHANDLE", "LDDZ_RIGHT_FENGEHANDLE"]}
tot, nz, nfiles = collections.Counter(), collections.Counter(), 0
for p in manifest["projects"][:12]:
    for f in p["files"]:
        t = Path(f["dxf_path"]).read_text(encoding="utf-8", errors="ignore")
        nfiles += 1
        for s, rx in pat.items():
            vals = rx.findall(t)
            tot[s] += len(vals)
            nz[s] += sum(1 for v in vals if v != "0")
checks["dxf_xdata_strip_slots"] = {"dxf_files_checked": nfiles, "projects": 12, "usages": dict(tot), "nonzero": dict(nz),
                                   "note": "_2 and FENGE slots are registered (APPID) but never populated with a handle in these DXFs"}

# ---- 2. destination texts: text entity properties (corpus-level)
heights, layers, etypes = collections.Counter(), collections.Counter(), collections.Counter()
for pid, d in [(p["project_id"], Path(p["project_dir"]) / "findings") for p in run["projects"]]:
    s = pd.read_parquet(d / "sw_strip_rows.parquet", columns=["potentials"])
    ids = set()
    for pots in s.potentials:
        for x in json.loads(pots):
            ids.add(x.get("text_id"))
    tx = pd.read_parquet(d / "texts.parquet", columns=["text_id", "height", "layer", "entity_type"])
    tx = tx[tx.text_id.isin(ids)]
    for r in tx.itertuples():
        heights[round(float(r.height), 3)] += 1
        layers[str(r.layer)] += 1
        etypes[str(r.entity_type)] += 1
checks["destination_text_entities"] = {"count": sum(heights.values()), "height": dict(heights), "layer": dict(layers), "entity_type": dict(etypes),
                                       "note": "TEXT entities on layer 0; small (height 1.0 or 3.0); visible but tiny at page scale"}

# ---- 3. identity equality between cross-page target and same-row strip connection
pots = pd.read_pickle(SCR / "pots_fam.pkl")
strip = pd.read_pickle(SCR / "strip.pkl")
conn = strip.groupby(["project", "record_id"]).value.apply(lambda s: {str(v).strip().casefold() for v in s}).to_dict()
eq = collections.Counter()
for r in pots.itertuples():
    if r.reason[:2] in ("X1", "X2"):
        k = "X1" if r.reason[:2] == "X1" else "X2"
        eq[k + "_n"] += 1
        ti = str(r.t_ident).strip().casefold()
        if ti and ti in conn.get((r.project, r.record_id), set()):
            eq[k + "_identity_equal"] += 1
checks["cross_page_identity_equality"] = {
    "X2_targets_unconsumed": eq["X2_n"], "X2_identity_equal_to_row_connection": eq["X2_identity_equal"],
    "X2_share": round(eq["X2_identity_equal"] / eq["X2_n"], 4),
    "X1_targets_consumed": eq["X1_n"], "X1_identity_equal_to_row_connection": eq["X1_identity_equal"],
    "X1_share": round(eq["X1_identity_equal"] / eq["X1_n"], 4)}

# ---- 4. uplift bound for strict terminal coverage if X2 targets were consumed
u = pd.read_pickle(SCR / "union.pkl")
b_unc = set(zip(u[u.layer.str.startswith("b_")].project, u[u.layer.str.startswith("b_")].obj))
x2 = pots[pots.reason.str.startswith("X2")]
x2_b = sum((p, t) in b_unc for p, t in zip(x2.project, x2.t_rid))
checks["strict_uplift_bound_if_X2_linked"] = {
    "X2_targets_that_are_uncovered_strict_terminals": int(x2_b), "eligible": 82680, "covered_now": 47380,
    "rate_now": round(47380 / 82680, 4), "rate_upper_bound": round((47380 + x2_b) / 82680, 4),
    "note": "upper bound: assumes every X2 target gets a correct cross-page pair"}

# ---- 5. P4 value-mismatch subtypes (pair side value vs SW endpoint value)
p4 = u[u.bucket.str.startswith("P4")]
kinds = collections.Counter()
for pid, sub in p4.groupby("project"):
    d = Path(run["projects"][[p["project_id"] for p in run["projects"]].index(pid)]["project_dir"]) / "findings"
    pr = pd.read_parquet(d / "pairs.parquet", columns=["status", "pair_kind", "left_value", "right_value", "evidence"])
    idx = collections.defaultdict(list)
    for r in pr.itertuples():
        ev = json.loads(r.evidence) if isinstance(r.evidence, str) else (r.evidence or {})
        sw = ev.get("superworks") or {}
        for side in ("left", "right"):
            e = sw.get(side) or {}
            for pid_ in e.get("port_ids") or []:
                idx[pid_].append((side, e.get("value"), r.left_value, r.right_value, r.status, r.pair_kind))
    for r in sub.itertuples():
        nd = [x for x in idx.get(r.obj, []) if x[4] != "discard"]
        if not nd:
            kinds["no_nondiscard_ref"] += 1
            continue
        side, swv, lv, rv, st, kd = nd[0]
        pv = str(lv if side == "left" else rv) if (lv if side == "left" else rv) == (lv if side == "left" else rv) else ""
        swv = "" if swv is None else str(swv)
        if not swv:
            k = "sw_value_missing"
        elif not pv or pv == "None":
            k = "pair_side_empty"
        else:
            a, b = swv.casefold().strip(), pv.casefold().strip()
            if a.endswith(b) and a != b:
                k = "pair_value_is_suffix_of_SW_value(device prefix dropped)"
            else:
                k = "different_identity"
        kinds[f"{k} | {st} | {kd}"] += 1
checks["P4_subtypes"] = dict(kinds.most_common())

# ---- 6. D1d: text claims 'Covered by component_mapping' but no non-discard mapping references it (corpus)
d1d = collections.Counter()
for p in run["projects"]:
    d = Path(p["project_dir"]) / "findings"
    ta = pd.read_parquet(d / "text_assignments.parquet", columns=["sheet_id", "page_type", "text_id", "explain_reason", "is_numeric_like", "resolution_status"])
    pr = pd.read_parquet(d / "pairs.parquet", columns=["sheet_id", "status", "pair_kind", "evidence", "left_text_id", "right_text_id"])
    cm = pr[pr.pair_kind.isin(["component_mapping", "wire_component_mapping"]) & (pr.status != "discard")]
    ref = collections.defaultdict(set)
    for r in cm.itertuples():
        for t in re.findall(r"T\d{3,6}", str(r.evidence)):
            ref[r.sheet_id].add(t)
        for t in (r.left_text_id, r.right_text_id):
            if isinstance(t, str):
                ref[r.sheet_id].add(t)
    sub = ta[(ta.page_type == "元件接线图") & ta.is_numeric_like.astype(bool) & (ta.resolution_status == "discarded") &
             ta.explain_reason.astype(str).str.startswith("Covered by component_mapping")]
    for r in sub.itertuples():
        d1d["n"] += 1
        d1d["referenced_by_nondiscard_component_mapping"] += int(r.text_id in ref[r.sheet_id])
checks["D1d_bookkeeping"] = dict(d1d)

# ---- 7. layer c: wire-candidate score does not separate resolved from unresolved (20 projects)
g_resolved = collections.Counter()
for p in run["projects"][:20]:
    d = Path(p["project_dir"]) / "findings"
    lg = pd.read_parquet(d / "line_groups.parquet", columns=["line_group_id", "wire_candidate_score", "sheet_id"])
    pg = pd.read_parquet(d / "pages.parquet", columns=["sheet_id", "page_type"])
    sch = set(pg.sheet_id[pg.page_type == "二次原理图"])
    lg = lg[lg.sheet_id.isin(sch)]
    sch_g = pd.read_pickle(SCR / "groups.pkl")
    sch_g = sch_g[sch_g.project == p["project_id"]].set_index("group")
    j = lg.set_index("line_group_id").join(sch_g[["n_resolved"]], how="inner")
    hi = j.wire_candidate_score >= 0.7
    g_resolved["hi_n"] += int(hi.sum())
    g_resolved["hi_resolved"] += int((hi & (j.n_resolved > 0)).sum())
    g_resolved["lo_n"] += int((~hi).sum())
    g_resolved["lo_resolved"] += int(((~hi) & (j.n_resolved > 0)).sum())
checks["layer_c_score_test_20_projects"] = {
    "score>=0.7_resolved_share": round(g_resolved["hi_resolved"] / max(1, g_resolved["hi_n"]), 4),
    "score<0.7_resolved_share": round(g_resolved["lo_resolved"] / max(1, g_resolved["lo_n"]), 4),
    "groups": g_resolved["hi_n"] + g_resolved["lo_n"],
    "conclusion": "wire_candidate_score does not filter out non-wire groups"}

# ---- 8. bucket narrative (visual reading of the 3 samples per bucket is in README)
NARR = {
 "O3": dict(name="对端为内部元件端口（无身份）", cause="导线另一端落在元件图形内的引脚（SW internal-component 端口，无 endpoint_identity），其旁只有裸引脚号或无文字，无法组成两端身份的配对。",
            fix="为元件内部引脚生成“元件标号 + 引脚号”身份（元件标号取自元件块旁的标签文字，引脚号取自 SW 端口 port_number 或块内数字），作为 SW 端子↔元件引脚的 SW 证据配对；仅当元件块内引脚号唯一、标号唯一时启用。",
            gain="最多 17333（端子→元件引脚）；与 O7、D1a 共用同一身份生成；严格口径分母内 b 层可提升约 21%（若全部成对，上界）。",
            risk="高：元件标号与引脚号重号、同名元件多实例；需要同页唯一性与互为对端校验，否则伪连接。"),
 "X2": dict(name="跨页去向：目标端口未消费（本链路未建立）", cause="端子排连接的去向文字（XDATA potentials，文字本身为 TEXT 实体，字高1/3，内容“未定义<句柄>:<端口>_<页>”）指向另一页的 SW 端口；该端口有身份，但没有任何非 discard 的配对引用端子排侧，跨页链路从未被建立。约 48% 的目标身份与同行端子排连接身份完全相同。",
            fix="利用 cross_page_refs（句柄+端口号）在同项目内定位目标端口；当目标端口身份与同行端子排连接身份（或端子排行身份所对应的内部连接）相等且目标在该项目内唯一时，生成跨页 SW 证据配对（status 由既有 pass/review 规则决定）。",
            gain="严格端口口径：11706 个 b 层未覆盖端子为本桶目标，上界覆盖率 57.3%→71.5%。",
            risk="中：同身份多页重复（competing_physical_port_identities 已有先例）；X1 同类目标若已被另一配对消费会产生多对一，必须交给已有 many-to-one 规则而非直接放行。"),
 "X1": dict(name="跨页去向：目标端口已消费（本链路未建立）", cause="目标端口已由其所在页的导线配对消费，但端子排侧的连接身份与目标身份命名不同（如 2-26n711 对 2-26TD111），仅靠身份无法对齐，缺少把两者连接起来的依据。",
            fix="只在存在独立证据（如 XDATA 句柄、与目标端口同一设备句柄的 cross_page_refs 唯一对应）时建立链接，并把已消费端口视为‘二次证据’，不改变既有配对。",
            gain="不直接提升严格端口覆盖（目标已消费）；提升的是端子排去向文字覆盖与跨页一致性；身份相等的仅约 1612 个。",
            risk="高：命名体系不同，身份相等规则会误连；建议先作为仅报告的候选，不进入覆盖率。"),
 "O10": dict(name="对端无实体无文字", cause="导线另一端既无 SW 端口、也无候选文字：多为元件图形内的未标注引脚（引脚号被当作块内号拒绝）或框线/表格边线的接入点，两者都不在任何配对源里。",
            fix="与 O3/D1a 合并处理（元件引脚身份）；框线/表格线类端点在导线组层面过滤（需要先给 line_group 分类为非导线）。",
            gain="最多 8357，但多数需要元件引脚身份才能转化。",
            risk="中：把框线误当导线会制造伪连接；需先做导线/框线分类。"),
 "D1a": dict(name="元件内部引脚号被拒（block_internal_pin_number）", cause="元件接线图上的数字文字位于元件圆形引脚符号内，被规则判为块内引脚号而拒绝；目视样例中无外部导线接入，多数不是外部端子，应从应覆盖分母中排除（或先确认是否有外部导线）。",
            fix="更像分母口径问题：在元件接线图的覆盖分母中把块内引脚号单列，不计入外部端子覆盖；若某引脚确有导线，再交给元件引脚身份规则。",
            gain="口径修正而非连接增量；可把层 d 覆盖率的分母缩小 4068。",
            risk="低（口径改动需要在报告中说明）。"),
 "X3": dict(name="跨页去向：目标设备无 SW 符号", cause="目标设备句柄在本项目 sw_symbols 中完全不存在（2442 中 0 个命中），SW 通道没有目标端口，只有文字侧可能给出设备名（如 A'-2、C663）。",
            fix="SW 侧无法补齐；需要文字侧设备名与端子排去向的对齐（独立的文字配对），不属于 SW 扩展。",
            gain="无法靠 SW 修复。",
            risk="低（只报告）。"),
 "P4": dict(name="SW 引用存在但身份值不一致", cause="主要形态：review 配对的侧值去掉了设备侧前缀（如配对值 717，SW 身份 1n717）；其次为 SW 端无 value 的 semantic_mapping 挂接。全部为 review 状态。",
            fix="在 SW 身份比较中加入‘设备前缀可剥离’的规范化（仅当前缀为同页内唯一的设备侧前缀，且后缀唯一对应该端口时），使该端口获得 SW 证据消费。",
            gain="约 1600 个严格端子（b 层）可获得消费；风险最低、实现最小。",
            risk="低-中：前缀规则必须限定在同页同设备；需要回归检查 many-to-one 与 competing identity。"),
 "O7": dict(name="对端文字已接受但未成对", cause="另一端是候选已接受的裸数字（继电器/触点的引脚号，如 7、13、3），缺少元件名前缀，无法形成完整身份，因此不配对；同一桶内 1601 个属于 discard-only 组。",
            fix="与 O3/O10 共用元件引脚身份：把已接受的裸引脚号与其旁边的元件标号（如 ZJ1）组合为完整身份后参与配对。",
            gain="最多 1628（与 O3 相关）。",
            risk="中：裸数字多义，必须有元件标号唯一性。"),
}
top8 = []
for rank, b in enumerate(R["uncovered_union"]["buckets"][:8], start=1):
    key = b["bucket"].split("_", 1)[0]
    if b["bucket"].startswith("O3"): key = "O3"
    elif b["bucket"].startswith("X2"): key = "X2"
    elif b["bucket"].startswith("X1"): key = "X1"
    elif b["bucket"].startswith("O10"): key = "O10"
    elif b["bucket"].startswith("D1a"): key = "D1a"
    elif b["bucket"].startswith("X3"): key = "X3"
    elif b["bucket"].startswith("P4"): key = "P4"
    elif b["bucket"].startswith("O7"): key = "O7"
    narr = NARR[key]
    samples = R["samples"].get(b["bucket"], [])
    top8.append({"rank": rank, "bucket": b["bucket"], "count": b["count"], "share_of_all_uncovered": b["share_of_all_uncovered"],
                 "layers": b["layer"], "projects": b["projects"], "families": b["families"], "tags": b["tags"],
                 "cause": narr["cause"], "fix": narr["fix"], "gain": narr["gain"], "risk": narr["risk"],
                 "samples": [{"project": s["project"], "sheet": s["sheet"], "obj": s["obj"], "ident": s.get("ident"),
                              "group": s.get("group"), "oend": s.get("oend"), "png_single": None} for s in samples]})
index = json.loads((OUT / "png/index.json").read_text(encoding="utf-8"))
for t in top8:
    names = [x["png"] for x in index if x["bucket"] == t["bucket"]]
    for s, n in zip(t["samples"], names):
        s["png_single"] = f"png/{n}"
    t["png_bucket_sheet"] = f"png/bucket_B{t['rank']}.png"

details = {
 "scope": {"run": ".tmp/superworks_round12_full (77 projects, read-only)", "date": "2026-10-10",
           "families": {"正式典设": 49, "N2604合同": 25, "110kV变压器保护柜": 1, "PAC-885G-H": 1, "变压器测控柜": 1}},
 "strict_definition": "沿用 report/superworks_artifacts.py：eligible = 端子/装置端子 且有导线接触且标签已解析；consumed = 非 discard 生产配对中的 SW 证据 port_ids 命中且侧值与端口身份相等。",
 "discrepancy": {"user_quoted_strict_coverage": "约 63%", "measured_round12_terminal_strict": R["b_terminal_ports_strict"]["rate"],
                 "round3_f5_strict": 0.5749, "report_md_quoted_strict": 0.9428,
                 "note": "round12 实测严格口径为 57.3%（47380/82680）；63% 无法在 round12/round3 复现（N2604 子集为 63.0%）；report.md 的 94.28% 来自另一次验收运行口径，不可与本回放比较。"},
 "layers": {k: R[k] for k in R if k in ("a_strip_connections", "a2_strip_destination_texts", "a2_cross_page_target_check",
                                         "b_terminal_ports_strict", "b_other_categories_loose", "d_component_backplane_text_level",
                                         "c_schematic_groups")},
 "uncovered_union": {"total": R["uncovered_union"]["total"], "layer_totals": R["uncovered_union"]["layer_totals"]},
 "top8": top8,
 "checks": checks,
}
(OUT / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("details.json written", len(top8), "top buckets")
print(json.dumps(checks, ensure_ascii=False, indent=1)[:4000])
