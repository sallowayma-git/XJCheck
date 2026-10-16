"""Render unannotated full-sheet and expanded raw-DXF views for the 66 source-stratum uncertain pass pairs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from ezdxf.addons.drawing import Frontend
from ezdxf.addons.drawing.config import ColorPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend


ROOT = Path("F:/workspace/XJToolkit")
BASE = ROOT / ".planning/superworks-adapter/loop/PRECISION-BASELINE/CURRENT-2026-10-16/data"
OUT = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/uncertain-66"
RENDERER_PATH = ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"


def import_renderer():
    spec = importlib.util.spec_from_file_location("raw_dxf_renderer", RENDERER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load raw DXF renderer at {RENDERER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def crop_window(row):
    points = [(safe_float(row.get(kx)), safe_float(row.get(ky)))
              for kx, ky in (("left_coord_x", "left_coord_y"), ("right_coord_x", "right_coord_y"))]
    points = [(x, y) for x, y in points if x is not None and y is not None]
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    pad = max(35.0, 0.35 * max(dx, dy))
    width, height = max(dx + 2 * pad, 100.0), max(dy + 2 * pad, 80.0)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return (cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)


def extents(items):
    boxes = [box for _, box in items if box and all(math.isfinite(float(v)) for v in box)]
    if not boxes:
        return None
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    if x1 <= x0 or y1 <= y0:
        return None
    padx, pady = max(3.0, (x1 - x0) * 0.015), max(3.0, (y1 - y0) * 0.015)
    return x0 - padx, y0 - pady, x1 + padx, y1 + pady


def draw_raw_panel(ax, doc, items, ctx, window):
    x0, y0, x1, y1 = window
    entities = [e for e, (bx0, by0, bx1, by1) in items
                if bx1 >= x0 and bx0 <= x1 and by1 >= y0 and by0 <= y1]
    config = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
    Frontend(ctx, MatplotlibBackend(ax), config=config).draw_entities(entities)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()


def render_case(renderer, row, output: Path):
    dxf_path = Path(str(row.get("dxf_path", "")))
    if not dxf_path.is_file():
        return {"rendered": False, "error": "source DXF missing", "dxf_path": str(dxf_path)}
    cache = renderer.DxfCache()
    doc, items, ctx = cache.get(str(dxf_path))
    overview = extents(items)
    detail = crop_window(row)
    if overview is None or detail is None:
        return {"rendered": False, "error": "no drawable extents or pair coordinates", "dxf_path": str(dxf_path)}

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.8), dpi=145, facecolor="white")
    fig.suptitle(f"{row['entity_id']} | {row['project_id']} | {row['file_id']}/{row['sheet_id']}\n"
                 "Raw DXF only: no pair route, endpoint, or classifier overlays", fontsize=10, x=0.02, ha="left")
    axes[0].set_title("Sheet overview", fontsize=8)
    axes[1].set_title("Expanded view around the two text coordinates", fontsize=8)
    draw_raw_panel(axes[0], doc, items, ctx, overview)
    draw_raw_panel(axes[1], doc, items, ctx, detail)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=145, facecolor="white")
    plt.close(fig)
    return {
        "rendered": True,
        "dxf_path": str(dxf_path),
        "dxf_sha256": hash_file(dxf_path),
        "overview_window": overview,
        "detail_window": detail,
        "screenshot_sha256": hash_file(output),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assignments = pd.read_csv(BASE / "sample_assignments.csv", dtype=str, keep_default_na=False)
    judgments = pd.read_csv(BASE / "judgments.csv", dtype=str, keep_default_na=False)
    cases = pd.read_csv(BASE / "sample_cases.csv", dtype=str, keep_default_na=False)
    render_index = pd.read_csv(BASE / "render_index.csv", dtype=str, keep_default_na=False)

    source = assignments[(assignments["margin"] == "source") & (assignments["status"] == "pass")]
    uncertain_ids = set(judgments.loc[judgments["visual_judgment"] == "uncertain", "entity_id"])
    source = source[source["entity_id"].isin(uncertain_ids)].copy()
    if len(source) != 66 or source["entity_id"].nunique() != 66:
        raise RuntimeError(f"Expected 66 unique source-stratum uncertain pairs; got {len(source)}")

    data = source.merge(judgments, on=["entity_kind", "entity_id", "project_id", "status"], suffixes=("_sample", "_old"))
    data = data.merge(cases, on=["entity_kind", "entity_id", "project_id", "status"], suffixes=("", "_case"))
    data = data.merge(render_index, on="entity_id", how="left")
    if len(data) != 66:
        raise RuntimeError(f"Case joins changed expected row count: {len(data)}")

    renderer = import_renderer()
    rows, inventory = [], []
    for row in data.to_dict("records"):
        key = row["entity_id"].replace(":", "_")
        baseline_rel = row.get("screenshot", "")
        baseline_path = BASE / baseline_rel
        baseline_exists = baseline_path.is_file()
        baseline_hash = hash_file(baseline_path) if baseline_exists else ""
        out_path = OUT / "screenshots" / f"{key}.png"
        result = render_case(renderer, row, out_path)
        record = {
            "entity_id": row["entity_id"],
            "project_id": row["project_id"],
            "file_id": row.get("file_id", ""),
            "sheet_id": row.get("sheet_id", ""),
            "source_stratum": row.get("stratum", ""),
            "pair_kind": row.get("pair_kind", ""),
            "page_type": row.get("page_type", ""),
            "left_value": row.get("left_value", ""),
            "right_value": row.get("right_value", ""),
            "left_text_id": row.get("left_text_id", ""),
            "right_text_id": row.get("right_text_id", ""),
            "left_coord_x": row.get("left_coord_x", ""),
            "left_coord_y": row.get("left_coord_y", ""),
            "right_coord_x": row.get("right_coord_x", ""),
            "right_coord_y": row.get("right_coord_y", ""),
            "old_visual_judgment": row.get("visual_judgment", ""),
            "old_judgment_note": row.get("judgment_note", ""),
            "dxf_path": row.get("dxf_path", ""),
            "expected_dxf_sha256": row.get("expected_dxf_sha256", ""),
            "dxf_integrity": row.get("dxf_integrity", ""),
            "baseline_screenshot": f"../../PRECISION-BASELINE/CURRENT-2026-10-16/data/{baseline_rel}" if baseline_exists else "",
            "baseline_screenshot_sha256": baseline_hash,
            "expanded_screenshot": f"screenshots/{out_path.name}" if result["rendered"] else "",
            "expanded_screenshot_sha256": result.get("screenshot_sha256", ""),
            "rendered": result["rendered"],
            "render_error": result.get("error", ""),
            "independent_evidence_type": "",
            "independent_evidence_reference": "",
            "new_visual_judgment": "",
            "manual_review_needed_after": "",
            "reviewer": "",
            "review_note": "",
        }
        rows.append(record)
        inventory.append({"entity_id": row["entity_id"], **result,
                          "expanded_screenshot": record["expanded_screenshot"]})

    pd.DataFrame(rows).to_csv(OUT / "case_review.csv", index=False, encoding="utf-8-sig")
    summary = {
        "scope": "status=pass, source-stratum uncertain judgments",
        "sample_count": len(rows),
        "rendered_count": sum(bool(x["rendered"]) for x in rows),
        "render_failures": [x["entity_id"] for x in rows if not x["rendered"]],
        "strata": source.groupby("stratum").size().to_dict(),
        "output": "screenshots/",
        "evidence_policy": "Raw DXF only; no pair-route, endpoint, or classifier overlays.",
    }
    (OUT / "render_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(inventory).to_json(OUT / "render_manifest.json", orient="records", force_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
