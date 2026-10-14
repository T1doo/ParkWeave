from conftest import pg,fixture
from test_template_consumer import template_consumption,products
from test_manual_goal_reply import ready,reply_data,command
from test_manual_goal_requests import read,post
from test_manual_goal_privacy import A,B
from test_manual_goal_tasks import tasks,manual_items
from test_recheck_independent import request,take
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
from copy import deepcopy
import pytest

@pytest.mark.parametrize('state',['RECHECK_REQUESTED','UNDER_MANUAL_RECHECK'])
def test_explicit_owner_withdraw_recheck_releases_reserved_slots_without_revival(template_consumption,state):
 f=template_consumption;row=ready(f)
 # Real API supplies enough original legal events to put the budget near32.
 for _ in range(8):
  for a,u in [('REQUEST_EVIDENCE',REVIEWERS[0]),('SUPPLY_EVIDENCE',ENTERPRISES[0]),('TAKE',REVIEWERS[0])]:
   v=read(f,row,user=u).json();d=command(v,a)
   if a=='SUPPLY_EVIDENCE':d['evidence']=[{k:v['materials'][0][k] for k in ('id','version','source_sha256')}]
   assert post(f,row,d,user=u).status_code==200
 assert read(f,row).json()['revision']==26
 assert post(f,row,reply_data(read(f,row,user=REVIEWERS[0]).json()),'prior-reply',user=REVIEWERS[0]).status_code==200
 q=request(read(f,row).json());qr=post(f,row,q,'withdraw-original-request');assert qr.status_code==200;event=qr.json()['event'];old_take=take(read(f,row,user=REVIEWERS[0]).json())
 if state=='UNDER_MANUAL_RECHECK':assert post(f,row,old_take,'original-take',user=REVIEWERS[0]).status_code==200
 old_reply=reply_data(read(f,row,user=REVIEWERS[0]).json());v=read(f,row).json();assert post(f,row,{**command(v,'REQUEST'),'goal':B},'other-target-request').status_code==200
 before=deepcopy(products(f['owner']));grants=grant_snapshot(f['owner']);v=read(f,row,user=REVIEWERS[0]).json();b_take={**command(v,'TAKE'),'goal':B}
 assert post(f,row,b_take,'blocked-other-take',user=REVIEWERS[0]).status_code==409
 v=read(f,row).json();r=post(f,row,command(v,'WITHDRAW'),'owner-explicit-withdraw');assert r.status_code==200,r.text;assert r.json()['items'][0]['state']=='WITHDRAWN'
 assert post(f,row,old_take,'late-old-take',user=REVIEWERS[0]).status_code==409;assert post(f,row,old_reply,'late-old-reply',user=REVIEWERS[0]).status_code==409
 prior=read(f,row,'withdraw-original-request');assert prior.status_code==200 and prior.json()['event']==event and prior.json()['items'][0]['state']=='WITHDRAWN';assert post(f,row,q,'withdraw-original-request').json()['event']==event
 for u in (ENTERPRISES[0],REVIEWERS[0]):assert all(i['manual_goal']!=A for i in manual_items(tasks(f,u)))
 # Exact reserved capacity released: another goal now really takes the slot.
 v=read(f,row,user=REVIEWERS[0]).json();d={**command(v,'TAKE'),'goal':B};assert post(f,row,d,'after-release-take',user=REVIEWERS[0]).status_code==200
 after=deepcopy(products(f['owner']))
 for data in (before,after):
  for p in data['preparations']:p['service_case_plan'].pop('manual_goal_requests',None)
 assert before==after and grant_snapshot(f['owner'])==grants;assert read(f,row).json()['overall_goal_state']=='PARTIAL'
