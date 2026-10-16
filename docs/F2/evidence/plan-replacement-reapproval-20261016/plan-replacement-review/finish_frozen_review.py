from pathlib import Path
import hashlib,json,subprocess,datetime
root=Path('/workspace/ParkWeave');out=root/'.runtime/plan-replacement-review/frozen-eaa2b9e91ce0'
f=json.loads((root/'.runtime/plan-replacement-root/freeze.json').read_text());before=json.loads((out/'before.json').read_text())
actual={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in f['all_tracked_sha256']}
after=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),all_tracked_sha256=actual,source_sha256={n:actual[n] for n in f['source_paths']},runner_sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in f['runner_paths']})
(out/'after-client.json').write_text(json.dumps(after,sort_keys=True,indent=2)+'\n')
manifest=json.loads((root/'.runtime/plan-replacement-backend/candidate-v5/manifest.json').read_text())
backend={i['path']:hashlib.sha256((root/i['path']).read_bytes()).hexdigest()==i['sha256'] for i in manifest['files']}
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_sha=f['source_sha'],status='LIMITED_PASS',blocking_findings=[],before_after_equal=before==after,source_paths=647,all_tracked_paths=19446,runner_paths=36,backend_v5_exact=backend,pure_protocol_cases=15,pure_protocol_failures=0,client_modules=['tests/test_plan_replacement_client.py','tests/test_plan_reapproval_client.py'],client_passed=11,client_failed=0,client_exit_code=0,actual_http=False,actual_owned_pg=False,real_browser='NOT_RUN',dedicated_pg27='NOT_RUN',other_gaps=['general in-flight/partial-chain replacement','Windows/native Windows browser','formal AT','real model','production','broad browser acceptance'])
assert before==after and all(backend.values())
(out/'review-result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
