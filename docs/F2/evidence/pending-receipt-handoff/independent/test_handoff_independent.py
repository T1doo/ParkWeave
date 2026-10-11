"""NEW private owned PG/ASGI probes. No external service or execution proof chain."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event, current_thread
from uuid import UUID, uuid4
import time
import pytest
import psycopg
from psycopg.types.json import Jsonb
from parkweave import service_dispatches as sd, executor_receipts as er
from parkweave.store import Store, Conflict
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture, ready, create as legacy_create
from test_service_dispatches import offer, command as decide, REVIEWER

BUSINESS=('service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps',
          'service_step_receipts','service_receipt_events','dispatch_notice_outbox','dispatch_notices')
AUTH=('principals','capability_grants','field_grants','action_grants','run_assignments','preparation_grants')

def snap(f,tables=BUSINESS):
    with f[1].connect() as c:
        return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in tables}

def setup(f):
    p=ready(f)
    f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
    response,_,_=offer(f,p);assert response.status_code==201
    response=decide(f,response.json(),'ACCEPT');assert response.status_code==200
    return p,response.json()

def body(f,p,row,target='unassigned'):
    # Derive the request from independent actual-event/step SQL, not author catalog helpers.
    with f[1].connect() as c:
        previous=c.execute("SELECT o.*,e.revision FROM service_dispatch_offers o JOIN service_dispatch_events e ON e.offer_id=o.id WHERE o.dispatch_id=%s AND e.action='ACCEPT' ORDER BY e.revision DESC LIMIT 1",(UUID(row['dispatch_id']),)).fetchone()
        step=c.execute('SELECT * FROM service_receipt_steps WHERE id=%s',(previous['receipt_step_id'],)).fetchone()
    return dict(expected_preparation_revision=p['revision'],expected_dispatch_revision=row['revision'],
                predecessor_offer_id=str(previous['id']),predecessor_receipt_step_id=str(step['id']),
                expected_receipt_revision=step['revision'],executor_id=target,reason='SYNTHETIC independent explicit reassignment')

def post(f,row,b,key=None):
    return f[3].post('/api/service-dispatches/'+row['dispatch_id']+'/reassign',
                     headers=headers(f[2],REVIEWER,key or uuid4().hex),json=b)

def recover(f,row,key):
    return f[3].get('/api/service-dispatches/'+row['dispatch_id']+'/reassignment-recovery/'+key,
                    headers=headers(f[2],REVIEWER))

@pytest.mark.parametrize('winner',['submit','handoff'])
def test_real_lock_wait_both_orders(receipt_fixture,monkeypatch,winner):
    f=receipt_fixture;p,row=setup(f);b=sd.Reassign(**body(f,p,row));step_id=UUID(row['receipt_step_id'])
    receipt=er.Command(action='SUBMIT',expected_revision=1,text='SYNTHETIC independent race',source_kind='SYNTHETIC',source_label='SYNTHETIC')
    held=Event();release=Event();second_connected=Event();pids={};original_connect=f[0].connect
    @contextmanager
    def tracked_connect():
        with original_connect() as c:
            name=current_thread().name
            pids[name]=c.execute('SELECT pg_backend_pid() n').fetchone()['n']
            if name.endswith('_1'):second_connected.set()
            yield c
    monkeypatch.setattr(f[0],'connect',tracked_connect)
    if winner=='handoff':
        original=sd._handoff_predecessor
        def hold(*args,**kwargs):
            result=original(*args,**kwargs)
            if kwargs.get('write') and not held.is_set():
                held.set();assert release.wait(5)
            return result
        monkeypatch.setattr(sd,'_handoff_predecessor',hold)
    else:
        original=er.current_step
        def hold(*args,**kwargs):
            result=original(*args,**kwargs)
            if current_thread().name.endswith('_0') and not held.is_set():
                held.set();assert release.wait(5)
            return result
        monkeypatch.setattr(er,'current_step',hold)
    def run(kind):
        try:
            if kind=='handoff':sd.reassign(f[0],f[2][REVIEWER],UUID(row['dispatch_id']),uuid4().hex,b)
            else:er.command(f[0],f[2]['executor-a'],step_id,uuid4().hex,receipt)
            return 'COMMITTED'
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2,thread_name_prefix='independent-race') as pool:
        first=pool.submit(run,winner);assert held.wait(3)
        second=pool.submit(run,'handoff' if winner=='submit' else 'submit')
        try:
            assert second_connected.wait(2)
            second_pid=pids['independent-race_1'];observed=False
            # Observe actual PostgreSQL blocking rather than assuming thread order implies locking.
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                with f[1].connect() as c:
                    wait=c.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',(second_pid,)).fetchone()
                if wait and wait['wait_event_type']=='Lock':observed=True;break
                time.sleep(.01)
            assert observed,'second backend never observed waiting on a database lock'
            assert not second.done()
        finally:release.set()
        assert first.result(timeout=5)=='COMMITTED'
        assert second.result(timeout=5)=='CONFLICT'
    with f[1].connect() as c:
        count=c.execute('SELECT count(*) n FROM service_step_receipts WHERE step_id=%s',(step_id,)).fetchone()['n']
        state=c.execute('SELECT o.state FROM service_dispatches d JOIN service_dispatch_offers o ON o.id=d.current_offer_id WHERE d.id=%s',(UUID(row['dispatch_id']),)).fetchone()['state']
    assert count==(1 if winner=='submit' else 0)
    assert state==('ACCEPTED' if winner=='submit' else 'OFFERED')

LINEAGE=('handoff_kind','predecessor_offer_id','predecessor_receipt_step_id','predecessor_executor_id',
         'predecessor_receipt_revision','previous_preparation_revision','previous_preparation_sha256',
         'accepted_preparation_revision','accepted_preparation_sha256')
@pytest.mark.parametrize('field',LINEAGE)
def test_each_handoff_lineage_field_tamper_denied(receipt_fixture,field):
    f=receipt_fixture;p,row=setup(f);pending=post(f,row,body(f,p,row));assert pending.status_code==201;pending=pending.json()
    with f[1].connect() as c:
        event=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action='REOFFER'",(UUID(pending['current_offer']['id']),)).fetchone()['payload']
        event[field]=event[field]+1 if type(event[field]) is int else 'SYNTHETIC_CORRUPTION'
        c.execute("UPDATE service_dispatch_events SET payload=%s WHERE offer_id=%s AND action='REOFFER'",(Jsonb(event),UUID(pending['current_offer']['id'])))
    before=snap(f);assert decide(f,pending,'ACCEPT').status_code==409
    assert snap(f)==before

def test_latest_actual_accept_not_old_generation(receipt_fixture):
    f=receipt_fixture;p,first=setup(f);first_body=body(f,p,first)
    pending=post(f,first,first_body).json();second=decide(f,pending,'ACCEPT').json()
    stale={**first_body,'expected_dispatch_revision':second['revision'],'executor_id':'executor-a'}
    before=snap(f);assert post(f,second,stale).status_code==409 and snap(f)==before
    accepted=post(f,second,body(f,p,second,'executor-a'));assert accepted.status_code==201
    third=decide(f,accepted.json(),'ACCEPT');assert third.status_code==200
    assert len({first['receipt_step_id'],second['receipt_step_id'],third.json()['receipt_step_id']})==3

@pytest.mark.parametrize('corruption',['missing_accept_event','wrong_accept_actor'])
def test_offer_state_and_step_without_valid_actual_accept_cannot_authorize(receipt_fixture,corruption):
    f=receipt_fixture;p,row=setup(f);b=body(f,p,row)
    with f[1].connect() as c:
        if corruption=='missing_accept_event':c.execute("UPDATE service_dispatch_events SET action='DECLINE' WHERE action='ACCEPT' AND dispatch_id=%s",(UUID(row['dispatch_id']),))
        else:c.execute("UPDATE service_dispatch_events SET actor_id='unassigned' WHERE action='ACCEPT' AND dispatch_id=%s",(UUID(row['dispatch_id']),))
    before=snap(f);assert post(f,row,b).status_code==409 and snap(f)==before

def test_schema29_one_receipt_cannot_be_claimed_by_second_offer(receipt_fixture):
    f=receipt_fixture;p,row=setup(f);pending=post(f,row,body(f,p,row)).json();before=snap(f)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with f[1].connect() as c:
            c.execute("UPDATE service_dispatch_offers SET state='ACCEPTED',receipt_step_id=%s WHERE id=%s",(UUID(row['receipt_step_id']),UUID(pending['current_offer']['id'])))
    assert snap(f)==before
    with f[1].connect() as c:
        constraints=c.execute("SELECT conname,pg_get_constraintdef(oid) d FROM pg_constraint WHERE conrelid='service_dispatch_offers'::regclass AND contype='u'").fetchall()
        assert any(r['d']=='UNIQUE (receipt_step_id)' for r in constraints)

@pytest.mark.parametrize('stage',['reassign','accept'])
def test_schema28_refuses_new_handoff_before_writes(receipt_fixture,stage):
    f=receipt_fixture;p,row=setup(f);b=body(f,p,row)
    if stage=='accept':row=post(f,row,b).json()
    with f[1].connect() as c:
        c.execute('ALTER TABLE service_dispatch_offers DROP CONSTRAINT service_dispatch_receipt_generation_key')
        c.execute('ALTER TABLE service_receipt_steps ADD CONSTRAINT service_receipt_preparation_generation_key UNIQUE(preparation_id,preparation_revision)')
        c.execute('DELETE FROM schema_version WHERE version=29')
    before=snap(f)
    response=post(f,row,b) if stage=='reassign' else decide(f,row,'ACCEPT')
    assert response.status_code==409 and snap(f)==before

@pytest.mark.parametrize('change',['read','preparation_grant','inactive','role','tenant'])
def test_recovery_get_current_authority_and_no_private_echo(receipt_fixture,change):
    f=receipt_fixture;p,row=setup(f);key=uuid4().hex;assert post(f,row,body(f,p,row),key).status_code==201
    with f[1].connect() as c:
        f[1].lock_principal(c,REVIEWER,exclusive=True)
        if change=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(REVIEWER,))
        elif change=='preparation_grant':c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(REVIEWER,))
        else:c.execute('UPDATE principals SET '+{'inactive':'active=false','role':"role='enterprise_operator'",'tenant':"org_id='org-b'"}[change]+' WHERE id=%s',(REVIEWER,))
    before=snap(f);response=recover(f,row,key);assert response.status_code==403
    assert response.json()=={'detail':'record unavailable or authorization denied'}
    assert all(s not in response.text for s in (key,row['dispatch_id'],p['preparation_id'],'independent explicit'))
    assert snap(f)==before

@pytest.mark.parametrize('attribute',['_isolated_run_access','_isolated_local_execution','_isolated_execution_preview',
                                    '_isolated_resource_execution_preview','_isolated_dispatch_execution_preview',
                                    '_isolated_receipt_execution_preview','_isolated_lifecycle_execution_preview'])
def test_every_isolated_attachment_blocks_before_business_writes(receipt_fixture,attribute):
    f=receipt_fixture;p,row=setup(f);b=body(f,p,row);setattr(f[0],attribute,object())
    before=snap(f)
    try:assert post(f,row,b).status_code==409 and snap(f)==before
    finally:delattr(f[0],attribute)

def test_plain_store_exact_type_and_legacy_create_stay_closed(receipt_fixture):
    f=receipt_fixture;p,row=setup(f);before=snap(f)
    class Alternate(Store):pass
    other=Alternate(f[0].dsn)
    with pytest.raises(Conflict):sd.reassign(other,f[2][REVIEWER],UUID(row['dispatch_id']),uuid4().hex,sd.Reassign(**body(f,p,row)))
    assert legacy_create(f,p)[0].status_code==409 and snap(f)==before

def test_raw_migration_requires_owned_ticket_and_repeat_preserves_history(receipt_fixture):
    from pathlib import Path
    f=receipt_fixture;p,row=setup(f);before=snap(f);authority=snap(f,AUTH)
    sql=Path('/workspace/ParkWeave/src/parkweave/migration-029.sql').read_text()
    # Owner credentials alone do not create a migration ticket; fail before DDL.
    with pytest.raises(psycopg.Error):
        with f[1].connect() as c:c.execute(sql)
    assert snap(f)==before and snap(f,AUTH)==authority
    # Only the original fixture-issued creation evidence is reused in this owned DB.
    with f[1].connect() as c:
        f[1]._case_fact_fixture_receipt.authorize_migration(c);c.execute(sql)
    assert snap(f)==before and snap(f,AUTH)==authority

def test_new_uuid_manual_submit_owner_ack_and_history_authority_unchanged(receipt_fixture):
    f=receipt_fixture;p,row=setup(f);before=snap(f);authority=snap(f,AUTH);key=uuid4().hex
    response=post(f,row,body(f,p,row),key);assert response.status_code==201
    read=recover(f,row,key);assert read.status_code==200 and read.headers['cache-control']=='no-store'
    assert read.json()['event']==response.json()['event'] and read.json()['historical_only'] is True
    newer=decide(f,response.json(),'ACCEPT').json();step=UUID(newer['receipt_step_id']);assert str(step)!=row['receipt_step_id']
    submitted=er.command(f[0],f[2]['unassigned'],step,uuid4().hex,er.Command(action='SUBMIT',expected_revision=1,text='SYNTHETIC independent manual work',source_kind='SYNTHETIC',source_label='SYNTHETIC'))
    final=er.command(f[0],f[2]['fixture-a'],step,uuid4().hex,er.Command(action='ACKNOWLEDGE',expected_revision=2,reason='SYNTHETIC independent owner review',receipt_sha256=submitted['current_receipt']['source_sha256']))
    assert final['step']['state']=='LOCAL_ACKNOWLEDGED' and final['case_goal_completed'] is False
    now=snap(f)
    for t in ('service_receipt_steps','service_receipt_events','service_dispatch_events','service_dispatch_offers'):
        assert all(r in now[t] for r in before[t])
    assert snap(f,AUTH)==authority
    assert recover(f,row,key).json()['event']==response.json()['event']
