"""Offline preservation/verification of failed official run22, no business calls."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
from collections import Counter
import json,shutil,subprocess
root=Path('/workspace/ParkWeave');raw=Path(__file__).parent;out=root/'docs/F2/evidence/again-role-readback-20261022/run22';out.mkdir(exist_ok=True)
load=lambda p:json.loads(p.read_text());hashfile=lambda p:sha256(p.read_bytes()).hexdigest()
r=load(raw/'artifact/result.json');run=load(raw/'run-api.json');jobs=load(raw/'job-api.json')['jobs'];a=load(raw/'artifact-metadata.json')['artifacts'][0]
assert run['head_sha']=='75d8661ffb6c6d804c4f93f378c0ff30ed320c9f' and run['id']==39783602539 and run['run_number']==22 and run['run_attempt']==1 and run['conclusion']=='failure'
assert jobs[0]['id']==119840861546 and jobs[0]['conclusion']=='failure'
assert r['status']=='FAIL' and r['stage']=='FRESH_SPECIALIST_READ_ONLY' and r['error']=='actual participating font union misses visible node CJK'
assert not r.get('finalization_errors') and not r['violations'] and not r['page_errors']
assert hashfile(raw/'artifact.zip')=='1d1cc4bad9e84838e1efa9a00799aeb778dbfd704caac538a213c7d96e2edd31' and a['digest']=='sha256:'+hashfile(raw/'artifact.zip')
assert hashfile(raw/'ci-original.log')=='2b1f30b067674bc7c05912f36398d6a3252678189226bf147b955251bca6f3c2'
log=(raw/'ci-original.log').read_text();lines=[v for v in log.splitlines() if '{"status": "PENDING_FINALIZATION", "stage":' in v];assert len(lines)==1
v=json.loads(lines[0][lines[0].index('{'):]);v['status']=v.pop('observation_outcome');v.pop('terminal_result');assert v=={k:v for k,v in r.items() if k not in ('seconds','seconds_scope')}
assert '$GITHUB_STEP_SUMMARY upload aborted' not in log # absence of the old error, not summary-body proof
with ZipFile(raw/'artifact.zip') as z:
 names=z.namelist();assert len(names)==7 and sum(i.file_size for i in z.infolist())<=8*1024*1024
 for name in names:
  assert '/' not in name and z.read(name)==(raw/'artifact'/name).read_bytes()
  if not name.endswith('.whl'):shutil.copyfile(raw/'artifact'/name,out/name)
 wheel=r['installation'];wp=raw/'artifact'/wheel['frozen_package_source']['file'];assert hashfile(wp)==wheel['wheel_sha256'] and len(wheel['package_files'])==191
 with ZipFile(wp) as wz:
  for name,fingerprint in wheel['package_files'].items():
   data=wz.read(name);assert sha256(data).hexdigest()==fingerprint and data==subprocess.check_output(['git','show',r['source_sha']+':src/'+name],cwd=root)
b=r['request_budget'];assert b['POST']==29 and b['phase_POST']==dict(API_PREPARATION=26,BROWSER=3) and b['GET_HEAD']==102 and b['main_GET_HEAD']==83 and b['readiness_attempts']==19
assert Counter(x['status'] for x in r['responses'] if x['method']=='POST')==Counter({200:15,201:12,202:2})
assert Counter(x['status'] for x in r['responses'] if x['method']=='GET')==Counter({200:79,403:4})
first,second=r['records']
for key in ('preparation_id','case_id','run_id','plan_id'):assert first[key]!=second[key]
assert [(x['role'],len(x['preparations']),len(x['plans'])) for x in r['fresh_roles']]==[('enterprise',2,2),('specialist',2,0)]
for role in r['fresh_roles']:
 for rec,view in zip((first,second),role['preparations']):assert view['preparation']['id']==rec['preparation_id'] and view['preparation']['case_id']==rec['case_id'] and view['preparation']['run_id']==rec['run_id']
for rec,plan in zip((first,second),r['fresh_roles'][0]['plans']):assert plan['plan_id']==rec['plan_id']
assert [len(p['required_goals']) for p in r['fresh_roles'][0]['plans']]==[5,1]
assert 'fresh_role_readback' not in r and 'final_named_business_snapshot' not in r
before,after=r['first_before_second'],r['first_after_second']
assert {k:v for k,v in before.items() if k!='tail_tables'}=={k:v for k,v in after.items() if k!='tail_tables'}
for name,rows in before['tail_tables'].items():assert rows==([v for v in after['tail_tables'][name] if v['id']==first['case_id']] if name=='cases' else after['tail_tables'][name])
proof=r['second_confirmation_original_key'];row=proof['SQL_event'];assert row['actor_id']=='ordinary-demo-enterprise' and row['action']=='CONFIRM' and row['request_key']==proof['key'] and row['preparation_id']==second['preparation_id']
assert len(r['browser_POST_key_proofs'])==2 and len(r['original_success_recovery_GETs'])==1
for p in r['browser_POST_key_proofs']:
 rows=[e for e in after['tail_tables']['service_dispatch_events'] if e['id']==p['stored_event_id'] and e['request_key']==p['key']]
 assert len(rows)==1 and rows[0]['payload']==p['stored_payload'] and rows[0]['actor_id']==p['actor_id'] and rows[0]['action']==p['action'] and rows[0]['fingerprint']==p['fingerprint']
assert r['original_success_recovery_GETs'][0]['response']['status']=='COMMITTED'
assert r['installed_worker_exits']==[0,0] and len(r['service_generations'])==1
for cleanup in [r['setup_owned_cleanup'],r['service_generations'][0]['cleanup']]:assert not cleanup['cleanup_errors'] and cleanup['postgres_marker_absent'] and all(c['exit_code']==0 for c in cleanup['children'])
assert r['service_generations'][0]['wrapper_exit']==0 and r['service_generations'][0]['API_listener_refused_after_stop']
for item in r['screenshots']:assert hashfile(raw/'artifact'/item['file'])==item['sha256'] and item['geometry']['width']==item['geometry']['documentWidth']==1200
for name in ['artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json','dynamic-font-diagnosis.json','archive_run22.py']:shutil.copyfile(raw/name,out/name)
shutil.copyfile(raw.parent/'source-publication-map.json',out/'source-publication-map.json')
for name in ['dynamic-font-before-original.log','dynamic-font-after-original.log']:shutil.copyfile(raw.parent/name,out/name)
v=dict(status='FAIL',source_sha=r['source_sha'],run_id=run['id'],run_number=22,attempt=1,job_id=jobs[0]['id'],artifact_id=a['id'],artifact_zip_sha256=hashfile(raw/'artifact.zip'),raw_log_sha256=hashfile(raw/'ci-original.log'),failure_stage=r['stage'],failure=r['error'],cause='FONT_ORACLE_STATIC_INTERSECTION_USED_FOR_DYNAMIC_TEXT_FALSE_NEGATIVE',original_artifact_members=len(names),POST_success=29,API_POST=26,DOM_POST=3,GET_HEAD=102,main_GET_HEAD=83,readiness=19,main_GET_200=79,main_GET_403=4,owner_fresh_records_read=2,specialist_fresh_records_read=2,executor_fresh_context='NOT_EXECUTED',final_dual_projection_comparison='NOT_EXECUTED',first_history_preservation_scope='Exact named projections excluding only new B row in global cases, not raw whole-object equality',wheel_source_files=191,workers=[0,0],API_PG_generations=1,cleanup='API/PG/wrapper0; marker absent; listener refused; no cleanup errors',summary='Old size-aborted error absent, bounded summary code executed; body/upload not independently read, no unqualified success claim',fix_verification='Controlled CDP fixture old1FAIL0.10s/new1PASS0.06s, actual browser after fix NOT_EXECUTED',screenshots='4 original1200px PNG including failure; 01 source-summary viewport not material confirmation proof,02 B plan only,03/failure B training readable; no390px claim',formal_AT35=False,real_model_calls=0)
(out/'validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print(v)
