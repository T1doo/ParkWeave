"""Same-Case capacity effects and independent actual-row checks in real PG/API."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import UUID, uuid4
import pytest, psycopg

from parkweave import case_resource_delivery as delivery, preparation as prep, case_resources as cr
from parkweave.store import Store, Conflict
from test_case_resources import link_fixture
from test_resource_bundles import bundle, states, totals, cancel, write as bundle_write
from test_preparation import preparation_fixture, headers, command as material_command
from test_executor_receipts import receipt_fixture, ready
from test_service_case_steps import setup, adopt, verified, read as plan_read, command as plan_command


def prepared(f):
    p = setup(f, 'LOCAL_CASE_RESOURCE_ASSOCIATION')
    r = adopt(f,p); assert r.status_code == 201,r.text
    verified(f,p,'P1')
    return p


def preview(f,p,data,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/resource-delivery/preview',headers=headers(f[2],user),json=data)


def quoted(f,p,data):
    r=preview(f,p,data); assert r.status_code == 200,r.text
    q=r.json()
    return {**data, 'expected_preparation_revision':q['expected_preparation_revision'],
        'expected_plan_revision':q['expected_plan_revision'],'expected_source_sha256':q['source_sha256'],
        'valid_until':q['valid_until'],'reason':'SYNTHETIC explicit first capacity delivery'}


def submit(f,p,data,key=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/resource-delivery',headers=headers(f[2],user,key or uuid4().hex),json=data)


def recover(f,p,key,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/resource-delivery/recovery/'+key,headers=headers(f[2],user))


def effects(f):
    with f[1].connect() as c:
        return [c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in
            ('synthetic_resource_combinations','synthetic_resource_combination_members','synthetic_resource_combination_receipts','resource_case_claims','case_resource_links')]


@pytest.mark.parametrize('n',[3,8])
def test_actual_capacity_case_atomic_delivery_independent_p2_and_cold_recovery(link_fixture,n):
    f=link_fixture;p=prepared(f);hs,d=bundle(f,n);body=quoted(f,p,d);key=uuid4().hex
    assert states(f,hs)==['HELD']*n and effects(f)==[0]*5
    r=submit(f,p,body,key);assert r.status_code==201,r.text;x=r.json()
    assert states(f,hs)==['CONFIRMED']*n and effects(f)==[1,n,1,1,1]
    assert x['independent_check']['status']=='CURRENT' and x['link']['case_id']==p['case_id']
    assert not x['case_goal_completed'] and x['formal_approval']=='NOT_IMPLEMENTED' and not x['formal_release']
    assert x['delivery_binding']['context']['service_version']==1
    assert plan_read(f,p).json()['steps'][1]['state']!='VERIFIED'
    verified(f,p,'P2');assert recover(f,p,key).json()['independent_check']['status']=='CURRENT'
    again=delivery.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key)
    assert str(again['link']['id'])==x['link']['id']
    assert submit(f,p,{**body,'members':list(reversed(body['members']))},key).json()['receipt']==x['receipt']
    assert effects(f)==[1,n,1,1,1]
    cancel(f,x['combination']['id']);now=recover(f,p,key).json()
    assert now['independent_check']['status']=='NEEDS_RECHECK' and 'RESOURCE_CANCELLED' in now['independent_check']['issues']
    assert submit(f,p,body,key).json()['combination']['state']=='CANCELLED' and states(f,hs)==['RELEASED']*n


@pytest.mark.parametrize('bad',['source','materials','plan','p1','hold','expired','disabled','capacity','grant'])
def test_any_changed_prerequisite_rejects_without_partial_delivery(link_fixture,bad):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d)
    with f[1].connect() as c:
        if bad=='source':c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','2')")
        elif bad=='materials':c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
        elif bad=='plan':c.execute("UPDATE preparations SET service_case_plan=jsonb_set(service_case_plan,'{revision}',to_jsonb((service_case_plan->>'revision')::int+1)) WHERE id=%s",(p['preparation_id'],))
        elif bad=='p1':c.execute("UPDATE preparations SET service_case_plan=jsonb_set(service_case_plan,'{steps,0,invalidated}','true') WHERE id=%s",(p['preparation_id'],))
        elif bad=='hold':c.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(hs[2]['resource_id'],))
        elif bad=='expired':c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()-interval '1 second',created_at=clock_timestamp()-interval '1 hour' WHERE id=%s",(hs[2]['id'],))
        elif bad=='disabled':c.execute('UPDATE synthetic_resources SET enabled=false WHERE id=%s',(hs[2]['resource_id'],))
        elif bad=='capacity':c.execute('UPDATE synthetic_resource_holds SET quantity=2 WHERE id=%s',(hs[2]['id'],))
        else:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    assert submit(f,p,body).status_code in (403,409) and effects(f)==[0]*5 and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('table',['synthetic_resource_combination_receipts','resource_case_claims','case_resource_links'])
def test_failure_after_capacity_update_rolls_back_confirmation_and_all_associations(link_fixture,table):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d)
    with f[1].connect() as c:
        c.execute("CREATE FUNCTION delivery_fault() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'synthetic delivery fault';END$$")
        c.execute('CREATE TRIGGER delivery_fault BEFORE INSERT ON '+table+' FOR EACH ROW EXECUTE FUNCTION delivery_fault()')
    with pytest.raises(psycopg.Error):delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**body))
    assert effects(f)==[0]*5 and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','unassigned'])
def test_current_role_scope_rejects_private_delivery_and_any_write(link_fixture,user):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d);key=uuid4().hex
    assert submit(f,p,body,key).status_code==201
    assert preview(f,p,d,user).status_code==submit(f,p,body,key,user).status_code==recover(f,p,key,user).status_code==403
    assert effects(f)==[1,3,1,1,1]


def test_two_keys_compete_for_first_case_and_all_resource_effects(link_fixture):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d)
    def run(_):
        try:return delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**body))
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,range(2)))
    assert rows.count('CONFLICT')==1 and effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3


def test_actor_key_scope_changed_body_and_old_bundle_key_conflict(link_fixture):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d);key=uuid4().hex
    assert submit(f,p,body,key).status_code==201
    assert submit(f,p,{**body,'reason':'changed reason'},key).status_code==409
    p2=prepared(f);assert recover(f,p2,key).status_code==409
    assert bundle_write(f,d,key=key).status_code==409
    assert effects(f)==[1,3,1,1,1]


@pytest.mark.parametrize('kind',['EXECUTE','HOLD','READ','PREPARE'])
def test_revocation_precedes_replay_read_only_recovery_intersection(link_fixture,kind):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d);key=uuid4().hex
    assert submit(f,p,body,key).status_code==201
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if kind in ('HOLD','READ'):c.execute('UPDATE synthetic_resource_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',kind))
        elif kind=='EXECUTE':c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        else:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
    assert submit(f,p,body,key).status_code==403
    assert recover(f,p,key).status_code==(200 if kind in ('EXECUTE','HOLD') else 403)
    assert effects(f)==[1,3,1,1,1]


def test_source_change_history_immutable_rows_and_recovery_not_observed(link_fixture):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d);key=uuid4().hex
    assert recover(f,p,key).json()['status']=='NOT_OBSERVED';x=submit(f,p,body,key).json()
    for t in ('resource_case_claims','case_resource_links','synthetic_resource_combination_receipts'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute('DELETE FROM '+t)
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','2')")
    r=recover(f,p,key);assert r.status_code==200,r.text
    assert r.json()['independent_check']['status']=='NEEDS_RECHECK' and r.json()['receipt']==x['receipt']
    assert effects(f)==[1,3,1,1,1]


def test_same_key_concurrent_exact_retry_has_one_atomic_effect(link_fixture):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d);key=uuid4().hex
    def run(_):return delivery.deliver(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key,delivery.Deliver(**body))
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,range(2)))
    assert rows[0]['receipt']==rows[1]['receipt'] and effects(f)==[1,3,1,1,1]


@pytest.mark.parametrize('bad',['proof-context','proof-key','proof-fingerprint','missing-association'])
def test_recovery_rejects_missing_or_corrupt_original_proof(link_fixture,bad):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d);key=uuid4().hex
    assert submit(f,p,body,key).status_code==201
    # Fixture administrator damage is outside app privileges; recovery must fail closed.
    with f[1].connect() as c:
        if bad=='missing-association':c.execute('DELETE FROM case_resource_links')
        else:
            field={'proof-context':'context','proof-key':'request_key','proof-fingerprint':'fingerprint'}[bad]
            c.execute("UPDATE synthetic_resource_combination_receipts SET payload=jsonb_set(payload,ARRAY['delivery_binding',%s],'null')",(field,))
    before=effects(f);r=recover(f,p,key);assert r.status_code==409,r.text;assert effects(f)==before


@pytest.mark.parametrize('field,value',[('reason',' '),('reason',''),('formal_approval',True),('expected_plan_revision',0),('valid_until','2026-10-09T00:00:00'),('members',[])])
def test_strict_write_body_never_accepts_invented_approval_or_unbounded_input(link_fixture,field,value):
    f=link_fixture;p=prepared(f);hs,d=bundle(f);body=quoted(f,p,d)
    r=submit(f,p,{**body,field:value});assert r.status_code==422,r.text
    assert effects(f)==[0]*5 and states(f,hs)==['HELD']*3


def test_lock_wait_expiry_rechecks_database_clock_without_partial_writes(link_fixture):
    import threading,time
    from datetime import datetime,timedelta,timezone
    f=link_fixture;p=prepared(f);hs,d=bundle(f)
    with f[1].connect() as c:c.execute('UPDATE synthetic_resource_holds SET expires_at=%s',(datetime.now(timezone.utc)+timedelta(seconds=1),))
    body=quoted(f,p,d);result=[];started=threading.Event()
    def run():
        started.set()
        try:delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**body));result.append('BAD')
        except Conflict:result.append('EXPIRED')
    with f[1].connect() as c:
        c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],));worker=threading.Thread(target=run);worker.start();assert started.wait(2);time.sleep(1.2)
    worker.join(8);assert not worker.is_alive() and result==['EXPIRED'] and effects(f)==[0]*5

from datetime import datetime, timedelta, timezone
import threading, time
from test_service_case_steps import GOALS
from test_request_intents import save


def test_case_row_wait_past_original_hold_quote_expiry_rolls_back(link_fixture,monkeypatch):
    f=link_fixture;p=prepared(f);hs,d=bundle(f)
    with f[1].connect() as c:
        c.execute('UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()+interval \'1.1 second\' WHERE id=ANY(%s)',([UUID(h['id']) for h in hs],))
    body=quoted(f,p,d);at_bind=threading.Event();original=cr._bind_locked
    def observe(*args,**kwargs):at_bind.set();return original(*args,**kwargs)
    monkeypatch.setattr(cr,'_bind_locked',observe)
    def run():
        try:return delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**body))
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            c.execute('SELECT id FROM cases WHERE id=%s FOR SHARE',(p['case_id'],))
            future=pool.submit(run);assert at_bind.wait(2),'did not reach Case binding after capacity confirmation'
            time.sleep(1.3)
        result=future.result(timeout=8)
    assert result=='CONFLICT'
    assert effects(f)==[0]*5 and states(f,hs)==['HELD']*3


def test_multi_required_goals_survive_delivery_and_p2_verify(link_fixture):
    f=link_fixture;p=ready(f)
    r=save(f,p,goals=GOALS,text='SYNTHETIC all original adapter goals');assert r.status_code==200
    p={**p,'revision':r.json()['revision']}
    p=material_command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC all-goal review').json()
    p=material_command(f,p,'CONFIRM',reason='SYNTHETIC all-goal confirmation').json()
    assert adopt(f,p).status_code==201;verified(f,p,'P1')
    hs,d=bundle(f);body=quoted(f,p,d);key=uuid4().hex;r=submit(f,p,body,key);assert r.status_code==201,r.text
    current=plan_read(f,p).json();assert current['required_goals']==GOALS
    assert next(s for s in current['steps'] if s['adapter_id']=='P2')['state']!='VERIFIED'
    verified(f,p,'P2');current=plan_read(f,p).json();assert current['required_goals']==GOALS
    assert any(s['state']!='VERIFIED' for s in current['steps'][2:])
    assert recover(f,p,key).json()['independent_check']['status']=='CURRENT'


def test_distinct_cases_competing_same_members_keep_one_exact_claim(link_fixture):
    f=link_fixture;p1=prepared(f);p2=prepared(f);hs,d=bundle(f);b1=quoted(f,p1,d);b2=quoted(f,p2,d)
    def run(item):
        p,b=item
        try:return delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**b))
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,[(p1,b1),(p2,b2)]))
    assert results.count('CONFLICT')==1
    result=next(r for r in results if isinstance(r,dict));assert effects(f)==[1,3,1,1,1]
    assert str(result['link']['case_id']) in (p1['case_id'],p2['case_id']) and states(f,hs)==['CONFIRMED']*3


def test_committed_original_key_recovers_after_preview_and_source_hold_ttl(link_fixture):
    f=link_fixture;p=prepared(f);hs,d=bundle(f)
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()+interval '1.3 second'")
    body=quoted(f,p,d);key=uuid4().hex;r=submit(f,p,body,key);assert r.status_code==201,r.text
    original=r.json()['receipt'];time.sleep(1.5)
    for current in (submit(f,p,body,key),recover(f,p,key)):
        assert current.status_code in (200,201),current.text
        assert current.json()['receipt']==original and current.json()['independent_check']['status']=='CURRENT'
    assert effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3
