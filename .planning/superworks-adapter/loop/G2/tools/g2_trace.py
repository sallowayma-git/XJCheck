"""G2 end-to-end trace for one project (diagnostic): counts the empty-gap wire breaks the changed snapshot makes.

Runs the frozen-input replay worker (replay.py --worker) on the G2 snapshot, with a wrapper on
line_groups._is_terminal_wire_break that records every gap it reports as a wire break.
Usage: python g2_trace.py <pid> <output_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path("F:/workspace/XJToolkit")
SNAPSHOT = ROOT / ".tmp" / "loop_g2_src"
PLAN = ROOT / ".planning" / "superworks-adapter"


def main(pid: str, output: str) -> None:
    sys.path.insert(0, str(SNAPSHOT))
    sys.path.insert(0, str(PLAN))
    import dwg_audit.audit.line_groups as line_groups
    assert Path(line_groups.__file__).resolve().is_relative_to(SNAPSHOT.resolve()), line_groups.__file__

    import time

    hits: list[dict] = []
    cost = {"calls": 0, "seconds": 0.0}
    original = line_groups._is_terminal_wire_break

    def traced(previous_end_axis, next_start_axis, previous_cross_axis, next_cross_axis, texts, evidence, **kwargs):
        started = time.perf_counter()
        broken = original(previous_end_axis, next_start_axis, previous_cross_axis, next_cross_axis, texts, evidence, **kwargs)
        cost["seconds"] += time.perf_counter() - started
        cost["calls"] += 1
        if broken:
            hits.append({"orientation": kwargs.get("orientation"), "gap_start": round(previous_end_axis, 3),
                         "gap_end": round(next_start_axis, 3), "cross_before": round(previous_cross_axis, 3),
                         "cross_after": round(next_cross_axis, 3),
                         "ports": len(evidence.ports) if evidence else 0})
        return broken

    line_groups._is_terminal_wire_break = traced
    import replay  # noqa: E402  (imports dwg_audit lazily, from the snapshot path above)

    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    replay.worker(pid, str(out))
    (out / "trace_wire_breaks.json").write_text(json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "trace_cost.json").write_text(json.dumps({"pid": pid, **cost, "wire_breaks": len(hits)}), encoding="utf-8")
    print(pid, "wire breaks:", len(hits), "calls:", cost["calls"], "seconds in check:", round(cost["seconds"], 4))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
