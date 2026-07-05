from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.desktop.state_store import default_state_db_path
from dwg_audit.report import load_report_frames


def render_project_preview(
    *,
    project_id: str,
    sheet_id: str | None = None,
    issue_id: str | None = None,
    output_dir: Path | None = None,
    state_db_path: Path | None = None,
) -> dict[str, Any]:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    latest = store.load_latest_project_result(project_id)
    if latest is None:
        raise FileNotFoundError(f"No stored result found for project_id={project_id}")

    artifact_dir = Path(latest["run"]["artifact_dir"])
    frames = load_report_frames(artifact_dir)
    issues = frames.get("issues", pd.DataFrame())
    pages = frames.get("pages", pd.DataFrame())
    lines = frames.get("lines", pd.DataFrame())
    texts = frames.get("texts", pd.DataFrame())
    line_groups = frames.get("line_groups", pd.DataFrame())

    issue_row: pd.Series | None = None
    if issue_id:
        issue_matches = issues[issues["issue_id"].astype(str) == issue_id] if not issues.empty else pd.DataFrame()
        if issue_matches.empty:
            raise FileNotFoundError(f"No issue found for issue_id={issue_id}")
        issue_row = issue_matches.iloc[0]
        sheet_id = sheet_id or str(issue_row.get("sheet_id") or "")

    if not sheet_id:
        raise ValueError("sheet_id is required when issue_id is not provided.")

    page_matches = pages[pages["sheet_id"].astype(str) == sheet_id] if not pages.empty else pd.DataFrame()
    if page_matches.empty:
        raise FileNotFoundError(f"No page found for sheet_id={sheet_id}")
    page_row = page_matches.iloc[0]

    extent = (
        _json_bbox(page_row.get("audit_area_bbox"))
        or _json_bbox(page_row.get("frame_bbox"))
        or _json_bbox(page_row.get("extent_bbox"))
    )
    if extent is None:
        raise ValueError(f"Page {sheet_id} does not have a usable extent bbox.")

    sheet_lines = lines[lines["sheet_id"].astype(str) == sheet_id] if not lines.empty else pd.DataFrame()
    sheet_texts = texts[texts["sheet_id"].astype(str) == sheet_id] if not texts.empty else pd.DataFrame()
    highlight = _resolve_highlight(issue_row, line_groups)

    target_dir = (output_dir or artifact_dir / "cache" / "previews").expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{sheet_id}_{issue_id or 'sheet'}.svg"
    target_path.write_text(
        _build_svg(page_row, sheet_lines, sheet_texts, extent, highlight=highlight, issue_row=issue_row),
        encoding="utf-8",
    )

    return {
        "project_id": project_id,
        "sheet_id": sheet_id,
        "issue_id": issue_id,
        "preview_path": str(target_path),
        "artifact_dir": str(artifact_dir),
    }


def _build_svg(
    page_row: pd.Series,
    lines: pd.DataFrame,
    texts: pd.DataFrame,
    extent: tuple[float, float, float, float],
    *,
    highlight: dict[str, Any] | None,
    issue_row: pd.Series | None,
) -> str:
    min_x, min_y, max_x, max_y = extent
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    pad = max(width, height) * 0.02
    canvas_width = width + (pad * 2.0)
    canvas_height = height + (pad * 2.0)

    def tx(x: float) -> float:
        return round((x - min_x) + pad, 2)

    def ty(y: float) -> float:
        return round((max_y - y) + pad, 2)

    svg_lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        (
            f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{round(canvas_width, 2)}\" "
            f"height=\"{round(canvas_height, 2)}\" viewBox=\"0 0 {round(canvas_width, 2)} {round(canvas_height, 2)}\">"
        ),
        "<rect width=\"100%\" height=\"100%\" fill=\"#fffdf8\" />",
        "<g id=\"page-lines\" stroke=\"#2b2b2b\" stroke-width=\"1\" fill=\"none\">",
    ]

    for _, row in lines.iterrows():
        svg_lines.append(
            (
                f"<line x1=\"{tx(float(row['start_x']))}\" y1=\"{ty(float(row['start_y']))}\" "
                f"x2=\"{tx(float(row['end_x']))}\" y2=\"{ty(float(row['end_y']))}\" "
                f"stroke=\"#343434\" stroke-width=\"0.9\" />"
            )
        )
    svg_lines.append("</g>")

    if not texts.empty:
        svg_lines.append("<g id=\"page-texts\">")
        for _, row in texts.iterrows():
            text = html.escape(str(row.get("normalized_text") or row.get("text") or ""))
            if not text:
                continue
            fill = "#111111" if bool(row.get("is_numeric_candidate")) else "#5b5b5b"
            opacity = "0.95" if bool(row.get("is_numeric_candidate")) else "0.55"
            font_size = max(6.0, min(float(row.get("height") or 2.5) * 3.0, 16.0))
            svg_lines.append(
                (
                    f"<text x=\"{tx(float(row['insert_x']))}\" y=\"{ty(float(row['insert_y']))}\" "
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
        rect_pad = max(width, height) * 0.01
        rect_x = tx(min_hx - rect_pad)
        rect_y = ty(max_hy + rect_pad)
        rect_w = round((max_hx - min_hx) + (rect_pad * 2.0), 2)
        rect_h = round((max_hy - min_hy) + (rect_pad * 2.0), 2)

        svg_lines.extend(
            [
                "<g id=\"issue-highlight\">",
                (
                    f"<rect x=\"{rect_x}\" y=\"{rect_y}\" width=\"{rect_w}\" height=\"{rect_h}\" "
                    f"fill=\"rgba(255,0,0,0.04)\" stroke=\"#d11f1f\" stroke-width=\"2.2\" />"
                ),
                (
                    f"<line x1=\"{tx(start[0])}\" y1=\"{ty(start[1])}\" x2=\"{tx(end[0])}\" y2=\"{ty(end[1])}\" "
                    f"stroke=\"#d11f1f\" stroke-width=\"2.8\" />"
                ),
                f"<circle cx=\"{tx(start[0])}\" cy=\"{ty(start[1])}\" r=\"3.4\" fill=\"#d11f1f\" />",
                f"<circle cx=\"{tx(end[0])}\" cy=\"{ty(end[1])}\" r=\"3.4\" fill=\"#d11f1f\" />",
                "</g>",
            ]
        )

    title = html.escape(str(page_row.get("sheet_title") or page_row.get("filename") or ""))
    subtitle_parts = [f"sheet={page_row.get('sheet_no') or page_row.get('sheet_id')}"]
    if issue_row is not None:
        subtitle_parts.append(f"issue={issue_row.get('issue_id')}")
        subtitle_parts.append(f"rule={issue_row.get('rule_id')}")
    subtitle = html.escape(" | ".join(subtitle_parts))
    svg_lines.extend(
        [
            "<g id=\"header\">",
            f"<text x=\"12\" y=\"24\" font-size=\"18\" fill=\"#101010\" font-family=\"Segoe UI, sans-serif\">{title}</text>",
            f"<text x=\"12\" y=\"44\" font-size=\"12\" fill=\"#666666\" font-family=\"Segoe UI, sans-serif\">{subtitle}</text>",
            "</g>",
            "</svg>",
        ]
    )
    return "\n".join(svg_lines) + "\n"


def _resolve_highlight(issue_row: pd.Series | None, line_groups: pd.DataFrame) -> dict[str, Any] | None:
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


def _is_point_pair(value: object) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2


def _decode_jsonish(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _json_bbox(value: object) -> tuple[float, float, float, float] | None:
    decoded = _decode_jsonish(value)
    if not isinstance(decoded, (list, tuple)) or len(decoded) != 4:
        return None
    try:
        return tuple(float(item) for item in decoded)
    except (TypeError, ValueError):
        return None
