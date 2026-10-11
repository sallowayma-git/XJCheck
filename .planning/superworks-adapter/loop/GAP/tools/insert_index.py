"""INSERT index of the frozen DXF files that carry GAP wires (read-only). Writes <out>/inserts.parquet.

One row per modelspace INSERT: project, file_id, handle, block name, insertion point, world bounding box of the block
(ezdxf extents of its virtual entities), and the SW markers of the INSERT (LD_SYMB2_SPECIAL / LD_SYMB2_LABEL present).
An INSERT with no LD_SYMB2_SPECIAL is an unregistered component block (the GAP-1 far-end candidate).

Usage: python insert_index.py <uncovered.parquet> <out_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import ezdxf
from ezdxf import bbox as ezbbox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaplib as G  # noqa: E402


def index_file(path: str, project: str, file_id: str):
    try:
        doc = ezdxf.readfile(path)
    except Exception:  # noqa: BLE001
        from ezdxf import recover
        doc, _ = recover.readfile(path)
    rows = []
    for ins in doc.modelspace().query("INSERT"):
        try:
            ext = ezbbox.extents(ins.virtual_entities(), fast=True)
            box = (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y) if ext.has_data else (None,) * 4
        except Exception:  # noqa: BLE001
            box = (None,) * 4
        has_special = bool(_has(ins, "LD_SYMB2_SPECIAL"))
        has_label = bool(_has(ins, "LD_SYMB2_LABEL"))
        rows.append({"project": project, "file_id": file_id, "handle": ins.dxf.handle, "block": ins.dxf.name,
                     "x": float(ins.dxf.insert.x), "y": float(ins.dxf.insert.y),
                     "xmin": box[0], "ymin": box[1], "xmax": box[2], "ymax": box[3],
                     "sw_special": has_special, "sw_label": has_label})
    return rows


def _has(ins, app):
    try:
        return ins.has_xdata(app)
    except Exception:  # noqa: BLE001
        return False


def main(uncovered_path: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    u = pd.read_parquet(uncovered_path)
    targets = u[u.dxf.notna()][["project", "file_id", "dxf"]].drop_duplicates()
    rows = []
    for i, r in enumerate(targets.itertuples()):
        if not Path(r.dxf).exists():
            continue
        try:
            rows.extend(index_file(r.dxf, r.project, r.file_id))
        except Exception as exc:  # noqa: BLE001
            print("fail", r.project, r.file_id, exc)
        if i % 50 == 0:
            print(i, len(targets), len(rows), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_parquet(out_dir / "inserts.parquet", index=False)
    print("inserts", len(frame), "files", len(targets))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
