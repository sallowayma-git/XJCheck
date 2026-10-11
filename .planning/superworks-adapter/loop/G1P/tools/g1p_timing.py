"""G1P timing (read-only on inputs): wall time of the two steps this slice touches, per project.

Usage: python g1p_timing.py <src_dir> <output_dir> <project ids...>
Runs the frozen-input replay worker (replay.worker) for each project with the given code (src_dir is put first on
sys.path), wrapping two functions: extract_superworks_semantics (per sheet, the walk and the wire end-point index) and
_device_internal_links (device-internal links). Also times the device-link and unregistered-block parquet writers (the latter exists only in the new code).
Writes <output_dir>/timing.json with per-project seconds. Run the HEAD
source and the new source separately, serially, so the two never share the machine.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path("F:/workspace/XJToolkit")


def main(src: Path, out: Path, projects: list[str]) -> None:
    sys.path.insert(0, str(src))
    import dwg_audit.extract.superworks_semantics as sem
    import dwg_audit.report.superworks_artifacts as art
    assert str(Path(sem.__file__).resolve()).startswith(str(src.resolve())), sem.__file__
    sys.path.insert(0, str(ROOT / ".planning/superworks-adapter"))
    import replay

    timers = {"extract": 0.0, "device_links": 0.0, "write_device_links": 0.0, "write_unregistered": 0.0}
    original_extract = sem.extract_superworks_semantics
    original_links = art._device_internal_links

    def timed_extract(*args, **kwargs):
        started = time.perf_counter()
        result = original_extract(*args, **kwargs)
        timers["extract"] += time.perf_counter() - started
        return result

    def timed_links(*args, **kwargs):
        started = time.perf_counter()
        result = original_links(*args, **kwargs)
        timers["device_links"] += time.perf_counter() - started
        return result

    def wrap_writer(name, key):
        original = getattr(art, name, None)
        if original is None:
            return
        def timed_writer(*args, **kwargs):
            started = time.perf_counter()
            result = original(*args, **kwargs)
            timers[key] += time.perf_counter() - started
            return result
        setattr(art, name, timed_writer)

    sem.extract_superworks_semantics = timed_extract
    art._device_internal_links = timed_links
    wrap_writer("_write_device_internal_links", "write_device_links")
    wrap_writer("_write_unregistered_symb2", "write_unregistered")
    out.mkdir(parents=True, exist_ok=True)
    rows = {}
    for pid in projects:
        for key in timers:
            timers[key] = 0.0
        started = time.perf_counter()
        replay.worker(pid, str(out / "replay"))
        elapsed = time.perf_counter() - started
        rows[pid] = {"elapsed": elapsed, **timers}
        print(pid, {k: round(v, 3) for k, v in rows[pid].items()}, flush=True)
    (out / "timing.json").write_text(json.dumps({"src": str(src), "projects": rows}, ensure_ascii=False, indent=1),
                                    encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
