import pandas as pd, json, glob, os, re
from collections import Counter
RUN = "F:/workspace/XJToolkit/.tmp/superworks_round23_full"

def jl(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    if isinstance(s, (dict, list)):
        return s
    try:
        return json.loads(s)
    except Exception:
        return None

def project_dirs():
    out = []
    for pdir in sorted(glob.glob(os.path.join(RUN, "p[0-9][0-9][0-9]"))):
        fd = glob.glob(os.path.join(pdir, "*", "findings"))
        if fd:
            out.append((os.path.basename(pdir), fd[0]))
    return out
