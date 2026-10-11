"""Independent frozen native activation counterexamples; existing owned fixtures only."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from types import SimpleNamespace
from uuid import UUID
import pytest
from conftest import pg, fixture
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture
from test_native_run_access import native_fixture
from test_native_run_access_activation import activation_fixture, activate, path, business

def test_unknown_provider_cannot_supply_effective_native_scope(activation_fixture):
    a=activation_fixture;f,parent,_,_=a
    assert activate(a).status_code==200
    f[0]._native_run_access=SimpleNamespace(assignment_allowed=lambda *args: True)
    result=f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a'))
    assert result.status_code==403, ('unknown provider granted native READ',result.status_code)

from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave.store import Store, Denied
from parkweave import native_run_access as native
from test_native_run_access_activation import activation_body

@pytest.fixture
def other_owned_fixture(pg,request):
    yield from fixture.__wrapped__(pg,request)

def test_foreign_business_database_cannot_activate_origin_permit(activation_fixture,other_owned_fixture):
    a=activation_fixture;f,parent,bridge,_=a
    other=other_owned_fixture
    wrong=Store(other[0].dsn)
    wrong._native_run_access=native.NativeRunAccess(wrong,test_permit=bridge.test_permit,activation_permit=bridge.activation_permit)
    before=business(a)
    with TestClient(create_app(wrong)) as client:
        r=client.post(path(a)+'/activate',headers=headers(f[2],key='foreign-business-db'),json=activation_body(a))
    assert r.status_code==403, ('foreign Store used origin writer',r.status_code)
    assert business(a)==before

from datetime import datetime,timezone
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import json,os
from psycopg.types.json import Jsonb
from test_native_run_access import act, body, snapshot, APPROVER
from test_native_run_access_activation import accepted, decisions, wait_parent
from test_executor_receipts import act as receipt_command
from test_service_dispatches import command as dispatch_command, read as dispatch_read
from test_case_cancellation_reconciliation import post as cancel_stage, body as cancel_body
from test_pending_receipt_handoff import body_for,post as handoff


def observe(name,value):
    root=Path(os.environ['PARKWEAVE_INDEPENDENT_NATIVE_OBSERVATIONS'])
    dest=root/(name+'.json');assert not dest.exists()
    dest.write_text(json.dumps(value,indent=2,sort_keys=True,default=str)+'\n')


def test_instance_override_cannot_fake_current_issued_enablement(activation_fixture):
    a=activation_fixture;f,parent,bridge,_=a
    assert activate(a).status_code==200
    bridge.activation_permit=None
    bridge.assignment_allowed=lambda *args: True
    result=f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a'))
    assert result.status_code==403


@pytest.mark.parametrize('table,actor,capability',[
    ('principals',APPROVER,None),('capability_grants','fixture-a','READ'),
    ('capability_grants','fixture-a','EXECUTE'),('capability_grants',APPROVER,'READ')])
def test_extra_authority_generations_cannot_revive_activated_lease(activation_fixture,table,actor,capability):
    a=activation_fixture;f,parent,bridge,_=a;assert activate(a).status_code==200
    predicate='id=%s' if table=='principals' else 'principal_id=%s AND capability=%s'
    args=(actor,) if capability is None else (actor,capability)
    with f[1].connect() as c:
        assert c.execute('SELECT 1 FROM '+table+' WHERE '+predicate,args).fetchone()
    for active in (False,True):
        with f[1].connect() as c:
            f[1].lock_principal(c,actor,exclusive=True)
            c.execute('UPDATE '+table+' SET active=%s WHERE '+predicate,(active,*args))
        assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    current=f[3].get(path(a),headers=headers(f[2])).json()
    assert not current['actual_run_access']


def test_reconciling_and_cancelled_case_keep_current_native_history_scope(activation_fixture):
    a=activation_fixture;f,parent,_,_=a;d=accepted(a)
    step=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    submitted=receipt_command(f,step,'SUBMIT');assert submitted.status_code==200,submitted.text
    for action in ('REQUEST_CANCEL','RECONCILE','CONFIRM_CANCEL'):
        r=cancel_stage(f,parent,cancel_body(f,parent,action));assert r.status_code==200,r.text
        expected='CANCELLED' if action=='CONFIRM_CANCEL' else 'RECONCILING'
        assert r.json()['event']['case_state']==expected
        assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==200
        view=f[3].get(path(a),headers=headers(f[2])).json()
        assert view['actual_run_access'] and not view['can_activate']
        assert activate(a).status_code==409
        assert receipt_command(f,submitted.json(),'SUBMIT').status_code==409
    observe('reconciliation-lease-history',dict(states=['RECONCILING','RECONCILING','CANCELLED'],native_read_preserved=True))


def test_manual_pending_handoff_cannot_restore_old_generation_or_expand_lease(activation_fixture):
    a=activation_fixture;f,parent,_,_=a;d=accepted(a)
    # Explicitly existing owned setup for a separate executor, never issued by native activation.
    f[1].assign_status('unassigned',UUID(parent['run_id']))
    before=snapshot(f[1])
    pending=handoff(f,d,body_for(f,parent,d));assert pending.status_code==201,pending.text
    old=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a'))
    assert old.status_code==200 and old.json()['record_mode']=='HISTORICAL_GENERATION'
    assert receipt_command(f,old.json(),'SUBMIT').status_code==409
    current=dispatch_command(f,pending.json(),'ACCEPT',user='unassigned');assert current.status_code==200,current.text
    assert f[3].get('/api/executor-receipts/'+current.json()['receipt_step_id'],headers=headers(f[2],'executor-a')).status_code==403
    assert snapshot(f[1])==before


@pytest.mark.parametrize('first',['submit','revoke'])
def test_actual_submit_revoke_parent_queue_order_and_atomic_result(activation_fixture,first):
    a=activation_fixture;f,parent,_,_=a;d=accepted(a)
    step=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    data=body(a,'REVOKE')
    def rev():return f[3].post(path(a)+'/commands',headers=headers(f[2],key='independent-queued-revoke'),json=data.model_dump(mode='json'))
    calls={'submit':lambda:receipt_command(f,step,'SUBMIT'),'revoke':rev}
    with f[1].connect() as lock:
        lock.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(parent['preparation_id'],))
        with ThreadPoolExecutor(max_workers=2) as pool:
            earlier=pool.submit(calls[first]);wait_parent(f[1],parent['run_id'])
            later=pool.submit(calls['revoke' if first=='submit' else 'submit']);wait_parent(f[1],parent['run_id'],2)
            lock.commit();r1,r2=earlier.result(),later.result()
    assert r1.status_code==200,r1.text
    assert r2.status_code==(200 if first=='submit' else 403),r2.text
    with f[1].connect() as c:
        events=c.execute("SELECT action FROM service_receipt_events WHERE action='SUBMIT'").fetchall()
    assert len(events)==(1 if first=='submit' else 0)
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    observe('receipt-revoke-'+first,dict(first=first,first_status=r1.status_code,second_status=r2.status_code,actual_submit_events=len(events)))


@pytest.mark.parametrize('activation_fixture',[2],indirect=True)
def test_guarded_native_read_commit_expiry_rolls_back_original_app_write(activation_fixture):
    a=activation_fixture;f,parent,_,_=a;assert activate(a).status_code==200
    uid=uuid4()
    with pytest.raises(Denied):
        with f[0].connect() as c:
            p=f[0].auth(c,f[2]['executor-a'],lock=True)
            f[0].scoped_run(c,p,UUID(parent['run_id']))
            c.execute("INSERT INTO authorization_audit(id,principal_id,category,outcome) VALUES(%s,%s,'SYNTHETIC native commit expiry','ALLOWED')",(uid,p['id']))
            c.execute('SELECT pg_sleep(2.1)')
    with f[1].connect() as c:
        assert not c.execute('SELECT 1 FROM authorization_audit WHERE id=%s',(uid,)).fetchone()
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403


@pytest.mark.parametrize('mutation',['run_revision','input_fingerprint','material_review'])
def test_native_read_source_mutation_invalidates_without_receipt_rewrite(activation_fixture,mutation):
    a=activation_fixture;f,parent,_,_=a;r=activate(a,key='source-key');assert r.status_code==200;original=r.json()
    with f[1].connect() as c:
        if mutation=='run_revision':c.execute('UPDATE runs SET revision=revision+1 WHERE id=%s',(parent['run_id'],))
        elif mutation=='input_fingerprint':c.execute("UPDATE runs SET fingerprint=%s WHERE id=%s",('e'*64,parent['run_id']))
        else:c.execute("UPDATE preparations SET review_sha256=%s WHERE id=%s",('e'*64,parent['preparation_id']))
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    if mutation!='input_fingerprint':
        r=f[3].get(path(a)+'/commands/source-key',headers=headers(f[2]));assert r.status_code==200,r.text
        assert r.json()['receipt']==original and not r.json()['actual_run_access']
    else:
        with f[1].connect() as c:
            original_db=c.execute('SELECT native_run_access_activation value FROM runs WHERE id=%s',(parent['run_id'],)).fetchone()['value']
        assert original_db['events'][0]==original


def test_closed_preview_connection_cannot_consume_native_assignment(activation_fixture):
    from parkweave.dispatch_execution_preview import _Store as PreviewStore
    a=activation_fixture;f,parent,bridge,_=a;assert activate(a).status_code==200
    with f[0].connect() as c:
        p=f[0].auth(c,f[2]['executor-a'],lock=True)
        row=c.execute('SELECT * FROM run_assignments WHERE principal_id=%s AND run_id=%s',(p['id'],parent['run_id'])).fetchone()
        shadow=PreviewStore(c)
        shadow._native_run_access=native.NativeRunAccess(shadow,test_permit=bridge.test_permit,activation_permit=bridge.activation_permit)
        assert not shadow.assignment_allowed(shadow.connection,p,UUID(parent['run_id']),assignment=row,track=False)
