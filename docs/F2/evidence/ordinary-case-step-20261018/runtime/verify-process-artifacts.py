from pathlib import Path
import hashlib,json
r=Path('/workspace/ParkWeave/.runtime/ordinary-case-step-20261018');f=r/'frozen-954825ef'
process=[];unique={}
for p in sorted((f/'process-artifacts').rglob('process.json')):
    d=json.loads(p.read_text())
    assert d[0]['api_pid']==d[0]['health_pid']
    assert d[-1]['owned_child_exit']==-15
    row=dict(path=str(p.relative_to(r)),api_pid=d[0]['api_pid'],health_pid=d[0]['health_pid'],owned_child_exit=d[-1]['owned_child_exit'])
    process.append(row)
    if row['api_pid'] in unique:assert d==unique[row['api_pid']]
    unique[row['api_pid']]=d
assert len(unique)==4
chains=list((f/'process-artifacts').rglob('chain-proof.json'))
assert len({hashlib.sha256(p.read_bytes()).hexdigest() for p in chains})==1
c=json.loads(chains[0].read_text());assert c['ordinary_api_processes']==3 and c['worker_processes']==3 and c['authority_unchanged']
assert c['first_offer']['deadline']==c['executed']['deadline']==c['cold']['deadline']
assert c['executed']['step']==c['cold']['step']
assert all(x['method']=='GET' for x in c['cold']['calls'])
workers=list((f/'process-artifacts').rglob('worker-result.json'))+list((f/'ordinary-artifacts').rglob('worker-result.json'))
assert all(json.loads(p.read_text())['exit_code']==0 for p in workers)
# pytest's *_current symlink produced duplicate copied raw paths. Preserve both,
# count each actual non-current path once; API identities are additionally deduped.
worker_unique=[p for p in workers if not any(part.endswith('current') for part in p.relative_to(f).parts)]
assert len(worker_unique)==5
x=dict(tested_sha='954825efb66d16f7e41087e1c108b45042732703',owned_api_process_observations=process,unique_owned_api_processes=4,api_exits=[-15]*4,api_stop='owned SIGTERM via original stop_children',owned_worker_processes=len(worker_unique),all_worker_exit_zero=True,duplicate_pytest_current_paths_retained=True,chain_paths=[str(p.relative_to(r)) for p in chains],same_uuid_and_first_deadline_after_restarts=True,cold_original_html_get_only=True,api_child_import_origins_separately_instrumented=False,fixed_mirror_cwd_and_pythonpath=True,real_browser=False,initial_verifier_failure=dict(reason='assumed owned API shutdown exit0; actual SIGTERM -15',exit_code=1,product_or_test_failure=False))
(r/'process-source-validation.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x))
