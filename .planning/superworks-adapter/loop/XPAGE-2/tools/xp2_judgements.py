"""Visual judgements of the final-state sample (XPAGE-2 round B remainder + round C), and the Markdown table.

Labels: A = suspected real inconsistency (clear wire/device disagreement, no visible equivalence);
B1 = naming form (hyphen between device prefix and terminal, e.g. K861-2X3 vs K8612X3);
B2 = range terminal of another U-number family (target U1Dx~y, row Uk Dx, same D number);
B3 = two labels on one drawn horizontal wire (the other end lies on the same drawn wire).
Usage: python xp2_judgements.py  (writes judgements_final.json and prints the table)
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LABELS = {
    "C01": ("B3", "57UD16 与目标 57nD10 共在同一水平导线（D8/D10/D12 标签），另一端 57nD12 同线"),
    "C02": ("A", "1KD5 → 1n114；目标 114 线去向 1qd22，图上未见等价（待人工核对）"),
    "C03": ("A", "1QD12 → 7 页 1QD10；该端子实际接线连 1QD9（同一水平线），与行远端 1n413 不符"),
    "D20": ("B1", "远端 k863-2x2 与目标 K8632X2 只差连字符"),
    "D24": ("B1", "远端 k861-1x9 与目标 K8611X9 只差连字符"),
    "D25": ("B1", "远端 k863-2x13 与目标 K8632X13 只差连字符"),
    "D26": ("A", "远端 3-4fa-14，目标线号 3-2n226，装置不同"),
    "D30": ("B1", "远端 k863-2x2 与目标 K8632X2 只差连字符"),
    "D31": ("A", "远端 k742-x4，目标为 K862 装置 1X7"),
    "W01": ("A", "2-7XD1 远端 1-7xd2/2-7n819，目标线号 1n101 不见于本行"),
    "W02": ("A", "4Q1D33 远端 4n1711，目标线号 1005"),
    "W03": ("A", "7QD18 远端 7qk-4，目标线号 202"),
    "W04": ("A", "7QD17 远端 7n602，目标线号 202（同页相邻 602/202）"),
    "W05": ("A", "1YD1 远端 1n1316，目标线号 1327"),
    "W06": ("A", "2-7XD2 远端 2-7n820，目标线号 1n101（同族 W01，未逐张目视）"),
    "W07": ("A", "1YD1 远端 1n1316，目标线号 1327（与 W05 同行）"),
    "W08": ("A", "4Q1D32 远端 4n1710，目标线号 1005"),
    "D09": ("B1", "远端 k862-1x5 与目标 K8621X5 只差连字符"),
    "D10": ("A", "4P2D2 远端 fzj1-8，目标为 K861 装置 2X6"),
    "D11": ("B1", "远端 k861-2x13 与目标 K8612X13 只差连字符"),
    "D12": ("A", "4Q1D16 远端 fzj1-3，目标为 K861 装置 1X5"),
    "D13": ("A", "1-4Q1D25 远端 k741-x4，目标为 K861 装置 1X7"),
    "D14": ("A", "1-7QD9 远端 1qd24，目标 1QD23（相邻编号）"),
    "D15": ("A", "1-4Q1D28 远端 fzj1-7，目标为 K861 装置 1X9"),
    "D16": ("A", "1-21YD1 远端 2-21gd17，目标 2-21GD1（相邻编号）"),
    "D17": ("A", "3-4Q2D16 远端 fzj5-3，目标为 K864 装置 1X5"),
    "D18": ("B1", "远端 k861-2x3 与目标 K8612X3 只差连字符"),
}
for k in range(34, 44):
    LABELS[f"R{k}"] = ("B2", "目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同")
for k in range(19, 25):
    LABELS[f"R{k}"] = ("B2", "目标为 U1 范围端子，D 号与行一致、U 号族不同")


def main():
    final = []
    for sub in ("png/it3/index.json", "it4/index.json"):
        for r in json.loads((HERE / sub).read_text(encoding="utf-8")):
            item = r["class"].split(" ", 1)[1]
            tag = item.split()[0]
            if sub.startswith("png/it3") and tag[0] == "W":
                continue  # explained by the target-in-group-far rule (round B)
            if sub.startswith("png/it3") and tag[0] == "D" and tag in ("D21", "D22", "D23", "D27", "D28", "D29", "D32", "D33"):
                continue
            label, note = LABELS[tag]
            final.append({"id": tag, "project": r["project_id"], "strip": r["strip_identity"], "target": r["target_identity"],
                          "far": ", ".join(r["far_values"]), "other": ", ".join(r.get("consumer_other_values") or []) or "-",
                          "page": r.get("ref_page_no", ""), "label": label, "note": note})
    (HERE / "judgements_final.json").write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["| 样本 | 项目 | 行 → 目标（页） | 行远端值 | 目标另一端 | 判定 | 说明 |", "|---|---|---|---|---|---|---|"]
    for f in final:
        lines.append(f"| {f['id']} | {f['project']} | {f['strip']} → {f['target']}（{f['page']} 页） | {f['far']} | {f['other']} | {f['label']} | {f['note']} |")
    print("\n".join(lines))
    from collections import Counter
    print(len(final), Counter(f["label"] for f in final))


if __name__ == "__main__":
    main()
