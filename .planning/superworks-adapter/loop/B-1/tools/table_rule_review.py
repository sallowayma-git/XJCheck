"""B-1 FIX v2 review: render every numeric three-column pass (round13 base) with its cell borders.

Read-only. Uses the base (unfiltered) per-sheet dump pickles from the debug replay, reproduces the
detected grid, and draws each mapped row over the DXF (frozen cache) with the detected cell borders
(dashed) and the numerals inside the middle and outer cells. Writes
B-1/fix_png/rule_<proj>_<sheet>_row<k>.png and a JSON summary.
"""
from __future__ import annotations

import json
import pickle
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
from common import ROOT, dxf_path  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))
from dwg_audit.audit.table_extractor import (  # noqa: E402
    _assign_texts_to_cells,
    _build_cells,
    _detect_table_grid,
    _looks_like_numeric_value,
)

DUMP = ROOT / ".tmp/loop_invis_dbg_pp"
OUT = ROOT / ".planning/superworks-adapter/loop/B-1/fix_png"
CASES = [("p055", "S0012"), ("p071", "S0008"), ("p071", "S0009")]
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
CFG = Configuration.defaults().with_changes(color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE)


def numerals(items):
    return sum(1 for t in items if _looks_like_numeric_value(t.normalized_text))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for proj, sheet_id in CASES:
        payload = pickle.load(open(DUMP / proj / "table_dump" / f"{sheet_id}.pkl", "rb"))
        sheet = payload["sheet"]
        texts = list(payload["texts"])  # base: no invisible filter, to match round13
        grid = _detect_table_grid(payload["lines"], payload["polylines"], sheet)
        rows, cols = grid
        cells = _build_cells(rows, cols)
        cell_values = _assign_texts_to_cells(texts, cells, sheet)
        # Pre-rule (base) rows: the current code adds the rule, so reuse the OLD row logic.
        from table_numeric_rule_impact import old_rows
        mappings = []
        for row_index, mid, left, right in old_rows(cell_values, rows):
            mappings.append({
                "row_index": row_index,
                "middle_value": mid.normalized_text,
                "middle_text_id": mid.text_id,
                "middle_coord": [mid.insert_x, mid.insert_y],
                "right_value": right.normalized_text if right is not None else None,
                "right_text_id": right.text_id if right is not None else None,
                "right_coord": [right.insert_x, right.insert_y] if right is not None else None,
            })
        doc = ezdxf.readfile(dxf_path(proj, sheet.file_id))
        msp = doc.modelspace()
        for m in mappings:
            r = m["row_index"]
            mid_xy = m["middle_coord"]
            right_xy = m["right_coord"]
            x0 = min(mid_xy[0], right_xy[0] if right_xy else mid_xy[0]) - 12
            x1 = max(mid_xy[0], right_xy[0] if right_xy else mid_xy[0]) + 12
            y0, y1 = rows[r] - 3, rows[r + 1] + 3
            fig, ax = plt.subplots(figsize=(7.6, 5.0), dpi=130)
            Frontend(RenderContext(doc), MatplotlibBackend(ax), config=CFG).draw_layout(msp, finalize=True)
            for c in cols:
                if x0 - 2 <= c <= x1 + 2:
                    ax.plot([c, c], [y0, y1], ls="--", lw=0.8, color="#0ea5e9", zorder=15)
            for yy in rows:
                if y0 - 1 <= yy <= y1 + 1:
                    ax.plot([x0, x1], [yy, yy], ls="--", lw=0.8, color="#0ea5e9", zorder=15)
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])
            cell_info = {}
            for col, label, colour in ((0, "L", "#2563eb"), (1, "M", "#dc2626"), (2, "R", "#16a34a")):
                items = cell_values.get((r, col), [])
                cell_info[label] = {"texts": len(items), "numerals": numerals(items)}
                for t in items:
                    if _looks_like_numeric_value(t.normalized_text):
                        ax.plot([t.insert_x], [t.insert_y], marker="o", ms=5, mfc="none", mec=colour, mew=1.2, zorder=20)
            mid_text = m["middle_text_id"]
            ax.set_title(
                f'{proj} {sheet_id} row {r}: M {m["middle_value"]} ({mid_text}) -> R {m["right_value"]} ({m["right_text_id"]})\n'
                f'cell numerals L/M/R = {cell_info["L"]["numerals"]}/{cell_info["M"]["numerals"]}/{cell_info["R"]["numerals"]}; '
                f'texts = {cell_info["L"]["texts"]}/{cell_info["M"]["texts"]}/{cell_info["R"]["texts"]}',
                fontsize=8,
            )
            out = OUT / f"rule_{proj}_{sheet_id}_row{r}.png"
            fig.savefig(out, bbox_inches="tight")
            plt.close(fig)
            summary.append({"project": proj, "sheet_id": sheet_id, "row_index": r,
                            "middle": {"text_id": mid_text, "value": m["middle_value"], "xy": mid_xy},
                            "right": {"text_id": m["right_text_id"], "value": m["right_value"], "xy": right_xy},
                            "cells": cell_info, "png": out.name})
            print(out.name, cell_info)
    (OUT / "rule_review_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
