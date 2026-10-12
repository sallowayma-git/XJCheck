"""Elapsed-time comparison from complete.json of two replay roots (read-only).

usage: wb_timing.py BASE_ROOT NEW_ROOT p001 p003 ...
"""
import json, sys
from pathlib import Path

base, new, pids = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
tb = tn = 0.0
for pid in pids:
    b = json.loads((base / pid / "complete.json").read_text(encoding="utf-8"))["elapsed_seconds"]
    n = json.loads((new / pid / "complete.json").read_text(encoding="utf-8"))["elapsed_seconds"]
    tb += b
    tn += n
    print(f"{pid} base {b:.1f}s new {n:.1f}s ({(n - b) / b * 100:+.1f}%)")
print(f"TOTAL base {tb:.1f}s new {tn:.1f}s ({(tn - tb) / tb * 100:+.1f}%)")
