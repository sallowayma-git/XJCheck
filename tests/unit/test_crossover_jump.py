import json
import math

from dwg_audit.audit.crossover_jump import FAMILY, recognize_crossover_jumps


def _shape(lines=((0, 3.75), (6.25, 10)), *, angle=(0, 180), bound=True,
           rotation_deg=0.0, scale=1.0):
    radians = math.radians(rotation_deg)
    def transform(point):
        x, y = point[0] * scale, point[1] * scale
        return [x * math.cos(radians) - y * math.sin(radians),
                x * math.sin(radians) + y * math.cos(radians), 0.0]
    rows = []
    for i, (a, b) in enumerate(lines):
        if not bound and i == 1:
            a += .1
        rows.append({"primitive_id": f"L{i}", "primitive_kind": "LINE", "sheet_id": "S", "definition_name": "x", "parent_handle": "P", "nested_path": "x[P]", "local_geometry_json": json.dumps({"start": transform((a, 0)), "end": transform((b, 0))})})
    rows.append({"primitive_id": "A", "primitive_kind": "ARC", "sheet_id": "S", "definition_name": "x", "parent_handle": "P", "nested_path": "x[P]", "local_geometry_json": json.dumps({"center": transform((5, 0)), "radius": 1.25 * scale, "start_angle": angle[0] + rotation_deg, "end_angle": angle[1] + rotation_deg})})
    return rows


def test_crossover_jump_is_name_and_fingerprint_independent():
    result = recognize_crossover_jumps(_shape())
    assert len(result) == 1 and result[0].family == FAMILY
    assert result[0].union_pairs == (("L0", "A"), ("A", "L1"))
    assert result[0].no_junction is True
    assert result[0].parent_handle == "P"


def test_crossover_jump_survives_arbitrary_rotation_and_scale():
    result = recognize_crossover_jumps(_shape(rotation_deg=37.0, scale=2.4))
    assert len(result) == 1
    assert result[0].family == FAMILY


def test_crossover_jump_rejects_unbound_and_non_semicircle():
    assert not recognize_crossover_jumps(_shape(bound=False))
    assert not recognize_crossover_jumps(_shape(angle=(0, 170)))


def test_crossover_jump_rejects_non_collinear_lead():
    rows = _shape()
    rows[0]["local_geometry_json"] = json.dumps({"start": [0, 1, 0], "end": [3.75, 0, 0]})
    assert not recognize_crossover_jumps(rows)
