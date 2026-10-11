"""Two-panel close-ups of one cross-page record: the terminal-strip page (left) and the target page (right).

Reuses the drawing helpers of round4/I/round4_samples_v2.py (read-only import). Marks: red = strip row
identity and destination text(s); blue = target port and its wire contact.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path("F:/workspace/XJToolkit")
_SPEC = importlib.util.spec_from_file_location("r4", str(ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"))
r4 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(r4)

_CACHE = None


def _cache():
    global _CACHE
    if _CACHE is None:
        _CACHE = r4.DxfCache()
    return _CACHE


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def draw_record(path: Path, project_id: str, record: dict, data: dict, dxf_map: dict, klass: str) -> dict:
    strip_id = record["strip_record_id"]
    strip_file = record["strip_file_id"]
    target_port = record["target_port_id"]
    target_file = record["target_file_id"]
    row_x, row_y = data["strip_xy"][strip_id]["row"]
    potentials = data["strip_xy"][strip_id]["potentials"]
    tx, ty, contacts = data["port_xy"][target_port]
    strip_info = data["page_info"].get(strip_file, {})
    target_info = data["page_info"].get(target_file, {})
    strip_points = [(row_x, row_y, "red")] + [(x, y, "red") for x, y in potentials if _num(x) is not None]
    target_points = [(tx, ty, "blue")] + [(c.get("x"), c.get("y"), "blue") for c in contacts
                                          if _num(c.get("x")) is not None and _num(c.get("y")) is not None]
    half_w, half_h = 16.0, 10.0
    strip_center = (float(row_x), float(row_y)) if _num(row_x) is not None else (tx, ty)
    title_strip = [
        f"[{klass}] {project_id} 端子排页（红） {strip_info.get('sheet_no')} {strip_info.get('filename')}",
        f"行身份 {record['strip_identity']}  行句柄 {strip_id}  去向句柄 {record['ref_handle']}:{record['ref_port_number']} 页 {record['ref_page_no']}",
        f"行连接远端值 {', '.join(record.get('far_values') or []) or '无'}  支撑配对 {', '.join(record.get('supporting_pair_ids') or []) or '无'}",
    ]
    consumers = record.get("consumer_pair_ids") or []
    title_target = [
        f"目标页（蓝） {target_info.get('sheet_no')} {target_info.get('filename')}  端口 {target_port}",
        f"目标身份 {record['target_identity']}  类别/有导线 {record['target_wire_contact']}",
        (f"目标已被配对 {', '.join(consumers)}，另一端 {', '.join(record.get('consumer_other_values') or [])}"
         if consumers else "目标未被任何非 discard 配对消费"),
        f"关系 {record.get('relation') or ''} 候选 {record.get('candidate') or '无'} 覆盖 {record.get('covers_target', False)}",
    ]
    r4_panels = [
        r4.Panel(title_strip, dxf_path=dxf_map.get((project_id, strip_file)),
                 window=(strip_center[0] - half_w, strip_center[1] - half_h, strip_center[0] + half_w, strip_center[1] + half_h),
                 points=strip_points),
        r4.Panel(title_target, dxf_path=dxf_map.get((project_id, target_file)),
                 window=(tx - half_w, ty - half_h, tx + half_w, ty + half_h), points=target_points),
    ]
    header = [f"XPAGE 样例 {klass}  项目 {project_id}  关系 {record.get('relation') or '-'}  "
              f"候选 {record.get('candidate') or '-'}  覆盖 {record.get('covers_target', False)}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    r4._render_issue_png(path, header, r4_panels, _cache())
    return {"file": str(path), "class": klass, "project_id": project_id, "link_id": record.get("link_id"),
            "strip_record_id": strip_id, "strip_identity": record["strip_identity"],
            "far_values": record.get("far_values"), "target_port_id": target_port,
            "target_identity": record["target_identity"], "relation": record.get("relation"),
            "candidate": record.get("candidate"), "covers_target": record.get("covers_target", False),
            "consumer_pair_ids": consumers, "consumer_other_values": record.get("consumer_other_values")}
