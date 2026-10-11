"""Disable the rules.py 上接 fold in a snapshot copy (experiment only; never edits src/).

Usage: python make_norules_snapshot.py <snapshot_dir>
Replaces the continuation mark with an ASCII marker that never matches and the continuation
header regex with a never-matching pattern, so the 上接 branch of rules.py is unreachable.
"""
import sys
from pathlib import Path

snap = Path(sys.argv[1])
p = snap / "dwg_audit" / "audit" / "rules.py"
s = p.read_bytes().decode("utf-8")
a = '_CONTINUATION_MARK = "上接"'
b = '_CONTINUATION_HEADER_PATTERN = re.compile(r"上接(?P<prefix>.+[A-Za-z])(?P<last_row>\\d+)")'
assert s.count(a) == 1 and s.count(b) == 1, (s.count(a), s.count(b))
s = s.replace(a, '_CONTINUATION_MARK = "@NOFOLD@"  # EXPERIMENT: fold disabled')
s = s.replace(b, '_CONTINUATION_HEADER_PATTERN = re.compile(r"(?!)")  # EXPERIMENT')
p.write_bytes(s.encode("utf-8"))
print("patched", p, "NUL" if "\x00" in s else "no-NUL")
