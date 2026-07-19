from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.desktop.lifecycle import default_preview_cache_root
from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.desktop.state_store import default_state_db_path
from dwg_audit.report import load_report_frames

# Fixed screen canvas keeps issue previews readable in the dense inspector.
_CANVAS_WIDTH = 960.0
_CANVAS_HEIGHT = 540.0
_HEADER_HEIGHT = 52.0
_EDGE_PAD = 18.0
_MAX_PREVIEW_LINES = 240
_MAX_PREVIEW_TEXTS = 160


def render_project_preview(
    *,
    project_id: str,
    sheet_id: str | None = None,
    issue_id: str | None = None,
    line_group_id: str | None = None,
    output_dir: Path | None = None,
    state_db_path: Path | None = None,
) -> dict[str, Any]:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    latest = store.load_latest_project_result(project_id)
    if latest is None:
        raise FileNotFoundError(f"No stored result found for project_id={project_id}")

    run = latest["run"]
    artifact_raw = str(run.get("artifact_dir") or "").strip()
    artifact_dir = Path(artifact_raw) if artifact_raw else None

    # Prefer SQLite-retained issue records after conversion workspaces are compacted.
    sqlite_issues = latest.get("issues") or []
    issue_row: pd.Series | None = None
    if issue_id:
        issue_row = _issue_row_from_sqlite(sqlite_issues, issue_id)

    # Lightweight path: when issue already has line geometry evidence, skip loading
    # multi-megabyte parquet frames that freeze the desktop sidecar.
    lightweight = issue_row is not None and _issue_has_geometry_evidence(issue_row)
    if lightweight:
        frames = {}
    elif artifact_dir and artifact_dir.exists():
        frames = load_report_frames(
            artifact_dir,
            names=("issues", "pages", "lines", "texts", "line_groups"),
        )
    else:
        frames = {}

    issues = frames.get("issues", pd.DataFrame())
    pages = frames.get("pages", pd.DataFrame())
    lines = frames.get("lines", pd.DataFrame())
    texts = frames.get("texts", pd.DataFrame())
    line_groups = frames.get("line_groups", pd.DataFrame())

    if issue_id:
        if issue_row is None and not issues.empty:
            issue_matches = issues[issues["issue_id"].astype(str) == issue_id]
            if not issue_matches.empty:
                issue_row = issue_matches.iloc[0]
        if issue_row is None:
            raise FileNotFoundError(f"No issue found for issue_id={issue_id}")
        sheet_id = sheet_id or str(issue_row.get("sheet_id") or "")

    if not sheet_id:
        raise ValueError("sheet_id is required when issue_id is not provided.")

    page_row = _resolve_page_row(
        pages=pages,
        sheet_id=sheet_id,
        issue_row=issue_row,
        page_findings=latest.get("page_findings") or [],
    )
    highlight = _resolve_highlight(issue_row, line_groups, line_group_id=line_group_id)
    line_semantics = _resolve_line_semantics(issue_row, line_groups, line_group_id=line_group_id)

    page_extent = (
        _json_bbox(page_row.get("audit_area_bbox"))
        or _json_bbox(page_row.get("frame_bbox"))
        or _json_bbox(page_row.get("extent_bbox"))
        or _extent_from_highlight(highlight)
        or _extent_from_issue_evidence(issue_row)
    )

    preview_root = default_preview_cache_root() / project_id
    target_dir = (output_dir or preview_root).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    if page_extent is None:
        target_path = target_dir / f"{sheet_id}_{issue_id or 'sheet'}_summary.svg"
        svg_text = _build_unlocated_svg(
            page_row,
            issue_row=issue_row,
            line_semantics=line_semantics,
        )
        target_path.write_text(svg_text, encoding="utf-8")
        return {
            "project_id": project_id,
            "sheet_id": sheet_id,
            "issue_id": issue_id,
            "preview_path": str(target_path),
            "preview_svg": svg_text,
            "artifact_dir": artifact_raw,
            "focus_bbox": None,
            "cropped_to_issue": False,
            "source": "sqlite_summary",
            "lightweight": True,
        }

    sheet_lines = lines[lines["sheet_id"].astype(str) == sheet_id] if not lines.empty else pd.DataFrame()
    sheet_texts = texts[texts["sheet_id"].astype(str) == sheet_id] if not texts.empty else pd.DataFrame()
    if sheet_lines.empty and highlight is not None:
        sheet_lines = _synthetic_line_frame(highlight, sheet_id=sheet_id)
    if sheet_texts.empty and issue_row is not None:
        sheet_texts = _synthetic_text_frame(issue_row, sheet_id=sheet_id)

    focus_extent = _resolve_focus_extent(
        page_extent=page_extent,
        highlight=highlight,
        issue_row=issue_row,
        texts=sheet_texts,
    )
    visible_lines = _filter_lines_in_extent(sheet_lines, focus_extent)
    visible_texts = _filter_texts_in_extent(sheet_texts, focus_extent)
    if visible_lines.empty and highlight is not None:
        visible_lines = _synthetic_line_frame(highlight, sheet_id=sheet_id)

    crop_token = "issue" if highlight is not None else "sheet"
    target_path = target_dir / f"{sheet_id}_{issue_id or 'sheet'}_{crop_token}.svg"
    if len(visible_lines) > _MAX_PREVIEW_LINES:
        visible_lines = visible_lines.iloc[:_MAX_PREVIEW_LINES].copy()
    if len(visible_texts) > _MAX_PREVIEW_TEXTS:
        visible_texts = visible_texts.iloc[:_MAX_PREVIEW_TEXTS].copy()

    svg_text = _build_svg(
        page_row,
        visible_lines,
        visible_texts,
        focus_extent,
        highlight=highlight,
        issue_row=issue_row,
        line_semantics=line_semantics,
        cropped=highlight is not None,
    )
    target_path.write_text(svg_text, encoding="utf-8")

    return {
        "project_id": project_id,
        "sheet_id": sheet_id,
        "issue_id": issue_id,
        "preview_path": str(target_path),
        "preview_svg": svg_text,
        "artifact_dir": artifact_raw,
        "focus_bbox": list(focus_extent),
        "cropped_to_issue": highlight is not None,
        "source": "sqlite_evidence" if lightweight or not artifact_raw else "artifacts",
        "lightweight": lightweight,
    }


def _build_svg(
    page_row: pd.Series,
    lines: pd.DataFrame,
    texts: pd.DataFrame,
    extent: tuple[float, float, float, float],
    *,
    highlight: dict[str, Any] | None,
    issue_row: pd.Series | None,
    line_semantics: dict[str, str] | None,
    cropped: bool,
) -> str:
    transform = _make_view_transform(extent)
    tx = transform["tx"]
    ty = transform["ty"]
    scale = transform["scale"]

    def sx(x: float) -> float:
        return round(tx(x), 2)

    def sy(y: float) -> float:
        return round(ty(y), 2)

    # Coordinates are already projected to screen pixels.
    line_stroke = 1.4
    highlight_stroke = 3.2
    endpoint_r = 4.8

    svg_lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        (
            f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{_CANVAS_WIDTH}\" "
            f"height=\"{_CANVAS_HEIGHT}\" viewBox=\"0 0 {_CANVAS_WIDTH} {_CANVAS_HEIGHT}\">"
        ),
        (
            f"<metadata>view={'issue-crop' if cropped else 'full-sheet'};"
            f"sheet={html.escape(str(page_row.get('sheet_no') or ''))}</metadata>"
        ),
        "<rect width=\"100%\" height=\"100%\" fill=\"#fffdf8\" />",
        "<g id=\"page-lines\" stroke=\"#2b2b2b\" fill=\"none\">",
    ]

    for _, row in lines.iterrows():
        svg_lines.append(
            (
                f"<line x1=\"{sx(float(row['start_x']))}\" y1=\"{sy(float(row['start_y']))}\" "
                f"x2=\"{sx(float(row['end_x']))}\" y2=\"{sy(float(row['end_y']))}\" "
                f"stroke=\"#343434\" stroke-width=\"{round(line_stroke, 2)}\" />"
            )
        )
    svg_lines.append("</g>")

    if not texts.empty:
        svg_lines.append("<g id=\"page-texts\">")
        for _, row in texts.iterrows():
            text = html.escape(str(row.get("normalized_text") or row.get("text") or ""))
            if not text:
                continue
            is_numeric = bool(row.get("is_numeric_candidate"))
            fill = "#111111" if is_numeric else "#5b5b5b"
            opacity = "0.98" if is_numeric else "0.72"
            world_height = float(row.get("height") or 2.5)
            font_size = max(11.0, min(world_height * scale * 1.15, 28.0))
            if is_numeric:
                font_size = max(font_size, 13.0)
            svg_lines.append(
                (
                    f"<text x=\"{sx(float(row['insert_x']))}\" y=\"{sy(float(row['insert_y']))}\" "
                    f"font-size=\"{round(font_size, 2)}\" fill=\"{fill}\" opacity=\"{opacity}\" "
                    f"font-family=\"Consolas, 'Segoe UI', sans-serif\">{text}</text>"
                )
            )
        svg_lines.append("</g>")

    if highlight is not None:
        start = highlight["start"]
        end = highlight["end"]
        min_hx = min(start[0], end[0])
        max_hx = max(start[0], end[0])
        min_hy = min(start[1], end[1])
        max_hy = max(start[1], end[1])
        # Padding in world units, then projected to screen.
        world_pad = max(_extent_span(extent) * 0.04, 2.0)
        rect_x = sx(min_hx - world_pad)
        rect_y = sy(max_hy + world_pad)
        rect_w = round(abs(sx(max_hx + world_pad) - sx(min_hx - world_pad)), 2)
        rect_h = round(abs(sy(min_hy - world_pad) - sy(max_hy + world_pad)), 2)

        svg_lines.extend(
            [
                "<g id=\"issue-highlight\">",
                (
                    f"<rect x=\"{rect_x}\" y=\"{rect_y}\" width=\"{rect_w}\" height=\"{rect_h}\" "
                    f"fill=\"rgba(176, 45, 32, 0.08)\" stroke=\"#b02d20\" "
                    f"stroke-width=\"{round(highlight_stroke, 2)}\" />"
                ),
                (
                    f"<line x1=\"{sx(start[0])}\" y1=\"{sy(start[1])}\" x2=\"{sx(end[0])}\" y2=\"{sy(end[1])}\" "
                    f"stroke=\"#b02d20\" stroke-width=\"{round(highlight_stroke + 0.6, 2)}\" />"
                ),
                f"<circle cx=\"{sx(start[0])}\" cy=\"{sy(start[1])}\" r=\"{round(endpoint_r, 2)}\" fill=\"#b02d20\" />",
                f"<circle cx=\"{sx(end[0])}\" cy=\"{sy(end[1])}\" r=\"{round(endpoint_r, 2)}\" fill=\"#b02d20\" />",
            ]
        )
        if issue_row is not None:
            left_label = html.escape(str(issue_row.get("left_value") or "").strip())
            right_label = html.escape(str(issue_row.get("right_value") or "").strip())
            if left_label:
                svg_lines.append(
                    (
                        f"<text x=\"{sx(start[0]) + 8}\" y=\"{sy(start[1]) - 8}\" "
                        f"font-size=\"14\" fill=\"#8a1f16\" font-weight=\"700\" "
                        f"font-family=\"Segoe UI, sans-serif\">{left_label}</text>"
                    )
                )
            if right_label:
                svg_lines.append(
                    (
                        f"<text x=\"{sx(end[0]) + 8}\" y=\"{sy(end[1]) - 8}\" "
                        f"font-size=\"14\" fill=\"#8a1f16\" font-weight=\"700\" "
                        f"font-family=\"Segoe UI, sans-serif\">{right_label}</text>"
                    )
                )
        svg_lines.append("</g>")

    title = html.escape(str(page_row.get("sheet_title") or page_row.get("filename") or "图纸预览"))
    subtitle_parts: list[str] = []
    sheet_no = str(page_row.get("sheet_no") or "").strip()
    if sheet_no:
        subtitle_parts.append(f"图号 {sheet_no}")
    if cropped:
        subtitle_parts.append("问题区域")
    else:
        subtitle_parts.append("整图预览")
    if issue_row is not None:
        left_value = issue_row.get("left_value")
        right_value = issue_row.get("right_value")
        if left_value not in (None, "") or right_value not in (None, ""):
            subtitle_parts.append(f"端子 {left_value or '?'} → {right_value or '?'}")
        rule_label = _humanize_rule_id(str(issue_row.get("rule_id") or ""))
        if rule_label:
            subtitle_parts.append(rule_label)
    if line_semantics:
        orientation = _humanize_orientation(line_semantics.get("line_orientation"))
        if orientation:
            subtitle_parts.append(f"方向 {orientation}")
        left_side = line_semantics.get("left_side_label")
        right_side = line_semantics.get("right_side_label")
        if left_side or right_side:
            subtitle_parts.append(f"线端 {left_side or '?'} → {right_side or '?'}")
    subtitle = html.escape(" · ".join(subtitle_parts) if subtitle_parts else "问题定位预览")
    svg_lines.extend(
        [
            "<g id=\"header\">",
            (
                f"<rect x=\"0\" y=\"0\" width=\"{_CANVAS_WIDTH}\" height=\"{_HEADER_HEIGHT}\" "
                f"fill=\"rgba(247, 244, 238, 0.94)\" />"
            ),
            f"<text x=\"14\" y=\"22\" font-size=\"15\" fill=\"#1a1814\" font-family=\"Segoe UI, sans-serif\">{title}</text>",
            f"<text x=\"14\" y=\"40\" font-size=\"11\" fill=\"#6b6458\" font-family=\"Segoe UI, sans-serif\">{subtitle}</text>",
            "</g>",
            "</svg>",
        ]
    )
    return "\n".join(svg_lines) + "\n"


def _build_unlocated_svg(
    page_row: pd.Series,
    *,
    issue_row: pd.Series | None,
    line_semantics: dict[str, str] | None,
) -> str:
    title = html.escape(str(page_row.get("sheet_title") or page_row.get("filename") or "图纸预览"))
    filename = html.escape(str(page_row.get("filename") or "").strip())
    sheet_no = html.escape(str(page_row.get("sheet_no") or "").strip())
    issue_title = "问题定位摘要"
    pair_label = ""
    summary = "该问题没有可用坐标，无法在图上精确框选。请结合下方问题说明复核。"
    rule_label = ""
    if issue_row is not None:
        issue_title = html.escape(str(issue_row.get("title") or "问题定位摘要").strip())
        left_value = str(issue_row.get("left_value") or "").strip()
        right_value = str(issue_row.get("right_value") or "").strip()
        if left_value or right_value:
            pair_label = html.escape(f"端子 {left_value or '?'} → {right_value or '?'}")
        issue_summary = str(issue_row.get("summary") or "").strip()
        if issue_summary:
            summary = html.escape(issue_summary[:140])
        rule_label = html.escape(_humanize_rule_id(str(issue_row.get("rule_id") or "")))

    orientation = ""
    if line_semantics:
        orientation = _humanize_orientation(line_semantics.get("line_orientation"))
    subtitle_parts = [value for value in (f"图号 {sheet_no}" if sheet_no else "", filename, "无坐标定位") if value]
    detail_parts = [value for value in (pair_label, rule_label, f"方向 {html.escape(orientation)}" if orientation else "") if value]
    subtitle = " · ".join(subtitle_parts)
    detail = " · ".join(detail_parts) or "已保留关联图纸与问题文字"

    return "\n".join(
        [
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            (
                f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{_CANVAS_WIDTH}\" "
                f"height=\"{_CANVAS_HEIGHT}\" viewBox=\"0 0 {_CANVAS_WIDTH} {_CANVAS_HEIGHT}\">"
            ),
            f"<metadata>view=unlocated-summary;sheet={sheet_no}</metadata>",
            "<rect width=\"100%\" height=\"100%\" fill=\"#fffdf8\" />",
            "<rect x=\"0\" y=\"0\" width=\"960\" height=\"58\" fill=\"#f7f4ee\" />",
            f"<text x=\"18\" y=\"25\" font-size=\"16\" fill=\"#1a1814\" font-family=\"Microsoft YaHei, Segoe UI, sans-serif\">{title}</text>",
            f"<text x=\"18\" y=\"46\" font-size=\"12\" fill=\"#6b6458\" font-family=\"Microsoft YaHei, Segoe UI, sans-serif\">{subtitle}</text>",
            "<rect x=\"150\" y=\"120\" width=\"660\" height=\"300\" rx=\"14\" fill=\"#fbf5e7\" stroke=\"#d8c58f\" stroke-width=\"2\" />",
            "<circle cx=\"210\" cy=\"180\" r=\"24\" fill=\"#f0d992\" />",
            "<text x=\"202\" y=\"190\" font-size=\"28\" fill=\"#745716\" font-family=\"Segoe UI, sans-serif\">i</text>",
            f"<text x=\"255\" y=\"178\" font-size=\"22\" font-weight=\"700\" fill=\"#2b261d\" font-family=\"Microsoft YaHei, Segoe UI, sans-serif\">{issue_title}</text>",
            f"<text x=\"190\" y=\"245\" font-size=\"17\" fill=\"#433b2d\" font-family=\"Microsoft YaHei, Segoe UI, sans-serif\">{detail}</text>",
            f"<text x=\"190\" y=\"302\" font-size=\"15\" fill=\"#6b6458\" font-family=\"Microsoft YaHei, Segoe UI, sans-serif\">{summary}</text>",
            "<text x=\"190\" y=\"362\" font-size=\"14\" fill=\"#8a6b20\" font-family=\"Microsoft YaHei, Segoe UI, sans-serif\">无坐标定位：未在图中绘制虚构框选，请结合文字说明人工复核。</text>",
            "</svg>",
            "",
        ]
    )


def _make_view_transform(extent: tuple[float, float, float, float]) -> dict[str, Any]:
    min_x, min_y, max_x, max_y = extent
    width = max(max_x - min_x, 1e-6)
    height = max(max_y - min_y, 1e-6)
    avail_w = _CANVAS_WIDTH - (_EDGE_PAD * 2.0)
    avail_h = _CANVAS_HEIGHT - _HEADER_HEIGHT - (_EDGE_PAD * 2.0)
    scale = min(avail_w / width, avail_h / height)
    content_w = width * scale
    content_h = height * scale
    origin_x = (_CANVAS_WIDTH - content_w) / 2.0
    origin_y = _HEADER_HEIGHT + ((_CANVAS_HEIGHT - _HEADER_HEIGHT - content_h) / 2.0)

    def tx(x: float) -> float:
        return origin_x + ((x - min_x) * scale)

    def ty(y: float) -> float:
        # CAD Y-up -> SVG Y-down
        return origin_y + ((max_y - y) * scale)

    return {"tx": tx, "ty": ty, "scale": scale}


def _resolve_focus_extent(
    *,
    page_extent: tuple[float, float, float, float],
    highlight: dict[str, Any] | None,
    issue_row: pd.Series | None,
    texts: pd.DataFrame,
) -> tuple[float, float, float, float]:
    """Prefer a tight crop around the issue geometry instead of the full sheet."""
    if highlight is None:
        return page_extent

    start = highlight["start"]
    end = highlight["end"]
    points: list[tuple[float, float]] = [start, end]

    evidence = _decode_jsonish(issue_row.get("evidence")) if issue_row is not None else None
    if isinstance(evidence, dict):
        for key in ("left_point", "right_point", "left_insert", "right_insert"):
            point = evidence.get(key)
            if _is_point_pair(point):
                points.append((float(point[0]), float(point[1])))
        for key in ("candidate_points", "related_points"):
            values = evidence.get(key)
            if isinstance(values, list):
                for item in values:
                    if _is_point_pair(item):
                        points.append((float(item[0]), float(item[1])))

    values: set[str] = set()
    if issue_row is not None:
        for key in ("left_value", "right_value"):
            value = issue_row.get(key)
            if value not in (None, ""):
                values.add(str(value).strip())
        decoded_values = _decode_jsonish(issue_row.get("values"))
        if isinstance(decoded_values, list):
            values.update(str(item).strip() for item in decoded_values if item not in (None, ""))

    if values and not texts.empty:
        for _, row in texts.iterrows():
            label = str(row.get("normalized_text") or row.get("text") or "").strip()
            if label in values:
                points.append((float(row["insert_x"]), float(row["insert_y"])))

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    page_span = _extent_span(page_extent)
    # Keep enough context around the wire/terminals without falling back to full sheet.
    pad = max(span_x, span_y) * 0.55
    pad = max(pad, page_span * 0.03, 12.0)
    pad = min(pad, page_span * 0.25)

    crop = (
        min_x - pad,
        min_y - pad,
        max_x + pad,
        max_y + pad,
    )
    return _clamp_extent(crop, page_extent)


def _filter_lines_in_extent(lines: pd.DataFrame, extent: tuple[float, float, float, float]) -> pd.DataFrame:
    if lines.empty:
        return lines
    min_x, min_y, max_x, max_y = extent

    def keep(row: pd.Series) -> bool:
        x1, y1 = float(row["start_x"]), float(row["start_y"])
        x2, y2 = float(row["end_x"]), float(row["end_y"])
        return _segment_intersects_bbox(x1, y1, x2, y2, min_x, min_y, max_x, max_y)

    mask = lines.apply(keep, axis=1)
    filtered = lines[mask]
    return filtered if not filtered.empty else lines.head(0)


def _filter_texts_in_extent(texts: pd.DataFrame, extent: tuple[float, float, float, float]) -> pd.DataFrame:
    if texts.empty:
        return texts
    min_x, min_y, max_x, max_y = extent
    xs = texts["insert_x"].astype(float)
    ys = texts["insert_y"].astype(float)
    mask = (xs >= min_x) & (xs <= max_x) & (ys >= min_y) & (ys <= max_y)
    filtered = texts[mask]
    return filtered if not filtered.empty else texts.head(0)


def _segment_intersects_bbox(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
) -> bool:
    if _point_in_bbox(x1, y1, min_x, min_y, max_x, max_y) or _point_in_bbox(x2, y2, min_x, min_y, max_x, max_y):
        return True
    # Reject if both ends are fully on one outside side.
    if max(x1, x2) < min_x or min(x1, x2) > max_x or max(y1, y2) < min_y or min(y1, y2) > max_y:
        return False
    # Conservative accept for segments crossing the crop window.
    return True


def _point_in_bbox(x: float, y: float, min_x: float, min_y: float, max_x: float, max_y: float) -> bool:
    return min_x <= x <= max_x and min_y <= y <= max_y


def _clamp_extent(
    crop: tuple[float, float, float, float],
    page_extent: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    page_min_x, page_min_y, page_max_x, page_max_y = page_extent
    min_x, min_y, max_x, max_y = crop
    return (
        max(min_x, page_min_x),
        max(min_y, page_min_y),
        min(max_x, page_max_x),
        min(max_y, page_max_y),
    )


def _extent_span(extent: tuple[float, float, float, float]) -> float:
    min_x, min_y, max_x, max_y = extent
    return max(max_x - min_x, max_y - min_y, 1.0)


def _issue_has_geometry_evidence(issue_row: pd.Series | None) -> bool:
    if issue_row is None:
        return False
    evidence = _decode_jsonish(issue_row.get("evidence"))
    if not isinstance(evidence, dict):
        return False
    return _is_point_pair(evidence.get("line_start")) and _is_point_pair(evidence.get("line_end"))


def _issue_row_from_sqlite(issues: list[dict[str, Any]], issue_id: str) -> pd.Series | None:
    for item in issues:
        if str(item.get("issue_id") or "") == issue_id:
            return pd.Series(item)
    return None


def _resolve_page_row(
    *,
    pages: pd.DataFrame,
    sheet_id: str,
    issue_row: pd.Series | None,
    page_findings: list[dict[str, Any]],
) -> pd.Series:
    if not pages.empty:
        matches = pages[pages["sheet_id"].astype(str) == sheet_id]
        if not matches.empty:
            return matches.iloc[0]

    for page in page_findings:
        if str(page.get("sheet_id") or "") == sheet_id:
            return pd.Series(
                {
                    "sheet_id": sheet_id,
                    "sheet_no": page.get("sheet_no") or "",
                    "sheet_title": page.get("sheet_title") or page.get("filename") or sheet_id,
                    "filename": page.get("filename") or "",
                    "extent_bbox": None,
                    "frame_bbox": None,
                    "audit_area_bbox": None,
                }
            )

    filename = ""
    sheet_no = ""
    sheet_title = sheet_id
    if issue_row is not None:
        filename = str(issue_row.get("filename") or "")
        sheet_no = str(issue_row.get("sheet_no") or "")
        sheet_title = filename or sheet_id
    return pd.Series(
        {
            "sheet_id": sheet_id,
            "sheet_no": sheet_no,
            "sheet_title": sheet_title,
            "filename": filename,
            "extent_bbox": None,
            "frame_bbox": None,
            "audit_area_bbox": None,
        }
    )


def _extent_from_highlight(highlight: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    if highlight is None:
        return None
    start = highlight["start"]
    end = highlight["end"]
    min_x = min(start[0], end[0])
    max_x = max(start[0], end[0])
    min_y = min(start[1], end[1])
    max_y = max(start[1], end[1])
    pad = max(max(max_x - min_x, max_y - min_y) * 0.8, 20.0)
    return (min_x - pad, min_y - pad, max_x + pad, max_y + pad)


def _extent_from_issue_evidence(issue_row: pd.Series | None) -> tuple[float, float, float, float] | None:
    if issue_row is None:
        return None
    evidence = _decode_jsonish(issue_row.get("evidence"))
    if not isinstance(evidence, dict):
        return None
    line_start = evidence.get("line_start")
    line_end = evidence.get("line_end")
    if _is_point_pair(line_start) and _is_point_pair(line_end):
        return _extent_from_highlight(
            {
                "start": (float(line_start[0]), float(line_start[1])),
                "end": (float(line_end[0]), float(line_end[1])),
            }
        )
    return None


def _synthetic_line_frame(highlight: dict[str, Any], *, sheet_id: str) -> pd.DataFrame:
    start = highlight["start"]
    end = highlight["end"]
    return pd.DataFrame(
        [
            {
                "line_id": "synthetic-issue-line",
                "sheet_id": sheet_id,
                "start_x": float(start[0]),
                "start_y": float(start[1]),
                "end_x": float(end[0]),
                "end_y": float(end[1]),
            }
        ]
    )


def _synthetic_text_frame(issue_row: pd.Series, *, sheet_id: str) -> pd.DataFrame:
    evidence = _decode_jsonish(issue_row.get("evidence"))
    rows: list[dict[str, Any]] = []
    if isinstance(evidence, dict):
        line_start = evidence.get("line_start")
        line_end = evidence.get("line_end")
        left_value = issue_row.get("left_value")
        right_value = issue_row.get("right_value")
        if _is_point_pair(line_start) and left_value not in (None, ""):
            rows.append(
                {
                    "text_id": "synthetic-left",
                    "sheet_id": sheet_id,
                    "text": str(left_value),
                    "normalized_text": str(left_value),
                    "is_numeric_candidate": True,
                    "height": 2.5,
                    "insert_x": float(line_start[0]),
                    "insert_y": float(line_start[1]) + 4.0,
                }
            )
        if _is_point_pair(line_end) and right_value not in (None, ""):
            rows.append(
                {
                    "text_id": "synthetic-right",
                    "sheet_id": sheet_id,
                    "text": str(right_value),
                    "normalized_text": str(right_value),
                    "is_numeric_candidate": True,
                    "height": 2.5,
                    "insert_x": float(line_end[0]),
                    "insert_y": float(line_end[1]) + 4.0,
                }
            )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _resolve_highlight(
    issue_row: pd.Series | None,
    line_groups: pd.DataFrame,
    *,
    line_group_id: str | None = None,
) -> dict[str, Any] | None:
    if line_group_id and not line_groups.empty:
        matches = line_groups[line_groups["line_group_id"].astype(str) == line_group_id]
        if not matches.empty:
            row = matches.iloc[0]
            return {
                "start": (float(row["start_x"]), float(row["start_y"])),
                "end": (float(row["end_x"]), float(row["end_y"])),
            }
    if issue_row is None:
        return None
    evidence = _decode_jsonish(issue_row.get("evidence"))
    if isinstance(evidence, dict):
        line_start = evidence.get("line_start")
        line_end = evidence.get("line_end")
        if _is_point_pair(line_start) and _is_point_pair(line_end):
            return {
                "start": (float(line_start[0]), float(line_start[1])),
                "end": (float(line_end[0]), float(line_end[1])),
            }
    line_group_id = str(issue_row.get("line_group_id") or "")
    if line_group_id and not line_groups.empty:
        matches = line_groups[line_groups["line_group_id"].astype(str) == line_group_id]
        if not matches.empty:
            row = matches.iloc[0]
            return {
                "start": (float(row["start_x"]), float(row["start_y"])),
                "end": (float(row["end_x"]), float(row["end_y"])),
            }
    return None


def _resolve_line_semantics(
    issue_row: pd.Series | None,
    line_groups: pd.DataFrame,
    *,
    line_group_id: str | None = None,
) -> dict[str, str] | None:
    semantics: dict[str, str] = {}
    if issue_row is not None:
        evidence = _decode_jsonish(issue_row.get("evidence"))
        if isinstance(evidence, dict):
            pair_evidence = evidence.get("pair_evidence")
            source = pair_evidence if isinstance(pair_evidence, dict) else evidence
            for key in ("line_orientation", "left_side_label", "right_side_label"):
                value = source.get(key)
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    semantics[key] = text
    lookup_line_group_id = line_group_id
    if not lookup_line_group_id and issue_row is not None:
        lookup_line_group_id = str(issue_row.get("line_group_id") or "")
    if lookup_line_group_id and not line_groups.empty:
        matches = line_groups[line_groups["line_group_id"].astype(str) == lookup_line_group_id]
        if not matches.empty and "orientation" in matches.columns and "line_orientation" not in semantics:
            orientation = str(matches.iloc[0].get("orientation") or "").strip()
            if orientation:
                semantics["line_orientation"] = orientation
    return semantics or None


def _is_point_pair(value: object) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2


def _decode_jsonish(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        try:
            return _normalize_jsonish(json.loads(value))
        except json.JSONDecodeError:
            return value
    return _normalize_jsonish(value)


def _normalize_jsonish(value: Any) -> Any:
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, bytearray)):
        value = value.tolist()
    if isinstance(value, dict):
        return {str(key): _normalize_jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_jsonish(item) for item in value]
    return value


def _json_bbox(value: object) -> tuple[float, float, float, float] | None:
    decoded = _decode_jsonish(value)
    if not isinstance(decoded, (list, tuple)) or len(decoded) != 4:
        return None
    try:
        return tuple(float(item) for item in decoded)
    except (TypeError, ValueError):
        return None


def _humanize_rule_id(rule_id: str) -> str:
    mapping = {
        "R-CROSS-PAGE-CONFLICT": "跨页端子冲突",
        "R-ONE-TO-MANY": "一对多连接",
        "R-MANY-TO-ONE": "多对一连接",
        "R-MISSING-RECIPROCAL": "缺少对端回指",
        "R-PAIR-MISSING-SIDE": "端子缺侧",
        "R-PAIR-LOW-CONFIDENCE": "端子配对不确定",
        "R-DUPLICATE-SAME-LINE": "同线重复端子",
        "R-SHEET-PAGE-MISMATCH": "页码不一致",
    }
    text = str(rule_id or "").strip()
    if not text:
        return ""
    return mapping.get(text, "")


def _humanize_orientation(value: object) -> str:
    mapping = {
        "horizontal": "水平",
        "vertical": "垂直",
        "diagonal": "斜向",
        "unknown": "未知",
    }
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return mapping.get(text, text)
