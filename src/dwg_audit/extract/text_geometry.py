from __future__ import annotations

import math
from typing import Any

from ezdxf.disassemble import make_primitive
from ezdxf.entities.dxfgfx import get_font_name
from ezdxf.fonts import fonts
from ezdxf.tools.text import text_wrap


def cad_text_geometry(entity: Any) -> dict[str, Any]:
    """Keep the oriented CAD layout rectangle, separately from insertion.

    ezdxf applies alignment, font metrics, width and OCS here. This is a layout
    estimate, not a claim of exact glyph outlines or full MTEXT formatting.
    """
    try:
        layout = entity
        line_metrics = {}
        if entity.dxftype() == "MTEXT" and entity.columns is None:
            font = fonts.make_font(get_font_name(entity), entity.dxf.char_height, 1.0)
            box_width = entity.dxf.get("width", 0.0)
            content = entity.plain_text()
            if not content.strip():
                return {}
            lines = [line for paragraph in content.split("\n")
                     for line in (text_wrap(paragraph, box_width if box_width > 0 else None, font.text_width) or [""])]
            if not lines:
                return {}
            widths = [font.text_width(line) for line in lines]
            line_height = font.measurements.total_height
            spacing = font.measurements.cap_height * entity.dxf.line_spacing_factor * 1.67
            # ezdxf's rough primitive treats a zero-width column as wrapping at
            # each word. Zero means unbounded in CAD. Supply the correctly
            # measured rectangle to its existing alignment/rotation machinery.
            layout = entity.copy()
            if not entity.dxf.hasattr("rect_width"):
                layout.dxf.rect_width = box_width if box_width > 0 else max(widths)
            if not entity.dxf.hasattr("rect_height"):
                layout.dxf.rect_height = line_height + spacing*(len(lines)-1)
            line_metrics = {"lines": lines, "line_widths": widths,
                            "line_height": line_height, "line_spacing": spacing}
        vertices = list(make_primitive(layout).vertices())[:4]
        if len(vertices) != 4:
            return {}
        if entity.dxftype() == "MTEXT":
            top_left, top_right, _, bottom_left = vertices
            content = entity.plain_text()
        else:
            bottom_left, _, top_right, top_left = vertices
            content = entity.dxf.text
        width = (top_right - top_left).magnitude
        height = (bottom_left - top_left).magnitude
        if width <= 0 or height <= 0:
            return {}
        return {
            "corners": [[p.x, p.y] for p in vertices],
            "top_left": [top_left.x, top_left.y],
            "axis_x": [(top_right.x-top_left.x)/width, (top_right.y-top_left.y)/width],
            "axis_down": [(bottom_left.x-top_left.x)/height, (bottom_left.y-top_left.y)/height],
            "width": width, "height": height,
            "rotation_deg": math.degrees(math.atan2(top_right.y-top_left.y, top_right.x-top_left.x)),
            "attachment_point": getattr(entity.dxf, "attachment_point", None),
            "lines": content.splitlines(), "accuracy": "cad_layout_estimate",
            **line_metrics,
        }
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        return {}
