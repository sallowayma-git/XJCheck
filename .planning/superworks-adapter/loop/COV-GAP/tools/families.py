import json, collections, os
MAN = "F:/workspace/XJToolkit/.planning/superworks-adapter/corpus_manifest.json"
d = json.load(open(MAN, encoding="utf-8"))
c = collections.Counter()
FAMILY_OF = {}
for p in d["projects"]:
    parts = p["input_root"].replace("/", "\\").split("\\")
    i = parts.index("test")
    fam = parts[i + 1]
    c[fam] += 1
    FAMILY_OF[p["project_id"]] = fam
    print(p["project_id"], "|", fam, "|", "/".join(parts[i + 2:i + 3])[:60])
print(c)
json.dump(FAMILY_OF, open("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/COV-GAP/tools/family_map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
