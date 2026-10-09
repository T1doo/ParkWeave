"""Original F3-T02 bounded Case opportunity business path over actual PG/API."""
import json,hashlib
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4,UUID
import pytest,psycopg
from parkweave.store import Store
from parkweave import case_opportunities as op
from test_preparation import preparation_fixture,filled,add,headers

def get(f,p,user='fixture-a'):
 return f[3].get('/api/preparations/'+p['preparation_id']+'/opportunities',headers=headers(f[2],user))
def recovery(f,p,key,user='fixture-a'):
 return f[3].get('/api/preparations/'+p['preparation_id']+'/opportunities/recovery/'+key,headers=headers(f[2],user))
def entry(**kw):
 b=dict(family_id=str(uuid4()),generation=1,kind='LOCAL_CASE_DATA',catalog_version=1,title='SYNTHETIC 新资料变化待人工审阅',note='SYNTHETIC 未核验提示，不是资格结论');b.update(kw);return b

def body(view,action='IMPORT',item=None,card=None):
 b=dict(action=action,expected_revision=view['revision'],expected_source_sha256=view['source_sha256'],reason='SYNTHETIC 明确本事项机会操作')
 if action=='IMPORT':b['entry']=item or entry()
 elif action in ('IGNORE','WITHDRAW'):b.update(card_id=card['id'],expected_card_version=card['version'])
 return b

def post(f,p,b,key=None,user='fixture-a'):
 return f[3].post('/api/preparations/'+p['preparation_id']+'/opportunities/commands',headers=headers(f[2],user,key or uuid4().hex),json=b)
def imported(f,p=None,item=None):
 p=p or filled(f);r=post(f,p,body(get(f,p).json(),item=item));assert r.status_code==200,r.text;return p,r.json()['current'],r.json()['receipt']
def business(f,include_opportunities=False):
 with f[1].connect() as c:
  tables=('cases','runs','preparation_events','preparation_evidence','field_grants','capability_grants','preparation_grants','controlled_plans','controlled_plan_events','case_local_lifecycles','case_local_events','synthetic_resource_holds','case_resource_links')
  data={t:c.execute('SELECT row_to_json(x) r FROM '+t+' x ORDER BY row_to_json(x)::text').fetchall() for t in tables}
  data['preparations']=c.execute("SELECT to_jsonb(p)"+("" if include_opportunities else "-'opportunities'")+" r FROM preparations p ORDER BY id").fetchall()
 return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()


def test_complete_import_refresh_ignore_withdraw_new_generation_and_restart(preparation_fixture):
 f=preparation_fixture;p=filled(f);before=business(f);item=entry();key=uuid4().hex;r=post(f,p,body(get(f,p).json(),item=item),key);assert r.status_code==200,r.text;x=r.json()['current'];assert x['cards'][0]['state']=='PENDING_REVIEW' and business(f)==before
 assert recovery(f,p,key).json()['receipt']==r.json()['receipt']
 add(f,p,text='SYNTHETIC new material revision');old=get(f,p).json();assert not old['cards'][0]['source_binding_current'];before=business(f)
 x=post(f,p,body(old,'REFRESH')).json()['current'];assert x['cards'][0]['source_binding_current'] and x['cards'][0]['version']==2 and business(f)==before
 x=post(f,p,body(x,'IGNORE',card=x['cards'][0])).json()['current'];assert x['cards'][0]['state']=='IGNORED';hist=deepcopy(x['history'])
 dup=post(f,p,body(x,item=item)).json();assert dup['receipt']['outcome']=='DUPLICATE' and len(dup['current']['cards'])==1 and dup['current']['cards'][0]['state']=='IGNORED';x=dup['current']
 x=post(f,p,body(x,'REFRESH')).json()['current'];assert x['cards'][0]['state']=='IGNORED';x=post(f,p,body(x,'WITHDRAW',card=x['cards'][0])).json()['current'];assert x['cards'][0]['state']=='WITHDRAWN'
 x=post(f,p,body(x,item={**item,'generation':2,'note':'SYNTHETIC 明确新来源版本'})).json()['current'];assert len(x['cards'])==2 and x['cards'][0]['state']=='WITHDRAWN' and not x['cards'][0]['is_latest_generation'] and x['cards'][1]['state']=='PENDING_REVIEW';assert x['history'][:len(hist)]==hist and business(f)==before
 fresh=op.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']));assert fresh==x and not x['case_goal_completed'] and not x['business_publication']

@pytest.mark.parametrize('bad',['content','older','kind','catalog','ledger','source','card'])
def test_conflicts_never_change_original_business_or_opportunity_history(preparation_fixture,bad):
 f=preparation_fixture;item=entry(generation=2);p,x,_=imported(f,item=item)
 if bad in ('content','older','kind','catalog'):
  e=deepcopy(item)
  if bad=='content':e['note']='SYNTHETIC changed same generation'
  if bad=='older':e['generation']=1
  if bad=='kind':e.update(generation=3,kind='LOCAL_SERVICE_VERSION')
  if bad=='catalog':e.update(generation=3,catalog_version=999)
  b=body(x,item=e)
 elif bad=='ledger':b=body(x,'REFRESH');b['expected_revision']=0
 elif bad=='source':b=body(x,'REFRESH');b['expected_source_sha256']='0'*64
 else:b=body(x,'IGNORE',card=x['cards'][0]);b['expected_card_version']=2
 before=business(f,True);assert post(f,p,b).status_code==409 and business(f,True)==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_other_enterprise_park_and_role_get_post_recovery_disclose_nothing(preparation_fixture,user):
 f=preparation_fixture;p,x,e=imported(f);before=business(f,True)
 for r in (get(f,p,user),post(f,p,body(x,'REFRESH'),user=user),recovery(f,p,e['request_key'],user)):
  assert r.status_code==403 and 'SYNTHETIC 未核验提示' not in r.text and 'receipt' not in r.text
 assert business(f,True)==before

@pytest.mark.parametrize('right',['READ','PREPARE','EXECUTE','ACTIVE'])
def test_revoke_read_and_write_intersection_current_history_never_restores_rights(preparation_fixture,right):
 f=preparation_fixture;p,x,e=imported(f)
 with f[1].connect() as c:
  if right=='ACTIVE':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
  elif right=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
  else:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',right))
 before=business(f,True);assert get(f,p).status_code==(200 if right=='EXECUTE' else 403);assert recovery(f,p,e['request_key']).status_code==(200 if right=='EXECUTE' else 403);assert post(f,p,body(x,'REFRESH')).status_code==403;assert business(f,True)==before


def test_same_key_replay_different_key_duplicate_and_cross_case_key(preparation_fixture):
 f=preparation_fixture;p=filled(f);x=get(f,p).json();b=body(x);key=uuid4().hex;r=post(f,p,b,key);assert r.status_code==200;before=business(f,True)
 assert post(f,p,b,key).json()['receipt']==r.json()['receipt'] and business(f,True)==before
 assert post(f,p,{**b,'reason':'SYNTHETIC different body'},key).status_code==409
 p2=filled(f);b2=body(get(f,p2).json());before=business(f,True);assert post(f,p2,b2,key).status_code==409 and recovery(f,p2,key).status_code==409 and business(f,True)==before
 unknown=recovery(f,p,uuid4().hex);assert unknown.json()['status']=='NOT_OBSERVED' and business(f,True)==before


def test_parallel_cas_and_parallel_same_key_have_one_card_effect(preparation_fixture):
 f=preparation_fixture;p=filled(f);b=body(get(f,p).json());key=uuid4().hex
 with ThreadPoolExecutor(max_workers=2) as pool:rs=list(pool.map(lambda _:post(f,p,b,key),range(2)))
 assert all(r.status_code==200 for r in rs) and len(get(f,p).json()['cards'])==1 and len(get(f,p).json()['history'])==1
 x=get(f,p).json();b=body(x,'IGNORE',card=x['cards'][0])
 with ThreadPoolExecutor(max_workers=2) as pool:rs=list(pool.map(lambda _:post(f,p,b),range(2)))
 assert sorted(r.status_code for r in rs)==[200,409] and len(get(f,p).json()['history'])==2

@pytest.mark.parametrize('bad',['binding','event','chain','project','version-bool'])
def test_corrupt_scope_or_history_is_not_returned_as_private_committed_result(preparation_fixture,bad):
 f=preparation_fixture;p,x,e=imported(f)
 with f[1].connect() as c:
  v=c.execute('SELECT opportunities FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['opportunities']
  if bad=='version-bool':v['version']=True
  elif bad=='binding':v['binding']['case_id']=str(uuid4())
  elif bad=='event':v['events'][0]['reason']='changed'
  elif bad=='chain':v['events'][0]['previous_sha256']='0'*64
  else:
   card=v['events'][0]['payload']['card'];card['basis']['binding']['run_id']=str(uuid4());card['basis_sha256']=op.sha(card['basis']);v['events'][0]['sha256']=op.sha({k:z for k,z in v['events'][0].items() if k!='sha256'})
  c.execute('UPDATE preparations SET opportunities=%s WHERE id=%s',(psycopg.types.json.Jsonb(v),p['preparation_id']))
 before=business(f,True);assert get(f,p).status_code==409 and recovery(f,p,e['request_key']).status_code==409 and business(f,True)==before

@pytest.mark.parametrize('patch',[{'action':'APPROVE'},{'park_id':'park-b'},{'expected_revision':True},{'reason':' '},{'reason':'x'*1001},{'expected_source_sha256':'bad'}])
def test_bounded_shapes_reject_before_any_business_effect(preparation_fixture,patch):
 f=preparation_fixture;p=filled(f);b=body(get(f,p).json());before=business(f,True);assert post(f,p,{**b,**patch}).status_code==422 and business(f,True)==before


def test_fixture_only_migration_retains_business_and_authority_and_no_new_grants(preparation_fixture):
 f=preparation_fixture;p,x,e=imported(f);before=business(f,True);f[1].migrate();Store(f[1].dsn).migrate();assert business(f,True)==before
 sql=Path('src/parkweave/migration-027.sql').read_text()
 with pytest.raises(psycopg.errors.RaiseException,match='creation ticket required'):
  with f[1].connect() as c:c.execute(sql)
 with f[1].connect() as c:f[1]._case_fact_fixture_receipt.authorize_migration(c);c.execute(sql)
 assert business(f,True)==before
 with f[1].connect() as c:c.execute('ALTER TABLE preparations DROP COLUMN opportunities')
 assert get(f,p).status_code==409


def test_family_card_and_history_bounds_are_real_persistent_limits(preparation_fixture):
 f=preparation_fixture;p=filled(f);x=get(f,p).json();first=None
 for _ in range(8):
  b=body(x);first=first or b['entry'];r=post(f,p,b);assert r.status_code==200;r=r.json();x=r['current']
 before=business(f,True);assert post(f,p,body(x)).status_code==409 and business(f,True)==before
 for generation in range(2,10):
  r=post(f,p,body(x,item={**first,'generation':generation}));assert r.status_code==200;x=r.json()['current']
 assert len(x['cards'])==16
 before=business(f,True);assert post(f,p,body(x,item={**first,'generation':10})).status_code==409 and business(f,True)==before
 for _ in range(128-x['revision']):r=post(f,p,body(x,'REFRESH'));assert r.status_code==200;x=r.json()['current']
 before=business(f,True);assert post(f,p,body(x,'REFRESH')).status_code==409 and business(f,True)==before


def test_generic_preparation_readiness_and_task_views_never_include_private_opportunity_import(preparation_fixture):
 f=preparation_fixture;p,x,e=imported(f,item=entry(note='SYNTHETIC PRIVATE_OPPORTUNITY_NOTE'));before=business(f,True)
 for user in ('fixture-a','prep-specialist-fixture-a'):
  for suffix in ('','/readiness'):
   r=f[3].get('/api/preparations/'+p['preparation_id']+suffix,headers=headers(f[2],user));assert r.status_code==200
   assert 'PRIVATE_OPPORTUNITY_NOTE' not in r.text and 'opportunities' not in r.json().get('preparation',{})
  r=f[3].get('/api/preparation-tasks',headers=headers(f[2],user));assert r.status_code==200 and 'PRIVATE_OPPORTUNITY_NOTE' not in r.text
 assert business(f,True)==before


def test_transaction_failure_after_ledger_update_rolls_back_whole_opportunity_event(preparation_fixture,monkeypatch):
 f=preparation_fixture;p=filled(f);b=body(get(f,p).json());before=business(f,True)
 def fail(*a,**k):raise RuntimeError('SYNTHETIC after opportunity update')
 monkeypatch.setattr(op,'view',fail)
 with pytest.raises(RuntimeError):post(f,p,b)
 assert business(f,True)==before


def test_catalog_change_and_unavailable_source_never_become_current_or_published(preparation_fixture):
 from psycopg.types.json import Jsonb
 f=preparation_fixture;p,x,e=imported(f);before=business(f)
 with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=%s WHERE service_id=%s",(Jsonb({'kind':'SYNTHETIC','revision':'2','label':'SYNTHETIC changed catalog bytes'}),op.prep.SERVICE))
 x=get(f,p).json();assert not x['cards'][0]['source_binding_current'];x=post(f,p,body(x,'REFRESH')).json()['current'];assert x['cards'][0]['source_binding_current'] and business(f)==before
 with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=%s WHERE service_id=%s",(Jsonb({'kind':'UNREVIEWED_REAL_SOURCE'}),op.prep.SERVICE))
 x=get(f,p).json();assert not x['cards'][0]['current_catalog_available'];x=post(f,p,body(x,'REFRESH')).json()['current'];assert not x['cards'][0]['source_binding_current'] and not x['business_publication'] and business(f)==before


def test_recovery_key_lock_timeout_stays_unknown_then_only_reads_original(preparation_fixture):
 import threading,time
 f=preparation_fixture;p,x,e=imported(f);key=e['request_key'];results=[];before=business(f,True)
 with f[1].connect() as c:
  c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('opportunity-key:fixture-a:'+key,));t=threading.Thread(target=lambda:results.append(recovery(f,p,key)));t.start();t.join(5);assert not t.is_alive() and results[0].status_code==409
 assert business(f,True)==before and recovery(f,p,key).json()['status']=='COMMITTED' and business(f,True)==before
