"""Actual owned-PG candidate probes; controlled SQL faults are labelled as such.

Never uses old replacement fixture/output roots. Preexecution source only until
root supplies frozen imports and authorizes the bounded real PG window.
"""
from copy import deepcopy
from uuid import UUID,uuid4
import pytest,psycopg
from frontier_fixture_support import (frontier_case,capability_resource_catalog,capability_catalog,receipt_fixture,preparation_fixture)
from frontier_oracle_support import (verify_imports,quote,commit,offer_body,offer_post,
 snapshot,verified,record,submit,recover,effects,approved,ledger,headers)
from test_resource_bundles import states
from test_case_resource_delivery import preview
from parkweave import executor_receipts as er

@pytest.fixture(autouse=True)
def actual_source_identity():verify_imports()


def query_request(data):
 return {k:data[k] for k in ('members','expected_link_revision','expected_previous_plan_id','replacement_frontier_profile')}


def insert_owned_legacy_step(x,c):
 """Controlled owner fault uses the original INSERT, not an authorized API CREATE."""
 p=x['p'];parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],)).fetchone()
 return er._insert_step(c,parent,'executor-a')


def test_frontier_epoch_actual_insert_delete_aba_cannot_restore_empty_history_eligibility(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);item,_=approved(f,p,data);before=snapshot(f,p);original=effects(f);oldledger=deepcopy(ledger(f,p))
 with f[1].connect() as c:step=insert_owned_legacy_step(x,c)
 during=snapshot(f,p);assert during['counts']['service_receipt_steps']==1 and during['marker']['ever_started']
 with f[1].connect() as c:
  c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
  c.execute('DELETE FROM service_receipt_steps WHERE id=%s',(step['id'],))
 after=snapshot(f,p);assert after['counts']==before['counts'] and not any(after['counts'].values())
 assert after['birth']==before['birth'] and after['marker']['epoch']>during['marker']['epoch']>0 and after['marker']['ever_started']
 r=preview(f,p,query_request(data));assert r.status_code==409,r.text
 r=submit(f,p,{**data,'approval_id':item['id']});assert r.status_code==409,r.text
 assert effects(f)==original and ledger(f,p)==oldledger and states(f,hs)==['HELD']*3
 record('controlled-owner-effect-delete-aba',dict(before=before,during=during,after=after,scope='OWNED_PG_SQL_FAULT_NOT_PUBLIC_DELETE_API'))


def test_frontier_epoch_real_effect_and_marker_rollback_keep_original_eligibility(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];before=snapshot(f,p)
 with pytest.raises(RuntimeError,match='frontier rollback probe'):
  with f[1].connect() as c:
   insert_owned_legacy_step(x,c)
   mark=c.execute('SELECT candidate_business_frontier FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['candidate_business_frontier']
   assert mark['epoch']>0 and mark['ever_started']
   raise RuntimeError('frontier rollback probe')
 assert snapshot(f,p)==before
 result=commit(x);r=recover(f,p,result['key']);assert r.status_code==200,r.text
 assert r.json()['receipt']==result['result']['receipt']
 record('controlled-owner-transaction-rollback',dict(before=before,after=snapshot(f,p),scope='OWNED_PG_ORIGINAL_INSERT_ROLLED_BACK_NOT_COMMITTED_HISTORY'))


def test_frontier_epoch_committed_late_effect_after_approve_refuses_original_commit(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);item,_=approved(f,p,data);original=effects(f);oldledger=deepcopy(ledger(f,p))
 with f[1].connect() as c:insert_owned_legacy_step(x,c)
 actual=snapshot(f,p);assert actual['marker']['epoch']>0 and actual['counts']['service_receipt_steps']==1
 r=submit(f,p,{**data,'approval_id':item['id']});assert r.status_code==409,r.text
 assert effects(f)==original and ledger(f,p)==oldledger and states(f,hs)==['HELD']*3
 record('controlled-late-owned-insert',dict(scope='OWNER_SQL_FAULT_BETWEEN_APPROVE_AND_COMMIT_NOT_P3_API',actual=actual,commit_status=r.status_code))


@pytest.mark.parametrize('capture',['old_plan_before_adopt','new_plan_before_p2'])
def test_frontier_epoch_actual_get_old_intent_after_new_commit_p2_is_refused_but_fresh_allowed(frontier_case,capture):
 x=frontier_case;f,p=x['f'],x['p']
 stale=deepcopy(x['old_offer_body']) if capture=='old_plan_before_adopt' else offer_body(x)
 # Both bodies were captured from actual original dispatch GET, never fabricated.
 assert stale['expected_preparation_revision']==p['revision'] and stale['expected_dispatch_revision']==0
 result=commit(x);verified(f,p,'P2');current=offer_body(x)
 if capture=='old_plan_before_adopt':assert stale['expected_business_frontier']['plan_id']!=current['expected_business_frontier']['plan_id']
 else:
  assert stale['expected_business_frontier']['plan_id']==current['expected_business_frontier']['plan_id']
  assert stale['expected_business_frontier']['plan_revision']<current['expected_business_frontier']['plan_revision']
 before=snapshot(f,p);r=offer_post(x,stale);assert r.status_code==409,r.text
 assert snapshot(f,p)==before
 r=offer_post(x,current);assert r.status_code==201,r.text
 assert snapshot(f,p)['marker']['epoch']>0 and snapshot(f,p)['counts']['service_dispatches']==1
 cold=recover(f,p,result['key']);assert cold.status_code==200,cold.text
 assert cold.json()['receipt']==result['result']['receipt']
 record('actual-asgi-late-intent-'+capture,dict(stale=stale['expected_business_frontier'],current=current['expected_business_frontier'],late_status=409,fresh_status=201))


@pytest.mark.parametrize('action',['DECLINE','WITHDRAW'])
def test_frontier_epoch_pending_plan_does_not_erase_real_offer_resolved_history(frontier_case,action):
 from test_service_dispatches import command as dispatch_command
 x=frontier_case;f,p=x['f'],x['p'];commit(x);verified(f,p,'P2');r=offer_post(x,offer_body(x));assert r.status_code==201,r.text
 offered=r.json();r=dispatch_command(f,offered,action,expected_business_frontier=offered['business_frontier']);assert r.status_code==200,r.text
 actual=snapshot(f,p);assert actual['marker']['ever_started'] and actual['counts']['service_dispatch_events']==2
 with f[1].connect() as c:
  parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],)).fetchone()
  assert all(s['coordination_state']=='PENDING' for s in parent['service_case_plan']['steps'][2:])
  from parkweave.store import Conflict
  with pytest.raises(Conflict):x['protocol'].qualify(c,parent,x['old'])
 record('actual-asgi-resolved-offer-history',dict(action=action,snapshot=actual,scope='ACTUAL_PRODUCT_OFFER_AND_RESOLVE_THEN_COMPONENT_QUALIFICATION_REFUSAL'))


def test_frontier_epoch_actual_committed_grant_false_true_aba_cannot_revive_approval(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);item,_=approved(f,p,data);original=effects(f);oldledger=deepcopy(ledger(f,p));snap=snapshot(f,p)
 versions=[]
 for active in (False,True):
  with f[1].connect() as c:
   f[1].lock_principal(c,'fixture-a',exclusive=True)
   c.execute("UPDATE capability_grants SET active=%s,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'",(active,))
  with f[1].connect() as c:versions.append(dict(c.execute("SELECT active,revision,xmin::text epoch FROM capability_grants WHERE principal_id='fixture-a' AND capability='EXECUTE'").fetchone()))
 assert versions[0]['active'] is False and versions[1]['active'] is True and versions[1]['revision']==versions[0]['revision']+1
 assert versions[0]['epoch']!=versions[1]['epoch']
 r=submit(f,p,{**data,'approval_id':item['id']});assert r.status_code==409,r.text
 assert effects(f)==original and ledger(f,p)==oldledger and snapshot(f,p)==snap and states(f,hs)==['HELD']*3
 record('grant-real-false-true',dict(versions=versions,commit_status=r.status_code))


def test_frontier_epoch_trigger_disable_enable_aba_restored_definition_loses_issued_continuity(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);before=effects(f)
 with f[1].connect() as c:c.execute('ALTER TABLE service_receipt_events DISABLE TRIGGER candidate_frontier_effect')
 with f[1].connect() as c:c.execute('ALTER TABLE service_receipt_events ENABLE ALWAYS TRIGGER candidate_frontier_effect')
 r=preview(f,p,query_request(data));assert r.status_code==403,r.text
 assert effects(f)==before and states(f,hs)==['HELD']*3
 record('ddl-trigger-committed-disable-enable-aba',dict(scope='CONTROLLED_OWNER_DDL',quote_status=r.status_code))


def test_frontier_epoch_statement_truncate_is_rejected_and_does_not_reset_eligibility(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];before=snapshot(f,p)
 with pytest.raises(psycopg.Error):
  with f[1].connect() as c:c.execute('TRUNCATE service_receipt_events')
 assert snapshot(f,p)==before
 _,data=quote(x);item,_=approved(f,p,data)
 assert item['state']=='APPROVED'
