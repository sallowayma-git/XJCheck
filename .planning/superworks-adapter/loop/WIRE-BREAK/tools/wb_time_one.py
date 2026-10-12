import json, sys, time
from pathlib import Path
from dwg_audit.services.execution import run_analysis_workflow
pid=sys.argv[1]; out=Path(sys.argv[2])
project=next(p for p in json.loads(Path('.planning/superworks-adapter/corpus_manifest.json').read_text(encoding='utf-8'))['projects'] if p['project_id']==pid)
t=time.perf_counter()
run_analysis_workflow(input_root=Path(project['input_root']), output_root=out, include_audit=True)
print(pid, sys.argv[3], round(time.perf_counter()-t,2), flush=True)
