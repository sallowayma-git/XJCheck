"""Aggregate eval_loggen.py per-project JSON into one table set (read-only).

Usage: python aggregate_loggen.py <eval_dir>   -> prints tables and writes <eval_dir>/aggregate.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

eval_dir = Path(sys.argv[1])
summary = json.loads((eval_dir / "summary.json").read_text(encoding="utf-8"))


def total(field):
    out = Counter()
    for item in summary.values():
        out.update(item.get(field, {}))
    return out


counts = total("counts")
strict = total("strict")
supplement = total("supplement")
supcat = total("supplement_end_categories")
reasons = total("reasons")
end_status = total("end_status")
side_forms = total("side_forms")

by_project = {}
for pid, item in summary.items():
    c = item.get("counts", {})
    s = item.get("strict", {})
    by_project[pid] = {
        "pairs": item.get("pair_count"),
        "records": c.get("records:LOGGEN", 0) + c.get("records:PCL", 0),
        "both_resolved": c.get("records_both_resolved", 0),
        "agree_side": sum(v for k, v in c.items() if k.startswith("side:agree")),
        "conflict_side": c.get("side:conflict", 0),
        "strict_eligible": sum(v for k, v in s.items() if k.startswith("eligible")),
        "strict_consumed": sum(v for k, v in s.items() if k.startswith("consumed")),
        "strict_potential": sum(v for k, v in s.items() if k.startswith("potential:")),
    }

aggregate = {
    "counts": dict(counts), "strict": dict(strict), "supplement": dict(supplement),
    "supplement_end_categories": dict(supcat), "reasons": dict(reasons), "end_status": dict(end_status),
    "side_forms": dict(side_forms), "by_project": by_project,
}
(eval_dir / "aggregate.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=1), encoding="utf-8")


def show(title, mapping, keys=None):
    print(f"\n## {title}")
    for key in sorted(keys if keys is not None else mapping):
        print(f"  {key}: {mapping.get(key, 0)}")


show("counts (selected)", counts, [k for k in counts if not k.startswith("records:LOGGEN:ends_") and not k.startswith("side:") or k.startswith("side:agree") or k.startswith("side:conflict") or k.startswith("side:discard")])
show("strict", strict)
show("supplement (no '|' keys)", supplement, [k for k in supplement if "|" not in k])
show("supplement by pattern", supplement, [k for k in supplement if "|" in k])
show("supplement end categories", supcat)
show("end status", end_status)
show("reasons", reasons)
show("side forms", side_forms)
print("\n## by project")
for pid, row in by_project.items():
    print(pid, row)
