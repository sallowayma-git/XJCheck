"""Read-only bisect: replay one project (p016) from git-archived src snapshots of given revisions.
Writes only under .tmp/fp_verify_src and .tmp/fp_verify_replay. Uses frozen replay.run (no repo writes)."""
import sys, os, subprocess, json, importlib.util
from pathlib import Path
ROOT = Path("F:/workspace/XJToolkit")
SNAP = ROOT / ".tmp/fp_verify_src"
OUT = ROOT / ".tmp/fp_verify_replay"
spec = importlib.util.spec_from_file_location("frozen_replay", ROOT / ".planning/superworks-adapter/replay.py")
replay = importlib.util.module_from_spec(spec); spec.loader.exec_module(replay)
pid = sys.argv[1]; revs = sys.argv[2:]
for rev in revs:
    d = SNAP / rev
    if not (d / "src" / "dwg_audit").exists():
        d.mkdir(parents=True, exist_ok=True)
        arc = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", rev, "src"], capture_output=True)
        assert arc.returncode == 0, arc.stderr
        subprocess.run(["tar", "-x", "-C", str(d)], input=arc.stdout, check=True)
    out = OUT / rev
    replay.run(out, d / "src", 1, [pid])
    print("done", rev, flush=True)
