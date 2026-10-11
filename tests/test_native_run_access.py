"""Real owned PostgreSQL, existing app privileges; decisions confer no access."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy, copy
from datetime import datetime, timedelta, timezone
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError
import pytest

from parkweave import native_run_access as native
from parkweave.api import create_app
from parkweave.native_run_access import RunCommand
from parkweave.store import Store, Conflict, Denied
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, filled, command as prep_command, headers

APPROVER='prep-specialist-fixture-a'
TABLES=('principals','capability_grants','field_grants','action_grants','preparation_grants',
        'synthetic_resource_grants','run_assignments')


def snapshot(owner):
    with owner.connect() as c:
        return {t:c.execute('SELECT row_to_json(t) row FROM '+t+' t ORDER BY row_to_json(t)::text').fetchall()
                for t in TABLES}


@pytest.fixture
def native_fixture(receipt_fixture):
    f=receipt_fixture
    parent=filled(f)
    parent=prep_command(f,parent,'REVIEW',APPROVER,reason='SYNTHETIC manual review').json()
    parent=prep_command(f,parent,'CONFIRM',reason='SYNTHETIC owner confirm').json()
    before=snapshot(f[1])
    native.install_owned_test_storage(f[1],f[1]._case_fact_fixture_receipt)
    permit=native.issue_decision_test_permit(f[1],f[1]._case_fact_fixture_receipt,approver_ids={APPROVER})
    bridge=native.NativeRunAccess(f[0],test_permit=permit)
    f[0]._native_run_access=bridge
    assert snapshot(f[1])==before
    return f,parent,bridge,before


def body(a,action,user=None,**changes):
    f,parent,bridge,_=a
    user=user or (APPROVER if action in ('APPROVE','REJECT') else 'fixture-a')
    view=bridge.read(f[2][user],UUID(parent['run_id']))
    data=dict(action=action,expected_revision=view['revision'],expected_run_revision=view['run_revision'],
              expected_authority_sha256=view['authority_sha256'],reason='SYNTHETIC explicit '+action)
    if action=='REQUEST':
        now=datetime.now(timezone.utc)
        data.update(target_id='executor-a',target_role='service_executor',capability='READ',
                    requested_validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(minutes=5)).isoformat(),timezone='UTC'))
    if action=='APPROVE':data['approved_validity']=view['request']['requested_validity']
    data.update(changes)
    return RunCommand.model_validate(data)


def act(a,action,user=None,key=None,data=None):
    f,parent,bridge,_=a
    user=user or (APPROVER if action in ('APPROVE','REJECT') else 'fixture-a')
    return bridge.command(f[2][user],UUID(parent['run_id']),key or uuid4().hex,data or body(a,action,user))


def ledger(a):
    with a[0][1].connect() as c:
        return c.execute('SELECT native_run_access_protocol value FROM runs WHERE id=%s',(a[1]['run_id'],)).fetchone()['value']


def test_native_atomic_approve_revoke_never_writes_assignment_or_permissions(native_fixture):
    a=native_fixture;f,parent,bridge,before=a
    request=act(a,'REQUEST',key='native-request')
    decision=act(a,'APPROVE',key='native-approve')
    assert decision['state']=='APPROVED' and decision['projection_state']=='NON_EFFECTIVE'
    current=ledger(a)
    assert current['events']==[request,decision] and len(current['leases'])==1
    assert current['leases'][0]['state']=='NON_EFFECTIVE'
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    with f[0].connect() as c:
        assert not c.execute("SELECT has_table_privilege(current_user,'run_assignments','UPDATE') ok").fetchone()['ok']
        assert not c.execute("SELECT has_table_privilege(current_user,'principals','UPDATE') ok").fetchone()['ok']
    assert act(a,'REVOKE')['state']=='REVOKED'
    assert snapshot(f[1])==before
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2])).json()['state']=='SUCCEEDED'


def test_original_receipt_recovery_after_later_events_and_cold_store(native_fixture):
    a=native_fixture;f,parent,bridge,before=a
    command=body(a,'REQUEST');first=act(a,'REQUEST',key='lost-response',data=command)
    act(a,'APPROVE');act(a,'REVOKE')
    assert act(a,'REQUEST',key='lost-response',data=command)==first
    cold=Store(f[0].dsn)
    with TestClient(create_app(cold)) as client:
        path='/api/runs/'+parent['run_id']+'/access'
        assert client.get('/api/run-access/status',headers=headers(f[2])).json()['enabled'] is False
        assert client.get(path,headers=headers(f[2])).json()['state']=='REVOKED'
        recovered=client.get(path+'/commands/lost-response',headers=headers(f[2])).json()
        assert recovered['found'] and recovered['receipt']==first
        assert client.get(path+'/commands/absent',headers=headers(f[2])).json()['found'] is False
        assert client.post(path+'/commands',headers=headers(f[2],key='closed'),json=command.model_dump(mode='json')).status_code==403
    assert snapshot(f[1])==before and len(ledger(a)['events'])==3


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-b','unassigned','executor-b','executor-c'])
def test_nonparticipants_cannot_read_command_or_recover(native_fixture,user):
    a=native_fixture;f,parent,_,_=a
    command=body(a,'REQUEST');act(a,'REQUEST',key='private')
    path='/api/runs/'+parent['run_id']+'/access'
    assert f[3].get(path,headers=headers(f[2],user)).status_code==403
    assert f[3].get(path+'/commands/private',headers=headers(f[2],user)).status_code==403
    assert f[3].post(path+'/commands',headers=headers(f[2],user,'private'),json=command.model_dump(mode='json')).status_code==403


def test_current_read_revocation_blocks_original_key_recovery(native_fixture):
    a=native_fixture;f,parent,bridge,_=a
    act(a,'REQUEST',key='old');f[1].revoke_capability('fixture-a','READ')
    with pytest.raises(Denied):bridge.recover(f[2]['fixture-a'],UUID(parent['run_id']),'old')
    assert ledger(a)['revision']==1


def test_owner_cannot_approve_and_beneficiary_metadata_is_not_run_access(native_fixture):
    a=native_fixture;f,parent,bridge,_=a
    act(a,'REQUEST')
    with pytest.raises(Denied):act(a,'APPROVE',user='fixture-a')
    target=bridge.read(f[2]['executor-a'],UUID(parent['run_id']))
    assert target['state']=='REQUESTED' and not target['actual_run_access']
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403


@pytest.mark.parametrize('same',[True,False])
def test_same_key_concurrent_commands_serialized_in_pg(native_fixture,same):
    a=native_fixture;data=body(a,'REQUEST');other=data if same else data.model_copy(update={'reason':'different'})
    def submit(d):
        try:return act(a,'REQUEST',key='concurrent',data=d)
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(submit,[data,other]))
    assert len(ledger(a)['events'])==1
    assert results[0]==results[1] if same else results.count('CONFLICT')==1


def test_same_key_different_run_conflicts(native_fixture):
    a=native_fixture;f,parent,bridge,_=a;data=body(a,'REQUEST');act(a,'REQUEST',key='global-key',data=data)
    other=filled(f)
    with pytest.raises(Conflict,match='fingerprint'):
        bridge.command(f[2]['fixture-a'],UUID(other['run_id']),'global-key',data)


def test_event_failure_rolls_back_request_decision_and_lease(native_fixture):
    a=native_fixture;f,parent,_,_=a
    act(a,'REQUEST');before=ledger(a);data=body(a,'APPROVE')
    with f[1].connect() as c:
        c.execute("""CREATE FUNCTION native_test_fail() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'SYNTHETIC event write failure'; END $$;
            CREATE TRIGGER native_test_fail BEFORE UPDATE OF native_run_access_protocol ON runs
            FOR EACH ROW EXECUTE FUNCTION native_test_fail()""")
    with pytest.raises(psycopg.errors.RaiseException,match='event write failure'):
        act(a,'APPROVE',data=data)
    assert ledger(a)==before and snapshot(f[1])==a[3]


@pytest.mark.parametrize('mutation',['prefix','clear','rewrite','missing_revision'])
def test_pg_immutable_history_and_state_guard(native_fixture,mutation):
    a=native_fixture;act(a,'REQUEST');value=deepcopy(ledger(a));before=deepcopy(value)
    if mutation=='prefix':value['events'][0]['reason']='tampered'
    elif mutation=='clear':value=None
    elif mutation=='rewrite':value['state']='APPROVED'
    else:value.pop('revision')
    with pytest.raises(psycopg.errors.RaiseException):
        with a[0][0].connect() as c:
            c.execute('UPDATE runs SET native_run_access_protocol=%s WHERE id=%s',(Jsonb(value),a[1]['run_id']))
    assert ledger(a)==before


def test_approval_interval_must_shrink_and_history_stays_atomic(native_fixture):
    a=native_fixture;act(a,'REQUEST');data=body(a,'APPROVE');before=ledger(a)
    interval=deepcopy(data.approved_validity.model_dump())
    interval['valid_from']=(datetime.fromisoformat(interval['valid_from'])-timedelta(seconds=1)).isoformat()
    with pytest.raises(Conflict,match='shrink'):
        act(a,'APPROVE',data=data.model_copy(update={'approved_validity':native.Validity.model_validate(interval)}))
    assert ledger(a)==before


def test_expiry_rechecked_after_actual_pg_parent_lock_wait(native_fixture):
    a=native_fixture;f,parent,_,_=a
    data=body(a,'REQUEST');now=datetime.now(timezone.utc)
    data=data.model_copy(update={'requested_validity':native.Validity(valid_from=now.isoformat(),valid_until=(now+timedelta(seconds=1.5)).isoformat(),timezone='UTC')})
    with f[1].connect() as blocker:
        blocker.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(parent['preparation_id'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(act,a,'REQUEST',data=data)
            waiting=False;deadline=monotonic()+2
            while monotonic()<deadline:
                with f[1].connect() as observer:
                    waiting=bool(observer.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM preparations%' LIMIT 1").fetchone())
                if waiting:break
                Event().wait(.02)
            assert waiting
            Event().wait(max(0,(now+timedelta(seconds=1.6)-datetime.now(timezone.utc)).total_seconds()))
            blocker.commit()
            with pytest.raises(Conflict,match='interval'):future.result(timeout=5)
    assert ledger(a) is None


@pytest.mark.parametrize('field',['input','receipt','empty_input','changed_goal','operation_action'])
def test_malformed_source_is_explicit_conflict_not_internal_error(native_fixture,field):
    a=native_fixture;f,parent,bridge,_=a
    with f[1].connect() as c:
        if field=='input':c.execute('UPDATE runs SET input=%s WHERE id=%s',(Jsonb(['invalid']),parent['run_id']))
        elif field=='empty_input':c.execute('UPDATE runs SET input=%s WHERE id=%s',(Jsonb({}),parent['run_id']))
        elif field=='changed_goal':
            value=c.execute('SELECT input FROM runs WHERE id=%s',(parent['run_id'],)).fetchone()['input']
            value['goal']='SYNTHETIC changed goal with old fingerprint'
            c.execute('UPDATE runs SET input=%s WHERE id=%s',(Jsonb(value),parent['run_id']))
        elif field=='operation_action':c.execute("UPDATE operations SET action='facts.assess' WHERE run_id=%s",(parent['run_id'],))
        else:
            receipt=c.execute('SELECT receipt FROM operations WHERE run_id=%s',(parent['run_id'],)).fetchone()['receipt']
            receipt['verified']=1
            c.execute('UPDATE operations SET receipt=%s WHERE run_id=%s',(Jsonb(receipt),parent['run_id']))
    with pytest.raises(Conflict,match='verified'):bridge.read(f[2]['fixture-a'],UUID(parent['run_id']))


def test_approval_rechecks_material_source_after_actual_parent_lock_wait(native_fixture):
    a=native_fixture;f,parent,_,_=a;act(a,'REQUEST');data=body(a,'APPROVE')
    with f[1].connect() as blocker:
        blocker.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(parent['preparation_id'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(act,a,'APPROVE',data=data)
            deadline=monotonic()+3;waiting=False
            while monotonic()<deadline:
                with f[1].connect() as observer:
                    waiting=bool(observer.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM preparations%' LIMIT 1").fetchone())
                if waiting:break
                Event().wait(.02)
            assert waiting,'actual PostgreSQL lock wait required'
            blocker.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(parent['preparation_id'],));blocker.commit()
            with pytest.raises(Conflict):future.result(timeout=5)
    assert ledger(a)['state']=='REQUESTED' and not ledger(a)['leases']


def test_permission_revoked_before_approval_is_not_cached(native_fixture):
    a=native_fixture;act(a,'REQUEST');data=body(a,'APPROVE')
    a[0][1].revoke_capability('executor-a','READ')
    with pytest.raises((Denied,Conflict)):act(a,'APPROVE',data=data)
    assert ledger(a)['state']=='REQUESTED'


def test_case_cancel_blocks_approve_preserves_history_recovery_and_request_cancel(native_fixture):
    a=native_fixture;f,parent,bridge,_=a
    first=act(a,'REQUEST',key='before-case-cancel')
    path='/api/preparations/'+parent['preparation_id']+'/case-cancellation'
    view=f[3].get(path,headers=headers(f[2])).json()
    assert view['can_cancel'],view
    data=dict(case_id=view['case_id'],expected_preparation_revision=view['preparation_revision'],
              expected_lifecycle_revision=view['lifecycle_revision'],expected_source_sha256=view['source_sha256'],
              confirm_cancel=True,reason='SYNTHETIC ordinary Case cancellation')
    response=f[3].post(path,headers=headers(f[2],key='cancel-case'),json=data)
    assert response.status_code==200,response.text
    approval=body(a,'APPROVE')
    current=bridge.read(f[2][APPROVER],UUID(parent['run_id']))
    assert current['can_approve'] is False
    with pytest.raises(Conflict,match='cancelled'):act(a,'APPROVE',data=approval)
    assert bridge.recover(f[2]['fixture-a'],UUID(parent['run_id']),'before-case-cancel')['receipt']==first
    assert act(a,'CANCEL')['state']=='CANCELLED'
    with pytest.raises(Conflict,match='cancelled'):act(a,'REQUEST')
    assert snapshot(f[1])==a[3]


def test_native_marker_is_never_legacy_even_with_cold_store(native_fixture):
    a=native_fixture;f,parent,_,_=a
    # An unpersisted supplied row has no trustworthy legacy provenance once
    # native storage exists. Cold stores deny it rather than losing a marker.
    with f[0].connect() as c:
        p=f[0].auth(c,f[2]['executor-a'],lock=True)
        assignment=dict(principal_id=p['id'],run_id=UUID(parent['run_id']),park_id=p['park_id'],org_id=p['org_id'],active=True)
        cold=Store(f[0].dsn)
        assert not cold.assignment_allowed(c,p,parent['run_id'],assignment=assignment)
        for marker in (None,{},dict(namespace=native.NAMESPACE),dict(namespace='UNKNOWN')):
            marked=dict(assignment,native_access=marker)
            assert not cold.assignment_allowed(c,p,parent['run_id'],assignment=marked)
            assert not cold.assignment_allowed(c,p,parent['run_id'],assignment=dict(marked,managed_access={'namespace':'ISOLATED'}))
    assert snapshot(f[1])==a[3]


def test_unissued_test_permit_and_default_constructor_are_closed(native_fixture):
    a=native_fixture;f,parent,bridge,_=a
    invalid=native.NativeRunAccess(f[0],test_permit=copy(bridge.test_permit))
    with pytest.raises(Denied):invalid.command(f[2]['fixture-a'],UUID(parent['run_id']),'closed',body(a,'REQUEST'))
    with pytest.raises(Denied):native.NativeRunAccess(f[0]).command(f[2]['fixture-a'],UUID(parent['run_id']),'closed',body(a,'REQUEST'))
    assert ledger(a) is None


@pytest.mark.parametrize('fields',[{'unknown':1},{'reason':' '},{'capability':'EXECUTE'},
    {'requested_validity':{'valid_from':'2026-10-11T00:00:00+08:00','valid_until':'2026-10-11T01:00:00+08:00','timezone':'UTC'}},
    {'approved_validity':{'valid_from':'2026-10-11T00:00:00Z','valid_until':'2026-10-11T01:00:00Z','timezone':'UTC'}}])
def test_native_strict_dto(native_fixture,fields):
    data=body(native_fixture,'REQUEST').model_dump();data.update(fields)
    with pytest.raises(ValidationError):RunCommand.model_validate(data)
