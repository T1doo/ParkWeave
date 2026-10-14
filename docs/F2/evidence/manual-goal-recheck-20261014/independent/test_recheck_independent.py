from conftest import pg,fixture
from test_template_consumer import template_consumption,products
from test_manual_goal_reply import replied,reply_data,ack_data,command
from test_manual_goal_privacy import A,B,replace_plan
from test_manual_goal_requests import read,post
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
from copy import deepcopy
from uuid import uuid4
from psycopg.types.json import Jsonb
import pytest


def request(v):
 e=next(i for i in v['items'] if i['goal']==A)['reply'];return command(v,'REQUEST_RECHECK',reply_event_id=e['id'],reply_fingerprint=e['fingerprint'])

def take(v):
 i=next(i for i in v['items'] if i['goal']==A);r=i['reply'];q=i['recheck'];return command(v,'TAKE_RECHECK',reply_event_id=r['id'],reply_fingerprint=r['fingerprint'],recheck_event_id=q['id'],recheck_fingerprint=q['fingerprint'])

def applied(f):
 row,_=replied(f);d=request(read(f,row).json());r=post(f,row,d,'ind-recheck');assert r.status_code==200,r.text;return row,d,r.json()['event']

@pytest.mark.parametrize('ended',[False,True])
def test_explicit_request_take_new_reply_awareness_only_changes_human_ledger(template_consumption,ended):
 f=template_consumption;row,_=replied(f);old=read(f,row,'original-reply',user=REVIEWERS[0]).json()['event']
 if ended:assert post(f,row,ack_data(read(f,row).json()),'old-ack').status_code==200
 before=deepcopy(products(f['owner']));grants=grant_snapshot(f['owner']);q=request(read(f,row).json());r=post(f,row,q,'ind-recheck');assert r.status_code==200,r.text
 i=r.json()['items'][0];assert i['state']=='RECHECK_REQUESTED' and i['responsible_actor_id'] is None
 v=read(f,row,user=REVIEWERS[0]).json();assert B not in str(v);assert v['items'][0]['allowed_actions']==['TAKE_RECHECK'];t=take(v)
 r=post(f,row,t,'ind-take',user=REVIEWERS[0]);assert r.status_code==200,r.text;assert r.json()['items'][0]['state']=='UNDER_MANUAL_RECHECK'
 assert r.json()['items'][0]['allowed_actions']==['REPLY'];assert post(f,row,reply_data(read(f,row,user=REVIEWERS[0]).json()),'ind-new-reply',user=REVIEWERS[0]).status_code==200
 r=post(f,row,ack_data(read(f,row).json()),'ind-new-ack');assert r.status_code==200 and r.json()['items'][0]['state']=='COORDINATION_ENDED';assert r.json()['overall_goal_state']=='PARTIAL' and r.json()['case_goal_completed'] is False
 assert read(f,row,'original-reply',user=REVIEWERS[0]).json()['event']==old
 after=deepcopy(products(f['owner']))
 for data in (before,after):
  for p in data['preparations']:p['service_case_plan'].pop('manual_goal_requests',None)
 assert after==before and grant_snapshot(f['owner'])==grants

@pytest.mark.parametrize('field',['reply_event_id','reply_fingerprint','recheck_event_id','recheck_fingerprint'])
def test_original_specialist_take_requires_exact_application_and_reply(template_consumption,field):
 f=template_consumption;row,_,_=applied(f);d=take(read(f,row,user=REVIEWERS[0]).json());d[field]=str(uuid4()) if field.endswith('_id') else '0'*64
 before=products(f['owner']);assert post(f,row,d,'wrong-take',user=REVIEWERS[0]).status_code==409;assert products(f['owner'])==before


def test_old_reply_cannot_acknowledge_new_round_but_old_key_receipt_survives(template_consumption):
 f=template_consumption;row,_,_=applied(f);old=read(f,row).json()['items'][0]['reply'];assert post(f,row,take(read(f,row,user=REVIEWERS[0]).json()),'ind-take',user=REVIEWERS[0]).status_code==200
 assert post(f,row,reply_data(read(f,row,user=REVIEWERS[0]).json()),'ind-new-reply',user=REVIEWERS[0]).status_code==200;d=ack_data(read(f,row).json());d.update(reply_event_id=old['id'],reply_fingerprint=old['fingerprint']);before=products(f['owner']);assert post(f,row,d,'old-reply-ack').status_code==409;assert products(f['owner'])==before
 assert read(f,row,'original-reply',user=REVIEWERS[0]).json()['event']['id']==old['id']

@pytest.mark.parametrize('action',['REPLY','TAKE_RECHECK'])
def test_no_implicit_resume_or_owner_specialist_acceptance(template_consumption,action):
 f=template_consumption;row,_,_=applied(f);d=reply_data(read(f,row,user=REVIEWERS[0]).json()) if action=='REPLY' else take(read(f,row).json());user=REVIEWERS[0] if action=='REPLY' else None
 before=products(f['owner']);assert post(f,row,d,'implicit-resume',user=user).status_code==409;assert products(f['owner'])==before


def test_actual_plan_replace_old_application_and_take_keys_are_historical_only(template_consumption):
 f=template_consumption;row,q,qe=applied(f);t=take(read(f,row,user=REVIEWERS[0]).json());r=post(f,row,t,'ind-take',user=REVIEWERS[0]);assert r.status_code==200;te=r.json()['event'];replace_plan(f,row);before=products(f['owner'],True)
 for data,key,event,user in [(q,'ind-recheck',qe,None),(t,'ind-take',te,REVIEWERS[0])]:
  r=read(f,row,key,user=user);assert r.status_code==200 and r.json()['event']==event and r.json()['status']=='COMMITTED'
  r=post(f,row,data,key,user=user);assert r.status_code==200 and r.json()['event']==event;assert post(f,row,{**data,'reason':'SYNTHETIC different'},key,user=user).status_code==409
 assert products(f['owner'],True)==before;assert read(f,row,user=REVIEWERS[0]).json()['items']==[]


def test_current_specialist_revocation_denies_original_take_recovery(template_consumption):
 f=template_consumption;row,_,_=applied(f);t=take(read(f,row,user=REVIEWERS[0]).json());assert post(f,row,t,'ind-take',user=REVIEWERS[0]).status_code==200
 with f['owner'].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(REVIEWERS[0],))
 before=products(f['owner']);assert read(f,row,'ind-take',user=REVIEWERS[0]).status_code==403;assert post(f,row,t,'ind-take',user=REVIEWERS[0]).status_code==403;assert products(f['owner'])==before


def test_owned_pg_material_update_wins_against_explicit_take_recheck(template_consumption):
 import time,json
 from concurrent.futures import ThreadPoolExecutor
 from pathlib import Path
 from parkweave.preparation import _insert_evidence
 f=template_consumption;row,_,_=applied(f);d=take(read(f,row,user=REVIEWERS[0]).json());observed=False
 with ThreadPoolExecutor(1) as pool:
  with f['owner'].connect() as h:
   parent=h.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],)).fetchone();pid=h.execute('SELECT pg_backend_pid() AS id').fetchone()['id'];future=pool.submit(post,f,row,d,'ind-wait-take',REVIEWERS[0]);end=time.monotonic()+2
   with f['owner'].connect() as monitor:
    while time.monotonic()<end:
     monitor.execute('SELECT pg_stat_clear_snapshot()');observed=monitor.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND %s=ANY(pg_blocking_pids(pid))) AS yes',(pid,)).fetchone()['yes']
     if observed:break
     time.sleep(.01)
   assert observed
   actor=h.execute('SELECT * FROM principals WHERE id=%s',(ENTERPRISES[0],)).fetchone();_insert_evidence(h,actor,parent,'material_outline','SYNTHETIC independent updated before take','DOCUMENT_EXCERPT','SYNTHETIC updated source')
  result=future.result(timeout=5);assert result.status_code==409,result.text
 v=read(f,row,user=REVIEWERS[0]).json();assert v['items'][0]['state']=='RECHECK_REQUESTED' and v['items'][0]['responsible_actor_id'] is None and 'TAKE_RECHECK' not in v['items'][0]['allowed_actions']
 Path('.runtime/manual-goal-recheck-20261014/independent/pg-wait.json').write_text(json.dumps({'actual_owned_pg_wait_observed':observed,'response':result.status_code,'state':v['items'][0]['state'],'responsible_actor_id':None})+'\n')
