from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[5]
OLD_FINDINGS = ROOT / ".tmp/superworks_round26_full/p067/26000_220kV/findings"
NEW_FINDINGS = ROOT / ".tmp/precision_loop_20261015/p057_slice_10/p067/26000_220kV/findings"
OUT = ROOT / ".tmp/precision_loop_20261015/p067_visibility_screenshots"


def json_value(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scoped_text(texts: pd.DataFrame, file_id: str, sheet_id: str, text_id: str) -> dict:
    rows = texts[(texts.file_id == file_id) & (texts.sheet_id == sheet_id) & (texts.text_id == text_id)]
    if len(rows) != 1:
        raise AssertionError(f"Expected one source text for {file_id}/{sheet_id}/{text_id}, got {len(rows)}")
    row = rows.iloc[0]
    return {
        "text_id": str(text_id),
        "text": str(row.normalized_text),
        "bbox": [float(row.bbox_min_x), float(row.bbox_max_x), float(row.bbox_min_y), float(row.bbox_max_y)],
        "xy": [float(row.insert_x), float(row.insert_y)],
        "dxf_visible": None if pd.isna(row.dxf_visible) else bool(row.dxf_visible),
        "layer": str(row.layer),
        "handle": str(row.handle),
    }


def render_source_page(dxf_path: Path, bbox: tuple[float, float, float, float], path: Path) -> tuple[float, ...]:
    xmin, ymin, xmax, ymax = bbox
    pad = 1.0
    bbox = (xmin - pad, ymin - pad, xmax + pad, ymax + pad)
    xmin, ymin, xmax, ymax = bbox
    width, height = xmax - xmin, ymax - ymin
    fig_width = 42.0
    fig = plt.figure(figsize=(fig_width, fig_width * height / width), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    doc = ezdxf.readfile(dxf_path)
    from ezdxf.addons.drawing import Frontend
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.properties import RenderContext

    cfg = Configuration().with_changes(color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE)
    ax.set_facecolor("white")
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace(), finalize=False)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    fig.savefig(path, dpi=100, facecolor="white", pad_inches=0)
    plt.close(fig)
    return bbox


def crop_world(image: Image.Image, page_bbox: tuple[float, ...], center: list[float], half: float) -> Image.Image:
    xmin, ymin, xmax, ymax = page_bbox
    x0, x1 = center[0] - half, center[0] + half
    y0, y1 = center[1] - half, center[1] + half
    sx = image.width / (xmax - xmin)
    sy = image.height / (ymax - ymin)
    left = int(round((x0 - xmin) * sx))
    right = int(round((x1 - xmin) * sx))
    top = int(round((ymax - y1) * sy))
    bottom = int(round((ymax - y0) * sy))
    return image.crop((left, top, right, bottom))


def draw_panel(ax, image, page_bbox, center, half, marks, title):
    crop = crop_world(image, page_bbox, center, half)
    x0, x1 = center[0] - half, center[0] + half
    y0, y1 = center[1] - half, center[1] + half
    ax.imshow(crop, extent=(x0, x1, y0, y1), origin="upper", interpolation="antialiased")
    mark = (x1 - x0) * 0.014
    for kind, xy, color, label, bbox in marks:
        if kind == "box" and bbox:
            x_min, x_max, y_min, y_max = bbox
            ax.add_patch(plt.Rectangle((x_min, y_min), x_max - x_min, y_max - y_min,
                                       fill=False, ec=color, lw=1.7, zorder=55))
            continue
        if xy is None:
            continue
        ax.add_patch(plt.Circle((xy[0], xy[1]), mark * 1.15, fill=False, ec=color, lw=1.7, zorder=55))
        ax.text(xy[0] + mark * 1.5, xy[1] + mark * 1.2, label, color=color, fontsize=6.5, zorder=60,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 0.5})
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=8)


def render_case(case: dict, page_image: Image.Image, page_bbox: tuple[float, ...], path: Path) -> None:
    row_xy = case["middle_text"]["xy"]
    right_xy = case["right_text"]["xy"]
    header_xy = case["header_coord"]
    points_xy = [row_xy, right_xy, header_xy]
    for text in (case["middle_text"], case["right_text"]):
        x_min, x_max, y_min, y_max = text["bbox"]
        points_xy.extend(([x_min, y_min], [x_max, y_max]))
    cx = (min(point[0] for point in points_xy) + max(point[0] for point in points_xy)) / 2
    cy = (min(point[1] for point in points_xy) + max(point[1] for point in points_xy)) / 2
    half = max(max(point[0] for point in points_xy) - min(point[0] for point in points_xy),
               max(point[1] for point in points_xy) - min(point[1] for point in points_xy)) / 2 + 9.0

    fig, axes = plt.subplots(1, 3, figsize=(18.0, 6.5), dpi=140)
    fig.subplots_adjust(left=0.012, right=0.988, top=0.80, bottom=0.055, wspace=0.10)
    marks = [
        ("box", row_xy, "#1f4fd1", "row " + case["middle_text"]["text"], case["middle_text"]["bbox"]),
        ("box", right_xy, "#c81e1e", "endpoint " + case["right_text"]["text"], case["right_text"]["bbox"]),
        ("circle", header_xy, "#d62fbf", "table title", None),
    ]
    draw_panel(axes[0], page_image, page_bbox, [cx, cy], half, marks, "A. Table header, row number, and external terminal")

    device = case["visible_device_text"]
    hidden = case["hidden_template_text"]
    device_center = device["xy"]
    device_half = 25.0
    device_marks = [
        ("circle", device["xy"], "#168139", "visible 8n", None),
        ("circle", hidden["xy"], "#c81e1e", "1-8n hidden in DXF", None),
    ]
    draw_panel(axes[1], page_image, page_bbox, device_center, device_half, device_marks,
               "B. MARK-layer device identity and hidden template prefix")

    caption = case["caption_text"]
    cap_center = caption["xy"]
    draw_panel(axes[2], page_image, page_bbox, cap_center, 22.0,
               [("box", cap_center, "#168139", caption["text"], caption["bbox"])],
               "C. Visible page caption")

    title = (f"{case['pair_id']} | old V1 {case['old_left']} -> {case['right_value']} ({case['old_status']})  |  "
             f"current {case['new_left']} -> {case['right_value']} ({case['new_status']})\n"
             f"device={case['new_device']} header={case['header_prefix']} row={case['row_number']} | "
             "blue=table row, red=external endpoint/hidden template location, green=visible device/caption")
    fig.text(0.014, 0.97, title, fontsize=9, va="top", ha="left")
    fig.savefig(path, dpi=140, facecolor="white")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=False)
    png_dir = OUT / "png"
    png_dir.mkdir()
    old_pairs = pd.read_parquet(OLD_FINDINGS / "pairs.parquet")
    new_pairs = pd.read_parquet(NEW_FINDINGS / "pairs.parquet")
    texts = pd.read_parquet(NEW_FINDINGS / "texts.parquet")
    pages = pd.read_parquet(NEW_FINDINGS / "pages.parquet")

    old_by_id = {}
    for row in old_pairs.itertuples():
        evidence = json_value(row.evidence) or {}
        mapping = evidence.get("table_mapping") or {}
        if (row.pair_kind == "table_mapping" and row.status == "pass"
                and mapping.get("mapping_mode") == "backplate_virtual_table"
                and mapping.get("composite_device_instance") == "1-8n"):
            old_by_id[str(row.pair_id)] = (row, evidence, mapping)
    new_by_id = {str(row.pair_id): row for row in new_pairs.itertuples()}
    changed = []
    for pair_id, (old_row, old_evidence, old_mapping) in sorted(old_by_id.items()):
        row = new_by_id[pair_id]
        evidence = json_value(row.evidence) or {}
        mapping = evidence.get("table_mapping") or {}
        if mapping.get("composite_device_instance") == "8n" and row.left_value != old_row.left_value:
            changed.append((pair_id, old_row, old_evidence, old_mapping, row, evidence, mapping))
    if len(changed) != 42:
        raise AssertionError(f"Expected exactly 42 p067 changed mappings, got {len(changed)}")

    file_id = str(changed[0][4].file_id)
    sheet_id = str(changed[0][4].sheet_id)
    if any(str(item[4].file_id) != file_id or str(item[4].sheet_id) != sheet_id for item in changed):
        raise AssertionError("Changed mappings span multiple source pages")
    page_texts = texts[(texts.file_id == file_id) & (texts.sheet_id == sheet_id)]
    visible_devices = page_texts[
        (page_texts.normalized_text.astype(str).str.strip().str.upper() == "8N")
        & (page_texts.layer.astype(str).str.upper() == "MARK")
        & page_texts.dxf_visible.fillna(False).astype(bool)
    ]
    hidden_templates = page_texts[
        (page_texts.normalized_text.astype(str).str.strip().str.upper() == "1-8N")
        & (page_texts.layer.astype(str).str.upper() == "MARK")
        & (~page_texts.dxf_visible.fillna(True).astype(bool))
    ]
    captions = page_texts[
        page_texts.normalized_text.astype(str).str.fullmatch(r"(?i)\s*8n\s*REAR\s*WIRING(?:\s*\d+)?\s*")
        & page_texts.dxf_visible.fillna(False).astype(bool)
    ]
    if len(visible_devices) != 1 or len(hidden_templates) < 1 or len(captions) != 1:
        raise AssertionError(f"Unexpected source visibility evidence: visible={len(visible_devices)} hidden={len(hidden_templates)} captions={len(captions)}")
    device = scoped_text(texts, file_id, sheet_id, str(visible_devices.iloc[0].text_id))
    hidden_row = hidden_templates.iloc[0]
    # Prefer the hidden field geometrically closest to the visible 8n title/device tag.
    hidden_index = ((hidden_templates.insert_x - device["xy"][0]) ** 2
                    + (hidden_templates.insert_y - device["xy"][1]) ** 2).idxmin()
    hidden = scoped_text(texts, file_id, sheet_id, str(texts.loc[hidden_index].text_id))
    caption = scoped_text(texts, file_id, sheet_id, str(captions.iloc[0].text_id))

    page = pages[pages.file_id == file_id].iloc[0]
    bbox = json_value(page.extent_bbox)
    bbox = tuple(float(item) for item in bbox)
    project = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
    project = next(item for item in project["projects"] if item["project_id"] == "p067")
    source = next(item for item in project["files"] if item["file_id"] == file_id)
    dxf_path = Path(source["dxf_path"])
    if sha256(dxf_path) != source["dxf_sha256"]:
        raise AssertionError("Frozen source DXF hash mismatch")
    page_raster = png_dir / "source_page.png"
    page_bbox = render_source_page(dxf_path, bbox, page_raster)
    with Image.open(page_raster) as image:
        page_image = image.copy()

    cases = []
    for ordinal, (pair_id, old_row, old_evidence, old_mapping, row, evidence, mapping) in enumerate(changed, start=1):
        header = mapping.get("header_coord")
        if not header:
            raise AssertionError(f"Missing table header coordinate for {pair_id}")
        middle = scoped_text(texts, file_id, sheet_id, str(mapping["middle_text_id"]))
        right = scoped_text(texts, file_id, sheet_id, str(mapping["right_text_id"]))
        header_xy = [float(header[0]), float(header[1])]
        case = {
            "case_no": ordinal,
            "pair_id": pair_id,
            "project": "p067",
            "file_id": file_id,
            "sheet_id": sheet_id,
            "sheet_no": str(evidence.get("sheet_no")),
            "filename": str(evidence.get("filename")),
            "old_status": str(old_row.status),
            "old_left": str(old_row.left_value),
            "new_status": str(row.status),
            "new_left": str(row.left_value),
            "right_value": str(row.right_value),
            "new_device": mapping.get("composite_device_instance"),
            "header_prefix": mapping.get("header_prefix"),
            "row_number": mapping.get("row_number"),
            "header_coord": header_xy,
            "middle_text": middle,
            "right_text": right,
            "hidden_template_text": hidden,
            "visible_device_text": device,
            "caption_text": caption,
            "dxf_path": dxf_path.as_posix(),
        }
        image_path = png_dir / f"{pair_id}.png"
        render_case(case, page_image, page_bbox, image_path)
        case["screenshot"] = f"png/{image_path.name}"
        case["screenshot_sha256"] = sha256(image_path)
        case["screenshot_bytes"] = image_path.stat().st_size
        with Image.open(image_path) as image:
            image.verify()
        with Image.open(image_path) as image:
            if image.width < 2000 or image.height < 700:
                raise AssertionError(f"Unexpected screenshot size for {pair_id}: {image.size}")
        cases.append(case)

    manifest = {
        "purpose": "One screenshot per p067 backplate mapping changed from hidden 1-8n to visible 8n.",
        "baseline_findings": OLD_FINDINGS.as_posix(),
        "current_findings": NEW_FINDINGS.as_posix(),
        "join_key": "(project, file_id, sheet_id, pair_id)",
        "source_scope": {"project": "p067", "file_id": file_id, "sheet_id": sheet_id, "count": len(cases)},
        "source_dxf": dxf_path.as_posix(),
        "source_dxf_sha256": sha256(dxf_path),
        "source_page_raster": "png/source_page.png",
        "visibility_evidence": {"hidden_template_text": hidden, "visible_device_text": device, "visible_caption": caption},
        "cases": cases,
    }
    (OUT / "cases_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "case_ledger.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "case_no", "pair_id", "file_id", "sheet_id", "old_status", "old_left", "new_status", "new_left",
            "right_value", "new_device", "header_prefix", "row_number", "screenshot", "screenshot_sha256",
        ])
        writer.writeheader()
        for case in cases:
            writer.writerow({key: case[key] for key in writer.fieldnames})
    (OUT / "README.md").write_text(
        "# p067 42-pair visibility review\n\n"
        "Each `png/Pxxxx.png` isolates one pair changed from a hidden MARK-layer `1-8n` template field to the visible `8n` page identity. "
        "Panel A shows its table title, row text, and external endpoint; panel B shows the hidden field location beside the visible `8n` and device model label; panel C shows the visible `8n REAR WIRING` caption. "
        "`cases_manifest.json` and `case_ledger.csv` record the project/file/sheet-scoped source text IDs, coordinates, statuses, and image hashes.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "case_count": len(cases),
        "file_id": file_id,
        "sheet_id": sheet_id,
        "device_text": device,
        "hidden_template_text": hidden,
        "caption_text": caption,
        "images": len(list(png_dir.glob("P*.png"))),
        "out": OUT.as_posix(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
