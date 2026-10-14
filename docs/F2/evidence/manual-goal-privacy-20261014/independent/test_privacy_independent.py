from conftest import pg,fixture
from test_template_consumer import template_consumption,body as intake,products
from test_template_consumer_planning import ready,preview,adoption,post as adopt
from test_manual_goal_requests import read,post,body
from template_candidate_support import REVIEWERS,ENTERPRISES,grant_snapshot
from copy import deepcopy
import pytest
A='SYNTHETIC_PRIVATE_MERGER_INTENT_DO_NOT_SHARE'
B='SYNTHETIC_PRIVATE_PATENT_PURPOSE_DO_NOT_SHARE'

def setup(f):
 d=intake(f);d['required_goals']=['LOCAL_MATERIAL_PREPARATION',A,B]
 row=ready(f,d);v=preview(f,row).json();r=adopt(f,row,'adopt',dict(adoption(v),partial_adoption=True),'ind-adopt');assert r.status_code==200,r.text
 return row

def private(r,shared=()):
 assert r.status_code==200,r.text
 v=r.json();assert [i['goal'] for i in v['items']]==list(shared)
 for g in (A,B):
  if g not in shared:assert g not in r.text
 assert v['overall_goal_state']=='PARTIAL' and not v['case_goal_completed']
 return v

def send(f,row,v,action,g,key,user=None):
 return post(f,row,dict(body(v,action),goal=g),key,user=user)

def test_empty_current_and_absent_recovery_private_and_zero_write(template_consumption):
 f=template_consumption;row=setup(f);before=products(f['owner'],True);grants=grant_snapshot(f['owner'])
 private(read(f,row,user=REVIEWERS[0]));private(read(f,row,'ind-absent',user=REVIEWERS[0]))
 assert [i['goal'] for i in read(f,row).json()['items']]==[A,B]
 assert products(f['owner'],True)==before and grant_snapshot(f['owner'])==grants

def test_share_second_goal_only_all_specialist_responses_and_recovery_private(template_consumption):
 f=template_consumption;row=setup(f);v=read(f,row).json();assert send(f,row,v,'REQUEST',B,'ind-share-b').status_code==200
 v=private(read(f,row,user=REVIEWERS[0]),[B]);before=products(f['owner'],True)
 r=send(f,row,v,'TAKE',A,'ind-unshared-take',REVIEWERS[0]);assert r.status_code==409 and A not in r.text and B not in r.text
 assert products(f['owner'],True)==before
 data=dict(body(v,'TAKE'),goal=B);r=post(f,row,data,'ind-take-lost',user=REVIEWERS[0]);private(r,[B]);original=r.json()['event'];before=products(f['owner'],True)
 recovery=read(f,row,'ind-take-lost',user=REVIEWERS[0]);private(recovery,[B]);assert recovery.json()['event']==original and recovery.json()['automatically_replayed'] is False
 private(post(f,row,data,'ind-take-lost',user=REVIEWERS[0]),[B]);assert products(f['owner'],True)==before


def test_withdraw_keeps_original_shared_history_late_response_zero_write(template_consumption):
 f=template_consumption;row=setup(f);v=read(f,row).json();assert send(f,row,v,'REQUEST',B,'ind-request').status_code==200
 late=private(read(f,row,user=REVIEWERS[0]),[B]);owner=read(f,row).json();assert send(f,row,owner,'WITHDRAW',B,'ind-withdraw').status_code==200
 before=products(f['owner'],True);r=send(f,row,late,'TAKE',B,'ind-late',REVIEWERS[0]);assert r.status_code==409;assert A not in r.text;assert products(f['owner'],True)==before
 v=private(read(f,row,user=REVIEWERS[0]),[B]);assert v['items'][0]['state']=='WITHDRAWN' and len(v['items'][0]['history'])==2
 private(read(f,row,'ind-late',user=REVIEWERS[0]),[B]);assert read(f,row,'ind-late',user=REVIEWERS[0]).json()['status']=='NOT_OBSERVED'
 assert [i['goal'] for i in read(f,row).json()['items']]==[A,B]

@pytest.mark.parametrize('capability',['READ','REVIEW_ASSIGNED'])
def test_specialist_revocation_stops_exact_key_recovery_and_late_cached_post(template_consumption,capability):
 f=template_consumption;row=setup(f);assert send(f,row,read(f,row).json(),'REQUEST',B,'ind-share').status_code==200
 v=private(read(f,row,user=REVIEWERS[0]),[B]);data=dict(body(v,'TAKE'),goal=B);assert post(f,row,data,'ind-original',user=REVIEWERS[0]).status_code==200
 with f['owner'].connect() as c:
  table='preparation_grants' if capability=='REVIEW_ASSIGNED' else 'capability_grants';c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',(REVIEWERS[0],capability))
 before=products(f['owner'],True)
 for r in [read(f,row,user=REVIEWERS[0]),read(f,row,'ind-original',user=REVIEWERS[0]),post(f,row,data,'ind-original',user=REVIEWERS[0])]:
  assert r.status_code==403 and A not in r.text and B not in r.text
 after=products(f['owner'],True);old_audit=before.pop('authorization_audit');new_audit=after.pop('authorization_audit')
 assert after==before and len(new_audit)==len(old_audit)+3 and all(e['outcome']=='DENIED' for e in new_audit)


def test_illegitimate_specialist_request_record_is_not_shared_by_metadata(template_consumption):
 from psycopg.types.json import Jsonb
 from parkweave import controlled_plans as cp
 f=template_consumption;row=setup(f);assert send(f,row,read(f,row).json(),'REQUEST',B,'ind-proof').status_code==200
 with f['owner'].connect() as c:
  p=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s FOR UPDATE',(row['preparation_id'],)).fetchone()['service_case_plan'];p['manual_goal_requests'][0]['actor_id']=REVIEWERS[0]
  c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(p),row['preparation_id']))
 before=products(f['owner'],True)
 r=read(f,row,user=REVIEWERS[0]);assert r.status_code==409 and A not in r.text and B not in r.text
 assert products(f['owner'],True)==before
