"""Additional original owned-fixture epochs: genuine value ABA and withdrawal reads.

No design credit is execution credit. These are separate from the revision-only
and catalog-xmin variants in the 27-item independent module.
"""
from copy import deepcopy
from uuid import uuid4
from pathlib import Path
import json
import pytest
from test_plan_replacement_independent import replacement_case,new_quote,capability_resource_catalog,capability_catalog,receipt_fixture,preparation_fixture
from test_plan_source_reapproval import approved
from test_case_resource_delivery import submit,effects,preview,recover
from test_service_plan_approval import read as approval_read,ledger
from test_resource_bundles import states
from test_preparation import headers
from parkweave import service_capability_catalog as cat


def record(kind,value):
 root=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').exists())
 out=root/'.runtime/plan-replacement-oracle/artifacts';out.mkdir(parents=True,exist_ok=True)
 (out/(kind+'-'+uuid4().hex+'.json')).write_text(json.dumps(value,indent=2)+'\n')


def test_original_two_committed_grant_transitions_cannot_revive_new_approval(replacement_case):
 x=replacement_case;f,p=x['f'],x['p'];hs,data=new_quote(x);item,_=approved(f,p,data)
 oldledger=deepcopy(ledger(f,p));before=effects(f);snapshots=[]
 with f[1].connect() as c:
  rows=c.execute("SELECT capability,active,revision FROM capability_grants WHERE principal_id='fixture-a' AND capability='EXECUTE' ORDER BY capability").fetchall()
  assert rows and all(r['active'] for r in rows);snapshots.append([dict(r) for r in rows])
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True)
  c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
 denied=submit(f,p,{**data,'approval_id':item['id']});assert denied.status_code==403,denied.text
 with f[1].connect() as c:
  rows=c.execute("SELECT capability,active,revision FROM capability_grants WHERE principal_id='fixture-a' AND capability='EXECUTE' ORDER BY capability").fetchall()
  assert all(not r['active'] for r in rows);snapshots.append([dict(r) for r in rows])
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True)
  c.execute("UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
 with f[1].connect() as c:
  rows=c.execute("SELECT capability,active,revision FROM capability_grants WHERE principal_id='fixture-a' AND capability='EXECUTE' ORDER BY capability").fetchall()
  assert all(r['active'] for r in rows);snapshots.append([dict(r) for r in rows])
 assert [r['active'] for r in snapshots[0]]==[r['active'] for r in snapshots[-1]]
 assert all(last['revision']==first['revision']+2 for first,last in zip(snapshots[0],snapshots[-1]))
 view=approval_read(f,p);assert view.status_code==200,view.text
 actual=next(v for v in view.json()['items'] if v['id']==item['id'])
 assert actual['state']=='APPROVED' and not actual['current_available']
 stale=submit(f,p,{**data,'approval_id':item['id']});assert stale.status_code==409,stale.text
 assert effects(f)==before and ledger(f,p)==oldledger and states(f,hs)==['HELD']*3
 record('real-grant-aba',dict(scope='OWNED_FIXTURE_REAL_VALUE_ABA',transitions=snapshots,revoked_commit_status=denied.status_code,restored_commit_status=stale.status_code,approval_current_available=False,no_effects=True))


def test_original_withdrawn_target_repeated_preflight_and_quote_reads_cannot_revive_approval(replacement_case):
 x=replacement_case;f,p=x['f'],x['p'];hs,data=new_quote(x);item,_=approved(f,p,data)
 oldledger=deepcopy(ledger(f,p));before=effects(f);target,instance=x['newpairs'][1]
 with x['a']['catalog'].connection() as c:revision=cat.proof(cat.row(c,'park-a'))['revision']
 x['a']['catalog'].withdraw_release('park-a',uuid4().hex,target['release_id'],revision,'SYNTHETIC original current coordination source withdrawal')
 replies=[]
 for _ in range(2):
  directory=x['checker'].directory(f[2]['fixture-a'],p['preparation_id'])
  checked=x['checker'].preview(f[2]['fixture-a'],p['preparation_id'],original_release_id=target['release_id'],original_instance_id=instance['instance_id'],target_instance_id=instance['instance_id'])
  assert checked['classification']=='UNKNOWN' and not checked['can_record'] and not checked['target_current_available']
  q=preview(f,p,{k:data[k] for k in ('members','expected_link_revision','expected_previous_plan_id')});assert q.status_code==409,q.text
  view=approval_read(f,p);assert view.status_code==200,view.text
  actual=next(v for v in view.json()['items'] if v['id']==item['id']);assert actual['state']=='APPROVED' and not actual['current_available']
  r=submit(f,p,{**data,'approval_id':item['id']});assert r.status_code==409,r.text
  replies.append(dict(preflight_classification=checked['classification'],target_available=False,quote_status=q.status_code,commit_status=r.status_code,approval_current_available=False,directory_state=directory['state']))
 assert effects(f)==before and ledger(f,p)==oldledger and states(f,hs)==['HELD']*3
 old=recover(f,p,x['oldreceipt']['delivery_binding']['request_key']);assert old.status_code==200,old.text
 assert old.json()['receipt']==x['oldreceipt']['receipt']
 record('withdrawal-read-refresh',dict(scope='REPEATED_ORIGINAL_READS_NOT_OPPORTUNITY_REFRESH_COMMAND',replies=replies,no_resurrection=True,no_effects=True,historical_receipt_unchanged=True))


@pytest.fixture
def incomplete_replacement_case(capability_resource_catalog,tmp_path):
 from test_plan_replacement_independent import bind_all,generate,ALL_GOALS
 from test_executor_receipts import ready
 from test_request_intents import save
 from test_preparation import command
 from test_service_case_steps import verified
 from test_resource_bundles import bundle
 from test_case_resource_delivery import quoted
 from test_service_plan_approval import enable
 from test_template_upgrade import publication
 from parkweave import service_release_preflight as pf
 from parkweave.template_consumer import ConsumerRepository
 a=capability_resource_catalog;f=a['f'];oldpairs=bind_all(a)
 checker=pf.ServiceReleasePreflight(a['catalog'],ConsumerRepository(tmp_path/'incomplete-preflight.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
 out=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').exists())/'.runtime/plan-replacement-oracle/artifacts';out.mkdir(parents=True,exist_ok=True)
 import os
 with os.fdopen(os.open(out/('redaction-'+uuid4().hex+'.private.json'),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as h:json.dump(sorted(set(f[2].values())),h)
 p=ready(f);r=save(f,p,goals=ALL_GOALS);assert r.status_code==200,r.text;p={**p,'revision':r.json()['revision']}
 for action,actor in [('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')]:
  r=command(f,p,action,actor,reason='SYNTHETIC original material proof for incomplete business Case');assert r.status_code==200,r.text;p=r.json()
 old=generate(a,p);verified(f,p,'P1')
 enable(f,p,enabled_for_source_reapproval_tests=True,enabled_for_plan_replacement_tests=True,plan_replacement_preflight=checker)
 hs,b=bundle(f);d=quoted(f,p,b);item,_=approved(f,p,d)
 r=submit(f,p,{**d,'approval_id':item['id']});assert r.status_code==201,r.text;verified(f,p,'P2')
 from test_service_plan_manual_lock import stored
 previous=deepcopy(stored(f,p));assert [s['coordination_state'] for s in previous['steps']]==['VERIFIED','VERIFIED','PENDING','PENDING','PENDING']
 a['published']=publication(a,goals=a['published']['snapshot']['definition']['required_goals'],source='1',name='SYNTHETIC compatible catalog for still incomplete original business')
 newpairs=bind_all(a,2)
 for release,instance in oldpairs:
  with a['catalog'].connection() as c:revision=cat.proof(cat.row(c,'park-a'))['revision']
  a['catalog'].withdraw_release('park-a',uuid4().hex,release['release_id'],revision,'SYNTHETIC explicit obsolete release retirement retains incomplete Case history')
 checks=[]
 for (oldrelease,oldinstance),(target,instance) in zip(oldpairs,newpairs):
  q=checker.preview(f[2]['fixture-a'],p['preparation_id'],original_release_id=oldrelease['release_id'],original_instance_id=oldinstance['instance_id'],target_instance_id=instance['instance_id'])
  checks.append({k:q[k] for k in ('classification','contract_classification','blocking_reasons','current_case_blocking_reasons','unknown_scope')})
 record('incomplete-preflight',dict(scope='ACTUAL_ORIGINAL_PREFLIGHT_BEFORE_REPLACEMENT',checks=checks))
 for action,actor in [('REOPEN','fixture-a'),('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')]:
  response=command(f,p,action,actor,reason='SYNTHETIC original review after known catalog generation changed');assert response.status_code==200,response.text;p=response.json()
 new=generate(a,p,previous['revision']);verified(f,p,'P1')
 return dict(a=a,f=f,p=p,old=previous,new=new,checks=checks)


def test_original_unfinished_business_chain_cannot_receive_replacement_approval(incomplete_replacement_case):
 from test_resource_bundles import bundle
 x=incomplete_replacement_case;f,p=x['f'],x['p'];hs,b=bundle(f);before=effects(f);oldledger=deepcopy(ledger(f,p))
 assert all(q['classification']=='UNKNOWN' for q in x['checks'])
 assert all(q['contract_classification']=='COMPATIBLE' for q in x['checks'])
 request={**b,'expected_link_revision':1,'expected_previous_plan_id':x['old']['id']}
 r=preview(f,p,request);assert r.status_code==409,r.text
 assert effects(f)==before and ledger(f,p)==oldledger and states(f,hs)==['HELD']*3
 record('unfinished-chain-refusal',dict(scope='OLD_P1_P2_ONLY_ORIGINAL_BUSINESS_UNFINISHED',quote_status=r.status_code,no_effects=True,preflight=x['checks']))
