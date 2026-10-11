"""Causal initial local cycle/state must survive a consistent SHA rehash."""
from uuid import UUID,uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import case_cancellation_reconciliation as cr,preparation as prep
from parkweave.store import digest
from test_independent_probes import pg,fixture,preparation_fixture,receipt_fixture,observe
import test_case_cancellation_reconciliation as new
import test_case_cancellation as old

@pytest.mark.parametrize('damage',['unearned_cycle','unearned_initial_state'])
def test_rehashed_initial_request_requires_prefix_derived_cycle_and_case_state(receipt_fixture,damage):
 f=receipt_fixture;p,d,row=new.submitted(f);key=uuid4().hex
 r=new.post(f,p,key=key);assert r.status_code==200,r.text
 with f[1].connect() as c:
  e=c.execute('SELECT * FROM case_local_events WHERE request_key=%s',(key,)).fetchone()
  payload=e['payload'];snapshot=e['snapshot'];cycle=e['cycle']
  if damage=='unearned_cycle':
   cycle=2;snapshot['lifecycle_cycle']=2;payload['cycle']=2
   c.execute('UPDATE case_local_lifecycles SET cycle=2')
  else:snapshot['case_state']='WAITING_CONFIRMATION'
  payload['request']['expected_source_sha256']=digest(prep.canonical(snapshot))
  fp=cr._fingerprint(UUID(p['preparation_id']),cr.Command.model_validate(payload['request']))
  c.execute('UPDATE case_local_events SET cycle=%s,payload=%s,snapshot=%s,fingerprint=%s WHERE id=%s',(cycle,Jsonb(payload),Jsonb(snapshot),fp,e['id']))
 before=old.snapshot(f);x=new.get(f,p);assert x.status_code==200,x.text
 recovered=new.recover(f,p,key)
 observe('initial-phase-'+damage,{'can_reconcile':x.json()['can_reconcile'],'blockers':x.json()['blockers'],'recovery_status':recovered.status_code,'lifecycle_revision':x.json()['lifecycle_revision']})
 assert not x.json()['can_reconcile'] and recovered.status_code==409
 assert old.snapshot(f)==before
