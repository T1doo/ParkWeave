from pathlib import Path
import hashlib,json,subprocess,os,datetime
root=Path('/workspace/ParkWeave');out=root/'.runtime/plan-replacement-root/v4/frozen-review'
f=json.loads((root/'.runtime/plan-replacement-root/v4/freeze.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
 actual={n:sha(root/n) for n in f['all_tracked_sha256']}
 return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),all_tracked_sha256=actual,source_sha256={n:actual[n] for n in f['source_paths']},runner_sha256={n:sha(root/n) for n in f['runner_paths']})
before=snapshot();(out/'before.json').write_text(json.dumps(before,sort_keys=True,indent=2)+'\n')
assert before['head']==f['source_sha'] and before['all_tracked_sha256']==f['all_tracked_sha256']
env={**os.environ,'PYTHONPATH':str(root/'src')+':'+str(out),'PYTHONDONTWRITEBYTECODE':'1'}
py=str(root/'.venv/bin/python')
imports=subprocess.run([py,'-c','import json,parkweave.case_resource_delivery as d,parkweave.service_plan_approval as a,parkweave.plan_replacement_compatibility as r;print(json.dumps({m.__name__:m.__file__ for m in (d,a,r)}))'],cwd=root,env=env,capture_output=True,text=True)
(out/'imports.stdout.json').write_text(imports.stdout);(out/'imports.stderr.log').write_text(imports.stderr)
assert imports.returncode==0
pure_cmd=[py,str(out/'replacement_protocol_probes.py')];pure=subprocess.run(pure_cmd,cwd=root,env=env,capture_output=True,text=True)
(out/'protocol-probes.stdout.json').write_text(pure.stdout);(out/'protocol-probes.stderr.log').write_text(pure.stderr)
client_cmd=[py,'-m','pytest','tests/test_plan_replacement_client.py','tests/test_plan_reapproval_client.py','--basetemp='+str(out/'client-tmp'),'-p','no:cacheprovider','-q']
client=subprocess.run(client_cmd,cwd=root,env=env,capture_output=True,text=True)
(out/'client-pytest.stdout.log').write_text(client.stdout);(out/'client-pytest.stderr.log').write_text(client.stderr)
after=snapshot();(out/'after.json').write_text(json.dumps(after,sort_keys=True,indent=2)+'\n')
product=subprocess.check_output(['git','diff','--name-only','eaa2b9e91ce0b1d9038488e3c457a4784ef04228',f['source_sha'],'--','src'],cwd=root,text=True)
proof=json.loads(pure.stdout) if pure.returncode==0 else None
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_sha=f['source_sha'],status='LIMITED_PASS' if pure.returncode==client.returncode==0 and before==after and not product else 'FAIL',blocking_findings=[],before_matches_freeze=True,before_after_equal=before==after,source_paths=len(f['source_paths']),all_tracked_paths=len(f['all_tracked_sha256']),runner_paths=len(f['runner_paths']),product_diff_from_eaa_empty=not product,pure_protocol_cases=len(proof['results']) if proof else None,pure_exit_code=pure.returncode,pure_command=pure_cmd,client_modules=client_cmd[3:5],client_passed=11 if client.returncode==0 and '11 passed' in client.stdout else None,client_exit_code=client.returncode,client_command=client_cmd,actual_http=False,actual_owned_pg=False,real_browser='NOT_RUN',dedicated_pg27='NOT_RUN',other_gaps=['general in-flight/partial-chain replacement','Windows/native Windows browser','formal AT','real model','production','broad browser acceptance'],freeze_manifest_sha256=sha(root/'.runtime/plan-replacement-root/v4/freeze.json'),local_probe_sha256={p.name:sha(p) for p in (out/'legacy_protocol_fixture.py',out/'replacement_protocol_probes.py',out/'run_review.py')})
(out/'review-result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result));print(client.stdout)
assert result['status']=='LIMITED_PASS'
