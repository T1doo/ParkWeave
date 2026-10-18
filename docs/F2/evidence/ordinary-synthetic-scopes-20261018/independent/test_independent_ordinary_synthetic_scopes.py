"""Three independent finite negatives from the pre-implementation literal oracle.

Fresh setup/real user HTTP only. No product-state SQL seed or full positive chain.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
from hashlib import sha256
import json,os,stat
import pytest
from parkweave.store import Store,Denied,digest
from scripts import ordinary_synthetic_demo as demo
from test_ordinary_synthetic_demo import demo_state,server,call,port,PrivateTokens,prepare_case,GOALS

TABLES=('runs','cases','preparations','preparation_events','preparation_evidence',
 'synthetic_resource_holds','synthetic_resource_receipts','synthetic_resource_combinations',
 'synthetic_resource_combination_members','synthetic_resource_combination_receipts',
 'case_resource_links','resource_case_claims','service_dispatches','service_dispatch_offers',
 'service_dispatch_events','service_receipt_steps','service_step_receipts','service_receipt_events',
 'case_local_lifecycles','case_local_events','controlled_plans','controlled_plan_events')


def evidence(name,value):
 p=Path(os.environ['PARKWEAVE_INDEPENDENT_DEMO_EVIDENCE']);p.mkdir(parents=True,exist_ok=True)
 (p/(name+'.json')).write_text(json.dumps(value,sort_keys=True,indent=2,default=str)+'\n')


def scope_tokens(tokens,scope):return PrivateTokens({a:tokens[k] for a,k in scope['sessions'].items()})


def snapshot(state):
 with Store(demo.lifecycle.dsn(state)).connect() as c:
  c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
  rows={t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in TABLES}
  audits=c.execute('SELECT id,principal_id,category,outcome FROM authorization_audit ORDER BY id').fetchall()
 return dict(business_sha256=digest(json.dumps(rows,sort_keys=True,default=str)),counts={k:len(v) for k,v in rows.items()},audits={str(x['id']):{k:v for k,v in x.items() if k!='id'} for x in audits})


def refuse(api,tokens,path,records,body=None,actor='enterprise',status=403):
 result=call(api,tokens,path,body,actor=actor,expected=status)
 records.append(dict(path=path,method='GET' if body is None else 'POST',actor=actor,status=status,detail=result.get('detail')))


def invariant(state,before,records):
 after=snapshot(state)
 assert after['business_sha256']==before['business_sha256']
 assert after['counts']==before['counts']
 assert all(after['audits'].get(k)==v for k,v in before['audits'].items())
 added=[v for k,v in after['audits'].items() if k not in before['audits']]
 assert len(added)==sum(r['status']==403 for r in records)
 assert all(x['category']=='API_AUTHORIZATION' and x['outcome']=='DENIED' for x in added)
 return dict(business_before=before['business_sha256'],business_after=after['business_sha256'],counts=after['counts'],denial_audit_delta=added)


def test_bidirectional_foreign_parent_and_source_proof_refusal_without_business_writes(demo_state,tmp_path):
 state,marker,tokens=demo_state
 scopes=[demo.SCOPES[k] for k in ('primary','secondary')];sessions=[scope_tokens(tokens,s) for s in scopes]
 with server(state,tmp_path/'independent-parent-negatives') as (api,ready):
  prepared=[prepare_case(api,t,label,s) for t,label,s in zip(sessions,('INDEPENDENT_PRIMARY_NEW','INDEPENDENT_SECONDARY_NEW'),scopes)]
  previews=[call(api,t,'/api/preparations/'+p['preparation_id']+'/planning-preview')['current'] for t,(p,_) in zip(sessions,prepared)]
  assert previews[0]['source_sha256']!=previews[1]['source_sha256']
  before=snapshot(state);records=[]
  for i in (0,1):
   own,other=prepared[i][0],prepared[1-i][0];foreign='/api/preparations/'+other['preparation_id'];own_base='/api/preparations/'+own['preparation_id'];t=sessions[i]
   for path in ('/api/runs/'+other['run_id'],foreign,foreign+'/planning-preview',foreign+'/service-case-plan',foreign+'/goal-results',foreign+'/local-case'):
    refuse(api,t,path,records)
   refuse(api,t,foreign+'/commands',records,dict(action='ADD_EVIDENCE',expected_revision=other['revision'],slot='need_summary',text='SYNTHETIC forbidden foreign edit',source_kind='USER_STATEMENT',source_label='SYNTHETIC refused'))
   refuse(api,t,'/api/preparations',records,dict(run_id=other['run_id'],service_id='synthetic-material-preparation',service_version=1,reviewer_id=scopes[i]['ids']['specialist']))
   refuse(api,t,'/api/preparations',records,dict(run_id=own['run_id'],service_id='synthetic-material-preparation',service_version=1,reviewer_id=scopes[1-i]['ids']['specialist']))
   refuse(api,t,own_base+'/service-case-plan',records,dict(expected_preparation_revision=own['revision'],expected_request_revision=prepared[i][1],expected_source_sha256=previews[1-i]['source_sha256'],expected_plan_revision=0,required_goals=GOALS,reason='SYNTHETIC foreign source proof negative'),status=409)
   assert call(api,t,own_base+'/planning-preview')['current']==previews[i]
   listed=call(api,t,'/api/preparations')['items'];assert len(listed)==1 and listed[0]['id']==own['preparation_id']
  unchanged=invariant(state,before,records)
  assert unchanged['counts']['controlled_plans']==0 and unchanged['counts']['service_dispatches']==0
 evidence('independent-parent-and-source-proof',dict(ready=ready,refusals=records,invariants=unchanged,full_positive_chain=False,sql_business_seeding=False,run_assignments=0))


def file_hashes(path):
 result={}
 for file in sorted(path.rglob('*')):
  assert not file.is_symlink()
  if file.is_file():result[str(file.relative_to(path))]=dict(sha256=sha256(file.read_bytes()).hexdigest(),bytes=file.stat().st_size,mode=stat.S_IMODE(file.stat().st_mode))
 return result


def test_new_scope_binding_and_genuine_owned_old_schema_refuse_before_process(demo_state,monkeypatch):
 state,marker,_=demo_state;attempts=[]
 old=Path('/tmp/parkweave-ordinary-demo-0spo1vlc')
 # This exact retained state was created/stopped by this reviewer in the prior slice.
 assert old.is_dir() and not (old/'data/postmaster.pid').exists() and not (old/'stop-unconfirmed').exists()
 old_marker=json.loads((old/'state.json').read_text());assert old_marker['schema']=='parkweave-ordinary-synthetic-demo/1'
 assert old_marker['system_identifier']=='7698107962362137161'
 old_before=file_hashes(old)
 def forbidden(*args,**kwargs):attempts.append(True);raise AssertionError('a rejected scope state must not start a process')
 with monkeypatch.context() as patch:
  patch.setattr(demo.lifecycle,'postgres',forbidden)
  patch.setattr(demo.subprocess,'Popen',forbidden)
  with pytest.raises(Denied):demo.serve(old,port())
  assert file_hashes(old)==old_before
  changes=[]
  missing=deepcopy(marker);missing.pop('scopes');changes.append(('missing',missing))
  swapped=deepcopy(marker);swapped['scopes']['primary'],swapped['scopes']['secondary']=swapped['scopes']['secondary'],swapped['scopes']['primary'];changes.append(('swapped',swapped))
  changed=deepcopy(marker);changed['scopes']['secondary']['ids']['enterprise']=marker['scopes']['primary']['ids']['enterprise'];changes.append(('foreign-owner-id',changed))
  for label,bad in changes:
   raw=(json.dumps(bad)+'\n').encode();(state/'state.json').write_bytes(raw)
   with pytest.raises(Denied):demo.serve(state,port())
   assert (state/'state.json').read_bytes()==raw and not (state/'data/postmaster.pid').exists()
 assert not attempts
 old_after=file_hashes(old);assert old_before==old_after
 evidence('independent-old-state-before',dict(state_dir=str(old),files=old_before))
 evidence('independent-old-state-after',dict(state_dir=str(old),files=old_after))
 evidence('independent-scope-binding',dict(old_schema=old_marker['schema'],old_system_identifier=old_marker['system_identifier'],old_files_hashed=len(old_before),old_session_values_read=False,old_process_started=False,old_all_file_hashes_unchanged=True,new_scope_mutations=[x[0] for x in changes],process_attempts=0,new_negative_state_retained=True))


def test_foreign_resource_and_mixed_combination_refusal_preserves_both_scopes(demo_state,tmp_path):
 state,marker,tokens=demo_state
 scopes=[demo.SCOPES[k] for k in ('primary','secondary')];sessions=[scope_tokens(tokens,s) for s in scopes]
 now=datetime.now(timezone.utc);window=dict(starts_at=(now+timedelta(hours=1)).isoformat(),ends_at=(now+timedelta(hours=2)).isoformat(),quantity=1)
 with server(state,tmp_path/'independent-resource-negatives') as (api,ready):
  holds=[];groups=[]
  for t,s in zip(sessions,scopes):
   catalog=call(api,t,'/api/synthetic-resources')['items'];assert {r['id'] for r in catalog}=={r['id'] for r in s['resources']}
   own=[call(api,t,'/api/synthetic-resources/'+r['id']+'/holds',dict(**window,expected_revision=1,ttl_seconds=120,purpose='SYNTHETIC INDEPENDENT '+s['org_id']),expected=201)['hold'] for r in s['resources']]
   group=call(api,t,'/api/resource-combinations',dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in own]),expected=201)['combination']
   holds.append(own);groups.append(group)
  before=snapshot(state);records=[]
  for i in (0,1):
   t=sessions[i];foreign_resource=scopes[1-i]['resources'][0]['id'];foreign_hold=holds[1-i][0]['id'];foreign_group=groups[1-i]['id']
   refuse(api,t,'/api/synthetic-resources/'+foreign_resource+'/preview',records,window)
   refuse(api,t,'/api/synthetic-resources/'+foreign_resource+'/holds',records,dict(**window,expected_revision=1,ttl_seconds=120,purpose='SYNTHETIC refused foreign resource'))
   refuse(api,t,'/api/resource-holds/'+foreign_hold,records)
   refuse(api,t,'/api/resource-holds/'+foreign_hold+'/release',records,{})
   refuse(api,t,'/api/resource-combinations/'+foreign_group,records)
   refuse(api,t,'/api/resource-combinations/'+foreign_group+'/cancel',records,{})
   refuse(api,t,'/api/resource-combinations',records,dict(members=[dict(hold_id=holds[i][0]['id'],expected_revision=1),dict(hold_id=foreign_hold,expected_revision=1)]))
   assert call(api,t,'/api/resource-combinations/'+groups[i]['id'])['combination']==groups[i]
   listed=call(api,t,'/api/resource-holds')['items'];assert len(listed)==2 and all(h['resource_id'] in {r['id'] for r in scopes[i]['resources']} for h in listed)
  unchanged=invariant(state,before,records)
  assert unchanged['counts']['runs']==0 and unchanged['counts']['cases']==0
 evidence('independent-cross-resource',dict(ready=ready,window=window,group_ids=[g['id'] for g in groups],refusals=records,invariants=unchanged,same_exact_interval=True,distinct_authorized_resource_sets=True,sql_business_seed=False,full_positive_chain=False))
