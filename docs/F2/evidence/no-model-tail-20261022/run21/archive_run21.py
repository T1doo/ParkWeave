"""Recheck immutable official run21 evidence offline; never runs business actions."""
from pathlib import Path
from hashlib import sha256
from collections import Counter
from zipfile import ZipFile
import json,subprocess,shutil,sys
root=Path('/workspace/ParkWeave');sys.path.insert(0,str(root));sys.path.insert(0,str(root/'src'))
from scripts.local_tail_installed_browser_once import truth,public_event,digest,unpack
raw=Path(__file__).parent;out=root/'docs/F2/evidence/no-model-tail-20261022/run21';out.mkdir(exist_ok=True)
load=lambda p:json.loads(p.read_text());h=lambda p:sha256(p.read_bytes()).hexdigest()
r=load(raw/'artifact/result.json');run=load(raw/'run-api.json');jobs=load(raw/'job-api.json')['jobs'];a=load(raw/'artifact-metadata.json')['artifacts'][0]
source='dbc66b066b592d8eeb2da705472f326893e8fa72'
assert run['id']==39777380048 and run['run_number']==21 and run['run_attempt']==1 and run['head_sha']==source and run['conclusion']=='success'
assert len(jobs)==1 and jobs[0]['id']==119819665446 and jobs[0]['conclusion']=='success' and all(s['conclusion']=='success' for s in jobs[0]['steps'])
assert a['id']==12424014884 and a['digest']=='sha256:'+h(raw/'artifact.zip')
assert h(raw/'artifact.zip')=='b8532315c8cc215c28a6d63f862dbde29475636d5647d83370540a4ae58050fb'
assert h(raw/'ci-original.log')=='7f81441119ea51f2e0cf17decf6ad296d16258867b93d426ac1d73c9e819fef1'
assert r['status']=='PASS' and r['source_sha']==source and not r['violations'] and not r['page_errors'] and not r.get('finalization_errors')
assert r['real_model_calls']==0 and not any(r[k] for k in ['formal_source','formal_AT35','Windows','PG_restart'])
log=(raw/'ci-original.log').read_text();stdout=[json.loads(line[line.index('{'):]) for line in log.splitlines() if '{"status": "PENDING_FINALIZATION", "stage":' in line]
assert '$GITHUB_STEP_SUMMARY upload aborted, supports content up to a size of 1024k, got 1685k.' in log
assert len(stdout)==1
v=stdout[0];v['status']=v.pop('observation_outcome');v.pop('terminal_result');actual={k:v for k,v in r.items() if k not in ('seconds','seconds_scope')};assert v==actual
with ZipFile(raw/'artifact.zip') as z:
 names=z.namelist();assert len(names)==9 and len(set(names))==9 and sum(i.file_size for i in z.infolist())<=8*1024*1024
 for name in names:assert '/' not in name and z.read(name)==(raw/'artifact'/name).read_bytes()
 wheel=r['installation']['frozen_package_source'];wp=raw/'artifact'/wheel['file'];assert h(wp)==wheel['sha256'] and wp.stat().st_size==wheel['bytes']
 with ZipFile(wp) as wz:
  files=r['installation']['package_files'];assert len(files)==191
  for name,fingerprint in files.items():
   data=wz.read(name);assert sha256(data).hexdigest()==fingerprint
   frozen=subprocess.check_output(['git','show',source+':src/'+name],cwd=root);assert data==frozen
 for name in names:
  if name!=wheel['file']:shutil.copyfile(raw/'artifact'/name,out/name)
for stage in r['goal_stages']:truth(stage['goal_results'],r['record'],[x['state'] for x in stage['goal_results']['results']])
for index,e in enumerate(r['exports']):
 states=['LOCAL_OUTPUT_VERIFIED']*5
 if not index:states[-1]='WAITING_OUTPUT'
 truth(e['goal_results'],r['record'],states);p=raw/'artifact'/e['file'];assert h(p)==e['TXT_sha256'] and p.stat().st_size==e['bytes']
 assert unpack(p.read_text(),e['goal_results'])==e['pack'] and digest(e['pack'])==e['pack_sha256'] and e['GET_only'] and e['named_projection_equal']
assert r['exports'][0]['TXT_sha256']!=r['exports'][1]['TXT_sha256']
assert len(r['prerequisite_refusals'])==3
for n in r['prerequisite_refusals']:assert n['HTTP']==409 and n['named_before']==n['named_after'] and n['named_projection_equal']
proofs=r['browser_POST_key_proofs'];assert len(proofs)==6 and len({p['key'] for p in proofs})==6
snap=r['final_named_business_snapshot'];tables=snap['tail_tables']
for p in proofs:
 table='service_dispatch_events' if p['action'] in ('OFFER','ACCEPT') else 'service_receipt_events' if p['action'] in ('SUBMIT','ACKNOWLEDGE') else 'case_local_events'
 rows=[e for e in tables[table] if str(e['id'])==p['stored_event_id'] and str(e['request_key'])==p['key']]
 assert len(rows)==1;row=rows[0]
 assert row['payload']==p['stored_payload'] and row['fingerprint']==p['fingerprint'] and row['actor_id']==p['actor_id'] and row['action']==p['action']
 assert p['response_event_equals_original_key_SQL_public_projection'] and p['only_dispatch_internal_marker_projected']==(table=='service_dispatch_events')
 # API response body equivalence was asserted live; stored SQL original remains complete here.
 assert public_event(table,row['payload'])
assert len(r['original_success_recovery_GETs'])==2
for g in r['original_success_recovery_GETs']:
 v=g['response'];p=next(p for p in proofs if p['key']==g['request_key']);assert g['HTTP']==200 and v['status']=='COMMITTED' and v['request_key']==p['key'] and v['event']['id']==p['stored_event_id'] and v['event']['action']==p['action']
 assert v['actor_ref']==digest(dict(actor_id=p['actor_id'])) and v['read_only'] and v['historical_only'] and v['automatically_replayed'] is False
 for key,value in g['query'].items():assert str(v[key])==value
assert not tables['run_assignments'] and len(tables['case_local_events'])==2 and len(snap['links'])==1 and len(snap['holds'])==3
assert all(h['state']=='CONFIRMED' for h in snap['holds'])
assert len(r['service_generations'])==1 and r['setup_stop_status']=='CONFIRMED'
for cleanup in [r['setup_owned_cleanup'],r['service_generations'][0]['cleanup']]:
 assert not cleanup['cleanup_errors'] and cleanup['postgres_marker_absent'] and all(c['exit_code']==0 for c in cleanup['children'])
g=r['service_generations'][0];assert g['wrapper_exit']==0 and g['API_listener_refused_after_stop']
budget=r['request_budget'];assert budget['POST']==30 and budget['GET_HEAD']==113 and budget['phase_POST']==dict(API_PREPARATION=21,BROWSER=6,NEGATIVE_AND_REPEAT=3)
assert Counter(x['status'] for x in r['responses'] if x['method']=='POST')==Counter({200:17,201:9,202:1,409:3})
denied=[x for x in r['responses'] if x['status']==403];assert len(denied)==3 and all(x['method']=='GET' for x in denied)
for shot in r['screenshots']:assert h(raw/'artifact'/shot['file'])==shot['sha256'] and shot['geometry']['width']==shot['geometry']['documentWidth'] and shot['geometry']['navPosition']=='relative'
assert len(r['screenshots'])==4
for name in ['artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json','archive_run21.py']:shutil.copyfile(raw/name,out/name)
shutil.copyfile(raw.parent/'publication-map.json',out/'source-publication-map.json')
summary=dict(status='LIMITED_PASS',source_sha=source,run_id=run['id'],run_number=21,attempt=1,job_id=jobs[0]['id'],artifact_id=a['id'],artifact_zip_sha256=h(raw/'artifact.zip'),raw_log_sha256=h(raw/'ci-original.log'),original_artifact_members=len(names),original_uncompressed_bytes=sum((raw/'artifact'/n).stat().st_size for n in names),wheel_source_files=191,POST=budget['POST'],POST_success=27,POST_expected_409=3,GET_HEAD=113,main_GET_HEAD=95,readiness_attempts=18,denied_GETs=denied,actual_DOM_business_POST=6,explicit_API_tail_VERIFY=3,original_success_recovery_GETs=2,negative_named_projections_unchanged=3,goal_stage_snapshots=7,final_goal_count=5,exports=[{k:e[k] for k in ('stage','file','bytes','TXT_sha256','pack_sha256')} for e in r['exports']],work_completion_seconds=r['work_completion_seconds'],artifact_scan_seconds=r['seconds'],no_business_product_patch=True,service_generations=1,service_restart=False,case_goal_completed=False,real_model_calls=0,step_summary_body_independently_read=False,step_summary_upload=dict(status='FAILED_SIZE_LIMIT',observed_log_timestamp='2026-10-22T12:20:54.8278311Z',actual_k=1685,limit_k=1024,job_conclusion='success',artifact_preserved=True),stdout_scope='PENDING_FINALIZATION exact observation object, not terminal PASS; terminal artifact + successful job/steps; runner summary upload failed size limit',SQL_fingerprint_scope='Stored original-key SQL fingerprint retained; not independently request-body recomputed',screenshots_scope='Four actual viewport originals; 390px shows aggregate and partial goal list, not every full goal card; no all-page/all-codepoint claim',unverified=['formal external source','Windows native','real models','real offline fulfillment','formal AT01-35 total acceptance'])
(out/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
