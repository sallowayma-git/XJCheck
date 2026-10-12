"""P2-BACKPLATE device-prefix offline evaluation (read-only over a finished replay).

For every backplate virtual-table pass pair whose sheet carries a page caption "<device> REAR WIRING":
  current device  = the V1 composite device in the replay;
  new device      = the rule of table_extractor: the caption replaces the current device only when the two
                    differ in device core (bay prefix and uppercase suffix dropped); a device-less pair takes the
                    caption device.
Each pair is compared with the SW identities that partner the same external terminal R with the same row number
(SW pass pairs only, same rule as the corroboration). Output: transition counts per class.
Usage: python prefix_offline_eval.py <replay_root> <out_json> <out_csv>
"""
import sys, json, glob, re, math, collections
sys.path.insert(0, 'F:/workspace/XJToolkit/src')
import pandas as pd
from dwg_audit.audit.superworks_extractor import _is_sw_produced_pair, _bp_identity, _bp_key, _bp_device_matches
from dwg_audit.audit.table_extractor import _backplate_device_core
from dwg_audit.domain.models import Pair
from dataclasses import fields

RUN, OUT_JSON, OUT_CSV = sys.argv[1:4]
CAPTION = re.compile(r'^\s*(\d+(?:-\d+)*[A-Za-z])\s*REAR\s*WIRING(?:\s*\d+)?\s*$', re.I)
names = {f.name for f in fields(Pair)}


def clean(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def verdict(devs, device, ok_key):
    if not devs:
        return 'no_row_partner'
    return ok_key if any(_bp_device_matches(d, device) for d in devs) else None


rows = []
stats = collections.Counter()
for pdir in sorted(glob.glob(RUN + '/p*/*/findings')):
    pid = pdir.replace(chr(92), '/').split('/')[-3]
    texts = pd.read_parquet(pdir + '/texts.parquet', columns=['sheet_id', 'text', 'normalized_text'])
    caps = {}
    for r in texts.itertuples():
        for s in (r.normalized_text, r.text):
            m = CAPTION.match(str(s or ''))
            if m:
                caps.setdefault(r.sheet_id, set()).add(m.group(1))
                break
    caps = {sid: list(v)[0] for sid, v in caps.items() if len(v) == 1}
    if not caps:
        continue
    df = pd.read_parquet(pdir + '/pairs.parquet')
    pairs = []
    for r in df.to_dict('records'):
        kw = {k: clean(v) for k, v in r.items() if k in names}
        kw['evidence'] = json.loads(r['evidence']) if isinstance(r['evidence'], str) else (r['evidence'] or {})
        kw['alternative_pair_candidate_ids'] = []
        pairs.append(Pair(**kw))
    partners = collections.defaultdict(list)
    for p in pairs:
        if p.status == 'pass' and _is_sw_produced_pair(p):
            for a, b in ((p.left_value, p.right_value), (p.right_value, p.left_value)):
                if _bp_key(a) and _bp_key(b):
                    partners[_bp_key(a)].append((p.pair_id, b))
    for p in pairs:
        tm = (p.evidence or {}).get('table_mapping') or {}
        if p.status != 'pass' or tm.get('mapping_mode') != 'backplate_virtual_table':
            continue
        if p.sheet_id not in caps:
            continue
        cap = caps[p.sheet_id]
        cur = tm.get('composite_device_instance')
        row = tm.get('row_number')
        if cur and _backplate_device_core(cur) == _backplate_device_core(cap):
            new = cur
        else:
            new = cap
        R = _bp_key(p.right_value)
        sw_devs = []
        for sw_id, other in partners.get(R, []):
            ident = _bp_identity(other)
            if ident and ident['row'] == row:
                sw_devs.append(ident['device'])
        if not sw_devs:
            cls = 'no_row_partner'
        else:
            cur_ok = bool(cur) and any(_bp_device_matches(d, cur) for d in sw_devs)
            new_ok = any(_bp_device_matches(d, new) for d in sw_devs)
            before = 'device_less' if not cur else ('cur_ok' if cur_ok else 'cur_bad')
            after = 'new_ok' if new_ok else 'new_bad'
            cls = before + '->' + after
            if cur and new != cur:
                cls += ' (string_changed)'
        stats[cls] += 1
        rows.append(dict(project=pid, sheet_id=p.sheet_id, pair_id=p.pair_id, R=p.right_value, row=row,
                         cur_device=cur, caption_device=cap, new_device=new, sw_devices=';'.join(sorted(set(sw_devs))),
                         cls=cls))
    stats['sheets_with_caption'] += len(caps)
pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
json.dump(dict(stats), open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(dict(stats))
