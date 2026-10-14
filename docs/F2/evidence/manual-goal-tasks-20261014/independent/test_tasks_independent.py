from conftest import pg,fixture
from test_template_consumer import template_consumption,products
from test_manual_goal_privacy import private_case,A,B,replace_plan
from test_manual_goal_requests import read,post,body
from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
import pytest
from uuid import uuid4
from psycopg.types.json import Jsonb

def tasks(f,user):
 return f['client'].get('/api/preparation-tasks',headers={'Authorization':'Bearer '+f['tokens'][user]})

def action(f,row,a,user=None):
 v=read(f,row,user=user).json();d={**body(v,a),'goal':A}
 if a=='SUPPLY_EVIDENCE':d['evidence']=[{k:v['materials'][0][k] for k in ('id','version','source_sha256')}]
 r=post(f,row,d,user=user);assert r.status_code==200,r.text
 return r.json()

def manual(r):
 assert r.status_code==200,r.text
 return [t for t in r.json()['items'] if t.get('goal')==A]

def test_no_request_then_one_shared_goal_confirmed_case_stays_readonly(template_consumption):
 f=template_consumption;row=private_case(f)
 for a,user in [('REVIEW',REVIEWERS[0]),('CONFIRM',ENTERPRISES[0])]:
  path='/api/preparations/'+row['preparation_id'];h={'Authorization':'Bearer '+f['tokens'][user]}
  rev=f['client'].get(path,headers=h).json()['preparation']['revision']
  r=f['client'].post(path+'/commands',headers={**h,'Idempotency-Key':uuid4().hex},json={'action':a,'expected_revision':rev,'reason':'SYNTHETIC independent explicit '+a});assert r.status_code==200,r.text
 with f['owner'].connect() as c:assert c.execute('SELECT state FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['state']=='LOCAL_CONFIRMED'
 before=products(f['owner'],True);grants=grant_snapshot(f['owner'])
 for user in (ENTERPRISES[0],REVIEWERS[0]):
  r=tasks(f,user);assert not manual(r);assert B not in r.text and A not in r.text
 assert products(f['owner'],True)==before
 action(f,row,'REQUEST');before=products(f['owner'],True)
 r=tasks(f,REVIEWERS[0]);assert len(manual(r))==1;assert B not in r.text
 assert not manual(tasks(f,ENTERPRISES[0]));assert products(f['owner'],True)==before and grant_snapshot(f['owner'])==grants

def test_responsibility_moves_without_completion_or_ledger_mutation(template_consumption):
 f=template_consumption;row=private_case(f);action(f,row,'REQUEST');action(f,row,'TAKE',REVIEWERS[0])
 assert len(manual(tasks(f,REVIEWERS[0])))==1
 action(f,row,'REQUEST_EVIDENCE',REVIEWERS[0]);before=products(f['owner'],True)
 assert len(manual(tasks(f,ENTERPRISES[0])))==1;assert not manual(tasks(f,REVIEWERS[0]));assert products(f['owner'],True)==before
 action(f,row,'SUPPLY_EVIDENCE');before=products(f['owner'],True)
 assert len(manual(tasks(f,REVIEWERS[0])))==1;assert not manual(tasks(f,ENTERPRISES[0]));assert products(f['owner'],True)==before
 assert read(f,row).json()['overall_goal_state']=='PARTIAL'

@pytest.mark.parametrize('terminal',['withdraw','replace'])
def test_withdrawal_and_real_plan_replacement_leave_no_old_todo(template_consumption,terminal):
 f=template_consumption;row=private_case(f);action(f,row,'REQUEST');action(f,row,'TAKE',REVIEWERS[0]);action(f,row,'REQUEST_EVIDENCE',REVIEWERS[0])
 if terminal=='withdraw':action(f,row,'WITHDRAW')
 else:replace_plan(f,row)
 before=products(f['owner'],True)
 for user in (ENTERPRISES[0],REVIEWERS[0]):
  r=tasks(f,user);assert not manual(r);assert B not in r.text
 assert products(f['owner'],True)==before

@pytest.mark.parametrize('authority',['READ','REVIEW_ASSIGNED'])
def test_revoked_specialist_tasks403_and_no_business_write(template_consumption,authority):
 f=template_consumption;row=private_case(f);action(f,row,'REQUEST')
 with f['owner'].connect() as c:c.execute('UPDATE '+('capability_grants' if authority=='READ' else 'preparation_grants')+' SET active=false WHERE principal_id=%s AND capability=%s',(REVIEWERS[0],authority))
 before=products(f['owner']);r=tasks(f,REVIEWERS[0]);assert r.status_code==403 and A not in r.text and B not in r.text;assert products(f['owner'])==before

def test_cross_enterprise_and_original_reviewer_lists_never_contain_other_case(template_consumption):
 f=template_consumption;row=private_case(f);action(f,row,'REQUEST');before=products(f['owner'],True)
 for user in (ENTERPRISES[1],REVIEWERS[1]):
  r=tasks(f,user);assert r.status_code==200,r.text;assert row['preparation_id'] not in r.text and row['case_id'] not in r.text and A not in r.text and B not in r.text
 assert products(f['owner'],True)==before

def test_invalid_share_proof_never_projects_private_target_to_specialist(template_consumption):
 f=template_consumption;row=private_case(f);action(f,row,'REQUEST')
 with f['owner'].connect() as c:
  p=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan'];p['manual_goal_requests'][0]['actor_id']=REVIEWERS[0]
  c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(p),row['preparation_id']))
 before=products(f['owner'],True);r=tasks(f,REVIEWERS[0]);assert r.status_code==200,r.text;assert A not in r.text and B not in r.text
 owner=tasks(f,ENTERPRISES[0]);assert owner.status_code==200,owner.text;assert any(t['blocked_reason']=='MANUAL_JOURNAL_UNVERIFIED' for t in owner.json()['items']);assert products(f['owner'],True)==before
