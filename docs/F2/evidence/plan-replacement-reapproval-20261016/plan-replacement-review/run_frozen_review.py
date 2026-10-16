from pathlib import Path
import hashlib,json,subprocess,os,datetime
root=Path('/workspace/ParkWeave');out=root/'.runtime/plan-replacement-review/frozen-eaa2b9e91ce0';out.mkdir(exist_ok=False)
f=json.loads((root/'.runtime/plan-replacement-root/freeze.json').read_text());freeze_sha=hashlib.sha256((root/'.runtime/plan-replacement-root/freeze.json').read_bytes()).hexdigest()
def snapshot():
 actual={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in f['all_tracked_sha256']}
 source={name:actual[name] for name in f['source_paths']}
 runners={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in f['runner_paths']}
 return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),all_tracked_sha256=actual,source_sha256=source,runner_sha256=runners)
before=snapshot();(out/'before.json').write_text(json.dumps(before,sort_keys=True,indent=2)+'\n')
assert before['head']==f['source_sha']
assert before['all_tracked_sha256']==f['all_tracked_sha256']
env={**os.environ,'PYTHONPATH':str(root/'src')+':'+str(root/'.runtime/plan-replacement-review'),'PYTHONDONTWRITEBYTECODE':'1'}
cmd=[str(root/'.venv/bin/python'),str(root/'.runtime/plan-replacement-review/replacement_protocol_probes.py')]
imports=subprocess.run([str(root/'.venv/bin/python'),'-c','import json,parkweave.case_resource_delivery as d,parkweave.service_plan_approval as a,parkweave.plan_replacement_compatibility as r;print(json.dumps({m.__name__:m.__file__ for m in (d,a,r)}))'],cwd=root,env=env,capture_output=True,text=True)
(out/'imports.stdout.json').write_text(imports.stdout);(out/'imports.stderr.log').write_text(imports.stderr)
assert imports.returncode==0
run=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True)
(out/'protocol-probes.stdout.json').write_text(run.stdout);(out/'protocol-probes.stderr.log').write_text(run.stderr)
after=snapshot();(out/'after.json').write_text(json.dumps(after,sort_keys=True,indent=2)+'\n')
summary=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_sha=f['source_sha'],freeze_manifest_sha256=freeze_sha,command=cmd,exit_code=run.returncode,source_paths=len(before['source_sha256']),all_tracked_paths=len(before['all_tracked_sha256']),runner_paths=len(before['runner_sha256']),before_matches_freeze=before['all_tracked_sha256']==f['all_tracked_sha256'],before_after_equal=before==after,scope='PURE_FINITE_LEDGER_RECEIPT_NO_DATABASE_HTTP_BROWSER')
if run.returncode==0:summary['results']=json.loads(run.stdout)
(out/'run-summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False))
print(run.stdout[:1200]);print(run.stderr[:2000])
