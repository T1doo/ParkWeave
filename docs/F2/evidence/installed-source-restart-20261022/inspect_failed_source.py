from pathlib import Path
from types import SimpleNamespace
import json,time
from scripts import local_source_restart_installed_browser_once as x
p=Path('/workspace/scratch/installed-source-restart-20261022/api-preflight-1');r=json.loads((p/'preflight-result.json').read_text());d=p.parent/'source-preview-readonly-diagnostic';d.mkdir(exist_ok=False)
run=SimpleNamespace(started=time.monotonic(),private=d,harness=p/'application/harness',python=p/'application/venv/bin/python',state=Path(r['setup_owned_cleanup']['state_dir']),report=dict(responses=[],stage='READ_ONLY_DIAGNOSTIC'),record=r['record'])
run.budget=x.old.Budget(run.report);run.budget.internal_reads=r['request_budget']['readiness_attempts'];run.tokens=json.loads((run.state/'sessions.json').read_text());run.secrets=list(run.tokens.values())
try:
 with x.server(run,'restarted'):
  last=r['responses'][-1]['path'];v=x.old.api_call(run,last);(d/'preview.json').write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n');print(json.dumps(dict(can_adopt=v['can_adopt'],blockers=v['blocking_reasons'],unknown=v['source_impact']['unknown_reasons'],scope=v['source_impact']['unknown_scope']),ensure_ascii=False))
finally:(d/'diagnostic.json').write_text(x.base.resource.redact(run.report,run.secrets)+'\n')
