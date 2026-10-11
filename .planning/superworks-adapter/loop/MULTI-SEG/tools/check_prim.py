import sys, json
import pandas as pd
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/MULTI-SEG/tools")
import ms_common as M
from pathlib import Path
pid, fid = sys.argv[1], sys.argv[2]
x0, x1, y0, y1 = map(float, sys.argv[3:7])
findings = next((M.ROUND / pid).glob("*/findings"))
prim = pd.read_parquet(findings / "primitive_segments.parquet")
p = prim[(prim.file_id == fid)]
hit = p[(p.bbox_max_x >= x0) & (p.bbox_min_x <= x1) & (p.bbox_max_y >= y0) & (p.bbox_min_y <= y1)]
print("primitives in window:", len(hit))
cols = ["primitive_kind", "source_entity_type", "definition_name", "nested_path", "layer", "bbox_min_x", "bbox_min_y", "bbox_max_x", "bbox_max_y", "visible"]
print(hit[cols].head(40).to_string())
