import json, sys, collections
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/MULTI-SEG/tools")
import ms_common as M
recs = json.load(open("F:/workspace/XJToolkit/.tmp/multiseg_work/cls870.json", encoding="utf-8"))
out = []
by_pid = collections.defaultdict(list)
for i, r in enumerate(recs):
    by_pid[r["pid"]].append((i, r))
stats = collections.Counter()
examples = collections.defaultdict(list)
for pid, items in by_pid.items():
    proj = M.Project(pid, next((M.ROUND / pid).glob("*/findings")))
    unreg = proj.unreg
    for i, r in items:
        fid = r["file_id"]
        blocks = [b for b in unreg if M.text(b["file_id"]) == fid]
        for g in r["gaps"]:
            if g["is_candidate_gap"]:
                continue
            x0, x1, y = g["x0"], g["x1"], r["y"]
            hit = None
            for b in blocks:
                tps = M.jload(b.get("termpoints"), [])
                left = right = False
                for tp in tps:
                    for p in (tp["a"], tp["b"]):
                        if abs(p[1] - y) <= 0.6 and abs(p[0] - x0) <= 0.6:
                            left = True
                        if abs(p[1] - y) <= 0.6 and abs(p[0] - x1) <= 0.6:
                            right = True
                if left and right:
                    hit = b
                    break
            key = "UNREG_2PIN_SPAN" if hit else ("ONE_END_UNREG" if any(
                abs(p[0] - x0) <= 0.6 or abs(p[0] - x1) <= 0.6 for b in blocks for tp in M.jload(b.get("termpoints"), [])
                for p in (tp["a"], tp["b"])) else "NO_UNREG")
            stats[(round(g["width"], 1) if g["width"] < 30 else "30+", key)] += 1
            if len(examples[key]) < 5:
                examples[key].append((i, pid, r["line_group_id"], round(x0, 2), round(x1, 2)))
for k, v in sorted(stats.items(), key=lambda kv: -kv[1])[:30]:
    print(v, k)
print({k: v[:3] for k, v in examples.items()})
