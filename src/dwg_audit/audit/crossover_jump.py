"""Human-certified, name-independent wire crossover jump recognition.

This is deliberately a topology semantic, rather than a symbol/port proposal.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Iterable


FAMILY = "wire.crossover_jump.v1"
CERTIFIED_FINGERPRINT = "f9d454c009fff6e62f248535070beb3ce1787db373d260f7159948192c492bb8"


@dataclass(frozen=True)
class CrossoverJump:
    family: str
    sheet_id: str | None
    parent_handle: str | None
    nested_path: str | None
    line_ids: tuple[str, str]
    arc_id: str
    union_pairs: tuple[tuple[str, str], ...]
    no_junction: bool
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"family": self.family, "sheet_id": self.sheet_id,
                "parent_handle": self.parent_handle, "nested_path": self.nested_path,
                "line_ids": list(self.line_ids),
                "arc_id": self.arc_id, "union_pairs": [list(p) for p in self.union_pairs],
                "no_junction": self.no_junction, "provenance": self.provenance}


def _field(item: Any, name: str, default: Any = None) -> Any:
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def _geom(item: Any, local: bool = True) -> dict[str, Any]:
    value = _field(item, "local_geometry_json" if local else "world_geometry_json")
    if value is None:
        value = (_field(item, "local_geometry" if local else "world_geometry")
                 or _field(item, "geometry"))
    if isinstance(value, str):
        value = json.loads(value)
    return value or {}


def _id(item: Any) -> str:
    return str(_field(item, "primitive_id") or _field(item, "entity_handle") or "")


def _kind(item: Any) -> str:
    return str(_field(item, "primitive_kind") or "").upper()


def _points(g: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]]:
    return tuple(tuple(float(v) for v in g[k][:2]) for k in ("start", "end"))  # type: ignore[return-value]


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def recognize_crossover_jumps(segments: Iterable[Any], *, tolerance: float = 1e-6) -> list[CrossoverJump]:
    """Recognize LINE-ARC-LINE block-local jumps; fingerprint is never required."""
    groups: dict[tuple[Any, ...], list[Any]] = {}
    for item in segments:
        if _kind(item) not in {"LINE", "ARC"}:
            continue
        nested_path = _field(item, "nested_path")
        key = (
            _field(item, "sheet_id"),
            _field(item, "definition_name"),
            _field(item, "parent_handle"),
            nested_path.rsplit("/", 1)[0] if nested_path else None,
        )
        groups.setdefault(key, []).append(item)
    found: list[CrossoverJump] = []
    for members in groups.values():
        arcs = [x for x in members if _kind(x) == "ARC"]
        lines = [x for x in members if _kind(x) == "LINE"]
        for arc in arcs:
            ag = _geom(arc)
            if not {"center", "radius", "start_angle", "end_angle"} <= ag.keys():
                continue
            sweep = abs(float(ag["end_angle"]) - float(ag["start_angle"])) % 360.0
            if abs(sweep - 180.0) > 1e-4 or float(ag["radius"]) <= tolerance:
                continue
            center = tuple(float(v) for v in ag["center"][:2]); r = float(ag["radius"])
            effective_tolerance = max(tolerance, r * 1e-5)
            ends = _points(ag) if "start" in ag and "end" in ag else tuple((center[0] + r * math.cos(math.radians(a)), center[1] + r * math.sin(math.radians(a))) for a in (float(ag["start_angle"]), float(ag["end_angle"])))
            for left in lines:
                lp = _points(_geom(left))
                for right in lines:
                    if left is right: continue
                    rp = _points(_geom(right))
                    # Both leads must lie on the chord and point away from the arc.
                    vx, vy = ends[1][0]-ends[0][0], ends[1][1]-ends[0][1]
                    def on_chord(p): return abs((p[0]-ends[0][0])*vy-(p[1]-ends[0][1])*vx) <= effective_tolerance
                    matches = []
                    for eleft, eright in (ends, (ends[1], ends[0])):
                        for lnear, lfar in ((lp[0], lp[1]), (lp[1], lp[0])):
                            for rnear, rfar in ((rp[0], rp[1]), (rp[1], rp[0])):
                                left_outward = ((lfar[0] - lnear[0]) * (eright[0] - eleft[0])
                                                + (lfar[1] - lnear[1]) * (eright[1] - eleft[1]))
                                right_outward = ((rfar[0] - rnear[0]) * (eleft[0] - eright[0])
                                                 + (rfar[1] - rnear[1]) * (eleft[1] - eright[1]))
                                if (_dist(lnear, eleft) <= effective_tolerance and _dist(rnear, eright) <= effective_tolerance
                                        and on_chord(lfar) and on_chord(rfar)
                                        and _dist(lfar, eleft) > effective_tolerance
                                        and _dist(rfar, eright) > effective_tolerance
                                        and left_outward < -effective_tolerance
                                        and right_outward < -effective_tolerance):
                                    matches.append(True)
                    if not matches: continue
                    sheet_id = _field(arc, "sheet_id")
                    parent_handle = _field(arc, "parent_handle")
                    nested_path = _field(arc, "nested_path")
                    prov = {
                        "arc_id": _id(arc),
                        "line_ids": [_id(left), _id(right)],
                        "definition_name": _field(arc, "definition_name"),
                        "parent_handle": parent_handle,
                        "nested_path": nested_path,
                        "source_handles": [_field(x, "entity_handle", _id(x)) for x in (left, arc, right)],
                    }
                    found.append(CrossoverJump(
                        FAMILY, sheet_id, parent_handle, nested_path,
                        (_id(left), _id(right)), _id(arc),
                        ((_id(left), _id(arc)), (_id(arc), _id(right))), True, prov,
                    ))
                    break
                else: continue
                break
    return found


__all__ = ["CrossoverJump", "FAMILY", "CERTIFIED_FINGERPRINT", "recognize_crossover_jumps"]
