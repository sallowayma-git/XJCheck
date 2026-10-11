import sys, json
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
pd.set_option("display.width", 320); pd.set_option("display.max_colwidth", 90); pd.set_option("display.max_columns", 30)
ids = {"p062": ["PSWa334926e05c04a06", "PSW9979c69861a36183", "PSW0cf5e7c865e7b280", "PSWe154b8e80458a9e1", "PSWb31c49994c795cfd"]}
for proj, run in [("p062", "21000")]:
    pairs = table(proj, run, "pairs")
    tx = table(proj, run, "texts")
    sel = pairs[pairs.pair_id.isin(ids[proj])]
    print(sel[["pair_id","line_group_id","sheet_id","status","left_value","right_value","left_text_id","right_text_id","rationale","pair_kind","confidence"]].to_string())
    for _, r in sel.iterrows():
        ev = r.evidence
        try: ev = json.loads(ev) if isinstance(ev, str) else ev
        except Exception: pass
        print("==", r.pair_id, json.dumps(jsonable(ev), ensure_ascii=False)[:1500])
