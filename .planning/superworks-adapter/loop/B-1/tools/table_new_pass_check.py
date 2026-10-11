"""B-1 FIX step 5 follow-up: explain the new table pass P0001 (T0479 "1" -> T0511 "1") on S0008.

Renders a window around the S0008 middle column with the hidden numeral (T0441),
the new middle reading (T0479), P0002's middle (T0472) and the outer cells (T0511, T0459).
Read-only; writes B-1/fix_png/table_new_pass_S0008.png and prints cell facts.
"""
from __future__ import annotations

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
from common import ROOT, dxf_path, table  # noqa: E402

OUT = ROOT / ".planning/superworks-adapter/loop/B-1/fix_png/table_new_pass_S0008.png"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
CFG = Configuration.defaults().with_changes(color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE)
MARK = {"T0441": ("hidden middle (old P0001)", "#dc2626"), "T0479": ("new middle (new P0001)", "#7c3aed"),
        "T0472": ("middle (P0002)", "#2563eb"), "T0511": ("outer (P0001 new / old)", "#16a34a"),
        "T0459": ("outer (P0002)", "#0d9488")}


def main() -> None:
    import glob
    import pandas as pd
    fix_texts = sorted(glob.glob(str(ROOT / ".tmp/loop_invis/p071/*/findings/texts.parquet")))[0]
    texts = pd.read_parquet(fix_texts).set_index("text_id")
    doc = ezdxf.readfile(dxf_path("p071", "F0008"))
    msp = doc.modelspace()
    cx, cy = 210.0, 178.0
    fig, ax = plt.subplots(figsize=(7.4, 5.2), dpi=130)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=CFG).draw_layout(msp, finalize=True)
    ax.set_xlim(cx - 45, cx + 150)
    ax.set_ylim(cy - 22, cy + 22)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    facts = []
    for tid, (label, colour) in MARK.items():
        r = texts.loc[tid]
        x, y = float(r.insert_x), float(r.insert_y)
        ax.plot([x], [y], marker="o", ms=7, mfc="none", mec=colour, mew=1.6, zorder=20)
        ax.text(x + 1.2, y + 1.0, f'{tid} "{r.text}" {r.layer} {label}', fontsize=6, color=colour, zorder=21)
        facts.append({"text_id": tid, "value": r.text, "layer": r.layer, "handle": r.handle,
                      "insert": [round(x, 3), round(y, 3)], "raw_height": None if r.raw_height != r.raw_height else float(r.raw_height)})
    ax.set_title("S0008 middle column window (x 165..360, y 156..200)", fontsize=8)
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    for f in facts:
        print(f)


if __name__ == "__main__":
    main()
