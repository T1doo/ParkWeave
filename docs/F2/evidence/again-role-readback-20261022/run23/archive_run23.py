"""Verify and preserve this complete official run23; no business execution."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
from collections import Counter
import json,shutil,subprocess
root=Path('/workspace/ParkWeave');raw=Path(__file__).parent;out=root/'docs/F2/evidence/again-role-readback-20261022/run23'
load=lambda p:json.loads(p.read_text());hashfile=lambda p:sha256(p.read_bytes()).hexdigest()
r=load(raw/'artifact/result.json');run=load(raw/'run-api.json');jobs=load(raw/'job-api.json')['jobs'];a=load(raw/'artifact-metadata.json')['artifacts'][0]
assert run['head_sha']=='c34668fe8d6dc2448917642b24800d5e337e6903' and run['id']==39787958372 and run['run_number']==23 and run['run_attempt']==1 and run['conclusion']=='success'
assert jobs[0]['id']==119856010803 and jobs[0]['conclusion']=='success' and all(s['conclusion']=='success' for s in jobs[0]['steps'])
assert r['status']=='PASS' and r['stage']=='TWO_ADOPTED_INPUTS_THREE_FRESH_ROLES_COMPLETE' and not r.get('error') and not r.get('finalization_errors') and not r['violations'] and not r['page_errors']
assert hashfile(raw/'artifact.zip')=='672cfa2e9d81aa165e9bbee1d16f2c18591801ea1a20ced75f405cd1185c479c' and a['digest']=='sha256:'+hashfile(raw/'artifact.zip')
assert hashfile(raw/'ci-original.log')=='ea95aeae67739947e3e65cad6190bc23d74e6c9e18262eb30cce031497845207'
log=(raw/'ci-original.log').read_text();lines=[v for v in log.splitlines() if '{"status": "PENDING_FINALIZATION", "stage":' in v];assert len(lines)==1
v=json.loads(lines[0][lines[0].index('{'):]);v['status']=v.pop('observation_outcome');v.pop('terminal_result');assert v=={k:v for k,v in r.items() if k not in ('seconds','seconds_scope')}
assert '$GITHUB_STEP_SUMMARY upload aborted' not in log # not a read of summary body
with ZipFile(raw/'artifact.zip') as z:
 names=z.namelist();assert len(names)==8 and sum(i.file_size for i in z.infolist())==2576320
 assert sum(i.file_size for i in z.infolist())<=8*1024*1024
 for name in names:
  assert '/' not in name and z.read(name)==(raw/'artifact'/name).read_bytes()
  if not name.endswith('.whl'):shutil.copyfile(raw/'artifact'/name,out/name)
 wheel=r['installation'];wp=raw/'artifact'/wheel['frozen_package_source']['file'];assert hashfile(wp)==wheel['wheel_sha256'] and len(wheel['package_files'])==191
 with ZipFile(wp) as wz:
  for name,fingerprint in wheel['package_files'].items():
   data=wz.read(name);assert sha256(data).hexdigest()==fingerprint and data==subprocess.check_output(['git','show',r['source_sha']+':src/'+name],cwd=root)
b=r['request_budget'];assert b['POST']==29 and b['phase_POST']==dict(API_PREPARATION=26,BROWSER=3) and b['GET_HEAD']==109 and b['main_GET_HEAD']==90 and b['readiness_attempts']==19
assert Counter(x['status'] for x in r['responses'] if x['method']=='POST')==Counter({200:15,201:12,202:2})
assert Counter(x['status'] for x in r['responses'] if x['method']=='GET')==Counter({200:84,403:6})
first,second=r['records']
for key in ('preparation_id','case_id','run_id','plan_id'):assert first[key]!=second[key]
assert [(x['role'],len(x['preparations']),len(x['plans'])) for x in r['fresh_roles']]==[('enterprise',2,2),('specialist',2,0),('executor',0,0)]
for role in r['fresh_roles']:
 assert role['new_context'] and role['empty_localStorage']
 for rec,view in zip((first,second),role['preparations']):assert view['preparation']['id']==rec['preparation_id'] and view['preparation']['case_id']==rec['case_id'] and view['preparation']['run_id']==rec['run_id']
for rec,plan in zip((first,second),r['fresh_roles'][0]['plans']):assert plan['plan_id']==rec['plan_id']
assert [len(p['required_goals']) for p in r['fresh_roles'][0]['plans']]==[5,1]
e=r['fresh_roles'][2];accepted=r['first_accepted_dispatch']
assert e['dispatch']['dispatch_id']==accepted['dispatch_id'] and e['dispatch']['case_id']==first['case_id']
assert e['receipt']['step']['id']==accepted['receipt_step_id'] and e['receipt']['step']['case_id']==first['case_id'] and e['receipt']['current_receipt'] is None
assert not e['receipt']['run_access_granted'] and not e['receipt']['case_goal_completed']
assert e['receipt']['assignment_valid_until']==e['dispatch']['assignment_valid_until']==accepted['assignment_valid_until']
assert e['B_entry_UI_403_after_navigation_cleared'] and e['B_dispatch_API_403']==dict(detail='record unavailable or authorization denied')
B='/api/preparations/'+second['preparation_id']
assert any(x['path']==B+'/dispatch' and x['transport']=='API' and x['status']==403 for x in r['responses'])
assert any(x['path']==B+'/entry' and x['transport']=='BROWSER' and x['status']==403 for x in r['responses'])
fresh=[x for x in r['responses'] if x['stage'].startswith('FRESH_')];assert fresh and all(x['method'] in ('GET','HEAD') for x in fresh)
assert r['fresh_role_readback']==dict(roles=3,new_contexts=3,business_POSTs=0,named_projection_equal=True,PG_restart=False)
assert set(r['final_named_business_snapshot'])=={first['preparation_id'],second['preparation_id']}
for rec in (first,second):assert r['final_named_business_snapshot'][rec['preparation_id']]['preparation']['id']==rec['preparation_id']
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
assert [len(f['nodes']) for f in r['font_observations']]==[16,15,21] and all(f['complete'] for f in r['font_observations'])
for stage in r['font_observations']:
 for node in stage['nodes']:assert not node['invalid_sources'] and not node['missing_codepoints'] and set(node['required_codepoints'])<=set().union(*(set(f['covered_visible_codepoints']) for f in node['matched_faces']))
for item in r['screenshots']:assert hashfile(raw/'artifact'/item['file'])==item['sha256'] and item['geometry']['width']==item['geometry']['documentWidth']==1200
assert len(r['screenshots'])==5 and not any(r[k] for k in ('formal_source','formal_AT35','Windows','PG_restart','real_model_calls'))
for name in ['artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json','archive_run23.py']:shutil.copyfile(raw/name,out/name)
shutil.copyfile(raw.parent/'source-publication-map.json',out/'source-publication-map.json')
v=dict(status='LIMITED_PASS',source_sha=r['source_sha'],run_id=run['id'],run_number=23,attempt=1,job_id=jobs[0]['id'],artifact_id=a['id'],artifact_zip_sha256=hashfile(raw/'artifact.zip'),raw_log_sha256=hashfile(raw/'ci-original.log'),original_artifact_members=8,uncompressed_bytes=2576320,POST_success=29,API_POST=26,DOM_POST=3,GET_HEAD=109,main_GET_HEAD=90,readiness=19,main_GET_200=84,main_GET_403=6,owner_fresh_records_read=2,specialist_fresh_records_read=2,executor_fresh_context='A_REAL_RECEIPT_STEP_CURRENT_RECEIPT_NONE; B_REAL_DISPATCH_API403_ENTRY_UI403',navigation_then_denial_four_views_empty=True,readback_business_POSTs=0,both_named_projection_runtime_comparison=True,separately_archived_after_projection=False,first_history_preservation_scope='Exact named projections excluding only new B row in global cases, not raw whole-object equality',wheel_source_files=191,workers=[0,0],API_PG_generations=1,cleanup='API/PG/wrapper0; marker absent; listener refused; no cleanup errors',font_visible_nodes=[16,15,21],font_scope='Actual visible CDP parents and original charset union; not glyph-to-codepoint or whole-page pixel proof',summary='Old size-aborted error absent; body/upload not independently read',work_completion_seconds=r['work_completion_seconds'],artifact_scan_seconds=r['seconds'],screenshots='5 actual1200px viewport PNG; 01Bmaterials,02Bplan,03Bmaterials,04Aemptyreceipt,05denied; not both plans simultaneously or390px',formal_AT35=False,second_case_full_fulfillment=False,real_model_calls=0,run22='FAIL_PRESERVED_NOT_REPLACED')
v.update(readback_GET_200=42,readback_GET_403=4,readback_GETs=46)
(out/'validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');print(v)
