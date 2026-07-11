from dwg_audit.audit.table_structure import build_table_structure_profiles
from dwg_audit.domain.models import LineEntity


def _line(line_id: str, x1: float, y1: float, x2: float, y2: float) -> LineEntity:
    return LineEntity(
        line_id=line_id, sheet_id="S1", file_id="F1", handle=line_id, source_entity_type="LINE", layer="ANY",
        start_x=x1, start_y=y1, end_x=x2, end_y=y2, length=abs(x2 - x1) + abs(y2 - y1), angle_deg=0.0,
        bbox_min_x=min(x1, x2), bbox_min_y=min(y1, y2), bbox_max_x=max(x1, x2), bbox_max_y=max(y1, y2),
    )


def test_build_table_structure_profiles_keeps_short_lead_out_of_complete_grid() -> None:
    lines = [
        *[_line(f"H{index}", 10.0, y, 70.0, y) for index, y in enumerate((10.0, 30.0, 50.0, 70.0))],
        *[_line(f"V{index}", x, 10.0, x, 70.0) for index, x in enumerate((10.0, 30.0, 50.0, 70.0))],
        _line("LEAD", 70.0, 40.0, 95.0, 40.0),
    ]

    profiles = build_table_structure_profiles([], lines)

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile["sheet_id"] == "S1"
    assert profile["bbox"] == (10.0, 10.0, 70.0, 70.0)
    assert profile["cell_count"] == 9
    assert set(profile["structural_line_ids"]) == {f"H{index}" for index in range(4)} | {f"V{index}" for index in range(4)}
    assert "LEAD" not in profile["structural_line_ids"]
    assert profile["header_scope"]["bbox"] == (10.0, 50.0, 70.0, 70.0)


def test_build_table_structure_profiles_rejects_non_grid_lines() -> None:
    lines = [
        _line("H1", 10.0, 10.0, 70.0, 10.0),
        _line("H2", 10.0, 30.0, 70.0, 30.0),
        _line("H3", 10.0, 50.0, 40.0, 50.0),
        _line("V1", 10.0, 10.0, 10.0, 50.0),
        _line("V2", 30.0, 10.0, 30.0, 50.0),
        _line("V3", 70.0, 10.0, 70.0, 30.0),
    ]

    assert build_table_structure_profiles([], lines) == []
