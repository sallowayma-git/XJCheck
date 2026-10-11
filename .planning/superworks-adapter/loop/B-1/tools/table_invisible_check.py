"""B-1 FIX step 3: verify the table_mapping passes that use hidden numerals (read-only).

For each table_mapping pass in round13 p071 (S0008/S0009), report the raw DXF height of
its cells and draw a window crop with the cells highlighted. Writes PNGs to B-1/fix_png/
and a JSON summary to B-1/fix_png/table_invisible_check.json. Reads the frozen DXF cache
only; does not modify any input.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MANIFEST, ROOT, dxf_path, table  # noqa: E402

ROUND_PROJ, ROUND_RUN = "p071", "30000"
OUT_DIR = ROOT / ".planning/superworks-adapter/loop/B-1/fix_png"
PAIR_IDS = ["P0001", "P0002", "P0003", "P0004"]
SHEETS = {"S0008": "F0008", "S0009": "F0009"}
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
CFG = Configuration.defaults().with_changes(color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE)


def modelspace_texts(doc):
    rows = []
    for e in doc.modelspace():
        if e.dxftype() == "TEXT":
            rows.append(e)
    return rows


def main() -> None:
    pairs = table(ROUND_PROJ, ROUND_RUN, "pairs")
    texts = table(ROUND_PROJ, ROUND_RUN, "texts")
    passes = pairs[pairs.pair_id.isin(PAIR_IDS)]
    summary = []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sheet_id, file_id in SHEETS.items():
        doc = ezdxf.readfile(dxf_path(ROUND_PROJ, file_id))
        msp = doc.modelspace()
        by_handle = {}
        for e in msp:
            h = str(getattr(e.dxf, "handle", ""))
            by_handle[h] = e
        for _, row in passes[passes.sheet_id == sheet_id].iterrows():
            info = json.loads(row.evidence)["table_mapping"]
            cells = {}
            for role in ("middle", "left", "right"):
                tid = info.get(f"{role}_text_id")
                if not tid:
                    continue
                trow = texts[texts.text_id == tid].iloc[0]
                ent = by_handle.get(trow.handle)
                raw = float(ent.dxf.height) if ent is not None and ent.dxftype() == "TEXT" else None
                cells[role] = {
                    "text_id": tid,
                    "handle": trow.handle,
                    "value": trow.text,
                    "layer": trow.layer,
                    "engine_height": float(trow.height),
                    "dxf_modelspace_height": raw,
                    "in_modelspace": ent is not None,
                    "insert": [float(trow.insert_x), float(trow.insert_y)],
                }
            summary.append({
                "pair_id": row.pair_id,
                "sheet_id": sheet_id,
                "row_index": info.get("row_index"),
                "left_value": row.left_value,
                "right_value": row.right_value,
                "status": row.status,
                "cells": cells,
            })
            # Window crop centred on the middle cell, wide enough to see the table grid.
            mid = cells.get("middle")
            if mid is None:
                continue
            cx, cy = mid["insert"]
            fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=130)
            ctx = RenderContext(doc)
            Frontend(ctx, MatplotlibBackend(ax), config=CFG).draw_layout(msp, finalize=True)
            ax.set_xlim(cx - 60, cx + 60)
            ax.set_ylim(cy - 40, cy + 40)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])
            colour = {"middle": "#dc2626", "left": "#2563eb", "right": "#16a34a"}
            for role, cell in cells.items():
                x, y = cell["insert"]
                ax.plot([x], [y], marker="o", ms=7, mfc="none", mec=colour[role], mew=1.6, zorder=20)
                tag = f'{role} {cell["text_id"]}/{cell["handle"]} {cell["layer"]} "{cell["value"]}" h={cell["dxf_modelspace_height"]}'
                ax.text(x + 1.5, y + 1.2, tag, fontsize=6.5, color=colour[role], zorder=21)
            ax.set_title(f'{row.pair_id} {sheet_id} row {info.get("row_index")}: {row.left_value} | {row.right_value} (middle hidden?)', fontsize=9)
            out = OUT_DIR / f"table_{row.pair_id}_{sheet_id}.png"
            fig.savefig(out, bbox_inches="tight")
            plt.close(fig)
    (OUT_DIR / "table_invisible_check.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in summary:
        print(item["pair_id"], item["sheet_id"], item["row_index"], item["left_value"], item["right_value"])
        for role, cell in item["cells"].items():
            print("   ", role, cell["text_id"], cell["handle"], repr(cell["value"]), cell["layer"],
                  "engine_h", cell["engine_height"], "dxf_h", cell["dxf_modelspace_height"],
                  "in_msp", cell["in_modelspace"])


if __name__ == "__main__":
    main()
