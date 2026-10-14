from conftest import pg,fixture
from test_template_consumer import template_consumption,products
from test_manual_goal_privacy import private_case,replace_plan,A,B
from test_manual_goal_requests import read,post,body
from test_manual_goal_tasks import confirmed
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
from uuid import uuid4
from copy import deepcopy
from psycopg.types.json import Jsonb
import pytest


def setup(f):
 row=private_case(f);confirmed(f,row)
 for a,u,k in [('REQUEST',None,'original-old-request'),('TAKE',REVIEWERS[0],'original-old-take')]:
  v=read(f,row,user=u).json();r=post(f,row,{**body(v,a),'goal':A},k,user=u);assert r.status_code==200,r.text
 return row

def reply(f,row,kind='INFORMATION'):
 v=read(f,row,user=REVIEWERS[0]).json();d={**body(v,'REPLY'),'goal':A,'reply_kind':kind}
 if kind=='INFORMATION':d['evidence']=[{k:v['materials'][0][k] for k in ('id','version','source_sha256')}]
 return d

def ack(f,row):
 v=read(f,row).json();e=next(x for x in v['items'] if x['goal']==A)['reply'];return {**body(v,'ACKNOWLEDGE_REPLY'),'goal':A,'reply_event_id':e['id'],'reply_fingerprint':e['fingerprint']}

def responded(f,kind='INFORMATION'):
 row=setup(f);d=reply(f,row,kind);r=post(f,row,d,'ind-reply',user=REVIEWERS[0]);assert r.status_code==200,r.text;return row,d,r.json()['event']

@pytest.mark.parametrize('kind',['INFORMATION','UNABLE_TO_HANDLE'])
def test_reply_awareness_only_mutates_manual_ledger_and_original_history_compatible(template_consumption,kind):
 f=template_consumption;row=setup(f);before=deepcopy(products(f['owner']));grants=grant_snapshot(f['owner']);d=reply(f,row,kind);r=post(f,row,d,'ind-reply',user=REVIEWERS[0]);assert r.status_code==200,r.text
 assert B not in r.text
 assert read(f,row,'original-old-request').json()['status']=='COMMITTED';assert read(f,row,'original-old-take',user=REVIEWERS[0]).json()['status']=='COMMITTED'
 v=read(f,row).json();assert v['items'][0]['reply']['truth_verified'] is False and v['items'][0]['reply']['awareness_proves_reading'] is False
 a=ack(f,row);r=post(f,row,a,'ind-ack');assert r.status_code==200,r.text;assert r.json()['items'][0]['state']=='COORDINATION_ENDED' and r.json()['items'][0]['allowed_actions']==[]
 assert r.json()['overall_goal_state']=='PARTIAL' and not r.json()['case_goal_completed'];assert r.json()['items'][1]['state']=='NOT_REQUESTED'
 after=deepcopy(products(f['owner']));
 for data in (before,after):
  for p in data['preparations']:p['service_case_plan'].pop('manual_goal_requests',None)
 assert after==before and grant_snapshot(f['owner'])==grants

@pytest.mark.parametrize('field',['reply_event_id','reply_fingerprint','goal'])
def test_exact_reply_cross_goal_or_forged_refusal_is_zero_write(template_consumption,field):
 f=template_consumption;row,_,_=responded(f);a=ack(f,row);a[field]=str(uuid4()) if field=='reply_event_id' else '0'*64 if field=='reply_fingerprint' else B
 before=products(f['owner']);r=post(f,row,a,'invalid-binding');assert r.status_code==409,r.text;assert products(f['owner'])==before

@pytest.mark.parametrize('actor',[ENTERPRISES[0],REVIEWERS[0]])
def test_current_authority_revocation_denies_reply_or_ack_cached_recovery(template_consumption,actor):
 f=template_consumption;row,d,e=responded(f);a=ack(f,row)
 if actor==ENTERPRISES[0]:
  r=post(f,row,a,'ind-ack');assert r.status_code==200;key='ind-ack';data=a
 else:key='ind-reply';data=d
 with f['owner'].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(actor,))
 before=products(f['owner']);assert read(f,row,key,user=actor).status_code==403;assert post(f,row,data,key,user=actor).status_code==403;assert products(f['owner'])==before


def test_lost_reply_then_actual_plan_replacement_original_key_never_changes_new_ledger(template_consumption):
 f=template_consumption;row,d,e=responded(f);a=ack(f,row);first=post(f,row,a,'ind-ack');assert first.status_code==200;event=first.json()['event']
 replace_plan(f,row);before=products(f['owner'],True)
 for u,key,data,original in [(REVIEWERS[0],'ind-reply',d,e),(None,'ind-ack',a,event)]:
  r=read(f,row,key,user=u);assert r.status_code==200,r.text;assert r.json()['status']=='COMMITTED' and r.json()['event']==original
  cached=post(f,row,data,key,user=u);assert cached.status_code==200 and cached.json()['event']==original
  assert post(f,row,{**data,'reason':'SYNTHETIC changed'},key,user=u).status_code==409
 assert products(f['owner'],True)==before
 assert read(f,row).json()['items'][0]['state']=='NOT_REQUESTED'


def test_damage_ack_proof_fails_closed_in_all_read_projections(template_consumption):
 f=template_consumption;row,_,_=responded(f);a=ack(f,row);assert post(f,row,a,'ind-ack').status_code==200
 with f['owner'].connect() as c:
  p=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan'];p['manual_goal_requests'][-1]['request']['reply_fingerprint']='0'*64;c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(p),row['preparation_id']))
 before=products(f['owner']);assert read(f,row).status_code==409;assert read(f,row,user=REVIEWERS[0]).status_code==409
 r=f['client'].get('/api/preparation-tasks',headers={'Authorization':'Bearer '+f['tokens'][REVIEWERS[0]]});assert r.status_code==200 and A not in r.text and B not in r.text;assert products(f['owner'])==before

@pytest.mark.parametrize('bad',['missing_information_evidence','ack_without_exact_reply'])
def test_command_schema_rejects_implicit_reply_awareness(template_consumption,bad):
 f=template_consumption;row=setup(f);d=reply(f,row)
 if bad=='missing_information_evidence':d['evidence']=[]
 else:d={**body(read(f,row).json(),'ACKNOWLEDGE_REPLY'),'goal':A}
 before=products(f['owner']);r=post(f,row,d,'implicit',user=REVIEWERS[0]);assert r.status_code==422;assert products(f['owner'])==before

def test_owned_pg_wait_source_update_wins_before_awareness_and_receipt_remains(template_consumption):
 from concurrent.futures import ThreadPoolExecutor
 import time,json
 from pathlib import Path
 from parkweave.preparation import _insert_evidence
 f=template_consumption;row,_,original=responded(f);a=ack(f,row);observed=False
 with ThreadPoolExecutor(1) as pool:
  with f['owner'].connect() as holder:
   parent=holder.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],)).fetchone();pid=holder.execute('SELECT pg_backend_pid() AS id').fetchone()['id']
   future=pool.submit(post,f,row,a,'ind-wait-ack');end=time.monotonic()+2
   with f['owner'].connect() as monitor:
    while time.monotonic()<end:
     monitor.execute('SELECT pg_stat_clear_snapshot()');observed=monitor.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND %s=ANY(pg_blocking_pids(pid))) AS yes',(pid,)).fetchone()['yes']
     if observed:break
     time.sleep(.01)
   assert observed,'actual owned PG blocker must be observed'
   actor=holder.execute('SELECT * FROM principals WHERE id=%s',(ENTERPRISES[0],)).fetchone();_insert_evidence(holder,actor,parent,'material_outline','SYNTHETIC independent newer material','DOCUMENT_EXCERPT','SYNTHETIC changed after reply')
  result=future.result(timeout=5);assert result.status_code==409,result.text
 current=read(f,row).json();assert current['items'][0]['state']=='WAITING_OWNER_ACKNOWLEDGEMENT' and 'ACKNOWLEDGE_REPLY' not in current['items'][0]['allowed_actions']
 assert read(f,row,'ind-reply',user=REVIEWERS[0]).json()['event']==original
 Path('.runtime/manual-goal-reply-20261014/independent/pg-wait.json').write_text(json.dumps({'actual_owned_pg_wait_observed':observed,'response':result.status_code,'state':current['items'][0]['state'],'reply_history_retained':True})+'\n')
