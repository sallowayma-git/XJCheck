import sys,glob,json
import pandas as pd
sys.path.insert(0,'.planning/superworks-adapter/loop/STRIPNAME/tools')
from render_strip_pairs import pair_frame, dxf_for, J
import ezdxf
after=pair_frame('.tmp/loop_stripname','p061')
rows=after[after.left_value.astype(str).str.contains("3-21GD1[67]$")].reset_index()
for r in rows.itertuples():
    print(r.pair_id, r.sheet_id, r.file_id, repr(r.left_value), repr(r.right_value), r.pair_kind, r.status)
# files for sheets
cov=pd.read_parquet(glob.glob('.tmp/loop_stripname/p061/*/findings/sw_strip_rows.parquet')[0])
s8=cov[cov.sheet_id=='S0008']
print('S0008 strip rows', len(s8), s8.endpoint_identity.astype(str).head(3).tolist())
fid=rows[rows.sheet_id=='S0008'].file_id.iloc[0]
doc=ezdxf.readfile(dxf_for('p061',fid))
hits=[(e.dxftype(), e.dxf.handle, (e.dxf.text if e.dxftype()=='TEXT' else e.plain_text()), round(e.dxf.insert.x,1), round(e.dxf.insert.y,1)) for e in doc.modelspace() if e.dxftype() in ('TEXT','MTEXT') and ('3-21GD17' in (e.dxf.text if e.dxftype()=='TEXT' else e.plain_text()) or '3-21GD16' in (e.dxf.text if e.dxftype()=='TEXT' else e.plain_text()))]
print('DXF texts for 3-21GD16/17 on S0008 file', fid, hits)
