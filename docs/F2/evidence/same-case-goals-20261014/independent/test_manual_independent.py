from conftest import fixture,pg
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_case_resources import link_fixture
from test_partial_service_plan import setup_partial,UNKNOWN
from test_service_case_steps import adopt,adopt_body
from test_service_dispatches import REVIEWER
from test_case_goal_results import snapshot
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest

def setup(f):
 p=setup_partial(f);r=adopt(f,p,adopt_body(f,p,partial_adoption=True));assert r.status_code==201,r.text;return p

def get(f,p,user='fixture-a',key=None):
 return f[3].get('/api/preparations/'+p['preparation_id']+'/manual-goal-requests'+('/recovery/'+key if key else ''),headers=headers(f[2],user))
def payload(v,action='REQUEST',**extra):
 return dict(action=action,plan_id=v['plan_id'],goal=UNKNOWN,expected_revision=v['revision'],expected_source_sha256=v['source_sha256'],reason='SYNTHETIC independent explicit coordination',**extra)
def post(f,p,b,user='fixture-a',key=None):
 return f[3].post('/api/preparations/'+p['preparation_id']+'/manual-goal-requests',headers=headers(f[2],user,key or uuid4().hex),json=b)

def test_actual_original_roles_keep_partial_and_exact_get_recovery(link_fixture):
 f=link_fixture;p=setup(f);v=get(f,p).json();b=payload(v);r=post(f,p,b,key='ind-request');assert r.status_code==200,r.text;original=r.json()['event']
 r=post(f,p,b,key='ind-request');assert r.status_code==200 and r.json()['event']==original
 assert post(f,p,b|dict(reason='SYNTHETIC changed'),key='ind-request').status_code==409
 before=snapshot(f);r=get(f,p,key='ind-request');assert r.status_code==200 and r.json()['event']==original and r.json()['automatically_replayed'] is False;assert snapshot(f)==before
 v=get(f,p,REVIEWER).json();assert post(f,p,payload(v,'TAKE'),REVIEWER).status_code==200
 v=get(f,p,REVIEWER).json();assert post(f,p,payload(v,'REQUEST_EVIDENCE'),REVIEWER).status_code==200
 v=get(f,p).json();m=v['materials'][0];r=post(f,p,payload(v,'SUPPLY_EVIDENCE',evidence=[{k:m[k] for k in ['id','version','source_sha256']}]));assert r.status_code==200,r.text
 v=get(f,p,REVIEWER).json();assert post(f,p,payload(v,'TAKE'),REVIEWER).status_code==200
 out=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2])).json();assert out['state']=='PARTIAL';assert out['results'][-1]['state']=='UNSUPPORTED';assert not out['case_goal_completed']

@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-a'])
def test_actual_foreign_principal_cannot_read_write_or_recover(link_fixture,user):
 f=link_fixture;p=setup(f);v=get(f,p).json();assert post(f,p,payload(v),key='ind-private').status_code==200;before=snapshot(f)
 assert get(f,p,user).status_code==403 and get(f,p,user,'ind-private').status_code==403 and post(f,p,payload(v),user).status_code==403;assert snapshot(f)==before

def test_different_key_actual_pg_compare_and_swap_is_single_winner(link_fixture):
 f=link_fixture;p=setup(f);b=payload(get(f,p).json())
 with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda _:post(f,p,b),range(2)))
 assert sorted(r.status_code for r in rs)==[200,409]
 assert get(f,p).json()['revision']==1

def test_same_key_actual_pg_is_one_event(link_fixture):
 f=link_fixture;p=setup(f);b=payload(get(f,p).json())
 with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda _:post(f,p,b,key='ind-concurrent'),range(2)))
 assert [r.status_code for r in rs]==[200,200];assert rs[0].json()['event']==rs[1].json()['event'];assert get(f,p).json()['revision']==1

@pytest.mark.parametrize('damage',['revision-bool','duplicate-id','fingerprint','actor','state'])
def test_corrupted_actual_stored_request_proof_fails_closed(link_fixture,damage):
 from psycopg.types.json import Jsonb
 f=link_fixture;p=setup(f);assert post(f,p,payload(get(f,p).json()),key='ind-proof').status_code==200
 assert post(f,p,payload(get(f,p,REVIEWER).json(),'TAKE'),REVIEWER,key='ind-proof-take').status_code==200
 with f[1].connect() as c:
  plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'];events=plan['manual_goal_requests']
  if damage=='revision-bool':events[0]['revision']=True
  elif damage=='duplicate-id':events[1]['id']=events[0]['id']
  elif damage=='fingerprint':events[0]['fingerprint']='0'*64
  elif damage=='actor':events[0]['actor_id']=REVIEWER
  else:events[0]['state']='FULFILLED'
  c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
 before=snapshot(f);assert get(f,p).status_code==409;assert get(f,p,key='ind-proof').status_code==409;assert snapshot(f)==before

@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_original_owner_authority_revoke_before_write_keeps_actual_ledger(link_fixture,capability):
 f=link_fixture;p=setup(f);b=payload(get(f,p).json())
 with f[1].connect() as c:
  table='preparation_grants' if capability=='PREPARE' else 'capability_grants';c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(capability,))
 before=snapshot(f);assert post(f,p,b).status_code==403;assert snapshot(f)==before
 if capability!='EXECUTE':assert get(f,p).status_code==403 and get(f,p,key='ind-none').status_code==403

def test_cross_case_original_key_conflict_never_rebinds(link_fixture):
 f=link_fixture;p=setup(f);q=setup(f);b=payload(get(f,p).json());assert post(f,p,b,key='ind-global-case-key').status_code==200;before=snapshot(f)
 assert post(f,q,payload(get(f,q).json()),key='ind-global-case-key').status_code==409
 assert get(f,q,key='ind-global-case-key').status_code==409;assert snapshot(f)==before

def test_cross_case_same_original_key_concurrency_has_one_global_winner(link_fixture):
 f=link_fixture;parents=[setup(f),setup(f)];bodies=[payload(get(f,p).json()) for p in parents]
 with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda i:post(f,parents[i],bodies[i],key='ind-global-concurrent'),range(2)))
 assert sorted(r.status_code for r in rs)==[200,409]
 assert sum(get(f,p).json()['revision'] for p in parents)==1

def test_actual_material_bytes_damage_marks_supplement_stale_without_closing_goal(link_fixture):
 f=link_fixture;p=setup(f);v=get(f,p).json();assert post(f,p,payload(v)).status_code==200
 v=get(f,p,REVIEWER).json();assert post(f,p,payload(v,'TAKE'),REVIEWER).status_code==200
 v=get(f,p,REVIEWER).json();assert post(f,p,payload(v,'REQUEST_EVIDENCE'),REVIEWER).status_code==200
 v=get(f,p).json();m=v['materials'][0];assert post(f,p,payload(v,'SUPPLY_EVIDENCE',evidence=[{k:m[k] for k in ['id','version','source_sha256']}])).status_code==200
 with f[1].connect() as c:c.execute('UPDATE preparation_evidence SET text=text||%s WHERE id=%s',(' SYNTHETIC changed underlying bytes',m['id']))
 before=snapshot(f);v=get(f,p).json();assert v['items'][0]['supplement_state']=='STALE';assert v['items'][0]['allowed_actions']==[];assert v['items'][0]['goal_state']=='UNSUPPORTED';assert not v['case_goal_completed'];assert v['overall_goal_state']=='PARTIAL';assert snapshot(f)==before
 assert post(f,p,payload(v,'TAKE'),REVIEWER).status_code==409;assert snapshot(f)==before
