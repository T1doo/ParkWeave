"""Ordinary current-preparation admission; synthetic setup is separate."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import json,os,subprocess,time
from uuid import UUID,uuid4
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from parkweave import case_step_assignments as cs,dispatch_notices as dn
from parkweave.api import configured_app,create_app
from parkweave.store import Denied,Store
from test_preparation import preparation_fixture,headers,add,command as prep_command
from test_executor_receipts import receipt_fixture,act
from test_case_step_assignments import prepared,dependency,ok,REVIEWER
from test_service_dispatches import offer,command as decision
from service_release_acceptance_support import authority_snapshot
from ordinary_case_step_support import ordinary_api,worker_once

OUT=Path(os.environ.get('PARKWEAVE_ORDINARY_CASE_STEP_EVIDENCE','.runtime/ordinary-case-step-20261018/development'))
CONFIGS=('PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_RUNTIME_WRITE_CONFIG','PARKWEAVE_SERVICE_PROFILE',
    'PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG','PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG','PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG')

@pytest.fixture
def ordinary(receipt_fixture,monkeypatch):
    f=receipt_fixture
    for name in CONFIGS:monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn);monkeypatch.setenv('PARKWEAVE_MODE','LOCAL')
    monkeypatch.setenv('PARKWEAVE_CASE_STEP_MODE',cs.ORDINARY_MODE)
    baseline=authority_snapshot(f[1])
    with TestClient(configured_app()) as api:yield (*f[:3],api),baseline

def inbox(f,user='executor-a'):return f[3].get('/api/dispatch-notices',headers=headers(f[2],user))
def dispatch(f,d,user='executor-a'):return f[3].get('/api/service-dispatches/'+d['dispatch_id'],headers=headers(f[2],user))
def notice(f,n,action,user='executor-a'):
    return f[3].post('/api/dispatch-notices/'+n['event_id']+'/commands',headers=headers(f[2],user),json=dict(action=action,expected_revision=n['revision']))
def consume(f):
    scope=cs.from_environment(Store(f[0].dsn),{'PARKWEAVE_CASE_STEP_MODE':cs.ORDINARY_MODE})
    for _ in range(20):
        if not dn.consume(scope.store,case_step_assignments=scope):return
    raise AssertionError('bounded owned queue did not settle')

def test_ordinary_existing_preparation_receipt_and_notices_without_run_grant(ordinary):
    f,baseline=ordinary;p=prepared(f);key=uuid4().hex;d=ok(offer(f,p,key=key)[0],201)
    assert d['assignment_contract']==cs.ORDINARY_CONTRACT and not d['run_access_granted']
    assert ok(offer(f,p,key=key)[0],201)['assignment_valid_until']==d['assignment_valid_until']
    consume(f);n=ok(inbox(f))['items'][0]
    ok(notice(f,n,'MARK_READ'),409);ok(notice(f,n,'OPEN'));marked=ok(notice(f,n,'MARK_READ'))
    assert ok(notice(f,n,'OPEN'))==marked==ok(notice(f,n,'MARK_READ'))
    d=ok(decision(f,d,'ACCEPT'));r=ok(f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')))
    r=ok(act(f,r,'SUBMIT'));r=ok(act(f,r,'ACKNOWLEDGE'))
    assert r['step']['state']=='LOCAL_ACKNOWLEDGED' and not r['case_goal_completed']
    consume(f);assert len(ok(inbox(f,'fixture-a'))['items'])==2
    assert authority_snapshot(f[1])==baseline
    ok(f[3].get('/api/runs/'+p['run_id'],headers=headers(f[2],'executor-a')),403)
    with TestClient(create_app(Store(f[0].dsn))) as default:
        ok(default.get('/api/service-dispatches/'+d['dispatch_id'],headers=headers(f[2],'executor-a')),403)
        assert ok(default.get('/api/dispatch-notices',headers=headers(f[2],'executor-a')))['items']==[]

@pytest.mark.parametrize('key',CONFIGS)
def test_ordinary_mode_refuses_native_and_other_provider_configuration(ordinary,monkeypatch,key):
    f,_=ordinary;monkeypatch.setenv(key,'{}')
    with pytest.raises(Denied):configured_app()
    with pytest.raises(Denied):cs.from_environment(Store(f[0].dsn),dict(os.environ))

@pytest.mark.parametrize('mode',['','ISOLATED_CASE_STEP_ASSIGNMENT_V1'])
def test_unknown_or_isolated_mode_is_not_ordinary_admission(ordinary,monkeypatch,mode):
    monkeypatch.setenv('PARKWEAVE_CASE_STEP_MODE',mode)
    with pytest.raises(Denied):configured_app()

@pytest.mark.parametrize('target',['owner_prepare','owner_read','owner_execute','reviewer_grant','reviewer_read','executor_read','catalog'])
def test_missing_current_input_cannot_offer_or_create_authority(ordinary,target):
    f,_=ordinary;p=prepared(f)
    with f[1].connect() as c:
        if target=='catalog':c.execute("UPDATE preparation_catalog SET source=%s WHERE park_id='park-a'",(Jsonb(dict(kind='UNKNOWN')),))
        elif target.endswith('prepare') or target=='reviewer_grant':
            c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',('fixture-a' if target.startswith('owner') else REVIEWER,))
        else:
            actor='fixture-a' if target.startswith('owner') else REVIEWER if target.startswith('reviewer') else 'executor-a'
            c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(actor,'EXECUTE' if target=='owner_execute' else 'READ'))
    before=authority_snapshot(f[1]);ok(offer(f,p)[0],403)
    with f[1].connect() as c:assert not c.execute('SELECT 1 FROM service_dispatches').fetchone()
    assert authority_snapshot(f[1])==before

@pytest.mark.parametrize('change',['executor_read','restore_generation','material','catalog','owner_execute','reviewer_grant','inactive','role'])
def test_current_changes_deny_step_after_factory_rebuild(ordinary,change):
    f,_=ordinary;p=prepared(f);d=ok(offer(f,p)[0],201);consume(f);n=ok(inbox(f))['items'][0]
    with f[1].connect() as c:
        if change in ('executor_read','restore_generation'):
            c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
            if change=='restore_generation':c.execute("UPDATE capability_grants SET active=true WHERE principal_id='executor-a' AND capability='READ'")
        elif change=='material':c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
        elif change=='catalog':c.execute("UPDATE preparation_catalog SET name=name||' changed' WHERE park_id='park-a'")
        elif change=='owner_execute':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        elif change=='reviewer_grant':c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(REVIEWER,))
        elif change=='inactive':c.execute("UPDATE principals SET active=false WHERE id='executor-a'")
        else:c.execute("UPDATE principals SET role='resource_admin' WHERE id='executor-a'")
    with TestClient(configured_app()) as api:
        fresh=(*f[:3],api);ok(dispatch(fresh,d),403);ok(decision(fresh,d,'ACCEPT'),403);ok(notice(fresh,n,'OPEN'),403)
        if change!='reviewer_grant':ok(decision(fresh,d,'WITHDRAW'))
    owner=ok(dispatch(f,d,'fixture-a'));assert not owner['can_accept']
    owner_notice=ok(inbox(f,'fixture-a'))['items'][0];ok(notice(f,owner_notice,'OPEN','fixture-a'));ok(notice(f,owner_notice,'MARK_READ','fixture-a'))

@pytest.mark.parametrize('actor',['fixture-b','fixture-c','executor-b','executor-c','unassigned'])
def test_other_people_never_inherit_the_offered_step(ordinary,actor):
    f,_=ordinary;p=prepared(f);d=ok(offer(f,p)[0],201);consume(f);n=ok(inbox(f))['items'][0]
    ok(dispatch(f,d,actor),403);ok(notice(f,n,'OPEN',actor),403)
    assert ok(f[3].get('/api/service-dispatches',headers=headers(f[2],actor)))['items']==[]

def test_old_isolated_events_are_never_adopted_or_consumed(ordinary):
    f,_=ordinary;old=dependency(f)
    with TestClient(create_app(f[0],case_step_assignments=old)) as api:
        isolated=(*f[:3],api);p=prepared(isolated);d=ok(offer(isolated,p)[0],201)
    consume(f);worker_once(f,OUT/('isolated-worker-'+uuid4().hex[:8]));ok(dispatch(f,d,'fixture-a'),403);ok(dispatch(f,d),403)
    with f[1].connect() as c:
        assert not c.execute('SELECT 1 FROM dispatch_notices').fetchone()
        assert {r['state'] for r in c.execute('SELECT state FROM dispatch_notice_outbox')}=={'PENDING'}
    with TestClient(configured_app()) as api:ok(dispatch((*f[:3],api),d),403)

@pytest.mark.parametrize('active',[True,False])
def test_existing_run_assignment_is_no_fallback_after_rebuild(ordinary,active):
    f,_=ordinary;p=prepared(f);f[1].assign_status('executor-a',UUID(p['run_id']),active=active)
    before=authority_snapshot(f[1])
    with TestClient(configured_app()) as api:ok(offer((*f[:3],api),p)[0],403)
    assert authority_snapshot(f[1])==before

def test_native_service_mixing_is_rejected_without_fallback(ordinary):
    f,_=ordinary;store=Store(f[0].dsn);store._native_run_access=object()
    with pytest.raises(Denied):cs.OrdinaryCaseStepAssignments(store)

def test_expired_first_offer_survives_factory_rebuild_and_owner_history(ordinary,monkeypatch):
    f,_=ordinary;p=prepared(f);d=ok(offer(f,p)[0],201);consume(f);n=ok(inbox(f))['items'][0]
    clock=cs._now;monkeypatch.setattr(cs,'_now',lambda c:clock(c)+timedelta(hours=2))
    with TestClient(configured_app()) as api:
        fresh=(*f[:3],api);ok(dispatch(fresh,d),403);ok(decision(fresh,d,'ACCEPT'),403);ok(notice(fresh,n,'MARK_READ'),403)
        assert ok(dispatch(fresh,d,'fixture-a'))['assignment_valid_until']==d['assignment_valid_until']
        owner=ok(inbox(fresh,'fixture-a'))['items'][0];ok(notice(fresh,owner,'OPEN','fixture-a'));ok(notice(fresh,owner,'MARK_READ','fixture-a'))
        ok(decision(fresh,d,'WITHDRAW'));ok(offer(fresh,p)[0],409)

def test_concurrent_consumers_and_parallel_cases_keep_their_own_bindings(ordinary):
    f,baseline=ordinary;p=prepared(f,'ONE');q=prepared(f,'TWO')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first,second=list(pool.map(lambda parent:ok(offer(f,parent)[0],201),[p,q]))
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:consume(f),range(6)))
    items=ok(inbox(f))['items'];assert {n['preparation_id'] for n in items}=={p['preparation_id'],q['preparation_id']}
    assert {ok(dispatch(f,d))['preparation_id'] for d in [first,second]}=={p['preparation_id'],q['preparation_id']}
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM dispatch_notices').fetchone()['n']==4
    assert authority_snapshot(f[1])==baseline

def test_actual_lock_wait_crosses_original_deadline_and_rolls_back(ordinary,monkeypatch):
    f,_=ordinary;monkeypatch.setattr(cs._OrdinaryCaseStep,'_offer_deadline',lambda self,c:cs._now(c)+timedelta(seconds=2))
    p=prepared(f);d=ok(offer(f,p)[0],201);consume(f);n=ok(inbox(f))['items'][0];ok(notice(f,n,'OPEN'))
    with f[1].connect() as lock:
        lock.execute("SELECT * FROM dispatch_notices WHERE recipient_id='executor-a' FOR UPDATE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            result=pool.submit(notice,f,n,'MARK_READ');observed=False
            for _ in range(40):
                with f[1].connect() as c:observed=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM dispatch_notices%' LIMIT 1").fetchone())
                if observed:break
                time.sleep(.02)
            assert observed;time.sleep(2.05);lock.commit();ok(result.result(timeout=10),403)
    with f[1].connect() as c:assert c.execute("SELECT read_at FROM dispatch_notices WHERE recipient_id='executor-a'").fetchone()['read_at'] is None
    assert ok(dispatch(f,d,'fixture-a'))['assignment_valid_until']==d['assignment_valid_until']

def test_new_worker_after_first_deadline_suppresses_executor_without_renewal(ordinary,monkeypatch):
    f,_=ordinary;monkeypatch.setattr(cs._OrdinaryCaseStep,'_offer_deadline',lambda self,c:cs._now(c)+timedelta(seconds=2))
    p=prepared(f);d=ok(offer(f,p)[0],201);time.sleep(2.05)
    worker_once(f,OUT/('expired-worker-'+uuid4().hex[:8]))
    with f[1].connect() as c:
        assert c.execute("SELECT state FROM dispatch_notice_outbox WHERE recipient_id='executor-a'").fetchone()['state']=='SUPPRESSED'
        assert not c.execute("SELECT 1 FROM dispatch_notices WHERE recipient_id='executor-a'").fetchone()
    n=ok(inbox(f,'fixture-a'))['items'][0];assert n['historical'] and not n['actionable']
    assert n['assignment_valid_until']==d['assignment_valid_until'];ok(dispatch(f,d),403)
