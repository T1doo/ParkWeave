from conftest import pg, fixture
from test_template_consumer import template_consumption, headers, body as intake, products
from test_template_consumer_planning import ready, preview, adoption, post as adopt
from test_manual_goal_requests import read, post, body
from template_candidate_support import ENTERPRISES, REVIEWERS
from copy import deepcopy
import pytest

A='SYNTHETIC_INDEPENDENT_PRIVATE_CORPORATE_PURPOSE'
B='SYNTHETIC_INDEPENDENT_PRIVATE_SECOND_PURPOSE'

def setup(f):
 d=intake(f);d['required_goals']=['LOCAL_MATERIAL_PREPARATION',A,B]
 row=ready(f,d);v=preview(f,row).json()
 r=adopt(f,row,'adopt',{**adoption(v),'partial_adoption':True},'restore-ind-adopt')
 assert r.status_code==200,r.text
 return row

def data(v,action,goal=A):
 return {**body(v,action),'goal':goal}

@pytest.mark.parametrize('authority',['EXECUTE','case.create'])
@pytest.mark.parametrize('requested',[False,True])
def test_revoked_owner_write_not_advertised_and_history_stays_readable(template_consumption,authority,requested):
 f=template_consumption;row=setup(f);v=read(f,row).json()
 if requested:
  r=post(f,row,data(v,'REQUEST'),'ind-original-request');assert r.status_code==200,r.text
  original=r.json()['event'];v=r.json()
 late=data(v,'WITHDRAW' if requested else 'REQUEST')
 with f['owner'].connect() as c:
  table,column=('capability_grants','capability') if authority=='EXECUTE' else ('action_grants','action')
  c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND '+column+'=%s',(ENTERPRISES[0],authority))
 before=products(f['owner']);r=read(f,row);assert r.status_code==200,r.text
 assert [x['goal'] for x in r.json()['items']]==[A,B]
 assert all(x['allowed_actions']==[] for x in r.json()['items'])
 if requested:
  restored=read(f,row,'ind-original-request');assert restored.status_code==200 and restored.json()['event']==original
 assert post(f,row,late,'ind-late-write').status_code==403
 assert products(f['owner'])==before

def replace(f,row):
 path='/api/preparations/'+row['preparation_id'];h=headers(f)
 p=f['client'].get(path,headers=h).json()['preparation']
 r=f['client'].post(path+'/request-intent',headers=headers(f,key='ind-revision'),json=dict(expected_preparation_revision=p['revision'],request_text='SYNTHETIC actual revised input with all goals',required_goals=['LOCAL_MATERIAL_PREPARATION',A,B]));assert r.status_code==200,r.text
 v=f['client'].get(path+'/planning-preview',headers=h);assert v.status_code==200,v.text
 plan=f['client'].get(path+'/service-case-plan',headers=h).json();current=v.json()['current']
 r=f['client'].post(path+'/service-case-plan',headers=headers(f,key='ind-real-replace'),json=dict(expected_preparation_revision=current['preparation_revision'],expected_request_revision=r.json()['request_intent']['revision'],expected_source_sha256=current['source_sha256'],expected_plan_revision=plan['revision'],required_goals=['LOCAL_MATERIAL_PREPARATION',A,B],reason='SYNTHETIC actual replacement retains every goal',partial_adoption=True));assert r.status_code==201,r.text

@pytest.mark.parametrize('actor',[ENTERPRISES[0],REVIEWERS[0]])
def test_original_receipt_after_actual_plan_replacement_and_current_revocation(template_consumption,actor):
 f=template_consumption;row=setup(f);v=read(f,row).json();owner_data=data(v,'REQUEST')
 r=post(f,row,owner_data,'ind-owner-original');assert r.status_code==200,r.text
 v=read(f,row,user=REVIEWERS[0]).json();specialist_data=data(v,'TAKE')
 r2=post(f,row,specialist_data,'ind-specialist-original',user=REVIEWERS[0]);assert r2.status_code==200,r2.text
 payload,key,event=(owner_data,'ind-owner-original',r.json()['event']) if actor==ENTERPRISES[0] else (specialist_data,'ind-specialist-original',r2.json()['event'])
 with f['owner'].connect() as c:old=deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan'])
 replace(f,row);before=products(f['owner'])
 cold=read(f,row,user=REVIEWERS[0]);assert cold.status_code==200 and cold.json()['items']==[] and A not in cold.text and B not in cold.text
 restored=read(f,row,key,user=actor);assert restored.status_code==200 and restored.json()['status']=='COMMITTED' and restored.json()['event']==event and restored.json()['original_plan_id']==old['id']
 same=post(f,row,payload,key,user=actor);assert same.status_code==200 and same.json()['event']==event
 assert post(f,row,{**payload,'reason':'SYNTHETIC changed parameter'},key,user=actor).status_code==409
 assert products(f['owner'])==before
 v=read(f,row).json();new=post(f,row,data(v,'REQUEST',B),'ind-new-plan-request');assert new.status_code==200,new.text
 cold=read(f,row,user=REVIEWERS[0]);assert [x['goal'] for x in cold.json()['items']]==[B] and A not in cold.text
 restored=read(f,row,key,user=actor);assert restored.status_code==200 and restored.json()['event']==event
 with f['owner'].connect() as c:
  current=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan']
  archived=deepcopy(old);assert archived.pop('history',[])==[]
  assert current['history'][-1]==archived and len(current['manual_goal_requests'])==1
  assert current['history'][-1]['manual_goal_requests']==old['manual_goal_requests']
  if actor==ENTERPRISES[0]:c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(actor,))
  else:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(actor,))
 before=products(f['owner'])
 assert read(f,row,key,user=actor).status_code==403
 assert post(f,row,payload,key,user=actor).status_code==403
 assert products(f['owner'])==before
